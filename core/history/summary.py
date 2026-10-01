import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

KEY_PREFIX = "daily_summary:"
KEEP_DAYS = 120
TZ_NAME = os.getenv("SUMMARY_TZ", "America/Mazatlan")


def today_local() -> date:
    return datetime.now(ZoneInfo(TZ_NAME)).date()

_ROWS_SQL = """
    SELECT sport, match_key, home, away, grupo, mercado, probability, rank, hit
    FROM match_predictions
    WHERE match_date = %(d)s
    ORDER BY sport, match_key, rank
"""


def summarize(rows: pd.DataFrame, day, scores: dict | None = None) -> dict:
    scores = scores or {}
    matches = []
    for key, g in rows.groupby("match_key", sort=False):
        g = g.sort_values("rank")
        done = g[g["hit"].notna()]
        items = [{"mercado": str(r.mercado), "grupo": str(r.grupo), "prob": round(float(r.probability), 4),
                  "hit": None if pd.isna(r.hit) else bool(r.hit)} for r in g.itertuples()]
        first = g.iloc[0]
        matches.append({
            "key": str(key), "sport": str(first["sport"]), "home": str(first["home"]),
            "away": str(first["away"]), "score": scores.get(str(key)),
            "total": len(g), "resolved": len(done), "hits": int(done["hit"].astype(bool).sum()),
            "promised": round(float(done["probability"].astype(float).mean()), 4) if len(done) else None,
            "main": items[0], "items": items,
        })
    resolved = [m for m in matches if m["resolved"]]
    n_res = sum(m["resolved"] for m in matches)
    promised = [i["prob"] for m in matches for i in m["items"] if i["hit"] is not None]
    return {
        "date": str(day),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "totals": {
            "matches": len(matches), "resolved_matches": len(resolved),
            "situations": sum(m["total"] for m in matches), "resolved": n_res,
            "hits": sum(m["hits"] for m in matches),
            "promised": round(sum(promised) / len(promised), 4) if promised else None,
            "main_hits": sum(1 for m in resolved if m["main"]["hit"]),
            "main_resolved": sum(1 for m in resolved if m["main"]["hit"] is not None),
        },
        "matches": matches,
    }


def build(engine, day, scores: dict | None = None) -> dict:
    rows = pd.read_sql(_ROWS_SQL, engine, params={"d": str(day)})
    return summarize(rows, day, scores)


# Se guarda en app_meta: sin cambios de esquema.
def save(summary: dict) -> bool:
    from core.database.meta import stamp_meta
    return stamp_meta(KEY_PREFIX + summary["date"], json.dumps(summary, ensure_ascii=False))


def load(engine, day) -> dict | None:
    df = pd.read_sql("SELECT value FROM app_meta WHERE key = %(k)s", engine,
                     params={"k": KEY_PREFIX + str(day)})
    if df.empty:
        return None
    try:
        return json.loads(df["value"].iloc[0])
    except (TypeError, ValueError):
        return None


def available_dates(engine, limit: int = 30) -> list:
    df = pd.read_sql("SELECT key FROM app_meta WHERE key LIKE %(p)s ORDER BY key DESC LIMIT %(n)s",
                     engine, params={"p": KEY_PREFIX + "2%", "n": int(limit)})
    return [date.fromisoformat(k[len(KEY_PREFIX):]) for k in df["key"]]


def prune(keep_days: int = KEEP_DAYS) -> int:
    from core.database.connection import get_pg_connection
    cut = KEY_PREFIX + str(date.today() - timedelta(days=keep_days))
    con = get_pg_connection()
    with con, con.cursor() as cur:
        cur.execute("DELETE FROM app_meta WHERE key LIKE %s AND key < %s", (KEY_PREFIX + "2%", cut))
        n = cur.rowcount
    con.close()
    return n
