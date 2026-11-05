<?php
// buscar.php
header('Content-Type: application/json; charset=utf-8');

try {
    $conexion = new PDO("mysql:host=localhost;dbname=gym_buscador;charset=utf8", "root", "");
    
    // 1. Recibir consulta del usuario
    $busquedaBruta = trim($_GET['q'] ?? '');
    if(empty($busquedaBruta)) {
        echo json_encode([]);
        exit;
    }

    // =========================================================================
    // UNA SOLA LLAMADA A PYTHON: raíces de la consulta + descubrimiento por árboles
    // (reemplaza motor_grafos.py y stem_query.py; ya no hay random ni LIKE ... LIMIT 1)
    // =========================================================================
    $salida = shell_exec("python scripts_py/motor_arboles.py " . escapeshellarg($busquedaBruta));
    $motor = json_decode($salida ?? '', true);

    $raices = [];
    $articulo_serendipia = null;
    $debug_motor = null;
    if (!is_array($motor) || ($motor['status'] ?? '') !== 'success') {
        // Si Python falla, lo vemos en la respuesta en vez de quedarnos con 0 resultados mudos
        $debug_motor = is_array($motor) ? ($motor['mensaje'] ?? 'error') : ('salida no JSON: ' . substr((string)$salida, 0, 300));
    }

    if (is_array($motor) && ($motor['status'] ?? '') === 'success') {
        $raices = $motor['raices'] ?? [];
        $d = $motor['descubrimiento'] ?? [];
        $doc = $d['documentos'][0] ?? null;   // ya viene ordenado y es determinista

        if ($doc && $doc['origen'] === 'articulos') {
            $stmt_teoria = $conexion->prepare("SELECT id, titulo, contenido, etiquetas FROM articulos WHERE id = ?");
            $stmt_teoria->execute([(int)$doc['doc_id']]);
            $articulo_db = $stmt_teoria->fetch(PDO::FETCH_ASSOC);
            if ($articulo_db) {
                $articulo_serendipia = [
                    'via' => $d['via'],
                    'arbol_origen' => $d['origen']['ruta_texto'] ?? '',
                    'arbol_destino' => $d['destino']['ruta_texto'] ?? '',
                    'razon_algoritmica' => $d['razon'],
                    'doc_id' => $articulo_db['id'],
                    'origen' => 'articulos',
                    'tipo' => 'Teoría',
                    'titulo' => $articulo_db['titulo'],
                    'snippet' => mb_substr($articulo_db['contenido'], 0, 150) . "...",
                    'tags' => explode(',', $articulo_db['etiquetas'])[0],
                    'score' => 'Salto Semántico'
                ];
            }
        }
    }

    // =========================================================================
    // CAPA ORIGINAL: MOTOR TF-IDF (Búsqueda Exacta en Índice Inverso)
    // =========================================================================

    $resultados_finales = [];

    if(!empty($raices)) {
        // 3. Crear los placeholders para la consulta SQL (ej. ?, ?, ?)
        $placeholders = implode(',', array_fill(0, count($raices), '?'));

        // 4. CONSULTA AL ÍNDICE INVERSO
        $sql_indice = "
            SELECT p.doc_id, p.origen, SUM(p.peso_tfidf) as score
            FROM diccionario d
            JOIN postings p ON d.id = p.termino_id
            WHERE d.termino IN ($placeholders)
            GROUP BY p.doc_id, p.origen
            ORDER BY score DESC
            LIMIT 20
        ";
        
        $stmt = $conexion->prepare($sql_indice);
        $stmt->execute(array_values($raices));
        $resultados_indice = $stmt->fetchAll(PDO::FETCH_ASSOC);

        // 5. Hidratar los resultados y comprobar interacciones ("Likes")
        foreach ($resultados_indice as $res) {
            $id = $res['doc_id'];
            $origen = $res['origen'];
            $score = round($res['score'], 4); 

            // VERIFICACIÓN DE LIKES (Memoria visual de los botones)
            // IMPORTANTE: Si tienes sistema de login, añade 'AND usuario_id = X' a esta consulta
            $check_like = $conexion->prepare("SELECT 1 FROM interacciones WHERE doc_id = ? AND origen = ? LIMIT 1");
            $check_like->execute([$id, $origen]);
            $is_liked = $check_like->fetch() ? true : false;

            if ($origen === 'ejercicios') {
                $s = $conexion->prepare("SELECT nombre_es, equipamiento, descripcion_es FROM ejercicios WHERE id = ?");
                $s->execute([$id]);
                $data = $s->fetch(PDO::FETCH_ASSOC);
                if($data) {
                    $resultados_finales[] = [
                        'doc_id' => $id,           
                        'origen' => $origen,       
                        'tipo' => 'Ejercicios',
                        'titulo' => $data['nombre_es'],
                        'tags' => $data['equipamiento'],
                        'snippet' => $data['descripcion_es'],
                        'score' => $score,
                        'liked' => $is_liked // <-- Estado del corazón
                    ];
                }
            } 
            elseif ($origen === 'articulos') {
                $s = $conexion->prepare("SELECT titulo, etiquetas, contenido FROM articulos WHERE id = ?");
                $s->execute([$id]);
                $data = $s->fetch(PDO::FETCH_ASSOC);
                if($data) {
                    $resultados_finales[] = [
                        'doc_id' => $id,           
                        'origen' => $origen,       
                        'tipo' => 'Teoría',
                        'titulo' => $data['titulo'],
                        'tags' => explode(',', $data['etiquetas'])[0],
                        'snippet' => $data['contenido'],
                        'score' => $score,
                        'liked' => $is_liked
                    ];
                }
            } 
            elseif ($origen === 'alimentos') {
                $s = $conexion->prepare("SELECT nombre_es, calorias_kcal FROM alimentos WHERE id = ?");
                $s->execute([$id]);
                $data = $s->fetch(PDO::FETCH_ASSOC);
                if($data) {
                    $resultados_finales[] = [
                        'doc_id' => $id,
                        'origen' => $origen,
                        'tipo' => 'Nutrición',
                        'titulo' => $data['nombre_es'],
                        'tags' => $data['calorias_kcal'] . ' kcal',
                        'snippet' => 'Información nutricional y macronutrientes del alimento.',
                        'score' => $score,
                        'liked' => $is_liked
                    ];
                }
            }
        }
    }

    // =========================================================================
    // RESPUESTA FINAL AL FRONTEND (HÍBRIDA)
    // =========================================================================
    // Devolvemos el array original pero envuelto en una estructura con metadatos
    echo json_encode([
        'status' => 'success',
        'resultados' => $resultados_finales,     // Lista normal para tu index.html
        'descubrimiento' => $articulo_serendipia, // La recomendación sorpresa del Grafo
        'debug_motor' => $debug_motor
    ]);

} catch(Exception $e) {
    echo json_encode(["status" => "error", "mensaje" => $e->getMessage()]);
}
?>