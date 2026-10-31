"""S10c.2 / Q35b — ``fa workflow``'s exit code reports the VERDICT (CT2).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10c-contract-and-posture-fixes.md``

**The contract this pins.** Every workflow mode returns 0 once its stages have
run, regardless of what the evaluator decided. That made
``fa workflow && deploy`` proceed on BLOCKED code, and any CI gate reading
``$?`` saw success. S8 recorded the fork as Q35a/Q35b and deliberately pinned
today's behaviour so a future change would be a visible diff; the operator
chose **Q35b**, and this module is the enforcement.

Exit codes after S10c.2:

* **0** — terminal ``FlowState.status == "DONE"`` (the eval accepted the work)
* **1** — any other terminal status (``FAILED`` / ``REPAIR_REQUIRED`` /
  ``REPLAN_REQUIRED``): the pipeline ran, the code was not accepted
* **2** — usage or configuration error, unchanged and deliberately distinct:
  a caller must be able to tell "I invoked this wrongly" from "the code was
  rejected"
* **3** — the code was accepted, but this invocation could not put the workspace
  back: the managed writer release was never confirmed (Q98, 2026-11-01). The
  verdict codes win over this one — a rejected run stays 1 — because the answer
  about the work is the more specific fact; the leak is always reported and
  recorded either way. **124** remains the deadline code from the controller.

**The authority is the persisted artifact, not a local flag.** The exit code is
derived from the same ``_read_back_terminal_state`` result that S8.7 uses for
``stop_reason``, so the two cannot drift apart.

Test class: **C2** (root is the shipped ``_cmd_workflow``; oracles are the exit
code plus the durable artifacts).
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any

import pytest

import fa.cli as fa_cli
from fa.cli import _cmd_workflow
from fa.execution.client import ExecutionRejectedError
from fa.inner_loop.workflow_artifacts import load_flow_state
from tests.test_cli import _TEST_SECRETS
from tests.test_cli_ergonomics import _RoleAwareTransport, _workflow_args
from tests.test_s8_workflow_controller import _global_history_row, _wf_env


def _status(home: Path, run_id: str) -> str:
    return load_flow_state(home / ".fa" / "session-log" / run_id / "flow_state.json").status


def test_s10c_workflow_pass_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10c.2 / CT2): an accepted run is exit 0.

    The positive control. Without it every "non-zero on rejection" assertion
    below is satisfiable by a command that can only fail.

    Oracle: exit 0 **and** terminal status ``DONE`` — asserting both is what
    ties the code to the verdict rather than to luck.
    Kill-check target: the ``== "DONE"`` comparison.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-pass", session_id=None)

    code = _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    assert code == 0
    assert _status(home, "wf-pass") == "DONE"


@pytest.mark.parametrize(
    ("verdict", "route", "expected_status", "run_id"),
    [
        ("BLOCKED", "blocked", "FAILED", "wf-blocked"),
        ("REPAIR_REQUIRED", "return_to_coder", "REPAIR_REQUIRED", "wf-repair"),
        ("REPLAN_REQUIRED", "return_to_planner", "REPLAN_REQUIRED", "wf-replan"),
    ],
)
def test_s10c_workflow_non_done_verdict_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verdict: str,
    route: str,
    expected_status: str,
    run_id: str,
) -> None:
    """C2 (S10c.2 / CT2 / GAP3): every non-``DONE`` terminal status is exit 1.

    Parametrised over all three rejection shapes rather than testing only
    BLOCKED: the mapping is a lookup over ``FlowStatus``
    (``_EVAL_VERDICT_TO_TERMINAL_STATUS``), and a single-case test would pass
    against an implementation that special-cased BLOCKED and let the other two
    keep returning 0.

    Oracle: exit **1** + the specific terminal status, so a case that reaches
    the right code via the wrong status still fails.
    Kill-check target: the ``0 if ... == "DONE" else 1`` derivation.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id=run_id, session_id=None)

    code = _cmd_workflow(args, transport=_RoleAwareTransport([(verdict, route)]), secrets=_TEST_SECRETS)

    assert code == 1, f"{verdict} must not report success"
    assert _status(home, run_id) == expected_status


