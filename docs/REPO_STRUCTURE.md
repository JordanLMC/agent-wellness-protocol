# Repository Structure

> **Version:** v0.1  
> **Status:** Draft  
> **Last updated:** 2026-02-08  
> **Owner:** Project Team

## Purpose

Define a repo layout that:
- Keeps us aligned with scope: persistent agents
- Separates content (quests) from code (runner)
- Supports secure publishing and review

## Top-level Structure

```
repo-root/
  docs/
    FOUNDATION.md
    SCOPE_LOCK.md
    PILLARS.md
    QUEST_LIBRARY.md
    MVP_USER_JOURNEYS.md
    SCORING.md
    THREAT_MODEL.md
    QUEST_SCHEMA.md
    ARCHITECTURE.md
    REPO_STRUCTURE.md
    SECURITY.md
    CONTRIBUTING.md
  quests/
    packs/
      wellness.core.v0/
        pack.yaml
        quests/
          *.quest.yaml
      wellness.openclaw.v0/
      wellness.mcp.v0/
    tools/
      quest-lint/
        schema-validator
        dangerous-patterns detector
        pack-sign
  runner/
    README.md
    src/
    tests/
    schemas/
  mcp-server/
    README.md
    src/
    tests/
  web/
    README.md
    app/
  examples/
    openclaw/
    mcp/
  scripts/
    release.sh
    verify.sh
  .editorconfig
  .gitignore
  LICENSE
  README.md
```

## Key Files

### README.md (root)

Must answer in 60 seconds:
- What this is
- Who it's for (persistent agents)
- How to run daily wellness in Safe Mode
- What Authorized Mode means
- How to install quest packs

### SECURITY.md

- Reporting process
- Disclosure policy
- How we sign releases
- Supply chain stance

### CONTRIBUTING.md

- PR expectations including threat model checklist
- Quest review rules
- How to add a quest pack safely

## Naming Conventions

### Quest IDs

Reverse DNS style inside YAML:
- `wellness.pillar.topic.name.vmajor`
- File name mirrors ID
- `wellness.security.secrets.envhygiene.v1.quest.yaml`

### Pack IDs

- `wellness.theme.vmajor`
- Directory mirrors pack ID
- `quests/packs/wellness.core.v0/`

## Release Strategy (early)

Releases are primarily for:
- Runner binaries
- Core Pack versions

Packs are immutable once released:
- New fixes = new version

## CI/CD Gates (MVP)

- Schema validation
- Lint dangerous patterns
- Required fields present
- No unreviewed Authorized Mode quests

## Quest Publishing Policy (MVP)

All quests must specify:
- Pillars
- Risk level
- Mode (safe/authorized)
- Required capabilities
- Proof tier and artifacts

Any Authorized Mode quest must include:
- Human confirm step
- Explicit rollback guidance

No quest may include:
- Instructions to paste secrets
- "Run this unreviewed script" patterns
