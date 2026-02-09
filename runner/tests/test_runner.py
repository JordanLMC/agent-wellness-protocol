from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_daily_plan_is_deterministic(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    d = date(2026, 2, 9)
    p1 = service.generate_daily_plan(d)
    p2 = service.get_daily_plan(d)
    assert p1["quest_ids"] == p2["quest_ids"]
    assert len(p1["quest_ids"]) >= 3


def test_completion_updates_scorecard(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.init_profiles()
    result = service.complete_quest(
        "wellness.identity.anchor.mission_statement.v1",
        "P0",
        "local summary ref",
    )
    card = service.get_scorecard()
    assert result["xp_awarded"] >= 0
    assert card["total_xp"] >= 0
    assert card["daily_streak"] >= 1
