# -*- coding: utf-8 -*-
"""
Script para procesar vigencias y facturación por grupo.
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def fmt_money(x):
    try:
        if pd.isna(x) or x == "": return ""
        return f"$ {int(round(float(x), 0)):,}".replace(",", ".")
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

    # 1. Fecha 2026 Objetivo
    df["Fecha 2026 (objetivo)"] = df.groupby(grp_keys)["_FV_DT"].transform(lambda s: s[s.dt.year == 2026].min())

    # 2. FV Anterior (máxima < objetivo)
    # Using a slightly different approach to avoid the ValueError
    def get_max_prev(g):
        target = g["Fecha 2026 (objetivo)"].iloc[0]
        if pd.isna(target):
            return pd.Series([pd.NaT] * len(g), index=g.index)
        prev_dates = g.loc[g["_FV_DT"] < target, "_FV_DT"]
        max_prev = prev_dates.max() if not prev_dates.empty else pd.NaT
        return pd.Series([max_prev] * len(g), index=g.index)

    # Use apply but extract the series correctly to avoid multi-column insertion attempt
    prev_fv_series = df.groupby(grp_keys, group_keys=False).apply(get_max_prev).squeeze()
    # In some pandas versions/cases, squeeze might not be enough or behaves differently.
    # Let's ensure it's a series.
    if isinstance(prev_fv_series, pd.DataFrame):
        prev_fv_series = prev_fv_series.iloc[:, 0]

    df["_FV_PREV_RAW"] = prev_fv_series

    # 3. Sumas
    df["_mask_prev"] = (df["_FV_DT"] == df["_FV_PREV_RAW"]) & pd.notna(df["_FV_DT"])
    df["_sum_prev_total"] = df.groupby(grp_keys + ["_FV_PREV_RAW"], dropna=False)["_SUB_VAL"].transform(lambda x: x[df.loc[x.index, "_mask_prev"]].sum())

    df["_mask_2026"] = (df["_FV_DT"].dt.year == 2026)
    df["_sum_2026_total"] = df.groupby(grp_keys)["_SUB_VAL"].transform(lambda x: x[df.loc[x.index, "_mask_2026"]].sum())

    # 4. Fila Objetivo (donde se muestra el resumen)
    df["_is_target_row"] = (df["_FV_DT"] == df["Fecha 2026 (objetivo)"]) & pd.notna(df["_FV_DT"])
    df["_is_first_target_row"] = df["_is_target_row"] & ~df.duplicated(subset=grp_keys + ["_is_target_row"])
    df.loc[~df["_is_target_row"], "_is_first_target_row"] = False

    df["Suma por FV (anterior)"] = np.nan
    df.loc[df["_is_first_target_row"], "Suma por FV (anterior)"] = df["_sum_prev_total"]

    df["Suma FV 2026"] = np.nan
    df.loc[df["_is_first_target_row"], "Suma FV 2026"] = df["_sum_2026_total"]

    df["FV anterior a 2026 (fecha)"] = pd.NaT
    df.loc[df["_is_first_target_row"], "FV anterior a 2026 (fecha)"] = df["_FV_PREV_RAW"]

    # 5. Display
    def build_display(row, d_val, s_val):
        if not row["_is_first_target_row"] or pd.isna(d_val) or pd.isna(s_val): return ""
        res = f"{d_val.strftime('%d/%m/%Y')} — {fmt_money(s_val)}"
        if COL_MVTO and COL_MVTO in df.columns:
            mv = str(row[COL_MVTO]).strip()
            if mv and mv.lower() != "nan": res += f" — {mv}"
        return res

    df["Fecha FV Anterior (mostrar)"] = df.apply(lambda r: build_display(r, r["_FV_PREV_RAW"], r["_sum_prev_total"]), axis=1)
    df["FV 2026 (mostrar)"] = df.apply(lambda r: build_display(r, r["Fecha 2026 (objetivo)"], r["_sum_2026_total"]), axis=1)

    # 6. Exportar
    display_cols = ["Fecha 2026 (objetivo)", "FV anterior a 2026 (fecha)", "Suma por FV (anterior)", "Suma FV 2026", "Fecha FV Anterior (mostrar)", "FV 2026 (mostrar)"]
    df_final = df[[c for c in df.columns if not c.startswith("_") and c not in display_cols] + display_cols]
    df_final.to_excel(args.output, index=False)
    print("✅ Proceso completado.")

if __name__ == "__main__": main()
