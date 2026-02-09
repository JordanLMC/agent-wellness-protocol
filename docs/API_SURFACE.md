# API_SURFACE.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-09  
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
  - pulls/updates packs from configured sources

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
- `GET /v1/proofs?quest_id=&date_range=`

### Scorecard
- `GET /v1/scorecard`
- `GET /v1/scorecard/export`
  - returns a shareable redacted export (local by default)

### Capability grants (Authorized Mode control)
- `GET /v1/capabilities`
- `POST /v1/capabilities/grant`
  - requires explicit user confirmation (UI-mediated)
  - includes scope and TTL
- `POST /v1/capabilities/revoke`

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
