<?php
// lib/estadisticas.php — registro de eventos y consultas para estadísticas.
//
// Reglas:
// - El registro NUNCA hace fallar la petición: todo pasa por registrar_sin_fallar(), que
//   ante un error guarda solo la clase de la excepción (registrar_fallo) y sigue.
// - Las impresiones se guardan con perfil_id NULL (ver sql/esquema_estadisticas.sql).
// - consultas no guarda el texto original ni el perfil: solo las raíces procesadas.
declare(strict_types=1);

require_once __DIR__ . '/documentos.php';

const TIPOS_EVENTO = ['impresion', 'apertura', 'like'];
const MAX_RAICES_BYTES = 255;     // consultas.raices es VARCHAR(255)
const MAX_VIA = 30;               // consultas.via es VARCHAR(30)

/** Ejecuta $fn; si lanza cualquier error, lo registra sin datos y devuelve false. */
function registrar_sin_fallar(callable $fn): bool
{
    try {
        $fn();
        return true;
    } catch (Throwable $e) {
        registrar_fallo($e);
        return false;
    }
}

/**
 * Raíces sin repetir, en orden alfabético y unidas por espacio. Se ordenan para no
 * conservar el orden de las palabras de la frase original. Si no caben, se cortan en
 * una raíz completa.
 */
function normalizar_raices(array $raices): string
{
    $limpias = [];
    foreach ($raices as $r) {
        if (is_string($r) && ($r = trim($r)) !== '') {
            $limpias[$r] = true;
        }
    }
    $limpias = array_keys($limpias);
    sort($limpias, SORT_STRING);

    $texto = '';
    foreach ($limpias as $r) {
        $siguiente = $texto === '' ? $r : "$texto $r";
        if (strlen($siguiente) > MAX_RAICES_BYTES) {   // bytes >= caracteres: nunca se pasa
            break;
        }
        $texto = $siguiente;
    }
    return $texto;
}

/** Una fila en consultas. No recibe ni guarda el texto original ni el perfil. */
function registrar_consulta(PDO $db, array $raices, ?string $via, int $nResultados): void
{
    $texto = normalizar_raices($raices);
    if ($texto === '') {
        return;
    }
    $via = is_string($via) && $via !== '' ? mb_substr($via, 0, MAX_VIA, 'UTF-8') : null;
    $db->prepare('INSERT INTO consultas (raices, via, n_resultados) VALUES (?, ?, ?)')
       ->execute([$texto, $via, max(0, $nResultados)]);
}

/**
 * Inserta varios eventos del mismo tipo con UN solo INSERT múltiple.
 * $refs = [['doc_id'=>..,'origen'=>..], ...]; se descartan las referencias inválidas.
 * Las impresiones se guardan siempre sin perfil.
 */
function registrar_eventos(PDO $db, string $tipo, array $refs, ?int $perfilId): void
{
    if (!in_array($tipo, TIPOS_EVENTO, true)) {
        throw new InvalidArgumentException('tipo de evento inválido');
    }
    if ($tipo === 'impresion') {
        $perfilId = null;
    }
    $filas = [];
    $valores = [];
    foreach ($refs as $r) {
        $origen = $r['origen'] ?? '';
        $docId = (int)($r['doc_id'] ?? 0);
        if (in_array($origen, ORIGENES_VALIDOS, true) && $docId > 0) {
            $filas[] = '(?, ?, ?, ?)';
            array_push($valores, $perfilId, $tipo, $origen, $docId);
        }
    }
    if (!$filas) {
        return;
    }
    $db->prepare('INSERT INTO eventos (perfil_id, tipo, origen, doc_id) VALUES ' . implode(',', $filas))
       ->execute($valores);
}
