import logging

_log = logging.getLogger(__name__)


def stamp_meta(key: str, value: str) -> bool:
    try:
        from core.database.connection import get_pg_connection
        con = get_pg_connection()
        with con, con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_meta (key, value, updated_at) VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, str(value)),
            )
        con.close()
        return True
    except Exception as e:
        _log.warning("no se pudo sellar app_meta['%s']: %s", key, e)
        return False


def get_meta(key: str, default=None):
    try:
        import pandas as pd
        from core.database.connection import get_sqlalchemy_engine
        df = pd.read_sql(
            "SELECT value FROM app_meta WHERE key = %(k)s",
            get_sqlalchemy_engine(), params={"k": key},
        )
        return df["value"].iloc[0] if not df.empty else default
    except Exception:
        return default
