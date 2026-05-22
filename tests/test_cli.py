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


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SEED_BASELINE = _REPO_ROOT / "knowledge" / "trace" / "codebase_map.json"


def test_inner_loop_smoke_wires_learning_observer(tmp_path: Path) -> None:
    """LearningObserver is registered in the smoke CLI and writes
    path-keyed discovery entries to the canonical ``knowledge/trace/``
    root with a fixed-clock timestamp.

    Asserts (ADR-7 §Sub-amendment 2026-05-21b «single canon root» +
    «deterministic-clock injection» + «path-keyed discovery key»):

    - canon root is ``<workspace>/knowledge/trace/`` (the same path
      the T-2 real runtime will use; the earlier ``.fa/`` relocation
      was rejected 2026-05-22 as a spec-bypassing workaround).
    - discovery key is path-keyed for ``fs.*`` tools and call-id-keyed
      for ``fs.run_bash`` (BUG-2 fix: a flat tool-name key collapsed
      every call onto a single slot).
    - every ``recorded_at`` equals ``2026-05-21T00:00:00Z`` (fixed-
      clock injection makes the artifact byte-stable across runs).
    """

    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["inner-loop-smoke", "--workspace", str(tmp_path)])

    exit_code = args.func(args)

    assert exit_code == 0
    # The ``.fa/`` relocation is gone — the canon root is the durable
    # cross-session artifact path.
    assert not (tmp_path / ".fa" / "knowledge" / "trace" / "codebase_map.json").exists()
    codebase_map = tmp_path / "knowledge" / "trace" / "codebase_map.json"
    assert codebase_map.exists(), "LearningObserver did not create codebase_map.json"

    data = json.loads(codebase_map.read_text(encoding="utf-8"))
    # Path-keyed: a second call against a different ``path`` no longer
    # overwrites the first.
    assert "fs/read_file/README.md" in data
    assert "fs/write_file/.fa/inner-loop-smoke.txt" in data
    # ``fs.run_bash`` has no ``path`` param — falls back to call_id.
    assert "fs/run_bash/tc-bash" in data
    for entry in data.values():
        assert entry["recorded_at"] == "2026-05-21T00:00:00Z"


def test_inner_loop_smoke_canon_snapshot_matches_seed_baseline(tmp_path: Path) -> None:
    """Snapshot regression: smoke output equals the seed baseline
    ``knowledge/trace/codebase_map.json`` byte-for-byte.

    Pairs with the ADR-7 §Sub-amendment 2026-05-21b «seed baseline +
    snapshot» rule: any future change that breaks artifact stability
    (new smoke tool wired, key scheme change, summary string change,
    timestamp anchor change) fails this test loudly instead of
    silently dirtying the live ``knowledge/trace/`` after every run.
    Updating the test requires updating the seed baseline in the
    same PR — an explicit, visible architectural decision.
    """

    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["inner-loop-smoke", "--workspace", str(tmp_path)])

    exit_code = args.func(args)

    assert exit_code == 0
    smoke_canon = tmp_path / "knowledge" / "trace" / "codebase_map.json"
    assert smoke_canon.exists()
    expected = _SEED_BASELINE.read_text(encoding="utf-8")
    actual = smoke_canon.read_text(encoding="utf-8")
    assert actual == expected, (
        "Smoke output diverged from the seed baseline at "
        f"{_SEED_BASELINE}. If this is intentional (new tool wired, "
        "summary string changed, etc.), update the baseline in the "
        "same PR as the code change and document it in ADR-7 "
        "§Sub-amendment 2026-05-21b."
    )


def test_inner_loop_smoke_records_gotcha_on_tool_failure(tmp_path: Path) -> None:
    """LearningObserver appends to ``gotchas.md`` when a tool fails.

    Pointing ``--input`` at a non-existent file forces ``fs.read_file``
    to return ``read_failed``; the observer's failure branch must call
    ``record_gotcha`` so the failure is durable under
    ``knowledge/trace/gotchas.md`` at the canonical root
    (TEST-GAP-1 fix — the success-only test above never exercised
    this code path).
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
    gotchas = tmp_path / "knowledge" / "trace" / "gotchas.md"
    assert gotchas.exists(), "LearningObserver did not create gotchas.md on failure"
    body = gotchas.read_text(encoding="utf-8")
    assert "fs.read_file failed" in body
    assert "does-not-exist.md" in body
    assert "2026-05-21T00:00:00Z" in body


def test_inner_loop_smoke_gotcha_dedups_across_repeated_runs(tmp_path: Path) -> None:
    """Repeated smoke runs against the same failing tool call must
    not pile up byte-identical sections in ``gotchas.md``.

    Pairs with ADR-7 §Sub-amendment 2026-05-21b «gotchas dedup»
    rule: ``record_gotcha`` skips the append when the file already
    ends with this exact section. Fixed-clock injection on the smoke
    CLI makes the bytes identical across runs; live timestamps in T-2
    real runtime keep the append-only contract for genuine
    cross-session gotchas (covered by
    ``test_record_gotcha_dedups_only_consecutive_identical_sections``
    in ``tests/test_record_gotcha.py``).
    """

    parser = build_parser()
    argv = [
        "inner-loop-smoke",
        "--workspace",
        str(tmp_path),
        "--input",
        "does-not-exist.md",
    ]
    args = parser.parse_args(argv)

    assert args.func(args) == 1
    gotchas = tmp_path / "knowledge" / "trace" / "gotchas.md"
    after_first = gotchas.read_text(encoding="utf-8")

    args = parser.parse_args(argv)
    assert args.func(args) == 1
    after_second = gotchas.read_text(encoding="utf-8")

    assert after_second == after_first, (
        "Second smoke run accumulated a duplicate gotcha section — "
        "the deterministic-clock + dedup pair is broken."
    )
