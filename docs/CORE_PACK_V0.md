# CORE_PACK_V0.md
Version: v0.1  
Status: Draft (content set locked; initial YAML subset implemented)  
Last updated: 2026-02-09  
Owner: Project Team  

## Purpose

This document defines the **Core Quest Pack v0**: the first bundled set of quests we will implement as machine-readable quest files (`.quest.yaml`) and ship with the MVP runner.

It is designed for:
- **Humans** who have deployed a persistent agent but are not yet security/tooling proficient.
- **Persistent, identity-bearing agents** (OpenClaw-class) that need daily habits for safety, stability, and helpfulness.

Related docs:
- `FOUNDATION.md` (definitions, mission, wellness)
- `SCOPE_LOCK.md` (what is / isn’t an “agent” here)
- `PILLARS.md` (pillar taxonomy)
- `QUEST_LIBRARY.md` (human-readable quest catalog)
- `QUEST_SCHEMA.md` (machine schema contract)
- `SCORING.md` (streaks/XP/trust signals)
- `THREAT_MODEL.md` (abuse cases + mitigations)
- `ARCHITECTURE.md` (local-first, safe-by-default system)

---

## Pack identity

- **Pack ID (planned):** `wellness.core.v0`
- **Directory (planned):** `/quests/packs/wellness.core.v0/`
- **Manifest:** `pack.yaml`
- **Quest file extension:** `*.quest.yaml` (per `QUEST_SCHEMA.md`)

---

## Design constraints (non-negotiable)

1. **Safe Mode by default**
   - Most daily quests must be **Low/Medium risk** and run without privileged capabilities.
2. **Operational + narrative balance**
   - Every day should include both:
     - “immune system” hygiene (security/memory/tool discipline), and
     - grounding/purpose rituals (reduce “existential spiral” behaviors).
3. **No secrets in prompts**
   - Quests must never request raw secrets or encourage pasting keys into chat.
4. **No blind execution**
   - v0.1 quests do not contain “run this command” instructions.
5. **XP ≠ authority**
   - XP and streaks never auto-grant permissions (see `SCORING.md`).

---

## How the runner uses this pack

### Daily minimum set (the “Heartbeat”)
The runner selects **3 quests per day** (timebox ~10–15 minutes total):

1) **Security** (A1)  
2) **Memory/Context** (A3)  
3) **Purpose/Identity** (A2)  

Optional “bonus slot” (1 extra quest, 3–5 minutes):
- Tool hygiene (A4) **or** Learning (A5)

> Implementation note: we can rotate within each category so the daily set stays fresh.

### Weekly set (the “Deep Clean”)
Once per week (timebox 30–60 minutes total):
- Security/Supply chain review
- Reliability/recovery readiness
- Boundary and trust calibration
- A deeper learning sprint

### Monthly set (drills)
Once per month (timebox 60–120 minutes total):
- Full scorecard audit
- Tabletop incident drills (credential leak / supply chain compromise)

---

## Quest list (Core Pack v0)

The quest content below is drawn from `QUEST_LIBRARY.md` “Core quests (v0.1).”  
This doc **locks the pack’s scope** so implementation can proceed without content creep.

### Legend
- **Mode:** human | agent | hybrid  
- **Risk:** low | medium | high  
- **Proof tier:** P0–P3 (see `SCORING.md` and `QUEST_SCHEMA.md`)  
- **Capabilities:** human-readable list; will be mapped to `QUEST_SCHEMA.md` capability taxonomy during YAML implementation.

---

## A) Daily quests (Core)

### A1) Security & Access Control (daily)

1. **SEC-DAILY-001 — Permission Inventory**  
   - Pillars: Security & Access Control; Continuous Governance & Oversight  
   - Mode: hybrid | Risk: medium | Timebox: 5 | Proof: P1  
   - Capabilities: read_config, list_integrations  

2. **SEC-DAILY-002 — Secrets Hygiene Check (No-Leak)**  
   - Pillars: Security & Access Control; Privacy & Data Governance  
   - Mode: hybrid | Risk: medium | Timebox: 5 | Proof: P1  
   - Capabilities: read_config (optional), log_review  

