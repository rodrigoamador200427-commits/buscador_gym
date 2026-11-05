"""Cargadores de filas. Producción = MySQL (IDs reales); pruebas = CSV.

IMPORTANTE: en MySQL los IDs de `ejercicios` no empiezan en 1 (tras borrar filas
quedaron desde 640), así que los IDs que salen de los CSV (número de fila) SOLO sirven
para pruebas. Los árboles que alimenten a `postings` deben construirse desde MySQL.
"""
import csv

COLUMNAS_EJERCICIOS = ["nombre_es", "nombre_en", "descripcion_es", "descripcion_en",
                       "grupo_id", "modalidad", "equipamiento", "nivel"]


def ejercicios_desde_csv(ruta):
    """ejercicios_final.csv no trae encabezado; el id es el número de fila (1..N)."""
    filas = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for i, fila in enumerate(csv.reader(f), start=1):
            d = dict(zip(COLUMNAS_EJERCICIOS, fila))
            d["id"] = i
            d["equipamiento"] = d.get("equipamiento") or None   # vacío -> None
            filas.append(d)
    return filas


def articulos_desde_csv(ruta):
    """articulos.csv trae encabezado (titulo, contenido, etiquetas); id = fila (1..N)."""
    with open(ruta, encoding="utf-8", newline="") as f:
        return [{"id": i, **fila} for i, fila in enumerate(csv.DictReader(f), start=1)]


def ejercicios_desde_mysql(conexion):
    cur = conexion.cursor(dictionary=True)
    cur.execute("SELECT id, nombre_es, grupo_id, modalidad, equipamiento, nivel FROM ejercicios")
    filas = cur.fetchall()
    cur.close()
    return filas


def articulos_desde_mysql(conexion):
    cur = conexion.cursor(dictionary=True)
    cur.execute("SELECT id, titulo, etiquetas FROM articulos")
    filas = cur.fetchall()
    cur.close()
    return filas
