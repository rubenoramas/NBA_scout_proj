"""Test setup.

Tests run inside the web container against a separate database,
opponent_scout_test, filled with a few hand-made documents. The real data
in opponent_scout is never touched, and results do not change when the
seed data is refreshed.

Run with:  docker compose run --rm web pytest
"""

import os
import sys
from pathlib import Path

import pytest

# Point the app at the test database BEFORE it is imported, because
# app/db.py reads MONGO_URI when it loads.
base_uri = os.environ.get("MONGO_URI", "mongodb://mongo:27017/opponent_scout")
os.environ["MONGO_URI"] = base_uri.rsplit("/", 1)[0] + "/opponent_scout_test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.db import client, db  # noqa: E402

assert db.name == "opponent_scout_test", "Tests must never run against the real database"

SEASON = "2026-27"
LAST = "2025-26"

# Three teams. AAA and BBB play each other this season. AAA and CCC only
# met in last season's playoffs. BBB and CCC have never met.
TEAMS = [
    {"_id": 1, "team_id": 1, "abbreviation": "AAA", "city": "Alpha", "name": "Ants", "full_name": "Alpha Ants", "conference": "East", "division": "Atlantic"},
    {"_id": 2, "team_id": 2, "abbreviation": "BBB", "city": "Beta", "name": "Bees", "full_name": "Beta Bees", "conference": "East", "division": "Central"},
    {"_id": 3, "team_id": 3, "abbreviation": "CCC", "city": "Gamma", "name": "Cats", "full_name": "Gamma Cats", "conference": "West", "division": "Pacific"},
]

STANDINGS = [
    {"_id": 1, "team_id": 1, "conference": "East", "seed": 1, "wins": 6, "losses": 1, "record": "6-1", "streak": "W 3", "last_ten": "6-1", "home_record": "3-0", "road_record": "3-1"},
    {"_id": 2, "team_id": 2, "conference": "East", "seed": 8, "wins": 2, "losses": 5, "record": "2-5", "streak": "L 2", "last_ten": "2-5", "home_record": "1-2", "road_record": "1-3"},
    {"_id": 3, "team_id": 3, "conference": "West", "seed": 4, "wins": 4, "losses": 3, "record": "4-3", "streak": "W 1", "last_ten": "4-3", "home_record": "2-1", "road_record": "2-2"},
]


def game(gid, date, home, away, home_pts=None, away_pts=None, season=SEASON, season_type="regular-season"):
    played = home_pts is not None
    abbr = {t["_id"]: t["abbreviation"] for t in TEAMS}
    return {
        "_id": gid, "game_id": gid, "season": season, "game_date": date, "season_type": season_type,
        "home_team_id": home, "home_abbr": abbr[home], "away_team_id": away, "away_abbr": abbr[away],
        "home_pts": home_pts, "away_pts": away_pts,
        "home_wl": ("W" if home_pts > away_pts else "L") if played else None,
        "away_wl": ("L" if home_pts > away_pts else "W") if played else None,
        "played": played,
    }


SCHEDULE = [
    game("0042500001", "2026-04-30", 3, 1, 110, 101, season=LAST, season_type="playoffs"),
    game("0022600001", "2026-10-25", 1, 2, 100, 90),
    game("0022600002", "2026-11-01", 2, 1, 95, 105),
    game("0022600003", "2026-11-05", 3, 2, 99, 97),
    game("0022600004", "2026-11-10", 1, 3, 120, 111),  # AAA's last game, a different season than L1
    game("0022600005", "2026-12-01", 2, 1),             # next AAA vs BBB meeting
    game("0022600006", "2026-12-20", 1, 2),
]


def log(gid, date, pid, team, pts=10, reb=4, ast=2, mins=30, name=None, season=SEASON):
    return {"_id": f"{gid}_{pid}", "game_id": gid, "game_date": date, "player_id": pid, "season": season,
            "player_name": name or f"Player {pid}", "team_id": team, "pts": pts, "reb": reb, "ast": ast,
            "min": mins}


def box_line(gid, date, pid, team, starter, **stats):
    """A full box score line for the box score tests."""
    line = {"_id": f"{gid}_{pid}", "game_id": gid, "game_date": date, "player_id": pid, "season": SEASON,
            "player_name": f"Box {pid}", "team_id": team, "starter": starter, "plus_minus": 0}
    line.update(stats)
    return line


# G1: AAA 100, BBB 90. Numbers chosen so every formula can be checked by hand.
BOX_LINES = [
    box_line("0022600001", "2026-10-25", 301, 1, True, min=30, pts=40, fgm=15, fga=25, fg3m=4, fg3a=10, ftm=6, fta=8,
             oreb=2, dreb=6, reb=8, ast=5, stl=2, blk=1, tov=3, pf=2),
    box_line("0022600001", "2026-10-25", 302, 1, False, min=18, pts=60, fgm=22, fga=40, fg3m=6, fg3a=15, ftm=10, fta=12,
             oreb=3, dreb=7, reb=10, ast=3, stl=1, blk=0, tov=2, pf=4),
    box_line("0022600001", "2026-10-25", 401, 2, True, min=48, pts=90, fgm=35, fga=70, fg3m=10, fg3a=30, ftm=10, fta=14,
             oreb=5, dreb=20, reb=25, ast=20, stl=5, blk=3, tov=10, pf=15),
]


