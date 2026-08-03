#!/usr/bin/env python3
"""LogKind Contract Check for FA observability.

Verifies that:
1. Every kind= value in log.append() calls is a member of LogKind
2. Every CONSOLE_MIRROR_KINDS member has BOTH a log.append producer
   AND an output.emit producer in the same code path
3. All LogKind members have at least one log.append producer in src/fa/

Run as: python scripts/check_log_kind_contract.py
Exit 1 if any gaps found. Exit 0 if all contracts satisfied.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import override

# UTF-8 console: this script prints non-ASCII (checkmarks / box drawing) and
# crashed with UnicodeEncodeError on a Windows host whose console was cp1251 —
# while REPORTING SUCCESS. See scripts/_console.py for the full rationale.
if __package__ in (None, ""):  # invoked as a file, not as scripts.<name>
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

force_utf8_stdio()

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_FA = REPO_ROOT / "src" / "fa"


# ── 0. Deliberately-dormant kinds ──────────────────────────────────────
# A LogKind with no ``log.append`` producer is a contract gap by default and
# fails CHECK 2. An entry here is an explicit, reviewed exception and MUST
# carry a reason: silence is what let the dormancy list grow unread.
#
# Removing an entry whose producer still does not exist re-breaks the build —
# that is the point.
KNOWN_DORMANT_KINDS: dict[str, str] = {
    "service_unavailable": (
        "not a log kind in practice — the literal is a ProviderError.kind value "
        "(providers/base.py:140), a different namespace that happens to share the "
        "spelling. Candidate for removal from LogKind in a later slice."
    ),
    "timeout": ("same as service_unavailable: ProviderError.kind (providers/base.py:119), not a log.append kind."),
}


# ── 1. Extract LogKind literals from output.py ─────────────────────────


def extract_log_kinds() -> list[str]:
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text(encoding="utf-8")
    match = re.search(r"LogKind = Literal\[(.*?)\]", source, re.DOTALL)
    if not match:
        print("FAIL: Could not find LogKind definition in output.py")
        sys.exit(1)
    body = match.group(1)
    kinds = re.findall(r'"([a-z_0-9]+)"', body)
    seen = set()
    result = []
    for k in kinds:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


# ── 2. Extract CONSOLE_MIRROR_KINDS from output.py ────────────────────


def extract_console_mirror_kinds() -> set[str]:
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text(encoding="utf-8")
    # Find the CONSOLE_MIRROR_KINDS frozenset
    match = re.search(
        r"CONSOLE_MIRROR_KINDS.*?frozenset(?:\[[^\]]+\])?\(\s*\{(.*?)\}\s*\)",
        source,
        re.DOTALL,
    )
    if not match:
        print("FAIL: Could not find CONSOLE_MIRROR_KINDS in output.py")
        sys.exit(1)
    body = match.group(1)
    return set(re.findall(r'"([a-z_0-9]+)"', body))


# ── 3. Find all log.append(kind=...) calls in src/fa/ ──────────────────


def _literals_of(node: ast.AST) -> list[str]:
    """Return every string literal a `kind=` expression can evaluate to.

    Handles the shapes that actually occur in this codebase:
    ``"literal"``, ``a if c else b`` (recursively), and ``x or y``. Anything
    else yields no literals and is treated as *unresolvable* by the caller —
    reported as ``unknown``, never silently as absent (fail closed).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _literals_of(node.body) + _literals_of(node.orelse)
    if isinstance(node, ast.BoolOp):
        out: list[str] = []
        for value in node.values:
            out.extend(_literals_of(value))
        return out
    return []


