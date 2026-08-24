# Reference — Terms, Features, and Session Architecture

> Single lookup file for agents. Replaces glossary.md, FEATURES.md, and architecture.md.
> For routing rules, see AGENTS.md §Query Routing. For vision/axes/principles, see project-overview.md.

---

## §Quick Ref — Most Common Queries

| Query | Answer |
|-------|--------|
| Where is session state? | `~/.fa/session-log/<run_id>/session.db` (SQLite authority). JSONL mirrors are best-effort. |
| How to read events programmatically? | `session.session_db.read_event_rows()` — never parse JSONL directly for correctness. |
| How to find artifacts/files by content? | `fs_blackboard_query(type="skill")` for typed artifacts; `fs_search(query="auth", output_mode="files", limit=10)` for repo-wide content/path search (S14b.1 unified BM25+trigram). See AGENTS.md §Querying Artifacts. |
| How to see cross-run stats? | `fa stats --global-history` reads `~/.fa/global_history.db`. |
| Is JSONL authoritative? | No. If JSONL and session.db disagree, session.db wins. JSONL is human-readability surface. |

---

## § Terms

Short definitions of terms used in First-Agent and this wiki.

| Term | Description |
|------|-------------|
| **ACI** | Agent–Computer Interface. The minimal surface through which an agent interacts with a computational environment (tools, files, shell). See [`research/cutting-edge-agent-research-radar-2026-05.md`](./research/cutting-edge-agent-research-radar-2026-05.md). |
| **ADR** | Architecture Decision Record. Canonical location: [`knowledge/adr/`](./adr/); process: [`knowledge/adr/README.md`](./adr/README.md). Cheat sheet: [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md). |
| **ADR DIGEST** | One-paragraph cheat-sheet per accepted ADR. Cheap-read overlay; per-ADR file authoritative. Updated in the same PR as any amendment ([`pr-creation` skill §PR Checklist rule #9](./skills/pr-creation/SKILL.md#pr-checklist)). Canonical: [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md). |
| **ADVISORY** | Authoring-guardrail severity that is visible in output but does **not** fail CI (exit 0). Must carry an `expires_on` date or auto-escalate; promotes to *HARD-BLOCK* only after a measured false-positive rate < 1 % on `fp-corpus/`. See [ADR-11 §ADR-11-I2](./adr/ADR-11-authoring-guardrails.md#adr-11-i2--severity-lifecycle-as-a-false-positive-budget). |
| **Agent** | A program that uses an LLM to select a sequence of actions (usually via tool calls) in pursuit of a goal. |
| **Aperant** | OSS reference TypeScript desktop coding-agent. Cited in [`research/gortex-aperant-inspiration-2026-05.md`](./research/gortex-aperant-inspiration-2026-05.md) as primary source for `record_gotcha` / `record_discovery` (R-8), pause-handler sentinel (R-25), bash-validator + path-containment (R-20). FA borrows shape, not code; TS → Python ports preserve atomic-rename idiom + empirically-validated intervals. |
| **Ara protocol** | Four-layer multi-agent research protocol from arXiv:2604.24658v2 (Orchestra Research): Live Research Manager / Compiler / Seal. First-Agent borrows only the `/trace/` *Exploration log* idea (R-1 of the cross-reference); the rest is out of scope for v0.1. See [`research/ara-protocol-cross-reference-2026-05.md`](./research/ara-protocol-cross-reference-2026-05.md). |
| **ArtifactStore** | Content-addressed store at `<workspace>/.fa/artifacts/`. Stores elided tool result payloads as `tool-result-<sha256[:16]>.json`. Keeps `event_log` lean. Lazy-initialized in `SessionState.__post_init__`. Source: `src/fa/inner_loop/artifacts.py`. |
| **Authoring-time guardrail** | Deterministic repository check that fires while writing/reviewing code — before runtime behaviour matters — under the *LLM as Untrusted Compiler* threat model. Enforced by the *Two-tier TCB*. See [ADR-11](./adr/ADR-11-authoring-guardrails.md). |
| **Axis (project)** | High level project axis, synonym for *Pillar* as defined in [`project-overview.md` §1.1](./project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars). Used in phrases such as "follow project axis". |
| **Axis (PR-checklist A/B/C)** | Evaluation criterion in §0 Decision Briefing per [`pr-creation` skill PR Checklist rule #8](./skills/pr-creation/SKILL.md#pr-checklist): (A) reduces session-start noise; (B) helps LLM locate context; (C) advances the selected `goal_lens`. (A) and (B) are stable axes for all notes; (C) is per-session. |
| **Bash sandbox / `bash_gate`** | Layered bash command validator (R-20 in [`research/borrow-roadmap-2026-05.md`](./research/borrow-roadmap-2026-05.md)): Layer 1 pattern classifier; Layer 2 per-command validators; Layer 3 path-containment. v0.2 [ADR-6](./adr/ADR-6-tool-sandbox-allow-list.md) sandbox upgrade. Default-deny with a per-classifier exception list. |
| **Blackboard** | Typed append-only content-hashed store for session state. Entries: `id`, `type`, `content_hash`, `read_set`, `write_set`, `assumptions`, `version_dependencies`. Authority: `session.db.blackboard` table. Mirror: `workspace/.fa/blackboard/blackboard.jsonl` (best-effort). Cannot exist without `SessionDatabase`. Gated by `FeatureFlags.blackboard_enabled`. Conflict detection via `detect_conflict()`. Source: `src/fa/blackboard/blackboard.py`. |
| **BM25 / FTS5** | The v0.1 read-side ranker. SQLite FTS5 in external-content mode with tokeniser `unicode61 remove_diacritics 2` + porter stemmer; default BM25 weights. **No vector layer in v0.1**; v0.2 ADR slot reserved for `sqlite-vec` or a separate `embeddings.sqlite`. See [ADR-4](./adr/ADR-4-storage-backend.md). |
| **Capability flag** | One of five Kronos-style boolean flags (R-21) that gate runtime features. All default `False`; capability enables via config file (audit-able), not runtime decision. Land in v0.2 [ADR-6](./adr/ADR-6-tool-sandbox-allow-list.md) amendment. |
| **Catch-corpus** | Fixture diffs from historical authoring omissions (F-1..F-10) that rules MUST flag — the true-positive baseline a rule must catch before promotion. Lives at `catch-corpus/`. See [ADR-11 §Verification](./adr/ADR-11-authoring-guardrails.md#verification). |
| **Chain of custody** | Provenance rule: when citing a number, date, name, or quote, fetch it from the primary source listed in the note's `source:` frontmatter — **not** from a summary note. Documented in [AGENTS.md §Query Routing](../AGENTS.md#query-routing). |
| **ContextVar DI** | Dependency injection via `contextvars.ContextVar`. `set_current_session(state)` in `drive_session()`; tool handlers call `get_current_session()` → access `session.blackboard`, `session.session_db`. Decouples tools from session lifecycle. Source: `src/fa/inner_loop/context.py`. |
| **Cost guardian** | R-45 middleware as `src/fa/observability/cost_guardian.py`. Single `GuardMiddleware` on `BEFORE_TOOL_EXEC` + `AFTER_TOOL_EXEC`. `cost_budget_usd` tri-mode: `None` unbounded (default), `0.0` observe-only, `> 0` hard cap. Documented in [ADR-7 §Sub-amendment 2026-05-21](./adr/ADR-7-inner-loop-tool-registry.md). |
| **Decision Briefing (§0)** | Mandatory first section of research notes. Eight-field R-N block + 7-column summary table. Lets agents read §0 alone (~150–250 lines) without loading the deep dive. |
| **DPC** | Disentinel Personal Companion — OSS reference Python LLM-agent stack with mature ADR / lessons-learned log. Cited in [`research/dpc-messenger-inspiration-2026-05.md`](./research/dpc-messenger-inspiration-2026-05.md). |
| **Draft PR** | A Pull Request in draft state; CI runs, but it is not marked as ready-for-review. |
| **DSV** | Deterministic State Verification. Post-tool gate that compares LLM-claimed success against actual events and overrides on mismatch. Implementation at `src/fa/verifier/`. |
| **Dual-write authority** | Write discipline: (1) write to SQLite authority first (raises on failure), (2) advance state only after commit, (3) write JSONL mirror best-effort. Both `EventLog` and `Blackboard` follow this pattern. SQLite = machine authority; JSONL = human-readability surface. |
| **Eval / Eval suite** | Reproducible set of inputs + expected behaviour used to measure agent quality between changes. |
| **EventLog** | Append-only event writer. Creates `SessionDatabase` at init. `append()` → `session_db.append_event_row()` (authority) + `events.jsonl` (mirror). `read_all()` → DB first, JSONL fallback. Source: `src/fa/inner_loop/state.py`. |
| **Exploration log** | Telegraphic markdown overlay at [`knowledge/trace/exploration_log.md`](./trace/exploration_log.md). One `## Q-N` block per ADR with `Chosen:` + `Rejected:` carrying `Reason:` + `Lesson:`. |
| **Family extractor** | Pure-function module (`src/fa/roles.py`) that maps LLM model slug to training-distribution family. 10-entry `KNOWN_FAMILIES` frozenset. Raises `FamilyExtractionError` on ambiguous slugs. Enforces [ADR-2 §Amendment 2026-05-20](./adr/ADR-2-llm-tiering.md) family-disjoint rule. |
| **FeatureFlags** | Runtime toggles from `~/.fa/config.yaml`. 13 fields, all with production consumers. Gate Blackboard and Telemetry init. Defaults safe (`blackboard_enabled=True`, `telemetry_enabled=True`). Source: `src/fa/feature_flags.py`. |
| **Feedback loop** | The cycle `action → observation → reflection → next action` — the core pattern of a reliable agent. |
| **Filesystem-canon** | Project convention that durable agent memory lives in ordinary repository files (Markdown / JSON / YAML) instead of opaque service state. |
| **FlowState** | Machine-readable workflow controller state persisted to `flow_state.json`. Records orchestration status, active role, plan version, repair/replan counters. Controller truth for workflow progression. |
| **FP-corpus** | Diffs from recent green commits that rules MUST NOT flag; used to measure false-positive rate (gate < 1 %) before an *ADVISORY* rule promotes to *HARD-BLOCK*. Lives at `fp-corpus/`. |
| **GlobalHistoryStore** | Derived analytics projection at `~/.fa/global_history.db`. Single `runs` table (tokens, cost, duration, tool breakdown). Populated at session end, best-effort, never crashes main. Active consumer: `fa stats --global-history`. NOT imported by hot-path code for correctness. Source: `src/fa/inner_loop/global_history.py`. |
| **goal_lens** | Frontmatter v2 field; one-sentence research goal, elicited at session start. Mandatory for notes from [`prompts/research-briefing.md`](./prompts/research-briefing.md), optional otherwise. |
| **Golden set** | A small, stable, manually annotated set of inputs used for regression evaluation. |
| **HARD-BLOCK** | Authoring-guardrail severity that fails CI (exit 1). Used only for deterministic, low-noise rules. See [ADR-11 §ADR-11-I2](./adr/ADR-11-authoring-guardrails.md#adr-11-i2--severity-lifecycle-as-a-false-positive-budget). |
| **Harness** | Control layer around an LLM: loop / orchestration, prompts, tool registry, retrieval pipeline, sandbox. Pillar 3 is to build the most token/tool-call efficient open-source harness for UC1+UC3. |
| **Hook** | Pre/post-tool extension point formalised by [ADR-7](./adr/ADR-7-inner-loop-tool-registry.md) §8. v0.1 ships `SandboxHook` + optional `ApprovalHook` + `AuditHook`. |
| **HookRegistry** | Registry-driven middleware chain. Two kinds: `GuardMiddleware` (may deny / modify) and `ObserverMiddleware` (read-only). Substrate for Wave 2 work. |
| **I-FROZEN** | Marker for a guarded block whose edits must pass a checker/generator. A mismatch on deterministic regeneration is a *HARD-BLOCK* (ADR-11-I3). |
| **INFO (severity)** | Authoring-guardrail severity for informational findings; never blocks CI. Lowest rung of the `HARD-BLOCK / ADVISORY / INFO` ladder. |
| **Inner-loop** | The Coder ↔ tools cycle: thought → tool-call → observation → next thought. Pinned by [ADR-7](./adr/ADR-7-inner-loop-tool-registry.md). |
| **Knowledge note** | A short trigger note that the agent automatically pulls into all future sessions. |
| **Kronos** | OSS reference "agent OS" implementing identity-preserving compaction (R-9), 5-flag capability opt-in (R-21), recursive PII walker (R-22, deferred). FA borrows shape. |
| **L0 / L1 / L2 (memory tiers)** | Progressive-disclosure retrieval tiers: **L0** = filename/title/tag grep; **L1** = SQLite FTS5 BM25; **L2** = vector / graph (deferred to v0.2). v0.1 ships L0+L1 only per [ADR-3](./adr/ADR-3-memory-architecture-variant.md) + [ADR-4](./adr/ADR-4-storage-backend.md). |
| **Lens** | See *goal_lens*. |
| **Level 0 kernel / Level 1 rule (authoring TCB)** | Two-tier authoring-check split (ADR-11): **Level 0** = frozen, stdlib-only, offline kernel; **Level 1** = the allowlisted semantic rule packs it dispatches. |
| **LLM agent** | See *Agent*. |
| **LLM as Untrusted Compiler** | ADR-11 threat model: the LLM author can edit the guardrails in the same patch as the code they constrain. |
| **MCP** | Model Context Protocol — a JSON-RPC shaped contract between an MCP host (agent) and MCP server. FA v0.1 implements a **convention** (in-process dispatcher), not a dependency. |
| **Mechanical Wiki** | v0.1 memory architecture variant ([ADR-3](./adr/ADR-3-memory-architecture-variant.md)): filesystem-canonical Markdown + YAML frontmatter, deterministic chunker, SQLite FTS5 read-side. **No embeddings, no graph, no Mem0.** |
| **Minimalism-first** | Project principle ([`project-overview.md` §1.2](./project-overview.md#12-enforceable-principle--minimalism-first)): every proposed harness component passes a 4-question test before addition. Contrast: *Subtraction-first*. |
| **Module** | A self contained unit of agent code located at `src/<name>/` with its own tests and README. |
| **NLAH** | Natural-Language Agent Harness — an externalised, editable natural language artifact describing harness behaviour. Source: Tsinghua `arXiv:2603.25723`. |
| **Pause sentinel** | Filesystem-canonical pause/resume primitive: orchestrator writes `RATE_LIMIT_PAUSE` or `AUTH_PAUSE`; human/frontend writes `RESUME` to unblock. Empirically-validated intervals. |
| **Phase R / S / M** | Build lifecycle: **R** = Research (exit with reviewed plan); **S** = Scaffolding (feedback loop standing); **M** = Module creation (current, iterative). |
| **Pillar** | One of 4 project goal pillars. Synonym *Project axis*. |
| **PRD** | Product Requirements Document. For First-Agent this is a short markdown file under `docs/prd/`. |
| **Prompt** | An instruction sent to an LLM. Reusable prompts are stored in `knowledge/prompts/`. |
| **Portable Tool Schema (PTS-v1)** | Closed provider-neutral authoring profile for `ToolSpec.input_schema`: scalar types object/array/string/integer/number/boolean and the keywords `type`, `properties`, `required`, `items`, `enum`, `description`, `default`, length/numeric bounds, and `additionalProperties`. The same schema is compiled locally and sent to providers; nullable unions, combinators, references, and unknown keywords fail registration. Source: [ADR-7 amendment 2026-08-16](./adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-08-16--portable-tool-schema-v1-single-authority). |
| **Provenance frontmatter** | Mandatory `source:` + `compiled:` (+ `chain_of_custody:` when citing facts) on every research note. Schema in [`knowledge/README.md`](../README.md). |
| **R-N / Q-N** | Notation in research notes and the exploration log: `R-N` = numbered recommendation (TAKE / SKIP / DEFER / UNCERTAIN-ASK); `Q-N` = open question. |
| **R-S-M** | Lifecycle: Research → Scaffolding → Module. See *Phase R / S / M*. |
| **ReAct** | Reasoning + Acting loop — the ubiquitous agent orchestration pattern: thought → action → thought. |
| **Reflexion / Critic / Reflector** | Inner-loop role that reviews its own output. **v0.1 has no Critic**; failure handling is intra-role retry per [ADR-2 amendment 2026-04-29](./adr/ADR-2-llm-tiering.md). |
| **RuntimeLimits (per-role iteration keys)** | S14b.2: `~/.fa/config.yaml` `runtime_limits:` block accepts five per-role keys — `max_iterations_planner/_coder/_eval` (live) and `max_iterations_researcher/_code-reviewer` (stubs, parsed but never applied until a runtime driver exists). Cap semantics are **per turn** (one `run_session` invocation = one LLM response batch), not per session. Code defaults: `ROLE_ITERATION_DEFAULTS` = **99 per turn for all roles** — a TESTING-STAGE anchor (operator decision 2026-08-17) that the operator will re-tune after the testing stage; `DEFAULT_MAX_ITERATIONS = 6` remains the ADR-7 anchor for role-less callers. Resolution seam: `_cmd_run` → `resolve_limits_for_role` (`src/fa/inner_loop/runtime_limits.py`). |
| **StructuralIndex / fs_reach** | S16: lazy, thread-safe Python call-graph index at `<workspace>/.fa/structural.db` (tables `symbols`, `calls`, `struct_meta`) + the `fs_reach` navigation tool (callers/callees BFS; exact-suffix resolution; `§`-anchor lookup; unresolved callees reported as `<unresolved:…>`; in-file-only resolution in v1). Sources: `src/fa/memory/structural_index.py`, `src/fa/inner_loop/tools/fs_reach.py`. |
| **Scheduled session** | A cron-like recurring agent session — e.g. weekly eval run. |
| **Seam (authoring)** | Declared boundary of intended edits for an authoring session (`.fa/session.toml`). First seam rule: *staged paths ⊆ declared seam* (ADR-11-I8). |
| **Self-evolving** | Agent writes its own `SKILL.md` files at session end. v0.1 commitment per Pillar 4; design in TBD ADR-8. |
| **SessionDatabase** | Per-run authoritative SQLite database at `~/.fa/session-log/<run_id>/session.db`. Three tables: `event_log`, `blackboard`, `session_meta`. Thread-safe via `threading.Lock` + short-lived connections + WAL. Created by `EventLog.__init__`; shared with `Blackboard` and `SessionState`. Source: `src/fa/inner_loop/session_db.py`. |
| **Session Insights** | Post-session analytics: timeline, cost, suggestions for prompt improvement. |
| **Skill** | A `SKILL.md` file — a procedure that the agent knows how to execute. v0.1 commitment: agent capability to write its own skills (Pillar 4). |
| **Soviet-code** | OSS reference npm-published agent harness. Cited for declarative per-role tool whitelist (B-NEW-1) and Phase-M runner pattern. |
| **Subtraction-first** | Design rule (Anthropic): remove components when measurements show they're no longer effective. **Retrofit** strategy. FA selected *Minimalism-first* (prevention). |
| **Symmetric reading** | Pre-flight rule ([AGENTS.md §Pre-flight Step 3](../AGENTS.md#pre-flight-checklist)): before citing a research note, `grep -ril "<key-term>" knowledge/research/` and read every match. |
| **TAKE / SKIP / DEFER / UNCERTAIN-ASK** | Verdict tokens used in §0 Decision Briefing. **TAKE** = act in v0.1; **SKIP** = reject with reason; **DEFER** = revisit in v0.2; **UNCERTAIN-ASK** = block on user. |
| **Tool call** | A structured request from an LLM to invoke a named tool with typed arguments. |
| **Tool Registry** | The collection of `ToolSpec` entries the Coder LLM is allowed to invoke. Pinned by [ADR-7](./adr/ADR-7-inner-loop-tool-registry.md). Three-tier disclosure per ADR-7 §6. |
| **Transaction** | Accumulates `read_set`/`write_set` during a session. Always initialized (unlike Blackboard, which is conditional). Feeds into Blackboard entries for conflict detection. Source: `src/fa/inner_loop/transaction.py`. |
| **Two-tier TCB** | Authoring-guardrail Trusted Computing Base: frozen *Level 0 kernel* + allowlisted *Level 1 rules*. See [ADR-11 §Decision](./adr/ADR-11-authoring-guardrails.md#decision). |
| **UC1 — UC5** | Use case labels from [`project-overview.md` §4](./project-overview.md#4-scope) + [ADR-1](./adr/ADR-1-v01-use-case-scope.md). |
| **Vector DB** | Database for similarity search over embeddings. Not used in v0.1. |

---

## § Features

### Session Database Authority

Every `fa run` creates a per-run SQLite database (`session.db`) that is the single source of truth for hot-path runtime state. Three tables hold the complete session history, blackboard entries, and metadata. JSONL files exist as human-readable mirrors — if they disagree with session.db, session.db wins. For operator-facing details, see `knowledge/instructions/02-operations.md`.

### Blackboard Conflict Detection

When `edit_file` or `write_file` writes, the Blackboard checks for conflicts: if entry B's `read_set` overlaps with a prior entry A's `write_set`, and A was written after B started reading, `detect_conflict()` returns a structured failure. This prevents the "parent HEAD switched" bug (Claude #55708).

### Cross-Run Analytics

`fa stats --global-history` reads `~/.fa/global_history.db` — a derived projection populated at session end. Not hot-path authority; purely analytics.

### Egress-Injection Proxy (ADR-12)

API keys live only in a separate `fa-egress-proxy` container. Agent reaches providers through the proxy (HTTP + non-key token); proxy injects the real key. Agent can *use* keys but never *read* them.

### Trusted Computing Base (ADR-11)

Two-tier authoring TCB: frozen stdlib-only Level-0 kernel + allowlisted Level-1 rules. LLM as Untrusted Compiler threat model. Test-decay lock prevents `pytest.skip` / `assert True` gaming.

### Bash Intent Analysis

`fs_run_bash` is parsed through `bashlex` AST. IntentGuard classifies: `READ_ONLY`, `INDEX_WRITE`, `REPO_WRITE`, `DANGEROUS`. REPO_WRITE blocked without authorized PR draft.

### Token-Efficient Retrieval

Mechanical Wiki: filesystem-canon Markdown + SQLite FTS5 BM25. No vector DB, no embeddings in v0.1. Tools have `max_context_bytes` with automatic head/tail elision.

---

## § Patterns

### Feedback Loop (П1)

Action → Observation → Reflection → Next Action. The core agent pattern. Tests after edits, linter, typechecker = the feedback loop made deterministic. First reliable agent pattern; everything else builds on it.

### Planning Before Execution (П2)

1. Parse requirements. 2. Explore codebase. 3. Plan (files, risks, tests). 4. Execute step-by-step. 5. Deliver.

### Escalation (П3)

`task_is_clear → execute() / task_is_ambiguous → ask() / task_exceeds_capability → report()` — three modes, never guess.

### Memory Taxonomy

| Type | Purpose | FA Location | CogSci Analog |
|------|---------|-------------|---------------|
| Session | Current task context | SessionState, observations | Working |
| Persistent | Cross-session facts | knowledge/ (filesystem-canon) | Semantic |
| Procedural | Step-by-step procedures | skills/ (SKILL.md) | Procedural |
| Episodic | Session outcomes | global_history.db, HANDOFF.md | Episodic |

### Stable vs Volatile Knowledge

| Type | Location | Policy |
|------|----------|--------|
| Stable (architecture, ADRs) | knowledge/adr/, knowledge/ | Synthesize once, rarely changes |
| Semi-stable (research) | knowledge/research/ | Update on significant findings |
| Volatile (session logs) | ~/.fa/session-log/ | Synthesize on demand only |

---

## § Session Data Layout

For the operator-facing description of session data, see `knowledge/instructions/02-operations.md`.

### Per-run artifacts (~/.fa/session-log/<run_id>/)

| File | Role | Authority |
|------|------|-----------|
| `session.db` | SQLite: event_log + blackboard + session_meta | **Yes** |
| `events.jsonl` | JSONL mirror of event_log | No (best-effort) |
| `pr_draft.md` | PR draft artifact | Standalone |
| `eval_report.json` | Workflow eval verdict | Standalone |
| `flow_state.json` | Workflow controller state | Standalone |
| `attempt_history.json` | Recovery attempt log | Standalone |

### Workspace artifacts (<workspace>/.fa/)

| Path | Role | Authority |
|------|------|-----------|
| `blackboard/blackboard.jsonl` | JSONL mirror of session.db.blackboard | No (best-effort) |
| `artifacts/` | Content-addressed tool result offloads | Complements event_log |
| `subagents/<task_id>.json` | Subagent spawn results | Standalone |
| `fts.db` | FTS5 full-text search index | Disposable cache |

### Cross-run artifacts

| Path | Role |
|------|------|
| `~/.fa/global_history.db` | Derived analytics. `fa stats --global-history` |
| `~/.fa/config.yaml` | FeatureFlags + runtime config |
| `~/.fa/models.yaml` | Unified routing config |

### Initialization chain

```
fa run → _cmd_run() → EventLog(path, run_id) → SessionDatabase(session.db)
       → SessionState(log, run_id, workspace) → __post_init__:
           session_db = log.session_db (shared instance)
           FeatureFlags from ~/.fa/config.yaml
           Transaction (always)
           ArtifactStore (lazy)
           Blackboard (lazy, requires session_db + flag)
           TelemetryLogger (lazy)
       → drive_session(state) → set_current_session(state)
       → Tools: get_current_session() → session.blackboard, session.session_db, ...
```

### Authority hierarchy

1. **session.db** — single source of truth for hot-path state
2. **JSONL mirrors** — best-effort, human-readable, for audit/diff
3. **global_history.db** — derived projection, never imported for correctness
4. **File artifacts** — standalone, not replicated in DB
