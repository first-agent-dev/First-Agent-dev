---
title: "ADR-13/14 Implementation Plan v3 — Reduced Surface, Pair over Autonomy, Formal Substrate"
source:
  - "knowledge/adr/ADR-13-stateful-bash-eventstream-runtime.md"
  - "knowledge/adr/ADR-14-multitask-subagents-worktree-isolation.md"
  - "knowledge/research/substrate-formalization-and-reduction.md"
  - "knowledge/research/philosophy-subagents-cheap-deterministic.md"
  - "knowledge/project-overview.md §1.2.6 Substrate Formality, §1.2.7 Pair over Autonomy"
  - "https://github.com/All-Hands-AI/OpenHands/pull/4881"
  - "https://github.com/anomalyco/opencode/issues/6488"
  - "https://arxiv.org/html/2603.05344v2"
compiled: "2026-07-11"
chain_of_custody: "This v3 supersedes v1 and v2, self-sufficient for implementation without needing v2 context. It amends previous plans after reduction analysis: 30+ components N^2 breaking point, topology complexity symptom of missing formal substrate, pair over autonomy philosophy. All decisions from Q&A rounds incorporated."
goal_lens: "Produce final production-ready plan ready for PR, with minimal surface, pair over autonomy, formal blackboard, minimal structured telemetry, 1 cheap stateless subagent for 2 use cases (structured websearch, simple function), measurable Pillar 3 KPI, ready for new session agent to implement without re-reading all history. This file is self-sufficient, no need to read v2."
tier: stable
---

> **Status:** active v3, **self-sufficient, supersedes v1 and v2**, no need to read v2. Reduces surface from 6 phases to 5 phases total (0, 0.5, 1, 2, 3) — 4 main after quick-win, closer to pair philosophy.
> **Use this file alone for implementation, plus next-session-context-bundle.md as entry point.**

## Why v3 Reduction

**v2 had 30+ components interacting per session:** artefacts, traces, anti-patterns, research, adr, memory tiers, prompts, skills, guardrails at all stages, roles, tool schemas, blackboard, telemetry, FTS index, worktrees, PtyPool, subagent envelopes, task worklogs, FlowState, EvalReport, PromptComposer, FeatureFlags. Adding new component (instant_grep) required updating 5-6 other components — breaking point.

**Senior eng insight from Paper 2 §4.4:** Topology complexity inversely correlates with harness-state formality. When substrate is formally represented and queryable, agents coordinate via simple transparent protocols. L2MAC uses simple sequential chain with sophisticated state management, not elaborate adaptive topologies (dynamic DAGs, fleet). Elaborate topology is symptom of missing formal substrate.

**User philosophy:** Self-evolving systems that produce 100k logs about nothing are want/FOMO, occupy neurodivergent minds. Enough to silently think and do one task together with agent as pair. Don't believe in smart autonomous systems now. Subagent idea is solution to problem not yet formed by practice, but can imagine scenario where main stateful with 180k context chain growing, sometimes launches external agent with isolated context which very cheaply and deterministically brings missing puzzle piece, e.g., structured websearch or simple function.

**Conclusion for v3:** Keep main as pair programming partner (stateful PTY, instant grep, tool batching, cap 8000, prompt caching per role, blackboard), add cheap stateless subagent only for 2 use cases (structured websearch, simple function), 1 at a time, clean slate ~1k, restricted tools, JSON envelope. Remove parallel subagents tree 8 worktrees, fleet, async tree, search-based MCTS, self-evolving harness — defer until eval-harness proves simple chain insufficient and practice-formed task emerges.

**New principles added per user approval:**

- §1.2.6 Substrate Formality Principle: Topology complexity is symptom of missing formal substrate. Formal substrate before topology complexity. Invariants I-6.1..I-6.4.
- §1.2.7 Pair over Autonomy Principle: Agent should work as pair programming partner, not autonomous system. Main 180k context, subagent clean slate ~1k, never inherits full parent history, task solvable with <600 tokens tool defs and <8000 output, structured JSON, stateless scrubbed env, isolated.

## Revised Phases (Reduced, 4 Main After Quick-Win)

### Phase 0 — Quick-win + Observability Foundation + Pair Tools (0.5 day)

**Goal:** Fix biggest token waste without PTY, add warning, cap output, observability tools, checkpoint/undo/diff for pair work.

