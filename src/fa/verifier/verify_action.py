"""Verifier core — :func:`verify_action` + :func:`load_contract`.

The verifier intentionally avoids a YAML dependency: contracts ship
as `.yaml` files on disk, but loading goes through a small subset
parser that recognises only the four top-level keys this module
needs. The parser exists because adding ``pyyaml`` to
``pyproject.toml`` for a Wave-0 standalone module is overkill; the
v0.2 HookRegistry PR (R-1) lands the broader YAML loader and this
function will switch to it then.

Contract YAML shape (only these keys are read; unknown keys are
ignored so callers can extend the file without churning this
parser):

.. code-block:: yaml

    target_action: edit_file
    required_trace_events:
      - file_write
      - sandbox_check
    failure_conditions:
      - file_unchanged_after_edit
      - sandbox_violation
    override_action: force_failure   # default; field optional
"""

from __future__ import annotations

from collections.abc import Iterable

from fa._yaml_subset import strip_inline_comment
from fa.verifier.types import TraceEvent, VerificationResult, VerifierContract


def verify_action(
    contract: VerifierContract,
    events: Iterable[TraceEvent],
) -> VerificationResult:
    """Verify the trace ``events`` against ``contract``.

    Pass means BOTH (a) every event type in
    ``contract.required_trace_events`` appears at least once
    in ``events`` for the contract's ``target_action`` tool, AND
    (b) no observed event lists a failure-condition that the
    contract treats as terminal.

    Reasons are accumulated, not short-circuited — the caller
    can log every distinct override trigger in one pass.
    """

    event_list = list(events)

    relevant = [event for event in event_list if event.tool == contract.target_action]
    observed_types: set[str] = {event.event_type for event in relevant}
    observed_failures: set[str] = {
        condition for event in relevant for condition in event.failure_conditions
    }

    reasons: list[str] = []

    for required_event in contract.required_trace_events:
        if required_event not in observed_types:
            reasons.append(f"missing_required_event:{required_event}")

    for terminal_condition in contract.failure_conditions:
        if terminal_condition in observed_failures:
            reasons.append(f"failure_condition_observed:{terminal_condition}")

    if reasons:
        return VerificationResult(
            passed=False,
            override_action=contract.override_action,
            reasons=tuple(reasons),
        )

    return VerificationResult(
        passed=True,
        override_action="",
        reasons=(),
    )


# C901-baseline waiver (18>15): hand-rolled YAML-subset parser; retires
# with the v0.2 shared YAML loader.
def load_contract(text: str) -> VerifierContract:  # noqa: C901
    """Parse a YAML contract from ``text``.

    The parser handles only the subset documented at the top of
    this module — sufficient for Wave-0 standalone use. The full
    YAML loader lands with R-1 HookRegistry.

    Raises :class:`ValueError` on missing required keys (target,
    required, failure) so the caller cannot silently use a
    half-populated contract.
    """

    target_action: str | None = None
    required_trace_events: list[str] = []
    failure_conditions: list[str] = []
    override_action = "force_failure"

    current_list: list[str] | None = None
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            # YAML inline comments must not be embedded in the parsed
            # value — see fa._yaml_subset.strip_inline_comment + Devin
            # Review finding 2026-05-20 on PR #19.
            value = strip_inline_comment(value).strip()
            current_key = key
            current_list = None
            if value:
                if key == "target_action":
                    target_action = value
                elif key == "override_action":
                    override_action = value
                elif key in {"required_trace_events", "failure_conditions"}:
                    # YAML inline list syntax: ``[]`` (empty) or
                    # ``[item, item, ...]``. The vendored M-1 contracts
                    # use ``required_trace_events: []`` and earlier
                    # versions of this parser silently dropped any
                    # inline list value (the ``if value:`` branch only
                    # handled scalar keys), producing an empty tuple
                    # for any inline list — a silent data loss for
                    # ``required_trace_events: [file_write]``. Now we
                    # parse the inline list explicitly and reject any
                    # other scalar value (e.g. ``required_trace_events:
                    # file_write`` without a list).
                    if not (value.startswith("[") and value.endswith("]")):
                        raise ValueError(
                            f"verifier contract key {key!r} must be a "
                            f"block list or inline list (e.g. ``[]`` or "
                            f"``[a, b]``); got scalar value: {value!r}"
                        )
                    inner = value[1:-1].strip()
                    target_list = (
                        required_trace_events
                        if key == "required_trace_events"
                        else failure_conditions
                    )
                    if inner:
                        for item in inner.split(","):
                            stripped_item = strip_inline_comment(item).strip()
                            if stripped_item:
                                target_list.append(stripped_item)
            else:
                if key == "required_trace_events":
                    current_list = required_trace_events
                elif key == "failure_conditions":
                    current_list = failure_conditions
            continue

        if stripped.startswith("- ") and current_list is not None:
            current_list.append(strip_inline_comment(stripped[2:]).strip())
            continue

        if stripped.startswith("- ") and current_key in {
            "required_trace_events",
            "failure_conditions",
        }:
            target_list = (
                required_trace_events
                if current_key == "required_trace_events"
                else failure_conditions
            )
            target_list.append(strip_inline_comment(stripped[2:]).strip())

    if target_action is None:
        raise ValueError("verifier contract missing required key: target_action")
    if not required_trace_events and not failure_conditions:
        raise ValueError(
            "verifier contract must declare at least one of "
            "required_trace_events or failure_conditions"
        )

    return VerifierContract(
        target_action=target_action,
        required_trace_events=tuple(required_trace_events),
        failure_conditions=tuple(failure_conditions),
        override_action=override_action,
    )


__all__ = ["load_contract", "verify_action"]
