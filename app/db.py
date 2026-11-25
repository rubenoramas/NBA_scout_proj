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
    """Indexes for the collections the app writes (lineups, reports,
    refresh_jobs and onepager_notes).
    The loader never rebuilds these, so they are created when the app starts.
    create_index does nothing if the index already exists."""
    from pymongo import ASCENDING, DESCENDING
    db.lineups.create_index([("team_id", ASCENDING), ("updated_at", DESCENDING)])
    db.reports.create_index([("created_at", DESCENDING)])
    db.reports.create_index([("us_team_id", ASCENDING)])
    db.reports.create_index([("them_team_id", ASCENDING)])
    # At most one active refresh job: a unique index that only covers
    # documents with active: true. A second active job is rejected.
    db.refresh_jobs.create_index([("active", ASCENDING)], unique=True,
                                 partialFilterExpression={"active": True}, name="one_active_job")
    db.refresh_jobs.create_index([("created_at", DESCENDING)])
    # One cached "How to guard him" text per player, our team, data date,
    # prompt version and set of our players who are Out. The unique index
    # makes the cache key a rule the database enforces, and makes each cache
    # lookup one index read.
    # The first version of this index had four fields; drop it if present.
    if "one_note_per_page" in db.onepager_notes.index_information():
        db.onepager_notes.drop_index("one_note_per_page")
    db.onepager_notes.create_index([("player_id", ASCENDING), ("vs_team_id", ASCENDING),
                                    ("data_as_of", ASCENDING), ("prompt_version", ASCENDING),
                                    ("us_out", ASCENDING)],
                                   unique=True, name="one_note_per_page_v2")
