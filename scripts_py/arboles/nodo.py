"""Estructura de datos del árbol: Nodo y Arbol.

Terminología (para el reporte): raíz = nodo sin padre; hoja = nodo sin hijos;
nivel = distancia a la raíz; altura = camino más largo hacia una hoja;
arista = enlace padre→hijo. Las operaciones son recursivas a propósito.
"""
from .taxonomia import normalizar


class Nodo:
    __slots__ = ("id", "nombre", "arbol", "padre", "hijos", "payload")

    def __init__(self, id, nombre, arbol, padre=None, payload=None):
        self.id = id
        self.nombre = nombre
        self.arbol = arbol          # nombre del árbol al que pertenece
        self.padre = padre
        self.hijos = []
        self.payload = payload or {}

    # --- propiedades estructurales -------------------------------------
    @property
    def es_raiz(self):
        return self.padre is None

    @property
    def es_hoja(self):
        return not self.hijos

    @property
    def nivel(self):
        return 0 if self.padre is None else self.padre.nivel + 1

    def altura(self):
        return 0 if self.es_hoja else 1 + max(h.altura() for h in self.hijos)

    def tamano(self):
        """Número de nodos del subárbol (incluido este)."""
        return 1 + sum(h.tamano() for h in self.hijos)

    def ruta(self):
        """Lista de nodos desde la raíz hasta este."""
        return [self] if self.padre is None else self.padre.ruta() + [self]

    def ruta_texto(self, sep=" > "):
        return sep.join(n.nombre for n in self.ruta())

    def __repr__(self):
        return f"Nodo({self.id}, {self.nombre!r}, nivel={self.nivel})"


class Arbol:
    def __init__(self, nombre, nombre_raiz):
        self.nombre = nombre
        self._nodos = {}
        self._siguiente = 1
        self.meta = {}              # referencias útiles (p. ej. músculos por grupo_id)
        self.doc_a_nodo = {}        # (origen, doc_id) -> nodo hoja
        self.raiz = self._crear(nombre_raiz, None, None)

    def _crear(self, nombre, padre, payload):
        nodo = Nodo(self._siguiente, nombre, self.nombre, padre, payload)
        self._nodos[nodo.id] = nodo
        self._siguiente += 1
        return nodo

    def agregar(self, nombre, padre, payload=None):
        nodo = self._crear(nombre, padre, payload)
        padre.hijos.append(nodo)
        return nodo

    def nodo(self, id):
        return self._nodos[id]

    def todos(self):
        return list(self._nodos.values())

    def buscar(self, nombre, nivel=None):
        """Nodos cuyo nombre coincide sin acentos/mayúsculas (y opcionalmente nivel)."""
        clave = normalizar(nombre)
        return [n for n in self._nodos.values()
                if normalizar(n.nombre) == clave and (nivel is None or n.nivel == nivel)]

    def ordenar_hijos(self, nodo, clave=None):
        nodo.hijos.sort(key=clave or (lambda n: normalizar(n.nombre)))

    def __len__(self):
        return len(self._nodos)
