"""Tests for GET /api/games/<game_id>/boxscore and its formulas."""

import pytest

from app.services.boxscore import game_score, true_shooting


def get_box(client_app, game_id="0022600001"):
    return client_app.get(f"/api/games/{game_id}/boxscore")


def test_boxscore_ids_must_be_ten_digits(client_app):
    res = get_box(client_app, "abc")
    assert res.status_code == 400
    assert "10 digits" in res.get_json()["error"]


def test_boxscore_unknown_and_unplayed_games(client_app):
    res = get_box(client_app, "0022699999")
    assert res.status_code == 404 and "No game" in res.get_json()["error"]
    res = get_box(client_app, "0022600005")
    assert res.status_code == 404 and "not been played" in res.get_json()["error"]


@pytest.fixture()
def box(client_app):
    res = get_box(client_app, "0022600001")
    assert res.status_code == 200
    return res.get_json()


def test_boxscore_game_info_and_totals_equal_final(box):
    assert box["game"]["venue"] == "AAA"
    assert box["home"]["team"]["abbreviation"] == "AAA" and box["away"]["team"]["abbreviation"] == "BBB"
    assert box["home"]["totals"]["pts"] == box["home"]["pts"] == 100
    assert box["away"]["totals"]["pts"] == box["away"]["pts"] == 90
    assert box["home"]["totals"]["fga"] == 65 and box["home"]["totals"]["min"] == 48
    assert box["has_lines"] is True and box["starters_known"] is True


def test_boxscore_starters_first(box):
    players = box["home"]["players"]
    assert [p["player_id"] for p in players] == [301, 302]  # starter first, despite fewer points
    assert players[0]["starter"] is True and players[1]["starter"] is False


def test_boxscore_player_formulas(box):
    p = box["home"]["players"][0]
    # TS% = 40 / (2 x (25 + 0.44 x 8)) = 0.7013
    assert p["ts_pct"] == pytest.approx(40 / 57.04)
    # eFG% = (15 + 0.5 x 4) / 25 = 0.68
    assert p["efg_pct"] == pytest.approx(0.68)
    # GmSc = 40 + 6 - 17.5 - 0.8 + 1.4 + 1.8 + 2 + 3.5 + 0.7 - 0.8 - 3 = 33.3
    assert p["game_score"] == 33.3
    # USG% = 100 x (25 + 3.52 + 3) x (48 / 5) / (30 x (65 + 8.8 + 5)) = 12.8
    assert p["usg_pct"] == pytest.approx(12.8, abs=0.01)
    assert p["ast_tov"] == pytest.approx(5 / 3)
    assert p["fg_pct"] == pytest.approx(0.6)


def test_boxscore_four_factors(box):
    ff = box["home"]["four_factors"]
    assert ff["efg_pct"] == pytest.approx(42 / 65)
    assert ff["tov_pct"] == pytest.approx(5 / 78.8)
    assert ff["oreb_pct"] == pytest.approx(5 / 25)  # 5 OREB, opponent 20 DREB
    assert ff["ft_rate"] == pytest.approx(20 / 65)


def test_boxscore_played_game_without_lines(client_app):
    body = get_box(client_app, "0022600002").get_json()
    assert body["has_lines"] is False
    assert body["home"]["players"] == [] and body["home"]["totals"] is None
    assert body["home"]["four_factors"] is None
    assert body["home"]["pts"] == 95


def test_formula_helpers_handle_zero_attempts():
    zero = {"pts": 0, "fgm": 0, "fga": 0, "fg3m": 0, "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0,
            "stl": 0, "ast": 0, "blk": 0, "pf": 0, "tov": 0}
    assert true_shooting(zero) is None
    assert game_score(zero) == 0


def test_standout_ignores_last_season(client_app):
    standout = client_app.get("/api/games/context?us=1&them=2").get_json()["us"]["standout"]
    # Last season's 50 point game would raise the average above 10.0.
    assert standout["average"] == 10.0 and standout["earlier_games"] == 5
