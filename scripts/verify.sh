#!/usr/bin/env bash
set -euo pipefail
python -m pytest --basetemp .pytest_tmp
python -m quest_lint quests --format text
