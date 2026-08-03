"""S8 — ``fa workflow`` as a separate controller surface.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S8-workflow-controller-surface.md`` (v3).

**Test-class labelling** (tests-writing skill §10 — every test declares its
class so unpaired C0-consumer tests cannot hide):

* **C2** — root is the shipped ``_cmd_workflow``; oracle is a durable artifact
  (``global_history.runs`` row, ``flow_state.json``, ``eval_report.json``) or a
  captured stream. These carry the producer kill-checks.
* **C1** — ``_read_back_terminal_state`` exercised directly for adversarial
  inputs that a full workflow run cannot conveniently produce (corrupt JSON,
  foreign ``run_id``). Paired with the C2 tests above them, never standalone.

**Why the oracles are what they are.** Ranked per the plan §6: DB/FS effect >
exit code > call trajectory > prose. No test here asserts on a printed sentence
as its primary oracle — ``CT5`` explicitly forbids prose as controller truth,
and S7 taught this workstream that a string assertion is the easiest kind to
satisfy vacuously.

**Fixture honesty.** ``_FailingTransport`` returns a persistent HTTP 500 —
what ``UrllibTransport`` actually yields on upstream failure
(``providers/transport.py:117`` converts ``HTTPError`` into a response, and
``URLError``/``TimeoutError``/``ConnectionError`` into ``status=0``). A mock
that *raises* was tried during planning and rejected: it propagates an
unhandled traceback out of ``_cmd_workflow``, i.e. it would assert behaviour the
production stack cannot produce.
"""

from __future__ import annotations

import io
import json
import sqlite3
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from fa.cli import _cmd_workflow, _read_back_terminal_state
from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path
from fa.inner_loop.workflow_artifacts import (
    FlowState,
    load_eval_report,
    load_flow_state,
    write_flow_state,
)
from fa.providers.base import TransportResponse
from tests.test_cli_ergonomics import (
    _FAKE_MODELS_YAML,
    _TEST_SECRETS,
    _RoleAwareTransport,
    _verdict_message,
    _workflow_args,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class _FailingTransport:
    """Persistent HTTP 500 — a realistic upstream outage.

    Counts per-role calls so a test can prove the pipeline *started* and then
    *stopped*, rather than never having run (the S7.C4 positive-control
    lesson: an absence assertion needs a liveness witness).
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.planner_calls = 0
        self.coder_calls = 0
        self.eval_calls = 0

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
        self.calls.append(dict(json_body))
        messages = json_body.get("messages", [])
        system = messages[0]["content"] if messages else ""
        if "First-Agent evaluator" in system:
            self.eval_calls += 1
        elif "First-Agent coder" in system:
            self.coder_calls += 1
        elif "Architect for First-Agent" in system:
            self.planner_calls += 1
        return TransportResponse(status=500, body={"error": "upstream boom"}, retry_after_seconds=None)


class _FailAfterNTransport:
    """Serves scripted eval verdicts, then hard-fails from call ``fail_from``.

    ``_FailingTransport`` can only exercise a *first-stage* failure, which
    reaches 2 of the 6 ``_write_stage_failure_state`` call sites (measured with
    ``trace``). The remaining 4 are **mid-loop** failures — a stage that dies
    *after* a successful eval has already routed the controller into a repair
    or replan round. Those are a genuinely different branch class: the run has
    non-zero ``repair_round``/``replan_round`` state by then, and the failure
    must still be recorded against the correct role.

    Failing "after N successful calls" rather than "on role X" is deliberate:
    the loop revisits the same roles, so a role predicate could not distinguish
    the first coder call from the repair-round coder call.
    """

    def __init__(self, eval_script: list[tuple[str, str]], fail_from: int) -> None:
        self._eval_script = list(eval_script)
        self._fail_from = fail_from
        self.calls = 0
        self.planner_calls = 0
        self.coder_calls = 0
        self.eval_calls = 0

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
        self.calls += 1
        messages = json_body.get("messages", [])
        system = messages[0]["content"] if messages else ""
        is_eval = "First-Agent evaluator" in system
        if is_eval:
            self.eval_calls += 1
        elif "First-Agent coder" in system:
            self.coder_calls += 1
        elif "Architect for First-Agent" in system:
            self.planner_calls += 1

        if self.calls >= self._fail_from:
            return TransportResponse(status=500, body={"error": "upstream boom"}, retry_after_seconds=None)

        content = "done"
        if is_eval:
            verdict, route = self._eval_script.pop(0) if self._eval_script else ("PASS", "complete")
            content = _verdict_message(verdict, route)
        return TransportResponse(
            status=200,
            body={
                "choices": [
                    {"message": {"role": "assistant", "content": content, "tool_calls": []}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            retry_after_seconds=None,
        )


def _wf_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Isolated ``$HOME`` + a models config. Returns ``(config, home)``."""
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return config, home


def _global_history_row(home: Path) -> dict[str, Any]:
    db = home / ".fa" / "global_history.db"
    assert db.is_file(), f"no global_history.db written at {db}"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM runs")]
    finally:
        con.close()
    assert len(rows) == 1, f"expected exactly one aggregate row, got {len(rows)}"
    return rows[0]


# ---------------------------------------------------------------------------
# CT3 / G2 / G3 — the aggregate projection row
# ---------------------------------------------------------------------------


def test_s8_workflow_aggregate_row_is_accurate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.2): the one aggregate row describes the whole workflow.

    Oracle: ``global_history.runs`` fields. Kill-check target: remove
    ``export_session_to_global_history(...)`` in ``_cmd_workflow`` — no row is
    written and ``_global_history_row`` fails its existence assertion.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-agg", session_id=None)

    assert _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS) == 0

    row = _global_history_row(home)
    assert row["run_id"] == "wf-agg"
    # role is the joined pipeline, not a single stage — this is what makes the
    # row an *aggregate* rather than a copy of the last stage.
    assert row["role"] == "planner→coder→eval"
    assert row["exit_code"] == 0
    # turns come from telemetry (usage events), not outcome.turns which the
    # workflow deliberately passes as 0.
    assert row["turns"] == 3, "aggregate turns must span all three stages"


