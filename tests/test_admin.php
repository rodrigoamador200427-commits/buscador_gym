<?php
// tests/test_admin.php — pruebas HTTP del panel de administrador (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_admin.php
//
// Mismo arnés que las otras pruebas (solo gym_buscador_test, servidor php -S propio) más el
// escenario fijo de tests/datos_admin.php, cuyos totales están calculados a mano en ese
// archivo. Comprueba acceso (401/403), que ninguna respuesta trae datos personales, el
// mínimo de 5 cuentas por rango de edad, que el rol no se puede enviar al registrarse y que
// totales y rankings coinciden con lo calculado a mano.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';
require_once __DIR__ . '/datos_admin.php';

echo "BD: $conectada  |  servidor: $BASE\n";
$db = conexion();
$ids = datos_admin($db);

$nombres = fn(array $lista, string $clave = 'concepto') => array_column($lista, $clave);
$porDoc = fn(array $lista) => array_combine(array_column($lista, 'doc_id'), $lista);

// ----------------------------------------------------------------------------- acceso
echo "\n[Acceso: 401 sin sesión, 403 sin el rol, 200 con el rol]\n";
$anon = new Cliente($BASE);
$usuario = new Cliente($BASE);
$admin = new Cliente($BASE);
comprobar('admin_estadisticas.php sin sesión -> 401', $anon->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 401);
comprobar('admin.php sin sesión -> 401', $anon->pedir('admin.php')[0] === 401);
comprobar('admin.html no existe como archivo (no se puede servir sin pasar por PHP)', !file_exists("$RAIZ/admin.html"));

[$cod] = $usuario->pedir('login.php', ['correo' => 'u01@prueba.test', 'contrasena' => 'UsuarioPrueba12345']);
comprobar('usuario normal inicia sesión', $cod === 200, "obtuvo $cod");
comprobar('usuario normal en admin_estadisticas.php -> 403', $usuario->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 403);
[$cod, $cuerpo] = $usuario->pedir('admin.php');
comprobar('usuario normal en admin.php -> 403 y sin el HTML del panel', $cod === 403 && !str_contains(json_encode($cuerpo), '<html'), "obtuvo $cod");
[, $s] = $usuario->pedir('sesion.php');
comprobar('sesion.php no revela el rol ni para el usuario', !array_key_exists('rol', $s) && !array_key_exists('admin', $s), json_encode($s));

[$cod] = $admin->pedir('login.php', ['correo' => 'admin@prueba.test', 'contrasena' => 'AdminPrueba12345']);
comprobar('administrador inicia sesión', $cod === 200, "obtuvo $cod");
[$cod, $r] = $admin->pedir('admin_estadisticas.php?seccion=resumen&dias=7');
comprobar('administrador en admin_estadisticas.php -> 200', $cod === 200 && ($r['status'] ?? '') === 'success', "obtuvo $cod " . json_encode($r));
$html = $admin->pedirCrudo('admin.php');
comprobar('administrador en admin.php -> 200 con la página del panel',
    $html[0] === 200 && str_starts_with($admin->cabeceras['content-type'] ?? '', 'text/html') && str_contains($admin->cuerpoCrudo, 'id="panel"'),
    json_encode([$html[0], $admin->cabeceras['content-type'] ?? null]));
[$cod] = $admin->pedirCrudo('admin_estadisticas.php?seccion=resumen&dias=7', '{}', 'application/json');
comprobar('POST -> 405 (solo GET)', $cod === 405, "obtuvo $cod");
foreach (['seccion=otra&dias=7' => 'sección desconocida', 'seccion=resumen&dias=15' => 'dias fuera de 7/30/90',
          'seccion=resumen&dias=7;DROP' => 'dias no numérico', 'dias=7' => 'sin sección'] as $q => $nombre) {
    [$cod] = $admin->pedir("admin_estadisticas.php?$q");
    comprobar("$nombre -> 422", $cod === 422, "obtuvo $cod");
}

