# IMPLEMENTATION_NOTES.md
Version: v0.1
Status: Working
Last updated: 2026-02-10
Owner: Project Team

## Scope lock and contract

This implementation follows these contract docs as source of truth:
- `FOUNDATION.md`
- `SCOPE_LOCK.md`
- `THREAT_MODEL.md`
- `QUEST_SCHEMA.md`
- `QUEST_LINT_RULES.md`
- `ARCHITECTURE.md`
- `SCORING.md`
- `PERSONALIZATION.md`
- `PROFILE_SCHEMA.md`
- `API_SURFACE.md`
- `CORE_PACK_V0.md`

Non-negotiables applied:
- Safe Mode default.
- Authorized Mode requires explicit human gating and TTL.
- No secrets collection.
- Quest packs treated as untrusted supply-chain input.
- XP/streaks do not grant authority.

## Current implementation status

- Core Pack v0 is implemented as 23 machine-readable quest YAML files with manifest checksums.
- `quest-lint` enforces schema/policy/security/pack/UX rules, including authorized-mode confirmation and hidden Unicode control rejection.
- Runner state uses schema-versioned local files with atomic writes and migration handling.
- Authorized Mode grants require short-lived single-use tickets plus TTL-scoped grants.
- Proof handling stores metadata envelopes only and rejects secret/PII/raw-log-like artifacts.
- MCP wrapper validates localhost-by-default API targets and strict tool payload safety limits.

## Implementation work plan (this branch)

1. Complete full Core Pack v0 quest YAML set in `quests/packs/wellness.core.v0/quests/`.
2. Update `pack.yaml` quest list and checksums to cover all Core Pack files.
3. Expand `quest-lint` to enforce all v0.1 contract rules used by this repo, including authorized-mode confirmation gate checks.
4. Add table/fixture coverage for schema, policy, security, pack, and UX lint rule categories.
5. Upgrade runner state handling:
   - atomic writes
   - state schema version and migrations
   - robust pack validation refusal path
6. Implement human-gated capability grant tickets with scope + TTL + single-use behavior for API grants.
7. Strengthen proof handling with artifact redaction/secret scanning checks for file references.
8. Keep API surface aligned with `API_SURFACE.md` and add regression tests for gating and route precedence.
9. Add MCP smoke coverage against local API behavior and strict tool payload constraints.
10. Keep docs in sync with any behavior changes in the same PR.

## Acceptance criteria for this branch

- `python -m pytest --basetemp .pytest_tmp` passes.
- `python -m quest_lint quests --format text` returns no findings.
- Core Pack v0 quest YAML is complete and consistent with `CORE_PACK_V0.md`.
- Runner CLI can deterministically generate daily plans and record completions/proofs.
- Local API endpoints in `API_SURFACE.md` are implemented and safe by default.
- Capability grants are explicit, scoped, TTL-bound, and human-gated by ticket.
- MCP tools map to local API and enforce strict safe payloads.
