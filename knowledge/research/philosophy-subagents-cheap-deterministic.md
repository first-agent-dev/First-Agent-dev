---
title: "Philosophy: Pair over Autonomy — Cheap Stateless Subagent as Puzzle Piece, Not Self-Evolving System"
source:
  - "User philosophy 2026-07-11: want and FOMO, 100k lines logs about nothing, enough to silently think and do one task together with agent as pair, don't believe in smart autonomous systems now"
  - "Paper 2 §4.4 Topology complexity vs formality, §5.1.1 Harness as Distillation Surface, §5.2.1 Harness-Level Evaluation"
  - "Paper 1 MACOG: constrained realization + policy grounding + runtime grounding triad"
  - "First-Agent Pillar 3 token/tool efficient, Pillar 2 pragmatic single-user product, §1.2 minimalism-first, §1.2.6 Substrate Formality Principle (proposed)"
compiled: "2026-07-11"
goal_lens: "Answer user philosophical question: is main stateful + cheap stateless subagent for isolated deterministic puzzle piece (structured websearch, simple function) good idea or overcomplicated? Should we do it?"
tier: stable
---

## User Philosophy (Verbatim for Context)

> для меня сейчас это похоже больше на want и fomo: я в сообществе часто слышу вопросы о новоприбывших в стиле:"а эта самоэволюционирующая система что полезного делает?" Мой ответ сейчас - занимает ум neurodivergent individuals как я сам, читаем эти логи ни-о-чем на 100 тысяч строк там,где достаточно было молча подумать и сделать одну задачу вместе с агентом на пару.
> Как бы ни хотелось умных автономных систем -не верю на текущий момент.
> Моя идея субагентов это решение задачи,которая еще не сформирована практикой.
> Да,я могу представить сценарий,где будет выгодно иметь main stateful - работает,цепочка api call растет с каждым вызовом,но иногда запускает внешнего агента со своим изолированным контекстом который очень дешево и детерминированно принесет main недостающий кусочек пазла. например,структурированный websearch или написанную простую функцию.
> там где у main в loop уже висит 180k token in context window этот суб агент может сэкономить на решении простой задачи вне main loop.

## My Take — Direct Answer: Not Overcomplicated If Limited to Cheap Deterministic Puzzle Piece, But Overcomplicated If Elaborate Self-Evolving System

You are right on both counts:

1. **Self-evolving systems that produce 100k logs about nothing are FOMO/want, not need.** Paper 2 §5.2.1 Harness-Level Evaluation warns: most evaluations measure end-task success, conflating model, harness quality, tool reliability, feedback informativeness, environment difficulty. If tests are weak or log parsing flawed, reported improvements may not reflect robust long-horizon behavior. Many self-evolving claims are anecdotal debugging, not comparative diagnosis with deep telemetry. Your instinct "молча подумать и сделать одну задачу вместе с агентом на пару" is exactly what L2MAC simple chain + sophisticated state management does, not elaborate DAG.

2. **Your subagent idea as cheap isolated puzzle piece is valid and high ROI, not overcomplicated, if scoped tightly.** This is Pattern 1 Single-shot from 4 subagent patterns 2026: stateless, no course-correct, ideal for code review, file analysis, research lookups, test generation, structured websearch, simple function. It works on cheaper models too. The catch you cannot course-correct mid-task, you find out when result comes home — but for simple deterministic tasks, you don't need to.

**Key distinction:**

- **Overcomplicated (FOMO):** Main spawns 2-3 parallel subagents each with own worktree, PTY pool maxSize 3, fleet, async tree, search-based planning MCTS over reasoning paths, Meta-Harness searching over harness code via filesystem, Evolution Agent autonomously mutating harness, self-evolving without regression. That's want, occupies mind, produces 100k logs.

- **Not overcomplicated (Need):** Main stateful pair programming partner (like Cursor Tab + Composer, stateful PTY, instant grep, tool batching) that has 180k context, and sometimes needs a cheap missing piece: structured websearch returning JSON list of 5 URLs with snippets, or simple function `def parse_auth_header(...)` with tests. Spawning a stateless subagent with clean slate ~1k context, restricted tools [web_search] or [write_file + bash], capped output 8000→500 preview, JSON envelope, returns 500 tokens, saves main from growing 180k→200k and overflowing. That's measurable saving.

