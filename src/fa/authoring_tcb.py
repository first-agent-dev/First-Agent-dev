"""Level-0 authoring-guardrail kernel (ADR-11, two-tier TCB).

This module is the **Trusted Computing Base** for authoring-time
admission control. It is **frozen** and **stdlib-only** by contract
(ADR-11-I1): it MUST NOT import any third-party package, make network
calls, load plugins dynamically, evaluate LLM output, or use regular
expressions for structural analysis. Its public contract is frozen in
[`knowledge/adr/ADR-11-authoring-guardrails.md`](../../knowledge/adr/ADR-11-authoring-guardrails.md)
§Decision (§9.6 Level-0 detailed contract, §9.7 deterministic output,
§9.8 fail-closed behaviour).

Responsibilities (ADR-11-I1; blueprint §9.6):

1. Parse a single ``--manifest <path>`` TOML file via stdlib
   :mod:`tomllib`, validating its shape (keys, types, required fields).
2. Enumerate repository paths in sorted order (deterministic).
3. Compute three SHA-256 binders — ``snapshot_id`` (sorted path+hash
   pairs), ``kernel_hash`` (this module's source), ``rule_pack_hash``
   (the Level-1 package source) — plus a nullable ``session_hash``
   when a manifest is supplied.
4. Dispatch an **allowlisted** static list of Level-1 rules (passed in
   by the caller — the kernel never discovers rules dynamically).
5. Collect, deterministically sort, and emit diagnostics as JSON or
   text, exiting ``0`` unless any ``HARD-BLOCK`` is present.

Behaviour is **fail-closed**: a malformed manifest, an unknown key, a
wrong type, a missing required field, an empty snapshot, or a rule that
raises each yields a ``HARD-BLOCK`` diagnostic and a non-zero exit.

Level 1 rule packs live in :mod:`fa.authoring_rules`; for v0.1 (PR 1)
the allowlist is empty, so a clean tree produces empty diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

KERNEL_VERSION = "0.1"

# Directory names never enumerated for the snapshot: caches, VCS
# metadata, and virtualenvs are not authored content and would make
# ``snapshot_id`` non-deterministic across environments.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        ".idea",
        ".vscode",
    }
)

# Frozen manifest schema (PR 1). The session seam is carried but not yet
# *enforced* — the staged-paths-subset-of-seam rule is Level-1 ``seam.py``
# (PR 4). Unknown tables/keys are rejected (fail-closed) so the schema
# cannot drift silently.
_MANIFEST_TABLES = frozenset({"kernel", "session"})
_KERNEL_KEYS = frozenset({"version"})
_SESSION_KEYS = frozenset({"id", "seam"})


class Severity(IntEnum):
    """Diagnostic severity, ordered by sort rank (ADR-11-I2; §9.7).

    The integer value is the deterministic sort rank (HARD-BLOCK sorts
    before ADVISORY before INFO). :attr:`label` is the wire form used in
    JSON/text output and in the frozen public contract.
    """

    HARD_BLOCK = 0
    ADVISORY = 1
    INFO = 2

    @property
    def label(self) -> str:
        """Return the contract wire label (e.g. ``"HARD-BLOCK"``)."""
        return _SEVERITY_LABELS[self]

    @classmethod
    def from_label(cls, label: str) -> Severity:
        """Resolve a wire label back to a :class:`Severity` member."""
        try:
            return _SEVERITY_BY_LABEL[label]
        except KeyError:
            raise ValueError(f"unknown severity label: {label!r}") from None


_SEVERITY_LABELS: Mapping[Severity, str] = {
    Severity.HARD_BLOCK: "HARD-BLOCK",
    Severity.ADVISORY: "ADVISORY",
    Severity.INFO: "INFO",
}
_SEVERITY_BY_LABEL: Mapping[str, Severity] = {
    label: severity for severity, label in _SEVERITY_LABELS.items()
}


@dataclass(frozen=True)
class RuleResult:
    """A single deterministic diagnostic (ADR-11-I2; blueprint §9.2/§9.7).

    ``rule_input_hash`` is computed by the emitting rule over the **exact
    bytes it consumed** (not the whole file), so two conforming kernels
    produce identical hashes for the same input. ``expires_on`` is
    required when ``severity is Severity.ADVISORY`` (an undated advisory
    is itself an advisory finding); the kernel does not mutate results,
    so rules are responsible for setting it.
    """

    severity: Severity
    code: str
    path: str
    message: str
    remediation: str
    rule_input_hash: str
    line: int | None = None
    column: int | None = None
    expires_on: str | None = None

    def sort_key(self) -> tuple[int, str, str, int, str]:
        """Return the deterministic sort key (§9.7 diagnostic sort order).

        Severity rank -> code -> path -> line -> message. ``line`` of
        ``None`` sorts before any concrete line.
        """
        return (
            int(self.severity),
            self.code,
            self.path,
            -1 if self.line is None else self.line,
            self.message,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serialisable wire form (§9.7)."""
        return {
            "severity": self.severity.label,
            "code": self.code,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "remediation": self.remediation,
            "expires_on": self.expires_on,
            "rule_input_hash": self.rule_input_hash,
        }


