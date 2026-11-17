# Avances — Módulo de cuentas y perfiles con protección de información

**Tema:** protección de información en un sistema de Recuperación de la Información.
**Fecha:** 11 de noviembre de 2026.

## 1. Problema de partida

El recomendador (centroide TF-IDF de los documentos con "me gusta" + similitud del coseno)
funcionaba para un solo usuario fijo (`usuario_id = 1`, escrito en el código). Al revisarlo se
encontraron estos riesgos:

| Riesgo | Dónde estaba |
|---|---|
| Sin cuentas: todos compartían el mismo historial | `registrar_interaccion.php`, `recommender.py` |
| La búsqueda marcaba los "me gusta" de **cualquier** usuario | `buscar.php` (consulta sin filtro de usuario) |
| Inyección SQL de segundo orden: el recomendador armaba SQL con f-string usando `origen`, que el cliente enviaba sin validar | `recommender.py`, `registrar_interaccion.php` |
| Consultas sin preparar | `recomendaciones.php` |
| Mensajes de excepción y salida cruda de Python enviados al navegador | todos los endpoints, `debug_motor` |
| Credenciales de la BD repetidas en el código y en Git | 4 PHP + `db_config.py` |
| HTML de las tarjetas sin escapar (XSS) | `index.html` |

## 2. Qué se construyó

**Modelo:** una **cuenta** (correo único + contraseña) tiene hasta **4 perfiles**. Cada perfil
tiene su propio historial. El recomendador calcula el centroide **solo** con el historial del
perfil activo, así que dos personas que comparten una cuenta reciben recomendaciones
independientes.

```
cuentas 1 ──< perfiles (máx. 4) 1 ──< interacciones
   │  ON DELETE CASCADE        │  ON DELETE CASCADE
   └─ correo (en claro, normalizado), contrasena_hash (bcrypt),
      nombre_cifrado + fecha_nac_cifrada (AES-256-GCM)
intentos_login (SHA-256 del correo + IP, sin clave foránea a propósito)
```

### Requisitos y cómo se cumplen

| # | Requisito | Implementación |
|---|---|---|
| 1 | Cuenta con hasta 4 perfiles | `perfiles.php` bloquea la fila de la cuenta (`SELECT … FOR UPDATE`) antes de contar. El trigger `trg_perfiles_max4` es la segunda barrera |
| 2 | Historial y centroide por `perfil_id` | `interacciones.perfil_id` con clave foránea. `recommender.py` lee el historial con `WHERE perfil_id = %s`. El centroide no se guarda: se recalcula en cada petición. El perfil sale **solo de la sesión** |
| 3 | Contraseñas seguras | `password_hash` (bcrypt) / `password_verify`, más `password_needs_rehash` al iniciar sesión |
| 4 | Consultas preparadas | PDO con `EMULATE_PREPARES=false`. La f-string del recomendador se sustituyó por un `JOIN` con parámetros |
| 5 | Autorización (403) | `requerir_perfil_propio()` en `seleccionar_perfil.php` y `perfiles.php` (eliminar). El `DELETE` además filtra por `cuenta_id` |
| 6 | Sesiones seguras | `session_regenerate_id(true)` al iniciar sesión y al cambiar de perfil. Cookie `HttpOnly` + `SameSite=Strict` (+ `Secure` con HTTPS). `use_strict_mode`. 30 min sin actividad cierran la sesión. El cierre de sesión vacía la sesión, borra la cookie y llama a `session_destroy()` |
| 7 | Validación y límite de intentos | Correo con `FILTER_VALIDATE_EMAIL`. Contraseña de 10 a 72 bytes con letras y números. 5 fallos por correo o 20 por IP en 15 min dan HTTP 429. Mismo mensaje y mismo tiempo de respuesta exista o no el correo (hash ficticio) |
| 8 | AES-256-GCM | Solo nombre completo y fecha de nacimiento. Nonce aleatorio por valor; el nombre del campo va como dato autenticado (AAD). La clave está en `config/config.local.ini.php` (en `.gitignore`; además bloqueada por HTTP) |
| 9 | Nada sensible en logs ni en `debug_motor` | `registrar_fallo()` guarda solo la clase de la excepción, el SQLSTATE y una referencia. `debug_motor = {codigo, ref}`. El stderr de Python se descarta |
| 10 | Borrado en cascada | Claves foráneas `ON DELETE CASCADE`: borrar un perfil borra su historial y borrar la cuenta borra todo. `intentos_login` se limpia por el hash del correo |

