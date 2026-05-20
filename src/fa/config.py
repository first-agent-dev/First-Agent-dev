"""Capability-flag config parser for First-Agent.

Wave-1 R-21 (borrow-roadmap-2026-05.md §R-21 / ADR-6 §Amendment
2026-05-20). Five boolean flags, all default ``False``, opt-in
through ``~/.fa/config.yaml``. The flags gate runtime capability
classes that are naturally deny-by-default:

- ``ENABLE_DYNAMIC_TOOLS``           — loading new tools at runtime.
- ``REQUIRE_DYNAMIC_TOOL_SANDBOX``   — force §Policy sandbox check
                                        on first call of a
                                        dynamically-loaded tool.
- ``ENABLE_MCP_GATEWAY_MANAGEMENT``  — MCP gateway management
                                        surface (register / config /
                                        deregister upstream servers).
- ``ENABLE_DYNAMIC_MCP_SERVERS``     — spawn new MCP server
                                        subprocesses at runtime.
- ``ENABLE_SERVER_OPS``              — mutating remote-service API
                                        calls (deploy / restart /
                                        scale / ...).

Layer-1 (this file's `Capabilities`) is AND-ed at the dispatcher
with Layer-2 (ADR-6 §Amendment 2026-05-13 per-role
``allowed_tools`` whitelist) plus the §Policy path check. All
three must permit a call for it to run.

This module ships with a tiny YAML reader that recognises only
the subset of YAML this file's schema needs (top-level
``capabilities:`` map → ``KEY: bool`` lines). The full YAML
loader lands with R-1 HookRegistry runtime (BACKLOG M-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

from fa._yaml_subset import strip_inline_comment

DEFAULT_CONFIG_PATH: Path = Path.home() / ".fa" / "config.yaml"

# Five flag names, in the order they appear in
# ADR-6 §Amendment 2026-05-20 + Kronos `kronos/config.py:62-69`.
_FLAG_NAMES: tuple[str, ...] = (
    "ENABLE_DYNAMIC_TOOLS",
    "REQUIRE_DYNAMIC_TOOL_SANDBOX",
    "ENABLE_MCP_GATEWAY_MANAGEMENT",
    "ENABLE_DYNAMIC_MCP_SERVERS",
    "ENABLE_SERVER_OPS",
)

_TRUE_LITERALS: frozenset[str] = frozenset({"true", "yes", "on", "1"})
_FALSE_LITERALS: frozenset[str] = frozenset({"false", "no", "off", "0"})


@dataclass(frozen=True)
class Capabilities:
    """Frozen snapshot of the five capability flags.

    All fields default ``False`` so that omitting the
    ``capabilities:`` block in ``config.yaml`` (or the entire
    file) yields the same deny-by-default behaviour as an empty
    block. Construct via :func:`load_capabilities`; do not
    instantiate directly from un-validated user input.
    """

    ENABLE_DYNAMIC_TOOLS: bool = False
    REQUIRE_DYNAMIC_TOOL_SANDBOX: bool = False
    ENABLE_MCP_GATEWAY_MANAGEMENT: bool = False
    ENABLE_DYNAMIC_MCP_SERVERS: bool = False
    ENABLE_SERVER_OPS: bool = False

    def names(self) -> tuple[str, ...]:
        """Return the five flag names in canonical order."""
        return _FLAG_NAMES

    def as_dict(self) -> dict[str, bool]:
        """Return a fresh ``dict[str, bool]`` keyed by flag name."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class CapabilityWarning:
    """Non-fatal issue surfaced during parse.

    Unknown keys under ``capabilities:`` (typos) and non-boolean
    values are surfaced as warnings rather than raised, so a
    typo in one flag never disables the four other flags by
    aborting parse. Caller decides whether to log / fail.
    """

    line_no: int
    key: str
    detail: str


@dataclass(frozen=True)
class CapabilityLoadResult:
    """Parse output. ``capabilities`` is always populated.

    On a missing file or an empty / absent ``capabilities:``
    block, ``capabilities`` is the all-``False`` default and
    ``warnings`` is empty.
    """

    capabilities: Capabilities
    warnings: tuple[CapabilityWarning, ...] = field(default_factory=tuple)


def load_capabilities(text: str) -> CapabilityLoadResult:
    """Parse capability flags from a YAML config text.

    Recognises exactly the schema documented in
    ADR-6 §Amendment 2026-05-20:

    .. code-block:: yaml

        capabilities:
          ENABLE_DYNAMIC_TOOLS: false
          ENABLE_MCP_GATEWAY_MANAGEMENT: true
          # ... three other flag lines ...

    Lines outside the ``capabilities:`` block are ignored.
    Unknown keys inside the block surface as
    :class:`CapabilityWarning` entries. Missing flags inherit
    their dataclass default (``False``).

    Raises :class:`ValueError` only for unparseable YAML
    structure (e.g. a bare list under ``capabilities:``); the
    flag-level errors are warnings, never exceptions.
    """

    found: dict[str, bool] = {}
    warnings: list[CapabilityWarning] = []
    in_capabilities = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Top-level key resets the section context.
        if indent == 0:
            in_capabilities = stripped.startswith("capabilities:")
            continue

        if not in_capabilities:
            continue

        if stripped.startswith("- "):
            raise ValueError(
                f"capability flags must be a key-value map, not a list (line {line_no}): {line!r}"
            )

        if ":" not in stripped:
            warnings.append(
                CapabilityWarning(
                    line_no=line_no,
                    key=stripped,
                    detail="missing ':' separator",
                )
            )
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        # YAML inline comments (`true  # enable`) must not pollute the
        # value — see fa._yaml_subset.strip_inline_comment + Devin Review
        # finding 2026-05-20 on PR #19.
        value = strip_inline_comment(value).strip().lower()

        if key not in _FLAG_NAMES:
            warnings.append(
                CapabilityWarning(
                    line_no=line_no,
                    key=key,
                    detail="not a recognised capability flag",
                )
            )
            continue

        if value in _TRUE_LITERALS:
            found[key] = True
        elif value in _FALSE_LITERALS:
            found[key] = False
        else:
            warnings.append(
                CapabilityWarning(
                    line_no=line_no,
                    key=key,
                    detail=f"value {value!r} is not boolean; expected true/false/yes/no/on/off/0/1",
                )
            )

    caps = Capabilities(**found)
    return CapabilityLoadResult(capabilities=caps, warnings=tuple(warnings))


def load_capabilities_from_path(
    path: Path = DEFAULT_CONFIG_PATH,
) -> CapabilityLoadResult:
    """Read ``path`` and parse capability flags.

    Missing file yields the all-``False`` default (no warnings),
    matching the deny-by-default policy in
    ADR-6 §Amendment 2026-05-20. The caller is responsible for
    deciding whether to warn on missing-file vs absent-block.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CapabilityLoadResult(capabilities=Capabilities())

    return load_capabilities(text)


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "Capabilities",
    "CapabilityLoadResult",
    "CapabilityWarning",
    "load_capabilities",
    "load_capabilities_from_path",
]
