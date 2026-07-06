"""
Scraper de lesiones NBA con MULTIPLES fuentes (failover).

Fuentes probadas en orden:
  1. ESPN API JSON  (per-team injuries endpoint, JSON nativo, mas estable)
  2. ESPN news API  (todas las lesiones en una llamada)
  3. basketball-reference HTML (fallback con browser User-Agent)

Cachea responses 6h.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "nba_injuries"
CACHE_TTL = timedelta(hours=6)

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ----------------------------------------------------------------------
#  ESPN API JSON (preferido)
# ----------------------------------------------------------------------

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_TEAM_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/injuries"
)


def _fetch_espn_team_list() -> List[dict]:
    r = requests.get(ESPN_TEAMS_URL, headers=HEADERS_BROWSER, timeout=30)
    r.raise_for_status()
    data = r.json()
    out = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for team_block in league.get("teams", []):
                t = team_block.get("team", {})
                if t.get("id") and t.get("displayName"):
                    out.append({
                        "id": str(t["id"]),
                        "name": t.get("displayName"),
                        "abbr": t.get("abbreviation"),
                    })
    return out


def _fetch_espn_team_injuries(team_id: str) -> List[dict]:
    url = ESPN_TEAM_INJURIES_URL.format(tid=team_id)
    r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    out = []
    for item in data.get("items", []):
        athlete_ref = item.get("athlete", {})
        out.append({
            "player_name": athlete_ref.get("fullName") or athlete_ref.get("displayName") or "?",
            "status": item.get("status", "Unknown"),
            "note": item.get("longComment") or item.get("shortComment") or "",
            "update_date": _parse_date_safe(item.get("date")),
        })
    return out


def _parse_date_safe(date_str: Optional[str]):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _try_espn_json() -> pd.DataFrame:
    cache_file = CACHE_DIR / "espn_json_latest.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_file.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if age < CACHE_TTL:
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                df = pd.DataFrame(cached)
                if not df.empty:
                    return df
            except Exception:
                pass

    try:
        teams = _fetch_espn_team_list()
    except requests.RequestException:
        return pd.DataFrame()

    rows = []
    for team in teams:
        try:
            injuries = _fetch_espn_team_injuries(team["id"])
            for inj in injuries:
                inj["team_name"] = team["name"]
                rows.append(inj)
        except requests.RequestException:
            continue

    if rows:
        cache_file.write_text(json.dumps(rows, default=str), encoding="utf-8")
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
#  ESPN HTML (fallback 1)
# ----------------------------------------------------------------------

ESPN_HTML_URL = "https://www.espn.com/nba/injuries"


def _try_espn_html() -> pd.DataFrame:
    try:
        r = requests.get(ESPN_HTML_URL, headers=HEADERS_BROWSER, timeout=30)
        if r.status_code != 200:
            return pd.DataFrame()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for ts in soup.select(".Table__Title, .Table__Header"):
        team_name = ts.get_text(strip=True)
        wrapper = ts.find_parent()
        table = wrapper.find_next("table") if wrapper else None
        if table is None:
            continue
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            rows.append({
                "player_name": cells[0].get_text(strip=True),
                "team_name": team_name,
                "update_date": None,
                "status": cells[3].get_text(strip=True) if len(cells) >= 4 else "Unknown",
                "note": cells[-1].get_text(strip=True),
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
#  Basketball-Reference (fallback 2)
# ----------------------------------------------------------------------

BBR_URL = "https://www.basketball-reference.com/friv/injuries.fcgi"


def _try_bbr() -> pd.DataFrame:
    try:
        r = requests.get(BBR_URL, headers=HEADERS_BROWSER, timeout=30)
        if r.status_code != 200:
            return pd.DataFrame()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", id="injuries")
    if table is None:
        return pd.DataFrame()
    tbody = table.find("tbody")
    if tbody is None:
        return pd.DataFrame()

    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 4:
            continue
        try:
            update_date = datetime.strptime(cells[2].get_text(strip=True), "%Y-%m-%d").date()
        except ValueError:
            update_date = None
        note = cells[3].get_text(strip=True)
        rows.append({
            "player_name": cells[0].get_text(strip=True),
            "team_name": cells[1].get_text(strip=True),
            "update_date": update_date,
            "status": _classify_status(note),
            "note": note,
        })
    return pd.DataFrame(rows)


def _classify_status(description: str) -> str:
    if not description:
        return "Unknown"
    desc = description.lower()
    if "out for season" in desc or "season-ending" in desc:
        return "Out for Season"
    if "ruled out" in desc or re.search(r"\bout\b", desc):
        return "Out"
    if "doubtful" in desc:
        return "Doubtful"
    return "Day-To-Day"


# ----------------------------------------------------------------------
#  API publica
# ----------------------------------------------------------------------

def _try_rotowire() -> pd.DataFrame:
    """Rotowire publica una tabla JSON con todas las lesiones NBA."""
    url = "https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL"
    try:
        r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
    except (requests.RequestException, ValueError):
        return pd.DataFrame()

    rows = []
    items = data if isinstance(data, list) else data.get("data", [])
    for item in items:
        rows.append({
            "player_name": item.get("player") or item.get("name"),
            "team_name": item.get("team") or item.get("teamFull") or "",
            "update_date": _parse_date_safe(item.get("date") or item.get("returns")),
            "status": (item.get("status") or "Unknown")[:50],
            "note": item.get("injury") or item.get("note") or "",
        })
    return pd.DataFrame([r for r in rows if r["player_name"]])


def _try_cbs() -> pd.DataFrame:
    """CBS Sports tiene un HTML estable de lesiones NBA."""
    url = "https://www.cbssports.com/nba/injuries/"
    try:
        r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
        if r.status_code != 200:
            return pd.DataFrame()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for table in soup.select("table.TableBase-table"):
        team_header = table.find_previous(["h4", "h3"])
        team_name = team_header.get_text(strip=True) if team_header else "Unknown"
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            rows.append({
                "player_name": cells[0].get_text(strip=True),
                "team_name": team_name,
                "update_date": None,
                "status": cells[3].get_text(strip=True) if len(cells) > 3 else "Unknown",
                "note": cells[-1].get_text(strip=True) if len(cells) >= 5 else "",
            })
    return pd.DataFrame([r for r in rows if r["player_name"]])


def fetch_injury_report(use_cache: bool = True) -> pd.DataFrame:
    sources = [
        ("Rotowire JSON",       _try_rotowire),
        ("ESPN API JSON",       _try_espn_json),
        ("ESPN HTML",           _try_espn_html),
        ("CBS Sports HTML",     _try_cbs),
        ("basketball-reference", _try_bbr),
    ]
    for source_name, fn in sources:
        try:
            df = fn()
        except Exception as e:
            print(f"  [debug] {source_name}: {type(e).__name__}: {e}")
            continue
        if not df.empty:
            df["source"] = source_name
            return df
    return pd.DataFrame()


def _clean_for_db(v):
    """Convierte NaN/NaT/None a None (para PostgreSQL NULL)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def store_to_db(df: pd.DataFrame, conn) -> int:
    if df.empty:
        return 0
    from psycopg2.extras import execute_values
    rows = [
        (
            _clean_for_db(r.get("player_name")),
            _clean_for_db(r.get("team_name")),
            _clean_for_db(r.get("update_date")),
            _clean_for_db(r.get("status")),
            _clean_for_db(r.get("note")),
        )
        for _, r in df.iterrows()
    ]
    # Filtrar filas sin player_name (corruptas)
    rows = [r for r in rows if r[0]]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO nba_injuries (player_name, team_name, update_date, status, note)
            VALUES %s
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def get_team_injuries_recent(conn, team_name: str, max_age_hours: int = 24) -> List[dict]:
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT player_name, status, note, update_date, fetched_at
            FROM nba_injuries
            WHERE team_name = %s AND fetched_at >= %s
            ORDER BY fetched_at DESC, player_name
            """,
            (team_name, cutoff),
        )
        rows = cur.fetchall()
    return [
        {"player": p, "status": s, "note": n, "update_date": ud, "fetched_at": fa}
        for p, s, n, ud, fa in rows
    ]
