"""S14b.2 — observable iteration cap (CT-2) + per-role limits + consumers.

C1 tests against the real ``run_session`` / ``drive_session`` composition
roots. Paths covered (plan P-matrix):
  P8      sequential top-check break → post-loop signal            (T10)
  P9      parallel last-batch truncation → post-loop signal        (T11)
  P10     mid-batch truncation + following batch → post-loop       (T12)
  P-exact exact budget fit → NO signal                             (T13)
  T15/T16 loader + default resolution (see test_inner_loop_runtime_limits.py)
  T17     drive_session console emit (iteration_cap OutputEvent)   (added in S12)
  T18     ConsoleRenderer/quiet renderer                           (added in S12)
Kill-check target: the post-loop StopInfo/log.append construction in
``fa.inner_loop.loop.run_session`` — not the consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _echo_spec(permission: str) -> ToolSpec:
    """A do-nothing tool. ``permission="read"`` → parallelizable; "workspace" → sequential."""

    def _handler(params: Mapping[str, Any]) -> ToolResult:
        return ToolResult(summary=f"echo {params.get('text', '')}", result=dict(params))

    return ToolSpec(
        name=f"echo_{permission}",
        description=f"Echo tool with permission={permission}.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=_handler,
        permission=permission,  # type: ignore[arg-type]  # literal from param
    )


def _state(tmp_path: Path) -> SessionState:
    return SessionState(workspace_root=tmp_path, run_id="t-cap", log=EventLog(tmp_path / "events.jsonl"))


def _stop_rows(state: SessionState) -> list[Any]:
    assert state.log is not None
    return [row for row in state.log.read_all() if row.kind == "run_stopped"]


def _calls(names: list[str], params: dict[str, object] | None = None) -> tuple[ToolCall, ...]:
    base = params if params is not None else {"text": "x"}
    return tuple(ToolCall(name=n, params=dict(base), call_id=f"tc-{i}") for i, n in enumerate(names))


# ── P8: sequential top-check break ─────────────────────────────────────────


def test_cap_p8_sequential_emits_stop_and_event(tmp_path: Path) -> None:
    """10 sequential calls, cap 3 → 3 results, stop.point=="iteration_cap", one run_stopped row."""
    registry = ToolRegistry()
    spec = _echo_spec("workspace")
    registry.register(spec)
    state = _state(tmp_path)

    result = run_session(
        _calls([spec.name] * 10),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )

    assert len(result) == 3
    assert result.stop is not None
    assert result.stop.point == "iteration_cap"
    assert "used 3 of 3" in result.stop.reason
    rows = _stop_rows(state)
    assert len(rows) == 1
    content = rows[0].content
    assert content["point"] == "iteration_cap"
    assert content["used"] == 3
    assert content["limit"] == 3
    assert content["profile"] == "coder"
    assert str(content["reason"]).startswith("iteration_cap")


# ── P9: parallel last-batch truncation (the path the v2.1 plan missed) ─────


def test_cap_p9_parallel_truncation_emits(tmp_path: Path) -> None:
    """3 parallel-safe calls, cap 2 → single batch truncated; loop exits naturally; post-loop site fires."""
    registry = ToolRegistry()
    spec = _echo_spec("read")
    registry.register(spec)
    state = _state(tmp_path)

    result = run_session(
        _calls([spec.name] * 3),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=2),
    )

    assert len(result) == 2
    assert result.stop is not None and result.stop.point == "iteration_cap"
    assert "used 2 of 2" in result.stop.reason
    rows = _stop_rows(state)
    assert len(rows) == 1
    assert rows[0].content["used"] == 2


# ── P10: mid-batch truncation + a following batch ──────────────────────────


def test_cap_p10_truncation_then_next_batch_break(tmp_path: Path) -> None:
    """Parallel batch of 3 truncated to 2, then one sequential call queued → top-check breaks; signal fires."""
    registry = ToolRegistry()
    read_spec = _echo_spec("read")
    seq_spec = _echo_spec("workspace")
    registry.register(read_spec)
    registry.register(seq_spec)
    state = _state(tmp_path)

    names = [read_spec.name, read_spec.name, read_spec.name, seq_spec.name]
    result = run_session(
        _calls(names),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=2),
    )

    assert len(result) == 2
    assert result.stop is not None and result.stop.point == "iteration_cap"
    assert len(_stop_rows(state)) == 1


# ── P-exact: budget consumed exactly → NO signal ───────────────────────────


def test_cap_exact_fit_emits_nothing(tmp_path: Path) -> None:
    """3 calls, cap 3 → everything ran; nothing was skipped; no stop, no run_stopped row."""
    registry = ToolRegistry()
    spec = _echo_spec("workspace")
    registry.register(spec)
    state = _state(tmp_path)

    result = run_session(
        _calls([spec.name] * 3),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )

    assert len(result) == 3
    assert result.stop is None
    assert _stop_rows(state) == []


# ── P-exact also holds on the parallel path ────────────────────────────────


def test_cap_exact_fit_parallel_no_signal(tmp_path: Path) -> None:
    """3 parallel-safe calls, cap 3 → batch not truncated; no signal."""
    registry = ToolRegistry()
    spec = _echo_spec("read")
    registry.register(spec)
    state = _state(tmp_path)

    result = run_session(
        _calls([spec.name] * 3),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )

    assert len(result) == 3
    assert result.stop is None
    assert _stop_rows(state) == []


# ── Guard denial wins over cap signal (stop is None guard) ─────────────────


def test_cap_signal_never_overwrites_guard_denial(tmp_path: Path) -> None:
    """A guard denial sets stop BEFORE the post-loop site; the cap signal must not overwrite it."""
    from fa.inner_loop.hooks.base import Decision, GuardMiddleware, HookPayload, LifecyclePoint

    class DenyAfter(GuardMiddleware):
        attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

        def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
            return Decision.deny("test denial")

    registry = ToolRegistry()
    spec = _echo_spec("workspace")
    registry.register(spec)
    state = _state(tmp_path)
    hooks = HookRegistry()
    hooks.register(DenyAfter())

    result = run_session(
        _calls([spec.name] * 5),
        registry=registry,
        hooks=hooks,
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )

    # Denial fired on the first call → stop is the guard's stop, not iteration_cap.
    assert result.stop is not None
    assert result.stop.point == LifecyclePoint.AFTER_TOOL_EXEC.value
    rows = _stop_rows(state)
    assert rows and rows[-1].content.get("reason") == "test denial"
    assert not any(str(r.content.get("point")) == "iteration_cap" for r in rows)


# ── S12 consumers: console signal (T17) + renderer (T18) ───────────────────


def test_drive_session_emits_iteration_cap_and_continues(tmp_path: Path) -> None:
    """C1: cap-hit turn emits OutputEvent(type="iteration_cap") to the bus; session continues (turns==2, exit 0)."""
    from fa.inner_loop.coder_loop import drive_session
    from fa.inner_loop.hooks import SandboxHook
    from fa.output import EventBus, OutputEvent
    from tests.test_coder_loop import (
        FakeProvider,
        _make_chain,
        _make_response,
        _registry_with_dummy_tool,
    )

    tool_calls = tuple(
        {
            "id": f"tc-{i}",
            "type": "function",
            "function": {"name": "echo", "arguments": f'{{"text": "call-{i}"}}'},
        }
        for i in range(3)
    )
    provider = FakeProvider(
        [
            _make_response(finish_reason="tool_calls", tool_calls=tool_calls),
            _make_response(text="done", finish_reason="stop"),
        ]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _state(tmp_path)

    events: list[OutputEvent] = []

    class _Capture:
        def on_event(self, e: OutputEvent) -> None:
            events.append(e)

    bus = EventBus()
    bus.add(_Capture())

    outcome = drive_session(
        "cap",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        limits=RuntimeLimits(max_iterations=2),
        output=bus,
    )

    assert outcome.exit_code == 0
    assert outcome.turns == 2  # session CONTINUED after the cap turn — no break
    cap_events = [e for e in events if e.type == "iteration_cap"]
    assert len(cap_events) == 1
    assert cap_events[0].data["profile"] == "coder"
    assert "used 2 of 2" in str(cap_events[0].data["reason"])


def test_console_renderer_prints_cap_line_and_quiet_stays_silent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C0: ConsoleRenderer renders the iteration_cap line; QuietRenderer emits nothing (quiet contract)."""
    from fa.output import ConsoleRenderer, OutputEvent, QuietRenderer

    event = OutputEvent(
        type="iteration_cap",
        data={
            "point": "iteration_cap",
            "reason": "iteration_cap: per-turn iteration limit (2) exceeded — used 2 of 2",
            "profile": "coder",
        },
    )

    console = ConsoleRenderer(detail="standard", no_color=True)
    console.on_event(event)
    out = capsys.readouterr()
    assert "iteration cap reached" in out.err
    assert "used 2 of 2" in out.err

    quiet = QuietRenderer()
    quiet.on_event(event)
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == ""


