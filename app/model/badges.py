"""The first four trait badges. Rules are in docs/SPEC.md and badge_config.py.

Badges pool this season's and last season's raw counts, because traits show
slowly, and every badge needs BADGE_MIN_MINUTES over the two seasons.
"""

import math

from app.model.badge_config import BADGE_MIN_MINUTES, BADGES

DEEP_MIN_FGA = 40
DEEP_MIN_SHARE = 0.20
STREAKY_MIN_PAIRS = 300
STREAKY_ALPHA = 0.05
PEST_MIN_LOST_BALL = 15
POSTER_MIN_DUNKS = 25
TOP_SHARE = 0.10


def quantile(values, q):
    """The q-th quantile (0 to 1) of a list, by linear interpolation."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    pos = q * (len(vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def two_proportion_z(made_a, n_a, made_b, n_b):
    """One-sided test that rate A is higher than rate B.
    z = (pA - pB) / sqrt(p (1 - p) (1/nA + 1/nB)), with p the pooled rate.
    Returns (z, p_value)."""
    if not n_a or not n_b:
        return None, None
    pa, pb = made_a / n_a, made_b / n_b
    pooled = (made_a + made_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    if se == 0:
        return None, None
    z = (pa - pb) / se
    # P(Z >= z) for a standard normal
    p_value = 0.5 * math.erfc(z / math.sqrt(2))
    return z, p_value


def per36(count, minutes):
    return count / minutes * 36 if minutes else None


def compute_badges(pooled):
    """pooled: {pid: dict of pooled counts over both seasons}:
       min, fg3a, deep3_fga, deep3_fgm, dunks (+ by type), lost_ball_steals,
       other_steals, deflections, after_make_fga/fgm, after_miss_fga/fgm,
       max_vertical_in, and league_fg3 (pooled league 3P%).
    Returns ({pid: {"badges": [...], "streaky_test": {...} or None}}, summary)."""
    eligible = {pid: p for pid, p in pooled.items() if (p.get("min") or 0) >= BADGE_MIN_MINUTES}
    out = {pid: {"badges": [], "streaky_test": None} for pid in pooled}

    # Thresholds that depend on the whole group.
    lb36 = {pid: per36(p.get("lost_ball_steals") or 0, p["min"]) for pid, p in eligible.items()}
    defl36 = {pid: per36(p.get("deflections") or 0, p["min"]) for pid, p in eligible.items()}
    dunks36 = {pid: per36(p.get("dunks") or 0, p["min"]) for pid, p in eligible.items()}
    lb36_cut = quantile(lb36.values(), 1 - TOP_SHARE)
    defl36_median = quantile(defl36.values(), 0.5)
    dunks36_cut = quantile(dunks36.values(), 1 - TOP_SHARE)

    tested = [pid for pid, p in eligible.items()
              if (p.get("after_make_fga") or 0) + (p.get("after_miss_fga") or 0) >= STREAKY_MIN_PAIRS]
    alpha = STREAKY_ALPHA / len(tested) if tested else None

    for pid, p in eligible.items():
        earned = []

        # Deep Range
        deep_fga = p.get("deep3_fga") or 0
        if deep_fga >= DEEP_MIN_FGA and p.get("fg3a"):
            share = deep_fga / p["fg3a"]
            pct = (p.get("deep3_fgm") or 0) / deep_fga
            if share >= DEEP_MIN_SHARE and pct >= p["league_fg3"]:
                earned.append(badge("deep_range", {
                    "deep_fga": deep_fga, "deep_fgm": p.get("deep3_fgm") or 0,
                    "deep_share": share, "deep_pct": pct, "league_fg3_pct": p["league_fg3"],
                }, f"{p.get('deep3_fgm') or 0} of {deep_fga} from 28 to 39 ft ({pct:.1%}), "
                   f"{share:.0%} of his threes. League 3P% {p['league_fg3']:.1%}."))

        # Streaky Shooter (the test result is kept even when not earned)
        if pid in tested:
            nm, mm = p["after_make_fga"], p["after_make_fgm"]
            nx, xm = p["after_miss_fga"], p["after_miss_fgm"]
            z, p_value = two_proportion_z(mm, nm, xm, nx)
            test = {
                "after_make_fga": nm, "after_make_pct": mm / nm if nm else None,
                "after_miss_fga": nx, "after_miss_pct": xm / nx if nx else None,
                "pairs": nm + nx, "z": z, "p_value": p_value, "alpha": alpha,
                "players_tested": len(tested), "passed": p_value is not None and p_value < alpha,
            }
            out[pid]["streaky_test"] = test
            if test["passed"]:
                earned.append(badge("streaky_shooter", test,
                    f"{test['after_make_pct']:.1%} after a make ({nm} shots) vs {test['after_miss_pct']:.1%} "
                    f"after a miss ({nx} shots). z = {z:.2f}, p = {p_value:.2g} (needed below {alpha:.2g})."))

        # On-Ball Pest
        lb = p.get("lost_ball_steals") or 0
        if (lb >= PEST_MIN_LOST_BALL and lb36_cut is not None and lb36[pid] >= lb36_cut
                and defl36[pid] is not None and defl36[pid] > defl36_median):
            earned.append(badge("on_ball_pest", {
                "lost_ball_steals": lb, "lost_ball_steals_36": lb36[pid],
                "other_steals": p.get("other_steals") or 0, "deflections_36": defl36[pid],
                "cutoff_36": lb36_cut,
            }, f"{lb} lost-ball steals ({lb36[pid]:.2f} per 36, top 10% starts at {lb36_cut:.2f}), "
               f"{p.get('other_steals') or 0} other steals, {defl36[pid]:.1f} deflections per 36."))

        # Poster Maker
        dunks = p.get("dunks") or 0
        if dunks >= POSTER_MIN_DUNKS and dunks36_cut is not None and dunks36[pid] >= dunks36_cut:
            mix = {k: p.get(f"dunks_{k}") or 0 for k in ("driving", "cutting", "running", "putback", "alley_oop")}
            mix_text = ", ".join(f"{v} {k.replace('_', '-')}" for k, v in mix.items() if v)
            vert = p.get("max_vertical_in")
            earned.append(badge("poster_maker", {
                "dunks": dunks, "dunks_36": dunks36[pid], "cutoff_36": dunks36_cut, "mix": mix,
                "max_vertical_in": vert,
            }, f"{dunks} dunks ({dunks36[pid]:.2f} per 36, top 10% starts at {dunks36_cut:.2f}): {mix_text}."
               + (f" Combine max vertical {vert:g} in." if vert else "")))

        out[pid]["badges"] = earned

    summary = {
        "eligible": len(eligible), "streaky_tested": len(tested), "streaky_alpha": alpha,
        "lost_ball_36_cutoff": lb36_cut, "deflections_36_median": defl36_median, "dunks_36_cutoff": dunks36_cut,
    }
    return out, summary


def badge(key, numbers, detail):
    cfg = BADGES[key]
    return {"key": key, "name": cfg["name"], "short": cfg["short"], "meaning": cfg["meaning"],
            "rule": cfg["rule"], "caveat": cfg.get("caveat"), "detail": detail, "numbers": numbers}