**Extras de protección:** CSRF (los POST exigen `application/json`), XSS (`esc()` en todas las
tarjetas), carpetas `config/`, `lib/`, `sql/`, `herramientas/` y `tests/` bloqueadas por HTTP,
lista blanca de `origen`, y versión de Chart.js fijada.

## 3. Evidencia (pruebas)

Todas las pruebas corren sobre `gym_buscador_test` con contenido sintético: 5 ejercicios de
pecho, 5 de pierna y 2 artículos. Se niegan a correr si la base no termina en `_test`.

**`scripts_py/tests/test_aislamiento.py` (pytest): 18 pruebas, todas pasan.**
- Dos perfiles de la **misma cuenta** (Pecho y Pierna) obtienen recomendaciones distintas y sin
  documentos en común. Cada uno recibe solo documentos de su universo, y su perfil semántico
  refleja solo su historial.
- Un perfil sin "me gusta" recibe *cold start* aunque sus perfiles hermanos tengan historial.
- Un "me gusta" en un perfil no cambia las recomendaciones de otro.
- Un "espía" de SQL comprueba que **toda** lectura de `interacciones` lleva
  `perfil_id = %s` con el perfil pedido.
- `perfil_id` inválido (`0`, `-1`, `"1 OR 1=1"`, `True`…) se rechaza.
- Borrado en cascada de perfil y de cuenta. Límite de 4 perfiles.

**`tests/test_autorizacion.php` (CLI, HTTP real): 24 comprobaciones, todas pasan.**
- **Un `perfil_id` ajeno devuelve 403** al seleccionarlo y al eliminarlo. Uno inexistente también
  devuelve 403, para no revelar qué IDs existen.
- De punta a punta, Pecho y Pierna de la misma cuenta reciben recomendaciones distintas. La cuenta
  B no ve los "me gusta" de A. Un `perfil_id` ajeno en el cuerpo de la petición se ignora.
- Cookie `HttpOnly` y `SameSite=Strict`, ID de sesión nuevo tras iniciar sesión, cookie inútil
  tras cerrar sesión, 429 al 6.º intento fallido.

**Validación de las pruebas:** se rompió a propósito el filtro por perfil del recomendador
(fallaron 3 pruebas de pytest) y la verificación de dueño en PHP (fallaron 3 comprobaciones de
403). Con el código correcto vuelven a pasar todas. Con la verificación rota, el perfil de A
tampoco se pudo borrar, porque el `DELETE` filtra por `cuenta_id` (defensa en profundidad).

**Prueba con datos reales (Apache + `gym_buscador`, cuenta demo):**

| Perfil | Perfil semántico | Primeras recomendaciones |
|---|---|---|
| Pecho | pech, pectoral, band, apertur, banc | 1695, 1749, 1633, 1755, 1672 |
| Pierna | pantorrill, talon, prens, toqu, plataform | 2733, 2680, 1505, 1478, 1504 |

Ninguna recomendación coincide entre los dos perfiles.

## 4. Cómo probarlo

```
D:\Tools\SHAMP\mysql\bin\mysql.exe -uroot gym_buscador < sql\esquema_cuentas.sql
D:\Tools\SHAMP\php\php.exe herramientas\crear_demo.php      (imprime la contraseña una vez)
```
Abrir `http://localhost/buscador_gym/`, entrar con `demo@buscador-gym.local`, elegir "Pecho",
luego "Pierna", y comparar.

## 5. Decisiones

- **Centroide recalculado, no guardado:** no queda desactualizado y es más fácil demostrar el
  aislamiento.
- **Solo se cifran nombre completo y fecha de nacimiento.** No se guardan datos de salud. El
  correo va en claro porque debe ser único y buscable para iniciar sesión.
- **Los "me gusta" anteriores (usuario 1) se descartaron.**
- **Las pruebas usan contenido sintético** y no una copia de la base real: los resultados se
  pueden predecir y nunca se lee la base real.

## 6. Pendientes / observaciones

- **Corregido:** la tabla `grupos_musculares` tenía los nombres desalineados con los IDs (el id 1,
  que tiene los 262 ejercicios de *Chest*, decía "Cuádriceps"). `ejercicios.grupo_id` y los
  árboles siempre estuvieron bien. Se corrigieron solo los nombres
  (`sql/corregir_grupos_musculares.sql`), y los 11 conteos coinciden con el dataset original.
