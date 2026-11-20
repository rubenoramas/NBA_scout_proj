"""Build one structured facts object for the AI report.

Everything here comes from numbers the app already computes. The language
model receives only this object and is told to use nothing else, and the
number check compares its text against these values. Every number is
rounded once, here, so the text and the check see the same values.
Percentages are given as percent numbers (61.8 means 61.8%).
"""

from app.db import db
from app.services.context import game_context
from app.services.matchups import effective_statuses, matchups, parse_overrides
from app.services.players import roster

KEY_USAGE = 25.0  # opposing players at or above this USG% are always included


def r1(v):
    return None if v is None else round(float(v), 1)


def pct(v):
    """0.618 -> 61.8"""
    return None if v is None else round(float(v) * 100, 1)


def team_line(side):
    t, s = side["team"], side.get("standing") or {}
    return {
        "abbreviation": t["abbreviation"], "name": t["full_name"],
        "record": s.get("record"), "seed": s.get("seed"), "conference": s.get("conference"),
        "streak": s.get("streak"), "last_ten": s.get("last_ten"),
        "home_record": s.get("home_record"), "road_record": s.get("road_record"),
    }


def game_line(g, us_abbr):
    if not g:
        return None
    out = {"date": g["date"], "season": g.get("season"), "game_type": g.get("season_type"),
           "venue": us_abbr if g["home"] else g["opponent"]["abbreviation"],
           "opponent": g["opponent"]["abbreviation"]}
    if g.get("played"):
        out.update(result=g["result"], score=f"{g['team_pts']}-{g['opp_pts']}",
                   playoffs=g.get("playoffs"))
    return out


def standout_line(side):
    s = side.get("standout")
    if not s:
        return None
    return {"team": side["team"]["abbreviation"], "player": s["player_name"], "stat": s["stat_label"],
            "last_game": s["value"], "season_average": r1(s["average"]), "earlier_games": s["earlier_games"],
            "minutes": s.get("minutes"), "small_sample": s["earlier_games"] < 10}


def usage_leaders(players, n=3):
    rows = [p for p in players if p.get("usage") and p["usage"]["usg_pct"] is not None
            and not p["usage"]["small_sample"] and p.get("season")]
    rows.sort(key=lambda p: -p["usage"]["usg_pct"])
    return [{"player": p["player_name"], "usg_pct": p["usage"]["usg_pct"], "usg_rank": p["usage"]["rank"],
             "points_per_game": r1(p["season"]["pts"]), "ts_pct": pct(p["season"]["ts_pct"])} for p in rows[:n]]


def ratings_of(attr):
    if not attr or not attr.get("qualified"):
        return None
    return [{"attribute": r["label"], "rating": r["rating"], "small_sample": r["small_sample"],
             "last_season_only": r["last_season_only"]} for r in attr.get("ratings", []) if r["rating"] is not None]


def badges_of(attr):
    if not attr:
        return []
    return [{"badge": b["name"], "meaning": b["meaning"], "numbers": b["detail"]} for b in attr.get("badges", [])]


