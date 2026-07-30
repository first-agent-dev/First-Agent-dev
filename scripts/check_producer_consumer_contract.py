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
    match = re.search(r"EventType = Literal\[(.*?)\]", source, re.DOTALL)
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
    return set(re.findall(r"def _handle_([a-z_]+)\(", source))


# ── 2b. Per-site producer floor (S6-F2) ────────────────────────────────
# Counting only "does this type have >=1 producer" made site-level rot
# invisible: `api_retry` has four emit sites, and deleting one left the output
# byte-identical with exit 0 — three of four could disappear undetected.
#
# This is the expected number of emit sites per EventType. Fewer than the floor
# fails. MORE than the floor also fails, because an unrecorded new producer is
# a path nobody enumerated (skill §3.14 path inventory) — update the floor in
# the same commit that adds the emit.
PRODUCER_SITE_FLOOR: dict[str, int] = {
    "api_retry": 4,
    "compaction_end": 5,
    "compaction_start": 2,
    "compaction_warning": 1,
    "config_warning": 2,
    "context_warn": 5,
    # S6.2 raised this from 2 -> 3: drive_session now emits hook_deny when an
    # AFTER_TOOL_EXEC denial stops the outer loop (S6-F4).
    "hook_deny": 3,
    "llm_response": 1,
    "loop_warn": 3,
    "session_end": 1,
    "session_start": 1,
    "subagent_end": 1,
    "subagent_start": 1,
    "tool_call": 1,
    "turn_start": 1,
}


# ── 3. Check output.emit() calls in production code (producers) ─────────

PRODUCER_FILES = [
    "src/fa/inner_loop/coder_loop.py",
    "src/fa/inner_loop/tools/spawn_subagent.py",
    "src/fa/cli.py",
    "src/fa/observability/cost_guardian.py",
    "src/fa/inner_loop/state.py",
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
            context = source[start : match.end()]
            if "OutputEvent" in context or "emit" in context:
                result.setdefault(et, []).append(fpath.split("/")[-1])
        # Centralized typed EventBus helper: the literal is passed as a
        # parameter, so there is no direct type= string at the call sites.
        if fpath.endswith("spawn_subagent.py") and "def _emit_subagent_event" in source:
            if "event_type: EventType" in source:
                for et in ("subagent_start", "subagent_end"):
                    if f'"{et}"' in source:
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
            # Most product signals use drive_session as the composition root.
            # Bootstrap/config warnings are produced by SessionState before
            # drive_session exists, so their C1 root is the real SessionState
            # construction plus output-bus attachment.
            is_c1_root = "drive_session(" in source or "SessionState(" in source
            if not is_c1_root:
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

# ── Deliberately-dormant EventTypes ────────────────────────────────────
# An EventType with a handler and no producer is a contract gap by default
# (S3-F5: a renderer that looks wired and is dead). An entry here is an
# explicit, reviewed exception and MUST carry a reason.
#
# Shape deliberately mirrors ``KNOWN_DORMANT_KINDS`` in
# check_log_kind_contract.py so the two checkers agree on what an exemption
# looks like. Previously this was a bare ``set`` with an inline comment, which
# meant one unjustified line could silence a real gap — measured: adding a name
# with no reason took the checker from exit 1 to exit 0.
#
# An entry is a claim that "no producer is expected YET". When a producer
# lands, the claim is false and the entry must be removed — enforced below, so
# a stale exemption cannot keep the type exempt from the C1-coverage check.
DORMANT_TYPES: dict[str, str] = {
    "cost_alert": (
        "blocked on upstream, not abandoned: CostGuardian is registered on both "
        "production paths (cli.py:922, cli.py:2045), writes cost_observation audit "
        "rows and denies over budget, but emits no OutputEvent until the T-2 LLM "
        "driver lands the cost=… artifact (cli.py:918-921). Handler and guardian "
        "are both live; only the emit is missing. Q20 (2026-07-28): keep the type."
    ),
}


def _check_consumer_without_producer(
    event_types: list[str],
    handlers: set[str],
    producers: dict[str, list[str]],
) -> bool:
    """CHECK 1 — a handler with no producer is a dead renderer (S3-F5).

    Extracted from ``main`` to stay under the complexity budget once CHECK 4
    was added; the block is self-contained and answers one question.
    """
    print("CHECK 1: Handler exists but NO producer emit()")
    print("-" * 72)
    gaps = False
    for et in sorted(event_types):
        if et not in handlers or et in producers:
            continue
        if et in DORMANT_TYPES:
            print(f"  💤 {et:<22s} DORMANT (no producer expected)")
            continue
        print(f"  ❌ {et:<22s} CONSUMER ONLY — handler exists, NO emit() in production code")
        print(f'     → Add output.emit(OutputEvent(type="{et}")) in the appropriate module')
        gaps = True
    if not gaps:
        print("  ✅ All non-dormant handlers have producers")
    print()
    return gaps


def _check_dormant_allowlist(producers: dict[str, list[str]]) -> bool:
    """CHECK 4 — the allowlist itself must stay honest. True if gaps.

    Two ways an allowlist rots, both checked here:

    * an entry with no reason — a mute button rather than a decision;
    * an entry whose producer has since landed — a stale exemption that keeps
      the type out of the C1-coverage check forever.
    """
    print("CHECK 4: dormancy allowlist is justified and current")
    print("-" * 72)
    gaps = False
    for name, reason in sorted(DORMANT_TYPES.items()):
        if not reason.strip():
            print(f"  ❌ {name:<22s} allowlisted with NO reason")
            print("     → state why no producer is expected, or remove the entry")
            gaps = True
            continue
        if name in producers:
            sites = ", ".join(producers[name])
            print(f"  ❌ {name:<22s} STALE — allowlisted as dormant but now produced at {sites}")
            print("     → remove it from DORMANT_TYPES so it is held to the same checks as its peers")
            gaps = True
        else:
            print(f"  💤 {name:<22s} dormant: {reason[:60]}...")
    if not gaps:
        print("  ✅ Every dormancy entry is justified and still accurate")
    print()
    return gaps


def _check_producer_site_floor(producers: dict[str, list[str]]) -> bool:
    """CHECK 0 — compare emit-site counts to the recorded floor. True if gaps.

    Extracted from ``main`` to keep it under the complexity budget; the block
    is self-contained and has one output (did anything drift?).
    """
    print("CHECK 0: producer emit-site counts match the recorded floor")
    print("-" * 72)
    gaps = False
    for et in sorted(PRODUCER_SITE_FLOOR):
        expected = PRODUCER_SITE_FLOOR[et]
        actual = len(producers.get(et, []))
        if actual == expected:
            continue
        drift = "a producer was removed" if actual < expected else "new producer not in the inventory"
        print(f"  ❌ {et:<22s} {actual} emit site(s), expected {expected} — {drift}")
        if actual > expected:
            print("     → add the path to the inventory and raise PRODUCER_SITE_FLOOR in the same commit")
        gaps = True
    if not gaps:
        print("  ✅ All producer emit-site counts match")
    print()
    return gaps


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

    # Check 0: per-site producer floor (S6-F2)
    if _check_producer_site_floor(producers):
        gaps_found = True

    # Check 4: the dormancy allowlist itself (S6.4 / S6-CT4)
    if _check_dormant_allowlist(producers):
        gaps_found = True

    # Check 1: Consumer without producer
    if _check_consumer_without_producer(event_types, handlers, producers):
        gaps_found = True

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
            print("     → Add a C1 test that exercises the production code path and asserts the emit")
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
