"""
Dia 1 - Test de cierre de infraestructura.

Verifica:
  1. Que .env se carga correctamente.
  2. Que PostgreSQL acepta la conexion con las credenciales.
  3. Que el schema se ha ejecutado (tabla 'sports' existe con 4 filas).

Uso:
  venv\\Scripts\\activate
  python scripts/test_connection.py

Codigo de salida:
  0 = todo OK, Dia 1 cerrado.
  1 = fallo de conexion o schema no aplicado.
"""
import os
import sys

from dotenv import load_dotenv
import psycopg2

load_dotenv()

required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    print(f"[ERROR] Faltan variables en .env: {', '.join(missing)}")
    sys.exit(1)

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
except psycopg2.OperationalError as e:
    print("[ERROR] No se pudo conectar a PostgreSQL.")
    print(f"  Detalle: {e}")
    print("  Revisa: servicio PostgreSQL arrancado, credenciales en .env, puerto 5432.")
    sys.exit(1)

try:
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print("[OK] Conexion a PostgreSQL establecida.")
        print(f"     {version}")

        cur.execute("SELECT code, name FROM sports ORDER BY id;")
        rows = cur.fetchall()
        if len(rows) != 4:
            print(f"[WARN] Tabla 'sports' tiene {len(rows)} filas, se esperaban 4.")
            print("       Revisa que schema.sql se ejecuto completo.")
            sys.exit(1)

        print("[OK] Schema aplicado. Deportes registrados:")
        for code, name in rows:
            print(f"     - {code}: {name}")

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [r[0] for r in cur.fetchall()]
        print(f"[OK] Tablas creadas ({len(tables)}):")
        for t in tables:
            print(f"     - {t}")

    conn.close()
    print()
    print("========================================")
    print("  Dia 1 cerrado correctamente.")
    print("  Puedes pasar a la Fase 1 (futbol).")
    print("========================================")
    sys.exit(0)

except psycopg2.errors.UndefinedTable:
    print("[ERROR] La tabla 'sports' no existe.")
    print("        Ejecuta: psql -U postgres -d betstats -f core/database/schema.sql")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Fallo inesperado: {type(e).__name__}: {e}")
    sys.exit(1)
