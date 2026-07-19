# Substrate Gap Closure — State Assessment Round 3

**Date:** 2026-07-15
**Branch:** substrate
**Assessor:** Agent Mode MAX effort
**Parent docs:**
- substrate-decision-freeze-2026-07-15.md (D8/D9/D10)
- substrate-gap-closure-workplan-round2-2026-07-15.md
- slice0-slice1 impl plan + slice1 closure + slice2/3/4 patch designs

---

## 0. Executive summary

Out of 11 planned slices (0-10), current code appears to have closed:

- **Slice 0** — contract freeze — ✅ decision-freeze file exists, D8/D9/D10 grep-able
- **Slice 1** — unified per-run DB authority — ✅ session_db.py exists, EventLog DB-first, Blackboard facade, tests pass (13 tests for session_db authority)
- **Slice 2** — observability runtime authority — ✅ chronicle_search + usage now DI via contextvar, no path-guessing, explicit run_id, tests pass (6 tests in test_observability_runtime_authority.py)
- **Slice 3** — Stage C correctness — ✅ ContextBudget now explicit warn/stage2/stage3 with distinct thresholds, Anthropic cache_control preservation (structured system), OpenAI extras forwarding from coder_loop, compactor uses config.model, fallback returns 4 headers. Tests for compaction_sota, pr1, pr3, pr5 pass (30 tests)
- **Slice 4** — governance plane repair — ✅ CLI now routes resume_draft_text to initial_memory_summary (mutable), not system_prompt_extra; PinnedBuffer.refresh replaces cache wholesale, warns on disappearance/hash change. Coder_loop merges resume + rebuilt summary.

Residual open slices:

- **Slice 5** — subagent hardening — 🟡 partially wired, but tests fail (5 failures)
- **Slice 6** — bash + PTY truthfulness — 🟡 large-output artifact API mismatch (confirmed bug), PTY not wired into live CLI
- **Slice 7** — scheduler + search safety — 🟡 parallel batching drops denied results (code confirmed), instant_grep does writes (auto-index) while classified read-only
- **Slice 8** — logging standardization — 🔴 91 print WARNING in src/fa
- **Slice 9** — global_history.db export — 🔴 not implemented
- **Slice 10** — anti-theater hardening — 🟡 partial (dead flags still exist)

---

## 1. Verification evidence for completed slices

### Slice 1
- File exists: src/fa/inner_loop/session_db.py (SessionDatabase with event_log/blackboard/session_meta, WAL, busy_timeout)
- EventLog.append: authority DB write first, then best-effort JSONL mirror, id advances only after DB success
- EventLog.read_all: prefers DB, falls back to JSONL only on exception
- SessionState binds blackboard to same session_db
- Tests: `test_session_db_authority.py` — 13 tests (roundtrip, split-brain, concurrent) — PASSED

### Slice 2
- observability.py: _resolve_event_log resolves active session via get_current_session() or explicit run_id, else no_active_session structured fail
- build_chronicle_search_tool and build_usage_tool no longer take guessed path at builder time; handler uses EventLog.read_all()
- usage parses authoritative usage rows: input_tokens/output_tokens/cache_read/create, not prompt_tokens/total_tokens
- profiles.py + tools/__init__.py no longer pass guessed paths
- Tests: test_observability_runtime_authority.py — 6 tests — PASSED

### Slice 3
- context_budget.py: stage2_threshold = configured or min(80%*limit,150k), stage3_threshold = min(max(stage2+1,90%*limit),limit), check() returns allow/warn/stage2/stage3 with warn threshold 70%
- coder_loop.py: request composition preserves extras (prompt_cache_key), distinct handling for stage2 vs stage3, stage2 runs first, stage3 only if still in zone or compaction disabled => hard stop only in stage3 zone
- compactor.py: model_slug = compactor_chain.config.model, fallback returns 4 headers + verbatim history even for short
- prompt_composer.py: memory-summary anchor tagged cache_control ephemeral
- anthropic.py: system_rows hoisting now preserves cache_control as structured blocks when present
- openai_compat.py: already forwards extras
- Tests: test_compaction_sota + test_pr1_wiring + test_pr5_wiring + test_pr3_wiring — 30 PASSED

### Slice 4
- cli.py line 1801-1802: system_prompt_extra="", initial_memory_summary=resume_draft_text — resume text no longer routed into PinnedBuffer
- coder_loop.py: new param initial_memory_summary, _merge_memory_summary_context, memory_summary initialization, PinnedBuffer.extract_pinned_content only gets true standing guidance
- pinned_buffer.py: refresh() snapshots previous, builds new_cache/new_hashes, replaces wholesale, warns on disappearance/change
- Tests: test_pr2_wiring (pin reload) still passes per previous slice evidence

---

## 2. Open defects — concrete reproduction

### FIND-002 / FIND-010 — Subagent safety + contract

Evidence:
- `src/fa/inner_loop/tools/spawn_subagent.py` runs SubagentRunner.run_stateless which does `subprocess.run(shell=True)` directly. No SandboxHook/IntentGuard/BashIntentAnalysis, no SecretGuard check. So bypass.
- Role param accepted but ignored: `from_verifier` always sets type verifier; test `test_spawn_subagent_tool_gated_by_flag` expects researcher.

Failing tests (repro):
```
test_run_bash_large_output_offloads_artifact_without_internal_error — AttributeError: ArtifactStore has no attribute write
test_spawn_subagent_tool_gated_by_flag — role researcher ignored
test_subagent_runner_honors_feature_flag_spawn_limit — second call should raise RuntimeError but doesn't
test_run_stateless — env_extra TEST_VAR not propagated
test_run_stateless_researcher_role_preserved — type remains verifier
```

