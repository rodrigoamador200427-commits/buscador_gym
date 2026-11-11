<?php
// sesion.php — GET. Estado de la sesión para la interfaz (sin datos sensibles:
// ni nombre completo ni fecha de nacimiento).
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

iniciar_sesion();
$cuentaId = $_SESSION['cuenta_id'] ?? null;
if (!is_int($cuentaId)) {
    responder(['status' => 'success', 'autenticado' => false]);
}

$s = conexion()->prepare('SELECT correo FROM cuentas WHERE id = ?');
$s->execute([$cuentaId]);
$correo = $s->fetchColumn();
if ($correo === false) {             // la cuenta ya no existe
    cerrar_sesion();
    responder(['status' => 'success', 'autenticado' => false]);
}

$perfil = null;
$perfilId = $_SESSION['perfil_id'] ?? null;
if (is_int($perfilId)) {
    $s = conexion()->prepare('SELECT id, nombre FROM perfiles WHERE id = ? AND cuenta_id = ?');
    $s->execute([$perfilId, $cuentaId]);
    $fila = $s->fetch();
    if ($fila) {
        $perfil = ['id' => (int)$fila['id'], 'nombre' => $fila['nombre']];
    } else {
        $_SESSION['perfil_id'] = null;
    }
}

responder(['status' => 'success', 'autenticado' => true, 'correo' => $correo, 'perfil_activo' => $perfil]);
