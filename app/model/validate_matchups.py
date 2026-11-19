"""Validate the matchup model. Run inside the web container:
    docker compose exec web python -m app.model.validate_matchups

1. Train on last season plus this season's games before the split date, then
   predict every pair in the games since. Compare predicted and actual
   points per 100 partial possessions (weighted by possessions).
2. For each game since the split, run the assignment on the two actual
   starting fives and check how often the model's pick is the defender who
   actually guarded each scorer most, against a same-position guess.
"""

import math
import sys
from collections import defaultdict

from app.db import db
from app.model.matchups import best_assignment, fit, pair_estimate, position_blocked
from app.services.matchups import bios as load_bios

SPLIT = "2026-11-01"
POS_ORDER = {"G": 0, "F": 1, "C": 2}


def weighted_corr(xs, ys, ws):
    tw = sum(ws)
    mx = sum(w * x for x, w in zip(xs, ws)) / tw
    my = sum(w * y for y, w in zip(ys, ws)) / tw
    cov = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    vx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    vy = sum(w * (y - my) ** 2 for y, w in zip(ys, ws))
    return cov / math.sqrt(vx * vy) if vx and vy else 0.0


def prepare():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    season, last = meta["season"], meta["last_season"]
    info = load_bios()
    games = list(db.matchup_games.find({}, {"_id": 0}))
    train_games = [g for g in games if g["game_date"] < SPLIT]
    test_games = [g for g in games if g["game_date"] >= SPLIT]
    pairs = [p for p in db.matchup_pairs.find({"season": last}, {"_id": 0})]
    agg = defaultdict(lambda: [0.0, 0.0])
    for g in train_games:
        a = agg[(g["off_id"], g["def_id"])]
        a[0] += g["pts"]; a[1] += g["poss"]
    pairs += [{"season": season, "off_id": o, "def_id": d, "pts": v[0], "poss": v[1]} for (o, d), v in agg.items()]
    minutes = defaultdict(float)
    for d in db.game_logs.find({"season": season, "game_date": {"$lt": SPLIT}}, {"player_id": 1, "min": 1}):
        minutes[d["player_id"]] += d.get("min") or 0
    return season, info, pairs, dict(minutes), train_games, test_games