def test_s8_workflow_duration_is_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.2 / G3): ``duration_ms`` is measured, not the literal 0.

    Oracle: ``duration_ms > 0``. Deliberately **not** ``>= 0`` — every integer
    satisfies that, which is the S7.C3 tautology this workstream already paid
    for once. Kill-check target: restore ``duration_ms=0`` at the export call.

    Flake analysis (plan RV6): three real ``_cmd_run`` invocations with SQLite
    writes measured ~120-150 ms; sub-1 ms truncation to 0 is unreachable.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-dur", session_id=None)

    assert _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS) == 0

    assert _global_history_row(home)["duration_ms"] > 0


# ---------------------------------------------------------------------------
# CT2 / CT7 / G1 / G6 — read-back and three-artifact agreement
# ---------------------------------------------------------------------------


def test_s8_artifacts_agree_on_blocked_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.7 / G6): the three durable artifacts agree. Regression for RV4.

    Before S8.7 a BLOCKED run was recorded in the cross-run projection as
    ``workflow_complete`` because ``stop_reason`` was derived from
    ``result_code`` — and every mode returns 0 when the pipeline merely ran to
    completion. S9 builds success rates on this column.

    Oracle: 3-way agreement, not one field. A single-field assertion would also
    pass if the run had genuinely crashed; only the agreement proves the wiring.
    Kill-check target: restore the ``result_code`` ternary at the
    ``aggregate_outcome`` construction.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-blocked", session_id=None)

    code = _cmd_workflow(args, transport=_RoleAwareTransport([("BLOCKED", "blocked")]), secrets=_TEST_SECRETS)

    run_dir = home / ".fa" / "session-log" / "wf-blocked"
    report = load_eval_report(run_dir / "eval_report.json")
    state = load_flow_state(run_dir / "flow_state.json")
    row = _global_history_row(home)

    assert report.verdict == "BLOCKED"
    assert state.status == "FAILED"
    assert row["stop_reason"] == "workflow_failed", "the projection must not call a BLOCKED run complete (plan RV4)"
    # Q35b (S10c.2) — RESOLVED, and this is the visible diff S8 asked for.
    #
    # S8 pinned `code == 0` here on purpose, writing: "pinning it here makes any
    # future change a visible diff rather than silent drift". The operator chose
    # Q35b, so a controller-level rejection now exits 1: `fa workflow && deploy`
    # must not proceed on BLOCKED code.
    #
    # The three artifact assertions above are UNCHANGED, which is the point —
    # only the exit code moved. `row["exit_code"]` follows it because the
    # aggregate row records the process's own status.
    assert code == 1
    assert row["exit_code"] == 1


