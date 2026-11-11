<?php
// lib/documentos.php — orígenes válidos e hidratación de documentos (contenido público).
declare(strict_types=1);

const ORIGENES_VALIDOS = ['ejercicios', 'articulos'];

/**
 * Recibe [['doc_id'=>..,'origen'=>..], ...] y devuelve ['origen:id' => tarjeta].
 * Una consulta preparada por origen (antes había una por documento, y sin preparar).
 */
function hidratar_documentos(PDO $db, array $refs): array
{
    $ids = ['ejercicios' => [], 'articulos' => []];
    foreach ($refs as $r) {
        if (in_array($r['origen'] ?? '', ORIGENES_VALIDOS, true)) {
            $ids[$r['origen']][] = (int)$r['doc_id'];
        }
    }

    $tarjetas = [];
    if ($ids['ejercicios']) {
        $ph = implode(',', array_fill(0, count($ids['ejercicios']), '?'));
        $s = $db->prepare("SELECT id, nombre_es, equipamiento, descripcion_es FROM ejercicios WHERE id IN ($ph)");
        $s->execute($ids['ejercicios']);
        foreach ($s->fetchAll() as $e) {
            $tarjetas['ejercicios:' . $e['id']] = [
                'doc_id' => (int)$e['id'], 'origen' => 'ejercicios', 'tipo' => 'Ejercicios',
                'titulo' => $e['nombre_es'], 'tags' => $e['equipamiento'], 'snippet' => (string)$e['descripcion_es'],
            ];
        }
    }
    if ($ids['articulos']) {
        $ph = implode(',', array_fill(0, count($ids['articulos']), '?'));
        $s = $db->prepare("SELECT id, titulo, etiquetas, contenido FROM articulos WHERE id IN ($ph)");
        $s->execute($ids['articulos']);
        foreach ($s->fetchAll() as $a) {
            $tarjetas['articulos:' . $a['id']] = [
                'doc_id' => (int)$a['id'], 'origen' => 'articulos', 'tipo' => 'Teoría',
                'titulo' => $a['titulo'], 'tags' => explode(',', (string)$a['etiquetas'])[0], 'snippet' => (string)$a['contenido'],
            ];
        }
    }
    return $tarjetas;
}

/** Conjunto 'origen:id' de los likes del perfil (solo de ese perfil). */
function likes_del_perfil(PDO $db, int $perfilId): array
{
    $s = $db->prepare("SELECT origen, doc_id FROM interacciones WHERE perfil_id = ? AND interaccion = 'like'");
    $s->execute([$perfilId]);
    $likes = [];
    foreach ($s->fetchAll() as $f) {
        $likes[$f['origen'] . ':' . $f['doc_id']] = true;
    }
    return $likes;
}
