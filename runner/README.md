# Runner

Local-first ClawSpa runner.

## Features (v0.1)

- Loads quest packs from `quests/packs/`
- Enforces quest-lint validation before planning
- Generates deterministic daily plans
- Records completions, streaks, XP, and proof envelopes locally
- Supports Safe Mode defaults and time-limited capability grants
- Exposes localhost API mapped to `docs/API_SURFACE.md`

## CLI examples

```bash
runner plan --date 2026-02-09
runner complete --quest wellness.identity.anchor.mission_statement.v1 --tier P0 --artifact "daily mission anchor"
runner scorecard
runner export-scorecard --out ./scorecard.json
runner profile init
runner capability ticket --cap exec:shell --ttl-seconds 900 --scope maintenance --reason "human approved"
runner capability grant --cap exec:shell --ttl-seconds 300 --scope maintenance --ticket <ticket_token>
runner api --host 127.0.0.1 --port 8000
```
