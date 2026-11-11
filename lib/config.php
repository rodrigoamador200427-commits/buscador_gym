<?php
// lib/config.php — carga la configuración con secretos (fuera de Git).
declare(strict_types=1);

/**
 * Devuelve la configuración como array [app, db, cifrado].
 *
 * Qué archivo se carga lo decide SOLO el entorno del proceso (variable
 * BUSCADOR_ENTORNO=pruebas, que ponen los scripts de prueba), nunca la petición
 * HTTP. Además se valida que el entorno y el nombre de la BD sean coherentes,
 * para que una prueba no pueda tocar la base real ni al revés.
 */
function config(): array
{
    static $config = null;
    if ($config !== null) {
        return $config;
    }

    $tipo = getenv('BUSCADOR_ENTORNO') === 'pruebas' ? 'test' : 'local';
    $ruta = dirname(__DIR__) . "/config/config.$tipo.ini.php";
    if (!is_readable($ruta)) {
        throw new RuntimeException("Falta config/config.$tipo.ini.php (copia config.example.ini.php)");
    }

    $c = parse_ini_file($ruta, true, INI_SCANNER_RAW);
    if (!is_array($c) || !isset($c['app']['entorno'], $c['db']['nombre'], $c['cifrado']['aes_clave'])) {
        throw new RuntimeException('Configuración incompleta');
    }

    $entorno = $c['app']['entorno'];
    $esBdPrueba = str_ends_with($c['db']['nombre'], '_test');
    if ($tipo === 'test' && ($entorno !== 'pruebas' || !$esBdPrueba)) {
        throw new RuntimeException('La configuración de pruebas debe usar entorno=pruebas y una BD *_test');
    }
    if ($tipo === 'local' && ($entorno === 'pruebas' || $esBdPrueba)) {
        throw new RuntimeException('La configuración real no puede apuntar a una BD de pruebas');
    }

    $clave = base64_decode((string)$c['cifrado']['aes_clave'], true);
    if ($clave === false || strlen($clave) !== 32) {
        throw new RuntimeException('aes_clave debe ser 32 bytes en base64');
    }
    $c['cifrado']['aes_clave_bin'] = $clave;

    return $config = $c;
}
