"""Recomendador por perfil: centroide TF-IDF de los likes del perfil + similitud del coseno.

Uso (lo llama recomendaciones.php con el perfil activo de la sesión):
    python scripts_py/recommender.py <perfil_id>

AISLAMIENTO: la ÚNICA consulta que toca `interacciones` filtra por
`perfil_id = %s` (consulta preparada). El centroide no se guarda: se recalcula
en cada petición solo con el historial de ese perfil, así que otro perfil, aunque
sea de la misma cuenta, no puede influir en el resultado. PHP ya verificó que el
perfil pertenece a la cuenta de la sesión. Este script no confía en nada más que
un entero positivo.
"""
import json
import math
import re
import sys
from collections import defaultdict

UMBRAL_SIMILITUD = 0.05      # similitud mínima del 5 %
TOP_TERMINOS_PERFIL = 8
_ACENTOS = str.maketrans("áéíóúüñ", "aeiouun")


def palabras_visibles(cursor, vistos, raices):
    """{raíz: palabra completa} para mostrar el perfil ('pech' -> 'pecho').

    Toma la palabra más frecuente que produce esa raíz en el texto de los documentos con
    like del perfil (los mismos que formaron el centroide). Lee solo tablas de contenido.
    Misma normalización que nlp_processor.clean_and_stem.
    """
    from nlp_processor import stemmer
    buscadas = set(raices)
    textos = []
    for origen, tabla, cols in (("ejercicios", "ejercicios", "nombre_es, descripcion_es"),
                                ("articulos", "articulos", "titulo, contenido")):
        ids = sorted(d for d, o in vistos if o == origen)
        if ids:
            cursor.execute(f"SELECT {cols} FROM {tabla} WHERE id IN ({','.join(['%s'] * len(ids))})",
                           tuple(ids))                      # tabla y columnas fijas; ids con %s
            for fila in cursor.fetchall():
                textos.extend(str(v or "") for v in fila.values())
    cuenta = defaultdict(lambda: defaultdict(int))
    for texto in textos:
        for palabra in re.findall(r"[a-záéíóúüñ]+", texto.lower()):
            base = re.sub(r"[^a-z]", "", palabra.translate(_ACENTOS))
            if len(base) > 2:
                raiz = stemmer.stem(base)
                if raiz in buscadas:
                    cuenta[raiz][palabra] += 1
    return {r: sorted(c.items(), key=lambda x: (-x[1], x[0]))[0][0] for r, c in cuenta.items()}


def magnitude(vector):
    """Calcula la longitud geométrica del vector."""
    return math.sqrt(sum(val ** 2 for val in vector.values()))


def historial_perfil(cursor, perfil_id):
    """Documentos con like de ESTE perfil. Única lectura de `interacciones`."""
    cursor.execute(
        "SELECT doc_id, origen FROM interacciones "
        "WHERE perfil_id = %s AND interaccion = 'like'",
        (perfil_id,),
    )
    return {(r["doc_id"], r["origen"]) for r in cursor.fetchall()}


def centroide_perfil(cursor, perfil_id, num_likes):
    """Vector U = promedio de los vectores TF-IDF de los documentos con like del perfil.

    Un JOIN preparado sustituye a la condición SQL que antes se armaba con f-string
    (doc_id = .. AND origen = '..'), que permitía inyección SQL de segundo orden.
    """
    cursor.execute(
        "SELECT p.termino_id, p.peso_tfidf "
        "FROM interacciones i "
        "JOIN postings p ON p.doc_id = i.doc_id AND p.origen = i.origen "
        "WHERE i.perfil_id = %s AND i.interaccion = 'like'",
        (perfil_id,),
    )
    u = defaultdict(float)
    for row in cursor.fetchall():
        u[row["termino_id"]] += row["peso_tfidf"]
    for t in u:
        u[t] /= num_likes
    return u


