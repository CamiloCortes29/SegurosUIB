# -*- coding: utf-8 -*-
"""
Script para consolidar vigencias y facturación para tabla dinámica.
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def main():
    parser = argparse.ArgumentParser(description="Consolidar vigencias y facturación por grupo.")
    parser.add_argument("--input", required=True, help="Ruta al archivo Excel de entrada")
    parser.add_argument("--sheet", default="0", help="Nombre de la hoja o índice (0=primera)")
    parser.add_argument("--output", default="resumen_pivot.xlsx", help="Ruta del Excel de salida")

    # Columnas de agrupación y metadatos
    parser.add_argument("--col-asegurado", default="Asegurado")
    parser.add_argument("--col-ramo", default="Ramo")
    parser.add_argument("--col-tipo-negocio", default="Tipo Negocio")
    parser.add_argument("--col-area", default="Area")
    parser.add_argument("--col-notacob", default="NotaCob")
    parser.add_argument("--col-anexo", default="Anexo NC")
    parser.add_argument("--col-fv", default="Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP")
    parser.add_argument("--col-tipomvto", default="Tipo Mvto")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: No existe el archivo de entrada: {input_path}")
        return

    sheet_val = args.sheet
    try:
        if str(sheet_val).isdigit():
            sheet_val = int(sheet_val)
    except:
        pass

    print(f"📥 Leyendo: {input_path} (hoja={sheet_val})")
    df = pd.read_excel(input_path, sheet_name=sheet_val, engine="openpyxl")

    COL_ASEG = args.col_asegurado
    COL_RAMO = args.col_ramo
    COL_TIPO_NEG = args.col_tipo_negocio
    COL_AREA = args.col_area
    COL_NOTA = args.col_notacob
    COL_ANEX = args.col_anexo
    COL_FV = args.col_fv
    COL_SUB = args.col_subtotal
    COL_MVTO = args.col_tipomvto

    # 1. Normalización
    df[COL_FV] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")
    df[COL_SUB] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)

    # Columnas que deben conservarse/agruparse
    consol_cols = [COL_NOTA, COL_ANEX, COL_MVTO, COL_ASEG, COL_RAMO, COL_TIPO_NEG, COL_AREA, COL_FV]

    # Validar columnas
    missing = [c for c in consol_cols + [COL_SUB] if c not in df.columns]
    if missing:
        print(f"❌ Error: Faltan columnas en el archivo: {missing}")
        return

    # Consolidar registros
    df_consol = df.groupby(consol_cols, dropna=False)[COL_SUB].sum().reset_index()

    # 2. Separar Actual (2026) y Potenciales Anteriores
    df_2026 = df_consol[df_consol[COL_FV].dt.year == 2026].copy()
    df_others = df_consol[df_consol[COL_FV].dt.year < 2026].copy()

    results = []
    for idx, row in df_2026.iterrows():
        # Búsqueda por Asegurado y Ramo para encontrar la vigencia anterior
        mask = (df_others[COL_ASEG] == row[COL_ASEG]) & (df_others[COL_RAMO] == row[COL_RAMO])
        potential_prev = df_others[mask]

        entry = {
            "Nombre Asegurado": row[COL_ASEG],
            "Ramo": row[COL_RAMO],
            "Tipo Negocio": row[COL_TIPO_NEG],
            "Area": row[COL_AREA],
            "Fv Actual": row[COL_FV],
            "Tipo Mvto Actual": row[COL_MVTO],
            "Monto Actual": row[COL_SUB],
        }

        if not potential_prev.empty:
            prev_row = potential_prev.loc[potential_prev[COL_FV].idxmax()]
            entry.update({
                "Fv Anterior": prev_row[COL_FV],
                "Tipo Mvto Anterior": prev_row[COL_MVTO],
                "Monto Anterior": prev_row[COL_SUB]
            })
        else:
            entry.update({
                "Fv Anterior": pd.NaT,
                "Tipo Mvto Anterior": "",
                "Monto Anterior": 0
            })
        results.append(entry)

    df_res = pd.DataFrame(results)
    if df_res.empty:
        print("⚠️ No se generaron registros de resumen.")
        return

    # 3. Exportar
    output_path = Path(args.output)
    column_order = [
        "Nombre Asegurado", "Ramo", "Tipo Negocio", "Area",
        "Fv Actual", "Tipo Mvto Actual", "Monto Actual",
        "Fv Anterior", "Tipo Mvto Anterior", "Monto Anterior"
    ]
    df_res = df_res[column_order]

    df_res.to_excel(output_path, index=False)
    print(f"✅ Proceso completado. Archivo generado: {output_path.resolve()}")

if __name__ == "__main__":
    main()