def test_s10c_workflow_usage_error_still_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10c.2 / CT2 / P9): a usage error is still exit **2**, not 1.

    The 1-vs-2 split is the part of this contract most easily lost. "The code
    was rejected" and "you invoked this wrongly" are different operator
    situations with different fixes, and a derivation that collapsed
    ``result_code`` into the verdict branch would merge them.

    Oracle: exit 2 for an unreadable config.
    Kill-check target: the ``result_code != 0`` passthrough.
    """
    config, _home = _wf_env(tmp_path, monkeypatch)
    missing = tmp_path / "nope.yaml"
    args = _workflow_args(tmp_path, missing, run_id="wf-usage", session_id=None)

    code = _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    assert code == 2, "a configuration error must stay distinguishable from a rejected verdict"
    assert config.is_file()  # the fixture's config exists; the one we passed does not


def test_s10c_workflow_exit_code_matches_the_projected_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10c.2 / CT2): the ``global_history`` row records the SAME exit code.

    **This caught a real inconsistency during execution.** The aggregate row is
    built inside the export block from ``result_code``, while the process
    returned a value derived later — so a BLOCKED run briefly reported
    ``code == 1`` with ``row["exit_code"] == 0``. Two artifacts disagreeing
    about one run is precisely the class S8.7 existed to remove.

    The fix computes the exit code once, before the export, so both are the
    same number by construction.

    Oracle: process exit code == ``row["exit_code"]`` == 1, with
    ``stop_reason`` still semantic.
    Kill-check target: revert ``exit_code=exit_code`` to ``exit_code=result_code``
    in the ``SessionOutcome`` — this fails while the plain exit-code tests pass.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-row", session_id=None)

    code = _cmd_workflow(args, transport=_RoleAwareTransport([("BLOCKED", "blocked")]), secrets=_TEST_SECRETS)

    row: dict[str, Any] = _global_history_row(home)
    assert code == 1
    assert row["exit_code"] == code, "the projection must not disagree with the process about its own exit code"
    assert row["stop_reason"] == "workflow_failed"


def test_s10c_workflow_exit_code_survives_export_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10c.2 / RK9): a telemetry failure must not break the exit code.

    **This is the regression the plan review predicted and the obvious
    implementation would have shipped.** ``_read_back_terminal_state`` was
    originally called *inside* the ``try/except Exception`` that guards the
    ``global_history`` export — a block that exists precisely so telemetry can
    never crash a workflow. Deriving the exit code from a local bound in there
    means an early export failure (a bad import, ``EventLog`` construction)
    is swallowed, execution reaches the return, and the name is **unbound**:
    ``UnboundLocalError`` escaping from the one place written never to fail.

    Here the export is forced to raise. The command must still exit 1 from the
    BLOCKED verdict, and must not raise.

    Oracle: exit 1 with the export broken — no exception.
    Kill-check target: move the ``_read_back_terminal_state`` call back inside
    the ``try`` → this fails with ``UnboundLocalError`` while every other test
    in this module still passes.
    """
    config, home = _wf_env(tmp_path, monkeypatch)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated telemetry failure")

    monkeypatch.setattr("fa.inner_loop.global_history.export_session_to_global_history", _boom)

    args = _workflow_args(tmp_path, config, run_id="wf-export-fail", session_id=None)
    code = _cmd_workflow(args, transport=_RoleAwareTransport([("BLOCKED", "blocked")]), secrets=_TEST_SECRETS)

    assert code == 1, "the verdict-derived exit code must not depend on telemetry succeeding"
    assert _status(home, "wf-export-fail") == "FAILED"


# ---------------------------------------------------------------------------
# Q98 — the managed-execution lifecycle is part of the invocation's outcome
# ---------------------------------------------------------------------------