def test_s8_pass_run_stop_reason_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.7): regression guard — a PASS run still reads ``workflow_complete``.

    S8.7 changes how ``stop_reason`` is derived; this pins the value that
    existing dashboards and queries already match on.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-pass", session_id=None)

    assert _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS) == 0

    assert load_flow_state(home / ".fa" / "session-log" / "wf-pass" / "flow_state.json").status == "DONE"
    assert _global_history_row(home)["stop_reason"] == "workflow_complete"


def test_s8_repair_exhausted_maps_to_its_own_stop_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.7): an exhausted repair budget is neither complete nor failed.

    Proves the mapping is a real lookup over ``FlowStatus`` rather than a
    two-valued boolean wearing a dict's clothes.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-repair", session_id=None, mode="repair", max_repairs=1)
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder")] * 10)

    # Q35b (S10c.2): REPAIR_REQUIRED is a non-DONE terminal status, so the exit
    # code is 1. The stop_reason assertion below is the subject of this test and
    # is unchanged — it still proves the mapping is a real FlowStatus lookup and
    # not a two-valued boolean, which a shared exit code could never show.
    assert _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS) == 1

    assert load_flow_state(home / ".fa" / "session-log" / "wf-repair" / "flow_state.json").status == "REPAIR_REQUIRED"
    assert _global_history_row(home)["stop_reason"] == "workflow_repair_required"


def test_s8_aggregate_stop_reason_comes_from_flow_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.3 / G1): the projection reads the artifact, it does not guess.

    This is the producer kill-check for the read-back: delete
    ``write_flow_state(...)`` inside ``_write_terminal_state`` and the read
    returns ``None``, the export falls back to the exit-code rule, and the
    BLOCKED run is mislabelled ``workflow_complete`` again — measured during
    execution, so this assertion is known to bite.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-src", session_id=None)

    _cmd_workflow(args, transport=_RoleAwareTransport([("BLOCKED", "blocked")]), secrets=_TEST_SECRETS)

    state = load_flow_state(home / ".fa" / "session-log" / "wf-src" / "flow_state.json")
    row = _global_history_row(home)
    # The persisted status is the *source* of the projected reason, so the two
    # must be linked by the mapping rather than coincidentally equal.
    assert state.status == "FAILED"
    assert row["stop_reason"] == "workflow_failed"


def test_s8_controller_truth_is_machine_reconstructable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (CT5): the whole terminal outcome is recoverable from disk alone.

    No prose is parsed. This is the invariant that makes ``fa workflow`` a
    controller surface rather than a script that prints things.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-recon", session_id=None)

    _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    run_dir = home / ".fa" / "session-log" / "wf-recon"
    state = load_flow_state(run_dir / "flow_state.json")
    report = load_eval_report(run_dir / "eval_report.json")

    assert state.run_id == "wf-recon"
    assert state.status == "DONE"
    assert state.last_route_decision == "complete"
    assert report.verdict == "PASS"
    assert _global_history_row(home)["stop_reason"] == "workflow_complete"


# ---------------------------------------------------------------------------
# CT2 adversarial — C1 on the read-back guard itself
# ---------------------------------------------------------------------------


def test_s8_read_back_rejects_foreign_run_id(tmp_path: Path) -> None:
    """C1 (S8.3): a foreign artifact is not trusted.

    The identity check is the difference between a *read* and a
    *verification*. A consumer that loads whatever file it finds would satisfy
    every other assertion in this module; only this one fails it.
    """
    path = tmp_path / "flow_state.json"
    write_flow_state(
        path,
        FlowState(
            run_id="some-other-run",
            task="t",
            status="DONE",
            active_role="eval",
            active_plan_id="x",
            active_plan_version=1,
        ),
    )

    assert _read_back_terminal_state(path, "wf-mine") is None
    # positive control: the same file IS accepted for its own run id, so the
    # None above is the identity guard firing and not a broken loader.
    accepted = _read_back_terminal_state(path, "some-other-run")
    assert accepted is not None
    assert accepted.status == "DONE"


@pytest.mark.parametrize(
    ("kind", "payload"),
    [("corrupt", "{ not json"), ("wrong_shape", json.dumps({"run_id": "wf-x"}))],
)
def test_s8_read_back_survives_unusable_artifact(tmp_path: Path, kind: str, payload: str) -> None:
    """C1 (S8.3): unusable artifacts degrade to ``None``, never raise.

    The workflow has already finished when this runs; a projection read must
    not be able to turn a completed run into a crash.
    """
    path = tmp_path / "flow_state.json"
    path.write_text(payload, encoding="utf-8")

    assert _read_back_terminal_state(path, "wf-x") is None, kind


