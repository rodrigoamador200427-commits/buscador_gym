import math
import json
import sys
from collections import defaultdict
from db_config import get_connection

def magnitude(vector):
    """Calcula la longitud geométrica del vector."""
    return math.sqrt(sum(val**2 for val in vector.values()))

def get_recommendations(usuario_id=1, limit=10):
    conn = get_connection()
    if not conn:
        print(json.dumps({"error": "Sin conexión a la BD"}))
        return

    cursor = conn.cursor(dictionary=True)

    # ==================================================
    # 1. OBTENER EL HISTORIAL DEL USUARIO
    # ==================================================
    cursor.execute('''
        SELECT doc_id, origen 
        FROM interacciones 
        WHERE usuario_id = %s AND interaccion = 'like'
    ''', (usuario_id,))
    interacciones = cursor.fetchall()
    
    # Manejo del "Cold Start" (Si el usuario es nuevo y no tiene likes)
    if not interacciones:
        print(json.dumps({"status": "cold_start", "mensaje": "Dale like a algunos ejercicios para conocerte."}))
        return

    liked_docs = [(r['doc_id'], r['origen']) for r in interacciones]
    
    # ==================================================
    # 2. CONSTRUIR EL VECTOR DE PERFIL DEL USUARIO (U)
    # ==================================================
    user_vector = defaultdict(float)
    
    # Generar la condición SQL para los documentos likeados
    liked_conditions = " OR ".join([f"(doc_id = {d} AND origen = '{o}')" for d, o in liked_docs])
    
    cursor.execute(f'''
        SELECT termino_id, peso_tfidf 
        FROM postings 
        WHERE {liked_conditions}
    ''')
    
    # Sumar los pesos: Si le gustaron 3 ejercicios de "pecho", la palabra "pech" será un pico enorme.
    for row in cursor.fetchall():
        user_vector[row['termino_id']] += row['peso_tfidf']
        
    # Promediar el vector (Centroide matemático)
    num_liked = len(liked_docs)
    for t in user_vector:
        user_vector[t] /= num_liked
        
    # [EXTRA ACADÉMICO] Extraer las top 5 raíces para mostrar en la interfaz "Tu Perfil Semántico"
    cursor.execute("SELECT id, termino FROM diccionario")
    diccionario_inverso = {r['id']: r['termino'] for r in cursor.fetchall()}
    top_user_terms = sorted(user_vector.items(), key=lambda x: x[1], reverse=True)[:5]
    perfil_semantico = [diccionario_inverso[t[0]] for t in top_user_terms]

    # ==================================================
    # 3. OBTENER VECTORES DE DOCUMENTOS NO VISTOS (D)
    # ==================================================
    # En lugar de hacer miles de queries, traemos todo a un diccionario anidado súper rápido
    cursor.execute('''
        SELECT doc_id, origen, termino_id, peso_tfidf 
        FROM postings
    ''')
    
    candidates = defaultdict(dict)
    for row in cursor.fetchall():
        doc_key = (row['doc_id'], row['origen'])
        # Regla de Agotamiento: Excluir las películas (documentos) que ya vio
        if doc_key not in liked_docs: 
            candidates[doc_key][row['termino_id']] = row['peso_tfidf']
            
    # ==================================================
    # 4. APLICAR SIMILITUD DEL COSENO
    # ==================================================
    scores = []
    user_mag = magnitude(user_vector)
    
    for doc_key, doc_vector in candidates.items():
        # [OPTIMIZACIÓN EXTREMA]: Producto punto. Si el documento no comparte 
        # NINGUNA palabra clave con el usuario, su similitud es 0. Nos saltamos la matemática pesada.
        common_terms = set(user_vector.keys()) & set(doc_vector.keys())
        if not common_terms:
            continue
            
        dot_product = sum(user_vector[t] * doc_vector[t] for t in common_terms)
        doc_mag = magnitude(doc_vector)
        
        # Fórmula del Coseno: (U * D) / (|U| * |D|)
        if doc_mag > 0 and user_mag > 0:
            similitud = dot_product / (user_mag * doc_mag)
            if similitud > 0.05: # Umbral mínimo de confianza (5%)
                scores.append({
                    "doc_id": doc_key[0],
                    "origen": doc_key[1],
                    "similitud": round(similitud, 4)
                })
                
    # ==================================================
    # 5. ORDENAR Y DEVOLVER JSON
    # ==================================================
    # Ordenar de mayor a menor similitud
    scores.sort(key=lambda x: x['similitud'], reverse=True)
    top_recommendations = scores[:limit]
    
    resultado = {
        "status": "success",
        "perfil_semantico": perfil_semantico,
        "recomendaciones": top_recommendations
    }
    
    # Imprimir en formato JSON para que PHP lo capture sin esfuerzo
    print(json.dumps(resultado))

if __name__ == "__main__":
    get_recommendations()