**Deliverables:**
- Cap output 8000 in projection.py with artifact_id + 500-char preview + ArtifactStore content-addressed
- Warning in fs.run_bash description: "STATEFUL for main (via PtyPool), stateless for cheap subagents (websearch, simple function) output capped 8000"
- fs.chronicle_search, fs.usage, fs.list_tasks skeletons (read EventLog, no new deps)
- fs.send_ctrl_c, fs.checkpoint, fs.undo, fs.diff skeletons (pair over autonomy) — checkpoint creates git commit/stash, undo git reset --hard HEAD~1, diff git diff
- Update llms.txt, DIGEST.md, HANDOFF.md§Next per MAINTENANCE.md

**Acceptance:**
- Tool descriptions mention stateful + cap + pair tools
- Output >8000 truncated with artifact_id + preview
- chronicle_search returns timeline entries
- checkpoint creates commit, undo restores, diff returns structured diff
- No new external deps, thread-safe, feature flagged

**Senior check:** No new external deps, deterministic Python functions, pass minimalism Q4.

### Phase 0.5 — Formal Blackboard + Structured Telemetry (1.5 days) — High ROI, Reduces Complexity

**Goal:** Land typed blackboard with content hashes + transactional semantics and minimal structured telemetry, enabling governed mutation and harness-level evaluation beyond final task success. This reduces complexity long-term and fixes root cause of worktree bugs and 124 steps thrashing without adding more tools.

**Subtasks 0.5a Blackboard:**

- File `src/fa/blackboard/blackboard.py` with BlackboardEntry id, type, content_hash sha256, toolchain_digest (python version, model id), schema_version, parent_id, read_set, write_set, assumptions, version_dependencies (base_commit, llms.txt hash), timestamp, payload
- Methods write append-only never overwrite content-addressed, read, query(type,key) queryable, detect_conflict where read_set overlaps write_set of concurrent entry or assumption violated
- Store `.fa/blackboard/blackboard.jsonl` append-only, Control Unit managing reads/writes, each entry stamped with digests for reproducibility (MACOG blackboard)
- Integration: fs.write_file declares read_set (files read via instant_grep), write_set, assumptions (base commit git rev-parse HEAD, llms.txt hash), version_dependencies; WorktreeManager declares transaction read_set/write_set; Metrics merge success, belief divergence |Bk-Sk|
- Defensive: thread-safe with Lock, graceful degradation WARNING not crash, backward compatible additive

**Subtasks 0.5b Telemetry:**

- File `src/fa/telemetry/telemetry.py` TelemetryEvent structured: run_id, turn, prompt_tokens, completion_tokens, cost_usd, model_id, tool_name, tool_args sanitized no secrets, permission_tier, edited_files, test_result PASS/FAIL, cache_hit, latency_ms, branch_decision, rejected_alternatives, human_approval, artifact_id (reference to full output offloaded, not raw log)
- Write to `.fa/telemetry/telemetry.jsonl` one line per tool call <1k chars, full outputs offloaded to ArtifactStore, active context only 500-char preview + artifact_id, not 100k raw logs
- Change contract template in `knowledge/skills/skill-writing/SKILL.md`: which component modified, failure mode targeted, improvement predicted, invariants preserved, evaluation that can falsify, rollback plan, HITL required for permission boundaries

**Acceptance Phase 0.5:**
- Blackboard append-only, content-hashed, queryable, detects conflict when read_set overlaps write_set of concurrent entry → returns fail code conflict_detected, no silent overwrite
- Telemetry structured <1k per line, artifact_id present, no 100k drowning, sanitizes secrets, active context compact summaries + artifact_id
- Change contract template exists
- Tests: test_blackboard_conflict, test_telemetry_structured
- Update llms.txt, DIGEST.md, HANDOFF.md

### Phase 1 — Foundation Abstractions (1 day)

**Goal:** Land WorktreeManager ABC with defensive checks + sanitized branch, Profiles dict dynamic toolset with globs, SubagentEnvelope full schema validated, PromptComposer cache-key per role with stable hash + agents_map + skills hash, FeatureFlags, Transaction object.

