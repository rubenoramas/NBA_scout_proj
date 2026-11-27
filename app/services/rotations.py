"""Rotation scouting: the opponent's most-used five-man lineups with tags,
and a suggested counter five from our healthy roster for each tag.

Lineups come from the lineups5 seed file (leaguedash lineups_base, this
season). Tags and counters are simple rules on positions and ratings, all
written out in RULES so the page can show them.
"""

from app.db import db
from app.services.context import current_season, get_team
from app.services.matchups import default_lineup, effective_statuses
from app.services.names import player_names

SHOW_LINEUPS = 10
SMALL_SAMPLE_MIN = 50       # minutes together
SHOOTER_RATING = 60         # Three-point shooting rating for a "shooter"
SHOOTERS_FOR_TAG = 4
DEFENSE_AVG = 75            # average of each player's better defense rating (top fifth of top lineups)
MAX_GUARDS = 3              # a counter five has at most three guards
BIGS_FOR_TAG = 2
POOL_MIN_THIS = 100         # our counter pool: 100+ minutes this season
POOL_MIN_LAST = 500         # or 500+ last season

TAGS = ["starters", "small_ball", "three_point", "defensive", "big"]
TAG_LABELS = {"starters": "Starters", "small_ball": "Small ball", "three_point": "3pt",
              "defensive": "Defensive", "big": "Big"}
RULES = {
    "starters": "Exactly the team's most common starting five this season.",
    "small_ball": "No player listed at center (C).",
    "three_point": f"{SHOOTERS_FOR_TAG} or more players rated {SHOOTER_RATING}+ in Three-point shooting (a rating that blends volume and accuracy).",
    "defensive": f"The five average {DEFENSE_AVG}+ in defense, using each player's better of Perimeter and Interior defense.",
    "big": f"{BIGS_FOR_TAG} or more players listed at center (C).",
}
COUNTER_RULES = {
    "starters": "Our most common starting five this season, with Out and Doubtful players replaced by the healthy players with the most minutes.",
    "small_ball": "Our five best by Perimeter defense, at most one center, one to three guards.",
    "three_point": "Our five best by the average of Perimeter defense and Speed, at most one center, one to three guards.",
    "defensive": "Our five best by the average of Three-point shooting, Pull-up shooting, Playmaking and Finishing, at most one center, one to three guards.",
    "big": "Our two best centers or forwards by the average of Rebounding and Interior defense, plus our three best non-centers by Perimeter defense, at least one and at most two of them guards.",
}
COUNTER_REASONS = {
    "starters": "Meet their usual starters with ours.",
    "small_ball": "They play without a center, so our best perimeter defenders can switch and stay in front.",
    "three_point": "Four or more shooters: our quickest perimeter defenders, to contest threes and close out.",
    "defensive": "A strong defensive five: our best shooting and shot creation, to stretch it and score.",
    "big": "Two centers: our best rebounding and rim-protecting bigs on the glass, with three perimeter defenders.",
}


# ---- Data -------------------------------------------------------------------

def ratings_for(ids):
    """{pid: {rating key: 0-99 or None}} for qualified players."""
    out = {}
    for d in db.attributes.find({"_id": {"$in": list(ids)}}, {"ratings": 1, "qualified": 1}):
        if d.get("qualified"):
            out[d["_id"]] = {r["key"]: r.get("rating") for r in d.get("ratings", [])}
    return out


def positions_for(ids):
    return {d["_id"]: d.get("position") for d in db.players.find({"_id": {"$in": list(ids)}}, {"position": 1})}


def most_common_starters(team_id, season):
    """The exact five that started most often (no injury substitutions)."""
    by_game = {}
    for d in db.game_logs.find({"team_id": team_id, "season": season, "starter": True}, {"game_id": 1, "player_id": 1}):
        by_game.setdefault(d["game_id"], set()).add(d["player_id"])
    counts = {}
    for ids in by_game.values():
        if len(ids) == 5:
            key = frozenset(ids)
            counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get) if counts else frozenset()


# ---- Tags -----------------------------------------------------------------------

