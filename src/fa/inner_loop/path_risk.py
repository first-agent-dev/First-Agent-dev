"""Path-based risk tiers — pure policy core (S10.2).

The positional risk model (Q26): *where* the run reads and writes decides
the verification posture. Paths are classed into three tiers:

  * safe   (1) — work logs, archive, research notes: never escalate;
  * medium (3) — ``knowledge/``, ``tests/``, ``scripts/``: a write here is
    a verification-posture change, never a scope escalation; reading is
    silent;
  * high   (5) — ``src/`` and repo-root manifests: a read *arms* level 2,
    a write *escalates* to level 3.

Unknown prefixes default to **medium** (RK-J): failing safe means
"ask for more process" rather than "stay casual inside production code",
and it also means a novel docs tree does not force workflow.

This module is stdlib-only and has no session state; the caller passes the
read/write path sets and receives tier maxima. Tiers are configurable via
the ``scope_risk_tiers:`` config block; defaults are the documented anchors
and a config that fails to parse or is absent degrades to defaults plus a
structured warning — never a crash, never silence (failure-observable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import PurePosixPath

from fa.inner_loop.expansion import TIER_HIGH, TIER_MEDIUM, TIER_SAFE

__all__ = [
    "DEFAULT_HIGH_PREFIXES",
    "DEFAULT_MEDIUM_PREFIXES",
    "DEFAULT_SAFE_PREFIXES",
    "ROOT_MANIFEST_NAMES",
    "TIER_NO_EVIDENCE",
    "ScopeRiskConfig",
    "ScopeRiskLoadResult",
    "ScopeRiskWarning",
    "combine_tiers",
    "default_scope_risk_config",
    "load_scope_risk_tiers",
    "observed_tiers",
    "tier_for_path",
]

#: No observed path yet; distinct from tier values so callers can tell
#: "nothing happened" apart from "everything observed was safe".
TIER_NO_EVIDENCE: int = 0

#: Repo-root manifest files (packaging, CI, top-level config).
ROOT_MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "package-lock.json",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "Makefile",
        "justfile",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".github",
    }
)

DEFAULT_SAFE_PREFIXES: frozenset[str] = frozenset(
    {
        "worklogs/archive",
        "worklogs/research",
        "worklogs/reviews",
        "worklogs/pr-notes",
        "worklogs/implementation-plans",
    }
)
DEFAULT_MEDIUM_PREFIXES: frozenset[str] = frozenset({"knowledge", "tests", "scripts"})
DEFAULT_HIGH_PREFIXES: frozenset[str] = frozenset({"src"})

_TIER_NAMES: dict[int, str] = {TIER_SAFE: "safe", TIER_MEDIUM: "medium", TIER_HIGH: "high"}


@dataclass(frozen=True)
class ScopeRiskConfig:
    """Resolved prefix lists per tier. Built by :func:`load_scope_risk_tiers`."""

    safe_prefixes: frozenset[str] = DEFAULT_SAFE_PREFIXES
    medium_prefixes: frozenset[str] = DEFAULT_MEDIUM_PREFIXES
    high_prefixes: frozenset[str] = DEFAULT_HIGH_PREFIXES

    def _tier_prefixes(self) -> tuple[tuple[int, frozenset[str]], ...]:
        return (
            (TIER_SAFE, self.safe_prefixes),
            (TIER_MEDIUM, self.medium_prefixes),
            (TIER_HIGH, self.high_prefixes),
        )


@dataclass(frozen=True)
class ScopeRiskWarning:
    """Non-fatal config issue; caller logs without aborting."""

    line_no: int
    key: str
    detail: str


@dataclass(frozen=True)
class ScopeRiskLoadResult:
    """Parse output; ``config`` always populated (defaults on failure)."""

    config: ScopeRiskConfig
    warnings: tuple[ScopeRiskWarning, ...] = field(default_factory=tuple)


def default_scope_risk_config() -> ScopeRiskConfig:
    """The documented anchors (used absent a config block)."""
    return ScopeRiskConfig()


def _normalise_prefix(raw: str) -> str:
    """Normalise a configured prefix: posix separators, no leading ``./``."""
    p = str(PurePosixPath(raw.strip().replace("\\", "/")))
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _prefix_matches(path: str, prefix: str) -> bool:
    """Glob-aware, path-boundary-aware prefix match.

    ``*`` is a glob (``fnmatch``); a literal prefix matches only at a path
    boundary, so ``src`` matches ``src/a.py`` and ``src`` but never
    ``src-legacy/x.py``.
    """
    path = path.strip().replace("\\", "/").lstrip("./")
    if any(ch in prefix for ch in "*?["):
        # fnmatch is path-blind; anchor ``*`` to within one segment by
        # translating ``/**`` (whole subtree) and leaving single-segment
        # globs to fnmatch against the top segment(s).
        if prefix.endswith("/**"):
            base = prefix[:-3]
            return path == base or path.startswith(base + "/")
        return fnmatch(path, prefix)
    return path == prefix or path.startswith(prefix + "/")


def tier_for_path(path: str, config: ScopeRiskConfig) -> int:
    """Return the configured tier for one path.

    Highest tier wins when prefixes overlap (explicit safe entries cannot
    mask an explicit high one). Repo-root manifests and ``.github/`` CI
    files are always high regardless of config. Unknown prefix -> medium
    (RK-J).
    """
    posix = path.strip().replace("\\", "/")
    while posix.startswith("./"):
        posix = posix[2:]
    if posix in ROOT_MANIFEST_NAMES:
        return TIER_HIGH
    if posix.startswith(".github/"):
        return TIER_HIGH
    best = TIER_NO_EVIDENCE
    for level, prefixes in config._tier_prefixes():
        if any(_prefix_matches(posix, p) for p in prefixes):
            best = max(best, level)
    return best if best != TIER_NO_EVIDENCE else TIER_MEDIUM


def combine_tiers(lexical: int, path_based: int) -> int:
    """Combine a lexical-difficulty tier with a path tier: MAX wins.

    MAX is associative, commutative and idempotent; it also keeps the
    strongest signal — a lexically-easy task (1) touching ``src/`` (5)
    must end up high, not average down to 3.
    """
    return max(lexical, path_based)


def observed_tiers(
    read_paths: frozenset[str],
    write_paths: frozenset[str],
    config: ScopeRiskConfig,
) -> dict[str, int]:
    """Tier maxima over the transaction read/write sets.

    Returns ``{"read_max", "write_max"}``; an empty set maps to
    :data:`TIER_NO_EVIDENCE` (0) so "no writes this turn" never looks like
    a safe write. Root manifests and ``.github/`` score high inside
    :func:`tier_for_path` itself, for reads and writes alike.
    """
    read_max = TIER_NO_EVIDENCE
    for p in read_paths:
        read_max = max(read_max, tier_for_path(p, config))
    write_max = TIER_NO_EVIDENCE
    for p in write_paths:
        write_max = max(write_max, tier_for_path(p, config))
    return {"read_max": read_max, "write_max": write_max}


def load_scope_risk_tiers(text: str) -> ScopeRiskLoadResult:
    """Parse a ``scope_risk_tiers:`` block from YAML config text.

    Recognises prefix-list entries per tier, in either shape:

    .. code-block:: yaml

        scope_risk_tiers:
          safe:
            - docs/notes
          medium: [knowledge, tests, scripts]
          high:
            - src

    Lists are **additive** to the documented defaults (a config narrows
    policy risk by raising tiers, never by silently dropping the high
    default). Unknown tier names, bad glob-free values and non-list shapes
    surface as :class:`ScopeRiskWarning` entries; the defaults always
    produce a working config. Raises only when the block itself is a
    scalar (unparseable structure).
    """
    safe: set[str] = set(DEFAULT_SAFE_PREFIXES)
    medium: set[str] = set(DEFAULT_MEDIUM_PREFIXES)
    high: set[str] = set(DEFAULT_HIGH_PREFIXES)
    warnings: list[ScopeRiskWarning] = []

    in_block = False
    current_tier: int | None = None

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0:
            header, sep, rest = stripped.partition(":")
            in_block = sep == ":" and header.strip() == "scope_risk_tiers"
            current_tier = None
            if in_block and rest.split("#", 1)[0].strip():
                # ``scope_risk_tiers: <scalar>`` — unusable shape.
                return ScopeRiskLoadResult(
                    config=default_scope_risk_config(),
                    warnings=(
                        ScopeRiskWarning(
                            line_no=line_no,
                            key="scope_risk_tiers",
                            detail="block must be a mapping of tier lists; got scalar",
                        ),
                    ),
                )
            continue
        if not in_block:
            continue

        # Tier header:  ``safe:`` / ``safe: [a, b]`` / ``safe:`` + child list.
        if ":" in stripped and (not stripped.startswith("- ")):
            key_raw, _, rest = stripped.partition(":")
            key = key_raw.strip()
            rest = rest.split("#", 1)[0].strip()
            tier = _tier_level_for_name(key)
            if tier is None:
                warnings.append(
                    ScopeRiskWarning(line_no=line_no, key=key, detail="unknown tier; expected safe/medium/high")
                )
                current_tier = None
                continue
            current_tier = tier
            if rest:
                for item in _parse_inline_list(rest):
                    _add_prefix(tier, item, line_no, safe, medium, high, warnings)
            continue

        # Child list item:  ``- knowledge``  (indent deeper than header).
        item_text = stripped[2:].strip().split("#", 1)[0].strip() if stripped.startswith("- ") else stripped
        if current_tier is None or not item_text:
            continue
        _add_prefix(current_tier, item_text, line_no, safe, medium, high, warnings)

    return ScopeRiskLoadResult(
        config=ScopeRiskConfig(
            safe_prefixes=frozenset(safe),
            medium_prefixes=frozenset(medium),
            high_prefixes=frozenset(high),
        ),
        warnings=tuple(warnings),
    )


def _tier_level_for_name(name: str) -> int | None:
    for level, label in _TIER_NAMES.items():
        if label == name:
            return level
    return None


def _parse_inline_list(rest: str) -> list[str]:
    body = rest.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1]
    return [part.strip().strip("'\"") for part in body.split(",") if part.strip()]


def _add_prefix(
    tier: int,
    raw: str,
    line_no: int,
    safe: set[str],
    medium: set[str],
    high: set[str],
    warnings: list[ScopeRiskWarning],
) -> None:
    prefix = _normalise_prefix(raw.strip("'\""))
    if not prefix or prefix in {".", "/"}:
        warnings.append(
            ScopeRiskWarning(line_no=line_no, key=_TIER_NAMES[tier], detail=f"empty/root prefix ignored: {raw!r}")
        )
        return
    target = {TIER_SAFE: safe, TIER_MEDIUM: medium, TIER_HIGH: high}[tier]
    target.add(prefix)