# ── S13: end-to-end seam (config file → loader → resolver → run_session cap) ─


def test_cmd_run_applies_config_per_role_limit_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2: a real ``fa run`` (`_cmd_run`) with ``~/.fa/config.yaml`` setting
    ``max_iterations_coder: 2`` caps the turn at 2 and writes the explicit
    ``run_stopped`` row — proving the loader → resolver → loop seam end-to-end."""
    import json as _json

    from tests.test_cli import (
        _FAKE_MODELS_YAML,
        _TEST_SECRETS,
        _ScriptedTransport,
        _stop_body,
        _tool_call,
        _tool_calls_body,
    )
    from tests.test_s7_cli_run_paths import _run_args

    home = tmp_path / "home"
    fa_dir = home / ".fa"
    fa_dir.mkdir(parents=True)
    config_path = fa_dir / "config.yaml"
    config_path.write_text(
        "runtime_limits:\n  max_iterations: 6\n  max_iterations_coder: 2\n",
        encoding="utf-8",
    )
    # DEFAULT_CONFIG_PATH is an import-time constant (fa.config module level);
    # the loader resolves it at call time, so patch the module global used by
    # runtime_limits.py (S14b.2 DI: load_runtime_limits_from_path(path=None)).
    import fa.inner_loop.runtime_limits as _rtl

    monkeypatch.setattr(_rtl, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", "0")
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)

    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    args = _run_args(tmp_path, config, "s14b2-seam")

    from fa.cli import _cmd_run

    bodies = [
        _tool_calls_body(
            _tool_call("tc-1", "fs_read_file", '{"path": "a.txt"}'),
            _tool_call("tc-2", "fs_read_file", '{"path": "a.txt"}'),
            _tool_call("tc-3", "fs_read_file", '{"path": "a.txt"}'),
        ),
        _stop_body("done"),
    ]
    code = _cmd_run(args, transport=_ScriptedTransport(bodies), secrets=_TEST_SECRETS)
    assert code == 0

    events_path = home / ".fa" / "session-log" / "s14b2-seam" / "events.jsonl"
    assert events_path.exists(), f"missing events mirror: {events_path}"
    rows = [_json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    stops = [r for r in rows if r.get("kind") == "run_stopped"]
    assert stops, "expected a run_stopped row (cap applied via config seam)"
    content = stops[-1]["content"]
    assert content["point"] == "iteration_cap"
    assert content["used"] == 2  # config max_iterations_coder: 2, three calls requested
    assert content["limit"] == 2
    assert content["profile"] == "coder"
    assert str(content["reason"]).startswith("iteration_cap")
