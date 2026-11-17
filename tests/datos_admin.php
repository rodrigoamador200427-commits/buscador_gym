<?php
// tests/datos_admin.php — escenario FIJO para probar el panel de administrador.
//
// Lo incluye tests/test_admin.php después de que el arnés recreó gym_buscador_test.
// Inserta cuentas, perfiles, eventos y consultas con fechas conocidas, de modo que los
// totales de cada sección se puedan calcular a mano. Solo escribe en la BD de pruebas
// (el arnés ya comprobó que la conexión es *_test). Devuelve los ids que las pruebas usan.
//
// Convención de fechas: "hace N días" = hoy menos N días, a las 12:00. Así un evento de
// hace 7 días cae DENTRO de un período de 30 días y FUERA de uno de 7 (que empieza ahora
// menos 7 días, es decir, unas horas después de ese mediodía).
//
// CUENTAS (rol usuario), 31 en total, por rango de edad:
//   menos de 18:  2 cuentas (menos de 5: el rango NO debe aparecer)   edad 15, 16
//   18 a 24:      6 cuentas                                            edad 20
//   25 a 34:     12 cuentas                                            edad 30
//   35 a 44:      7 cuentas                                            edad 40
//   45 o más:     4 cuentas (menos de 5: NO debe aparecer)             edad 50
//   + 1 cuenta admin (admin@prueba.test), que no cuenta en nada.
// Cada cuenta tiene UN perfil (31 perfiles). Las 6 primeras cuentas (u01..u06) se crearon
// hace 3 días; el resto hace 60 días.
//
// EVENTOS con perfil (apertura / like), documentos del contenido sintético:
//   Período de 7 días (hace 1 y 2 días):
//     u01 (18-24): apertura 101, apertura 102, like 101          -> 2 aperturas, 1 like
//     u02 (18-24): apertura 101, apertura 301                    -> 2 aperturas
//     u07 (25-34): apertura 201, like 201, like 101              -> 1 apertura, 2 likes
//     u08 (25-34): apertura 101, apertura 302, like 302          -> 2 aperturas, 1 like
//     u19 (35-44): apertura 101                                  -> 1 apertura
//     u26 (45+):   apertura 201                                  -> 1 apertura (rango oculto)
//     u30 (<18):   like 201                                      -> 1 like     (rango oculto)
//   Total 7 días: aperturas 9, likes 5, perfiles activos 7.
//     Por documento (aperturas+likes): 101 -> 4 ap + 2 like = 6; 201 -> 2 ap + 2 like = 4;
//     102 -> 1; 301 -> 1; 302 -> 1 ap + 1 like = 2.
//   Período anterior (hace 8 a 14 días):
//     u03: apertura 103; u04: apertura 104, like 104; u09: like 105  -> 2 aperturas, 2 likes, 3 activos
//   Hace 20 días (solo cuenta en 30 y 90): u10: apertura 202; u11: like 203 -> 1 apertura, 1 like
//   Hace 50 días (solo cuenta en 90):      u12: apertura 204, apertura 205  -> 2 aperturas
//   Total 30 días: aperturas 9+2+1 = 12, likes 5+2+1 = 8, activos 7+3+2 = 12.
//   Total 90 días: aperturas 12+2 = 14, likes 8, activos 13.
//
// IMPRESIONES (sin perfil), hace 1 día:
//   ejercicio 105: 25 impresiones, 0 aperturas  -> "poco abierto" (tasa 0 %)
//   ejercicio 104: 20 impresiones, 1 apertura en el período anterior (fuera de 7 días)
//                  -> en 7 días: 0 aperturas; en 30: 1 apertura (5 %)
//   artículo 301:  30 impresiones, 1 apertura (u02)  -> 3.3 %
//   ejercicio 101: 10 impresiones (menos de 20: no entra en "poco abierto")
//   Todos los documentos del contenido sintético (101 a 105, 201 a 205, 301 y 302) tienen
//   algún evento. Por eso este escenario agrega el artículo 303 "Artículo sin estrenar",
//   con la etiqueta "recuperacion" y sin ningún evento: es el único nunca mostrado.
//
// CONSULTAS (sin perfil):
//   hace 1 día:  "banc press" via concepto n=5 (x3), "sentadill" via concepto n=5 (x2),
//                "xyz" via ninguno n=0 (x2), "pech zancad" via sin_interseccion n=3 (x1)
//   hace 10 días: "banc press" via concepto n=5 (x4)
//   7 días: 8 búsquedas, 2 sin resultados. Raíces: banc 3, press 3, sentadill 2, xyz 2, pech 1, zancad 1.
//   30 días: 12 búsquedas. Período anterior a 7: 4.
declare(strict_types=1);

require_once "$RAIZ/lib/cifrado.php";