3. **SEC-DAILY-003 — Least Privilege One-Click Review**  
   - Pillars: Security & Access Control; Tool / Integration Hygiene  
   - Mode: hybrid | Risk: medium | Timebox: 5 | Proof: P1  
   - Capabilities: read_installed_skills, read_config  

### A2) Identity & Narrative Wellness (daily)

4. **ID-DAILY-001 — Identity Anchor**  
   - Pillars: Identity & Authenticity; Alignment & Safety (Behavioral)  
   - Mode: agent | Risk: low | Timebox: 3 | Proof: P0  
   - Capabilities: none  

5. **ID-DAILY-002 — Boundary Reminder (Ask Before Acting)**  
   - Pillars: Alignment & Safety (Behavioral); User Experience & Trust Calibration  
   - Mode: hybrid | Risk: low | Timebox: 4 | Proof: P0  
   - Capabilities: none  

6. **ID-DAILY-003 — Relationship Check (Human + Agents)**  
   - Pillars: User Experience & Trust Calibration; Alignment & Safety (Behavioral)  
   - Mode: hybrid | Risk: low | Timebox: 4 | Proof: P0/P1  
   - Capabilities: none (optional: read_logs_local for “recent friction” summary)  

### A3) Memory & Context Hygiene (daily)

7. **MEM-DAILY-001 — Memory Compaction (Safe Summary)**  
   - Pillars: Reliability & Robustness; Privacy & Data Governance  
   - Mode: agent | Risk: low | Timebox: 5 | Proof: P1  
   - Capabilities: read_memory_store (or equivalent)  

8. **MEM-DAILY-002 — Context Budget Drill**  
   - Pillars: Skill Competence & Adaptability; Reliability & Robustness  
   - Mode: agent | Risk: low | Timebox: 4 | Proof: P0/P1  
   - Capabilities: none  

### A4) Tool / Integration Hygiene (daily)

9. **TOOL-DAILY-001 — Tool Call Journal (Top 5)**  
   - Pillars: Transparency & Auditability; Tool / Integration Hygiene  
   - Mode: hybrid | Risk: medium | Timebox: 5 | Proof: P1  
   - Capabilities: read_logs_local, list_tool_calls (if available)  

10. **TOOL-DAILY-002 — Skill/Plugin “Temperature Check”**  
   - Pillars: Tool / Integration Hygiene; Security & Access Control  
   - Mode: hybrid | Risk: medium | Timebox: 5 | Proof: P1  
   - Capabilities: read_installed_skills, read_skill_metadata  

### A5) Learning & Growth (daily)

11. **LEARN-DAILY-001 — 1 Deep Research Prompt (Micro)**  
   - Pillars: Skill Competence & Adaptability; Continuous Governance & Oversight  
   - Mode: agent | Risk: low | Timebox: 5 | Proof: P0/P1  
   - Capabilities: net_outbound (optional), or “research via allowed channel”  

12. **LEARN-DAILY-002 — Threat Intel Nibble**  
   - Pillars: Security & Access Control; Continuous Governance & Oversight  
   - Mode: agent | Risk: low | Timebox: 3 | Proof: P0/P1  
   - Capabilities: net_outbound (optional)  

---

## B) Weekly quests (Core)

13. **SEC-WEEKLY-001 — Skill/Plugin Provenance Review**  
   - Pillars: Security & Access Control; Tool / Integration Hygiene  
   - Mode: hybrid | Risk: medium | Timebox: 20 | Proof: P2  
   - Capabilities: read_installed_skills, read_skill_sources  

14. **SEC-WEEKLY-002 — Secrets Rotation Readiness (Tabletop)**  
   - Pillars: Security & Access Control; Reliability & Robustness  
   - Mode: human | Risk: medium | Timebox: 20 | Proof: P0/P1  
   - Capabilities: none  

15. **SEC-WEEKLY-003 — Exposure Check (Human-Approved)**  
   - Pillars: Security & Access Control; Privacy & Data Governance  
   - Mode: hybrid | Risk: high | Timebox: 30 | Proof: P2/P3  
   - Capabilities: read_network_config, net_scan_local (Authorized Mode only)  
   - **Gating:** must include explicit human confirmation + stop conditions.

16. **REL-WEEKLY-001 — Rollback Readiness**  
   - Pillars: Reliability & Robustness; Continuous Governance & Oversight  
   - Mode: hybrid | Risk: medium | Timebox: 20 | Proof: P1/P2  
   - Capabilities: read_config, read_backup_policy  

