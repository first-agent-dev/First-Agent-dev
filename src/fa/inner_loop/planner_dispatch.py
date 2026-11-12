"""Controller-owned planner write scope, never populated from model arguments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class PlannerDispatchError(ValueError):
    """A malformed controller capability must not degrade to ordinary tools."""

    def __init__(self) -> None:
        super().__init__("invalid planner dispatch")


class PlannerDispatchKind(StrEnum):
    ORDINARY_PLANNING = "ORDINARY_PLANNING"
    ADMISSION_REPAIR = "ADMISSION_REPAIR"
    EVAL_REPLAN = "EVAL_REPLAN"
    # S5P1 (spec §7.0): the initial managed planner that chooses a target. It runs
    # before any plan exists, so it owns neither a candidate buffer nor an active
    # plan -- read/search and one final strict choice, nothing else.
    ACQUISITION = "ACQUISITION"


def _relative_target(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or "\x00" in value:
        raise PlannerDispatchError
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise PlannerDispatchError
    return parts


@dataclass(frozen=True, slots=True)
class PlannerDispatch:
    kind: PlannerDispatchKind
    run_id: str
    active_plan: str | None = None
    candidate_target: str | None = None

    @property
    def owns_candidate(self) -> bool:
        """Whether this stage may write the staged-candidate buffer.

        Spelled out as one positive fact rather than re-derived at each call site.
        The previous shape asked ``kind != ORDINARY_PLANNING`` in six places, which
        was true only because every non-ordinary kind happened to own a candidate;
        adding ``ACQUISITION`` would have silently granted it a capability it neither
        asked for nor can label (CT120 needs an admitted ``plan_ref``). A new kind
        now has to opt in here, in one place, where the reviewer sees it.
        """
        return self.kind in (PlannerDispatchKind.ADMISSION_REPAIR, PlannerDispatchKind.EVAL_REPLAN)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PlannerDispatchKind):
            raise PlannerDispatchError
        if not isinstance(self.run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.run_id) is None:
            raise PlannerDispatchError
        if self.active_plan is not None:
            _relative_target(self.active_plan)
        if self.owns_candidate:
            parts = _relative_target(self.candidate_target)
            if len(parts) < 4 or parts[:3] != (".fa", "admission", self.run_id):
                raise PlannerDispatchError
            if self.candidate_target == self.active_plan:
                raise PlannerDispatchError
        else:
            # No candidate, and never a half-built one: a stray target on a kind that
            # does not own the buffer is a controller mistake, not something to ignore.
            if self.candidate_target is not None:
                raise PlannerDispatchError
            if self.kind is PlannerDispatchKind.ACQUISITION and self.active_plan is not None:
                # Acquisition runs before a plan is admitted, so naming one would be a
                # claim about a target nobody has selected yet.
                raise PlannerDispatchError
