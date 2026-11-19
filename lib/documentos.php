<?php
// lib/documentos.php — orígenes válidos e hidratación de documentos (contenido público).
declare(strict_types=1);

const ORIGENES_VALIDOS = ['ejercicios', 'articulos'];
const TIPO_DOCUMENTO = ['ejercicios' => 'Ejercicio', 'articulos' => 'Artículo'];
const LARGO_RESUMEN = 280;      // la tarjeta muestra 3 líneas; el texto completo va en detalle.php

/**
 * Recibe [['doc_id'=>..,'origen'=>..], ...] y devuelve ['origen:id' => tarjeta]:
 *   doc_id, origen, tipo, titulo, resumen (o texto si $textoCompleto),
 *   meta {musculo, equipamiento, nivel} (nombres visibles o null), etiquetas [{id, nombre, tipo}]
 *   y lo que decide su ilustración (assets/ilustraciones.js): grupo_id en los ejercicios y
 *   tema (el del árbol de Temas) en los artículos; el otro va en null.
 * Una consulta preparada por origen, una para las etiquetas de todos y una para los temas.
 * Todo es contenido público; el escape lo hace quien lo muestra.
 */
function hidratar_documentos(PDO $db, array $refs, bool $textoCompleto = false): array
{
    $ids = ['ejercicios' => [], 'articulos' => []];
    foreach ($refs as $r) {
        if (in_array($r['origen'] ?? '', ORIGENES_VALIDOS, true)) {
            $ids[$r['origen']][] = (int)$r['doc_id'];
        }
    }
    $consultas = [
        'ejercicios' => 'SELECT id, nombre_es AS titulo, descripcion_es AS texto, grupo_id FROM ejercicios WHERE id IN (%s)',
        'articulos'  => 'SELECT id, titulo, contenido AS texto, NULL AS grupo_id FROM articulos WHERE id IN (%s)',
    ];

    $tarjetas = [];
    foreach ($consultas as $origen => $sql) {
        if (!$ids[$origen]) {
            continue;
        }
        $s = $db->prepare(sprintf($sql, implode(',', array_fill(0, count($ids[$origen]), '?'))));
        $s->execute($ids[$origen]);
        foreach ($s->fetchAll() as $f) {
            $texto = trim((string)$f['texto']);
            $tarjetas["$origen:{$f['id']}"] = [
                'doc_id' => (int)$f['id'], 'origen' => $origen, 'tipo' => TIPO_DOCUMENTO[$origen],
                'titulo' => (string)$f['titulo'],
            ] + ($textoCompleto ? ['texto' => $texto] : ['resumen' => resumir($texto)]) + [
                'meta' => ['musculo' => null, 'equipamiento' => null, 'nivel' => null],
                'etiquetas' => [],
                'grupo_id' => $f['grupo_id'] !== null ? (int)$f['grupo_id'] : null,
                'tema' => null,
            ];
        }
    }

    // Tema de cada artículo: el último nodo de su ruta en el árbol de Temas
    if ($ids['articulos']) {
        $s = $db->prepare("SELECT doc_id, ruta FROM documento_rutas WHERE origen = 'articulos' AND arbol = 'temas' AND doc_id IN ("
            . implode(',', array_fill(0, count($ids['articulos']), '?')) . ')');
        $s->execute($ids['articulos']);
        foreach ($s->fetchAll() as $f) {
            $nodos = explode(' > ', (string)$f['ruta']);
            if (isset($tarjetas["articulos:{$f['doc_id']}"])) {
                $tarjetas["articulos:{$f['doc_id']}"]['tema'] = end($nodos);
            }
        }
    }

    foreach (etiquetas_de_documentos($db, array_keys($tarjetas)) as $clave => $lista) {
        $tarjetas[$clave]['etiquetas'] = $lista;
        foreach (['musculo', 'equipamiento', 'nivel'] as $tipo) {
            $nombres = array_column(array_filter($lista, fn($e) => $e['tipo'] === $tipo), 'nombre');
            $tarjetas[$clave]['meta'][$tipo] = $nombres ? implode(', ', array_slice($nombres, 0, 2)) : null;
        }
    }
    return $tarjetas;
}

