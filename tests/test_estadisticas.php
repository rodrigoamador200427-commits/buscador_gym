<?php
// tests/test_estadisticas.php — pruebas HTTP del registro de eventos y consultas (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php
//
// Usa el mismo arnés que test_autorizacion.php: solo gym_buscador_test, recreada con
// contenido sintético, y un servidor php -S propio. Comprueba que:
// - un evento queda ligado al perfil de la sesión y no a uno enviado en el cuerpo;
// - borrar el perfil deja sus eventos con perfil_id NULL;
// - consultas no guarda el texto original ni el perfil, y las impresiones no llevan perfil;
// - un fallo del registro no rompe la búsqueda;
// - la purga borra solo lo de más de 180 días.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

/** Consulta directa a la BD de pruebas (el arnés ya garantizó que es *_test). */
function filas(string $sql, array $p = []): array
{
    $s = conexion()->prepare($sql);
    $s->execute($p);
    return $s->fetchAll();
}
function valor(string $sql, array $p = []): mixed
{
    return filas($sql, $p)[0][array_key_first(filas($sql, $p)[0])] ?? null;
}
function contar(string $tabla, string $where = '1', array $p = []): int
{
    return (int)valor("SELECT COUNT(*) AS n FROM $tabla WHERE $where", $p);   // $tabla fijo en este archivo
}

/**
 * buscar.php registra DESPUÉS de enviar la respuesta, así que el cliente puede leer la BD
 * antes de que termine el registro. php -S atiende una petición a la vez: cuando esta
 * otra petición vuelve, la anterior ya terminó por completo.
 */
function buscar(Cliente $c, string $q): array
{
    $r = $c->pedir('buscar.php?q=' . rawurlencode($q));
    $cabeceras = $c->cabeceras;
    $c->pedir('sesion.php');
    $c->cabeceras = $cabeceras;
    return $r;
}

echo "BD: $conectada  |  servidor: $BASE\n";

$A = new Cliente($BASE);
$B = new Cliente($BASE);
$anon = new Cliente($BASE);
$A->pedir('registro.php', ['correo' => 'a@prueba.test', 'contrasena' => 'CuentaA12345',
                           'nombre_completo' => 'Cuenta A', 'fecha_nacimiento' => '2000-01-01']);
$B->pedir('registro.php', ['correo' => 'b@prueba.test', 'contrasena' => 'CuentaB12345',
                           'nombre_completo' => 'Cuenta B', 'fecha_nacimiento' => '2000-01-01']);
$pechoA = crearPerfil($A, 'Pecho');
$piernaA = crearPerfil($A, 'Pierna');
$mioB = crearPerfil($B, 'Mio');

// ----------------------------------------------------------------------------- apertura
echo "\n[registrar_evento.php: apertura]\n";
[$cod] = $A->pedir('registrar_evento.php', ['doc_id' => 101, 'origen' => 'ejercicios']);
comprobar('sin perfil elegido -> 409', $cod === 409, "obtuvo $cod");
comprobar('sin sesión -> 401', $anon->pedir('registrar_evento.php', ['doc_id' => 101, 'origen' => 'ejercicios'])[0] === 401);

$A->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
[$cod, $r] = $A->pedir('registrar_evento.php',
    ['doc_id' => 101, 'origen' => 'ejercicios', 'perfil_id' => $mioB, 'tipo' => 'like']);
$ev = filas("SELECT perfil_id, tipo FROM eventos WHERE doc_id = 101 AND origen = 'ejercicios'");
comprobar('apertura -> 200', $cod === 200 && ($r['status'] ?? '') === 'ok', "obtuvo $cod");
comprobar('el evento va al perfil de la sesión, no al perfil_id del cuerpo',
    count($ev) === 1 && (int)$ev[0]['perfil_id'] === $pechoA, json_encode($ev));
comprobar('el tipo del cuerpo se ignora: siempre es apertura', ($ev[0]['tipo'] ?? '') === 'apertura', json_encode($ev));
[$cod] = $A->pedir('registrar_evento.php', ['doc_id' => '301', 'origen' => 'articulos']);
comprobar('doc_id como cadena de dígitos -> 200', $cod === 200, "obtuvo $cod");

