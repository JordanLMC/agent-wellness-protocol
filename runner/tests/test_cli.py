from __future__ import annotations

import sys

from clawspa_runner import cli


class _DummyService:
    def __init__(self) -> None:
        self.trace_id: str | None = None

    def complete_quest(  # noqa: PLR0913
        self,
        quest: str,
        tier: str,
        artifact: str,
        *,
        actor_mode: str,
        artifacts: list[dict] | None = None,
        source: str,
        actor_id: str,
        trace_id: str | None,
    ) -> dict:
        self.trace_id = trace_id
        return {"quest_id": quest, "tier": tier, "xp_awarded": 0}


def test_cli_generates_trace_id_for_completion(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    service = _DummyService()
    monkeypatch.setattr(cli, "_service", lambda: service)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "complete",
            "--quest",
            "wellness.identity.anchor.mission_statement.v1",
            "--tier",
            "P0",
            "--artifact",
            "safe summary",
        ],
    )
    result = cli.main()
    assert result == 0
    assert isinstance(service.trace_id, str)
    assert service.trace_id.startswith("cli:")
