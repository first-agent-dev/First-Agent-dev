from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _pytest.capture import CaptureFixture

from fa.cli import _cmd_run, _cmd_stats, build_parser
from fa.inner_loop.session_db import SessionDatabase
from fa.providers import SecretStore
from fa.providers.base import TransportResponse

# Injected via the _cmd_run(secrets=...) seam (ADR-12): tests supply keys through
# the private store instead of os.environ, matching production's file-only model.
_TEST_SECRETS = SecretStore({"TEST_FA_RUN_KEY": "sk-test-x"})

# Use the interpreter running pytest when spawning bash commands, so tests work
# on minimal environments that only expose ``python3`` (e.g. stock Ubuntu) as
# well as venvs where ``python`` exists. Canonical pytest idiom for
# interpreter-agnostic subprocess tests (``sys.executable`` is absolute, so
# PATH resolution does not matter).
_PYTHON = sys.executable


@pytest.fixture(autouse=True)
def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate these tests from ambient egress-proxy env (ADR-12).

    The whole file exercises the legacy (non-proxy) ``_cmd_run`` path. When the
    suite runs INSIDE the agent container, ``FA_EGRESS_PROXY_URL`` /
    ``FA_PROXY_TOKEN_FILE`` are set in the environment, which would silently flip
    ``_cmd_run`` into proxy mode and break expectations such as the legacy
    "configuration error" message. Clear them so the test outcome does not depend
    on where the suite runs. Proxy-mode behaviour is covered by
    ``tests/test_proxy_wiring_cli.py`` / ``tests/test_secret_isolation_cli.py``.
    """
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)


def test_cli_help_contains_project_name() -> None:
    help_text = build_parser().format_help()

    assert "First-Agent" in help_text


def test_cli_has_inner_loop_smoke_command() -> None:
    help_text = build_parser().format_help()

    assert "inner-loop-smoke" in help_text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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
        "Second smoke run accumulated a duplicate gotcha section — the deterministic-clock + dedup pair is broken."
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
        f"R-8 canon-root invariant violated: parent directory for gotchas.md does not exist at {canon_gotchas_dir}."
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
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
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
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, transport_retries
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


def _tool_call(call_id: str, name: str, arguments: str) -> Mapping[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


def _tool_calls_body(*tool_calls: Mapping[str, Any], text: str = "") -> Mapping[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                    "tool_calls": list(tool_calls),
                },
                "finish_reason": "tool_calls",
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
        task_pos=None,
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
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    transport = _ScriptedTransport([_stop_body("hello world")])
    args = _make_run_args(workspace=tmp_path, config=config)

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "OK:" in captured
    assert "stopped_by_llm" in captured
    assert "hello world" in captured
    assert len(transport.calls) == 1
    # The driver injects the system prompt as the first message.
    messages = transport.calls[0]["messages"]
    assert messages[0]["role"] == "system"


@pytest.mark.parametrize(
    ("debug_env", "capture_expected"),
    [("1", True), ("0", False)],
    ids=["enabled", "disabled"],
)
def test_fa_run_debug_body_capture_follows_exact_env_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    debug_env: str,
    capture_expected: bool,
) -> None:
    """C2 producer proof for ``_cmd_run`` → provider → Transport.post.

    Matrix: ``FA_DEBUG_LLM_BODIES=1`` / ``0`` with ``detail=debug`` in both
    cases. Root: shipped ``_cmd_run``. Kill-check: removing the production
    ``wrap_transport_for_debug_bodies(...)`` call in ``src/fa/cli.py`` makes
    the enabled case fail because no ``llm_bodies.jsonl`` row is produced.
    The disabled case proves ``--detail debug`` is not the capture gate.
    """
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", debug_env)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    run_id = f"debug-{debug_env}"
    args = _make_run_args(workspace=tmp_path, config=config, run_id=run_id)
    args.detail = "debug"
    secret = _TEST_SECRETS["TEST_FA_RUN_KEY"]
    transport = _ScriptedTransport([_stop_body(f"captured {secret}")])

    assert _cmd_run(args, transport=transport, secrets=_TEST_SECRETS) == 0

    body_path = home / ".fa" / "session-log" / run_id / "llm_bodies.jsonl"
    if not capture_expected:
        assert not body_path.exists()
        return

    raw_body = body_path.read_text(encoding="utf-8")
    assert secret not in raw_body
    assert "***REDACTED***" in raw_body
    rows = [json.loads(line) for line in raw_body.splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "llm_body"
    assert rows[0]["logical_call_id"]
    assert rows[0]["provider"] == "openrouter"
    assert rows[0]["slug"] == "test/model"
    assert rows[0]["attempt_index"] == 0
    assert rows[0]["request_body"]["model"] == "test/model"
    assert rows[0]["response_body"]["choices"][0]["message"]["content"] == "captured ***REDACTED***"


def test_fa_run_reports_session_db_initialization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """C2: authority init failure is reported before provider execution."""
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    def fail_event_log(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise RuntimeError("session_db_init_failed: disk unavailable")

    monkeypatch.setattr("fa.cli.EventLog", fail_event_log)
    transport = _ScriptedTransport([_stop_body("must not call provider")])

    exit_code = _cmd_run(
        _make_run_args(workspace=tmp_path, config=config, run_id="db-failure"),
        transport=transport,
        secrets=_TEST_SECRETS,
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "session database not available" in captured.err
    assert str(home / ".fa" / "session-log" / "db-failure" / "session.db") in captured.err
    assert "session_db_init_failed" in captured.err
    assert transport.calls == []


def test_fa_run_rejects_empty_task(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    args = _make_run_args(workspace=tmp_path, config=tmp_path / "models.yaml", task=" \n\t")

    exit_code = _cmd_run(args, transport=_ScriptedTransport([]))

    assert exit_code == 2
    assert "task must be non-empty" in capsys.readouterr().err


def test_fa_run_rejects_unsafe_run_id(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    args = _make_run_args(workspace=tmp_path, config=tmp_path / "models.yaml", run_id="../escape")

    exit_code = _cmd_run(args, transport=_ScriptedTransport([]))

    assert exit_code == 2
    assert "--run-id" in capsys.readouterr().err


def test_fa_run_configuration_error_returns_two_without_traceback(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    args = _make_run_args(workspace=tmp_path, config=config)

    exit_code = _cmd_run(args, transport=_ScriptedTransport([]))

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "configuration error" in captured.err
    assert "TEST_FA_RUN_KEY" in captured.err
    assert "Traceback" not in captured.err


def test_fa_run_returns_two_when_role_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    transport = _ScriptedTransport([])
    args = _make_run_args(workspace=tmp_path, config=config, role="planner")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 2
    assert "planner" in capsys.readouterr().err


def test_fa_run_writes_events_jsonl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _ScriptedTransport([_stop_body("ok")])
    args = _make_run_args(workspace=tmp_path, config=config, run_id="audit-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    events = home / ".fa" / "session-log" / "audit-run" / "events.jsonl"
    assert events.exists()
    kinds = [json.loads(line)["kind"] for line in events.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert "user_msg" in kinds
    assert "model_msg" in kinds


def test_fa_run_hits_turn_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
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

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 1
    assert "iteration_cap" in capsys.readouterr().out


def test_fa_run_registers_pr_prepare_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    transport = _ScriptedTransport([_stop_body("ok")])
    args = _make_run_args(workspace=tmp_path, config=config)

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    tools = transport.calls[0]["tools"]
    names = [tool["function"]["name"] for tool in tools]
    for expected_name in ["fs.read_file", "fs.run_bash", "fs.write_file", "pr.prepare"]:
        assert expected_name in names
    prepare = next(tool for tool in tools if tool["function"]["name"] == "pr.prepare")
    assert "pr_draft.md" in prepare["function"]["description"]
    assert prepare["function"]["parameters"]["required"] == ["intent", "invariant"]


def test_fa_run_denies_first_mutation_until_pr_prepare_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call("tc-write", "fs.write_file", '{"path": "src/fa/x.py", "content": "x\\n"}'),
                _tool_call("tc-prepare", "pr.prepare", '{"intent": "CHORE", "invariant": "n/a"}'),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    assert not (tmp_path / "src" / "fa" / "x.py").exists()
    draft_path = home / ".fa" / "session-log" / "test-run" / "pr_draft.md"
    assert draft_path.read_text(encoding="utf-8") == "INTENT: CHORE\nINVARIANT: n/a\n"
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    write_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-write"
    )
    assert write_result["content"]["error"]["code"] == "hook_deny"
    assert "call `pr.prepare`" in write_result["content"]["error"]["message"]


def test_fa_run_clears_stale_pr_draft_on_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    stale = home / ".fa" / "session-log" / "reuse-run" / "pr_draft.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("INTENT: FIX\nCLASS: REPAIR\nINVARIANT: Affects: stale\n", encoding="utf-8")
    transport = _ScriptedTransport([_stop_body("ok")])
    args = _make_run_args(workspace=tmp_path, config=config, run_id="reuse-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    assert not stale.exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_run_verify_only_bash_allowed_before_pr_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call(
                    "tc-bash",
                    "fs.run_bash",
                    json.dumps({"command": f"{_PYTHON} -m pytest --version"}),
                ),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bash_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-bash"
    )
    assert bash_result["content"]["ok"] is True


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_run_repo_write_bash_requires_pr_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call(
                    "tc-bash",
                    "fs.run_bash",
                    json.dumps({"command": "mkdir -p src/fa && printf 'x\\n' > src/fa/x.py"}),
                ),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    assert not (tmp_path / "src" / "fa" / "x.py").exists()
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bash_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-bash"
    )
    assert bash_result["content"]["error"]["code"] == "hook_deny"
    assert "call `pr.prepare`" in bash_result["content"]["error"]["message"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_run_opaque_exec_bash_requires_pr_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    command = 'python -c "import pathlib; pathlib.Path("src/fa/x.py").write_text("x")"'
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call("tc-bash", "fs.run_bash", json.dumps({"command": command})),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    assert not (tmp_path / "src" / "fa" / "x.py").exists()
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bash_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-bash"
    )
    assert bash_result["content"]["error"]["code"] == "hook_deny"
    assert "call `pr.prepare`" in bash_result["content"]["error"]["message"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_run_opaque_exec_bash_allowed_after_pr_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    command = f"{_PYTHON} -c \"open('opaque.py', 'w').write('x')\""
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call(
                    "tc-prepare",
                    "pr.prepare",
                    '{"intent": "CHORE", "invariant": "n/a"}',
                ),
                _tool_call("tc-bash", "fs.run_bash", json.dumps({"command": command})),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    draft_path = home / ".fa" / "session-log" / "test-run" / "pr_draft.md"
    assert draft_path.read_text(encoding="utf-8") == "INTENT: CHORE\nINVARIANT: n/a\n"
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bash_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-bash"
    )
    assert bash_result["content"]["ok"] is True
    assert (tmp_path / "opaque.py").read_text(encoding="utf-8") == "x"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_run_repo_write_bash_allowed_after_pr_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _ScriptedTransport(
        [
            _tool_calls_body(
                _tool_call(
                    "tc-prepare",
                    "pr.prepare",
                    '{"intent": "IMPLEMENT", "invariant": "Implements: src/fa/x.py"}',
                ),
                _tool_call(
                    "tc-bash",
                    "fs.run_bash",
                    json.dumps({"command": "mkdir -p src/fa && printf 'x\n' > src/fa/x.py"}),
                ),
            ),
            _stop_body("done"),
        ]
    )
    args = _make_run_args(workspace=tmp_path, config=config, run_id="test-run")

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    assert (tmp_path / "src" / "fa" / "x.py").read_text(encoding="utf-8") == "x\n"
    draft_path = home / ".fa" / "session-log" / "test-run" / "pr_draft.md"
    assert draft_path.read_text(encoding="utf-8") == "INTENT: IMPLEMENT\nINVARIANT: Implements: src/fa/x.py\n"
    events = [
        json.loads(line)
        for line in (home / ".fa" / "session-log" / "test-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bash_result = next(
        event for event in events if event["kind"] == "tool_result" and event["tool_call_id"] == "tc-bash"
    )
    assert bash_result["content"]["ok"] is True


def test_fa_run_system_prompt_mentions_pr_prepare_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    transport = _ScriptedTransport([_stop_body("ok")])
    args = _make_run_args(workspace=tmp_path, config=config)

    exit_code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)

    assert exit_code == 0
    system_message = transport.calls[0]["messages"][0]["content"]
    assert "pr.prepare" in system_message
    assert "Before your first mutation" in system_message


def test_fa_run_session_manager_creates_and_attaches_with_fresh_run_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 producer proof: real ``_cmd_run`` uses SessionManager + one session DB.

    Matrix: default new session → explicit attach. Kill-check: removing the
    SessionManager call from ``_cmd_run`` must make the manifest/DB assertions
    fail. Provider I/O is deterministic and mocked at Transport only.
    """
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    first_args = _make_run_args(workspace=tmp_path, config=config, run_id="")
    first_args.session_id = None
    first_args.resume = False
    assert _cmd_run(first_args, transport=_ScriptedTransport([_stop_body("first")]), secrets=_TEST_SECRETS) == 0

    manifests = sorted((home / ".fa" / "sessions").glob("*/manifest.json"))
    assert len(manifests) == 1
    session_id = json.loads(manifests[0].read_text(encoding="utf-8"))["session_id"]
    run_dirs = sorted(d for d in (home / ".fa" / "session-log").iterdir() if d.is_dir())
    assert len(run_dirs) == 1
    first_run_id = run_dirs[0].name

    second_args = _make_run_args(workspace=tmp_path, config=config, run_id="")
    second_args.session_id = session_id
    second_args.resume = False
    assert _cmd_run(second_args, transport=_ScriptedTransport([_stop_body("second")]), secrets=_TEST_SECRETS) == 0

    run_dirs = sorted(d for d in (home / ".fa" / "session-log").iterdir() if d.is_dir())
    assert len(run_dirs) == 2
    second_run_id = next(d.name for d in run_dirs if d.name != first_run_id)
    assert second_run_id != first_run_id

    db_path = home / ".fa" / "sessions" / session_id / "session.db"
    db = SessionDatabase.open_existing(db_path, session_id=session_id)
    assert db.read_event_rows(run_id=first_run_id)
    assert db.read_event_rows(run_id=second_run_id)
    assert all(row["session_id"] == session_id for row in db.read_event_rows())


