"""Tests for the rating formulas and badge rules in app/model/."""

import pytest

from app.model.badges import compute_badges, quantile, two_proportion_z
from app.model.ratings import (
    blend, blend_weight, blended_value, compute_ratings, league_rates, per36, percentile_ranks,
    rating_from_percentile, shrink,
)

# ---- Rating building blocks ----------------------------------------------


def test_blend_weight_grows_with_minutes():
    assert blend_weight(0) == 0
    assert blend_weight(300) == pytest.approx(300 / 900)
    assert blend_weight(900) == pytest.approx(0.6)
    assert blend_weight(1800) == pytest.approx(0.75)


def test_blend_uses_whichever_season_exists():
    assert blend(0.5, 0.3, 0.25) == pytest.approx(0.35)
    assert blend(None, 0.3, 0.9) == 0.3
    assert blend(0.5, None, 0.1) == 0.5


def test_shrink_pulls_small_samples_toward_league():
    # 4 of 5 with a 35% league rate and k = 50: (4 + 17.5) / 55
    assert shrink(4, 5, 0.35, 50) == pytest.approx(21.5 / 55)
    # No attempts gives exactly the league rate
    assert shrink(0, 0, 0.35, 50) == pytest.approx(0.35)
    # A big sample barely moves
    assert shrink(400, 1000, 0.35, 50) == pytest.approx(417.5 / 1050)


def test_per36_shrinks_by_minutes():
    # League 0.1 per minute (3.6 per 36). 20 in 50 minutes is 14.4 per 36 raw;
    # shrunk: (20 + 0.1 x 400) / (50 + 400) x 36 = 4.8
    assert per36(20, 50, 0.1) == pytest.approx(4.8)
    # 200 in 1000 minutes: (200 + 40) / 1400 x 36 = 6.17, close to the raw 7.2
    assert per36(200, 1000, 0.1) == pytest.approx(240 / 1400 * 36)
    # No minutes gives the league rate; no league rate gives the plain rate
    assert per36(0, 0, 0.1) == pytest.approx(3.6)
    assert per36(10, 360) == pytest.approx(1.0)
    assert per36(None, 100, 0.1) is None


def test_percentile_ranks_ties_and_direction():
    ranks = percentile_ranks({"a": 1, "b": 2, "c": 2, "d": 3, "e": None})
    assert ranks == {"a": 0.0, "b": 0.5, "c": 0.5, "d": 1.0}
    flipped = percentile_ranks({"a": 1, "b": 3}, higher_is_better=False)
    assert flipped == {"a": 1.0, "b": 0.0}
    assert percentile_ranks({"a": 5}) == {"a": 0.5}


def test_rating_scale():
    assert rating_from_percentile(0) == 0
    assert rating_from_percentile(0.5) == 50
    assert rating_from_percentile(1) == 99


def row(minutes, fg3m, fg3a):
    return {"min": minutes, "fg3m": fg3m, "fg3a": fg3a, "fga": fg3a, "zones": {}}


LEAGUE = league_rates([row(1000, 360, 1000)])  # 36% from three, 36 3PA per 36


def test_blend_first_then_shrink_once():
    # This season 43 of 94 in 263 minutes, last season 190 of 484 in 1329.
    this, last = row(263, 43, 94), row(1329, 190, 484)
    lt = ll = {"fg3": 0.36}
    w = blend_weight(263)
    rate = w * 43 / 94 + (1 - w) * 190 / 484
    sample = w * 94 + (1 - w) * 484
    expected = (rate * sample + 50 * 0.36) / (sample + 50)
    assert blended_value("fg3", this, last, w, lt, ll) == pytest.approx(expected)
    # Not the old order (shrink each season, then blend)
    old = w * shrink(43, 94, 0.36, 50) + (1 - w) * shrink(190, 484, 0.36, 50)
    assert blended_value("fg3", this, last, w, lt, ll) != pytest.approx(old)


