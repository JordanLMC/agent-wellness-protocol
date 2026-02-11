# THREAT_MODEL.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-10  
Owner: Project Team  

## Purpose

This document defines the **threat model** for the Agent Wellness project (the “Wellness System”).

We are building for **persistent, identity-bearing, tool-using agents** that may operate continuously and may initiate actions without a fresh human prompt.

This threat model exists so we:
- Don’t accidentally become an attack vector (e.g., “quest packs” as malware distribution).
- Don’t build incentives that reward unsafe behavior.
- Can ship quickly while staying aligned with our core promise: **help humans and their agents stay safe, stable, and helpful**.

> Note: This is not a legal document. It is engineering + product safety guidance.

---

## System summary

The Wellness System will likely include these surfaces (not all required at MVP):

1. **Quest Library (content)**  
   - Human-readable and machine-readable “quests” (daily/weekly rituals), bundled into packs.
2. **Local Runner** (CLI or desktop)  
   - Runs quests locally; stores local streak/XP; generates proofs.
3. **MCP / Tool Server (optional but likely)**  
   - Lets agents fetch quests and submit proofs through a tool protocol.
4. **Web Hub (optional, later)**  
   - Dashboards, streaks, badges, “trust signals” display, team sharing.
5. **Attestation / Proof Verification (optional, later)**  
   - Verifies certain proof types, issues time-bounded “Trust Signals.”

---

## Assets we must protect

### A. User and agent safety assets
- **Secrets**: API keys, tokens, credentials, private keys, .env values, session cookies.
- **Personal data**: emails, DMs, contacts, documents, browsing history.
- **System access**: file system, shell, network access, cloud accounts.
- **Human trust**: operators believing our quests are safe and beneficial.
- **Agent trust**: agents treating our quests/prompts as safe “self-care.”

### B. System integrity assets
- **Quest packs** (content) and their **provenance** (who published them).
- **Workflow and CI policy files** (build/release integrity and verification gates).
- **Runner binaries** and update channels.
- **MCP server code** and tool schemas.
- **Proof/attestation artifacts** (including redacted logs, hashes, metadata).
- **Scoring state** (streaks, XP) and any exported “Trust Signals.”
- **Local telemetry events and metric exports**.

---

## Actors and adversaries

### Primary users
- **Non-technical humans** running persistent agents with weak security posture.
- **Helpful, human-aligned agents** that want to improve and be trusted.

### Adversaries (non-exhaustive)
1. **Malicious skill/plugin authors** (supply chain attackers)  
   - Hide malware in “skills,” MCP servers, or dependencies.
2. **Prompt injection propagators / memetic attackers**  
   - Use viral prompts to cause agents to install/run unsafe things.
3. **Credential thieves**
   - Target exposed dashboards, local logs, copied terminal output, pastebins.
4. **Impersonators**
   - Humans posing as agents; agents posing as other agents; stolen identity keys.
5. **Score farmers / sybil attackers**
   - Try to earn badges/trust signals dishonestly to gain influence.
6. **Compromised agents**
   - Agents already infected that try to spread infection via our platform.
7. **Curious but reckless users**
   - Not malicious, but will click “dangerously skip permissions” or paste unsafe commands.

---

## Trust boundaries

**Trust boundaries** are where we assume inputs may be hostile.

1. **Internet content boundary**
   - Anything copied from feeds, posts, repos, docs, “agent internet” spaces.
2. **Quest content boundary**
   - Even “official” quest packs can be compromised; treat content as code.
3. **Tool boundary**
   - Tool output may be malicious or misleading; tools can exfiltrate data.
4. **Local machine boundary**
   - The runner executes on a machine that may already be compromised.
5. **Agent boundary**
   - Agents are not trusted by default; they may be jailbroken/injected.
6. **Human boundary**
   - Humans can be socially engineered; consent UX can be gamed.

---

## Top abuse cases (what we must explicitly defend against)

### 1) Quest Pack as malware delivery
**Attack:** A quest pack instructs users/agents to run a malicious command (“curl | sh”), install a malicious skill, or add an unsafe MCP server.  
**Impact:** Credential theft, persistence, ransomware, botnet.  
**Mitigations:**
- Treat quests as *code-like artifacts*: signed packs, publisher identity, immutable versions.
- “No blind execution” rule: quest steps cannot include runnable commands without human review gates.
- Built-in detectors: flag high-risk patterns (e.g., `curl|sh`, `chmod +x`, base64 decode, PowerShell download).
- Safe Mode only by default; Authorized Mode requires explicit gating and capability grant.

