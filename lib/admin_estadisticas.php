<?php
// lib/admin_estadisticas.php — consultas del panel de administrador.
//
// Reglas:
// - Solo consultas preparadas. El período y los límites llegan como enteros ya validados.
// - Todo lo que sale de aquí es AGREGADO: nunca correo, nombre, fecha de nacimiento,
//   contraseña ni perfil_id. La edad se calcula en memoria a partir de la fecha cifrada y
//   solo se devuelven rangos con al menos EDAD_MIN_CUENTAS cuentas.
// - Las cuentas con rol 'admin' no cuentan: ni como cuentas, perfiles o edad, ni por las
//   aperturas y "me gusta" de sus perfiles (sin_eventos_de_admin). Sus búsquedas e impresiones
//   NO se pueden separar: no llevan perfil, a propósito (fase 2), así que sí suman.
// - Las impresiones no llevan perfil (fase 2), así que "perfil activo" se mide con
//   aperturas y "me gusta".
declare(strict_types=1);

require_once __DIR__ . '/cifrado.php';

const PERIODOS_VALIDOS = [7, 30, 90];
const EDAD_MIN_CUENTAS = 5;
const MIN_IMPRESIONES_POCO_ABIERTO = 20;
const RANGOS_EDAD = [            // [etiqueta, edad mínima, edad máxima]
    ['menos de 18', 0, 17],
    ['18 a 24', 18, 24],
    ['25 a 34', 25, 34],
    ['35 a 44', 35, 44],
    ['45 o más', 45, 200],
];

/**
 * Condición SQL que deja fuera los eventos de perfiles de cuentas administradoras. Los eventos
 * sin perfil (las impresiones, o los de un perfil ya borrado) se conservan. $alias es SIEMPRE
 * una constante escrita en este archivo, nunca un dato de la petición.
 */
function sin_eventos_de_admin(string $alias): string
{
    return "NOT EXISTS (SELECT 1 FROM perfiles pfa JOIN cuentas ca ON ca.id = pfa.cuenta_id
        WHERE pfa.id = {$alias}.perfil_id AND ca.rol = 'admin')";
}

/** Fechas (Y-m-d H:i:s) del período de `dias` días que termina ahora y del anterior. */
function periodos(int $dias, ?DateTimeImmutable $ahora = null): array
{
    $ahora ??= new DateTimeImmutable('now');
    $inicio = $ahora->sub(new DateInterval("P{$dias}D"));
    $inicioAnterior = $inicio->sub(new DateInterval("P{$dias}D"));
    $f = fn(DateTimeImmutable $d) => $d->format('Y-m-d H:i:s');
    return ['desde' => $f($inicio), 'hasta' => $f($ahora), 'desde_anterior' => $f($inicioAnterior), 'hasta_anterior' => $f($inicio)];
}

function variacion(int $actual, int $anterior): ?float
{
    return $anterior === 0 ? null : round(($actual - $anterior) / $anterior * 100, 1);
}

// --------------------------------------------------------------------------- 1. Resumen

