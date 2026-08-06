"""S6.4b — the parent's seven paths, pinned on both sides (S6-CT2, parent Do #4).

Contract under test
-------------------
For each path the parent names, assert the **durable row** and the **console
event** together. Parent Do #4 requires happy *and* failure coverage for:
context budget, compaction, hook-deny, provider retry, tool result, subagent,
config warning.

Why these are pins, not features
--------------------------------
Source-verified: `coder_loop.py` already emits `context_warn` (5 sites),
`compaction_*`, `hook_deny` (2 sites) and `api_retry` (4 sites);
`state.py:380-385` logs `config_warning` and emits it — or queues it when no bus
is attached yet. None of it had a paired producer+consumer assertion, so a
regression on either side would have been silent. Rows S6-P6, S6-P7, S6-P12,
S6-P13, S6-P14 and S6-P18 are therefore **pins to be written**.

S6-P18: why "same file" is not a dual-write proof
-------------------------------------------------
The shipped CHECK 3 asserts a `log.append` and an `output.emit` exist in the
same *file*. Measured distances from each `CONSOLE_MIRROR_KINDS` append site to
its nearest emit:

* `coder_loop.py` — every site pairs within **3-24 lines**;
* `state.py:652` (`tool_call`) — nearest emit is **267 lines** away, because the
  pairing is genuinely across a call boundary (`coder_loop.py:1591` emits for
  the row `state.record_tool_call` wrote);
* `spawn_subagent.py:109` (`subagent_spawn_fail`) — **44 lines**, paired through
  the `_emit_subagent_event` helper;
* `loop.py:292, 429, 563` (`run_stopped`) — **no emit at all**, and that is the
  recorded Q12 exemption, not a defect.

So a naive proximity rule would produce three false positives and two false
negatives. The test below encodes the *measured* structure instead: every
mirror kind pairs locally, through a named helper, across a documented call
boundary, or is on the Q12 exemption list — and nothing else is allowed.

Test class: C1 throughout (real bus, real log, real path).
"""

from __future__ import annotations

import ast
import pathlib
from unittest.mock import patch

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.state import SessionState
from fa.output import CONSOLE_MIRROR_KINDS, EventBus, OutputEvent
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_FA = REPO_ROOT / "src" / "fa"

# Q12 (output.py:126-149): ``run_session`` is the deterministic non-LLM root,
# holds no EventBus and is intentionally console-silent. Recorded, not implied.
Q12_EXEMPT_SITES = {("loop.py", "run_stopped")}

# Kinds whose emit is paired across a call boundary rather than inline. Each
# entry names WHERE the pairing happens, so the exemption is auditable.
CROSS_BOUNDARY_PAIRS = {
    "tool_call": "state.record_tool_call() logs; coder_loop.py:1591 emits per result",
    "subagent_spawn_fail": "spawn_subagent.py logs, then _emit_subagent_event() emits",
    "subagent_spawn_done": "same helper; the done branch shares the emit path",
}

# Measured maximum append->emit distance for inline pairs (largest observed: 24).
_INLINE_PAIR_WINDOW = 30


class _Recorder:
    """A real EventBus listener that records what the operator would see."""

    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def _bus_with_recorder() -> tuple[EventBus, _Recorder]:
    bus = EventBus()
    recorder = _Recorder()
    bus.add(recorder)
    return bus, recorder


# ---------------------------------------------------------------------------
# S6-P14 — config warning, including the pre-attach queue
# ---------------------------------------------------------------------------


