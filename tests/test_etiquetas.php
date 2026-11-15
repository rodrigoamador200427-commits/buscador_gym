<?php
// tests/test_etiquetas.php — pruebas HTTP de etiquetas, detalle de tarjeta y gráfica (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_etiquetas.php
//
// Mismo arnés que las otras pruebas: solo gym_buscador_test (contenido sintético con sus
// etiquetas y rutas ya generadas) y un servidor php -S propio.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

echo "BD: $conectada  |  servidor: $BASE\n";

$A = new Cliente($BASE);
$B = new Cliente($BASE);
$anon = new Cliente($BASE);
$A->pedir('registro.php', ['correo' => 'a@prueba.test', 'contrasena' => 'CuentaA12345',
                           'nombre_completo' => 'Cuenta A', 'fecha_nacimiento' => '2000-01-01']);
$B->pedir('registro.php', ['correo' => 'b@prueba.test', 'contrasena' => 'CuentaB12345',
                           'nombre_completo' => 'Cuenta B', 'fecha_nacimiento' => '2000-01-01']);
$pechoA = crearPerfil($A, 'Pecho');
$vacioA = crearPerfil($A, 'Vacio');
$mioB = crearPerfil($B, 'Mio');

$nombres = fn(array $etiquetas) => array_column($etiquetas, 'nombre');

// ----------------------------------------------------------------------------- etiquetas.php
echo "\n[etiquetas.php: catálogo con conteo]\n";
[$cod, $r] = $anon->pedir('etiquetas.php');
$porNombre = array_column($r['etiquetas'] ?? [], null, 'nombre');
comprobar('GET etiquetas.php -> 200', $cod === 200 && ($r['status'] ?? '') === 'success', "obtuvo $cod");
comprobar('cada etiqueta trae id, nombre, tipo y n',
    $r['etiquetas'] && !array_filter($r['etiquetas'], fn($e) => array_keys($e) !== ['id', 'nombre', 'tipo', 'n']),
    json_encode($r['etiquetas'][0] ?? null));
comprobar('conteos: Pecho 6 (5 ejercicios + artículo 301), Fuerza 12, Intermedio 2',
    ($porNombre['Pecho']['n'] ?? 0) === 6 && ($porNombre['Fuerza']['n'] ?? 0) === 12 && ($porNombre['Intermedio']['n'] ?? 0) === 2,
    json_encode(array_map(fn($e) => $e['n'], $porNombre)));
comprobar('tipos: Pecho músculo, Barra equipamiento, Intermedio nivel, Fuerza modalidad, Pierna tema',
    ($porNombre['Pecho']['tipo'] ?? '') === 'musculo' && ($porNombre['Barra']['tipo'] ?? '') === 'equipamiento'
    && ($porNombre['Intermedio']['tipo'] ?? '') === 'nivel' && ($porNombre['Fuerza']['tipo'] ?? '') === 'modalidad'
    && ($porNombre['Pierna']['tipo'] ?? '') === 'tema');
comprobar('nombres visibles con acento (Cuádriceps, Máquina)', isset($porNombre['Cuádriceps'], $porNombre['Máquina']));
[$cod, $r] = $anon->pedir('etiquetas.php?tipo=nivel');
comprobar('?tipo=nivel devuelve solo niveles',
    $cod === 200 && $r['etiquetas'] && !array_filter($r['etiquetas'], fn($e) => $e['tipo'] !== 'nivel'), json_encode($r));
[$cod] = $anon->pedir('etiquetas.php?tipo=' . rawurlencode("nivel' OR '1'='1"));
comprobar('tipo fuera de la lista -> 422', $cod === 422, "obtuvo $cod");

