from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _pytest.capture import CaptureFixture

from fa.cli import _cmd_run, build_parser
from fa.providers.base import TransportResponse


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


def test_invariant_adr7_r8_canon_root_is_knowledge_trace(tmp_path: Path) -> None:
    """INVARIANT (ADR-7 §Sub-amendment 2026-05-21b): R-8 LearningObserver
    writes its filesystem-canon artifacts under ``<workspace>/knowledge/trace/``
    — both in the smoke CLI and in the T-2 real runtime, because that is
    the cross-session memory path the rest of the system reads from.

    Layer-2 worked example (named-invariant test, see
    ``knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md``).
    The test name encodes the assertion so that any future agent
    grepping for «R-8 canon» / «ADR-7 sub-amendment 2026-05-21b» /
    «knowledge/trace» finds this test as the mechanical answer to
    «where is R-8 supposed to write?».

    If the canon needs to move, the relocation MUST land together
    with an ADR amendment in the same PR — at which point the
    expected paths in this test are updated as part of the visible
    architectural decision (RELAX), not as a silent WORKAROUND.

    Complementary to ``test_inner_loop_smoke_wires_learning_observer``
    (integration test bundling several assertions): this test holds
    one invariant per ADR amendment, named-after the amendment.
    """

    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["inner-loop-smoke", "--workspace", str(tmp_path)])

    args.func(args)

    canon_map = tmp_path / "knowledge" / "trace" / "codebase_map.json"
    canon_gotchas_dir = tmp_path / "knowledge" / "trace"
    assert canon_map.exists(), (
        f"R-8 canon-root invariant violated: expected {canon_map} after "
        "`fa inner-loop-smoke`. Spec: ADR-7 §Sub-amendment 2026-05-21b "
        "«single canon root». See "
        "knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md."
    )
    assert canon_gotchas_dir.is_dir(), (
        "R-8 canon-root invariant violated: parent directory for "
        f"gotchas.md does not exist at {canon_gotchas_dir}."
    )
    relocated = tmp_path / ".fa" / "knowledge" / "trace" / "codebase_map.json"
    assert not relocated.exists(), (
        "R-8 canon-root invariant violated: canon was relocated under "
        ".fa/ (a previously-rejected WORKAROUND). See "
        "knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md "
        "and the worked-history note in ADR-7 §Sub-amendment 2026-05-21b."
    )


# ---------------------------------------------------------------------------
# `fa run` tests — exercise the LLM-driven driver behind the CLI seam.
# ---------------------------------------------------------------------------


_FAKE_MODELS_YAML = """\
coder:
  model: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      slug: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""


class _ScriptedTransport:
    """Test transport that returns canned ``TransportResponse`` objects in order.

    The driver only cares about the canonical
    :class:`fa.providers.base.ResponseInfo` shape; the adapter
    (``OpenAICompatProvider``) does the body → ResponseInfo
    normalisation. We feed adapter-shaped bodies via ``TransportResponse``
    so the production code path is exercised end-to-end.
    """

    def __init__(self, bodies: list[Mapping[str, Any]]) -> None:
        self._bodies = list(bodies)
        self.calls: list[Mapping[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        self.calls.append(json_body)
        if not self._bodies:
            return TransportResponse(status=503, body={})
        body = self._bodies.pop(0)
        return TransportResponse(status=200, body=body)


def _stop_body(text: str = "done") -> Mapping[str, Any]:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": text, "tool_calls": []},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


def _make_run_args(
    *,
    workspace: Path,
    config: Path,
    task: str = "do nothing",
    role: str = "coder",
    max_turns: int = 4,
    run_id: str = "test-run",
) -> argparse.Namespace:
    return argparse.Namespace(
        task=task,
        role=role,
        config=config,
        workspace=workspace,
        max_turns=max_turns,
        run_id=run_id,
    )


def test_fa_run_help_contains_run_command() -> None:
    help_text = build_parser().format_help()
    assert "run" in help_text


def test_fa_run_returns_zero_on_clean_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "k")
    transport = _ScriptedTransport([_stop_body("hello world")])
    args = _make_run_args(workspace=tmp_path, config=config)

    exit_code = _cmd_run(args, transport=transport)

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "OK:" in captured
    assert "stopped_by_llm" in captured
    assert "hello world" in captured
    assert len(transport.calls) == 1
    # The driver injects the system prompt as the first message.
    messages = transport.calls[0]["messages"]
    assert messages[0]["role"] == "system"


def test_fa_run_returns_two_when_role_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "k")
    transport = _ScriptedTransport([])
    args = _make_run_args(workspace=tmp_path, config=config, role="planner")

    exit_code = _cmd_run(args, transport=transport)

    assert exit_code == 2
    assert "planner" in capsys.readouterr().err


def test_fa_run_writes_events_jsonl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "k")
    transport = _ScriptedTransport([_stop_body("ok")])
    args = _make_run_args(workspace=tmp_path, config=config, run_id="audit-run")

    exit_code = _cmd_run(args, transport=transport)

    assert exit_code == 0
    events = tmp_path / ".fa" / "runs" / "audit-run" / "events.jsonl"
    assert events.exists()
    kinds = [
        json.loads(line)["kind"]
        for line in events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "user_msg" in kinds
    assert "model_msg" in kinds


def test_fa_run_hits_turn_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "k")
    # Tool call that yields invalid_params (no such tool registered),
    # making the LLM loop indefinitely without ever signalling stop.
    looping_body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc-loop",
                            "type": "function",
                            "function": {
                                "name": "fs.read_file",
                                "arguments": '{"path": "missing.txt"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    transport = _ScriptedTransport([looping_body, looping_body])
    args = _make_run_args(workspace=tmp_path, config=config, max_turns=2)

    exit_code = _cmd_run(args, transport=transport)

    assert exit_code == 1
    assert "iteration_cap" in capsys.readouterr().out
