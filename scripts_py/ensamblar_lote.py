"""Une los archivos de trabajo de un lote en el CSV del lote y su plan.

    python scripts_py/ensamblar_lote.py 1 corpus/lotes/trabajo/lote_01_*.csv

Cada archivo de trabajo trae las columnas  tema, musculo, titulo, contenido, etiquetas  (el tema y
el músculo son lo que se PRETENDE; validar_lote.py comprueba que las etiquetas los produzcan).
Escribe corpus/lotes/lote_NN.csv (titulo, contenido, etiquetas, como articulos.csv) y
corpus/lotes/lote_NN.plan.csv (titulo, tema, musculo). Si existe corpus/lotes/lote_NN.cuotas.csv
comprueba que el lote cumple las cuotas de planear_lote.py celda por celda.
"""
import csv
import glob
import os
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ENTRADA = ["tema", "musculo", "titulo", "contenido", "etiquetas"]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(__doc__)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    numero = int(argv[0])
    archivos = sorted(a for patron in argv[1:] for a in glob.glob(patron))
    filas = []
    for ruta in archivos:
        with open(ruta, encoding="utf-8", newline="") as f:
            lector = csv.reader(f)
            enc = next(lector, None)
            if enc is None or [c.strip().lower() for c in enc] != ENTRADA:
                print(f"ERROR: {ruta}: el encabezado debe ser {ENTRADA}")
                return 1
            for r in lector:
                if len(r) != 5:
                    print(f"ERROR: {ruta}: fila con {len(r)} columnas: {r[:3]}")
                    return 1
                filas.append([c.strip() for c in r])
    carpeta = os.path.join(RAIZ, "corpus", "lotes")
    os.makedirs(carpeta, exist_ok=True)
    ruta_lote = os.path.join(carpeta, f"lote_{numero:02d}.csv")
    ruta_plan = os.path.join(carpeta, f"lote_{numero:02d}.plan.csv")
    with open(ruta_lote, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["titulo", "contenido", "etiquetas"])
        for tema, musculo, titulo, contenido, etiquetas in filas:
            w.writerow([titulo, contenido, etiquetas])
    with open(ruta_plan, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["titulo", "tema", "musculo"])
        for tema, musculo, titulo, contenido, etiquetas in filas:
            w.writerow([titulo, tema, musculo])
    print(f"{len(filas)} artículos -> {ruta_lote} y {ruta_plan}")

    ruta_cuotas = os.path.join(carpeta, f"lote_{numero:02d}.cuotas.csv")
    if os.path.exists(ruta_cuotas):
        with open(ruta_cuotas, encoding="utf-8", newline="") as f:
            cuotas = Counter({(r["tema"], r["musculo"]): int(r["n"]) for r in csv.DictReader(f)})
        reales = Counter((tema, musculo) for tema, musculo, *_ in filas)
        distintas = {k: (cuotas.get(k, 0), reales.get(k, 0)) for k in set(cuotas) | set(reales) if cuotas.get(k, 0) != reales.get(k, 0)}
        if distintas:
            print("ERROR: el lote no cumple las cuotas (celda: cuota, real):")
            for k, v in sorted(distintas.items()):
                print(f"  {k}: {v}")
            return 1
        print("el lote cumple las cuotas de planear_lote.py celda por celda")
    return 0


if __name__ == "__main__":
    sys.exit(main())