/** Recorta en una palabra completa, sin pasar de LARGO_RESUMEN caracteres. */
function resumir(string $texto): string
{
    $texto = preg_replace('/\s+/u', ' ', $texto) ?? $texto;
    if (mb_strlen($texto, 'UTF-8') <= LARGO_RESUMEN) {
        return $texto;
    }
    $corte = mb_substr($texto, 0, LARGO_RESUMEN, 'UTF-8');
    $espacio = mb_strrpos($corte, ' ', 0, 'UTF-8');
    return rtrim($espacio > 0 ? mb_substr($corte, 0, $espacio, 'UTF-8') : $corte, " ,.;:") . '…';
}

/**
 * ['origen:id' => [{id, nombre, tipo}, ...]] para las claves dadas, ordenadas por tipo
 * (músculo, equipamiento, nivel, modalidad, tema) y luego por nombre.
 */
function etiquetas_de_documentos(PDO $db, array $claves): array
{
    $pares = [];
    $valores = [];
    foreach ($claves as $c) {
        [$origen, $id] = explode(':', $c, 2);
        if (in_array($origen, ORIGENES_VALIDOS, true)) {
            $pares[] = '(?, ?)';
            array_push($valores, $origen, (int)$id);
        }
    }
    if (!$pares) {
        return [];
    }
    $s = $db->prepare('SELECT de.origen, de.doc_id, e.id, e.nombre_visible, e.tipo
        FROM documento_etiquetas de JOIN etiquetas e ON e.id = de.etiqueta_id
        WHERE (de.origen, de.doc_id) IN (' . implode(',', $pares) . ")
        ORDER BY FIELD(e.tipo, 'musculo', 'equipamiento', 'nivel', 'modalidad', 'tema'), e.nombre_visible, e.id");
    $s->execute($valores);
    $res = [];
    foreach ($s->fetchAll() as $f) {
        $res[$f['origen'] . ':' . $f['doc_id']][] =
            ['id' => (int)$f['id'], 'nombre' => $f['nombre_visible'], 'tipo' => $f['tipo']];
    }
    return $res;
}

/**
 * Hasta $limite documentos que comparten más etiquetas con el dado. Cada etiqueta en común
 * suma (peso del tipo) / ln(1 + documentos con esa etiqueta):
 * - las etiquetas raras pesan más: compartir "Romboides" dice más que compartir "Intermedio";
 * - el tipo importa: mismo músculo (3) > mismo tema (2) > equipamiento (1.5) > modalidad (1)
 *   > nivel (0.5). Sin esto, "sentadilla con barra" salía antes que "aperturas de pecho"
 *   como relacionado del press de banca, solo por compartir la barra.
 * Devuelve [{doc_id, origen, comparte: [nombres]}].
 */
function documentos_relacionados(PDO $db, string $origen, int $docId, int $limite = 4): array
{
    $s = $db->prepare("SELECT o.origen, o.doc_id,
               SUM(CASE e.tipo WHEN 'musculo' THEN 3 WHEN 'tema' THEN 2 WHEN 'equipamiento' THEN 1.5
                               WHEN 'modalidad' THEN 1 ELSE 0.5 END / LN(1 + c.n)) AS peso,
               GROUP_CONCAT(e.nombre_visible
                   ORDER BY FIELD(e.tipo, 'musculo', 'tema', 'equipamiento', 'modalidad', 'nivel'), c.n, e.nombre_visible
                   SEPARATOR '\n') AS comparte
        FROM documento_etiquetas mi
        JOIN (SELECT etiqueta_id, COUNT(*) AS n FROM documento_etiquetas GROUP BY etiqueta_id) c
             ON c.etiqueta_id = mi.etiqueta_id
        JOIN documento_etiquetas o
             ON o.etiqueta_id = mi.etiqueta_id AND NOT (o.origen = mi.origen AND o.doc_id = mi.doc_id)
        JOIN etiquetas e ON e.id = mi.etiqueta_id
        WHERE mi.origen = ? AND mi.doc_id = ?
        GROUP BY o.origen, o.doc_id
        ORDER BY peso DESC, o.origen, o.doc_id
        LIMIT " . max(1, min(10, $limite)));
    $s->execute([$origen, $docId]);
    return array_map(fn($f) => [
        'doc_id' => (int)$f['doc_id'], 'origen' => $f['origen'],
        'comparte' => array_slice(explode("\n", (string)$f['comparte']), 0, 3),
    ], $s->fetchAll());
}

// ORDEN_ARBOLES: los que admite la tabla documento_rutas; ARBOLES_ACTIVOS: los que el motor construye hoy.
const ORDEN_ARBOLES = ['anatomia', 'temas', 'equipamiento', 'nivel', 'patron'];
const ARBOLES_ACTIVOS = ['anatomia', 'temas', 'equipamiento', 'nivel', 'patron'];
// Árboles cuya clasificación es una aproximación (el patrón se infiere de palabras del nombre): la interfaz lo avisa.
const ARBOLES_APROXIMADOS = ['patron'];
const TITULO_ARBOL = ['anatomia' => 'Anatomía', 'temas' => 'Temas', 'equipamiento' => 'Equipamiento',
                      'nivel' => 'Nivel', 'patron' => 'Patrón de movimiento'];

/** Todas las rutas del documento, una por árbol: [{arbol, titulo, nodos: [...]}] en el orden fijo de los árboles. */
function rutas_documento(PDO $db, string $origen, int $docId): array
{
    $s = $db->prepare("SELECT arbol, ruta FROM documento_rutas WHERE origen = ? AND doc_id = ?
        ORDER BY FIELD(arbol, 'anatomia', 'temas', 'equipamiento', 'nivel', 'patron')");
    $s->execute([$origen, $docId]);
    return array_map(fn($f) => ['arbol' => $f['arbol'], 'titulo' => TITULO_ARBOL[$f['arbol']] ?? $f['arbol'],
                                'aproximado' => in_array($f['arbol'], ARBOLES_APROXIMADOS, true),
                                'nodos' => explode(' > ', (string)$f['ruta'])], $s->fetchAll());
}

/**
 * Nodos que el motor reconoció (uno por árbol que participa) listos para la tarjeta:
 * [{arbol, titulo, nombre, ruta: [...]}]. Lo que viene de Python se filtra: árbol de la lista
 * blanca, solo cadenas y largos acotados; lo que no encaja se descarta.
 */
function nodos_de_descubrimiento($nodos): array
{
    $res = [];
    foreach (is_array($nodos) ? array_slice($nodos, 0, 6) : [] as $n) {
        if (!is_array($n) || !in_array($n['arbol'] ?? '', ORDEN_ARBOLES, true)
            || !is_string($n['nombre'] ?? null) || !is_array($n['ruta'] ?? null)) {
            continue;
        }
        $ruta = array_values(array_map(fn($x) => mb_substr($x, 0, 120, 'UTF-8'), array_filter($n['ruta'], 'is_string')));
        $res[] = ['arbol' => $n['arbol'], 'titulo' => TITULO_ARBOL[$n['arbol']], 'nombre' => mb_substr($n['nombre'], 0, 120, 'UTF-8'),
                  'aproximado' => in_array($n['arbol'], ARBOLES_APROXIMADOS, true),
                  'ruta' => array_slice($ruta, 0, 6)];
    }
    return $res;
}

/** Ruta principal del documento (la de anatomía en un ejercicio, la de temas en un artículo): {arbol, nodos} o null. */
function ruta_documento(PDO $db, string $origen, int $docId): ?array
{
    $r = rutas_documento($db, $origen, $docId)[0] ?? null;
    return $r ? ['arbol' => $r['arbol'], 'nodos' => $r['nodos']] : null;
}

/**
 * Lee {doc_id, origen} de una petición. origen contra la lista blanca y doc_id entero
 * positivo (int o cadena de dígitos); si no, 422. No comprueba que el documento exista.
 * @return array{0:int,1:string} [doc_id, origen]
 */
function leer_ref_documento(array $datos): array
{
    $origen = $datos['origen'] ?? '';
    $docId = $datos['doc_id'] ?? null;
    if (!in_array($origen, ORIGENES_VALIDOS, true)              // lista blanca: cierra la inyección de segundo orden
        || !(is_int($docId) || (is_string($docId) && ctype_digit($docId) && strlen($docId) <= 10))
        || (int)$docId <= 0 || (int)$docId > 2147483647) {
        responder_error(422, 'doc_id u origen inválido');
    }
    return [(int)$docId, $origen];
}

/** Conjunto 'origen:id' de los likes del perfil (solo de ese perfil). */
function likes_del_perfil(PDO $db, int $perfilId): array
{
    $s = $db->prepare("SELECT origen, doc_id FROM interacciones WHERE perfil_id = ? AND interaccion = 'like'");
    $s->execute([$perfilId]);
    $likes = [];
    foreach ($s->fetchAll() as $f) {
        $likes[$f['origen'] . ':' . $f['doc_id']] = true;
    }
    return $likes;
}
