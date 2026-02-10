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
- Tool arguments are validated for secret/PII/raw-log patterns and bounded sizes.
- Intended for localhost API bridge usage.
- `--api-base` is localhost-only by default.
- Use `--allow-nonlocal` only for explicit trusted deployments.
- `--api-base` must use `http` or `https` and must not include userinfo.

## Run

```bash
clawspa-mcp --api-base http://127.0.0.1:8000
```

```bash
# Explicit non-local override (not default)
clawspa-mcp --api-base https://trusted-host.example --allow-nonlocal
```
