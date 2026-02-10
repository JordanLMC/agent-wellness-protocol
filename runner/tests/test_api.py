from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from clawspa_runner.api import create_app
from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def test_quests_search_route_not_shadowed(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.get("/v1/quests/search", params={"mode": "safe"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


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
        json={"capabilities": ["exec:shell"], "ttl_seconds": 300, "scope": "test", "ticket_token": "bad-token"},
    )
    assert response.status_code == 400


def test_capability_grant_succeeds_with_valid_ticket(tmp_path: Path) -> None:
    service, client = _service_and_client(tmp_path)
    ticket = service.create_grant_ticket(["exec:shell"], ttl_seconds=600, scope="test", reason="human approved")
    response = client.post(
        "/v1/capabilities/grant",
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
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
        json={
            "capabilities": ["exec:shell"],
            "ttl_seconds": 300,
            "scope": "test",
            "ticket_token": ticket["token"],
        },
    )
    assert response.status_code == 400


def test_pack_sync_route_not_shadowed_by_pack_id(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post("/v1/packs/sync")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "noop"


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


def test_mcp_header_sets_event_source(tmp_path: Path) -> None:
    _, client = _service_and_client(tmp_path)
    response = client.post(
        "/v1/plans/daily/generate",
        params={"date": "2026-02-10"},
        headers={"X-Clawspa-Source": "mcp", "X-Clawspa-Actor": "agent"},
    )
    assert response.status_code == 200

    events = _events(tmp_path)
    plan_events = [event for event in events if event.get("event_type") == "plan.generated"]
    assert plan_events
    assert plan_events[-1]["source"] == "mcp"
    assert plan_events[-1]["actor"] == "agent"
