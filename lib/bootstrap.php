<?php
// lib/bootstrap.php — se incluye al inicio de cada endpoint JSON.
declare(strict_types=1);

// Nunca mostrar errores al cliente (php.ini de SHAMP trae display_errors=On);
// se registran en el log sin datos sensibles (ver registrar_fallo).
ini_set('display_errors', '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/respuesta.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/sesion.php';

set_exception_handler(function (Throwable $e): void {
    $ref = registrar_fallo($e);
    responder_error(500, 'Error interno', ['ref' => $ref]);
});

// Que un warning no rompa el JSON ni filtre rutas: se convierte en excepción.
set_error_handler(function (int $nivel, string $msg, string $archivo, int $linea): bool {
    if (!(error_reporting() & $nivel)) {
        return false;
    }
    throw new ErrorException($msg, 0, $nivel, $archivo, $linea);
});
