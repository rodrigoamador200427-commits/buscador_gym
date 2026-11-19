"""Mide por fases lo que hace motor_arboles.py en cada búsqueda (fase 7, rendimiento).

    python scripts_py/perfil_motor.py

Solo LEE la BD configurada (la real si no hay BUSCADOR_ENTORNO=pruebas). No escribe nada.
Sirve para ver dónde se va el tiempo de un proceso de Python: importar NLTK, construir los
árboles o consultar. Los números dependen de la máquina; el reparto, no.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
T0 = time.perf_counter()
marcas = []


def marca(nombre):
    marcas.append((nombre, time.perf_counter()))


def reporte():
    ant = T0
    for nombre, t in marcas:
        print(f"  {nombre:60} {t - ant:6.2f} s")
        ant = t
    print(f"  {'TOTAL':60} {marcas[-1][1] - T0:6.2f} s")


import nltk                                         # noqa: E402
marca("import nltk (arrastra scipy.stats y otros módulos)")
from nltk.corpus import stopwords                    # noqa: E402
from nltk.stem.snowball import SnowballStemmer       # noqa: E402
nltk.download("stopwords", quiet=True)               # lo que hace nlp_processor.py en cada importación
marca("nltk.download('stopwords'): una petición de red")
stop = set(stopwords.words("spanish"))
stemmer = SnowballStemmer("spanish")
marca("cargar stopwords y crear el stemmer")

from db_config import get_connection                 # noqa: E402
from stem_query import THESAURUS, strip_vowels       # noqa: E402
from arboles import Bosque                           # noqa: E402
from arboles.consulta import raices_de, recuperar    # noqa: E402
from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql  # noqa: E402
from arboles.motor import MotorArboles               # noqa: E402
from arboles.taxonomia import PALABRAS_INTENCION     # noqa: E402
marca("importar el resto del proyecto")

con = get_connection()
marca("conectar a MariaDB")
ej = ejercicios_desde_mysql(con)
ar = articulos_desde_mysql(con)
marca(f"leer {len(ej)} ejercicios y {len(ar)} artículos")
bosque = Bosque.construir(ej, ar)
marca("Bosque.construir (5 árboles y las aristas de 10 pares)")
motor = MotorArboles.desde_bosque(bosque, stemmer.stem)
cur = con.cursor(dictionary=True)
cur.execute("SELECT termino FROM diccionario")
vocab = {f["termino"] for f in cur.fetchall()}
marca(f"leer el diccionario ({len(vocab)} términos)")
for q in ("pecho mancuernas principiante", "creatina"):
    raices = raices_de(q, vocab, stemmer, stop | PALABRAS_INTENCION, THESAURUS, strip_vowels)
    prep = motor.preparar_consulta(raices)
    docs = recuperar(cur, prep["raices"])
    marca(f"«{q}»: raíces y recuperación TF-IDF ({len(docs)} documentos)")
    motor.descubrir(raices, docs)
    marca(f"«{q}»: descubrimiento en los árboles")
reporte()
