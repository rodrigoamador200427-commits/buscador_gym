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

- **Resuelto el 16 de noviembre (fase 4):** el esquema de etiquetas ya está aplicado en
  `gym_buscador` y `generar_etiquetas.py` corrió ahí: 930 etiquetas, 13 491 asignaciones y
  3189 rutas (una por documento). Ejercicios, artículos y cuentas no cambiaron.
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
- El modo oscuro se agregó en la fase 4.
- La prueba de interfaz solo corre en Edge o Chrome; no se probó en Firefox ni Safari.
- Las búsquedas contra la BD real siguen tardando unos 13 s por `motor_arboles.py` (problema
  anterior a esta fase).

---

# Fase 4 — Ilustraciones por músculo y por tema

**Fecha:** 16 de noviembre de 2026. **Rama:** `fase-4-ilustraciones` (sale de `fase-3-interfaz`).

## 1. Qué se hizo

Todos los dibujos son originales del proyecto, hechos a mano con formas simples. No se copió
ni se calcó ninguna imagen.

| Archivo | Contenido |
|---|---|
| `assets/anatomia/frontal.svg` | Cuerpo humano esquemático de frente, de una sola tinta. Regiones con id: `hombro`, `pecho`, `biceps`, `antebrazos`, `abdomen`, `cuadriceps` |
| `assets/anatomia/posterior.svg` | El mismo cuerpo de espaldas. Regiones: `hombro`, `espalda`, `triceps`, `antebrazos`, `gluteo`, `isquiotibiales`, `pantorrilla` |
| `assets/temas/pictogramas.svg` | Un pictograma geométrico y sin texto por cada uno de los 9 temas del árbol de Temas, más uno de respaldo |
| `assets/ilustraciones.js` | `ilustracion(origen, grupo_id_o_tema)` devuelve el SVG adecuado con su título accesible |

**Una ilustración por grupo muscular sin duplicar el dibujo.** Hay un archivo por vista, no uno
por músculo. `ilustracion()` toma el cuerpo con `<use href="assets/anatomia/frontal.svg#cuerpo">`
y resalta la región con una variable CSS (`--ilu-pecho`, `--ilu-espalda`…) que el archivo lee.
Corregir el dibujo en un solo lugar corrige las 11 ilustraciones.

| grupo_id | Músculo | Vista | | grupo_id | Músculo | Vista |
|---|---|---|---|---|---|---|
| 1 | Pecho | frontal | | 7 | Isquiotibiales | posterior |
| 2 | Espalda | posterior | | 8 | Pantorrilla | posterior |
| 3 | Hombro | frontal | | 9 | Glúteo | posterior |
| 4 | Bíceps | frontal | | 10 | Abdomen | frontal |
| 5 | Tríceps | posterior | | 11 | Antebrazos | frontal |
| 6 | Cuádriceps | frontal | | | | |

**Pictogramas:** Fuerza (barra con discos), Hipertrofia (núcleo con anillos), Resistencia
(pulso), Técnica y biomecánica (palanca con su ángulo), Planificación (calendario), Recuperación
(luna), Prevención y movilidad (escudo con cruz), Alimentación (plato con cubiertos),
Suplementación (cápsula). Respaldo: una hoja de documento.

**Colores:** ningún dibujo lleva un color fijo. Cada región se pinta con su variable y, si no
existe, con `currentColor`. Los valores salen de `assets/estilos.css`
(`--color-ilustracion-fondo`, `-base`, `-resaltado`, `-tinta`).

**Respaldo:** un `grupo_id` desconocido muestra el cuerpo sin ninguna región resaltada
("Ejercicio sin grupo muscular asignado"); un tema desconocido, el pictograma de documento.

**En la interfaz:**

- **Tarjetas:** empiezan con un recuadro de proporción fija 16:9. Dentro va la ilustración con
  medio cuerpo (la mitad superior o inferior, según el músculo), que se ve 1.8 veces más grande
  que el cuerpo entero. Una foto puesta ahí ocupa el mismo recuadro (`object-fit: cover`).
- **Detalle:** el cuerpo completo, a 400 px de alto, en una columna a la izquierda del texto.
  En teléfono va arriba.
- **Título accesible:** cada SVG lleva `role="img"` y un `<title>` enlazado con
  `aria-labelledby`, por ejemplo "Músculo trabajado: pecho" o "Tema del artículo: fuerza".
- **Datos:** `hidratar_documentos()` agrega a cada tarjeta `grupo_id` (ejercicios) o `tema`
  (artículos; es el último nodo de su ruta en `documento_rutas`).

**Modo oscuro (decidido en esta fase):** toda la interfaz sigue la preferencia del sistema
(`prefers-color-scheme`). Es el mismo sistema de variables con otros valores. Los pocos colores
que seguían fijos (texto sobre botones de acento, aviso, sombra, velo del detalle) pasaron a
variables. Contraste en oscuro: texto 13:1, texto secundario 8:1, texto sobre acento 8:1.

## 2. Verificación

Se hizo una captura de cada ilustración, en tamaño de tarjeta y de detalle, en claro y en
oscuro (88 capturas), y se revisaron de dos formas:

- **A ojo:** en las 11 se distingue el músculo resaltado y la vista es la correcta. Las hojas
  con todas están en `docs/capturas/ilustraciones/`.
- **Contando píxeles** (`tests/ilustraciones.mjs` decodifica cada PNG):

| Comprobación | Resultado |
|---|---|
| Área resaltada en la tarjeta | Entre 345 px (antebrazos) y 2220 px (espalda). Mínimo exigido: 250 |
| Área resaltada en el detalle | Entre 788 px (antebrazos) y 5137 px (espalda). Mínimo exigido: 600 |
| Contraste del resaltado con el cuerpo atenuado | 4.3:1 en claro y 3.3:1 en oscuro |
| Respaldo de ejercicios | 0 píxeles resaltados |
| Colores fijos | Con una paleta de prueba puesta solo con las variables CSS, el 0.000 % de los píxeles de las 44 capturas queda sin explicar |

- **Todos los `grupo_id` tienen ilustración:** los 11 de `taxonomia.MUSCULOS`, los de la BD de
  pruebas y, revisado a mano en `gym_buscador`, los 11 de `grupos_musculares` (2848 ejercicios,
  ninguno con `grupo_id` nulo). Los 341 artículos reales caen en los 9 temas con pictograma.
- **Ningún enlace externo:** ni en los SVG, ni en `ilustraciones.js`, `estilos.css` o
  `index.html`. En el navegador, todo lo que se carga sale del mismo sitio.
- **La foto no mueve el diseño:** se sustituyó la ilustración de una tarjeta por una imagen
  vertical de 600 x 1500 y no cambió ni la altura de la tarjeta ni la posición del título.

## 3. Qué falló durante el desarrollo

1. **Comentarios XML inválidos (dibujos).** Escribí los nombres de las variables CSS, que
   empiezan con dos guiones, dentro de comentarios de los SVG. XML no admite dos guiones
   seguidos en un comentario. Lo detecté antes de probar y reescribí los comentarios.
2. **El músculo no se veía más grande en el detalle (diseño).** Con el detalle a 300 px de
   alto, cada músculo medía casi lo mismo que en la tarjeta. Se pasó a dos columnas con la
   figura a 400 px.
3. **Comparar el tema claro con el oscuro no sirve para buscar colores fijos (prueba).** Los dos
   temas comparten grises parecidos y la prueba los confundía. Se cambió por la paleta de
   prueba de colores inconfundibles.
