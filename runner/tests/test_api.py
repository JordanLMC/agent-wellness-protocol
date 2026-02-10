from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from clawspa_runner.api import create_app
from clawspa_runner.service import RunnerService


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _client(tmp_path: Path) -> TestClient:
    os.environ["AGENTWELLNESS_HOME"] = str(tmp_path / "home")
    service = RunnerService.create(_repo_root())
    app = create_app(service)
    return TestClient(app)


def test_daily_plan_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/v1/plans/daily", params={"date": "2026-02-09"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["quest_ids"]) >= 3


def test_capability_grant_requires_confirmation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/v1/capabilities/grant",
        json={"capabilities": ["exec:shell"], "ttl_seconds": 300, "scope": "test", "confirmed": False},
    )
    assert response.status_code == 400
