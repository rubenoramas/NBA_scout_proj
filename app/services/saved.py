"""Saved lineups and reports: the user-written data, kept in MongoDB.

This is where the app does create, read, update and delete (CRUD) in
MongoDB. Seed collections are rebuilt by the loader; these two are written
only by users, and the loader never touches them.

- Ids: MongoDB gives each new document a unique ObjectId in `_id`. The API
  turns it into a 24-character text `id`, and turns text back into an
  ObjectId to look a document up.
- A report keeps a snapshot of the matchup result at the moment it was
  saved, so it reads the same later even after the data is refreshed.
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.db import db
from app.services.context import data_as_of, get_team
from app.services.matchups import matchups, parse_overrides, validate_lineup, out_players

NAME_MAX = 60
TITLE_MAX = 120
NOTES_MAX = 10000


def now():
    return datetime.now(timezone.utc)


def parse_id(raw):
    """Text id -> ObjectId, or None if it is not a valid 24-character id."""
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z") if isinstance(dt, datetime) else dt


def overrides_list(over):
    return [{"player_id": pid, "status": st} for pid, st in sorted(over.items())]


# ---- Lineups ---------------------------------------------------------------

def lineup_out(doc):
    """A MongoDB document -> what the API sends back."""
    return {
        "id": str(doc["_id"]), "team_id": doc["team_id"], "name": doc["name"],
        "player_ids": doc["player_ids"], "overrides": doc.get("overrides", []),
        "created_at": iso(doc.get("created_at")), "updated_at": iso(doc.get("updated_at")),
    }


def check_name(name):
    if not isinstance(name, str) or not name.strip():
        return None, "Give the lineup a name."
    name = name.strip()
    if len(name) > NAME_MAX:
        return None, f"A lineup name can be at most {NAME_MAX} characters."
    return name, None


def check_lineup_fields(team_id, player_ids, raw_overrides):
    """Validate five players and overrides for one team. Returns
    (player_ids, overrides dict, error)."""
    over, err = parse_overrides(raw_overrides, "lineup")
    if err:
        return None, None, err
    on_team = {d["_id"] for d in db.players.find({"team_id": team_id}, {"_id": 1})}
    stray = [pid for pid in over if pid not in on_team]
    if stray:
        return None, None, f"Player {stray[0]} in the overrides is not on this team."
    ids, err = validate_lineup(team_id, player_ids, out_players(team_id, over))
    if err:
        return None, None, err
    return ids, over, None


def create_lineup(body):
    try:
        team_id = int(body.get("team_id"))
    except (TypeError, ValueError):
        return None, ("The team id is missing or not a number.", 400)
    if not get_team(team_id):
        return None, (f"No team has the id {team_id}.", 404)
    name, err = check_name(body.get("name"))
    if err:
        return None, (err, 400)
    ids, over, err = check_lineup_fields(team_id, body.get("player_ids"), body.get("overrides"))
    if err:
        return None, (err, 400)
    stamp = now()
    doc = {"team_id": team_id, "name": name, "player_ids": ids, "overrides": overrides_list(over),
           "created_at": stamp, "updated_at": stamp}
    # insert_one stores the document; MongoDB fills in a new ObjectId as _id.
    result = db.lineups.insert_one(doc)
    doc["_id"] = result.inserted_id
    return lineup_out(doc), None


def list_lineups(team_id=None):
    query = {"team_id": team_id} if team_id is not None else {}
    return [lineup_out(d) for d in db.lineups.find(query).sort("updated_at", -1)]


def get_lineup(oid):
    doc = db.lineups.find_one({"_id": oid})
    return lineup_out(doc) if doc else None


def update_lineup(oid, body):
    doc = db.lineups.find_one({"_id": oid})
    if not doc:
        return None, ("No saved lineup has this id.", 404)
    changes = {}
    if "name" in body:
        name, err = check_name(body.get("name"))
        if err:
            return None, (err, 400)
        changes["name"] = name
    if "player_ids" in body or "overrides" in body:
        ids, over, err = check_lineup_fields(
            doc["team_id"], body.get("player_ids", doc["player_ids"]),
            body.get("overrides", doc.get("overrides", [])))
        if err:
            return None, (err, 400)
        changes.update(player_ids=ids, overrides=overrides_list(over))
    if not changes:
        return None, ("Nothing to change: send a name, player_ids or overrides.", 400)
    changes["updated_at"] = now()
    # $set changes only the listed fields and leaves the rest as they are.
    db.lineups.update_one({"_id": oid}, {"$set": changes})
    return get_lineup(oid), None


def delete_lineup(oid):
    return db.lineups.delete_one({"_id": oid}).deleted_count == 1


# ---- Reports ---------------------------------------------------------------

def report_out(doc, full=True):
    out = {
        "id": str(doc["_id"]), "us_team_id": doc["us_team_id"], "them_team_id": doc["them_team_id"],
        "us_abbr": doc.get("us_abbr"), "them_abbr": doc.get("them_abbr"),
        "game_id": doc.get("game_id"), "game_date": doc.get("game_date"),
        "title": doc["title"], "created_at": iso(doc.get("created_at")), "updated_at": iso(doc.get("updated_at")),
        "data_as_of": doc.get("data_as_of"),
    }
    if full:
        out.update(notes=doc.get("notes", ""), us_lineup=doc.get("us_lineup"), them_lineup=doc.get("them_lineup"),
                   matchup_snapshot=doc.get("matchup_snapshot"), ai_text=doc.get("ai_text"))
    return out


def check_title_notes(body, required_title):
    changes = {}
    if "title" in body or required_title:
        title = body.get("title")
        if not isinstance(title, str) or not title.strip():
            return None, "Give the report a title."
        if len(title.strip()) > TITLE_MAX:
            return None, f"A title can be at most {TITLE_MAX} characters."
        changes["title"] = title.strip()
    if "notes" in body:
        notes = body.get("notes") or ""
        if not isinstance(notes, str):
            return None, "Notes must be text."
        if len(notes) > NOTES_MAX:
            return None, f"Notes can be at most {NOTES_MAX} characters."
        changes["notes"] = notes
    return changes, None


def create_report(body):
    try:
        us_id, them_id = int(body.get("us_team_id")), int(body.get("them_team_id"))
    except (TypeError, ValueError):
        return None, ("Both team ids are needed (us_team_id and them_team_id).", 400)
    if us_id == them_id:
        return None, ("Pick two different teams.", 400)
    teams = {tid: get_team(tid) for tid in (us_id, them_id)}
    for tid, team in teams.items():
        if not team:
            return None, (f"No team has the id {tid}.", 404)
    fields, err = check_title_notes(body, required_title=True)
    if err:
        return None, (err, 400)
    us_l = body.get("us_lineup") or {}
    them_l = body.get("them_lineup") or {}
    # The server reruns the matchup model on the lineups it is given, so the
    # snapshot always matches them and cannot be faked by the browser.
    snapshot, err = matchups(us_id, them_id, us_l.get("player_ids"), them_l.get("player_ids"),
                             us_l.get("overrides"), them_l.get("overrides"))
    if err:
        return None, (err, 400)
    game_id = body.get("game_id")
    game = db.schedule.find_one({"_id": game_id}) if game_id else None
    stamp = now()
    doc = {
        "us_team_id": us_id, "them_team_id": them_id,
        "us_abbr": teams[us_id]["abbreviation"], "them_abbr": teams[them_id]["abbreviation"],
        "game_id": game_id if game else None, "game_date": game["game_date"] if game else None,
        "title": fields["title"], "notes": fields.get("notes", ""),
        "us_lineup": {"player_ids": [p["player_id"] for p in snapshot["us_lineup"]], "overrides": snapshot["overrides"]["us"]},
        "them_lineup": {"player_ids": [p["player_id"] for p in snapshot["them_lineup"]], "overrides": snapshot["overrides"]["them"]},
        "matchup_snapshot": snapshot,
        "data_as_of": data_as_of(),
        "ai_text": None,
        "created_at": stamp, "updated_at": stamp,
    }
    result = db.reports.insert_one(doc)
    doc["_id"] = result.inserted_id
    return report_out(doc), None


def list_reports():
    # Newest first; the list leaves out the big snapshot.
    return [report_out(d, full=False) for d in db.reports.find({}, {"matchup_snapshot": 0}).sort("created_at", -1)]


def get_report(oid):
    doc = db.reports.find_one({"_id": oid})
    return report_out(doc) if doc else None


def update_report(oid, body):
    if not db.reports.find_one({"_id": oid}, {"_id": 1}):
        return None, ("No saved report has this id.", 404)
    locked = [k for k in ("us_lineup", "them_lineup", "matchup_snapshot", "us_team_id", "them_team_id") if k in body]
    if locked:
        return None, (f"{locked[0]} cannot be changed after saving. Save a new report instead.", 400)
    changes, err = check_title_notes(body, required_title=False)
    if err:
        return None, (err, 400)
    if "ai_text" in body:
        changes["ai_text"] = body["ai_text"]
    if not changes:
        return None, ("Nothing to change: send a title or notes.", 400)
    changes["updated_at"] = now()
    db.reports.update_one({"_id": oid}, {"$set": changes})
    return get_report(oid), None


def delete_report(oid):
    return db.reports.delete_one({"_id": oid}).deleted_count == 1
