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
    path-keyed discovery entry for each successful tool call.

    Asserts:
    - canon root is ``<workspace>/.fa/knowledge/trace/`` (BUG-1 fix:
      live workspace stays untouched by smoke).
    - discovery key is path-keyed for ``fs.*`` tools and call-id-keyed
      for ``fs.run_bash`` (BUG-2 fix: a flat tool-name key collapsed
      every call onto a single slot).
    """

    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["inner-loop-smoke", "--workspace", str(tmp_path)])

    exit_code = args.func(args)

    assert exit_code == 0
    # Live workspace MUST stay clean — the canon root for smoke is
    # under ``.fa/`` (covered by ``.gitignore``).
    assert not (tmp_path / "knowledge" / "trace" / "codebase_map.json").exists()
    codebase_map = tmp_path / ".fa" / "knowledge" / "trace" / "codebase_map.json"
    assert codebase_map.exists(), "LearningObserver did not create codebase_map.json"

    data = json.loads(codebase_map.read_text(encoding="utf-8"))
    # Path-keyed: a second call against a different ``path`` no longer
    # overwrites the first.
    assert "fs/read_file/README.md" in data
    assert "fs/write_file/.fa/inner-loop-smoke.txt" in data
    # ``fs.run_bash`` has no ``path`` param — falls back to call_id.
    assert "fs/run_bash/tc-bash" in data


def test_inner_loop_smoke_records_gotcha_on_tool_failure(tmp_path: Path) -> None:
    """LearningObserver appends to ``gotchas.md`` when a tool fails.

    Pointing ``--input`` at a non-existent file forces ``fs.read_file``
    to return ``read_failed``; the observer's failure branch must call
    ``record_gotcha`` so the failure is durable under
    ``.fa/knowledge/trace/gotchas.md`` (TEST-GAP-1 fix — the success-only
    test above never exercised this code path).
    """

    parser = build_parser()
    args = parser.parse_args(
        [
            "inner-loop-smoke",
            "--workspace",
            str(tmp_path),
            "--input",
            "does-not-exist.md",
        ]
    )

    exit_code = args.func(args)

    # At least one tool failed (the read) — smoke CLI returns 1.
    assert exit_code == 1
    gotchas = tmp_path / ".fa" / "knowledge" / "trace" / "gotchas.md"
    assert gotchas.exists(), "LearningObserver did not create gotchas.md on failure"
    body = gotchas.read_text(encoding="utf-8")
    assert "fs.read_file failed" in body
    assert "does-not-exist.md" in body
