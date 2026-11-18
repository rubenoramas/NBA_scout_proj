"""The twelve attribute ratings.

Every formula here is written out in docs/SPEC.md, "How ratings are computed".

1. Blend: w = MIN_this / (MIN_this + 600); value = w x this + (1 - w) x last.
2. Shrink shooting percentages toward the league:
   shrunk = (makes + k x league) / (attempts + k).
   Per-36 rates are shrunk the same way, by minutes:
   shrunk per 36 = (count + league rate per minute x 400) / (minutes + 400) x 36.
3. Qualified: 200+ minutes this season or 500+ last season.
4. Each component becomes a percentile (0 to 1) among qualified players.
5. composite = weighted average of component percentiles;
   rating = round(99 x percentile rank of the composite).
"""

BLEND_MINUTES = 600
# Per-36 rates are pulled toward the league by this many minutes.
PER36_K = 400
QUALIFY_THIS = 200
QUALIFY_LAST = 500
SMALL_MINUTES = 300


def blend_weight(min_this):
    """How much this season counts, from 0 to 1."""
    if not min_this:
        return 0.0
    return min_this / (min_this + BLEND_MINUTES)


def blend(this, last, w):
    if this is None:
        return last
    if last is None:
        return this
    return w * this + (1 - w) * last


def shrink(makes, attempts, league, k):
    """Pull a rate toward the league rate: (makes + k x league) / (attempts + k)."""
    if league is None:
        return None
    return (makes + k * league) / (attempts + k)


def per36(count, minutes, league_per_min=None, k=PER36_K):
    """Count per 36 minutes, shrunk toward the league rate:
    (count + league_per_min x k) / (minutes + k) x 36.
    Without a league rate it is the plain rate."""
    if count is None:
        return None
    if league_per_min is None:
        return count / minutes * 36 if minutes else None
    return (count + league_per_min * k) / ((minutes or 0) + k) * 36


def zone_count(row, zones, field):
    z = row.get("zones", {})
    return sum(z.get(name, {}).get(field, 0) for name in zones)


# The count behind every per-36 component. A count of None (no data for him
# in that table) leaves the component out for that season.
PER36_COUNTS = {
    "ra_fga36": lambda r: zone_count(r, ["restricted_area"], "fga"),
    "drive_pts36": lambda r: r.get("drive_pts"),
    "post_poss36": lambda r: r.get("postup_poss") or 0,
    "post_touch_pts36": lambda r: r.get("post_touch_pts"),
    "mid_fga36": lambda r: zone_count(r, ["paint", "midrange"], "fga"),
    "fg3a36": lambda r: r.get("fg3a"),
    "cs_fga36": lambda r: r.get("catch_shoot_fga"),
    "pu_fga36": lambda r: r.get("pull_up_fga"),
    "potential_ast36": lambda r: r.get("potential_ast"),
    "stl36": lambda r: r.get("stl"),
    "defl36": lambda r: r.get("deflections"),
    "contested3_36": lambda r: r.get("contested_3pt"),
    "rim_fga_def36": lambda r: r.get("def_rim_fga"),
    "blk36": lambda r: r.get("blk"),
    "miles36": lambda r: r.get("dist_miles"),
}


def league_per_minute(rows):
    """League rate per minute for every per-36 count, for one season:
    total count / total minutes over players who have that count."""
    out = {}
    for key, fn in PER36_COUNTS.items():
        count = minutes = 0
        for r in rows:
            c = fn(r)
            if c is not None and r.get("min"):
                count += c
                minutes += r["min"]
        out[key] = count / minutes if minutes else None
    return out


def safe_div(a, b):
    if a is None or not b:
        return None
    return a / b


def percentile_ranks(values, higher_is_better=True):
    """Percentile rank (0 to 1) of each value among the others. Ties share
    the average rank. A single value gets 0.5. None values are skipped."""
    items = [(k, v) for k, v in values.items() if v is not None]
    if not items:
        return {}
    if len(items) == 1:
        return {items[0][0]: 0.5}
    ordered = sorted(items, key=lambda kv: kv[1], reverse=not higher_is_better)
    ranks = {}
    i = 0
    n = len(ordered)
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg = (i + j) / 2
        for idx in range(i, j + 1):
            ranks[ordered[idx][0]] = avg / (n - 1)
        i = j + 1
    return ranks


def rating_from_percentile(p):
    return round(99 * p)


# ---- Per-season metrics ------------------------------------------------------
# `row` holds one player's numbers for one season. `league` holds league rates
# for that season. Each function returns a metric value or None.

