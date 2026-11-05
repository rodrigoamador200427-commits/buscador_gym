import math
from collections import Counter
from db_config import get_connection
from nlp_processor import clean_and_stem

def index_corpus():
    conn = get_connection()
    if not conn:
        return
    cursor = conn.cursor(dictionary=True)
    
    # 1. Extracción de Documentos con sus IDs y Origen
    documents = []
    
    print("1. Extrayendo documentos de las 3 tablas...")
    cursor.execute("SELECT id, descripcion_es FROM ejercicios WHERE descripcion_es IS NOT NULL")
    for r in cursor.fetchall():
        documents.append({'id': r['id'], 'origen': 'ejercicios', 'text': r['descripcion_es']})
        
    cursor.execute("SELECT id, CONCAT(titulo, ' ', contenido, ' ', etiquetas) as text FROM articulos")
    for r in cursor.fetchall():
        documents.append({'id': r['id'], 'origen': 'articulos', 'text': r['text']})
        
        
    N = len(documents)
    print(f"Total documentos a indexar: {N}")
    
    # 2. Calcular Frecuencia del Término (TF) y Frecuencia de Documento (DF)
    df = Counter() # En cuántos documentos distintos aparece una palabra
    doc_tfs = []   # Guardará la info de cada documento
    
    print("2. Procesando NLP y calculando TF (Frecuencia Local)...")
    for doc in documents:
        tokens = clean_and_stem(doc['text'])
        if not tokens:
            continue
        
        term_counts = Counter(tokens)
        doc_tfs.append({
            'doc_id': doc['id'],
            'origen': doc['origen'],
            'term_counts': term_counts,
            'total_terms': len(tokens) # Necesario para TF normalizado
        })
        
        # Aumentar la cuenta DF para cada término único en este documento
        for term in term_counts.keys():
            df[term] += 1
            
    # 3. Limpiar tablas viejas (Por si ejecutas el script más de una vez)
    print("3. Preparando base de datos...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE postings;")
    cursor.execute("TRUNCATE TABLE diccionario;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    
    # 4. Calcular IDF e insertar en Diccionario
    print("4. Calculando IDF (Rareza Global) e insertando en Diccionario...")
    dict_insert_query = "INSERT INTO diccionario (termino, idf) VALUES (%s, %s)"
    dict_data = []
    term_idf = {} # Cache en memoria para usarlo luego
    
    for term, count in df.items():
        # Fórmula IDF estándar = Logaritmo(Total_Docs / Docs_Con_El_Termino)
        idf = math.log10(N / float(count))
        term_idf[term] = idf
        dict_data.append((term, idf))
        
    cursor.executemany(dict_insert_query, dict_data)
    conn.commit()
    
    # Recuperar los IDs que MySQL le asignó a cada término
    diccionario_db = {}
    cursor.execute("SELECT id, termino FROM diccionario")
    for r in cursor.fetchall():
        diccionario_db[r['termino']] = r['id']
        
    # 5. Calcular TF-IDF y crear Postings List
    print("5. Calculando TF-IDF y generando Postings List...")
    postings_insert_query = """
        INSERT INTO postings (termino_id, doc_id, origen, tf, peso_tfidf) 
        VALUES (%s, %s, %s, %s, %s)
    """
    postings_data = []
    
    for doc in doc_tfs:
        for term, count in doc['term_counts'].items():
            # TF Normalizado = (Veces que aparece la palabra / Total de palabras en el doc)
            tf = count / float(doc['total_terms'])
            idf = term_idf[term]
            tfidf = tf * idf # ¡LA FÓRMULA MÁGICA!
            
            term_id = diccionario_db[term]
            postings_data.append((term_id, doc['doc_id'], doc['origen'], tf, tfidf))
    
    # Inserción masiva en bloques de 10,000 para no saturar la memoria RAM
    chunk_size = 10000
    print(f"Total de referencias a insertar: {len(postings_data)}")
    for i in range(0, len(postings_data), chunk_size):
        cursor.executemany(postings_insert_query, postings_data[i:i+chunk_size])
        conn.commit()
        print(f" -> Insertados {min(i+chunk_size, len(postings_data))} / {len(postings_data)}...")
        
    cursor.close()
    conn.close()
    print("\n¡ÉXITO! Tu Índice Inverso TF-IDF ha sido construido perfectamente.")

if __name__ == "__main__":
    index_corpus()