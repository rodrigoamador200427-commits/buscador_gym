<?php
// lib/validacion.php — validación de los datos de cuenta.
// Cada validador devuelve null si es válido, o el mensaje de error.
declare(strict_types=1);

function normalizar_correo(string $correo): string
{
    return mb_strtolower(trim($correo), 'UTF-8');
}

function validar_correo(string $correo): ?string
{
    if ($correo === '' || strlen($correo) > 254 || filter_var($correo, FILTER_VALIDATE_EMAIL) === false) {
        return 'Correo inválido';
    }
    return null;
}

/**
 * 10 a 72 bytes (bcrypt, el algoritmo de PASSWORD_DEFAULT, ignora lo que pasa
 * de 72 bytes), con al menos una letra y un dígito, y distinta del correo.
 */
function validar_contrasena(string $contrasena, string $correo): ?string
{
    $bytes = strlen($contrasena);
    if ($bytes < 10) {
        return 'La contraseña debe tener al menos 10 caracteres';
    }
    if ($bytes > 72) {
        return 'La contraseña no puede pasar de 72 bytes';
    }
    if (!preg_match('/\p{L}/u', $contrasena) || !preg_match('/\d/', $contrasena)) {
        return 'La contraseña debe incluir letras y números';
    }
    if (mb_strtolower($contrasena, 'UTF-8') === $correo) {
        return 'La contraseña no puede ser igual al correo';
    }
    return null;
}

/** Normaliza espacios; devuelve el nombre limpio o null si no es válido. */
function limpiar_nombre_completo(string $nombre): ?string
{
    $nombre = trim((string)preg_replace('/\s+/u', ' ', $nombre));
    $largo = mb_strlen($nombre, 'UTF-8');
    if ($largo < 2 || $largo > 100 || !preg_match("/^\p{L}[\p{L}\p{M} '.\-]*$/u", $nombre)) {
        return null;
    }
    return $nombre;
}

/** Fecha exacta AAAA-MM-DD, no futura, edad entre 13 y 120 años. */
function validar_fecha_nacimiento(string $fecha): ?string
{
    $d = DateTimeImmutable::createFromFormat('!Y-m-d', $fecha);
    if ($d === false || $d->format('Y-m-d') !== $fecha) {
        return 'Fecha de nacimiento inválida (AAAA-MM-DD)';
    }
    $edad = $d->diff(new DateTimeImmutable('today'));
    if ($edad->invert === 1 || $edad->y < 13 || $edad->y > 120) {
        return 'La edad debe estar entre 13 y 120 años';
    }
    return null;
}
