"""Refresh jobs for the "Refresh data" button.

The R pulls run in the optional refresher container (refresher/server.py).
This module keeps the job in MongoDB, so every gunicorn worker sees the
same job, asks the refresher for progress, and when the pulls finish it
reloads MongoDB with the existing loader and records what changed.

Job states: pulling -> reloading -> done, or failed at any point.
Only one job can be active: a partial unique index on "active" rejects a
second active job, even if two people click at the same moment.
"""

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import loader
from app.db import db

REFRESHER_URL = os.environ.get("REFRESHER_URL", "http://refresher:8080")
HOW_TO_START = ("The refresher is not running. Start it with: docker compose --profile refresh up "
                "(or run ./refresh.sh on your laptop).")
RELOAD_STUCK_AFTER = timedelta(minutes=15)
RELOAD_IN_THREAD = True  # tests set this to False to reload right away

# Collections people write. A reload never touches these, so they are not
# part of the "what changed" summary.
USER_COLLECTIONS = {"lineups", "reports", "refresh_jobs", "meta"}


def now():
    return datetime.now(timezone.utc)


# ---- Talking to the refresher container ------------------------------------

def _call(method, path, payload=None, timeout=3):
    """Returns (status, body); status None when the refresher is unreachable."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(REFRESHER_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except ValueError:
            return err.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return None, None


def refresher_up():
    status, _ = _call("GET", "/health", timeout=1.5)
    return status == 200


def refresher_start(job_id):
    return _call("POST", "/jobs", {"job_id": job_id})


def refresher_job(job_id):
    return _call("GET", f"/jobs/{job_id}")


# ---- Jobs ------------------------------------------------------------------

def public(job):
    if not job:
        return None
    out = {k: v for k, v in job.items() if k not in ("_id", "active")}
    out["job_id"] = str(job["_id"])
    for k in ("created_at", "updated_at", "finished_at", "reload_started_at"):
        if isinstance(out.get(k), datetime):
            out[k] = out[k].replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return out


def _finish(job_id, state, **fields):
    db.refresh_jobs.update_one({"_id": job_id}, {"$set": {"state": state, "updated_at": now(), "finished_at": now(), **fields},
                                                 "$unset": {"active": ""}})


def active_job():
    return db.refresh_jobs.find_one({"active": True})


def start_job():
    """Returns (job, None) or (None, (message, status, extra))."""
    if not refresher_up():
        return None, (HOW_TO_START, 503, {})
    job = {"_id": ObjectId(), "active": True, "state": "pulling", "step": "Starting...",
           "error": None, "changes": None, "created_at": now(), "updated_at": now()}
    try:
        db.refresh_jobs.insert_one(job)
    except DuplicateKeyError:
        running = active_job()
        return None, ("A refresh is already running.", 409, {"job_id": str(running["_id"]) if running else None})
    status, body = refresher_start(str(job["_id"]))
    if status != 202:
        message = (body or {}).get("error") if status else None
        _finish(job["_id"], "failed", error=message or HOW_TO_START)
        return None, (message or HOW_TO_START, 409 if status == 409 else 503, {})
    return public(job), None


def get_job(job_id):
    """Returns the job, moving it along: refresher progress, then the reload."""
    job = db.refresh_jobs.find_one({"_id": job_id})
    if not job:
        return None
    if job["state"] == "pulling":
        status, body = refresher_job(str(job_id))
        if status is None:
            # The refresher stopped answering. Keep the job; the page keeps polling.
            job["step_note"] = "Waiting for the refresher to answer..."
        elif status == 404:
            _finish(job_id, "failed", error="The refresher restarted during the refresh, so the pulls stopped. Try again.")
        elif body.get("state") == "running":
            db.refresh_jobs.update_one({"_id": job_id}, {"$set": {"step": body.get("step"), "updated_at": now()}})
        elif body.get("state") == "failed":
            step = (body.get("step") or "A pull").rstrip(".")
            _finish(job_id, "failed", log_tail=body.get("log_tail"),
                    error=f"{step} failed: {(body.get('error') or 'no error message').rstrip('.')}. "
                          "The seed files may be partly updated. Fix the problem and try again.")
        elif body.get("state") == "done":
            # Exactly one request claims the reload, whichever worker it lands on.
            claimed = db.refresh_jobs.find_one_and_update(
                {"_id": job_id, "state": "pulling"},
                {"$set": {"state": "reloading", "step": "Reloading database...", "reload_started_at": now(), "updated_at": now()}},
                return_document=ReturnDocument.AFTER)
            if claimed:
                start_reload(job_id)
    elif job["state"] == "reloading" and job.get("reload_started_at"):
        started = job["reload_started_at"].replace(tzinfo=timezone.utc)
        if now() - started > RELOAD_STUCK_AFTER:
            _finish(job_id, "failed", error="Reloading the database did not finish. Restart the app and try again.")
    fresh = db.refresh_jobs.find_one({"_id": job_id})
    out = public(fresh)
    if job.get("step_note") and out["state"] == "pulling":
        out["step_note"] = job["step_note"]
    return out


def start_reload(job_id):
    if RELOAD_IN_THREAD:
        threading.Thread(target=reload_database, args=(job_id,), daemon=True).start()
    else:
        reload_database(job_id)


def seed_counts():
    names = [n for n in db.list_collection_names() if n not in USER_COLLECTIONS and not n.startswith("tmp_")]
    return {n: db[n].estimated_document_count() for n in names}


def freshness():
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return {"data_as_of": meta.get("data_as_of"), "pulled_at": meta.get("pulled_at")}


def reload_database(job_id):
    """Run the existing loader, then record the row-count changes."""
    try:
        before, was = seed_counts(), freshness()
        loader.main()
        after, now_fresh = seed_counts(), freshness()
        changes = [{"collection": n, "before": before.get(n, 0), "after": after.get(n, 0),
                    "change": after.get(n, 0) - before.get(n, 0)}
                   for n in sorted(set(before) | set(after)) if before.get(n, 0) != after.get(n, 0)]
        _finish(job_id, "done", step="Done", changes=changes, freshness_before=was, freshness=now_fresh)
    except Exception as err:  # noqa: BLE001 - report any failure to the page
        _finish(job_id, "failed", error=f"Reloading the database failed: {err}. The seed files are updated; "
                                        "restart the app to load them.")
