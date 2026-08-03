#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
LOG_DIR="$PROJECT_ROOT/logs"
DATE="$(date +%Y%m%d)"
DISPLAY_DATE="$(date +%F)"
PYTHON="${PYTHON:-$PROJECT_ROOT/.venv/bin/python}"

mkdir -p "$LOG_DIR"
LOG_PATH="$LOG_DIR/daily-update-$DATE.log"
exec > >(tee -a "$LOG_PATH") 2>&1
export PYTHONIOENCODING=utf-8

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

run_python() {
  log "Run: $PYTHON $*"
  "$PYTHON" "$@"
}

valid_snapshot() {
  local path="$1"
  [ -s "$path" ] || return 1
  "$PYTHON" - "$path" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    snapshot = json.load(fh)
categories = snapshot.get("categories", [])
books = [book for category in categories for book in category.get("books", [])]
if len(categories) < 15 or len(books) < 300:
    raise SystemExit(1)
if any(len(category.get("books", [])) < 15 for category in categories):
    raise SystemExit(1)
required = ("title", "author", "reads", "intro", "url")
if any(not all(str(book.get(key, "")).strip() for key in required) for book in books):
    raise SystemExit(1)
PY
}

boards=(
  "female_new 0 1"
  "female_read 0 2"
  "male_new 1 1"
  "male_read 1 2"
)

scrape_board() {
  local key="$1"
  local channel="$2"
  local rank_type="$3"
  local snapshot="$4"
  local max_attempts="${SCRAPE_RETRIES:-3}"
  local retry_delay="${SCRAPE_RETRY_DELAY:-30}"
  local attempt

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    log "Scrape start: $key (attempt $attempt/$max_attempts)"
    if run_python "$PROJECT_ROOT/scrape_fanqie_ranks.py" \
      --channel "$channel" --type "$rank_type" --limit 30 --sleep 5 \
      && valid_snapshot "$snapshot"; then
      log "Snapshot passed quality check: $key"
      return 0
    fi

    log "Scrape or quality check failed: $key (attempt $attempt/$max_attempts)"
    if (( attempt < max_attempts )); then
      log "Retrying $key from checkpoint in ${retry_delay}s"
      sleep "$retry_delay"
    fi
  done

  log "Snapshot failed after $max_attempts attempts: $key"
  return 1
}

log "Daily four-board update started for $DISPLAY_DATE"

if [ -x "$PROJECT_ROOT/scripts/check_upstream.sh" ]; then
  if ! "$PROJECT_ROOT/scripts/check_upstream.sh"; then
    log "Warning: upstream check failed; keeping the current production code."
  fi
fi

for board in "${boards[@]}"; do
  read -r key channel rank_type <<< "$board"
  snapshot="$DATA_DIR/fanqie_${key}_ranks_${DATE}.json"
  if valid_snapshot "$snapshot"; then
    log "Skip validated snapshot: $key"
    continue
  fi
  scrape_board "$key" "$channel" "$rank_type" "$snapshot" || exit 1
done

for board in "${boards[@]}"; do
  read -r key channel rank_type <<< "$board"
  snapshot="$DATA_DIR/fanqie_${key}_ranks_${DATE}.json"
  cp -f "$snapshot" "$DATA_DIR/latest_${key}_ranks.json"
  if [ "$key" = "female_new" ]; then
    cp -f "$snapshot" "$DATA_DIR/latest_ranks.json"
  fi
  run_python "$PROJECT_ROOT/scripts/build_latest.py" \
    --channel "$channel" --type "$rank_type"
done

RETENTION_DAYS="${HISTORY_RETENTION_DAYS:-180}"
if [ -f "$PROJECT_ROOT/scripts/prune_history.py" ]; then
  run_python "$PROJECT_ROOT/scripts/prune_history.py" --keep-days "$RETENTION_DAYS"
fi

log "All four boards updated; aggregates, history indexes, and trends generated."