- No hay endpoint para eliminar la cuenta (el borrado en cascada sí existe en la BD y está
  probado). Tampoco hay recuperación de contraseña: quedó fuera del alcance.
- En local la cookie no lleva `Secure` (no hay HTTPS). En un servidor con HTTPS se activa sola.

---

# Fase 2 — Registro de eventos para estadísticas

**Fecha:** 14 de noviembre de 2026. **Rama:** `fase-2-estadisticas`.

**Objetivo:** medir qué contenido se consume y qué búsquedas fallan, sin guardar datos
personales.

## 1. Qué se hizo

**Esquema** (`sql/esquema_estadisticas.sql`, idempotente, sin `USE`):

| Tabla | Columnas | Protección |
|---|---|---|
| `eventos` | `perfil_id` (NULL, FK `ON DELETE SET NULL`), `tipo` (`impresion`/`apertura`/`like`), `origen`, `doc_id`, `creado_en` | Al borrar el perfil, el evento queda para el conteo pero sin perfil. Las impresiones siempre van **sin perfil** |
| `consultas` | `raices`, `via`, `n_resultados`, `creado_en` | Sin `perfil_id` y sin el texto original: solo las raíces de la consulta, sin repetir y en orden alfabético |

Índices: `eventos (origen, doc_id, tipo)`, `eventos (creado_en)`, `consultas (creado_en)`.

**Por qué las impresiones no llevan perfil:** la fila de `consultas` y las impresiones de esa
búsqueda se crean en el mismo segundo. Si las impresiones llevaran `perfil_id`, unir las dos
tablas por `creado_en` diría qué perfil hizo cada búsqueda.

**Código:**

| Archivo | Cambio |
|---|---|
| `lib/estadisticas.php` | `registrar_consulta()`, `registrar_eventos()` (un solo `INSERT` múltiple), `normalizar_raices()`, `registrar_sin_fallar()` (ante un error solo llama a `registrar_fallo()`) |
| `lib/respuesta.php` | `enviar_y_continuar()`: manda la respuesta completa (`Content-Length` + `Connection: close` + `flush`) y devuelve el control. Apache corre PHP como módulo, así que `fastcgi_finish_request()` no existe |
| `lib/documentos.php` | `leer_ref_documento()`: validación compartida de `doc_id` (entero positivo) y `origen` (lista blanca) |
| `buscar.php` | Responde primero. Luego guarda una fila en `consultas` y las impresiones de lo mostrado (TF-IDF + artículo descubierto). Guarda `raices_consulta` (lo que escribió el usuario), no las raíces expandidas por los árboles. Sin raíces no registra nada |
| `registrar_interaccion.php` | Evento `like` al dar "me gusta" (quitarlo no es un evento). Si el registro falla, el like se guarda igual |
| `registrar_evento.php` (nuevo) | POST JSON `{doc_id, origen}` → evento `apertura` del perfil de la sesión. Ignora `perfil_id` y `tipo` del cuerpo. Responde 401/409/415/405/422/404 |
| `index.html` | Clic en una tarjeta (salvo el corazón) o en su título abre un diálogo con el texto completo y registra la apertura. Si falla, el usuario no ve ningún error |
| `herramientas/purgar_estadisticas.php` (nuevo) | Solo CLI: borra `consultas` y `eventos` de más de 180 días, en lotes de 5000 |

## 2. Qué falló durante el desarrollo

La primera versión de `test_estadisticas.php` tuvo 3 fallos, todos de la prueba:
1. Una variable `$total` pisaba el contador global del arnés.
2. Los `doc_id` marcadores de la purga ya tenían impresiones reales.
3. Hubo una **carrera**: el cliente recibía la respuesta y leía la BD antes de que el servidor
   terminara de registrar. Esto confirma que el registro ya no retrasa la respuesta. La prueba
   ahora espera con otra petición, porque `php -S` atiende una a la vez.

## 3. Cómo probarlo

```
D:\Tools\SHAMP\mysql\bin\mysql.exe -uroot gym_buscador < sql\esquema_estadisticas.sql
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php      49 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php      24 comprobaciones (sin cambios)
cd scripts_py && python -m pytest tests -q                  53 pasan, 8 se saltan (piden CSV_EJERCICIOS/CSV_ARTICULOS)
D:\Tools\SHAMP\php\php.exe herramientas\purgar_estadisticas.php
```

