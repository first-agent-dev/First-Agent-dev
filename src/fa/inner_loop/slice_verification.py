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

import ast
import contextlib
import enum
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, override
from xml.etree import ElementTree

from fa.inner_loop.junit_nodeid_plugin import JUNIT_NODEID_PROPERTY
from fa.inner_loop.plan_ids import FAIL, PlanDiagnostic, PlanIds, SliceRecord
from fa.inner_loop.tools.bash_env import build_scrubbed_env

__all__ = [
    "DEFAULT_PROBE_TIMEOUT_SECONDS",
    "DEFAULT_VERIFY_TIMEOUT_SECONDS",
    "KILL_CHECK_COMMAND",
    "KILL_CHECK_VERDICTS",
    "NODEID_CAPTURE_COMMAND",
    "TAIL_LIMIT",
    "CommandOutcome",
    "CommandResult",
    "KillApplication",
    "KillCheck",
    "KillDirective",
    "KillOperator",
    "NodeidCapture",
    "OverlayError",
    "PlanVerification",
    "SliceVerdict",
    "SliceVerification",
    "apply_kill",
    "capture_test_nodeids",
    "mutation_overlay",
    "parse_kill_directives",
    "run_commands",
    "validate_kill_directives",
    "verify_plan",
    "verify_slice",
]

logger = logging.getLogger(__name__)


#: Per-command budget for a verify command, in seconds.
#:
#: Deliberately **not** ``runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS`` (30).
#: That number sizes an interactive shell call the model issues mid-turn. A
#: verify command is a test suite, and the planner is instructed to emit
#: ``uv run pytest ...`` (``prompt.py:205-207``). Inheriting 30s would turn
#: every slow-but-correct slice into an ``ERROR``, and ``ERROR`` blocks -- so
#: the gate would reject healthy work for an environmental reason.
DEFAULT_VERIFY_TIMEOUT_SECONDS = 600.0

#: Budget for an infrastructure sanity check, in seconds. (Q46(b))
#:
#: Separate from the verify budget on purpose. 600 s sizes *work the slice
#: asked for* -- a test suite, a compile, a heavy check. A provenance probe is
#: an assertion about the execution environment ("did the overlay win the
#: import?"), and it finishes in milliseconds. Putting unrelated things on one
#: timeout is a leaky abstraction: the number can then only be tuned for one
#: of them, and here it would be tuned for the wrong one.
#:
#: 30 s is deliberately generous -- enough for a cold import on slow I/O, with
#: room to spare -- and the point is not the precision of the number but the
#: 9.5 minutes it saves when something genuinely hangs. A hang caused by an
#: agent bug happens long before there is a measured distribution to pick a
#: tighter value from, which is why this is not deferred to a later slice.
#:
#: It equals ``runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS`` by coincidence,
#: not by derivation. Do not collapse them: that constant sizes an interactive
#: shell call the model issues mid-turn, and a change made for the model's
#: benefit must not silently retune this gate's failure detection.
DEFAULT_PROBE_TIMEOUT_SECONDS = 30.0

#: Captured output is truncated to this many characters per stream. The tails
#: travel into an eval report and an artifact file; an unbounded test log would
#: evict the diff the judge actually needs.
TAIL_LIMIT = 4000

#: The JUnit adapter must carry pytest's authoritative Item.nodeid (CT68/CT69).
#: Keep this command separate from planner-authored verify fences: these are
#: harness-issued before/after snapshots, not commands the plan gets to rewrite.
NODEID_CAPTURE_COMMAND = (
    "python -m pytest {paths} -p fa.inner_loop.junit_nodeid_plugin "
    "--junitxml={report} -q"
)

_GATE_TEST_DEPTH_ENV: Final = "FA_VERIFY_GATE_TEST_DEPTH"
_GATE_KILL_CHECK_ENV: Final = "FA_VERIFY_GATE_KILL_CHECK"
_GATE_MODES: Final = frozenset({"observe", "enforce"})

#: Explicit source roots kill-checks may copy into a temporary overlay. Test
#: roots and every other workspace path stay outside the mutation surface.
_MUTATION_ROOTS: Final = frozenset({"src", "scripts"})
_OVERLAY_PROVENANCE_ERROR_MARKER: Final = "FA_MUTATION_OVERLAY_PROVENANCE_ERROR:"


def _gate_mode(value: object | None = None) -> str:
    """Resolve the workflow verification mode to the closed observe/enforce enum.

    Operators configure ``feature_flags.workflow.verify_gate.mode`` in
    ``~/.fa/config.yaml``. Missing or unreadable configuration follows the
    rollout default (``observe``); an unknown value is observable and also
    falls back to observe, never silently turning a typo into a cold blocking
    deployment. Callers may pass an already-resolved value so one workflow
    keeps a stable mode even if the config file changes mid-run.
    """
    candidate = value
    if candidate is None:
        try:
            from fa.feature_flags import load_feature_flags_from_path

            candidate = load_feature_flags_from_path().flags.workflow_verify_gate_mode
        except Exception as error:  # noqa: BLE001 — the rollout default must remain usable
            logger.warning("verification gate mode unavailable (%s); observing", error)
            candidate = "observe"
    if isinstance(candidate, str):
        normalized = candidate.strip().lower()
        if normalized in _GATE_MODES:
            return normalized
    logger.warning("unknown verification gate mode %r; observing", candidate)
    return "observe"


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


@dataclass(frozen=True, slots=True)
class NodeidCapture:
    """One harness-issued JUnit run and its exact pytest nodeid outcomes.

    ``nodeids=None`` means the report was unusable, not that no tests ran.
    ``nodeids={}`` is a valid empty snapshot, including the CT86 case where a
    declared test path does not exist yet.
    """

    nodeids: Mapping[str, bool] | None
    command_result: CommandResult | None = None
    detail: str = ""


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


