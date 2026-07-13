---
title: "Substrate Formalization, Topology Complexity Quote, and Reduction Possibility"
source:
  - "Paper 2 §4.4 Patterns and Trends — Topology complexity inversely correlates with harness-state formality"
  - "Paper 2 §4.3 Shared Code-Centric Harness Substrate"
  - "knowledge/project-overview.md §1.1 Four Pillars, §1.2 Minimalism-first, §1.2.5 Compliance-by-construction"
  - "src/fa/inner_loop/loop.py, registry.py, prompt.py, state.py, artifacts.py, projection.py"
  - "src/fa/inner_loop/hooks/*, src/fa/workspace/worktree_manager.py (planned), src/fa/blackboard/blackboard.py (planned), src/fa/telemetry/telemetry.py (planned)"
  - "knowledge/research/adr-13-14-implementation-plan-2026-07-11-v2-production.md"
compiled: "2026-07-11"
chain_of_custody: "Verified quote from final-review-gaps-high-roi-metaharnesses-july2026.md Gap analysis and Paper 2 p47-48. Inspected current repo: knowledge/ layout, src/fa/inner_loop/*, knowledge/skills/README.md, knowledge/adr/, knowledge/anti-patterns/, HANDOFF.md, AGENTS.md Pre-flight checklist. Enumerated substrate after applying all features from plan via reading skeletons src/fa/runtime/, src/fa/memory/, src/fa/workspace/, src/fa/blackboard/, src/fa/telemetry/."
goal_lens: "Answer user question: What do I think about quote 'Topology complexity is symptom of missing formal substrate' for First-Agent? Should it be закреплено near axes/pillars? What will substrate be after all features? Is there breaking point? Consolidation possibility? Reduction?"
tier: stable
---

## 0. The Quote and My Honest Take for First-Agent

> **Topology complexity inversely correlates with harness-state formality: Systems with explicit formal shared substrates use simpler topologies (L2MAC simple chain + sophisticated state management). Implicit-state systems develop elaborate adaptive topologies (dynamic DAGs, workflow mutation, agent pool scaling) as workaround. Topology complexity is symptom of missing formal substrate.**

**My take for First-Agent: This quote is 100% true for your project, and you are at the exact inflection point where it bites.**

Current First-Agent workflow is simple chain: `INIT → PLANNING → PLAN_READY → CODING → EVALUATING → DONE` + repair/replan branches. That's L2MAC-like: simple chain, not elaborate DAG.

But your planned ADR-13/14 adds topology complexity to fix token efficiency and 124 steps problem:
- Main stateful PTY + 1 subagent shared dir → future 2-3 parallel isolated worktrees + PtyPool maxSize=3 + ThreadPool batching + Fleet parallel + async subagents tree (Cursor 3.2 /multitask) + fan-out spawn now wait later.

**Outside-the-box senior question:** Do we need parallel subagents tree if shared state were formally queryable?

- Researcher subagent's job: "find files mentioning AuthMiddleware" — that's exactly what `fs.instant_grep` FTS5 trigram does, <50ms, substring search, returns paths not content. If substrate is queryable (instant grep index), no need separate agent, just tool call.
- Verifier subagent's job: "run pytest -k test_login -x" — that's deterministic sensor, not agent. Could be tool `fs.verify` with structured JSON result, not separate agent.
- Code-reviewer subagent: could be static analysis tool with structured output.

**Thus:** Adding subagents is workaround for missing formal substrate (instant grep index, verification sensors, blackboard with read_set/write_set). If substrate were formal, simple chain planner→coder→eval could stay simple.

**This is exactly what senior teams do:** L2MAC file store D external persistent never overwritten but extended, Control Unit manages reads/writes, provides precisely controlled context window, not elaborate topology. SoA partitions task state across agents each bounded slice, but global consistency sacrificed.