// Si se quita el rol en la BD, la siguiente petición ya es 403 (no basta la sesión)
$db->prepare("UPDATE cuentas SET rol = 'usuario' WHERE id = ?")->execute([$ids['admin_id']]);
comprobar('al quitar el rol en la BD, la misma sesión recibe 403 de inmediato', $admin->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 403);
$db->prepare("UPDATE cuentas SET rol = 'admin' WHERE id = ?")->execute([$ids['admin_id']]);
comprobar('al devolverlo, vuelve a 200', $admin->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 200);

// ----------------------------------------------------------------------------- el rol no se puede enviar
echo "\n[El rol admin no se puede obtener por la web]\n";
$nuevo = new Cliente($BASE);
[$cod] = $nuevo->pedir('registro.php', ['correo' => 'colado@prueba.test', 'contrasena' => 'Colado12345678',
    'nombre_completo' => 'Intento Colado', 'fecha_nacimiento' => '1990-05-05', 'rol' => 'admin']);
$rol = $db->query("SELECT rol FROM cuentas WHERE correo = 'colado@prueba.test'")->fetchColumn();
comprobar('registro.php con rol=admin en el cuerpo crea la cuenta como usuario', $cod === 201 && $rol === 'usuario', "cod $cod rol $rol");
comprobar('esa cuenta recibe 403 en el panel', $nuevo->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 403);
[$cod] = $nuevo->pedir('perfiles.php', ['accion' => 'crear', 'nombre' => 'X', 'rol' => 'admin']);
$rol = $db->query("SELECT rol FROM cuentas WHERE correo = 'colado@prueba.test'")->fetchColumn();
comprobar('otros endpoints con rol en el cuerpo tampoco lo cambian', $rol === 'usuario');
$fuentes = array_filter(glob("$RAIZ/*.php"), fn($f) => basename($f) !== 'admin_estadisticas.php' && basename($f) !== 'admin.php');
$mencionan = array_map('basename', array_filter($fuentes, fn($f) => preg_match('/\brol\b/', (string)file_get_contents($f))));
comprobar('ningún endpoint web (salvo los del panel) menciona la columna rol', !$mencionan, json_encode($mencionan));
// Solo sentencias que ESCRIBEN la columna (UPDATE ... SET rol / INSERT INTO cuentas (... rol ...)); leerla
// (por ejemplo para excluir a los administradores de las cifras) es normal.
const ESCRIBE_ROL = '/UPDATE\s+cuentas\s+SET[^;"]*\brol\b|INSERT\s+INTO\s+cuentas\s*\([^)]*\brol\b/is';
$libs = array_map('basename', array_filter(glob("$RAIZ/lib/*.php"), fn($f) => preg_match(ESCRIBE_ROL, (string)file_get_contents($f))));
comprobar('ninguna librería escribe el rol (solo herramientas/crear_admin.php)', !$libs, json_encode($libs));
comprobar('la regla sí detecta una escritura del rol (control)',
    preg_match(ESCRIBE_ROL, "UPDATE cuentas SET rol = 'admin' WHERE id = 1") === 1
    && preg_match(ESCRIBE_ROL, "INSERT INTO cuentas (correo, rol) VALUES (?, 'admin')") === 1
    && preg_match(ESCRIBE_ROL, "SELECT 1 FROM cuentas ca WHERE ca.rol = 'admin'") === 0);
$db->exec("DELETE FROM cuentas WHERE correo = 'colado@prueba.test'");