def test_s8_read_back_missing_file_is_none(tmp_path: Path) -> None:
    """C1 (S8.3): absent artifact is a normal, non-fatal outcome."""
    assert _read_back_terminal_state(tmp_path / "nope.json", "wf-x") is None


# ---------------------------------------------------------------------------
# CT6 / G5 — terminal FAILED states (the v1 audit omission)
# ---------------------------------------------------------------------------


def test_s8_stage_failure_writes_failed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / CT6): a non-zero stage writes FAILED and stops the pipeline.

    ``_write_stage_failure_state`` has 7 call sites and, before S8.6, zero
    tests. Oracle: exit code + persisted state + **call trajectory**. The
    ``coder_calls == 0`` assertion is the liveness witness — without it a test
    that never started the pipeline would pass identically.

    Kill-check target: remove ``_write_stage_failure_state(...)`` from
    ``_run_linear``.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-fail", session_id=None)
    transport = _FailingTransport()

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)

    assert code == 2
    state = load_flow_state(home / ".fa" / "session-log" / "wf-fail" / "flow_state.json")
    assert state.status == "FAILED"
    assert state.active_role == "planner"
    assert "planner" in state.blocked_reason
    # fail-fast: the pipeline demonstrably started (planner was attempted) and
    # demonstrably stopped (no later stage ran).
    assert transport.planner_calls > 0, "the run never reached the provider; the test proves nothing"
    assert transport.coder_calls == 0
    assert transport.eval_calls == 0


# ---------------------------------------------------------------------------
# S8.8 — projection path is resolved at call time (FA_STATE_ROOT honoured)
# ---------------------------------------------------------------------------


def test_s8_global_history_path_honours_state_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C0 (S8.8): the projection path follows ``FA_STATE_ROOT``.

    Regression for an import-time-constant bug: ``DEFAULT_GLOBAL_HISTORY_PATH``
    captured ``Path.home()`` at import, so the writer ignored ``FA_STATE_ROOT``
    while ``fa stats --global-history`` already honoured it — the operator got
    an empty history while rows accumulated in ``~/.fa``.

    Paired with the C2 tests above, which exercise the same resolution through
    the shipped ``_cmd_workflow`` (skill §10: a C0 must not stand alone).
    """
    root = tmp_path / "custom-state-root"
    monkeypatch.setenv("FA_STATE_ROOT", str(root))

    assert default_global_history_path() == root / "global_history.db"
    # The store must agree with the helper; reader and writer disagreeing is
    # precisely the defect this guards.
    assert GlobalHistoryStore(db_path=None).path == root / "global_history.db"


def test_s8_global_history_path_default_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """C0 (S8.8): with no override, the path is byte-identical to the legacy constant.

    The fix must be invisible in production — an operator who never sets
    ``FA_STATE_ROOT`` keeps the exact same file, so no migration is implied.
    """
    monkeypatch.delenv("FA_STATE_ROOT", raising=False)

    assert default_global_history_path() == Path.home() / ".fa" / "global_history.db"


def test_s8_explicit_db_path_still_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C0 (S8.8): an injected ``db_path`` overrides environment resolution.

    Existing callers inject a path; S8.8 must not change their behaviour.
    """
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "ignored"))
    explicit = tmp_path / "explicit" / "gh.db"

    assert GlobalHistoryStore(db_path=explicit).path == explicit


def test_s8_repair_round_stage_failure_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / CT6, P11): a stage dying *inside* a repair round still records FAILED.

    Covers the ``_run_repair`` failure sites, which a first-stage failure
    cannot reach: the controller must already have completed one eval and
    routed to ``return_to_coder`` before these branches exist. Measured with
    ``trace``: ``_FailingTransport`` hits 2 of the 6
    ``_write_stage_failure_state`` call sites, so this class of branch was
    entirely unexercised.

    Oracle: exit code + persisted state + the repair counter, which is the
    witness that the failure happened *mid-loop* rather than at stage one.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-repfail", session_id=None, mode="repair", max_repairs=2)
    # planner, coder, eval(REPAIR_REQUIRED) succeed -> repair round starts -> 4th call dies.
    transport = _FailAfterNTransport([("REPAIR_REQUIRED", "return_to_coder")], fail_from=4)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)

    assert code == 2
    state = load_flow_state(home / ".fa" / "session-log" / "wf-repfail" / "flow_state.json")
    assert state.status == "FAILED"
    assert state.repair_round >= 1, "the failure must be attributed to a repair round, not stage one"
    assert "exited 2" in state.blocked_reason
    # liveness witness: the pipeline genuinely reached the repair loop.
    assert transport.eval_calls >= 1


