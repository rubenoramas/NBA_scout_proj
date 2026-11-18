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


def main():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    season, last = meta["season"], meta["last_season"]
    info = load_bios()
    games = list(db.matchup_games.find({}, {"_id": 0}))
    train_games = [g for g in games if g["game_date"] < SPLIT]
    test_games = [g for g in games if g["game_date"] >= SPLIT]

    # Training pairs: all of last season plus this season before the split
    pairs = [p for p in db.matchup_pairs.find({"season": last}, {"_id": 0})]
    agg = defaultdict(lambda: [0.0, 0.0])
    for g in train_games:
        a = agg[(g["off_id"], g["def_id"])]
        a[0] += g["pts"]; a[1] += g["poss"]
    pairs += [{"season": season, "off_id": o, "def_id": d, "pts": v[0], "poss": v[1]} for (o, d), v in agg.items()]
    minutes = defaultdict(float)
    for d in db.game_logs.find({"season": season, "game_date": {"$lt": SPLIT}}, {"player_id": 1, "min": 1}):
        minutes[d["player_id"]] += d.get("min") or 0
    model = fit(pairs, dict(minutes), season, info)
    print(f"Trained on {len(pairs)} pair-seasons ({len(train_games)} game rows before {SPLIT}); "
          f"testing on {len(test_games)} game rows since.")
    print(f"Size fit per 100: height {model['beta'][0]*100:+.3f}/in, weight {model['beta'][1]*100:+.3f}/10 lb, "
          f"wingspan {model['beta'][2]*100:+.3f}/in; explains {model['size_r2']:.2%} of the leftover variance.")

    # 1. Predicted vs actual, per pair over the test period
    test = defaultdict(lambda: [0.0, 0.0])
    for g in test_games:
        t = test[(g["off_id"], g["def_id"])]
        t[0] += g["pts"]; t[1] += g["poss"]
    rows = [(o, d, v[0], v[1]) for (o, d), v in test.items() if v[1] > 0]
    actual = [pts / poss * 100 for _o, _d, pts, poss in rows]
    weights = [poss for *_x, poss in rows]
    preds = {
        "league average": [model["league_all"] * 100] * len(rows),
        "scorer norm only (B)": [model["B"].get(o, model["league_all"]) * 100 for o, _d, _p, _q in rows],
        "B + defender (B + D)": [(model["B"].get(o, model["league_all"]) + model["D"].get(d, 0)) * 100 for o, d, _p, _q in rows],
        "full model (E)": [pair_estimate(model, o, d)["expected"] * 100 for o, d, _p, _q in rows],
    }
    tw = sum(weights)
    print(f"\n1. Pairs in test games: {len(rows)}, {tw:.0f} partial possessions. Actual average "
          f"{sum(a * w for a, w in zip(actual, weights)) / tw:.1f} per 100.")
    print(f"   {'prediction':24} {'weighted corr':>14} {'weighted MAE':>13}")
    for name, p in preds.items():
        corr = weighted_corr(p, actual, weights)
        mae = sum(w * abs(x - y) for x, y, w in zip(p, actual, weights)) / tw
        print(f"   {name:24} {corr:14.3f} {mae:13.1f}")
    # Pairs with real volume, where the noise is smaller
    big = [i for i, w in enumerate(weights) if w >= 10]
    if big:
        bw = [weights[i] for i in big]
        print(f"   Pairs with 10+ possessions in the test period ({len(big)}):")
        for name, p in preds.items():
            print(f"     {name:22} corr {weighted_corr([p[i] for i in big], [actual[i] for i in big], bw):.3f}")
    # Calibration: five bands of the full model's prediction
    full = preds["full model (E)"]
    order = sorted(range(len(rows)), key=lambda i: full[i])
    print("   Calibration of the full model (five bands of equal possessions):")
    band, acc, bands = [], 0.0, []
    for i in order:
        band.append(i); acc += weights[i]
        if acc >= tw / 5 or i == order[-1]:
            bands.append(band); band, acc = [], 0.0
    for b in bands:
        bw = sum(weights[i] for i in b)
        print(f"     predicted {sum(full[i] * weights[i] for i in b) / bw:5.1f}  actual "
              f"{sum(actual[i] * weights[i] for i in b) / bw:5.1f}  ({bw:.0f} poss)")

    # 2. Who guarded whom most, in each test game's starting fives
    starters = defaultdict(lambda: defaultdict(list))
    for d in db.game_logs.find({"season": season, "game_date": {"$gte": SPLIT}, "starter": True},
                               {"game_id": 1, "team_id": 1, "player_id": 1}):
        starters[d["game_id"]][d["team_id"]].append(d["player_id"])
    by_game = defaultdict(list)
    for g in test_games:
        by_game[g["game_id"]].append(g)
    usage = {}
    for d in db.player_stats.find({"season": season}, {"player_id": 1, "usg_pct": 1}):
        usage[d["player_id"]] = d.get("usg_pct") or 0.2
    positions = {pid: b.get("position") for pid, b in info.items()}

    def same_position_guess(scorers, defenders):
        key = lambda p: (POS_ORDER.get(positions.get(p), 1), (info.get(p) or {}).get("height_inches") or 78)  # noqa: E731
        return dict(zip(sorted(scorers, key=key), sorted(defenders, key=key)))

    counts = defaultdict(int)
    for gid, teams in starters.items():
        if len(teams) != 2 or any(len(v) != 5 for v in teams.values()):
            continue
        rows_g = by_game.get(gid, [])
        for off_team, scorers in teams.items():
            defenders = [p for t, ps in teams.items() if t != off_team for p in ps]
            guarded = defaultdict(lambda: defaultdict(float))
            for r in rows_g:
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
                counts["scorers"] += 1
                counts["free_hit"] += free[s] == top
                counts["guard_hit"] += guard[s] == top
                counts["pos_hit"] += pos_guess[s] == top
                gc = {positions.get(s), positions.get(free[s])} == {"G", "C"}
                counts["free_gc"] += gc
                counts["actual_gc"] += {positions.get(s), positions.get(top)} == {"G", "C"}
    n = counts["scorers"]
    if not n:
        print("\n2. No test games with two full starting fives.")
        return
    print(f"\n2. Starting scorers in test games: {n}")
    print(f"   Unconstrained model picked a guard-center pairing for {counts['free_gc']} of {n} "
          f"({counts['free_gc'] / n:.1%}). Actual top defender was a guard-center pairing {counts['actual_gc'] / n:.1%} of the time.")
    print(f"   Pick matches the defender who guarded him most:")
    print(f"     model, unconstrained   {counts['free_hit'] / n:.1%}")
    print(f"     model, position guard  {counts['guard_hit'] / n:.1%}")
    print(f"     same-position guess    {counts['pos_hit'] / n:.1%}")
    print(f"     random                 20.0%")


if __name__ == "__main__":
    sys.exit(main())
