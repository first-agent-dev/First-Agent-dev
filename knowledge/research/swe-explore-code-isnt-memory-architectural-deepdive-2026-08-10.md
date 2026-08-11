# SWE-Explore + Code-Isn't-Memory → First-Agent architectural deep-dive (2026-08-10)

**Status.** Research synthesis. No code written yet. Every concrete idea below is (a) sourced to a specific finding in the two arXiv papers, (b) mapped against First-Agent's existing substrate, (c) given an ROI estimate relative to FA's Pillar-3 goal ("most token/tool-call efficient harness").

**Primary sources.**
- [SE] Zhang et al., *SWE-Explore: Benchmarking How Coding Agents Explore Repositories*, arXiv:2606.07297v1, 5 Jun 2026 (Shanghai Jiao Tong et al.).
- [CiM] "Code Isn't Memory: A Structural Codebase Index Inside a Coding Agent", arXiv:2606.22417v1, 21 Jun 2026 (SuperCoder / Opus-4.7 ablation, leak-audited).
- Supporting: Sen et al., *Is Grep All You Need?*, arXiv:2605.15184 (May 2026) — already used in our fs_search design; referenced inside CiM.

---

## §1. Findings distilled from the two papers, in plain language

### 1.1 SWE-Explore (what agents actually do wrong)

SE isolates *repository exploration* from patch generation and benchmarks it at line-level granularity across 848 issues, 10 languages, 203 repos. Main results:

- **Finding F1: File-level localization is already "good" — line-level recall is the bottleneck.** On K=5 (return top-5 regions), general agents hit the *right file* 84–95% of the time (HitFile 0.65–0.95 across agents with GPT-5.4), but *line-level recall inside those files* is only 0.11–0.19. They land in the right file, then read the wrong 30–80 lines.
- **Finding F2: one-shot retrieval (BM25/TF-IDF/dense embeddings) ≈ Random.** BM25 HitFile = 0.08, nDCG@500 = 0.02; TF-IDF = 0.14/0.05; Potion dense = 0.09/0.03. Only agentic multi-step exploration reaches the useful regime. This is consistent with the "Grep-is-all-you-need" paper — but it goes further: not even one-shot *vector* search helps.
- **Finding F3: general coding agents behave surprisingly alike.** Claude Code, Codex, OpenHands, Mini-SWE-Agent, AweAgent — different harnesses, similar profiles: high HitFile, high FUH (early useful hit), low Recℓ. Implication: the bottleneck is *architectural*, not *model-power* — swapping to a stronger model doesn't close the line-recall gap (Table 5: GPT-5.4-mini is on par with GPT-5.4 on exploration).
- **Finding F4: The specialized agent that *iteratively walks the call graph* (CoSIL) is the only one that materially raises line-level recall.** CoSIL HitReg=0.54, Recℓ=0.79, F1=0.60 vs ~0.15–0.23 for everything else. Its win is multi-file graph traversal, not smarter ranking.
- **Finding F5: Context Efficiency (fraction of retrieved lines that are actually in ground-truth core) has the *highest* downstream correlation with resolve rate (r=0.95, ρ=0.74).** Recall@100 ρ=0.85. nDCG has high Pearson but lower Spearman because it separates tiers but ranks neighbors unstably. Translation: what matters is (a) get core lines into the top-100 quickly, (b) don't drown them in noise.
- **Finding F6: Missing core evidence hurts far more than redundant evidence hurts.** In the controlled α-fraction degradation experiment, resolve rate stays low until ~50–75% of core regions are present, then jumps; padding with random non-core after that point does almost no damage. This is an explicit refutation of the "too much context confuses the model" folk-belief (on these models, at Opus-4.7/GPT-5.4 capability level): noise after the core is present is cheap; missing core is fatal.

### 1.2 Code-Isn't-Memory (what actually moves the needle on $/solve)

CiM runs a leak-audited, model-controlled (Claude Opus 4.7 fixed), three-seed ablation across SWE-PolyBench+SWE-bench-Pro (n=91, 3 languages), three arms: SC-ON (with structural index: vector+BM25+call-graph), SC-OFF (same harness, index tools removed), OpenCode (independent ripgrep-based open-source harness). Results:

