"""Team endpoints: the team list and one team's schedule."""

from flask import Blueprint, jsonify

from app.db import db
from app.routes.errors import error, parse_team_id
from app.services.context import current_season, data_as_of, get_team, pulled_at, team_overview, team_schedule

teams_bp = Blueprint("teams", __name__)


@teams_bp.get("/api/teams")
def list_teams():
    teams = list(db.teams.find({}, {"_id": 0}).sort("full_name", 1))
    return jsonify({"teams": teams, "data_as_of": data_as_of(), "pulled_at": pulled_at()})


@teams_bp.get("/api/teams/<team_id>/schedule")
def schedule(team_id):
    tid, err = parse_team_id(team_id)
    if err:
        return err
    team = get_team(tid)
    if not team:
        return error(f"No team has the id {tid}.", 404)
    season = current_season()
    return jsonify({
        "team": team,
        "season": season,
        "data_as_of": data_as_of(),
        "pulled_at": pulled_at(),
        "games": team_schedule(tid, season),
    })


@teams_bp.get("/api/teams/<team_id>")
def team(team_id):
    tid, err = parse_team_id(team_id)
    if err:
        return err
    if not get_team(tid):
        return error(f"No team has the id {tid}.", 404)
    return jsonify(team_overview(tid))
