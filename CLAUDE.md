# buscador_gym

Buscador y recomendador de ejercicios y artículos de gimnasio (proyecto de Recuperación de la
Información). PHP 8.2 + MariaDB 10.4 (SHAMP, en `D:\Tools\SHAMP`) + Python 3 (`scripts_py/`).
PHP no está en el PATH: usar `D:\Tools\SHAMP\php\php.exe` y `D:\Tools\SHAMP\mysql\bin\mysql.exe`.

## Arquitectura

- `index.html`: única página (HTML + JS). Acceso (registro/login) → selector de perfil →
  búsqueda, recomendaciones, detalle de tarjeta (`<dialog>`) y "Explorar por árboles".
  Sus estilos están en `assets/estilos.css` (sistema de diseño con variables CSS; el modo
  oscuro son las mismas variables con otros valores bajo `prefers-color-scheme: dark`).
- Ilustraciones (dibujos propios, sin enlaces externos): `assets/anatomia/frontal.svg` y
  `posterior.svg` (cuerpo con una región con id por músculo), `assets/temas/pictogramas.svg`
  (un pictograma por tema) y `assets/ilustraciones.js`, cuya función
  `ilustracion(origen, grupo_id_o_tema)` elige cuál mostrar. El cuerpo se toma con `<use>` y la
  región se resalta con una variable CSS (`--ilu-<region>`): un archivo por vista sirve para
  los 11 músculos. Un músculo o tema nuevo se agrega en los mapas `MUSCULOS` / `TEMAS` de ese JS.
- Endpoints JSON en la raíz: `registro.php`, `login.php`, `logout.php`, `sesion.php`,
  `perfiles.php`, `seleccionar_perfil.php`, `buscar.php`, `recomendaciones.php`,
  `registrar_interaccion.php`, `registrar_evento.php`, `detalle.php`, `etiquetas.php`,
  `menus.php`.
- Panel de administrador: `admin.php` (entrega la página solo a un admin; el HTML está en
  `lib/admin_panel.html`, porque PHP no puede proteger un `.html` estático) y
  `admin_estadisticas.php?seccion=resumen|mas|menos|edad|busquedas|cobertura&dias=7|30|90`
  (solo GET, solo agregados). Su código está en `assets/admin.js` y `assets/admin.css`; las
  gráficas son SVG propio.
- `lib/`: código común. Todo endpoint empieza con `require_once __DIR__ . '/lib/bootstrap.php';`.
  - `config.php` (secretos) · `db.php` (`conexion()`) · `sesion.php` (sesión + autorización)
  - `cifrado.php` (AES-256-GCM) · `validacion.php` · `intentos.php` (límite de login)
  - `respuesta.php` (`responder`, `responder_error`, `leer_json_post`, `registrar_fallo`)
  - `python.php` (`ejecutar_python`) · `cuentas.php`
  - `documentos.php`: `hidratar_documentos()` arma la tarjeta que usan TODOS los endpoints
    (tipo, título, resumen, `meta`, `etiquetas`, y `grupo_id` o `tema` para su ilustración),
    `leer_ref_documento`, `documentos_relacionados`, `ruta_documento`
  - `estadisticas.php` (`registrar_consulta`, `registrar_eventos`, `registrar_sin_fallar`)
  - `admin_estadisticas.php`: las consultas del panel (una función por sección). `sesion.php` trae
    `requerir_admin()`
- `scripts_py/arboles/`: cinco árboles (anatomía, temas, equipamiento, nivel, patrón; `taxonomia.py` es la fuente única de
  nombres y vocabulario). `bosque.py`: `Bosque` = árboles + pertenencia de cada documento a nodos + una `AristasPar` por
  cada par de árboles (aristas derivadas, en memoria, con lift). `motor.py`: `MotorArboles`; la consulta «nombra» cero, uno o
  varios árboles (cero: recuperación en anatomía y temas; uno: salta al compañero; varios: intersección total, mejor par
  `interseccion_parcial` o `sin_interseccion`). El constructor de dos árboles se conserva. `catalogo.py`: catálogo y cruce
  de cualquier par. `patrones.py`: el árbol de Patrón de movimiento, una clasificación APROXIMADA del nombre del ejercicio
  por reglas de palabras clave (gana la primera regla que coincide; lo que no se reconoce queda en «Sin clasificar», no se
  adivina). Siempre que se muestre hay que avisar que es aproximado (`ARBOLES_APROXIMADOS`; la interfaz lo hace).
- `scripts_py/`: motor TF-IDF, `motor_arboles.py` (entrada de PHP), `catalogo_arboles.py` y `puente_arboles.py` (menús
  A+B de dos árboles cualesquiera), `medir_arboles.py` y `patron_sin_clasificar.py` (medición y reporte de la fase 6B), `recommender.py` (centroide + coseno por
  perfil), `db_config.py` (lee la misma config que PHP), `etiquetado.py` (lógica pura) y
  `generar_etiquetas.py` (llena las tablas de etiquetas y rutas; hay que volver a correrlo si
  cambia el contenido).
