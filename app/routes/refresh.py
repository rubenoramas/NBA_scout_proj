"""Endpoints for the "Refresh data" button.

    GET  /api/refresh/status   is the refresher running, and is a job active
    POST /api/refresh          start a job: 202 {job_id}; 409 if one is running;
                               503 if the refresher is not running
    GET  /api/refresh/<id>     the job's state, current step, and when done,
                               what changed
"""

from flask import Blueprint, jsonify

from app.routes.errors import error
from app.services import refresh, saved

refresh_bp = Blueprint("refresh", __name__)


@refresh_bp.get("/api/refresh/status")
def refresh_status():
    up = refresh.refresher_up()
    return jsonify({"refresher": up, "how_to_start": None if up else refresh.HOW_TO_START,
                    "job": refresh.public(refresh.active_job())})


@refresh_bp.post("/api/refresh")
def start_refresh():
    job, problem = refresh.start_job()
    if problem:
        message, status, extra = problem
        return jsonify({"error": message, **extra}), status
    return jsonify(job), 202


@refresh_bp.get("/api/refresh/<job_id>")
def refresh_job(job_id):
    oid = saved.parse_id(job_id)
    if oid is None:
        return error("That job id is not valid.", 400)
    job = refresh.get_job(oid)
    return jsonify(job) if job else error("No refresh job has this id.", 404)