// ----------------------------------------------------------------------------- sin datos personales
echo "\n[Ninguna respuesta del panel contiene datos personales]\n";
const PROHIBIDAS = ['correo', 'nombre', 'nombre_completo', 'fecha_nac', 'fecha_nacimiento', 'contrasena', 'contrasena_hash', 'perfil_id', 'cuenta_id'];
$claves = function (mixed $v, array &$acum) use (&$claves): void {
    if (!is_array($v)) {
        return;
    }
    foreach ($v as $k => $x) {
        if (is_string($k)) {
            $acum[$k] = true;
        }
        $claves($x, $acum);
    }
};
$respuestas = [];
foreach (['resumen', 'mas', 'menos', 'edad', 'busquedas', 'cobertura'] as $sec) {
    foreach ([7, 30, 90] as $d) {
        [$cod, $r] = $admin->pedir("admin_estadisticas.php?seccion=$sec&dias=$d");
        $respuestas["$sec/$d"] = [$cod, $r];
    }
}
$todas = [];
foreach ($respuestas as $k => [$cod, $r]) {
    $claves($r, $todas);
}
$encontradas = array_values(array_intersect(array_keys($todas), PROHIBIDAS));
comprobar('las 18 respuestas (6 secciones x 3 períodos) responden 200', !array_filter($respuestas, fn($x) => $x[0] !== 200));
comprobar('ninguna clave de las respuestas es correo, nombre, fecha_nac, contrasena ni perfil_id', !$encontradas, json_encode($encontradas));
$textoTodo = json_encode(array_map(fn($x) => $x[1], $respuestas));
comprobar('ningún correo de prueba ni nombre de usuario aparece en el texto de las respuestas',
    !preg_match('/@prueba\.test|Usuario u\d\d|Administrador/', $textoTodo));
$rangoEdad = fn(array $r) => $r['edad']['rangos'] ?? [];

// ----------------------------------------------------------------------------- el admin no cuenta
echo "\n[Los eventos del administrador no cuentan]\n";
$delAdmin = (int)$db->query("SELECT COUNT(*) FROM eventos e JOIN perfiles p ON p.id = e.perfil_id JOIN cuentas c ON c.id = p.cuenta_id WHERE c.rol = 'admin'")->fetchColumn();
comprobar('control: el administrador sí tiene 5 eventos en la BD (4 aperturas y 1 «me gusta», hace 1 día)', $delAdmin === 5, "tiene $delAdmin");
$r7admin = $respuestas['resumen/7'][1];
comprobar('7 días: siguen siendo 9 aperturas y 5 «me gusta» (con los del admin serían 13 y 6)', $r7admin['aperturas']['valor'] === 9 && $r7admin['me_gusta']['valor'] === 5, json_encode([$r7admin['aperturas'], $r7admin['me_gusta']]));
comprobar('la actividad de ayer sigue en 5 aperturas y 4 «me gusta»', (function () use ($r7admin) {
    $ayer = (new DateTimeImmutable('today'))->sub(new DateInterval('P1D'))->format('Y-m-d');
    $p = array_values(array_filter($r7admin['por_dia'], fn($x) => $x['dia'] === $ayer))[0] ?? [];
    return ($p['aperturas'] ?? null) === 5 && ($p['me_gusta'] ?? null) === 4;
})(), json_encode($r7admin['por_dia'] ?? null));
$mas7 = $respuestas['mas/7'][1];
comprobar('más consumidos: 105 y 303 (que solo abrió el admin) no aparecen y 101 sigue con 6',
    !in_array(105, array_column($mas7['ejercicios'], 'doc_id'), true) && !in_array(303, array_column($mas7['articulos'], 'doc_id'), true)
    && ($mas7['ejercicios'][0]['total'] ?? 0) === 6, json_encode($mas7));
$menos7 = $respuestas['menos/7'][1];
comprobar('105 sigue siendo "poco abierto" con 0 aperturas (el admin lo abrió) y 303 sigue "nunca mostrado"',
    ($menos7['poco_abiertos'][0]['doc_id'] ?? 0) === 105 && ($menos7['poco_abiertos'][0]['aperturas'] ?? -1) === 0
    && array_column($menos7['nunca_mostrados'], 'doc_id') === [303], json_encode([$menos7['poco_abiertos'][0] ?? null, $menos7['nunca_mostrados']]));
comprobar('cobertura: Pecho sigue con 8 interacciones (con las del admin serían 10)', (function () use ($respuestas) {
    $m = array_column($respuestas['cobertura/7'][1]['musculos'], null, 'concepto');
    return ($m['Pecho']['interacciones'] ?? null) === 8;
})());

