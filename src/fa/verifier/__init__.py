"""Deterministic State Verification (DSV) — post-tool gate.

Wave-0 implementation per
[`research/borrow-roadmap-2026-05.md` §R-5](../../../knowledge/research/borrow-roadmap-2026-05.md).
The verifier inspects a tool-execution event trace and **overrides
the LLM-claimed success flag** when the required-event signature is
not satisfied or any failure-condition is observed. No LLM calls
inside; the gate is the cheapest reliability layer possible.

Public surface (stable through R-1 HookRegistry integration):

- :class:`VerifierContract` — frozen dataclass describing one
  tool's verification contract (the YAML schema in
  ``verifiers/*.yaml`` deserialises into this).
- :class:`TraceEvent` — frozen dataclass for a single tool-event
  emitted onto the trace.
- :class:`VerificationResult` — frozen dataclass returned by
  :func:`verify_action`.
- :func:`verify_action` — verification function the
  ``AFTER_TOOL_EXEC`` middleware calls.
- :func:`load_contract` — parse a YAML contract from text (the
  loader is deliberately separate from the verifier so callers
  can cache contracts).
- :func:`load_contracts_from_dir` — convenience batch loader
  for a directory of ``<tool>.yaml`` files (Wave-2 R-5 PR-3);
  used by the smoke CLI to seed the ``VerifierObserver``
  contract map.
"""

from __future__ import annotations

from pathlib import Path

from fa.verifier.types import (
    TraceEvent,
    VerificationResult,
    VerifierContract,
)
from fa.verifier.verify_action import load_contract, verify_action


def load_contracts_from_dir(directory: Path) -> dict[str, VerifierContract]:
    """Load every ``<tool>.yaml`` contract under ``directory``.

    Returns a ``{target_action: VerifierContract}`` mapping suitable
    for direct construction of :class:`VerifierObserver`. The
    filename stem is **not** the key — the key is the in-file
    ``target_action:`` field, so a tool renamed in the YAML still
    routes correctly even if the filename lags. Missing directory
    returns an empty mapping (the smoke CLI may run before
    contracts are vendored). Bad files (parse errors) raise
    :class:`ValueError` with the offending path appended so the
    caller can pin-point the bad contract.
    """

    contracts: dict[str, VerifierContract] = {}
    if not directory.exists() or not directory.is_dir():
        return contracts
    for path in sorted(directory.glob("*.yaml")):
        try:
            contract = load_contract(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        contracts[contract.target_action] = contract
    return contracts


__all__ = [
    "TraceEvent",
    "VerificationResult",
    "VerifierContract",
    "load_contract",
    "load_contracts_from_dir",
    "verify_action",
]
