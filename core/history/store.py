import logging

import pandas as pd

_log = logging.getLogger(__name__)


def _engine():
    from core.database.connection import get_sqlalchemy_engine
    return get_sqlalchemy_engine()


def log_predictions(sport, match_date, home, away, situations,
                    home_id=None, away_id=None) -> int:
    if not situations:
        return 0
    key = f"{sport}:{match_date}:{home}:{away}"
    values = [
        (sport, key, str(match_date), home, away, home_id, away_id,
         s["grupo"], s["mercado"], float(s["prob"]), i + 1)
        for i, s in enumerate(situations)
    ]
    try:
        from psycopg2.extras import execute_values

        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        with con, con.cursor() as cur:
            execute_values(cur, """
                INSERT INTO match_predictions
                  (sport, match_key, match_date, home, away, home_id, away_id,
                   grupo, mercado, probability, rank)
                VALUES %s
                ON CONFLICT (match_key, grupo, mercado) DO NOTHING
            """, values)
        con.close()
        return len(values)
    except Exception as e:
        _log.warning("log_predictions: %s", e)
        return 0


def resolve_football_pending() -> dict:
    from core.history.resolvers import resolve_football, resolve_football_stats, STATS_GROUPS
    eng = _engine()
    pend = pd.read_sql("""
        SELECT p.id, p.grupo, p.mercado,
               m.home_goals AS hg, m.away_goals AS ag,
               m.home_corners AS hc, m.away_corners AS ac,
               m.home_yellows AS hy, m.away_yellows AS ay,
               m.home_reds AS hr, m.away_reds AS ar
        FROM match_predictions p
        JOIN football_matches m
          ON m.home_team_id = p.home_id
         AND m.away_team_id = p.away_id
         AND m.date = p.match_date
        WHERE p.sport = 'football' AND p.hit IS NULL
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
    """, eng)
    if pend.empty:
        return {"resueltas": 0, "push_borradas": 0}

    def _val(x):
        return None if pd.isna(x) else x

    hits, pushes = [], []
    for r in pend.itertuples(index=False):
        if r.grupo in STATS_GROUPS:
            if pd.isna(r.hc) or pd.isna(r.ac):
                continue
            res = resolve_football_stats(r.grupo, r.mercado, r.hc, r.ac,
                                         _val(r.hy), _val(r.ay), _val(r.hr), _val(r.ar))
            if res is not None:
                hits.append((int(r.id), bool(res)))
            continue
        res = resolve_football(r.grupo, r.mercado, r.hg, r.ag)
        if res is None:
            pushes.append(int(r.id))
        else:
            hits.append((int(r.id), bool(res)))

    from core.database.connection import get_pg_connection
    con = get_pg_connection()
    with con, con.cursor() as cur:
        for pid, hit in hits:
            cur.execute("UPDATE match_predictions SET hit=%s, resolved_at=NOW() WHERE id=%s", (hit, pid))
        if pushes:
            cur.execute("DELETE FROM match_predictions WHERE id = ANY(%s)", (pushes,))
    con.close()
    return {"resueltas": len(hits), "push_borradas": len(pushes)}


def resolve_baseball_pending() -> dict:
    from core.history.resolvers import (resolve_baseball, resolve_baseball_stats,
                                        BASEBALL_STATS_GROUPS)
    eng = _engine()
    pend = pd.read_sql("""
        SELECT p.id, p.grupo, p.mercado,
               m.home_runs AS hr, m.away_runs AS ar,
               m.home_hits AS hh, m.away_hits AS ah,
               m.home_hr AS hhr, m.away_hr AS ahr,
               m.home_so AS hso, m.away_so AS aso
        FROM match_predictions p
        JOIN baseball_games m
          ON m.home_team_id = p.home_id
         AND m.away_team_id = p.away_id
         AND m.date = p.match_date
        WHERE p.sport = 'baseball' AND p.hit IS NULL
          AND m.home_runs IS NOT NULL AND m.away_runs IS NOT NULL
    """, eng)
    if pend.empty:
        return {"resueltas": 0}

    def _v(x):
        return None if pd.isna(x) else x

    hits = []
    for r in pend.itertuples(index=False):
        if r.grupo in BASEBALL_STATS_GROUPS:
            res = resolve_baseball_stats(r.grupo, r.mercado, _v(r.hh), _v(r.ah),
                                         _v(r.hhr), _v(r.ahr), _v(r.hso), _v(r.aso))
        else:
            res = resolve_baseball(r.grupo, r.mercado, r.hr, r.ar)
        if res is not None:
            hits.append((int(r.id), bool(res)))

    if hits:
        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        with con, con.cursor() as cur:
            for pid, hit in hits:
                cur.execute("UPDATE match_predictions SET hit=%s, resolved_at=NOW() WHERE id=%s",
                            (hit, pid))
        con.close()
    return {"resueltas": len(hits)}


