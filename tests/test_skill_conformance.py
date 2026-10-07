"""I01/SLICE4 — the authoring chain closes: skill text -> parser -> pre-check.

The planning skills are the *producers* of plan text. ``knowledge/skills/
{plan-authoring,feature-planning}/SKILL.md`` are injected into the live planner
prompt in full -- ``coder_loop.py:895`` calls ``read_skill_for_injection`` with
its default ``file_name="SKILL.md"`` from inside ``_drive_session_inner`` -- so
the ``PLAN-SKELETON`` block in them is literally the template the model copies.
``plan_ids`` is the *consumer*. These tests assert producer and consumer agree.

Contracts: CT14, CT40, CT41, CT42, CT43 (increment-01, SLICE4).

Test class: **C0** (pure parser over producer text). The C1 composition-root
pair is deliberately absent and registered, not forgotten: see
``worklogs/planning-topology-and-executable-contracts-loop/notes/
deferred-verification-register.md`` rows D1 and D3, owned by I02. Under SD-C
(ledger E93/E103) I01 ships no live-path test by design.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fa.inner_loop.plan_ids import extract_plan_ids, precheck

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "knowledge" / "skills"

#: The two skills whose body teaches plan grammar and is injected at planning time.
PLANNING_SKILLS = ("plan-authoring", "feature-planning")

#: CT43 pins these marker names: the SLICE1b tests key on them, so a rename is a
#: silent break, not a refactor.
SKELETON_BEGIN = "<!-- PLAN-SKELETON:BEGIN -->"
SKELETON_END = "<!-- PLAN-SKELETON:END -->"

_SKELETON_RE = re.compile(
    re.escape(SKELETON_BEGIN) + r"\n(?P<body>.*?)" + re.escape(SKELETON_END),
    re.DOTALL,
)
#: A fence line opening or closing the skeleton's *outer* code block. The skeleton
#: is wrapped in a FOUR-backtick fence precisely because it nests a three-backtick
#: ``verify`` block, so this must match four or more -- stripping three-backtick
#: lines too would delete the verify fence and silently rob every derived sample
#: of its commands.
_FENCE_RE = re.compile(r"^`{4,}[a-zA-Z]*\s*$")

#: The skeleton's placeholder notation: ``<title>``, ``<slug>``, ``<N>``.
_PLACEHOLDER_RE = re.compile(r"<[^<>\n]+>")

#: CT41 -- the pre-rename tier. ``S#`` is the literal token the old grammar used
#: for a step/slice card. Inside a plan it is ambiguous (ledger E106), so no text
#: that teaches an agent how to write a plan may still use it.
_PRE_RENAME_TOKEN_RE = re.compile(r"\bS#")


def _skill_path(skill: str, file_name: str = "SKILL.md") -> Path:
    return SKILLS_ROOT / skill / file_name


def skeleton_of(skill: str) -> str:
    """Return the ``PLAN-SKELETON`` body of *skill*, fence lines removed.

    Raises if the markers are missing: a skeleton that cannot be found must be a
    hard error, never an empty string that makes every assertion below pass
    vacuously.
    """
    text = _skill_path(skill).read_text(encoding="utf-8")
    match = _SKELETON_RE.search(text)
    if match is None:
        raise AssertionError(f"{skill}: no {SKELETON_BEGIN} ... {SKELETON_END} block")
    body = match.group("body")
    kept = [line for line in body.splitlines() if not _FENCE_RE.match(line)]
    return "\n".join(kept) + "\n"


def derive_sample(skeleton: str) -> str:
    """CT42 -- the documented substitution that turns the skeleton into a sample.

    Exactly one rule: **every ``<...>`` placeholder becomes the literal word
    ``sample``.** Nothing else is rewritten -- no field is added, removed, or
    reordered, and no value is chosen for the author.

    That single rule is the whole anti-theater mechanism. Because the sample is
    computed from the skill file on every run, it cannot drift away from the
    skeleton, and it cannot be quietly tuned until the lint goes green: the only
    way to make these tests pass is to fix the skeleton itself.

    It is also why the skeleton may not carry alternation notation such as
    ``a | b`` (Q40, resolved (b)). A placeholder has one obvious substitution; an
    alternation does not, and picking a branch here would be this function
    inventing grammar the skill never taught.
    """
    return _PLACEHOLDER_RE.sub("sample", skeleton)


def _fail_diagnostics(text: str) -> list[str]:
    report = precheck(text)
    return [f"{d.rule} (line {d.line}): {d.message}" for d in report.diagnostics if d.severity == "FAIL"]


# --------------------------------------------------------------------------- #
# Non-vacuity guards: these run first and protect every assertion below.
# --------------------------------------------------------------------------- #


def test_both_planning_skills_exist_and_embed_a_skeleton() -> None:
    """Guard: a typo'd skill name must not turn the suite into a green no-op."""
    for skill in PLANNING_SKILLS:
        path = _skill_path(skill)
        assert path.is_file(), f"{path} is missing"
        body = skeleton_of(skill)
        assert "## SLICE1:" in body, f"{skill}: skeleton teaches no SLICE1 heading"
        assert len(body.splitlines()) >= 10, f"{skill}: skeleton is suspiciously short"


