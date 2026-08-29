"""RK6 — the nested-pipeline wall-clock deadline.

**Why this exists.** Serial tool dispatch has no timeout: the only timeouts in
``loop.py`` are on the parallel branch, and ``RuntimeLimits`` has no session
wall-clock cap. So one ``invoke_workflow`` call could run planner -> coder ->
eval plus repair and replan rounds with no bound on elapsed time, blocking the
chat turn indefinitely. The deadline caps the NUMBER of stages dispatched.

**What it deliberately does not do.** A cooperative check cannot interrupt a
stage already in flight, so the honest worst case is ``deadline + one stage``.
That is acceptable because a single stage is already bounded by
``max_iterations`` and ``bash_timeout_seconds``. ``test_deadline_cannot_
interrupt_a_stage_already_running`` pins that limit rather than hiding it.

Class: **C1** — the real ``run_workflow`` from ``workflow_controller``, with
only the stage dispatcher injected. ``run_stage_fn`` is a real callable with
the production ``(namespace, **kwargs)`` shape, not a mock.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.workflow_controller import (
    DEADLINE_REASON_MARKER,
    WORKFLOW_DEADLINE_EXIT_CODE,
    run_workflow,
)

_ROLES = ["planner", "coder", "eval"]


class _RecordingStage:
    """A real ``run_stage_fn``: positional Namespace plus keyword extras.

    ``_run_stage`` builds an ``argparse.Namespace`` and calls
    ``run_stage_fn(stage_args, transport=..., secrets=..., outcome_sink=...)``.
    Matching that shape exactly is what makes this a fixture rather than a mock:
    a signature drift in the controller shows up here as a ``TypeError``.
    """

    def __init__(self, *, delay: float = 0.0, exit_code: int = 0) -> None:
        self.roles: list[str] = []
        self._delay = delay
        self._exit_code = exit_code

    def __call__(self, args: argparse.Namespace, **_kwargs: Any) -> int:
        self.roles.append(str(getattr(args, "role", "?")))
        if self._delay:
            time.sleep(self._delay)
        return self._exit_code


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")
    return config


def _run(
    tmp_path: Path,
    stage: _RecordingStage,
    *,
    run_id: str,
    deadline_mono: float | None,
    roles: list[str] | None = None,
    mode: str = "linear",
) -> tuple[int, Any]:
    return run_workflow(
        roles=list(roles or _ROLES),
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
        run_stage_fn=stage,
        deadline_mono=deadline_mono,
    )


def test_expired_deadline_runs_zero_stages(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — removing the ``_run_stage`` guard fails this test.

    A deadline already in the past must stop the pipeline before it dispatches
    anything at all; the guard is checked before the stage, not after.
    """
    stage = _RecordingStage()
    exit_code, state = _run(tmp_path, stage, run_id="dl-past", deadline_mono=time.monotonic() - 1.0)

    assert stage.roles == [], "no stage may be dispatched once the deadline has passed"
    assert exit_code != 0
    assert state is not None
    assert state.status == "FAILED"


