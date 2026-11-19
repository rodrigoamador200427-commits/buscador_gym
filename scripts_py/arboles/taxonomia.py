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


# ---------------------------------------------------------------------------
# ETIQUETAS (tablas etiquetas / documento_etiquetas; las genera generar_etiquetas.py)
# ---------------------------------------------------------------------------
# Valores del dataset (en inglés) -> nombre visible en español.
NIVELES = {"Beginner": "Principiante", "Intermediate": "Intermedio", "Expert": "Avanzado"}
MODALIDADES = {
    "Strength": "Fuerza", "Powerlifting": "Powerlifting", "Strongman": "Strongman",
    "Olympic Weightlifting": "Halterofilia", "Plyometrics": "Pliometría",
    "Cardio": "Cardio", "Stretching": "Estiramiento",
}
# Equipamiento que no describe nada útil: no genera etiqueta.
EQUIPAMIENTO_SIN_ETIQUETA = {"Other", ""}

# Sinónimos (ya normalizados) -> forma canónica. Los plurales simples ("rodillas",
# "mancuernas") se unen solos si existe el singular; aquí van los que no siguen la regla
# o cuyo singular no aparece en el contenido.
SINONIMOS_ETIQUETA = {
    "pectoral": "pecho", "pectorales": "pecho",
    "deltoides": "hombro",
    "gemelos": "pantorrilla", "gemelo": "pantorrilla",
    "abdominales": "abdomen",
    "antebrazos": "antebrazo",
    "gluteos": "gluteo",
    "femoral": "isquiotibiales",
    "mancuernas": "mancuerna", "bandas": "banda", "kettlebells": "kettlebell",
    "estiramientos": "estiramiento", "elongacion": "estiramiento",
    "lesiones": "lesion",
    "chin-ups": "dominadas",
    "barra ez": "barra z",
}

# Claves de etiquetas de artículos que son músculos o equipamiento (el resto son temas).
# Los 11 músculos de MUSCULOS ya cuentan; aquí van los demás términos anatómicos.
TERMINOS_MUSCULO = {
    "dorsal", "lumbar", "trapecio", "romboides", "serrato", "erectores", "oblicuos",
    "aductores", "manguito rotador", "soleo", "core", "gluteo mayor", "gluteo medio",
    "recto femoral", "recto abdominal", "vastos",
}
TERMINOS_EQUIPAMIENTO = {
    "barra", "mancuerna", "maquina", "polea", "banda", "banda elastica", "banco",
    "kettlebell", "paralelas", "correas", "balon medicinal", "rodillo", "barra hexagonal",
    "barra z",
}

# ---------------------------------------------------------------------------
# VOCABULARIO CONTROLADO AMPLIADO (fase 6A: corpus de artículos generados)
# ---------------------------------------------------------------------------
# Etiquetas que los artículos originales ya usan 4 veces o más y que NO están en TEMAS,
# ETIQUETA_A_MUSCULO ni los diccionarios de arriba. Se agregan aparte a propósito: si
# entraran en TEMAS cambiaría el tema que el árbol asigna a los 341 artículos originales.
# Se dejaron fuera las que tocan salud o medicina (dosis, cortisol, inflamacion, inmunidad,
# hormonas, mtor, melatonina, atp, dolor): un artículo generado no debe apoyarse en ellas.
VOCABULARIO_EXTRA = {
    "rendimiento", "fisiologia", "entrenamiento", "sobreentrenamiento", "asimetrias",
    "principiantes", "pelvis", "macros", "tendones", "saciedad", "sudoracion", "bienestar",
    "deficit", "ritmo circadiano", "peso muerto", "aminoacidos", "glucogeno", "salud",
    "masa magra", "fibras tipo 2", "rango", "profundidad", "bisagra", "grasa", "leucina",
    "electrolitos", "sodio", "tension mecanica", "autorregulacion", "vfc", "rigidez",
    "sueno profundo", "rango de movimiento", "hueso", "seguridad", "evidencia", "oxigeno",
    "fibra", "digestion", "micronutrientes", "coordinacion", "perdida de grasa",
    "mitocondrias", "articulaciones", "rutina nocturna",
}


# ---------------------------------------------------------------------------
# ÁRBOLES 3 y 4 — EQUIPAMIENTO y NIVEL (fase 6B; para ejercicios y, por etiquetas, artículos)
#   Equipamiento > Categoría > Equipamiento > Ejercicio (hoja)
#   Nivel de experiencia > Nivel > Ejercicio (hoja)
# ---------------------------------------------------------------------------
# (categoría, [equipamientos]). El orden es el de los menús y desempata de forma determinista.
# Los nombres de los equipamientos con columna salen de EQUIPAMIENTO; Banco, Paralelas y
# Correas solo existen como etiquetas de artículos (ningún ejercicio los trae): 0 ejercicios.
CATEGORIAS_EQUIPAMIENTO = [
    ("Pesas libres", ["Barra", "Barra Z", "Mancuernas", "Kettlebell"]),
    ("Máquinas y poleas", ["Máquina", "Polea"]),
    ("Peso corporal y bandas", ["Peso corporal", "Bandas", "Rodillo"]),
    ("Balones", ["Balón medicinal", "Pelota de ejercicio"]),
    ("Accesorios", ["Banco", "Paralelas", "Correas"]),
    ("Otros", ["Otro", SIN_EQUIPAMIENTO]),
]
CATEGORIA_DE_EQUIPAMIENTO_DESCONOCIDO = "Otros"

