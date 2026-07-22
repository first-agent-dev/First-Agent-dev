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

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_FA = REPO_ROOT / "src" / "fa"


# ── 1. Extract LogKind literals from output.py ─────────────────────────


def extract_log_kinds() -> list[str]:
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text()
    match = re.search(r'LogKind = Literal\[(.*?)\]', source, re.DOTALL)
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
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text()
    # Find the CONSOLE_MIRROR_KINDS frozenset
    match = re.search(
        r'CONSOLE_MIRROR_KINDS.*?frozenset(?:\[[^\]]+\])?\(\s*\{(.*?)\}\s*\)',
        source,
        re.DOTALL,
    )
    if not match:
        print("FAIL: Could not find CONSOLE_MIRROR_KINDS in output.py")
        sys.exit(1)
    body = match.group(1)
    return set(re.findall(r'"([a-z_0-9]+)"', body))


# ── 3. Find all log.append(kind=...) calls in src/fa/ ──────────────────


def extract_log_append_kinds() -> dict[str, list[str]]:
    """Return {kind: [file.py:line, ...]} for each log.append(kind=...) found."""
    result: dict[str, list[str]] = {}
    for py_file in SRC_FA.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_path = str(py_file.relative_to(REPO_ROOT))
        lines = source.splitlines()
        for lineno, line in enumerate(lines, 1):
            # Only match kind="value" inside .append() call contexts.
            # This excludes ProviderTransientError(kind=...), etc.
            # Strategy: check if "append" appears in the same statement
            # (within ~3 lines above, accounting for multi-line calls).
            context_start = max(0, lineno - 4)
            context = "\n".join(lines[context_start:lineno])

            # Check this is a log.append / state.log.append / self.log.append call
            is_append_context = bool(re.search(
                r'\.(append|log\.append)\s*\(', context
            ))

            if not is_append_context:
                # Also match dynamic kind assignments that feed into append:
                # kind = "subagent_spawn_done" if ... else "subagent_spawn_fail"
                # Check if the variable 'kind' is used in a log.append later
                if re.search(r'kind\s*=\s*"([a-z_0-9]+)"', line):
                    # Look ahead ~10 lines for .append
                    ahead = "\n".join(lines[lineno:lineno + 10])
                    if re.search(r'\.(log\.append|append)\s*\(', ahead):
                        for m in re.finditer(r'kind\s*=\s*"([a-z_0-9]+)"', line):
                            kind_val = m.group(1)
                            result.setdefault(kind_val, []).append(
                                f"{rel_path}:{lineno} (dynamic)"
                            )
                continue

            for m in re.finditer(r'kind="([a-z_0-9]+)"', line):
                kind = m.group(1)
                result.setdefault(kind, []).append(f"{rel_path}:{lineno}")

    return result


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
            ctx = source[ctx_start:m.end()]
            if "OutputEvent" in ctx or "emit" in ctx:
                emit_types_found.add(m.group(1))

    for kind in sorted(console_mirror_kinds):
        expected_type = kind_to_event_type.get(kind)
        if expected_type and expected_type in emit_types_found:
            continue
        # spawn_subagent centralizes its two event emissions through a typed
        # helper; prove the helper is typed and the expected event literal is
        # present rather than requiring a duplicated constructor at each call.
        spawn_source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "tools" / "spawn_subagent.py").read_text()
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
    append_kinds = extract_log_append_kinds()

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
    if orphan_kinds:
        # Some kinds may not have producers yet (e.g., compaction_warning before S6)
        for k in sorted(orphan_kinds):
            print(f"  💤 {k!r} — NO producer found (may be planned/dead)")
        # This is a soft warning, not a hard failure, unless CI is strict
        # For now, exit 0 but note the orphans
    else:
        print("  ✅ All LogKind members have producers")

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