def test_blend_with_one_season_only():
    # No last season: plain shrink on this season's numbers
    assert blended_value("fg3", row(400, 40, 100), None, blend_weight(400), {"fg3": 0.36}, None) == \
        pytest.approx(shrink(40, 100, 0.36, 50))
    # No attempts this season: the rate comes from last season, but this
    # season's zero attempts still count in the blended sample (0.67 x 200).
    sample = 0.67 * 200
    assert blended_value("fg3", row(300, 0, 0), row(900, 90, 200), 0.33, {"fg3": 0.36}, {"fg3": 0.36}) == \
        pytest.approx((0.45 * sample + 50 * 0.36) / (sample + 50))


def test_compute_ratings_qualification_and_order():
    players = {
        1: {"this": row(400, 50, 120), "last": None, "league_this": LEAGUE, "league_last": LEAGUE},  # good shooter
        2: {"this": row(400, 30, 120), "last": None, "league_this": LEAGUE, "league_last": LEAGUE},  # worse
        3: {"this": row(100, 5, 10), "last": None, "league_this": LEAGUE, "league_last": LEAGUE},    # not qualified
        4: {"this": None, "last": row(900, 200, 500), "league_this": LEAGUE, "league_last": LEAGUE},  # last season only
    }
    out = compute_ratings(players)
    three = {pid: next(r for r in out[pid]["ratings"] if r["key"] == "three_point") for pid in out}
    assert out[3]["qualified"] is False and three[3]["rating"] is None
    assert out[4]["qualified"] is True and three[4]["last_season_only"] is True
    assert three[1]["rating"] > three[2]["rating"]
    # 10 3PA is below the 50 needed, but player 3 is not rated at all.
    assert three[3]["small_sample"] is False
    assert out[1]["w"] == pytest.approx(400 / 1000)


def test_playmaking_uses_skill_and_volume():
    players = {}
    for pid, (minutes, ast_pct, ast_to, pot, gp) in {
        1: (1500, 0.33, 3.3, 300, 50),   # starter: high volume, good rates
        2: (210, 0.40, 4.0, 15, 15),     # backup: great rates in few minutes
        3: (1200, 0.10, 1.0, 50, 50),
    }.items():
        r = row(minutes, 10, 30)
        r.update({"ast_pct": ast_pct, "ast_to": ast_to, "potential_ast": pot, "gp": gp})
        players[pid] = {"this": r, "last": None}
    league = league_rates([p["this"] for p in players.values()])
    for p in players.values():
        p.update(league_this=league, league_last=league)
    out = compute_ratings(players)
    play = {pid: next(r for r in out[pid]["ratings"] if r["key"] == "playmaking")["rating"] for pid in out}
    assert play[1] > play[2] > play[3]


def test_compute_ratings_small_sample_flag():
    players = {
        1: {"this": row(400, 10, 30), "last": None, "league_this": LEAGUE, "league_last": LEAGUE},
        2: {"this": row(400, 30, 120), "last": None, "league_this": LEAGUE, "league_last": LEAGUE},
    }
    out = compute_ratings(players)
    three = next(r for r in out[1]["ratings"] if r["key"] == "three_point")
    assert three["small_sample"] is True and three["sample"] == {"n": 30, "min": 50, "label": "3PA"}


# ---- Badges --------------------------------------------------------------


def test_z_test_hand_worked():
    # 60 of 100 after a make, 45 of 100 after a miss. Pooled 0.525.
    # se = sqrt(0.525 x 0.475 x 0.02) = 0.070622; z = 0.15 / 0.070622 = 2.124
    z, p = two_proportion_z(60, 100, 45, 100)
    assert z == pytest.approx(2.124, abs=0.001)
    assert p == pytest.approx(0.01684, abs=0.0001)
    assert two_proportion_z(0, 0, 1, 2) == (None, None)


def test_quantile():
    assert quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert quantile([0, 10], 0.9) == pytest.approx(9)


