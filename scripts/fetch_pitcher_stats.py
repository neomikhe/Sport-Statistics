"""
Descarga estadisticas de pitchers MLB directamente desde MLB Stats API
y calcula FIP localmente. NO depende de FanGraphs (403) ni pybaseball.

FIP = ((13 * HR) + (3 * (BB + HBP)) - (2 * K)) / IP + cFIP
    cFIP ≈ 3.10 (calibrado a ERA media de liga, varia por temporada)

Uso:
    venv\\Scripts\\activate
    python scripts/fetch_pitcher_stats.py            # ultima temporada
    python scripts/fetch_pitcher_stats.py 2024 2025
"""
import sys
from pathlib import Path

import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402


BASE_URL = "https://statsapi.mlb.com/api/v1"

# Constante FIP calibrada a ERA media MLB (3.10-3.20 los ultimos anios)
FIP_CONSTANT = 3.10


def fetch_pitching_leaders(season: int, limit: int = 200) -> list:
    """
    Trae pitchers ordenados por innings pitched. Cada item incluye
    stats agregados de la temporada (ERA, K, BB, HR, etc.).
    """
    url = f"{BASE_URL}/stats"
    params = {
        "stats": "season",
        "group": "pitching",
        "season": season,
        "playerPool": "All",
        "limit": limit,
        "sportId": 1,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("stats", [])


def parse_pitcher_stats(api_response: list, min_ip: float = 10.0) -> list:
    """
    Extrae lista de dicts: nombre, IP, K, BB, HBP, HR, ERA, FIP calculado.
    """
    out = []
    for stats_block in api_response:
        for split in stats_block.get("splits", []):
            player = split.get("player", {})
            stat = split.get("stat", {})
            team = split.get("team", {})

            ip_str = stat.get("inningsPitched", "0")
            try:
                ip_whole, ip_frac = (ip_str + ".0").split(".")[:2]
                ip = int(ip_whole) + int(ip_frac) / 3.0  # MLB convention .1=1/3, .2=2/3
            except (ValueError, AttributeError):
                ip = 0.0

            if ip < min_ip:
                continue

            k = int(stat.get("strikeOuts", 0) or 0)
            bb = int(stat.get("baseOnBalls", 0) or 0)
            hbp = int(stat.get("hitByPitch", 0) or 0)
            hr = int(stat.get("homeRuns", 0) or 0)
            era = float(stat.get("era", 0) or 0)

            # FIP
            if ip > 0:
                fip = ((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip + FIP_CONSTANT
            else:
                fip = None

            # K%, BB% sobre batters faced
            tbf = int(stat.get("battersFaced", 0) or 0)
            k_pct = (k / tbf) if tbf > 0 else None
            bb_pct = (bb / tbf) if tbf > 0 else None

            whip = float(stat.get("whip", 0) or 0)

            out.append({
                "player_name": player.get("fullName"),
                "player_id": player.get("id"),
                "team": team.get("name", "")[:50],
                "ip": round(ip, 1),
                "era": era,
                "fip": round(fip, 3) if fip is not None else None,
                "xfip": None,  # requeriria HR/FB rate de liga
                "k_pct": round(k_pct, 4) if k_pct else None,
                "bb_pct": round(bb_pct, 4) if bb_pct else None,
                "whip": whip,
            })
    return out


def store_to_db(stats_list: list, season: int, conn) -> int:
    if not stats_list:
        return 0

    rows = []
    for s in stats_list:
        rows.append((
            season,
            s["player_name"],
            s.get("player_id"),
            s["team"],
            s["ip"],
            s["era"],
            s["fip"],
            s["xfip"],
            s["k_pct"],
            s["bb_pct"],
            s["whip"],
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO mlb_pitcher_stats
                (season, pitcher_name, pitcher_id, team, ip, era, fip, xfip, k_pct, bb_pct, whip)
            VALUES %s
            ON CONFLICT (season, pitcher_name) DO UPDATE SET
                pitcher_id = COALESCE(EXCLUDED.pitcher_id, mlb_pitcher_stats.pitcher_id),
                team = EXCLUDED.team,
                ip = EXCLUDED.ip,
                era = EXCLUDED.era,
                fip = EXCLUDED.fip,
                k_pct = EXCLUDED.k_pct,
                bb_pct = EXCLUDED.bb_pct,
                whip = EXCLUDED.whip,
                fetched_at = NOW()
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def main():
    if len(sys.argv) > 1:
        try:
            seasons = [int(s) for s in sys.argv[1:]]
        except ValueError:
            print("[ERR] Argumentos deben ser anios.")
            return 1
    else:
        seasons = [2024]

    conn = get_pg_connection()
    try:
        for season in seasons:
            print(f"\n[{season}] Descargando via MLB Stats API...")
            try:
                api_resp = fetch_pitching_leaders(season, limit=300)
            except Exception as e:
                print(f"  [FAIL] {type(e).__name__}: {e}")
                continue

            stats = parse_pitcher_stats(api_resp, min_ip=10.0)
            print(f"  Pitchers con >=10 IP: {len(stats)}")

            if not stats:
                continue

            # Top 10 por FIP
            ranked = sorted(
                [s for s in stats if s["fip"] is not None and s["ip"] >= 100],
                key=lambda s: s["fip"],
            )
            print(f"\n  Top 10 pitchers calificados (>=100 IP) por FIP mas bajo:")
            print(f"  {'#':<4}{'Pitcher':<28}{'Team':<10}{'IP':>7}{'FIP':>7}{'ERA':>7}")
            for i, s in enumerate(ranked[:10], 1):
                print(f"  {i:<4}{s['player_name']:<28}{s['team']:<10}"
                      f"{s['ip']:>7.1f}{s['fip']:>7.2f}{s['era']:>7.2f}")

            n = store_to_db(stats, season, conn)
            print(f"\n  [OK] {n} pitchers guardados en mlb_pitcher_stats (season={season})")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
