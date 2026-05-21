"""Public dataclasses for the DSV verifier.

Schema documented in
[`research/borrow-roadmap-2026-05.md` §R-5](../../../knowledge/research/borrow-roadmap-2026-05.md).
Field semantics short version (full rationale in the source note):

- ``target_action`` — the tool name this contract verifies
  (e.g. ``"edit_file"``). One contract per tool.
- ``required_trace_events`` — event types whose presence is
  REQUIRED for the action to be considered successful. Order is
  insignificant; presence is checked as a set membership.
- ``failure_conditions`` — string IDs of failure-conditions any
  one of which trips the override. The IDs are well-known
  short slugs (e.g. ``"file_unchanged_after_edit"``,
  ``"sandbox_violation"``) — semantics live in the trace
  emitter, not here; the verifier only checks ID membership in
  the observed events' ``failure_conditions`` set.
- ``override_action`` — action to take when verification fails.
  v0.1 only supports ``"force_failure"``; the dispatcher reads
  this and clears the LLM-claimed success flag.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceEvent:
    """One event emitted on the tool-execution trace.

    The dispatcher (future R-1 HookRegistry) is responsible for
    writing these; the verifier only reads them.

    - ``event_type`` — short slug (e.g. ``"file_write"``,
      ``"file_read"``, ``"sandbox_check"``).
    - ``tool`` — name of the tool that emitted the event.
    - ``failure_conditions`` — tuple of failure-condition IDs
      observed when this event was emitted. Empty tuple for
      success events.
    """

    event_type: str
    tool: str
    failure_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifierContract:
    """One tool's verification contract — the in-memory shape of
    a ``verifiers/<tool>.yaml`` file.
    """

    target_action: str
    required_trace_events: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    override_action: str = "force_failure"


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of :func:`verify_action`.

    - ``passed`` — true when no override is triggered. The
      dispatcher MUST NOT clear the LLM-claimed success flag
      when this is true.
    - ``override_action`` — copied from the contract when the
      result is a failure; empty string on pass.
    - ``reasons`` — human-readable reason slugs for the override
      (e.g. ``"missing_required_event:file_write"``,
      ``"failure_condition_observed:file_unchanged_after_edit"``).
      Tuple, not list, to keep the result hashable and easy to
      log as JSON.
    """

    passed: bool
    override_action: str
    reasons: tuple[str, ...]


__all__ = ["TraceEvent", "VerificationResult", "VerifierContract"]
