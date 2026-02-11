from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from clawspa_runner.api import create_app
from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _service_and_client(tmp_path: Path) -> tuple[RunnerService, TestClient]:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    app = create_app(service)
    return service, TestClient(app)


def _events(tmp_path: Path) -> list[dict]:
    events_path = tmp_path / "home" / "telemetry" / "events.jsonl"
    if not events_path.exists():
        return []
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_daily_plan_endpoint(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/plans/daily", params={"date": "2026-02-09"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["quest_ids"]) >= 3


def test_weekly_plan_endpoints(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    read_response = client.get("/v1/plans/weekly", params={"date": "2026-02-11"})
    assert read_response.status_code == 200
    read_payload = read_response.json()
    assert "quest_ids" in read_payload
    assert len(read_payload["quest_ids"]) >= 1

    generate_response = client.post("/v1/plans/weekly/generate", params={"date": "2026-02-11"})
    assert generate_response.status_code == 200
    assert len(generate_response.json()["quest_ids"]) >= 1


def test_quests_search_route_not_shadowed(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/quests/search", params={"mode": "safe"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_quest_invalid_id_returns_404(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/quests/wellness.missing.quest.v1")
    assert response.status_code == 404


def test_health_endpoint_exposes_versions(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert payload["schema_versions"]["quest"] == "0.1"


def test_packs_endpoints_list_and_get(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    listing = client.get("/v1/packs")
    assert listing.status_code == 200
    packs = listing.json()
    assert isinstance(packs, list)
    assert any(item.get("id") == "wellness.core.v0" for item in packs)

    pack = client.get("/v1/packs/wellness.core.v0")
    assert pack.status_code == 200
    assert pack.json()["pack"]["id"] == "wellness.core.v0"

    missing = client.get("/v1/packs/wellness.missing.v0")
    assert missing.status_code == 404


def test_profiles_endpoints_get_put_and_alignment_snapshot(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    human = client.get("/v1/profiles/human")
    agent = client.get("/v1/profiles/agent")
    assert human.status_code == 200
    assert agent.status_code == 200

    human_payload = human.json()
    human_payload["identity"]["display_name"] = "Jordan"
    update_human = client.put("/v1/profiles/human", json=human_payload)
    assert update_human.status_code == 200
    assert update_human.json()["identity"]["display_name"] == "Jordan"

    agent_payload = agent.json()
    agent_payload["identity"]["display_name"] = "Moltfred"
    update_agent = client.put("/v1/profiles/agent", json=agent_payload)
    assert update_agent.status_code == 200
    assert update_agent.json()["identity"]["display_name"] == "Moltfred"

    before = client.get("/v1/profiles/alignment_snapshot")
    assert before.status_code == 200
    generated = client.post("/v1/profiles/alignment_snapshot/generate")
    assert generated.status_code == 200
    assert generated.json()["schema_version"] == "0.1"


def test_capability_grant_requires_ticket_token(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/capabilities/grant",
        json={"capabilities": ["exec:shell"], "ttl_seconds": 300, "scope": "test"},
    )
    assert response.status_code == 422


def test_capability_grant_fails_for_invalid_ticket(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/capabilities/grant",
        headers={"X-Clawspa-Confirm": "true"},
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": "bad-token",
            "confirm": True,
        },
    )
    assert response.status_code == 400


def test_capability_grant_succeeds_with_valid_ticket(tmp_path: Path) -> None:
    service, client = _service_and_client(tmp_path)
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=600, scope="test", reason="human approved")
    response = client.post(
        "/v1/capabilities/grant",
        headers={"X-Clawspa-Confirm": "true"},
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
            "confirm": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "test"


def test_capability_grant_rejects_ttl_exceeding_ticket_window(tmp_path: Path) -> None:
    service, client = _service_and_client(tmp_path)
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=1, scope="test", reason="human approved")
    response = client.post(
        "/v1/capabilities/grant",
        headers={"X-Clawspa-Confirm": "true"},
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
            "confirm": True,
        },
    )
    assert response.status_code == 400


def test_pack_sync_route_not_shadowed_by_pack_id(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post("/v1/packs/sync")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "lint_errors"}
    assert payload["pack_count"] >= 1


def test_pack_sync_reload_includes_local_pack_sources(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    extra_root = tmp_path / "pack-sources"
    pack_dir = extra_root / "wellness.test.sync.v0"
    _write(
        pack_dir / "quests" / "wellness.test.sync.quest.v1.quest.yaml",
        """
schema_version: 0.1
quest:
  id: "wellness.test.sync.quest.v1"
  title: "Sync Source Quest"
  summary: "Test quest for local pack source reload."
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
  tags: ["timebox:1", "sync-test"]
""",
    )
    _write(
        pack_dir / "pack.yaml",
        """
pack_version: 0.1
pack:
  id: "wellness.test.sync.v0"
  title: "Sync Source Pack"
  publisher:
    name: "Agent Wellness Project"
    id: "org.agentwellness"
    contact: "security@agentwellness.example"
  version: "0.1.0"
  license: "Apache-2.0"
  created_at: "2026-02-11"
  quests:
    - "wellness.test.sync.quest.v1"
""",
    )

    os.environ["CLAWSPA_LOCAL_PACK_SOURCES"] = str(extra_root)
    try:
        synced = client.post("/v1/packs/sync")
    finally:
        os.environ.pop("CLAWSPA_LOCAL_PACK_SOURCES", None)
    assert synced.status_code == 200
    payload = synced.json()
    assert str(extra_root.resolve()) in payload["sources"]


def test_capability_grant_requires_explicit_dual_confirmation(tmp_path: Path) -> None:
    service, client = _service_and_client(tmp_path)
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=600, scope="test", reason="human approved")

    body_only = client.post(
        "/v1/capabilities/grant",
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
            "confirm": True,
        },
    )
    assert body_only.status_code == 400

    header_only = client.post(
        "/v1/capabilities/grant",
        headers={"X-Clawspa-Confirm": "true"},
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
            "confirm": False,
        },
    )
    assert header_only.status_code == 400


