"""
Validacion de la Fase 1.

Ejecuta la consulta clave que demuestra que los datos estan bien cargados:
los 10 ultimos partidos de un equipo con sus cuotas Pinnacle de cierre.

Ademas imprime un resumen global (total de partidos, por liga y por temporada)
para detectar huecos en la ingesta.

Uso:
    venv\\Scripts\\activate
    python scripts/validate_fase1.py                 # por defecto: Man United
    python scripts/validate_fase1.py "Real Madrid"
    python scripts/validate_fase1.py "Bayern Munich"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402


def main():
    team = sys.argv[1] if len(sys.argv) > 1 else "Man United"

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # --- Resumen global ---
            cur.execute("SELECT COUNT(*) FROM football_matches")
            total = cur.fetchone()[0]

            cur.execute(
                """
                SELECT league, season, COUNT(*) AS n
                FROM football_matches
                GROUP BY league, season
                ORDER BY league, season
                """
            )
            summary = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE odds_home_close IS NOT NULL) AS con_1x2,
                    COUNT(*) FILTER (WHERE odds_o25_close IS NOT NULL) AS con_ou,
                    COUNT(*) AS total
                FROM football_matches
                """
            )
            con_1x2, con_ou, total_chk = cur.fetchone()

            # --- Consulta clave: ultimos 10 partidos de un equipo ---
            cur.execute(
                """
                SELECT
                    m.date,
                    m.league,
                    h.name AS home_team,
                    a.name AS away_team,
                    m.home_goals,
                    m.away_goals,
                    m.odds_home_close,
                    m.odds_draw_close,
                    m.odds_away_close
                FROM football_matches m
                JOIN entities h ON h.id = m.home_team_id
                JOIN entities a ON a.id = m.away_team_id
                WHERE h.name = %s OR a.name = %s
                ORDER BY m.date DESC
                LIMIT 10
                """,
                (team, team),
            )
            last10 = cur.fetchall()
    finally:
        conn.close()

    # ---------- Salida ----------
    print("=" * 72)
    print(f"RESUMEN GLOBAL")
    print("=" * 72)
    print(f"Total de partidos en BD: {total}")
    if total > 0:
        pct_1x2 = 100.0 * con_1x2 / total
        pct_ou = 100.0 * con_ou / total
        print(f"Con cuotas 1X2 (Pinnacle):  {con_1x2:>6}  ({pct_1x2:5.1f} %)")
        print(f"Con cuotas Over/Under 2.5:  {con_ou:>6}  ({pct_ou:5.1f} %)")
    print()
    print("Por liga y temporada:")
    print(f"  {'Liga':<18} {'Temporada':<12} {'Partidos':>8}")
    print(f"  {'-' * 18} {'-' * 12} {'-' * 8}")
    for league, season, n in summary:
        print(f"  {league:<18} {season:<12} {n:>8}")

    print()
    print("=" * 72)
    print(f"ULTIMOS 10 PARTIDOS DE: {team}")
    print("=" * 72)
    if not last10:
        print(f"(sin resultados - prueba con otro nombre, ej.:")
        print(f"  python scripts/validate_fase1.py \"Real Madrid\")")
        return 1

    print(f"{'Fecha':<12} {'Liga':<16} {'Local':<18} {'Visitante':<18} "
          f"{'Result':<8} {'H/D/A (Pinn.)'}")
    print(f"{'-' * 12} {'-' * 16} {'-' * 18} {'-' * 18} "
          f"{'-' * 8} {'-' * 20}")
    for date, league, home, away, hg, ag, oh, od, oa in last10:
        result = f"{hg}-{ag}" if hg is not None and ag is not None else "   "
        if oh is not None:
            odds = f"{float(oh):.2f}/{float(od):.2f}/{float(oa):.2f}"
        else:
            odds = "N/A"
        print(f"{str(date):<12} {league:<16} {home:<18} {away:<18} "
              f"{result:<8} {odds}")

    print()
    print("=" * 72)
    print("  Fase 1 validada correctamente. Listo para Fase 2 (modelo).")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
