"""Pruebas de AISLAMIENTO de recomendaciones por perfil (protección de información).

Corren SOLO sobre gym_buscador_test (ver bd_prueba.py), con contenido sintético:
    cd scripts_py && python -m pytest tests/test_aislamiento.py -v

Escenario:
    cuenta 1 ── perfil "Pecho"  : likes 101, 102 (press de banca)
             └─ perfil "Pierna" : likes 201, 202 (sentadilla)
             └─ perfil "Vacío"  : sin likes
    cuenta 2 ── perfil "Otro"   : likes 101, 102, 103 (mismos gustos que Pecho)
"""
import re

import pytest

import bd_prueba
from recommender import recomendar

PECHO = {("ejercicios", i) for i in (101, 102, 103, 104, 105)} | {("articulos", 301)}
PIERNA = {("ejercicios", i) for i in (201, 202, 203, 204, 205)} | {("articulos", 302)}


# --------------------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def conn():
    try:
        c = bd_prueba.conectar_prueba()
    except bd_prueba.BDNoEsDePrueba:
        raise                                            # nunca se salta: es un error grave
    except Exception as e:                               # p. ej. falta config.test.ini.php
        pytest.skip(f"BD de pruebas no disponible: {e}")
    if c is None:
        pytest.skip("MySQL no disponible para gym_buscador_test")
    yield c
    c.close()


@pytest.fixture()
def escenario(conn):
    """BD recién recreada + las cuentas/perfiles/likes del docstring. Devuelve los ids."""
    bd_prueba.preparar_bd(conn)
    cur = conn.cursor()

    def cuenta(correo):
        # Los campos cifrados no importan aquí: se guarda un blob de prueba
        cur.execute("INSERT INTO cuentas (correo, contrasena_hash, nombre_cifrado, fecha_nac_cifrada) "
                    "VALUES (%s, 'x', %s, %s)", (correo, b"\x01prueba", b"\x01prueba"))
        return cur.lastrowid

    def perfil(cuenta_id, nombre, likes):
        cur.execute("INSERT INTO perfiles (cuenta_id, nombre) VALUES (%s, %s)", (cuenta_id, nombre))
        pid = cur.lastrowid
        for doc in likes:
            cur.execute("INSERT INTO interacciones (perfil_id, doc_id, origen) VALUES (%s, %s, 'ejercicios')",
                        (pid, doc))
        return pid

    c1 = cuenta("uno@prueba.test")
    c2 = cuenta("dos@prueba.test")
    ids = {
        "cuenta1": c1, "cuenta2": c2,
        "pecho": perfil(c1, "Pecho", [101, 102]),
        "pierna": perfil(c1, "Pierna", [201, 202]),
        "vacio": perfil(c1, "Vacío", []),
        "otro": perfil(c2, "Otro", [101, 102, 103]),
    }
    conn.commit()
    cur.close()
    return ids


def docs(resultado):
    return {(r["origen"], r["doc_id"]) for r in resultado.get("recomendaciones", [])}


# --------------------------------------------------------------------------- guardas

def test_las_pruebas_solo_usan_la_bd_de_pruebas(conn):
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    nombre = cur.fetchone()[0]
    cur.close()
    assert nombre.endswith("_test")
    assert nombre != bd_prueba._nombre_bd_real()


def test_preparar_bd_se_niega_fuera_de_una_bd_test():
    class CursorFalso:
        def execute(self, sql, *a):
            self.ultimo = sql

        def fetchone(self):
            return ("gym_buscador",)

    class ConexionFalsa:
        def cursor(self):
            return CursorFalso()

    with pytest.raises(bd_prueba.BDNoEsDePrueba):
        bd_prueba.preparar_bd(ConexionFalsa())


# --------------------------------------------------------------------------- aislamiento

def test_dos_perfiles_de_la_misma_cuenta_obtienen_recomendaciones_distintas(conn, escenario):
    pecho = recomendar(conn, escenario["pecho"])
    pierna = recomendar(conn, escenario["pierna"])

    assert pecho["status"] == pierna["status"] == "success"
    assert docs(pecho) and docs(pierna)
    assert docs(pecho).isdisjoint(docs(pierna)), "los perfiles comparten recomendaciones"
    # Cada uno solo recibe documentos de su propio universo
    assert docs(pecho) <= PECHO
    assert docs(pierna) <= PIERNA
    # Y su perfil semántico refleja solo su historial
    assert {"pech", "banc", "press"} <= set(pecho["perfil_semantico"])
    assert {"sentadill", "cuadricep"} <= set(pierna["perfil_semantico"])
    assert not {"sentadill", "cuadricep", "piern", "zancad"} & set(pecho["perfil_semantico"])


def test_perfil_sin_likes_es_cold_start_aunque_sus_hermanos_tengan_historial(conn, escenario):
    assert recomendar(conn, escenario["vacio"])["status"] == "cold_start"


