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

2.  **Hot-reloadable.** The mode is resolved by CALLING a resolver at the moment
    it is needed, not by reading a string once at process start. A running
    session therefore observes a ``~/.fa/config.yaml`` edit on its next turn --
    which is what a future WebUI toggle needs, since it will write config and
    expect a live agent to follow without a restart. The read is cached for
    :data:`_CACHE_TTL_SECONDS` so a per-turn resolve does not mean a per-turn
    stat+parse of the config file.

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
import threading
import time
from collections.abc import Callable, Mapping
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

#: How long a resolved config read is reused before re-reading from disk. Short
#: enough that a WebUI toggle feels immediate (a turn is seconds to minutes),
#: long enough that a multi-call turn does not re-parse the file each time.
_CACHE_TTL_SECONDS = 2.0


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

#: A zero-arg callable returning the mode for one injection, evaluated at the
#: moment the mode is needed. Threading a resolver rather than a string is what
#: makes hot reload possible: the value is not captured at dispatch time.
ModeResolver = Callable[[], str]

#: Mapping of injection name -> resolver, as carried through the stage boundary.
InjectionModes = Mapping[str, ModeResolver]


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


class _FlagCache:
    """TTL cache over the on-disk feature flags.

    Exists so that resolving N injection modes on every turn does not mean N
    config parses per turn, while still observing an external edit within
    :data:`_CACHE_TTL_SECONDS`. Guarded by a lock because a session may resolve
    from more than one thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: object | None = None
        self._expires_at = 0.0

    def get(self, path: Path | None) -> object | None:
        now = time.monotonic()
        with self._lock:
            if self._value is not None and now < self._expires_at:
                return self._value
        loaded = self._load(path)
        with self._lock:
            self._value = loaded
            self._expires_at = now + _CACHE_TTL_SECONDS
        return loaded

    def invalidate(self) -> None:
        """Drop the cached read. Used by tests and by an explicit reload."""
        with self._lock:
            self._value = None
            self._expires_at = 0.0

    @staticmethod
    def _load(path: Path | None) -> object | None:
        try:
            from fa.feature_flags import load_feature_flags_from_path

            if path is None:
                return load_feature_flags_from_path().flags
            return load_feature_flags_from_path(path).flags
        except Exception as exc:  # noqa: BLE001 - advisory; must never crash a run
            logger.warning("injection modes: config unreadable (%s); using %r", exc, FALLBACK_MODE)
            return None


_FLAG_CACHE = _FlagCache()


def reset_flag_cache() -> None:
    """Force the next resolve to re-read config. Test seam and reload hook."""
    _FLAG_CACHE.invalidate()


def resolve_mode(spec: InjectionSpec, role: str, *, config_path: Path | None = None) -> str:
    """Resolve one injection's effective mode for *role*, reading config now.

    Role gating is applied first and unconditionally: an injection never fires
    for a role outside its :attr:`InjectionSpec.roles`, whatever the config
    says. That keeps a future planner injection from firing in a coder session
    because of a single mistyped flag.
    """
    if role not in spec.roles:
        return MODE_OFF
    flags = _FLAG_CACHE.get(config_path)
    if flags is None:
        return FALLBACK_MODE
    try:
        raw = spec.read_flag(flags)
    except AttributeError as exc:  # spec points at a field that no longer exists
        logger.warning("injection %r: flag unreadable (%s); using %r", spec.name, exc, FALLBACK_MODE)
        return FALLBACK_MODE
    return normalize_mode(raw)


def build_injection_modes(role: str, *, config_path: Path | None = None) -> dict[str, ModeResolver]:
    """Build the resolver mapping handed to a session for *role*.

    Every known injection gets an entry, including ones that are ``off`` for
    this role, so a consumer can always ask about any injection by name without
    a membership check. The resolvers are lazy: constructing this mapping reads
    no config, and a session that never asks never pays.
    """
    return {
        name: (lambda s=spec: resolve_mode(s, role, config_path=config_path))  # type: ignore[misc]
        for name, spec in INJECTION_SPECS.items()
    }


def mode_for(modes: InjectionModes | None, name: str) -> str:
    """Read one injection's mode from a resolver mapping, safely.

    Returns :data:`MODE_OFF` when the mapping is absent, the injection is not
    present, or the resolver raises. This is the function call sites should use
    -- it is the single place the "absence means off" rule is enforced, so no
    consumer has to remember it.
    """
    if not modes:
        return MODE_OFF
    resolver = modes.get(name)
    if resolver is None:
        return MODE_OFF
    try:
        return normalize_mode(resolver())
    except Exception as exc:  # noqa: BLE001 - advisory; must never crash a run
        logger.warning("injection %r: resolver failed (%s); using %r", name, exc, MODE_OFF)
        return MODE_OFF


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
    "InjectionModes",
    "InjectionSpec",
    "ModeResolver",
    "build_injection_modes",
    "is_active",
    "is_observed",
    "mode_for",
    "normalize_mode",
    "reset_flag_cache",
    "resolve_mode",
]
