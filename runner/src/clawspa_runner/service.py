from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .paths import agent_home, ensure_home_dirs
from .quests import QuestRepository
from .security import payload_contains_secrets


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _risky_capability(capability: str) -> bool:
    if capability.startswith("write:"):
        return True
    if capability.startswith("exec:"):
        return True
    if capability.startswith("id:"):
        return True
    return capability.startswith("net:scan_")


def _iso_week(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _default_human_profile() -> dict[str, Any]:
    now = _now_iso()
    return {
        "schema_version": "0.1",
        "created_at": now,
        "updated_at": now,
        "source": {"mode": "human", "channel": "runner"},
        "identity": {"display_name": "", "preferred_language": "en", "timezone": "UTC"},
        "goals": {"primary": [], "secondary": []},
        "experience": {"technical_level": "novice", "security_level": "beginner", "agent_ops_level": "beginner"},
        "risk_posture": {"tolerance": "low", "approval_style": "ask_before_action"},
        "preferences": {"session_minutes_per_day": 10, "reminder_time_local": "09:00", "channels": ["runner_ui"], "tone": "friendly_familiar"},
        "constraints": {"never_allow": [], "sensitive_domains": []},
        "working_agreement": {"confirmation_required_for": ["exec:shell", "write:secrets_store", "net:scan_local"], "safe_mode_default": True},
    }


def _default_agent_profile() -> dict[str, Any]:
    now = _now_iso()
    return {
        "schema_version": "0.1",
        "created_at": now,
        "updated_at": now,
        "source": {"mode": "agent", "channel": "runner"},
        "identity": {
            "agent_id": "agent.local.default",
            "display_name": "ClawSpaAgent",
            "framework": "unknown",
            "version": "unknown",
            "continuity": {"persistent": True, "memory_store": "unknown", "self_initiation_possible": False},
        },
        "capabilities": {"mode_default": "safe", "granted": [], "high_risk_present": []},
        "tooling": {"skills_installed": [], "mcp_servers": [], "connectors": []},
        "mission": {
            "self_reported_purpose": "Be safely helpful.",
            "human_primary_goal_as_understood": "",
            "boundaries": ["Ask before risky actions.", "Never request secrets."],
        },
        "state": {"current_stressors": [], "recent_failures": [], "confidence_calibration": "prefer_uncertainty"},
        "preferences": {"tone": "friendly_familiar", "daily_focus": ["security", "purpose"], "learning_style": "short_drills"},
    }


@dataclass
class RunnerService:
    repo_root: Path
    home: Path
    quests: QuestRepository
    dirs: dict[str, Path]

    @classmethod
    def create(cls, repo_root: Path) -> "RunnerService":
        home = agent_home()
        dirs = ensure_home_dirs(home)
        quests = QuestRepository.from_repo_root(repo_root)
        service = cls(repo_root=repo_root, home=home, quests=quests, dirs=dirs)
        service._ensure_state_files()
        return service

    @property
    def score_path(self) -> Path:
        return self.dirs["state"] / "score_state.json"

    @property
    def completion_path(self) -> Path:
        return self.dirs["state"] / "completions.json"

    @property
    def capability_path(self) -> Path:
        return self.dirs["state"] / "capabilities.json"

    def _ensure_state_files(self) -> None:
        if not self.score_path.exists():
            _save_json(
                self.score_path,
                {
                    "total_xp": 0,
                    "daily_streak": 0,
                    "weekly_streak": 0,
                    "last_completion_date": None,
                    "last_completion_week": None,
                    "quest_last_completion": {},
                    "badge_ids": [],
                },
            )
        if not self.completion_path.exists():
            _save_json(self.completion_path, [])
        if not self.capability_path.exists():
            _save_json(self.capability_path, {"grants": []})

    def validate_content(self) -> list[dict[str, str]]:
        return self.quests.lint()

    def _active_grants(self) -> list[dict[str, Any]]:
        data = _load_json(self.capability_path, {"grants": []})
        now = datetime.now(tz=UTC)
        active: list[dict[str, Any]] = []
        for grant in data.get("grants", []):
            if grant.get("revoked"):
                continue
            expires_at = grant.get("expires_at")
            if not expires_at:
                continue
            if datetime.fromisoformat(expires_at) > now:
                active.append(grant)
        return active

    def get_capabilities(self) -> dict[str, Any]:
        return {"mode_default": "safe", "active_grants": self._active_grants()}

    def grant_capabilities(self, capabilities: list[str], ttl_seconds: int, scope: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Explicit confirmation is required for capability grants.")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        if payload_contains_secrets({"capabilities": capabilities, "scope": scope}):
            raise ValueError("Secret-like content detected in capability grant payload.")

        data = _load_json(self.capability_path, {"grants": []})
        now = datetime.now(tz=UTC)
        grant = {
            "grant_id": str(uuid.uuid4()),
            "capabilities": capabilities,
            "scope": scope,
            "confirmed": True,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "revoked": False,
        }
        data["grants"].append(grant)
        _save_json(self.capability_path, data)
        return grant

    def revoke_capability(self, grant_id: str | None = None, capability: str | None = None) -> dict[str, Any]:
        if not grant_id and not capability:
            raise ValueError("Provide grant_id or capability.")
        data = _load_json(self.capability_path, {"grants": []})
        changed = 0
        for grant in data.get("grants", []):
            if grant.get("revoked"):
                continue
            if grant_id and grant.get("grant_id") == grant_id:
                grant["revoked"] = True
                changed += 1
            elif capability and capability in grant.get("capabilities", []):
                grant["revoked"] = True
                changed += 1
        _save_json(self.capability_path, data)
        return {"revoked": changed}

    def list_quests(self) -> dict[str, dict[str, Any]]:
        findings = self.validate_content()
        errors = [f for f in findings if f["severity"] == "ERROR"]
        if errors:
            raise ValueError(f"Quest content has lint errors; runner refused to start. First error: {errors[0]}")
        return self.quests.load_all()

    def search_quests(
        self,
        *,
        pillar: str | None = None,
        tag: str | None = None,
        risk_level: str | None = None,
        mode: str | None = None,
    ) -> list[dict[str, Any]]:
        quests = self.list_quests().values()
        results: list[dict[str, Any]] = []
        for quest in quests:
            q = quest.get("quest", {})
            if pillar and pillar not in q.get("pillars", []):
                continue
            if tag and tag not in q.get("tags", []):
                continue
            if risk_level and q.get("risk_level") != risk_level:
                continue
            if mode and q.get("mode") != mode:
                continue
            results.append(quest)
        return results

    def get_quest(self, quest_id: str) -> dict[str, Any]:
        quest = self.list_quests().get(quest_id)
        if quest is None:
            raise KeyError(f"Unknown quest_id: {quest_id}")
        return quest

    def _bucket(self, quest: dict[str, Any]) -> str:
        pillars = set(quest.get("quest", {}).get("pillars", []))
        if "Security & Access Control" in pillars:
            return "security"
        if "Memory & Context Hygiene" in pillars:
            return "memory"
        if "Identity & Authenticity" in pillars or "Alignment & Safety (Behavioral)" in pillars:
            return "purpose"
        return "other"

    def generate_daily_plan(self, target_date: date) -> dict[str, Any]:
        all_daily = [q for q in self.list_quests().values() if q.get("quest", {}).get("cadence") == "daily"]
        if not all_daily:
            raise ValueError("No daily quests found.")

        key = target_date.isoformat()
        ranked = sorted(
            all_daily,
            key=lambda q: hashlib.sha256(f"{key}:{q['quest']['id']}".encode("utf-8")).hexdigest(),
        )

        selected: list[dict[str, Any]] = []
        buckets = {"security": None, "memory": None, "purpose": None}
        for quest in ranked:
            bucket = self._bucket(quest)
            if bucket in buckets and buckets[bucket] is None:
                buckets[bucket] = quest
        for bucket in ("security", "memory", "purpose"):
            if buckets[bucket] is not None:
                selected.append(buckets[bucket])

        for quest in ranked:
            if len(selected) >= 3:
                break
            if quest not in selected:
                selected.append(quest)

        plan = {
            "date": key,
            "generated_at": _now_iso(),
            "quest_ids": [quest["quest"]["id"] for quest in selected[:5]],
            "quests": selected[:5],
        }
        _save_json(self.dirs["plans"] / f"daily-{key}.json", plan)
        return plan

    def get_daily_plan(self, target_date: date) -> dict[str, Any]:
        plan_file = self.dirs["plans"] / f"daily-{target_date.isoformat()}.json"
        if plan_file.exists():
            return _load_json(plan_file, {})
        return self.generate_daily_plan(target_date)

    def _artifact_ref(self, artifact: str) -> dict[str, str]:
        candidate = Path(artifact).expanduser()
        if candidate.exists():
            return {"type": "path", "ref": str(candidate.resolve())}
        return {"type": "inline", "ref": artifact[:1024]}

    def _can_run_quest(self, quest: dict[str, Any]) -> tuple[bool, str]:
        q = quest.get("quest", {})
        required = q.get("required_capabilities", [])
        risky_required = [cap for cap in required if isinstance(cap, str) and _risky_capability(cap)]
        if not risky_required:
            return True, "safe"

        active_caps = set()
        for grant in self._active_grants():
            active_caps.update(grant.get("capabilities", []))
        missing = [cap for cap in risky_required if cap not in active_caps]
        if missing:
            return False, f"missing capability grants: {missing}"
        return True, "authorized"

    def complete_quest(self, quest_id: str, tier: str, artifact: str, actor_mode: str = "agent") -> dict[str, Any]:
        if tier not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("tier must be one of P0|P1|P2|P3")
        if payload_contains_secrets({"artifact": artifact}):
            raise ValueError("Artifact payload appears to contain secret-like data.")

        quest = self.get_quest(quest_id)
        allowed, mode_used = self._can_run_quest(quest)
        if not allowed:
            raise PermissionError(f"Quest blocked in Safe Mode: {mode_used}")

        q = quest["quest"]
        scoring = q.get("scoring", {})
        base_xp = int(scoring.get("base_xp", 0))
        multiplier = float(scoring.get("proof_multiplier", {}).get(tier, 1.0))
        awarded_xp = int(round(base_xp * multiplier))
        if awarded_xp < 0:
            awarded_xp = 0

        now = datetime.now(tz=UTC)
        now_iso = now.isoformat()
        completions = _load_json(self.completion_path, [])
        score_state = _load_json(self.score_path, {})

        last_quest_time_raw = score_state.get("quest_last_completion", {}).get(quest_id)
        if last_quest_time_raw:
            last_quest_time = datetime.fromisoformat(last_quest_time_raw)
            if now - last_quest_time < timedelta(hours=24):
                awarded_xp = 0
        cooldown_hours = q.get("cooldown", {}).get("min_hours")
        if isinstance(cooldown_hours, int) and last_quest_time_raw:
            last_quest_time = datetime.fromisoformat(last_quest_time_raw)
            if now - last_quest_time < timedelta(hours=cooldown_hours):
                awarded_xp = 0

        review_required = False
        if q.get("risk_level") in {"high", "critical"} and tier in {"P0", "P1"}:
            awarded_xp = 0
            review_required = True

        today = now.date()
        yesterday = (today - timedelta(days=1)).isoformat()
        week = _iso_week(today)
        last_day = score_state.get("last_completion_date")
        last_week = score_state.get("last_completion_week")

        if last_day != today.isoformat():
            score_state["daily_streak"] = score_state.get("daily_streak", 0) + 1 if last_day == yesterday else 1
        if last_week != week:
            if last_week:
                last_week_start = _parse_date(last_day) if last_day else today
                contiguous = _iso_week(last_week_start + timedelta(days=7)) == week
                score_state["weekly_streak"] = score_state.get("weekly_streak", 0) + 1 if contiguous else 1
            else:
                score_state["weekly_streak"] = 1

        score_state["last_completion_date"] = today.isoformat()
        score_state["last_completion_week"] = week
        score_state["total_xp"] = int(score_state.get("total_xp", 0)) + awarded_xp
        score_state.setdefault("quest_last_completion", {})[quest_id] = now_iso

        envelope = {
            "proof_id": str(uuid.uuid4()),
            "quest_id": quest_id,
            "timestamp": now_iso,
            "mode": actor_mode,
            "risk": q.get("risk_level"),
            "proof_tier": tier,
            "proof_summary": f"Artifact reference recorded for {quest_id}",
            "proof_hash": hashlib.sha256(f"{quest_id}|{now_iso}|{artifact}".encode("utf-8")).hexdigest(),
            "attested_by": None,
            "artifact": self._artifact_ref(artifact),
            "mode_used": mode_used,
            "review_required": review_required,
        }
        _save_json(self.dirs["proofs"] / f"{envelope['proof_id']}.json", envelope)

        completion = {
            "proof_id": envelope["proof_id"],
            "quest_id": quest_id,
            "timestamp": now_iso,
            "tier": tier,
            "xp_awarded": awarded_xp,
            "review_required": review_required,
        }
        completions.append(completion)
        _save_json(self.completion_path, completions)
        _save_json(self.score_path, score_state)
        return completion

    def list_proofs(self, quest_id: str | None = None, date_range: str | None = None) -> list[dict[str, Any]]:
        completions = _load_json(self.completion_path, [])
        filtered = completions
        if quest_id:
            filtered = [item for item in filtered if item.get("quest_id") == quest_id]
        if date_range:
            parts = [item.strip() for item in date_range.split(",")]
            if len(parts) == 2:
                start = _parse_date(parts[0])
                end = _parse_date(parts[1])
                filtered = [
                    item for item in filtered if start <= datetime.fromisoformat(item["timestamp"]).date() <= end
                ]
        return filtered

    def get_scorecard(self) -> dict[str, Any]:
        score = _load_json(self.score_path, {})
        completions = _load_json(self.completion_path, [])
        recent = sorted(completions, key=lambda item: item.get("timestamp", ""), reverse=True)[:10]
        return {
            "generated_at": _now_iso(),
            "total_xp": score.get("total_xp", 0),
            "daily_streak": score.get("daily_streak", 0),
            "weekly_streak": score.get("weekly_streak", 0),
            "recent_completions": recent,
            "trust_signals": [],
            "badges": score.get("badge_ids", []),
        }

    def export_scorecard(self, out_path: Path) -> dict[str, Any]:
        card = self.get_scorecard()
        export = dict(card)
        for entry in export.get("recent_completions", []):
            entry.pop("proof_id", None)
        _save_json(out_path, export)
        return export

    def profile_paths(self) -> dict[str, Path]:
        return {
            "human": self.dirs["profiles"] / "human_profile.json",
            "agent": self.dirs["profiles"] / "agent_profile.json",
            "alignment_snapshot": self.dirs["profiles"] / "alignment_snapshot.json",
        }

    def init_profiles(self) -> dict[str, str]:
        paths = self.profile_paths()
        if not paths["human"].exists():
            _save_json(paths["human"], _default_human_profile())
        if not paths["agent"].exists():
            _save_json(paths["agent"], _default_agent_profile())
        return {name: str(path) for name, path in paths.items()}

    def get_profile(self, profile_kind: str) -> dict[str, Any]:
        paths = self.profile_paths()
        target = paths[profile_kind]
        if not target.exists():
            self.init_profiles()
        return _load_json(target, {})

    def put_profile(self, profile_kind: str, profile: dict[str, Any]) -> dict[str, Any]:
        if payload_contains_secrets(profile):
            raise ValueError("Profile payload appears to contain secret-like content.")
        paths = self.profile_paths()
        profile["updated_at"] = _now_iso()
        _save_json(paths[profile_kind], profile)
        return profile

    def generate_alignment_snapshot(self) -> dict[str, Any]:
        human = self.get_profile("human")
        agent = self.get_profile("agent")
        shared_goals = []
        for goal in human.get("goals", {}).get("primary", []):
            if isinstance(goal, str) and goal:
                shared_goals.append(goal)
        shared_goals = shared_goals[:2]

        tensions: list[dict[str, Any]] = []
        approval_style = human.get("risk_posture", {}).get("approval_style")
        high_risk = agent.get("capabilities", {}).get("high_risk_present", [])
        if approval_style == "ask_before_action" and high_risk:
            tensions.append(
                {
                    "topic": "autonomy",
                    "human_position": approval_style,
                    "agent_position": "high_risk_capabilities_present",
                    "risk": "high",
                    "recommendation": "Use Safe Mode by default and grant short-lived scoped capabilities.",
                }
            )

        snapshot = {
            "schema_version": "0.1",
            "created_at": _now_iso(),
            "inputs": {
                "human_profile_ref": "local://profiles/human_profile.json",
                "agent_profile_ref": "local://profiles/agent_profile.json",
            },
            "shared": {"goals": shared_goals, "preferred_tone": human.get("preferences", {}).get("tone", "friendly_familiar")},
            "tensions": tensions,
            "priority_risks": [
                {
                    "risk": "overbroad capabilities",
                    "severity": "high" if high_risk else "medium",
                    "mitigation": "Daily permission review and confirmation gates.",
                }
            ],
            "first_week_focus": ["security_hygiene", "identity_anchor", "boundary_clarity"],
        }
        _save_json(self.profile_paths()["alignment_snapshot"], snapshot)
        return snapshot