def season_metrics(row, league):
    m = row.get("min") or 0
    per_min = league.get("per_min", {})

    def rate(key):
        return per36(PER36_COUNTS[key](row), m, per_min.get(key))

    z = row.get("zones", {})
    ra = z.get("restricted_area", {"fga": 0, "fgm": 0})
    mid_fga = sum(z.get(k, {}).get("fga", 0) for k in ("paint", "midrange"))
    mid_fgm = sum(z.get(k, {}).get("fgm", 0) for k in ("paint", "midrange"))
    cs_fga = row.get("catch_shoot_fga") or 0
    pu_fga = row.get("pull_up_fga") or 0
    postup_poss = row.get("postup_poss") or 0
    rim_fga = row.get("def_rim_fga") or 0
    def_poss = row.get("def_partial_poss") or 0
    return {
        # Finishing
        "ra_fg": shrink(ra["fgm"], ra["fga"], league["ra_fg"], 50),
        "ra_fga36": rate("ra_fga36"),
        "drive_pts36": rate("drive_pts36"),
        # Post scoring
        "post_ppp": shrink(row.get("postup_pts") or 0, postup_poss, league["post_ppp"], 25),
        "post_poss36": rate("post_poss36"),
        "post_touch_pts36": rate("post_touch_pts36"),
        # Midrange
        "mid_fg": shrink(mid_fgm, mid_fga, league["mid_fg"], 50),
        "mid_fga36": rate("mid_fga36"),
        # Three-point shooting
        "fg3": shrink(row.get("fg3m") or 0, row.get("fg3a") or 0, league["fg3"], 50),
        "fg3a36": rate("fg3a36"),
        # Catch-and-shoot and pull-up: eFG% x FGA gives "effective makes"
        "cs_efg": shrink((row.get("catch_shoot_efg_pct") or 0) * cs_fga, cs_fga, league["cs_efg"], 50),
        "cs_fga36": rate("cs_fga36"),
        "pu_efg": shrink((row.get("pull_up_efg_pct") or 0) * pu_fga, pu_fga, league["pu_efg"], 50),
        "pu_fga36": rate("pu_fga36"),
        # Free throws and drawing fouls
        "ft": shrink(row.get("ftm") or 0, row.get("fta") or 0, league["ft"], 30),
        "fta_per_fga": safe_div(row.get("fta"), row.get("fga")),
        # Playmaking
        "ast_pct": row.get("ast_pct"),
        "potential_ast36": rate("potential_ast36"),
        "ast_to": row.get("ast_to"),
        # Rebounding
        "oreb_pct": row.get("oreb_pct"),
        "dreb_pct": row.get("dreb_pct"),
        "reb_chance_pct": row.get("reb_chance_pct"),
        # Perimeter defense
        "stl36": rate("stl36"),
        "defl36": rate("defl36"),
        "contested3_36": rate("contested3_36"),
        "pts_allowed_per_poss": safe_div(row.get("def_player_pts"), def_poss) if def_poss >= 50 else None,
        # Interior defense
        "rim_fg_allowed": shrink(row.get("def_rim_fgm") or 0, rim_fga, league["rim_def"], 50) if m else None,
        "rim_fga_def36": rate("rim_fga_def36"),
        "blk36": rate("blk36"),
        # Speed
        "avg_speed": row.get("avg_speed"),
        "miles36": rate("miles36"),
    }


def season_samples(row):
    z = row.get("zones", {})
    return {
        "ra_fga": z.get("restricted_area", {}).get("fga", 0),
        "postup_poss": row.get("postup_poss") or 0,
        "mid_fga": sum(z.get(k, {}).get("fga", 0) for k in ("paint", "midrange")),
        "fg3a": row.get("fg3a") or 0,
        "cs_fga": row.get("catch_shoot_fga") or 0,
        "pu_fga": row.get("pull_up_fga") or 0,
        "fta": row.get("fta") or 0,
        "rim_fga_def": row.get("def_rim_fga") or 0,
        "min": row.get("min") or 0,
    }


# ---- Attribute definitions ---------------------------------------------------
# (metric key, label, weight, lower_is_better)

