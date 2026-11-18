"""The matchup model. All formulas are in docs/SPEC.md, "Matchup model".

Units: points per partial possession internally (shown x 100 as points per
100 partial possessions). The league averages about 24 per 100, because a
scorer finishes only a small share of the possessions he is on the floor.

1. League rate L = total points / total partial possessions.
2. Scorer baseline B = (pts + 200 x L) / (poss + 200)        (k = 200)
3. Defender effect  D = (actual - expected) / (poss + 300)    (k = 300, toward 0)
   where expected = sum over his pairs of poss x B_scorer.
4. Size fit S = b_h x height gap + b_w x weight gap / 10 + b_ws x wingspan gap,
   fitted by weighted least squares on what is left after B + D.
5. Pair prior mu = B + D + S; pair estimate E = (pts + 50 x mu) / (poss + 50).
Seasons are blended like the ratings: rate and sample each weighted by
w = MIN_this / (MIN_this + 600), with the scorer's minutes for B and pair
history and the defender's minutes for D.
"""

from itertools import permutations

from app.model.ratings import blend_weight

K_SCORER = 200
K_DEFENDER = 300
K_PAIR = 50
GUARD_CENTER_MIN_POSS = 20
SMALL_HISTORY = 20


# ---- Blending ------------------------------------------------------------

def blend_rate(parts):
    """parts: [(weight, numerator, sample)]. Returns (blended rate, blended sample).
    Seasons with no sample give no rate but still count in the sample."""
    parts = [p for p in parts if p[2] is not None]
    if not parts:
        return None, 0.0
    # A player with data but no minutes on record would give every season a
    # weight of 0; weight the seasons equally instead of dropping the data.
    if sum(p[0] for p in parts) <= 0:
        parts = [(1.0, p[1], p[2]) for p in parts]
    total_w = sum(p[0] for p in parts) or 1.0
    with_rate = [p for p in parts if p[2] > 0]
    rate_w = sum(p[0] for p in with_rate)
    rate = sum(p[0] * p[1] / p[2] for p in with_rate) / rate_w if rate_w else None
    sample = sum(p[0] * p[2] for p in parts) / total_w
    return rate, sample


def shrink_toward(rate, sample, target, k):
    """(rate x sample + k x target) / (sample + k)"""
    return ((rate or 0.0) * sample + k * target) / (sample + k)


# ---- Fitting -------------------------------------------------------------

