"""Game preview for the app: projections for upcoming games, the saved
projections and their running record, and the backtest.

The model itself is in app/model/preview.py. It is trained on last season
and kept in memory until the seed data changes.

Two error numbers, for two jobs:
- "average miss" (mean absolute error on the training games, about 11
  points) is what the screen shows: how far off a projection usually is.
- sigma (the residual standard deviation, about 14.6 points) turns a margin
  into a win probability: P(home wins) = Phi(margin / sigma). It is larger
  than the average miss because a few big misses weigh more in it.
"""

from datetime import datetime, timezone

from app.db import db
from app.model.preview import build_features, load_box, load_games, load_priors, predict, train, win_prob

_cache = {"key": None, "model": None, "rows": None, "backtest": None}


def _seed_key():
    hashes = db.meta.find_one({"_id": "seed_hashes"}) or {}
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return str(sorted((hashes.get("files") or {}).items())) + str(meta.get("data_as_of"))


def state():
    """Model, this season's feature rows (played and upcoming) and the backtest."""
    key = _seed_key()
    if _cache["key"] != key or _cache["model"] is None:
        meta = db.meta.find_one({"_id": "seed"}) or {}
        this, last = meta.get("season"), meta.get("last_season")
        model, train_rows = train(last)
        model["avg_miss"] = sum(abs(r["margin"] - predict(model["beta"], r)) for r in train_rows
                                if r["margin"] is not None) / model["n"]
        rows = build_features(load_games([this]), load_box([this]), load_priors(), model["k"])
        _cache.update(key=key, model=model, rows={r["game_id"]: r for r in rows}, backtest=backtest(model, rows))
    return _cache


def backtest(model, rows):
    """What the model would have said before each of this season's games,
    from pre-game data only. Labeled as a backtest, not saved projections."""
    played = [r for r in rows if r["margin"] not in (None, 0)]
    if not played:
        return {"games": 0}
    preds = [predict(model["beta"], r) for r in played]
    return {"games": len(played),
            "avg_miss": round(sum(abs(r["margin"] - p) for r, p in zip(played, preds)) / len(played), 1),
            "picked": round(sum((p > 0) == (r["margin"] > 0) for r, p in zip(played, preds)) / len(played), 3)}


def _abbr(team_id):
    t = db.teams.find_one({"_id": team_id}, {"abbreviation": 1}) or {}
    return t.get("abbreviation")


def describe(model, row):
    """One projection, from the home team's side and from the favorite's."""
    margin = predict(model["beta"], row)
    p_home = win_prob(margin, model["sigma"])
    home, away = _abbr(row["home_team_id"]), _abbr(row["away_team_id"])
    fav_home = margin >= 0
    return {
        "game_id": row["game_id"], "date": row["date"],
        "home_team_id": row["home_team_id"], "away_team_id": row["away_team_id"],
        "home": home, "away": away,
        "home_margin": round(margin, 1),
        "home_win_prob": round(p_home, 3),
        "favorite": home if fav_home else away,
        "favorite_team_id": row["home_team_id"] if fav_home else row["away_team_id"],
        "by": round(abs(margin), 1),
        "favorite_win_prob": round(p_home if fav_home else 1 - p_home, 3),
        "avg_miss": round(model["avg_miss"]),
        "sigma": round(model["sigma"], 1),
        "inputs": {
            "home_net": round(row["home"]["net"], 1), "away_net": round(row["away"]["net"], 1),
            "home_games": row["home"]["games"], "away_games": row["away"]["games"],
            "home_rest": row["home"]["rest"], "away_rest": row["away"]["rest"],
            "home_b2b": row["home"]["b2b"], "away_b2b": row["away"]["b2b"],
        },
    }


def project(game_id):
    """The current projection for one game this season, or None."""
    s = state()
    row = s["rows"].get(game_id)
    return describe(s["model"], row) if row else None


def model_summary():
    m = state()["model"]
    return {"train_season": m["train_season"], "games": m["n"], "k": m["k"],
            "beta": {k: round(v, 3) for k, v in m["beta"].items()},
            "avg_miss": round(m["avg_miss"], 1), "sigma": round(m["sigma"], 1)}


# ---- Saved projections -----------------------------------------------------------

def save_projections():
    """Called after every data load (each pull). Saves the current projection
    for every upcoming game, replacing an earlier one, and freezes the
    projection of every game that has since been played, adding the result.
    A frozen projection is never changed. Returns (saved, frozen)."""
    s = state()
    meta = db.meta.find_one({"_id": "seed"}) or {}
    now = datetime.now(timezone.utc)
    saved = frozen = 0
    for gid, row in s["rows"].items():
        doc = db.projections.find_one({"_id": gid}, {"final": 1})
        if doc and doc.get("final"):
            continue
        if row["margin"] is None:
            p = describe(s["model"], row)
            db.projections.replace_one({"_id": gid}, {"_id": gid, **p, "season": row["season"], "final": False,
                                                      "data_as_of": meta.get("data_as_of"), "saved_at": now},
                                       upsert=True)
            saved += 1
        elif doc:
            # Played since the last save: record the result next to the projection.
            g = db.schedule.find_one({"_id": gid}, {"home_pts": 1, "away_pts": 1})
            db.projections.update_one({"_id": gid}, {"$set": {
                "final": True, "home_pts": g["home_pts"], "away_pts": g["away_pts"],
                "actual_home_margin": g["home_pts"] - g["away_pts"], "frozen_at": now}})
            frozen += 1
    return saved, frozen


def _graded(doc):
    miss = abs(doc["actual_home_margin"] - doc["home_margin"])
    right = (doc["home_margin"] >= 0) == (doc["actual_home_margin"] > 0)
    winner = doc["home"] if doc["actual_home_margin"] > 0 else doc["away"]
    return {k: doc.get(k) for k in ("game_id", "date", "home", "away", "favorite", "by", "favorite_win_prob",
                                    "home_pts", "away_pts", "data_as_of")} | {
        "winner": winner, "miss": round(miss, 1), "picked_winner": right}


def record(team_id=None, recent=5):
    """Running record of saved projections (all games), the team's latest
    graded games, and the backtest for comparison."""
    done = list(db.projections.find({"final": True}, {"_id": 0}).sort("date", -1))
    graded = [_graded(d) for d in done]
    out = {
        "saved": {"games": len(graded),
                  "avg_miss": round(sum(g["miss"] for g in graded) / len(graded), 1) if graded else None,
                  "picked": round(sum(g["picked_winner"] for g in graded) / len(graded), 3) if graded else None},
        "backtest": state()["backtest"],
        "model": model_summary(),
    }
    if team_id is not None:
        mine = [g for d, g in zip(done, graded) if team_id in (d["home_team_id"], d["away_team_id"])]
        out["team_recent"] = mine[:recent]
    return out
