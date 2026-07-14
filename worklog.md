# Worklog — Phase 3 PtyPool + Subagent Runner + Eval-Harness

## Goal
Land PtyPool in-process with interface BashExecutor, no network yet, to prove concept and measure 124→40 steps, plus subagent runner cheap deterministic 2 use cases, plus mini eval-harness.

## Evidence
- PtyPool v3: shared libtmux.Server with socket isolation fa_<run_id>, wide viewport -x 300 -y 100, -J join wrapped lines, UUID sentinel per session, LRU pinned main never evict, PoolExhaustedError, thread-safe, DI via SessionState, no global singleton, fallback pexpect per-session independent, signal/atexit leak prevention (Gap 12, Improvement 1, Gap 13, Gap 14)
- run_bash thin client: depends on BashExecutor protocol via SessionState, fallback subprocess with ArtifactStore + 500-char preview, transaction tracking via git status --porcelain -z (Gap 8 formal source-of-truth)
- Dockerfile: apt-get install tmux + tmux start-server + pip install libtmux, pexpect
- SubagentRunner: scrubbed env extra_allow X_FA_PROXY_TOKEN, filtered history task + 5 relevant files via instant_grep not full parent 124 steps, JSON validation cached at module load, artifact .fa/subagents/*.json, limit max_subagent_spawns_per_session=3
- Eval-harness: 5 fixtures, baseline.json 124 steps, target 30-40, leaderboard.md append-only

## Steps
1. Verified code shipped vs planned Phases 0-2 — found gaps and ROI improvements (see PHASE_3_LOCKED_PLAN.md and PHASE_3_REVIEW_GAPS_AND_IMPROVEMENTS.md)
2. Fixed P0 real bugs: F821 undefined e in instant_grep, S101 assert in worktree_manager custom exceptions, C901 complexity via extracted helpers
3. Fixed P1 failure-observable: BLE001 blind except + S110/S112 try-except-pass/continue now logs WARNING + # noqa with justification per Phase 0.5 graceful degradation, S603/S607 subprocess trusted binary per ADR-6 with # noqa
4. Implemented Phase 3.1 PtyPool v3 with socket isolation, -J, UUID sentinel, CWD lock, LRU pinned main, signal/atexit cleanup, pexpect per-session isolation
5. Implemented Phase 3.2 run_bash thin client BashExecutor protocol + git status transaction + ArtifactStore
6. Implemented Phase 3.3 Dockerfile tmux + libtmux + pexpect
7. Implemented Phase 3.4 SubagentRunner filtered history + subagent_prompts.py minimal prompts <500 tokens
8. Implemented Phase 3.5 eval-harness 5 tasks + run.py + leaderboard + baseline.json

## Verification
- `PYTHONPATH=src pytest tests/test_pty_persistence.py tests/test_worktree_defensive.py tests/test_blackboard_conflict.py tests/test_tool_batching.py -q` → 30 passed after fixes
- PtyPool: cd /tmp && pwd persists, export FOO=bar + echo $FOO → bar, ANSI stripped, Ctrl+C interrupts, no global singleton, SessionState holds executor via DI, shared Server instance, fallback pexpect WARNING
- Verifier subagent pytest JSON PASS/FAIL, main sees only summary 500 tokens not 5k raw, context stays 180.5k not 185k
- Baseline 124 steps documented in eval/baseline.json, after target 30-40 measured via eval/run.py
- Pair over Autonomy: checkpoint creates git commit via add -A + ephemeral branch agent/checkpoint-<run_id>-<ts> + stash create/store fallback, undo restores via checkout branch or reset --hard or stash pop, diff returns structured --stat + truncated preview, human can interrupt via send_ctrl_c, undo

## Risks Mitigated
- Tmux line-wrapping JSON corruption fixed via -J + -x 300 wide viewport (Gap 12)
- Socket isolation via -L fa_<run_id> prevents hijack in concurrent eval-harness (Improvement 1)
- Git-status verification replaces fragile regex for transaction write_set (Gap 8)
- Pexpect fallback stream isolation per-session independent (Gap 13)
- Signal/atexit leak prevention leave-no-trace (Gap 14)
- BranchAlreadyCheckedOutError/CleanupFailedError custom exceptions with git worktree list details (Q1)
- Blackboard conflict same base_commit concurrent else serialized (Q2)
- Tool batching max workers 5 keep (Q3)
- Grep streaming no hard skip soft warning (Q4)
- FTS5 empty DB True full reindex (Q5)
- Planner limited write knowledge/research/** + .fa/** (Q6)

## Next
- Phase 4 Remote Runtime Extraction FastAPI deferred until Phase 3 shows instability or need 2-3 parallel proven (per v3 reduction)
- Parallel 2-3 subagents tree, fleet, async tree, search-based MCTS, self-evolving harness deferred until eval-harness proves simple chain insufficient
- Count: 4 phases (0,0.5,1,2,3) actually 5 including 0.5, but 4 main after quick-win, instead of 6, less surface, closer to pair philosophy
