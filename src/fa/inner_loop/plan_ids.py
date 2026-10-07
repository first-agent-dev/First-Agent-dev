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
from graphlib import CycleError, TopologicalSorter

__all__ = [
    "FAIL",
    "WARN",
    "PlanDiagnostic",
    "PlanIds",
    "PrecheckReport",
    "SliceRecord",
    "canonical_slice_id",
    "extract_plan_id",
    "extract_plan_ids",
    "parse_slice_id",
    "precheck",
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
#:
#: The marker is *captured, not filtered* (CT36). An earlier version admitted
#: only ``[ ]``, ``[x]`` and ``[>]``, which meant a capital ``[X]`` was not a
#: step at all and vanished from the lint in silence. Recognising the line
#: first and judging the marker second turns that into a diagnostic.
_STEP_RE = re.compile(r"^\s*- \[(?P<mark>[^\]]*)\]\s*STEP(?P<num>\d+[a-z]?)\s*:", re.MULTILINE)

#: Step states, after normalisation. ``[]``/``[ ]``/``[   ]`` are all "to do":
#: authors and formatters disagree about the inner space, and the disagreement
#: carries no meaning. Done accepts the two spellings GitHub renders plus the
#: check marks people paste from elsewhere.
_STEP_STATES = {"": "todo", "x": "done", "\u2713": "done", "\u2714": "done", ">": "in-progress"}


def _step_state(marker: str) -> str | None:
    """Normalise a checkbox marker to a state, or ``None`` if it is not one."""
    return _STEP_STATES.get(marker.strip().casefold())


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


#: A slice id exactly as the plan grammar defines it. Anchored at both ends:
#: this *validates*, where :func:`canonical_slice_id` *rewrites a prefix*.
_PLAN_SLICE_ID_RE = re.compile(r"^SLICE(\d+[a-z]?)$", re.IGNORECASE)


def parse_slice_id(raw: str) -> str | None:
    """Return the canonical slice id for *raw*, or ``None`` if it is not one.

    The strict counterpart to :func:`canonical_slice_id`, and the one the plan
    grammar must use. Three differences matter:

    * It **validates** instead of rewriting a prefix, so ``"slices"`` is not
      silently turned into ``"SLICEs"``.
    * It rejects the abbreviated ``S<n>`` form. Inside a plan that token is
      ambiguous — ``S1`` could be ``SLICE1`` or ``STEP1``, since a plan carries
      both namespaces — and quietly picking one is the failure class this
      module exists to remove. The abbreviation is reported, never resolved.
    * It returns ``None`` rather than the input, so a caller cannot mistake a
      non-id for an id by forgetting to check.

    :func:`canonical_slice_id` keeps the lenient behaviour and keeps its job:
    reconciling an eval report against the plan (``workflow_controller``).
    Tolerance is correct *there* because a report has only one namespace to
    match against — step results are slice verdicts — so ``S1`` is unambiguous
    at that boundary and dropping it would discard a usable verdict.
    """
    match = _PLAN_SLICE_ID_RE.match(raw.strip())
    if match is None:
        return None
    return f"SLICE{match.group(1)}"


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


def _contract_entries(section: str) -> list[tuple[int, re.Match[str]]]:
    """``(block index, entry match)`` for each contract declaration.

    The single source of truth for "which lines declare a contract".
    :func:`_section_contracts` reads the entries and the pre-check reads their
    line numbers from it, so the lint can never disagree with the parser about
    what a declaration is.
    """
    return [(i, m) for i, line in enumerate(_contracts_block(section)) if (m := _CONTRACT_ENTRY_RE.match(line))]


def _contract_declaration_sites(section: str) -> list[tuple[str, int]]:
    """``(contract id, 0-based section line)`` for each declaration entry.

    Block element ``i`` sits on section line ``start + i``: element 0 is the
    remainder of the ``CONTRACTS:`` line itself. The arithmetic lives here
    rather than at the call site so there is no sentinel to mishandle — a
    section with no ``CONTRACTS:`` line simply has no sites.
    """
    match = _CONTRACTS_LINE_RE.search(section)
    if match is None:
        return []
    start = section.count("\n", 0, match.start())
    return [(f"CT{entry.group('num')}", start + i) for i, entry in _contract_entries(section)]


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
    starts = _contract_entries(section)
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


# ---------------------------------------------------------------------------
# I01/SLICE3 — the plan pre-check
# ---------------------------------------------------------------------------
#
# Everything below reads a plan and reports; nothing here parses a *new* part
# of the grammar. The pre-check is deliberately the same module as the
# extractor so that a rule can never drift from the production that feeds it:
# `contract-declaration-lost` compares declaration-shaped lines against what
# `_section_contracts` actually returned, which is only honest while both read
# `_contract_entries`.
#
# Purity is a contract, not an accident (Q39). `precheck` touches no
# filesystem, no clock, no environment: it is a function of its text argument.
# That is what lets the harness run it on a plan that has not been written to
# disk yet, and what kept "does this TESTS: path exist?" out of I01 — at
# pre-check time a new slice's path is absent *by design*, so the check is
# false by construction here and belongs to the I02 verify gate, where
# `tests_note` makes "(NEW — author it)" interpretable.

#: A ``DEPS:`` line and its payload. Parsed here rather than promoted onto
#: ``SliceRecord``: the pre-check is its own only consumer, and SD-B forbids
#: shipping an accessor before an increment is named that wires it.
_DEPS_LINE_RE = re.compile(r"^DEPS:\s*(.*)$", re.MULTILINE)

#: A heading that *nearly* declares a slice (CT26). Case-insensitive, and
#: tolerant of a dropped letter or a stray space, because those are the
#: spellings observed in real drift. Matching here is not an accusation: a
#: line is only reported when :data:`_SLICE_RE` also declines it.
#:
#: Two alternatives, because the two abbreviation families need different
#: guards. A dropped letter (``SLIC1``, ``SLICE 1``) is unmistakable, so no
#: colon is required — one corpus case is a bare ``#### SLICE1``. The bare
#: ``S<n>`` form *is* mistakable: ``## S18 + I-63 CLOSED`` is a real heading in
#: this repository's worklogs, so that branch requires the colon that makes it
#: a declaration rather than section numbering.
_NEAR_MISS_HEADING_RE = re.compile(r"^#{2,4}\s+(?:SLI?CE?\s*\d|S\s*\d+[a-z]?\s*:)", re.IGNORECASE)

#: A line shaped like a contract declaration, wherever it sits (CT35). The
#: anchor is the start of the line after optional indentation, so prose that
#: merely mentions ``CT3 [CONSTRAINT]:`` mid-sentence is not a declaration.
_DECLARATION_SHAPE_RE = re.compile(r"^\s*CT(?P<num>\d+[a-z]?)\s*\[(?:FUNCTIONAL|CONSTRAINT|PRESERVATION)\]\s*:")

#: A checkbox line that abbreviates ``STEP<n>`` to ``S<n>`` (CT37).
_STEP_NEAR_MISS_RE = re.compile(r"^\s*- \[[^\]]*\]\s*S\s*\d+[a-z]?\s*:", re.IGNORECASE)

#: A column-0 slice field line. Used by the conservation rule to ask whether
#: the grammar the document contains ended up inside a slice (CT39).
_SLICE_FIELD_RE = re.compile(r"^(?P<field>STEPS|DEPS|INTENT|CONTRACTS|TESTS|SHIPPED):")

#: Slices per increment before the ceiling is reached (CT38). A ceiling, not a
#: sizing prior: see roadmap Q16.
_SLICE_CEILING = 7

#: Payload tokens that mean "this slice depends on nothing". Em dash, en dash
#: and hyphen are all in use across existing plans; written as escapes because
#: the two dashes are indistinguishable in most editors and a reader must be
#: able to tell which one the set actually contains.
_NO_DEPS = frozenset({"", "\u2014", "\u2013", "-", "none", "n/a", "na"})

#: The two severities. Public because a consumer cannot filter a report
#: without naming them, and a bare ``"FAIL"`` literal at every call site is how
#: a typo becomes a silently empty filter. ``FAIL`` blocks, ``WARN`` advises;
#: only ``FAIL`` clears :attr:`PrecheckReport.ok`.
FAIL = "FAIL"
WARN = "WARN"


def _contract_ids(record: SliceRecord) -> tuple[str, ...]:
    """Just the ids from a record's ``(id, class, text)`` triples."""
    return tuple(cid for cid, _cls, _text in record.contracts)


@dataclass(frozen=True, slots=True)
class PlanDiagnostic:
    """One rule violation, located well enough for an operator to go fix it.

    ``rule`` is a stable mnemonic (``slice-without-tests``), never a ``CT#``.
    Contract ids renumber when an increment is re-planned; a rule id appears in
    operator muscle memory, in commit messages and in suppressions, so it must
    outlive the plan that introduced it. The owning contract is recorded in the
    rule function's docstring instead.
    """

    rule: str
    severity: str
    path: str
    line: int
    message: str

    @property
    def location(self) -> str:
        """``file:line`` — the form CT25 requires and an editor can jump to."""
        return f"{self.path}:{self.line}"

    def render(self) -> str:
        return f"{self.location} [{self.severity} {self.rule}] {self.message}"


@dataclass(frozen=True, slots=True)
class PrecheckReport:
    """The whole verdict for one plan: every violation, in document order.

    One pass, all violations (CT25). A lint that stops at the first problem
    turns a five-minute fix into five round trips, which for an agent means
    five more chances to re-plan around the symptom instead of the cause.

    There is deliberately no ``warnings`` accessor to mirror :attr:`failures`.
    SD-B: no accessor ships before an increment is named that wires it, and
    nothing consumes the warning list yet — ``[d for d in r.diagnostics if
    d.severity == WARN]`` is one line when I02's gate renderer needs it.
    """

    path: str
    diagnostics: tuple[PlanDiagnostic, ...] = ()

    @property
    def failures(self) -> tuple[PlanDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity == FAIL)

    @property
    def ok(self) -> bool:
        """True when nothing *blocks*. Warnings are advice, not a gate (Q38)."""
        return not self.failures

    def render(self) -> str:
        return "\n".join(d.render() for d in self.diagnostics)


@dataclass(frozen=True, slots=True)
class _Slice:
    """A slice as the pre-check needs it: the record plus where it lives."""

    record: SliceRecord
    section: str
    start_line: int  # 1-based line of the slice heading

    def line_of(self, offset_in_section: int) -> int:
        return self.start_line + self.section.count("\n", 0, offset_in_section)


def _line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _rule_heading_near_miss(text: str, path: str) -> list[PlanDiagnostic]:
    """CT26 — a heading that looks like a slice but does not parse as one.

    FAIL, not WARN. The failure mode is not a cosmetic one: ``## SLICE 1:``
    declares no slice, so the slice and every contract, step and test path
    inside it are absent from the plan the harness gates against. The author
    sees a slice; the machine sees prose. Nothing downstream can detect that,
    because there is nothing downstream to detect.
    """
    out: list[PlanDiagnostic] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if _NEAR_MISS_HEADING_RE.match(line) and not _SLICE_RE.match(line):
            out.append(
                PlanDiagnostic(
                    rule="heading-near-miss",
                    severity=FAIL,
                    path=path,
                    line=index,
                    message=(
                        f"{line.strip()!r} does not declare a slice and its whole "
                        f"body is invisible to the harness; the form is '## SLICE<n>: title'"
                    ),
                )
            )
    return out


def _rule_step_marker_unknown(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT36 — the checkbox marker must be one the vocabulary knows.

    Reported on the line rather than normalised away. A marker nobody agreed
    on usually means the author meant a state the schema does not have, and
    guessing which one re-creates the silent mismatch this rule replaces.
    """
    out: list[PlanDiagnostic] = []
    for s in slices:
        for index, line in enumerate(s.section.splitlines()):
            step = _STEP_RE.match(line)
            if step is None or _step_state(step.group("mark")) is not None:
                continue
            out.append(
                PlanDiagnostic(
                    rule="step-marker-unknown",
                    severity=FAIL,
                    path=path,
                    line=s.start_line + index,
                    message=(
                        f"STEP{step.group('num')} is marked [{step.group('mark')}], which is "
                        f"not a step state; schema §6 defines [ ] to do, [>] in progress, "
                        f"[x] done"
                    ),
                )
            )
    return out


def _rule_step_near_miss(text: str, path: str) -> list[PlanDiagnostic]:
    """CT37 — a checkbox that abbreviates ``STEP<n>`` to ``S<n>``.

    Same reasoning as the heading near-miss: the line reads as a step, parses
    as a bullet, and its exit predicate is never checked by anything.

    Scanned over the whole document rather than per slice, because the two
    abbreviations travel together: a plan that writes ``## S1:`` declares no
    slice, so a per-slice scan would be blind to the ``- [ ] S2:`` beneath it
    — the one case where both mistakes are certain to appear at once.
    """
    out: list[PlanDiagnostic] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not _STEP_NEAR_MISS_RE.match(line) or _STEP_RE.match(line):
            continue
        out.append(
            PlanDiagnostic(
                rule="step-near-miss",
                severity=FAIL,
                path=path,
                line=index,
                message=(
                    f"{line.strip()!r} abbreviates the step id; write STEP<n> in full, "
                    f"because S<n> is ambiguous between a slice and a step"
                ),
            )
        )
    return out


def _rule_slice_count(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT38 — WARN at the ceiling. Never a FAIL.

    `N <= 7` is admission control, not a sizing prior (Q16): it says a
    decomposition needing more slices is mis-scoped, which is a judgement the
    planner makes and a gate cannot. So this signals and gets out of the way.
    Reported at 7 rather than 8 because 7 is still legal and is the moment the
    headroom is gone — which is the thing worth knowing before the next split.
    """
    if len(slices) < _SLICE_CEILING:
        return []
    return [
        PlanDiagnostic(
            rule="slice-count-at-ceiling",
            severity=WARN,
            path=path,
            line=slices[_SLICE_CEILING - 1].start_line,
            message=(
                f"{len(slices)} slices against a ceiling of {_SLICE_CEILING}; a decomposition "
                f"that needs more is a mis-scoped increment, not a long one"
            ),
        )
    ]


def _rule_orphaned_grammar(text: str, slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT39 — grammar the document contains must have landed inside a slice.

    A conservation rule rather than a list of forbidden constructs. Every
    other rule here names a mistake someone already made; this one asks a
    question the grammar answers for free — did the parser account for what is
    written? — and so it covers drift nobody has thought of yet.

    The motivating case: a `## Grounding` heading inside a slice ends that
    slice under CT16's depth rule, so the `TESTS:` line below it belongs to no
    slice. Today that is silent, or worse, surfaces as CT8 insisting the slice
    "has no TESTS: line" when the author plainly wrote one.

    Silent on a document with no slices at all. A pre-grammar plan is not an
    error — that is this module's founding rule — and flagging every line of
    one would be the noisiest possible way to say nothing.
    """
    if not slices:
        return []
    spans = [(s.section, s.start_line) for s in slices]
    inside = set()
    for section, start_line in spans:
        inside.update(range(start_line, start_line + section.count("\n") + 1))

    out: list[PlanDiagnostic] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if index in inside:
            continue
        if field := _SLICE_FIELD_RE.match(line):
            what = f"the field {field.group('field')}:"
        elif step := _STEP_RE.match(line):
            what = f"STEP{step.group('num')}"
        elif decl := _DECLARATION_SHAPE_RE.match(line):
            what = f"CT{decl.group('num')}"
        else:
            continue
        out.append(
            PlanDiagnostic(
                rule="orphaned-slice-field",
                severity=FAIL,
                path=path,
                line=index,
                message=(
                    f"{what} sits outside every slice, so nothing owns it; the slice above "
                    f"ended early — most often a '##' heading inside it, which must be '###'"
                ),
            )
        )
    return out


def _orphaned_tests_owners(slices: list[_Slice], orphans: list[PlanDiagnostic]) -> frozenset[str]:
    """Slice ids whose ``TESTS:`` line exists but fell outside the slice.

    Attribution is positional: an orphan belongs to the nearest slice above
    it, because that is the slice the author was writing when the section
    ended early. Used only to keep CT8 honest — see
    :func:`_rule_slice_without_tests`.
    """
    starts = [s.start_line for s in slices]
    owners: set[str] = set()
    for orphan in orphans:
        if "the field TESTS:" not in orphan.message:
            continue
        above = [i for i, start in enumerate(starts) if start < orphan.line]
        if above:
            owners.add(slices[above[-1]].record.slice_id)
    return frozenset(owners)


def _rule_slice_without_tests(
    slices: list[_Slice], path: str, *, suppress: frozenset[str] = frozenset()
) -> list[PlanDiagnostic]:
    """CT8 — a slice that declares contracts must name where they are proved.

    Conditioned on declaring at least one ``CT#``: a slice with no contracts
    asserts nothing, so there is nothing for a test to hold up.

    *suppress* carries slices whose ``TESTS:`` line was orphaned by CT39. For
    those, "has no TESTS: line" is simply false — the author wrote one and the
    section ended before it — and sending the operator to look for a missing
    line that is right there is worse than saying nothing. CT39 already
    reports the real defect at the real line.
    """
    return [
        PlanDiagnostic(
            rule="slice-without-tests",
            severity=FAIL,
            path=path,
            line=s.start_line,
            message=(
                f"{s.record.slice_id} declares "
                f"{', '.join(_contract_ids(s.record))} but has no TESTS: line, so no "
                f"contract in it is checkable"
            ),
        )
        for s in slices
        if s.record.contracts and not s.record.test_paths and s.record.slice_id not in suppress
    ]


def _step_blocks(section: str) -> list[tuple[str, int, str]]:
    """``(step id, offset, block text)`` per ``STEP#``.

    A step is a block, not a line. Real exit predicates wrap, and reading only
    the ``- [ ]`` line would reject the majority of correctly written steps —
    a lint with that false-positive rate gets switched off, which is strictly
    worse than not having it.

    A block ends at the next line that is non-blank and unindented. No
    lookahead to the following ``STEP#`` is needed and none is done: a step
    marker is itself unindented, so the same rule already stops there. The
    id is returned rather than re-derived by the caller, which removes an
    unreachable "no id" branch that the first draft of this carried.
    """
    lines = section.splitlines(keepends=True)
    out: list[tuple[str, int, str]] = []
    offset = 0
    for i, line in enumerate(lines):
        step = _STEP_RE.match(line)
        if step is not None:
            body = [line]
            for following in lines[i + 1 :]:
                if following.strip() and not following[:1].isspace():
                    break
                body.append(following)
            out.append((f"STEP{step.group('num')}", offset, "".join(body)))
        offset += len(line)
    return out


def _rule_step_without_exit(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT9 — every step of a prescriptive slice carries an ``(exit: …)``.

    ``STEPS: outcome`` slices are exempt by grammar: they state a destination
    and leave the route to the coder, so demanding a per-step predicate would
    contradict the mode the author chose.
    """
    out: list[PlanDiagnostic] = []
    for s in slices:
        if s.record.steps_mode != "prescriptive":
            continue
        for name, offset, block in _step_blocks(s.section):
            if "(exit:" in block:
                continue
            out.append(
                PlanDiagnostic(
                    rule="step-without-exit",
                    severity=FAIL,
                    path=path,
                    line=s.line_of(offset),
                    message=(
                        f"{s.record.slice_id}/{name} is prescriptive but states no "
                        f"'(exit: ...)' predicate, so done-ness is a judgement call"
                    ),
                )
            )
    return out


def _declared_deps(section: str) -> tuple[int, list[str]] | None:
    """``(offset, canonical dep ids)`` from the slice's ``DEPS:`` line."""
    match = _DEPS_LINE_RE.search(section)
    if match is None:
        return None
    payload = match.group(1).strip()
    tokens = [t.strip(" .,;") for t in re.split(r"[,\s]+", payload) if t.strip(" .,;")]
    deps = [parse_slice_id(token) or token for token in tokens if token.casefold() not in _NO_DEPS]
    return match.start(), deps


def _dependency_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Every dependency cycle, as a path whose first and last node are equal.

    :class:`graphlib.TopologicalSorter` is the stdlib answer to exactly this
    question and reports the offending path, so there is no hand-written graph
    walk here to get subtly wrong. It surfaces one cycle per attempt; the edge
    that closed it is dropped and the sort retried, so independent cycles are
    all reported in the single pass CT25 asks for.

    Termination is bounded by the edge count: every iteration either finds the
    graph acyclic and returns, or removes one edge.
    """
    remaining = {node: list(deps) for node, deps in graph.items()}
    found: list[list[str]] = []
    for _ in range(sum(len(deps) for deps in remaining.values()) + 1):
        try:
            TopologicalSorter(remaining).prepare()
        except CycleError as exc:
            cycle = list(exc.args[1])
            found.append(cycle)
            # `cycle[i]` precedes `cycle[i+1]`, so the first pair is a real
            # edge: `cycle[1]` depends on `cycle[0]`. Dropping it breaks this
            # cycle and exposes any further one behind it. Filtered rather
            # than `.remove()`d so the walk cannot raise on a surprise.
            remaining[cycle[1]] = [d for d in remaining[cycle[1]] if d != cycle[0]]
        else:
            break
    return found


def _rule_deps(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT10 (Q38: slice ids only) — the dependency graph must be runnable.

    Two ways it is not. A ``DEPS:`` entry naming a slice that does not exist is
    a broken edge: the harness cannot order a run against a node it cannot
    find. A cycle has no topological order at all. Both are FAIL, because in
    either case there is no correct sequence to execute and guessing one
    silently is how a slice gets built before the thing it depends on.

    Contract references are *not* this rule's business — see
    :func:`_rule_contract_reference_undeclared`, which warns instead.
    """
    out: list[PlanDiagnostic] = []
    known = {s.record.slice_id for s in slices}
    graph: dict[str, list[str]] = {}
    lines: dict[str, int] = {}

    for s in slices:
        parsed = _declared_deps(s.section)
        if parsed is None:
            graph[s.record.slice_id] = []
            continue
        offset, deps = parsed
        lines[s.record.slice_id] = s.line_of(offset)
        graph[s.record.slice_id] = [d for d in deps if d in known]
        for dep in deps:
            if dep not in known:
                out.append(
                    PlanDiagnostic(
                        rule="deps-undefined-slice",
                        severity=FAIL,
                        path=path,
                        line=s.line_of(offset),
                        message=(
                            f"{s.record.slice_id} declares DEPS: {dep}, which no "
                            f"heading in this plan defines; run order is undefined"
                        ),
                    )
                )

    for cycle in _dependency_cycles(graph):
        out.append(
            PlanDiagnostic(
                rule="deps-cycle",
                severity=FAIL,
                path=path,
                # The printed path starts at `cycle[0]`, so its first edge is
                # declared by `cycle[1]`'s DEPS: line. Point there: it is a
                # line the operator can actually edit to break the cycle,
                # rather than a node that merely participates in it.
                line=lines[cycle[1]],
                message="DEPS: cycle " + " -> ".join(cycle) + "; no slice in it can be built first",
            )
        )
    return out


def _rule_contract_reference_undeclared(
    text: str, slices: list[_Slice], path: str, *, suppress: frozenset[str] = frozenset()
) -> list[PlanDiagnostic]:
    """CT27 (Q38: contract ids only) — WARN, never FAIL.

    A plan legitimately cites a contract that lives somewhere else: a
    neighbouring increment's ``CT#``, a superseded plan's, a ledger entry's.
    Failing on that would force authors to invent an escape hatch, and an
    escape hatch is used for the real misses too. A warning stays readable and
    costs nothing to leave standing when it is correct.

    Reported once per id, at its first mention, so a contract quoted in ten
    steps produces one line of output rather than ten.

    *suppress* carries the ids ``contract-declaration-lost`` already claimed.
    An id whose declaration was eaten by a margin wrap is trivially "declared
    nowhere", so without this every such contract is reported twice under two
    rules — and the warning is the misleading one, because it points at a
    mention rather than at the broken block that caused it. One defect, one
    diagnostic, at the line the operator has to edit.
    """
    declared = {cid for s in slices for cid in _contract_ids(s.record)}
    seen: set[str] = set()
    out: list[PlanDiagnostic] = []
    for index, line in enumerate(text.splitlines(), start=1):
        for num in _CONTRACT_RE.findall(line):
            cid = f"CT{num}"
            if cid in declared or cid in seen or cid in suppress:
                continue
            seen.add(cid)
            out.append(
                PlanDiagnostic(
                    rule="contract-reference-undeclared",
                    severity=WARN,
                    path=path,
                    line=index,
                    message=(f"{cid} is referenced here but declared in no CONTRACTS: block in this plan"),
                )
            )
    return out


def _rule_contract_declared_twice(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT34 — one contract id, one owner, naming both sites.

    Two slices claiming ``CT1`` makes "CT1 is green" ambiguous: the harness
    ticks one of them and the other's assertion is never checked, while the
    plan reads as though it were. Naming both locations is the whole value —
    an operator cannot resolve a duplicate they have to go hunt for.
    """
    sites: dict[str, list[tuple[str, int]]] = {}
    for s in slices:
        for cid, section_line in _contract_declaration_sites(s.section):
            sites.setdefault(cid, []).append((s.record.slice_id, s.start_line + section_line))
    out: list[PlanDiagnostic] = []
    for cid, places in sites.items():
        if len(places) < 2:
            continue
        where = ", ".join(f"{sid} at {path}:{line}" for sid, line in places)
        out.append(
            PlanDiagnostic(
                rule="contract-declared-twice",
                severity=FAIL,
                path=path,
                line=places[1][1],
                message=f"{cid} is declared {len(places)} times — {where}",
            )
        )
    return out


def _rule_contract_declaration_lost(slices: list[_Slice], path: str) -> list[PlanDiagnostic]:
    """CT35 (Q36) — a declaration the author wrote that the parser did not see.

    The motivating defect: a contract sentence wrapped back to column 0 ends
    the ``CONTRACTS:`` block, so that entry is truncated *and* every contract
    after it disappears. Nothing errors. The plan renders correctly in a
    Markdown viewer and is simply missing contracts in the machine.

    This rule is the only one that compares the document against the parser's
    own output rather than against the grammar, which is why it catches the
    class "the extractor silently dropped something" in general.
    """
    out: list[PlanDiagnostic] = []
    for s in slices:
        declared = set(_contract_ids(s.record))
        for offset_line, line in enumerate(s.section.splitlines()):
            match = _DECLARATION_SHAPE_RE.match(line)
            if match is None:
                continue
            cid = f"CT{match.group('num')}"
            if cid in declared:
                continue
            out.append(
                PlanDiagnostic(
                    rule="contract-declaration-lost",
                    severity=FAIL,
                    path=path,
                    line=s.start_line + offset_line,
                    message=(
                        f"{cid} is written as a declaration but {s.record.slice_id} "
                        f"parsed only {', '.join(_contract_ids(s.record)) or 'none'} — the "
                        f"CONTRACTS: block ended early, usually a continuation line "
                        f"wrapped back to column 0"
                    ),
                )
            )
    return out


def _lost_ids(lost: list[PlanDiagnostic]) -> list[str]:
    """The contract ids named by ``contract-declaration-lost`` diagnostics."""
    return [match.group(0) for d in lost if (match := _CONTRACT_RE.match(d.message))]


def precheck(text: str, *, path: str = "<plan>") -> PrecheckReport:
    """Lint a plan artifact and return every violation in one pass.

    Pure, total and stdlib-only: a function of *text* alone. It never raises,
    never reads the filesystem and never consults the clock, so it is safe to
    run on a draft the author has not saved and gives the same verdict in CI,
    in the harness and on a laptop.

    *path* is used only to render ``file:line`` locations (CT25); it is never
    opened. Call it with the plan's real path when you have one so the output
    is clickable, and leave it alone when linting a buffer.

    Severities: ``FAIL`` means there is no correct way to execute the plan as
    written — a missing test anchor, an unordered graph, a contract the parser
    cannot see. ``WARN`` means the plan is runnable but something is probably
    a mistake. Only failures clear :attr:`PrecheckReport.ok`.
    """
    body = text or ""
    ids = extract_plan_ids(body)
    spans = _slice_spans(body)
    by_id = {record.slice_id: record for record in ids.slice_records}
    slices = [
        _Slice(record=by_id[sid], section=body[start:end], start_line=_line_at(body, start))
        for sid, start, end in spans
        if sid in by_id
    ]

    lost = _rule_contract_declaration_lost(slices, path)
    orphans = _rule_orphaned_grammar(body, slices, path)
    diagnostics = [
        *_rule_heading_near_miss(body, path),
        *_rule_step_marker_unknown(slices, path),
        *_rule_step_near_miss(body, path),
        *_rule_slice_count(slices, path),
        *orphans,
        *_rule_slice_without_tests(slices, path, suppress=_orphaned_tests_owners(slices, orphans)),
        *_rule_step_without_exit(slices, path),
        *_rule_deps(slices, path),
        *_rule_contract_reference_undeclared(body, slices, path, suppress=frozenset(_lost_ids(lost))),
        *_rule_contract_declared_twice(slices, path),
        *lost,
    ]
    diagnostics.sort(key=lambda d: (d.line, d.rule))
    return PrecheckReport(path=path, diagnostics=tuple(diagnostics))