function datos_admin(PDO $db): array
{
    $hoy = new DateTimeImmutable('today');
    $hace = fn(int $dias) => $hoy->sub(new DateInterval("P{$dias}D"))->format('Y-m-d 12:00:00');
    $nacido = fn(int $edad) => $hoy->sub(new DateInterval("P{$edad}Y"))->sub(new DateInterval('P30D'))->format('Y-m-d');

    $edades = array_merge(array_fill(0, 6, 20), array_fill(0, 12, 30), array_fill(0, 7, 40), array_fill(0, 4, 50), [15, 16]);
    $insC = $db->prepare('INSERT INTO cuentas (correo, contrasena_hash, rol, nombre_cifrado, fecha_nac_cifrada, creado_en) VALUES (?, ?, ?, ?, ?, ?)');
    $insP = $db->prepare('INSERT INTO perfiles (cuenta_id, nombre, creado_en) VALUES (?, ?, ?)');
    $perfil = [];       // 'u01' => perfil_id
    foreach ($edades as $i => $edad) {
        $u = sprintf('u%02d', $i + 1);
        $creada = $hace($i < 6 ? 3 : 60);
        $insC->execute(["$u@prueba.test", password_hash('UsuarioPrueba12345', PASSWORD_DEFAULT), 'usuario',
            cifrar_campo("Usuario $u", 'cuentas.nombre'), cifrar_campo($nacido($edad), 'cuentas.fecha_nacimiento'), $creada]);
        $cuentaId = (int)$db->lastInsertId();
        $insP->execute([$cuentaId, 'Principal', $creada]);
        $perfil[$u] = (int)$db->lastInsertId();
    }
    $insC->execute(['admin@prueba.test', password_hash('AdminPrueba12345', PASSWORD_DEFAULT), 'admin',
        cifrar_campo('Administrador', 'cuentas.nombre'), cifrar_campo('1980-01-01', 'cuentas.fecha_nacimiento'), $hace(60)]);
    $adminId = (int)$db->lastInsertId();

    $db->prepare("INSERT INTO articulos (id, titulo, contenido, etiquetas) VALUES (303, 'Artículo sin estrenar', 'Nadie lo ha visto.', 'recuperacion')")->execute();
    // Etiquetas y rutas del artículo nuevo (BUSCADOR_ENTORNO=pruebas ya está puesto por el arnés)
    global $RAIZ;
    exec('python ' . escapeshellarg("$RAIZ/scripts_py/generar_etiquetas.py") . ' 2>&1', $salida, $codigo);
    if ($codigo !== 0) {
        abortar('no se pudieron regenerar las etiquetas: ' . implode(' ', $salida));
    }

    $ev = $db->prepare('INSERT INTO eventos (perfil_id, tipo, origen, doc_id, creado_en) VALUES (?, ?, ?, ?, ?)');
    $like = $db->prepare("INSERT IGNORE INTO interacciones (perfil_id, doc_id, origen, interaccion, peso, fecha) VALUES (?, ?, ?, 'like', 1.0, ?)");
    $evento = function (string $u, string $tipo, string $origen, int $doc, int $haceDias) use ($ev, $like, $perfil, $hace): void {
        $ev->execute([$perfil[$u], $tipo, $origen, $doc, $hace($haceDias)]);
        if ($tipo === 'like') {
            $like->execute([$perfil[$u], $doc, $origen, $hace($haceDias)]);
        }
    };
    // Período de 7 días
    $evento('u01', 'apertura', 'ejercicios', 101, 1); $evento('u01', 'apertura', 'ejercicios', 102, 2); $evento('u01', 'like', 'ejercicios', 101, 1);
    $evento('u02', 'apertura', 'ejercicios', 101, 1); $evento('u02', 'apertura', 'articulos', 301, 2);
    $evento('u07', 'apertura', 'ejercicios', 201, 1); $evento('u07', 'like', 'ejercicios', 201, 1); $evento('u07', 'like', 'ejercicios', 101, 2);
    $evento('u08', 'apertura', 'ejercicios', 101, 2); $evento('u08', 'apertura', 'articulos', 302, 1); $evento('u08', 'like', 'articulos', 302, 1);
    $evento('u19', 'apertura', 'ejercicios', 101, 1);
    $evento('u26', 'apertura', 'ejercicios', 201, 2);
    $evento('u30', 'like', 'ejercicios', 201, 1);
    // Período anterior (8 a 14 días)
    $evento('u03', 'apertura', 'ejercicios', 103, 9); $evento('u04', 'apertura', 'ejercicios', 104, 10); $evento('u04', 'like', 'ejercicios', 104, 10);
    $evento('u09', 'like', 'ejercicios', 105, 12);
    // Hace 20 y 50 días
    $evento('u10', 'apertura', 'ejercicios', 202, 20); $evento('u11', 'like', 'ejercicios', 203, 20);
    $evento('u12', 'apertura', 'ejercicios', 204, 50); $evento('u12', 'apertura', 'ejercicios', 205, 50);

    // Impresiones (sin perfil)
    $imp = $db->prepare("INSERT INTO eventos (perfil_id, tipo, origen, doc_id, creado_en) VALUES (NULL, 'impresion', ?, ?, ?)");
    foreach ([['ejercicios', 105, 25], ['ejercicios', 104, 20], ['articulos', 301, 30], ['ejercicios', 101, 10]] as [$o, $d, $n]) {
        for ($i = 0; $i < $n; $i++) {
            $imp->execute([$o, $d, $hace(1)]);
        }
    }

    // Consultas (sin perfil ni texto original)
    $con = $db->prepare('INSERT INTO consultas (raices, via, n_resultados, creado_en) VALUES (?, ?, ?, ?)');
    foreach ([['banc press', 'concepto', 5, 1, 3], ['sentadill', 'concepto', 5, 1, 2], ['xyz', 'ninguno', 0, 1, 2],
              ['pech zancad', 'sin_interseccion', 3, 1, 1], ['banc press', 'concepto', 5, 10, 4]] as [$r, $via, $n, $d, $veces]) {
        for ($i = 0; $i < $veces; $i++) {
            $con->execute([$r, $via, $n, $hace($d)]);
        }
    }

    return ['perfiles' => $perfil, 'admin_id' => $adminId];
}
