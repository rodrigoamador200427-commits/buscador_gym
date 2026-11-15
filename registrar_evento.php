<?php
// registrar_evento.php — POST JSON {doc_id, origen}. Registra la APERTURA del detalle de
// una tarjeta para el PERFIL ACTIVO. El perfil sale de la sesión: un perfil_id (o un
// tipo) enviado en el cuerpo se ignora.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/documentos.php';
require_once __DIR__ . '/lib/estadisticas.php';

$datos = leer_json_post();
$perfilId = requerir_perfil_activo();          // 401 sin sesión, 409 sin perfil elegido
session_write_close();

[$docId, $origen] = leer_ref_documento($datos);   // 422 si origen u doc_id no son válidos

$db = conexion();
if (!hidratar_documentos($db, [['doc_id' => $docId, 'origen' => $origen]])) {
    responder_error(404, 'Documento inexistente');
}

registrar_eventos($db, 'apertura', [['doc_id' => $docId, 'origen' => $origen]], $perfilId);
responder(['status' => 'ok']);
