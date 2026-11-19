"""Pruebas del etiquetado (etiquetado.py) y de su generador (generar_etiquetas.py).

    cd scripts_py && python -m pytest tests/test_etiquetas.py -v

La lógica pura no usa BD. Las pruebas con BD corren SOLO sobre gym_buscador_test.
"""
import pytest

import bd_prueba
from arboles import construir_arbol_anatomia, construir_arbol_temas
from etiquetado import clave, construir_etiquetas, construir_rutas, formas_con_acento, unir_plurales


def ej(i, grupo=1, equipo="Barbell", nivel="Beginner", modalidad="Strength", nombre="Ejercicio"):
    return {"id": i, "nombre_es": nombre, "grupo_id": grupo, "equipamiento": equipo,
            "nivel": nivel, "modalidad": modalidad}


def art(i, etiquetas, titulo="Artículo"):
    return {"id": i, "titulo": titulo, "etiquetas": etiquetas}


def etiquetas_de(asignaciones, origen, doc_id):
    return {k for o, d, k in asignaciones if o == origen and d == doc_id}


# --------------------------------------------------------------------------- normalización

@pytest.mark.parametrize("texto, esperado", [
    ("Cuádriceps", "cuadriceps"),
    ("  Peso   Corporal ", "peso corporal"),
    ("Pectoral", "pecho"),                 # sinónimo
    ("GEMELOS", "pantorrilla"),            # sinónimo
    ("barra EZ", "barra z"),
    ("Mancuernas", "mancuerna"),
    ("sueño", "sueno"),
])
def test_clave_normaliza_y_junta_sinonimos(texto, esperado):
    assert clave(texto) == esperado


def test_plural_se_une_solo_si_existe_el_singular():
    canon = unir_plurales(["rodillas", "rodilla", "series", "macros", "lesion", "lesiones"])
    assert canon["rodillas"] == "rodilla"
    assert canon["lesiones"] == "lesion"
    assert canon["macros"] == "macros"     # no hay "macro": se queda igual
    assert canon["series"] == "series"


def test_formas_con_acento_elige_la_mas_frecuente():
    formas = formas_con_acento(["El sueño importa", "sueño y técnica", "sueno"])
    assert formas["sueno"] == "sueño"
    assert formas["tecnica"] == "técnica"


# --------------------------------------------------------------------------- ejercicios

def test_ejercicio_genera_musculo_equipamiento_nivel_y_modalidad_en_espanol():
    etq, asig = construir_etiquetas([ej(1, grupo=6, equipo="Dumbbell", nivel="Expert",
                                        modalidad="Plyometrics")], [])
    assert etiquetas_de(asig, "ejercicios", 1) == {"cuadriceps", "mancuerna", "avanzado", "pliometria"}
    assert etq["cuadriceps"] == {"tipo": "musculo", "visible": "Cuádriceps"}
    assert etq["mancuerna"] == {"tipo": "equipamiento", "visible": "Mancuernas"}
    assert etq["avanzado"] == {"tipo": "nivel", "visible": "Avanzado"}
    assert etq["pliometria"] == {"tipo": "modalidad", "visible": "Pliometría"}


def test_equipamiento_otro_o_vacio_y_grupo_desconocido_no_generan_etiqueta():
    _, asig = construir_etiquetas([ej(1, grupo=99, equipo="Other", nivel=None, modalidad=None),
                                   ej(2, grupo=None, equipo="", nivel="", modalidad="")], [])
    assert etiquetas_de(asig, "ejercicios", 1) == set()
    assert etiquetas_de(asig, "ejercicios", 2) == set()


# --------------------------------------------------------------------------- artículos

def test_articulo_clasifica_musculo_equipamiento_y_tema():
    etq, asig = construir_etiquetas([], [art(1, "Pectoral, dorsal, barra, creatina")])
    assert etiquetas_de(asig, "articulos", 1) == {"pecho", "dorsal", "barra", "creatina"}
    assert etq["pecho"]["tipo"] == "musculo"
    assert etq["dorsal"]["tipo"] == "musculo"
    assert etq["barra"]["tipo"] == "equipamiento"
    assert etq["creatina"]["tipo"] == "tema"


def test_plurales_y_sinonimos_de_articulos_quedan_en_una_sola_etiqueta():
    _, asig = construir_etiquetas([], [art(1, "rodillas, gemelos"), art(2, "rodilla, pantorrilla")])
    assert etiquetas_de(asig, "articulos", 1) == {"rodilla", "pantorrilla"}
    assert etiquetas_de(asig, "articulos", 2) == {"rodilla", "pantorrilla"}


def test_misma_clave_en_ejercicio_y_articulo_es_una_etiqueta_con_el_tipo_de_mayor_prioridad():
    etq, asig = construir_etiquetas([ej(1, grupo=1)], [art(2, "fuerza, pecho")])
    assert ("ejercicios", 1, "fuerza") in asig and ("articulos", 2, "fuerza") in asig
    assert etq["fuerza"] == {"tipo": "modalidad", "visible": "Fuerza"}   # modalidad > tema
    assert etq["pecho"] == {"tipo": "musculo", "visible": "Pecho"}       # nombre de taxonomia.py


def test_nombre_visible_recupera_acentos_del_texto():
    etq, _ = construir_etiquetas([], [art(1, "sueno, tecnica de carrera")],
                                 ["El sueño y la técnica de carrera"])
    assert etq["sueno"]["visible"] == "Sueño"
    assert etq["tecnica de carrera"]["visible"] == "Técnica de carrera"


def test_etiqueta_con_html_se_guarda_como_texto():
    """El generador no interpreta nada: el escape es tarea de quien muestra (index.html)."""
    etq, _ = construir_etiquetas([], [art(1, "<b>negrita</b>")])
    assert any("<b>" in k for k in etq)


