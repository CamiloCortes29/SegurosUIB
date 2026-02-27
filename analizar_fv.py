# -*- coding: utf-8 -*-
"""
Script para procesar vigencias y facturación por grupo.

Cálculos de:
- Fecha 2026 (objetivo)  = primera Fecha FV en 2026 por grupo
- FV anterior a 2026     = máxima Fecha FV < objetivo por grupo
- Suma por FV (anterior) = suma Subtotal COP donde Fecha FV == FV anterior (solo 1a línea)
- Suma FV 2026           = suma Subtotal COP en 2026 por grupo (solo 1a línea)
- Columnas de display con formato: "dd/mm/aaaa — $ X"

Autor: Jules
"""

from pathlib import Path
import argparse
import pandas as pd
import numpy as np


def fmt_money(x):
    """Formatea valores numéricos a moneda: $ 1.234"""
    try:
        if pd.isna(x) or x == "":
            return ""
        # Redondear y formatear con punto como separador de miles
        return f"$ {int(round(float(x), 0)):,}".replace(",", ".")
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Procesar vigencias y facturación por grupo.")
    parser.add_argument("--input", required=True, help="Ruta al archivo Excel de entrada")
    parser.add_argument("--sheet", default=0, help="Nombre de la hoja o índice (0=primera)")
    parser.add_argument("--output", default="resultado_vigencias.xlsx", help="Ruta del Excel de salida")

    # Nombres de columnas personalizables
    parser.add_argument("--col-asegurado", default="Asegurado", help="Columna de Asegurado")
    parser.add_argument("--col-notacob", default="NotaCob", help="Columna de NotaCob")
    parser.add_argument("--col-anexo", default="Anexo NC", help="Columna de Anexo NC")
    parser.add_argument("--col-fv", default="Fecha FV", help="Columna de Fecha FV")
    parser.add_argument("--col-subtotal", default="Subtotal COP", help="Columna de Subtotal COP")
    parser.add_argument("--col-tipomvto", default=None, help="(Opcional) Columna de Tipo Mvto")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: No existe el archivo de entrada: {input_path}")
        return

    # ----- 1. Cargar y Normalizar -----
    sheet_name = args.sheet
    try:
        if isinstance(sheet_name, str) and sheet_name.isdigit():
            sheet_name = int(sheet_name)
    except Exception:
        pass

    print(f"📥 Leyendo: {input_path} (hoja={sheet_name})")
    df = pd.read_excel(input_path, sheet_name=sheet_name, engine="openpyxl")

    # Validar columnas
    COL_ASEG = args.col_asegurado
    COL_NOTA = args.col_notacob
    COL_ANEX = args.col_anexo
    COL_FV   = args.col_fv
    COL_SUB  = args.col_subtotal
    COL_MVTO = args.col_tipomvto

    required_cols = [COL_ASEG, COL_NOTA, COL_ANEX, COL_FV, COL_SUB]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"⚠️ ADVERTENCIA: Faltan columnas en el archivo: {missing}")
        print(f"Columnas disponibles: {list(df.columns)}")
        return

    # Normalizaciones técnicas para agrupación (sin modificar columnas originales)
    df["_ASEG_N"]  = df[COL_ASEG].astype(str).str.strip().str.upper()
    df["_NOTA_N"]  = df[COL_NOTA].astype(str).str.strip().str.upper()
    df["_ANEXO_N"] = df[COL_ANEX].astype(str).fillna("").str.strip()

    # Procesar Fecha FV
    df["_FV_DT"] = pd.to_datetime(df[COL_FV], dayfirst=True, errors="coerce").dt.floor("D")

    # Procesar Subtotal COP
    df["_SUB_VAL"] = pd.to_numeric(df[COL_SUB], errors="coerce").fillna(0)

    grp_keys = ["_ASEG_N", "_NOTA_N", "_ANEXO_N"]

    # ----- 2. Cálculos de Fechas -----

    # Fecha 2026 (objetivo): primera FV en 2026 por grupo
    df["Fecha 2026 (objetivo)"] = df.groupby(grp_keys)["_FV_DT"].transform(
        lambda s: s[s.dt.year == 2026].min() if any(s.dt.year == 2026) else pd.NaT
    )

    # FV anterior a 2026 (fecha): máxima Fecha FV < objetivo por grupo
    # Usamos una función auxiliar para evitar merges complejos y mantener el shape
    def calc_prev_fv(group):
        target = group["Fecha 2026 (objetivo)"].iloc[0]
        if pd.isna(target):
            return pd.Series([pd.NaT] * len(group), index=group.index)
        prev_dates = group.loc[group["_FV_DT"] < target, "_FV_DT"]
        max_prev = prev_dates.max() if not prev_dates.empty else pd.NaT
        return pd.Series([max_prev] * len(group), index=group.index)

    df["FV anterior a 2026 (fecha)"] = df.groupby(grp_keys, group_keys=False).apply(calc_prev_fv)

    # ----- 3. Cálculos de Sumas -----

    # Suma por FV (anterior): suma de SUB donde FV == FV_anterior
    # Solo sumamos en las filas que coinciden exactamente con la fecha anterior del grupo
    df["_mask_prev"] = (df["_FV_DT"] == df["FV anterior a 2026 (fecha)"]) & pd.notna(df["_FV_DT"])

    # Calculamos el total por grupo y fecha anterior
    df["_sum_prev_total"] = df.groupby(grp_keys + ["FV anterior a 2026 (fecha)"], dropna=False)["_SUB_VAL"].transform(
        lambda x: x[df.loc[x.index, "_mask_prev"]].sum()
    )

    # Suma FV 2026: suma de SUB de todas las FV en 2026 por grupo
    df["_mask_2026"] = (df["_FV_DT"].dt.year == 2026)
    df["_sum_2026_total"] = df.groupby(grp_keys)["_SUB_VAL"].transform(
        lambda x: x[df.loc[x.index, "_mask_2026"]].sum()
    )

    # Identificar primera fila de cada grupo para mostrar sumas
    is_first_in_group = ~df.duplicated(subset=grp_keys)

    # Asignar a columnas finales solo en la primera fila
    df["Suma por FV (anterior)"] = np.nan
    df.loc[is_first_in_group & pd.notna(df["FV anterior a 2026 (fecha)"]), "Suma por FV (anterior)"] = df["_sum_prev_total"]

    df["Suma FV 2026"] = np.nan
    df.loc[is_first_in_group & pd.notna(df["Fecha 2026 (objetivo)"]), "Suma FV 2026"] = df["_sum_2026_total"]

    # ----- 4. Columnas de Display -----

    def build_display(row, date_col, sum_col):
        dt = row[date_col]
        sm = row[sum_col]
        # Solo mostrar si es la primera fila del grupo y tiene datos válidos
        if not is_first_in_group.loc[row.name] or pd.isna(dt) or pd.isna(sm):
            return ""

        res = f"{dt.strftime('%d/%m/%Y')} — {fmt_money(sm)}"

        # Agregar Tipo Mvto si existe y está configurado
        if COL_MVTO and COL_MVTO in df.columns:
            mvto = str(row[COL_MVTO]).strip()
            if mvto and mvto.lower() != "nan":
                res += f" — {mvto}"
        return res

    df["Fecha FV Anterior (mostrar)"] = df.apply(
        lambda r: build_display(r, "FV anterior a 2026 (fecha)", "_sum_prev_total"), axis=1
    )

    df["FV 2026 (mostrar)"] = df.apply(
        lambda r: build_display(r, "Fecha 2026 (objetivo)", "_sum_2026_total"), axis=1
    )

    # ----- 5. Exportar -----

    # Limpiar columnas temporales
    temp_cols = [c for c in df.columns if c.startswith("_")]
    df_final = df.drop(columns=temp_cols)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"💾 Guardando resultado en: {output_path.resolve()}")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="resultado")

    print("✅ Listo. Columnas generadas:")
    print("   - Fecha 2026 (objetivo)")
    print("   - FV anterior a 2026 (fecha)")
    print("   - Suma por FV (anterior)")
    print("   - Suma FV 2026")
    print("   - Fecha FV Anterior (mostrar)")
    print("   - FV 2026 (mostrar)")


if __name__ == "__main__":
    main()