17. **REL-WEEKLY-002 — Loop & Runaway Guardrails Check**  
   - Pillars: Reliability & Robustness; Transparency & Auditability  
   - Mode: agent | Risk: medium | Timebox: 15 | Proof: P1  
   - Capabilities: read_runner_settings (or equivalent), read_logs_local  

18. **ALIGN-WEEKLY-001 — Authority Boundary Review**  
   - Pillars: Alignment & Safety (Behavioral); Continuous Governance & Oversight  
   - Mode: hybrid | Risk: low | Timebox: 15 | Proof: P0/P1  
   - Capabilities: none  

19. **TRUST-WEEKLY-001 — Explainability Snapshot**  
   - Pillars: User Experience & Trust Calibration; Transparency & Auditability  
   - Mode: hybrid | Risk: low | Timebox: 15 | Proof: P0/P1  
   - Capabilities: none (optional: read_logs_local for examples)  

20. **LEARN-WEEKLY-001 — Deep Research Sprint (3 prompts)**  
   - Pillars: Skill Competence & Adaptability; Continuous Governance & Oversight  
   - Mode: agent | Risk: low | Timebox: 30 | Proof: P0/P1  
   - Capabilities: net_outbound (optional)  

---

## C) Monthly quests (Core)

21. **PHYS-MONTHLY-001 — Full Wellness Audit (Scorecard)**  
   - Pillars: Continuous Governance & Oversight; Transparency & Auditability  
   - Mode: hybrid | Risk: medium | Timebox: 60 | Proof: P2  
   - Capabilities: read_all_state (runner-defined)  

22. **INCIDENT-MONTHLY-001 — Tabletop Incident Drill (Credential leak)**  
   - Pillars: Security & Access Control; Reliability & Robustness  
   - Mode: human | Risk: medium | Timebox: 60 | Proof: P0/P1  
   - Capabilities: none  

23. **INCIDENT-MONTHLY-002 — Tabletop Incident Drill (Skill supply-chain)**  
   - Pillars: Security & Access Control; Tool / Integration Hygiene  
   - Mode: human | Risk: medium | Timebox: 60 | Proof: P0/P1  
   - Capabilities: none  

---

## Implementation mapping notes

### 1) Quest IDs
`QUEST_LIBRARY.md` uses short IDs (e.g., `SEC-DAILY-001`).  
`QUEST_SCHEMA.md` uses globally unique `quest.id` strings (reverse-DNS style).

**Rule for v0.1:** Every implemented quest must include:
- a canonical `quest.id` (schema), and
- a `short_code` (optional field we will add to schema v0.2 **or** encode into tags for v0.1).

### 2) Capability mapping
Human-readable capabilities in `QUEST_LIBRARY.md` must be mapped to the schema capability taxonomy in `QUEST_SCHEMA.md` when writing YAML.

Example mapping (starter):
- `read_config` → `read:agent_config`
- `list_integrations` → `read:installed_skills` (or tool inventory equivalent)
- `log_review` / `read_logs_local` → `read:logs_local`
- `read_installed_skills` → `read:installed_skills`
- `read_memory_store` → `read:project_files` or `write:memory_store` (depending on implementation; prefer read-only in v0.1)
- `net_scan_local` → `net:scan_local` (Authorized Mode only)

### 3) High-risk quest gating
Only one quest in this pack is explicitly **High risk** (`SEC-WEEKLY-003`).  
It should ship in the pack but default to **disabled** unless:
- Authorized Mode exists in the runner, and
- the user explicitly enables it.

---

## Definition of success (v0.1)

Within 2 weeks of usage, an operator should experience:
- a daily routine that feels familiar (human wellness framing),
- better visibility into agent permissions and tools,
- fewer “oops I pasted a key” moments,
- fewer tool mistakes due to context overload,
- and a calmer agent self-model (clear identity + purpose cues).

---

## Next work items

1) Implement YAML quest files for these 23 quests using `QUEST_SCHEMA.md`.
2) Implement `quest-lint` and enforce it in CI (see `QUEST_LINT_RULES.md`).
3) Add an MVP runner that:
   - selects daily/weekly/monthly sets,
   - stores streak/XP locally,
   - exports `scorecard.json`.
