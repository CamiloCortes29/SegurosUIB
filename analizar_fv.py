# -*- coding: utf-8 -*-
"""
Script para procesar vigencias y facturación por grupo.
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def fmt_money(x, include_space=True):
    try:
        if pd.isna(x) or x == "": return ""
        val = f"{int(round(float(x), 0)):,}".replace(",", ".")
        return f"$ {val}" if include_space else f"${val}"
    except: return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--sheet", default=0)
    parser.add_argument("--output", default="resultado_vigencias.xlsx")
    parser.add_argument("--col-asegurado", default="Asegurado")
    parser.add_argument("--col-notacob", default="NotaCob")
    parser.add_argument("--col-anexo", default="Anexo NC")
    parser.add_argument("--col-fv", default="Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP")
    parser.add_argument("--col-tipomvto", default=None)
    args = parser.parse_args()

    if not Path(args.input).exists(): return

    df = pd.read_excel(args.input, sheet_name=args.sheet, engine="openpyxl")
    COL_ASEG, COL_NOTA, COL_ANEX = args.col_asegurado, args.col_notacob, args.col_anexo
    COL_FV, COL_SUB, COL_MVTO = args.col_fv, args.col_subtotal, args.col_tipomvto

    df["_ASEG_N"]  = df[COL_ASEG].astype(str).str.strip().str.upper()
    df["_NOTA_N"]  = df[COL_NOTA].astype(str).str.strip().str.upper()
    df["_ANEXO_N"] = df[COL_ANEX].astype(str).fillna("").str.strip()
    df["_FV_DT"] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")
    df["_SUB_VAL"] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)
    grp_keys = ["_ASEG_N", "_NOTA_N", "_ANEXO_N"]

    # 1. Cálculos de base
    df["_TARGET_DATE_GLOBAL"] = df.groupby(grp_keys)["_FV_DT"].transform(lambda s: s[s.dt.year == 2026].min())

    df["_FV_PREV_GLOBAL"] = df.groupby(grp_keys)["_FV_DT"].transform(
        lambda s: s[s < df.loc[s.index, "_TARGET_DATE_GLOBAL"]].max()
    )

    df["_mask_prev"] = (df["_FV_DT"] == df["_FV_PREV_GLOBAL"]) & pd.notna(df["_FV_DT"])
    df["_sum_prev_total"] = df.groupby(grp_keys + ["_FV_PREV_GLOBAL"], dropna=False)["_SUB_VAL"].transform(lambda x: x[df.loc[x.index, "_mask_prev"]].sum())

    df["_mask_2026"] = (df["_FV_DT"].dt.year == 2026)
    df["_sum_2026_total"] = df.groupby(grp_keys)["_SUB_VAL"].transform(lambda x: x[df.loc[x.index, "_mask_2026"]].sum())

    # 2. Visibilidad según imagen
    df["Fecha 2026 (objetivo)"] = pd.NaT
    df.loc[df["_mask_2026"], "Fecha 2026 (objetivo)"] = df["_TARGET_DATE_GLOBAL"]

    # Fila donde se muestran los resúmenes (Primera fila de 2026 del grupo)
    df["_is_first_2026_row"] = df["_mask_2026"] & ~df.duplicated(subset=grp_keys + ["_mask_2026"])

    df["FV anterior a 2026 (fecha)"] = pd.NaT
    df.loc[df["_is_first_2026_row"], "FV anterior a 2026 (fecha)"] = df["_FV_PREV_GLOBAL"]

    df["Suma por FV (anterior)"] = ""
    df.loc[df["_is_first_2026_row"], "Suma por FV (anterior)"] = df.loc[df["_is_first_2026_row"], "_sum_prev_total"].apply(lambda x: fmt_money(x, include_space=True))

    df["Suma FV 2026"] = np.nan
    df.loc[df["_is_first_2026_row"], "Suma FV 2026"] = df.loc[df["_is_first_2026_row"], "_sum_2026_total"].round(0)

    # 3. Columnas de Display
    def build_prev_display(row):
        if not row["_is_first_2026_row"] or pd.isna(row["_FV_PREV_GLOBAL"]) or pd.isna(row["_sum_prev_total"]): return ""
        return f"{row['_FV_PREV_GLOBAL'].strftime('%d/%m/%Y')} - {fmt_money(row['_sum_prev_total'], include_space=False)}"

    def build_2026_display(row):
        if not row["_is_first_2026_row"] or pd.isna(row["_TARGET_DATE_GLOBAL"]) or pd.isna(row["_sum_2026_total"]): return ""
        return f"{row['_TARGET_DATE_GLOBAL'].strftime('%d/%m/%Y')} — {fmt_money(row['_sum_2026_total'], include_space=True)}"

    df["Fecha FV Anterior (mostrar)"] = df.apply(build_prev_display, axis=1)
    df["FV 2026 (mostrar)"] = df.apply(build_2026_display, axis=1)

    # 4. Exportar
    display_cols = ["Fecha 2026 (objetivo)", "FV anterior a 2026 (fecha)", "Suma por FV (anterior)", "Suma FV 2026", "Fecha FV Anterior (mostrar)", "FV 2026 (mostrar)"]
    df_final = df[[c for c in df.columns if not c.startswith("_") and c not in display_cols] + display_cols]

    # Ensure Suma FV 2026 is exported without decimals where possible
    if "Suma FV 2026" in df_final.columns:
        df_final["Suma FV 2026"] = df_final["Suma FV 2026"].astype(object)
        df_final.loc[df_final["Suma FV 2026"].notna(), "Suma FV 2026"] = df_final.loc[df_final["Suma FV 2026"].notna(), "Suma FV 2026"].astype(int)

    df_final.to_excel(args.output, index=False)
    print("✅ Proceso completado exitosamente.")

if __name__ == "__main__": main()