4. **Las esquinas redondeadas contaban como "color ajeno" (prueba).** Asomaba el blanco de la
   tarjeta. En esa pasada las esquinas se ponen rectas.
5. **Dos comprobaciones de HTML contaban un número fijo de `<script>` (prueba).** Al cargar
   `ilustraciones.js` hay dos. Ahora comparan contra los que había antes de buscar.
6. **Una corrida de la prueba de interfaz se arrastró hasta el tope de 5 minutos.** Coincidió
   con el arranque del Edge del sistema. Repetida, pasó. Si la máquina está cargada, la prueba
   del navegador puede fallar por tiempo: hay que repetirla.

**Validación de la prueba:** se puso a propósito un color fijo en `frontal.svg` y se apuntó
tríceps a una región que no existe en su vista. Fallaron 5 comprobaciones, tanto las que leen
los archivos como las que cuentan píxeles. Con los archivos correctos pasan todas.

## 4. Cómo probarlo

```
D:\Tools\SHAMP\php\php.exe tests\test_ilustraciones.php [carpeta]   85 del navegador + 12
D:\Tools\SHAMP\php\php.exe tests\test_interfaz.php                  85 del navegador + 3
D:\Tools\SHAMP\php\php.exe tests\test_etiquetas.php                 34 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php              49 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php              24 comprobaciones
cd scripts_py && python -m pytest tests -q                          74 pasan, 8 se saltan
```

Con una carpeta como argumento, `test_ilustraciones.php` guarda ahí las capturas de cada
ilustración. Para verlo en el navegador: entrar a `http://localhost/buscador_gym/`, buscar
"press banca" y abrir una tarjeta. Para ver el modo oscuro, cambiar el tema del sistema o
simularlo en las herramientas de desarrollo (Rendering → `prefers-color-scheme`).

## 5. Pendientes

- **Las ramas `fase-3-interfaz` y `fase-4-ilustraciones` no tienen push.** La fase 4 sale de la
  fase 3, así que hay que fusionar primero la 3.
- Las ilustraciones y el modo oscuro solo se probaron en Edge. `<use>` hacia otro archivo con
  variables CSS es estándar, pero falta mirarlo en Firefox y Safari.
- No hay un botón para elegir el tema: sigue al sistema.
- La figura es esquemática y única (no hay versiones por sexo ni complexión).
- La espalda es una sola región (trapecio, dorsal y lumbar juntos), igual que en la taxonomía.
- Hombro y antebrazos existen en las dos vistas, pero se muestran siempre de frente.
- Los relacionados del detalle no llevan ilustración.
- El recuadro de la tarjeta está listo para fotos, pero no hay fotos ni dónde guardarlas.
- La vista de árboles y el artículo relacionado con la búsqueda usan las mismas tarjetas, así
  que también muestran ilustración; no tienen pruebas propias de esto.


---

# Fase 5 — Panel de administrador

**Fecha:** 17 de noviembre de 2026. **Rama:** `fase-5-admin` (sale de `main`, que ya incluye las fases 3 y 4).

## 1. Qué se hizo

**Esquema** (`sql/esquema_admin.sql`, idempotente, sin `USE`): `cuentas.rol ENUM('usuario','admin') NOT NULL
DEFAULT 'usuario'`. Se agrega solo si la columna no existe; las cuentas que ya existían quedan como `usuario`.

**Acceso** (lo importante de la fase):

| Pieza | Qué hace |
|---|---|
| `herramientas/crear_admin.php` | Única forma de obtener el rol `admin`. Solo línea de comandos. Pide la contraseña dos veces **sin mostrarla** (PowerShell `Read-Host -AsSecureString` en Windows, `stty -echo` en otros). Si el correo ya tiene cuenta, solo le cambia el rol y conserva su contraseña |
| `registro.php` y demás endpoints web | Nunca mencionan la columna `rol`. Un `rol: "admin"` en el cuerpo se ignora |
| `requerir_admin()` en `lib/sesion.php` | 401 sin sesión; 403 si el rol leído **de la BD en esa petición** no es `admin`. No basta el rol guardado en la sesión: si se quita el rol, la siguiente petición ya recibe 403 |
| Sesión de administrador | 15 minutos de inactividad (900 s); un usuario normal conserva 30 minutos |
| `admin.php` | Entrega la página del panel solo después de `requerir_admin()`. Con cabeceras `no-store`, `X-Frame-Options: DENY` y una política de contenido que solo permite recursos del mismo sitio |
| `admin_estadisticas.php?seccion=...&dias=7\|30\|90` | Solo GET, consultas preparadas, solo agregados. Una última barrera lanza un error si alguna respuesta llegara a contener `correo`, `nombre`, `fecha_nac`, `contrasena`, `perfil_id` o `cuenta_id` |

**Por qué `admin.php` y no `admin.html`:** PHP no puede proteger un archivo `.html` estático; cualquiera
que adivine la URL lo descargaría. El HTML vive en `lib/admin_panel.html` (carpeta bloqueada por HTTP) y
solo sale por `admin.php`. Así "un usuario normal recibe 403" se cumple en el servidor y no solo en el
navegador. La URL `admin.html` da 404.

**Secciones** (cada una con el período de 7, 30 o 90 días):

| Sección | Qué muestra |
|---|---|
| Resumen | Cuentas, perfiles, perfiles activos, búsquedas, aperturas y «me gusta», con la variación frente al período anterior de la misma duración. Dos gráficas de línea por día |
| Más consumidos | Top 10 de ejercicios y de artículos por aperturas más «me gusta» |
| Menos consumidos | Documentos con al menos 20 impresiones y pocas aperturas (de menor a mayor tasa de apertura) y documentos nunca mostrados. Un aviso nombra los títulos y las etiquetas que conviene revisar |
| Edad | Consumo por rango (menos de 18, 18 a 24, 25 a 34, 35 a 44, 45 o más) con los 5 músculos y temas más consumidos de cada uno. Solo rangos con al menos 5 cuentas |
| Búsquedas | Raíces más buscadas y consultas que terminan en `ninguno` o `sin_interseccion` (contenido que falta) |
| Cobertura | Músculos y temas con sus documentos e interacciones, marcando pocos documentos o poca interacción |

**Gráficas:** SVG propio, sin librerías ni enlaces externos (como las ilustraciones de la fase 4). Líneas
por día con eje de fechas ("12 nov") y tooltip, también con el teclado; barras horizontales ordenadas de
mayor a menor con el valor al lado y un solo color; barras agrupadas para la edad con leyenda. Sin gráficas
de pastel. Cada título dice la conclusión, por ejemplo "El rango 18 a 24 concentra el 50 % de las
aperturas" o "«Cuádriceps» tiene solo 5 documentos: es donde más falta contenido". Cada tabla exporta a
CSV con datos agregados (las celdas que empiezan con `=`, `+`, `-` o `@` llevan un apóstrofo para que una
hoja de cálculo no las ejecute como fórmula).

**Diseño:** navegación lateral, selector de período que sigue visible al desplazar, fila de tarjetas de
números y debajo las gráficas en dos columnas (una en pantallas pequeñas). Reutiliza el sistema de la fase 3,
incluido el modo oscuro; se agregó solo `--color-serie-b` para la segunda serie.

Capturas en `docs/capturas/admin/` (resumen, más consumidos, edad en claro y en oscuro, y 375 px).

## 2. Decisiones

