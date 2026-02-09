from __future__ import annotations

from pathlib import Path


def discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "docs").is_dir() and (candidate / "quests").is_dir():
            return candidate
    raise FileNotFoundError("Could not discover repository root containing /docs and /quests.")


def load_canonical_pillars(docs_dir: Path) -> set[str]:
    pillars_file = docs_dir / "PILLARS.md"
    if not pillars_file.exists():
        raise FileNotFoundError(f"Missing pillars document: {pillars_file}")

    pillars: set[str] = set()
    for raw_line in pillars_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            value = line[2:].strip()
            if value:
                pillars.add(value)
    return pillars
