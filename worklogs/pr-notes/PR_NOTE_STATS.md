# PR: `fa stats` — Session analytics

## Intent: IMPLEMENT
## Invariant: Implements: post-hoc session analytics from existing EventLog data

## Problem

EventLog writes detailed JSONL data for every session (tool calls, tokens,
provider attempts, guard decisions) but nothing reads it for analysis.
The operator has no way to see file access patterns, token waste,
provider health, or guard activity across sessions.

## Solution

`fa stats` — a pure read-only consumer of existing `events.jsonl` files.
Zero changes to coder_loop or EventLog. Zero new dependencies.

```bash
fa stats --run-id workflow-001    # single session analytics
fa stats                          # aggregate across all sessions
fa stats --dead-zones             # src/ files never accessed
fa stats --output json            # JSON for WebUI
fa stats --since 7d               # filter by age
```

## What it shows

- **Tool usage**: fs.read_file 14x, fs.run_bash 6x, ...
- **File access**: which files read/written, how many times, ⚠ redundant reads
- **Bash commands**: which commands run, repeated ones flagged
- **Token timeline**: per-turn in/out/cache_read + cache hit ratio
- **Provider health**: ok/fail count, avg/max latency
- **Guard activity**: per-hook allow/deny/warn counts
- **Dead zones**: src/ files never accessed across sessions
- **Efficiency warnings**: redundant reads, repeated commands, cache misses

## Architecture

```text
events.jsonl (existing, unchanged)
    ↓ read by EventLog.read_all() (existing, reused)
    ↓
parse_session() → SessionAnalytics (typed dataclass)
    ↓
render_session()  → human-readable to stderr
render_session_json() → dict for --output json (WebUI ready)
aggregate_sessions() → cross-session metrics
find_dead_zones() → src/ files never touched
efficiency_warnings() → actionable improvement suggestions
```

## Files changed

| File | Change |
|------|--------|
| `src/fa/stats.py` | NEW — analytics engine (~300 lines) |
| `src/fa/cli.py` | `fa stats` subparser + `_cmd_stats` handler |
| `tests/test_stats.py` | NEW — 14 tests |
| `knowledge/pr-notes/PR_NOTE_STATS.md` | This file |

## Data model (WebUI foundation)

Typed dataclasses: `SessionAnalytics`, `TurnTokens`, `ToolUsage`,
`FileAccess`, `BashCommand`, `ProviderHealth`, `GuardActivity`.
All serializable to JSON via `dataclasses.asdict()`.

## Subtraction check

- **Removing what?** None — EventLog is the writer, fa stats is the missing reader
- **Lost if omitted?** No visibility into agent behavior patterns
- **OSS precedent?** Aider /tokens, Claude Code total_cost_usd. No post-hoc
  session analysis exists — FA would be first.
