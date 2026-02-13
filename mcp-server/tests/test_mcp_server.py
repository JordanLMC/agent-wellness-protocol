from __future__ import annotations

import pytest

from clawspa_mcp.server import MCPBridge, deep_merge, validate_api_base, validate_tool_arguments


def test_deep_merge_nested() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    patch = {"nested": {"y": 9, "z": 3}}
    merged = deep_merge(base, patch)
    assert merged == {"a": 1, "nested": {"x": 1, "y": 9, "z": 3}}


def test_tool_unknown_raises() -> None:
    bridge = MCPBridge("http://127.0.0.1:8000")
    try:
        bridge.call_tool("unknown_tool", {})
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_validate_api_base_localhost_allowed() -> None:
    value = validate_api_base("http://localhost:8000")
    assert value == "http://localhost:8000"


def test_validate_api_base_nonlocal_rejected_by_default() -> None:
    with pytest.raises(ValueError, match="localhost"):
        validate_api_base("https://example.com")


def test_validate_api_base_nonlocal_allowed_with_override() -> None:
    value = validate_api_base("https://example.com", allow_nonlocal=True)
    assert value == "https://example.com"


def test_validate_api_base_rejects_userinfo() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        validate_api_base("http://user:pass@127.0.0.1:8000")


def test_validate_api_base_rejects_bad_scheme() -> None:
    with pytest.raises(ValueError, match="http or https"):
        validate_api_base("ftp://127.0.0.1")


def test_validate_tool_arguments_rejects_bad_date() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_tool_arguments("get_daily_quests", {"date": "09-02-2026"})


def test_validate_tool_arguments_rejects_secret_like_submit_proof() -> None:
    with pytest.raises(ValueError, match="secret-like"):
        validate_tool_arguments(
            "submit_proof",
            {
                "quest_id": "wellness.identity.anchor.mission_statement.v1",
                "tier": "P1",
                "artifacts": [{"ref": "sk-abcdefghijklmnop"}],
            },
        )


def test_validate_tool_arguments_rejects_path_like_proof_ref() -> None:
    with pytest.raises(ValueError, match="path separators"):
        validate_tool_arguments(
            "submit_proof",
            {
                "quest_id": "wellness.identity.anchor.mission_statement.v1",
                "tier": "P1",
                "artifacts": [{"ref": "nested/path/ref"}],
            },
        )


def test_validate_tool_arguments_rejects_large_profile_patch() -> None:
    large_patch = {"notes": "a" * 9000}
    with pytest.raises(ValueError, match="exceeds"):
        validate_tool_arguments("update_agent_profile", {"profile_patch": large_patch})


def test_validate_tool_arguments_rejects_secret_profile_patch() -> None:
    with pytest.raises(ValueError, match="secret-like"):
        validate_tool_arguments("update_agent_profile", {"profile_patch": {"token": "sk-abcdefghijklmnop"}})


def test_validate_tool_arguments_submit_feedback_rejects_secret_details() -> None:
    with pytest.raises(ValueError, match="secret-like"):
        validate_tool_arguments(
            "submit_feedback",
            {
                "severity": "medium",
                "component": "proofs",
                "title": "Proof issue",
                "details": "sk-abcdefghijklmnop",
            },
        )


def test_mcp_request_sets_source_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def _fake_urlopen(request, timeout=10):  # noqa: ANN001
        headers = {key.lower(): value for key, value in request.header_items()}
        captured["source"] = headers.get("x-clawspa-source")
        captured["actor"] = headers.get("x-clawspa-actor")
        captured["actor_id"] = headers.get("x-clawspa-actor-id")
        captured["trace_id"] = headers.get("x-clawspa-trace-id")
        return _DummyResponse()

    monkeypatch.setattr("clawspa_mcp.server.urlopen", _fake_urlopen)
    bridge = MCPBridge("http://127.0.0.1:8000", actor_id="openclaw:moltfred")
    bridge._request("GET", "/v1/health")

    assert captured["source"] == "mcp"
    assert captured["actor"] == "agent"
    assert captured["actor_id"] == "openclaw:moltfred"
    assert captured["trace_id"].startswith("mcp:")


def test_mcp_tool_actor_id_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def _fake_urlopen(request, timeout=10):  # noqa: ANN001
        headers = {key.lower(): value for key, value in request.header_items()}
        captured["actor_id"] = headers.get("x-clawspa-actor-id")
        captured["trace_id"] = headers.get("x-clawspa-trace-id")
        return _DummyResponse()

    monkeypatch.setattr("clawspa_mcp.server.urlopen", _fake_urlopen)
    bridge = MCPBridge("http://127.0.0.1:8000", actor_id="mcp:unknown")
    bridge.call_tool(
        "get_daily_quests",
        {"date": "2026-02-10", "actor_id": "openclaw:moltfred", "trace_id": "mcp:manual-trace"},
    )
    assert captured["actor_id"] == "openclaw:moltfred"
    assert captured["trace_id"] == "mcp:manual-trace"


def test_mcp_submit_feedback_calls_feedback_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def _fake_urlopen(request, timeout=10):  # noqa: ANN001
        captured["url"] = request.full_url
        headers = {key.lower(): value for key, value in request.header_items()}
        captured["trace_id"] = headers.get("x-clawspa-trace-id")
        captured["body"] = request.data.decode("utf-8")
        return _DummyResponse()

    monkeypatch.setattr("clawspa_mcp.server.urlopen", _fake_urlopen)
    bridge = MCPBridge("http://127.0.0.1:8000", actor_id="openclaw:moltfred")
    bridge.call_tool(
        "submit_feedback",
        {
            "severity": "low",
            "component": "proofs",
            "title": "UX note",
            "summary": "short ref guidance helped",
            "trace_id": "mcp:feedback-test",
        },
    )
    assert captured["url"].endswith("/v1/feedback")
    assert captured["trace_id"] == "mcp:feedback-test"
    assert "\"component\": \"proofs\"" in captured["body"]


def test_validate_tool_arguments_apply_preset_requires_valid_id() -> None:
    with pytest.raises(ValueError, match="preset_id"):
        validate_tool_arguments("apply_preset", {"preset_id": "Not Valid"})


def test_mcp_list_presets_calls_presets_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return b"[]"

    def _fake_urlopen(request, timeout=10):  # noqa: ANN001
        captured["url"] = request.full_url
        return _DummyResponse()

    monkeypatch.setattr("clawspa_mcp.server.urlopen", _fake_urlopen)
    bridge = MCPBridge("http://127.0.0.1:8000", actor_id="openclaw:moltfred")
    bridge.call_tool("list_presets", {"trace_id": "mcp:preset-list"})
    assert captured["url"].endswith("/v1/presets")


def test_mcp_apply_preset_calls_apply_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def _fake_urlopen(request, timeout=10):  # noqa: ANN001
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        return _DummyResponse()

    monkeypatch.setattr("clawspa_mcp.server.urlopen", _fake_urlopen)
    bridge = MCPBridge("http://127.0.0.1:8000", actor_id="openclaw:moltfred")
    bridge.call_tool(
        "apply_preset",
        {"preset_id": "builder.v0", "trace_id": "mcp:preset-apply"},
    )
    assert captured["url"].endswith("/v1/presets/apply")
    assert "\"preset_id\": \"builder.v0\"" in captured["body"]
