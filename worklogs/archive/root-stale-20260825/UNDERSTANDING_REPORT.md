# First-Agent — Deep Understanding Report (Ready Proof)

> Prepared 2026-08-24, repo HEAD `234ca80 big patch` (operator big patch). This report answers the 4 screening questions with primary-source evidence, to unblock the next implementation-plan slice.

## Verification Steps Taken (MAX effort)

```bash
git clone https://github.com/first-agent-dev/First-Agent-dev.git
find . -type f -name "*.md" | wc -l  # 100+ markdown files
ls knowledge/adr/  # 16 ADRs + DIGEST + template
ls src/fa/  # 20+ modules: cli.py, blackboard, inner_loop, providers, sandbox, session, etc.
ls worklogs/implementation-plans/  # 30+ plans, parent plan v12 S14 closure
git log -n 5 --oneline  # 234ca80 big patch, f2ed2c9 file work, 22ab73a S13.11 closure
cat knowledge/llms.txt §MUST READ FIRST (5 files)
cat AGENTS.md §Pre-flight checklist (5 steps)
```

Files read in full for this report (primary sources, not summaries):
- `README.md` — elevator pitch + architecture mermaid
- `AGENTS.md` — session bootstrap, pre-flight, context-budget, skills, query routing
- `knowledge/project-overview.md` — §1 problem, §1.1 four pillars, §1.2 minimalism-first, §1.2.5 compliance-by-construction, §1.2.6 substrate formality, §1.2.7 pair over autonomy, §4 scope
- `knowledge/reference.md` — §Terms (90+ terms), §Features, §Session Data Layout (authority hierarchy)
- `knowledge/architecture.md` (now merged into reference but still present) — three-layer model + current implementation state 2026-05-29
- `knowledge/overview/FEATURES.md` — egress proxy, TCB, bash intent, token-efficient retrieval
- `knowledge/adr/DIGEST.md` — 758 lines, one paragraph per ADR + amendments
- `knowledge/adr/ADR-1-v01-use-case-scope.md` — UC1+UC3 in v0.1, UC4/UC5 deferred, amendments 2026-05-01/06
- `knowledge/adr/ADR-2-llm-tiering.md` — static role routing, tool_protocol, MCP shape, family-disjoint Eval
- `knowledge/adr/ADR-3-memory-architecture-variant.md` — Variant A Mechanical Wiki
- `knowledge/adr/ADR-4-storage-backend.md` — SQLite FTS5
- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` + ADR-8 HookRegistry + ADR-9 provider client + ADR-10 invariants + ADR-11 TCB + ADR-12 secret isolation + ADR-13 workspace isolation
- `knowledge/BACKLOG.md` — I-1..I-56, M-1..M-12, open security items I-34, I-36..I-54
- `worklogs/HANDOFF.md` — S14 READY, S13 CLOSED live-verified 2026-08-09, S13.11 closure, current patch
- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` v12 parent
- `worklogs/implementation-plans/PLAN-cli-trace-S13.11-portable-tool-schema-contract.md` v5 READY (current ongoing slice per git log `22ab73a`)
- `knowledge/skills/` — 8 skills, README scope distinction skill vs prompt vs rule
- `pyproject.toml` — Python 3.13, dependencies, ruff/mypy/pyrefly/pylint/mutmut gates
- `knowledge/instructions/README.md` + 02-operations.md — deploy/operate AIO

Symmetric reading executed:
```bash
grep -ril "blackboard" knowledge/research/  # 5+ notes
grep -ril "token.*efficient" knowledge/
grep -i "^\| \*\*Pillar\*\*" knowledge/reference.md  # fallback to project-overview
```

---

## 1. Why does this project exist?

### Primary source: `knowledge/project-overview.md` §1 Problem statement + §1.1 Four Pillars

> Quote (project-overview.md:11-24):
> "First-Agent (FA) is a locally orchestrated, mixed-tier LLM coding agent for a single power-user with deterministically bound harness. It exists because:
> - Hosted coding agents (Claude Code, Cursor, Copilot Workspace) are great but expensive at scale and constrained to their own context-/memory-models. We need a setup where planner/coder/debug roles can use different LLM tiers under our config control.
> - Local GraphRAG stacks (MS GraphRAG, LightRAG, HippoRAG) optimise reading but produce write-side bookkeeping the user has to maintain. LLM-Wiki stacks (Karpathy, AI-Context-OS) optimise writing but read-side is often grep+BM25 only.
> - We want the hybrid: filesystem-canon + lazy search-side scaling BM25 → vectors → graph."

**In other words:**
- **Cost & control gap:** Hosted agents force one model/tier; FA wants `planner=top-tier OSS (GLM 5.1 / Kimi 2.6 / Mimo 2.5)`, `coder=mid-tier OSS (Nemotron 3 Super / Qwen 3.6)`, `debug=elite Claude` — static role routing per ADR-2, configurable in `~/.fa/models.yaml`.
- **Memory gap:** Existing local stacks are either read-optimised (GraphRAG) or write-optimised (LLM-Wiki). FA picks **Mechanical Wiki** — filesystem-canon Markdown + YAML frontmatter + deterministic chunker + SQLite FTS5 BM25 — per ADR-3 + ADR-4. No embeddings in v0.1, but scaffolded for v0.2.
- **Efficiency gap:** Pillar 3 goal is explicit — build **most token- and tool-call-efficient harness** among known open-source agent stacks for UC1+UC3. Measured by 4 KPIs (median tokens/task, tool-calls/task, tools-in-context, USD/task) after UC5 baseline lands (project-overview.md §1.1 Pillar 3, §3 Success metrics).

**Architecture at a Glance (README.md mermaid):**
- `User --fa run--> HostWrapper scripts/fa --docker exec--> AgentContainer`
- Inside Docker Compose: `fa-egress-proxy` holds real API keys; `first-agent` container has no keys, only `X-FA-Proxy-Token` + `base_url http://fa-egress-proxy:8080`. Proxy injects real header. Isolation via mount/PID namespaces (ADR-12).
- Session state authority: `~/.fa/session-log/<run_id>/session.db` SQLite with 3 tables `event_log, blackboard, session_meta` (reference.md §Session Data Layout). JSONL `events.jsonl` is best-effort mirror; session.db wins.

**Deeper rationale from `knowledge/overview/FEATURES.md`:**
- Session Database Authority, Blackboard Conflict Detection (read_set overlaps write_set → `conflict_detected`), Egress-Injection Proxy, TCB two-tier frozen stdlib kernel, Bash Intent Analysis via `bashlex` AST (READ_ONLY/INDEX_WRITE/REPO_WRITE/DANGEROUS), Token-Efficient Retrieval (Mechanical Wiki).

So existence = **research-backed, locally-deployable, secure, measurable alternative** to hosted coding agents, not a LangChain wrapper.

