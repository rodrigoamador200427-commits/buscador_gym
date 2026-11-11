<?php
// lib/cifrado.php — AES-256-GCM para campos personales sensibles.
//
// Formato guardado (VARBINARY): version(1) || nonce(12) || tag(16) || texto_cifrado
// - nonce aleatorio por cada valor (nunca se repite con la misma clave).
// - tag GCM: si alguien altera el valor en la BD, descifrar falla.
// - AAD = nombre del campo ("cuentas.nombre"): un valor cifrado no se puede
//   copiar a otra columna y descifrarse como si fuera de ella.
declare(strict_types=1);

const CIFRADO_VERSION = "\x01";
const CIFRADO_ALGORITMO = 'aes-256-gcm';

function cifrar_campo(string $texto, string $campo): string
{
    $nonce = random_bytes(12);
    $tag = '';
    $cifrado = openssl_encrypt($texto, CIFRADO_ALGORITMO, config()['cifrado']['aes_clave_bin'],
        OPENSSL_RAW_DATA, $nonce, $tag, $campo, 16);
    if ($cifrado === false) {
        throw new RuntimeException('No se pudo cifrar');
    }
    return CIFRADO_VERSION . $nonce . $tag . $cifrado;
}

function descifrar_campo(string $blob, string $campo): string
{
    if (strlen($blob) < 29 || $blob[0] !== CIFRADO_VERSION) {
        throw new RuntimeException('Formato cifrado desconocido');
    }
    $texto = openssl_decrypt(substr($blob, 29), CIFRADO_ALGORITMO, config()['cifrado']['aes_clave_bin'],
        OPENSSL_RAW_DATA, substr($blob, 1, 12), substr($blob, 13, 16), $campo);
    if ($texto === false) {
        throw new RuntimeException('Dato cifrado alterado o clave incorrecta');
    }
    return $texto;
}
