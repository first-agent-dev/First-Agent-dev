"""Role-layer family-disjoint check + slug-to-family regex extractor.

ADR-2 §Amendment 2026-05-20 «Eval-role family-disjoint + primary-
source citation» rule 1+2 — role-layer enforcement complement to the
hook-layer enforcement already in
:class:`fa.inner_loop.hooks.base.HookRegistry._validate_middleware`
(R-29 cross-link rule 4 in ADR-7 §Amendment 2026-05-20).

Scope of this module is intentionally narrow:

- :func:`extract_family` — model-slug → family inference using the
  regex table from ADR-2 §Amendment 2026-05-20 rule 2. Ambiguous slugs
  raise :class:`FamilyExtractionError` so the caller can fall back to
  an explicit ``family:`` override at config-load time (matching the
  «default-deny when family unknown» stance ADR-2 borrows from ADR-6).
- :func:`check_eval_disjoint` — small pure function that verifies the
  Eval-role family differs from both the Planner and Coder families.
  Raises :class:`EvalFamilyConflictError` with both colliding families in
  the message so the user sees which override would fix it.

Intentionally **out of scope** for this Wave-3 stack:

- ``RoleConfig`` dataclass + ``~/.fa/models.yaml`` loader. The
  loader lands with the T-2 `fa run` driver, where the loaded
  config is actually consumed. Putting the loader here now would
  be YAGNI — every consumer pipes role strings in by hand and the
  loader has no caller in M-1. The check is callable today with
  caller-supplied family strings; the loader is one composition
  layer above, not a separate machine.

References:
- ``knowledge/adr/ADR-2-llm-tiering.md`` §Amendment 2026-05-20
- ``knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md`` §0 R-1
  (Cornell P-1 + Simula P-2 - same-family ensembles correlation ~+0.6).
- ``knowledge/adr/ADR-7-inner-loop-tool-registry.md``
  §Amendment 2026-05-20 rule 4 (cross-linked hook-layer check).
"""

from __future__ import annotations

import re

# Families recognised by the regex extractor. The set is closed at the
# training-distribution level per ADR-2 §Amendment 2026-05-20 rule 1
# («glm-*, qwen*, deepseek-*, kimi-*, mimo-*, claude-*, gpt-*,
# gemini-*, ... are each separate families»). Adding a new family
# means adding a new row to the regex table AND extending this set;
# the two MUST stay in sync (the test suite asserts this).
KNOWN_FAMILIES: frozenset[str] = frozenset(
    {
        "anthropic",
        "openai",
        "google",
        "qwen",
        "deepseek",
        "glm",
        "kimi",
        "mimo",
        "nemotron",
        "llama",
    }
)


# Regex table: ordered list of ``(pattern, family)`` pairs evaluated
# top-to-bottom; the first matching pattern wins. Ordered list (not
# dict) so the «more specific before more general» discipline is
# explicit — a future ``anthropic-haiku`` row must sit above the
# generic ``^claude-`` row to match correctly.
#
# Each pattern is matched against the model-slug LOWERCASED —
# OpenRouter and most provider slugs are case-insensitive in practice;
# normalising once at the extractor boundary avoids per-row ``re.I``
# noise.
_FAMILY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Anthropic Claude family. Both ``claude-*`` and OpenRouter's
    # ``anthropic/claude-*`` slug form match here.
    (re.compile(r"^(?:anthropic/)?claude(?:-|$)"), "anthropic"),
    (re.compile(r"^anthropic/"), "anthropic"),
    # OpenAI GPT family. ``gpt-*``, ``o1-*``, ``o3-*`` all share the
    # OpenAI training distribution per the ADR.
    (re.compile(r"^(?:openai/)?gpt(?:-|$)"), "openai"),
    (re.compile(r"^(?:openai/)?o[1-9](?:-|$)"), "openai"),
    (re.compile(r"^openai/"), "openai"),
    # Google Gemini family.
    (re.compile(r"^(?:google/)?gemini(?:-|$)"), "google"),
    (re.compile(r"^google/"), "google"),
    # Alibaba Qwen family. ``qwen-*``, ``qwen2-*``, ``qwen2.5-*`` and
    # OpenRouter's ``qwen/*`` all collapse to the same family.
    (re.compile(r"^(?:qwen/)?qwen"), "qwen"),
    (re.compile(r"^qwen/"), "qwen"),
    # DeepSeek family.
    (re.compile(r"^(?:deepseek/)?deepseek(?:-|$)"), "deepseek"),
    (re.compile(r"^deepseek/"), "deepseek"),
    # Zhipu GLM family. ``glm-*`` + OpenRouter ``z-ai/glm-*`` per the
    # ADR Amendment 2026-05-20 example.
    (re.compile(r"^(?:z-ai/)?glm(?:-|$)"), "glm"),
    (re.compile(r"^z-ai/"), "glm"),
    # Moonshot Kimi family. ``kimi-*`` + OpenRouter ``moonshotai/*``
    # per the ADR Amendment 2026-05-20 example.
    (re.compile(r"^(?:moonshotai/)?kimi(?:-|$)"), "kimi"),
    (re.compile(r"^moonshotai/"), "kimi"),
    # Xiaomi MiMo family.
    (re.compile(r"^(?:xiaomi/)?mimo(?:-|$)"), "mimo"),
    (re.compile(r"^xiaomi/"), "mimo"),
    # NVIDIA Nemotron family.
    (re.compile(r"^(?:nvidia/)?nemotron(?:-|$)"), "nemotron"),
    (re.compile(r"^nvidia/"), "nemotron"),
    # Meta Llama family. Bare ``llama-*`` only (no ``llama-finetune``
    # passthrough — that's ambiguous, see the ADR's
    # ``local-llama-finetune`` example).
    (re.compile(r"^(?:meta-llama/)?llama(?:-|$)"), "llama"),
    (re.compile(r"^meta-llama/"), "llama"),
)


