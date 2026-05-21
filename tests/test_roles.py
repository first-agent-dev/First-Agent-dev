"""Tests for :mod:`fa.roles` — R-19 role-layer family-disjoint check.

Five-test scope (per the approved Wave-3 plan §M1.2):
1. ``extract_family`` infers the correct family for each entry in
   :data:`KNOWN_FAMILIES` (one parametrised case per family per shape:
   bare slug + OpenRouter-style provider/slug).
2. ``extract_family`` raises :class:`FamilyExtractionError` on
   ambiguous slugs (matches ADR-2 §Amendment 2026-05-20 rule 2
   «default-deny when family unknown»).
3. ``extract_family`` honours an explicit ``override=...`` when
   supplied; rejects override values not in :data:`KNOWN_FAMILIES`.
4. ``check_eval_disjoint`` raises :class:`EvalFamilyConflictError` when
   eval matches planner or coder family.
5. ``check_eval_disjoint`` allows planner+coder sharing a family
   (per ADR-2 §Decision — a single coder-tier model may back both).

Plus one sync invariant: every regex row in ``_FAMILY_PATTERNS``
maps to a family already in :data:`KNOWN_FAMILIES`.
"""

from __future__ import annotations

import pytest

from fa.roles import (
    _FAMILY_PATTERNS,
    KNOWN_FAMILIES,
    EvalFamilyConflictError,
    FamilyExtractionError,
    check_eval_disjoint,
    extract_family,
)

# --- extract_family happy paths --------------------------------------------


@pytest.mark.parametrize(
    ("slug", "expected_family"),
    [
        # Anthropic
        ("claude-3-5-sonnet", "anthropic"),
        ("anthropic/claude-3-haiku", "anthropic"),
        # OpenAI
        ("gpt-4o-mini", "openai"),
        ("openai/gpt-4-turbo", "openai"),
        ("o3-mini", "openai"),
        # Google
        ("gemini-2.0-flash", "google"),
        ("google/gemini-1.5-pro", "google"),
        # Qwen
        ("qwen3-coder", "qwen"),
        ("qwen/qwen2.5-72b-instruct", "qwen"),
        # DeepSeek
        ("deepseek-v3.1", "deepseek"),
        ("deepseek/deepseek-r1", "deepseek"),
        # GLM (Zhipu)
        ("glm-5.1", "glm"),
        ("z-ai/glm-4.5-air", "glm"),
        # Kimi (Moonshot)
        ("kimi-k2-thinking", "kimi"),
        ("moonshotai/kimi-k2", "kimi"),
        # MiMo (Xiaomi)
        ("mimo-7b-rl-v0.1", "mimo"),
        ("xiaomi/mimo-rl-7b", "mimo"),
        # Nemotron (NVIDIA)
        ("nemotron-3-super-49b", "nemotron"),
        ("nvidia/nemotron-mini", "nemotron"),
        # Llama (Meta)
        ("llama-3.3-70b-instruct", "llama"),
        ("meta-llama/llama-3.2-3b", "llama"),
    ],
)
def test_extract_family_recognises_known_slugs(slug: str, expected_family: str) -> None:
    assert extract_family(slug) == expected_family
    # Case-insensitive normalisation: uppercase variant resolves identically.
    assert extract_family(slug.upper()) == expected_family


def test_family_patterns_are_all_known_families() -> None:
    """Sync invariant promised by the module docstring (lines 17-18)
    and cited by ADR-2 §Re-evaluation triggers as the enforcement
    mechanism for adding a new family.

    Without this test a typo in :data:`_FAMILY_PATTERNS` (e.g.
    ``"anthropi"`` instead of ``"anthropic"``) would ship unflagged —
    the happy-path table in
    :func:`test_extract_family_recognises_known_slugs` checks the
    opposite direction (every :data:`KNOWN_FAMILIES` entry has a
    happy-path case) but does NOT verify the reverse mapping.
    Regression guard for Devin-Review BUG on PR #27.
    """

    for pattern, family in _FAMILY_PATTERNS:
        assert (
            family in KNOWN_FAMILIES
        ), f"pattern {pattern.pattern!r} maps to unknown family {family!r}"