- `sql/esquema_cuentas.sql`: cuentas, perfiles, interacciones (por perfil), intentos_login.
  Es idempotente y no tiene `USE`: se aplica a la BD elegida.
- `sql/esquema_rutas_arboles.sql`: `documento_rutas` con una ruta POR ÁRBOL (clave `origen, doc_id, arbol`; ENUM con
  `patron` ya incluido). Se aplica después de `esquema_etiquetas.sql`. Idempotente.
- `sql/esquema_estadisticas.sql`: `eventos` (impresion/apertura/like; `perfil_id` NULL con
  `ON DELETE SET NULL`) y `consultas` (solo raíces; sin perfil ni texto original). Mismo estilo.
- `sql/esquema_etiquetas.sql`: `etiquetas`, `documento_etiquetas` y `documento_rutas`. Son
  tablas DERIVADAS: las regenera `generar_etiquetas.py`. Los nombres en español de músculo,
  equipamiento, nivel y modalidad, y los sinónimos, viven en `arboles/taxonomia.py`.
- `sql/esquema_admin.sql`: `cuentas.rol ENUM('usuario','admin') DEFAULT 'usuario'`. Idempotente.
- `herramientas/crear_admin.php`: ÚNICA forma de crear un administrador o dar el rol (solo CLI, pide
  la contraseña sin mostrarla).
- `sql/esquema_corpus.sql`: `articulos.origen_contenido` ('original' o 'generado').
- `corpus/`: lotes de artículos de la fase 6A (`lotes/lote_NN.csv`, su `.plan.csv` y `trabajo/`), `objetivos.json`
  (metas aprobadas), `consultas_referencia.json` (18 consultas) y `resultados/` (línea de base y estado tras cada
  lote). La fase 6A terminó con 17 lotes: 2 000 artículos (341 `original` y 1 659 `generado`). Bloqueada por HTTP.
  Herramientas en `scripts_py/`: `planear_lote.py`, `ensamblar_lote.py`, `validar_lote.py`,
  `importar_lote.py` y `consultas_referencia.py`.
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
8. En `index.html`, todo texto del servidor pasa por `esc()` antes de ir a `innerHTML` (o se
   asigna con `textContent`). `tests/test_interfaz.php` lo comprueba con un documento que trae
   HTML en título, texto y etiquetas.
9. Estadísticas: el registro nunca hace fallar ni retrasa la petición (`enviar_y_continuar()` +
   `registrar_sin_fallar()`). Las impresiones se guardan SIN perfil (si no, se unirían por
   `creado_en` con `consultas`). `consultas` nunca guarda el texto original ni el perfil.
10. Panel de administrador: el rol `admin` solo lo escribe `herramientas/crear_admin.php` (CLI);
   ningún endpoint web menciona la columna. `requerir_admin()` lee el rol de la BD en cada petición
   (401 sin sesión, 403 sin rol) y no confía en la sesión. La sesión de admin dura 15 min de
   inactividad. `admin_estadisticas.php` devuelve solo agregados y nunca `correo`, `nombre`,
   `fecha_nac`, `contrasena`, `perfil_id` ni `cuenta_id` (una barrera final lo comprueba; por eso las
   listas de músculos y temas usan la clave `concepto`). La edad se calcula en memoria y un rango
   con menos de 5 cuentas no se devuelve. Las cuentas admin no cuentan: ni como cuentas, perfiles o edad, ni por las
   aperturas y «me gusta» de sus perfiles (`sin_eventos_de_admin()` en cada consulta de eventos). Sus
   búsquedas e impresiones sí suman: no llevan perfil, a propósito.

## Pruebas

