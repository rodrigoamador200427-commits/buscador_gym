"""Pruebas del motor de relación (MotorArboles) y del procesamiento de consulta.

    python -m pytest tests -v        (desde scripts_py)
Las de datos reales usan CSV_EJERCICIOS y CSV_ARTICULOS; si no están, se omiten.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arboles import MotorArboles, construir_aristas, construir_arbol_anatomia, construir_arbol_temas
from arboles.consulta import normalizar_consulta, raices_de
from arboles.fuentes import articulos_desde_csv, ejercicios_desde_csv
from nltk.stem.snowball import SnowballStemmer

st = SnowballStemmer("spanish")
STOP = set("de del la el los las un una y a con en para por que como mi me quiero mas es lo al se su".split())


def raices(q):
    return raices_de(q, set(), st, STOP, {}, lambda w: w)


def ej(i, nombre, grupo):
    return {"id": i, "nombre_es": nombre, "grupo_id": grupo, "equipamiento": "Barbell",
            "modalidad": "Strength", "nivel": "Beginner"}


def ar(i, titulo, etiquetas):
    return {"id": i, "titulo": titulo, "etiquetas": etiquetas}


@pytest.fixture
def motor():
    ejercicios = [ej(1, "Press banca", 1), ej(2, "Curl", 4), ej(3, "Sentadilla", 6)]
    articulos = [
        ar(10, "Fuerza en pecho", "pecho, fuerza"),
        ar(11, "Fuerza en pecho 2", "pecho, fuerza"),
        ar(12, "Hipertrofia de biceps", "biceps, hipertrofia"),
        ar(13, "Hipertrofia de biceps 2", "biceps, hipertrofia"),
        ar(14, "Dieta", "dieta, proteina"),
        ar(15, "Recuperar", "sueno, descanso"),
    ]
    A, T = construir_arbol_anatomia(ejercicios), construir_arbol_temas(articulos)
    return MotorArboles(A, T, construir_aristas(articulos, A, T), st.stem)


def test_interseccion(motor):
    r = motor.descubrir(raices("pecho fuerza"))
    assert r["via"] == "interseccion"
    assert {d["doc_id"] for d in r["documentos"]} == {10, 11}


def test_sin_interseccion_no_inventa(motor):
    r = motor.descubrir(raices("pecho hipertrofia"))
    assert r["via"] == "sin_interseccion" and r["documentos"] == []


def test_objetivo_sin_musculo_salta_a_anatomia(motor):
    r = motor.descubrir(raices("ganar fuerza"))
    assert r["via"] == "concepto"
    assert r["origen"]["arbol"] != r["destino"]["arbol"]
    assert r["destino"]["nombre"] == "Pecho"


def test_musculo_salta_a_tema(motor):
    r = motor.descubrir(raices("biceps"))
    assert r["destino"]["nombre"] == "Hipertrofia"


def test_concepto_local(motor):
    r = motor.descubrir(raices("dieta"))
    assert r["via"] == "concepto_local"
    assert [d["doc_id"] for d in r["documentos"]] == [14]


def test_recuperacion_sin_conceptos(motor):
    r = motor.descubrir(raices("zzz"), [("articulos", 12, 0.9), ("articulos", 13, 0.1)])
    assert r["via"] == "recuperacion"
    assert r["destino"] is not None


def test_ninguno(motor):
    r = motor.descubrir(raices("zzz qqq"))
    assert r["via"] == "ninguno" and r["documentos"] == []


def test_determinista(motor):
    for q in ["ganar fuerza", "biceps", "dieta", "pecho fuerza"]:
        assert len({str(motor.descubrir(raices(q))) for _ in range(10)}) == 1


def test_consultas_distintas_destinos_distintos(motor):
    destinos = {motor.descubrir(raices(q))["destino"]["nombre"] for q in ["ganar fuerza", "biceps", "dieta", "pecho fuerza"]}
    assert len(destinos) >= 3


def test_normaliza_enie_como_indexador():
    assert normalizar_consulta("Muñeca") == "muneca"


def test_raices_sin_repetir_y_en_orden():
    r = raices_de("pecho pecho fuerza", {"pech", "fuerz"}, st, STOP, {}, lambda w: w)
    assert r == ["pech", "fuerz"]


def test_esqueleto_corrige_typo_de_forma_estable():
    esq = lambda w: "".join(c for c in w if c not in "aeiou")
    vocab = {"pech", "pach"}   # colisión de esqueleto: gana el alfabéticamente primero
    assert {tuple(raices_de("pecho", vocab, st, STOP, {}, esq)) for _ in range(5)} == {("pech",)}
    assert raices_de("puche", vocab, st, STOP, {}, esq) == ["pach"]


# ---------------- datos reales ----------------
CSV_E, CSV_A = os.environ.get("CSV_EJERCICIOS"), os.environ.get("CSV_ARTICULOS")
reales = pytest.mark.skipif(not (CSV_E and CSV_A and os.path.exists(CSV_E or "") and os.path.exists(CSV_A or "")),
                            reason="define CSV_EJERCICIOS y CSV_ARTICULOS")


@pytest.fixture(scope="module")
def motor_real():
    e, a = ejercicios_desde_csv(CSV_E), articulos_desde_csv(CSV_A)
    A, T = construir_arbol_anatomia(e), construir_arbol_temas(a)
    return MotorArboles(A, T, construir_aristas(a, A, T), st.stem)


QS = ["ganar fuerza", "quiero ganar fuerza en bench press", "ejercicios de pecho", "pecho", "press de banca",
      "biceps", "curl de biceps", "sentadilla", "como bajar de peso", "espalda", "rutina para espalda",
      "hombros", "abdomen", "pectoral", "gluteo", "piernas", "antebrazos", "cuadriceps"]


@reales
def test_real_sin_fallback(motor_real):
    vias = [motor_real.descubrir(raices(q))["via"] for q in QS]
    assert not [v for v in vias if v in ("ninguno", "sin_interseccion")]


@reales
def test_real_diversidad_y_documentos(motor_real):
    rs = [motor_real.descubrir(raices(q)) for q in QS]
    assert len({r["destino"]["nombre"] for r in rs}) >= 5
    assert all(r["documentos"] for r in rs)


@reales
def test_real_determinista(motor_real):
    assert len({str(motor_real.descubrir(raices("ganar fuerza"))) for _ in range(5)}) == 1


# ---------------- catálogo A+B ----------------
def test_catalogo_puentes(motor):
    from arboles.catalogo import catalogo
    c = catalogo(motor.A, motor.T, motor.E)
    assert c["puentes"]["1|Fuerza"] == [10, 11]
    assert c["puentes"]["4|Hipertrofia"] == [12, 13]
    assert "1|Hipertrofia" not in c["puentes"]          # sin relación: no se inventa
    assert {m["gid"] for m in c["musculos"]} >= {1, 4, 6}
    assert next(m for m in c["musculos"] if m["gid"] == 1)["n_ejercicios"] == 1
    assert next(t for t in c["temas"] if t["nombre"] == "Fuerza")["n_articulos"] == 2


# ---------------- stopwords en capas y preparación de consulta ----------------
from arboles.taxonomia import OBJETIVO_PROTEGIDO, PALABRAS_INTENCION


def test_capas_de_stopwords_no_se_pisan():
    assert not (PALABRAS_INTENCION & OBJETIVO_PROTEGIDO)


def test_palabras_objetivo_sobreviven_a_las_stopwords():
    q = " ".join(sorted(OBJETIVO_PROTEGIDO))
    r = raices_de(q, set(), st, STOP | PALABRAS_INTENCION, {}, lambda w: w)
    assert len(r) == len({st.stem(w) for w in OBJETIVO_PROTEGIDO})


def test_palabras_de_intencion_se_quitan():
    r = raices_de("quiero saber como hacer fuerza", set(), st, STOP | PALABRAS_INTENCION, {}, lambda w: w)
    assert r == [st.stem("saber"), st.stem("fuerza")]


def test_stopwords_con_acento_coinciden():
    assert raices_de("está más fuerza", set(), st, {"está", "más"}, {}, lambda w: w) == [st.stem("fuerza")]


def test_frase_de_intencion_se_sustituye_por_vocabulario_del_tema(motor):
    r = raices("como bajar de peso")
    p = motor.preparar_consulta(r)
    assert st.stem("bajar") not in p["raices"] and st.stem("peso") not in p["raices"]
    assert {st.stem("dieta"), st.stem("calorias"), st.stem("nutricion")} <= set(p["raices"])
    assert set(p["descartadas"]) == {st.stem("bajar"), st.stem("peso")}


def test_palabra_suelta_se_conserva_y_se_expande(motor):
    p = motor.preparar_consulta(raices("masa"))
    assert st.stem("masa") in p["raices"] and st.stem("hipertrofia") in p["raices"]
    assert p["descartadas"] == []


def test_consulta_con_etiquetas_no_cambia(motor):
    r = raices("pecho fuerza")
    assert motor.preparar_consulta(r)["raices"] == r


def test_musculo_nombrado_no_se_descarta(motor):
    p = motor.preparar_consulta(raices("bajar peso pecho"))
    assert st.stem("pecho") in p["raices"]


def test_preparar_consulta_nunca_devuelve_vacio(motor):
    assert motor.preparar_consulta([]) ["raices"] == []
    assert motor.preparar_consulta(raices("zzz"))["raices"] == raices("zzz")
