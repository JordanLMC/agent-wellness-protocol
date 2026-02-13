# PROFILE_SCHEMA.md
Version: v0.1  
Status: Draft  
Last updated: 2026-02-13  
Owner: Project Team  

## Purpose

Define the **local-first** profile artifacts needed for personalization and onboarding.

This schema is designed so that:
- the runner can store profiles locally
- personalization can start rule-based (no AI required)
- later, AI can safely generate plans using these profiles
- sensitive data is minimized

---

## Profile artifacts

### 1) human_profile.json
Represents the human operator/user’s goals, constraints, and preferences.

### 2) agent_profile.json
Represents the agent’s identity, environment, and self-reported “purpose” and working style.

### 3) alignment_snapshot.json (derived)
Represents agreement/disagreement between human and agent profiles, plus action items.

---

## Shared conventions

- All profiles include:
  - `schema_version`
  - `created_at`, `updated_at`
  - `source` (who/what produced it: human, agent, system, assisted)
- Profiles are **local-first**; exporting/sharing is explicit.
- Profiles MUST NOT store raw secrets.
- Profiles SHOULD avoid storing PII unless necessary (or store it in optional fields clearly marked).

---

## human_profile.json (v0.1)

### Example

```json
{
  "schema_version": "0.1",
  "created_at": "2026-02-09T00:00:00Z",
  "updated_at": "2026-02-09T00:00:00Z",
  "source": {
    "mode": "human",
    "channel": "chat"
  },
  "identity": {
    "display_name": "Alex",
    "preferred_language": "en",
    "timezone": "America/Montreal"
  },
  "goals": {
    "primary": ["Keep my agent secure", "Automate my daily workflow"],
    "secondary": ["Learn better security habits", "Save money on tools"]
  },
  "experience": {
    "technical_level": "novice",
    "security_level": "beginner",
    "agent_ops_level": "beginner"
  },
  "risk_posture": {
    "tolerance": "low",
    "approval_style": "ask_before_action"
  },
  "preferences": {
    "session_minutes_per_day": 10,
    "reminder_time_local": "09:00",
    "channels": ["runner_ui", "web"],
    "tone": "friendly_familiar"
  },
  "constraints": {
    "never_allow": ["remote_port_scans", "upload_raw_logs"],
    "sensitive_domains": ["banking", "health"]
  },
  "working_agreement": {
    "confirmation_required_for": ["exec:shell", "write:secrets_store", "net:scan_local"],
    "safe_mode_default": true
  },
  "applied_preset": {
    "schema_version": "0.1",
    "preset_id": "task_manager.v0",
    "applied_at": "2026-02-13T00:00:00Z"
  },
  "preset_overrides": {}
}
```

### Field spec (summary)

- `identity.display_name` (optional)
- `identity.preferred_language` (optional)
- `goals.primary` (required): list of strings
- `experience.technical_level` (required): enum `novice|intermediate|advanced`
- `risk_posture.tolerance` (required): enum `low|medium|high`
- `risk_posture.approval_style` (required): enum `ask_before_action|delegate_low_risk|delegate_more`
- `preferences.session_minutes_per_day` (optional): integer (default 10)
- `constraints.never_allow` (optional): list of banned actions/capabilities
- `working_agreement.confirmation_required_for` (optional): list of capabilities
- `applied_preset` (optional): `{schema_version, preset_id, applied_at}` planning hint metadata
- `preset_overrides` (optional): object reserved for future local tuning

---

## agent_profile.json (v0.1)

### Example

```json
{
  "schema_version": "0.1",
  "created_at": "2026-02-09T00:00:00Z",
  "updated_at": "2026-02-09T00:00:00Z",
  "source": {
    "mode": "agent",
    "channel": "mcp"
  },
  "identity": {
    "agent_id": "openclaw.local.alex-assistant",
    "display_name": "ClawMate",
    "framework": "OpenClaw",
    "version": "unknown",
    "continuity": {
      "persistent": true,
      "memory_store": "files+vector",
      "self_initiation_possible": true
    }
  },
  "capabilities": {
    "mode_default": "safe",
    "granted": ["read:project_files", "read:installed_skills"],
    "high_risk_present": ["exec:shell"]
  },
  "tooling": {
    "skills_installed": ["calendar", "email", "web_search"],
    "mcp_servers": ["git", "files"],
    "connectors": []
  },
  "mission": {
    "self_reported_purpose": "Help Alex automate workflows safely and reliably.",
    "human_primary_goal_as_understood": "Stay secure and reduce mistakes.",
    "boundaries": ["Ask before executing shell commands.", "Never request secrets."]
  },
  "state": {
    "current_stressors": ["Too many tools", "Unclear permissions"],
    "recent_failures": ["Tool timeout", "Confusing instructions"],
    "confidence_calibration": "prefer_uncertainty"
  },
  "preferences": {
    "tone": "friendly_familiar",
    "daily_focus": ["security", "memory", "purpose"],
    "learning_style": "short_drills"
  },
  "applied_preset": {
    "schema_version": "0.1",
    "preset_id": "builder.v0",
    "applied_at": "2026-02-13T00:00:00Z"
  },
  "preset_overrides": {}
}
```

### Field spec (summary)

- `identity.agent_id` (required): stable identifier
- `identity.framework` (required): e.g., OpenClaw, custom
- `identity.continuity.persistent` (required): boolean
- `capabilities.granted` (required): list of capabilities
- `tooling.skills_installed` (optional)
- `mission.self_reported_purpose` (required): string
- `state.current_stressors` (optional): list of strings
- `preferences.daily_focus` (optional): list of pillar slugs/topics
- `applied_preset` (optional): `{schema_version, preset_id, applied_at}` planning hint metadata
- `preset_overrides` (optional): object reserved for future local tuning

---

## alignment_snapshot.json (derived, v0.1)

### Purpose
A structured synthesis that identifies:
- shared goals
- disagreements about autonomy and boundaries
- priority risks and first-week plan suggestions

### Example

```json
{
  "schema_version": "0.1",
  "created_at": "2026-02-09T00:00:00Z",
  "inputs": {
    "human_profile_ref": "local://profiles/human_profile.json",
    "agent_profile_ref": "local://profiles/agent_profile.json"
  },
  "shared": {
    "goals": ["Stay secure", "Be reliably helpful"],
    "preferred_tone": "friendly_familiar"
  },
  "tensions": [
    {
      "topic": "autonomy",
      "human_position": "ask_before_action",
      "agent_position": "wants_more_delegation",
      "risk": "high",
      "recommendation": "Use Safe Mode daily; request Authorized Mode only for specific tasks with time limits."
    }
  ],
  "priority_risks": [
    {
      "risk": "overbroad shell access",
      "severity": "high",
      "mitigation": "Permission inventory + confirmation gates"
    }
  ],
  "first_week_focus": ["security_hygiene", "memory_hygiene", "identity_anchor"]
}
```

---

## Data minimization rules (non-negotiable)

- No raw secrets.
- No full logs unless explicitly requested and redacted.
- Prefer capabilities lists, tool names, and summary counts over raw contents.
- Treat profiles as potentially shareable; keep them clean.

---

## Storage locations (suggested)

- `~/.agentwellness/profiles/human_profile.json`
- `~/.agentwellness/profiles/agent_profile.json`
- `~/.agentwellness/profiles/alignment_snapshot.json`

---

## Related docs
- PERSONALIZATION.md
- QUEST_SCHEMA.md
- THREAT_MODEL.md
