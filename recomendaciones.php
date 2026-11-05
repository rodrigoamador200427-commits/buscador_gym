<?php
// recomendaciones.php
header('Content-Type: application/json; charset=utf-8');
error_reporting(0); // Evitar que PHP imprima HTML (Warnings) que rompan el JSON

try {
    $conexion = new PDO("mysql:host=localhost;dbname=gym_buscador;charset=utf8", "root", "");
    
    // 1. Ejecutar Python capturando también los errores de la terminal (2>&1)
    $comando = "python scripts_py/recommender.py 2>&1";
    $json_python = shell_exec($comando);
    
    if (!$json_python) {
        echo json_encode(["status" => "error", "mensaje" => "Error: El script de Python no devolvió ninguna respuesta."]);
        exit;
    }

    // 2. Extraer solo el JSON (por si Python imprimió advertencias de NLTK antes)
    $json_str = trim($json_python);
    $inicio_json = strpos($json_str, '{');
    if ($inicio_json !== false && $inicio_json > 0) {
        $json_str = substr($json_str, $inicio_json);
    }

    $datos = json_decode($json_str, true);

    // Si el JSON se rompió, devolver el error exacto al frontend
    if (json_last_error() !== JSON_ERROR_NONE) {
        echo json_encode([
            "status" => "error", 
            "mensaje" => "Python no devolvió un JSON válido.", 
            "python_output" => $json_python
        ]);
        exit;
    }

    // Si es un usuario nuevo (Cold Start) o si Python reporta error interno
    if (isset($datos['status']) && $datos['status'] != 'success') {
        echo json_encode($datos);
        exit;
    }

    // 3. Hidratar las recomendaciones
    $resultados_completos = [];
    
    if (isset($datos['recomendaciones']) && is_array($datos['recomendaciones'])) {
        foreach ($datos['recomendaciones'] as $rec) {
            $id = $rec['doc_id'];
            $origen = $rec['origen'];
            $similitud = $rec['similitud']; 
            
            if ($origen === 'ejercicios') {
                $stmt = $conexion->query("SELECT nombre_es, equipamiento, descripcion_es FROM ejercicios WHERE id = $id");
                $data = $stmt->fetch(PDO::FETCH_ASSOC);
                if($data) {
                    $resultados_completos[] = [
                        'doc_id' => $id,
                        'origen' => $origen,
                        'tipo' => 'Ejercicios',
                        'titulo' => $data['nombre_es'],
                        'tags' => $data['equipamiento'],
                        'snippet' => $data['descripcion_es'],
                        'score' => "Similitud: " . round($similitud * 100, 1) . "%"
                    ];
                }
            } 
            elseif ($origen === 'articulos') {
                $stmt = $conexion->query("SELECT titulo, etiquetas, contenido FROM articulos WHERE id = $id");
                $data = $stmt->fetch(PDO::FETCH_ASSOC);
                if($data) {
                    $resultados_completos[] = [
                        'doc_id' => $id,
                        'origen' => $origen,
                        'tipo' => 'Teoría',
                        'titulo' => $data['titulo'],
                        'tags' => explode(',', $data['etiquetas'])[0],
                        'snippet' => $data['contenido'],
                        'score' => "Similitud: " . round($similitud * 100, 1) . "%"
                    ];
                }
            }
        }
    }

    // 4. Devolver JSON listo para la interfaz
    echo json_encode([
        "status" => "success",
        "perfil_semantico" => $datos['perfil_semantico'] ?? [],
        "recomendaciones" => $resultados_completos
    ]);

} catch(Exception $e) {
    echo json_encode(["status" => "error", "mensaje" => $e->getMessage()]);
}
?>