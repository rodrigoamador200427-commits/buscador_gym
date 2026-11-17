"""Importa un lote validado a la tabla articulos con origen_contenido = 'generado'.

    python scripts_py/importar_lote.py corpus/lotes/lote_01.csv --plan corpus/lotes/lote_01.plan.csv
    python scripts_py/importar_lote.py corpus/lotes/lote_01.csv --dry-run

Vuelve a validar el lote con validar_lote.py y NO importa nada si hay errores. Inserta todo en una
sola transacción (todo o nada) con consultas preparadas. Como la validación rechaza títulos que ya
existen, volver a correrlo con el mismo lote no duplica nada.

NO reconstruye el índice. Después hay que correr, en este orden:
    python scripts_py/indexer.py              (diccionario y postings: lo hace vacío y recalcula todo)
    python scripts_py/generar_etiquetas.py    (etiquetas y rutas; sin esto los nuevos no las tienen)
"""
import argparse
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

from validar_lote import (cargar_objetivos, contar_familias, informe, leer_existentes,  # noqa: E402
                          leer_lote, leer_plan, validar)

SQL_INSERTAR = "INSERT INTO articulos (titulo, contenido, etiquetas, origen_contenido) VALUES (%s, %s, %s, 'generado')"


def tiene_columna_origen(cursor):
    cursor.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                   "AND TABLE_NAME = 'articulos' AND COLUMN_NAME = 'origen_contenido'")
    return cursor.fetchone()["n"] == 1


def importar(conn, lote):
    """Inserta las filas del lote como 'generado', todo o nada. Devuelve (primer_id, ultimo_id)."""
    cur = conn.cursor()
    try:
        ids = []
        for a in lote:
            cur.execute(SQL_INSERTAR, (a["titulo"], a["contenido"], a["etiquetas"]))
            ids.append(cur.lastrowid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    return (min(ids), max(ids)) if ids else (None, None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("lote")
    ap.add_argument("--plan")
    ap.add_argument("--dry-run", action="store_true", help="valida y muestra el informe, pero no inserta")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lote, fallos = leer_lote(args.lote)
    if fallos:
        for f in fallos:
            print("ERROR de formato:", f)
        return 1
    from db_config import get_connection
    conn = get_connection()
    if conn is None:
        print("ERROR: sin conexión con la BD")
        return 1
    try:
        cur = conn.cursor(dictionary=True)
        if not tiene_columna_origen(cur):
            print("ERROR: falta articulos.origen_contenido; aplica sql/esquema_corpus.sql primero")
            return 1
        existentes = leer_existentes(cur)
        conteo = contar_familias(cur)
        cur.close()
        plan = leer_plan(args.plan) if args.plan else None
        res = validar(lote, existentes, conteo, plan)
        informe(res, lote, existentes, cargar_objetivos())
        if res["errores"]:
            print(f"\nNO SE IMPORTÓ NADA: hay {len(res['errores'])} errores.")
            return 1
        if args.dry_run:
            print("\n--dry-run: el lote es válido; no se insertó nada.")
            return 0
        primero, ultimo = importar(conn, lote)
        print(f"\nIMPORTADOS {len(lote)} artículos como 'generado' (ids {primero} a {ultimo}).")
        print("Falta reconstruir el índice:  python scripts_py/indexer.py  y luego  python scripts_py/generar_etiquetas.py")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
