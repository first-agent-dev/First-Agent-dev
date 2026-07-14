# Phase 3 Locked Plan — In-Process PtyPool + BashExecutor Thin Client + Subagent Runner + Eval-Harness

**Date:** 2026-07-13 locked
**Branch base:** `substrate` latest 91686a9 (Phase 0-2 shipped with fixes: glob senior refactor --cached --others --exclude-standard, grep streaming, instant_grep F821 fixed, fts_index patterns fixed, blackboard Q2 linear frontier policy, telemetry valid JSON, worktree SharedDir primary + Isolated kept for tests with custom BranchAlreadyCheckedOutError/CleanupFailedError, pair_tools checkpoint git add -A + ephemeral branch agent/checkpoint-<run_id>-<ts>, loop Hermes pattern NEVER_PARALLEL/PARALLEL_SAFE/PATH_SCOPED, profiles planner limited write knowledge/research/** + .fa/**)
**Goal lens v3:** Minimal surface, pair over autonomy, formal blackboard, minimal structured telemetry, 1 cheap stateless subagent, measurable Pillar 3 KPI, ready for new session agent without re-reading history. Self-sufficient.

---

## What Ideas We Implementing (Locked for Phase 3)

### From Original v3 Plan

1. **PtyPool In-Process with Shared Server** — No network yet, interface BashExecutor allows switch to remote later. Big teams start simple, extract to service only when parallel need proven per senior eng.
2. **run_bash Thin Client Depends on BashExecutor Protocol** — Not concrete PtyPool, injected via SessionState, fallback subprocess.run with WARNING.
3. **Dockerfile + Feature Flag** — apt-get install tmux, pip install libtmux, runtime.mode=in_process
4. **SubagentRunner Scrubbed Env + Filtered History + JSON Validation** — extra_allow X_FA_PROXY_TOKEN foundation per-subagent random, filtered history task + relevant files via instant_grep not full parent 124 steps, fastjsonschema cached at module load, artifact .fa/subagents/.json, limit max_subagent_spawns_per_session=3
5. **Worklog.md + Eval-Harness 5 Tasks** — Goal, Evidence, Steps, Verification aggregated from JSONs for PR body, mini eval-harness concrete repro `fa run --role planner --task "Read repository and tell what you found"`, metrics median tokens/tool-calls/USD, before/after 124→30-40, trajectory efficiency, verification strength, state consistency, safety compliance, replayability (open problem 5.2.1)

### From Additional Rigorous Review (Other Agent + Our Review)

6. **TMux Line-Wrapping & JSON Corruption Fix (Gap 12)** — By default tmux auto-wraps lines, capture-pane retrieves exactly as displayed, inserts hard newline inside JSON envelopes → JSONDecodeError. Fix: `-J` join wrapped lines + preserve trailing spaces + wide virtual viewport `-x 300` per `man tmux` capture-pane -J. Aligns §1.2.6 Substrate Formality formal representation must not be mangled by display viewport.

7. **TMux Socket Isolation (Improvement 1)** — Default socket `/tmp/tmux-UID/default` shared across concurrent agent sessions, evals, CI checks → one run hijacks/kills panes of other run if same session_id `main`. Fix: `-L socket-name` allows several independent tmux servers, libtmux.Server(socket_name='mysocket') == `tmux -L mysocket` per libtmux quickstart. Use unique run_id: `fa_<run_id>`. Aligns §1.2.7 Pair over Autonomy clean localized boundaries.

8. **Dynamic Git-Status Verification (Gap 8) — Replace regex parsing bash commands** — Regex for `>` `>>` fails for `python -c`, `sed -i`, `rsync`, binary scripts → silent Blackboard out-of-sync. Standard practice: `git status --porcelain -z` <2ms machine-readable 100% accurate, plus `-z` NUL-delimited safe for pathological filenames (spaces, newlines, quotes). Aligns §1.2.6 formal source-of-truth for transaction diffs rather than brittle heuristics.

9. **Pexpect Fallback Stream Isolation (Gap 13)** — pexpect single-stream sequential, if try concurrent subagent using same global fallback instance, stdin/stdout interleave corrupting. Fix: PtyPool sessions OrderedDict each PtySession has own _fallback pexpect.spawn per session_id, thread-safe lock around sessions dict, LRU.

10. **Signal/Atexit TMux Leak Prevention (Gap 14) — Leave-No-Trace Principle** — PtyPool in-process, if parent python crashes/killed/CI timeout, tmux server + sub-shells left as zombies consuming PTYs. Fix: signal trap handlers SIGTERM, SIGINT + atexit cleanup cascade `tmux kill-session` + `kill-server` for isolated socket, per senior daemon-less runner architecture.

### From Compaction Research (Stage 1-2 extra)

11. **Constraint Pinning 47 tokens <0.5%** — Governance Decay paper: compaction raises violation 0→30% up to 59%, fixed by PinnedBuffer AGENTS.md + llms.txt + custom profile exempt re-injected verbatim, integrity-checked. For Phase 3 PtyPool will not yet have compaction, but eval-harness should include ConstraintRot-like fixture.

12. **Prompt Caching Anchoring + ContextBudget** — Claude 94% hit rate, need cache_control breakpoint end system prompt + tool defs + compaction block separately, plus KV-stable snapshot refresh only on session_before_compact + long_term write. ContextBudget WARN 70% HARD 90% banner + inline marker + diff view.

---

## How Are We Doing It — Method, Verifiable Steps

**Overall method: In-process first, interface segregation, DI, no global singleton, thread-safe, graceful degradation.**

**Phase 3.1 PtyPool:**

- Shared Server injection: SessionState holds `server: libtmux.Server | None` created once per session_root via `libtmux.Server(socket_name=f"fa_{run_id}")` where run_id = `run-{uuid[:8]}` from SessionState.run_id. PtyPool gets injected server, not create new per PtyPool. No global singleton, DI via SessionState. If `shutil.which("tmux") is None` or ImportError libtmux → fallback pexpect with WARNING.
- Wide viewport + -J: `server.new_session(session_name=f"fa_{session_id}", x=300, y=100, attach=False, start_directory=str(cwd))` + `pane.cmd("capture-pane", "-p", "-J", "-S", "-100", "-E", "-")` to join wrapped lines.
- UUID sentinel per session: `sentinel = f"FA_READY_{session_id}_{uuid.uuid4().hex[:6]}"` + `FA_EXIT_{uuid}` to avoid collision if command output contains sentinel string.
- LRU + pinned main: `self.sessions: OrderedDict[str, PtySession]`, `max_size=2` = main pinned + 1 LRU sub slot. `acquire(session_id)`: if session_id in sessions move_to_end, return. If len >= max_size: if session_id != "main" and "main" in sessions and len==max_size, evict LRU sub (not main) — find first key != "main" from OrderedDict start. If trying to acquire 3rd distinct after main+1 sub already, evict LRU sub, not fail. PoolExhaustedError only when trying to acquire same session_id that is currently locked? Or when maxSize=1 and main present and trying sub? Define: For v0.1, maxSize=2, main pinned, LRU eviction for sub, no PoolExhaustedError yet. PoolExhaustedError reserved for future maxSize=1 or when trying to acquire main while main already acquired elsewhere? Document clearly to avoid contradictory spec (previous review Error 1).
- Thread-safe: `self.lock = threading.Lock()` around sessions dict acquire/kill/list_sessions.
- ANSI strip + exit code parsing: regex `\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07` already, plus `__FA_EXIT__:{uuid}:$? __FA_END__:{uuid}` with uuid.
- CWD lock: per PtySession lock for workdir changes? For v0.1 single subagent limit, CWD race unlikely but add `self._cwd_lock = threading.Lock()` per session.
- Signal/atexit: `atexit.register(_cleanup_all)` + `signal.signal(SIGTERM/SIGINT, handler)` that kills all sessions via `pool.kill(sid)` + `server.cmd("kill-server")` for isolated socket, removes socket file `/tmp/tmux-UID/fa_*`.
- Fallback pexpect: PtySession has `_is_fallback` bool, `_fallback: pexpect.spawn` per session_id, independent, thread-safe via `self.lock` in PtyPool. Fallback also uses sentinel and exit code parsing same.

**Phase 3.2 run_bash thin client:**

- `bash_executor.py` Protocol `BashExecutor` with `run(command, timeout, workdir, session_id) -> PtyResult`, `send_ctrl_c`, `close`, `list_sessions` already partially shipped.
- `InProcessPtyExecutor(pool)` implements Protocol via `pool.acquire(session_id, workdir).run(command)`.
- `RemoteRuntimeExecutor` future: thin client to FastAPI `POST /execute`.
- `run_bash.py` handler: try `session = get_current_session()`, `executor = getattr(session, "bash_executor", None) or getattr(session, "pty_pool", None)`? Actually per spec: `run_bash.py thin client depends on BashExecutor protocol, not concrete PtyPool, injected via SessionState`. So SessionState should have `bash_executor: BashExecutor | None` = `InProcessPtyExecutor(pty_pool)`. Then handler: if executor present, `result = executor.run(command, timeout, workdir=root, session_id="main")` -> `PtyResult` -> convert to `ToolResult.ok` with stdout, exit_code, truncated. Else fallback `subprocess.run` with `_elide_500_preview` + ArtifactStore write full output + artifact_id + 500-char preview + WARNING log.
- Ensure `max_context_bytes=8000` + elide.

**Phase 3.3 Dockerfile:**

- Verify `Dockerfile.fa` has `RUN apt-get update && apt-get install -y tmux && tmux start-server; tmux list-sessions || true` + `pip install libtmux` or in `pyproject.toml` dependencies includes `libtmux>=0.32`. Feature flag `runtime.mode` default in_process already in `FeatureFlags`.
- Add `libtmux` to `pyproject.toml` if not present.

**Phase 3.4 SubagentRunner:**

- Scrubbed env: `build_scrubbed_env(os.environ, extra_allow=("X_FA_PROXY_TOKEN",))` + keep PATH, HOME, etc via allowlist. Use in `subprocess.run` for verifier bash tool and in PtyPool env.
- Filtered history: `build_filtered_history(task, session_state, workspace_root, limit=5)`:
  - Get `transaction.read_set + write_set` (already accumulated)
  - Call `instant_grep(task)` to get 5 relevant files paths via FTS5 trigram <50ms
  - If instant_grep returns <3 results (vague task), fallback to `glob **/*.md` + `read llms.txt` + `read AGENTS.md` + `read README.md` limit 5
  - Reads those files via `read_file` tool but only 500-char preview each, total <8000 chars
  - Returns list messages `[task, {"role": "system", "content": "Relevant files: ..."}]` not full parent 124 steps
- JSON validation cached at module load: `fastjsonschema.compile(SUBAGENT_ENVELOPE_SCHEMA)` already, validate envelope before writing artifact.
- Artifact write `.fa/subagents/<id>.json` sanitized task_id via `_sanitize_task_id`, parent dir mkdir -p.
- Subagent limit: `SessionState.subagent_spawns` with Lock, increment on spawn, check against `RuntimeLimits.max_subagent_spawns_per_session=3`, fail-fast `SubagentLimitExceeded` if limit reached.
- Worklog aggregation: After subagent returns JSON envelope Goal, Verification, Risks, token_usage, duration_ms, next_action, aggregate into `worklog.md` with sections Goal, Evidence, Steps, Verification.

**Phase 3.5 Eval-harness:**

- Fixtures `eval/fixtures/*.md` frontmatter `task_id`, `scoring_kind`, `expected`
- `eval/run.py` or `fa eval run` CLI: reads fixtures, runs `fa run --role <role> --task`, parses `~/.fa/session-log/<run_id>/events.jsonl`, produces `eval/reports/<run_id>.md` with per-task verdict + aggregate metrics
- Metrics: median tokens/tool-calls/USD, before/after 124→30-40, trajectory efficiency tokens-per-task + re-fetch frequency, verification strength, state consistency, safety compliance, replayability
- Leaderboard.md append-only
- Baseline stored in `eval/baseline.json`

**Phase 3.6 Docs:**

- Update llms.txt BY-DEMAND INDEX, HANDOFF.md §Next, DIGEST.md, markdown-link-check, no shell=True without nosemgrep + ADR-6, no Level-0 TCB import external lib per ADR-11

---

## How We Write Those Ideas in Code for First-Agent

**File mapping:**

- `src/fa/runtime/pty_pool.py` — PtyPool v2 production with shared Server injection, socket isolation, UUID sentinel, wide viewport -x 300, -J join, ANSI strip, exit code parsing, LRU never reuse main, PoolExhaustedError, thread-safe, fallback pexpect per-session, signal/atexit cleanup
- `src/fa/runtime/bash_executor.py` — BashExecutor Protocol + InProcessPtyExecutor(pool) + RemoteRuntimeExecutor future
- `src/fa/inner_loop/tools/run_bash.py` — thin client depends on BashExecutor via SessionState, fallback subprocess with ArtifactStore
- `src/fa/workspace/worktree_manager.py` — SharedDir primary, Isolated kept for tests with custom BranchAlreadyCheckedOutError/CleanupFailedError
- `src/fa/blackboard/blackboard.py` — full read/write conflict + Q2 base_commit linear frontier policy + assumption violated, query dict check
- `src/fa/inner_loop/loop.py` — Hermes pattern NEVER_PARALLEL, PARALLEL_SAFE, PATH_SCOPED with _paths_overlap, max_workers min(len,5), wait + fallback sequential, synthetic error blocks
- `src/fa/inner_loop/profiles.py` — planner limited write to knowledge/research/** + .fa/** compliance-by-construction
- `src/fa/inner_loop/tools/glob.py` — senior refactor single responsibility helpers, symlink escape check, git ls-files --cached --others --exclude-standard, centralized _matches with **/ handling
- `src/fa/inner_loop/tools/grep.py` — streaming line-by-line _grep_file_stream, no hard skip, soft limit warning, max_file_size param overridable
- `src/fa/inner_loop/tools/instant_grep.py` — F821 fixed via fts_error variable, split _fts_search, _git_fallback_search, _walk_fallback_search, module-level EXCLUDE_DIRS
- `src/fa/inner_loop/tools/observability.py` — usage TBD until telemetry, list_tasks DI via contextvar for pty_pool/worktree_manager + subagent artifacts
- `src/fa/inner_loop/tools/pair_tools.py` — checkpoint git add -A respects .gitignore + ephemeral branch agent/checkpoint-<run_id>-<ts> + stash create/store fallback, automated, merges to origin/main manual
- `src/fa/memory/fts_index.py` — patterns fixed *.js, empty DB full reindex precaution, single walk pruning
- `src/fa/telemetry/telemetry.py` — field-level truncation always valid JSON, minimal fallback
- `src/fa/inner_loop/subagent_runner.py` — scrubbed env, filtered history, JSON validation cached, artifact write, limit enforced
- `src/fa/inner_loop/subagent/prompts.py` — RESEARCHER_MINIMAL_PROMPT 139 tokens, VERIFIER 105 tokens
- `eval/fixtures/` + `eval/run.py` + `eval/leaderboard.md` + `eval/baseline.json` — mini eval-harness

**Coding conventions per project:**

- Single responsibility pure helpers, deterministic Python without LLM per Q4 minimalism
- Single source of truth EXCLUDE_DIRS imported once at module load
- Safety: resolved root, symlink escape check `resolve().is_relative_to(root)`, EXCLUDE_DIRS pruning, limit capped max 200
- Intended fictions: returns paths not content token efficient, respects .gitignore via git ls-files --cached --others --exclude-standard, fallback pruning, limit default 50
- Failure-observable: print WARNING not silent pass/continue, narrow exceptions OSError, json.JSONDecodeError, sqlite3.Error where possible, else # noqa: BLE001 with justification per Phase 0.5 graceful degradation
- No global singleton, DI via SessionState, thread-safe Lock
- No shell=True without # nosemgrep + ADR-6, no Level-0 TCB import external lib per ADR-11
- S603/S607 subprocess trusted binary per ADR-6 with # noqa: S603, S607 + list args, no shell, -- separator
- C901 complexity: split into helpers, add # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4 where needed

---

## How We Will Verify Correctness

**Unit tests (existing + new):**

- `pytest tests/test_pty_persistence.py -q` — PtyPool persistence cd /tmp && pwd returns /tmp, export FOO=bar + echo $FOO → bar, ANSI stripped ls --color=always no \x1b\[, Ctrl+C interrupts sleep 10, no global singleton, SessionState holds executor via DI, shared Server instance, fallback pexpect WARNING
- New tests:
  - `test_pty_pool_lru_never_evict_main`: acquire main, cd /tmp, acquire sub1 export FOO=bar, acquire sub2 (should evict sub1 not main), assert main still /tmp, sub1 gone, sub2 present
  - `test_sentinel_collision`: write file containing |||FA_READY||| + __FA_EXIT__:, cat via PtyPool, assert output contains file content fully and exit code 0, no premature sentinel detection
  - `test_socket_isolation`: run two fa runs with same session_id main but different run_id, assert both have independent /tmp/tmux-UID/fa_* sockets, no cross-talk, no hijack
  - `test_pexpect_fallback_isolation`: mock tmux missing, two threads acquire different session_id with fallback, run echo $SESSION_ID concurrently, assert outputs not interleaved
  - `test_signal_atexit_cleanup`: run fa run that creates PtyPool, kill parent with SIGTERM, assert tmux -L fa_run_id list-sessions returns no sessions, socket file removed
  - `test_filtered_history_fallback`: vague task "Read repository and tell what you found", instant_grep returns 0, assert build_filtered_history returns at least 3 files llms.txt, AGENTS.md, README.md, total <8000 chars
  - `test_git_status_transaction`: echo foo > bar.txt via bash, then _get_write_set_from_git_status returns bar.txt, transaction.add_write called, blackboard query finds it
  - `test_planner_limited_write`: planner registry write_file to src/illegal.py fails path_denied, to knowledge/research/plan.md succeeds

**Integration tests (mini eval-harness 5 tasks):**

- Task 1: `fa run --role planner --task "Read repository and tell what you found"` — measures baseline 124 steps before Phase 3, after target 30-40
- Task 2: fs.glob + read + write + run_bash + diff + checkpoint/undo pair tools — measures state consistency cd /tmp persists
- Task 3: instant_grep "auth" finds Authentication <50ms — measures FTS5
- Task 4: Blackboard conflict detection concurrent write without coordination → conflict_detected — measures safety compliance
- Task 5: Verifier subagent pytest returns JSON PASS/FAIL, main sees only summary 500 tokens not 5k raw, context stays 180.5k not 185k — measures verification strength + token efficiency

Metrics: median tokens/tool-calls/USD, before/after 124→30-40, trajectory efficiency tokens-per-task + re-fetch frequency, verification strength, state consistency, safety compliance, replayability (events.jsonl replay), plus governance decay fixture policy "never call production DB" must survive compaction (ConstraintRot).

**CI / pre-commit:**

- `ruff check` — no new P0 errors F821, S101, C901 for critical paths (blackboard, worktree_manager, loop, pty_pool) after split helpers + noqa with justification
- `ruff format` — 14 files reformatted, 1 file left unchanged previously, now 0 after fixes
- `markdown-link-check` — link integrity per MAINTENANCE.md
- No `shell=True` without `# nosemgrep + ADR-6`
- No Level-0 TCB import external lib per ADR-11
- `pytest tests/test_blackboard_conflict.py tests/test_worktree_defensive.py tests/test_instant_grep.py tests/test_tool_batching.py tests/test_inner_loop_runtime.py` — 30 passed previously after P0/P1 fixes, should stay green

**Manual verifications:**

- `cd /tmp && pwd` persists across calls second pwd returns /tmp
- `export FOO=bar + echo $FOO → bar`
- `ls --color=always` no `\x1b\[` after ANSI strip
- `sleep 10` + `send_ctrl_c` interrupts
- `git status --porcelain -z` <2ms for transaction detection

---

## Next Steps Implementation Order (2-3 days)

**Day 1: PtyPool hardening + BashExecutor thin client + Dockerfile**

1. Update `pty_pool.py` with socket isolation `socket_name=f"fa_{run_id}"`, wide viewport `-x 300`, `-J` join wrapped lines, UUID sentinel per session, CWD lock per session, PoolExhaustedError policy pinned main + LRU sub, shared Server injection via SessionState, timeout, thread-safe, fallback per-session, signal/atexit cleanup
2. Update `bash_executor.py` InProcessPtyExecutor using pool, RemoteRuntimeExecutor future
3. Update `run_bash.py` thin client depends on BashExecutor via SessionState, fallback subprocess with ArtifactStore + artifact_id + 500-char preview
4. Update `Dockerfile.fa` apt-get install tmux + tmux start-server + pip install libtmux, feature flag runtime.mode=in_process
5. Tests: test_pty_persistence, test_lru_never_evict_main, test_sentinel_collision, test_socket_isolation, test_pexpect_fallback_isolation, test_signal_atexit_cleanup

**Day 2: SubagentRunner + Worklog + Profiles planner limited write**

6. Update `subagent_runner.py` scrubbed env via `build_scrubbed_env`, filtered history with fallback chain transaction read_set/write_set → instant_grep → glob llms.txt/AGENTS.md/README.md, JSON validation cached, artifact write .fa/subagents/<id>.json sanitized task_id, limit enforced via RuntimeLimits
7. Update `profiles.py` planner limited write allowlist already done, verify and add tests
8. Worklog.md aggregation from JSONs Goal, Evidence, Steps, Verification

**Day 3: Eval-harness + Docs**

9. Create `eval/fixtures/*.md` 5 tasks, `eval/run.py`, `eval/leaderboard.md`, `eval/baseline.json` with baseline 124 steps documented
10. Update `knowledge/llms.txt` BY-DEMAND INDEX, `HANDOFF.md` §Next, `DIGEST.md`, markdown-link-check, no shell=True, no Level-0 TCB import

**Acceptance for Phase 3 (from v3):**
- cd /tmp && pwd persists, export FOO=bar + echo $FOO → bar, ANSI stripped, Ctrl+C interrupts sleep 10
- No global pool singleton, SessionState holds executor via DI, shared Server instance, fallback pexpect WARNING
- Verifier subagent pytest JSON PASS/FAIL, main sees only summary 500 tokens, worklog contains Goal, Verification, Risks
- Baseline 124 steps documented after target 30-40 measured tokens ↓60% tool-calls ↓50%, pair over autonomy checkpoint/undo/diff

