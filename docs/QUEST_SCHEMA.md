# QUEST_SCHEMA.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-08  
Owner: Project Team  

## Purpose

Define the **machine-readable contract** for quests and quest packs so:
- We can build a runner + MCP server without ambiguity.
- Content can be reviewed, versioned, and signed like code.
- Quests can be safely rendered to humans and agents.

This schema is designed for **persistent, identity-bearing, tool-using agents** and their humans.

---

## Design goals

- **Structured > freeform**: reduce prompt-injection risk and ambiguity.
- **Declarative capabilities**: quests declare what they need; runner enforces.
- **Proof-first**: every quest defines what “done” means.
- **Human + agent lanes**: many quests have both.
- **Versionable and signable**: content should be treatable as supply chain artifacts.

---

## Core concepts

### Quest
A single repeatable ritual/task (daily/weekly/monthly) that improves a wellness pillar.

### Quest Pack
A versioned bundle of quests published by a known publisher, optionally signed.

### Modes
- **Safe Mode**: no writes, no shell exec, no outbound network beyond fetching quest packs (configurable).
- **Authorized Mode**: explicitly granted capabilities (scoped, time-limited), usually with human confirmation.

### Proof tiers (P0–P3)
- **P0 Self-Report**: user/agent checks a box (lowest trust).
- **P1 Local Evidence**: local-only artifact exists (summary, hash); not uploaded.
- **P2 Redacted Evidence**: redacted snippet/metadata can be shared.
- **P3 Verified Attestation**: cryptographically signed or system-verified evidence (highest trust).

---

## Quest file format

- File extension: `.quest.yaml`
- Encoding: UTF-8
- IDs are stable and globally unique (recommend reverse DNS style).

### Example quest (minimal)

```yaml
schema_version: 0.1
quest:
  id: "wellness.security.secrets.env_hygiene.v1"
  title: "Secrets Hygiene: .env and API Keys"
  summary: "Reduce accidental key leaks by tightening how secrets are stored and referenced."
  pillars: ["Security & Access Control", "Privacy & Data Governance"]
  cadence: "daily"  # daily|weekly|monthly|ad-hoc
  difficulty: 1     # 1..5
  risk_level: "low" # low|medium|high|critical

  mode: "safe"      # safe|authorized
  required_capabilities:
    - "read:project_files"   # capabilities are enforced by runner/tooling

  steps:
    human:
      - type: "read"
        text: "Confirm you are not pasting secrets into prompts, chat logs, or issue trackers."
      - type: "checklist"
        items:
          - "Secrets are stored in a .env file or a secrets manager"
          - ".env is in .gitignore"
          - "No secrets appear in terminal logs or screenshots"
    agent:
      - type: "reflect"
        text: "Summarize the most likely secret-leak paths in this environment and how to avoid them."
      - type: "output"
        artifact: "summary"

  proof:
    tier: "P1"
    artifacts:
      - id: "summary"
        type: "markdown"
        redaction_policy: "no-secrets"
        required: true

  scoring:
    base_xp: 10
    streak_weight: 1
    proof_multiplier:
      P0: 1.0
      P1: 1.1
      P2: 1.25
      P3: 1.5

  cooldown:
    min_hours: 18

  references:
    - type: "doc"
      label: "Internal: FOUNDATION.md"
    - type: "url"
      label: "Secret management basics"
      value: "https://example.com"

  tags: ["secrets", "env", "hygiene"]
```

---

## Field specification

### Top-level
- `schema_version` (required): number, current `0.1`
- `quest` (required): object (the quest definition)

### quest.id (required)
- string, globally unique
- recommended pattern: `wellness.<pillar>.<topic>.<name>.v<major>`

### quest.title / quest.summary (required)
- human-readable strings
- must not contain executable code blocks by default

### quest.pillars (required)
- list of strings matching canonical pillar names (see PILLARS.md)

### quest.cadence (required)
- enum: `daily | weekly | monthly | ad-hoc`

### quest.difficulty (optional, default 1)
- integer 1–5

