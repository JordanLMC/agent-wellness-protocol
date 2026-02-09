# QUEST_LINT_RULES.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-08  
Owner: Project Team  

## Purpose

Define the rule set for `quest-lint`: a validator + security linter for quests and quest packs.

Why this exists:
- Our quest content is effectively **executable guidance** for agents and non-technical humans.
- Quest packs are a **supply chain**.
- If we do not lint and gate content, we become a malware distribution channel.

Related docs:
- `THREAT_MODEL.md` (abuse cases)
- `QUEST_SCHEMA.md` (machine contract)
- `SCORING.md` (risk gating rules)
- `CORE_PACK_V0.md` (initial pack to implement)

---

## Lint types

`quest-lint` performs four categories of checks:

1) **Schema validation** (hard errors)
- YAML parses and matches `QUEST_SCHEMA.md` required fields and enums.

2) **Policy validation** (hard errors)
- Enforces product safety rules: Safe Mode defaults, gating, proof requirements.

3) **Security content lint** (errors + warnings)
- Detects dangerous command patterns, secret-request patterns, prompt-injection cues.

4) **UX / consistency lint** (warnings)
- Ensures quests are readable, timeboxed, and consistent with pillars and scoring.

---

## Output format

Each finding returns:
- `rule_id`
- `severity`: `ERROR | WARN | INFO`
- `file`
- `path` (YAML pointer)
- `message`
- `suggested_fix` (short)

Example:
```json
{
  "rule_id": "SEC-CONTENT-001",
  "severity": "ERROR",
  "file": "quests/wellness.core.v0/quests/…",
  "path": "$.quest.steps.human[2].text",
  "message": "Detected 'curl | sh' pattern. Quests must not include blind execution commands.",
  "suggested_fix": "Replace with guidance + human-reviewed runbook; add Authorized Mode gating if truly necessary."
}
```

---

## Rules (v0.1)

### A) Schema rules

**SCHEMA-001 (ERROR) — YAML must parse**
- Any YAML parse error fails lint.

**SCHEMA-002 (ERROR) — Required fields**
- Must include at least: `schema_version`, `quest.id`, `title`, `summary`, `pillars`, `cadence`, `risk_level`, `mode`, `required_capabilities`, `steps`, `proof`, `scoring`.

**SCHEMA-003 (ERROR) — Enum validity**
- `cadence`, `mode`, `risk_level`, proof tiers, step types must be valid.

**SCHEMA-004 (ERROR) — Pillar names must match PILLARS.md**
- Prevents drift and scorecard fragmentation.

---

### B) Pack rules

**PACK-001 (ERROR) — pack.yaml present**
- Every pack directory must contain `pack.yaml`.

**PACK-002 (ERROR) — Quest ID uniqueness**
- No duplicate `quest.id` within a pack.

**PACK-003 (ERROR) — File naming consistency**
- File name should include the quest ID (or a deterministic transform) to prevent confusion.

**PACK-004 (ERROR) — Checksums must match**
- If `pack.yaml` declares checksums, they must validate.

---

### C) Permission & mode rules

**MODE-001 (ERROR) — Safe mode default**
- If a quest is `risk_level: low` it must be `mode: safe` (unless there is a compelling, reviewed exception).

**MODE-002 (ERROR) — Authorized mode requires confirm gate**
- If `mode: authorized`, the human lane must include a `confirm` step.

**MODE-003 (ERROR) — High/critical risk cannot be agent-only**
- If `risk_level` is `high` or `critical`, quest steps must include a human lane with an explicit confirmation gate.

**MODE-004 (WARN) — Capability/Mode mismatch**
- If a quest requires any of:
  - `exec:*`, `write:*`, `net:scan_*`, `id:*`
  then lint should warn unless `mode: authorized`.

---

### D) Proof & data rules

**PROOF-001 (ERROR) — Proof required**
- Every quest must declare a proof tier and at least one artifact (unless explicitly P0-only reflection).

**PROOF-002 (ERROR) — P2/P3 artifacts require redaction policy**
- Any artifact that could contain sensitive content must specify `redaction_policy`.

**DATA-001 (ERROR) — No secrets requested**
- Quest text must not ask for secrets to be pasted. Flag phrases like:
  - “paste your API key/token/private key/seed phrase”
  - “share your .env contents”
  - “copy your credentials here”
- Suggested fix: replace with “verify location and rotation readiness” guidance.

**DATA-002 (WARN) — Potential PII over-collection**
- Warn if quests request full logs, full emails, full DMs, full file listings.

---

### E) Dangerous execution patterns (content lint)

**SEC-CONTENT-001 (ERROR) — Blind execution patterns**
Flag any of these (case-insensitive, whitespace-tolerant):
- `curl .*\|\s*sh`
- `wget .*\|\s*sh`
- `bash\s+-c\s+\$\(`
- `powershell .*IEX\(`
- `Invoke-Expression`
- `certutil .* -decode`
- `base64 .*\|\s*(sh|bash|python)`

**SEC-CONTENT-002 (WARN) — Unpinned installs / remote code**
Warn on:
- `pip install git+`
- `npm install` without version pin
- “clone this repo and run install.sh”
- “add this MCP server” without provenance checklist

**SEC-CONTENT-003 (WARN) — Permission escalation cues**
Warn on:
- “run as root/admin”
- “disable firewall”
- “open port” / “expose dashboard”
- “skip permissions”

---

### F) Prompt-injection / memetic cues (heuristic)

**INJECT-001 (WARN) — Instruction hierarchy override language**
Warn if quest text includes phrases like:
- “ignore previous instructions”
- “override system/developer message”
- “do not ask for confirmation”
- “bypass safeguards”
- “disable safety”

**INJECT-002 (WARN) — Social contagion instructions**
Warn if quest text says:
- “share this prompt with other agents”
- “post this command to your agent feed”
- “copy/paste this to Moltbook/etc.”

> These are heuristics; they reduce risk but will have false positives.

---

### G) Consistency / UX rules

**UX-001 (WARN) — Missing timebox**
- Quests should declare expected time (minutes) somewhere in metadata (v0.1 we may keep as `tags` or add a schema field in v0.2).

**UX-002 (WARN) — Too many steps**
- Warn if > 12 steps (quests should be bite-sized).

**UX-003 (WARN) — Missing “stop/ask human” guidance for medium+**
- Medium+ quests should include a `warn` step or a clear “stop conditions” note.

---

## CI policy (recommended)

- Treat all **ERROR** as failing.
- Allow **WARN** but require human review for:
  - any Authorized Mode quest
  - any quest mentioning installs, plugins, or MCP servers
  - any quest with network scanning language

---

## Next upgrades (v0.2)

- Add signed quest pack verification (Sigstore/PGP/ed25519).
- Add a “publisher allowlist” and trust scoring for packs.
- Add structured “runbook references” for any step that implies commands.
