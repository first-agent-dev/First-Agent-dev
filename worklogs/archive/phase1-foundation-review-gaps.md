---
title: "Phase 1 Foundation — Review Lens: Will new modules work as intended for first-agent harness?"
source:
  - "knowledge/research/phase1-foundation-detailed-implementation-plan.md"
  - "knowledge/research/adr-13-14-implementation-plan-2026-07-11-v3-reduced.md"
  - "src/fa/workspace/worktree_manager.py"
  - "src/fa/inner_loop/profiles.py"
  - "src/fa/inner_loop/prompt_composer.py"
  - "src/fa/inner_loop/subagent_runner.py"
compiled: "2026-07-12"
chain_of_custody: "Review of detailed implementation plan before coding. Main lens: will module work as intended and serve its function for first-agent LLM agent harness (token efficiency, defensive Tier 1, pair over autonomy, formal substrate)."
goal_lens: "Find implementation gaps and logic errors in Phase 1 plan, tighten plan, ask pivoting decisions."
tier: stable
---

# Phase 1 Foundation — Review Gaps & Logic Errors

> **Lens:** Will this new module work as intended and serve its function for first-agent harness? (Pillar 3 token/tool-call efficient, Pillar 4 measurement, §1.2.6 Substrate Formality, §1.2.7 Pair over Autonomy)

## Summary — 12 Gaps Found, 7 High ROI, 5 Medium

### High ROI (must fix before coding)

#### Gap H1: WorktreeManager sanitizer non-idempotent + leak

**Current plan:**
```python
def _sanitize_task_id(task_id) -> str:
    sanitized = re.sub(..., task_id)[:50].strip('-').lower()
    if not sanitized: return f"task-{uuid4().hex[:8]}"  # random each call
worktree_path = root / _sanitize_task_id(task_id)
branch = f"agent/{_sanitize_task_id(task_id)}"  # calls twice -> two different uuids!
```

**Problem:**
- Calls twice → path `task-abc123` vs branch `agent/task-def456` mismatch, cleanup will fail (assert not exists).
- If task_id="" called twice in same session (1 subagent limit sequential, but still possible), random uuid → two different paths, first worktree leak (not cleaned because path differs).

**Impact:** Worktree leak, defensive assert fails, branch name inconsistent.

**Fix (tightened):**
- Call once, reuse:
```python
clean_id = _sanitize_task_id(task_id)  # deterministic "task" for empty, not random
worktree_path = worktrees_root / clean_id
branch = f"agent/{clean_id}"
```
- For empty: return `"task"` deterministic + WARNING log, not random. Reason: 1 subagent sequential, collision across sessions impossible (session_root isolated per run), leak avoided. If parallel 2-3 in future, then switch to uuid + store mapping.

**Verification:** `test_sanitize_empty` expects `"task"` not random, + WARNING.

#### Gap H2: PROFILES filtering from wrong base registry

**Current plan:** `build_registry_for_role(role, base_registry)` filters from `build_baseline_registry()` which has 11 tools (read, write, bash, observability, pair, instant_grep) but **no** `fs.glob`, `fs.grep`, `fs.edit_file`.

**Problem:** Researcher needs `[glob,grep,read,instant_grep]` — `glob`/`grep` not in baseline → filtered registry will be missing tools → researcher fails to find files → 124 steps not fixed.

**Impact:** Role toolset incomplete, token saving but functionality broken.

**Fix:**
- Create `TOOL_BUILDERS` dict mapping name → builder function:
```python
TOOL_BUILDERS = {
    "fs.read_file": lambda root: build_read_file_tool(root),
    "fs.write_file": lambda root: build_write_file_tool(root),
    "fs.glob": lambda root: build_glob_tool(root),  # existing?
    "fs.grep": lambda root: build_grep_tool(root),
    "fs.instant_grep": lambda root: build_instant_grep_tool(db_path, root),
    ...
}
```
- Or reuse `build_all_tools_registry` that includes all tools (including glob/grep). Check if `glob`/`grep` tools exist in codebase: `src/fa/inner_loop/tools/` currently has read, write, bash, observability, pair, instant_grep, prepare_pr — no glob/grep. They might be in older code or need to be added? Need to check `registry.py` or `AGENTS.md`.

- For Phase 1, keep researcher to only tools that exist: `["fs.read_file", "fs.instant_grep", "fs.chronicle_search", "fs.usage"]` — all exist. Or add stub glob/grep builders that wrap `git ls-files` + `instant_grep`.

