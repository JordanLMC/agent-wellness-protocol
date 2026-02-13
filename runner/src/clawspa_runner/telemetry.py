from __future__ import annotations

"""Telemetry event sanitization, persistence, and local summary export helpers."""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
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
    "proof.rejected",
    "quest.completed",
    "quest.failed",
    "scorecard.updated",
    "profile.updated",
    "capability.granted",
    "capability.revoked",
    "feedback.submitted",
    "preset.applied",
    "risk.flagged",
    "telemetry.purged",
    "trust_signal.updated",
}
VALID_ACTOR_KINDS = {"human", "agent", "system"}
VALID_SOURCES = {"cli", "api", "mcp"}
MAX_STRING_LENGTH = 200
RANGE_PATTERN = re.compile(r"^(\d+)([dh])$")
GENESIS_PREV_HASH = "0" * 64

if os.name == "nt":  # pragma: no cover - Windows-specific import path
    import msvcrt
else:  # pragma: no cover - POSIX-specific import path
    import fcntl


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


def _event_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    base = dict(payload)
    base.pop("prev_hash", None)
    base.pop("event_hash", None)
    canonical = _safe_json(base)
    return hashlib_sha256_hex(f"{prev_hash}:{canonical}")


def _strip_control_chars(value: str) -> str:
    return "".join(ch for ch in value if not unicodedata.category(ch).startswith("C"))


@dataclass(frozen=True)
class BuildInfo:
    """Static build/runtime metadata attached to every telemetry event."""

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
    """Counts for redactions and truncations emitted during sanitization."""

    redacted_fields: int = 0
    truncated_fields: int = 0


def _combine_stats(a: SanitizeStats, b: SanitizeStats) -> SanitizeStats:
    return SanitizeStats(
        redacted_fields=a.redacted_fields + b.redacted_fields,
        truncated_fields=a.truncated_fields + b.truncated_fields,
    )


def _sanitize_text(value: str, *, empty_fallback: str | None = None) -> tuple[str, SanitizeStats]:
    cleaned = _strip_control_chars(value).strip()
    if not cleaned and empty_fallback is not None:
        cleaned = empty_fallback
    if payload_contains_secrets(cleaned) or payload_contains_pii(cleaned):
        return "[redacted]", SanitizeStats(redacted_fields=1)
    if len(cleaned) > MAX_STRING_LENGTH:
        return f"{cleaned[:MAX_STRING_LENGTH]}...[truncated]", SanitizeStats(truncated_fields=1)
    return cleaned, SanitizeStats()


def sanitize_actor_id(value: Any) -> str:
    """Normalize actor identity to a safe string and redact risky payloads."""

    text = "unknown" if value is None else str(value)
    sanitized, _ = _sanitize_text(text, empty_fallback="unknown")
    if not sanitized:
        return "unknown"
    return sanitized


def normalize_actor_model(
    actor: Any,
    *,
    actor_id: Any | None = None,
    default_kind: str = "system",
) -> dict[str, str]:
    """Return canonical actor model `{kind, id}` for events and exports."""

    raw_kind: Any = default_kind
    raw_id: Any | None = actor_id

    if isinstance(actor, dict):
        raw_kind = actor.get("kind", default_kind)
        if raw_id is None:
            raw_id = actor.get("id")
    elif isinstance(actor, str):
        lowered = actor.strip().lower()
        if lowered in VALID_ACTOR_KINDS:
            raw_kind = lowered
        else:
            if raw_id is None and actor.strip():
                raw_id = actor
            if ":" in lowered:
                prefix = lowered.split(":", 1)[0]
                if prefix in VALID_ACTOR_KINDS:
                    raw_kind = prefix
    else:
        raw_kind = default_kind

    kind = str(raw_kind).strip().lower()
    if kind not in VALID_ACTOR_KINDS:
        kind = default_kind if default_kind in VALID_ACTOR_KINDS else "system"
    return {"kind": kind, "id": sanitize_actor_id(raw_id)}


def normalize_event_actor(event: dict[str, Any]) -> dict[str, str]:
    """Read actor information from legacy or modern event payload shapes."""

    actor_value = event.get("actor")
    if isinstance(actor_value, dict):
        return normalize_actor_model(actor_value, default_kind="system")
    if isinstance(actor_value, str):
        return normalize_actor_model(actor_value, default_kind="system")
    return {"kind": "system", "id": "unknown"}


