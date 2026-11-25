"""Game context: records, streaks, last games, standouts and meetings.

Everything here reads MongoDB and returns plain dicts for the API.
"""

from app.db import db

# Last game standout rule. A player stands out when, in his team's last game,
# a stat beat his average from his earlier games this season by at least
# `min_jump`, and was at least `min_ratio` times that average. He needs at
# least MIN_EARLIER_GAMES earlier games so the average means something, and
# real minutes: an average of MIN_AVG_MINUTES over the earlier games and at
# least MIN_LAST_GAME_MINUTES in the last game. The minutes floor stops a
# deep bench player's one good night from beating a starter's big game.
STANDOUT_RULES = [
    {"stat": "pts", "label": "points", "min_jump": 10},
    {"stat": "reb", "label": "rebounds", "min_jump": 6},
    {"stat": "ast", "label": "assists", "min_jump": 5},
]
MIN_RATIO = 1.5
MIN_EARLIER_GAMES = 5
MIN_AVG_MINUTES = 15
MIN_LAST_GAME_MINUTES = 20


def current_season():
    """The season label of the loaded data, such as "2026-27"."""
    meta = db.meta.find_one({"_id": "seed"}) or {}
    if meta.get("season"):
        return meta["season"]
    newest = db.schedule.find_one({}, sort=[("game_date", -1)])
    return newest["season"] if newest else None


def data_as_of():
    """The date of the latest game in the data, such as "2026-11-17"."""
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return meta.get("data_as_of")


def pulled_at():
    """When the data was pulled, as UTC text such as "2026-11-18T16:58:25Z"."""
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return meta.get("pulled_at")


def get_team(team_id):
    return db.teams.find_one({"_id": team_id}, {"_id": 0})


def team_game(game, team_id):
    """Describe a schedule document from one team's point of view."""
    home = game["home_team_id"] == team_id
    result = {
        "game_id": game["game_id"],
        "date": game["game_date"],
        "season": game.get("season"),
        "season_type": game.get("season_type"),
        "playoffs": game.get("season_type") in ("playoffs", "play-in"),
        "home": home,
        "opponent": {
            "team_id": game["away_team_id"] if home else game["home_team_id"],
            "abbreviation": game["away_abbr"] if home else game["home_abbr"],
        },
        "played": bool(game.get("played")),
    }
    if result["played"]:
        result["team_pts"] = game["home_pts"] if home else game["away_pts"]
        result["opp_pts"] = game["away_pts"] if home else game["home_pts"]
        result["result"] = game["home_wl"] if home else game["away_wl"]
    return result


def involves(team_id):
    """MongoDB filter for games where the team played home or away."""
    return {"$or": [{"home_team_id": team_id}, {"away_team_id": team_id}]}


def team_schedule(team_id, season):
    """The team's games. Upcoming games carry schedule spots for both teams."""
    from app.services.spots import season_spots
    spots = season_spots(season)
    games = db.schedule.find({**involves(team_id), "season": season}).sort("game_date", 1)
    out = []
    for g in games:
        row = team_game(g, team_id)
        if not row["played"]:
            row["spots"] = spots.get((team_id, g["game_id"]))
            row["opp_spots"] = spots.get((row["opponent"]["team_id"], g["game_id"]))
        out.append(row)
    return out


def last_game(team_id, season):
    game = db.schedule.find_one(
        {**involves(team_id), "season": season, "played": True},
        sort=[("game_date", -1)],
    )
    return team_game(game, team_id) if game else None


def meetings(us_id, them_id):
    """Games between the two teams, in either building."""
    return {
        "$or": [
            {"home_team_id": us_id, "away_team_id": them_id},
            {"home_team_id": them_id, "away_team_id": us_id},
        ]
    }


def last_meeting(us_id, them_id):
    """The most recent played game between the two, this season or last."""
    game = db.schedule.find_one({**meetings(us_id, them_id), "played": True}, sort=[("game_date", -1)])
    return team_game(game, us_id) if game else None