- **La edad se calcula en el servidor, en memoria.** La fecha de nacimiento está cifrada (AES-GCM), así
  que no se puede calcular el rango en SQL. Cada petición de la sección Edad descifra las fechas, las
  convierte en rango y las descarta; solo se devuelven rangos y conteos. Un rango con menos de 5 cuentas
  no aparece en la respuesta (ni siquiera con conteo cero).
- **Las cuentas `admin` no cuentan en el panel:** ni como cuentas, perfiles o edad, ni por las aperturas y
  los «me gusta» de sus perfiles (aunque use la aplicación con un perfil propio). Excepción que no se puede
  arreglar: sus búsquedas y las impresiones que generan **sí suman**, porque no llevan perfil a propósito
  (decisión de la fase 2, para que no se pueda saber quién buscó qué).
- **Perfil activo** = perfil con al menos una apertura o un «me gusta» en el período. Las impresiones no
  llevan perfil (decisión de la fase 2), así que no sirven para esto.
- **Período anterior** = la misma duración justo antes (7 días contra los 7 anteriores, etc.). Si el
  anterior es 0, la variación se muestra como "Sin datos de los N días anteriores".
- **Las claves de músculos y temas se llaman `concepto`, no `nombre`**, para que ninguna respuesta del
  panel contenga una clave `nombre`, aunque aquí fuera un músculo.
- **"Poca interacción"** = ninguna interacción o menos de la mitad de la mediana. "Pocos documentos" =
  menos de la mitad de la mediana.

## 3. Qué falló durante el desarrollo

1. **MariaDB no admite un alias de agregado dentro de una expresión del `ORDER BY`** (error 1247). La
   consulta de "poco abiertos" usaba `aperturas / impresiones`. Se repitió la expresión completa.
2. **Regla de cobertura que no marcaba nada.** Con más de la mitad de los temas sin interacciones, la
   mediana es 0 y "menos de la mitad de la mediana" nunca se cumple. Lo vio la prueba del navegador. Se
   puso un umbral mínimo de 1.
3. **Prueba intermitente por la coma del ID de sesión (arnés).** El archivo de cookies guarda la coma como
   `%2C`; cuando el ID la tenía, la prueba de envejecer la sesión no encontraba su archivo. Fallaba 3 de
   cada 4 corridas. Se decodifica el valor.
4. **La `~` de las rutas cortas de Windows (`ANAKAR~1`) rompe el valor de `php -d`** (la toma como el
   operador `~`). Todo el servidor de pruebas daba 500. La ruta va entre comillas.
5. **Dos cifras calculadas a mano estaban mal** (aperturas del período anterior: son 2 y no 3; interacciones
   de Pecho en 7 días: 8 y no 6). La prueba falló y se corrigió el cálculo, no el código. Los dos
   artículos que agregué para probar HTML en los títulos también cambiaron los totales de 30 y 90 días
   (20 y 22 aperturas); la prueba lo refleja.
6. **Comprobaciones que no probaban nada.** Dejé dos con `|| true`, que pasaban siempre. Las quité antes de
   confirmar.
7. **`Blob.text()` quita el BOM** al decodificar, así que mi prueba no podía verlo en el CSV. Ahora se
   leen los bytes del archivo.
9. **Documentación incorrecta que corregí después.** Había escrito que las cuentas admin no cuentan en
   ninguna métrica, pero las consultas de aperturas, «me gusta», más consumidos, menos consumidos y cobertura
   no filtraban por rol: los eventos de un administrador que usara la aplicación sumaban. Lo vi al explicar
   cómo funciona la cuenta. Se agregó `sin_eventos_de_admin()` a cada consulta, el escenario de prueba
   incluye ahora un administrador con 5 eventos, y al quitar el filtro fallan 21 comprobaciones.
8. **Pulido visual detectado en las capturas:** el botón "Volver a la aplicación" se veía como enlace
   subrayado, la sexta tarjeta del resumen quedaba sola en una segunda fila y, en teléfono, los títulos
   largos salían en letra enorme porque una regla móvil pisaba a otra. Los tres tienen ahora su
   comprobación.

## 4. Verificación

Los totales y rankings de las pruebas están calculados a mano en el encabezado de `tests/datos_admin.php`
(31 cuentas de usuario en 5 rangos de edad, un administrador, eventos y consultas en fechas conocidas) y
las pruebas comparan contra esos números.

| Requisito | Cómo se comprueba |
|---|---|
| Usuario normal: 403 en la página y en el endpoint; sin sesión: 401 | `test_admin.php`, y a mano contra Apache con la cuenta demo (403) |
| Ninguna respuesta contiene `correo`, `nombre`, `fecha_nac`, `contrasena` ni `perfil_id` | Las 18 respuestas (6 secciones por 3 períodos) se recorren buscando esas claves, y se busca que no aparezcan correos ni nombres en el texto |
| Un rango con menos de 5 cuentas no aparece | "menos de 18" (2 cuentas) y "45 o más" (4) no salen aunque tengan eventos; al borrar 2 cuentas, "18 a 24" (de 6 a 4) desaparece |
| El rol admin no se puede enviar en el registro | `registro.php` con `rol: "admin"` crea una cuenta `usuario`; ningún endpoint web ni librería escribe la columna |
| Totales y rankings iguales a lo calculado a mano | 77 comprobaciones HTTP (incluidas las del administrador que usa la aplicación) |

Además: al quitar el rol en la BD, la misma sesión recibe 403 de inmediato; tras 16 minutos de inactividad el
administrador recibe 401 mientras un usuario normal sigue con sesión (se simula envejeciendo el archivo de
sesión del servidor de pruebas).

**Validación de las pruebas:** se rompió a propósito el mínimo de 5 cuentas, la comprobación del rol y se
agregó una clave prohibida a la respuesta: fallaron 22 comprobaciones (la clave prohibida hizo fallar el
endpoint con 500 en vez de salir). En el navegador se desactivó `esc()`, se invirtió el orden de las barras
y se mostraron los rangos pequeños: fallaron 11 comprobaciones (los títulos con HTML crearon 5 nodos
`<img>` reales). Con el código correcto pasa todo.

## 5. Cómo probarlo

```
D:\Tools\SHAMP\mysql\bin\mysql.exe -uroot gym_buscador < sql\esquema_admin.sql
php herramientas\crear_admin.php tu-correo@dominio.com        pide la contraseña sin mostrarla

cd scripts_py && python -m pytest tests -q                    74 pasan, 8 se saltan
D:\Tools\SHAMP\php\php.exe tests\test_admin.php               77 comprobaciones
D:\Tools\SHAMP\php\php.exe tests\test_admin_interfaz.php      73 del navegador + 1
D:\Tools\SHAMP\php\php.exe tests\test_autorizacion.php        24
D:\Tools\SHAMP\php\php.exe tests\test_estadisticas.php        49
D:\Tools\SHAMP\php\php.exe tests\test_etiquetas.php           34
D:\Tools\SHAMP\php\php.exe tests\test_interfaz.php            85 del navegador + 3
D:\Tools\SHAMP\php\php.exe tests\test_ilustraciones.php       85 del navegador + 12
```

Para verlo: iniciar sesión en `http://localhost/buscador_gym/` con la cuenta de administrador y abrir
`http://localhost/buscador_gym/admin.php`. Con `CAPTURAS=<carpeta>` la prueba del navegador guarda capturas.

## 6. Pendientes

- **El esquema ya está aplicado en `gym_buscador` (17 de noviembre), pero todavía no existe ninguna cuenta
  de administrador.** El script pide la contraseña por la consola, así que la tiene que escribir quien va
  a usar la cuenta: `php herramientas\crear_admin.php <correo>` en una terminal normal.
