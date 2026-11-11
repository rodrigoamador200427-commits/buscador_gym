<?php
// login.php — POST JSON {correo, contrasena}
// Límite: 5 fallos por correo o 20 por IP en 15 min -> 429.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/validacion.php';
require_once __DIR__ . '/lib/intentos.php';

// Hash de una contraseña aleatoria que nadie conoce. Si el correo no existe se
// verifica contra él, para que la respuesta tarde lo mismo y no revele qué correos
// tienen cuenta.
const HASH_FICTICIO = '$2y$10$5AfQN8b1Jb2YF4PSr5wI8ulZQeqpUp/tB7cHQ1afxvSKubwNEb7mG';

$datos = leer_json_post();
$correo     = normalizar_correo((string)($datos['correo'] ?? ''));
$contrasena = (string)($datos['contrasena'] ?? '');

if (validar_correo($correo) !== null || $contrasena === '') {
    responder_error(422, 'Escribe tu correo y tu contraseña');
}

$db = conexion();
$correoHash = hash_correo($correo);
$ip = ip_cliente_binaria();

if (login_bloqueado($db, $correoHash, $ip)) {
    header('Retry-After: ' . (INTENTOS_VENTANA_MIN * 60));
    responder_error(429, 'Demasiados intentos. Espera ' . INTENTOS_VENTANA_MIN . ' minutos.');
}

$s = $db->prepare('SELECT id, contrasena_hash FROM cuentas WHERE correo = ?');
$s->execute([$correo]);
$cuenta = $s->fetch() ?: null;

$valida = password_verify($contrasena, $cuenta['contrasena_hash'] ?? HASH_FICTICIO) && $cuenta !== null;
registrar_intento($db, $correoHash, $ip, $valida);

if (!$valida) {
    responder_error(401, 'Correo o contraseña incorrectos');   // mismo mensaje exista o no el correo
}

// Si PHP cambia el algoritmo o el coste por defecto, se actualiza el hash
if (password_needs_rehash($cuenta['contrasena_hash'], PASSWORD_DEFAULT)) {
    $db->prepare('UPDATE cuentas SET contrasena_hash = ? WHERE id = ?')
       ->execute([password_hash($contrasena, PASSWORD_DEFAULT), $cuenta['id']]);
}

abrir_sesion_de_cuenta((int)$cuenta['id']);   // incluye session_regenerate_id(true)
responder(['status' => 'success', 'correo' => $correo]);
