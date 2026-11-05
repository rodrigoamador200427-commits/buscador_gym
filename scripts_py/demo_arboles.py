"""Demo para el avance: construye los árboles y muestra recorridos y enlaces.

CSV (pruebas):   python scripts_py/demo_arboles.py --csv-ejercicios X.csv --csv-articulos Y.csv
MySQL (real):    python scripts_py/demo_arboles.py --mysql
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from arboles import (construir_aristas, construir_arbol_anatomia, construir_arbol_temas,
                     por_niveles, posorden, preorden)
from arboles.fuentes import (articulos_desde_csv, articulos_desde_mysql,
                             ejercicios_desde_csv, ejercicios_desde_mysql)


def imprimir_hasta_nivel(raiz, nivel_max):
    for n in preorden(raiz):
        if n.nivel <= nivel_max:
            extra = f"  ({n.tamano() - 1} descendientes)" if not n.es_hoja else ""
            print("  " * n.nivel + f"- {n.nombre}{extra}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-ejercicios")
    p.add_argument("--csv-articulos")
    p.add_argument("--mysql", action="store_true")
    a = p.parse_args()

    if a.mysql:
        from db_config import get_connection
        con = get_connection()
        ejercicios, articulos = ejercicios_desde_mysql(con), articulos_desde_mysql(con)
    else:
        ejercicios, articulos = ejercicios_desde_csv(a.csv_ejercicios), articulos_desde_csv(a.csv_articulos)

    A, T = construir_arbol_anatomia(ejercicios), construir_arbol_temas(articulos)
    E = construir_aristas(articulos, A, T)

    print(f"\n== ÁRBOL ANATOMÍA: {len(A)} nodos, altura {A.raiz.altura()} ==")
    imprimir_hasta_nivel(A.raiz, 2)
    print(f"\n== ÁRBOL TEMAS: {len(T)} nodos, altura {T.raiz.altura()} ==")
    imprimir_hasta_nivel(T.raiz, 2)

    print("\n== Preorden (primeros 8) / Posorden (primeros 8) del árbol de temas ==")
    print("pre :", [n.nombre for n in list(preorden(T.raiz))[:8]])
    print("post:", [n.nombre[:28] for n in list(posorden(T.raiz))[:8]])
    print("niveles:", [n.nombre for n in list(por_niveles(T.raiz))[:8]])

    print(f"\n== Aristas cruzadas músculo↔tema: {E.total()} ==")
    for gid, musculo in A.meta["musculos"].items():
        vecinos = [(T.nodo(t).nombre, w, round(l, 1)) for t, w, l in E.vecinos_de_musculo(musculo.id)[:3]]
        print(f"  {musculo.nombre:15} -> {vecinos}")   # (tema, nº artículos, lift)


if __name__ == "__main__":
    main()
