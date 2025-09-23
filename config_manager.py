import os
import json

# Define la ruta base de la configuración relativa a este archivo.
# Esto hace que el sistema de configuración sea más robusto.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

# Asegurarse de que el directorio de configuración exista.
os.makedirs(CONFIG_DIR, exist_ok=True)

def get_list_names():
    """
    Escanea el directorio de configuración y devuelve los nombres base de los
    archivos JSON (que corresponden a los nombres de las listas).
    """
    try:
        files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]
        # Devuelve el nombre del archivo sin la extensión .json
        return [os.path.splitext(f)[0] for f in files]
    except FileNotFoundError:
        return []

def get_list(list_name):
    """
    Carga y devuelve una lista desde su archivo JSON correspondiente.
    El nombre de la lista corresponde al nombre del archivo sin la extensión .json.
    """
    file_path = os.path.join(CONFIG_DIR, f"{list_name}.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Si el archivo no se encuentra o está corrupto, devuelve una lista vacía.
        return []

def save_list(list_name, data):
    """
    Guarda una lista (data) en su archivo JSON correspondiente.
    Sobrescribe el archivo si ya existe.
    """
    file_path = os.path.join(CONFIG_DIR, f"{list_name}.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error al guardar la lista '{list_name}' en {file_path}: {e}")
        return False
