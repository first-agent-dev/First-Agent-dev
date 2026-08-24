"""S15 (CT-4): exploration metrics aggregator — acc@k / FUH / CtxEff.

Reads ``file_read`` rows from the session EventLog (append-only authority),
counts ``fs_search`` tool calls, and combines the transaction write-set to
compute context efficiency. Pure computation lives in
:func:`compute_metrics` so it is unit-testable without the ToolSpec layer;
the handler is a thin session-access shell.

Gold files are declared by the harness via
``SessionState.declare_gold_files`` (no CLI/tool producer in v1 — S15 plan
Q-S15-2 default). When gold is unset, acc@k / first_useful_hit are ``None``
and ``note`` explains how to enable them.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from fa.inner_loop.context import get_current_session
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.state import TraceEvent

logger = logging.getLogger(__name__)

_ACC_K_KEYS: tuple[str, ...] = ("1", "5", "10", "20")

_NO_GOLD_NOTE = "declare gold files via declare_gold_files for acc/fuh"


@dataclass(frozen=True)
class ExplorationMetrics:
    """Computed exploration metrics for the current session (CT-4)."""

    acc_at_k: dict[str, float | None]
    first_useful_hit: int | None
    ctx_efficiency: float
    n_reads: int
    n_searches: int
    gold_files: list[str] | None
    note: str


def compute_metrics(
    file_read_rows: Sequence[TraceEvent],
    search_count: int,
    write_set: set[str] | None,
    gold_files: set[str] | None,
) -> ExplorationMetrics:
    """Compute exploration metrics from telemetry rows (pure function).

    Formulas (CT-4, exact):
    - acc@k = |{g in gold : first_read_index(g) <= k}| / |gold|
      (first_read_index = 1-based position of the gold file's FIRST file_read
      row in event order; a gold file never read contributes 0 to the count)
    - first_useful_hit = min(batch_turn of file_read rows whose path is gold);
      None if no gold file was read
    - ctx_efficiency = sum(bytes_read of rows whose path is in write_set)
      / sum(bytes_read of ALL rows); 0.0 when no rows exist
    """
    reads = list(file_read_rows)
    n_reads = len(reads)
    effective_write_set = write_set if write_set is not None else set()
    gold = set(gold_files) if gold_files is not None else None

    total_bytes = 0
    write_bytes = 0
    first_index_of_gold: dict[str, int] = {}
    turns_of_gold: list[int] = []
    for idx, row in enumerate(reads, start=1):
        content = row.content
        path = str(content.get("path", ""))
        # Boundary narrowing: EventLog content is Mapping[str, object] — an
        # int/str value parses, anything else degrades to 0 rather than raising
        # (telemetry rows are best-effort mirror data; fail-degraded by design).
        raw_bytes = content.get("bytes_read", 0)
        nbytes = int(raw_bytes) if isinstance(raw_bytes, (int, str)) else 0
        raw_turn = content.get("turn", 0)
        turn = int(raw_turn) if isinstance(raw_turn, (int, str)) else 0
        total_bytes += nbytes
        if path in effective_write_set:
            write_bytes += nbytes
        if gold is not None and path in gold:
            first_index_of_gold.setdefault(path, idx)
            turns_of_gold.append(turn)

    ctx_efficiency = (write_bytes / total_bytes) if total_bytes > 0 else 0.0

    if gold is None:
        return ExplorationMetrics(
            acc_at_k=dict.fromkeys(_ACC_K_KEYS),
            first_useful_hit=None,
            ctx_efficiency=ctx_efficiency,
            n_reads=n_reads,
            n_searches=search_count,
            gold_files=None,
            note=_NO_GOLD_NOTE,
        )

    acc_at_k: dict[str, float | None] = {}
    for key in _ACC_K_KEYS:
        k = int(key)
        acc_at_k[key] = sum(1 for idx in first_index_of_gold.values() if idx <= k) / len(gold)
    first_useful_hit = min(turns_of_gold) if turns_of_gold else None
    return ExplorationMetrics(
        acc_at_k=acc_at_k,
        first_useful_hit=first_useful_hit,
        ctx_efficiency=ctx_efficiency,
        n_reads=n_reads,
        n_searches=search_count,
        gold_files=sorted(gold),
        note="",
    )


def build_fs_exploration_metrics_tool() -> ToolSpec:
    """Build the ``fs_exploration_metrics`` ToolSpec (session-scoped, read-mostly)."""

    def handler(params: Mapping[str, object]) -> ToolResult:
        session = get_current_session()
        if session is None:
            return ToolResult.fail(
                "no_session",
                "fs_exploration_metrics requires a running session",
                retryable=False,
            )
        reset = bool(params.get("reset", False))
        if reset:
            session.clear_gold_files()

        log = session.log
        if log is None:
            return ToolResult.fail(
                "no_log",
                "session log unavailable; metrics require an active EventLog",
                retryable=False,
            )
        try:
            rows = log.read_all()
        except Exception as exc:  # noqa: BLE001 - fail-degraded like fs_usage
            return ToolResult.fail("read_error", f"Failed to read EventLog: {exc}", retryable=False)

        file_read_rows = [row for row in rows if row.kind == "file_read"]
        search_count = sum(1 for row in rows if row.kind == "tool_call" and row.tool_name == "fs_search")
        write_set = set(session.write_set)
        gold = set(session.gold_files) if session.gold_files else None

        metrics = compute_metrics(file_read_rows, search_count, write_set, gold)
        return ToolResult.ok("exploration metrics computed", result=asdict(metrics))

    return ToolSpec(
        name="fs_exploration_metrics",
        description=(
            "Compute exploration metrics for the current session: acc@k "
            "(fraction of declared gold files among the first k reads), "
            "first_useful_hit (batch turn of the first gold-file read), "
            "ctx_efficiency (bytes read in files that appear in the write-set "
            "over total bytes read), n_reads, n_searches. reset=true clears "
            "declared gold files."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "reset": {"type": "boolean", "default": False},
            },
        },
        handler=handler,
        permission="workspace",  # NOT "read": reset mutates state — keep serialized
    )
