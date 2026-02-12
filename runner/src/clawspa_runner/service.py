from __future__ import annotations

"""Core runner service for planning, completion, capability gating, and telemetry."""

import hashlib
import json
import os
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .paths import agent_home, ensure_home_dirs
from .quests import QuestRepository
from .security import payload_contains_pii, payload_contains_secrets, payload_requests_raw_logs
from .telemetry import (
    TelemetryLogger,
    diff_aggregated_summaries,
    load_aggregated_summary,
    parse_range,
    render_summary_diff_text,
    sanitize_actor_id,
    summary_sha256,
)


STATE_SCHEMA_VERSION = "0.1"
TIER_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
DATE_RANGE_ABS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}$")
ARTIFACT_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,127}$")
DEFAULT_TELEMETRY_RETENTION_DAYS = 30
DEFAULT_PROOFS_RETENTION_DAYS = 90
DEFAULT_TRACE_ID_PREFIX = "cli"
FEEDBACK_SCHEMA_VERSION = "0.1"
MAX_FEEDBACK_TITLE_CHARS = 120
MAX_FEEDBACK_SUMMARY_CHARS = 280
MAX_FEEDBACK_DETAILS_CHARS = 4000
MAX_FEEDBACK_ITEMS = 100
MAX_FEEDBACK_TAGS = 20
MAX_FEEDBACK_LINK_VALUE_CHARS = 200
MAX_ARTIFACT_REF_CHARS = 128
MAX_ARTIFACT_SUMMARY_CHARS = 4000
VALID_FEEDBACK_SEVERITY = {"info", "low", "medium", "high", "critical"}
VALID_FEEDBACK_COMPONENT = {"proofs", "planner", "api", "mcp", "telemetry", "quests", "docs", "other"}

TRUST_SIGNAL_RULES: dict[str, dict[str, Any]] = {
    "wellness.security_access_control.permissions.delta_inventory.v1": {
        "signal_id": "trust.security.permissions.delta_inventory.fresh",
        "min_tier": "P1",
        "ttl_days": 14,
        "summary": "Recent permission inventory evidence is available.",
    },
    "wellness.security_access_control.capabilities.ttl_audit.v1": {
        "signal_id": "trust.security.capability.ttl_audit.current",
        "min_tier": "P2",
        "ttl_days": 14,
        "summary": "Capability TTL review evidence is current.",
    },
    "wellness.transparency_auditability.telemetry.hash_chain_verify_drill.v1": {
        "signal_id": "trust.transparency.telemetry_chain.verified",
        "min_tier": "P2",
        "ttl_days": 7,
        "summary": "Telemetry hash-chain verification evidence is current.",
    },
    "wellness.continuous_governance_oversight.actor.registry_review.v1": {
        "signal_id": "trust.governance.actor_registry.reviewed",
        "min_tier": "P1",
        "ttl_days": 14,
        "summary": "Actor registry review evidence is current.",
    },
    "wellness.privacy_data_governance.proof.redaction_drill.v1": {
        "signal_id": "trust.privacy.redaction.drill_current",
        "min_tier": "P2",
        "ttl_days": 14,
        "summary": "Recent redaction drill evidence is available.",
    },
}


