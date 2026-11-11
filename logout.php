<?php
// logout.php — POST (application/json). Destruye la sesión y borra la cookie.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

leer_json_post();     // exige POST + JSON: otro sitio no puede cerrar tu sesión con un <img> o un formulario
cerrar_sesion();
responder(['status' => 'success']);
