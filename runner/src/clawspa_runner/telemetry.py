from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from .security import payload_contains_pii, payload_contains_secrets


SCHEMA_VERSION = "0.1"
VALID_EVENT_TYPES = {
    "runner.started",
    "plan.generated",
    "proof.submitted",
    "quest.completed",
    "quest.failed",
    "scorecard.updated",
    "profile.updated",
    "capability.granted",
    "capability.revoked",
    "risk.flagged",
}
VALID_ACTORS = {"human", "agent", "system"}
VALID_SOURCES = {"cli", "api", "mcp"}
MAX_STRING_LENGTH = 200
RANGE_PATTERN = re.compile(r"^(\d+)([dh])$")


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _utc_now_rfc3339() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class BuildInfo:
    runner_version: str
    git_sha: str | None
    python_version: str
    platform: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "runner_version": self.runner_version,
            "git_sha": self.git_sha,
            "python_version": self.python_version,
            "platform": self.platform,
        }


@dataclass(frozen=True)
class SanitizeStats:
    redacted_fields: int = 0
    truncated_fields: int = 0


def _combine_stats(a: SanitizeStats, b: SanitizeStats) -> SanitizeStats:
    return SanitizeStats(
        redacted_fields=a.redacted_fields + b.redacted_fields,
        truncated_fields=a.truncated_fields + b.truncated_fields,
    )


def _sanitize_scalar(value: Any) -> tuple[Any, SanitizeStats]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, SanitizeStats()
    if isinstance(value, str):
        if payload_contains_secrets(value) or payload_contains_pii(value):
            return "[redacted]", SanitizeStats(redacted_fields=1)
        if len(value) > MAX_STRING_LENGTH:
            return f"{value[:MAX_STRING_LENGTH]}...[truncated]", SanitizeStats(truncated_fields=1)
        return value, SanitizeStats()

    # Non-JSON scalar-like values are coerced to safe strings.
    as_text = str(value)
    if payload_contains_secrets(as_text) or payload_contains_pii(as_text):
        return "[redacted]", SanitizeStats(redacted_fields=1)
    if len(as_text) > MAX_STRING_LENGTH:
        return f"{as_text[:MAX_STRING_LENGTH]}...[truncated]", SanitizeStats(truncated_fields=1)
    return as_text, SanitizeStats()


def sanitize_event_data(data: Any) -> tuple[Any, SanitizeStats]:
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        stats = SanitizeStats()
        for key, value in data.items():
            key_text, key_stats = _sanitize_scalar(key)
            value_sanitized, value_stats = sanitize_event_data(value)
            sanitized[str(key_text)] = value_sanitized
            stats = _combine_stats(stats, key_stats)
            stats = _combine_stats(stats, value_stats)
        return sanitized, stats
    if isinstance(data, list):
        sanitized_items: list[Any] = []
        stats = SanitizeStats()
        for item in data:
            item_sanitized, item_stats = sanitize_event_data(item)
            sanitized_items.append(item_sanitized)
            stats = _combine_stats(stats, item_stats)
        return sanitized_items, stats
    return _sanitize_scalar(data)


def parse_range(range_value: str) -> timedelta:
    match = RANGE_PATTERN.match(range_value.strip().lower())
    if not match:
        raise ValueError("range must be like 7d or 24h")
    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise ValueError("range amount must be > 0")
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(hours=amount)


def detect_git_sha(repo_root: Path) -> str | None:
    try:
        output = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = output.stdout.strip()
    if output.returncode != 0 or not value:
        return None
    return value


def detect_runner_version() -> str:
    try:
        return package_version("clawspa")
    except PackageNotFoundError:
        return "0.1.0"


