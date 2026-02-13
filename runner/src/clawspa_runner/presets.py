from __future__ import annotations

"""Preset loading and normalization helpers for deterministic planner hints."""

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


PRESET_SCHEMA_VERSION = "0.1"
DEFAULT_CADENCE_WEIGHTS = {"daily": 1.0, "weekly": 1.0, "monthly": 1.0}


def _to_positive_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if parsed <= 0:
        return fallback
    return parsed


def _normalize_relative_weights(weights: dict[str, float]) -> dict[str, float]:
    filtered = {key: float(value) for key, value in weights.items() if float(value) > 0}
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {key: round(value / total, 6) for key, value in sorted(filtered.items())}


def _schema_path(repo_root: Path) -> Path:
    return repo_root / "presets" / "schema" / "preset.schema.json"


def _preset_dir(repo_root: Path) -> Path:
    return repo_root / "presets" / "v0"


def _load_schema(repo_root: Path) -> dict[str, Any]:
    path = _schema_path(repo_root)
    if not path.exists():
        raise ValueError(f"Preset schema file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Preset schema is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Preset schema must be a JSON object: {path}")
    return payload


def load_presets(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Load and validate versioned preset YAML files from the repository."""

    schema = _load_schema(repo_root)
    validator = Draft202012Validator(schema)
    preset_dir = _preset_dir(repo_root)
    if not preset_dir.exists():
        raise ValueError(f"Preset directory not found: {preset_dir}")

    loaded: dict[str, dict[str, Any]] = {}
    for preset_path in sorted(preset_dir.glob("*.preset.yaml")):
        payload = yaml.safe_load(preset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Preset file must be a mapping: {preset_path}")
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
        if errors:
            first = errors[0]
            where = ".".join(str(part) for part in first.path) or "<root>"
            raise ValueError(f"Preset schema validation failed for {preset_path} at {where}: {first.message}")
        preset_id = payload.get("preset_id")
        if not isinstance(preset_id, str) or not preset_id:
            raise ValueError(f"Preset file missing preset_id: {preset_path}")
        if preset_id in loaded:
            raise ValueError(f"Duplicate preset_id detected: {preset_id}")
        normalized = dict(payload)
        normalized["_file"] = str(preset_path)
        loaded[preset_id] = normalized

    if not loaded:
        raise ValueError(f"No preset definitions found under {preset_dir}")
    return dict(sorted(loaded.items()))


def preset_pack_allowlist(preset: dict[str, Any]) -> set[str]:
    allowlist = preset.get("pack_allowlist", [])
    if not isinstance(allowlist, list):
        return set()
    values = {value.strip() for value in allowlist if isinstance(value, str) and value.strip()}
    return values


def preset_pillar_weights(preset: dict[str, Any]) -> dict[str, float]:
    raw = preset.get("pillar_weights", {})
    if not isinstance(raw, dict):
        return {}
    parsed = {str(key): _to_positive_float(value, 0.0) for key, value in raw.items()}
    return _normalize_relative_weights(parsed)


def preset_cadence_weights(preset: dict[str, Any]) -> dict[str, float]:
    raw = preset.get("cadence", {})
    merged = dict(DEFAULT_CADENCE_WEIGHTS)
    if isinstance(raw, dict):
        merged["daily"] = _to_positive_float(raw.get("daily_weight"), merged["daily"])
        merged["weekly"] = _to_positive_float(raw.get("weekly_weight"), merged["weekly"])
        merged["monthly"] = _to_positive_float(raw.get("monthly_weight"), merged["monthly"])
    normalized = _normalize_relative_weights(merged)
    if not normalized:
        return dict(DEFAULT_CADENCE_WEIGHTS)
    normalized["ad-hoc"] = normalized.get("daily", 0.333333)
    return normalized


def summarize_preset(preset: dict[str, Any]) -> dict[str, Any]:
    """Return a stable public view of preset metadata and normalized weights."""

    return {
        "schema_version": preset.get("schema_version", PRESET_SCHEMA_VERSION),
        "preset_id": preset.get("preset_id"),
        "name": preset.get("name"),
        "description": preset.get("description"),
        "intended_for": preset.get("intended_for"),
        "pack_allowlist": sorted(preset_pack_allowlist(preset)),
        "pillar_weights": preset_pillar_weights(preset),
        "cadence": preset_cadence_weights(preset),
        "default_proof_tier": preset.get("default_proof_tier"),
        "capability_policy": preset.get("capability_policy", {}),
        "telemetry_tags": [tag for tag in preset.get("telemetry_tags", []) if isinstance(tag, str)],
    }