# --------------------------------------------------------------------------- rutas

def test_rutas_van_de_la_raiz_al_padre_de_la_hoja():
    ejercicios = [ej(1, grupo=1, equipo="Barbell", nombre="Press de banca")]
    articulos = [art(2, "creatina, suplemento", titulo="Creatina")]
    rutas = construir_rutas(construir_arbol_anatomia(ejercicios), construir_arbol_temas(articulos))
    assert rutas[("ejercicios", 1)] == ("anatomia", "Cuerpo humano > Tren superior > Pecho > Barra")
    assert rutas[("articulos", 2)] == ("temas", "Conocimiento > Nutrición > Suplementación")


# --------------------------------------------------------------------------- con BD de pruebas

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


def filas(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    r = cur.fetchall()
    cur.close()
    return r


def test_generar_llena_las_tablas_con_el_contenido_sintetico(conn):
    bd_prueba.preparar_bd(conn)                       # ya llama a generar()
    etq = dict(filas(conn, "SELECT nombre_normalizado, tipo FROM etiquetas"))
    assert etq["pecho"] == "musculo" and etq["cuadriceps"] == "musculo"
    assert etq["barra"] == "equipamiento" and etq["intermedio"] == "nivel"
    assert etq["fuerza"] == "modalidad"
    de101 = {r[0] for r in filas(conn, "SELECT e.nombre_normalizado FROM documento_etiquetas d "
                                       "JOIN etiquetas e ON e.id = d.etiqueta_id "
                                       "WHERE d.origen = 'ejercicios' AND d.doc_id = %s", (101,))}
    assert de101 == {"pecho", "barra", "principiante", "fuerza"}
    rutas = filas(conn, "SELECT origen, doc_id, ruta FROM documento_rutas ORDER BY origen, doc_id")
    assert ("ejercicios", 201, "Cuerpo humano > Tren inferior > Cuádriceps > Barra") in rutas
    # Fase 6B: una ruta POR ÁRBOL. 10 ejercicios x 4 árboles (anatomía, equipamiento, nivel, patrón) y 2 artículos x temas
    por_arbol = dict(filas(conn, "SELECT arbol, COUNT(*) FROM documento_rutas GROUP BY arbol"))
    assert por_arbol == {"anatomia": 10, "equipamiento": 10, "nivel": 10, "patron": 10, "temas": 2}
    assert len(rutas) == 42
    de101 = {r[0]: r[1] for r in filas(conn, "SELECT arbol, ruta FROM documento_rutas WHERE origen = 'ejercicios' AND doc_id = %s", (101,))}
    assert de101 == {"anatomia": "Cuerpo humano > Tren superior > Pecho > Barra",
                     "equipamiento": "Equipamiento > Pesas libres > Barra",
                     "nivel": "Nivel de experiencia > Principiante",
                     "patron": "Patrón de movimiento > Empuje > Empuje horizontal"}


def test_generar_es_idempotente_y_conserva_los_ids(conn):
    from generar_etiquetas import generar
    bd_prueba.preparar_bd(conn)
    antes = filas(conn, "SELECT id, nombre_normalizado FROM etiquetas ORDER BY id")
    n_asig = filas(conn, "SELECT COUNT(*) FROM documento_etiquetas")
    generar(conn)
    generar(conn)
    assert filas(conn, "SELECT id, nombre_normalizado FROM etiquetas ORDER BY id") == antes
    assert filas(conn, "SELECT COUNT(*) FROM documento_etiquetas") == n_asig


def test_generar_borra_lo_que_ya_no_existe(conn):
    from generar_etiquetas import generar
    bd_prueba.preparar_bd(conn)
    cur = conn.cursor()
    cur.execute("UPDATE articulos SET etiquetas = %s WHERE id = %s", ("pecho", 302))
    cur.execute("DELETE FROM ejercicios WHERE id = %s", (205,))
    conn.commit()
    cur.close()
    generar(conn)
    nombres = {r[0] for r in filas(conn, "SELECT nombre_normalizado FROM etiquetas")}
    assert "pierna" not in nombres                    # solo la tenía el artículo 302
    assert filas(conn, "SELECT COUNT(*) FROM documento_etiquetas WHERE origen = 'ejercicios' "
                       "AND doc_id = %s", (205,)) == [(0,)]
    assert filas(conn, "SELECT COUNT(*) FROM documento_rutas WHERE doc_id = %s", (205,)) == [(0,)]
    bd_prueba.preparar_bd(conn)                       # dejar la BD como la esperan las demás pruebas


def test_insertar_en_bloques_parte_las_filas_para_no_pasar_max_allowed_packet():
    """Con el árbol de patrón había 13 392 rutas y un solo INSERT superó el 1 MB de max_allowed_packet:
    MariaDB cortó la conexión. Ahora se parte en bloques (dentro de la misma transacción)."""
    from generar_etiquetas import BLOQUE, insertar_en_bloques

    class Cursor:
        def __init__(self):
            self.lotes = []

        def executemany(self, sql, filas):
            self.lotes.append(list(filas))

    cur = Cursor()
    filas = [(i,) for i in range(BLOQUE * 3 + 7)]
    insertar_en_bloques(cur, "INSERT ...", filas)
    assert [len(l) for l in cur.lotes] == [BLOQUE, BLOQUE, BLOQUE, 7]
    assert [f for l in cur.lotes for f in l] == filas                  # nada se pierde ni se reordena
    cur2 = Cursor()
    insertar_en_bloques(cur2, "INSERT ...", [])
    assert cur2.lotes == []
