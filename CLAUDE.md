# buscador_gym

Buscador y recomendador de ejercicios y artículos de gimnasio (proyecto de Recuperación de la
Información). PHP 8.2 + MariaDB 10.4 (SHAMP, en `D:\Tools\SHAMP`) + Python 3 (`scripts_py/`).
PHP no está en el PATH: usar `D:\Tools\SHAMP\php\php.exe` y `D:\Tools\SHAMP\mysql\bin\mysql.exe`.

## Arquitectura

- `index.html`: única página. Acceso (registro/login) → selector de perfil → búsqueda,
  recomendaciones y menús A+B.
- Endpoints JSON en la raíz: `registro.php`, `login.php`, `logout.php`, `sesion.php`,
  `perfiles.php`, `seleccionar_perfil.php`, `buscar.php`, `recomendaciones.php`,
  `registrar_interaccion.php`, `registrar_evento.php`, `menus.php`.
- `lib/`: código común. Todo endpoint empieza con `require_once __DIR__ . '/lib/bootstrap.php';`.
  - `config.php` (secretos) · `db.php` (`conexion()`) · `sesion.php` (sesión + autorización)
  - `cifrado.php` (AES-256-GCM) · `validacion.php` · `intentos.php` (límite de login)
  - `respuesta.php` (`responder`, `responder_error`, `leer_json_post`, `registrar_fallo`)
  - `python.php` (`ejecutar_python`) · `documentos.php` (`leer_ref_documento`) · `cuentas.php`
  - `estadisticas.php` (`registrar_consulta`, `registrar_eventos`, `registrar_sin_fallar`)
- `scripts_py/`: motor TF-IDF, árboles (`arboles/`), `recommender.py` (centroide + coseno por
  perfil), `db_config.py` (lee la misma config que PHP).
- `sql/esquema_cuentas.sql`: cuentas, perfiles, interacciones (por perfil), intentos_login.
  Es idempotente y no tiene `USE`: se aplica a la BD elegida.
- `sql/esquema_estadisticas.sql`: `eventos` (impresion/apertura/like; `perfil_id` NULL con
  `ON DELETE SET NULL`) y `consultas` (solo raíces; sin perfil ni texto original). Mismo estilo.
- `herramientas/crear_demo.php`: cuenta demo con perfiles "Pecho" y "Pierna" (solo CLI).
- `herramientas/purgar_estadisticas.php`: borra `consultas` y `eventos` de más de 180 días (solo CLI).
- `config/`, `lib/`, `herramientas/`, `sql/`, `tests/` tienen `.htaccess` con `Require all denied`.

## Configuración (secretos fuera de Git)

`config/config.local.ini.php` (BD real) y `config/config.test.ini.php` (`gym_buscador_test`)
están en `.gitignore`. La plantilla es `config/config.example.ini.php`. La variable de entorno
`BUSCADOR_ENTORNO=pruebas` (del proceso, nunca de la petición) elige la de pruebas. PHP y Python
rechazan una configuración real que apunte a `*_test` y una de pruebas que no lo haga.
Cambiar `aes_clave` vuelve ilegibles los datos ya cifrados.

## Reglas de seguridad (no romperlas)

1. **El perfil activo sale SOLO de la sesión** (`requerir_perfil_activo()`). Nunca leer
   `perfil_id` de la petición para buscar, dar likes o recomendar.
2. Todo endpoint que reciba un `perfil_id` lo valida con `requerir_perfil_propio()`, que responde
   403 si es ajeno o no existe. Además se filtra por `cuenta_id` en el SQL.
3. Toda consulta a `interacciones` lleva `WHERE perfil_id = ?`. El centroide NO se guarda: se
   recalcula por perfil. `scripts_py/tests/test_aislamiento.py` espía el SQL para comprobarlo.
4. Solo consultas preparadas (PDO con `EMULATE_PREPARES=false`; `%s` en Python). Nada de SQL con
   f-strings ni concatenación de valores. `origen` ∈ `ORIGENES_VALIDOS` (`ejercicios`, `articulos`).
5. Contraseñas: `password_hash`/`password_verify`. Nombre completo y fecha de nacimiento:
   `cifrar_campo($v, 'cuentas.<campo>')`. El correo va normalizado y en claro.
6. Nada sensible en logs ni respuestas: `registrar_fallo()` registra clase + SQLSTATE + ref,
   nunca `getMessage()`. `debug_motor` solo trae `{codigo, ref}`. La salida de Python no se
   reenvía al cliente, y su stderr se descarta.
7. POST siempre con `leer_json_post()` (exige `application/json`; frena CSRF junto con
   `SameSite=Strict`).
8. En `index.html`, todo texto del servidor pasa por `esc()` antes de ir a `innerHTML`.
9. Estadísticas: el registro nunca hace fallar ni retrasa la petición (`enviar_y_continuar()` +
   `registrar_sin_fallar()`). Las impresiones se guardan SIN perfil (si no, se unirían por
   `creado_en` con `consultas`). `consultas` nunca guarda el texto original ni el perfil.

## Pruebas

```
cd scripts_py && python -m pytest tests -v                  # incluye test_aislamiento.py
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php       # HTTP: 403, sesión, aislamiento
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php       # HTTP: eventos, consultas, purga
```
Ambas usan SOLO `gym_buscador_test`: la recrean con contenido sintético
(`scripts_py/tests/fixtures/contenido_test.sql`) y se niegan a correr si la BD no termina en
`_test` o coincide con la real. Las pruebas PHP comparten `tests/arnes.php`: guardas de BD, su
propio `php -S` en un puerto libre (no usa Apache) y el cliente HTTP. `buscar.php` registra
después de responder: una prueba que lea la BD tras buscar debe esperar con otra petición
(ver `buscar()` en `test_estadisticas.php`).

## Puesta en marcha

```
mysql -uroot gym_buscador < sql/esquema_cuentas.sql
mysql -uroot gym_buscador < sql/esquema_estadisticas.sql
php herramientas/crear_demo.php        # imprime la contraseña demo una sola vez
```

## Avisos

- Los IDs de músculo (`ejercicios.grupo_id`) son los de `unirdataset/limpiar_ejercicios.py` y
  `taxonomia.MUSCULOS` (1=Pecho … 11=Antebrazos). La tabla `grupos_musculares` tenía los nombres
  desalineados; se corrigió con `sql/corregir_grupos_musculares.sql`. Ningún código la lee: la
  fuente de verdad es `taxonomia.py`.
- No existe la tabla `alimentos`. `postings.origen` solo tiene `ejercicios` y `articulos`.
- Avances del proyecto: `docs/Avances.md`. Estructura de los árboles: `ESTRUCTURA.md`.