class _AppendKindVisitor(ast.NodeVisitor):
    """Collect ``kind=`` values passed to ``*.append(...)`` calls.

    AST rather than regex (S3-F1 sub-finding: the regex checker printed PASS on
    source that no longer parsed). Single-assignment locals are resolved so a
    dynamic producer such as
    ``kind: LogKind = "a" if cond else "b"; log.append(kind=kind)``
    is recognised as a real producer instead of a dormant kind (S3-F4).
    """

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.found: dict[str, list[str]] = {}
        self.unresolved: list[str] = []
        self._locals: dict[str, list[str]] = {}

    def _record(self, kind: str, lineno: int, suffix: str = "") -> None:
        self.found.setdefault(kind, []).append(f"{self.rel_path}:{lineno}{suffix}")

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            literals = _literals_of(node.value)
            if literals:
                self._locals[node.target.id] = literals
        self.generic_visit(node)

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        literals = _literals_of(node.value)
        if literals:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._locals[target.id] = literals
        self.generic_visit(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        is_append = isinstance(func, ast.Attribute) and func.attr == "append"
        if is_append:
            for kw in node.keywords:
                if kw.arg != "kind":
                    continue
                literals = _literals_of(kw.value)
                if literals:
                    for kind in literals:
                        self._record(kind, node.lineno)
                elif isinstance(kw.value, ast.Name):
                    resolved = self._locals.get(kw.value.id)
                    if resolved:
                        for kind in resolved:
                            self._record(kind, node.lineno, " (dynamic)")
                    else:
                        self.unresolved.append(f"{self.rel_path}:{node.lineno} kind={kw.value.id}")
                else:
                    self.unresolved.append(f"{self.rel_path}:{node.lineno} kind=<expr>")
        self.generic_visit(node)


def extract_log_append_kinds() -> tuple[dict[str, list[str]], list[str]]:
    """Return ``({kind: [file:line, ...]}, [unresolvable sites])``.

    A file that fails to parse is a hard error: the previous regex
    implementation happily reported PASS on unparseable source (S3 §5.1).
    """
    result: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for py_file in sorted(SRC_FA.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_path = str(py_file.relative_to(REPO_ROOT))
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            print(f"FAIL: {rel_path} does not parse: {exc}")
            sys.exit(1)
        visitor = _AppendKindVisitor(rel_path)
        visitor.visit(tree)
        for kind, sites in visitor.found.items():
            result.setdefault(kind, []).extend(sites)
        unresolved.extend(visitor.unresolved)
    return result, unresolved


# ── 4. Check CONSOLE_MIRROR_KINDS dual-write ──────────────────────────


def check_console_mirror_dual_write(console_mirror_kinds: set[str]) -> list[str]:
    """For each CONSOLE_MIRROR_KIND, check that output.emit exists somewhere
    in the producer files. This is a heuristic check — it doesn't verify exact
    code-path pairing, but catches the most common omission (no emit at all)."""
    gaps: list[str] = []

    # Map LogKind → EventType for dual-write check
    # Console mirror kinds use a specific OutputEvent type.
    # The mapping is documented in the output.emit() calls.
    kind_to_event_type: dict[str, str] = {
        "context_budget_warn": "context_warn",
        "context_budget_hard_stop": "context_warn",
        "compaction_warning": "compaction_warning",
        "config_warning": "config_warning",
        "compaction_stage2_start": "compaction_start",
        "compaction_stage2_done": "compaction_end",
        "compaction_stage2_error": "compaction_end",
        "compaction_stage3_start": "compaction_start",
        "compaction_stage3_done": "compaction_end",
        "compaction_stage3_error": "compaction_end",
        "compaction_circuit_breaker": "compaction_end",
        "tool_call": "tool_call",
        "subagent_spawn_done": "subagent_end",
        "subagent_spawn_fail": "subagent_end",
        "run_stopped": "session_end",
    }

    # Files that contain output.emit calls
    producer_files = [
        REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py",
        REPO_ROOT / "src" / "fa" / "inner_loop" / "tools" / "spawn_subagent.py",
        REPO_ROOT / "src" / "fa" / "cli.py",
        REPO_ROOT / "src" / "fa" / "inner_loop" / "state.py",
        REPO_ROOT / "src" / "fa" / "inner_loop" / "tools" / "spawn_subagent.py",
    ]

    # Build a set of all EventType strings that appear in output.emit calls
    emit_types_found: set[str] = set()
    for fpath in producer_files:
        if not fpath.exists():
            continue
        source = fpath.read_text(encoding="utf-8")
        # Match type="event_type" in OutputEvent constructor
        for m in re.finditer(r'type="([a-z_]+)"', source):
            # Verify it's in an OutputEvent/emit context
            ctx_start = max(0, m.start() - 200)
            ctx = source[ctx_start : m.end()]
            if "OutputEvent" in ctx or "emit" in ctx:
                emit_types_found.add(m.group(1))

    for kind in sorted(console_mirror_kinds):
        expected_type = kind_to_event_type.get(kind)
        if expected_type and expected_type in emit_types_found:
            continue
        # spawn_subagent centralizes its two event emissions through a typed
        # helper; prove the helper is typed and the expected event literal is
        # present rather than requiring a duplicated constructor at each call.
        spawn_source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "tools" / "spawn_subagent.py").read_text(
            encoding="utf-8"
        )
        if (
            kind in {"subagent_spawn_done", "subagent_spawn_fail"}
            and "def _emit_subagent_event" in spawn_source
            and "event_type: EventType" in spawn_source
            and f'"{expected_type}"' in spawn_source
        ):
            continue
        # If no mapping exists, that's a gap
        gaps.append(kind)

    return gaps


# ── Main ────────────────────────────────────────────────────────────────


def main() -> None:
    print("LOGKIND CONTRACT CHECK")
    print("=" * 72)

    log_kinds = extract_log_kinds()
    console_mirror_kinds = extract_console_mirror_kinds()
    append_kinds, unresolved_producers = extract_log_append_kinds()

    print(f"LogKind members: {len(log_kinds)}")
    print(f"CONSOLE_MIRROR_KINDS members: {len(console_mirror_kinds)}")
    print(f"log.append(kind=...) producers found: {len(append_kinds)} distinct kinds")
    print()

    failures = 0

    # CHECK 1: Every log.append kind is in LogKind
    print("CHECK 1: log.append(kind=...) uses valid LogKind member")
    print("-" * 72)
    unknown_kinds = set(append_kinds.keys()) - set(log_kinds)
    if unknown_kinds:
        for k in sorted(unknown_kinds):
            sites = append_kinds[k]
            print(f"  ❌ {k!r} NOT in LogKind — found at: {', '.join(sites[:3])}")
        failures += 1
    else:
        print("  ✅ All log.append kinds are valid LogKind members")

    # CHECK 2: Every LogKind member has at least one producer
    print()
    print("CHECK 2: Every LogKind member has a log.append producer")
    print("-" * 72)
    orphan_kinds = set(log_kinds) - set(append_kinds.keys())
    unexplained = sorted(orphan_kinds - set(KNOWN_DORMANT_KINDS))
    explained = sorted(orphan_kinds & set(KNOWN_DORMANT_KINDS))
    for k in explained:
        print(f"  💤 {k!r} — allowlisted: {KNOWN_DORMANT_KINDS[k]}")
    if unexplained:
        # S6.1: fail closed. Previously this printed and returned 0, so a kind
        # losing its last producer was reported and then ignored — the checker
        # could not fail, and S3 recorded that its PASS carried no information.
        for k in unexplained:
            print(f"  ❌ {k!r} — NO producer found and not in KNOWN_DORMANT_KINDS")
            print("     → add a producer, remove it from LogKind, or allowlist it with a reason")
        failures += 1
    elif not orphan_kinds:
        print("  ✅ All LogKind members have producers")
    else:
        print("  ✅ All LogKind members have producers or a reasoned allowlist entry")

    # CHECK 2b: no unresolvable dynamic producer
    print()
    print("CHECK 2b: every dynamic kind= resolves to literals")
    print("-" * 72)
    if unresolved_producers:
        # Fail closed: a producer the resolver cannot follow is UNKNOWN, not
        # absent. Classifying it as absent is how a live producer came to be
        # reported dormant (S3-F4); classifying it as present would hide a
        # genuine gap. Neither is safe, so it fails and asks for a human.
        for site in unresolved_producers:
            print(f"  ❌ {site} — kind= does not resolve to string literals (UNKNOWN, not absent)")
        print("     → assign the kind to a local with literal values, or extend _literals_of()")
        failures += 1
    else:
        print("  ✅ All dynamic kind= expressions resolve")

    # CHECK 3: CONSOLE_MIRROR_KINDS dual-write
    print()
    print("CHECK 3: CONSOLE_MIRROR_KINDS have dual-write (log + emit)")
    print("-" * 72)
    dual_write_gaps = check_console_mirror_dual_write(console_mirror_kinds)
    if dual_write_gaps:
        for k in sorted(dual_write_gaps):
            print(f"  ❌ {k!r} — in CONSOLE_MIRROR_KINDS but no output.emit found")
        failures += 1
    else:
        print("  ✅ All CONSOLE_MIRROR_KINDS have dual-write")

    # CHECK 4: CONSOLE_MIRROR_KINDS subset of LogKind
    print()
    print("CHECK 4: CONSOLE_MIRROR_KINDS ⊆ LogKind")
    print("-" * 72)
    not_in_logkind = console_mirror_kinds - set(log_kinds)
    if not_in_logkind:
        for k in sorted(not_in_logkind):
            print(f"  ❌ {k!r} — in CONSOLE_MIRROR_KINDS but NOT in LogKind")
        failures += 1
    else:
        print("  ✅ All CONSOLE_MIRROR_KINDS are valid LogKind members")

    # Summary
    print()
    print("=" * 72)
    if failures:
        print(f"FAIL: {failures} contract gap(s) found")
        sys.exit(1)
    else:
        print("PASS: All LogKind contracts satisfied")
        sys.exit(0)


if __name__ == "__main__":
    main()
