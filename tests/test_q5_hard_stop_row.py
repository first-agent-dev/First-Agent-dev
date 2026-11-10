"""Q#5 — one durable schema for `context_budget_hard_stop`.

The bug this pins: the circuit-breaker branch wrote the row by hand with four
keys, while both stage-3 sites wrote the verdict's nine. `fa stats` reads
`content["ratio"]` with a `0.0` default, so the heaviest exit in the system
reported **0% context** in the summary — though overflowing the context is
precisely what tripped the breaker.

Two things have to stay true, and they fail independently:

1. the numbers on the row come from the object that computed the thresholds
   (`hard_stop_row`), not from whatever locals the call site happens to hold;
2. every site that writes this kind goes through that builder, so a fourth site
   cannot reintroduce a hand-written payload.

(1) is behavioural, (2) is structural — a test that only checks the builder
would pass while the driver still wrote its own dict, which is exactly the
shape of the original defect.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from fa.inner_loop.state import EventLog
from fa.memory.context_budget import ContextBudget
from fa.stats import _parse_events
from tests.fixtures.budget_effects_probe import run_case

SRC = Path("src")

_REQUIRED_KEYS = {
    "action",
    "ratio",
    "message",
    "current_tokens",
    "limit_tokens",
    "threshold",
    "warning_threshold",
    "stage2_threshold",
    "stage3_threshold",
}


# ---------------------------------------------------------------------------
# Behaviour — the report has to describe the state the run died in
# ---------------------------------------------------------------------------


def test_circuit_breaker_row_reports_its_real_percentage(tmp_path: Path) -> None:
    """C1: the breaker's hard stop reports 94%, not the 0% from the default.

    Driven through the real loop, with seeded history — without it stage 3
    finds no `older_history` and the breaker branch is unreachable (measured;
    see the probe module).
    """
    case = run_case(95_000, threshold=80_000, run_id="q5-cb", breaker=True, tokens_after=94_000, seed_history=True)
    assert case["outcome"]["exit_code"] == 1
    assert case["outcome"]["stop_reason"] == "context_budget_hard_stop"

    rows = [r for r in case["rows"] if r["kind"] == "context_budget_hard_stop"]
    assert len(rows) == 1
    content: dict[str, Any] = dict(rows[0]["content"])
    assert set(content) == _REQUIRED_KEYS, f"hard-stop schema drifted: {sorted(content)}"
    assert content["ratio"] == 0.94
    assert content["current_tokens"] == 94_000

    # The breaker's own wording stays on the row — it is the message that
    # explains the exit, and `fa stats` prints this field.
    assert "circuit breaker" in str(content["message"]).lower()

    log = EventLog(tmp_path / "cb.jsonl", run_id="q5-cb")
    log.append(actor="runtime", kind="context_budget_hard_stop", content=content)
    analytics = _parse_events(tuple(log.read_all()), "q5-cb")
    assert analytics is not None
    assert len(analytics.context_budget_events) == 1
    assert round(analytics.context_budget_events[0].pct) == 94


def test_all_three_hard_stop_sites_report_the_same_schema() -> None:
    """C1: three different exits, one shape — and each percentage is its own.

    The three are the stage-3 stop without compaction (95%), the stage-3 stop
    after compaction (92%, the Q#4 post-compaction number) and the breaker
    (94%). Pinning them together is what makes "same schema" mean something:
    identical keys, different values.
    """
    cases = {
        "stage3_disabled": run_case(95_000, threshold=None, run_id="q5-s3-off"),
        "stage3_after_compaction": run_case(
            95_000, threshold=80_000, run_id="q5-s3-after", tokens_after=92_000, seed_history=True
        ),
        "circuit_breaker": run_case(
            95_000, threshold=80_000, run_id="q5-cb2", breaker=True, tokens_after=94_000, seed_history=True
        ),
    }
    seen: dict[str, float] = {}
    for label, case in cases.items():
        rows = [r for r in case["rows"] if r["kind"] == "context_budget_hard_stop"]
        assert len(rows) == 1, f"{label}: expected exactly one hard-stop row, got {len(rows)}"
        content = dict(rows[0]["content"])
        assert set(content) == _REQUIRED_KEYS, f"{label}: schema drift {sorted(content)}"
        seen[label] = float(content["ratio"])
    assert seen == {"stage3_disabled": 0.95, "stage3_after_compaction": 0.92, "circuit_breaker": 0.94}


# ---------------------------------------------------------------------------
# The builder — the numbers come from the budget, the words from the caller
# ---------------------------------------------------------------------------


def test_builder_keeps_decision_numbers_and_replaces_only_the_message() -> None:
    """C1 two-sided: `message` is the caller's, everything else is the budget's."""
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    decision = budget.check(94_000)
    row = budget.hard_stop_row(94_000, message="breaker says stop")

    assert row["message"] == "breaker says stop"
    assert {k: v for k, v in row.items() if k != "message"} == {k: v for k, v in decision.items() if k != "message"}


def test_builder_row_for_every_ladder_rung_still_carries_ratio() -> None:
    """C0 (negative): no usage value may produce a row without a usable ratio.

    The defect was a missing key, so the guard is a table over the ladder rather
    than a single example: allow, warn, stage2 and stage3 all have to yield the
    same key set, including at 0 tokens and at the limit.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    for tokens in (0, 70_000, 80_000, 90_000, 100_000, 250_000):
        row = budget.hard_stop_row(tokens, message="x")
        assert set(row) == _REQUIRED_KEYS
        assert row["ratio"] == tokens / 100_000
        assert row["current_tokens"] == tokens


# ---------------------------------------------------------------------------
# Structure — a fourth site cannot write its own payload again
# ---------------------------------------------------------------------------


def _hard_stop_appends() -> list[tuple[Path, ast.Call]]:
    found: list[tuple[Path, ast.Call]] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "append":
                continue
            kind = next(
                (kw.value.value for kw in node.keywords if kw.arg == "kind" and isinstance(kw.value, ast.Constant)),
                None,
            )
            if kind == "context_budget_hard_stop":
                found.append((path, node))
    return found


def test_every_hard_stop_row_is_built_by_the_budget() -> None:
    """C1 (structural): no hand-written `content` dict for this kind, anywhere.

    A behavioural test on the builder passes while the driver still writes its
    own four keys — that is exactly how Q#5 shipped. So the site list is checked
    at the AST level and floored at the three known exits, which keeps the check
    alive if one of them moves to another module during the compaction slice.
    """
    appends = _hard_stop_appends()
    assert len(appends) >= 3, f"expected at least 3 hard-stop sites, found {len(appends)}"
    for path, node in appends:
        content = next((kw.value for kw in node.keywords if kw.arg == "content"), None)
        assert isinstance(content, ast.Call), (
            f"{path}:{node.lineno} writes a literal hard-stop payload — "
            "use ContextBudget.hard_stop_row so every exit carries the same keys"
        )
        func = content.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        assert name == "hard_stop_row", f"{path}:{node.lineno} builds the row with {name!r}, not hard_stop_row"
        assert any(kw.arg == "message" for kw in content.keywords), (
            f"{path}:{node.lineno}: the exit's own wording must reach the row"
        )
