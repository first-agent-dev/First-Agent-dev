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
    # D-V2-9 (CT-2.3): the create-new authoring stage. Unlike ACQUISITION this
    # stage *writes* -- but only inside one project root, and never through a
    # candidate buffer. ``plan_ref`` is None for it (D-V2-9.5), because the plan
    # it is about to author is exactly what a plan boundary would freeze.
    CREATE_NEW_PROJECT = "CREATE_NEW_PROJECT"


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
    #: D-V2-9: the one directory a ``CREATE_NEW_PROJECT`` stage may write under,
    #: ``worklogs/<slug>``. Controller-built, never model-supplied, and present
    #: on exactly one kind -- a stray root on any other kind is a mistake to
    #: refuse rather than a value to ignore.
    authoring_root: str | None = None
    #: D-V2-9.8: the exact prefixes a create-new *repair* stage may write. ``None``
    #: means "the ordinary authoring scope" (all of ``authoring_root``); a tuple means
    #: a second stage that may touch only the files admission already read. It travels
    #: on the dispatch because that is the value every layer between the controller and
    #: the limited writer already receives -- threading a sixth parameter through
    #: ``_run_cli_stage``/``_build_run_tool_registry``/``_build_role_registry``/
    #: ``build_planner_registry`` just to narrow one tuple is five chances to drop it.
    repair_allowlist: tuple[str, ...] | None = None

    def _check_repair_allowlist(self) -> None:
        """A repair is *narrower* than the stage it repairs, never wider.

        Every entry must be a file inside ``authoring_root``, and there must be at
        least one: an empty tuple would be a writer that can write nothing, which
        would surface as a confusing ``path_denied`` at tool level instead of a
        dispatch built wrong.
        """
        if self.repair_allowlist is None:
            return
        if self.authoring_root is None or not self.repair_allowlist:
            raise PlannerDispatchError
        prefix = f"{self.authoring_root}/"
        for entry in self.repair_allowlist:
            if not isinstance(entry, str) or not entry.startswith(prefix):
                raise PlannerDispatchError
            if len(_relative_target(entry)) < 3:
                raise PlannerDispatchError

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
        # D-V2-9: the authoring root travels only with the authoring kind, and it is
        # exactly ``worklogs/<slug>`` -- two components, no traversal, no nesting.
        # Anything else would widen a write allowlist that exists to be one directory.
        if self.kind is PlannerDispatchKind.CREATE_NEW_PROJECT:
            parts = _relative_target(self.authoring_root)
            if len(parts) != 2 or parts[0] != "worklogs":
                raise PlannerDispatchError
            self._check_repair_allowlist()
            if self.active_plan is not None:
                # D-V2-9.5: the stage authors the plan it would have to freeze.
                raise PlannerDispatchError
        elif self.authoring_root is not None or self.repair_allowlist is not None:
            raise PlannerDispatchError
