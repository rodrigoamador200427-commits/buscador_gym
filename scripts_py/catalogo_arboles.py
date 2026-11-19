"""CLI de los menús A+B: imprime el catálogo de los árboles y de sus cruces como JSON ASCII.

    python scripts_py/catalogo_arboles.py
Devuelve {"status", "arboles": [...], "pares": {...}} (ver arboles/catalogo.py: catalogo_general).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    from db_config import get_connection
    from arboles import Bosque
    from arboles.catalogo import catalogo_general
    from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql

    con = get_connection()
    if not con:
        print(json.dumps({"status": "error", "mensaje": "Sin conexión a MySQL"}))
        return
    bosque = Bosque.construir(ejercicios_desde_mysql(con), articulos_desde_mysql(con))
    con.close()
    print(json.dumps({"status": "success", **catalogo_general(bosque)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error", "mensaje": f"{type(e).__name__}: {e}"}))
