import re


def resolve_football(grupo: str, mercado: str, home_goals, away_goals):
    hg, ag = int(home_goals), int(away_goals)
    total, diff = hg + ag, hg - ag
    g, s = grupo, mercado

    if g == "1X2":
        return {"Gana local": hg > ag, "Empate": hg == ag, "Gana visitante": hg < ag}.get(s)

    if g == "Doble oportunidad":
        return {"1X (local o empate)": hg >= ag,
                "12 (sin empate)": hg != ag,
                "X2 (empate o visitante)": hg <= ag}.get(s)

    if g == "DNB (empate anula)":
        if hg == ag:
            return None
        return {"Local": hg > ag, "Visitante": ag > hg}.get(s)

    if g == "Over/Under":
        mm = re.match(r"(Over|Under) (\d+\.\d+)", s)
        if not mm:
            return None
        over = total > float(mm.group(2))
        return over if mm.group(1) == "Over" else not over

    if g == "Ambos anotan (BTTS)":
        both = hg >= 1 and ag >= 1
        return {"Sí": both, "No": not both}.get(s)

    if g == "Goles del local":
        return {"Local Over 0.5": hg >= 1, "Local Over 1.5": hg >= 2, "Local Over 2.5": hg >= 3}.get(s)

    if g == "Goles del visitante":
        return {"Visitante Over 0.5": ag >= 1, "Visitante Over 1.5": ag >= 2,
                "Visitante Over 2.5": ag >= 3}.get(s)

    if g == "Hándicap":
        return {
            "Local -1.5 (gana por ≥2)": diff >= 2,
            "Visitante +1.5": diff <= 1,
            "Local -2.5 (gana por ≥3)": diff >= 3,
            "Visitante +2.5": diff <= 2,
            "Visitante -1.5 (gana por ≥2)": diff <= -2,
            "Local +1.5": diff >= -1,
        }.get(s)

    if g == "Resultado + O/U 2.5":
        return {
            "Local y Over 2.5": hg > ag and total >= 3,
            "Local y Under 2.5": hg > ag and total <= 2,
            "Visitante y Over 2.5": hg < ag and total >= 3,
            "Visitante y Under 2.5": hg < ag and total <= 2,
        }.get(s)

    if g == "Resultado + BTTS":
        return {
            "Local y BTTS sí": hg > ag and ag >= 1,
            "Visitante y BTTS sí": hg < ag and hg >= 1,
            "Empate y BTTS sí": hg == ag and hg >= 1,
        }.get(s)

    return None


STATS_GROUPS = {"Córners totales", "Córners del local", "Córners del visitante",
                "Tarjetas totales", "Tarjeta roja"}


def resolve_football_stats(grupo: str, mercado: str, home_corners, away_corners,
                           home_yellows, away_yellows, home_reds, away_reds):
    if any(v is None for v in (home_corners, away_corners)):
        return None
    hc, ac = int(home_corners), int(away_corners)
    total_c = hc + ac
    total_cards = (int(home_yellows or 0) + int(away_yellows or 0)
                   + int(home_reds or 0) + int(away_reds or 0))
    total_reds = int(home_reds or 0) + int(away_reds or 0)
    g, s = grupo, mercado

    if g in ("Córners totales", "Córners del local", "Córners del visitante"):
        mm = re.search(r"(\d+\.\d+)", s)
        if not mm:
            return None
        line = float(mm.group(1))
        val = {"Córners totales": total_c, "Córners del local": hc,
               "Córners del visitante": ac}[g]
        over = val > line
        return over if "Más de" in s else not over

    if g == "Tarjetas totales":
        mm = re.search(r"(\d+\.\d+)", s)
        if not mm:
            return None
        over = total_cards > float(mm.group(1))
        return over if "Más de" in s else not over

    if g == "Tarjeta roja":
        any_red = total_reds >= 1
        return {"Al menos 1 tarjeta roja": any_red,
                "Ninguna tarjeta roja": not any_red}.get(s)

    return None


def resolve_baseball(grupo: str, mercado: str, home_runs, away_runs):
    hr_, ar = int(home_runs), int(away_runs)
    total, diff = hr_ + ar, hr_ - ar
    g, s = grupo, mercado

    if g == "Ganador (ML)":
        return {"Gana local": hr_ > ar, "Gana visitante": ar > hr_}.get(s)

    if g == "Run line (±1.5)":
        return {"Local -1.5 (gana por ≥2)": diff >= 2, "Visitante +1.5": diff <= 1,
                "Visitante -1.5 (gana por ≥2)": diff <= -2, "Local +1.5": diff >= -1}.get(s)

    if g == "Total carreras":
        mm = re.match(r"(Over|Under) (\d+\.\d+)", s)
        if not mm:
            return None
        over = total > float(mm.group(2))
        return over if mm.group(1) == "Over" else not over

    if g == "Carreras del local":
        return {"Local Over 0.5": hr_ >= 1, "Local Over 2.5": hr_ >= 3}.get(s)
    if g == "Carreras del visitante":
        return {"Visitante Over 0.5": ar >= 1, "Visitante Over 2.5": ar >= 3}.get(s)

    return None


BASEBALL_STATS_GROUPS = {"Hits totales", "Hits del local", "Hits del visitante",
                         "Jonrones totales", "Jonrones", "Ponches totales"}


def resolve_baseball_stats(grupo: str, mercado: str, hh, ah, hhr, ahr, hso, aso):
    def _ou(total, mercado):
        mm = re.search(r"(\d+\.\d+)", mercado)
        if mm is None:
            return None
        over = total > float(mm.group(1))
        return over if "más de" in mercado else not over

    if grupo in ("Hits totales", "Hits del local", "Hits del visitante"):
        if hh is None or ah is None:
            return None
        val = {"Hits totales": int(hh) + int(ah), "Hits del local": int(hh),
               "Hits del visitante": int(ah)}[grupo]
        return _ou(val, mercado)

    if grupo == "Jonrones totales":
        if hhr is None or ahr is None:
            return None
        return _ou(int(hhr) + int(ahr), mercado)

    if grupo == "Jonrones":
        if hhr is None or ahr is None:
            return None
        any_hr = (int(hhr) + int(ahr)) >= 1
        return {"Al menos 1 jonrón": any_hr, "Ningún jonrón": not any_hr}.get(mercado)

    if grupo == "Ponches totales":
        if hso is None or aso is None:
            return None
        return _ou(int(hso) + int(aso), mercado)

    return None


def resolve_winner(grupo: str, mercado: str, home_won: bool, is_draw: bool = False):
    if is_draw and grupo in ("Ganador (ML)", "Ganador"):
        return None
    m = mercado.lower()
    if "gana local" in m or grupo == "Ganador" and "local" in m:
        return bool(home_won)
    if "gana visitante" in m:
        return not bool(home_won)
    return None


def resolve(sport: str, grupo: str, mercado: str, outcome: dict):
    if sport == "football" and grupo in STATS_GROUPS:
        return resolve_football_stats(
            grupo, mercado,
            outcome.get("home_corners"), outcome.get("away_corners"),
            outcome.get("home_yellows"), outcome.get("away_yellows"),
            outcome.get("home_reds"), outcome.get("away_reds"))
    if sport == "football" and "home_goals" in outcome:
        return resolve_football(grupo, mercado, outcome["home_goals"], outcome["away_goals"])
    if "home_won" in outcome:
        return resolve_winner(grupo, mercado, outcome["home_won"], outcome.get("is_draw", False))
    return None
