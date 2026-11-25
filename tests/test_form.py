"""Tests for the Season / Last 10 toggle: the team stats math, picking the
last 10 games, ranks, the roster and player card over the window, and the
endpoints. Ratings, badges and on/off must not change with the window."""

import pytest

from app.db import db
from app.services.form import LAST_N, _rank_corr, team_stats_over, usg_from_sums, window_games


def totals_for(n_games):
    """Team 1 plays team 2 n times; team 1 scores 110 and allows 100 on 100
    possessions each (FGA 88, FTA 25 -> 11, OREB 10, TOV 11)."""
    out = {}
    for i in range(n_games):
        gid, day = f"G{i:02d}", f"2026-11-{i + 1:02d}"
        base = {"fgm": 40, "fga": 88, "fg3m": 12, "fg3a": 35, "ftm": 18, "fta": 25, "oreb": 10, "dreb": 33,
                "tov": 11, "min": 240, "date": day}
        out[(gid, 1)] = {"game_id": gid, "team_id": 1, "opp": 2, "pts": 110 + (5 if i >= n_games - LAST_N else 0), **base}
        out[(gid, 2)] = {"game_id": gid, "team_id": 2, "opp": 1, "pts": 100, **base}
    return out


def test_team_stats_math():
    t = totals_for(3)
    s = team_stats_over(t, 1, ["G00", "G01", "G02"])
    # 88 + 0.44 x 25 - 10 + 11 = 100 possessions a game for both teams.
    assert s["gp"] == 3 and s["pace"] == pytest.approx(100.0)
    assert s["off_rating"] == pytest.approx(115.0) and s["def_rating"] == pytest.approx(100.0)
    assert s["net_rating"] == pytest.approx(15.0)
    assert s["efg_pct"] == pytest.approx((40 + 6) / 88)
    assert s["tov_pct"] == pytest.approx(11 / (88 + 11 + 11))
    assert s["oreb_pct"] == pytest.approx(10 / (10 + 33)) and s["fta_rate"] == pytest.approx(25 / 88)


def test_last_10_picks_the_newest_ten_games():
    t = totals_for(14)
    last = window_games(t, 1, "last10")
    assert len(last) == 10 and last[0] == "G13" and "G03" not in last
    assert len(window_games(t, 1, "season")) == 14
    # The last 10 games score 5 more, so last 10 is better than the season.
    assert team_stats_over(t, 1, last)["off_rating"] == pytest.approx(115.0)
    assert team_stats_over(t, 1, window_games(t, 1, "season"))["off_rating"] < 115.0


def test_usage_over_summed_games_matches_the_box_score_formula():
    # Player 301 in the conftest box score: 25 FGA, 8 FTA, 3 TOV in 30 min;
    # his team: 65 FGA, 20 FTA, 5 TOV, 48 player-minutes.
    p = {"fga": 25, "fta": 8, "tov": 3, "min": 30, "team_fga": 65, "team_fta": 20, "team_tov": 5, "team_min": 48}
    assert usg_from_sums(p) == pytest.approx(100 * (25 + 0.44 * 8 + 3) * (48 / 5) / (30 * (65 + 0.44 * 20 + 5)), abs=0.05)


def test_rank_correlation():
    assert _rank_corr([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert _rank_corr([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0


@pytest.mark.parametrize("path", [
    "/api/teams/1?form=week", "/api/teams/1/roster?form=x", "/api/players/101?form=x",
    "/api/players/101/shots?form=x", "/api/teams/1/defense-shots?form=x",
])
def test_bad_form_is_rejected(client_app, path):
    res = client_app.get(path)
    assert res.status_code == 400 and "season" in res.get_json()["error"]


def test_team_stats_last_10_endpoint(client_app):
    d = client_app.get("/api/teams/1?form=last10").get_json()
    ts = d["team_stats"]
    # In conftest only game 0022600001 has full box lines for both teams.
    assert d["form"] == "last10" and ts["form"] == "last10" and ts["source"] == "box scores" and ts["gp"] == 1
    byk = {s["key"]: s for s in ts["stats"]}
    assert byk["off_rating"]["rank"] in (1, 2) and byk["off_rating"]["of"] == 2
    assert "season_same_method" in byk["net_rating"]
    assert ts["first_date"] == ts["last_date"] == "2026-10-25"


def test_roster_and_card_over_last_10(client_app):
    db.players.insert_many([
        {"_id": 301, "player_id": 301, "player_name": "Box 301", "team_id": 1, "position": "G", "has_stats": True, "gp": 1},
        {"_id": 302, "player_id": 302, "player_name": "Box 302", "team_id": 1, "position": "F", "has_stats": True, "gp": 1},
    ])
    players = {p["player_id"]: p for p in client_app.get("/api/teams/1/roster?form=last10").get_json()["players"]}
    p = players[301]
    assert p["season"]["gp"] == 1 and p["season"]["pts"] == 40.0 and p["season"]["ts_pct"] == pytest.approx(40 / (2 * (25 + 0.44 * 8)))
    assert p["usage"]["usg_pct"] == pytest.approx(12.8, abs=0.05) and p["usage"]["small_sample"] is True
    # Player 101 has no box line in the window: no line, not a zero line.
    assert players[101]["season"] is None
    # On the card, Last 10 filters his shots to the team's last 10 games:
    # all of 101's shots are in game 0022600004, which has no box lines for
    # CCC, so it is not in AAA's window.
    season = client_app.get("/api/players/101").get_json()
    last10 = client_app.get("/api/players/101?form=last10").get_json()
    assert season["shots"]["total_fga"] == 4 and last10["shots"]["total_fga"] == 0
    assert last10["form"]["form"] == "last10" and last10["form"]["team_games"] == 1
    assert client_app.get("/api/players/101/shots?form=last10").get_json()["count"] == 0
    # Ratings, badges and on/off are the same whatever the window.
    assert season["attributes"] == last10["attributes"] and season["onoff"] == last10["onoff"]


def test_defense_shots_over_last_10(client_app):
    d = client_app.get("/api/teams/2/defense-shots?form=last10").get_json()
    assert d["form"] == "last10" and d["total_fga"] == 0
    assert client_app.get("/api/teams/1/defense-shots").get_json()["form"] == "season"
