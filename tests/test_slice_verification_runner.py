"""Oracles for the slice verify-command runner (I02 SLICE1, CT44-CT49e).

Class: **C0** unit + **C0p** property + **C3** security (environment scrubbing).
The C1 composition-root proof belongs to SLICE6, which wires ``run_commands``
into ``_run_stage``; until then this module has no production caller and a C1
test here would be theatre.

Every assertion below is an observable effect of a real subprocess -- the
command's own exit code, its stdout, or a file it did or did not create --
rather than "the call returned without raising". The runner's whole purpose is
to distinguish "ran and failed" from "never ran", so a test that only proves
absence of exceptions would verify nothing it exists to verify.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from fa.inner_loop.slice_verification import (
    DEFAULT_VERIFY_TIMEOUT_SECONDS,
    TAIL_LIMIT,
    CommandOutcome,
    CommandResult,
    run_commands,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A session-workspace stand-in. No ``.venv`` unless a test makes one."""
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


# ── CT44: one result per command, in order, carrying the real exit code ──────


def test_one_result_per_command_in_order(workspace: Path) -> None:
    """CT44 -- producer: ``run_commands``. Neutralising it returns None and this fails."""
    results = run_commands(("echo first", "echo second", "echo third"), workspace=workspace)

    assert len(results) == 3
    assert [r.command for r in results] == ["echo first", "echo second", "echo third"]
    assert [r.stdout_tail.strip() for r in results] == ["first", "second", "third"]


def test_exit_code_is_the_real_integer_not_a_boolean(workspace: Path) -> None:
    """CT44 -- a non-zero code is preserved verbatim, not coerced to True/False."""
    (result,) = run_commands(("exit 3",), workspace=workspace)

    assert result.exit_code == 3
    assert isinstance(result.exit_code, int)
    assert not isinstance(result.exit_code, bool)
    assert result.outcome is CommandOutcome.FAIL


def test_zero_exit_is_pass_and_nonzero_is_fail(workspace: Path) -> None:
    """CT44 -- the PASS boundary sits at 0 and nowhere else."""
    ok, bad = run_commands(("true", "false"), workspace=workspace)

    assert (ok.outcome, ok.exit_code) == (CommandOutcome.PASS, 0)
    assert bad.outcome is CommandOutcome.FAIL
    assert bad.exit_code != 0


def test_stderr_is_captured_separately_from_stdout(workspace: Path) -> None:
    """CT44 -- a failing command's diagnostic must survive for the coder to read."""
    (result,) = run_commands(("echo out; echo err >&2; exit 1",), workspace=workspace)

    assert result.stdout_tail.strip() == "out"
    assert result.stderr_tail.strip() == "err"


# ── CT45: a timeout is ERROR, never PASS and never a silent FAIL ─────────────


def test_timeout_yields_error_with_no_exit_code(workspace: Path) -> None:
    """CT45 -- producer: ``_timeout_result``. Neutralising it returns None and this fails."""
    (result,) = run_commands(("sleep 5",), workspace=workspace, timeout_s=0.5)

    assert result.outcome is CommandOutcome.ERROR
    assert result.exit_code is None
    assert result.outcome is not CommandOutcome.PASS
    assert result.outcome is not CommandOutcome.FAIL
    assert "budget" in result.stderr_tail


def test_timeout_records_elapsed_seconds(workspace: Path) -> None:
    """CT49d -- the operator must be able to see what the command actually cost."""
    (result,) = run_commands(("sleep 5",), workspace=workspace, timeout_s=0.5)

    assert result.duration_s >= 0.5
    assert result.duration_s < 5.0


# ── CT47: the run deadline stops later commands being STARTED ────────────────


def test_deadline_prevents_remaining_commands_from_running(workspace: Path) -> None:
    """CT47 -- negative proof: the side effect the command would have had is absent."""
    witness = workspace / "witness.txt"
    past = time.monotonic() - 1.0

    results = run_commands((f"touch {witness}",), workspace=workspace, deadline=past)

    assert results[0].outcome is CommandOutcome.ERROR
    assert results[0].exit_code is None
    assert "deadline" in results[0].stderr_tail
    assert not witness.exists(), "command must not merely be reported as skipped, it must not run"


