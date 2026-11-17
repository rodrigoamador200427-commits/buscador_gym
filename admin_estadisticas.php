<?php
// admin_estadisticas.php — GET ?seccion=resumen|mas|menos|edad|busquedas|cobertura&dias=7|30|90
// Datos agregados para el panel de administrador. Solo para cuentas con rol 'admin'
// (requerir_admin: 401 sin sesión, 403 sin el rol). Solo GET.
// La respuesta nunca incluye correo, nombre, fecha de nacimiento, contraseña ni perfil_id.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/admin_estadisticas.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    header('Allow: GET');
    responder_error(405, 'Método no permitido');
}

requerir_admin();
session_write_close();

const SECCIONES = ['resumen', 'mas', 'menos', 'edad', 'busquedas', 'cobertura'];
$seccion = $_GET['seccion'] ?? '';
$dias = $_GET['dias'] ?? '30';
if (!in_array($seccion, SECCIONES, true)) {
    responder_error(422, 'seccion inválida');
}
if (!is_string($dias) || !ctype_digit($dias) || !in_array((int)$dias, PERIODOS_VALIDOS, true)) {
    responder_error(422, 'dias debe ser 7, 30 o 90');
}
$dias = (int)$dias;

$db = conexion();
$datos = match ($seccion) {
    'resumen'   => seccion_resumen($db, $dias),
    'mas'       => seccion_mas_consumidos($db, $dias),
    'menos'     => seccion_menos_consumidos($db, $dias),
    'edad'      => seccion_edad($db, $dias),
    'busquedas' => seccion_busquedas($db, $dias),
    'cobertura' => seccion_cobertura($db, $dias),
};

// Última barrera: si una consulta futura colara una clave sensible, no sale del servidor
const CLAVES_PROHIBIDAS = ['correo', 'nombre_completo', 'nombre_cifrado', 'fecha_nac', 'fecha_nacimiento', 'fecha_nac_cifrada',
    'contrasena', 'contrasena_hash', 'perfil_id', 'cuenta_id'];
$revisar = function (mixed $v) use (&$revisar): void {
    if (!is_array($v)) {
        return;
    }
    foreach ($v as $k => $x) {
        if (is_string($k) && in_array($k, CLAVES_PROHIBIDAS, true)) {
            throw new RuntimeException("clave prohibida en la respuesta del panel: $k");
        }
        $revisar($x);
    }
};
$revisar($datos);

responder(['status' => 'success', 'seccion' => $seccion, 'dias' => $dias, 'generado_en' => date('Y-m-d H:i:s')] + $datos);