class ProofSubmissionError(ValueError):
    """Structured proof validation error for stable API responses."""

    def __init__(self, code: str, message: str, *, hint: str | None = None, **context: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        for key, value in self.context.items():
            if value is not None:
                payload[key] = value
        return payload


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _env_days(name: str, fallback: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    if value <= 0:
        return fallback
    return value


def _new_trace_id(prefix: str = DEFAULT_TRACE_ID_PREFIX) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _strip_controls(value: str) -> str:
    return "".join(ch for ch in value if not unicodedata.category(ch).startswith("C"))


def _sanitize_feedback_text(value: str | None, *, max_chars: int, fallback: str = "") -> str:
    text = _strip_controls(value or "").strip()
    if payload_contains_secrets(text) or payload_contains_pii(text):
        return "[redacted]"
    if len(text) > max_chars:
        return f"{text[:max_chars]}...[truncated]"
    if not text:
        return fallback
    return text


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp"
    payload = json.dumps(value, indent=2)
    for attempt in range(5):
        temp_path.write_text(payload, encoding="utf-8")
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            # On Windows, AV/indexers can briefly lock newly-written temp files.
            time.sleep(0.02 * (attempt + 1))


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
    """Stateful local service enforcing Safe Mode defaults and audit-friendly events."""

    repo_root: Path
    home: Path
    quests: QuestRepository
    dirs: dict[str, Path]
    telemetry: TelemetryLogger

    @classmethod
    def create(cls, repo_root: Path) -> "RunnerService":
        """Instantiate a service and initialize local state and startup telemetry."""

        home = agent_home()
        dirs = ensure_home_dirs(home)
        quests = QuestRepository.from_repo_root(repo_root)
        telemetry = TelemetryLogger(events_path=dirs["telemetry"] / "events.jsonl", repo_root=repo_root)
        service = cls(repo_root=repo_root, home=home, quests=quests, dirs=dirs, telemetry=telemetry)
        service._ensure_state_files()
        service.telemetry.log_event(
            "runner.started",
            actor="system",
            actor_id="system:runner",
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
    def trust_signal_path(self) -> Path:
        return self.dirs["state"] / "trust_signals.json"

    @property
    def migration_path(self) -> Path:
        return self.dirs["state"] / "state_meta.json"

    @property
    def feedback_path(self) -> Path:
        return self.dirs["feedback"] / "feedback.jsonl"

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
        if not self.trust_signal_path.exists():
            _save_json(self.trust_signal_path, {"state_schema_version": STATE_SCHEMA_VERSION, "items": []})
        if not self.feedback_path.exists():
            self.feedback_path.write_text("", encoding="utf-8")

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
        if self.trust_signal_path.exists():
            trust_signals = _load_json(self.trust_signal_path, {"items": []})
            if isinstance(trust_signals, dict) and "state_schema_version" not in trust_signals:
                trust_signals["state_schema_version"] = new_version
                _save_json(self.trust_signal_path, trust_signals)
        _save_json(self.migration_path, {"state_schema_version": new_version, "migrated_from": old_version, "updated_at": _now_iso()})

    def validate_content(self) -> list[dict[str, str]]:
        """Run quest-lint against loaded quest packs and return findings."""

        return self.quests.lint()

    def _normalize_actor(self, actor: str) -> str:
        if actor in {"human", "agent", "system"}:
            return actor
        return "system"

    def _normalize_source(self, source: str) -> str:
        if source in {"cli", "api", "mcp"}:
            return source
        return "cli"

    def _normalize_actor_id(self, actor_id: str | None) -> str:
        return sanitize_actor_id(actor_id)

    def _emit_event(
        self,
        event_type: str,
        *,
        actor: str,
        actor_id: str | None,
        source: str,
        data: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        self.telemetry.log_event(
            event_type,
            actor=self._normalize_actor(actor),
            actor_id=self._normalize_actor_id(actor_id),
            source=self._normalize_source(source),
            data=data,
            trace_id=trace_id,
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

    def _load_trust_signal_state(self) -> dict[str, Any]:
        data = _load_json(self.trust_signal_path, {"state_schema_version": STATE_SCHEMA_VERSION, "items": []})
        if not isinstance(data, dict):
            return {"state_schema_version": STATE_SCHEMA_VERSION, "items": []}
        data.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
        if not isinstance(data.get("items"), list):
            data["items"] = []
        return data

    def _active_trust_signals(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(tz=UTC)
        state = self._load_trust_signal_state()
        active: list[dict[str, Any]] = []
        for item in state.get("items", []):
            if not isinstance(item, dict):
                continue
            expires_at = self._parse_iso_dt(item.get("expires_at"))
            if expires_at is None or expires_at <= current:
                continue
            active.append(item)
        active.sort(key=lambda signal: str(signal.get("signal_id")))
        return active

    def _apply_trust_signal_rules(
        self,
        *,
        quest_id: str,
        tier: str,
        timestamp: datetime,
        actor: str,
        actor_id: str | None,
        source: str,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rule = TRUST_SIGNAL_RULES.get(quest_id)
        if rule is None:
            return []
        min_tier = str(rule.get("min_tier", "P3"))
        if TIER_RANK.get(tier, -1) < TIER_RANK.get(min_tier, 99):
            return []

        ttl_days = int(rule.get("ttl_days", 7))
        signal = {
            "signal_id": str(rule["signal_id"]),
            "summary": str(rule["summary"]),
            "quest_id": quest_id,
            "tier": tier,
            "issued_at": timestamp.isoformat(),
            "expires_at": (timestamp + timedelta(days=ttl_days)).isoformat(),
        }
        state = self._load_trust_signal_state()
        items = [item for item in state.get("items", []) if item.get("signal_id") != signal["signal_id"]]
        items.append(signal)
        state["items"] = items
        _save_json(self.trust_signal_path, state)
        self._emit_event(
            "trust_signal.updated",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "signal_id": signal["signal_id"],
                "quest_id": quest_id,
                "tier": tier,
                "expires_at": signal["expires_at"],
            },
        )
        return [signal]

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
        """Return active capability grants and pending ticket inventory."""

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
        """Create a short-lived human confirmation ticket for capability grants."""

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
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Grant capabilities only when a matching unexpired ticket is presented."""

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
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
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
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Revoke capability grants by grant id or capability name."""

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
                actor_id=actor_id,
                source=source,
                trace_id=trace_id,
                data={
                    "revoked_count": changed,
                    "grant_id": grant_id,
                    "capability": capability,
                    "revoked_grants": revoked_grants,
                },
            )
        return {"revoked": changed}

    def sync_packs(self) -> dict[str, Any]:
        """Reload local pack sources and return summary metadata."""

        self.quests = QuestRepository.from_repo_root(self.repo_root)
        findings = self.validate_content()
        error_count = sum(1 for item in findings if item.get("severity") == "ERROR")
        warn_count = sum(1 for item in findings if item.get("severity") == "WARN")
        packs = self.quests.list_packs()
        return {
            "status": "ok" if error_count == 0 else "lint_errors",
            "sources": self.quests.pack_sources(),
            "pack_count": len(packs),
            "error_count": error_count,
            "warn_count": warn_count,
        }

    def list_quests(self) -> dict[str, dict[str, Any]]:
        """Load validated quests, refusing to serve content with lint errors."""

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
        """Search validated quests by optional pillar/tag/risk/mode filters."""

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
        """Return one validated quest by canonical quest id."""

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

    def _risk_footprint_high(self) -> bool:
        for grant in self._active_grants():
            for capability in grant.get("capabilities", []):
                if not isinstance(capability, str):
                    continue
                if capability.startswith("exec:") or capability.startswith("net:"):
                    return True
        return False

    def _completion_dropoff_detected(self, target_date: date) -> bool:
        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
        recent_start = target_date - timedelta(days=2)
        prior_start = target_date - timedelta(days=5)
        prior_end = target_date - timedelta(days=3)

        recent_count = 0
        prior_count = 0
        for item in completions:
            timestamp = self._parse_iso_dt(item.get("timestamp"))
            if timestamp is None:
                continue
            completed_day = timestamp.date()
            if recent_start <= completed_day <= target_date:
                recent_count += 1
            elif prior_start <= completed_day <= prior_end:
                prior_count += 1
        return prior_count >= 3 and recent_count < prior_count

    def _quest_due_for_date(self, quest: dict[str, Any], target_date: date, score_state: dict[str, Any]) -> bool:
        q = quest.get("quest", {})
        quest_id = q.get("id")
        if not isinstance(quest_id, str) or not quest_id:
            return False
        cadence = q.get("cadence", "daily")
        base_hours = {"daily": 18, "weekly": 120, "monthly": 720, "ad-hoc": 24}.get(cadence, 18)
        cooldown_hours = q.get("cooldown", {}).get("min_hours")
        if not isinstance(cooldown_hours, int) or cooldown_hours <= 0:
            cooldown_hours = base_hours
        required_hours = max(base_hours, cooldown_hours)

        last_raw = score_state.get("quest_last_completion", {}).get(quest_id)
        if not isinstance(last_raw, str) or not last_raw:
            return True
        last_dt = self._parse_iso_dt(last_raw)
        if last_dt is None:
            return True
        target_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
        return target_dt - last_dt >= timedelta(hours=required_hours)

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

    def _plan_quest_metadata(self, quest: dict[str, Any]) -> dict[str, Any]:
        q = quest.get("quest", {})
        proof = q.get("proof", {})
        artifacts_decl = proof.get("artifacts", [])
        artifact_declarations: list[dict[str, Any]] = []
        if isinstance(artifacts_decl, list):
            for item in artifacts_decl:
                if not isinstance(item, dict):
                    continue
                artifact_declarations.append(
                    {
                        "id": item.get("id"),
                        "type": item.get("type"),
                        "required": bool(item.get("required", True)),
                        "redaction_policy": item.get("redaction_policy"),
                    }
                )
        capabilities = [cap for cap in q.get("required_capabilities", []) if isinstance(cap, str)]
        pillars = [pillar for pillar in q.get("pillars", []) if isinstance(pillar, str)]
        return {
            "quest_id": q.get("id"),
            "title": q.get("title"),
            "pillars": pillars,
            "risk_level": q.get("risk_level"),
            "mode": q.get("mode"),
            "required_capabilities": capabilities,
            "required_proof_tier": proof.get("tier", "P0"),
            "artifacts": artifact_declarations,
        }

    def _ensure_plan_metadata(self, plan: dict[str, Any]) -> dict[str, Any]:
        quest_metadata = plan.get("quest_metadata")
        if isinstance(quest_metadata, list) and quest_metadata:
            return plan
        quest_ids = plan.get("quest_ids", [])
        if not isinstance(quest_ids, list):
            plan["quest_metadata"] = []
            return plan
        all_quests = self.list_quests()
        metadata_rows: list[dict[str, Any]] = []
        for quest_id in quest_ids:
            if not isinstance(quest_id, str):
                continue
            quest = all_quests.get(quest_id)
            if quest is None:
                continue
            metadata_rows.append(self._plan_quest_metadata(quest))
        plan["quest_metadata"] = metadata_rows
        return plan

    def generate_daily_plan(
        self,
        target_date: date,
        *,
        source: str = "cli",
        actor: str = "human",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a deterministic daily plan and emit `plan.generated` telemetry."""

        score_state = self._load_score_state()
        all_due = []
        for quest in self.list_quests().values():
            allowed, _ = self._can_run_quest(quest)
            if not allowed:
                continue
            if not self._quest_due_for_date(quest, target_date, score_state):
                continue
            all_due.append(quest)
        if not all_due:
            raise ValueError("No due quests available for planning.")

        key = target_date.isoformat()
        dropoff = self._completion_dropoff_detected(target_date)
        risk_high = self._risk_footprint_high()
        cadence_priority = {"monthly": 0, "weekly": 1, "daily": 2, "ad-hoc": 3}
        ranked = sorted(
            all_due,
            key=lambda q: (
                cadence_priority.get(q.get("quest", {}).get("cadence", "daily"), 9),
                hashlib.sha256(f"{key}:{actor_id}:{q['quest']['id']}".encode("utf-8")).hexdigest(),
            ),
        )
        if dropoff:
            easier = [q for q in ranked if int(q.get("quest", {}).get("difficulty", 1)) <= 2]
            if easier:
                ranked = easier

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

        if risk_high:
            for quest in ranked:
                q = quest.get("quest", {})
                if quest in selected:
                    continue
                if self._bucket(quest) != "security":
                    continue
                if q.get("mode") != "safe":
                    continue
                selected.append(quest)
                break

        if len(selected) < 5:
            bonus = self._choose_bonus(ranked, selected, target_date)
            if bonus is not None and bonus not in selected:
                selected.append(bonus)

        plan = {
            "date": key,
            "generated_at": _now_iso(),
            "quest_ids": [quest["quest"]["id"] for quest in selected[:5]],
            "quests": selected[:5],
            "quest_metadata": [self._plan_quest_metadata(quest) for quest in selected[:5]],
        }
        _save_json(self.dirs["plans"] / f"daily-{key}.json", plan)
        self._emit_event(
            "plan.generated",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "date": key,
                "quest_ids": plan["quest_ids"],
                "quest_count": len(plan["quest_ids"]),
                "dropoff_mode": dropoff,
                "risk_footprint_high": risk_high,
                "cadences": sorted(
                    {
                        cadence
                        for quest in selected[:5]
                        for cadence in [quest.get("quest", {}).get("cadence")]
                        if isinstance(cadence, str)
                    }
                ),
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

    def get_daily_plan(
        self,
        target_date: date,
        *,
        source: str = "cli",
        actor: str = "human",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Return cached daily plan or generate one deterministically for the date."""

        plan_file = self.dirs["plans"] / f"daily-{target_date.isoformat()}.json"
        if plan_file.exists():
            cached = _load_json(plan_file, {})
            if isinstance(cached, dict):
                had_metadata = isinstance(cached.get("quest_metadata"), list) and bool(cached.get("quest_metadata"))
                enriched = self._ensure_plan_metadata(cached)
                if not had_metadata:
                    _save_json(plan_file, enriched)
                return enriched
            return {}
        return self.generate_daily_plan(
            target_date,
            source=source,
            actor=actor,
            actor_id=actor_id,
            trace_id=trace_id,
        )

    def generate_weekly_plan(
        self,
        target_date: date,
        *,
        source: str = "cli",
        actor: str = "human",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a deterministic weekly plan from due weekly/monthly quests."""

        score_state = self._load_score_state()
        candidates: list[dict[str, Any]] = []
        for quest in self.list_quests().values():
            cadence = quest.get("quest", {}).get("cadence")
            if cadence not in {"weekly", "monthly"}:
                continue
            allowed, _ = self._can_run_quest(quest)
            if not allowed:
                continue
            if not self._quest_due_for_date(quest, target_date, score_state):
                continue
            candidates.append(quest)
        if not candidates:
            raise ValueError("No due weekly/monthly quests available for planning.")

        key = f"{target_date.isoformat()}:{_iso_week(target_date)}"
        ranked = sorted(
            candidates,
            key=lambda q: hashlib.sha256(f"{key}:{actor_id}:{q['quest']['id']}".encode("utf-8")).hexdigest(),
        )
        selected: list[dict[str, Any]] = []
        security = next((q for q in ranked if self._bucket(q) == "security"), None)
        if security is not None:
            selected.append(security)
        governance = next((q for q in ranked if q not in selected and "Continuous Governance & Oversight" in q.get("quest", {}).get("pillars", [])), None)
        if governance is not None:
            selected.append(governance)
        target_count = 3 if self._risk_footprint_high() else 2
        for quest in ranked:
            if len(selected) >= target_count:
                break
            if quest not in selected:
                selected.append(quest)

        week_key = _iso_week(target_date)
        plan = {
            "week": week_key,
            "anchor_date": target_date.isoformat(),
            "generated_at": _now_iso(),
            "quest_ids": [quest["quest"]["id"] for quest in selected[:3]],
            "quests": selected[:3],
            "quest_metadata": [self._plan_quest_metadata(quest) for quest in selected[:3]],
        }
        _save_json(self.dirs["plans"] / f"weekly-{week_key}.json", plan)
        self._emit_event(
            "plan.generated",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "plan_type": "weekly",
                "week": week_key,
                "quest_ids": plan["quest_ids"],
                "quest_count": len(plan["quest_ids"]),
                "pillars": sorted(
                    {
                        pillar
                        for quest in selected[:3]
                        for pillar in quest.get("quest", {}).get("pillars", [])
                        if isinstance(pillar, str)
                    }
                ),
            },
        )
        return plan

    def get_weekly_plan(
        self,
        target_date: date,
        *,
        source: str = "cli",
        actor: str = "human",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Return cached weekly plan or generate one deterministically for the week."""

        week_key = _iso_week(target_date)
        plan_file = self.dirs["plans"] / f"weekly-{week_key}.json"
        if plan_file.exists():
            cached = _load_json(plan_file, {})
            if isinstance(cached, dict):
                had_metadata = isinstance(cached.get("quest_metadata"), list) and bool(cached.get("quest_metadata"))
                enriched = self._ensure_plan_metadata(cached)
                if not had_metadata:
                    _save_json(plan_file, enriched)
                return enriched
            return {}
        return self.generate_weekly_plan(
            target_date,
            source=source,
            actor=actor,
            actor_id=actor_id,
            trace_id=trace_id,
        )

    def _validate_artifact_text(self, text: str, *, source: str) -> None:
        if payload_contains_secrets(text):
            raise ValueError(f"{source} appears to contain secret-like content.")
        if payload_contains_pii(text):
            raise ValueError(f"{source} appears to contain PII-like content.")
        if payload_requests_raw_logs(text):
            raise ValueError(f"{source} appears to contain raw log content.")

    def _normalize_artifact_ref(self, raw_ref: str) -> str:
        ref = raw_ref.strip()
        if not ref:
            raise ProofSubmissionError(
                "PROOF_REF_INVALID",
                "artifact ref must be short; put long content in summary",
                hint="Use artifacts[].summary for long text; keep ref like 'control-owner-attestation'.",
            )
        if "/" in ref or "\\" in ref:
            raise ProofSubmissionError(
                "PROOF_REF_INVALID",
                "artifact ref must be short; put long content in summary",
                hint="Use artifacts[].summary for long text; keep ref like 'control-owner-attestation'.",
            )
        if len(ref) > MAX_ARTIFACT_REF_CHARS or not ARTIFACT_REF_PATTERN.match(ref):
            raise ProofSubmissionError(
                "PROOF_REF_INVALID",
                "artifact ref must be short; put long content in summary",
                hint="Use artifacts[].summary for long text; keep ref like 'control-owner-attestation'.",
            )
        self._validate_artifact_text(ref, source="Artifact ref")
        return ref

    def _artifact_ref(self, artifact: dict[str, Any]) -> dict[str, Any]:
        ref = self._normalize_artifact_ref(str(artifact.get("ref", "")))
        summary_raw = artifact.get("summary")
        summary = ""
        if summary_raw is not None:
            if not isinstance(summary_raw, str):
                raise ProofSubmissionError(
                    "PROOF_SUMMARY_INVALID",
                    "artifact summary must be a string when provided",
                )
            summary = summary_raw.strip()
            if len(summary) > MAX_ARTIFACT_SUMMARY_CHARS:
                raise ProofSubmissionError(
                    "PROOF_SUMMARY_TOO_LONG",
                    f"artifact summary exceeds {MAX_ARTIFACT_SUMMARY_CHARS} characters",
                )
            if summary:
                self._validate_artifact_text(summary, source="Artifact summary")
        ref_bytes = ref.encode("utf-8")
        summary_bytes = summary.encode("utf-8")
        return {
            "type": "ref",
            "ref": ref,
            "sha256": hashlib.sha256(ref_bytes).hexdigest(),
            "size_bytes": len(ref_bytes),
            "summary_sha256": hashlib.sha256(summary_bytes).hexdigest() if summary else None,
            "summary_chars": len(summary),
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
        artifacts: list[dict[str, Any] | str] | None = None,
        source: str = "cli",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Record quest completion with proof validation, scoring, and telemetry."""

        actor = self._normalize_actor(actor_mode)
        source = self._normalize_source(source)
        resolved_pillars: list[str] = []
        resolved_pack_id: str | None = None

        def _reject(
            reason: str,
            message: str,
            *,
            raise_exc: Exception,
            code: str = "PROOF_REJECTED",
            hint: str | None = None,
            **context: Any,
        ) -> None:
            self._emit_event(
                "quest.failed",
                actor=actor,
                actor_id=actor_id,
                source=source,
                trace_id=trace_id,
                data={
                    "quest_id": quest_id,
                    "pack_id": resolved_pack_id,
                    "pillars": resolved_pillars,
                    "reason": reason,
                    "detail_hash": hashlib.sha256(message.encode("utf-8")).hexdigest(),
                },
            )
            reject_payload = {
                "quest_id": quest_id,
                "pack_id": resolved_pack_id,
                "pillars": resolved_pillars,
                "reason": reason,
                "code": code,
            }
            if hint:
                reject_payload["hint"] = hint
            for key, value in context.items():
                if value is not None:
                    reject_payload[key] = value
            self._emit_event(
                "proof.rejected",
                actor=actor,
                actor_id=actor_id,
                source=source,
                trace_id=trace_id,
                data=reject_payload,
            )
            raise raise_exc

        if tier not in TIER_RANK:
            error = ProofSubmissionError("PROOF_TIER_INVALID", "tier must be one of P0|P1|P2|P3")
            _reject("validation_error", error.message, raise_exc=error, code=error.code)

        if payload_contains_secrets({"artifact": artifact, "artifacts": artifacts or []}):
            self._emit_event(
                "risk.flagged",
                actor="system",
                actor_id=actor_id,
                source=source,
                trace_id=trace_id,
                data={"reason": "artifact_secret_like", "quest_id": quest_id},
            )
            error = ProofSubmissionError("PROOF_ARTIFACT_UNSAFE", "Artifact payload appears to contain secret-like data.")
            _reject(
                "validation_error",
                error.message,
                raise_exc=error,
                code=error.code,
            )

        try:
            quest = self.get_quest(quest_id)
        except KeyError as exc:
            _reject("not_found", "unknown quest_id", raise_exc=exc, code="PROOF_QUEST_NOT_FOUND")

        allowed, mode_used = self._can_run_quest(quest)
        if not allowed:
            _reject(
                "capability_missing" if "missing capability grants" in mode_used else "policy_blocked",
                mode_used,
                raise_exc=PermissionError(f"Quest blocked in Safe Mode: {mode_used}"),
                code="PROOF_BLOCKED_BY_POLICY",
            )

        q = quest["quest"]
        resolved_pillars = [str(item) for item in q.get("pillars", []) if isinstance(item, str) and item]
        resolved_pack_id = quest.get("_pack")
        expected_tier = q.get("proof", {}).get("tier")
        if expected_tier in TIER_RANK and TIER_RANK[tier] < TIER_RANK[expected_tier]:
            error = ProofSubmissionError(
                "PROOF_TIER_TOO_LOW",
                f"Quest requires {expected_tier} minimum",
                required_tier=expected_tier,
                provided_tier=tier,
            )
            _reject(
                "validation_error",
                error.message,
                raise_exc=error,
                code=error.code,
                required_tier=expected_tier,
                provided_tier=tier,
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
                    _reject(
                        "validation_error",
                        "missing redaction policy",
                        raise_exc=ValueError("Quest proof artifacts for P2/P3 must include redaction_policy."),
                        code="PROOF_REDACTION_POLICY_MISSING",
                    )

        artifact_inputs = artifacts or []
        if artifact and artifact.strip():
            artifact_inputs = [{"ref": artifact.strip()}] + artifact_inputs
        normalized_artifacts: list[dict[str, Any]] = []
        seen_refs = set()
        for item in artifact_inputs:
            ref_value = ""
            summary_value: str | None = None
            if isinstance(item, dict):
                ref_raw = item.get("ref")
                if isinstance(ref_raw, str):
                    ref_value = ref_raw
                summary_raw = item.get("summary")
                if summary_raw is None or isinstance(summary_raw, str):
                    summary_value = summary_raw
            elif isinstance(item, str):
                ref_value = item
            ref_value = ref_value.strip()
            if not ref_value or ref_value in seen_refs:
                continue
            normalized_artifacts.append({"ref": ref_value, "summary": summary_value})
            seen_refs.add(ref_value)

        if required_artifacts and not normalized_artifacts:
            _reject(
                "validation_error",
                "required artifact missing",
                raise_exc=ProofSubmissionError("PROOF_ARTIFACT_REQUIRED", "This quest requires at least one artifact reference."),
                code="PROOF_ARTIFACT_REQUIRED",
            )
        if tier != "P0" and not normalized_artifacts:
            _reject(
                "validation_error",
                "tier P1+ requires artifact",
                raise_exc=ProofSubmissionError("PROOF_ARTIFACT_REQUIRED", "tier P1+ requires at least one artifact reference."),
                code="PROOF_ARTIFACT_REQUIRED",
            )

        try:
            artifact_refs = [self._artifact_ref(item) for item in normalized_artifacts]
        except ProofSubmissionError as exc:
            lowered = exc.message.lower()
            if "secret-like" in lowered or "pii-like" in lowered or "raw log" in lowered:
                self._emit_event(
                    "risk.flagged",
                    actor="system",
                    actor_id=actor_id,
                    source=source,
                    trace_id=trace_id,
                    data={"reason": "artifact_blocked", "quest_id": quest_id},
                )
            _reject(
                "validation_error",
                exc.message,
                raise_exc=exc,
                code=exc.code,
                hint=exc.hint,
                **exc.context,
            )
        except ValueError as exc:
            lowered = str(exc).lower()
            if "secret-like" in lowered or "pii-like" in lowered or "raw log" in lowered:
                self._emit_event(
                    "risk.flagged",
                    actor="system",
                    actor_id=actor_id,
                    source=source,
                    trace_id=trace_id,
                    data={"reason": "artifact_blocked", "quest_id": quest_id},
                )
            error = ProofSubmissionError("PROOF_ARTIFACT_INVALID", str(exc))
            _reject("validation_error", error.message, raise_exc=error, code=error.code)

        pillars = resolved_pillars
        pack_id = resolved_pack_id
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
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "quest_id": quest_id,
                "pack_id": pack_id,
                "pillars": pillars,
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
        emitted_signals = self._apply_trust_signal_rules(
            quest_id=quest_id,
            tier=tier,
            timestamp=now,
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
        )

        self._emit_event(
            "quest.completed",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "quest_id": quest_id,
                "pack_id": pack_id,
                "pillars": pillars,
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
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "quest_id": quest_id,
                "xp_delta": awarded_xp,
                "total_xp": int(score_state.get("total_xp", 0)),
                "daily_streak": int(score_state.get("daily_streak", 0)),
                "weekly_streak": int(score_state.get("weekly_streak", 0)),
                "trust_signal_count": len(self._active_trust_signals(now)),
            },
        )
        completion["trust_signals_emitted"] = emitted_signals
        return completion

    def list_proofs(self, quest_id: str | None = None, date_range: str | None = None) -> list[dict[str, Any]]:
        """List completion proofs, optionally filtered by quest id and date window."""

        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
        filtered = completions
        if quest_id:
            filtered = [item for item in filtered if item.get("quest_id") == quest_id]
        if date_range:
            range_text = date_range.strip()
            narrowed: list[dict[str, Any]] = []
            if DATE_RANGE_ABS_PATTERN.match(range_text):
                start_raw, end_raw = range_text.split("..", 1)
                start = _parse_date(start_raw)
                end = _parse_date(end_raw)
                if start > end:
                    raise ValueError("date_range start must be <= end.")
                for item in filtered:
                    timestamp = self._parse_iso_dt(item.get("timestamp"))
                    if timestamp is None:
                        continue
                    if start <= timestamp.date() <= end:
                        narrowed.append(item)
                filtered = narrowed
            else:
                window = parse_range(range_text)
                now = datetime.now(tz=UTC)
                start_dt = now - window
                for item in filtered:
                    timestamp = self._parse_iso_dt(item.get("timestamp"))
                    if timestamp is None:
                        continue
                    if timestamp >= start_dt:
                        narrowed.append(item)
                filtered = narrowed
        return filtered

    def _append_feedback_row(self, payload: dict[str, Any]) -> None:
        self.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        with self.feedback_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            handle.write("\n")

    def _iter_feedback_rows(self) -> list[dict[str, Any]]:
        if not self.feedback_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.feedback_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                node = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(node, dict):
                rows.append(node)
        return rows

    def add_feedback(
        self,
        *,
        severity: str,
        component: str,
        title: str,
        summary: str = "",
        details: str | None = None,
        links: dict[str, str] | None = None,
        tags: list[str] | None = None,
        source: str = "cli",
        actor: str = "human",
        actor_id: str = "unknown",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist one sanitized feedback item and emit metadata-only telemetry."""

        normalized_severity = severity.strip().lower()
        normalized_component = component.strip().lower()
        if normalized_severity not in VALID_FEEDBACK_SEVERITY:
            raise ValueError(f"severity must be one of {sorted(VALID_FEEDBACK_SEVERITY)}.")
        if normalized_component not in VALID_FEEDBACK_COMPONENT:
            raise ValueError(f"component must be one of {sorted(VALID_FEEDBACK_COMPONENT)}.")

        sanitized_title = _sanitize_feedback_text(title, max_chars=MAX_FEEDBACK_TITLE_CHARS)
        if not sanitized_title:
            raise ValueError("title is required.")
        sanitized_summary = _sanitize_feedback_text(summary, max_chars=MAX_FEEDBACK_SUMMARY_CHARS)
        sanitized_details = _sanitize_feedback_text(details, max_chars=MAX_FEEDBACK_DETAILS_CHARS) if details else None

        normalized_links: dict[str, str] = {}
        allowed_links = {"quest_id", "proof_id", "endpoint", "commit", "pr"}
        for key, value in (links or {}).items():
            if key not in allowed_links or not isinstance(value, str):
                continue
            sanitized_value = _sanitize_feedback_text(value, max_chars=MAX_FEEDBACK_LINK_VALUE_CHARS)
            if sanitized_value:
                normalized_links[key] = sanitized_value

        normalized_tags: list[str] = []
        seen_tags = set()
        for tag in tags or []:
            if not isinstance(tag, str):
                continue
            sanitized_tag = _sanitize_feedback_text(tag, max_chars=40)
            if not sanitized_tag or sanitized_tag in seen_tags:
                continue
            normalized_tags.append(sanitized_tag)
            seen_tags.add(sanitized_tag)
            if len(normalized_tags) >= MAX_FEEDBACK_TAGS:
                break

        entry = {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "feedback_id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "actor": {"kind": self._normalize_actor(actor), "id": self._normalize_actor_id(actor_id)},
            "source": self._normalize_source(source),
            "trace_id": sanitize_actor_id(trace_id) if trace_id else None,
            "severity": normalized_severity,
            "component": normalized_component,
            "title": sanitized_title,
            "summary": sanitized_summary,
            "details": sanitized_details,
            "links": normalized_links,
            "tags": normalized_tags,
        }
        self._append_feedback_row(entry)
        self._emit_event(
            "feedback.submitted",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "feedback_id": entry["feedback_id"],
                "severity": normalized_severity,
                "component": normalized_component,
                "tag_count": len(normalized_tags),
            },
        )
        return entry

    def list_feedback(
        self,
        *,
        range_value: str = "7d",
        actor_id: str | None = None,
        limit: int = MAX_FEEDBACK_ITEMS,
    ) -> list[dict[str, Any]]:
        """List feedback rows filtered by time window and optional actor id."""

        window = parse_range(range_value)
        cutoff = datetime.now(tz=UTC) - window
        actor_filter = sanitize_actor_id(actor_id) if actor_id else None
        items: list[dict[str, Any]] = []
        for row in self._iter_feedback_rows():
            parsed_ts = self._parse_iso_dt(row.get("ts"))
            if parsed_ts is None or parsed_ts < cutoff:
                continue
            row_actor = row.get("actor", {})
            row_actor_id = sanitize_actor_id(row_actor.get("id")) if isinstance(row_actor, dict) else "unknown"
            if actor_filter is not None and row_actor_id != actor_filter:
                continue
            items.append(row)
        items.sort(key=lambda item: str(item.get("ts", "")), reverse=True)
        if limit <= 0:
            return []
        return items[:limit]

    def feedback_summary(self, *, range_value: str = "30d", actor_id: str | None = None) -> dict[str, Any]:
        """Return aggregate feedback counts by severity/component plus top tags."""

        items = self.list_feedback(range_value=range_value, actor_id=actor_id, limit=10_000)
        severity_counts: dict[str, int] = {}
        component_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}

        for item in items:
            severity = item.get("severity")
            component = item.get("component")
            if isinstance(severity, str):
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            if isinstance(component, str):
                component_counts[component] = component_counts.get(component, 0) + 1
            tags = item.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if not isinstance(tag, str):
                        continue
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]
        return {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "range": range_value,
            "actor_id_filter": sanitize_actor_id(actor_id) if actor_id else None,
            "feedback_count": len(items),
            "feedback_by_severity": dict(sorted(severity_counts.items())),
            "feedback_by_component": dict(sorted(component_counts.items())),
            "top_tags": top_tags,
        }

    def get_scorecard(self) -> dict[str, Any]:
        """Return current XP/streak summary plus recent completion metadata."""

        score = self._load_score_state()
        completion_state = self._load_completions_state()
        completions = completion_state.get("items", [])
        recent = sorted(completions, key=lambda item: item.get("timestamp", ""), reverse=True)[:10]
        trust_signals = self._active_trust_signals()
        return {
            "generated_at": _now_iso(),
            "total_xp": score.get("total_xp", 0),
            "daily_streak": score.get("daily_streak", 0),
            "weekly_streak": score.get("weekly_streak", 0),
            "recent_completions": recent,
            "trust_signals": trust_signals,
            "badges": score.get("badge_ids", []),
        }

    def export_scorecard(self, out_path: Path) -> dict[str, Any]:
        """Write a redacted scorecard export suitable for local sharing."""

        card = self.get_scorecard()
        export = dict(card)
        for entry in export.get("recent_completions", []):
            entry.pop("proof_id", None)
        _save_json(out_path, export)
        return export

    def telemetry_status(self) -> dict[str, Any]:
        """Report local telemetry path and current event count."""

        return {
            "enabled": True,
            "path": str(self.telemetry.events_path),
            "event_count": self.telemetry.count_events(),
        }

    def telemetry_verify(self) -> dict[str, Any]:
        """Verify local telemetry hash-chain integrity."""

        return self.telemetry.verify_chain()

    def telemetry_retention_days(self) -> int:
        return _env_days("CLAWSPA_TELEMETRY_RETENTION_DAYS", DEFAULT_TELEMETRY_RETENTION_DAYS)

    def proofs_retention_days(self) -> int:
        return _env_days("CLAWSPA_PROOFS_RETENTION_DAYS", DEFAULT_PROOFS_RETENTION_DAYS)

    def telemetry_purge(
        self,
        *,
        older_than: str | None = None,
        source: str = "cli",
        actor: str = "system",
        actor_id: str = "system:retention",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Purge telemetry older than a time window while preserving chain validity."""

        effective_window = older_than or f"{self.telemetry_retention_days()}d"
        result = self.telemetry.purge_older_than(parse_range(effective_window))
        self._emit_event(
            "telemetry.purged",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "target": "telemetry",
                "window": effective_window,
                "purged_count": int(result.get("purged_count", 0)),
                "kept_count": int(result.get("kept_count", 0)),
                "archive_path": result.get("archive_path"),
                "archive_sha256": result.get("archive_sha256"),
            },
        )
        return result

    def proofs_purge(
        self,
        *,
        older_than: str | None = None,
        source: str = "cli",
        actor: str = "system",
        actor_id: str = "system:retention",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Purge proof files/completion records older than a configured window."""

        effective_window = older_than or f"{self.proofs_retention_days()}d"
        window = parse_range(effective_window)
        cutoff = datetime.now(tz=UTC) - window
        removed_files = 0
        for proof_file in self.dirs["proofs"].glob("*.json"):
            try:
                payload = _load_json(proof_file, {})
            except json.JSONDecodeError:
                continue
            timestamp = self._parse_iso_dt(payload.get("timestamp")) if isinstance(payload, dict) else None
            if timestamp is not None and timestamp < cutoff:
                proof_file.unlink(missing_ok=True)
                removed_files += 1

        completion_state = self._load_completions_state()
        original_items = completion_state.get("items", [])
        kept_items: list[dict[str, Any]] = []
        removed_items = 0
        for item in original_items:
            timestamp = self._parse_iso_dt(item.get("timestamp")) if isinstance(item, dict) else None
            if timestamp is not None and timestamp < cutoff:
                removed_items += 1
                continue
            kept_items.append(item)
        completion_state["items"] = kept_items
        _save_json(self.completion_path, completion_state)

        result = {
            "path": str(self.dirs["proofs"]),
            "purged_files": removed_files,
            "purged_completions": removed_items,
            "kept_completions": len(kept_items),
            "window": effective_window,
        }
        self._emit_event(
            "telemetry.purged",
            actor=actor,
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={
                "target": "proofs",
                "window": effective_window,
                "purged_files": removed_files,
                "purged_completions": removed_items,
            },
        )
        return result

    def telemetry_export(self, range_value: str, out_path: Path, actor_id: str | None = None) -> dict[str, Any]:
        """Export aggregated telemetry for the requested window and optional actor id."""

        return self.telemetry.export_summary(
            range_value=range_value,
            score_state=self._load_score_state(),
            out_path=out_path,
            actor_id=actor_id,
        )

    def telemetry_snapshot(
        self,
        range_value: str,
        *,
        actor_id: str | None = None,
        out_path: Path | None = None,
    ) -> dict[str, Any]:
        """Write a baseline snapshot from aggregated telemetry and return its checksum."""

        if out_path is None:
            baselines_dir = self.home / "baselines"
            baselines_dir.mkdir(parents=True, exist_ok=True)
            actor_slug = sanitize_actor_id(actor_id).replace(":", "_") if actor_id is not None else "all"
            stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            out_path = baselines_dir / f"telemetry-baseline-{actor_slug}-{range_value}-{stamp}.json"

        summary = self.telemetry.export_summary(
            range_value=range_value,
            score_state=self._load_score_state(),
            out_path=out_path,
            actor_id=actor_id,
        )
        return {
            "path": str(out_path),
            "sha256": summary_sha256(summary),
            "summary": summary,
        }

    def telemetry_diff(
        self,
        baseline_a: Path,
        baseline_b: Path,
        *,
        out_path: Path | None = None,
    ) -> dict[str, Any]:
        """Diff two aggregated telemetry summaries and optionally persist the JSON diff."""

        summary_a = load_aggregated_summary(baseline_a)
        summary_b = load_aggregated_summary(baseline_b)
        diff_payload = diff_aggregated_summaries(summary_a, summary_b)
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            _save_json(out_path, diff_payload)
        return {"diff": diff_payload, "text": render_summary_diff_text(diff_payload)}

    def profile_paths(self) -> dict[str, Path]:
        """Return canonical paths for persisted profile documents."""

        return {
            "human": self.dirs["profiles"] / "human_profile.json",
            "agent": self.dirs["profiles"] / "agent_profile.json",
            "alignment_snapshot": self.dirs["profiles"] / "alignment_snapshot.json",
        }

    def init_profiles(self) -> dict[str, str]:
        """Initialize default human/agent profile files when absent."""

        paths = self.profile_paths()
        if not paths["human"].exists():
            _save_json(paths["human"], _default_human_profile())
        if not paths["agent"].exists():
            _save_json(paths["agent"], _default_agent_profile())
        return {name: str(path) for name, path in paths.items()}

    def get_profile(self, profile_kind: str) -> dict[str, Any]:
        """Load one profile document, creating defaults on first access."""

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
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist profile updates after secret-like payload screening."""

        if payload_contains_secrets(profile):
            self._emit_event(
                "risk.flagged",
                actor="system",
                actor_id=actor_id,
                source=source,
                trace_id=trace_id,
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
            actor_id=actor_id,
            source=source,
            trace_id=trace_id,
            data={"profile_kind": profile_kind},
        )
        return profile

    def generate_alignment_snapshot(self) -> dict[str, Any]:
        """Derive a lightweight alignment snapshot from human and agent profiles."""

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