def _gate_subprocess_env(
    workspace: Path,
    *,
    base_env: Mapping[str, str] | None = None,
    kill_check: bool = False,
) -> dict[str, str]:
    """Add private recursion markers to a gate-owned subprocess environment.

    The live composition test is itself one of a slice's ``TESTS:`` paths.
    The depth marker keeps a JUnit/kill-check child from recursively launching
    the same live workflow forever; the kill marker lets the outer CT71
    mutation still execute the live oracle once. These markers are computed
    after the scrubber, never inherited as ambient configuration.
    """
    env = _build_env(workspace) if base_env is None else dict(base_env)
    try:
        parent_depth = max(0, int(os.environ.get(_GATE_TEST_DEPTH_ENV, "0")))
    except ValueError:
        parent_depth = 0
    env[_GATE_TEST_DEPTH_ENV] = str(parent_depth + 1)
    env.pop(_GATE_KILL_CHECK_ENV, None)
    if kill_check:
        env[_GATE_KILL_CHECK_ENV] = "1"
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
    env: dict[str, str] | None = None,
) -> tuple[CommandResult, ...]:
    """Run a slice's verify commands in order and report what each did.

    ``deadline`` is a ``time.monotonic`` instant, never a wall-clock one, so a
    system clock adjustment mid-run cannot extend or collapse the budget --
    the same reasoning as ``workflow_controller._deadline_exceeded``.

    Returns one :class:`CommandResult` per input command, in input order, so a
    caller can attribute a failure to the exact command the plan declared.

    ``env`` is an injection seam with the production value as its default: a
    kill-check must run against the overlay, and it must otherwise be the same
    run as the verify command it is judging. Passing the environment in beats
    rebuilding it here from a flag, because the overlay environment is already
    assembled by :func:`_overlay_env` and a second assembly could drift from
    it (CT61).
    """
    ordered: Sequence[str] = tuple(commands)
    if not ordered:
        return _empty_result()

    cwd = _workspace_cwd(workspace)
    command_env = _build_env(workspace) if env is None else env
    budget = _command_timeout(timeout_s)

    results: list[CommandResult] = []
    for command in ordered:
        if deadline is not None and time.monotonic() >= deadline:
            results.append(_deadline_result(command))
            continue
        results.append(_run_one(command, cwd=cwd, timeout_s=budget, env=command_env))
    return tuple(results)


def _existing_test_paths(test_paths: Sequence[str], root: Path) -> tuple[str, ...]:
    """Keep declared pytest paths that exist at this snapshot's T0/now point."""
    existing: list[str] = []
    for raw_path in test_paths:
        path = raw_path.strip()
        if not path:
            continue
        filesystem_path = path.split("::", 1)[0]
        if (Path(root) / filesystem_path).exists():
            existing.append(path)
    return tuple(dict.fromkeys(existing))


def _parse_nodeid_report(path: Path) -> tuple[dict[str, bool] | None, str]:
    """Read exact nodeid/status rows from a harness-issued JUnitXML report."""
    try:
        xml_bytes = path.read_bytes()
    except OSError as error:
        return None, f"JUnitXML report is missing or invalid: {error}"
    upper_xml = xml_bytes.upper()
    if b"<!DOCTYPE" in upper_xml or b"<!ENTITY" in upper_xml:
        return None, "JUnitXML report contains a forbidden DTD/entity declaration"
    try:
        root = ElementTree.fromstring(xml_bytes)  # noqa: S314 — declarations are rejected above
    except ElementTree.ParseError as error:
        return None, f"JUnitXML report is missing or invalid: {error}"

    for suite in root.iter():
        if suite.tag not in {"testsuite", "testsuites"}:
            continue
        try:
            errors = int(suite.attrib.get("errors", "0"))
        except ValueError:
            return None, f"JUnitXML has an invalid errors count on <{suite.tag}>"
        if errors:
            return None, f"JUnitXML reports {errors} collection/setup error(s)"

    nodeids: dict[str, bool] = {}
    for testcase in root.iter("testcase"):
        values = [
            prop.attrib.get("value")
            for prop in testcase.findall("./properties/property")
            if prop.attrib.get("name") == JUNIT_NODEID_PROPERTY
        ]
        if len(values) != 1 or not values[0]:
            return None, f"JUnit testcase {testcase.attrib!r} has {len(values)} exact nodeid properties"
        nodeid = values[0]
        if nodeid in nodeids:
            return None, f"JUnitXML repeats pytest nodeid {nodeid!r}"
        # A skipped/xfail test is not green. The baseline comparison can then
        # distinguish red-to-red from a formerly green test that stops passing.
        nodeids[nodeid] = not any(testcase.find(tag) is not None for tag in ("failure", "error", "skipped"))
    return nodeids, ""


def capture_test_nodeids(
    test_paths: Sequence[str],
    *,
    root: Path,
    deadline: float | None = None,
) -> NodeidCapture:
    """Run existing declared tests with the exact-nodeid JUnit plugin (CT68/69).

    Paths absent at this snapshot contribute no rows rather than becoming
    false tests. A started but unusable JUnit run returns ``nodeids=None`` so
    callers classify it as ``ERROR``; a valid report with zero tests is ``{}``.
    """
    existing_paths = _existing_test_paths(test_paths, Path(root))
    if not existing_paths:
        return NodeidCapture(nodeids={}, detail="no declared TESTS path exists at this snapshot")

    with tempfile.TemporaryDirectory(prefix="fa-verify-junit-") as temporary_directory:
        report = Path(temporary_directory) / "results.xml"
        command = NODEID_CAPTURE_COMMAND.format(
            paths=shlex.join(existing_paths),
            report=shlex.quote(str(report)),
        )
        (result,) = run_commands(
            (command,),
            workspace=Path(root),
            deadline=deadline,
            env=_gate_subprocess_env(Path(root)),
        )
        if result.outcome is CommandOutcome.ERROR:
            return NodeidCapture(
                nodeids=None,
                command_result=result,
                detail=result.stderr_tail or "harness-issued JUnit run could not be completed",
            )
        nodeids, detail = _parse_nodeid_report(report)
        return NodeidCapture(nodeids=nodeids, command_result=result, detail=detail)


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


