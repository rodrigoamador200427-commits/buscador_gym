import pandas as pd
import glob

# Lee todos los archivos que empiezan con FOOD-DATA-GROUP
archivos = glob.glob("FOOD-DATA-GROUP*.csv")
df_lista = [pd.read_csv(archivo) for archivo in archivos]

# Une todos los archivos en uno solo
df_final = pd.concat(df_lista, ignore_index=True)

# Exporta el resultado
df_final.to_csv("alimentos_maestro.csv", index=False)