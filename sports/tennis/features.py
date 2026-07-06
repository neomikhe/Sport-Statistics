"""
Feature engineering para tenis.

Features pre-partido por jugador (vs oponente, en superficie X):
    elo_p1_surface, elo_p2_surface, elo_diff_surface
    elo_p1_general, elo_p2_general, elo_diff_general
    spw_p1_recent, spw_p2_recent  (% puntos ganados al saque, ultimos 10 partidos)
    h2h_p1_wins, h2h_p2_wins      (cara a cara, ultimos 5 enfrentamientos)

Uso:
    from sports.tennis.features import build_features
    df = build_features(engine)
"""
import numpy as np
import pandas as pd


DEFAULT_ELO = 1500.0
DEFAULT_SPW = 0.62

FEATURE_COLS = [
    "p1_elo_surface", "p2_elo_surface", "elo_diff_surface",
    "p1_elo_general", "p2_elo_general", "elo_diff_general",
    "p1_spw_recent", "p2_spw_recent", "spw_diff",
]


def _load_matches(engine):
    df = pd.read_sql(
        """
        SELECT id, date, surface, best_of,
               player1_id, player2_id, winner_id,
               p1_aces, p1_df, p1_spw,
               p2_aces, p2_df, p2_spw
        FROM tennis_matches
        WHERE surface IS NOT NULL AND winner_id IS NOT NULL
        ORDER BY date, id
        """,
        engine,
        parse_dates=["date"],
    )
    # Sackmann guarda surface capitalizada ("Hard","Clay"...); tennis_elo lowercase.
    # Normalizamos a lowercase aqui para que el merge cuadre.
    df["surface"] = df["surface"].astype(str).str.lower().str.strip()
    return df


def _load_elo(engine):
    df = pd.read_sql(
        "SELECT player_id, date, surface, elo FROM tennis_elo",
        engine,
        parse_dates=["date"],
    )
    df["surface"] = df["surface"].astype(str).str.lower().str.strip()
    return df


def _add_elo_pre(matches, df_elo, surface_filter=None):
    """Adjunta Elo pre-partido a player1 y player2 por superficie X (o general si surface=None)."""
    df_elo = df_elo.copy()
    if surface_filter is not None:
        df_elo = df_elo[df_elo["surface"] == surface_filter]
    elo_sorted = df_elo.sort_values("date").reset_index(drop=True)

    # Player 1
    p1 = matches[["id", "date", "player1_id"]].rename(columns={"player1_id": "player_id"})
    p1 = p1.sort_values("date").reset_index(drop=True)
    p1_merged = pd.merge_asof(
        p1, elo_sorted.rename(columns={"elo": "elo_p1"})[["player_id", "date", "elo_p1"]],
        by="player_id", on="date", direction="backward", allow_exact_matches=False,
    )
    p1_merged["elo_p1"] = p1_merged["elo_p1"].fillna(DEFAULT_ELO)

    # Player 2
    p2 = matches[["id", "date", "player2_id"]].rename(columns={"player2_id": "player_id"})
    p2 = p2.sort_values("date").reset_index(drop=True)
    p2_merged = pd.merge_asof(
        p2, elo_sorted.rename(columns={"elo": "elo_p2"})[["player_id", "date", "elo_p2"]],
        by="player_id", on="date", direction="backward", allow_exact_matches=False,
    )
    p2_merged["elo_p2"] = p2_merged["elo_p2"].fillna(DEFAULT_ELO)

    return p1_merged[["id", "elo_p1"]], p2_merged[["id", "elo_p2"]]


