"""Varios árboles y las aristas entre CUALQUIER par de ellos (fase 6B).

Un DOCUMENTO (ejercicio o artículo) pertenece a uno o más nodos-concepto de cada árbol:

  árbol         ejercicios                       artículos
  anatomía      músculo (grupo_id)               músculos de sus etiquetas
  temas         (ninguno)                        temas de sus etiquetas
  equipamiento  columna `equipamiento`           equipamientos de sus etiquetas
  nivel         columna `nivel`                  niveles de sus etiquetas

Una ARISTA entre el nodo x del árbol X y el nodo y del árbol Y existe si algún documento
pertenece a los dos. Se derivan de los datos (nada se teclea), se guardan en memoria, uno
por par de árboles, y se miden como en la fase 1: peso = nº de documentos y lift = cuánto más
se asocian que por azar (N = documentos con alguna arista en ese par).

Como los ejercicios no pertenecen a Temas, el par anatomía-temas sale solo de artículos y es
idéntico al de la fase 1 (hay una prueba que lo exige).

Un documento se identifica por (origen, doc_id). Todo es determinista: las listas van ordenadas
y los empates se resuelven por el orden fijo de taxonomia.ORDEN_ARBOLES.
"""
from collections import defaultdict
from itertools import combinations

from .constructor import (construir_arbol_anatomia, construir_arbol_equipamiento,
                          construir_arbol_nivel, construir_arbol_temas)
from .taxonomia import (ORDEN_ARBOLES, equipamientos_de_etiquetas, musculos_de_etiquetas,
                        nombre_equipamiento, niveles_de_etiquetas, NIVELES, separar_etiquetas,
                        temas_del_articulo)


class AristasPar:
    """Aristas entre dos árboles. Los nodos se identifican por su id dentro de cada árbol.
    `a` es el árbol de mayor prioridad (el que va antes en ORDEN_ARBOLES)."""

    def __init__(self, arbol_a, arbol_b):
        self.arbol_a, self.arbol_b = arbol_a, arbol_b
        self._docs = defaultdict(set)            # (id_a, id_b) -> {(origen, doc_id)}
        self._vecinos_a = defaultdict(set)       # id_a -> {id_b}
        self._vecinos_b = defaultdict(set)
        self._docs_a = defaultdict(set)          # id_a -> {doc}
        self._docs_b = defaultdict(set)
        self._todos = set()

    def agregar(self, id_a, id_b, doc):
        self._docs[(id_a, id_b)].add(doc)
        self._vecinos_a[id_a].add(id_b)
        self._vecinos_b[id_b].add(id_a)
        self._docs_a[id_a].add(doc)
        self._docs_b[id_b].add(doc)
        self._todos.add(doc)

    # --- consultas -------------------------------------------------------
    def peso(self, id_a, id_b):
        return len(self._docs.get((id_a, id_b), ()))

    def docs(self, id_a, id_b):
        return sorted(self._docs.get((id_a, id_b), ()))

    def items(self):
        """[((id_a, id_b), [doc])] ordenado (determinista)."""
        return sorted((k, sorted(v)) for k, v in self._docs.items())

    def total(self):
        return len(self._docs)

    def n_docs(self, lado, id_nodo, origen=None):
        """Documentos con alguna arista en este par y que pertenecen al nodo (lado 'a' o 'b')."""
        docs = (self._docs_a if lado == "a" else self._docs_b).get(id_nodo, ())
        return sum(1 for d in docs if origen is None or d[0] == origen)

    def lift(self, id_a, id_b):
        c = self.peso(id_a, id_b)
        if not c:
            return 0.0
        return c * len(self._todos) / (len(self._docs_a[id_a]) * len(self._docs_b[id_b]))

    def vecinos(self, lado, id_nodo, medida="lift", min_soporte=2):
        """[(id_otro, peso, lift)] del nodo en `lado` ('a'|'b'), ordenado por `medida`
        ('lift' | 'peso') y luego por id: determinista."""
        if lado == "a":
            filas = [(b, self.peso(id_nodo, b), self.lift(id_nodo, b)) for b in self._vecinos_a.get(id_nodo, ())]
        else:
            filas = [(a, self.peso(a, id_nodo), self.lift(a, id_nodo)) for a in self._vecinos_b.get(id_nodo, ())]
        filas = [f for f in filas if f[1] >= min_soporte]
        clave = (lambda f: (-f[2], -f[1], f[0])) if medida == "lift" else (lambda f: (-f[1], -f[2], f[0]))
        return sorted(filas, key=clave)


# ----------------------------------------------------------------- pertenencia
def _pertenencia_anatomia(arbol, ejercicios, articulos):
    musculos, docs = arbol.meta["musculos"], {}
    for e in ejercicios:
        gid = e.get("grupo_id")
        if gid is not None and int(gid) in musculos:
            docs[("ejercicios", int(e["id"]))] = [musculos[int(gid)].id]
    for a in articulos:
        ids = [musculos[g].id for g in musculos_de_etiquetas(separar_etiquetas(a["etiquetas"]))]
        if ids:
            docs[("articulos", int(a["id"]))] = ids
    return docs


