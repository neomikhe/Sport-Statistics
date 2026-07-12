"""
Refresco de datos NBA — EJECUTAR EN LOCAL (no en la nube).

nba_api (stats.nba.com) bloquea las IPs de los datacenters (GitHub Actions,
Streamlit Cloud), así que el baloncesto NO se puede refrescar desde el cron. Este
script se corre desde tu PC (IP residencial, que sí funciona) apuntando a la BD de
la nube, para poblar basketball_games (pace/ortg) que el resto del pipeline usa.

Uso (desde tu PC):
    # 1. Instala nba_api si no lo tienes:  pip install nba_api
    # 2. Apunta a la BD de la nube y ejecuta:
    #    Windows (PowerShell):  $env:DATABASE_URL="postgresql://..."; python scripts/refresh_nba_local.py
    #    Linux/Mac:             DATABASE_URL="postgresql://..." python scripts/refresh_nba_local.py

Descarga las 2 temporadas más recientes (previa + actual) por defecto, o las que
pases como argumentos:
    python scripts/refresh_nba_local.py 2023-24 2024-25
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _recent_seasons() -> list:
    t = date.today()
    start = t.year if t.month >= 9 else t.year - 1
    return [f"{y}-{(y + 1) % 100:02d}" for y in (start - 1, start)]


def main() -> int:
    seasons = sys.argv[1:] or _recent_seasons()
    print(f"Refrescando NBA en local (temporadas: {', '.join(seasons)})…")
    print("Recuerda: DATABASE_URL debe apuntar a la BD de la nube para que suba allí.\n")
    code = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "download_basketball_data.py"), *seasons],
        cwd=str(ROOT),
    ).returncode
    if code == 0:
        print("\n[OK] Baloncesto actualizado. El analizador ya lo verá.")
    else:
        print(f"\n[FALLO] código {code}. ¿Instalaste nba_api? ¿DATABASE_URL correcto?")
    return code


if __name__ == "__main__":
    sys.exit(main())