Files:
- src/fa/inner_loop/tools/spawn_subagent.py
- src/fa/inner_loop/subagent_runner.py (role ignored in from_verifier, env_extra handled but test shows failure)
- src/fa/inner_loop/subagent_envelope.py (from_verifier hardcodes type)

### FIND-006 — Bash large-output artifact API

- ArtifactStore defines `put()`, but run_bash.py uses `write()` in both PTY and fallback paths, leading to AttributeError -> internal_error.
- Location: src/fa/inner_loop/tools/run_bash.py:131 and :198
- Also catches only OSError, not AttributeError.

### FIND-007 — PTY not wired into live CLI

- cli.py creates SessionState without pty_pool. SessionState doc says optional DI Phase 3, but field stays None.
- run_bash tool tries DI: gets bash_executor or pty_pool from session, but always None -> falls back to subprocess (stateless).
- Therefore claimed "STATEFUL via PtyPool" is false in live harness.
- File to fix: src/fa/cli.py _cmd_run must instantiate PtyPool

### FIND-012 — Scheduler drops denied results

Confirmed in src/fa/inner_loop/loop.py _execute_batch_parallel:

BEFORE loop creates denied result, appends to local `results` but payloads adds None placeholder.
Then return value is only `ordered_results` (parallel successes), denied dropped.
So returned tuple length < input length, order broken.

### FIND-013 — instant_grep write in read-only path

- instant_grep tool permission="read" but handler calls _fts_search which does:
  `index.index_repo(workspace_root)` when count==0 or on exception.
  That writes to DB and indexes all files — not read-only.
  Also git fallback paths only read, but FTS path is write.

### FIND-015 — Logging migration

91 occurrences of `print(f"WARNING: ...")` in src/fa. Should be logger.warning.

### FIND-016 — CR cleaning

- PtyPool returns stdout that may contain \r (progress bars). No \r -> \n normalization in run_bash capture paths.

### FIND-009 — global_history.db export absent

No file `global_history.db` export implementation found. Workplan expects derived projection.

---

## 3. Proposed next intermediate goal

### Decision: Slice 5 + Slice 6 + Slice 7 combined as "Safety & Execution Truthfulness Slice"

Rationale:
- Subagent bypass (FIND-002 P0) is highest severity remaining — security boundary.
- Bash large-output (FIND-006) blocks token-efficient offload; test already fails — easy win.
- Scheduler denied-result loss (FIND-012) breaks tool-call pairing invariant — correctness P1.
- instant_grep write (FIND-013) violates read-only classification — safety.
- These 4 defects are co-located in inner_loop/tools and loop.py and share the same verification surfaces (test_inner_loop_tools, test_subagent_runner, test_tool_batching, test_instant_grep).

Slice ordering recommendation:
1. **Fix ArtifactStore API** (FIND-006) — 15 min, unblocks bash tests.
2. **Fix scheduler denied preservation + order** (FIND-012) — 30 min, fixes invariant.
3. **Fix instant_grep write removal** (FIND-013) — 30 min, make read-only truthful.
4. **Subagent hardening** (FIND-002,010) — 2-3 hrs, biggest.
5. **PTY wiring decision** (FIND-007,016) — 1 hr, depends on operator choice.

Leaving logging (Slice 8) and global export (Slice 9) for later separate slices — they are lower risk and don't block safety.

---

## 4. Open design decisions needing operator lock

See attached questions list — need explicit answers before code edits to avoid re-litigating D10.

---

## 5. Test plan for next slice

- `test_run_bash_large_output_offloads_artifact_without_internal_error` must pass
- `test_spawn_subagent_tool_gated_by_flag` must pass
- `test_subagent_runner_honors_feature_flag_spawn_limit` must pass
- `test_run_stateless` env_extra must pass
- `test_run_stateless_researcher_role_preserved` must pass
- batching: new tests — batch with one denied read tool returns full ordered result tuple (preserve denied), empty-index instant_grep not writing
- subagent: malicious nested shell denied by same policy class as parent shell
- subagent: researcher vs verifier behavior difference test
- subagent: configured spawn limit non-default test (1)
- subagent: lifecycle cleanup test
- bash: CR cleaning examples `foo\rbar\n -> bar`

---

## 6. Risks

- Changing subagent to check sandbox policy before execution may break existing allowed subagent commands — need allowlist or explicit bypass flag.
- Wiring PtyPool into CLI introduces dependency on pexpect/fast event loop; need graceful fallback if not available.
- Removing auto-index from instant_grep will make FTS empty on fresh workspaces — need explicit `fa reindex` or lazy read-only rebuild outside tool path.

---

## Appendix — file targets for next slice

- src/fa/inner_loop/tools/run_bash.py (fix write->put, add CR cleaning, add \r normalization helper)
- src/fa/inner_loop/artifacts.py (add write alias or fix callsite; prefer alias for compat)
- src/fa/inner_loop/loop.py (_execute_batch_parallel merge denied results)
- src/fa/inner_loop/tools/instant_grep.py (remove index_repo from handler, make read-only, or reclassify permission)
- src/fa/memory/fts_index.py (ensure read-only query path doesn't trigger indexing)
- src/fa/inner_loop/subagent_runner.py (role handling, from_researcher factory, env_extra fix, spawn limit wiring to RuntimeLimits + FeatureFlags)
- src/fa/inner_loop/subagent_envelope.py (add from_researcher or role-aware factory)
- src/fa/inner_loop/tools/spawn_subagent.py (add env input_schema?, role behavior diff, sandbox check via IntentGuard)
- src/fa/cli.py (instantiate PtyPool if feature flag)
- tests/* (no edits allowed per hook, but we can add new tests under allowed pattern: new file tests/test_substrate_slice5_6_7.py)
