"""Tests for the series history, who guarded whom, schedule spots and the
team defense shot profile. Uses the hand-made data in conftest.py:
AAA (1) and BBB (2) met twice this season; AAA and CCC (3) met in last
season's playoffs and once this season."""

import pytest

from app.db import db
from app.services.spots import spot_at


def top(game_id, off_id, off_team, def_id, def_team, poss, pts, scorer_pts, season="2026-27", **extra):
    doc = {"_id": f"{game_id}_{off_id}", "game_id": game_id, "season": season, "season_type_id": 2,
           "off_id": off_id, "def_id": def_id, "off_team_id": off_team, "def_team_id": def_team,
           "poss": poss, "pts": pts, "fga": 5, "fgm": 2, "fg3a": 2, "fg3m": 1,
           "scorer_poss": poss * 2, "scorer_pts": scorer_pts, "scorer_fga": 10, "scorer_fgm": 4, "defenders": 4,
           "off_name": f"Scorer {off_id}", "def_name": f"Defender {def_id}"}
    doc.update(extra)
    return doc


# ---- Series history ---------------------------------------------------------

def test_series_lists_every_meeting_newest_first(client_app):
    # A play-in meeting last season, with no box score lines.
    db.schedule.insert_one({"_id": "0052500001", "game_id": "0052500001", "season": "2025-26", "game_date": "2026-04-15",
                            "season_type": "play-in", "home_team_id": 1, "home_abbr": "AAA", "away_team_id": 3,
                            "away_abbr": "CCC", "home_pts": 99, "away_pts": 100, "home_wl": "L", "away_wl": "W",
                            "played": True})
    db.matchup_top.insert_one(top("0042500001", 301, 3, 101, 1, 20.0, 6, 22, season="2025-26", season_type_id=4))
    d = client_app.get("/api/games/series?us=1&them=3").get_json()
    assert [m["game_id"] for m in d["meetings"]] == ["0022600004", "0042500001", "0052500001"]
    first, playoff, playin = d["meetings"]
    assert first["result"] == "W" and first["home"] is True and first["team_pts"] == 120
    assert playoff["season_type"] == "playoffs" and playoff["result"] == "L" and playoff["home"] is False
    # Box scores exist for games in game_logs only.
    assert first["has_box_score"] and playoff["has_box_score"] and not playin["has_box_score"]
    assert playoff["has_matchups"] and not first["has_matchups"]
    # The default is the newest meeting that has matchup data.
    assert d["default_game_id"] == "0042500001"
    assert d["records"] == [
        {"season": "2026-27", "wins": 1, "losses": 0, "postseason_wins": 0, "postseason_losses": 0},
        {"season": "2025-26", "wins": 0, "losses": 2, "postseason_wins": 0, "postseason_losses": 2},
    ]


def test_series_counts_upcoming_and_handles_no_meetings(client_app):
    d = client_app.get("/api/games/series?us=1&them=2").get_json()
    assert len(d["meetings"]) == 2 and d["upcoming_meetings"] == 2 and d["default_game_id"] is None
    d = client_app.get("/api/games/series?us=2&them=3").get_json()
    assert len(d["meetings"]) == 1  # BBB at CCC on Nov 5


@pytest.mark.parametrize("query, status", [("us=1", 400), ("us=1&them=1", 400), ("us=1&them=99", 404), ("us=x&them=2", 400)])
def test_series_validates_input(client_app, query, status):
    assert client_app.get(f"/api/games/series?{query}").status_code == status


# ---- Who guarded whom -----------------------------------------------------------

def test_guarded_shows_both_directions(client_app):
    db.matchup_top.insert_many([
        top("0022600001", 201, 2, 101, 1, 30.0, 8, 20),
        top("0022600001", 202, 2, 102, 1, 25.0, 4, 26),
        top("0022600001", 101, 1, 201, 2, 28.0, 10, 18),
    ])
    d = client_app.get("/api/games/0022600001/guarded?us=1").get_json()
    assert d["us"] == "AAA" and d["them"] == "BBB" and d["game"]["result"] == "W"
    # Their scorers against our defenders, most points first.
    assert [r["scorer_id"] for r in d["their_scorers"]] == [202, 201]
    r = d["their_scorers"][1]
    assert r["defender_name"] == "Defender 101" and r["poss"] == 30.0 and r["pts"] == 8
    assert r["share_of_scorer_poss"] == pytest.approx(0.5)
    assert [r["scorer_id"] for r in d["our_scorers"]] == [101]
    # From BBB's side, the directions swap.
    d = client_app.get("/api/games/0022600001/guarded?us=2").get_json()
    assert [r["scorer_id"] for r in d["their_scorers"]] == [101]


@pytest.mark.parametrize("path, status, words", [
    ("/api/games/0022600001/guarded?us=3", 400, "does not involve"),
    ("/api/games/0022600002/guarded?us=1", 404, "no matchup data"),
    ("/api/games/9999999999/guarded?us=1", 404, "No game"),
    ("/api/games/abc/guarded?us=1", 400, "10 digits"),
    ("/api/games/0022600001/guarded", 400, "missing"),
])
def test_guarded_errors(client_app, path, status, words):
    res = client_app.get(path)
    assert res.status_code == status and words in res.get_json()["error"]