`test_estadisticas.php` comprueba lo siguiente:
- El evento va al perfil de la sesión aunque el cuerpo traiga otro `perfil_id`.
- Al borrar el perfil, sus eventos quedan con `perfil_id` NULL y no se pierde ninguno.
- `consultas` solo tiene esas 5 columnas, no contiene el texto original y sus raíces van sin
  repetir y ordenadas.
- Las impresiones no llevan perfil.
- Una búsqueda sin resultados queda con `n_resultados = 0`.
- Si se borran las tablas `consultas` y `eventos`, la búsqueda sigue respondiendo 200 con
  resultados y el like se guarda.
- La purga borra lo de 181 días, conserva lo de 179 y no se puede lanzar por HTTP.

**Validación de la prueba:** se rompieron a propósito tres cosas: el perfil tomado del cuerpo, el
texto original guardado en `consultas` y el registro relanzando la excepción. Fallaron
7 comprobaciones. Con el código correcto vuelven a pasar las 49.

**En el navegador:** buscar "press banca", abrir una tarjeta y revisar:

```sql
SELECT tipo, perfil_id, origen, doc_id FROM eventos ORDER BY id DESC LIMIT 5;
SELECT * FROM consultas ORDER BY id DESC LIMIT 5;
```

## 4. Pendientes

- Esquema aplicado también a `gym_buscador` (dos veces, sin errores; la purga corre sobre la
  BD real). Por Apache: `registrar_evento.php` da 405 con GET y 401 sin sesión; `lib/`, `sql/`,
  `tests/` y `herramientas/` dan 403.
- **Probado contra Apache y la BD real con la cuenta demo** (con `curl`; las 64 filas de
  `eventos` y las 3 de `consultas` que generó la prueba se borraron después):
  - `registrar_evento.php` con `perfil_id: 4` y `tipo: like` en el cuerpo guardó una
    `apertura` del perfil 3 (Pecho, el de la sesión).
  - **El registro no retrasa la respuesta bajo mod_php:** con `consultas` bloqueada
    (`LOCK TABLES ... WRITE` durante 40 s desde otra sesión), la búsqueda respondió 200 en
    12.6 s con `Content-Length` y `Connection: close`. En ese momento la fila todavía no
    existía; se escribió al liberar el bloqueo.
  - Las búsquedas tardan unos 13 s, pero no por el registro: `motor_arboles.py` solo tarda
    12.1 s sobre la BD real. Es un problema anterior a esta fase.
- Falta comprobar el diálogo de detalle en un navegador: que se abra al hacer clic en la
  tarjeta, que se cierre con "Cerrar", con Esc y con clic fuera, y que el corazón no lo abra.
- El artículo descubierto por los árboles y las tarjetas de la vista A+B no abren el detalle.
  El artículo descubierto trae su texto cortado a 150 caracteres.
- `registrar_evento.php` no tiene límite de frecuencia: un usuario con sesión puede inflar las
  aperturas de un documento.
- Las recomendaciones (`recomendaciones.php`) no registran impresiones: no se pidió.
- No hay todavía consultas ni pantalla de estadísticas: solo se recogen los datos.
- La purga no está programada: hay que correrla a mano o con el Programador de tareas.

---

# Fase 3 — Interfaz, etiquetas y detalle de tarjeta

**Fecha:** 14 al 16 de noviembre de 2026. **Rama:** `fase-3-interfaz`.

## 1. Qué se hizo

**Etiquetas** (`sql/esquema_etiquetas.sql`, idempotente, sin `USE`):

| Tabla | Para qué |
|---|---|
| `etiquetas` | `nombre_normalizado` (único), `nombre_visible`, `tipo` (musculo, equipamiento, nivel, modalidad, tema) |
| `documento_etiquetas` | Qué etiquetas tiene cada documento (`origen`, `doc_id`, `etiqueta_id`) |
| `documento_rutas` | Ruta de cada documento en su árbol, por ejemplo "Cuerpo humano > Tren superior > Pecho > Barra" |

Las tres son tablas derivadas. `scripts_py/generar_etiquetas.py` las llena de nuevo completas en
una sola transacción y conserva los `id` de las etiquetas que siguen existiendo.

