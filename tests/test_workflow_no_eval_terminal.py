"""S11a / F6 — a run nothing judged must never report success.

**The defect this pins.** ``_write_terminal_state`` collapsed two different
situations into ``DONE``:

* the operator asked for an ``eval`` stage and no verdict came back, and
* no ``eval`` stage was ever requested (``fa workflow --roles coder``).

Both wrote ``status="DONE"`` and exited 0, so a pipeline in which *nothing
evaluated anything* was indistinguishable from a verified pass. Absence of
evidence was being reported as evidence of success. This is the harness
version of the rule the ceremony already imposes on the coder: never mark
complete from "no exception".

**Why the empty-sink case is reachable rather than theoretical.**
``_run_stage`` only builds a report when ``role == "eval" and code == 0 and
sink``. A stage that exits 0 without pushing a ``SessionOutcome`` therefore
leaves ``eval_report`` unset and falls straight through to the terminal write
-- which is exactly what ``_RecordingStage`` below does, without simulating
anything.

Class: **C1** — the real ``run_workflow``, with only the stage dispatcher
injected, plus one **C0** case for the extracted pure mapping. The oracle is
the persisted ``flow_state.json`` and the process exit code, not "no
exception".

Kill-check target: the ``else`` branch of ``_write_terminal_state`` (via
``terminal_status_without_eval``). Restoring ``status = "DONE"`` there fails
``test_eval_requested_but_no_verdict_fails``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.workflow_controller import (
    run_workflow,
    terminal_status_without_eval,
    workflow_artifact_paths,
)


class _SilentStage:
    """A real ``run_stage_fn`` that succeeds without producing an outcome.

    Mirrors the production call shape ``(Namespace, **kwargs)``; a controller
    signature drift surfaces here as a ``TypeError`` rather than a silent pass.
    Critically it never appends to ``outcome_sink``, which is the real
    condition under which an eval stage yields no report.
    """

    def __init__(self) -> None:
        self.roles: list[str] = []

    def __call__(self, args: argparse.Namespace, **_kwargs: Any) -> int:
        self.roles.append(str(getattr(args, "role", "?")))
        return 0


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")
    return config


def _run(tmp_path: Path, roles: list[str], *, run_id: str, mode: str = "linear") -> tuple[int, Any]:
    return run_workflow(
        roles=roles,
        task="do the thing",
        per_role_task={},
        mode=mode,
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=_SilentStage(),
    )


def _flow_state(run_id: str) -> dict[str, Any]:
    """Read the persisted artifact from its PRODUCTION location.

    Artifacts land under ``~/.fa/session-log/<run_id>`` (``fa_session_log_root``),
    not under ``tmp_path``; resolving them via the production helper is what
    makes this an end-to-end assertion rather than a guess about layout.
    """
    flow_state = workflow_artifact_paths(run_id).flow_state
    assert flow_state.is_file(), f"no flow_state.json at {flow_state}"
    payload = json.loads(flow_state.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


# ── C0: the extracted decision ─────────────────────────────────────────────


def test_terminal_status_without_eval_is_fail_closed() -> None:
    """C0 — requesting a judge that never ruled is a failure, not a pass."""
    assert terminal_status_without_eval(eval_requested=True)[0] == "FAILED"
    assert terminal_status_without_eval(eval_requested=False)[0] == "DONE"


def test_failed_status_carries_a_reason() -> None:
    """C0 — the artifact must say WHY, not just fail silently."""
    status, blocked = terminal_status_without_eval(eval_requested=True)
    assert status == "FAILED"
    assert "no verdict" in blocked.lower()
    assert terminal_status_without_eval(eval_requested=False)[1] == ""


# ── C1: T19 / T19c — eval asked for, no verdict returned ───────────────────


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_eval_requested_but_no_verdict_fails(tmp_path: Path, mode: str) -> None:
    """T19/T19c (KILL-CHECK) — eval in --roles but no report ⇒ FAILED, exit 1.

    Covers both pipeline modes because ``_run_linear`` and ``_run_adaptive``
    each own a separate no-eval terminal write; fixing one and not the other
    was a live possibility.
    """
    exit_code, state = _run(tmp_path, ["planner", "coder", "eval"], run_id=f"r-{mode}", mode=mode)

    assert state is not None
    assert state.status == "FAILED", "a requested judge that never ruled must not yield DONE"
    assert exit_code == 1, "non-DONE must map to a non-zero exit code"
    payload = _flow_state(f"r-{mode}")
    assert payload["status"] == "FAILED"
    assert "no verdict" in payload["blocked_reason"].lower()


# ── C1: T19b — eval never requested ────────────────────────────────────────


def test_scratch_pipeline_succeeds_but_is_marked_unjudged(tmp_path: Path) -> None:
    """T19b — ``--roles coder`` stays a valid success, tagged ``judged=false``.

    The fix must not make eval mandatory: a scratch pipeline is a legitimate
    use. What it must do is stop the artifact from being mistakable for a
    verified run.
    """
    exit_code, state = _run(tmp_path, ["coder"], run_id="r-scratch")

    assert exit_code == 0, "a scratch pipeline must still succeed"
    assert state is not None
    assert state.status == "DONE"
    assert state.judged is False, "nothing judged this run; the artifact must say so"
    assert _flow_state("r-scratch")["judged"] is False


def test_planner_coder_without_eval_is_also_unjudged(tmp_path: Path) -> None:
    """T19b — the rule keys on eval's ABSENCE, not on a single-role run."""
    exit_code, state = _run(tmp_path, ["planner", "coder"], run_id="r-pc")
    assert exit_code == 0
    assert state is not None
    assert (state.status, state.judged) == ("DONE", False)


