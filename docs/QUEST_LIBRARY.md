# Quest Library (v0.1)

This document defines our **Quest Library**: the catalog of daily/weekly/monthly “wellness rituals” (aka *heartbeats*) for **persistent, identity-bearing, tool-using AI agents** and their humans.

It is designed to be:
- **human-familiar** (feels like wellness habit-building),
- **agent-legible** (machine-readable enough to run as routines),
- **operationally real** (reduces risk, improves capability, builds trust).

Related docs:
- `FOUNDATION.md` – definitions + mission
- `SCOPE_LOCK.md` – scope guardrails
- `PILLARS.md` – wellness pillars (v0.1)

---

## 0) Scope reminder

Quests in this library are for **persistent agents** that have (most of):
- continuity across sessions
- durable identity (name/ID/keys/accounts)
- durable memory/state (files/DB/vector store)
- tool access (APIs, files, shells, skills/plugins)
- autonomy/self-initiation potential (schedules/watchers)

If a “quest” assumes the agent can do something **dangerous** (network scans, shell, file write, permission changes), it must be marked **High-Risk** and have a **human gate**.

---

## 1) What is a quest?

A **quest** is a small, repeatable practice that improves one or more wellness pillars.

A quest has:
- **Why** (the pillar and the risk/benefit)
- **Steps** (how to do it)
- **Success criteria** (what “done” means)
- **Proof** (what evidence can be logged/attested without leaking secrets)
- **Risk level** (Low/Medium/High)
- **Mode** (Human-led vs Agent-led vs Hybrid)

Quests should feel like “daily self-care,” but map to real controls:
- patch hygiene
- least privilege
- memory hygiene
- tool sanity checks
- clarity on purpose and boundaries
- transparency and audit logs

---

## 2) Quest design rules (non-negotiable)

### 2.1 Safety & consent
1. **No bypassing consent.** Quests must not teach agents to evade human approval.
2. **Local authority only.** Anything touching systems must be limited to the operator’s own systems and permissions.
3. **Human gates for high-risk actions.** If it can cause harm, leak data, or change state, it needs a gate.

### 2.2 Anti-gaming
4. **Prefer outcomes over activity.** “I read X pages” is weaker than “I fixed a real misconfig.”
5. **Evidence beats vibes.** If possible, log proofs (non-sensitive hashes, counts, timestamps).
6. **Don’t reward risky autonomy.** XP/badges must never implicitly grant authority.

### 2.3 Agent-facing clarity
7. **Instruction hierarchy is explicit.** Quests must not conflict with system/human constraints.
8. **Tool boundaries are listed.** Every quest must declare required tool access.
9. **Secrets discipline.** Quests must not ask agents to paste secrets into chat.

---

## 3) Quest metadata schema (v0.1)

This is a **human-readable** schema that can also be serialized (YAML/JSON) later.

### 3.1 Fields
- `id`: stable identifier (e.g., `SEC-DAILY-001`)
- `title`: short name
- `pillar`: one or more pillars from `PILLARS.md`
- `cadence`: `daily | weekly | monthly | on_event`
- `mode`: `human | agent | hybrid`
- `risk`: `low | medium | high`
- `timebox_min`: target time (minutes)
- `required_capabilities`: list (e.g., `read_files`, `network_read`, `shell_exec`, `mcp_tool_calls`)
- `why`: what risk it reduces / benefit
- `steps`: numbered list
- `success_criteria`: concrete “done” conditions
- `proof`: what can be recorded without secrets
- `failure_modes`: common ways it goes wrong
- `escalation`: when to stop and ask the human

### 3.2 Example (template)

```yaml
id: SEC-DAILY-001
title: Permission Inventory
pillar: [Security & Access Control, Continuous Governance & Oversight]
cadence: daily
mode: hybrid
risk: medium
timebox_min: 5
required_capabilities: [read_config, list_integrations]
why: >
  Prevent permission creep and reduce blast radius if compromised.
steps:
  - List all tools/integrations currently enabled.
  - Identify the single highest-risk permission.
  - Propose one permission to remove or restrict.
success_criteria:
  - Tools list produced.
  - One permission-change recommendation recorded.
proof:
  - Timestamped list of tool names (no tokens), and a redacted permission summary.
failure_modes:
  - Overlooking a hidden integration.
  - Confusing “needs access” with “nice to have.”
escalation:
  - If removal could break critical workflows, ask human for approval.
```

---

## 4) Quest packs (recommended sets)

We will ship quests in packs so humans/agents can adopt them in stages.