**Measurable ROI of Cheap Subagent:**

Scenario: main loop 180k tokens in context window (near limit), needs to do websearch "Stripe API v12 subscription cancellation".

- Option A (no subagent): main does `fs_web_search` tool call → tool result 5k tokens added to main context → 185k → next turn 185k input, costs $X, risks context overflow → needs compaction LLM summary $Y.
- Option B (cheap stateless subagent): main spawns subagent with task "websearch Stripe API v12 subscription cancellation, return JSON {urls, snippets, summary}" — subagent context clean slate 1k, does websearch 5k, returns JSON 500 tokens via envelope. Main sees only 500 tokens summary, not 5k. Main context stays 180.5k, not 185k. Saves $ and prevents compaction.

**Calculation:** If main 180k input, output 1k, at $5/M input, $15/M output (GPT-5 pricing), one call costs ~$0.90 input + $0.015 output. Adding 5k websearch result makes next call $0.925 input. With subagent, subagent call costs 1k input + 5k tool result + 0.5k output = ~6.5k tokens ~$0.04, plus main 0.5k extra = $0.0025, total $0.0425 vs $0.025 extra if done in main but with context bloat risk. More importantly, avoids compaction LLM call which costs $0.10-0.50 and risks quality degradation.

**Conclusion:** Cheap subagent saves money and prevents context overflow, but only if subagent is truly cheap, deterministic, isolated, with restricted tools and structured output, not another full agent loop with 180k context.

## What Senior Teams Do

From Paper 2 and production harnesses:

- **Cursor, Claude Code, OpenHands, SWE-agent:** Main is pair programming partner, not autonomous. They have checkpoint, undo, diff review, human-in-loop approval gates. Cursor Tab acceptance metrics: 28% higher acceptance with 21% fewer suggestions — Tab learns to suggest less, so suggestions you do see worth keeping. That's pair over autonomy.

- **L2MAC:** Simple sequential chain with sophisticated state management (Control Unit resets context window between steps, provides targeted summary Mrs, stores partial results to file store D). Not elaborate topology.

- **SoA:** Agent pool scaling — spawns more agents as task complexity grows, each bounded context, but global consistency sacrificed. SoA is workaround when shared representation too large to fit in one window, not default.

**Senior principle:** Use subagents only when task is embarrassingly parallel with non-overlapping write_sets and can be solved with <600 tokens tool defs, not when it needs 180k context. Researcher needing 180k context should not be subagent, should be main.

## Proposal: Do It, But Limited Scope — Pair over Autonomy

**Do:**

- Main stateful PTY via PtyPool in-process (Phase 3), holds cwd/env/venv, does pair programming: reads files via instant_grep, edits, runs pytest, shows diffs.
- Subagent cheap stateless for two use cases only:
  1. **Structured websearch:** tools=[web_search], input: query, output: JSON {urls, snippets, summary, 5 sources}. Clean slate 1k context, no repo access.
  2. **Simple function:** tools=[write_file, bash], input: function spec, output: JSON {file_path, test_result PASS/FAIL, summary}. Clean slate, scrubbed env, no access to main's 180k context.

- Limit: 1 subagent at a time v0.1, max 3 spawns per session via RuntimeLimits, filtered history (task + relevant files from instant_grep, not full parent), JSON envelope full schema validated, artifact write .fa/subagents/<id>.json, main aggregates into task_worklog.md.

**Don't:**

- Don't add parallel subagents tree (Cursor 3.2 /multitask with 8 worktrees) now — that's topology complexity symptom of missing formal substrate (instant grep + verification sensors already solve researcher/verifier without subagent).
- Don't add self-evolving harness, search-based planning MCTS, Meta-Harness searching over harness code, Evolution Agent autonomous mutation — that's FOMO want, occupies mind, produces 100k logs about nothing. Defer until eval-harness proves simple chain insufficient.

**Add Principle to Project:**

Per your earlier question "Что если ее закрепить рядом с axes/pillars?" — add two principles:

**§1.2.6 Substrate Formality Principle** (already proposed): Topology complexity is symptom of missing formal substrate. Prefer formal blackboard + instant grep + verification sensors over parallel agents.

**§1.2.7 Pair over Autonomy Principle — NEW, from this philosophy:**

> **Principle:** Agent should work as pair programming partner, not autonomous system. Optimize for effective pair work: checkpoint, undo, diff review, human-in-loop approval gates, observable failures, not for autonomous hours. Subagents only as cheap deterministic puzzle piece providers (structured websearch, simple function) when main context is near limit (180k), not as autonomous workers. Measure pair productivity, not autonomous hours.
>
> **Invariants:**
> - I-7.1 Main has 180k context, subagent has clean slate ~1k, never inherits full parent history
> - I-7.2 Subagent task must be solvable with <600 tokens tool defs and <8000 chars output, returns structured JSON, not raw logs
> - I-7.3 Subagent is stateless, scrubbed env, no access to main's PTY state, isolated via WorktreeManager SharedDir v0.1
> - I-7.4 No self-evolving harness without eval-harness proving simple chain insufficient and human approval for permission boundary changes

**This addresses your neurodivergent concern:** Pair work is predictable, controllable, measurable (diff accepted, test PASS), not 100k logs about nothing.

## Concrete Implementation for Cheap Subagent (Achievable)

```python
# src/fa/inner_loop/subagent_runner.py — already skeleton, need to restrict to 2 use cases

# Use case 1: Structured websearch
def spawn_websearch_subagent(query: str) -> SubagentEnvelope:
    # Clean slate, no repo access, tools=[web_search] only
    # Task: "websearch Stripe API v12 subscription cancellation, return JSON {urls, snippets, summary}"
    # Output: JSON 500 tokens
    pass


# Use case 2: Simple function
def spawn_function_subagent(spec: str) -> SubagentEnvelope:
    # Clean slate, tools=[write_file, bash], scrubbed env, no main PTY state
    # Task: "Write simple function def parse_auth_header(s: str) -> dict with tests, return JSON {file_path, test_result}"
    # Output: JSON with file_path and test_result PASS/FAIL
    pass


# Main loop at 180k context:
if token_usage > 150000 and needs_websearch:
    # Spawn cheap subagent instead of doing websearch in main loop
    envelope = spawn_websearch_subagent("Stripe API v12 subscription cancellation")
    # Main sees only envelope.summary 500 tokens, not 5k raw search results
    # Main context stays 180.5k, not 185k
    task_worklog.md += f"Websearch result: {envelope.summary}\n"
```

**Measurement:**

- Baseline: main does websearch in 180k context → next turn 185k input, compaction needed?
- With subagent: main 180k + 0.5k summary, subagent 1k + 5k + 0.5k = 6.5k separate, no compaction. Token saving and prevents overflow.

## Final Answer: Сделаем Так, Но Ограниченно

**Да, сделаем так, но не overcomplicated:**

- Main stateful pair partner with PTY, instant grep, tool batching, cap 8000, prompt caching per role, blackboard with read_set/write_set — keep simple chain, not elaborate DAG
- Subagent cheap stateless only for 2 use cases: structured websearch and simple function, 1 at a time, clean slate ~1k, restricted tools, JSON envelope, filtered history, scrubbed env, isolated via SharedDirWorktreeManager
- No parallel subagents tree, no self-evolving harness, no search-based planning MCTS now — defer until eval-harness proves simple chain insufficient and you have concrete practice-formed task where parallel would help

**This is not FOMO, it's need:** Solves concrete problem main 180k context near limit, cheap deterministic puzzle piece saves tokens and prevents compaction.

**Reduction:** Remove from plan Phase 4 Remote Runtime Extraction and parallel 2-3 subagents — keep Phase 0 quick-win, Phase 0.5 blackboard + telemetry, Phase 1 foundation, Phase 2 batching+FTS5, Phase 3 in-process PTY pool with 1 subagent limit. That's it. No fleet, no async tree.

**Next:** Update implementation plan v2 to reflect Pair over Autonomy principle and limit subagents to cheap deterministic 2 use cases.
