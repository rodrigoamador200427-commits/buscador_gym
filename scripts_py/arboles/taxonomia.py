"""Taxonomía del dominio: ÚNICA fuente de verdad de los árboles.

Aquí viven los nombres, jerarquías y diccionarios de etiquetas. Ningún otro
módulo debe escribir a mano nombres de músculos, equipamiento o temas.
"""
import unicodedata


def normalizar(texto):
    """Minúsculas, sin acentos ni espacios sobrantes (misma idea que nlp_processor)."""
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFD", str(texto).lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# ÁRBOL 1 — ANATOMÍA (para ejercicios)
#   Cuerpo humano > Región > Músculo > Equipamiento > Ejercicio (hoja)
# ---------------------------------------------------------------------------
# IDs = los de unirdataset/limpiar_ejercicios.py (columna grupo_id de `ejercicios`).
MUSCULOS = {
    1: "Pecho", 2: "Espalda", 3: "Hombro", 4: "Bíceps", 5: "Tríceps",
    6: "Cuádriceps", 7: "Isquiotibiales", 8: "Pantorrilla", 9: "Glúteo",
    10: "Abdomen", 11: "Antebrazos",
}

REGIONES = {
    "Tren superior": [1, 2, 3, 4, 5, 11],
    "Tren inferior": [6, 7, 8, 9],
    "Core": [10],
}

EQUIPAMIENTO = {
    "Body Only": "Peso corporal", "Dumbbell": "Mancuernas", "Barbell": "Barra",
    "Cable": "Polea", "Machine": "Máquina", "Kettlebells": "Kettlebell",
    "Bands": "Bandas", "Medicine Ball": "Balón medicinal",
    "Exercise Ball": "Pelota de ejercicio", "E-Z Curl Bar": "Barra Z",
    "Foam Roll": "Rodillo", "Other": "Otro",
}
SIN_EQUIPAMIENTO = "Sin especificar"

# Etiqueta de artículo (normalizada) -> grupo_id. Conecta la teoría con la anatomía.
ETIQUETA_A_MUSCULO = {
    "pecho": 1, "pectoral": 1, "press banca": 1,
    "espalda": 2, "dorsal": 2, "lumbar": 2, "dominadas": 2, "remo": 2, "trapecio": 2,
    "hombro": 3, "deltoides": 3, "manguito rotador": 3,
    "biceps": 4, "curl": 4,
    "triceps": 5,
    "cuadriceps": 6, "sentadilla": 6, "rodilla": 6, "rodillas": 6,
    "isquiotibiales": 7, "femoral": 7,
    "pantorrilla": 8, "gemelos": 8, "soleo": 8, "tobillo": 8,
    "gluteo": 9, "hip thrust": 9, "cadera": 9,
    "core": 10, "abdomen": 10, "abdominales": 10, "plancha": 10,
    "antebrazos": 11, "antebrazo": 11, "agarre": 11, "muneca": 11,
}

# ---------------------------------------------------------------------------
# ÁRBOL 2 — TEMAS / OBJETIVOS (para artículos)
#   Conocimiento > Rama > Tema > Artículo (hoja)
# ---------------------------------------------------------------------------
# (rama, tema, etiquetas que lo definen). El orden desempata de forma determinista.
TEMAS = [
    ("Entrenamiento", "Fuerza", ["fuerza", "potencia", "carga", "intensidad", "maximo", "fibras tipo ii",
                                 "explosividad", "velocidad", "pliometria"]),
    ("Entrenamiento", "Hipertrofia", ["hipertrofia", "volumen", "tension", "elongacion", "aislamiento",
                                      "fallo", "estres metabolico", "bombeo", "masa muscular"]),
    ("Entrenamiento", "Resistencia", ["resistencia", "aerobico", "cardio"]),
    ("Entrenamiento", "Técnica y biomecánica", ["tecnica", "biomecanica", "excentrica", "unilateral",
                                                 "empuje", "estabilidad", "variantes", "rango completo",
                                                 "pausa", "trayectoria", "escapulas", "activacion",
                                                 "activacion neural", "cadena posterior"]),
    ("Entrenamiento", "Planificación", ["planificacion", "progresion", "monitoreo", "adherencia",
                                         "periodizacion", "competencia"]),
    ("Salud y recuperación", "Recuperación", ["recuperacion", "sueno", "descanso", "fatiga",
                                               "relajacion", "estres", "adaptacion"]),
    ("Salud y recuperación", "Prevención y movilidad", ["movilidad", "prevencion", "rehabilitacion",
                                                         "dolor muscular", "flexibilidad", "calentamiento",
                                                         "propiocepcion", "equilibrio", "lesiones",
                                                         "preparacion", "temperatura"]),
    ("Nutrición", "Alimentación", ["nutricion", "proteina", "carbohidratos", "calorias", "dieta",
                                    "hidratacion", "metabolismo", "sintesis proteica", "energia",
                                    "definicion", "calcio", "insulina", "glucosa", "nutrientes",
                                    "anabolismo"]),
    ("Nutrición", "Suplementación", ["suplemento", "creatina", "cafeina"]),
]
SIN_CLASIFICAR = "Sin clasificar"

