;<?php http_response_code(404); exit; ?>
; =============================================================================
; PLANTILLA de configuración (esta sí va en Git; NO contiene secretos reales).
;
; Copia este archivo como:
;   config/config.local.ini.php   -> base real (gym_buscador)
;   config/config.test.ini.php    -> base de pruebas (gym_buscador_test)
; Ambos están en .gitignore. La primera línea hace que, si alguien lo pide por
; HTTP, PHP lo ejecute y responda 404 sin mostrar nada; además config/.htaccess
; niega todo acceso web a esta carpeta.
;
; Genera la clave AES con:
;   php -r "echo base64_encode(random_bytes(32)), PHP_EOL;"
; Si cambias la clave, los datos cifrados con la anterior ya no se pueden leer.
; =============================================================================

[app]
; produccion | pruebas   (las pruebas se niegan a correr si no dice "pruebas")
entorno = "produccion"

[db]
host = "localhost"
nombre = "gym_buscador"
usuario = "root"
contrasena = ""

[cifrado]
; 32 bytes en base64 (AES-256-GCM)
aes_clave = "CAMBIAME_base64_de_32_bytes"
