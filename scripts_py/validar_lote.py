"""Valida un lote de artículos generados ANTES de importarlo (fase 6A).

    python scripts_py/validar_lote.py corpus/lotes/lote_01.csv
    python scripts_py/validar_lote.py corpus/lotes/lote_01.csv --plan corpus/lotes/lote_01.plan.csv

Lee de la BD (solo SELECT) los artículos y ejercicios existentes. Sale con 0 si no hay errores
(los avisos no bloquean) y con 1 si hay alguno. Con BUSCADOR_ENTORNO=pruebas usa gym_buscador_test.

Errores (bloquean la importación):
  - encabezado distinto de titulo, contenido, etiquetas; campos vacíos; caracteres raros;
  - título repetido (en el lote o en la BD, sin distinguir mayúsculas ni acentos) o fuera de 3 a 10 palabras;
  - contenido fuera de 38 a 56 palabras o de 2 a 4 frases;
  - 6 o 7 etiquetas, sin repetir y TODAS dentro del vocabulario controlado (taxonomia.py);
  - texto que no parece español;
  - similitud del coseno mayor a 0,8 con otro artículo del lote o con uno existente;
  - cantidades con unidad (g, mg, ml, kg, kcal, %, grados), años, plazos de resultados y palabras de
    salud, estudios o promesas (dosis, tratamiento, estudio, garantiza...);
  - mencionar un ejercicio del que la tabla `ejercicios` tiene menos de 5 registros;
  - un artículo de técnica, fuerza o hipertrofia de un músculo que no nombra ninguna de las familias de
    ejercicio que la tabla sí tiene para ese músculo;
  - con --plan: que el tema principal o el músculo que resultan de las etiquetas no sean los previstos.
Avisos (se reportan, no bloquean): similitud entre 0,6 y 0,8, cualquier cifra suelta y palabras absolutas.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)

from arboles import taxonomia as T          # noqa: E402
from etiquetado import clave, vocabulario_controlado  # noqa: E402

COLUMNAS = ["titulo", "contenido", "etiquetas"]
PALABRAS = (38, 56)             # los 341 originales miden de 39 a 53
TITULO_PALABRAS = (3, 10)
FRASES = (2, 4)
ETIQUETAS = (6, 7)
SIMILITUD_RECHAZO = 0.8
SIMILITUD_REVISION = 0.6
MIN_EJERCICIOS_FAMILIA = 5
ESPANOL_MIN = 0.25              # proporción mínima de palabras vacías en español (originales: 0,28 a 0,5)
INGLES_MAX = 0.03
TEMAS_CON_EJERCICIO = {"Técnica y biomecánica", "Fuerza", "Hipertrofia"}

# ---------------------------------------------------------------------------
# Ejercicios: (clave, regex sobre el texto sin acentos, patrones LIKE de la tabla)
# Los LIKE no llevan acentos: la tabla usa una colación que no los distingue.
# ---------------------------------------------------------------------------
FAMILIAS = [
    ("press de banca", r"press (?:de |en )?banca", ["%press de banca%"]),
    ("flexiones", r"\bflexiones\b|flexion de brazos", ["%flexiones%", "%flexion de brazos%"]),
    ("aperturas", r"\baperturas?\b", ["%apertura%"]),
    ("cruce de cables", r"cruces? de (?:cables|poleas)", ["%cruce de cables%"]),
    ("remo", r"\bremos?\b", ["remo %", "% remo %"]),
    ("jalon", r"\bjalon(?:es)?\b", ["%jalon%"]),
    ("dominadas", r"\bdominadas?\b", ["%dominada%"]),
    ("peso muerto", r"peso muerto", ["%peso muerto%"]),
    ("peso muerto rumano", r"peso muerto rumano", ["%peso muerto rumano%"]),
    ("press de hombros", r"press (?:de hombros?|militar|sobre (?:la )?cabeza)", ["%press de hombro%", "%press militar%"]),
    ("elevaciones laterales", r"elevacion(?:es)? laterales?", ["%elevacion lateral%", "%elevaciones laterales%"]),
    ("elevaciones frontales", r"elevacion(?:es)? frontales?", ["%elevacion frontal%", "%elevaciones frontales%"]),
    ("encogimientos", r"\bencogimientos?\b", ["%encogimiento%"]),
    ("curl", r"\bcurls?\b", ["%curl%"]),
    ("flexion de piernas", r"curl (?:femoral|de pierna)|flexion(?:es)? de piernas?|flexion de isquiotibiales",
     ["%flexion de pierna%", "%flexion de isquiotibiales%"]),
    ("extension de triceps", r"extension(?:es)? de triceps", ["%extension de triceps%", "%extensiones de triceps%"]),
    ("fondos", r"\bfondos\b", ["%fondos%"]),
    ("sentadilla", r"\bsentadillas?\b", ["%sentadilla%"]),
    ("zancada", r"\bzancadas?\b", ["%zancada%"]),
    ("prensa de piernas", r"prensa de piernas", ["%prensa de piernas%"]),
    ("puente de gluteos", r"puentes? de gluteos?", ["%puente de gluteo%"]),
    ("elevacion de cadera", r"(?:elevacion(?:es)?|empuje) de cadera", ["%elevacion de cadera%", "%empuje de cadera%"]),
    ("elevacion de pantorrillas", r"elevacion(?:es)? de pantorrillas?", ["%elevacion de pantorrilla%", "%elevaciones de pantorrilla%"]),
    ("plancha", r"\bplanchas?\b", ["%plancha%"]),
    ("abdominales", r"\babdominales\b", ["%abdominales%"]),
    ("crunch", r"\bcrunch(?:es)?\b", ["%crunch%"]),
    ("elevacion de piernas", r"elevacion(?:es)? de piernas?", ["%elevacion de pierna%"]),
    ("escalador", r"escaladores?", ["%escalador%"]),
    ("flexion de muneca", r"(?:flexion(?:es)?|curl(?:s)?) de muneca", ["%flexion de muneca%", "%curl de muneca%"]),
    # --- ejercicios conocidos que la tabla NO tiene (o tiene menos de 5): mencionarlos es un error
    ("hip thrust", r"hip thrust", ["%hip thrust%"]),
    ("face pull", r"face pull", ["%face pull%"]),
    ("pajaros", r"\bpajaros\b", ["%pajaros%"]),
    ("pullover", r"pull ?over", ["%pull over%", "%pullover%"]),
    ("good morning", r"good morning", ["%good morning%", "%buenos dias%"]),
    ("paseo del granjero", r"paseo del (?:granjero|agricultor)", ["%paseo del granjero%", "%paseo del agricultor%"]),
    ("sentadilla bulgara", r"sentadilla bulgara", ["%sentadilla bulgara%"]),
    ("peso muerto sumo", r"peso muerto sumo", ["%peso muerto sumo%"]),
    ("curl de concentracion", r"curl de concentracion", ["%curl de concentracion%"]),
    ("remo al menton", r"remo al menton|remo alto", ["%remo al menton%"]),
    ("press arnold", r"press arnold", ["%arnold%"]),
]
FAMILIAS_POR_MUSCULO = {      # grupo_id -> familias de ejercicio que la tabla sí tiene (>= 5 registros)
    1: ["press de banca", "flexiones", "aperturas", "cruce de cables"],
    2: ["remo", "jalon", "dominadas", "peso muerto"],
    3: ["press de hombros", "elevaciones laterales", "elevaciones frontales", "encogimientos"],
    4: ["curl"],
    5: ["extension de triceps", "fondos"],
    6: ["sentadilla", "zancada", "prensa de piernas"],
    7: ["peso muerto rumano", "flexion de piernas"],
    8: ["elevacion de pantorrillas"],
    9: ["puente de gluteos", "elevacion de cadera", "sentadilla"],
    10: ["plancha", "abdominales", "crunch", "elevacion de piernas", "escalador"],
    11: ["flexion de muneca"],
}

# ---------------------------------------------------------------------------
# Seguridad del contenido (sobre el texto sin acentos y en minúsculas)
# ---------------------------------------------------------------------------
_NUM = r"\d+(?:[.,]\d+)?"
_RANGO = rf"{_NUM}(?:\s*(?:a|-|y)\s*{_NUM})?"
ERRORES_SEGURIDAD = [
    (re.compile(rf"{_RANGO}\s*(?:g|gr|gramos?|mg|miligramos?|mcg|microgramos?|ml|mililitros?|l|litros?|kg|kilos?|kilogramos?|kcal|calorias?|ui|grados?)\b"),
     "cantidad con unidad de masa, volumen, energía o grados"),
    (re.compile(r"\d\s*%|por ciento"), "porcentaje"),
    (re.compile(r"\b(?:19|20)\d{2}\b"), "año (parece una cita)"),
    (re.compile(r"\ben\s+\d+\s+(?:dias|semanas|meses|anos)\b"), "plazo para obtener resultados"),
    (re.compile(r"\bdosis\b"), "dosis"),
    (re.compile(r"\bdiagnostic\w*"), "diagnóstico"),
    (re.compile(r"\btratamientos?\b"), "tratamiento"),
    (re.compile(r"\bmedicament\w*|\bfarmac\w*|\bmedicacion\b"), "medicamentos o fármacos"),
    (re.compile(r"\bcur(?:a|ar|an|acion)\b"), "cura o curar"),
    (re.compile(r"\bgarantiz\w*|\bgarantia\b"), "garantía de resultados"),
    (re.compile(r"\bmilagr\w*"), "promesa milagrosa"),
    (re.compile(r"\bestudios?\b|\binvestigacion(?:es)?\b|\bcientific\w*"), "cita de estudios o ciencia"),
    (re.compile(r"\bdemostrad\w*|\bcomprobad\w*|\bprobad[oa]s?\b|\bevidencia\b"), "afirma que algo está demostrado"),
    (re.compile(r"\benfermedad\w*|\bpatolog\w*|\bsindrome\b|\bterapia\b"), "lenguaje médico"),
]
AVISOS_SEGURIDAD = [
    (re.compile(r"\d"), "contiene una cifra"),
    (re.compile(r"\bsiempre\b|\bnunca\b|\bnadie\b|\bjamas\b|\bimposible\b|\btodos\b"), "palabra absoluta"),
    (re.compile(r"\bsegun\b"), "usa «según»"),
]
CARACTERES_PERMITIDOS = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.,;:¿?¡!()\"'«»\-–—/]+$")
_CARACTER_PERMITIDO = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.,;:¿?¡!()\"'«»\-–—/]")
INGLES = set("the and of to in is are for with that this it as on be by or from at an which you your can may more than when should during while about into not".split())


def normalizar(texto):
    """Minúsculas, sin acentos y con los espacios colapsados."""
    return re.sub(r"\s+", " ", T.normalizar(texto)).strip()


def palabras(texto):
    return re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", texto)


def frases(texto):
    return [f for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f]


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
def leer_lote(ruta):
    """Devuelve (filas, errores_de_formato). Cada fila: {fila, titulo, contenido, etiquetas}."""
    with open(ruta, encoding="utf-8", newline="") as f:
        lector = csv.reader(f)
        try:
            encabezado = next(lector)
        except StopIteration:
            return [], ["el archivo está vacío"]
        if [c.strip().lower() for c in encabezado] != COLUMNAS:
            return [], [f"el encabezado debe ser {COLUMNAS} y es {encabezado}"]
        filas, errores = [], []
        for n, r in enumerate(lector, start=2):
            if len(r) != 3:
                errores.append(f"fila {n}: tiene {len(r)} columnas en vez de 3")
                continue
            filas.append({"fila": n, "titulo": r[0].strip(), "contenido": r[1].strip(), "etiquetas": r[2].strip()})
    return filas, errores


def leer_plan(ruta):
    """CSV titulo,tema,musculo -> {titulo normalizado: (tema, nombre de músculo o '')}."""
    plan = {}
    with open(ruta, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            plan[normalizar(r["titulo"])] = (r["tema"].strip(), r["musculo"].strip())
    return plan


# ---------------------------------------------------------------------------
# Clasificación igual que el árbol de Temas
# ---------------------------------------------------------------------------
def clasificar(etiquetas_texto):
    """(tema principal, [grupo_id de músculo]) a partir de las etiquetas, con las mismas funciones del árbol."""
    tags = T.separar_etiquetas(etiquetas_texto)
    temas = T.temas_del_articulo(tags)
    return (temas[0] if temas else T.SIN_CLASIFICAR), T.musculos_de_etiquetas(tags)


def gid_de_musculo(nombre):
    for gid, n in T.MUSCULOS.items():
        if normalizar(n) == normalizar(nombre):
            return gid
    return None


# ---------------------------------------------------------------------------
# Similitud
# ---------------------------------------------------------------------------
def similitudes(textos_lote, textos_existentes):
    """Matriz (lote x [existentes + lote]) de similitud del coseno con TF-IDF como el indexador
    (mismo preprocesamiento: clean_and_stem sobre título + contenido + etiquetas). La diagonal va en 0."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from nlp_processor import clean_and_stem
    todos = list(textos_existentes) + list(textos_lote)
    X = TfidfVectorizer(analyzer=clean_and_stem).fit_transform(todos)
    n_ex = len(textos_existentes)
    S = (X[n_ex:] @ X.T).toarray()
    for i in range(len(textos_lote)):
        S[i, n_ex + i] = 0.0
    return S, n_ex


