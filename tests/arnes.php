<?php
// tests/arnes.php — arnés común de las pruebas HTTP (CLI). Al incluirlo:
// 1. Fuerza BUSCADOR_ENTORNO=pruebas y se niega a seguir si la BD no es *_test o si
//    coincide con la BD real.
// 2. Recrea gym_buscador_test (python scripts_py/tests/bd_prueba.py: contenido sintético).
// 3. Levanta su PROPIO servidor (php -S 127.0.0.1:<puerto libre>) con la config de
//    pruebas: no usa Apache ni la base real.
// Deja definidos $RAIZ, $BASE, $conectada, la clase Cliente, comprobar(), crearPerfil()
// y terminar().
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

putenv('BUSCADOR_ENTORNO=pruebas');
$RAIZ = dirname(__DIR__);
require_once "$RAIZ/lib/config.php";
require_once "$RAIZ/lib/db.php";

function abortar(string $msg): never
{
    fwrite(STDERR, "ABORTADO: $msg\n");
    exit(2);
}

// ----------------------------------------------------------------------------- guardas
$nombreBd = config()['db']['nombre'];                 // config() ya exige entorno=pruebas y *_test
$real = @parse_ini_file("$RAIZ/config/config.local.ini.php", true, INI_SCANNER_RAW);
if (!str_ends_with($nombreBd, '_test') || ($real && ($real['db']['nombre'] ?? null) === $nombreBd)) {
    abortar("me niego a usar la BD '$nombreBd'");
}
$conectada = (string)conexion()->query('SELECT DATABASE()')->fetchColumn();
if (!str_ends_with($conectada, '_test')) {
    abortar("la conexión apunta a '$conectada'");
}

// ----------------------------------------------------------------------------- BD limpia
exec('python ' . escapeshellarg("$RAIZ/scripts_py/tests/bd_prueba.py") . ' 2>&1', $salida, $codigo);
if ($codigo !== 0) {
    abortar('no se pudo preparar la BD de pruebas: ' . implode(' ', $salida));
}

// ----------------------------------------------------------------------------- servidor propio
$s = stream_socket_server('tcp://127.0.0.1:0');
$puerto = (int)substr(strrchr(stream_socket_get_name($s, false), ':'), 1);
fclose($s);
$nulo = PHP_OS_FAMILY === 'Windows' ? 'NUL' : '/dev/null';
$servidor = proc_open([PHP_BINARY, '-S', "127.0.0.1:$puerto", '-t', $RAIZ],
    [0 => ['file', $nulo, 'r'], 1 => ['file', $nulo, 'w'], 2 => ['file', $nulo, 'w']],
    $tuberias, $RAIZ, ['BUSCADOR_ENTORNO' => 'pruebas'] + getenv());
register_shutdown_function(fn() => is_resource($servidor) && proc_terminate($servidor));
for ($i = 0; $i < 50 && !@fsockopen('127.0.0.1', $puerto, $en, $es, 0.1); $i++) {
    usleep(100000);
}
$BASE = "http://127.0.0.1:$puerto";

// ----------------------------------------------------------------------------- cliente HTTP con cookies
final class Cliente
{
    private string $jar;
    public array $setCookie = [];

    public function __construct(private string $base)
    {
        $this->jar = tempnam(sys_get_temp_dir(), 'jar');
    }

    public function __destruct()
    {
        @unlink($this->jar);
    }

    /** Cabeceras de la última respuesta, en minúsculas: ['content-length' => '123', ...] */
    public array $cabeceras = [];

    /** @return array{0:int,1:array} */
    public function pedir(string $ruta, ?array $json = null): array
    {
        return $json === null ? $this->pedirCrudo($ruta) : $this->pedirCrudo($ruta, json_encode($json), 'application/json');
    }

    /** POST con cuerpo y Content-Type arbitrarios (o GET si $cuerpo es null). */
    public function pedirCrudo(string $ruta, ?string $cuerpoEnviado = null, string $tipo = 'application/json'): array
    {
        $this->setCookie = [];
        $this->cabeceras = [];
        $c = curl_init($this->base . '/' . $ruta);
        curl_setopt_array($c, [
            CURLOPT_RETURNTRANSFER => true, CURLOPT_COOKIEJAR => $this->jar, CURLOPT_COOKIEFILE => $this->jar,
            CURLOPT_TIMEOUT => 60,
            CURLOPT_HEADERFUNCTION => function ($c, $h) {
                if (stripos($h, 'Set-Cookie:') === 0) {
                    $this->setCookie[] = trim($h);
                }
                if (str_contains($h, ':')) {
                    [$k, $v] = explode(':', $h, 2);
                    $this->cabeceras[strtolower(trim($k))] = trim($v);
                }
                return strlen($h);
            },
        ]);
        if ($cuerpoEnviado !== null) {
            curl_setopt_array($c, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $cuerpoEnviado,
                                   CURLOPT_HTTPHEADER => ["Content-Type: $tipo"]]);
        }
        $cuerpo = curl_exec($c);
        $codigo = curl_getinfo($c, CURLINFO_RESPONSE_CODE);
        curl_close($c);
        return [$codigo, json_decode((string)$cuerpo, true) ?? []];
    }

    public function copiarCookiesA(Cliente $otro): void
    {
        copy($this->jar, $otro->jar);
    }
}

$fallos = 0;
$total = 0;
function comprobar(string $nombre, bool $ok, string $detalle = ''): void
{
    global $fallos, $total;
    $total++;
    if (!$ok) {
        $fallos++;
    }
    echo ($ok ? '  OK    ' : '  FALLO ') . $nombre . ($ok || $detalle === '' ? '' : "  -> $detalle") . "\n";
}
function crearPerfil(Cliente $c, string $nombre): int
{
    [, $r] = $c->pedir('perfiles.php', ['accion' => 'crear', 'nombre' => $nombre]);
    foreach ($r['perfiles'] ?? [] as $p) {
        if ($p['nombre'] === $nombre) {
            return $p['id'];
        }
    }
    abortar("no se pudo crear el perfil $nombre");
}

/** Imprime el resumen y sale con 0 si todo pasó, 1 si algo falló. */
function terminar(): never
{
    global $fallos, $total;
    echo "\n$total comprobaciones, $fallos fallos\n";
    exit($fallos === 0 ? 0 : 1);
}