**For First-Agent, the quote predicts:** If you keep adding parallel agents, worktree isolation, fleet, without formal blackboard, you will hit same bugs as Claude Code #55708 #47548 #31546: parent HEAD switched, CWD remains inside deleted worktree path, nested worktree creation, isolation:worktree param silently ignored with full write access. Those bugs are symptom of missing transactional semantics, not missing topology.

**Conclusion:** Quote is correct and highly relevant. It should be added as principle.

### Should It Be закреплено Near Axes/Pillars?

**Yes, as §1.2.6 Substrate Formality Principle (or §1.2.6 Topology Simplicity Principle), next to minimalism-first (§1.2) and compliance-by-construction (§1.2.5).**

**Proposed wording for `knowledge/project-overview.md`:**

```markdown
### 1.2.6. Substrate Formality Principle — formal substrate before topology complexity

> **Principle, not goal.** When you feel need to add parallel agents, dynamic DAGs, workflow mutation, agent pool scaling, fleet, or elaborate adaptive topologies to fix token efficiency, context window, or coordination problems, first check if missing formal shared substrate would allow simple chain to work:
> - Is shared state formally queryable, versioned, content-hashed, with read_set/write_set/assumptions/version_dependencies declared per action?
> - Is blackboard append-only, never overwritten, with Control Unit managing reads/writes, content-addressed, with toolchain digests and schema versions for reproducibility?
> - Can instant grep / semantic search / verification sensors answer the question without spawning subagent?
> - Can conflict be detected via transactional semantics (read_set overlaps write_set) rather than via file-level isolation?
>
> If answer is No to any, fix substrate first. Topology complexity is symptom of missing formal substrate.
>
> **Invariants:**
> - I-6.1: Every write declares read_set, write_set, assumptions, version_dependencies (base commit, llms.txt hash)
> - I-6.2: Blackboard is append-only, content-hashed, queryable, with detect_conflict()
> - I-6.3: No silent overwrite: second agent writing same file without coordination → Conflict detected, not silent file overwrite, returns structured ToolResult.fail code "conflict_detected"
> - I-6.4: Simple chain planner→coder→eval is default; parallel subagents only when substrate formal and task is embarrassingly parallel with non-overlapping write_sets
```

**Where to place:** In `knowledge/project-overview.md` §1.2 Enforceable principles, after §1.2.5 compliance-by-construction, as §1.2.6. Also add to `knowledge/adr/DIGEST.md` as principle reference, and to `AGENTS.md` §Industry-proven rules as Rule 6.

**ROI of adding as principle:** Prevents future scope creep into elaborate DAGs (EvoMAC, SEW) before formal substrate proven. Forces question "Can formal blackboard + instant grep solve this without new agent?" per minimalism-first 4-question test.

---

## 1. What Will Be Substrate After Applying All Features from Plan?

Let's enumerate verifiably by reading current code + planned skeletons.

### Current Substrate (Before Plan) — Implicit/File-Only + Some Repository-Based

From `knowledge/README.md` layout + `src/fa/inner_loop/`:

**Layer 0: Immutable Filesystem Canon (Human-Readable, Git-Able, Versioned)**

