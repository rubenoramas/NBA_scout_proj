"""Series history between two teams, and who guarded whom in each meeting.

Meetings come from the schedule (this season and last, every game type).
"Who guarded whom" comes from matchup_top: for each game and scorer, the
defender with the most partial possessions on him (pulls/pull_stats.R).
"""

from app.db import db
from app.services.context import get_team, meetings, team_game
from app.services.names import player_names

# Shown as game type tags, and counted separately in the series record.
POSTSEASON = ("playoffs", "play-in")


def series_history(us_id, them_id):
    """Every played meeting, newest first, and a record per season."""
    games = list(db.schedule.find({**meetings(us_id, them_id), "played": True}).sort("game_date", -1))
    ids = [g["game_id"] for g in games]
    with_box = set(db.game_logs.distinct("game_id", {"game_id": {"$in": ids}}))
    with_matchups = set(db.matchup_top.distinct("game_id", {"game_id": {"$in": ids}}))
    rows, records = [], {}
    for g in games:
        m = team_game(g, us_id)
        m["has_box_score"] = g["game_id"] in with_box
        m["has_matchups"] = g["game_id"] in with_matchups
        rows.append(m)
        rec = records.setdefault(m["season"], {"season": m["season"], "wins": 0, "losses": 0,
                                               "postseason_wins": 0, "postseason_losses": 0})
        key = "wins" if m["result"] == "W" else "losses"
        rec[key] += 1
        if m["season_type"] in POSTSEASON:
            rec[f"postseason_{key}"] += 1
    upcoming = db.schedule.count_documents({**meetings(us_id, them_id), "played": False})
    return {
        "meetings": rows,
        "records": sorted(records.values(), key=lambda r: r["season"], reverse=True),
        "default_game_id": next((m["game_id"] for m in rows if m["has_matchups"]), None),
        "upcoming_meetings": upcoming,
    }


def _names(ids):
    return player_names(ids)


def _row(d, names):
    return {
        "scorer_id": d["off_id"], "scorer_name": d.get("off_name") or names.get(d["off_id"]) or f"Player {d['off_id']}",
        "defender_id": d["def_id"],
        "defender_name": d.get("def_name") or names.get(d["def_id"]) or f"Player {d['def_id']}",
        "poss": d["poss"], "pts": d["pts"], "fgm": d["fgm"], "fga": d["fga"], "fg3m": d["fg3m"], "fg3a": d["fg3a"],
        "scorer_poss": d["scorer_poss"], "scorer_pts": d["scorer_pts"],
        "share_of_scorer_poss": d["poss"] / d["scorer_poss"] if d["scorer_poss"] else None,
        "defenders": d.get("defenders"),
    }


def guarded_in_game(game_id, us_id):
    """Returns (result, (message, status)). Both directions: their scorers
    against our defenders, and ours against theirs."""
    game = db.schedule.find_one({"_id": game_id})
    if not game:
        return None, (f"No game has the id {game_id}.", 404)
    if us_id not in (game["home_team_id"], game["away_team_id"]):
        return None, ("This game does not involve the \"us\" team.", 400)
    docs = list(db.matchup_top.find({"game_id": game_id}, {"_id": 0}))
    if not docs:
        return None, ("There is no matchup data for this game.", 404)
    them_id = game["away_team_id"] if game["home_team_id"] == us_id else game["home_team_id"]
    names = _names({d["off_id"] for d in docs} | {d["def_id"] for d in docs})
    # Most points first, then the most possessions he was guarded.
    order = lambda r: (-r["scorer_pts"], -r["scorer_poss"])  # noqa: E731
    theirs = sorted((_row(d, names) for d in docs if d["off_team_id"] == them_id), key=order)
    ours = sorted((_row(d, names) for d in docs if d["off_team_id"] == us_id), key=order)
    return {
        "game": team_game(game, us_id),
        "us": get_team(us_id)["abbreviation"], "them": get_team(them_id)["abbreviation"],
        "their_scorers": theirs, "our_scorers": ours,
    }, None


def last_meeting_guards(us_id, them_id, scorer_ids):
    """Who guarded each of their scorers most in the last played meeting.
    Returns {"game": ..., "has_data": bool, "by_scorer": {pid: {...} or None}}."""
    game = db.schedule.find_one({**meetings(us_id, them_id), "played": True}, sort=[("game_date", -1)])
    if not game:
        return {"game": None, "has_data": False, "by_scorer": {}}
    docs = {d["off_id"]: d for d in db.matchup_top.find({"game_id": game["game_id"], "off_id": {"$in": list(scorer_ids)}},
                                                        {"_id": 0})}
    has_data = bool(docs) or db.matchup_top.count_documents({"game_id": game["game_id"]}, limit=1) > 0
    names = _names({d["def_id"] for d in docs.values()})
    current = {d["_id"]: d.get("team_id") for d in db.players.find({"_id": {"$in": [d["def_id"] for d in docs.values()]}},
                                                                    {"team_id": 1})}
    by_scorer = {}
    for pid in scorer_ids:
        d = docs.get(pid)
        if not d:
            by_scorer[pid] = None
            continue
        by_scorer[pid] = {"defender_id": d["def_id"],
                          "defender_name": d.get("def_name") or names.get(d["def_id"]) or f"Player {d['def_id']}",
                          "poss": d["poss"], "pts": d["pts"], "scorer_poss": d["scorer_poss"],
                          "still_with_us": current.get(d["def_id"]) == us_id}
    return {"game": team_game(game, us_id), "has_data": has_data, "by_scorer": by_scorer}
