"""Fill MongoDB from the seed files in data/seed/.

Runs once when the stack starts, as the "loader" service in
docker-compose.yml, then exits. Run it by hand with:

    docker compose run --rm loader

How it works
- Each .jsonl file holds one MongoDB document per line, and becomes one
  collection with the same name (players.jsonl -> players). The two big
  files are gzip-compressed (.jsonl.gz) and are read the same way.
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

import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError

from app.db import db
from app.model import compute as model

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
    "shots": [
        IndexModel([("player_id", ASCENDING), ("zone", ASCENDING)]),
        IndexModel([("team_id", ASCENDING)]),
        IndexModel([("zone", ASCENDING)]),
    ],
    "shot_zones_last": [
        IndexModel([("player_id", ASCENDING)]),
    ],
    "shot_types_last": [
        IndexModel([("player_id", ASCENDING)]),
    ],
    "player_stats": [IndexModel([("player_id", ASCENDING), ("season", ASCENDING)])],
    "play_types": [IndexModel([("player_id", ASCENDING)])],
    "play_type_mix": [IndexModel([("player_id", ASCENDING), ("season", ASCENDING)])],
    "assist_pairs": [IndexModel([("scorer_id", ASCENDING)])],
    "hustle": [IndexModel([("player_id", ASCENDING)])],
    "steals": [IndexModel([("player_id", ASCENDING)])],
    "shot_extras": [IndexModel([("player_id", ASCENDING)])],
    "matchup_defense": [IndexModel([("player_id", ASCENDING)])],
    "team_stats": [],
    "matchup_pairs": [IndexModel([("off_id", ASCENDING)]), IndexModel([("def_id", ASCENDING)])],
    "matchup_games": [IndexModel([("game_id", ASCENDING)]), IndexModel([("game_date", ASCENDING)])],
    "matchup_top": [IndexModel([("game_id", ASCENDING)])],
    "player_onoff": [IndexModel([("player_id", ASCENDING), ("season", ASCENDING)])],
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


def collection_name(path):
    """players.jsonl -> players, shots.jsonl.gz -> shots"""
    name = path.name
    for suffix in (".jsonl.gz", ".jsonl"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def read_jsonl(path):
    """Read one JSON document per line. Blank lines are ignored.
    A .gz file is decompressed on the fly."""
    docs = []
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
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

    seed_files = sorted(list(SEED_DIR.glob("*.jsonl")) + list(SEED_DIR.glob("*.jsonl.gz")))
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
        name = collection_name(path)
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
        except (OSError, ValueError, EOFError, PyMongoError) as err:
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

    # Ratings and badges are computed in Python from the loaded data. Skip
    # the work when none of their inputs changed and they already exist.
    changed = {entry.split(" ")[0] for entry in loaded}
    if changed & set(model.INPUTS) or "attributes" not in db.list_collection_names():
        try:
            docs, summary = model.compute()
            model.write(docs, summary)
            log(f"Computed ratings and badges for {len(docs)} players.")
        except Exception as err:  # noqa: BLE001 - the app must still start
            log(f"Could not compute ratings and badges: {err}. The rest of the app still works.")
    else:
        log("Ratings and badges unchanged, skipped.")

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
