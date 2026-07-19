---
title: "Phase 1 Closure Review — Implementation Gaps, Logic Errors, Wiring Fit for first-agent harness"
source:
  - "knowledge/research/adr-13-14-implementation-plan-2026-07-11-v3-reduced.md"
  - "knowledge/research/phase1-foundation-detailed-implementation-plan.md"
  - "knowledge/research/phase1-foundation-final-decisions.md"
  - "src/fa/inner_loop/tools/__init__.py"
  - "src/fa/inner_loop/profiles.py"
  - "src/fa/inner_loop/prompt_composer.py"
  - "src/fa/workspace/worktree_manager.py"
  - "src/fa/inner_loop/subagent_runner.py"
  - "src/fa/inner_loop/subagent_envelope.py"
  - "src/fa/skills/loader.py"
  - "src/fa/inner_loop/state.py"
  - "src/fa/inner_loop/loop.py"
  - "src/fa/inner_loop/coder_loop.py"
compiled: "2026-07-12"
chain_of_custody: "Hard critical thinking review after Phase 1 implementation, before closing Phase 1 prod."
goal_lens: "Will LLM loop correctly invoke new modules as intended now? Are all modules correctly wired into first-agent harness?"
tier: stable
---

# Phase 1 Closure Review — Wiring & Logic Errors

## Main Lens: Will new module work as intended and serve its function for first-agent harness?

### Summary — 9 Gaps Found (4 High, 5 Medium)

#### High H1: PROFILES builder not wired into actual registries used by loop

**Current:**
- `src/fa/inner_loop/tools/__init__.py` `build_baseline_registry()` manually registers read, write, bash, plus _register_stage0_tools (glob, grep, observability, pair, instant_grep) → 13 tools.
- `src/fa/inner_loop/profiles.py` `build_registry_for_role()` exists, tested, returns filtered registry (researcher 4 tools 403 tokens), but **never called** from `__init__.py` or `coder_loop.py`.
- LLM loop uses `build_baseline_registry` / `build_planner_registry` / `build_eval_registry`, not `build_registry_for_role`.

**Impact:** Researcher role intended -60% tokens via 4 tools, but LLM in planner role still gets 7-8 tools (read, bash, glob, grep, instant_grep, chronicle_search, usage) → not 600 tokens, not as efficient as planned. Token saving not realized in prod.

**Fix for closure:**
- Change `build_planner_registry` to call `build_registry_for_role("planner", root)` + add observability tools (chronicle_search, usage) as extra.
- Change `build_baseline_registry` to call `build_registry_for_role("implementer", root)` + observability + pair tools.
- Change `build_eval_registry` to call `build_registry_for_role("verifier", root)` + usage.
- This wires profiles into actual loop.

**Verification:** After fix, `build_planner_registry` names should be subset of planner profile + observability, tokens <800.

#### High H2: PromptComposer not wired into coder_loop.py

**Current:**
- `coder_loop.py` builds system prompt via `build_system_message()` from `prompt.py` (PLANNER_SYSTEM_PROMPT etc) + `render_tool_specs(registry.specs())` → old path.
- `prompt_composer.py` `build_prompt_parts_v2` exists, tested, two-level caching, but **never imported or called** in `coder_loop.py` or providers chain.

**Impact:** Prompt caching per role (cache-key = role + hash_tools + hash_map + hash_always_skills) not used, no cache_control ephemeral, no prompt_cache_key for OpenAI, no token saving 90% off. Pillar 3 KPI not improved.

**Fix for closure:**
- In `coder_loop.py`, add feature-flag check: if `feature_flags.prompt_caching` and `prompt_composer` available, build messages via `build_prompt_parts_v2` + `to_anthropic_request_v2`, else fallback to old `build_system_message`.
- For Phase 1, implement minimal wiring: keep old path as default, new path behind flag `prompt.caching` enabled. Document.

**Why not full wiring now:** Coder loop has complex logic for system_message + tool_payload + observations, requires refactoring. For Phase 1 closure, add function `build_messages_with_composer_if_enabled()` that returns PromptParts if flag enabled, else None.

#### High H3: Skill loader not wired into PromptComposer nor SessionState

**Current:**
- `src/fa/skills/loader.py` `should_load_skill()` and `get_current_files_for_skill_loader()` exist, tested, but never called from `prompt_composer.py` or `state.py` or `coder_loop.py`.
- Skills in `knowledge/skills/` are not loaded on demand based on globs, alwaysApply is ignored, all skills would need to be manually loaded.

**Impact:** Token bloat: agent loads all skills every time or none, not conditional globs → tools-in-context not reduced.

