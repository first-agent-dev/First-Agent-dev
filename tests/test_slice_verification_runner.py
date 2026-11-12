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
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fa.execution.client import (
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.primitives import ExecutionContractError
from fa.inner_loop.slice_verification import (
    DEFAULT_VERIFY_TIMEOUT_SECONDS,
    JUNIT_BLOCK_END,
    JUNIT_BLOCK_START,
    TAIL_LIMIT,
    CommandOutcome,
    CommandResult,
    ManagedVerifyCommandExecutor,
    _junit_block,
    _with_markers,
    build_env,
    capture_test_nodeids,
    run_commands,
)
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from fa.runtime.pty_pool import PtyResult


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
    assert result.outcome not in {CommandOutcome.PASS}
    assert result.outcome not in {CommandOutcome.FAIL}
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
    results: tuple[CommandResult, ...] = run_commands([], workspace=workspace)

    assert not any(r.outcome is CommandOutcome.ERROR for r in results)
    assert results == ()


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
    assert result.outcome not in {CommandOutcome.FAIL}
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


# ── R24/Q140: the substrate seam ──────────────────────────────────────────────


class _RecordingExecutor:
    """A substrate that records what it was asked to run and answers in the gate's vocabulary."""

    def __init__(self, outcome: CommandOutcome = CommandOutcome.PASS, exit_code: int = 0) -> None:
        self.calls: list[tuple[str, Path, float, dict[str, str]]] = []
        self._outcome = outcome
        self._exit_code = exit_code

    def run_verify_command(self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]) -> CommandResult:
        self.calls.append((command, cwd, timeout_s, env))
        return CommandResult(
            command=command,
            outcome=self._outcome,
            exit_code=self._exit_code,
            stdout_tail="managed",
            stderr_tail="",
            duration_s=0.0,
        )


def test_an_injected_executor_replaces_the_host_shell_entirely(workspace: Path) -> None:
    """C1 — the seam, proved by absence: no host process runs when an executor is given.

    R24's whole point is that a managed run must not verify the host tree. The
    assertion that proves it is not "the executor was called" — that would pass
    even if the host shell ran first — but that the host produced *nothing*: the
    marker file a shell command would create never appears.
    """
    executor = _RecordingExecutor()
    marker = workspace / "host-shell-ran"

    (result,) = run_commands((f"touch {marker}; echo host",), workspace=workspace, executor=executor)

    assert executor.calls and executor.calls[0][0] == f"touch {marker}; echo host"
    assert result.stdout_tail == "managed"  # the executor's verdict, not the shell's
    assert not marker.exists()  # the host shell never ran


def test_the_executor_receives_the_same_command_cwd_budget_and_environment(workspace: Path) -> None:
    """C1 — interchangeable substrates: the seam must not quietly rewrite its inputs.

    If the managed path received a different cwd or a trimmed environment, a
    verify command could pass on the authority and fail on the host (or worse,
    pass in both for different reasons). The comparison is against the host run
    itself, so it pins equivalence rather than a hard-coded expectation.
    """
    (host,) = run_commands(("true",), workspace=workspace)
    executor = _RecordingExecutor()

    run_commands(("true",), workspace=workspace, timeout_s=42.0, executor=executor)

    command, cwd, timeout_s, env = executor.calls[0]
    assert command == "true"
    # CT49c: the working directory is the caller's path verbatim, not a resolved
    # one -- resolving here would let a symlinked session workspace run commands
    # in a tree the coder never saw.
    assert cwd == Path(workspace)
    assert timeout_s == 42.0
    # The environment is the assembled one, not an empty dict and not the raw
    # parent environment: both substrates receive the same scrubbed overlay.
    assert env
    assert env == build_env(workspace)  # the same assembled overlay the host path uses
    assert host.outcome is CommandOutcome.PASS


def test_an_executor_failure_is_reported_and_never_becomes_a_pass(workspace: Path) -> None:
    """EDGE — the substrate's own ERROR stays an ERROR; a gate cannot out-vote its runner."""
    executor = _RecordingExecutor(outcome=CommandOutcome.ERROR, exit_code=0)

    (result,) = run_commands(("true",), workspace=workspace, executor=executor)

    # exit_code 0 from a broken substrate must not be read as a pass.
    assert result.outcome is CommandOutcome.ERROR


def test_the_default_substrate_is_unchanged_when_no_executor_is_given(workspace: Path) -> None:
    """C0 — negative proof for the seam: existing callers keep the host behaviour."""
    (result,) = run_commands(("echo default-host",), workspace=workspace)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "default-host"


