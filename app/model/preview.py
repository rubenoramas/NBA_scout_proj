"""Game preview: a projected margin for the home team.

margin = home court + b x (home net - away net) + rest terms

- Net rating: points scored minus allowed per 100 possessions, from the box
  scores of games played BEFORE this game's date in the same season.
  Possessions per game are the usual box-score estimate
  (FGA + 0.44 x FTA - OREB + TOV), averaged over both teams.
- Early in a season the pre-game net rating is blended with last season's
  final net rating (team_priors): (g x current + K x last) / (g + K), where
  g is games played so far. K is picked on the training season.
- Rest: days since the team's previous scheduled game this season (capped
  at 3; a first game counts as 3), and a back-to-back flag for each team.
  The schedule is known in advance, so an upcoming game's rest uses the
  games scheduled before it, played or not.
- Fitted by least squares on last season's regular-season games. The win
  probability is Phi(margin / sigma), sigma being the typical error (the
  residual standard deviation) on the training games.

No leakage: features are built in date order, and a date's games only update
the running totals after every game on that date has its features. A game
never sees itself, a later game or a game on the same day.
"""

import math
from datetime import date

from app.db import db

REST_CAP = 3
K_CHOICES = [0, 1, 2, 3, 5, 10, 15, 20, 30]
FEATURES = ["home_court", "net_diff", "rest_diff", "b2b_home", "b2b_away"]


def _day(text):
    return date.fromisoformat(text[:10])