def _pertenencia_temas(arbol, ejercicios, articulos):
    temas, docs = arbol.meta["temas"], {}
    for a in articulos:
        candidatos = temas_del_articulo(separar_etiquetas(a["etiquetas"]))
        if candidatos:
            docs[("articulos", int(a["id"]))] = [temas[t].id for t in candidatos]
    return docs


def _pertenencia_equipamiento(arbol, ejercicios, articulos):
    equipos, docs = arbol.meta["equipamientos"], {}
    for e in ejercicios:
        docs[("ejercicios", int(e["id"]))] = [equipos[nombre_equipamiento(e.get("equipamiento"))].id]
    for a in articulos:
        ids = [equipos[n].id for n in equipamientos_de_etiquetas(separar_etiquetas(a["etiquetas"]))
               if n in equipos]
        if ids:
            docs[("articulos", int(a["id"]))] = ids
    return docs


def _pertenencia_nivel(arbol, ejercicios, articulos):
    niveles, docs = arbol.meta["niveles"], {}
    for e in ejercicios:
        valor = e.get("nivel")
        nombre = NIVELES.get(valor.strip()) if isinstance(valor, str) else None
        nodo = niveles.get(nombre) if nombre else arbol.meta["sin_nivel"]
        if nodo is not None:
            docs[("ejercicios", int(e["id"]))] = [nodo.id]
    for a in articulos:
        ids = [niveles[n].id for n in niveles_de_etiquetas(separar_etiquetas(a["etiquetas"]))]
        if ids:
            docs[("articulos", int(a["id"]))] = ids
    return docs


_CONSTRUCTORES = {
    "anatomia": (lambda ej, ar: construir_arbol_anatomia(ej), _pertenencia_anatomia),
    "temas": (lambda ej, ar: construir_arbol_temas(ar), _pertenencia_temas),
    "equipamiento": (lambda ej, ar: construir_arbol_equipamiento(ej), _pertenencia_equipamiento),
    "nivel": (lambda ej, ar: construir_arbol_nivel(ej), _pertenencia_nivel),
}


class Bosque:
    """Árboles (en el orden de ORDEN_ARBOLES), pertenencia de documentos y aristas por par."""

    def __init__(self, arboles, pertenencia):
        """arboles: {nombre: Arbol}; pertenencia: {nombre: {(origen, doc_id): [id_nodo]}}."""
        self.arboles = {n: arboles[n] for n in ORDEN_ARBOLES if n in arboles}
        self.pertenencia = pertenencia
        self._docs_de_nodo = {}                       # (arbol, id_nodo) -> {doc}
        for nombre, docs in pertenencia.items():
            for doc, ids in docs.items():
                for i in ids:
                    self._docs_de_nodo.setdefault((nombre, i), set()).add(doc)
        self._pares = {}
        for a, b in combinations(self.nombres, 2):    # a siempre va antes que b en la prioridad
            par = AristasPar(a, b)
            pb = pertenencia.get(b, {})
            for doc, ids_a in sorted(pertenencia.get(a, {}).items()):
                for ib in pb.get(doc, ()):
                    for ia in ids_a:
                        par.agregar(ia, ib, doc)
            self._pares[(a, b)] = par

    @classmethod
    def construir(cls, ejercicios, articulos, nombres=ORDEN_ARBOLES):
        arboles, pertenencia = {}, {}
        for nombre in nombres:
            construir, derivar = _CONSTRUCTORES[nombre]
            arboles[nombre] = construir(ejercicios, articulos)
            pertenencia[nombre] = derivar(arboles[nombre], ejercicios, articulos)
        return cls(arboles, pertenencia)

    @classmethod
    def desde_aristas_clasicas(cls, anatomia, temas, aristas):
        """Envuelve los dos árboles y las `Aristas` de la fase 1 (músculo x tema, solo artículos)."""
        pa, pt = defaultdict(set), defaultdict(set)
        for (m, t), docs in aristas.items():
            for d in docs:
                pa[("articulos", d)].add(m)
                pt[("articulos", d)].add(t)
        return cls({"anatomia": anatomia, "temas": temas},
                   {"anatomia": {k: sorted(v) for k, v in pa.items()},
                    "temas": {k: sorted(v) for k, v in pt.items()}})

    # --- acceso ----------------------------------------------------------
    @property
    def nombres(self):
        return list(self.arboles)

    def arbol(self, nombre):
        return self.arboles[nombre]

    def conceptos(self, nombre):
        """{clave: Nodo} de lo que se puede nombrar en ese árbol."""
        return self.arboles[nombre].meta["conceptos"]

    def par(self, x, y):
        """AristasPar de dos árboles distintos, sea cual sea el orden en que se pidan."""
        return self._pares[(x, y) if (x, y) in self._pares else (y, x)]

    def pares(self):
        return [(k, self._pares[k]) for k in sorted(self._pares, key=lambda k: (self.nombres.index(k[0]),
                                                                                 self.nombres.index(k[1])))]

    def docs_de_nodo(self, nodo):
        """Conjunto de documentos (origen, doc_id) que pertenecen al nodo-concepto."""
        return self._docs_de_nodo.get((nodo.arbol, nodo.id), set())

    def n_articulos(self, nodo):
        return sum(1 for d in self.docs_de_nodo(nodo) if d[0] == "articulos")
