#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Opponent Scout: refresh the data
#
# Runs every R pull script in order, then reloads MongoDB with the loader,
# and prints how the row count of each seed file changed.
#
# How to run (from the repo root, on your laptop, with Docker running):
#   ./refresh.sh
#
# Needs R with hoopR, arrow, dplyr and jsonlite (see pulls/), and Docker.
# The live NBA stats script (pulls/pull_live.R) is not run here, because it
# only works from a phone hotspot. Run it by hand when you want it.
# ---------------------------------------------------------------------------

set -euo pipefail

# Always work from the repo root, wherever the script is called from.
cd "$(dirname "$0")"

# The pull scripts, in the order they must run. Add new ones here.
PULL_SCRIPTS=(
  pulls/pull_core.R
  pulls/pull_shots.R
  pulls/pull_stats.R
)

SEED_DIR="data/seed"

fail() {
  echo
  echo "Refresh stopped: $1"
  echo "The seed files may be partly updated. Fix the problem and run ./refresh.sh again."
  exit 1
}

# ---- Checks ---------------------------------------------------------------
command -v Rscript >/dev/null 2>&1 || fail "R is not installed (the Rscript command was not found)."
command -v docker >/dev/null 2>&1 || fail "Docker is not installed (the docker command was not found)."
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop and try again."

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  fail "Docker Compose was not found."
fi

# Prints "file rows" for every seed file. A .jsonl file has one row per
# line, a .jsonl.gz file is the same but compressed, and meta.json is a
# single document.
count_rows() {
  for f in "$SEED_DIR"/*.jsonl "$SEED_DIR"/*.jsonl.gz "$SEED_DIR"/*.json; do
    [ -e "$f" ] || continue
    if [[ "$f" == *.jsonl.gz ]]; then
      echo "$(basename "$f") $(gzip -cd "$f" | wc -l | tr -d ' ')"
    elif [[ "$f" == *.jsonl ]]; then
      echo "$(basename "$f") $(wc -l < "$f" | tr -d ' ')"
    else
      echo "$(basename "$f") 1"
    fi
  done
}

BEFORE="$(mktemp)"
AFTER="$(mktemp)"
trap 'rm -f "$BEFORE" "$AFTER"' EXIT
count_rows > "$BEFORE"

# ---- Pull -----------------------------------------------------------------
for script in "${PULL_SCRIPTS[@]}"; do
  [ -f "$script" ] || fail "$script does not exist."
  echo "==> Running $script"
  if ! Rscript "$script"; then
    fail "$script failed. Read the R error above. A common cause is a missing package or no internet."
  fi
  echo
done

# ---- Load -----------------------------------------------------------------
echo "==> Reloading MongoDB from $SEED_DIR"
if ! "${COMPOSE[@]}" run --rm loader; then
  fail "the loader could not reload MongoDB. Check that 'docker-compose up' works."
fi

# ---- What changed ---------------------------------------------------------
count_rows > "$AFTER"
echo
echo "==> What changed"
printf "%-24s %10s %10s %8s\n" "file" "before" "after" "change"
# join the before and after lists on the file name. Files that are new or
# gone show 0 on the missing side.
join -a1 -a2 -e 0 -o 0,1.2,2.2 <(sort "$BEFORE") <(sort "$AFTER") | while read -r file before after; do
  diff=$((after - before))
  if [ "$diff" -gt 0 ]; then sign="+$diff"; else sign="$diff"; fi
  printf "%-24s %10s %10s %8s\n" "$file" "$before" "$after" "$sign"
done

games_through=$(grep -o '"data_as_of": *"[^"]*"' "$SEED_DIR/meta.json" | sed 's/.*"\([^"]*\)"$/\1/')
pulled=$(grep -o '"pulled_at": *"[^"]*"' "$SEED_DIR/meta.json" | sed 's/.*"\([^"]*\)"$/\1/')
echo
echo "Games through $games_through, pulled $pulled (UTC)."
echo "Done. Reload the app in the browser to see the new data."
echo
echo "Note: commit refreshed seed data only at milestones (before the demo video"
echo "and before submitting), not after every refresh. Each commit of data/seed/"
echo "adds a few MB to the repo history. To keep your working copy clean between"
echo "milestones, you can undo a refresh with: git checkout -- data/seed"