// ----------------------------------------------------------------------------- resumen
echo "\n[Resumen: totales calculados a mano]\n";
$r7 = $respuestas['resumen/7'][1];
$r30 = $respuestas['resumen/30'][1];
$r90 = $respuestas['resumen/90'][1];
comprobar('cuentas de usuario: 31 (el admin no cuenta)', ($r7['cuentas']['valor'] ?? null) === 31, json_encode($r7['cuentas'] ?? null));
comprobar('cuentas nuevas en 7 días: 6, en el período anterior 0', ($r7['cuentas']['nuevas']['valor'] ?? null) === 6 && $r7['cuentas']['nuevas']['anterior'] === 0
    && $r7['cuentas']['nuevas']['variacion'] === null, json_encode($r7['cuentas']['nuevas'] ?? null));
comprobar('perfiles: 31', ($r7['perfiles']['valor'] ?? null) === 31);
comprobar('7 días: 9 aperturas, 5 me gusta, 7 perfiles activos', $r7['aperturas']['valor'] === 9 && $r7['me_gusta']['valor'] === 5 && $r7['perfiles_activos']['valor'] === 7,
    json_encode([$r7['aperturas'], $r7['me_gusta'], $r7['perfiles_activos']]));
comprobar('7 días: período anterior con 2 aperturas, 2 me gusta y 3 activos; variación +350 %, +150 %, +133.3 %',
    $r7['aperturas']['anterior'] === 2 && $r7['aperturas']['variacion'] == 350.0 && $r7['me_gusta']['anterior'] === 2 && $r7['me_gusta']['variacion'] == 150.0
    && $r7['perfiles_activos']['anterior'] === 3 && $r7['perfiles_activos']['variacion'] == 133.3, json_encode([$r7['aperturas'], $r7['me_gusta'], $r7['perfiles_activos']]));
comprobar('7 días: 8 búsquedas, 4 en el período anterior (+100 %)', $r7['busquedas']['valor'] === 8 && $r7['busquedas']['anterior'] === 4 && $r7['busquedas']['variacion'] == 100.0, json_encode($r7['busquedas']));
comprobar('30 días: 12 aperturas, 8 me gusta, 12 activos, 12 búsquedas', $r30['aperturas']['valor'] === 12 && $r30['me_gusta']['valor'] === 8
    && $r30['perfiles_activos']['valor'] === 12 && $r30['busquedas']['valor'] === 12, json_encode([$r30['aperturas'], $r30['me_gusta'], $r30['perfiles_activos'], $r30['busquedas']]));
comprobar('90 días: 14 aperturas, 8 me gusta, 13 activos', $r90['aperturas']['valor'] === 14 && $r90['me_gusta']['valor'] === 8 && $r90['perfiles_activos']['valor'] === 13,
    json_encode([$r90['aperturas'], $r90['me_gusta'], $r90['perfiles_activos']]));
$dias = $r7['por_dia'] ?? [];
$sumaDias = array_sum(array_column($dias, 'aperturas'));
comprobar('actividad por día: 8 puntos consecutivos (7 días + hoy) y la suma de aperturas da 9',
    count($dias) === 8 && $sumaDias === 9 && array_column($dias, 'dia') === array_map(fn($i) => (new DateTimeImmutable('today'))->sub(new DateInterval("P{$i}D"))->format('Y-m-d'), range(7, 0)),
    json_encode($dias));
$ayer = (new DateTimeImmutable('today'))->sub(new DateInterval('P1D'))->format('Y-m-d');
$pAyer = array_values(array_filter($dias, fn($p) => $p['dia'] === $ayer))[0] ?? [];
comprobar('ayer: 5 aperturas, 4 me gusta y 8 búsquedas', ($pAyer['aperturas'] ?? null) === 5 && ($pAyer['me_gusta'] ?? null) === 4 && ($pAyer['busquedas'] ?? null) === 8, json_encode($pAyer));

