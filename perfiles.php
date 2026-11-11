<?php
// perfiles.php — perfiles de la cuenta de la sesión (máximo 4).
//   GET                                          -> listar
//   POST JSON {"accion":"crear", "nombre":"..."} -> crear
//   POST JSON {"accion":"eliminar", "perfil_id":N} -> eliminar (borra su historial en cascada)
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

const PERFILES_MAX = 4;

function listar_perfiles(int $cuentaId): array
{
    $s = conexion()->prepare('SELECT id, nombre FROM perfiles WHERE cuenta_id = ? ORDER BY id');
    $s->execute([$cuentaId]);
    return array_map(fn($p) => ['id' => (int)$p['id'], 'nombre' => $p['nombre']], $s->fetchAll());
}

function respuesta_lista(int $cuentaId, int $codigo = 200): never
{
    responder([
        'status'          => 'success',
        'perfiles'        => listar_perfiles($cuentaId),
        'perfil_activo'   => $_SESSION['perfil_id'] ?? null,
        'maximo'          => PERFILES_MAX,
    ], $codigo);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    respuesta_lista(requerir_cuenta());
}

$datos = leer_json_post();
$accion = $datos['accion'] ?? '';

if ($accion === 'crear') {
    $cuentaId = requerir_cuenta();
    $nombre = trim((string)preg_replace('/\s+/u', ' ', (string)($datos['nombre'] ?? '')));
    if (!preg_match('/^[\p{L}\p{N}][\p{L}\p{M}\p{N} ._\-]{0,39}$/u', $nombre)) {
        responder_error(422, 'Nombre de perfil inválido (1 a 40 letras, números, espacio . _ -)');
    }

    $db = conexion();
    $db->beginTransaction();
    try {
        // Bloquea la fila de la cuenta: dos peticiones simultáneas no pueden pasar
        // las dos el conteo y dejar 5 perfiles (el trigger es la segunda barrera).
        $db->prepare('SELECT id FROM cuentas WHERE id = ? FOR UPDATE')->execute([$cuentaId]);
        $s = $db->prepare('SELECT COUNT(*) FROM perfiles WHERE cuenta_id = ?');
        $s->execute([$cuentaId]);
        if ((int)$s->fetchColumn() >= PERFILES_MAX) {
            $db->rollBack();
            responder_error(409, 'Ya tienes ' . PERFILES_MAX . ' perfiles');
        }
        $db->prepare('INSERT INTO perfiles (cuenta_id, nombre) VALUES (?, ?)')->execute([$cuentaId, $nombre]);
        $db->commit();
    } catch (PDOException $e) {
        if ($db->inTransaction()) {
            $db->rollBack();
        }
        $sqlstate = $e->errorInfo[0] ?? '';
        if (($e->errorInfo[1] ?? 0) === 1062) {
            responder_error(409, 'Ya tienes un perfil con ese nombre');
        }
        if ($sqlstate === '45000') {               // trigger trg_perfiles_max4
            responder_error(409, 'Ya tienes ' . PERFILES_MAX . ' perfiles');
        }
        throw $e;
    }
    respuesta_lista($cuentaId, 201);
}

if ($accion === 'eliminar') {
    [$cuentaId, $perfilId] = requerir_perfil_propio($datos['perfil_id'] ?? null);   // 403 si es ajeno
    // cuenta_id también en el DELETE: aunque la comprobación anterior fallara, nunca
    // se podría borrar un perfil de otra cuenta.
    conexion()->prepare('DELETE FROM perfiles WHERE id = ? AND cuenta_id = ?')->execute([$perfilId, $cuentaId]);
    if (($_SESSION['perfil_id'] ?? null) === $perfilId) {
        $_SESSION['perfil_id'] = null;
    }
    respuesta_lista($cuentaId);
}

responder_error(400, 'Acción desconocida');
