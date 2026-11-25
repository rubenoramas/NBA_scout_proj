"""The "How to guard him" text on the player one-pager.

onepager_facts() turns the page data into the facts object: only numbers
that are printed on the page, each rounded once, here, so the text and the
number check see the same values. get_note() returns the cached text or
writes it with the shared report writer, then caches it in MongoDB.

Cache key: player, our team, the data date and the prompt version. The same
page opened again with the same data reads MongoDB and never calls the API.
New data (a refresh) or a new prompt version writes fresh text.
"""

from datetime import datetime, timezone

from app.db import db
from app.report import config
from app.report.check import check_text, facts_vocabulary
from app.report.writer import write

SCHEMA = {
    "type": "object",
    "properties": {"how_to_guard": {"type": "string"}},
    "required": ["how_to_guard"],
    "additionalProperties": False,
}
LEVEL_NAMES = {"rim": "at_the_rim", "midrange": "midrange", "three": "three"}


def r1(v):
    return None if v is None else round(float(v), 1)


def r2(v):
    return None if v is None else round(float(v), 2)


def pct(v):
    """0.618 -> 61.8"""
    return None if v is None else round(float(v) * 100, 1)


def onepager_facts(page):
    """The facts object for one page. Everything in it is on the page."""
    p, s, u = page["player"], page["season"] or {}, page["usage"] or {}
    attrs, shots, pt, fd = page["attributes"], page["shots"], page["play_types"], page["feeders"]
    facts = {
        "data_as_of": page["data_as_of"],
        "season": page["season_label"],
        "units": {
            "per100": "points per 100 partial possessions (time a defender guards a scorer); league average about 24",
            "vs_his_norm_per100": "negative means our defender holds him below what he usually scores",
            "percentages": "given as percent numbers, 41.2 means 41.2%",
            "ratings": "0 to 99 percentile among qualified players; 50 is typical",
            "points_per_possession": "points he scores per possession that ends in that play type",
        },
        "player": {
            "name": p["player_name"], "team": (page["team"] or {}).get("abbreviation") or p.get("team_abbr"),
            "position": p.get("position"), "height": p.get("height"), "weight_lbs": p.get("weight_lbs"),
            "wingspan_inches": p.get("wingspan_inches"),
            "injury_status": (page["injury"] or {}).get("status") or "Available",
        },
        "guarded_by_team": page["us"]["abbreviation"],
        "defender_statuses_from": page["defenders"]["status_source_label"],
        "season_line": {
            "games": s.get("gp"), "minutes": s.get("min"), "points": s.get("pts"), "rebounds": s.get("reb"),
            "assists": s.get("ast"), "turnovers": s.get("tov"),
            "fg_pct": pct(s.get("fg_pct")), "three_point_pct": pct(s.get("fg3_pct")),
            "ft_pct": pct(s.get("ft_pct")), "ts_pct": pct(s.get("ts_pct")),
            "usg_pct": u.get("usg_pct"), "usg_rank": u.get("rank"), "usg_ranked_of": u.get("ranked_of"),
            "usg_small_sample": u.get("small_sample"),
        } if page["season"] else None,
        "ratings_0_to_99": [{"attribute": r["label"], "rating": r["rating"], "small_sample": r["small_sample"],
                             "last_season_only": r["last_season_only"]}
                            for r in attrs["ratings"] if r["rating"] is not None] if attrs["qualified"] else None,
        "badges": [{"badge": b["name"], "meaning": b["meaning"], "numbers": b["detail"]} for b in attrs["badges"]],
        "best_defenders": [{
            "defender": o["defender_name"], "vs_his_norm_per100": o["vs_norm_per100"],
            "expected_per100": o["expected_per100"], "his_norm_per100": o["norm_per100"],
            "history_possessions": round(o["history_poss"]), "small_history": o["small_history"],
        } for o in page["defenders"]["options"]],
        "favorite_shots": {
            LEVEL_NAMES[level]: {
                "attempts": block["fga"],
                "types": [{"shot_type": t["shot_type"], "made": t["fgm"], "attempts": t["fga"],
                           "fg_pct": pct(t["fg_pct"]), "share_of_level_pct": pct(t["share"])} for t in block["types"]],
            } for level, block in shots["top_types"].items()
        } if shots["total_fga"] else None,
        "play_types": {
            "season": pt["season"], "last_season_only": pt["last_season_only"],
            "types": [{"play_type": r["label"], "possessions": r["poss"], "share_pct": pct(r["share"]),
                       "points_per_possession": r2(r["ppp"]), "league_points_per_possession": r2(r["league_ppp"]),
                       "small_sample": r["small_sample"]} for r in pt["rows"][:6]],
        } if pt["rows"] else None,
        "who_feeds_him": {
            "made_shots": fd["fgm"], "assisted_made_shots": fd["assisted_fgm"],
            "assisted_pct": pct(fd["assisted_share"]), "small_sample": fd["small_sample"],
            "top_passers": [{"passer": x["player_name"], "assists": x["ast"], "assists_on_threes": x["ast_fg3"],
                             "share_of_assisted_pct": pct(x["share_of_assisted"]),
                             "traded_since": bool(x["now_with"])} for x in fd["passers"]],
        } if fd["fgm"] else None,
    }
    return facts


def cache_key(page):
    """Player, our team, data date, prompt version, and which of our players
    are Out. The last part matters because the text may name our best
    defender: marking him Out in the lineup editor must not reuse a text
    that recommends him. It is a string ("201,305"), not a list, so the
    unique index compares the whole set."""
    return {"player_id": page["player"]["player_id"], "vs_team_id": page["us"]["team_id"],
            "data_as_of": page["data_as_of"], "prompt_version": config.ONEPAGER_PROMPT_VERSION,
            "us_out": ",".join(str(p) for p in page["defenders"]["out"])}


def public(doc):
    """What the browser gets: the text and how it was written."""
    if not doc:
        return None
    return {k: doc.get(k) for k in ("text", "flags", "model", "prompt_version", "generated_at", "data_as_of")}


def cached_note(page):
    return public(db.onepager_notes.find_one(cache_key(page)))


def get_note(page, client=None):
    """Returns (note, cached). Raises ReportError (from the writer) when the
    text has to be written and cannot be."""
    key = cache_key(page)
    hit = db.onepager_notes.find_one(key)
    if hit:
        return public(hit), True
    facts = onepager_facts(page)
    out = write(facts, system=config.onepager_prompt(), schema=SCHEMA,
                prompt_version=config.ONEPAGER_PROMPT_VERSION, max_tokens=config.ONEPAGER_MAX_TOKENS,
                client=client, what="note")
    text = (out["sections"].get("how_to_guard") or "").strip()
    flags = [{"section": "How to guard him", "item": None, **f} for f in check_text(text, facts_vocabulary(facts))]
    doc = {**key, "text": text, "flags": flags, "model": out["model"], "requested_model": out["requested_model"],
           "generated_at": out["generated_at"], "usage": out["usage"], "facts": facts,
           "created_at": datetime.now(timezone.utc)}
    # Upsert with $setOnInsert: if two requests write the same page at once,
    # the first one stored wins and the second does not overwrite it.
    db.onepager_notes.update_one(key, {"$setOnInsert": doc}, upsert=True)
    return public(db.onepager_notes.find_one(key)), False
