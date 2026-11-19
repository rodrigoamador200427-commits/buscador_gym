"""Medición de la fase 6B: las 18 consultas de referencia con el motor de dos árboles (fase 1) y con
el de cuatro, más unas consultas que combinan equipamiento o nivel, y las aristas de cada par de árboles.

    python scripts_py/medir_arboles.py                    imprime las tablas
    python scripts_py/medir_arboles.py --guardar corpus/resultados/arboles_6b.json

Solo lee la BD. Para cada consulta ejecuta el mismo proceso que motor_arboles.py (raíces, preparación,
recuperación TF-IDF y descubrimiento). «Fallback» = el descubrimiento no pudo salir de un concepto
reconocido o de un cruce: via en {ninguno, sin_interseccion, concepto_local, recuperacion}.
"""
import argparse
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)

FALLBACK = ("ninguno", "sin_interseccion", "concepto_local", "recuperacion")

# Consultas nuevas de la fase 6B (no están en las 18 de referencia): combinan equipamiento o nivel.
CONSULTAS_6B = [
    "pecho mancuernas principiante", "press de banca con barra", "espalda polea", "triceps kettlebell avanzado",
    "sentadilla maquina principiante", "abdomen peso corporal", "ejercicios con bandas", "biceps mancuernas",
    "ganar fuerza con barra", "dieta para principiantes", "pecho kettlebell principiante", "pelota de ejercicio abdomen",
    # Patrón de movimiento (clasificación aproximada)
    "jalon espalda polea", "bisagra gluteo", "fondos triceps", "zancada cuadriceps mancuernas",
    "tiron horizontal principiante", "press militar barra", "arrancada barra avanzado", "saltos principiante",
]


def cargar_consultas():
    with open(os.path.join(RAIZ, "corpus", "consultas_referencia.json"), encoding="utf-8") as f:
        return [c["consulta"] for c in json.load(f)["consultas"]]


def resumen(r):
    destino = r["destino"]
    return {"via": r["via"],
            "origen": None if r["origen"] is None else f'{r["origen"]["titulo_arbol"]}: {r["origen"]["nombre"]}',
            "destino": None if destino is None else f'{destino["titulo_arbol"]}: {destino["nombre"]}',
            "arboles": [n["titulo_arbol"] for n in r.get("nodos", [])],
            "documento": (r["documentos"][0]["origen"], r["documentos"][0]["doc_id"]) if r["documentos"] else None}


def metricas(filas):
    vias = {}
    for f in filas:
        vias[f["via"]] = vias.get(f["via"], 0) + 1
    destinos = {f["destino"] for f in filas if f["destino"]}
    return {"consultas": len(filas), "por_via": dict(sorted(vias.items())),
            "fallback": sum(n for v, n in vias.items() if v in FALLBACK),
            "destinos_distintos": len(destinos),
            "documentos_distintos": len({f["documento"] for f in filas if f["documento"]})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guardar")
    args = ap.parse_args()

    from db_config import get_connection
    from nlp_processor import stemmer, stop_words
    from stem_query import THESAURUS, strip_vowels
    from arboles import Bosque, MotorArboles, construir_aristas
    from arboles.consulta import raices_de, recuperar
    from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql
    from arboles.taxonomia import PALABRAS_INTENCION, TITULO_ARBOL

    con = get_connection()
    bosque = Bosque.construir(ejercicios_desde_mysql(con), articulos_desde_mysql(con))
    A, T = bosque.arbol("anatomia"), bosque.arbol("temas")
    articulos = articulos_desde_mysql(con)
    motor2 = MotorArboles(A, T, construir_aristas(articulos, A, T), stemmer.stem)    # dos árboles (fase 1)
    motor4 = MotorArboles.desde_bosque(bosque, stemmer.stem)                          # cuatro árboles

    cur = con.cursor(dictionary=True)
    cur.execute("SELECT termino FROM diccionario")
    vocabulario = {f["termino"] for f in cur.fetchall()}
    stop = set(stop_words) | PALABRAS_INTENCION

    def correr(motor, consulta):
        raices = raices_de(consulta, vocabulario, stemmer, stop, THESAURUS, strip_vowels)
        prep = motor.preparar_consulta(raices)
        return motor.descubrir(raices, recuperar(cur, prep["raices"]))

    salida = {"referencia": [], "nuevas": [], "pares": []}
    for clave, lista in (("referencia", cargar_consultas()), ("nuevas", CONSULTAS_6B)):
        for q in lista:
            dos, cuatro = resumen(correr(motor2, q)), resumen(correr(motor4, q))
            salida[clave].append({"consulta": q, "dos_arboles": dos, "cuatro_arboles": cuatro,
                                  "cambia": (dos["via"], dos["destino"], dos["documento"]) != (cuatro["via"], cuatro["destino"], cuatro["documento"])})
    for (a, b), par in bosque.pares():
        docs = {d for _, ds in par.items() for d in ds}
        salida["pares"].append({"par": f"{TITULO_ARBOL[a]} x {TITULO_ARBOL[b]}", "aristas": par.total(), "documentos": len(docs),
                                "ejercicios": sum(1 for d in docs if d[0] == "ejercicios"),
                                "articulos": sum(1 for d in docs if d[0] == "articulos")})
    for clave in ("referencia", "nuevas"):
        salida[f"metricas_{clave}"] = {"dos_arboles": metricas([f["dos_arboles"] for f in salida[clave]]),
                                       "cuatro_arboles": metricas([f["cuatro_arboles"] for f in salida[clave]])}
    con.close()

    for clave, titulo in (("referencia", "18 CONSULTAS DE REFERENCIA"), ("nuevas", "CONSULTAS NUEVAS (equipamiento, nivel y patrón)")):
        print(f"\n{titulo}\n{'#':>2} {'consulta':36} {'vía (2 árboles)':20} {'vía (4 árboles)':22} destino (4 árboles)")
        for i, f in enumerate(salida[clave], 1):
            d, c = f["dos_arboles"], f["cuatro_arboles"]
            marca = "*" if f["cambia"] else " "
            print(f"{i:>2}{marca}{f['consulta'][:36]:36} {d['via']:20} {c['via']:22} {c['destino'] or '-'}  [{', '.join(c['arboles'])}]")
        print("   métricas:", json.dumps(salida[f"metricas_{clave}"], ensure_ascii=False))
    print("\nARISTAS POR PAR DE ÁRBOLES")
    for p in salida["pares"]:
        print(f"  {p['par']:30} {p['aristas']:>4} aristas  {p['documentos']:>5} documentos ({p['ejercicios']} ejercicios, {p['articulos']} artículos)")
    if args.guardar:
        ruta = args.guardar if os.path.isabs(args.guardar) else os.path.join(RAIZ, args.guardar)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=1)
        print("guardado en", ruta)


if __name__ == "__main__":
    main()
