import re
import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

# Descargar recursos
nltk.download('stopwords', quiet=True)

stemmer = SnowballStemmer('spanish')
stop_words = set(stopwords.words('spanish'))

def clean_and_stem(text):
    # 1. Convertir a minúsculas
    text = text.lower()
    
    # 2. Normalización de caracteres (Acentos y eñes)
    reemplazos = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ü", "u"), ("ñ", "n")
    )
    for a, b in reemplazos:
        text = text.replace(a, b)
        
    # 3. Eliminar todo lo que NO sea letras de la 'a' a la 'z' (sin acentos) o espacios
    text = re.sub(r'[^a-z\s]', '', text)
    
    # 4. Tokenizar
    tokens = text.split()
    
    # 5. Eliminar stopwords y aplicar Stemming
    stemmed_tokens = [
        stemmer.stem(word) for word in tokens 
        # Asegurarnos de quitar stopwords normalizadas
        if word not in stop_words and len(word) > 2
    ]
    
    return stemmed_tokens