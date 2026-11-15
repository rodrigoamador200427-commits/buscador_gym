<?php
// tests/test_autorizacion.php — pruebas HTTP de autorización y aislamiento (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php
//
// 1. Fuerza BUSCADOR_ENTORNO=pruebas y se niega a seguir si la BD no es *_test o si
//    coincide con la BD real.
// 2. Recrea gym_buscador_test (python scripts_py/tests/bd_prueba.py: contenido sintético).
// 3. Levanta su PROPIO servidor (php -S 127.0.0.1:<puerto libre>) con la config de
//    pruebas: no usa Apache ni la base real.
// 4. Recorre los endpoints como dos usuarios distintos (A y B). Sale con código 1 si algo falla.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

function docs(array $r): array
{
    return array_map(fn($d) => $d['origen'] . ':' . $d['doc_id'], $r['recomendaciones'] ?? []);
}

echo "BD: $conectada  |  servidor: $BASE\n";

// ----------------------------------------------------------------------------- escenario
$A = new Cliente($BASE);
$B = new Cliente($BASE);
$anon = new Cliente($BASE);

echo "\n[Sin sesión]\n";
comprobar('GET perfiles.php -> 401', $anon->pedir('perfiles.php')[0] === 401);
comprobar('seleccionar_perfil.php -> 401', $anon->pedir('seleccionar_perfil.php', ['perfil_id' => 1])[0] === 401);
comprobar('recomendaciones.php -> 401', $anon->pedir('recomendaciones.php')[0] === 401);

echo "\n[Sesión segura]\n";
[$cod] = $A->pedir('registro.php', ['correo' => 'a@prueba.test', 'contrasena' => 'CuentaA12345',
                                    'nombre_completo' => 'Cuenta A', 'fecha_nacimiento' => '2000-01-01']);
comprobar('registro A -> 201', $cod === 201);
$cookieRegistro = $A->setCookie[0] ?? '';
comprobar('cookie HttpOnly', stripos($cookieRegistro, 'HttpOnly') !== false, $cookieRegistro);
comprobar('cookie SameSite=Strict', stripos($cookieRegistro, 'SameSite=Strict') !== false, $cookieRegistro);
[$cod] = $A->pedir('login.php', ['correo' => 'a@prueba.test', 'contrasena' => 'CuentaA12345']);
$cookieLogin = $A->setCookie[0] ?? '';
$id = fn($c) => preg_match('/BGSESION=([^;]+)/', $c, $m) ? $m[1] : null;
comprobar('login regenera el ID de sesión', $cod === 200 && $id($cookieLogin) && $id($cookieLogin) !== $id($cookieRegistro));
$B->pedir('registro.php', ['correo' => 'b@prueba.test', 'contrasena' => 'CuentaB12345',
                           'nombre_completo' => 'Cuenta B', 'fecha_nacimiento' => '2000-01-01']);

$pechoA = crearPerfil($A, 'Pecho');
$piernaA = crearPerfil($A, 'Pierna');
$mioB = crearPerfil($B, 'Mio');

echo "\n[Autorización: perfil_id ajeno -> 403]\n";
[$cod] = $B->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
comprobar("B selecciona el perfil $pechoA de A -> 403", $cod === 403, "obtuvo $cod");
[$cod] = $B->pedir('perfiles.php', ['accion' => 'eliminar', 'perfil_id' => $piernaA]);
comprobar("B elimina el perfil $piernaA de A -> 403", $cod === 403, "obtuvo $cod");
[$cod] = $B->pedir('seleccionar_perfil.php', ['perfil_id' => 999999]);
comprobar('B usa un perfil inexistente -> 403 (no revela si existe)', $cod === 403, "obtuvo $cod");
[$cod] = $B->pedir('seleccionar_perfil.php', ['perfil_id' => '1 OR 1=1']);
comprobar('perfil_id no numérico -> 400', $cod === 400, "obtuvo $cod");
$n = (int)conexion()->query("SELECT COUNT(*) FROM perfiles WHERE id IN ($pechoA, $piernaA)")->fetchColumn();
comprobar('los perfiles de A siguen existiendo', $n === 2);
[$cod] = $A->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
comprobar('A selecciona su propio perfil -> 200', $cod === 200, "obtuvo $cod");

