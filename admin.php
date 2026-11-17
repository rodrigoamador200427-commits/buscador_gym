<?php
// admin.php — página del panel de administrador.
//
// PHP no puede proteger un .html estático, así que el HTML vive en lib/admin_panel.html
// (carpeta bloqueada por HTTP) y solo se entrega después de requerir_admin(): 401 sin
// sesión, 403 si la cuenta no tiene el rol. El navegador pide aquí la página y a
// admin_estadisticas.php los datos; ninguno de los dos funciona sin el rol.
declare(strict_types=1);
require_once __DIR__ . '/lib/bootstrap.php';

requerir_admin();
session_write_close();

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
// Solo recursos de este mismo sitio; los estilos en línea son los anchos de las barras
header("Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'");
readfile(__DIR__ . '/lib/admin_panel.html');
