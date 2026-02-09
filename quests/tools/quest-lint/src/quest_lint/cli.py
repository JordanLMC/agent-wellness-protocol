from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .linter import findings_to_json, findings_to_text, lint_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint ClawSpa quest packs and quest files.")
    parser.add_argument("path", help="Path to scan recursively for *.quest.yaml files.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit non-zero when WARN findings are present.",
    )
    args = parser.parse_args()

    findings = lint_path(Path(args.path))
    has_error = any(item.severity == "ERROR" for item in findings)
    has_warn = any(item.severity == "WARN" for item in findings)

    if args.format == "json":
        print(findings_to_json(findings))
    else:
        print(findings_to_text(findings))

    if has_error:
        return 1
    if args.fail_on_warn and has_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