# Modalidad del dataset de ejercicios -> tema. OJO: 'Strength' es el 88 % de los
# ejercicios, así que por sí sola NO discrimina ("ganar fuerza" no puede apoyarse solo en ella).
MODALIDAD_A_TEMA = {
    "Strength": "Fuerza", "Powerlifting": "Fuerza", "Strongman": "Fuerza",
    "Olympic Weightlifting": "Fuerza", "Plyometrics": "Fuerza",
    "Cardio": "Resistencia", "Stretching": "Prevención y movilidad",
}


def separar_etiquetas(cadena):
    """'press banca, agarre, pecho' -> ['press banca', 'agarre', 'pecho'] (normalizadas)."""
    return [normalizar(t) for t in str(cadena or "").split(",") if t.strip()]


def nombre_equipamiento(valor):
    if not isinstance(valor, str) or not valor.strip():
        return SIN_EQUIPAMIENTO
    return EQUIPAMIENTO.get(valor.strip(), valor.strip())


def temas_de_etiquetas(etiquetas):
    """Todos los temas con al menos una etiqueta en común, del más al menos puntuado.
    Desempate determinista: orden de definición en TEMAS."""
    conjunto = set(etiquetas)
    puntajes = []
    for orden, (_, tema, tags) in enumerate(TEMAS):
        coincidencias = sum(1 for t in tags if t in conjunto)
        if coincidencias:
            puntajes.append((-coincidencias, orden, tema))
    return [tema for _, _, tema in sorted(puntajes)]


def musculos_de_etiquetas(etiquetas):
    """grupo_id de todos los músculos que mencionan las etiquetas (orden estable)."""
    return sorted({ETIQUETA_A_MUSCULO[t] for t in etiquetas if t in ETIQUETA_A_MUSCULO})


# --- Vocabulario del USUARIO (consultas), distinto del vocabulario de los artículos ---
# Palabras o frases que alguien escribe y que apuntan a un tema (se suman a las etiquetas).
# Las frases cuentan solo si TODAS sus palabras están en la consulta ("bajar peso", no "peso muerto").
SINONIMOS_TEMA = {
    "Fuerza": ["fuerte", "fortalecer", "potente"],
    "Hipertrofia": ["masa", "crecer"],
    "Resistencia": ["aguante", "correr", "cardiovascular"],
    "Alimentación": ["comer", "comida", "alimentos", "bajar peso", "adelgazar", "perder grasa",
                     "grasa corporal"],
    "Recuperación": ["recuperar", "dormir"],
    "Prevención y movilidad": ["lesion", "estirar", "estiramiento"],
    "Planificación": ["plan", "programa", "programar"],
}

# Regiones o apodos que designan VARIOS músculos (grupo_id).
ALIAS_MUSCULO = {
    "piernas": [6, 7, 8, 9], "pierna": [6, 7, 8, 9],
    "brazos": [4, 5, 11], "brazo": [4, 5, 11],
    "abs": [10], "gluteos": [9],
}


# Regla de respaldo: un artículo que habla de un músculo pero de ningún tema concreto
# se considera de técnica/biomecánica (la teoría centrada en un músculo suele serlo).
TEMA_POR_DEFECTO_ANATOMICO = "Técnica y biomecánica"


def temas_del_articulo(etiquetas):
    """Temas del artículo (el primero es el principal). [] si no se puede clasificar."""
    temas = temas_de_etiquetas(etiquetas)
    if not temas and musculos_de_etiquetas(etiquetas):
        temas = [TEMA_POR_DEFECTO_ANATOMICO]
    return temas


# ---------------------------------------------------------------------------
# STOPWORDS DE CONSULTA, en capas (solo afectan a lo que ESCRIBE el usuario; el índice no se toca)
#   1. Gramaticales: las de NLTK (nlp_processor.stop_words), se aplican igual que en el indexador.
#   2. Intención/pregunta: palabras que piden algo pero no describen el tema ("quiero", "como").
#   3. Objetivo (PROTEGIDAS): palabras con significado de dominio. NUNCA se eliminan.
#      El stopwords.txt original mezclaba estas con las gramaticales (fuerza, hipertrofia, masa, peso...):
#      por eso no se puede usar tal cual.
# ---------------------------------------------------------------------------
PALABRAS_INTENCION = {
    "quiero", "quisiera", "necesito", "busco", "puedo", "podria", "hacer", "hago", "hacerlo",
    "dame", "dime", "ayuda", "ayudame", "como", "cual", "cuales", "donde", "cuando", "porque",
    "tips", "consejos", "consejo",
}

OBJETIVO_PROTEGIDO = {
    "fuerza", "fuerte", "hipertrofia", "masa", "muscular", "musculo", "peso", "grasa", "volumen",
    "ganar", "bajar", "subir", "perder", "definicion", "resistencia", "dieta", "proteina", "calorias",
    "rutina", "ejercicio", "ejercicios", "entrenamiento", "entrenar", "recuperacion", "descanso",
}

# Expansión de consulta: cuando el usuario expresa un objetivo con SUS palabras, se añade el
# vocabulario con el que los documentos hablan de ese tema (lo que de verdad está en el índice).
EXPANSION_TEMA = {
    "Fuerza": ["fuerza", "potencia"],
    "Hipertrofia": ["hipertrofia", "volumen"],
    "Resistencia": ["resistencia", "aerobico", "cardio"],
    "Alimentación": ["dieta", "calorias", "nutricion"],
    "Recuperación": ["recuperacion", "sueno", "descanso"],
    "Prevención y movilidad": ["movilidad", "prevencion", "lesiones"],
    "Planificación": ["planificacion", "progresion"],
}