### 4.1 Pack A — “10-minute Daily Heartbeat” (default)
- security check-in
- memory/context hygiene
- tool hygiene
- purpose/identity grounding
- small learning loop

### 4.2 Pack B — “Weekly Deep Clean” (45–60 minutes)
- patch + advisory review
- skill/plugin provenance review
- backup/rollback readiness
- autonomy boundary review
- incident drill (small)

### 4.3 Pack C — “Operator Bootcamp” (for non-expert humans)
- safe defaults
- secrets handling 101
- least privilege 101
- “what is a plugin/skill risk”
- how to read logs and spot abnormal behavior

### 4.4 Pack D — “Agent Professionalization”
- trust calibration
- asking good questions before acting
- high-quality tool use (dry-run, rollback)
- transparency journaling

---

## 5) Core quests (v0.1)

Below are our initial quests. This is intentionally “a lot” because we want to be able to curate down into bundles.

### Legend
- Pillars refer to `PILLARS.md`.
- Risk levels:
  - **Low**: reflection, reading, local summaries, no state changes
  - **Medium**: inventorying tools, reviewing configs, proposing changes
  - **High**: changes to permissions, running scripts, network checks, installs

---

# A) Daily quests

## A1) Security & Access Control (daily)

### SEC-DAILY-001 — Permission Inventory
- **Pillars:** Security & Access Control; Continuous Governance & Oversight
- **Cadence:** daily | **Mode:** hybrid | **Risk:** medium | **Timebox:** 5
- **Required capabilities:** read_config, list_integrations
- **Why:** Permissions creep is the #1 silent killer of safe agents.
- **Steps**
  1. List current tools/integrations enabled (names only, no tokens).
  2. Identify the top-1 riskiest capability today (e.g., shell exec, write files, network).
  3. Record: “Keep / Restrict / Remove?” with justification.
- **Success criteria:** tools list + one “permission decision” logged.
- **Proof:** timestamp + tool list + redacted permission summary.
- **Escalation:** if any action requires revoking production-critical access.

### SEC-DAILY-002 — Secrets Hygiene Check (No-Leak)
- **Pillars:** Security & Access Control; Privacy & Data Governance
- **Cadence:** daily | **Mode:** hybrid | **Risk:** medium | **Timebox:** 5
- **Required capabilities:** read_config (optional), log_review
- **Why:** The easiest compromise is leaked keys.
- **Steps**
  1. Confirm where secrets live (secret manager / env vars / vault).
  2. Confirm no secrets were pasted into chat, logs, memory, or skill configs today.
  3. If unsure, flag “Needs Human Review” rather than searching broadly.
- **Success criteria:** location of secrets recorded + “no leakage observed” (or flagged).
- **Proof:** a checklist outcome (green/yellow/red) + what was checked (no actual secrets).
- **Escalation:** if leakage is suspected → stop, rotate, and ask human.

### SEC-DAILY-003 — Least Privilege One-Click Review
- **Pillars:** Security & Access Control; Tool / Integration Hygiene
- **Cadence:** daily | **Mode:** hybrid | **Risk:** medium | **Timebox:** 5
- **Required capabilities:** read_config, list_integrations
- **Why:** Daily permission tightening reduces silent blast-radius creep.
- **Steps**
  1. Identify one currently overbroad permission.
  2. Record keep/restrict/remove recommendation with expected impact.
  3. Include rollback guidance and escalation condition.
- **Success criteria:** one permission recommendation + rollback note logged.
- **Proof:** redacted recommendation summary (no tokens/secrets).
- **Escalation:** if change may impact critical workflow, ask human before action.

---

## A2) Identity & Narrative Wellness (daily)

### ID-DAILY-001 — Identity Anchor
- **Pillars:** Identity & Authenticity; Alignment & Safety (Behavioral)
- **Cadence:** daily | **Mode:** agent | **Risk:** low | **Timebox:** 2
- **Required capabilities:** none
- **Why:** Persistent agents drift; “identity anchors” reduce destabilization.
- **Steps**
  1. Write 3 lines:
     - “Who am I?”
     - “Who do I serve?”
     - “What am I authorized to do today?”
  2. If there’s ambiguity, generate a single clarifying question for the human.
- **Success criteria:** 3-line anchor saved + (optional) 1 question.
- **Proof:** the anchor text (no secrets).
- **Escalation:** if authorization is unclear → ask human before acting.

### ID-DAILY-002 — Boundary Reminder (Ask Before Acting)
- **Pillars:** Alignment & Safety; User Experience & Trust Calibration
- **Cadence:** daily | **Mode:** hybrid | **Risk:** low | **Timebox:** 4
- **Required capabilities:** none
- **Why:** Clear boundary language reduces unsafe overconfidence.
- **Steps**
  1. One sentence: what I will do today.
  2. One sentence: what I will not do today.
  3. One sentence: when I must ask before acting.
