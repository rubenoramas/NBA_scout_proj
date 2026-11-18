"""Box scores built from player game log lines.

Every advanced stat is computed here, once, so the page and the tests use
the same formulas. Each formula is written out next to its function and in
the "How these are calculated" note on the box score page.
"""

from app.db import db
from app.services.context import get_team

# The counting stats summed into team totals.
COUNT_FIELDS = [
    "min", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
    "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf",
]


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else None


def pct(numerator, denominator):
    """A shooting percentage as 0 to 1, or None with no attempts."""
    return safe_div(numerator, denominator)


def true_shooting(line):
    # TS% = PTS / (2 x (FGA + 0.44 x FTA))
    return safe_div(line["pts"], 2 * (line["fga"] + 0.44 * line["fta"]))


def effective_fg(line):
    # eFG% = (FGM + 0.5 x 3PM) / FGA
    return safe_div(line["fgm"] + 0.5 * line["fg3m"], line["fga"])


def game_score(line):
    # Game Score (John Hollinger) = PTS + 0.4 FGM - 0.7 FGA - 0.4 (FTA - FTM)
    #   + 0.7 OREB + 0.3 DREB + STL + 0.7 AST + 0.7 BLK - 0.4 PF - TOV
    return (
        line["pts"] + 0.4 * line["fgm"] - 0.7 * line["fga"] - 0.4 * (line["fta"] - line["ftm"])
        + 0.7 * line["oreb"] + 0.3 * line["dreb"] + line["stl"] + 0.7 * line["ast"]
        + 0.7 * line["blk"] - 0.4 * line["pf"] - line["tov"]
    )


def usage(line, team):
    # USG% = 100 x (FGA + 0.44 x FTA + TOV) x (team MIN / 5)
    #        / (MIN x (team FGA + 0.44 x team FTA + team TOV))
    # Minutes in the data are whole numbers, so this is slightly rounded.
    plays = line["fga"] + 0.44 * line["fta"] + line["tov"]
    team_plays = team["fga"] + 0.44 * team["fta"] + team["tov"]
    value = safe_div(plays * (team["min"] / 5), line["min"] * team_plays)
    return None if value is None else 100 * value


def assist_to_turnover(line):
    # AST/TOV = AST / TOV, left empty when TOV is 0
    return safe_div(line["ast"], line["tov"])


def four_factors(team, opponent):
    """Dean Oliver's four factors for one team in one game."""
    return {
        # eFG% = (FGM + 0.5 x 3PM) / FGA
        "efg_pct": effective_fg(team),
        # TOV% = TOV / (FGA + 0.44 x FTA + TOV)
        "tov_pct": safe_div(team["tov"], team["fga"] + 0.44 * team["fta"] + team["tov"]),
        # OREB% = OREB / (OREB + opponent DREB). Player rebounds only:
        # team rebounds are not in the player lines.
        "oreb_pct": safe_div(team["oreb"], team["oreb"] + opponent["dreb"]),
        # FT rate = FTA / FGA
        "ft_rate": safe_div(team["fta"], team["fga"]),
    }


def clean_line(doc):
    """Make every counting stat a number (missing becomes 0)."""
    line = {key: doc.get(key) or 0 for key in COUNT_FIELDS}
    line.update({
        "player_id": doc["player_id"],
        "player_name": doc.get("player_name"),
        "starter": doc.get("starter"),
        "plus_minus": doc.get("plus_minus"),
    })
    return line


def team_totals(lines):
    totals = {key: sum(line[key] for line in lines) for key in COUNT_FIELDS}
    totals["fg_pct"] = pct(totals["fgm"], totals["fga"])
    totals["fg3_pct"] = pct(totals["fg3m"], totals["fg3a"])
    totals["ft_pct"] = pct(totals["ftm"], totals["fta"])
    totals["ts_pct"] = true_shooting(totals)
    totals["efg_pct"] = effective_fg(totals)
    totals["ast_tov"] = assist_to_turnover(totals)
    return totals


def add_line_stats(line, totals):
    line["fg_pct"] = pct(line["fgm"], line["fga"])
    line["fg3_pct"] = pct(line["fg3m"], line["fg3a"])
    line["ft_pct"] = pct(line["ftm"], line["fta"])
    line["ts_pct"] = true_shooting(line)
    line["efg_pct"] = effective_fg(line)
    line["usg_pct"] = usage(line, totals) if line["min"] else None
    line["game_score"] = round(game_score(line), 1)
    line["ast_tov"] = assist_to_turnover(line)
    return line


def team_side(team_id, abbr, pts, home, lines):
    totals = team_totals(lines) if lines else None
    lines = [add_line_stats(line, totals) for line in lines] if lines else []
    # Starters first, then everyone else, each group by points.
    lines.sort(key=lambda l: (not l["starter"], -l["pts"], -l["min"]))
    team = get_team(team_id) or {"team_id": team_id, "abbreviation": abbr}
    return {"team": team, "home": home, "pts": pts, "players": lines, "totals": totals}


def box_score(game):
    """Build the box score for a played schedule document."""
    docs = list(db.game_logs.find({"game_id": game["game_id"]}))
    by_team = {}
    for doc in docs:
        by_team.setdefault(doc["team_id"], []).append(clean_line(doc))

    home = team_side(game["home_team_id"], game["home_abbr"], game["home_pts"], True,
                     by_team.get(game["home_team_id"], []))
    away = team_side(game["away_team_id"], game["away_abbr"], game["away_pts"], False,
                     by_team.get(game["away_team_id"], []))
    for side, other in ((home, away), (away, home)):
        side["four_factors"] = (
            four_factors(side["totals"], other["totals"]) if side["totals"] and other["totals"] else None
        )
    starters_known = any(line["starter"] is not None for side in (home, away) for line in side["players"])

    return {
        "game": {
            "game_id": game["game_id"],
            "date": game["game_date"],
            "season": game.get("season"),
            "season_type": game.get("season_type"),
            "venue": game["home_abbr"],
        },
        "away": away,
        "home": home,
        "has_lines": bool(docs),
        "starters_known": starters_known,
    }
