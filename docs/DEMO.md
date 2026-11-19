# Guion de la demo

Duración: unos 20 minutos. Todo lo que dice «debe verse» se comprobó el 19 de noviembre de 2026 con el
corpus completo (2 000 artículos, 2 848 ejercicios) y la cuenta demo que crea `crear_demo.php`. Si cambia el
contenido, cambian los títulos y los conteos; la estructura de cada respuesta, no.

## 0. Antes de empezar (10 minutos antes)

1. **Encender SHAMP** (Apache y MariaDB). Abrir `http://localhost/buscador_gym/`.
2. **Cuenta demo** (borra y recrea la anterior; imprime la contraseña una sola vez, anotarla):
   ```
   D:\Tools\SHAMP\php\php.exe herramientas\crear_demo.php
   ```
   Crea `demo@buscador-gym.local` con dos perfiles: **Pecho** (6 «me gusta»: press de banca y aperturas) y
   **Pierna** (6: sentadilla, zancada, prensa de piernas).
3. **Cuenta de administrador** (la única forma de crearla; pide la contraseña sin mostrarla):
   ```
   D:\Tools\SHAMP\php\php.exe herramientas\crear_admin.php correo@dominio.com
   ```
   Si ya hay una administradora en la BD, se usa esa.
4. **Calentar**: hacer una búsqueda cualquiera con la cuenta demo. **Cada búsqueda y cada recomendación tarda unos
   6 segundos** (ver `docs/rendimiento.md`; sin internet, unos 8). Es lo único lento. Conviene decirlo en voz alta
   («está calculando los árboles») y no repetir búsquedas innecesarias. Entre búsqueda y búsqueda la interfaz
   muestra «Buscando…».
5. **Que el panel tenga datos**: el panel solo cuenta lo que hacen las cuentas que no son administradoras. Con la
   cuenta demo, hacer las búsquedas del punto 3, abrir 4 o 5 tarjetas y dar un par de «me gusta». Si no, el panel
   sale casi vacío (y eso también es correcto: dice «Sin actividad en este período»).
6. Ventana del navegador de unos 1 280 px de ancho. Tener a mano una terminal en la carpeta del proyecto (punto 7).

## 1. Acceso y perfiles

| Paso | Qué debe verse |
|---|---|
| Abrir la página sin sesión | Solo el formulario de acceso («Entrar» / «Crear cuenta»). No hay búsqueda ni menú de perfil. |
| «Crear cuenta» con un correo nuevo | Pide nombre (solo letras), fecha de nacimiento y contraseña de 10 caracteres o más con letras y números. Con una contraseña corta o sin números, dice por qué. Al crearla pasa a «Elige un perfil». |
| Cerrar sesión y entrar con la cuenta demo | «Elige un perfil» con **Pecho** y **Pierna**. |
| Elegir **Pecho** | Aparece la búsqueda y arriba el menú con el perfil activo («Pecho») y el correo. |

Qué decir: el nombre y la fecha de nacimiento se guardan cifrados (AES-256-GCM); la contraseña, con hash; el perfil
activo vive solo en la sesión del servidor, nunca viaja en la petición.

## 2. Recomendaciones y aislamiento entre perfiles

Con el perfil **Pecho** y sin escribir nada, la pantalla ya muestra recomendaciones:

- Primeros resultados: ejercicios de pecho parecidos a los que le gustaron («Press de pecho con cable inclinado»,
  «Press de pecho con cable de pie», «flexiones de pecho en banco», «máquinas de press de pecho»).
- A la izquierda, **«Lo que más pesa en tus recomendaciones»**: barras horizontales con las palabras que más pesan
  (por ejemplo «pecho»), ordenadas de mayor a menor.

Menú del perfil → **Cambiar perfil** → **Pierna**:

- Las recomendaciones cambian por completo: «Zancada lateral tocando el talón», «Prensa de piernas»,
  «Elevación de pantorrillas…», y la gráfica pesa palabras de pierna.
- Es la misma cuenta: lo que le gusta a un perfil no influye en el otro (se calcula por perfil en cada petición).

Un perfil nuevo, sin «me gusta», no ve gráfica sino una frase que dice qué hacer («Da “me gusta” a un ejercicio…»).

## 3. Búsquedas

Escribir en el cuadro de búsqueda y pulsar Enter, con el perfil **Pecho**. Cada búsqueda trae hasta 20 resultados
(ejercicios y artículos) y, arriba, la tarjeta **«Relacionado con tu búsqueda»**, que dice **por qué** aparece y
muestra **la ruta del nodo en cada árbol** que participó. Qué debe verse:

