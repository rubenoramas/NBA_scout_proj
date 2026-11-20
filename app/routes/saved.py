"""REST endpoints for saved lineups and reports (create, read, update, delete).

    POST   /api/lineups          create        201
    GET    /api/lineups?team=id  list          200
    GET    /api/lineups/<id>     read one      200 or 404
    PUT    /api/lineups/<id>     update        200, 400 or 404
    DELETE /api/lineups/<id>     delete        204 or 404
    (the same five for /api/reports)
"""

from flask import Blueprint, jsonify, request

from app.report.facts import build_facts
from app.report.writer import ReportError, generate
from app.routes.errors import error, parse_team_id
from app.services import saved
from app.services.context import get_team

saved_bp = Blueprint("saved", __name__)


def json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def with_id(raw):
    oid = saved.parse_id(raw)
    if oid is None:
        return None, error("That id is not valid. Ids are 24 characters, letters a to f and digits.", 400)
    return oid, None


# ---- Lineups ---------------------------------------------------------------

@saved_bp.post("/api/lineups")
def create_lineup():
    body = json_body()
    if body is None:
        return error("Send the lineup as JSON.", 400)
    out, problem = saved.create_lineup(body)
    if problem:
        return error(*problem)
    return jsonify(out), 201


@saved_bp.get("/api/lineups")
def list_lineups():
    team = request.args.get("team")
    if team is not None:
        tid, err = parse_team_id(team)
        if err:
            return err
        return jsonify({"lineups": saved.list_lineups(tid)})
    return jsonify({"lineups": saved.list_lineups()})


@saved_bp.get("/api/lineups/<lineup_id>")
def get_lineup(lineup_id):
    oid, err = with_id(lineup_id)
    if err:
        return err
    out = saved.get_lineup(oid)
    return jsonify(out) if out else error("No saved lineup has this id.", 404)


@saved_bp.put("/api/lineups/<lineup_id>")
def update_lineup(lineup_id):
    oid, err = with_id(lineup_id)
    if err:
        return err
    body = json_body()
    if body is None:
        return error("Send the changes as JSON.", 400)
    out, problem = saved.update_lineup(oid, body)
    return error(*problem) if problem else jsonify(out)


@saved_bp.delete("/api/lineups/<lineup_id>")
def delete_lineup(lineup_id):
    oid, err = with_id(lineup_id)
    if err:
        return err
    return ("", 204) if saved.delete_lineup(oid) else error("No saved lineup has this id.", 404)


# ---- Reports ---------------------------------------------------------------

@saved_bp.post("/api/reports")
def create_report():
    body = json_body()
    if body is None:
        return error("Send the report as JSON.", 400)
    out, problem = saved.create_report(body)
    if problem:
        return error(*problem)
    return jsonify(out), 201


@saved_bp.get("/api/reports")
def list_reports():
    return jsonify({"reports": saved.list_reports()})


@saved_bp.get("/api/reports/<report_id>")
def get_report(report_id):
    oid, err = with_id(report_id)
    if err:
        return err
    out = saved.get_report(oid)
    return jsonify(out) if out else error("No saved report has this id. It may have been deleted.", 404)


@saved_bp.put("/api/reports/<report_id>")
def update_report(report_id):
    oid, err = with_id(report_id)
    if err:
        return err
    body = json_body()
    if body is None:
        return error("Send the changes as JSON.", 400)
    out, problem = saved.update_report(oid, body)
    return error(*problem) if problem else jsonify(out)


@saved_bp.delete("/api/reports/<report_id>")
def delete_report(report_id):
    oid, err = with_id(report_id)
    if err:
        return err
    return ("", 204) if saved.delete_report(oid) else error("No saved report has this id.", 404)


# ---- AI draft --------------------------------------------------------------

@saved_bp.post("/api/reports/draft")
def draft_report():
    """Build the facts, ask Claude for the four sections, check the numbers.
    Nothing is saved; the browser saves the (possibly edited) draft later."""
    body = json_body()
    if body is None:
        return error("Send the teams and lineups as JSON.", 400)
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
    built, message = build_facts(us_id, them_id, body.get("us_lineup"), body.get("them_lineup"),
                                 body.get("us_overrides"), body.get("them_overrides"))
    if message:
        return error(message, 400)
    try:
        draft = generate(built["facts"])
    except ReportError as err:
        return jsonify({"error": err.message, "facts": built["facts"]}), err.status
    draft["facts"] = built["facts"]
    return jsonify(draft)
