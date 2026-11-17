<?php
// buscar.php — GET ?q=... Búsqueda TF-IDF + descubrimiento por árboles, para el PERFIL ACTIVO.
// El perfil solo se usa para marcar los corazones con los likes de ESE perfil.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/python.php';
require_once __DIR__ . '/lib/documentos.php';
require_once __DIR__ . '/lib/estadisticas.php';

$perfilId = requerir_perfil_activo();          // 401 sin sesión, 409 sin perfil elegido
session_write_close();

// 1. Recibir consulta del usuario (limitada para no pasar textos enormes a Python)
$busquedaBruta = trim((string)($_GET['q'] ?? ''));
if ($busquedaBruta === '') {
    responder(['status' => 'success', 'resultados' => [], 'descubrimiento' => null, 'debug_motor' => null]);
}
$busquedaBruta = mb_substr($busquedaBruta, 0, 200, 'UTF-8');

$db = conexion();

// =========================================================================
// UNA SOLA LLAMADA A PYTHON: raíces de la consulta + descubrimiento por árboles
// =========================================================================
$motor = ejecutar_python('motor_arboles.py', [$busquedaBruta]);

$raices = [];
$raicesConsulta = [];
$articulo_serendipia = null;
$debug_motor = null;
if (($motor['status'] ?? '') !== 'success') {
    // Solo un código fijo y una referencia: ni el texto de Python ni la consulta,
    // que pueden traer datos del usuario. El detalle técnico queda en el log (sin datos).
    $debug_motor = ['codigo' => 'motor_no_disponible',
                    'ref' => registrar_fallo(new RuntimeException('motor_arboles.py sin JSON válido'))];
} else {
    $raices = array_values(array_filter($motor['raices'] ?? [], 'is_string'));
    // Para estadísticas: solo las raíces de lo que escribió el usuario, sin la expansión
    $raicesConsulta = array_values(array_filter($motor['raices_consulta'] ?? $raices, 'is_string'));
    $d = $motor['descubrimiento'] ?? [];
    $doc = $d['documentos'][0] ?? null;   // ya viene ordenado y es determinista

    if ($doc && ($doc['origen'] ?? '') === 'articulos') {
        $tarjeta = hidratar_documentos($db, [['doc_id' => (int)$doc['doc_id'], 'origen' => 'articulos']]);
        $a = reset($tarjeta);
        if ($a) {
            $articulo_serendipia = $a + [
                'via' => $d['via'] ?? null,
                'arbol_origen' => $d['origen']['ruta_texto'] ?? '',
                'arbol_destino' => $d['destino']['ruta_texto'] ?? '',
                'origen_ruta' => $d['origen']['ruta'] ?? [],
                'destino_ruta' => $d['destino']['ruta'] ?? [],
                'origen_arbol' => $d['origen']['arbol'] ?? '',
                'destino_arbol' => $d['destino']['arbol'] ?? '',
                'lift' => $d['lift'] ?? null,
                'razon_algoritmica' => $d['razon'] ?? '',
            ];
        }
    }

    // Sin documento que recomendar (sin_interseccion / ninguno): se muestra solo la explicación
    if ($articulo_serendipia === null && !empty($d['razon'])) {
        $articulo_serendipia = ['via' => $d['via'] ?? null, 'razon_algoritmica' => $d['razon'], 'sin_documento' => true];
    }
}

// =========================================================================
// MOTOR TF-IDF (búsqueda exacta en el índice inverso)
// =========================================================================
$resultados_finales = [];
if ($raices) {
    $placeholders = implode(',', array_fill(0, count($raices), '?'));
    $stmt = $db->prepare("
        SELECT p.doc_id, p.origen, SUM(p.peso_tfidf) AS score
        FROM diccionario d
        JOIN postings p ON d.id = p.termino_id
        WHERE d.termino IN ($placeholders)
        GROUP BY p.doc_id, p.origen
        ORDER BY score DESC, p.origen, p.doc_id
        LIMIT 20
    ");
    $stmt->execute($raices);
    $indice = $stmt->fetchAll();

    $docs = hidratar_documentos($db, $indice);
    $likes = likes_del_perfil($db, $perfilId);     // SOLO los likes de este perfil
    foreach ($indice as $res) {
        $clave = $res['origen'] . ':' . $res['doc_id'];
        if (isset($docs[$clave])) {
            $resultados_finales[] = $docs[$clave] + [
                'score' => round((float)$res['score'], 4),
                'liked' => isset($likes[$clave]),
            ];
        }
    }
}

enviar_y_continuar([
    'status' => 'success',
    'resultados' => $resultados_finales,
    'descubrimiento' => $articulo_serendipia,
    'debug_motor' => $debug_motor,
]);

// =========================================================================
// ESTADÍSTICAS (después de responder: no retrasan la búsqueda ni la hacen fallar)
// - consultas: una fila, solo raíces; sin perfil y sin el texto original.
// - eventos: impresiones de lo mostrado (TF-IDF + artículo descubierto), en un
//   solo INSERT múltiple y sin perfil.
// raices = solo las de la consulta, sin la expansión por árboles.
// Sin raíces (motor caído o consulta vacía tras procesarla) no se registra nada.
// =========================================================================
if ($raicesConsulta) {
    registrar_sin_fallar(fn() => registrar_consulta(
        $db, $raicesConsulta, $articulo_serendipia['via'] ?? null, count($resultados_finales)));

    $mostrados = $resultados_finales;
    if (isset($articulo_serendipia['doc_id'])) {
        $mostrados[] = $articulo_serendipia;
    }
    registrar_sin_fallar(fn() => registrar_eventos($db, 'impresion', $mostrados, null));
}
exit;