def test_un_like_en_un_perfil_no_cambia_las_recomendaciones_de_otro(conn, escenario):
    antes = recomendar(conn, escenario["pierna"])
    cur = conn.cursor()
    cur.execute("INSERT INTO interacciones (perfil_id, doc_id, origen) VALUES (%s, 104, 'ejercicios'),"
                " (%s, 105, 'ejercicios')", (escenario["pecho"], escenario["pecho"]))
    conn.commit()
    cur.close()
    assert recomendar(conn, escenario["pierna"]) == antes


def test_perfil_de_otra_cuenta_con_gustos_parecidos_no_influye(conn, escenario):
    # "Otro" (cuenta 2) ya dio like a 103; si su historial se filtrara, 103 desaparecería
    # de las recomendaciones de "Pecho" (regla de agotamiento). Debe seguir ahí.
    assert ("ejercicios", 103) in docs(recomendar(conn, escenario["pecho"]))


def test_excluye_lo_que_el_propio_perfil_ya_vio(conn, escenario):
    assert not docs(recomendar(conn, escenario["pecho"])) & {("ejercicios", 101), ("ejercicios", 102)}


def test_ninguna_consulta_lee_interacciones_sin_filtrar_por_el_perfil(conn, escenario):
    """Espía cada SQL que ejecuta el recomendador: toda lectura de `interacciones`
    debe filtrar por perfil_id con parámetro, y el parámetro debe ser el perfil pedido."""
    ejecutadas = []

    class CursorEspia:
        def __init__(self, real):
            self._real = real

        def execute(self, sql, params=None):
            ejecutadas.append((sql, params))
            return self._real.execute(sql, params)

        def __getattr__(self, nombre):
            return getattr(self._real, nombre)

    class ConexionEspia:
        def cursor(self, **kw):
            return CursorEspia(conn.cursor(**kw))

    perfil = escenario["pecho"]
    recomendar(ConexionEspia(), perfil)

    con_interacciones = [(s, p) for s, p in ejecutadas if "interacciones" in s.lower()]
    assert con_interacciones, "el recomendador debería leer el historial"
    for sql, params in con_interacciones:
        assert re.search(r"perfil_id\s*=\s*%s", sql), f"consulta sin filtro de perfil: {sql}"
        assert params == (perfil,), f"parámetros inesperados: {params}"
    # Sin SQL armado con valores: ningún literal numérico de perfil ni f-string de docs
    assert not any(re.search(r"doc_id\s*=\s*\d", s) for s, _ in ejecutadas)


@pytest.mark.parametrize("malo", [0, -1, "1", "1 OR 1=1", None, True, 1.0])
def test_perfil_id_invalido_se_rechaza(conn, malo):
    with pytest.raises(ValueError):
        recomendar(conn, malo)


# --------------------------------------------------------------------------- borrado en cascada

def contar(conn, sql, params):
    cur = conn.cursor()
    cur.execute(sql, params)
    n = cur.fetchone()[0]
    cur.close()
    return n


def test_eliminar_un_perfil_borra_su_historial_y_no_el_de_los_demas(conn, escenario):
    cur = conn.cursor()
    cur.execute("DELETE FROM perfiles WHERE id = %s", (escenario["pecho"],))
    conn.commit()
    cur.close()
    assert contar(conn, "SELECT COUNT(*) FROM interacciones WHERE perfil_id = %s", (escenario["pecho"],)) == 0
    assert contar(conn, "SELECT COUNT(*) FROM interacciones WHERE perfil_id = %s", (escenario["pierna"],)) == 2
    assert contar(conn, "SELECT COUNT(*) FROM interacciones WHERE perfil_id = %s", (escenario["otro"],)) == 3
    assert recomendar(conn, escenario["pecho"])["status"] == "cold_start"


def test_eliminar_la_cuenta_borra_perfiles_e_historial(conn, escenario):
    cur = conn.cursor()
    cur.execute("DELETE FROM cuentas WHERE id = %s", (escenario["cuenta1"],))
    conn.commit()
    cur.close()
    assert contar(conn, "SELECT COUNT(*) FROM perfiles WHERE cuenta_id = %s", (escenario["cuenta1"],)) == 0
    assert contar(conn, "SELECT COUNT(*) FROM interacciones WHERE perfil_id IN (%s, %s, %s)",
                  (escenario["pecho"], escenario["pierna"], escenario["vacio"])) == 0
    # La otra cuenta queda intacta
    assert contar(conn, "SELECT COUNT(*) FROM interacciones WHERE perfil_id = %s", (escenario["otro"],)) == 3


def test_no_se_pueden_crear_mas_de_cuatro_perfiles(conn, escenario):
    cur = conn.cursor()
    cur.execute("INSERT INTO perfiles (cuenta_id, nombre) VALUES (%s, 'Cuarto')", (escenario["cuenta1"],))
    with pytest.raises(Exception, match="4 perfiles"):
        cur.execute("INSERT INTO perfiles (cuenta_id, nombre) VALUES (%s, 'Quinto')", (escenario["cuenta1"],))
    conn.rollback()
    cur.close()
