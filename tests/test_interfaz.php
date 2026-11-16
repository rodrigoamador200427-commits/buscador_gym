<?php
// tests/test_interfaz.php — pruebas de la interfaz en un navegador real (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_interfaz.php
//
// Usa el arnés común (solo gym_buscador_test + servidor php -S propio), agrega un documento
// con HTML en título, texto y etiquetas, y lanza tests/interfaz.mjs, que maneja Edge sin
// ventana (necesita Node 22+ y Edge o Chrome; ruta alternativa en EDGE_PATH).
// Comprueba: el detalle se abre y se cierra con teclado, el filtro por etiqueta reduce los
// resultados, el HTML del contenido no se interpreta y la página funciona a 375 px.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

echo "BD: $conectada  |  servidor: $BASE\n";

// Documento con HTML: si la interfaz no escapara, se crearían nodos o correría el script.
$db = conexion();
$db->prepare('INSERT INTO articulos (id, titulo, contenido, etiquetas) VALUES (?, ?, ?, ?)')->execute([
    390,
    '<img src=x id="xss-titulo" onerror="window.__xss=1">Título con HTML',
    'Texto <script>window.__xss=2</script><b class="xss">negrita</b>',
    '<i id="xss-tag">cursiva</i>,pecho',
]);
$db->exec("INSERT INTO diccionario (id, termino) VALUES (10, 'xsstest')");
$db->exec("INSERT INTO postings (termino_id, doc_id, origen, peso_tfidf) VALUES (10, 390, 'articulos', 1.0)");
exec('python ' . escapeshellarg("$RAIZ/scripts_py/generar_etiquetas.py") . ' 2>&1', $salida, $codigo);   // BUSCADOR_ENTORNO=pruebas ya está puesto
if ($codigo !== 0) {
    abortar('no se pudieron regenerar las etiquetas: ' . implode(' ', $salida));
}

passthru('node ' . escapeshellarg(__DIR__ . '/interfaz.mjs') . ' ' . escapeshellarg($BASE), $codigoNode);
if ($codigoNode === 3) {
    abortar('no se pudo arrancar el navegador (Node 22+ y Edge o Chrome; ver EDGE_PATH)');
}
comprobar('las pruebas del navegador pasan (detalle arriba)', $codigoNode === 0, "node salió con $codigoNode");

// Lo que la interfaz dejó en la BD
echo "\n[Efectos en la BD]\n";
$perfil = (int)$db->query("SELECT p.id FROM perfiles p JOIN cuentas c ON c.id = p.cuenta_id WHERE c.correo = 'ui@prueba.test'")->fetchColumn();
$aperturas = $db->prepare("SELECT COUNT(*) FROM eventos WHERE tipo = 'apertura' AND perfil_id = ?");
$aperturas->execute([$perfil]);
$n = (int)$aperturas->fetchColumn();
comprobar('abrir el detalle registró aperturas del perfil de la sesión', $perfil > 0 && $n >= 5, "aperturas: $n");
$likes = $db->prepare("SELECT doc_id FROM interacciones WHERE perfil_id = ? ORDER BY doc_id");
$likes->execute([$perfil]);
comprobar('los «me gusta» de la interfaz quedaron en ese perfil', array_map('intval', $likes->fetchAll(PDO::FETCH_COLUMN)) === [101, 102]);

terminar();
