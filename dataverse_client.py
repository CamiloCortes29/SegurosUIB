import os
import requests
import msal
import json
from config_manager import get_config

# --- Configuración de Dataverse y Autenticación ---
# Obtener la configuración desde config.json
dataverse_config = get_config('dataverse')

RESOURCE = dataverse_config.get('resource')
CLIENT_ID = dataverse_config.get('client_id')
CLIENT_SECRET = dataverse_config.get('client_secret')
AUTHORITY = f"https://login.microsoftonline.com/{dataverse_config.get('tenant_id')}"

# --- Cliente de Autenticación (Cache para el Token) ---
# Se crea una sola instancia para reutilizar el token cacheado
cca = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

def get_dataverse_token():
    """
    Obtiene un token de acceso para la API de Dataverse.
    Utiliza MSAL para manejar la autenticación y el cacheo del token.
    """
    # Busca un token en la caché
    token_result = cca.acquire_token_silent([f"{RESOURCE}/.default"], account=None)

    # Si no hay token en caché o ha expirado, solicita uno nuevo
    if not token_result:
        token_result = cca.acquire_token_for_client(scopes=[f"{RESOURCE}/.default"])

    # Verifica si se obtuvo el token
    if "access_token" in token_result:
        return token_result['access_token']
    else:
        # Lanza un error si la autenticación falla
        error_details = token_result.get("error_description", "No se pudo obtener el token de acceso.")
        raise Exception(f"Error de autenticación con Dataverse: {error_details}")

def get_headers():
    """
    Construye los encabezados estándar para las solicitudes a la API de Dataverse.
    """
    token = get_dataverse_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Prefer": "return=representation" # Pide a Dataverse que devuelva el registro creado/actualizado
    }

def create_record(table_name, data):
    """
    Crea un nuevo registro en una tabla de Dataverse.

    Args:
        table_name (str): El nombre lógico de la tabla en Dataverse (ej. "cr1a3_remisiones").
        data (dict): Un diccionario con los datos del registro a crear.

    Returns:
        dict: El registro creado, devuelto por la API de Dataverse.
    """
    api_url = f"{RESOURCE}/api/data/v9.2/{table_name}"
    headers = get_headers()

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Lanza una excepción para errores HTTP (4xx o 5xx)
        return response.json()
    except requests.exceptions.HTTPError as err:
        # Agrega más detalles al error
        raise Exception(f"Error HTTP al crear registro en '{table_name}': {err.response.status_code} - {err.response.text}")
    except Exception as e:
        raise Exception(f"Error inesperado al crear registro en '{table_name}': {str(e)}")

def get_records(table_name, select_columns=None, filter_query=None, order_by=None, top=None):
    """
    Obtiene registros de una tabla de Dataverse con opciones de consulta.

    Args:
        table_name (str): El nombre lógico de la tabla.
        select_columns (list, optional): Columnas a seleccionar. Defaults to None.
        filter_query (str, optional): Filtro OData. Defaults to None.
        order_by (str, optional): Campo para ordenar. Defaults to None.
        top (int, optional): Número de registros a obtener. Defaults to None.

    Returns:
        list: Una lista de diccionarios, donde cada uno es un registro.
    """
    api_url = f"{RESOURCE}/api/data/v9.2/{table_name}"
    headers = get_headers()
    params = {}

    if select_columns:
        params["$select"] = ",".join(select_columns)
    if filter_query:
        params["$filter"] = filter_query
    if order_by:
        params["$orderby"] = order_by
    if top:
        params["$top"] = top

    try:
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("value", [])
    except requests.exceptions.HTTPError as err:
        raise Exception(f"Error HTTP al obtener registros de '{table_name}': {err.response.status_code} - {err.response.text}")
    except Exception as e:
        raise Exception(f"Error inesperado al obtener registros de '{table_name}': {str(e)}")

def update_record(table_name, record_id, data):
    """
    Actualiza un registro existente en una tabla de Dataverse.

    Args:
        table_name (str): El nombre lógico de la tabla.
        record_id (str): El GUID del registro a actualizar.
        data (dict): Un diccionario con los campos a actualizar.

    Returns:
        dict: El registro actualizado, devuelto por la API.
    """
    # En Dataverse, el ID se pasa en la URL entre paréntesis
    api_url = f"{RESOURCE}/api/data/v9.2/{table_name}({record_id})"
    headers = get_headers()

    try:
        # PATCH se usa para actualizaciones parciales
        response = requests.patch(api_url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        # La respuesta para una actualización exitosa puede no tener cuerpo (204 No Content)
        # o devolver el objeto completo si se usó 'Prefer: return=representation'
        if response.status_code == 204:
            return {"status": "success", "message": "Registro actualizado correctamente."}
        return response.json()
    except requests.exceptions.HTTPError as err:
        raise Exception(f"Error HTTP al actualizar registro '{record_id}' en '{table_name}': {err.response.status_code} - {err.response.text}")
    except Exception as e:
        raise Exception(f"Error inesperado al actualizar registro '{record_id}' en '{table_name}': {str(e)}")

def delete_record(table_name, record_id):
    """
    Elimina un registro de una tabla de Dataverse.

    Args:
        table_name (str): El nombre lógico de la tabla.
        record_id (str): El GUID del registro a eliminar.

    Returns:
        bool: True si la eliminación fue exitosa.
    """
    api_url = f"{RESOURCE}/api/data/v9.2/{table_name}({record_id})"
    headers = get_headers()

    try:
        response = requests.delete(api_url, headers=headers)
        response.raise_for_status()
        # Una eliminación exitosa devuelve 204 No Content
        return response.status_code == 204
    except requests.exceptions.HTTPError as err:
        raise Exception(f"Error HTTP al eliminar registro '{record_id}' en '{table_name}': {err.response.status_code} - {err.response.text}")
    except Exception as e:
        raise Exception(f"Error inesperado al eliminar registro '{record_id}' en '{table_name}': {str(e)}")