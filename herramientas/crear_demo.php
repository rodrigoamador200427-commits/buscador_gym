<?php
// herramientas/crear_demo.php — cuenta demo con 2 perfiles de historiales distintos.
//
//   php herramientas/crear_demo.php                              (BD real, gym_buscador)
//   BUSCADOR_ENTORNO=pruebas php herramientas/crear_demo.php     (gym_buscador_test)
//
// - "Pecho":  likes en ejercicios cuyo nombre dice "press de banca" / "aperturas"
// - "Pierna": likes en "sentadilla" / "zancada" / "prensa de piernas"
// Se elige por nombre y no por ejercicios.grupo_id porque ese campo NO corresponde
// al músculo en el dataset (el grupo 5 "Pecho" contiene ejercicios de tríceps).
// Es idempotente: si la cuenta demo existe, la borra (cascada) y la vuelve a crear.
// La contraseña se toma de DEMO_CONTRASENA o se genera al azar y se imprime UNA vez en
// la consola (no se escribe en ningún archivo ni log).
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once dirname(__DIR__) . '/lib/config.php';
require_once dirname(__DIR__) . '/lib/db.php';
require_once dirname(__DIR__) . '/lib/cifrado.php';
require_once dirname(__DIR__) . '/lib/validacion.php';
require_once dirname(__DIR__) . '/lib/cuentas.php';

const DEMO_CORREO = 'demo@buscador-gym.local';
const LIKES_POR_PERFIL = [                       // perfil => [palabra del nombre => cuántos]
    'Pecho'  => ['press de banca' => 3, 'aperturas' => 3],
    'Pierna' => ['sentadilla' => 2, 'zancada' => 2, 'prensa de piernas' => 2],
];

$contrasena = getenv('DEMO_CONTRASENA') ?: ('Demo' . bin2hex(random_bytes(5)) . '7');
if (($err = validar_contrasena($contrasena, DEMO_CORREO)) !== null) {
    fwrite(STDERR, "DEMO_CONTRASENA no válida: $err\n");
    exit(1);
}

$db = conexion();
$db->beginTransaction();

$s = $db->prepare('SELECT id FROM cuentas WHERE correo = ?');
$s->execute([DEMO_CORREO]);
if ($idViejo = $s->fetchColumn()) {
    eliminar_cuenta($db, (int)$idViejo, DEMO_CORREO);
}

$db->prepare('INSERT INTO cuentas (correo, contrasena_hash, nombre_cifrado, fecha_nac_cifrada) VALUES (?, ?, ?, ?)')
   ->execute([DEMO_CORREO, password_hash($contrasena, PASSWORD_DEFAULT),
              cifrar_campo('Cuenta Demo', 'cuentas.nombre'), cifrar_campo('2000-01-01', 'cuentas.fecha_nacimiento')]);
$cuentaId = (int)$db->lastInsertId();

// Solo ejercicios que están indexados (tienen postings), en orden estable por id
$ejercicios = $db->prepare(
    "SELECT e.id FROM ejercicios e
      WHERE e.nombre_es LIKE CONCAT('%', ?, '%')
        AND EXISTS (SELECT 1 FROM postings p WHERE p.origen = 'ejercicios' AND p.doc_id = e.id)
      ORDER BY e.id LIMIT ?");
$insPerfil = $db->prepare('INSERT INTO perfiles (cuenta_id, nombre) VALUES (?, ?)');
$insLike = $db->prepare("INSERT IGNORE INTO interacciones (perfil_id, doc_id, origen, interaccion, peso) VALUES (?, ?, 'ejercicios', 'like', 1.0)");

foreach (LIKES_POR_PERFIL as $nombrePerfil => $palabras) {
    $insPerfil->execute([$cuentaId, $nombrePerfil]);
    $perfilId = (int)$db->lastInsertId();
    $n = 0;
    foreach ($palabras as $palabra => $cuantos) {
        $ejercicios->bindValue(1, $palabra, PDO::PARAM_STR);
        $ejercicios->bindValue(2, $cuantos, PDO::PARAM_INT);     // LIMIT necesita entero real
        $ejercicios->execute();
        foreach ($ejercicios->fetchAll(PDO::FETCH_COLUMN) as $docId) {
            $insLike->execute([$perfilId, $docId]);
            $n += $insLike->rowCount();
        }
    }
    echo "Perfil \"$nombrePerfil\" (id $perfilId): $n likes\n";
}
$db->commit();

echo 'BD: ' . config()['db']['nombre'] . "\n";
echo 'Correo: ' . DEMO_CORREO . "\n";
echo (getenv('DEMO_CONTRASENA') ? "Contraseña: la de DEMO_CONTRASENA\n" : "Contraseña (se muestra solo ahora): $contrasena\n");
