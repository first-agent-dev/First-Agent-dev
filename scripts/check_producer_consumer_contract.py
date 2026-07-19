#!/usr/bin/env python3
"""Producer-Consumer Contract Check for FA observability.

Verifies that every EventType literal has BOTH a producer (emit call in
production code) AND a consumer (handler in ConsoleRenderer). Reports gaps
as FAIL with actionable messages.

This is the structural fix for the "not wired / partial implementation"
bug class documented in:
  knowledge/research/root-cause-analysis-not-wired-gaps-2026-07-19.md

Run as: python scripts/check_producer_consumer_contract.py
Exit 1 if any gaps found. Exit 0 if all contracts satisfied.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── 1. Extract EventType literals from output.py ─────────────────────────

def extract_event_types() -> list[str]:
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text()
    # Parse the Literal[...] type annotation
    match = re.search(r'EventType = Literal\[(.*?)\]', source, re.DOTALL)
    if not match:
        print("FAIL: Could not find EventType definition in output.py")
        sys.exit(1)
    body = match.group(1)
    types = re.findall(r'"([a-z_]+)"', body)
    # Deduplicate preserving order
    seen = set()
    result = []
    for t in types:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── 2. Check ConsoleRenderer handlers (consumers) ───────────────────────

def extract_handler_events() -> set[str]:
    source = (REPO_ROOT / "src" / "fa" / "output.py").read_text()
    # Match def _handle_<event_type>(self, e: OutputEvent)
    return set(re.findall(r'def _handle_([a-z_]+)\(', source))


# ── 3. Check output.emit() calls in production code (producers) ─────────

PRODUCER_FILES = [
    "src/fa/inner_loop/coder_loop.py",
    "src/fa/inner_loop/tools/spawn_subagent.py",
    "src/fa/cli.py",
    "src/fa/observability/cost_guardian.py",
]

def extract_producer_events() -> dict[str, list[str]]:
    """Return {event_type: [file.py, ...]} for each emit call found."""
    result: dict[str, list[str]] = {}
    for fpath in PRODUCER_FILES:
        full = REPO_ROOT / fpath
        if not full.exists():
            continue
        source = full.read_text()
        for match in re.finditer(r'type="([a-z_]+)"', source):
            et = match.group(1)
            # Only count if it's inside an OutputEvent() or output.emit() context
            # Check surrounding 200 chars for OutputEvent or emit
            start = max(0, match.start() - 200)
            context = source[start:match.end()]
            if 'OutputEvent' in context or 'emit' in context:
                result.setdefault(et, []).append(fpath.split("/")[-1])
    return result


# ── 4. Check C1 test coverage (tests that exercise the producer) ───────

TEST_DIRS = [
    "tests/",
]

def extract_c1_tested_events() -> set[str]:
    """Find event types that have C1 tests (drive_session-based)."""
    tested = set()
    for test_dir in TEST_DIRS:
        test_path = REPO_ROOT / test_dir
        if not test_path.exists():
            continue
        for py_file in test_path.rglob("test_*.py"):
            source = py_file.read_text()
            # If the test file calls drive_session, any event type it
            # checks for is a C1-tested type
            if 'drive_session(' not in source:
                continue
            for match in re.finditer(r'type="([a-z_]+)"', source):
                tested.add(match.group(1))
            # Also check for event type assertions like e.type == "X"
            for match in re.finditer(r'\.type\s*==\s*"([a-z_]+)"', source):
                tested.add(match.group(1))
            # Check for e.type == "X" patterns
            for match in re.finditer(r'e\.type\s*==\s*"([a-z_]+)"', source):
                tested.add(match.group(1))
    return tested


# ── 5. Main check ──────────────────────────────────────────────────────

# EventTypes that are intentionally dormant (no producer expected)
DORMANT_TYPES = {
    "cost_alert",  # CostGuardian dormant by design
}

def main() -> int:
    event_types = extract_event_types()
    handlers = extract_handler_events()
    producers = extract_producer_events()
    c1_tested = extract_c1_tested_events()

    gaps_found = False

    print("PRODUCER-CONSUMER CONTRACT CHECK")
    print("=" * 72)
    print(f"EventType literals: {len(event_types)}")
    print(f"ConsoleRenderer handlers: {len(handlers)}")
    print(f"Producer emit() calls: {sum(len(v) for v in producers.values())} across {len(producers)} types")
    print(f"C1 tested: {len(c1_tested)} types")
    print()

    # Check 1: Consumer without producer
    print("CHECK 1: Handler exists but NO producer emit()")
    print("-" * 72)
    for et in sorted(event_types):
        has_handler = et in handlers
        has_producer = et in producers
        is_dormant = et in DORMANT_TYPES

        if has_handler and not has_producer:
            if is_dormant:
                print(f"  💤 {et:<22s} DORMANT (no producer expected)")
            else:
                print(f"  ❌ {et:<22s} CONSUMER ONLY — handler exists, NO emit() in production code")
                print(f"     → Add output.emit(OutputEvent(type=\"{et}\")) in the appropriate module")
                gaps_found = True

    if not any(et in handlers and et not in producers and et not in DORMANT_TYPES for et in event_types):
        print("  ✅ All non-dormant handlers have producers")

    print()

    # Check 2: Producer without consumer
    print("CHECK 2: Producer emit() exists but NO handler")
    print("-" * 72)
    for et in sorted(event_types):
        has_handler = et in handlers
        has_producer = et in producers
        if has_producer and not has_handler:
            print(f"  ❌ {et:<22s} PRODUCER ONLY — emit() exists, NO handler in ConsoleRenderer")
            gaps_found = True

    produced_but_no_handler = [et for et in event_types if et in producers and et not in handlers]
    if not produced_but_no_handler:
        print("  ✅ All producers have handlers")

    print()

    # Check 3: C1 test coverage
    print("CHECK 3: EventType with NO C1 producer test")
    print("-" * 72)
    c1_gaps = False
    for et in sorted(event_types):
        has_producer = et in producers
        has_c1 = et in c1_tested
        is_dormant = et in DORMANT_TYPES

        if has_producer and not has_c1 and not is_dormant:
            producer_files = ", ".join(producers.get(et, []))
            print(f"  ❌ {et:<22s} NO C1 test — producer in {producer_files}")
            print(f"     → Add a C1 test that exercises the production code path and asserts the emit")
            c1_gaps = True

    if not c1_gaps:
        print("  ✅ All non-dormant EventTypes with producers have C1 tests")

    print()

    # Summary
    print("=" * 72)
    if gaps_found or c1_gaps:
        if gaps_found:
            print("FAIL: Producer-consumer contract gaps found. See CHECK 1-2.")
        if c1_gaps:
            print("FAIL: C1 producer test gaps found. See CHECK 3.")
        return 1
    else:
        print("PASS: All non-dormant EventTypes have both producer and consumer.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
