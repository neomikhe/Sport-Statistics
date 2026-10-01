from pathlib import Path

import pandas as pd
import requests


BASE_URL_ATP = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv"
BASE_URL_WTA = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv"


def download_year(tour: str, year: int, output_dir: Path) -> Path:
    if tour.upper() == "ATP":
        url = BASE_URL_ATP.format(year=year)
    elif tour.upper() == "WTA":
        url = BASE_URL_WTA.format(year=year)
    else:
        raise ValueError("tour debe ser 'ATP' o 'WTA'")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{tour.lower()}_{year}.csv"

    if output_file.exists() and output_file.stat().st_size > 1024:
        return output_file

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    output_file.write_bytes(r.content)
    return output_file


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["tourney_date", "winner_id", "loser_id"])
    return df


def parse_to_db_format(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "tourney_date": "date",
        "tourney_name": "tournament",
    })
