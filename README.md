# ClawSpa v0.1

ClawSpa is a local-first Agent Wellness System for persistent, identity-bearing, tool-using agents (OpenClaw-class) and their humans.

## What this repo contains

- `docs/`: source-of-truth contract docs
- `research/`: local pillar research reports used to derive quests
- `quests/`: versioned quest packs + quest-lint tool
- `runner/`: local runner CLI + localhost API
- `mcp-server/`: thin MCP wrapper over the local API

## Quickstart: macOS / Windows

- Setup overview (single source of truth): `docs/SETUP.md`
- macOS setup: `docs/SETUP_MAC.md`
- Windows setup (WSL2 + PowerShell): `docs/SETUP_WINDOWS.md`
- Purpose presets overview: `docs/PRESETS.md`

## Safety posture

- Default is Safe Mode.
- No secrets collection (no keys/tokens/.env content requests).
- Quest content is treated as untrusted supply chain input.
- XP/streaks never grant authority.

## Developer quickstart

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Copy/paste commands

```bash
# lint all quest content
quest-lint quests

# run tests
pytest

# run full local verification sequence
./scripts/verify.sh

# show daily plan
runner plan --date 2026-02-09

# initialize local profiles (~/.agentwellness/profiles)
runner profile init

# record quest completion
runner complete --quest wellness.security.permissions.permission_inventory.v1 --tier P1 --artifact notes/permission-summary.md

# print scorecard
runner scorecard

# export scorecard json
runner export-scorecard --out ./scorecard.json

# run local API (localhost only)
runner api --host 127.0.0.1 --port 8000

# create human approval ticket and grant scoped capability
runner capability ticket --cap exec:shell --ttl-seconds 900 --scope maintenance --reason "human approved"
runner capability grant --cap exec:shell --ttl-seconds 300 --scope maintenance --ticket <ticket_token>

# telemetry status + export + purge
runner telemetry status
runner telemetry verify
runner telemetry export --range 7d --out ./telemetry-summary.json
runner telemetry snapshot --range 7d --actor-id openclaw:moltfred
runner telemetry diff --a ./baseline-a.json --b ./baseline-b.json --format text
runner telemetry purge --older-than 30d
runner proofs purge --older-than 90d

# run MCP stdio wrapper against local API
clawspa-mcp --api-base http://127.0.0.1:8000
```

## Notes

- API endpoints are defined in `docs/API_SURFACE.md` and implemented under `runner/`.
- Pack inventory and intended use live in `docs/PACKS.md`.
- Core quest pack v0 lives in `quests/packs/wellness.core.v0/`.
- Telemetry policy and event model are documented in `docs/TELEMETRY.md`.
