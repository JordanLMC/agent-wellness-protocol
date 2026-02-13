from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_events(home: Path) -> list[dict]:
    events_path = home / "telemetry" / "events.jsonl"
    if not events_path.exists():
        return []
    rows: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def test_preset_files_validate_against_schema() -> None:
    repo_root = _repo_root()
    schema = json.loads((repo_root / "presets" / "schema" / "preset.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    preset_files = sorted((repo_root / "presets" / "v0").glob("*.preset.yaml"))
    assert len(preset_files) == 5
    for preset_file in preset_files:
        payload = yaml.safe_load(preset_file.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
        assert not errors, f"{preset_file}: {errors[0].message}"


def test_apply_preset_writes_profile_and_emits_event(tmp_path: Path) -> None:
    home = tmp_path / "home"
    os.environ["AGENTWELLNESS_HOME"] = str(home)
    service = RunnerService.create(_repo_root())
    result = service.apply_preset(
        "builder.v0",
        source="cli",
        actor="agent",
        actor_id="openclaw:moltfred",
        trace_id="cli:preset-apply",
    )
    assert result["applied_preset"]["preset_id"] == "builder.v0"
    profile = service.get_profile("agent")
    assert profile["applied_preset"]["preset_id"] == "builder.v0"

    events = _read_events(home)
    applied_events = [event for event in events if event.get("event_type") == "preset.applied"]
    assert applied_events
    assert applied_events[-1]["actor"] == {"kind": "agent", "id": "openclaw:moltfred"}
    assert applied_events[-1]["trace_id"] == "cli:preset-apply"


def test_daily_plan_with_preset_respects_pack_allowlist(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.apply_preset("task_manager.v0", actor="agent", actor_id="openclaw:moltfred")
    allowlist = set(service.get_preset("task_manager.v0")["pack_allowlist"])

    plan = service.generate_daily_plan(date(2026, 2, 13), actor="agent", actor_id="openclaw:moltfred")
    assert plan["applied_preset_id"] == "task_manager.v0"
    assert plan["quest_ids"]
    for quest in plan["quests"]:
        assert quest.get("_pack") in allowlist


def test_telemetry_export_includes_preset_metrics(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.apply_preset("security_steward.v0", actor="agent", actor_id="openclaw:moltfred")
    service.complete_quest(
        "wellness.identity.anchor.mission_statement.v1",
        "P0",
        "preset-safe-proof",
        actor_mode="agent",
        source="mcp",
        actor_id="openclaw:moltfred",
    )

    out = tmp_path / "summary.json"
    summary = service.telemetry_export("7d", out, actor_id="openclaw:moltfred")
    assert summary["applied_preset_id"] == "security_steward.v0"
    assert summary["completions_by_preset"]["security_steward.v0"] >= 1
    assert summary["xp_by_preset"]["security_steward.v0"] >= 0
