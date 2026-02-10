#!/usr/bin/env bash
set -euo pipefail
python scripts/check_bidi.py .
python -m pytest --basetemp .pytest_tmp
python -m quest_lint quests --format text
