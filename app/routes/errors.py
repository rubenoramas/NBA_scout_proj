"""Shared helpers for JSON errors with plain-language messages."""

from flask import jsonify


def error(message, status):
    return jsonify({"error": message}), status


def parse_team_id(raw, name="team id"):
    """Turn a URL value into an int team id, or return (None, error response)."""
    if raw is None or str(raw).strip() == "":
        return None, error(f"The {name} is missing.", 400)
    try:
        return int(raw), None
    except ValueError:
        return None, error(f"The {name} must be a number, such as 1610612738.", 400)