# Etiqueta de artículo (normalizada) -> nodo de Equipamiento.
TERMINO_A_EQUIPAMIENTO = {
    "barra": "Barra", "barra hexagonal": "Barra", "barra z": "Barra Z", "barra ez": "Barra Z",
    "mancuerna": "Mancuernas", "mancuernas": "Mancuernas",
    "maquina": "Máquina", "polea": "Polea",
    "kettlebell": "Kettlebell", "kettlebells": "Kettlebell",
    "banda": "Bandas", "bandas": "Bandas", "banda elastica": "Bandas",
    "peso corporal": "Peso corporal", "rodillo": "Rodillo",
    "balon medicinal": "Balón medicinal", "pelota de ejercicio": "Pelota de ejercicio",
    "banco": "Banco", "paralelas": "Paralelas", "correas": "Correas",
}

# Vocabulario del USUARIO que nombra un equipamiento (consultas). Quedan fuera los que comparten raíz
# (la del stemmer, que es lo que compara el motor) con otra palabra que ya nombra un concepto de otro árbol:
#   «banco»   (raíz de «banca»: «press de banca» no habla del banco),
#   «correas» (raíz de «correr», un sinónimo del tema Resistencia),
#   «rodillo» (raíz de «rodilla», un músculo; ni siquiera «rodillo de espuma» sirve, porque contiene la raíz
#             de «rodilla»): solo se nombra con «foam roller».
# Banco y Correas siguen siendo nodos (los artículos los enlazan por etiquetas) y salen en los menús.
# «Otro» y «Sin especificar» no se pueden nombrar. tests/test_arboles_n.py comprueba que no haya choques.
CONSULTA_EQUIPAMIENTO = {
    "Barra": ["barra", "barra hexagonal"], "Barra Z": ["barra ez", "barra zeta"],
    "Mancuernas": ["mancuerna", "mancuernas"], "Máquina": ["maquina", "maquinas"],
    "Polea": ["polea", "poleas", "cable"], "Kettlebell": ["kettlebell", "pesa rusa"],
    "Bandas": ["banda", "bandas", "banda elastica"],
    "Peso corporal": ["peso corporal", "sin material", "sin equipo"],
    "Rodillo": ["foam roller"], "Balón medicinal": ["balon medicinal"],
    "Pelota de ejercicio": ["pelota de ejercicio", "fitball"],
    "Paralelas": ["paralelas"],
}

NIVELES_ORDEN = ["Principiante", "Intermedio", "Avanzado"]    # = valores de NIVELES, de menor a mayor
TERMINO_A_NIVEL = {
    "principiante": "Principiante", "principiantes": "Principiante", "novato": "Principiante",
    "intermedio": "Intermedio", "avanzado": "Avanzado", "experto": "Avanzado",
}
CONSULTA_NIVEL = {
    "Principiante": ["principiante", "principiantes", "novato"],
    "Intermedio": ["intermedio"],
    "Avanzado": ["avanzado", "experto"],
}

# --- Los árboles juntos (orden = prioridad: desempata cualquier elección entre árboles) ---
ORDEN_ARBOLES = ["anatomia", "temas", "equipamiento", "nivel"]
TITULO_ARBOL = {"anatomia": "Anatomía", "temas": "Temas", "equipamiento": "Equipamiento", "nivel": "Nivel"}
# Árbol al que salta una consulta que nombra UN solo concepto (conserva el comportamiento de la fase 1:
# músculo <-> tema; los demás saltan a Anatomía).
ARBOL_COMPANERO = {"anatomia": "temas", "temas": "anatomia", "equipamiento": "anatomia", "nivel": "anatomia"}
# La recuperación TF-IDF sin conceptos solo compara estos árboles (los de la fase 1).
ARBOLES_RECUPERACION = ("anatomia", "temas")


def equipamientos_de_etiquetas(etiquetas):
    """Nombres de nodos de Equipamiento que mencionan las etiquetas (orden estable)."""
    return sorted({TERMINO_A_EQUIPAMIENTO[t] for t in etiquetas if t in TERMINO_A_EQUIPAMIENTO})


def niveles_de_etiquetas(etiquetas):
    """Niveles que mencionan las etiquetas, de menor a mayor."""
    hallados = {TERMINO_A_NIVEL[t] for t in etiquetas if t in TERMINO_A_NIVEL}
    return [n for n in NIVELES_ORDEN if n in hallados]
