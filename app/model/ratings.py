"""The twelve attribute ratings.

Every formula here is written out in docs/SPEC.md, "How ratings are computed".

Each component is a rate: a numerator over a sample (makes over attempts,
a count over minutes). For each component:
1. Blend the two seasons first, with w = MIN_this / (MIN_this + 600):
     blended rate   = w x rate_this + (1 - w) x rate_last
     blended sample = w x sample_this + (1 - w) x sample_last
     blended league = w x league_this + (1 - w) x league_last
   A season with no data for the component is left out and the weights are
   renormalized.
2. Shrink once, on the blended numbers:
     value = (blended rate x blended sample + k x blended league) / (blended sample + k)
   k = 50 attempts for field goal types, 30 for free throws, 25 possessions
   for post-ups, 400 minutes for per-36 rates and for AST% and AST/TOV.
   Per-36 rates are then multiplied by 36. Components with k = 0 are not shrunk.
3. Qualified: 200+ minutes this season or 500+ last season.
4. Each component becomes a percentile (0 to 1) among qualified players.
5. composite = weighted average of component percentiles;
   rating = round(99 x percentile rank of the composite).
"""

BLEND_MINUTES = 600
# Per-36 rates (and AST%, AST/TOV) are pulled toward the league by this many minutes.
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


def _get(key):
    return lambda r: r.get(key)


def _minutes(r):
    return r.get("min") or None


def _times_min(key):
    """A rate weighted by minutes, so seasons and the league combine by minutes."""
    return lambda r: (r.get(key) * r["min"]) if r.get(key) is not None and r.get("min") else None


def _zone(zones, field):
    return lambda r: zone_count(r, zones, field)


def _efg_makes(efg_key, fga_key):
    """eFG% x FGA gives "effective makes"."""
    return lambda r: (r.get(efg_key) or 0) * (r.get(fga_key) or 0)


# Every component: (numerator, sample, k, scale). value = numerator / sample.
METRICS = {
    # Finishing
    "ra_fg": (_zone(["restricted_area"], "fgm"), _zone(["restricted_area"], "fga"), 50, 1),
    "ra_fga36": (_zone(["restricted_area"], "fga"), _minutes, PER36_K, 36),
    "drive_pts36": (_get("drive_pts"), _minutes, PER36_K, 36),
    # Post scoring
    "post_ppp": (lambda r: r.get("postup_pts") or 0, lambda r: r.get("postup_poss") or 0, 25, 1),
    "post_poss36": (lambda r: r.get("postup_poss") or 0, _minutes, PER36_K, 36),
    "post_touch_pts36": (_get("post_touch_pts"), _minutes, PER36_K, 36),
    # Midrange
    "mid_fg": (_zone(["paint", "midrange"], "fgm"), _zone(["paint", "midrange"], "fga"), 50, 1),
    "mid_fga36": (_zone(["paint", "midrange"], "fga"), _minutes, PER36_K, 36),
    # Three-point shooting
    "fg3": (lambda r: r.get("fg3m") or 0, lambda r: r.get("fg3a") or 0, 50, 1),
    "fg3a36": (_get("fg3a"), _minutes, PER36_K, 36),
    # Catch-and-shoot and pull-up
    "cs_efg": (_efg_makes("catch_shoot_efg_pct", "catch_shoot_fga"), lambda r: r.get("catch_shoot_fga") or 0, 50, 1),
    "cs_fga36": (_get("catch_shoot_fga"), _minutes, PER36_K, 36),
    "pu_efg": (_efg_makes("pull_up_efg_pct", "pull_up_fga"), lambda r: r.get("pull_up_fga") or 0, 50, 1),
    "pu_fga36": (_get("pull_up_fga"), _minutes, PER36_K, 36),
    # Free throws and drawing fouls
    "ft": (lambda r: r.get("ftm") or 0, lambda r: r.get("fta") or 0, 30, 1),
    "fta_per_fga": (lambda r: r.get("fta") or 0, lambda r: r.get("fga") or 0, 0, 1),
    # Playmaking: skill (AST%, AST/TOV, shrunk by minutes) plus volume
    "ast_pct": (_times_min("ast_pct"), _minutes, PER36_K, 1),
    "ast_to": (_times_min("ast_to"), _minutes, PER36_K, 1),
    "potential_ast_pg": (_get("potential_ast"), lambda r: r.get("gp") or None, 0, 1),
    # Rebounding: rates weighted by minutes, not shrunk
    "oreb_pct": (_times_min("oreb_pct"), _minutes, 0, 1),
    "dreb_pct": (_times_min("dreb_pct"), _minutes, 0, 1),
    "reb_chance_pct": (_times_min("reb_chance_pct"), _minutes, 0, 1),
    # Perimeter defense
    "stl36": (_get("stl"), _minutes, PER36_K, 36),
    "defl36": (_get("deflections"), _minutes, PER36_K, 36),
    "contested3_36": (_get("contested_3pt"), _minutes, PER36_K, 36),
    "pts_allowed_per_poss": (_get("def_player_pts"), _get("def_partial_poss"), 0, 1),
    # Interior defense
    "rim_fg_allowed": (lambda r: r.get("def_rim_fgm") or 0, lambda r: r.get("def_rim_fga") or 0, 50, 1),
    "rim_fga_def36": (_get("def_rim_fga"), _minutes, PER36_K, 36),
    "blk36": (_get("blk"), _minutes, PER36_K, 36),
    # Speed
    "avg_speed": (_times_min("avg_speed"), _minutes, 0, 1),
    "miles36": (_get("dist_miles"), _minutes, PER36_K, 36),
}
# Points allowed per possession needs this blended sample, or it is left out.
MIN_DEF_POSSESSIONS = 50


