# TELEMETRY.md
Version: v0.1
Status: Draft
Last updated: 2026-02-10
Owner: Project Team

## Purpose

Telemetry v0 provides local-first, privacy-preserving tracking so operators can measure wellness outcomes over time without creating a new data leak path.

## Storage model

- Path: `~/.agentwellness/telemetry/events.jsonl`
- Format: JSON Lines (one JSON object per line)
- Write model: append-only
- Network: none (no background uploads, no cloud sync)

## Event schema (v0.1)

Every event includes:

- `schema_version`: `"0.1"`
- `event_id`: UUIDv4
- `ts`: RFC3339 UTC timestamp
- `event_type`: one of
  - `runner.started`
  - `plan.generated`
  - `proof.submitted`
  - `quest.completed`
  - `quest.failed`
  - `scorecard.updated`
  - `profile.updated`
  - `capability.granted`
  - `capability.revoked`
  - `risk.flagged`
- `actor`
  - `kind`: `human | agent | system`
  - `id`: optional-at-source but persisted with fallback `"unknown"` (for example `openclaw:moltfred`, `human:jordan`)
- `source`: `cli | api | mcp`
- `build`
  - `runner_version`
  - `git_sha` (if available)
  - `python_version`
  - `platform`
- `data`: sanitized event payload

## Data minimization and secret safety

Telemetry is redacted-by-design:

- Never stores raw secrets, tokens, private keys, seed phrases, or `.env` contents.
- Never stores raw tool outputs, full logs, or raw artifact text.
- For proof-related events, logs only metadata such as:
  - quest id
  - proof tier
  - artifact type
  - byte size
  - sha256
- Long strings are truncated to prevent accidental dumping.
- Secret/PII-like values are replaced with `[redacted]`.
- Actor ids are sanitized with the same policy (control chars removed, secret-like values redacted, oversized values truncated).
- If sanitizer actions occur, the system appends a `risk.flagged` event with:
  - `reason: telemetry_sanitized`
  - `fields_redacted_count`
  - `fields_truncated_count`

Backward compatibility:
- Older events with string `actor` or missing `actor.id` are normalized at read/export time.

## CLI operations

```bash
# show telemetry status
runner telemetry status

# export aggregated, shareable metrics only
runner telemetry export --range 7d --out ./telemetry-summary.json

# export metrics for a specific actor id only
runner telemetry export --range 1d --actor-id openclaw:moltfred --out ./moltfred-summary.json

# purge local telemetry events
runner telemetry purge
```

Range format:

- `Nd` for days (example: `7d`)
- `Nh` for hours (example: `24h`)

## Export format

`runner telemetry export` writes aggregate metrics only, including:

- `completions_total`
- `completions_by_actor`
- `completions_by_actor_kind`
- `completions_by_actor_id`
- `completions_by_source`
- `events_by_actor_kind`
- `events_by_actor_id`
- `completions_by_proof_tier`
- `daily_streak`, `weekly_streak`, `total_xp`
- `plans_generated`, `avg_quests_per_plan`
- `quest_success_rate`
- `failures_by_reason`
- `risk_flags_count`
- `top_quests_completed`
- `timebox_estimates_sum`
- `observed_duration_sum`

No raw events are included in export.