- `knowledge/adr/ADR-*.md` — architectural decisions, fixed
- `knowledge/research/*.md` — research notes with frontmatter v1/v2, Decision Briefing
- `knowledge/skills/*/SKILL.md` — per-task disciplines, triggers verb-based, frontmatter name,description,status,triggers,last-reviewed
- `knowledge/prompts/*.md` — prompts, RESOLVER.md, architect-fa.md, architect-fa-compact.md
- `knowledge/anti-patterns/AP-*.md` — named anti-pattern catalog
- `knowledge/overview/FEATURES.md` — pitch
- `knowledge/templates/` — fa.env.template, config.yaml.example, models.yaml.example
- `knowledge/trace/exploration_log.md` — alternatives rejected
- `AGENTS.md` — universal session loadout, pre-flight checklist, context-budget discipline, industry-proven rules
- `HANDOFF.md` — current state tables, Next priority
- `knowledge/llms.txt` — one-fetch index, MUST READ FIRST 5 files, BY-DEMAND INDEX full list
- `knowledge/glossary.md` — canonical definitions
- `src/fa/inner_loop/prompt.py` — PLANNER/CODER/EVAL system prompts constants
- `src/fa/inner_loop/registry.py` — ToolRegistry, ToolSpec, ToolResult, ToolCall, JSON Schema validation via fastjsonschema, max_context_bytes
- `src/fa/inner_loop/tools/*` — run_bash, base, bash_env, etc.
- `src/fa/inner_loop/hooks/*` — HookRegistry, GuardMiddleware, PauseGuard, CapabilityGuard, SandboxHook, ApprovalHook, AuditHook, VerifierObserver, LearningObserver, LoopGuard, RateLimitBlocker, RecoveryActionObserver, AttemptHistoryObserver, IntentGuard
- `src/fa/hygiene/pr_intent.py` — closed-enum classifier RESEARCH/ADR-RULE/IMPLEMENT/FIX/CHORE

**Layer 1: Ephemeral Session Clones (Isolated RW Workspaces)**

- `/repo` RO mount + `/sessions/<id>` git clone --local per session, isolated RW workspaces, entrypoint creates clone
- `src/fa/inner_loop/state.py` — EventLog, SessionState
- `src/fa/inner_loop/artifacts.py` — ArtifactStore content-addressed per-run artifact store for full payloads elided from model context
- `src/fa/inner_loop/projection.py` — project_for_model, context budget enforcement, head/tail elision
- `src/fa/inner_loop/runtime_limits.py` — RuntimeLimits from ~/.fa/config.yaml
- `src/fa/inner_loop/workflow_artifacts.py` — EvalReport, EvalFinding, StepResult, FlowState (from fa-workflow-loop plan)

**Layer 2: Execution Feedback (Deterministic Sensors, Not LLM)**

- `fs.run_bash` → subprocess.run with scrubbed env, timeout
- Test execution pytest, cargo test, npm test (via bash)
- Static analysis: mypy, ruff, semgrep (via bash)
- Cost Guardian (planned), SecretGuard, SecretRedactor, Sandbox secret_paths
- `src/fa/output.py` EventBus + OutputEvent + ConsoleRenderer

**Layer 3: Implicit Shared State (Reconstructed from Conversational History)**

- `events.jsonl` EventLog — tool_call/tool_result paired rows, hook_decision rows, run_stopped rows, audit trail replay-complete, but no content hashes, no read_set/write_set, no version_dependencies
- `observations` list in SessionState — list of summaries
- `HANDOFF.md` snapshot for cross-LLM sessions
- No formal blackboard, no queryable index beyond grep -ril

**Problem:** Majority resides in implicit/file-only category per Paper §4.3.1: shared harness as simply current code file, no persistent queryable representation, agents cannot reason about shared substrate except through narrow lens of most recent context window, state divergence invisible.

### After Plan (All Features) — Formal Shared Substrate Added But Still Many Components

From `adr-13-14-implementation-plan-2026-07-11-v2-production.md` + skeletons:

**Layer 0: Immutable Filesystem Canon (Same as Before, Still Human-Readable)**

- Same as above, plus new skills with globs frontmatter `globs, alwaysApply`

**Layer 1: Ephemeral Session Clones + Worktree Isolation (Enhanced)**

- `/repo` RO + `/sessions/<id>` clone + `.fa/worktrees/<id>` via WorktreeManager SharedDir v0.1 → Isolated future `git worktree add .fa/worktrees/<id> -b agent/<id> origin/main`, defensive checks path exists, worktree list contains, branch already checked out fail-fast, CWD lock, cleanup assert not exists + prune
- `src/fa/workspace/worktree_manager.py` — WorktreeManager ABC, SharedDir, Isolated, sanitized branch names, transactional read_set/write_set declarations

