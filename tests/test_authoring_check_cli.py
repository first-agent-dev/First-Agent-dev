"""Tests for the ``fa authoring-check`` CLI wiring (src/fa/cli.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _pytest.capture import CaptureFixture

# Add scripts/ to path for check_protected_paths import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_protected_paths import is_protected

from fa.cli import build_parser


def _make_workspace(root: Path) -> None:
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")


def test_help_lists_authoring_check() -> None:
    assert "authoring-check" in build_parser().format_help()


def test_authoring_check_json_on_clean_tree(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    _make_workspace(tmp_path)
    args = build_parser().parse_args(
        ["authoring-check", "--workspace", str(tmp_path), "--output", "json"]
    )
    exit_code = args.func(args)
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kernel_version"] == "0.1"
    assert payload["diagnostics"] == []


def test_authoring_check_text_default(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    _make_workspace(tmp_path)
    args = build_parser().parse_args(["authoring-check", "--workspace", str(tmp_path)])
    exit_code = args.func(args)
    assert exit_code == 0
    assert "kernel 0.1" in capsys.readouterr().out


def test_authoring_check_rejects_non_workspace(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    # No knowledge/llms.txt marker -> exit 2 (no walk-up; AGENTS.md).
    args = build_parser().parse_args(["authoring-check", "--workspace", str(tmp_path)])
    exit_code = args.func(args)
    assert exit_code == 2
    assert "not a First-Agent workspace" in capsys.readouterr().err


def test_authoring_check_with_manifest(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    _make_workspace(tmp_path)
    manifest = tmp_path / "session.toml"
    manifest.write_text('[kernel]\nversion = "0.1"\n', encoding="utf-8")
    args = build_parser().parse_args(
        [
            "authoring-check",
            "--workspace",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--output",
            "json",
        ]
    )
    exit_code = args.func(args)
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_hash"] is not None


def test_is_protected_catches_symlink_to_prefix(tmp_path: Path) -> None:
    """Regression test for symlink-to-prefix bypass (ADR-11-I7)."""
    # Create a temp repo structure with protected prefix
    src_dir = tmp_path / "src" / "fa" / "authoring_rules"
    src_dir.mkdir(parents=True)
    (src_dir / "exports.py").write_text("# protected file\n", encoding="utf-8")

    # Create a symlink pointing to the protected file
    alias = tmp_path / "alias.py"
    # Windows requires admin rights for symlinks by default; skip if not available
    try:
        alias.symlink_to(src_dir / "exports.py")
    except (OSError, NotImplementedError):
        # Skip test on systems without symlink support
        return

    # The symlink should be detected as protected
    assert is_protected("alias.py", tmp_path) is True
