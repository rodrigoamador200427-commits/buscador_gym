"""Reporte del árbol de Patrón de movimiento: cuántos ejercicios hay en cada patrón y la lista COMPLETA de
los que ninguna regla pudo clasificar.

    python scripts_py/patron_sin_clasificar.py                        imprime el resumen
    python scripts_py/patron_sin_clasificar.py --escribir docs/patron_sin_clasificar.md

La clasificación es APROXIMADA (reglas de palabras clave sobre `nombre_es`, ver arboles/patrones.py):
lo que no se reconoce no se adivina y queda en «Sin clasificar». Solo lee la BD.
"""
import argparse
import collections
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir")
    args = ap.parse_args()

    from db_config import get_connection
    from arboles.fuentes import ejercicios_desde_mysql
    from arboles.patrones import GRUPOS_PATRON, patron_de_nombre

    ejercicios = sorted(ejercicios_desde_mysql(get_connection()), key=lambda e: int(e["id"]))
    por_patron = collections.Counter(patron_de_nombre(e["nombre_es"]) for e in ejercicios)
    sin = [e for e in ejercicios if not patron_de_nombre(e["nombre_es"])]
    total = len(ejercicios)
    clasificados = total - len(sin)

    lineas = ["# Árbol de Patrón de movimiento: reporte de la clasificación", "",
              "Generado por `scripts_py/patron_sin_clasificar.py` (no editar a mano).", "",
              "**La clasificación es aproximada.** El patrón se infiere con reglas de palabras clave sobre el nombre del ejercicio "
              "(`nombre_es`, que son traducciones automáticas con marcas y apellidos). Lo que ninguna regla reconoce NO se adivina: "
              "queda en «Sin clasificar». Los que sí se clasifican pueden equivocarse en casos mixtos "
              f"(una revisión a ojo de 60 al azar encontró unos 5 mal).", "",
              f"- Ejercicios: {total}",
              f"- Clasificados: {clasificados} ({100 * clasificados / total:.1f} %)",
              f"- Sin clasificar: {len(sin)} ({100 * len(sin) / total:.1f} %)", "",
              "| Grupo | Patrón | Ejercicios |", "|---|---|---|"]
    for grupo, patrones in GRUPOS_PATRON:
        for p in patrones:
            lineas.append(f"| {grupo} | {p} | {por_patron[p]} |")
    lineas += [f"| (raíz) | Sin clasificar | {len(sin)} |", "",
               f"## Ejercicios sin clasificar ({len(sin)})", "", "| id | nombre_es |", "|---|---|"]
    lineas += [f"| {e['id']} | {str(e['nombre_es']).replace('|', '/')} |" for e in sin]
    texto = "\n".join(lineas) + "\n"

    print(f"ejercicios {total} | clasificados {clasificados} ({100 * clasificados / total:.1f} %) | sin clasificar {len(sin)}")
    for grupo, patrones in GRUPOS_PATRON:
        print(f"  {grupo}: " + ", ".join(f"{p} {por_patron[p]}" for p in patrones))
    if args.escribir:
        ruta = args.escribir if os.path.isabs(args.escribir) else os.path.join(RAIZ, args.escribir)
        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        print("escrito", ruta)


if __name__ == "__main__":
    main()
