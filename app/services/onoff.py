"""On/off impact: how his team scores and allows per 100 possessions with
him on the floor and off it.

The R pull (pulls/pull_stats.R, section 6d) counts possessions and points
from the play-by-play and game lineups and writes player_onoff: one row per
player, season and team. "Off" counts only games he played. Free throws and
possessions that end on free throws are credited to the players on the floor
at the foul. Ratings are computed here.
"""

from app.db import db
from app.services.context import current_season

# Fewer possessions on the floor than this: not shown ("Not enough minutes").
SHOW_MIN_POSS = 250
# Fewer possessions on or off than this: tagged as a small sample.
SMALL_POSS = 1000
NOISE_NOTE = ("On/off is noisy and depends on who a player shares the floor with, "
              "so read it alongside the other numbers.")
FIELDS = ["games", "on_poss_off", "on_poss_def", "on_pts_for", "on_pts_against",
          "off_poss_off", "off_poss_def", "off_pts_for", "off_pts_against"]


def per100(pts, poss):
    return round(100 * pts / poss, 1) if poss else None


def side(pts_for, pts_against, poss_off, poss_def):
    o, d = per100(pts_for, poss_off), per100(pts_against, poss_def)
    return {"off_rating": o, "def_rating": d,
            "net_rating": round(o - d, 1) if o is not None and d is not None else None,
            # Possessions = the average of his team's and the opponent's.
            "poss": round((poss_off + poss_def) / 2)}


def rate_line(t):
    """Ratings from summed totals (one team, or a season across teams)."""
    on = side(t["on_pts_for"], t["on_pts_against"], t["on_poss_off"], t["on_poss_def"])
    off = side(t["off_pts_for"], t["off_pts_against"], t["off_poss_off"], t["off_poss_def"])
    shown = on["poss"] >= SHOW_MIN_POSS
    diff = (round(on["net_rating"] - off["net_rating"], 1)
            if shown and on["net_rating"] is not None and off["net_rating"] is not None else None)
    return {"games": t["games"], "on": on, "off": off, "on_off_net": diff, "shown": shown,
            "small_sample": on["poss"] < SMALL_POSS or off["poss"] < SMALL_POSS}


def season_line(rows):
    """One season: summed over every team he played for, plus each team."""
    if not rows:
        return None
    total = {k: sum(r.get(k) or 0 for r in rows) for k in FIELDS}
    line = rate_line(total)
    line["teams"] = [{"team_id": r["team_id"], **rate_line(r)} for r in rows] if len(rows) > 1 else None
    return line


def by_player(season):
    """{player_id: season line} for every player in one season."""
    rows = {}
    for d in db.player_onoff.find({"season": season}, {"_id": 0}):
        rows.setdefault(d["player_id"], []).append(d)
    return {pid: season_line(r) for pid, r in rows.items()}


def compact(line):
    """The few fields tables need."""
    if not line:
        return None
    return {"on_off_net": line["on_off_net"], "shown": line["shown"], "small_sample": line["small_sample"],
            "on_poss": line["on"]["poss"], "off_poss": line["off"]["poss"]}


def player_onoff(player_id):
    meta = db.meta.find_one({"_id": "seed"}) or {}
    season, last = meta.get("season") or current_season(), meta.get("last_season")
    docs = list(db.player_onoff.find({"player_id": player_id}, {"_id": 0}))
    return {
        "this_season": {"season": season, **(season_line([d for d in docs if d["season"] == season]) or {"empty": True})},
        "last_season": {"season": last, **(season_line([d for d in docs if d["season"] == last]) or {"empty": True})},
        "rules": {"show_min_poss": SHOW_MIN_POSS, "small_poss": SMALL_POSS},
        "note": NOISE_NOTE,
    }
