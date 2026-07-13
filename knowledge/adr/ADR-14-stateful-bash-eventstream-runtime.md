# ADR-13 — Stateful Bash via EventStream Runtime (FastAPI + PTY Pool)

- **Status:** proposed
- **Date:** 2026-07-11
- **Deciders:** owner + FA agent
- **Related:** ADR-6 (Sandbox), ADR-12 (Secret Isolation), ADR-11 (Authoring TCB), ADR-7 (Tool Registry), ADR-3/4 (Mechanical Wiki)

## Context

Current `fs.run_bash` = `subprocess.run(cwd=root, shell=True, capture_output=True, env=scrubbed)` stateless. Task "прочитай репозиторий и расскажи что нашел" → 124 steps → timeout, context accumulates. `cd`, `export`, `source .venv` do not persist. Agent not warned in tool description → hallucinations, token waste.

Production agents:
- OpenHands EventStream Runtime: Docker container runs FastAPI Action Execution Server with persistent tmux bash session, IPython kernel, browser. Backend sends `CmdRunAction` via REST, receives `CmdOutputObservation`. OpenHands PR #4881 replaced pexpect with libtmux for stability.
- OpenCode ShellPool #6488: Map<id, Session> maxSize=3, acquire/release, 97% reduction process count, completion via shell integration sequences.
- Cursor 3.2: PTY requires real TTY, solution tmux persistent session, 8 parallel agents each isolated git worktree, cloud VMs.
- Hermes: persistent_shell true by default for SSH backend, single bash -l alive via temp files.

Need stateful PTY for main agent planner-coder-eval workflow to reduce median tool-calls (Pillar 3).

Constraints:
- Zero-Trust TCB Level-0 stdlib-only kernel must stay stdlib-only (ADR-11). PTY manager must live in Level-1 inner_loop.
- IntentGuard (bashlex AST → BashIntentEffect) must stay BEFORE execution (ADR-10 I-1 single-source-of-truth classifier).
- Egress-Proxy already provides container separation (ADR-12). Keys live only in proxy container.
- Minimalism-first 4-question test + compliance-by-construction (project-overview §1.2, §1.2.5)

Research: knowledge/research/stateful-bash-pty-2026-07.md + final-review-gaps-high-roi-metaharnesses-july2026.md

## Options considered

### Option A — Fake Stateful (cwd/env dict)

- Pros: 0 dependencies, 1 day, no ADR amendment, solves 80% `cd` waste.
- Cons: Does not solve `source .venv`, `npm run dev &`, interactive prompts, ANSI handling.

### Option B — pexpect directly in coder_loop (Phase 2 originally)

- Pros: Pure Python 4.9.0, 200KB, no C deps, 2-3 days, passes Level-1 easily.
- Cons: PTY in same process as LLM loop, crash loses state, hanging processes, ANSI parsing fragile, hard to test without LLM.

### Option C — EventStream Runtime FastAPI + PTY Pool libtmux (chosen, direct)

- Pros: 
  - Stability: PTY pool lives in separate process/server, survives main crash, can kill/recreate hanging PTY without killing main loop (OpenHands pattern).
  - Testability: `curl -X POST http://fa-runtime:8001/execute -d '{"command":"cd /tmp && pwd"}'` unit testable.
  - Parallelism: Pool maxSize=3 acquire/release ready for 2-3 parallel subagents (Cursor 3.2 /multitask).
  - Security: Runtime server can enforce IntentGuard before PTY + per-subagent random token rewriting foundation for Gap 7 arbiter.
  - Observability: Server exposes /list, /read, /kill endpoints like opencode-pty.
- Cons: +FastAPI dependency, +libtmux + tmux binary in Dockerfile, ~500 LoC server, higher complexity than direct pexpect. Requires Docker network wiring between first-agent and fa-runtime-server or sidecar process.

## Decision

We will choose **Option C — EventStream Runtime FastAPI + PTY Pool libtmux**, directly target (skip pexpect phase per user decision 2026-07-11 direct_fastapi).

**Why:**

- User chose direct_fastapi in Q&A: libtmux more stable than pexpect (OpenHands moved pexpect → libtmux).
- Defensive worktree checks must be Tier 1 (external reviewer feedback) — runtime server centralizes defensive checks.
- Enables future Cursor-like 8 parallel agents, background dev server `npm run dev &` + browser QA (Devin pattern), and background task tools `pty_read/list/kill`.

**Architecture:**

