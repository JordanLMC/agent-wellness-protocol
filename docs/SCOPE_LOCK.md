# SCOPE_LOCK.md
Version: v0.1
Status: Locked for MVP
Last updated: 2026-02-09
Owner: Project Team

## Why this exists

Scope lock prevents accidental expansion into unsafe or non-MVP behavior.

## In scope (v0.1)

- Local-first runner for quest planning and completion logging
- Quest packs as versioned YAML content
- quest-lint schema/policy/security checks
- Safe Mode default with Authorized Mode grant records and TTL expiry
- Scorecard export and local proof envelopes
- Local API + MCP wrapper over local API

## Out of scope (v0.1)

- Auto-executing commands from quest text
- Automatic autonomy grants from XP, badges, or trust signals
- Cloud dependency requirements for core operation
- Public leaderboards, tokens, or financial incentives
- Broad remote scanning, offensive security workflows, or persistence tooling
- Uploading raw logs/config/secrets by default

## Hard guardrails

- Commands are not a quest step type in v0.1.
- Quest packs are untrusted supply chain input and must be linted/validated.
- Any high/critical behavior requires human gate and explicit confirmation flow.
- No collection or request of API keys, private keys, seed phrases, or .env contents.

## Change policy

Any behavior or scope change must update relevant docs in the same PR/commit series.
