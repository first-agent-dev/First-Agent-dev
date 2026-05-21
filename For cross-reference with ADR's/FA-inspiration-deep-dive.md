# Deep-Dive: `zzet/gortex` + `AndyMik90/Aperant` → Inspiration for First-Agent (FA)

> Research-only brief. No PR, no code changes. Goal: surface the most useful files in each repo for FA's minimalism-first, filesystem-canonical, role-routed harness — and explain *why* each one matters.

---

## TL;DR — what each repo gives FA

| Repo | One-line | What FA can steal |
|------|----------|-------------------|
| **`zzet/gortex`** | Go-native code-intelligence daemon + MCP server that wires itself into 15 AI agents. | (1) **Bloat/staleness audit of agent config files** — a working implementation of FA's "Mechanical Wiki" hygiene story. (2) **Adapter pattern** for emitting per-agent config (CLAUDE.md, .cursorrules, AGENTS.md, …) from one centralized spec. (3) **MCP-tool-table-as-instruction** ("Instead of X, you MUST use Y") that operationalizes ACI / ADR-7. (4) **Marker-fenced regenerable blocks** in CLAUDE.md so generated and human content coexist. |
| **`AndyMik90/Aperant`** | Electron app that runs an autonomous planner→coder→QA pipeline + heavy GitHub PR-review automation. | (1) **A full library of role-routing prompts** (planner / coder / qa_reviewer / qa_fixer / spec_*; plus ~20 GitHub-workflow prompts: pr_orchestrator, issue_analyzer, pr_security_agent, finding_validator, bot_detector, etc.). (2) **Filesystem-canonical learning loop** (`record_discovery` / `record_gotcha` tools writing to `memory/codebase_map.json` and `memory/gotchas.md`) — almost exactly FA's Mechanical Wiki idiom. (3) **Phase-protocol orchestration** (planning → coding → qa_review → qa_fixing with validated transitions) — concrete blueprint for FA's Phase R/S/M. (4) **Worktree-isolation pattern** for safe agent edits + AI-powered semantic merge. |

If you only read three files in each repo, read these:

**Gortex** (in priority order):
1. `internal/audit/bloat.go` — quantified bloat scoring for markdown agent configs.
2. `internal/audit/audit.go` + `internal/audit/tokens.go` + `internal/audit/discover.go` — the full "are my CLAUDE.md / AGENTS.md references still real?" pipeline.
3. `internal/agents/instructions.go` — the marker-fenced, centrally-defined instruction body shared across 15 agents.

**Aperant** (in priority order):
1. `apps/desktop/prompts/github/pr_orchestrator.md` (and `pr_followup_orchestrator.md`) — the highest-density example of role-routed PR review.
2. `apps/desktop/src/main/ai/tools/auto-claude/record-{gotcha,discovery}.ts` — minimal filesystem-canonical learning hooks.
3. `apps/desktop/src/main/ai/orchestration/build-orchestrator.ts` + `spec-orchestrator.ts` — concrete phase-protocol implementation with validated transitions.

---

## Part 1 — `zzet/gortex`

### What it actually is

Go code-intelligence engine. Indexes a repo into an in-memory knowledge graph (tree-sitter–driven, 256 languages, 62 MCP tools), runs as a daemon, and exposes itself to 15 AI coding assistants (Claude Code, Cursor, Kiro, Windsurf, Cline, Aider, Codex, Gemini, OpenCode, Continue, Antigravity, VS Code/Copilot, Zed, Kilo Code, OpenClaw) via MCP. The big idea: replace `Read`/`Grep` for indexed source with one `smart_context` call.

Two CLI commands carry the agent-integration story:
- `gortex install` — user-level setup (writes `~/.claude.json`, `~/.gemini/...`, etc.).
- `gortex init` — per-repo setup (writes `.mcp.json`, `.cursor/mcp.json`, marker-fenced blocks in CLAUDE.md/AGENTS.md, per-community `SKILL.md` files).

The `Detect → Plan → Apply` adapter contract makes every integration pluggable.

### Ranked file list for FA

#### Tier 1 — directly portable to FA (high signal, low LOC, immediately useful)

1. **`internal/audit/bloat.go`** *(158 LOC)*
   Heuristic 0–100 bloat score for any markdown agent-config file. Counts lines, long lines (>200 chars), duplicate bullets, list nesting depth, code blocks. Soft cap at 600 lines, hard cap at 1500.
   → **FA application**: This is FA's "Mechanical Wiki minimalism KPI" made concrete. Lift the scoring directly into a `fa audit` or `fa hygiene` command that runs over `knowledge/`, `AGENTS.md`, `hot.md`, etc. and rejects PRs that push score above a threshold. Especially relevant given FA's "subtraction-first" principle.

2. **`internal/audit/audit.go`** *(201 LOC)*
   The orchestrator. Walks every configured doc, extracts every backticked token, classifies each as `tokenSymbol` / `tokenPath` / `tokenOther`, then graph-validates symbol refs and stat-checks path refs.
   → **FA application**: FA already has a symbol graph implicit in `knowledge/llms.txt` + ctags chunker. Build the same audit but against FA's chunker-derived index. The output structure (`StaleRef[]`, `DeadPath[]`, `BloatMetrics`, `Suggestions[]`) is a clean schema for FA's pre-flight checklist.

3. **`internal/audit/tokens.go`** *(156 LOC)*
   The cleverest piece. Classifies backticked tokens with conservative heuristics — requires uppercase OR `::` qualifier OR explicit `()` suffix to count as a symbol, so it doesn't false-positive on tool names like `search_symbols` or option keys like `older_than`. Hard skip list for common shell verbs (`grep`, `ls`, `git`, …).
   → **FA application**: FA's docs are full of backticked tool names, ADR refs, file paths. Steal this classifier wholesale — it's exactly the heuristic you'd otherwise reinvent badly.

4. **`internal/audit/discover.go`** *(83 LOC)*
   `DefaultConfigPaths()` returns the canonical probe list: `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, `.cursorrules`, `.cursor/rules/`, `.github/copilot-instructions.md`, `.windsurfrules`, `.antigravity/rules`, `.aider.conf.yml`.
   → **FA application**: FA's equivalent is `AGENTS.md` + `knowledge/llms.txt` + `hot.md` + `HANDOFF.md`. Add a small `fa hygiene discover` that walks the standard FA wiki paths plus this list (so FA self-audits even if users drop in foreign agent files).

5. **`internal/agents/instructions.go`** *(576 LOC)*
   Central constant `GlobalInstructionsBody` ⇒ identical text written into ~/.claude/CLAUDE.md, AGENTS.md, .cursor/rules, etc. with **marker fences**:
   - `<!-- gortex:rules:start -->` … `<!-- gortex:rules:end -->` — regenerable rule block.
   - `<!-- gortex:communities:start -->` … end — regenerable codebase-routing block.
   - `## MANDATORY: Use Gortex MCP tools` — sentinel string for idempotency checks.
   → **FA application**: FA needs *exactly this* if it ever wants to manage `AGENTS.md` and `CLAUDE.md` (and the like) from a single source. Marker fences + sentinel are the minimum-viable contract for "I'll overwrite my own block, leave yours alone." This solves a recurring FA pain (drift between AGENTS.md and knowledge/prompts/).

#### Tier 2 — architectural patterns worth lifting

6. **`internal/agents/agents.go`** *(182 LOC)*
   `Adapter` interface: `Name() / DocsURL() / Detect() / Plan() / Apply()` with `Mode = Project | Global` and an `Env` struct carrying `Root`, `Home`, `HookCommand`, `Stderr`, `SkillsRouting`, `GeneratedSkills`. Every external-agent integration implements this.
   → **FA application**: When FA grows beyond "we generate AGENTS.md and that's it" — e.g. when it needs to emit a `.cursor/rules` block or a Cline rules file from the same source of truth — this `Detect/Plan/Apply` + `--dry-run` shape is the right contract. Particularly the `Plan()` separation: it lets CI lint what *would* be written without touching disk.

7. **`internal/skills/generator.go`** *(298 LOC)*
   Builds per-community `SKILL.md` files from graph-analysis output, plus a routing table written between markers in CLAUDE.md. Demonstrates the "structurally-derived skills, not handwritten" angle.
   → **FA application**: FA's prompt templates in `knowledge/prompts/` could be (partially) generated from chunker output — community-detection-lite over module boundaries. Less immediate than the audit pieces, but it's the right north star if FA wants prompts to track the codebase automatically.

