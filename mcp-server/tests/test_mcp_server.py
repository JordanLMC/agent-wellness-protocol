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


def test_validate_tool_arguments_rejects_large_profile_patch() -> None:
    large_patch = {"notes": "a" * 9000}
    with pytest.raises(ValueError, match="exceeds"):
        validate_tool_arguments("update_agent_profile", {"profile_patch": large_patch})


def test_validate_tool_arguments_rejects_secret_profile_patch() -> None:
    with pytest.raises(ValueError, match="secret-like"):
        validate_tool_arguments("update_agent_profile", {"profile_patch": {"token": "sk-abcdefghijklmnop"}})
