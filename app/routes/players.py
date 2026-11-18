"""Roster, player card and shot endpoints."""

from flask import Blueprint, jsonify, request

from app.db import db
from app.routes.errors import error, parse_team_id
from app.services.context import get_team
from app.services.players import ZONE_LABELS, ZONES, player_card, player_shots, roster, shot_types_for

players_bp = Blueprint("players", __name__)


def parse_player_id(raw):
    try:
        return int(raw), None
    except ValueError:
        return None, error("The player id must be a number, such as 1628369.", 400)


@players_bp.get("/api/teams/<team_id>/roster")
def team_roster(team_id):
    tid, err = parse_team_id(team_id)
    if err:
        return err
    team = get_team(tid)
    if not team:
        return error(f"No team has the id {tid}.", 404)
    return jsonify({"team": team, "players": roster(tid)})


@players_bp.get("/api/players/<player_id>")
def card(player_id):
    pid, err = parse_player_id(player_id)
    if err:
        return err
    data = player_card(pid)
    if not data:
        return error(f"No player has the id {pid}.", 404)
    return jsonify(data)


@players_bp.get("/api/players/<player_id>/shots")
def shots(player_id):
    pid, err = parse_player_id(player_id)
    if err:
        return err
    if not db.players.find_one({"_id": pid}, {"_id": 1}):
        return error(f"No player has the id {pid}.", 404)
    zone = request.args.get("zone") or None
    shot_type = request.args.get("type") or None
    if zone and zone not in ZONES:
        return error(f"Unknown zone \"{zone}\". Use one of: {', '.join(ZONES)}.", 400)
    types = shot_types_for(pid)
    if shot_type and shot_type not in types:
        return error(f"He has no shots of type \"{shot_type}\" this season.", 400)
    found = player_shots(pid, shot_type, zone)
    return jsonify({
        "player_id": pid,
        "filters": {"type": shot_type, "zone": zone},
        "shot_types": types,
        "zones": [{"zone": z, "label": ZONE_LABELS[z]} for z in ZONES],
        "count": len(found),
        "made": sum(1 for s in found if s["made"]),
        "shots": found,
    })
