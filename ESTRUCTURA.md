# Estructura del proyecto buscador_gym (Fases 1-5: árboles + motor + integración)

## Qué se agrega
Todo es nuevo salvo **`buscar.php`, que se REEMPLAZA** (respáldalo antes). `motor_grafos.py` queda obsoleto (no se borra).

```
buscador_gym/
├── scripts_py/
│   ├── arboles/                  <- NUEVO paquete, una responsabilidad por archivo
│   │   ├── taxonomia.py          fuente única de verdad: músculos, regiones, equipamiento, temas, etiquetas
│   │   ├── nodo.py               Nodo y Arbol (raíz, padre, hijos, nivel, altura, hoja, ruta)
│   │   ├── recorridos.py         preorden, inorden, posorden, por niveles, acumular_posorden, mejor_camino
│   │   ├── constructor.py        construye el árbol de anatomía y el de temas desde filas
│   │   ├── enlaces.py            aristas cruzadas músculo<->tema (peso y lift) derivadas de los artículos
│   │   ├── fuentes.py            cargadores: MySQL (real) y CSV (pruebas)
│   │   ├── motor.py              MotorArboles: consulta -> nodos -> salto entre árboles (campo `via`)
│   │   └── consulta.py           raíces de la consulta (ñ->n, determinista) y recuperación TF-IDF
│   ├── motor_arboles.py          ENTRADA ÚNICA para PHP (JSON: raices + descubrimiento)
│   ├── tests/test_arboles.py     18 pruebas
│   ├── tests/test_motor.py       15 pruebas del motor
│   └── demo_arboles.py           imprime árboles, recorridos y enlaces (para el avance)
├── buscar.php                    PARCHADO: una llamada a Python, sin LIKE...LIMIT 1 ni random
└── sql/esquema_arboles.sql       tablas nodos, doc_nodo, aristas_cruzadas (aún sin ejecutar)
```

## Los dos árboles

- **Anatomía** (ejercicios): Cuerpo humano > Región > Músculo > Equipamiento > Ejercicio. Altura 4.
  "pecho + mancuernas" es un solo nodo: Cuerpo humano > Tren superior > Pecho > Mancuernas.
- **Temas** (artículos): Conocimiento > Rama > Tema > Artículo. Altura 3.
- **Aristas cruzadas**: un artículo que menciona un músculo y un tema une sus dos nodos.
  Eso convierte los dos árboles en un grafo (el "salto" del profe).

## Cómo ejecutar (desde la raíz del proyecto)

```
python scripts_py/demo_arboles.py --mysql
python scripts_py/demo_arboles.py --csv-ejercicios RUTA.csv --csv-articulos RUTA.csv
cd scripts_py && python -m pytest tests -v
```
Las pruebas con datos reales se activan con las variables de entorno CSV_EJERCICIOS y CSV_ARTICULOS.

## Advertencias

1. **IDs**: los IDs de `ejercicios` en MySQL empiezan en 640, no en 1. Los árboles que se
   conecten con `postings` deben construirse con `--mysql`; con CSV los IDs son número de fila.
2. `fuentes.py` (MySQL) y `sql/esquema_arboles.sql` NO se probaron contra una base real.
3. `modalidad` = 88 % "Strength": no sirve por sí sola para el objetivo "ganar fuerza".
4. Con 341 artículos, los lift de pocos artículos (2 a 4) son ruidosos.

## Política del motor (`via`)

interseccion > sin_interseccion (se dice, no se inventa) > concepto > concepto_local > recuperacion > ninguno.
Determinista: la misma consulta devuelve siempre lo mismo.

## Probar la integración (en tu máquina)

```
python scripts_py/motor_arboles.py "ganar fuerza"
python scripts_py/motor_arboles.py "pecho fuerza"
python scripts_py/motor_arboles.py "como bajar de peso"
```
Debe imprimir un JSON con `"status": "success"`. Luego abre el buscador y prueba las mismas consultas.

## Siguientes fases

2. Cargador a MySQL (nodos, doc_nodo, aristas_cruzadas) — opcional.
6. Panel visual del árbol y menús A+B en `index.html`.
7. Separar stopwords gramaticales de palabras-objetivo (`stopwords.txt`).
