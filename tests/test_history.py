from core.history.resolvers import resolve, resolve_football, resolve_winner


def test_futbol_marcador_2_1():
    r = lambda g, s: resolve_football(g, s, 2, 1)   # noqa: E731
    assert r("1X2", "Gana local") is True
    assert r("1X2", "Empate") is False
    assert r("1X2", "Gana visitante") is False
    assert r("Doble oportunidad", "1X (local o empate)") is True
    assert r("Doble oportunidad", "X2 (empate o visitante)") is False
    assert r("Over/Under", "Over 2.5") is True
    assert r("Over/Under", "Under 2.5") is False
    assert r("Over/Under", "Over 3.5") is False
    assert r("Ambos anotan (BTTS)", "Sí") is True
    assert r("Goles del local", "Local Over 1.5") is True
    assert r("Goles del local", "Local Over 2.5") is False
    assert r("Hándicap", "Local -1.5 (gana por ≥2)") is False
    assert r("Hándicap", "Local +1.5") is True
    assert r("Hándicap", "Visitante +1.5") is True
    assert r("Resultado + O/U 2.5", "Local y Over 2.5") is True
    assert r("Resultado + BTTS", "Local y BTTS sí") is True


def test_futbol_empate_dnb_es_push():
    assert resolve_football("DNB (empate anula)", "Local", 1, 1) is None
    assert resolve_football("1X2", "Empate", 1, 1) is True
    assert resolve_football("Doble oportunidad", "12 (sin empate)", 1, 1) is False


def test_moneyline_generico():
    assert resolve_winner("Ganador (ML)", "Gana local", True) is True
    assert resolve_winner("Ganador (ML)", "Gana visitante", True) is False
    assert resolve_winner("Ganador (ML)", "Gana local", False) is False
    assert resolve_winner("Ganador", "Gana X", True, is_draw=True) is None


def test_dispatcher():
    assert resolve("football", "1X2", "Gana local", {"home_goals": 3, "away_goals": 0}) is True
    assert resolve("basketball", "Ganador (ML)", "Gana visitante",
                   {"home_won": True}) is False


def test_cobertura_todos_los_mercados_de_tiempo_completo():
    from sports.football.markets import all_markets
    markets = all_markets(1.7, 1.0, rho=-0.10)
    sin_resolver = []
    for m in markets:
        if m.get("aprox"):
            continue
        if resolve_football(m["grupo"], m["mercado"], 2, 1) is None:
            sin_resolver.append((m["grupo"], m["mercado"]))
    assert sin_resolver == [], f"Mercados sin resolvedor: {sin_resolver}"
