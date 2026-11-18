"""Matchups: default lineups, the five-on-five assignment and top three
defenders for each opposing player. The model itself is in app/model/matchups.py."""

from collections import Counter

from app.db import db
from app.model.matchups import (
    GUARD_CENTER_MIN_POSS, SMALL_HISTORY, best_assignment, fit, pair_estimate, position_blocked, reason_line,
)
from app.services.context import current_season

_cache = {"key": None, "model": None}

NOISE_NOTE = ("Public matchup data is noisy: switches and help defense split every scorer across several "
              "defenders, so treat these as suggestions, not answers.")
UNIT_NOTE = ("Expected points are per 100 partial possessions, the time a defender spends guarding a scorer. "
             "The league average is about 24, because a scorer finishes only a small share of the possessions "
             "he is on the floor. \"His norm\" is what the scorer usually scores against everyone.")
TOP_MIN_THIS = 100
TOP_MIN_LAST = 500


def load_pairs():
    return list(db.matchup_pairs.find({}, {"_id": 0, "season": 1, "off_id": 1, "def_id": 1, "poss": 1, "pts": 1}))


def bios():
    fields = {"height_inches": 1, "weight_lbs": 1, "wingspan_inches": 1, "position": 1, "player_name": 1,
              "team_id": 1, "team_abbr": 1}
    return {d["_id"]: d for d in db.players.find({}, fields)}


def minutes_and_usage(season, last_season):
    minutes, usage = {}, {}
    last_usage = {}
    for d in db.player_stats.find({}, {"player_id": 1, "season": 1, "min": 1, "usg_pct": 1}):
        if d["season"] == season:
            minutes[d["player_id"]] = d.get("min") or 0
            if (d.get("min") or 0) >= 100 and d.get("usg_pct") is not None:
                usage[d["player_id"]] = d["usg_pct"]
        elif d["season"] == last_season and d.get("usg_pct") is not None:
            last_usage[d["player_id"]] = (d["usg_pct"], d.get("min") or 0)
    for pid, (u, _m) in last_usage.items():
        usage.setdefault(pid, u)
    last_minutes = {pid: m for pid, (_u, m) in last_usage.items()}
    return minutes, usage, last_minutes


def get_model():
    """Fit once per seed version and keep it in memory."""
    hashes = db.meta.find_one({"_id": "seed_hashes"}) or {}
    key = str(sorted((hashes.get("files") or {}).items()))
    if _cache["key"] != key or _cache["model"] is None:
        meta = db.meta.find_one({"_id": "seed"}) or {}
        season = meta.get("season") or current_season()
        minutes, usage, last_minutes = minutes_and_usage(season, meta.get("last_season"))
        model = fit(load_pairs(), minutes, season, bios())
        model["usage"] = usage
        model["last_minutes"] = last_minutes
        _cache.update(key=key, model=model)
    return _cache["model"]


def out_players(team_id):
    return {d["_id"] for d in db.injuries.find({"team_id": team_id, "status": "Out"})}


def default_lineup(team_id, season, excluded):
    """Most common starting five this season, with Out players replaced by
    the healthy players with the most minutes."""
    fives = Counter()
    by_game = {}
    for d in db.game_logs.find({"team_id": team_id, "season": season, "starter": True}, {"game_id": 1, "player_id": 1}):
        by_game.setdefault(d["game_id"], []).append(d["player_id"])
    for ids in by_game.values():
        if len(ids) == 5:
            fives[frozenset(ids)] += 1
    lineup = [pid for pid in (sorted(fives.most_common(1)[0][0]) if fives else []) if pid not in excluded]
    if len(lineup) < 5:
        roster = [d for d in db.players.find({"team_id": team_id}, {"_id": 1, "min_total": 1})
                  if d["_id"] not in excluded and d["_id"] not in lineup]
        roster.sort(key=lambda d: -(d.get("min_total") or 0))
        lineup += [d["_id"] for d in roster[: 5 - len(lineup)]]
    return lineup


def validate_lineup(team_id, ids, excluded, label):
    if not isinstance(ids, list) or len(ids) != 5:
        return None, f"The {label} lineup needs exactly 5 players."
    try:
        ids = [int(x) for x in ids]
    except (TypeError, ValueError):
        return None, f"The {label} lineup has a player id that is not a number."
    if len(set(ids)) != 5:
        return None, f"The {label} lineup lists the same player twice."
    on_team = {d["_id"] for d in db.players.find({"team_id": team_id, "_id": {"$in": ids}}, {"_id": 1})}
    missing = [i for i in ids if i not in on_team]
    if missing:
        return None, f"Player {missing[0]} is not on the {label} team."
    hurt = [i for i in ids if i in excluded]
    if hurt:
        return None, f"Player {hurt[0]} is Out and cannot be in the {label} lineup."
    return ids, None


