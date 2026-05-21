from __future__ import annotations

import json
from pathlib import Path

from _pytest.capture import CaptureFixture

from fa.cli import build_parser


def test_cli_help_contains_project_name() -> None:
    help_text = build_parser().format_help()

    assert "First-Agent" in help_text


def test_cli_has_inner_loop_smoke_command() -> None:
    help_text = build_parser().format_help()

    assert "inner-loop-smoke" in help_text


def test_inner_loop_smoke_command_runs(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# sample\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(
        [
            "inner-loop-smoke",
            "--workspace",
            str(tmp_path),
            "--output",
            "nested dir/smoke; no-inject.txt",
        ]
    )

    exit_code = args.func(args)

    assert exit_code == 0
    assert (tmp_path / "nested dir" / "smoke; no-inject.txt").exists()
    assert "OK: bash exited 0" in capsys.readouterr().out


def test_inner_loop_smoke_wires_learning_observer(tmp_path: Path) -> None:
    """LearningObserver is registered in the smoke CLI and writes a
    discovery entry for a successful tool result (fs.read_file produces
    a non-empty summary → discovery entry for ``fs/read_file`` key).
    """

    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["inner-loop-smoke", "--workspace", str(tmp_path)])

    exit_code = args.func(args)

    assert exit_code == 0
    codebase_map = tmp_path / "knowledge" / "trace" / "codebase_map.json"
    assert codebase_map.exists(), "LearningObserver did not create codebase_map.json"

    data = json.loads(codebase_map.read_text(encoding="utf-8"))
    assert "fs/read_file" in data
