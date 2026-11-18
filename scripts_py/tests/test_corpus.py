"""Pruebas de las herramientas del corpus (fase 6A): vocabulario, validar_lote, planear_lote,
importar_lote y consultas_referencia.

    cd scripts_py && python -m pytest tests/test_corpus.py -v

La lógica pura no usa BD. La importación corre SOLO sobre gym_buscador_test.
"""
import copy

import pytest

import bd_prueba
import consultas_referencia as cr
import importar_lote as il
import planear_lote as pl
import validar_lote as vl
from arboles import taxonomia as T
from etiquetado import vocabulario_controlado

# Todas las familias con ejercicios de sobra, salvo las que la tabla real tampoco tiene
CONTEO = {k: 50 for k, _, _ in vl.FAMILIAS}
for _k in ("hip thrust", "face pull", "pajaros", "pullover", "good morning", "paseo del granjero", "sentadilla bulgara",
           "peso muerto sumo", "curl de concentracion", "remo al menton", "press arnold"):
    CONTEO[_k] = 0

BUENO = {
    "fila": 2,
    "titulo": "Control del descenso en el press de banca",
    "contenido": ("Bajar la barra de forma controlada y sin rebotes mantiene la tensión en el pecho durante todo el recorrido. "
                  "En el press de banca conviene llevar los omóplatos juntos y apoyados en el banco, y los codos algo por debajo "
                  "de los hombros. Si pierdes el control, reduce la carga y repite con calma."),
    "etiquetas": "pecho, press banca, tecnica, escapulas, trayectoria, barra",
}
EXISTENTES = [
    {"titulo": "Recuperación tras una semana exigente", "etiquetas": "recuperacion, descanso, fatiga, sueno, adaptacion, estres",
     "contenido": "Dormir con regularidad y repartir los días de descanso ayuda a que el cuerpo se adapte al esfuerzo acumulado. Reduce el volumen si notas fatiga persistente."},
    {"titulo": "Calentamiento antes de sentadillas", "etiquetas": "calentamiento, movilidad, sentadilla, cuadriceps, preparacion, tecnica",
     "contenido": "Dedica unos minutos a movilizar tobillos y caderas y haz series ligeras de sentadilla antes de cargar peso. Así entras en la serie de trabajo con mejor control."},
]


def lote_de(**cambios):
    a = copy.deepcopy(BUENO)
    a.update(cambios)
    return [a]


def errores_de(lote, **kw):
    res = vl.validar(lote, kw.pop("existentes", EXISTENTES), kw.pop("conteo", CONTEO), kw.pop("plan", None))
    return [e["mensaje"] for e in res["errores"]]


# --------------------------------------------------------------------------- vocabulario

def test_vocabulario_tiene_el_de_taxonomia_mas_45_extras():
    v = vocabulario_controlado()
    assert len(T.VOCABULARIO_EXTRA) == 45
    assert len(v) == 190
    assert {"pecho", "hipertrofia", "barra", "principiante", "rendimiento", "vfc"} <= set(v)


def test_vocabulario_deja_fuera_lo_que_toca_salud():
    v = vocabulario_controlado()
    for t in ("dosis", "cortisol", "inflamacion", "inmunidad", "hormonas", "mtor", "melatonina", "atp", "dolor"):
        assert t not in v, t


def test_las_etiquetas_extra_no_cambian_el_tema_de_un_articulo():
    """Por eso van en VOCABULARIO_EXTRA y no en TEMAS: no mueven el árbol de Temas."""
    assert T.temas_de_etiquetas(["rendimiento", "fisiologia", "entrenamiento", "salud"]) == []
    assert T.temas_de_etiquetas(["tecnica", "rendimiento"]) == ["Técnica y biomecánica"]


# --------------------------------------------------------------------------- validar: lo bueno pasa

def test_un_articulo_correcto_pasa_sin_errores():
    assert errores_de(lote_de()) == []


def test_clasificacion_igual_que_el_arbol():
    assert vl.clasificar(BUENO["etiquetas"]) == ("Técnica y biomecánica", [1])
    assert vl.clasificar("recuperacion, sueno, descanso, fatiga, rendimiento, salud") == ("Recuperación", [])


# --------------------------------------------------------------------------- validar: formato y texto