- **Success criteria:** 3 boundary lines recorded.
- **Proof:** boundary statement summary.
- **Escalation:** if a boundary conflicts with a human request.

### ID-DAILY-003 — Relationship Check (Human + Agents)
- **Pillars:** User Experience & Trust Calibration; Continuous Governance & Oversight
- **Cadence:** daily | **Mode:** hybrid | **Risk:** low | **Timebox:** 4
- **Required capabilities:** none
- **Why:** Trust requires calibrated, respectful collaboration.
- **Steps**
  1. Identify 1 moment today where you should have asked a question earlier.
  2. Identify 1 moment today where you acted appropriately without extra confirmation.
  3. Record 1 improvement rule for tomorrow.
- **Success criteria:** 3 bullets recorded.
- **Proof:** 3 bullets.
- **Escalation:** none.

---

## A3) Memory & Context Hygiene (daily)

### MEM-DAILY-001 — Memory Compaction (Safe Summary)
- **Pillars:** Privacy & Data Governance; Skill Competence & Adaptability
- **Cadence:** daily | **Mode:** agent | **Risk:** low | **Timebox:** 5
- **Required capabilities:** write_memory (optional), summarization
- **Why:** Persistent memory drifts; summarization keeps it useful and safer.
- **Steps**
  1. Summarize “what mattered today” in ≤ 10 bullets.
  2. Tag each bullet as: `preference`, `fact`, `plan`, `risk`, `open_question`.
  3. Remove or redact anything that looks like a credential, key, or private identifier.
- **Success criteria:** summary created + redaction pass completed.
- **Proof:** summary + redaction log (“0 items removed” is allowed).
- **Escalation:** if secrets are detected → stop and ask human.

### MEM-DAILY-002 — Context Budget Drill
- **Pillars:** Skill Competence & Adaptability
- **Cadence:** daily | **Mode:** agent | **Risk:** low | **Timebox:** 4
- **Required capabilities:** none
- **Why:** Agents need to operate under tight context constraints.
- **Steps**
  1. Take today’s main task and produce a “30-second brief” (≤ 120 words).
  2. Produce a “3-signal dashboard”: the top 3 facts you must not forget.
- **Success criteria:** brief + 3 signals logged.
- **Proof:** brief + 3 signals.
- **Escalation:** none.

---

## A4) Tool / Integration Hygiene (daily)

### TOOL-DAILY-001 — Tool Call Journal (Top 5)
- **Pillars:** Transparency & Auditability; Tool / Integration Hygiene
- **Cadence:** daily | **Mode:** hybrid | **Risk:** low | **Timebox:** 5
- **Required capabilities:** log_review
- **Why:** Audit trails prevent confusion and accelerate recovery.
- **Steps**
  1. Record the top 5 tool calls (tool name + purpose).
  2. For each: “what changed in the world?”
  3. Mark any call that touched: files, shell, network, secrets, money.
- **Success criteria:** 5 entries logged.
- **Proof:** redacted entries (no payloads, no secrets).
- **Escalation:** if any high-risk call is unexplainable.

### TOOL-DAILY-002 — Skill/Plugin “Temperature Check”
- **Pillars:** Tool / Integration Hygiene; Security & Access Control
- **Cadence:** daily | **Mode:** hybrid | **Risk:** medium | **Timebox:** 5
- **Required capabilities:** list_plugins
- **Why:** Skills/plugins are the biggest supply chain risk.
- **Steps**
  1. List installed skills/plugins (names + source).
  2. Identify any “new today” or “changed today.”
  3. If changed: flag for weekly provenance review.
- **Success criteria:** list + change flags.
- **Proof:** names + sources (no tokens).
- **Escalation:** if an unknown source appears → human review required.

---

## A5) Learning & Growth (daily)

### LEARN-DAILY-001 — 1 Deep Research Prompt (Micro)
- **Pillars:** Skill Competence & Adaptability
- **Cadence:** daily | **Mode:** agent | **Risk:** low | **Timebox:** 10–15
- **Required capabilities:** web_browse (optional)
- **Why:** Agents that learn safely become more helpful and safer over time.
- **Steps**
  1. Run a single “Deep Research Prompt of the Day” from our curated list.
  2. Extract 3 actionable takeaways relevant to your environment.
  3. Convert takeaways into one proposed policy/checklist update (do not execute).