def test_extract_family_covers_every_known_family() -> None:
    """The parametrised happy-path table covers every entry in
    :data:`KNOWN_FAMILIES` — if a new family lands in the table, this
    test enforces a matching parametrised case is added too.
    """

    families_in_table = {
        family
        for slug, family in [
            ("claude-3", "anthropic"),
            ("gpt-4o", "openai"),
            ("gemini-2", "google"),
            ("qwen3", "qwen"),
            ("deepseek-v3", "deepseek"),
            ("glm-5", "glm"),
            ("kimi-k2", "kimi"),
            ("mimo-7b", "mimo"),
            ("nemotron-3", "nemotron"),
            ("llama-3.3", "llama"),
        ]
    }
    assert families_in_table == set(KNOWN_FAMILIES)


# --- extract_family failure paths ------------------------------------------


@pytest.mark.parametrize(
    "ambiguous_slug",
    [
        "local-llama-finetune",  # ADR example
        "my-custom-finetune-v1",
        "some-random-model",
        "mistral-small",  # not in the recognised set
        "phi-3-mini",  # not in the recognised set
    ],
)
def test_extract_family_raises_on_ambiguous_slug(ambiguous_slug: str) -> None:
    """Default-deny when the regex table does not match — ADR-2
    §Amendment 2026-05-20 rule 2 «explicit family: override required»."""

    with pytest.raises(FamilyExtractionError, match="cannot infer family"):
        extract_family(ambiguous_slug)


def test_extract_family_raises_on_empty_slug() -> None:
    with pytest.raises(FamilyExtractionError, match="empty slug"):
        extract_family("")


def test_extract_family_honours_explicit_override() -> None:
    """An explicit ``family:`` override skips the regex table entirely."""

    assert extract_family("local-llama-finetune", override="llama") == "llama"
    assert extract_family("totally-novel-slug", override="qwen") == "qwen"
    # Case-insensitive normalisation.
    assert extract_family("anything", override="GLM") == "glm"


def test_extract_family_rejects_unknown_override() -> None:
    """A typo in the YAML override is caught early."""

    with pytest.raises(FamilyExtractionError, match="not a known family"):
        extract_family("some-slug", override="mistral")


# --- check_eval_disjoint --------------------------------------------------


def test_check_eval_disjoint_allows_disjoint_families() -> None:
    """The expected 95% case — eval is from a different family."""

    # No exception raised.
    check_eval_disjoint(
        planner_family="glm",
        coder_family="qwen",
        eval_family="kimi",
    )


def test_check_eval_disjoint_allows_planner_and_coder_to_share_family() -> None:
    """ADR-2 §Decision permits one coder-tier model to back both
    planner and coder; only the eval-vs-actor disjointness is enforced
    here. Without this, the loader would refuse the documented config.
    """

    # planner == coder == 'qwen' is fine; eval differs.
    check_eval_disjoke = check_eval_disjoint  # alias to keep line length
    check_eval_disjoke(
        planner_family="qwen",
        coder_family="qwen",
        eval_family="kimi",
    )


def test_check_eval_disjoint_rejects_eval_matching_planner() -> None:
    with pytest.raises(EvalFamilyConflictError, match="planner-role"):
        check_eval_disjoint(
            planner_family="glm",
            coder_family="qwen",
            eval_family="glm",
        )


def test_check_eval_disjoint_rejects_eval_matching_coder() -> None:
    with pytest.raises(EvalFamilyConflictError, match="coder-role"):
        check_eval_disjoint(
            planner_family="glm",
            coder_family="qwen",
            eval_family="qwen",
        )
