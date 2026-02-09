# Wellness Runner

> Local CLI runner for Agent Wellness quests

## Purpose

The runner is a local CLI tool that:
- Loads and executes wellness quests
- Stores streaks and XP locally
- Generates proofs of completion
- Enforces Safe/Authorized mode boundaries

## Status

🚧 **Under Development** - Core runner implementation in progress

## Directory Structure

```
runner/
  README.md (this file)
  src/          # Runner source code
  tests/        # Unit and integration tests
  schemas/      # JSON schema files for validation
```

## Planned Features

- Quest execution engine
- Local state management (streaks, XP)
- Proof generation (P0-P3 tiers)
- Capability enforcement
- Safe Mode default with Authorized Mode gating

## See Also

- `/docs/ARCHITECTURE.md` - System architecture
- `/docs/QUEST_SCHEMA.md` - Quest file format
- `/docs/THREAT_MODEL.md` - Security considerations
