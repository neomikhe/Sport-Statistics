"""
Utilidades de conexion a PostgreSQL.

Resuelve las credenciales en este orden de prioridad:
  1. st.secrets  -> cuando la app corre en Streamlit Community Cloud.
  2. variables de entorno / .env  -> desarrollo local.

Soporta dos formas de configurar la conexion:
  - DATABASE_URL: cadena completa del proveedor PostgreSQL. Recomendada en la nube.
  - DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD: parametros sueltos (local).

Si el host no es local, se fuerza sslmode=require (lo exige el PostgreSQL gestionado).
"""
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", ""}


def _secret(key: str, default=None):
    """Lee una clave de st.secrets si esta disponible; si no, de las env vars."""
    try:
        import streamlit as st  # import perezoso: los scripts no dependen de streamlit

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # Streamlit no instalado, o sin secrets configurados -> caemos a env
        pass
    return os.getenv(key, default)


def _needs_ssl(host: str) -> bool:
    return (host or "").lower() not in _LOCAL_HOSTS


def _database_url() -> str | None:
    """Devuelve una DATABASE_URL normalizada (con sslmode si toca) o None."""
    url = _secret("DATABASE_URL")
    if not url:
        return None

    parts = urlparse(url)
    # Normaliza el esquema a postgresql:// (psycopg2 no entiende postgres://)
    scheme = "postgresql" if parts.scheme in ("postgres", "postgresql") else parts.scheme

    query = dict(parse_qsl(parts.query))
    if _needs_ssl(parts.hostname or "") and "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunparse((
        scheme, parts.netloc, parts.path,
        parts.params, urlencode(query), parts.fragment,
    ))


def _params() -> dict:
    """Parametros sueltos para psycopg2 (fallback cuando no hay DATABASE_URL)."""
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
    """Conexion psycopg2 directa. Ideal para ingestas con execute_values / COPY."""
    url = _database_url()
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(**_params())


def get_sqlalchemy_engine():
    """Engine SQLAlchemy. Ideal para pandas read_sql / to_sql."""
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

    # pool_pre_ping evita conexiones zombi; pool_recycle ayuda con pausas del servidor.
    return create_engine(sqlalchemy_url, pool_pre_ping=True, pool_recycle=1800)
