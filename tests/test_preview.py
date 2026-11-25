"""Tests for the game preview model: no leakage, the blend with last season,
rest and back-to-backs, the fit and the win probability. Uses small
in-memory schedules, so no database is needed."""

import copy
import math

import pytest

from app.model.preview import build_features, fit, predict, previous_season, win_prob

S = "2026-27"


def game(gid, day, home, away, hp=None, ap=None):
    return {"game_id": gid, "season": S, "game_date": f"2026-11-{day:02d}", "home_team_id": home, "away_team_id": away,
            "home_pts": hp, "away_pts": ap, "played": hp is not None}


GAMES = [
    game("g1", 1, 1, 2, 110, 100),
    game("g2", 2, 3, 1, 95, 105),
    game("g3", 3, 2, 3, 120, 90),
    game("g4", 4, 1, 3, 100, 101),   # the game under test
    game("g5", 4, 2, 4, 99, 98),     # same day as g4
    game("g6", 5, 3, 2, 80, 130),    # later
    game("g7", 7, 1, 2),             # upcoming
]
# Every team: 100 possessions per game (FGA 90, FTA 0, OREB 0, TOV 10).
BOX = {(g["game_id"], t): {"pts": 0, "poss_est": 100.0} for g in GAMES for t in (g["home_team_id"], g["away_team_id"])}
PRIORS = {(1, "2025-26"): 4.0, (2, "2025-26"): -2.0, (3, "2025-26"): 0.0}


def rows_by_id(games, box=BOX, k=5):
    return {r["game_id"]: r for r in build_features(games, box, PRIORS, k)}


def test_no_input_uses_the_game_itself_a_same_day_game_or_a_later_game():
    before = rows_by_id(GAMES)
    # Change the result of g4 itself, the same-day g5, and the later g6, and
    # blow up their possessions. g4's inputs (and earlier games') must not move.
    changed = copy.deepcopy(GAMES)
    for g in changed:
        if g["game_id"] in ("g4", "g5", "g6"):
            g["home_pts"], g["away_pts"] = 200, 0
    box = dict(BOX)
    for key in list(box):
        if key[0] in ("g4", "g5", "g6"):
            box[key] = {"pts": 0, "poss_est": 1.0}
    after = rows_by_id(changed, box)
    for gid in ("g1", "g2", "g3", "g4", "g5"):
        assert after[gid]["x"] == before[gid]["x"], gid
        assert after[gid]["home"] == before[gid]["home"] and after[gid]["away"] == before[gid]["away"], gid
    # The upcoming g7 does see the changed results, as it should.
    assert after["g7"]["x"] != before["g7"]["x"]


def test_pre_game_net_rating_blends_with_last_season():
    r = rows_by_id(GAMES)["g4"]
    # Team 1 before Nov 4: +10 in g1, +10 in g2, over 200 possessions: +10.0 per 100, 2 games.
    h = r["home"]
    assert h["current_net"] == pytest.approx(10.0) and h["games"] == 2 and h["prior_net"] == 4.0
    assert h["net"] == pytest.approx((2 * 10.0 + 5 * 4.0) / 7)
    # Team 3: -10 in g2, -30 in g3: -20.0 per 100.
    assert r["away"]["current_net"] == pytest.approx(-20.0)
    # Before any game, the net rating is last season's.
    first = rows_by_id(GAMES)["g1"]
    assert first["home"]["net"] == 4.0 and first["home"]["current_net"] is None
    # No prior season on record: league average (0).
    assert rows_by_id([game("x", 1, 9, 8)])["x"]["home"]["net"] == 0.0


def test_rest_and_back_to_backs():
    r = rows_by_id(GAMES)["g4"]
    # Team 1 last played Nov 2: 1 day of rest. Team 3 played Nov 3: back-to-back.
    assert r["home"]["rest"] == 1 and not r["home"]["b2b"]
    assert r["away"]["rest"] == 0 and r["away"]["b2b"]
    assert r["x"]["rest_diff"] == 1 and r["x"]["b2b_away"] == 1.0 and r["x"]["b2b_home"] == 0.0
    # A team's first game counts as full rest (3 days, the cap), not a back-to-back.
    g1 = rows_by_id(GAMES)["g1"]
    assert g1["home"]["rest"] == 3 and not g1["home"]["b2b"]
    # Upcoming games have no margin.
    assert rows_by_id(GAMES)["g7"]["margin"] is None and rows_by_id(GAMES)["g4"]["margin"] == -1


def test_fit_recovers_a_known_line():
    rows = []
    for i in range(40):
        x = {"home_court": 1.0, "net_diff": float(i - 20), "rest_diff": float(i % 3 - 1),
             "b2b_home": float(i % 5 == 0), "b2b_away": float(i % 7 == 0)}
        rows.append({"x": x, "margin": 2.5 + 0.9 * x["net_diff"] - 0.4 * x["rest_diff"] - 2 * x["b2b_home"]
                     + 1 * x["b2b_away"] + (1 if i % 2 else -1)})
    m = fit(rows)
    assert m["beta"]["home_court"] == pytest.approx(2.5, abs=0.3) and m["beta"]["net_diff"] == pytest.approx(0.9, abs=0.02)
    assert m["sigma"] == pytest.approx(1.0, abs=0.15)
    assert predict(m["beta"], rows[0]) == pytest.approx(rows[0]["margin"], abs=1.5)


def test_win_probability():
    assert win_prob(0, 12) == pytest.approx(0.5)
    assert win_prob(12, 12) == pytest.approx(0.8413, abs=1e-4)
    assert win_prob(-3.5, 12) == pytest.approx(1 - win_prob(3.5, 12))
    assert previous_season("2026-27") == "2025-26" and previous_season("2009-10") == "2008-09"
    assert not math.isnan(win_prob(100, 12))


def test_rest_for_upcoming_games_uses_the_schedule():
    games = GAMES + [game("g8", 8, 2, 1)]  # Nov 8, the day after the upcoming g7
    r = rows_by_id(games)["g8"]
    # Both teams play g7 on Nov 7 (not played yet): g8 is a back-to-back for both.
    assert r["home"]["b2b"] and r["away"]["b2b"] and r["margin"] is None
    # Results of unplayed games never count toward the net rating.
    assert r["home"]["games"] == 4 and r["away"]["games"] == 3
