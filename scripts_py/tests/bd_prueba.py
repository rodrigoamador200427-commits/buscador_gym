"""Base de datos de PRUEBAS (gym_buscador_test): guardas y preparación.

Nunca puede tocar la base real. Hay tres barreras:
  1. Fuerza BUSCADOR_ENTORNO=pruebas, así db_config carga config.test.ini.php,
     que a su vez exige entorno=pruebas y un nombre de BD terminado en _test.
  2. Comprueba con SELECT DATABASE() que la BD conectada termine en _test.
  3. Comprueba que no sea la misma BD que config.local.ini.php (la real).

Uso desde la línea de comandos (lo usa también tests/test_autorizacion.php):
    python scripts_py/tests/bd_prueba.py      -> borra y vuelve a crear la BD de pruebas
"""
import os
import sys

os.environ["BUSCADOR_ENTORNO"] = "pruebas"

AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_PY = os.path.dirname(AQUI)
RAIZ = os.path.dirname(SCRIPTS_PY)
if SCRIPTS_PY not in sys.path:
    sys.path.insert(0, SCRIPTS_PY)

import db_config  # noqa: E402

TABLAS = ["interacciones", "intentos_login", "perfiles", "cuentas",
          "postings", "diccionario", "ejercicios", "articulos"]


class BDNoEsDePrueba(RuntimeError):
    pass


def _nombre_bd_real():
    previo = os.environ.pop("BUSCADOR_ENTORNO", None)
    try:
        return db_config.cargar_config()["nombre"]
    except Exception:
        return None
    finally:
        os.environ["BUSCADOR_ENTORNO"] = previo or "pruebas"


def conectar_prueba():
    """Conexión a la BD de pruebas, o una excepción si hay cualquier duda."""
    os.environ["BUSCADOR_ENTORNO"] = "pruebas"
    nombre = db_config.cargar_config()["nombre"]          # ya valida entorno y sufijo _test
    if not nombre.endswith("_test") or nombre == _nombre_bd_real():
        raise BDNoEsDePrueba(f"Me niego a usar la BD '{nombre}'")
    conn = db_config.get_connection()
    if conn is None:
        return None
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    conectada = cur.fetchone()[0]
    cur.close()
    if not conectada or not conectada.endswith("_test"):
        conn.close()
        raise BDNoEsDePrueba(f"La conexión apunta a '{conectada}', no a una BD _test")
    return conn


def ejecutar_script_sql(cur, texto):
    """Ejecuta un .sql con soporte de DELIMITER (como el cliente mysql)."""
    delim, buf = ";", []
    for linea in texto.splitlines():
        s = linea.strip()
        if not s or s.startswith("--"):
            continue
        if s.upper().startswith("DELIMITER "):
            delim = s.split(None, 1)[1]
            continue
        buf.append(linea)
        if s.endswith(delim):
            sentencia = "\n".join(buf).rstrip()[: -len(delim)]
            buf = []
            if sentencia.strip():
                cur.execute(sentencia)
                if cur.with_rows:
                    cur.fetchall()


def preparar_bd(conn):
    """Borra todo en la BD de pruebas y la recrea: contenido sintético + esquema de cuentas."""
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    if not cur.fetchone()[0].endswith("_test"):           # última barrera antes de borrar nada
        raise BDNoEsDePrueba("preparar_bd solo corre sobre una BD _test")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in TABLAS:
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")          # nombres fijos, no vienen de fuera
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    with open(os.path.join(AQUI, "fixtures", "contenido_test.sql"), encoding="utf-8") as f:
        ejecutar_script_sql(cur, f.read())
    with open(os.path.join(RAIZ, "sql", "esquema_cuentas.sql"), encoding="utf-8") as f:
        ejecutar_script_sql(cur, f.read())
    conn.commit()
    cur.close()


if __name__ == "__main__":
    c = conectar_prueba()
    if c is None:
        print("ERROR: no hay conexión con la BD de pruebas", file=sys.stderr)
        sys.exit(1)
    preparar_bd(c)
    c.close()
    print("BD de pruebas lista")
