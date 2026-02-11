from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml


def _sha256_text_normalized(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _collect_quest_ids_and_checksums(pack_dir: Path) -> tuple[list[str], dict[str, str]]:
    quests_dir = pack_dir / "quests"
    quest_files = sorted(quests_dir.glob("*.quest.yaml"), key=lambda p: p.name)

    quest_ids: list[str] = []
    checksums: dict[str, str] = {}

    for file_path in quest_files:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        quest = data.get("quest", {})
        quest_id = quest.get("id")
        if not isinstance(quest_id, str) or not quest_id:
            raise ValueError(f"Missing quest.id in {file_path}")

        quest_ids.append(quest_id)
        rel = file_path.relative_to(pack_dir).as_posix()
        checksums[rel] = _sha256_text_normalized(file_path)

    return sorted(quest_ids), checksums


def update_pack(pack_dir: Path) -> bool:
    pack_file = pack_dir / "pack.yaml"
    if not pack_file.exists():
        raise FileNotFoundError(f"Missing pack manifest: {pack_file}")

    old_text = pack_file.read_text(encoding="utf-8")
    doc = yaml.safe_load(old_text) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"pack.yaml must contain a YAML mapping: {pack_file}")

    pack = doc.get("pack")
    if not isinstance(pack, dict):
        raise ValueError("pack.yaml is missing the top-level 'pack' mapping.")

    quest_ids, checksums = _collect_quest_ids_and_checksums(pack_dir)
    pack["quests"] = quest_ids

    checksum_doc = pack.get("checksums")
    if not isinstance(checksum_doc, dict):
        checksum_doc = {}
        pack["checksums"] = checksum_doc
    checksum_doc["algo"] = "sha256"
    checksum_doc["files"] = checksums

    new_text = yaml.safe_dump(doc, sort_keys=False)
    changed = new_text != old_text
    if changed:
        pack_file.write_text(new_text, encoding="utf-8", newline="\n")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update quest list and checksum map for a quest pack."
    )
    parser.add_argument(
        "pack_dir",
        type=Path,
        help="Path to pack directory (example: quests/packs/wellness.core.v0).",
    )
    args = parser.parse_args(argv)

    try:
        pack_dir = args.pack_dir.resolve()
        changed = update_pack(pack_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    status = "Updated" if changed else "No changes"
    print(f"{status}: {pack_dir / 'pack.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
