"""Trusted plan-context value; NOT a resource authority or metadata loader.

Only the required authority may construct this from protected immutable view
metadata and its registered source root. Neither root nor evidence policy is a
wire/model/worker input. Real persistence/authority integration remains required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from fa.execution.protocol import validate_plan_ref
from fa.execution.types import ExecutionContractError
from fa.inner_loop.plan_admission import PlanRef, PlanRefError, read_plan_snapshot


@dataclass(frozen=True, slots=True, repr=False)
class ProtectedPlanContext:
    source_root: Path
    plan_ref: PlanRef | None
    formal_evidence: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_root, Path) or not self.source_root.is_absolute():
            raise ExecutionContractError
        if type(self.formal_evidence) is not bool:
            raise ExecutionContractError
        if self.plan_ref is not None:
            if not isinstance(self.plan_ref, PlanRef):
                raise ExecutionContractError
            validate_plan_ref(asdict(self.plan_ref))
        if self.formal_evidence and self.plan_ref is None:
            raise ExecutionContractError

    def to_plan_ref(self) -> dict[str, str] | None:
        return None if self.plan_ref is None else asdict(self.plan_ref)

    def recheck(self) -> None:
        """Read bounded actual bytes through the existing no-follow reader."""
        if self.plan_ref is None:
            return  # Ordinary no-active-plan context, not formal evidence.
        try:
            actual = read_plan_snapshot(self.source_root, Path(self.plan_ref.workspace_relative_path))
        except PlanRefError:
            raise ExecutionContractError from None
        if actual.ref.sha256 != self.plan_ref.sha256:
            raise ExecutionContractError

    def check_receipt_plan(self, plan_sha256: str | None) -> None:
        expected = None if self.plan_ref is None else self.plan_ref.sha256
        if plan_sha256 != expected:
            raise ExecutionContractError