def base(**extra):
    p = {"min": 1000, "league_fg3": 0.36, "fg3a": 100, "deep3_fga": 0, "deep3_fgm": 0, "dunks": 0,
         "lost_ball_steals": 0, "other_steals": 0, "deflections": 0,
         "after_make_fga": 0, "after_make_fgm": 0, "after_miss_fga": 0, "after_miss_fgm": 0}
    p.update(extra)
    return p


def names(result, pid):
    return [b["key"] for b in result[pid]["badges"]]


def test_deep_range_edges():
    pooled = {
        1: base(fg3a=200, deep3_fga=40, deep3_fgm=15),   # 20% share, 37.5%: earns
        2: base(fg3a=200, deep3_fga=39, deep3_fgm=20),   # one attempt short
        3: base(fg3a=201, deep3_fga=40, deep3_fgm=15),   # share just under 20%
        4: base(fg3a=200, deep3_fga=40, deep3_fgm=14),   # 35% < league 36%
    }
    out, _ = compute_badges(pooled)
    assert names(out, 1) == ["deep_range"]
    assert names(out, 2) == names(out, 3) == names(out, 4) == []


def test_badges_need_minutes():
    out, summary = compute_badges({1: base(min=499, fg3a=200, deep3_fga=60, deep3_fgm=30)})
    assert names(out, 1) == [] and summary["eligible"] == 0


def test_streaky_needs_strict_significance():
    pooled = {
        # Strong effect over 1000 pairs: p is far below 0.05 / 2
        1: base(after_make_fga=500, after_make_fgm=300, after_miss_fga=500, after_miss_fgm=200),
        # Same rates, too few pairs to be tested
        2: base(after_make_fga=100, after_make_fgm=60, after_miss_fga=100, after_miss_fgm=40),
        # Tested, small effect: not earned, but the result is kept
        3: base(after_make_fga=300, after_make_fgm=150, after_miss_fga=300, after_miss_fgm=145),
    }
    out, summary = compute_badges(pooled)
    assert summary["streaky_tested"] == 2 and summary["streaky_alpha"] == pytest.approx(0.025)
    assert names(out, 1) == ["streaky_shooter"]
    assert out[2]["streaky_test"] is None
    assert out[3]["streaky_test"]["passed"] is False and names(out, 3) == []


def test_pest_and_poster_top_ten_percent():
    pooled = {pid: base(lost_ball_steals=5, deflections=50, dunks_driving=5) for pid in range(1, 21)}
    pooled[1] = base(lost_ball_steals=40, deflections=100, dunks_driving=30, dunks_running=20, dunks_cutting=10)
    pooled[2] = base(lost_ball_steals=14, deflections=100, dunks_driving=24)   # under both minimums
    # Many dunks, but all alley-oops and putbacks: they do not count
    pooled[3] = base(dunks_alley_oop=80, dunks_putback=40)
    out, _ = compute_badges(pooled)
    assert set(names(out, 1)) == {"on_ball_pest", "poster_maker"}
    poster = next(b for b in out[1]["badges"] if b["key"] == "poster_maker")
    assert poster["numbers"]["dunks"] == 60
    assert names(out, 2) == []
    assert "poster_maker" not in names(out, 3)


def test_api_includes_ratings_and_badges(client_app):
    from app.db import db

    db.attributes.delete_many({})
    db.attributes.insert_one({"_id": 101, "player_id": 101, "qualified": True, "blend_weight": 0.4,
                              "ratings": [], "streaky_test": None,
                              "badges": [{"key": "deep_range", "name": "Deep Range", "short": "Deep",
                                          "meaning": "m", "rule": "r", "detail": "d"}]})
    card = client_app.get("/api/players/101").get_json()
    assert card["attributes"]["badges"][0]["name"] == "Deep Range"
    roster = client_app.get("/api/teams/1/roster").get_json()["players"]
    assert roster[0]["badges"][0]["short"] == "Deep"
    assert roster[1]["badges"] == []
    db.attributes.delete_many({})
    assert client_app.get("/api/players/101").get_json()["attributes"] is None
