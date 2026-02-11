from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from clawspa_runner.service import RunnerService
from clawspa_runner.telemetry import TelemetryLogger, sanitize_event_data, summary_sha256


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
    assert row["actor"] == {"kind": "system", "id": "unknown"}
    assert row["source"] == "cli"
    assert "build" in row


def test_export_aggregates_metrics(tmp_path: Path) -> None:
    events_path = tmp_path / "telemetry" / "events.jsonl"
    logger = TelemetryLogger(events_path=events_path, repo_root=_repo_root())
    logger.log_event(
        "plan.generated",
        actor="human",
        actor_id="human:jordan",
        source="cli",
        data={"date": "2026-02-10", "quest_ids": ["q1", "q2", "q3"], "quest_count": 3},
    )
    logger.log_event(
        "quest.completed",
        actor="agent",
        actor_id="openclaw:moltfred",
        source="mcp",
        data={"quest_id": "q1", "proof_tier": "P1", "timebox_estimate_minutes": 5, "observed_duration_seconds": 120},
    )
    logger.log_event(
        "quest.completed",
        actor="human",
        actor_id="human:jordan",
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
    assert summary["completions_by_actor_id"]["openclaw:moltfred"] == 1
    assert summary["completions_by_actor_id"]["human:jordan"] == 1
    assert summary["completions_by_source"]["mcp"] == 1
    assert summary["events_by_actor_id"]["human:jordan"] >= 1
    assert summary["top_quests_completed"][0]["count"] == 1


def test_plan_generation_writes_telemetry_event(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.generate_daily_plan(
        date(2026, 2, 10),
        source="cli",
        actor="human",
        actor_id="human:jordan",
    )

    events_path = Path(os.environ["AGENTWELLNESS_HOME"]) / "telemetry" / "events.jsonl"
    rows = _read_jsonl(events_path)
    types = [row.get("event_type") for row in rows]
    assert "plan.generated" in types
    plan_event = next(row for row in reversed(rows) if row.get("event_type") == "plan.generated")
    assert plan_event["actor"] == {"kind": "human", "id": "human:jordan"}


def test_proof_submission_writes_telemetry_event(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.complete_quest(
        "wellness.identity.anchor.mission_statement.v1",
        "P0",
        "mission reflection",
        actor_mode="agent",
        source="mcp",
        actor_id="openclaw:moltfred",
    )
    events_path = Path(os.environ["AGENTWELLNESS_HOME"]) / "telemetry" / "events.jsonl"
    rows = _read_jsonl(events_path)
    types = [row.get("event_type") for row in rows]
    assert "proof.submitted" in types
    assert "quest.completed" in types
    proof_event = next(row for row in reversed(rows) if row.get("event_type") == "proof.submitted")
    assert proof_event["actor"] == {"kind": "agent", "id": "openclaw:moltfred"}


def test_export_can_filter_by_actor_id(tmp_path: Path) -> None:
    events_path = tmp_path / "telemetry" / "events.jsonl"
    logger = TelemetryLogger(events_path=events_path, repo_root=_repo_root())
    logger.log_event(
        "quest.completed",
        actor="agent",
        actor_id="openclaw:moltfred",
        source="mcp",
        data={"quest_id": "q1", "proof_tier": "P1"},
    )
    logger.log_event(
        "quest.completed",
        actor="human",
        actor_id="human:jordan",
        source="cli",
        data={"quest_id": "q2", "proof_tier": "P0"},
    )

    summary = logger.export_summary(
        range_value="7d",
        score_state={"daily_streak": 0, "weekly_streak": 0, "total_xp": 0},
        actor_id="openclaw:moltfred",
    )
    assert summary["actor_id_filter"] == "openclaw:moltfred"
    assert summary["events_considered"] == 1
    assert summary["completions_total"] == 1
    assert summary["completions_by_actor_id"] == {"openclaw:moltfred": 1}


def test_export_normalizes_legacy_actor_strings(tmp_path: Path) -> None:
    events_path = tmp_path / "telemetry" / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    legacy_events = [
        {
            "schema_version": "0.1",
            "event_id": "legacy-1",
            "ts": now,
            "event_type": "quest.completed",
            "actor": "agent",
            "source": "mcp",
            "build": {},
            "data": {"quest_id": "q1", "proof_tier": "P0"},
        },
        {
            "schema_version": "0.1",
            "event_id": "legacy-2",
            "ts": now,
            "event_type": "quest.completed",
            "source": "cli",
            "build": {},
            "data": {"quest_id": "q2", "proof_tier": "P1"},
        },
    ]
    events_path.write_text("\n".join(json.dumps(event) for event in legacy_events) + "\n", encoding="utf-8")

    logger = TelemetryLogger(events_path=events_path, repo_root=_repo_root())
    summary = logger.export_summary(
        range_value="365d",
        score_state={"daily_streak": 0, "weekly_streak": 0, "total_xp": 0},
    )
    assert summary["completions_total"] == 2
    assert summary["completions_by_actor_kind"]["agent"] == 1
    assert summary["completions_by_actor_kind"]["system"] == 1
    assert summary["completions_by_actor_id"]["unknown"] == 2


def test_snapshot_writes_file_and_sha_matches_payload(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    out = tmp_path / "baseline.json"
    snapshot = service.telemetry_snapshot("7d", actor_id="openclaw:moltfred", out_path=out)
    assert out.exists()

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert snapshot["path"] == str(out)
    assert snapshot["sha256"] == summary_sha256(payload)


def test_telemetry_diff_reports_expected_deltas(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    baseline_a = tmp_path / "baseline-a.json"
    baseline_b = tmp_path / "baseline-b.json"

    baseline_a.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "generated_at": "2026-02-10T00:00:00Z",
                "range": "7d",
                "events_considered": 10,
                "completions_total": 2,
                "total_xp": 30,
                "daily_streak": 2,
                "weekly_streak": 1,
                "risk_flags_count": 1,
                "quest_success_rate": 0.5,
                "completions_by_actor_id": {"openclaw:moltfred": 1},
                "top_quests_completed": [{"quest_id": "q1", "count": 1}],
            }
        ),
        encoding="utf-8",
    )
    baseline_b.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "generated_at": "2026-02-11T00:00:00Z",
                "range": "7d",
                "events_considered": 20,
                "completions_total": 5,
                "total_xp": 90,
                "daily_streak": 4,
                "weekly_streak": 2,
                "risk_flags_count": 1,
                "quest_success_rate": 0.8,
                "completions_by_actor_id": {"openclaw:moltfred": 3, "human:jordan": 2},
                "top_quests_completed": [{"quest_id": "q1", "count": 2}, {"quest_id": "q2", "count": 2}],
            }
        ),
        encoding="utf-8",
    )

    diff = service.telemetry_diff(baseline_a, baseline_b)
    changes = diff["diff"]["changes"]
    assert changes["completions_total_delta"] == 3
    assert changes["total_xp_delta"] == 60
    assert changes["daily_streak_delta"] == 2
    assert changes["quest_success_rate_delta"] == 0.3
    assert changes["completions_by_actor_id_delta"]["human:jordan"] == 2
    assert "Completions delta: 3" in diff["text"]


def test_telemetry_diff_rejects_invalid_summary_schema(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    baseline_a = tmp_path / "baseline-a.json"
    baseline_b = tmp_path / "baseline-b.json"
    baseline_a.write_text(json.dumps({"schema_version": "0.1"}), encoding="utf-8")
    baseline_b.write_text(json.dumps({"schema_version": "0.1"}), encoding="utf-8")

    try:
        service.telemetry_diff(baseline_a, baseline_b)
        assert False, "Expected schema validation failure"
    except ValueError:
        assert True