# --------------------------------------------------------------------------- #
# CT40 -- the skeleton is itself a valid plan.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", PLANNING_SKILLS)
def test_the_skeleton_is_itself_a_valid_plan(skill: str) -> None:
    """CT40 -- the text the planner copies must survive its own lint.

    Before this slice both skeletons emitted three ``deps-undefined-slice``
    failures from ``DEPS: SLICE<a>, SLICE<b> | -``: the parser read the
    alternation bar and the two placeholders as literal slice names. An author
    who copied the skeleton and linted it was greeted by three errors about
    grammar the skill itself had written.
    """
    skeleton = skeleton_of(skill)
    failures = _fail_diagnostics(skeleton)
    assert failures == [], f"{skill}: skeleton does not pre-check clean:\n  " + "\n  ".join(failures)


# --------------------------------------------------------------------------- #
# CT14 + CT42 -- a sample derived from the skill parses and pre-checks clean.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", PLANNING_SKILLS)
def test_a_sample_derived_from_the_skill_parses(skill: str) -> None:
    """CT14 (parse half) -- the sample yields real structure, not an empty hull.

    ``extract_plan_ids`` never raises; it returns empties. So asserting "it
    parsed" is worthless unless the fields are checked.
    """
    sample = derive_sample(skeleton_of(skill))
    plan = extract_plan_ids(sample)

    assert plan.slices == ("SLICE1",), f"{skill}: slices={plan.slices!r}"
    (record,) = plan.slice_records
    assert record.intent.strip(), f"{skill}: INTENT did not survive substitution"
    assert [ct for ct, _cls, _text in record.contracts] == ["CT1", "CT2", "CT3"]
    assert {cls for _ct, cls, _text in record.contracts} == {
        "FUNCTIONAL",
        "CONSTRAINT",
        "PRESERVATION",
    }, f"{skill}: the skeleton must teach all three contract classes"
    assert record.test_paths, f"{skill}: TESTS: line produced no path"
    assert record.steps_mode in {"prescriptive", "outcome"}, f"{skill}: steps_mode={record.steps_mode!r}"
    assert record.commands, f"{skill}: the verify block produced no command"


@pytest.mark.parametrize("skill", PLANNING_SKILLS)
def test_a_sample_derived_from_the_skill_prechecks_clean(skill: str) -> None:
    """CT14 (pre-check half) -- zero FAIL diagnostics, which is the slice's claim."""
    sample = derive_sample(skeleton_of(skill))
    failures = _fail_diagnostics(sample)
    assert failures == [], f"{skill}: derived sample has failures:\n  " + "\n  ".join(failures)