def solve3(a, b):
    """Solve a 3x3 linear system by Gaussian elimination. Returns None if singular."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    n = 3
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def size_gaps(scorer, defender):
    """(height gap in inches, weight gap in 10 lb, wingspan gap in inches),
    scorer minus defender. A missing measurement gives 0 for that gap."""
    def gap(key, scale=1.0):
        a, b = (scorer or {}).get(key), (defender or {}).get(key)
        return (a - b) / scale if a is not None and b is not None else 0.0
    return gap("height_inches"), gap("weight_lbs", 10.0), gap("wingspan_inches")


def fit(pairs, minutes_this, this_season, bios):
    """pairs: [{"season", "off_id", "def_id", "poss", "pts"}]
    minutes_this: {pid: minutes this season}; bios: {pid: {height_inches, ...}}
    Returns a model dict with L, B, D, beta and pair histories."""
    w = lambda pid: blend_weight(minutes_this.get(pid, 0))  # noqa: E731

    seasons = sorted({p["season"] for p in pairs})
    league = {}
    for s in seasons:
        poss = sum(p["poss"] for p in pairs if p["season"] == s)
        pts = sum(p["pts"] for p in pairs if p["season"] == s)
        league[s] = pts / poss if poss else 0.0

    # Per player and season totals as scorer and as defender
    off, dfn, hist = {}, {}, {}
    for p in pairs:
        o = off.setdefault(p["off_id"], {}).setdefault(p["season"], [0.0, 0.0])
        o[0] += p["pts"]; o[1] += p["poss"]
        d = dfn.setdefault(p["def_id"], {}).setdefault(p["season"], [])
        d.append(p)
        h = hist.setdefault((p["off_id"], p["def_id"]), {}).setdefault(p["season"], [0.0, 0.0])
        h[0] += p["pts"]; h[1] += p["poss"]

    def season_weight(pid, season):
        return w(pid) if season == this_season else 1 - w(pid)

    def blended_league(pid, season_list):
        parts = [(season_weight(pid, s), league[s]) for s in season_list]
        tw = sum(x[0] for x in parts)
        return sum(a * b for a, b in parts) / tw if tw else (sum(league.values()) / len(league))

    # 2. Scorer baselines
    B, B_sample = {}, {}
    for pid, by_season in off.items():
        rate, sample = blend_rate([(season_weight(pid, s), v[0], v[1]) for s, v in by_season.items()])
        target = blended_league(pid, list(by_season))
        B[pid] = shrink_toward(rate, sample, target, K_SCORER)
        B_sample[pid] = sample
    league_all = sum(league.values()) / len(league) if league else 0.0

    def baseline(pid):
        return B.get(pid, league_all)

    # 3. Defender effects
    D, D_sample = {}, {}
    for pid, by_season in dfn.items():
        parts = []
        for s, rows in by_season.items():
            actual = sum(r["pts"] for r in rows)
            expected = sum(r["poss"] * baseline(r["off_id"]) for r in rows)
            poss = sum(r["poss"] for r in rows)
            parts.append((season_weight(pid, s), actual - expected, poss))
        rate, sample = blend_rate(parts)
        D[pid] = shrink_toward(rate, sample, 0.0, K_DEFENDER)
        D_sample[pid] = sample

    # 4. Size fit: weighted least squares, no intercept, on per-possession leftovers
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    yy = 0.0
    for p in pairs:
        if p["poss"] <= 0:
            continue
        x = size_gaps(bios.get(p["off_id"]), bios.get(p["def_id"]))
        y = p["pts"] / p["poss"] - baseline(p["off_id"]) - D.get(p["def_id"], 0.0)
        wt = p["poss"]
        yy += wt * y * y
        for i in range(3):
            xty[i] += wt * x[i] * y
            for j in range(3):
                xtx[i][j] += wt * x[i] * x[j]
    beta = solve3(xtx, xty) or [0.0, 0.0, 0.0]
    explained = sum(beta[i] * xty[i] for i in range(3))
    r2 = explained / yy if yy else 0.0

    return {
        "league": league, "league_all": league_all, "this_season": this_season,
        "B": B, "B_sample": B_sample, "D": D, "D_sample": D_sample,
        "beta": beta, "size_r2": r2, "hist": hist, "minutes_this": minutes_this, "bios": bios,
    }


# ---- Estimates -----------------------------------------------------------

def pair_estimate(model, off_id, def_id):
    """Expected points per partial possession for this scorer against this
    defender, with every part of the estimate."""
    B = model["B"].get(off_id, model["league_all"])
    D = model["D"].get(def_id, 0.0)
    gaps = size_gaps(model["bios"].get(off_id), model["bios"].get(def_id))
    S = sum(b * g for b, g in zip(model["beta"], gaps))
    mu = B + D + S
    h = model["hist"].get((off_id, def_id), {})
    w = blend_weight(model["minutes_this"].get(off_id, 0))
    parts = [((w if s == model["this_season"] else 1 - w), v[0], v[1]) for s, v in h.items()]
    rate, sample = blend_rate(parts)
    raw_poss = sum(v[1] for v in h.values())
    E = shrink_toward(rate, sample, mu, K_PAIR) if sample > 0 else mu
    return {
        "expected": E, "baseline": B, "defender_effect": D, "size": S, "prior": mu,
        "history_poss": raw_poss, "history_rate": rate, "history_shift": E - mu,
        "vs_norm": E - B, "gaps": {"height_in": gaps[0], "weight_10lb": gaps[1], "wingspan_in": gaps[2]},
    }


def position_blocked(model, off_id, def_id, positions):
    """A guard may not guard a center (or the reverse) without 20+ partial
    possessions of history between them."""
    a, b = positions.get(off_id), positions.get(def_id)
    if {a, b} != {"G", "C"}:
        return False
    poss = sum(v[1] for v in model["hist"].get((off_id, def_id), {}).values())
    return poss < GUARD_CENTER_MIN_POSS


def best_assignment(scorers, defenders, cost, usage, blocked=lambda s, d: False):
    """scorers, defenders: five ids each. cost(s, d) -> expected points.
    Returns (assignment {scorer: defender}, total, used_guard). Checks all 120
    orderings; ties go to the earlier ordering."""
    best, best_total = None, None
    for order in permutations(defenders):
        if any(blocked(s, d) for s, d in zip(scorers, order)):
            continue
        total = sum(usage.get(s, 0.0) * cost(s, d) for s, d in zip(scorers, order))
        if best_total is None or total < best_total - 1e-12:
            best, best_total = order, total
    if best is None:
        # The position guard left no valid ordering: fall back to all orderings.
        a, t, _ = best_assignment(scorers, defenders, cost, usage)
        return a, t, False
    return dict(zip(scorers, best)), best_total, True


def reason_line(est, scorer_name, defender_name):
    """One line built from the parts of the estimate, largest first."""
    bits = []
    d = est["defender_effect"] * 100
    if abs(d) >= 0.05:
        bits.append((abs(d), f"{defender_name} allows {abs(d):.1f} {'fewer' if d < 0 else 'more'} than expected"))
    s = est["size"] * 100
    if abs(s) >= 0.05:
        h = est["gaps"]["height_in"]
        size_text = f"{abs(h):.0f} in {'shorter' if h > 0 else 'taller'}" if abs(h) >= 1 else "size"
        bits.append((abs(s), f"{size_text} ({s:+.1f})"))
    if est["history_poss"] > 0:
        shift = est["history_shift"] * 100
        bits.append((abs(shift), f"{est['history_poss']:.0f} poss of history at {est['history_rate'] * 100:.1f} "
                                 f"({'pulls down' if shift < 0 else 'pushes up'} {abs(shift):.1f})"))
    bits.sort(key=lambda b: -b[0])
    text = f"{scorer_name} norm {est['baseline'] * 100:.1f}"
    if bits:
        text += "; " + "; ".join(b[1] for b in bits)
    return text + f". Expected {est['expected'] * 100:.1f} per 100."
