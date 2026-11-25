"""Validate the game preview: train on last season, test on this season.

Run with:  docker compose exec web python -m app.model.validate_preview
"""

from app.db import db
from app.model.preview import K_CHOICES, build_features, fit, load_box, load_games, load_priors, predict, train, win_prob

BANDS = [(0.0, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 1.01)]


def evaluate(rows, model, net_only):
    played = [r for r in rows if r["margin"] is not None and r["margin"] != 0]
    n = len(played)
    res = {"n": n}
    pred = [predict(model["beta"], r) for r in played]
    res["model_mae"] = sum(abs(r["margin"] - p) for r, p in zip(played, pred)) / n
    res["model_pick"] = sum((p > 0) == (r["margin"] > 0) for r, p in zip(played, pred)) / n
    # Baseline 1: the home team always wins (margin: the training home edge).
    home_edge = model["beta"]["home_court"]
    res["home_pick"] = sum(r["margin"] > 0 for r in played) / n
    res["home_mae"] = sum(abs(r["margin"] - home_edge) for r in played) / n
    # Baseline 2: the better record before the game wins (ties: home).
    def rec(s):
        return s["wins"] / s["games"] if s["games"] else 0.5
    res["record_pick"] = sum((rec(r["home"]) >= rec(r["away"])) == (r["margin"] > 0) for r in played) / n
    # Baseline 3: net rating difference alone (no home court or rest).
    p3 = [predict(net_only["beta"], r) for r in played]
    res["net_mae"] = sum(abs(r["margin"] - p) for r, p in zip(played, p3)) / n
    res["net_pick"] = sum((p >= 0) == (r["margin"] > 0) for r, p in zip(played, p3)) / n
    # Calibration of the home win probability, in bands.
    cal = []
    for lo, hi in BANDS:
        inb = [(win_prob(p, model["sigma"]), r) for r, p in zip(played, pred) if lo <= win_prob(p, model["sigma"]) < hi]
        if inb:
            cal.append((lo, hi, len(inb), sum(w for w, _ in inb) / len(inb), sum(r["margin"] > 0 for _, r in inb) / len(inb)))
    res["calibration"] = cal
    return res


def report(title, res):
    print(f"\n{title}: {res['n']} games")
    print(f"  {'Method':<34}{'Avg error (pts)':>16}{'Winners picked':>16}")
    print(f"  {'Model (net + home + rest)':<34}{res['model_mae']:>16.2f}{100 * res['model_pick']:>15.1f}%")
    print(f"  {'Net rating difference alone':<34}{res['net_mae']:>16.2f}{100 * res['net_pick']:>15.1f}%")
    print(f"  {'Home team always wins':<34}{res['home_mae']:>16.2f}{100 * res['home_pick']:>15.1f}%")
    print(f"  {'Better record wins':<34}{'–':>16}{100 * res['record_pick']:>15.1f}%")
    print("  Calibration of the home win probability:")
    print(f"    {'Band':<12}{'Games':>7}{'Predicted':>11}{'Actual':>9}")
    for lo, hi, n, p, a in res["calibration"]:
        print(f"    {f'{int(lo * 100)}-{min(100, int(hi * 100))}%':<12}{n:>7}{100 * p:>10.1f}%{100 * a:>8.1f}%")


def main():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    this, last = meta["season"], meta["last_season"]
    model, train_rows = train(last)
    net_only = fit(train_rows, ["net_diff"])
    b = model["beta"]
    choices = ", ".join(str(k) for k in K_CHOICES)
    print(f"Trained on {last} regular season: {model['n']} games, K = {model['k']} (picked from {choices})")
    print(f"  margin = {b['home_court']:.2f} home court + {b['net_diff']:.3f} x net difference"
          f" + {b['rest_diff']:.2f} x rest difference (days, capped at 3)"
          f" {b['b2b_home']:+.2f} if home is on a back-to-back {b['b2b_away']:+.2f} if away is")
    print(f"  typical error (residual SD): {model['sigma']:.1f} points")
    report(f"Training season {last} (in sample)", evaluate(train_rows, model, net_only))
    test_rows = build_features(load_games([this]), load_box([this]), load_priors(), model["k"])
    report(f"Test season {this} so far (out of sample)", evaluate(test_rows, model, net_only))


if __name__ == "__main__":
    main()