def test_deadline_still_returns_one_result_per_command(workspace: Path) -> None:
    """CT47 -- skipped commands are reported, not dropped; the caller can attribute them."""
    past = time.monotonic() - 1.0

    results = run_commands(("true", "true", "true"), workspace=workspace, deadline=past)

    assert len(results) == 3
    assert all(r.outcome is CommandOutcome.ERROR for r in results)


def test_a_generous_deadline_does_not_block_commands(workspace: Path) -> None:
    """CT47 -- the deadline must not be a blanket refusal; it is a budget."""
    future = time.monotonic() + 60.0

    (result,) = run_commands(("echo alive",), workspace=workspace, deadline=future)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "alive"


# ── CT48: no declared commands is not an error ───────────────────────────────


def test_empty_command_tuple_returns_empty_results(workspace: Path) -> None:
    """CT48 -- producer: ``_empty_result``. Removing the call makes this fail."""
    assert run_commands((), workspace=workspace) == ()


def test_empty_commands_do_not_raise_or_block(workspace: Path) -> None:
    """CT48 -- a slice with no verify fence must be skippable, not fatal."""
    results = run_commands([], workspace=workspace)

    assert results == ()
    assert not any(r.outcome is CommandOutcome.ERROR for r in results)


# ── CT49c: commands run in the session workspace ─────────────────────────────


def test_commands_run_inside_the_workspace(workspace: Path) -> None:
    """CT49c -- producer: ``_workspace_cwd``. Removing the call makes cwd wrong and this fails."""
    (result,) = run_commands(("pwd",), workspace=workspace)

    assert Path(result.stdout_tail.strip()).resolve() == workspace.resolve()