// ----------------------------------------------------------------------------- más consumidos
echo "\n[Más consumidos]\n";
$m7 = $respuestas['mas/7'][1];
$ej = $porDoc($m7['ejercicios'] ?? []);
comprobar('ejercicios en 7 días ordenados: 101 (6), 201 (4), 102 (1)', array_column($m7['ejercicios'] ?? [], 'doc_id') === [101, 201, 102], json_encode($m7['ejercicios'] ?? null));
comprobar('101: 4 aperturas y 2 me gusta; 201: 2 y 2', ($ej[101]['aperturas'] ?? 0) === 4 && $ej[101]['me_gusta'] === 2 && $ej[201]['aperturas'] === 2 && $ej[201]['me_gusta'] === 2, json_encode($ej));
comprobar('cada fila trae el título del documento', ($ej[101]['titulo'] ?? '') === 'Press de banca plano');
comprobar('artículos en 7 días: 302 (2) antes que 301 (1)', array_column($m7['articulos'] ?? [], 'doc_id') === [302, 301], json_encode($m7['articulos'] ?? null));
$m90 = $respuestas['mas/90'][1];
comprobar('90 días: entran 104 (2) y 204, 205, 103, 105, 202, 203 (1 cada uno); máximo 10 filas',
    count($m90['ejercicios']) === 10 && array_slice(array_column($m90['ejercicios'], 'doc_id'), 0, 3) === [101, 201, 104], json_encode(array_column($m90['ejercicios'], 'doc_id')));

// ----------------------------------------------------------------------------- menos consumidos
echo "\n[Menos consumidos]\n";
$l7 = $respuestas['menos/7'][1];
$poco = $l7['poco_abiertos'] ?? [];
comprobar('poco abiertos en 7 días: 105 (25 impresiones, 0 %), 104 (20, 0 %) y 301 (30, 3.3 %); 101 queda fuera (10 impresiones)',
    array_map(fn($x) => $x['origen'] . ':' . $x['doc_id'], $poco) === ['ejercicios:105', 'ejercicios:104', 'articulos:301'], json_encode($poco));
comprobar('tasas de apertura: 0, 0 y 3.3 %', array_column($poco, 'tasa_apertura') == [0, 0, 3.3], json_encode(array_column($poco, 'tasa_apertura')));
comprobar('cada fila trae sus etiquetas para saber qué revisar', !array_filter($poco, fn($x) => !$x['etiquetas']), json_encode(array_column($poco, 'etiquetas')));
$l30 = $respuestas['menos/30'][1];
comprobar('en 30 días 104 ya tiene 1 apertura (5 %) y pasa detrás de 105', array_column($l30['poco_abiertos'], 'doc_id') === [105, 301, 104], json_encode(array_column($l30['poco_abiertos'], 'doc_id')));
comprobar('nunca mostrados: solo el artículo 303', count($l7['nunca_mostrados']) === 1 && $l7['nunca_mostrados'][0]['doc_id'] === 303
    && $l7['nunca_mostrados_total'] === ['ejercicios' => 0, 'articulos' => 1], json_encode($l7['nunca_mostrados']));
comprobar('etiquetas a revisar: las que se repiten entre los poco abiertos (Pecho y Fuerza en los 3)',
    in_array('Pecho', array_column($l7['etiquetas_a_revisar'], 'etiqueta'), true), json_encode($l7['etiquetas_a_revisar']));

// ----------------------------------------------------------------------------- edad
echo "\n[Edad]\n";
$e7 = $respuestas['edad/7'][1];
$rangos = array_combine(array_column($e7['rangos'], 'rango'), $e7['rangos']);
comprobar('solo aparecen los rangos con 5 cuentas o más: 18 a 24, 25 a 34, 35 a 44', array_keys($rangos) === ['18 a 24', '25 a 34', '35 a 44'], json_encode(array_keys($rangos)));
comprobar('"menos de 18" (2 cuentas) y "45 o más" (4) no aparecen aunque tengan eventos', !isset($rangos['menos de 18']) && !isset($rangos['45 o más']));
comprobar('cuentas por rango: 6, 12 y 7; 6 cuentas quedan sin rango visible', $rangos['18 a 24']['cuentas'] === 6 && $rangos['25 a 34']['cuentas'] === 12
    && $rangos['35 a 44']['cuentas'] === 7 && $e7['cuentas_sin_rango_visible'] === 6, json_encode($e7));