echo "\n[Aislamiento de recomendaciones, de punta a punta]\n";
foreach ([101, 102] as $d) {
    $A->pedir('registrar_interaccion.php', ['doc_id' => $d, 'origen' => 'ejercicios']);
}
[, $recPecho] = $A->pedir('recomendaciones.php');
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $piernaA]);
foreach ([201, 202] as $d) {
    $A->pedir('registrar_interaccion.php', ['doc_id' => $d, 'origen' => 'ejercicios']);
}
[, $recPierna] = $A->pedir('recomendaciones.php');
$dp = docs($recPecho);
$dn = docs($recPierna);
comprobar('Pecho y Pierna (misma cuenta) tienen recomendaciones', $dp && $dn,
    json_encode([$recPecho['status'] ?? null, $recPierna['status'] ?? null]));
comprobar('las recomendaciones son distintas y no comparten documentos', $dp && $dn && !array_intersect($dp, $dn),
    json_encode([$dp, $dn]));
comprobar('Pecho solo recibe pecho (1xx / art. 301)',
    $dp && !array_filter($dp, fn($k) => !preg_match('/^(ejercicios:1\d\d|articulos:301)$/', $k)), json_encode($dp));
comprobar('Pierna solo recibe pierna (2xx / art. 302)',
    $dn && !array_filter($dn, fn($k) => !preg_match('/^(ejercicios:2\d\d|articulos:302)$/', $k)), json_encode($dn));

$B->pedir('seleccionar_perfil.php', ['perfil_id' => $mioB]);
[, $recB] = $B->pedir('recomendaciones.php');
comprobar('B (sin likes) recibe cold_start, no el historial de A', ($recB['status'] ?? '') === 'cold_start');
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $pechoA]);
[, $busA] = $A->pedir('buscar.php?q=' . rawurlencode('press banca'));
$likedA = array_map(fn($r) => $r['doc_id'], array_values(array_filter($busA['resultados'] ?? [], fn($r) => $r['liked'])));
sort($likedA);
comprobar('control: A (Pecho) ve sus corazones 101 y 102 en la búsqueda', $likedA === [101, 102], json_encode($likedA));
[, $busB] = $B->pedir('buscar.php?q=' . rawurlencode('press banca'));
$likedB = array_filter($busB['resultados'] ?? [], fn($r) => $r['liked']);
comprobar('la misma búsqueda como B devuelve resultados', count($busB['resultados'] ?? []) > 0, json_encode($busB));
comprobar('en la búsqueda, B no ve los corazones de A', !$likedB, json_encode(array_values($likedB)));

[$cod] = $B->pedir('registrar_interaccion.php', ['doc_id' => 103, 'origen' => 'ejercicios', 'perfil_id' => $pechoA]);
$dueno = conexion()->query("SELECT perfil_id FROM interacciones WHERE doc_id = 103")->fetchAll(PDO::FETCH_COLUMN);
comprobar('un perfil_id ajeno en el cuerpo se ignora: el like va al perfil activo de B',
    $cod === 200 && array_map('intval', $dueno) === [$mioB], json_encode($dueno));

echo "\n[Cierre de sesión y límite de intentos]\n";
$copia = new Cliente($BASE);
$A->copiarCookiesA($copia);
$A->pedir('logout.php', []);
comprobar('cookie anterior al logout ya no sirve -> 401', $copia->pedir('recomendaciones.php')[0] === 401);
$codigos = [];
for ($i = 0; $i < 6; $i++) {
    $codigos[] = $anon->pedir('login.php', ['correo' => 'a@prueba.test', 'contrasena' => 'incorrecta123'])[0];
}
comprobar('5 fallos -> 401, el 6.º -> 429', $codigos === [401, 401, 401, 401, 401, 429], json_encode($codigos));

terminar();
