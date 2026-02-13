# API_SURFACE.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-13  
Owner: Project Team  

## Purpose

We are **AI-first and API-first**.

This document defines a stable API surface so:
- The local runner can be driven by UI, CLI, agents, or external apps.
- Agents can use the system via MCP (tool calls), not only a human UI.
- We can later add a web hub without breaking clients.

This is a **conceptual API** for v0.1. We can implement it as:
- localhost HTTP server
- CLI commands
- MCP tools that map to these operations
- library calls

---

## Principles

- **Local-first** by default (avoid uploading sensitive data).
- **Idempotent** operations where possible.
- **Explicit capability gating** for anything risky.
- **No secrets in API calls** (the API should not become a secret exfiltration channel).

### Request context headers (v0.1)

Supported optional headers for attribution and audit context:
- `X-Clawspa-Source`: `cli | api | mcp` (defaults to `api`)
- `X-Clawspa-Actor`: `human | agent | system` (endpoint-specific default if omitted)
- `X-Clawspa-Actor-Id`: actor identifier string (for example `openclaw:moltfred`, `human:jordan`)
- `X-Clawspa-Trace-Id`: request trace identifier for cross-channel audit continuity

Actor id resolution precedence:
1. `X-Clawspa-Actor-Id` header
2. request body `actor_id` (for endpoints that accept bodies)
3. fallback `"<source>:unknown"` (for example `api:unknown`, `mcp:unknown`)

Actor ids are sanitized before telemetry persistence (control chars stripped, secret-like content redacted, long values truncated).

Trace-id behavior:
- if `X-Clawspa-Trace-Id` is absent, API generates one (`api:<uuid>`).
- API echoes the effective value in response header `X-Clawspa-Trace-Id`.
- Telemetry events emitted by API-backed actions include `trace_id`.

---

## Core resources

- Packs: quest pack manifests
- Quests: quest definitions
- Plans: a set of selected quests for a date/time window
- Profiles: human_profile, agent_profile, alignment_snapshot
- Proofs: quest completion artifacts
- Scorecard: current streak/XP and summaries

---

## Local Runner API (v0.1)

### Health
- `GET /v1/health`
  - returns runner version, schema versions

### Packs
- `GET /v1/packs`
- `GET /v1/packs/{pack_id}`
- `POST /v1/packs/sync`
  - v0.1 reloads local pack sources only (no remote fetch by default)
  - default source: `quests/packs/`
  - optional extra local-only sources can be provided via `CLAWSPA_LOCAL_PACK_SOURCES` (OS path separator delimited)
  - response includes: `status`, `sources`, `pack_count`, `error_count`, `warn_count`

### Quests
- `GET /v1/quests/{quest_id}`
- `GET /v1/quests/search?pillar=&tag=&risk_level=&mode=`

### Profiles
- `GET /v1/profiles/human`
- `PUT /v1/profiles/human`
- `GET /v1/profiles/agent`
- `PUT /v1/profiles/agent`
- `GET /v1/profiles/alignment_snapshot`
- `POST /v1/profiles/alignment_snapshot/generate`
  - v0.1 can be heuristic; later AI-assisted

### Presets
- `GET /v1/presets`
- `GET /v1/presets/{preset_id}`
- `POST /v1/presets/apply`
  - body: `preset_id`, optional `actor_id`
  - actor resolution still follows header/body precedence
  - applies preset metadata to the resolved actor profile (`human` or `agent`)

### Plans (daily/weekly)
- `GET /v1/plans/daily?date=YYYY-MM-DD`
- `POST /v1/plans/daily/generate?date=YYYY-MM-DD`
- `GET /v1/plans/weekly?date=YYYY-MM-DD`
- `POST /v1/plans/weekly/generate?date=YYYY-MM-DD`
  - v0.1: rule-based picker
  - later: AI planner selects from curated quests
  - includes optional `applied_preset_id` when a preset is active for the actor profile
  - response includes `quest_metadata` rows per quest with:
    - `quest_id`
    - `title`
    - `pillars`
    - `risk_level`
    - `mode`
    - `required_capabilities`
    - `required_proof_tier`
    - `artifacts` (expected proof artifact declarations)