def test_s8_adaptive_round_stage_failure_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / CT6, P11): same for the adaptive controller's canonical rounds.

    ``_run_adaptive`` has its own two failure sites, distinct from
    ``_run_repair``'s. Covering one mode's loop says nothing about the other's
    — the per-branch rule (plan RN4b) applies within a step, not just across
    features.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(
        tmp_path,
        config,
        run_id="wf-adpfail",
        session_id=None,
        mode="adaptive",
        max_repairs=2,
        max_replans=1,
    )
    transport = _FailAfterNTransport([("REPLAN_REQUIRED", "return_to_planner")], fail_from=4)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)

    assert code == 2
    state = load_flow_state(home / ".fa" / "session-log" / "wf-adpfail" / "flow_state.json")
    assert state.status == "FAILED"
    assert "exited 2" in state.blocked_reason
    assert transport.eval_calls >= 1


def test_s8_shared_initial_roles_failure_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / CT6, P11): the shared ``_run_initial_roles`` failure branch.

    ``repair`` and ``adaptive`` do not run their own initial pass — both
    delegate to ``_run_initial_roles``, which owns a *separate*
    ``_write_stage_failure_state`` call site from ``_run_linear``'s. A linear
    failure test does not cover it (measured: linear reaches one site, this
    reaches a different one).
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-initfail", session_id=None, mode="repair", max_repairs=2)
    transport = _FailingTransport()

    assert _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS) == 2

    state = load_flow_state(home / ".fa" / "session-log" / "wf-initfail" / "flow_state.json")
    assert state.status == "FAILED"
    assert state.active_role == "planner"
    assert state.repair_round == 0, "failure happened before any repair round began"
    assert transport.coder_calls == 0


def test_s8_repair_round_eval_failure_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / CT6, P11): the eval stage dying *during* a repair round.

    ``_run_repair`` guards its coder and its eval with two distinct call
    sites. Covering the coder one says nothing about the eval one — the
    per-branch rule again. Here the coder repair succeeds and the re-eval
    fails, which is the branch a coder-failure test steps over.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-repeval", session_id=None, mode="repair", max_repairs=2)
    # planner, coder, eval(REPAIR_REQUIRED), repair-coder succeed; the 5th call
    # (the re-eval) dies.
    transport = _FailAfterNTransport([("REPAIR_REQUIRED", "return_to_coder")], fail_from=5)

    assert _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS) == 2

    state = load_flow_state(home / ".fa" / "session-log" / "wf-repeval" / "flow_state.json")
    assert state.status == "FAILED"
    assert state.active_role == "eval", "the failure must be attributed to the re-eval, not the coder"
    assert state.repair_round >= 1


# ---------------------------------------------------------------------------
# CT4 / G4 — the stdout contract (I-38 / Q32, scoped to quiet)
# ---------------------------------------------------------------------------


def _run_cli_run(tmp_path: Path, config: Path, *, run_id: str, output_mode: str) -> tuple[int, str, str]:
    """Drive the shipped ``_cmd_run`` and capture both streams verbatim."""
    from fa.cli import _cmd_run
    from tests.test_cli import _make_run_args, _ScriptedTransport, _stop_body

    args = _make_run_args(workspace=tmp_path, config=config, run_id=run_id)
    args.output_mode = output_mode
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = _cmd_run(args, transport=_ScriptedTransport([_stop_body("pong")]), secrets=_TEST_SECRETS)
    return code, out.getvalue(), err.getvalue()


