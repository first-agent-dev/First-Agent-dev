"""Harness-side execution of the verify commands a plan slice declares.

The planner writes a ``verify`` fence per slice; until now nothing ran it, so
"the slice is done" rested on the coder's narration. This module is the first
half of the gate that replaces narration with an exit code.

Design notes that are load-bearing rather than stylistic:

* **Three outcomes, not a boolean.** ``PASS`` / ``FAIL`` / ``ERROR`` are
  distinct because "the command said no" and "the command never ran" demand
  opposite responses: the first is the coder's problem, the second is the
  harness's. Collapsing them is the specific defect ``_git_output``
  (``workflow_controller.py:401``) carries today, where ``OSError`` and
  ``SubprocessError`` both become ``None`` and read downstream as "no output".
  An ``ERROR`` here is never allowed to present as a pass.
* **The environment is computed, not inherited.** ``build_scrubbed_env``
  allowlists names; anything this gate additionally needs is *set* afterwards,
  mirroring ``tools/run_bash.py:233-246``, which prepends the workspace venv to
  ``PATH`` rather than widening the allowlist. An allowlist is for values you
  cannot know; a computed value is for the ones you can. Inheriting
  ``UV_PROJECT_ENVIRONMENT`` would import whatever the parent happened to hold,
  including a pin to a *different* session's workspace.
* **Commands run in the session workspace**, matching the agent's own shell
  (``tools/run_bash.py:240``). This is conformance with existing behaviour, not
  a new requirement: a gate that invented its own working directory would
  verify the tree FA was installed from instead of the one the coder edited.
"""

from __future__ import annotations

import enum
import os
import subprocess
import time
from collections.abc import Iterable, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fa.inner_loop.tools.bash_env import build_scrubbed_env

__all__ = [
    "DEFAULT_VERIFY_TIMEOUT_SECONDS",
    "TAIL_LIMIT",
    "CommandOutcome",
    "CommandResult",
    "run_commands",
]


#: Per-command budget for a verify command, in seconds.
#:
#: Deliberately **not** ``runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS`` (30).
#: That number sizes an interactive shell call the model issues mid-turn. A
#: verify command is a test suite, and the planner is instructed to emit
#: ``uv run pytest ...`` (``prompt.py:205-207``). Inheriting 30s would turn
#: every slow-but-correct slice into an ``ERROR``, and ``ERROR`` blocks -- so
#: the gate would reject healthy work for an environmental reason.
DEFAULT_VERIFY_TIMEOUT_SECONDS = 600.0

#: Captured output is truncated to this many characters per stream. The tails
#: travel into an eval report and an artifact file; an unbounded test log would
#: evict the diff the judge actually needs.
TAIL_LIMIT = 4000


class CommandOutcome(enum.StrEnum):
    """What happened to one verify command.

    ``StrEnum`` so the value survives ``json.dump`` unchanged -- these results
    are written to a run artifact that an operator reads after a live session.
    """

    PASS = "pass"  # noqa: S105 — an outcome name, not a credential
    FAIL = "fail"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """One command's verbatim text and what running it actually produced.

    ``exit_code`` is ``int | None`` rather than a sentinel integer: there is no
    integer that honestly means "the process never reached exit". ``None`` is
    reachable only on the ``ERROR`` paths.
    """

    command: str
    outcome: CommandOutcome
    exit_code: int | None
    stdout_tail: str
    stderr_tail: str
    duration_s: float


def _tail(raw: bytes, limit: int = TAIL_LIMIT) -> str:
    """Decode a captured stream and keep its last ``limit`` characters.

    ``errors="ignore"`` matches ``tools/run_bash.py``: a test suite may emit
    partial UTF-8 under its own truncation, and losing a byte is preferable to
    raising while reporting someone else's failure.
    """
    text = raw.decode("utf-8", errors="ignore")
    return text[-limit:]


def _command_timeout(timeout_s: float | None) -> float:
    """Resolve the per-command budget. (CT49d)"""
    if timeout_s is None:
        return DEFAULT_VERIFY_TIMEOUT_SECONDS
    return float(timeout_s)


def _workspace_cwd(workspace: Path) -> Path:
    """Resolve the directory commands run in. (CT49c)"""
    return Path(workspace)