@dataclass(frozen=True)
class Manifest:
    """Parsed, validated ``.fa/session.toml`` (frozen v0.1 schema).

    ``raw_bytes`` is retained so the kernel can bind ``session_hash`` to
    the exact on-disk manifest content.
    """

    kernel_version: str
    session_id: str | None
    seam: tuple[str, ...]
    raw_bytes: bytes = field(repr=False)


@runtime_checkable
class Rule(Protocol):
    """Level-1 rule contract (ADR-11-I1: rules never own dispatch/hash/output).

    A rule is any callable that inspects the repository and returns a
    sequence of :class:`RuleResult`. It receives an immutable
    :class:`RuleContext` and MUST be deterministic and side-effect free.
    Rules are dispatched only from a static allowlist
    (:data:`fa.authoring_rules.RULE_ALLOWLIST`); the kernel never
    discovers them dynamically.
    """

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]: ...


@dataclass(frozen=True)
class RuleContext:
    """Immutable input handed to every dispatched Level-1 rule.

    ``files`` is the sorted snapshot of repo-relative POSIX paths the
    kernel enumerated, so rules share one deterministic file view rather
    than each re-walking the tree.
    """

    repo_root: Path
    files: tuple[str, ...]
    manifest: Manifest | None


@dataclass(frozen=True)
class KernelReport:
    """The kernel's full deterministic verdict (§9.7 output contract)."""

    kernel_version: str
    kernel_hash: str
    snapshot_id: str
    rule_pack_hash: str
    session_hash: str | None
    diagnostics: tuple[RuleResult, ...]

    @property
    def exit_code(self) -> int:
        """Return ``1`` if any diagnostic is HARD-BLOCK, else ``0``."""
        return 1 if any(d.severity is Severity.HARD_BLOCK for d in self.diagnostics) else 0

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-serialisable wire form (§9.7)."""
        return {
            "kernel_version": self.kernel_version,
            "kernel_hash": self.kernel_hash,
            "snapshot_id": self.snapshot_id,
            "rule_pack_hash": self.rule_pack_hash,
            "session_hash": self.session_hash,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "exit_code": self.exit_code,
        }


# --- hashing helpers -------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return _sha256_hex(path.read_bytes())


def _hash_directory_sources(directory: Path) -> str:
    """SHA-256 over the sorted ``*.py`` sources beneath ``directory``.

    Used for ``rule_pack_hash``: the binder changes whenever any Level-1
    module's bytes change, independent of which rules a caller dispatches.
    """
    digest = hashlib.sha256()
    for source in sorted(directory.rglob("*.py")):
        rel = source.relative_to(directory).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


# --- path enumeration ------------------------------------------------------


def enumerate_paths(repo_root: Path) -> tuple[str, ...]:
    """Return repo-relative POSIX paths in deterministic sorted order.

    Cache / VCS / virtualenv directories (:data:`_SKIP_DIRS`) are pruned.
    Sorting is by the POSIX string so ordering is stable across
    filesystems.
    """
    paths: list[str] = []
    for child in _walk_files(repo_root):
        paths.append(child.relative_to(repo_root).as_posix())
    return tuple(sorted(paths))


def _walk_files(repo_root: Path) -> Iterator[Path]:
    stack: list[Path] = [repo_root]
    while stack:
        current = stack.pop()
        for entry in current.iterdir():
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                yield entry


def _compute_snapshot_id(repo_root: Path, files: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for rel in files:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_hash_file(repo_root / rel).encode("ascii"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


# --- manifest parsing (fail-closed) ----------------------------------------


class ManifestError(ValueError):
    """Raised on any manifest defect; carries a fail-closed diagnostic."""

    def __init__(self, diagnostic: RuleResult) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _manifest_diagnostic(path: Path, message: str, remediation: str) -> RuleResult:
    return RuleResult(
        severity=Severity.HARD_BLOCK,
        code="FA-AUTHORING-V0-MANIFEST",
        path=path.as_posix(),
        message=message,
        remediation=remediation,
        rule_input_hash=_sha256_hex(message.encode("utf-8")),
    )


def _require_table(data: Mapping[str, object], path: Path) -> None:
    unknown = sorted(set(data) - _MANIFEST_TABLES)
    if unknown:
        raise ManifestError(
            _manifest_diagnostic(
                path,
                f"unknown manifest table(s): {', '.join(unknown)}",
                f"remove the unknown table(s); allowed tables: {sorted(_MANIFEST_TABLES)}",
            )
        )
    if "kernel" not in data:
        raise ManifestError(
            _manifest_diagnostic(
                path,
                "missing required table [kernel]",
                "add a [kernel] table with version = \"0.1\"",
            )
        )


def _parse_kernel_table(data: Mapping[str, object], path: Path) -> str:
    kernel = data["kernel"]
    if not isinstance(kernel, dict):
        raise ManifestError(
            _manifest_diagnostic(path, "[kernel] must be a table", "make [kernel] a TOML table")
        )
    unknown = sorted(set(kernel) - _KERNEL_KEYS)
    if unknown:
        raise ManifestError(
            _manifest_diagnostic(
                path,
                f"unknown key(s) in [kernel]: {', '.join(unknown)}",
                f"remove the unknown key(s); allowed: {sorted(_KERNEL_KEYS)}",
            )
        )
    version = kernel.get("version")
    if not isinstance(version, str):
        raise ManifestError(
            _manifest_diagnostic(
                path, "kernel.version is required and must be a string", 'set version = "0.1"'
            )
        )
    if version != KERNEL_VERSION:
        raise ManifestError(
            _manifest_diagnostic(
                path,
                f"kernel.version {version!r} != supported {KERNEL_VERSION!r}",
                f'set version = "{KERNEL_VERSION}"',
            )
        )
    return version


def _parse_session_table(
    data: Mapping[str, object], path: Path
) -> tuple[str | None, tuple[str, ...]]:
    session = data.get("session")
    if session is None:
        return None, ()
    if not isinstance(session, dict):
        raise ManifestError(
            _manifest_diagnostic(path, "[session] must be a table", "make [session] a TOML table")
        )
    unknown = sorted(set(session) - _SESSION_KEYS)
    if unknown:
        raise ManifestError(
            _manifest_diagnostic(
                path,
                f"unknown key(s) in [session]: {', '.join(unknown)}",
                f"remove the unknown key(s); allowed: {sorted(_SESSION_KEYS)}",
            )
        )
    session_id = session.get("id")
    if session_id is not None and not isinstance(session_id, str):
        raise ManifestError(
            _manifest_diagnostic(path, "session.id must be a string", "set id to a string or omit")
        )
    seam = _parse_seam(session.get("seam"), path)
    return session_id, seam


def _parse_seam(value: object, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError(
            _manifest_diagnostic(
                path, "session.seam must be a list of strings", "set seam = [\"path\", ...] or omit"
            )
        )
    return tuple(value)


def parse_manifest(path: Path) -> Manifest:
    """Parse and validate a manifest, raising :class:`ManifestError` on any defect."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ManifestError(
            _manifest_diagnostic(
                path, f"manifest not readable: {exc}", "pass --manifest with a readable TOML path"
            )
        ) from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError(
            _manifest_diagnostic(path, f"manifest is not valid TOML: {exc}", "fix the TOML syntax")
        ) from exc
    _require_table(data, path)
    version = _parse_kernel_table(data, path)
    session_id, seam = _parse_session_table(data, path)
    return Manifest(kernel_version=version, session_id=session_id, seam=seam, raw_bytes=raw)


