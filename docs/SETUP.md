# SETUP.md
Version: v0.1
Status: Draft
Last updated: 2026-02-13
Owner: Project Team

## Purpose

This is the setup source of truth for running ClawSpa locally in Safe Mode.

Platform pages:
- macOS: `docs/SETUP_MAC.md`
- Windows (WSL2 + PowerShell): `docs/SETUP_WINDOWS.md`

## What you get

After setup, you can run:
- Runner CLI (`runner`) for plans, proofs, scorecard, telemetry, and feedback.
- Local Runner API on loopback (`127.0.0.1`) for UI/agent/MCP access.
- MCP bridge (`clawspa-mcp`) as stdio tool server over the local API.
- Local-first storage in `~/.agentwellness/` (no cloud sync by default).

## Security defaults

- Safe Mode is the default posture.
- No secrets collection in quests, proofs, telemetry, or feedback.
- API should bind to loopback only: `runner api --host 127.0.0.1 --port 8000`.
- Do not bind API to `0.0.0.0` by default.

If you intentionally bind to LAN, you are responsible for strict firewall and allowlist controls.

## Local data locations

- Profiles: `~/.agentwellness/profiles/`
- Telemetry: `~/.agentwellness/telemetry/`
- Feedback: `~/.agentwellness/feedback/`
- Baselines: `~/.agentwellness/baselines/`

## Common verification checklist

Run these from the repo root after install:

```bash
python -m quest_lint quests --format text
python -m pytest --basetemp .pytest_tmp
python scripts/check_bidi.py .
runner profile init
runner api --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
curl http://127.0.0.1:8000/v1/health
```

Expected output shape:

```json
{"status":"ok","version":"0.1","schema_versions":{"quest":"0.1","profile":"0.1"}}
```

Expected command outcomes:
- `quest_lint`: `No findings.`
- `pytest`: test suite completes with all passing.
- `check_bidi`: `No suspicious Unicode controls found.`
- `runner profile init`: JSON payload with initialized profile paths.

## Optional background API service

Keep loopback bind and write logs to local home only.

macOS example:

```bash
nohup runner api --host 127.0.0.1 --port 8000 > ~/.agentwellness/api.log 2>&1 &
```

Windows PowerShell example:

```powershell
Start-Process -FilePath "runner" -ArgumentList "api --host 127.0.0.1 --port 8000" -RedirectStandardOutput "$HOME\.agentwellness\api.log" -RedirectStandardError "$HOME\.agentwellness\api.log"
```

## Remote agent access (keep API local-first)

Goal: let an agent on another machine call the API without exposing public ports.

Pattern 1 (preferred): SSH local port forward

On the agent machine:

```bash
ssh -L 8000:127.0.0.1:8000 user@host
```

Then the agent calls:

```text
http://127.0.0.1:8000/v1/...
```

Pattern 2: Tailscale SSH

Use the same forwarding concept over Tailscale SSH. Keep the runner API bound to `127.0.0.1` on host.

Warning:
- Do not bind runner API to `0.0.0.0` by default.
- Do not expose an unauthenticated API listener directly to the public internet.