comprobar('18 a 24 en 7 días: 4 aperturas, 1 me gusta, 2 cuentas activas', $rangos['18 a 24']['aperturas'] === 4 && $rangos['18 a 24']['me_gusta'] === 1 && $rangos['18 a 24']['cuentas_activas'] === 2, json_encode($rangos['18 a 24']));
comprobar('25 a 34 en 7 días: 3 aperturas, 3 me gusta', $rangos['25 a 34']['aperturas'] === 3 && $rangos['25 a 34']['me_gusta'] === 3, json_encode($rangos['25 a 34']));
comprobar('18 a 24: músculo más consumido Pecho (4 eventos: 101 x3, 102) y tema Fuerza (artículo 301)',
    ($rangos['18 a 24']['musculos'][0] ?? null) === ['concepto' => 'Pecho', 'eventos' => 4] && ($rangos['18 a 24']['temas'][0] ?? null) === ['concepto' => 'Fuerza', 'eventos' => 1], json_encode($rangos['18 a 24']));
comprobar('25 a 34: Cuádriceps 2 (201 x2) y Pecho 2 (101 x2); tema Fuerza 2 (302 x2)',
    array_column($rangos['25 a 34']['musculos'], 'eventos', 'concepto') === ['Cuádriceps' => 2, 'Pecho' => 2] && ($rangos['25 a 34']['temas'][0]['eventos'] ?? 0) === 2, json_encode($rangos['25 a 34']));
comprobar('las listas de músculos y temas tienen 5 entradas como máximo', !array_filter($e7['rangos'], fn($r) => count($r['musculos']) > 5 || count($r['temas']) > 5));
unset($e7['generado_en']);     // la marca de hora de la respuesta no es un dato de personas
comprobar('la respuesta no trae edades individuales ni fechas (solo rangos)', !preg_match('/"edad"\s*:\s*\d|\d{4}-\d{2}-\d{2}/', json_encode($e7)));
// Con menos cuentas visibles, desaparecen rangos: se borran 2 cuentas de 18 a 24 (quedan 4)
$db->exec("DELETE FROM cuentas WHERE correo IN ('u05@prueba.test', 'u06@prueba.test')");
[, $e2] = $admin->pedir('admin_estadisticas.php?seccion=edad&dias=7');
comprobar('al bajar "18 a 24" a 4 cuentas, el rango desaparece', array_column($e2['rangos'], 'rango') === ['25 a 34', '35 a 44'], json_encode(array_column($e2['rangos'], 'rango')));

// ----------------------------------------------------------------------------- búsquedas
echo "\n[Búsquedas]\n";
$b7 = $respuestas['busquedas/7'][1];
comprobar('7 días: 8 búsquedas, 2 sin resultados', $b7['total'] === 8 && $b7['sin_resultados'] === 2, json_encode([$b7['total'], $b7['sin_resultados']]));
comprobar('raíces más buscadas: banc 3, press 3, sentadill 2, xyz 2, pech 1, zancad 1',
    array_column($b7['raices'], 'busquedas', 'raiz') === ['banc' => 3, 'press' => 3, 'sentadill' => 2, 'xyz' => 2, 'pech' => 1, 'zancad' => 1], json_encode($b7['raices']));
comprobar('contenido faltante: "xyz" (ninguno, 2 veces, 2 sin resultados) y "pech zancad" (sin_interseccion, 1)',
    array_map(fn($f) => [$f['raices'], $f['via'], $f['busquedas'], $f['sin_resultados']], $b7['contenido_faltante']) === [['xyz', 'ninguno', 2, 2], ['pech zancad', 'sin_interseccion', 1, 0]],
    json_encode($b7['contenido_faltante']));
comprobar('30 días: 12 búsquedas y banc/press suben a 7', $respuestas['busquedas/30'][1]['total'] === 12 && ($respuestas['busquedas/30'][1]['raices'][0]['busquedas'] ?? 0) === 7);
comprobar('ninguna consulta trae texto original ni perfil (solo raíces, vía y conteos)', !array_diff(array_keys($b7['contenido_faltante'][0]), ['raices', 'via', 'busquedas', 'sin_resultados']));

