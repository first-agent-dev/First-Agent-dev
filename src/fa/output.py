"""Live session output — EventBus + renderers for ``fa run``.

Emits user-facing progress to **stderr** (never stdout — that's
reserved for the final answer so ``fa run --task "..." > result.txt``
works).  EventLog (events.jsonl) remains the audit/replay sink;
this module is the display complement.

Architecture::

    coder_loop.py
        ├── state.log.append(...)    → EventLog (JSONL file, audit)
        └── output.emit(...)         → EventBus → ConsoleRenderer (stderr)
                                                → QuietRenderer (nothing)
                                                → (Phase 2: JsonLineWriter)

Design rules:
- A listener that raises does NOT crash the agent loop.
- NO new runtime dependencies (no Rich, no structlog).
- Respects NO_COLOR (https://no-color.org) and TERM=dumb.
- All data comes from existing ResponseInfo / ToolCall / ToolResult
  objects — no recomputation.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from fa.formatting import fmt_tokens as _fmt_tokens

logger = logging.getLogger(__name__)

__all__ = [
    "CONSOLE_MIRROR_KINDS",
    "ConsoleRenderer",
    "EventBus",
    "EventType",
    "LogKind",
    "OutputEvent",
    "QuietRenderer",
]

# ── Event type ─────────────────────────────────────────────────────────────

EventType = Literal[
    "session_start",
    "turn_start",
    "llm_response",
    "tool_call",
    "hook_deny",
    "api_retry",
    "session_end",
    "context_warn",
    "compaction_warning",
    "config_warning",
    "compaction_start",
    "compaction_end",
    "subagent_start",
    "subagent_end",
    "cost_alert",
    "loop_warn",
]

# ── Log kind ──────────────────────────────────────────────────────────────
# Canonical enumeration of all `kind=` string values passed to
# `EventLog.append()`.  Every log.append(kind=...) call site must use
# one of these values — pyright enforces at lint time.  Adding a new
# kind requires updating this Literal; the contract check script
# (check_log_kind_contract.py) validates consistency.

LogKind = Literal[
    # Session lifecycle
    "run_started",
    "run_stopped",
    "session_summary",
    # LLM I/O
    "user_msg",
    "model_msg",
    "usage",
    "provider_attempt",
    "llm_call",
    # Tool I/O
    "tool_call",
    "tool_result",
    # Hooks / guards
    "hook_decision",
    "loop_guard_warn",
    "audit",
    # Context budget
    "context_budget_warn",
    "context_budget_hard_stop",
    # Configuration and compaction
    "config_warning",
    "compaction_warning",  # emitted before compaction starts (context pressure detected)
    "compaction_circuit_breaker",
    "compaction_stage2_start",
    "compaction_stage2_done",
    "compaction_stage2_error",
    "compaction_stage3_start",
    "compaction_stage3_done",
    "compaction_stage3_error",
    # Subagent
    "subagent_spawn_start",
    "subagent_spawn_done",
    "subagent_spawn_fail",
    # Observability / recovery
    "recovery_action",
    "verification",
    "cost_observation",
    "telemetry",
    # Infrastructure
    "service_unavailable",
    "timeout",
]

# ── Console-mirror kinds ─────────────────────────────────────────────────
# Log kinds that MUST also emit an OutputEvent on the same code path.
# This ensures the operator sees these critical events in the console
# (stderr) in addition to the audit trail (events.jsonl). The contract
# check script (check_log_kind_contract.py) validates dual-write.

CONSOLE_MIRROR_KINDS: frozenset[LogKind] = frozenset(
    {
        "context_budget_warn",
        "context_budget_hard_stop",
        "compaction_warning",
        "config_warning",
        "compaction_stage2_start",
        "compaction_stage2_done",
        "compaction_stage2_error",
        "compaction_stage3_start",
        "compaction_stage3_done",
        "compaction_stage3_error",
        "compaction_circuit_breaker",
        "tool_call",
        "subagent_spawn_done",
        "subagent_spawn_fail",
        "run_stopped",
    }
)


@dataclass(frozen=True, slots=True)
class OutputEvent:
    """Single display event. Consumed by renderers via EventBus."""

    type: EventType
    ts: float = field(default_factory=time.monotonic)
    turn: int = 0
    max_turns: int = 0
    data: dict[str, Any] = field(default_factory=dict)


# ── EventBus ───────────────────────────────────────────────────────────────


class EventBus:
    """Sync fan-out: dispatches OutputEvent to registered listeners.

    A listener that raises is caught and printed to stderr — it never
    crashes the agent loop.
    """

    def __init__(self) -> None:
        self._listeners: list[Any] = []

    def add(self, listener: Any) -> None:
        self._listeners.append(listener)

    def emit(self, event: OutputEvent) -> None:
        for listener in self._listeners:
            try:
                listener.on_event(event)
            except Exception as exc:  # Listener errors are logged but never crash the loop
                logger.error(
                    "Output listener %s raised: %s",
                    type(listener).__name__,
                    exc,
                    exc_info=True,
                )


# ── Helpers ────────────────────────────────────────────────────────────────

_ACTION_VERBS: dict[str, str] = {
    "fs.read_file": "Read",
    "fs.write_file": "Write",
    "fs.run_bash": "Bash",
    "pr.prepare": "Draft",
}


# ── ConsoleRenderer ───────────────────────────────────────────────────────


class ConsoleRenderer:
    """Human-readable output to stderr. Respects NO_COLOR + TERM=dumb.

    Detail levels:
    - minimal:  turn headers + final summary
    - standard: + tool action lines
    - verbose:  + LLM timing/tokens + tool params
    - debug:    + model text per turn
    """

    def __init__(
        self,
        *,
        detail: str = "standard",
        show_cost: bool = False,
        show_context_pct: bool = True,
        no_color: bool = False,
    ) -> None:
        self.detail = detail
        self.show_cost = show_cost
        self.show_context_pct = show_context_pct
        # ``no_color`` is the explicit caller-supplied form of the same
        # decision the NO_COLOR env var expresses. It exists so ``fa run
        # --no-color`` does not have to mutate ``os.environ`` to reach this
        # constructor: writing process-global state from a command handler
        # leaked colourless output into every later in-process invocation
        # and into tests sharing the interpreter. The env var remains
        # honoured for the no-color.org contract and for TERM=dumb.
        self._use_color = (
            not no_color
            and os.environ.get("NO_COLOR", "") == ""
            and os.environ.get("TERM", "xterm") not in ("dumb", "")
            and sys.stderr.isatty()
        )

    def _c(self, code: str, text: str) -> str:
        if not self._use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def _write(self, text: str) -> None:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

    def on_event(self, event: OutputEvent) -> None:
        handler = getattr(self, f"_handle_{event.type}", None)
        if handler:
            handler(event)

    def _handle_session_start(self, e: OutputEvent) -> None:
        d = e.data
        self._write(f"{self._c('1', 'FA')} │ {d.get('model', '?')} ({d.get('role', '?')}) │ max_turns={e.max_turns}")

    def _handle_turn_start(self, e: OutputEvent) -> None:
        if self.detail == "minimal":
            return
        self._write(f"\n{self._c('1', f'[turn {e.turn}/{e.max_turns}]')}")

    def _handle_llm_response(self, e: OutputEvent) -> None:
        d = e.data
        parts = [f"🤖 {d.get('ms', 0)}ms"]
        parts.append(f"in={_fmt_tokens(d.get('in_tokens', 0))}")
        parts.append(f"out={_fmt_tokens(d.get('out_tokens', 0))}")

        cache_read = d.get("cache_read", 0)
        in_tokens = d.get("in_tokens", 0)
        if cache_read and in_tokens:
            ratio = cache_read / max(in_tokens, 1) * 100
            parts.append(f"cache={ratio:.0f}%")

        self._write("  " + self._c("36", " │ ".join(parts)))

        if self.detail in ("verbose", "debug") and d.get("text"):
            raw_text = d["text"]
            text_str = raw_text if isinstance(raw_text, str) else str(raw_text)
            preview = text_str[:200].replace("\n", " ")
            self._write(f"  {self._c('2', f'💭 {preview}')}")

    def _handle_tool_call(self, e: OutputEvent) -> None:
        d = e.data
        tool = d.get("tool", "?")
        verb = _ACTION_VERBS.get(tool, tool)
        ok = d.get("ok", True)
        icon = self._c("32", "✓") if ok else self._c("31", "✗")

        if self.detail == "minimal":
            return

        summary = d.get("summary", "")
        param_hint = ""
        if self.detail in ("standard", "verbose", "debug"):
            params = d.get("params", {})
            if "path" in params:
                param_hint = str(params["path"])
            elif "command" in params:
                cmd = str(params["command"])
                param_hint = cmd[:60] + ("..." if len(cmd) > 60 else "")

        line = f"  → {verb}"
        if param_hint:
            line += f" {self._c('2', param_hint)}"
        if ok and summary:
            line += f" {icon} {summary}"
        elif not ok:
            line += f" {icon} {d.get('error', 'failed')}"
        else:
            line += f" {icon}"

        if self.detail == "debug" and d.get("ms"):
            ms = d.get("ms", 0)
            line += f" {self._c('2', f'({ms}ms)')}"

        self._write(line)

    def _handle_hook_deny(self, e: OutputEvent) -> None:
        d = e.data
        self._write(f"  {self._c('31', '⛔')} {d.get('hook', '?')}: {d.get('reason', '?')}")

    def _handle_api_retry(self, e: OutputEvent) -> None:
        d = e.data
        self._write(
            f"  {self._c('33', '⏳')} retry in {d.get('retry_after_s', '?')}s "
            f"({d.get('provider', '?')}/{d.get('status', '?')})"
        )

    def _handle_session_end(self, e: OutputEvent) -> None:
        d = e.data
        sep = "─" * 50 if self._use_color else "-" * 50
        self._write(sep)
        ok = d.get("ok", True)
        status = self._c("32", "OK") if ok else self._c("31", "FAIL")
        self._write(f"{status}: {d.get('stop_reason', '?')} (turns={d.get('turns', 0)})")

        parts = [f"{d.get('wall_s', 0):.1f}s"]
        parts.append(f"in={_fmt_tokens(d.get('total_in', 0))}")
        parts.append(f"out={_fmt_tokens(d.get('total_out', 0))}")

        cache_ratio = d.get("cache_hit_ratio")
        if cache_ratio is not None:
            parts.append(f"cache={cache_ratio:.0%}")

        if self.show_cost and d.get("est_cost_usd") is not None:
            parts.append(f"~${d['est_cost_usd']:.4f}")

        self._write(f" Total: {' │ '.join(parts)}")

        if self.show_context_pct and d.get("context_used_pct") is not None:
            self._write(f" Context: {d['context_used_pct']:.0f}% of window")

    # ── New handlers for PR #53 observability gaps ──────────────────────

    def _handle_context_warn(self, e: OutputEvent) -> None:
        d = e.data
        pct = d.get("pct", 0)
        action = d.get("action", "")
        if action in ("stage2", "stage3") or pct >= 80:
            self._write(f"  {self._c('33', '⚠️')} context: {pct}% of window ({action})")
        elif self.detail in ("verbose", "debug"):
            self._write(f"  {self._c('33', '⚠️')} context: {pct}% of window")

    def _handle_compaction_warning(self, e: OutputEvent) -> None:
        d = e.data
        enabled = bool(d.get("compaction_enabled", False))
        threshold = d.get("threshold")
        action = d.get("action", "")
        state = "enabled" if enabled else "disabled"
        threshold_text = f", threshold={threshold}" if threshold is not None else ""
        self._write(f"  {self._c('33', '⚠️')} compaction {state}{threshold_text} ({action})")

    def _handle_config_warning(self, e: OutputEvent) -> None:
        d = e.data
        self._write(
            f"  {self._c('33', '⚠️')} config: {d.get('key', 'unknown')} — {d.get('detail', 'configuration warning')}"
        )

    def _handle_compaction_start(self, e: OutputEvent) -> None:
        d = e.data
        stage = d.get("stage", "?")
        self._write(f"  {self._c('36', '🗜️')} compaction stage{stage}: summarizing...")

    def _handle_compaction_end(self, e: OutputEvent) -> None:
        d = e.data
        stage = d.get("stage", "?")
        ok = d.get("ok", True)
        if ok:
            before = d.get("tokens_before", 0)
            after = d.get("tokens_after", 0)
            self._write(f"  {self._c('36', '🗜️')} compaction stage{stage}: done, {before} → {after} tokens")
        else:
            self._write(f"  {self._c('31', '❌')} compaction stage{stage} error: {d.get('error', 'unknown')}")

    def _handle_subagent_start(self, e: OutputEvent) -> None:
        d = e.data
        role = d.get("role", "?")
        self._write(f"  → Spawn subagent [{role}]")

    def _handle_subagent_end(self, e: OutputEvent) -> None:
        d = e.data
        ok = d.get("ok", True)
        if ok:
            if self.detail in ("verbose", "debug"):
                self._write("  ← subagent done: exit=0")
        else:
            self._write(f"  {self._c('31', '❌')} subagent failed: {d.get('error', 'unknown')}")

    def _handle_cost_alert(self, e: OutputEvent) -> None:
        d = e.data
        self._write(f"  {self._c('33', '💰')} cost: {d.get('message', 'threshold reached')}")

    def _handle_loop_warn(self, e: OutputEvent) -> None:
        d = e.data
        self._write(f"  {self._c('33', '🔄')} loop detected: {d.get('detector', '?')} — {d.get('message', '')}")


# ── QuietRenderer ─────────────────────────────────────────────────────────


class QuietRenderer:
    """Emits nothing. Final answer is printed by cli.py to stdout."""

    def on_event(self, event: OutputEvent) -> None:
        pass