- **Finding C1: Causal effect of a structural index is large on localization, moderate on resolve.** Within-harness ON vs. OFF: loc acc@5 84.5% vs. 44.3% (∆=+39.6pp, p<0.0001); resolve 50.4% vs. 41.9% (∆=+7.9pp, p=0.003). Cross-harness vs. OpenCode: +6.0pp resolve (p=0.087, directional), acc@5 +8.1pp (p=0.080).
- **Finding C2: The gain is paid for in effort, not cost.** $/cell SC-ON $1.15 vs SC-OFF $1.19 (null, p=0.73). Mean turns: 28.3 vs 36.2 (−22%, p<0.0001). Mean tokens: 10.1k vs 11.1k (−9%, p=0.027). Wall-clock: 4.5min vs 5.5min. The index is cost-neutral per cell and $/solved drops from $2.84 to $2.30 (−19%) because more cells resolve.
- **Finding C3: The big gains are concentrated in *multi-file* tasks.** Breaking out by gold-file count (Fig. 4): ON vs. OFF acc@5 on 1-file: 85.3 vs. 74.2 (+11pp); on 2-file: 74.1 vs. 49.0 (+25pp); on 3+-file: 91.3 vs. 44.9 (**+46.4pp**). This matches the F4/CoSIL observation: reachability-based ranking across file boundaries is what grep+read does poorly.
- **Finding C4: The View B scoring correction matters.** If you count paths shown in engine result-lists as "reached" (View A), you inflate acc@5; if you require the agent to *actively choose* a path from the list by issuing a grep/read (View B — the behaviorally real metric), the index still wins but the picture is more honest: the agent has to *act on* the hints, not just be shown them.
- **Finding C5: Grep+read is a surprisingly strong baseline if the agent is competent.** OpenCode (plain ripgrep+read+glob+bash, no index) hits 45.3% resolve on the same cells vs. SC-ON's 50.4%; loc acc@5 75.3% vs. 84.5%. So a competent agent can do ~90% of what a structural index does — the structural win is real but not a 2× game-changer, and it's concentrated in multi-file work.
- **Finding C6: First-gold-rank CDF (Fig. 3) is the most actionable single diagnostic.** SC-ON places gold at rank 1 in 77.4% of cells (vs. 58.4% OpenCode, 33.3% SC-OFF). That number cascades into turns, tokens, and resolve.

---

## §2. Mapping FA's current substrate against the paper findings

FA today has the following relevant substrate (source-verified on this sandbox tree at commit `103fb89` + uncommitted S14 patch):

