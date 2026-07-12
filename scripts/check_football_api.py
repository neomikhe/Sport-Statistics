"""
Diagnóstico de la API de fútbol (football-data.org).

Responde a: ¿la clave está bien?, ¿el servidor la acepta?, ¿cuánta cuota me queda?
y ¿hay partidos en esa fecha? Sirve para distinguir «clave mal puesta» de
«simplemente no hay partidos ese día» (p. ej. parón de verano).

Uso (en local):
    # Windows (PowerShell)
    $env:FOOTBALL_DATA_TOKEN="tu_clave"; python scripts/check_football_api.py
    # Linux/Mac
    FOOTBALL_DATA_TOKEN="tu_clave" python scripts/check_football_api.py

    # Con una fecha concreta:
    python scripts/check_football_api.py 2026-07-12

Gasta solo 2 peticiones (de las 10/min del plan gratuito).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_URL = "https://api.football-data.org/v4/matches?dateFrom={a}&dateTo={b}"


def _request(token: str, a: str, b: str):
    """(status, headers, data). No lanza: devuelve el error como status."""
    req = urllib.request.Request(_URL.format(a=a, b=b),
                                 headers={"X-Auth-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        return e.code, getattr(e, "headers", None), {"error": body}
    except Exception as e:
        return None, None, {"error": str(e)}


def _show_quota(headers) -> None:
    if not headers:
        return
    rem = headers.get("X-Requests-Available-Minute")
    reset = headers.get("X-RequestCounter-Reset")
    if rem is not None:
        print(f"  Cuota: quedan {rem} peticiones este minuto "
              f"(reset en {reset}s)" if reset else f"  Cuota: quedan {rem}")


def main() -> int:
    token = os.getenv("FOOTBALL_DATA_TOKEN")
    print("=" * 62)
    if not token:
        print("[X] NO se encontró la clave en la variable FOOTBALL_DATA_TOKEN.")
        print("    Ponla y vuelve a ejecutar (ver la cabecera de este archivo).")
        return 1
    # Nunca imprimimos NADA del token (ni un fragmento, ni su longitud): esta salida
    # se comparte a menudo en capturas y no debe revelar información de la clave.
    print("[OK] Clave encontrada.")

    day = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m-%d")
    print(f"\n1) Consultando partidos del {day} ...")
    status, headers, data = _request(token, day, day)

    if status == 200:
        matches = data.get("matches", [])
        print("[OK] El servidor ACEPTA tu clave (HTTP 200).")
        _show_quota(headers)
        print(f"     Partidos ese día: {len(matches)}")
        for m in matches[:8]:
            comp = m.get("competition", {}).get("name", "?")
            h = m.get("homeTeam", {}).get("name", "?")
            a = m.get("awayTeam", {}).get("name", "?")
            print(f"       - [{comp}] {h} vs {a}  ({m.get('status')})")
        if not matches:
            print("     -> La clave FUNCIONA; simplemente no hay partidos ese día.")
    elif status in (401, 403):
        print(f"[X] HTTP {status}: el servidor RECHAZA la clave.")
        print("    Revisa que copiaste el token completo, sin espacios.")
        return 1
    elif status == 429:
        print("[!] HTTP 429: rate limit. Espera un minuto y reintenta.")
        _show_quota(headers)
        return 1
    else:
        print(f"[X] Respuesta inesperada: {status} {data.get('error','')}")
        return 1

    # 2) ¿Hay partidos próximamente? (1 sola petición para un rango de 14 días)
    a = date.today()
    b = a + timedelta(days=14)
    print(f"\n2) Buscando partidos entre {a} y {b} (próximos 14 días) ...")
    status2, headers2, data2 = _request(token, a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d"))
    if status2 == 200:
        ms = data2.get("matches", [])
        _show_quota(headers2)
        print(f"     Partidos en los próximos 14 días: {len(ms)}")
        seen = set()
        for m in ms[:10]:
            d = (m.get("utcDate") or "")[:10]
            comp = m.get("competition", {}).get("name", "?")
            if (d, comp) in seen:
                continue
            seen.add((d, comp))
            print(f"       - {d}  [{comp}]")
        if ms:
            print("\n     -> Usa una de esas fechas en el selector de la app.")
        else:
            print("\n     -> No hay partidos en 2 semanas en las 12 competiciones del plan "
                  "gratuito (parón de temporada). No es un fallo de tu clave.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
