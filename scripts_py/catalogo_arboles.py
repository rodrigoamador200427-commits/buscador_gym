"""CLI de los menús A+B: imprime el catálogo (músculos, temas, puentes) como JSON ASCII."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    from db_config import get_connection
    from arboles import construir_aristas, construir_arbol_anatomia, construir_arbol_temas
    from arboles.catalogo import catalogo
    from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql

    con = get_connection()
    if not con:
        print(json.dumps({"status": "error", "mensaje": "Sin conexión a MySQL"}))
        return
    ar = articulos_desde_mysql(con)
    A, T = construir_arbol_anatomia(ejercicios_desde_mysql(con)), construir_arbol_temas(ar)
    con.close()
    print(json.dumps({"status": "success", **catalogo(A, T, construir_aristas(ar, A, T))}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error", "mensaje": f"{type(e).__name__}: {e}"}))