| Capability | Present today? | Where | Paper-relevant? |
|---|---|---|---|
| Append-only content-hashed blackboard (session DB) | ✅ | `src/fa/blackboard/blackboard.py`, `session_db.py` | **Core.** Both papers' winning pipelines rely on the agent *remembering what it already read/changed*; FA's blackboard is unique here — neither SuperCoder nor OpenCode have a formal append-only substrate. |
| File_version mutation tracking (pre/post images, read_set/write_set) | ✅ | `mutation_guard.py` | **Core.** CiM's detection of "agent actually arrived at a file" (View B) is reconstructible from blackboard rows without custom tracing. |
| Typed artifact index (skills/ADR/research/...) | ✅ (S14) | `artifact_index.py`, `fs_blackboard_query` | Strong: gives agents fast listing of non-code knowledge. Not relevant to code localization per se. |
| fs_instant_grep (FTS5 trigram over whole repo, paths only, <50ms) | ✅ | `tools/instant_grep.py` (fts.db) | Analogous to SuperCoder's lexical fast path, but paths-only, no content/snippets/score. |
| fs_grep (git-grep with streaming fallback, returns matched lines) | ✅ | `tools/grep.py` | The workhorse, default limit 20 lines, max 100 lines, max_context_bytes=2000. |
| fs_glob (name pattern) | ✅ | `tools/glob.py` | Present. |
| fs_read_file (with start_line/end_line range) | ✅ | `tools/read_file.py` | Correct API shape for line-budgeted reading. |
| ReAct coder loop with parallel tool dispatch | ✅ | `coder_loop.py`, `loop.py` | Multi-tool-call parallelism already present (CiM uses this too). |
| Compact/projection layer elides oversized results to artifacts | ✅ | `projection.py`, `artifacts.py` | Token-budget discipline on tool outputs — SWE-Explore's "Context Efficiency" metric is basically a runtime score for this. |
| Runtime limits (iterations/bash timeout) | ✅ | `runtime_limits.py` (default max_iter=6, bash_timeout=30s) | **Mismatch with papers.** CiM uses 30-min wall-clock, no per-turn cap; FA caps at 6 iterations — this is far below what SWE-bench-class tasks require and was set for short "coding+PR" UC1 sessions, not deep exploration. |
| Compaction (history summarization) | ✅ | `compaction/` | Present, but currently simple; no "grounding set" mechanism. |
| Profile-based toolset reduction (researcher/verifier/code-reviewer/implementer/planner) | ✅ | `profiles.py` | Strong for token efficiency — researcher profile is 4 tools/600tok vs 3000tok full set. Aligned with F5/C2 (token efficiency is high-leverage). |
| Structural call graph / symbol index | ❌ | — | Direct gap CiM shows pays off on multi-file (+46pp acc@5). |
| BM25 over source files (separate from FTS instant_grep) | ❌ — instant_grep is substring, not BM25-ranked | `instant_grep.py` uses FTS5 trigram | FTS trigram is fine for exact substring but does not TF-IDF rank; BM25 would reorder hits by rarity. Low cost addition inside sqlite. |
| Embedding/semantic code search | ❌ (v0.2 out of scope per project-overview §4) | — | CiM uses it as one of three legs but the paper's ablation doesn't isolate it vs BM25 vs graph; FA's scope decision holds: defer until we have a measured gap lexical can't close. |
| Tree-sitter/AST parser for symbol/calls extraction | ❌ (stdlib `ast` is used for authoring_rules exports-scan over FA itself, not over target repo code) | `authoring_rules/` | Required for call graph. |
| Merkle-tree incremental re-index | ❌ (we have no structural index to diff) | — | CiM does this; optional — at our repo sizes (First-Agent-dev ≈ 25k LOC Python + 200 docs), a full rebuild is <1s. |
| Structured "surfaced set" / first-gold-rank telemetry | ❌ (no per-session exploration trace) | event_log exists but doesn't track "first time a gold path was read" | Required for A/B testing our own improvements (Pillar 4: iteration via measurement). Without this we are flying blind on the exact metric CiM shows is most actionable. |
| Line-budgeted exploration return schema (return top-K regions, each a (path,start,end)) | ❌ | — | CiM's two engine tools and SWE-Explore's explorer output format. Currently our tools return paths OR lines but no first-class "region list" concept. |
| bash grep/rg usage ban in favor of substrate search | ⚠️ partial (AGENTS.md mentions `grep -ril` deprecation but no enforcement) | AGENTS.md | SWE-Explore shows agentic bash grep is *part* of the high-performing profile (OpenCode uses it as primary), but unconstrained bash grep historically caused FA's 124-step timeouts. Middle ground: allow shell *after* structured tools, or forbid only bare unbounded greps. |

### First-order readout

The single most important sentence from both papers, for FA, is:

> *"The dominant failure is reaching the right file but reading the wrong lines; iterative exploration with a reachability signal across files cures most of it; pure one-shot lexical/semantic retrieval is near-useless."*

This is actually a *good* story for FA: we already have 80% of the winning harness (append-only blackboard, structured tools, projection/elision, per-profile token discipline, multi-tool parallelism). What we don't yet have — in priority order implied by the papers' effect sizes — are:

1. **The exploration metrics themselves, so we can see regressions/wins.** Without acc@k / first-gold-rank / Context Efficiency on our own evals, we are guessing. (This is pure measurement, no AI, ~200 LOC.)
2. **A multi-file reachability signal (call graph).** This is the single biggest lever CiM measured (+46pp on 3+ file changes). Does not require embeddings; can be done with stdlib `ast` for Python, plus a regex-lite fallback for other languages at first.
3. **BM25 ranking on top of FTS**, to push identifier-rich hits above generic substring hits. ~10 LOC in sqlite (`create virtual table ... using fts5(... tokenize='porter unicode61', ...)` + `order by bm25(...)`).
4. **Line-budgeted reads in the tool protocol**, so the agent gets a *region list* and can paginate. Today `fs_read_file` supports `start_line/end_line`, which is the right primitive; we don't yet have a tool that *returns* regions.
5. **Iteration-budget tuning.** Default `max_iterations=6` is far too low for the exploration-relevant tasks SWE-bench style — but that's a v0.2/UC5 question. The iteration cap should be role-settable and measured, not a blanket constant.
6. **Embeddings/semantic search.** Not indicated by either paper as a near-term win given our corpus size; defer per v0.1 scope.

