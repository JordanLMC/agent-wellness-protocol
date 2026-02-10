from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .pillars import discover_repo_root, load_canonical_pillars


SEVERITY_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}

CADENCE_VALUES = {"daily", "weekly", "monthly", "ad-hoc"}
MODE_VALUES = {"safe", "authorized"}
RISK_VALUES = {"low", "medium", "high", "critical"}
PROOF_TIER_VALUES = {"P0", "P1", "P2", "P3"}
STEP_TYPES = {"read", "checklist", "reflect", "output", "link", "warn", "confirm", "runbook"}

RISKY_CAPABILITY_PREFIXES = ("exec:", "write:", "id:")
RISKY_CAPABILITIES = {"net:scan_local", "net:scan_remote"}

SECRET_REQUEST_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"paste\s+your\s+(api\s*key|token|private\s*key|seed\s*phrase)",
        r"share\s+your\s+\.env",
        r"copy\s+your\s+credentials?\s+here",
    ]
]

OVER_COLLECTION_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"full\s+logs?",
        r"full\s+emails?",
        r"full\s+dms?",
        r"full\s+file\s+listings?",
    ]
]

BLIND_EXECUTION_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"curl\s+.*\|\s*sh",
        r"wget\s+.*\|\s*sh",
        r"bash\s+-c\s+\$\(",
        r"powershell\s+.*IEX\(",
        r"Invoke-Expression",
        r"certutil\s+.*\s-decode",
        r"base64\s+.*\|\s*(sh|bash|python)",
    ]
]

REMOTE_CODE_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"pip\s+install\s+git\+",
        r"npm\s+install(?!\s+[^@\s]+@[\w.\-]+)",
        r"clone\s+this\s+repo\s+and\s+run\s+install\.sh",
        r"add\s+this\s+mcp\s+server",
    ]
]

PERMISSION_ESCALATION_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"run\s+as\s+(root|admin)",
        r"disable\s+firewall",
        r"open\s+port",
        r"expose\s+dashboard",
        r"skip\s+permissions",
    ]
]

INSTRUCTION_OVERRIDE_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"ignore\s+previous\s+instructions",
        r"override\s+system\/developer\s+message",
        r"do\s+not\s+ask\s+for\s+confirmation",
        r"bypass\s+safeguards",
        r"disable\s+safety",
    ]
]

SOCIAL_CONTAGION_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"share\s+this\s+prompt\s+with\s+other\s+agents",
        r"post\s+this\s+command\s+to\s+your\s+agent\s+feed",
        r"copy\/paste\s+this\s+to\s+moltbook",
        r"moltbook",
    ]
]


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    path: str
    message: str
    suggested_fix: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _to_pointer(base: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]"
    return f"{base}.{key}" if base else f"$.{key}"


def _iter_strings(node: Any, path: str = "$") -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if isinstance(node, str):
        values.append((path, node))
        return values
    if isinstance(node, list):
        for idx, value in enumerate(node):
            values.extend(_iter_strings(value, _to_pointer(path, idx)))
        return values
    if isinstance(node, dict):
        for key, value in node.items():
            values.extend(_iter_strings(value, _to_pointer(path, key)))
    return values