**Layer 2: Execution Feedback + Sandboxed Execution (Enhanced)**

- PtyPool Map<id, PtySession> maxSize=2 (main+1 sub) LRU + fail-fast PoolExhaustedError never reuse main, shared libtmux.Server injected, fallback pexpect with WARNING, sentinel |||FA_READY|||, ANSI strip, exit code parsing, send_ctrl_c
- EventStream Runtime FastAPI + PtyPool (if direct_fastapi chosen) POST /execute, /send_ctrl_c, /list, /kill, /health, USER fa, healthcheck, thin client run_bash.py `requests.post` with timeout 2s fallback to in-process + WARNING
- Verification-driven tools: verifier subagent pytest, static analysis, security scanner, performance profiler (future)
- Permissioned state transition: read-only tier (repo browsing, retrieval, static inspection), sandbox-edit tier (local patching, test execution), full-access tier (network, credentials, deployment, package publishing) guarded by HITL gates (ApprovalHook)

**Layer 3: Formal Blackboard + Structured Telemetry (NEW Phase 0.5) — The Formal Substrate**

- `src/fa/blackboard/blackboard.py` — BlackboardEntry with content_hash sha256, toolchain_digest (python version, mypy version, model id), schema_version (Task IR v1, Plan Artifact v2), parent_id, read_set List[str], write_set List[str], assumptions List[str], version_dependencies Dict[str,str] (base_commit, llms.txt hash), timestamp, payload Any. Methods write() append-only never overwrite content-addressed, read(id), query(type, key) queryable, detect_conflict() where read_set overlaps write_set of concurrent entry. Store `.fa/blackboard/blackboard.jsonl` append-only, Control Unit managing reads/writes (L2MAC file store D), each entry stamped with digests for reproducibility (MACOG blackboard)
- `src/fa/telemetry/telemetry.py` — TelemetryEvent structured: run_id, turn, prompt_tokens, completion_tokens, cost_usd, model_id, tool_name, tool_args sanitized, permission_tier, edited_files, test_result PASS/FAIL, cache_hit, latency_ms, branch_decision, rejected_alternatives, human_approval, artifact_id (reference to full output offloaded to ArtifactStore, not raw log). Write to `.fa/telemetry/telemetry.jsonl` one line per tool call, <1k chars per line, 500-char preview in active context, not 100k raw logs. Offload full outputs to ArtifactStore content-addressed (already have artifacts.py)
- `src/fa/inner_loop/artifacts.py` — ArtifactStore content-addressed per-run store for full payloads elided from model context, already exists
- `src/fa/inner_loop/compaction/foundation.py` — CompactionManager Stage 1 warning 70% + offload 8000 chars → scratch file + 500-char preview, foundation for ADR-15 full 5-stage (80/85/90/99%)

**Layer 4: Index and Memory (Enhanced)**

- `src/fa/memory/fts_index.py` — InstantGrepIndex FTS5 trigram with DELETE then INSERT, mtime tracking, stale cleanup, fallback porter with WARNING. Tool `fs.instant_grep` returns paths <50ms substring search "auth"→"AuthMiddleware", not content, token efficient
- `src/fa/memory/__init__.py`
- Semantic Memory: repository-specific program-structured evidence (class definitions, function impls, call relations) via glob, grep, instant_grep, future ast_grep
- Experiential Memory: `attempt_history.py` sliding-window JSON writer + `RecoveryActionObserver` + governed experience replay (MemGovern quality-controlled, not scale)
- Long-Term Memory: skill library `knowledge/skills/*` typed versioned plan fragments with proof-carrying bundle reference, not raw snippets, frontmatter name,description,status,triggers,globs,alwaysApply
- Multi-Agent Memory: Shared blackboard, EventLog, ArtifactStore, FlowState, EvalReport, SubagentEnvelope
- Working Memory: SessionState observations + structured prompt regions + state summaries + failed-test records

