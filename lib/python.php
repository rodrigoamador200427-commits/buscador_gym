<?php
// lib/python.php — ejecutar los scripts de scripts_py/ y leer su JSON.
declare(strict_types=1);

/**
 * Ejecuta scripts_py/<script> con argumentos escapados y devuelve el JSON decodificado,
 * o null si falla. stderr se descarta: puede traer trazas con datos de la consulta, y
 * no debe acabar ni en la respuesta ni en los logs. La salida cruda NUNCA se devuelve
 * al cliente (antes salía en `python_output` y `debug_motor`).
 */
function ejecutar_python(string $script, array $args = []): ?array
{
    if (!preg_match('/^[a-z_]+\.py$/', $script)) {
        throw new InvalidArgumentException('Nombre de script no permitido');
    }
    $cmd = 'python ' . escapeshellarg(dirname(__DIR__) . '/scripts_py/' . $script);
    foreach ($args as $a) {
        $cmd .= ' ' . escapeshellarg((string)$a);
    }
    $cmd .= PHP_OS_FAMILY === 'Windows' ? ' 2>NUL' : ' 2>/dev/null';

    $salida = shell_exec($cmd);
    if (!is_string($salida)) {
        return null;
    }
    // Si alguna librería imprime algo antes del JSON (p. ej. NLTK), se salta hasta la primera '{'
    $inicio = strpos($salida, '{');
    $datos = $inicio === false ? null : json_decode(substr($salida, $inicio), true);
    return is_array($datos) ? $datos : null;
}
