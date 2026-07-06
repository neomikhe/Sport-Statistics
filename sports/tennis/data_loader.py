"""
Carga de datos de tenis desde Jeff Sackmann (GitHub publico).

Repositorios:
    https://github.com/JeffSackmann/tennis_atp
    https://github.com/JeffSackmann/tennis_wta

Cada anio tiene un CSV con un partido por fila. Columnas relevantes:
    tourney_date, surface, tourney_level, best_of,
    winner_id, winner_name, loser_id, loser_name,
    score, w_ace, w_df, w_svpt, w_1stWon, w_2ndWon, l_*, ...

Scaffolding para Fase 8.
"""
from pathlib import Path

import pandas as pd
import requests


BASE_URL_ATP = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv"
BASE_URL_WTA = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv"


def download_year(tour: str, year: int, output_dir: Path) -> Path:
    """Descarga un CSV anual de Sackmann y lo guarda en output_dir."""
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
    """Lee un CSV de Sackmann a DataFrame con tipos correctos."""
    df = pd.read_csv(csv_path)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["tourney_date", "winner_id", "loser_id"])
    return df


def parse_to_db_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte el formato Sackmann al esquema tennis_matches.

    Mapping:
        tourney_date  -> date
        tourney_name  -> tournament
        surface       -> surface
        round         -> round
        best_of       -> best_of
        winner_id     -> winner_id (mapeo a entities)
        winner_name   -> player1_name
        loser_id      -> player2_id (mapeo a entities)
        ...
    """
    return df.rename(columns={
        "tourney_date": "date",
        "tourney_name": "tournament",
    })


# Pendiente: load_year() que inserte directamente en tennis_matches.
# Requiere mapeo player_id -> entity_id (Sackmann -> nuestro schema).