**Decision needed:** Do we add glob/grep tools now, or restrict PROFILES to existing tools for Phase 1?

#### Gap H3: PromptComposer cache-key stability vs correctness tradeoff

**Current plan:** `cache_key = role + hash_tools + hash_map + hash_skills` where hash_skills = hash of loaded skills (subset based on current_files).

**Problem:** If hash is of loaded subset, cache_key changes per task (current_files vary) → cache hit ratio low, defeats prompt caching (90% cost saving). If hash is of all skills in repo, cache_key stable but prompt content (subset) differs from cached content → Anthropic returns cached prompt with wrong skills, incorrect behavior.

**Impact:** Either low cache hit or incorrect cached prompt.

**Fix (tightened):**
- Two-level: **cacheable** = BASE + map + tool defs + **alwaysApply=true** skills (stable across tasks). **Non-cacheable** = task + memory_summary + observations + **conditionally loaded** skills (globs matched).
- Then `hash_tools` = stable, `hash_map` = stable, `hash_always_apply_skills` = stable → cache_key stable, high hit.
- Conditionally loaded skills go to non-cacheable, not affecting cache_key, so cache correctness preserved.

**Verification:** `test_cache_key_includes_only_always_apply_skills`.

#### Gap H4: SubagentEnvelope extraction increases surface, violates minimalism-first

**Current plan:** Extract to new file `src/fa/inner_loop/subagent_envelope.py`.

**Problem:** Minimalism-first 4-question test: "Can we add to existing file?" Yes, envelope already in `subagent_runner.py`, 50 lines. New file adds surface, needs update in llms.txt (deprecated but still), increases maintenance per MAINTENANCE.md. ROI low for Phase 1.

**Impact:** Surface bloat, 30+ components N^2 problem from v2 returns.

**Fix:** Keep envelope in `subagent_runner.py` for Phase 1, add methods `from_researcher`, spawn limit check. Extract to separate module only in Phase 3 when PtyPool + WorktreeManager need it. Document deferred.

#### Gap H5: Skill globs loader frontmatter parsing — yaml subset vs pyyaml

