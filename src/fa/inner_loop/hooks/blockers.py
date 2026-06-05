"""BlockerMiddleware (Wave-2 R-4): deterministic pre-tool blockers.

A small family of :class:`GuardMiddleware` subclasses that take three
classes of *predictable, content-pattern-detected* failures off the
LLM's plate so the model never reasons about them:

1. **RateLimitBlocker** — observes ``ToolResult.error.code`` /
   ``message`` for rate-limit signatures, then denies subsequent
   calls to the same tool within ``rate_limit_suppression_seconds``
   (30s, Aperant ``pause-handler.ts:30-80`` prod-tuned default).
2. **LockfileBlocker** — observes bash stderr / error message for
   lockfile contention signatures and denies for
   ``lockfile_suppression_seconds`` (5s; most apt/cargo/npm lock
   contention self-resolves within a few seconds).
3. **AuthExpiredBlocker** — observes auth-expired signatures and
   emits ``kind="hook_decision"`` audit rows. **Does not gate**
   in M-1 (``auth_expired_suppression_seconds = 0``) because
   synthetic-credential-injection lives with the T-2 LLM driver;
   gating without the LLM seeing the auth state would silently
   stall the run.

All three blockers share the same shape:

- Attach to ``BEFORE_TOOL_EXEC`` (gate) **and** ``AFTER_TOOL_EXEC``
  (observe). Observation never gates; gating reads the observation
  state recorded by earlier dispatches.
- The pattern-detection lives in subclass :meth:`_detect` — a pure
  function of the just-produced ``ToolResult``. Subclasses keep
  ``_detect`` deterministic so the test suite can assert by code.
- ``suppression_seconds == 0`` => observe-only (no gating, only
  the audit row); >0 => gate subsequent calls to the same
  ``tool_name`` until the window elapses.

The blockers are **dormant on baseline M-1 tools by error code** —
none of ``hook_deny`` / ``read_failed`` / ``write_failed`` /
``command_failed`` / ``command_timeout`` / ``invalid_params`` /
``internal_error`` matches the detectors' code sets, and the
:class:`LockfileBlocker` matches *only* contention-specific message
patterns (``could not get lock``, ``unable to create *.lock``,
``blocking waiting for file lock``, ``resource temporarily
unavailable``, ``another (instance|process) ... (lock|running)``)
rather than bare ``.lock`` substrings, so a baseline ``fs.run_bash``
error like ``No such file or directory: Cargo.lock`` does **not**
trigger gating. They activate when the LLM driver T-2 wires API /
browser / git tools that emit rate-limit / lockfile / auth error
codes natively. Landing them now keeps the family-disjoint ADR-7
§Amendment 2026-05-20 rule 3 contract honoured for future
LLM-using hooks without churning the registry shape.

References:
- ``knowledge/research/borrow-roadmap-2026-05.md`` §R-4 (377-389)
- Aperant ``pause-handler.ts`` 30s interval
- YT-4 ``login_handler`` auth-expired pattern
- Cline ``lockfile-detector.ts`` lockfile pattern
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from enum import StrEnum
from typing import override

from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.runtime_limits import (
    DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS,
    DEFAULT_LOCKFILE_SUPPRESSION_SECONDS,
    DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS,
)


class BlockerCategory(StrEnum):
    """Categories of pre-tool blockers (one per subclass).

    Used in deny reasons + audit rows so consumers can route on
    category rather than parsing free-text. New blocker subclasses
    extend this enum.
    """

    RATE_LIMIT = "rate_limit"
    LOCKFILE = "lockfile"
    AUTH_EXPIRED = "auth_expired"


TimeSource = Callable[[], float]


class BlockerMiddleware(GuardMiddleware):
    """Base class for deterministic pre-tool blockers (R-4).

    Subclasses override :meth:`_detect` to recognise the failure
    signature and (optionally) :attr:`category` /
    :attr:`suppression_seconds`. The base class wires the
    observe-on-AFTER + gate-on-BEFORE flow so every subclass is
    a ~10-line specialisation.

    Tests inject ``time_source`` to skip ``time.time()`` clock drift.
    """

    category: BlockerCategory = BlockerCategory.RATE_LIMIT
    suppression_seconds: float = 0.0
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC, LifecyclePoint.AFTER_TOOL_EXEC)
    # Each subclass overrides ``name`` to its category-tagged form; the
    # base class default keeps the registry happy for ad-hoc subclasses
    # in tests (e.g. a one-off ``_StubBlocker`` with overridden
    # ``_detect``).
    name = "blocker:base"

    def __init__(
        self,
        *,
        suppression_seconds: float | None = None,
        time_source: TimeSource | None = None,
    ) -> None:
        if suppression_seconds is not None:
            if suppression_seconds < 0:
                raise ValueError("suppression_seconds must be >= 0")
            self.suppression_seconds = float(suppression_seconds)
        self._time_source: TimeSource = time_source if time_source is not None else time.time
        # Last observed-at timestamp keyed by tool_name. The dict is
        # bounded by the number of distinct tools the blocker observes,
        # which is one or two for the baseline tool set; no eviction
        # needed at M-1 scale.
        self._observed_at: dict[str, float] = {}

    def _detect(self, result: ToolResult) -> bool:
        """Return ``True`` if the result matches the subclass signature.

        Subclasses MUST override. The base class raises so a forgotten
        override fails loudly rather than silently never blocking.
        """

        raise NotImplementedError

    def _observe(self, payload: HookPayload) -> None:
        """Record an observation if the result matches :meth:`_detect`."""

        if payload.tool_call is None or payload.tool_result is None:
            return
        if payload.tool_result.error is None:
            return
        if not self._detect(payload.tool_result):
            return
        self._observed_at[payload.tool_call.name] = self._time_source()

    def _gate(self, payload: HookPayload) -> Decision:
        """Deny if a recent observation matches the current tool name."""

        if self.suppression_seconds <= 0 or payload.tool_call is None:
            return Decision.allow()
        observed = self._observed_at.get(payload.tool_call.name)
        if observed is None:
            return Decision.allow()
        elapsed = self._time_source() - observed
        if elapsed >= self.suppression_seconds:
            return Decision.allow()
        remaining = self.suppression_seconds - elapsed
        return Decision.deny(
            f"{self.category.value} blocker active for {payload.tool_call.name}: "
            f"{remaining:.1f}s remaining in suppression window"
        )

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is LifecyclePoint.BEFORE_TOOL_EXEC:
            return self._gate(payload)
        if point is LifecyclePoint.AFTER_TOOL_EXEC:
            self._observe(payload)
            return Decision.allow()
        return Decision.allow()


# Pattern detectors. Compiled once at module load — recompiling on every
# detect call would be wasteful for the hot ``AFTER_TOOL_EXEC`` path.
_RATE_LIMIT_CODES: frozenset[str] = frozenset(
    {
        "rate_limited",
        "rate_limit",
        "http_429",
        "too_many_requests",
    }
)
_RATE_LIMIT_MESSAGE = re.compile(
    r"\b(rate[ _-]?limit(ed)?|too[ _-]?many[ _-]?requests|429)\b",
    re.IGNORECASE,
)
_LOCKFILE_MESSAGE = re.compile(
    # Match only *contention-specific* lockfile signatures so a baseline
    # ``fs.run_bash`` failure that merely mentions a ``.lock`` filename
    # (``No such file or directory: Cargo.lock``, ``Permission denied:
    # package-lock.json``, ``Cargo.lock not found``) does not falsely
    # trip the gate. Earlier versions of this regex included a bare
    # ``\.lock\b`` alternative — that matched any error message naming
    # a lock file rather than only contention. The five alternatives
    # below cover apt (``E: Could not get lock``), git
    # (``Unable to create '*.lock': File exists``), cargo
    # (``Blocking waiting for file lock on package cache``), generic
    # POSIX (``Resource temporarily unavailable``), and the npm /
    # cargo style ``another instance / process is already running``
    # message. Case-insensitive; word-boundary anchors keep partial
    # substrings inside larger English sentences matching.
    r"(could[ _-]?not[ _-]?(get|acquire)[ _-]?lock"
    r"|unable[ _-]?to[ _-]?create[ _\-\'\"\/A-Za-z0-9.]*?\.lock"
    r"|blocking[ _-]?waiting[ _-]?for[ _-]?file[ _-]?lock"
    r"|resource[ _-]?temporarily[ _-]?unavailable"
    r"|another[ _-]?(instance|process)[ \-A-Za-z0-9_\.\'\"]+(lock|running))",
    re.IGNORECASE,
)
_AUTH_EXPIRED_CODES: frozenset[str] = frozenset(
    {
        "auth_expired",
        "unauthorized",
        "http_401",
        "token_expired",
    }
)
_AUTH_EXPIRED_MESSAGE = re.compile(
    r"\b(401|unauthorized|authentication[ _-]?(required|expired)"
    r"|token[ _-]?(expired|invalid)|invalid[ _-]?credentials)\b",
    re.IGNORECASE,
)


class RateLimitBlocker(BlockerMiddleware):
    """Suppress repeat tool calls for ``rate_limit_suppression_seconds``.

    Detects rate-limit signatures via either ``error.code`` membership
    in :data:`_RATE_LIMIT_CODES` or a regex match on
    ``error.message``. Both paths are necessary because tool handlers
    in the wild attach the signature to either the code (structured
    HTTP-client wrappers) or the message (raw subprocess output).
    """

    category = BlockerCategory.RATE_LIMIT
    name = "blocker:rate_limit"
    # The base class uses this class attribute as the default when the
    # constructor's ``suppression_seconds`` is None, so no __init__ override
    # is needed (avoids useless-parent-delegation / W0246).
    suppression_seconds = DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS

    @override
    def _detect(self, result: ToolResult) -> bool:
        if result.error is None:
            return False
        if result.error.code in _RATE_LIMIT_CODES:
            return True
        return bool(_RATE_LIMIT_MESSAGE.search(result.error.message))


class LockfileBlocker(BlockerMiddleware):
    """Suppress repeat tool calls when a lockfile-contention pattern fires.

    Detects five contention-specific signatures via
    :data:`_LOCKFILE_MESSAGE`: apt (``Could not get lock``), git
    (``Unable to create *.lock``), cargo (``Blocking waiting for
    file lock``), generic POSIX (``Resource temporarily unavailable``),
    and npm / cargo (``another instance|process ... (lock|running)``).
    The error ``code`` channel is not used — current handler
    implementations never set a structured lockfile code, so message
    matching is the only signal available.

    The regex is intentionally *contention-tight*: a bare ``.lock``
    filename mention (``No such file or directory: Cargo.lock``,
    ``Permission denied: package-lock.json``) does **not** trip the
    gate. Future tools that emit a structured ``lockfile_busy``
    ``error.code`` should add it to a new ``_LOCKFILE_CODES`` set
    rather than relaxing the message regex.
    """

    category = BlockerCategory.LOCKFILE
    name = "blocker:lockfile"
    # Default supplied via class attribute; see RateLimitBlocker note (W0246).
    suppression_seconds = DEFAULT_LOCKFILE_SUPPRESSION_SECONDS

    @override
    def _detect(self, result: ToolResult) -> bool:
        if result.error is None:
            return False
        return bool(_LOCKFILE_MESSAGE.search(result.error.message))


class AuthExpiredBlocker(BlockerMiddleware):
    """Observe auth-expired signatures; **does not** gate in M-1.

    Default ``suppression_seconds == 0`` means the gate is inert —
    observations are recorded (for future audit projection) but
    ``BEFORE_TOOL_EXEC`` always returns allow. Synthetic re-auth
    via ``Decision.modify`` lands with the T-2 LLM driver; gating
    here without that channel would block the LLM from ever seeing
    the auth state.

    Callers can opt into gating by passing
    ``suppression_seconds > 0`` (e.g. for tests or for tools where
    a re-auth handler is wired externally).
    """

    category = BlockerCategory.AUTH_EXPIRED
    name = "blocker:auth_expired"
    # Default supplied via class attribute; see RateLimitBlocker note (W0246).
    # 0 == inert gate (observe-only) per the class docstring.
    suppression_seconds = DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS

    @override
    def _detect(self, result: ToolResult) -> bool:
        if result.error is None:
            return False
        if result.error.code in _AUTH_EXPIRED_CODES:
            return True
        return bool(_AUTH_EXPIRED_MESSAGE.search(result.error.message))


__all__ = [
    "AuthExpiredBlocker",
    "BlockerCategory",
    "BlockerMiddleware",
    "LockfileBlocker",
    "RateLimitBlocker",
]
