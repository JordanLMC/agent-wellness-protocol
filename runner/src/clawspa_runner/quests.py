from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quest_lint.linter import lint_path


@dataclass
class QuestRepository:
    repo_root: Path
    pack_root: Path

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "QuestRepository":
        return cls(repo_root=repo_root, pack_root=repo_root / "quests" / "packs")

    def lint(self) -> list[dict[str, str]]:
        findings = lint_path(self.pack_root, docs_dir=self.repo_root / "docs")
        return [f.to_dict() for f in findings]

    def load_all(self) -> dict[str, dict[str, Any]]:
        quests: dict[str, dict[str, Any]] = {}
        for file_path in sorted(self.pack_root.rglob("*.quest.yaml")):
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            quest = data.get("quest", {})
            quest_id = quest.get("id")
            if not isinstance(quest_id, str):
                continue
            normalized = dict(data)
            normalized["_file"] = str(file_path)
            normalized["_pack"] = self._pack_id_for_file(file_path)
            quests[quest_id] = normalized
        return quests

    def list_packs(self) -> list[dict[str, Any]]:
        packs: list[dict[str, Any]] = []
        for pack_file in sorted(self.pack_root.rglob("pack.yaml")):
            data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
            pack_obj = data.get("pack", {})
            packs.append(
                {
                    "id": pack_obj.get("id"),
                    "title": pack_obj.get("title"),
                    "version": pack_obj.get("version"),
                    "path": str(pack_file),
                }
            )
        return packs

    def get_pack(self, pack_id: str) -> dict[str, Any] | None:
        for pack_file in sorted(self.pack_root.rglob("pack.yaml")):
            data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
            pack_obj = data.get("pack", {})
            if pack_obj.get("id") == pack_id:
                return data
        return None

    def _pack_id_for_file(self, file_path: Path) -> str | None:
        for parent in [file_path.parent, *file_path.parents]:
            pack_file = parent / "pack.yaml"
            if pack_file.exists():
                data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
                pack_obj = data.get("pack", {})
                return pack_obj.get("id")
        return None
