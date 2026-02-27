# -*- coding: utf-8 -*-
"""
Cálculos de:
- Fecha 2026 (objetivo)  = primera Fecha FV en 2026 por grupo
- FV anterior a 2026     = máxima Fecha FV < objetivo por grupo
- Suma por FV (anterior) = suma Subtotal COP donde Fecha FV == FV anterior (solo 1a línea)
- Suma FV 2026           = suma Subtotal COP en 2026 por grupo (solo 1a línea)
- Columnas de display con formato: "dd/mm/aaaa — $ X"
Agrupación por: (Asegurado, NotaCob, Anexo NC)

Autor: Camilo + Jules
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np


def fmt_money(x):
    try:
        if pd.isna(x) or x == "":
            return ""
        return f"$ {int(round(float(x), 0)):,}".replace(",", ".")
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Calcular FV 2026 y FV anterior por grupo.")
    parser.add_argument("--input", required=True, help=r"Ruta al archivo Excel de entrada")
    parser.add_argument("--sheet", default=0, help="Nombre de la hoja o índice (0=primera)")
    parser.add_argument("--output", default="salida_con_fv.xlsx", help="Ruta del Excel de salida (.xlsx)")

    # Permitir personalizar nombres de columnas si difieren
    parser.add_argument("--col-asegurado", default="Asegurado", help="Columna de Asegurado")
    parser.add_argument("--col-notacob", default="NotaCob", help="Columna de NotaCob")
    parser.add_argument("--col-anexo", default="Anexo NC", help="Columna de Anexo NC")
    parser.add_argument("--col-fv", default="Fecha FV", help="Columna de Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP", help="Columna de Subtotal COP")
    parser.add_argument("--col-tipomvto", default=None, help="(Opcional) Tipo Mvto para mostrar en display")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de entrada: {input_path.resolve()}")

    # ----- Cargar -----
    sheet_name = args.sheet
    try:
        if isinstance(sheet_name, str) and sheet_name.isdigit():
            sheet_name = int(sheet_name)
    except Exception:
        pass

    print(f"📥 Leyendo: {input_path}  (hoja={sheet_name})")
    df = pd.read_excel(input_path, sheet_name=sheet_name, engine="openpyxl")

    # ----- Validar columnas esperadas -----
    COL_ASEG = args.col_asegurado
    COL_NOTA = args.col_notacob
    COL_ANEX = args.col_anexo
    COL_FV   = args.col_fv
    COL_SUB  = args.col_subtotal
    COL_MVTO = args.col_tipomvto

    missing = [c for c in [COL_ASEG, COL_NOTA, COL_ANEX, COL_FV, COL_SUB] if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas en el archivo: {missing}\n"
                       f"Columnas disponibles: {list(df.columns)}")

    # ----- Normalizaciones -----
    df["_ASEG_N"]  = df[COL_ASEG].astype(str).str.strip().str.upper()
    df["_NOTA_N"]  = df[COL_NOTA].astype(str).str.strip().str.upper()
    df["_ANEXO_N"] = df[COL_ANEX].astype(str).fillna("").str.strip()
    df["_FV"] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")
    df["_SUB"] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)

    grp = ["_ASEG_N", "_NOTA_N", "_ANEXO_N"]

    # ----- 1) Fecha 2026 (objetivo) -----
    df["Fecha 2026 (objetivo)"] = df.groupby(grp)["_FV"].transform(
        lambda s: s[s.dt.year == 2026].min() if any(s.dt.year == 2026) else pd.NaT
    )

    # ----- 2) FV anterior a 2026 (fecha) -----
    def get_prev_max(group):
        target = group["Fecha 2026 (objetivo)"].iloc[0]
        if pd.isna(target):
            return pd.Series([pd.NaT] * len(group), index=group.index)
        prev_dates = group.loc[group["_FV"] < target, "_FV"]
        res = prev_dates.max() if not prev_dates.empty else pd.NaT
        return pd.Series([res] * len(group), index=group.index)

    df["FV anterior a 2026 (fecha)"] = df.groupby(grp, group_keys=False).apply(get_prev_max)

    # ----- 3) Suma por FV (anterior) -----
    df["_is_prev"] = df["_FV"] == df["FV anterior a 2026 (fecha)"]
    df["Suma por FV (anterior)"] = df.groupby(grp + ["FV anterior a 2026 (fecha)"], dropna=False)["_SUB"].transform(
        lambda x: x[df.loc[x.index, "_is_prev"]].sum()
    )
    mask_prev_valid = pd.notna(df["FV anterior a 2026 (fecha)"])
    is_first_prev = ~df.duplicated(subset=grp + ["FV anterior a 2026 (fecha)"])
    df.loc[~(mask_prev_valid & is_first_prev), "Suma por FV (anterior)"] = np.nan

    # ----- 4) Suma FV 2026 -----
    df["_is_2026"] = df["_FV"].dt.year == 2026
    df["Suma FV 2026"] = df.groupby(grp)["_SUB"].transform(
        lambda x: x[df.loc[x.index, "_is_2026"]].sum()
    )
    mask_2026_valid = pd.notna(df["Fecha 2026 (objetivo)"])
    is_first_2026 = ~df.duplicated(subset=grp + ["Fecha 2026 (objetivo)"])
    df.loc[~(mask_2026_valid & is_first_2026), "Suma FV 2026"] = np.nan

    # ----- 5) Columnas de display -----
    def build_display(row, date_col, sum_col):
        d = row[date_col]
        s = row[sum_col]
        if pd.isna(d) or pd.isna(s):
            return ""
        txt = f"{d.strftime('%d/%m/%Y')} — {fmt_money(s)}"
        if COL_MVTO and COL_MVTO in df.columns and pd.notna(row[COL_MVTO]):
            mvto = str(row[COL_MVTO]).strip()
            if mvto:
                txt += f" — {mvto}"
        return txt

    df["Fecha FV Anterior (mostrar)"] = df.apply(
        lambda r: build_display(r, "FV anterior a 2026 (fecha)", "Suma por FV (anterior)"), axis=1
    )
    df["FV 2026 (mostrar)"] = df.apply(
        lambda r: build_display(r, "Fecha 2026 (objetivo)", "Suma FV 2026"), axis=1
    )

    # ----- 6) Limpieza y exportar -----
    drop_cols = ["_ASEG_N", "_NOTA_N", "_ANEXO_N", "_FV", "_SUB", "_is_prev", "_is_2026"]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True, errors="ignore")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"💾 Guardando: {output_path.resolve()}")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="resultado")

    print("✅ Proceso completado.")

if __name__ == "__main__":
    main()
