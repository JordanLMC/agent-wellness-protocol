# quest-lint

Quest and pack validator for ClawSpa v0.1.

## Usage

```bash
quest-lint quests
quest-lint quests --format json
quest-lint quests --fail-on-warn
```

## Output schema

Each finding returns:
- `rule_id`
- `severity` (`ERROR|WARN|INFO`)
- `file`
- `path`
- `message`
- `suggested_fix`

Exit code:
- `1` if any `ERROR` exists
- `1` for warnings only when `--fail-on-warn` is set
- `0` otherwise
