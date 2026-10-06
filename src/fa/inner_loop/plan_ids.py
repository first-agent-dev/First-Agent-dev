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
    "SliceRecord",
    "canonical_slice_id",
    "extract_plan_id",
    "extract_plan_ids",
]


#: Slice headings: ``## SLICE5: title`` / ``## SLICE5a: title``. The number may
#: carry a lowercase suffix (``SLICE5a``) because plans routinely insert a
#: slice without renumbering its successors. ``SLICE#``-only: the legacy ``S#``
#: pattern is gone, so a pre-rename plan yields no slices (it is archived).
_SLICE_RE = re.compile(r"^(#{2,4})\s+SLICE(\d+[a-z]?)\s*:", re.MULTILINE)

#: Any ATX heading. Used only as a section *terminator* (CT16). The depth is
#: read from the match rather than hardcoded, because ``_SLICE_RE`` admits
#: ``##`` through ``####`` and a fixed ``^#{1,2}`` is wrong for a ``###`` slice.
_HEADING_RE = re.compile(r"^(#{1,6})\s", re.MULTILINE)

#: The ``CONTRACTS:`` field line. Declaration is scoped to its block (CT17).
_CONTRACTS_LINE_RE = re.compile(r"^CONTRACTS:", re.MULTILINE)

#: The trailing note on a ``TESTS:`` line: the first whitespace-delimited token
#: opening with ``(`` or ``#``, through end of line (CT33).
_TESTS_NOTE_RE = re.compile(r"(?:^|\s)([(#].*)$")

#: One contract entry: an indented ``CT<n> [CLASS]: text`` line. The class is
#: optional and defaults to ``FUNCTIONAL``; continuation lines are joined onto
#: the entry rather than parsed (CT18).
_CONTRACT_ENTRY_RE = re.compile(
    r"^(?P<indent>\s+)CT(?P<num>\d+[a-z]?)\s*"
    r"(?:\[(?P<cls>FUNCTIONAL|CONSTRAINT|PRESERVATION)\])?\s*:\s*(?P<text>.*)$"
)

#: Tracked step checkboxes inside a slice: ``- [ ] STEP3: ...``. Consumed by the
#: SLICE3 pre-check; kept here so the grammar lives in one module.
_STEP_RE = re.compile(r"^\s*- \[[ x>]\]\s*STEP(\d+[a-z]?)\s*:", re.MULTILINE)

#: Per-slice field lines. ``STEPS:`` is the mode line only; ``TESTS:``/``INTENT:``
#: carry the slice's test paths and intent.
_STEPS_MODE_RE = re.compile(r"^STEPS:\s*(prescriptive|outcome)\b", re.MULTILINE)
_TESTS_LINE_RE = re.compile(r"^TESTS:\s*(.+)$", re.MULTILINE)
_INTENT_LINE_RE = re.compile(r"^INTENT:\s*(.+)$", re.MULTILINE)

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
class SliceRecord:
    """Everything the verify gate (I02) and coder brief (I03) need for one slice.

    Frozen and tuple-valued for the same reason as :class:`PlanIds`: an
    extraction's result must be immutable and stable across calls.
    """

    slice_id: str
    intent: str = ""
    #: (contract id, class, text) triples in document order.
    contracts: tuple[tuple[str, str, str], ...] = ()
    test_paths: tuple[str, ...] = ()
    steps_mode: str = "prescriptive"
    commands: tuple[str, ...] = ()
    section: str = ""
    #: CT33. The trailing ``(NEW — …)`` annotation on the ``TESTS:`` line,
    #: verbatim. I01 preserves it and assigns it no meaning; I02's fail-before
    #: filter keys on it and has no other source for it.
    tests_note: str = ""