| Búsqueda | Qué debe verse | Qué demuestra |
|---|---|---|
| `pecho` | 20 resultados. «Relacionado»: el artículo *Flexiones: progresiones de empuje con peso corporal*. Razón: «Tu consulta apunta a “Pecho”. De 110 artículos sobre ese músculo, 6 tratan “Planificación”: el grafo salta de Anatomía a Temas». Dos rutas: Anatomía > Cuerpo humano > Tren superior > Pecho, y Temas > Conocimiento > Entrenamiento > Planificación. | Un solo concepto salta al árbol compañero. |
| `press de banca con barra` | Resultados de press de banca. Razón: combina «Pecho» (Anatomía) y «Barra» (Equipamiento): 25 ejercicios y 25 artículos pertenecen a ambos. Dos rutas. | Cruce de dos árboles. |
| `pecho mancuernas principiante` | Razón: combina Pecho, Mancuernas y Principiante: 5 ejercicios pertenecen a los tres. «Relacionado»: el ejercicio *Banco inclinado para mancuernas con las palmas hacia adentro*. **Tres rutas** (Anatomía, Equipamiento, Nivel). | Cruce de tres árboles. |
| `jalon espalda polea` | Razón: Espalda, Polea y «Tirón vertical» (Patrón de movimiento): 31 ejercicios. «Relacionado»: *Jalón lateral de rodillas*. La ruta de Patrón de movimiento lleva **«(aproximado)»** y debajo hay un aviso: la clasificación es aproximada, se infiere de las palabras del nombre y puede equivocarse. | El árbol aproximado siempre se avisa. |
| `bisagra gluteo` | Razón: Glúteo y «Bisagra de cadera» (Patrón): 27 ejercicios y 6 artículos. También con aviso de aproximado. | Patrón de movimiento. |
| `triceps kettlebell avanzado` | Razón: «Ningún documento reúne a la vez Tríceps, Kettlebell y Avanzado. La mejor relación es entre Kettlebell y Avanzado: 1 ejercicio; quedó fuera Anatomía». | Cuando no hay cruce de todo, dice cuál es el mejor y qué dejó fuera. |
| `pecho avanzado` | Resultados normales, **pero no aparece la tarjeta «Relacionado»**: ningún documento reúne Pecho y Avanzado y el sistema no inventa una relación (en la sección Búsquedas del panel de administrador, la tabla por tipo de respuesta lo cuenta como «Sin relación entre ambos conceptos»). | No se inventan resultados. |
| `creatina` | 18 resultados, todos artículos. Razón: apunta a «Suplementación», pero ningún artículo lo relaciona con un músculo; se muestran los documentos de ese nodo (120). Una sola ruta (Temas > Conocimiento > Nutrición > Suplementación). | Concepto sin pareja. |
| `ganar fuerza` | Razón: apunta al tema «Fuerza»; de 185 artículos, 20 también tratan «Tríceps»: salta de Temas a Anatomía. | El salto también va de temas a músculos. |
| `xyzzy` | Cero resultados: «No hay resultados para “xyzzy”. Prueba con otra palabra o revisa la ortografía.» Sin tarjeta «Relacionado». | Estado vacío claro. |

La misma consulta devuelve siempre la misma respuesta (no hay aleatoriedad).

### Tarjeta de detalle

Abrir un resultado (clic en el título, o Enter con el teclado), por ejemplo *Press de banca con barra - Agarre ancho*:

- Ventana modal con la ilustración grande (cuerpo con el músculo resaltado) y el texto completo.
- **Cuatro ubicaciones**, una por árbol: Anatomía (Cuerpo humano > Tren superior > Pecho > Barra), Equipamiento (Pesas
  libres > Barra), Nivel (Principiante) y Patrón de movimiento **(aproximado)** (Empuje > Empuje horizontal).
- Músculo, equipamiento y nivel; etiquetas (Pecho, Barra, Principiante, Fuerza); hasta 4 documentos relacionados con
  lo que comparten; botón «Me gusta».
- **Escape** cierra y el foco vuelve a la tarjeta. Un artículo muestra solo la ubicación en Temas.

### Filtros

Panel «Filtros»: tipo (ejercicios/artículos), nivel, equipamiento y etiquetas. Al filtrar, el conteo dice
«N de M resultados»; si nada cumple, lo dice y ofrece «Quitar filtros».

## 4. Explorar por árboles

Pestaña **Explorar por árboles**: dos árboles cualesquiera (A y B), un concepto de cada uno y **Ver documentos**.
Entre paréntesis, cada concepto trae cuántos documentos tiene en común con lo elegido en el otro menú.

| Selección | Qué debe verse |
|---|---|
| Anatomía: Pecho × Equipamiento: Barra | 25 ejercicios y 25 artículos; se muestran 12 ejercicios y hasta 30 artículos. Arriba, la ruta de cada nodo con el nombre de su árbol. |
| Anatomía: Pecho × Patrón de movimiento: Empuje horizontal | 159 ejercicios y 52 artículos. Aparece el aviso de **clasificación aproximada** y cuántos ejercicios no se pudieron clasificar (557). |
| Patrón: Sin clasificar × Nivel: Principiante | 98 ejercicios: son los que ninguna regla reconoció. Sirve para enseñar qué no se sabe clasificar. |
| Anatomía: Pecho × Nivel: Avanzado | «Ningún documento pertenece a “Pecho” y “Avanzado” a la vez.» |
| Anatomía: Pecho × Temas: Fuerza | 27 artículos y, aparte, algunos ejercicios de pecho (el texto aclara que son del músculo, porque los ejercicios no entran en Temas). |