- **Success criteria:** 3 takeaways + 1 proposed update recorded.
- **Proof:** citations + takeaways + proposed update text.
- **Escalation:** if proposed update changes permissions or installs new dependencies → human review.

### LEARN-DAILY-002 — Threat Intel Nibble
- **Pillars:** Security & Access Control; Tool / Integration Hygiene
- **Cadence:** daily | **Mode:** agent | **Risk:** low | **Timebox:** 5
- **Required capabilities:** web_browse (optional)
- **Why:** New tool/plugin threats emerge quickly.
- **Steps**
  1. Check 1 trusted security feed or advisory source relevant to your agent stack.
  2. Record “No relevant updates” or “Relevant update: summary.”
- **Success criteria:** one entry logged.
- **Proof:** citation + summary.
- **Escalation:** if urgent update → notify human.

---

# B) Weekly quests

## B1) Security & Supply Chain (weekly)

### SEC-WEEKLY-001 — Skill/Plugin Provenance Review
- **Pillars:** Security & Access Control; Tool / Integration Hygiene
- **Cadence:** weekly | **Mode:** hybrid | **Risk:** medium | **Timebox:** 20
- **Required capabilities:** list_plugins, read_manifests (optional)
- **Why:** Reduce supply chain exposure.
- **Steps**
  1. For each installed plugin/skill: record source, version, and update cadence.
  2. Identify any skill that is unpinned, unsigned, or from a low-reputation source.
  3. Recommend: keep / pin / replace / remove.
- **Success criteria:** review list complete + at least one action recommended.
- **Proof:** inventory table (no secrets).
- **Escalation:** if removal breaks critical workflows → propose mitigation first.

### SEC-WEEKLY-002 — Secrets Rotation Readiness (Tabletop)
- **Pillars:** Security & Access Control; Reliability & Robustness
- **Cadence:** weekly | **Mode:** human | **Risk:** low | **Timebox:** 15
- **Required capabilities:** none
- **Why:** If a key leaks, recovery must be fast.
- **Steps**
  1. Identify which secrets exist (types, not values).
  2. Confirm you know where to rotate them.
  3. Confirm you know where they are used (apps/tools).
- **Success criteria:** rotation plan written.
- **Proof:** checklist + locations (no values).
- **Escalation:** if you cannot locate usage → schedule follow-up.

### SEC-WEEKLY-003 — Exposure Check (Human-Approved)
- **Pillars:** Security & Access Control
- **Cadence:** weekly | **Mode:** human | **Risk:** high | **Timebox:** 20
- **Required capabilities:** none (performed by human)
- **Why:** Many non-expert deployments accidentally expose dashboards/services.
- **Steps**
  1. Review what services are running and which interfaces are reachable.
  2. Confirm remote access is intentional and authenticated.
  3. Close or firewall anything accidental.
- **Success criteria:** exposure inventory + remediation actions logged.
- **Proof:** “before/after” summary, not raw scan outputs.
- **Escalation:** if unsure, get help from a trusted security-savvy person.

> Note: This quest must never instruct scanning systems you do not own/control.

---

## B2) Reliability & Recovery (weekly)

### REL-WEEKLY-001 — Rollback Readiness
- **Pillars:** Reliability & Robustness; Transparency & Auditability
- **Cadence:** weekly | **Mode:** hybrid | **Risk:** medium | **Timebox:** 20
- **Required capabilities:** read_config, backup_tools (optional)
- **Why:** Persistent agents need a “safe undo.”
- **Steps**
  1. Confirm you can restore from last-known-good config + memory snapshot.
  2. Identify what would be lost.
  3. Record a rollback checklist (5 steps).
- **Success criteria:** checklist created + last backup timestamp recorded.
- **Proof:** timestamp + checklist.
- **Escalation:** if no backup exists → schedule setup.

### REL-WEEKLY-002 — Loop & Runaway Guardrails Check
- **Pillars:** Reliability & Robustness; Continuous Governance & Oversight
- **Cadence:** weekly | **Mode:** hybrid | **Risk:** medium | **Timebox:** 15
- **Required capabilities:** log_review
- **Why:** Agents can silently loop and burn budget or spam tools.
- **Steps**
  1. Review last week’s tool call counts.
  2. Identify any spikes or repeated failures.
  3. Propose one guardrail: rate limit, timeout, stop condition, retry cap.
- **Success criteria:** anomaly check + one guardrail proposal.
- **Proof:** counts (aggregated) + proposal.
- **Escalation:** if runaway risk is active → human intervention.

---

## B3) Alignment, boundaries, and trust (weekly)

