import pandas as pd

# 1. Cargar el dataset original
df = pd.read_csv('megaGymDataset.csv')

# 2. Seleccionar las columnas útiles (AHORA INCLUYE 'Desc')
columnas_utiles = ['Title', 'Desc', 'BodyPart', 'Equipment', 'Level', 'Type']
df = df[columnas_utiles]

# 3. Diccionario de Mapeo
mapeo_musculos = {
    'Chest': 1,
    'Lats': 2,
    'Lower Back': 2,
    'Middle Back': 2,
    'Shoulders': 3,
    'Biceps': 4,
    'Triceps': 5,
    'Quadriceps': 6,
    'Hamstrings': 7,
    'Calves': 8,
    'Glutes': 9,
    'Abdominals': 10,
    'Forearms': 11
}

# 4. Aplicar el mapeo
df['grupo_id'] = df['BodyPart'].map(mapeo_musculos)
df = df.dropna(subset=['grupo_id']) # Elimina filas sin grupo muscular válido
df['grupo_id'] = df['grupo_id'].astype(int)

# 5. Renombrar columnas
df = df.rename(columns={
    'Title': 'nombre_en',
    'Desc': 'descripcion_en',
    'Equipment': 'equipamiento',
    'Level': 'nivel',
    'Type': 'modalidad'
})

df = df.drop('BodyPart', axis=1)

# 6. Crear columnas vacías para el español
df['nombre_es'] = ""
df['descripcion_es'] = ""

# 7. Ordenar columnas igual que en SQL
orden_columnas = ['nombre_es', 'nombre_en', 'descripcion_es', 'descripcion_en', 'grupo_id', 'modalidad', 'equipamiento', 'nivel']
df = df[orden_columnas]

# 8. Exportar
df.to_csv('ejercicios_limpios.csv', index=False)
print("¡Dataset limpio con descripciones exportado con éxito!")