Hay cinco árboles (Anatomía, Temas, Equipamiento, Nivel, Patrón de movimiento), 10 pares posibles, y el menú B nunca
ofrece el mismo árbol que A.

## 5. Panel de administrador

1. Cerrar sesión, **entrar con la cuenta de administrador en la página principal** (el panel no tiene botón: se
   entra a la dirección) y abrir `http://localhost/buscador_gym/admin.php`.
2. Primero, para demostrar el control de acceso: con la cuenta **demo** abrir `admin.php` → «No tienes acceso»
   (403); sin sesión → «Inicia sesión» (401).

Secciones (navegación a la izquierda, y selector de período de 7, 30 o 90 días):

| Sección | Qué debe verse |
|---|---|
| **Resumen** | Seis tarjetas (cuentas, perfiles, perfiles activos, búsquedas, aperturas y «me gusta») con la variación frente al período anterior, y la gráfica de actividad por día. Pasar el ratón, o el foco con Tab, por un día muestra el detalle. |
| **Más consumidos** | Ejercicio y artículo con más interacciones, y barras por músculo y por tema. |
| **Menos consumidos** | Documentos que se muestran mucho y casi no se abren, con las etiquetas que repiten y los que nunca se han mostrado. |
| **Edad** | Solo rangos con **5 cuentas o más**; con pocas cuentas dice que están ocultos (privacidad). La edad se calcula en memoria y no se guarda. |
| **Búsquedas** | Raíces más buscadas (nunca el texto escrito ni quién buscó), búsquedas sin resultados y «contenido que la gente busca y no existe». |
| **Cobertura** | Por músculo y por tema: cuántos documentos hay, cuántas interacciones, y dónde falta contenido. |

Cada tabla tiene **Exportar CSV**. Las gráficas son SVG propios y los números también están en las tablas.
Qué decir: el panel solo recibe agregados (nunca correo, nombre, fecha de nacimiento ni identificadores de perfil),
las cuentas de administrador no cuentan, y la sesión de administrador se cierra a los 15 minutos de inactividad.

## 6. Teclado, teléfono y modo oscuro (3 minutos)

- **Solo teclado**: en la búsqueda, escribir y Enter; **Tab** llega primero a «Saltar a los resultados» (aparece al
  recibir el foco; Enter lleva al título de los resultados y de ahí a la primera tarjeta en unas 5 pulsaciones);
  Enter abre el detalle, Escape lo cierra. En «Explorar por árboles», Tab recorre los selectores, las flechas cambian
  el valor y Enter en «Ver documentos» muestra el resultado.
- **Teléfono**: herramientas del navegador (F12), ancho de 375 px: una columna de tarjetas, filtros plegados, sin
  desplazamiento horizontal.
- **Modo oscuro**: cambiar la preferencia del sistema; la interfaz y las ilustraciones cambian de colores.

## 7. Seguridad en la terminal (2 minutos, opcional)

```
curl -i http://localhost/buscador_gym/menus.php                 # 401: ya no es público
curl -i http://localhost/buscador_gym/CLAUDE.md                 # 403: documentos no se sirven
curl -i http://localhost/buscador_gym/.git/config               # 404
curl -i http://localhost/buscador_gym/scripts_py/db_config.py   # 403: el código no se sirve
curl -i http://localhost/buscador_gym/admin_estadisticas.php?seccion=resumen    # 401
```

## 8. Qué decir con honestidad

- **La mayor parte del corpus de artículos es generada**: de 2 000 artículos, 341 son originales y 1 659 se
  generaron y están marcados (`origen_contenido`). Son cortos y genéricos; en algunas búsquedas desplazan a artículos
  originales más específicos.
- **Los nombres de los ejercicios son traducciones automáticas** del inglés: aparecen cosas como «pesa rusa» (kettlebell)
  o resultados raros (en `pecho` aparece «Salsa rusa para untar»). Es un límite del dataset, no de la búsqueda.
- **El árbol de Patrón de movimiento es aproximado**: se infiere del nombre; 80,4 % se clasifica y unos 5 de cada 60
  clasificados, a ojo, están mal. Por eso la interfaz lo avisa siempre.
- **Cada búsqueda tarda unos 6 s**: está medido y la causa y la propuesta de arreglo están en `docs/rendimiento.md`
  (no aplicada).

## 9. Si algo sale mal

| Síntoma | Qué hacer |
|---|---|
| «No se pudo cargar», 502 o «Lost connection» | MariaDB se ha caído antes en este equipo. Reiniciar SHAMP y repetir. |
| Todo muy lento (más de 10 s) | Cerrar programas pesados; sin internet cada búsqueda suma unos 2 s. |
| La cuenta demo no entra | Volver a ejecutar `crear_demo.php` (es idempotente) y usar la contraseña nueva. |
| Aparece «Elige un perfil» a mitad de la demo | La sesión del perfil caducó (30 minutos sin actividad; 15 la de administrador): elegirlo otra vez. |
| El panel sale vacío | Normal si nadie ha buscado: hacer el punto 0.5 y recargar. |