def test_relative_paths_resolve_against_the_workspace(workspace: Path) -> None:
    """CT49c -- the stronger claim: a *relative* command path hits the workspace tree."""
    (workspace / "marker.txt").write_text("present", encoding="utf-8")

    (result,) = run_commands(("cat marker.txt",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "present"


# ── CT49d: the runner owns its timeout and does not inherit the bash default ─


def test_default_timeout_is_not_the_interactive_bash_budget() -> None:
    """CT49d -- producer: ``_command_timeout``. Neutralising it returns None and this fails."""
    from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
    from fa.inner_loop.slice_verification import _command_timeout

    assert DEFAULT_VERIFY_TIMEOUT_SECONDS == 600.0
    assert DEFAULT_VERIFY_TIMEOUT_SECONDS != DEFAULT_BASH_TIMEOUT_SECONDS
    assert _command_timeout(None) == DEFAULT_VERIFY_TIMEOUT_SECONDS


def test_explicit_timeout_overrides_the_default() -> None:
    """CT49d -- the budget is operator-overridable at the call seam."""
    from fa.inner_loop.slice_verification import _command_timeout

    assert _command_timeout(12) == 12.0
    assert _command_timeout(0.25) == 0.25


# ── CT46 / CT49b / CT49e: the environment is scrubbed, then computed ─────────


def test_secret_named_variables_are_not_inherited(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CT46 (C3) -- a verify command must never see the operator's credentials."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-leak")
    monkeypatch.setenv("SOME_SECRET", "also-never")

    (result,) = run_commands(("env",), workspace=workspace)

    assert "sk-should-never-leak" not in result.stdout_tail
    assert "also-never" not in result.stdout_tail
    assert "ANTHROPIC_API_KEY" not in result.stdout_tail


def test_pythonpath_survives_scrubbing(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CT49b -- the highest-impact silent inversion in this system.

    With ``PYTHONPATH`` dropped, a verify command imports the image-baked
    ``/opt/first-agent/src`` rather than the coder's workspace edits, and the
    gate passes regardless of what was written. Removing ``PYTHONPATH`` from
    ``tools/bash_env.py:41`` must fail this test.
    """
    monkeypatch.setenv("PYTHONPATH", "/sentinel/pythonpath")

    (result,) = run_commands(("printenv PYTHONPATH",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "/sentinel/pythonpath"


def test_uv_is_pinned_to_the_workspace_venv(workspace: Path) -> None:
    """CT49e -- producer: ``_pin_uv_environment``. Removing the call makes this fail."""
    (result,) = run_commands(("printenv UV_PROJECT_ENVIRONMENT",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert Path(result.stdout_tail.strip()) == (workspace / ".venv").resolve()


def test_uv_sync_is_disabled(workspace: Path) -> None:
    """CT49e -- a verify command must not reach for a network the container lacks."""
    (result,) = run_commands(("printenv UV_NO_SYNC",), workspace=workspace)

    assert result.stdout_tail.strip() == "1"


def test_inherited_uv_project_environment_is_overridden(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CT49e -- the stale-pin hazard: another session's value must not win."""
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/sessions/some-other-session/.venv")

    (result,) = run_commands(("printenv UV_PROJECT_ENVIRONMENT",), workspace=workspace)

    assert Path(result.stdout_tail.strip()) == (workspace / ".venv").resolve()


def test_workspace_venv_bin_is_prepended_to_path(workspace: Path) -> None:
    """CT46 -- mirrors ``tools/run_bash.py:233-236``; the workspace venv wins."""
    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    (result,) = run_commands(("printenv PATH",), workspace=workspace)

    assert result.stdout_tail.strip().split(":")[0] == str(venv_bin)


def test_no_venv_directory_leaves_path_usable(workspace: Path) -> None:
    """CT46 -- a workspace without a venv must still run commands, not break."""
    (result,) = run_commands(("echo ok",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "ok"


# ── CT46: the forbidden private helper is not reused ─────────────────────────


def test_private_subprocess_fallback_is_not_reused() -> None:
    """CT46 -- ``_run_subprocess_fallback`` has write side effects a read-only gate must not have."""
    source = Path("src/fa/inner_loop/slice_verification.py").read_text(encoding="utf-8")

    assert "_run_subprocess_fallback" not in source


# ── CT49 (PRESERVATION): plan_ids stays pure ─────────────────────────────────


def test_plan_ids_remains_free_of_execution_facilities() -> None:
    """CT49 -- the extractor must not acquire the ability to run or write anything."""
    source = Path("src/fa/inner_loop/plan_ids.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "os.environ" not in source
    assert "write_text" not in source


# ── C0p: order and arity are total over arbitrary command counts ─────────────


@pytest.mark.parametrize("count", [1, 2, 5, 12])
def test_result_arity_and_order_hold_for_any_command_count(workspace: Path, count: int) -> None:
    """C0p -- one result per command, in order, with no silent coalescing."""
    commands = tuple(f"echo item{i}" for i in range(count))

    results = run_commands(commands, workspace=workspace)

    assert len(results) == count
    assert [r.command for r in results] == list(commands)
    assert [r.stdout_tail.strip() for r in results] == [f"item{i}" for i in range(count)]


# ── Mutation-driven oracles (C4 follow-up to the SLICE1 sweep) ──────────────


def test_a_command_that_cannot_be_launched_is_error_not_fail(tmp_path: Path) -> None:
    """CT45/CT46 -- producer: ``_spawn_failure_result``.

    Found by mutation testing: the whole OSError branch had no oracle, so 12
    mutants of it survived as "no tests". A session workspace pruned mid-run is
    the realistic trigger. The harness failing to ask is never the command
    refusing the work, so this must be ERROR -- collapsing it into a falsy
    value is the ``_git_output`` anti-pattern the module exists not to repeat.
    """
    missing = tmp_path / "workspace-was-pruned"

    (result,) = run_commands(("true",), workspace=missing)

    assert result.outcome is CommandOutcome.ERROR
    assert result.outcome is not CommandOutcome.FAIL
    assert result.exit_code is None
    assert "could not start" in result.stderr_tail
    assert result.command == "true"
    assert result.stdout_tail == "", "a command that never ran produced no output"
    assert 0.0 <= result.duration_s < 60.0


def test_invalid_utf8_output_is_tolerated_not_raised(workspace: Path) -> None:
    """CT44 -- producer: the ``errors="ignore"`` argument in ``_tail``.

    Found by mutation testing: dropping the handler, or mis-casing it to
    ``"IGNORE"`` (handler names, unlike codec names, are case-sensitive), both
    survived. Losing a byte must beat raising while reporting someone else's
    failure.
    """
    # Octal, not ``\xff``: /bin/sh is dash here and dash's printf does not
    # implement \xHH -- it emits the literal text, so the hex form never puts
    # an invalid byte on the pipe and proves nothing. Measured, not assumed.
    (result,) = run_commands((r"printf 'ok\377\376'",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert "ok" in result.stdout_tail


def test_output_longer_than_the_tail_limit_is_truncated(workspace: Path) -> None:
    """CT44 -- an unbounded test log would evict the diff the judge needs."""
    (result,) = run_commands((f"printf 'x%.0s' $(seq 1 {TAIL_LIMIT * 2})",), workspace=workspace)

    assert len(result.stdout_tail) == TAIL_LIMIT


def test_duration_is_elapsed_time_not_a_clock_reading(workspace: Path) -> None:
    """CT49d -- producer: the ``- started`` subtraction in ``_run_one``.

    Found by mutation testing: flipping it to ``+ started`` survived, because
    no oracle bounded the duration of a *successful* command. A monotonic clock
    reading is a large number; elapsed time for ``true`` is near zero.
    """
    (result,) = run_commands(("true",), workspace=workspace)

    assert 0.0 <= result.duration_s < 60.0


def test_a_command_never_started_reports_zero_cost(workspace: Path) -> None:
    """CT47 -- producer: ``duration_s=0.0`` in ``_deadline_result``.

    A command that did not run must not appear to have consumed time, or the
    operator's cost data for the live run is a fabrication.
    """
    past = time.monotonic() - 1.0

    (result,) = run_commands(("sleep 99",), workspace=workspace, deadline=past)

    assert result.duration_s == 0.0
    assert result.stdout_tail == ""


def test_timeout_reports_no_stdout(workspace: Path) -> None:
    """CT45 -- a killed command has no trustworthy stdout to report."""
    (result,) = run_commands(("sleep 5",), workspace=workspace, timeout_s=0.5)

    assert result.stdout_tail == ""


def test_inherited_path_survives_the_venv_prepend(workspace: Path) -> None:
    """CT46 -- producer: the ``'PATH'`` key in ``_build_env``'s lookup.

    Found by mutation testing: lower-casing the key to ``'path'`` survived,
    because the existing oracle only checked the FIRST path element. That
    mutant silently discards the inherited PATH and replaces it with
    ``os.defpath``, so ``uv``, ``git`` and the system tools disappear.
    """
    # Differential, not a restatement of the implementation: measure the PATH a
    # command sees with no workspace venv, then assert the venv case is exactly
    # that value with one entry prepended. A mutant that mis-spells the lookup
    # key silently swaps the inherited PATH for ``os.defpath``; only comparing
    # against the real baseline catches it.
    (baseline,) = run_commands(("printenv PATH",), workspace=workspace)
    inherited = baseline.stdout_tail.strip()
    assert inherited, "precondition: the scrubbed environment carries a PATH"

    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    (result,) = run_commands(("printenv PATH",), workspace=workspace)

    assert result.stdout_tail.strip() == f"{venv_bin}{os.pathsep}{inherited}"


def test_results_are_immutable(workspace: Path) -> None:
    """C0 -- a verdict a caller can edit after the fact is not evidence."""
    (result,) = run_commands(("true",), workspace=workspace)

    assert isinstance(result, CommandResult)
    with pytest.raises((AttributeError, TypeError)):
        result.exit_code = 99  # type: ignore[misc]