def test_fa_stats_reads_current_session_db_and_rejects_legacy_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """C2/C3: stats is DB-only for current format and legacy is unsupported."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    session_id = "session-stats"
    run_id = "run-stats"
    session_dir = home / ".fa" / "sessions" / session_id
    session_dir.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (session_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "session_id": session_id,
                "workspace_path": str(workspace),
                "session_db_path": str(session_dir / "session.db"),
                "created_at": "2026-06-21T14:00:00Z",
                "last_used_at": "2026-06-21T14:00:00Z",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    db = SessionDatabase(session_dir / "session.db", session_id=session_id)
    db.reserve_run_binding(run_id, "2026-06-21T14:00:00Z")
    db.append_event_row(
        {
            "event_id": "ev-1",
            "session_id": session_id,
            "ts": "2026-06-21T14:00:00Z",
            "run_id": run_id,
            "harness_id": "fa-inner-loop@0.1.0",
            "actor": "runtime",
            "kind": "session_summary",
            "content": {"n_turns": 1, "input_tokens": 1, "output_tokens": 1},
        }
    )
    args = argparse.Namespace(
        run_id=run_id,
        session_id=session_id,
        since=None,
        output="json",
        workspace=workspace,
        dead_zones=False,
        global_history=False,
    )
    assert _cmd_stats(args) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["run_id"] == run_id

    legacy_home = tmp_path / "legacy-home"
    monkeypatch.setenv("HOME", str(legacy_home))
    legacy_dir = legacy_home / ".fa" / "session-log" / "old-run"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")
    legacy_args = argparse.Namespace(
        run_id=None,
        session_id=None,
        since=None,
        output="json",
        workspace=workspace,
        dead_zones=False,
        global_history=False,
    )
    assert _cmd_stats(legacy_args) == 2
    assert "legacy_trace_unsupported" in capsys.readouterr().err
    assert not (legacy_dir / "session.db").exists()


def test_fa_run_resume_without_session_id_fails_before_provider(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    transport = _ScriptedTransport([_stop_body("must not run")])
    args = _make_run_args(workspace=tmp_path, config=config, run_id="resume-run")
    args.session_id = None
    args.resume = True

    assert _cmd_run(args, transport=transport, secrets=_TEST_SECRETS) == 2
    assert transport.calls == []
    assert "requires --session-id" in capsys.readouterr().err
