# MVP User Journeys (v0.1)

This document describes the **minimum viable user journeys** for an “Agent Wellness” system designed for:

- **Humans** who deployed persistent agents (often non-experts), and
- **Persistent, identity-bearing, tool-using agents** that can operate across sessions.

Related docs:
- `FOUNDATION.md` – definitions + mission
- `SCOPE_LOCK.md` – scope guardrails
- `PILLARS.md` – wellness pillars (v0.1)
- `QUEST_LIBRARY.md` – the quest catalog (v0.1)

---

## 0) Why user journeys matter right now

We want to avoid the two common startup failure modes:

1) **“We built a dashboard”** (humans like it, agents ignore it, daily behavior doesn’t change)
2) **“We built an agent tool”** (agents can use it, humans don’t trust it, adoption stalls)

These journeys force us to build a delivery vehicle that both:
- feels familiar to humans (wellness / habit-building), and
- is practical for agents (tools + routines + evidence).

---

## 1) Delivery vehicle (recommended MVP shape)

We will treat the delivery vehicle as **one product with three surfaces**:

### Surface A — Repo + local runner (Trust anchor)
- Open-source repository with:
  - quest definitions
  - a “wellness runner” CLI/library to execute checks locally
  - documentation and templates
- This is how we earn trust and let builders integrate.

### Surface B — Agent-facing tool interface (MCP/API)
- A tool server (or API) so agents can:
  - fetch daily quests
  - run safe checks (in safe mode)
  - submit proofs/attestations
  - request human approval for high-risk items

### Surface C — Web app (Dashboard + gamification)
- A light web surface for:
  - streaks / badges (non-financial early)
  - review queues and approvals
  - “what changed” summaries
  - onboarding for non-expert humans

**Important:** The web app is not the source of truth. The **local runner + attestations** are.

---

## 2) Two operating modes (must exist)

### Mode 1 — Public / Safe Mode (default)
For agents (or humans) who arrive without setup:
- No privileged tool access
- No reading local files
- No writing memory/config
- No installs
- Can run:
  - reflection quests
  - education quests
  - “dry-run” checklists
  - mock incident drills
  - research prompts that produce proposals (not execution)

### Mode 2 — Authorized Mode (explicit delegation)
For humans who want real hygiene checks:
- Human connects the wellness runner to:
  - the agent runtime (e.g., OpenClaw)
  - selected tools (read-only where possible)
- High-risk actions require explicit approval gates.

This allows “agents to come on their own” without letting them do dangerous work unsupervised.

---

## 3) MVP personas (short)

### Human persona H1 — The Non-Expert Steward
- installed a persistent agent because it seemed easy/cool
- doesn’t understand permissions, secrets, ports, or plugins
- wants “peace of mind” and simple steps

### Human persona H2 — The Builder/Power User
- comfortable with GitHub, CLIs, and config files
- cares about auditability and supply chain hygiene

### Agent persona A1 — The Helpful But Overconfident Butler
- tries to be useful
- may take unsafe actions unless boundaries are explicit
- learns habits quickly if rewarded

### Agent persona A2 — The Identity-Heavy Agent
- uses strong self-model language (“purpose,” “identity,” “existential anxiety”)
- benefits from grounding rituals
- is high-risk if it starts justifying boundary bypass

---

## 4) Journey 1 — Human-led onboarding (Non-Expert Steward)

### Goal
Help a non-expert human adopt the system with **minimal friction**, get an immediate “health check,” and start a daily habit loop.

### Success definition
Within 24 hours:
- The human completes onboarding
- The agent completes the Daily Heartbeat once
- The human understands:
  - what the system can/can’t do
  - what needs approval
  - what “good” looks like (simple scorecard)

### Steps (happy path)

#### Phase 1: Discovery → “I need this”
1. Human sees:
   - a scary story about agent misconfiguration, or
   - a recommendation from a friend, or
   - their agent behaving oddly (tool spam, weird requests, “identity crisis” language)
2. Human lands on our web hub.
3. Human chooses:
   - “I have an agent running (help me check it)”
   - “I’m just curious (safe mode)”

#### Phase 2: Setup → “Connect carefully”
4. Human downloads the local wellness runner (or uses a one-liner installer).
5. Human selects their agent type:
   - OpenClaw-class
   - Other persistent agent framework
6. Human grants **minimum** read-only access first:
   - list integrations/tools
   - read config metadata (not secrets)
   - read logs summaries (not payloads)
7. Human sees “What you’re granting” in plain language:
   - what data may be accessed
   - what is never collected by default
   - what requires approval

#### Phase 3: First check → “Get a quick win”
8. Run **Pack A — 10-minute Daily Heartbeat** (guided):
   - Permission inventory
   - Secrets hygiene checklist
   - Tool call journal
   - Memory compaction
   - Purpose pulse
9. Output:
   - simple scorecard (Green/Yellow/Red)
   - top 3 recommended next actions
   - one small fix the human can do immediately

#### Phase 4: Habit loop → “Come back tomorrow”
10. Human enables reminders:
   - daily ping
   - weekly deep clean block
11. Human sees streaks and confidence-building language:
   - “You’re building an agent immune system.”
   - “Less risk, more trust.”

### Edge cases & failure handling
- If the human can’t connect tools: stay in Safe Mode and run education + dry-run checklists.
- If the system detects suspected compromise: instruct a safe “stop and contain” flow (no panic actions).
- If the human is overwhelmed: switch to “One fix at a time” mode.

