"""Fill MongoDB from the seed files in data/seed/.

Runs once when the stack starts, as the "loader" service in
docker-compose.yml, then exits. Run it by hand with:

    docker compose run --rm loader

How it works
- Each .jsonl file holds one MongoDB document per line, and becomes one
  collection with the same name (players.jsonl -> players).
- Every document carries its own _id (an NBA id), so the same row can never
  be stored twice.
- A collection loads into a temporary collection first, gets its indexes,
  and is then renamed over the old one in one step. The app never sees a
  half-loaded collection, and rows that vanished from the seed are removed.
- The loader stores a fingerprint (SHA-256 hash) of each file it loaded. On
  the next start, a file with the same fingerprint is skipped.
- A missing or broken file is reported in plain words and skipped. The rest
  still loads, and the loader always exits normally so the app still starts.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError

from app.db import db

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"

# The id of the document in the meta collection that remembers which file
# fingerprints were loaded.
HASHES_ID = "seed_hashes"

# Indexes for each collection, matching how the app looks things up.
# _id is always indexed by MongoDB, so it is not listed.
INDEXES = {
    "teams": [
        IndexModel([("abbreviation", ASCENDING)], unique=True),
    ],
    "players": [
        IndexModel([("team_id", ASCENDING)]),
        IndexModel([("player_name", ASCENDING)]),
    ],
    "standings": [],
    "schedule": [
        IndexModel([("game_date", ASCENDING)]),
        IndexModel([("home_team_id", ASCENDING), ("game_date", ASCENDING)]),
        IndexModel([("away_team_id", ASCENDING), ("game_date", ASCENDING)]),
    ],
    "game_logs": [
        IndexModel([("player_id", ASCENDING), ("game_date", DESCENDING)]),
        IndexModel([("team_id", ASCENDING), ("game_date", DESCENDING)]),
        IndexModel([("game_id", ASCENDING)]),
    ],
    "injuries": [
        IndexModel([("team_id", ASCENDING)]),
    ],
}


def log(message):
    print(f"[loader] {message}", flush=True)


def fingerprint(path):
    """SHA-256 hash of a file. It changes whenever any byte of the file changes."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path):
    """Read one JSON document per line. Blank lines are ignored."""
    docs = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"line {line_number} is not valid JSON ({err.msg})") from None
            if "_id" not in doc:
                raise ValueError(f"line {line_number} has no _id")
            docs.append(doc)
    return docs


def replace_collection(name, docs):
    """Load docs into a temporary collection, then swap it in for the real one."""
    temp = db[f"{name}__loading"]
    temp.drop()
    if docs:
        # insert_many fails on a repeated _id, which catches duplicate rows
        # in the seed file itself.
        temp.insert_many(docs, ordered=True)
        indexes = INDEXES.get(name, [])
        if indexes:
            temp.create_indexes(indexes)
        # rename with dropTarget replaces the old collection in one step.
        temp.rename(name, dropTarget=True)
    else:
        db[name].drop()


def load_meta(path, meta_collection):
    """meta.json is a single document. It is upserted, not swapped, so the
    stored fingerprints in the same collection are kept."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.setdefault("_id", "seed")
    meta_collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)


def main():
    if not SEED_DIR.is_dir():
        log(f"No seed folder at {SEED_DIR}. Nothing to load. Run the R pulls first.")
        return

    seed_files = sorted(SEED_DIR.glob("*.jsonl"))
    meta_file = SEED_DIR / "meta.json"
    if not seed_files and not meta_file.exists():
        log("The seed folder is empty. Nothing to load. Run the R pulls first.")
        return

    meta = db["meta"]
    stored = meta.find_one({"_id": HASHES_ID}) or {}
    known = stored.get("files", {})
    existing = set(db.list_collection_names())

    loaded, skipped, failed = [], [], []

    for path in seed_files:
        name = path.stem
        try:
            file_hash = fingerprint(path)
            # Skip only when the file is unchanged AND the collection is
            # still there (someone may have dropped it by hand).
            if known.get(path.name) == file_hash and name in existing:
                skipped.append(name)
                continue
            docs = read_jsonl(path)
            replace_collection(name, docs)
            known[path.name] = file_hash
            loaded.append(f"{name} ({len(docs)})")
        except (OSError, ValueError, PyMongoError) as err:
            failed.append(name)
            log(f"Could not load {path.name}: {err}. Skipped it, the rest still loads.")

    if meta_file.exists():
        try:
            file_hash = fingerprint(meta_file)
            if known.get(meta_file.name) == file_hash:
                skipped.append("meta")
            else:
                load_meta(meta_file, meta)
                known[meta_file.name] = file_hash
                loaded.append("meta (1)")
        except (OSError, ValueError, PyMongoError) as err:
            failed.append("meta")
            log(f"Could not load meta.json: {err}. Skipped it.")

    meta.replace_one(
        {"_id": HASHES_ID},
        {"_id": HASHES_ID, "files": known, "checked_at": datetime.now(timezone.utc).isoformat()},
        upsert=True,
    )

    if loaded:
        log("Loaded: " + ", ".join(loaded))
    if skipped:
        log("Unchanged, skipped: " + ", ".join(skipped))
    if failed:
        log("Failed: " + ", ".join(failed))
    log("Done.")


if __name__ == "__main__":
    try:
        main()
    except PyMongoError as err:
        # The database is not answering. Say so, but exit normally so the web
        # app still starts and its health check can report the problem.
        log(f"Could not reach MongoDB, so nothing was loaded: {err}")
    sys.exit(0)
