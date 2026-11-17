"""GET /api/health: says whether the API can reach MongoDB."""

import os

from flask import Blueprint, jsonify

from app.db import mongo_is_reachable

health_bp = Blueprint("health", __name__)


def ai_key_is_set():
    """True when ANTHROPIC_API_KEY holds something other than the sample value.

    The key itself is never returned or logged.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return bool(key) and key != "your-key-here"


@health_bp.get("/api/health")
def health():
    mongo_ok = mongo_is_reachable()
    body = {
        "api": "ok",
        "mongo": "ok" if mongo_ok else "unreachable",
        "ai_key_set": ai_key_is_set(),
    }
    if not mongo_ok:
        body["message"] = "The API is running but cannot reach the database."
    return jsonify(body), 200 if mongo_ok else 503
