import os
import matplotlib.pyplot as plt
from collections import Counter
from extractor import extract_corpus
from nlp_processor import clean_and_stem

def plot_zipf(frequencies, output_dir):
    ranks = range(1, len(frequencies) + 1)
    freqs = [f for word, f in frequencies]
    
    plt.figure(figsize=(10, 6))
    plt.loglog(ranks, freqs, marker='.', linestyle='none', color='b')
    plt.title('Ley de Zipf - Corpus Fitness')
    plt.xlabel('Rango de la palabra (Log)')
    plt.ylabel('Frecuencia (Log)')
    plt.grid(True, which="both", ls="--")
    plt.savefig(os.path.join(output_dir, 'zipf_law.png'))
    plt.close()

def plot_heaps(tokens_processed, vocab_sizes, output_dir):
    plt.figure(figsize=(10, 6))
    plt.plot(tokens_processed, vocab_sizes, color='r')
    plt.title('Ley de Heaps - Crecimiento del Vocabulario')
    plt.xlabel('Total de palabras procesadas (N)')
    plt.ylabel('Tamaño del vocabulario único (V)')
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'heaps_law.png'))
    plt.close()

def main():
    print("Iniciando Fase 1: Procesamiento y Análisis...")
    
    # Asegurar que exista la carpeta de gráficas
    output_dir = '../assets/graficas'
    os.makedirs(output_dir, exist_ok=True)

    # 1. Extraer datos
    corpus = extract_corpus()
    
    # Variables para estadísticas y Heaps
    all_stems = []
    unique_vocab = set()
    tokens_processed = []
    vocab_sizes = []
    token_count = 0

    print("Procesando NLP (Stemming y limpieza)... esto puede tardar unos segundos.")
    # 2. Procesar cada documento
    for doc in corpus:
        stems = clean_and_stem(doc)
        all_stems.extend(stems)
        
        # Calcular Heaps dinámicamente
        for stem in stems:
            token_count += 1
            unique_vocab.add(stem)
            if token_count % 1000 == 0:  # Registrar puntos cada 1000 palabras
                tokens_processed.append(token_count)
                vocab_sizes.append(len(unique_vocab))

    # 3. Calcular frecuencias para Zipf
    stem_counts = Counter(all_stems)
    frequencies = stem_counts.most_common()

    print(f"Total de palabras procesadas: {token_count}")
    print(f"Tamaño del vocabulario (raíces únicas): {len(unique_vocab)}")
    print("Top 10 raíces más comunes:")
    for word, freq in frequencies[:10]:
        print(f" - {word}: {freq}")

    # 4. Generar Gráficas
    print("Generando gráficas de Zipf y Heaps...")
    plot_zipf(frequencies, output_dir)
    plot_heaps(tokens_processed, vocab_sizes, output_dir)
    print(f"¡Fase 1 completada! Gráficas guardadas en {os.path.abspath(output_dir)}")

if __name__ == "__main__":
    main()