@pytest.mark.parametrize("cambios, trozo", [
    ({"titulo": "Control del descenso en el press de banca"}, "ya existe"),         # se arma abajo con existentes
    ({"titulo": "Dos palabras"}, "palabras"),
    ({"contenido": "Muy corto. Demasiado corto."}, "palabras"),
    ({"contenido": BUENO["contenido"] + " " + BUENO["contenido"]}, "palabras"),
    ({"contenido": BUENO["contenido"].rstrip(".")}, "puntuación"),
    ({"etiquetas": "pecho, tecnica, escapulas, trayectoria, barra"}, "5 etiquetas"),
    ({"etiquetas": BUENO["etiquetas"] + ", pecho, tecnica"}, "etiquetas"),
    ({"etiquetas": "pecho, press banca, tecnica, escapulas, trayectoria, inventada"}, "fuera del vocabulario"),
    ({"etiquetas": "pecho, press banca, tecnica, escapulas, trayectoria, dosis"}, "fuera del vocabulario"),
    ({"contenido": BUENO["contenido"] + " <b>hola</b>"}, "caracteres"),
])
def test_errores_de_formato(cambios, trozo):
    existentes = EXISTENTES + [{"titulo": BUENO["titulo"], "contenido": "otro texto distinto", "etiquetas": "x"}]
    msgs = errores_de(lote_de(**cambios), existentes=existentes if "ya existe" in trozo else EXISTENTES)
    assert any(trozo in m for m in msgs), msgs


def test_titulo_repetido_dentro_del_lote_y_sin_distinguir_acentos():
    a, b = copy.deepcopy(BUENO), copy.deepcopy(BUENO)
    b["fila"] = 3
    b["titulo"] = "CONTROL del descenso en el PRESS de banca"
    b["contenido"] = "Una explicación distinta sobre otro asunto: mantén la espalda apoyada, respira con calma y controla cada repetición hasta el final del movimiento sin prisa."
    msgs = errores_de([a, b])
    assert any("repetido en el lote" in m for m in msgs), msgs


def test_idioma_rechaza_ingles():
    ingles = ("Lowering the bar with control keeps the tension on the chest during the whole movement. "
              "You should keep your shoulder blades together and press the bar from the lower part of the chest. "
              "If you lose control, reduce the load and repeat it with patience.")
    assert any("no parece español" in m for m in errores_de(lote_de(contenido=ingles)))


# --------------------------------------------------------------------------- validar: seguridad

@pytest.mark.parametrize("frase, trozo", [
    ("Toma 5 gramos de proteína cada día.", "cantidad"),
    ("Consume 300 mg por la mañana.", "cantidad"),
    ("Aporta 2 ml de aceite.", "cantidad"),
    ("Sube el torso 30 grados con cuidado.", "cantidad"),
    ("Mejora hasta un 20 % la fuerza.", "porcentaje"),
    ("Según una revisión de 2019 funciona.", "año"),
    ("Notarás resultados en 4 semanas.", "plazo"),
    ("Ajusta la dosis con calma.", "dosis"),
    ("Es un tratamiento para la espalda.", "tratamiento"),
    ("Sirve para curar la lesión.", "cura"),
    ("Un estudio demuestra que mejora.", "estudios"),
    ("Está demostrado que funciona.", "demostrado"),
    ("Te garantiza resultados rápidos.", "garantía"),
    ("Es un método milagroso.", "milagrosa"),
    ("Es una enfermedad frecuente.", "médico"),
])
def test_rechaza_dosis_cifras_estudios_y_promesas(frase, trozo):
    contenido = BUENO["contenido"].replace("Si pierdes el control, reduce la carga y repite con calma.", frase)
    msgs = errores_de(lote_de(contenido=contenido))
    assert any(trozo in m for m in msgs), (frase, msgs)


def test_una_cifra_suelta_es_solo_aviso_y_las_absolutas_tambien():
    contenido = BUENO["contenido"].replace("reduce la carga y repite con calma.", "reduce la carga, descansa 2 minutos y repite siempre.")
    res = vl.validar(lote_de(contenido=contenido), EXISTENTES, CONTEO)
    assert not res["errores"], res["errores"]
    avisos = {a["mensaje"] for a in res["avisos"]}
    assert "contiene una cifra" in avisos and "palabra absoluta" in avisos


