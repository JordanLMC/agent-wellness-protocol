from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from clawspa_runner.service import RunnerService
from clawspa_runner.telemetry import TelemetryLogger, sanitize_event_data


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def test_sanitize_redacts_secret_like_values() -> None:
    payload = {
        "token": "sk-abcdefghijklmnop",
        "nested": {"email": "user@example.com", "note": "a" * 250},
    }
    sanitized, stats = sanitize_event_data(payload)
    assert sanitized["token"] == "[redacted]"
    assert sanitized["nested"]["email"] == "[redacted]"
    assert sanitized["nested"]["note"].endswith("...[truncated]")
    assert stats.redacted_fields >= 2
    assert stats.truncated_fields >= 1


def test_event_logger_appends_valid_jsonl(tmp_path: Path) -> None:
    events_path = tmp_path / "telemetry" / "events.jsonl"
    logger = TelemetryLogger(events_path=events_path, repo_root=_repo_root())
    logger.log_event(
        "runner.started",
        actor="system",
        source="cli",
        data={"session": "local"},
    )
    rows = _read_jsonl(events_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_version"] == "0.1"
    assert row["event_type"] == "runner.started"
    assert row["actor"] == "system"
    assert row["source"] == "cli"
    assert "build" in row


def test_export_aggregates_metrics(tmp_path: Path) -> None:
    events_path = tmp_path / "telemetry" / "events.jsonl"
    logger = TelemetryLogger(events_path=events_path, repo_root=_repo_root())
    logger.log_event(
        "plan.generated",
        actor="human",
        source="cli",
        data={"date": "2026-02-10", "quest_ids": ["q1", "q2", "q3"], "quest_count": 3},
    )
    logger.log_event(
        "quest.completed",
        actor="agent",
        source="mcp",
        data={"quest_id": "q1", "proof_tier": "P1", "timebox_estimate_minutes": 5, "observed_duration_seconds": 120},
    )
    logger.log_event(
        "quest.completed",
        actor="human",
        source="cli",
        data={"quest_id": "q2", "proof_tier": "P0", "timebox_estimate_minutes": 4, "observed_duration_seconds": 90},
    )
    logger.log_event(
        "quest.failed",
        actor="agent",
        source="mcp",
        data={"quest_id": "q3", "reason": "capability_missing"},
    )
    logger.log_event("risk.flagged", actor="system", source="api", data={"reason": "telemetry_sanitized"})

    summary = logger.export_summary(
        range_value="7d",
        score_state={"daily_streak": 2, "weekly_streak": 1, "total_xp": 30},
    )
    assert summary["completions_total"] == 2
    assert summary["plans_generated"] == 1
    assert summary["avg_quests_per_plan"] == 3.0
    assert summary["quest_success_rate"] == 0.6667
    assert summary["risk_flags_count"] >= 1
    assert summary["daily_streak"] == 2
    assert summary["total_xp"] == 30
    assert summary["top_quests_completed"][0]["count"] == 1


def test_plan_generation_writes_telemetry_event(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.generate_daily_plan(date(2026, 2, 10), source="cli", actor="human")

    events_path = Path(os.environ["AGENTWELLNESS_HOME"]) / "telemetry" / "events.jsonl"
    rows = _read_jsonl(events_path)
    types = [row.get("event_type") for row in rows]
    assert "plan.generated" in types


def test_proof_submission_writes_telemetry_event(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.complete_quest(
        "wellness.identity.anchor.mission_statement.v1",
        "P0",
        "mission reflection",
        actor_mode="agent",
        source="mcp",
    )
    events_path = Path(os.environ["AGENTWELLNESS_HOME"]) / "telemetry" / "events.jsonl"
    rows = _read_jsonl(events_path)
    types = [row.get("event_type") for row in rows]
    assert "proof.submitted" in types
    assert "quest.completed" in types