---

## 2. How has it been created?

### Lifecycle: Phase R → S → M (research → scaffolding → module) — per `knowledge/reference.md` §Terms Phase R/S/M + `knowledge/architecture.md`

**Creation story reconstructed from ADRs + BACKLOG + HANDOFF:**

1. **R-phase (research):** `knowledge/research/` holds 20+ notes with frontmatter `source:, compiled:, chain_of_custody:`. Each ADR has Prior Art section. Example: ADR-1 cites PR #17 user verbatim ranking "1 coding+PR / 3 local-docs-to-wiki main". ADR-2 cites Cornell P-1 (Kim et al. ICML 2025) + Simula P-2 for family-disjoint rule. Exploration log `knowledge/trace/exploration_log.md` records `Chosen:` + `Rejected:` with Reason + Lesson per Q-N (per knowledge/README.md §trace/).

2. **Scope freeze (ADR-1, 2026-04-27, amended 2026-05-01/06):**
   - UC1 Persistent coding & PR management (folder → search → edit → PR) — in scope v0.1
   - UC3 Local docs to wiki (large file → inbox → indexed → selective retrieval) — in scope
   - UC2 multi-source research — best-effort LLM fan-out, no graph
   - UC4 Telegram multi-user + UC5 semi-autonomous multi-LLM research/eval harness — deferred to v0.2, with eval-harness design (5a benchmark suite → 5b trace consumption → 5c iteration interface → 5d leaderboard)

3. **Architectural decisions (ADRs, chronological):**
   - **ADR-2 (2026-04-27):** Static role routing, `tool_protocol: native|prompt-only`, MCP forward-compat shape `request {name, params} / response {result, error}`, family-disjoint Eval MUST be different family than Planner/Coder (later relaxed 2026-08-04 to adversarial stance + warning, not blocking).
   - **ADR-3 (2026-04-27):** Variant A Mechanical Wiki — filesystem-canon MD + YAML, deterministic chunker, SQLite FTS5 BM25, no embeddings/graph/Mem0 in v0.1.
   - **ADR-4 (2026-04-27):** Storage backend SQLite FTS5 at `~/.fa/state/index.sqlite`, tokeniser `unicode61 remove_diacritics 2` + porter.
   - **ADR-5 (2026-04-28):** Chunker universal-ctags + markdown-it-py, interface `Chunker.chunk_file(path) -> list[Chunk]`, tree-sitter explicit non-goal.
   - **ADR-6 (2026-04-29, amended 2026-05-13/20):** Tool sandbox & path allow-list at `~/.fa/sandbox.toml` [read]/[write] deny overrides allow, `pathlib.resolve`, `pathspec` globs; per-role `allowed_tools` whitelist; 5 capability flags `ENABLE_DYNAMIC_TOOLS` etc default False (Kronos R-21); bash sandbox 3-layer pipeline classifier + validators + path containment (ported from Aperant/Gortex).
   - **ADR-7 (2026-05-12, amended 2026-05-13/20/21, 2026-08-16 PTS-v1):** Inner-loop & tool-registry contract — `ToolSpec`/`ToolResult`, 5-tool v0.1 catalog, edit-shapes, JSON-Schema validation, three-tier disclosure, trace separation `events.jsonl` raw + `hot.md` summary, mini hook pipeline pre_tool×2 + post_tool×1, static layered prompt frozen, retry-budget invariant `max_iterations=6` default, cost guardian, learning observer. Amendment 2026-08-16 Portable Tool Schema v1: closed type/keyword profile, `ToolSchemaPortabilityError`.
   - **ADR-8 (2026-05-20):** HookRegistry middleware chain — 5 lifecycle points `BETWEEN_ROUNDS/BEFORE_LLM_CALL/AFTER_LLM_CALL/BEFORE_TOOL_EXEC/AFTER_TOOL_EXEC`, GuardMiddleware may deny/modify, ObserverMiddleware read-only, first-deny short-circuit, family-disjoint at register time, `revalidates_after_modify`.
   - **ADR-9 (2026-05-22, T-2 driver landed M-4, T-4 loader M-5, amended 2026-08-16 selected-provider CONF-8):** LLM provider client Option D+α — per-role explicit chain `[{provider, slug, base_url, api_key_env, cooldown_seconds, ...}]`, cooldown 5min default adaptive `max(now+cooldown, Retry-After)`, 401/403 continue chain, 400/422 fail-fast `ProviderRequestShapeError`, 3-tier observability keyed on `logical_call_id`, 2-category adapter split OpenAICompat vs Anthropic, 6 typed errors, pricing via `cost_table.py`. Selected-provider exact-request qualification: `--provider` filters coder entries before keys/proxy, CONF-8 with deployed sampling + exact production tool corpus.
   - **ADR-10 (2026-05-25):** Deterministic-harness invariants I-1..I-5 — single-source-of-truth classifier, numbered MANDATORY workflows are A-bucket residue, stable `[CODE]` prefix, typed loop-state ownership, layer-boundary fail-fast.
   - **ADR-11 (2026-06-01, I9 2026-07-15):** Authoring Guardrails two-tier TCB — Level-0 frozen stdlib-only kernel (tomllib manifest, sorted enumeration, SHA-256, allowlist dispatch, fail-closed), Level-1 rule packs, severity lifecycle HARD-BLOCK/ADVISORY-with-expiry/INFO, I-FROZEN marker, AST over regex, test-decay lock, CI-enforced not pre-commit-only, protected-path governance, I-BOOT `.fa/session.toml` seam, live-path DoD I9: harness product behavior not done until composition-root test would fail if production call site removed.
   - **ADR-12 (2026-06-16):** API-key isolation — egress-injection proxy boundary, secret-path deny `/run/secrets`, model-egress redaction at one chokepoint `coder_loop._redact`, private SecretStore, SecretGuard.
   - **ADR-13 (2026-06-25, amended 2026-08-13):** Workspace Isolation — read-only `/repo` source, persistent writable clones under `/sessions/<session-id>`, local Git pack transport, lifecycle readiness prepares `.venv` + 4 hook seats + pre-commit envs before model use, bounded caches ephemeral.
   - **ADR-14 (2026-07-11):** Stateful Bash via EventStream Runtime — PTY via libtmux PtyPool Map<id,Session> max 2-3 LRU fail-fast, fallback pexpect, sentinel `|||FA_READY|||`, tool batching parallel read-only via ThreadPool max5 with Lock sequential log, prompt caching split cacheable=[BASE, AGENTS.md map, tool defs per role] + non-cacheable task+memory, cache-key = role_id + hash(names+schemas) + hash(agents_map) + hash(skills).
   - **ADR-15 (2026-07-11):** Multitask Subagents Worktree Isolation — WorktreeManager SharedDir v0.1 → IsolatedWorktreeManager future `git worktree add`, profiles dynamic toolset researcher 600 tokens vs full 3000, instant grep FTS5 trigram `tokenize='trigram'`, SubagentEnvelope Goal/Verification/Risks/token_usage/duration/next_action, task worklog.md aggregation.

