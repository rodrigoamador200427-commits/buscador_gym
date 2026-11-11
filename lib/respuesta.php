<?php
// lib/respuesta.php — respuestas JSON, lectura de peticiones y registro de fallos
// sin datos sensibles.
declare(strict_types=1);

function responder(array $datos, int $codigo = 200): never
{
    http_response_code($codigo);
    header('Content-Type: application/json; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Cache-Control: no-store');
    echo json_encode($datos, JSON_UNESCAPED_UNICODE);
    exit;
}

function responder_error(int $codigo, string $mensaje, array $extra = []): never
{
    responder(['status' => 'error', 'mensaje' => $mensaje] + $extra, $codigo);
}

/**
 * Escribe en el log de PHP solo la clase de la excepción, el código SQLSTATE y el
 * archivo:línea, más una referencia aleatoria que también recibe el cliente.
 * NUNCA el mensaje: los de PDO pueden incluir valores, como
 * "Duplicate entry 'correo@...'".
 */
function registrar_fallo(Throwable $e): string
{
    $ref = bin2hex(random_bytes(6));
    $codigo = $e instanceof PDOException ? ($e->errorInfo[0] ?? $e->getCode()) : $e->getCode();
    error_log(sprintf('[buscador_gym] ref=%s %s codigo=%s en %s:%d',
        $ref, get_class($e), (string)$codigo, basename($e->getFile()), $e->getLine()));
    return $ref;
}

/**
 * Exige POST con Content-Type application/json y devuelve el cuerpo como array.
 * Exigir JSON también frena CSRF: un formulario de otro sitio no puede enviar
 * application/json sin una verificación previa de CORS (preflight).
 */
function leer_json_post(int $maxBytes = 8192): array
{
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
        header('Allow: POST');
        responder_error(405, 'Método no permitido');
    }
    $tipo = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
    if ($tipo !== 'application/json') {
        responder_error(415, 'Se espera application/json');
    }
    $cuerpo = file_get_contents('php://input', false, null, 0, $maxBytes + 1);
    if ($cuerpo === false || strlen($cuerpo) > $maxBytes) {
        responder_error(413, 'Petición demasiado grande');
    }
    if (trim($cuerpo) === '') {
        return [];
    }
    $datos = json_decode($cuerpo, true);
    if (!is_array($datos)) {
        responder_error(400, 'JSON inválido');
    }
    return $datos;
}