def attribute_defs(shooting_weights=(0.65, 0.35)):
    acc, vol = shooting_weights
    return [
        {"key": "finishing", "label": "Finishing", "sample": ("ra_fga", 40, "restricted-area FGA"),
         "parts": [("ra_fg", "Restricted-area FG%", 0.4, False), ("ra_fga36", "Restricted-area FGA/36", 0.3, False),
                   ("drive_pts36", "Drive points/36", 0.3, False)]},
        {"key": "post_scoring", "label": "Post scoring", "sample": ("postup_poss", 25, "post-up possessions"),
         "parts": [("post_ppp", "Post-up PPP", 0.5, False), ("post_poss36", "Post-ups/36", 0.2, False),
                   ("post_touch_pts36", "Post-touch points/36", 0.3, False)]},
        {"key": "midrange", "label": "Midrange", "sample": ("mid_fga", 40, "midrange FGA"),
         "parts": [("mid_fg", "Midrange FG%", 0.6, False), ("mid_fga36", "Midrange FGA/36", 0.4, False)]},
        {"key": "three_point", "label": "Three-point shooting", "sample": ("fg3a", 50, "3PA"),
         "parts": [("fg3", "3P%", acc, False), ("fg3a36", "3PA/36", vol, False)]},
        {"key": "catch_shoot", "label": "Catch-and-shoot", "sample": ("cs_fga", 40, "catch-and-shoot FGA"),
         "parts": [("cs_efg", "Catch-and-shoot eFG%", acc, False), ("cs_fga36", "Catch-and-shoot FGA/36", vol, False)]},
        {"key": "pull_up", "label": "Pull-up shooting", "sample": ("pu_fga", 40, "pull-up FGA"),
         "parts": [("pu_efg", "Pull-up eFG%", acc, False), ("pu_fga36", "Pull-up FGA/36", vol, False)]},
        {"key": "free_throws", "label": "Free throws and drawing fouls", "sample": ("fta", 30, "FTA"),
         "parts": [("ft", "FT%", 0.5, False), ("fta_per_fga", "FTA per FGA", 0.5, False)]},
        {"key": "playmaking", "label": "Playmaking", "sample": ("min", SMALL_MINUTES, "minutes"),
         "parts": [("ast_pct", "AST%", 0.4, False), ("potential_ast36", "Potential assists/36", 0.3, False),
                   ("ast_to", "AST/TOV", 0.3, False)]},
        {"key": "rebounding", "label": "Rebounding", "sample": ("min", SMALL_MINUTES, "minutes"),
         "parts": [("oreb_pct", "OREB%", 0.3, False), ("dreb_pct", "DREB%", 0.4, False),
                   ("reb_chance_pct", "Rebound chance %", 0.3, False)]},
        {"key": "perimeter_defense", "label": "Perimeter defense", "sample": ("min", SMALL_MINUTES, "minutes"),
         "parts": [("stl36", "Steals/36", 0.3, False), ("defl36", "Deflections/36", 0.3, False),
                   ("contested3_36", "Contested threes/36", 0.2, False),
                   ("pts_allowed_per_poss", "Points allowed per partial possession", 0.2, True)]},
        {"key": "interior_defense", "label": "Interior defense", "sample": ("rim_fga_def", 40, "rim FGA defended"),
         "parts": [("rim_fg_allowed", "Opponent FG% at the rim", 0.4, True),
                   ("rim_fga_def36", "Rim FGA defended/36", 0.2, False), ("blk36", "Blocks/36", 0.4, False)]},
        {"key": "speed", "label": "Speed", "sample": ("min", SMALL_MINUTES, "minutes"),
         "parts": [("avg_speed", "Average speed (mph)", 0.7, False), ("miles36", "Miles/36", 0.3, False)]},
    ]


def compute_ratings(players, shooting_weights=(0.65, 0.35)):
    """players: {pid: {"this": row or None, "last": row or None,
                       "league_this": {...}, "league_last": {...}}}
    Returns {pid: {"qualified", "w", "min_this", "min_last", "ratings": [...]}}."""
    defs = attribute_defs(shooting_weights)
    blended = {}
    info = {}
    for pid, p in players.items():
        this, last = p.get("this"), p.get("last")
        min_this = (this or {}).get("min") or 0
        min_last = (last or {}).get("min") or 0
        w = blend_weight(min_this)
        mt = season_metrics(this, p["league_this"]) if this else {}
        ml = season_metrics(last, p["league_last"]) if last else {}
        st = season_samples(this) if this else {}
        sl = season_samples(last) if last else {}
        keys = set(mt) | set(ml)
        blended[pid] = {k: blend(mt.get(k), ml.get(k), w) for k in keys}
        info[pid] = {
            "qualified": min_this >= QUALIFY_THIS or min_last >= QUALIFY_LAST,
            "w": w, "min_this": min_this, "min_last": min_last,
            "samples": {k: st.get(k, 0) + sl.get(k, 0) for k in set(st) | set(sl)},
        }

    qualified = [pid for pid, i in info.items() if i["qualified"]]
    # Component percentiles among qualified players.
    part_pct = {}
    for d in defs:
        for key, _label, _w, lower in d["parts"]:
            if key not in part_pct:
                part_pct[key] = percentile_ranks({pid: blended[pid].get(key) for pid in qualified},
                                                 higher_is_better=not lower)
    out = {pid: dict(info[pid], ratings=[]) for pid in info}
    for d in defs:
        composites = {}
        for pid in qualified:
            total = weight = 0.0
            for key, _label, w_part, _lower in d["parts"]:
                p = part_pct[key].get(pid)
                if p is not None:
                    total += w_part * p
                    weight += w_part
            # Missing components are left out and the weights renormalized.
            composites[pid] = total / weight if weight else None
        ranks = percentile_ranks(composites)
        sample_key, sample_min, sample_label = d["sample"]
        for pid in info:
            q = info[pid]["qualified"]
            n = info[pid]["samples"].get(sample_key, 0)
            entry = {
                "key": d["key"], "label": d["label"],
                "rating": rating_from_percentile(ranks[pid]) if q and pid in ranks else None,
                "small_sample": q and n < sample_min,
                "last_season_only": q and info[pid]["min_this"] == 0,
                "sample": {"n": round(n), "min": sample_min, "label": sample_label},
                "components": [
                    {"label": label, "weight": w_part, "lower_is_better": lower,
                     "value": blended[pid].get(key), "percentile": part_pct[key].get(pid) if q else None}
                    for key, label, w_part, lower in d["parts"]
                ],
            }
            out[pid]["ratings"].append(entry)
    return out
