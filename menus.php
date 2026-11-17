<?php
// menus.php — datos para los menús A+B (contenido público, no usa perfil)
//   ?accion=catalogo                       -> músculos, temas y puentes (Python)
//   ?accion=docs&m=<grupo_id>&ids=1,2,3    -> artículos puente + ejercicios del músculo (MySQL)
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/python.php';
require_once __DIR__ . '/lib/documentos.php';

$accion = $_GET['accion'] ?? 'catalogo';

if ($accion === 'catalogo') {
    $datos = ejecutar_python('catalogo_arboles.py');
    if ($datos === null || ($datos['status'] ?? '') !== 'success') {
        $ref = registrar_fallo(new RuntimeException('catalogo_arboles.py sin JSON válido'));
        responder_error(502, 'No se pudo cargar el catálogo', ['ref' => $ref]);
    }
    responder($datos);
}

$conexion = conexion();

// Artículos puente: ids validados como enteros, consulta preparada
$ids = array_values(array_filter(array_map('intval', explode(',', (string)($_GET['ids'] ?? ''))), fn($i) => $i > 0));
$ids = array_slice(array_unique($ids), 0, 100);
sort($ids);
$refs = array_map(fn($i) => ['doc_id' => $i, 'origen' => 'articulos'], $ids);

// Ejercicios del músculo elegido (menú A), orden estable
$gid = (int)($_GET['m'] ?? 0);
if ($gid > 0) {
    $s = $conexion->prepare('SELECT id FROM ejercicios WHERE grupo_id = ? ORDER BY id LIMIT 6');
    $s->execute([$gid]);
    foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $id) {
        $refs[] = ['doc_id' => (int)$id, 'origen' => 'ejercicios'];
    }
}

// Mismas tarjetas que la búsqueda (con metadatos y etiquetas), en el orden de $refs
$tarjetas = hidratar_documentos($conexion, $refs);
$articulos = $ejercicios = [];
foreach ($refs as $r) {
    $t = $tarjetas[$r['origen'] . ':' . $r['doc_id']] ?? null;
    if ($t) {
        if ($r['origen'] === 'articulos') {
            $articulos[] = $t;
        } else {
            $ejercicios[] = $t;
        }
    }
}

responder(['status' => 'success', 'articulos' => $articulos, 'ejercicios' => $ejercicios]);
