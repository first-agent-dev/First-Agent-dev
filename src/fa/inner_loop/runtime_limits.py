"""Runtime caps loaded from ``~/.fa/config.yaml`` (ADR-7 \u00a7Amendment 2026-05-20).

Two caps live on the loop driver, not in hook code:

- ``max_iterations`` \u2014 hard cap on the deterministic loop (ADR-7 \u00a71
  step 8 + Amendment 2026-05-20 rule 2: default = 6 per R-30/YT-4
  empirical anchor).
- ``bash_timeout_seconds`` \u2014 wall-clock timeout for ``fs.run_bash``
  (anchored at 30s in v0.1; raise via config, never via a code constant).

Amendment 2026-05-20 rule 1 says \u00abevery retry loop reads its hard cap
from ``~/.fa/config.yaml`` \u2014 never from a constant in hook code\u00bb. The
M-1 substrate ships the canonical anchors as the documented fallback so
the smoke entrypoint runs cleanly out-of-the-box; the future ``fa run``
LLM driver (T-2) tightens this to \u00abrefuse to start on missing key\u00bb.
This is the **T-4 mini** loader \u2014 it parses exactly the
``runtime_limits:`` block; the full YAML loader lands with T-4 proper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fa._yaml_subset import strip_inline_comment
from fa.config import DEFAULT_CONFIG_PATH

# Anchors documented in ADR-7 \u00a7Amendment 2026-05-20 rule 2 (max_iterations=6)
# and the bash timeout that PR #24 introduced (30s). Both live here so any
# code that needs the documented default imports from one place \u2014 no
# magic constants in ``loop.py`` / ``run_bash.py``.
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_BASH_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class RuntimeLimits:
    """Loop-driver caps. Construct via :func:`load_runtime_limits`."""

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS

    @classmethod
    def anchored_defaults(cls) -> RuntimeLimits:
        """Return the canonical defaults from ADR-7 \u00a7Amendment 2026-05-20."""
        return cls(
            max_iterations=DEFAULT_MAX_ITERATIONS,
            bash_timeout_seconds=DEFAULT_BASH_TIMEOUT_SECONDS,
        )


@dataclass(frozen=True)
class RuntimeLimitsWarning:
    """Non-fatal issue surfaced during parse (mirror of CapabilityWarning)."""

    line_no: int
    key: str
    detail: str


@dataclass(frozen=True)
class RuntimeLimitsLoadResult:
    limits: RuntimeLimits
    warnings: tuple[RuntimeLimitsWarning, ...] = field(default_factory=tuple)


_KNOWN_KEYS: frozenset[str] = frozenset({"max_iterations", "bash_timeout_seconds"})


def load_runtime_limits(text: str) -> RuntimeLimitsLoadResult:
    """Parse a ``runtime_limits:`` block from a YAML config text.

    Recognises exactly:

    .. code-block:: yaml

        runtime_limits:
          max_iterations: 6
          bash_timeout_seconds: 30

    Lines outside the block are ignored. Unknown keys inside the block
    surface as :class:`RuntimeLimitsWarning` entries; missing keys
    inherit the documented anchors so the loop driver still starts.
    Negative or zero values surface as warnings and the anchor is kept.
    """

    found: dict[str, int] = {}
    warnings: list[RuntimeLimitsWarning] = []
    in_block = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0:
            in_block = stripped.rstrip(":") == "runtime_limits" and stripped.endswith(":")
            continue
        if not in_block:
            continue
        if ":" not in stripped:
            continue
        key_raw, _, rest = stripped.partition(":")
        key = key_raw.strip()
        value_str = strip_inline_comment(rest).strip()
        if key not in _KNOWN_KEYS:
            warnings.append(RuntimeLimitsWarning(line_no=line_no, key=key, detail="unknown key"))
            continue
        try:
            value = int(value_str)
        except ValueError:
            warnings.append(
                RuntimeLimitsWarning(
                    line_no=line_no,
                    key=key,
                    detail=f"non-integer value: {value_str!r}",
                )
            )
            continue
        if value <= 0:
            warnings.append(
                RuntimeLimitsWarning(
                    line_no=line_no,
                    key=key,
                    detail=f"value must be positive: {value}",
                )
            )
            continue
        found[key] = value

    limits = RuntimeLimits(
        max_iterations=found.get("max_iterations", DEFAULT_MAX_ITERATIONS),
        bash_timeout_seconds=found.get("bash_timeout_seconds", DEFAULT_BASH_TIMEOUT_SECONDS),
    )
    return RuntimeLimitsLoadResult(limits=limits, warnings=tuple(warnings))


def load_runtime_limits_from_path(
    path: Path = DEFAULT_CONFIG_PATH,
) -> RuntimeLimitsLoadResult:
    """Read ``runtime_limits:`` from ``path``; fall back to anchored defaults.

    Missing file = anchored defaults + empty warnings (the smoke
    entrypoint must run before the user creates ``~/.fa/config.yaml``).
    The stricter \u00abrefuse-to-start-on-missing-key\u00bb mode lands with the
    ``fa run`` driver in T-2.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return RuntimeLimitsLoadResult(limits=RuntimeLimits.anchored_defaults())
    return load_runtime_limits(text)


__all__ = [
    "DEFAULT_BASH_TIMEOUT_SECONDS",
    "DEFAULT_MAX_ITERATIONS",
    "RuntimeLimits",
    "RuntimeLimitsLoadResult",
    "RuntimeLimitsWarning",
    "load_runtime_limits",
    "load_runtime_limits_from_path",
]