**Subtasks:**
- WorktreeManager ABC + SharedDirWorktreeManager (1 subagent limit, sequential single-shot, not parallel, 100% stable) + IsolatedWorktreeManager future with sanitized branch `re.sub(r'[^a-zA-Z0-9-_]', '-', task_id)[:50]`, defensive asserts path exists + is_dir + worktree list contains + branch already checked out fail-fast, CWD lock, cleanup assert not exists + prune
- PROFILES dict: researcher [glob,grep,read,instant_grep] 600 tokens, verifier [bash] 200 tokens, code-reviewer [read,grep], implementer [read,write,edit,bash,glob,grep,instant_grep], planner [glob,grep,read,instant_grep] — dynamic toolset, cache-key = role_id + hash(names+schemas) + hash(agents_map) + hash(skills), exclude description with date
- SubagentEnvelope full schema Goal, Verification, Risks, token_usage, duration_ms, next_action, fastjsonschema validator cached at module load, artifact write .fa/subagents/<id>.json
- PromptComposer with cacheable split BASE+map+tool defs per role + non-cacheable task+memory_summary+observations, per role cache-key, to_anthropic cache_control ephemeral, to_openai prompt_cache_key retention 1h via LiteLLM
- FeatureFlags loader from ~/.fa/config.yaml with anchored defaults, RuntimeLimits extended max_subagent_spawns_per_session=3
- Transaction object read_set/write_set accumulated during execution, not just declared upfront, add_read/add_write methods via SessionState
- Skill globs: extend SKILL.md frontmatter globs, alwaysApply false, loader should_load_skill checks globs matches current_files or triggers verb matches

**Acceptance:**
- SharedDir returns session_root, Isolated creates worktree in temp dir with defensive asserts passing
- PROFILES researcher 600 vs full 3000
- SubagentEnvelope valid JSON round-trip
- Cache keys differ per role, no date in hash, include skills hash
- Branch sanitization "verify-auth login" → "verify-auth-login"
- Transaction read_set accumulated during execution

### Phase 2 — Tool Batching + Instant Grep FTS5 (1 day)

**Goal:** Parallel read-only + instant grep trigram with incremental index and stale cleanup, plus cheap deterministic subagent minimal system prompt.

**Subtasks:**
- Tool batching: group read-only (glob,grep,read,instant_grep) → ThreadPoolExecutor max 5 parallel, writes sequential, log write sequential with Lock, EventLog thread-safe, ToolPermission read vs workspace to decide parallelizable, plus IntentGuard effect REPO_READ → parallelizable
- InstantGrepIndex FTS5 trigram: CREATE VIRTUAL TABLE USING fts5(path, content, tokenize='trigram'), DELETE then INSERT, track mtime file→last indexed, delete stale entries where file not exists, clear and reindex if DB older than 24h, fallback porter with WARNING log, exclude .fa/, node_modules/, .venv/, __pycache__/, .git/, sessions/, .gremlins_cache
- Tool fs.instant_grep handler using index, returns paths not content <50ms, substring search
- Subagent cheap deterministic minimal system prompt <500 tokens, not full BASE+map: websearch agent "You are websearch agent, tools=[web_search], input query, output JSON {urls, snippets, summary}" and function writer "You are function writer, tools=[write_file,bash], input spec, output JSON {file_path, test_result}"

**Acceptance:**
- 3 parallel reads <0.25s vs sequential 0.3s, EventLog paired rows intact
- instant_grep "auth" finds "Authentication" substring in <50ms
- Index incremental, stale cleanup works, excludes sessions/
- Subagent minimal prompt <500 tokens, not full BASE

### Phase 3 — EventStream Runtime In-Process PTY Pool + Subagent Runner + Eval-Harness (2-3 days) — Final Phase

**Goal:** Land PtyPool in-process with interface BashExecutor, no network yet, to prove concept and measure 124→40 steps, plus subagent runner cheap deterministic 2 use cases, plus mini eval-harness.

**Why in-process first per senior eng:** Big teams start simple, extract to service only when parallel need proven. Interface BashExecutor allows switch to remote later without changing callers. Direct FastAPI was user choice earlier, but for reduction we go back to in-process for v0.1 to keep surface minimal, pair over autonomy. Remote extraction deferred to future if Phase 3 shows instability or need 2-3 parallel proven — currently not needed for pair work.

**Subtasks:**

