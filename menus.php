<?php
// menus.php — datos para los menús A+B (contenido público, no usa perfil)
//   ?accion=catalogo                       -> músculos, temas y puentes (Python)
//   ?accion=docs&m=<grupo_id>&ids=1,2,3    -> artículos puente + ejercicios del músculo (MySQL)
//   ?accion=cruce&a=<árbol>&x=<clave>&b=<árbol>&y=<clave>
//                                          -> documentos de dos nodos de dos árboles cualesquiera
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

const MAX_ARTICULOS_CRUCE = 30;
const MAX_EJERCICIOS_CRUCE = 12;

if ($accion === 'cruce') {
    // Árboles contra lista blanca; las claves se validan contra el catálogo en Python (aquí solo forma y largo)
    $a = (string)($_GET['a'] ?? '');
    $b = (string)($_GET['b'] ?? '');
    $x = (string)($_GET['x'] ?? '');
    $y = (string)($_GET['y'] ?? '');
    if (!in_array($a, ARBOLES_ACTIVOS, true) || !in_array($b, ARBOLES_ACTIVOS, true) || $a === $b
        || !preg_match('/^[a-z0-9 ]{1,60}$/', $x) || !preg_match('/^[a-z0-9 ]{1,60}$/', $y)) {
        responder_error(422, 'Árbol o concepto inválido');
    }
    $r = ejecutar_python('puente_arboles.py', [$a, $x, $b, $y]);
    if ($r === null) {
        $ref = registrar_fallo(new RuntimeException('puente_arboles.py sin JSON válido'));
        responder_error(502, 'No se pudo calcular el cruce', ['ref' => $ref]);
    }
    if (($r['status'] ?? '') !== 'success') {
        responder_error(404, 'Ese cruce no existe');
    }
    $porOrigen = ['articulos' => [], 'ejercicios' => []];
    foreach ($r['documentos'] ?? [] as $d) {
        if (is_array($d) && isset($porOrigen[$d[0] ?? ''])) {
            $porOrigen[$d[0]][] = (int)$d[1];
        }
    }
    $refs = [];
    foreach (array_slice($porOrigen['articulos'], 0, MAX_ARTICULOS_CRUCE) as $id) {
        $refs[] = ['doc_id' => $id, 'origen' => 'articulos'];
    }
    foreach (array_slice($porOrigen['ejercicios'], 0, MAX_EJERCICIOS_CRUCE) as $id) {
        $refs[] = ['doc_id' => $id, 'origen' => 'ejercicios'];
    }
    // Como siempre en músculo x tema (los ejercicios no entran en Temas): se muestran también unos
    // ejercicios del músculo para no dejar la mitad de la pantalla vacía
    $hayEjercicios = (bool)$porOrigen['ejercicios'];
    $claveMusculo = $a === 'anatomia' ? $x : ($b === 'anatomia' ? $y : '');
    if (!$hayEjercicios && ctype_digit($claveMusculo) && $porOrigen['articulos']) {
        $s = $conexion->prepare('SELECT id FROM ejercicios WHERE grupo_id = ? ORDER BY id LIMIT 6');
        $s->execute([(int)$claveMusculo]);
        foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $id) {
            $refs[] = ['doc_id' => (int)$id, 'origen' => 'ejercicios'];
        }
    }
    $tarjetas = hidratar_documentos($conexion, $refs);
    $articulos = $ejercicios = [];
    foreach ($refs as $ref) {
        $t = $tarjetas[$ref['origen'] . ':' . $ref['doc_id']] ?? null;
        if ($t) {
            if ($ref['origen'] === 'articulos') {
                $articulos[] = $t;
            } else {
                $ejercicios[] = $t;
            }
        }
    }
    responder(['status' => 'success', 'nodos' => nodos_de_descubrimiento($r['nodos'] ?? []),
               'total_articulos' => count($porOrigen['articulos']), 'total_ejercicios' => count($porOrigen['ejercicios']),
               'ejercicios_del_musculo' => !$hayEjercicios,   // los ejercicios son los del músculo, no del cruce
               'articulos' => $articulos, 'ejercicios' => $ejercicios]);
}

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
