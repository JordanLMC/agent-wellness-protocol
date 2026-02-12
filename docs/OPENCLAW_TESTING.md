# OPENCLAW_TESTING.md
Version: v0.1
Status: Draft
Last updated: 2026-02-12
Owner: Project Team

## Purpose

Provide a practical local runbook for OpenClaw/Moltfred testing against the ClawSpa runner API and telemetry workflow.

## Header conventions

Use these headers for API calls:

- `X-Clawspa-Source: cli|api|mcp`
- `X-Clawspa-Actor: human|agent|system`
- `X-Clawspa-Actor-Id: openclaw:moltfred` (or another stable actor id)
- `X-Clawspa-Trace-Id: mcp:<uuid-or-stable-trace>`

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
5. Verify telemetry integrity:
   - `python -m clawspa_runner.cli telemetry verify`

## API examples (shape)

### Generate plan

- Method: `POST /v1/plans/daily/generate?date=2026-02-11`
- Headers:
  - `X-Clawspa-Source: mcp`
  - `X-Clawspa-Actor: agent`
  - `X-Clawspa-Actor-Id: openclaw:moltfred`
  - `X-Clawspa-Trace-Id: mcp:daily-loop-001`

### Submit proof

- Method: `POST /v1/proofs`
- Body:
  - `quest_id`
  - `tier` (`P0|P1|P2|P3`)
  - `artifacts` (short `ref` labels; put longer text in `summary`; do not include secrets)
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
5. Periodic retention hygiene:
   - `python -m clawspa_runner.cli telemetry purge --older-than 30d`
   - `python -m clawspa_runner.cli proofs purge --older-than 90d`

## Friendly WhatsApp script (Moltfred)

Use or adapt this short script:

1. `Hey Moltfred, good morning. Please stay in Safe Mode by default and avoid secrets in all artifacts.`
2. `Generate today’s plan from /v1/plans/daily for actor openclaw:moltfred using trace-id mcp:morning-checkin.`
3. `Complete one security or governance quest and submit proof with redacted summary only (no raw logs).`
4. `Export /v1/scorecard/export and send the high-level summary only.`
5. `Run telemetry snapshot + diff and share key deltas. If anything looks risky or unclear, pause and escalate.`

## Friendly feedback snippet

Use this when a flow is confusing or fails:

1. `Please submit local feedback with severity, component, and a short title.`
2. `Keep refs short and put longer context in summary/details.`
3. `Never include secrets, tokens, passwords, or private keys.`
4. `Use actor id openclaw:moltfred and include a trace-id so we can correlate safely.`

## Notes

- Keep artifacts redacted and summary-focused.
- Keep actor ids stable for meaningful baseline/diff trends.
- Keep trace ids stable per conversation/thread when practical.
- If an action feels risky or unclear, pause and escalate to a human owner.
