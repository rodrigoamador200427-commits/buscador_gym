<?php
// menus.php — datos para los menús A+B (contenido público, no usa perfil)
//   ?accion=catalogo                       -> músculos, temas y puentes (Python)
//   ?accion=docs&m=<grupo_id>&ids=1,2,3    -> artículos puente + ejercicios del músculo (MySQL)
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';
require_once __DIR__ . '/lib/python.php';

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
$ids = array_values(array_filter(array_map('intval', explode(',', (string)($_GET['ids'] ?? '')))));
$ids = array_slice($ids, 0, 100);
$articulos = [];
if ($ids) {
    $ph = implode(',', array_fill(0, count($ids), '?'));
    $s = $conexion->prepare("SELECT id, titulo, etiquetas, contenido FROM articulos WHERE id IN ($ph) ORDER BY id");
    $s->execute($ids);
    foreach ($s->fetchAll() as $a) {
        $articulos[] = ['doc_id' => (int)$a['id'], 'origen' => 'articulos', 'tipo' => 'Teoría',
                        'titulo' => $a['titulo'], 'tags' => explode(',', (string)$a['etiquetas'])[0],
                        'snippet' => mb_substr((string)$a['contenido'], 0, 150) . '...'];
    }
}

// Ejercicios del músculo elegido (menú A), orden estable
$ejercicios = [];
$gid = (int)($_GET['m'] ?? 0);
if ($gid > 0) {
    $s = $conexion->prepare("SELECT id, nombre_es, equipamiento, descripcion_es FROM ejercicios WHERE grupo_id = ? ORDER BY id LIMIT 6");
    $s->execute([$gid]);
    foreach ($s->fetchAll() as $e) {
        $ejercicios[] = ['doc_id' => (int)$e['id'], 'origen' => 'ejercicios', 'tipo' => 'Ejercicios',
                         'titulo' => $e['nombre_es'], 'tags' => $e['equipamiento'],
                         'snippet' => mb_substr((string)$e['descripcion_es'], 0, 150) . '...'];
    }
}

responder(['status' => 'success', 'articulos' => $articulos, 'ejercicios' => $ejercicios]);
