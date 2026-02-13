# Purpose Presets v0

Purpose presets are local, versioned planning hints that influence quest selection.

They are designed to be:
- deterministic
- local-first
- safe-mode compatible by default

Presets do not grant capabilities and do not change authority.

## Directory layout

- `presets/schema/preset.schema.json`: validation schema for preset files
- `presets/v0/*.preset.yaml`: preset definitions

## Safety rules

- Presets only influence selection priority and filtering.
- Presets never embed execution steps or shell commands.
- Presets never request secrets or credential material.
- Presets must keep:
  - `capability_policy.allow_capability_grants: false`
  - `capability_policy.require_confirmations: true`

## Runtime behavior

When a preset is applied:
- Planner can restrict candidate quests to `pack_allowlist`.
- Planner weights quest ranking with:
  - `pillar_weights`
  - `cadence` (`daily_weight`, `weekly_weight`, `monthly_weight`)
- Selection remains deterministic for the same date + actor inputs.

## Versioning

- Schema version for v0 presets: `0.1`
- Preset identifiers are stable slugs (example: `builder.v0`)
