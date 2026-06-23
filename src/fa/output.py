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

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = [
    "ConsoleRenderer",
    "EventBus",
    "EventType",
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
]


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
            except Exception as exc:  # noqa: BLE001 — never crash the loop
                print(
                    f"[output] {type(listener).__name__} raised: {exc}",
                    file=sys.stderr,
                )


# ── Helpers ────────────────────────────────────────────────────────────────

_ACTION_VERBS: dict[str, str] = {
    "fs.read_file": "Read",
    "fs.write_file": "Write",
    "fs.run_bash": "Bash",
    "pr.prepare": "Draft",
}


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


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
    ) -> None:
        self.detail = detail
        self.show_cost = show_cost
        self.show_context_pct = show_context_pct
        self._use_color = (
            os.environ.get("NO_COLOR", "") == ""
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
        self._write(
            f"{self._c('1', 'FA')} │ {d.get('model', '?')} ({d.get('role', '?')}) │ "
            f"max_turns={e.max_turns}"
        )

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
            preview = d["text"][:200].replace("\n", " ")
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


# ── QuietRenderer ─────────────────────────────────────────────────────────


class QuietRenderer:
    """Emits nothing. Final answer is printed by cli.py to stdout."""

    def on_event(self, event: OutputEvent) -> None:
        pass