def test_matchups_show_who_guarded_each_scorer_last_meeting(client_app, matchup_data):
    # Last AAA-BBB meeting is Nov 1 (0022600002). 113 guarded 210; 999 has left.
    db.matchup_top.insert_many([
        top("0022600002", 210, 2, 113, 1, 22.4, 7, 15),
        top("0022600002", 211, 2, 999, 1, 18.0, 4, 9),
    ])
    d = client_app.post("/api/matchups", json={"us": 1, "them": 2}).get_json()
    assert d["last_meeting"]["game"]["game_id"] == "0022600002" and d["last_meeting"]["has_data"] is True
    rows = {r["scorer_id"]: r["last_meeting"] for r in d["rows"]}
    assert rows[210]["defender_id"] == 113 and rows[210]["poss"] == 22.4 and rows[210]["still_with_us"] is True
    assert rows[211]["defender_name"] == "Defender 999" and rows[211]["still_with_us"] is False
    assert rows[212] is None  # no row for him in that game


def test_matchups_without_matchup_data_for_the_last_meeting(client_app, matchup_data):
    d = client_app.post("/api/matchups", json={"us": 1, "them": 2}).get_json()
    assert d["last_meeting"]["has_data"] is False
    assert all(r["last_meeting"] is None for r in d["rows"])


# ---- Schedule spots -------------------------------------------------------------

def g(gid, day, home, away=9):
    return {"game_id": gid, "game_date": f"2026-11-{day:02d}", "home_team_id": home, "away_team_id": away}


def test_spots_count_rest_and_stretches():
    # Team 1: home Nov 1, road Nov 3, 4, 5 (3 in 3 nights) and 7 (4 in 6 nights), home Nov 10.
    games = [g("a", 1, 1), g("b", 3, 9, 1), g("c", 4, 9, 1), g("d", 5, 9, 1), g("e", 7, 9, 1), g("f", 10, 1)]
    first = spot_at(games, 0, 1)
    assert first["rest_days"] is None and first["stretch"] == {"kind": "home stand", "game": 1, "games": 1}
    b = spot_at(games, 1, 1)
    assert b["rest_days"] == 1 and not b["back_to_back"] and b["stretch"] == {"kind": "road trip", "game": 1, "games": 4}
    d = spot_at(games, 3, 1)
    assert d["back_to_back"] and d["rest_days"] == 0 and d["three_in_four"] and d["games_in_4_nights"] == 3
    e = spot_at(games, 4, 1)
    # Nov 7 is also the third game in 4 nights (Nov 4, 5 and 7).
    assert e["rest_days"] == 1 and e["four_in_six"] and e["games_in_6_nights"] == 4 and e["three_in_four"]
    assert e["stretch"] == {"kind": "road trip", "game": 4, "games": 4}
    f = spot_at(games, 5, 1)
    assert f["rest_days"] == 2 and not f["four_in_six"] and f["stretch"]["kind"] == "home stand"


def test_context_and_schedule_carry_spots(client_app):
    ctx = client_app.get("/api/games/context?us=1&them=2").get_json()
    # Next AAA-BBB meeting: Dec 1 at BBB. AAA last played Nov 10, BBB Nov 5.
    assert ctx["spots"]["us"]["rest_days"] == 20 and ctx["spots"]["them"]["rest_days"] == 25
    assert ctx["spots"]["us"]["stretch"]["kind"] == "road trip"
    games = client_app.get("/api/teams/1/schedule").get_json()["games"]
    upcoming = [x for x in games if not x["played"]]
    played = [x for x in games if x["played"]]
    assert all("spots" in x and "opp_spots" in x for x in upcoming)
    assert all("spots" not in x for x in played)
    # Dec 20 vs BBB: 18 full days after both teams played on Dec 1.
    dec20 = next(x for x in upcoming if x["game_id"] == "0022600006")
    assert dec20["spots"]["rest_days"] == 18 and dec20["opp_spots"]["rest_days"] == 18


# ---- Where they give up shots --------------------------------------------------

def test_defense_shot_profile(client_app):
    # AAA's games this season: shots in game 0022600004 by the other team are
    # S5 (restricted area, made) and S6 (midrange, missed).
    d = client_app.get("/api/teams/1/defense-shots").get_json()
    assert d["total_fga"] == 2 and d["games"] == 1 and len(d["shots"]) == 2
    z = {r["zone"]: r for r in d["zones"]}
    ra = z["restricted_area"]
    assert ra["fga"] == 1 and ra["fg_pct"] == 1.0 and ra["share"] == 0.5
    # League: 3 of 6 shots at the rim, 2 made.
    assert ra["league_share"] == 0.5 and ra["league_fg_pct"] == pytest.approx(2 / 3)
    assert ra["fg_vs_league"] == pytest.approx(1 / 3) and ra["small_sample"] is True
    assert z["corner_three"]["fga"] == 0 and z["corner_three"]["fg_pct"] is None


def test_defense_shot_profile_errors(client_app):
    assert client_app.get("/api/teams/99/defense-shots").status_code == 404
    assert client_app.get("/api/teams/x/defense-shots").status_code == 400
