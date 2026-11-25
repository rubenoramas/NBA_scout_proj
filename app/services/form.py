"""Recent form: the same numbers over a window of games.

A window is "season" (every regular-season game this season) or "last10"
(each team's last 10 played regular-season games). For a player, the window
is his team's games: on a player card, "last10" means the team's last 10
games, of which he played some.

Team stats are computed from the box scores with one function for both
windows. The season view of the app keeps the NBA's official numbers;
computing the season with this same code is the consistency check
(python -m app.services.form).
"""

from app.db import db
from app.services.context import current_season

FORMS = ("season", "last10")
LAST_N = 10
FORM_LABEL = {"season": "Season", "last10": "Last 10 games"}
# Last 10 USG% is ranked among players with at least this many minutes in
# their team's last 10 games, and marked a small sample below it.
FORM_USG_MINUTES = 100

SUM = ["pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "tov", "min"]


def parse_form(raw):
    """(form, error message)."""
    form = (raw or "season").strip().lower()
    if form not in FORMS:
        return None, "form must be \"season\" or \"last10\"."
    return form, None


# Kept in memory until the seed data changes (same idea as the matchup model).
_cache = {}


def _seed_key():
    hashes = db.meta.find_one({"_id": "seed_hashes"}) or {}
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return str(sorted((hashes.get("files") or {}).items())) + str(meta.get("data_as_of"))


def _cached(name, build):
    key = (name, _seed_key())
    if key not in _cache:
        if len(_cache) > 50:
            _cache.clear()
        _cache[key] = build()
    return _cache[key]


def team_game_totals(season):
    """{(game_id, team_id): totals} for this season's regular-season games,
    with game_date and the opponent's id."""
    return _cached(("totals", season), lambda: _team_game_totals(season))


def _team_game_totals(season):
    pipeline = [
        {"$match": {"season": season, "game_id": {"$regex": "^002"}}},
        {"$group": {"_id": {"g": "$game_id", "t": "$team_id"}, "date": {"$first": "$game_date"},
                    **{k: {"$sum": f"${k}"} for k in SUM}}},
    ]
    rows = {}
    by_game = {}
    for d in db.game_logs.aggregate(pipeline):
        key = (d["_id"]["g"], d["_id"]["t"])
        rows[key] = {"game_id": key[0], "team_id": key[1], "date": d["date"], **{k: d[k] or 0 for k in SUM}}
        by_game.setdefault(key[0], []).append(key[1])
    for gid, teams in by_game.items():
        if len(teams) == 2:
            rows[(gid, teams[0])]["opp"] = teams[1]
            rows[(gid, teams[1])]["opp"] = teams[0]
    return {k: v for k, v in rows.items() if "opp" in v}


def window_games(totals, team_id, form):
    """The team's game ids in the window, newest first."""
    games = sorted((v for (g, t), v in totals.items() if t == team_id), key=lambda v: v["date"], reverse=True)
    if form == "last10":
        games = games[:LAST_N]
    return [g["game_id"] for g in games]


def _poss(t):
    return t["fga"] + 0.44 * t["fta"] - t["oreb"] + t["tov"]


def team_stats_over(totals, team_id, game_ids):
    """Team stats over a set of games, from the box scores. Possessions are
    the box-score estimate averaged over both teams."""
    us = {k: 0 for k in SUM}
    them = {k: 0 for k in SUM}
    for gid in game_ids:
        mine = totals[(gid, team_id)]
        theirs = totals[(gid, mine["opp"])]
        for k in SUM:
            us[k] += mine[k]
            them[k] += theirs[k]
    poss = (_poss(us) + _poss(them)) / 2
    minutes = us["min"] / 5 if us["min"] else None

    def div(a, b):
        return a / b if b else None

    off, deff = div(100 * us["pts"], poss), div(100 * them["pts"], poss)
    return {
        "gp": len(game_ids),
        "off_rating": off, "def_rating": deff, "net_rating": off - deff if off is not None and deff is not None else None,
        "pace": div(48 * poss, minutes) if minutes else None,
        "efg_pct": div(us["fgm"] + 0.5 * us["fg3m"], us["fga"]),
        "tov_pct": div(us["tov"], us["fga"] + 0.44 * us["fta"] + us["tov"]),
        "oreb_pct": div(us["oreb"], us["oreb"] + them["dreb"]),
        "fta_rate": div(us["fta"], us["fga"]),
        "opp_efg_pct": div(them["fgm"] + 0.5 * them["fg3m"], them["fga"]),
        "opp_tov_pct": div(them["tov"], them["fga"] + 0.44 * them["fta"] + them["tov"]),
        "opp_oreb_pct": div(them["oreb"], them["oreb"] + us["dreb"]),
        "opp_fta_rate": div(them["fta"], them["fga"]),
    }


def all_team_stats(form, season=None):
    """{team_id: stats} for every team over the window."""
    season = season or current_season()
    totals = team_game_totals(season)
    teams = {t for (_g, t) in totals}
    return {t: team_stats_over(totals, t, window_games(totals, t, form)) for t in teams}


def form_games(team_id, form, season=None):
    """The team's game ids in the window (None for the whole season, so
    callers can skip the filter)."""
    if form == "season":
        return None
    season = season or current_season()
    return window_games(team_game_totals(season), team_id, form)


# ---- Players ---------------------------------------------------------------

def player_window_lines(team_id, form, season=None):
    """{player_id: summed line over the team's window games} plus team sums
    per player (over the games he played), for per-game stats, TS% and USG%."""
    season = season or current_season()
    games = form_games(team_id, form, season)
    match = {"season": season, "team_id": team_id, "game_id": {"$regex": "^002"}}
    if games is not None:
        match["game_id"] = {"$in": games}
    lines = list(db.game_logs.find(match, {"_id": 0}))
    team_by_game = {}
    for ln in lines:
        t = team_by_game.setdefault(ln["game_id"], {"fga": 0, "fta": 0, "tov": 0, "min": 0})
        for k in t:
            t[k] += ln.get(k) or 0
    out = {}
    for ln in lines:
        if not (ln.get("min") or 0):
            continue
        p = out.setdefault(ln["player_id"], {"gp": 0, **{k: 0 for k in SUM}, "reb": 0, "ast": 0, "stl": 0, "blk": 0,
                                             "pf": 0, "team_fga": 0, "team_fta": 0, "team_tov": 0, "team_min": 0})
        p["gp"] += 1
        for k in SUM + ["reb", "ast", "stl", "blk", "pf"]:
            p[k] += ln.get(k) or 0
        t = team_by_game[ln["game_id"]]
        for k in ("fga", "fta", "tov", "min"):
            p[f"team_{k}"] += t[k]
    return out, (len(games) if games is not None else None)


def usg_from_sums(p):
    """Box-score USG% over summed games:
    100 x (FGA + 0.44 FTA + TOV) x (team MIN / 5) / (MIN x (team FGA + 0.44 team FTA + team TOV))."""
    denom = p["min"] * (p["team_fga"] + 0.44 * p["team_fta"] + p["team_tov"])
    return round(100 * (p["fga"] + 0.44 * p["fta"] + p["tov"]) * (p["team_min"] / 5) / denom, 1) if denom else None


def per_game_from_sums(p):
    gp = p["gp"]
    line = {k: round(p[k] / gp, 1) for k in ["min", "pts", "reb", "ast", "stl", "blk", "tov", "oreb", "dreb", "pf",
                                              "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"]}
    line.update({
        "gp": gp,
        "fg_pct": p["fgm"] / p["fga"] if p["fga"] else None,
        "fg3_pct": p["fg3m"] / p["fg3a"] if p["fg3a"] else None,
        "ft_pct": p["ftm"] / p["fta"] if p["fta"] else None,
        "ts_pct": p["pts"] / (2 * (p["fga"] + 0.44 * p["fta"])) if p["fga"] + p["fta"] else None,
    })
    return line


def league_window_usage(form, season=None):
    """{player_id: {usg_pct, min, rank, ranked_of}} over every team's window."""
    season = season or current_season()
    return _cached(("usage", form, season), lambda: _league_window_usage(form, season))


def _league_window_usage(form, season):
    out = {}
    for team in db.teams.distinct("_id"):
        sums, _ = player_window_lines(team, form, season)
        for pid, p in sums.items():
            out[pid] = {"usg_pct": usg_from_sums(p), "min": p["min"]}
    ranked = sorted((pid for pid, v in out.items() if v["usg_pct"] is not None and v["min"] >= FORM_USG_MINUTES),
                    key=lambda pid: -out[pid]["usg_pct"])
    for i, pid in enumerate(ranked):
        out[pid]["rank"] = i + 1
    for v in out.values():
        v.setdefault("rank", None)
        v["ranked_of"] = len(ranked)
    return out


# ---- Consistency check ---------------------------------------------------------

def consistency_report():
    """Season team stats computed from the box scores against the NBA's
    official numbers: the gap per stat, averaged over the 30 teams."""
    ours = all_team_stats("season")
    official = {d["team_id"]: d for d in db.team_stats.find({}, {"_id": 0})}
    keys = ["off_rating", "def_rating", "net_rating", "pace", "efg_pct", "tov_pct", "oreb_pct", "fta_rate",
            "opp_efg_pct", "opp_tov_pct", "opp_oreb_pct", "opp_fta_rate"]
    rows = []
    for k in keys:
        pairs = [(ours[t][k], official[t][k]) for t in ours if t in official and official[t].get(k) is not None
                 and ours[t][k] is not None]
        scale = 100 if k.endswith("_pct") else 1
        gaps = [(a - b) * scale for a, b in pairs]
        rows.append({"stat": k, "teams": len(pairs), "mean_gap": sum(gaps) / len(gaps),
                     "mean_abs_gap": sum(abs(g) for g in gaps) / len(gaps), "max_abs_gap": max(abs(g) for g in gaps),
                     "rank_agreement": _rank_corr([a for a, _ in pairs], [b for _, b in pairs])})
    return rows


def _rank_corr(a, b):
    """Spearman rank correlation (no ties expected)."""
    ra = {i: r for r, i in enumerate(sorted(range(len(a)), key=lambda i: a[i]))}
    rb = {i: r for r, i in enumerate(sorted(range(len(b)), key=lambda i: b[i]))}
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


if __name__ == "__main__":
    print("Season team stats from box scores vs the NBA's official numbers (30 teams).")
    print("Gaps are ours minus official; percentages in percentage points.")
    print(f"{'Stat':<14}{'Mean gap':>10}{'Mean |gap|':>12}{'Max |gap|':>11}{'Rank corr':>11}")
    for r in consistency_report():
        print(f"{r['stat']:<14}{r['mean_gap']:>10.2f}{r['mean_abs_gap']:>12.2f}{r['max_abs_gap']:>11.2f}{r['rank_agreement']:>11.3f}")