# --- kernel dispatch -------------------------------------------------------


def _empty_snapshot_diagnostic(repo_root: Path) -> RuleResult:
    return RuleResult(
        severity=Severity.HARD_BLOCK,
        code="FA-AUTHORING-V0-SNAPSHOT",
        path=repo_root.as_posix(),
        message="empty snapshot: no files enumerated under the repository root",
        remediation="run the kernel from a populated First-Agent workspace",
        rule_input_hash=_sha256_hex(b"empty-snapshot"),
    )


def _rule_crash_diagnostic(rule: Rule, exc: Exception) -> RuleResult:
    name = getattr(rule, "__name__", rule.__class__.__name__)
    message = f"rule {name!r} raised {type(exc).__name__}: {exc}"
    return RuleResult(
        severity=Severity.HARD_BLOCK,
        code="FA-AUTHORING-V0-RULE-CRASH",
        path="<kernel>",
        message=message,
        remediation="fix or remove the offending Level-1 rule from the allowlist",
        rule_input_hash=_sha256_hex(message.encode("utf-8")),
    )


def _dispatch_rules(rules: Iterable[Rule], context: RuleContext) -> list[RuleResult]:
    collected: list[RuleResult] = []
    for rule in rules:
        try:
            results = rule(context)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Fail-closed: any rule crash becomes a HARD-BLOCK diagnostic.
            collected.append(_rule_crash_diagnostic(rule, exc))
            continue
        collected.extend(results)
    return collected