def test_deadline_stops_between_stages(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — the cap is on the NUMBER of stages.

    The deadline expires while stage 1 is running, so stage 1 completes and
    stage 2 is never dispatched. Asserting ``["planner"]`` (not merely "fewer
    than three") is what makes this a real oracle.
    """
    stage = _RecordingStage(delay=0.25)
    exit_code, _state = _run(tmp_path, stage, run_id="dl-mid", deadline_mono=time.monotonic() + 0.15)

    assert stage.roles == ["planner"], f"expected to stop after stage 1, ran {stage.roles}"
    assert exit_code == WORKFLOW_DEADLINE_EXIT_CODE


def test_deadline_cannot_interrupt_a_stage_already_running(tmp_path: Path) -> None:
    """C1 — pins the stated limit of a cooperative check.

    The worst case is ``deadline + one stage``, and that is a documented
    trade-off, not a bug: a stage in flight is bounded by ``max_iterations``
    and ``bash_timeout_seconds``. If this ever starts failing, someone has
    added real pre-emption and the docstrings need updating.
    """
    stage = _RecordingStage(delay=0.3)
    started = time.monotonic()
    _run(tmp_path, stage, run_id="dl-inflight", deadline_mono=started + 0.05)
    elapsed = time.monotonic() - started

    assert stage.roles == ["planner"]
    assert elapsed >= 0.3, "the in-flight stage was truncated, which this design cannot do"


def test_deadline_writes_terminal_flow_state(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — making the deadline raise fails this test.

    The run must stay auditable: a well-formed terminal artifact on disk, with
    the marker the tool keys ``timed_out`` off.
    """
    stage = _RecordingStage()
    _run(tmp_path, stage, run_id="dl-artifact", deadline_mono=time.monotonic() - 1.0)

    # Resolved through the production helper rather than a hardcoded path, so
    # the test cannot drift from where the controller actually writes.
    from fa.inner_loop.workflow_controller import workflow_artifact_paths

    flow_state = workflow_artifact_paths("dl-artifact").flow_state
    assert flow_state.is_file(), f"no flow_state.json at {flow_state}"
    payload = json.loads(flow_state.read_text(encoding="utf-8"))
    assert payload["status"] == "FAILED"
    assert DEADLINE_REASON_MARKER in payload["last_transition_reason"]


def test_deadline_reason_is_not_overwritten_by_fail_fast(tmp_path: Path) -> None:
    """C1 — the richer deadline state must survive the fail-fast writer.

    A deadline stop returns non-zero, and every non-zero stage normally
    triggers ``_write_stage_failure_state``. Without the pass-through for
    ``WORKFLOW_DEADLINE_EXIT_CODE`` that writer would clobber the marker with
    ``stage exited 124`` and the tool would report ``timed_out=False``.
    """
    stage = _RecordingStage()
    _, state = _run(tmp_path, stage, run_id="dl-nooverwrite", deadline_mono=time.monotonic() - 1.0)

    assert state is not None
    assert DEADLINE_REASON_MARKER in state.last_transition_reason
    assert "stage exited" not in state.last_transition_reason


def test_no_deadline_runs_the_full_pipeline(tmp_path: Path) -> None:
    """C1 (matrix C — defaults) — every existing caller is unchanged.

    ``_cmd_workflow`` passes no deadline. This is the regression guard for the
    "byte-identical for existing callers" claim.
    """
    stage = _RecordingStage()
    exit_code, state = _run(tmp_path, stage, run_id="dl-none", deadline_mono=None)

    assert stage.roles == _ROLES, "the whole pipeline must still run without a deadline"
    assert exit_code == 0
    assert state is not None
    assert state.status == "DONE"


def test_generous_deadline_runs_the_full_pipeline(tmp_path: Path) -> None:
    """C1 (matrix A — feature on, not firing) — the guard is not a blanket stop."""
    stage = _RecordingStage()
    exit_code, _state = _run(tmp_path, stage, run_id="dl-generous", deadline_mono=time.monotonic() + 3600)

    assert stage.roles == _ROLES
    assert exit_code == 0


def test_deadline_applies_to_adaptive_mode_too(tmp_path: Path) -> None:
    """C1 (path inventory) — the guard sits at the choke point, so every mode gets it.

    ``linear`` and ``adaptive`` reach ``_run_stage`` through different call
    sites; testing one does not prove the other.
    """
    stage = _RecordingStage()
    exit_code, _state = _run(
        tmp_path,
        stage,
        run_id="dl-adaptive",
        deadline_mono=time.monotonic() - 1.0,
        roles=["coder", "eval"],
        mode="adaptive",
    )

    assert stage.roles == []
    assert exit_code == WORKFLOW_DEADLINE_EXIT_CODE


def test_workflow_timeout_seconds_is_a_real_config_knob() -> None:
    """C0p — the operator-facing half of RK6.

    Rejects ``0`` deliberately: "no deadline" is expressed by omitting
    ``deadline_mono``, not by configuring a zero timeout, so ``0`` here is an
    operator error and must be reported rather than silently disabling the cap.
    """
    from fa.inner_loop.runtime_limits import (
        DEFAULT_WORKFLOW_TIMEOUT_SECONDS,
        RuntimeLimits,
        load_runtime_limits,
    )

    assert RuntimeLimits().workflow_timeout_seconds == DEFAULT_WORKFLOW_TIMEOUT_SECONDS

    applied = load_runtime_limits("runtime_limits:\n  workflow_timeout_seconds: 90")
    assert applied.limits.workflow_timeout_seconds == 90
    assert applied.warnings == ()

    for bad in ("0", "-5", "abc"):
        rejected = load_runtime_limits(f"runtime_limits:\n  workflow_timeout_seconds: {bad}")
        assert rejected.limits.workflow_timeout_seconds == DEFAULT_WORKFLOW_TIMEOUT_SECONDS
        assert any(w.key == "workflow_timeout_seconds" for w in rejected.warnings), f"{bad!r} was rejected silently"


@pytest.mark.parametrize("elapsed_past", [0.0, 0.5])
def test_deadline_boundary_is_inclusive(tmp_path: Path, elapsed_past: float) -> None:
    """C0p — ``>=`` not ``>``: a deadline exactly reached is exceeded."""
    stage = _RecordingStage()
    _run(
        tmp_path,
        stage,
        run_id=f"dl-boundary-{elapsed_past}",
        deadline_mono=time.monotonic() - elapsed_past,
    )
    assert stage.roles == []