def test_s8_quiet_stdout_is_payload_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.4 / CT4): under quiet, stdout is byte-exactly the payload.

    Oracle: captured stdout compared for **equality**, not a substring or a
    negative. ``"OK:" not in stdout`` alone would pass for a command that never
    ran — the S7.C4 lesson — so the exit code and a non-empty payload are the
    liveness witnesses that make the absence meaningful.

    Kill-check target: make the status-line stream unconditional stdout again.
    """
    config, _ = _wf_env(tmp_path, monkeypatch)

    code, out, err = _run_cli_run(tmp_path, config, run_id="s8-quiet", output_mode="quiet")

    assert code == 0
    assert out == "pong\n", f"stdout must be exactly the payload, got {out!r}"
    # the status line was moved, not deleted — an operator still sees it.
    assert "OK:" in err


def test_s8_console_stdout_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.4 / CT4): default console output is untouched.

    The inverse kill-check. Q32 scoped the change to ``quiet`` precisely so
    existing console users see no difference; making the stream
    *unconditionally* stderr would satisfy the quiet test above while silently
    changing everyone else's terminal. Both directions must be pinned for a
    conditional to be verified.
    """
    config, _ = _wf_env(tmp_path, monkeypatch)

    code, out, _ = _run_cli_run(tmp_path, config, run_id="s8-console", output_mode="console")

    assert code == 0
    assert out.startswith("OK: "), "console mode must keep the status line on stdout"
    assert "pong" in out


def test_s8_workflow_quiet_stdout_is_payload_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.4, P9): the workflow forwards ``--output-mode`` to every stage.

    Workflow is where I-38 compounded — one status line per stage, measured at
    102 bytes for three stages. Kill-check target: revert the
    ``output_mode`` forwarding in ``_run_stage`` to the hardcoded ``"console"``.
    """
    config, _ = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-quiet", session_id=None, output_mode="quiet")

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    assert code == 0
    assert "OK:" not in out.getvalue(), f"status lines leaked to stdout: {out.getvalue()!r}"
    # liveness: the pipeline really ran all three stages (otherwise the
    # absence above is vacuous).
    assert "stage 3/3" in err.getvalue()


def test_s8_workflow_output_mode_defaults_to_console(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.4): omitting the flag preserves today's workflow behaviour."""
    config, _ = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-default", session_id=None)

    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)

    assert code == 0
    assert "OK:" in out.getvalue()


def test_s8_quiet_changes_console_not_durable_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.4 / Q32): quiet alters the console, never the processing.

    The operator's definition of quiet was "less info per turn, all info
    processed as usual". That is a claim about *durable* state, so it needs its
    own oracle: run the same workflow twice, once per mode, and compare the
    artifacts and DB rows rather than the streams.
    """
    results: dict[str, dict[str, object]] = {}
    for mode in ("console", "quiet"):
        root = tmp_path / mode
        root.mkdir()
        config, home = _wf_env(root, monkeypatch)
        args = _workflow_args(root, config, run_id=f"wf-{mode}", session_id=None, output_mode=mode)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = _cmd_workflow(args, transport=_RoleAwareTransport([("PASS", "complete")]), secrets=_TEST_SECRETS)
        run_dir = home / ".fa" / "session-log" / f"wf-{mode}"
        state = load_flow_state(run_dir / "flow_state.json")
        row = _global_history_row(home)
        results[mode] = {
            "code": code,
            "status": state.status,
            "route": state.last_route_decision,
            "verdict": load_eval_report(run_dir / "eval_report.json").verdict,
            "stop_reason": row["stop_reason"],
            "turns": row["turns"],
            "artifacts": sorted(p.name for p in run_dir.iterdir()),
        }

    assert results["console"] == results["quiet"], (
        "quiet mode changed durable state; it must only change what is displayed"
    )
    # positive control: the comparison is not trivially equal-because-empty.
    assert results["quiet"]["turns"] == 3
    quiet_artifacts = results["quiet"]["artifacts"]
    assert isinstance(quiet_artifacts, list)
    assert "flow_state.json" in quiet_artifacts


def test_s8_failure_path_still_exports_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S8.6 / RV5): failed runs still land in the projection.

    The export sits after the single terminal ``return``, so it is reached on
    the failure path too. Nothing protected that: a future early-return in the
    failure branch would silently drop failed runs out of ``global_history``
    and bias every S9 metric toward success.
    """
    config, home = _wf_env(tmp_path, monkeypatch)
    args = _workflow_args(tmp_path, config, run_id="wf-failrow", session_id=None)

    assert _cmd_workflow(args, transport=_FailingTransport(), secrets=_TEST_SECRETS) == 2

    row = _global_history_row(home)
    assert row["exit_code"] == 2
    assert row["stop_reason"] == "workflow_failed"