def test_capability_revoke_endpoint(tmp_path: Path) -> None:
    service, client = _service_and_client(tmp_path)
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=600, scope="test", reason="human approved")
    granted = client.post(
        "/v1/capabilities/grant",
        headers={"X-Clawspa-Confirm": "true"},
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
            "confirm": True,
        },
    )
    assert granted.status_code == 200
    grant_id = granted.json()["grant_id"]

    revoked = client.post("/v1/capabilities/revoke", json={"grant_id": grant_id})
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 1


def test_proof_submission_rejects_secret_like_artifacts(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/proofs",
        json={
            "quest_id": "wellness.identity.anchor.mission_statement.v1",
            "tier": "P0",
            "artifacts": [{"ref": "AKIA1234567890ABCDEF"}],
            "mode": "agent",
        },
    )
    assert response.status_code == 400


def test_proof_submission_invalid_quest_returns_404(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/proofs",
        json={
            "quest_id": "wellness.missing.quest.v1",
            "tier": "P0",
            "artifacts": [{"ref": "safe summary"}],
            "mode": "agent",
        },
    )
    assert response.status_code == 404


def test_mcp_header_sets_event_source(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/plans/daily/generate",
        params={"date": "2026-02-10"},
        headers={
            "X-Clawspa-Source": "mcp",
            "X-Clawspa-Actor": "agent",
            "X-Clawspa-Actor-Id": "openclaw:moltfred",
        },
    )
    assert response.status_code == 200

    events = _events(tmp_path)
    plan_events = [event for event in events if event.get("event_type") == "plan.generated"]
    assert plan_events
    assert plan_events[-1]["source"] == "mcp"
    assert plan_events[-1]["actor"] == {"kind": "agent", "id": "openclaw:moltfred"}


def test_trace_id_header_echo_and_telemetry_propagation(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    trace_id = "mcp:test-trace-id"
    response = client.post(
        "/v1/plans/daily/generate",
        params={"date": "2026-02-10"},
        headers={
            "X-Clawspa-Source": "mcp",
            "X-Clawspa-Actor": "agent",
            "X-Clawspa-Actor-Id": "openclaw:moltfred",
            "X-Clawspa-Trace-Id": trace_id,
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-clawspa-trace-id") == trace_id

    events = _events(tmp_path)
    plan_events = [event for event in events if event.get("event_type") == "plan.generated"]
    assert plan_events[-1].get("trace_id") == trace_id


def test_actor_id_falls_back_to_source_unknown(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/plans/daily/generate",
        params={"date": "2026-02-10"},
        headers={"X-Clawspa-Source": "mcp", "X-Clawspa-Actor": "agent"},
    )
    assert response.status_code == 200
    events = _events(tmp_path)
    plan_events = [event for event in events if event.get("event_type") == "plan.generated"]
    assert plan_events[-1]["actor"] == {"kind": "agent", "id": "mcp:unknown"}


def test_actor_id_header_precedence_over_body_actor_id(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/proofs",
        headers={"X-Clawspa-Actor-Id": "openclaw:moltfred"},
        json={
            "quest_id": "wellness.identity.anchor.mission_statement.v1",
            "tier": "P0",
            "artifacts": [{"ref": "safe summary"}],
            "mode": "agent",
            "actor_id": "agent:body-actor",
        },
    )
    assert response.status_code == 200
    events = _events(tmp_path)
    proof_events = [event for event in events if event.get("event_type") == "proof.submitted"]
    assert proof_events
    assert proof_events[-1]["actor"] == {"kind": "agent", "id": "openclaw:moltfred"}


def test_actor_id_body_used_when_header_missing(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/proofs",
        json={
            "quest_id": "wellness.identity.anchor.mission_statement.v1",
            "tier": "P0",
            "artifacts": [{"ref": "safe summary"}],
            "mode": "agent",
            "actor_id": "openclaw:moltfred",
        },
    )
    assert response.status_code == 200
    events = _events(tmp_path)
    proof_events = [event for event in events if event.get("event_type") == "proof.submitted"]
    assert proof_events
    assert proof_events[-1]["actor"] == {"kind": "agent", "id": "openclaw:moltfred"}


def test_list_proofs_date_range_supports_relative_and_absolute(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    created = client.post(
        "/v1/proofs",
        json={
            "quest_id": "wellness.identity.anchor.mission_statement.v1",
            "tier": "P0",
            "artifacts": [{"ref": "safe summary"}],
            "mode": "agent",
        },
    )
    assert created.status_code == 200

    relative = client.get("/v1/proofs", params={"date_range": "7d"})
    assert relative.status_code == 200
    assert len(relative.json()) >= 1

    absolute = client.get("/v1/proofs", params={"date_range": "2026-01-01..2026-12-31"})
    assert absolute.status_code == 200
    assert isinstance(absolute.json(), list)


def test_list_proofs_invalid_date_range_rejected(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/proofs", params={"date_range": "2026/01/01-2026/02/01"})
    assert response.status_code == 400


def test_scorecard_export_is_redacted(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    client.post(
        "/v1/proofs",
        json={
            "quest_id": "wellness.identity.anchor.mission_statement.v1",
            "tier": "P0",
            "artifacts": [{"ref": "safe summary"}],
            "mode": "agent",
        },
    )
    exported = client.get("/v1/scorecard/export")
    assert exported.status_code == 200
    payload = exported.json()
    for row in payload.get("recent_completions", []):
        assert "proof_id" not in row
