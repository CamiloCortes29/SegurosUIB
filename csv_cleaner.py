#!/usr/bin/env python3
import argparse
import csv
import logging
import os
import re
import sys
from datetime import datetime
import pandas as pd
import numpy as np

# Intentar importar chardet para detección de codificación
try:
    import chardet
except ImportError:
    chardet = None

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def to_snake_case(name):
    """Convierte una cadena a snake_case legible."""
    # Eliminar acentos y caracteres especiales comunes
    name = str(name).lower()
    replacements = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ñ", "n"), ("ü", "u")
    )
    for a, b in replacements:
        name = name.replace(a, b)

    # Reemplazar caracteres no alfanuméricos por guiones bajos
    name = re.sub(r'[^a-z0-9]+', '_', name)
    # Eliminar guiones bajos duplicados
    name = re.sub(r'_+', '_', name)
    # Recortar guiones bajos al inicio y al final
    return name.strip('_')

def clean_text(text):
    """Limpia espacios y elimina caracteres de control de una cadena."""
    if not isinstance(text, str):
        if pd.isna(text):
            return text
        return str(text)
    # Eliminar caracteres de control (excepto saltos de línea y tabuladores si se desea)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Recortar espacios inicio/fin
    text = text.strip()
    # Normalizar espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    return text

def detect_encoding(file_path):
    """Detecta la codificación del archivo."""
    # Primero probar con UTF-8 con BOM (utf-8-sig)
    try:
        with open(file_path, 'rb') as f:
            rawdata = f.read(10000)
            if rawdata.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
    except Exception:
        pass

    if chardet:
        try:
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read(10000))
                return result['encoding']
        except Exception as e:
            logger.warning(f"Error detectando codificación con chardet: {e}")

    # Probamos leer una pequeña parte con utf-8 para ver si falla
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(10000)
        return 'utf-8'
    except UnicodeDecodeError:
        return 'latin-1'

def main():
    parser = argparse.ArgumentParser(description='Script para limpiar archivos CSV.')
    parser.add_argument('input', help='Ruta del archivo CSV de entrada')
    parser.add_argument('--output', help='Ruta del archivo CSV de salida (opcional)')
    parser.add_argument('--date-iso', action='store_true', help='Estandarizar formatos de fecha a ISO YYYY-MM-DD')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"El archivo {args.input} no existe.")
        sys.exit(1)

    if not args.input.lower().endswith('.csv'):
        logger.error("El archivo no tiene extensión .csv.")
        sys.exit(1)

    # 1 & 2. Codificación
    encoding = detect_encoding(args.input)
    logger.info(f"Codificación detectada: {encoding}")

    try:
        # 3. Detectar delimitador
        delimiter = ','
        try:
            with open(args.input, 'r', encoding=encoding, errors='replace') as f:
                content_sample = f.read(10000)
                if not content_sample:
                    logger.error("El archivo está vacío.")
                    sys.exit(1)

                sniffer = csv.Sniffer()
                # Probar delimitadores comunes
                dialect = sniffer.sniff(content_sample, delimiters=',;\t|')
                delimiter = dialect.delimiter
                logger.info(f"Delimitador detectado: '{delimiter}'")
        except Exception as e:
            logger.warning(f"No se pudo detectar el delimitador automáticamente: {e}. Usando coma por defecto.")

        # 4. Cargar con pandas
        try:
            df = pd.read_csv(args.input, sep=delimiter, encoding=encoding, dtype=str, engine='python', on_bad_lines='warn')
        except UnicodeDecodeError:
            logger.warning(f"Fallo al leer con {encoding}, intentando con latin-1")
            df = pd.read_csv(args.input, sep=delimiter, encoding='latin-1', dtype=str, engine='python', on_bad_lines='warn')

        initial_rows, initial_cols = df.shape
        logger.info(f"Cargadas {initial_rows} filas y {initial_cols} columnas.")

        # 5. Limpieza
        # Aplicar limpieza de texto a los nombres de las columnas antes de snake_case
        df.columns = [to_snake_case(clean_text(col)) for col in df.columns]

        # Convertir NAs comunes a NaN ANTES de limpiar texto para identificarlos bien
        nas_comunes = ['nan', 'null', 'none', 'n/a', 'na', '']

        # Limpiar texto en todas las celdas
        df = df.map(clean_text)

        # Reemplazar NAs comunes por NaN real
        for na_val in nas_comunes:
            df = df.replace(to_replace=re.compile(f'^{re.escape(na_val)}$', re.IGNORECASE), value=np.nan)

        # Eliminar filas y columnas completamente vacías
        df.dropna(how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)

        # Quitar duplicados exactos
        df.drop_duplicates(inplace=True)

        # 6. Opcional: Estandarizar fechas
        if args.date_iso:
            for col in df.columns:
                if 'fecha' in col.lower():
                    try:
                        temp_dates = pd.to_datetime(df[col], errors='coerce')
                        if temp_dates.notna().any():
                            df[col] = temp_dates.dt.strftime('%Y-%m-%d')
                            logger.info(f"Columna '{col}' estandarizada a formato ISO.")
                    except Exception as e:
                        logger.debug(f"No se pudo estandarizar la columna de fecha '{col}': {e}")

        # 8. Resumen de limpieza
        final_rows, final_cols = df.shape

        logger.info("--- Resumen de Limpieza ---")
        logger.info(f"Filas: {initial_rows} -> {final_rows} (Eliminadas: {initial_rows - final_rows})")
        logger.info(f"Columnas: {initial_cols} -> {final_cols} (Eliminadas: {initial_cols - final_cols})")

        # 7. Guardar CSV limpio
        output_path = args.output if args.output else f"cleaned_{os.path.basename(args.input)}"
        df.to_csv(output_path, index=False, sep=delimiter, encoding='utf-8', lineterminator='\n')
        logger.info(f"Archivo guardado exitosamente en: {output_path}")

    except Exception as e:
        logger.error(f"Error crítico procesando el archivo: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
