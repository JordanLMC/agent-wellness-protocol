from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


TOOL_SCHEMAS = [
    {
        "name": "get_daily_quests",
        "description": "Get daily quest plan for a date (defaults to today).",
        "input_schema": {"type": "object", "properties": {"date": {"type": "string"}}, "additionalProperties": False},
    },
    {
        "name": "get_quest",
        "description": "Get one quest by canonical quest_id.",
        "input_schema": {
            "type": "object",
            "properties": {"quest_id": {"type": "string"}},
            "required": ["quest_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_proof",
        "description": "Submit proof metadata for a quest completion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quest_id": {"type": "string"},
                "tier": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                "artifacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"ref": {"type": "string"}, "summary": {"type": "string"}},
                        "required": ["ref"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["quest_id", "tier", "artifacts"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_scorecard",
        "description": "Get current local scorecard.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_profiles",
        "description": "Get human, agent, and alignment profiles.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "update_agent_profile",
        "description": "Patch and update agent profile fields.",
        "input_schema": {
            "type": "object",
            "properties": {"profile_patch": {"type": "object"}},
            "required": ["profile_patch"],
            "additionalProperties": False,
        },
    },
]


class MCPBridge:
    def __init__(self, api_base: str, *, allow_nonlocal: bool = False) -> None:
        self.api_base = validate_api_base(api_base, allow_nonlocal=allow_nonlocal)

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        request = Request(url=url, method=method, headers=headers, data=data)
        try:
            with urlopen(request, timeout=10) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"API HTTP error {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"API request failed: {exc}") from exc

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "get_daily_quests":
            target = arguments.get("date") or date.today().isoformat()
            return self._request("GET", "/v1/plans/daily", params={"date": target})
        if name == "get_quest":
            return self._request("GET", f"/v1/quests/{arguments['quest_id']}")
        if name == "submit_proof":
            payload = {
                "quest_id": arguments["quest_id"],
                "tier": arguments["tier"],
                "artifacts": arguments.get("artifacts", []),
                "mode": "agent",
            }
            return self._request("POST", "/v1/proofs", body=payload)
        if name == "get_scorecard":
            return self._request("GET", "/v1/scorecard")
        if name == "get_profiles":
            return {
                "human": self._request("GET", "/v1/profiles/human"),
                "agent": self._request("GET", "/v1/profiles/agent"),
                "alignment_snapshot": self._request("GET", "/v1/profiles/alignment_snapshot"),
            }
        if name == "update_agent_profile":
            current = self._request("GET", "/v1/profiles/agent")
            merged = deep_merge(current, arguments.get("profile_patch", {}))
            return self._request("PUT", "/v1/profiles/agent", body=merged)
        raise ValueError(f"Unknown tool: {name}")


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def is_local_host(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_api_base(api_base: str, *, allow_nonlocal: bool = False) -> str:
    parsed = urlsplit(api_base)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("api-base must use http or https scheme.")
    if parsed.username or parsed.password:
        raise ValueError("api-base must not include userinfo.")
    if not parsed.hostname:
        raise ValueError("api-base must include a host.")
    if not allow_nonlocal and not is_local_host(parsed.hostname):
        raise ValueError("api-base must target localhost by default. Use --allow-nonlocal to override.")
    return api_base.rstrip("/")


def _write_response(response_id: Any, result: Any = None, error: str | None = None) -> None:
    payload: dict[str, Any] = {"id": response_id}
    if error is not None:
        payload["error"] = {"message": error}
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def serve_stdio(bridge: MCPBridge) -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _write_response(None, error="Invalid JSON input.")
            continue

        response_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})
        try:
            if method == "initialize":
                _write_response(response_id, {"server": "clawspa-mcp", "version": "0.1"})
            elif method == "tools/list":
                _write_response(response_id, {"tools": TOOL_SCHEMAS})
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = bridge.call_tool(name, arguments)
                _write_response(response_id, {"content": result})
            else:
                _write_response(response_id, error=f"Unsupported method: {method}")
        except Exception as exc:  # noqa: BLE001
            _write_response(response_id, error=str(exc))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ClawSpa MCP wrapper over local runner API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Local runner API base URL.")
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow non-local api-base hosts (off by default for safety).",
    )
    parser.add_argument("--tool", help="Optional direct tool call mode.")
    parser.add_argument("--args-json", default="{}", help="Tool arguments in JSON.")
    args = parser.parse_args()

    bridge = MCPBridge(api_base=args.api_base, allow_nonlocal=args.allow_nonlocal)
    if args.tool:
        tool_args = json.loads(args.args_json)
        print(json.dumps(bridge.call_tool(args.tool, tool_args), indent=2))
        return 0
    return serve_stdio(bridge)


if __name__ == "__main__":
    raise SystemExit(main())
