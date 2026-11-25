"""Rosters, player cards and shot profiles."""

from app.db import db
from app.services.context import current_season

ZONES = ["restricted_area", "paint", "midrange", "corner_three", "above_break_three"]
ZONE_LABELS = {
    "restricted_area": "Restricted area",
    "paint": "Paint (non-RA)",
    "midrange": "Midrange",
    "corner_three": "Corner three",
    "above_break_three": "Above-the-break three",
}
# Levels for "favorite shots": at the rim is the restricted area, midrange
# is the rest of the paint plus the midrange, and three is both threes.
LEVEL_OF_ZONE = {
    "restricted_area": "rim",
    "paint": "midrange",
    "midrange": "midrange",
    "corner_three": "three",
    "above_break_three": "three",
}
LEVELS = ["rim", "midrange", "three"]
# A zone with fewer attempts than this is marked as a small sample.
SMALL_SAMPLE_FGA = 20


# USG% is ranked among players with at least this many minutes this season.
USG_RANK_MINUTES = 200
# Below this many minutes a USG% is shown but marked as a small sample, and
# it is left out of default sorting and the "who runs the offense" panel.
USG_SMALL_MINUTES = 100


def usage_table(season):
    """{pid: {"usg_pct", "min", "rank", "ranked_of"}} for one season.
    usg_pct is a percentage (31.2 means 31.2%), the same scale as the box
    score. It is the share of his team's plays (FGA + 0.44 x FTA + TOV) he
    uses while on the floor."""
    rows = [d for d in db.player_stats.find({"season": season}, {"player_id": 1, "usg_pct": 1, "min": 1})
            if d.get("usg_pct") is not None]
    ranked = sorted([d for d in rows if (d.get("min") or 0) >= USG_RANK_MINUTES], key=lambda d: -d["usg_pct"])
    rank = {d["player_id"]: i + 1 for i, d in enumerate(ranked)}
    return {d["player_id"]: {"usg_pct": round(d["usg_pct"] * 100, 1), "min": d.get("min") or 0,
                             "rank": rank.get(d["player_id"]), "ranked_of": len(ranked)} for d in rows}


def usage_for(pid, this_usage, last_usage):
    u = this_usage.get(pid)
    last = last_usage.get(pid)
    return {
        "usg_pct": u["usg_pct"] if u else None,
        "rank": u["rank"] if u else None,
        "ranked_of": u["ranked_of"] if u else len([1 for v in this_usage.values() if v["rank"]]),
        "minutes": round(u["min"]) if u else 0,
        "small_sample": (u["min"] if u else 0) < USG_SMALL_MINUTES,
        "last_season_usg_pct": last["usg_pct"] if last else None,
    }


def safe_div(a, b):
    return a / b if b else None


def per_game(doc):
    """Season line per game from the season totals, or None with no games."""
    gp = doc.get("gp") or 0
    if not gp:
        return None
    t = {k: doc.get(f"{k}_total") or 0 for k in
         ["min", "pts", "reb", "ast", "stl", "blk", "tov", "oreb", "dreb", "pf",
          "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"]}
    line = {k: round(v / gp, 1) for k, v in t.items()}
    line.update({
        "gp": gp,
        "fg_pct": safe_div(t["fgm"], t["fga"]),
        "fg3_pct": safe_div(t["fg3m"], t["fg3a"]),
        "ft_pct": safe_div(t["ftm"], t["fta"]),
        # TS% = PTS / (2 x (FGA + 0.44 x FTA))
        "ts_pct": safe_div(t["pts"], 2 * (t["fga"] + 0.44 * t["fta"])),
    })
    return line


def injury_for(player_id):
    doc = db.injuries.find_one({"_id": player_id}, {"_id": 0})
    if not doc:
        return None
    return {k: doc.get(k) for k in ("status", "reason", "game_date", "report_time")}


def badge_summary(attr):
    """Short badge list for tables: key, name, short name and his numbers."""
    if not attr:
        return []
    return [{k: b.get(k) for k in ("key", "name", "short", "meaning", "rule", "detail")} for b in attr.get("badges", [])]


def roster(team_id):
    from app.services.onoff import by_player, compact
    this_season = current_season()
    meta = db.meta.find_one({"_id": "seed"}) or {}
    onoff_this, onoff_last = by_player(this_season), by_player(meta.get("last_season"))
    this_usage = usage_table(this_season)
    last_usage = usage_table(meta.get("last_season"))
    injuries = {d["_id"]: d for d in db.injuries.find({"team_id": team_id})}
    attrs = {d["_id"]: d for d in db.attributes.find({}, {"badges": 1})}
    rows = []
    for doc in db.players.find({"team_id": team_id}):
        inj = injuries.get(doc["_id"])
        rows.append({
            "player_id": doc["player_id"],
            "player_name": doc.get("player_name"),
            "position": doc.get("position"),
            "has_stats": bool(doc.get("has_stats")) and bool(doc.get("gp")),
            "season": per_game(doc),
            "injury": {"status": inj.get("status"), "reason": inj.get("reason")} if inj else None,
            "badges": badge_summary(attrs.get(doc["_id"])),
            "usage": usage_for(doc["_id"], this_usage, last_usage),
            "onoff": {"this_season": compact(onoff_this.get(doc["_id"])),
                      "last_season": compact(onoff_last.get(doc["_id"]))},
        })
    # Most minutes first; players with no stats at the bottom.
    rows.sort(key=lambda r: -(r["season"]["min"] if r["season"] else -1))
    return rows


