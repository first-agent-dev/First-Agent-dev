# ADR-14 — Multitask Subagents: Worktree Isolation, Toolset per Role, Instant Grep, JSON Envelope

- **Status:** proposed
- **Date:** 2026-07-11
- **Deciders:** owner + FA agent
- **Related:** ADR-13 (EventStream Runtime), ADR-7 (Tool Registry), ADR-3/4 (Mechanical Wiki FTS5), ADR-11 (Authoring TCB)

## Context

After ADR-13 Main agent becomes stateful PTY via EventStream Runtime, need to enable Cursor 3.2 /multitask pattern: main breaks task into chunks, async subagents each in git worktree isolated, each with restricted tools and structured JSON result.

Current workflow roles planner/coder/eval share same toolset (~18 tools, ~3000 tokens), no skill globs, no instant grep, `pr.prepare` only for PR tasks. Task "прочитай репозиторий" → 124 steps due to repeated `grep -ril` scanning all files, no fast search, no tool call batching, no restricted toolset, no structured output.

Top-tier trends July 2026:
- Cursor 3.2 /multitask: main breaks into chunks, async subagents each git worktree, 8 parallel, no hard tool call limit.
- Copilot CLI CustomAgents: `Name, Tools=[grep,glob,view], Prompt` isolated context, `list_agents/read_agent/task/write_agent`, fleet parallel, autopilot limit 5.
- OpenAI Sandbox Agents as Tools: each sandbox agent isolated, orchestrator gets structured JSON via `custom_output_extractor`, never sees files.
- Cursor instant grep N-gram DB: trigram index, <50ms substring search, 3 months in prod.
- LangChain subagents pattern: supervisor maintains context, subagents stateless isolated.
- 4 subagent patterns: single-shot, fan-out spawn now wait later, agent pool persistent messaging, teams.

Constraints: Pillar 3 most token/tool-call efficient harness, Pillar 4 iteration via measurement, minimalism-first 4-question test, compliance-by-construction, Level-0 TCB stdlib-only.

Q&A decisions:
- role prompts hybrid base in code + MD overrides `knowledge/skills/<role>/SKILL.md`
- memory keep `knowledge/llms.txt` progressive disclosure + instant grep FTS5 trigram
- toolset dynamic main chooses at spawn
- orchestration hybrid planner writes spawn in Plan
- worklog task_worklog.md per task + JSON envelope full schema (Goal, Verification, Risks)
- skill-writing manual, KPI manual count
- worktree SharedDir v0.1 → Isolated dir future, easy transition via abstraction

## Options considered

### Option A — Keep same toolset for all roles, same worktree shared dir, no instant grep

- Pros: 0 code, simple.
- Cons: Token bloat (18 tools 3000 tokens vs 3 tools 600), no isolation, grep scans all files each time slow, no structured output → context accumulation → 124 steps.

### Option B — Full Cursor-like: 8 parallel isolated worktrees, persistent per agent, merge lock, skill globs alwaysApply false, instant grep trigram, JSON envelope, tool batching (chosen)

- Pros:
  - Token efficient: restricted tools -60%, instant grep -95% on exploration, JSON envelope reduces full stdout to summary.
  - Isolation via worktree prevents file conflicts, fixes Claude Code bugs #55708 #47548.
  - Skill globs keeps tools-in-context low (10-20 specific rules without bloat).
  - Structured JSON enables deterministic validation via fastjsonschema.
  - Tool batching parallel read-only cuts tool-calls 2-3x.
- Cons: +4 files, git worktree mgmt, FTS index maintenance, JSON schema validation.

### Option C — Only worktree, no toolset restriction, no instant grep

- Pros: Fixes isolation only.
- Cons: Still token heavy, no fast search.

## Decision

We will choose **Option B — Full Cursor-like but phased: v0.1 SharedDir + 1 subagent limit + restricted toolset + instant grep FTS5 trigram + JSON envelope full schema + skill globs foundation, future IsolatedWorktree + 2-3 parallel**.

**Phased:**

**v0.1 (Tier 1 High ROI, 1-2 days):**