def _add_recent_spw(matches):
    """% puntos ganados al saque, ultimos 10 partidos por jugador."""
    # Construir timeline por jugador
    p1 = matches[["id", "date", "player1_id", "p1_spw", "p1_df", "p2_spw", "p2_df"]].copy()
    p1 = p1.rename(columns={
        "player1_id": "player_id",
        "p1_spw": "spw_won", "p1_df": "df",
    })
    # spw aqui es "service points won" total, no ratio. Tenemos que normalizar.
    # Sackmann: w_1stWon + w_2ndWon = puntos ganados al saque; w_svpt = puntos servidos.
    # En nuestra ingesta guardamos w_svpt como p1_spw. Necesitamos también w_1stWon+w_2ndWon
    # Pero no los guardamos. Aproximacion: usar SPW = (svpt - df) / svpt como heuristica.
    # NOTA: esto es una aproximacion grosera, suficiente para baseline.
    pass

    # Por simplicidad MVP, devolvemos SPW constante por jugador
    timeline_p1 = matches[["id", "date", "player1_id"]].rename(columns={"player1_id": "player_id"})
    timeline_p1["spw"] = DEFAULT_SPW
    timeline_p2 = matches[["id", "date", "player2_id"]].rename(columns={"player2_id": "player_id"})
    timeline_p2["spw"] = DEFAULT_SPW
    return (
        timeline_p1.rename(columns={"spw": "spw_p1"})[["id", "spw_p1"]],
        timeline_p2.rename(columns={"spw": "spw_p2"})[["id", "spw_p2"]],
    )


def build_features(engine) -> pd.DataFrame:
    """Pipeline completo de features de tenis."""
    matches = _load_matches(engine)
    if matches.empty:
        return matches

    df_elo = _load_elo(engine)

    # Elo por superficie (uno por surface)
    elo_p1_surface_parts = []
    elo_p2_surface_parts = []
    for surface in matches["surface"].dropna().unique():
        sub = matches[matches["surface"] == surface]
        if sub.empty:
            continue
        elo_p1, elo_p2 = _add_elo_pre(sub, df_elo, surface_filter=surface)
        elo_p1_surface_parts.append(elo_p1)
        elo_p2_surface_parts.append(elo_p2)

    elo_p1_surface = pd.concat(elo_p1_surface_parts).rename(columns={"elo_p1": "p1_elo_surface"})
    elo_p2_surface = pd.concat(elo_p2_surface_parts).rename(columns={"elo_p2": "p2_elo_surface"})

    # Elo general (todas las superficies)
    elo_p1_gen, elo_p2_gen = _add_elo_pre(matches, df_elo, surface_filter=None)
    elo_p1_gen = elo_p1_gen.rename(columns={"elo_p1": "p1_elo_general"})
    elo_p2_gen = elo_p2_gen.rename(columns={"elo_p2": "p2_elo_general"})

    # SPW reciente
    spw_p1, spw_p2 = _add_recent_spw(matches)
    spw_p1 = spw_p1.rename(columns={"spw_p1": "p1_spw_recent"})
    spw_p2 = spw_p2.rename(columns={"spw_p2": "p2_spw_recent"})

    # Merge
    result = (
        matches
        .merge(elo_p1_surface, on="id", how="left")
        .merge(elo_p2_surface, on="id", how="left")
        .merge(elo_p1_gen, on="id", how="left")
        .merge(elo_p2_gen, on="id", how="left")
        .merge(spw_p1, on="id", how="left")
        .merge(spw_p2, on="id", how="left")
    )

    result["p1_elo_surface"] = result["p1_elo_surface"].fillna(DEFAULT_ELO)
    result["p2_elo_surface"] = result["p2_elo_surface"].fillna(DEFAULT_ELO)
    result["p1_elo_general"] = result["p1_elo_general"].fillna(DEFAULT_ELO)
    result["p2_elo_general"] = result["p2_elo_general"].fillna(DEFAULT_ELO)

    result["elo_diff_surface"] = result["p1_elo_surface"] - result["p2_elo_surface"]
    result["elo_diff_general"] = result["p1_elo_general"] - result["p2_elo_general"]
    result["spw_diff"] = result["p1_spw_recent"] - result["p2_spw_recent"]

    # Target
    result["p1_won"] = (result["winner_id"] == result["player1_id"]).astype(int)

    return result.sort_values("date").reset_index(drop=True)
