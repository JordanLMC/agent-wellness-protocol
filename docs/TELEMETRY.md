# TELEMETRY.md
Version: v0.1
Status: Draft
Last updated: 2026-02-13
Owner: Project Team

## Purpose

Telemetry v0 is local-first, privacy-preserving, and tamper-evident.
It supports trend measurement without collecting raw secrets or sensitive payloads.

## Storage model

- Path: `~/.agentwellness/telemetry/events.jsonl`
- Format: JSON Lines (one event per line)
- Network: none by default (no background uploads, no cloud sync)
- Retention controls:
  - `CLAWSPA_TELEMETRY_RETENTION_DAYS` (default `30`)
  - `CLAWSPA_PROOFS_RETENTION_DAYS` (default `90`)

## Event schema (v0.1)

Every event includes:

- `schema_version`: `"0.1"`
- `event_id`: UUIDv4
- `ts`: RFC3339 UTC timestamp
- `event_type`:
  - `runner.started`
  - `plan.generated`
  - `proof.submitted`
  - `proof.rejected`
  - `quest.completed`
  - `quest.failed`
  - `scorecard.updated`
  - `profile.updated`
  - `capability.granted`
  - `capability.revoked`
  - `feedback.submitted`
  - `preset.applied`
  - `risk.flagged`
  - `telemetry.purged`
  - `trust_signal.updated`
- `actor`:
  - `kind`: `human | agent | system`
  - `id`: persisted with fallback `"<source>:unknown"` (for example `openclaw:moltfred`, `mcp:unknown`)
- `source`: `cli | api | mcp`
- `trace_id`: request/tool correlation id (for example `api:<uuid>`, `mcp:<uuid>`, `cli:<uuid>`)
- `build`:
  - `runner_version`
  - `git_sha` (if available)
  - `python_version`
  - `platform`
- `data`: sanitized payload

## Tamper-evident hash-chain

Each row includes:

- `prev_hash`
- `event_hash`

Computation:

- `event_hash = sha256(prev_hash + ":" + canonical_json(event_without_hash_fields))`
- First event uses `prev_hash = "0000...0000"` (64 hex chars).
- Verification fails if any row has:
  - missing hash fields,
  - mismatched `prev_hash`,
  - mismatched recomputed `event_hash`,
  - malformed JSON.

### Concurrency safety

- Telemetry appends use a cross-process writer lock at `events.jsonl.lock` in the same directory.
- Under the lock, the logger:
  - reads the current tail row,
  - derives `prev_hash` from the tail `event_hash`,
  - appends one new row,
  - flushes and fsyncs best-effort.
- This prevents interleaving writes from API/CLI/MCP processes from producing broken chains during normal operation.

### Failure semantics

- `prev_hash_mismatch` means a row does not point to the immediate prior row's `event_hash`.
- `missing_hash_fields` means at least one row is legacy/malformed and not hash-chained.
- If the tail is legacy/malformed, new hashed events are refused until rotation/purge rewrites the log.
- Use `runner telemetry purge --older-than <window>` (or manual local rotation) to recover to a valid chain.

## Data minimization and secret safety

Telemetry is redacted-by-design:

- Never stores raw secrets/credentials/private keys.
- Never stores raw artifact contents in event payloads.
- Proof telemetry stores metadata only (type, size, sha256, tier, quest id).
- Secret/PII-like values are replaced with `[redacted]`.
- Long values are truncated.
- If sanitization occurs, `risk.flagged` is emitted with redaction/truncation counts.
- Actor IDs and trace IDs are treated as untrusted input and sanitized.
- `feedback.submitted` telemetry includes metadata only (`feedback_id`, `severity`, `component`, counts), not full free-text details.

## CLI operations

```bash
# show telemetry status
runner telemetry status

# verify hash-chain integrity
runner telemetry verify

# export aggregated metrics only
runner telemetry export --range 7d --out ./telemetry-summary.json

# actor-filtered export
runner telemetry export --range 1d --actor-id openclaw:moltfred --out ./moltfred-summary.json

# create baseline snapshot (JSON + sha256)
runner telemetry snapshot --range 7d --actor-id openclaw:moltfred

# diff two aggregated summaries
runner telemetry diff --a ./baseline-a.json --b ./baseline-b.json --format text

# purge telemetry by window (chain-preserving rewrite + archive)
runner telemetry purge --older-than 30d

# purge proof storage by window
runner proofs purge --older-than 90d
```

Range format:

- `Nd` for days (example: `7d`)
- `Nh` for hours (example: `24h`)

## Export format (aggregated only)

`runner telemetry export` includes:

- `completions_total`
- `completions_by_actor_kind`
- `completions_by_actor_id`
- `completions_by_source`
- `completions_by_proof_tier`
- `completions_by_pillar`
- `xp_by_pillar`
- `completions_by_pack`
- `applied_preset_id` (when export is actor-filtered)
- `completions_by_preset`
- `xp_by_preset`
- `events_by_actor_kind`
- `events_by_actor_id`
- `daily_streak`, `weekly_streak`, `total_xp`
- `plans_generated`, `avg_quests_per_plan`
- `quest_success_rate`
- `quest_success_rate_by_pillar`
- `failures_by_reason`
- `risk_flags_count`
- `risk_flags_by_pillar`
- `feedback_count`
- `feedback_by_component`
- `feedback_by_severity`
- `top_quests_completed`
- `timebox_estimates_sum`
- `observed_duration_sum`

No raw events are included in export output.

## Snapshot/diff behavior

- `runner telemetry snapshot` writes an aggregated summary and returns deterministic SHA-256.
- Default snapshot location (without `--out`): `~/.agentwellness/baselines/`.
- `runner telemetry diff` compares two aggregated summaries and reports safe deltas, including:
  - totals/streaks/success rates
  - feedback count/component/severity deltas
  - by-actor completion deltas
  - by-pillar completion/xp/risk-flag deltas
  - by-pack completion deltas
  - top quest deltas

Diff works on aggregated JSON only; raw event files are not required.
