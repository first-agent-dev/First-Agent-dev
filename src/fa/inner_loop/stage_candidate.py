"""The stage-local binding between a planner's candidate and its buffer (S3P3).

Two frames need the same object for different reasons, and the view that holds
the candidate is owned by neither of them:

* the **composition root** (``_drive_stage_with_managed_workspace``) opens the
  CANDIDATE view and settles it before the stage returns;
* the **controller** (``_run_admission_repair``) validates the candidate *after*
  that call returns and hands the bytes to the publisher.

So the read has to happen where the view is still alive, and the bytes have to
outlive it. That is exactly the split below: the composition root reads once,
inside the stage, and publishes the result through a context variable that the
controller's reader consumes afterwards. Nothing is cached from a previous stage
-- both variables are cleared on the way out.

This module exists so neither side imports the other: the CLI imports the
controller, so the controller cannot import the CLI back.
"""

from __future__ import annotations

from contextvars import ContextVar

from fa.inner_loop.tools.workspace_port import CandidateWorkspacePort, WorkspacePortError

#: The managed candidate buffer of the stage being driven, or ``None`` in host
#: mode and on every stage that owns no candidate.
STAGE_CANDIDATE_PORT: ContextVar[CandidateWorkspacePort | None] = ContextVar("fa_stage_candidate_port", default=None)

#: ``(text, sha256)`` of the buffer the stage read while its view was open.
#: ``None`` means "no candidate was read", never "an empty candidate": refused
#: bytes are reported through the buffer's own codes, not through this value.
STAGE_CANDIDATE_BYTES: ContextVar[tuple[str, str] | None] = ContextVar("fa_stage_candidate_bytes", default=None)


def reset_stage_candidate() -> None:
    """Forget any captured bytes. Called before a stage whose bytes they are not."""
    STAGE_CANDIDATE_BYTES.set(None)


def capture_stage_candidate(port: CandidateWorkspacePort) -> None:
    """Read the stage's buffer once, inside the view's lifetime.

    A buffer that cannot be read in one window is not captured: a partial plan
    would be validated as if it were the whole candidate, which is worse than a
    named refusal. The refusal travels as ``unavailable`` rather than being
    swallowed, because the alternative -- treating a failed read as "no candidate"
    -- would let a repair silently publish the seed.
    """
    try:
        read = port.read_candidate()
    except WorkspacePortError as error:
        if error.code != "stale":
            raise
        # `stale` here means the buffer is empty: the planner produced no
        # candidate. That is not a substrate failure and not an empty plan --
        # the controller keeps the seed it copied, exactly as host mode would,
        # and admission decides whether those bytes are an acceptable repair.
        return
    if read.eof is not True:
        raise WorkspacePortError("input_policy")
    STAGE_CANDIDATE_BYTES.set((read.content, read.sha256))


def stage_candidate_reader(plan_ref: object) -> tuple[str, str] | None:
    """The bytes this stage captured from its buffer, or ``None`` if it captured none.

    ``None`` is not a fallback switch: the composition root captures on every
    stage that owns a candidate and fails the stage closed if the capture cannot
    be completed (``capture_stage_candidate`` raises), so a candidate-owning
    managed stage never reaches the controller empty-handed. What ``None`` does
    describe is a stage that owns no candidate at all -- host mode, and doubles
    that drive a stage without a buffer -- and those legitimately read the
    controller's own copy.

    The label in ``plan_ref`` is deliberately ignored: the buffer's address is the
    identity the view pinned (CT120), and naming it again here would reintroduce
    the second address that change removed.
    """
    del plan_ref
    return STAGE_CANDIDATE_BYTES.get()


__all__ = [
    "STAGE_CANDIDATE_BYTES",
    "STAGE_CANDIDATE_PORT",
    "capture_stage_candidate",
    "reset_stage_candidate",
    "stage_candidate_reader",
]