- PtyPool with shared libtmux.Server instance injected, not per session, LRU eviction + fail-fast PoolExhaustedError never reuse main, maxSize=2 (main+1 sub) for v0.1, sentinel |||FA_READY|||, ANSI strip, exit code parsing __FA_EXIT__:$? __FA_END__, fallback to pexpect if libtmux ImportError or which tmux None, log WARNING, DI via SessionState, no global singleton, thread-safe
- run_bash.py thin client depends on BashExecutor protocol, not concrete PtyPool, injected via SessionState, fallback to subprocess.run if pool not available with WARNING
- Dockerfile: apt-get install tmux, pip install libtmux, feature flag runtime.mode=in_process
- SubagentRunner scrubbed env extra_allow X_FA_PROXY_TOKEN foundation for future per-subagent random, filtered history (task + relevant files from instant_grep, not full parent 124 steps), JSON validation cached at module load, artifact write .fa/subagents/<id>.json, 1 subagent limit enforced via RuntimeLimits.max_subagent_spawns_per_session=3
- Task worklog.md Goal, Evidence, Steps, Verification aggregated from JSONs, for PR → PR body, not only pr.prepare
- Mini eval-harness 5 tasks, concrete repro fa run --role planner --task "Read repository and tell what you found", metrics median tokens/tool-calls/USD, before/after 124→30-40, trajectory efficiency, verification strength, state consistency, safety compliance, replayability (from open problem 5.2.1 Harness-Level Evaluation)
- Update DIGEST.md, HANDOFF.md, llms.txt BY-DEMAND INDEX per MAINTENANCE.md link integrity, markdown-link-check, no shell=True without # nosemgrep + ADR-6, no Level-0 TCB import external lib per ADR-11

**Acceptance:**

- cd /tmp && pwd persists across calls (second pwd returns /tmp)
- export FOO=bar + echo $FOO → bar
- ANSI stripped (ls --color=always no \x1b[)
- Ctrl+C interrupts sleep 10
- No global pool singleton, SessionState holds executor via DI, shared Server instance
- Fallback to pexpect when tmux missing logs WARNING
- Verifier subagent pytest returns JSON PASS/FAIL, main sees only summary 500 tokens, not 5k raw, context stays 180.5k not 185k
- Worklog contains Goal, Verification, Risks
- Baseline 124 steps documented, after target 30-40 measured, tokens ↓60%, tool-calls ↓50%
- Pair over Autonomy: checkpoint creates git commit/stash, undo restores, diff returns structured diff, human can interrupt, undo

**Removed from v2 (Reduction):**

- Phase 4 Remote Runtime Extraction FastAPI separate service — deferred until Phase 3 shows instability or need 2-3 parallel proven. Interface BashExecutor already allows switch via feature flag without changing callers, so no code wasted.
- Parallel 2-3 subagents tree, fleet, async tree, search-based planning MCTS, self-evolving harness, Evolution Agent autonomous — deferred until eval-harness proves simple chain insufficient and practice-formed task emerges. Keep 1 subagent limit.

**Count: 4 phases (0, 0.5, 1, 2, 3) actually 5 including 0.5, but 4 main after quick-win, instead of 6, less surface, closer to pair philosophy "молча подумать и сделать одну задачу вместе".**

## Risks and Mitigations Updated for Reduced Plan

- libtmux not available: Fallback pexpect with WARNING, not silent. Check shutil.which("tmux").
- FTS5 trigram not available: Fallback porter with WARNING, not silent.
- Branch already checked out: Fail-fast BranchAlreadyCheckedOutError with clear message and git worktree list details.
- Tool batching race: Read-only parallel, writes sequential, log write sequential with Lock.
- Cache-key contradiction: Solved by role_id + hash(names+schemas) + hash(agents_map) + hash(skills), exclude description with date.
- Blackboard stale: Before query, check mtime vs last indexed, reindex if changed, delete entries where file not exists.
- Transaction read_set incomplete: Accumulate during execution via add_read/add_write, not just declared upfront.
- Telemetry drowning: Structured <1k per line, offload full outputs to ArtifactStore, active context only 500-char preview + artifact_id.
- Subagent minimal prompt: <500 tokens, not full BASE, clean slate ~1k, restricted tools, JSON envelope.
- Pair over autonomy: checkpoint/undo/diff tools deterministic Python, not LLM, pass minimalism Q4.

## References Updated

- Paper 2 §4.4 Topology complexity vs formality, §5.2.4 Transactional Shared State, §5.2.1 Harness-Level Evaluation, §3.5 Deep Telemetry, §3.5.3 Governed Mutation, §5.1.1 Harness as Distillation Surface, §5.2.3 Self-Evolving without Regression
- OpenHands EventStream Runtime + PR #4881 libtmux
- OpenCode ShellPool #6488
- ArXiv 2603.05344 v2 staged compaction
- Prompt Caching Guide aioutlooks.com + litellm docs
- Blog.fsck.com July 5 2026 arbiter pattern verified
- Claude Code worktree bugs #55708 #47548 #31546
- User philosophy: pair over autonomy, 100k logs about nothing, enough to silently think and do one task together

