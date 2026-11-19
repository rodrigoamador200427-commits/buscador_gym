"""Catálogo para los menús A+B: qué hay en cada árbol y qué artículos unen cada par.

Menú A = músculos (árbol de Anatomía). Menú B = temas (árbol de Temas).
`puentes["gid|Tema"]` = ids de los artículos que conectan ambos nodos (el "World War Z").
"""
from .recorridos import preorden
from .taxonomia import TITULO_ARBOL


def catalogo(anatomia, temas, aristas):
    musculos, tm = anatomia.meta["musculos"], temas.meta["temas"]
    por_id_m = {n.id: g for g, n in musculos.items()}
    por_id_t = {n.id: nombre for nombre, n in tm.items()}

    lista_m = [{"gid": g, "nombre": n.nombre, "region": n.padre.nombre if n.padre else "",
                "n_ejercicios": sum(1 for x in preorden(n) if x.es_hoja and "doc_id" in x.payload),
                "n_articulos": aristas.n_docs_musculo(n.id)}
               for g, n in sorted(musculos.items())]
    lista_t = [{"nombre": nombre, "rama": n.padre.nombre if n.padre else "",
                "n_articulos": aristas.n_docs_tema(n.id)}
               for nombre, n in sorted(tm.items(), key=lambda kv: (kv[1].padre.nombre, kv[0]))]
    puentes = {f"{por_id_m[m]}|{por_id_t[t]}": docs for (m, t), docs in aristas.items()}
    return {"musculos": lista_m, "temas": lista_t, "puentes": puentes}


# ------------------------------------------------------------------ N árboles (fase 6B)
def _conteo(bosque, nodo):
    docs = bosque.docs_de_nodo(nodo)
    ej = sum(1 for d in docs if d[0] == "ejercicios")
    return [ej, len(docs) - ej]


def catalogo_general(bosque):
    """Catálogo para los menús de dos árboles cualesquiera.

    {"arboles": [{"id", "titulo", "conceptos": [{"clave", "nombre", "grupo", "ruta", "n": [ejercicios, artículos]}]}],
     "pares": {"anatomia|temas": {"1|Fuerza": [ejercicios, artículos], ...}}}
    Solo salen las combinaciones que tienen documentos (las demás no se inventan). `n` cuenta los
    documentos del nodo; en `pares`, los documentos que pertenecen a los dos nodos.
    """
    arboles = []
    for nombre in bosque.nombres:
        arbol = bosque.arbol(nombre)
        conceptos = []
        for clave, nodo in bosque.conceptos(nombre).items():
            conceptos.append({"clave": str(clave), "nombre": nodo.nombre,
                              "grupo": nodo.padre.nombre if nodo.padre and nodo.padre is not arbol.raiz else "",
                              "ruta": [n.nombre for n in nodo.ruta()], "n": _conteo(bosque, nodo)})
        arboles.append({"id": nombre, "titulo": TITULO_ARBOL[nombre], "conceptos": conceptos})

    claves = {nombre: {n.id: str(c) for c, n in bosque.conceptos(nombre).items()} for nombre in bosque.nombres}
    pares = {}
    for (a, b), par in bosque.pares():
        filas = {}
        for (ia, ib), docs in par.items():
            ej = sum(1 for d in docs if d[0] == "ejercicios")
            filas[f"{claves[a][ia]}|{claves[b][ib]}"] = [ej, len(docs) - ej]
        pares[f"{a}|{b}"] = filas
    return {"arboles": arboles, "pares": pares}


def docs_del_cruce(bosque, arbol_a, clave_a, arbol_b, clave_b):
    """Documentos (origen, doc_id) que pertenecen a los dos nodos, o None si algún dato no existe.
    Artículos primero y luego ejercicios, cada grupo por id. Valida contra el catálogo: lo que no
    sea un árbol o un concepto reales devuelve None (no se interpreta nada)."""
    if arbol_a == arbol_b or arbol_a not in bosque.arboles or arbol_b not in bosque.arboles:
        return None
    nodos = []
    for arbol, clave in ((arbol_a, clave_a), (arbol_b, clave_b)):
        por_clave = {str(c): n for c, n in bosque.conceptos(arbol).items()}
        if str(clave) not in por_clave:
            return None
        nodos.append(por_clave[str(clave)])
    docs = bosque.docs_de_nodo(nodos[0]) & bosque.docs_de_nodo(nodos[1])
    return nodos, sorted(docs, key=lambda d: (0 if d[0] == "articulos" else 1, d[1]))