def _pin_uv_environment(env: MutableMapping[str, str], workspace: Path) -> None:
    """Pin ``uv`` to the workspace venv and forbid it syncing. (CT49e)

    Set rather than inherited. ``UV_PROJECT_ENVIRONMENT`` is absent from the
    scrubber allowlist (``tools/bash_env.py:29-50``) and must stay absent:
    passing it through would import the parent's value, which may point at
    another session's workspace. ``UV_NO_SYNC`` keeps a verify command from
    reaching for a network the container does not have.
    """
    env["UV_PROJECT_ENVIRONMENT"] = str((workspace / ".venv").resolve())
    env["UV_NO_SYNC"] = "1"


def _build_env(workspace: Path) -> dict[str, str]:
    """Build the scrubbed, workspace-pinned environment for verify commands.

    Mirrors the policy at ``tools/run_bash.py:233-246``. ``PYTHONPATH`` is
    allowlisted upstream (``tools/bash_env.py:41``) and must survive: without
    it a verify command imports the image-baked ``/opt/first-agent/src``
    instead of the coder's workspace edits, and the gate would pass whatever
    the coder wrote.
    """
    env = build_scrubbed_env(os.environ)
    venv_bin = workspace / ".venv" / "bin"
    if venv_bin.is_dir():
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', os.defpath)}"
    _pin_uv_environment(env, workspace)
    return env


def _timeout_result(command: str, *, elapsed_s: float, timeout_s: float) -> CommandResult:
    """Build the result for a command killed by its own budget. (CT45)"""
    return CommandResult(
        command=command,
        outcome=CommandOutcome.ERROR,
        exit_code=None,
        stdout_tail="",
        stderr_tail=f"verify: command exceeded its {timeout_s:g}s budget and was killed",
        duration_s=elapsed_s,
    )


def _deadline_result(command: str) -> CommandResult:
    """Build the result for a command never started, the run budget being gone. (CT47)"""
    return CommandResult(
        command=command,
        outcome=CommandOutcome.ERROR,
        exit_code=None,
        stdout_tail="",
        stderr_tail="verify: run deadline exceeded; command was not started",
        duration_s=0.0,
    )


def _spawn_failure_result(command: str, *, error: OSError, elapsed_s: float) -> CommandResult:
    """Build the result for a command that could not be launched at all.

    Explicitly ``ERROR`` and never ``FAIL``: the command did not refuse the
    work, the harness failed to ask. Swallowing this into a falsy value is the
    ``_git_output`` anti-pattern this module exists not to repeat.
    """
    return CommandResult(
        command=command,
        outcome=CommandOutcome.ERROR,
        exit_code=None,
        stdout_tail="",
        stderr_tail=f"verify: could not start command: {error}",
        duration_s=elapsed_s,
    )


def _empty_result() -> tuple[CommandResult, ...]:
    """No commands declared is not a failure. (CT48)"""
    return ()


def _run_one(command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]) -> CommandResult:
    """Run one command and classify the outcome."""
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S602 — the verify fence is planner-authored shell, by contract
            command,
            cwd=cwd,
            shell=True,
            check=False,
            capture_output=True,
            text=False,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return _timeout_result(command, elapsed_s=time.monotonic() - started, timeout_s=timeout_s)
    except OSError as error:
        return _spawn_failure_result(command, error=error, elapsed_s=time.monotonic() - started)

    code = completed.returncode
    return CommandResult(
        command=command,
        outcome=CommandOutcome.PASS if code == 0 else CommandOutcome.FAIL,
        exit_code=code,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
        duration_s=time.monotonic() - started,
    )


def run_commands(
    commands: Iterable[str],
    *,
    workspace: Path,
    timeout_s: float | None = None,
    deadline: float | None = None,
) -> tuple[CommandResult, ...]:
    """Run a slice's verify commands in order and report what each did.

    ``deadline`` is a ``time.monotonic`` instant, never a wall-clock one, so a
    system clock adjustment mid-run cannot extend or collapse the budget --
    the same reasoning as ``workflow_controller._deadline_exceeded``.

    Returns one :class:`CommandResult` per input command, in input order, so a
    caller can attribute a failure to the exact command the plan declared.
    """
    ordered: Sequence[str] = tuple(commands)
    if not ordered:
        return _empty_result()

    cwd = _workspace_cwd(workspace)
    env = _build_env(workspace)
    budget = _command_timeout(timeout_s)

    results: list[CommandResult] = []
    for command in ordered:
        if deadline is not None and time.monotonic() >= deadline:
            results.append(_deadline_result(command))
            continue
        results.append(_run_one(command, cwd=cwd, timeout_s=budget, env=env))
    return tuple(results)