- El panel nunca se ha visto con datos reales de varias semanas: la BD real tiene 2 cuentas y 25 eventos,
  así que casi todo saldrá vacío (la edad no mostrará ningún rango hasta que haya 5 cuentas por rango).
- La sección Edad descifra la fecha de todas las cuentas en cada petición. Con miles de cuentas habría que
  guardar el rango por cuenta; con las que hay hoy es instantáneo.
- No hay registro de qué hace cada administrador (bitácora de auditoría).
- Los artículos que el árbol de Temas no logra clasificar aparecen en Cobertura como un tema llamado
  "Sin clasificar".
- La prueba del panel solo corre en Edge o Chrome. Los tooltips con el dedo (pantalla táctil) no se
  probaron; el teclado sí.
- "Perfiles activos" no cuenta a quien solo vio resultados sin abrir nada ni dar «me gusta» (las impresiones
  no llevan perfil).
- Un administrador solo puede serlo quien tenga acceso a la línea de comandos del servidor. No hay forma
  web de quitar el rol; se hace con SQL (`UPDATE cuentas SET rol = 'usuario' WHERE correo = ...`).


---

# Fase 6A — Ampliar el corpus de artículos de 341 a 2 000

**Fecha:** 17 y 18 de noviembre de 2026. **Rama:** `fase-6a-corpus`. **Estado:** completa: 2 000 artículos (341 originales y 1 659 generados) en 17 lotes. Sin push ni pull request todavía.

**Objetivo:** pasar de 341 a unos 2 000 artículos sin repetir el sesgo actual (69 % sin ningún vínculo a
un músculo; Alimentación, Recuperación y Suplementación sin ninguno), con texto original en español, etiquetas
del vocabulario controlado y sin dosis, estudios ni promesas.

## 1. Medición de partida (Paso 0)

| Dato | Valor |
|---|---|
| Longitud del contenido | 39 a 53 palabras (media 46,7), 2 a 4 frases |
| Etiquetas por artículo | 6 o 7; 950 distintas, el 64,5 % usada una sola vez |
| Tema más grande | Recuperación (22,3 %); Técnica y biomecánica es la segunda (19,6 %) pero concentra el 57 % de los artículos que sí tienen músculo |
| Sin vínculo a un músculo | 236 de 341 (69 %) |
| Pares con similitud del coseno mayor a 0,8 | 0 (el máximo es 0,614) |
| Etiquetas dentro del vocabulario de `taxonomia.py` | 46 % de las apariciones; solo 3 artículos con todas dentro |
| Artículos con cantidades en g, mg, ml o kg | 45 (13 %); 26 usan la palabra "dosis" |

Metas aprobadas (`corpus/objetivos.json`): 1 659 artículos nuevos repartidos por tema (Fuerza 270, Hipertrofia 270,
Resistencia 170, Técnica 280, Planificación 160, Recuperación 220, Prevención 230, Alimentación 280,
Suplementación 120 en total) y por músculo (de 35 en Antebrazos a 130 en Espalda y Cuádriceps), con 825 nuevos
artículos que llevan un músculo (antes: 105 de 341).

## 2. Qué se construyó

| Pieza | Para qué |
|---|---|
| `sql/esquema_corpus.sql` | `articulos.origen_contenido ENUM('original','generado') NOT NULL DEFAULT 'original'`. Idempotente. Los 341 quedan como `original` |
| `taxonomia.VOCABULARIO_EXTRA` y `etiquetado.vocabulario_controlado()` | Vocabulario controlado de 190 etiquetas: las 145 de la taxonomía más 45 que los originales ya usan 4 veces o más. Van aparte de `TEMAS` para no cambiar el tema que el árbol asigna a los originales. Se dejaron fuera 9 que tocan salud (dosis, cortisol, inflamación, inmunidad, hormonas, mtor, melatonina, atp, dolor) |
| `scripts_py/validar_lote.py` | Valida un lote antes de importar (ver abajo) |
| `scripts_py/planear_lote.py` | Reparte las plazas de un lote sobre la matriz tema por músculo, restando lo ya generado |
| `scripts_py/ensamblar_lote.py` | Une los archivos de trabajo en `corpus/lotes/lote_NN.csv` y su plan, y comprueba las cuotas |
| `scripts_py/importar_lote.py` | Vuelve a validar e inserta todo o nada como `generado`, con consultas preparadas |
| `scripts_py/consultas_referencia.py` y `corpus/consultas_referencia.json` | Las 18 consultas de referencia (las propuse yo; no existían en el repositorio), ejecutadas antes y después de cada lote |

**Qué valida `validar_lote.py`:** encabezado y columnas; títulos únicos (exactos y por similitud); 38 a 56 palabras y
2 a 4 frases; 6 o 7 etiquetas, todas del vocabulario; español (proporción de palabras vacías); similitud del coseno
con TF-IDF como el indexador (rechaza más de 0,8 y lista 0,6 a 0,8 para revisión); cantidades con unidad,
porcentajes, años, plazos de resultados y palabras de salud, estudios o promesas; ejercicios inexistentes (la tabla
`ejercicios` debe tener al menos 5 registros de la familia mencionada); que un artículo de técnica, fuerza o
hipertrofia de un músculo nombre un ejercicio que la tabla sí tiene para ese músculo; y que el tema y el músculo que
resultan de las etiquetas, calculados con las mismas funciones del árbol, sean los previstos en el plan.

## 3. Lote 1 (100 artículos)

Cuotas calculadas por `planear_lote.py` (53 celdas): Fuerza 13, Hipertrofia 15, Resistencia 9, Técnica 13,
Planificación 8, Recuperación 7, Prevención 14, Alimentación 14, Suplementación 7; 49 con músculo y 51 sin él.

| Paso | Resultado |
|---|---|
| Validación | 0 errores, 0 avisos, 41 a 55 palabras (media 47,9), similitud máxima con otro artículo 0,570 |
| Importación | 100 artículos como `generado` (ids 343 a 442) |
| `indexer.py` | 23 s; diccionario de 2 805 a 2 973 términos y postings de 77 885 a 81 120 |
| `generar_etiquetas.py` | 931 etiquetas, 14 142 asignaciones, 3 289 rutas; ningún artículo sin ruta ni etiquetas |
| 18 consultas de referencia | Ninguna marcada para revisión: el primer resultado de antes sigue entre los 3 primeros en las 18 |

La consulta 12 ("correr resistencia cardio") cambió mucho (solo 1 de los 5 primeros se mantiene), y es una mejora:
antes había un único artículo de cardio y el resto eran ejercicios con puntajes bajos; ahora lideran artículos
pertinentes. En la 1 ("press de banca pecho") el nuevo artículo de press de banca inclinado entra primero por 0,001.

## 4. Qué falló o hubo que corregir

1. **Tres errores de etiquetas repetidas.** "abdomen" y "abdominales", y "hombro" y "deltoides", son la misma etiqueta
   una vez normalizadas. El validador los rechazó y se cambió una de cada par.
2. **Un artículo repetía el tema de uno original.** Mi "Extensión de tríceps sobre la cabeza" quedó con similitud 0,722
   frente al original del mismo nombre: no era un error (está bajo 0,8) pero sí un duplicado de enfoque. Lo reescribí
   como "Fondos en banco". Esta es la utilidad de la banda 0,6 a 0,8.
