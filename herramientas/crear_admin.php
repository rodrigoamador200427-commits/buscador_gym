<?php
// herramientas/crear_admin.php — crea una cuenta de administrador o da el rol a una existente.
//
//   php herramientas/crear_admin.php correo@dominio.com                 (BD real)
//   BUSCADOR_ENTORNO=pruebas php herramientas/crear_admin.php correo    (gym_buscador_test)
//
// Es la ÚNICA forma de obtener el rol 'admin': ningún endpoint web lo escribe.
// Pide la contraseña por consola sin mostrarla (y la pide dos veces). Si la cuenta ya
// existe, solo cambia su rol y conserva su contraseña. Solo CLI; la carpeta además está
// bloqueada por HTTP. Para pruebas automáticas, ADMIN_CONTRASENA evita la pregunta.
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once dirname(__DIR__) . '/lib/config.php';
require_once dirname(__DIR__) . '/lib/db.php';
require_once dirname(__DIR__) . '/lib/cifrado.php';
require_once dirname(__DIR__) . '/lib/validacion.php';

function salir(string $msg, int $codigo = 1): never
{
    fwrite(STDERR, "$msg\n");
    exit($codigo);
}

/** Lee una línea de la consola sin eco. En Windows usa PowerShell; en otros, stty. */
function leer_secreto(string $aviso): string
{
    fwrite(STDOUT, $aviso);
    if (PHP_OS_FAMILY === 'Windows') {
        $ps = 'powershell -NoProfile -Command "$p = Read-Host -AsSecureString; '
            . '[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($p))"';
        $valor = shell_exec($ps);
    } else {
        shell_exec('stty -echo');
        $valor = fgets(STDIN);
        shell_exec('stty echo');
    }
    fwrite(STDOUT, "\n");
    return rtrim((string)$valor, "\r\n");
}

$correo = normalizar_correo((string)($argv[1] ?? ''));
if (($err = validar_correo($correo)) !== null) {
    salir("Uso: php herramientas/crear_admin.php <correo>\n$err");
}

$db = conexion();
$s = $db->prepare('SELECT id, rol FROM cuentas WHERE correo = ?');
$s->execute([$correo]);
$existente = $s->fetch() ?: null;

if ($existente !== null) {
    if ($existente['rol'] === 'admin') {
        echo "La cuenta ya es administradora. Nada que hacer.\n";
        exit(0);
    }
    $db->prepare("UPDATE cuentas SET rol = 'admin' WHERE id = ?")->execute([$existente['id']]);
    echo "La cuenta existente ahora es administradora (conserva su contraseña).\n";
    exit(0);
}

$contrasena = getenv('ADMIN_CONTRASENA') ?: '';
if ($contrasena === '') {
    $contrasena = leer_secreto('Contraseña del administrador (no se muestra): ');
    $repetida = leer_secreto('Repite la contraseña: ');
    if ($contrasena !== $repetida) {
        salir('Las contraseñas no coinciden.');
    }
}
if (($err = validar_contrasena($contrasena, $correo)) !== null) {
    salir($err);
}

// Nombre y fecha de nacimiento son obligatorios en el esquema; una cuenta de
// administrador no participa en las estadísticas, así que llevan valores fijos.
$db->prepare("INSERT INTO cuentas (correo, contrasena_hash, rol, nombre_cifrado, fecha_nac_cifrada)
              VALUES (?, ?, 'admin', ?, ?)")
   ->execute([$correo, password_hash($contrasena, PASSWORD_DEFAULT),
              cifrar_campo('Administrador', 'cuentas.nombre'),
              cifrar_campo('1970-01-01', 'cuentas.fecha_nacimiento')]);

echo 'BD: ' . config()['db']['nombre'] . "\nCuenta de administrador creada: $correo\n";
echo "Entra con ella en index.html y abre admin.php.\n";