$antes = contar('eventos');
$invalidos = [
    'origen fuera de la lista blanca -> 422' => [['doc_id' => 101, 'origen' => 'alimentos'], 422],
    'doc_id "1 OR 1=1" -> 422'               => [['doc_id' => '1 OR 1=1', 'origen' => 'ejercicios'], 422],
    'doc_id negativo -> 422'                 => [['doc_id' => -1, 'origen' => 'ejercicios'], 422],
    'doc_id decimal -> 422'                  => [['doc_id' => 1.5, 'origen' => 'ejercicios'], 422],
    'doc_id enorme -> 422'                   => [['doc_id' => '99999999999999999999', 'origen' => 'ejercicios'], 422],
    'sin doc_id -> 422'                      => [['origen' => 'ejercicios'], 422],
    'documento inexistente -> 404'           => [['doc_id' => 999999, 'origen' => 'ejercicios'], 404],
];
foreach ($invalidos as $nombre => [$cuerpo, $esperado]) {
    [$cod] = $A->pedir('registrar_evento.php', $cuerpo);
    comprobar($nombre, $cod === $esperado, "obtuvo $cod");
}
[$cod] = $A->pedirCrudo('registrar_evento.php', 'doc_id=101&origen=ejercicios', 'application/x-www-form-urlencoded');
comprobar('formulario (no JSON) -> 415', $cod === 415, "obtuvo $cod");
[$cod] = $A->pedir('registrar_evento.php');
comprobar('GET -> 405', $cod === 405, "obtuvo $cod");
comprobar('ninguna petición rechazada creó eventos', contar('eventos') === $antes);

// ----------------------------------------------------------------------------- like
echo "\n[registrar_interaccion.php: evento like]\n";
$B->pedir('seleccionar_perfil.php', ['perfil_id' => $mioB]);
[, $r] = $B->pedir('registrar_interaccion.php', ['doc_id' => 103, 'origen' => 'ejercicios', 'perfil_id' => $pechoA]);
$ev = filas("SELECT perfil_id FROM eventos WHERE tipo = 'like' AND doc_id = 103");
comprobar('like -> evento like del perfil de la sesión (B), no del perfil_id del cuerpo (A)',
    ($r['status'] ?? '') === 'added' && array_map(fn($f) => (int)$f['perfil_id'], $ev) === [$mioB], json_encode($ev));
[, $r] = $B->pedir('registrar_interaccion.php', ['doc_id' => 103, 'origen' => 'ejercicios']);
comprobar('quitar el like no crea evento', ($r['status'] ?? '') === 'removed'
    && contar('eventos', "tipo = 'like' AND doc_id = 103") === 1);
$B->pedir('registrar_interaccion.php', ['doc_id' => 103, 'origen' => 'ejercicios']);
comprobar('volver a darlo crea otro evento', contar('eventos', "tipo = 'like' AND doc_id = 103") === 2);
$A->pedir('registrar_interaccion.php', ['doc_id' => 102, 'origen' => 'ejercicios']);   // para el borrado de perfil

// ----------------------------------------------------------------------------- búsqueda
echo "\n[buscar.php: consultas e impresiones]\n";
$textoOriginal = 'Press  BANCA, press plano!';
$consultasAntes = contar('consultas');
$impAntes = contar('eventos', "tipo = 'impresion'");
[$cod, $bus] = buscar($A, $textoOriginal);
$n = count($bus['resultados'] ?? []);
comprobar('la búsqueda responde 200 con resultados', $cod === 200 && $n > 0, "obtuvo $cod, $n resultados");
comprobar('la respuesta lleva Content-Length (el registro va después)',
    isset($A->cabeceras['content-length']), json_encode($A->cabeceras));

$c = filas('SELECT * FROM consultas ORDER BY id DESC LIMIT 1')[0] ?? [];
comprobar('una sola fila nueva en consultas', contar('consultas') === $consultasAntes + 1);
comprobar('consultas solo tiene id, raices, via, n_resultados, creado_en (sin perfil ni texto)',
    array_keys($c) === ['id', 'raices', 'via', 'n_resultados', 'creado_en'], json_encode(array_keys($c)));