```
Host: fa run
  → first-agent container: coder_loop.py thin client
     ↓ HTTP POST http://fa-runtime:8001/execute {session_id: main, command: cd /tmp && pwd, timeout:30}
  → fa-runtime-server (FastAPI, port 8001) inside same Docker network
     ├── PtyPool Map<id,PtySession> maxSize=3 (libtmux Server, sentinel |||FA_READY|||)
     ├── ANSI stripper regex \x1b\[[0-9;]*[mGJK]
     ├── WorktreeManager abstraction (SharedDir v0.1 → Isolated future)
     └── EventLog writer (paired tool_call/tool_result rows)

  → fa-egress-proxy (existing): injects real Authorization, allowlist, per-subagent random token foundation
```

**Prompt Caching Split Universal (Gap 2 fix, part of this ADR):**

- Cache-key = role_id + hash(tool_defs), not global — solves internal contradiction flagged by external reviewer: restricted toolset per role dynamic → TOOL_DEFS not identical across roles.
- Implementation: `src/fa/inner_loop/prompt_composer.py` PromptParts(cacheable=[BASE, AGENTS.md map, tool defs for that role], non_cacheable=[task, memory_summary, observations])
- To Anthropic: add `cache_control: {type: ephemeral}` markers, 4 explicit +1 auto, min 1024-4096, 90% off read.
- To OpenAI: automatic >1024, plus `prompt_cache_key: f"fa-{role_id}-{hash}"` + `prompt_cache_retention: "1h"` via LiteLLM extra_body.

**Progressive Context Compaction Foundation (Gap 3, foundation for ADR-15):**

- Stage 1 only now: warning at 70% token usage / context_limit + tool output offload >8000 chars → ArtifactStore content-addressed + 500-char preview retained (as per ArXiv 2603.05344 table Tool output offload 8000 chars).
- Full 5-stage (warning 70%, observation masking 80%, fast pruning 85%, aggressive masking 90%, full LLM compaction 99%) → separate ADR-15.

**Tool Call Batching Parallel (Gap 8):**

- In `loop.py`, group calls: read-only (glob, grep, read, instant_grep, list_files) → ThreadPoolExecutor max 5 parallel, workspace writes (write_file, run_bash) sequential.

**Defensive Worktree Checks (Gap 6 raised to Tier 1):**

- After `git worktree add`, assert path exists + is_dir + `git worktree list --porcelain` contains new path, else fail clear error (not silent fallback as Claude Code bug #47548).
- Before add, check if branch already checked out elsewhere → fail fast "branch already checked out at /other".
- CWD lock: subagent cwd must be worktree_path.

## Consequences

- Positive:
  - Fixes cd/venv persistence, reduces median tool-calls: baseline 124 steps "прочитай репозиторий" → target 30-40 steps.
  - Enables background dev server + browser QA (Devin pattern).
  - Testable via curl, parallel subagents ready.
  - Token efficient via caching split + batching: immediate 60-90% cost saving.
  - Defensive checks prevent silent corruption of parent repo (validates external reviewer feedback).
  - Compliance-by-construction: IntentGuard before PTY, failure observable via structured WARNING on timeout.

- Negative:
  - +FastAPI, libtmux, tmux binary in Dockerfile, ~500 LoC server, higher complexity.
  - Requires Docker network wiring, extra container or sidecar process.

- Follow-up unlocks:
  - ADR-14 Multitask Subagents (PROFILES, instant grep, JSON envelope).
  - ADR-15 Full 5-stage compaction.
  - ADR-12 amendment per-subagent random token rewriting (Gap 7).

## References

- OpenHands EventStream Runtime issue 2404 + PR #4881 Replace pexpect with libtmux
- OpenCode ShellPool issue #6488, ShellPool maxSize=3 acquire/release 97% reduction
- pi-persistent-term table bash vs run_in_terminal vs monitor_process background=true
- Hermes persistent_shell true for SSH backend
- Claude Code PTY feature #9881 + worktree isolation bugs #55708, #47548, #31546
- Cursor 3.2 /multitask async subagents tree, 8 parallel worktree isolation
- ArXiv 2603.05344 Building Effective AI Coding Agents for the Terminal: Staged Context Management warning 70/80/85/90/99%, tool output offload 8000 chars
- Provider caching comparison aioutlooks.com/prompt-caching-guide + litellm docs + lubulabs.com
- Blog.fsck.com 2026-07-05 new patterns Security Arbiter + MITM proxy random rewriting
- final-review-gaps-high-roi-metaharnesses-july2026.md Gap 2,3,6,8