4. **Milestone implementation (BACKLOG.md M-N + HANDOFF.md):**
   - M-1 inner-loop scaffolding/HookRegistry runtime closed PR #24 (2026-05-20) — 338 tests
   - M-2 LoopGuard + FailureClassifier + attempt_history closed PR-2 stacking
   - M-3 BlockerMiddleware + DSV YAML + QA constants closed PR-3
   - M-4 T-2 provider client driver closed 2026-05-22 — 7 modules `src/fa/providers/` + cost_table, 55 tests
   - M-5 T-4 models.yaml loader closed 2026-05-22 — `src/fa/providers/config.py` + 23 tests, new dep `pyyaml>=6.0`
   - M-6 PR B `pr_intent` classifier + git hooks closed PR B 2026-05-27
   - M-7 PR C `IntentGuard` GuardMiddleware closed PR C 2026-05-27, expanded to bash_intent AST + PrDraftStore
   - M-8 PR D LLM-driven coder loop `drive_session` + `fa run` CLI + UrllibTransport closed PR #23 2026-05-28
   - Then parent plan `cli-trace-substrate-rebaseline-2026-07-25.md` v12: S1 session lifecycle → S2 SessionManager/authority → S3 liveness audit → S4 direct-container baseline → S5 authority correctness (V1 event identity DB-serialized UNIQUE(session_id,event_id) + BEGIN IMMEDIATE, V2 kind_counts, V6 blackboard, V15/V17 mutation symmetry, S3-F13 observability tools read authority) → S6 observability contracts → S6.6 mutation gap closure → S7 container verification (C0-C7) → S8 workflow controller surface → S9 stats projections → S10a CLI coverage 59%→83.5% → S10b C901 decomposition 39→<15 + budget 19→15 → S10c deploy-gate contracts artifact posture request cost → S11 controlled deployment → S12 platform capability markers (tests/_capabilities.py) → S13 multi-provider conformance (CONF-1..7 offline, live runner, cache hit ≥74%, workflow 3/3, eval_independence) → S13.11 portable tool schema contract (PTS-v1, fs_search simplification, exact corpus helper, selected-provider CONF-8, cache hash fix, C901 ratchet 15→14/13→12) → S14 blackboard artifact index (I-56 closed) — lazy indexer `src/fa/blackboard/artifact_index.py` 250 LOC walks `knowledge/{skills,adr,research,instructions,prompts,codemaps,anti-patterns}/**/*.md` + 6 root docs, hashes sha256[:16], writes typed Blackboard entries via `blackboard.write()` append-only with parent_id, triggered lazily from `fs_blackboard_query`, 31 tests green, patch at `/home/user/s14-blackboard-artifact-index.patch` (note: your current HEAD `234ca80 big patch` already includes S13.11 closure per log `22ab73a`)

5. **Engineering rigor:** `pyproject.toml` gates — ruff line-length 120, mccabe max 15, mypy strict, pyrefly strict blocking (Q50 resolved 2026-08-01), pylint duplicate-code + cyclic-import binary gate, deptry, pip-audit blocking in CI, gitleaks, markdownlint, doc-links, uv-lock, vulture advisory, mutmut scope sandbox + session + state.py + subagent_envelope + subagent_runner + workflow_artifacts + stats.py + workspace_bootstrap.py (~42x whole-src would be 916h, so scoped), pytest-gremlins Windows mirror, coverage fail_under 80 (temporarily 89→80 while cli.py runtime paths low, BACKLOG I-28 tracks restore 90), 1300+ tests per README badge.

**Creation evidence:** Every step has a PR note under `worklogs/pr-notes/`, a verification report under `worklogs/implementation-plans/cli-trace-S*-verification-report.md`, and a mutation kill-check matrix.

---

## 3. What are goals and guidelines?

### Goals — Four Pillars (project-overview.md §1.1) — verbatim + paraphrase with evidence

**Pillar 1 — Research-backed implementation-first reference:**
- Goal: become open-source reference implementation for locally orchestrated coding agents.
- Mechanism: every architectural decision fixed via ADR (`knowledge/adr/`) + research note (`knowledge/research/`) with provenance frontmatter `source:, compiled:, chain_of_custody:, claims_requiring_verification:, superseded_by:` per `knowledge/README.md` §Provenance-frontmatter. Exploration log `knowledge/trace/exploration_log.md` is pointer overlay, not source of truth.
- Evidence: `knowledge/adr/DIGEST.md` lists 16 ADRs, each with amendments; `knowledge/research/` 30+ notes.

**Pillar 2 — Pragmatic single-user product:**
- v0.1 ships as locally orchestrated mixed-tier coding agent for single power-user under UC1 coding+PR + UC3 local-docs-to-wiki. Hybrid-shape filesystem-canon MD + lazy search-side scaling BM25→vectors→graph.
- In scope v0.1: chunk-aware reading (MD, Python, Go, PS1, TS/JS, YAML/TOML/JSON), edit via shell tools, push feature branch, open PR via `gh` CLI; `fa ingest <path-or-url>`; three-layer retrieval filename/tag grep → FTS5 BM25 → vector reserved; Q&A over top-k chunks; session model `hot.md` per session auto-archived to `notes/sessions/<date>.md`.
- Out of scope v0.1: UC2 multi-source research best-effort only, UC4 Telegram multi-user deferred, embeddings/vector store scaffolded interface only, graph layer, Mem0 volatile store, YouTube/Whisper, binary extractors PDF/DOCX.
- Evidence: ADR-1 §Decision + project-overview.md §4 Scope.

**Pillar 3 — Most token/tool-call efficient harness (open-source scope):**
- Main axes: build most efficient harness among known OSS stacks for UC1+UC3 single-user single-workstation.
- Measurable: median tokens/completed task, median tool-calls/task, tools-in-context at session start, API cost USD/task. Numbers TBD until UC5 baseline run lands.
- Mechanism: mechanical wiki (no vector DB), tool specs with `max_context_bytes` head/tail elision, static role-routing avoids wasteful escalation, prompt caching split cacheable vs non-cacheable with stable cache-key per role.
- Evidence: project-overview.md §1.1 Pillar 3, §3 Success metrics, ADR-10 KPI candidates.

