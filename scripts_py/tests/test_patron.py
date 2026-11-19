"""Pruebas del árbol de Patrón de movimiento (fase 6B): clasificación APROXIMADA por palabras clave.

    python -m pytest tests -v        (desde scripts_py)
Las de datos reales usan CSV_EJERCICIOS y CSV_ARTICULOS; si no están, se omiten.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arboles import (Bosque, MotorArboles, acumular_posorden, construir_arbol_patron, por_niveles, posorden, preorden)
from arboles.catalogo import catalogo_general, docs_del_cruce
from arboles.consulta import raices_de
from arboles.fuentes import articulos_desde_csv, ejercicios_desde_csv
from arboles.patrones import (CONSULTA_PATRON, GRUPOS_PATRON, PATRONES, REGLAS_PATRON, TERMINO_A_PATRON, patron_de_nombre,
                              patrones_de_etiquetas)
from arboles.taxonomia import SIN_CLASIFICAR
from nltk.stem.snowball import SnowballStemmer

st = SnowballStemmer("spanish")
STOP = set("de del la el los las un una y a con en para por que como mi me quiero mas es lo al se su".split())


def raices(q):
    return raices_de(q, set(), st, STOP, {}, lambda w: w)


# ======================================================================== las reglas
CASOS = [
    ("Press de banca plano", "Empuje horizontal"), ("Flexiones de diamante", "Empuje horizontal"),
    ("Flexión de brazos con inclinación", "Empuje horizontal"), ("Press de suelo con mancuernas", "Empuje horizontal"),
    ("Press de hombros con mancuernas", "Empuje vertical"), ("Press militar de pie", "Empuje vertical"),
    ("Fondos en paralelas", "Extensión de codo"), ("Extensión de tríceps por encima de la cabeza con cable", "Extensión de codo"),
    ("Remo con barra", "Tirón horizontal"), ("Tirador facial sentado", "Tirón horizontal"), ("Pendlay Row", "Tirón horizontal"),
    ("Jalón al pecho", "Tirón vertical"), ("Dominadas con banda elástica", "Tirón vertical"),
    ("Curl con barra Z", "Flexión de codo"), ("Cable aéreo rizado", "Flexión de codo"),
    ("Aperturas inclinadas con mancuernas", "Aperturas y cruces"), ("Cruce de cables de pie", "Aperturas y cruces"),
    ("Elevación lateral con mancuernas", "Elevaciones de hombro"), ("Elevaciones laterales", "Elevaciones de hombro"),
    ("Elevación frontal con disco", "Elevaciones de hombro"), ("Elevaciones frontales", "Elevaciones de hombro"),
    ("Encogimientos con barra", "Encogimientos"), ("Flexión de muñeca con barra", "Muñeca y antebrazo"),
    ("Sentadilla frontal", "Sentadilla"), ("Prensa de piernas", "Sentadilla"), ("Cuclillas de gorila", "Sentadilla"),
    ("Peso muerto rumano con mancuernas", "Bisagra de cadera"), ("Puente de glúteos", "Bisagra de cadera"),
    ("Patada de burro", "Bisagra de cadera"), ("Hiperextensión", "Bisagra de cadera"),
    ("Zancada inversa", "Zancada y unilateral"), ("Subida al escalón con mancuernas", "Zancada y unilateral"),
    ("Extensión de pierna", "Flexión y extensión de rodilla"), ("Extensiones de piernas sentado", "Flexión y extensión de rodilla"),
    ("Flexión de piernas tumbado", "Flexión y extensión de rodilla"), ("Flexiones de piernas", "Flexión y extensión de rodilla"),
    ("Elevación de pantorrillas de pie", "Pantorrilla"),
    ("Plancha lateral", "Estabilización del tronco"), ("Despliegue de barra", "Estabilización del tronco"),
    ("Giro ruso con balón", "Rotación del tronco"), ("Leñador con cable", "Rotación del tronco"),
    ("Abdominales en máquina", "Flexión de tronco"), ("Crunch inverso", "Flexión de tronco"),
    ("Elevación de piernas colgado", "Flexión de tronco"), ("Elevaciones de piernas", "Flexión de tronco"),
    ("Elevación de rodillas en barras paralelas", "Flexión de tronco"), ("Doble crujido", "Flexión de tronco"),
    ("Arrancada con pesa rusa a una mano", "Olímpico y balístico"), ("Lanzamientos de balón medicinal", "Olímpico y balístico"),
    ("Salto pliométrico sobre cajón", "Saltos y pliometría"), ("Burpee con flexión", "Saltos y pliometría"),
    ("Boxeo de sombra", "Cardio y locomoción"), ("Entrenador elíptico", "Cardio y locomoción"),
    ("Estiramiento de isquiotibiales", "Estiramiento y movilidad"), ("Gato-vaca", "Estiramiento y movilidad"),
]
# Donde dos reglas podrían coincidir, gana la que va antes: lo específico antes que lo general.
PRIORIDADES = [
    ("Remo al mentón", "Elevaciones de hombro"),                 # no es un remo
    ("Remo vertical en máquina Smith", "Elevaciones de hombro"),
    ("Curl de muñeca", "Muñeca y antebrazo"),                    # no es un curl de bíceps
    ("Curl de piernas sentado", "Flexión y extensión de rodilla"),
    ("Sentadilla a una pierna", "Zancada y unilateral"),         # unilateral antes que sentadilla
    ("Salto en sentadilla", "Saltos y pliometría"),              # pliometría antes que sentadilla
    ("Abdominales con giro ruso", "Rotación del tronco"),        # rotación antes que flexión de tronco
    ("Elevación de pierna con lanzamiento lateral", "Flexión de tronco"),   # tronco antes que balístico
    ("Extensión de tríceps con cable", "Extensión de codo"),     # tríceps antes que empuje
    ("Elevación de pantorrillas con salto", "Saltos y pliometría"),
    ("Peso muerto con pesa rusa", "Bisagra de cadera"),
    ("Press de hombros con barra de pie", "Empuje vertical"),    # hombros antes que el press genérico
    ("Estiramiento de pecho con press", "Estiramiento y movilidad"),
]


@pytest.mark.parametrize("nombre,esperado", CASOS)
def test_reglas_clasifican_lo_que_nombran_con_claridad(nombre, esperado):
    assert patron_de_nombre(nombre) == esperado


@pytest.mark.parametrize("nombre,esperado", PRIORIDADES)
def test_gana_la_primera_regla_que_coincide(nombre, esperado):
    assert patron_de_nombre(nombre) == esperado


@pytest.mark.parametrize("nombre", ["Salsa TBS", "Extensión", "Plato giratorio", "¡Salud!", "Hacedor de hombres", "", None, "   "])
def test_lo_que_no_se_reconoce_no_se_adivina(nombre):
    assert patron_de_nombre(nombre) is None


def test_la_clasificacion_es_determinista_y_no_distingue_acentos_ni_mayusculas():
    assert patron_de_nombre("ELEVACIÓN LATERAL") == patron_de_nombre("elevacion lateral") == "Elevaciones de hombro"
    assert len({patron_de_nombre("Zancada inversa") for _ in range(20)}) == 1


def test_toda_regla_apunta_a_un_patron_que_existe_y_compila():
    import re
    for patron, regla in REGLAS_PATRON:
        assert patron in PATRONES, patron
        re.compile(regla)
    assert len(PATRONES) == len(set(PATRONES)) == 22
    assert set(TERMINO_A_PATRON.values()) <= set(PATRONES) and set(CONSULTA_PATRON) <= set(PATRONES)


def test_cada_patron_lo_alcanza_alguna_regla():
    """Un patrón sin ninguna regla que lo produzca sería una rama vacía para siempre."""
    assert {p for p, _ in REGLAS_PATRON} == set(PATRONES)


# ======================================================================== el árbol
EJ = [
    {"id": 1, "nombre_es": "Press de banca plano", "grupo_id": 1, "equipamiento": "Barbell", "modalidad": "Strength", "nivel": "Beginner"},
    {"id": 2, "nombre_es": "Jalón al pecho", "grupo_id": 2, "equipamiento": "Cable", "modalidad": "Strength", "nivel": "Beginner"},
    {"id": 3, "nombre_es": "Remo con mancuerna", "grupo_id": 2, "equipamiento": "Dumbbell", "modalidad": "Strength", "nivel": "Intermediate"},
    {"id": 4, "nombre_es": "Sentadilla frontal", "grupo_id": 6, "equipamiento": "Barbell", "modalidad": "Strength", "nivel": "Intermediate"},
    {"id": 5, "nombre_es": "Salsa TBS", "grupo_id": 6, "equipamiento": "Other", "modalidad": "Strength", "nivel": "Intermediate"},
    {"id": 6, "nombre_es": "Plancha recta", "grupo_id": 10, "equipamiento": "Body Only", "modalidad": "Strength", "nivel": "Beginner"},
    {"id": 7, "nombre_es": "Extensión", "grupo_id": 10, "equipamiento": "Body Only", "modalidad": "Strength", "nivel": "Beginner"},
    {"id": 8, "nombre_es": "Curl con barra Z", "grupo_id": 4, "equipamiento": "E-Z Curl Bar", "modalidad": "Strength", "nivel": "Beginner"},
]
ART = [
    {"id": 10, "titulo": "Remo bien hecho", "etiquetas": "espalda, remo, tecnica"},
    {"id": 11, "titulo": "Curl y biceps", "etiquetas": "biceps, curl, hipertrofia"},
    {"id": 12, "titulo": "Dieta", "etiquetas": "dieta, proteina"},
    {"id": 13, "titulo": "Piernas", "etiquetas": "sentadilla, bisagra, fuerza"},
]


@pytest.fixture(scope="module")
def arbol():
    return construir_arbol_patron(EJ)


@pytest.fixture(scope="module")
def bosque():
    return Bosque.construir(EJ, ART)


@pytest.fixture(scope="module")
def motor(bosque):
    return MotorArboles.desde_bosque(bosque, st.stem)


def test_estructura_altura_y_hojas(arbol):
    assert arbol.raiz.nombre == "Patrón de movimiento" and arbol.raiz.altura() == 3
    assert [g.nombre for g in arbol.raiz.hijos] == [g for g, _ in GRUPOS_PATRON] + [SIN_CLASIFICAR]
    # todos los patrones existen aunque no tengan ejercicios (aquí casi ninguno)
    assert set(arbol.meta["patrones"]) == set(PATRONES)
    assert arbol.meta["patrones"]["Zancada y unilateral"].hijos == []
    hojas = [n for n in arbol.todos() if n.es_hoja and "doc_id" in n.payload]
    assert len(hojas) == len(EJ) and {h.nivel for h in hojas} == {3, 2}      # 2: los de «Sin clasificar»
    assert len(arbol) == 1 + len(GRUPOS_PATRON) + len(PATRONES) + 1 + len(EJ)


def test_los_ejercicios_van_a_su_patron_y_el_resto_a_sin_clasificar(arbol):
    p = arbol.meta["patrones"]
    assert [h.payload["doc_id"] for h in p["Empuje horizontal"].hijos] == [1]
    assert [h.payload["doc_id"] for h in p["Tirón vertical"].hijos] == [2]
    assert [h.payload["doc_id"] for h in p["Tirón horizontal"].hijos] == [3]
    assert [h.payload["doc_id"] for h in arbol.meta["sin_clasificar"].hijos] == [5, 7]
    assert arbol.meta["sin_clasificar_ids"] == [5, 7] and arbol.meta["aproximado"] is True
    assert arbol.doc_a_nodo[("ejercicios", 4)].ruta_texto() == "Patrón de movimiento > Piernas > Sentadilla > Sentadilla frontal"
    assert arbol.doc_a_nodo[("ejercicios", 5)].ruta_texto() == "Patrón de movimiento > Sin clasificar > Salsa TBS"


def test_sin_clasificar_es_un_concepto_pero_las_consultas_no_lo_nombran(arbol):
    assert SIN_CLASIFICAR in arbol.meta["conceptos"] and set(arbol.meta["conceptos"]) == set(PATRONES) | {SIN_CLASIFICAR}
    assert SIN_CLASIFICAR not in CONSULTA_PATRON


def test_recorridos(arbol):
    pre = [n.nombre for n in preorden(arbol.raiz)]
    assert pre[:3] == ["Patrón de movimiento", "Empuje", "Empuje horizontal"] and pre[3] == "Press de banca plano"
    assert [n.nombre for n in posorden(arbol.raiz)][-1] == "Patrón de movimiento"
    niveles = [n.nivel for n in por_niveles(arbol.raiz)]
    assert niveles == sorted(niveles) and max(niveles) == 3
    uno = lambda h: 1.0 if "doc_id" in h.payload else 0.0
    acum = acumular_posorden(arbol.raiz, uno)
    assert acum[arbol.raiz.id] == len(EJ) and acum[arbol.meta["grupos"]["Tirón"].id] == 3      # jalón, remo y curl


def test_aproximado_solo_en_patron():
    from arboles.taxonomia import ARBOLES_APROXIMADOS
    assert ARBOLES_APROXIMADOS == {"patron"}


# ======================================================================== pertenencia y aristas
def test_los_articulos_se_enlazan_por_etiquetas(bosque):
    c = bosque.conceptos("patron")
    assert bosque.docs_de_nodo(c["Tirón horizontal"]) == {("ejercicios", 3), ("articulos", 10)}
    assert bosque.docs_de_nodo(c["Flexión de codo"]) == {("ejercicios", 8), ("articulos", 11)}
    assert bosque.docs_de_nodo(c["Sentadilla"]) == {("ejercicios", 4), ("articulos", 13)}
    assert ("articulos", 13) in bosque.docs_de_nodo(c["Bisagra de cadera"])
    assert bosque.docs_de_nodo(c[SIN_CLASIFICAR]) == {("ejercicios", 5), ("ejercicios", 7)}      # ningún artículo
    assert patrones_de_etiquetas(["dieta", "curl", "remo"]) == ["Tirón horizontal", "Flexión de codo"]


def test_hay_aristas_con_los_cuatro_arboles_anteriores(bosque):
    for otro in ("anatomia", "temas", "equipamiento", "nivel"):
        assert bosque.par(otro, "patron").total() > 0, otro
    # bosque.pares(): cinco árboles, diez pares, en el orden fijo
    assert len(bosque.pares()) == 10 and bosque.pares()[-1][0] == ("nivel", "patron")


def test_los_pares_de_antes_no_cambian_al_agregar_el_patron(bosque):
    from arboles import construir_aristas, construir_arbol_anatomia, construir_arbol_temas
    antes = Bosque.construir(EJ, ART, nombres=["anatomia", "temas", "equipamiento", "nivel"])
    for a, b in (("anatomia", "temas"), ("anatomia", "equipamiento"), ("anatomia", "nivel"), ("temas", "equipamiento"),
                 ("temas", "nivel"), ("equipamiento", "nivel")):
        assert antes.par(a, b).items() == bosque.par(a, b).items(), (a, b)


# ======================================================================== catálogo y cruce
def test_catalogo_avisa_que_es_aproximado_y_cuenta_los_sin_clasificar(bosque):
    c = catalogo_general(bosque)
    por_id = {a["id"]: a for a in c["arboles"]}
    assert list(por_id) == ["anatomia", "temas", "equipamiento", "nivel", "patron"]
    assert por_id["patron"]["titulo"] == "Patrón de movimiento" and por_id["patron"]["aproximado"] is True
    assert por_id["patron"]["sin_clasificar"] == 2
    assert all("aproximado" not in por_id[a] for a in ("anatomia", "temas", "equipamiento", "nivel"))
    conceptos = {x["clave"]: x for x in por_id["patron"]["conceptos"]}
    assert conceptos["sentadilla"]["nombre"] == "Sentadilla" and conceptos["sin clasificar"]["n"] == [2, 0]
    assert conceptos["bisagra de cadera"]["grupo"] == "Piernas"
    assert len(c["pares"]) == 10 and "anatomia|patron" in c["pares"] and "nivel|patron" in c["pares"]
    assert c["pares"]["anatomia|patron"]["2|tiron vertical"] == [1, 0]


def test_cruce_con_patron_valida_y_funciona(bosque):
    nodos, docs = docs_del_cruce(bosque, "anatomia", "2", "patron", "tiron horizontal")
    assert [n.nombre for n in nodos] == ["Espalda", "Tirón horizontal"] and docs == [("articulos", 10), ("ejercicios", 3)]
    assert docs_del_cruce(bosque, "patron", "sin clasificar", "nivel", "intermedio")[1] == [("ejercicios", 5)]
    assert docs_del_cruce(bosque, "patron", "Sentadilla", "nivel", "intermedio") is None      # clave con mayúsculas


# ======================================================================== consultas
def test_una_consulta_puede_nombrar_el_patron(motor):
    r = motor.descubrir(raices("jalon espalda"))
    assert r["via"] == "interseccion"
    assert [n["arbol"] for n in r["nodos"]] == ["anatomia", "patron"]
    assert r["nodos"][1]["nombre"] == "Tirón vertical" and r["nodos"][1]["aproximado"] is True
    assert r["nodos"][0]["aproximado"] is False
    assert [(d["origen"], d["doc_id"]) for d in r["documentos"]] == [("ejercicios", 2)]


def test_patron_solo_salta_a_anatomia(motor):
    r = motor.descubrir(raices("jalon"))
    assert r["via"] == "concepto" and r["origen"]["arbol"] == "patron" and r["destino"]["arbol"] == "anatomia"
    assert r["origen"]["aproximado"] is True


def test_patron_y_equipamiento_y_nivel(motor):
    r = motor.descubrir(raices("jalon polea principiante"))
    assert r["via"] == "interseccion" and [n["arbol"] for n in r["nodos"]] == ["equipamiento", "nivel", "patron"]
    assert [d["doc_id"] for d in r["documentos"]] == [2]


def test_las_palabras_de_musculos_y_temas_no_nombran_patrones(motor):
    """«sentadilla», «plancha», «curl», «remo» y «dominadas» ya nombran un músculo: no cambian de comportamiento."""
    for q in ("sentadilla", "plancha", "curl", "remo", "dominadas", "press banca", "triceps extension", "peso muerto cadera"):
        assert "patron" not in motor.descubrir(raices(q))["traza"]["conceptos"], q


def test_el_vocabulario_de_consulta_de_todos_los_arboles_no_choca():
    """Ninguna frase de un árbol puede tener las raíces iguales, contenidas o contenedoras de las de otro
    árbol (cambiaría consultas ya resueltas). Revisa los cinco."""
    from arboles.taxonomia import (ALIAS_MUSCULO, CONSULTA_EQUIPAMIENTO, CONSULTA_NIVEL, ETIQUETA_A_MUSCULO,
                                   SINONIMOS_TEMA, TEMAS, normalizar)
    fr = lambda f: frozenset(st.stem(p) for p in normalizar(f).split() if p)
    vocab = [("anatomia", f) for f in list(ETIQUETA_A_MUSCULO) + list(ALIAS_MUSCULO)]
    vocab += [("temas", t) for _, _, tags in TEMAS for t in tags] + [("temas", f) for fs in SINONIMOS_TEMA.values() for f in fs]
    for arbol, voc in (("equipamiento", CONSULTA_EQUIPAMIENTO), ("nivel", CONSULTA_NIVEL), ("patron", CONSULTA_PATRON)):
        vocab += [(arbol, f) for fs in voc.values() for f in fs]
    choques = [(a1, f1, a2, f2) for i, (a1, f1) in enumerate(vocab) for a2, f2 in vocab[i + 1:]
               if a1 != a2 and fr(f1) and fr(f2) and (fr(f1) <= fr(f2) or fr(f2) <= fr(f1))]
    assert not choques, choques


def test_determinista(motor):
    for q in ("jalon espalda", "jalon polea principiante", "bisagra", "zzz"):
        assert len({str(motor.descubrir(raices(q))) for _ in range(10)}) == 1


# ======================================================================== datos reales (opcionales)
CSV_E, CSV_A = os.environ.get("CSV_EJERCICIOS"), os.environ.get("CSV_ARTICULOS")
reales = pytest.mark.skipif(not (CSV_E and CSV_A and os.path.exists(CSV_E or "") and os.path.exists(CSV_A or "")),
                            reason="define CSV_EJERCICIOS y CSV_ARTICULOS")


@reales
def test_real_cobertura_y_nada_se_pierde():
    e = ejercicios_desde_csv(CSV_E)
    a = construir_arbol_patron(e)
    hojas = [n for n in a.todos() if n.es_hoja and "doc_id" in n.payload]
    assert len(hojas) == len(e) == len({h.payload["doc_id"] for h in hojas})
    sin = len(a.meta["sin_clasificar_ids"])
    assert sin == len(a.meta["sin_clasificar"].hijos)
    assert 0.70 <= 1 - sin / len(e) < 0.95        # clasifica la mayoría y NO pretende clasificarlo todo
    assert a.raiz.altura() == 3


@reales
def test_real_determinista():
    e = ejercicios_desde_csv(CSV_E)
    assert construir_arbol_patron(e).meta["sin_clasificar_ids"] == construir_arbol_patron(list(reversed(e))).meta["sin_clasificar_ids"]
