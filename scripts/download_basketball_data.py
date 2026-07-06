"""
Descarga historial NBA usando nba_api e inserta en basketball_games.

Por defecto descarga las ultimas 5 temporadas. Editable con CLI:
    python scripts/download_basketball_data.py 2020-21 2021-22 2022-23

nba_api hace peticiones a stats.nba.com con rate limit informal.
El script duerme 1s entre temporadas.

Uso:
    venv\\Scripts\\activate
    pip install nba_api    # si no esta instalado
    python scripts/download_basketball_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.basketball.data_loader import load_multiple_seasons  # noqa: E402


DEFAULT_SEASONS = [
    "2019-20", "2020-21", "2021-22",
    "2022-23", "2023-24", "2024-25", "2025-26",
]


def main():
    seasons = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_SEASONS

    print(f"Temporadas a descargar: {seasons}")
    print("(Pulsa Ctrl+C para cancelar; cada temporada tarda ~10-30 segundos)")
    print()

    totals = load_multiple_seasons(seasons)

    print()
    print("=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    grand_total = 0
    for season, n in totals.items():
        status = f"{n} partidos" if n >= 0 else "FALLO"
        print(f"  {season}: {status}")
        if n > 0:
            grand_total += n
    print(f"\n  Total: {grand_total} partidos insertados en basketball_games")
    return 0


if __name__ == "__main__":
    sys.exit(main())
