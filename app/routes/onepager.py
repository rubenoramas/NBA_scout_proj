"""Player one-pager endpoints.

    GET  /api/players/<id>/onepager?vs=<team id>        page data, plus the cached
                                                        "How to guard him" text if any.
                                                        Never calls the AI service.
    POST /api/players/<id>/onepager/note?vs=<team id>   the text: from the cache, or
                                                        written by Claude and cached.
"""

from flask import Blueprint, jsonify, request

from app.report import config
from app.report.onepager import cached_note, get_note
from app.report.writer import NO_KEY_MESSAGE, ReportError
from app.routes.errors import error, parse_team_id
from app.routes.players import parse_player_id
from app.services.onepager import build_page

onepager_bp = Blueprint("onepager", __name__)


def page_or_error(player_id):
    pid, err = parse_player_id(player_id)
    if err:
        return None, err
    vs, err = parse_team_id(request.args.get("vs"), "\"vs\" team id (the team that will guard him)")
    if err:
        return None, err
    page, problem = build_page(pid, vs)
    if problem:
        return None, error(*problem)
    return page, None


@onepager_bp.get("/api/players/<player_id>/onepager")
def onepager(player_id):
    page, err = page_or_error(player_id)
    if err:
        return err
    key_set = config.api_key_set()
    page["note"] = {"key_set": key_set, "cached": cached_note(page),
                    "no_key_message": None if key_set else NO_KEY_MESSAGE}
    return jsonify(page)


@onepager_bp.post("/api/players/<player_id>/onepager/note")
def onepager_note(player_id):
    page, err = page_or_error(player_id)
    if err:
        return err
    try:
        note, cached = get_note(page)
    except ReportError as e:
        return error(e.message, e.status)
    return jsonify({"note": note, "cached": cached}), 200 if cached else 201