def matchups(us_id, them_id, us_lineup=None, them_lineup=None):
    """Returns (result, error message)."""
    model = get_model()
    season = model["this_season"]
    info = model["bios"]
    out_us, out_them = out_players(us_id), out_players(them_id)

    if us_lineup is None:
        ours, us_default = default_lineup(us_id, season, out_us), True
    else:
        ours, err = validate_lineup(us_id, us_lineup, out_us, "\"us\"")
        if err:
            return None, err
        us_default = False
    if them_lineup is None:
        theirs, them_default = default_lineup(them_id, season, out_them), True
    else:
        theirs, err = validate_lineup(them_id, them_lineup, out_them, "\"them\"")
        if err:
            return None, err
        them_default = False
    if len(ours) < 5 or len(theirs) < 5:
        return None, "One team does not have five healthy players to build a lineup."

    positions = {pid: (info.get(pid) or {}).get("position") for pid in set(ours) | set(theirs)}
    usage = {pid: model["usage"].get(pid, 0.2) for pid in theirs}
    cache = {}

    def est(s, d):
        if (s, d) not in cache:
            cache[(s, d)] = pair_estimate(model, s, d)
        return cache[(s, d)]

    def blocked(s, d):
        return position_blocked(model, s, d, positions)

    assignment, _total, guard_applied = best_assignment(
        theirs, ours, lambda s, d: est(s, d)["expected"], usage, blocked)

    # Top three from our whole healthy roster with enough minutes.
    pool = []
    for d in db.players.find({"team_id": us_id}, {"_id": 1, "position": 1}):
        pid = d["_id"]
        if pid in out_us:
            continue
        if model["minutes_this"].get(pid, 0) >= TOP_MIN_THIS or model["last_minutes"].get(pid, 0) >= TOP_MIN_LAST:
            pool.append(pid)
            positions[pid] = d.get("position")

    def name(pid):
        return (info.get(pid) or {}).get("player_name") or str(pid)

    def describe(s, d):
        e = est(s, d)
        return {
            "defender_id": d, "defender_name": name(d), "position": positions.get(d),
            "expected_per100": round(e["expected"] * 100, 1),
            "norm_per100": round(e["baseline"] * 100, 1),
            "vs_norm_per100": round(e["vs_norm"] * 100, 1),
            "defender_effect_per100": round(e["defender_effect"] * 100, 1),
            "size_per100": round(e["size"] * 100, 2),
            "history_poss": round(e["history_poss"], 1),
            "history_per100": round(e["history_rate"] * 100, 1) if e["history_rate"] is not None else None,
            "history_shift_per100": round(e["history_shift"] * 100, 1),
            "small_history": e["history_poss"] < SMALL_HISTORY,
            "reason": reason_line(e, name(s).split(" ")[-1], name(d)),
        }

    rows = []
    for s in sorted(theirs, key=lambda p: -usage.get(p, 0)):
        options = sorted((d for d in pool if not blocked(s, d)), key=lambda d: est(s, d)["expected"])[:3]
        rows.append({
            "scorer_id": s, "scorer_name": name(s), "position": positions.get(s),
            "usg_pct": round(usage.get(s, 0) * 100, 1),
            "assigned": describe(s, assignment[s]),
            "top_three": [describe(s, d) for d in options],
        })

    return {
        "us_lineup": [{"player_id": p, "player_name": name(p), "position": positions.get(p)} for p in ours],
        "them_lineup": [{"player_id": p, "player_name": name(p), "position": positions.get(p)} for p in theirs],
        "us_default": us_default, "them_default": them_default,
        "excluded_out": {"us": sorted(out_us), "them": sorted(out_them)},
        "rows": rows,
        "position_guard": {"applied": guard_applied, "min_history": GUARD_CENTER_MIN_POSS},
        "size_fit": {"beta_per100": {"height_per_inch": round(model["beta"][0] * 100, 3),
                                     "weight_per_10lb": round(model["beta"][1] * 100, 3),
                                     "wingspan_per_inch": round(model["beta"][2] * 100, 3)},
                     "share_of_leftover_explained": round(model["size_r2"], 4)},
        "league_per100": round(model["league_all"] * 100, 1),
        "notes": {"noise": NOISE_NOTE, "unit": UNIT_NOTE},
    }, None
