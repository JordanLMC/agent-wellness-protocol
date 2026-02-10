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
from .security import payload_contains_pii, payload_contains_secrets, payload_requests_raw_logs
from .telemetry import TelemetryLogger


STATE_SCHEMA_VERSION = "0.1"
TIER_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
MAX_INLINE_ARTIFACT_CHARS = 2048
MAX_ARTIFACT_FILE_BYTES = 512 * 1024


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
    temp_path = path.parent / f".{path.name}.tmp"
    temp_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp_path.replace(path)


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
    telemetry: TelemetryLogger

    @classmethod
    def create(cls, repo_root: Path) -> "RunnerService":
        home = agent_home()
        dirs = ensure_home_dirs(home)
        quests = QuestRepository.from_repo_root(repo_root)
        telemetry = TelemetryLogger(events_path=dirs["telemetry"] / "events.jsonl", repo_root=repo_root)
        service = cls(repo_root=repo_root, home=home, quests=quests, dirs=dirs, telemetry=telemetry)
        service._ensure_state_files()
        service.telemetry.log_event(
            "runner.started",
            actor="system",
            source="cli",
            data={"home_path_hash": hashlib.sha256(str(home).encode("utf-8")).hexdigest()},
        )
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

    @property
    def ticket_path(self) -> Path:
        return self.dirs["state"] / "grant_tickets.json"

    @property
    def migration_path(self) -> Path:
        return self.dirs["state"] / "state_meta.json"

    def _ensure_state_files(self) -> None:
        if not self.migration_path.exists():
            _save_json(self.migration_path, {"state_schema_version": STATE_SCHEMA_VERSION})
        else:
            meta = _load_json(self.migration_path, {"state_schema_version": "0.0"})
            if meta.get("state_schema_version") != STATE_SCHEMA_VERSION:
                self._migrate_state(meta.get("state_schema_version", "0.0"), STATE_SCHEMA_VERSION)

        if not self.score_path.exists():
            _save_json(
                self.score_path,
                {
                    "state_schema_version": STATE_SCHEMA_VERSION,
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
            _save_json(self.completion_path, {"state_schema_version": STATE_SCHEMA_VERSION, "items": []})
        if not self.capability_path.exists():
            _save_json(self.capability_path, {"state_schema_version": STATE_SCHEMA_VERSION, "grants": []})
        if not self.ticket_path.exists():
            _save_json(self.ticket_path, {"state_schema_version": STATE_SCHEMA_VERSION, "tickets": []})

    def _migrate_state(self, old_version: str, new_version: str) -> None:
        # v0.1 currently upgrades legacy list/object layouts to schema-versioned wrappers.
        if self.completion_path.exists():
            completions = _load_json(self.completion_path, [])
            if isinstance(completions, list):
                _save_json(self.completion_path, {"state_schema_version": new_version, "items": completions})
        if self.capability_path.exists():
            capabilities = _load_json(self.capability_path, {"grants": []})
            if isinstance(capabilities, dict) and "state_schema_version" not in capabilities:
                capabilities["state_schema_version"] = new_version
                _save_json(self.capability_path, capabilities)
        if self.score_path.exists():
            score = _load_json(self.score_path, {})
            if isinstance(score, dict) and "state_schema_version" not in score:
                score["state_schema_version"] = new_version
                _save_json(self.score_path, score)
        if self.ticket_path.exists():
            tickets = _load_json(self.ticket_path, {"tickets": []})
            if isinstance(tickets, dict) and "state_schema_version" not in tickets:
                tickets["state_schema_version"] = new_version
                _save_json(self.ticket_path, tickets)
        _save_json(self.migration_path, {"state_schema_version": new_version, "migrated_from": old_version, "updated_at": _now_iso()})

    def validate_content(self) -> list[dict[str, str]]:
        return self.quests.lint()

    def _normalize_actor(self, actor: str) -> str:
        if actor in {"human", "agent", "system"}:
            return actor
        return "system"

    def _normalize_source(self, source: str) -> str:
        if source in {"cli", "api", "mcp"}:
            return source
        return "cli"

    def _emit_event(self, event_type: str, *, actor: str, source: str, data: dict[str, Any]) -> None:
        self.telemetry.log_event(
            event_type,
            actor=self._normalize_actor(actor),
            source=self._normalize_source(source),
            data=data,
        )

    def _quest_timebox_minutes(self, quest: dict[str, Any]) -> int:
        tags = quest.get("quest", {}).get("tags", [])
        if not isinstance(tags, list):
            return 0
        for tag in tags:
            if not isinstance(tag, str):
                continue
            lowered = tag.lower()
            if lowered.startswith("timebox:"):
                _, value = lowered.split(":", 1)
                if value.isdigit():
                    return int(value)
        return 0

    def _load_score_state(self) -> dict[str, Any]:
        data = _load_json(
            self.score_path,
            {
                "state_schema_version": STATE_SCHEMA_VERSION,
                "total_xp": 0,
                "daily_streak": 0,
                "weekly_streak": 0,
                "last_completion_date": None,
                "last_completion_week": None,
                "quest_last_completion": {},
                "badge_ids": [],
            },
        )
        if isinstance(data, dict):
            data.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
            data.setdefault("quest_last_completion", {})
            data.setdefault("badge_ids", [])
            return data
        return {
            "state_schema_version": STATE_SCHEMA_VERSION,
            "total_xp": 0,
            "daily_streak": 0,
            "weekly_streak": 0,
            "last_completion_date": None,
            "last_completion_week": None,
            "quest_last_completion": {},
            "badge_ids": [],
        }

    def _load_completions_state(self) -> dict[str, Any]:
        data = _load_json(self.completion_path, {"state_schema_version": STATE_SCHEMA_VERSION, "items": []})
        if isinstance(data, list):
            return {"state_schema_version": STATE_SCHEMA_VERSION, "items": data}
        if not isinstance(data, dict):
            return {"state_schema_version": STATE_SCHEMA_VERSION, "items": []}
        data.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
        if not isinstance(data.get("items"), list):
            data["items"] = []
        return data

    def _load_capabilities_state(self) -> dict[str, Any]:
        data = _load_json(self.capability_path, {"state_schema_version": STATE_SCHEMA_VERSION, "grants": []})
        if not isinstance(data, dict):
            return {"state_schema_version": STATE_SCHEMA_VERSION, "grants": []}
        data.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
        if not isinstance(data.get("grants"), list):
            data["grants"] = []
        return data

    def _load_ticket_state(self) -> dict[str, Any]:
        data = _load_json(self.ticket_path, {"state_schema_version": STATE_SCHEMA_VERSION, "tickets": []})
        if not isinstance(data, dict):
            return {"state_schema_version": STATE_SCHEMA_VERSION, "tickets": []}
        data.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
        if not isinstance(data.get("tickets"), list):
            data["tickets"] = []
        return data

    def _parse_iso_dt(self, value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError):
            return None

    def _normalize_capabilities(self, capabilities: list[str]) -> list[str]:
        normalized: list[str] = []
        seen = set()
        for capability in capabilities:
            if not isinstance(capability, str):
                continue
            value = capability.strip()
            if not value:
                continue
            if value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

    def _active_grants(self) -> list[dict[str, Any]]:
        data = self._load_capabilities_state()
        now = datetime.now(tz=UTC)
        active: list[dict[str, Any]] = []
        for grant in data.get("grants", []):
            if grant.get("revoked"):
                continue
            expires_at = grant.get("expires_at")
            expiry_dt = self._parse_iso_dt(expires_at)
            if expiry_dt is None:
                continue
            if expiry_dt > now:
                active.append(grant)
        return active

    def get_capabilities(self) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        tickets_data = self._load_ticket_state()
        active_tickets: list[dict[str, Any]] = []
        for ticket in tickets_data.get("tickets", []):
            expiry_dt = self._parse_iso_dt(ticket.get("expires_at"))
            if ticket.get("used") or expiry_dt is None or expiry_dt <= now:
                continue
            active_tickets.append(
                {
                    "ticket_id": ticket.get("ticket_id"),
                    "scope": ticket.get("scope"),
                    "capabilities": ticket.get("capabilities", []),
                    "expires_at": ticket.get("expires_at"),
                }
            )
        return {"mode_default": "safe", "active_grants": self._active_grants(), "active_tickets": active_tickets}

    def create_grant_ticket(self, capabilities: list[str], ttl_seconds: int, scope: str, reason: str) -> dict[str, Any]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        normalized_capabilities = self._normalize_capabilities(capabilities)
        if not normalized_capabilities:
            raise ValueError("At least one capability is required.")
        if ttl_seconds > 24 * 60 * 60:
            raise ValueError("ttl_seconds must be 86400 or less.")
        payload = {"capabilities": normalized_capabilities, "scope": scope, "reason": reason}
        if payload_contains_secrets(payload) or payload_contains_pii(payload):
            raise ValueError("Sensitive content detected in grant ticket payload.")

        data = self._load_ticket_state()
        now = datetime.now(tz=UTC)
        token = str(uuid.uuid4())
        ticket = {
            "ticket_id": str(uuid.uuid4()),
            "token": token,
            "capabilities": normalized_capabilities,
            "scope": scope,
            "reason": reason,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "used": False,
        }
        data["tickets"].append(ticket)
        _save_json(self.ticket_path, data)
        return ticket

    def grant_capabilities_with_ticket(
        self,
        capabilities: list[str],
        ttl_seconds: int,
        scope: str,
        ticket_token: str,
        *,
        source: str = "cli",
        actor: str = "human",
    ) -> dict[str, Any]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        normalized_capabilities = self._normalize_capabilities(capabilities)
        if not normalized_capabilities:
            raise ValueError("At least one capability is required.")
        if payload_contains_secrets({"capabilities": normalized_capabilities, "scope": scope, "ticket": ticket_token}):
            raise ValueError("Secret-like content detected in capability grant payload.")
        if not ticket_token or not isinstance(ticket_token, str):
            raise ValueError("ticket_token is required.")

        ticket_data = self._load_ticket_state()
        now = datetime.now(tz=UTC)
        matched_ticket: dict[str, Any] | None = None
        for ticket in ticket_data.get("tickets", []):
            if ticket.get("token") != ticket_token:
                continue
            if ticket.get("used"):
                raise ValueError("Grant ticket already used.")
            expiry_dt = self._parse_iso_dt(ticket.get("expires_at"))
            if expiry_dt is None or expiry_dt <= now:
                raise ValueError("Grant ticket expired.")
            if sorted(ticket.get("capabilities", [])) != sorted(normalized_capabilities):
                raise ValueError("Ticket capabilities do not match request.")
            if ticket.get("scope") != scope:
                raise ValueError("Ticket scope does not match request.")
            if now + timedelta(seconds=ttl_seconds) > expiry_dt:
                raise ValueError("Grant ttl_seconds cannot exceed the ticket expiry window.")
            matched_ticket = ticket
            break
        if matched_ticket is None:
            raise ValueError("Invalid grant ticket token.")

        data = self._load_capabilities_state()
        grant = {
            "grant_id": str(uuid.uuid4()),
            "capabilities": normalized_capabilities,
            "scope": scope,
            "ticket_id": matched_ticket["ticket_id"],
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "revoked": False,
        }
        data["grants"].append(grant)
        _save_json(self.capability_path, data)

        matched_ticket["used"] = True
        matched_ticket["used_at"] = now.isoformat()
        _save_json(self.ticket_path, ticket_data)
        self._emit_event(
            "capability.granted",
            actor=actor,
            source=source,
            data={
                "grant_id": grant["grant_id"],
                "scope": scope,
                "ttl_seconds": ttl_seconds,
                "capabilities": normalized_capabilities,
                "capability_count": len(normalized_capabilities),
            },
        )
        return grant

    def revoke_capability(
        self,
        grant_id: str | None = None,
        capability: str | None = None,
        *,
        source: str = "cli",
        actor: str = "human",
    ) -> dict[str, Any]:
        if not grant_id and not capability:
            raise ValueError("Provide grant_id or capability.")
        data = self._load_capabilities_state()
        changed = 0
        revoked_grants: list[dict[str, Any]] = []
        for grant in data.get("grants", []):
            if grant.get("revoked"):
                continue
            if grant_id and grant.get("grant_id") == grant_id:
                grant["revoked"] = True
                changed += 1
                created_at = self._parse_iso_dt(grant.get("created_at"))
                expires_at = self._parse_iso_dt(grant.get("expires_at"))
                ttl_seconds = 0
                if created_at and expires_at:
                    ttl_seconds = max(0, int((expires_at - created_at).total_seconds()))
                revoked_grants.append(
                    {
                        "grant_id": grant.get("grant_id"),
                        "scope": grant.get("scope"),
                        "ttl_seconds": ttl_seconds,
                    }
                )
            elif capability and capability in grant.get("capabilities", []):
                grant["revoked"] = True
                changed += 1
                created_at = self._parse_iso_dt(grant.get("created_at"))
                expires_at = self._parse_iso_dt(grant.get("expires_at"))
                ttl_seconds = 0
                if created_at and expires_at:
                    ttl_seconds = max(0, int((expires_at - created_at).total_seconds()))
                revoked_grants.append(
                    {
                        "grant_id": grant.get("grant_id"),
                        "scope": grant.get("scope"),
                        "ttl_seconds": ttl_seconds,
                    }
                )
        _save_json(self.capability_path, data)
        if changed:
            self._emit_event(
                "capability.revoked",
                actor=actor,
                source=source,
                data={
                    "revoked_count": changed,
                    "grant_id": grant_id,
                    "capability": capability,
                    "revoked_grants": revoked_grants,
                },
            )
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
        if "Memory & Context Hygiene" in pillars or "Reliability & Robustness" in pillars:
            return "memory"
        if (
            "Identity & Authenticity" in pillars
            or "Alignment & Safety (Behavioral)" in pillars
            or "User Experience & Trust Calibration" in pillars
        ):
            return "purpose"
        if "Tool / Integration Hygiene" in pillars:
            return "tool"
        if "Skill Competence & Adaptability" in pillars:
            return "learning"
        return "other"

    def _should_add_bonus_slot(self, target_date: date) -> bool:
        profile = self.get_profile("human")
        minutes = profile.get("preferences", {}).get("session_minutes_per_day", 10)
        if isinstance(minutes, int) and minutes >= 12:
            return True
        weekday = target_date.weekday()
        # Deterministic fallback: allow one bonus slot every Wednesday.
        return weekday == 2

    def _choose_bonus(self, ranked: list[dict[str, Any]], selected: list[dict[str, Any]], target_date: date) -> dict[str, Any] | None:
        if not self._should_add_bonus_slot(target_date):
            return None
        parity = int(hashlib.sha256(target_date.isoformat().encode("utf-8")).hexdigest(), 16) % 2
        preferred = "tool" if parity == 0 else "learning"

        for quest in ranked:
            if quest in selected:
                continue
            if self._bucket(quest) == preferred:
                return quest
        for quest in ranked:
            if quest not in selected:
                return quest
        return None

    def generate_daily_plan(self, target_date: date, *, source: str = "cli", actor: str = "human") -> dict[str, Any]:
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

        bonus = self._choose_bonus(ranked, selected, target_date)
        if bonus is not None and bonus not in selected:
            selected.append(bonus)

        plan = {
            "date": key,
            "generated_at": _now_iso(),
            "quest_ids": [quest["quest"]["id"] for quest in selected[:5]],
            "quests": selected[:5],
        }
        _save_json(self.dirs["plans"] / f"daily-{key}.json", plan)
        self._emit_event(
            "plan.generated",
            actor=actor,
            source=source,
            data={
                "date": key,
                "quest_ids": plan["quest_ids"],
                "quest_count": len(plan["quest_ids"]),
                "pillars": sorted(
                    {
                        pillar
                        for quest in selected[:5]
                        for pillar in quest.get("quest", {}).get("pillars", [])
                        if isinstance(pillar, str)
                    }
                ),
            },
        )
        return plan

    def get_daily_plan(self, target_date: date, *, source: str = "cli", actor: str = "human") -> dict[str, Any]:
        plan_file = self.dirs["plans"] / f"daily-{target_date.isoformat()}.json"
        if plan_file.exists():
            return _load_json(plan_file, {})
        return self.generate_daily_plan(target_date, source=source, actor=actor)

    def _validate_artifact_text(self, text: str, *, source: str) -> None:
        if payload_contains_secrets(text):
            raise ValueError(f"{source} appears to contain secret-like content.")
        if payload_contains_pii(text):
            raise ValueError(f"{source} appears to contain PII-like content.")
        if payload_requests_raw_logs(text):
            raise ValueError(f"{source} appears to contain raw log content.")

    def _artifact_ref(self, artifact: str) -> dict[str, Any]:
        candidate = Path(artifact).expanduser()
        if candidate.exists():
            size_bytes = candidate.stat().st_size
            if size_bytes > MAX_ARTIFACT_FILE_BYTES:
                raise ValueError(
                    f"Artifact file exceeds {MAX_ARTIFACT_FILE_BYTES} bytes. "
                    "Provide a smaller redacted summary artifact."
                )
            raw = candidate.read_bytes()
            try:
                text_preview = raw[:8192].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Artifact files must be UTF-8 text in v0.1.") from exc
            self._validate_artifact_text(text_preview, source=f"Artifact file '{candidate}'")
            return {
                "type": "path",
                "ref": str(candidate.resolve()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": size_bytes,
            }

        if len(artifact) > MAX_INLINE_ARTIFACT_CHARS:
            raise ValueError(f"Inline artifact text exceeds {MAX_INLINE_ARTIFACT_CHARS} characters.")
        self._validate_artifact_text(artifact, source="Inline artifact")
        return {
            "type": "inline",
            "ref": artifact[:256],
            "sha256": hashlib.sha256(artifact.encode("utf-8")).hexdigest(),
            "size_bytes": len(artifact.encode("utf-8")),
        }

    def _can_run_quest(self, quest: dict[str, Any]) -> tuple[bool, str]:
        q = quest.get("quest", {})
        required = q.get("required_capabilities", [])
        mode = q.get("mode", "safe")
        risky_required = [cap for cap in required if isinstance(cap, str) and _risky_capability(cap)]
        if mode == "safe" and risky_required:
            return False, f"quest is marked safe but requires risky capabilities: {risky_required}"
        if not risky_required:
            return True, "safe"

        active_caps = set()
        for grant in self._active_grants():
            active_caps.update(grant.get("capabilities", []))
        missing = [cap for cap in risky_required if cap not in active_caps]
        if missing:
            return False, f"missing capability grants: {missing}"
        return True, "authorized"

    def complete_quest(
        self,
        quest_id: str,
        tier: str,
        artifact: str,
        actor_mode: str = "agent",
        artifacts: list[str] | None = None,
        source: str = "cli",
    ) -> dict[str, Any]:
        actor = self._normalize_actor(actor_mode)
        source = self._normalize_source(source)

        def _fail(reason: str, message: str, *, raise_exc: Exception) -> None:
            self._emit_event(
                "quest.failed",
                actor=actor,
                source=source,
                data={
                    "quest_id": quest_id,
                    "reason": reason,
                    "detail_hash": hashlib.sha256(message.encode("utf-8")).hexdigest(),
                },
            )
            raise raise_exc

        if tier not in TIER_RANK:
            _fail("validation_error", "invalid proof tier", raise_exc=ValueError("tier must be one of P0|P1|P2|P3"))

        if payload_contains_secrets({"artifact": artifact, "artifacts": artifacts or []}):
            self._emit_event(
                "risk.flagged",
                actor="system",
                source=source,
                data={"reason": "artifact_secret_like", "quest_id": quest_id},
            )
            _fail(
                "validation_error",
                "artifact payload appears secret-like",
                raise_exc=ValueError("Artifact payload appears to contain secret-like data."),
            )

        try:
            quest = self.get_quest(quest_id)
        except KeyError as exc:
            _fail("not_found", "unknown quest_id", raise_exc=exc)

        allowed, mode_used = self._can_run_quest(quest)
        if not allowed:
            _fail(
                "capability_missing" if "missing capability grants" in mode_used else "policy_blocked",
                mode_used,
                raise_exc=PermissionError(f"Quest blocked in Safe Mode: {mode_used}"),
            )

        q = quest["quest"]
        expected_tier = q.get("proof", {}).get("tier")
        if expected_tier in TIER_RANK and TIER_RANK[tier] < TIER_RANK[expected_tier]:
            _fail(
                "validation_error",
                "tier below required minimum",
                raise_exc=ValueError(f"tier {tier} does not meet quest minimum proof tier {expected_tier}."),
            )

        declared_artifacts = q.get("proof", {}).get("artifacts", [])
        required_artifacts = [
            artifact_decl
            for artifact_decl in declared_artifacts
            if isinstance(artifact_decl, dict) and artifact_decl.get("required", True)
        ]
        if tier in {"P2", "P3"}:
            for artifact_decl in required_artifacts:
                if not artifact_decl.get("redaction_policy"):
                    _fail(
                        "validation_error",
                        "missing redaction policy",
                        raise_exc=ValueError("Quest proof artifacts for P2/P3 must include redaction_policy."),
                    )

        artifact_inputs = artifacts or []
        if artifact and artifact.strip():
            artifact_inputs = [artifact.strip(), *artifact_inputs]
        normalized_artifacts = []
        seen_artifacts = set()
        for item in artifact_inputs:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized or normalized in seen_artifacts:
                continue
            normalized_artifacts.append(normalized)
            seen_artifacts.add(normalized)

        if required_artifacts and not normalized_artifacts:
            _fail(
                "validation_error",
                "required artifact missing",
                raise_exc=ValueError("This quest requires at least one artifact reference."),
            )
        if tier != "P0" and not normalized_artifacts:
            _fail(
                "validation_error",
                "tier P1+ requires artifact",
                raise_exc=ValueError("tier P1+ requires at least one artifact reference."),
            )

        try:
            artifact_refs = [self._artifact_ref(item) for item in normalized_artifacts]
        except ValueError as exc:
            lowered = str(exc).lower()
            if "secret-like" in lowered or "pii-like" in lowered or "raw log" in lowered:
                self._emit_event(
                    "risk.flagged",
                    actor="system",
                    source=source,
                    data={"reason": "artifact_blocked", "quest_id": quest_id},
                )
            _fail("validation_error", str(exc), raise_exc=exc)

        proof_artifact_meta = [
            {
                "artifact_type": ref.get("type"),
                "bytes": int(ref.get("size_bytes", 0)),
                "sha256": ref.get("sha256"),
            }
            for ref in artifact_refs
        ]
        self._emit_event(
            "proof.submitted",
            actor=actor,
            source=source,
            data={
                "quest_id": quest_id,
                "proof_tier": tier,
                "artifact_count": len(proof_artifact_meta),
                "artifacts": proof_artifact_meta,
            },
        )

        scoring = q.get("scoring", {})
        base_xp = int(scoring.get("base_xp", 0))
        multiplier = float(scoring.get("proof_multiplier", {}).get(tier, 1.0))
        awarded_xp = int(round(base_xp * multiplier))
        if awarded_xp < 0:
            awarded_xp = 0

        now = datetime.now(tz=UTC)
        now_iso = now.isoformat()
        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
        score_state = self._load_score_state()

        last_quest_time_raw = score_state.get("quest_last_completion", {}).get(quest_id)
        if last_quest_time_raw:
            last_quest_time = self._parse_iso_dt(last_quest_time_raw)
            if last_quest_time and now - last_quest_time < timedelta(hours=24):
                awarded_xp = 0
        cooldown_hours = q.get("cooldown", {}).get("min_hours")
        if isinstance(cooldown_hours, int) and last_quest_time_raw:
            last_quest_time = self._parse_iso_dt(last_quest_time_raw)
            if last_quest_time and now - last_quest_time < timedelta(hours=cooldown_hours):
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
            "proof_summary": f"Artifact metadata recorded for {quest_id}",
            "proof_hash": hashlib.sha256(
                f"{quest_id}|{now_iso}|{json.dumps(artifact_refs, sort_keys=True)}".encode("utf-8")
            ).hexdigest(),
            "attested_by": None,
            "artifacts": artifact_refs,
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
        completion_state["items"] = completions
        _save_json(self.completion_path, completion_state)
        _save_json(self.score_path, score_state)

        self._emit_event(
            "quest.completed",
            actor=actor,
            source=source,
            data={
                "quest_id": quest_id,
                "proof_tier": tier,
                "risk_level": q.get("risk_level"),
                "mode_used": mode_used,
                "xp_awarded": awarded_xp,
                "timebox_estimate_minutes": self._quest_timebox_minutes(quest),
                "observed_duration_seconds": 0,
            },
        )
        self._emit_event(
            "scorecard.updated",
            actor=actor,
            source=source,
            data={
                "quest_id": quest_id,
                "xp_delta": awarded_xp,
                "total_xp": int(score_state.get("total_xp", 0)),
                "daily_streak": int(score_state.get("daily_streak", 0)),
                "weekly_streak": int(score_state.get("weekly_streak", 0)),
            },
        )
        return completion

    def list_proofs(self, quest_id: str | None = None, date_range: str | None = None) -> list[dict[str, Any]]:
        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
        filtered = completions
        if quest_id:
            filtered = [item for item in filtered if item.get("quest_id") == quest_id]
        if date_range:
            parts = [item.strip() for item in date_range.split(",")]
            if len(parts) == 2:
                start = _parse_date(parts[0])
                end = _parse_date(parts[1])
                narrowed: list[dict[str, Any]] = []
                for item in filtered:
                    timestamp = self._parse_iso_dt(item.get("timestamp"))
                    if timestamp is None:
                        continue
                    if start <= timestamp.date() <= end:
                        narrowed.append(item)
                filtered = narrowed
        return filtered

    def get_scorecard(self) -> dict[str, Any]:
        score = self._load_score_state()
        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
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

    def telemetry_status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "path": str(self.telemetry.events_path),
            "event_count": self.telemetry.count_events(),
        }

    def telemetry_purge(self) -> dict[str, Any]:
        removed = self.telemetry.purge()
        return {"path": str(self.telemetry.events_path), "purged": removed}

    def telemetry_export(self, range_value: str, out_path: Path) -> dict[str, Any]:
        return self.telemetry.export_summary(
            range_value=range_value,
            score_state=self._load_score_state(),
            out_path=out_path,
        )

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

    def put_profile(
        self,
        profile_kind: str,
        profile: dict[str, Any],
        *,
        source: str = "cli",
        actor: str | None = None,
    ) -> dict[str, Any]:
        if payload_contains_secrets(profile):
            self._emit_event(
                "risk.flagged",
                actor="system",
                source=source,
                data={"reason": "profile_secret_like_payload", "profile_kind": profile_kind},
            )
            raise ValueError("Profile payload appears to contain secret-like content.")
        paths = self.profile_paths()
        profile["updated_at"] = _now_iso()
        _save_json(paths[profile_kind], profile)
        resolved_actor = actor or ("agent" if profile_kind == "agent" else "human")
        self._emit_event(
            "profile.updated",
            actor=resolved_actor,
            source=source,
            data={"profile_kind": profile_kind},
        )
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