$todo = mb_strtolower(implode(' ', array_map('strval', $c)), 'UTF-8');
comprobar('el texto original no aparece en consultas',
    !str_contains($todo, 'banca') && !str_contains($todo, 'plano') && !str_contains($todo, 'press  ')
    && !str_contains($todo, mb_strtolower($textoOriginal, 'UTF-8')), json_encode($c));
$tok = explode(' ', (string)($c['raices'] ?? ''));
$ordenado = $tok;
sort($ordenado, SORT_STRING);
comprobar('raíces sin repetir y en orden alfabético', $tok === $ordenado && $tok === array_values(array_unique($tok))
    && in_array('press', $tok, true) && in_array('banc', $tok, true), json_encode($c['raices'] ?? null));
comprobar('raíces sin la expansión por árboles', !in_array('planif', $tok, true), json_encode($c['raices'] ?? null));
comprobar('n_resultados = resultados devueltos', (int)($c['n_resultados'] ?? -1) === $n, json_encode($c));
comprobar('via = vía del descubrimiento', ($c['via'] ?? null) === ($bus['descubrimiento']['via'] ?? null), json_encode($c));

$mostrados = array_map(fn($d) => $d['origen'] . ':' . $d['doc_id'], $bus['resultados']);
if (isset($bus['descubrimiento']['doc_id'])) {
    $mostrados[] = 'articulos:' . $bus['descubrimiento']['doc_id'];
}
$imp = filas("SELECT perfil_id, origen, doc_id FROM eventos WHERE tipo = 'impresion' ORDER BY id DESC LIMIT " . count($mostrados));
$impDocs = array_map(fn($f) => $f['origen'] . ':' . $f['doc_id'], $imp);
sort($impDocs);
sort($mostrados);
comprobar('una impresión por documento mostrado', contar('eventos', "tipo = 'impresion'") === $impAntes + count($mostrados)
    && $impDocs === $mostrados, json_encode([$impDocs, $mostrados]));
comprobar('las impresiones no llevan perfil', !array_filter($imp, fn($f) => $f['perfil_id'] !== null), json_encode($imp));

$impAntes = contar('eventos', "tipo = 'impresion'");
[$cod, $bus] = buscar($A, 'xyzzyqw');
$c = filas('SELECT raices, n_resultados FROM consultas ORDER BY id DESC LIMIT 1')[0] ?? [];
comprobar('búsqueda fallida: se registra con n_resultados = 0',
    $cod === 200 && ($c['raices'] ?? '') === 'xyzzyqw' && (int)$c['n_resultados'] === 0, json_encode($c));
comprobar('búsqueda fallida: sin impresiones', contar('eventos', "tipo = 'impresion'") === $impAntes);
$antes = contar('consultas');
buscar($A, '');
comprobar('búsqueda vacía: no se registra', contar('consultas') === $antes);

// ----------------------------------------------------------------------------- borrado de perfil
echo "\n[Borrar el perfil conserva sus eventos sin perfil]\n";
$delPerfil = contar('eventos', 'perfil_id = ?', [$pechoA]);
$totalEventos = contar('eventos');
comprobar("control: el perfil $pechoA tiene eventos", $delPerfil >= 3, "tiene $delPerfil");
[$cod] = $A->pedir('perfiles.php', ['accion' => 'eliminar', 'perfil_id' => $pechoA]);
comprobar('eliminar el perfil -> 200', $cod === 200, "obtuvo $cod");
comprobar('ya no queda ningún evento con ese perfil_id', contar('eventos', 'perfil_id = ?', [$pechoA]) === 0);
comprobar('no se borró ningún evento (quedan con perfil_id NULL)', contar('eventos') === $totalEventos);
comprobar('los eventos de otros perfiles no cambiaron', contar('eventos', 'perfil_id = ?', [$mioB]) === 2);
comprobar('control: el historial de likes sí se borró en cascada', contar('interacciones', 'perfil_id = ?', [$pechoA]) === 0);

