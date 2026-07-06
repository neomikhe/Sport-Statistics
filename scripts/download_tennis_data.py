"""
Descarga CSVs anuales de Jeff Sackmann desde GitHub.

Por defecto descarga ATP y WTA de los ultimos 5 anios:
    https://github.com/JeffSackmann/tennis_atp
    https://github.com/JeffSackmann/tennis_wta

Cada CSV tiene un partido por fila con winner_id, loser_id, surface, etc.
Los archivos se guardan en data/raw/tennis/.

Uso:
    venv\\Scripts\\activate
    python scripts/download_tennis_data.py
    python scripts/download_tennis_data.py 2020 2021 2022 2023 2024 2025  # anios explicitos
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.tennis.data_loader import download_year  # noqa: E402


DEFAULT_YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
TOURS = ["ATP", "WTA"]


def main():
    if len(sys.argv) > 1:
        try:
            years = [int(y) for y in sys.argv[1:]]
        except ValueError:
            print("[ERR] Argumentos deben ser anios (ej.: 2022 2023 2024).")
            return 1
    else:
        years = DEFAULT_YEARS

    output_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "tennis"

    print(f"Descargando: ATP + WTA, anios {years}")
    print(f"Destino: {output_dir}")
    print()

    total = 0
    failed = 0
    cached = 0

    for tour in TOURS:
        for year in years:
            try:
                output_file = download_year(tour, year, output_dir)
                size_kb = output_file.stat().st_size / 1024
                if output_file.stat().st_mtime < time.time() - 60:
                    cached += 1
                    print(f"  [cached] {tour} {year} ({size_kb:.1f} KB)")
                else:
                    total += 1
                    print(f"  [NEW]    {tour} {year} ({size_kb:.1f} KB)")
                    time.sleep(0.5)
            except Exception as e:
                failed += 1
                print(f"  [FAIL]   {tour} {year}: {type(e).__name__}: {e}")

    print()
    print(f"Resumen: {total} nuevos | {cached} cacheados | {failed} fallidos")
    print(f"Archivos en {output_dir}: {len(list(output_dir.glob('*.csv')))}")

    print()
    print("[NOTA] La ingesta a tennis_matches (PostgreSQL) requiere mapear")
    print("       jugadores Sackmann a la tabla entities. Pendiente de Fase 8.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