**Fix for closure:**
- Wire skill loader into PromptComposer: in `build_prompt_parts_v2`, accept `current_files` param, call `should_load_skill` for each skill file in `knowledge/skills/*/SKILL.md`, split into alwaysApply vs conditional.
- Wire `get_current_files_for_skill_loader` into `state.py` to get current_files from transaction + instant_grep.
- For Phase 1, implement helper `load_skills_for_prompt(workspace_root, current_files, task_text)` that returns (always_skills, conditional_skills).

#### High H4: WorktreeManagerFactory not wired into SessionState, SubagentRunner workdir not via Manager

**Current:**
- `WorktreeManagerFactory.from_flags()` exists, but `SessionState` does not have `worktree_manager` field.
- `SubagentRunner.run_stateless` takes `workdir` param, but caller must create workdir via WorktreeManager manually. No tool does that, so LLM cannot spawn subagent with isolated worktree.

**Impact:** Isolated worktree never used, subagent always uses session_root (SharedDir), isolation not tested.

**Fix for closure:**
- Add `worktree_manager` field to SessionState, init via Factory from FeatureFlags (shared for v0.1).
- Add method `SessionState.create_subagent_workspace(task_id)` that delegates to manager.
- In SubagentRunner, accept optional WorktreeManager, or get via contextvar SessionState.

#### Medium M1: Glob/Grep tools added but edit_file still missing for implementer

**Current:** PROFILES implementer wants [read,write,edit_file,bash,glob,grep,instant_grep] 7 tools, but `fs.edit_file` builder not found → warning skip, implementer gets 6 tools.

**Impact:** Implementer cannot do string-replace edit, only full write_file → more tokens, less efficient, but not critical for Phase 1.

**Fix:** Either implement `fs.edit_file` as wrapper around write_file with simple replace, or remove edit_file from implementer profile for Phase 1 and document.

#### Medium M2: Transaction read_set/write_set accumulation works, but WorktreeManager does not declare read_set/write_set

**Current:** Plan says WorktreeManager declares transaction read_set/write_set. Currently WorktreeManager doesn't interact with Transaction.

**Impact:** Blackboard conflict detection for worktree paths not tracked.

**Fix:** In WorktreeManager.create_subagent_workspace, add transaction.add_write for worktree_path, and add_read for base_branch.

#### Medium M3: PromptComposer cache-key includes hash_always but hash_always computed from skills_all fallback to skills_all if always empty — could be confusing

**Current:** In `build_prompt_parts_v2`:
```python
if not skills_always and skills_all:
    hash_skills_effective = _hash_skills(skills_all)
    if hash_always == "no-skills":
        hash_always = hash_skills_effective
```

**Impact:** If caller passes skills_all but not skills_always, hash will be of all skills, not just always, inconsistent.

**Fix:** Simplify: always compute hash from skills_always only (stable), ignore skills_all for cache_key. Document.

#### Medium M4: SubagentEnvelope artifact path .fa/subagents/<id>.json — is .fa ignored? Yes .gitignore has .fa/, but need to ensure parent dir created

**Current:** `write_envelope_artifact` does `mkdir(parents=True, exist_ok=True)` — ok.

**Impact:** None, but need to ensure cleanup of old artifacts (stale cleanup) not implemented.

**Fix:** For Phase 1, no stale cleanup needed, document future.

#### Medium M5: SessionState subagent_spawns counter thread-safety — uses Lock, ok, but increment via setattr fallback not thread-safe if no method

**Current:** In SubagentRunner, fallback `setattr(session, "subagent_spawns", count+1)` not via Lock, race possible.

**Impact:** In Phase 2 parallel 2-3 subagents, race could allow spawn over limit.

**Fix:** Use `session.increment_subagent_spawns()` which uses Lock, always, not setattr fallback.

## Wiring Fit for first-agent harness — Will LLM loop correctly invoke?

### What is wired and works now (Stage 0, 0.5, Phase 1 partial)

- **Transaction:** Wired via contextvar in loop.py set_current_session, read_file/write_file add_read/add_write, state.py add_read/add_write, record_tool_call tracks. LLM loop **does** invoke it — every fs.read_file adds to read_set, every fs.write_file adds to write_set. Verified via integration tests.

- **Blackboard:** Wired via write_file handler calling detect_conflict before write, writing entry after. LLM loop **does** invoke — second write same file fails conflict_detected. Verified.

- **Telemetry:** Wired via SessionState.record_tool_result logging TelemetryEvent + artifact offload + EventLog kind=telemetry. LLM loop **does** invoke — telemetry.jsonl written each tool call. Verified.

