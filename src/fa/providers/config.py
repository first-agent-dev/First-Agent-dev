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
        - provider: fireworks
          slug:     "accounts/fireworks/models/deepseek-v3"
          base_url: "https://api.fireworks.ai/inference/v1"
          api_key_env: FIREWORKS_API_KEY

    planner:
      model:  "kimi-k2"
      family: "kimi"
      chain: [...]

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
        warnings.extend(chain_config.validate(environ))
        roles[role_name] = chain_config

    # Family-disjoint check (ADR-2 §Amendment 2026-05-20 rule 1).
    # Only fires when all three of planner / coder / eval are
    # declared — the loader does not synthesise a missing role nor
    # invent a family value. Two-role or single-role configs skip
    # the check; the caller decides whether that's acceptable for
    # its workflow.
    if _FAMILY_DISJOINT_ROLES.issubset(roles.keys()):
        check_eval_disjoint(
            planner_family=roles["planner"].family,
            coder_family=roles["coder"].family,
            eval_family=roles["eval"].family,
        )

    return ModelsConfig(roles=roles, warnings=tuple(warnings))


def load_models_config_from_path(
    path: Path = DEFAULT_MODELS_YAML_PATH,
    *,
    env: Mapping[str, str] | None = None,
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
    return load_models_config(text, env=env)


__all__ = [
    "DEFAULT_MODELS_YAML_PATH",
    "ModelsConfig",
    "load_models_config",
    "load_models_config_from_path",
]
