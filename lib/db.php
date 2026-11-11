<?php
// lib/db.php — única conexión PDO del proyecto (credenciales desde config).
declare(strict_types=1);

function conexion(): PDO
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }
    $db = config()['db'];
    $dsn = sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', $db['host'], $db['nombre']);
    $pdo = new PDO($dsn, $db['usuario'], $db['contrasena'] ?? '', [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_EMULATE_PREPARES   => false,   // consultas preparadas reales en el servidor
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    return $pdo;
}