class _RefusingRelease:
    """A client whose only job is to answer RELEASE with a refusal."""

    def __init__(self) -> None:
        self.operations: list[object] = []

    def request(self, operation: Any, **_: Any) -> dict[str, Any]:
        self.operations.append(operation)
        raise ExecutionRejectedError("workspace-not-owned", None)


def _managed_with_a_refusing_release() -> tuple[Any, _RefusingRelease]:
    from fa.execution.composition import ExecutionBinding, ManagedExecution
    from fa.execution.types import GrantReply, NamespaceRef, Operation

    client = _RefusingRelease()
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)
    grant = GrantReply(Operation.ACQUIRE_WRITER, "2" * 64, None, 1, "rev-" + "3" * 32)
    return ManagedExecution(client, binding, grant), client  # type: ignore[arg-type]


def _workflow_with_a_managed_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, run_id: str
) -> tuple[Any, Any, Path]:
    """A workflow the CLI can actually run, with a managed execution it cannot release."""
    from fa.session.manager import RunContext

    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id=run_id, session_id=None)
    workspace = Path(args.workspace)
    managed, client = _managed_with_a_refusing_release()
    # The real lifecycle puts the run's artifacts under ``$HOME/.fa/session-log``; a
    # stubbed RunContext has to do the same or the test would grade a path the CLI
    # never uses.
    run_log_dir = home / ".fa" / "session-log" / run_id
    run = RunContext(run_id, "session-1", workspace, run_log_dir / "session.db", run_log_dir)
    monkeypatch.setattr(fa_cli, "_resolve_workflow_lifecycle", lambda a, rid: (rid, None, run, None))
    monkeypatch.setattr(fa_cli, "managed_execution_for_run", lambda *a, **k: managed)
    return args, client, home


def test_an_unconfirmed_writer_release_exits_three(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Q98: an accepted run that leaked its writer is not reported as a clean success.

    The verdict keeps its own code (0 = accepted) because that is what callers gate
    on, so the leak gets its own: 0 becomes 3, and 1/2/124 stay what they were.
    Oracle: the exit code, the console line, and the terminal state — the run's own
    artifact must still say DONE, because the work really was accepted.
    """
    args, client, home = _workflow_with_a_managed_execution(tmp_path, monkeypatch, run_id="wf-leak")

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        code = fa_cli._cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    assert code == fa_cli.WORKFLOW_RELEASE_EXIT_CODE == 3
    assert _status(home, "wf-leak") == "DONE"
    assert "writer release for workspace ws-" in stderr.getvalue()
    assert client.operations  # the release was actually attempted before being believed


def test_the_verdict_outranks_a_leaked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected run stays 1: the more specific answer about the work must not be masked."""
    args, _, home = _workflow_with_a_managed_execution(tmp_path, monkeypatch, run_id="wf-leak-blocked")

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        code = fa_cli._cmd_workflow(
            args, transport=_RoleAwareTransport([("BLOCKED", "blocked")]), secrets=_TEST_SECRETS
        )

    assert code == 1
    assert _status(home, "wf-leak-blocked") == "FAILED"
    assert "writer release for workspace" in stderr.getvalue()  # still reported


def test_an_unconfirmed_release_leaves_a_durable_row(tmp_path: Path) -> None:
    """The stderr line is for whoever is watching; the row is for whoever asks later."""
    from fa.inner_loop.session_db import SessionDatabase

    managed, _ = _managed_with_a_refusing_release()
    db = SessionDatabase(tmp_path / "session.db")

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        assert fa_cli._settle_writer_release(managed, run_id="wf-row", session_db=db) is False

    row = db.get_meta("managed_execution_release")
    assert row is not None
    assert row["confirmed"] is False
    assert row["run_id"] == "wf-row"
    assert row["workspace_id"] == "ws-" + "1" * 32
    assert row["exit_code"] == fa_cli.WORKFLOW_RELEASE_EXIT_CODE