# ── SLICE4: the mutation sandbox ──────────────────────────────────────────
#
# A kill-check has to run the slice's tests against *mutated* production code
# and watch them fail. The mutation must therefore be visible to the import
# system and invisible to the operator's checkout, and those two requirements
# pull in opposite directions. Everything below exists to hold both.
#
# The measured defect this is built around (E125/D1): with the package
# installed, an absolute path sits on ``sys.path``, so running tests with
# ``cwd`` inside a mutated copy **still imports the original module**. Every
# kill-check would have passed against unmutated code, every contract would
# have been reported VACUOUS, and the gate would have blocked every correct
# slice while never once detecting a weak test. A gate that is wrong in that
# direction is worse than no gate, because it is trusted.
#
# Hence two mechanisms rather than one: ``PYTHONPATH`` prepending to make the
# overlay win, and a **mandatory provenance probe** to prove that it did.
# Relying on the prepend alone is the same silent fragility that caused the
# defect.


class OverlayError(RuntimeError):
    """A mutation overlay could not be established, so no verdict is possible.

    Raised rather than returned. A ``None`` can be ignored by a caller that
    forgets to check it, and the thing it would be ignoring is "the sandbox
    is not there" -- after which a kill-check would run against the
    operator's real tree. An exception that escapes is noisy and safe; a
    silently skipped guard is quiet and catastrophic. SLICE5 converts this
    into an ``ERROR`` verdict at the one place that assembles verdicts.
    """


def _mutation_root(rel_path: str) -> str | None:
    """The explicit workspace source root named by a kill directive. (Q54)"""
    candidate = Path(rel_path)
    if candidate.is_absolute() or len(candidate.parts) < 2 or candidate.parts[0] not in _MUTATION_ROOTS:
        return None
    return candidate.parts[0]


