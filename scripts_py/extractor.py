from db_config import get_connection

def extract_corpus():
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    corpus = []

    # 1. Extraer descripciones de ejercicios
    cursor.execute("SELECT descripcion_es FROM ejercicios WHERE descripcion_es IS NOT NULL AND descripcion_es != ''")
    for row in cursor.fetchall():
        corpus.append(row['descripcion_es'])

    # 2. Extraer artículos (título, contenido y etiquetas)
    cursor.execute("SELECT CONCAT(titulo, ' ', contenido, ' ', etiquetas) as texto FROM articulos")
    for row in cursor.fetchall():
        corpus.append(row['texto'])


    cursor.close()
    conn.close()
    
    print(f"Documentos extraídos con éxito: {len(corpus)}")
    return corpus