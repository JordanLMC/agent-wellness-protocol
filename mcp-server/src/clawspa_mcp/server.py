from __future__ import annotations

"""MCP bridge that forwards validated tool calls to the local runner API."""

import argparse
import ipaddress
import json
import re
import sys
import uuid
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from clawspa_runner.security import payload_contains_pii, payload_contains_secrets, payload_requests_raw_logs


QUEST_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,159}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_ARTIFACTS = 8
MAX_STRING_LENGTH = 1024
MAX_PROFILE_PATCH_BYTES = 8 * 1024


TOOL_SCHEMAS = [
    {
        "name": "get_daily_quests",
        "description": "Get daily quest plan for a date (defaults to today).",
        "input_schema": {
            "type": "object",
            "properties": {"date": {"type": "string"}, "actor_id": {"type": "string"}, "trace_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_quest",
        "description": "Get one quest by canonical quest_id.",
        "input_schema": {
            "type": "object",
            "properties": {"quest_id": {"type": "string"}, "actor_id": {"type": "string"}, "trace_id": {"type": "string"}},
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
                "actor_id": {"type": "string"},
                "trace_id": {"type": "string"},
            },
            "required": ["quest_id", "tier", "artifacts"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_scorecard",
        "description": "Get current local scorecard.",
        "input_schema": {
            "type": "object",
            "properties": {"actor_id": {"type": "string"}, "trace_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_profiles",
        "description": "Get human, agent, and alignment profiles.",
        "input_schema": {
            "type": "object",
            "properties": {"actor_id": {"type": "string"}, "trace_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "update_agent_profile",
        "description": "Patch and update agent profile fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "profile_patch": {"type": "object"},
                "actor_id": {"type": "string"},
                "trace_id": {"type": "string"},
            },
            "required": ["profile_patch"],
            "additionalProperties": False,
        },
    },
]


class MCPBridge:
    """Thin API client that injects MCP source and actor identity headers."""

    def __init__(self, api_base: str, *, allow_nonlocal: bool = False, actor_id: str = "mcp:unknown") -> None:
        self.api_base = validate_api_base(api_base, allow_nonlocal=allow_nonlocal)
        self.actor_id = actor_id

    def _new_trace_id(self) -> str:
        return f"mcp:{uuid.uuid4()}"

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        data = None
        effective_actor_id = actor_id or self.actor_id
        headers = {
            "Content-Type": "application/json",
            "X-Clawspa-Source": "mcp",
            "X-Clawspa-Actor": "agent",
            "X-Clawspa-Actor-Id": effective_actor_id,
            "X-Clawspa-Trace-Id": trace_id or self._new_trace_id(),
        }
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
        validate_tool_arguments(name, arguments)
        actor_id = arguments.get("actor_id") or self.actor_id
        trace_id = arguments.get("trace_id") or self._new_trace_id()
        if name == "get_daily_quests":
            target = arguments.get("date") or date.today().isoformat()
            return self._request(
                "GET",
                "/v1/plans/daily",
                params={"date": target},
                actor_id=actor_id,
                trace_id=trace_id,
            )
        if name == "get_quest":
            return self._request("GET", f"/v1/quests/{arguments['quest_id']}", actor_id=actor_id, trace_id=trace_id)
        if name == "submit_proof":
            payload = {
                "quest_id": arguments["quest_id"],
                "tier": arguments["tier"],
                "artifacts": arguments.get("artifacts", []),
                "mode": "agent",
                "actor_id": actor_id,
            }
            return self._request("POST", "/v1/proofs", body=payload, actor_id=actor_id, trace_id=trace_id)
        if name == "get_scorecard":
            return self._request("GET", "/v1/scorecard", actor_id=actor_id, trace_id=trace_id)
        if name == "get_profiles":
            return {
                "human": self._request("GET", "/v1/profiles/human", actor_id=actor_id, trace_id=trace_id),
                "agent": self._request("GET", "/v1/profiles/agent", actor_id=actor_id, trace_id=trace_id),
                "alignment_snapshot": self._request(
                    "GET",
                    "/v1/profiles/alignment_snapshot",
                    actor_id=actor_id,
                    trace_id=trace_id,
                ),
            }
        if name == "update_agent_profile":
            current = self._request("GET", "/v1/profiles/agent", actor_id=actor_id, trace_id=trace_id)
            merged = deep_merge(current, arguments.get("profile_patch", {}))
            return self._request("PUT", "/v1/profiles/agent", body=merged, actor_id=actor_id, trace_id=trace_id)
        raise ValueError(f"Unknown tool: {name}")


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `patch` into `base` without mutating the input mapping."""

    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_safe_text(value: str, *, field: str, max_length: int = MAX_STRING_LENGTH) -> None:
    if len(value) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters.")
    if payload_contains_secrets(value):
        raise ValueError(f"{field} appears to contain secret-like content.")
    if payload_contains_pii(value):
        raise ValueError(f"{field} appears to contain PII-like content.")
    if payload_requests_raw_logs(value):
        raise ValueError(f"{field} appears to contain raw log text.")


def _iter_strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        values: list[str] = []
        for item in node:
            values.extend(_iter_strings(item))
        return values
    if isinstance(node, dict):
        values = []
        for key, value in node.items():
            if isinstance(key, str):
                values.append(key)
            values.extend(_iter_strings(value))
        return values
    return []


def validate_tool_arguments(name: str, arguments: dict[str, Any]) -> None:
    """Validate MCP tool arguments and reject secret/PII-like payloads."""

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")

    actor_id = arguments.get("actor_id")
    if actor_id is not None:
        if not isinstance(actor_id, str):
            raise ValueError("actor_id must be a string.")
        _validate_safe_text(actor_id, field="actor_id", max_length=200)
    trace_id = arguments.get("trace_id")
    if trace_id is not None:
        if not isinstance(trace_id, str):
            raise ValueError("trace_id must be a string.")
        _validate_safe_text(trace_id, field="trace_id", max_length=200)

    if name == "get_daily_quests":
        target = arguments.get("date")
        if target is None:
            return
        if not isinstance(target, str) or not DATE_PATTERN.match(target):
            raise ValueError("date must be YYYY-MM-DD.")
        date.fromisoformat(target)
        return
    if name == "get_quest":
        quest_id = arguments.get("quest_id")
        if not isinstance(quest_id, str) or not QUEST_ID_PATTERN.match(quest_id):
            raise ValueError("quest_id must be a canonical quest identifier.")
        _validate_safe_text(quest_id, field="quest_id", max_length=160)
        return
    if name == "submit_proof":
        quest_id = arguments.get("quest_id")
        tier = arguments.get("tier")
        artifacts = arguments.get("artifacts")
        if not isinstance(quest_id, str) or not QUEST_ID_PATTERN.match(quest_id):
            raise ValueError("quest_id must be a canonical quest identifier.")
        if tier not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("tier must be one of P0|P1|P2|P3.")
        if not isinstance(artifacts, list):
            raise ValueError("artifacts must be an array.")
        if len(artifacts) > MAX_ARTIFACTS:
            raise ValueError(f"artifacts exceeds max of {MAX_ARTIFACTS}.")
        for idx, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                raise ValueError(f"artifacts[{idx}] must be an object.")
            ref = artifact.get("ref")
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError(f"artifacts[{idx}].ref is required.")
            _validate_safe_text(ref, field=f"artifacts[{idx}].ref", max_length=512)
            summary = artifact.get("summary")
            if summary is not None:
                if not isinstance(summary, str):
                    raise ValueError(f"artifacts[{idx}].summary must be a string.")
                _validate_safe_text(summary, field=f"artifacts[{idx}].summary", max_length=280)
        return
    if name == "update_agent_profile":
        patch = arguments.get("profile_patch")
        if not isinstance(patch, dict):
            raise ValueError("profile_patch must be an object.")
        payload_bytes = len(json.dumps(patch).encode("utf-8"))
        if payload_bytes > MAX_PROFILE_PATCH_BYTES:
            raise ValueError(f"profile_patch exceeds {MAX_PROFILE_PATCH_BYTES} bytes.")
        for string_value in _iter_strings(patch):
            _validate_safe_text(string_value, field="profile_patch", max_length=MAX_STRING_LENGTH)
        return
    if name in {"get_scorecard", "get_profiles"}:
        allowed = {"actor_id", "trace_id"}
        if any(key not in allowed for key in arguments):
            raise ValueError(f"{name} does not accept arguments.")
        return
    raise ValueError(f"Unknown tool: {name}")


def is_local_host(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_api_base(api_base: str, *, allow_nonlocal: bool = False) -> str:
    """Validate runner API base URL with localhost-only default safety guard."""

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
    """Serve minimal MCP-style JSON-RPC requests over stdio."""

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
    """CLI entrypoint for stdio server mode or one-shot tool invocation."""

    parser = argparse.ArgumentParser(description="ClawSpa MCP wrapper over local runner API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Local runner API base URL.")
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow non-local api-base hosts (off by default for safety).",
    )
    parser.add_argument("--actor-id", default="mcp:unknown", help="Default actor id for MCP-originated calls.")
    parser.add_argument("--tool", help="Optional direct tool call mode.")
    parser.add_argument("--args-json", default="{}", help="Tool arguments in JSON.")
    args = parser.parse_args()

    bridge = MCPBridge(api_base=args.api_base, allow_nonlocal=args.allow_nonlocal, actor_id=args.actor_id)
    if args.tool:
        tool_args = json.loads(args.args_json)
        print(json.dumps(bridge.call_tool(args.tool, tool_args), indent=2))
        return 0
    return serve_stdio(bridge)


if __name__ == "__main__":
    raise SystemExit(main())
