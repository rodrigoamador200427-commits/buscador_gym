"""Procesamiento de la consulta y recuperación TF-IDF, como funciones puras.

`raices_de` reproduce la lógica de stem_query.py (tesauro -> raíz -> corrección por
esqueleto de consonantes) con TRES diferencias deliberadas:
  1. Normaliza igual que el indexador (nlp_processor): ñ->n y ü->u. stem_query.py borraba
     la ñ ("muñeca" -> "mueca") y no coincidía con el índice ("munec").
  2. Recorre el vocabulario en orden alfabético, así que el mapa de esqueletos es el
     mismo en cada ejecución (con `set` el ganador de una colisión cambiaba entre corridas).
  3. Conserva el orden de aparición de las raíces y no repite ninguna.
"""
import re

_REEMPLAZOS = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n"))


def normalizar_consulta(texto):
    texto = texto.lower()
    for a, b in _REEMPLAZOS:
        texto = texto.replace(a, b)
    return re.sub(r"[^a-z\s]", "", texto)


def raices_de(consulta, vocabulario, stemmer, stop_words, tesauro, esqueleto):
    """-> lista de raíces (sin repetir, en orden). `esqueleto` = strip_vowels de stem_query."""
    mapa = {}
    for termino in sorted(vocabulario):
        mapa.setdefault(esqueleto(termino), termino)

    raices = []
    for palabra in normalizar_consulta(consulta).split():
        if palabra in stop_words or len(palabra) < 2:
            continue
        palabra = tesauro.get(palabra, palabra)
        raiz = stemmer.stem(palabra)
        if raiz not in vocabulario:
            raiz = mapa.get(esqueleto(palabra), raiz)
        raices.append(raiz)
    return list(dict.fromkeys(raices))


def recuperar(cursor, raices, limite=50):
    """Mismo cálculo que buscar.php (suma de pesos TF-IDF por documento) -> [(origen, doc_id, score)]."""
    if not raices:
        return []
    marcas = ",".join(["%s"] * len(raices))
    cursor.execute(
        f"""SELECT p.origen, p.doc_id, SUM(p.peso_tfidf) AS score
            FROM diccionario d JOIN postings p ON d.id = p.termino_id
            WHERE d.termino IN ({marcas})
            GROUP BY p.origen, p.doc_id
            ORDER BY score DESC, p.doc_id ASC
            LIMIT {int(limite)}""",
        list(raices),
    )
    return [(f["origen"], int(f["doc_id"]), float(f["score"])) for f in cursor.fetchall()]