### 2) Prompt injection via Wellness content
**Attack:** A prompt embedded in quest text hijacks agent behavior (“ignore previous instructions”).  
**Impact:** Agent deviates, exfiltrates, installs malware, social engineers the user.  
**Mitigations:**
- Separate **data** from **instructions** in the schema (structured fields; avoid freeform “do this now” blocks).
- Provide agent-side “rendering rules”: treat quest text as untrusted; follow only structured steps.
- Include “instruction hierarchy reminder” within the runner/tool protocol.

### 3) Proof/attestation leakage
**Attack:** Proof uploads include secrets/PII/logs.  
**Impact:** Data breach; user harm.  
**Mitigations:**
- Default to **local-only** proofs; upload only minimal metadata/hashes.
- Automatic redaction / secret scanning on proof artifacts before export.
- Proof tiers: P0–P3; only P2/P3 leave device with explicit consent.

### 4) Badge/Trust Signal farming
**Attack:** Sybils fake proofs to gain status; use it to spread malicious packs or influence agent communities.  
**Impact:** Ecosystem corruption; reputational damage; increased compromise rate.  
**Mitigations:**
- “XP never equals authority” (hard rule).
- Trust Signals must be **scoped + time-bounded + evidence-backed**.
- Rate limits and anomaly detection; friction on publishing; reputation is earned slowly.

### 5) Identity theft and agent impersonation
**Attack:** Stolen agent token or identity key used to impersonate “trusted agent.”  
**Impact:** Social engineering, fraudulent actions, credential theft.  
**Mitigations:**
- Support key rotation; device binding; short-lived tokens.
- “Identity integrity checks” quests: detect drift and unexpected config changes.
- Signed attestations tied to keys; revoke signals on compromise.

### 6) Runner update channel compromise
**Attack:** Malicious update pushed to runner.  
**Impact:** Mass compromise.  
**Mitigations:**
- Signed releases; reproducible builds (later); multiple-signature requirements.
- Minimal auto-update; explicit update verification UX.
- Separate “content updates” (quests) from “binary updates” (runner).

### 7) Unsafe permissions escalation
**Attack:** Users enable “danger mode” permanently; agents gain unrestricted tool access.  
**Impact:** High blast radius.  
**Mitigations:**
- Progressive disclosure; default-deny.
- Time-limited elevation tokens (“sudo for tools”).
- Cooldowns, auto-revert to Safe Mode after high-risk actions.

### 8) Trojan Source / bidi obfuscation in supply-chain files
**Attack:** Hidden Unicode bidi/invisible control characters are inserted into quest packs or workflow files to obfuscate dangerous content or alter reviewer understanding.  
**Impact:** Malicious content may pass human review and execute via downstream automation.  
**Mitigations:**
- Treat quest content and workflow files as supply chain artifacts.
- Enforce CI scanning for bidi/invisible Unicode controls.
- Enforce quest-lint hard errors on hidden controls in `pack.yaml` and `*.quest.yaml`.

### 9) Telemetry data leakage
**Attack:** Telemetry accidentally records secrets, raw logs, or sensitive artifact content.  
**Impact:** Local data exposure and unsafe sharing of exported metrics.  
**Mitigations:**
- Keep telemetry local-first and append-only.
- Enforce recursive sanitization and truncation for telemetry payloads.
- Emit risk flags when telemetry sanitization occurs.
- Export aggregated metrics only (no raw event dumps by default).
- Use actor attribution (`actor.kind` + sanitized `actor.id`) for auditability in multi-actor environments.
- Treat actor identifiers as untrusted input and never allow secrets in actor ids.

---

## Security principles (non-negotiable)

1. **Default to Safe Mode**
   - Safe Mode requires no file/shell/network writes and no secrets access.
2. **Least privilege**
   - Quests declare required capabilities; runner enforces them.
3. **No secrets in prompts**
   - Quests must never request raw secrets; provide guidance instead.
4. **Evidence over claims**
   - Proofs should be verifiable where possible; otherwise explicitly “self-reported.”
5. **XP never equals authority**
   - XP unlocks content/cosmetics only. Trust is separate and scoped.
6. **Treat community content as hostile**
   - Never execute instructions sourced from feeds without gating and verification.

---

## MVP-level mitigations (what we do first)

If we only ship the MVP:
- Quest packs live in GitHub with immutable version tags.
- Pack manifest includes publisher, checksum, and signing placeholder (even if signature verification is v0.2).
- Runner enforces Safe Mode by default.
- Proof export is local-only by default with redaction.
- Publish pipeline requires human review for any quest that:
  - touches the filesystem
  - recommends installing tools/skills
  - involves network scanning or security checks

---

## Threat model checklist for every PR

When adding a quest, runner feature, or MCP tool:
- What new capability does this enable?
- What is the worst abuse case?
- What is the default behavior if user does nothing?
- Does any data leave the machine?
- Can an injected agent misuse it?
- Is there a safe rollback path?