// ----------------------------------------------------------------------------- tarjetas
echo "\n[Tarjetas: misma estructura en búsqueda, recomendaciones y árboles]\n";
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
[, $bus] = $A->pedir('buscar.php?q=' . rawurlencode('press banca'));
$t101 = array_values(array_filter($bus['resultados'] ?? [], fn($t) => $t['doc_id'] === 101))[0] ?? [];
comprobar('la tarjeta trae tipo, titulo, resumen, meta y etiquetas',
    !array_diff(['doc_id', 'origen', 'tipo', 'titulo', 'resumen', 'meta', 'etiquetas', 'liked'], array_keys($t101))
    && !isset($t101['snippet']) && !isset($t101['tags']), json_encode(array_keys($t101)));
comprobar('meta del ejercicio 101: Pecho, Barra, Principiante',
    ($t101['meta'] ?? []) === ['musculo' => 'Pecho', 'equipamiento' => 'Barra', 'nivel' => 'Principiante'], json_encode($t101['meta'] ?? null));
comprobar('etiquetas del ejercicio 101 en orden de tipo', $nombres($t101['etiquetas'] ?? []) === ['Pecho', 'Barra', 'Principiante', 'Fuerza'],
    json_encode($nombres($t101['etiquetas'] ?? [])));
comprobar('tipo en singular: Ejercicio', ($t101['tipo'] ?? '') === 'Ejercicio');
[, $ab] = $anon->pedir('menus.php?accion=docs&m=1&ids=301');
comprobar('menus.php devuelve las mismas tarjetas',
    ($ab['articulos'][0]['tipo'] ?? '') === 'Artículo' && isset($ab['articulos'][0]['etiquetas'], $ab['ejercicios'][0]['meta'])
    && count($ab['ejercicios']) === 5, json_encode([$ab['articulos'][0] ?? null, count($ab['ejercicios'] ?? [])]));

// ----------------------------------------------------------------------------- detalle.php
echo "\n[detalle.php]\n";
comprobar('sin sesión -> 401', $anon->pedir('detalle.php?origen=ejercicios&doc_id=101')[0] === 401);
$A->pedir('registrar_interaccion.php', ['doc_id' => 101, 'origen' => 'ejercicios']);
[$cod, $d] = $A->pedir('detalle.php?origen=ejercicios&doc_id=101&perfil_id=' . $mioB);
$doc = $d['documento'] ?? [];
comprobar('detalle -> 200', $cod === 200 && ($d['status'] ?? '') === 'success', "obtuvo $cod");
comprobar('texto completo, no el resumen', ($doc['texto'] ?? '') === 'Press de pecho en banco plano' && !isset($doc['resumen']), json_encode($doc));
comprobar('todas las etiquetas', $nombres($doc['etiquetas'] ?? []) === ['Pecho', 'Barra', 'Principiante', 'Fuerza']);
comprobar('ruta en el árbol de anatomía',
    ($doc['ruta'] ?? null) === ['arbol' => 'anatomia', 'nodos' => ['Cuerpo humano', 'Tren superior', 'Pecho', 'Barra']], json_encode($doc['ruta'] ?? null));
comprobar('liked = true para el perfil de la sesión (el perfil_id de la URL se ignora)', ($doc['liked'] ?? null) === true);
$rel = $d['relacionados'] ?? [];
$relClaves = array_map(fn($x) => $x['origen'] . ':' . $x['doc_id'], $rel);
comprobar('hasta 4 relacionados, sin el propio documento', count($rel) > 0 && count($rel) <= 4 && !in_array('ejercicios:101', $relClaves, true),
    json_encode($relClaves));
comprobar('el más relacionado comparte las 4 etiquetas (102: pecho, barra, principiante, fuerza)',
    ($relClaves[0] ?? '') === 'ejercicios:102', json_encode($relClaves));
comprobar('cada relacionado es una tarjeta con las etiquetas que comparte',
    !array_filter($rel, fn($x) => !isset($x['titulo'], $x['resumen'], $x['meta']) || !$x['comparte']), json_encode($rel[0] ?? null));
comprobar('los relacionados de pecho no incluyen pierna antes que pecho',
    !array_filter(array_slice($relClaves, 0, 3), fn($k) => preg_match('/^ejercicios:2/', $k)), json_encode($relClaves));

