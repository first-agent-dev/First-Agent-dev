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
import re
import subprocess
import time
from collections.abc import Iterable, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fa.inner_loop.plan_ids import FAIL, PlanDiagnostic, PlanIds, SliceRecord
from fa.inner_loop.tools.bash_env import build_scrubbed_env

__all__ = [
    "DEFAULT_VERIFY_TIMEOUT_SECONDS",
    "TAIL_LIMIT",
    "CommandOutcome",
    "CommandResult",
    "KillDirective",
    "KillOperator",
    "parse_kill_directives",
    "run_commands",
    "validate_kill_directives",
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


# --------------------------------------------------------------------------- #
# SLICE2 -- kill directives: strict parse, loud failure.
#
# A contract's kill-check is the only thing standing between "the tests are
# green" and "the tests are green AND they would notice if the feature were
# deleted". A directive that fails to parse therefore cannot be allowed to read
# as "the planner declared none": that silently disables the non-vacuity gate,
# which is the precise failure this project exists to prevent. Every ambiguous
# shape below is an error with a line number, never a shrug.
#
# Why the directive is read from ``section()`` and not from the contract body
# (E123): ``_section_contracts`` joins continuation lines with single spaces, so
# in the body the line boundary is gone. Measured over six cases, four degraded
# to "no kill-check found" -- including the common one where prose follows the
# directive. The raw section keeps newlines, so attribution is exact and
# trailing prose is harmless.
# --------------------------------------------------------------------------- #


class KillOperator(enum.StrEnum):
    """The two mutation operators a contract may declare. (CT50)

    Deliberately two. Every additional operator is another way for a plan to
    describe a mutation the engine cannot perform, and the two here already
    span the failure modes worth proving: ``NEUTRALISE`` asks "would anything
    notice if this function stopped working?", ``REMOVE_CALL`` asks "would
    anything notice if this call site disappeared?".
    """

    NEUTRALISE = "neutralise"
    REMOVE_CALL = "remove-call"


@dataclass(frozen=True, slots=True)
class KillDirective:
    """One parsed ``kill:`` line.

    ``callee`` is ``None`` for ``NEUTRALISE`` (which needs no second symbol)
    and the called name for ``REMOVE_CALL``.

    ``line`` is 1-based and **relative to the text it was parsed from** --
    a section, not the file. Absolute positions belong to diagnostics, which
    :func:`validate_kill_directives` produces from the whole document; keeping
    the two apart is what lets parsing stay pure and reusable (CT53).
    """

    operator: KillOperator
    path: str
    symbol: str
    callee: str | None
    line: int


#: The only shape accepted. Anchored at both ends so a directive cannot absorb
#: trailing prose, which is safe here only because the section preserves lines.
_KILL_STRICT_RE = re.compile(
    r"^\s*kill:\s*(?P<operator>neutralise|remove-call)\s+(?P<path>\S+)::(?P<symbol>\S+?)"
    r"(?:\s*->\s*(?P<callee>\S+))?\s*$"
)

#: "This line claims to be a directive." Anything matching this but not the
#: strict form is malformed -- a loud error, never a silent absence.
_KILL_SOFT_RE = re.compile(r"^\s*kill:")

#: Typos that read as a directive to a human and as prose to the strict form:
#: ``kil:``, ``Kill :``, ``kill-check:``. Fires only when the soft form does
#: not, so one line is never reported twice.
_KILL_NEAR_MISS_RE = re.compile(r"^\s*ki?ll?[-_ ]?(?:check)?\s*:", re.IGNORECASE)


def _split_dotted(symbol: str) -> tuple[str, ...]:
    """Split a directive symbol into its dotted parts. (CT50b)

    ``"f"`` -> ``("f",)``; ``"Class.method"`` -> ``("Class", "method")``.

    Exists because a bare-name grammar cannot express a method. Found by
    auditing this plan's own directives: three of them name
    ``_Silence.visit_Call``, which under a bare-name reader resolves to
    nothing and reports ``PRODUCER_ABSENT`` against working code -- a false
    accusation that looks exactly like a real one.
    """
    return tuple(part for part in symbol.split(".") if part)


def _owner_at(sites: tuple[tuple[int, str], ...], line: int) -> str | None:
    """The contract whose declaration most recently preceded *line*.

    *sites* is ``(line, contract id)`` ascending, as I01 reported it. A
    directive belongs to the entry it is written under, so the owner is the
    last declaration at or above it; ``None`` means the line sits before any
    declaration and belongs to no contract.

    This module deliberately holds no opinion about what a contract looks
    like. It once did -- a regex mirroring I01's -- and the two disagreed
    about unclassed entries, which cost a correct plan a false accusation
    (E152). Positions come from the parser that read the document; this
    function only does arithmetic on them.
    """
    owner: str | None = None
    for site_line, contract_id in sites:
        if site_line > line:
            break
        owner = contract_id
    return owner


def _scan_directives(section: str, sites: tuple[tuple[int, str], ...]) -> list[tuple[str | None, KillDirective]]:
    """Every strict directive in *section*, in order, with its owning contract.

    Returns a list rather than a mapping because duplicate attribution is a
    diagnosable condition (CT52's ``kill-directive-ambiguous``) and a mapping
    would destroy the evidence for it.
    """
    found: list[tuple[str | None, KillDirective]] = []
    for index, line in enumerate(section.splitlines(), start=1):
        match = _KILL_STRICT_RE.match(line)
        if match is None:
            continue
        found.append(
            (
                _owner_at(sites, index),
                KillDirective(
                    operator=KillOperator(match.group("operator")),
                    path=match.group("path"),
                    symbol=match.group("symbol"),
                    callee=match.group("callee"),
                    line=index,
                ),
            )
        )
    return found


def parse_kill_directives(record: SliceRecord) -> dict[str, KillDirective]:
    """Read one slice's directives from the record I01 produced, by contract.

    CT50. Takes the :class:`SliceRecord` rather than loose text because
    attribution needs two things that only I01 can answer together: the raw
    section (the joined contract body loses the line structure directives live
    on) and where each contract was declared. Passing the record keeps both
    from one parse, so there is no second grammar to drift.

    A contract declaring two directives keeps its **first** here, so this
    accessor stays total and deterministic; reporting the duplicate is
    :func:`validate_kill_directives`' job, not this function's -- the same
    division I01 draws between ``contract_class`` and the duplicate-id rule.
    """
    sites = tuple(sorted((line - record.start_line + 1, contract_id) for contract_id, line in record.contract_lines))
    out: dict[str, KillDirective] = {}
    for contract_id, directive in _scan_directives(record.section, sites):
        if contract_id is None or contract_id in out:
            continue
        out[contract_id] = directive
    return out


def _near_miss(line: str, index: int, path: str) -> PlanDiagnostic | None:
    """A line that reads as a kill directive to a human but not to the parser. (CT51)

    ``kil:``, ``Kill :``, ``kill-check:``. Without this rule each of them
    presents as "the planner declared no kill-check", which is indistinguishable
    from a contract that legitimately has none -- so a typo would silently
    switch off the non-vacuity gate for that contract. Same reasoning, and same
    shape, as ``heading-near-miss`` (CT26) and ``step-near-miss`` (CT37).

    Returns ``None`` when the line is a well-formed claim; the strict reader
    deals with it, and reporting it here too would double-count one mistake.
    """
    if not _KILL_NEAR_MISS_RE.match(line) or _KILL_SOFT_RE.match(line):
        return None
    return PlanDiagnostic(
        rule="kill-directive-near-miss",
        severity=FAIL,
        path=path,
        line=index,
        message=(
            f"{line.strip()!r} reads as a kill directive but is not one; "
            f"write 'kill: <neutralise|remove-call> <path>::<symbol>[ -> <callee>]', "
            f"because a near-miss is indistinguishable from declaring none"
        ),
    )


def validate_kill_directives(plan_text: str, ids: PlanIds, *, path: str) -> list[PlanDiagnostic]:
    """Check every contract's kill directive before the coder starts. (CT52, CT54)

    Pure: no filesystem, no subprocess, stdlib only, so this can run at
    admission (CT53). A malformed directive discovered after the coder has
    worked is a bill, not a gate.

    Four conditions, each a ``FAIL`` naming ``file:line``:

    ``kill-directive-near-miss``
        a typo'd keyword (CT51).
    ``kill-directive-malformed``
        a line that claims to be a directive and does not parse.
    ``kill-directive-ambiguous``
        two or more directives on one contract, where the engine would
        otherwise silently honour one and drop the other.
    ``kill-directive-missing``
        a ``FUNCTIONAL`` contract with no directive at all.

    ``CONSTRAINT`` and ``PRESERVATION`` contracts are exempt (CT54): their
    proof is an existing test or an absence, and demanding a mutation of them
    would manufacture ceremony rather than evidence.

    Line numbers are absolute, taken from one pass over the whole document --
    the same approach ``_rule_step_near_miss`` takes and for the same reason
    (Q44 option (i)). What counts as a contract, and of what class, is asked of
    *ids*; this function only locates ids that I01 already declared.
    """
    out: list[PlanDiagnostic] = []
    directive_lines: dict[str, list[int]] = {}
    attempted: set[str] = set()
    # Declaration positions as I01 reported them, document-absolute. Only
    # declared contracts appear, so an id this plan merely cites can never
    # capture a directive written under something else.
    sites = tuple(
        sorted((line, contract_id) for record in ids.slice_records for contract_id, line in record.contract_lines)
    )

    for index, line in enumerate(plan_text.splitlines(), start=1):
        current = _owner_at(sites, index)

        near = _near_miss(line, index, path)
        if near is not None:
            out.append(near)
            continue

        if not _KILL_SOFT_RE.match(line):
            continue
        if current is not None:
            attempted.add(current)

        if _KILL_STRICT_RE.match(line) is None:
            out.append(
                PlanDiagnostic(
                    rule="kill-directive-malformed",
                    severity=FAIL,
                    path=path,
                    line=index,
                    message=(
                        f"{line.strip()!r} does not parse; expected "
                        f"'kill: <neutralise|remove-call> <path>::<symbol>[ -> <callee>]'"
                    ),
                )
            )
            continue
        if current is not None:
            directive_lines.setdefault(current, []).append(index)

    for contract_id, lines in directive_lines.items():
        if len(lines) < 2:
            continue
        out.append(
            PlanDiagnostic(
                rule="kill-directive-ambiguous",
                severity=FAIL,
                path=path,
                line=lines[1],
                message=(
                    f"{contract_id} declares {len(lines)} kill directives "
                    f"(lines {', '.join(str(n) for n in lines)}); one contract, one kill-check"
                ),
            )
        )

    # ``ids.contracts`` is every id *mentioned*, not every id declared: this
    # plan's own CT51 cites I01's CT26 and CT37 by name, and they appear here
    # too. ``contract_class`` is what separates the two -- it returns ``None``
    # for an id that is merely referenced -- so the class test below is also
    # the declaration test. Stated because the correctness is not obvious:
    # without it this rule would demand a kill directive from another
    # increment's contracts.
    for contract_id in ids.contracts:
        if ids.contract_class(contract_id) != "FUNCTIONAL":
            continue
        if contract_id in attempted:
            continue
        out.append(
            PlanDiagnostic(
                rule="kill-directive-missing",
                severity=FAIL,
                path=path,
                line=ids.contract_line(contract_id),
                message=(
                    f"{contract_id} is FUNCTIONAL and declares no kill directive; "
                    f"without one its test cannot be shown to fail when the feature is removed"
                ),
            )
        )

    return sorted(out, key=lambda diagnostic: (diagnostic.line, diagnostic.rule))