---

## §3. Prioritized architectural ideas, mapped to FA files

Each item below follows the format: **source → idea → mechanism → files → ROI → what we'd measure.** I've separated them into tiers (P0 = highest ROI / lowest effort, deterministic; P1 = moderate effort, high confidence from the literature; P2 = larger investments, need evidence first).

### Tier P0 — Measurement & hardening (deterministic, no new ML, ~1–3 days)

These are the cheapest and highest-leverage because they are prerequisites to validating anything else.

#### P0-1. Exploration telemetry in blackboard + event log (CiM §4.7 View B, SE §F5)

**Source.** CiM's entire causal claim rests on measuring *which files the agent actually arrived at* (View B: tool result lists don't count — the agent must issue a `read`/`edit`/`grep` that names the path). SE's F5 ranks Context Efficiency and first-useful-hit as the two highest-correlation metrics with resolve rate.

**Mechanism.** Add a per-session `surfaced_paths: dict[path, first_turn_index, first_tool]` maintained in `SessionState` or the event-log layer. Recorded on every `fs_read_file`, `fs_edit_file`, `fs_write_file` call (and the `read_set` declared through mutation guard). *Not* recorded when paths appear only in tool *results* (instant_grep/grep returning a hit list) — that's CiM View A vs. B. Expose a small helper `get_exploration_stats(ground_truth: set[Path])` returning `first_gold_rank`, `acc_at_k` for k∈{1,3,5,10}, `ctx_efficiency` (lines read from gold / total lines read).

**Files.**
- `src/fa/inner_loop/state.py` — add `surfaced_paths: dict[str, dict]` field, initialized empty.
- `src/fa/inner_loop/loop.py` (or a new `hooks/exploration_metrics.py`) — hook that runs on every tool *call* (not result) and records the path arguments.
- `src/fa/blackboard/blackboard.py` — optional: write structured `type=exploration_step` rows for easy post-hoc analysis (nice but not required).
- New file `src/fa/eval/exploration_metrics.py` — pure functions to compute acc@k/ctx_eff/FUH from a trace.
- Tests: `tests/test_exploration_metrics.py` (C1 deterministic, no LLM).

**ROI.** Very high. Without this we cannot replicate CiM's ablation or verify any future change actually improves exploration quality, per Pillar 4. Today we have zero visibility into whether a session failed because the model couldn't write the patch or because it never read the right file.

**Measurement.** On our existing SWE-bench-lite style fixtures (we can build a small set of ~20 local fixture tasks in-repo), acc@5 baseline for our current harness. CiM's SC-OFF (analogous to current FA) lands at 44% acc@5 with Opus-4.7; with a mid-tier model we expect 25–45% depending on model — but we need the number to track.

#### P0-2. BM25 ranking on `fs_instant_grep` (SE F2 context, CiM §3.2 lexical index)

**Source.** CiM's lexical index is BM25 over identifiers+tokens, one of three legs. Current `instant_grep.py` uses FTS5 trigram for substring (good for partial matches like `content_ha`→`content_hash`) but does not use BM25 ranking. SQLite FTS5 supports BM25 natively with zero new dependencies.

**Mechanism.** Change FTS table creation to `tokenize='porter unicode61 remove_diacritics 2'`, use `ORDER BY bm25(fts, 1.0, 1.0)` in the MATCH query. Keep trigram substring search as a separate fallback for partial tokens (or add a `match_mode` param: `substring` (default) vs `bm25_token`).

**Files.**
- `src/fa/inner_loop/tools/instant_grep.py` (~10 LOC change).
- Tests: add BM25 ranking cases to `tests/test_instant_grep.py` (e.g., "rare identifier ranks above common word").

**ROI.** High. Very small change; directly improves the "first useful hit" metric (CiM Fig 3) which is the highest-variance upstream of resolve. Not a silver bullet, but almost free.

**Caveat.** Need to reindex or rebuild FTS table; instant_grep already has reindex logic? Check — if FTS is per-session at `.fa/fts.db` we can rebuild lazily.

#### P0-3. Enforce the "no raw grep via bash" rule (CiM §6 OpenCode performance)

**Source.** CiM shows OpenCode (pure ripgrep+read) is *competitive* with the structural index on everything except multi-file — but the key is *disciplined* ripgrep with result caps, not unrestricted `grep -r`. Our current AGENTS.md language deprecates `grep -ril` for token-cost reasons; we should mechanically block it the same way mutation guard blocks unsafe writes.