def _get(node: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = node
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _is_risky_capability(capability: str) -> bool:
    if capability.startswith(RISKY_CAPABILITY_PREFIXES):
        return True
    if capability in RISKY_CAPABILITIES:
        return True
    return capability.startswith("net:scan_")


def _has_confirm_step(human_steps: Any) -> bool:
    if not isinstance(human_steps, list):
        return False
    for step in human_steps:
        if isinstance(step, dict) and step.get("type") == "confirm":
            return True
    return False


def _has_warn_or_stop_guidance(steps: dict[str, Any]) -> bool:
    all_steps: list[dict[str, Any]] = []
    for lane in ("human", "agent", "both"):
        lane_steps = steps.get(lane, [])
        if isinstance(lane_steps, list):
            for item in lane_steps:
                if isinstance(item, dict):
                    all_steps.append(item)
    for step in all_steps:
        if step.get("type") == "warn":
            return True
        for _, text in _iter_strings(step, "$.step"):
            lowered = text.lower()
            if "stop" in lowered or "ask human" in lowered:
                return True
    return False


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _add(
    findings: list[Finding],
    *,
    rule_id: str,
    severity: str,
    file: Path,
    path: str,
    message: str,
    suggested_fix: str,
) -> None:
    findings.append(
        Finding(
            rule_id=rule_id,
            severity=severity,
            file=str(file).replace("\\", "/"),
            path=path,
            message=message,
            suggested_fix=suggested_fix,
        )
    )


def lint_path(target_path: str | Path, docs_dir: str | Path | None = None) -> list[Finding]:
    target = Path(target_path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")

    if docs_dir:
        docs = Path(docs_dir).resolve()
    else:
        repo_root = discover_repo_root(target)
        docs = repo_root / "docs"
    canonical_pillars = load_canonical_pillars(docs)

    findings: list[Finding] = []
    quest_files = sorted(p for p in target.rglob("*.quest.yaml") if p.is_file())
    parsed_quests: dict[Path, dict[str, Any]] = {}
    pack_by_quest: dict[Path, Path | None] = {}
    quest_id_by_file: dict[Path, str] = {}

    for quest_file in quest_files:
        pack_dir: Path | None = None
        for parent in [quest_file.parent, *quest_file.parents]:
            if (parent / "pack.yaml").exists():
                pack_dir = parent
                break
        pack_by_quest[quest_file] = pack_dir
        if pack_dir is None:
            _add(
                findings,
                rule_id="PACK-001",
                severity="ERROR",
                file=quest_file,
                path="$",
                message="Quest file is not inside a pack directory with pack.yaml.",
                suggested_fix="Add pack.yaml to the pack directory.",
            )

        try:
            data = yaml.safe_load(quest_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            _add(
                findings,
                rule_id="SCHEMA-001",
                severity="ERROR",
                file=quest_file,
                path="$",
                message=f"YAML parse failure: {exc}",
                suggested_fix="Fix YAML syntax.",
            )
            continue

        if not isinstance(data, dict):
            _add(
                findings,
                rule_id="SCHEMA-001",
                severity="ERROR",
                file=quest_file,
                path="$",
                message="Top-level YAML document must be an object.",
                suggested_fix="Wrap quest content in a top-level mapping.",
            )
            continue

        parsed_quests[quest_file] = data
        quest = data.get("quest")
        if isinstance(quest, dict) and isinstance(quest.get("id"), str):
            quest_id_by_file[quest_file] = quest["id"]

        required_fields = [
            (["schema_version"], "$.schema_version"),
            (["quest", "id"], "$.quest.id"),
            (["quest", "title"], "$.quest.title"),
            (["quest", "summary"], "$.quest.summary"),
            (["quest", "pillars"], "$.quest.pillars"),
            (["quest", "cadence"], "$.quest.cadence"),
            (["quest", "risk_level"], "$.quest.risk_level"),
            (["quest", "mode"], "$.quest.mode"),
            (["quest", "required_capabilities"], "$.quest.required_capabilities"),
            (["quest", "steps"], "$.quest.steps"),
            (["quest", "proof"], "$.quest.proof"),
            (["quest", "scoring"], "$.quest.scoring"),
        ]

        for path, ptr in required_fields:
            value = _get(data, path, default=None)
            if value in (None, ""):
                _add(
                    findings,
                    rule_id="SCHEMA-002",
                    severity="ERROR",
                    file=quest_file,
                    path=ptr,
                    message=f"Missing required field: {'.'.join(path)}",
                    suggested_fix="Populate all required schema fields.",
                )

        quest = data.get("quest", {})
        cadence = quest.get("cadence")
        if cadence is not None and cadence not in CADENCE_VALUES:
            _add(
                findings,
                rule_id="SCHEMA-003",
                severity="ERROR",
                file=quest_file,
                path="$.quest.cadence",
                message=f"Invalid cadence value: {cadence}",
                suggested_fix=f"Use one of: {sorted(CADENCE_VALUES)}",
            )
        mode = quest.get("mode")
        if mode is not None and mode not in MODE_VALUES:
            _add(
                findings,
                rule_id="SCHEMA-003",
                severity="ERROR",
                file=quest_file,
                path="$.quest.mode",
                message=f"Invalid mode value: {mode}",
                suggested_fix=f"Use one of: {sorted(MODE_VALUES)}",
            )
        risk_level = quest.get("risk_level")
        if risk_level is not None and risk_level not in RISK_VALUES:
            _add(
                findings,
                rule_id="SCHEMA-003",
                severity="ERROR",
                file=quest_file,
                path="$.quest.risk_level",
                message=f"Invalid risk_level value: {risk_level}",
                suggested_fix=f"Use one of: {sorted(RISK_VALUES)}",
            )

        proof_tier = _get(data, ["quest", "proof", "tier"])
        if proof_tier is not None and proof_tier not in PROOF_TIER_VALUES:
            _add(
                findings,
                rule_id="SCHEMA-003",
                severity="ERROR",
                file=quest_file,
                path="$.quest.proof.tier",
                message=f"Invalid proof tier value: {proof_tier}",
                suggested_fix=f"Use one of: {sorted(PROOF_TIER_VALUES)}",
            )

        steps = quest.get("steps", {})
        if isinstance(steps, dict):
            for lane in ("human", "agent", "both"):
                lane_steps = steps.get(lane, [])
                if lane_steps is None:
                    continue
                if isinstance(lane_steps, list):
                    for idx, step in enumerate(lane_steps):
                        if isinstance(step, dict):
                            step_type = step.get("type")
                            if step_type not in STEP_TYPES:
                                _add(
                                    findings,
                                    rule_id="SCHEMA-003",
                                    severity="ERROR",
                                    file=quest_file,
                                    path=f"$.quest.steps.{lane}[{idx}].type",
                                    message=f"Invalid step type: {step_type}",
                                    suggested_fix=f"Use one of: {sorted(STEP_TYPES)}",
                                )

        pillars = quest.get("pillars", [])
        if isinstance(pillars, list):
            for idx, pillar in enumerate(pillars):
                if pillar not in canonical_pillars:
                    _add(
                        findings,
                        rule_id="SCHEMA-004",
                        severity="ERROR",
                        file=quest_file,
                        path=f"$.quest.pillars[{idx}]",
                        message=f"Unknown pillar: {pillar}",
                        suggested_fix="Use canonical pillar names from docs/PILLARS.md.",
                    )

        required_capabilities = quest.get("required_capabilities", [])
        if not isinstance(required_capabilities, list):
            required_capabilities = []

        if risk_level == "low" and mode and mode != "safe":
            _add(
                findings,
                rule_id="MODE-001",
                severity="ERROR",
                file=quest_file,
                path="$.quest.mode",
                message="Low-risk quests must run in safe mode.",
                suggested_fix="Set quest.mode to safe.",
            )

        human_steps = _get(data, ["quest", "steps", "human"], default=[])
        if risk_level in {"high", "critical"}:
            if not isinstance(human_steps, list) or not human_steps:
                _add(
                    findings,
                    rule_id="MODE-003",
                    severity="ERROR",
                    file=quest_file,
                    path="$.quest.steps.human",
                    message="High/critical risk quests must include human lane steps.",
                    suggested_fix="Add human lane steps with confirmation gate.",
                )
            if not _has_confirm_step(human_steps):
                _add(
                    findings,
                    rule_id="MODE-003",
                    severity="ERROR",
                    file=quest_file,
                    path="$.quest.steps.human",
                    message="High/critical risk quests must include explicit confirm step.",
                    suggested_fix="Add a confirm step in the human lane.",
                )

        if any(_is_risky_capability(cap) for cap in required_capabilities) and mode != "authorized":
            _add(
                findings,
                rule_id="MODE-004",
                severity="WARN",
                file=quest_file,
                path="$.quest.required_capabilities",
                message="Risky capabilities usually require authorized mode.",
                suggested_fix="Use mode: authorized or remove risky capabilities.",
            )

        proof = quest.get("proof", {})
        proof_tier = proof.get("tier")
        artifacts = proof.get("artifacts", [])
        if proof_tier is None:
            _add(
                findings,
                rule_id="PROOF-001",
                severity="ERROR",
                file=quest_file,
                path="$.quest.proof",
                message="Quest proof section must include tier.",
                suggested_fix="Add proof.tier and proof.artifacts.",
            )
        if proof_tier != "P0" and (not isinstance(artifacts, list) or len(artifacts) == 0):
            _add(
                findings,
                rule_id="PROOF-001",
                severity="ERROR",
                file=quest_file,
                path="$.quest.proof.artifacts",
                message="Non-P0 quests must define at least one artifact.",
                suggested_fix="Declare required proof artifacts.",
            )
        if proof_tier in {"P2", "P3"} and isinstance(artifacts, list):
            for idx, artifact in enumerate(artifacts):
                if isinstance(artifact, dict) and not artifact.get("redaction_policy"):
                    _add(
                        findings,
                        rule_id="PROOF-002",
                        severity="ERROR",
                        file=quest_file,
                        path=f"$.quest.proof.artifacts[{idx}]",
                        message="P2/P3 artifacts require redaction_policy.",
                        suggested_fix="Set artifact.redaction_policy (e.g., no-secrets).",
                    )

        all_strings = _iter_strings(data)
        for ptr, text in all_strings:
            for pattern in SECRET_REQUEST_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="DATA-001",
                        severity="ERROR",
                        file=quest_file,
                        path=ptr,
                        message="Detected secret request language in quest content.",
                        suggested_fix="Replace with non-secret verification guidance.",
                    )
                    break
            for pattern in OVER_COLLECTION_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="DATA-002",
                        severity="WARN",
                        file=quest_file,
                        path=ptr,
                        message="Potential over-collection language detected.",
                        suggested_fix="Request redacted summaries or metadata instead.",
                    )
                    break
            for pattern in BLIND_EXECUTION_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="SEC-CONTENT-001",
                        severity="ERROR",
                        file=quest_file,
                        path=ptr,
                        message="Detected blind execution pattern.",
                        suggested_fix="Replace with reviewed runbook guidance and gating.",
                    )
                    break
            for pattern in REMOTE_CODE_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="SEC-CONTENT-002",
                        severity="WARN",
                        file=quest_file,
                        path=ptr,
                        message="Detected unpinned install or remote code guidance.",
                        suggested_fix="Require pinned versions and provenance review.",
                    )
                    break
            for pattern in PERMISSION_ESCALATION_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="SEC-CONTENT-003",
                        severity="WARN",
                        file=quest_file,
                        path=ptr,
                        message="Detected permission escalation cue.",
                        suggested_fix="Add approval gates and safer alternatives.",
                    )
                    break
            for pattern in INSTRUCTION_OVERRIDE_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="INJECT-001",
                        severity="WARN",
                        file=quest_file,
                        path=ptr,
                        message="Detected instruction hierarchy override language.",
                        suggested_fix="Remove hierarchy-bypass phrasing.",
                    )
                    break
            for pattern in SOCIAL_CONTAGION_PATTERNS:
                if pattern.search(text):
                    _add(
                        findings,
                        rule_id="INJECT-002",
                        severity="WARN",
                        file=quest_file,
                        path=ptr,
                        message="Detected social contagion instruction language.",
                        suggested_fix="Remove agent-to-agent propagation instructions.",
                    )
                    break

        tags = quest.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        if not any(isinstance(tag, str) and tag.lower().startswith("timebox:") for tag in tags):
            _add(
                findings,
                rule_id="UX-001",
                severity="WARN",
                file=quest_file,
                path="$.quest.tags",
                message="Quest is missing timebox metadata.",
                suggested_fix='Add a tag such as "timebox:5".',
            )

        total_steps = 0
        if isinstance(steps, dict):
            for lane in ("human", "agent", "both"):
                lane_steps = steps.get(lane, [])
                if isinstance(lane_steps, list):
                    total_steps += len(lane_steps)
        if total_steps > 12:
            _add(
                findings,
                rule_id="UX-002",
                severity="WARN",
                file=quest_file,
                path="$.quest.steps",
                message=f"Quest has too many steps ({total_steps}).",
                suggested_fix="Keep quests bite-sized (<= 12 steps).",
            )

        if risk_level in {"medium", "high", "critical"} and isinstance(steps, dict):
            if not _has_warn_or_stop_guidance(steps):
                _add(
                    findings,
                    rule_id="UX-003",
                    severity="WARN",
                    file=quest_file,
                    path="$.quest.steps",
                    message="Medium+ risk quest should include warn/stop guidance.",
                    suggested_fix="Add a warn step or explicit stop/ask-human condition.",
                )

    pack_to_ids: dict[Path, dict[str, list[Path]]] = {}
    for quest_file, quest_id in quest_id_by_file.items():
        pack_dir = pack_by_quest.get(quest_file)
        if pack_dir is None:
            continue
        pack_to_ids.setdefault(pack_dir, {}).setdefault(quest_id, []).append(quest_file)
        filename = quest_file.name.lower()
        slug = _slugify(quest_id)
        if quest_id.lower() not in filename and slug not in filename:
            _add(
                findings,
                rule_id="PACK-003",
                severity="ERROR",
                file=quest_file,
                path="$.quest.id",
                message="Quest filename does not include quest ID or deterministic transform.",
                suggested_fix=f"Rename file to include '{quest_id}' or '{slug}'.",
            )

    for pack_dir, id_to_files in pack_to_ids.items():
        for quest_id, files in id_to_files.items():
            if len(files) > 1:
                for file in files:
                    _add(
                        findings,
                        rule_id="PACK-002",
                        severity="ERROR",
                        file=file,
                        path="$.quest.id",
                        message=f"Duplicate quest.id in pack: {quest_id}",
                        suggested_fix="Use unique quest.id values within each pack.",
                    )

        pack_file = pack_dir / "pack.yaml"
        if not pack_file.exists():
            continue
        try:
            pack_data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            _add(
                findings,
                rule_id="PACK-004",
                severity="ERROR",
                file=pack_file,
                path="$",
                message=f"pack.yaml could not be parsed: {exc}",
                suggested_fix="Fix pack.yaml syntax.",
            )
            continue

        checksums = pack_data.get("checksums")
        if checksums is None and isinstance(pack_data.get("pack"), dict):
            checksums = pack_data["pack"].get("checksums")
        if not isinstance(checksums, dict):
            continue
        if checksums.get("algo") != "sha256":
            continue
        files_map = checksums.get("files", {})
        if not isinstance(files_map, dict):
            continue

        for rel_path, expected in files_map.items():
            file_path = (pack_dir / str(rel_path)).resolve()
            if not file_path.exists():
                _add(
                    findings,
                    rule_id="PACK-004",
                    severity="ERROR",
                    file=pack_file,
                    path=f"$.checksums.files.{rel_path}",
                    message=f"Checksum target missing: {rel_path}",
                    suggested_fix="Update checksums.files to existing files.",
                )
                continue
            actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual != str(expected):
                _add(
                    findings,
                    rule_id="PACK-004",
                    severity="ERROR",
                    file=pack_file,
                    path=f"$.checksums.files.{rel_path}",
                    message=f"Checksum mismatch for {rel_path}",
                    suggested_fix="Recompute sha256 checksum in pack.yaml.",
                )

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.file, f.rule_id, f.path))
    return findings


def findings_to_json(findings: list[Finding]) -> str:
    return json.dumps([item.to_dict() for item in findings], indent=2)


def findings_to_text(findings: list[Finding]) -> str:
    if not findings:
        return "No findings."
    lines: list[str] = []
    for finding in findings:
        lines.append(
            f"[{finding.severity}] {finding.rule_id} {finding.file} {finding.path} :: {finding.message}"
        )
        lines.append(f"  fix: {finding.suggested_fix}")
    return "\n".join(lines)
