"""``~/.fa/models.yaml`` loader (T-4 — pairs with T-2 / ADR-9).

This module is the per-role config-load entry point for the T-2
provider client. It walks ``~/.fa/models.yaml``, materialises one
:class:`fa.providers.chain.ChainConfig` per role, runs each chain's
config-load validator (ADR-9 §1), and enforces the cross-role
family-disjoint invariant from
:func:`fa.roles.check_eval_disjoint` (ADR-2 §Amendment 2026-05-20
rule 1) when ``planner``, ``coder``, and ``eval`` are all declared.

Loader contract (ADR-9 §1 schema, verbatim):

.. code-block:: yaml

    coder:
      model:  "deepseek-v3"
      family: "deepseek"
      chain:
        - provider: openrouter
          slug:     "deepseek/deepseek-chat-v3"
          base_url: "https://openrouter.ai/api/v1"
          api_key_env: OPENROUTER_API_KEY
          cooldown_seconds: 3   # optional: local cooldown floor after transient failure
          timeout_seconds: 15   # optional: per-request HTTP timeout
          httpx_retries: 1      # optional: reserved transport retry knob (future transport use)
          extra_headers:        # optional: extra HTTP headers for this route
            HTTP-Referer: "https://example.invalid"
        - provider: fireworks
          slug:     "accounts/fireworks/models/deepseek-v3"
          base_url: "https://api.fireworks.ai/inference/v1"
          api_key_env: FIREWORKS_API_KEY

    planner:
      model:  "glm-5p2"
      family: "glm"
      chain:
        - provider: fireworks
          slug: "accounts/fireworks/models/glm-5p2"
          base_url: "https://api.fireworks.ai/inference/v1"
          api_key_env: FIREWORKS_API_KEY
          cooldown_seconds: 3

    eval:
      model:  "qwen-3-32b"
      family: "qwen"
      chain: [...]

The four ADR-2 §Decision roles (``planner``, ``coder``, ``debug``,
``eval``) are recognised but **NOT** required by this loader — a
v0.1 config with only ``coder`` declared is a legal file and yields
``ModelsConfig(roles={"coder": ...})``. The family-disjoint check
is a no-op when fewer than three of ``planner`` / ``coder`` /
``eval`` are declared; the caller (the inner-loop runtime) decides
whether a missing role is a fatal error for its workflow.

Errors raised at load time (fail-fast, never lazy):

- :class:`fa.providers.errors.ConfigurationError` — malformed YAML
  structure, malformed role entry, empty / unknown / reserved
  provider in a chain entry, missing required chain-entry field,
  invalid ``base_url`` scheme, missing ``api_key_env`` env var,
  etc. (see :meth:`fa.providers.chain.ChainConfig.validate` for
  the full taxonomy).
- :class:`fa.roles.EvalFamilyConflictError` — eval-role family
  matches planner or coder family (ADR-2 §Amendment 2026-05-20
  rule 1; same-family ensembles correlate at ~+0.6 per the
  Cornell P-1 / Simula P-2 study cited there).

References:

- ``knowledge/adr/ADR-9-llm-provider-client.md`` §1 (chain config
  schema), §7 (family-disjoint preservation across the chain).
- ``knowledge/adr/ADR-2-llm-tiering.md`` §Amendment 2026-05-20
  (role-layer family-disjoint enforcement).
- :mod:`fa.providers.chain` — :func:`chain_from_mapping` +
  :class:`ChainConfig.validate` (the loader composes these per
  role row).
- :mod:`fa.roles` — :func:`check_eval_disjoint` + family
  extraction.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from fa.providers.chain import ChainConfig, chain_from_mapping
from fa.providers.errors import ConfigurationError
from fa.roles import check_eval_disjoint

DEFAULT_MODELS_YAML_PATH: Path = Path.home() / ".fa" / "models.yaml"

# Roles that participate in the ADR-2 §Amendment 2026-05-20 rule 1
# family-disjoint check. The set is closed: the check only fires
# when all three are declared (the loader does not synthesise a
# missing role from defaults).
_FAMILY_DISJOINT_ROLES: frozenset[str] = frozenset({"planner", "coder", "eval"})

# The two «actor» roles that the eval-role family must be disjoint
# from per ADR-2 §Amendment 2026-05-20 rule 1. Used by
# :func:`_partial_disjoint_warning` to surface partial-config gaps.
_ACTOR_ROLES: frozenset[str] = frozenset({"planner", "coder"})


def _partial_disjoint_warning(role_names: frozenset[str]) -> str | None:
    """Surface the partial-config gap in the family-disjoint check.

    The hard ``check_eval_disjoint`` call site only fires when all
    three of planner / coder / eval are declared (see
    :data:`_FAMILY_DISJOINT_ROLES` and the call site below). When
    ``eval`` is declared alongside *exactly one* actor (planner XOR
    coder), the loader's hard gate is silent — but ADR-2 §Amendment
    2026-05-20 rule 1 («Eval-role MUST be from a family disjoint from
    Planner AND Coder») still applies pairwise to the declared actor.

    This helper returns a warning string for that exact partial shape
    so the caller (the inner-loop runtime) can log the gap and decide
    whether to fail or accept. Returns ``None`` when:

    - ``eval`` is not declared (no gap — the rule is eval-anchored);
    - ``eval`` is declared with *both* actors (the hard
      ``check_eval_disjoint`` call site fires);
    - ``eval`` is declared *alone* (no declared actor to be disjoint
      from — vacuously satisfied).

    Rationale: this is a Agent Review PR-#13 follow-up («F1» —
    partial-config bypass). The fix shape is option B (WARNING,
    keep current «caller decides» behaviour) rather than option A
    (hard pairwise enforcement) because option A would change a
    deliberate design choice (ADR-2 §Sub-amendment 2026-05-21
    §Decision rule 2 says «call `check_eval_disjoint` **once**»,
    singular — the loader's hard gate matches that wording). Option
    B surfaces the gap visibly without re-opening the ADR.
    """

    if "eval" not in role_names:
        return None
    declared_actors = _ACTOR_ROLES & role_names
    if len(declared_actors) != 1:
        return None
    only_actor = next(iter(declared_actors))
    missing_actor = next(iter(_ACTOR_ROLES - declared_actors))
    return (
        f"models.yaml declares 'eval' + {only_actor!r} but not "
        f"{missing_actor!r}; the loader's hard family-disjoint gate "
        "fires only when all three of planner / coder / eval are "
        f"declared, so ADR-2 §Amendment 2026-05-20 rule 1 "
        f"(eval-vs-{only_actor} disjointness) is NOT enforced by the "
        "loader for this config shape — the caller must verify the "
        "rule holds before using the config, or declare the missing "
        f"{missing_actor!r} role so the hard gate fires."
    )


@dataclass(frozen=True)
class ModelsConfig:
    """Validated snapshot of ``~/.fa/models.yaml``.

    ``roles`` maps role name → :class:`ChainConfig`; keys are
    whatever the YAML file declares (the loader does not synthesise
    missing roles). ``warnings`` collects best-effort heuristic
    findings from each chain's
    :meth:`fa.providers.chain.ChainConfig.validate` call — slug
    family mismatches, mixed-adapter chains, ``http://`` base URLs
    on a localhost gateway, etc. — so the caller can log them
    without losing context. Hard errors (unknown provider, missing
    ``api_key_env``, family conflict, ...) are raised, not
    collected.
    """

    roles: Mapping[str, ChainConfig]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def load_models_config(
    text: str,
    *,
    env: Mapping[str, str] | None = None,
    require_api_keys: bool = True,
) -> ModelsConfig:
    """Parse + validate a ``~/.fa/models.yaml`` document.

    Args:
        text: Raw YAML body. Empty / whitespace-only / a single
            YAML ``~`` returns an empty :class:`ModelsConfig` (no
            roles, no warnings) — same behaviour as a missing file
            via :func:`load_models_config_from_path`, so the inner-
            loop can decide whether absence is fatal for its
            workflow.
        env: Optional environment mapping used to validate each
            chain entry's ``api_key_env`` lookup. Defaults to
            ``os.environ``. Tests pass a custom dict to exercise
            missing-env failure paths without polluting the real
            environment.

    Returns:
        :class:`ModelsConfig` with ``roles`` populated for every
        top-level key in the YAML, and ``warnings`` accumulating
        per-role validator hints.

    Raises:
        ConfigurationError: When the YAML root is not a mapping,
            when a role value is not a mapping, when a chain entry
            is malformed per ADR-9 §1, when ``api_key_env`` is
            missing from ``env``, or when any other config-load
            invariant from :meth:`ChainConfig.validate` is
            violated.
        EvalFamilyConflictError: When ``planner``, ``coder``, and
            ``eval`` are all declared and the eval-role family
            matches planner or coder family (ADR-2 §Amendment
            2026-05-20 rule 1).

    Partial-config gap (PR-#13 follow-up «F1»):
        When ``eval`` is declared alongside *exactly one* actor
        role (planner XOR coder), the hard family-disjoint gate
        below is silent — but ADR-2 §Amendment 2026-05-20 rule 1
        still applies pairwise. The loader appends a warning to
        ``ModelsConfig.warnings`` for that exact shape via
        :func:`_partial_disjoint_warning` so the caller can log
        the gap. Caller-side enforcement is intentional: ADR-2
        §Sub-amendment 2026-05-21 §Decision rule 2 says «call
        ``check_eval_disjoint`` **once** before returning the
        parsed config» (singular) — the loader's hard gate
        matches that wording.
    """

    # ``yaml.safe_load`` returns ``None`` for empty / whitespace-only
    # / ``null``-only documents; treat all three as «no config».
    # ``yaml.safe_load`` (NOT ``yaml.load``) is mandatory here — the
    # loader contract is data-only; arbitrary Python tag execution
    # is a remote-code-execution footgun on a user-edited config
    # file. The pyproject dependency comment pins this.
    raw_root: Any = yaml.safe_load(text)
    if raw_root is None:
        return ModelsConfig(roles={})
    if not isinstance(raw_root, Mapping):
        raise ConfigurationError(
            f"models.yaml root must be a mapping of role names to role configs; "
            f"got {type(raw_root).__name__}"
        )

    environ: Mapping[str, str] = env if env is not None else os.environ

    roles: dict[str, ChainConfig] = {}
    warnings: list[str] = []
    for role_name, raw_role in raw_root.items():
        if not isinstance(role_name, str):
            raise ConfigurationError(
                f"models.yaml role names must be strings; got "
                f"{type(role_name).__name__} for {role_name!r}"
            )
        if raw_role is None:
            raise ConfigurationError(
                f"models.yaml role {role_name!r}: role config is null; "
                "expected a mapping with `model`, `family`, and `chain` fields"
            )
        if not isinstance(raw_role, Mapping):
            raise ConfigurationError(
                f"models.yaml role {role_name!r}: role config must be a mapping; "
                f"got {type(raw_role).__name__}"
            )
        chain_config = chain_from_mapping(role_name, raw_role)
        warnings.extend(chain_config.validate(environ, require_api_keys=require_api_keys))
        roles[role_name] = chain_config

    # Family-disjoint check (ADR-2 §Amendment 2026-05-20 rule 1).
    # Only fires when all three of planner / coder / eval are
    # declared — the loader does not synthesise a missing role nor
    # invent a family value. Two-role or single-role configs skip
    # the check; the caller decides whether that's acceptable for
    # its workflow.
    #
    # ``check_eval_disjoint`` does a case-sensitive ``==`` comparison
    # and its docstring says it expects «already extracted» families
    # (the lowercased form returned by ``fa.roles.extract_family``).
    # ``ChainConfig.family`` is already normalised to lowercase via
    # ``.strip().lower()`` by ``chain_from_mapping`` at the producer
    # site — see :func:`fa.providers.chain.chain_from_mapping` for
    # the rationale (without producer-side normalisation, a YAML
    # ``family: "DeepSeek"`` vs ``family: "deepseek"`` casing typo
    # would silently bypass the safety-critical eval-vs-actor
    # disjoint check from ADR-2 §Amendment 2026-05-20 rule 1).
    # The explicit ``.strip().lower()`` here is defence-in-depth:
    # if a future refactor of ``chain_from_mapping`` drops the
    # producer-side normalisation, the safety-critical check at
    # this call site still holds.
    if _FAMILY_DISJOINT_ROLES.issubset(roles.keys()):
        check_eval_disjoint(
            planner_family=roles["planner"].family.strip().lower(),
            coder_family=roles["coder"].family.strip().lower(),
            eval_family=roles["eval"].family.strip().lower(),
        )

    # Partial-config gap surface (PR-#13 follow-up «F1»). The hard
    # gate above fires only when all three roles are declared; the
    # caller still needs visibility into the partial-config case
    # (eval + exactly one actor) where ADR-2 §Amendment 2026-05-20
    # rule 1 would apply pairwise but the loader does not enforce.
    # See :func:`_partial_disjoint_warning` for the rationale on
    # why this is a warning and not a hard pairwise enforcement.
    partial_warning = _partial_disjoint_warning(frozenset(roles.keys()))
    if partial_warning is not None:
        warnings.append(partial_warning)

    return ModelsConfig(roles=roles, warnings=tuple(warnings))


def load_models_config_from_path(
    path: Path = DEFAULT_MODELS_YAML_PATH,
    *,
    env: Mapping[str, str] | None = None,
    require_api_keys: bool = True,
) -> ModelsConfig:
    """Read ``path`` and parse + validate it via :func:`load_models_config`.

    Missing file yields an empty :class:`ModelsConfig` (no roles, no
    warnings) — matching the «caller decides if absence is fatal»
    policy that :mod:`fa.config` uses for ``~/.fa/config.yaml``.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ModelsConfig(roles={})
    return load_models_config(text, env=env, require_api_keys=require_api_keys)


__all__ = [
    "DEFAULT_MODELS_YAML_PATH",
    "ModelsConfig",
    "load_models_config",
    "load_models_config_from_path",
]
