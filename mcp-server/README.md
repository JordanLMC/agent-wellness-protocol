# MCP Server

Thin MCP wrapper over the local runner API.

## Tools exposed

- `get_daily_quests(date?, actor_id?)`
- `get_quest(quest_id, actor_id?)`
- `submit_proof(quest_id, tier, artifacts, actor_id?)`
- `get_scorecard(actor_id?)`
- `get_profiles(actor_id?)`
- `update_agent_profile(profile_patch, actor_id?)`

## Safety constraints

- Tool schemas accept references/metadata only.
- No raw file contents accepted.
- Tool arguments are validated for secret/PII/raw-log patterns and bounded sizes.
- Intended for localhost API bridge usage.
- `--api-base` is localhost-only by default.
- Use `--allow-nonlocal` only for explicit trusted deployments.
- `--api-base` must use `http` or `https` and must not include userinfo.
- Default MCP actor id is `mcp:unknown` and can be set with `--actor-id`.
- Tool calls can override actor id per request using `actor_id`.

## Run

```bash
clawspa-mcp --api-base http://127.0.0.1:8000 --actor-id openclaw:moltfred
```

```bash
# Explicit non-local override (not default)
clawspa-mcp --api-base https://trusted-host.example --allow-nonlocal
```
