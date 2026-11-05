<?php
// menus.php — datos para los menús A+B
//   ?accion=catalogo                       -> músculos, temas y puentes (Python)
//   ?accion=docs&m=<grupo_id>&ids=1,2,3    -> artículos puente + ejercicios del músculo (MySQL)
header('Content-Type: application/json; charset=utf-8');

try {
    $accion = $_GET['accion'] ?? 'catalogo';

    if ($accion === 'catalogo') {
        $salida = shell_exec("python scripts_py/catalogo_arboles.py");
        $datos = json_decode($salida ?? '', true);
        if (!is_array($datos)) {
            echo json_encode(['status' => 'error', 'mensaje' => 'salida no JSON: ' . substr((string)$salida, 0, 300)]);
        } else {
            echo json_encode($datos);
        }
        exit;
    }

    $conexion = new PDO("mysql:host=localhost;dbname=gym_buscador;charset=utf8", "root", "");
    $conexion->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Artículos puente: ids validados como enteros, consulta preparada
    $ids = array_values(array_filter(array_map('intval', explode(',', $_GET['ids'] ?? ''))));
    $articulos = [];
    if ($ids) {
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $s = $conexion->prepare("SELECT id, titulo, etiquetas, contenido FROM articulos WHERE id IN ($ph) ORDER BY id");
        $s->execute($ids);
        foreach ($s->fetchAll(PDO::FETCH_ASSOC) as $a) {
            $articulos[] = ['doc_id' => (int)$a['id'], 'origen' => 'articulos', 'tipo' => 'Teoría',
                            'titulo' => $a['titulo'], 'tags' => explode(',', $a['etiquetas'])[0],
                            'snippet' => mb_substr($a['contenido'], 0, 150) . '...'];
        }
    }

    // Ejercicios del músculo elegido (menú A), orden estable
    $ejercicios = [];
    $gid = (int)($_GET['m'] ?? 0);
    if ($gid > 0) {
        $s = $conexion->prepare("SELECT id, nombre_es, equipamiento, descripcion_es FROM ejercicios WHERE grupo_id = ? ORDER BY id LIMIT 6");
        $s->execute([$gid]);
        foreach ($s->fetchAll(PDO::FETCH_ASSOC) as $e) {
            $ejercicios[] = ['doc_id' => (int)$e['id'], 'origen' => 'ejercicios', 'tipo' => 'Ejercicios',
                             'titulo' => $e['nombre_es'], 'tags' => $e['equipamiento'],
                             'snippet' => mb_substr((string)$e['descripcion_es'], 0, 150) . '...'];
        }
    }

    echo json_encode(['status' => 'success', 'articulos' => $articulos, 'ejercicios' => $ejercicios]);
} catch (Exception $e) {
    echo json_encode(['status' => 'error', 'mensaje' => $e->getMessage()]);
}