def build_logs():
    """Player 101 (AAA): 5 earlier games of 10 pts, then 20 in G4 (exactly +10, 2x).
    Player 102 (AAA): only 4 earlier games, so he cannot qualify.
    Player 201 (BBB): ordinary game, no standout."""
    logs = []
    dates = ["2026-10-20", "2026-10-22", "2026-10-25", "2026-11-01", "2026-11-03"]
    for i, d in enumerate(dates):
        logs.append(log(f"E{i}", d, 101, 1, pts=10, name="Steady Scorer"))
        if i < 4:
            logs.append(log(f"E{i}", d, 102, 1, pts=2, name="New Guy"))
        logs.append(log(f"F{i}", d, 201, 2, pts=12))
    logs.append(log("0022600004", "2026-11-10", 101, 1, pts=20, name="Steady Scorer"))
    logs.append(log("0022600004", "2026-11-10", 102, 1, pts=30, name="New Guy"))
    logs.append(log("0022600003", "2026-11-05", 201, 2, pts=13))
    # Last season: a 50 point game for player 101. It must not count in this
    # season's standout average.
    logs.append(log("0042500001", "2026-04-30", 101, 1, pts=50, name="Steady Scorer", season=LAST))
    return logs + BOX_LINES


# Players: 101 has stats and a wingspan, 102 is injured with no stats yet,
# 201 plays for BBB.
PLAYERS = [
    {"_id": 101, "player_id": 101, "player_name": "Steady Scorer", "team_id": 1, "team_abbr": "AAA",
     "position": "G", "height": "6-5", "height_inches": 77, "weight_lbs": 200, "wingspan_inches": 80.5,
     "has_stats": True, "gp": 4, "min_total": 120, "pts_total": 80, "reb_total": 20, "ast_total": 12,
     "stl_total": 4, "blk_total": 2, "tov_total": 8, "fgm_total": 30, "fga_total": 60, "fg3m_total": 8,
     "fg3a_total": 20, "ftm_total": 12, "fta_total": 16},
    {"_id": 102, "player_id": 102, "player_name": "New Guy", "team_id": 1, "team_abbr": "AAA",
     "position": None, "has_stats": False},
    {"_id": 201, "player_id": 201, "player_name": "Player 201", "team_id": 2, "team_abbr": "BBB",
     "position": "C", "has_stats": True, "gp": 2, "min_total": 40, "pts_total": 20, "fgm_total": 8, "fga_total": 16,
     "fg3m_total": 0, "fg3a_total": 0, "ftm_total": 4, "fta_total": 4},
]
INJURIES = [{"_id": 102, "player_id": 102, "team_id": 1, "status": "Out", "reason": "Injury/Illness - Left Knee"}]


def shot(n, pid, team, zone, made, shot_type, x=0, y=10):
    return {"_id": f"S{n}", "game_id": "0022600004", "game_date": "2026-11-10", "player_id": pid, "team_id": team,
            "x": x, "y": y, "distance": 1, "value": 3 if "three" in zone else 2, "made": made,
            "shot_type": shot_type, "zone": zone, "side": "center", "period": 1}


SHOTS = [
    shot(1, 101, 1, "restricted_area", True, "Driving Layup Shot"),
    shot(2, 101, 1, "restricted_area", False, "Driving Layup Shot"),
    shot(3, 101, 1, "corner_three", True, "Jump Shot", x=-230, y=0),
    shot(4, 101, 1, "above_break_three", False, "Pullup Jump shot", x=0, y=260),
    shot(5, 201, 2, "restricted_area", True, "Dunk Shot"),
    shot(6, 201, 2, "midrange", False, "Jump Shot", x=150, y=60),
]
ZONES_LAST = [{"_id": "101_corner_three", "player_id": 101, "zone": "corner_three", "fga": 10, "fgm": 4, "season": LAST}]


@pytest.fixture()
def client_app():
    db.teams.delete_many({})
    db.standings.delete_many({})
    db.schedule.delete_many({})
    db.game_logs.delete_many({})
    db.meta.delete_many({})
    for name in ("players", "injuries", "shots", "shot_zones_last", "shot_types_last", "matchup_pairs",
                 "player_stats", "attributes"):
        db[name].delete_many({})
    db.players.insert_many([dict(p) for p in PLAYERS])
    db.injuries.insert_many([dict(i) for i in INJURIES])
    db.shots.insert_many([dict(x) for x in SHOTS])
    db.shot_zones_last.insert_many([dict(z) for z in ZONES_LAST])
    db.teams.insert_many(TEAMS)
    db.standings.insert_many(STANDINGS)
    db.schedule.insert_many(SCHEDULE)
    db.game_logs.insert_many(build_logs())
    db.meta.insert_one({"_id": "seed", "season": SEASON, "data_as_of": "2026-11-10", "pulled_at": "2026-11-11T14:02:00Z"})
    app = create_app()
    app.config["TESTING"] = True
    yield app.test_client()


def pytest_sessionfinish(session, exitstatus):
    client.drop_database("opponent_scout_test")