def build_facts(us_id, them_id, us_lineup=None, them_lineup=None, us_overrides=None, them_overrides=None):
    """Returns (facts, error message)."""
    ctx = game_context(us_id, them_id)
    result, err = matchups(us_id, them_id, us_lineup, them_lineup, us_overrides, them_overrides)
    if err:
        return None, err
    us_abbr, them_abbr = ctx["us"]["team"]["abbreviation"], ctx["them"]["team"]["abbreviation"]
    us_roster, them_roster = roster(us_id), roster(them_id)
    us_over, _ = parse_overrides(us_overrides, "us")
    them_over, _ = parse_overrides(them_overrides, "them")

    def injuries(team_id, players, over):
        statuses = effective_statuses(team_id, over)
        names = {p["player_id"]: p["player_name"] for p in players}
        rows = []
        for pid, st in sorted(statuses.items(), key=lambda kv: names.get(kv[0], "")):
            if st in (None, "Available") and pid not in over:
                continue
            rows.append({"player": names.get(pid, str(pid)), "status": st, "set_for_this_game": pid in over})
        return rows

    matchup_rows = []
    for row in result["rows"]:
        a = row["assigned"]
        matchup_rows.append({
            "their_player": row["scorer_name"], "position": row["position"], "usg_pct": row["usg_pct"],
            "our_defender": a["defender_name"],
            "vs_his_norm_per100": a["vs_norm_per100"], "expected_per100": a["expected_per100"],
            "his_norm_per100": a["norm_per100"],
            "history_possessions": round(a["history_poss"]), "small_history": a["small_history"],
            "reason": a["reason"],
            "top_three_options": [{"defender": o["defender_name"], "vs_his_norm_per100": o["vs_norm_per100"]}
                                  for o in row["top_three"]],
        })

    # Key opposing players: their five plus anyone with USG% >= KEY_USAGE.
    them_five = {p["player_id"] for p in result["them_lineup"]}
    key_ids = [p["player_id"] for p in them_roster
               if p["player_id"] in them_five or (p.get("usage") and (p["usage"]["usg_pct"] or 0) >= KEY_USAGE
                                                  and not p["usage"]["small_sample"])]
    attrs = {d["_id"]: d for d in db.attributes.find({"_id": {"$in": key_ids}})}
    bios = {d["_id"]: d for d in db.players.find({"_id": {"$in": key_ids}},
                                                 {"height": 1, "wingspan_inches": 1, "position": 1})}
    by_id = {p["player_id"]: p for p in them_roster}
    them_status = effective_statuses(them_id, them_over)
    key_players = []
    for pid in key_ids:
        p = by_id[pid]
        season = p.get("season") or {}
        key_players.append({
            "player": p["player_name"], "position": p.get("position"),
            "in_their_lineup": pid in them_five,
            "status_for_this_game": them_status.get(pid) or "Available",
            "height": (bios.get(pid) or {}).get("height"),
            "wingspan_inches": (bios.get(pid) or {}).get("wingspan_inches"),
            "usg_pct": (p.get("usage") or {}).get("usg_pct"),
            "points_per_game": r1(season.get("pts")), "rebounds_per_game": r1(season.get("reb")),
            "assists_per_game": r1(season.get("ast")), "ts_pct": pct(season.get("ts_pct")),
            "three_point_pct": pct(season.get("fg3_pct")),
            "ratings_0_to_99": ratings_of(attrs.get(pid)),
            "badges": badges_of(attrs.get(pid)),
        })
    key_players.sort(key=lambda k: -(k["usg_pct"] or 0))

    facts = {
        "data_as_of": ctx["data_as_of"],
        "season": ctx["season"],
        "units": {
            "per100": "points per 100 partial possessions (time a defender guards a scorer); league average about 24",
            "vs_his_norm_per100": "negative means our defender holds the scorer below what he usually scores",
            "percentages": "given as percent numbers, 61.8 means 61.8%",
            "ratings": "0 to 99 percentile among qualified players; 50 is typical",
        },
        "us": team_line(ctx["us"]),
        "them": team_line(ctx["them"]),
        "next_meeting": game_line(ctx.get("next_meeting"), us_abbr),
        "last_meeting": game_line(ctx.get("last_meeting"), us_abbr),
        "last_games": {us_abbr: game_line(ctx["us"].get("last_game"), us_abbr),
                       them_abbr: game_line(ctx["them"].get("last_game"), them_abbr)},
        "who_runs_the_offense": {us_abbr: usage_leaders(us_roster), them_abbr: usage_leaders(them_roster)},
        "last_game_standouts": [s for s in (standout_line(ctx["us"]), standout_line(ctx["them"])) if s],
        "injuries": {us_abbr: injuries(us_id, us_roster, us_over), them_abbr: injuries(them_id, them_roster, them_over)},
        "lineups": {us_abbr: [p["player_name"] for p in result["us_lineup"]],
                    them_abbr: [p["player_name"] for p in result["them_lineup"]]},
        "matchups": matchup_rows,
        "key_opposing_players": key_players,
    }
    return {"facts": facts, "matchup_result": result}, None
