# REPO_STRUCTURE.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-11  
Owner: Project Team  

## Purpose

Define a repo layout that:
- keeps us aligned with scope (persistent agents)
- separates content (quests) from code (runner)
- supports secure publishing and review

---

## Recommended top-level structure

```text
/ (repo root)
  /docs/
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
    TELEMETRY.md
    PACKS.md

  /research/
    *.pdf                     # local research artifacts for quest and pillar design
    *.md                      # local synthesis notes derived from research

  /quests/
    /packs/
      /wellness.core.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.home_security.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.security_access_control.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.reliability_robustness.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.privacy_data_governance.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.transparency_auditability.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.tool_integration_hygiene.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.continuous_governance_oversight.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.openclaw.v0/
        pack.yaml
        /quests/
          *.quest.yaml
      /wellness.mcp.v0/
        pack.yaml
        /quests/
          *.quest.yaml

    /tools/
      quest-lint/             # schema validator + “dangerous patterns” detector
      pack-sign/              # signing helper (v0.2+)
      pack-build/             # checksum generator

  /runner/
    README.md
    /src/
    /tests/
    /schemas/                 # jsonschema equivalents for quest/pack
    /examples/
    /plugins/                 # runner plugins (optional)

  /mcp-server/
    README.md
    /src/
    /tests/

  /web/
    README.md
    /app/                     # optional dashboard (later)

  /examples/
    openclaw/                 # example configs, safe demo environments
    mcp/                      # example MCP server configs

  /scripts/
    release.sh
    verify.sh

  .editorconfig
  .gitignore
  LICENSE
  README.md
```

---

## Key files

### /research
- Stores local research artifacts (for example pillar PDFs) used to inform quest content.
- Git LFS is optional; use it when binary size or churn makes normal Git history noisy.

### README.md (root)
Must answer in 60 seconds:
- what this is
- who it’s for (persistent agents)
- how to run daily wellness in Safe Mode
- what “Authorized Mode” means
- how to install quest packs

### SECURITY.md
- reporting process
- disclosure policy
- how we sign releases (when we do)
- supply chain stance (content treated as code)

### CONTRIBUTING.md
- PR expectations (including threat model checklist)
- quest review rules
- how to add a quest pack safely

---

## Naming conventions

### Quest IDs
- Reverse DNS style inside YAML: `wellness.<pillar>.<topic>.<name>.v<major>`
- File name mirrors ID:
  - `wellness.security.secrets.env_hygiene.v1.quest.yaml`

### Pack IDs
- `wellness.<theme>.v<major>`
- Directory mirrors pack ID:
  - `/quests/packs/wellness.core.v0/`

---

## Release strategy (early)

- Releases are primarily for:
  - runner binaries
  - “Core Pack” versions
- Packs are immutable once released:
  - new fixes = new version
- Add a basic CI gate:
  - schema validation
  - lint dangerous patterns
  - required fields present
  - no unreviewed Authorized Mode quests

---

## Quest publishing policy (MVP)

- All quests must specify:
  - pillar(s)
  - risk_level
  - mode (safe/authorized)
  - required_capabilities
  - proof tier and artifacts
- Any Authorized Mode quest must include:
  - human confirm step
  - explicit rollback guidance (even if it’s “revert this config change”)
- No quest may include:
  - instructions to paste secrets into the runner
  - “run this unreviewed script” patterns

Optional pack note:
- `wellness.home_security.v0` is an optional Safe Mode posture pack for home environment checks.
- It is not part of `CORE_PACK_V0` daily minimum selection logic.
- `wellness.security_access_control.v0` is a pillar pack focused on access hygiene, identity checks, and safety-gated tabletop drills.
- Additional pillar packs (`reliability_robustness`, `privacy_data_governance`, `transparency_auditability`,
  `tool_integration_hygiene`, `continuous_governance_oversight`) extend v0.1 coverage while preserving local-first Safe Mode defaults.
