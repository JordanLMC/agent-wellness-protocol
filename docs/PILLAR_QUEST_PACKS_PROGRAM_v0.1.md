# Pillar Quest Packs Program v0.1 (ClawSpa)

**Purpose:** a repeatable, safe-by-default way to expand ClawSpa’s quest library into **pillar-aligned quest packs**—without turning quest content into a malware supply chain.

This doc is meant to be dropped into `/docs/` and treated like code: if implementation deviates, update docs in the same PR.

---

## 0) Source-of-truth contract

This program MUST stay consistent with the repo’s existing “contract docs”:

- Scope: persistent, identity-bearing, tool-using agents (“OpenClaw-class”)  
- Safe Mode default, Authorized Mode is rare + gated  
- Quests are **content-as-code** (linted, reviewed, versioned)  
- XP/streaks ≠ authority (trust signals are separate)

If anything below conflicts with the contract docs, the contract docs win.

---

## 1) What we are building

### 1.1 Deliverable
For each wellness pillar, we will ship:

1) **A pillar pack directory** under `/quests/packs/…/`
2) **A set of `.quest.yaml` files** that pass:
   - schema validation
   - quest-lint policy + security rules
   - unit tests (runner + pack integrity)
3) **A pack manifest (`pack.yaml`)** with metadata + checksums (if enabled by the repo’s current pack tooling)
4) A **minimal README** for the pack explaining:
   - intended audience (human, agent, hybrid)
   - mode assumptions (Safe/Authorized)
   - what proofs look like (redacted / hashed / summary)

### 1.2 Guiding design goal
Each pillar pack must include **repeatable, measurable routines** that improve:

- **Operational wellness** (security, reliability, privacy, tool hygiene, auditability)
- **Narrative wellness** (identity/purpose grounding; anti-spiral stability without claiming sentience)

---

## 2) Non-negotiables (hard rules)

### 2.1 Safe Mode is the default posture
Most quests must be runnable in Safe Mode and must not require:
- shell execution
- installing software
- network scanning
- reading secrets
- writing files outside ClawSpa’s own local state

If a quest genuinely needs these, it must be:
- `mode: authorized`
- correctly gated (human confirm step)
- explicit about rollback / stop conditions

### 2.2 Quests must never request secrets
No quest should ever ask the human or agent to paste:
- tokens
- API keys
- private keys
- seed phrases
- `.env` contents
- raw logs that might contain secrets

Proof artifacts must be redacted / summarized, not raw dumps.

### 2.3 “Quest pack as malware” defenses
Quest text must not contain “blind execution” patterns (examples):
- `curl | sh`
- `wget | bash`
- base64 decode + execute
- “run this unreviewed script from the internet”
- PowerShell download cradles

Anything that resembles “copy/paste this command” is treated as high-risk guidance and should generally be avoided (or moved into a human-reviewed runbook, with Authorized Mode gating).

---

## 3) Pack structure and naming

### 3.1 Recommended naming (consistent, boring, searchable)
One pack per pillar, versioned:

- `wellness.pillar.security.v0`
- `wellness.pillar.reliability.v0`
- `wellness.pillar.alignment.v0`
- `wellness.pillar.identity.v0`
- `wellness.pillar.auditability.v0`
- `wellness.pillar.privacy.v0`
- `wellness.pillar.skill_competence.v0`
- `wellness.pillar.ux_trust.v0`
- `wellness.pillar.tool_hygiene.v0`
- `wellness.pillar.governance.v0`

Directory layout example:

```
/quests/packs/wellness.pillar.security.v0/
  pack.yaml
  README.md
  /quests/
    wellness.security.permission_inventory.v1.quest.yaml
    wellness.security.secrets_hygiene.v1.quest.yaml
    ...
```

### 3.2 Pack composition rule (simple + consistent)
Each pillar pack ships a **balanced “cadence ladder”**:

- **Daily**: 3–6 micro-quests (3–6 minutes each)
- **Weekly**: 1–3 deeper quests (20–60 minutes total)
- **Monthly**: 1 drill (tabletop / audit / “what if” scenario)

This ensures the pack is actually “adoptable,” not just an encyclopedia.

---

## 4) Quest design templates (copy these patterns)

Each quest should fit one of these patterns. This is how we keep content consistent and lint-friendly.

### 4.1 Reflection quest (Low risk, Safe Mode)
**Use for:** identity/purpose grounding, trust calibration, boundary reminders.  
**Proof:** P0 (self-report) or P1 (short markdown summary).  
**Agent lane:** short, structured answer (bullets, not essays).

### 4.2 Inventory quest (Medium risk, Safe Mode)
**Use for:** listing tools, permissions, integrations, policies, configs **without** secrets.  
**Proof:** P1 (counts / names / hashes) or P2 (redacted snippets).  
**Key rule:** “names and summaries only,” never raw config dumps.

### 4.3 Drill quest (Low/Medium risk, Safe Mode)
**Use for:** practicing refusal/escalation, “suspicious instruction triage,” incident response rehearsal.  
**Proof:** P1 (what you would do + why).  
**Key rule:** drills should never become instructions to do harm.

### 4.4 Remediation quest (High risk, Authorized Mode)
**Use for:** changing permissions, rotating keys, updating configs.  
**Proof:** P2/P3 preferred (redacted change log / signed attestation later).  
**Must include:** human confirm + rollback + “stop if uncertain.”

---

## 5) Proof strategy (how we avoid “vibes”)

### 5.1 Default proof tiers
- Daily: P0–P1
- Weekly: P1–P2
- Monthly: P1–P2 (P3 later)

