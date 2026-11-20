"""One shared MongoDB connection for the whole app.

MongoClient does not connect when it is created. It connects the first time
a command runs, so the app starts even when MongoDB is down.
"""

import os

from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/opponent_scout")

# Give up after 2 seconds, so a missing database gives a quick, clear error
# and not a 30 second hang.
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)

# The database name comes from the end of MONGO_URI ("opponent_scout").
db = client.get_default_database()


def mongo_is_reachable():
    """Return True if MongoDB answers a ping."""
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False


def ensure_user_indexes():
    """Indexes for the two collections users write (lineups and reports).
    The loader never rebuilds these, so they are created when the app starts.
    create_index does nothing if the index already exists."""
    from pymongo import ASCENDING, DESCENDING
    db.lineups.create_index([("team_id", ASCENDING), ("updated_at", DESCENDING)])
    db.reports.create_index([("created_at", DESCENDING)])
    db.reports.create_index([("us_team_id", ASCENDING)])
    db.reports.create_index([("them_team_id", ASCENDING)])
