from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "check_bidi.py"


def test_check_bidi_passes_clean_content(tmp_path: Path) -> None:
    (tmp_path / "clean.md").write_text("safe text only\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No suspicious Unicode controls found." in result.stdout


def test_check_bidi_fails_on_hidden_control(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("safe\u202Etext\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "U+202E" in result.stdout
    assert "\\u202e" in result.stdout


def test_check_bidi_fails_on_generic_cf_character(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("value: be\u2063careful\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "U+2063" in result.stdout


def test_check_bidi_scans_extensionless_text_files(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n# note\u202E\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Dockerfile" in result.stdout
    assert "U+202E" in result.stdout


def test_check_bidi_skips_binary_files_safely(tmp_path: Path) -> None:
    (tmp_path / "blob").write_bytes(b"\x00\x01\x02\x03\xE2\x80\xAE")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_script_path()), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No suspicious Unicode controls found." in result.stdout