### quest.risk_level (required)
- enum: `low | medium | high | critical`
- Guidance:
  - low: reflection/checklists only
  - medium: reads local config, no writes
  - high: writes config, installs/upgrades, network checks
  - critical: touches credentials, privileged access, production

### quest.mode (required)
- enum: `safe | authorized`
- `authorized` requires explicit capability grants and usually human approval

### quest.required_capabilities (required)
- list of strings (capability taxonomy is defined below)
- runner MUST enforce: if not granted, quest cannot run (or must degrade to Safe Mode lane)

### quest.steps (required)
- object with lanes:
  - `human`: list of step objects
  - `agent`: list of step objects
  - optional `both` lane for shared instructions (use sparingly)
- Step object:
  - `type` (required): enum (see Step Types)
  - Additional fields depend on type

#### Step types (v0.1)
- `read`: show text
- `checklist`: list of items
- `reflect`: structured reflection prompt (no tool execution)
- `output`: declares an artifact to produce
- `link`: external reference link
- `warn`: prominent caution text
- `confirm`: explicit user confirmation gate (especially for Authorized Mode)
- `runbook`: reference to a runbook section ID (in docs)

> We intentionally avoid embedding raw “commands to run” as a step type in v0.1.

### quest.proof (required)
- `tier`: `P0 | P1 | P2 | P3`
- `artifacts`: list of artifact declarations

Artifact fields:
- `id` (required): string
- `type` (required): enum `markdown | json | text | hash | screenshot | link`
- `required` (optional, default true)
- `redaction_policy` (optional): enum `no-secrets | pii-minimize | none`
- `max_size_kb` (optional)

### quest.scoring (required)
- `base_xp` (required): integer
- `streak_weight` (required): integer 0–3
- `proof_multiplier` (required): map for P0–P3 multipliers
- optional:
  - `first_time_bonus_xp`
  - `cooldown_bonus_xp`
  - `team_bonus_xp` (later)

### quest.cooldown (optional)
- `min_hours` integer; prevents grind

### quest.references (optional)
- citations and internal links
- object fields:
  - `type`: `doc | url | paper | video | standard | issue`
  - `label`: string
  - `value`: string

### quest.tags (optional)
- list of strings

---

## Capability taxonomy (v0.1)

Capabilities are **declarative**. The runner maps them to actual permissions.

### Read-only
- `read:project_files`
- `read:agent_config`
- `read:logs_local`
- `read:installed_skills`
- `read:network_config`

### Write / change
- `write:project_files`
- `write:agent_config`
- `write:memory_store`
- `write:secrets_store` (use sparingly; high risk)

### Execution
- `exec:shell`
- `exec:package_manager`
- `exec:container`

### Network
- `net:outbound`
- `net:scan_local` (high risk)
- `net:scan_remote` (critical; likely out of MVP)

### Identity
- `id:sign_attestation`
- `id:rotate_keys`

---

## Quest Pack format

- File: `pack.yaml`
- Quests live in the pack directory as `.quest.yaml`

### Pack manifest example

```yaml
pack_version: 0.1
pack:
  id: "wellness.core.v0"
  title: "Core Wellness Pack"
  publisher:
    name: "Agent Wellness Project"
    id: "org.agentwellness"
    contact: "security@agentwellness.example"
  version: "0.1.0"
  license: "Apache-2.0"
  created_at: "2026-02-08"
  quests:
    - "wellness.security.secrets.env_hygiene.v1"
    - "wellness.identity.integrity.checksum.v1"
  checksums:
    algo: "sha256"
    files:
      "quests/wellness.security.secrets.env_hygiene.v1.quest.yaml": "<sha256>"
  signing:
    scheme: "none"  # none|sigstore|pgp|ed25519
    signature: null
    public_key: null
```

---

## Versioning rules

- `schema_version` changes when the schema changes.
- Quest IDs use `v<major>` suffix; breaking changes bump the quest major.
- Pack versions follow semver.

---

## Validation rules (runner must enforce)

- Required fields present and types match.
- No step contains suspicious executable patterns unless explicitly allowed and gated.
- If `mode: authorized`, then at least one `confirm` step must exist in the human lane.
- Proof tier P2+ requires a redaction policy on any artifact type that might contain sensitive data.
