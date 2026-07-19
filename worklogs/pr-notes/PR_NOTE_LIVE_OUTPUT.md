# PR: Live per-turn console output for `fa run`

## Intent: IMPLEMENT
## Invariant: Implements: real-time session progress display via EventBus

## Problem

`fa run` showed nothing for 30-120 seconds while the agent worked,
then printed the final result. Zero visibility into what was happening.

## Solution

EventBus architecture: `drive_session()` emits `OutputEvent` objects
at 8 call sites alongside existing `EventLog` writes. Registered
listeners render them.

```
coder_loop.py
    ├── state.log.append(...)    → EventLog (JSONL file, unchanged)
    └── output.emit(...)         → EventBus → ConsoleRenderer (stderr)
```

Console output example:
```
FA │ glm-5p2 (planner) │ max_turns=16

[turn 1/16]
  🤖 1847ms │ in=2.1k out=312 cache=87%
  → Read src/fa/cli.py ✓ 505 lines
  → Write src/fa/cli.py ✓
  → Bash ruff check src/fa/cli.py ✓ exit=0

[turn 2/16]
  🤖 3201ms │ in=4.8k out=891 cache=92%
  → Draft intent=FIX ✓

──────────────────────────────────────────────────
OK: stopped_by_llm (turns=2)
 Total: 5.0s │ in=6.9k out=1.2k │ cache=89%
```

## Key design decisions

- **stderr for progress, stdout for final answer** — `fa run > result.txt` works
- **EventBus crash-isolates listeners** — a broken renderer never crashes the agent
- **0 new runtime dependencies** — ANSI escapes, no Rich
- **NO_COLOR + TERM=dumb** respected — industry standard
- **4 detail levels** — minimal/standard/verbose/debug (progressive disclosure)
- **Extends, doesn't replace** — EventLog (audit JSONL) unchanged

## CLI flags

```
--output-mode console|quiet    # default: console
--detail minimal|standard|verbose|debug
--no-color
```

## Phase 2 extension points

Adding a new output sink = one file + `output_bus.add(new_listener)`:
- JsonLineWriter for WebUI (NDJSON on stdout)
- config.yaml `output:` section for WebUI button control
- `fa replay` command reading existing EventLog JSONL

## Files changed

| File | Change |
|------|--------|
| `src/fa/output.py` | NEW — EventBus + OutputEvent + ConsoleRenderer + QuietRenderer |
| `src/fa/inner_loop/coder_loop.py` | 8 emit sites + `output` parameter on drive_session |
| `src/fa/cli.py` | --output-mode, --detail, --no-color flags + EventBus wiring |
| `tests/test_output.py` | NEW — 10 tests |

## Subtraction check

- **Removing what?** Nothing duplicated — EventLog = audit file, Output = user display
- **Lost if omitted?** Operator waits 30-120s blind
- **OSS precedent?** Claude Code, Kiro, Aider, Agent — all show per-turn progress
