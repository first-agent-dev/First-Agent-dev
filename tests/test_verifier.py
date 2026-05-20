"""Smoke tests for the DSV verifier (R-5).

Coverage targets per the standalone-module contract in
[`research/borrow-roadmap-2026-05.md` §R-5](../knowledge/research/borrow-roadmap-2026-05.md):

1. Happy path — required events present, no failure-conditions
   observed → ``passed`` true.
2. Missing required event → ``passed`` false with the matching
   reason slug.
3. Failure-condition observed → ``passed`` false even when all
   required events are present.
4. Events from other tools are ignored — verifier scopes to
   ``contract.target_action`` only.
5. :func:`load_contract` round-trips the documented YAML subset
   and rejects contracts missing ``target_action``.
"""

from __future__ import annotations

import pytest

from fa.verifier import (
    TraceEvent,
    VerificationResult,
    VerifierContract,
    load_contract,
    verify_action,
)

_HAPPY_CONTRACT = VerifierContract(
    target_action="edit_file",
    required_trace_events=("file_write", "sandbox_check"),
    failure_conditions=("file_unchanged_after_edit", "sandbox_violation"),
)


def test_verifier_passes_when_all_required_events_observed() -> None:
    events = [
        TraceEvent(event_type="sandbox_check", tool="edit_file"),
        TraceEvent(event_type="file_write", tool="edit_file"),
    ]
    result = verify_action(_HAPPY_CONTRACT, events)
    assert result == VerificationResult(passed=True, override_action="", reasons=())


def test_verifier_overrides_on_missing_required_event() -> None:
    events = [
        TraceEvent(event_type="sandbox_check", tool="edit_file"),
    ]
    result = verify_action(_HAPPY_CONTRACT, events)
    assert result.passed is False
    assert result.override_action == "force_failure"
    assert "missing_required_event:file_write" in result.reasons


def test_verifier_overrides_on_failure_condition_even_with_all_events() -> None:
    events = [
        TraceEvent(event_type="sandbox_check", tool="edit_file"),
        TraceEvent(
            event_type="file_write",
            tool="edit_file",
            failure_conditions=("file_unchanged_after_edit",),
        ),
    ]
    result = verify_action(_HAPPY_CONTRACT, events)
    assert result.passed is False
    assert "failure_condition_observed:file_unchanged_after_edit" in result.reasons


def test_verifier_ignores_events_from_other_tools() -> None:
    events = [
        TraceEvent(event_type="file_write", tool="apply_patch"),
        TraceEvent(event_type="sandbox_check", tool="apply_patch"),
    ]
    result = verify_action(_HAPPY_CONTRACT, events)
    assert result.passed is False
    assert "missing_required_event:file_write" in result.reasons
    assert "missing_required_event:sandbox_check" in result.reasons


def test_load_contract_round_trips_documented_subset() -> None:
    yaml = """
target_action: edit_file
required_trace_events:
  - file_write
  - sandbox_check
failure_conditions:
  - file_unchanged_after_edit
  - sandbox_violation
override_action: force_failure
"""
    contract = load_contract(yaml)
    assert contract == _HAPPY_CONTRACT


def test_load_contract_default_override_action_is_force_failure() -> None:
    yaml = """
target_action: edit_file
failure_conditions:
  - sandbox_violation
"""
    contract = load_contract(yaml)
    assert contract.override_action == "force_failure"


def test_load_contract_rejects_missing_target_action() -> None:
    yaml = """
required_trace_events:
  - file_write
"""
    with pytest.raises(ValueError, match="target_action"):
        load_contract(yaml)


def test_load_contract_rejects_empty_required_and_failure_lists() -> None:
    yaml = "target_action: edit_file\n"
    with pytest.raises(ValueError, match="required_trace_events"):
        load_contract(yaml)


def test_load_contract_strips_inline_comments_in_scalars_and_lists() -> None:
    """YAML inline comments must not pollute scalar values or list items.

    Devin Review finding 2026-05-20 on PR #19 — the original parser
    embedded ``# the edit tool`` and ``# important`` into the parsed
    values, which would cause every verifier call to fail with
    ``missing_required_event`` reasons even when the trace was correct.
    """
    yaml = """
target_action: edit_file  # the edit tool
required_trace_events:
  - file_write  # important
  - sandbox_check  # also important
failure_conditions:
  - sandbox_violation  # critical
override_action: force_failure  # default
"""
    contract = load_contract(yaml)
    assert contract.target_action == "edit_file"
    assert contract.required_trace_events == ("file_write", "sandbox_check")
    assert contract.failure_conditions == ("sandbox_violation",)
    assert contract.override_action == "force_failure"

    # Regression guard — round-trip through verify_action passes when
    # the trace matches the comment-stripped contract.
    events = [
        TraceEvent(event_type="sandbox_check", tool="edit_file"),
        TraceEvent(event_type="file_write", tool="edit_file"),
    ]
    result = verify_action(contract, events)
    assert result.passed is True
