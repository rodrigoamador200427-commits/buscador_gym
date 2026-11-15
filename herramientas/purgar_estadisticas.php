<?php
// herramientas/purgar_estadisticas.php — borra consultas y eventos de más de 180 días.
//
//   php herramientas/purgar_estadisticas.php                              (BD real)
//   BUSCADOR_ENTORNO=pruebas php herramientas/purgar_estadisticas.php     (gym_buscador_test)
//
// Solo CLI (la carpeta además está bloqueada por HTTP). Borra en lotes para no bloquear
// las tablas mucho tiempo. Imprime solo cuántas filas borró de cada tabla.
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once dirname(__DIR__) . '/lib/config.php';
require_once dirname(__DIR__) . '/lib/db.php';

const DIAS_RETENCION = 180;
const LOTE = 5000;
const TABLAS_ESTADISTICAS = ['consultas', 'eventos'];   // nombres fijos, no vienen de fuera

$db = conexion();
$codigo = 0;
foreach (TABLAS_ESTADISTICAS as $tabla) {
    try {
        $borrar = $db->prepare("DELETE FROM $tabla WHERE creado_en < NOW() - INTERVAL ? DAY LIMIT " . LOTE);
        $total = 0;
        do {
            $borrar->execute([DIAS_RETENCION]);
            $total += $n = $borrar->rowCount();
        } while ($n === LOTE);
        echo "$tabla: $total filas borradas\n";
    } catch (PDOException $e) {
        // Sin getMessage(): puede incluir valores. Solo clase y SQLSTATE.
        fwrite(STDERR, sprintf("%s: no se pudo purgar (%s %s)\n", $tabla, get_class($e), $e->errorInfo[0] ?? ''));
        $codigo = 1;
    }
}
exit($codigo);