def recomendar(conn, perfil_id, limit=10):
    """Devuelve el dict de respuesta (status success | cold_start) para `perfil_id`."""
    if not isinstance(perfil_id, int) or isinstance(perfil_id, bool) or perfil_id <= 0:
        raise ValueError("perfil_id debe ser un entero positivo")

    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Historial del perfil (Cold Start si no hay likes)
        vistos = historial_perfil(cursor, perfil_id)
        if not vistos:
            return {"status": "cold_start", "mensaje": "Dale like a algunos ejercicios para conocerte."}

        # 2. Vector de perfil U (centroide), solo con datos de este perfil
        user_vector = centroide_perfil(cursor, perfil_id, len(vistos))

        # Top raíces para "Tu Perfil Semántico" (solo los términos del perfil, no todo el diccionario)
        top = sorted(user_vector.items(), key=lambda x: x[1], reverse=True)[:TOP_TERMINOS_PERFIL]
        perfil_semantico, nombres = [], {}
        if top:
            ids = [t for t, _ in top]
            cursor.execute(
                "SELECT id, termino FROM diccionario WHERE id IN (%s)" % ",".join(["%s"] * len(ids)),
                tuple(ids),
            )
            nombres = {r["id"]: r["termino"] for r in cursor.fetchall()}
            perfil_semantico = [nombres[t] for t in ids if t in nombres]
        # Para la gráfica: raíz, palabra completa y peso en el centroide, de mayor a menor
        visibles = palabras_visibles(cursor, vistos, perfil_semantico)
        perfil_terminos = [{"termino": nombres[t], "palabra": visibles.get(nombres[t], nombres[t]),
                            "peso": round(p, 4)} for t, p in top if t in nombres]

        # 3. Vectores de documentos D no vistos (postings es contenido público, no del usuario)
        cursor.execute("SELECT doc_id, origen, termino_id, peso_tfidf FROM postings")
        candidates = defaultdict(dict)
        for row in cursor.fetchall():
            doc_key = (row["doc_id"], row["origen"])
            if doc_key not in vistos:          # Regla de agotamiento
                candidates[doc_key][row["termino_id"]] = row["peso_tfidf"]
    finally:
        cursor.close()

    # 4. Similitud del coseno: (U · D) / (|U| |D|)
    scores = []
    user_mag = magnitude(user_vector)
    user_terms = set(user_vector)
    for doc_key, doc_vector in candidates.items():
        common_terms = user_terms & doc_vector.keys()
        if not common_terms:
            continue                            # sin términos comunes: coseno 0
        dot_product = sum(user_vector[t] * doc_vector[t] for t in common_terms)
        doc_mag = magnitude(doc_vector)
        if doc_mag > 0 and user_mag > 0:
            similitud = dot_product / (user_mag * doc_mag)
            if similitud > UMBRAL_SIMILITUD:
                scores.append({"doc_id": doc_key[0], "origen": doc_key[1], "similitud": round(similitud, 4)})

    # 5. Orden determinista: similitud desc y, en empate, por documento
    scores.sort(key=lambda x: (-x["similitud"], x["origen"], x["doc_id"]))
    return {"status": "success", "perfil_semantico": perfil_semantico, "perfil_terminos": perfil_terminos,
            "recomendaciones": scores[:limit]}


def main(argv):
    if len(argv) != 2 or not argv[1].isdigit() or int(argv[1]) <= 0:
        print(json.dumps({"status": "error", "mensaje": "uso: recommender.py <perfil_id>"}))
        return 2
    from db_config import get_connection
    conn = get_connection()
    if not conn:
        print(json.dumps({"status": "error", "mensaje": "Sin conexión a la BD"}))
        return 1
    try:
        print(json.dumps(recomendar(conn, int(argv[1]))))
        return 0
    except Exception as e:   # PHP necesita SIEMPRE un JSON válido; sin detalles (solo el tipo)
        print(json.dumps({"status": "error", "mensaje": f"fallo interno ({type(e).__name__})"}))
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
