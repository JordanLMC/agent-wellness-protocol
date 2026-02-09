# MCP Server

Thin MCP wrapper over the local runner API.

## Tools exposed

- `get_daily_quests(date?)`
- `get_quest(quest_id)`
- `submit_proof(quest_id, tier, artifacts)`
- `get_scorecard()`
- `get_profiles()`
- `update_agent_profile(profile_patch)`

## Safety constraints

- Tool schemas accept references/metadata only.
- No raw file contents accepted.
- Intended for localhost API bridge usage.

## Run

```bash
clawspa-mcp --api-base http://127.0.0.1:8000
```