def tag_lineup(ids, positions, ratings, starters):
    """Tags for one five, each with the numbers behind it."""
    tags = []
    centers = [p for p in ids if positions.get(p) == "C"]
    if starters and set(ids) == set(starters):
        tags.append({"key": "starters", "why": "Their most common starting five."})
    if not centers:
        tags.append({"key": "small_ball", "why": "No center."})
    shooters = [p for p in ids if (ratings.get(p) or {}).get("three_point") is not None
                and ratings[p]["three_point"] >= SHOOTER_RATING]
    if len(shooters) >= SHOOTERS_FOR_TAG:
        tags.append({"key": "three_point", "why": f"{len(shooters)} players rated {SHOOTER_RATING}+ in Three-point shooting."})
    defense = [max(v for v in (ratings[p].get("perimeter_defense"), ratings[p].get("interior_defense")) if v is not None)
               for p in ids if p in ratings and (ratings[p].get("perimeter_defense") is not None
                                                 or ratings[p].get("interior_defense") is not None)]
    # Needs ratings for at least four of the five to call it.
    if len(defense) >= 4 and sum(defense) / len(defense) >= DEFENSE_AVG:
        tags.append({"key": "defensive", "why": f"Average defense rating {sum(defense) / len(defense):.0f}."})
    if len(centers) >= BIGS_FOR_TAG:
        tags.append({"key": "big", "why": f"{len(centers)} centers."})
    for t in tags:
        t["label"] = TAG_LABELS[t["key"]]
    return tags


# ---- Counters ---------------------------------------------------------------------

def score_of(ratings, pid, keys):
    vals = [(ratings.get(pid) or {}).get(k) for k in keys]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if len(vals) == len(keys) else None


def pick_five(pool, positions, score, max_centers=1, min_guards=1, minutes=None, max_guards=MAX_GUARDS):
    """Highest scores first, at most max_centers centers and max_guards
    guards, at least min_guards guards. Players without the ratings come
    last, by minutes."""
    minutes = minutes or {}
    order = sorted(pool, key=lambda p: (score(p) is None, -(score(p) or 0), -minutes.get(p, 0)))
    chosen = []
    for p in order:
        if len(chosen) == 5:
            break
        if positions.get(p) == "C" and max_centers is not None and sum(positions.get(x) == "C" for x in chosen) >= max_centers:
            continue
        if positions.get(p) == "G" and max_guards is not None and sum(positions.get(x) == "G" for x in chosen) >= max_guards:
            continue
        chosen.append(p)
    guards = [p for p in chosen if positions.get(p) == "G"]
    if len(guards) < min_guards:
        spare = [p for p in order if p not in chosen and positions.get(p) == "G"]
        while len([p for p in chosen if positions.get(p) == "G"]) < min_guards and spare:
            # Swap the lowest-ranked non-guard for the best remaining guard.
            worst = max((p for p in chosen if positions.get(p) != "G"), key=order.index)
            chosen[chosen.index(worst)] = spare.pop(0)
    return chosen


def counter_pool(us_id, statuses):
    """Our healthy players with real minutes: not Out, 100+ minutes this
    season or 500+ last season. Returns (pool, minutes this season)."""
    meta = db.meta.find_one({"_id": "seed"}) or {}
    season, last = meta.get("season") or current_season(), meta.get("last_season")
    ids = [d["_id"] for d in db.players.find({"team_id": us_id}, {"_id": 1})]
    mins = {(d["player_id"], d["season"]): d.get("min") or 0
            for d in db.player_stats.find({"player_id": {"$in": ids}}, {"player_id": 1, "season": 1, "min": 1})}
    pool = [p for p in ids if statuses.get(p) != "Out"
            and (mins.get((p, season), 0) >= POOL_MIN_THIS or mins.get((p, last), 0) >= POOL_MIN_LAST)]
    return pool, {p: mins.get((p, season), 0) for p in ids}


