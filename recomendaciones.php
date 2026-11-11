<?php
// recomendaciones.php — GET. Recomendaciones del PERFIL ACTIVO de la sesión.
// No acepta perfil_id del cliente: no hay forma de pedir las recomendaciones de otro perfil.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/python.php';
require_once __DIR__ . '/lib/documentos.php';

$perfilId = requerir_perfil_activo();          // 401 sin sesión, 409 sin perfil elegido
session_write_close();                         // no bloquear otras peticiones mientras corre Python

$datos = ejecutar_python('recommender.py', [$perfilId]);
if ($datos === null || !in_array($datos['status'] ?? '', ['success', 'cold_start'], true)) {
    $ref = registrar_fallo(new RuntimeException('recommender.py sin JSON válido'));
    responder_error(502, 'El recomendador no respondió', ['ref' => $ref]);
}
if ($datos['status'] === 'cold_start') {
    responder(['status' => 'cold_start', 'mensaje' => $datos['mensaje'] ?? '']);
}

$recs = $datos['recomendaciones'] ?? [];
$docs = hidratar_documentos(conexion(), $recs);
$resultados = [];
foreach ($recs as $r) {
    $d = $docs[$r['origen'] . ':' . $r['doc_id']] ?? null;
    if ($d) {
        $d['score'] = 'Similitud: ' . round((float)$r['similitud'] * 100, 1) . '%';
        $d['liked'] = false;                   // el recomendador excluye lo que ya tiene like
        $resultados[] = $d;
    }
}

responder([
    'status'           => 'success',
    'perfil_semantico' => $datos['perfil_semantico'] ?? [],
    'recomendaciones'  => $resultados,
]);
