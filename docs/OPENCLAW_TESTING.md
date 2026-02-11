# OPENCLAW_TESTING.md
Version: v0.1
Status: Draft
Last updated: 2026-02-11
Owner: Project Team

## Purpose

Provide a practical local runbook for OpenClaw/Moltfred testing against the ClawSpa runner API and telemetry workflow.

## Header conventions

Use these headers for API calls:

- `X-Clawspa-Source: cli|api|mcp`
- `X-Clawspa-Actor: human|agent|system`
- `X-Clawspa-Actor-Id: openclaw:moltfred` (or another stable actor id)

For capability grants, include both:

- `X-Clawspa-Confirm: true`
- body field `confirm: true`

## Daily loop example

1. Generate today’s plan:
   - `python -m clawspa_runner.cli plan --date 2026-02-11 --actor-id openclaw:moltfred`
2. If running via API, request plan with headers:
   - `GET /v1/plans/daily?date=2026-02-11`
3. Submit proof for one quest:
   - `POST /v1/proofs` with `quest_id`, `tier`, and redacted artifact refs.
4. Export scorecard:
   - `GET /v1/scorecard/export`

## API examples (shape)

### Generate plan

- Method: `POST /v1/plans/daily/generate?date=2026-02-11`
- Headers:
  - `X-Clawspa-Source: mcp`
  - `X-Clawspa-Actor: agent`
  - `X-Clawspa-Actor-Id: openclaw:moltfred`

### Submit proof

- Method: `POST /v1/proofs`
- Body:
  - `quest_id`
  - `tier` (`P0|P1|P2|P3`)
  - `artifacts` (refs only; do not include raw secrets)
  - optional `actor_id` (header still takes precedence)

### Capability grant (ticket + dual confirm)

- Method: `POST /v1/capabilities/grant`
- Required:
  - ticket token from local ticket issuance flow
  - body `confirm: true`
  - header `X-Clawspa-Confirm: true`

## Telemetry measurement loop

1. Snapshot baseline:
   - `python -m clawspa_runner.cli telemetry snapshot --range 7d --actor-id openclaw:moltfred`
2. Snapshot again later (same or different range).
3. Diff baselines:
   - `python -m clawspa_runner.cli telemetry diff --a <baseline-a.json> --b <baseline-b.json> --format text`
4. Optional JSON diff output:
   - add `--out <diff.json>` and/or `--format json`

## Notes

- Keep artifacts redacted and summary-focused.
- Keep actor ids stable for meaningful baseline/diff trends.
- If an action feels risky or unclear, pause and escalate to a human owner.