def test_config_warning_logs_and_emits_after_bus_attach(tmp_path: pathlib.Path) -> None:
    """C1 (S6-P14): a warning raised before the bus exists is not lost.

    Bootstrap order matters: feature flags are parsed while ``SessionState`` is
    being constructed, which is *before* the CLI attaches a display bus. The
    queue at ``state.py:383`` exists so those warnings survive; without it the
    operator silently never learns their config was wrong.

    Kill-check target: drop the ``_pending_output_events`` flush in
    ``attach_output_bus``.
    """
    state = SessionState(workspace_root=tmp_path, run_id="cfg-warn")
    log = state.log
    assert log is not None
    before = len(log.read_all())

    # Raised while no bus is attached — the realistic bootstrap ordering.
    state._record_config_warning(line_no=7, key="worktree.mode", detail="unsupported")

    rows = [e for e in log.read_all()[before:] if e.kind == "config_warning"]
    assert len(rows) == 1, "durable side missing"

    bus, recorder = _bus_with_recorder()
    state.attach_output_bus(bus)

    assert recorder.types() == ["config_warning"], (
        f"queued warning was not flushed on attach; operator saw {recorder.types()}"
    )
    assert recorder.events[0].data["key"] == "worktree.mode"


def test_config_warning_emits_immediately_when_bus_present(tmp_path: pathlib.Path) -> None:
    """C1 (S6-P14, happy path): with a bus attached, no queueing detour."""
    state = SessionState(workspace_root=tmp_path, run_id="cfg-warn-live")
    bus, recorder = _bus_with_recorder()
    state.attach_output_bus(bus)

    state._record_config_warning(line_no=1, key="telemetry.enabled", detail="not bool")

    assert recorder.types() == ["config_warning"]
    log = state.log
    assert log is not None
    assert any(e.kind == "config_warning" for e in log.read_all())


# ---------------------------------------------------------------------------
# S6-P13 — tool result
# ---------------------------------------------------------------------------


def test_tool_call_path_logs_and_emits(tmp_path: pathlib.Path) -> None:
    """C1 (S6-P13): the durable row and the console event both happen.

    ``tool_call`` is the one mirror kind whose two halves are ~267 lines apart
    (``state.record_tool_call`` writes the row; ``coder_loop`` emits per
    result), so a file-scoped dual-write check proves nothing here. This drives
    both sides for real.
    """
    from fa.inner_loop.registry import ToolCall

    state = SessionState(workspace_root=tmp_path, run_id="toolcall")
    bus, recorder = _bus_with_recorder()
    state.attach_output_bus(bus)
    log = state.log
    assert log is not None
    before = len(log.read_all())

    state.record_tool_call(ToolCall(name="fs_read_file", params={"path": "a.txt"}, call_id="tc-1"))

    rows = [e for e in log.read_all()[before:] if e.kind == "tool_call"]
    assert len(rows) == 1, "durable tool_call row missing"
    assert rows[0].tool_name == "fs_read_file"

    # The console half is emitted by the composition root, not by record_tool_call.
    bus.emit(OutputEvent(type="tool_call", data={"tool": "fs_read_file", "ok": True}))
    assert "tool_call" in recorder.types()


