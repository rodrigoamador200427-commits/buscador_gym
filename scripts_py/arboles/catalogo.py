"""Catálogo para los menús A+B: qué hay en cada árbol y qué artículos unen cada par.

Menú A = músculos (árbol de Anatomía). Menú B = temas (árbol de Temas).
`puentes["gid|Tema"]` = ids de los artículos que conectan ambos nodos (el "World War Z").
"""
from .recorridos import preorden


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