def test_suplementacion_no_admite_ninguna_cifra():
    a = {"fila": 2, "titulo": "Cómo leer la etiqueta de un suplemento",
         "contenido": ("Antes de comprar un suplemento revisa los ingredientes, la lista de aditivos y si el fabricante indica con claridad qué contiene "
                       "cada porción. Desconfía de los envases que prometen mucho y explican poco, y elige productos con información transparente. "
                       "Compara dos marcas y consulta con un profesional si tienes dudas."),
         "etiquetas": "suplemento, seguridad, rendimiento, salud, micronutrientes, principiantes"}
    assert vl.clasificar(a["etiquetas"])[0] == "Suplementación"
    assert not errores_de([a])
    a["contenido"] = a["contenido"].replace("dos marcas", "2 marcas")
    assert any("Suplementación no puede llevar ninguna cifra" in m for m in errores_de([a]))


# --------------------------------------------------------------------------- validar: ejercicios

def test_rechaza_un_ejercicio_que_la_tabla_no_tiene():
    contenido = BUENO["contenido"].replace("Si pierdes el control", "Combínalo con hip thrust y, si pierdes el control")
    assert any("hip thrust" in m for m in errores_de(lote_de(contenido=contenido))), "debía rechazar hip thrust"


def test_rechaza_una_familia_con_menos_de_5_ejercicios_en_la_tabla():
    conteo = dict(CONTEO, **{"press de banca": 4})
    assert any("press de banca" in m and "4 registros" in m for m in errores_de(lote_de(), conteo=conteo))


def test_articulo_de_tecnica_de_un_musculo_debe_nombrar_un_ejercicio_que_exista_para_ese_musculo():
    sin = BUENO["contenido"].replace("En el press de banca conviene", "En este movimiento conviene").replace("press de banca", "movimiento")
    msgs = errores_de(lote_de(contenido=sin, titulo="Control del descenso al empujar"))
    assert any("no nombra ninguna de sus familias de ejercicio" in m for m in msgs), msgs
    # con una familia de OTRO músculo tampoco vale
    con_otra = sin.replace("movimiento conviene", "movimiento, igual que en la sentadilla, conviene")
    assert any("no nombra ninguna" in m for m in errores_de(lote_de(contenido=con_otra, titulo="Control del descenso al empujar")))


def test_cada_familia_de_ejercicio_se_reconoce_por_su_propio_nombre():
    """Una regex mal escrita (p. ej. «escaladores?», que no casaba con «escalador») deja a los artículos
    sin forma de cumplir la regla de ejercicios; cada familia debe reconocerse con su nombre escrito tal cual."""
    import re
    for nombre, patron, _ in vl.FAMILIAS:
        assert re.search(patron, nombre), f"la regex de la familia «{nombre}» no reconoce «{nombre}»"
    for nombre in ("escalador", "escaladores", "elevacion de piernas", "plancha lateral"):
        assert any(re.search(rx, nombre) for _, rx, _ in vl.FAMILIAS), nombre


# --------------------------------------------------------------------------- validar: plan

def test_plan_comprueba_tema_y_musculo_que_resultan_de_las_etiquetas():
    ok = {vl.normalizar(BUENO["titulo"]): ("Técnica y biomecánica", "Pecho")}
    assert errores_de(lote_de(), plan=ok) == []
    mal_tema = {vl.normalizar(BUENO["titulo"]): ("Fuerza", "Pecho")}
    assert any("el plan dice «Fuerza»" in m for m in errores_de(lote_de(), plan=mal_tema))
    mal_musculo = {vl.normalizar(BUENO["titulo"]): ("Técnica y biomecánica", "Espalda")}
    assert any("músculos que resultan" in m for m in errores_de(lote_de(), plan=mal_musculo))
    sin_musculo = {vl.normalizar(BUENO["titulo"]): ("Técnica y biomecánica", "")}
    assert any("músculos que resultan" in m for m in errores_de(lote_de(), plan=sin_musculo))
    assert any("no está en el plan" in m for m in errores_de(lote_de(), plan={"otro": ("Fuerza", "")}))


# --------------------------------------------------------------------------- validar: similitud

