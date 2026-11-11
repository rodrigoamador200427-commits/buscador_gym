<?php
// lib/intentos.php — límite de intentos de inicio de sesión.
//
// Se bloquea por correo (5 fallos en 15 min) y por IP (20 fallos en 15 min).
// El correo se guarda como SHA-256, no en claro. Un login correcto borra los
// fallos de ese correo.
declare(strict_types=1);

const INTENTOS_MAX_POR_CORREO = 5;
const INTENTOS_MAX_POR_IP = 20;
const INTENTOS_VENTANA_MIN = 15;

function hash_correo(string $correoNormalizado): string
{
    return hash('sha256', $correoNormalizado, true);
}

function ip_cliente_binaria(): string
{
    // Solo REMOTE_ADDR: X-Forwarded-For lo controla el cliente y permitiría evadir el límite.
    $bin = @inet_pton($_SERVER['REMOTE_ADDR'] ?? '');
    return $bin === false ? str_repeat("\0", 4) : $bin;
}

function login_bloqueado(PDO $db, string $correoHash, string $ip): bool
{
    $s = $db->prepare(
        'SELECT
            (SELECT COUNT(*) FROM intentos_login
              WHERE correo_hash = ? AND exito = 0 AND creado_en > NOW() - INTERVAL ? MINUTE) AS por_correo,
            (SELECT COUNT(*) FROM intentos_login
              WHERE ip = ? AND exito = 0 AND creado_en > NOW() - INTERVAL ? MINUTE) AS por_ip');
    $s->execute([$correoHash, INTENTOS_VENTANA_MIN, $ip, INTENTOS_VENTANA_MIN]);
    $f = $s->fetch();
    return (int)$f['por_correo'] >= INTENTOS_MAX_POR_CORREO || (int)$f['por_ip'] >= INTENTOS_MAX_POR_IP;
}

function registrar_intento(PDO $db, string $correoHash, string $ip, bool $exito): void
{
    $db->prepare('INSERT INTO intentos_login (correo_hash, ip, exito) VALUES (?, ?, ?)')
       ->execute([$correoHash, $ip, $exito ? 1 : 0]);
    if ($exito) {
        $db->prepare('DELETE FROM intentos_login WHERE correo_hash = ? AND exito = 0')->execute([$correoHash]);
    }
    // Purga ocasional: no guardar intentos más de 24 h
    if (random_int(1, 50) === 1) {
        $db->exec('DELETE FROM intentos_login WHERE creado_en < NOW() - INTERVAL 1 DAY');
    }
}