def next_meeting(us_id, them_id, season):
    game = db.schedule.find_one(
        {**meetings(us_id, them_id), "season": season, "played": False},
        sort=[("game_date", 1)],
    )
    return team_game(game, us_id) if game else None


def standing(team_id):
    doc = db.standings.find_one({"_id": team_id}, {"_id": 0})
    if not doc:
        return None
    keys = ["conference", "seed", "wins", "losses", "record", "streak", "last_ten", "home_record", "road_record"]
    return {k: doc.get(k) for k in keys}


def find_standout(last_lines, earlier_by_player):
    """Apply the standout rule.

    last_lines: each player's box score line from the team's last game.
    earlier_by_player: player_id -> list of his earlier lines this season.
    Returns the single biggest standout (largest jump relative to the
    average), or None.
    """
    best = None
    for line in last_lines:
        earlier = earlier_by_player.get(line["player_id"], [])
        if len(earlier) < MIN_EARLIER_GAMES:
            continue
        avg_minutes = sum(g.get("min") or 0 for g in earlier) / len(earlier)
        if avg_minutes < MIN_AVG_MINUTES or (line.get("min") or 0) < MIN_LAST_GAME_MINUTES:
            continue
        for rule in STANDOUT_RULES:
            stat = rule["stat"]
            value = line.get(stat)
            if value is None:
                continue
            average = sum(g.get(stat) or 0 for g in earlier) / len(earlier)
            jump = value - average
            if jump < rule["min_jump"] or value < MIN_RATIO * average:
                continue
            # Compare jumps across stats by size relative to the average.
            # max(average, 1) avoids dividing by zero for a 0.0 average.
            relative = jump / max(average, 1.0)
            if best is None or relative > best["relative_jump"]:
                best = {
                    "player_id": line["player_id"],
                    "player_name": line.get("player_name"),
                    "stat": stat,
                    "stat_label": rule["label"],
                    "value": value,
                    "average": round(average, 1),
                    "earlier_games": len(earlier),
                    "minutes": line.get("min"),
                    "avg_minutes": round(avg_minutes, 1),
                    "relative_jump": round(relative, 2),
                }
    return best


def team_standout(team_id, game):
    """Standout for one team's last game, read from game_logs."""
    if not game:
        return None
    last_lines = list(db.game_logs.find({"game_id": game["game_id"], "team_id": team_id}))
    if not last_lines:
        return None
    player_ids = [line["player_id"] for line in last_lines]
    earlier_by_player = {}
    # Only this season's earlier games count. game_logs also holds last
    # season's lines (for box scores), which must not leak into the average.
    earlier = db.game_logs.find({
        "player_id": {"$in": player_ids},
        "season": game["season"],
        "game_date": {"$lt": game["date"]},
    })
    for line in earlier:
        earlier_by_player.setdefault(line["player_id"], []).append(line)
    return find_standout(last_lines, earlier_by_player)


def team_context(team_id, season):
    game = last_game(team_id, season)
    return {
        "team": get_team(team_id),
        "standing": standing(team_id),
        "last_game": game,
        "standout": team_standout(team_id, game),
    }


def _projection(game_id):
    from app.services.preview import project
    try:
        return project(game_id)
    except Exception:  # noqa: BLE001 - a missing model must not break the page
        return None


def game_context(us_id, them_id):
    from app.services.spots import game_spots
    season = current_season()
    upcoming = next_meeting(us_id, them_id, season)
    spots = game_spots(upcoming["game_id"], [us_id, them_id], season) if upcoming else {}
    return {
        "season": season,
        "data_as_of": data_as_of(),
        "pulled_at": pulled_at(),
        "us": team_context(us_id, season),
        "them": team_context(them_id, season),
        "last_meeting": last_meeting(us_id, them_id),
        "next_meeting": upcoming,
        # Projected margin and win probability for the next meeting.
        "projection": _projection(upcoming["game_id"]) if upcoming else None,
        # Rest and travel facts for each team around the next meeting.
        "spots": {"us": spots.get(us_id), "them": spots.get(them_id)},
        "standout_rule": {
            "rules": STANDOUT_RULES,
            "min_ratio": MIN_RATIO,
            "min_earlier_games": MIN_EARLIER_GAMES,
            "min_avg_minutes": MIN_AVG_MINUTES,
            "min_last_game_minutes": MIN_LAST_GAME_MINUTES,
        },
    }