// ----------------------------------------------------------------------------- purga
echo "\n[Purga de más de 180 días]\n";
$db = conexion();
$db->exec("INSERT INTO consultas (raices, via, n_resultados, creado_en) VALUES
    ('vieja', NULL, 0, NOW() - INTERVAL 181 DAY), ('reciente', NULL, 0, NOW() - INTERVAL 179 DAY)");
$db->exec("INSERT INTO eventos (perfil_id, tipo, origen, doc_id, creado_en) VALUES
    (NULL, 'impresion', 'ejercicios', 900001, NOW() - INTERVAL 181 DAY),
    (NULL, 'impresion', 'ejercicios', 900002, NOW() - INTERVAL 179 DAY)");   // ids inexistentes: marcadores
$consultasAntes = contar('consultas');
$eventosAntes = contar('eventos');
[$cod] = $anon->pedir('herramientas/purgar_estadisticas.php');
comprobar('la purga no se puede lanzar por HTTP -> 404', $cod === 404 && contar('consultas') === $consultasAntes, "obtuvo $cod");
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg("$RAIZ/herramientas/purgar_estadisticas.php"), $salida, $codigo);
comprobar('purgar_estadisticas.php termina bien', $codigo === 0, implode(' | ', $salida));
comprobar('borra la consulta de 181 días y deja la de 179',
    contar('consultas', "raices = 'vieja'") === 0 && contar('consultas', "raices = 'reciente'") === 1
    && contar('consultas') === $consultasAntes - 1);
comprobar('borra el evento de 181 días y deja el de 179',
    contar('eventos', 'doc_id = 900001') === 0 && contar('eventos', 'doc_id = 900002') === 1
    && contar('eventos') === $eventosAntes - 1);

// ----------------------------------------------------------------------------- fallos del registro
echo "\n[Un fallo del registro no rompe la búsqueda]\n";
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $piernaA]);
$db->exec('DROP TABLE consultas');
$impAntes = contar('eventos', "tipo = 'impresion'");
[$cod, $bus] = buscar($A, 'sentadilla');
comprobar('sin la tabla consultas, la búsqueda responde 200 con resultados',
    $cod === 200 && ($bus['status'] ?? '') === 'success' && count($bus['resultados'] ?? []) > 0, json_encode([$cod, $bus['status'] ?? null]));
comprobar('las impresiones se registran aunque falle consultas', contar('eventos', "tipo = 'impresion'") > $impAntes);

$db->exec('DROP TABLE eventos');
[$cod, $bus] = buscar($A, 'sentadilla');
comprobar('sin consultas ni eventos, la búsqueda responde 200 con resultados',
    $cod === 200 && ($bus['status'] ?? '') === 'success' && count($bus['resultados'] ?? []) > 0, json_encode([$cod, $bus['status'] ?? null]));
[$cod, $r] = $A->pedir('registrar_interaccion.php', ['doc_id' => 201, 'origen' => 'ejercicios']);
comprobar('sin la tabla eventos, el like se guarda igual',
    $cod === 200 && ($r['status'] ?? '') === 'added' && contar('interacciones', 'perfil_id = ? AND doc_id = 201', [$piernaA]) === 1,
    json_encode([$cod, $r]));
[$cod, $r] = $A->pedir('registrar_evento.php', ['doc_id' => 201, 'origen' => 'ejercicios']);
comprobar('registrar_evento.php falla con 500 sin filtrar el error de SQL',
    $cod === 500 && array_keys($r) === ['status', 'mensaje', 'ref'] && $r['mensaje'] === 'Error interno', json_encode([$cod, $r]));

// Dejar la BD de pruebas completa otra vez (el archivo no tiene DELIMITER)
$sql = preg_replace('/^\s*--.*$/m', '', file_get_contents("$RAIZ/sql/esquema_estadisticas.sql"));
foreach (array_filter(array_map('trim', explode(';', $sql))) as $sentencia) {
    $db->exec($sentencia);
}
comprobar('esquema de estadísticas restaurado', contar('eventos') === 0 && contar('consultas') === 0);

terminar();
