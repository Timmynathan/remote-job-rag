#!/bin/bash
# Daily scheduled entrypoint, invoked by launchd (see scripts/launchd/).
# Clears uv's recurring macOS "hidden .pth file" bug defensively before every
# run, since an unattended job can't notice and retry a silent import failure
# the way an interactive session can.
set -euo pipefail

REPO_ROOT="/Users/timmyilesanmi/Desktop/remote-job-rag"
cd "$REPO_ROOT"

chflags nohidden .venv/lib/python3.12/site-packages/*.pth 2>/dev/null || true

/opt/homebrew/bin/uv run --no-sync naija-job-hunter \
    --min-strong-matches 3 \
    --max-iterations 2 \
    --max-candidates-to-score 15
