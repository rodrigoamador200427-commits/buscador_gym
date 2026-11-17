"""Ejecuta las 18 consultas de referencia (corpus/consultas_referencia.json) y compara antes y después.

    python scripts_py/consultas_referencia.py guardar corpus/resultados/base.json
    python scripts_py/consultas_referencia.py comparar corpus/resultados/base.json --guardar corpus/resultados/lote_01.json

La búsqueda es la de buscar.php sin la expansión por árboles: raíces de la consulta (nlp_processor)
y la suma de peso_tfidf en los postings, de mayor a menor, top 20. Solo lee la BD.

Qué se compara (los resultados cambian a propósito al agregar artículos; lo que se vigila es que un
lote no desplace lo que ya era bueno):
  - top1: ¿el primer resultado de antes sigue entre los 3 primeros? Si no, la consulta se marca REVISAR.
  - top5: cuántos de los 5 primeros de antes siguen entre los 5 primeros.
  - perdidos10: cuántos de los 10 primeros de antes ya no están en el top 10.
  - nuevos5 / nuevos10: cuántos generados entran en el top 5 / top 10.
"""
import argparse
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)

TOP = 20


def cargar_consultas():
    with open(os.path.join(RAIZ, "corpus", "consultas_referencia.json"), encoding="utf-8") as f:
        return json.load(f)["consultas"]


def buscar(cursor, consulta, limite=TOP):
    """[{origen, doc_id, score, titulo, generado}] con la consulta SQL de buscar.php."""
    from nlp_processor import clean_and_stem
    raices = list(dict.fromkeys(clean_and_stem(consulta)))
    if not raices:
        return []
    marcas = ",".join(["%s"] * len(raices))
    cursor.execute(
        "SELECT p.doc_id, p.origen, SUM(p.peso_tfidf) AS score FROM diccionario d JOIN postings p ON d.id = p.termino_id "
        f"WHERE d.termino IN ({marcas}) GROUP BY p.doc_id, p.origen ORDER BY score DESC, p.origen, p.doc_id LIMIT {int(limite)}",
        tuple(raices))
    filas = cursor.fetchall()
    resultados = []
    for r in filas:
        if r["origen"] == "articulos":
            cursor.execute("SELECT titulo, origen_contenido FROM articulos WHERE id = %s", (r["doc_id"],))
            a = cursor.fetchone() or {}
            titulo, generado = a.get("titulo", "?"), a.get("origen_contenido") == "generado"
        else:
            cursor.execute("SELECT nombre_es FROM ejercicios WHERE id = %s", (r["doc_id"],))
            e = cursor.fetchone() or {}
            titulo, generado = e.get("nombre_es", "?"), False
        resultados.append({"origen": r["origen"], "doc_id": int(r["doc_id"]), "score": round(float(r["score"]), 4),
                           "titulo": titulo, "generado": generado})
    return resultados


def ejecutar():
    from db_config import get_connection
    conn = get_connection()
    if conn is None:
        raise SystemExit("ERROR: sin conexión con la BD")
    cur = conn.cursor(dictionary=True)
    try:
        return [{"id": q["id"], "consulta": q["consulta"], "resultados": buscar(cur, q["consulta"])} for q in cargar_consultas()]
    finally:
        conn.close()


def clave(r):
    return f"{r['origen']}:{r['doc_id']}"


def comparar(antes, despues):
    """Una fila por consulta con las métricas descritas arriba."""
    ant = {q["id"]: q for q in antes}
    filas = []
    for q in despues:
        a = ant.get(q["id"])
        if a is None:
            continue
        ka = [clave(r) for r in a["resultados"]]
        kd = [clave(r) for r in q["resultados"]]
        top1 = bool(ka) and ka[0] in kd[:3]
        top5 = len(set(ka[:5]) & set(kd[:5]))
        perdidos10 = len(set(ka[:10]) - set(kd[:10]))
        nuevos5 = sum(1 for r in q["resultados"][:5] if r["generado"])
        nuevos10 = sum(1 for r in q["resultados"][:10] if r["generado"])
        filas.append({"id": q["id"], "consulta": q["consulta"], "vacia_antes": not ka, "vacia_despues": not kd, "top1": top1,
                      "top5": top5, "perdidos10": perdidos10, "nuevos5": nuevos5, "nuevos10": nuevos10,
                      "revisar": (not kd) or (bool(ka) and not top1),
                      "primero_antes": a["resultados"][0]["titulo"] if ka else "", "primero_despues": q["resultados"][0]["titulo"] if kd else ""})
    return filas


def imprimir(filas, salida=print):
    salida(f"{'#':>2s} {'consulta':34s} {'top1':>5s} {'top5':>5s} {'perd10':>6s} {'nuev5':>5s} {'nuev10':>6s}  estado")
    for f in filas:
        estado = "REVISAR" if f["revisar"] else "ok"
        salida(f"{f['id']:2d} {f['consulta']:34s} {'sí' if f['top1'] else 'NO':>5s} {f['top5']:>3d}/5 {f['perdidos10']:6d} {f['nuevos5']:5d} {f['nuevos10']:6d}  {estado}")
    salida(f"consultas a revisar: {sum(1 for f in filas if f['revisar'])} de {len(filas)} | "
           f"consultas sin resultados: {sum(1 for f in filas if f['vacia_despues'])}")
    for f in filas:
        if f["revisar"]:
            salida(f"  - #{f['id']} «{f['consulta']}»: antes «{f['primero_antes']}» -> ahora «{f['primero_despues']}»")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["guardar", "comparar"])
    ap.add_argument("archivo")
    ap.add_argument("--guardar", help="en 'comparar', guarda también los resultados actuales aquí")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    actual = ejecutar()
    if args.accion == "guardar":
        with open(args.archivo, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=1)
        vacias = [q["id"] for q in actual if not q["resultados"]]
        print(f"guardadas {len(actual)} consultas en {args.archivo}; sin resultados: {vacias or 'ninguna'}")
        for q in actual:
            top = q["resultados"][0]["titulo"] if q["resultados"] else "(sin resultados)"
            print(f"  {q['id']:2d} {q['consulta']:34s} -> {top[:60]}")
        return 0
    with open(args.archivo, encoding="utf-8") as f:
        base = json.load(f)
    filas = comparar(base, actual)
    imprimir(filas)
    if args.guardar:
        with open(args.guardar, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
