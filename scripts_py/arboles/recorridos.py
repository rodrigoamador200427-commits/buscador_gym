"""Recorridos del árbol (recursivos) y acumulación de relevancia.

- preorden : raíz, luego hijos      -> pintar el menú / listar la jerarquía
- inorden  : primer hijo, raíz, resto de hijos (generalización n-aria del inorden binario)
- posorden : hijos, luego raíz      -> ACUMULAR valores de abajo hacia arriba
- por_niveles (BFS)                 -> mostrar nivel por nivel
"""
from collections import deque


def preorden(nodo):
    yield nodo
    for hijo in nodo.hijos:
        yield from preorden(hijo)


def inorden(nodo):
    if nodo.es_hoja:
        yield nodo
        return
    yield from inorden(nodo.hijos[0])
    yield nodo
    for hijo in nodo.hijos[1:]:
        yield from inorden(hijo)


def posorden(nodo):
    for hijo in nodo.hijos:
        yield from posorden(hijo)
    yield nodo


def por_niveles(raiz):
    cola = deque([raiz])
    while cola:
        nodo = cola.popleft()
        yield nodo
        cola.extend(nodo.hijos)


def acumular_posorden(raiz, valor_hoja):
    """Suma de valor_hoja(hoja) de todo el subárbol de cada nodo.

    valor_hoja: función Nodo(hoja) -> número (p. ej. el score TF-IDF del documento
    de esa hoja, 0 si no fue recuperado). Devuelve {id_nodo: acumulado}.
    """
    acumulado = {}

    def visitar(nodo):
        total = valor_hoja(nodo) if nodo.es_hoja else sum(visitar(h) for h in nodo.hijos)
        acumulado[nodo.id] = total
        return total

    visitar(raiz)
    return acumulado


def mejor_camino(raiz, acumulado):
    """Desde la raíz baja siempre por el hijo de mayor acumulado (desempate: el primero).
    Se detiene en una hoja o cuando ya no hay valor positivo."""
    camino = [raiz]
    nodo = raiz
    while nodo.hijos:
        mejor = max(nodo.hijos, key=lambda h: acumulado.get(h.id, 0))
        if acumulado.get(mejor.id, 0) <= 0:
            break
        camino.append(mejor)
        nodo = mejor
    return camino