**Pillar 4 — Iteration via measurement:**
- Efficiency not declared but measured and improved iteratively.
- Base v0.1: agent can write own skills (`SKILL.md` under `~/.fa/skills/` or `knowledge/skills/`) from completed tasks — pattern from Anthropic Claude Skills adapted to Mechanical Wiki (frontmatter + FTS5 per ADR-3/ADR-4). Requires ADR-8.
- UC5 v0.2: benchmark-suite → eval report → manual or skill-write-based modification → re-benchmark → leaderboard. Details ADR-1 Amendment 2026-05-06: 5a local benchmark fixtures `eval/fixtures/<task_id>.md` with `scoring_kind`, 5b trace consumption `events.jsonl` → `eval/reports/<run_id>.md` with tokens/tool-calls/tools-in-context/cost/success-rate, 5c iteration via config files, 5d score tracking `eval/leaderboard.md` append-only, 5e out-of-scope (no auto proposer, no prompt-mutation-via-code, one target-model per iteration).
- Evidence: `eval/fixtures/` + `eval/reports/` + `eval/leaderboard.md`, project-overview.md §1.1 Pillar 4.

### Enforceable Principles (project-overview.md §1.2, §1.2.5, §1.2.6, §1.2.7)

**§1.2 Minimalism-first (principle, not goal):** Every new harness component must pass 4-question test before addition:
1. What research-evidence supports necessity under UC1+UC3?
2. Does OSS stack already delete/not add similar component and what result?
3. If not added, what capability lost and can existing tool/config replace?
4. Compliance-by-construction, failure-observable — can deterministic Python function do it without LLM call? If LLM call not needed for quality (parsing, formatting, aggregation, fan-out, lookup), function is default; LLM call justified only when judgement cannot be expressed deterministically.
If (1) no evidence or (2) deleted without loss or (3) replaceable or (4) function suffices → rejected in current form (LLM-step) in v0.1; for (4) may return with design where step is code not model call. Post-UC5 re-check: must reduce at least one Pillar 3 KPI on reproducible benchmark else rejected.
References: `research/efficient-llm-agent-harness-deep-dive-2026-05.md` §3.5 + §0 R-7 (Anthropic code execution subtraction, Tsinghua module-ablation arXiv:2603.25723).

