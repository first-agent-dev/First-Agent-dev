from __future__ import annotations

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
