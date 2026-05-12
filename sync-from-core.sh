#!/usr/bin/env bash
# sync-from-core.sh — Copy live fazle_payroll_engine files into this git repo.
# Run this before committing to keep the repo up to date with core.

set -euo pipefail

SRC="/home/azim/core/modules/fazle_payroll_engine"
DST="$(cd "$(dirname "$0")" && pwd)/fazle_payroll_engine"

echo "Syncing from $SRC → $DST"

rsync -av --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SRC/" "$DST/"

echo "Done. Review changes with: git diff"
echo "Commit with: git add -A && git commit -m 'chore: sync from core'"
