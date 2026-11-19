<?php
// tests/medir_rendimiento.php — MEDICIÓN (no es una prueba que pase o falle) de la fase 7.
//
//   D:\Tools\SHAMP\php\php.exe tests\medir_rendimiento.php
//   SALTAR_PYTHON=1 D:\Tools\SHAMP\php\php.exe tests\medir_rendimiento.php    (solo el panel)
//
// Usa SOLO gym_buscador_test (el arnés lo garantiza). Copia a ella el contenido real (mysqldump de
// gym_buscador: la real solo se lee), crea una cuenta con tres «me gusta» y cronometra de punta a punta
// buscar.php, recomendaciones.php, menus.php, detalle.php y etiquetas.php; luego agrega 60 cuentas,
// 40 000 eventos y 5 000 consultas sintéticos y cronometra las seis secciones del panel.
// OJO: deja la BD de pruebas con el contenido real; la siguiente prueba la recrea.
declare(strict_types=1);
require_once __DIR__ . '/arnes.php';

$MYSQL = dirname(PHP_BINARY, 2) . DIRECTORY_SEPARATOR . 'mysql' . DIRECTORY_SEPARATOR . 'bin';   // SHAMP: <raíz>\php\php.exe y <raíz>\mysql\bin
$tablas = ['articulos', 'diccionario', 'documento_etiquetas', 'documento_rutas', 'ejercicios', 'etiquetas', 'postings'];
$volcado = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'contenido_real_fase7.sql';

