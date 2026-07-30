"""S5.4 — both mutating tools must enforce one pre-write conflict contract.

Contract under test (S5-CT4)
----------------------------
``fs.write_file`` and ``fs.edit_file`` behave identically at the substrate
boundary: a conflicting Blackboard entry denies the mutation **before** the file
is touched, and the denial names *which* precondition failed.

Current behaviour this replaces (source-verified)
-------------------------------------------------
``write_file`` calls ``_check_conflict`` at line 196. ``edit_file`` has no
conflict check at all — it goes straight from ``_find_fuzzy`` to
``path.write_text`` — despite its own module docstring claiming *"Blackboard
helpers shared with write_file via extracted module to avoid duplication"*.
That shared module did not exist. The most-used edit path therefore bypassed
the substrate's core guarantee entirely (gap V15/V17).

Design constraints proven before writing these tests
----------------------------------------------------
* ``cli.py:972`` ships ``FeatureFlags(blackboard_enabled=False)`` for
  ``fa inner-loop-smoke``. A deliberately disabled substrate must keep
  permitting writes, or this slice breaks a shipped command (S5-P24).
* Tools are routinely invoked with **no session bound** (measured: 5 write_file
  and 2 edit_file calls across the suite). ``fs.write_file``/``fs.edit_file``
  are both in ``_NEVER_PARALLEL_TOOLS``, so this is never a lost-contextvar
  race — it is legitimate direct use. Denying it would be a gratuitous
  behaviour break, so "no session" stays permitted (S5-P24).
* The anchor check must stay primary in ``edit_file``: aider's SEARCH/REPLACE
  ladder is the correctness mechanism, and the conflict check is additive to
  it, not a replacement.

Test classes: C1 (tool behaviour on the real substrate), C3 (failure paths).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.feature_flags import FeatureFlags
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.state import SessionState
from fa.inner_loop.tools.edit_file import build_edit_file_tool
from fa.inner_loop.tools.write_file import build_write_file_tool

TARGET = "target.txt"
ORIGINAL = "original content\n"

# Each tool is exercised through the same scenarios via a uniform adapter:
# (build the ToolSpec, params that mutate TARGET, the content that results).
ToolFactory = Callable[[Path], ToolSpec]


def _write_params() -> Mapping[str, object]:
    return {"path": TARGET, "content": "replacement\n"}


def _edit_params() -> Mapping[str, object]:
    return {"path": TARGET, "old_string": "original", "new_string": "replacement"}


# (factory, params, expected file content after a permitted mutation)
TOOLS: dict[str, tuple[ToolFactory, Callable[[], Mapping[str, object]], str]] = {
    "write_file": (build_write_file_tool, _write_params, "replacement\n"),
    "edit_file": (build_edit_file_tool, _edit_params, "replacement content\n"),
}


@pytest.fixture(params=sorted(TOOLS), ids=sorted(TOOLS))
def tool_case(request: pytest.FixtureRequest) -> tuple[ToolFactory, Callable[[], Mapping[str, object]], str]:
    """Both mutating tools run through one parametrised case so they cannot drift."""
    return TOOLS[request.param]


def _seed_target(workspace: Path) -> None:
    """edit_file requires an existing file; write_file tolerates one."""
    (workspace / TARGET).write_text(ORIGINAL, encoding="utf-8")


def _run(
    tool_case: tuple[ToolFactory, Callable[[], Mapping[str, object]], str],
    workspace: Path,
    state: SessionState | None,
) -> ToolResult:
    factory, params, _expected = tool_case
    tool = factory(workspace)
    if state is None:
        return tool.handler(params())
    token = set_current_session(state)
    try:
        return tool.handler(params())
    finally:
        reset_current_session(token)


def _conflicting_entry_from_other_writer(state: SessionState, workspace: Path) -> None:
    """Write a TARGET-claiming entry as a *different* run (post-S5.4.1 semantics)."""
    other = Blackboard(
        workspace / ".fa" / "blackboard",
        session_db=state.session_db,
        run_id="run-other-agent",
        session_id=state.session_id,
    )
    other.write(
        BlackboardEntry.create(
            id="other-agent-claim",
            type="file_version",
            payload={"path": TARGET},
            read_set=[],
            write_set=[TARGET],
            assumptions=[],
            version_dependencies={"base_commit": "unknown"},
        )
    )


# ---------------------------------------------------------------------------
# S5-P7 — the symmetry contract
# ---------------------------------------------------------------------------


def test_conflict_denies_mutation(tool_case: Any, tmp_path: Path) -> None:
    """C1 (S5-P7): a conflicting entry denies BOTH tools before the write.

    Kill-check target: remove either tool's conflict call site.
    """
    _seed_target(tmp_path)
    state = SessionState(workspace_root=tmp_path, run_id="run-under-test")
    _conflicting_entry_from_other_writer(state, tmp_path)

    result = _run(tool_case, tmp_path, state)

    assert result.error is not None, "conflicting entry did not deny the mutation"
    assert result.error.code == "conflict_detected", f"unexpected code {result.error.code}"
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == ORIGINAL, (
        "the file was modified despite the denial — the check must run BEFORE the write"
    )


# ---------------------------------------------------------------------------
# S5-R3 / S5-P8 — the positive case: the fix must not degrade into "deny all"
# ---------------------------------------------------------------------------


def test_no_conflict_allows_write(tool_case: Any, tmp_path: Path) -> None:
    """C1 (S5-R3): with a clean Blackboard, legitimate mutations still succeed."""
    _seed_target(tmp_path)
    state = SessionState(workspace_root=tmp_path, run_id="run-clean")

    result = _run(tool_case, tmp_path, state)

    assert result.error is None, f"legitimate mutation denied: {result.error}"
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == tool_case[2]


def test_repeated_mutation_by_same_writer_allowed(tool_case: Any, tmp_path: Path) -> None:
    """C1: iterative editing — the S5.4.1 guarantee must hold through both tools.

    Guards the interaction between this slice and S5.4.1: propagating the
    conflict check to ``edit_file`` must not resurrect the Q18 self-conflict on
    the most-used edit path.
    """
    _seed_target(tmp_path)
    state = SessionState(workspace_root=tmp_path, run_id="run-iterative")
    factory, _params, _expected = tool_case
    tool = factory(tmp_path)

    token = set_current_session(state)
    try:
        if tool.name == "fs.write_file":
            results = [tool.handler({"path": TARGET, "content": f"v{i}\n"}) for i in range(3)]
            expected = "v2\n"
        else:
            results = [
                tool.handler({"path": TARGET, "old_string": src, "new_string": dst})
                for src, dst in (("original", "first"), ("first", "second"), ("second", "third"))
            ]
            expected = "third content\n"
    finally:
        reset_current_session(token)

    codes = [r.error.code if r.error is not None else "ok" for r in results]
    assert codes == ["ok", "ok", "ok"], f"same-writer sequential mutations denied: {codes}"
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == expected


# ---------------------------------------------------------------------------
# S5-P24 — a deliberately disabled or absent substrate must not deny
# ---------------------------------------------------------------------------


def test_blackboard_disabled_still_allows_write(tool_case: Any, tmp_path: Path) -> None:
    """C1 (S5-P24): ``blackboard_enabled=False`` is a supported configuration.

    ``cli.py:972`` uses exactly this for the shipped ``fa inner-loop-smoke``
    entrypoint. Disabling the substrate deliberately is not the same as it
    failing, and must not be treated as one.
    """
    _seed_target(tmp_path)
    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-bb-off",
        feature_flags=FeatureFlags(blackboard_enabled=False),
    )
    assert state.blackboard is None, "precondition: the flag must actually disable the Blackboard"

    result = _run(tool_case, tmp_path, state)

    assert result.error is None, f"disabled Blackboard denied a write: {result.error}"
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == tool_case[2]


def test_no_session_bound_still_allows_write(tool_case: Any, tmp_path: Path) -> None:
    """C1 (S5-P24): direct tool use with no session bound stays permitted.

    Measured across the suite: 5 ``write_file`` and 2 ``edit_file`` invocations
    run with no session in the contextvar. Both tools are in
    ``_NEVER_PARALLEL_TOOLS``, so this is never a lost-contextvar race in the
    runtime — it is legitimate direct use, and denying it would break callers
    for no safety gain.
    """
    _seed_target(tmp_path)

    result = _run(tool_case, tmp_path, None)

    assert result.error is None, f"session-less invocation denied: {result.error}"
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == tool_case[2]


# ---------------------------------------------------------------------------
# S5-P8 / S5-P25 — failure paths must be attributable
# ---------------------------------------------------------------------------


def test_blackboard_read_failure_denies_and_names_precondition(tool_case: Any, tmp_path: Path) -> None:
    """C3 (S5-P8 + S5-P25): an unreadable Blackboard denies, and says why.

    Fail-closed is the ADR-16 I-6.3 posture: an unguarded write is a silent
    correctness hole, a denied write is a loud diagnosable one. The denial must
    name the failed precondition rather than emitting a generic refusal, so an
    operator can tell "the substrate is broken" from "you have a real conflict".

    Kill-check target: swallow the Blackboard error and return None (the old
    ``allowing write`` path), or collapse the code into ``conflict_detected``.
    """
    _seed_target(tmp_path)
    state = SessionState(workspace_root=tmp_path, run_id="run-bb-broken")
    assert state.blackboard is not None

    class _ExplodingBlackboard:
        root = tmp_path / ".fa" / "blackboard"

        def detect_conflict(self, _entry: object) -> list[object]:
            raise RuntimeError("blackboard_query_failed: disk on fire")

        def write(self, _entry: object) -> None:
            raise RuntimeError("blackboard_write_failed: disk on fire")

    # Structural stand-in: check_mutation_allowed only touches .root and
    # .detect_conflict. Typing it as Blackboard would require constructing a
    # real one and then breaking it, which is a less direct test of "the
    # substrate is present but raises".
    state.blackboard = _ExplodingBlackboard()  # type: ignore[assignment]

    result = _run(tool_case, tmp_path, state)

    assert result.error is not None, "a failing Blackboard was treated as permission to write"
    assert result.error.code == "blackboard_unavailable", (
        f"denial must name the failed precondition, got {result.error.code!r}"
    )
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == ORIGINAL, "file mutated despite denial"


def test_foreign_workspace_blackboard_is_ignored(tool_case: Any, tmp_path: Path) -> None:
    """C3 (S5-P8): a Blackboard belonging to another workspace must not deny.

    Leaked-contextvar protection. An entry claiming ``target.txt`` in a
    *different* workspace says nothing about this workspace's file, so it must
    neither deny the write nor be consulted as authority.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    foreign = tmp_path / "other-ws"
    foreign.mkdir()
    _seed_target(workspace)

    state = SessionState(workspace_root=workspace, run_id="run-leak")
    foreign_bb = Blackboard(
        foreign / ".fa" / "blackboard",
        session_db=state.session_db,
        run_id="run-foreign",
        session_id=state.session_id,
    )
    foreign_bb.write(
        BlackboardEntry.create(
            id="foreign-claim",
            type="file_version",
            payload={"path": TARGET},
            read_set=[],
            write_set=[TARGET],
            assumptions=[],
            version_dependencies={"base_commit": "unknown"},
        )
    )
    state.blackboard = foreign_bb

    result = _run(tool_case, workspace, state)

    assert result.error is None, f"foreign-workspace Blackboard denied a local write: {result.error}"
    assert (workspace / TARGET).read_text(encoding="utf-8") == tool_case[2]


# ---------------------------------------------------------------------------
# Anchor primacy — the conflict check is additive, not a replacement
# ---------------------------------------------------------------------------


def test_edit_file_anchor_failure_still_reported(tmp_path: Path) -> None:
    """C1: a missing anchor still fails as ``edit_failed``, not as a conflict.

    ``edit_file``'s fuzzy SEARCH ladder is its correctness mechanism (aider's
    model). Adding a conflict check must not mask or reorder it: an edit whose
    ``old_string`` does not match is a bad edit regardless of the Blackboard.
    """
    _seed_target(tmp_path)
    state = SessionState(workspace_root=tmp_path, run_id="run-anchor")
    tool = build_edit_file_tool(tmp_path)

    token = set_current_session(state)
    try:
        result = tool.handler({"path": TARGET, "old_string": "text that does not appear", "new_string": "x"})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "edit_failed", (
        f"anchor failure was reported as {result.error.code!r}; the anchor check must stay primary"
    )
    assert (tmp_path / TARGET).read_text(encoding="utf-8") == ORIGINAL
