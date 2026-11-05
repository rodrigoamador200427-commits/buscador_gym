"""Entrada ÚNICA para PHP: una consulta -> JSON con raíces, descubrimiento y traza.

    python scripts_py/motor_arboles.py "ganar fuerza"

Hace en un solo proceso lo que antes eran dos shell_exec (stem_query.py y motor_grafos.py).
Imprime SOLO JSON por stdout.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    consulta = " ".join(sys.argv[1:]).strip()

    from db_config import get_connection
    from nlp_processor import stemmer, stop_words
    from stem_query import THESAURUS, strip_vowels
    from arboles import construir_aristas, construir_arbol_anatomia, construir_arbol_temas
    from arboles.consulta import raices_de, recuperar
    from arboles.fuentes import articulos_desde_mysql, ejercicios_desde_mysql
    from arboles.motor import MotorArboles
    from arboles.taxonomia import PALABRAS_INTENCION

    con = get_connection()
    if not con:
        print(json.dumps({"status": "error", "mensaje": "Sin conexión a MySQL"}))
        return

    ejercicios, articulos = ejercicios_desde_mysql(con), articulos_desde_mysql(con)
    anatomia, temas = construir_arbol_anatomia(ejercicios), construir_arbol_temas(articulos)
    motor = MotorArboles(anatomia, temas, construir_aristas(articulos, anatomia, temas), stemmer.stem)

    cur = con.cursor(dictionary=True)
    cur.execute("SELECT termino FROM diccionario")
    vocabulario = {f["termino"] for f in cur.fetchall()}

    raices = raices_de(consulta, vocabulario, stemmer, set(stop_words) | PALABRAS_INTENCION,
                       THESAURUS, strip_vowels)
    prep = motor.preparar_consulta(raices)          # qué raíces se usan para recuperar
    descubrimiento = motor.descubrir(raices, recuperar(cur, prep["raices"]))
    descubrimiento["traza"]["consulta_preparada"] = prep
    cur.close()
    con.close()

    # ensure_ascii=True (por defecto): solo ASCII, así PHP lo decodifica sin importar la
    # codificación de consola de Windows (cp1252 vs UTF-8).
    print(json.dumps({"status": "success", "raices": prep["raices"], "raices_consulta": raices, "descubrimiento": descubrimiento}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # PHP necesita SIEMPRE un JSON válido
        print(json.dumps({"status": "error", "mensaje": f"{type(e).__name__}: {e}"}))
