# PRESETS.md
Version: v0.1
Status: Draft
Last updated: 2026-02-13
Owner: Project Team

## Purpose

Define Purpose Presets v0: local, versioned planning hints that bias quest selection without changing authority.

Presets are stored in:
- `presets/schema/preset.schema.json`
- `presets/v0/*.preset.yaml`

## Safety contract

- Presets influence selection only (pack filtering + pillar/cadence weights).
- Presets do not execute actions and do not grant capabilities.
- Safe Mode remains default.
- Capability grants still require explicit confirmation gates.
- XP never equals authority; presets do not alter trust boundaries.

## Available v0 presets

- `builder.v0`
- `researcher.v0`
- `admin_ops.v0`
- `task_manager.v0`
- `security_steward.v0`

## Runtime surfaces

- CLI:
  - `runner preset list`
  - `runner preset show --actor-id <id>`
  - `runner preset apply <preset_id> --actor-id <id>`
- API:
  - `GET /v1/presets`
  - `GET /v1/presets/{preset_id}`
  - `POST /v1/presets/apply`
- MCP tools:
  - `list_presets`
  - `apply_preset`

## Related docs

- `docs/PERSONALIZATION.md`
- `docs/API_SURFACE.md`
- `docs/PROFILE_SCHEMA.md`
- `presets/README.md`
