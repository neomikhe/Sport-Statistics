"""
Descarga Lahman Baseball Database desde chadwickbureau/baseballdatabank.

Estrategia robusta: descarga el ZIP completo del repo via GitHub archive y
extrae los CSVs Teams/Pitching/Batting independientemente de su ruta interna.
Asi el script no se rompe si el repo reorganiza carpetas.

Uso:
    venv\\Scripts\\activate
    python scripts/download_baseball_data.py
    python scripts/download_baseball_data.py 2020      # filtrar a yearID >= 2020
"""
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests


DEFAULT_MIN_YEAR = 2018

# Probamos varios endpoints/ramas porque chadwickbureau renombro su default branch
# a `main` en algun momento, y algunos forks usan otros nombres.
ZIP_URLS_TO_TRY = [
    "https://api.github.com/repos/chadwickbureau/baseballdatabank/zipball/HEAD",
    "https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/main.zip",
    "https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/master.zip",
    "https://codeload.github.com/chadwickbureau/baseballdatabank/zip/refs/heads/main",
    "https://codeload.github.com/chadwickbureau/baseballdatabank/zip/refs/heads/master",
]

WANTED = ["Teams.csv", "Pitching.csv", "Batting.csv"]


def main():
    if len(sys.argv) > 1:
        try:
            min_year = int(sys.argv[1])
        except ValueError:
            print("[ERR] Argumento debe ser un anio (ej.: 2020).")
            return 1
    else:
        min_year = DEFAULT_MIN_YEAR

    output_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "baseball"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Descargando ZIP del repo chadwickbureau/baseballdatabank...")
    print(f"  Destino: {output_dir}")
    print()

    r = None
    for url in ZIP_URLS_TO_TRY:
        try:
            print(f"  Probando: {url}")
            tmp = requests.get(url, timeout=180, allow_redirects=True)
            if tmp.status_code == 200 and len(tmp.content) > 100_000:
                r = tmp
                print(f"  [ok] {len(r.content) / 1024 / 1024:.1f} MB descargados")
                break
            else:
                print(f"    -> status {tmp.status_code}, size {len(tmp.content)}")
        except requests.RequestException as e:
            print(f"    -> {type(e).__name__}: {e}")

    if r is None:
        print()
        print("[FAIL] Ninguna URL del repo funciono.")
        print("Posibles causas: conexion sin acceso a github.com, o el repo cambio.")
        print("Como ultimo recurso, descarga manual desde:")
        print("    https://github.com/chadwickbureau/baseballdatabank")
        print("y descomprime en data/raw/baseball/")
        return 1

    n_files = 0
    n_failed = 0

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = z.namelist()
        for target in WANTED:
            # Buscar cualquier path que termine en /<target>
            matches = [n for n in names if n.endswith(f"/{target}")]
            if not matches:
                print(f"  [FAIL] {target} no encontrado en el ZIP")
                n_failed += 1
                continue
            internal_path = matches[0]
            try:
                with z.open(internal_path) as f:
                    df = pd.read_csv(f)
                if "yearID" in df.columns:
                    df_recent = df[df["yearID"] >= min_year].copy()
                else:
                    df_recent = df
                stem = target.replace(".csv", "").lower()
                output = output_dir / f"lahman_{stem}.csv"
                df_recent.to_csv(output, index=False)
                print(f"  [ok] {target} -> {output.name}: {len(df_recent):,} filas")
                n_files += 1
            except Exception as e:
                print(f"  [FAIL] {target}: {type(e).__name__}: {e}")
                n_failed += 1

    print()
    print(f"Resumen: {n_files} CSVs creados | {n_failed} fallos")
    print(f"Archivos en {output_dir}: {len(list(output_dir.glob('*.csv')))}")
    print()
    print("[NOTA] Lahman tiene datos a nivel SEASON, no game-level.")
    print("       Para Elo y picks por partido, ya tienes:")
    print("           python scripts/download_retrosheet_data.py")
    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
