from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "update_pack_checksums.py"


def _normalized_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_update_pack_checksums_updates_manifest_and_is_idempotent(tmp_path: Path) -> None:
    pack_dir = tmp_path / "packs" / "wellness.core.v0"
    quests_dir = pack_dir / "quests"

    quest_a = quests_dir / "wellness.example.a.v1.quest.yaml"
    quest_b = quests_dir / "wellness.example.b.v1.quest.yaml"

    _write(
        quest_a,
        """
schema_version: 0.1
quest:
  id: "wellness.example.a.v1"
  title: "A"
  summary: "A"
  pillars: ["Security & Access Control"]
  cadence: "daily"
  difficulty: 1
  risk_level: "low"
  mode: "safe"
  required_capabilities: []
  steps:
    human:
      - type: "read"
        text: "Read."
    agent:
      - type: "reflect"
        text: "Reflect."
  proof:
    tier: "P0"
    artifacts: []
  scoring:
    base_xp: 5
    streak_weight: 1
    proof_multiplier: {P0: 1.0, P1: 1.2, P2: 1.5, P3: 1.4}
  tags: ["short:EXAMPLE-A", "timebox:1"]
""",
    )
    _write(
        quest_b,
        """
schema_version: 0.1
quest:
  id: "wellness.example.b.v1"
  title: "B"
  summary: "B"
  pillars: ["Security & Access Control"]
  cadence: "weekly"
  difficulty: 1
  risk_level: "low"
  mode: "safe"
  required_capabilities: []
  steps:
    human:
      - type: "read"
        text: "Read."
    agent:
      - type: "reflect"
        text: "Reflect."
  proof:
    tier: "P0"
    artifacts: []
  scoring:
    base_xp: 5
    streak_weight: 1
    proof_multiplier: {P0: 1.0, P1: 1.2, P2: 1.5, P3: 1.4}
  tags: ["short:EXAMPLE-B", "timebox:1"]
""",
    )

    _write(
        pack_dir / "pack.yaml",
        """
pack_version: 0.1
pack:
  id: wellness.core.v0
  title: Core Wellness Pack
  publisher:
    name: Agent Wellness Project
    id: org.agentwellness
    contact: security@agentwellness.example
  version: 0.1.0
  license: Apache-2.0
  created_at: '2026-02-09'
  quests: ["outdated.id.v1"]
  checksums:
    algo: sha256
    files:
      quests/wellness.example.a.v1.quest.yaml: 0000000000000000000000000000000000000000000000000000000000000000
  signing:
    scheme: none
    signature: null
    public_key: null
""",
    )

    first = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(pack_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    assert "Updated:" in first.stdout

    pack_doc = yaml.safe_load((pack_dir / "pack.yaml").read_text(encoding="utf-8"))
    assert pack_doc["pack"]["quests"] == ["wellness.example.a.v1", "wellness.example.b.v1"]

    expected_checksums = {
        "quests/wellness.example.a.v1.quest.yaml": _normalized_sha256(quest_a),
        "quests/wellness.example.b.v1.quest.yaml": _normalized_sha256(quest_b),
    }
    assert pack_doc["pack"]["checksums"]["algo"] == "sha256"
    assert pack_doc["pack"]["checksums"]["files"] == expected_checksums

    rendered_after_first = (pack_dir / "pack.yaml").read_text(encoding="utf-8")
    second = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(pack_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0
    assert "No changes:" in second.stdout
    assert (pack_dir / "pack.yaml").read_text(encoding="utf-8") == rendered_after_first
