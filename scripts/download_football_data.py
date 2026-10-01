import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://www.football-data.co.uk/mmz4281"

LEAGUES = [
    "E0",
    "SP1",
    "I1",
    "D1",
    "F1",
    "E1",
    "SP2",
    "I2",
    "D2",
    "F2",
    "N1",
    "B1",
    "P1",
    "T1",
    "G1",
    "SC0",
]

def _current_season_code(today=None):
    from datetime import date
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


SEASONS = [
    "1516", "1617", "1718", "1819", "1920",
    "2021", "2122", "2223", "2324", "2425", "2526",
]
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
                time.sleep(0.5)
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
