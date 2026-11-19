"""Árbol de PATRÓN DE MOVIMIENTO: clasificación APROXIMADA de los ejercicios por palabras clave.

    Patrón de movimiento > Grupo > Patrón > Ejercicio (hoja)        (altura 3)

Los datos no traen el patrón de movimiento, así que se infiere de `nombre_es` con reglas de
palabras clave. NO es una clasificación exacta y la interfaz y los reportes lo dicen:
  * los nombres son traducciones automáticas, a menudo con marcas o apellidos («Holman», «Gethin»,
    «FYR2», «Metaburn») y algunos no dicen qué movimiento es («Extensión», «Plato giratorio»);
  * una regla acierta casi siempre en lo que nombra con claridad (sentadilla, remo, curl, plancha) y
    falla en los casos mixtos («zancada inversa a peso muerto»: solo cabe un patrón);
  * lo que ninguna regla reconoce NO se adivina: cuelga de «Sin clasificar».
Las reglas se evalúan EN ORDEN y gana la primera que coincide (lo específico va antes que lo general).
Solo se usa el nombre; no se mira el músculo, la modalidad ni el equipamiento.

Los artículos se enlazan a los patrones por unas etiquetas concretas (TERMINO_A_PATRON), igual que a
Equipamiento y Nivel.
"""
import re

from .taxonomia import SIN_CLASIFICAR, normalizar

# (grupo, [patrones]). El orden es el de los menús y desempata de forma determinista.
GRUPOS_PATRON = [
    ("Empuje", ["Empuje horizontal", "Empuje vertical", "Extensión de codo"]),
    ("Tirón", ["Tirón horizontal", "Tirón vertical", "Flexión de codo"]),
    ("Aislamiento del tren superior", ["Aperturas y cruces", "Elevaciones de hombro", "Encogimientos", "Muñeca y antebrazo"]),
    ("Piernas", ["Sentadilla", "Bisagra de cadera", "Zancada y unilateral", "Flexión y extensión de rodilla", "Pantorrilla"]),
    ("Core", ["Estabilización del tronco", "Flexión de tronco", "Rotación del tronco"]),
    ("Cuerpo completo", ["Olímpico y balístico", "Saltos y pliometría", "Cardio y locomoción"]),
    ("Movilidad", ["Estiramiento y movilidad"]),
]
NOMBRE_RAIZ = "Patrón de movimiento"