# ── Regression guard: judged must not become decorative ────────────────────


def test_judged_is_false_exactly_when_no_report_exists(tmp_path: Path) -> None:
    """Pins the binding between ``judged`` and the report's existence.

    A mutant hard-coding ``judged=True`` would keep every other assertion here
    green, because the FAILED path asserts on ``status``. This is the assertion
    that kills it.
    """
    _, unjudged = _run(tmp_path, ["coder"], run_id="r-a")
    assert unjudged is not None and unjudged.judged is False

    _, failed = _run(tmp_path, ["coder", "eval"], run_id="r-b")
    assert failed is not None
    assert failed.status == "FAILED"
    assert failed.judged is False, "a FAILED-for-no-verdict run was also never judged"


# ── Backward compatibility: pre-S11a artifacts ─────────────────────────────


def test_legacy_flow_state_without_judged_reads_as_judged() -> None:
    """C0 — an artifact written before S11a must not be reinterpreted.

    ``judged`` defaults to True precisely so historical ``flow_state.json``
    files (which have no such key) keep meaning "this run was judged". A
    mutation flipping that default survived the first battery: every other
    test constructs the field explicitly, so nothing pinned the default.
    Reading a legacy payload is the only oracle that catches it.
    """
    from fa.inner_loop.workflow_artifacts import FlowState

    legacy: dict[str, object] = {
        "run_id": "legacy-1",
        "task": "t",
        "status": "DONE",
        "active_role": "eval",
        "active_plan_id": "p",
        "active_plan_version": 1,
    }
    assert FlowState.from_json_dict(legacy).judged is True, (
        "a pre-S11a artifact has no 'judged' key and must default to judged, not be silently downgraded to unjudged"
    )

    # The deserialiser carries its own ``data.get("judged", True)``, so the
    # line above passes even if the DATACLASS default is flipped. Pin the
    # dataclass default separately -- it is the contract for every in-process
    # construction site that does not pass the field (mutation M4).
    constructed = FlowState(
        run_id="c-1",
        task="t",
        status="DONE",
        active_role="eval",
        active_plan_id="p",
        active_plan_version=1,
    )
    assert constructed.judged is True, (
        "constructing a FlowState without stating judged must mean judged; "
        "defaulting to False would mark every unrelated caller's run unjudged"
    )
