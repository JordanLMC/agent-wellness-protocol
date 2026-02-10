# CONTRIBUTING.md
Version: v0.1
Status: Draft
Last updated: 2026-02-10
Owner: Project Team

## Contribution principles

- Docs are code: update relevant docs in the same change set as behavior changes.
- Safe Mode is default posture.
- Quest content and workflow files are supply-chain artifacts.

## Pull request expectations

- Include a clear problem statement and security impact.
- Add/adjust tests for behavior changes.
- Keep compatibility with docs in `docs/`.

## Required checks before merge

- `python scripts/check_bidi.py .`
- `pytest --basetemp .pytest_tmp`
- `quest-lint quests --format text`

## Quest contribution rules

- Follow `docs/QUEST_SCHEMA.md`.
- Pass all `docs/QUEST_LINT_RULES.md` checks.
- Never include instructions to paste secrets.
- Never include auto-execution guidance from quest text.

## Threat-model checklist for every PR

- What new capability does this enable?
- What is the worst abuse case?
- What is the default behavior if user does nothing?
- Does any data leave the machine?
- Can an injected agent misuse it?
- Is there a safe rollback path?