# Reglas sobre el nombre normalizado (minúsculas, sin acentos). Gana la PRIMERA que coincide.
REGLAS_PATRON = [
    ("Estiramiento y movilidad", r"\b(estiramiento|estiramientos|estirar|circulo|circulos|movilidad|abraza|superhombre|enhebrar)\b|gato vaca|gato-vaca|foca gato|inclinacion pelvica|90/90|rodillo de espuma|foam roll"),
    ("Bisagra de cadera", r"\b(peso muerto|buenos dias|good morning|rumano)\b"),
    ("Estabilización del tronco", r"\b(plancha|plank|tablon|despliegue|escalador|pallof|hollow)\b|rueda abdominal|bicho muerto|puente lateral|cuerpo hueco"),
    ("Rotación del tronco", r"\b(giro|giros|torsion|lenador|molino|retorcido)\b|rotacion rusa|rotacion del tronco|rotaciones del torso"),
    ("Flexión de tronco", r"\b(abdominales|abdominal|crunch|crujido|crujidos|crisis)\b|elevaci(?:on|ones) de piernas?|elevaci(?:on|ones) de rodillas?|rodillas al pecho|sit up|encogimiento abdominal|v[- ]up"),
    ("Olímpico y balístico", r"\b(arrancada|cargada|limpieza|limpiar|envion|snatch|clean|jerk|swing|lanzamiento|lanzamientos|lanzar|atrapar|slam)\b|balanceo con pesa"),
    ("Saltos y pliometría", r"\b(salto|saltos|saltar|saltando|burpee|burpees|pliometric\w*|jack|jacks|brinco\w*|tijera\w*|saltador\w*)\b"),
    ("Cardio y locomoción", r"\b(boxeo|elipt\w*|correr|carrera|trote|caminata|caminar|bicicleta|ciclismo|metaburn|esquiador|esqui|trineo|granjero|paseo|acarreo|gateo|escalada|oruga|oso|cangrejo|skipping)\b|rodillas? altas?|pies rapidos|deslizamiento defensivo"),
    ("Pantorrilla", r"\b(pantorrilla|pantorrillas|gemelo|gemelos|soleo|talones|talon)\b"),
    ("Bisagra de cadera", r"puentes? de gluteos?|puentes? de cadera|empuje de cadera|hip thrust|elevaci(?:on|ones) de cadera|elevaci(?:on|ones) de gluteos|hiperextension\w*|extension de espalda|extension de respaldo|patada de mula|patada de burro|patada de gluteo|patada hacia atras|patada trasera|curl nordico|extension de cadera"),
    ("Zancada y unilateral", r"\b(zancada|zancadas|estocada|estocadas|escalon|bulgara|pistol)\b|paso adelante|paso atras|a una pierna|una pierna|split squat"),
    ("Sentadilla", r"\b(sentadilla|sentadillas|squat|squats|hack|cuclilla|cuclillas)\b|prensa de piernas?|prensa de pie|prensa inclinada"),
    ("Flexión y extensión de rodilla", r"extensi(?:on|ones) de piernas?|flexi(?:on|ones) de piernas?|curl de piernas?|curl femoral|curl de isquio\w*"),
    ("Muñeca y antebrazo", r"\b(muneca|munecas|antebrazo|antebrazos|pellizco|dedos)\b|agarre de"),
    ("Encogimientos", r"\b(encogimiento|encogimientos|shrug|shrugs|trapecio)\b"),
    ("Elevaciones de hombro", r"elevaci(?:on|ones) lateral(?:es)?|elevaci(?:on|ones) frontal(?:es)?|elevaci(?:on|ones) posterior(?:es)?|elevaci(?:on|ones) de deltoides|elevaci(?:on|ones) de hombros?|\b(pajaro|pajaros)\b|remo al menton|remo vertical|levantamientos? frontal(?:es)?|levantamientos? lateral(?:es)?|elevacion en y|mosca inversa|mosca posterior"),
    ("Aperturas y cruces", r"\b(apertura|aperturas|mosca|moscas|crossover|contractora)\b|cruces? de cables?|pec deck"),
    ("Extensión de codo", r"\b(triceps|fondo|fondos|skull|triturador|craneos|inmersion|inmersiones)\b|extension de codo|patada de triceps|press frances|rompecraneos"),
    ("Tirón vertical", r"\b(jalon|jalones|dominada|dominadas|pullover|pullovers)\b|pull ?ups?|chin ?ups?|subida a la barra|muscle up"),
    ("Tirón horizontal", r"\b(remo|remos|fila|filas|rowing|row|rows|tirador facial)\b|face pull|tiron facial|tiron horizontal"),
    ("Flexión de codo", r"\b(curl|curls|biceps|martillo|predicador|bayesiano|concentracion|rizador|rizado|rizo|rizos)\b"),
    ("Empuje vertical", r"press militar|press de hombros?|press arnold|press sobre la cabeza|press por encima de la cabeza|empuje vertical|push press|press de pie|empuje[\w ]* por encima de la cabeza"),
    ("Empuje horizontal", r"\b(press|flexiones|flexion|lagartija|lagartijas)\b|flexion de brazos|push ?ups?|empuje horizontal|prensa de suelo"),
]
_REGLAS = [(p, re.compile(r)) for p, r in REGLAS_PATRON]
PATRONES = [p for _, ps in GRUPOS_PATRON for p in ps]
GRUPO_DE_PATRON = {p: g for g, ps in GRUPOS_PATRON for p in ps}