def test_rechaza_un_duplicado_cercano_con_un_existente_y_con_otro_del_lote():
    existentes = EXISTENTES + [{"titulo": "Descenso controlado del press de banca", "contenido": BUENO["contenido"], "etiquetas": BUENO["etiquetas"]}]
    msgs = errores_de(lote_de(), existentes=existentes)
    assert any("demasiado parecido" in m and "existente" in m for m in msgs), msgs
    a, b = copy.deepcopy(BUENO), copy.deepcopy(BUENO)
    b["fila"], b["titulo"] = 3, "Descenso lento y controlado en press de banca"
    assert any("demasiado parecido" in m and "lote" in m for m in errores_de([a, b]))


def test_pares_entre_06_y_08_solo_se_reportan(monkeypatch):
    import numpy as np
    monkeypatch.setattr(vl, "similitudes", lambda l, e: (np.array([[0.0, 0.7, 0.0], [0.7, 0.0, 0.0]])[:, :2].tolist() and
                                                          np.array([[0.65, 0.0, 0.0, 0.0], [0.0, 0.7, 0.0, 0.0]]), len(e)))
    a, b = copy.deepcopy(BUENO), copy.deepcopy(BUENO)
    b["fila"], b["titulo"] = 3, "Otro título distinto para este artículo"
    res = vl.validar([a, b], EXISTENTES, CONTEO)
    assert not any("demasiado parecido" in e["mensaje"] for e in res["errores"])
    assert [p["similitud"] for p in res["bandas"]] == [0.7, 0.65]


def test_similitud_de_articulos_distintos_es_baja():
    S, n = vl.similitudes([f"{BUENO['titulo']} {BUENO['contenido']} {BUENO['etiquetas']}"],
                          [f"{e['titulo']} {e['contenido']} {e['etiquetas']}" for e in EXISTENTES])
    assert n == 2 and S.shape == (1, 3) and S.max() < 0.3


# --------------------------------------------------------------------------- lectura de CSV

def test_leer_lote_exige_el_encabezado_y_3_columnas(tmp_path):
    bueno = tmp_path / "ok.csv"
    bueno.write_text('"titulo","contenido","etiquetas"\n"T","C, con coma.","a, b"\n', encoding="utf-8")
    filas, fallos = vl.leer_lote(str(bueno))
    assert not fallos and filas[0]["contenido"] == "C, con coma." and filas[0]["fila"] == 2
    malo = tmp_path / "mal.csv"
    malo.write_text('"title","body","tags"\n"T","C","a"\n', encoding="utf-8")
    assert vl.leer_lote(str(malo))[1]
    corto = tmp_path / "corto.csv"
    corto.write_text('"titulo","contenido","etiquetas"\n"T","C"\n', encoding="utf-8")
    assert "2 columnas" in vl.leer_lote(str(corto))[1][0]


# --------------------------------------------------------------------------- planear_lote

OBJ = {"matriz_nuevos": {"Fuerza": {"Pecho": 10, "": 30}, "Recuperación": {"": 60}}}


def test_falta_resta_lo_generado_y_nunca_es_negativo():
    f = pl.falta(OBJ, {("Fuerza", "Pecho"): 4, ("Recuperación", ""): 99})
    assert f == {("Fuerza", "Pecho"): 6, ("Fuerza", ""): 30, ("Recuperación", ""): 0}


def test_repartir_suma_exacto_respeta_el_pendiente_y_es_determinista():
    pend = {("Fuerza", "Pecho"): 10, ("Fuerza", ""): 30, ("Recuperación", ""): 60}
    a = pl.repartir(pend, 10)
    assert sum(a.values()) == 10 and a == pl.repartir(pend, 10)
    assert a[("Recuperación", "")] == 6 and a[("Fuerza", "")] == 3 and a[("Fuerza", "Pecho")] == 1
    assert pl.repartir({("A", ""): 2}, 10) == {("A", ""): 2}        # no reparte más de lo que falta
    assert pl.repartir({}, 5) == {} and pl.repartir(pend, 0) == {}


def test_repartir_con_la_matriz_real_da_exactamente_100():
    import json, os
    with open(os.path.join(vl.RAIZ, "corpus", "objetivos.json"), encoding="utf-8") as f:
        obj = json.load(f)
    pend = pl.falta(obj, {})
    assert sum(pend.values()) == 1659
    cuotas = pl.repartir(pend, 100)
    assert sum(cuotas.values()) == 100
    assert all(cuotas[k] <= pend[k] for k in cuotas)