def league_rates(rows):
    """League rate of every component for one season: total numerator over
    total sample, across players who have both."""
    out = {}
    for key, (num_fn, den_fn, _k, _scale) in METRICS.items():
        num = den = 0
        for r in rows:
            n, d = num_fn(r), den_fn(r)
            if n is not None and d:
                num += n
                den += d
        out[key] = num / den if den else None
    return out


def blended_value(key, this, last, w, league_this, league_last):
    """Blend the two seasons, then shrink once. Returns the component value."""
    num_fn, den_fn, k, scale = METRICS[key]
    seasons = []
    for row, weight, league in ((this, w, league_this), (last, 1 - w, league_last)):
        if row is None:
            continue
        num, den = num_fn(row), den_fn(row)
        if num is None or den is None:
            continue
        seasons.append((weight, num, den, (league or {}).get(key)))
    if not seasons:
        return None
    total_w = sum(s[0] for s in seasons) or 1.0
    with_rate = [s for s in seasons if s[2]]
    rate_w = sum(s[0] for s in with_rate)
    rate = sum(s[0] * s[1] / s[2] for s in with_rate) / rate_w if rate_w else None
    sample = sum(s[0] * s[2] for s in seasons) / total_w
    leagues = [(s[0], s[3]) for s in seasons if s[3] is not None]
    league = sum(wt * lg for wt, lg in leagues) / sum(wt for wt, _ in leagues) if leagues and sum(wt for wt, _ in leagues) else None
    if key == "pts_allowed_per_poss" and sample < MIN_DEF_POSSESSIONS:
        return None
    if k:
        if league is None:
            return None
        value = ((rate or 0) * sample + k * league) / (sample + k)
    else:
        if rate is None:
            return None
        value = rate
    return value * scale


def season_samples(row):
    return {
        "ra_fga": zone_count(row, ["restricted_area"], "fga"),
        "postup_poss": row.get("postup_poss") or 0,
        "mid_fga": zone_count(row, ["paint", "midrange"], "fga"),
        "fg3a": row.get("fg3a") or 0,
        "cs_fga": row.get("catch_shoot_fga") or 0,
        "pu_fga": row.get("pull_up_fga") or 0,
        "fta": row.get("fta") or 0,
        "rim_fga_def": row.get("def_rim_fga") or 0,
        "min": row.get("min") or 0,
    }


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
         "parts": [("ast_pct", "AST%", 0.3, False), ("ast_to", "AST/TOV", 0.3, False),
                   ("potential_ast_pg", "Potential assists per game", 0.4, False)]},
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
        st = season_samples(this) if this else {}
        sl = season_samples(last) if last else {}
        blended[pid] = {k: blended_value(k, this, last, w, p["league_this"], p["league_last"]) for k in METRICS}
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
