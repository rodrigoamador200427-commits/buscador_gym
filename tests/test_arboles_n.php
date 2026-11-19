<?php
// tests/test_arboles_n.php — pruebas HTTP de los árboles de la fase 6B (CLI).
//
//   D:\Tools\SHAMP\php\php.exe tests\test_arboles_n.php
//
// Catálogo de cuatro árboles, cruce de dos árboles cualesquiera (menus.php?accion=cruce), el
// descubrimiento de buscar.php con la ruta de CADA árbol que participa, y una ruta por árbol en
// el detalle. Mismo arnés que las otras pruebas: solo gym_buscador_test y un php -S propio.
declare(strict_types=1);

require_once __DIR__ . '/arnes.php';

echo "BD: $conectada  |  servidor: $BASE\n";

$A = new Cliente($BASE);
$anon = new Cliente($BASE);
$A->pedir('registro.php', ['correo' => 'a@prueba.test', 'contrasena' => 'CuentaA12345',
                           'nombre_completo' => 'Cuenta A', 'fecha_nacimiento' => '2000-01-01']);
$perfil = crearPerfil($A, 'Pecho');
$A->pedir('seleccionar_perfil.php', ['perfil_id' => $perfil]);

// ----------------------------------------------------------------------------- catálogo
echo "\n[menus.php?accion=catalogo: cinco árboles]\n";
[$cod, $cat] = $anon->pedir('menus.php?accion=catalogo');
comprobar('catálogo -> 200 con los cinco árboles en orden', $cod === 200 && array_column($cat['arboles'] ?? [], 'id') === ['anatomia', 'temas', 'equipamiento', 'nivel', 'patron'],
    json_encode(array_column($cat['arboles'] ?? [], 'id')));
comprobar('un par por cada combinación de dos árboles (10)', count($cat['pares'] ?? []) === 10, json_encode(array_keys($cat['pares'] ?? [])));
$eq = array_column(array_column($cat['arboles'], null, 'id')['equipamiento']['conceptos'] ?? [], null, 'clave');
comprobar('equipamiento: claves sin acentos (maquina) y nombre visible con acento (Máquina)',
    ($eq['maquina']['nombre'] ?? '') === 'Máquina' && isset($eq['barra'], $eq['mancuernas']), json_encode(array_keys($eq)));
comprobar('cada concepto trae su ruta de la raíz al nodo', ($eq['barra']['ruta'] ?? []) === ['Equipamiento', 'Pesas libres', 'Barra'], json_encode($eq['barra']['ruta'] ?? null));
comprobar('pares anatomia|equipamiento: pecho x barra = [ejercicios, artículos]',
    is_array($cat['pares']['anatomia|equipamiento']['1|barra'] ?? null) && $cat['pares']['anatomia|equipamiento']['1|barra'][0] >= 1,
    json_encode($cat['pares']['anatomia|equipamiento']['1|barra'] ?? null));
$patron = array_column($cat['arboles'], null, 'id')['patron'] ?? [];
comprobar('patrón: marcado como aproximado, con el número de ejercicios sin clasificar y «Sin clasificar» como concepto',
    ($patron['aproximado'] ?? null) === true && is_int($patron['sin_clasificar'] ?? null)
    && in_array('sin clasificar', array_column($patron['conceptos'] ?? [], 'clave'), true), json_encode([$patron['aproximado'] ?? null, $patron['sin_clasificar'] ?? null]));
comprobar('los otros cuatro árboles no se marcan como aproximados',
    !array_filter($cat['arboles'], fn($a) => $a['id'] !== 'patron' && isset($a['aproximado'])));
comprobar('anatomia|temas solo tiene artículos (los ejercicios no entran en Temas)',
    !array_filter($cat['pares']['anatomia|temas'], fn($n) => $n[0] !== 0), json_encode($cat['pares']['anatomia|temas']));