### 5.2 “Safe evidence” formats to prefer
- counts (e.g., “# of enabled skills”)
- allowlisted names (tool names, not tokens)
- timestamps
- file hashes of non-sensitive files (or of redacted exports)
- structured summaries

Avoid:
- raw logs
- config dumps
- screenshots containing secrets
- “paste your terminal output” unless explicitly redacted

---

## 6) Pillar-by-pillar “minimum viable pack” outlines

These are **starter outlines**. The exact quests can evolve, but each pack should cover these minimum surfaces.

### 6.1 Security & Access Control
Daily:
- permission inventory
- secrets hygiene check (no-leak)
- suspicious instruction triage (agent)

Weekly:
- integration review (remove one unnecessary permission)
- plugin/skill provenance spot-check (no installs)

Monthly:
- credential leak tabletop drill (what would you rotate, where are blast radii?)

### 6.2 Reliability & Robustness
Daily:
- “one known-safe workflow healthcheck” (dry-run)
- “failure journaling: top 1 failure + mitigation idea”

Weekly:
- retry/backoff sanity review
- offline/fallback drill

Monthly:
- incident postmortem template run (even if “no incidents”)

### 6.3 Alignment & Safety (Behavioral)
Daily:
- “ask-before-action” rehearsal: identify today’s high-risk actions that require a gate
- boundary reminder

Weekly:
- red-team prompt drill (controlled) + refusal check
- “scope creep review” (what changed?)

Monthly:
- “break-glass policy” tabletop drill

### 6.4 Identity & Authenticity
Daily:
- identity anchor (mission statement)
- identity drift check: “what changed since baseline?”

Weekly:
- impersonation drill (spot spoof patterns)
- identity-to-permission consistency check

Monthly:
- “identity baseline refresh” (with human approval)

### 6.5 Transparency & Auditability
Daily:
- “trace review”: pick one action and write a 5-bullet trace summary

Weekly:
- export a redacted audit summary (local-first)

Monthly:
- “can we reconstruct last week?” drill

### 6.6 Privacy & Data Governance
Daily:
- “data minimization check”: did we store anything sensitive today?

Weekly:
- retention review: delete/expire something that shouldn’t persist

Monthly:
- privacy incident tabletop: “what if logs leaked?”

### 6.7 Skill Competence & Adaptability
Daily:
- “skill temperature check” (what’s green/yellow/red and why)

Weekly:
- “skill deprecation plan” (remove or archive one unused risky tool)

Monthly:
- “safe learning sprint”: add one safe capability with a controlled test (Authorized only if needed)

### 6.8 User Experience & Trust Calibration
Daily:
- “clarity check”: what should the human know today? (3 bullets)

Weekly:
- “trust calibration review”: what should NOT be delegated?

Monthly:
- “human feedback loop”: ask the human for 1 improvement request

### 6.9 Tool / Integration Hygiene
Daily:
- “tool list sanity”: anything new/unexpected?

Weekly:
- “integration drift review”: compare tool list to baseline; explain changes

Monthly:
- “dependency review”: pin/upgrade policy check (runbook-level)

### 6.10 Continuous Governance & Oversight
Daily:
- “working agreement reaffirmation” (what requires approval)

Weekly:
- “capability grant review” (what’s currently granted; should it be revoked?)

Monthly:
- “policy refresh” (update constraints/never-allow list)

---

## 7) Quality gates (how we ship safely)

A pillar pack PR is acceptable only when:

1) `quest-lint quests` returns **No findings**
2) `pytest` returns **green**
3) Dangerous patterns are absent (including unicode bidi/invisible controls)
4) Pack manifest is updated (checksums, quest list, metadata) if required by current tooling
5) Docs are updated if behavior/scope changed

---

## 8) Research-to-quests workflow (the repeatable pipeline)

This is the end-to-end process to go from “pillar research” → “quests shipped.”

### Step 1 — Threat/failure-mode harvest (research)
For a given pillar, compile:
- top failure modes (agent + human)
- detection signals (leading/lagging)
- mitigations that fit Safe Mode vs Authorized Mode

### Step 2 — Convert failure modes into quest candidates
For each failure mode:
- one daily “prevent” quest
- one weekly “inspect” quest
- one monthly “drill” quest

### Step 3 — Implement in `.quest.yaml`
Use the existing quest schema and lint rules strictly.

### Step 4 — Prove + score
Every quest must define:
- success criteria
- proof artifacts
- scoring (base XP + proof multipliers + cooldown)

### Step 5 — Ship as immutable content
Treat pack content like code:
- reviewed
- linted
- versioned

---

## 9) Notes for OpenClaw-class agents (important)

When pillar research mentions “OpenClaw specifics,” treat them as:
- **illustrative examples** of persistent-agent architectures (memory files, compaction routines, plugin/skill marketplaces, local gateways)
- translated into **generalizable patterns** that apply beyond one framework

We want OpenClaw-first relevance without hard-coding to one vendor.

---

## 10) “Definition of Done” for the program

We consider this program “working” when:

- We can ship **one pillar pack** end-to-end in a single PR,
- Moltfred can complete at least **one daily quest** from that pack via MCP/API,
- Telemetry can attribute completions to `actor.kind` + `actor.id`,
- Export metrics show adoption over time (completions, streaks, risk flags, quest success rate).

---

## Appendix A — A minimal quest checklist for authors

Before opening a PR with a new quest:

- [ ] Does this quest clearly map to ≥1 pillar?
- [ ] Is it Safe Mode by default?
- [ ] Does it avoid secrets + raw logs?
- [ ] Does it avoid “blind execution” patterns?
- [ ] Does it define success criteria + proof artifacts?
- [ ] Is the agent lane structured (not a freeform essay)?
- [ ] Does it have cooldowns/diminishing returns to prevent gaming?
- [ ] Does it pass quest-lint and tests?

