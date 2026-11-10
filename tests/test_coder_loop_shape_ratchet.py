"""S13.12 — the driver's *shape* ratchet: nesting and implicit coupling.

Plan: ``worklogs/planning-topology-and-executable-contracts-loop/notes/
remaining-work-c901-and-repairs-2026-11-10.md``

**What this module protects.** ``_drive_session_inner`` reached 1097 lines and
C901 68 through *Divergent Change* — one function that changes for six
unrelated reasons (skills ceremony, scope expansion, budget, provider, tools,
summary). Line count is the symptom; the two causes are:

* **``Hidden Temporal Coupling``** — 190 names in one scope, 5 nested functions
  closing over 27 of them, two of which mutate enclosing state through
  ``nonlocal``. Nothing inside can be tested or moved without rewriting an exit.
* **nesting** — control flow reaches **7 levels deep**, so no single branch can
  be read without holding six conditions in mind.

Neither is fixed by moving lines into another file: a helper that takes twelve
parameters and returns a tuple has the same coupling, one call frame further
away. So the ratchet measures the properties that actually have to fall.

**Why a ratchet and not a target.** The end state (see the plan) is ~300-350
lines: setup, one ``while``, five phase calls, and the decisions about exit.
Getting there is six slices. A test asserting the end state would be red for
the duration and would be deleted by whoever gets tired of it — the failure
mode ``test_s10b_complexity_ratchet`` was written to prevent. So, like that
file: **these numbers may only go down**, and they go down in the same commit
that earns it.

**Why the dependencies, not the line count, is the primary metric.** A
function can be 400 lines and obvious. What makes this one hard to enter is
that ``finish`` mangles enclosing state through ``nonlocal`` and that
``_compose_request_payload`` reads nine driver locals. Those are measurable and
they are the thing that must reach zero before the exits can move.

Test class: **C1** (static-shape contract).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODER_LOOP = REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py"

DRIVER = "_drive_session_inner"

# ---------------------------------------------------------------------------
# The ratchet. Each entry may ONLY decrease.
#
# Lower a number in the same commit that earns it, and say in the commit
# message which slice moved it. Raising one is not a formatting decision: it
# means the driver got worse, and that is a design discussion.
# ---------------------------------------------------------------------------

#: Deepest chain of nested control-flow statements (if/try/for/while/with).
#: Measured at 7 when this file was added. Target: 2 — every phase call flat.
MAX_NESTING_DEPTH = 7

#: Functions defined inside the driver. Each is a closure over driver state;
#: target 1, because only the composer genuinely needs per-turn bindings.
MAX_NESTED_FUNCTIONS = 5

#: `nonlocal` statements inside the driver's nested functions. This is the
#: load-bearing number: a `nonlocal` write means a nested function mutates
#: state the loop owns, which is exactly what makes the exits unmovable.
#:
#: 2 -> 0 in the `UsageLedger` slice (2026-11-10): `usage_turns` and
#: `summary_written` became fields of a named object, so `record_usage` and
#: `finish` take it as an argument instead of capturing it. Zero is the target
#: and there is no reason to move it back up: a new `nonlocal` is a new
#: unnamed object.
MAX_NONLOCAL_WRITES = 0

#: Deepest nesting inside any nested function (the bodies must stay readable
#: too — extracting into an already-unreadable closure moves the problem).
MAX_NESTED_FUNCTION_DEPTH = 4

#: Driver-body lines. Not the primary metric (see module docstring), kept so a
#: slice cannot "fix" nesting by inlining a hundred more lines.
MAX_DRIVER_LINES = 836  # 848 -> 836 with the ledger slice


def _driver() -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Parse the driver, with a liveness check on the lookup itself."""
    tree = ast.parse(CODER_LOOP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == DRIVER:
            return node
    raise AssertionError(
        f"{DRIVER} not found in {CODER_LOOP}. Either it was renamed (update this "
        f"file) or the measurement below would be vacuous."
    )


#: The node under measurement is either a function or a module wrapping one
#: fixture. Both are "the container", not a control-flow level.
_CONTAINERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    """Deepest chain of control-flow statements below ``node``.

    Nested ``def`` bodies are NOT counted: they are separate units of
    readability and get their own budget. Counting them here would let a
    deeply nested closure hide inside a shallow-looking parent, which is the
    same vacuity the rest of this file guards against.

    The entry node's own body IS walked: the driver is a ``FunctionDef`` and
    its branches are what this file measures. Skipping function nodes outright
    (the first version of this helper did) makes every measurement return 0 —
    a ratchet that passes forever. The liveness test below is what caught it.
    """
    # A ``Module`` is the container a fixture is parsed into. Unwrap it, or the
    # single ``FunctionDef`` inside is skipped as "a nested function" and every
    # fixture measures 0 — a liveness oracle that cannot fail.
    if isinstance(node, ast.Module):
        bodies = [child for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert len(bodies) == 1, "a nesting fixture must contain exactly one function"
        node = bodies[0]

    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        step = 1 if isinstance(child, (ast.If, ast.Try, ast.For, ast.While, ast.With)) else 0
        best = max(best, _nesting_depth(child, depth + step))
    return best


def _nested_functions(driver: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Functions defined directly in the driver's body or nested in them."""
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append(child)
            walk(child)

    walk(driver)
    return found


def _nonlocal_writes(driver: ast.AST) -> list[tuple[str, int]]:
    """``(name, lineno)`` for every ``nonlocal`` inside the driver's closures."""
    return [
        (name, node.lineno)
        for fn in _nested_functions(driver)
        for node in ast.walk(fn)
        if isinstance(node, ast.Nonlocal)
        for name in node.names
    ]


# ---------------------------------------------------------------------------
# Liveness first: every measurement below must be able to find its subject.
# ---------------------------------------------------------------------------


def test_driver_is_found_and_is_still_the_long_function() -> None:
    """C0 liveness: a renamed driver must fail loudly, not measure nothing."""
    driver = _driver()

    assert driver.end_lineno is not None
    lines = driver.end_lineno - driver.lineno + 1
    # Not a ratchet — a sanity anchor. If the driver suddenly measures 40
    # lines, either it was split (great: retune the constants here) or the
    # parse picked up the wrong symbol.
    assert lines > 200, (
        f"{DRIVER} measured {lines} lines. If it really shrank this far, the "
        f"constants in this file need retuning deliberately; if it did not, the "
        f"lookup is broken."
    )


def test_nesting_measurement_sees_the_known_deep_branch() -> None:
    """C0 liveness: the depth metric must actually descend.

    Kills the failure mode where a bug in the walker returns 1 for everything,
    which would make the ratchet below pass forever.
    """
    fixture = ast.parse(
        "def f(x):\n"
        "    if x:\n"
        "        if x:\n"
        "            try:\n"
        "                pass\n"
        "            except Exception:\n"
        "                pass\n"
    )
    assert _nesting_depth(fixture) == 3


# ---------------------------------------------------------------------------
# The ratchet itself.
# ---------------------------------------------------------------------------


def test_driver_nesting_depth_does_not_grow() -> None:
    """C1: control flow in the driver may only get flatter.

    Kill-check target: wrap any existing two-level branch in another ``if`` ->
    this fails and reports the new depth.
    """
    driver = _driver()
    depth = _nesting_depth(driver)

    assert depth <= MAX_NESTING_DEPTH, (
        f"{DRIVER} nests control flow {depth} deep, budget {MAX_NESTING_DEPTH}. "
        "Flat is the point: a phase that needs a third level is a phase that "
        "wants to be a function taking its condition as an argument."
    )


def test_driver_nested_function_count_does_not_grow() -> None:
    """C1: a new closure is a new coupling; the count may only fall."""
    nested = _nested_functions(_driver())

    assert len(nested) <= MAX_NESTED_FUNCTIONS, (
        f"{DRIVER} defines {len(nested)} nested functions, budget "
        f"{MAX_NESTED_FUNCTIONS}: {[f.name for f in nested]}. Each one captures "
        "driver locals; prefer a module-level function that receives what it needs."
    )


def test_nonlocal_writes_in_driver_do_not_grow() -> None:
    """C1: the load-bearing metric — nested functions must not mutate loop state.

    Every ``nonlocal`` here is a hidden channel from a closure into the loop's
    state (`usage_turns`, `summary_written`). While they exist, the exits that
    read that state cannot move out of this function, which is what keeps the
    driver a single unreadable unit. Target: zero, by making the counters
    fields of an object the loop owns.

    Kill-check target: add a third `nonlocal` write -> this fails and names it.
    """
    writes = _nonlocal_writes(_driver())

    assert len(writes) <= MAX_NONLOCAL_WRITES, (
        f"{DRIVER} has {len(writes)} `nonlocal` writes, budget "
        f"{MAX_NONLOCAL_WRITES}: {writes}. A closure that writes enclosing state "
        "is an unnamed object; name it (a dataclass field touched by the loop) "
        "instead of adding another channel."
    )


def test_nested_function_bodies_stay_shallow() -> None:
    """C1: extracting into an unreadable closure would move the problem, not solve it."""
    nested = _nested_functions(_driver())
    worst = max((_nesting_depth(fn) for fn in nested), default=0)

    assert worst <= MAX_NESTED_FUNCTION_DEPTH, (
        f"a nested function in {DRIVER} nests {worst} deep, budget "
        f"{MAX_NESTED_FUNCTION_DEPTH}. The bodies inside the driver get the same "
        "shape budget as the driver itself."
    )


def test_driver_line_count_does_not_grow() -> None:
    """C1: the secondary metric, kept so nesting cannot be "fixed" by inlining."""
    driver = _driver()
    assert driver.end_lineno is not None
    lines = driver.end_lineno - driver.lineno + 1

    assert lines <= MAX_DRIVER_LINES, (
        f"{DRIVER} is {lines} lines, budget {MAX_DRIVER_LINES}. A slice that "
        "flattens the body by inlining more code has not decomposed anything."
    )