@dataclass(frozen=True)
class PlanIds:
    """IDs and commands recovered from one plan artifact.

    Every field defaults to empty: an unparseable or absent plan is a valid,
    fully-constructed result, not an error state. Tuples (not lists) so a
    consumer cannot mutate one extraction's result and affect another.

    The flat fields are the historical surface and are retained unchanged for
    the two ``.slices`` callers and the flat-command test; ``slice_records`` is
    added *beside* them, never substituted.
    """

    slices: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    contracts: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    commands: tuple[str, ...] = field(default=())
    slice_records: tuple[SliceRecord, ...] = field(default=())
    #: CT4b/Q35. Verify commands owned by no slice — the prologue, and any
    #: increment-level section after the last slice. Ownership is total, so a
    #: command can never be reachable from ``commands`` and from no record.
    plan_commands: tuple[str, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        """True when nothing was recovered — the caller should stay advisory."""
        return not (self.slices or self.gaps or self.contracts or self.tests or self.commands)

    def _record(self, slice_id: str) -> SliceRecord | None:
        wanted = canonical_slice_id(slice_id)
        return next((r for r in self.slice_records if r.slice_id == wanted), None)

    def commands_for(self, slice_id: str | None) -> tuple[str, ...]:
        """Verify commands owned by *slice_id*, or by the plan when ``None``.

        CT3/CT4b. ``None`` is not "no filter" but a real owner: the commands
        that belong to no slice. Every command in :attr:`commands` is reachable
        through exactly one of these two routes, so a per-slice consumer cannot
        silently skip one. An unknown id yields ``()`` rather than raising,
        because the caller is advisory.
        """
        if slice_id is None:
            return self.plan_commands
        record = self._record(slice_id)
        return record.commands if record is not None else ()

    def section(self, slice_id: str) -> str:
        """The slice's own block, heading included (CT4). Unknown id -> ``""``."""
        record = self._record(slice_id)
        return record.section if record is not None else ""

    def tests_for(self, slice_id: str) -> tuple[str, ...]:
        """The slice's ``TESTS:`` paths (CT20). Unknown id -> ``()``."""
        record = self._record(slice_id)
        return record.test_paths if record is not None else ()

    def contract_class(self, contract_id: str) -> str | None:
        """The declared class of *contract_id*, or ``None`` if never declared.

        CT19. ``None`` distinguishes "not declared anywhere" from a declared
        contract, which is what the pre-check needs to report an orphan
        reference. A duplicated id resolves to its first declaration in
        document order so the answer is deterministic; reporting the duplicate
        is CT34's job, not this accessor's.
        """
        wanted = contract_id.strip()
        for record in self.slice_records:
            for cid, cls, _ in record.contracts:
                if cid == wanted:
                    return cls
        return None


def canonical_slice_id(raw: str) -> str:
    """Map a slice token from either grammar onto the canonical ``SLICE<n>`` space.

    ``S5a`` -> ``SLICE5a`` and ``SLICE5a`` -> ``SLICE5a`` (idempotent). The plan
    side (``.slices``) and the eval side (report step IDs) are one logical ID
    surface; the eval parser still accepts legacy ``S<n>`` tokens during the
    migration, so the cross-check in ``validate_slice_ids`` compares canonical
    forms rather than raw tokens. Non-slice tokens are returned unchanged.
    """
    text = raw.strip()
    low = text.lower()
    if low.startswith("slice"):
        return "SLICE" + text[5:]
    if low.startswith("s") and len(text) > 1 and text[1].isdigit():
        return "SLICE" + text[1:]
    return text


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


def _slice_spans(text: str) -> list[tuple[str, int, int]]:
    """``(slice_id, start, end)`` for every slice section, in document order.

    CT16. A section ends at the first later heading whose depth is less than
    or equal to the depth of the slice's *own* heading, or at end of text.
    Two consequences are deliberate:

    * a deeper heading stays **inside** the section, so a slice owns its own
      ``### Grounding``-style subsections. A terminator of "any heading" would
      truncate every slice at its first subsection.
    * a later slice heading ends the section **whatever its depth**. The depth
      rule alone would let a ``### SLICE2`` nest inside a ``## SLICE1``, and
      one command would then belong to two records — breaking the ownership
      partition CT4b/CT4c rest on. Sections never overlap.

    Before CT16 a section ran to the next slice heading only, so the final
    slice absorbed every increment-level section that followed it, along with
    every contract id mentioned in them.
    """
    matches = list(_SLICE_RE.finditer(text))
    spans: list[tuple[str, int, int]] = []
    for i, match in enumerate(matches):
        depth = len(match.group(1))
        end = len(text)
        for heading in _HEADING_RE.finditer(text, match.end()):
            if len(heading.group(1)) <= depth:
                end = heading.start()
                break
        if i + 1 < len(matches):
            end = min(end, matches[i + 1].start())
        spans.append((f"SLICE{match.group(2)}", match.start(), end))
    return spans


def _unowned_commands(text: str, spans: list[tuple[str, int, int]]) -> tuple[str, ...]:
    """Verify commands belonging to no slice (CT4b, scoped by Q35).

    The complement of the slice spans: the prologue, and any increment-level
    section after the last slice. Each gap is scanned on its own rather than
    concatenated first, so two distant fragments can never be spliced into one
    spurious fence.
    """
    out: list[str] = []
    cursor = 0
    for _, start, end in spans:
        out.extend(_extract_commands(text[cursor:start]))
        cursor = max(cursor, end)
    out.extend(_extract_commands(text[cursor:]))
    return _ordered_unique(out)


def _tests_note(line: str) -> str:
    """The trailing annotation on a ``TESTS:`` line, verbatim (CT33).

    Everything from the first ``(``- or ``#``-prefixed token onward — exactly
    the remainder :func:`_test_paths` discards. Preserved, not interpreted:
    I02 decides what ``NEW`` licenses.
    """
    match = _TESTS_NOTE_RE.search(line)
    return match.group(1).strip() if match else ""


def _test_paths(line: str) -> tuple[str, ...]:
    """Path tokens from a ``TESTS:`` line, stopping at a ``(`` or ``#`` note."""
    cut: list[str] = []
    for t in line.split():
        if t.startswith(("(", "#")):
            break
        cut.append(t.strip(",;"))
    return tuple(dict.fromkeys(cut))


def _contracts_block(section: str) -> list[str]:
    """The lines of this slice's ``CONTRACTS:`` block (CT17).

    From the ``CONTRACTS:`` line to the first later non-blank line that begins
    at column 0, or to the end of the section. Indentation is the only
    terminator — deliberately not an allowlist of field names, because the
    grammar keeps growing column-0 fields and the one an allowlist missed
    (``SHIPPED:``) would silently pull step prose into the block.
    """
    match = _CONTRACTS_LINE_RE.search(section)
    if match is None:
        return []
    block: list[str] = []
    for line in section[match.end() :].splitlines():
        if line.strip() and not line[:1].isspace():
            break
        block.append(line)
    return block


def _section_contracts(section: str) -> tuple[tuple[str, str, str], ...]:
    """``(id, class, text)`` for every contract **declared** in this slice.

    CT17 scopes declaration to the ``CONTRACTS:`` block, so a contract id
    typed in step prose is a reference and not a declaration of this slice.
    CT18 makes one entry exactly one contract: id and class are read from the
    entry's first line only, and the text is the whole entry with continuation
    lines joined by single spaces. Both halves matter — a bracketed class
    quoted inside a continuation is an illustration rather than a second
    declaration, and truncating at the first line would discard exactly the
    ``Catches:`` rationale the grammar mandates. An unclassed entry defaults to
    ``FUNCTIONAL``; a repeated id keeps its first declaration (CT19).
    """
    block = _contracts_block(section)
    starts = [(i, m) for i, line in enumerate(block) if (m := _CONTRACT_ENTRY_RE.match(line))]
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for position, (index, entry) in enumerate(starts):
        indent = len(entry.group("indent"))
        parts = [entry.group("text").strip()]
        stop = starts[position + 1][0] if position + 1 < len(starts) else len(block)
        for line in block[index + 1 : stop]:
            if not line.strip():
                continue
            if len(line) - len(line.lstrip()) <= indent:
                break
            parts.append(line.strip())
        cid = f"CT{entry.group('num')}"
        if cid in seen:
            continue
        seen.add(cid)
        out.append((cid, entry.group("cls") or "FUNCTIONAL", " ".join(p for p in parts if p)))
    return tuple(out)


def _build_record(slice_id: str, section: str) -> SliceRecord:
    intent = _INTENT_LINE_RE.search(section)
    tests = _TESTS_LINE_RE.search(section)
    mode = _STEPS_MODE_RE.search(section)
    return SliceRecord(
        slice_id=slice_id,
        intent=intent.group(1).strip() if intent else "",
        contracts=_section_contracts(section),
        test_paths=_test_paths(tests.group(1)) if tests else (),
        steps_mode=mode.group(1) if mode else "prescriptive",
        commands=_extract_commands(section),
        section=section,
        tests_note=_tests_note(tests.group(1)) if tests else "",
    )


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

    spans = _slice_spans(text)
    records = tuple(_build_record(sid, text[start:end]) for sid, start, end in spans)
    return PlanIds(
        slices=_ordered_unique([r.slice_id for r in records]),
        gaps=_ordered_unique([f"GAP{n}" for n in _GAP_RE.findall(text)]),
        contracts=_ordered_unique([f"CT{n}" for n in _CONTRACT_RE.findall(text)]),
        tests=_ordered_unique([f"T{n}" for n in _TEST_RE.findall(text)]),
        commands=_extract_commands(text),
        slice_records=records,
        plan_commands=_unowned_commands(text, spans),
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