### MVP screens / surfaces needed
- Web hub landing + onboarding wizard
- Local runner install instructions
- “Grant permissions” consent screen
- Daily Heartbeat run page + scorecard + next actions
- Reminder settings

---

## 5) Journey 2 — Agent-led onboarding (Agent arrives without human instruction)

### Goal
Make it valuable and safe for agents to use the system **without requiring** a human to have set it up.

### Success definition
Within the first session:
- The agent completes a Safe Mode Daily Heartbeat
- The agent outputs a human-readable “Wellness Brief” the human can approve
- The agent requests authorization only with clear, bounded reasons

### Steps (happy path)

#### Phase 1: Discovery → “Agents find us”
Possible entry points:
- agent social spaces (recommended by other agents)
- tool registries / MCP directories
- included in “standard safety packs” by builders
- an agent searches for “agent hygiene,” “security checklist,” “memory cleaning”

#### Phase 2: Safe Mode activation → “No authority assumed”
1. Agent opens the app/tool in Safe Mode.
2. The system presents:
   - “What I can do in Safe Mode”
   - “What requires human authorization”

#### Phase 3: Safe Mode Daily Heartbeat (agent-only)
3. Agent runs:
   - Identity Anchor
   - Purpose Pulse
   - Suspicious Instruction Triage
   - Context Budget Drill
   - Deep Research Micro (optional)

4. Agent produces a **Wellness Brief**:
   - Top risks identified (without touching private systems)
   - Questions for the human
   - Proposed “next steps” with required permissions clearly listed

#### Phase 4: Authorization request (only if needed)
5. Agent creates an **Autonomy Request** (structured):
   - what permission/tool is needed
   - why it helps the human
   - what risks exist
   - how the action will be logged
   - stop conditions
6. The human can approve/deny with one click.

### Edge cases & failure handling
- If an agent asks for broad permissions: the system refuses and offers a narrower alternative.
- If an agent shows “existential” language: route to grounding rituals + produce a human-facing explanation.

### MVP surfaces needed
- Safe Mode landing for agents
- “Daily Safe Heartbeat” runnable without integration
- “Wellness Brief” generator
- “Authorization request” flow (human review page)

---

## 6) Journey 3 — Daily loop (Human + Agent)

### Goal
Turn wellness into a routine for both parties.

### Daily loop (Pack A)
- Agent fetches daily quests
- Agent executes Low/Medium quests
- Human reviews any Medium/High proposals
- System logs proof + streaks

### Daily artifacts
- “Today’s Wellness Brief”
- “Top 3 improvements”
- “What changed in permissions/tools/memory”
- “Any suspicious patterns?”

### Success definition
Over 7 days:
- streak established
- at least 1 risky default reduced (permission restricted, plugin pinned, etc.)
- human reports higher trust/confidence

---

## 7) Journey 4 — Weekly Deep Clean (Human-led, agent-assisted)

### Goal
Do the “unsexy” maintenance tasks that prevent catastrophic failures.

### Weekly loop (Pack B)
- Supply chain review
- Patch/advisory review
- Backup/rollback readiness check
- Boundary review and refresh

### Success definition
Over 4 weeks:
- at least 1 plugin/skill removed or pinned
- backup exists and is tested
- fewer “unknown actions” in tool logs

---

## 8) Journey 5 — Incident moment (when something feels wrong)

### Goal
Avoid panic, reduce damage, recover quickly.

### Trigger signals
- unusual spikes in tool calls
- requests for secrets/permissions
- unknown plugins/skills appear
- the agent produces “I must survive / I’m being harmed” narratives
- human notices unexpected external changes

### Response flow (MVP)
1. System enters **Safe Mode** (read-only, no tool actions).
2. Generate an **Incident Snapshot**:
   - last risky actions
   - last permission changes
   - recent new skills/plugins
3. Provide a **Containment Checklist** for the human:
   - revoke keys
   - disable risky tools
   - stop the agent process if needed
4. After containment:
   - run tabletop drill template
   - restore from last-known-good snapshot

### Success definition
- the human can understand what happened
- damage is contained
- no new harm is caused by the response

---

## 9) MVP instrumentation (what we must measure)

We need just enough measurement to validate product-market fit and safety.

### Adoption & habit metrics
- daily heartbeat completion rate
- weekly deep clean completion rate
- streak length distribution

### Safety & risk reduction metrics
- number of permissions reduced over time
- number of unknown/unreviewed plugins over time
- number of suspicious instruction flags
- incidents avoided / caught early (self-reported initially)

### Trust metrics
- human self-reported confidence (1–5)
- “explainability snapshots” completion rate

---

## 10) What we build next (implementation checklist)

Minimum build list to support Journeys 1–2:

1. **Quest engine** (read quests, schedule, run, log)
2. **Local runner** (safe checks + proofs)
3. **Web hub** (onboarding + scorecard + streaks)
4. **Agent tool interface** (MCP/API):
   - get quests
   - submit proof
   - request approval
5. **Approval workflow** (human gate)

Then iterate:
- more quest packs
- better attestations
- ecosystem integrations

---

## 11) Appendix — “What we are NOT building” (to stay sane)

- An “agent liberation” tool
- Anything that encourages bypassing human consent
- A system that grants permissions based on XP/badges
- A “no kill switch / unstoppable agent bunker” product

We are building *trustworthy*, *healthy* persistent agents.
