# Rendimiento: medición y propuesta (fase 7)

Medido el 19 de noviembre de 2026 con el corpus completo: 2 000 artículos, 2 848 ejercicios, 3 860 términos
y 126 771 postings. Servidor `php -S` y MariaDB locales. Los números cambian con la máquina; el reparto, no.

Cómo repetirlo:

```
D:\Tools\SHAMP\php\php.exe tests\medir_rendimiento.php      # de punta a punta por HTTP (solo BD de pruebas)
python scripts_py\perfil_motor.py                           # por fases dentro de Python (solo lee la BD)
```

## 1. Resultado

| Petición | Tiempo (3 repeticiones) |
|---|---|
| `buscar.php`, 8 consultas distintas (de «pecho» a «pecho kettlebell») | **6,15 a 6,69 s**, todas |
| `recomendaciones.php` | **6,05 a 6,48 s** |
| `menus.php?accion=catalogo` | 1,18 a 1,27 s |
| `menus.php?accion=cruce` | 1,20 a 1,23 s |
| `detalle.php` | 0,02 s |
| `etiquetas.php` | 0,07 a 0,21 s |
| Panel: las 6 secciones seguidas, con 40 003 eventos, 5 000 consultas y 62 cuentas | 0,62 a 0,75 s |
| Panel: la sección más lenta (`menos`) | 0,18 a 0,30 s |

**El panel y el detalle están bien. Toda búsqueda y toda recomendación tarda unos 6 s, el triple del límite de 2 s.**
Y no depende de la consulta: «pecho» y «creatina» tardan lo mismo, porque el tiempo no está en buscar.

## 2. Dónde se va el tiempo

`buscar.php` lanza `motor_arboles.py` con `shell_exec`: un proceso nuevo de Python por búsqueda, que no
conserva nada. Ese proceso tarda unos 6 s (el resto de la petición, PHP y la hidratación de tarjetas, unos 0,2 s):

| Fase del proceso de Python | Tiempo |
|---|---|
| `import nltk` | **4,8 a 5,1 s** |
| `nltk.download('stopwords')` (una petición de red) | 0,17 s |
| Importar el resto del proyecto | 0,13 s |
| Leer 2 848 ejercicios y 2 000 artículos | 0,04 s |
| **Construir los 5 árboles y las aristas de los 10 pares** | **0,58 a 0,59 s** |
| Leer el diccionario, sacar raíces, recuperar con TF-IDF, descubrir | 0,05 a 0,25 s |

Tres hechos que importan:

1. **Los árboles no son el cuello de botella.** Se reconstruyen en cada consulta, como se sospechaba, pero eso
   cuesta 0,6 s. Lo que cuesta 5 s es `import nltk`: al importar el paquete, NLTK carga `scipy.stats`
   (2,7 s, por `nltk.metrics`) y `nltk.chunk` (1,7 s), módulos que aquí no se usan. Solo se necesitan el
   stemmer Snowball en español y la lista de stopwords.
   `menus.php?accion=catalogo` y `cruce` no importan NLTK y por eso tardan 1,2 s (árboles incluidos).
2. **`recomendaciones.php` paga lo mismo**: `recommender.py` importa `nlp_processor` solo para el stemmer.
3. **Cada proceso hace una petición de red inútil.** `nlp_processor.py` ejecuta `nltk.download('stopwords')`
   al importarse. Con internet cuesta 0,17 s. Sin internet falla en silencio (las stopwords ya están
   instaladas y la búsqueda sigue funcionando) pero tarda unos 2 s más: en una demo sin red, cada
   búsqueda sería de unos 8 s.

Además, 6 s de CPU por petición significa que unas pocas búsquedas simultáneas saturan el servidor.

## 3. Propuesta (NO aplicada)

En orden de ganancia contra riesgo. Las dos primeras se pueden hacer sin cambiar la arquitectura.

**A. Sacar NLTK del camino de la consulta** (de unos 6,2 s a cerca de 1 s; la más rentable).
- Usar el paquete `snowballstemmer` (Python puro, el mismo algoritmo Snowball para español) en
  `motor_arboles.py`, `recommender.py` y `stem_query.py`. NLTK se queda solo en `indexer.py`.
- Guardar la lista de stopwords de NLTK (313 palabras) en un archivo del proyecto y leerla de ahí.
  No sirve `stopwords.txt` de la raíz: tiene 402 palabras (solo 101 en común con las de NLTK) y hoy ningún
  código lo lee.
- Quitar `nltk.download` de `nlp_processor.py` (la descarga es un paso de instalación, no de cada consulta).
- **Antes de adoptarla**, comprobar con una prueba que ambos stemmers dan las mismas raíces para los 3 860
  términos del diccionario y para las 38 consultas de medición. Si una raíz cambia, el índice dejaría de
  coincidir con las consultas. Esta cifra es una estimación: no se midió porque implica instalar un paquete.

**B. Guardar los árboles ya construidos** (ahorra unos 0,55 s). `generar_etiquetas.py` ya se corre cada vez
que cambia el contenido: ahí se puede serializar el `Bosque` (árboles, pertenencia y aristas) junto con una
huella del contenido, y `motor_arboles.py` lo carga en vez de reconstruirlo. Si la huella no coincide, lo
reconstruye. Con A y B, unos 0,3 s por búsqueda.

**C. Guardar la respuesta de Python por consulta** (para consultas repetidas). El descubrimiento no depende
del perfil (solo la lista de resultados sí), así que se puede guardar por consulta normalizada, con la misma
huella de contenido. Útil en una demo, donde se repiten las mismas búsquedas.

**D. Un proceso de Python que siga vivo** (un servicio local que carga todo una vez; unos 0,1 s por consulta).
Es lo más rápido y lo más pesado: hay que arrancarlo, reiniciarlo cuando cambia el contenido y manejar sus
fallos en SHAMP sobre Windows. No hace falta si se hacen A y B.

Recomendación: **A y B juntas**, con la prueba de equivalencia de raíces. C solo si se quiere que la demo
sea instantánea. D no.