def normalize_event_source(event: dict[str, Any]) -> str:
    """Return normalized event source with a safe default."""

    source = event.get("source")
    if isinstance(source, str):
        candidate = source.strip().lower()
        if candidate in VALID_SOURCES:
            return candidate
    return "cli"


def _sanitize_scalar(value: Any) -> tuple[Any, SanitizeStats]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, SanitizeStats()
    if isinstance(value, str):
        return _sanitize_text(value, empty_fallback="")

    as_text = str(value)
    return _sanitize_text(as_text, empty_fallback="")


def sanitize_event_data(data: Any) -> tuple[Any, SanitizeStats]:
    """Recursively sanitize telemetry payloads for secrets, PII, and controls."""

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
    """Parse compact duration windows such as `7d` or `24h`."""

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
    """Best-effort short commit hash for build provenance metadata."""

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
    """Resolve installed package version with local fallback."""

    try:
        return package_version("clawspa")
    except PackageNotFoundError:
        return "0.1.0"


class TelemetryTailError(RuntimeError):
    """Raised when the current telemetry tail cannot safely anchor a new hashed event."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class TelemetryLogger:
    """Append-only telemetry logger with local summary export helpers."""

    def __init__(self, events_path: Path, repo_root: Path) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.events_path.parent / f"{self.events_path.name}.lock"
        self.build = BuildInfo(
            runner_version=detect_runner_version(),
            git_sha=detect_git_sha(repo_root),
            python_version=sys.version.split()[0],
            platform=platform.platform(),
        )

    def _normalize_source(self, source: str) -> str:
        if source in VALID_SOURCES:
            return source
        return "cli"

    @contextmanager
    def _events_lock(self) -> Any:
        """Acquire a cross-process lock used by all telemetry file writers/readers."""

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            if os.name == "nt":
                lock_handle.seek(0, os.SEEK_END)
                if lock_handle.tell() == 0:
                    lock_handle.write(b"\0")
                    lock_handle.flush()
                lock_handle.seek(0)
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield lock_handle
                finally:
                    lock_handle.seek(0)
                    msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield lock_handle
                finally:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _read_last_nonempty_line(self) -> str | None:
        """Read the last non-empty JSONL row using end-seek scanning."""

        if not self.events_path.exists():
            return None
        with self.events_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            if file_size == 0:
                return None

            scan = file_size - 1
            while scan >= 0:
                handle.seek(scan)
                char = handle.read(1)
                if char not in {b"\n", b"\r"}:
                    break
                scan -= 1
            if scan < 0:
                return None

            line_end = scan
            line_start = 0
            while scan > 0:
                scan -= 1
                handle.seek(scan)
                if handle.read(1) == b"\n":
                    line_start = scan + 1
                    break

            handle.seek(line_start)
            raw_line = handle.read(line_end - line_start + 1)
            try:
                text = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TelemetryTailError(
                    "invalid_utf8_tail",
                    "Telemetry tail is not UTF-8 decodable; rotate telemetry before writing.",
                ) from exc
            stripped = text.strip()
            return stripped or None

    def _tail_event_hash_locked(self) -> str:
        """Return the last event hash from file tail or genesis when file is empty."""

        last_line = self._read_last_nonempty_line()
        if last_line is None:
            return GENESIS_PREV_HASH
        try:
            payload = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise TelemetryTailError(
                "invalid_json_line",
                "Telemetry tail has invalid JSON; rotate telemetry before writing.",
            ) from exc
        if not isinstance(payload, dict):
            raise TelemetryTailError(
                "invalid_event_shape",
                "Telemetry tail is not a JSON object; rotate telemetry before writing.",
            )
        if "prev_hash" not in payload or "event_hash" not in payload:
            raise TelemetryTailError(
                "missing_hash_fields",
                "Telemetry tail has missing hash fields; rotate telemetry before writing new events.",
            )
        prev_hash = str(payload.get("prev_hash"))
        event_hash = str(payload.get("event_hash"))
        expected_hash = _event_hash(prev_hash, payload)
        if event_hash != expected_hash:
            raise TelemetryTailError(
                "event_hash_mismatch",
                "Telemetry tail hash mismatch; rotate telemetry before writing new events.",
            )
        return event_hash

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self._events_lock():
            prev_hash = self._tail_event_hash_locked()
            row = dict(payload)
            row["prev_hash"] = prev_hash
            row["event_hash"] = _event_hash(prev_hash, row)
            with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(_safe_json(row))
                handle.write("\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

    def _base_event(
        self,
        *,
        event_type: str,
        actor: str,
        actor_id: str | None,
        source: str,
        data: dict[str, Any],
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        requested_event_type = event_type
        if requested_event_type not in VALID_EVENT_TYPES:
            event_type = "risk.flagged"
            data = {
                "reason": "invalid_event_type",
                "invalid_event_type_hash": hashlib_sha256_hex(requested_event_type),
            }
        actor_model = normalize_actor_model(actor, actor_id=actor_id, default_kind="system")
        return {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(uuid.uuid4()),
            "ts": _utc_now_rfc3339(),
            "event_type": event_type,
            "actor": actor_model,
            "source": self._normalize_source(source),
            "trace_id": sanitize_actor_id(trace_id) if trace_id is not None else None,
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
        actor_id: str | None = None,
        trace_id: str | None = None,
        _emit_sanitize_flag: bool = True,
    ) -> None:
        """Write one sanitized event and optional sanitization risk flag."""

        try:
            sanitized_data, stats = sanitize_event_data(data)
            event_payload = self._base_event(
                event_type=event_type,
                actor=actor,
                actor_id=actor_id,
                source=source,
                data=sanitized_data if isinstance(sanitized_data, dict) else {"value": sanitized_data},
                trace_id=trace_id,
            )
            self._append_jsonl(event_payload)
            if _emit_sanitize_flag and (stats.redacted_fields or stats.truncated_fields):
                self.log_event(
                    "risk.flagged",
                    actor="system",
                    actor_id=actor_id,
                    source=source,
                    trace_id=trace_id,
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
        with self._events_lock():
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
        with self._events_lock():
            if not self.events_path.exists():
                return 0
            count = 0
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        count += 1
            return count

    def purge(self) -> bool:
        with self._events_lock():
            if not self.events_path.exists():
                return False
            self.events_path.unlink()
            return True

    def verify_chain(self) -> dict[str, Any]:
        """Verify telemetry hash-chain integrity and report first break, if any."""

        with self._events_lock():
            if not self.events_path.exists():
                return {"ok": True, "checked_events": 0, "broken_index": None, "reason": None}

            prev_hash = GENESIS_PREV_HASH
            checked = 0
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line_idx, raw_line in enumerate(handle):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        return {
                            "ok": False,
                            "checked_events": checked,
                            "broken_index": line_idx,
                            "reason": "invalid_json_line",
                        }
                    if not isinstance(payload, dict):
                        return {
                            "ok": False,
                            "checked_events": checked,
                            "broken_index": line_idx,
                            "reason": "invalid_event_shape",
                        }
                    if "prev_hash" not in payload or "event_hash" not in payload:
                        return {
                            "ok": False,
                            "checked_events": checked,
                            "broken_index": line_idx,
                            "reason": "missing_hash_fields",
                        }
                    expected_prev = str(payload.get("prev_hash"))
                    if expected_prev != prev_hash:
                        return {
                            "ok": False,
                            "checked_events": checked,
                            "broken_index": line_idx,
                            "reason": "prev_hash_mismatch",
                        }
                    expected_hash = _event_hash(prev_hash, payload)
                    event_hash = str(payload.get("event_hash"))
                    if event_hash != expected_hash:
                        return {
                            "ok": False,
                            "checked_events": checked,
                            "broken_index": line_idx,
                            "reason": "event_hash_mismatch",
                        }
                    prev_hash = event_hash
                    checked += 1
            return {"ok": True, "checked_events": checked, "broken_index": None, "reason": None}

    def purge_older_than(self, older_than: timedelta) -> dict[str, Any]:
        """Purge telemetry events older than a relative threshold and keep chain valid."""

        if older_than <= timedelta(0):
            raise ValueError("older_than must be positive.")
        with self._events_lock():
            if not self.events_path.exists():
                return {
                    "path": str(self.events_path),
                    "purged_count": 0,
                    "kept_count": 0,
                    "archive_path": None,
                    "archive_sha256": None,
                }

            cutoff = _utc_now() - older_than
            kept: list[dict[str, Any]] = []
            purged: list[dict[str, Any]] = []
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    parsed_ts = _parse_ts(payload.get("ts"))
                    if parsed_ts is None:
                        kept.append(payload)
                        continue
                    if parsed_ts < cutoff:
                        purged.append(payload)
                    else:
                        kept.append(payload)

            if not purged:
                return {
                    "path": str(self.events_path),
                    "purged_count": 0,
                    "kept_count": len(kept),
                    "archive_path": None,
                    "archive_sha256": None,
                }

            archive_dir = self.events_path.parent / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            stamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
            archive_path = archive_dir / f"events-purged-{stamp}.jsonl"
            with archive_path.open("w", encoding="utf-8", newline="\n") as handle:
                for item in purged:
                    handle.write(_safe_json(item))
                    handle.write("\n")
            archive_sha256 = hashlib_sha256_hex(archive_path.read_text(encoding="utf-8"))

            prev_hash = GENESIS_PREV_HASH
            with self.events_path.open("w", encoding="utf-8", newline="\n") as handle:
                for item in kept:
                    row = dict(item)
                    row.pop("prev_hash", None)
                    row.pop("event_hash", None)
                    row["prev_hash"] = prev_hash
                    row["event_hash"] = _event_hash(prev_hash, row)
                    prev_hash = str(row["event_hash"])
                    handle.write(_safe_json(row))
                    handle.write("\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

            return {
                "path": str(self.events_path),
                "purged_count": len(purged),
                "kept_count": len(kept),
                "archive_path": str(archive_path),
                "archive_sha256": archive_sha256,
            }

    def export_summary(
        self,
        *,
        range_value: str,
        score_state: dict[str, Any],
        out_path: Path | None = None,
        actor_id: str | None = None,
        applied_preset_id: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate windowed telemetry metrics, optionally filtered by actor id."""

        window = parse_range(range_value)
        end = _utc_now()
        start = end - window
        actor_filter = sanitize_actor_id(actor_id) if actor_id is not None else None

        events = self.iter_events()
        in_window: list[dict[str, Any]] = []
        normalized_actors: dict[int, dict[str, str]] = {}
        normalized_sources: dict[int, str] = {}
        for event in events:
            parsed_ts = _parse_ts(event.get("ts"))
            if parsed_ts is None:
                continue
            if not (start <= parsed_ts <= end):
                continue
            actor_model = normalize_event_actor(event)
            if actor_filter is not None and actor_model["id"] != actor_filter:
                continue
            in_window.append(event)
            normalized_actors[id(event)] = actor_model
            normalized_sources[id(event)] = normalize_event_source(event)

        completions = [evt for evt in in_window if evt.get("event_type") == "quest.completed"]
        failures = [evt for evt in in_window if evt.get("event_type") == "quest.failed"]
        plans = [evt for evt in in_window if evt.get("event_type") == "plan.generated"]
        flags = [evt for evt in in_window if evt.get("event_type") == "risk.flagged"]
        feedback = [evt for evt in in_window if evt.get("event_type") == "feedback.submitted"]

        quest_pillars_by_id: dict[str, list[str]] = {}
        quest_pack_by_id: dict[str, str] = {}
        for event in completions:
            data = event.get("data", {})
            if not isinstance(data, dict):
                continue
            quest_id = data.get("quest_id")
            if not isinstance(quest_id, str) or not quest_id:
                continue
            pillars = [str(item) for item in data.get("pillars", []) if isinstance(item, str) and item]
            if pillars:
                quest_pillars_by_id[quest_id] = pillars
            pack_id = data.get("pack_id")
            if isinstance(pack_id, str) and pack_id:
                quest_pack_by_id[quest_id] = pack_id

        def _resolve_pillars(event: dict[str, Any]) -> list[str]:
            data = event.get("data", {})
            if isinstance(data, dict):
                pillars = data.get("pillars", [])
                if isinstance(pillars, list):
                    normalized = [str(item) for item in pillars if isinstance(item, str) and item]
                    if normalized:
                        return normalized
                quest_id = data.get("quest_id")
                if isinstance(quest_id, str) and quest_id in quest_pillars_by_id:
                    return quest_pillars_by_id[quest_id]
            return ["Unknown"]

        def _resolve_pack(event: dict[str, Any]) -> str:
            data = event.get("data", {})
            if isinstance(data, dict):
                pack_id = data.get("pack_id")
                if isinstance(pack_id, str) and pack_id:
                    return pack_id
                quest_id = data.get("quest_id")
                if isinstance(quest_id, str):
                    return quest_pack_by_id.get(quest_id, "unknown")
            return "unknown"

        events_by_actor_kind = Counter(normalized_actors[id(evt)]["kind"] for evt in in_window)
        events_by_actor_id = Counter(normalized_actors[id(evt)]["id"] for evt in in_window)
        completions_by_actor_kind = Counter(normalized_actors[id(evt)]["kind"] for evt in completions)
        completions_by_actor_id = Counter(normalized_actors[id(evt)]["id"] for evt in completions)
        completions_by_source = Counter(normalized_sources[id(evt)] for evt in completions)
        completions_by_proof_tier = Counter(
            str(evt.get("data", {}).get("proof_tier", "unknown")) for evt in completions
        )
        failures_by_reason = Counter(str(evt.get("data", {}).get("reason", "unknown")) for evt in failures)
        quest_counts = Counter(str(evt.get("data", {}).get("quest_id", "")) for evt in completions)
        quest_counts.pop("", None)
        completions_by_pillar: Counter[str] = Counter()
        xp_by_pillar: Counter[str] = Counter()
        completions_by_pack: Counter[str] = Counter()
        completions_by_preset: Counter[str] = Counter()
        xp_by_preset: Counter[str] = Counter()
        risk_flags_by_pillar: Counter[str] = Counter()
        attempts_by_pillar: Counter[str] = Counter()
        successes_by_pillar: Counter[str] = Counter()
        feedback_by_component: Counter[str] = Counter()
        feedback_by_severity: Counter[str] = Counter()

        for event in completions:
            data = event.get("data", {})
            awarded = int(data.get("xp_awarded", 0)) if isinstance(data, dict) else 0
            pack_id = _resolve_pack(event)
            completions_by_pack[pack_id] += 1
            preset_id = "none"
            if isinstance(data, dict):
                raw_preset_id = data.get("applied_preset_id")
                if isinstance(raw_preset_id, str) and raw_preset_id:
                    preset_id = raw_preset_id
            completions_by_preset[preset_id] += 1
            xp_by_preset[preset_id] += awarded
            for pillar in _resolve_pillars(event):
                completions_by_pillar[pillar] += 1
                xp_by_pillar[pillar] += awarded
                successes_by_pillar[pillar] += 1
                attempts_by_pillar[pillar] += 1

        for event in failures:
            for pillar in _resolve_pillars(event):
                attempts_by_pillar[pillar] += 1

        for event in flags:
            for pillar in _resolve_pillars(event):
                risk_flags_by_pillar[pillar] += 1

        for event in feedback:
            data = event.get("data", {})
            if not isinstance(data, dict):
                continue
            component = data.get("component")
            severity = data.get("severity")
            if isinstance(component, str) and component:
                feedback_by_component[component] += 1
            if isinstance(severity, str) and severity:
                feedback_by_severity[severity] += 1

        plans_generated = len(plans)
        quest_count_sum = sum(int(evt.get("data", {}).get("quest_count", 0)) for evt in plans)
        attempts = len(completions) + len(failures)
        timebox_estimates_sum = sum(
            int(evt.get("data", {}).get("timebox_estimate_minutes", 0)) for evt in completions
        )
        observed_duration_sum = sum(
            int(evt.get("data", {}).get("observed_duration_seconds", 0)) for evt in completions
        )
        quest_success_rate_by_pillar = {
            pillar: round((successes_by_pillar[pillar] / attempts_by_pillar[pillar]), 4)
            for pillar in sorted(attempts_by_pillar)
            if attempts_by_pillar[pillar] > 0
        }

        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now_rfc3339(),
            "range": range_value,
            "actor_id_filter": actor_filter,
            "applied_preset_id": applied_preset_id,
            "window_start": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "window_end": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "events_considered": len(in_window),
            "events_by_actor_kind": dict(sorted(events_by_actor_kind.items())),
            "events_by_actor_id": dict(sorted(events_by_actor_id.items())),
            "completions_total": len(completions),
            "completions_by_actor": dict(sorted(completions_by_actor_kind.items())),
            "completions_by_actor_kind": dict(sorted(completions_by_actor_kind.items())),
            "completions_by_actor_id": dict(sorted(completions_by_actor_id.items())),
            "completions_by_source": dict(sorted(completions_by_source.items())),
            "completions_by_proof_tier": dict(sorted(completions_by_proof_tier.items())),
            "completions_by_pillar": dict(sorted(completions_by_pillar.items())),
            "xp_by_pillar": dict(sorted(xp_by_pillar.items())),
            "completions_by_pack": dict(sorted(completions_by_pack.items())),
            "completions_by_preset": dict(sorted(completions_by_preset.items())),
            "xp_by_preset": dict(sorted(xp_by_preset.items())),
            "daily_streak": int(score_state.get("daily_streak", 0)),
            "weekly_streak": int(score_state.get("weekly_streak", 0)),
            "total_xp": int(score_state.get("total_xp", 0)),
            "plans_generated": plans_generated,
            "avg_quests_per_plan": round((quest_count_sum / plans_generated), 3) if plans_generated else 0.0,
            "quest_success_rate": round((len(completions) / attempts), 4) if attempts else 0.0,
            "quest_success_rate_by_pillar": quest_success_rate_by_pillar,
            "failures_by_reason": dict(sorted(failures_by_reason.items())),
            "risk_flags_count": len(flags),
            "risk_flags_by_pillar": dict(sorted(risk_flags_by_pillar.items())),
            "feedback_count": len(feedback),
            "feedback_by_component": dict(sorted(feedback_by_component.items())),
            "feedback_by_severity": dict(sorted(feedback_by_severity.items())),
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
    """Return SHA-256 hex digest for sensitive identifier hashing."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def summary_sha256(summary: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 for an aggregated telemetry summary."""

    return hashlib_sha256_hex(_safe_json(summary))


