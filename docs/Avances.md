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
- La vista de detalle no se probó en un navegador: falta abrir una tarjeta con la cuenta demo y
  confirmar que aparece la fila `apertura` en `eventos`. Bajo Apache (mod_php) tampoco se midió
  que el registro no retrase la respuesta; eso solo está probado con `php -S`.
- El artículo descubierto por los árboles y las tarjetas de la vista A+B no abren el detalle.
  El artículo descubierto trae su texto cortado a 150 caracteres.
- `registrar_evento.php` no tiene límite de frecuencia: un usuario con sesión puede inflar las
  aperturas de un documento.
- Las recomendaciones (`recomendaciones.php`) no registran impresiones: no se pidió.
- No hay todavía consultas ni pantalla de estadísticas: solo se recogen los datos.
- La purga no está programada: hay que correrla a mano o con el Programador de tareas.
