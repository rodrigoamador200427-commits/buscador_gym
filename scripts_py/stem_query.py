import sys
import re
from nlp_processor import stemmer, stop_words
from db_config import get_connection

# ==========================================
# CAPA 1: TESAURO DE DOMINIO (Truncamientos)
# ==========================================
# Resuelve abreviaturas que no siguen reglas de vocales
THESAURUS = {
    "esp": "espalda",
    "ext": "extension",
    "flex": "flexion",
    "abd": "abdomen",
    "cuad": "cuadriceps",
    "fem": "femoral",
    "isq": "isquiotibial",
    "manc": "mancuerna",
    "sent": "sentadilla",
    "homb": "hombro",
    "bicep": "biceps",
    "tricep": "triceps"
}

def strip_vowels(word):
    """Extrae el esqueleto de consonantes. Ej: 'chest' -> 'chst', 'remo' -> 'rm'"""
    if len(word) <= 1: return word
    # Conservamos la primera letra y eliminamos las vocales del resto
    return word[0] + re.sub(r'[aeiouáéíóú]', '', word[1:])

def process_query():
    if len(sys.argv) <= 1:
        return
        
    raw_query = " ".join(sys.argv[1:])
    raw_query = raw_query.lower()
    
    # Limpieza de caracteres extraños
    reemplazos = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"))
    for a, b in reemplazos:
        raw_query = raw_query.replace(a, b)
    raw_query = re.sub(r'[^a-z\s]', '', raw_query)
    
    tokens = raw_query.split()
    
    # ==========================================
    # CAPA 2: MOTOR DE EXPANSIÓN Y CORRECCIÓN
    # ==========================================
    conn = get_connection()
    if not conn:
        print(raw_query) # Fallback de seguridad
        return
        
    cursor = conn.cursor(dictionary=True)
    # Cargamos el vocabulario real que existe en nuestra base de datos
    cursor.execute("SELECT termino FROM diccionario")
    vocabulario_bd = set(r['termino'] for r in cursor.fetchall())
    
    # Creamos un mapa de esqueletos: {'chst': 'chest', 'prss': 'press', 'rm': 'rem', 'spld': 'espald'}
    mapa_consonantes = {}
    for termino in vocabulario_bd:
        esqueleto = strip_vowels(termino)
        # Si no existe en el mapa, lo registramos
        if esqueleto not in mapa_consonantes:
            mapa_consonantes[esqueleto] = termino

    raices_finales = []
    
    for word in tokens:
        if word in stop_words or len(word) < 2:
            continue
            
        # 1. Pasar por el Tesauro ("esp" -> "espalda")
        if word in THESAURUS:
            word = THESAURUS[word]
            
        # 2. Obtener la raíz normal
        stem_normal = stemmer.stem(word)
        
        # 3. Lógica de Toma de Decisiones
        if stem_normal in vocabulario_bd:
            # Camino Feliz: La palabra o el tesauro generaron una raíz que SÍ existe
            raices_finales.append(stem_normal)
        else:
            # Camino de Corrección: La palabra no existe ("chst", "rmo")
            # Extraemos su esqueleto de consonantes
            esqueleto_usuario = strip_vowels(word)
            
            # Buscamos el esqueleto en nuestro mapa
            if esqueleto_usuario in mapa_consonantes:
                # ¡Magia! Convertimos "chst" en el ID de "chest"
                raices_finales.append(mapa_consonantes[esqueleto_usuario])
            else:
                # Si falla todo, la enviamos normal
                raices_finales.append(stem_normal)

    # Devolver las raíces únicas separadas por espacio a PHP
    raices_unicas = list(set(raices_finales))
    print(" ".join(raices_unicas))

if __name__ == "__main__":
    process_query()