def load_aggregated_summary(path: Path) -> dict[str, Any]:
    """Load and validate an aggregated telemetry summary JSON document."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid telemetry summary file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Telemetry summary must be a JSON object: {path}")

    required = {
        "schema_version",
        "generated_at",
        "range",
        "events_considered",
        "completions_total",
        "total_xp",
        "daily_streak",
        "weekly_streak",
        "risk_flags_count",
        "quest_success_rate",
        "completions_by_actor_id",
        "top_quests_completed",
    }
    missing = [key for key in sorted(required) if key not in payload]
    if missing:
        raise ValueError(f"Telemetry summary missing required keys: {', '.join(missing)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported telemetry summary schema_version: {payload.get('schema_version')}; expected {SCHEMA_VERSION}."
        )
    return payload


def diff_aggregated_summaries(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Produce a safe baseline diff from two aggregated telemetry summaries."""

    def _delta_int(field: str) -> int:
        return int(b.get(field, 0)) - int(a.get(field, 0))

    def _delta_float(field: str, ndigits: int = 4) -> float:
        return round(float(b.get(field, 0.0)) - float(a.get(field, 0.0)), ndigits)

    def _counter_delta(field: str) -> dict[str, int]:
        left = a.get(field, {})
        right = b.get(field, {})
        if not isinstance(left, dict):
            left = {}
        if not isinstance(right, dict):
            right = {}
        keys = sorted(set(left) | set(right))
        return {str(key): int(right.get(key, 0)) - int(left.get(key, 0)) for key in keys}

    def _counter_delta_float(field: str, ndigits: int = 4) -> dict[str, float]:
        left = a.get(field, {})
        right = b.get(field, {})
        if not isinstance(left, dict):
            left = {}
        if not isinstance(right, dict):
            right = {}
        keys = sorted(set(left) | set(right))
        return {
            str(key): round(float(right.get(key, 0.0)) - float(left.get(key, 0.0)), ndigits)
            for key in keys
        }

    def _top_quest_delta() -> list[dict[str, Any]]:
        def _to_counter(node: Any) -> dict[str, int]:
            if not isinstance(node, list):
                return {}
            counter: dict[str, int] = {}
            for item in node:
                if not isinstance(item, dict):
                    continue
                quest_id = item.get("quest_id")
                count = item.get("count", 0)
                if isinstance(quest_id, str):
                    counter[quest_id] = int(count)
            return counter

        before = _to_counter(a.get("top_quests_completed"))
        after = _to_counter(b.get("top_quests_completed"))
        keys = sorted(set(before) | set(after))
        rows = []
        for quest_id in keys:
            rows.append(
                {
                    "quest_id": quest_id,
                    "before": before.get(quest_id, 0),
                    "after": after.get(quest_id, 0),
                    "delta": after.get(quest_id, 0) - before.get(quest_id, 0),
                }
            )
        rows.sort(key=lambda item: (-abs(int(item["delta"])), item["quest_id"]))
        return rows

    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_a_generated_at": a.get("generated_at"),
        "baseline_b_generated_at": b.get("generated_at"),
        "baseline_a_range": a.get("range"),
        "baseline_b_range": b.get("range"),
        "changes": {
            "events_considered_delta": _delta_int("events_considered"),
            "completions_total_delta": _delta_int("completions_total"),
            "total_xp_delta": _delta_int("total_xp"),
            "daily_streak_delta": _delta_int("daily_streak"),
            "weekly_streak_delta": _delta_int("weekly_streak"),
            "risk_flags_count_delta": _delta_int("risk_flags_count"),
            "feedback_count_delta": _delta_int("feedback_count"),
            "quest_success_rate_delta": _delta_float("quest_success_rate"),
            "completions_by_actor_id_delta": _counter_delta("completions_by_actor_id"),
            "completions_by_pillar_delta": _counter_delta("completions_by_pillar"),
            "xp_by_pillar_delta": _counter_delta("xp_by_pillar"),
            "completions_by_pack_delta": _counter_delta("completions_by_pack"),
            "completions_by_preset_delta": _counter_delta("completions_by_preset"),
            "xp_by_preset_delta": _counter_delta("xp_by_preset"),
            "risk_flags_by_pillar_delta": _counter_delta("risk_flags_by_pillar"),
            "feedback_by_component_delta": _counter_delta("feedback_by_component"),
            "feedback_by_severity_delta": _counter_delta("feedback_by_severity"),
            "quest_success_rate_by_pillar_delta": _counter_delta_float("quest_success_rate_by_pillar"),
            "top_quests_completed_delta": _top_quest_delta(),
        },
    }


