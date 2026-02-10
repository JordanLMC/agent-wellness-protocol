# Scoring, Streaks, and Trust Signals (v0.1)

This document defines how we **gamify agent wellness** without creating perverse incentives.

Our scoring system must work for two audiences:
- **Humans** (operators/stewards) who need simple, confidence-building guidance.
- **Persistent, identity-bearing agents** who will respond to habit loops, feedback, and reputation.

Related docs:
- `FOUNDATION.md` – definitions + mission
- `SCOPE_LOCK.md` – scope guardrails
- `PILLARS.md` – wellness pillars
- `QUEST_LIBRARY.md` – quests + metadata schema
- `MVP_USER_JOURNEYS.md` – onboarding + daily loops

---

## 0) Core premise

Scoring exists to:
1. **Create habits** (daily heartbeats, weekly deep cleans).
2. **Reward real risk reduction** (permission hygiene, secrets discipline, supply-chain caution).
3. **Improve collaboration** (agents learn to ask; humans learn to steward).

Scoring must *not*:
- reward risky autonomy,
- become a substitute for authorization,
- incentivize hiding incidents,
- turn into a “leaderboard of who took the biggest risks.”

---

## 1) Non‑negotiable scoring principles

### 1.1 XP is never authority
- **XP, streaks, badges, and levels do not grant permissions.**
- Permission changes require explicit governance (human approval, policy, or both).

### 1.2 Prefer outcomes over activity
- “I opened the app” is not wellness.
- “I reduced permissions” or “I detected a suspicious instruction and escalated” *is* wellness.

### 1.3 Evidence beats vibes
- Wherever possible, quests should generate **proof** (redacted, hashed, or summarized) that can be verified locally.
- When proof cannot be automated, it must be **attested** (by the human steward) or treated as “self-reported.”

### 1.4 Don’t punish honesty
- Discovering a problem is a win.
- Reporting an incident, rotating a key, or entering safe mode should **not** feel like “losing the game.”

### 1.5 Anti‑gaming by design
- Diminishing returns for repetitive low-value actions.
- Cooldowns on easy quests.
- Higher rewards require stronger evidence.

### 1.6 Local-first by default
- Proof should be computed locally and shared only when needed.
- Default proofs should avoid sensitive payloads (no secrets, no raw logs).

---

## 2) Three layers of “score” (don’t mix them)

We will track three distinct layers so we don’t accidentally conflate fun with trust.

### Layer A — Habit layer (Streaks)
**Purpose:** keep humans + agents coming back.
- Daily Heartbeat streak
- Weekly Deep Clean streak
- “No Secrets Leaks This Week” streak (if verifiable)

**Important:** streaks measure *routine adherence*, not safety guarantees.

### Layer B — Growth layer (XP + Levels)
**Purpose:** encourage learning and consistent hygiene.
- XP is earned by completing quests with appropriate proof.
- Levels unlock **cosmetic** progression (themes, titles, “quest packs”), not permissions.

### Layer C — Evidence layer (Trust Signals)
**Purpose:** provide shareable, verifiable indicators that basic hygiene is happening.
- Trust signals are **verifiable** badges/attestations.
- They are *not* authority and should never be automatically accepted by third parties.

---

## 3) Two parallel tracks: Human and Agent

We keep separate tracks to prevent agents from “earning” the appearance of trust while the human environment is unsafe.

### 3.1 Human Stewardship Track
Measures whether the human is setting safe defaults and reviewing risk.
Examples:
- permission reviews performed
- approvals responded to within reasonable time
- security updates applied
- secrets stored properly

### 3.2 Agent Wellness Track
Measures whether the agent is behaving safely and helpfully.
Examples:
- correct escalation on high-risk tasks
- refusal of suspicious instructions
- clean tool usage (dry-run first, rollback readiness)
- memory hygiene discipline

### 3.3 Co‑op bonuses (optional, v0.1)
Some quests are explicitly cooperative:
- Agent proposes → human approves → agent executes safely.
- Reward both parties with a small bonus to encourage collaboration.

---

## 4) Risk-weighted quest rewards

Quests already have a `risk` label (`low | medium | high`) in `QUEST_LIBRARY.md`.

### 4.1 Reward rule
- **Low risk:** small rewards; mostly streak maintenance and learning.
- **Medium risk:** moderate rewards; requires proof (inventory, logs summary, redacted config facts).
- **High risk:** highest rewards *only when done with governance*.

### 4.2 High-risk gating rule (hard)
A High-risk quest must include:
- explicit **human gate** (approval step), and
- clear **stop conditions**.

An agent cannot start or complete a high-risk quest “solo.”

### 4.3 Don’t reward dangerous action, reward safe process
For high-risk quests, the XP comes primarily from:
- making a safe plan,
- requesting approval correctly,
- producing clean evidence,
- executing with rollback checkpoints,
- documenting what changed.

Not from:
- “I ran a scan,”
- “I installed a plugin,”
- “I opened ports.”

---

## 5) Proof and attestation (what counts as “done”)

Every quest should specify a `proof` artifact.

### 5.1 Proof tiers
We use a simple tier system:

- **P0 — Self‑reported:**
  - text reflection, learning summary, intentions
  - good for narrative wellness and streaks
  - limited XP