def phi(x):
    """Standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---- Data ------------------------------------------------------------------

def load_games(seasons):
    """Regular-season games in date order, played or not."""
    return list(db.schedule.find({"season": {"$in": list(seasons)}, "season_type": "regular-season"},
                                 {"_id": 0}).sort([("game_date", 1), ("game_id", 1)]))


def load_box(seasons):
    """{(game_id, team_id): {pts, poss_est}} from the box score lines."""
    pipeline = [
        {"$match": {"season": {"$in": list(seasons)}}},
        {"$group": {"_id": {"g": "$game_id", "t": "$team_id"}, "pts": {"$sum": "$pts"}, "fga": {"$sum": "$fga"},
                    "fta": {"$sum": "$fta"}, "oreb": {"$sum": "$oreb"}, "tov": {"$sum": "$tov"}}},
    ]
    out = {}
    for d in db.game_logs.aggregate(pipeline):
        out[(d["_id"]["g"], d["_id"]["t"])] = {
            "pts": d["pts"], "poss_est": (d["fga"] or 0) + 0.44 * (d["fta"] or 0) - (d["oreb"] or 0) + (d["tov"] or 0)}
    return out


def load_priors():
    """{(team_id, season): final net rating}."""
    return {(d["team_id"], d["season"]): d["net_rating"] for d in db.team_priors.find({}, {"_id": 0})}


def previous_season(label):
    start = int(label[:4]) - 1
    return f"{start}-{(start + 1) % 100:02d}"


# ---- Features ----------------------------------------------------------------

def build_features(games, box, priors, k):
    """One feature row per game, using only games from earlier dates.

    games: schedule documents sorted by date. box: {(game_id, team_id): ...}.
    Returns [{game_id, season, date, home/away ids, features..., margin or None}].
    """
    totals = {}   # (season, team) -> {"pf", "pa", "poss", "g", "w", "last"}
    rows = []
    i = 0
    while i < len(games):
        day = games[i]["game_date"]
        same_day = []
        while i < len(games) and games[i]["game_date"] == day:
            same_day.append(games[i])
            i += 1
        # 1. Features for every game on this date, from totals before it.
        for g in same_day:
            rows.append(feature_row(g, totals, priors, k))
        # 2. Only then add this date's played games to the totals.
        for g in same_day:
            add_game(g, totals, box)
    return rows


def team_state(totals, season, team_id, prior, k, day):
    t = totals.get((season, team_id))
    games = t["g"] if t else 0
    current = 100 * (t["pf"] - t["pa"]) / t["poss"] if t and t["poss"] else None
    if prior is None:
        prior = 0.0  # no earlier season: league average
    net = prior if current is None else (games * current + k * prior) / (games + k)
    rest = REST_CAP if not t or not t.get("last") else min(REST_CAP, (_day(day) - _day(t["last"])).days - 1)
    return {"net": net, "current_net": current, "prior_net": prior, "games": games,
            "wins": t["w"] if t else 0, "rest": rest, "b2b": bool(t and t.get("last")) and rest == 0}


def feature_row(g, totals, priors, k):
    season, day = g["season"], g["game_date"]
    prev = previous_season(season)
    h = team_state(totals, season, g["home_team_id"], priors.get((g["home_team_id"], prev)), k, day)
    a = team_state(totals, season, g["away_team_id"], priors.get((g["away_team_id"], prev)), k, day)
    played = bool(g.get("played")) and g.get("home_pts") is not None
    return {
        "game_id": g["game_id"], "season": season, "date": day,
        "home_team_id": g["home_team_id"], "away_team_id": g["away_team_id"],
        "home": h, "away": a,
        "x": {"home_court": 1.0, "net_diff": h["net"] - a["net"], "rest_diff": h["rest"] - a["rest"],
              "b2b_home": 1.0 if h["b2b"] else 0.0, "b2b_away": 1.0 if a["b2b"] else 0.0},
        "margin": (g["home_pts"] - g["away_pts"]) if played else None,
    }


def add_game(g, totals, box):
    # Rest comes from the schedule, which is known in advance, so every
    # earlier game counts for "last game", played or not. Results count only
    # once played.
    for team in (g["home_team_id"], g["away_team_id"]):
        totals.setdefault((g["season"], team), {"pf": 0, "pa": 0, "poss": 0.0, "g": 0, "w": 0, "last": None})["last"] = g["game_date"]
    if not g.get("played") or g.get("home_pts") is None:
        return
    for team, opp, pf, pa in ((g["home_team_id"], g["away_team_id"], g["home_pts"], g["away_pts"]),
                              (g["away_team_id"], g["home_team_id"], g["away_pts"], g["home_pts"])):
        t = totals.setdefault((g["season"], team), {"pf": 0, "pa": 0, "poss": 0.0, "g": 0, "w": 0, "last": None})
        mine, theirs = box.get((g["game_id"], team)), box.get((g["game_id"], opp))
        if mine and theirs:
            t["pf"] += pf
            t["pa"] += pa
            t["poss"] += (mine["poss_est"] + theirs["poss_est"]) / 2
        t["g"] += 1
        t["w"] += 1 if pf > pa else 0


# ---- Fit -----------------------------------------------------------------------

def solve(a, b):
    """Solve a x = b (small, dense) by Gauss-Jordan elimination."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit(rows, features=FEATURES):
    rows = [r for r in rows if r["margin"] is not None]
    # A feature that is zero in every game (no back-to-backs, say) cannot be
    # estimated: it gets a coefficient of 0 instead of breaking the fit.
    unused = [f for f in features if f != "home_court" and all(r["x"][f] == 0 for r in rows)]
    features = [f for f in features if f not in unused]
    xtx = [[sum(r["x"][f] * r["x"][g] for r in rows) for g in features] for f in features]
    xty = [sum(r["x"][f] * r["margin"] for r in rows) for f in features]
    beta = dict(zip(features, solve(xtx, xty)))
    beta.update({f: 0.0 for f in unused})
    resid = [r["margin"] - predict(beta, r) for r in rows]
    sigma = math.sqrt(sum(e * e for e in resid) / (len(rows) - len(features)))
    return {"beta": beta, "sigma": sigma, "n": len(rows)}


def predict(beta, row):
    return sum(beta[f] * row["x"][f] for f in beta)


def win_prob(margin, sigma):
    return phi(margin / sigma)


def train(train_season):
    """Fit on one season, picking K by error on that same season.
    Returns (model, rows of the training season)."""
    priors = load_priors()
    games = load_games([train_season])
    box = load_box([train_season])
    best = None
    for k in K_CHOICES:
        rows = build_features(games, box, priors, k)
        m = fit(rows)
        mae = sum(abs(r["margin"] - predict(m["beta"], r)) for r in rows if r["margin"] is not None) / m["n"]
        if best is None or mae < best[0]:
            best = (mae, k, m, rows)
    _, k, m, rows = best
    m["k"] = k
    m["train_season"] = train_season
    return m, rows
