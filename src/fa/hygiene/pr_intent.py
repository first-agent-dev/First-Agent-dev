"""PR-intent classifier + commit-message validator (PR B — M-6).

Single source of truth for the PR-intent rulebook is
[`knowledge/skills/pr-creation/SKILL.md`](../../../knowledge/skills/pr-creation/SKILL.md)
§Reference + §Output format + §What the hook validates. This module
materialises that contract as four pure-Python deterministic
functions:

- :func:`classify_intent` — closed-enum Level-1 classifier over a
  list of staged paths (the output of ``git diff --cached
  --name-status``). Cross-category resolution
  ``ADR-RULE > IMPLEMENT > FIX > RESEARCH > CHORE`` per skill
  §Reference.
- :func:`derive_required_fields` — per-intent required-field list
  for ``prepare-commit-msg`` buffer pre-population.
- :func:`validate_commit_msg` — implements all six checks from
  skill §What the hook validates, single pass, no short-circuit.
- :func:`resolve_citation` — ``path/file.ext:line`` resolution
  against the staged tree or HEAD, plus the ``n/a (reason)``
  escape hatch.

A snapshot test (``tests/test_pr_intent_snapshot.py``) pins the
constants exported here to the skill's §Output format fenced
blocks so the two views cannot drift; that test is the
dual-located-rule guard per ADR-10 I-1 single-source-of-truth.

The hook itself never invokes an LLM; every check is a closed-enum
lookup or regex match or file-existence check (skill §What the
hook validates final paragraph).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType


class Intent(StrEnum):
    """Level-1 PR intent (closed enum; skill §Reference Level-1 table)."""

    RESEARCH = "RESEARCH"
    ADR_RULE = "ADR-RULE"
    IMPLEMENT = "IMPLEMENT"
    FIX = "FIX"
    CHORE = "CHORE"


class FixClass(StrEnum):
    """Level-2 CLASS sub-classifier for ``INTENT: FIX`` (skill §Reference Level-2)."""

    REPAIR = "REPAIR"
    RELAX = "RELAX"
    WORKAROUND = "WORKAROUND"


# Cross-category resolution order per skill §Reference.
_INTENT_PRIORITY: tuple[Intent, ...] = (
    Intent.ADR_RULE,
    Intent.IMPLEMENT,
    Intent.FIX,
    Intent.RESEARCH,
    Intent.CHORE,
)

# Paths that mirror upstream changes (skill §Reference «Mirror files»);
# do not independently trigger any intent.
# NOTE: knowledge/llms.txt appears here only (mirror bucket). The
# former duplicate entry in _CHORE_EXACT_PATHS has been removed because
# the mirror filter runs first in _fired_intents, making the CHORE-set
# entry dead code and causing confusing dual membership. Standalone
# llms.txt diffs still fall through to CHORE via the _fired_intents
# empty-set fallback — behaviour is unchanged, dead code is gone.
_MIRROR_PATHS: frozenset[str] = frozenset(
    {
        "HANDOFF.md",
        "knowledge/trace/exploration_log.md",
        "knowledge/adr/DIGEST.md",
        "knowledge/llms.txt",
    }
)

# CHORE-bucket exact paths / prefixes per skill §Reference.
# knowledge/llms.txt is intentionally absent here; it lives in
# _MIRROR_PATHS only (see note above).
_CHORE_EXACT_PATHS: frozenset[str] = frozenset({"pyproject.toml", ".pre-commit-config.yaml"})
_CHORE_PREFIXES: tuple[str, ...] = (".github/",)

# ADR-RULE bucket prefixes / exact paths per skill §Reference.
_ADR_RULE_EXACT_PATHS: frozenset[str] = frozenset(
    {"AGENTS.md", "knowledge/project-overview.md", "knowledge/MAINTENANCE.md"}
)
_ADR_RULE_PREFIXES: tuple[str, ...] = (
    "knowledge/adr/ADR-",
    "knowledge/anti-patterns/AP-",
    "knowledge/skills/",
)


@dataclass(frozen=True)
class StagedPath:
    """One row of ``git diff --cached --name-status`` output.

    ``status`` is git's letter (``A``, ``M``, ``D``, ``R``, ``C``, ``T``).
    Rename/copy rows expose the *destination* path; the caller is
    responsible for picking destination paths off ``R``/``C`` rows.
    """

    status: str
    path: str


@dataclass(frozen=True)
class FieldSpec:
    """Per-intent required-field row for ``prepare-commit-msg`` buffer."""

    name: str
    placeholder: str


@dataclass(frozen=True)
class Violation:
    """One commit-message validation failure (skill §What the hook validates)."""

    code: str
    message: str


# ---------------------------------------------------------------------------
# Path-shape buckets
# ---------------------------------------------------------------------------


def _is_mirror(path: str) -> bool:
    return path in _MIRROR_PATHS


def _is_adr_rule(path: str) -> bool:
    if path in _ADR_RULE_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _ADR_RULE_PREFIXES)


def _is_src_or_tests(path: str) -> bool:
    return path.startswith("src/fa/") or path.startswith("tests/")


def _is_research(path: str) -> bool:
    return path.startswith("knowledge/research/") and path.endswith(".md")


def _is_chore(path: str) -> bool:
    if path in _CHORE_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _CHORE_PREFIXES)


def classify_intent(staged_paths: Sequence[StagedPath]) -> Intent:
    """Closed-enum classifier per skill §Reference Level-1 table.

    Reads pre-parsed ``StagedPath`` rows (caller-passed; this function
    never invokes git itself, which keeps it testable). When the diff
    spans multiple intents, the higher-priority intent wins per
    ``ADR-RULE > IMPLEMENT > FIX > RESEARCH > CHORE``. Mirror-only
    diffs (no upstream-trigger path) fall back to ``CHORE``; callers
    that want the warning surface should consult
    :func:`detect_multi_intent` separately.

    The parameter is typed as ``Sequence[StagedPath]`` (not
    ``Iterable``) to make the non-exhaustion contract explicit:
    the caller must not pass a one-shot generator, because
    ``_cli_prepare`` iterates ``staged`` through multiple calls
    (``classify_intent``, ``detect_multi_intent``, ``is_mirror_only``).
    ``parse_name_status`` already returns a ``list``, satisfying this
    contract at every call site.
    """

    fired = _fired_intents(staged_paths)
    for intent in _INTENT_PRIORITY:
        if intent in fired:
            return intent
    return Intent.CHORE


def detect_multi_intent(staged_paths: Sequence[StagedPath]) -> set[Intent]:
    """Return the set of intents that fire for the given staged diff.

    Used by the prepare-commit-msg hook to emit the multi-intent
    WARNING surface per skill §No mixed PRs.
    """

    return _fired_intents(staged_paths)


def is_mirror_only(staged_paths: Sequence[StagedPath]) -> bool:
    """True iff every staged path is a mirror-bucket path.

    Skill §Reference: «If the diff is mirror-only with nothing
    upstream, the hook emits a warning». Used by the prepare hook.
    """

    materialised = [sp for sp in staged_paths if sp.path]
    if not materialised:
        return False
    return all(_is_mirror(sp.path) for sp in materialised)


def _fired_intents(staged_paths: Sequence[StagedPath]) -> set[Intent]:
    paths = [sp for sp in staged_paths if sp.path]
    non_mirror = [sp for sp in paths if not _is_mirror(sp.path)]
    if not non_mirror:
        return set()

    fired: set[Intent] = set()

    # ADR-RULE: ANY path matches → fires.
    if any(_is_adr_rule(sp.path) for sp in non_mirror):
        fired.add(Intent.ADR_RULE)

    # IMPLEMENT vs FIX: based on src/fa/** and tests/** paths.
    src_rows = [sp for sp in non_mirror if _is_src_or_tests(sp.path)]
    if src_rows:
        if all(sp.status == "A" for sp in src_rows):
            fired.add(Intent.IMPLEMENT)
        else:
            fired.add(Intent.FIX)

    # RESEARCH: sole adds under knowledge/research/*.md AND no src/tests
    # AND no rule files. The «sole» reading is structural: a RESEARCH
    # PR is research-only. If any research path is present at all the
    # research bucket fires; cross-category resolution then demotes
    # it when a higher bucket also fires.
    research_rows = [sp for sp in non_mirror if _is_research(sp.path)]
    if research_rows and all(sp.status == "A" for sp in research_rows):
        fired.add(Intent.RESEARCH)

    # CHORE: every non-mirror path is a chore path → CHORE fires.
    # A chore path appearing alongside a non-chore path does not fire
    # CHORE (the non-chore path's bucket dominates anyway).
    if non_mirror and all(_is_chore(sp.path) for sp in non_mirror):
        fired.add(Intent.CHORE)

    return fired


# ---------------------------------------------------------------------------
# Per-intent required fields (prepare-commit-msg buffer)
# ---------------------------------------------------------------------------


# Single source of truth for the required-field list per intent.
# The snapshot test pins these placeholders to the skill's §Output
# format fenced block; do NOT edit the placeholder strings without
# first updating the skill (or the snapshot test will fail).
_FIX_REQUIRED_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("INTENT", "FIX"),
    FieldSpec("CLASS", "<REPAIR | RELAX | WORKAROUND>"),
    FieldSpec("INVARIANT", "Affects: <pre-existing ADR or rule invariant>"),
    FieldSpec(
        "DEGREE-OF-FREEDOM CLOSED",
        "<one sentence | n/a (reason)>",
    ),
    FieldSpec(
        "DETERMINISTIC MECHANISM",
        "<one sentence ending with `repo/file.ext:line` | n/a (reason)>",
    ),
)

_REQUIRED_FIELDS_BY_INTENT: dict[Intent, tuple[FieldSpec, ...]] = {
    Intent.RESEARCH: (
        FieldSpec("INTENT", "RESEARCH"),
        FieldSpec("INVARIANT", "n/a"),
    ),
    Intent.ADR_RULE: (
        FieldSpec("INTENT", "ADR-RULE"),
        FieldSpec("INVARIANT", "Contract: <one sentence>"),
    ),
    Intent.IMPLEMENT: (
        FieldSpec("INTENT", "IMPLEMENT"),
        FieldSpec("INVARIANT", "Implements: <ADR or rule reference>"),
    ),
    Intent.FIX: _FIX_REQUIRED_FIELDS,
    Intent.CHORE: (
        FieldSpec("INTENT", "CHORE"),
        FieldSpec("INVARIANT", "n/a"),
    ),
}


def derive_required_fields(intent: Intent) -> list[FieldSpec]:
    """Per-intent required-field list for ``prepare-commit-msg``.

    Returns ``FieldSpec(name, placeholder)`` rows in the order the
    ``prepare-commit-msg`` hook should pre-populate them above the
    user's commit-message buffer.
    """

    return list(_REQUIRED_FIELDS_BY_INTENT[intent])


def render_prepare_buffer(intent: Intent) -> str:
    """Render the ``prepare-commit-msg`` pre-populated header block.

    Each required field becomes a ``NAME: <fill me — placeholder>``
    row except ``INTENT`` itself, which is mechanically filled. The
    output is a multi-line string ready to splice above an existing
    commit-msg buffer.
    """

    lines: list[str] = []
    for field in derive_required_fields(intent):
        if field.name == "INTENT":
            lines.append(f"INTENT: {field.placeholder}")
            continue
        lines.append(f"{field.name}: <fill me — {field.placeholder}>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commit-message validation (skill §What the hook validates)
# ---------------------------------------------------------------------------


# Closed-enum values pinned by the snapshot test against the skill's
# §Output format fenced block.
INTENT_VALUES: frozenset[str] = frozenset(intent.value for intent in Intent)
CLASS_VALUES: frozenset[str] = frozenset(cls.value for cls in FixClass)

# Header line anchors. The snapshot test asserts these match the
# field names that appear at the start of the lines inside the
# skill's §Output format fenced block.
HEADER_INTENT = "INTENT:"
HEADER_CLASS = "CLASS:"
HEADER_INVARIANT = "INVARIANT:"
HEADER_DOF_CLOSED = "DEGREE-OF-FREEDOM CLOSED:"
HEADER_DET_MECHANISM = "DETERMINISTIC MECHANISM:"
# Existing-test-protection declaration field (skill §Test-edit declaration).
# One entry per line below the header: ``tests/test_x.py — <one-line reason>``.
# Consumed by :func:`validate_test_edits`; see that function for the rule.
HEADER_TEST_EDITS = "TEST-EDITS:"

# Citation must end with `path/file.ext:line`. The path component
# must contain a dot (skill §D-4: «repo/file.ext:line»). The regex
# intentionally does NOT require a path separator so that flat-repo
# citations like `cli.py:10` are valid; extensionless files like
# Makefile cannot be cited — the skill's «.ext» requirement is
# explicit (review item #4: design choice, not a bug).
_CITATION_RE: re.Pattern[str] = re.compile(r"`?(?P<path>\S+\.\S+):(?P<line>\d+)`?\s*$")
_NA_RE: re.Pattern[str] = re.compile(r"^n/a\s*\(.+\)\s*$", re.IGNORECASE)

# Per-intent required INVARIANT prefix (skill §Reference INVARIANT-content table).
_INVARIANT_REQUIRED_PREFIXES: dict[Intent, tuple[str, ...]] = {
    Intent.RESEARCH: ("n/a",),
    Intent.ADR_RULE: ("Contract:",),
    Intent.IMPLEMENT: ("Implements:",),
    Intent.FIX: ("Affects:",),
    Intent.CHORE: ("n/a",),
}
# Public read-only view so M-7 §Q-N consumers (e.g., the ``pr.prepare``
# tool) can validate against the same table without duplicating it.
# Exporting a live dict alias would let external code mutate global
# validation behaviour at runtime; the mapping-proxy keeps ADR-10 I-1's
# single source of truth observable without making it writable.
INVARIANT_REQUIRED_PREFIXES: Mapping[Intent, tuple[str, ...]] = MappingProxyType(
    _INVARIANT_REQUIRED_PREFIXES
)


def parse_field(text: str, header: str) -> str | None:
    """Return the value of ``HEADER:`` if present in ``text`` else None.

    Header lines may appear anywhere in the commit-message body; the
    skill's §Output format mandates they open the message but the
    validator is lenient on placement so a contributor who appended
    a ``Co-Authored-By`` trailer above the header still sees a clear
    violation rather than a parse failure.

    Only the *first* occurrence of the header is captured; only the
    text on that same line is returned (no multi-line folding). A
    long single-line value is fully captured; a value that spans
    multiple lines will be truncated at the first newline.
    """

    pattern = re.compile(
        rf"^{re.escape(header)}\s*(?P<value>.*)$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group("value").strip()


def parse_test_edits(text: str) -> dict[str, str]:
    """Parse the ``TEST-EDITS:`` declaration block from a PR draft.

    Format (skill §Test-edit declaration): the header line, then one
    entry per immediately-following line, each ``<path> — <reason>``
    (em-dash or ``-`` accepted). The block ends at the first blank
    line or the first line that parses as another ``HEADER:`` field.
    Returns ``{normalised_path: reason}``; malformed entry lines
    (no separator / empty reason) are EXCLUDED so an undeclared edit
    cannot smuggle through on a half-written row — the caller's
    violation message tells the author how to fix the row.
    """

    lines = text.splitlines()
    out: dict[str, str] = {}
    in_block = False
    for line in lines:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith(HEADER_TEST_EDITS):
                in_block = True
                # Same-line first entry is allowed: ``TEST-EDITS: path — reason``.
                rest = stripped[len(HEADER_TEST_EDITS) :].strip()
                if rest:
                    _add_test_edit_entry(rest, out)
            continue
        if not stripped:
            break
        # A new ``WORD:`` header terminates the block (any of the known
        # headers, or an unknown-but-header-shaped line).
        if re.match(r"^[A-Z][A-Z -]*:", stripped):
            break
        _add_test_edit_entry(stripped, out)
    return out


def _add_test_edit_entry(entry: str, out: dict[str, str]) -> None:
    # Accept em-dash (skill convention) or plain hyphen separator.
    for sep in (" — ", " - "):
        if sep in entry:
            path, _, reason = entry.partition(sep)
            path = path.strip().replace("\\", "/").removeprefix("./")
            reason = reason.strip()
            if path and reason:
                out[path] = reason
            return
    # No separator → malformed; excluded (fail-closed).


def _is_test_path(path: str) -> bool:
    """True for Python files under ``tests/`` (the protected set).

    Deliberately ``.py``-only: deleting a *data* fixture under
    ``tests/`` breaks its consuming tests LOUDLY (collection/runtime
    error), while deleting a test file silences coverage — only the
    silent direction needs a guard.
    """
    normalised = path.replace("\\", "/").removeprefix("./")
    return normalised.startswith("tests/") and normalised.endswith(".py")


def validate_test_edits(
    draft_text: str,
    classifier_intent: Intent,
    staged: Sequence[StagedPath],
) -> list[Violation]:
    """Existing-test-protection rule (research-note R-6; ImpossibleBench).

    Counters the dominant agent test-gaming move: when blocked by a
    failing test, delete or rewrite the test instead of the code.

    - ``D`` (delete) or ``R``/``C`` (rename/copy destination — the
      *source* test vanished from the dest-only ``--name-status``
      view) row on ``tests/**``: violation under EVERY intent shape.
      No declaration escape — removing a test needs a human decision,
      not a draft field.
    - ``M`` (modify) row on ``tests/**`` when ``classifier_intent``
      is ``FIX``: violation unless the path is declared under
      ``TEST-EDITS:`` with a reason. New test files (``A``) are
      always fine; ``IMPLEMENT``-shaped diffs may modify tests freely
      (extending an existing test module is normal feature work).

    SECURITY INVARIANT — classifier intent only: this function MUST
    receive the intent derived from the staged diff, NEVER the
    draft's typed ``INTENT:`` override (skill D-5). The draft is
    agent-authored; honouring the typed value here would let a
    blocked agent disarm the rule by editing its own draft. The two
    seats (IntentGuard / git hook) therefore call this with their
    ``classify_intent(...)`` result, bypassing the D-5 override that
    governs shape validation only.
    """

    violations: list[Violation] = []
    declared = parse_test_edits(draft_text)
    for row in staged:
        if not _is_test_path(row.path):
            continue
        if row.status in ("D", "R", "C"):
            violations.append(
                Violation(
                    "test_delete_blocked",
                    f"deleting/renaming an existing test is blocked: `{row.path}` "
                    f"(status {row.status}). Fix the code, not the test; if the "
                    "test is genuinely obsolete a human removes it in a "
                    "dedicated CHORE PR.",
                )
            )
        elif row.status == "M" and classifier_intent is Intent.FIX:
            if row.path not in declared:
                violations.append(
                    Violation(
                        "test_edit_undeclared",
                        f"modifying existing test `{row.path}` during a "
                        f"FIX-shaped diff requires a `{HEADER_TEST_EDITS}` "
                        "declaration line (`<path> — <one-line reason>`) in "
                        "the PR draft. Fix the code, not the test — or "
                        "declare why this test must change.",
                    )
                )
    return violations


def validate_commit_msg(
    text: str,
    intent: Intent,
    staged: Sequence[StagedPath],
    repo_root: Path,
) -> list[Violation]:
    """Run all six checks from skill §What the hook validates.

    Single pass, no short-circuit: every violation found is reported
    so the agent / contributor sees the full picture in one shot
    (the skill explicitly forbids first-failure short-circuit).
    """

    violations: list[Violation] = []
    staged_list = list(staged)

    intent_value = parse_field(text, HEADER_INTENT)
    class_value = parse_field(text, HEADER_CLASS)
    invariant_value = parse_field(text, HEADER_INVARIANT)
    dof_value = parse_field(text, HEADER_DOF_CLOSED)
    mech_value = parse_field(text, HEADER_DET_MECHANISM)

    # Check 1: INTENT line present; value in closed enum.
    if intent_value is None:
        violations.append(
            Violation(
                "intent_missing",
                f"missing `{HEADER_INTENT}` header line (expected one of: {sorted(INTENT_VALUES)})",
            )
        )
    elif intent_value not in INTENT_VALUES:
        violations.append(
            Violation(
                "intent_value_invalid",
                f"`{HEADER_INTENT} {intent_value}` not in closed enum {sorted(INTENT_VALUES)}",
            )
        )

    # Check 2: CLASS present iff INTENT is FIX; value in closed enum.
    if intent == Intent.FIX:
        if class_value is None:
            violations.append(
                Violation(
                    "class_missing",
                    f"`INTENT: FIX` requires `{HEADER_CLASS}` header line "
                    f"(one of: {sorted(CLASS_VALUES)})",
                )
            )
        elif class_value not in CLASS_VALUES:
            violations.append(
                Violation(
                    "class_value_invalid",
                    f"`{HEADER_CLASS} {class_value}` not in closed enum {sorted(CLASS_VALUES)}",
                )
            )
    elif class_value is not None:
        violations.append(
            Violation(
                "class_unexpected",
                f"`{HEADER_CLASS}` header line is only valid when "
                f"`INTENT: FIX`; got `INTENT: {intent.value}`",
            )
        )

    # Check 3: INVARIANT present; content matches the intent's required shape.
    if invariant_value is None or not invariant_value:
        violations.append(
            Violation(
                "invariant_missing",
                f"missing `{HEADER_INVARIANT}` header line",
            )
        )
    else:
        required = _INVARIANT_REQUIRED_PREFIXES[intent]
        if not any(invariant_value.lower().startswith(p.lower()) for p in required):
            violations.append(
                Violation(
                    "invariant_shape_mismatch",
                    f"`{HEADER_INVARIANT}` value `{invariant_value!r}` "
                    f"does not match the required shape for "
                    f"`INTENT: {intent.value}` "
                    f"(expected to start with one of: {list(required)})",
                )
            )

    # Checks 4-6: only fire for INTENT: FIX.
    if intent == Intent.FIX:
        violations.extend(_validate_fix_clauses(dof_value, mech_value, staged_list, repo_root))

    return violations


def _validate_fix_clauses(
    dof_value: str | None,
    mech_value: str | None,
    staged: list[StagedPath],
    repo_root: Path,
) -> list[Violation]:
    violations: list[Violation] = []

    # Check 4: DEGREE-OF-FREEDOM CLOSED and DETERMINISTIC MECHANISM
    # present and non-empty.
    if dof_value is None or not dof_value:
        violations.append(
            Violation(
                "dof_missing",
                f"`INTENT: FIX` requires `{HEADER_DOF_CLOSED}` header "
                "line (one sentence | `n/a (reason)`)",
            )
        )
    if mech_value is None or not mech_value:
        violations.append(
            Violation(
                "mechanism_missing",
                f"`INTENT: FIX` requires `{HEADER_DET_MECHANISM}` header "
                "line (one sentence ending with `path/file.ext:line` | "
                "`n/a (reason)`)",
            )
        )

    # Check 5: DETERMINISTIC MECHANISM ends with `path/file.ext:line`
    # and resolves, OR equals `n/a (reason)`.
    if mech_value:
        if not resolve_citation(mech_value, repo_root, staged):
            violations.append(
                Violation(
                    "mechanism_citation_unresolved",
                    f"`{HEADER_DET_MECHANISM}` must end with a resolving "
                    "`path/file.ext:line` citation (file in staged tree "
                    "or HEAD; line within bounds), or be `n/a (reason)`. "
                    f"Got: {mech_value!r}",
                )
            )

    # Check 6: tautology — DOF CLOSED and DETERMINISTIC MECHANISM not
    # string-identical modulo whitespace.
    if dof_value and mech_value:
        if _normalise_whitespace(dof_value) == _normalise_whitespace(mech_value):
            violations.append(
                Violation(
                    "fix_tautology",
                    f"`{HEADER_DOF_CLOSED}` and `{HEADER_DET_MECHANISM}` "
                    "are string-identical modulo whitespace; restate the "
                    "mechanism as a producer-site artefact distinct from "
                    "the degree of freedom it closes",
                )
            )

    return violations


def _normalise_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


# ---------------------------------------------------------------------------
# Citation resolution
# ---------------------------------------------------------------------------


def resolve_citation(
    citation: str,
    repo_root: Path,
    staged: Sequence[StagedPath],
) -> bool:
    """Resolve a ``DETERMINISTIC MECHANISM:`` citation.

    True iff the citation ends with ``path/file.ext:line`` AND the
    file exists in the staged tree or HEAD (worktree fallback) AND
    the line number is within the file's bounds. Also true for the
    literal ``n/a (reason)`` escape hatch — the skill accepts that
    form when the FIX has no agent-facing degree of freedom.

    Pure-Python: no git invocation. The staged tree is approximated
    via the ``staged`` argument (added/modified rows are read from
    the worktree at ``repo_root``); HEAD-only files are read from
    the worktree too (the worktree is HEAD when no edits are
    staged for that path).

    Note on staged-only files: when a cited file is recorded as
    staged but does not yet exist on disk (status ``A`` in an
    in-memory test scenario), the line-bounds check is skipped and
    the citation is accepted. In real git workflow at commit time
    the worktree always mirrors the staged tree, so the bounds
    check runs for all production calls. The docstring's claim that
    the line is «within bounds» is accurate for the on-disk path;
    the staged-only fallback is a test-harness accommodation only.
    """

    text = citation.strip()
    if _NA_RE.match(text):
        return True

    match = _CITATION_RE.search(text)
    if match is None:
        return False
    rel_path = match.group("path")
    line_number = int(match.group("line"))
    if line_number < 1:
        return False

    candidate = (repo_root / rel_path).resolve()
    repo_root_resolved = repo_root.resolve()
    try:
        candidate.relative_to(repo_root_resolved)
    except ValueError:
        return False

    if not candidate.is_file():
        # The path may be staged-only (status `A`) — in normal usage
        # the worktree mirrors the staged tree at commit time, but
        # accept any staged entry as a fallback so tests can exercise
        # the staged-only branch without touching the worktree.
        staged_set = {sp.path for sp in staged}
        if rel_path not in staged_set:
            return False
        return True

    try:
        line_count = sum(1 for _ in candidate.open("r", encoding="utf-8", errors="replace"))
    except OSError:
        return False
    return 1 <= line_number <= line_count


# ---------------------------------------------------------------------------
# Git-diff parsing helper
# ---------------------------------------------------------------------------


def parse_name_status(stdout: str) -> list[StagedPath]:
    """Parse ``git diff --cached --name-status`` output.

    Each row is ``<status>\\t<path>`` (or for renames/copies,
    ``<status>\\t<old>\\t<new>``). Rename / copy rows expose the
    destination path with status ``R`` or ``C`` so cross-category
    resolution treats the file as «touched» rather than «added».
    """

    rows: list[StagedPath] = []
    for raw in stdout.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        status_letter = parts[0][:1]
        path = parts[-1]
        rows.append(StagedPath(status=status_letter, path=path))
    return rows


# ---------------------------------------------------------------------------
# Module CLI — invoked by the prepare-commit-msg / commit-msg hooks
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> str:
    """Invoke git and return stdout; raise on non-zero exit."""

    # Waiver: fixed "git" argv, no shell; args are repo-internal constants;
    # bare "git" resolved via PATH is the portable convention.
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _find_repo_root(start: Path) -> Path:
    """Anchor-on-cwd workspace resolution per AGENTS.md (no walk-up)."""

    if (start / "knowledge" / "llms.txt").is_file():
        return start
    raise SystemExit(
        "fa.hygiene.pr_intent: not a First-Agent workspace (no knowledge/llms.txt at cwd)"
    )


def _git_dir(repo_root: Path) -> Path:
    """Return the effective ``.git`` directory for ``repo_root``.

    In a normal checkout ``.git`` is a directory. In a ``git worktree``
    checkout ``.git`` is a *file* whose content is
    ``gitdir: /path/to/.git/worktrees/<name>``; git also sets the
    ``GIT_DIR`` environment variable when running hooks so worktree
    hooks always have the correct path available.

    Resolution order (matches what the bash hook does with
    ``GIT_DIR_PATH="${GIT_DIR:-.git}"``):

    1. ``GIT_DIR`` environment variable (set by git itself when
       invoking hooks — always correct in hook context).
    2. ``repo_root / ".git"`` fallback for direct Python invocation
       outside a hook (e.g. tests, programmatic use).
    """
    env_git_dir = os.environ.get("GIT_DIR")
    if env_git_dir:
        return Path(env_git_dir)
    return repo_root / ".git"


def _is_non_validating_commit_source(repo_root: Path) -> bool:
    """Return True when the commit was created by a git operation that does
    not produce a user-authored header block.

    The ``prepare-commit-msg`` hook skips template injection for
    ``merge``, ``squash``, ``commit`` (amend), ``template``, and
    ``message`` (``-m``) sources so those commit types never receive
    the INTENT/INVARIANT placeholders. The ``commit-msg`` hook must
    apply a matching skip so it does not reject commit messages that
    were never given the chance to be pre-populated.

    Git does not pass ``COMMIT_SOURCE`` to ``commit-msg`` (only to
    ``prepare-commit-msg``), so we detect the commit type from the
    state files git leaves in the git directory and from environment
    variables:

    - ``.git/MERGE_HEAD`` — present during ``git merge`` /
      ``git pull`` (merge strategy).
    - ``.git/CHERRY_PICK_HEAD`` — present during ``git cherry-pick``.
    - ``.git/REVERT_HEAD`` — present during ``git revert``.
    - ``.git/SQUASH_MSG`` — present during ``git commit --squash``.
    - ``GIT_REFLOG_ACTION`` environment variable — git sets this to
      ``"merge"`` for merge commits and ``"commit (amend)"`` for
      ``git commit --amend``. We check for the substrings ``merge``
      and ``amend`` (case-insensitive) to cover both.

    The git directory is resolved via :func:`_git_dir` which honours
    the ``GIT_DIR`` environment variable so git worktrees work
    correctly (in a worktree ``.git`` is a file, not a directory,
    but git sets ``GIT_DIR`` to the actual git dir when running hooks).
    """
    git_dir_path = _git_dir(repo_root)

    # State-file detection (merge, cherry-pick, revert, squash).
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "SQUASH_MSG"):
        if (git_dir_path / marker).is_file():
            return True

    # Env-var detection (amend / merge via GIT_REFLOG_ACTION).
    reflog_action = os.environ.get("GIT_REFLOG_ACTION", "").lower()
    if "merge" in reflog_action or "amend" in reflog_action:
        return True

    return False


def _cli_prepare(commit_msg_file: Path, repo_root: Path) -> int:
    name_status = _run_git(["diff", "--cached", "--name-status"], cwd=repo_root)
    staged = parse_name_status(name_status)
    intent = classify_intent(staged)
    fired = detect_multi_intent(staged)
    warning_lines: list[str] = []
    if len(fired) > 1:
        warning_lines.append(
            "# WARNING (skill §No mixed PRs): multi-intent diff "
            f"detected — fired {sorted(i.value for i in fired)}; "
            "consider splitting."
        )
    if is_mirror_only(staged):
        warning_lines.append(
            "# WARNING: mirror-only diff is unusual; pick the "
            "dominant upstream intent or commit as `CHORE` if pure cleanup."
        )

    existing = commit_msg_file.read_text(encoding="utf-8") if commit_msg_file.exists() else ""
    header = render_prepare_buffer(intent)

    # Build the buffer: optional warnings, then the header block, then
    # the existing content. Use a blank line between the header block
    # and the existing git template text so editors render them as
    # distinct paragraphs. Strip any trailing newline from `existing`
    # before joining so the final write produces exactly one trailing
    # newline.
    pieces: list[str] = []
    if warning_lines:
        pieces.append("\n".join(warning_lines))
    pieces.append(header)
    if existing:
        pieces.append(existing.rstrip("\n"))
    commit_msg_file.write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
    return 0


def _cli_validate(commit_msg_file: Path, repo_root: Path) -> int:
    # Skip validation for git-generated commit messages (merge, cherry-pick,
    # revert, amend). The prepare-commit-msg hook already skips injection for
    # these sources; the validator must match so it does not hard-block
    # standard git operations that never received the INTENT/INVARIANT template.
    if _is_non_validating_commit_source(repo_root):
        return 0

    text = commit_msg_file.read_text(encoding="utf-8")

    # Message-source commits (git commit -m "...", VS Code Git extension):
    # the prepare-commit-msg hook does NOT inject the INTENT/INVARIANT
    # template for these sources (COMMIT_SOURCE=message), so the
    # commit-msg validator must not require it.  Detect by checking if
    # the message body contains an INTENT: header line.  If it doesn't,
    # the template was never injected — validate only that the subject
    # line carries a recognized conventional commit prefix.  This is the
    # lightweight commit-phase check; the full INTENT/INVARIANT format
    # is enforced for editor-buffer commits where the template IS
    # injected.
    has_intent_line = any(line.startswith("INTENT:") for line in text.splitlines())
    if not has_intent_line:
        subject = text.splitlines()[0].strip() if text.splitlines() else ""
        conventional_prefixes = (
            "RESEARCH:",
            "ADR-RULE:",
            "IMPLEMENT:",
            "FIX:",
            "CHORE:",
        )
        if any(subject.startswith(p) for p in conventional_prefixes):
            return 0
    name_status = _run_git(["diff", "--cached", "--name-status"], cwd=repo_root)
    staged = parse_name_status(name_status)
    classifier_intent = classify_intent(staged)
    # Skill D-5: «the hook is INTENT-suggestive but not INTENT-prescriptive».
    # Validate against the user-typed intent so a deliberate override
    # (recorded as a one-sentence rationale at the top of the PR
    # description) passes the shape gate; fall back to the classifier
    # intent only when the user did not type one or typed something
    # outside the closed enum (Check 1 fires either way).
    typed = parse_field(text, HEADER_INTENT)
    if typed in INTENT_VALUES:
        intent = Intent(typed)
    else:
        intent = classifier_intent
    violations = validate_commit_msg(text, intent, staged, repo_root)
    # Test-protection seat (R-6): keyed on CLASSIFIER intent — the typed
    # D-5 override governs shape checks above, never this rule (see
    # validate_test_edits docstring SECURITY INVARIANT).
    violations.extend(validate_test_edits(text, classifier_intent, staged))
    if not violations:
        return 0
    sys.stderr.write(
        f"fa.hygiene.pr_intent: commit-msg validation failed "
        f"({len(violations)} violations; classifier intent = {classifier_intent.value}, "
        f"validated against intent = {intent.value}):\n"
    )
    for violation in violations:
        sys.stderr.write(f"  [{violation.code}] {violation.message}\n")
    sys.stderr.write(
        "Source of truth: knowledge/skills/pr-creation/SKILL.md "
        "§Reference + §Output format + §What the hook validates.\n"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        sys.stderr.write("usage: python -m fa.hygiene {prepare|validate} <commit-msg-file>\n")
        return 2
    command, msg_file = args[0], Path(args[1])
    repo_root = _find_repo_root(Path.cwd())
    if command == "prepare":
        return _cli_prepare(msg_file, repo_root)
    if command == "validate":
        return _cli_validate(msg_file, repo_root)
    sys.stderr.write(f"fa.hygiene.pr_intent: unknown command {command!r}\n")
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests.
    raise SystemExit(main())