3. **Una imprecisión que el validador no puede ver.** Escribí que el press militar se empuja "desde las piernas"; el
   press militar estricto no usa las piernas. Lo encontré releyendo, no por una regla. El validador comprueba formato,
   seguridad y consistencia, no si un consejo de ejercicio es correcto: por eso se entregan 5 artículos al azar por lote
   para tu revisión.
4. **El contenido de prueba no coincidía con la tabla real.** `articulos` de las pruebas no tenía `AUTO_INCREMENT` ni
   `contenido NOT NULL`. Se alineó con la real.
5. **Dos cálculos míos en las pruebas estaban mal** (2 y no 3 resultados perdidos; el contenido de prueba tiene 2 press
   de banca y no 1).
6. **MariaDB se detuvo dos veces durante la sesión** sin ningún error en su registro; la segunda vez, justo antes de
   importar (al arrancar hizo la recuperación habitual y los datos coincidían). No sé la causa. Se reinició de forma
   limpia y desacoplada del terminal; la importación es una sola transacción, así que una caída no deja datos a medias.
7. **La corrida completa de pruebas fue anormalmente lenta y una suite de navegador falló por tiempo.** pytest tardó
   25 minutos (normalmente unos 25 segundos) y `test_interfaz.php` agotó una espera de 30 s. Coincidió con poca memoria
   libre en la máquina (1 GB de 16, con Android Studio, Word y varios navegadores abiertos). Repetidas por separado,
   `test_interfaz.php` pasó (85 de 85) y las pruebas del corpus tardaron 17 s. Si pasa otra vez, hay que repetir esa suite.

## 5. Cómo operar un lote

```
python scripts_py\planear_lote.py 100 --salida corpus\lotes\lote_NN.cuotas.csv
(redactar corpus\lotes\trabajo\lote_NN_*.csv con: tema, musculo, titulo, contenido, etiquetas)
python scripts_py\ensamblar_lote.py NN "corpus\lotes\trabajo\lote_NN_*.csv"
python scripts_py\validar_lote.py corpus\lotes\lote_NN.csv --plan corpus\lotes\lote_NN.plan.csv
python scripts_py\importar_lote.py corpus\lotes\lote_NN.csv --plan corpus\lotes\lote_NN.plan.csv
python scripts_py\indexer.py
python scripts_py\generar_etiquetas.py
python scripts_py\consultas_referencia.py comparar corpus\resultados\base.json --guardar corpus\resultados\lote_NN.json
```

Antes del lote 1 se hizo una copia de `articulos`, `diccionario` y `postings` en `backups/` (carpeta fuera de Git).
`indexer.py` vacía y recalcula todo el índice, así que cada lote cambia un poco el IDF de todos los términos.

## 6. Los lotes 2 a 17

Por pedido tuyo ("haz todos los lotes de corrido") los 16 lotes restantes se hicieron seguidos, **sin la revisión de
muestras que se había acordado entre lote y lote**. Cada lote siguió el mismo ciclo: planear, redactar, ensamblar,
validar hasta 0 errores, importar, reindexar, regenerar etiquetas y rutas, comparar las 18 consultas, correr las
pruebas del corpus (53) y un commit. El lote 17 es el de 59 artículos que cierra los 2 000.

| Lote | Ids | Palabras (mín-media-máx) | Sim. máx | Pares 0,6-0,8 | Consultas a revisar (de 18) | Notas |
|---|---|---|---|---|---|---|
| 02 | 443-542 | 38-42,5-49 | 0,614 | 1 | 1 | 4 reescritos por pares parecidos o longitud; 1 por un ejercicio sin registros en la tabla |
| 03 | 543-642 | 38-42,6-50 | 0,613 | 2 | 2 | 11 errores (longitud, títulos largos, tema, una promesa) |
| 04 | 643-742 | 38-42,5-47 | 0,660 | 6 | 5 | Se arregló la regex de «escalador» del validador (ver 7) |
| 05 | 743-842 | 38-42,5-47 | 0,693 | 8 | 4 | Los artículos de creatina empiezan a desplazar a los originales |
| 06 | 843-942 | 38-42,0-47 | 0,696 | 10 | 5 | 14 errores; un tema duplicado sustituido |
| 07 | 943-1042 | 38-42,7-47 | 0,680 | 7 | 5 | Temas casi repetidos en banda y polea |
| 08 | 1043-1142 | 38-42,4-49 | 0,679 | 7 | 5 | Los ejercicios por músculo se repiten; cambia el enfoque |
| 09 | 1143-1242 | 38-42,3-47 | 0,692 | 5 | 6 | Nuevo enfoque: errores comunes, programación y cuidados por músculo |
| 10 | 1243-1342 | 38-42,6-48 | 0,675 | 12 | 6 | 13 rehechos: títulos largos, duplicados de tema |
| 11 | 1343-1442 | 38-42,5-48 | 0,679 | 12 | 7 | Pares casi duplicados (hasta 0,79) en pantorrilla, bíceps y abdomen |
| 12 | 1443-1542 | 38-42,2-49 | 0,680 | 15 | 7 | 9 filas con el músculo sin indicar en la columna del plan |
| 13 | 1543-1642 | 38-41,8-49 | 0,678 | 10 | 8 | Enfoque de mitos, preguntas frecuentes y escenarios |
| 14 | 1643-1742 | 38-41,8-50 | 0,664 | 14 | 8 | 21 errores; tres pares casi duplicados rehechos |
| 15 | 1743-1842 | 38-41,6-48 | 0,700 | 20 | 9 | Hubo un fallo de proceso (ver 7) |
| 16 | 1843-1942 | 38-41,7-52 | 0,690 | 20 | 9 | 24 errores; 9 pares casi duplicados (hasta 0,82) rehechos |
| 17 | 1943-2001 | 38-40,6-45 | 0,697 | 11 | 9 | 59 artículos; total 2 000 |

## 7. Qué falló o hubo que corregir durante los lotes 2 a 17

1. **Un fallo real del validador (lote 4).** La regex de la familia «escalador» era `escaladores?`, que no reconocía la
   palabra en singular y rechazaba artículos que sí nombraban el ejercicio. Se corrigió a `escalador(?:es)?` y se añadió
   una prueba que comprueba que cada familia se reconozca por su propio nombre.
2. **El fallo de proceso del lote 15.** El script que encadenaba importación, índice y consultas seguía aunque la
   importación fallara (el validador aún marcaba un título de 11 palabras): dejé constancia de un lote «importado» y lo
   comprometí cuando la BD seguía en 1 400 generados. Lo detecté al ver que el reparto del lote siguiente no había
   cambiado, corregí el título, importé de verdad y enmendé ese commit local (sin push). El script ahora aborta si
   falla un paso. Lección: comprobar siempre el conteo en la BD, no solo la salida del script.
3. **Corrupción de la referencia de la rama.** Al reanudar, `git` decía que la rama `fase-6a-corpus` estaba rota: su
   archivo de referencia contenía 41 bytes nulos (probablemente por un apagado). Los objetos estaban intactos y el
   reflog daba el último commit, así que se restauró solo ese archivo. `git fsck` quedó limpio.
4. **Errores de forma recurrentes que el validador sí atrapó:** títulos de más de 10 palabras (el más frecuente),
   contenidos de 35 a 37 palabras, la palabra «estudio», «garantiza», «dosis», «tratamiento» y «milagroso», etiquetas
   de otro tema que cambiaban el tema del artículo (un empate favorece al tema que está antes en `TEMAS`) y etiquetas
   de un segundo músculo que cambiaban el músculo del artículo.
