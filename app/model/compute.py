"""Gather the seed data from MongoDB, compute ratings and badges, and write
one document per player into the `attributes` collection.

Run by the loader whenever one of the input collections changed. By hand:
    docker compose run --rm loader python -m app.model.compute
"""

from datetime import datetime, timezone

from app.db import db
from app.model.badges import compute_badges
from app.model.ratings import compute_ratings, league_rates

# Collections the ratings and badges read. The loader recomputes when any
# of their seed files changed.
INPUTS = ["players", "player_stats", "play_types", "hustle", "steals", "shot_extras",
          "matchup_defense", "combine_drills", "shots", "shot_zones_last", "meta"]


def seasons():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return meta.get("season"), meta.get("last_season")


def by_player_season(collection):
    out = {}
    for d in db[collection].find({}, {"_id": 0}):
        out[(d["player_id"], d["season"])] = d
    return out


def zone_totals(this_season):
    """{(pid, season): {zone: {"fga", "fgm"}}} for both seasons."""
    zones = {}
    pipeline = [{"$group": {"_id": {"p": "$player_id", "z": "$zone"}, "fga": {"$sum": 1},
                            "fgm": {"$sum": {"$cond": ["$made", 1, 0]}}}}]
    for d in db.shots.aggregate(pipeline):
        zones.setdefault((d["_id"]["p"], this_season), {})[d["_id"]["z"]] = {"fga": d["fga"], "fgm": d["fgm"]}
    for d in db.shot_zones_last.find():
        zones.setdefault((d["player_id"], d["season"]), {})[d["zone"]] = {"fga": d["fga"], "fgm": d["fgm"]}
    return zones


def gather():
    this_season, last_season = seasons()
    tables = {name: by_player_season(name) for name in
              ("player_stats", "play_types", "hustle", "steals", "shot_extras", "matchup_defense")}
    zones = zone_totals(this_season)
    vertical = {d["player_id"]: d.get("max_vertical_in") for d in db.combine_drills.find()}

    rows = {}
    for (pid, season), stats in tables["player_stats"].items():
        row = dict(stats)
        for name in ("play_types", "hustle", "steals", "shot_extras", "matchup_defense"):
            extra = tables[name].get((pid, season))
            if extra:
                # shot_extras has its own fg3a/fg3m from the shots file; the
                # player_stats ones (box score) are kept for the rating.
                row.update({k: v for k, v in extra.items() if k not in row or name != "shot_extras"})
        row["zones"] = zones.get((pid, season), {})
        rows[(pid, season)] = row

    league = {s: league_rates([r for (p, ss), r in rows.items() if ss == s]) for s in (this_season, last_season)}
    return this_season, last_season, rows, league, vertical, tables["shot_extras"]


def build_inputs(this_season, last_season, rows, league, vertical, extras, player_ids):
    rating_in = {}
    badge_in = {}
    # League 3P% on shots, pooled over both seasons, for Deep Range.
    fg3m = sum(e.get("fg3m") or 0 for e in extras.values())
    fg3a = sum(e.get("fg3a") or 0 for e in extras.values())
    league_fg3 = fg3m / fg3a if fg3a else None
    for pid in player_ids:
        this = rows.get((pid, this_season))
        last = rows.get((pid, last_season))
        if not this and not last:
            continue
        rating_in[pid] = {"this": this, "last": last,
                          "league_this": league[this_season], "league_last": league[last_season]}
        pooled = {"min": 0, "league_fg3": league_fg3, "max_vertical_in": vertical.get(pid)}
        for r, ex in ((this, extras.get((pid, this_season))), (last, extras.get((pid, last_season)))):
            if r:
                pooled["min"] += r.get("min") or 0
                for k in ("lost_ball_steals", "other_steals", "deflections"):
                    pooled[k] = pooled.get(k, 0) + (r.get(k) or 0)
            if ex:
                for k in ("fg3a", "deep3_fga", "deep3_fgm", "dunks_driving", "dunks_cutting",
                          "dunks_running", "dunks_putback", "dunks_alley_oop", "after_make_fga",
                          "after_make_fgm", "after_miss_fga", "after_miss_fgm"):
                    pooled[k] = pooled.get(k, 0) + (ex.get(k) or 0)
        badge_in[pid] = pooled
    return rating_in, badge_in


def compute(shooting_weights=(0.65, 0.35)):
    """Return ({pid: attributes document}, badge summary)."""
    this_season, last_season, rows, league, vertical, extras = gather()
    # Only current players are rated, so percentiles compare today's league.
    player_ids = {d["_id"] for d in db.players.find({}, {"_id": 1})}
    rating_in, badge_in = build_inputs(this_season, last_season, rows, league, vertical, extras, player_ids)
    ratings = compute_ratings(rating_in, shooting_weights)
    badges, summary = compute_badges(badge_in)
    docs = {}
    for pid, r in ratings.items():
        docs[pid] = {
            "_id": pid, "player_id": pid, "season": this_season,
            "qualified": r["qualified"], "blend_weight": r["w"],
            "min_this": r["min_this"], "min_last": r["min_last"],
            "ratings": r["ratings"],
            "badges": badges.get(pid, {}).get("badges", []),
            "streaky_test": badges.get(pid, {}).get("streaky_test"),
        }
    return docs, summary


def write(docs, summary):
    temp = db["attributes__loading"]
    temp.drop()
    if docs:
        temp.insert_many(list(docs.values()))
        temp.rename("attributes", dropTarget=True)
    db.meta.replace_one({"_id": "attributes"}, {"_id": "attributes", **summary,
                        "computed_at": datetime.now(timezone.utc).isoformat()}, upsert=True)


def main():
    docs, summary = compute()
    write(docs, summary)
    print(f"[model] Ratings and badges for {len(docs)} players. "
          f"Badge-eligible {summary['eligible']}, streaky tested {summary['streaky_tested']}.", flush=True)


if __name__ == "__main__":
    main()
