import os
import pandas as pd
import dataverse_client
import config_manager
from datetime import datetime

# --- Configuración ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dataverse_config = config_manager.get_config('dataverse')
TABLE_NAMES = dataverse_config.get('tables', {})

# Mapeo de archivos Excel a tablas de Dataverse
FILES_TO_MIGRATE = {
    'remisiones': os.path.join(BASE_DIR, 'remisiones.xlsx'),
    'cartera': os.path.join(BASE_DIR, 'DATOS_CARTERA', 'cartera_procesada.xlsx'),
    'vencimientos': os.path.join(BASE_DIR, 'DATOS_VENCIMIENTOS', 'vencimientos_procesados.xlsx'),
    'prospectos': os.path.join(BASE_DIR, 'DATOS_PROSPECTOS', 'prospectos.xlsx'),
    'cobros': os.path.join(BASE_DIR, 'cobros.xlsx'),
    'siniestros': os.path.join(BASE_DIR, 'siniestros.xlsx'),
}

def clean_data(df, entity_name):
    """
    Limpia y transforma un DataFrame para que coincida con el esquema de Dataverse.
    Esta función debe ser adaptada según las necesidades de cada entidad.
    """
    # Nombres de columnas a minúsculas y sin espacios/caracteres especiales
    df.columns = [col.lower().replace(' ', '_').replace('$', 'monto').replace('%', 'porcentaje') for col in df.columns]

    if entity_name == 'remisiones':
        # Ejemplo de transformaciones para remisiones
        for field in ['renovacion', 'negocio_nuevo', 'renovable', 'modificacion', 'anexo_checkbox', 'policy_number_modified']:
            if field in df.columns:
                df[field] = df[field].astype(str).str.lower() == 'si'

        for date_field in ['fecha_recepcion', 'fecha_inicio', 'fecha_fin', 'fecha_limite_pago', 'fecha_registro']:
             if date_field in df.columns:
                df[date_field] = pd.to_datetime(df[date_field], errors='coerce').dt.strftime('%Y-%m-%d').replace({pd.NaT: None})

    if entity_name == 'prospectos':
        # Renombrar columnas para que coincidan con Dataverse
        df.rename(columns={
            'nombre_cliente': 'NombreCliente',
            'responsable_tecnico': 'ResponsableTecnico',
            'responsable_comercial': 'ResponsableComercial',
            'fecha_de_cotizacion': 'Fecha_de_Cotizacion',
            'fecha_inicio_poliza': 'Fecha_inicio_poliza',
            'comision_porcentaje': 'Comision_porcentaje',
            'comision_monto': 'Comision_monto',
            'fecha_creacion': 'FechaCreacion'
        }, inplace=True)
        if 'es_tpp' in df.columns:
            df['es_TPP'] = df['es_tpp'].astype(str).str.lower() == 'si'

    # Reemplazar NaN/NaT por None, que se traduce a null en JSON
    df = df.where(pd.notnull(df), None)
    return df

def migrate_entity(entity_key, file_path, table_name):
    """
    Migra los datos de un único archivo Excel a su tabla correspondiente en Dataverse.
    """
    print(f"\n--- Iniciando migración para: {entity_key.upper()} ---")

    if not os.path.exists(file_path):
        print(f"Archivo no encontrado: {file_path}. Saltando migración.")
        return

    if not table_name:
        print(f"Nombre de tabla para '{entity_key}' no encontrado en config.json. Saltando migración.")
        return

    try:
        df = pd.read_excel(file_path)
        print(f"Se encontraron {len(df)} registros en {os.path.basename(file_path)}.")

        # Limpiar y transformar los datos
        df_cleaned = clean_data(df.copy(), entity_key)

        # Convertir DataFrame a una lista de diccionarios
        records_to_migrate = df_cleaned.to_dict(orient='records')

        success_count = 0
        error_count = 0

        for i, record in enumerate(records_to_migrate):
            try:
                # Eliminar claves con valores nulos para no enviar datos innecesarios
                payload = {k: v for k, v in record.items() if v is not None}

                # Aquí se podrían añadir validaciones antes de enviar
                # Por ejemplo, verificar si un registro con una clave única ya existe.

                dataverse_client.create_record(table_name, payload)
                success_count += 1
                print(f"  Registro {i+1}/{len(records_to_migrate)} migrado exitosamente.")

            except Exception as e:
                error_count += 1
                print(f"  ERROR al migrar registro {i+1}: {e}")
                # Opcional: guardar el registro fallido en un archivo de log
                with open('migration_errors.log', 'a') as f:
                    f.write(f"[{datetime.now()}] Error en {entity_key} - Registro: {record} - Error: {e}\n")

        print(f"--- Migración para {entity_key.upper()} completada ---")
        print(f"Resultados: {success_count} registros exitosos, {error_count} errores.")

    except Exception as e:
        print(f"Error CRÍTICO durante la migración de {entity_key}: {e}")

def main():
    """
    Función principal que orquesta la migración de todas las entidades.
    """
    print("==============================================")
    print("INICIO DEL SCRIPT DE MIGRACIÓN DE DATOS A DATAVERSE")
    print("==============================================")
    print("Este script leerá los archivos Excel locales y subirá los datos a las tablas de Dataverse.")
    print("Asegúrese de que el 'dataverse_client' esté correctamente configurado en 'config.json'.")

    # Limpiar archivo de log de errores de migraciones anteriores
    if os.path.exists('migration_errors.log'):
        os.remove('migration_errors.log')

    for entity_key, file_path in FILES_TO_MIGRATE.items():
        table_name = TABLE_NAMES.get(entity_key)
        migrate_entity(entity_key, file_path, table_name)

    print("\n==============================================")
    print("FIN DEL SCRIPT DE MIGRACIÓN")
    print("==============================================")
    print("Revise el archivo 'migration_errors.log' si se reportaron errores.")

if __name__ == '__main__':
    # Esta confirmación previene ejecuciones accidentales
    confirm = input("¿Está seguro de que desea iniciar la migración de datos de Excel a Dataverse? (s/n): ")
    if confirm.lower() == 's':
        main()
    else:
        print("Migración cancelada por el usuario.")