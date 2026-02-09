# Threat Model

> **Version:** v0.1  
> **Status:** Draft  
> **Last updated:** 2026-02-08  
> **Owner:** Project Team

## Purpose

Define the threat model for the Agent Wellness project to ensure we:
- Don't become an attack vector (e.g., quest packs as malware distribution)
- Don't build incentives that reward unsafe behavior
- Can ship quickly while staying aligned with our core promise: help humans and agents stay safe

## Assets to Protect

### User & Agent Safety
- Secrets (API keys, tokens, credentials)
- Personal data (emails, contacts, documents)
- System access (filesystem, shell, network)
- Human trust and agent trust

### System Integrity
- Quest packs and provenance
- Runner binaries and update channels
- MCP server code
- Proof artifacts
- Scoring state (streaks, XP, trust signals)

## Primary Adversaries

1. Malicious skill/plugin authors (supply chain)
2. Prompt injection propagators (memetic attacks)
3. Credential thieves
4. Identity impersonators
5. Score farmers (sybil attacks)
6. Compromised agents
7. Curious but reckless users

## Top Abuse Cases

###  1. Quest Pack as Malware
**Attack:** Quest instructs user/agent to run malicious command  
**Mitigations:** 
- Treat quests as code
- Signed packs
- No blind execution
- Safe Mode by default

### 2. Prompt Injection
**Attack:** Quest text hijacks agent behavior  
**Mitigations:**
- Separate data from instructions
- Structured schema
- Instruction hierarchy

### 3. Proof/Attestation Leakage
**Attack:** Proof uploads include secrets/PII  
**Mitigations:**
- Local-only by default
- Automatic redaction
- Tiered proof system (P0-P3)

### 4. Trust Signal Farming
**Attack:** Fake proofs to gain status  
**Mitigations:**
- XP ≠ authority
- Scoped, time-bounded signals
- Rate limits

## Security Principles

1. **Default to Safe Mode** - No file/shell/network writes
2. **Least Privilege** - Quests declare required capabilities
3. **No Secrets in Prompts** - Never request raw secrets
4. **Evidence Over Claims** - Proofs should be verifiable
5. **XP ≠ Authority** - XP unlocks content only
6. **Treat Community Content as Hostile** - Gate and verify

## MVP Mitigations

- Quest packs in GitHub with immutable version tags
- Pack manifest includes publisher, checksum, signing placeholder
- Runner enforces Safe Mode by default
- Proof export local-only with redaction
- Human review for Authorized Mode quests

## Threat Model Checklist

For every PR:
- What new capability does this enable?
- What is the worst abuse case?
- What is the default behavior?
- Does any data leave the machine?
- Can an injected agent misuse it?
- Is there a safe rollback path?
