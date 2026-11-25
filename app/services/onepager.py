"""Player one-pager: one printable page on an opposing player, for the
player on our team who will guard him.

Every part reuses data the app already has: the player card (bio, season
line, USG%, injury, favorite shots), the ratings and badges, the matchup
model's top three defenders, plus two seed files made for this page:
play_type_mix (every offensive play type) and assist_pairs (who assisted
whom, parsed from the play-by-play).
"""

from app.db import db
from app.services.context import current_season, get_team
from app.services.matchups import best_defenders
from app.services.players import injury_for, per_game, top_shot_types, usage_for, usage_table

# Play type names as the NBA files spell them, and how the page says them.
PLAY_TYPE_LABELS = {
    "Isolation": "Isolation",
    "PRBallHandler": "Pick and roll ball handler",
    "PRRollMan": "Pick and roll roll man",
    "Postup": "Post up",
    "Spotup": "Spot up",
    "Handoff": "Handoff",
    "Cut": "Cut",
    "OffScreen": "Off screen",
    "OffRebound": "Putbacks",
    "Transition": "Transition",
    "Misc": "Other",
}
# A play type with fewer possessions than this is a small sample. Same k as
# the post-up rating (docs/SPEC.md).
SMALL_PLAY_TYPE_POSS = 25
# Below this many made shots, the assist split is a small sample.
SMALL_ASSIST_FGM = 40
TOP_PASSERS = 3


def season_labels():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return meta.get("season") or current_season(), meta.get("last_season"), meta.get("data_as_of")


def league_ppp(season):
    """League points per possession for each play type in one season."""
    pipeline = [{"$match": {"season": season}},
                {"$group": {"_id": "$play_type", "poss": {"$sum": "$poss"}, "pts": {"$sum": "$pts"}}}]
    return {d["_id"]: d["pts"] / d["poss"] for d in db.play_type_mix.aggregate(pipeline) if d["poss"]}


def play_type_mix(player_id, season, last_season):
    """His play types this season, most used first. Falls back to last
    season when he has none this season, and says so."""
    used = season
    rows = list(db.play_type_mix.find({"player_id": player_id, "season": season}, {"_id": 0}))
    if not rows and last_season:
        used = last_season
        rows = list(db.play_type_mix.find({"player_id": player_id, "season": last_season}, {"_id": 0}))
    if not rows:
        return {"season": None, "last_season_only": False, "total_poss": None, "rows": []}
    league = league_ppp(used)
    total = rows[0].get("total_poss") or sum(r["poss"] for r in rows)
    out = []
    for r in sorted(rows, key=lambda r: -r["poss"]):
        if not r["poss"]:
            continue
        out.append({
            "play_type": r["play_type"],
            "label": PLAY_TYPE_LABELS.get(r["play_type"], r["play_type"]),
            "poss": r["poss"],
            "pts": r["pts"],
            "share": r["poss"] / total if total else None,
            "ppp": r["pts"] / r["poss"],
            "league_ppp": league.get(r["play_type"]),
            "small_sample": r["poss"] < SMALL_PLAY_TYPE_POSS,
        })
    return {"season": used, "last_season_only": used != season, "total_poss": total, "rows": out}


def feeders(player_id, team_id):
    """Who assists him most this season, from assist_pairs."""
    pairs = list(db.assist_pairs.find({"scorer_id": player_id}, {"_id": 0}).sort("ast", -1))
    if not pairs:
        doc = db.players.find_one({"_id": player_id}, {"fgm_total": 1}) or {}
        return {"fgm": doc.get("fgm_total") or 0, "assisted_fgm": 0, "assisted_share": None,
                "small_sample": True, "min_fgm": SMALL_ASSIST_FGM, "passers": []}
    fgm, assisted = pairs[0].get("scorer_fgm") or 0, pairs[0].get("scorer_assisted") or 0
    top = pairs[:TOP_PASSERS]
    names = {d["_id"]: d for d in db.players.find({"_id": {"$in": [p["passer_id"] for p in top]}},
                                                   {"player_name": 1, "team_id": 1, "team_abbr": 1})}
    passers = []
    for p in top:
        who = names.get(p["passer_id"]) or {}
        passers.append({
            "player_id": p["passer_id"],
            "player_name": who.get("player_name") or f"Player {p['passer_id']}",
            # A passer traded since then is marked, so nobody plans around him.
            "now_with": who.get("team_abbr") if who.get("team_id") != team_id else None,
            "ast": p["ast"],
            "ast_fg3": p.get("ast_fg3") or 0,
            "share_of_assisted": p["ast"] / assisted if assisted else None,
        })
    return {"fgm": fgm, "assisted_fgm": assisted, "assisted_share": assisted / fgm if fgm else None,
            "small_sample": fgm < SMALL_ASSIST_FGM, "min_fgm": SMALL_ASSIST_FGM, "passers": passers}


def ratings_block(attr):
    if not attr:
        return {"qualified": False, "ratings": [], "badges": []}
    ratings = [{k: r.get(k) for k in ("key", "label", "rating", "small_sample", "last_season_only")}
               | {"sample": r.get("sample")} for r in attr.get("ratings", [])]
    badges = [{k: b.get(k) for k in ("key", "name", "short", "meaning", "rule", "caveat", "detail")}
              for b in attr.get("badges", [])]
    return {"qualified": bool(attr.get("qualified")), "blend_weight": attr.get("blend_weight"),
            "ratings": ratings, "badges": badges}


def build_page(player_id, vs_id):
    """Returns (page, (message, status)). vs_id is our team, the one whose
    player will guard him."""
    doc = db.players.find_one({"_id": player_id})
    if not doc:
        return None, (f"No player has the id {player_id}.", 404)
    us = get_team(vs_id)
    if not us:
        return None, (f"No team has the id {vs_id}.", 404)
    if doc.get("team_id") == vs_id:
        return None, (f"{doc.get('player_name')} plays for {us['abbreviation']}. "
                      "Pick the team that will guard him, not his own team.", 400)
    season, last_season, data_as_of = season_labels()
    team = db.teams.find_one({"_id": doc.get("team_id")}, {"_id": 0})
    usage = usage_for(player_id, usage_table(season), usage_table(last_season))
    attr = db.attributes.find_one({"_id": player_id}, {"_id": 0})
    shots = list(db.shots.find({"player_id": player_id}, {"_id": 0, "x": 1, "y": 1, "made": 1}))
    bio_keys = ["player_id", "player_name", "team_id", "team_abbr", "position", "height", "height_inches",
                "weight_lbs", "wingspan_inches", "headshot_url"]
    return {
        "data_as_of": data_as_of,
        "season_label": season,
        "player": {k: doc.get(k) for k in bio_keys},
        "team": team,
        "us": {k: us.get(k) for k in ("team_id", "abbreviation", "full_name")},
        "injury": injury_for(player_id),
        "season": per_game(doc),
        "usage": usage,
        "attributes": ratings_block(attr),
        "defenders": best_defenders(vs_id, player_id),
        "shots": {"total_fga": len(shots), "made": sum(1 for s in shots if s["made"]),
                  "top_types": top_shot_types(player_id), "chart": shots},
        "play_types": play_type_mix(player_id, season, last_season),
        "feeders": feeders(player_id, doc.get("team_id")),
    }, None
