"""Pruebas del paquete `arboles`.

Ejecutar desde scripts_py:   python -m pytest tests -v
Las pruebas con datos reales leen los CSV indicados en las variables de entorno
CSV_EJERCICIOS y CSV_ARTICULOS; si no existen, se omiten.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arboles import (Arbol, acumular_posorden, construir_aristas, construir_arbol_anatomia,
                     construir_arbol_temas, inorden, mejor_camino, por_niveles, posorden, preorden)
from arboles.fuentes import articulos_desde_csv, ejercicios_desde_csv
from arboles.taxonomia import nombre_equipamiento, temas_del_articulo


def nombres(it):
    return [n.nombre for n in it]


@pytest.fixture
def pequeno():
    """        A
             /   \\
            B     C
           / \\     \\
          D   E     F
    """
    t = Arbol("t", "A")
    b = t.agregar("B", t.raiz)
    c = t.agregar("C", t.raiz)
    t.agregar("D", b)
    t.agregar("E", b)
    t.agregar("F", c)
    return t


# --- estructura -------------------------------------------------------------
def test_terminologia(pequeno):
    t = pequeno
    d = t.buscar("D")[0]
    assert t.raiz.es_raiz and not t.raiz.es_hoja
    assert d.es_hoja and d.nivel == 2 and d.padre.nombre == "B"
    assert t.raiz.altura() == 2 and t.raiz.tamano() == 6
    assert d.ruta_texto() == "A > B > D"
    assert len(t) == 6


def test_buscar_ignora_acentos_y_mayusculas():
    t = Arbol("t", "Raíz")
    t.agregar("Bíceps", t.raiz)
    assert t.buscar("biceps") and t.buscar("BÍCEPS")


# --- recorridos (orden exacto) -----------------------------------------------
def test_preorden(pequeno):
    assert nombres(preorden(pequeno.raiz)) == list("ABDECF")


def test_posorden(pequeno):
    assert nombres(posorden(pequeno.raiz)) == list("DEBFCA")


def test_inorden_generalizado(pequeno):
    # Regla: subárbol del 1.er hijo, nodo, subárboles de los demás hijos.
    # C solo tiene un hijo (F), así que C se visita después de F.
    assert nombres(inorden(pequeno.raiz)) == list("DBEAFC")


def test_por_niveles(pequeno):
    assert nombres(por_niveles(pequeno.raiz)) == list("ABCDEF")


# --- acumulación en posorden -------------------------------------------------
def test_acumular_y_mejor_camino(pequeno):
    t = pequeno
    valores = {"D": 1.0, "E": 4.0, "F": 2.0}
    acum = acumular_posorden(t.raiz, lambda n: valores.get(n.nombre, 0.0))
    por_nombre = {t.nodo(i).nombre: v for i, v in acum.items()}
    assert por_nombre == {"D": 1.0, "E": 4.0, "B": 5.0, "F": 2.0, "C": 2.0, "A": 7.0}
    assert nombres(mejor_camino(t.raiz, acum)) == ["A", "B", "E"]


def test_mejor_camino_sin_valor_se_queda_en_la_raiz(pequeno):
    acum = acumular_posorden(pequeno.raiz, lambda n: 0.0)
    assert nombres(mejor_camino(pequeno.raiz, acum)) == ["A"]


def test_determinismo_de_recorridos(pequeno):
    assert nombres(preorden(pequeno.raiz)) == nombres(preorden(pequeno.raiz))


# --- taxonomía ---------------------------------------------------------------
def test_equipamiento_vacio_o_nan():
    assert nombre_equipamiento(None) == "Sin especificar"
    assert nombre_equipamiento(float("nan")) == "Sin especificar"
    assert nombre_equipamiento("Dumbbell") == "Mancuernas"


def test_tema_por_etiquetas_y_regla_de_respaldo():
    assert temas_del_articulo(["hipertrofia", "volumen", "fuerza"])[0] == "Hipertrofia"
    assert temas_del_articulo(["gluteo", "dorsal"]) == ["Técnica y biomecánica"]  # respaldo
    assert temas_del_articulo(["zzz"]) == []


# --- datos mínimos propios (sin CSV) ----------------------------------------
def test_constructores_con_filas_minimas():
    ej = [
        {"id": 7, "nombre_es": "Press de banca", "grupo_id": 1, "equipamiento": "Barbell",
         "modalidad": "Strength", "nivel": "Beginner"},
        {"id": 3, "nombre_es": "Flexiones", "grupo_id": 1, "equipamiento": None,
         "modalidad": "Strength", "nivel": "Beginner"},
        {"id": 9, "nombre_es": "Fantasma", "grupo_id": 99, "equipamiento": "Barbell",
         "modalidad": "Strength", "nivel": "Beginner"},
    ]
    A = construir_arbol_anatomia(ej)
    assert A.meta["descartados"] == [9]
    assert A.doc_a_nodo[("ejercicios", 7)].ruta_texto() == \
        "Cuerpo humano > Tren superior > Pecho > Barra > Press de banca"
    assert A.doc_a_nodo[("ejercicios", 3)].padre.nombre == "Sin especificar"

    arts = [{"id": 1, "titulo": "Agarre en press banca", "etiquetas": "press banca, pecho, fuerza, tecnica"}]
    T = construir_arbol_temas(arts)
    E = construir_aristas(arts, A, T)
    pecho = A.meta["musculos"][1]
    tema_fuerza = T.meta["temas"]["Fuerza"]
    assert E.peso(pecho.id, tema_fuerza.id) == 1
    assert E.vecinos_de_musculo(pecho.id, min_soporte=1)[0][:2] == (tema_fuerza.id, 1)


def test_lift_no_favorece_al_tema_mas_grande():
    """Con conteo bruto gana el tema grande; con lift gana la asociación específica."""
    from arboles.enlaces import Aristas
    E = Aristas()
    # músculo 1: 4 artículos con tema 10 (tema muy popular) y 2 con tema 20
    for d in (1, 2, 3, 4):
        E.agregar(1, 10, d)
    for d in (5, 6):
        E.agregar(1, 20, d)
    # músculo 2 usa casi solo el tema 10; el tema 20 es exclusivo de músculo 1
    for d in (7, 8, 9, 10, 11, 12):
        E.agregar(2, 10, d)
    assert E.vecinos_de_musculo(1, medida="peso")[0][0] == 10
    assert E.vecinos_de_musculo(1, medida="lift")[0][0] == 20
    assert E.vecinos_de_musculo(1, min_soporte=3)[0][0] == 10   # soporte filtra el tema con 2


# --- datos reales (se omiten si no hay CSV) ---------------------------------
CSV_E, CSV_A = os.environ.get("CSV_EJERCICIOS"), os.environ.get("CSV_ARTICULOS")
reales = pytest.mark.skipif(not (CSV_E and CSV_A and os.path.exists(CSV_E) and os.path.exists(CSV_A)),
                            reason="define CSV_EJERCICIOS y CSV_ARTICULOS")


@pytest.fixture(scope="module")
def datos():
    ej, ar = ejercicios_desde_csv(CSV_E), articulos_desde_csv(CSV_A)
    A, T = construir_arbol_anatomia(ej), construir_arbol_temas(ar)
    return ej, ar, A, T, construir_aristas(ar, A, T)


@reales
def test_cada_documento_aparece_una_sola_vez(datos):
    ej, ar, A, T, _ = datos
    assert len(A.doc_a_nodo) == len(ej) and not A.meta["descartados"]
    assert len(T.doc_a_nodo) == len(ar)
    hojas_a = [n for n in A.todos() if n.es_hoja and "doc_id" in n.payload]
    assert len(hojas_a) == len(ej)


@reales
def test_forma_del_arbol_de_anatomia(datos):
    _, _, A, _, _ = datos
    assert A.raiz.altura() == 4
    assert [h.nombre for h in A.raiz.hijos] == ["Tren superior", "Tren inferior", "Core"]
    assert len(A.meta["musculos"]) == 11


@reales
def test_interseccion_musculo_equipo(datos):
    """'pecho + mancuernas' es UN nodo del árbol de anatomía."""
    _, _, A, _, _ = datos
    nodo = [n for n in A.buscar("Mancuernas") if n.padre.nombre == "Pecho"]
    assert len(nodo) == 1 and nodo[0].tamano() > 1


@reales
def test_casi_todos_los_articulos_quedan_clasificados(datos):
    _, ar, _, T, _ = datos
    sc = T.meta["sin_clasificar"]
    assert (0 if sc is None else len(sc.hijos)) / len(ar) < 0.05


@reales
def test_hay_aristas_cruzadas_y_son_deterministas(datos):
    ej, ar, A, T, E = datos
    assert E.total() > 20
    E2 = construir_aristas(ar, construir_arbol_anatomia(ej), construir_arbol_temas(ar))
    pecho = A.meta["musculos"][1].id
    assert E.vecinos_de_musculo(pecho) == E2.vecinos_de_musculo(pecho)
