# -*- coding: utf-8 -*-
"""
Script para consolidar vigencias y facturación para tabla dinámica.
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--sheet", default=0)
    parser.add_argument("--output", default="resumen_pivot.xlsx")
    parser.add_argument("--col-asegurado", default="Asegurado")
    parser.add_argument("--col-ramo", default="Ramo")
    parser.add_argument("--col-notacob", default="NotaCob")
    parser.add_argument("--col-anexo", default="Anexo NC")
    parser.add_argument("--col-fv", default="Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP")
    parser.add_argument("--col-tipomvto", default="Tipo Mvto")
    args = parser.parse_args()

    if not Path(args.input).exists(): return

    df = pd.read_excel(args.input, sheet_name=args.sheet, engine="openpyxl")

    COL_ASEG, COL_RAMO, COL_NOTA = args.col_asegurado, args.col_ramo, args.col_notacob
    COL_ANEX, COL_FV, COL_SUB, COL_MVTO = args.col_anexo, args.col_fv, args.col_subtotal, args.col_tipomvto

    df[COL_FV] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")
    df[COL_SUB] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)

    consol_cols = [COL_NOTA, COL_ANEX, COL_MVTO, COL_ASEG, COL_RAMO, COL_FV]
    df_consol = df.groupby(consol_cols, dropna=False)[COL_SUB].sum().reset_index()

    df_2026 = df_consol[df_consol[COL_FV].dt.year == 2026].copy()
    df_others = df_consol[df_consol[COL_FV].dt.year < 2026].copy()

    results = []
    for idx, row in df_2026.iterrows():
        mask = (df_others[COL_ASEG] == row[COL_ASEG]) & (df_others[COL_RAMO] == row[COL_RAMO])
        potential_prev = df_others[mask]

        if not potential_prev.empty:
            prev_row = potential_prev.loc[potential_prev[COL_FV].idxmax()]
            results.append({
                "Nombre Asegurado": row[COL_ASEG],
                "Fv Actual": row[COL_FV],
                "Tipo Mvto Actual": row[COL_MVTO],
                "Monto Actual": row[COL_SUB],
                "Fv Anterior": prev_row[COL_FV],
                "Tipo Mvto Anterior": prev_row[COL_MVTO],
                "Monto Anterior": prev_row[COL_SUB]
            })
        else:
            results.append({
                "Nombre Asegurado": row[COL_ASEG],
                "Fv Actual": row[COL_FV],
                "Tipo Mvto Actual": row[COL_MVTO],
                "Monto Actual": row[COL_SUB],
                "Fv Anterior": pd.NaT,
                "Tipo Mvto Anterior": "",
                "Monto Anterior": 0
            })

    df_res = pd.DataFrame(results)
    if df_res.empty: return

    # Formatear para Excel
    output_path = Path(args.output)

    # Usar ExcelWriter para aplicar formatos de número y fecha si fuera necesario,
    # pero aquí nos enfocamos en el orden y nombres de columnas de la imagen.
    column_order = ["Nombre Asegurado", "Fv Actual", "Tipo Mvto Actual", "Monto Actual", "Fv Anterior", "Tipo Mvto Anterior", "Monto Anterior"]
    df_res = df_res[column_order]

    # Renombrar para que coincida exactamente con la imagen si es necesario
    # Imagen muestra: Nombre Asegurado | Fv Actual | Tipo Mvto | Fv Anterior | Tipo Mvto
    # Y los montos debajo de Fv Actual y Fv Anterior. Esto sugiere una estructura de pivot o
    # simplemente columnas alineadas. El usuario pide "Tabla dinámica".

    df_res.to_excel(output_path, index=False)
    print(f"✅ Archivo consolidado generado: {output_path.resolve()}")

if __name__ == "__main__": main()