**Layer 5: Planning and Orchestration (Enhanced)**

- PromptComposer with cacheable split BASE+AGENTS.md map+tool defs per role + non_cacheable task+memory_summary+observations, cache-key = role_id + hash(names+schemas) + hash(agents_map), to_anthropic cache_control ephemeral, to_openai prompt_cache_key retention 1h
- Profiles dynamic toolset: researcher [glob,grep,read,instant_grep] 600 tokens vs full 3000, verifier [bash], main full
- SubagentRunner with scrubbed env extra_allow X_FA_PROXY_TOKEN foundation for Gap 7 arbiter, filtered history (task + relevant files from instant_grep, not full parent 124 steps), JSON validation cached via fastjsonschema, artifact write `.fa/subagents/<id>.json`
- Task worklog `task_worklog.md` per task Goal, Evidence, Steps, Verification aggregated from JSONs, for PR → PR body, not only pr.prepare
- SubagentEnvelope full schema Goal, Verification, Risks, token_usage, duration_ms, next_action, validation
- Tool batching parallel read-only via ThreadPoolExecutor max 5, writes sequential, log write sequential with Lock, EventLog thread-safe
- FlowState MVP, EvalReport with verdict + route decision return_to_coder/return_to_planner/complete/blocked, retry budgets, adaptive routing

**Layer 6: Observability, Governance, Evolution**

- EventBus + OutputEvent + ConsoleRenderer per-turn progress to stderr timing, tokens, cache hit ratio, tool actions with verbs
- `fs.chronicle_search`, `fs.usage`, `fs.list_tasks` tools for Pillar 3 KPI
- `fs.send_ctrl_c` tool
- HookRegistry: GuardMiddleware, ObserverMiddleware, Decision, lifecycle dispatch BEFORE_TOOL_EXEC, AFTER_TOOL_EXEC, BETWEEN_ROUNDS
- Builtin guards: PauseGuard, CapabilityGuard, SandboxHook, ApprovalHook, AuditHook, VerifierObserver, LearningObserver, LoopGuard identical-call repeat + same-path thrash, RateLimitBlocker, LockfileBlocker, AuthExpiredBlocker, IntentGuard bashlex AST → BashIntentEffect
- Change contract template for Evolution Agent: which component modified, failure mode targeted, improvement predicted, invariants preserved, evaluation that can falsify, rollback plan, HITL required for permission boundaries
- Govemance: permission tiers read, sandbox-edit, full-access with mandatory HITL gates, context-sensitive permissions (same command safe in disposable sandbox but unsafe in production repo), human feedback as durable harness state (approvals update permission rules)

**Count:** After plan, substrate will be ~30+ components interacting with each session and pending subagents: artefacts, traces, anti-patterns, research, adr, memory tiers, prompts, skills, guardrails at all stages, roles, tool schemas, blackboard, telemetry, FTS index, worktrees, PtyPool, subagent envelopes, task worklogs, FlowState, EvalReport, PromptComposer, FeatureFlags, RuntimeLimits, etc.

### Breaking Point? Yes.

Each component created with good intentions, both need and want. Interaction complexity N^2.

- EventLog + ArtifactStore + Blackboard + Telemetry all store tool results, but with different formats: events.jsonl paired rows, artifacts/ content-addressed, blackboard.jsonl content-hashed with read_set/write_set, telemetry.jsonl structured with artifact_id. Four storages for same tool result.
- Skills + Prompts + ADR + Anti-patterns + Research + Glossary all markdown files with frontmatter, but different loaders: skills on demand by verb, prompts once at session start, ADR always read, anti-patterns via grep, glossary via grep. Five loaders for markdown files.
- Roles + Tool schemas + Guardrails + Profiles + WorktreeManager all interact: role determines toolset, toolset determines cache-key, cache-key determines prompt caching, guardrails check tool permissions, worktree manager checks branch, blackboard checks conflict.
- Subagents: researcher needs instant_grep, verifier needs bash, but both need scrubbed env, proxy_token, filtered history, JSON envelope validation.