- **Ejercicios:** músculo, equipamiento, nivel y modalidad salen de sus columnas, con nombres en
  español definidos en `taxonomia.py` (Beginner pasa a Principiante, Dumbbell a Mancuernas).
  "Other" y el equipamiento vacío no generan etiqueta.
- **Artículos:** su columna `etiquetas`. El tipo es músculo o equipamiento si la etiqueta está
  en los diccionarios de `taxonomia.py`; si no, tema.
- **Normalización:** sin acentos, en minúsculas, con sinónimos unidos (pectoral y pecho, gemelos
  y pantorrilla) y plurales unidos cuando existe el singular (rodillas y rodilla).
- **Un nombre, una etiqueta:** "Fuerza" (modalidad de un ejercicio) y "fuerza" (etiqueta de un
  artículo) son la misma. Si un nombre aparece con dos tipos gana músculo, luego equipamiento,
  nivel, modalidad y tema.
- **Acentos:** las etiquetas de los artículos vienen sin acento. El nombre visible se recupera
  con la forma más frecuente de cada palabra en el texto de los documentos ("sueno" se muestra
  como "Sueño").
- Con el contenido real salen 930 etiquetas y 13 491 asignaciones (simulación de solo lectura).

**Backend:**

| Archivo | Cambio |
|---|---|
| `lib/documentos.php` | `hidratar_documentos()` devuelve la misma tarjeta en todas partes: tipo, título, resumen de hasta 280 caracteres, `meta` (músculo, equipamiento, nivel) y `etiquetas`. Nuevas `etiquetas_de_documentos()`, `documentos_relacionados()` y `ruta_documento()` |
| `detalle.php` (nuevo) | GET: texto completo, todas las etiquetas, ruta en el árbol, si el perfil de la sesión le dio "me gusta" y hasta 4 relacionados |
| `etiquetas.php` (nuevo) | GET: catálogo de etiquetas con su conteo. Acepta `?tipo=` validado contra una lista |
| `recommender.py` | Devuelve `perfil_terminos`: los 8 términos más fuertes con su peso y la palabra completa ("pech" se muestra como "pecho"), tomada del texto de los documentos con "me gusta" |
| `buscar.php`, `recomendaciones.php`, `menus.php` | Usan las tarjetas nuevas. El servidor ya no manda textos técnicos ("Salto Semántico", "Similitud: x%") ni el mensaje de perfil vacío |

**Relacionados:** se ordenan por etiquetas en común. Cada etiqueta compartida suma su peso de
tipo (músculo 3, tema 2, equipamiento 1.5, modalidad 1, nivel 0.5) dividido entre
ln(1 + documentos con esa etiqueta), así que las etiquetas raras pesan más.

**Interfaz** (`index.html` reescrito y `assets/estilos.css` nuevo):

- Barra superior fija con el nombre del sitio, la búsqueda y el menú del perfil activo (cambiar
  perfil, cerrar sesión). Pestañas "Búsqueda y recomendaciones" y "Explorar por árboles".
- Panel lateral con filtros sobre los resultados cargados (tipo, nivel, equipamiento, etiquetas)
  y la gráfica del perfil. En teléfono el panel se pliega.
- Tarjetas con la misma altura y estructura: tipo, título, resumen de 3 líneas, metadatos y
  etiquetas.
- Detalle en un `<dialog>` modal: texto completo, etiquetas, ruta, "me gusta" y relacionados.
  Se cierra con Escape y con un botón, y Tab no sale de la ventana. Al abrirlo se llama a
  `registrar_evento.php`.
- Clic en una etiqueta (tarjeta, panel o detalle) filtra los resultados. Nivel y equipamiento
  aceptan cualquiera de los marcados; las demás etiquetas deben cumplirse todas.
- Gráfica "Lo que más pesa en tus recomendaciones": barras horizontales en HTML y CSS, un solo
  color, valor al lado. Se quitó Chart.js. Sin "me gusta" solo hay una frase.
- Sistema de diseño con variables CSS de color, tipografía, espaciado y radios. Texto normal con
  contraste 15:1 y texto secundario 7.5:1 sobre blanco.
- Sin emojis ni textos de relleno. "Razón algorítmica" pasó a "Por qué aparece esto", "Salto
  semántico" a "Relacionado con tu búsqueda", y "cold start" no se muestra.
