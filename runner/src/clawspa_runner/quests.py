from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quest_lint.linter import lint_path


@dataclass
class QuestRepository:
    repo_root: Path
    pack_roots: list[Path]

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "QuestRepository":
        default_root = (repo_root / "quests" / "packs").resolve()
        roots: list[Path] = [default_root]
        seen = {default_root}

        raw_sources = os.environ.get("CLAWSPA_LOCAL_PACK_SOURCES", "").strip()
        if raw_sources:
            for raw in raw_sources.split(os.pathsep):
                candidate = Path(raw).expanduser().resolve()
                if not candidate.exists() or not candidate.is_dir():
                    continue
                if candidate in seen:
                    continue
                roots.append(candidate)
                seen.add(candidate)

        return cls(repo_root=repo_root, pack_roots=roots)

    @property
    def pack_root(self) -> Path:
        # Backwards-compatible alias used by existing call sites/tests.
        return self.pack_roots[0]

    def pack_sources(self) -> list[str]:
        return [str(root) for root in self.pack_roots]

    def lint(self) -> list[dict[str, str]]:
        docs_dir = self.repo_root / "docs"
        all_findings: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str, str, str]] = set()
        for root in self.pack_roots:
            if not root.exists():
                continue
            for finding in lint_path(root, docs_dir=docs_dir):
                as_dict = finding.to_dict()
                key = (
                    as_dict["rule_id"],
                    as_dict["severity"],
                    as_dict["file"],
                    as_dict["path"],
                    as_dict["message"],
                    as_dict["suggested_fix"],
                )
                if key in seen:
                    continue
                seen.add(key)
                all_findings.append(as_dict)
        all_findings.sort(key=lambda item: (item["severity"], item["file"], item["rule_id"], item["path"]))
        return all_findings

    def load_all(self) -> dict[str, dict[str, Any]]:
        quests: dict[str, dict[str, Any]] = {}
        for file_path in self._quest_files():
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            quest = data.get("quest", {})
            quest_id = quest.get("id")
            if not isinstance(quest_id, str):
                continue
            if quest_id in quests:
                # Deterministic first-wins behavior for duplicate IDs across sources.
                continue
            normalized = dict(data)
            normalized["_file"] = str(file_path)
            normalized["_pack"] = self._pack_id_for_file(file_path)
            quests[quest_id] = normalized
        return quests

    def list_packs(self) -> list[dict[str, Any]]:
        packs: list[dict[str, Any]] = []
        for pack_file in self._pack_files():
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
        packs.sort(key=lambda item: (str(item.get("id")), str(item.get("path"))))
        return packs

    def get_pack(self, pack_id: str) -> dict[str, Any] | None:
        for pack_file in self._pack_files():
            data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
            pack_obj = data.get("pack", {})
            if pack_obj.get("id") == pack_id:
                return data
        return None

    def _pack_files(self) -> list[Path]:
        files: list[Path] = []
        seen: set[Path] = set()
        for root in self.pack_roots:
            if not root.exists():
                continue
            for pack_file in sorted(root.rglob("pack.yaml")):
                resolved = pack_file.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                files.append(resolved)
        files.sort(key=lambda p: str(p))
        return files

    def _quest_files(self) -> list[Path]:
        files: list[Path] = []
        seen: set[Path] = set()
        for root in self.pack_roots:
            if not root.exists():
                continue
            for quest_file in sorted(root.rglob("*.quest.yaml")):
                resolved = quest_file.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                files.append(resolved)
        files.sort(key=lambda p: str(p))
        return files

    def _pack_id_for_file(self, file_path: Path) -> str | None:
        for parent in [file_path.parent, *file_path.parents]:
            pack_file = parent / "pack.yaml"
            if pack_file.exists():
                data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
                pack_obj = data.get("pack", {})
                return pack_obj.get("id")
        return None
