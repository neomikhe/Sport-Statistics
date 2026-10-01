import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", ""}


def _secret(key: str, default=None):
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


def _needs_ssl(host: str) -> bool:
    return (host or "").lower() not in _LOCAL_HOSTS


def _database_url() -> str | None:
    url = _secret("DATABASE_URL")
    if not url:
        return None

    parts = urlparse(url)
    scheme = "postgresql" if parts.scheme in ("postgres", "postgresql") else parts.scheme

    query = dict(parse_qsl(parts.query))
    if _needs_ssl(parts.hostname or "") and "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunparse((
        scheme, parts.netloc, parts.path,
        parts.params, urlencode(query), parts.fragment,
    ))


def _params() -> dict:
    host = _secret("DB_HOST", "127.0.0.1")
    params = {
        "host": host,
        "port": _secret("DB_PORT", "5432"),
        "dbname": _secret("DB_NAME"),
        "user": _secret("DB_USER"),
        "password": _secret("DB_PASSWORD"),
    }
    sslmode = _secret("DB_SSLMODE")
    if sslmode:
        params["sslmode"] = sslmode
    elif _needs_ssl(host):
        params["sslmode"] = "require"
    return params


def get_pg_connection():
    url = _database_url()
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(**_params())


def get_sqlalchemy_engine():
    from sqlalchemy import create_engine

    url = _database_url()
    if url:
        sqlalchemy_url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        p = _params()
        sslmode = p.get("sslmode")
        query = f"?sslmode={sslmode}" if sslmode else ""
        sqlalchemy_url = (
            f"postgresql+psycopg2://"
            f"{p['user']}:{p['password']}"
            f"@{p['host']}:{p['port']}/{p['dbname']}{query}"
        )

    return create_engine(sqlalchemy_url, pool_pre_ping=True, pool_recycle=1800)