- El perfil sin "me gusta" ve una frase que dice qué hacer y los músculos del catálogo como
  punto de partida (cada uno lanza esa búsqueda).

## 2. Qué falló durante el desarrollo

1. **Relacionados mal ordenados (código).** Para el press de banca salía la sentadilla con barra
   antes que las aperturas de pecho, porque "Barra" era más rara que "Pecho". Se corrigió con el
   peso por tipo de etiqueta.
2. **El foco salía del detalle (código).** `<dialog>` impide llegar al contenido de atrás, pero
   Tab en el último elemento pasaba a la barra del navegador. Ahora Tab cicla dentro.
3. **Detalle atascado en "Cargando…" (código).** Si se reabría un documento justo después de
   cerrar el detalle, el evento `close` llegaba tarde y borraba el estado del que se acababa de
   abrir. Ahora cada apertura lleva su número y el cierre no toca un detalle ya reabierto. Lo
   encontró la prueba de teclado, que al principio fallaba de forma intermitente.
4. **Contenido de prueba con músculos mal numerados.** `contenido_test.sql` usaba la numeración
   antigua (pecho con `grupo_id` 5). Se alineó con `taxonomia.MUSCULOS`.
5. **La prueba de interfaz se colgó una vez** más de 10 minutos: las órdenes a Edge no tenían
   tiempo límite. Ahora cada orden vence a los 30 s y la prueba completa a los 5 minutos.
6. **El disco C: se llenó** durante la fase (0 MB libres) y hubo que parar hasta liberar espacio.
   Las pruebas usan la carpeta temporal de C:.

## 3. Cómo probarlo

```
D:\Tools\SHAMP\mysql\bin\mysql.exe -uroot gym_buscador < sql\esquema_etiquetas.sql
python scripts_py\generar_etiquetas.py                      llena etiquetas y rutas

cd scripts_py && python -m pytest tests -q                  74 pasan, 8 se saltan (piden CSV)
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php      24 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php      49 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_etiquetas.php         34 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_interfaz.php          72 del navegador + 3 de la BD
```

`test_interfaz.php` necesita Node 22 o posterior y Edge (o Chrome; ruta alternativa en
`EDGE_PATH`). No instala nada: maneja Edge sin ventana con el protocolo de DevTools. Con
`CAPTURAS=<carpeta>` guarda capturas de pantalla. Comprueba, entre otras cosas:

- El detalle se abre con Enter, Tab no sale de él, Escape y "Cerrar" lo cierran y el foco vuelve
  a la tarjeta.
- El filtro por etiqueta reduce los resultados desde la tarjeta, el panel y el detalle.
- Un documento con HTML en título, texto y etiquetas se muestra como texto: no se crea ningún
  nodo ni corre su script. Con `esc()` desactivado a propósito, estas comprobaciones fallan.
- A 375 px no hay desplazamiento horizontal en ninguna vista y el detalle cabe en pantalla.
- Todas las tarjetas miden lo mismo y el resumen no pasa de 3 líneas.
- Ninguna pantalla tiene emojis ni vocabulario técnico.

## 4. Pendientes

- **El esquema de etiquetas solo está aplicado en `gym_buscador_test`.** Hasta aplicarlo y
  correr `generar_etiquetas.py` en `gym_buscador`, la búsqueda y las recomendaciones de esta
  rama fallan contra la BD real, porque leen `documento_etiquetas`.
- Si cambia el contenido (ejercicios o artículos), hay que volver a correr
  `generar_etiquetas.py`.
- Algunas etiquetas quedan sin acento ("Fisiologia", "Planificacion") porque así están escritas
  en el texto de los artículos.
- Los ejercicios solo tienen 4 etiquetas, así que muchos empatan como relacionados y el
  desempate es por `id`.
- El filtro actúa sobre los resultados ya cargados (hasta 20 en una búsqueda), no sobre todo el
  catálogo. Fue la opción elegida.
- Cuando la búsqueda no encuentra relación entre dos conceptos ya no se muestra la explicación;
  ese caso sigue visible en "Explorar por árboles".
- No hay modo oscuro. Los colores ya están en variables, así que agregarlo es redefinirlas.
- La prueba de interfaz solo corre en Edge o Chrome; no se probó en Firefox ni Safari.
- Las búsquedas contra la BD real siguen tardando unos 13 s por `motor_arboles.py` (problema
  anterior a esta fase).
