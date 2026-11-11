<?php
// registro.php — POST JSON {correo, contrasena, nombre_completo, fecha_nacimiento}
// Crea la cuenta y deja la sesión iniciada (sin perfil activo todavía).
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/validacion.php';
require_once __DIR__ . '/lib/cifrado.php';

$datos = leer_json_post();

$correo     = normalizar_correo((string)($datos['correo'] ?? ''));
$contrasena = (string)($datos['contrasena'] ?? '');
$nombre     = limpiar_nombre_completo((string)($datos['nombre_completo'] ?? ''));
$fechaNac   = trim((string)($datos['fecha_nacimiento'] ?? ''));

$errores = array_filter([
    'correo'           => validar_correo($correo),
    'contrasena'       => validar_contrasena($contrasena, $correo),
    'nombre_completo'  => $nombre === null ? 'Nombre inválido (2 a 100 letras)' : null,
    'fecha_nacimiento' => validar_fecha_nacimiento($fechaNac),
]);
if ($errores) {
    responder_error(422, 'Datos inválidos', ['errores' => $errores]);
}

$db = conexion();
try {
    $db->prepare(
        'INSERT INTO cuentas (correo, contrasena_hash, nombre_cifrado, fecha_nac_cifrada)
         VALUES (?, ?, ?, ?)'
    )->execute([
        $correo,
        password_hash($contrasena, PASSWORD_DEFAULT),
        cifrar_campo($nombre, 'cuentas.nombre'),
        cifrar_campo($fechaNac, 'cuentas.fecha_nacimiento'),
    ]);
} catch (PDOException $e) {
    if (($e->errorInfo[1] ?? 0) === 1062) {        // correo duplicado
        responder_error(409, 'Ese correo no está disponible');
    }
    throw $e;
}

abrir_sesion_de_cuenta((int)$db->lastInsertId());
responder(['status' => 'success', 'correo' => $correo], 201);
