# API_SURFACE.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-11  
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

Actor id resolution precedence:
1. `X-Clawspa-Actor-Id` header
2. request body `actor_id` (for endpoints that accept bodies)
3. fallback `"<source>:unknown"` (for example `api:unknown`, `mcp:unknown`)

Actor ids are sanitized before telemetry persistence (control chars stripped, secret-like content redacted, long values truncated).

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

### Plans (daily/weekly)
- `GET /v1/plans/daily?date=YYYY-MM-DD`
- `POST /v1/plans/daily/generate?date=YYYY-MM-DD`
  - v0.1: rule-based picker
  - later: AI planner selects from curated quests

### Proofs / Completion
- `POST /v1/proofs`
  - body includes: quest_id, proof tier, artifact refs
  - optional body `actor_id` (lower precedence than `X-Clawspa-Actor-Id`)
- `GET /v1/proofs?quest_id=&date_range=`
  - `date_range` supports:
    - relative window: `7d`, `24h`, etc.
    - absolute range: `YYYY-MM-DD..YYYY-MM-DD`
  - invalid format returns `400`

### Scorecard
- `GET /v1/scorecard`
- `GET /v1/scorecard/export`
  - returns a shareable redacted export (local by default)
  - excludes raw proof artifacts and excludes `proof_id` from recent completion rows

### Telemetry (v0.1)
- v0.1 telemetry is local CLI-driven:
  - append-only local event log
  - aggregated export via runner CLI
- No raw telemetry event API endpoint is exposed by default.

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
