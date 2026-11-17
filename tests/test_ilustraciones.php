<?php
// tests/test_ilustraciones.php — pruebas de las ilustraciones por músculo y por tema (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_ilustraciones.php [carpeta de capturas]
//
// 1. Revisa los archivos: SVG bien formados y ninguna dirección externa.
// 2. Comprueba que el servidor dice a cada tarjeta qué ilustración le toca (grupo_id o tema).
// 3. Lanza tests/ilustraciones.mjs (Edge sin ventana), que hace una captura de CADA ilustración
//    en claro y en oscuro y cuenta píxeles: el músculo resaltado se ve, el resto queda
//    atenuado y ningún color está fijo. Con una carpeta (o CAPTURAS) guarda los PNG.
// Usa el arnés común: solo gym_buscador_test y un servidor php -S propio.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

echo "BD: $conectada  |  servidor: $BASE\n";

// ----------------------------------------------------------------------------- archivos
echo "\n[Archivos de las ilustraciones]\n";
$svgs = array_merge(glob("$RAIZ/assets/anatomia/*.svg") ?: [], glob("$RAIZ/assets/temas/*.svg") ?: []);
$nombres = array_map('basename', $svgs);
sort($nombres);
comprobar('existen frontal.svg, posterior.svg (assets/anatomia) y pictogramas.svg (assets/temas)',
    $nombres === ['frontal.svg', 'pictogramas.svg', 'posterior.svg'], json_encode($nombres));
$malFormados = [];
foreach ($svgs as $f) {
    $doc = new DOMDocument();
    if (!@$doc->load($f) || $doc->documentElement->localName !== 'svg') {
        $malFormados[] = basename($f);
    }
}
comprobar('los SVG son XML bien formado', !$malFormados, json_encode($malFormados));

// Ninguna dirección externa: ni en los dibujos, ni en el código que los usa, ni en la página.
// El espacio de nombres de SVG (xmlns) es un identificador, no un enlace que se descargue.
$externos = [];
foreach (array_merge($svgs, ["$RAIZ/assets/ilustraciones.js", "$RAIZ/assets/estilos.css", "$RAIZ/index.html"]) as $f) {
    $texto = str_replace('xmlns="http://www.w3.org/2000/svg"', '', (string)file_get_contents($f));
    if (preg_match_all('~(?:https?:)?//[a-z0-9.-]+\.[a-z]{2,}[^\s"\'<>)]*~i', $texto, $m)) {
        $externos[basename($f)] = array_values(array_unique($m[0]));
    }
    if (preg_match('~<(script|link|img|image|use)[^>]*(src|href)\s*=\s*["\'](?:data:|https?:|//)~i', $texto)) {
        $externos[basename($f)][] = 'etiqueta con recurso externo o data:';
    }
}
comprobar('ningún archivo de la interfaz apunta a una dirección externa', !$externos, json_encode($externos));
comprobar('index.html carga assets/ilustraciones.js', str_contains((string)file_get_contents("$RAIZ/index.html"), '<script src="assets/ilustraciones.js"></script>'));

// ----------------------------------------------------------------------------- datos para el navegador
exec('python -c ' . escapeshellarg(
    "import json, sys; sys.path.insert(0, r'$RAIZ/scripts_py'); from arboles.taxonomia import MUSCULOS, TEMAS; "
    . "print(json.dumps({'musculos': sorted(MUSCULOS), 'temas': [t[1] for t in TEMAS]}))"
) . ' 2>&1', $salidaTax, $codigoTax);
$taxonomia = json_decode(implode('', $salidaTax), true);
if ($codigoTax !== 0 || !is_array($taxonomia)) {
    abortar('no se pudo leer la taxonomía: ' . implode(' ', $salidaTax));
}
$db = conexion();
$taxonomia['grupos_bd'] = array_map('intval', $db->query('SELECT DISTINCT grupo_id FROM ejercicios WHERE grupo_id IS NOT NULL ORDER BY grupo_id')->fetchAll(PDO::FETCH_COLUMN));
comprobar('la taxonomía tiene 11 grupos musculares y 9 temas', count($taxonomia['musculos']) === 11 && count($taxonomia['temas']) === 9,
    json_encode($taxonomia));

// ----------------------------------------------------------------------------- el servidor dice qué ilustración toca
echo "\n[Tarjetas: grupo_id en los ejercicios y tema en los artículos]\n";
$A = new Cliente($BASE);
$A->pedir('registro.php', ['correo' => 'ilu@prueba.test', 'contrasena' => 'Ilustra12345',
                           'nombre_completo' => 'Prueba Ilustraciones', 'fecha_nacimiento' => '2000-01-01']);
$A->pedir('seleccionar_perfil.php', ['perfil_id' => crearPerfil($A, 'Uno')]);
[, $bus] = $A->pedir('buscar.php?q=calentamiento');
$porClave = [];
foreach ($bus['resultados'] ?? [] as $t) {
    $porClave[$t['origen'] . ':' . $t['doc_id']] = $t;
}
comprobar('ejercicio 101 (pecho): grupo_id 1 y sin tema', ($porClave['ejercicios:101']['grupo_id'] ?? null) === 1
    && array_key_exists('tema', $porClave['ejercicios:101']) && $porClave['ejercicios:101']['tema'] === null, json_encode($porClave['ejercicios:101'] ?? null));
comprobar('ejercicio 201 (cuádriceps): grupo_id 6', ($porClave['ejercicios:201']['grupo_id'] ?? null) === 6);
comprobar('artículo 301: tema "Fuerza" (su nodo en el árbol de Temas) y sin grupo_id',
    ($porClave['articulos:301']['tema'] ?? null) === 'Fuerza' && $porClave['articulos:301']['grupo_id'] === null, json_encode($porClave['articulos:301'] ?? null));
$sinDato = array_keys(array_filter($porClave, fn($t) => $t['grupo_id'] === null && $t['tema'] === null));
comprobar('las 12 tarjetas traen uno de los dos datos', count($porClave) === 12 && !$sinDato, json_encode($sinDato));
[, $det] = $A->pedir('detalle.php?origen=articulos&doc_id=302');
comprobar('el detalle también lo trae', ($det['documento']['tema'] ?? null) === 'Fuerza');
[, $det] = $A->pedir('detalle.php?origen=ejercicios&doc_id=204');
comprobar('el detalle de un ejercicio trae su grupo_id', ($det['documento']['grupo_id'] ?? null) === 6);

// ----------------------------------------------------------------------------- navegador
$carpeta = $argv[1] ?? getenv('CAPTURAS') ?: '';
$rutaDatos = tempnam(sys_get_temp_dir(), 'ilu');
file_put_contents($rutaDatos, json_encode($taxonomia));
passthru('node ' . escapeshellarg(__DIR__ . '/ilustraciones.mjs') . ' ' . escapeshellarg($BASE) . ' ' . escapeshellarg($rutaDatos)
    . ($carpeta !== '' ? ' ' . escapeshellarg($carpeta) : ''), $codigoNode);
@unlink($rutaDatos);
if ($codigoNode === 3) {
    abortar('no se pudo arrancar el navegador (Node 22+ y Edge o Chrome; ver EDGE_PATH)');
}
echo "\n";
comprobar('las pruebas del navegador pasan (detalle arriba)', $codigoNode === 0, "node salió con $codigoNode");

terminar();