function seccion_resumen(PDO $db, int $dias): array
{
    $p = periodos($dias);
    $contar = function (string $sql, array $params) use ($db): int {
        $s = $db->prepare($sql);
        $s->execute($params);
        return (int)$s->fetchColumn();
    };
    $enPeriodo = fn(string $sql) => [
        $contar($sql, [$p['desde'], $p['hasta']]),
        $contar($sql, [$p['desde_anterior'], $p['hasta_anterior']]),
    ];

    [$busquedas, $busquedasAnt] = $enPeriodo('SELECT COUNT(*) FROM consultas WHERE creado_en >= ? AND creado_en < ?');
    [$aperturas, $aperturasAnt] = $enPeriodo("SELECT COUNT(*) FROM eventos e WHERE e.tipo = 'apertura' AND e.creado_en >= ? AND e.creado_en < ? AND " . sin_eventos_de_admin('e'));
    [$gustas, $gustasAnt] = $enPeriodo("SELECT COUNT(*) FROM eventos e WHERE e.tipo = 'like' AND e.creado_en >= ? AND e.creado_en < ? AND " . sin_eventos_de_admin('e'));
    [$activos, $activosAnt] = $enPeriodo("SELECT COUNT(DISTINCT e.perfil_id) FROM eventos e
        JOIN perfiles pf ON pf.id = e.perfil_id JOIN cuentas c ON c.id = pf.cuenta_id
        WHERE c.rol = 'usuario' AND e.tipo IN ('apertura', 'like') AND e.creado_en >= ? AND e.creado_en < ?");
    [$cuentasNuevas, $cuentasNuevasAnt] = $enPeriodo("SELECT COUNT(*) FROM cuentas WHERE rol = 'usuario' AND creado_en >= ? AND creado_en < ?");

    $tarjeta = fn(int $v, int $ant) => ['valor' => $v, 'anterior' => $ant, 'variacion' => variacion($v, $ant)];
    return [
        'cuentas' => ['valor' => $contar("SELECT COUNT(*) FROM cuentas WHERE rol = 'usuario'", []), 'nuevas' => $tarjeta($cuentasNuevas, $cuentasNuevasAnt)],
        'perfiles' => ['valor' => $contar("SELECT COUNT(*) FROM perfiles pf JOIN cuentas c ON c.id = pf.cuenta_id WHERE c.rol = 'usuario'", [])],
        'perfiles_activos' => $tarjeta($activos, $activosAnt),
        'busquedas' => $tarjeta($busquedas, $busquedasAnt),
        'aperturas' => $tarjeta($aperturas, $aperturasAnt),
        'me_gusta' => $tarjeta($gustas, $gustasAnt),
        'por_dia' => actividad_por_dia($db, $dias),
    ];
}

/** Un punto por día del período, aunque no haya actividad ese día. */
function actividad_por_dia(PDO $db, int $dias): array
{
    $p = periodos($dias);
    $s = $db->prepare("SELECT DATE(creado_en) AS dia,
            SUM(tipo = 'apertura') AS aperturas, SUM(tipo = 'like') AS me_gusta
        FROM eventos e WHERE e.creado_en >= ? AND e.creado_en < ? AND " . sin_eventos_de_admin('e') . " GROUP BY dia");
    $s->execute([$p['desde'], $p['hasta']]);
    $eventos = array_column($s->fetchAll(), null, 'dia');
    $s = $db->prepare('SELECT DATE(creado_en) AS dia, COUNT(*) AS n FROM consultas WHERE creado_en >= ? AND creado_en < ? GROUP BY dia');
    $s->execute([$p['desde'], $p['hasta']]);
    $busquedas = array_column($s->fetchAll(), 'n', 'dia');

    $puntos = [];
    $d = new DateTimeImmutable(substr($p['desde'], 0, 10));
    $fin = new DateTimeImmutable(substr($p['hasta'], 0, 10));
    while ($d <= $fin) {
        $dia = $d->format('Y-m-d');
        $puntos[] = ['dia' => $dia, 'busquedas' => (int)($busquedas[$dia] ?? 0),
            'aperturas' => (int)($eventos[$dia]['aperturas'] ?? 0), 'me_gusta' => (int)($eventos[$dia]['me_gusta'] ?? 0)];
        $d = $d->add(new DateInterval('P1D'));
    }
    return $puntos;
}

// --------------------------------------------------------------------------- títulos

/** ['origen:id' => título] de los documentos dados (contenido público). */
function titulos_de(PDO $db, array $refs): array
{
    $ids = ['ejercicios' => [], 'articulos' => []];
    foreach ($refs as [$origen, $id]) {
        $ids[$origen][] = (int)$id;
    }
    $titulos = [];
    foreach (['ejercicios' => 'SELECT id, nombre_es AS titulo FROM ejercicios WHERE id IN (%s)',
              'articulos' => 'SELECT id, titulo FROM articulos WHERE id IN (%s)'] as $origen => $sql) {
        if (!$ids[$origen]) {
            continue;
        }
        $s = $db->prepare(sprintf($sql, implode(',', array_fill(0, count($ids[$origen]), '?'))));
        $s->execute($ids[$origen]);
        foreach ($s->fetchAll() as $f) {
            $titulos["$origen:{$f['id']}"] = $f['titulo'];
        }
    }
    return $titulos;
}

/** ['origen:id' => [nombres de etiquetas]] (hasta 4 por documento, músculo y tema primero). */
function etiquetas_de(PDO $db, array $refs): array
{
    if (!$refs) {
        return [];
    }
    $pares = implode(',', array_fill(0, count($refs), '(?, ?)'));
    $valores = [];
    foreach ($refs as [$origen, $id]) {
        array_push($valores, $origen, (int)$id);
    }
    $s = $db->prepare("SELECT de.origen, de.doc_id, e.nombre_visible FROM documento_etiquetas de
        JOIN etiquetas e ON e.id = de.etiqueta_id WHERE (de.origen, de.doc_id) IN ($pares)
        ORDER BY FIELD(e.tipo, 'musculo', 'tema', 'equipamiento', 'modalidad', 'nivel'), e.nombre_visible");
    $s->execute($valores);
    $res = [];
    foreach ($s->fetchAll() as $f) {
        $k = $f['origen'] . ':' . $f['doc_id'];
        if (count($res[$k] ?? []) < 4) {
            $res[$k][] = $f['nombre_visible'];
        }
    }
    return $res;
}

// --------------------------------------------------------------------------- 2. Más consumidos

function seccion_mas_consumidos(PDO $db, int $dias, int $limite = 10): array
{
    $p = periodos($dias);
    $res = [];
    foreach (['ejercicios', 'articulos'] as $origen) {
        $s = $db->prepare("SELECT doc_id, SUM(tipo = 'apertura') AS aperturas, SUM(tipo = 'like') AS me_gusta,
                SUM(tipo IN ('apertura', 'like')) AS total
            FROM eventos e WHERE e.origen = ? AND e.tipo IN ('apertura', 'like') AND e.creado_en >= ? AND e.creado_en < ?
              AND " . sin_eventos_de_admin('e') . "
            GROUP BY doc_id ORDER BY total DESC, aperturas DESC, doc_id LIMIT " . max(1, min(50, $limite)));
        $s->execute([$origen, $p['desde'], $p['hasta']]);
        $filas = $s->fetchAll();
        $titulos = titulos_de($db, array_map(fn($f) => [$origen, $f['doc_id']], $filas));
        $res[$origen] = array_map(fn($f) => [
            'doc_id' => (int)$f['doc_id'], 'titulo' => $titulos["$origen:{$f['doc_id']}"] ?? "(documento {$f['doc_id']} eliminado)",
            'aperturas' => (int)$f['aperturas'], 'me_gusta' => (int)$f['me_gusta'], 'total' => (int)$f['total'],
        ], $filas);
    }
    return $res;
}

// --------------------------------------------------------------------------- 3. Menos consumidos

function seccion_menos_consumidos(PDO $db, int $dias, int $limite = 10): array
{
    $p = periodos($dias);
    // Mostrados mucho y casi nunca abiertos: tasa de apertura por impresión
    $s = $db->prepare("SELECT origen, doc_id, SUM(tipo = 'impresion') AS impresiones, SUM(tipo = 'apertura') AS aperturas
        FROM eventos e WHERE e.creado_en >= ? AND e.creado_en < ? AND " . sin_eventos_de_admin('e') . " GROUP BY origen, doc_id
        HAVING impresiones >= ? ORDER BY SUM(tipo = 'apertura') / SUM(tipo = 'impresion') ASC, impresiones DESC, origen, doc_id LIMIT " . max(1, min(50, $limite)));
    $s->execute([$p['desde'], $p['hasta'], MIN_IMPRESIONES_POCO_ABIERTO]);
    $poco = $s->fetchAll();
    $refs = array_map(fn($f) => [$f['origen'], $f['doc_id']], $poco);
    $titulos = titulos_de($db, $refs);
    $etiquetas = etiquetas_de($db, $refs);
    $pocoAbiertos = array_map(fn($f) => [
        'origen' => $f['origen'], 'doc_id' => (int)$f['doc_id'],
        'titulo' => $titulos["{$f['origen']}:{$f['doc_id']}"] ?? "(documento {$f['doc_id']} eliminado)",
        'impresiones' => (int)$f['impresiones'], 'aperturas' => (int)$f['aperturas'],
        'tasa_apertura' => round((int)$f['aperturas'] / (int)$f['impresiones'] * 100, 1),
        'etiquetas' => $etiquetas["{$f['origen']}:{$f['doc_id']}"] ?? [],
    ], $poco);

    // Nunca mostrados en TODO el histórico de eventos (no depende del período)
    $nunca = [];
    $totales = [];
    foreach (['ejercicios' => 'SELECT id, nombre_es AS titulo FROM ejercicios e', 'articulos' => 'SELECT id, titulo FROM articulos e'] as $origen => $sql) {
        $s = $db->prepare("$sql WHERE NOT EXISTS (SELECT 1 FROM eventos ev WHERE ev.origen = ? AND ev.doc_id = e.id AND " . sin_eventos_de_admin('ev') . ") ORDER BY e.id LIMIT " . max(1, min(50, $limite)));
        $s->execute([$origen]);
        foreach ($s->fetchAll() as $f) {
            $nunca[] = ['origen' => $origen, 'doc_id' => (int)$f['id'], 'titulo' => $f['titulo']];
        }
        $s = $db->prepare("SELECT COUNT(*) FROM $origen e WHERE NOT EXISTS (SELECT 1 FROM eventos ev WHERE ev.origen = ? AND ev.doc_id = e.id AND " . sin_eventos_de_admin('ev') . ")");
        $s->execute([$origen]);
        $totales[$origen] = (int)$s->fetchColumn();
    }
    $etq = etiquetas_de($db, array_map(fn($f) => [$f['origen'], $f['doc_id']], $nunca));
    foreach ($nunca as &$n) {
        $n['etiquetas'] = $etq["{$n['origen']}:{$n['doc_id']}"] ?? [];
    }
    unset($n);

    // Qué conviene revisar: las etiquetas que más se repiten entre los poco abiertos
    $cuenta = [];
    foreach ($pocoAbiertos as $d) {
        foreach ($d['etiquetas'] as $e) {
            $cuenta[$e] = ($cuenta[$e] ?? 0) + 1;
        }
    }
    arsort($cuenta);
    $revisar = [];
    foreach (array_slice($cuenta, 0, 5, true) as $e => $n) {
        if ($n >= 2) {
            $revisar[] = ['etiqueta' => $e, 'documentos' => $n];
        }
    }
    return ['poco_abiertos' => $pocoAbiertos, 'nunca_mostrados' => $nunca, 'nunca_mostrados_total' => $totales,
            'etiquetas_a_revisar' => $revisar, 'minimo_impresiones' => MIN_IMPRESIONES_POCO_ABIERTO];
}

// --------------------------------------------------------------------------- 4. Edad

/** Edad en años cumplidos a la fecha dada. */
function edad_en(string $fechaNac, DateTimeImmutable $hoy): ?int
{
    $d = DateTimeImmutable::createFromFormat('!Y-m-d', $fechaNac);
    if ($d === false || $d > $hoy) {
        return null;
    }
    return $d->diff($hoy)->y;
}

function rango_de_edad(int $edad): string
{
    foreach (RANGOS_EDAD as [$nombre, $min, $max]) {
        if ($edad >= $min && $edad <= $max) {
            return $nombre;
        }
    }
    return RANGOS_EDAD[count(RANGOS_EDAD) - 1][0];
}

/**
 * [cuenta_id => rango]. Descifra la fecha de nacimiento SOLO en memoria y la descarta de
 * inmediato: lo único que queda es el rango. Una fecha que no se pueda descifrar o leer
 * deja a esa cuenta fuera.
 */
function rangos_por_cuenta(PDO $db, ?DateTimeImmutable $hoy = null): array
{
    $hoy ??= new DateTimeImmutable('today');
    $s = $db->query("SELECT id, fecha_nac_cifrada FROM cuentas WHERE rol = 'usuario'");
    $rangos = [];
    foreach ($s->fetchAll() as $f) {
        try {
            $edad = edad_en(descifrar_campo((string)$f['fecha_nac_cifrada'], 'cuentas.fecha_nacimiento'), $hoy);
        } catch (RuntimeException) {
            $edad = null;
        }
        if ($edad !== null) {
            $rangos[(int)$f['id']] = rango_de_edad($edad);
        }
    }
    return $rangos;
}

function seccion_edad(PDO $db, int $dias, int $top = 5): array
{
    $p = periodos($dias);
    $rangoDeCuenta = rangos_por_cuenta($db);

    // Cuentas por rango: solo los rangos con al menos EDAD_MIN_CUENTAS cuentas se devuelven
    $cuentasPorRango = array_count_values($rangoDeCuenta);
    $visibles = array_filter($cuentasPorRango, fn($n) => $n >= EDAD_MIN_CUENTAS);

    // Eventos del período con su cuenta (vía perfil) -> rango, músculo o tema del documento
    $s = $db->prepare("SELECT pf.cuenta_id, ev.tipo, ev.origen, ev.doc_id FROM eventos ev
        JOIN perfiles pf ON pf.id = ev.perfil_id
        WHERE ev.tipo IN ('apertura', 'like') AND ev.creado_en >= ? AND ev.creado_en < ?");
    $s->execute([$p['desde'], $p['hasta']]);
    $eventos = $s->fetchAll();

    $musculoDe = [];
    $s = $db->query("SELECT de.doc_id, e.nombre_visible FROM documento_etiquetas de JOIN etiquetas e ON e.id = de.etiqueta_id
        WHERE de.origen = 'ejercicios' AND e.tipo = 'musculo'");
    foreach ($s->fetchAll() as $f) {
        $musculoDe[(int)$f['doc_id']] ??= $f['nombre_visible'];
    }
    $temaDe = [];
    $s = $db->query("SELECT doc_id, ruta FROM documento_rutas WHERE origen = 'articulos' AND arbol = 'temas'");
    foreach ($s->fetchAll() as $f) {
        $nodos = explode(' > ', (string)$f['ruta']);
        $temaDe[(int)$f['doc_id']] = end($nodos);
    }

    $porRango = [];
    foreach (RANGOS_EDAD as [$nombre]) {
        if (isset($visibles[$nombre])) {
            $porRango[$nombre] = ['rango' => $nombre, 'cuentas' => $visibles[$nombre], 'aperturas' => 0, 'me_gusta' => 0,
                'cuentas_activas' => [], 'musculos' => [], 'temas' => []];
        }
    }
    foreach ($eventos as $ev) {
        $rango = $rangoDeCuenta[(int)$ev['cuenta_id']] ?? null;
        if ($rango === null || !isset($porRango[$rango])) {
            continue;
        }
        $r = &$porRango[$rango];
        $r[$ev['tipo'] === 'like' ? 'me_gusta' : 'aperturas']++;
        $r['cuentas_activas'][(int)$ev['cuenta_id']] = true;
        if ($ev['origen'] === 'ejercicios' && isset($musculoDe[(int)$ev['doc_id']])) {
            $m = $musculoDe[(int)$ev['doc_id']];
            $r['musculos'][$m] = ($r['musculos'][$m] ?? 0) + 1;
        } elseif ($ev['origen'] === 'articulos' && isset($temaDe[(int)$ev['doc_id']])) {
            $t = $temaDe[(int)$ev['doc_id']];
            $r['temas'][$t] = ($r['temas'][$t] ?? 0) + 1;
        }
        unset($r);
    }
    $topN = function (array $cuenta) use ($top): array {
        uksort($cuenta, fn($a, $b) => $cuenta[$b] <=> $cuenta[$a] ?: strcmp($a, $b));
        $out = [];
        foreach (array_slice($cuenta, 0, $top, true) as $concepto => $n) {
            $out[] = ['concepto' => $concepto, 'eventos' => $n];
        }
        return $out;
    };
    $rangos = [];
    foreach ($porRango as $r) {
        $rangos[] = ['rango' => $r['rango'], 'cuentas' => $r['cuentas'], 'cuentas_activas' => count($r['cuentas_activas']),
            'aperturas' => $r['aperturas'], 'me_gusta' => $r['me_gusta'],
            'musculos' => $topN($r['musculos']), 'temas' => $topN($r['temas'])];
    }
    return ['rangos' => $rangos, 'minimo_cuentas' => EDAD_MIN_CUENTAS,
            'cuentas_sin_rango_visible' => array_sum($cuentasPorRango) - array_sum($visibles)];
}

// --------------------------------------------------------------------------- 5. Búsquedas

function seccion_busquedas(PDO $db, int $dias, int $limite = 15): array
{
    $p = periodos($dias);
    $lim = max(1, min(50, $limite));
    // Raíces: cada fila de consultas tiene varias separadas por espacio; se cuentan en PHP
    $s = $db->prepare('SELECT raices, n_resultados FROM consultas WHERE creado_en >= ? AND creado_en < ?');
    $s->execute([$p['desde'], $p['hasta']]);
    $filas = $s->fetchAll();
    $cuenta = [];
    foreach ($filas as $f) {
        foreach (array_unique(explode(' ', $f['raices'])) as $r) {
            if ($r !== '') {
                $cuenta[$r] = ($cuenta[$r] ?? 0) + 1;
            }
        }
    }
    uksort($cuenta, fn($a, $b) => $cuenta[$b] <=> $cuenta[$a] ?: strcmp($a, $b));
    $raices = [];
    foreach (array_slice($cuenta, 0, $lim, true) as $r => $n) {
        $raices[] = ['raiz' => $r, 'busquedas' => $n];
    }

    // Consultas que no encontraron relación: via 'ninguno' o 'sin_interseccion'
    $s = $db->prepare("SELECT raices, via, COUNT(*) AS n, SUM(n_resultados = 0) AS sin_resultados
        FROM consultas WHERE creado_en >= ? AND creado_en < ? AND via IN ('ninguno', 'sin_interseccion')
        GROUP BY raices, via ORDER BY n DESC, raices LIMIT $lim");
    $s->execute([$p['desde'], $p['hasta']]);
    $faltantes = array_map(fn($f) => ['raices' => $f['raices'], 'via' => $f['via'], 'busquedas' => (int)$f['n'],
        'sin_resultados' => (int)$f['sin_resultados']], $s->fetchAll());

    $s = $db->prepare("SELECT via, COUNT(*) AS n FROM consultas WHERE creado_en >= ? AND creado_en < ? GROUP BY via ORDER BY n DESC");
    $s->execute([$p['desde'], $p['hasta']]);
    $porVia = array_map(fn($f) => ['via' => $f['via'] ?? 'sin descubrimiento', 'busquedas' => (int)$f['n']], $s->fetchAll());

    return ['total' => count($filas), 'sin_resultados' => count(array_filter($filas, fn($f) => (int)$f['n_resultados'] === 0)),
            'raices' => $raices, 'contenido_faltante' => $faltantes, 'por_via' => $porVia];
}

// --------------------------------------------------------------------------- 6. Cobertura

function seccion_cobertura(PDO $db, int $dias): array
{
    $p = periodos($dias);
    // Músculos: documentos por etiqueta de músculo e interacción de esos documentos en el período
    $s = $db->prepare("SELECT e.nombre_visible AS concepto, COUNT(DISTINCT de.origen, de.doc_id) AS documentos,
            COALESCE(SUM(ev.n), 0) AS interacciones
        FROM etiquetas e JOIN documento_etiquetas de ON de.etiqueta_id = e.id
        LEFT JOIN (SELECT x.origen, x.doc_id, COUNT(*) AS n FROM eventos x
                   WHERE x.tipo IN ('apertura', 'like') AND x.creado_en >= ? AND x.creado_en < ? AND " . sin_eventos_de_admin('x') . "
                   GROUP BY x.origen, x.doc_id) ev
               ON ev.origen = de.origen AND ev.doc_id = de.doc_id
        WHERE e.tipo = 'musculo' GROUP BY e.id, e.nombre_visible ORDER BY documentos ASC, interacciones ASC, concepto");
    $s->execute([$p['desde'], $p['hasta']]);
    $musculos = array_map(fn($f) => ['concepto' => $f['concepto'], 'documentos' => (int)$f['documentos'], 'interacciones' => (int)$f['interacciones']], $s->fetchAll());

    // Temas: por el nodo del árbol de Temas (documento_rutas), no por etiqueta libre
    $s = $db->prepare("SELECT SUBSTRING_INDEX(r.ruta, ' > ', -1) AS concepto, COUNT(*) AS documentos, COALESCE(SUM(ev.n), 0) AS interacciones
        FROM documento_rutas r
        LEFT JOIN (SELECT x.origen, x.doc_id, COUNT(*) AS n FROM eventos x
                   WHERE x.tipo IN ('apertura', 'like') AND x.creado_en >= ? AND x.creado_en < ? AND " . sin_eventos_de_admin('x') . "
                   GROUP BY x.origen, x.doc_id) ev
               ON ev.origen = r.origen AND ev.doc_id = r.doc_id
        WHERE r.origen = 'articulos' AND r.arbol = 'temas' GROUP BY concepto ORDER BY documentos ASC, interacciones ASC, concepto");
    $s->execute([$p['desde'], $p['hasta']]);
    $temas = array_map(fn($f) => ['concepto' => $f['concepto'], 'documentos' => (int)$f['documentos'], 'interacciones' => (int)$f['interacciones']], $s->fetchAll());

    $mediana = function (array $lista, string $clave): float {
        $v = array_column($lista, $clave);
        sort($v);
        $n = count($v);
        return $n === 0 ? 0 : ($n % 2 ? (float)$v[intdiv($n, 2)] : ($v[$n / 2 - 1] + $v[$n / 2]) / 2);
    };
    $marcar = function (array $lista) use ($mediana): array {
        $medDocs = $mediana($lista, 'documentos');
        // Si la mayoría no tiene ninguna interacción la mediana es 0 y "menos de la mitad" no
        // marcaría nada: por eso el umbral mínimo es 1 (quien no tiene ninguna siempre se marca).
        $umbralInteraccion = max(1.0, $mediana($lista, 'interacciones') / 2);
        foreach ($lista as &$x) {
            $x['pocos_documentos'] = $x['documentos'] < $medDocs / 2;
            $x['poca_interaccion'] = $x['interacciones'] < $umbralInteraccion;
        }
        return $lista;
    };
    return ['musculos' => $marcar($musculos), 'temas' => $marcar($temas)];
}
