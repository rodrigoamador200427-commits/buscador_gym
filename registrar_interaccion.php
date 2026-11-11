<?php
// registrar_interaccion.php — POST JSON {doc_id, origen}. Alterna el like del PERFIL ACTIVO.
// El perfil sale de la sesión; si el cliente manda un perfil_id, se ignora.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/documentos.php';

$datos = leer_json_post();
$perfilId = requerir_perfil_activo();

$origen = $datos['origen'] ?? '';
$docId = $datos['doc_id'] ?? null;
if (!in_array($origen, ORIGENES_VALIDOS, true)              // lista blanca: cierra la inyección de segundo orden
    || !(is_int($docId) || (is_string($docId) && ctype_digit($docId))) || (int)$docId <= 0) {
    responder_error(422, 'doc_id u origen inválido');
}
$docId = (int)$docId;

$db = conexion();
if (!hidratar_documentos($db, [['doc_id' => $docId, 'origen' => $origen]])) {
    responder_error(404, 'Documento inexistente');
}

// Alternar: si había like se quita; si no, se crea (el índice único evita duplicados)
$del = $db->prepare("DELETE FROM interacciones WHERE perfil_id = ? AND origen = ? AND doc_id = ? AND interaccion = 'like'");
$del->execute([$perfilId, $origen, $docId]);
if ($del->rowCount() > 0) {
    responder(['status' => 'removed']);
}
$db->prepare("INSERT IGNORE INTO interacciones (perfil_id, doc_id, origen, interaccion, peso) VALUES (?, ?, ?, 'like', 1.0)")
   ->execute([$perfilId, $docId, $origen]);
responder(['status' => 'added']);
