#!/usr/bin/env python3
"""Scan repository text files for bidi/invisible Unicode control characters."""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path


SUSPICIOUS_CODEPOINTS = {
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


def find_controls(text: str) -> list[tuple[int, int, str]]:
    findings: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for column_number, char in enumerate(line, start=1):
            if ord(char) in SUSPICIOUS_CODEPOINTS:
                findings.append((line_number, column_number, char))
    return findings


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
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


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file():
            rel_parts = path.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for bidi/invisible Unicode control characters.")
    parser.add_argument("path", nargs="?", default=".", help="Path to scan (default: current directory).")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2

    violations = 0
    for path in iter_files(root):
        if not is_probably_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line, col, char in find_controls(text):
            codepoint = ord(char)
            name = unicodedata.name(char, "UNKNOWN")
            rel = str(path.relative_to(root)) if root.is_dir() else str(path)
            print(f"{rel}:{line}:{col} U+{codepoint:04X} {name}")
            violations += 1

    if violations:
        print(f"Found {violations} suspicious Unicode control character(s).", file=sys.stderr)
        return 1
    print("No suspicious Unicode controls found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
