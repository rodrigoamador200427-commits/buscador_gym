import random
import sys
import json
import unicodedata

def normalizar_texto(texto):
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

class MotorGrafoConocimiento:
    def __init__(self):
        # MATRIZ DE ADYACENCIA (Enlaces Dinámicos Árbol Práctico -> Árbol Teórico)
        # Llave: Raíces NLP esperadas del usuario
        # Valor: Configuración del salto semántico con tags EXACTOS de tu articulos.csv
        self.grafo_saltos = {
            # TREN SUPERIOR
            "pech pectoral banc": {
                "id_musculo": 1,
                "arbol_destino": "Biomecánica y Prevención",
                "razon": "Antes de realizar empujes pesados, es vital entender la retracción escapular para proteger el hombro.",
                "query_teorica": "press banca agarre escapulas trayectoria hombro" # Tags reales de tu CSV
            },
            "espald dorsal rem lumb dominad": {
                "id_musculo": 2,
                "arbol_destino": "Biomecánica de Tracción",
                "razon": "Cuidar la zona lumbar es crítico en los tirones. Descubre la técnica de la bisagra de cadera.",
                "query_teorica": "peso muerto bisagra cadera lumbar barra tecnica"
            },
            "hombr deltoid militar": {
                "id_musculo": 3,
                "arbol_destino": "Prevención Articular",
                "razon": "El hombro es la articulación más inestable. Aprende a cuidar el manguito rotador.",
                "query_teorica": "manguito rotador deltoides posterior hombro prevencion rotacion externa"
            },
            "bicep curl braquial": {
                "id_musculo": 4,
                "arbol_destino": "Fisiología de Hipertrofia",
                "razon": "Para maximizar el crecimiento de los brazos, necesitas dominar la tensión pasiva y el rango completo.",
                "query_teorica": "rango completo elongacion hipertrofia tension pasiva longitud muscular curl estiramiento"
            },
            "tricep frances extension": {
                "id_musculo": 5,
                "arbol_destino": "Fisiología de Hipertrofia",
                "razon": "Descubre cómo el estrés metabólico ayuda a hipertrofiar fibras en ejercicios de aislamiento.",
                "query_teorica": "estres metabolico lactato bombeo hipertrofia series altas descansos cortos celula"
            },
            "antebraz muñec agarr": {
                "id_musculo": 11,
                "arbol_destino": "Fuerza Aplicada",
                "razon": "El agarre es el limitante en peso muerto y dominadas. Conoce la biomecánica del antebrazo.",
                "query_teorica": "agarre antebrazos peso muerto dominadas correas muneca fuerza"
            },
            
            # TREN INFERIOR
            "cuadric sentadill prensa": {
                "id_musculo": 6,
                "arbol_destino": "Biomecánica Estructural",
                "razon": "La profundidad de la sentadilla y el valgo de rodilla determinan tu salud articular a largo plazo.",
                "query_teorica": "sentadilla profundidad gluteo biomecanica tecnica rodillas"
            },
            "isquio femoral ruman": {
                "id_musculo": 7,
                "arbol_destino": "Prevención de Lesiones",
                "razon": "Los isquiotibiales son propensos a desgarros. El trabajo excéntrico es la mejor prevención.",
                "query_teorica": "curl nordico isquiotibiales excentrica lesiones prevencion tobillos fuerza"
            },
            "pantorrill gemel soleo talon": {
                "id_musculo": 8,
                "arbol_destino": "Movilidad Articular",
                "razon": "Una mala movilidad de tobillo arruina tu sentadilla. Así puedes mejorar tu dorsiflexión.",
                "query_teorica": "movilidad tobillo dorsiflexion sentadilla profundidad tecnica lumbar rango"
            },
            "glute cader hip thrust pelvis": {
                "id_musculo": 9,
                "arbol_destino": "Activación Neuromuscular",
                "razon": "Para desarrollar el glúteo, primero debes dominar la activación pélvica y el bloqueo de cadera.",
                "query_teorica": "hip thrust gluteo pelvis activacion lumbar cadera fuerza"
            },
            
            # CORE Y METABOLISMO
            "core abdomen abdominal planch oblicu": {
                "id_musculo": 10,
                "arbol_destino": "Estabilidad Espinal",
                "razon": "El core no es para hacer flexiones, sino para resistir la extensión y rotar. Conoce la 'anti-extensión'.",
                "query_teorica": "plancha core antiextension abdomen estabilidad lumbar progresion"
            }
        }
        
        # POOL DE SERENDIPIA DINÁMICA (Random Walk)
        # Si la búsqueda no activa un músculo, el motor salta aleatoriamente a uno de estos universos:
        self.pool_saltos_genericos = [
            {
                "arbol_destino": "Recuperación y Sueño",
                "razon": "El músculo no crece en el gimnasio, crece en la cama. Prioriza tu descanso.",
                "query_teorica": "sueno melatonina ritmo circadiano descanso"
            },
            {
                "arbol_destino": "Nutrición y Metabolismo",
                "razon": "El entrenamiento es solo el estímulo, pero la comida es el material de construcción.",
                "query_teorica": "superavit deficit calorias macros proteina"
            },
            {
                "arbol_destino": "Suplementación Científica",
                "razon": "Potencia tu esfuerzo físico con suplementos que tienen evidencia comprobada.",
                "query_teorica": "creatina monohidrato cafeina rendimiento suplemento"
            },
            {
                "arbol_destino": "Prevención y Movilidad",
                "razon": "Un atleta lesionado no progresa. No ignores el calentamiento y la movilidad.",
                "query_teorica": "movilidad estiramiento calentamiento flexibilidad prevencion"
            },
            {
                "arbol_destino": "Fisiología del Esfuerzo",
                "razon": "Entender cómo funciona la fatiga te ayudará a programar mejores entrenamientos.",
                "query_teorica": "sistema nervioso central fatiga sobreentrenamiento volumen"
            }
        ]

    def extraer_salto_semantico(self, query):
        tokens = query.split()
        for token in tokens:
            if len(token) < 3: continue
            
            # Buscamos si el token activa alguna de las llaves de nuestra matriz
            for claves, datos_salto in self.grafo_saltos.items():
                if token in claves:
                    return datos_salto # Retorna el primer salto encontrado
        
        # Si no hubo match anatómico, devolvemos el salto genérico (Serendipia garantizada)
       # Si no hubo match anatómico, inyectamos serendipia aleatoria controlada
        return random.choice(self.pool_saltos_genericos)

if __name__ == "__main__":
    query_usuario = normalizar_texto(sys.argv[1]) if len(sys.argv) > 1 else ""
    
    motor = MotorGrafoConocimiento()
    salto = motor.extraer_salto_semantico(query_usuario)
    
    print(json.dumps({
        "status": "success",
        "salto_semantico": salto
    }))