"""Documentos que unen dos nodos de dos árboles cualesquiera (menús A+B).

    python scripts_py/puente_arboles.py ARBOL_A CLAVE_A ARBOL_B CLAVE_B
    python scripts_py/puente_arboles.py anatomia 1 equipamiento Mancuernas

Valida los cuatro datos contra el catálogo; si algo no existe responde error (no interpreta nada).
Imprime SOLO JSON ASCII: {"status", "nodos": [{arbol, nombre, ruta}], "documentos": [[origen, doc_id], ...]}.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    if len(sys.argv) != 5:
        print(json.dumps({"status": "error", "mensaje": "uso: ARBOL_A CLAVE_A ARBOL_B CLAVE_B"}))
        return
    from db_config import get_connection
    from arboles import Bosque
    from arboles.catalogo import docs_del_cruce
    from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql

    con = get_connection()
    if not con:
        print(json.dumps({"status": "error", "mensaje": "Sin conexión a MySQL"}))
        return
    bosque = Bosque.construir(ejercicios_desde_mysql(con), articulos_desde_mysql(con))
    con.close()
    resultado = docs_del_cruce(bosque, *sys.argv[1:5])
    if resultado is None:
        print(json.dumps({"status": "error", "mensaje": "árbol o concepto inexistente"}))
        return
    nodos, docs = resultado
    print(json.dumps({"status": "success",
                      "nodos": [{"arbol": n.arbol, "nombre": n.nombre, "ruta": [x.nombre for x in n.ruta()]} for n in nodos],
                      "documentos": [list(d) for d in docs]}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error", "mensaje": f"{type(e).__name__}: {e}"}))
