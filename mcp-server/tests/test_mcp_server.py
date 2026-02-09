from __future__ import annotations

from clawspa_mcp.server import MCPBridge, deep_merge


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