**Mechanism.** In the bash-intent or runtime-limit layer (see existing `bash_intent.py`), detect raw `grep|rg|ag|ack|find` invocations that bypass our tools, return a structured ToolResult.fail directing the agent to use `fs_search`/`fs_instant_grep`/`fs_grep`/`fs_glob`. One allow-list: when the grep is a legitimate pipeline *component* (e.g., `ps | grep fa`), not a repo-content search — distinguishable by whether there's a path into workspace_root.

**Files.**
- `src/fa/inner_loop/bash_intent.py` — add a detector.
- `src/fa/inner_loop/runtime_limits.py` — if needed.
- AGENTS.md/llms.txt — tighten language to "never shell-grep repo contents; use fs_search/fs_instant_grep/fs_grep."

**ROI.** Medium-high. Removes the 124-step timeout class of failure and forces all discovery through the measured path, which is what makes P0-1's metrics meaningful.

#### P0-4. Tighten loop cap configurability & track per-turn budget exhaustion (SE F4 "agentic loops > one-shot")

**Source.** SWE-Explore agents typically take 20–60 tool calls to localize (CiM reports 28.3 mean turns for SC-ON, 36.2 for SC-OFF). FA's default `max_iterations=6` is fine for short "edit this file" tasks but prevents genuine exploration. The cap exists for good reason (runaway loops were observed in the early harness); the fix is not "remove the cap" but (a) make it per-profile, (b) surface a structured warning when the cap is hit so the loop terminates with a useful diagnostic instead of truncating, (c) track "exploration turns spent" vs "editing turns spent" as a metric.

**Files.**
- `src/fa/inner_loop/runtime_limits.py` — expose a profile-overridable limit (researcher=3, code-reviewer=6, implementer=30, planner=15).
- `src/fa/inner_loop/loop.py` — raise a specific, catchable exception (not silent stop) at cap.
- Tests.

**ROI.** Medium. Unblocks serious multi-file bug-fix tasks (SWE-bench scale). Risk: higher token spend. Mitigation: keep a conservative default and let role profiles opt into higher budgets.

### Tier P1 — Structural index, low-friction version (CiM §3.2 call graph, SE F4/CoSIL)

#### P1-1. Symbol-and-call-graph index (Python first, stdlib `ast`)

**Source.** CiM's biggest measured win comes from the *graph* leg (vector+BM25+graph), and the graph is the only component that plausibly explains the +46pp acc@5 on 3+-file tasks (per §6.3 / Fig. 4). CoSIL (SE's highest-recall agentic explorer) is essentially "iterate grep over call-graph edges."

**Mechanism.**
- New module `src/fa/structural/` (or under `blackboard/` — naming TBD).
- `symbol_index.py`: walk workspace Python files with stdlib `ast`, extract top-level and nested `FunctionDef/AsyncFunctionDef/ClassDef`, record name, file, start_line, end_line, signature (args), docstring summary (first line).
- `call_graph.py`: for each function, record which other functions it calls (resolvable statically within the repo; cross-file calls via import-resolution best-effort, ignoring dynamic/importlib).
- Build on first session startup (or lazy on first call); at FA's own size (~25k LOC) this is <1s. Invalidation on `fs_write_file`/`fs_edit_file` can simply reparse the changed file (Merkle-diff per CiM §3.2) — that is `os.stat` mtime check, easy.
- Storage: a new SQLite database `.fa/structural.db` with tables `symbols(path, qualname, kind, start_line, end_line, signature, docstring, file_hash)` and `calls(caller_path, caller_qualname, callee_path, callee_qualname)`. No new dependency.

**Files.** New `src/fa/structural/*.py` (~400–600 LOC total including incremental update). Tests with a fixture repo.

**Non-goals for v1 of this.** Multi-language (just Python first — tree-sitter for other languages is a P2 follow-up). No cross-package resolution into `site-packages`. No type inference. No semantic edge types.

