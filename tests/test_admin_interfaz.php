<?php
// tests/test_admin_interfaz.php — pruebas del panel de administrador en un navegador real (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_admin_interfaz.php [carpeta de capturas]
//
// Usa el arnés común (solo gym_buscador_test, servidor php -S propio) y el escenario fijo de
// tests/datos_admin.php, cuyos totales están calculados a mano. Agrega dos artículos con
// títulos "peligrosos" (HTML y una fórmula de hoja de cálculo) y lanza tests/admin_interfaz.mjs,
// que maneja Edge sin ventana (Node 22+ y Edge o Chrome; ruta alternativa en EDGE_PATH).
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';
require_once __DIR__ . '/datos_admin.php';

echo "BD: $conectada  |  servidor: $BASE\n";
$db = conexion();
$ids = datos_admin($db);

// Dos artículos con títulos peligrosos, con aperturas hace 20 días (solo se ven a 30 y 90
// días, así no cambian los totales de 7 días calculados a mano).
$ins = $db->prepare('INSERT INTO articulos (id, titulo, contenido, etiquetas) VALUES (?, ?, ?, ?)');
$ins->execute([391, '<img src=x onerror="window.__xss=1">Título con HTML', 'Texto <b>x</b>', 'pecho']);
$ins->execute([392, '=HYPERLINK("http://ejemplo.invalido","clic")', 'Texto', 'pecho']);
$ev = $db->prepare("INSERT INTO eventos (perfil_id, tipo, origen, doc_id, creado_en) VALUES (?, 'apertura', 'articulos', ?, ?)");
$hace20 = (new DateTimeImmutable('today'))->sub(new DateInterval('P20D'))->format('Y-m-d 12:00:00');
foreach (['u07', 'u08', 'u09', 'u10', 'u11'] as $u) {
    $ev->execute([$ids['perfiles'][$u], 391, $hace20]);
}
foreach (['u07', 'u08', 'u09'] as $u) {
    $ev->execute([$ids['perfiles'][$u], 392, $hace20]);
}
exec('python ' . escapeshellarg("$RAIZ/scripts_py/generar_etiquetas.py") . ' 2>&1', $salidaGen, $codigoGen);
if ($codigoGen !== 0) {
    abortar('no se pudieron regenerar las etiquetas: ' . implode(' ', $salidaGen));
}

$carpeta = $argv[1] ?? getenv('CAPTURAS') ?: '';
if ($carpeta !== '') {
    putenv("CAPTURAS=$carpeta");
}
passthru('node ' . escapeshellarg(__DIR__ . '/admin_interfaz.mjs') . ' ' . escapeshellarg($BASE), $codigoNode);
if ($codigoNode === 3) {
    abortar('no se pudo arrancar el navegador (Node 22+ y Edge o Chrome; ver EDGE_PATH)');
}
echo "\n";
comprobar('las pruebas del navegador pasan (detalle arriba)', $codigoNode === 0, "node salió con $codigoNode");

terminar();