def _copy_src(workspace: Path, overlay_root: Path) -> Path:
    """Copy the allowlisted ``src`` and ``scripts`` trees; never tests. (CT60, CT63, Q54)

    ``src`` is required because every mutation run uses the project package.
    ``scripts`` is copied when present, as a distinct optional source root for
    workspace developer tools such as CT83. The test tree is never copied, so
    the code under test cannot rewrite its own oracle. Symlinks remain links;
    each requested target is later resolved and checked against its own root.
    """
    workspace = Path(workspace).resolve()
    copied_src: Path | None = None
    for root_name in ("src", "scripts"):
        source = workspace / root_name
        if not source.is_dir():
            if root_name == "src":
                raise OverlayError(f"no src directory to overlay at {source}")
            continue
        if source.is_symlink():
            raise OverlayError(f"workspace {root_name} source root must not be a symlink")
        if not source.resolve().is_relative_to(workspace):
            raise OverlayError(f"workspace {root_name} source root resolves outside the workspace")
        destination = Path(overlay_root) / root_name
        shutil.copytree(source, destination, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if root_name == "src":
            copied_src = destination
    if copied_src is None:
        raise OverlayError("required src root was not copied into the mutation overlay")
    return copied_src


def _overlay_target(overlay_root: Path, rel_path: str) -> Path:
    """Resolve a target inside its explicit ``src`` or ``scripts`` root. (CT60, CT63)

    Kill-directive paths are workspace-relative. Containment is checked on the
    resolved path under the root selected by the first path component, which
    rejects ``..`` and symlink escapes without allowing one source root to
    alias another. No test path, repository-root file or arbitrary sibling is
    a writable target.
    """
    try:
        candidate = Path(rel_path)
        if candidate.is_absolute():
            raise OverlayError(f"kill-directive path must be workspace-relative, got {rel_path!r}")
        source_root = _mutation_root(rel_path)
        if source_root is None:
            raise OverlayError(
                f"kill-directive path {rel_path!r} resolves outside the allowed src/scripts overlay trees"
            )
        resolved = (Path(overlay_root) / candidate).resolve()
        allowed_root = (Path(overlay_root) / source_root).resolve()
    except OverlayError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        raise OverlayError(f"unusable kill-directive path {rel_path!r}: {error}") from error
    if resolved == allowed_root or allowed_root not in resolved.parents:
        raise OverlayError(f"kill-directive path {rel_path!r} resolves outside the overlay {source_root} tree")
    return resolved

@contextlib.contextmanager
def mutation_overlay(workspace: Path, rel_path: str, mutated_source: str) -> Iterator[Path]:
    """Yield a throwaway tree holding allowlisted source roots with one file mutated. (CT60, Q54)

    The operator's checkout is never written to, and no ``git`` command is
    involved at all (CT64) -- an earlier design used ``git worktree``, which
    could not work in any case because the deployed ``/repo`` is read-only
    (E128), and which would have put a mutation one mistake away from the real
    branch.

    The tree is removed on normal exit **and** on exception. Cleanup uses
    ``ignore_errors`` so that a failure to unlink cannot replace the real
    exception travelling up the stack with a confusing one from the ``finally``
    block; the cost of that choice is a possible stray temporary directory,
    which is strictly better than losing the reason a kill-check failed.
    """
    overlay_root = Path(tempfile.mkdtemp(prefix="fa-mutation-overlay-"))
    try:
        _copy_src(workspace, overlay_root)
        target = _overlay_target(overlay_root, rel_path)
        if not target.exists():
            raise OverlayError(f"kill-directive path {rel_path!r} does not exist in the workspace source roots")
        target.write_text(mutated_source, encoding="utf-8")
        yield overlay_root
    finally:
        shutil.rmtree(overlay_root, ignore_errors=True)


def _prepend_pythonpath(env: MutableMapping[str, str], path: Path) -> None:
    """Put *path* in front of any inherited ``PYTHONPATH``. (CT61)

    Prepend, never replace. The deployed container already relies on this
    exact idiom -- ``scripts/fa-entrypoint.sh:237`` prepends
    ``<workspace>/src`` ahead of whatever it inherited -- and the inherited
    value is what makes a verify command import the coder's edits instead of
    the baked image. Replacing it would make the overlay win by deleting the
    workspace, so a kill-check would be measured against the image's code and
    report nonsense with total confidence.
    """
    inherited = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{path}{os.pathsep}{inherited}" if inherited else str(path)


def _overlay_env(
    workspace: Path,
    overlay_root: Path,
    *,
    source_root: str = "src",
) -> dict[str, str]:
    """Build the SLICE1 environment and the selected overlay import roots. (CT61, Q54)

    Every mutation keeps ``<overlay>/src`` first for FA package imports. A
    script-target mutation additionally prepends the overlay parent so
    ``import scripts.*`` resolves from its copied package. Pytest receives a
    small bootstrap plugin that puts this root ahead of the workspace during
    collection and checks the exact target module before tests execute.
    """
    if source_root not in _MUTATION_ROOTS:
        raise OverlayError(f"unsupported mutation source root {source_root!r}")
    env = _build_env(workspace)
    if source_root == "scripts":
        _prepend_pythonpath(env, overlay_root)
    _prepend_pythonpath(env, overlay_root / "src")
    if source_root == "scripts":
        env["FA_MUTATION_OVERLAY_SCRIPTS_ROOT"] = str(Path(overlay_root).resolve())
        plugin = "fa.inner_loop.overlay_pytest_plugin"
        configured = [value.strip() for value in env.get("PYTEST_PLUGINS", "").split(",") if value.strip()]
        if plugin not in configured:
            configured.insert(0, plugin)
        env["PYTEST_PLUGINS"] = ",".join(configured)
    return env


#: Proves that the target module came from its exact overlay source tree. The
#: src probe trusts the environment prepend; for scripts it simulates the
#: pytest bootstrap that must outrank the workspace-root package, then checks
#: the resolved module file against the narrower source tree.
_PROVENANCE_PROBE = (
    "import importlib,pathlib,sys;"
    "expected=pathlib.Path(sys.argv[1]).resolve();"
    "module=sys.argv[2];"
    "mode=sys.argv[3];"
    "bootstrap='from fa.inner_loop.overlay_pytest_plugin import "
    "_install_scripts_importer; _install_scripts_importer(expected)';"
    "exec(bootstrap if mode=='pytest-bootstrap' else 'pass');"
    "m=importlib.import_module(module);"
    "f=getattr(m,'__file__',None);"
    "sys.exit(0 if f and pathlib.Path(f).resolve().is_relative_to(expected) else 3)"
)

def _assert_overlay_wins(
    module: str,
    overlay_root: Path,
    env: dict[str, str],
    *,
    workspace: Path,
    source_root: str = "src",
) -> CommandResult:
    """Prove *module* resolves inside the selected overlay source root. (CT62, Q54)

    ``src`` imports resolve through the environment's ``<overlay>/src`` prepend;
    ``scripts`` uses the same meta-path finder as pytest's bootstrap. In both
    cases the resolved file must live under the exact selected source tree, so
    a sibling or the other overlay root cannot satisfy the probe.
    """
    started = time.monotonic()
    if source_root not in _MUTATION_ROOTS:
        return CommandResult(
            command="<overlay provenance probe>",
            outcome=CommandOutcome.ERROR,
            exit_code=None,
            stdout_tail="",
            stderr_tail=f"unsupported mutation source root {source_root!r}",
            duration_s=0.0,
        )
    expected_tree = (Path(overlay_root) / source_root).resolve()
    path_mode = "pytest-bootstrap" if source_root == "scripts" else "environment"
    command = (
        f"python -c {shlex.quote(_PROVENANCE_PROBE)} {shlex.quote(str(expected_tree))} "
        f"{shlex.quote(module)} {path_mode}"
    )
    probe = _run_one(
        command,
        cwd=_workspace_cwd(workspace),
        timeout_s=DEFAULT_PROBE_TIMEOUT_SECONDS,
        env=env,
    )
    if probe.outcome is CommandOutcome.PASS:
        return probe
    return CommandResult(
        command=probe.command,
        outcome=CommandOutcome.ERROR,
        exit_code=probe.exit_code,
        stdout_tail=probe.stdout_tail,
        stderr_tail=probe.stderr_tail or f"{module} did not resolve inside {expected_tree}",
        duration_s=time.monotonic() - started,
    )

# ---------------------------------------------------------------------------
# The mutation operators (SLICE3). Pure: source text in, source text out.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KillApplication:
    """What one directive did to one source text. (CT57)

    Two counts, because the caller is asking two different questions.

    ``targets``
        a question of **search**: how many definitions in the module carry the
        qualified name the directive wrote. It must be exactly 1. ``0`` means
        the plan is ahead of the code (``PRODUCER_ABSENT``); ``>1`` means the
        directive is under-specified, and picking one would be the guess this
        gate exists to refuse (``ERROR``).
    ``edits``
        a question of **transformation**: how many nodes changed. For
        ``NEUTRALISE`` it is always 1 once the target resolved. For
        ``REMOVE_CALL`` it is legitimately ``0..n`` -- one method may call the
        emitter four times, and silencing three of them would not simulate
        "the producer never ran".

    Collapsing the two into one ``hits`` was a design bug (Q47). It made the
    four-call sample CT56 exists to defend -- the slice's headline behaviour --
    report ``4`` and be rejected by its own gate as an ambiguous target.

    ``source`` is ``None`` whenever the result is not safe to run. A caller
    that ignored a failed lookup and ran the slice's tests against unmutated
    source would watch them pass and report ``VACUOUS``: a sound test accused
    of being weak, when the real story is a missing producer. The ``None``
    turns that mistake from a matter of discipline into a type error.
    """

    source: str | None
    targets: int
    edits: int

    def __post_init__(self) -> None:
        """Refuse to exist in a state that would mislead the caller.

        An assertion about *this module*, not a condition the caller handles:
        every raise here is a bug in :func:`apply_kill`. It is deliberately
        not an error channel -- ``apply_kill`` stays total, and the mapping
        onto the status lattice stays with the caller that owns the lattice.
        """
        applied = self.targets == 1 and self.edits > 0
        if applied and self.source is None:
            raise ValueError("source must be present when a kill was applied")
        if not applied and self.source is not None:
            raise ValueError("source must be None when no kill was applied")


#: The definition kinds a directive may name. A ``class`` is not among them:
#: "neutralise this class" has no meaning the operators can express, so a
#: directive naming one resolves to nothing and is reported absent.
_DEFINITION = (ast.FunctionDef, ast.AsyncFunctionDef)


def _resolve_targets(tree: ast.Module, symbol: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every definition whose qualified name is exactly *symbol*. (CT57)

    Exact and anchored at the module root, split by :func:`_split_dotted`:
    ``_Silence.visit_Call`` resolves to one method and a bare ``visit_Call``
    resolves to nothing.

    The looser rule -- match any unambiguous dotted *suffix* -- was rejected
    (Q47). It manufactures the ambiguity it then has to report, and no
    directive needs it: every one written so far already spells the name out
    in full. Under exactness a mis-spelled or under-qualified symbol lands on
    ``PRODUCER_ABSENT``, which is loud and accurate, instead of silently
    matching a same-named method on some other class.

    ``targets > 1`` therefore stays reachable only through a genuine double
    definition -- a ``try/except ImportError`` fallback, a platform-conditional
    ``def``, a redefinition bug -- which is exactly the case worth refusing.
    """
    wanted = _split_dotted(symbol)
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def walk(body: Iterable[ast.stmt], prefix: tuple[str, ...]) -> None:
        for node in body:
            if not isinstance(node, (*_DEFINITION, ast.ClassDef)):
                continue
            qualified = (*prefix, node.name)
            if qualified == wanted and isinstance(node, _DEFINITION):
                found.append(node)
            walk(node.body, qualified)

    walk(tree.body, ())
    return found


def _dotted_text(func: ast.expr) -> str | None:
    """``self.emit`` for an attribute chain, ``emit`` for a name, else None."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _dotted_text(func.value)
        return f"{base}.{func.attr}" if base is not None else None
    return None


def _callee_matches(func: ast.expr, callee: str) -> bool:
    """Does this call expression call *callee*? (CT56)

    Asymmetric with symbol resolution on purpose. A definition has one
    canonical qualified name; a call site does not -- the same function is
    reached as ``emit``, ``self.emit`` or ``mod.emit`` depending on where the
    line is written. Demanding an exact dotted match there would make most
    directives unwritable, so an undotted directive names the attribute or
    name being called, and a dotted one must match the whole dotted text.
    """
    if "." in callee:
        return _dotted_text(func) == callee
    if isinstance(func, ast.Name):
        return func.id == callee
    if isinstance(func, ast.Attribute):
        return func.attr == callee
    return False


class _Silence(ast.NodeTransformer):
    """Replace every call to one callee with the constant ``None``. (CT56)

    Replacement, not deletion of the enclosing statement. Measured on a
    four-call sample (``a = emit(x)``, ``emit(x)``, ``if emit(x):``, and a
    comprehension): removing only ``ast.Expr`` statements sees **1 of 4**,
    which reports ``PRODUCER_ABSENT`` when the producer's result is assigned
    and half-removes it otherwise. Replacing the call expression handles all
    four forms uniformly.

    A matched call is replaced whole and not descended into: its arguments
    disappear with it, which is what "the producer never ran" means -- they
    were never evaluated either.
    """

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.edits = 0

    @override
    def visit_Call(self, node: ast.Call) -> ast.AST:
        if _callee_matches(node.func, self.callee):
            self.edits += 1
            return ast.Constant(value=None)
        self.generic_visit(node)
        return node


def _neutralise_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Replace the body of *node* with ``return None``. (CT55)

    Signature, decorators and ``async`` are kept: the function must still be
    callable in every way its callers expect, and only stop working.
    """
    node.body = [ast.Return(value=ast.Constant(value=None))]
    return 1


def apply_kill(source: str, directive: KillDirective) -> KillApplication:
    """Apply one declared kill to *source*. Pure, and total. (CT55, CT57, CT58)

    Reads no file, writes no file, spawns nothing (CT58): a mutation helper
    that could be pointed at the working tree would eventually be pointed at
    the working tree. The caller stages the returned text through
    :func:`mutation_overlay`, which owns the only copy that exists on disk.

    It never raises for an input it dislikes, either. ``targets`` and ``edits``
    carry every outcome, so the caller keeps the whole status-lattice decision
    in one place instead of splitting it across a ``try`` and an ``if``.
    """
    tree = ast.parse(source)
    targets = _resolve_targets(tree, directive.symbol)
    if len(targets) != 1:
        return KillApplication(source=None, targets=len(targets), edits=0)

    target = targets[0]
    if directive.operator is KillOperator.NEUTRALISE:
        edits = _neutralise_body(target)
    elif directive.callee is None:
        # A ``remove-call`` with no ``-> callee`` names no call site, so it can
        # match nothing. The grammar makes the arrow optional because
        # ``neutralise`` has no second symbol; this is the belt for the case
        # the parser lets through.
        edits = 0
    else:
        silence = _Silence(directive.callee)
        target.body = [silence.visit(statement) for statement in target.body]
        edits = silence.edits

    if edits == 0:
        return KillApplication(source=None, targets=1, edits=0)
    ast.fix_missing_locations(tree)
    return KillApplication(source=ast.unparse(tree), targets=1, edits=edits)


# ---------------------------------------------------------------------------
# Verdict assembly (SLICE5)
# ---------------------------------------------------------------------------


class SliceVerdict(enum.StrEnum):
    """What the gate concluded about one slice. (CT65, design note §3.2)

    Seven members, and the two that look alike are the reason the project
    exists:

    ``VACUOUS``
        the producer is there and the test passes, but removing the producer
        does **not** break the test. The *test* is wrong; strengthen it.
    ``PRODUCER_ABSENT``
        the declared producer is not in the tree at all. The *feature* is
        wrong; wire it. This is the "dead code shipped as a working feature"
        detector, stated rather than inferred.

    Merging them would discard exactly the signal the gate was built for,
    because they have different causes and different repairs.
    """

    PROVEN = "proven"
    VACUOUS = "vacuous"
    PRODUCER_ABSENT = "producer_absent"
    FAILING = "failing"
    REGRESSION = "regression"
    ERROR = "error"
    SKIPPED = "skipped"


#: The members one kill-check can reach on its own. A kill-check speaks about
#: a single contract, so it cannot observe a failing verify command
#: (``FAILING``), a baseline comparison (``REGRESSION``) or a missing verify
#: block (``SKIPPED``) -- those are statements about the slice. Reusing
#: :class:`SliceVerdict` rather than minting a parallel per-contract
#: vocabulary keeps one set of words in the reports, and this constant is what
#: keeps the reuse honest.
KILL_CHECK_VERDICTS: Final = frozenset(
    {
        SliceVerdict.PROVEN,
        SliceVerdict.VACUOUS,
        SliceVerdict.PRODUCER_ABSENT,
        SliceVerdict.ERROR,
    }
)

#: How the harness invokes one contract's test. ``_build_env`` prepends the
#: workspace's ``.venv/bin``, so ``python`` selects the same interpreter
#: ``uv run`` would select once the workspace is ready. ``-q`` because only
#: the exit code is read. A module-level constant for the same reason
#: ``_PROVENANCE_PROBE`` is one: it is the seam a test substitutes to run
#: hermetically, without a flag existing in production for a test's benefit.
KILL_CHECK_COMMAND = "python -m pytest {path} -q"


@dataclass(frozen=True, slots=True)
class KillCheck:
    """What one declared kill-check did. (CT66, CT67)

    ``verdict`` is drawn from :data:`KILL_CHECK_VERDICTS`. ``detail`` is empty
    only for :attr:`SliceVerdict.PROVEN`: every other outcome has to say what
    the operator should go and look at, because a verdict a human cannot act
    on is an alarm that will be ignored.
    """

    directive: KillDirective
    verdict: SliceVerdict
    detail: str
    duration_s: float

    def __post_init__(self) -> None:
        """Refuse a verdict a kill-check cannot legitimately reach."""
        if self.verdict not in KILL_CHECK_VERDICTS:
            raise ValueError(f"{self.verdict} is not a kill-check verdict")
        if self.verdict is not SliceVerdict.PROVEN and not self.detail:
            raise ValueError(f"{self.verdict} must say what went wrong")


def _module_name(rel_path: str) -> str | None:
    """Derive an import name under either allowlisted root.

    ``src`` is stripped because that tree itself is on ``PYTHONPATH``; the
    ``scripts`` prefix remains because the overlay parent is on the path and
    ``scripts`` is the package name. An ``__init__.py`` names its package, as
    an importer would. ``None`` means the target is not an importable module.
    """
    path = PurePosixPath(rel_path)
    if path.suffix != ".py":
        return None
    parts = list(path.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    elif parts and parts[0] not in _MUTATION_ROOTS:
        return None
    if not parts:
        return None
    parts[-1] = path.stem
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or None


def _absent(directive: KillDirective, detail: str, started: float) -> KillCheck:
    return KillCheck(
        directive=directive,
        verdict=SliceVerdict.PRODUCER_ABSENT,
        detail=detail,
        duration_s=time.monotonic() - started,
    )


def _errored(directive: KillDirective, detail: str, started: float) -> KillCheck:
    return KillCheck(
        directive=directive,
        verdict=SliceVerdict.ERROR,
        detail=detail,
        duration_s=time.monotonic() - started,
    )


def _run_kill_check(
    directive: KillDirective,
    test_paths: str | Sequence[str],
    root: Path,
    *,
    deadline: float | None = None,
) -> KillCheck:
    """Mutate one producer and run the slice's declared tests. (CT66, CT67, CT82, Q53(c))

    The order is load-bearing: :func:`apply_kill` (pure), then
    :func:`mutation_overlay` (the only copy on disk), then
    :func:`_assert_overlay_wins` (the mutated module is the one that will be
    imported), and only then the test. Running the test before the probe would
    produce a number that looks like evidence and is not -- the measured
    failure is that an installed package resolves to an absolute path, so the
    mutation is never imported and every kill-check reports a false
    ``VACUOUS`` (E125/D1).

    Q53(c): every `TESTS:` path declared for the slice runs under every
    functional contract's mutation. Any failing test makes this contract's
    kill-check ``PROVEN``; an unrelated test can therefore be falsely
    attributed, a cost and risk explicitly accepted by the operator.

    A surviving test set is ``VACUOUS``, not a pass. Any uncertainty -- an
    ambiguous symbol, a failed probe, a timeout -- is ``ERROR``, which never
    presents as a pass anywhere in this module.
    """
    started = time.monotonic()
    paths = (test_paths,) if isinstance(test_paths, str) else tuple(test_paths)
    if not paths or any(not path for path in paths):
        return _errored(directive, "the slice has no usable TESTS paths for this kill-check", started)
    paths_label = ", ".join(paths)
    source_root = _mutation_root(directive.path)
    if source_root is None:
        return _errored(directive, f"{directive.path} is outside the allowed src/scripts mutation roots", started)

    source_path = Path(root) / directive.path
    if not source_path.is_file():
        return _absent(directive, f"{directive.path} is not a file in the workspace", started)

    module = _module_name(directive.path)
    if module is None:
        return _errored(directive, f"{directive.path} is not an importable module path", started)

    try:
        source = source_path.read_text(encoding="utf-8")
        application = apply_kill(source, directive)
    except (OSError, SyntaxError, ValueError) as exc:
        return _errored(directive, f"could not mutate {directive.path}: {exc}", started)

    if application.targets > 1:
        return _errored(
            directive,
            f"{directive.symbol} resolves to {application.targets} definitions; "
            "qualify the symbol rather than letting the gate choose",
            started,
        )
    if application.source is None:
        target = directive.symbol if directive.callee is None else f"{directive.symbol} -> {directive.callee}"
        return _absent(directive, f"{target} was not found in {directive.path}", started)

    try:
        with mutation_overlay(Path(root), directive.path, application.source) as overlay_root:
            env = _overlay_env(Path(root), overlay_root, source_root=source_root)
            if source_root == "scripts":
                env["FA_MUTATION_OVERLAY_MODULE"] = module
            probe = _assert_overlay_wins(
                module,
                overlay_root,
                env,
                workspace=Path(root),
                source_root=source_root,
            )
            if probe.outcome is not CommandOutcome.PASS:
                return _errored(
                    directive,
                    f"overlay provenance probe did not pass: {probe.stderr_tail or probe.stdout_tail}",
                    started,
                )
            command = KILL_CHECK_COMMAND.format(path=shlex.join(paths))
            kill_env = _gate_subprocess_env(Path(root), base_env=env, kill_check=True)
            (result,) = run_commands((command,), workspace=Path(root), deadline=deadline, env=kill_env)
    except OverlayError as exc:
        return _errored(directive, f"overlay failed: {exc}", started)

    elapsed = time.monotonic() - started
    combined_tail = f"{result.stdout_tail}\n{result.stderr_tail}"
    if _OVERLAY_PROVENANCE_ERROR_MARKER in combined_tail:
        return _errored(
            directive,
            f"pytest did not prove the scripts overlay import: {combined_tail[-TAIL_LIMIT:]}",
            started,
        )
    if result.outcome is CommandOutcome.ERROR:
        return _errored(directive, f"{paths_label} could not be run: {result.stderr_tail}", started)
    if result.outcome is CommandOutcome.FAIL:
        return KillCheck(
            directive=directive,
            verdict=SliceVerdict.PROVEN,
            detail="",
            duration_s=elapsed,
        )
    return KillCheck(
        directive=directive,
        verdict=SliceVerdict.VACUOUS,
        detail=(
            f"the declared slice test set still passes ({paths_label}) with {directive.symbol} mutated; "
            "the tests do not detect removal of this producer"
        ),
        duration_s=elapsed,
    )


# ---------------------------------------------------------------------------
# Classification (SLICE5 / CT65-CT68)
# ---------------------------------------------------------------------------


def _compare_baseline(
    baseline: Mapping[str, bool] | None,
    now: Mapping[str, bool] | None,
) -> tuple[str, ...]:
    """Return existing nodeids that went GREEN at T0 -> RED now. (CT68)

    The key is a pytest nodeid, never a file. A newly-added or renamed test is
    absent from ``baseline`` and cannot be called a regression; a missing row
    on either side is unknown, not ``False``. ``None`` means that the run did
    not produce a usable report (as opposed to an empty mapping, which is a
    valid report with zero collected tests). The caller maps that unavailable
    phase to ``ERROR``; this pure comparison does not invent a failure row.

    Sorting makes the result stable for reports and tests, regardless of the
    mapping implementation used by the JUnitXML adapter.
    """
    if baseline is None or now is None:
        return ()
    return tuple(
        sorted(nodeid for nodeid, was_green in baseline.items() if was_green is True and now.get(nodeid) is False)
    )


def _producer_absent(kill_checks: Sequence[KillCheck]) -> bool:
    """Whether any declared producer is missing from the mutated workspace. (CT67)

    Kept as a named decision point because this outcome has a different repair
    from ``VACUOUS``: the feature is absent, rather than the test being weak.
    The CT67 producer kill removes this predicate and proves classification
    cannot silently fold a missing feature into another outcome.
    """
    return any(check.verdict is SliceVerdict.PRODUCER_ABSENT for check in kill_checks)


def _classify(
    command_results: Sequence[CommandResult],
    kill_checks: Sequence[KillCheck],
    *,
    baseline: Mapping[str, bool] | None,
    now: Mapping[str, bool] | None,
) -> SliceVerdict:
    """Reduce phase evidence to the single slice verdict. (CT65-CT68)

    Precedence is deliberate and fail-closed:

    1. Any indeterminate phase is ``ERROR``; it can never be laundered by a
       green command or a successful kill-check.
    2. No verify commands means the legacy/advisory ``SKIPPED`` state.
    3. A declared verify command's non-zero exit remains ``FAILING``. The
       commands are arbitrary planner-owned text (CT69), so without proven
       attribution the baseline comparison must never turn that exit into a
       pass. A current red nodeid absent at T0 is also ``FAILING`` (Q49); it
       cannot be ``REGRESSION`` because there is no before-state.
    4. With commands green and no new red nodeid, a T0-green -> now-red nodeid
       is ``REGRESSION``. Red-to-red is not a regression and is advisory.
    5. With the preceding phases clear, a missing producer is more specific
       than a test that survives the mutation; then ``PROVEN`` is the only
       remaining all-green outcome.

    This is a single status, while ``command_results`` and ``kill_checks``
    remain attached to the result object so the operator can inspect the
    evidence behind it.
    """
    if any(result.outcome is CommandOutcome.ERROR for result in command_results):
        return SliceVerdict.ERROR
    if any(check.verdict is SliceVerdict.ERROR for check in kill_checks):
        return SliceVerdict.ERROR

    if not command_results:
        return SliceVerdict.SKIPPED

    # A missing JUnit report is not an empty (all-green) baseline. With verify
    # commands present, the gate could not determine the comparison phase.
    if baseline is None or now is None:
        return SliceVerdict.ERROR

    if any(result.outcome is CommandOutcome.FAIL for result in command_results):
        return SliceVerdict.FAILING

    # A test nodeid introduced after T0 has no regression edge, but if it is
    # red now it is still a current test failure. A pre-existing red row is
    # advisory; only an absent-at-T0 red row is newly failing here.
    if any(not passed and nodeid not in baseline for nodeid, passed in now.items()):
        return SliceVerdict.FAILING

    if _compare_baseline(baseline, now):
        return SliceVerdict.REGRESSION

    if _producer_absent(kill_checks):
        return SliceVerdict.PRODUCER_ABSENT
    if any(check.verdict is SliceVerdict.VACUOUS for check in kill_checks):
        return SliceVerdict.VACUOUS

    return SliceVerdict.PROVEN


@dataclass(frozen=True, slots=True)
class SliceVerification:
    """Immutable evidence and verdict for one slice. (CT65)

    ``kill_checks`` retains each contract id beside its outcome; Q53(c) means
    each outcome was measured by running the complete slice ``TESTS:`` path
    set, not by a contract-specific test mapping. Nodeid fields keep baseline
    evidence inspectable by a caller preparing an operator-facing report.
    ``detail`` is reserved for a verification precondition that prevented
    phase execution; command and kill-check failures retain their own detail in
    their respective result records.
    """

    slice_id: str
    verdict: SliceVerdict
    command_results: tuple[CommandResult, ...]
    kill_checks: tuple[tuple[str, KillCheck], ...]
    regression_nodeids: tuple[str, ...] = ()
    failed_nodeids: tuple[str, ...] = ()
    detail: str = ""
    test_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanVerification:
    """Plan-wide evidence with each command still attached to its owner (CT71/76)."""

    plan_command_results: tuple[CommandResult, ...]
    slice_verifications: tuple[SliceVerification, ...]
    errors: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        """Whether enforce mode must route this verification back to the coder."""
        if self.errors:
            return True
        if any(result.outcome is not CommandOutcome.PASS for result in self.plan_command_results):
            return True
        return any(
            result.verdict
            not in {SliceVerdict.PROVEN, SliceVerdict.SKIPPED}
            for result in self.slice_verifications
        )


def verify_slice(
    record: SliceRecord,
    *,
    root: Path,
    baseline: Mapping[str, bool] | None,
    now: Mapping[str, bool] | None,
    deadline: float | None = None,
) -> SliceVerification:
    """Run and compose one slice's verify, baseline and contract kill evidence. (CT65-CT69)

    The baseline and current nodeid maps are injected by the workflow-level
    harness. This function never captures or refreshes either one; CT85 keeps
    T0 fixed across repair rounds. Planner-authored verify commands stay
    verbatim, while the Q49/Q53 test-result maps and kill-checks are separate
    harness-issued evidence.

    A legacy slice with no verify commands is ``SKIPPED`` and does not run
    kills. Otherwise, every declared ``FUNCTIONAL`` contract must have one
    parsed kill directive and the slice must declare at least one ``TESTS:``
    path. Missing metadata is ``ERROR`` before any command is run. Every
    functional contract then runs its mutation against every test path in the
    slice, as explicitly selected in Q53(c).
    """
    if not record.commands:
        return SliceVerification(
            slice_id=record.slice_id,
            verdict=SliceVerdict.SKIPPED,
            command_results=(),
            kill_checks=(),
            test_paths=record.test_paths,
        )

    functional_ids = tuple(contract_id for contract_id, kind, _ in record.contracts if kind == "FUNCTIONAL")
    directives = parse_kill_directives(record)
    missing_directives = tuple(contract_id for contract_id in functional_ids if contract_id not in directives)
    if not record.test_paths and functional_ids:
        return SliceVerification(
            slice_id=record.slice_id,
            verdict=SliceVerdict.ERROR,
            command_results=(),
            kill_checks=(),
            detail=f"functional contracts require at least one TESTS path: {', '.join(functional_ids)}",
            test_paths=record.test_paths,
        )
    if missing_directives:
        return SliceVerification(
            slice_id=record.slice_id,
            verdict=SliceVerdict.ERROR,
            command_results=(),
            kill_checks=(),
            detail=f"functional contracts lack parsed kill directives: {', '.join(missing_directives)}",
            test_paths=record.test_paths,
        )

    command_results = run_commands(
        record.commands,
        workspace=root,
        deadline=deadline,
        env=_gate_subprocess_env(root),
    )
    named_kills = tuple(
        (
            contract_id,
            _run_kill_check(directives[contract_id], record.test_paths, root, deadline=deadline),
        )
        for contract_id in functional_ids
    )
    kill_outcomes = tuple(check for _, check in named_kills)
    regression_nodeids = _compare_baseline(baseline, now)
    failed_nodeids = () if now is None else tuple(sorted(nodeid for nodeid, passed in now.items() if passed is False))
    verdict = _classify(command_results, kill_outcomes, baseline=baseline, now=now)

    return SliceVerification(
        slice_id=record.slice_id,
        verdict=verdict,
        command_results=command_results,
        kill_checks=named_kills,
        regression_nodeids=regression_nodeids,
        failed_nodeids=failed_nodeids,
        test_paths=record.test_paths,
    )


def verify_plan(
    plan_ids: PlanIds,
    *,
    root: Path,
    baseline_by_slice: Mapping[str, Mapping[str, bool] | None] | None = None,
    now_by_slice: Mapping[str, Mapping[str, bool] | None] | None = None,
    deadline: float | None = None,
) -> PlanVerification:
    """Run the plan-level commands once and preserve each slice's ownership (CT71/76).

    ``baseline_by_slice`` is the write-once T0 snapshot from CT86; ``now_by_slice``
    is captured after the successful coder stage. ``None`` for a slice means its
    JUnit report was unavailable and therefore flows to ``ERROR`` in
    :func:`verify_slice`. Empty mappings are valid snapshots with no collected
    nodeids. Plan-level commands use the distinct ``commands_for(None)`` owner
    exactly once; slice commands stay inside their :class:`SliceVerification`.
    """
    plan_commands = run_commands(
        plan_ids.commands_for(None),
        workspace=root,
        deadline=deadline,
        env=_gate_subprocess_env(root),
    )
    slice_results = tuple(
        verify_slice(
            record,
            root=root,
            baseline=None if baseline_by_slice is None else baseline_by_slice.get(record.slice_id),
            now=None if now_by_slice is None else now_by_slice.get(record.slice_id),
            deadline=deadline,
        )
        for record in plan_ids.slice_records
    )
    return PlanVerification(plan_command_results=plan_commands, slice_verifications=slice_results)