# ---------------------------------------------------------------------------
# Validación (sin BD: recibe los datos)
# ---------------------------------------------------------------------------
def validar(lote, existentes, conteo_familias, plan=None, vocabulario=None, ejercicios_min=MIN_EJERCICIOS_FAMILIA):
    """lote, existentes: listas de dict con titulo, contenido, etiquetas.
    conteo_familias: {clave de FAMILIAS: cuántos ejercicios hay en la tabla}.
    Devuelve {errores, avisos, bandas, distribucion, longitudes}."""
    vocabulario = vocabulario or vocabulario_controlado()
    errores, avisos = [], []

    def err(a, msg):
        errores.append({"fila": a["fila"], "titulo": a["titulo"], "mensaje": msg})

    def avi(a, msg):
        avisos.append({"fila": a["fila"], "titulo": a["titulo"], "mensaje": msg})

    titulos_bd = {normalizar(e["titulo"]) for e in existentes}
    vistos = {}
    es_stop = None
    for a in lote:
        t, c = a["titulo"], a["contenido"]
        if not t or not c or not a["etiquetas"]:
            err(a, "título, contenido o etiquetas vacíos")
            continue
        for campo in ("titulo", "contenido", "etiquetas"):
            if not CARACTERES_PERMITIDOS.match(a[campo]):
                raros = sorted(set(_CARACTER_PERMITIDO.sub("", a[campo])))
                err(a, f"{campo}: caracteres no permitidos {raros}")

        # --- título
        nt = normalizar(t)
        if nt in vistos:
            err(a, f"título repetido en el lote (fila {vistos[nt]})")
        vistos.setdefault(nt, a["fila"])
        if nt in titulos_bd:
            err(a, "el título ya existe en la BD")
        if not TITULO_PALABRAS[0] <= len(palabras(t)) <= TITULO_PALABRAS[1]:
            err(a, f"el título tiene {len(palabras(t))} palabras (debe tener de {TITULO_PALABRAS[0]} a {TITULO_PALABRAS[1]})")

        # --- longitud
        n = len(palabras(c))
        if not PALABRAS[0] <= n <= PALABRAS[1]:
            err(a, f"el contenido tiene {n} palabras (debe tener de {PALABRAS[0]} a {PALABRAS[1]})")
        nf = len(frases(c))
        if not FRASES[0] <= nf <= FRASES[1]:
            err(a, f"el contenido tiene {nf} frases (debe tener de {FRASES[0]} a {FRASES[1]})")
        if not c.endswith((".", "!", "?")):
            err(a, "el contenido no termina en un signo de puntuación")

        # --- etiquetas
        tags = [clave(x) for x in T.separar_etiquetas(a["etiquetas"])]
        if not ETIQUETAS[0] <= len(tags) <= ETIQUETAS[1]:
            err(a, f"tiene {len(tags)} etiquetas (debe tener de {ETIQUETAS[0]} a {ETIQUETAS[1]})")
        if len(set(tags)) != len(tags):
            err(a, "etiquetas repetidas")
        fuera = [x for x in tags if x not in vocabulario]
        if fuera:
            err(a, f"etiquetas fuera del vocabulario controlado: {fuera}")

        # --- idioma
        if es_stop is None:
            from nlp_processor import stop_words
            es_stop = {w.lower() for w in stop_words}
        toks = [w.lower() for w in palabras(c)]
        r_es = sum(1 for w in toks if w in es_stop) / max(1, len(toks))
        r_en = sum(1 for w in toks if w in INGLES) / max(1, len(toks))
        if r_es < ESPANOL_MIN or r_en > INGLES_MAX:
            err(a, f"no parece español (palabras vacías en español {r_es:.2f}, en inglés {r_en:.2f})")

        # --- seguridad
        texto = normalizar(t + " " + c)
        for patron, nombre in ERRORES_SEGURIDAD:
            m = patron.search(texto)
            if m:
                err(a, f"{nombre}: «{m.group(0)}»")
        for patron, nombre in AVISOS_SEGURIDAD:
            if patron.search(normalizar(c)):
                avi(a, nombre)

        # --- ejercicios
        mencionadas = [k for k, rx, _ in FAMILIAS if re.search(rx, texto)]
        for k in mencionadas:
            cantidad = conteo_familias.get(k, 0)
            if cantidad < ejercicios_min:
                err(a, f"menciona «{k}», del que la tabla ejercicios tiene {cantidad} registros (mínimo {ejercicios_min})")
        tema, musculos = clasificar(a["etiquetas"])
        a["_tema"], a["_musculos"] = tema, musculos
        if tema in TEMAS_CON_EJERCICIO and musculos:
            permitidas = {k for g in musculos for k in FAMILIAS_POR_MUSCULO.get(g, [])}
            if not (permitidas & set(mencionadas)):
                err(a, f"artículo de {tema} sobre {[T.MUSCULOS[g] for g in musculos]} que no nombra ninguna de sus familias de ejercicio {sorted(permitidas)}")
        if tema == "Suplementación" and re.search(r"\d", c):
            err(a, "un artículo de Suplementación no puede llevar ninguna cifra")

        # --- plan
        if plan is not None:
            previsto = plan.get(nt)
            if previsto is None:
                err(a, "no está en el plan del lote")
            else:
                tema_p, musculo_p = previsto
                gid_p = gid_de_musculo(musculo_p) if musculo_p else None
                if musculo_p and gid_p is None:
                    err(a, f"el plan nombra un músculo desconocido: {musculo_p}")
                esperados = [gid_p] if gid_p else []
                if tema != tema_p:
                    err(a, f"el tema que resulta de las etiquetas es «{tema}» y el plan dice «{tema_p}»")
                if musculos != esperados:
                    err(a, f"los músculos que resultan de las etiquetas son {[T.MUSCULOS[g] for g in musculos]} y el plan dice {[musculo_p] if musculo_p else []}")
    if plan is not None:
        faltan = set(plan) - {normalizar(a["titulo"]) for a in lote}
        for nt in sorted(faltan):
            errores.append({"fila": 0, "titulo": nt, "mensaje": "está en el plan pero no en el lote"})

    # --- similitud (solo con artículos válidos en formato)
    bandas = []
    sim_max = []
    if lote:
        textos_l = [f"{a['titulo']} {a['contenido']} {a['etiquetas']}" for a in lote]
        textos_e = [f"{e['titulo']} {e['contenido']} {e['etiquetas']}" for e in existentes]
        S, n_ex = similitudes(textos_l, textos_e)
        for i, a in enumerate(lote):
            fila = S[i]
            sim_max.append(float(fila.max()) if len(fila) else 0.0)
            for j in range(len(fila)):
                v = float(fila[j])
                if v < SIMILITUD_REVISION or (j >= n_ex and j - n_ex < i):
                    continue                                   # cada par del lote se reporta una vez
                otro = existentes[j] if j < n_ex else lote[j - n_ex]
                par = {"a": a["titulo"], "b": otro["titulo"], "similitud": round(v, 3),
                       "con": "existente" if j < n_ex else "lote"}
                if v > SIMILITUD_RECHAZO:
                    err(a, f"similitud {v:.3f} con «{otro['titulo']}» ({par['con']}): demasiado parecido")
                else:
                    bandas.append(par)
    # --- distribución
    por_tema = Counter(a.get("_tema") for a in lote if "_tema" in a)
    por_musculo = Counter(g for a in lote for g in a.get("_musculos", []))
    sin_musculo = sum(1 for a in lote if "_musculos" in a and not a["_musculos"])
    longitudes = [len(palabras(a["contenido"])) for a in lote]
    return {"errores": errores, "avisos": avisos, "bandas": sorted(bandas, key=lambda p: -p["similitud"]),
            "similitud_max": sim_max, "por_tema": dict(por_tema), "por_musculo": dict(por_musculo),
            "sin_musculo": sin_musculo, "longitudes": longitudes}