**Current plan:** Use `fa._yaml_subset` (hand-rolled, doesn't support lists) or `pyyaml` (exists as dep).

**Problem:** `_yaml_subset` can't parse:
```yaml
globs:
  - "src/**/*.py"
  - "knowledge/**/*.md"
```
It will treat `- "src/..."` as unknown. If we use pyyaml, we add dependency on yaml for Level-1 code which is okay (pyyaml already dep from ADR-9), but need to ensure Level-0 TCB not affected (Level-0 is only `authoring_tcb.py`, safe).

**Impact:** Loader fails to parse globs, always returns False, skills never loaded.

**Fix:** Use `yaml.safe_load` for frontmatter (already dep), with graceful fallback to hand-rolled if yaml missing, log WARNING.

#### Gap H6: Skill loader current_files source ambiguous

**Current plan:** `should_load_skill(skill_path, current_files, task_text)` but `current_files` not defined where from.

**Problem:** If `current_files = git ls-files` (all tracked, ~100s files), many globs will match, many skills loaded → token bloat, defeats purpose. If `current_files = transaction.read_set + write_set` (only touched files, 5-10), precise but might miss files relevant to task not yet touched.

**Impact:** Either too many skills loaded (bloat) or too few (miss).

**Fix:** Define `current_files = transaction.read_set + write_set + relevant_files_from_instant_grep(task_text, limit=10)`. Instant grep query from task text finds relevant files without scanning all. Token efficient, substrate formal.

#### Gap H7: SubagentRunner spawn limit stored in instance, not session

**Current plan:** `_spawn_count` in Runner instance.

**Problem:** If Runner recreated each time we spawn subagent (e.g., `SubagentRunner(session_root)` in tool handler), count resets to 0 each time → limit never enforced → can spawn unlimited subagents, breaking 1 subagent sequential limit for v0.1.

**Impact:** Scope creep to parallel tree, violates pair over autonomy.

**Fix:** Store count in `SessionState` (add `subagent_spawns: int` field) or in `Transaction`. Runner reads/writes from SessionState via contextvar. Then limit enforced across Runner recreations.

### Medium ROI (should fix)

#### Gap M1: AGENTS.md map source for PromptComposer undefined

**Problem:** `agents_md_map` param where from? File `AGENTS.md` content? `llms.txt`? Need to specify: read `AGENTS.md` at session start, or use already loaded `knowledge/llms.txt` MUST READ FIRST? For token efficiency, map should be short summary, not full AGENTS.md.

**Fix:** Define `agents_md_map = extract_agents_map(AGENTS.md)` helper that extracts only `## Loadable skills` table + `## Repository Structure`, not full file.

#### Gap M2: WorktreeManager git worktree list parsing substring false positive

**Current:** `assert str(worktree_path) in list_result.stdout`

**Problem:** If path `/tmp/a` and another worktree `/tmp/a-b`, substring check passes false positive.

**Fix:** Parse porcelain: lines `worktree <path>` exact match.

#### Gap M3: PROFILES token counting uses registry.all_specs() which may not exist

**Problem:** `ToolRegistry` might not have `all_specs()` method, only `names()` and `lookup()`. Need to check `registry.py`.

**Fix:** Implement `def all_specs(self): return [self.lookup(name) for name in self.names()]` or use existing.

#### Gap M4: Skill trigger verb substring matching false positive

**Current:** `if trig.lower() in task_lower`

**Problem:** Trigger "pr" matches "prepare", "repo" matches "report".

**Fix:** Use word boundaries regex: `re.search(r'\b' + re.escape(trig) + r'\b', task_lower)`.

#### Gap M5: Phase 1 scope creep — PromptComposer 4+1 breakpoints not needed for v0.1

**Problem:** Anthropic allows up to 4 cache_control breakpoints, but Phase 1 only needs 1 (last cacheable). Implementing 4+1 adds complexity without ROI.

**Fix:** For Phase 1, single breakpoint on last cacheable message. Document 4+1 as future Phase 2.

## Tightened Plan — What to Change

1. **WorktreeManager:** Unified `_sanitize_task_id` deterministic "task" fallback, call once, reuse for path and branch. Add `WorktreeManagerFactory`. Parse worktree list exact.

2. **PROFILES:** Don't filter from baseline. Create `TOOL_BUILDERS` dict with builders that exist. For Phase 1, restrict researcher to existing tools: `["fs.read_file", "fs.instant_grep", "fs.chronicle_search", "fs.usage"]` (all exist). Defer glob/grep tool creation to Phase 2 when we add them.

3. **PromptComposer:** Two-level caching: stable alwaysApply skills in cacheable, conditional globs skills in non-cacheable. Hash only stable part for cache_key. Single breakpoint for Phase 1.

4. **SubagentEnvelope:** Keep in runner.py for Phase 1, don't extract new file. Add spawn limit via SessionState field, not Runner instance.

5. **Skill loader:** Use yaml.safe_load (pyyaml already dep), fallback WARNING. `current_files = transaction.read_set + write_set + instant_grep(task, limit=10)`. Word boundary regex for triggers.

6. **Transaction:** Already done, no change.

7. **FeatureFlags:** Already done, integrate flag check in PromptComposer.

## Verification After Tightening

- [ ] WorktreeManager sanitize deterministic, no leak, path == branch clean_id reuse
- [ ] PROFILES researcher only existing tools, token estimate 600 vs 3000 via chars/4
- [ ] PromptComposer cache_key stable, excludes date, includes only alwaysApply skills hash, single cache_control breakpoint
- [ ] SubagentEnvelope stays in runner, spawn limit enforced via SessionState, artifact write ok
- [ ] Skill loader uses yaml.safe_load, current_files = transaction + instant_grep, word boundary triggers

## Risks Mitigated

- Worktree leak → fixed deterministic fallback + single call reuse
- Tools missing → fixed by restricting to existing tools for Phase 1
- Cache incorrect → fixed two-level caching
- Surface bloat → fixed keep envelope in runner
- Frontmatter parse fail → fixed yaml.safe_load + WARNING fallback
- Skill overload → fixed current_files precise + word boundaries
- Spawn limit bypass → fixed SessionState counter

## Next Steps After Review

1. Ask user pivoting decisions (5 questions below)
2. Update detailed plan file with tightened fixes
3. Proceed to coding Phase 1 modules in order: WorktreeManager helper → PROFILES registry builder → Skill loader → PromptComposer → SubagentEnvelope spawn limit → Integration tests