5. **Saturación de temas.** Con 47 palabras por artículo y 11 músculos por 9 temas, a partir del lote 7 aparecían
   variantes casi idénticas del mismo ejercicio (banda y glúteo, extensión de tríceps en polea, flexión de muñeca,
   pantorrilla). El validador rechaza más de 0,8 y se rehicieron todos los pares que superaban 0,7; los lotes 9 a 17
   cambiaron de enfoque (errores comunes, mitos, preguntas, programación, cuidados) para ganar diversidad.
6. **Memoria y estabilidad.** MariaDB siguió arrancada todo el tiempo; las pruebas del corpus tardaron entre 11 y 25 s
   en cada lote.

## 8. Resultado final

| Dato | Valor |
|---|---|
| Artículos | 2 000: 341 `original` y 1 659 `generado` (ids 343 a 2001); ningún título repetido |
| Longitud | generados 38 a 55 palabras (media 42,5); originales 39 a 53 (media 46,5) |
| Índice | diccionario 3 860 términos; 126 771 postings |
| Tablas derivadas | 931 etiquetas, 23 503 asignaciones, 4 848 rutas; ningún artículo sin etiquetas ni ruta |
| Sin ningún músculo | 1 070 de 2 000 (53,5 %); antes eran 236 de 341 (69 %) |
| Similitud global (coseno) | máxima 0,706; ningún par sobre 0,8; solo 2 artículos con un vecino sobre 0,7; 240 (12 %) con un vecino sobre 0,6 |
| Similitud media con el vecino más parecido | originales 0,38; generados 0,48 |

Se cumplió exactamente la matriz aprobada: los totales por tema y por músculo son los de `corpus/objetivos.json`
(Fuerza 270, Hipertrofia 270, Resistencia 170, Técnica 280, Planificación 160, Recuperación 220, Prevención 230,
Alimentación 280, Suplementación 120; Pecho 110, Espalda 130, Hombro 110, Bíceps 80, Tríceps 80, Cuádriceps 130,
Isquiotibiales 70, Pantorrilla 40, Glúteo 90, Abdomen 120, Antebrazos 35).

### Efecto en la búsqueda (las 18 consultas de referencia)

Respecto de la línea base, el primer resultado de antes salió de los 3 primeros en 9 de las 18 consultas, y en otras 9 (no
siempre las mismas) al menos 4 de los 5 primeros resultados son ahora artículos generados; en 5 (proteína después de entrenar, creatina, calentamiento, correr
resistencia cardio, abdomen plancha) son los 5. En varios casos el nuevo primer resultado es pertinente (p. ej.
«abdomen plancha» pasa de «Salida con tablones» a un artículo de plancha), pero en otros un artículo genérico y corto
que contiene las palabras de la consulta desplaza a un original más específico: «proteína después de entrenar» pierde
«Ventana anabólica: mito y realidad», «creatina» pierde «Creatina en vegetarianos y veganos» del primer puesto y
«cafeína antes de entrenar» pierde «Cafeína como ayuda ergogénica». Es un efecto esperable del TF-IDF con documentos
cortos y no se corrigió porque cambiar el ranking queda fuera de esta fase. Si importa, las opciones son ponderar o
filtrar por `origen_contenido` al buscar, o limitar cuántos artículos genéricos de un mismo tema entran en un
resultado. Es una decisión tuya.

### Pruebas al final de la fase

```
pytest (scripts_py/tests)  127 passed, 8 skipped (una prueba nueva: familias de ejercicio del validador)
test_autorizacion.php      24 comprobaciones, 0 fallos
test_estadisticas.php      49 comprobaciones, 0 fallos
test_etiquetas.php         34 comprobaciones, 0 fallos
test_admin.php             77 comprobaciones, 0 fallos
test_ilustraciones.php     12 comprobaciones, 0 fallos (tras repetirla)
test_admin_interfaz.php    1 comprobación (el detalle lo imprime el script de Node), 0 fallos (tras repetirla)
test_interfaz.php          3 comprobaciones (idem), 0 fallos (tras repetirla)
Nota: la primera corrida de las tres pruebas de navegador falló porque MariaDB se detuvo a media suite (las dos últimas
no pudieron conectar). Con el servidor otra vez en marcha y la BD real intacta (341 + 1 659 artículos), las tres pasan.
Es la tercera vez que MariaDB se cae durante esta fase, sin errores en su registro.
```

### Muestra al azar de 10 artículos generados

Elegidos con una semilla fija sobre los 1 659 (ver la consulta en `corpus/`, no se guardan aparte): están en la
respuesta final de la sesión para tu revisión.

## 9. Cómo probarlo

```
python scripts_py\consultas_referencia.py comparar corpus\resultados\base.json
cd scripts_py && python -m pytest tests -q
D:\Tools\SHAMP\mysql\bin\mysql.exe -uroot gym_buscador -e "SELECT origen_contenido, COUNT(*) FROM articulos GROUP BY 1"
```

## 10. Pendientes

- **Revisión humana:** el validador no juzga si un consejo de ejercicio es exacto ni el tono. Los lotes 2 a 17 se
  entregaron sin la revisión de muestras que se había acordado entre lotes; conviene que revises una muestra amplia
  (al menos 5 por lote, de cualquier tema) antes de fusionar.
- **Decisión sobre el ranking:** ver «Efecto en la búsqueda». Los artículos generados desplazan a originales más
  específicos en varias consultas.
- **Redundancia:** el espacio de temas por músculo está casi agotado; 240 artículos (12 %) tienen un vecino con
  similitud mayor a 0,6. Si se quiere más corpus, conviene cambiar la matriz (menos celdas por músculo) y no solo
  seguir generando.
- Los 45 artículos originales con cantidades en gramos, mg o ml se dejaron como están (decisión tuya).
- `origen_contenido` todavía no se usa en la interfaz ni en el panel.
- El push y el pull request de `fase-6a-corpus` (19 commits propios) siguen sin hacerse. `backups/` (fuera de Git)
  tiene la copia previa a la fase; no se actualizó con cada lote.


---

# Fase 6B — Árboles de Equipamiento y Nivel y motor de N árboles

**Fecha:** 18 de noviembre de 2026. **Rama:** `fase-6b-arboles`, creada sobre `fase-6a-corpus` (que sigue sin fusionar:
6B necesita los 2 000 artículos y sus etiquetas). **Estado:** completa, salvo el árbol de Patrón de movimiento, que no se
construyó (se decidió dejarlo para después). Sin push.

**Objetivo:** que el motor deje de estar pensado para dos árboles (Anatomía y Temas) y pueda combinar cualquier par,
sumando los árboles de Equipamiento y Nivel, sin cambiar lo que ya respondía para un músculo y un tema.

## 1. Qué se hizo

