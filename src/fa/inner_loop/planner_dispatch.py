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

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PlannerDispatchKind):
            raise PlannerDispatchError
        if not isinstance(self.run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.run_id) is None:
            raise PlannerDispatchError
        if self.active_plan is not None:
            _relative_target(self.active_plan)
        if self.kind == PlannerDispatchKind.ORDINARY_PLANNING:
            if self.candidate_target is not None:
                raise PlannerDispatchError
        else:
            parts = _relative_target(self.candidate_target)
            if len(parts) < 4 or parts[:3] != (".fa", "admission", self.run_id):
                raise PlannerDispatchError
            if self.candidate_target == self.active_plan:
                raise PlannerDispatchError