def patron_de_nombre(nombre_es):
    """Patrón de movimiento (nombre) que las reglas asignan a un ejercicio, o None si ninguna coincide."""
    n = normalizar(nombre_es)
    for patron, regla in _REGLAS:
        if regla.search(n):
            return patron
    return None


# Etiqueta de artículo (normalizada, tal como sale de separar_etiquetas) -> patrón. Solo etiquetas que
# nombran un movimiento sin ambigüedad.
TERMINO_A_PATRON = {
    "press banca": "Empuje horizontal", "press banca arco": "Empuje horizontal", "press mancuernas": "Empuje horizontal",
    "floor press": "Empuje horizontal", "press suelo": "Empuje horizontal", "press": "Empuje horizontal",
    "remo": "Tirón horizontal", "remo invertido": "Tirón horizontal",
    "dominadas": "Tirón vertical", "dominadas neutro": "Tirón vertical", "jalon": "Tirón vertical",
    "curl": "Flexión de codo", "curl martillo": "Flexión de codo", "curl biceps": "Flexión de codo",
    "fondos": "Extensión de codo",
    "sentadilla": "Sentadilla", "sentadilla cajon": "Sentadilla", "sentadilla zercher": "Sentadilla",
    "sentadilla sissy": "Sentadilla", "sentadillas": "Sentadilla",
    "bisagra": "Bisagra de cadera", "peso muerto": "Bisagra de cadera", "peso muerto snatch": "Bisagra de cadera",
    "hip thrust": "Bisagra de cadera", "hip thrust unilateral": "Bisagra de cadera",
    "zancada": "Zancada y unilateral", "zancadas": "Zancada y unilateral",
    "leg curl sentado": "Flexión y extensión de rodilla",
    "plancha": "Estabilización del tronco", "antirrotacion": "Estabilización del tronco",
    "rueda abdominal": "Estabilización del tronco",
    "estiramiento": "Estiramiento y movilidad",
    "olimpicos": "Olímpico y balístico",
    "pliometria": "Saltos y pliometría", "salto": "Saltos y pliometría", "saltos": "Saltos y pliometría",
}

# Vocabulario del USUARIO que nombra un patrón (consultas). Solo entran frases cuyas raíces no
# coinciden ni contienen las de otro concepto de otro árbol: «sentadilla», «plancha», «curl»,
# «remo», «dominadas», «press banca»... ya nombran un músculo, y «empuje» o «pliometria», un tema.
# Tampoco «cargada» (raíz de «carga») ni «estiramiento» (ya es sinónimo de un tema). Esos patrones existen en el
# árbol y en los menús, pero no se pueden nombrar en una consulta.
# tests/test_arboles_n.py comprueba que no haya choques.
CONSULTA_PATRON = {
    "Empuje vertical": ["press militar", "press arnold"],
    "Extensión de codo": ["fondos", "fondo"],
    "Tirón horizontal": ["tiron horizontal"],
    "Tirón vertical": ["tiron vertical", "jalon", "jalones"],
    "Bisagra de cadera": ["bisagra"],
    "Zancada y unilateral": ["zancada", "zancadas", "estocada", "estocadas"],
    "Saltos y pliometría": ["salto", "saltos", "burpee", "burpees"],
    "Cardio y locomoción": ["boxeo", "eliptica", "trote"],
    "Olímpico y balístico": ["arrancada", "envion", "snatch"],
    "Rotación del tronco": ["giro ruso", "lenador"],
    "Elevaciones de hombro": ["elevaciones laterales", "elevacion lateral", "pajaros"],
    "Aperturas y cruces": ["aperturas", "apertura", "mosca"],
    "Encogimientos": ["encogimientos", "encogimiento"],
}


def patrones_de_etiquetas(etiquetas):
    """Nombres de patrón que mencionan las etiquetas de un artículo (orden estable)."""
    hallados = {TERMINO_A_PATRON[t] for t in etiquetas if t in TERMINO_A_PATRON}
    return [p for p in PATRONES if p in hallados]