| Pieza | Para qué |
|---|---|
| `sql/esquema_rutas_arboles.sql` | `documento_rutas` pasa a tener una ruta POR ÁRBOL (clave `origen, doc_id, arbol`) y el ENUM acepta `equipamiento`, `nivel` y `patron`. Idempotente; aplicado dos veces a `gym_buscador` (se conservaron las 4 848 filas) |
| `arboles/taxonomia.py` | Categorías de equipamiento, tabla etiqueta-de-artículo a nodo, vocabulario de consulta, orden y títulos de los árboles, árbol compañero de cada uno |
| `arboles/constructor.py` | `construir_arbol_equipamiento` y `construir_arbol_nivel`; los árboles previos exponen `meta["conceptos"]` |
| `arboles/bosque.py` | `Bosque`: los árboles, la pertenencia de cada documento a nodos y una `AristasPar` por cada par de árboles |
| `arboles/motor.py` | `MotorArboles` con N árboles (`desde_bosque`); el constructor de dos árboles se conserva |
| `arboles/catalogo.py`, `catalogo_arboles.py`, `puente_arboles.py` | Catálogo de todos los árboles con el conteo de cada cruce, y los documentos que unen dos nodos |
| `generar_etiquetas.py`, `etiquetado.construir_rutas_arboles` | Una ruta por árbol y documento (10 544 filas en la BD real) |
| `menus.php`, `buscar.php`, `detalle.php`, `lib/documentos.php`, `index.html` | `accion=cruce` para cualquier par; el descubrimiento puede ser un ejercicio y trae la ruta de cada árbol; el detalle trae `rutas`; los menús A y B eligen árbol y concepto |
| `medir_arboles.py` | La medición final (solo lee la BD) |

## 2. Cómo decide el motor (aprobado en el Paso 0)

- **Pertenencia.** Un documento pertenece a nodos de cada árbol: un ejercicio, por sus columnas (músculo, equipamiento,
  nivel); un artículo, por sus etiquetas. Los ejercicios no pertenecen a Temas.
- **Aristas.** Hay una por cada par de nodos de dos árboles con al menos un documento en común (peso = documentos; lift como
  en la fase 1, con N = documentos que tienen alguna arista en ese par). Se guardan en memoria, derivadas, sin tablas nuevas.
  Como los ejercicios no entran en Temas, **Anatomía x Temas sale solo de artículos y es idéntico al de la fase 1**.
- **Cero árboles nombrados:** recuperación TF-IDF sobre Anatomía y Temas, como antes.
- **Uno:** salta al árbol compañero (músculo con tema y tema con músculo, como antes; Equipamiento y Nivel saltan a Anatomía).
- **Dos o más:** el mejor nodo de cada árbol nombrado y (1) `interseccion` si hay documentos en todos; (2) si no, y hay tres
  árboles, `interseccion_parcial` con el par de mayor lift (luego peso, luego orden fijo de árboles; primero con 2 o más
  documentos y si no con 1), indicando en la traza qué árbol quedó fuera; (3) si ningún par se relaciona,
  `sin_interseccion` (se dice, no se inventa).
- **JSON.** Se conservan `via`, `origen`, `destino`, `documentos`, `lift`, `razon`, `traza` y `alternativa`. Se añade `nodos`
  (la ruta del nodo en cada árbol que participa) y la vía `interseccion_parcial` (cabe en `consultas.via VARCHAR(30)`).
- **Documentos.** Se ordenan por puntaje TF-IDF, artículos antes que ejercicios en empate y luego por id. Sin azar.

## 3. Los árboles nuevos

| Árbol | Estructura | Altura | Nodos | Hojas (ejercicios) |
|---|---|---|---|---|
| Equipamiento | Equipamiento > categoría > equipamiento > ejercicio | 3 | 2 871 (1 raíz, 6 categorías, 16 equipamientos) | 2 848 |
| Nivel | Nivel de experiencia > nivel > ejercicio | 2 | 2 852 (1 raíz, 3 niveles) | 2 848 |

Categorías de equipamiento: Pesas libres (Barra, Barra Z, Mancuernas, Kettlebell), Máquinas y poleas, Peso corporal y bandas
(Peso corporal, Bandas, Rodillo), Balones, Accesorios (Banco, Paralelas, Correas: solo los nombran artículos, 0 ejercicios) y
Otros (Otro y Sin especificar: los 29 ejercicios sin equipamiento). Los artículos no son hojas: se enlazan por etiquetas.
**Nivel está muy desbalanceado:** 438 ejercicios Principiante, 2 397 Intermedio y 13 Avanzado; solo 2 artículos Avanzado,
así que cualquier lift con Avanzado es ruidoso.

## 4. Aristas por par de árboles (BD real, 2 000 artículos y 2 848 ejercicios)

| Par de árboles | Aristas | Documentos | Ejercicios | Artículos |
|---|---|---|---|---|
| Anatomía x Temas | 81 | 930 | 0 | 930 |
| Anatomía x Equipamiento | 134 | 3371 | 2848 | 523 |
| Anatomía x Nivel | 25 | 2885 | 2848 | 37 |
| Temas x Equipamiento | 58 | 562 | 0 | 562 |
| Temas x Nivel | 13 | 237 | 0 | 237 |
| Equipamiento x Nivel | 34 | 2882 | 2848 | 34 |

## 5. Medición final

Las 18 consultas de referencia dan **lo mismo con dos árboles que con cuatro** (ninguna cambia de vía ni de destino):
concepto 14, concepto_local 2, interseccion 2; **2 caen en fallback** (las dos son `concepto_local`: «creatina» y «cafeina antes de entrenar»,
que ya lo eran), **9 destinos distintos** y 16 documentos distintos. «Fallback» = vía `ninguno`,
`sin_interseccion`, `concepto_local` o `recuperacion`. Ninguna de las 18 nombra un equipamiento ni un nivel, así que no podía
mejorar: lo que se comprueba es que no empeora.

| # | Consulta | Vía con 2 árboles | Vía con 4 árboles | Destino (4 árboles) | Árboles que participan |
|---|---|---|---|---|---|
| 1 | press de banca pecho | concepto | concepto | Temas: Planificación | Anatomía, Temas |
| 2 | sentadilla profundidad | concepto | concepto | Temas: Resistencia | Anatomía, Temas |
| 3 | dominadas espalda | concepto | concepto | Temas: Planificación | Anatomía, Temas |
| 4 | peso muerto cadera | concepto | concepto | Temas: Resistencia | Anatomía, Temas |
| 5 | hipertrofia biceps | interseccion | interseccion | Temas: Hipertrofia | Anatomía, Temas |
| 6 | proteina despues de entrenar | concepto | concepto | Anatomía: Antebrazos | Temas, Anatomía |
| 7 | dormir recuperacion muscular | concepto | concepto | Anatomía: Antebrazos | Temas, Anatomía |
| 8 | creatina | concepto_local | concepto_local | Temas: Suplementación | Temas |
| 9 | calentamiento antes de entrenar | concepto | concepto | Anatomía: Pantorrilla | Temas, Anatomía |
| 10 | movilidad de hombro | interseccion | interseccion | Temas: Prevención y movilidad | Anatomía, Temas |
| 11 | periodizacion del entrenamiento | concepto | concepto | Anatomía: Isquiotibiales | Temas, Anatomía |
| 12 | correr resistencia cardio | concepto | concepto | Anatomía: Pantorrilla | Temas, Anatomía |
| 13 | gluteo puente | concepto | concepto | Temas: Resistencia | Anatomía, Temas |
| 14 | abdomen plancha | concepto | concepto | Temas: Resistencia | Anatomía, Temas |
| 15 | dolor de rodilla sentadilla | concepto | concepto | Temas: Resistencia | Anatomía, Temas |
| 16 | cafeina antes de entrenar | concepto_local | concepto_local | Temas: Suplementación | Temas |
| 17 | hidratacion sudor | concepto | concepto | Anatomía: Antebrazos | Temas, Anatomía |
| 18 | triceps extension | concepto | concepto | Temas: Fuerza | Anatomía, Temas |

