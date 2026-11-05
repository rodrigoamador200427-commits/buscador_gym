<?php
// registrar_interaccion.php
header('Content-Type: application/json; charset=utf-8');
error_reporting(0); // Añadir esto en la línea 3

// Recibir JSON desde Javascript (Fetch API)
$input = json_decode(file_get_contents("php://input"), true);

if (!isset($input['doc_id']) || !isset($input['origen'])) {
    echo json_encode(["status" => "error", "mensaje" => "Datos incompletos"]);
    exit;
}

$doc_id = intval($input['doc_id']);
$origen = $input['origen'];
$usuario_id = 1; // Usuario por defecto para el proyecto
$interaccion = 'like';
$peso = 1.0;

try {
    $conexion = new PDO("mysql:host=localhost;dbname=gym_buscador;charset=utf8", "root", "");
    
    // Revisar si ya existe el like
    $check = $conexion->prepare("SELECT id FROM interacciones WHERE usuario_id = ? AND doc_id = ? AND origen = ? AND interaccion = ?");
    $check->execute([$usuario_id, $doc_id, $origen, $interaccion]);
    
    if ($check->rowCount() > 0) {
        // Si ya le había dado like, lo borramos (Dislike)
        $del = $conexion->prepare("DELETE FROM interacciones WHERE usuario_id = ? AND doc_id = ? AND origen = ? AND interaccion = ?");
        $del->execute([$usuario_id, $doc_id, $origen, $interaccion]);
        echo json_encode(["status" => "removed"]);
    } else {
        // Si es nuevo, lo insertamos
        $ins = $conexion->prepare("INSERT INTO interacciones (usuario_id, doc_id, origen, interaccion, peso) VALUES (?, ?, ?, ?, ?)");
        $ins->execute([$usuario_id, $doc_id, $origen, $interaccion, $peso]);
        echo json_encode(["status" => "added"]);
    }

} catch(PDOException $e) {
    echo json_encode(["status" => "error", "mensaje" => $e->getMessage()]);
}
?>