echo "== Copiando el contenido real a $conectada\n";
exec("\"$MYSQL\\mysqldump.exe\" -uroot --skip-triggers --skip-add-locks gym_buscador " . implode(' ', $tablas) . " > \"$volcado\" 2>&1", $o, $c);
if ($c !== 0) abortar('mysqldump: ' . implode(' ', $o));
exec("\"$MYSQL\\mysql.exe\" -uroot --init-command=\"SET FOREIGN_KEY_CHECKS=0\" $conectada < \"$volcado\" 2>&1", $o, $c);
if ($c !== 0) abortar('importar: ' . implode(' ', $o));
@unlink($volcado);
function nuevaConexion(): PDO
{
    $d = config()['db'];
    return new PDO(sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', $d['host'], $d['nombre']), $d['usuario'], $d['contrasena'] ?? '',
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
}
$db = nuevaConexion();
foreach (['articulos', 'ejercicios', 'postings', 'documento_rutas'] as $t) {
    echo "   $t: " . $db->query("SELECT COUNT(*) FROM $t")->fetchColumn() . "\n";
}

function cronometrar(callable $f, int $n = 3): array
{
    $t = [];
    $r = null;
    for ($i = 0; $i < $n; $i++) {
        $a = hrtime(true);
        $r = $f();
        $t[] = (hrtime(true) - $a) / 1e9;
    }
    sort($t);
    return [$t, $r];
}
function fila(string $nombre, array $t): void
{
    printf("  %-58s min %5.2f  mediana %5.2f  max %5.2f s\n", $nombre, $t[0], $t[intdiv(count($t), 2)], $t[count($t) - 1]);
}

// ------------------------------------------------------------------ cuenta de usuario, perfil y likes
$U = new Cliente($BASE);
$U->pedir('registro.php', ['correo' => 'medida@prueba.test', 'contrasena' => 'Medida12345x', 'nombre_completo' => 'Medida', 'fecha_nacimiento' => '1995-05-05']);
$p = crearPerfil($U, 'Pecho');
$U->pedir('seleccionar_perfil.php', ['perfil_id' => $p]);
foreach ($db->query("SELECT id FROM ejercicios WHERE nombre_es LIKE '%press de banca%' ORDER BY id LIMIT 3")->fetchAll(PDO::FETCH_COLUMN) as $id) {
    $U->pedir('registrar_interaccion.php', ['doc_id' => (int)$id, 'origen' => 'ejercicios']);
}

if (!getenv('SALTAR_PYTHON')) {
echo "\n== Búsqueda de punta a punta (buscar.php, 3 repeticiones; el servidor es php -S)\n";
$consultas = ['pecho', 'press de banca con barra', 'pecho mancuernas principiante', 'jalon espalda polea', 'bisagra gluteo', 'creatina', 'pecho kettlebell', 'ganar fuerza'];
foreach ($consultas as $q) {
    [$t, $r] = cronometrar(fn() => $U->pedir('buscar.php?q=' . rawurlencode($q)));
    $d = $r[1]['descubrimiento'] ?? [];
    fila(sprintf('«%s» (%d resultados, vía %s)', $q, count($r[1]['resultados'] ?? []), $d['via'] ?? '-'), $t);
}
echo "\n== Otros endpoints que lanzan Python\n";
[$t] = cronometrar(fn() => $U->pedir('recomendaciones.php'));
fila('recomendaciones.php (3 likes)', $t);
[$t] = cronometrar(fn() => $U->pedir('menus.php?accion=catalogo'));
fila('menus.php?accion=catalogo', $t);
[$t] = cronometrar(fn() => $U->pedir('menus.php?accion=cruce&a=anatomia&x=1&b=equipamiento&y=barra'));
fila('menus.php?accion=cruce (pecho x barra)', $t);
}
echo "\n== Endpoints sin Python\n";
[$t] = cronometrar(fn() => $U->pedir('detalle.php?origen=ejercicios&doc_id=101'), 5);
fila('detalle.php', $t);
[$t] = cronometrar(fn() => $U->pedir('etiquetas.php'), 5);
fila('etiquetas.php', $t);

// ------------------------------------------------------------------ panel con actividad sintética
echo "\n== Panel de administrador (admin_estadisticas.php, dias=30)\n";
$A = new Cliente($BASE);
$A->pedir('registro.php', ['correo' => 'admin@prueba.test', 'contrasena' => 'AdminMedida12x', 'nombre_completo' => 'Admin', 'fecha_nacimiento' => '1990-01-01']);
$db = nuevaConexion();                            // la anterior estuvo inactiva durante las búsquedas
$db->exec("UPDATE cuentas SET rol='admin' WHERE correo='admin@prueba.test'");
$perfiles = [];
for ($i = 1; $i <= 60; $i++) {                    // 60 cuentas con un perfil cada una
    $c = new Cliente($BASE);
    [$cod, $rr] = $c->pedir('registro.php', ['correo' => "u$i@prueba.test", 'contrasena' => "Zq$i" . 'Lmnopq4567', 'nombre_completo' => 'Persona ' . strtr((string)$i, '0123456789', 'abcdefghij'), 'fecha_nacimiento' => (1980 + $i % 30) . '-06-15']);
    if ($cod !== 201) abortar("registro $i: $cod " . json_encode($rr));
    $perfiles[] = crearPerfil($c, "P$i");
}
$ej = $db->query('SELECT id FROM ejercicios')->fetchAll(PDO::FETCH_COLUMN);
$ar = $db->query('SELECT id FROM articulos')->fetchAll(PDO::FETCH_COLUMN);
$ins = fn(string $sql, array $filas) => $db->prepare($sql . implode(',', array_fill(0, count($filas), '(' . implode(',', array_fill(0, count(reset($filas)), '?')) . ')')))->execute(array_merge(...$filas));
mt_srand(7);
for ($lote = 0; $lote < 40; $lote++) {            // 40 000 eventos en 90 días
    $f = [];
    for ($i = 0; $i < 1000; $i++) {
        $esEj = mt_rand(0, 2) > 0;
        $tipo = ['impresion', 'impresion', 'impresion', 'apertura', 'like'][mt_rand(0, 4)];
        $f[] = [$tipo === 'impresion' ? null : $perfiles[mt_rand(0, 59)], $tipo, $esEj ? 'ejercicios' : 'articulos',
                $esEj ? $ej[mt_rand(0, count($ej) - 1)] : $ar[mt_rand(0, count($ar) - 1)], date('Y-m-d H:i:s', time() - mt_rand(0, 90 * 86400))];
    }
    $ins('INSERT INTO eventos (perfil_id, tipo, origen, doc_id, creado_en) VALUES ', $f);
}
$raices = ['pech', 'pech press', 'espald', 'gluteo', 'creatin', 'fuerz', 'diet', 'kettlebel pech', 'bicep', 'abdomen'];
for ($lote = 0; $lote < 5; $lote++) {              // 5 000 consultas
    $f = [];
    for ($i = 0; $i < 1000; $i++) {
        $f[] = [$raices[mt_rand(0, 9)], ['interseccion', 'concepto', 'recuperacion', 'sin_interseccion'][mt_rand(0, 3)], mt_rand(0, 40), date('Y-m-d H:i:s', time() - mt_rand(0, 90 * 86400))];
    }
    $ins('INSERT INTO consultas (raices, via, n_resultados, creado_en) VALUES ', $f);
}
echo '   ' . $db->query('SELECT COUNT(*) FROM eventos')->fetchColumn() . ' eventos, ' . $db->query('SELECT COUNT(*) FROM consultas')->fetchColumn()
    . ' consultas, ' . $db->query('SELECT COUNT(*) FROM cuentas')->fetchColumn() . " cuentas\n";
$A->pedir('login.php', ['correo' => 'admin@prueba.test', 'contrasena' => 'AdminMedida12x']);
foreach (['resumen', 'mas', 'menos', 'edad', 'busquedas', 'cobertura'] as $s) {
    [$t, $r] = cronometrar(fn() => $A->pedir("admin_estadisticas.php?seccion=$s&dias=30"));
    fila("seccion=$s (HTTP {$r[0]})", $t);
}
[$t] = cronometrar(function () use ($A) { foreach (['resumen', 'mas', 'menos', 'edad', 'busquedas', 'cobertura'] as $s) $A->pedir("admin_estadisticas.php?seccion=$s&dias=30"); }, 3);
fila('las 6 secciones seguidas (abrir el panel de cero)', $t);
[$t] = cronometrar(fn() => $A->pedir('admin_estadisticas.php?seccion=mas&dias=90'));
fila('seccion=mas dias=90', $t);
terminar();