Breaking point is when adding new component requires updating 5-6 other components. E.g., adding instant_grep tool requires: register in ToolRegistry, add to PROFILES researcher, add to prompt_composer cacheable, add to tool_batching parallel list, add to FTS index, update llms.txt BY-DEMAND INDEX, update DIGEST.md, update HANDOFF.md.

### Consolidation Possibility — Reduction

**Senior teams would consolidate all these into unified substrate: Typed, Versioned, Content-Hashed, Queryable Artifacts with Single Loader.**

**Proposal: Unify All Knowledge Types Under Blackboard with Schema Versioning**

All of artefacts, traces, anti-patterns, research, adr, memory tiers, prompts, skills, guardrails, roles, tool schemas are actually same thing: **typed, versioned, content-hashed, queryable artifacts with read_set/write_set**.

- ADR = type: adr, schema_version: v1, payload: {decision, consequences}, read_set: [], write_set: ["knowledge/adr/ADR-13.md"], assumptions: []
- Skill = type: skill, schema_version: v1, payload: {name, description, triggers, globs, alwaysApply, body}, read_set: files it applies to, write_set: []
- Prompt = type: prompt, schema_version: v1, payload: {role, system_prompt}
- Anti-pattern = type: antipattern, schema_version: v1
- Research note = type: research, with frontmatter v1+v2 tier, links, mentions, confidence, goal_lens, topic
- ToolSpec = type: tool_spec, schema_version: v1, payload: {name, description, input_schema, permission}
- Guardrail = type: guardrail, read_set/write_set
- Role = type: role, payload: {system_prompt, tools, max_tokens}

Then single storage: Blackboard `.fa/blackboard/blackboard.jsonl` is index over markdown files, not replace them. Filesystem canon markdown files remain human-readable source of truth, git-able, diff-reviewable (filesystem-canon principle from project-overview). Blackboard is queryable index with content_hash + read_set/write_set, built via `index_repo()` similar to FTS index.

**Loader consolidation:**

Instead of 5 loaders (skills verb-based, prompts once, ADR always, anti-patterns grep, glossary grep), single loader:

```python
def load_artifacts(type: str, query: str, current_files: List[Path]) -> List[BlackboardEntry]:
  # Query blackboard for type=skill where globs matches current_files or triggers matches verb
  # Returns list sorted by rank
```

- Skills: query type=skill where globs matches current_files or triggers matches verb
- Prompts: query type=prompt where role == current_role
- ADR: query type=adr always (but cached)
- Anti-patterns: query type=antipattern where file path matches?

**Reduction of surface:**

- Keep filesystem canon markdown files as human-readable source (per project-overview hybrid-shape filesystem-canon Markdown + lazy search-side scaling)
- Blackboard as formal, queryable, versioned, content-hashed index over them, with transactional semantics
- Telemetry as structured, offloaded, with artifact_id references, not raw logs
- EventLog remains audit trail, but could be seen as blackboard type=tool_result
- ArtifactStore remains content-addressed store for full payloads
- FlowState, EvalReport, SubagentEnvelope, Task Worklog are all blackboard entries with different types

**Resulting Substrate After Reduction (Formalized):**

**Layer 1: Immutable Filesystem Canon (Source of Truth)**

- `knowledge/**/*.md` + `src/**/*.py` — git-able, human-readable, versioned. Each file content_hash sha256, mtime tracked.

**Layer 2: Formal Blackboard Index (Queryable, Transactional)**