// ----------------------------------------------------------------------------- cruce
echo "\n[menus.php?accion=cruce]\n";
[$cod, $c] = $anon->pedir('menus.php?accion=cruce&a=anatomia&x=1&b=equipamiento&y=barra');
comprobar('pecho x barra -> 200 con ejercicios y las rutas de los dos nodos',
    $cod === 200 && ($c['status'] ?? '') === 'success' && count($c['ejercicios'] ?? []) >= 1
    && array_column($c['nodos'] ?? [], 'arbol') === ['anatomia', 'equipamiento'], json_encode([$cod, array_column($c['nodos'] ?? [], 'arbol'), count($c['ejercicios'] ?? [])]));
comprobar('los ejercicios devueltos son de pecho y de barra',
    !array_filter($c['ejercicios'] ?? [], fn($t) => ($t['meta']['musculo'] ?? '') !== 'Pecho' || ($t['meta']['equipamiento'] ?? '') !== 'Barra'),
    json_encode(array_map(fn($t) => $t['meta'], $c['ejercicios'] ?? [])));
comprobar('el cruce no depende del orden de los árboles', json_encode($anon->pedir('menus.php?accion=cruce&a=equipamiento&x=barra&b=anatomia&y=1')[1]['ejercicios'] ?? null) === json_encode($c['ejercicios'] ?? 0));
[, $m] = $anon->pedir('menus.php?accion=cruce&a=anatomia&x=1&b=temas&y=fuerza');
comprobar('músculo x tema sigue mostrando los ejercicios del músculo', ($m['ejercicios_del_musculo'] ?? null) === true && count($m['articulos'] ?? []) >= 1, json_encode($m['ejercicios_del_musculo'] ?? null));
comprobar('misma estructura de tarjeta que la búsqueda', !array_diff(['doc_id', 'origen', 'tipo', 'titulo', 'resumen', 'meta', 'etiquetas'], array_keys($c['ejercicios'][0] ?? [])));
foreach (['a=inventado&x=1&b=nivel&y=principiante' => 'árbol fuera de la lista',
          'a=anatomia&x=1&b=anatomia&y=2' => 'el mismo árbol dos veces',
          'a=anatomia&x=1&b=equipamiento&y=Barra' => 'clave con mayúsculas',
          "a=anatomia&x=1&b=nivel&y=" . rawurlencode("principiante' OR 1=1") => 'inyección en la clave',
          'a=anatomia&x=1&b=nivel' => 'falta una clave'] as $url => $que) {
    comprobar("422: $que", $anon->pedir("menus.php?accion=cruce&$url")[0] === 422);
}
comprobar('concepto que no existe -> 404 (no se interpreta)', $anon->pedir('menus.php?accion=cruce&a=anatomia&x=99&b=nivel&y=principiante')[0] === 404);

[$cod, $p] = $anon->pedir('menus.php?accion=cruce&a=anatomia&x=1&b=patron&y=empuje%20horizontal');
comprobar('pecho x empuje horizontal -> 200, ejercicios de pecho y aviso de aproximado', $cod === 200 && count($p['ejercicios'] ?? []) >= 1
    && ($p['aproximado'] ?? null) === true && array_column($p['nodos'] ?? [], 'aproximado') === [false, true], json_encode([$cod, $p['aproximado'] ?? null]));
[, $p2] = $anon->pedir('menus.php?accion=cruce&a=anatomia&x=1&b=equipamiento&y=barra');
comprobar('un cruce sin patrón no se marca como aproximado', ($p2['aproximado'] ?? null) === false);
comprobar('«sin clasificar» se puede pedir como cualquier concepto', $anon->pedir('menus.php?accion=cruce&a=patron&x=sin%20clasificar&b=nivel&y=principiante')[0] === 200);

// ----------------------------------------------------------------------------- buscar.php
echo "\n[buscar.php: descubrimiento con la ruta de cada árbol]\n";
[$cod, $bus] = $A->pedir('buscar.php?q=' . rawurlencode('pecho barra principiante'));
$d = $bus['descubrimiento'] ?? [];
comprobar('pecho barra principiante: cruza tres árboles', $cod === 200 && ($d['via'] ?? '') === 'interseccion'
    && array_column($d['nodos'] ?? [], 'arbol') === ['anatomia', 'equipamiento', 'nivel'], json_encode([$d['via'] ?? null, array_column($d['nodos'] ?? [], 'arbol')]));