**ROI.** High, with moderate effort. Predictably large gain on multi-file Python tasks (which is the majority of FA's UC1 work on its *own* codebase, i.e. self-improvement loops). Risk: static Python call graphs have well-known gaps (dynamic dispatch, decorators, monkey-patching), but:
- CiM's graph index is produced by tree-sitter which has *similar* static limitations, and the win still materializes.
- The tool should be explicit about its confidence: edges with unknown resolution are surfaced with a "heuristic" tag.

#### P1-2. New tool `fs_reach` ("find files/functions reachable from X") — the graph-leg tool

**Source.** CiM's `codebase_graph` traverses callers/callees from a symbol and returns ranked related symbols. This is the tool that produced the 3+-file win.

**Mechanism.** Tool `fs_reach` (or `fs_code_graph`):
- Params: `symbol: str` (required, e.g. "fs_blackboard_query"), `direction: "callers"|"callees"|"both"`, `depth: int=1`, `limit: int=20`, `snippets: bool=false`.
- Returns: `{"symbol": {...}, "neighbors": [{"path":..., "qualname":..., "start_line":..., "signature":..., "snippet":..., "distance":...}], "truncated": bool}`.
- Backed by P1-1's tables.
- Registered only in `implementer` and `planner` profiles (researcher/code-reviewer/verifier don't need it — token discipline).

**Files.** New `src/fa/inner_loop/tools/code_graph.py`; register in `profiles.py`; docs in AGENTS.md/llms.txt.

**ROI.** High. Direct implementation of the single biggest win in CiM. The tool is narrow (one job, no LLM in the loop) → easy to test deterministically. Expected effect: 20–40pp acc@5 on multi-file changes, per CiM's §6.3, and 15–25% reduction in mean turns/tokens on those tasks.

#### P1-3. Region-list return shape for exploration tools (SE §3.1 "ranked list of relevant code regions")

**Source.** SE's output format is `P = (r_1...r_K)` with each `r_i = (p_i, s_i, e_i)` — file path + line range. This is the unit that SWE-Explore scores; CiM's engine returns a similar shape. FA's current tools either return *paths only* (instant_grep, glob) or *flat match lines* (grep, no region grouping).

**Mechanism.** Add an optional `regions=true` mode to `fs_instant_grep` and `fs_grep` that groups consecutive matches within `context_lines` into a compact `{path, start_line, end_line, snippets:[...]}` region list, with `limit` interpreted over regions not over match lines. Add `start_line/end_line` fields even in normal mode. This is a backward-compatible additive response field.

**Files.** `tools/instant_grep.py`, `tools/grep.py`. Tests.

**ROI.** Medium. Directly targets the "land in the right file, read the wrong window" failure (F1). Makes the agent's read budgeting more intentional: "I got 5 regions; I'll read each in 80-line windows starting at `max(1,region.start-20)`," rather than scattering `cat -n` calls.

#### P1-4. Unified `fs_search` (already planned as S14b) — promote BM25+regions+glob merge into it

**Source.** Already in plan from our earlier S14b discussion; the papers reinforce the shape.

**Mechanism / v1 spec update informed by this research:**
- Three modes `files|content|count` stays.
- `output_mode="files"` default stays (token discipline — CiM/Cursor/Agentless all surface paths first).
- Add `order="bm25"` option (P0-2) in addition to deterministic `match_count_desc` (default for reproducibility).
- Add `regions: bool=false` (P1-3).
- Add `glob`/`path`/`include_artifacts` filters (already planned).
- Keep `regex=true` opt-in (literal by default — both papers support: literal identifier matching dominates code search).
- **No** `semantic=true` / embeddings yet (deferred).
- **No** hardwired call-graph expansion in v1 — that's P1-2's separate `fs_reach` tool (the two tools compose: `fs_search` → see candidates → `fs_reach` from the most promising symbol).

**Files.** Already scoped: new `tools/fs_search.py`, deletions of `grep.py/instant_grep.py/glob.py`, profile updates, AGENTS.md/llms.md.

**ROI.** High. Consolidation reduces tool-count (good for toolset tokens per ADR-8 style profile budgets) and gives us a single place to add P0-2/P1-3.

### Tier P2 — Require evidence before building

#### P2-1. Tree-sitter based multi-language parser (CiM uses it)

**Status.** Useful for Go/TS/Rust support if/when FA's use cases expand beyond Python. First-Agent itself is Python; the v0.1 controlled allowlist of user repos per project-overview §6 is Python-first.
**Effort.** ~1–2 weeks to integrate tree-sitter grammars for Python/Go/TS/Rust into P1-1's index.
**Wait for.** Multi-language repo use case appearing in real sessions; or when S14b/P1-1 is proven to help on Python.

#### P2-2. Embeddings-based semantic code search (CiM vector leg)

**Status.** The paper does not isolate the vector leg's marginal contribution (the three legs are ablated together). From SE Table 6, standalone dense retrieval is ~0.03 HitReg (near random) — only useful in *fusion* with BM25+graph. FA v0.1 scope already defers embeddings.
**Effort.** Modest if using aigate free API; still requires: index build, chunking strategy, incremental update, fallback when API is unavailable, test fixtures for non-determinism.
**Wait for.** A measured failure mode after P1-1/P1-2 lands where (a) agent reaches correct file, (b) callee/caller expansion is insufficient, (c) terminology mismatch (e.g., code says "invalidate_cache" but plan says "drop entries") is provably the cause. That is the case embeddings solve — until we have trace evidence of that failure we are in FOMO territory.

#### P2-3. CoSIL-style iterative graph-walk agent

**Status.** CoSIL is the only SE explorer that broke the line-recall barrier (Recℓ=0.79 vs ~0.15 for others). It runs an inner loop that proposes symbols, expands their callers/callees, and re-ranks. This is essentially a sub-agent dedicated to exploration.
**Effort.** Medium-high (design subagent protocol, search budget, output schema). Worth doing once P1-1/P1-2 exist, as a planner/implementer sub-agent "find all code relevant to X" — strongly aligned with FA's subagent envelope in `subagent_runner.py` (I-55 type=plan deferred, but this is a different subagent purpose: retrieval, not planning).
**Wait for.** P1-1/P1-2 done and measured.

#### P2-4. Adaptive context / grounding-set compaction (CiM mentions "compaction disclosed but not load-bearing")

**Status.** Current FA compaction is simple history summarization. A more principled approach is: maintain a *grounding set* G of (file, region) that the agent has explicitly read/edited + the current task + relevant blackboard entries; when the message history is compacted, keep the grounding set verbatim and summarize the rest. SE F6 (core > noise) implies that compacting should never drop grounding, but can aggressively summarize non-core turns.
**Wait for.** Evidence of compaction-induced amnesia in traces (P0-1 will give us the data to see this).

#### P2-5. Relevance score field on tool results

**Status.** Earlier we considered and *rejected* this for v1 fs_search in the S14b research note (reasons: LLM over-relies on scalars, non-determinism from embeddings/BM25 tunings, testing flakiness). Reconsider only if P1-2/P1-3 evidence shows agents make systematically bad choices among equally-looking candidates. BM25 scores are not interpretable across queries; RRF-fused scores even less so. Keep the ordering deterministic in v1 and only add a numeric score if we have a concrete LLM-consumption use for it (e.g., threshold-based truncation).

---

## §4. Recommended sequence (respects §1.2 minimalism-first / Pillar 4 iteration)

1. **Land S14 first** (already queued — blackboard artifact index).
2. **S14b — unified `fs_search`** (P1-4) without BM25/graph — just the consolidation of grep/instant_grep/glob into 3-mode tool; deterministic ordering; `context_lines=1` default. ~1–2 days.
3. **S15a — Exploration telemetry (P0-1) + bash grep block (P0-3) + per-profile iteration caps (P0-4).** ~1–2 days. This is our measurement bed.
4. **S15b — Build a small in-repo eval harness.** 20 representative local tasks (e.g., "add a limit clamp to tool X", "fix bug Y from BACKLOG", "find where Z is defined") runnable with `PYTHONPATH=src python -m pytest tests/eval/...`. Capture acc@3/5/10, first-gold-rank, ctx_efficiency, turns, tokens. Run baseline: current FA at whatever tier/model is configured. Record numbers.
5. **S15c — Add BM25 ordering to fs_search (P0-2)**; re-run eval → delta. Expect +5–10pp acc@5 (small but measurable).
6. **S16 — Python structural call-graph index + `fs_reach` (P1-1/P1-2).** This is the big one; re-run eval; expect +15–30pp acc@5 on multi-file tasks, -20% turns.
7. **Re-evaluate P2 items based on measured residual gaps** after S16. Do not invest in embeddings / multi-language tree-sitter / CoSIL subagent / grounding-set compaction until we have traces showing the specific failure they would close.

Each step should be its own patch, gated by its own pytest suite + ruff/mypy/py_compile, applied to origin/main independently — consistent with the S14 delivery pattern.

---

## §5. Concrete ideas that look appealing but should be rejected on current evidence

To keep this exercise honest, here are ideas that sound good but are **not supported** by the papers or contradict FA's minimalism-first principle:

- **"Just add embeddings / vector search and everything will get better."** Directly contradicted by SE Table 6 (Potion dense ≈ BM25 ≈ Random) and CiM's ablation, which does not even show a standalone vector leg result (implying it's not the load-bearing component — the graph is).
- **"Surface a numeric relevance score on every search result."** CiM doesn't return scores to the agent; it returns ranked chunks with snippets. Scores invite LLM over-trust (we documented this risk in the fs_search note).
- **"Give the agent a giant 10K-file project map up front."** Both papers show that *ranking* under a budget is everything; dumping a file tree is noise. SE F5/F6: noise is cheap *after* core is present, but before core is present it's expensive (dips in resolve at α=25 in CiM Fig 5).
- **"More tool calls = better."** CiM SC-ON is better *and uses fewer turns*; turns are a cost, not a KPI to maximize. The right metric is first-gold rank (earlier = better).
- **"Stronger model will fix exploration."** SE Table 5: GPT-5.4 vs. GPT-5.4-mini vs. Kimi-K2.6 vs. Sonnet-4.5 vs. GLM-4.7 vs. Gemini-3-Pro — all show high HitFile / low Recℓ pattern; model tier changes the operating point modestly, but doesn't close the structural gap. Pillar-2 mixed-tier is validated (weaker models for exploration work fine once substrate supports them).
- **"Fancy RAG / GraphRAG on the codebase."** CiM's index is simple (BM25 + vector + call graph), not a knowledge graph with LLM-extracted entities/relations. GraphRAG-style approaches have no positive evidence in these papers and have build cost + non-determinism + maintenance burden that violates §1.2 compliance-by-construction.

---

## §6. Three immediate questions for the operator

1. **S14b scope creep.** The fs_search unification we locked earlier is P1-4 and does not include P0-1/P0-2/P0-3/P1-1/P1-2. Should I:
   - (a) keep S14b as planned (consolidation only, deterministic, no BM25, no graph) and sequence P0/P1 as separate S15a/b/c/S16 slices; *or*
   - (b) expand S14b to include P0-2 (BM25 on fs_search, ~10 LOC) since it's nearly free and improves quality; keep everything else as follow-ons.
   My recommendation: **(b)** for P0-2 only; defer the rest. Rationale: BM25 is a one-line `ORDER BY` in sqlite with zero API surface change; everything else adds tools/modules and needs its own test surface.

2. **Eval harness investment.** P0-1/S15a assumes we commit to a small in-repo eval harness (20 tasks, runnable via pytest) against which we measure acc@k / turns / tokens. Do you want this to be a new `tests/eval/` tree alongside unit tests, or a separate `eval/` top-level directory with its own runner? (I'd recommend `tests/eval/` so it can coexist with the existing pytest configuration and CI.)

3. **Python-only call graph vs. tree-sitter in v1.** P1-1 (structural index) can ship faster and stdlib-only if we scoped it to Python using `ast`. For First-Agent itself (our primary target repo today) that covers 100% of the code. Multi-language support would be deferred to P2-1. OK to start Python-only, or do you need Go/TS in the first cut? My recommendation: **Python-only in v1**, with a clean `LanguageHandler` interface so other languages can plug in later.

---

## §7. References

- SE: Zhang et al., *SWE-Explore: Benchmarking How Coding Agents Explore Repositories*, arXiv:2606.07297v1, Jun 2026. https://arxiv.org/abs/2606.07297
- CiM: *Code Isn't Memory: A Structural Codebase Index Inside a Coding Agent*, arXiv:2606.22417v1, Jun 2026. https://arxiv.org/abs/2606.22417
- Sen et al., *Is Grep All You Need? How Agent Harnesses Reshape Agentic Search*, arXiv:2605.15184, May 2026. (Cited inside CiM; already used as an input to our S14b design.)
- FA internal: `knowledge/project-overview.md` (Pillars 1–4, §1.2 minimalism-first, §1.2.5 compliance-by-construction, §1.2.6 Substrate Formality).
- FA internal: `knowledge/research/fs-search-unification-sota-2026-08-10.md` (prior S14b design note).
- FA internal: `knowledge/research/fs-search-relevance-score-bm25-embeddings-decision-2026-08-10.md` (prior BM25/embedding decision note — conclusions preserved here; this note extends it with SE/CiM evidence).
