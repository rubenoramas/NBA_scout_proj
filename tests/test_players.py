"""Tests for the roster, player card and shot endpoints."""

import pytest


def test_roster_lists_players_with_stats_and_injury(client_app):
    res = client_app.get("/api/teams/1/roster")
    assert res.status_code == 200
    players = res.get_json()["players"]
    assert [p["player_id"] for p in players] == [101, 102]  # most minutes first, no stats last
    star, hurt = players
    assert star["season"]["pts"] == 20.0 and star["season"]["min"] == 30.0
    assert star["season"]["fg_pct"] == pytest.approx(0.5)
    # TS% = 80 / (2 x (60 + 0.44 x 16)) = 0.5965
    assert star["season"]["ts_pct"] == pytest.approx(80 / (2 * 67.04))
    assert star["injury"] is None
    assert hurt["has_stats"] is False and hurt["season"] is None
    assert hurt["injury"] == {"status": "Out", "reason": "Injury/Illness - Left Knee"}


def test_roster_errors(client_app):
    assert client_app.get("/api/teams/999/roster").status_code == 404
    assert client_app.get("/api/teams/abc/roster").status_code == 400


def test_player_card_bio_and_last_games(client_app):
    card = client_app.get("/api/players/101").get_json()
    assert card["player"]["wingspan_inches"] == 80.5
    assert card["player"]["height_inches"] == 77 and card["player"]["weight_lbs"] == 200
    assert card["team"]["abbreviation"] == "AAA"
    assert card["has_stats"] is True
    # Last five games, newest first, this season only (not last season's L1 game).
    dates = [g["date"] for g in card["last_games"]]
    assert dates == sorted(dates, reverse=True) and len(dates) == 5
    assert dates[0] == "2026-11-10"
    assert all(g["game_id"] != "0042500001" for g in card["last_games"])


def test_player_card_zone_table_and_league_comparison(client_app):
    zones = {z["zone"]: z for z in client_app.get("/api/players/101").get_json()["shots"]["zones"]}
    ra = zones["restricted_area"]
    assert (ra["fga"], ra["fgm"]) == (2, 1)
    # League restricted area: 2 made of 3 across both players.
    assert ra["league_fg_pct"] == pytest.approx(2 / 3)
    assert ra["vs_league"] == pytest.approx(0.5 - 2 / 3)
    assert ra["small_sample"] is True
    assert zones["corner_three"]["last_season"] == {"fga": 10, "fgm": 4, "fg_pct": 0.4}
    assert zones["paint"]["fga"] == 0 and zones["paint"]["fg_pct"] is None
    assert sum(z["fga"] for z in zones.values()) == 4


def test_player_card_top_shot_types(client_app):
    top = client_app.get("/api/players/101").get_json()["shots"]["top_types"]
    assert top["rim"]["types"][0] == {"shot_type": "Driving Layup Shot", "fga": 2, "fgm": 1, "fg_pct": 0.5, "share": 1.0}
    assert top["midrange"]["fga"] == 0 and top["midrange"]["types"] == []
    assert {t["shot_type"] for t in top["three"]["types"]} == {"Jump Shot", "Pullup Jump shot"}


def test_player_without_stats_or_wingspan(client_app):
    card = client_app.get("/api/players/102").get_json()
    assert card["has_stats"] is False and card["season"] is None
    assert card["player"]["wingspan_inches"] is None
    assert card["injury"]["status"] == "Out"
    assert card["shots"]["total_fga"] == 0  # no shots, so an empty shot profile


def test_player_errors(client_app):
    assert client_app.get("/api/players/9999").status_code == 404
    assert client_app.get("/api/players/abc").status_code == 400


def test_shots_filters(client_app):
    body = client_app.get("/api/players/101/shots").get_json()
    assert body["count"] == 4 and body["made"] == 2
    assert "side" not in body["shots"][0]  # sides stay out until confirmed
    assert body["shot_types"] == ["Driving Layup Shot", "Jump Shot", "Pullup Jump shot"]
    body = client_app.get("/api/players/101/shots?zone=restricted_area").get_json()
    assert body["count"] == 2 and all(s["zone"] == "restricted_area" for s in body["shots"])
    body = client_app.get("/api/players/101/shots?type=Jump%20Shot").get_json()
    assert body["count"] == 1 and body["shots"][0]["zone"] == "corner_three"
    body = client_app.get("/api/players/101/shots?type=Jump%20Shot&zone=restricted_area").get_json()
    assert body["count"] == 0


def test_shots_bad_filters(client_app):
    res = client_app.get("/api/players/101/shots?zone=moon")
    assert res.status_code == 400 and "Unknown zone" in res.get_json()["error"]
    res = client_app.get("/api/players/101/shots?type=Hook%20Shot")
    assert res.status_code == 400 and "no shots of type" in res.get_json()["error"]
    assert client_app.get("/api/players/9999/shots").status_code == 404