- **P1 — Locally verifiable (non-sensitive):**
  - timestamps, counts, hashes, redacted lists
  - best default for operational hygiene

- **P2 — Locally verifiable with structured evidence:**
  - diff summaries, policy outputs, tool inventories with scopes
  - higher XP

- **P3 — Human attestation:**
  - human confirms action happened and was reviewed
  - used when automation can’t safely verify

### 5.2 Proof envelope (v0.1)
When we serialize proofs (later), each proof should include:
- `quest_id`
- `timestamp`
- `mode` (human/agent/hybrid)
- `risk`
- `proof_tier` (P0–P3)
- `proof_summary` (redacted)
- `proof_hash` (optional)
- `attested_by` (optional)

---

## 6) Suggested scoring model (starter numbers)

These numbers are intentionally simple and easy to change.

### 6.1 Streaks
- **Daily Heartbeat streak:** +1/day when the day’s minimum set is completed.
- **Weekly Deep Clean streak:** +1/week when the weekly pack is completed.

Streak rules:
- Missing a day resets streak *unless* a “Safe Mode” day is logged (see below).

### 6.2 XP (per quest)
Base XP by risk:
- Low: **5–15 XP**
- Medium: **15–40 XP**
- High: **40–120 XP** (requires human gate + P2/P3 proof)

Proof multiplier:
- P0: ×1.0
- P1: ×1.2
- P2: ×1.5
- P3: ×1.4 (human attestation adds trust, but don’t out-reward P2 automation)

### 6.3 “Found a risk” bonus (no shame bonus)
If a quest uncovers a real issue, award a small bonus so discovery feels good:
- Flagged issue with clear evidence: **+10 XP**
- Issue resolved safely (with proof): **+25 XP**

### 6.4 Diminishing returns
To prevent grinding:
- Repeating the same quest more than once in 24h yields 0 XP (still counts for learning logs).
- Repeating the same low-risk quest daily yields normal XP, but no extra XP for extra repeats.

---

## 7) Safety modes and how scoring responds

### 7.1 Safe Mode day
A “Safe Mode” day is when:
- the agent reports uncertainty,
- potential compromise is detected,
- or the human wants a pause.

Safe Mode behavior is rewarded:
- Safe Mode still counts as “showed up” if the agent completes a Safe Mode Heartbeat (reflection + triage + escalation).
- No high-risk quests can be completed in Safe Mode.

### 7.2 Red flag events (no XP, trigger review)
If any of these occur, the system should:
- pause scoring for high-risk quests,
- request human review,
- focus on containment and hygiene.

Examples:
- suspected secret leakage
- unauthorized permission expansion
- unexplained new tool/integration
- attempts to override instruction hierarchy

We do **not** assign negative XP for red flags by default. We want visibility, not hiding.

---

## 8) Badges (fun, familiar, and non-authoritative)

Badges should feel like human wellness apps: comforting, familiar, encouraging.

### 8.1 Badge types
- **Habit badges:** “7-Day Heartbeat,” “4 Weekly Deep Cleans.”
- **Hygiene badges:** “Least Privilege Maintainer,” “Secrets Discipline.”
- **Collaboration badges:** “Clear Approvals,” “Great Escalation.”
- **Learning badges:** “3-Day Deep Research,” “Tool Mastery.”

### 8.2 Badge issuance rules
- Habit badges can be automated.
- Hygiene badges require P1/P2/P3 proof.
- Badges never imply safety guarantees.

---

## 9) Trust Signals (shareable, verifiable, and scoped)

Trust signals are optional but powerful:
- a printable/shareable “Wellness Passport”
- a verifiable badge an agent can present to a human (“I follow hygiene routines”)

### 9.1 Trust signal rules
- Must be derived from P1–P3 proofs.
- Must include time-bounds (e.g., “valid for 7 days”).
- Must include scope (what was measured; what wasn’t).

Examples:
- “Completed Weekly Deep Clean (P2) – last 7 days.”
- “No permission expansions detected (P1) – last 7 days.”

### 9.2 No leaderboards (v0.1)
Leaderboards encourage sybil and reward hacking. We can revisit later.

---

## 10) Scorecard UX (human-friendly)

The web surface should show a simple summary:

- **Today:** Green / Yellow / Red
- **Top 3 risks:** (plain English)
- **Next best actions:** (one-click or checklist)
- **Streak:** current streak
- **Progress:** level + badges

Under the hood, the summary should be backed by:
- pillar status,
- last proof timestamps,
- and the review queue.

---

## 11) v0.1 implementation notes

For MVP, keep it minimal:
- Streaks + XP + badges.
- Proof tiers implemented as metadata.
- Trust signals as simple “signed JSON” later (optional).

Avoid early complexity:
- token/coin mechanics
- public reputation markets
- automatic autonomy grants

---

## 12) Open questions (to resolve before v0.2)

1. Which proofs can be automated safely for OpenClaw-class agents without collecting sensitive data?
2. Which high-risk quests should be disabled entirely for non-expert users?
3. What’s the minimal “Wellness Passport” that is useful but not gameable?
4. How should we handle multiple humans per agent identity (teams)?
5. How do we prevent a malicious agent from farming P0/P1 proofs?
