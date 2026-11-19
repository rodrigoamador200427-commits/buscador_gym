<?php
// etiquetas.php — GET [?tipo=musculo|equipamiento|nivel|modalidad|tema].
// Catálogo de etiquetas con su conteo de documentos. Exige sesión (cualquier cuenta); no usa perfil.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

requerir_cuenta();          // 401 sin sesión
session_write_close();

const TIPOS_ETIQUETA = ['musculo', 'equipamiento', 'nivel', 'modalidad', 'tema'];

$tipo = $_GET['tipo'] ?? null;
if ($tipo !== null && !in_array($tipo, TIPOS_ETIQUETA, true)) {
    responder_error(422, 'tipo inválido');
}

$sql = "SELECT e.id, e.nombre_visible AS nombre, e.tipo, COUNT(de.etiqueta_id) AS n
        FROM etiquetas e LEFT JOIN documento_etiquetas de ON de.etiqueta_id = e.id"
     . ($tipo !== null ? ' WHERE e.tipo = ?' : '')
     . " GROUP BY e.id, e.nombre_visible, e.tipo
        ORDER BY FIELD(e.tipo, 'musculo', 'equipamiento', 'nivel', 'modalidad', 'tema'), n DESC, e.nombre_visible";
$s = conexion()->prepare($sql);
$s->execute($tipo !== null ? [$tipo] : []);

responder(['status' => 'success', 'etiquetas' => array_map(fn($f) => [
    'id' => (int)$f['id'], 'nombre' => $f['nombre'], 'tipo' => $f['tipo'], 'n' => (int)$f['n'],
], $s->fetchAll())]);