def resolve_football_from_scores(scores) -> dict:
    from core.history.resolvers import resolve_football, STATS_GROUPS
    if not scores:
        return {"resueltas": 0, "push_borradas": 0}
    by_key = {f"football:{s['date']}:{s['home']}:{s['away']}": s for s in scores}
    try:
        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        n, pushes = 0, []
        with con, con.cursor() as cur:
            cur.execute(
                "SELECT id, match_key, grupo, mercado FROM match_predictions "
                "WHERE sport = 'football' AND hit IS NULL AND match_key = ANY(%s)",
                (list(by_key.keys()),))
            for pid, mk, grupo, mercado in cur.fetchall():
                if grupo in STATS_GROUPS:
                    continue
                s = by_key[mk]
                res = resolve_football(grupo, mercado, s["home_goals"], s["away_goals"])
                if res is None:
                    pushes.append(pid)
                else:
                    cur.execute("UPDATE match_predictions SET hit=%s, resolved_at=NOW() "
                                "WHERE id=%s", (bool(res), pid))
                    n += 1
            if pushes:
                cur.execute("DELETE FROM match_predictions WHERE id = ANY(%s)", (pushes,))
        con.close()
        return {"resueltas": n, "push_borradas": len(pushes)}
    except Exception as e:
        _log.warning("resolve_football_from_scores: %s", e)
        return {"resueltas": 0, "push_borradas": 0}


def resolve_baseball_from_boxscores(boxscores) -> dict:
    from core.history.resolvers import (resolve_baseball, resolve_baseball_stats,
                                        BASEBALL_STATS_GROUPS)
    if not boxscores:
        return {"resueltas": 0}
    by_key = {f"baseball:{b['date']}:{b['home']}:{b['away']}": b for b in boxscores}
    try:
        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        n = 0
        with con, con.cursor() as cur:
            cur.execute(
                "SELECT id, match_key, grupo, mercado FROM match_predictions "
                "WHERE sport = 'baseball' AND hit IS NULL AND match_key = ANY(%s)",
                (list(by_key.keys()),))
            pend = cur.fetchall()
            for pid, mk, grupo, mercado in pend:
                b = by_key[mk]
                if grupo in BASEBALL_STATS_GROUPS:
                    res = resolve_baseball_stats(
                        grupo, mercado, b["home_hits"], b["away_hits"],
                        b["home_hr"], b["away_hr"], b["home_so"], b["away_so"])
                else:
                    res = resolve_baseball(grupo, mercado, b["home_runs"], b["away_runs"])
                if res is not None:
                    cur.execute("UPDATE match_predictions SET hit=%s, resolved_at=NOW() "
                                "WHERE id=%s", (bool(res), pid))
                    n += 1
        con.close()
        return {"resueltas": n}
    except Exception as e:
        _log.warning("resolve_baseball_from_boxscores: %s", e)
        return {"resueltas": 0}


def expire_old(months: int = 3) -> int:
    try:
        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        with con, con.cursor() as cur:
            cur.execute(
                "DELETE FROM match_predictions "
                "WHERE match_date < (CURRENT_DATE - (%s || ' months')::interval)",
                (str(months),),
            )
            n = cur.rowcount
        con.close()
        return n
    except Exception as e:
        _log.warning("expire_old: %s", e)
        return 0


def _where(sport: str = None, since=None) -> tuple:
    where = "WHERE hit IS NOT NULL"
    params = {}
    if sport:
        where += " AND sport = %(sport)s"
        params["sport"] = sport
    if since:
        where += " AND match_date >= %(since)s"
        params["since"] = str(since)
    return where, params


def history_summary(sport: str = None, since=None) -> pd.DataFrame:
    try:
        where, params = _where(sport, since)
        return pd.read_sql(f"""
            SELECT sport, grupo,
                   COUNT(*)                                   AS n,
                   SUM(CASE WHEN hit THEN 1 ELSE 0 END)       AS aciertos,
                   AVG(probability)                           AS prob_media,
                   AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END)   AS tasa_acierto,
                   AVG(POWER(probability - CASE WHEN hit THEN 1.0 ELSE 0.0 END, 2)) AS brier
            FROM match_predictions
            {where}
            GROUP BY sport, grupo
            ORDER BY n DESC
        """, _engine(), params=params or None)
    except Exception:
        return pd.DataFrame(columns=["sport", "grupo", "n", "aciertos", "prob_media",
                                     "tasa_acierto", "brier"])


def history_trend(sport: str = None, since=None) -> pd.DataFrame:
    try:
        where, params = _where(sport, since)
        return pd.read_sql(f"""
            SELECT date_trunc('week', match_date)::date AS semana,
                   COUNT(*)                                 AS n,
                   AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) AS tasa,
                   AVG(probability)                         AS prob_media,
                   AVG(POWER(probability - CASE WHEN hit THEN 1.0 ELSE 0.0 END, 2)) AS brier
            FROM match_predictions
            {where}
            GROUP BY 1 ORDER BY 1
        """, _engine(), params=params or None)
    except Exception:
        return pd.DataFrame(columns=["semana", "n", "tasa", "prob_media", "brier"])


def history_points(sport: str = None, since=None, limit: int = 50000) -> pd.DataFrame:
    try:
        where, params = _where(sport, since)
        params["lim"] = int(limit)
        return pd.read_sql(f"""
            SELECT probability, hit FROM match_predictions
            {where}
            ORDER BY match_date DESC
            LIMIT %(lim)s
        """, _engine(), params=params)
    except Exception:
        return pd.DataFrame(columns=["probability", "hit"])


def recent_resolved(limit: int = 200, sport: str = None, since=None) -> pd.DataFrame:
    try:
        where, params = _where(sport, since)
        params["lim"] = int(limit)
        return pd.read_sql(f"""
            SELECT match_date, sport, home, away, grupo, mercado,
                   probability, hit
            FROM match_predictions
            {where}
            ORDER BY match_date DESC, id DESC
            LIMIT %(lim)s
        """, _engine(), params=params)
    except Exception:
        return pd.DataFrame(columns=["match_date", "sport", "home", "away",
                                     "grupo", "mercado", "probability", "hit"])