def build_counters(us_id, statuses, overrides):
    pool, minutes = counter_pool(us_id, statuses)
    positions, ratings = positions_for(pool), ratings_for(pool)
    season = current_season()
    out = {}

    def by(keys):
        return lambda p: score_of(ratings, p, keys)

    skip = {p for p, st in statuses.items() if st in ("Out", "Doubtful")}
    out["starters"] = default_lineup(us_id, season, skip)
    out["small_ball"] = pick_five(pool, positions, by(["perimeter_defense"]), minutes=minutes)
    out["three_point"] = pick_five(pool, positions, by(["perimeter_defense", "speed"]), minutes=minutes)
    out["defensive"] = pick_five(pool, positions, by(["three_point", "pull_up", "playmaking", "finishing"]), minutes=minutes)
    bigs = pick_five([p for p in pool if positions.get(p) in ("C", "F")], positions, by(["rebounding", "interior_defense"]),
                     max_centers=None, min_guards=0, minutes=minutes)[:2]
    rest = pick_five([p for p in pool if p not in bigs], positions, by(["perimeter_defense"]), max_centers=0,
                     minutes=minutes, max_guards=2)[:3]
    out["big"] = bigs + rest
    keys_used = {"starters": [], "small_ball": ["perimeter_defense"], "three_point": ["perimeter_defense", "speed"],
                 "defensive": ["three_point", "pull_up", "playmaking", "finishing"],
                 "big": ["rebounding", "interior_defense", "perimeter_defense"]}
    names = player_names({p for ids in out.values() for p in ids})
    all_pos = positions_for({p for ids in out.values() for p in ids})
    all_rat = ratings_for({p for ids in out.values() for p in ids})
    return {tag: {
        "tag": tag, "label": TAG_LABELS[tag], "rule": COUNTER_RULES[tag], "reason": COUNTER_REASONS[tag],
        "player_ids": ids,
        "players": [{"player_id": p, "player_name": names.get(p, f"Player {p}"), "position": all_pos.get(p),
                     "status": statuses.get(p) or "Available",
                     "ratings": {k: (all_rat.get(p) or {}).get(k) for k in keys_used[tag]}} for p in ids],
        "complete": len(ids) == 5,
    } for tag, ids in out.items()}


# ---- Page -------------------------------------------------------------------------

def rotations(us_id, them_id, us_overrides=None, them_overrides=None):
    season = current_season()
    them_status = effective_statuses(them_id, them_overrides or {})
    us_status = effective_statuses(us_id, us_overrides or {})
    docs = list(db.lineups5.find({"team_id": them_id}, {"_id": 0}).sort("min", -1).limit(SHOW_LINEUPS))
    all_ids = {int(x) for d in docs for x in d["player_ids"].split(",")}
    positions, ratings = positions_for(all_ids), ratings_for(all_ids)
    names = player_names(all_ids)
    starters = most_common_starters(them_id, season)
    lineups = []
    for d in docs:
        ids = [int(x) for x in d["player_ids"].split(",")]
        out = [p for p in ids if them_status.get(p) == "Out"]
        lineups.append({
            "player_ids": ids,
            "players": [{"player_id": p, "player_name": names.get(p, f"Player {p}"), "position": positions.get(p),
                         "status": them_status.get(p) or "Available"} for p in ids],
            "minutes": round(d["min"], 1), "games": d["gp"], "plus_minus": d["plus_minus"],
            "plus_minus_per48": round(48 * d["plus_minus"] / d["min"], 1) if d["min"] else None,
            "small_sample": d["min"] < SMALL_SAMPLE_MIN,
            "tags": tag_lineup(ids, positions, ratings, starters),
            "includes_out": out,
        })
    tag_counts = {t: sum(any(x["key"] == t for x in ln["tags"]) for ln in lineups) for t in TAGS}
    return {
        "team": get_team(them_id), "season": season,
        "lineups": lineups, "tag_counts": tag_counts,
        "counters": build_counters(us_id, us_status, us_overrides or {}),
        "status_source": "lineup" if us_overrides else "official",
        "rules": {"tags": RULES, "counters": COUNTER_RULES, "small_sample_min": SMALL_SAMPLE_MIN,
                  "shown": SHOW_LINEUPS, "tag_labels": TAG_LABELS, "order": TAGS},
    }