// ----------------------------------------------------------------------------- cobertura
echo "\n[Cobertura]\n";
$c7 = $respuestas['cobertura/7'][1];
$mus = array_combine($nombres($c7['musculos']), $c7['musculos']);
comprobar('músculos: Pecho (5 ejercicios + artículo 301 = 6 documentos) con 8 interacciones en 7 días (101: 6, 102: 1, 301: 1); Cuádriceps (5) con 4',
    $mus['Pecho']['documentos'] === 6 && $mus['Pecho']['interacciones'] === 8 && $mus['Cuádriceps']['documentos'] === 5 && $mus['Cuádriceps']['interacciones'] === 4, json_encode($c7['musculos']));
comprobar('ordenados de menos a más documentos', array_column($c7['musculos'], 'documentos') === array_values(array_filter(array_column($c7['musculos'], 'documentos'))) && $c7['musculos'][0]['documentos'] <= end($c7['musculos'])['documentos']);
$tem = array_combine($nombres($c7['temas']), $c7['temas']);
comprobar('temas: Fuerza con 2 artículos y 3 interacciones; Recuperación con 1 (el 303) y 0, marcada con poca interacción',
    $tem['Fuerza']['documentos'] === 2 && $tem['Fuerza']['interacciones'] === 3 && $tem['Recuperación']['documentos'] === 1 && $tem['Recuperación']['interacciones'] === 0
    && $tem['Recuperación']['poca_interaccion'] === true, json_encode($c7['temas']));
$tecnica = $tem['Técnica y biomecánica'] ?? null;
comprobar('un tema sin ninguna interacción siempre se marca con poca interacción, aunque la mediana sea 0',
    $tecnica === null || ($tecnica['interacciones'] === 0 && $tecnica['poca_interaccion'] === true), json_encode($tecnica));
comprobar('cada fila dice si tiene pocos documentos o poca interacción', !array_filter(array_merge($c7['musculos'], $c7['temas']), fn($x) => !array_key_exists('pocos_documentos', $x) || !array_key_exists('poca_interaccion', $x)));

// ----------------------------------------------------------------------------- sesión de 15 minutos
echo "\n[Sesión de administrador: 15 minutos de inactividad]\n";
comprobar('la constante de inactividad del administrador es 900 s (15 min) y la del usuario 1800 s',
    preg_match("/SESION_INACTIVIDAD_ADMIN_SEG = 900;/", (string)file_get_contents("$RAIZ/lib/sesion.php")) === 1 && preg_match("/SESION_INACTIVIDAD_SEG = 1800;/", (string)file_get_contents("$RAIZ/lib/sesion.php")) === 1);
// Se simula el paso del tiempo retrasando 'ultima_actividad' en el archivo de sesión del servidor de pruebas
$envejecer = function (Cliente $c, int $segundos) use ($RUTA_SESIONES): bool {
    $id = $c->idSesion();
    $ruta = $id ? "$RUTA_SESIONES/sess_$id" : null;
    if (!$ruta || !is_file($ruta)) {
        return false;
    }
    $datos = (string)file_get_contents($ruta);
    $nuevo = preg_replace_callback('/ultima_actividad\|i:(\d+);/', fn($m) => 'ultima_actividad|i:' . ((int)$m[1] - $segundos) . ';', $datos);
    return file_put_contents($ruta, $nuevo) !== false;
};
if ($envejecer($admin, 16 * 60)) {
    comprobar('tras 16 minutos sin actividad, el administrador recibe 401', $admin->pedir('admin_estadisticas.php?seccion=resumen&dias=7')[0] === 401);
    $envejecer($usuario, 16 * 60);
    comprobar('tras 16 minutos, un usuario normal sigue con sesión (su límite es 30)', $usuario->pedir('sesion.php')[1]['autenticado'] === true);
    $envejecer($usuario, 31 * 60);
    comprobar('tras 31 minutos, el usuario normal también la pierde', $usuario->pedir('sesion.php')[1]['autenticado'] === false);
} else {
    comprobar('se pudo envejecer la sesión en el servidor de pruebas', false, json_encode(['id' => $admin->idSesion(), 'carpeta' => $RUTA_SESIONES, 'archivos' => array_map('basename', glob("$RUTA_SESIONES/*") ?: [])]));
}

terminar();