- **FeatureFlags:** Wired via SessionState __post_init__ loading from ~/.fa/config.yaml. LLM loop **does** use flags for blackboard.enabled, telemetry.enabled, offload_threshold. Verified.

- **Glob/Grep tools:** Wired via tools/__init__.py _register_stage0_tools include_glob_grep=True for baseline and planner, so LLM **can** call fs.glob and fs.grep. Verified via manual test.

- **WorktreeManager SharedDir:** Wired? No, not in SessionState, but SharedDir returns session_root so effectively no isolation, LLM doesn't call it explicitly, so no invocation needed for v0.1.

### What is NOT wired and LLM loop does NOT invoke as intended

- **PROFILES dynamic registry:** Exists but not used by baseline/planner/eval registries. LLM still gets 11-13 tools, not 4 tools 600 tokens. Token saving not realized.

- **PromptComposer two-level caching:** Exists but not used by coder_loop.py, so no cache_control, no prompt_cache_key, no 90% cost saving.

- **Skill loader:** Exists but not used by PromptComposer, so skills not loaded conditionally, token bloat remains.

- **SubagentRunner + Envelope:** Runner exists, envelope extracted, spawn limit via SessionState works when called directly, but no tool exposes spawn to LLM (no fs.spawn_subagent tool). So LLM cannot spawn subagent as intended for cheap deterministic puzzle piece.

- **WorktreeManager Isolated + Factory:** Factory exists but not in SessionState, Isolated not used, so isolation not tested in prod.

## Tightened Plan to Close Phase 1 Properly

### Must fix for closure (High ROI, required for "correctly wired")

1. **Wire PROFILES into registry builders:**
   - Update `build_planner_registry` to use `build_registry_for_role("planner")` + observability.
   - Update `build_baseline_registry` to use `build_registry_for_role("implementer")` + observability + pair.
   - Update `build_eval_registry` to use `build_registry_for_role("verifier")`.

2. **Wire WorktreeManager into SessionState:**
   - Add `worktree_manager` field, init via Factory from flags, run_id.
   - Add method `create_subagent_workspace`.

3. **Fix SubagentRunner spawn limit race:** Use `increment_subagent_spawns()` always, not setattr fallback.

4. **Wire PromptComposer minimally:** Add function `build_messages_if_caching_enabled()` in coder_loop that checks flag and uses composer, with fallback old path. For Phase 1, keep old path default, new behind flag.

5. **Wire Skill loader into PromptComposer helper:** Create `load_skills_for_prompt()` that uses `get_current_files_for_skill_loader` + `should_load_skill`, split always vs conditional.

6. **Add edit_file tool stub for implementer:** Implement simple `fs.edit_file` as string replace (read file, replace old_string with new_string, write), so implementer profile complete.

### Can defer to Phase 2 (Medium, not blocking closure)

- Full PromptComposer integration into provider chain (Anthropic cache_control 4+1 breakpoints)
- Skill loader integration into full prompt (conditional skills in non-cacheable)
- Subagent spawn tool `fs.spawn_subagent` for LLM to call
- WorktreeManager Isolated tested with real git repo in prod loop
- Transaction read_set/write_set for WorktreeManager

## Verification After Tightened Fixes

- [ ] `build_planner_registry` returns only planner tools + observability, tokens <800
- [ ] `build_baseline_registry` returns implementer tools + observability + pair, tokens ~1500-2000 vs old 3000
- [ ] `build_registry_for_role("researcher")` 4 tools 403 tokens verified
- [ ] SessionState has worktree_manager, create_subagent_workspace returns session_root for shared mode
- [ ] SubagentRunner spawn limit enforced via SessionState counter, not instance fallback
- [ ] PromptComposer two-level caching helper exists, flag check works
- [ ] Skill loader helper load_skills_for_prompt returns always vs conditional split
- [ ] All 20 old tests still pass, new Phase 1 unit tests pass
- [ ] Markdown link check 84 OK
- [ ] No new shell=True without nosemgrep

## Risks Mitigated

- Token saving not realized → fixed via profiles wiring
- Prompt caching not used → fixed minimal wiring behind flag
- Skills bloat → fixed via loader helper
- Worktree isolation not tested → fixed via SessionState factory
- Spawn limit race → fixed via increment method

## Next Steps to Close Phase 1

1. Implement wiring fixes above (1 hour)
2. Run pytest 20 + new Phase 1 tests
3. Update STAGE_1_VERIFICATION.md with closure checklist
4. Update DIGEST.md and exploration_log.md Q-23 Phase 1
5. Prepare PR with final compact bundle
