#!/usr/bin/env python3
"""Local smoke test for runner API + MCP stdio bridge."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def _wait_for_health(api_base: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    url = f"{api_base}/v1/health"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # nosec B310
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") == "ok":
                    return
        except URLError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Runner API did not become healthy in time.")


def _rpc(proc: subprocess.Popen[str], request_id: int, method: str, params: dict | None = None) -> dict:
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("MCP process stdio is unavailable.")
    message = {"id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()

    line = proc.stdout.readline()
    if not line:
        stderr_output = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"No response from MCP process. stderr: {stderr_output}")
    payload = json.loads(line)
    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message", "Unknown MCP error"))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test runner API + MCP bridge")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    api_base = f"http://127.0.0.1:{args.port}"

    with tempfile.TemporaryDirectory(prefix="clawspa-smoke-") as tmp_home:
        env = os.environ.copy()
        env["AGENTWELLNESS_HOME"] = tmp_home

        api_proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "clawspa_runner.cli", "api", "--host", "127.0.0.1", "--port", str(args.port)],
            cwd=repo_root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        mcp_proc: subprocess.Popen[str] | None = None
        try:
            _wait_for_health(api_base)
            mcp_proc = subprocess.Popen(  # noqa: S603
                [sys.executable, "-m", "clawspa_mcp.server", "--api-base", api_base],
                cwd=repo_root,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            _rpc(mcp_proc, 1, "initialize")
            daily = _rpc(
                mcp_proc,
                2,
                "tools/call",
                {"name": "get_daily_quests", "arguments": {"date": date.today().isoformat()}},
            )
            content = daily.get("result", {}).get("content", {})
            if "quest_ids" not in content:
                raise RuntimeError("get_daily_quests did not return quest_ids.")

            _rpc(
                mcp_proc,
                3,
                "tools/call",
                {
                    "name": "submit_proof",
                    "arguments": {
                        "quest_id": "wellness.identity.anchor.mission_statement.v1",
                        "tier": "P0",
                        "artifacts": [{"ref": "mcp smoke summary"}],
                    },
                },
            )
            print("MCP smoke test passed.")
            return 0
        finally:
            if mcp_proc is not None and mcp_proc.poll() is None:
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()
            if api_proc.poll() is None:
                api_proc.terminate()
                try:
                    api_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    api_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
