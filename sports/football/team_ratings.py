from dataclasses import dataclass

import numpy as np
import pandas as pd

XI_PER_DAY = 0.002
L2_REG = 3.0
WINDOW_DAYS = 3 * 365


@dataclass
class TeamRatings:
    teams: dict
    attack: np.ndarray
    defense: np.ndarray
    mu: float
    home: float
    n_matches: dict
    ref_date: object

    def has(self, team_id: int) -> bool:
        return team_id in self.teams

    def lambdas(self, home_id: int, away_id: int) -> tuple:
        i, j = self.teams.get(home_id), self.teams.get(away_id)
        ah = self.attack[i] if i is not None else 0.0
        dh = self.defense[i] if i is not None else 0.0
        aa = self.attack[j] if j is not None else 0.0
        da = self.defense[j] if j is not None else 0.0
        return (float(np.exp(self.mu + self.home + ah + da)),
                float(np.exp(self.mu + aa + dh)))

    def team(self, team_id: int) -> dict:
        i = self.teams.get(team_id)
        if i is None:
            return {"attack": 1.0, "defense": 1.0, "matches": 0}
        return {"attack": float(np.exp(self.attack[i])),
                "defense": float(np.exp(self.defense[i])),
                "matches": int(self.n_matches.get(team_id, 0))}


def fit_ratings(matches: pd.DataFrame, ref_date, xi: float = XI_PER_DAY,
                reg: float = L2_REG, window_days: int = WINDOW_DAYS,
                max_iter: int = 25) -> TeamRatings | None:
    ref = pd.Timestamp(ref_date)
    age = (ref - pd.to_datetime(matches["date"])).dt.days
    m = matches[(age > 0) & (age <= window_days)]
    if len(m) < 30:
        return None
    age = (ref - pd.to_datetime(m["date"])).dt.days.to_numpy(dtype=float)
    w = np.exp(-xi * age)

    ids = pd.unique(pd.concat([m["home_team_id"], m["away_team_id"]]).to_numpy())
    idx = {int(t): k for k, t in enumerate(ids)}
    n, nm = len(ids), len(m)
    hi = np.array([idx[int(t)] for t in m["home_team_id"]])
    ai = np.array([idx[int(t)] for t in m["away_team_id"]])

    p = 2 + 2 * n
    X = np.zeros((2 * nm, p))
    rows = np.arange(nm)
    X[rows, 0] = 1.0
    X[rows, 1] = 1.0
    X[rows, 2 + hi] = 1.0
    X[rows, 2 + n + ai] = 1.0
    X[nm + rows, 0] = 1.0
    X[nm + rows, 2 + ai] = 1.0
    X[nm + rows, 2 + n + hi] = 1.0
    y = np.concatenate([m["home_goals"].to_numpy(float), m["away_goals"].to_numpy(float)])
    ww = np.concatenate([w, w])

    penalty = np.zeros(p)
    penalty[2:] = reg
    theta = np.zeros(p)
    theta[0] = np.log(max(np.average(y, weights=ww), 0.1))
    # Newton-Raphson sobre la verosimilitud Poisson ponderada, con L2.
    for _ in range(max_iter):
        lam = np.exp(np.clip(X @ theta, -10, 5))
        grad = X.T @ (ww * (y - lam)) - penalty * theta
        hess = (X * (ww * lam)[:, None]).T @ X + np.diag(penalty)
        step = np.linalg.solve(hess + 1e-9 * np.eye(p), grad)
        theta += step
        if np.max(np.abs(step)) < 1e-7:
            break

    counts = pd.concat([m["home_team_id"], m["away_team_id"]]).value_counts()
    return TeamRatings(
        teams=idx, attack=theta[2:2 + n], defense=theta[2 + n:], mu=float(theta[0]),
        home=float(theta[1]), n_matches={int(k): int(v) for k, v in counts.items()},
        ref_date=ref,
    )
