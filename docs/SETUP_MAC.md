# SETUP_MAC.md
Version: v0.1
Status: Draft
Last updated: 2026-02-13
Owner: Project Team

Use `docs/SETUP.md` as the primary setup contract. This page is macOS-specific.

## Prerequisites

- Xcode Command Line Tools installed.
- Python 3.12+ available (`python3 --version`).
- Homebrew is optional but recommended for Python management.

## Install

```bash
git clone <repo-url>
cd agent-wellness-protocol
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Verify

```bash
python -m quest_lint quests --format text
python -m pytest --basetemp .pytest_tmp
python scripts/check_bidi.py .
runner profile init
```

Expected outputs:
- `No findings.` from quest lint.
- all tests pass in pytest output.
- `No suspicious Unicode controls found.` from bidi check.

## Start local API (safe default)

```bash
runner api --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/v1/health
```

Expected output shape:

```json
{"status":"ok","version":"0.1","schema_versions":{"quest":"0.1","profile":"0.1"}}
```

## MCP usage

Run MCP bridge over stdio against local API:

```bash
clawspa-mcp --api-base http://127.0.0.1:8000
```

When calling API endpoints directly, pass actor headers:
- `X-Clawspa-Source: mcp`
- `X-Clawspa-Actor: agent`
- `X-Clawspa-Actor-Id: openclaw:moltfred`
- `X-Clawspa-Trace-Id: mcp:<trace>`

## Agent Quickstart (copy/paste)

Please keep proofs redacted and do not include secrets.

Terminal A:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
runner profile init
runner api --host 127.0.0.1 --port 8000
```

Terminal B:

```bash
source .venv/bin/activate
runner plan --date 2026-02-13 --actor-id openclaw:moltfred
runner complete --quest wellness.identity.anchor.mission_statement.v1 --tier P0 --artifact mission-summary --actor agent --actor-id openclaw:moltfred
runner scorecard
runner telemetry verify
```