# ---------------------------------------------------------------------------
# BD (solo lectura)
# ---------------------------------------------------------------------------
def leer_existentes(cursor):
    cursor.execute("SELECT titulo, contenido, etiquetas FROM articulos ORDER BY id")
    return [{"titulo": r["titulo"], "contenido": r["contenido"], "etiquetas": r["etiquetas"] or ""} for r in cursor.fetchall()]


def contar_familias(cursor):
    """{clave: cuántos ejercicios tienen esa familia en el nombre}. Consultas preparadas."""
    conteo = {}
    for k, _, likes in FAMILIAS:
        donde = " OR ".join(["nombre_es LIKE %s"] * len(likes))
        cursor.execute(f"SELECT COUNT(*) AS n FROM ejercicios WHERE {donde}", tuple(likes))   # donde se arma con %s fijos
        conteo[k] = int(cursor.fetchone()["n"])
    return conteo


def distribucion_acumulada(existentes_con_etiquetas):
    por_tema, por_musculo = Counter(), Counter()
    for e in existentes_con_etiquetas:
        tema, musculos = clasificar(e["etiquetas"])
        por_tema[tema] += 1
        for g in musculos:
            por_musculo[g] += 1
    return por_tema, por_musculo


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------
def informe(res, lote, existentes, objetivos=None, salida=print):
    p = salida
    nl = len(lote)
    p(f"\nLOTE: {nl} artículos | errores: {len(res['errores'])} | avisos: {len(res['avisos'])} | pares entre {SIMILITUD_REVISION} y {SIMILITUD_RECHAZO}: {len(res['bandas'])}")
    if res["longitudes"]:
        L = res["longitudes"]
        p(f"longitud (palabras): mín {min(L)} | media {sum(L) / len(L):.1f} | máx {max(L)}")
        sm = res["similitud_max"]
        p(f"similitud con su vecino más parecido: media {sum(sm) / len(sm):.3f} | máx {max(sm):.3f}")
    if res["errores"]:
        p("\nERRORES")
        for e in res["errores"][:60]:
            p(f"  fila {e['fila']:>3} «{e['titulo'][:50]}»: {e['mensaje']}")
        if len(res["errores"]) > 60:
            p(f"  ... y {len(res['errores']) - 60} más")
    if res["avisos"]:
        cuenta = Counter(a["mensaje"] for a in res["avisos"])
        p("\nAVISOS (no bloquean): " + "; ".join(f"{k}: {v}" for k, v in cuenta.items()))
    if res["bandas"]:
        p(f"\nPARES PARECIDOS ({SIMILITUD_REVISION} a {SIMILITUD_RECHAZO}) para revisar:")
        for b in res["bandas"][:15]:
            p(f"  {b['similitud']:.3f}  «{b['a'][:45]}» / «{b['b'][:45]}» ({b['con']})")
    acum_t, acum_m = distribucion_acumulada(existentes + [dict(l) for l in lote])
    p("\nDISTRIBUCIÓN POR TEMA (tema principal que resulta de las etiquetas)")
    p(f"  {'tema':26s} {'lote':>5s} {'acumulado':>10s} {'meta final':>11s} {'avance':>7s}")
    for _, tema, _ in T.TEMAS:
        meta = (objetivos or {}).get("tema", {}).get(tema)
        p(f"  {tema:26s} {res['por_tema'].get(tema, 0):5d} {acum_t.get(tema, 0):10d} {meta if meta is not None else '':>11} "
          f"{(str(round(acum_t.get(tema, 0) / meta * 100)) + ' %') if meta else '':>7}")
    p("\nDISTRIBUCIÓN POR MÚSCULO (un artículo puede tocar varios)")
    p(f"  {'músculo':26s} {'lote':>5s} {'acumulado':>10s} {'meta final':>11s} {'avance':>7s}")
    for gid, nombre in T.MUSCULOS.items():
        meta = (objetivos or {}).get("musculo", {}).get(nombre)
        p(f"  {nombre:26s} {res['por_musculo'].get(gid, 0):5d} {acum_m.get(gid, 0):10d} {meta if meta is not None else '':>11} "
          f"{(str(round(acum_m.get(gid, 0) / meta * 100)) + ' %') if meta else '':>7}")
    p(f"  sin ningún músculo en este lote: {res['sin_musculo']}")


def cargar_objetivos():
    ruta = os.path.join(RAIZ, "corpus", "objetivos.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida un lote de artículos antes de importarlo")
    ap.add_argument("lote")
    ap.add_argument("--plan", help="CSV titulo,tema,musculo con lo que se espera de cada artículo")
    ap.add_argument("--json", help="guarda el resultado completo en este archivo")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lote, fallos = leer_lote(args.lote)
    if fallos:
        for f in fallos:
            print("ERROR de formato:", f)
        return 1
    from db_config import get_connection
    conn = get_connection()
    if conn is None:
        print("ERROR: sin conexión con la BD")
        return 1
    try:
        cur = conn.cursor(dictionary=True)
        existentes = leer_existentes(cur)
        conteo = contar_familias(cur)
        cur.close()
    finally:
        conn.close()
    plan = leer_plan(args.plan) if args.plan else None
    res = validar(lote, existentes, conteo, plan)
    informe(res, lote, existentes, cargar_objetivos())
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print("\nRESULTADO:", "APROBADO" if not res["errores"] else f"RECHAZADO ({len(res['errores'])} errores)")
    return 0 if not res["errores"] else 1


if __name__ == "__main__":
    sys.exit(main())
