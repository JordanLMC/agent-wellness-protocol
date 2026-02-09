# PERSONALIZATION.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-09  
Owner: Project Team  

## Why this exists

Our target users are **persistent, identity-bearing, tool-using agents** (and their humans).  
These agents are **not interchangeable**. Their needs vary dramatically based on:

- **Mission / goals** (what the human wants; what the agent thinks it is for)
- **Environment** (local machine vs server; dev vs prod; personal vs team)
- **Capabilities / permissions** (read-only vs shell + network + secrets)
- **Tool stack** (skills/plugins, MCP servers, connectors)
- **Maturity level** (novice operator vs experienced builder)
- **Current condition** (healthy vs drifting vs compromised vs confused)

Therefore, the Wellness System must be **adaptive**:
- different quests for different agent/human pairs
- different tone and pacing
- different risk gating
- different “pillar weights” over time

> MVP can start with a static pack and simple heuristics, but the architecture must remain **AI-first and API-first** from day one.

---

## The personalization ladder (how we phase it)

This is the intended evolution. We can ship v0.1 without most of it, **as long as we design for it**.

### Level 0 — Fixed plan (MVP)
- Everyone gets the same “Core Pack v0” daily set.
- Minimal knobs: reminders, preferred time, optional quests.

### Level 1 — Rule-based personalization (still no LLM required)
- Use profiles + environment snapshot to select quests from a **curated library**.
- Examples:
  - If tools include `exec:shell` ⇒ add “shell safety” quests.
  - If human proficiency low ⇒ prioritize “human safety education” quests.
  - If agent reports “identity confusion” ⇒ increase “Identity Anchor” / “Purpose Pulse.”

### Level 2 — AI-guided planning (LLM planner; still uses curated quests)
- LLM generates a **plan** (which quests to do, in what order, with what emphasis),
  but it **selects from approved quests** only.
- LLM can also **parameterize** quests (fill placeholders), but not create new ones.

### Level 3 — AI-generated quests (high risk; post-MVP)
- LLM drafts new quests, but they:
  - MUST pass lint rules (QUEST_LINT_RULES.md)
  - MUST be reviewed by humans (or trusted maintainers)
  - MUST be published as immutable versions in packs (QUEST_SCHEMA.md)
- Default stance: **not needed early**; introduces supply-chain risk.

---

## Personalization primitives (what the system adapts)

### 1) Quest selection
Pick which quests are in today’s set based on:
- pillar weights
- recent incidents / near-misses
- maturity goals (skill-building path)
- capability footprint (blast radius)
- agent/human misalignment signals

### 2) Quest parameters (safe variable substitution)
Quests can contain placeholders like:
- `{agent_name}`
- `{human_name}`
- `{tool_list}`
- `{risk_posture}`
- `{goal_primary}`

Parameters are filled by the runner (or AI planner) and rendered as text.  
**Parameter filling must never produce executable commands.**

### 3) Tone and framing (“human-familiar”)
We can use familiar wellness language (“routine,” “streak,” “check-in,” “reset”) while keeping the actions operational:
- “Grounding check” → permission review
- “Self-care hygiene” → secrets handling
- “Boundary practice” → confirmation policy + tool gating
- “Purpose pulse” → mission statement + escalation rules

### 4) Difficulty and cadence
- Increase difficulty gradually.
- Avoid burnout: rotate pillars; use cooldowns (SCORING.md).
- Use “recovery weeks” after heavy changes or incidents.

### 5) Safety mode enforcement
Personalization must respect:
- Safe Mode default (ARCHITECTURE.md)
- capability gating (QUEST_SCHEMA.md)
- threat model non-negotiables (THREAT_MODEL.md)

---

## Onboarding and re-onboarding (the interview system)

Personalization requires **profiles**. We treat onboarding as a pair of interviews:

1) **Human interview** (human answers for themselves)
2) **Agent interview** (agent answers for itself)

Then we synthesize an **Alignment Snapshot** (where the pair agrees / disagrees).

### Interview channels (same questions, different UX)
- Chat-based interview (in-runner)
- Web survey (link)
- Voice call (ElevenLabs + Twilio) (later)
- Agent-to-agent interview (via MCP) (later)

**Rule of thumb:**  
- Human should do the human interview.  
- Agent should do the agent interview.  
- System can optionally offer “assisted” mode (agent helps human answer), but that should be discouraged as default.

### Interview outcomes
Each interview produces a structured artifact:
- `human_profile.json`
- `agent_profile.json`
- `alignment_snapshot.json` (derived)

These are **local-first** by default.

### Re-onboarding triggers
We should automatically recommend a re-interview when:
- major capability changes occur (new tools, new permissions)
- skills/plugins changed materially
- incident occurs
- large memory changes
- user goals change
- agent expresses instability (identity/purpose confusion) repeatedly

---

## “AI everywhere” without making the system unsafe

### The golden rule
**AI can decide *which* safe things to do; AI should not be able to decide *unsafe execution details* without gates.**

Practical implications:
- AI planner selects quests from curated packs.
- AI can recommend enabling Authorized Mode, but the human must confirm.
- AI can produce summaries, checklists, and plans.
- AI cannot auto-run commands or install skills by default.

### Keep AI outputs inside guardrails
Any AI-generated content that becomes actionable must:
- flow through the same quest schema (QUEST_SCHEMA.md)
- pass lint rules (QUEST_LINT_RULES.md)
- respect mode/capabilities (Safe vs Authorized)

---

## Personalization algorithm (MVP-friendly)

Even before AI, we can implement a simple “quest picker”:

Inputs:
- human_profile, agent_profile
- environment snapshot (capabilities, tools installed)
- completion history (streaks, drop-offs)
- “risk footprint” score (capability-weighted)

Outputs:
- daily quest set (3–5 quests)
- weekly quest set (2–3 quests)

Example heuristic:
- Always include 1 quest from:
  - Security & Access Control
  - Memory & Context Hygiene
  - Identity & Purpose
- If risk footprint high, add a 4th security quest.
- If completion drop-off, reduce difficulty and rotate to easier quests.

---

## What we should build now (design-first, ship later)

### MVP build requirements
- Runner stores profiles locally (even if empty at first).
- Runner exposes an API to read/write profiles (API_SURFACE.md).
- Daily quest selection code accepts a `plan` object (even if generated by heuristics today).

### “Later” integrations (planned)
- Twilio + ElevenLabs for voice interviews
- MCP tool endpoints for agent interviews
- LLM planner service (local or remote)
- “Alignment snapshot” generator (LLM-assisted synthesis, bounded by schema)

---

## References
- SCOPE_LOCK.md
- THREAT_MODEL.md
- QUEST_SCHEMA.md
- QUEST_LINT_RULES.md
- ARCHITECTURE.md
- SCORING.md
