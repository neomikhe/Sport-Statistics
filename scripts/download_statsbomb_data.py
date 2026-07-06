"""
Descarga StatsBomb Open Data (xG, eventos) desde su repositorio publico de GitHub.

Repositorio: https://github.com/statsbomb/open-data
Estructura:
    open-data/data/competitions.json   -> lista de competiciones disponibles
    open-data/data/matches/{comp}/{season}.json
    open-data/data/events/{match_id}.json
    open-data/data/lineups/{match_id}.json

Por defecto descarga el indice de competiciones y guarda en data/raw/statsbomb/.

NOTA: la integracion de xG en el modelo Poisson de fútbol requiere mapear nombres
de equipos StatsBomb a football-data.co.uk (distintos), tarea no trivial.
Este script proporciona la INFRAESTRUCTURA de descarga; el mapeo se documenta en
docs/statsbomb_team_mapping.md (a crear cuando se complete la integracion).

Uso:
    venv\\Scripts\\activate
    python scripts/download_statsbomb_data.py
"""
import json
import sys
from pathlib import Path

import requests


REPO_RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def main():
    output_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "statsbomb"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Descargando indice de competiciones StatsBomb...")
    url = f"{REPO_RAW}/competitions.json"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return 1

    competitions = r.json()
    output_file = output_dir / "competitions.json"
    output_file.write_text(json.dumps(competitions, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Guardado: {output_file}")
    print(f"     {len(competitions)} (competition, season) disponibles")

    # Resumen por competicion
    by_comp = {}
    for c in competitions:
        name = c.get("competition_name", "?")
        season = c.get("season_name", "?")
        by_comp.setdefault(name, []).append(season)

    print()
    print("=" * 70)
    print("  COMPETICIONES DISPONIBLES")
    print("=" * 70)
    for comp, seasons in sorted(by_comp.items()):
        print(f"  {comp:<40} {len(seasons)} temporadas")
        if len(seasons) <= 5:
            for s in seasons:
                print(f"      - {s}")

    print()
    print("[NOTA] Para cargar partidos de una competicion-temporada concreta:")
    print('       url = f"{REPO_RAW}/matches/{competition_id}/{season_id}.json"')
    print()
    print("[NOTA] La integracion completa de xG en el modelo Poisson requiere:")
    print("  1. Descargar partidos+eventos de competiciones que cubran las 5 ligas")
    print("     principales que ya tenemos (Premier, La Liga, Serie A, Bundesliga, Ligue 1)")
    print("  2. Mapear team_name de StatsBomb a 'fd:<name>' de football-data.co.uk")
    print("     (mapping manual ~80 equipos)")
    print("  3. Agregar xG por equipo por partido y guardar en una nueva tabla")
    print("     football_xg(match_id, home_xg, away_xg)")
    print("  4. Re-entrenar GLM Poisson incluyendo home_xg_rolling como feature")
    print()
    print("  StatsBomb cubre ~10 % de partidos de las 5 ligas top (Champions,")
    print("  Mundial, Eurocopa). Para cobertura completa, FBref via soccerdata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
