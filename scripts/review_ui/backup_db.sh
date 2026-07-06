#!/bin/bash
# Back up the human-annotation reviews.db via a consistent VACUUM INTO copy.
# Safe on a live WAL-mode db (unlike a raw cp, which can grab a torn snapshot).
# Keeps only the most recent 50 backups; irreplaceable data, so this script
# never deletes the source db and never overwrites an existing backup file.
set -euo pipefail

REVIEW_DIR="${REVIEW_DIR:-/home/deploy/repos/givecare/gc-bench/internal/review}"
DB="$REVIEW_DIR/reviews.db"
BACKUP_DIR="$REVIEW_DIR/backups"
KEEP=50

if [ ! -f "$DB" ]; then
  # Nothing to back up yet — not an error condition.
  exit 0
fi

mkdir -p "$BACKUP_DIR"

DEST="$BACKUP_DIR/reviews-$(date -u +%Y%m%dT%H%M%SZ).db"

# busy_timeout so a concurrent reviewer write doesn't fail the backup (which,
# under set -e, would otherwise skip that scheduled backup entirely).
sqlite3 "$DB" ".timeout 5000" "VACUUM INTO '$DEST'"

# Prune to the most recent $KEEP backups. Sort by filename descending: the UTC
# timestamp format is lexicographically chronological, so this is newest-first
# regardless of mtime (which a restore/touch could scramble).
mapfile -t backups < <(ls -1 "$BACKUP_DIR"/reviews-*.db 2>/dev/null | sort -r)
total="${#backups[@]}"
if [ "$total" -gt "$KEEP" ]; then
  for ((i = KEEP; i < total; i++)); do
    rm -f -- "${backups[$i]}"
  done
fi

kept=$(( total < KEEP ? total : KEEP ))
echo "backup_db: wrote $DEST (kept $kept/$KEEP backups)"