def evaluate(model, season, info, test_games):
    """Returns (prediction table rows, assignment results)."""
    test = defaultdict(lambda: [0.0, 0.0])
    for g in test_games:
        t = test[(g["off_id"], g["def_id"])]
        t[0] += g["pts"]; t[1] += g["poss"]
    rows = [(o, d, v[0], v[1]) for (o, d), v in test.items() if v[1] > 0]
    actual = [pts / poss * 100 for _o, _d, pts, poss in rows]
    weights = [poss for *_x, poss in rows]
    tw = sum(weights)
    lg = model["league_all"]
    preds = {
        "league average": [lg * 100] * len(rows),
        "scorer norm only (B)": [model["B"].get(o, lg) * 100 for o, _d, _p, _q in rows],
        "B + defender (B + D)": [(model["B"].get(o, lg) + model["D"].get(d, 0)) * 100 for o, d, _p, _q in rows],
        "full model (E)": [pair_estimate(model, o, d)["expected"] * 100 for o, d, _p, _q in rows],
    }
    big = [i for i, w in enumerate(weights) if w >= 10]
    table = {}
    for name, p in preds.items():
        table[name] = (
            weighted_corr(p, actual, weights),
            sum(w * abs(x - y) for x, y, w in zip(p, actual, weights)) / tw,
            weighted_corr([p[i] for i in big], [actual[i] for i in big], [weights[i] for i in big]),
        )
    full = preds["full model (E)"]
    order = sorted(range(len(rows)), key=lambda i: full[i])
    bands, band, acc = [], [], 0.0
    for i in order:
        band.append(i); acc += weights[i]
        if acc >= tw / 5 or i == order[-1]:
            bands.append(band); band, acc = [], 0.0
    calibration = [(sum(full[i] * weights[i] for i in b) / sum(weights[i] for i in b),
                    sum(actual[i] * weights[i] for i in b) / sum(weights[i] for i in b)) for b in bands]

    starters = defaultdict(lambda: defaultdict(list))
    for d in db.game_logs.find({"season": season, "game_date": {"$gte": SPLIT}, "starter": True},
                               {"game_id": 1, "team_id": 1, "player_id": 1}):
        starters[d["game_id"]][d["team_id"]].append(d["player_id"])
    by_game = defaultdict(list)
    for g in test_games:
        by_game[g["game_id"]].append(g)
    usage = {d["player_id"]: d.get("usg_pct") or 0.2 for d in db.player_stats.find({"season": season}, {"player_id": 1, "usg_pct": 1})}
    positions = {pid: b.get("position") for pid, b in info.items()}

    def same_position_guess(scorers, defenders):
        key = lambda p: (POS_ORDER.get(positions.get(p), 1), (info.get(p) or {}).get("height_inches") or 78)  # noqa: E731
        return dict(zip(sorted(scorers, key=key), sorted(defenders, key=key)))

    c = defaultdict(int)
    for gid, teams in starters.items():
        if len(teams) != 2 or any(len(v) != 5 for v in teams.values()):
            continue
        for off_team, scorers in teams.items():
            defenders = [p for t, ps in teams.items() if t != off_team for p in ps]
            guarded = defaultdict(lambda: defaultdict(float))
            for r in by_game.get(gid, []):
                if r["off_id"] in scorers and r["def_id"] in defenders:
                    guarded[r["off_id"]][r["def_id"]] += r["poss"]
            cost = lambda s, d: pair_estimate(model, s, d)["expected"]  # noqa: E731
            u = {s: usage.get(s, 0.2) for s in scorers}
            free, _t, _g = best_assignment(scorers, defenders, cost, u)
            guard, _t, _g = best_assignment(scorers, defenders, cost, u,
                                            lambda s, d: position_blocked(model, s, d, positions))
            pos_guess = same_position_guess(scorers, defenders)
            for s in scorers:
                if not guarded[s]:
                    continue
                top = max(guarded[s], key=guarded[s].get)
                c["n"] += 1
                c["free"] += free[s] == top
                c["guard"] += guard[s] == top
                c["pos"] += pos_guess[s] == top
                c["free_gc"] += {positions.get(s), positions.get(free[s])} == {"G", "C"}
                c["actual_gc"] += {positions.get(s), positions.get(top)} == {"G", "C"}
    return table, calibration, c, len(rows), tw


CONFIGS = [
    ("before: no position adjustment, k = 50", False, 50),
    ("position-relative, k = 50", True, 50),
    ("position-relative, k = 100", True, 100),
    ("position-relative, k = 200", True, 200),
]


def main():
    season, info, pairs, minutes, train_games, test_games = prepare()
    print(f"Trained on {len(pairs)} pair-seasons ({len(train_games)} game rows before {SPLIT}); "
          f"testing on {len(test_games)} game rows since.")
    for label, relative, k in CONFIGS:
        model = fit(pairs, minutes, season, info, k_pair=k, position_relative=relative)
        table, calibration, c, n_pairs, tw = evaluate(model, season, info, test_games)
        n = c["n"] or 1
        print(f"\n=== {label} ===")
        print(f"Size fit per 100: height {model['beta'][0]*100:+.3f}/in, weight {model['beta'][1]*100:+.3f}/10 lb, "
              f"wingspan {model['beta'][2]*100:+.3f}/in; explains {model['size_r2']:.2%} of the leftover variance.")
        if relative:
            print("Position averages removed (per 100): " + ", ".join(
                f"{p} {v*100:+.2f}" for p, v in sorted(model["position_avg"].items())))
        print(f"1. {n_pairs} test pairs, {tw:.0f} partial possessions")
        print(f"   {'prediction':24} {'corr':>6} {'MAE':>6} {'corr 10+':>9}")
        for name, (corr, mae, corr_big) in table.items():
            print(f"   {name:24} {corr:6.3f} {mae:6.1f} {corr_big:9.3f}")
        print("   calibration (predicted, actual): " + "  ".join(f"{p:.1f}/{a:.1f}" for p, a in calibration))
        print(f"2. {c['n']} starting scorers. Unconstrained guard-center picks: {c['free_gc']} ({c['free_gc']/n:.1%}); "
              f"actual {c['actual_gc']/n:.1%}")
        print(f"   matches top defender: model {c['free']/n:.1%}, model + guard {c['guard']/n:.1%}, "
              f"same position {c['pos']/n:.1%}, random 20.0%")


if __name__ == "__main__":
    sys.exit(main())
