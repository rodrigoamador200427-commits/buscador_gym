"""Pruebas de la fase 6B: árboles de Equipamiento y Nivel, aristas entre cualquier par de árboles y
motor con N árboles.

    python -m pytest tests -v        (desde scripts_py)
Las de datos reales usan CSV_EJERCICIOS y CSV_ARTICULOS; si no están, se omiten.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arboles import (Bosque, MotorArboles, acumular_posorden, construir_aristas, construir_arbol_anatomia,
                     construir_arbol_equipamiento, construir_arbol_nivel, construir_arbol_temas,
                     por_niveles, posorden, preorden)
from arboles.consulta import raices_de
from arboles.fuentes import articulos_desde_csv, ejercicios_desde_csv
from arboles.taxonomia import (CATEGORIAS_EQUIPAMIENTO, NIVELES_ORDEN, SIN_EQUIPAMIENTO, TERMINO_A_EQUIPAMIENTO,
                               TERMINO_A_NIVEL, CONSULTA_EQUIPAMIENTO, EQUIPAMIENTO, TITULO_ARBOL)
from nltk.stem.snowball import SnowballStemmer

st = SnowballStemmer("spanish")
STOP = set("de del la el los las un una y a con en para por que como mi me quiero mas es lo al se su".split())


def raices(q):
    return raices_de(q, set(), st, STOP, {}, lambda w: w)


def ej(i, nombre, grupo, equipo, nivel):
    return {"id": i, "nombre_es": nombre, "grupo_id": grupo, "equipamiento": equipo,
            "modalidad": "Strength", "nivel": nivel}


EJERCICIOS = [
    ej(1, "Press con mancuernas", 1, "Dumbbell", "Beginner"),
    ej(2, "Aperturas con mancuernas", 1, "Dumbbell", "Intermediate"),
    ej(3, "Press con barra", 1, "Barbell", "Beginner"),
    ej(4, "Curl con barra", 4, "Barbell", "Beginner"),
    ej(5, "Sentadilla en máquina", 6, "Machine", "Expert"),
    ej(6, "Plancha", 10, "Body Only", None),            # sin nivel
    ej(7, "Remo", 2, "", "Beginner"),                    # sin equipamiento
    ej(8, "Extensión", 5, "Equipo raro", "Intermediate"),  # equipamiento que la taxonomía no conoce
]
ARTICULOS = [
    {"id": 10, "titulo": "Pecho para empezar", "etiquetas": "pecho, mancuerna, principiantes, fuerza"},
    {"id": 11, "titulo": "Pecho con mancuernas", "etiquetas": "pecho, mancuerna, hipertrofia"},
    {"id": 12, "titulo": "Curl con barra", "etiquetas": "biceps, barra, hipertrofia"},
    {"id": 13, "titulo": "Comer bien", "etiquetas": "dieta, proteina"},
    {"id": 14, "titulo": "Pecho sin material", "etiquetas": "pecho, principiantes, tecnica, banda elastica"},
    {"id": 15, "titulo": "Pesa rusa para empezar", "etiquetas": "kettlebell, principiantes, resistencia"},
    {"id": 16, "titulo": "Banco y paralelas", "etiquetas": "banco, paralelas, fuerza"},
]


@pytest.fixture(scope="module")
def bosque():
    return Bosque.construir(EJERCICIOS, ARTICULOS)


@pytest.fixture(scope="module")
def motor(bosque):
    return MotorArboles.desde_bosque(bosque, st.stem)


UNO_POR_EJERCICIO = lambda h: 1.0 if "doc_id" in h.payload else 0.0   # un equipamiento sin ejercicios también es hoja


# =============================================================== árbol de Equipamiento
def test_equipamiento_estructura_y_altura():
    A = construir_arbol_equipamiento(EJERCICIOS)
    assert A.raiz.nombre == "Equipamiento" and A.raiz.altura() == 3
    assert [c.nombre for c in A.raiz.hijos] == [c for c, _ in CATEGORIAS_EQUIPAMIENTO]
    # raíz, categorías, equipamientos y una hoja por ejercicio
    equipos = {n for _, l in CATEGORIAS_EQUIPAMIENTO for n in l}
    assert len(A) == 1 + len(CATEGORIAS_EQUIPAMIENTO) + len(equipos) + 1 + len(EJERCICIOS)   # +1: «Equipo raro»
    hojas = [n for n in A.todos() if n.es_hoja and "doc_id" in n.payload]
    assert len(hojas) == len(EJERCICIOS) and all(h.nivel == 3 for h in hojas)


def test_el_vocabulario_de_consulta_no_choca_con_el_de_otros_arboles():
    """Una palabra de equipamiento o nivel no puede tener la misma raíz que una que ya nombra un
    músculo o un tema («rodillo»/«rodilla», «correas»/«correr»): cambiaría consultas de la fase 1."""
    from arboles.taxonomia import (ALIAS_MUSCULO, CONSULTA_NIVEL, ETIQUETA_A_MUSCULO, SINONIMOS_TEMA, TEMAS, normalizar)

    def raices_de_frase(f):
        return frozenset(st.stem(p) for p in normalizar(f).split() if p)

    previos = [raices_de_frase(f) for f in list(ETIQUETA_A_MUSCULO) + list(ALIAS_MUSCULO)]
    previos += [raices_de_frase(t) for _, _, tags in TEMAS for t in tags]
    previos += [raices_de_frase(f) for fs in SINONIMOS_TEMA.values() for f in fs]
    nuevos = [(n, f) for vocab in (CONSULTA_EQUIPAMIENTO, CONSULTA_NIVEL) for n, fs in vocab.items() for f in fs]
    choques = [(n, f) for n, f in nuevos for p in previos if p and (p <= raices_de_frase(f) or raices_de_frase(f) <= p)]
    assert not choques, choques


def test_rodilla_y_correr_no_nombran_equipamiento(motor):
    assert "equipamiento" not in motor.descubrir(raices("dolor de rodilla sentadilla"))["traza"]["conceptos"]
    assert "equipamiento" not in motor.descubrir(raices("correr resistencia cardio"))["traza"]["conceptos"]
    assert motor.descubrir(raices("foam roller"))["traza"]["conceptos"] == {"equipamiento": ["Rodillo"]}


def test_equipamiento_nombres_salen_de_la_taxonomia():
    nombres = {n for _, l in CATEGORIAS_EQUIPAMIENTO for n in l}
    assert set(EQUIPAMIENTO.values()) <= nombres                                 # todo valor de la columna tiene nodo
    assert set(TERMINO_A_EQUIPAMIENTO.values()) <= nombres                       # y toda etiqueta de artículo
    assert set(CONSULTA_EQUIPAMIENTO) <= nombres
    assert "banco" not in {f for fs in CONSULTA_EQUIPAMIENTO.values() for f in fs}   # «banca» y «banco» comparten raíz


def test_equipamiento_ejercicios_y_casos_raros():
    A = construir_arbol_equipamiento(EJERCICIOS)
    e = A.meta["equipamientos"]
    assert [h.payload["doc_id"] for h in e["Mancuernas"].hijos] == [1, 2]
    assert [h.payload["doc_id"] for h in e["Barra"].hijos] == [3, 4]
    assert e["Banco"].hijos == [] and e["Paralelas"].hijos == []                  # solo los nombran artículos
    assert [h.payload["doc_id"] for h in e[SIN_EQUIPAMIENTO].hijos] == [7]
    assert e["Equipo raro"].padre.nombre == "Otros"                              # valor desconocido: no se pierde
    assert A.doc_a_nodo[("ejercicios", 4)].ruta_texto() == "Equipamiento > Pesas libres > Barra > Curl con barra"


def test_equipamiento_recorridos():
    A = construir_arbol_equipamiento(EJERCICIOS)
    pre = [n.nombre for n in preorden(A.raiz)]
    assert pre[0] == "Equipamiento" and pre[1] == "Pesas libres" and pre[2] == "Barra"
    assert [n.nombre for n in posorden(A.raiz)][-1] == "Equipamiento"
    niveles = [n.nivel for n in por_niveles(A.raiz)]
    assert niveles == sorted(niveles) and niveles[0] == 0 and max(niveles) == 3
    acum = acumular_posorden(A.raiz, UNO_POR_EJERCICIO)   # cada ejercicio vale 1 (los nodos vacíos, 0)
    assert acum[A.raiz.id] == len(EJERCICIOS) and acum[A.meta["equipamientos"]["Barra"].id] == 2


# ====================================================================== árbol de Nivel
def test_nivel_estructura_y_altura():
    N = construir_arbol_nivel(EJERCICIOS)
    assert N.raiz.altura() == 2
    assert [n.nombre for n in N.raiz.hijos] == NIVELES_ORDEN + [SIN_EQUIPAMIENTO]   # «Sin especificar» solo si hace falta
    n = N.meta["niveles"]
    assert [h.payload["doc_id"] for h in n["Principiante"].hijos] == [1, 3, 4, 7]
    assert [h.payload["doc_id"] for h in n["Intermedio"].hijos] == [2, 8]
    assert [h.payload["doc_id"] for h in n["Avanzado"].hijos] == [5]
    assert [h.payload["doc_id"] for h in N.meta["sin_nivel"].hijos] == [6]
    assert len([x for x in N.todos() if x.es_hoja and "doc_id" in x.payload]) == len(EJERCICIOS)


def test_nivel_siempre_tiene_los_tres_niveles_y_no_inventa_sin_nivel():
    N = construir_arbol_nivel([ej(1, "A", 1, "Barbell", "Beginner")])
    assert [n.nombre for n in N.raiz.hijos] == NIVELES_ORDEN and N.meta["sin_nivel"] is None
    assert N.meta["niveles"]["Avanzado"].hijos == []


def test_nivel_recorridos_y_ruta():
    N = construir_arbol_nivel(EJERCICIOS)
    assert N.doc_a_nodo[("ejercicios", 5)].ruta_texto() == "Nivel de experiencia > Avanzado > Sentadilla en máquina"
    assert [n.nombre for n in preorden(N.raiz)][:3] == ["Nivel de experiencia", "Principiante", "Press con mancuernas"]
    assert [n.nivel for n in por_niveles(N.raiz)] == sorted(n.nivel for n in N.todos())
    assert acumular_posorden(N.raiz, UNO_POR_EJERCICIO)[N.raiz.id] == len(EJERCICIOS)


# ======================================================== pertenencia y aristas por par
def test_los_articulos_se_enlazan_por_etiquetas(bosque):
    e, n = bosque.conceptos("equipamiento"), bosque.conceptos("nivel")
    assert bosque.docs_de_nodo(e["Mancuernas"]) == {("ejercicios", 1), ("ejercicios", 2), ("articulos", 10), ("articulos", 11)}
    assert ("articulos", 14) in bosque.docs_de_nodo(e["Bandas"])                  # «banda elastica» -> Bandas
    assert bosque.docs_de_nodo(e["Banco"]) == {("articulos", 16)}                 # solo artículos
    assert bosque.docs_de_nodo(n["Principiante"]) == {("ejercicios", 1), ("ejercicios", 3), ("ejercicios", 4), ("ejercicios", 7),
                                                      ("articulos", 10), ("articulos", 14), ("articulos", 15)}
    assert TERMINO_A_NIVEL["principiantes"] == "Principiante"


def test_hay_una_arista_por_cada_par_de_arboles(bosque):
    assert [k for k, _ in bosque.pares()] == [("anatomia", "temas"), ("anatomia", "equipamiento"), ("anatomia", "nivel"),
                                              ("temas", "equipamiento"), ("temas", "nivel"), ("equipamiento", "nivel")]
    assert all(p.total() > 0 for _, p in bosque.pares())
    assert bosque.par("nivel", "anatomia") is bosque.par("anatomia", "nivel")     # se pide en cualquier orden


def test_par_anatomia_temas_es_identico_al_de_la_fase_1(bosque):
    A, T = bosque.arbol("anatomia"), bosque.arbol("temas")
    clasicas = construir_aristas(ARTICULOS, A, T)
    nuevas = [(k, [d[1] for d in docs]) for k, docs in bosque.par("anatomia", "temas").items()]
    assert nuevas == [(k, docs) for k, docs in clasicas.items()]
    assert all(d[0] == "articulos" for _, docs in bosque.par("anatomia", "temas").items() for d in docs)
    for (m, t), _ in clasicas.items():
        assert abs(bosque.par("anatomia", "temas").lift(m, t) - clasicas.lift(m, t)) < 1e-12


def test_aristas_mezclan_ejercicios_y_articulos(bosque):
    par = bosque.par("anatomia", "equipamiento")
    pecho, mancuernas = bosque.conceptos("anatomia")[1], bosque.conceptos("equipamiento")["Mancuernas"]
    assert par.docs(pecho.id, mancuernas.id) == [("articulos", 10), ("articulos", 11), ("ejercicios", 1), ("ejercicios", 2)]
    assert par.peso(pecho.id, mancuernas.id) == 4 and par.lift(pecho.id, mancuernas.id) > 0
    # vecinos del lado «a» (anatomía): el de mayor lift primero; determinista
    v = par.vecinos("a", pecho.id, min_soporte=1)
    assert v == par.vecinos("a", pecho.id, min_soporte=1) and v[0][1] >= 1


# ====================================================================== consultas
def test_pecho_mancuernas_principiante_cruza_tres_arboles(motor):
    r = motor.descubrir(raices("pecho mancuernas principiante"))
    assert r["via"] == "interseccion"
    assert [n["arbol"] for n in r["nodos"]] == ["anatomia", "equipamiento", "nivel"]
    assert [n["nombre"] for n in r["nodos"]] == ["Pecho", "Mancuernas", "Principiante"]
    assert r["nodos"][1]["ruta"] == ["Equipamiento", "Pesas libres", "Mancuernas"]
    assert r["nodos"][2]["ruta"] == ["Nivel de experiencia", "Principiante"]
    assert [(d["origen"], d["doc_id"]) for d in r["documentos"]] == [("articulos", 10), ("ejercicios", 1)]
    assert r["origen"]["arbol"] == "anatomia" and r["destino"]["arbol"] == "equipamiento"
    assert r["traza"]["arboles_nombrados"] == ["anatomia", "equipamiento", "nivel"]


def test_musculo_y_equipamiento_dos_arboles(motor):
    r = motor.descubrir(raices("pecho mancuernas"))
    assert r["via"] == "interseccion" and len(r["nodos"]) == 2
    assert {(d["origen"], d["doc_id"]) for d in r["documentos"]} == {("articulos", 10), ("articulos", 11), ("ejercicios", 1)}


def test_equipamiento_y_nivel_sin_musculo(motor):
    r = motor.descubrir(raices("barra principiante"))
    assert r["via"] == "interseccion"
    assert [n["arbol"] for n in r["nodos"]] == ["equipamiento", "nivel"]
    assert {(d["origen"], d["doc_id"]) for d in r["documentos"]} == {("ejercicios", 3), ("ejercicios", 4)}


def test_par_sin_interseccion_no_inventa(motor):
    r = motor.descubrir(raices("pecho kettlebell"))
    assert r["via"] == "sin_interseccion" and r["documentos"] == []
    assert r["origen"] is None and [n["nombre"] for n in r["nodos"]] == ["Pecho", "Kettlebell"]
    assert "no inventa" in r["razon"] and "alternativa" in r


def test_tres_arboles_sin_interseccion_total_elige_el_mejor_par(bosque, motor):
    r = motor.descubrir(raices("pecho kettlebell principiante"))      # no hay documento con los tres
    assert r["via"] == "interseccion_parcial"
    usados, omitidos = r["traza"]["arboles_usados"], r["traza"]["arboles_omitidos"]
    assert len(usados) == 2 and len(omitidos) == 1 and set(usados) | set(omitidos) == {"anatomia", "equipamiento", "nivel"}
    assert [n["arbol"] for n in r["nodos"]] == usados and r["documentos"]
    # el par de mayor lift entre los que tienen documentos comunes, con soporte de 2 o más si lo hay
    mejores = {"anatomia": 1, "equipamiento": "Kettlebell", "nivel": "Principiante"}
    nodos = {a: bosque.conceptos(a)[c] for a, c in mejores.items()}
    esperado = None
    for minimo in (2, 1):        # primero los pares con al menos 2 documentos; si no hay, con 1
        candidatos = []
        for a, b in (("anatomia", "equipamiento"), ("anatomia", "nivel"), ("equipamiento", "nivel")):
            par = bosque.par(a, b)
            peso = par.peso(nodos[a].id, nodos[b].id)
            if peso >= minimo:
                candidatos.append((-par.lift(nodos[a].id, nodos[b].id), -peso, (a, b)))
        if candidatos:
            esperado = list(min(candidatos)[2])
            break
    assert usados == esperado == ["anatomia", "nivel"]     # equipamiento-nivel solo tiene 1 documento
    assert omitidos[0] in r["razon"].lower() or TITULO_ARBOL[omitidos[0]] in r["razon"]


def test_un_solo_concepto_conserva_la_fase_1(motor):
    r = motor.descubrir(raices("pecho"))
    assert r["via"] == "concepto" and r["destino"]["arbol"] == "temas"
    r = motor.descubrir(raices("fuerza"))
    assert r["via"] == "concepto" and r["destino"]["arbol"] == "anatomia" and r["destino"]["nombre"] == "Pecho"


def test_equipamiento_o_nivel_solos_saltan_a_anatomia(motor):
    for q, esperado in (("mancuernas", "Pecho"), ("principiantes", "Pecho")):
        r = motor.descubrir(raices(q))
        assert r["via"] == "concepto" and r["origen"]["arbol"] != "anatomia" and r["destino"]["arbol"] == "anatomia"
        assert r["destino"]["nombre"] == esperado


def test_press_de_banca_no_nombra_el_banco(motor):
    r = motor.descubrir(raices("press de banca con barra"))
    assert r["traza"]["conceptos"].get("equipamiento") == ["Barra"]


def test_musculo_y_tema_no_cambia_con_mas_arboles(bosque, motor):
    """La misma consulta da lo mismo con dos árboles que con cuatro (documentos aparte)."""
    A, T = bosque.arbol("anatomia"), bosque.arbol("temas")
    clasico = MotorArboles(A, T, construir_aristas(ARTICULOS, A, T), st.stem)
    for q in ("pecho fuerza", "pecho hipertrofia", "biceps hipertrofia", "ganar fuerza", "dieta"):
        a, b = clasico.descubrir(raices(q)), motor.descubrir(raices(q))
        assert (a["via"], a["origen"], a["destino"], a["documentos"], a["lift"]) == \
               (b["via"], b["origen"], b["destino"], b["documentos"], b["lift"]), q


def test_determinista_y_serializable(motor):
    for q in ("pecho mancuernas principiante", "pecho kettlebell principiante", "pecho kettlebell", "mancuernas", "zzz"):
        salidas = {json.dumps(motor.descubrir(raices(q)), sort_keys=True) for _ in range(10)}
        assert len(salidas) == 1


def test_recuperacion_sigue_usando_solo_anatomia_y_temas(motor):
    r = motor.descubrir(raices("zzz"), [("articulos", 12, 0.9), ("ejercicios", 4, 0.5)])
    assert r["via"] == "recuperacion" and r["origen"]["arbol"] in ("anatomia", "temas")


# ======================================================================== catálogo
def test_catalogo_general_arboles_conceptos_y_pares(bosque):
    from arboles.catalogo import catalogo_general
    c = catalogo_general(bosque)
    assert [a["id"] for a in c["arboles"]] == ["anatomia", "temas", "equipamiento", "nivel"]
    assert [a["titulo"] for a in c["arboles"]] == ["Anatomía", "Temas", "Equipamiento", "Nivel"]
    eq = next(a for a in c["arboles"] if a["id"] == "equipamiento")["conceptos"]
    mancuernas = next(x for x in eq if x["nombre"] == "Mancuernas")
    assert mancuernas["clave"] == "mancuernas" and mancuernas["grupo"] == "Pesas libres" and mancuernas["n"] == [2, 2]
    assert mancuernas["ruta"] == ["Equipamiento", "Pesas libres", "Mancuernas"]
    pecho = next(x for x in next(a for a in c["arboles"] if a["id"] == "anatomia")["conceptos"] if x["clave"] == "1")
    assert pecho["nombre"] == "Pecho" and pecho["grupo"] == "Tren superior"
    assert len(c["pares"]) == 6
    assert c["pares"]["anatomia|equipamiento"]["1|mancuernas"] == [2, 2]          # [ejercicios, artículos]
    assert c["pares"]["anatomia|temas"]["1|fuerza"] == [0, 1]                    # los ejercicios no entran en Temas
    assert "1|kettlebell" not in c["pares"]["anatomia|equipamiento"]              # sin documentos: no se inventa
    assert json.dumps(c)                                                          # serializable


def test_el_catalogo_clasico_sigue_igual(bosque):
    from arboles.catalogo import catalogo
    A, T = bosque.arbol("anatomia"), bosque.arbol("temas")
    c = catalogo(A, T, construir_aristas(ARTICULOS, A, T))
    assert c["puentes"]["1|Fuerza"] == [10]


def test_docs_del_cruce_valida_y_ordena(bosque):
    from arboles.catalogo import docs_del_cruce
    nodos, docs = docs_del_cruce(bosque, "anatomia", "1", "equipamiento", "mancuernas")
    assert [n.nombre for n in nodos] == ["Pecho", "Mancuernas"]
    assert docs == [("articulos", 10), ("articulos", 11), ("ejercicios", 1), ("ejercicios", 2)]   # artículos primero
    assert docs_del_cruce(bosque, "equipamiento", "mancuernas", "anatomia", "1")[1] == [("articulos", 10), ("articulos", 11), ("ejercicios", 1), ("ejercicios", 2)]
    for malo in (("anatomia", "1", "anatomia", "2"), ("anatomia", "99", "nivel", "principiante"),
                 ("anatomia", "1", "patron", "x"), ("anatomia", "1; DROP", "nivel", "principiante"), ("anatomia", "1", "equipamiento", "Mancuernas")):
        assert docs_del_cruce(bosque, *malo) is None
    assert docs_del_cruce(bosque, "anatomia", "1", "equipamiento", "kettlebell")[1] == []         # existe el cruce, sin documentos


# ============================================================= datos reales (opcionales)
CSV_E, CSV_A = os.environ.get("CSV_EJERCICIOS"), os.environ.get("CSV_ARTICULOS")
reales = pytest.mark.skipif(not (CSV_E and CSV_A and os.path.exists(CSV_E or "") and os.path.exists(CSV_A or "")),
                            reason="define CSV_EJERCICIOS y CSV_ARTICULOS")


@reales
def test_real_equipamiento_y_nivel():
    e = ejercicios_desde_csv(CSV_E)
    A, N = construir_arbol_equipamiento(e), construir_arbol_nivel(e)
    assert A.raiz.altura() == 3 and N.raiz.altura() == 2
    assert sum(1 for n in A.todos() if n.es_hoja and "doc_id" in n.payload) == len(e)
    assert sum(1 for n in N.todos() if n.es_hoja and "doc_id" in n.payload) == len(e)
    assert sum(len(n.hijos) for n in A.meta["equipamientos"].values()) == len(e)      # nada se pierde
    assert sum(len(n.hijos) for n in N.raiz.hijos) == len(e)


@reales
def test_real_pecho_mancuernas_principiante():
    e, a = ejercicios_desde_csv(CSV_E), articulos_desde_csv(CSV_A)
    m = MotorArboles.desde_bosque(Bosque.construir(e, a), st.stem)
    r = m.descubrir(raices("pecho mancuernas principiante"))
    assert r["via"] in ("interseccion", "interseccion_parcial") and r["documentos"]
    assert m.descubrir(raices("pecho mancuernas principiante")) == r