class TelemetryLogger:
    def __init__(self, events_path: Path, repo_root: Path) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.build = BuildInfo(
            runner_version=detect_runner_version(),
            git_sha=detect_git_sha(repo_root),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
        )

    def _normalize_actor(self, actor: str) -> str:
        if actor in VALID_ACTORS:
            return actor
        return "system"

    def _normalize_source(self, source: str) -> str:
        if source in VALID_SOURCES:
            return source
        return "cli"

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_safe_json(payload))
            handle.write("\n")

    def _base_event(self, *, event_type: str, actor: str, source: str, data: dict[str, Any]) -> dict[str, Any]:
        if event_type not in VALID_EVENT_TYPES:
            event_type = "risk.flagged"
            data = {
                "reason": "invalid_event_type",
                "invalid_event_type_hash": hashlib_sha256_hex(event_type),
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(uuid.uuid4()),
            "ts": _utc_now_rfc3339(),
            "event_type": event_type,
            "actor": self._normalize_actor(actor),
            "source": self._normalize_source(source),
            "build": self.build.to_dict(),
            "data": data,
        }

    def log_event(
        self,
        event_type: str,
        *,
        actor: str,
        source: str,
        data: dict[str, Any],
        _emit_sanitize_flag: bool = True,
    ) -> None:
        try:
            sanitized_data, stats = sanitize_event_data(data)
            event_payload = self._base_event(
                event_type=event_type,
                actor=actor,
                source=source,
                data=sanitized_data if isinstance(sanitized_data, dict) else {"value": sanitized_data},
            )
            self._append_jsonl(event_payload)
            if _emit_sanitize_flag and (stats.redacted_fields or stats.truncated_fields):
                self.log_event(
                    "risk.flagged",
                    actor="system",
                    source=source,
                    data={
                        "reason": "telemetry_sanitized",
                        "trigger_event_type": event_type,
                        "fields_redacted_count": stats.redacted_fields,
                        "fields_truncated_count": stats.truncated_fields,
                    },
                    _emit_sanitize_flag=False,
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[telemetry] failed to append event: {exc}", file=sys.stderr)

    def iter_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)
        return events

    def count_events(self) -> int:
        if not self.events_path.exists():
            return 0
        count = 0
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count

    def purge(self) -> bool:
        if not self.events_path.exists():
            return False
        self.events_path.unlink()
        return True

    def export_summary(
        self,
        *,
        range_value: str,
        score_state: dict[str, Any],
        out_path: Path | None = None,
    ) -> dict[str, Any]:
        window = parse_range(range_value)
        end = _utc_now()
        start = end - window

        events = self.iter_events()
        in_window: list[dict[str, Any]] = []
        for event in events:
            parsed_ts = _parse_ts(event.get("ts"))
            if parsed_ts is None:
                continue
            if start <= parsed_ts <= end:
                in_window.append(event)

        completions = [evt for evt in in_window if evt.get("event_type") == "quest.completed"]
        failures = [evt for evt in in_window if evt.get("event_type") == "quest.failed"]
        plans = [evt for evt in in_window if evt.get("event_type") == "plan.generated"]
        flags = [evt for evt in in_window if evt.get("event_type") == "risk.flagged"]

        completions_by_actor = Counter(evt.get("actor", "system") for evt in completions)
        completions_by_proof_tier = Counter(
            str(evt.get("data", {}).get("proof_tier", "unknown")) for evt in completions
        )
        failures_by_reason = Counter(str(evt.get("data", {}).get("reason", "unknown")) for evt in failures)
        quest_counts = Counter(str(evt.get("data", {}).get("quest_id", "")) for evt in completions)
        quest_counts.pop("", None)

        plans_generated = len(plans)
        quest_count_sum = sum(int(evt.get("data", {}).get("quest_count", 0)) for evt in plans)
        attempts = len(completions) + len(failures)
        timebox_estimates_sum = sum(
            int(evt.get("data", {}).get("timebox_estimate_minutes", 0)) for evt in completions
        )
        observed_duration_sum = sum(
            int(evt.get("data", {}).get("observed_duration_seconds", 0)) for evt in completions
        )

        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now_rfc3339(),
            "range": range_value,
            "window_start": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "window_end": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "events_considered": len(in_window),
            "completions_total": len(completions),
            "completions_by_actor": dict(sorted(completions_by_actor.items())),
            "completions_by_proof_tier": dict(sorted(completions_by_proof_tier.items())),
            "daily_streak": int(score_state.get("daily_streak", 0)),
            "weekly_streak": int(score_state.get("weekly_streak", 0)),
            "total_xp": int(score_state.get("total_xp", 0)),
            "plans_generated": plans_generated,
            "avg_quests_per_plan": round((quest_count_sum / plans_generated), 3) if plans_generated else 0.0,
            "quest_success_rate": round((len(completions) / attempts), 4) if attempts else 0.0,
            "failures_by_reason": dict(sorted(failures_by_reason.items())),
            "risk_flags_count": len(flags),
            "top_quests_completed": [
                {"quest_id": quest_id, "count": count}
                for quest_id, count in sorted(quest_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
            ],
            "timebox_estimates_sum": timebox_estimates_sum,
            "observed_duration_sum": observed_duration_sum,
        }
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


def hashlib_sha256_hex(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
