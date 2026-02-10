#!/usr/bin/env python3
"""Scan tracked text files for bidi/invisible Unicode control characters."""

from __future__ import annotations

import argparse
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Iterable


EXPLICIT_SUSPICIOUS_CODEPOINTS = {
    0x00AD,  # SOFT HYPHEN
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x200E,  # LEFT-TO-RIGHT MARK
    0x200F,  # RIGHT-TO-LEFT MARK
    0x202A,  # LEFT-TO-RIGHT EMBEDDING
    0x202B,  # RIGHT-TO-LEFT EMBEDDING
    0x202C,  # POP DIRECTIONAL FORMATTING
    0x202D,  # LEFT-TO-RIGHT OVERRIDE
    0x202E,  # RIGHT-TO-LEFT OVERRIDE
    0x2060,  # WORD JOINER
    0x2066,  # LEFT-TO-RIGHT ISOLATE
    0x2067,  # RIGHT-TO-LEFT ISOLATE
    0x2068,  # FIRST STRONG ISOLATE
    0x2069,  # POP DIRECTIONAL ISOLATE
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE/BOM
}

TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".json"}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".pytest_tmp",
    "node_modules",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".class",
    ".jar",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
}


def is_suspicious_char(char: str) -> bool:
    codepoint = ord(char)
    return codepoint in EXPLICIT_SUSPICIOUS_CODEPOINTS or unicodedata.category(char) == "Cf"


def escaped_snippet(line: str, column: int, radius: int = 24) -> str:
    start = max(0, column - 1 - radius)
    end = min(len(line), column - 1 + radius)
    snippet = line[start:end]
    escaped = snippet.encode("unicode_escape").decode("ascii")
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(line) else ""
    return f"{prefix}{escaped}{suffix}"


def find_controls(text: str) -> list[tuple[int, int, str, str]]:
    findings: list[tuple[int, int, str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for column_number, char in enumerate(line, start=1):
            if is_suspicious_char(char):
                findings.append((line_number, column_number, char, escaped_snippet(line, column_number)))
    return findings


def is_text_target(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    return path.suffix.lower() not in SKIP_SUFFIXES


def is_probably_utf8_text(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def git_tracked_files(root: Path) -> list[Path]:
    try:
        toplevel_result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if toplevel_result.returncode != 0:
        return []
    repo_root = Path(toplevel_result.stdout.strip())
    if not repo_root.exists():
        return []

    try:
        ls_result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if ls_result.returncode != 0:
        return []

    files: list[Path] = []
    for raw_rel in ls_result.stdout.decode("utf-8", errors="ignore").split("\x00"):
        if not raw_rel:
            continue
        candidate = (repo_root / raw_rel).resolve()
        if not candidate.exists() or not candidate.is_file():
            continue
        if root.is_dir() and not candidate.is_relative_to(root):
            continue
        files.append(candidate)
    return files


def walk_filesystem(root: Path) -> list[Path]:
    if root.is_file():
        return [root.resolve()]
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path.resolve())
    return files


def iter_candidate_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        candidate = root.resolve()
        if is_text_target(candidate):
            yield candidate
        return

    tracked = git_tracked_files(root)
    paths = tracked if tracked else walk_filesystem(root)
    for path in sorted(set(paths)):
        if is_text_target(path):
            yield path


def display_path(path: Path, root: Path) -> str:
    if root.is_file():
        return str(path)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for bidi/invisible Unicode control characters.")
    parser.add_argument("path", nargs="?", default=".", help="Path to scan (default: current directory).")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2

    violations = 0
    for path in iter_candidate_files(root):
        if not is_probably_utf8_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line, col, char, snippet in find_controls(text):
            codepoint = ord(char)
            name = unicodedata.name(char, "UNKNOWN")
            rel = display_path(path, root)
            print(f"{rel}:{line}:{col} U+{codepoint:04X} {name} snippet='{snippet}'")
            violations += 1

    if violations:
        print(f"Found {violations} suspicious Unicode control character(s).", file=sys.stderr)
        return 1
    print("No suspicious Unicode controls found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