def test_a_symlinked_workspace_is_passed_through_unresolved(tmp_path: Path) -> None:
    """CT49c at the seam: the executor must see the path the caller named.

    Resolving here is not cosmetic. A session workspace reached through a symlink
    (an operator's mounted path, a migrated home) resolves to a *different* host
    path; a managed substrate authorized for the named path would then be asked to
    run in one nobody admitted. The oracle needs a real symlink, because on an
    ordinary tmp_path the two spellings are identical and a mutant that resolves
    would survive.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    executor = _RecordingExecutor()

    run_commands(("true",), workspace=link, executor=executor)

    _command, cwd, _timeout, _env = executor.calls[0]
    assert cwd == link
    assert cwd != real.resolve()  # the distinction the oracle exists to make


# ── R24/Q140: verify on the authority, read-only ─────────────────────────────


class _FakeManagedExecutor:
    """Stands in for ``ReadOnlyManagedBashExecutor``: records the call, returns a result."""

    interactive = False

    def __init__(self, *, exit_code: int = 0, timed_out: bool = False, truncated: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self._result = PtyResult(
            stdout="managed stdout",
            exit_code=exit_code,
            truncated=truncated,
            session_id="",
            timed_out=timed_out,
        )

    def run(
        self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str | None = None
    ) -> PtyResult:
        self.calls.append({"command": command, "timeout": timeout, "workdir": workdir, "session_id": session_id})
        return self._result


def test_managed_verify_never_opens_a_session(tmp_path: Path) -> None:
    """C1 — an interactive session would keep state between verify commands.

    ``admit`` requires ``profile.interactive == (session_id is not None)``, so a
    session id here is not merely unnecessary: the author is a non-interactive
    profile and any session id it sent would be refused.
    """
    executor = _FakeManagedExecutor()
    managed = ManagedVerifyCommandExecutor(executor, root=tmp_path)

    managed.run_verify_command("true", cwd=tmp_path, timeout_s=10.0, env={})

    assert executor.calls[0]["session_id"] is None
    assert executor.calls[0]["workdir"] == tmp_path
    assert executor.calls[0]["timeout"] == 10


def test_managed_verify_rounds_a_fractional_budget_up_never_down(tmp_path: Path) -> None:
    """EDGE — ``ceil``, not ``int``: rounding a 0.4s budget down to 0 would refuse a valid run."""
    executor = _FakeManagedExecutor()
    managed = ManagedVerifyCommandExecutor(executor, root=tmp_path)

    managed.run_verify_command("true", cwd=tmp_path, timeout_s=0.4, env={})
    managed.run_verify_command("true", cwd=tmp_path, timeout_s=2.7, env={})

    # 0.4 -> 1 (int would give 0, i.e. a refused run); 2.7 -> 3 (int would give 2,
    # i.e. a command killed early for no reason).
    assert [call["timeout"] for call in executor.calls] == [1, 3]


def test_managed_verify_maps_exit_codes_without_inventing_a_pass(tmp_path: Path) -> None:
    """C1 — the three-outcome vocabulary, on the managed substrate."""
    managed = ManagedVerifyCommandExecutor(_FakeManagedExecutor(exit_code=0), root=tmp_path)
    (passed,) = run_commands(("true",), workspace=tmp_path, executor=managed)
    assert passed.outcome is CommandOutcome.PASS

    managed = ManagedVerifyCommandExecutor(_FakeManagedExecutor(exit_code=7), root=tmp_path)
    (failed,) = run_commands(("false",), workspace=tmp_path, executor=managed)
    assert failed.outcome is CommandOutcome.FAIL
    assert failed.exit_code == 7


def test_a_managed_timeout_is_error_and_not_a_failure_verdict(tmp_path: Path) -> None:
    """C1 — a killed command did not refuse the work; the budget ran out."""
    managed = ManagedVerifyCommandExecutor(_FakeManagedExecutor(timed_out=True, exit_code=0), root=tmp_path)

    (result,) = run_commands(("slow",), workspace=tmp_path, executor=managed)

    assert result.outcome is CommandOutcome.ERROR
    assert result.exit_code is None
    assert "budget" in result.stderr_tail


def test_truncated_managed_output_cannot_prove_a_pass(tmp_path: Path) -> None:
    """EDGE — the failure may be in the part that was cut off."""
    managed = ManagedVerifyCommandExecutor(_FakeManagedExecutor(truncated=True, exit_code=0), root=tmp_path)

    (result,) = run_commands(("chatty",), workspace=tmp_path, executor=managed)

    assert result.outcome is CommandOutcome.ERROR
    assert "truncated" in result.stderr_tail


@pytest.mark.parametrize(
    "error",
    [
        ExecutionRejectedError("PATH_DENIED", "op-1"),
        ExecutionUnavailableError(),
        ExecutionUncertainError("op-1"),
        ExecutionContractError(),
    ],
)
def test_every_execution_error_becomes_error_never_pass(tmp_path: Path, error: Exception) -> None:
    """EDGE — an exception is not a verdict: ``ERROR``, and the reason is readable."""

    class _Raising:
        interactive = False

        def run(self, *_args: object, **_kwargs: object) -> PtyResult:
            raise error

    managed = ManagedVerifyCommandExecutor(_Raising(), root=tmp_path)

    (result,) = run_commands(("true",), workspace=tmp_path, executor=managed)

    assert result.outcome is CommandOutcome.ERROR
    assert result.exit_code is None
    assert type(error).__name__ in result.stderr_tail


def test_a_managed_executor_needs_an_absolute_controller_root(tmp_path: Path) -> None:
    """C0 — a relative or traversing root could escape the admitted workspace."""
    with pytest.raises(ExecutionContractError):
        ManagedVerifyCommandExecutor(_FakeManagedExecutor(), root=Path("relative/path"))
    with pytest.raises(ExecutionContractError):
        ManagedVerifyCommandExecutor(_FakeManagedExecutor(), root=Path("/a/../b"))


def test_managed_verify_leaves_no_host_trace(tmp_path: Path) -> None:
    """C1 — negative proof: the same proof shape as the host seam, on the managed path.

    The marker a host shell would create must not exist, because the whole point of
    Q140 is that a verify command runs on the authority and not on this machine.
    """
    marker = tmp_path / "host-shell-ran"
    managed = ManagedVerifyCommandExecutor(_FakeManagedExecutor(), root=tmp_path)

    run_commands((f"touch {marker}",), workspace=tmp_path, executor=managed)

    assert not marker.exists()


# ── Q142 option A: the report travels in the receipt ─────────────────────────


def _inband_executor(*, writes_visible: bool, prepared: dict[str, Path] | None = None) -> object:
    """A substrate that answers the in-band command with a real JUnit report in stdout."""

    class _InBand:
        writes_are_visible = writes_visible

        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            del timeout_s, env
            report = Path(command.rsplit("--junitxml=", 1)[1].split(" ", 1)[0].strip("'"))
            report.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                command.replace("python -m pytest", f"{sys.executable} -m pytest"),
                shell=True,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
            )
            if prepared is not None:
                prepared["report"] = report
            body = report.read_text(encoding="utf-8") if report.exists() else ""
            return CommandResult(
                command=command,
                outcome=CommandOutcome.PASS,
                exit_code=0,
                stdout_tail=f"{JUNIT_BLOCK_START}\n{body}\n{JUNIT_BLOCK_END}\n",
                stderr_tail="",
                duration_s=0.0,
            )

    return _InBand()


def test_the_inband_block_round_trips_a_real_report(tmp_path: Path) -> None:
    """C1 — the whole loop: a real pytest run, a real report, carried and parsed."""
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    executor = _inband_executor(writes_visible=False)

    capture = capture_test_nodeids(("test_sample.py",), root=tmp_path, executor=executor)

    assert capture.nodeids == {"test_sample.py::test_ok": True}


def _sample_report(nodeid: str) -> str:
    """A smallest-possible report the real parser accepts: proves the markers, not pytest."""
    return (
        '<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0">'
        f'<testcase classname="x" name="y"><properties>'
        f'<property name="fa_pytest_nodeid" value="{nodeid}"/>'
        "</properties></testcase></testsuite>"
    )


def test_the_block_markers_survive_arbitrary_test_output(tmp_path: Path) -> None:
    """EDGE — the report is found even when the run prints its own noise first."""
    body = _sample_report("test_sample.py::test_ok")
    tail = f"some test log\n{JUNIT_BLOCK_START}\n{body}\n{JUNIT_BLOCK_END}\nmore noise\n"

    carried, detail = _junit_block(tail)

    assert detail == ""
    assert carried is not None
    assert b"test_sample.py::test_ok" in carried


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("no markers at all", "expected one block"),
        (f"{JUNIT_BLOCK_START}\n<testsuite/>\n", "expected one block"),
        (f"{JUNIT_BLOCK_START}\n<testsuite/>\n{JUNIT_BLOCK_END}\n" * 2, "expected one block"),
        (f"{JUNIT_BLOCK_START}\n{JUNIT_BLOCK_END}", "empty"),
    ],
)
def test_a_malformed_inband_block_is_refused_not_guessed(tail: str, expected: str) -> None:
    """EDGE — every unusable shape names its defect, and none of them becomes a report."""
    carried, detail = _junit_block(tail)

    assert carried is None
    assert expected in detail


def test_a_missing_block_never_becomes_an_empty_t0(tmp_path: Path) -> None:
    """C1 — no report is ``None``, not ``{}``: silence must not read as "no tests failed"."""

    class _NoBlock:
        writes_are_visible = False

        def run_verify_command(self, command: str, **_kwargs: object) -> CommandResult:
            return CommandResult(command, CommandOutcome.PASS, 0, "plain log", "", 0.0)

    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    capture = capture_test_nodeids(("test_sample.py",), root=tmp_path, executor=_NoBlock())

    assert capture.nodeids is None
    assert "markers" in capture.detail


def test_a_path_the_snapshot_cannot_read_is_absent_and_not_an_error(tmp_path: Path) -> None:
    """C1 — absence and refusal are one answer, and that answer is not "unproven".

    The port does not disclose whether a path exists (``workspace_port.py:35-39``), so
    a declared test file that is not in the snapshot arrives as a refusal. The gate's
    documented behaviour is that an absent path contributes no rows; upgrading the
    refusal to "unproven" made every managed slice whose test file lives elsewhere
    block the run, which is how this was found (a real workflow oracle went red).
    """

    class _EmptySnapshot:
        def read_file(self, *_args: object, **_kwargs: object) -> object:
            raise WorkspacePortError("denied")

    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    capture = capture_test_nodeids(
        ("test_missing.py",), root=tmp_path, executor=_inband_executor(writes_visible=False), port=_EmptySnapshot()
    )

    assert capture.nodeids == {}
    assert "no declared TESTS path" in capture.detail


def test_a_confirmed_snapshot_path_runs_and_reports(tmp_path: Path) -> None:
    """C1 — the positive half: a path the snapshot can read is a path that gets run."""
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    class _Snapshot:
        def read_file(self, path: str, **_kwargs: object) -> object:
            if (tmp_path / path).is_file():
                return object()
            raise WorkspacePortError("refused")

    capture = capture_test_nodeids(
        ("test_sample.py",), root=tmp_path, executor=_inband_executor(writes_visible=False), port=_Snapshot()
    )

    assert capture.nodeids == {"test_sample.py::test_ok": True}


def test_managed_markers_travel_as_a_command_prefix_never_as_environment() -> None:
    """C1 — the recursion guard reaches the managed command, and only the markers do."""
    prefixed = _with_markers("true", {"FA_VERIFY_GATE_TEST_DEPTH": "2", "PATH": "/host/bin", "HOME": "/home/x"})

    assert prefixed.startswith("FA_VERIFY_GATE_TEST_DEPTH=2 ")
    assert "PATH=" not in prefixed
    assert "HOME=" not in prefixed
    assert prefixed.endswith(" true")

    # The same property through the executor, which is where a wholesale forward would
    # actually go wrong: the cell would inherit a controller HOME and PATH.
    executor = _FakeManagedExecutor()
    managed = ManagedVerifyCommandExecutor(executor, root=Path("/tmp"))
    managed.run_verify_command(
        "true", cwd=Path("/tmp"), timeout_s=5.0, env={"FA_VERIFY_GATE_TEST_DEPTH": "2", "PATH": "/host/bin"}
    )
    sent = executor.calls[0]["command"]
    assert isinstance(sent, str)
    assert sent.startswith("FA_VERIFY_GATE_TEST_DEPTH=2 ")
    assert "PATH=" not in sent


def test_a_marker_value_cannot_become_shell_syntax() -> None:
    """EDGE — quoted, so a value is a value even if it one day carries model text."""
    prefixed = _with_markers("true", {"FA_VERIFY_JUNIT_RUN_ID": "$(id); rm -rf /"})

    assert "'" in prefixed
    assert "$(id)" not in prefixed.replace("'$(id); rm -rf /'", "")


def test_a_host_present_path_absent_from_the_snapshot_is_not_run(tmp_path: Path) -> None:
    """C1 — the false pass Q142 found, stated positively.

    The file exists on the controller host but not in the snapshot under judgement.
    A host check would run it (and report on the wrong tree); the port must not. This
    is the only case that distinguishes the two, which is why the composition oracle
    cannot catch it — its declared test path exists in neither place.
    """
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    class _SnapshotWithoutIt:
        def read_file(self, *_args: object, **_kwargs: object) -> object:
            raise WorkspacePortError("denied")

    capture = capture_test_nodeids(
        ("test_sample.py",), root=tmp_path, executor=_inband_executor(writes_visible=False), port=_SnapshotWithoutIt()
    )

    assert capture.nodeids == {}
    assert "test_sample.py::test_ok" not in str(capture.nodeids)
