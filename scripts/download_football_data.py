"""
Descarga CSVs historicos de football-data.co.uk.

URLs con formato:
    https://www.football-data.co.uk/mmz4281/{SEASON}/{LEAGUE}.csv
    ej.: https://www.football-data.co.uk/mmz4281/2425/E0.csv

Ligas descargadas por defecto:
    E0  - Premier League (ENG)
    SP1 - La Liga (ESP)
    I1  - Serie A (ITA)
    D1  - Bundesliga (GER)
    F1  - Ligue 1 (FRA)

Temporadas: 2015-16 hasta 2025-26 (11 temporadas, ~55 archivos).

Los archivos se guardan en data/raw/football/{LEAGUE}_{SEASON}.csv
El script es idempotente: archivos ya descargados se detectan y se saltan.

Uso:
    venv\\Scripts\\activate
    python scripts/download_football_data.py
"""
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://www.football-data.co.uk/mmz4281"

# Top 5 + segunda division + otras ligas europeas con cuotas Pinnacle
LEAGUES = [
    # Top 5 (ya teniamos)
    "E0",   # Premier League (Inglaterra)
    "SP1",  # La Liga (Espana)
    "I1",   # Serie A (Italia)
    "D1",   # Bundesliga (Alemania)
    "F1",   # Ligue 1 (Francia)
    # Segunda division
    "E1",   # Championship (Inglaterra D2)
    "SP2",  # Segunda Division (Espana)
    "I2",   # Serie B (Italia)
    "D2",   # 2. Bundesliga (Alemania)
    "F2",   # Ligue 2 (Francia)
    # Otras ligas top
    "N1",   # Eredivisie (Holanda)
    "B1",   # Pro League (Belgica)
    "P1",   # Primeira Liga (Portugal)
    "T1",   # Super Lig (Turquia)
    "G1",   # Super League (Grecia)
    "SC0",  # Premiership (Escocia)
]

def _current_season_code(today=None):
    """Código football-data de la temporada en curso, p.ej. '2526' o '2627'.

    La temporada europea arranca en agosto; usamos julio como corte para tener
    el código listo desde pretemporada. Así la lista se auto-actualiza cada año.
    """
    from datetime import date
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


SEASONS = [
    "1516", "1617", "1718", "1819", "1920",
    "2021", "2122", "2223", "2324", "2425", "2526",
]
# Asegura que la temporada en curso siempre esté incluida (sin duplicar).
if _current_season_code() not in SEASONS:
    SEASONS.append(_current_season_code())

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "football"

HEADERS = {
    "User-Agent": "SportStatistics/0.1 (personal research; contact: local)",
}


def download_one(league, season):
    url = f"{BASE_URL}/{season}/{league}.csv"
    output = OUTPUT_DIR / f"{league}_{season}.csv"

    if output.exists() and output.stat().st_size > 1024:
        return "cached"

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        return f"error:{type(e).__name__}"

    if r.status_code == 404:
        return "not_found"
    if r.status_code != 200:
        return f"http_{r.status_code}"
    if len(r.content) < 1024:
        return "too_small"

    output.write_bytes(r.content)
    return "downloaded"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(LEAGUES) * len(SEASONS)
    done = 0
    downloaded = 0
    cached = 0
    failed = 0

    print(f"Descargando hasta {total} CSVs a {OUTPUT_DIR}")
    print()

    for league in LEAGUES:
        for season in SEASONS:
            status = download_one(league, season)
            done += 1

            if status == "downloaded":
                downloaded += 1
                marker = "[NEW] "
                time.sleep(0.5)  # ser educado con el servidor
            elif status == "cached":
                cached += 1
                marker = "[OK]  "
            else:
                failed += 1
                marker = "[FAIL]"

            print(f"{marker} ({done:>2}/{total}) {league}_{season} -> {status}")

    print()
    print(f"Resumen: {downloaded} nuevos | {cached} cacheados | {failed} fallidos")
    print(f"Archivos totales en {OUTPUT_DIR}: {len(list(OUTPUT_DIR.glob('*.csv')))}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
