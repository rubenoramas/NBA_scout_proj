"""Game endpoints: the context header for one matchup."""

from flask import Blueprint, jsonify, request

from app.routes.errors import error, parse_team_id
from app.services.context import game_context, get_team

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
