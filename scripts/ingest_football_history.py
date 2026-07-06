"""
Ingesta masiva de CSVs de futbol historicos a la tabla football_matches.

Pre-requisito: CSVs descargados en data/raw/football/ via
    python scripts/download_football_data.py

Uso:
    venv\\Scripts\\activate
    python scripts/ingest_football_history.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.data_loader import load_directory


def main():
    raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "football"
    print(f"Ingestando CSVs desde: {raw_dir}")
    print()

    total = load_directory(str(raw_dir))

    print()
    print(f"Total de filas insertadas (sin contar duplicados): {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