class FamilyExtractionError(ValueError):
    """Raised when ``extract_family`` cannot infer a family from the slug.

    The caller (loader / role-config layer) is expected to recover by
    consulting an explicit ``family:`` override tagged in
    ``~/.fa/models.yaml`` per ADR-2 §Amendment 2026-05-20 rule 2.
    """


class EvalFamilyConflictError(ValueError):
    """Raised when the eval-role family overlaps planner or coder family.

    Message includes both colliding roles so the user knows which
    override would fix the config (e.g. «eval=glm conflicts with
    coder=glm — set eval to a non-glm model»).
    """


def extract_family(slug: str, *, override: str | None = None) -> str:
    """Infer the family of a model slug, or honour an explicit override.

    Args:
        slug: Provider-prefixed or bare model identifier
            (e.g. ``"z-ai/glm-5.1"``, ``"qwen3-coder"``,
            ``"anthropic/claude-3-5-sonnet"``).
        override: Optional explicit family from a ``family:`` field
            in ``~/.fa/models.yaml``. When set, the regex table is
            skipped and this value is validated against
            :data:`KNOWN_FAMILIES` only.

    Returns:
        The family string (lowercase), guaranteed to be a member of
        :data:`KNOWN_FAMILIES`.

    Raises:
        FamilyExtractionError: When no override is supplied and the
            regex table does not match (the «default-deny when family
            unknown» branch); also when the override is set but not a
            member of :data:`KNOWN_FAMILIES`.
    """

    if override is not None:
        normalised = override.strip().lower()
        if normalised not in KNOWN_FAMILIES:
            raise FamilyExtractionError(
                f"family override {override!r} is not a known family "
                f"(known: {sorted(KNOWN_FAMILIES)})"
            )
        return normalised
    if not slug:
        raise FamilyExtractionError("cannot infer family from empty slug")
    normalised_slug = slug.strip().lower()
    for pattern, family in _FAMILY_PATTERNS:
        if pattern.match(normalised_slug):
            return family
    raise FamilyExtractionError(
        f"cannot infer family from slug {slug!r}; tag it with an explicit "
        "'family:' field in ~/.fa/models.yaml"
    )


def check_eval_disjoint(
    *,
    planner_family: str,
    coder_family: str,
    eval_family: str,
) -> None:
    """Verify the eval-role family is disjoint from planner and coder.

    Per ADR-2 §Amendment 2026-05-20 rule 1: same-family eval replicates
    the acting-role's training-distribution bias (Cornell P-1 / Simula
    P-2 - see ADR-2 amendment text for the ensemble-error correlation
    figures: ~+0.6 same-family vs ~-0.05 cross-family).

    Args:
        planner_family: Planner-role family (already extracted).
        coder_family: Coder-role family (already extracted).
        eval_family: Eval-role family (already extracted).

    Raises:
        EvalFamilyConflictError: When ``eval_family`` matches either
            ``planner_family`` or ``coder_family``. Note: planner and
            coder MAY share a family (ADR-2 §Decision routing table
            allows a single «coder-tier» model to back both roles);
            only the eval-vs-actor disjointness is enforced here.
    """

    if eval_family == planner_family:
        raise EvalFamilyConflictError(
            f"eval-role family {eval_family!r} conflicts with planner-role "
            f"family {planner_family!r} — ADR-2 §Amendment 2026-05-20 "
            "requires eval be from a disjoint training distribution; "
            "override eval to a different family."
        )
    if eval_family == coder_family:
        raise EvalFamilyConflictError(
            f"eval-role family {eval_family!r} conflicts with coder-role "
            f"family {coder_family!r} — ADR-2 §Amendment 2026-05-20 "
            "requires eval be from a disjoint training distribution; "
            "override eval to a different family."
        )


__all__ = [
    "KNOWN_FAMILIES",
    "EvalFamilyConflictError",
    "FamilyExtractionError",
    "check_eval_disjoint",
    "extract_family",
]
