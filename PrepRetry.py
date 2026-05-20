import pandas as pd
import subprocess

# Definir rutas de archivos
input_file = "log/res_orchitems.csv"
output_file = "log/Retry_OrderItems.csv"
script_to_run = "PrepRetry.py"

# Cargar el archivo en un DataFrame de forma segura
try:
    df = pd.read_csv(input_file)
    print(f"Archivo '{input_file}' cargado exitosamente.")
except FileNotFoundError:
    print(f"Error: El archivo '{input_file}' no se encuentra.")
    exit()
except Exception as e:
    print(f"Error al leer '{input_file}': {str(e)}")
    exit()

# Filtrar registros donde "state" sea "Fatally Failed"
filtered_df = df[df["State"] == "Fatally Failed"]

# Verificar si hay registros filtrados
if filtered_df.empty:
    print("No hay registros con estado 'Fatally Failed'. No se generará archivo de salida.")
    exit()

# Crear nuevo DataFrame con las columnas requeridas
retry_df = filtered_df[["Id"]].copy()
retry_df["State"] = "ready"

# Guardar el nuevo archivo CSV en la misma ubicación
try:
    retry_df.to_csv(output_file, index=False)
    print(f"Archivo '{output_file}' creado exitosamente con {len(retry_df)} registros.")
except Exception as e:
    print(f"Error al guardar '{output_file}': {str(e)}")
    exit()