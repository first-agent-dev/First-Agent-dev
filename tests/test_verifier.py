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

from pathlib import Path

import pytest

from fa.verifier import (
    TraceEvent,
    VerificationResult,
    VerifierContract,
    load_contract,
    load_contracts_from_dir,
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

    Agent Review finding 2026-05-20 on PR #19 — the original parser
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


def test_load_contract_parses_inline_empty_list() -> None:
    """``required_trace_events: []`` parses to an empty tuple explicitly.

    The vendored M-1 ``verifiers/*.yaml`` contracts all use inline-empty
    list syntax for ``required_trace_events``. Earlier versions of the
    subset parser silently dropped any inline list value (the
    ``if value:`` branch only handled scalar keys), so this happened
    to produce the right empty tuple by omission. The fix makes inline
    list parsing explicit.
    """
    yaml = """
target_action: fs.read_file
required_trace_events: []
failure_conditions:
  - read_failed
"""
    contract = load_contract(yaml)
    assert contract.required_trace_events == ()
    assert contract.failure_conditions == ("read_failed",)


def test_load_contract_parses_inline_populated_list() -> None:
    """``required_trace_events: [file_write, sandbox_check]`` parses items.

    Regression guard for the silent-data-loss bug: previously, inline
    populated lists were silently dropped, producing an empty tuple
    instead of the declared events.
    """
    yaml = """
target_action: edit_file
required_trace_events: [file_write, sandbox_check]
failure_conditions: [file_unchanged_after_edit]
"""
    contract = load_contract(yaml)
    assert contract.required_trace_events == ("file_write", "sandbox_check")
    assert contract.failure_conditions == ("file_unchanged_after_edit",)


def test_load_contract_rejects_scalar_for_list_key() -> None:
    """A bare scalar for a list-typed key fails loudly, not silently.

    Before the fix, ``required_trace_events: file_write`` (missing the
    list brackets) was silently dropped — the contract ended up with
    an empty tuple and every verifier call passed trivially. Now the
    parser raises so the author sees the typo.
    """
    yaml = """
target_action: edit_file
required_trace_events: file_write
failure_conditions:
  - sandbox_violation
"""
    with pytest.raises(ValueError, match=r"required_trace_events.*list"):
        load_contract(yaml)


# --- load_contracts_from_dir (R-5 batch loader) ----------------------------


def test_load_contracts_from_dir_indexes_by_target_action(tmp_path: Path) -> None:
    """The map key is the in-file ``target_action`` field, not the filename.

    A tool renamed in the YAML still routes correctly even if the
    filename lags — this is the contract the smoke CLI relies on.
    """

    (tmp_path / "alpha.yaml").write_text(
        "target_action: fs.read_file\n"
        "required_trace_events: []\n"
        "failure_conditions:\n"
        "  - read_failed\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.yaml").write_text(
        "target_action: fs.write_file\n"
        "required_trace_events: []\n"
        "failure_conditions:\n"
        "  - write_failed\n",
        encoding="utf-8",
    )

    contracts = load_contracts_from_dir(tmp_path)

    assert set(contracts) == {"fs.read_file", "fs.write_file"}
    assert contracts["fs.read_file"].failure_conditions == ("read_failed",)


def test_load_contracts_from_dir_returns_empty_for_missing_directory(
    tmp_path: Path,
) -> None:
    """A missing or empty directory returns ``{}`` rather than raising.

    The smoke CLI may run before contracts are vendored; a hard error
    here would block the entry-point. The right failure mode is «no
    contracts loaded» = «verifier runs as a no-op».
    """

    assert load_contracts_from_dir(tmp_path / "does-not-exist") == {}
    assert load_contracts_from_dir(tmp_path) == {}


def test_load_contracts_from_dir_appends_filename_to_parse_errors(
    tmp_path: Path,
) -> None:
    """A bad file is named in the error so the caller can pin-point it."""

    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text("required_trace_events: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"bad\.yaml.*target_action"):
        load_contracts_from_dir(tmp_path)


def test_load_contracts_from_dir_skips_non_yaml_files(tmp_path: Path) -> None:
    """Only ``*.yaml`` files are loaded; sibling files are ignored."""

    (tmp_path / "noise.md").write_text("# README\n", encoding="utf-8")
    (tmp_path / "fs.read_file.yaml").write_text(
        "target_action: fs.read_file\n"
        "required_trace_events: []\n"
        "failure_conditions:\n"
        "  - read_failed\n",
        encoding="utf-8",
    )

    contracts = load_contracts_from_dir(tmp_path)
    assert set(contracts) == {"fs.read_file"}
