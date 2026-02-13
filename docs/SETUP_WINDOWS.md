# SETUP_WINDOWS.md
Version: v0.1
Status: Draft
Last updated: 2026-02-13
Owner: Project Team

Use `docs/SETUP.md` as the primary setup contract. This page is Windows-specific.

## Option 1 (recommended): WSL2 Ubuntu

This is closest to Linux/macOS behavior and usually simplest for Python tooling.

### Prerequisites

- WSL2 with an Ubuntu distribution installed.
- Python 3.12+, `venv`, and `pip` installed inside WSL.

### Install

In WSL terminal:

```bash
git clone <repo-url>
cd agent-wellness-protocol
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify

```bash
python -m quest_lint quests --format text
python -m pytest --basetemp .pytest_tmp
python scripts/check_bidi.py .
runner profile init
```

### Start API and verify

```bash
runner api --host 127.0.0.1 --port 8000
```

In a second WSL terminal:

```bash
curl http://127.0.0.1:8000/v1/health
```

Note: local-first paths are in WSL home, such as `~/.agentwellness/`.

### Agent Quickstart (copy/paste)

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

## Option 2: Native Windows (PowerShell)

### Prerequisites

- Python 3.12 installed (Microsoft Store or python.org distribution).
- PowerShell 5+ or PowerShell 7+.

### Install

```powershell
git clone <repo-url>
cd agent-wellness-protocol
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

If script execution is blocked for activation, use the current-process scope only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### Verify

```powershell
py -m quest_lint quests --format text
py -m pytest --basetemp .pytest_tmp
py scripts\check_bidi.py .
runner profile init
```

Expected outputs:
- `No findings.` from quest lint.
- all tests pass in pytest output.
- `No suspicious Unicode controls found.` from bidi check.

### Start API and verify

```powershell
runner api --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
curl.exe http://127.0.0.1:8000/v1/health
```

### Agent Quickstart (copy/paste)

Please keep proofs redacted and do not include secrets.

Window A:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
runner profile init
runner api --host 127.0.0.1 --port 8000
```

Window B:

```powershell
.venv\Scripts\Activate.ps1
runner plan --date 2026-02-13 --actor-id openclaw:moltfred
runner complete --quest wellness.identity.anchor.mission_statement.v1 --tier P0 --artifact mission-summary --actor agent --actor-id openclaw:moltfred
runner scorecard
runner telemetry verify
```
