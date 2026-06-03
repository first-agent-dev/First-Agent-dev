"""Tests for the ``fa authoring-check`` CLI wiring (src/fa/cli.py)."""

from __future__ import annotations

import json
from pathlib import Path

from _pytest.capture import CaptureFixture

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
