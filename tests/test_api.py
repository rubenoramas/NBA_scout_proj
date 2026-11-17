"""Tests for GET /api/teams, GET /api/teams/<id>/schedule and
GET /api/games/context, plus the standout rule."""

from app.services.context import find_standout

# ---- /api/teams ---------------------------------------------------------


def test_teams_lists_all_teams_sorted(client_app):
    res = client_app.get("/api/teams")
    assert res.status_code == 200
    body = res.get_json()
    assert [t["abbreviation"] for t in body["teams"]] == ["AAA", "BBB", "CCC"]
    assert body["data_as_of"] == "2026-11-10"
    assert "_id" not in body["teams"][0]


# ---- /api/teams/<id>/schedule -------------------------------------------


def test_schedule_returns_this_season_from_team_view(client_app):
    res = client_app.get("/api/teams/1/schedule")
    assert res.status_code == 200
    body = res.get_json()
    assert body["team"]["abbreviation"] == "AAA"
    games = body["games"]
    # Last season's playoff game is not on this season's calendar.
    assert [g["game_id"] for g in games] == ["G1", "G2", "G4", "G5", "G6"]
    away_win = games[1]
    assert away_win["home"] is False
    assert (away_win["team_pts"], away_win["opp_pts"], away_win["result"]) == (105, 95, "W")
    upcoming = games[3]
    assert upcoming["played"] is False and "result" not in upcoming


def test_schedule_unknown_team_is_404(client_app):
    res = client_app.get("/api/teams/999/schedule")
    assert res.status_code == 404
    assert "999" in res.get_json()["error"]


def test_schedule_bad_id_is_400(client_app):
    res = client_app.get("/api/teams/abc/schedule")
    assert res.status_code == 400
    assert "number" in res.get_json()["error"]


# ---- /api/games/context -------------------------------------------------


def test_context_this_season(client_app):
    res = client_app.get("/api/games/context?us=1&them=2")
    assert res.status_code == 200
    ctx = res.get_json()
    assert ctx["data_as_of"] == "2026-11-10"
    assert ctx["us"]["standing"]["record"] == "6-1"
    assert ctx["us"]["standing"]["streak"] == "W 3"
    assert ctx["them"]["standing"]["seed"] == 8

    last = ctx["us"]["last_game"]
    assert (last["date"], last["opponent"]["abbreviation"], last["result"]) == ("2026-11-10", "CCC", "W")

    meeting = ctx["last_meeting"]
    assert meeting["game_id"] == "G2" and meeting["season"] == "2026-27"
    assert meeting["result"] == "W" and meeting["playoffs"] is False

    assert ctx["next_meeting"]["game_id"] == "G5"
    assert ctx["next_meeting"]["home"] is False


def test_context_last_meeting_from_last_season_playoffs(client_app):
    ctx = client_app.get("/api/games/context?us=1&them=3").get_json()
    meeting = ctx["last_meeting"]
    # G4 (this season) is more recent than L1, so it wins.
    assert meeting["game_id"] == "G4"

    ctx = client_app.get("/api/games/context?us=3&them=1").get_json()
    assert ctx["last_meeting"]["game_id"] == "G4"


def test_context_playoff_meeting_labeled(client_app):
    from app.db import db
    db.schedule.delete_one({"_id": "G4"})
    ctx = client_app.get("/api/games/context?us=1&them=3").get_json()
    meeting = ctx["last_meeting"]
    assert meeting["game_id"] == "L1"
    assert meeting["season"] == "2025-26"
    assert meeting["season_type"] == "playoffs" and meeting["playoffs"] is True
    assert meeting["result"] == "L"


def test_context_never_met(client_app):
    from app.db import db
    db.schedule.delete_one({"_id": "G3"})
    ctx = client_app.get("/api/games/context?us=2&them=3").get_json()
    assert ctx["last_meeting"] is None
    assert ctx["next_meeting"] is None


def test_context_standout_at_exact_threshold(client_app):
    ctx = client_app.get("/api/games/context?us=1&them=2").get_json()
    standout = ctx["us"]["standout"]
    # Player 102 scored 30 but has only 4 earlier games, so 101 is picked.
    assert standout["player_id"] == 101
    assert standout["stat"] == "pts"
    assert (standout["value"], standout["average"], standout["earlier_games"]) == (20, 10.0, 5)
    assert ctx["them"]["standout"] is None


def test_context_validation(client_app):
    cases = {
        "/api/games/context?us=1": 400,
        "/api/games/context?them=1": 400,
        "/api/games/context?us=x&them=1": 400,
        "/api/games/context?us=1&them=1": 400,
        "/api/games/context?us=1&them=999": 404,
    }
    for url, status in cases.items():
        res = client_app.get(url)
        assert res.status_code == status, url
        assert res.get_json()["error"], url


# ---- Standout rule on its own ------------------------------------------


def lines(n, **stats):
    base = {"pts": 10, "reb": 4, "ast": 2}
    base.update(stats)
    return [dict(base) for _ in range(n)]


def test_standout_just_below_threshold_is_none():
    last = [{"player_id": 1, "player_name": "A", "pts": 19, "reb": 4, "ast": 2}]
    assert find_standout(last, {1: lines(5)}) is None


def test_standout_needs_ratio_too():
    # +10 points, and 30 is exactly 1.5 times a 20 average, so it qualifies.
    last = [{"player_id": 1, "player_name": "A", "pts": 30, "reb": 4, "ast": 2}]
    assert find_standout(last, {1: lines(5, pts=20)})["stat"] == "pts"
    # +10 points on a 25 average is only 1.4x, so it does not.
    last = [{"player_id": 1, "player_name": "A", "pts": 35, "reb": 4, "ast": 2}]
    assert find_standout(last, {1: lines(5, pts=25)}) is None


def test_standout_rebounds_and_assists():
    last = [{"player_id": 1, "player_name": "A", "pts": 10, "reb": 10, "ast": 2}]
    found = find_standout(last, {1: lines(5, reb=4)})
    assert (found["stat"], found["stat_label"], found["value"]) == ("reb", "rebounds", 10)

    last = [{"player_id": 1, "player_name": "A", "pts": 10, "reb": 4, "ast": 7}]
    assert find_standout(last, {1: lines(5, ast=2)})["stat"] == "ast"
    last = [{"player_id": 1, "player_name": "A", "pts": 10, "reb": 4, "ast": 6}]
    assert find_standout(last, {1: lines(5, ast=2)}) is None  # only +4


def test_standout_picks_biggest_relative_jump():
    # Player 1: 20 pts vs 10 avg (+100%). Player 2: 10 reb vs 4 avg (+150%).
    last = [
        {"player_id": 1, "player_name": "Scorer", "pts": 20, "reb": 4, "ast": 2},
        {"player_id": 2, "player_name": "Rebounder", "pts": 10, "reb": 10, "ast": 2},
    ]
    found = find_standout(last, {1: lines(5), 2: lines(5)})
    assert found["player_name"] == "Rebounder"
    assert found["relative_jump"] == 1.5
