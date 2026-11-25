"""Player names for any NBA id, including players no longer on a roster.

The players collection holds current rosters only. A player who left the
league (or has not played this season) still has his name in last season's
player stats and in the game logs, so those are the fallbacks.
"""

from app.db import db


def player_names(ids):
    """{player_id: name} for every id that has a name anywhere."""
    ids = {i for i in ids if i is not None}
    names = {d["_id"]: d["player_name"] for d in db.players.find({"_id": {"$in": list(ids)}}, {"player_name": 1})
             if d.get("player_name")}
    missing = ids - names.keys()
    if missing:
        # Newest season first, so a changed spelling uses the latest one.
        for d in db.player_stats.find({"player_id": {"$in": list(missing)}}, {"player_id": 1, "player_name": 1}).sort("season", -1):
            if d.get("player_name"):
                names.setdefault(d["player_id"], d["player_name"])
    missing = ids - names.keys()
    if missing:
        for d in db.game_logs.find({"player_id": {"$in": list(missing)}}, {"player_id": 1, "player_name": 1}).sort("game_date", -1):
            if d.get("player_name"):
                names.setdefault(d["player_id"], d["player_name"])
    return names


def name_of(names, pid):
    return names.get(pid) or f"Player {pid}"
