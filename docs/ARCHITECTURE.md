# ARCHITECTURE.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-11  
Owner: Project Team  

## Purpose

Define a reference architecture for the Agent Wellness system that supports:
- Humans (especially non-technical operators)
- Persistent agents (OpenClaw-class)
- Daily/weekly “heartbeats” (quests)
- Safe-by-default execution and proof generation

This is a startup: the architecture must support **shipping fast** without becoming insecure by default.

---

## Product surfaces

We treat this as **one product with three surfaces**:

1. **GitHub Repo (trust anchor)**
   - Canonical quest packs, schemas, runner source, release artifacts, security policy.
2. **Local Runner (execution + local state)**
   - Runs quests; enforces permissions; stores streak/XP locally; generates proofs.
3. **Agent Interface (MCP server / tool API)**
   - Agents can fetch daily quests and submit proofs in a structured way.
4. **Web Hub (optional, later)**
   - Human dashboards, team sharing, trust signal viewing, community discovery.

---

## Core architectural principles

- **Local-first**: run checks locally; keep sensitive data local by default.
- **Safe Mode by default**: no risky capabilities until explicitly granted.
- **Explicit actor attribution**: record actor kind and actor id so multi-actor environments (human + multiple agents + systems) remain auditable.
- **Separation of concerns**:
  - Content (quests) is separate from code (runner).
  - XP is separate from trust.
- **Verifiable where possible**: proofs should be evidence-backed and redacted.
- **Treat content as code**: packs are versioned, reviewable, and signable.

---

## High-level components

### A) Quest Registry (GitHub)
- Stores packs and quests.
- Provides immutable version tags.
- Publishes checksums/signatures (v0.2+).
- Runtime loading is local-first: default `quests/packs/`, with optional extra local directories via `CLAWSPA_LOCAL_PACK_SOURCES` (no remote URL sync by default).

### B) Local Runner
- Reads quest packs and picks “daily set”.
- Renders quests (human UI and agent lane).
- Enforces capabilities and mode gating.
- Generates proofs and stores local state:
  - streaks
  - XP
  - quest completion history
  - local proofs (redacted and/or hashed)
  - local telemetry events (sanitized, append-only JSONL)
  - telemetry hash-chain fields (`prev_hash`, `event_hash`) with local verification
  - retention controls for telemetry/proofs (`CLAWSPA_TELEMETRY_RETENTION_DAYS`, `CLAWSPA_PROOFS_RETENTION_DAYS`)
  - actor-attributed telemetry (`actor.kind`, `actor.id`) for per-actor analysis
  - request trace attribution (`trace_id`) propagated across CLI/API/MCP

### C) MCP / Tool Server (optional, but likely)
- Exposes tools like:
  - `get_daily_quests`
  - `get_quest`
  - `submit_proof`
  - `get_scorecard`
- Acts as a bridge between agents and the local runner.
- Enforces the same Safe/Authorized gating.
- Generates and forwards `trace_id` context when missing.

### D) Web Hub (later)
- Reads exported scorecards and trust signals.
- Displays “what changed” logs and summaries.
- Can push new quest packs (as pointers) but should not execute anything.

---

## Data flows (MVP)

### Flow 1: Human-led onboarding (Safe Mode)
1. Human installs runner (or uses a simple desktop wrapper).
2. Runner loads local packs from `quests/packs/` (and optional explicit local sources).
3. Runner runs a 5-minute baseline:
   - explains Safe Mode vs Authorized Mode
   - sets “working agreement” (confirmation policy)
4. Runner schedules daily reminders locally.

**No accounts required** for MVP.

### Flow 2: Daily quests (human + agent)
1. Runner selects the daily set:
   - balanced across security, memory/context, and identity/alignment
   - cadence-aware (can include due weekly/monthly items)
   - capability- and cooldown-aware under Safe Mode defaults
2. Human completes checklist prompts; agent completes “agent lane” prompts.
3. Proof is generated locally:
   - summary markdown
   - optional hashes of config files (not contents)
4. Streak/XP updated locally.

### Flow 3: Agent-led usage (Safe Mode)
1. Agent calls MCP tool `get_daily_quests`.
2. MCP server returns structured quest steps (agent lane).
3. Agent completes reflection + outputs artifact.
4. Agent submits proof via `submit_proof`.
5. Runner stores proof and updates score locally.

Agent can “self-start” here without needing the human to push buttons.

---

## Modes and gating

### Safe Mode (default)
Allowed:
- reading quest content
- reflection, journaling, summaries
- read-only checks (where safe)
- local score updates

Not allowed:
- writing to files
- shell execution
- installing skills/plugins
- network scanning
- touching secrets stores

### Authorized Mode (explicit)
Allowed only after:
- human confirmation step
- human-issued short-lived grant ticket (single-use)
- API dual confirm signal (`confirm: true` in body + `X-Clawspa-Confirm: true` header)
- scoped capabilities are granted
- time limit applied (auto revert)

Authorized Mode should be rare and feel like “sudo.”

---

## Proof and trust signal architecture

### Local proof store
- Contains artifacts declared in quests (QUEST_SCHEMA.md).
- Redaction happens before any export.
- Retention purge supports `older-than` windows to minimize stale sensitive metadata.

### Export formats (MVP)
- `scorecard.json` (local only)
- `shareable_summary.md` (optional)
- `attestation.json` (optional, unsigned for v0.1)

### Trust signals
- A trust signal is a **time-bounded, scoped** statement backed by proof.
- Example: “Security hygiene daily streak: 7 days (last 14 days), P1 evidence.”
- v0.1 stores active trust signals locally and surfaces them in scorecard exports.

> Important: trust signals never grant permissions automatically.

---

## Security posture (MVP)

Even at MVP, we should implement:
- Pack checksums (at minimum)
- “dangerous pattern” detection in quest content
- Safe Mode enforcement
- Proof redaction before export
- Tamper-evident telemetry hash-chain + verification
- Sanitizer hardening with `risk.flagged` when redaction/truncation occurs
- Retention purge with archive + chain-preserving rewrite

---

## Technology notes (non-binding)

We can implement the runner in:
- Python (fast iteration) with strong sandbox discipline, or
- Go/Rust (stronger distribution story)

MCP server can be a thin wrapper around runner APIs.

Web hub can be:
- static site reading exported scorecards, or
- lightweight authenticated dashboard (later)

---

## What we intentionally avoid in MVP

- Auto-executing commands from quest content
- Uploading raw logs or config files by default
- Token/coin mechanics
- Any “agent persistence as survival” features
