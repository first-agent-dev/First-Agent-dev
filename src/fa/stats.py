"""Session analytics — ``fa stats`` post-hoc analysis of events.jsonl.

Reads existing EventLog JSONL files (no changes to how events are written).
Pure consumer: parses ``TraceEvent`` rows from ``EventLog.read_all()``
and computes file access patterns, tool usage, token timelines, provider
health, guard activity, and efficiency warnings.

Data model uses typed dataclasses (foundation for WebUI JSON output).

References:
- ADR-7 §7 (event schema — kind values and content shapes)
- AGENTS.md §Cross-project anti-patterns rule 3: "Every write target
  must have an active consumer" — fa stats IS the consumer for EventLog.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TextIO

from fa.formatting import fmt_tokens as _fmt_tokens
from fa.inner_loop.state import EventLog
from fa.output import LogKind

__all__ = [
    "UNPARSED_KINDS",
    "BashCommand",
    "CircuitBreakerRecord",
    "CompactionRecord",
    "CompactionStartRecord",
    "CompactionWarningRecord",
    "ContextBudgetEvent",
    "FileAccess",
    "GuardActivity",
    "ProviderHealth",
    "SessionAnalytics",
    "SubagentRecord",
    "ToolError",
    "ToolUsage",
    "TurnTokens",
    "aggregate_sessions",
    "efficiency_warnings",
    "find_dead_zones",
    "parse_session",
    "render_aggregate",
    "render_session",
    "render_session_json",
]

# ── Unparsed kinds ──────────────────────────────────────────────────────────
# LogKinds that have no actionable analytics value for `fa stats`.
# These are either infrastructure signals (service_unavailable, timeout),
# low-value observability (audit, telemetry), or event types where the
# content is fully captured by other parsers (cost_observation → session_summary
# totals, recovery_action/verification → tool_result, subagent_spawn_start →
# subagent_spawn_done/fail). Listing them explicitly makes invisibility
# auditable — adding a new LogKind to output.py without a parser here
# will fail the contract check.
UNPARSED_KINDS: frozenset[LogKind] = frozenset(
    {
        "audit",  # low-value — rule evaluation audit trail
        "config_warning",  # operator-visible at runtime; no session analytics aggregate
        "cost_observation",  # redundant — session_summary has totals
        "recovery_action",  # captured by tool_result + provider_attempt
        "service_unavailable",  # infrastructure — no structured analytics
        "subagent_spawn_start",  # captured by subagent_spawn_done/fail
        "telemetry",  # low-value — per-tool audit noise
        "timeout",  # infrastructure — no structured analytics
        "verification",  # captured by tool_result
    }
)

# ── Data model ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TurnTokens:
    """Per-turn token breakdown."""

    turn: int
    in_tokens: int
    out_tokens: int
    cache_read: int
    cache_creation: int

    @property
    def cache_hit_ratio(self) -> float:
        return self.cache_read / max(self.in_tokens, 1)


@dataclass(frozen=True)
class ToolUsage:
    """Tool call count."""

    name: str
    count: int


@dataclass(frozen=True)
class FileAccess:
    """File read/write counts."""

    path: str
    reads: int = 0
    writes: int = 0


@dataclass(frozen=True)
class BashCommand:
    """Bash command execution record."""

    command: str
    count: int


@dataclass(frozen=True)
class ProviderHealth:
    """Provider reliability metrics."""

    provider: str
    slug: str
    total: int
    ok: int
    avg_ms: int
    max_ms: int


@dataclass(frozen=True)
class GuardActivity:
    """Per-hook allow/deny/warn counts."""

    hook: str
    allow: int = 0
    deny: int = 0
    warn: int = 0


@dataclass(frozen=True)
class ToolError:
    """Failed tool call detail."""

    tool: str
    code: str = ""
    message: str = ""


@dataclass(frozen=True)
class CompactionRecord:
    """One compaction event pair (start → done/error)."""

    stage: int
    ok: bool
    tokens_before: int = 0
    tokens_after: int = 0
    error: str = ""


@dataclass(frozen=True)
class SubagentRecord:
    """Subagent spawn result."""

    ok: bool
    error: str = ""


@dataclass(frozen=True)
class ContextBudgetEvent:
    """Context budget warn or hard-stop event."""

    action: str
    pct: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class CompactionWarningRecord:
    """Compaction-pressure warning — fires in both enabled/disabled cases."""

    action: str
    compaction_enabled: bool
    ratio: float = 0.0
    threshold: float = 0.0


@dataclass(frozen=True)
class CircuitBreakerRecord:
    """Compaction circuit-breaker event — anti-thrashing guard fired."""

    message: str = ""


@dataclass(frozen=True)
class CompactionStartRecord:
    """Compaction stage start — tokens_before and threshold."""

    stage: int
    tokens_before: int = 0
    threshold: float = 0.0


@dataclass
class SessionAnalytics:
    """Complete analytics for one session. Serializable to JSON for WebUI."""

    run_id: str
    role: str
    start_ts: str
    stop_reason: str
    ok: bool
    turns: int

    tool_usage: list[ToolUsage] = field(default_factory=list)
    file_access: list[FileAccess] = field(default_factory=list)
    bash_commands: list[BashCommand] = field(default_factory=list)
    token_timeline: list[TurnTokens] = field(default_factory=list)
    provider_health: list[ProviderHealth] = field(default_factory=list)
    guard_activity: list[GuardActivity] = field(default_factory=list)

    total_in: int = 0
    total_out: int = 0
    cache_hit_ratio: float = 0.0
    redundant_reads: int = 0
    repeated_commands: int = 0

    # PR #53 observability: tool errors, compaction, subagent, context budget
    tool_errors: list[ToolError] = field(default_factory=list)
    compaction_records: list[CompactionRecord] = field(default_factory=list)
    subagent_records: list[SubagentRecord] = field(default_factory=list)
    context_budget_events: list[ContextBudgetEvent] = field(default_factory=list)

    # S19: extended observability — compaction warnings, circuit breakers,
    # compaction starts, and message-level token accounting.
    compaction_warnings: list[CompactionWarningRecord] = field(default_factory=list)
    circuit_breaker_events: list[CircuitBreakerRecord] = field(default_factory=list)
    compaction_starts: list[CompactionStartRecord] = field(default_factory=list)
    model_msg_count: int = 0
    user_msg_count: int = 0


# ── Parsing ────────────────────────────────────────────────────────────────


def parse_session(events_path: Path) -> SessionAnalytics | None:  # noqa: C901 — event dispatch
    """Parse one events.jsonl into SessionAnalytics.

    Returns None if the file doesn't exist or is empty.
    Uses EventLog.read_all() for robust JSONL parsing (reuse, not duplicate).
    """
    if not events_path.exists():
        return None

    log = EventLog(events_path)
    try:
        events = log.read_all()
    except Exception:  # noqa: BLE001 — corrupt JSONL must not crash stats
        return None
    if not events:
        return None

    # Extract metadata from run_started
    run_id = events[0].run_id or events_path.parent.name
    role = ""
    start_ts = events[0].ts if events else ""
    stop_reason = "unknown"
    ok = True
    has_session_summary = False

    # Tool counts
    tool_counter: Counter[str] = Counter()
    # File access
    reads: Counter[str] = Counter()
    writes: Counter[str] = Counter()
    # Bash commands
    bash_counter: Counter[str] = Counter()
    # Token timeline
    turn_tokens: list[TurnTokens] = []
    current_turn = 0
    # Provider attempts
    provider_data: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    # Guard activity
    guard_data: dict[str, dict[str, int]] = defaultdict(lambda: {"allow": 0, "deny": 0, "warn": 0})
    # Totals from session_summary
    total_in = 0
    total_out = 0
    cache_hit_ratio = 0.0
    n_turns = 0
    # PR #53 observability accumulators
    tool_errors: list[ToolError] = []
    compaction_records: list[CompactionRecord] = []
    subagent_records: list[SubagentRecord] = []
    context_budget_events: list[ContextBudgetEvent] = []
    # S19: extended observability accumulators
    compaction_warnings: list[CompactionWarningRecord] = []
    circuit_breaker_events: list[CircuitBreakerRecord] = []
    compaction_starts: list[CompactionStartRecord] = []
    model_msg_count: int = 0
    user_msg_count: int = 0

    for event in events:
        kind = event.kind
        # TraceEvent.content is Mapping[str, object] (open schema per ADR-7 §7).
        # Values are always JSON primitives (int/float/str) after json.loads
        # round-trip; annotate as Any so int()/float() satisfy strict checkers.
        content: dict[str, Any] = dict(event.content) if event.content else {}

        if kind == "run_started":
            role = str(content.get("role", ""))

        elif kind == "tool_call":
            tool_name = event.tool_name
            tool_counter[tool_name] += 1
            params = content.get("params", {})
            if isinstance(params, dict):
                if tool_name == "fs.read_file" and "path" in params:
                    reads[str(params["path"])] += 1
                elif tool_name == "fs.write_file" and "path" in params:
                    writes[str(params["path"])] += 1
                elif tool_name == "fs.run_bash" and "command" in params:
                    bash_counter[str(params["command"])] += 1

        elif kind == "usage":
            current_turn += 1
            turn_tokens.append(
                TurnTokens(
                    turn=current_turn,
                    in_tokens=int(content.get("input_tokens", 0)),
                    out_tokens=int(content.get("output_tokens", 0)),
                    cache_read=int(content.get("cache_read_input_tokens", 0)),
                    cache_creation=int(content.get("cache_creation_input_tokens", 0)),
                )
            )

        elif kind == "provider_attempt":
            key = (str(content.get("provider", "")), str(content.get("slug", "")))
            provider_data[key].append(
                {
                    "status": int(content.get("status", 0)),
                    "ms": int(content.get("ms", 0)),
                    "error": content.get("error"),
                }
            )

        elif kind == "hook_decision":
            hook_name = str(content.get("middleware", "unknown"))
            decision = str(content.get("decision", ""))
            if "allow" in decision.lower():
                guard_data[hook_name]["allow"] += 1
            elif "deny" in decision.lower():
                guard_data[hook_name]["deny"] += 1

        elif kind == "loop_guard_warn":
            guard_data["LoopGuard"]["warn"] += 1

        # ── PR #53 observability: tool_result errors ──────────────────
        elif kind == "tool_result":
            tool_name = event.tool_name
            ok = bool(content.get("ok", True))
            if not ok:
                error = content.get("error")
                if isinstance(error, dict):
                    tool_errors.append(
                        ToolError(
                            tool=tool_name,
                            code=str(error.get("code", "")),
                            message=str(error.get("message", "")),
                        )
                    )

        # ── PR #53 observability: compaction events ───────────────────
        elif kind == "compaction_stage2_done":
            compaction_records.append(
                CompactionRecord(
                    stage=2,
                    ok=True,
                    tokens_before=int(content.get("tokens_before", 0)),
                    tokens_after=int(content.get("tokens_after", 0)),
                )
            )
        elif kind == "compaction_stage2_error":
            compaction_records.append(
                CompactionRecord(
                    stage=2,
                    ok=False,
                    error=str(content.get("error", "")),
                )
            )
        elif kind == "compaction_stage3_done":
            compaction_records.append(
                CompactionRecord(
                    stage=3,
                    ok=True,
                    tokens_before=int(content.get("tokens_before", 0)),
                    tokens_after=int(content.get("tokens_after", 0)),
                )
            )
        elif kind == "compaction_stage3_error":
            compaction_records.append(
                CompactionRecord(
                    stage=3,
                    ok=False,
                    error=str(content.get("error", "")),
                )
            )

        # ── PR #53 observability: subagent events ─────────────────────
        elif kind == "subagent_spawn_done":
            subagent_records.append(SubagentRecord(ok=True))
        elif kind == "subagent_spawn_fail":
            subagent_records.append(SubagentRecord(ok=False, error=str(content.get("error", ""))))

        # ── PR #53 observability: context budget events ───────────────
        elif kind == "context_budget_warn":
            context_budget_events.append(
                ContextBudgetEvent(
                    action=str(content.get("action", "warn")),
                    pct=float(content.get("ratio", 0.0)) * 100,
                    message=str(content.get("message", "")),
                )
            )
        elif kind == "context_budget_hard_stop":
            context_budget_events.append(
                ContextBudgetEvent(
                    action="hard_stop",
                    pct=float(content.get("ratio", 0.0)) * 100,
                    message=str(content.get("message", "")),
                )
            )

        # ── S19: compaction warning / circuit breaker / compaction starts ──
        elif kind == "compaction_warning":
            compaction_warnings.append(
                CompactionWarningRecord(
                    action=str(content.get("action", "")),
                    compaction_enabled=bool(content.get("compaction_enabled", False)),
                    ratio=float(content.get("ratio", 0.0)),
                    threshold=float(content.get("threshold", 0.0)),
                )
            )

        elif kind == "compaction_circuit_breaker":
            circuit_breaker_events.append(
                CircuitBreakerRecord(
                    message=str(content.get("message", "")),
                )
            )

        elif kind == "compaction_stage2_start":
            compaction_starts.append(
                CompactionStartRecord(
                    stage=2,
                    tokens_before=int(content.get("tokens_before", 0)),
                    threshold=float(content.get("threshold", 0.0)),
                )
            )

        elif kind == "compaction_stage3_start":
            compaction_starts.append(
                CompactionStartRecord(
                    stage=3,
                    tokens_before=int(content.get("tokens_before", 0)),
                    threshold=float(content.get("threshold", 0.0)),
                )
            )

        # ── S19: model_msg / user_msg counting ────────────────────────
        elif kind == "model_msg":
            model_msg_count += 1

        elif kind == "user_msg":
            user_msg_count += 1

        elif kind == "session_summary":
            total_in = int(content.get("input_tokens", 0))
            total_out = int(content.get("output_tokens", 0))
            cache_hit_ratio = float(content.get("cache_hit_ratio", 0.0))
            n_turns = int(content.get("n_turns", 0))
            has_session_summary = True

        elif kind == "run_stopped":
            reason = str(content.get("reason", ""))
            if reason:
                stop_reason = reason
                ok = False  # any run_stopped event is abnormal

    # Infer clean stop: session_summary present + no run_stopped event
    # means drive_session exited via finish() with stop_reason="stopped_by_llm".
    if has_session_summary and stop_reason == "unknown":
        stop_reason = "stopped_by_llm"
        ok = True

    # Build typed results
    tool_usage = sorted(
        [ToolUsage(name=n, count=c) for n, c in tool_counter.items()],
        key=lambda t: -t.count,
    )

    all_paths: set[str] = set(reads) | set(writes)
    file_access = sorted(
        [FileAccess(path=p, reads=reads.get(p, 0), writes=writes.get(p, 0)) for p in all_paths],
        key=lambda f: -(f.reads + f.writes),
    )

    bash_cmds = sorted(
        [BashCommand(command=c, count=n) for c, n in bash_counter.items()],
        key=lambda b: -b.count,
    )

    provider_health: list[ProviderHealth] = []
    for (prov, slug), attempts in provider_data.items():
        ok_count = sum(1 for a in attempts if a["status"] == 200)
        ms_list = [a["ms"] for a in attempts if a["ms"] > 0]
        provider_health.append(
            ProviderHealth(
                provider=prov,
                slug=slug,
                total=len(attempts),
                ok=ok_count,
                avg_ms=int(sum(ms_list) / len(ms_list)) if ms_list else 0,
                max_ms=max(ms_list) if ms_list else 0,
            )
        )

    guard_list = [
        GuardActivity(hook=h, allow=d["allow"], deny=d["deny"], warn=d["warn"]) for h, d in guard_data.items()
    ]

    redundant = sum(c - 1 for c in reads.values() if c > 1)
    repeated = sum(c - 1 for c in bash_counter.values() if c > 1)

    return SessionAnalytics(
        run_id=run_id,
        role=role,
        start_ts=start_ts,
        stop_reason=stop_reason,
        ok=ok,
        turns=n_turns or current_turn,
        tool_usage=tool_usage,
        file_access=file_access,
        bash_commands=bash_cmds,
        token_timeline=turn_tokens,
        provider_health=provider_health,
        guard_activity=guard_list,
        total_in=total_in,
        total_out=total_out,
        cache_hit_ratio=cache_hit_ratio,
        redundant_reads=redundant,
        repeated_commands=repeated,
        tool_errors=tool_errors,
        compaction_records=compaction_records,
        subagent_records=subagent_records,
        context_budget_events=context_budget_events,
        compaction_warnings=compaction_warnings,
        circuit_breaker_events=circuit_breaker_events,
        compaction_starts=compaction_starts,
        model_msg_count=model_msg_count,
        user_msg_count=user_msg_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _bar(count: int, max_count: int, width: int = 16) -> str:
    if max_count <= 0:
        return ""
    filled = max(1, int(width * count / max_count))
    return "█" * filled


# ── Rendering ──────────────────────────────────────────────────────────────


def render_session(analytics: SessionAnalytics, *, stream: TextIO = sys.stderr) -> None:  # noqa: C901 — section renderer
    """Render single-session report to stream."""
    a = analytics
    w = stream.write

    w(f"\n{'═' * 50}\n")
    w(f"📊 Session: {a.run_id}\n")
    status = "✅" if a.ok else "❌"
    w(f"   {status} {a.role} │ {a.turns} turns │ {a.start_ts[:10]}\n")
    w(f"   Stop: {a.stop_reason}\n")
    w(f"{'═' * 50}\n\n")

    # Tools
    if a.tool_usage:
        max_count = a.tool_usage[0].count if a.tool_usage else 1
        w("🔧 Tools:\n")
        for t in a.tool_usage:
            w(f"   {t.name:<20s} {t.count:>3d}x  {_bar(t.count, max_count)}\n")
        w("\n")

    # Files
    if a.file_access:
        w("📂 Files:\n")
        for f_acc in a.file_access[:10]:
            parts: list[str] = []
            if f_acc.reads:
                warn = " ⚠" if f_acc.reads > 2 else ""
                parts.append(f"READ {f_acc.reads}x{warn}")
            if f_acc.writes:
                parts.append(f"WRITE {f_acc.writes}x")
            w(f"   {' '.join(parts):<16s} {f_acc.path}\n")
        if len(a.file_access) > 10:
            w(f"   ... and {len(a.file_access) - 10} more\n")
        w("\n")

    # Bash
    if a.bash_commands:
        w("💻 Bash:\n")
        for b in a.bash_commands[:5]:
            cmd_preview = b.command[:60] + ("..." if len(b.command) > 60 else "")
            warn = " ⚠" if b.count > 1 else ""
            w(f"   {b.count}x{warn}  {cmd_preview}\n")
        w("\n")

    # Tokens
    if a.token_timeline:
        w("📊 Tokens:\n")
        w(f"   {'Turn':<6s} {'In':<8s} {'Out':<8s} {'Cache':<8s}\n")
        for tt in a.token_timeline:
            w(
                f"   {tt.turn:<6d} {_fmt_tokens(tt.in_tokens):<8s} "
                f"{_fmt_tokens(tt.out_tokens):<8s} {tt.cache_hit_ratio:.0%}\n"
            )
        w(
            f"   {'Total':<6s} {_fmt_tokens(a.total_in):<8s} "
            f"{_fmt_tokens(a.total_out):<8s} {a.cache_hit_ratio:.0%}\n"
        )
        w("\n")

    # Provider
    if a.provider_health:
        w("🌐 Provider:\n")
        for p in a.provider_health:
            w(f"   {p.provider}/{p.slug}  {p.ok}/{p.total} ok  avg={p.avg_ms}ms\n")
        w("\n")

    # Guards
    if a.guard_activity:
        w("🛡 Guards:\n")
        for g in a.guard_activity:
            parts_g = [f"{g.allow} allow"]
            if g.deny:
                parts_g.append(f"{g.deny} deny")
            if g.warn:
                parts_g.append(f"{g.warn} warn")
            w(f"   {g.hook:<20s} {', '.join(parts_g)}\n")
        w("\n")

    # Tool errors
    if a.tool_errors:
        w("❌ Tool errors:\n")
        for te in a.tool_errors[:10]:
            w(f"   {te.tool:<20s} {te.code}: {te.message[:60]}\n")
        if len(a.tool_errors) > 10:
            w(f"   ... and {len(a.tool_errors) - 10} more\n")
        w("\n")

    # Compaction
    if a.compaction_records:
        w("🗜️ Compaction:\n")
        for cr in a.compaction_records:
            if cr.ok:
                w(f"   stage{cr.stage}: {cr.tokens_before} → {cr.tokens_after} tokens ✓\n")
            else:
                w(f"   stage{cr.stage}: error — {cr.error[:60]} ✗\n")
        w("\n")

    # Subagent
    if a.subagent_records:
        ok_count = sum(1 for s in a.subagent_records if s.ok)
        fail_count = len(a.subagent_records) - ok_count
        w(f"🔀 Subagent: {ok_count} ok, {fail_count} failed\n")
        for sr in a.subagent_records:
            if not sr.ok:
                w(f"   failed: {sr.error[:60]}\n")
        w("\n")

    # Context budget
    if a.context_budget_events:
        w("📐 Context budget:\n")
        for cbe in a.context_budget_events:
            w(f"   {cbe.action}: {cbe.pct:.0f}% — {cbe.message[:60]}\n")
        w("\n")

    # Compaction warnings (S19)
    if a.compaction_warnings:
        w("⚡ Compaction pressure:\n")
        for cw in a.compaction_warnings:
            enabled = "enabled" if cw.compaction_enabled else "disabled"
            w(f"   {cw.action}: ratio={cw.ratio:.0%} threshold={cw.threshold:.0%} ({enabled})\n")
        w("\n")

    # Circuit breaker (S19)
    if a.circuit_breaker_events:
        w("🔴 Circuit breaker:\n")
        for cb in a.circuit_breaker_events:
            w(f"   {cb.message[:80]}\n")
        w("\n")

    # Message-level accounting (S19)
    if a.model_msg_count or a.user_msg_count:
        w(f"💬 Messages: {a.model_msg_count} model, {a.user_msg_count} user\n\n")

    # Efficiency
    warnings = efficiency_warnings(a)
    if warnings:
        w("⚠ Efficiency:\n")
        for warning in warnings:
            w(f"   {warning}\n")
        w("\n")

    stream.flush()


def render_session_json(analytics: SessionAnalytics) -> dict[str, Any]:
    """Convert SessionAnalytics to JSON-serializable dict."""
    return asdict(analytics)


# ── Aggregate ──────────────────────────────────────────────────────────────


def aggregate_sessions(sessions: list[SessionAnalytics]) -> dict[str, Any]:
    """Compute cross-session aggregate metrics."""
    if not sessions:
        return {
            "sessions": 0,
            "ok": 0,
            "failed": 0,
            "total_in": 0,
            "total_out": 0,
            "avg_cache_hit": 0.0,
            "stop_reasons": {},
            "most_read_files": [],
            "total_turns": 0,
        }

    total_in = sum(s.total_in for s in sessions)
    total_out = sum(s.total_out for s in sessions)
    ok_count = sum(1 for s in sessions if s.ok)

    # Most read files across all sessions
    all_reads: Counter[str] = Counter()
    for s in sessions:
        for f_acc in s.file_access:
            all_reads[f_acc.path] += f_acc.reads

    # Stop reasons
    stop_reasons: Counter[str] = Counter()
    for s in sessions:
        stop_reasons[s.stop_reason] += 1

    # Cache hit avg
    cache_ratios = [s.cache_hit_ratio for s in sessions if s.cache_hit_ratio > 0]
    avg_cache = sum(cache_ratios) / len(cache_ratios) if cache_ratios else 0.0

    return {
        "sessions": len(sessions),
        "ok": ok_count,
        "failed": len(sessions) - ok_count,
        "total_in": total_in,
        "total_out": total_out,
        "avg_cache_hit": avg_cache,
        "stop_reasons": dict(stop_reasons.most_common()),
        "most_read_files": all_reads.most_common(10),
        "total_turns": sum(s.turns for s in sessions),
    }


def render_aggregate(sessions: list[SessionAnalytics], *, stream: TextIO = sys.stderr) -> None:
    """Render cross-session aggregate report."""
    agg = aggregate_sessions(sessions)
    w = stream.write

    w(f"\n{'═' * 50}\n")
    w(f"📊 {agg['sessions']} sessions\n")
    w(f"{'═' * 50}\n\n")

    w(f"Status: {agg['ok']} OK │ {agg['failed']} failed\n")
    if agg["stop_reasons"]:
        for reason, count in agg["stop_reasons"].items():
            w(f"   {reason}: {count}x\n")
    w(
        f"\nTokens: in={_fmt_tokens(agg['total_in'])} "
        f"out={_fmt_tokens(agg['total_out'])} │ "
        f"Cache avg: {agg['avg_cache_hit']:.0%}\n"
    )
    w(f"Turns: {agg['total_turns']} total\n\n")

    if agg["most_read_files"]:
        w("Most read files:\n")
        for path, count in agg["most_read_files"][:5]:
            w(f"   {path:<45s} {count}x\n")
        w("\n")

    stream.flush()


# ── Dead zones ─────────────────────────────────────────────────────────────


def find_dead_zones(workspace: Path, sessions: list[SessionAnalytics]) -> list[str]:
    """Find src/ Python files never accessed across all sessions."""
    src_dir = workspace / "src"
    if not src_dir.exists():
        return []

    all_py = {str(p.relative_to(workspace)) for p in src_dir.rglob("*.py") if "__pycache__" not in str(p)}

    accessed: set[str] = set()
    for s in sessions:
        for f_acc in s.file_access:
            accessed.add(f_acc.path)

    dead = sorted(all_py - accessed)
    return dead


# ── Efficiency warnings ───────────────────────────────────────────────────


def efficiency_warnings(analytics: SessionAnalytics) -> list[str]:
    """Generate human-readable efficiency warnings."""
    warnings: list[str] = []

    if analytics.redundant_reads > 0:
        warnings.append(f"{analytics.redundant_reads} redundant file reads (same file read multiple times)")

    if analytics.repeated_commands > 0:
        warnings.append(
            f"{analytics.repeated_commands} repeated bash commands (same command run multiple times)"
        )

    # Cold start warning
    if analytics.token_timeline and analytics.token_timeline[0].cache_hit_ratio == 0:
        if len(analytics.token_timeline) > 3:
            late_cold = [t for t in analytics.token_timeline[2:] if t.cache_hit_ratio < 0.1]
            if late_cold:
                warnings.append(
                    f"Cache miss after turn 2 (turns {[t.turn for t in late_cold]}) "
                    f"— prompt caching may not be working"
                )

    return warnings
