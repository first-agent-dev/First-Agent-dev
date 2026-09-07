"""Plan-artifact ID and verification-command extraction (PLAN S3 / CT6).

Pure, stdlib-only, no LLM. Given the text of an implementation plan, recover
the machine-addressable parts: slice/gap/contract/test IDs, and the shell
commands the harness is allowed to run to verify a slice.

**Why a script and not a model call.** The operator's decision (F6 rev 5 Q-op5)
is explicit: script extraction only. Every value here is either present in the
plan text verbatim or absent — there is nothing to infer, so an LLM call would
add cost, latency, and a failure mode without adding information.

**Why absence is never an error.** This module feeds an *advisory* pre-fill.
A plan that does not follow the ID grammar (every plan written before the
grammar existed) yields empty tuples and the run proceeds. Raising, or
returning a sentinel the caller must check, would recreate the
``pr_prepare`` failure shape the parent plan exists to remove: a harness that
rejects work because a field it wanted was not in the format it expected.

**ID grammar authority.** ``G#/GAP#/CT#/P#/M#/A#/S#/T#/Q#/RK#/RN#`` is common
to both planning skills — ``knowledge/skills/feature-planning/SKILL.md``
(§2 "IDs and liveness") and ``knowledge/skills/plan-authoring/SKILL.md``
(§1 "Traceability & ID conventions"). Because the vocabularies are identical,
one extractor serves plans authored under either skill; the harness does not
need to know which produced a given file.

**Command grammar.** ``T#`` is a *taxonomy label* (C0/C0p/C1/C2/C3/C4), not a
runnable string, so test IDs cannot be executed. Commands are therefore read
from fenced ``verify`` blocks only::

    ```verify
    uv run pytest tests/test_plan_ids.py -q
    ```

Nothing is ever inferred from prose: a plan with no ``verify`` block yields no
commands, and the caller records the verification as skipped rather than
guessing what to run. This is the boundary that keeps a model-authored
sentence from becoming a shell command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "PlanIds",
    "extract_plan_id",
    "extract_plan_ids",
]


#: Slice headings: ``### Step S5a: title`` or ``### S5: title``. The step
#: number may carry a lowercase suffix (``S5a``) because plans routinely
#: insert a step without renumbering their successors.
_SLICE_RE = re.compile(r"^#{2,4}\s+(?:Step\s+)?(S\d+[a-z]?)\s*:", re.MULTILINE)

#: Bare ID tokens. ``\b`` on both sides so ``GAP12`` does not also yield
#: ``GAP1``, and ``CT10`` is not read as ``CT1``. Case-sensitive: the grammar
#: is uppercase, and lowercasing would sweep up prose words like "ct".
_GAP_RE = re.compile(r"\bGAP(\d+[a-z]?)\b")
_CONTRACT_RE = re.compile(r"\bCT(\d+[a-z]?)\b")
_TEST_RE = re.compile(r"\bT(\d+[a-z]?)\b")

#: The plan's own declared identity, e.g. ``Plan-ID: PLAN-foo``. Real plans in
#: this repo use three shapes, all of which must parse:
#:
#:   ``Plan-ID: `PLAN-foo```   (backticked -- the most common)
#:   ``Plan-ID:** PLAN-foo``   (the label was bolded, so ``**`` trails the colon)
#:   ``Plan-ID: PLAN-foo``     (bare)
#:
#: Anchored to a line start so a mention in prose ("see Plan-ID: X above")
#: further down the document cannot masquerade as the declaration; callers
#: take the FIRST match, which is the header.
#: ``.*?`` before the label because this repo's own plan puts the declaration
#: at the END of the H1 title line ("# PLAN: ...    Plan-ID: PLAN-foo"), not on
#: a line of its own. Still line-anchored, so the first match is the header.
_PLAN_ID_RE = re.compile(
    r"^.*?Plan-ID:\s*\**\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?",
    re.MULTILINE,
)

#: Fenced ``verify`` block. ``[ \t]*`` tolerates indentation inside list
#: items; the closing fence is any ``` at line start (after optional
#: whitespace). Non-greedy so consecutive blocks stay separate.
_VERIFY_BLOCK_RE = re.compile(
    r"^[ \t]*```[ \t]*verify[ \t]*\n(.*?)^[ \t]*```",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class PlanIds:
    """IDs and commands recovered from one plan artifact.

    Every field defaults to empty: an unparseable or absent plan is a valid,
    fully-constructed result, not an error state. Tuples (not lists) so a
    consumer cannot mutate one extraction's result and affect another.
    """

    slices: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    contracts: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    commands: tuple[str, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        """True when nothing was recovered — the caller should stay advisory."""
        return not (self.slices or self.gaps or self.contracts or self.tests or self.commands)


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    """De-duplicate preserving first-appearance order.

    Order is document order, which makes the output stable and diffable, and
    keeps ``slices[0]`` meaningful (the first slice defined in the plan).
    ``dict.fromkeys`` rather than ``set`` precisely because a set would make
    the result non-deterministic across runs.
    """
    return tuple(dict.fromkeys(values))


def _extract_commands(text: str) -> tuple[str, ...]:
    """Return runnable command lines from fenced ``verify`` blocks.

    Blank lines and ``#`` comments are dropped so a block can be annotated
    without the annotation being executed. Everything else is preserved
    verbatim — this function does not validate, rewrite, or shell-quote the
    command, because the harness runs it exactly as the plan author wrote it.
    """
    commands: list[str] = []
    for block in _VERIFY_BLOCK_RE.findall(text):
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            commands.append(line)
    return _ordered_unique(commands)


def extract_plan_ids(text: str) -> PlanIds:
    """Extract slice/gap/contract/test IDs and verify commands from *text*.

    Pure: no filesystem access, no network, no LLM call, no logging side
    effects. Total: every input maps to a ``PlanIds``; malformed, empty, and
    non-plan inputs all return empty tuples rather than raising. The caller is
    an advisory pre-fill path, so a thrown exception here would convert a
    cosmetic miss into a failed run.

    Args:
        text: full plan-artifact text. A non-``str`` (or ``None``) is treated
            as no input, since the read that produced it may itself have
            degraded.

    Returns:
        :class:`PlanIds` with document-ordered, de-duplicated values.
    """
    if not isinstance(text, str) or not text:
        return PlanIds()

    return PlanIds(
        slices=_ordered_unique(_SLICE_RE.findall(text)),
        gaps=_ordered_unique([f"GAP{n}" for n in _GAP_RE.findall(text)]),
        contracts=_ordered_unique([f"CT{n}" for n in _CONTRACT_RE.findall(text)]),
        tests=_ordered_unique([f"T{n}" for n in _TEST_RE.findall(text)]),
        commands=_extract_commands(text),
    )


def extract_plan_id(text: str) -> str | None:
    """Return the plan's declared ``Plan-ID``, or ``None`` if it has none.

    S12a. Separate from :func:`extract_plan_ids` because the two answer
    different questions and have different failure modes: the plural function
    recovers *contents* (slices, gaps, commands) and an empty result is normal,
    while this one recovers the plan's *identity* and its absence means the
    caller must fall back to another identifier rather than invent one.

    Never raises. An absent, malformed, or non-textual declaration yields
    ``None``, because a run must not fail merely because its plan omitted a
    header field.
    """
    match = _PLAN_ID_RE.search(text or "")
    if match is None:
        return None
    return match.group(1).strip() or None
