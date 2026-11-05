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
    // NUEVA CAPA: EXTRACCIÓN DEL GRAFO DE CONOCIMIENTO (EL EFECTO DISNEY)
    // =========================================================================
    // Aquí es donde Python busca la Serendipia y los saltos hacia la Teoría
    $comando_grafo = "python scripts_py/motor_grafos.py " . escapeshellarg($busquedaBruta);
    $respuesta_grafo = json_decode(shell_exec($comando_grafo), true);

    $articulo_serendipia = null; // Aquí guardaremos el artículo teórico recomendado

    if (isset($respuesta_grafo['status']) && $respuesta_grafo['status'] === 'success') {
        $datos_salto = $respuesta_grafo['salto_semantico'];
        // Leemos 'query_teorica' que es como lo definimos en Python
        $tags_teoricos = $datos_salto['query_teorica'];
        
        // Convertimos los tags en un array para buscar en la base de datos de artículos
        $palabras_clave = explode(" ", $tags_teoricos);
        $condiciones_sql = [];
        foreach ($palabras_clave as $palabra) {
            $condiciones_sql[] = "etiquetas LIKE " . $conexion->quote("%" . trim($palabra) . "%");
        }
        
        // Hacemos una búsqueda EXCLUSIVA en tu tabla de artículos cruzando el conocimiento
        // Unimos con OR para traer el artículo que más encaje con el salto
        $sql_teoria = "SELECT id, titulo, contenido, etiquetas FROM articulos WHERE " . implode(" OR ", $condiciones_sql) . " LIMIT 1";
        $stmt_teoria = $conexion->query($sql_teoria);
        $articulo_db = $stmt_teoria->fetch(PDO::FETCH_ASSOC);
        
        if ($articulo_db) {
            $articulo_serendipia = [
                'arbol_origen' => "Práctico/Anatomía",
                'arbol_destino' => $datos_salto['arbol_destino'],
                'razon_algoritmica' => $datos_salto['razon'],
                'doc_id' => $articulo_db['id'],
                'origen' => 'articulos',
                'tipo' => 'Teoría',
                'titulo' => $articulo_db['titulo'],
                'snippet' => substr($articulo_db['contenido'], 0, 150) . "...",
                'tags' => explode(',', $articulo_db['etiquetas'])[0],
                // Como es una sugerencia directa del grafo, no tiene un score matemático como tal, 
                // le ponemos uno simbólico alto o lo indicamos como 'Serendipia'
                'score' => 'Salto Semántico' 
            ];
        }
    }


    // =========================================================================
    // CAPA ORIGINAL: MOTOR TF-IDF (Búsqueda Exacta en Índice Inverso)
    // =========================================================================

    // 2. Ejecutar script de Python para obtener las raíces (Stemming) de la búsqueda original
    $comando_stem = "python scripts_py/stem_query.py " . escapeshellarg($busquedaBruta);
    $raicesString = shell_exec($comando_stem);
    $raices = array_filter(explode(' ', trim($raicesString)));

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
        'descubrimiento' => $articulo_serendipia // La recomendación sorpresa del Grafo
    ]);

} catch(Exception $e) {
    echo json_encode(["status" => "error", "mensaje" => $e->getMessage()]);
}
?>