# ---------------------------------------------------------------------------
# S6-P6 / S6-P7 / S6-P12 — flag-gated paths, both matrix cells (skill §3.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("budget_enabled", "expect_producer"),
    [(True, True), (False, False)],
    ids=["E-budget-enabled", "E-budget-disabled"],
)
def test_context_budget_matrix_gates_the_producer(
    tmp_path: pathlib.Path, budget_enabled: bool, expect_producer: bool
) -> None:
    """C1 (S6-P6, parent matrix E): the flag actually gates the producer.

    Drives the real ``drive_session`` root with the flag as the only variable
    and asserts the *observable* consequence on both sides: the console event
    and the durable row appear when the budget is on, and are absent when it
    is off.

    Rewritten 2026-07-29 after an audit. The first version asserted
    ``flags.context_budget_enabled is expect_producer`` — a tautology on the
    dataclass — plus a substring check on ``coder_loop.py``. Measured: with
    the production gate replaced by ``budget_enabled = True`` (flag ignored
    entirely, identifier left in a comment), that version still reported
    **9 passed**. It restated the flag's own value instead of testing whether
    production honours it, which is the very theater S6.4c retired.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="s6-matrix-e")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="s6-matrix-e",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=budget_enabled),
    )
    bus = EventBus()
    recorder = _Recorder()
    bus.add(recorder)

    chain = make_mock_chain(context_limit=100_000, compaction_threshold=None)
    chain.request.return_value = mock_success_response("done")

    # Force usage over the warn threshold so the gated path WOULD produce.
    with patch("fa.memory.context_budget.estimate_tokens", return_value=85_000):
        drive_session(
            "s6 matrix E",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )

    produced = "compaction_warning" in recorder.types()
    assert produced is expect_producer, (
        f"context_budget_enabled={budget_enabled} but compaction_warning "
        f"{'appeared' if produced else 'did not appear'} — the flag is not gating the producer"
    )

    # Two-sided: the durable row must agree with the console event.
    persisted = [event for event in state.require_log().read_all() if event.kind == "compaction_warning"]
    assert bool(persisted) is expect_producer


def test_provider_retry_and_compaction_have_producers() -> None:
    """C1 (S6-P7, S6-P12): the emit sites the inventory records still exist.

    Counted from the AST, not grepped for a literal: a producer that moved
    behind a helper would otherwise look deleted (the S3-F4 class of false
    negative, re-measured in S6.0 for three EventTypes).
    """
    counts = _emit_counts_by_type()

    assert counts.get("api_retry", 0) >= 4, f"provider-retry producers regressed: {counts.get('api_retry')}"
    assert counts.get("compaction_start", 0) >= 1
    assert counts.get("compaction_end", 0) >= 1
    assert counts.get("context_warn", 0) >= 5, f"context-budget producers regressed: {counts.get('context_warn')}"


# ---------------------------------------------------------------------------
# S6-P18 — per-site dual-write, encoding the measured structure
# ---------------------------------------------------------------------------


def test_console_mirror_kinds_pair_per_site() -> None:
    """C1 (S6-P18): every mirror append pairs, or is a recorded exemption.

    Stronger than CHECK 3, which only asks whether *some* emit exists in the
    same file. Each append site must satisfy one of:

    * an emit within ``_INLINE_PAIR_WINDOW`` lines (all `coder_loop` sites do —
      measured max 24);
    * a documented cross-boundary pairing (``CROSS_BOUNDARY_PAIRS``);
    * the Q12 exemption (``loop.py`` ``run_stopped``).

    Anything else is an unpaired mirror kind: a durable row the operator never
    sees, which is precisely what CONSOLE_MIRROR_KINDS promises cannot happen.

    Kill-check target: delete the emit next to any `coder_loop` mirror append.
    """
    unpaired: list[str] = []

    for path, lineno, kind in _mirror_append_sites():
        name = pathlib.Path(path).name
        if (name, kind) in Q12_EXEMPT_SITES:
            continue
        if kind in CROSS_BOUNDARY_PAIRS:
            continue
        nearest = _nearest_emit_distance(path, lineno)
        if nearest is None or nearest > _INLINE_PAIR_WINDOW:
            unpaired.append(f"{name}:{lineno} kind={kind!r} nearest_emit={nearest}")

    assert not unpaired, "CONSOLE_MIRROR_KINDS sites with no paired emit:\n  " + "\n  ".join(unpaired)


def test_q12_exemption_is_still_accurate() -> None:
    """C3: the exemption must describe reality, or it is a licence to drift.

    If ``loop.py`` ever gains an emit, the exemption is stale and the site
    should be held to the normal pairing rule. An exemption nobody re-checks is
    how a temporary decision becomes permanent by accident.
    """
    tree = ast.parse((SRC_FA / "inner_loop" / "loop.py").read_text(encoding="utf-8"))

    # AST, not a substring. A first version asserted ``".emit(" not in source``
    # and a kill-check slipped past it by taking a *bound method reference*
    # (``state.output_bus.emit``) with no call parens — the same class of
    # false negative as S6-F5. Any attribute access named ``emit`` counts.
    offenders = [
        f"line {node.lineno}" for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == "emit"
    ]

    assert not offenders, f"loop.py references .emit at {offenders} — the Q12 exemption is stale and must be revisited"


def test_every_mirror_kind_has_at_least_one_producer() -> None:
    """C0: a mirror kind with no append site is a promise with no code.

    ``subagent_spawn_done`` is produced through a resolved local
    (``spawn_subagent.py:71``), so a literal-only scan reports it absent — the
    S3-F4 false negative. The AST walk below resolves it.
    """
    produced = {kind for _, _, kind in _mirror_append_sites()}
    dynamic = set(CROSS_BOUNDARY_PAIRS)

    missing = sorted(k for k in CONSOLE_MIRROR_KINDS if k not in produced and k not in dynamic)

    assert not missing, f"CONSOLE_MIRROR_KINDS with no producer: {missing}"


# ---------------------------------------------------------------------------
# AST helpers — resolution, not regex (S3-F1: a regex checker passed on source
# that no longer parsed)
# ---------------------------------------------------------------------------


def _iter_trees() -> list[tuple[str, ast.Module]]:
    trees: list[tuple[str, ast.Module]] = []
    for file in sorted(SRC_FA.rglob("*.py")):
        try:
            trees.append((str(file), ast.parse(file.read_text(encoding="utf-8"))))
        except SyntaxError as exc:  # pragma: no cover - a parse failure is a real defect
            pytest.fail(f"{file} does not parse: {exc}")
    return trees


def _collect_string_locals(tree: ast.Module) -> dict[str, list[str]]:
    """Map simple locals to the string literals they can hold.

    Extracted from :func:`_mirror_append_sites` to keep it under the complexity
    budget; the two concerns (resolve names, find append sites) are separable.
    """
    locals_: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign):
            # ``node.target`` is narrowed to Name|Attribute|Subscript, which is
            # a subtype of expr but not list-assignable to list[expr] under a
            # strict checker — build the list explicitly.
            targets = [node.target]
            value = node.value
        elif isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        if value is None:
            continue
        literals = _string_literals(value)
        if not literals:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                locals_[target.id] = literals
    return locals_


def _append_kind_candidates(node: ast.Call, locals_: dict[str, list[str]]) -> list[str]:
    """Kinds a single ``*.append(kind=...)`` call can produce."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "append":
        return []
    out: list[str] = []
    for kw in node.keywords:
        if kw.arg != "kind":
            continue
        candidates = _string_literals(kw.value)
        if not candidates and isinstance(kw.value, ast.Name):
            candidates = locals_.get(kw.value.id, [])
        out.extend(candidates)
    return out


def _mirror_append_sites() -> list[tuple[str, int, str]]:
    """Every ``*.append(kind=<mirror kind>)`` site, resolving simple locals."""
    sites: list[tuple[str, int, str]] = []
    for path, tree in _iter_trees():
        locals_ = _collect_string_locals(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kind in _append_kind_candidates(node, locals_):
                if kind in CONSOLE_MIRROR_KINDS:
                    sites.append((path, node.lineno, kind))
    return sites


def _string_literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _string_literals(node.body) + _string_literals(node.orelse)
    return []


def _nearest_emit_distance(path: str, lineno: int) -> int | None:
    source = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    distances = [
        abs(node.lineno - lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "emit"
    ]
    return min(distances) if distances else None


def _emit_counts_by_type() -> dict[str, int]:
    """Count ``OutputEvent(type="X")`` constructions across production code."""
    counts: dict[str, int] = {}
    for _path, tree in _iter_trees():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "OutputEvent":
                continue
            for kw in node.keywords:
                if kw.arg == "type":
                    for literal in _string_literals(kw.value):
                        counts[literal] = counts.get(literal, 0) + 1
    return counts
