#!/usr/bin/env bash
# Embed the fragments with Harrier-OSS-v1-0.6B, then finalize them.
#
# Usage: scripts/run_embeddings.sh [PART] [extra options for "run", e.g. --device cpu]
#
# With PART (e.g. stable), it embeds the part fragments.PART, whose input must
# first be frozen with `uv run python -m pipeline.embed snapshot`.
#
# Safe to re-run: completed shards are skipped, so it resumes after a crash,
# sleep or Ctrl-C. Keeps the Mac awake (caffeinate -dimsu) while it runs.
# Exits non-zero on the first failure. Logs: data/interim/logs/.
set -euo pipefail

# Re-run this script under caffeinate so the whole sequence keeps the Mac awake.
# This happens before the cd below, so a relative "$0" still resolves.
if [[ -z "${EMBED_CAFFEINATED:-}" ]] && command -v caffeinate >/dev/null; then
  export EMBED_CAFFEINATED=1
  exec caffeinate -dimsu "$0" "$@"
fi

cd "$(dirname "$0")/.."

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
LOG_DIR=data/interim/logs
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run_embeddings_$(date +%Y%m%d_%H%M%S).log"

PART=""
if [[ $# -gt 0 && "$1" != -* ]]; then
  PART=".$1"
  shift
fi

steps() {
  uv run python -m pipeline.embed run "fragments$PART" "$@"
  uv run python -m pipeline.embed finalize "fragments$PART"
  uv run python -m pipeline.embed status
}

echo "Log: $LOG"
steps "$@" 2>&1 | tee -a "$LOG"
