from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_daily_plan_is_deterministic(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    d = date(2026, 2, 9)
    p1 = service.generate_daily_plan(d)
    p2 = service.get_daily_plan(d)
    assert p1["quest_ids"] == p2["quest_ids"]
    assert len(p1["quest_ids"]) >= 3


def test_daily_plan_has_required_pillar_coverage(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    plan = service.generate_daily_plan(date(2026, 2, 9))
    assert 3 <= len(plan["quest_ids"]) <= 5

    pillars = {
        pillar
        for quest in plan.get("quests", [])
        for pillar in quest.get("quest", {}).get("pillars", [])
        if isinstance(pillar, str)
    }
    assert "Security & Access Control" in pillars
    assert ("Memory & Context Hygiene" in pillars) or ("Reliability & Robustness" in pillars)
    assert (
        ("Identity & Authenticity" in pillars)
        or ("Alignment & Safety (Behavioral)" in pillars)
        or ("User Experience & Trust Calibration" in pillars)
    )


def test_daily_plan_adds_fourth_security_when_risk_footprint_high(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=600, scope="planner", reason="human approved")
    service.grant_capabilities_with_ticket(
        capabilities=["exec:shell"],
        ttl_seconds=300,
        scope="planner",
        ticket_token=ticket["token"],
    )

    plan = service.generate_daily_plan(date(2026, 2, 10))
    security_count = sum(
        1 for quest in plan.get("quests", []) if "Security & Access Control" in quest.get("quest", {}).get("pillars", [])
    )
    assert len(plan["quest_ids"]) >= 4
    assert security_count >= 2


def test_daily_plan_dropoff_mode_prefers_easier_quests(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    target = date(2026, 2, 10)

    completion_state = {
        "state_schema_version": "0.1",
        "items": [
            {
                "proof_id": f"p{i}",
                "quest_id": "wellness.identity.anchor.mission_statement.v1",
                "timestamp": ts,
                "tier": "P0",
                "xp_awarded": 1,
                "review_required": False,
            }
            for i, ts in enumerate(
                [
                    "2026-02-05T10:00:00+00:00",
                    "2026-02-05T12:00:00+00:00",
                    "2026-02-06T10:00:00+00:00",
                    "2026-02-06T12:00:00+00:00",
                    "2026-02-07T10:00:00+00:00",
                    "2026-02-07T12:00:00+00:00",
                ],
                start=1,
            )
        ],
    }
    service.completion_path.write_text(json.dumps(completion_state), encoding="utf-8")
    plan = service.generate_daily_plan(target)
    difficulties = [int(quest.get("quest", {}).get("difficulty", 1)) for quest in plan.get("quests", [])]
    assert difficulties
    assert max(difficulties) <= 2


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


def test_capability_ticket_enforced_and_single_use(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    ticket = service.create_grant_ticket(
        capabilities=["exec:shell"],
        ttl_seconds=600,
        scope="test-flow",
        reason="human approved",
    )

    grant = service.grant_capabilities_with_ticket(
        capabilities=["exec:shell"],
        ttl_seconds=300,
        scope="test-flow",
        ticket_token=ticket["token"],
    )
    assert grant["scope"] == "test-flow"

    try:
        service.grant_capabilities_with_ticket(
            capabilities=["exec:shell"],
            ttl_seconds=300,
            scope="test-flow",
            ticket_token=ticket["token"],
        )
        assert False, "Expected single-use ticket failure"
    except ValueError:
        assert True


def test_daily_plan_skips_authorized_quest_without_grants(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    extra_root = tmp_path / "extra-packs"
    pack_dir = extra_root / "wellness.test.authorized.v0"
    quest_file = pack_dir / "quests" / "wellness.test.authorized.only.v1.quest.yaml"
    _write(
        quest_file,
        """
schema_version: 0.1
quest:
  id: "wellness.test.authorized.only.v1"
  title: "Authorized Daily Gate Test"
  summary: "Test-only authorized quest."
  pillars: ["Security & Access Control"]
  cadence: "daily"
  difficulty: 2
  risk_level: "high"
  mode: "authorized"
  required_capabilities: ["net:scan_local"]
  steps:
    human:
      - type: "warn"
        text: "Stop if approval context is missing."
      - type: "confirm"
        text: "I confirm this is test-only."
    agent:
      - type: "reflect"
        text: "Summarize approved scope."
  proof:
    tier: "P2"
    artifacts:
      - id: "summary"
        type: "markdown"
        redaction_policy: "no-secrets"
        required: true
  scoring:
    base_xp: 50
    streak_weight: 1
    proof_multiplier: {P0: 1.0, P1: 1.2, P2: 1.5, P3: 1.5}
  tags: ["timebox:5", "test"]
""",
    )
    _write(
        pack_dir / "pack.yaml",
        """
pack_version: 0.1
pack:
  id: "wellness.test.authorized.v0"
  title: "Authorized Test Pack"
  publisher:
    name: "Agent Wellness Project"
    id: "org.agentwellness"
    contact: "security@agentwellness.example"
  version: "0.1.0"
  license: "Apache-2.0"
  created_at: "2026-02-11"
  quests:
    - "wellness.test.authorized.only.v1"
""",
    )

    os.environ["CLAWSPA_LOCAL_PACK_SOURCES"] = str(extra_root)
    try:
        service = RunnerService.create(_repo_root())
        plan = service.generate_daily_plan(date(2026, 2, 10))
    finally:
        os.environ.pop("CLAWSPA_LOCAL_PACK_SOURCES", None)
    assert "wellness.test.authorized.only.v1" not in plan["quest_ids"]


def test_search_includes_local_pack_source(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    extra_root = tmp_path / "extra-packs"
    pack_dir = extra_root / "wellness.test.searchable.v0"
    _write(
        pack_dir / "quests" / "wellness.test.searchable.daily.v1.quest.yaml",
        """
schema_version: 0.1
quest:
  id: "wellness.test.searchable.daily.v1"
  title: "Searchable Daily Quest"
  summary: "Test-only safe searchable quest."
  pillars: ["Security & Access Control"]
  cadence: "daily"
  difficulty: 1
  risk_level: "low"
  mode: "safe"
  required_capabilities: []
  steps:
    human:
      - type: "read"
        text: "Read."
    agent:
      - type: "reflect"
        text: "Reflect."
  proof:
    tier: "P0"
    artifacts: []
  scoring:
    base_xp: 5
    streak_weight: 1
    proof_multiplier: {P0: 1.0, P1: 1.2, P2: 1.5, P3: 1.5}
  tags: ["timebox:2", "test-search"]
""",
    )
    _write(
        pack_dir / "pack.yaml",
        """
pack_version: 0.1
pack:
  id: "wellness.test.searchable.v0"
  title: "Search Test Pack"
  publisher:
    name: "Agent Wellness Project"
    id: "org.agentwellness"
    contact: "security@agentwellness.example"
  version: "0.1.0"
  license: "Apache-2.0"
  created_at: "2026-02-11"
  quests:
    - "wellness.test.searchable.daily.v1"
""",
    )

    os.environ["CLAWSPA_LOCAL_PACK_SOURCES"] = str(extra_root)
    try:
        service = RunnerService.create(_repo_root())
        results = service.search_quests(tag="test-search")
    finally:
        os.environ.pop("CLAWSPA_LOCAL_PACK_SOURCES", None)
    assert any(item.get("quest", {}).get("id") == "wellness.test.searchable.daily.v1" for item in results)


def test_artifact_with_secret_like_content_rejected(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    service.init_profiles()

    try:
        service.complete_quest(
            "wellness.identity.anchor.mission_statement.v1",
            "P0",
            "sk-abcdefghijklmnop",
        )
        assert False, "Expected secret-like artifact rejection"
    except ValueError:
        assert True


def test_daily_plan_is_cadence_aware_and_can_include_non_daily(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    plan = service.generate_daily_plan(date(2026, 2, 11))
    cadences = {quest.get("quest", {}).get("cadence") for quest in plan.get("quests", [])}
    assert any(cadence in {"weekly", "monthly"} for cadence in cadences)


def test_trust_signal_emitted_when_rule_threshold_met(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    result = service.complete_quest(
        "wellness.security_access_control.permissions.delta_inventory.v1",
        "P1",
        "sanitized permission summary",
        actor_mode="agent",
        source="mcp",
        actor_id="openclaw:moltfred",
    )
    assert result["trust_signals_emitted"]
    card = service.get_scorecard()
    assert any(signal.get("signal_id") == "trust.security.permissions.delta_inventory.fresh" for signal in card["trust_signals"])


def test_proofs_purge_removes_old_entries(tmp_path: Path) -> None:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    old_completion = {
        "proof_id": "p-old",
        "quest_id": "wellness.identity.anchor.mission_statement.v1",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "tier": "P0",
        "xp_awarded": 0,
        "review_required": False,
    }
    recent_completion = {
        "proof_id": "p-new",
        "quest_id": "wellness.identity.anchor.mission_statement.v1",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "tier": "P0",
        "xp_awarded": 0,
        "review_required": False,
    }
    service.completion_path.write_text(
        json.dumps({"state_schema_version": "0.1", "items": [old_completion, recent_completion]}),
        encoding="utf-8",
    )

    old_proof = service.dirs["proofs"] / "p-old.json"
    old_proof.write_text(json.dumps({"proof_id": "p-old", "timestamp": "2024-01-01T00:00:00+00:00"}), encoding="utf-8")
    recent_proof = service.dirs["proofs"] / "p-new.json"
    recent_proof.write_text(
        json.dumps({"proof_id": "p-new", "timestamp": datetime.now(tz=UTC).isoformat()}),
        encoding="utf-8",
    )

    purge = service.proofs_purge(older_than="30d")
    assert purge["purged_completions"] == 1
    assert purge["purged_files"] == 1
    assert old_proof.exists() is False
    assert recent_proof.exists() is True
