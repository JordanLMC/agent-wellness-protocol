from __future__ import annotations

import os
from pathlib import Path


def discover_repo_root(start: Path | None = None) -> Path:
    start_path = (start or Path.cwd()).resolve()
    for candidate in [start_path, *start_path.parents]:
        if (candidate / "docs").is_dir() and (candidate / "quests").is_dir():
            return candidate
    raise FileNotFoundError("Could not find repository root with /docs and /quests.")


def agent_home() -> Path:
    configured = os.environ.get("AGENTWELLNESS_HOME") or os.environ.get("CLAWSPA_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".agentwellness"


def ensure_home_dirs(base: Path) -> dict[str, Path]:
    profiles = base / "profiles"
    state = base / "state"
    proofs = base / "proofs"
    plans = state / "plans"
    for path in (base, profiles, state, proofs, plans):
        path.mkdir(parents=True, exist_ok=True)
    return {"base": base, "profiles": profiles, "state": state, "proofs": proofs, "plans": plans}