[, $d] = $A->pedir('detalle.php?origen=articulos&doc_id=302');
comprobar('ruta de un artículo en el árbol de temas',
    ($d['documento']['ruta']['arbol'] ?? '') === 'temas' && ($d['documento']['ruta']['nodos'][0] ?? '') === 'Conocimiento',
    json_encode($d['documento']['ruta'] ?? null));
$B->pedir('seleccionar_perfil.php', ['perfil_id' => $mioB]);
[, $d] = $B->pedir('detalle.php?origen=ejercicios&doc_id=101');
comprobar('otra cuenta ve liked = false: no ve el "me gusta" de A', ($d['documento']['liked'] ?? null) === false);
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $vacioA]);
[, $d] = $A->pedir('detalle.php?origen=ejercicios&doc_id=101');
comprobar('otro perfil de la MISMA cuenta ve liked = false', ($d['documento']['liked'] ?? null) === false);

$invalidos = [
    'origen fuera de la lista blanca -> 422' => ['origen=alimentos&doc_id=101', 422],
    'doc_id "1 OR 1=1" -> 422'               => ['origen=ejercicios&doc_id=' . rawurlencode('1 OR 1=1'), 422],
    'sin doc_id -> 422'                      => ['origen=ejercicios', 422],
    'documento inexistente -> 404'           => ['origen=ejercicios&doc_id=999999', 404],
];
foreach ($invalidos as $nombre => [$q, $esperado]) {
    [$cod] = $A->pedir("detalle.php?$q");
    comprobar($nombre, $cod === $esperado, "obtuvo $cod");
}

// HTML en el contenido: el servidor lo entrega como texto JSON, sin interpretarlo
$db = conexion();
$html = '<img src=x onerror="alert(1)"><b>negrita</b>';
$db->prepare('INSERT INTO articulos (id, titulo, contenido, etiquetas) VALUES (?, ?, ?, ?)')
   ->execute([390, $html, "Texto $html", 'pecho']);
[$cod, $d] = $A->pedir('detalle.php?origen=articulos&doc_id=390');
comprobar('contenido con HTML: va como texto en JSON, con nosniff',
    $cod === 200 && ($d['documento']['titulo'] ?? '') === $html
    && str_starts_with($A->cabeceras['content-type'] ?? '', 'application/json')
    && ($A->cabeceras['x-content-type-options'] ?? '') === 'nosniff', json_encode($A->cabeceras));
$db->exec('DELETE FROM articulos WHERE id = 390');

// ----------------------------------------------------------------------------- gráfica
echo "\n[recomendaciones.php: términos para la gráfica]\n";
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
$A->pedir('registrar_interaccion.php', ['doc_id' => 102, 'origen' => 'ejercicios']);
[$cod, $rec] = $A->pedir('recomendaciones.php');
$ter = $rec['perfil_terminos'] ?? [];
$pesos = array_column($ter, 'peso');
$ordenados = $pesos;
rsort($ordenados);
comprobar('hasta 8 términos, de mayor a menor peso', $cod === 200 && $ter && count($ter) <= 8 && $pesos === $ordenados, json_encode($ter));
comprobar('cada término trae la palabra completa, no solo la raíz',
    in_array('pecho', array_column($ter, 'palabra'), true) && !in_array('pech', array_column($ter, 'palabra'), true), json_encode($ter));
comprobar('las recomendaciones son tarjetas con similitud numérica',
    isset($rec['recomendaciones'][0]['meta'], $rec['recomendaciones'][0]['etiquetas']) && is_float($rec['recomendaciones'][0]['similitud'] ?? null)
    && !isset($rec['recomendaciones'][0]['score']), json_encode($rec['recomendaciones'][0] ?? null));
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $vacioA]);
[$cod, $rec] = $A->pedir('recomendaciones.php');
comprobar('perfil sin "me gusta": solo el estado, sin términos ni mensaje del servidor',
    $cod === 200 && $rec === ['status' => 'cold_start'], json_encode($rec));

terminar();
