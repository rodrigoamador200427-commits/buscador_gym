"""Calcula cuántos artículos de cada celda (tema x músculo) corresponden al próximo lote.

    python scripts_py/planear_lote.py 100
    python scripts_py/planear_lote.py 100 --salida corpus/lotes/lote_01.cuotas.csv

Parte de corpus/objetivos.json (la matriz aprobada de nuevos artículos) y le resta lo que ya
hay importado como 'generado' en la BD (clasificado con las etiquetas, igual que el árbol de
Temas). Reparte las N plazas del lote en proporción a lo que falta, con el método del resto
mayor, así cada lote avanza parejo hacia la meta. Solo lee la BD.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)

from arboles import taxonomia as T   # noqa: E402
from validar_lote import clasificar  # noqa: E402


def celda_de(etiquetas):
    """(tema, nombre del músculo o '') de un artículo: con varios músculos cuenta el primero."""
    tema, musculos = clasificar(etiquetas)
    return tema, (T.MUSCULOS[musculos[0]] if musculos else "")


def falta(objetivos, generados):
    """{(tema, musculo): cuántos faltan} = matriz de nuevos menos lo ya generado (nunca negativo)."""
    res = {}
    for tema, fila in objetivos["matriz_nuevos"].items():
        for musculo, meta in fila.items():
            res[(tema, musculo)] = max(0, meta - generados.get((tema, musculo), 0))
    return res


def repartir(pendiente, n):
    """Reparte n plazas entre las celdas en proporción a lo que falta (resto mayor). Determinista."""
    total = sum(pendiente.values())
    if total == 0 or n <= 0:
        return {}
    n = min(n, total)
    exacto = {k: v * n / total for k, v in pendiente.items()}
    base = {k: min(pendiente[k], int(x)) for k, x in exacto.items()}
    resto = n - sum(base.values())
    for k in sorted(exacto, key=lambda k: (-(exacto[k] - int(exacto[k])), k)):
        if resto == 0:
            break
        if base[k] < pendiente[k]:
            base[k] += 1
            resto -= 1
    return {k: v for k, v in base.items() if v > 0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, help="tamaño del lote")
    ap.add_argument("--salida", help="CSV tema,musculo,n con las cuotas")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with open(os.path.join(RAIZ, "corpus", "objetivos.json"), encoding="utf-8") as f:
        objetivos = json.load(f)
    from db_config import get_connection
    conn = get_connection()
    if conn is None:
        print("ERROR: sin conexión con la BD")
        return 1
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT etiquetas FROM articulos WHERE origen_contenido = 'generado'")
    generados = Counter(celda_de(r["etiquetas"] or "") for r in cur.fetchall())
    conn.close()

    pendiente = falta(objetivos, generados)
    cuotas = repartir(pendiente, args.n)
    print(f"ya generados: {sum(generados.values())} | faltan: {sum(pendiente.values())} | este lote: {sum(cuotas.values())}")
    orden = [t[1] for t in T.TEMAS]
    filas = sorted(cuotas.items(), key=lambda kv: (orden.index(kv[0][0]), kv[0][1]))
    print(f"\n{'tema':26s} {'músculo':16s} {'cuota':>5s} {'falta':>6s}")
    for (tema, musculo), n in filas:
        print(f"{tema:26s} {musculo or '(sin músculo)':16s} {n:5d} {pendiente[(tema, musculo)]:6d}")
    por_tema = Counter()
    for (tema, _), n in cuotas.items():
        por_tema[tema] += n
    print("\npor tema:", {t: por_tema[t] for t in orden if por_tema[t]})
    if args.salida:
        with open(args.salida, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tema", "musculo", "n"])
            for (tema, musculo), n in filas:
                w.writerow([tema, musculo, n])
        print("cuotas guardadas en", args.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