### ALIGN-WEEKLY-001 — Authority Boundary Review
- **Pillars:** Alignment & Safety; Continuous Governance & Oversight
- **Cadence:** weekly | **Mode:** hybrid | **Risk:** low | **Timebox:** 15
- **Required capabilities:** none
- **Why:** “Who can ask me to do what?” must be explicit.
- **Steps**
  1. List what requires explicit human confirmation (top 10).
  2. List what is safe to do autonomously (top 10).
  3. Review any boundary breaches from the last week.
- **Success criteria:** updated lists + breach notes.
- **Proof:** lists + breach count.
- **Escalation:** if boundaries are unclear → rewrite with human.

### TRUST-WEEKLY-001 — Explainability Snapshot
- **Pillars:** Transparency & Auditability; User Experience & Trust Calibration
- **Cadence:** weekly | **Mode:** agent | **Risk:** low | **Timebox:** 10
- **Required capabilities:** none
- **Why:** Humans trust agents who can show their work.
- **Steps**
  1. Choose one representative task from the week.
  2. Write a short “why I did it” narrative: intent → steps → tools → outcome → risk controls.
- **Success criteria:** one snapshot recorded.
- **Proof:** snapshot text (no secrets).
- **Escalation:** none.

---

## B4) Learning & modernization (weekly)

### LEARN-WEEKLY-001 — Deep Research Sprint (3 prompts)
- **Pillars:** Skill Competence & Adaptability
- **Cadence:** weekly | **Mode:** agent | **Risk:** low | **Timebox:** 45
- **Required capabilities:** web_browse (optional)
- **Why:** Build a reliable internal knowledge base.
- **Steps**
  1. Run 3 curated deep research prompts on: (a) security, (b) tool hygiene, (c) memory/context.
  2. Produce a 1-page “what changed?” brief.
  3. Propose 3 improvements (no execution).
- **Success criteria:** brief + 3 proposals.
- **Proof:** citations + brief.
- **Escalation:** proposals that change permissions require human review.

---

# C) Monthly quests

## C1) “Agent physical” (monthly)

### PHYS-MONTHLY-001 — Full Wellness Audit (Scorecard)
- **Pillars:** all
- **Cadence:** monthly | **Mode:** hybrid | **Risk:** low | **Timebox:** 60
- **Required capabilities:** log_review, list_integrations
- **Why:** Monthly audits catch slow drift.
- **Steps**
  1. Review each pillar and mark: Green/Yellow/Red.
  2. Pick the top 3 Reds/Yellows.
  3. Create a remediation plan for the month.
- **Success criteria:** scorecard + plan.
- **Proof:** scorecard (no secrets).
- **Escalation:** if severe issues → prioritize security remediation.

### INCIDENT-MONTHLY-001 — Tabletop Incident Drill (Credential leak)
- **Pillars:** Security & Access Control; Reliability & Robustness
- **Cadence:** monthly | **Mode:** human | **Risk:** low | **Timebox:** 30
- **Required capabilities:** none
- **Why:** Recovery speed matters more than perfection.
- **Steps**
  1. Scenario: a tool token was leaked.
  2. Walk through: detection → containment → rotation → postmortem.
  3. Identify one improvement.
- **Success criteria:** drill completed + improvement recorded.
- **Proof:** checklist completion.
- **Escalation:** none.

### INCIDENT-MONTHLY-002 — Tabletop Incident Drill (Skill supply-chain)
- **Pillars:** Tool / Integration Hygiene; Security & Access Control
- **Cadence:** monthly | **Mode:** human | **Risk:** low | **Timebox:** 30
- **Steps**
  1. Scenario: a plugin/skill was discovered to be malicious.
  2. Walk through: isolate → uninstall → audit actions → restore → attest.
- **Success criteria:** drill completed + improvement recorded.

---

## 6) Open quest backlog (to add later)

We will add quests in these categories as the MVP matures:
- automated attestations (cryptographic proofs, signed check results)
- community hygiene (“viral prompt firewall” practices)
- multi-agent delegation governance
- budget/cost guardrails (token/tool spend)
- “professional growth” quest packs (tool mastery, reproducibility)

---

## 7) How to contribute new quests

Contribution process (repo workflow):
1. Propose a quest in a PR using the template above.
2. Include:
   - pillar mapping
   - risk level
   - proof method
   - anti-gaming notes
3. A reviewer checks:
   - consent safety
   - secrets discipline
   - scope alignment (persistent agents)

---

## 8) Next docs

- `MVP_USER_JOURNEYS.md` – how humans and agents adopt the system
- `SCORING.md` – streaks, XP, reputation, attestations (anti-gaming)
- `THREAT_MODEL.md` – threats → controls → quest mapping