def run_all(
    repo_root: Path,
    *,
    manifest_path: Path | None = None,
    rules: Sequence[Rule] = (),
) -> KernelReport:
    """Run the Level-0 kernel and return a deterministic :class:`KernelReport`.

    ``manifest_path`` is optional: when supplied it is parsed/validated and
    binds ``session_hash``; when omitted ``session_hash`` is ``None``.
    ``rules`` is the static allowlist the caller dispatches (empty for
    PR 1). Any fail-closed condition is surfaced as a HARD-BLOCK diagnostic
    rather than an exception, so callers always receive a serialisable
    report.
    """
    repo_root = repo_root.resolve()
    kernel_hash = _hash_file(Path(__file__))
    rule_pack_hash = _hash_directory_sources(Path(__file__).with_name("authoring_rules"))

    diagnostics: list[RuleResult] = []
    manifest: Manifest | None = None
    session_hash: str | None = None
    if manifest_path is not None:
        try:
            manifest = parse_manifest(manifest_path)
            session_hash = _sha256_hex(manifest.raw_bytes)
        except ManifestError as exc:
            diagnostics.append(exc.diagnostic)

    files = enumerate_paths(repo_root)
    if not files:
        diagnostics.append(_empty_snapshot_diagnostic(repo_root))
        snapshot_id = _sha256_hex(b"")
    else:
        snapshot_id = _compute_snapshot_id(repo_root, files)
        context = RuleContext(repo_root=repo_root, files=files, manifest=manifest)
        diagnostics.extend(_dispatch_rules(rules, context))

    ordered = tuple(sorted(diagnostics, key=RuleResult.sort_key))
    return KernelReport(
        kernel_version=KERNEL_VERSION,
        kernel_hash=kernel_hash,
        snapshot_id=snapshot_id,
        rule_pack_hash=rule_pack_hash,
        session_hash=session_hash,
        diagnostics=ordered,
    )


# --- rendering -------------------------------------------------------------


def render_json(report: KernelReport) -> str:
    """Render ``report`` as indented, key-stable JSON (§9.7)."""
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=False)


def render_text(report: KernelReport) -> str:
    """Render ``report`` as a compact human-readable summary."""
    lines = [
        f"kernel {report.kernel_version}  snapshot {report.snapshot_id}",
        f"kernel_hash {report.kernel_hash}",
        f"rule_pack_hash {report.rule_pack_hash}",
        f"session_hash {report.session_hash or 'null'}",
        f"diagnostics: {len(report.diagnostics)}  exit_code: {report.exit_code}",
    ]
    for diag in report.diagnostics:
        location = diag.path if diag.line is None else f"{diag.path}:{diag.line}"
        lines.append(f"- [{diag.severity.label}] {diag.code} {location} — {diag.message}")
    return "\n".join(lines)
