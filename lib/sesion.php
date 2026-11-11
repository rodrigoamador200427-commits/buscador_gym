<?php
// lib/sesion.php — sesión segura y autorización.
//
// php.ini de SHAMP trae use_strict_mode=0 y cookie_httponly vacío: aquí se
// fuerzan los valores seguros antes de cada session_start(), sin depender de php.ini.
declare(strict_types=1);

const SESION_NOMBRE = 'BGSESION';
const SESION_INACTIVIDAD_SEG = 1800;   // 30 min sin actividad -> sesión cerrada

function es_https(): bool
{
    return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || (int)($_SERVER['SERVER_PORT'] ?? 0) === 443;
}

function parametros_cookie(): array
{
    // Cookie limitada a la carpeta del proyecto (todos los endpoints viven en su raíz)
    $ruta = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/') . '/';
    return [
        'lifetime' => 0,                // muere al cerrar el navegador
        'path'     => $ruta,
        'secure'   => es_https(),       // en local es http; en un servidor real con HTTPS se activa sola
        'httponly' => true,             // JavaScript no puede leerla (mitiga robo por XSS)
        'samesite' => 'Strict',         // no viaja en peticiones iniciadas por otros sitios (CSRF)
    ];
}

function iniciar_sesion(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    ini_set('session.use_strict_mode', '1');      // rechaza IDs de sesión inventados (fijación)
    ini_set('session.use_only_cookies', '1');
    ini_set('session.use_trans_sid', '0');        // nunca el ID en la URL
    ini_set('session.sid_length', '48');
    ini_set('session.sid_bits_per_character', '6');
    session_name(SESION_NOMBRE);
    session_set_cookie_params(parametros_cookie());
    session_start();

    $ultima = $_SESSION['ultima_actividad'] ?? null;
    if ($ultima !== null && time() - $ultima > SESION_INACTIVIDAD_SEG) {
        cerrar_sesion();
        session_start();
    }
    $_SESSION['ultima_actividad'] = time();
}

/** Llamar justo después de autenticar: un ID nuevo invalida cualquier ID previo (fijación). */
function abrir_sesion_de_cuenta(int $cuentaId): void
{
    iniciar_sesion();
    session_regenerate_id(true);
    $_SESSION = [
        'cuenta_id'        => $cuentaId,
        'perfil_id'        => null,        // se elige con seleccionar_perfil.php
        'ultima_actividad' => time(),
    ];
}

/** Vacía la sesión, borra la cookie en el navegador y destruye el archivo de sesión. */
function cerrar_sesion(): void
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        iniciar_sesion();
    }
    $_SESSION = [];
    $p = parametros_cookie();
    setcookie(session_name(), '', [
        'expires' => time() - 3600, 'path' => $p['path'],
        'secure' => $p['secure'], 'httponly' => true, 'samesite' => 'Strict',
    ]);
    session_destroy();
}

/** Devuelve el cuenta_id de la sesión o responde 401. Comprueba que la cuenta siga existiendo. */
function requerir_cuenta(): int
{
    iniciar_sesion();
    $cuentaId = $_SESSION['cuenta_id'] ?? null;
    if (!is_int($cuentaId)) {
        responder_error(401, 'Inicia sesión');
    }
    $s = conexion()->prepare('SELECT 1 FROM cuentas WHERE id = ?');
    $s->execute([$cuentaId]);
    if (!$s->fetchColumn()) {
        cerrar_sesion();
        responder_error(401, 'Inicia sesión');
    }
    return $cuentaId;
}

/** Acepta un entero positivo (o un string de solo dígitos); si no, responde 400. */
function leer_perfil_id(mixed $valor): int
{
    if (is_int($valor) && $valor > 0) {
        return $valor;
    }
    if (is_string($valor) && ctype_digit($valor) && strlen($valor) <= 10 && (int)$valor > 0) {
        return (int)$valor;
    }
    responder_error(400, 'perfil_id inválido');
}

function perfil_es_de_cuenta(int $perfilId, int $cuentaId): bool
{
    $s = conexion()->prepare('SELECT 1 FROM perfiles WHERE id = ? AND cuenta_id = ?');
    $s->execute([$perfilId, $cuentaId]);
    return (bool)$s->fetchColumn();
}

/**
 * AUTORIZACIÓN: todo endpoint que reciba un perfil_id del cliente lo pasa por aquí.
 * Si el perfil no existe o es de otra cuenta, responde 403 (la misma respuesta en
 * los dos casos, para no revelar qué IDs existen).
 */
function requerir_perfil_propio(mixed $perfilIdCliente): array
{
    $cuentaId = requerir_cuenta();
    $perfilId = leer_perfil_id($perfilIdCliente);
    if (!perfil_es_de_cuenta($perfilId, $cuentaId)) {
        responder_error(403, 'Ese perfil no pertenece a tu cuenta');
    }
    return [$cuentaId, $perfilId];
}

/**
 * Perfil activo de la sesión (para buscar, dar likes y recomendar). El perfil_id
 * sale SIEMPRE de la sesión, nunca de la petición. Se vuelve a comprobar en la BD
 * porque el perfil pudo borrarse desde otra sesión.
 */
function requerir_perfil_activo(): int
{
    $cuentaId = requerir_cuenta();
    $perfilId = $_SESSION['perfil_id'] ?? null;
    if (!is_int($perfilId) || !perfil_es_de_cuenta($perfilId, $cuentaId)) {
        $_SESSION['perfil_id'] = null;
        responder_error(409, 'Elige un perfil', ['requiere' => 'perfil']);
    }
    return $perfilId;
}