### Proofs / Completion
- `POST /v1/proofs`
  - body includes: quest_id, proof tier, artifact refs
  - `artifacts[].ref` is a short label (not payload content):
    - max 128 chars
    - path separators (`/`, `\`) are forbidden
    - use `artifacts[].summary` for longer text
  - optional body `actor_id` (lower precedence than `X-Clawspa-Actor-Id`)
- `GET /v1/proofs?quest_id=&date_range=`
  - `date_range` supports:
    - relative window: `7d`, `24h`, etc.
    - absolute range: `YYYY-MM-DD..YYYY-MM-DD`
  - invalid format returns `400`

Proof error codes (HTTP `400`):
- `PROOF_REF_INVALID`
  - message: `artifact ref must be short; put long content in summary`
  - hint includes example short refs
- `PROOF_TIER_TOO_LOW`
  - includes `required_tier` and `provided_tier`
  - message example: `Quest requires P2 minimum`

Unhandled internal errors return HTTP `500` with:
- `code: INTERNAL_SERVER_ERROR`
- `trace_id` in body
- `X-Clawspa-Trace-Id` response header

### Scorecard
- `GET /v1/scorecard`
- `GET /v1/scorecard/export`
  - returns a shareable redacted export (local by default)
  - excludes raw proof artifacts and excludes `proof_id` from recent completion rows
  - includes active trust signals with explicit expiries (trust signals are evidence metadata, not authority)

### Telemetry (v0.1)
- v0.1 telemetry is local CLI-driven:
  - append-only local event log
  - hash-chain verification via runner CLI
  - retention purge by range (older-than) via runner CLI
  - aggregated export/snapshot/diff via runner CLI
  - aggregated export includes preset metrics:
    - `applied_preset_id` (when filtered by actor id)
    - `completions_by_preset`
    - `xp_by_preset`
- No raw telemetry event API endpoint is exposed by default.

### Feedback (local-first)
- `POST /v1/feedback`
  - stores sanitized feedback in local JSONL (`~/.agentwellness/feedback/feedback.jsonl`)
  - emits metadata-only telemetry event `feedback.submitted`
  - payload fields:
    - `severity`: `info|low|medium|high|critical`
    - `component`: `proofs|planner|api|mcp|telemetry|quests|docs|other`
    - `title`, optional `summary`, optional `details`
    - optional `links` (`quest_id`, `proof_id`, `endpoint`, `commit`, `pr`)
    - optional `tags`
    - optional body `actor_id` (lower precedence than `X-Clawspa-Actor-Id`)
- `GET /v1/feedback?range=7d&actor_id=...&limit=100`
  - returns sanitized items
  - max response cap is 100
- `GET /v1/feedback/summary?range=7d&actor_id=...`
  - returns aggregate counts by severity/component and top tags

### Capability grants (Authorized Mode control)
- `GET /v1/capabilities`
- `POST /v1/capabilities/grant`
  - requires explicit user confirmation via a short-lived local grant ticket
  - includes scope, TTL, and `ticket_token` (single use)
  - requires dual confirmation signal (deny by default):
    - body: `confirm: true`
    - header: `X-Clawspa-Confirm: true`
  - optional body `actor_id` (lower precedence than `X-Clawspa-Actor-Id`)
  - ticket issuance is local-human mediated (CLI/runner UX), not agent-issued
- `POST /v1/capabilities/revoke`
  - optional body `actor_id` (lower precedence than `X-Clawspa-Actor-Id`)

---

## MCP tool mapping (v0.1)

The MCP server should expose tools that map cleanly to the API:

- `get_daily_quests(date?)` → `GET /v1/plans/daily`
- `get_quest(quest_id)` → `GET /v1/quests/{quest_id}`
- `submit_proof(quest_id, artifacts, tier)` → `POST /v1/proofs`
- `submit_feedback(severity, component, title, ...)` → `POST /v1/feedback`
- `get_feedback_summary(range?, actor_id?)` → `GET /v1/feedback/summary`
- `list_presets()` → `GET /v1/presets`
- `apply_preset(preset_id, actor_id?)` → `POST /v1/presets/apply`
- `get_scorecard()` → `GET /v1/scorecard`
- `get_profiles()` → `GET /v1/profiles/*`
- `update_agent_profile(profile_patch)` → `PUT /v1/profiles/agent`

> MCP tool schemas should avoid accepting raw file contents or secrets.
> MCP tools should reject oversized blobs and secret/PII-like payloads.

MCP transport policy (runner wrapper):
- default `api-base` target is localhost only (`127.0.0.1`, `::1`, `localhost`)
- non-local targets require explicit `--allow-nonlocal`
- scheme must be `http` or `https`
- userinfo in URL is forbidden

---

## Web Hub API (later)

If we add an online hub, it should accept only:
- redacted scorecard exports
- optional signed attestations (P3)
- pack metadata (not executable content)

Possible endpoints:
- `POST /v1/share/scorecard`
- `POST /v1/share/attestation`
- `GET /v1/packs/registry` (metadata only)

---

## Events (optional but helpful)

If we add an event bus:
- `quest.completed`
- `plan.generated`
- `capability.granted`
- `capability.revoked`
- `profile.updated`
- `risk.flagged`

---

## Related docs
- ARCHITECTURE.md
- QUEST_SCHEMA.md
- QUEST_LINT_RULES.md
- PERSONALIZATION.md
- PROFILE_SCHEMA.md