@pytest.mark.parametrize("skill", PLANNING_SKILLS)
def test_the_sample_is_derived_from_the_skill_not_frozen(skill: str) -> None:
    """CT42 -- kill-check on the producer.

    Damage the skeleton the way a careless edit would and the derived sample must
    go red. If this passes while the skeleton is broken, the fixture is a
    hand-written copy pretending to be derived, and CT14 proves nothing about the
    text the planner is actually shown.
    """
    skeleton = skeleton_of(skill)
    assert "DEPS:" in skeleton, f"{skill}: no DEPS: line to damage"

    damaged = re.sub(r"(?m)^DEPS:.*$", "DEPS: SLICE99", skeleton)
    assert damaged != skeleton, f"{skill}: the DEPS: line was not replaced"

    failures = _fail_diagnostics(derive_sample(damaged))
    assert any("deps-undefined-slice" in f for f in failures), (
        f"{skill}: a skeleton depending on an undeclared SLICE99 still looked clean; "
        f"the sample is not tracking the skill file. Diagnostics: {failures}"
    )


# --------------------------------------------------------------------------- #
# CT41 -- no producer text teaches the pre-rename tier.
# --------------------------------------------------------------------------- #


def _producer_texts() -> list[Path]:
    """Every skill text an agent is ever shown: full bodies and inject condensates."""
    paths = sorted(SKILLS_ROOT.glob("*/SKILL.md")) + sorted(SKILLS_ROOT.glob("*/INJECT.md"))
    return paths


def test_the_producer_corpus_is_not_empty() -> None:
    """Guard: a broken glob would make CT41 pass over nothing."""
    paths = _producer_texts()
    assert len(paths) >= 8, f"expected the skills tree, found {len(paths)}: {paths}"
    names = {p.parent.name for p in paths}
    assert set(PLANNING_SKILLS) <= names, f"planning skills missing from corpus: {names}"


def test_no_producer_text_teaches_the_pre_rename_tier() -> None:
    """CT41 -- one grammar, everywhere an agent reads one.

    The rename made ``S#`` ambiguous inside a plan (E106), and the parser rejects
    it. A skill that still teaches it hands the planner two incompatible
    grammars, and the half the harness can read is not the half the id table
    declares.
    """
    offenders: list[str] = []
    for path in _producer_texts():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _PRE_RENAME_TOKEN_RE.search(line):
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert offenders == [], "producer text still teaches the pre-rename tier:\n  " + "\n  ".join(offenders)


def test_the_pre_rename_scanner_actually_matches() -> None:
    """Non-vacuity for CT41: a regex typo must not make the scan silently clean."""
    assert _PRE_RENAME_TOKEN_RE.search("maps to >=1 CT#, S#, and T#")
    assert _PRE_RENAME_TOKEN_RE.search("## EDIT PACKET `E# / S#`")
    # And it must not fire on the post-rename ids, or the fix would be impossible.
    assert not _PRE_RENAME_TOKEN_RE.search("SLICE1 depends on SLICE2")
    assert not _PRE_RENAME_TOKEN_RE.search("- [ ] STEP3: do the thing (exit: green)")
    assert not _PRE_RENAME_TOKEN_RE.search("every GAP# maps to a CT#")


# --------------------------------------------------------------------------- #
# CT43 -- preservation.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", PLANNING_SKILLS)
def test_the_skeleton_marker_names_are_unchanged(skill: str) -> None:
    """CT43 -- SLICE1b's CT22 test keys on these exact strings."""
    text = _skill_path(skill).read_text(encoding="utf-8")
    assert SKELETON_BEGIN in text and SKELETON_END in text, f"{skill}: skeleton markers renamed"


def test_the_schema_oracle_markers_are_unchanged() -> None:
    """CT43 -- the §4 executable oracle is a separate contract; do not disturb it."""
    schema = (
        REPO_ROOT
        / "worklogs"
        / "planning-topology-and-executable-contracts-loop"
        / "notes"
        / "artifact-schema-and-grammar.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "<!-- SCHEMA4-EXAMPLE:BEGIN -->",
        "<!-- SCHEMA4-EXAMPLE:END -->",
        "<!-- SCHEMA4-EXPECTED:BEGIN -->",
        "<!-- SCHEMA4-EXPECTED:END -->",
    ):
        assert marker in schema, f"schema §4 oracle marker missing: {marker}"