1. **WorktreeManager Abstraction** with defensive checks raised to Tier 1 per external reviewer:
   - Interface `create_subagent_workspace(task_id)->Path`
   - `SharedDirWorktreeManager`: returns session_root, 1 subagent limit, 100% stable, 0 code.
   - `IsolatedWorktreeManager`: `git worktree add .fa/worktrees/<id> -b agent/<id> origin/main`, separate dir, lock cwd, cleanup `git worktree remove --force`, `git worktree prune`.
   - Defensive checks: after add assert path exists + is_dir + `git worktree list --porcelain` contains new path else fail clear error, before add check if branch already checked out elsewhere → fail fast, CWD lock.

2. **Profiles Dynamic Toolset:**
   ```python
   PROFILES = {
       "researcher": {
           "tools": ["fs.glob", "fs.grep", "fs.read_file", "fs.instant_grep"],
           "max_tokens": 600,
           "stateless": True,
       },
       "verifier": {"tools": ["fs.run_bash"], "max_tokens": 200, "stateless": True},
       "code-reviewer": {"tools": ["fs.read_file", "fs.grep"]},
   }
   ```
   Main chooses at spawn, ToolRegistry per subagent only 1-4 tools, cache-key = role_id + hash(tool_defs) solves internal contradiction.

3. **Instant Grep FTS5 Trigram:**
   - `src/fa/memory/fts_index.py` with `CREATE VIRTUAL TABLE files_fts USING fts5(path, content, tokenize='trigram')`
   - Index `knowledge/` + `src/` at session start, DB `.fa/fts.db`, incremental
   - Tool `fs.instant_grep(query, limit)` → list paths <50ms substring search "auth"→"AuthMiddleware", not content → token efficient.
   - Existing SQLite FTS5 for Mechanical Wiki, sqlite3 stdlib, 0 external deps.

4. **JSON Envelope Full Schema:**
   ```json
   {
     "task_id": "...", "type": "verifier", "goal": "...", "exit_code": 0,
     "summary": "PASS 12 tests", "verification": "pytest exit 0",
     "files_changed": [], "patch_diff": "", "risks": [], "open_questions": [],
     "token_usage": {}, "duration_ms": 3420, "next_action": "none"
   }
   ```
   Validation via fastjsonschema (already used for input_schema), custom_output_extractor Pattern as OpenAI Sandbox.

5. **Skill Globs alwaysApply false:**
   - Extend frontmatter SKILL.md: `globs: ["src/api/**/*.ts"]`, `alwaysApply: false`
   - Loader: if alwaysApply or globs match current files → load else skip. Current skills without globs work as before.

**Future (Tier 4):**

- IsolatedWorktreeManager separate dir + persistent worktrees per agent rotate branches (fast, build caches survive) + merge lock `merge_sequential.sh`.
- Parallel 2-3 via ThreadPool (Pattern 2 Fan-out spawn now wait later).
- Skill lazy loading with globs.
- Security arbiter per-subagent random token rewriting foundation already in WorktreeManager/SubagentRunner accepts separate proxy_token var.

## Consequences

- Positive:
  - Fixes isolation (prevents silent corruption of parent repo as in Claude Code bugs).
  - Token efficient (restricted tools -60%, instant grep -95% on exploration, JSON envelope reduces context).
  - Progressive disclosure already via llms.txt map, enhanced by instant grep.
  - Compliance-by-construction: restricted tools = less blast radius, deterministic Python functions.

- Negative:
  - +4 files, git worktree mgmt, FTS index maintenance, JSON schema validation.

- Follow-up:
  - ADR-15 Full 5-stage compaction.
  - Eval-harness UC5 for Pillar 3 KPI.
  - ADR-12 amendment per-subagent random token rewriting.

## References

- Cursor 3.2 /multitask async subagents each git worktree, 8 parallel [futurumgroup, augmentcode, mindstudio]
- Copilot CLI CustomAgents tool restriction + fleet parallel + list_agents/read_agent [docs.github.com custom-agents + changelog 1.0.41]
- OpenAI Sandbox Agents as Tools custom_output_extractor JSON [daytona docs + developers.openai.com/sandbox]
- Cursor instant grep N-gram 3 months prod (user note) + SQLite FTS5 trigram
- LangChain subagents pattern supervisor stateless subagents isolated [langchain choosing architecture]
- Reddit 4 subagent patterns single-shot, fan-out, pool, teams [Self-OS wiki]
- Claude Code worktree isolation bugs #55708, #47548, #31546 + defensive checks
- final-review-gaps-high-roi-metaharnesses-july2026.md Gaps 4,6,8,10,11
- metaharness-phase1-decisions.md Q&A
