"""Tests for rotation scouting: the five tag rules, the counter picks and
their limits, statuses from the lineup editor, and the endpoint."""

import pytest

from app.db import db
from app.services.rotations import pick_five, tag_lineup

POS = {1: "G", 2: "G", 3: "F", 4: "F", 5: "C", 6: "C", 7: "G", 8: "F"}


def rate(three=50, perim=50, inter=50, **extra):
    return {"three_point": three, "perimeter_defense": perim, "interior_defense": inter, **extra}


def keys(tags):
    return [t["key"] for t in tags]


def test_starters_and_small_ball_and_big():
    r = {p: rate() for p in POS}
    assert keys(tag_lineup([1, 2, 3, 4, 5], POS, r, frozenset({1, 2, 3, 4, 5}))) == ["starters"]
    # No center: small ball. Two centers: big.
    assert keys(tag_lineup([1, 2, 3, 4, 7], POS, r, frozenset())) == ["small_ball"]
    assert keys(tag_lineup([1, 3, 4, 5, 6], POS, r, frozenset())) == ["big"]
    # A different five from the starters is not tagged Starters.
    assert "starters" not in keys(tag_lineup([1, 2, 3, 4, 6], POS, r, frozenset({1, 2, 3, 4, 5})))


def test_three_point_needs_four_shooters_rated_60():
    r = {p: rate(three=70) for p in (1, 2, 3)} | {4: rate(three=59), 5: rate(three=20)}
    assert "three_point" not in keys(tag_lineup([1, 2, 3, 4, 5], POS, r, frozenset()))
    r[4] = rate(three=60)
    tags = tag_lineup([1, 2, 3, 4, 5], POS, r, frozenset())
    assert "three_point" in keys(tags) and "4 players" in next(t for t in tags if t["key"] == "three_point")["why"]


def test_defensive_uses_each_players_better_defense_and_needs_four_rated():
    # Guards strong on the perimeter, center strong inside: the better of the two counts.
    r = {1: rate(perim=80, inter=10), 2: rate(perim=76, inter=10), 3: rate(perim=75, inter=60),
         4: rate(perim=40, inter=75), 5: rate(perim=5, inter=90)}
    assert "defensive" in keys(tag_lineup([1, 2, 3, 4, 5], POS, r, frozenset()))
    r[4] = rate(perim=40, inter=50)
    assert "defensive" not in keys(tag_lineup([1, 2, 3, 4, 5], POS, r, frozenset()))
    # Only three players with ratings: not enough to call it.
    few = {1: rate(perim=99), 2: rate(perim=99), 5: rate(inter=99)}
    assert "defensive" not in keys(tag_lineup([1, 2, 3, 4, 5], POS, few, frozenset()))


def test_pick_five_limits():
    score = {1: 90, 2: 85, 7: 80, 5: 75, 6: 70, 3: 20, 4: 10, 8: 5}
    five = pick_five(list(score), POS, score.get)
    # At most three guards and one center: 1, 2, 7 (G), 5 (C), then the best forward.
    assert five == [1, 2, 7, 5, 3]
    # At least one guard even when guards score lowest.
    low_guards = {1: 1, 2: 2, 3: 90, 4: 80, 5: 70, 8: 60, 6: 50}
    five = pick_five(list(low_guards), POS, low_guards.get)
    assert any(POS[p] == "G" for p in five) and sum(POS[p] == "C" for p in five) <= 1
    # Players without the ratings come last: with five rated players, 1 is left out.
    assert 1 not in pick_five([1, 2, 3, 4, 8, 5], POS, lambda p: None if p == 1 else 50)


@pytest.fixture
def rotation_data(client_app, matchup_data):
    """Ratings for both teams, and BBB lineups. AAA: 110 G, 111 G, 112 F
    (Out), 113 F, 114 C, 115 G. BBB likewise 210-215."""
    for team, base in ((1, 110), (2, 210)):
        for i in range(6):
            pid = base + i
            db.attributes.insert_one({"_id": pid, "qualified": True, "ratings": [
                {"key": "three_point", "rating": 70 if i != 4 else 20}, {"key": "perimeter_defense", "rating": 90 - 10 * i},
                {"key": "interior_defense", "rating": 30 + 10 * i}, {"key": "speed", "rating": 60},
                {"key": "pull_up", "rating": 50}, {"key": "playmaking", "rating": 50 + i}, {"key": "finishing", "rating": 50},
                {"key": "rebounding", "rating": 40 + 10 * i}]})
    db.lineups5.insert_many([
        {"_id": "a", "team_id": 2, "player_ids": "210,211,212,213,214", "gp": 2, "min": 80.0, "plus_minus": 12, "season": "2026-27"},
        {"_id": "b", "team_id": 2, "player_ids": "210,211,212,213,215", "gp": 2, "min": 30.0, "plus_minus": -6, "season": "2026-27"},
        {"_id": "c", "team_id": 1, "player_ids": "110,111,112,113,114", "gp": 2, "min": 99.0, "plus_minus": 1, "season": "2026-27"},
    ])
    yield


def test_rotations_endpoint(client_app, rotation_data):
    d = client_app.get("/api/rotations?us=1&them=2").get_json()
    lineups = d["lineups"]
    assert [ln["minutes"] for ln in lineups] == [80.0, 30.0]  # theirs only, most minutes first
    first, second = lineups
    assert first["small_sample"] is False and second["small_sample"] is True
    # 210-214 are the most common starters in the fixture; 215 is a guard, so b has no center.
    assert "starters" in [t["key"] for t in first["tags"]] and "small_ball" in [t["key"] for t in second["tags"]]
    assert first["plus_minus_per48"] == pytest.approx(7.2) and d["tag_counts"]["starters"] == 1
    # Counters come from our healthy roster: 112 is Out.
    for c in d["counters"].values():
        assert 112 not in c["player_ids"] and len(set(c["player_ids"])) == len(c["player_ids"])
        assert c["reason"] and c["rule"]
    sb = d["counters"]["small_ball"]
    assert sum(p["position"] == "C" for p in sb["players"]) <= 1 and sum(p["position"] == "G" for p in sb["players"]) <= 3
    assert d["status_source"] == "official"


def test_counters_follow_the_lineup_editor(client_app, rotation_data):
    d = client_app.get("/api/rotations?us=1&them=2&us_status=110:Out,112:Available&them_status=214:Out").get_json()
    assert d["status_source"] == "lineup"
    small = d["counters"]["small_ball"]["player_ids"]
    assert 110 not in small and 112 in small  # 112 is back, 110 is out
    # Their lineups with an Out player are flagged.
    assert d["lineups"][0]["includes_out"] == [214] and d["lineups"][1]["includes_out"] == []


@pytest.mark.parametrize("query, status", [("us=1", 400), ("us=1&them=2&us_status=110", 400), ("us=1&them=99", 404)])
def test_rotations_errors(client_app, rotation_data, query, status):
    assert client_app.get(f"/api/rotations?{query}").status_code == status