Para ver el efecto de los árboles nuevos se añadieron 12 consultas que no estaban en las 18
(`scripts_py/medir_arboles.py`): con dos árboles, concepto 11, recuperacion 1 (1 en fallback, 6 destinos);
con cuatro, concepto 1, interseccion 10, interseccion_parcial 1 (0 en fallback, 10 destinos distintos, 12 documentos distintos).

| # | Consulta | Vía con 2 árboles | Vía con 4 árboles | Destino (4 árboles) | Árboles que participan |
|---|---|---|---|---|---|
| 1 | pecho mancuernas principiante | concepto | interseccion | Equipamiento: Mancuernas | Anatomía, Equipamiento, Nivel |
| 2 | press de banca con barra | concepto | interseccion | Equipamiento: Barra | Anatomía, Equipamiento |
| 3 | espalda polea | concepto | interseccion | Equipamiento: Polea | Anatomía, Equipamiento |
| 4 | triceps kettlebell avanzado | concepto | interseccion_parcial | Nivel: Avanzado | Equipamiento, Nivel |
| 5 | sentadilla maquina principiante | concepto | interseccion | Equipamiento: Máquina | Anatomía, Equipamiento, Nivel |
| 6 | abdomen peso corporal | concepto | interseccion | Equipamiento: Peso corporal | Anatomía, Equipamiento |
| 7 | ejercicios con bandas | recuperacion | concepto | Anatomía: Glúteo | Equipamiento, Anatomía |
| 8 | biceps mancuernas | concepto | interseccion | Equipamiento: Mancuernas | Anatomía, Equipamiento |
| 9 | ganar fuerza con barra | concepto | interseccion | Equipamiento: Barra | Temas, Equipamiento |
| 10 | dieta para principiantes | concepto | interseccion | Nivel: Principiante | Temas, Nivel |
| 11 | pecho kettlebell principiante | concepto | interseccion | Equipamiento: Kettlebell | Anatomía, Equipamiento, Nivel |
| 12 | pelota de ejercicio abdomen | concepto | interseccion | Equipamiento: Pelota de ejercicio | Anatomía, Equipamiento |

## 6. Qué falló o hubo que corregir

1. **Dos palabras de equipamiento cambiaban consultas de la fase 1.** La primera medición mostró que 2 de las 18 consultas
   cambiaban: «dolor de **rodilla** sentadilla» nombraba el equipamiento «Rodillo» y «**correr** resistencia cardio» nombraba
   «Correas», porque el stemmer da la misma raíz (`rodill`, `corr`). Se quitaron «rodillo» (queda «foam roller») y «correas» del
   vocabulario de consulta (siguen siendo nodos y salen en los menús) y se añadió una prueba que revisa todas las
   frases de equipamiento y nivel contra las de músculos y temas. Tampoco sirve «rodillo de espuma», porque contiene la raíz de
   «rodilla»; y «banco» queda fuera por su choque con «banca». Una consecuencia: quien escriba «rodillo» no obtiene ese equipamiento.
2. **«Pelota de ejercicio» no se reconocía.** «ejercicio» es una palabra de intención que el motor descarta de la consulta,
   así que la frase completa nunca coincidía. Se nombra con «pelota» o «fitball».
3. **«Sin especificar» en Nivel tenía aristas pero no era concepto**, y el catálogo fallaba con un `KeyError`. Ahora es un concepto
   (los menús lo muestran; las consultas no lo pueden nombrar).
4. **Los argumentos de línea de comandos con acento no son fiables en Windows**, así que las claves de los conceptos que viajan a
   `puente_arboles.py` van sin acentos ni mayúsculas (`maquina`, `balon medicinal`) y el grupo_id en Anatomía.
5. **Pruebas que se adaptaron, no se debilitaron.** `test_etiquetas.py` esperaba 12 rutas (una por documento) y ahora espera una por
   árbol (32 en el contenido de prueba); `interfaz.mjs` esperaba una sola ruta en el detalle y ahora comprueba que la primera sea la
   de anatomía y que haya una ubicación por árbol.
6. **Dos errores míos en las pruebas nuevas:** un conteo mal calculado a mano (2 y no 3 artículos) y una espera del navegador que
   daba por buena una pantalla anterior. Se corrigieron.
7. **Una suite de navegador falló por tiempo una vez** (`test_interfaz.php`, antes de mis bloques) y pasó al repetirla, como ya
   estaba documentado.
8. **Rendimiento:** el motor sigue tardando unos 7,6 s por consulta. De eso, 6,6 s son el `import` de NLTK (anterior a esta fase);
   construir los cuatro árboles y las aristas cuesta menos de 2 s. No se tocó.

## 7. Pruebas

```
pytest (scripts_py/tests)  165 passed (con CSV_EJERCICIOS y CSV_ARTICULOS; 30 de ellas, nuevas)
test_autorizacion.php      24 comprobaciones, 0 fallos
test_estadisticas.php      49 comprobaciones, 0 fallos
test_etiquetas.php         34 comprobaciones, 0 fallos
test_arboles_n.php         28 comprobaciones, 0 fallos (nueva)
test_admin.php             77 comprobaciones, 0 fallos
test_ilustraciones.php     85 + 12 comprobaciones, 0 fallos
test_admin_interfaz.php    73 + 1 comprobaciones, 0 fallos
test_interfaz.php          92 + 3 comprobaciones, 0 fallos (7 nuevas)
```

Las 43 pruebas anteriores de árboles y motor pasan sin cambios (con `CSV_EJERCICIOS` y `CSV_ARTICULOS` las 8 de datos reales
también). Nuevas: `scripts_py/tests/test_arboles_n.py` (altura, hojas, recorridos y posorden de Equipamiento y Nivel; pertenencia
por etiquetas; las aristas Anatomía x Temas idénticas a las de la fase 1; «pecho mancuernas principiante»; un par sin
intersección; tres árboles sin intersección total que eligen el mejor par; un solo concepto sin cambios; la misma respuesta con dos
y con cuatro árboles para músculo y tema; el vocabulario sin choques; catálogo y cruce), `tests/test_arboles_n.php` (HTTP) y nuevas
comprobaciones en `tests/interfaz.mjs`.

## 8. Cómo probarlo

```
mysql -uroot gym_buscador < sql/esquema_rutas_arboles.sql
python scripts_py/generar_etiquetas.py            # una ruta por árbol
python scripts_py/medir_arboles.py                # la medición
python scripts_py/motor_arboles.py "pecho mancuernas principiante"
cd scripts_py && python -m pytest tests -v
D:\Tools\SHAMP\php\php.exe tests\test_arboles_n.php
```

## 9. Pendientes

- **Árbol de Patrón de movimiento:** no se construyó. El esquema ya lo admite (`patron` en el ENUM) y añadirlo es registrar un
  constructor y su pertenencia en `bosque.py` más su vocabulario; sería una clasificación aproximada por palabras clave sobre
  `nombre_es`, con la lista de ejercicios que no pudo clasificar.
- Quien escriba «rodillo», «correas» o «banco» no obtiene esos equipamientos como concepto de consulta (ver 6.1); sí están en los menús.
- Nivel está casi todo en Intermedio; sus cruces con Avanzado tienen 13 ejercicios y 2 artículos.
- La búsqueda TF-IDF no usa los árboles nuevos: solo el descubrimiento y los menús. Las 18 consultas de referencia dan el mismo
  resultado de búsqueda que antes de esta fase.
- Los lotes de la fase 6A siguen sin fusionar y sin push (esta rama depende de ellos).
- La latencia de 7,6 s por consulta (NLTK) sigue pendiente.
