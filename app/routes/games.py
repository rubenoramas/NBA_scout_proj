"""Game endpoints: the context header for a matchup, and box scores."""

import re

from flask import Blueprint, jsonify, request

from app.db import db
from app.routes.errors import error, parse_team_id
from app.services.boxscore import box_score
from app.services.context import game_context, get_team
from app.services.matchups import matchups

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