comprobar('cada nodo trae título del árbol y ruta de la raíz al nodo',
    ($d['nodos'][1]['titulo'] ?? '') === 'Equipamiento' && ($d['nodos'][1]['ruta'] ?? []) === ['Equipamiento', 'Pesas libres', 'Barra']
    && ($d['nodos'][2]['ruta'] ?? []) === ['Nivel de experiencia', 'Principiante'], json_encode($d['nodos'] ?? null));
comprobar('el documento descubierto puede ser un ejercicio (se hidrata como cualquier tarjeta)',
    isset($d['doc_id'], $d['titulo'], $d['meta']) && in_array($d['origen'] ?? '', ['ejercicios', 'articulos'], true), json_encode(array_keys($d)));
comprobar('compatibilidad: origen_ruta y destino_ruta siguen ahí', ($d['origen_ruta'] ?? []) === ['Cuerpo humano', 'Tren superior', 'Pecho'] && !empty($d['destino_ruta']));

[, $bus] = $A->pedir('buscar.php?q=' . rawurlencode('pecho'));
comprobar('pecho solo: salto a Temas como en la fase 1', ($bus['descubrimiento']['destino_arbol'] ?? '') === 'temas' && ($bus['descubrimiento']['via'] ?? '') === 'concepto',
    json_encode([$bus['descubrimiento']['via'] ?? null, $bus['descubrimiento']['destino_arbol'] ?? null]));
[, $bus] = $A->pedir('buscar.php?q=' . rawurlencode('pecho kettlebell'));
comprobar('par sin documentos: se dice y no se inventa', ($bus['descubrimiento']['via'] ?? '') === 'sin_interseccion' && !empty($bus['descubrimiento']['sin_documento'])
    && count($bus['descubrimiento']['nodos'] ?? []) === 2, json_encode($bus['descubrimiento'] ?? null));
[, $a1] = $A->pedir('buscar.php?q=' . rawurlencode('pecho barra principiante'));
comprobar('misma consulta, misma respuesta (determinista)', json_encode($a1['descubrimiento'] ?? 1) === json_encode($d));

// ----------------------------------------------------------------------------- detalle
echo "\n[detalle.php: una ruta por árbol]\n";
[, $e] = $A->pedir('detalle.php?origen=ejercicios&doc_id=101');
$rutas = array_column($e['documento']['rutas'] ?? [], null, 'arbol');
comprobar('un ejercicio: anatomía, equipamiento, nivel y patrón, en ese orden',
    array_keys($rutas) === ['anatomia', 'equipamiento', 'nivel', 'patron'], json_encode(array_keys($rutas)));
comprobar('la ruta de patrón va marcada como aproximada y las demás no',
    ($rutas['patron']['aproximado'] ?? null) === true && ($rutas['patron']['nodos'] ?? []) === ['Patrón de movimiento', 'Empuje', 'Empuje horizontal']
    && !array_filter(['anatomia', 'equipamiento', 'nivel'], fn($k) => $rutas[$k]['aproximado'] !== false), json_encode($rutas['patron'] ?? null));
comprobar('rutas completas', ($rutas['equipamiento']['nodos'] ?? []) === ['Equipamiento', 'Pesas libres', 'Barra'] && ($rutas['nivel']['titulo'] ?? '') === 'Nivel'
    && ($rutas['anatomia']['nodos'] ?? []) === ['Cuerpo humano', 'Tren superior', 'Pecho', 'Barra']);
comprobar('`ruta` (la principal) se conserva igual que antes', ($e['documento']['ruta'] ?? null) === ['arbol' => 'anatomia', 'nodos' => ['Cuerpo humano', 'Tren superior', 'Pecho', 'Barra']]);
[, $ar] = $A->pedir('detalle.php?origen=articulos&doc_id=302');
comprobar('un artículo: solo temas', array_column($ar['documento']['rutas'] ?? [], 'arbol') === ['temas'], json_encode($ar['documento']['rutas'] ?? null));

terminar();