8. **`CLAUDE.md`** (root, 245 LOC)
   The reference instance of "instructions as ACI table." Every section is `| Instead of... | You MUST use... |`. Forces the model into graph-tool-first behavior. Plus a numbered "Session start" checklist (`graph_stats` → `index_repository` → `smart_context` → `get_editing_context` → `verify_change` → `check_guards`).
   → **FA application**: FA's ADR-7 inner loop deserves this treatment. The "Session start" 1–10 checklist is a near-perfect rendering of FA's Pre-flight Checklist concept — copy the structure, replace tool names. Critically, the table format is far more terse than prose for an LLM context window (matches FA's minimalism-first).

9. **`docs/agents.md`** *(254 LOC)*
   The adapter matrix table: 15 agents × `What gets written` × `Mode` × `Docs link`. Demonstrates how to make a multi-agent harness *legible* in one page.
   → **FA application**: When FA adds even one external agent target (Claude Code? Cursor?), copy this table verbatim. Single source of "what does FA touch on disk for which agent" beats scattered prose.

10. **`internal/llm/agent/agent.go`** *(307 LOC, build-tagged `llama`)* + **`internal/llm/agent/tools.go`** *(109 LOC)*
    A self-contained, grammar-constrained tool-calling loop on top of llama.cpp. Tools emit JSON `{"tool": "...", "args": {...}}`, agent feeds observations back, terminates on `final_answer`. Includes `ChatTemplate` abstraction (ChatML vs Llama-3) and two tool tiers: `GortexTools` (local) and `GortexChainTools` (cross-repo).
    → **FA application**: FA already has its own ReAct loop. This is mostly confirmatory — but the `ChatTemplate` abstraction (BOS / system / user / tool / `AssistPrime`) is a clean way to swap model families without rewriting the loop. Also a good reference for "when the user wants a *local* planner tier without going to a hosted Claude/GPT."

#### Tier 3 — interesting context, lower priority

- **`cmd/gortex/init.go`** *(415 LOC)* — orchestrates `Detect/Plan/Apply` across all 15 adapters with flags for `--dry-run`, `--agents=<csv>`, `--agents-skip=<csv>`, `--no-hooks`, `--json`. Good reference for FA's CLI surface if it ever has multi-target install.
- **`.gortex.yaml`** *(45 LOC)* — tiny config file (`index.languages`, `index.exclude`, `watch.*`, `query.default_depth`, `mcp.transport`). Compare to FA's `.fa.yaml` (if any). Reminder: simple YAML beats a 200-line settings module.
- **`eval/`** — full SWE-bench-Lite evaluation harness with `agents/gortex_agent.py`, `prompts/{system,instance}_*.jinja`, `bridge/`, `environments/`, `analysis/`. If/when FA wants empirical "does the harness actually help?" data, this is the template.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — minimal (20 lines): Summary / Changes / Testing / Checklist with one repo-specific item ("Language extractor includes `Meta[\"methods\"]`"). Counter-example to over-templated PRs (see Aperant's 103-line template below).

### What FA can ignore from Gortex

- The whole `internal/parser/`, `internal/graph/`, `internal/indexer/`, `internal/semantic/` stack — FA doesn't (and shouldn't) build a tree-sitter–based knowledge graph. Stick with ctags + markdown-it.
- The 62-tool MCP surface (`internal/mcp/*.go`) — FA's ACI is leaner by design.
- The Go-specific build/release infra (`.goreleaser.yml`, supply-chain hardening).

---

## Part 2 — `AndyMik90/Aperant` (formerly Auto-Claude)

### What it actually is

Electron desktop app that runs an autonomous multi-agent pipeline: user states a goal → spec creation (complexity_assessor → spec_gatherer → spec_writer → spec_critic) → planner → coder (parallel subagents) → qa_reviewer → qa_fixer → user reviews & merges. All work happens in isolated git worktrees. AI layer is built on Vercel AI SDK v6 (TS-first) with multi-provider support (Anthropic / OpenAI / Google / Bedrock / Azure / Mistral / Groq / xAI / Ollama).

The most FA-relevant piece is **not** the Electron shell. It's:
1. The `apps/desktop/prompts/` directory — a dense, battle-tested library of role-routed agent prompts.
2. The `apps/desktop/src/main/ai/` TypeScript module — a clean reference implementation of phase-based orchestration, security validation, and filesystem-canonical learning.

### Ranked file list for FA

#### Tier 1 — directly portable (Aperant's gold for FA)

1. **`apps/desktop/src/main/ai/tools/auto-claude/record-gotcha.ts`** *(78 LOC)*
   Append-only writer to `<specDir>/memory/gotchas.md` with timestamped sections (`## [YYYY-MM-DD HH:MM]\n<gotcha>\n_Context: ..._`).
   → **FA application**: This *is* FA's Mechanical Wiki, miniaturized. Drop-in pattern for a `fa record gotcha` tool that writes to `knowledge/trace/gotchas.md` (or wherever FA tracks rejected paths). Five-minute port.

2. **`apps/desktop/src/main/ai/tools/auto-claude/record-discovery.ts`** *(90 LOC)*
   JSON keyed by `file_path`, value = `{description, category, discovered_at}`, written atomically (`.tmp` + `rename`). Bounded growth (one entry per file).
   → **FA application**: Exactly what FA needs for "I learned what `src/fa/foo.py` does — don't re-read it next session." Pair with `gotchas.md` and you have FA's L1 memory tier. Use the same atomic-rename idiom.

3. **`apps/desktop/prompts/github/pr_orchestrator.md`** *(435 LOC)*
   Hardened PR-review system prompt. Forces three-phase review (Understand → Deep Analysis → Verify), with a section on "**Never classify a PR as trivial and skip analysis**" backed by a real war story (a 1-line PR with 9 latent issues). Explicit subagent-dispatch playbook (`spawn_security_review`, `spawn_quality_review`, `spawn_deep_analysis`).
   → **FA application**: Pull the *structure* (not the verbatim text) into FA's `knowledge/prompts/code-review.md` and equivalents. The "war story → discipline" framing is a high-leverage way to encode lessons learned into prompts without growing them unbounded.

4. **`apps/desktop/prompts/github/pr_followup_orchestrator.md`** *(364 LOC)*
   PR-follow-up-review orchestration with strict scope rules (in-scope: changes in this PR + their impact; out-of-scope: pre-existing issues, code from merged sub-PRs identified by `(#N)` patterns). Plus a four-specialist task tool dispatch (`resolution-verifier`, `new-code-reviewer`, `comment-analyzer`, `finding-validator`).
   → **FA application**: FA struggles with the same "is this finding from my diff or from main?" question. The scope-policing language here is reusable verbatim. The four-specialist split also maps cleanly to FA's role-routing model.

5. **`apps/desktop/prompts/github/issue_analyzer.md`** *(112 LOC)* + **`issue_triager.md`** *(199 LOC)*
   Pre-spec issue intake. `issue_analyzer.md` extracts `requirements`, `acceptance_criteria`, `affected_areas`, `complexity` (simple/standard/complex), `risks`, `needs_clarification` into a strict JSON schema. `issue_triager.md` classifies issue category (bug/feature/docs/question/duplicate/spam/feature_creep) with explicit confidence thresholds (80%/75%/70%).
   → **FA application**: If FA ever wants to manage its own GitHub issues automatically, these are the right starting prompts. The JSON-schema-first output also matches FA's preference for structured agent emissions.

6. **`apps/desktop/src/main/ai/runners/github/pr-creator.ts`** *(392 LOC)*
   Minimal viable AI-PR-creator: push branch → gather diff → `generateText()` with a tight system prompt (Summary / Changes / Testing sections) → `gh pr create`. Uses `createSimpleClient()` (no tools, single turn).
   → **FA application**: Direct reference for FA's "open a PR with body X" automation. Particularly the **single-turn `generateText()` for PR descriptions** pattern — don't burn an agent loop on something that's a deterministic one-shot.

7. **`apps/desktop/src/main/ai/runners/github/triage-engine.ts`** *(302 LOC)*
   Structured-output triage via Vercel AI SDK `Output.object()` with a Zod schema. Returns `{issueNumber, category, confidence, labelsToAdd, labelsToRemove, isDuplicate, duplicateOf, isSpam, priority, comment}`.
   → **FA application**: Reference for *any* time FA wants structured agent output. The Zod-schema + `Output.object()` pattern (or its Python/Pydantic equivalent) gives you parser-free outputs at the cost of one extra schema definition.

8. **`apps/desktop/src/main/ai/runners/github/bot-detector.ts`** *(309 LOC)*
   Prevents infinite loops in agent-driven GitHub automation: tracks `reviewed_commits`, `last_review_times`, `in_progress_reviews` in a JSON state file. Cool-off period (1 minute) between re-reviews. Stale-in-progress timeout (30 minutes). Skips PRs authored by the bot.
   → **FA application**: As soon as FA starts driving its own PRs/comments on `Bupitsa-ai/First-Agent-debloat`, you'll need this. Five-minute port of the state-file pattern saves you from a "Devin reviews itself reviewing itself" disaster.

9. **`apps/desktop/prompts/planner.md`** *(901 LOC)* + **`coder.md`** *(1147 LOC)* + **`qa_reviewer.md`** *(652 LOC)* + **`qa_fixer.md`**
   The canonical planner/coder/qa role-routing prompt set. Each has a `## YOUR ROLE` header, a `## YOUR CONTRACT` (inputs/outputs), explicit phases (Phase 0 → … → Phase N), and a `MANDATORY` rule that the agent must `Write()` a specific output file or the phase fails.
   → **FA application**: This is the single best public reference for FA's role-routing concept. Especially valuable:
   - The **"YOUR CONTRACT"** framing forces input/output discipline.
   - The **"MUST call Write tool — describing the output doesn't count"** rule is exactly the bind FA needs: orchestrator validates by checking the filesystem, not by parsing model text.
   - The **path-confusion-prevention** sections in `coder.md` (forbidden absolute paths, doubled-path warnings in monorepos, `pwd` checks) are universal LLM coder failure modes — copy verbatim.

10. **`apps/desktop/src/main/ai/orchestration/build-orchestrator.ts`** *(788 LOC)* + **`spec-orchestrator.ts`** *(742 LOC)*
    The phase machine. `build-orchestrator.ts` defines `BuildPhase = 'planning' | 'coding' | 'qa_review' | 'qa_fixing'`, `PHASE_AGENT_MAP` mapping each phase to its agent type, `MAX_PLANNING_VALIDATION_RETRIES = 3`, `MAX_SUBTASK_RETRIES = 3`, validated transitions via `isValidPhaseTransition()` from `phase-protocol.ts`. `spec-orchestrator.ts` adds **complexity-tier-conditional pipelines**: SIMPLE = `[quick_spec, validation]`, STANDARD = `[discovery, requirements, spec_writing, planning, validation]`, COMPLEX = full pipeline with research and self-critique.
    → **FA application**: This is FA's "Phase R/S/M" rendered concretely. Specifically:
    - Use the **complexity-conditional phase list** to keep simple tasks from running the heavy pipeline (matches FA's minimalism-first).
    - Use the **`MAX_PHASE_OUTPUT_SIZE = 12_000`** constant to bound how much of one phase's output is carried into the next — a hard backpressure mechanism on context bloat.
    - Use the **`onStepFinish` callback for progress tracking** — gives FA a deterministic place to update `hot.md` between steps.

#### Tier 2 — patterns worth knowing

11. **`apps/desktop/src/main/ai/orchestration/qa-loop.ts`** *(630 LOC)*
    QA review → fix iteration with `MAX_QA_ITERATIONS = 50`, `MAX_CONSECUTIVE_ERRORS = 3`, `RECURRING_ISSUE_THRESHOLD = 3` (escalate to human after the same issue recurs 3 times). Reads `QA_FIX_REQUEST.md` for human feedback injection.
    → **FA application**: FA's QA loop needs the same circuit breakers. The "recurring-issue threshold ⇒ escalate" pattern is what stops a Devin/agent from spinning forever on a flaky test.

12. **`apps/desktop/src/main/ai/orchestration/parallel-executor.ts`** *(273 LOC)*
    `Promise.allSettled()` over concurrent `runAgentSession()` calls. Rate-limit detection with exponential back-off (`RATE_LIMIT_BASE_DELAY_MS = 30_000`, max 300_000). 1-second stagger between concurrent launches. Per-call failure isolation.
    → **FA application**: When FA spawns sub-agents (e.g. multiple researchers in Phase R), use this exact pattern. The stagger is non-obvious but real — back-pressure against burst rate limits.

13. **`apps/desktop/src/main/ai/security/bash-validator.ts`** *(300 LOC)* + **`path-containment.ts`** *(147 LOC)* + **`security/denylist.ts`**, **`secret-scanner.ts`**, **`validators/`**
    Pre-tool-use security model: denylist-based bash validation (allow-by-default with per-command validators for `rm`, `chmod`, `git`, `pkill`, `psql`, etc.) plus path-containment (resolves symlinks, lowercases on Windows, blocks `..` traversal).
    → **FA application**: FA's sandbox (ADR-6) deserves the same denylist + per-command-validator approach. Especially relevant for the `git config user.email` and `rm /` cases the validators catch.

14. **`apps/desktop/prompts/spec_writer.md`** *(307 LOC)* + **`spec_gatherer.md`** + **`spec_critic.md`** + **`spec_researcher.md`**
    The full spec-creation pipeline prompt set. `spec_writer.md` enforces a strict template (Overview / Workflow Type / Services / Files to Modify / Files to Reference / Acceptance Criteria / Implementation Strategy / Risks). `spec_critic.md` is the self-critique pass.
    → **FA application**: Maps directly onto FA's Phase R (Research) and Phase S (Scaffolding). The template-enforced output is the right antidote to FA's spec sprawl risk.

15. **`apps/desktop/prompts/github/pr_security_agent.md`**, **`pr_quality_agent.md`**, **`pr_logic_agent.md`**, **`pr_codebase_fit_agent.md`**, **`pr_finding_validator.md`**, **`pr_structural.md`**, **`pr_template_filler.md`**
    The specialist set the `pr_orchestrator` dispatches to. Each is single-purpose, narrowly scoped, with explicit input format and output JSON shape.
    → **FA application**: Reference for "split a long prompt into specialists, dispatch with structured output." Even if FA doesn't do PR review, this is the canonical example of role-routing in production.

16. **`apps/desktop/src/main/ai/orchestration/subagent-executor.ts`** *(197 LOC)*
    `generateText()` (not `streamText()`) for subagents because their output flows back to the orchestrator's context, not the UI. Cap at `SUBAGENT_MAX_STEPS = 100`. Excludes the `SpawnSubagent` tool from sub-agent tool sets to prevent recursion.
    → **FA application**: The "no streaming for sub-agents" + "remove spawn-tool from spawned agent" rules are non-obvious correctness fixes. Steal both.

17. **`apps/desktop/src/main/ai/config/agent-configs.ts`** *(608 LOC)*
    Single registry of `AgentType → tools → MCP servers` mapping. Phase-aware model resolution (`thinking_low` / `thinking_medium` / `thinking_high`). Per-agent tool restriction (e.g. `SPEC_TOOLS = [Read, Glob, Grep, Write, WebFetch, WebSearch]` — no `Edit`, no `Bash`).
    → **FA application**: FA's role-routing currently assigns models per role. This file shows that you also want to assign *tools* per role — `spec_*` agents can't accidentally `Bash`, `coder` can; this is much safer than a single tool list shared across roles.

18. **`apps/desktop/src/main/ai/session/runner.ts`** *(682 LOC)*
    The actual session loop. Key constants: `DEFAULT_MAX_STEPS = 500`, `CONTEXT_WINDOW_THRESHOLD = 0.85` (warn), `CONTEXT_WINDOW_ABORT_THRESHOLD = 0.90` (force-continue), `STREAM_INACTIVITY_TIMEOUT_MS = 60_000`, `POST_STREAM_TIMEOUT_MS = 10_000`. Convergence-nudge agent set (`qa_reviewer`, `spec_critic`, …) gets a "write your verdict NOW" nudge at 75% step budget.
    → **FA application**: Steal the *numbers*. Particularly the 85/90% context-window thresholds and the convergence-nudge concept. The inactivity timeout is also worth keeping for the OpenAI Codex bug it documents.

19. **`apps/desktop/src/main/ai/runners/github/pr-review-engine.ts`** *(724 LOC)* + **`parallel-orchestrator.ts`** *(1028 LOC)*
    Full multi-pass review engine. `ReviewPass = quick_scan | security | quality | deep_analysis | structural | ai_comment_triage`. `ReviewSeverity = critical | high | medium | low`. `ReviewCategory = security | quality | style | test | docs | pattern | performance | verification_failed`. Cross-validation: findings flagged by multiple specialists get severity boosts; the `finding-validator` re-reads actual code to confirm/dismiss.
    → **FA application**: If FA ever does PR review, this is the data model. The "finding-validator" pattern (re-read code to confirm a claim) is *exactly* the kind of "Symmetric Reading" FA already espouses.

20. **`Memory.md`** *(2156 LOC)*
    Design doc for Aperant's V5 memory system: scratchpad → validated promotion pipeline, hybrid retrieval (BM25 + dense + graph), tree-sitter AST chunking, cross-session pattern synthesis, Turso/libSQL backend, embedding strategy.
    → **FA application**: Don't adopt the architecture (FA has explicitly chosen filesystem-canonical over DB-backed). But read sections 1 (Design Philosophy), 5 (Scratchpad-to-Validated Promotion Pipeline), and 12 (Cross-Session Pattern Synthesis) — they're the most articulate public defense of "memory is the moat" that exists, and the failure modes they discuss (cold-start, personal-vs-team conflicts, graph indexing UX) all show up in FA's wiki story.

#### Tier 3 — lower-priority context

- **`.github/PULL_REQUEST_TEMPLATE.md`** *(103 LOC)* — heavily structured (base branch, AI disclosure, platform testing checklist, feature toggle). Counter-point to Gortex's 20-line template. FA should land closer to Gortex's terseness.
- **`.coderabbit.yaml`** — example of how to configure CodeRabbit (assertive review profile, path-specific instructions). Useful if FA ever adds AI-PR-review as a CI check rather than building it from scratch.
- **`scripts/ai-pr-reviewer.md`** — standalone "copy-paste prompt" version of the PR reviewer. Demonstrates the same content packaged for "no infra, just paste into Claude" use.
- **`apps/desktop/prompts/github/duplicate_detector.md`** + **`spam_detector.md`** + **`pr_ai_triage.md`** — narrow specialists for issue/PR hygiene. Optional for FA.

### What FA should explicitly NOT copy from Aperant

- **Electron / React / Zustand UI layer** — irrelevant; FA is a CLI/library.
- **Vercel AI SDK lock-in** — FA's harness is Python; the *patterns* port, the SDK doesn't.
- **Worktree-isolated parallel builds** — overkill for FA's single-user, single-task workflow (the knowledge note says "single-user").
- **Turso / Convex / libSQL memory backend** — directly contradicts FA's Mechanical-Wiki principle (filesystem-canonical Markdown).
- **The 103-line PR template** — too much ceremony for FA. Steal one or two checklist items at most.

---

## Part 3 — Concrete recommendations for FA

Cross-referenced against the FA concepts surfaced in the knowledge index (Mechanical Wiki, Minimalism-first, Subtraction-first, Role-Routing, Exploration DAG, Goal-lens, ACI, ADR-7, Sandbox, Chunker, SLIDERS, Phase R/S/M, Symmetric Reading, Pre-flight Checklist, L0/L1/L2).

### Highest-leverage borrows (do these first)

| FA concept | Borrow from | What |
|---|---|---|
| **Mechanical Wiki hygiene / Pre-flight Checklist** | `gortex/internal/audit/{bloat,audit,tokens,discover}.go` (~600 LOC total) | Port the bloat scorer + token classifier to Python. Run `fa hygiene` over `knowledge/`, `AGENTS.md`, `hot.md`, `HANDOFF.md`. Fail PR / refuse to start a session if bloat score >70 or stale-ref count >5. |
| **L0/L1 memory tier** | `aperant/.../auto-claude/record-{gotcha,discovery}.ts` (~170 LOC total) | Two tools, filesystem-canonical: `fa record-gotcha "..."` appends to `knowledge/trace/gotchas.md`; `fa record-discovery <file> "..."` upserts JSON in `knowledge/wiki/codebase_map.json`. Atomic write + rename. |
| **Role-Routing prompts** | `aperant/apps/desktop/prompts/{planner,coder,qa_reviewer,qa_fixer,spec_*}.md` | Read for the **"YOUR CONTRACT"** + **"MANDATORY: Write tool"** structure. Rewrite FA's `knowledge/prompts/` to enforce the same shape. Single source of "what files must exist after this agent runs" beats parsing model text. |
| **Phase R/S/M, validated transitions** | `aperant/apps/desktop/src/main/ai/orchestration/build-orchestrator.ts` + `phase-protocol.ts` | Adopt validated phase transitions (refuse to enter Phase M without Phase S artifacts). Use `MAX_PHASE_OUTPUT_SIZE` to bound carry-over. Complexity-tier-conditional pipelines from `spec-orchestrator.ts` keep the harness minimal for simple tasks. |
| **ACI — instructions as tool-routing table** | `gortex/CLAUDE.md` + `gortex/internal/agents/instructions.go` | Reformat `AGENTS.md` to use `\| Instead of X \| You MUST use Y \|` tables instead of prose. Add a numbered "Session start" checklist (1–10). Bracket the generated parts with marker fences so human and machine content coexist. |
| **Sandbox (ADR-6)** | `aperant/.../security/{bash-validator,path-containment,denylist}.ts` + `validators/` | Replicate the denylist-by-default model with per-command validators for `rm`, `git config`, `chmod`. Path containment with symlink resolution. |
| **Exploration DAG** | `aperant/apps/desktop/prompts/github/pr_followup_orchestrator.md` (scope rules) + `record-gotcha.ts` | The "in-scope vs out-of-scope" framing in `pr_followup_orchestrator.md` is exactly the discipline the Exploration DAG needs. `record-gotcha` is the mechanical write path. |

### Avoid these traps (lessons from both repos)

1. **Don't over-template PRs**: Aperant's 103-line template is a maintenance burden. Gortex's 20-line one is closer to FA's spirit.
2. **Don't store memory in a database**: Both repos hint at this trajectory (Aperant explicitly with Turso, Gortex implicitly with the daemon's snapshot). FA's filesystem-canonical choice is correct; both Memory.md sections 13–14 and Gortex's daemon-state code are good cautionary reading on the complexity that follows.
3. **Don't generate prompts from scratch every session**: Both repos use **marker-fenced regenerable blocks** in existing files (gortex more explicitly). This is the right balance — agents own their generated content, humans own everything outside the markers.
4. **Don't let prompts grow unboundedly**: Aperant's `coder.md` is 1147 lines. That's too long; symptoms include duplicate phase guidance and conflicting rules. The `audit/bloat.go` scorer is what FA should use to keep its own prompts honest.
5. **Don't skip the "write to file" contract**: Both repos enforce "the orchestrator validates by checking disk, not by parsing model text." This is critical for FA — a "Planner agent" that only emits markdown into the response stream is unverifiable.

### Concrete one-line file copies (low-risk starter set)

If you want to start with one PR's worth of borrowing:

1. Port `gortex/internal/audit/bloat.go` → `src/fa/hygiene/bloat.py` (~120 LOC).
2. Port `gortex/internal/audit/discover.go` → `src/fa/hygiene/discover.py` (~60 LOC) with FA's default paths (`AGENTS.md`, `hot.md`, `HANDOFF.md`, `knowledge/llms.txt`, `knowledge/adr/*.md`, `knowledge/prompts/*.md`).
3. Port `aperant/apps/desktop/src/main/ai/tools/auto-claude/record-{gotcha,discovery}.ts` → `src/fa/tools/record.py` (~150 LOC total).
4. Add a `fa hygiene` CLI subcommand that runs both audits and prints the report.
5. Restructure `AGENTS.md` into the `\| Instead of X \| You MUST use Y \|` table format borrowed from `gortex/CLAUDE.md`.

That single PR would land all four highest-leverage borrows in a few hundred lines of Python.

---

## Appendix — file index (paths only, ordered by priority)

### Gortex
```
internal/audit/bloat.go                  # bloat score
internal/audit/audit.go                  # orchestrator
internal/audit/tokens.go                 # token classifier
internal/audit/discover.go               # config path discovery
internal/agents/instructions.go          # central instructions + markers
internal/agents/agents.go                # Adapter interface
internal/skills/generator.go             # per-community SKILL.md
CLAUDE.md                                # ACI table reference instance
docs/agents.md                           # adapter matrix
internal/llm/agent/agent.go              # local agent loop (build-tag llama)
internal/llm/agent/tools.go              # tool bindings
cmd/gortex/init.go                       # multi-adapter init orchestrator
.gortex.yaml                             # minimal config
.github/PULL_REQUEST_TEMPLATE.md         # 20-line PR template
eval/                                    # SWE-bench harness
```

### Aperant
```
apps/desktop/src/main/ai/tools/auto-claude/record-gotcha.ts        # gotchas.md writer
apps/desktop/src/main/ai/tools/auto-claude/record-discovery.ts     # codebase_map.json upserter
apps/desktop/prompts/github/pr_orchestrator.md                     # role-routed PR review
apps/desktop/prompts/github/pr_followup_orchestrator.md            # scope-policed follow-up
apps/desktop/prompts/github/issue_analyzer.md                      # issue → spec JSON
apps/desktop/prompts/github/issue_triager.md                       # issue category + confidence
apps/desktop/prompts/{planner,coder,qa_reviewer,qa_fixer}.md       # role prompts
apps/desktop/prompts/spec_{writer,gatherer,critic,researcher}.md   # spec pipeline prompts
apps/desktop/src/main/ai/orchestration/build-orchestrator.ts       # phase machine
apps/desktop/src/main/ai/orchestration/spec-orchestrator.ts        # complexity-conditional spec pipeline
apps/desktop/src/main/ai/orchestration/qa-loop.ts                  # review/fix iteration + circuit breakers
apps/desktop/src/main/ai/orchestration/parallel-executor.ts        # Promise.allSettled subagent pattern
apps/desktop/src/main/ai/orchestration/subagent-executor.ts        # nested generateText pattern
apps/desktop/src/main/ai/session/runner.ts                         # session loop + context-window thresholds
apps/desktop/src/main/ai/runners/github/pr-creator.ts              # AI PR description generator
apps/desktop/src/main/ai/runners/github/triage-engine.ts           # Zod-schema structured triage
apps/desktop/src/main/ai/runners/github/bot-detector.ts            # self-loop prevention
apps/desktop/src/main/ai/runners/github/parallel-orchestrator.ts   # multi-specialist PR review
apps/desktop/src/main/ai/security/bash-validator.ts                # denylist + per-cmd validators
apps/desktop/src/main/ai/security/path-containment.ts              # path-traversal guard
apps/desktop/src/main/ai/config/agent-configs.ts                   # role → tools registry
Memory.md                                                          # memory architecture (design doc)
CLAUDE.md                                                          # orchestrator-first project rules
scripts/ai-pr-reviewer.md                                          # copy-paste prompt version
```

---

## Addendum (verification pass) — files added after directory re-audit

After the initial brief I re-walked both repos to find anything important that didn't make the first cut. The items below are net-new additions, not restatements. They fall into four buckets: (a) **Gortex hooks / claudemd / workspace** — the parts that actually wire Gortex into Claude Code at runtime; (b) **Gortex `feedback` / `frecency` / `combo`** — the per-symbol learning loop inside the MCP server; (c) **Aperant recovery + pause/resume orchestration** — the parts that make the agent loop survive failure; (d) **Aperant ideation/spec specialists + extra GitHub prompts** — additional role-prompt templates worth lifting wholesale.

Where a file restates a pattern already in the brief, it's listed Tier-3 (reference only). Where it adds a *new* pattern, it's promoted to Tier-1 or Tier-2.

### Gortex — additional Tier-1 files (new patterns)

1. **`internal/hooks/dispatch.go`** *(38 LOC)* + **`internal/hooks/{pretooluse,posttask,sessionstart,precompact,subagent}.go`** *(266 / 316 / 265 / 223 / 101 LOC)*
   Five Claude-Code hook entry points wired through one dispatcher. Each hook receives a JSON payload over stdin and emits either nothing (silent no-op) or a `hookSpecificOutput` block that Claude Code injects as `additionalContext` for the next turn. Critical design rules baked in:
   - `runPreToolUse` — **enriches** every tool call with graph context (e.g. "this file has 14 callers, here are the test targets") AND can **deny** a call by emitting `permissionDecision: "deny"` with a reason. This is the single most powerful integration surface Gortex exposes.
   - `runSessionStart` — injects daemon-status briefing at session start; degrades gracefully (still emits a block when daemon is down, but the block tells the user enforcement is disabled).
   - `runPostTask` (Stop hook) — runs `detect_changes` diagnostics on unstaged changes, injects findings as `additionalContext` so the agent self-corrects before handing off. Has explicit recursion guard (`stop_hook_active`).
   - All hooks degrade **silently** on parse error or daemon-unreachable — they MUST NOT block Claude Code's normal flow.
   → **FA application**: This is the prototype for **FA's ADR-7 pre-flight + post-flight checklists made executable**. FA's current pre-flight is a markdown checklist the LLM may or may not follow. The Gortex hook pattern shows the alternative: pre-flight = an executable that reads stdin (or the LLM's tentative tool call), validates it against the FA sandbox + Mechanical Wiki, and either enriches the context or denies the action. The recursion guards (`stop_hook_active`) and graceful-degradation rules ("never block normal flow") are also directly relevant to FA's ACI design.

2. **`internal/agents/claudecode/adapter.go`** *(408 LOC)* — concrete reference adapter
   First adapter to read end-to-end. `Detect` returns `true` unconditionally (claude-code is the "home" agent); `Plan` branches between `ModeGlobal` (writes to `~/.claude/...`) and `ModeProject` (writes `.mcp.json`, `.claude/settings.json`, `.claude/settings.local.json`, marker-fenced block in `CLAUDE.md`); `InstallHooks` and `InstallGlobalInstructions` are independently togglable. Pairs with `content.go` (471 LOC, the actual markdown bodies), `hooks.go` (395 LOC, hook-registration JSON), `plugin.go` (378 LOC, plugin-mode variant).
   → **FA application**: When (if) FA grows to emit per-agent config (CLAUDE.md, AGENTS.md, .cursorrules, copilot-instructions.md), this adapter — not the abstract interface — is the file to copy. The mode/flag matrix is the part you actually need: most adapter implementations get the basics wrong because they don't separate user-level from project-level surfaces.

3. **`internal/audit/audit.go`'s `buildSuggestions()` (lines 185–199)**
   Tiny but worth calling out separately: a 15-line function that turns the raw audit report into 1–3 human-readable remediation hints (`"Remove or rename stale symbol references"`, `"Config files are bloated (score >=60). Split long sections, dedupe bullets, trim >200-char lines."`, `"Config looks clean."`). This is the model for FA's `fa hygiene` output — the user does not want a JSON dump, they want 3 sentences naming the top issues.
   → **FA application**: Lift this verbatim into the `fa hygiene` command output layer. The "config looks clean" case (`out` empty after non-zero `FilesScanned`) is the polish that makes such tools feel finished.

### Gortex — additional Tier-2 files (rounding out the architecture)

4. **`internal/claudemd/generator.go`** *(142 LOC)*
   Generates a `CLAUDE.md` section *from the indexed graph itself*: language breakdown, entry points (`main` functions), top-10 most-referenced symbols (with call counts), graph size, kind breakdown — then appends the "Instead of X / You MUST use Y" table and a 4-step Session-start checklist. The whole "Codebase Overview" block is **synthesized from the live graph at `gortex init` time**, not handwritten.
   → **FA application**: FA's `knowledge/llms.txt` and any future repo-overview block in `AGENTS.md` should be **generated** from the chunker output (ctags + markdown-it), not maintained by hand. The structural skeleton in `generator.go` (4 sections × ~10 lines each, ends with hardcoded ACI table) is a perfect template.

5. **`internal/hooks/bash_classify.go`** *(266 LOC)*
   Pre-classifies any bash command the agent is about to run into categories like `read-only`, `git-write`, `package-manager-install`, `dangerous`, etc. Used by `pretooluse.go` to decide whether to deny, enrich with context, or pass through. Notable: the classifier is **pattern-based** (no LLM call), so it adds zero latency to PreToolUse.
   → **FA application**: FA's ADR-6 sandbox is currently path-only (deny-by-default allow-list for file paths). Bash needs the same treatment, and this file shows the cheap way to do it — a static classifier, not an LLM-judge. Pairs naturally with FA's existing `safe-fs` / sandbox module.

6. **`internal/mcp/feedback.go`** *(~150 LOC)* + **`internal/mcp/frecency.go`** *(~150 LOC)* + **`internal/mcp/combo.go`**
   Per-symbol useful/not-useful/missing counts persisted to disk via `persistence.FeedbackStore`. The `frecency.go` decay function combines recency + frequency with `AgentMode`-dependent half-lives. `combo.go` blends frecency, feedback, and base graph rank into a single score used by `smart_context` and `winnow_symbols`. This is the **learning loop inside the MCP server** — the agent's votes durably reshape future query results.
   → **FA application**: FA's exploration DAG tracks rejected paths (which lessons worked) but does not yet feed back into retrieval ranking. The Gortex model — a tiny on-disk JSON store, per-symbol counters, frecency decay — is the minimum viable version of "learning from your own exploration history" and could be added to FA in <200 LOC. Important caveat: keep the storage filesystem-canonical (FA's principle), don't add a DB.

7. **`internal/workspace/workspace.go`** *(331 LOC)*
   Two-mode workspace resolution: marker file (`.gortex/workspace.toml`) at cwd → workspace mode (members = immediate children with `.gortex/`), or `.gortex/` directly at cwd → single-project mode. **No walk-up** — entry-point discovery is explicit by design. Workspace isolation is enforced (members must live strictly inside the resolved root, no cross-workspace bridging).
   → **FA application**: FA is single-project today, but if it ever wants to support multiple co-located projects (e.g. a monorepo where each package has its own `knowledge/`), the no-walk-up + auto-discover-children + explicit-exclude design is much simpler than `find . -name AGENTS.md` and avoids surprising scope-creep bugs. Worth pinning as an ADR even if not implemented yet.

8. **`.github/workflows/ci.yml`** *(~110 LOC)*
   Three-matrix Go build (ubuntu/macos × Go 1.26), `go test -race -coverprofile=...` + codecov upload, golangci-lint (pinned `v2.11.4`), three additional build modes (default Hugot, `-tags embeddings_onnx`, `-tags embeddings_gomlx`) to verify build tags don't bit-rot, and a `benchmark` job on PRs only. Every action pinned to a SHA, not a tag (supply-chain hygiene).
   → **FA application**: FA's CI today is light. The two patterns worth copying: (1) **SHA-pinned actions** (the file reads `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6` everywhere — readable comment + immutable pin); (2) **build-tag matrix to prevent silent rot** — FA has optional dependency paths (ctags, FTS5) that could break without anyone noticing. A 3-line build-mode matrix catches that.

9. **`.github/workflows/release.yml`** *(longer; key bits at top)*
   Tag-triggered release with full goreleaser pipeline: cosign keyless signing (OIDC), SLSA-3 provenance generation, macOS notarization via `rcodesign`, signing material staged under a 0700 tmpdir and wiped at job end. Reads like a security audit because it is one.
   → **FA application**: FA likely doesn't need notarization or SLSA-3 today, but the **shape of the workflow** — tag-triggered, cosign-signed binaries, provenance attestation — is the gold standard for any OSS tool that ships executables. Worth bookmarking even if it's a future-PR concern.

### Gortex — Tier-3 (noted but lower priority)

- **`internal/agents/{cursor,kiro,windsurf,cline,aider,codex,gemini,opencode,continuedev,antigravity,vscode,zed,kilocode,openclaw,mcp}/`** — 14 more adapter implementations, each ~200–400 LOC. Read one (claudecode is the canonical reference) and skim the rest only when you actually need to emit that agent's config format. Pattern is identical; differences are file paths and JSON-vs-TOML-vs-Markdown.
- **`internal/agents/instructions_test.go`** — the test for the marker-fenced regenerable block. Good model for FA's own marker-fence tests if/when that pattern lands.
- **`internal/mcp/scope.go` / `scope_init.go`** — the runtime "active project" scoping for multi-repo mode. Out of scope for FA today.

### Aperant — additional Tier-1 files (new patterns)

10. **`apps/desktop/src/main/ai/orchestration/recovery-manager.ts`** *(456 LOC)*
    The **failure-recovery brain** sitting alongside `build-orchestrator.ts`. Classifies any error into `broken_build` / `verification_failed` / `circular_fix` / `context_exhausted` / `rate_limited` / `auth_failure` / `unknown` via keyword matching on the lowercased error text. Tracks attempts per-subtask in `<specDir>/memory/attempt_history.json` with a 2-hour window and a 50-attempt cap. Detects circular fixes via simple error-hash (`simpleHash(error)`) → `CIRCULAR_FIX_THRESHOLD = 3`. Exposes `RecoveryAction { action: 'rollback' | 'retry' | 'skip' | 'escalate', target, reason }` for the orchestrator to consume.
    → **FA application**: This is the **missing piece for FA's Exploration DAG**. FA already tracks rejected paths but doesn't currently classify *why* they were rejected or detect when the agent is going in circles. The `classifyFailure` + `simpleHash` pattern is ~30 LOC and turns the DAG from a passive log into an active control surface. The 2-hour attempt window is the right knob to expose — short enough that yesterday's stale errors don't poison today's planner, long enough that a multi-hour session sees its own history.

11. **`apps/desktop/src/main/ai/orchestration/pause-handler.ts`** *(276 LOC)*
    Filesystem-sentinel pause/resume mechanism. The orchestrator writes `<specDir>/RATE_LIMIT_PAUSE` (with reset timestamp) or `AUTH_PAUSE` when it hits HTTP 429/401; the frontend (or a human) writes `<specDir>/RESUME` to unblock. Constants are precise and defensible: `MAX_RATE_LIMIT_WAIT_MS = 7_200_000` (2h), `RATE_LIMIT_CHECK_INTERVAL_MS = 30_000` (30s), `AUTH_RESUME_MAX_WAIT_MS = 86_400_000` (24h), `AUTH_RESUME_CHECK_INTERVAL_MS = 10_000` (10s).
    → **FA application**: FA inherits the same problem (rate-limited or auth-failed local LLM tier blocks the whole session). The pause-file pattern is exactly the FA idiom — Markdown/JSON on disk, no IPC, no daemon. Lift verbatim into `src/fa/orchestration/pause.py` (~80 LOC). The intervals (30s for rate limit, 10s for auth) are well-tuned defaults; don't change them without evidence.

12. **`apps/desktop/src/main/ai/orchestration/subtask-iterator.ts`** *(528 LOC)*
    The actual loop that reads `implementation_plan.json`, finds the next pending subtask, calls the coder session, tracks per-subtask retries, marks subtasks `stuck` after `maxRetries`, and (optionally) extracts insights after each session via `extractSessionInsights`. The orchestrator hooks (`onSubtaskStart`, `onSubtaskComplete`, `onSubtaskStuck`, `onInsightsExtracted`) are the supervisor's-eye-view of the loop — clean callback-based separation of "do work" from "observe work."
    → **FA application**: FA's session loop today is conceptual; this is a 528-LOC concrete implementation that handles every edge case (cancellation via AbortSignal, worktree-mode RESUME fallback, stuck-subtask escalation, attempt counting, insight extraction as a post-session phase). Worth reading end-to-end before writing FA's equivalent — saves at least 2 design iterations.

13. **`apps/desktop/src/main/ai/runners/insight-extractor.ts`** *(308 LOC)* + **`apps/desktop/prompts/insight_extractor.md`** *(178 LOC)*
    The "structured insights from a completed session" pipeline. Runs `generateText` (no tools) with a Zod schema (`ExtractedInsightsOutputSchema`) on inputs: git diff (capped at 15 000 chars), subtask description, attempt history (last 3 entries), commit messages, success flag. Uses `haiku` as the default model — fast and cheap, because insight extraction is high-volume. Output shape: `file_insights[]`, `patterns_discovered[]`, `gotchas_discovered[]`, `approach_outcome{success, why_it_worked, why_it_failed, alternatives_tried}`, `recommendations[]`. The prompt file is well-engineered: explicit "ACTIONABLE knowledge, not logs" framing, JSON-only output contract, "good example / bad example" demonstrations.
    → **FA application**: This is **the Mechanical Wiki feeder loop** for FA. FA's gotchas/discoveries files today are written by the LLM mid-task (via `record_gotcha` / `record_discovery` if FA implements them); this pattern adds a **post-session insight pass** that mines the diff + attempt history for structured learnings the in-flight LLM would miss. The 15 000-char diff cap is the key empirical detail — bigger diffs degrade extraction quality, smaller diffs miss context.

14. **`apps/desktop/src/main/ai/agent/worker.ts`** *(1268 LOC)* + **`apps/desktop/src/main/ai/agent/executor.ts`** *(119 LOC)* + **`apps/desktop/src/main/ai/agent/types.ts`** *(192 LOC)* + **`apps/desktop/src/main/ai/agent/worker-bridge.ts`** *(250 LOC)*
    Worker-thread isolation for every agent session. `worker.ts` is the entry point — receives `WorkerConfig` via `workerData`, builds tool registry, creates MCP clients, runs `runAgentSession()` or `runContinuableSession()`, posts structured `WorkerMessage`s back to the parent via `parentPort`. Each phase (planning/coding/QA/spec) gets its own worker thread. `executor.ts` is the parent-side spawner (`new Worker(workerScript, { workerData })`); `worker-bridge.ts` is the bidirectional message protocol; `types.ts` is the serializable config + message envelope.
    → **FA application**: FA is single-process today but will eventually want isolation between phases (so a planner can't accidentally corrupt the coder's spec dir, and a crashed phase doesn't take down the orchestrator). Python's `multiprocessing` is the analog. The shape of `WorkerConfig` (everything serializable, no live objects passed across the boundary) is the design rule — copy it. The `TaskLogWriter` singleton-per-spec pattern (line 71) is also worth lifting: one log file per spec, all phases accumulate.

15. **`apps/desktop/prompts/coder_recovery.md`** *(290 LOC)*
    Add-on to `coder.md` that injects recovery awareness. Step 0 reads `memory/attempt_history.json`; if the current subtask has 1+ prior attempts, prints `⚠️⚠️⚠️ THIS SUBTASK HAS BEEN ATTEMPTED BEFORE! ⚠️⚠️⚠️` and forces the coder to articulate a *different* approach. At 2+ prior attempts, escalates to `HIGH RISK` and suggests "completely different library or pattern / simplify / check feasibility."
    → **FA application**: FA's Exploration DAG records rejected paths; this prompt shows the **reading side** — how to surface that history to the next planner/coder turn so they don't repeat the same dead-end. Pairs naturally with #10 (recovery-manager): one writes the history, this one reads it. Lift the prompt structure verbatim — the explicit `attempt_count >= 2 → HIGH RISK` ladder is the model.

### Aperant — additional Tier-2 files (specialized but lifesaving)

16. **`apps/desktop/src/main/ai/merge/orchestrator.ts`** *(725 LOC)* + **`auto-merger.ts`** + **`semantic-analyzer.ts`** *(363 LOC)* + **`conflict-detector.ts`** + **`file-evolution.ts`** + **`runners/merge-resolver.ts`** *(118 LOC)*
    Six-file intent-aware merge subsystem. Pipeline: load baselines + task changes → `semantic-analyzer.ts` extracts language-aware deltas (imports added/removed, functions added/removed/modified, hook calls, JSX changes) via regex patterns per file extension → `conflict-detector.ts` flags conflicts → `auto-merger.ts` applies deterministic merges → ambiguous conflicts go to `runners/merge-resolver.ts` (one-shot AI call with the conflict block) → final merged content + detailed report.
    → **FA application**: FA today is single-agent; multi-agent worktree-based parallelism is a future-state. But the **semantic-analyzer regex-by-extension pattern** (lines 26–50) is reusable in its own right — anywhere FA needs a cheap, no-LLM signal "what kind of change is this diff?" (e.g. for triage, for changelog generation, for deciding whether a change is safe to auto-merge). The Python equivalent is ~80 LOC.

17. **`apps/desktop/prompts/{complexity_assessor,spec_quick,spec_critic,spec_gatherer,spec_researcher}.md`**
    The **spec-creation pipeline**, not just `spec_writer.md`. `complexity_assessor.md` is the first phase — reads `requirements.json` + `project_index.json`, outputs `complexity_assessment.json` classifying the task as SIMPLE/STANDARD/COMPLEX, which then routes to either `spec_quick.md` (SIMPLE — 20–50 line spec, single-phase implementation_plan.json) or the full `spec_gatherer.md` → `spec_researcher.md` → `spec_writer.md` → `spec_critic.md` pipeline (COMPLEX). Every prompt has the same explicit contract: "**MANDATORY**: You MUST call the Write tool. Describing the assessment in your text response does NOT count — the orchestrator validates that the file exists on disk."
    → **FA application**: This is the **canonical example of filesystem-canonical validation**, which is core FA philosophy. The "MUST call Write tool, orchestrator validates by disk read" rule is the right idiom for FA's every tool that produces structured output. Worth lifting both: (a) the **5-stage spec pipeline structure** (complexity → quick-or-full → researcher → writer → critic) as a model for FA's Phase S; (b) the **"Write or it didn't happen" rule** as a universal pattern for any FA tool that produces files.

18. **`apps/desktop/prompts/qa_orchestrator_agentic.md`** *(detail not fully read but structure visible)*
    The **agentic** QA loop. Unlike the procedural `qa-loop.ts` that brute-forces up to 50 iterations, this one *reasons* about each review cycle and decides what to fix / accept / escalate. Uses `SpawnSubagent` to delegate to `qa_reviewer` (with browser/test tools) and `qa_fixer` (with full write access). Pre-flight: read `implementation_plan.json`, verify all subtasks completed; read `spec.md`; check for `QA_FIX_REQUEST.md` (human feedback takes priority — explicit override path).
    → **FA application**: FA has two QA design choices: procedural (a fixed pipeline of checks) or agentic (an LLM that decides what to check). This prompt is the agentic version — pairs well with FA's role-routing if there's eventually a "QA tier" with its own LLM. The **human override file (`QA_FIX_REQUEST.md`)** is the most important detail: a filesystem-sentinel that lets the human inject priority feedback without modifying any tool surface. Same idiom as Aperant's pause-handler.

19. **`apps/desktop/prompts/ideation_{code_quality,code_improvements,documentation,performance,security,ui_ux}.md`**
    Six **ideation specialists** that each scan a project and produce category-specific improvement suggestions. Reading just `ideation_code_quality.md`: it's structured as senior-architect role with explicit categories (large files >500 LOC, code smells like long methods / deep nesting / >4 params, cyclomatic complexity, duplication). Crucially, it reads a Graphiti-derived `graph_hints.json` and uses it to (a) avoid suggesting already-completed refactorings, (b) prioritize patterns that worked before, (c) avoid past regressions.
    → **FA application**: FA's research phase (Phase R) could use this pattern — instead of one monolithic "research" prompt, six specialist prompts that each scan for one type of improvement. The **graph-hints integration** is the deeper insight: ideation is more useful when it knows what's already been tried. Maps onto FA's Exploration DAG read-side (#15) and the feedback loop (#6).

20. **`apps/desktop/prompts/github/pr_finding_validator.md`** *(detail visible)*
    Evidence-based validator. For each finding from a prior PR review, it must: verify the file is actually in the PR's changed files; verify the line number exists; read the actual code at file/line; either prove the issue exists with concrete code evidence or dismiss as `dismissed_false_positive`. Core principle stated explicitly: **"Evidence, not confidence scores. Either you can prove the issue exists with actual code, or you can't. There is no middle ground."**
    → **FA application**: This file is the antidote to the most common LLM failure mode in PR review (and in FA's own pre-flight) — **the model invents findings that look plausible but reference lines that don't exist or files that aren't in scope**. The validator pattern (read the actual code, verify scope, dismiss hallucinations) is what makes FA's symmetric-reading rule operational. The "Evidence, not confidence scores" framing is worth quoting verbatim in FA's AGENTS.md.

21. **`apps/desktop/prompts/github/pr_template_filler.md`**
    Single-purpose agent: given the repo's `.github/PULL_REQUEST_TEMPLATE.md`, a diff summary, spec overview, commit history, branch names → produces a complete filled PR body. Rule: **"Never leave a section empty — if not applicable, explicitly state 'N/A'."**
    → **FA application**: Direct lift for FA's `fa pr` (or equivalent) command. The "never leave empty, always 'N/A'" rule is the small detail that makes PR descriptions feel professional. ~60 LOC of Python wrapping a single `generateText` call.

22. **`apps/desktop/prompts/github/duplicate_detector.md`**
    Tiered similarity weights for duplicate-issue detection. Strong indicators (high weight): identical error messages, same stack trace patterns, same repro steps, same affected component. Moderate (medium): similar problem description, same area, same symptoms, related title keywords. Weak (low): same labels, same author (explicitly marked "not reliable"), similar timestamps.
    → **FA application**: If FA ever surfaces "have I done this task before?" before a session starts, this is the model. The **explicit weight tiers** and the **"not reliable" warning on same-author** are the bits that distinguish a working detector from a noisy one.

23. **`apps/desktop/prompts/mcp_tools/{api_validation,database_validation,electron_validation,puppeteer_browser}.md`**
    Four **runtime-validation** prompts that each cover one infrastructure layer. `api_validation.md` covers endpoint existence (FastAPI `openapi.json`, Express grep, Django `show_urls`), auth, response format, status codes. `database_validation.md` covers migrations (Django, Rails, Prisma, Alembic, Drizzle), schema integrity, rollback. Same structure across all four: numbered "Step N: Verify X" sections with literal `curl` / framework-specific commands.
    → **FA application**: These are the **operational** counterpart to FA's pre-flight (which is largely advisory). When FA grows runtime-validation tooling, this template (numbered steps, framework-specific copy-paste commands, explicit success/failure criteria) is the right shape. The framework branching pattern (FastAPI vs Express vs Django) is the cheap way to handle "FA on different projects" without an LLM call.

24. **`.husky/pre-commit`** *(extensive, ~200 LOC of shell)*
    The **version-sync + safety + lint** hook. Three notable patterns: (a) unsets `GIT_DIR` / `GIT_WORK_TREE` env at entry to prevent IDE-leaked vars from corrupting hook target (paragraph-long comment explaining why); (b) detects and auto-fixes corrupted `core.worktree` config that leaks across worktrees (paragraph-long comment again); (c) **version sync**: when `package.json` changes, propagates the new version to `apps/desktop/package.json`, README badges (separate stable vs beta sections detected by `-` in version), download URLs. Beta detection is regex-based (`echo "$VERSION" | grep -q '-'`).
    → **FA application**: Most of this is Aperant-specific (Electron monorepo + dual-channel release), but the **section-aware README updates** (BETA_VERSION_BADGE / BETA_DOWNLOADS markers) are the same marker-fenced regenerable-block pattern as Gortex's `<!-- gortex:rules:start -->`. FA already has Mechanical-Wiki markers; this is the proof that the same idiom works for arbitrary version-stamped content (badges, download links, install instructions) and not just LLM instructions.

25. **`.github/release-drafter.yml`**
    Auto-generates release notes from merged PRs, categorized by label (`feature`/`enhancement` → New Features, `bug`/`fix` → Bug Fixes, `improvement`/`refactor` → Improvements, `documentation` → Documentation, everything else → Other). Tag template `v$RESOLVED_VERSION`. Includes auto-generated contributor section.
    → **FA application**: FA has no release-notes automation yet. Drop-in 40-line config. The labels match GitHub defaults; no extra setup required.

### Aperant — Tier-3 (noted but skim-only)

- **`apps/desktop/prompts/github/{pr_security_agent,pr_quality_agent,pr_logic_agent,pr_codebase_fit_agent,pr_followup_{comment,newcode,resolution}_agent,pr_parallel_orchestrator,pr_structural,pr_ai_triage,pr_reviewer,pr_fixer,QA_REVIEW_SYSTEM_PROMPT,spam_detector}.md`** — 13 more specialist PR/issue prompts. Pattern is identical to the four already covered (pr_orchestrator, pr_followup_orchestrator, issue_analyzer, issue_triager); each is a "ROLE / CONTRACT / METHODOLOGY / OUTPUT FORMAT" 4-section markdown file averaging 200–400 LOC. Lift on a per-need basis — don't import the whole library at once.
- **`apps/desktop/src/main/ai/runners/{changelog,commit-message,ideation,roadmap}.ts`** — Vercel-AI-SDK wrappers that each do one job (changelog from commits, conventional commit message from diff, roadmap from project state). All follow `createSimpleClient()` → `generateText()` → JSON-or-text-output. The `commit-message.ts` `CATEGORY_TO_COMMIT_TYPE` map (feature → feat, bug_fix → fix, refactoring → refactor, …) is reusable as-is.
- **`apps/desktop/src/main/ai/orchestration/__tests__/`** — the test suite. Worth one read-through if FA's orchestration code matures, otherwise out of scope.
- **`scripts/{ai-pr-reviewer.md,bump-version.js,cleanup-version-branches.sh,update-readme.mjs,validate-release.js}`** — release/maintenance scripts. Aperant-specific but the **`update-readme.mjs` marker-block updater** is another concrete instance of the regenerable-block pattern.

### Coverage summary after addendum

Files examined now total ~110 across both repos (was ~70 in first pass). New patterns surfaced this round, not in original brief:

- **Runtime hook architecture** (Gortex `internal/hooks/`) — enrich-or-deny on every tool call.
- **Generated-from-graph CLAUDE.md** (Gortex `claudemd/generator.go`) — repo overview is synthesized at init time.
- **Bash classifier** (Gortex `hooks/bash_classify.go`) — static patterns, no LLM, for sandbox decisions.
- **Per-symbol feedback loop** (Gortex `mcp/feedback.go` + `frecency.go` + `combo.go`) — agent votes durably reshape retrieval.
- **Workspace marker + auto-discover** (Gortex `workspace/workspace.go`) — explicit entry-point, no walk-up.
- **Failure classifier + circular-fix detector** (Aperant `orchestration/recovery-manager.ts`) — keyword-based classification + simple-hash circularity.
- **Filesystem-sentinel pause/resume** (Aperant `orchestration/pause-handler.ts`) — rate-limit and auth-failure as marker files.
- **Post-session insight extraction** (Aperant `runners/insight-extractor.ts` + `prompts/insight_extractor.md`) — mine the diff after every session.
- **Worker-thread session isolation** (Aperant `agent/worker.ts`) — phase-level process isolation.
- **Recovery-aware coder prompt** (Aperant `coder_recovery.md`) — read attempt_history.json before retrying.
- **Intent-aware semantic merge** (Aperant `merge/`) — regex-based per-extension semantic diff classification.
- **Multi-stage spec pipeline with disk-validated handoffs** (Aperant `complexity_assessor` → `spec_quick`-or-full pipeline) — "Write or it didn't happen."
- **Specialist ideation prompts with graph-hints feedback** (Aperant `ideation_*.md`) — category-specific scanners that consume Graphiti history.
- **Evidence-based finding validation** (Aperant `pr_finding_validator.md`) — antidote to LLM-invented findings.
- **Marker-fenced README sections** (Aperant `.husky/pre-commit`) — proves regenerable-block pattern generalizes beyond agent instructions.

If anything else still feels missing, the most likely candidates are: Aperant's `src/main/ai/memory/{graph,db,injection,retrieval,embedding,observer}/` subdirectories (the actual V5 memory implementation behind `Memory.md`), and Gortex's `internal/{indexer,resolver,semantic,query}/` (the graph build pipeline). I've flagged these as out-of-scope for FA's near-term roadmap — both are deep, both presume infrastructure FA doesn't have (SQLite-vectors / language servers), and both restate patterns already covered in the brief at a higher level of abstraction. If you want either of them pulled in, say so and I'll do a focused pass.

---

*Generated 2026-05-13. First pass plus verification addendum. Based on shallow clones (`--depth=50`) of both repos pulled fresh. No code modified in either repo or in FA.*
