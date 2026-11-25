"""Schedule spots: rest and travel facts for a team around one game.

Facts only, counted from the schedule: days of rest before the game, back
to back, 3 games in 4 nights, 4 in 6 nights, and where the game sits in the
current road trip or home stand. No claims about what they do to a team.
"""

from datetime import date

from app.db import db
from app.services.context import involves


def _day(text):
    return date.fromisoformat(text[:10])


def spot_at(games, i, team_id):
    """games: one team's games in one season, sorted by date."""
    g = games[i]
    d = _day(g["game_date"])
    home = g["home_team_id"] == team_id
    prev = games[i - 1] if i > 0 else None
    rest = (d - _day(prev["game_date"])).days - 1 if prev else None
    days_back = [(d - _day(x["game_date"])).days for x in games[: i + 1]]
    # "3 in 4" means this is at least the third game in the 4 nights ending today.
    in_four = sum(1 for n in days_back if 0 <= n <= 3)
    in_six = sum(1 for n in days_back if 0 <= n <= 5)
    start = i
    while start > 0 and (games[start - 1]["home_team_id"] == team_id) == home:
        start -= 1
    end = i
    while end < len(games) - 1 and (games[end + 1]["home_team_id"] == team_id) == home:
        end += 1
    return {
        "rest_days": rest,
        "back_to_back": rest == 0,
        "three_in_four": in_four >= 3,
        "four_in_six": in_six >= 4,
        "games_in_4_nights": in_four,
        "games_in_6_nights": in_six,
        "stretch": {"kind": "home stand" if home else "road trip", "game": i - start + 1, "games": end - start + 1},
    }


def team_spots(team_id, season):
    """{game_id: spots} for every game of one team in one season."""
    games = list(db.schedule.find({**involves(team_id), "season": season}).sort("game_date", 1))
    return {g["game_id"]: spot_at(games, i, team_id) for i, g in enumerate(games)}


def season_spots(season):
    """{(team_id, game_id): spots} for every team, from one schedule read."""
    by_team = {}
    for g in db.schedule.find({"season": season}).sort("game_date", 1):
        for tid in (g["home_team_id"], g["away_team_id"]):
            by_team.setdefault(tid, []).append(g)
    return {(tid, g["game_id"]): spot_at(games, i, tid)
            for tid, games in by_team.items() for i, g in enumerate(games)}


def game_spots(game_id, team_ids, season):
    """Spots for each team in one game: {team_id: spots or None}."""
    return {tid: team_spots(tid, season).get(game_id) for tid in team_ids}
