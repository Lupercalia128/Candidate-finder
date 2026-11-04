#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3.12 -c 'import sys; assert sys.version_info[:2] == (3, 12)'
# A virtual environment created with Python 3.14 must not be reused.
# Preserve it as a local backup rather than removing the user's files.
if [ -e .venv ]; then
  if ! .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>/dev/null; then
    mv .venv ".venv-backup-$(date +%s)-$$"
  fi
fi
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.lock
.venv/bin/python -m pip check
