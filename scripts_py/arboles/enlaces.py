"""Aristas cruzadas entre árboles (lo que convierte dos árboles en un grafo).

Una arista une un nodo-MÚSCULO del árbol de anatomía con un nodo-TEMA del árbol de
temas cuando existe al menos un artículo cuyas etiquetas mencionan ambos. Los enlaces
se DERIVAN de los datos, no se teclean.

Dos medidas por arista:
  - peso : nº de artículos puente (conteo bruto).
  - lift : cuánto más se asocian músculo y tema que por azar.
           lift = (docs con m y t) * N / (docs con m * docs con t), N = artículos puente.
           lift > 1  => asociación real; lift ~ 1 => ruido.
Se ordena por LIFT porque el conteo bruto favorece siempre al tema más grande
(p. ej. 'Técnica y biomecánica' sería el vecino de todos los músculos).
"""
from collections import defaultdict

from .taxonomia import musculos_de_etiquetas, separar_etiquetas, temas_del_articulo


class Aristas:
    def __init__(self):
        self._docs = defaultdict(list)          # (id_musculo, id_tema) -> [doc_id]
        self._por_musculo = defaultdict(set)
        self._por_tema = defaultdict(set)
        self._docs_musculo = defaultdict(set)   # id_musculo -> {doc_id}
        self._docs_tema = defaultdict(set)      # id_tema -> {doc_id}
        self._todos = set()

    def agregar(self, id_musculo, id_tema, doc_id):
        self._docs[(id_musculo, id_tema)].append(doc_id)
        self._por_musculo[id_musculo].add(id_tema)
        self._por_tema[id_tema].add(id_musculo)
        self._docs_musculo[id_musculo].add(doc_id)
        self._docs_tema[id_tema].add(doc_id)
        self._todos.add(doc_id)

    def peso(self, id_musculo, id_tema):
        return len(self._docs.get((id_musculo, id_tema), []))

    def docs(self, id_musculo, id_tema):
        return list(self._docs.get((id_musculo, id_tema), []))

    def total(self):
        return len(self._docs)

    def n_docs_musculo(self, id_musculo):
        return len(self._docs_musculo.get(id_musculo, ()))

    def n_docs_tema(self, id_tema):
        return len(self._docs_tema.get(id_tema, ()))

    def lift(self, id_musculo, id_tema):
        c_mt = self.peso(id_musculo, id_tema)
        if not c_mt:
            return 0.0
        n = len(self._todos)
        return c_mt * n / (len(self._docs_musculo[id_musculo]) * len(self._docs_tema[id_tema]))

    def _ordenar(self, pares, medida, min_soporte):
        filas = [(otro, peso, lift) for otro, peso, lift in pares if peso >= min_soporte]
        clave = (lambda f: (-f[2], -f[1], f[0])) if medida == "lift" else (lambda f: (-f[1], -f[2], f[0]))
        return sorted(filas, key=clave)

    def vecinos_de_musculo(self, id_musculo, medida="lift", min_soporte=2):
        """[(id_tema, peso, lift)] ordenado por `medida` ('lift' | 'peso'); determinista."""
        pares = [(t, self.peso(id_musculo, t), self.lift(id_musculo, t))
                 for t in self._por_musculo.get(id_musculo, ())]
        return self._ordenar(pares, medida, min_soporte)

    def vecinos_de_tema(self, id_tema, medida="lift", min_soporte=2):
        """[(id_musculo, peso, lift)] ordenado por `medida`; determinista."""
        pares = [(m, self.peso(m, id_tema), self.lift(m, id_tema))
                 for m in self._por_tema.get(id_tema, ())]
        return self._ordenar(pares, medida, min_soporte)


def construir_aristas(articulos, arbol_anatomia, arbol_temas):
    aristas = Aristas()
    musculos = arbol_anatomia.meta["musculos"]
    temas = arbol_temas.meta["temas"]
    for fila in articulos:
        etiquetas = separar_etiquetas(fila["etiquetas"])
        for gid in musculos_de_etiquetas(etiquetas):
            for tema in temas_del_articulo(etiquetas):
                aristas.agregar(musculos[gid].id, temas[tema].id, int(fila["id"]))
    return aristas