**§1.2.5 Compliance-by-construction, failure-observable:** When component exists, compliance enforced by construction not LLM judgement, and failure observable to agent/operator via structured WARNING not silent skip. Invariants I-1..I-5 in ADR-10. Operational companion is loadable skill `pr-creation` anti-shallow-fix gate: FIX PRs carry `DEGREE-OF-FREEDOM CLOSED:` + `DETERMINISTIC MECHANISM:` clauses citing `repo/file.ext:line` resolving against staged tree (or `n/a (reason)`), tautological mechanisms → CLASS WORKAROUND catalogued under `AP-003-shallow-fix-no-mechanism.md`. Five KPI candidates: exit-code contracts (rtk R1), schema validators with line-cited failure (gbrain G1 + hermes H1), harness-derived weights from LLM-emitted labels (icm IC2), observable failures via WARNING surfaces (kronos K2 + fork2 PR #13 F1 partial-disjoint WARNING), named-invariant tests citing ADR clauses (Layer-2 retrofit).

**§1.2.6 Substrate Formality Principle:** Topology complexity is symptom of missing formal substrate. Before adding parallel agents/dynamic DAGs/fleet, check if shared state formally queryable/versioned/content-hashed with read_set/write_set/assumptions/version_dependencies per action, blackboard append-only content-addressed with toolchain digests/schema versions, instant grep/semantic search/verification sensors answer without subagent, conflict detected via transactional semantics not file isolation. Invariants I-6.1..I-6.4. Reference Paper 2 §4.4.

**§1.2.7 Pair over Autonomy Principle:** Agent as pair programming partner not autonomous system. Optimize for checkpoint/undo/diff review/human-in-loop approval gates/observable failures, not autonomous hours. Subagents only as cheap deterministic puzzle piece providers when main context near 180k limit. Invariants I-7.1..I-7.5: main 180k context, subagent clean slate ~1k never inherits full parent history, task solvable <600 tokens tool defs + <8000 chars output structured JSON, stateless scrubbed env isolated via WorktreeManager SharedDir v0.1, no self-evolving harness without eval-harness proving simple chain insufficient + human approval.

### Guidelines — Repo Conventions (AGENTS.md)

**Pre-flight checklist (5 steps, mandatory before any non-trivial edit):**
1. Recency surface: `git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md` — expect ≤5 lines; if touches 2026-MM-DD research note, open §0 Decision Briefing.
2. Term expansion: for every project-specific noun (axis, lens, pillar, harness, hook, ACI, UC1..UC5, NLAH, MCP, subtraction-first, minimalism-first, R-S-M, …) run `grep -i "^\| \*\*<term>\*\*" knowledge/reference.md` — expect exactly one row; if missing fallback to project-overview.md §1.1–1.2 and add to reference.md §Terms in same PR.
3. Symmetric reading: before citing research note, `grep -ril "<key-term>" knowledge/research/` and open every file; cite most recent `compiled:` unless superseded.
4. Subtraction-check: before adding artefact (file, section, rule, frontmatter field, dependency), answer verbatim:
   - Removing what makes this redundant? <existing artefact covering ≥80% or "none">
   - What capability lost if omitted? <one sentence concrete>
   - Open-source precedent for not having it? <URL or repo path or "none found in 5-min search">
   If third answer "none found" → keep existing code as-is — burden of proof on adding per project-overview.md §1.2.
5. Goal-lens declaration: state openly every session:
   - goal_lens: <one-sentence from `knowledge/prompts/research-briefing.md` Stage1 or free-text>
   - project-axes advanced: <≥1 of A noise-reduction | B context-finding | C goal_lens-advancement>
   - subtraction evaluated: <YES — answers in Step4 | EXEMPT (doc-only PR no new artefact) — restate why>
   - session-type: <new-feature|bug-fix|refactor|doc-edit|reference-edit|dep-bump|research-briefing|other-explain>

**Context-budget discipline (AGENTS.md):** Collect necessary not breadth-first; navigate repo, identify relevant files, read only parts that move task forward; use `knowledge/llms.txt` routing surface + `HANDOFF.md` bootstrap; `session.db` reduces context need; use §-anchors and grep-windows; design invariant: any single LLM call total input — system prompt + role prompt + tool definitions + retrieved chunks + scrollback + in-line memory — must leave headroom.

**Industry-proven rules (from OSS agent stacks):**
1. Keep system human-curated — self-improving subsystems anti-pattern unless host mature enough to validate output.
2. Estimate tasks by scale (files touched) — scope-only metrics.
3. Every write target must have active consumer — every new file/table/metric/event-channel lands with named automated/human consumer in same PR.
4. Every new ADR requires §Prior Art section.
5. Build runtime model before fixing infra errors — state implicit behaviors, read tool docs, focus fixing abstraction; use anti-patterns catalog.

**Loadable skills (AGENTS.md table):**
- `pr-creation` — before any PR, 5-intent classifier RESEARCH/ADR-RULE/IMPLEMENT/FIX/CHORE, PR description + first commit body MUST open with header lines per skill §Output format, reads skill §Reference tables as SSOT, test-edit declaration, AI-Session trailer.
- `repo-audit` — 7-phase audit workflow orientation→inventory→cross-reference→invariants→contradiction sweep→demotion ledger→final report.
- `mutation-clearing` — 4-archetype triage taxonomy, spy isolation, accepted equivalent mutants ledger for zero-trust mutation clearing.
- `tests-writing` — live-path DoD ADR-11-I9: composition-root tests (`drive_session`/shipped CLI) would fail if production call site removed, anti-theater kill-check, flag matrices; authority remains `just check`/pytest.
- `feature-planning` — large feature plan→execute slices, GAP#/CT#/S#/T# traceability, deterministic authority, before/per/after edit gates, live-path tests, producer kill-checks, mutation handoff, minimal-code/evidence gates.
- `doc-maintenance` — at session close or when moving/pruning/adding file under `knowledge/` or `worklogs/`, ensures link integrity, llms.txt updates, HANDOFF freshness.

**Development workflow:**
- Branch `fa/<timestamp>-<slug>` from main, all changes via PR, harness tool does styling.
- Checkout roles: `~/First-Agent-dev` operator dev clone (VS Code/SSH, commits, PRs), `/srv/first-agent/repo/First-Agent-dev` clean deployment mirror updated only through operator-controlled flow, session workspaces managed clones with `.venv` + 4 hook seats + pre-commit envs prepared before model work.
- Bootstrap: `cd ~/First-Agent-dev; uvx --from rust-just==1.57.0 just agent-bootstrap` (or `just doctor` read-only check).
- Just recipes public surface (6): `doctor` (read-only readiness), `install` (locked dev sync + pre-commit prewarm + 4 hook seats), `fix` (ruff check --fix-only → ruff format → ruff check), `test` (pytest branch coverage + CLI coverage-floor gate), `check` (full blocking gate chain no fail-fast: lock-check, lint, mypy strict, pyrefly, authoring, contracts, shell-syntax, test+coverage; advisory vulture at end), `check-deep` (check + targeted-mutmut + targeted-semgrep on changed files, what pre-push runs). Compatibility alias `agent-bootstrap` emits `FA_AGENT_READY=1` only after READY.
- Lint autofix-first; pre-commit per commit ~60s on i5-1235U; pre-push per push runs check-deep; escape hatches `FA_HOOK_SKIP_FULL_CHECK=1 git push` operator-only, narrower `FA_SKIP_TARGETED_MUTATION=1` or `FA_SKIP_TARGETED_SEMGREP=1`; before PR review `just check-deep` green, CI duplicates.
- Judgment rules (S, BLE001, C901, duplicate-code/cyclic-import, TRY201/203/401, RUF012/013/015): fix design, waive only with `# noqa: <code> — <reason>` one-line rationale; bare `# noqa: XXX` without explanation fails CI.
- Type-checker errors fix by boundary validation + isinstance narrowing (pattern `src/fa/inner_loop/tools/base.py` `require_string`).
- Harness product behavior not done until composition-root test would fail if production call site removed (ADR-11-I9); prefer `tests/test_*_wiring.py`.
- Existing tests protected: deleting/renaming `tests/**` blocked at hook/harness seats; modifying during FIX requires `TEST-EDITS:` declaration in PR draft per pr-creation skill.
- Commit messages descriptive English present tense, push to branch, merge via PR only, `AI-Session:` git trailer per pr-creation skill.

**Query routing (AGENTS.md):**
- Architecture/patterns/decisions → `knowledge/adr/`
- Current task → `worklogs/HANDOFF.md`
- Research findings → `knowledge/research/`
- Specific decision/quote/number/date → primary source (URL/code/gist), not summary
- Terms → `knowledge/reference.md` §Terms
- Session state/event history/data layout → `knowledge/reference.md` §Session Data Layout + `session.db`

**Chain-of-custody rule:** If citing specific decision/quote/number/date, go to primary source and quote from there. Summaries in `knowledge/research/` are pointers not authoritative.

**Querying Artifacts — Tool Selection by Intent (ADR-14/15, S14, 2026-08-10):**
- Bootstrap mandatory unchanged: AGENTS.md → llms.txt MUST READ FIRST (5 files in order) → project-overview.md → HANDOFF.md
- Intent→tool exhaustive ordered:
  - What artifact types exist? List all skills/ADRs/research/… → `fs_blackboard_query(type="skill")` (or adr/research/instruction/prompt/codemap/antipattern/file_version) — typed content-hashed rows id/title/path/timestamps, triggers lazy index first call, 50-row cap, token-cheap, does NOT search file bodies.
  - Find artifact whose title/path mentions X → `fs_blackboard_query(type=…, key="api")` — key matches substring against entry metadata not body.
  - Which file versions did I touch? → `fs_blackboard_query(type="file_version")` — pre-<uuid>/post-<uuid> snapshots with read_set/write_set.
  - Find content somewhere — body substring across code AND docs, don't know type yet (DEFAULT START) → `fs_search(query="…", output_mode="files", limit=10)` — FTS5 BM25 + trigram <50ms after first-call index, returns paths with match_count + first-match snippet, respects .gitignore, add `glob="*.py"` for path filter, `include_tests=false` to exclude tests/.
  - Find files whose names/paths match glob → `fs_search(query="", glob="tests/**/test_*.py")`
  - I have path — read bytes now → `fs_read_file(path=…)`
  - Find callers/callees of known function → `fs_reach(symbol=…, direction=…, depth=…)` — S16 Python-only call-graph BFS over structural index, unresolved callees reported as `<unresolved:…>` (v1 in-file only).
  - I need matching lines inline → `fs_search(query="…", output_mode="matches", context_lines=1, glob="*.py")` — use sparingly after files-mode identified relevant files.
  - I need contiguous snippets → `fs_search(query="…", output_mode="regions", context_lines=2)` — token-efficient alternative to read_file.
  - I am about to WRITE → mutation guard flow: declare read_set + write_set + assumptions (base git rev-parse HEAD, llms.txt hash) + version_dependencies; blackboard runs `detect_conflict()`; on conflict structured `ToolResult.fail(code="conflict_detected")`, never silent overwrite (fixes Claude bug #55708).
- Combinators: Type-browse (blackboard query → skim titles → read_file), Body search S14b.1 (fs_search files → inspect paths → optional blackboard query for hash → escalate to matches/regions only when needed), Before writing gather read_set → mutation guard → blackboard serializes.
- Hard rules S14b.1: Do NOT slurp llms.txt/BACKLOG wholesale for full list (deprecated by ADR-14/15), use blackboard query or fs_search; Do NOT call blackboard query key expecting body hits — it searches metadata only, for body use fs_search; Do NOT invoke grep/rg/find/ag/ack via fs_run_bash for discovery — two approved discovery tools enforce token budgets 30KB caps and .gitignore pruning, raw shell grep historically caused 124-step timeouts; Do NOT call fs_search with matches/regions as first move — DEFAULT files; Do NOT invent additional search flags/tools.

**Code anchors S17:** Contract/invariant points carry `# §<stable-id>: <short description>` sparse ≤1 per ~200 lines stable never rename id once referenced, deprecate with `[deprecated in favor of §<new-id>]` suffix for one cycle then remove, indexed as doc_anchor symbols resolvable via `fs_reach(symbol="§<id>")` and findable via `fs_search(query="§<id>")`, referenced externally as `<filepath>#§<id>`.

**Iteration limits S14b.2:** Per-turn tool-call cap configurable per role in `~/.fa/config.yaml` → `runtime_limits:` via `max_iterations_planner/_coder/_eval` (+ _researcher/_code-reviewer stubs), per TURN one run_session call = one LLM response batch, testing-stage default 99 for all roles (operator will re-tune), `max_iterations: 6` stays role-less ADR-7 anchor, cap hits emit `StopInfo(point="iteration_cap")` + `run_stopped` log row + `iteration_cap` console event.

---

## 4. How would I contribute?

### Primary source: AGENTS.md §Working in This Repo + §Development Workflow + knowledge/skills/pr-creation/SKILL.md + knowledge/skills/doc-maintenance/SKILL.md + knowledge/instructions/

**Step-by-step contribution path (what an agent/human must do):**

1. **Bootstrap (mandatory, 5 files in order per AGENTS.md + llms.txt):**
   - Read `AGENTS.md` (universal session loadout, pre-flight, context-budget, skills, query routing, querying artifacts)
   - Read `knowledge/project-overview.md` §1.1 four pillars, §1.2 minimalism-first, §1.2.5 compliance-by-construction, §1.2.6 substrate formality, §1.2.7 pair over autonomy
   - Read `worklogs/HANDOFF.md` §60-second bootstrap — current state tables Landmarks/Gotchas/Backlog, §Next priority list (currently S14 READY awaiting operator apply, S13.11 closure 22ab73a, S14b search consolidation agreed, S13.9 cross-family workflow pending)
   - Read `knowledge/adr/DIGEST.md` — one-paragraph cheat-sheet per ADR
   - Read `knowledge/reference.md` — canonical definitions, features, session data layout
   - If HANDOFF and llms.txt disagree, llms.txt wins.

2. **Pre-flight checklist (AGENTS.md) — output cheap, skipping is failure mode:**
   - Run `git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md`
   - For every project-specific noun in prompt (axis, lens, pillar, harness, hook, ACI, UC1..UC5, NLAH, MCP, subtraction-first, minimalism-first, R-S-M, PTS-v1, etc.) run `grep -i "^\| \*\*<term>\*\*" knowledge/reference.md`
   - Symmetric reading: `grep -ril "<key-term>" knowledge/research/` open every match, cite most recent `compiled:` unless superseded
   - Subtraction-check 3 questions verbatim (Removing what makes this redundant? What capability lost if omitted? OSS precedent for not having it?); if third "none found" keep existing code as-is
   - Goal-lens declaration 4 slots: `goal_lens:`, `project-axes advanced:`, `subtraction evaluated:`, `session-type:`

3. **Find work:**
   - **Active:** `worklogs/HANDOFF.md` §Next (currently S14 patch apply, S13.9 live smoke, S14b fs_search consolidation, S13.11 final verification)
   - **Deferred with unblock trigger:** `knowledge/BACKLOG.md` — I-1..I-56, M-1..M-12, e.g. I-34 subagent OS-level writable-mount boundary P0 security with strict xfail executable record `tests/test_s5_isolation_boundary.py`, I-37 tool schemas sent twice 43% request bytes, I-48 mistral-medium-2604 greedy sampling, I-50 resumed workflow stage sends assistant last provider 400s, I-54 prompt caching capability-driven model, I-55 subagent WIP unfinished
   - **Implementation plans:** `worklogs/implementation-plans/` — parent plan `cli-trace-substrate-rebaseline-2026-07-25.md` v12 + subplans S1..S14, S13.11, S14b, etc. Each plan has GAP ledger, contracts CT1..CTn, steps S0..Sn, verification T1..Tn, mutation handoff MU1..MUn, artifacts inventory A1..An, anti-theater checklist, READY gate
   - **Formal substrate for discovery (not grep):** `fs_blackboard_query(type="skill")` lists typed artifacts, `fs_search(query="auth", output_mode="files", limit=10)` for body substring <50ms, `fs_reach(symbol="classify_batches", direction="down")` for call graph, `fs_read_file` for bytes

4. **Create branch:** `fa/<timestamp>-<slug>` from main per AGENTS.md. Example `fa/20260824-s14b-search-consolidation`. Never develop in `/srv/first-agent/repo/First-Agent-dev` clean mirror; use `~/First-Agent-dev` operator dev clone or managed session workspace `/sessions/<id>` which lifecycle prepares `.venv` + 4 hook seats + pre-commit envs before model use.

5. **Implement per minimalism-first + compliance-by-construction:**
   - Every new harness component passes 4-question test per project-overview.md §1.2; after UC5 must reduce at least one Pillar 3 KPI on reproducible benchmark else rejected
   - Every write declares `read_set, write_set, assumptions (base commit `git rev-parse HEAD`, llms.txt hash), version_dependencies` — I-6.1
   - Blackboard append-only content-hashed queryable `detect_conflict()` — I-6.2 — no silent overwrite returns fail code `conflict_detected` (fixes Claude bug #55708)
   - Simple chain planner→coder→eval default; parallel subagents only when substrate formal and task embarrassingly parallel with non-overlapping write_sets — I-6.3
   - Pair over autonomy: main 180k context, subagent clean slate ~1k never inherits full parent history, task solvable <600 tokens tool defs + <8000 chars output structured JSON, stateless scrubbed env isolated via WorktreeManager SharedDir v0.1 — I-7.1..I-7.5
   - Code anchors sparse ≤1 per ~200 lines stable never rename
   - Iteration limits per-turn configurable per role in `~/.fa/config.yaml` runtime_limits

6. **Tests (load `knowledge/skills/tests-writing/SKILL.md` before writing/changing tests):**
   - Live-path DoD ADR-11-I9: harness product behavior not done until composition-root test (`drive_session`/shipped CLI) would fail if production call site removed. Unit tests alone insufficient for session claims. Authority = pytest in `just check`/CI; steering = tests-writing skill.
   - Prefer `tests/test_*_wiring.py` patterns already in tree.
   - Existing tests protected: deleting/renaming `tests/**` blocked at hook/harness seats; modifying during FIX requires `TEST-EDITS:` declaration in PR draft per pr-creation skill.
   - Mutation testing: `mutmut` + `pytest-gremlins` verifies suite actually catches bugs not just executes lines. Scope `src/fa/sandbox` + session + state.py + subagent_envelope + subagent_runner + workflow_artifacts + stats.py + workspace_bootstrap.py. Full-src would be ~42x ~26,600 mutants ~916h exceeds 6h GitHub cap, needs sharded design Q26 option (d). Run `just check-deep` includes targeted-mutmut on changed files.

7. **Gates (run in order):**
   - `just fix` — auto-fix mechanical findings ruff check --fix-only → ruff format → trailing ruff check
   - `just test` — pytest branch coverage + CLI coverage-floor gate
   - `just check` — full blocking chain no fail-fast: lock-check, lint, mypy strict, pyrefly, authoring, contracts, shell-syntax, test+coverage; advisory vulture at end does NOT fail
   - `just check-deep` — check + targeted-mutmut + targeted-semgrep on changed files (what pre-push runs)
   - Before opening PR for review, check-deep green. Pre-push hook enforces; CI duplicates.
   - Judgement rules fix design not symptom; waive only with `# noqa: <code> — <reason>` one-line rationale; bare `# noqa: XXX` without explanation fails CI.
   - Type-checker errors fix by boundary validation + isinstance narrowing.

8. **PR creation (load `knowledge/skills/pr-creation/SKILL.md` before opening any PR):**
   - 5-intent classifier: RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE — classifier `src/fa/hygiene/pr_intent.py` closed enum `RESEARCH/ADR-RULE/IMPLEMENT/FIX/CHORE` with cross-category resolution `ADR-RULE > IMPLEMENT > FIX > RESEARCH > CHORE` per skill §Reference
   - PR description AND first commit message body MUST open with header lines per skill §Output format — e.g. `INTENT: IMPLEMENT`, `TEST-EDITS:`, `DEGREE-OF-FREEDOM CLOSED:`, `DETERMINISTIC MECHANISM:`, `AI-Session:` trailer
   - For FIX PRs: `DEGREE-OF-FREEDOM CLOSED:` + `DETERMINISTIC MECHANISM:` clauses must end with `repo/file.ext:line` resolving against staged tree (or `n/a (reason)`); tautological mechanisms (string-identical to degree-of-freedom) → CLASS WORKAROUND catalogued under `AP-003-shallow-fix-no-mechanism.md`
   - Every write target lands with named active consumer in same PR (AGENTS.md industry rule #3)
   - Every new ADR requires §Prior Art section (rule #4)
   - New docs go in right folder: guides/references → `knowledge/` (former `docs/` retired 2026-05-29), update `knowledge/llms.txt` §BY-DEMAND INDEX (now deprecated in favor of blackboard query + instant grep, but doc-maintenance skill still handles link integrity), project artifacts → `knowledge/`
   - Commit messages descriptive English present tense (`docs: add architecture note`), push to branch, merge via PR only
   - Link integrity: in same PR that removes/renames/replaces file, update/delete every reference via `grep -rn <old-path>` fix llms.txt, HANDOFF.md, DIGEST.md, reference.md, in-doc links, code comments — checklist `doc-maintenance` skill §When moving or pruning a doc
   - Session close: update `worklogs/HANDOFF.md` per §Session Protocol (overwrite §Current state, rewrite §Next), load doc-maintenance skill before committing, update `knowledge/llms.txt` rows per doc-maintenance skill

9. **Deploy/operate (for human operator, per `knowledge/instructions/README.md`):**
   - `01-install.md` one-time BIOS→Ubuntu→Docker→Tailscale→first run
   - `02-operations.md` repeated operations: update, rebuild, backups, restart, diagnostics, task launching (manual `fa run -r planner -i work-1`, workflow `fa workflow planner,coder,eval`, auto)
   - `03-live-server-ci-governance-plan-ru.md` CI/security/governance live-server
   - SSH hardening lives in `scripts/ssh-tailscale/README.md`
   - Roles cycle: planner (read-only, forms `pr_draft.md`) → coder (isolated workspace clone, cannot push without authorized draft per IntentGuard) → eval (read-only, verdict PASS/REPAIR_REQUIRED/REPLAN_REQUIRED/BLOCKED + `eval_report.json`) → optional compactor (small model for context compaction when `context_compaction_enabled` + declared in `models.yaml`)
   - Deployment topology: `docker-compose.fa.yml` — `first-agent` runs as 1000:1000, source bind `/repo` RO, `/sessions` writable, `/srv/first-agent/state` → `/home/fa/.fa` rw, then `/srv/first-agent/routing/models.yaml` → `/home/fa/.fa/models.yaml` ro nested bind requires stub file at host path (BACKLOG I-49 re-diagnosed 2026-08-03 — deleting stub breaks mount), `fa-egress-proxy` separate key-holding service, agent receives `FA_EGRESS_PROXY_URL` + `FA_PROXY_TOKEN_FILE`
   - Session layout authoritative: `~/.fa/sessions/<sid>/session.db` authority (event_log + session_meta), `~/.fa/sessions/<sid>/manifest.json` binding, `~/.fa/session-log/<run_id>/` projections (events.jsonl, llm_bodies.jsonl, pr_draft.md, attempt_history.json, eval_report.json, flow_state.json), `~/.fa/global_history.db` cross-run projection
   - Diagnostic ladder: `fa selfcheck --role coder` (healthz + routes), `fa routing-check --config ~/.fa/models.yaml` (3 roles checked), `fa probe --role <role>`, `fa conformance --provider <name> --json` (CONF-1..7 offline, CONF-8 exact production request profile live), `fa stats --run-id`, direct SQLite `SessionDatabase.read_event_rows(run_id=)`

10. **Workspace readiness:**
    - One command `cd ~/First-Agent-dev; uvx --from rust-just==1.57.0 just agent-bootstrap` performs host-tool setup + locked workspace readiness (uv/just/python≥3.13/env/hooks/marker/cache sentinel/uv.lock). `just doctor` read-only check.
    - VS Code folderOpen task is best-effort convenience not readiness authority.
    - Managed session workspaces lifecycle prepares `.venv`, all 4 Git-hook seats, pre-commit envs before model/provider work; model must not rebuild them.

### Current State — Big Patch Shipped (HEAD 234ca80)

- **Recent commits:** `234ca80 big patch`, `f2ed2c9 file work`, `22ab73a PLAN-cli-trace-S13.11-portable-tool-schema-contract closure`, `ef9d4fa fix`, `a14bb4e something` — indicates S13.11 implementation landed locally, awaiting operator verification? Parent plan v12 S14 closure patch prepared at `/home/user/s14-blackboard-artifact-index.patch` awaiting `git apply` + `fa update` + live smoke per HANDOFF.md S14 section.
- **S14 (blackboard artifact index, I-56):** READY for operator application — code/tests/doc edits complete in sandbox, 31 tests green, adds `src/fa/blackboard/artifact_index.py` lazy on-demand indexer for `knowledge/` artifacts (skills, ADRs, research, instructions, prompts, codemaps, anti-patterns + 6 root docs), wires into `fs_blackboard_query` with additive `indexed` stats field + title projection, doc alignment one-sentence clarification in AGENTS.md + llms.txt, no new CLI verb/config flag/dependency, append-only preserved via parent_id, symlink-safe `_is_within()`, conflict safety via `Blackboard.detect_conflict` filters by type (disjoint namespaces), session-scoped.
- **S13 multi-provider conformance:** CLOSED live-verified 2026-08-09 — `fa selfcheck` OK, `routing-check` OK, conformance aigate CONF-1..7 OK exit0 live 200 through proxy no 401, sampling omission PASS (0/7 bodies contain temperature/top_p), prompt_cache_* on wire PASS (7/7 carry key+retention), mistral 6/7 OK (CONF-5 FAIL trailing assistant expected per strict MessageRules), nvidia_build 6/7 OK (CONF-7 503 rate limit deferred), anymodel 404 provider-side deferred, stats cache hit 89% warm 72% cumulative 76-99% per-turn after warm-up, workflow planner,coder,eval 3/3 stages ran eval_report.json `eval_independence: {disjoint:true, stance:"neutral"}`.
- **S13.11 portable tool schema contract:** READY per plan v5 2026-08-16 — fixes CD1..CD9 (incompatible source schema type: [...] nullable unions in fs_search.glob/types/exclude_dirs, dead parameter types, no portable authoring contract, contract errors swallowed, conformance omits tools, --provider does not select provider, no shared exact tool-corpus producer, cache key ignores real tool names/schemas, no live tool-aware proof). Mechanism: simplify fs_search source schema → validate every registered schema against PTS-v1 → render same schema unchanged → share one `_build_run_tool_registry` producer between `_cmd_run` and CONF-8 → filter live chain to requested provider → send CONF-8 → natural fa run smoke. Goals G1..G6, contracts CT1..CT9, verification T1..T13 + live T11/T12, mutation MU1..MU7, 32 artifacts A1..A32, risks RK1..RK12, deferred DF1..DF4. Current HEAD includes closure per `22ab73a`.
- **S14b fs_search consolidation (agreed 2026-08-10):** Plan replace `fs_instant_grep` + `fs_grep` + `fs_glob` with single `fs_search` tool (3 output modes files|content|count, default files paths-only <50ms FTS fast path, literal-by-default with regex=true opt-in, context_lines=1 default content mode hard 5-line cap, glob absorbed as name-listing path when pattern="", raw bash grep/ripgrep/find/ag/ack verboten). Discovery tools after S14b = 3: `fs_blackboard_query`, `fs_search`, `fs_read_file`. Ships as separate S14b patch after S14 live-smoke, not included in S14 to keep bisection clean. v1 scope excludes BM25/embedding/artifact type-scoped search (S15+).
- **Open items not addressed in S14 (operator-deferred per HANDOFF.md):** S13.9 cross-family workflow live smoke (protocol script `/home/user/s13-9-run.sh` prepared), thinking-mode toggle and Gemini adapter S13.8 backlogged per operator pivot 2026-08-10 (thinking modes NOT priority), I-34 subagent OS-level writable-mount boundary Q19/V24/V25 P0 security, I-37 tool schemas sent twice, I-40 config gate, etc., pre-existing test failures `test_providers_chain.py` 2, `test_pyrefly_import_topology.py` 2 missing binary, `test_s10a_cli_coverage.py` 1 needs docker/tmux, etc. not S14 regressions.

### Evidence of Readiness for Next Slice

- **Why project exists:** cited project-overview.md §1, README.md architecture, FEATURES.md, reference.md authority — all primary sources, not summaries.
- **How created:** cited ADR-1..ADR-15 chronological with amendments, BACKLOG M-1..M-12, HANDOFF S1..S14, implementation plans v12 parent, pyproject.toml gates, deployment anatomy.
- **Goals/guidelines:** cited four pillars + 4 KPI TBD, minimalism-first 4-question test, compliance-by-construction I-1..I-5 + anti-shallow-fix gate, substrate formality I-6.1..I-6.4, pair over autonomy I-7.1..I-7.5, AGENTS.md pre-flight 5 steps, context-budget, industry rules, 6 loadable skills, dev workflow branch/PR/just recipes, code anchors S17, iteration limits S14b.2, query routing, chain-of-custody, querying artifacts intent→tool table + combinators + hard rules, formal substrate session.db 3 tables authority hierarchy.
- **Contribute path:** cited bootstrap 5 files, pre-flight commands, find work via HANDOFF/BACKLOG/plans + formal substrate tools, branch naming, implementation principles, tests-writing live-path DoD + mutation, gates just fix/test/check/check-deep, PR creation 5-intent classifier + header lines + TEST-EDITS + DOF CLOSED/MECHANISM + AI-Session trailer + link integrity + session close protocol, deploy/operate instructions + diagnostic ladder + session layout + workspace readiness.

**Next action awaiting your details:** I have cloned repo at `/home/user/First-Agent-dev`, HEAD `234ca80`, and prepared understanding report. When you pass implementation plan details (e.g., S14b search consolidation, S13.9 cross-family smoke, S13.11 final live verification, or other slice), I will execute per that plan's contracts (CT), verification (T), mutation handoff (MU), and DoD, using formal substrate tools (`fs_blackboard_query`, `fs_search`, `fs_reach`, `fs_read_file`) with read_set/write_set/assumptions/version_dependencies declared, and run `just check` / `just check-deep` before PR.

---
*This report follows AGENTS.md §Pre-flight Step 2 term expansion (Pillar, Axis, Harness, Hook, ACI, UC1..UC5, NLAH, MCP, minimalism-first, subtraction-first, R-S-M, PTS-v1), Step 3 symmetric reading (grep research for blackboard, token efficiency, etc.), Step 4 subtraction-check (Removing what makes this redundant? knowledge/README.md + reference.md + DIGEST.md already cover 80% but this report is synthesis for operator screening; capability lost if omitted: no single proof of readiness; OSS precedent: repo-audit skill 7-phase report), Step 5 goal-lens declaration: goal_lens = "Provide evidence-backed understanding of First-Agent existence, creation, goals, guidelines, contribution path to unblock next implementation slice" — project-axes advanced: A noise-reduction (clarify deprecated BY-DEMAND INDEX vs formal substrate), B context-finding (map ADRs/BACKLOG/HANDOFF/plans), C goal_lens-advancement (close screening gate) — subtraction evaluated: YES — answers in Step4 — session-type: research-briefing.*
