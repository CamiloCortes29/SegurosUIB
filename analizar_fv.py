# -*- coding: utf-8 -*-
"""
Cálculos de:
- Fecha 2026 (objetivo)  = primera Fecha FV en 2026 por grupo
- FV anterior a 2026     = máxima Fecha FV < objetivo por grupo
- Suma por FV (anterior) = suma Subtotal COP donde Fecha FV == FV anterior (solo 1a línea)
- Suma FV 2026           = suma Subtotal COP en 2026 por grupo (solo 1a línea)
- Columnas de display con formato: "dd/mm/aaaa — $ X"
Agrupación por: (Asegurado, NotaCob) -> Se removió Anexo NC para evitar fragmentación.

Autor: Camilo + Jules
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def fmt_money(x):
    try:
        if pd.isna(x) or x == 0:
            return ""
        return f"$ {int(round(x, 0)):,}".replace(",", ".")
    except Exception:
        return ""

def main():
    parser = argparse.ArgumentParser(description="Calcular FV 2026 y FV anterior por grupo.")
    parser.add_argument("--input", required=True, help="Ruta al archivo Excel de entrada")
    parser.add_argument("--sheet", default=0, help="Hoja (nombre o índice)")
    parser.add_argument("--output", default="salida_con_fv.xlsx", help="Ruta de salida")

    # Columnas
    parser.add_argument("--col-asegurado", default="Asegurado")
    parser.add_argument("--col-notacob", default="NotaCob")
    parser.add_argument("--col-fv", default="Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP")
    parser.add_argument("--col-tipomvto", default="Tipo Mvto")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: No existe el archivo: {input_path}")
        return

    print(f"📥 Leyendo: {input_path}")
    df = pd.read_excel(input_path, sheet_name=args.sheet, engine="openpyxl")

    COL_ASEG = args.col_asegurado
    COL_NOTA = args.col_notacob
    COL_FV   = args.col_fv
    COL_SUB  = args.col_subtotal
    COL_MVTO = args.col_tipomvto

    # Validar
    required = [COL_ASEG, COL_NOTA, COL_FV, COL_SUB]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"❌ Error: Faltan columnas: {missing}")
        return

    # Normalización
    df["_FV"] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")
    df["_SUB"] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)

    # Agrupación sugerida: Asegurado y NotaCob
    grp = [COL_ASEG, COL_NOTA]

    # 1. Fecha 2026 (objetivo)
    df["Fecha 2026 (objetivo)"] = df.groupby(grp)["_FV"].transform(lambda s: s[s.dt.year == 2026].min())

    # 2. FV anterior a 2026 (Máxima fecha < objetivo)
    def get_prev_date(group):
        if group["Fecha 2026 (objetivo)"].empty: return pd.Series(pd.NaT, index=group.index)
        target = group["Fecha 2026 (objetivo)"].iloc[0]
        if pd.isna(target): return pd.Series(pd.NaT, index=group.index)
        prev_dates = group.loc[group["_FV"] < target, "_FV"]
        return pd.Series(prev_dates.max() if not prev_dates.empty else pd.NaT, index=group.index)

    df["FV anterior a 2026 (fecha)"] = df.groupby(grp, group_keys=False).apply(get_prev_date)

    # 3. Sumas
    df["_sum_2026"] = df.groupby(grp)["_SUB"].transform(lambda s: s[df.loc[s.index, "_FV"].dt.year == 2026].sum())

    mask_prev = (df["_FV"] == df["FV anterior a 2026 (fecha)"]) & df["FV anterior a 2026 (fecha)"].notna()
    df["_sum_prev"] = df.groupby(grp)["_SUB"].transform(lambda s: s[mask_prev.loc[s.index]].sum())

    # 4. Formatear Display (Solo en la primera fila de 2026 del grupo)
    df["_is_first_2026"] = False
    for name, group in df.groupby(grp):
        idx_2026 = group[group["_FV"].dt.year == 2026].index
        if not idx_2026.empty:
            df.at[idx_2026[0], "_is_first_2026"] = True

    def build_display(row, is_2026=True):
        if not row["_is_first_2026"]: return ""

        date_col = "Fecha 2026 (objetivo)" if is_2026 else "FV anterior a 2026 (fecha)"
        sum_col = "_sum_2026" if is_2026 else "_sum_prev"

        if pd.isna(row[date_col]): return ""

        txt = f"{row[date_col].strftime('%d/%m/%Y')} — {fmt_money(row[sum_col])}"
        if COL_MVTO in df.columns and pd.notna(row[COL_MVTO]):
            txt += f" — {str(row[COL_MVTO])}"
        return txt

    df["FV 2026 (mostrar)"] = df.apply(lambda r: build_display(r, True), axis=1)
    df["Fecha FV Anterior (mostrar)"] = df.apply(lambda r: build_display(r, False), axis=1)

    # Limpieza
    orig_cols = [c for c in df.columns if not c.startswith('_')]
    new_cols = [
        "Fecha 2026 (objetivo)", "FV anterior a 2026 (fecha)",
        "FV 2026 (mostrar)", "Fecha FV Anterior (mostrar)"
    ]
    # Enforce order and unique columns
    df_final = df.loc[:, ~df.columns.duplicated()][orig_cols + [c for c in new_cols if c not in orig_cols]].copy()

    print(f"💾 Guardando: {args.output}")
    df_final.to_excel(args.output, index=False)
    print("✅ Proceso terminado con éxito.")

if __name__ == "__main__":
    main()