def render_summary_diff_text(diff_payload: dict[str, Any]) -> str:
    """Render a compact human-readable summary diff."""

    changes = diff_payload.get("changes", {})
    top_deltas = changes.get("top_quests_completed_delta", [])
    if not isinstance(top_deltas, list):
        top_deltas = []

    lines = [
        f"Baseline A: {diff_payload.get('baseline_a_generated_at')} ({diff_payload.get('baseline_a_range')})",
        f"Baseline B: {diff_payload.get('baseline_b_generated_at')} ({diff_payload.get('baseline_b_range')})",
        f"Completions delta: {changes.get('completions_total_delta', 0)}",
        f"Total XP delta: {changes.get('total_xp_delta', 0)}",
        f"Daily streak delta: {changes.get('daily_streak_delta', 0)}",
        f"Weekly streak delta: {changes.get('weekly_streak_delta', 0)}",
        f"Risk flags delta: {changes.get('risk_flags_count_delta', 0)}",
        f"Feedback submitted delta: {changes.get('feedback_count_delta', 0)}",
        f"Quest success rate delta: {changes.get('quest_success_rate_delta', 0.0)}",
    ]
    pillar_delta = changes.get("completions_by_pillar_delta", {})
    if isinstance(pillar_delta, dict) and pillar_delta:
        top_pillars = sorted(pillar_delta.items(), key=lambda item: (-abs(int(item[1])), str(item[0])))[:3]
        lines.append("Top pillar completion deltas:")
        for pillar, delta in top_pillars:
            lines.append(f"- {pillar}: delta {delta}")
    if top_deltas:
        lines.append("Top quest deltas:")
        for row in top_deltas[:5]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('quest_id')}: {row.get('before', 0)} -> {row.get('after', 0)} "
                f"(delta {row.get('delta', 0)})"
            )
    return "\n".join(lines)
