import pandas as pd


def attach_entity_ids(engine, sport_code: str, fixtures: list) -> list:
    try:
        ents = pd.read_sql(
            "SELECT id, name FROM entities "
            "WHERE sport_id = (SELECT id FROM sports WHERE code = %(c)s)",
            engine, params={"c": sport_code})
    except Exception:
        return [dict(f, home_id=None, away_id=None) for f in fixtures]

    by_name = {str(n).lower().strip(): int(i) for i, n in zip(ents["id"], ents["name"])}
    out = []
    for f in fixtures:
        f = dict(f)
        f["home_id"] = by_name.get(str(f.get("home", "")).lower().strip())
        f["away_id"] = by_name.get(str(f.get("away", "")).lower().strip())
        out.append(f)
    return out
