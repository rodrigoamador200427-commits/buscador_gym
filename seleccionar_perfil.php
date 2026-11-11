<?php
// seleccionar_perfil.php — POST JSON {"perfil_id": N}
// Deja ese perfil como activo en la sesión. A partir de aquí buscar.php,
// registrar_interaccion.php y recomendaciones.php usan SOLO este perfil.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

$datos = leer_json_post();
[, $perfilId] = requerir_perfil_propio($datos['perfil_id'] ?? null);   // 403 si es ajeno

session_regenerate_id(true);       // cambia el contexto de la sesión: ID nuevo
$_SESSION['perfil_id'] = $perfilId;

$s = conexion()->prepare('SELECT nombre FROM perfiles WHERE id = ?');
$s->execute([$perfilId]);
responder(['status' => 'success', 'perfil_activo' => ['id' => $perfilId, 'nombre' => $s->fetchColumn()]]);
