<?php
// lib/cuentas.php — operaciones sobre cuentas.
declare(strict_types=1);

require_once __DIR__ . '/intentos.php';

/**
 * Elimina la cuenta. La BD borra en cascada perfiles -> interacciones. intentos_login
 * no tiene clave foránea (a propósito), así que sus filas se borran aquí por el hash
 * del correo.
 */
function eliminar_cuenta(PDO $db, int $cuentaId, string $correoNormalizado): void
{
    $db->prepare('DELETE FROM cuentas WHERE id = ?')->execute([$cuentaId]);
    $db->prepare('DELETE FROM intentos_login WHERE correo_hash = ?')->execute([hash_correo($correoNormalizado)]);
}