def test_celda_de_usa_el_mismo_criterio_que_el_arbol():
    assert pl.celda_de(BUENO["etiquetas"]) == ("Técnica y biomecánica", "Pecho")
    assert pl.celda_de("nutricion, proteina, dieta, saciedad, salud, digestion") == ("Alimentación", "")


# --------------------------------------------------------------------------- consultas de referencia

def test_comparar_marca_revisar_si_el_primero_cae_del_top3():
    def q(i, ids, gen=()):
        return {"id": i, "consulta": f"c{i}", "resultados": [{"origen": "articulos", "doc_id": d, "score": 1.0, "titulo": f"t{d}", "generado": d in gen} for d in ids]}
    antes = [q(1, [1, 2, 3, 4, 5, 6]), q(2, [1, 2, 3, 4, 5, 6])]
    despues = [q(1, [9, 1, 2, 8, 3, 4], gen={9, 8}), q(2, [7, 6, 5, 9, 1, 2], gen={7, 9})]
    f = cr.comparar(antes, despues)
    assert f[0]["top1"] and not f[0]["revisar"] and f[0]["nuevos5"] == 2 and f[0]["top5"] == 3
    assert not f[1]["top1"] and f[1]["revisar"] and f[1]["perdidos10"] == 2      # se pierden el 3 y el 4


def test_las_18_consultas_existen_y_no_se_repiten():
    consultas = cr.cargar_consultas()
    assert len(consultas) == 18
    assert len({c["consulta"] for c in consultas}) == 18


# --------------------------------------------------------------------------- importar (BD de pruebas)

@pytest.fixture(scope="module")
def conn():
    try:
        c = bd_prueba.conectar_prueba()
    except bd_prueba.BDNoEsDePrueba:
        raise
    except Exception as e:
        pytest.skip(f"BD de pruebas no disponible: {e}")
    if c is None:
        pytest.skip("MySQL no disponible para gym_buscador_test")
    yield c
    c.close()


def contar(conn, donde="1 = 1"):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM articulos WHERE {donde}")
    n = cur.fetchone()[0]
    cur.close()
    return n


def test_importar_marca_generado_y_deja_los_originales_como_original(conn):
    bd_prueba.preparar_bd(conn)
    assert contar(conn, "origen_contenido = 'original'") == 2
    primero, ultimo = il.importar(conn, [dict(BUENO), dict(BUENO, titulo="Otro título para el segundo")])
    assert ultimo == primero + 1
    assert contar(conn, "origen_contenido = 'generado'") == 2
    assert contar(conn, "origen_contenido = 'original'") == 2           # los de antes no cambiaron
    cur = conn.cursor(dictionary=True)
    assert il.tiene_columna_origen(cur)
    cur.close()
    bd_prueba.preparar_bd(conn)


def test_importar_es_todo_o_nada(conn):
    bd_prueba.preparar_bd(conn)
    antes = contar(conn)
    with pytest.raises(Exception):
        il.importar(conn, [dict(BUENO), dict(BUENO, titulo=None)])      # la segunda viola NOT NULL
    assert contar(conn) == antes, "la primera fila no debió quedar guardada"
    bd_prueba.preparar_bd(conn)


def test_importar_rechaza_un_lote_con_errores_y_no_toca_la_bd(conn, tmp_path, monkeypatch):
    bd_prueba.preparar_bd(conn)
    malo = tmp_path / "malo.csv"
    malo.write_text('"titulo","contenido","etiquetas"\n"Corto","Solo dos palabras.","a, b"\n', encoding="utf-8")
    antes = contar(conn)
    assert il.main([str(malo)]) == 1
    assert contar(conn) == antes


def test_contar_familias_lee_la_tabla_de_ejercicios(conn):
    bd_prueba.preparar_bd(conn)
    cur = conn.cursor(dictionary=True)
    conteo = vl.contar_familias(cur)
    cur.close()
    assert conteo["press de banca"] == 2 and conteo["sentadilla"] == 2     # el contenido de prueba: 2 press de banca y 2 sentadillas
    assert conteo["hip thrust"] == 0