# Team stats on the team page, with the direction that ranks 1st.
# True = higher is better. Pace has no better or worse; 1st is the fastest.
TEAM_STATS = [
    ("off_rating", "Offensive rating", "Points scored per 100 possessions", True),
    ("def_rating", "Defensive rating", "Points allowed per 100 possessions", False),
    ("net_rating", "Net rating", "Offensive minus defensive rating", True),
    ("pace", "Pace", "Possessions per 48 minutes (1st is fastest)", True),
    ("efg_pct", "eFG%", "Offense: (FGM + 0.5 x 3PM) / FGA", True),
    ("tov_pct", "TOV%", "Offense: turnovers per play", False),
    ("oreb_pct", "OREB%", "Offense: share of its misses it rebounds", True),
    ("fta_rate", "FT rate", "Offense: FTA / FGA", True),
    ("opp_efg_pct", "Opponent eFG%", "Defense: opponents' eFG%", False),
    ("opp_tov_pct", "Opponent TOV%", "Defense: turnovers it forces per play", True),
    ("opp_oreb_pct", "Opponent OREB%", "Defense: share of misses opponents rebound", False),
    ("opp_fta_rate", "Opponent FT rate", "Defense: opponents' FTA / FGA", False),
]


def team_stats_with_ranks(team_id, form="season"):
    """Each team stat with its league rank (1 = best, or fastest for pace).
    Season: the NBA's official numbers. Last 10: computed from every team's
    last 10 box scores, ranked among those, with this team's season computed
    the same way beside each value (the box scores have no team turnovers or
    team rebounds, so they run lower than the official TOV% and OREB%)."""
    if form != "season":
        from app.services.form import all_team_stats, form_games
        window = all_team_stats(form)
        same_method_season = all_team_stats("season").get(team_id)
        all_stats = [{"team_id": t, **s} for t, s in window.items()]
        mine = next((t for t in all_stats if t["team_id"] == team_id), None)
        if not mine:
            return None
        out = _ranked(mine, all_stats)
        for row in out:
            row["season_same_method"] = (same_method_season or {}).get(row["key"])
        games = form_games(team_id, form)
        dates = sorted(db.game_logs.distinct("game_date", {"game_id": {"$in": games}, "team_id": team_id}))
        return {"gp": mine.get("gp"), "stats": out, "form": form, "source": "box scores",
                "first_date": dates[0] if dates else None, "last_date": dates[-1] if dates else None}
    all_stats = list(db.team_stats.find({}, {"_id": 0}))
    mine = next((t for t in all_stats if t["team_id"] == team_id), None)
    if not mine:
        return None
    return {"gp": mine.get("gp"), "stats": _ranked(mine, all_stats), "form": "season", "source": "official"}


def _ranked(mine, all_stats):
    out = []
    for key, label, help_text, higher_better in TEAM_STATS:
        values = [t.get(key) for t in all_stats if t.get(key) is not None]
        value = mine.get(key)
        rank = None
        if value is not None:
            better = [v for v in values if (v > value if higher_better else v < value)]
            rank = len(better) + 1
        out.append({"key": key, "label": label, "help": help_text, "value": value,
                    "rank": rank, "of": len(values)})
    return out


def team_overview(team_id, form="season"):
    return {
        "team": get_team(team_id),
        "standing": standing(team_id),
        "season": current_season(),
        "data_as_of": data_as_of(),
        "form": form,
        "team_stats": team_stats_with_ranks(team_id, form),
    }