- `.fa/blackboard/blackboard.jsonl` append-only, content-hashed, with Control Unit managing reads/writes
- Each entry: id, type (adr, skill, prompt, antipattern, research, tool_spec, guardrail, role, plan, execution, evaluation, flowstate, tool_result, file_version, telemetry, subagent_envelope, task_worklog), content_hash, toolchain_digest, schema_version, parent_id, read_set, write_set, assumptions, version_dependencies, timestamp, payload
- Methods: write, read, query(type, key), detect_conflict
- Metrics: merge success, belief divergence |Bk-Sk|

**Layer 3: Ephemeral Session Clones + Worktree Isolation (Transactional)**

- `/sessions/<id>` git clone --local + `.fa/worktrees/<id>` via WorktreeManager, with Transaction read_set/write_set, defensive checks

**Layer 4: Execution Feedback (Deterministic Sensors)**

- pytest, mypy, ruff, semgrep, OPA, cost sheets, policy traces, static logs — all produce structured CE JSON, routed via Error-to-Edit mapper E: CE→Δ minimal

**Layer 5: Index and Memory (Queryable Evidence Space)**

- FTS5 trigram instant grep + BM25 + future vector, AST-based chunking, iterative query rewriting
- Semantic, experiential (quality-controlled), long-term (validated commits), multi-agent (shared blackboard)

**Layer 6: Planning as Contract + PEV Loop + Governed Mutation**

- Plan Artifact contract with relevant files, invariants, validation commands, rollback points, risky ops
- PEV loop: Plan externalizes intended change + validation criteria, Execute inside sandboxed permissioned env, Verify via deterministic sensors + human-review gates
- Evolution Agent with change contract + rollback + HITL for permission boundaries

**Count After Reduction:** 6 layers, each with clear owner, instead of 30+ components. Interaction complexity O(layers) not O(components^2).

**Minimalism-first check:**

- Removing what makes this redundant? Each of the 30+ components (artefacts, traces, anti-patterns, research, adr, memory tiers, prompts, skills, guardrails, roles, tool schemas) is partially redundant: they all are typed markdown files with frontmatter, need queryable index, need read_set/write_set, need versioning.
- What capability is lost if artefact omitted? If we unify under blackboard, we lose separate directories, but keep files, just add index.
- Open-source precedent for not having it? L2MAC has file store D external persistent never overwritten but extended/revised, Control Unit manages reads/writes, precisely controlled context window — single store, not 5 loaders. So precedent for unified store exists.

**Conclusion:** Yes, there is breaking point, consolidation possible via Formal Blackboard as unified substrate.

---

## Recommendation: Add Quote as Principle and Implement Reduction via Blackboard

**Add to project-overview.md §1.2.6:**

> **Substrate Formality Principle — formal substrate before topology complexity**
> 
> When you feel need to add parallel agents, dynamic DAGs, workflow mutation, agent pool scaling, fleet, or elaborate adaptive topologies to fix token efficiency, context window, or coordination problems, first check if missing formal shared substrate would allow simple chain to work.
> 
> Topology complexity is symptom of missing formal substrate.

**Invariants:**

- I-6.1 Every write declares read_set, write_set, assumptions, version_dependencies
- I-6.2 Blackboard append-only, content-hashed, queryable, detect_conflict()
- I-6.3 No silent overwrite: second agent writing same file without coordination → Conflict detected, returns fail code conflict_detected
- I-6.4 Simple chain planner→coder→eval is default; parallel subagents only when substrate formal and task is embarrassingly parallel with non-overlapping write_sets

**For next session:**

- Implement Phase 0.5 Formal Blackboard + Structured Telemetry first (1.5 days), before Phase 1 foundation abstractions, because it reduces complexity and enables simple chain to stay simple, avoiding need for elaborate topology.
- Then evaluate if parallel subagents tree still needed: if instant_grep + verification sensors + blackboard queryable can answer researcher/verifier tasks without separate agent, you can keep simple chain and save 2-3 days of parallel implementation.