```
cd scripts_py && python -m pytest tests -v                  # incluye test_aislamiento.py
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php       # HTTP: 403, sesión, aislamiento
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php       # HTTP: eventos, consultas, purga
D:\Tools\SHAMP\php\php.exe tests\test_etiquetas.php          # HTTP: etiquetas, detalle, gráfica
D:\Tools\SHAMP\php\php.exe tests\test_arboles_n.php          # HTTP: catálogo de 4 árboles, cruce, descubrimiento, rutas
D:\Tools\SHAMP\php\php.exe tests\test_interfaz.php           # navegador: teclado, filtros, XSS, 375 px, contraste claro/oscuro
D:\Tools\SHAMP\php\php.exe tests\test_ilustraciones.php      # navegador: captura cada ilustración y cuenta píxeles
D:\Tools\SHAMP\php\php.exe tests\test_admin.php               # HTTP: panel, 401/403, sin datos personales, totales a mano
D:\Tools\SHAMP\php\php.exe tests\test_admin_interfaz.php      # navegador: panel, gráficas, CSV, 375 px, modo oscuro
```
`tests/datos_admin.php` crea el escenario fijo del panel (con los totales calculados a mano en su
encabezado); `tests/arnes.php` da al servidor de pruebas su propia carpeta de sesiones.
Las dos pruebas de navegador lanzan un script de Node (`tests/interfaz.mjs`,
`tests/ilustraciones.mjs`) que maneja Edge sin ventana con `tests/navegador.mjs` (protocolo de
DevTools, Node 22+, sin dependencias; `EDGE_PATH` cambia el navegador y `CAPTURAS=<carpeta>`
guarda capturas). Si la máquina está cargada pueden fallar por tiempo: repetirlas. No correr
dos pruebas a la vez: todas recrean la misma BD de pruebas.
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
mysql -uroot gym_buscador < sql/esquema_etiquetas.sql
mysql -uroot gym_buscador < sql/esquema_rutas_arboles.sql   # una ruta por árbol (fase 6B)
mysql -uroot gym_buscador < sql/esquema_admin.sql
php herramientas/crear_admin.php correo@dominio.com   # pide la contraseña; luego abrir admin.php
python scripts_py/generar_etiquetas.py # etiquetas y rutas; repetir si cambia el contenido
mysql -uroot gym_buscador < sql/esquema_corpus.sql
php herramientas/crear_demo.php        # imprime la contraseña demo una sola vez
```

## Avisos

- Los IDs de músculo (`ejercicios.grupo_id`) son los de `unirdataset/limpiar_ejercicios.py` y
  `taxonomia.MUSCULOS` (1=Pecho … 11=Antebrazos). La tabla `grupos_musculares` tenía los nombres
  desalineados; se corrigió con `sql/corregir_grupos_musculares.sql`. Ningún código la lee: la
  fuente de verdad es `taxonomia.py`.
- No existe la tabla `alimentos`. `postings.origen` solo tiene `ejercicios` y `articulos`.
- Las pruebas que dependen de fechas ("hace N días") ponen los eventos a las 12:00 para que un
  evento de hace 7 días caiga dentro de 30 días y fuera de 7 sin importar la hora a la que corran.
- `php -d` con una ruta que lleve `~` (rutas cortas de Windows, `ANAKAR~1`) necesita comillas:
  `-d "session.save_path=\"RUTA\""`.
- MariaDB no deja usar un alias de agregado dentro de una expresión del `ORDER BY`: repetir la
  expresión (`SUM(...) / SUM(...)`).
- Artículos nuevos: se agregan SOLO con `validar_lote.py` + `importar_lote.py` (marcan `generado`), y después hay que
  correr `indexer.py` (vacía y recalcula diccionario y postings) y `generar_etiquetas.py`; sin lo segundo los nuevos no
  tienen etiquetas ni ruta. Las etiquetas salen de `etiquetado.vocabulario_controlado()` (190); el tema y el músculo de
  un artículo los decide `taxonomia.py` con sus etiquetas, así que un artículo generado solo cae donde se quiere si sus
  etiquetas lo producen (el validador lo comprueba contra el plan). Hay que hacer copia de `articulos`, `diccionario` y
  `postings` antes del primer lote de una tanda (`backups/` está en `.gitignore`). Tras importar, comprobar el conteo
  en la BD: un script que encadene los pasos debe abortar si falla uno (en el lote 15 no lo hizo). Los artículos
  `generado` son cortos y genéricos y, con TF-IDF, desplazan a originales más específicos en varias consultas de
  referencia (ver `docs/Avances.md`, fase 6A).
- MariaDB (aquí): `max_allowed_packet` es 1 MB. Un `executemany` con miles de filas hace un solo `INSERT` que lo supera y el
  servidor corta la conexión («Lost connection»); `generar_etiquetas.py` inserta en bloques de 2 000 (hay una prueba).
- Regex de plural: `elevaciones?` o `laterales?` NO casan con «elevación» ni «lateral» (la `?` solo afecta a la última letra).
  Escribir `elevaci(?:on|ones)`, `lateral(?:es)?`. Lo mismo pasó con «escaladores?» en 6A.
- Árboles y vocabulario de consulta: el motor compara RAÍCES del stemmer, no palabras. Una palabra que nombre un
  equipamiento o un nivel no puede compartir raíz con otra que ya nombre un músculo o un tema («rodillo»/«rodilla»,
  «correas»/«correr», «banco»/«banca»; «ejercicio» es palabra de intención y se descarta). `test_arboles_n.py` revisa todas
  las frases. Los argumentos de línea de comandos con acento no son fiables en Windows: las claves de concepto van sin acentos.
- Colores: ninguno va fijo fuera de las variables de `:root` en `assets/estilos.css`, ni dentro
  de los SVG (usan variables o `currentColor`). De eso dependen el modo oscuro y las
  ilustraciones; `tests/test_ilustraciones.php` lo comprueba contando píxeles.
- Un comentario XML no admite dos guiones seguidos: en los SVG no se pueden escribir los nombres
  de las variables CSS (`--ilu-...`) dentro de `<!-- -->`.
- Avances del proyecto: `docs/Avances.md`. Estructura de los árboles: `ESTRUCTURA.md`.
