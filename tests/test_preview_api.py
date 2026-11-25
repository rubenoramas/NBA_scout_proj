"""Tests for the game preview in the app: projections for upcoming games,
saving and freezing them after each load, the running record, the backtest
and the endpoints. A small made-up last season trains the model."""

from datetime import date, timedelta
from pathlib import Path

import pytest

import app.services.preview as svc
from app.db import db

LAST = "2025-26"


@pytest.fixture
def preview_data(client_app):
    """60 last-season games among AAA, BBB and CCC: AAA strong, CCC weak,
    home teams a little better."""
    db.meta.update_one({"_id": "seed"}, {"$set": {"last_season": LAST}})
    strength = {1: 6, 2: 0, 3: -6}
    games, logs = [], []
    day = date(2025, 10, 21)
    pairs = [(1, 2), (2, 3), (3, 1), (2, 1), (3, 2), (1, 3)]
    for i in range(60):
        home, away = pairs[i % 6]
        margin = strength[home] - strength[away] + 2 + (5 if i % 3 == 0 else -4)
        hp, ap = 105 + margin // 2, 105 - (margin - margin // 2)
        gid = f"00225{i:05d}"
        games.append({"_id": gid, "game_id": gid, "season": LAST, "game_date": day.isoformat(),
                      "season_type": "regular-season", "home_team_id": home, "away_team_id": away,
                      "home_abbr": "x", "away_abbr": "y", "home_pts": hp, "away_pts": ap,
                      "home_wl": "W" if hp > ap else "L", "away_wl": "L" if hp > ap else "W", "played": True})
        for team, pts in ((home, hp), (away, ap)):
            logs.append({"_id": f"{gid}_{team}", "game_id": gid, "season": LAST, "game_date": day.isoformat(),
                         "player_id": 9000 + team, "team_id": team, "pts": pts, "fga": 88, "fta": 20, "oreb": 10, "tov": 13})
        day += timedelta(days=2)
    db.schedule.insert_many(games)
    db.game_logs.insert_many(logs)
    db.team_priors.insert_many([{"_id": f"{t}_{LAST}", "team_id": t, "season": LAST, "net_rating": n}
                                for t, n in ((1, 5.0), (2, 0.0), (3, -5.0))])
    svc._cache.update(key=None, model=None)
    yield
    svc._cache.update(key=None, model=None)


def test_context_carries_a_projection_for_the_next_meeting(client_app, preview_data):
    p = client_app.get("/api/games/context?us=1&them=2").get_json()["projection"]
    # Next AAA-BBB meeting: Dec 1 at BBB.
    assert p["game_id"] == "0022600005" and p["home"] == "BBB" and p["away"] == "AAA"
    assert p["favorite"] in ("AAA", "BBB") and p["by"] == abs(p["home_margin"])
    assert 0.5 <= p["favorite_win_prob"] <= 1 and p["avg_miss"] > 0 and p["sigma"] > p["avg_miss"]
    assert p["home_win_prob"] == pytest.approx(svc.win_prob(p["home_margin"], p["sigma"]), abs=0.01)


def test_saving_then_freezing_projections(client_app, preview_data):
    saved, frozen = svc.save_projections()
    assert (saved, frozen) == (2, 0)  # the two upcoming games
    doc = db.projections.find_one({"_id": "0022600005"})
    assert doc["final"] is False and doc["data_as_of"] == "2026-11-10" and "saved_at" in doc
    projected = doc["home_margin"]

    # The game is played: the next load freezes the projection with the result.
    db.schedule.update_one({"_id": "0022600005"}, {"$set": {"played": True, "home_pts": 90, "away_pts": 112}})
    svc._cache.update(key=None, model=None)
    assert svc.save_projections() == (1, 1)
    doc = db.projections.find_one({"_id": "0022600005"})
    assert doc["final"] is True and doc["actual_home_margin"] == -22 and doc["home_margin"] == projected

    # A frozen projection never changes, even if later data would move it.
    db.team_priors.update_many({}, {"$set": {"net_rating": 0.0}})
    svc._cache.update(key=None, model=None)
    svc.save_projections()
    assert db.projections.find_one({"_id": "0022600005"})["home_margin"] == projected

    r = client_app.get("/api/projections/record?team=1").get_json()
    assert r["saved"]["games"] == 1
    assert r["saved"]["avg_miss"] == pytest.approx(abs(-22 - projected), abs=0.1)
    g = r["team_recent"][0]
    assert g["winner"] == "AAA" and g["picked_winner"] == (projected < 0)
    assert r["backtest"]["games"] >= 1 and r["model"]["train_season"] == LAST

    p = client_app.get("/api/games/0022600005/projection").get_json()
    assert p["played"] is True and p["saved"]["final"] is True and p["current"] is None
    p = client_app.get("/api/games/0022600006/projection").get_json()
    assert p["played"] is False and p["saved"]["final"] is False and p["current"]["game_id"] == "0022600006"


def test_games_played_before_any_save_are_not_graded(client_app, preview_data):
    # Nothing was saved before these games, so the record stays empty:
    # the backtest is reported separately, never as saved projections.
    svc.save_projections()
    r = client_app.get("/api/projections/record").get_json()
    assert r["saved"]["games"] == 0 and r["saved"]["avg_miss"] is None
    assert db.projections.count_documents({"final": True}) == 0


@pytest.mark.parametrize("path, status", [
    ("/api/games/abc/projection", 400), ("/api/games/9999999999/projection", 404),
    ("/api/projections/record?team=x", 400),
])
def test_projection_errors(client_app, preview_data, path, status):
    assert client_app.get(path).status_code == status


def test_no_betting_language_on_screen():
    js = (Path(__file__).resolve().parent.parent / "app/static/js/projection.js").read_text().lower()
    for word in ("spread", "odds", "bet", "moneyline", "cover"):
        assert word not in js, word
