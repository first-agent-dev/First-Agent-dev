"""Per-role prompt-injection modes: registry, resolution, and hot reload.

PLAN S5a (generalized). The first consumer is the coder role's per-slice
implementation ceremony (``coder_slice_ceremony``), but the module is shaped
for the injections that follow -- a planner-role injection in the workflow, and
possibly chat-role injections -- so adding one is a table entry plus a flag,
not a new plumbing path through the controller and CLI.

Three design constraints drove the shape:

1.  **Extensible.** Injections live in :data:`INJECTION_SPECS`, keyed by name.
    Adding ``planner_research_protocol`` means appending one :class:`InjectionSpec`
    and one ``FeatureFlags`` field; every hop below already carries it because
    the transport is a mapping, not a parameter per injection.

2.  **Configured per invocation.** The effective mode is resolved ONCE, at
    startup, from ``--inject <name>=<mode>`` if given, else ``~/.fa/config.yaml``,
    else ``off`` (:func:`resolve_injection_modes`). This mirrors
    ``_resolve_intent_guard_mode`` (cli.py) so the codebase has one
    override-then-config idiom rather than two.

    A deliberate NON-goal (plan v5 RK15): re-reading config mid-run. One
    ``fa workflow`` invocation is a single process spanning many stages, so a
    live re-read would only enable toggling while the agent is mid-loop --
    which is not how the toggles are used. Modes change between invocations.
    If that ever changes, the indirection at :func:`mode_for` is where a lazy
    resolver would slot back in.

3.  **Inert by default.** Every unknown, malformed, or unreadable input resolves
    to :data:`MODE_OFF`. An injection rewrites the model's context; a config
    typo must never silently turn that on. Note this is the opposite polarity
    from IntentGuard, which fails CLOSED to "enforce" because it is a safety
    gate. This is an advisory payload, so quiet is the safe direction.

The mode vocabulary is deliberately the same three states for every injection
(:data:`INJECTION_MODES`), so an operator learns it once:

``off``
    No injection, no events. Byte-identical to the pre-feature harness.
``observe``
    Emit telemetry that the trigger fired; leave the request payload untouched.
    This is the S12.4 rollout precedent -- prove the trigger is correct on real
    runs before altering any prompt.
``enforce``
    Perform the injection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Mode vocabulary ────────────────────────────────────────────────────────

MODE_OFF = "off"
MODE_OBSERVE = "observe"
MODE_ENFORCE = "enforce"

#: The closed enum every injection mode is validated against.
INJECTION_MODES: frozenset[str] = frozenset({MODE_OFF, MODE_OBSERVE, MODE_ENFORCE})

#: Where anything unrecognised lands. ``off`` and not ``observe``: an operator
#: who typo'd the mode has not consented to telemetry either, and ``off`` is the
#: only value that is provably identical to not having the feature.
FALLBACK_MODE = MODE_OFF

# ── Injection registry ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class InjectionSpec:
    """One named injection point.

    Attributes:
        name: Stable identifier, also the ``stage_kwargs``/mapping key.
        roles: Session roles this injection may fire for. A role outside this
            set always resolves to ``off``, so a planner injection cannot leak
            into a coder session by misconfiguration alone.
        read_flag: Reads this injection's raw mode off a ``FeatureFlags``.
            A direct attribute read in a lambda, never dynamic lookup by
            field name. Two repo gates depend on that: S13 bans dynamic flag
            access, and the dead-flag scanner (scripts/check_dead_flags.py)
            only recognises literal ``.field`` syntax -- a name-based registry
            would make every injection flag read as dead.
        summary: One line, for diagnostics and ``fa`` help output.
    """

    name: str
    roles: frozenset[str]
    read_flag: Callable[[object], object]
    summary: str


#: PLAN S5a/S5: the per-slice implementation ceremony
#: (feature-planning/SKILL.md 9-12) injected at coder-stage slice entry.
CODER_SLICE_CEREMONY = InjectionSpec(
    name="coder_slice_ceremony",
    roles=frozenset({"coder"}),
    read_flag=lambda flags: flags.coder_slice_ceremony_mode,  # type: ignore[attr-defined]
    summary="Per-slice implementation ceremony (before-gate, edit packet, after-gate).",
)

#: Every known injection, keyed by name. Adding an injection = adding a row
#: here plus the matching ``FeatureFlags`` field. Nothing else changes.
INJECTION_SPECS: Mapping[str, InjectionSpec] = {
    CODER_SLICE_CEREMONY.name: CODER_SLICE_CEREMONY,
}


# ── Mode resolution ────────────────────────────────────────────────────────

#: Mapping of injection name -> already-resolved mode, as carried through the
#: stage boundary. Plain strings: resolution happens once at startup.
InjectionModes = Mapping[str, str]


def normalize_mode(value: object) -> str:
    """Coerce an arbitrary config value to a valid mode.

    Total by construction: any type, any casing, any surrounding whitespace,
    and anything outside the enum resolves to :data:`FALLBACK_MODE`. Callers
    can therefore treat the result as a closed enum without re-checking.
    """
    if not isinstance(value, str):
        return FALLBACK_MODE
    candidate = value.strip().lower()
    if candidate not in INJECTION_MODES:
        return FALLBACK_MODE
    return candidate


def _load_flags(config_path: Path | None) -> object | None:
    """Read feature flags from disk, or ``None`` when unreadable.

    Never raises: an advisory feature must not be able to abort a run because
    the operator's config has a syntax error.
    """
    try:
        from fa.feature_flags import load_feature_flags_from_path

        if config_path is None:
            return load_feature_flags_from_path().flags
        return load_feature_flags_from_path(config_path).flags
    except Exception as exc:  # noqa: BLE001 - advisory; must never crash a run
        logger.warning("injection modes: config unreadable (%s); using %r", exc, FALLBACK_MODE)
        return None


def resolve_mode(spec: InjectionSpec, role: str, *, config_path: Path | None = None) -> str:
    """Resolve one injection's effective mode for *role*, reading config now.

    Role gating is applied first and unconditionally: an injection never fires
    for a role outside its :attr:`InjectionSpec.roles`, whatever the config
    says. That keeps a future planner injection from firing in a coder session
    because of a single mistyped flag.
    """
    if role not in spec.roles:
        return MODE_OFF
    flags = _load_flags(config_path)
    if flags is None:
        return FALLBACK_MODE
    try:
        raw = spec.read_flag(flags)
    except AttributeError as exc:  # spec points at a field that no longer exists
        logger.warning("injection %r: flag unreadable (%s); using %r", spec.name, exc, FALLBACK_MODE)
        return FALLBACK_MODE
    return normalize_mode(raw)


class InjectionFlagError(ValueError):
    """A ``--inject`` argument the operator wrote cannot be honoured.

    Raised rather than ignored: the operator asked for something specific, so
    silently dropping a typo would produce a run that looks configured and is
    not. Config-file problems degrade quietly to ``off``; explicit CLI input
    does not (plan Q6 -- fail closed, never guess).
    """


def parse_inject_overrides(values: Sequence[str] | None) -> dict[str, str]:
    """Parse repeatable ``--inject <name>=<mode>`` arguments.

    Every failure mode is an error, never a shrug: unknown injection name,
    unknown mode, missing ``=``, blank name, and duplicate names for the same
    injection all raise :class:`InjectionFlagError` with the valid choices in
    the message.

    Duplicates are rejected rather than last-wins because ``--inject x=off
    --inject x=enforce`` has no obvious reading, and guessing one would be
    exactly the silent misconfiguration this function exists to prevent.
    """
    overrides: dict[str, str] = {}
    for raw in values or ():
        text = str(raw).strip()
        if "=" not in text:
            raise InjectionFlagError(
                f"--inject expects <name>=<mode>, got {raw!r}. Known injections: {sorted(INJECTION_SPECS)}."
            )
        name, _, mode_text = text.partition("=")
        name = name.strip()
        mode = mode_text.strip().lower()
        if name not in INJECTION_SPECS:
            raise InjectionFlagError(f"--inject: unknown injection {name!r}. Known: {sorted(INJECTION_SPECS)}.")
        if mode not in INJECTION_MODES:
            raise InjectionFlagError(
                f"--inject {name}: unknown mode {mode_text.strip()!r}. Valid modes: {sorted(INJECTION_MODES)}."
            )
        if name in overrides:
            raise InjectionFlagError(f"--inject: {name!r} given more than once.")
        overrides[name] = mode
    return overrides


def resolve_injection_modes(
    role: str,
    *,
    overrides: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> dict[str, str]:
    """Resolve every injection's effective mode for *role*, once.

    Precedence is ``--inject`` flag > config file > ``off``, matching
    ``_resolve_intent_guard_mode``'s override-then-config shape.

    Role gating is applied to overrides too: ``--inject coder_slice_ceremony=
    enforce`` on a planner stage still yields ``off``. The flag says what the
    operator wants enabled, not which roles it applies to -- that is the spec's
    business, so one flag cannot smuggle a payload into the wrong role.

    Every known injection gets an entry, including ones that are ``off`` here,
    so a consumer can ask about any injection by name without a membership
    check.
    """
    supplied = overrides or {}
    resolved: dict[str, str] = {}
    for name, spec in INJECTION_SPECS.items():
        if role not in spec.roles:
            resolved[name] = MODE_OFF
            continue
        override = supplied.get(name)
        resolved[name] = (
            normalize_mode(override) if override is not None else resolve_mode(spec, role, config_path=config_path)
        )
    return resolved


def mode_for(modes: InjectionModes | None, name: str) -> str:
    """Read one injection's mode from a resolver mapping, safely.

    Returns :data:`MODE_OFF` when the mapping is absent, the injection is not
    present, or the resolver raises. This is the function call sites should use
    -- it is the single place the "absence means off" rule is enforced, so no
    consumer has to remember it.
    """
    if not modes:
        return MODE_OFF
    return normalize_mode(modes.get(name))


def is_active(modes: InjectionModes | None, name: str) -> bool:
    """True when the injection should actually alter the request payload."""
    return mode_for(modes, name) == MODE_ENFORCE


def is_observed(modes: InjectionModes | None, name: str) -> bool:
    """True when the injection should emit telemetry (``observe`` or ``enforce``)."""
    return mode_for(modes, name) in (MODE_OBSERVE, MODE_ENFORCE)


__all__ = [
    "CODER_SLICE_CEREMONY",
    "FALLBACK_MODE",
    "INJECTION_MODES",
    "INJECTION_SPECS",
    "MODE_ENFORCE",
    "MODE_OBSERVE",
    "MODE_OFF",
    "InjectionFlagError",
    "InjectionModes",
    "InjectionSpec",
    "is_active",
    "is_observed",
    "mode_for",
    "normalize_mode",
    "parse_inject_overrides",
    "resolve_injection_modes",
    "resolve_mode",
]