def last_games(player_id, season, n=5):
    docs = db.game_logs.find({"player_id": player_id, "season": season}).sort("game_date", -1).limit(n)
    out = []
    for d in docs:
        # The matchup reads "BOS vs. ORL" at home and "BOS @ ORL" on the road.
        matchup = d.get("matchup") or ""
        opponent = matchup.split(" ")[-1] if matchup else None
        out.append({
            "game_id": d["game_id"], "date": d["game_date"], "home": d.get("home"),
            "opponent": opponent, "result": d.get("wl"), "starter": d.get("starter"),
            "min": d.get("min"), "pts": d.get("pts"), "reb": d.get("reb"), "ast": d.get("ast"),
            "fgm": d.get("fgm"), "fga": d.get("fga"), "fg3m": d.get("fg3m"), "fg3a": d.get("fg3a"),
            "plus_minus": d.get("plus_minus"),
        })
    return out


def zone_counts(match):
    """FGA and FGM per zone for shots matching a MongoDB filter."""
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$zone", "fga": {"$sum": 1}, "fgm": {"$sum": {"$cond": ["$made", 1, 0]}}}},
    ]
    return {d["_id"]: d for d in db.shots.aggregate(pipeline)}


def zone_table(player_id):
    """This season by zone, with league FG% and last season's totals."""
    mine = zone_counts({"player_id": player_id})
    league = zone_counts({})
    last = {d["zone"]: d for d in db.shot_zones_last.find({"player_id": player_id})}
    total_fga = sum(z["fga"] for z in mine.values())
    rows = []
    for zone in ZONES:
        m = mine.get(zone, {"fga": 0, "fgm": 0})
        lg = league.get(zone, {"fga": 0, "fgm": 0})
        ls = last.get(zone)
        fg = safe_div(m["fgm"], m["fga"])
        league_fg = safe_div(lg["fgm"], lg["fga"])
        rows.append({
            "zone": zone,
            "label": ZONE_LABELS[zone],
            "fga": m["fga"],
            "fgm": m["fgm"],
            "fg_pct": fg,
            "share": safe_div(m["fga"], total_fga),
            "league_fg_pct": league_fg,
            # Gap to league average in percentage points (0.05 = 5 points).
            "vs_league": (fg - league_fg) if fg is not None and league_fg is not None else None,
            "small_sample": m["fga"] < SMALL_SAMPLE_FGA,
            "last_season": {"fga": ls["fga"], "fgm": ls["fgm"], "fg_pct": safe_div(ls["fgm"], ls["fga"])} if ls else None,
        })
    return rows, total_fga


def top_shot_types(player_id, per_level=3):
    """His three most common shot types at each level, this season."""
    pipeline = [
        {"$match": {"player_id": player_id}},
        {"$group": {"_id": {"zone": "$zone", "type": "$shot_type"},
                    "fga": {"$sum": 1}, "fgm": {"$sum": {"$cond": ["$made", 1, 0]}}}},
    ]
    by_level = {level: {} for level in LEVELS}
    for d in db.shots.aggregate(pipeline):
        level = LEVEL_OF_ZONE.get(d["_id"]["zone"])
        if not level:
            continue
        entry = by_level[level].setdefault(d["_id"]["type"], {"fga": 0, "fgm": 0})
        entry["fga"] += d["fga"]
        entry["fgm"] += d["fgm"]
    out = {}
    for level, types in by_level.items():
        level_fga = sum(t["fga"] for t in types.values())
        ranked = sorted(types.items(), key=lambda kv: (-kv[1]["fga"], kv[0]))[:per_level]
        out[level] = {
            "fga": level_fga,
            "types": [{"shot_type": name, "fga": t["fga"], "fgm": t["fgm"],
                       "fg_pct": safe_div(t["fgm"], t["fga"]), "share": safe_div(t["fga"], level_fga)}
                      for name, t in ranked],
        }
    return out


def player_card(player_id):
    doc = db.players.find_one({"_id": player_id})
    if not doc:
        return None
    season = current_season()
    team = db.teams.find_one({"_id": doc.get("team_id")}, {"_id": 0})
    zones, total_fga = zone_table(player_id)
    bio_keys = ["player_id", "player_name", "team_id", "team_abbr", "position", "position_source", "age",
                "height", "height_inches", "weight_lbs", "wingspan_inches", "standing_reach_inches",
                "college", "country", "draft_year", "draft_round", "draft_number", "headshot_url"]
    attr = db.attributes.find_one({"_id": player_id}, {"_id": 0}) or None
    meta = db.meta.find_one({"_id": "seed"}) or {}
    usage = usage_for(player_id, usage_table(season), usage_table(meta.get("last_season")))
    from app.services.onoff import player_onoff
    return {
        "usage": usage,
        "onoff": player_onoff(player_id),
        "attributes": attr,
        "player": {k: doc.get(k) for k in bio_keys},
        "team": team,
        "has_stats": bool(doc.get("has_stats")) and bool(doc.get("gp")),
        "season_label": season,
        "season": per_game(doc),
        "injury": injury_for(player_id),
        "last_games": last_games(player_id, season),
        "shots": {
            "total_fga": total_fga,
            "zones": zones,
            "top_types": top_shot_types(player_id),
            "small_sample_fga": SMALL_SAMPLE_FGA,
        },
    }


def shot_types_for(player_id):
    return sorted(db.shots.distinct("shot_type", {"player_id": player_id}))


def player_shots(player_id, shot_type=None, zone=None):
    query = {"player_id": player_id}
    if shot_type:
        query["shot_type"] = shot_type
    if zone:
        query["zone"] = zone
    # Sides are left out until pulls/check_sides.R confirms which way is left.
    fields = {"_id": 0, "x": 1, "y": 1, "made": 1, "zone": 1, "shot_type": 1, "value": 1,
              "distance": 1, "game_id": 1, "game_date": 1, "period": 1}
    return list(db.shots.find(query, fields))
