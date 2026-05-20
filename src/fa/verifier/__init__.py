"""Deterministic State Verification (DSV) — post-tool gate.

Wave-0 implementation per
[`research/borrow-roadmap-2026-05.md` §R-5](../../../knowledge/research/borrow-roadmap-2026-05.md).
The verifier inspects a tool-execution event trace and **overrides
the LLM-claimed success flag** when the required-event signature is
not satisfied or any failure-condition is observed. No LLM calls
inside; the gate is the cheapest reliability layer possible.

Public surface (stable until R-1 HookRegistry integration lands):

- :class:`VerifierContract` — frozen dataclass describing one
  tool's verification contract (the YAML schema in
  ``verifiers/*.yaml`` deserialises into this).
- :class:`TraceEvent` — frozen dataclass for a single tool-event
  emitted onto the trace.
- :class:`VerificationResult` — frozen dataclass returned by
  :func:`verify_action`.
- :func:`verify_action` — verification function the future
  ``AFTER_TOOL_EXEC`` middleware will call.
- :func:`load_contract` — parse a YAML contract from text (the
  loader is deliberately separate from the verifier so callers
  can cache contracts).
"""

from __future__ import annotations

from fa.verifier.types import (
    TraceEvent,
    VerificationResult,
    VerifierContract,
)
from fa.verifier.verify_action import load_contract, verify_action

__all__ = [
    "TraceEvent",
    "VerificationResult",
    "VerifierContract",
    "load_contract",
    "verify_action",
]
