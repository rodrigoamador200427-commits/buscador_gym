<?php
// detalle.php — GET ?origen=ejercicios|articulos&doc_id=N. Detalle de una tarjeta:
// texto completo, todas las etiquetas, su ruta en cada árbol, si el PERFIL ACTIVO le dio
// "me gusta" y hasta 4 documentos relacionados (por etiquetas en común).
// El perfil sale solo de la sesión. La apertura se registra aparte (registrar_evento.php).
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/documentos.php';

$perfilId = requerir_perfil_activo();          // 401 sin sesión, 409 sin perfil elegido
session_write_close();

[$docId, $origen] = leer_ref_documento($_GET); // 422 si origen o doc_id no son válidos

$db = conexion();
$doc = hidratar_documentos($db, [['doc_id' => $docId, 'origen' => $origen]], true)["$origen:$docId"] ?? null;
if ($doc === null) {
    responder_error(404, 'Documento inexistente');
}

$s = $db->prepare("SELECT 1 FROM interacciones WHERE perfil_id = ? AND origen = ? AND doc_id = ? AND interaccion = 'like'");
$s->execute([$perfilId, $origen, $docId]);
$doc['liked'] = (bool)$s->fetchColumn();
$doc['ruta'] = ruta_documento($db, $origen, $docId);          // la principal (compatibilidad)
$doc['rutas'] = rutas_documento($db, $origen, $docId);        // una por árbol

$rel = documentos_relacionados($db, $origen, $docId, 4);
$tarjetas = hidratar_documentos($db, $rel);
$relacionados = [];
foreach ($rel as $r) {
    $t = $tarjetas[$r['origen'] . ':' . $r['doc_id']] ?? null;
    if ($t) {
        $relacionados[] = $t + ['comparte' => $r['comparte']];
    }
}

responder(['status' => 'success', 'documento' => $doc, 'relacionados' => $relacionados]);
