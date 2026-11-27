"""Game endpoints: the context header for a matchup, and box scores."""

import re

from flask import Blueprint, jsonify, request

from app.db import db
from app.routes.errors import error, parse_team_id
from app.services.boxscore import box_score
from app.services.context import game_context, get_team
from app.services.matchups import matchups
from app.services.series import guarded_in_game, series_history
from app.services import preview

games_bp = Blueprint("games", __name__)


@games_bp.get("/api/games/context")
def context():
    us_id, err = parse_team_id(request.args.get("us"), "\"us\" team id")
    if err:
        return err
    them_id, err = parse_team_id(request.args.get("them"), "\"them\" team id")
    if err:
        return err
    if us_id == them_id:
        return error("Pick two different teams.", 400)
    for tid in (us_id, them_id):
        if not get_team(tid):
            return error(f"No team has the id {tid}.", 404)
    return jsonify(game_context(us_id, them_id))


def two_teams(args):
    """(us_id, them_id, error response) from ?us=&them=."""
    us_id, err = parse_team_id(args.get("us"), "\"us\" team id")
    if err:
        return None, None, err
    them_id, err = parse_team_id(args.get("them"), "\"them\" team id")
    if err:
        return None, None, err
    if us_id == them_id:
        return None, None, error("Pick two different teams.", 400)
    for tid in (us_id, them_id):
        if not get_team(tid):
            return None, None, error(f"No team has the id {tid}.", 404)
    return us_id, them_id, None


@games_bp.get("/api/games/series")
def series():
    """Every meeting this season and last (playoffs and play-in included)."""
    us_id, them_id, err = two_teams(request.args)
    if err:
        return err
    return jsonify(series_history(us_id, them_id))


@games_bp.get("/api/games/<game_id>/guarded")
def guarded(game_id):
    """Who guarded whom in one game, from the "us" team's point of view."""
    if not re.fullmatch(r"\d{10}", game_id):
        return error("A game id is 10 digits, such as 0022600245.", 400)
    us_id, err = parse_team_id(request.args.get("us"), "\"us\" team id")
    if err:
        return err
    result, problem = guarded_in_game(game_id, us_id)
    return error(*problem) if problem else jsonify(result)


@games_bp.get("/api/rotations")
def rotation_scouting():
    """Their most-used five-man lineups with tags, and our counters.
    us_status / them_status: statuses set in the lineup editor, as
    <pid>:<status>,... (otherwise the official injury report)."""
    from app.services.onepager import parse_status_param
    from app.services.rotations import rotations
    us_id, them_id, err = two_teams(request.args)
    if err:
        return err
    us_over, message = parse_status_param(request.args.get("us_status"))
    if message:
        return error(message, 400)
    them_over, message = parse_status_param(request.args.get("them_status"))
    if message:
        return error(message, 400)
    return jsonify(rotations(us_id, them_id, us_over, them_over))


@games_bp.get("/api/games/<game_id>/projection")
def projection(game_id):
    """The saved projection (with the result once played), or for an upcoming
    game the current one."""
    if not re.fullmatch(r"\d{10}", game_id):
        return error("A game id is 10 digits, such as 0022600245.", 400)
    game = db.schedule.find_one({"_id": game_id}, {"played": 1})
    if not game:
        return error(f"No game has the id {game_id}.", 404)
    saved = db.projections.find_one({"_id": game_id}, {"_id": 0})
    current = None if game.get("played") else preview.project(game_id)
    return jsonify({"game_id": game_id, "played": bool(game.get("played")), "saved": saved, "current": current})


@games_bp.get("/api/projections/record")
def projection_record():
    """Running record of saved projections, plus the backtest."""
    team = request.args.get("team")
    tid = None
    if team is not None:
        tid, err = parse_team_id(team)
        if err:
            return err
    return jsonify(preview.record(tid))


@games_bp.get("/api/games/<game_id>/boxscore")
def boxscore(game_id):
    # NBA game ids are 10 digits, such as 0022600245.
    if not re.fullmatch(r"\d{10}", game_id):
        return error("A game id is 10 digits, such as 0022600245.", 400)
    game = db.schedule.find_one({"_id": game_id})
    if not game:
        return error(f"No game has the id {game_id}.", 404)
    if not game.get("played"):
        return error("This game has not been played yet, so there is no box score.", 404)
    return jsonify(box_score(game))


@games_bp.post("/api/matchups")
def suggest_matchups():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error("Send a JSON body with \"us\" and \"them\" team ids.", 400)
    us_id, err = parse_team_id(body.get("us"), "\"us\" team id")
    if err:
        return err
    them_id, err = parse_team_id(body.get("them"), "\"them\" team id")
    if err:
        return err
    if us_id == them_id:
        return error("Pick two different teams.", 400)
    for tid in (us_id, them_id):
        if not get_team(tid):
            return error(f"No team has the id {tid}.", 404)
    result, message = matchups(us_id, them_id, body.get("us_lineup"), body.get("them_lineup"),
                               body.get("us_overrides"), body.get("them_overrides"))
    if message:
        return error(message, 400)
    return jsonify(result)
