# PLAN: S14b — Search tools unification + memory system expansion (post-S14 substrate)

**Plan-ID:** `PLAN-cli-trace-S14b-search-tools-memory-expansion`
**Status:** REVIEW-UPDATED v2.1 (2026-08-10). v2 = senior-review pass (R1-R17 closed). v2.1 = implementer pre-flight gap closure (11 items, see §1.1) on top of v2. Q-AST resolved=narrow; Q1–Q6 defaults recorded. Ready for implementation of S14b.1.
**Depth:** P2 (cross-module, migration of 3→1 tool, structural DB, telemetry extension; sliced into 5 independently-deployable sub-steps)
**Revision:** v2.1 (2026-08-10)
**Author:** agent
**Parent:** `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` (v12; post-S14)
**Prereq:** S14 (`s14-blackboard-artifact-index.patch`) must be live-merged before S14b is applied. S14 and S14b are separate patches; S14b applies **on top** of S14, never to S14's patch file itself.
**Closes / advances:**
- **I-57 (NEW, opened by this plan):** search surface is 3 overlapping grep-like tools; unify into one `fs_search`.
- **I-58 (NEW):** FTS index uses trigram substring but no BM25 ranking → poor ordering on multi-term queries.
- **I-59 (NEW):** `max_iterations=6` is silently reached; no operator-visible signal, no configurability beyond code constants.
- **I-60 (NEW):** telemetry records path reads but lacks first-read turn, line ranges, and surfaced-vs-arrived distinction; exploration metrics (acc@k / FUH / CtxEff) cannot be computed.
- **I-61 (NEW):** no structural call-graph index; multi-file navigation costs agent many iterations (SWE-Explore / CiM papers show this is the dominant bottleneck on ≥3 file tasks).
- **I-62 (NEW):** no stable `§<anchor>:` convention in Python code contracts; cross-ref from docs to code lines is brittle.

**Scope note (explicit).** This plan is a **multi-slice rollout plan**, not a single diff. It is structured so each slice S14b.1..S14b.5 is its own independently-verified patch with its own DoD, live-path proof, and gating. A later slice may be deferred (its own non-goal) without blocking earlier slices. Operator can stop shipping after any slice and remain on a shippable substrate.

**Slice sequence (committed order):**

| Slice | Title | LOC est | New deps | Shippable alone? |
|---|---|---|---|---|
| S14b.1 | Unified `fs_search` replaces `fs_grep` + `fs_instant_grep` + `fs_glob`, with FTS5 BM25 ranking | ~500 (3→1, net -ve) | 0 | yes |
| S14b.2 | Observable iteration-cap signal + per-profile iteration limits + YAML config | ~120 | 0 (PyYAML already in deps) | yes, on top of S14b.1 |
| S15   | Exploration telemetry v1: first-read turn, line ranges, surfaced-vs-arrived flag + metrics aggregator | ~200 | 0 | yes, on top of S14b.1 |
| S16   | Python call-graph index via stdlib `ast` + `fs_reach` tool | ~500 (incl. tests) | 0 | yes, after S14b.1 |
| S17   | `§<stable-id>:` code-anchor convention + indexing into S16 symbols table | ~80 (mostly docs + indexing) | 0 | yes, after S16 |

Slices S15 and S16 may be developed in parallel after S14b.1 lands (no shared code paths beyond common tool-registration wiring). S17 depends on S16.

P2 items explicitly **deferred, not in this plan**: embeddings / vector search, tree-sitter multi-language support, CoSIL-style graph-walk subagent, LSP/jedi integration, relevance_score numeric field (see §1.6).

---

## §1.1 v2.1 IMPLEMENTER PRE-FLIGHT GAP CLOSURE (2026-08-10)

Second-pass source-verification by implementer (against HEAD `103fb89 fix` + S14 applied in working tree) found 11 issues in v2 that would have caused test failures, bugs, or contradictions during coding. All closed in-place below; this block is the changelog + anchor for anyone reading diffs.

| # | Severity | Finding (v2 text vs actual code) | Resolution (applied in v2.1) |
|---|---|---|---|
| G-1 | **HIGH** | S1 said "add `fs_search`, `fs_reach`, `fs_exploration_metrics`" to TOOL_NAMES frozenset in S1. But `tests/test_s13_10_tool_names.py::_scrape_tool_spec_names()` greps `tools/*.py` for `name="(fs|pr)_..."` literals and asserts every scraped name is in TOOL_NAMES and vice versa. Adding names for tools whose modules don't yet exist breaks the composition test at S1 before S5/S15/S20 create the files. | S1 only replaces the three old names with `fs_search` in S14b.1. Names `fs_exploration_metrics` and `fs_reach` are added to TOOL_NAMES **in their own slice patches** (S15 and S20 respectively), immediately after their tool modules are created. Added explicit note to S1 and to the S15/S20 step cards. |
| G-2 | **HIGH** | S2/S3 described `iter_searchable_files` using only `os.walk` + EXCLUDE_DIRS prune. But `glob.py` and `grep.py` both call `git_ls_files()` from `tools/_common.py` as the **fast path** (respects `.gitignore` for untracked files, generated dirs like htmlcov/, *.egg-info, .mypy_cache that aren't in EXCLUDE_DIRS but are gitignored). Replacing git-ls with raw os.walk would index build artifacts, venvs (if user removed .venv from EXCLUDE_DIRS), .gitignored secrets, etc. — a regression from current behavior. | `iter_searchable_files` now tries `git_ls_files(root)` first; on any failure (subprocess error, not a git repo, timeout) falls back to the existing `os.walk` + EXCLUDE_DIRS prune (mirrors `glob.py` pattern exactly). This also means EXCLUDE_DIRS prune must ALSO run on git-ls output (defense in depth: git ls-files can return files inside EXCLUDE_DIRS if they were force-added). Added to S3 deterministic mechanism. |
| G-3 | **HIGH** | S14 said "Add `current_turn: int = 0` to SessionState, increment per batch". But `state.py:656` already does `self.turn += 1` **inside `record_tool_call()`** — that field is per-tool-call, not per-batch. Adding a second counter with a confusingly similar name double-counts and breaks any consumer reading `state.turn` today (which includes `record_tool_result` telemetry path at line 674). | The S15 turn counter for telemetry is the **existing** `state.turn` (already 1-based, already increments per tool_call). We do NOT add `current_turn`. We do add `batch_turn: int = 0` which increments once per `classify_batches` batch in `run_session` (in the for-batch loop, BEFORE dispatch). S14 "turn" field in the `file_read` event uses `state.batch_turn` (the iteration number) NOT `state.turn` (the per-tool-call counter). Clarified throughout §2.2 TO-BE and Step S14. |
| G-4 | MED | v2 §2.2 said "extend EXCLUDE_DIRS in fts_index.py to add `.tox, .pytest_cache, .ruff_cache, .nox, htmlcov, *.egg-info`". `*.egg-info` is a glob, not a directory name literal — a set-membership check against the basename won't match `fa.egg-info/` or `first_agent.egg-info/`. | EXCLUDE_DIRS extension adds the literal directory names `.tox, .pytest_cache, .ruff_cache, .nox, htmlcov` (basenames). `*.egg-info` and similar globs are NOT added to EXCLUDE_DIRS; they are handled by (a) `git ls-files` respecting `.gitignore` (which already ignores *.egg-info in standard FA .gitignore), AND (b) an `fnmatch.fnmatch(basename, pattern)` check in `iter_searchable_files` for a small `EXCLUDE_DIR_GLOBS = {"*.egg-info", "*.egg", "*.tox"}` set. Documented in S2 change list. |
| G-5 | MED | v2 AS-IS incorrectly stated "instant_grep returns fts_error when DB missing/empty". Source-verified: `instant_grep.py` opens `InstantGrepIndex(db_path)` which **always** creates the DB via `sqlite3.connect` + `CREATE VIRTUAL TABLE IF NOT EXISTS` (fts_index.py:42-55); only the `fts_meta` table might be empty. The "read-only" guarantee in v2 was overstated. | AS-IS corrected: instant_grep does create an empty DB file on first import but does NOT populate content (no auto-index). Correctly described as "FTS DB is created on construction; content is NOT indexed until `index_repo()` is explicitly called by the caller, which no current tool path does — so first live query falls through to the `fts_error`/fallback path". R-2 (lazy auto-index on first fs_search) resolution unchanged; description tightened. |
| G-6 | MED | v2 did not specify the "shared helper" location for `iter_searchable_files`. Putting it inside `search_index.py` makes `structural_index.py` (S16) import from a module that itself imports sqlite3 + has a heavy class — minor coupling issue but also creates a circular-import risk if structural_index wants to import the iterator before SearchIndex is fully initialized. | Create the iterator as its own small module `src/fa/memory/_safe_walk.py` (40-60 lines) with function `iter_searchable_files(root, patterns, exclude_dirs, extra_exclude_dirs, include_tests, max_file_size) -> Iterator[tuple[Path, str, float, int]]`. Both `search_index.py` and `structural_index.py` import from there. S2/S3 updated. |
| G-7 | MED | v2 said `SearchIndex` and `InstantGrepIndex` are "separate DB connections" and "SearchIndex creates a NEW table `files_fts_bm25`". But `fts_index.py:44` creates a virtual table named `files_fts` using `tokenize='trigram'`; adding `files_fts_bm25` to the SAME database file means both classes connect to the same `.fa/fts.db`. That is the INTENT (single `.fa/fts.db`), but plan text was ambiguous about whether the trigram table is rebuilt (and would thus invalidate any in-process `InstantGrepIndex` instances). | Made explicit: `SearchIndex` opens the SAME `db_path` (`workspace_root / ".fa" / "fts.db"` by default, same feature flag `fts_db_path`). On first `ensure_indexed()` it runs a schema migration: if `PRAGMA table_info(files_fts_bm25)` returns zero rows, it creates BM25 table AND drops+recreates the trigram `files_fts` table (because the old `files_fts` had porter-fallback content-inserted-as-raw; SearchIndex wants to control normalization itself). After migration, `InstantGrepIndex.instant_grep()` still works against the rebuilt trigram table (same schema, just re-populated). A `schema_version` row in `search_meta` tracks this. Added migration detail to S2. |
| G-8 | MED | v2 did not address that `state.py` has no `_search_result_paths` container initialized in `__post_init__`; fs_search.py needs a place to write this set, and read_file.py needs to read it. In SessionState's current shape, all ad-hoc fields are declared at class level (see lines ~400-450). | Step S14 adds THREE class-level fields to SessionState: `last_search_results: set[str] = field(default_factory=set)`, `last_search_turn: int = -1` (the `batch_turn` at which fs_search last ran), `_gold_files: set[str] = field(default_factory=set)`. `last_search_results` is CLEARED at the start of each batch (loop.py, in the same place `batch_turn` increments) — this prevents stale cross-turn attribution. read_file.py attributes `surfaced_by="search_result"` only when `state.batch_turn == state.last_search_turn AND rel in state.last_search_results`. Fixes "surfaced_by stays true forever after one search" bug. |
| G-9 | LOW | v2 Step S5 said `_add_optional_tool_builders` is the registration point but `_build_tool_builders` in `profiles.py:138-269` is the ACTUAL builders dict (profiles.py:143 has the try/except for glob/grep/instant_grep). `tools/__init__.py` has its OWN try/except imports and `_register_extra_tools()` function that also registers instant_grep conditionally. Two registration sites must be updated or old-tool imports will throw ImportError when files are deleted. | S5 edit list now names BOTH sites explicitly: (1) `profiles.py:_build_tool_builders` lines 225-269 (remove glob/grep/instant_grep try blocks, add fs_search try block), AND (2) `tools/__init__.py` lines 24-76 (remove `build_glob_tool`/`build_grep_tool`/`build_instant_grep_tool` imports and `include_instant_grep`/`include_glob_grep` parameter branches from `_register_extra_tools`, add fs_search registration). The fs_search builder is ALWAYS registered (no conditional flag) because it replaces all three. |
| G-10 | LOW | v2 listed EXCLUDE_DIRS extension as adding directories to `fts_index.py`, but after S14b.1 ships, `fts_index.py` has `InstantGrepIndex` (deprecated shim) while `_safe_walk.py` is the module that actually owns the file-iteration filter. Single-source-of-truth for EXCLUDE_DIRS needs to be unambiguous. | EXCLUDE_DIRS stays defined in `memory/fts_index.py` (back-compat, any lingering external importers). `_safe_walk.py` does `from fa.memory.fts_index import EXCLUDE_DIRS as _BASE_EXCLUDE_DIRS` and defines `EXTRA_EXCLUDE_DIRS = frozenset({".tox", ".pytest_cache", ".ruff_cache", ".nox", "htmlcov"})` and `EXCLUDE_DIR_GLOBS = frozenset({"*.egg-info"})`. Effective exclude = `_BASE_EXCLUDE_DIRS | EXTRA_EXCLUDE_DIRS | user_extra | ({"tests"} if not include_tests else set())`. No drift. |
| G-11 | LOW | v2 said `include_tests=False` for fs_reach default, but fs_search default is `include_tests=True`. Plan text in S20 matches this, but §2.2 default-flag table omitted fs_search's `include_tests` default (making it look inconsistent). | Added row to §2.2 default flag table and a one-line note in CT-1 `include_tests` param: "fs_search defaults to `include_tests=True` (discovery often needs test files); fs_reach defaults to `include_tests=False` (navigation over production call graph is the common case; test edges are noise unless requested)." |

**Net effect of v2.1:** no change to scope, goals, contracts, or slice ordering. 3 HIGH-severity test/runtime failures prevented (G-1: test_map_covers_all fails; G-2: indexes gitignored junk; G-3: double turn counter / semantics clash). 4 MEDIUM correctness issues fixed (G-4..G-7). 4 LOW documentation/coupling issues fixed (G-8..G-11).

---

## PREFLIGHT LOG (§2 of plan-authoring skill — MANDATORY)

**Roots checked:**
- Tool builder / registration: `src/fa/inner_loop/profiles.py` (lines 41, 60, 71-73, 83, 230-257 verified) — `fs_glob`, `fs_grep`, `fs_instant_grep` are listed in four role profiles AND wired via separate builders in `build_registry_for_role`.
- Lazy import / fallback registration: `src/fa/inner_loop/tools/__init__.py` (lines 24-76, 92-176, 203-268 verified) — all three tools have try/except import, failure-observable WARNING, and `include_instant_grep` / `include_glob_grep` flags.
- Existing FTS index: `src/fa/memory/fts_index.py` (204 lines verified) — `InstantGrepIndex` uses SQLite FTS5 `tokenize='trigram'` with porter fallback; has `fts_meta` for mtime/size; index stored at `.fa/fts.db` (default) or feature-flag path.
- Loop driver: `src/fa/inner_loop/loop.py` (613 lines verified) — `run_session` iterates batches, compares `len(results) >= effective_limits.max_iterations: break` at line 548; `StopInfo` already exists and is returned to caller; currently only AFTER_TOOL_EXEC denial and BETWEEN_ROUNDS denial surface there (iteration-cap break is silent — no StopInfo emitted).
- Runtime limits: `src/fa/inner_loop/runtime_limits.py` (404 lines verified) — `RuntimeLimits` dataclass at line 95; `DEFAULT_MAX_ITERATIONS=6` at line 37; loads from `~/.fa/config.yaml`? Currently loads from session context / env (verified lines 127-347: key-lookup from `found` dict, source is session `.fa/config` not yet validated for operator-global).
- Telemetry / read tracking: `src/fa/inner_loop/state.py` (772 lines) — `SessionState.add_read(path)` at line 545 calls `transaction.add_read(path)` only; no turn number, no line range. `record_tool_call`/`record_tool_result` at lines 650/674 write to `EventLog` with no read-line metadata.
- Existing AST consumer: `src/fa/authoring_rules/_scan.py` (77 lines verified) — `iter_python_files` yields `(rel, source_bytes, tree)` for authoring rules; imports stdlib `ast`, uses `ast.parse`; pattern reused for S16 (no new parser dep).
- Canonical tool names: `src/fa/inner_loop/tool_names.py` (63 lines verified) — `TOOL_NAMES` frozenset contains `fs_glob`, `fs_grep`, `fs_instant_grep`; membership enforced by `test_s13_10_tool_names.py`.
- Observability tools: `src/fa/inner_loop/tools/observability.py` (existing) — `fs_chronicle_search` and `fs_usage` already use EventLog as substrate; S15 metrics extend the same log.
- Existing `§`-marker convention: `grep -rn '§[A-Z]' knowledge/ AGENTS.md src/fa/` confirms markers are used pervasively in docs (ADR glossary at ADR-11, BACKLOG, HANDOFF, skills) with the syntax `§<stable-id>`. `ADR-11 §Glossary` defines `I-FROZEN: source=<path#anchor> checker=<path-or-rule-code>` as the existing marker syntax. No `§` markers exist in Python source today (verified: `grep -rn '# §' src/fa/` returns 0 hits).

**Greps run → findings:**
- `fs_grep|fs_instant_grep|fs_glob` across `src/` → hits in: `profiles.py`, `tools/__init__.py`, `loop.py` (_PARALLEL_SAFE_TOOLS), `subagent_prompts.py`, `subagent_runner.py`, `tool_names.py`. **Critical:** the subagent prompt at `subagent_prompts.py:19` and `:150-151` names `fs_instant_grep` directly in prompt text — must update as part of S14b.1 or subagent will call a removed tool.
- `bm25(` in `src/` → zero hits (NEW for S14b.1 P0-2).
- `DEFAULT_MAX_ITERATIONS` → only at `runtime_limits.py:37`; single point of truth.
- `iteration_limit|max_iterations` in any CLI/config loader → `runtime_limits.py` has a loader from per-session config but no operator-global `~/.fa/config.yaml` loader for this key.
- `ast.parse|ast.walk` in production code → `authoring_rules/_scan.py` + a few authoring rule modules (the tree is discarded after rules run; not stored). No structural DB exists.
- `sqlite3.connect` → only `memory/fts_index.py`; we will add a second DB at `.fa/structural.db` (co-located with `fts.db` — trivial directory convention already exists).
- `add_read(` → call sites in `state.py:548` (transaction.add_read) and `state.py:658` (read_file path). The only caller passing line-range? None.
- `surfac|first_read|fuh|ctx_eff|acc@k|acc_at_k` → zero hits (NEW for S15).
- `call.?graph|callee|caller` → a few doc references; zero code (NEW for S16).
- `tests/test_instant_grep.py` exists (2 tests, trigram + limit). No tests for `fs_grep` or `fs_glob` as ToolSpecs (only implicit via higher-level tests) — gap we close with S14b.1 test suite.

**Gold patterns mirrored:**
- `src/fa/blackboard/artifact_index.py` (S14) for: lazy-on-first-call indexing, fail-degraded BLE001 catch, deterministic hash ids, idempotency, `file_version` type isolation. S14b.1's lazy FTS-BM25 index and S16's call-graph index reuse these patterns.
- `tests/test_blackboard_artifact_index.py` for test style: fresh tempdir + tiny fake repo, assert on `result.status`, kill-check via direct `artifact_index.ensure_artifacts_indexed` bypassing ToolSpec.
- `src/fa/memory/fts_index.py` for SQLite connection lifecycle, mtime-based skip, EXCLUDE_DIRS constant reuse.

**Conflicts / invariants found:**
1. **I-S14b-1 Tool-name stability.** S13.10 (`tool_names.py`) enforces canonical wire names. Removing three names and adding `fs_search` requires coordinated edits to: `tool_names.py`, `profiles.py` (4 role tool lists + builders block), `tools/__init__.py` (registration block), `loop.py` (_PARALLEL_SAFE_TOOLS), `subagent_prompts.py` (prompt text mentions `fs_instant_grep`), `subagent_runner.py` (comment references instant_grep), and `AGENTS.md` / `knowledge/llms.txt` (S14 already started intent-matrix table). Failure to update any one of these → runtime KeyError (unknown tool) or dead code.
2. **I-S14b-2 FTS5 tokenizer compatibility.** Current `tokenize='trigram'` is fine for substring but BM25 ranking on trigram tokens behaves poorly for multi-word queries (it scores on 3-char shingles, not words). Hybrid approach required: create a second FTS5 virtual table with `tokenize='unicode61 remove_diacritics 2'` for BM25 ranking; keep trigram table for `LIKE '%q%'` substring fallback; combine with UNION or prefer BM25 with trigram fallback. Verified sqlite3 supports both tokenizers in same DB.
3. **I-S14b-3 Fail-degraded auto-index guarantee.** *(v2.1 G-5 corrected)* Current `instant_grep.py` creates an empty FTS DB on construction but never populates content; the first live query hits an empty index and falls back. `fa reindex` is currently a stub comment in `cli.py:391`. S14b.1 decision: lazy auto-index on first `fs_search` call, with a per-process flag to avoid re-indexing more than once per session, mirroring S14's `_indexed_for_session` guard. CLI `fa reindex` is a non-goal for S14b.1; added later if we need offline indexing.
4. **I-S14b-4 Symlink escape.** `grep.py:_iter_files_for_grep` and `glob.py:_iter_files_fallback` both resolve symlinks and skip outside-root paths. S14b.1's file iterator must preserve this invariant (otherwise a malicious repo could escape via a symlink to `/etc/passwd` and have that file's contents indexed).
5. **I-S14b-5 Event schema compatibility.** S15 extends EventLog event payloads. EventLog is JSON in SQLite (session_db.py) — schema-flexible — but `fs_chronicle_search` substring-matches content; we must not break existing queries. Adding new keys is safe; renaming/removing existing keys is not.
6. **I-S14b-6 Structural DB for Python only, on .py files.** S16 MUST NOT attempt non-Python parsing; for non-Python repos `fs_reach` returns a structured `{"status":"unavailable","reason":"only Python supported in v1","detected_languages":[…]}` instead of raising. This keeps the substrate honest and supports the "other projects are not FA-shaped" scenario operator highlighted.

**As-is liveness (per §4 liveness scale):**
- 3-tool search surface: L3 (shipped, used in live runs, has tests) but mis-shapen (overlapping, no ranking).
- BM25 ranking: L0 (not present).
- FTS substring index: L2 (code present; builder lazy-reads DB and falls back; `fa reindex` CLI not present so first query always hits fallback walk).
- Iteration-cap signal: L1 (constant exists; silent break at loop.py:548; no operator-visible signal).
- Exploration telemetry (turn/line/surfaced): L0.
- Exploration metrics (acc@k/FUH/CtxEff): L0.
- Python call-graph index: L0.
- `fs_reach`: L0.
- `§` markers in Python code: L0 (only in docs).

**Unresolved → promoted to Q# (see §10):**
- **Q-AST (BLOCKING):** In S16, do we want to index **only** function/method definitions and direct calls, OR also class definitions, dataclass fields, and decorator references? Recommendation: start narrow (functions/methods + their direct calls); classes/imports are follow-on if metrics show need. **Defaults marked; operator approval needed on this one before S16 implementation starts.**
- Non-blocking Qs Q1-Q4 carry stated defaults so executor proceeds unless operator overrides.

---

## 0. Executive intent (§3)

**IDEA:** Unify First-Agent's discovery surface into one well-ranked search tool (`fs_search`), then layer measurable telemetry, multi-file navigation (Python call-graph + `fs_reach`), and stable code anchors on top — each slice independently shippable, all on stdlib, zero new dependencies, and **no** embeddings/ML/vector-DB until metrics prove they pay for themselves.

**Project meaning:** This lives in `src/fa/inner_loop/tools/` (search), `src/fa/memory/` (indexes), `src/fa/inner_loop/state.py` and `event_log` (telemetry), and `src/fa/` (new structural index module). It belongs here because: (a) discovery is the #1 consumer of iteration budget (per SWE-Explore, line-level recall Recℓ≈0.14–0.19 is the bottleneck); (b) the existing 3 overlapping tools already exist in this package; (c) telemetry lives on SessionState; (d) call-graph index is a peer of FTS (memory layer), not a tool.

**Goals (G1..G6):**
- **G1 (S14b.1):** One discovery tool `fs_search` replaces `fs_grep`, `fs_instant_grep`, `fs_glob`; supports 4 output modes (`files`/`matches`/`regions`/`counts`); ranks results via SQLite FTS5 BM25; auto-indexes on first call with mtime-based incrementality; safe symlink containment; respects `.gitignore` via `git ls-files`.
- **G2 (S14b.2):** When the iteration cap is hit, the operator and the model both see a structured signal (StopInfo reason `iteration_cap_reached`, log event of kind `run_stopped`, user-visible message via existing renderer path); per-profile iteration defaults are raised appropriately (verifier=5, researcher=15, code-reviewer=15, planner=20, implementer=40); operator can override any of these via `~/.fa/config.yaml`.
- **G3 (S15):** Existing `add_read` is extended to record first-read turn number, line range (start_line/end_line for range reads), and `surfaced_by` (`search_result`/`direct_reference`/`artifact_index`/`breadcrumbs`); an aggregator (new tool `fs_exploration_metrics`) returns acc@k, FUH, and CtxEff for the current session.
- **G4 (S16):** A stdlib-`ast` Python call-graph index is built lazily at `.fa/structural.db` (tables `symbols`, `calls`, incremental by `file_hash`); new tool `fs_reach(symbol, direction, depth, limit, kind, include_tests)` returns resolved symbol + ranked callers/callees list with path/line/distance; auto-deactivates on non-Python repos with a structured "unavailable" result.
- **G5 (S17):** A documented `# §<stable-id>: <description>` convention is adopted for contract/invariant points in Python code (≤1 anchor per ~200 lines, not every function); these anchors are indexed into the S16 `symbols` table (kind=`doc_anchor`) so they participate in `fs_search` and `fs_reach`.
- **G6 (cross-cutting):** All slices remain fail-degraded (BLE001 catch + WARNING log + structured error result); none add network calls, new dependencies, or long-running startup work; indexes live under `.fa/` (per-session) and are wiped when session ends.

**Non-goals (explicit; scope firewall §5):**
- **NO** vector embeddings / semantic search (papers show no standalone benefit without graph; FOMO risk explicitly acknowledged and rejected).
- **NO** tree-sitter / multi-language parser for S16 (Python-only via stdlib `ast`; `LanguageHandler` interface rejected as YAGNI per §5).
- **NO** LSP / jedi integration (deferred until AST resolver proven insufficient via S15 metrics).
- **NO** CoSIL-style iterative graph-walk subagent (research-grade, not production-ready).
- **NO** numeric `relevance_score` field in `fs_search` output (over-trust risk; ranking happens in the engine, not surfaced).
- **NO** `fs_grep`/`fs_instant_grep`/`fs_glob` compatibility shim (operator confirmed "fs_search is the single discovery tool going forward"; we rename all internal call sites and prompt text in one atomic patch).
- **NO** bash grep ban (P0-3 per operator: deferred to backlog, not in this plan).
- **NO** change to blackboard conflict-detection semantics (S14b writes nothing to blackboard types that conflict with `file_version`).
- **NO** touching S13.x or pre-existing baseline test failures (providers_chain, pyrefly, s10a/s10b/s12/s5_state_root); S14b patches must not regress those baselines but also are not obligated to fix them.
- **NO** startup-time indexing for any index (FTS, structural, telemetry); all lazy.
- **NO** `fa reindex` CLI verb in S14b.1 (lazy auto-index is sufficient); can be added later as a UX improvement.

**INTENT (the "why" behind mechanisms):** Code should ensure the agent finds the right file/line **faster**, with **fewer tool calls**, and on multi-file tasks can follow call relationships without guessing — so that the current budget of 6 iterations (going to sensible per-profile defaults) is enough for real work instead of being wasted on repetitive grep+read loops. Measurement (S15) comes before any further investment in vector/ML/extra-language support.

**MECHANISM SKETCH (one paragraph):** `fs_search` is a single tool that on first call walks the workspace (respecting `.gitignore`/`EXCLUDE_DIRS`/symlink safety), indexes content into a SQLite FTS5 database at `.fa/fts.db` with two virtual tables (trigram for substring fallback, unicode61+bm25 for ranking) plus a mtime/size metadata table (reusing the existing `fts_index.py` patterns, extended), then serves queries by running BM25-ordered FTS with substring fallback and grouping results into `files`/`matches`/`regions`/`counts` shapes depending on `output_mode`. When the loop hits the iteration cap it emits a structured `StopInfo` and `run_stopped` event, surfaced through existing renderers. `add_read` gains line/turn/source metadata that S15's metrics aggregator reads back to compute acc@k / FUH / CtxEff. S16's `fs_reach` walks a lazily-built `structural.db` populated from stdlib `ast` walks of `.py` files, returning call-graph neighbourhoods for a queried symbol. S17 adds `§<id>:` anchors that the structural indexer picks up as `doc_anchor` symbols.

**PROOF SKETCH (top-level; per-slice details in §6 + §9):**
- G1 kill-check: delete the `bm25(...) ORDER BY` clause from the search SQL → `test_fs_search_bm25_ranking` fails because query results are no longer in expected relevance order.
- G2 kill-check: remove the StopInfo emission at the iteration-cap break in `loop.py` → `test_iteration_cap_signal` fails (result.stop is None).
- G3 kill-check: comment out the `first_read_turn` column write in `add_read` → `test_first_read_turn_recorded` fails.
- G4 kill-check: drop the `calls` table from structural schema → `test_fs_reach_finds_direct_caller` fails.
- G5 kill-check: remove the `§`-anchor regex extraction in the structural indexer → `test_doc_anchor_indexed_as_symbol` fails.

**SIZE:** M (medium); slices S/M/S/M/M/S, total ~1400 new/changed lines across all slices, zero new deps.

---

## 1. Non-goals & minimal-mechanism check (§5)

For each major design choice, state the minimal smaller alternative and why it is/isn't sufficient.

| Mechanism | Could a smaller change satisfy intent? | Verdict |
|---|---|---|
| Single `fs_search` tool replacing 3 tools | Could keep 3 tools and just add BM25 to `fs_instant_grep`, teach the agent via AGENTS.md to prefer instant_grep first. Rejected: (a) cognitive load on model (3 tools to choose between, known failure mode); (b) duplicated code (exclude-dir logic, symlink checks, glob filtering all duplicated across 3 files today — 640 lines → can be ~350 with shared helpers); (c) operator already ratified "fs_search is the single discovery tool". | Accept unified tool. |
| FTS5 BM25 as secondary table | Could change `tokenize='trigram'` to `tokenize='porter'` and use bm25() on that. Rejected: loses substring search (trigram is what makes instant_grep find "Authentication" from "auth"). Two-table hybrid is smallest design that preserves both capabilities. | Accept two-table hybrid. |
| Per-profile iteration limits | Could just raise default from 6 to 20 globally. Rejected: for verifier profile a cap of 20 masks infinite loops; for researcher 6 is too tight. Per-profile is smaller than a full dynamic-budget system and matches SWE-Explore finding that researcher/navigator phases need more iterations than implementer. | Accept per-profile. |
| `~/.fa/config.yaml` override | Could hardcode per-profile limits with no override. Rejected: operator needs to be able to tighten/loosen without code edits; YAML loader already exists in deps (PyYAML is a current dep). | Accept YAML config. |
| Exploration telemetry extension | Could skip telemetry and go straight to call graph. Rejected: CiM and SWE-Explore both emphasize measurement-before-investment; without telemetry we cannot tell whether the call graph actually helped, and we cannot compute the high-correlation metrics (CtxEff r=0.95). Telemetry is 200 lines of additive code on top of existing EventLog. | Accept S15 before S16. |
| Python-only `ast` call graph, no `LanguageHandler` interface | Could add an abstract `LanguageHandler` base class now and implement Python. Rejected (over-engineering, YAGNI): interface adds ~80 lines of dispatch/registration/plugin code with zero consumers besides Python. When/if JS/TS is needed we can extract the interface in a 1-hour refactor with no schema changes (DB already keyed on language column). | Accept Python-only, no interface. |
| `fs_reach` returns callers/callees only | Could return fully transitive reachable set up to depth=N. Rejected: token explosion and diminishing returns; depth=3 default and ranked by proximity matches CiM's empirical finding that most navigation is within 2 hops. Agent can issue multiple `fs_reach` calls to walk further. | Accept bounded-depth ranked results. |
| `§`-anchor convention in code | Could use docstrings and `grep` for cross-ref. Rejected: docstrings describe function behavior, not stable contract invariants; cross-ref by line number breaks as code moves. `§I-xx.y` anchors are the same stable-id system already used in docs, so doc→code and code→code references share a namespace. | Accept `§<id>:` convention. |
| Embeddings/vector DB | Could add sqlite-vec or Chroma for semantic search. Rejected per §0 non-goals: CiM ablation shows vector leg alone gives no significant lift without graph; vector index adds dependency, model download/cold-start, non-determinism; defer until S15 metrics show lexical+graph systematically failing on synonym/semantic matches in FA's own workloads. | Reject/defer. |
| Auto-fallback to substring on BM25 zero-results | Could return zero results when BM25 finds nothing (like current FTS on trigram sometimes does for typos). Rejected: substring fallback is what lets "auth" find "Authentication" and saves the agent a turn; current instant_grep already does this via `LIKE '%q%'` fallback and we must preserve that behavior. | Accept substring auto-fallback. |

**New component gate (per plan-authoring §5):** each new component below must pass the "why existing code cannot replace it" check:
- `fs_search` — replaces three existing tools; net lines decrease; passes.
- `.fa/fts.db` (new BM25 table) — existing FTS DB is the same file, we add one virtual table; passes.
- `~/.fa/config.yaml` loader — existing runtime_limits loader reads per-session config; we extend to check `~/.fa/` for operator-global overrides; additive, passes.
- `fs_exploration_metrics` tool — new but only reads existing EventLog (no new state); passes.
- `.fa/structural.db` — new DB file; new because it stores different data (symbols/calls) with different update cadence (per-file-hash vs per-mtime); co-located with FTS; passes.
- `fs_reach` tool — new surface but only reads structural DB; cannot be done via fs_search alone (fs_search finds text occurrences, not call relationships); passes.

None of these require LLM calls, network access, or non-stdlib deps.

---

## 2. Current state → Target state (liveness-scored, §4)

### 2.1 AS-IS (source-verified on `103fb89 fix` + S14 patch applied)

**Search surface (S14b.1):**
- Three tools exist:
  - `fs_grep` (grep.py:211 lines) — line-oriented, fast path `git grep -n`, fallback streaming Python walk, returns `matches: [{path, line, content}]`.
  - `fs_instant_grep` (instant_grep.py:232 lines) — path-only FTS5 trigram index, read-only query (no auto-index), returns `paths: [str]`.
  - `fs_glob` (glob.py:200 lines) — glob pattern matcher, returns `paths: [str]`.
- All three share: EXCLUDE_DIRS from `fts_index.py`, symlink containment, `git ls-files` fast path, BLE001 fail-degraded, limit/max_file_size params. Three copies of similar logic = drift surface.
- FTS index (`InstantGrepIndex`): one virtual table `files_fts(path, content) tokenize='trigram'`, meta table `fts_meta(path PRIMARY KEY, mtime, size)`; query uses `ORDER BY rank` (trigram rank is not BM25, it's a trigram-similarity score that favors dense 3-char hits over real relevance).
- No CLI `fa reindex`. *(v2.1 G-5 corrected):* `instant_grep.py` always opens `InstantGrepIndex(db_path)` which executes `sqlite3.connect` + `CREATE VIRTUAL TABLE IF NOT EXISTS files_fts ...` (fts_index.py:38-55), so an empty DB file is created on construction — but no file CONTENT is indexed until `index_repo()` is explicitly called (which no existing tool path does). The result is that the first live query always sees an empty index and falls through to the fts-error/`git ls-files` fallback path, giving the *appearance* of read-only behavior while in fact creating a zero-byte-or-empty DB file.
- Subagent prompt (`subagent_prompts.py:150-151`) hard-codes instant_grep in its fallback chain.
- Tool registry wiring is in two places: `profiles.py` (builders dict) and `tools/__init__.py` (extra-tools registration).

**Iteration cap (S14b.2):**
- `RuntimeLimits.max_iterations = 6` (single default).
- Loop checks `len(results) >= max_iterations: break` (loop.py:548-550) — silent; no StopInfo, no log event, no user-visible message.
- Loader for RuntimeLimits reads per-session config only (`~/.fa/config.yaml` is not consulted for loop limits today — grep confirms loader reads session-local state).
- Profile tool lists do not influence iteration count.

**Telemetry (S15):**
- `EventLog` (state.py:155) records `tool_call`, `tool_result`, `hook_decision`, `run_stopped` events with JSON `content`.
- `SessionState.add_read(path)` calls `transaction.add_read(path)` only; no turn/line/source metadata.
- `fs_chronicle_search` (observability.py) does substring scan over log; `fs_usage` aggregates tokens/cost/calls.
- No metric computes acc@k / FUH / CtxEff; no concept of "gold file" or "surfaced set" exists.

**Structural index (S16):**
- No DB, no tables, no tool.
- `ast.parse` is already used in authoring rules (`authoring_rules/_scan.py`) proving stdlib availability.
- No call graph, no symbol table.

**Code anchors (S17):**
- `§<id>:` markers exist in markdown docs (AGENTS.md, BACKLOG, ADRs, plans, HANDOFF, skills) — verified via grep.
- No such markers in `.py` files; no indexer for them.

### 2.2 TO-BE (machine-checkable facts)

**S14b.1 Search:**
- New module `src/fa/memory/search_index.py` exposing `SearchIndex` (keeps `fts_index.py` with its `InstantGrepIndex` class intact for one release cycle as a thin re-export/deprecation shim — see R-8 below; new code imports from `search_index.py`):
  - Virtual table `files_fts_bm25(path UNINDEXED, content) tokenize='unicode61 remove_diacritics 2'` using FTS5 built-in `bm25()` rank.
  - Existing trigram table `files_fts` preserved for substring fallback (we re-create+populate it via SearchIndex on first build; see migration below).
  - **R-1 tokenizer normalization (critical fix):** raw file content is transformed before being inserted into the BM25 FTS column so that snake_case and CamelCase identifiers are found by their subtokens. A deterministic function `_bm25_tokenize(text: str) -> str` is applied to content at index time:
    1. Replace `_` with space (so `build_instant_grep_tool` becomes `build instant grep tool`).
    2. Insert space at CamelCase/PascalCase boundaries via regex `re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)` and `re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)` (so `AuthMiddleware` → `Auth Middleware`, `HTTPClient` → `HTTP Client`).
    3. Truncate to 100 KB per file (matches current `fts_index.py` behavior, avoids oversized FTS rows).
    The trigram table continues to receive **raw, un-normalized** content so substring lookups (e.g. partial identifier fragments inside names) are not affected.
  - **Migration:** on first open, SearchIndex checks `search_meta` for `schema_version=1`. If BM25 table is missing, it is created AND the trigram table is dropped+re-created (simple path; DB is per-session, rebuild cost ~30-80ms on FA repo — same as S14's artifact index build). A `schema_version` row is written.
  - `ensure_indexed(root, *, patterns=DEFAULT_PATTERNS, max_file_size=200_000) -> SearchIndexStats` (lazy, idempotent, per-instance flag `_indexed_for_session: bool`; pattern mirrors S14 `ArtifactIndexer._indexed_for_session`). mtime/size-compare per file via `fts_meta` skips unchanged files on second+call.
  - `search(query, output_mode, glob, path, include_tests, exclude_dirs, max_file_size, context_lines, limit, order, regex, case_sensitive) -> SearchResult` (see CT-1 for result schema).
  - EXCLUDE_DIRS **imported from `memory.fts_index`** (single source of truth — extend `EXCLUDE_DIRS` in `fts_index.py` to add `.tox`, `.pytest_cache`, `.ruff_cache`, `.nox`, `htmlcov`, `*.egg-info`; these are per the workspace snapshot-exclusion list already used elsewhere).
  - Symlink escape check preserved (strict `fp.resolve().is_relative_to(root_resolved)` in the shared iterator; matches existing grep.py/glob.py pattern).
  - Glob matching factored into a shared `_matches_rel(rel, pattern)` helper that absorbs the `Path.match`/`fnmatch`/`**/`-strip logic currently duplicated in `glob.py`.
- New tool `src/fa/inner_loop/tools/fs_search.py` exposing `build_fs_search_tool(db_path, workspace_root) -> ToolSpec`, name=`fs_search`, input_schema has the full parameter set from the operator-confirmed spec (see §3 contracts).
- Deleted: `src/fa/inner_loop/tools/grep.py`, `src/fa/inner_loop/tools/instant_grep.py`, `src/fa/inner_loop/tools/glob.py`.
- Updated registrations:
  - `src/fa/inner_loop/tool_names.py`: replace three names with `fs_search`.
  - `src/fa/inner_loop/profiles.py`: all four role tool lists replace three entries with `fs_search`; builders dict removes three entries, adds one `fs_search` entry.
  - `src/fa/inner_loop/tools/__init__.py`: remove `build_glob_tool`/`build_grep_tool`/`build_instant_grep_tool` imports and registration calls; add `build_fs_search_tool`.
  - `src/fa/inner_loop/loop.py`: `_PARALLEL_SAFE_TOOLS` replaces three entries with `fs_search` (read-only, parallel-safe).
  - `src/fa/inner_loop/subagent_prompts.py` and `src/fa/inner_loop/subagent_runner.py`: replace references to `fs_instant_grep`/`fs_grep`/`fs_glob` with `fs_search` (use `output_mode="files"` for what used to be instant_grep; the prompt explains the modes).
  - `AGENTS.md` intent-matrix table (S14 added the matrix) is updated: single row for `fs_search` with mode-selection guidance; removes rows for old tools.
  - `knowledge/llms.txt`: same update.
- Default parameters aligned with Claude Code convention (per SWE-Explore/CiM observation that Claude Code defaults to path-only results):
  - `output_mode="files"` (default, cheapest, token-efficient)
  - `context_lines=1`, hard cap 5
  - `limit=20`, hard cap 50
  - `order="bm25"` (P0-2)
- Auto-indexing on first query (lazy), mtime-based incrementality (same mechanism as current `fts_index.index_repo`), per-process guard so re-index does not repeat within a session.
- Result shape is always `{query, method, returned, truncated, total_bytes, files?|matches?|regions?|counts?}` (see §3 CT-1 for full schema).
- Liveness target for G1: L3.

**S14b.2 Iteration cap (§3 CT-2):**
- New `StopInfo(point="iteration_cap", reason="max_iterations reached: used N of M", profile=role, limit=M)` emitted at loop.py:548 (replace silent `break`).
- Log event `kind="run_stopped"` with `content={"point":"iteration_cap","used":N,"limit":M,"profile":role}` is appended (producer: loop.py; consumer: existing StopInfo renderer path plus `fs_chronicle_search` which will already surface it via kind match).
- Per-profile `max_iterations` defaults added to `RoleProfile` (or to a separate `PROFILE_LIMITS` dict near PROFILES_RAW) with values:
  - verifier=5
  - researcher=15
  - code-reviewer=15
  - planner=20
  - implementer=40
- `RuntimeLimits.anchored_defaults()` is modified to accept an optional `role` argument; `build_registry_for_role` passes role through to the loop when available; a default-role fallback keeps backward compatibility (role=None → DEFAULT_MAX_ITERATIONS=6 for callers that don't specify — used by tests and eval).
- `~/.fa/config.yaml` is loaded (if present) and overrides per-profile defaults; schema:
  ```yaml
  iteration_limits:
    default: 10
    implementer: 40
    planner: 20
    researcher: 15
    code-reviewer: 15
    verifier: 5
  ```
  Loader is tolerant (missing file = defaults; malformed entries = WARNING + fall back to defaults; never crashes).
- Liveness target for G2: L3.

**S15 Telemetry (§3 CT-3, CT-4):**
- `EventLog` records a new event kind `file_read` (not just `tool_result`), produced in `fs_read_file` handler and in `add_read` (augmented) with fields:
  - `path` (string, rel)
  - `turn` (integer, 1-based; index of the current tool batch)
  - `start_line` / `end_line` (integers, null for whole-file reads)
  - `surfaced_by` (enum: `search_result` | `direct_reference` | `artifact_index` | `breadcrumbs` | `unknown`)
  - `bytes_read` (integer)
- Producer: `read_file.py` handler sets `start_line/end_line` from params; the loop sets `turn` via an incrementing counter on SessionState; `surfaced_by` is inferred from the *immediately preceding* `fs_search` result (if path was in that result's `files[]|matches[]|regions[]` → `search_result`; if preceding tool was `fs_blackboard_query` and path was in result → `artifact_index`; else `direct_reference`).
- Existing `record_tool_call/record_tool_result` are unchanged (schema-additive only).
- New tool `fs_exploration_metrics(reset: bool = false) -> {acc_at_k: {k:float, ...}, first_useful_hit_turn: int|null, ctx_efficiency: float, n_reads: int, n_search_results_clicked: int, gold_files: [str]|null}`. For this slice "gold file" is optional — operator or test harness can declare it via `session.declare_gold_files([...])` (a small helper on SessionState); when unset, acc@k/FUH return `null`. CtxEff is computed as `sum(bytes of files that appear in final write-set patches) / sum(bytes of all read files)`.
- Liveness target for G3: L3.

**S16 Structural call graph (§3 CT-5, CT-6):**
- New DB `.fa/structural.db` (SQLite, same pattern as `.fa/fts.db`; stored under workspace `.fa/`; deleted with session).
- Schema:
  ```sql
  CREATE TABLE IF NOT EXISTS symbols (
    sym_id        TEXT PRIMARY KEY,         -- sha256(relpath + ":" + qualname)[:16]
    path          TEXT NOT NULL,
    qualname      TEXT NOT NULL,            -- e.g. "fa.memory.fts_index.InstantGrepIndex.instant_grep"
    kind          TEXT NOT NULL,            -- "function"|"method"|"class"|"doc_anchor"
    start_line    INTEGER NOT NULL,
    end_line      INTEGER NOT NULL,
    args_json     TEXT,                     -- JSON list of arg names (for functions/methods)
    docstring     TEXT,                     -- first line, capped at 400 chars
    file_hash     TEXT NOT NULL,            -- sha256(file_bytes)[:24]
    language      TEXT NOT NULL DEFAULT 'python'
  );
  CREATE INDEX IF NOT EXISTS idx_symbols_qualname ON symbols(qualname);
  CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path);
  CREATE TABLE IF NOT EXISTS calls (
    caller_sym_id TEXT NOT NULL,
    callee_sym_id TEXT NOT NULL,
    call_line     INTEGER NOT NULL,
    PRIMARY KEY (caller_sym_id, callee_sym_id, call_line),
    FOREIGN KEY (caller_sym_id) REFERENCES symbols(sym_id),
    FOREIGN KEY (callee_sym_id) REFERENCES symbols(sym_id)
  );
  CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_sym_id);
  CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_sym_id);
  CREATE TABLE IF NOT EXISTS struct_meta (
    path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    indexed_at REAL NOT NULL
  );
  ```
- Indexer (`src/fa/memory/structural_index.py`): walks `.py` files via the same exclude/symlink-safe iterator as S14b.1; uses `ast.parse`; walks `ast.FunctionDef`/`ast.AsyncFunctionDef` (and per Q-AST decision possibly `ast.ClassDef`); for each function body walks `ast.Call` nodes, resolves callee to a qualname best-effort (by name against in-file symbols first; cross-file resolution is best-effort: match last component against known symbols, mark unresolved callees as `<unresolved>` — do NOT invent edges).
- New tool `src/fa/inner_loop/tools/fs_reach.py` with params:
  - `symbol` (required): e.g. `"build_grep_tool"`, `"InstantGrepIndex.instant_grep"`, `§I-6.2`
  - `direction`: `"up"` (callers) | `"down"` (callees) | `"both"`, default `"both"`
  - `depth`: int default 2, max 5
  - `limit`: int default 20, max 50
  - `kind`: optional filter `"function"|"method"|"class"|"doc_anchor"`
  - `include_tests`: bool default False
  Returns: `{query:..., resolved_to: {sym_id, path, qualname, kind, line, docstring}|null, callers: [...], callees: [...], truncated: bool, unresolved: int}`.
- On non-Python repos (detected by scanning file extensions in root — if no `.py` files found after walking first 50 files), tool returns `{status:"unavailable", reason:"structural index is Python-only in v1", detected_languages:[...]}` (fail-degraded, honest).
- Liveness target for G4: L3.

**S17 Code anchors (§3 CT-7):**
- Doc update to `AGENTS.md` and `knowledge/llms.txt` and `knowledge/skills/authoring` adds convention: at contract/invariant points (not every function, ≤1 per ~200 lines), place a line comment `# §<stable-id>: <short invariant description>` where `<stable-id>` follows the existing pattern (e.g. `§I-S14b-1`, `§CT-5`, `§I-56`).
- The S16 structural indexer picks these up as `kind='doc_anchor'` symbols: regex `r'#\s*§([A-Za-z0-9_.-]+):\s*(.+)$'` matched line-by-line before AST parsing; anchor qualname is `§<id>`; start_line/end_line are the line itself; docstring is the description text.
- `fs_search(query="§I-6.2")` will find these via content search AND `fs_reach(symbol="§I-6.2")` resolves them directly.
- 5–10 seed anchors added to existing FA code as examples (in `blackboard.py:detect_conflict`, `state.py:add_read`, `runtime_limits.py:DEFAULT_MAX_ITERATIONS`, etc.), but we do NOT bulk-annotate every function — that violates the sparsity rule.
- Liveness target for G5: L3.

**State transitions (per slice):**
- STATE `.fa/fts.db`: AS-IS = has `files_fts` (trigram) + `fts_meta`. TO-BE = adds `files_fts_bm25` (unicode61) + a `search_index_meta` version marker row. **Migration:** first run of new indexer detects missing bm25 table and drops+recreates both virtual tables + re-indexes (simple path; the DB is per-session, cheap to rebuild).
- STATE `EventLog` schema: AS-IS = has `tool_call`, `tool_result`, `hook_decision`, `run_stopped` kinds. TO-BE = adds `file_read` kind. Additive; no migration needed (JSON).
- STATE SessionState fields: AS-IS = has per-tool-call `self.turn` (incremented in `record_tool_call`, line 656), but no per-batch counter and no container for search-result paths. TO-BE = adds `batch_turn: int = 0` (per batch/iteration, NOT per tool call — v2.1 G-3 avoids colliding with existing `self.turn`), `last_search_results: set[str] = field(default_factory=set)`, `last_search_turn: int = -1`, and `_gold_files: set[str] = field(default_factory=set)` (v2.1 G-8). `last_search_results` is CLEARED at the start of each batch iteration so that `surfaced_by="search_result"` is only attributed to reads within the same batch that produced the search result.
- STATE `.fa/structural.db`: AS-IS = absent. TO-BE = created lazily on first `fs_reach` call (or first `fs_search` call that references a `§` anchor — TBD in implementation).
- STATE runtime limits load path: AS-IS = per-session config. TO-BE = per-session config overrides `~/.fa/config.yaml` overrides per-profile defaults.

**Performance constraints:**
- First `fs_search` on FA-sized repo (~400 files, ~2MB text): <500ms to index (measured against S14's artifact indexer which indexes ~200 files in 30-80ms).
- Subsequent `fs_search` calls: <50ms.
- `fs_reach` after structural index built: <20ms (BFS over DB, bounded by limit 50).
- First `fs_reach` call (structural index build): <3s on FA repo (~100 .py files, ~15k lines total).
- Event overhead for `file_read` events: <1ms per read (one INSERT, sync=normal; matches existing EventLog write latency).

**Default flag values / error-deny behavior:**
- `output_mode="files"` default for fs_search (cheapest, matches Claude Code).
- `context_lines=1`, hard cap 5 (explicitly reject requests for >5 to prevent token blow-up — return error with deny-reason `context_lines_cap_exceeded`).
- `limit=20`, hard cap 50 (same pattern).
- `case_sensitive=False` default (case-insensitive substring).
- `regex=False` default (literal substring; regex mode is opt-in because it can be expensive on large repos).
- `include_tests=True` for fs_search; `include_tests=False` for fs_reach default (navigation usually wants production code; search usually wants everything).
- `fs_reach` on non-Python: structured `status:"unavailable"`, not exception.
- `fs_exploration_metrics` when no gold declared: returns nulls for acc@k/FUH, never crashes.

---

## 3. Contracts (§6 — hard center)

Contracts are listed by slice; each has producer/consumer/failure/kill-check.

### CT-1: `fs_search` tool signal

```
PRODUCER: src/fa/inner_loop/tools/fs_search.py::build_fs_search_tool → handler(params)
  trigger: LLM invokes fs_search
  pre: params is a mapping; query is non-empty string
  post: returns ToolResult.ok(summary, result={...}) or ToolResult.fail(code, msg)
  IN (params schema):
    query:           str (required, non-empty)
    regex:           bool = False
    case_sensitive:  bool = False
    glob:            str | None = None             (e.g. "src/fa/**/*.py")
    path:            str = "."                     (subdirectory)
    types:           list[str] | None = None       (reserved for blackboard type filter; not implemented in S14b.1, validated+ignored with notice)
    include_tests:   bool = True                   *(v2.1 G-11: note asymmetry — fs_search defaults to True because discovery often needs test files for context; fs_reach defaults to False because call-graph navigation over production code is the common case and test edges are noise)*
    exclude_dirs:    list[str] | None = None       (appended to EXCLUDE_DIRS + EXTRA_EXCLUDE_DIRS)
    max_file_size:   int = 200_000
    output_mode:     "files"|"matches"|"regions"|"counts" = "files"
    context_lines:   int = 1                       (clamped to 0..5)
    limit:           int = 20                      (clamped to 1..50)
    order:           "bm25"|"path"|"match_count" = "bm25"
  OUT (result dict schema):
    query:           str
    method:          "fts5_bm25" | "fts5_trigram_fallback" | "literal_fallback" | "regex_fallback"
    returned:        int
    truncated:       bool
    total_bytes:     int                   # sum of st_size of matched files; 0 when no files matched
    index_stats:     {"indexed": int, "skipped": int, "errors": int}  # populated when ensure_indexed ran this call, else None
    warnings:        list[str] | None      # e.g. ["context_lines clamped from 100 to 5 (hard cap)"], only present when clamping/fallback occurred
    # Exactly one of the four output arrays is populated (matching output_mode)
    files:           list[{"path": str, "match_count": int, "first_match_line": int | None, "first_match_snippet": str | None}]  # when output_mode="files"
    matches:         list[{"path": str, "line": int, "content": str, "before": [str], "after": [str]}]                            # when output_mode="matches"
    regions:         list[{"path": str, "start_line": int, "end_line": int, "match_count": int, "snippet": [str]}]                # when output_mode="regions"
    counts:          list[{"path": str, "count": int}]                                                                           # when output_mode="counts"
    note:            str | None            # e.g. "types parameter reserved; ignoring in v1"
  ERRORS (ToolResult.fail):
    invalid_params         (retryable=True): missing/empty query, bad types (e.g. output_mode not in the enum)
    path_escape            (retryable=True): resolved search path escapes workspace root
    search_failed          (retryable=False): unexpected internal error (BLE001 catch)
  # NOTE: context_lines/limit overages are CLAMPED (not rejected) per R-14: values above cap are
  # reduced to cap and a warning string is appended to result.warnings (e.g. "context_lines clamped
  # from 100 to 5 (hard cap)"). This matches UX research that hard-failing on soft parameter limits
  # wastes a turn when the agent can see the clamp warning and adjust next call. Negative values
  # are normalized to defaults (context_lines<0 → 1; limit<1 → 20).
  SIDE EFFECTS:
    - May trigger lazy index build (writes to .fa/fts.db) on first call
    - Appends tool_call/tool_result to EventLog (via registry base)
    - Updates SessionState.last_search_results / last_search_turn for telemetry (S15, v2.1 G-8)

CONSUMERS:
  - LLM (direct): reads result to decide next reads/edits
  - subagent_prompts.py: updated to call fs_search with output_mode="files" for path discovery
  - tests/test_fs_search.py (C1 live-path proof)

KILL-CHECK (producer-side): remove the `ORDER BY bm25(files_fts_bm25)` clause in the search SQL
  → test_fs_search_bm25_ranking fails because "authentication_middleware.py" (higher TF-IDF weight)
    no longer outranks "test_auth.py" when query="auth middleware".

KILL-CHECK (consumer-side): remove subagent_prompts.py reference update (leave old fs_instant_grep text)
  → test_subagent_prompt_uses_fs_search fails (prompt text assertion).

SHIP RULE: producer C1 tests must pass before consumer-only doc updates count as shipped.
```

### CT-2: Iteration cap reached signal

```
PRODUCER: src/fa/inner_loop/loop.py::run_session  (existing break at line 548 becomes a signal emit)
  trigger: len(results) >= effective_limits.max_iterations after processing a batch
  payload (StopInfo):
    point:  "iteration_cap"
    reason: f"iteration cap reached: used {used} of {limit}"
  payload (EventLog):
    actor:  "runtime"
    kind:   "run_stopped"
    content: {point:"iteration_cap", used:int, limit:int, profile:str}
  paths:
    P1: sequential-batch path (loop.py:565-583)
    P2: parallel-batch path (loop.py:587-605)
    P3: cap reached in the middle of a batch (current truncation code at lines 550-554)
  DUAL-WRITE: required — StopInfo returned AND log.append(...) in same branch, same as existing AFTER_TOOL_EXEC denial.

CONSUMERS:
  - CLI driver (existing StopInfo render path): surfaces "Iteration cap reached (N/M)" to operator
  - fs_chronicle_search (existing, no change needed; event kind "run_stopped" is already searchable)
  - tests/test_iteration_cap.py (C1 live-path)

KILL-CHECK: comment out StopInfo construction and log.append at the cap site
  → test_iteration_cap_emits_stopinfo fails (result.stop is None)
  → test_iteration_cap_logs_event fails (no run_stopped event in log).
```

### CT-3: `file_read` telemetry event

```
PRODUCER: src/fa/inner_loop/tools/read_file.py::handler (augmented)
          via SessionState.add_read (augmented to take metadata kwargs)
  trigger: fs_read_file tool returns successfully
  payload (EventLog event, kind="file_read"):
    path:          str (relative to workspace root)
    turn:          int (1-based batch/iteration counter, from SessionState.batch_turn — v2.1 G-3: this is NOT the existing per-tool-call `state.turn` counter)
    start_line:    int | null
    end_line:      int | null
    surfaced_by:   "search_result"|"artifact_index"|"direct_reference"|"breadcrumbs"|"unknown"
    bytes_read:    int
  SIDE EFFECTS: one INSERT to EventLog; calls transaction.add_read as before (no breakage of write-set tracking).

CONSUMERS:
  - fs_exploration_metrics tool (CT-4)
  - fs_chronicle_search (existing; substring search works on new events automatically)
  - tests/test_exploration_telemetry.py

KILL-CHECK: remove the event emission in read_file.py (leave old add_read(path) call in place)
  → test_file_read_event_emitted fails.
```

### CT-4: `fs_exploration_metrics` tool

```
PRODUCER: src/fa/inner_loop/tools/fs_exploration_metrics.py (NEW)
  IN:
    reset: bool = False    (if True, clears declared gold and resets counters for current session)
  OUT:
    acc_at_k:           dict[str, float|null]   {"1":...,"5":...,"10":...,"20":...}
    first_useful_hit:   int|null                (turn of first read of any gold file; null if none)
    ctx_efficiency:     float (0..1)
    n_reads:            int
    n_searches:         int
    gold_files:         list[str]|null
    note:               str (when gold_files is null: "declare gold files via declare_gold_files for acc/fuh")
  Computation:
    acc@k = (any of the first-k reads intersects gold_files) ? 1 : 0   (per session)
    FUH   = first turn index where a gold file was read; null if none
    CtxEff = bytes_read_in_files_that_appear_in_write_patches / total_bytes_read_in_session
            (write-set comes from transaction.write_set — already tracked)
  SIDE EFFECTS: none on reset=False; on reset=True clears SessionState._gold_files

CONSUMERS:
  - Operator-facing: run fs_exploration_metrics at end of session to see how navigation performed
  - Eval harness (for C1 tests)
  - tests/test_exploration_metrics.py

KILL-CHECK: hard-code acc_at_k to return all zeros
  → test_exploration_metrics_acc_at_k fails (seeded session with gold file at position 2 expects acc@5=1.0)
```

### CT-5: Structural index schema + incremental build

```
PRODUCER: src/fa/memory/structural_index.py (NEW)::StructuralIndex
  - builds on first fs_reach call
  - walks via same safe iterator as S14b.1
  - for each .py file:
      1. compute file_hash = sha256(bytes)[:24]
      2. check struct_meta — if file_hash matches, skip (incremental)
      3. ast.parse; on SyntaxError: skip file with WARNING
      4. walk FunctionDef/AsyncFunctionDef → insert symbols
      5. walk Call nodes → insert calls edges (callee resolved best-effort; unresolved → INSERT with callee_sym_id="<unresolved>:<name>" that is NOT linked to a real symbol)
      6. update struct_meta
  - indexes # §<id>: ... comment lines as doc_anchor symbols
  SCHEMA: see §2.2 (symbols, calls, struct_meta)
  FAILURE SURFACE:
    - on DB error: logs WARNING, structural index marked unavailable for the session
    - on file parse error: skip that file (log WARNING), continue with rest
    - on non-Python repo: index_build returns StructIndexStats with files_indexed=0, available=False

CONSUMERS:
  - fs_reach tool (CT-6)
  - tests/test_structural_index.py (C0 unit tests)
  - tests/test_fs_reach.py (C1 live-path)

KILL-CHECK: drop the `calls` table after building (in test setup)
  → test_fs_reach_finds_direct_caller fails (expected caller edge is missing).
```

### CT-6: `fs_reach` tool

```
PRODUCER: src/fa/inner_loop/tools/fs_reach.py (NEW)
  IN (params):
    symbol:        str (required, e.g. "build_grep_tool", "InstantGrepIndex.instant_grep", "§I-6.2")
    direction:     "up"|"down"|"both" = "both"
    depth:         int = 2, clamped 0..5
    limit:         int = 20, clamped 1..50
    kind:          "function"|"method"|"class"|"doc_anchor"|null = null
    include_tests: bool = False
  OUT (result dict):
    status:       "ok"|"unavailable"
    query:        str
    resolved_to:  {sym_id, path, qualname, kind, line:int, docstring:str|null} | null
    callers:      list[{sym_id, path, qualname, kind, line:int, distance:int, docstring:str|null}]
    callees:      list[{sym_id, path, qualname, kind, line:int, distance:int, docstring:str|null}]
    truncated:    bool
    unresolved:   int
    reason:       str | null (when status="unavailable")
    detected_languages: list[str] (when status="unavailable")
  ERRORS:
    invalid_params (retryable=True): missing/empty symbol, bad enum values
    reach_failed   (retryable=False): unexpected internal error (BLE001)
  SIDE EFFECTS: may trigger lazy structural index build on first call

CONSUMERS:
  - LLM (direct, for multi-file navigation)
  - subagent_prompts.py (phase 2 of subagent upgrade; S16)
  - tests/test_fs_reach.py

KILL-CHECK: comment out BFS expansion in callee direction
  → test_fs_reach_callees_transitive fails (depth=2 callee not found).
```

### CT-7: `§<id>:` code-anchor contract + indexing

```
CONVENTION (doc-enforced):
  - Anchor line format: `# §<stable-id>: <description>` (single-line, # comment, one space after #, §, id, colon, space, description until EOL)
  - <stable-id> matches `[A-Za-z0-9_.-]+`
  - Density: at most one anchor per ~200 lines per file; anchors mark contracts/invariants/plan-trace points, NOT routine functions
  - Anchor ids are stable across edits (do NOT rename §I-56 once referenced); to deprecate an anchor leave the comment with `[deprecated in favor of §<new-id>]` suffix for one cycle, then remove.
  - Anchors are referenced externally as `<filepath>#§<id>` (same style as doc anchors).

PRODUCER: developer/agent writing code; enforced by doc-maintenance skill (best effort; not a hard gate initially).

INDEXER (subsumed by CT-5): structural_index.py extracts these as kind='doc_anchor' symbols before AST parsing.

CONSUMERS:
  - fs_reach (symbol="§X.Y")
  - fs_search (content match)
  - doc-maintenance skill can cross-check BACKLOG/ADR references for anchor existence

KILL-CHECK: remove the regex extraction in structural_index.py
  → test_doc_anchor_indexed_as_symbol fails (anchor symbol not in DB, fs_reach returns null).
```

### Invariants (plan-local)

- **INV-S14b-1 (symlink safety):** No file outside `workspace_root.resolve()` is ever read for indexing or search. Verified by `test_fs_search_symlink_escape` (adversarial C3 test — symlink to /etc/passwd; file must not appear in results or index).
- **INV-S14b-2 (fail-degraded):** Any unexpected exception in fs_search, fs_reach, fs_exploration_metrics, or the indexers is caught by a BLE001 handler that logs WARNING and returns a structured ToolResult.fail — the loop MUST never crash due to a search/index failure.
- **INV-S14b-3 (read-only search):** fs_search and fs_reach do not modify any file in the workspace (they may write to `.fa/` indexes, which are excluded from write-set tracking by convention).
- **INV-S14b-4 (no query-time full reindex):** mtime-based incremental update; the indexer never does a full reindex unless explicitly triggered (DB missing, schema version change).
- **INV-S14b-5 (token caps):** No fs_search response exceeds ~30KB (enforced by limit+context_lines caps + elider; matches existing ToolSpec.max_context_bytes pattern).
- **INV-S14b-6 (tool-name wire compatibility):** After S14b.1, every ToolSpec.name in the registry is a member of the updated TOOL_NAMES frozenset; enforced by existing S13.10 test.
- **INV-S14b-7 (no backward-compat shim):** fs_grep / fs_instant_grep / fs_glob are NOT preserved as aliases. All internal and prompt references must be updated in the same patch. This is a deliberate operator-ratified break.

### Security contract (C3)

- **CT-SEC1 (path traversal):** The `path` and `glob` parameters of fs_search are resolved relative to workspace_root and may not escape it. C3 test: `fs_search(query="x", path="../../../../../etc")` → result contains no files outside workspace; structured error or empty.
- **CT-SEC2 (symlink escape, same as INV-S14b-1):** C3 test plants a symlink `repo-link -> /etc` inside workspace; fs_search must not return /etc/passwd content.
- **CT-SEC3 (read-side DoS):** `max_file_size` default 200KB with hard cap on `context_lines` (5) and `limit` (50) bounds response size. C3 test: `fs_search(query="x", context_lines=1000, limit=10000)` is clamped to the caps and a warning entry is appended to `result.warnings` (R-14); only truly invalid values (negative, wrong type, empty query, bad enum) produce `invalid_params`.
- **CT-SEC4 (regex DoS):** When `regex=True`, pattern is compiled once with `re.compile` and executed per-file with bounded time? No timeouts per-file in v1 (fail-degraded: if file read throws OSError it is skipped); however the same max_file_size cap prevents pathological regex runtime on huge files. Note: regex catastrophic-backtracking risk is real but bounded because: (a) files are read as streaming lines, (b) per-line regex match against ≤200KB is fast in CPython's re2-like C engine for most patterns. Documented as residual risk; can add a per-call timeout in follow-up if observed.

---

## 4. Path & flag matrix (§7)

### 4.1 Path inventory (producer paths for signal contracts)

| P# | Trigger | File:symbol | Slice | Covering S#/T# |
|---|---|---|---|---|
| P1 | First fs_search call, FTS index missing/empty → lazy build | `fs_search.py:handler` → `search_index.ensure_indexed` | S14b.1 | S1-S3 / T1 |
| P2 | fs_search, BM25 yields results (happy path) | `search_index.search` → FTS bm25 query | S14b.1 | S4 / T2 |
| P3 | fs_search, BM25 yields 0 results → trigram substring fallback | same, fallback branch | S14b.1 | S4 / T3 |
| P4 | fs_search, both FTS paths fail (DB corrupt/missing) → python walk | same, outer fallback | S14b.1 | S4 / T4 |
| P5 | fs_search with glob filter | search._apply_glob | S14b.1 | S4 / T5 |
| P6 | fs_search output_mode=regions (adjacent-line grouping) | search._group_regions | S14b.1 | S4 / T6 |
| P7 | fs_search on symlink-escape attempt | search._iter_files + is_relative_to | S14b.1 | S3 / T-SEC2 |
| P8 | Iteration cap hit in sequential path | loop.py `_execute_one_sequential` branch | S14b.2 | S10 / T10 |
| P9 | Iteration cap hit in parallel path | loop.py `_execute_batch_parallel` continuation | S14b.2 | S10 / T11 |
| P10 | Iteration cap hit mid-batch (truncation) | loop.py `batch = batch[:remaining]` branch | S14b.2 | S10 / T12 |
| P11 | read_file tool called with start/end line → file_read event with line metadata | read_file.py handler | S15 | S14 / T14 |
| P12 | read_file tool called for whole file → file_read event with null line range | read_file.py handler | S15 | S14 / T14 |
| P13 | fs_search result is followed by read_file → surfaced_by="search_result" | telemetry._attribute_read_source | S15 | S15 / T15 |
| P14 | First fs_reach call on Python repo → lazy structural build | structural_index.py | S16 | S19 / T19 |
| P15 | fs_reach resolves an in-file symbol | reach._resolve_symbol | S16 | S20 / T20 |
| P16 | fs_reach on non-Python repo → unavailable status | reach handler | S16 | S20 / T21 |
| P17 | fs_reach with `§` anchor symbol | reach._resolve_anchor | S16+S17 | S23 / T23 |

Coverage gate: every P1..P17 has a named covering step S# and a named verification T#. All 17 rows covered.

### 4.2 Flag / environment / profile matrix

| ID | Config | Proves | Covering S#/T# |
|---|---|---|---|
| A | Default config (no `~/.fa/config.yaml`), role=implementer | primary path (highest expected usage); fs_search defaults work; per-profile iteration limit=40 | S4, S10 / T2, T10 |
| B | Full cascade: `~/.fa/config.yaml` sets `iteration_limits.implementer=10`, session config overrides to 8 | config precedence (session > ~/.fa > default) works | S12 / T12 |
| C | Defaults out-of-the-box on fresh clone (no ~/.fa, no session .fa) | zero-config behaviour for new users; fs_search auto-indexes; iteration defaults match code | S3, S10 / T1, T10 |
| D | Non-Python repo (fixture with only .js/.md files) | fs_reach degrades gracefully; fs_search works regardless | S20 / T21 |
| E | Researcher role | researcher iteration limit=15; fs_search is in tool set | S11 / T11 |
| F | Verifier role | verifier iteration limit=5 | S11 / T11 |
| P-r | Regex query (regex=true) on Python code | regex path works; invalid regex returns invalid_params | S4 / T5 |
| P-c | Case-sensitive search | case_sensitive=True flips matching | S4 / T2 |
| P-s | Symlink escape attempt (adversarial) | INV-S14b-1 holds | S3 / T-SEC2 |
| P-t | include_tests=False filter | tests/ files excluded | S4 / T5 |
| P-x | Context_lines=5 (cap) | cap enforced; >5 rejected | S4 / T-SEC3 |

Each matrix row has a covering step or is explicitly verified in tests (per §6 verification).

---

## 5. Step-by-step implementation (task cards, §8)

Ordering rules per plan-authoring skill: discover/confirm → types/schemas → producers → consumers → root wiring (L2→L3) → producer kill-check → paired consumer verification → path/matrix completion → adversarial cases → contract/CI gate → docs/ADR.

Slices are ordered so earlier slices don't depend on later ones. Within a slice, steps are ordered by dependency.

### Slice S14b.1 — Unified fs_search (G1)

---

#### Step S1: Update canonical tool names (TOOL_NAMES frozenset)

**Traces-to:** G1, CT-1
**Depends-on:** none (pure set edit, can be done early without breaking imports)
**Parallelizable-with:** S2, S3 (schema/module work doesn't touch tool_names)
**Target liveness:** L0→L1 (names exist but no ToolSpec provides them yet; composition test will fail until S5 lands — that's intentional, we don't mark READY until S5)

**Edit:**
- path: `src/fa/inner_loop/tool_names.py`
- symbol: `TOOL_NAMES` frozenset
- change: remove `"fs_glob"`, `"fs_grep"`, `"fs_instant_grep"`; add `"fs_search"` ONLY in this patch.
  - **(v2.1 G-1):** Do NOT add `fs_reach` or `fs_exploration_metrics` here yet — their ToolSpec modules don't exist in S14b.1, and `test_s13_10_tool_names.py::test_map_covers_all_tool_spec_names` asserts bidirectional coverage (every TOOL_NAMES name must match a `name="fs_*"` literal in `tools/*.py`). Those two names are added in their own slice patches (S15 adds `fs_exploration_metrics`, S20 adds `fs_reach`), immediately after their ToolSpec files are created.

**Do:**
1. Open tool_names.py, edit the frozenset literal.
2. Run `python3 -c "from fa.inner_loop.tool_names import TOOL_NAMES; print('fs_search' in TOOL_NAMES, 'fs_grep' in TOOL_NAMES)"` → must print `True False`.

**Do-not:**
- Do not remove the old names yet (that's done in the same edit — replace, not leave alongside). Per INV-S14b-7 we don't keep aliases.

**Exit criteria:**
- [ ] `grep -n "fs_search" src/fa/inner_loop/tool_names.py` matches.
- [ ] `grep -nE "fs_grep|fs_instant_grep|fs_glob" src/fa/inner_loop/tool_names.py` returns 0.
- [ ] python -c import check passes.

---

#### Step S2: Extend memory/fts_index.py with BM25 support (or add new module search_index.py)

**Traces-to:** G1, CT-1 (P2/P3/P4)
**Depends-on:** none
**Parallelizable-with:** S1, S4
**Target liveness:** L0→L2 (module exists and has index+search methods, but no tool calls it yet)

**Design decision (preflight-verified):** Keep `InstantGrepIndex` in `fts_index.py` for backward import compatibility (one release cycle with DeprecationWarning per R-8), but add a new class `SearchIndex` in a new file `src/fa/memory/search_index.py` that owns the BM25 table AND rebuilds/uses the trigram table for unified search. (New code is additive where possible; existing `test_instant_grep.py` continues to pass because InstantGrepIndex class is retained.)

**Edit:**
- path: `src/fa/memory/_safe_walk.py` (NEW — small helper, ~60 lines)  *(v2.1 G-6, G-10)*
  - symbol: `iter_searchable_files(root, patterns, *, extra_exclude_dirs=None, include_tests=True, max_file_size=200_000, use_git_ls_files=True) -> Iterator[tuple[Path, str, float, int]]`
  - yields `(absolute_path, rel_path_str, st_mtime, st_size)` for files that pass ALL filters.
  - Imports `EXCLUDE_DIRS` from `fa.memory.fts_index` as `_BASE_EXCLUDE_DIRS`, defines module-level `EXTRA_EXCLUDE_DIRS = frozenset({".tox", ".pytest_cache", ".ruff_cache", ".nox", "htmlcov"})` and `EXCLUDE_DIR_GLOBS = frozenset({"*.egg-info"})`  *(v2.1 G-4)*.
  - Effective exclude = `_BASE_EXCLUDE_DIRS | EXTRA_EXCLUDE_DIRS | extra_exclude_dirs | ({"tests"} if not include_tests else set())`.
  - **Fast path (v2.1 G-2):** tries `git_ls_files(root)` from `fa.inner_loop.tools._common`; on success iterates that list (filtering by patterns, EXCLUDE_DIRS, symlink-escape, size). On any exception (subprocess error, not a git repo, timeout — captured as BLE001), logs WARNING and falls back to `os.walk` with in-place dir prune (matching existing `glob.py:_iter_files_fallback` behavior exactly).
  - Symlink safety: for every candidate, `fp.resolve().is_relative_to(root_resolved)` is checked BEFORE yielding; symlinks that escape the root are silently skipped.
  - fnmatch-based directory pruning AND basename-glob matching for `*.egg-info` etc.
- path: `src/fa/memory/search_index.py` (NEW)
- symbol: `SearchIndex`
- change: new class with:
  - `__init__(db_path)`: opens SQLite connection at the SAME `db_path` used by InstantGrepIndex (default `.fa/fts.db`, feature-flag `fts_db_path`) — *(v2.1 G-7)*. Runs one-time schema migration:
    1. `CREATE TABLE IF NOT EXISTS search_meta (key TEXT PRIMARY KEY, value TEXT)`
    2. Check `schema_version` row; if missing or <1: `DROP TABLE IF EXISTS files_fts` (the old trigram table from InstantGrepIndex is rebuilt so content matches new normalization expectations — safe because per-session DB is disposable), then create both virtual tables:
       - `files_fts (path UNINDEXED, content) USING fts5(tokenize='trigram')` — rebuilt, populated with RAW content for substring.
       - `files_fts_bm25 (path UNINDEXED, content) USING fts5(tokenize='unicode61 remove_diacritics 2')` — populated with `_bm25_tokenize(raw)` content for ranking.
    3. (Re)create `fts_meta(path PRIMARY KEY, mtime REAL, size INTEGER)` if not exists (for cross-compat with InstantGrepIndex; same schema).
    4. Insert `schema_version=1` into search_meta.
  - `_bm25_tokenize(text: str) -> str`: static method implementing R-1 normalization (snake_case and CamelCase splitting, capped per-file at 100 KB).
  - `ensure_indexed(root: Path, *, patterns=DEFAULT_PATTERNS, max_file_size=200_000) -> SearchIndexStats`: calls `iter_searchable_files` (S3 helper) to enumerate candidates; for each file, compares (mtime, size) against `fts_meta`; for new/changed files reads content (utf-8, errors=ignore), inserts RAW into `files_fts` and `_bm25_tokenize(content)` into `files_fts_bm25` within a single transaction per file; updates `fts_meta`; tracks new/updated/skipped/error counts; sets process-local sentinel `_indexed_for_session = True` at end.
  - `_search_bm25(query, limit) -> list[(path, bm25_score, snippet)]`
  - `_search_trigram(query, limit) -> list[path]` (substring fallback via `files_fts WHERE content LIKE '%q%'` OR `files_fts MATCH query` depending on query shape)
  - `_search_literal(query, limit, case_sensitive, regex) -> list[path]` (streaming Python walk fallback when FTS returns zero rows across both tables, OR when regex=True)
  - `search(query, *, output_mode, glob, path, include_tests, exclude_dirs, max_file_size, context_lines, limit, order, regex, case_sensitive) -> SearchResult`: orchestrates: try BM25 first; if zero rows AND no special FTS syntax fall back to trigram LIKE; if still zero fall back to streaming Python walk. Populate output per mode.
  - `close()`: closes connection; context-manager support.
- path: `src/fa/memory/__init__.py` (if needed) — export `SearchIndex` and `iter_searchable_files`.
- path: `src/fa/memory/fts_index.py`
- symbol: `EXCLUDE_DIRS`, `InstantGrepIndex.__init__`
- change (v2.1 R-8):
  - NO CHANGE to `EXCLUDE_DIRS` itself (single-source-of-truth kept here; `_safe_walk.py` adds EXTRA_EXCLUDE_DIRS on import).
  - Add `import warnings; warnings.warn("InstantGrepIndex is deprecated; use fa.memory.search_index.SearchIndex", DeprecationWarning, stacklevel=2)` at the TOP of `InstantGrepIndex.__init__`.

**Degree of freedom closed:**
- Without a schema_version row, future schema changes (e.g., adding new columns) couldn't detect stale DBs. Include `schema_version INTEGER` in `search_meta` initial population with CURRENT_VERSION=1.

**Deterministic mechanism:**
- All file iteration uses `root_resolved = root.resolve()` and `fp.resolve().is_relative_to(root_resolved)` (matches existing pattern).
- Exclude dirs = EXCLUDE_DIRS ∪ user-supplied exclude_dirs ∪ ({"tests"} if not include_tests else set()).
- BM25 query uses parameterized SQL (no string concatenation into SQL) → no SQL injection risk.
- `query` is wrapped in double-quotes for FTS MATCH and internal `"` are escaped as `""` (standard FTS5 escaping).
- Regex mode bypasses FTS entirely, uses Python `re.compile` (because FTS MATCH doesn't speak regex).

**Do:**
1. Create search_index.py with the skeleton class (no logic yet — just `__init__`, `ensure_indexed` with a TODO, `search` that raises NotImplementedError).
2. Write unit tests for the schema creation first (C0): `test_search_index_schema.py` → asserts the three tables exist on a fresh DB.
3. Implement `ensure_indexed` using the same os.walk + prune pattern as `fts_index.index_repo`. Factor out the file-iteration logic into a shared helper `iter_searchable_files(root, patterns, exclude_dirs)` in `search_index.py` (to be reused by structural_index.py in S16).
4. Implement `_search_bm25` using `SELECT path, bm25(files_fts_bm25) AS score FROM files_fts_bm25 WHERE files_fts_bm25 MATCH ? ORDER BY score LIMIT ?`. Note: bm25() returns lower=better in FTS5 by default; we invert by ordering ASC.
5. Implement trigram fallback (delegates to InstantGrepIndex.instant_grep or queries the trigram table directly).
6. Implement python walk fallback (mirrors existing grep.py `_grep_file_stream`).
7. Wire fallbacks: try bm25 first; if 0 rows AND query has no special FTS syntax, fall back to trigram; if trigram also 0, fall back to python walk (literal substring or regex). Set `method` field in result accordingly.

**Do-not:**
- Do not modify `InstantGrepIndex` (keep it working for any lingering imports; we will remove imports in later steps).
- Do not add network calls, threads, or background indexing.
- Do not write to `.fa/` on any error path (fail-degraded: if DB can't be opened, fall back to python walk every call; do not crash).
- Do not call `index_repo` inside `search()` unless `self._indexed` is False AND we are on the FIRST call (process-local sentinel set at end of ensure_indexed).

**Exit criteria:**
- [ ] C0 unit tests pass for schema creation, ensure_indexed idempotency, bm25 ranking, trigram fallback, python walk fallback, glob filter.
- [ ] `py_compile` passes on search_index.py.
- [ ] `ruff check src/fa/memory/search_index.py` passes.
- [ ] `mypy src/fa/memory/search_index.py` has zero errors (existing stub warnings in other modules are pre-existing and out of scope).

**Kill-check (CT-1 producer, pre-tool):** remove the `ORDER BY bm25(...) ASC` clause; C0 test `test_bm25_ordering` must fail because results are returned in insertion order.

---

#### Step S3: Safe file iterator shared helper

**Traces-to:** CT-1, INV-S14b-1, INV-S14b-2, CT-SEC2
**Depends-on:** none (can be done in parallel with S2; S2 imports from here)
**Parallelizable-with:** S1, S2
**Target liveness:** L0→L3 (this is the iterator; kill-check is security-critical)

**Edit:**
- path: `src/fa/memory/_safe_walk.py` (NEW, dedicated module — v2.1 G-6 fixes coupling concern)
- symbol: `iter_searchable_files(root, patterns, *, extra_exclude_dirs=None, include_tests=True, max_file_size=200_000, use_git_ls_files=True) -> Iterator[tuple[Path, str, float, int]]`
- change: generator yielding `(absolute_path, rel_path_str, st_mtime_float, st_size_int)` for files that pass all filters (extension, exclude dirs, symlink escape, size cap). Used by both `SearchIndex.ensure_indexed` (S2) and `StructuralIndex.ensure_indexed` (S18).

**Deterministic mechanism (v2.1 G-2, G-4, G-10):**
- `root_resolved = root.resolve(strict=True)` — fails early if root isn't a directory.
- Build `effective_exclude: frozenset[str]` = `_BASE_EXCLUDE_DIRS | EXTRA_EXCLUDE_DIRS | extra_exclude_dirs | ({"tests"} if not include_tests else set())`.
- **Fast path (primary):** call `git_ls_files(root)` (from `fa.inner_loop.tools._common`, which already exists and handles `--cached --others --exclude-standard`). On success, iterate returned relpaths; for each:
  1. construct `fp = root / rel`, `fp_resolved = fp.resolve()`; if `not fp_resolved.is_relative_to(root_resolved)` → skip (symlink escape).
  2. check `any(part in effective_exclude for part in fp.parts)` → skip if any path component matches an excluded dir name (defense in depth against force-added files).
  3. check `fnmatch.fnmatch(fp.name, pat)` against `EXCLUDE_DIR_GLOBS` (catches `*.egg-info`) → skip if matched.
  4. extension match: `any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(fp.name, pat) for pat in patterns)` → skip if none match.
  5. stat; skip on OSError (log WARNING, continue); skip if `st.st_size > max_file_size` (unless `max_file_size <= 0` which means unlimited).
  6. yield `(fp_resolved, rel, st.st_mtime, st.st_size)`.
- **Fallback (on git failure, non-git repo, timeout):** log WARNING, then run `os.walk(root_resolved, followlinks=False)` with in-place dir prune: `dirnames[:] = [d for d in dirnames if d not in effective_exclude and not any(fnmatch.fnmatch(d, g) for g in EXCLUDE_DIR_GLOBS) and not d.startswith('.')]`. Apply the same per-file filters (2-5) as the fast path.
- On any unexpected per-file exception: WARNING log, continue (BLE001 pattern, matches existing grep.py/glob.py).

**Do:**
1. Write helper function with docstring describing the safety properties.
2. Write adversarial C3 tests in `tests/test_safe_walk.py`:
   - Symlink to outside root (→ file is skipped, no content read).
   - Directory named `node_modules` (→ pruned, not entered).
   - File with 0 bytes (→ yielded normally).
   - File over max_file_size (→ skipped, in skipped_large return list).
   - Permission denied on a file (→ skipped with WARNING, does not abort walk).

**Do-not:**
- Do not resolve symlinks and then follow them OUTSIDE the root (that's the bug we're preventing).
- Do not open/read file content inside the iterator (that's the caller's job; iterator does stat + filtering only).

**Exit criteria:**
- [ ] C3 adversarial tests pass, especially the symlink escape test (T-SEC2).
- [ ] `mypy`/`ruff` clean.

---

#### Step S4: Build fs_search ToolSpec

**Traces-to:** CT-1 (main producer), all P2-P7
**Depends-on:** S2 (SearchIndex class), S3 (safe iterator)
**Parallelizable-with:** none (depends on both)
**Target liveness:** L0→L2 (ToolSpec exists and is importable; not yet wired into profiles)

**Edit:**
- path: `src/fa/inner_loop/tools/fs_search.py` (NEW)
- symbol: `build_fs_search_tool(db_path: Path, workspace_root: Path) -> ToolSpec`
- change: new module with handler that:
  1. Parses params: query, regex, case_sensitive, glob, path, types, include_tests, exclude_dirs, max_file_size, output_mode, context_lines, limit, order.
  2. Validates with friendly errors (per CT-1 error list).
  3. Clamps context_lines to [0, 5], limit to [1, 50].
  4. Resolves `subdir = (workspace_root / path).resolve()` and checks it is_relative_to workspace_root (CT-SEC1).
  5. Gets or creates SearchIndex via a module-level cache (one index per db_path), calls `ensure_indexed(workspace_root)` (lazy).
  6. Calls `index.search(...)` with all the validated params.
  7. Calls `session.note_search_results(returned_paths)` for S15 telemetry (if session is available via `get_current_session()`; if not, skip). Uses `note_search_results` helper (S14) which sets `last_search_results` and `last_search_turn` on the session state (v2.1 G-8).
  8. Returns `ToolResult.ok(summary, result=...)`.
  9. Wraps handler body in try/except BLE001 returning ToolResult.fail("search_failed", ...).

**Edit (docs in description):** ToolSpec.description explains the four output modes and how to pick them, aligning with AGENTS.md intent-matrix.

**Do:**
1. Start from grep.py's structure (similar handler pattern), but consolidate the three tools' features.
2. Implement output mode dispatch:
   - `files`: returns only unique paths with match_count (what fs_instant_grep did, but with BM25 order).
   - `matches`: returns line-level matches with before/after context (what fs_grep did).
   - `regions`: groups adjacent line matches within 3 lines of each other into contiguous regions; each region has `{path, start_line, end_line, match_count, snippet:[str]}` (P1-3).
   - `counts`: returns count-per-path (what a summary glob+grep combo does).
3. For `matches` and `regions`, read file content on demand and extract context lines (bounded by limit * context_lines).
4. Compute `total_bytes` as sum of st_size for matched files (cheap; already available from meta).
5. Set `truncated=True` if more results exist than limit.
6. Set `note="types parameter reserved; not yet filtering by artifact type"` when `types` is passed (future extension point).
7. Add `__all__ = ["build_fs_search_tool"]`.

**Do-not:**
- Do not filter by blackboard artifact types in this slice (reserved param for future; documented, validated, ignored).
- Do not return content snippets for `files` mode (token-efficient).
- Do not import read_file or write_file (no circular imports; fs_search is read-only on workspace).
- Do not exceed MAX_CONTEXT_BYTES (set ToolSpec.max_context_bytes to ~30_000; use truncate_for_preview pattern from _common.py if needed).

**Exit criteria:**
- [ ] C0 unit tests pass for all four output modes on a tiny fixture repo (5-10 files with known content).
- [ ] C1 test at ToolSpec layer: invoke the handler directly via ToolSpec and assert result shape.
- [ ] Parameter validation tests: empty query, bad enum, context_lines>5, limit>50, path escape.
- [ ] Kill-check T-BM25 passes (remove ORDER BY bm25 → test fails).

---

#### Step S5: Wire fs_search into profiles + registry + parallel-safe set

**Traces-to:** G1, INV-S14b-6 (S13.10)
**Depends-on:** S1 (tool_names updated), S4 (ToolSpec exists)
**Parallelizable-with:** S6 (prompt updates), S7 (doc updates)
**Target liveness:** L2→L3 (tool is callable from the loop for all roles)

**Edits (two registration sites, v2.1 G-9):**

The registration surface in v2 code is split across TWO modules; both must be updated atomically or imports of the deleted tools will throw at registry-build time.

- path: `src/fa/inner_loop/profiles.py` (SITE 1 — `_build_tool_builders`, lines 138-269)
  - In `PROFILES_RAW` for researcher (~line 41), code-reviewer (~line 60), implementer (~line 71), and planner (~line 83) profiles, replace `"fs_glob", "fs_grep", "fs_instant_grep"` (or whichever subset each role has) with `"fs_search"`.
  - **Verifier role (line ~43, `tools: ["fs_run_bash"]`) is NOT modified** — keep it bash-only per the role's minimal single-command contract (R-3 fix from review).
  - In `_build_tool_builders` (lines 225-269):
    - REMOVE the three try/except blocks that import `build_glob_tool` (lines 226-230), `build_grep_tool` (lines 232-236), and `build_instant_grep_tool` (lines 238-256) including the feature-flag `fts_path` lookup inside the instant_grep block.
    - ADD a new try/except block in their place:
      ```python
      try:
          from fa.inner_loop.tools.fs_search import build_fs_search_tool
          try:
              from fa.feature_flags import load_feature_flags_from_path
              ff = load_feature_flags_from_path().flags
              fts_path = getattr(ff, "fts_db_path", ".fa/fts.db")
          except Exception:  # noqa: BLE001
              fts_path = ".fa/fts.db"
          builders["fs_search"] = lambda bp=fts_path: build_fs_search_tool(root / bp, root)
      except Exception as exc:  # noqa: BLE001
          logger.warning(f"Failed to setup builder fs_search: {exc}")
      ```
    - Wrap in try/except WARNING (failure-observable, matches existing pattern). Note the `bp=fts_path` late-binding closure fix (Python closure gotcha; without it, all lambdas capture the final `fts_path` value).
- path: `src/fa/inner_loop/tools/__init__.py` (SITE 2 — `_register_extra_tools` + module-level try/except imports)
  - REMOVE module-level try/except imports for `build_glob_tool`, `build_grep_tool`, `build_instant_grep_tool` (lines 24-50 area).
  - ADD module-level try/except for `build_fs_search_tool`:
    ```python
    build_fs_search_tool: Callable[[Path, Path], ToolSpec] | None
    try:
        from fa.inner_loop.tools.fs_search import build_fs_search_tool
    except ImportError as exc:
        logger.warning(f"Failed to import fs_search tool: {exc}")
        build_fs_search_tool = None
    ```
  - In `_register_extra_tools`, REMOVE the `include_glob_grep` parameter and its body (lines 92-110 area), REMOVE the `include_instant_grep` parameter and its body (lines 165-180 area).
  - ADD unconditional registration of fs_search (every role gets it):
    ```python
    if build_fs_search_tool is not None:
        try:
            if "fs_search" not in registry.names():
                # resolve fts_path via feature flags same as profiles.py
                try:
                    from fa.feature_flags import load_feature_flags_from_path
                    ff = load_feature_flags_from_path().flags
                    fts_path = getattr(ff, "fts_db_path", ".fa/fts.db")
                except Exception:  # noqa: BLE001
                    fts_path = ".fa/fts.db"
                registry.register(build_fs_search_tool(workspace_root / fts_path, workspace_root))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to register fs_search: {exc}")
    ```
    (Note: we duplicate the `fts_path` resolution because this module must not import `profiles` — no circular imports allowed. Small DRY violation is intentional.)
  - Remove `include_instant_grep`/`include_glob_grep` parameters from the `_register_extra_tools` signature; update call sites in `build_baseline_registry`, `build_planner_registry`, `build_eval_registry` to stop passing these flags.
- path: `src/fa/inner_loop/loop.py`
  - In `_PARALLEL_SAFE_TOOLS` (lines 40-48), replace `"fs_glob", "fs_grep", "fs_instant_grep"` with `"fs_search"` (it's read-only, parallel-safe). Do NOT add fs_search to `_NEVER_PARALLEL_TOOLS` or `_PATH_SCOPED_TOOLS` (it's read-only on many paths; no write-conflict risk).
  - Remove the old names from `READ_ONLY_TOOLS` alias (it's defined as `_PARALLEL_SAFE_TOOLS` so the update propagates automatically).

**Do:**
1. Run a quick grep for `fs_grep|fs_instant_grep|fs_glob` across `src/` (excluding tests/, excluding the old tool files themselves before deletion) to catch any remaining references.
2. Delete `src/fa/inner_loop/tools/grep.py`, `instant_grep.py`, `glob.py` AFTER all references are updated. (Deleting them first would cause import errors that block intermediate validation.)
   - **Keep** `src/fa/memory/fts_index.py` with its `InstantGrepIndex` class for this release (R-8 shim decision). The new `SearchIndex` in `search_index.py` supersedes it functionally, but out-of-tree callers (e.g. any operator scripts that import `fa.memory.fts_index`) continue to work. Add a `DeprecationWarning` emitted on `InstantGrepIndex.__init__` pointing users to `SearchIndex`. Full removal is a separate cleanup patch (not in S14b.1) to keep this patch focused.
3. Run `python3 -c "from fa.inner_loop.profiles import build_registry_for_role; r = build_registry_for_role('implementer', Path('/tmp')); print(sorted(r.names()))"` — must list `fs_search` and must NOT list the old names.
4. Run the existing S13.10 test (`test_s13_10_tool_names.py`) which enforces TOOL_NAMES coverage; it must pass.

**Do:**
1. Run `grep -rn "fs_grep\|fs_instant_grep\|fs_glob\|build_grep_tool\|build_instant_grep_tool\|build_glob_tool" src/ tests/ AGENTS.md knowledge/llms.txt` BEFORE deleting files, to enumerate every remaining reference.
2. Apply edits to `profiles.py` and `tools/__init__.py` FIRST, update subagent_prompts.py (S6) and any test files that reference the old tool names (S8 migration list), THEN delete the three old tool files. This ordering prevents intermediate states where imports break.
3. Run `python3 -c "from fa.inner_loop.profiles import build_registry_for_role; from pathlib import Path; r = build_registry_for_role('implementer', Path('/tmp')); print(sorted(r.names()))"` — must list `fs_search` and must NOT list `fs_grep`, `fs_instant_grep`, or `fs_glob`.
4. Run the existing S13.10 test (`tests/test_s13_10_tool_names.py`) which enforces TOOL_NAMES coverage; it must pass after S1.
5. **Keep** `src/fa/memory/fts_index.py` with its `InstantGrepIndex` class for this release (R-8 shim decision). Add the DeprecationWarning per S2. Out-of-tree callers (any operator scripts that import `fa.memory.fts_index`) continue to work through one deprecation cycle. Full removal is a dedicated cleanup patch (not in S14b.1) to keep this patch focused.

**Do-not:**
- Do not leave the three old tool files in place as thin wrappers re-exporting fs_search (that's a shim; INV-S14b-7 rejects aliases).
- Do not register fs_search conditionally — it's the universal discovery tool; every non-verifier role needs it.
- Do not register fs_search for the verifier role (R-3); verifier stays `[fs_run_bash]` only.

**Exit criteria:**
- [ ] `grep -rn "fs_grep\|fs_instant_grep\|fs_glob" src/fa/` returns zero code hits (comments that say "formerly fs_grep" are acceptable but discouraged; prompt code and doc references that instruct the LLM must be fully rewritten).
- [ ] `pytest tests/test_s13_10_tool_names.py` passes (TOOL_NAMES ↔ ToolSpec.name bidirectional coverage).
- [ ] `pytest tests/test_blackboard_*.py` still passes (S14 tests not regressed).
- [ ] All three old tool files are deleted: `src/fa/inner_loop/tools/grep.py`, `src/fa/inner_loop/tools/instant_grep.py`, `src/fa/inner_loop/tools/glob.py`.
- [ ] Fresh-session functional smoke (per S14 playbook): in a tmpdir with a few .py/.md files, instantiate `build_fs_search_tool(db_path, root)` and invoke handler with `{"query": "def "}', observe result with `method in ("fts5_bm25", "fts5_trigram_fallback", "literal_fallback")` and returned > 0.

---

#### Step S6: Update subagent prompts + runner comments

**Traces-to:** CT-1 (consumer), KILL-CHECK consumer side
**Depends-on:** S4 (ToolSpec exists)
**Parallelizable-with:** S5
**Target liveness:** consumer updated

**Edits:**
- path: `src/fa/inner_loop/subagent_prompts.py`
  - Line 19 (`RESEARCHER_MINIMAL_PROMPT`): replace the bare `fs_instant_grep` tool reference in the narrative tool list with `fs_search` (the actual tool list is generated from the registry, but the prompt text enumerates them for the model and currently names all three old tools).
  - Lines 64-95 (`_get_fts_files`): this is **live code** (not a comment) that imports `InstantGrepIndex` and calls `.instant_grep(task, limit=limit)` directly. It must be rewritten to use `SearchIndex` from `fa.memory.search_index`, opening the DB at `workspace_root / ".fa" / "fts.db"` and calling `search(query=task, output_mode="files", limit=limit)` and extracting the paths list. Keep the same try/except and fallback signature (return list[str], empty on failure). Wrap in try/except that WARNING-logs and returns [] on failure (fail-degraded, matches existing pattern).
  - Lines 145-155 (`build_filtered_history` docstring and fallback comment): update fallback-chain text from "...transaction read/write sets first, then instant_grep, then glob llms.txt/AGENTS.md/README.md if instant_grep <3 results" → "...transaction read/write sets first, then fs_search(output_mode='files'), then fs_search(output_mode='regions') on narrowed paths, then read_file ranges; fall back to enumerating llms.txt/AGENTS.md/README.md if fs_search returns <3 results".
- path: `src/fa/inner_loop/subagent_runner.py`
  - Line 11 module docstring: update "Phase 3: filtered history task + 5 relevant files via instant_grep not full parent 124 steps" → "via fs_search".
  - Line 44 comment: "+ instant_grep fallback" → "+ fs_search files-mode fallback".
  - Line 205 comment: verify whether it is comment-only or code; if there is live code that references instant_grep, rewrite to use `_get_fts_files` (which was updated above) — do not duplicate search logic.

**Do:**
1. Verify with grep that there is no code (only comments) calling the old tool names; if there is code (e.g. `registry.dispatch(ToolCall(name="fs_instant_grep",...))` it must be rewritten.
2. Run existing subagent tests (if any) to verify they don't hard-code the old names.

**Do-not:**
- Do not change subagent behavior beyond tool/comment names in this slice; deeper subagent prompting improvements are out of scope.

**Exit criteria:**
- [ ] Grep for old names in subagent files returns 0 code hits (comments may reference old names only in "formerly fs_grep" historical notes — but we should just replace, not leave historical notes in prompt code).
- [ ] Subagent tests pass.

---

#### Step S7: Update AGENTS.md and knowledge/llms.txt

**Traces-to:** G1, CT-1 (human/LLM-facing docs)
**Depends-on:** S4, S5
**Parallelizable-with:** S6
**Target liveness:** docs match code

**Edits:**
- path: `src/fa/inner_loop/tools/blackboard_query.py`
  - Line 14 module docstring: "Content search is ``fs_instant_grep``'s job." → "Content search is ``fs_search``'s job (output_mode=\"files\" for path discovery; \"matches\"/\"regions\" for line content)."
  - Line 201 ToolSpec description: "Use fs_instant_grep (not this tool) for substring" → "Use fs_search (not this tool) for substring content search."
- path: `AGENTS.md`
  - Section "Querying Artifacts — Tool Selection by Intent" (already present from S14): collapse the grep/instant_grep/glob rows into a single fs_search row explaining `output_mode` selection.
  - Add explicit rules:
    1. Default to `output_mode="files"` when discovering where to look.
    2. Use `output_mode="regions"` to see grouped context around matches (best for reading snippets without opening the file).
    3. Use `output_mode="matches"` only when you need exact line numbers (e.g., for edit_file targeting).
    4. Use `output_mode="counts"` to understand distribution before narrowing.
    5. Never use raw grep/rg via fs_run_bash for discovery (P0-3 already in llms.txt; reiterate).
    6. Prefer narrower `path` and `glob` scopes over broad searches to save tokens.
- path: `knowledge/llms.txt`
  - §FORMAL SUBSTRATE section: replace old tool entries with fs_search entry documenting all parameters briefly.
  - Update any hard rules that reference old tool names.

**Do:**
1. Re-use the intent-matrix S14 introduced; just consolidate the three rows into one with mode column.
2. Keep examples concrete (e.g., `fs_search(query="detect_conflict", path="src/fa/blackboard", output_mode="regions")`).

**Exit criteria:**
- [ ] No stale references to fs_grep/fs_instant_grep/fs_glob remain except in deprecation notes.
- [ ] Docs show the four output modes.

---

#### Step S8: Write fs_search C1 test suite + live-path proof

**Traces-to:** G1, CT-1 verification
**Depends-on:** S5, S6, S7
**Target liveness:** producer L3

**Do:**
1. Create `tests/test_fs_search.py` with the following test classes:
   - **C0p (pure helpers):** `test_region_grouping` (adjacent lines grouped correctly), `test_bm25_ordering` (synthetic two-file corpus; rarer-term file ranks higher), `test_glob_matches` (pattern matching), `test_symlink_filtering` (uses S3 helper directly).
   - **C1 (live-path at ToolSpec layer):**
     - `test_fs_search_files_mode` — on a fixture with 5 files, `output_mode="files"` returns paths; BM25 orders more relevant files first (T2).
     - `test_fs_search_matches_mode` — line-level content returned with correct line numbers and context (T2).
     - `test_fs_search_regions_mode` — adjacent matches grouped, snippet populated (T6).
     - `test_fs_search_counts_mode` — per-file counts (T2).
     - `test_fs_search_bm25_then_trigram_fallback` — query for a substring that appears inside a word (e.g. "auth" finds "authentication") even though unicode61 tokenizer wouldn't match it as a standalone term (T3).
     - `test_fs_search_python_walk_fallback` — corrupt the FTS DB (write garbage bytes); handler should fall back to walk and still return results (T4).
     - `test_fs_search_glob_filter` — `glob="*.py"` excludes .md files (T5).
     - `test_fs_search_path_escape_rejected` — path="../../etc" → ToolResult.fail or empty result, no /etc content (CT-SEC1, T-SEC1).
     - `test_fs_search_symlink_escape_blocked` — symlink to outside workspace not followed (CT-SEC2, T-SEC2).
     - `test_fs_search_context_cap_enforced` — context_lines=6 → ToolResult.fail (CT-SEC3, T-SEC3).
     - `test_fs_search_limit_cap_enforced` — limit=10000 → clamped or error (CT-SEC3).
     - `test_fs_search_idempotent_index` — call twice; second call does not re-index (mtime check skips all files).
     - `test_fs_search_case_insensitive_default` — query="AUTH" finds "auth" by default; case_sensitive=True does not.
     - `test_fs_search_regex_mode` — `regex=True, query="a.b"` matches "acb" but not "axyb" (T-P-r).
     - `test_fs_search_exclude_tests` — `include_tests=False` excludes tests/ files (T-P-t).
     - `test_fs_search_invalid_params` — empty query, bad enum → ToolResult with error code "invalid_params".
     - `test_fs_search_clamps_context_lines` — context_lines=100 → warning emitted and effective value=5 (kill-check for R-14).
     - `test_fs_search_clamps_limit` — limit=10000 → clamped to 50 with warning.
     - `test_fs_search_path_escape` — path="../../etc" → ToolResult.fail with code "path_escape".
     - `test_fs_search_bm25_finds_snake_case` — query="instant" matches "build_instant_grep_tool" via normalized BM25 column (kill-check for R-1).
     - `test_fs_search_bm25_finds_camel_case` — query="auth" matches "AuthenticationMiddleware" via trigram fallback (R-1 / P3).
     - `test_fs_search_files_mode_has_snippet` — files-mode entries include non-null `first_match_line` and `first_match_snippet` (≤200 chars) for at least the top-N results (R-10).
   - **C1 test-file migration (R-5, critical — must ship in same patch):** the following pre-existing tests reference `fs_grep`/`fs_instant_grep`/`fs_glob` by string name (tool registry assertions, batching, prompt-cache, coverage, slice-wiring). For each, substitute `fs_search` where the test asserts toolset membership / parallel-safe classification, and remove any test that asserts the existence of the three old tool names (replace with a regression-cage test that asserts they are NOT registered):
     - `tests/test_coverage_failure_paths.py`
     - `tests/test_coverage_tools_batch.py`
     - `tests/test_inner_loop_tools.py`
     - `tests/test_observability_runtime_authority.py`
     - `tests/test_prompt_caching_per_role.py`
     - `tests/test_quality_slice_coverage.py`
     - `tests/test_slice5_6_7_wiring.py`
     - `tests/test_tool_batching.py`
     Add an explicit regression test `test_old_tool_names_not_registered` that asserts `"fs_grep" not in registry.names()`, `"fs_instant_grep" not in registry.names()`, `"fs_glob" not in registry.names()` for every role (prevents accidental re-addition).
   - Gate after migration: `grep -rn "fs_grep\|fs_instant_grep\|fs_glob" tests/ src/fa/ AGENTS.md knowledge/llms.txt` must return zero hits (except in the dedicated "deprecated names rejected" test and in historical/CHANGELOG references, which are excluded by `grep -v`).
   - **C1 at composition root:** `test_fs_search_wired_in_all_profiles` — for each role, build the registry and assert "fs_search" is in `registry.names()` and old names are not.
2. Create fixture directory `tests/fixtures/small_repo/` with a handful of known files (auth.py, readme.md, tests/test_auth.py, etc.) used by the tests.

**Do-not:**
- Do not use mocks for the SearchIndex in C1 tests; test the real path with a tempdir repo.
- Do not skip the fallback tests — those are the resilience contracts.

**Exit criteria:**
- [ ] All 18+ tests in test_fs_search.py pass.
- [ ] `pytest tests/test_fs_search.py -v` shows all green.
- [ ] Kill-check: manually comment out the BM25 ORDER BY clause; test_fs_search_bm25_ordering fails.
- [ ] LIVE-PATH PROOF (S14b.1):
  ```
  root: run_session via implementer profile
  matrix: A (default config, role=implementer)
  test: tests/test_fs_search.py::test_fs_search_live_end_to_end
  oracle: fs_search returns ok with method=fts5_bm25, files populated, returned>0
  kill-check: remove bm25 ORDER BY → ordering test fails
  producer: fs_search.py:handler (tool side)
  consumer: LLM-receiving ToolResult (asserted via result shape)
  paths-covered: P1, P2 (happy path); other paths covered by their own tests
  contract-check: INV-S14b-1..7 verified by their tests
  efficiency: first-call index <1s, subsequent calls <50ms (asserted via timing sanity check in test)
  ```

---

#### Step S9: Regenerate patch + run full gate

**Traces-to:** G1 (ship-ready)
**Depends-on:** S1–S8
**Do:**
1. Commit changes to a throwaway branch (or stage them), produce patch:
   ```bash
   cd /home/user/First-Agent-dev
   git diff main -- src/ tests/ AGENTS.md knowledge/llms.txt \
     > /home/user/s14b1-fs-search-unification.patch
   ```
2. On a fresh clone (or via `git stash` + `git apply` on clean `103fb89` with S14 already applied), verify gates in order:
   - `git apply --check s14b1-fs-search-unification.patch` ✅
   - `python3 -m py_compile (all new/changed .py files)` ✅
   - `ruff check src/ tests/` ✅
   - `mypy src/fa/memory/search_index.py src/fa/inner_loop/tools/fs_search.py` ✅
   - `PYTHONPATH=src python3 -m pytest tests/test_fs_search.py tests/test_instant_grep.py tests/test_blackboard_artifact_index.py tests/test_blackboard_query_tool.py -v` ✅ (existing tests must still pass; note: test_instant_grep.py may need adjustment if it imports from moved code — if InstantGrepIndex remains in fts_index.py, no change needed).
   - `PYTHONPATH=src python3 -m pytest tests/ -v` — confirm pre-existing failures (providers_chain, pyrefly, s10a/b, s12, s5_state_root) are unchanged; no new failures introduced.
3. Compute SHA-256 of patch, note size, number of files changed.

**Exit criteria:**
- [ ] Gate checklist fully green.
- [ ] Patch file ready at `/home/user/s14b1-fs-search-unification.patch`.

---

### Slice S14b.2 — Observable iteration cap + per-profile limits + YAML config (G2)

S14b.2 is implemented **on top of** S14b.1 (i.e., in a separate patch applied after S14b.1). Steps S10–S13 below.

---

#### Step S10: Emit StopInfo + run_stopped event at cap

**Traces-to:** CT-2 (producer)
**Depends-on:** S14b.1 landed (not strictly code-dependent; but shipped as next patch after S14b.1)
**Target liveness:** L1→L3

**Edit:**
- path: `src/fa/inner_loop/loop.py`
- symbol: `run_session`
- change: at lines 548-554 (the silent `break`), replace with:
  1. Compute `used = len(results)`, `limit = effective_limits.max_iterations`.
  2. Construct `stop = StopInfo(point="iteration_cap", reason=f"iteration cap reached: used {used} of {limit}")`.
  3. Call `log.append(actor="runtime", kind="run_stopped", content={"point":"iteration_cap","used":used,"limit":limit,"profile":role})`.
  4. `break` (same control flow, but now stop is set so caller sees it).
- Also at the "batch truncated because of remaining" (lines 550-554): after executing the truncated batch, loop back to the cap check and emit the same signal if the cap is reached after that batch.

**Do:**
1. Add a C1 test `tests/test_iteration_cap.py::test_iteration_cap_emits_stopinfo`:
   - Build a registry with a tool that always returns ok but does nothing.
   - Run a session with RuntimeLimits(max_iterations=3) against a call list of length 10.
   - Assert `len(result.results) == 3`, `result.stop is not None`, `result.stop.point == "iteration_cap"`, `result.stop.reason` contains "3 of 3".
   - Assert a `run_stopped` event exists in the log with the expected content fields.

**Do-not:**
- Do not raise an exception or interrupt the currently-executing batch mid-call; the cap is checked between batches (existing behavior preserved) — we just make it visible.
- Do not change the existing StopInfo semantics for AFTER_TOOL_EXEC or BETWEEN_ROUNDS; those remain as-is.

**Exit criteria:**
- [ ] T10 passes (P1 path, sequential).
- [ ] Add parallel-path variant T11: batch with 3 parallel-safe tools, cap at 2, verify stop signal fires correctly.
- [ ] Kill-check: remove the StopInfo construction → T10 fails.

---

#### Step S11: Per-profile iteration limits

**Traces-to:** G2, CT-2 (profile matrix coverage)
**Depends-on:** S10
**Target liveness:** L0→L3

**Edit:**
- path: `src/fa/inner_loop/runtime_limits.py`
  - Add a `PROFILE_ITERATION_DEFAULTS` dict near `DEFAULT_MAX_ITERATIONS`:
    ```python
    PROFILE_ITERATION_DEFAULTS: dict[str, int] = {
        "verifier": 5,
        "researcher": 15,
        "code-reviewer": 15,
        "planner": 20,
        "implementer": 40,
    }
    DEFAULT_MAX_ITERATIONS = 6  # fallback when role is unspecified
    ```
  - Add a classmethod `RuntimeLimits.for_role(role: str | None, *, overrides: dict | None = None) -> RuntimeLimits` that:
    1. Starts with `anchored_defaults()`.
    2. If role is not None and role is in PROFILE_ITERATION_DEFAULTS, sets max_iterations = PROFILE_ITERATION_DEFAULTS[role].
    3. Applies any overrides (from config files — see S12).
- path: `src/fa/inner_loop/profiles.py`
  - In `build_registry_for_role`, accept an optional `runtime_limits: RuntimeLimits | None` parameter; if None, construct via `RuntimeLimits.for_role(role)`.
  - Pass limits down to `run_session` wherever it is called (verify where run_session is invoked from — likely coder_loop.py or session driver).

**Do:**
1. Write tests `test_runtime_limits.py::test_per_profile_limits` for each role's default.
2. Write test `test_runtime_limits_for_role_unknown_role_defaults` to confirm unknown role falls back to DEFAULT_MAX_ITERATIONS.
3. Update T10/T11 to run with explicit roles and verify cap values match.

**Do-not:**
- Do not remove the `max_iterations` field from `RuntimeLimits` (that would break external consumers who construct it directly).
- Do not silently change the default when role=None; code-level default stays at 6 for backward compat (existing tests which don't pass a role will keep working).

**Exit criteria:**
- [ ] Tests pass for all five roles.
- [ ] Existing callers that don't pass role continue to get 6.

---

#### Step S12: `~/.fa/config.yaml` loader

**Traces-to:** G2, CT-2 (matrix B config cascade)
**Depends-on:** S11
**Target liveness:** L0→L3

**Edit:**
- path: `src/fa/inner_loop/runtime_limits.py`
  - Add `_load_user_config_overrides() -> dict`:
    1. Look for `Path.home() / ".fa" / "config.yaml"`.
    2. If missing: return {}.
    3. If present: try `yaml.safe_load`, extract the `iteration_limits` mapping (if present); return it as a dict (lowercased keys).
    4. On YAML parse error / permission error: log WARNING, return {} (fail-degraded, never crash).
  - Modify `for_role` to apply user overrides on top of PROFILE_ITERATION_DEFAULTS (overrides are per-role keyed).
  - Also accept a session-local config path whose values take precedence over user config (cascade: session > ~/.fa > profile default).

**Config schema (documented in docstring):**
```yaml
# ~/.fa/config.yaml
iteration_limits:
  default: 10          # used when role is unspecified
  implementer: 40
  planner: 20
  researcher: 15
  code-reviewer: 15
  verifier: 5
```

**Do:**
1. Write C1 tests:
   - With temp HOME dir containing a config.yaml that sets implementer=10: RuntimeLimits.for_role("implementer").max_iterations == 10.
   - With malformed YAML: WARNING logged, defaults applied.
   - With missing file: defaults applied.
   - Precedence: session override > user override > profile default.
2. Doc: note in AGENTS.md quick-reference that `~/.fa/config.yaml` can tune iteration limits.

**Exit criteria:**
- [ ] Config cascade tests pass.
- [ ] Loader is tolerant (never crashes).

---

#### Step S13: Wire + verify + patch S14b.2

**Do:**
1. Ensure loop.py passes limits through wherever run_session is invoked (grep for `run_session(` call sites).
2. Write C1 end-to-end test `test_iteration_cap_end_to_end.py`: drive a session with role=researcher (limit 15), inject 20 trivial tool calls via a fake tool, assert stop is correct.
3. Generate patch `/home/user/s14b2-iteration-cap.patch`.
4. Run gate: `git apply --check`, `py_compile`, `ruff`, `mypy`, `pytest` (same sequence as S9).

**Exit criteria:**
- [ ] Gate green; patch ready.
- [ ] S14b.2 LIVE-PATH PROOF documented (root=coder_loop invoking run_session with role=implementer, test=test_iteration_cap_end_to_end, oracle=stop.point=="iteration_cap" after 40 results, kill-check=remove StopInfo emit → test fails).

---

### Slice S15 — Exploration telemetry (G3)

S15 patch applies after S14b.1; may be developed in parallel with S14b.2 but ships as its own patch.

---

#### Step S14: Extend add_read and read_file with metadata

**Traces-to:** CT-3 (producer)
**Depends-on:** S14b.1 landed
**Target liveness:** L0→L3

**Edits:**
- path: `src/fa/inner_loop/state.py`
  - Add fields to SessionState (class-level, with `field(default_factory=...)` where mutable):
    - `batch_turn: int = 0` *(v2.1 G-3: renamed from `current_turn` to avoid clash with existing `self.turn` per-tool-call counter at line 656. `batch_turn` increments once per loop batch, i.e. per agent iteration producing a parallel/sequential batch of tool calls. Existing `self.turn` is left untouched.)*
    - `last_search_results: set[str] = field(default_factory=set)` (v2.1 G-8: relpaths returned by the most recent fs_search in the current batch)
    - `last_search_turn: int = -1` (v2.1 G-8: the `batch_turn` at which fs_search last wrote to `last_search_results`)
    - `_gold_files: set[str] = field(default_factory=set)` (for metrics; set via `declare_gold_files`)
  - Change `add_read(self, path: str, *, start_line: int|None=None, end_line: int|None=None, surfaced_by: str="unknown", bytes_read: int=0) -> None`:
    1. Keep existing `transaction.add_read(path)` call.
    2. Append to EventLog a new kind `file_read` with fields `{path, turn (batch_turn), start_line, end_line, surfaced_by, bytes_read}`.
    3. Wrap in BLE001 catch (any failure → WARNING, don't crash loop).
  - Add helper `declare_gold_files(self, paths: list[str])` (sets `_gold_files`).
  - Add helper `note_search_results(self, paths: list[str])` which sets `self.last_search_results = set(paths)` and `self.last_search_turn = self.batch_turn` (called by fs_search handler).
- path: `src/fa/inner_loop/loop.py`
  - At the start of each batch iteration inside `run_session`'s `for batch in batches:` loop (BEFORE dispatching, AFTER the iteration-cap break check):
    1. Increment `state.batch_turn += 1`.
    2. Clear `state.last_search_results = set()` (v2.1 G-8: prevents cross-turn stale attribution — any fs_read_file that was NOT surfaced by THIS batch's fs_search gets `surfaced_by="direct_reference"`).
- path: `src/fa/inner_loop/tools/read_file.py`
  - After a successful file read (where the tool returns file content), call `session.add_read(rel_path, start_line=start, end_line=end, surfaced_by=source, bytes_read=len(content))`. Compute `source` as:
    - `if session.batch_turn == session.last_search_turn and rel_path in session.last_search_results: source = "search_result"`
    - else: `source = "direct_reference"`
    (Artifact-index source requires cross-tool tracking of fs_blackboard_query results; deferred — those reads currently classify as `direct_reference` which is correct-at-some-granularity.)
- path: `src/fa/inner_loop/tools/fs_search.py`
  - On successful search result, call `session.note_search_results([file["path"] for file in result.get("files", [])] + ...)` for matches/regions modes too — essentially all paths returned in this search result.

**Do:**
1. Write C1 test `test_file_read_event_emitted`: invoke fs_read_file on a real file, assert EventLog has a `file_read` event with correct path, turn, start_line, end_line.
2. Write C1 test `test_surfaced_by_search_result`: invoke fs_search (returns file X), then fs_read_file(path=X) → the file_read event has surfaced_by="search_result".
3. Write C1 test `test_surfaced_by_direct`: invoke fs_read_file without a preceding fs_search for that path → surfaced_by="direct_reference".

**Do-not:**
- Do not change the existing `transaction.add_read` semantics (write-set tracking for mutation_guard still works).
- Do not fire a file_read event for failed/denied reads.

**Exit criteria:**
- [ ] T14 tests pass.
- [ ] Kill-check T14: remove event emission → test fails.

---

#### Step S15: fs_exploration_metrics tool

**Traces-to:** CT-4
**Depends-on:** S14
**Target liveness:** L0→L3

**Edits:**
- path: `src/fa/inner_loop/tools/fs_exploration_metrics.py` (NEW)
  - Build ToolSpec per CT-4.
  - Computation of acc@k / FUH reads `file_read` events from EventLog; CtxEff reads transaction.read_set/write_set.
- path: `src/fa/inner_loop/tools/__init__.py` and `profiles.py` — register for all non-verifier roles (read-only, low-risk; useful for researcher/planner/implementer). Verifier stays bash-only.
- path: `src/fa/inner_loop/tool_names.py` — add `"fs_exploration_metrics"` to the TOOL_NAMES frozenset NOW (its ToolSpec file is being added in this same patch, so `test_map_covers_all_tool_spec_names` will pass). *(v2.1 G-1: this is the correct slice to add the name, not S1.)*

**Do:**
1. Implement metrics computation as a standalone function `compute_metrics(log: EventLog, txn: Transaction, gold_files: set[str]|None) -> ExplorationMetrics` so it's unit-testable without the ToolSpec layer.
2. Write C1 tests:
   - Seed EventLog with a synthetic sequence (3 searches, reads of [A, B, gold.py, C, D]), assert acc@1=0, acc@5=1, FUH=3.
   - CtxEff: write_set contains gold.py; CtxEff = size(gold.py)/(size A+size B+size gold+size C+size D).
   - With no gold_files: metrics return nulls for acc/FUH and a note.
3. Register as a read-only, parallel-safe tool (add to _PARALLEL_SAFE_TOOLS in loop.py — it doesn't mutate state except on reset=True, which is a rare operator action; we can mark it parallel-safe because reads are safe).

**Exit criteria:**
- [ ] T15 tests pass.
- [ ] Kill-check: hard-code acc_at_k to zeros → test fails.
- [ ] Tool wired in all profiles.

---

#### Step S16: Wire + verify + patch S15

**Do:**
1. Generate patch `/home/user/s15-exploration-telemetry.patch`.
2. Run full gate: `git apply --check`, `py_compile`, `ruff`, `mypy`, `pytest tests/test_fs_search.py tests/test_file_read_event.py tests/test_exploration_metrics.py`.
3. Run full `pytest tests/` to ensure no regressions.

**Exit criteria:**
- [ ] Gate green; patch ready.
- [ ] S15 LIVE-PATH PROOF: root=run_session, matrix=A (default), test=test_exploration_metrics_live (session with search→read→write pattern; metrics show non-null acc/FUH when gold declared), oracle=acc@5=1.0, kill-check=see T15.

---

### Slice S16 — Python call-graph index + fs_reach (G4)

S16 patch applies after S14b.1; independent of S14b.2 and S15 (can ship in any order relative to them, after S14b.1).

---

#### Step S17: Confirm Q-AST scope decision (RESOLVED)

**Traces-to:** CT-5
**Depends-on:** none (decision locked 2026-08-10)
**Decision (per operator):** Narrow scope — index `ast.FunctionDef` and `ast.AsyncFunctionDef` only in v1, plus their direct `ast.Call` children. No ClassDef, no dataclass fields, no import targets in v1 (kinds: `"function"`, `"method"`, plus `"doc_anchor"` for S17). Schema already reserves a `kind` column so extending to `"class"` later is a backward-compatible additive migration.
**Action:** Proceed to S18.

---

#### Step S18: Structural index module

**Traces-to:** CT-5 (producer)
**Depends-on:** S3 (safe walker — reused), Q-AST decision
**Target liveness:** L0→L2 (module exists; no tool yet)

**Edit:**
- path: `src/fa/memory/structural_index.py` (NEW)
- symbol: `StructuralIndex`
- change:
  - `__init__(db_path: Path)`: opens DB, creates tables per §2.2 schema if not exist.
  - `ensure_indexed(root: Path, *, include_tests: bool = False) -> StructIndexStats`: uses `iter_searchable_files` (from S3) with patterns=("*.py",); per file:
    1. read bytes, compute file_hash (sha256[:24]).
    2. if struct_meta has matching file_hash → skip.
    3. try `ast.parse(source)`; on SyntaxError: WARNING, skip.
    4. walk tree:
       - (narrow scope per Q-AST): for each `ast.FunctionDef`/`ast.AsyncFunctionDef` at any nesting level:
         - compute qualname (join enclosing class/function names with ".");
         - extract args (args.args[i].arg for i in range(len(args.args)));
         - extract docstring (ast.get_docstring, first line, capped at 400 chars);
         - insert into `symbols` (sym_id = sha256(rel+":"+qualname)[:16], kind="function"/"method" depending on whether enclosed by a ClassDef).
         - walk body for `ast.Call` nodes:
           - resolve callee name best-effort (see below).
           - insert into `calls` (caller_sym_id = this function, callee_sym_id = resolved or "<unresolved>:<name>", call_line = call.lineno).
  - Callee resolution heuristic (best-effort, deliberately conservative):
    - If call.func is `ast.Name(id=foo)`: look up `foo` among in-file symbols (same-file function/class defined earlier); if found → sym_id; else → `<unresolved>:foo`.
    - If call.func is `ast.Attribute(value=ast.Name(id=self), attr=foo)`: look for `foo` in same-class methods (enclosing ClassDef); if found → sym_id; else → `<unresolved>:self.foo`.
    - If call.func is `ast.Attribute(value=ast.Name(id=cls), attr=foo)` where cls is an imported alias or known class name in this file: try to resolve against imported modules tracked during the walk (we do simple import tracking: collect `import X`/`from X import Y` at module top; resolve X.Y or Y to symbols if we've indexed those files? **Decision for v1:** cross-file resolution is not attempted; calls via module/attribute are classified as `<unresolved>:<base>.<attr>` — this avoids hallucinating edges. Follow-up slices can add import-based resolution once we have metrics.
    - Everything else → `<unresolved>`.
  - A per-file `DELETE FROM symbols WHERE path=?` then `DELETE FROM calls WHERE caller_sym_id IN (SELECT sym_id FROM symbols WHERE path=?)` is run before re-indexing that file (incremental update).
  - Update `struct_meta` on completion per file.
  - `find_symbols(self, name: str, *, kind: str|None, include_tests: bool) -> list[dict]`: LIKE match on qualname suffix (e.g. "build_grep_tool" matches "fa.inner_loop.tools.grep.build_grep_tool"); returns up to 50 candidates ordered by same-as-bonus + name-match proximity.
  - `reachable(self, sym_id: str, direction: str, depth: int, limit: int) -> list[dict]`: BFS on calls table, returns list of {sym_id, path, qualname, kind, line, distance, docstring} ordered by distance then path.

**Do:**
1. Write C0 tests for schema creation, idempotent indexing, symbol extraction on a tiny .py file (one function calling another).
2. Write C0 test for the callee-resolution heuristics (in-file calls resolve; unknown calls become <unresolved>).
3. Write C0 test for incremental update (modify file content; only that file is re-indexed).
4. Write C0 test for syntax-error skip (file with bad syntax doesn't abort whole index).

**Do-not:**
- Do not attempt cross-file symbol resolution in v1 (leave as `<unresolved>`; fs_search already finds text occurrences, which is what CiM shows OpenCode achieves 45% resolve with — competent).
- Do not index third-party/site-packages code (only files under workspace).
- Do not index strings/imports as symbols (narrow scope).

**Exit criteria:**
- [ ] C0 tests pass.
- [ ] `mypy`/`ruff`/`py_compile` pass.
- [ ] Indexing the FA repo (src/fa/ ~100 .py files) completes without errors (manual sanity check).

---

#### Step S19: Lazy index integration

**Traces-to:** CT-5 P14
**Depends-on:** S18
**Do:**
1. In structural_index.py, add a process-local sentinel `_indexed_for_session` (mirrors S14's ArtifactIndexer).
2. `ensure_indexed` returns early with zero stats if already indexed for this process (unless `force=True`).
3. For non-Python repos (detected by: after walking the first 50 candidate files during indexing, zero .py files found), set `self.available = False` and return stats with available=False; fs_reach checks this flag.

**Do-not:**
- Do not index at import time or at session startup (lazy per INV-S14b-*).

**Exit criteria:**
- [ ] Manual test: create a tmpdir with no .py files → `ensure_indexed` returns available=False.

---

#### Step S20: fs_reach ToolSpec

**Traces-to:** CT-6
**Depends-on:** S18, S19
**Target liveness:** L0→L3

**Edits:**
- path: `src/fa/inner_loop/tools/fs_reach.py` (NEW)
  - `build_fs_reach_tool(db_path: Path, workspace_root: Path) -> ToolSpec` per CT-6.
  - Handler:
    1. Parse params (symbol, direction, depth, limit, kind, include_tests).
    2. Validate (per CT-6 errors).
    3. Obtain StructuralIndex (lazy).
    4. Call `ensure_indexed(workspace_root, include_tests=include_tests)`.
    5. If index.available is False → return ok with status="unavailable", reason, detected_languages.
    6. Resolve starting symbol:
       - If symbol starts with `§` → look up doc_anchor by qualname=symbol.
       - Else use `find_symbols(symbol, kind=kind)` and take top match (if multiple, pick shortest qualname = most local; include note listing alternatives).
    7. Run reachable BFS per direction/depth/limit.
    8. Return ToolResult.ok(summary, result=...) per CT-6 OUT shape.
    9. BLE001 catch → ToolResult.fail("reach_failed", ...).
- path: `src/fa/inner_loop/profiles.py`, `tools/__init__.py`, `tool_names.py` — ADD `"fs_reach"` to TOOL_NAMES frozenset here (v2.1 G-1: added in the same patch that creates tools/fs_reach.py), and wire builders/registration into `_build_tool_builders` (profiles.py) and `_register_extra_tools` (tools/__init__.py) for researcher/code-reviewer/implementer/planner (NOT verifier). Also add `"fs_reach"` to `_PARALLEL_SAFE_TOOLS` in loop.py (fs_reach is read-only).

**Do:**
1. Write C1 tests `tests/test_fs_reach.py`:
   - Fixture: a small Python module with a() calls b() calls c() calls d().
   - `fs_reach(symbol="a", direction="down", depth=2)` returns callees b (distance 1) and c (distance 2), not d (depth 3 cut).
   - `fs_reach(symbol="c", direction="up", depth=3)` returns callers b and a.
   - `fs_reach(symbol="nonexistent")` → resolved_to=null, lists candidates.
   - `fs_reach(symbol="x")` on non-Python fixture → status="unavailable", detected_languages includes "javascript" or whatever was detected.
   - `fs_reach(symbol="§I-42")` resolves when anchor exists (co-tested with S17).
   - Kill-check T20: delete BFS depth expansion → test fails.

**Exit criteria:**
- [ ] Tests pass.
- [ ] Tool registered in implementer/planner/researcher/code-reviewer profiles. **Verifier stays bash-only** (per R-3 decision, matches fs_search policy; the verifier use case is single-command PASS/FAIL, not code navigation).
- [ ] _PARALLEL_SAFE_TOOLS updated (add `"fs_reach"`).

---

#### Step S21: Doc updates for S16

**Edits:**
- AGENTS.md: add fs_reach to intent-matrix: "Use fs_reach when you need to find callers or callees of a known function (multi-file navigation). Start with fs_search to find the function by name, then fs_reach to trace relationships."
- knowledge/llms.txt: add fs_reach parameters and example.

---

#### Step S22: Patch S16

**Do:**
1. Generate `/home/user/s16-python-call-graph.patch`.
2. Run full gate: git apply --check, py_compile, ruff, mypy, pytest (fs_search + fs_reach + blackboard tests).
3. Full pytest run to confirm no regressions.

**Exit criteria:**
- [ ] Gate green; patch ready.
- [ ] S16 LIVE-PATH PROOF documented: test=test_fs_reach_live_on_real_repo (runs against FA source tree; fs_reach("build_grep_tool", direction="up") finds build_registry_for_role or _register_extra_tools as caller).

---

### Slice S17 — § code-anchor convention (G5)

S17 patch depends on S16.

---

#### Step S23: Index `§` comment anchors in structural_index.py

**Traces-to:** CT-7, CT-5
**Depends-on:** S18
**Target liveness:** L0→L3

**Edit:**
- path: `src/fa/memory/structural_index.py`
  - Before AST parsing of a .py file, scan lines with regex `r'^#\s*§([A-Za-z0-9_.-]+):\s*(.+)$'` (anchored at line start, allows leading whitespace).
  - For each match, insert into `symbols` with:
    - qualname = `§<id>`
    - kind = "doc_anchor"
    - start_line = end_line = line_number
    - docstring = description (one line, capped at 400)
    - file_hash = same file hash
    - sym_id = sha256(rel+":"+qualname)[:16]
  - Cleanup (DELETE per-path) already handles re-indexing.

**Do:**
1. Write C0 test: a file with `# §I-FOO: does the thing` → structural_index has a doc_anchor symbol with qualname="§I-FOO".
2. Extend fs_reach tests (T23): `fs_reach(symbol="§I-FOO")` resolves to the anchor.
3. Verify fs_search(query="§I-FOO") finds the file via content match (it will naturally; no extra work needed).

**Exit criteria:**
- [ ] T23 passes.
- [ ] Kill-check: remove regex scan → test_fs_reach_anchor fails.

---

#### Step S24: Document the convention

**Edits:**
- path: `AGENTS.md` and `knowledge/llms.txt`: add section on code anchors: format, density rule (≤1 per ~200 lines; not for every function), stability rule (don't rename once referenced; deprecated with suffix then removed).
- path: `knowledge/adr/ADR-11-...` (the existing ADR that defines I-FROZEN markers): update to reference code anchors as a peer mechanism.

**Do:**
1. Add 5-10 seed anchors to FA's own code as examples (DO NOT bulk-annotate):
   - `src/fa/blackboard/blackboard.py` at `detect_conflict` (§I-56-1: append-only write invariant)
   - `src/fa/inner_loop/state.py:add_read` (§I-S15-1: transaction read-set tracking)
   - `src/fa/inner_loop/runtime_limits.py:DEFAULT_MAX_ITERATIONS` (§I-S14b-2: iteration cap constant)
   - `src/fa/inner_loop/loop.py` cap-emit block (§I-S14b-3: cap signal emit)
   - `src/fa/memory/fts_index.py:EXCLUDE_DIRS` (§I-S14b-4: canonical exclude set)
   These are illustrative, not exhaustive; more get added as code is touched in future work.

**Do-not:**
- Do not add anchors to every function or every class — that defeats the purpose (sparse, stable, contract-only).

**Exit criteria:**
- [ ] Doc updates complete.
- [ ] 5–10 seed anchors added; fs_reach resolves each.

---

#### Step S25: Patch S17

**Do:**
1. Generate `/home/user/s17-code-anchors.patch`.
2. Run full gate.

**Exit criteria:**
- [ ] Gate green; patch ready.
- [ ] S17 LIVE-PATH PROOF documented: test=test_fs_reach_seed_anchors (all 5 seed anchors resolvable via fs_reach).

---

## 6. Verification plan (§9)

### 6.1 Per-contract verification (test-class + oracle + kill-check)

| CT# | Test class | Oracle (ranked) | Kill-check target |
|---|---|---|---|
| CT-1 fs_search | C1 (tests/test_fs_search.py, 18+ tests, see S8) | tool result shape + method field + content + ordering | BM25 ORDER BY clause removal |
| CT-2 iteration cap | C1 (tests/test_iteration_cap.py) | StopInfo.point=="iteration_cap" + log event present | StopInfo construction removal |
| CT-3 file_read event | C1 (tests/test_file_read_event.py) | EventLog contains file_read event with expected fields | event emission removal |
| CT-4 fs_exploration_metrics | C1 (tests/test_exploration_metrics.py) | acc@k/FUH/CtxEff numeric values match seeded fixture | hard-code acc@k to zeros |
| CT-5 structural index | C0 + C1 (tests/test_structural_index.py, unit) + C1 via fs_reach | DB rows present, calls edges correct | DROP TABLE calls |
| CT-6 fs_reach | C1 (tests/test_fs_reach.py) | reachable callees/callers with correct distance | BFS expansion removal |
| CT-7 § anchors | C1 (via fs_reach tests, separate anchor test) | doc_anchor symbols present and resolvable | regex anchor extraction removal |

### 6.2 C3 (security/adversarial) tests

| ID | Test | Target invariant |
|---|---|---|
| T-SEC1 | path escape `../../../etc` | CT-SEC1 |
| T-SEC2 | symlink to outside root | INV-S14b-1, CT-SEC2 |
| T-SEC3 | context_lines=1000 → fail | CT-SEC3 |
| T-SEC4 | limit=10000 → clamped or fail | CT-SEC3 |
| T-SEC5 | regex catastrophic backtracking risk bounded by max_file_size (doc'd as residual risk; add a test with a 1KB file and a tricky regex, must complete in <200ms) | CT-SEC4 |

### 6.3 Static gates (per-patch; apply to each S14b.x patch before ship)

- `python3 -m py_compile <all changed .py files>` — exit 0
- `ruff check src/ tests/` — "All checks passed"
- `mypy <changed files>` — 0 errors in new/changed files (pre-existing stub warnings elsewhere are NOT in scope)
- `git apply --check <patch>` — clean apply on fresh clone with S14 applied
- `PYTHONPATH=src python3 -m pytest <focused tests>` — green
- `PYTHONPATH=src python3 -m pytest tests/` — pre-existing failures unchanged; no new failures

### 6.4 LIVE-PATH PROOF blocks (one per slice; collected)

**S14b.1:** root = run_session (implementer profile), matrix = A (default config), test = `tests/test_fs_search.py::test_fs_search_live_end_to_end`, oracle = ToolResult with method="fts5_bm25" and returned>0, kill-check = remove BM25 ORDER BY → test fails, producer = fs_search.py:handler, consumer = LLM-side result consumption (asserted in test via shape), paths-covered = P1+P2 (index+happy search); other paths have individual tests, efficiency <50ms after first call.

**S14b.2:** root = run_session (role=implementer, default limits), matrix = A, test = `tests/test_iteration_cap.py::test_cap_end_to_end`, oracle = SessionRun.stop.point=="iteration_cap" with used=40, kill-check = remove StopInfo construction → test fails, producer = loop.py run_session, consumer = CLI renderer (exercised via existing StopInfo rendering path), paths-covered = P8-P10, efficiency = no overhead.

**S15:** root = run_session (implementer), matrix = A, test = `tests/test_exploration_metrics.py::test_metrics_live_session`, oracle = acc@5=1.0 on seeded gold, kill-check = hard-code acc@k to zeros → test fails, producer = read_file.py + state.add_read, consumer = fs_exploration_metrics tool, paths-covered = P11-P13.

**S16:** root = run_session (implementer), matrix = A, test = `tests/test_fs_reach.py::test_reach_live_on_fa_repo` (runs against actual FA source), oracle = fs_reach("build_grep_tool", direction="up") returns build_registry_for_role or _register_extra_tools as a caller, kill-check = remove calls edges for that path → test returns empty list, producer = structural_index + fs_reach, consumer = LLM via ToolResult, paths-covered = P14-P16.

**S17:** root = structural_index (construction), matrix = A, test = `tests/test_fs_reach.py::test_seed_anchors_resolve`, oracle = all seed anchors resolve to correct file/line, kill-check = remove regex scan → anchors missing, producer = structural_index anchor extractor, consumer = fs_reach + fs_search.

---

## 7. Risks, rollback, open questions (§10)

### RISKS

| RK# | Risk | Likelihood | Impact | Mitigation | How detected |
|---|---|---|---|---|---|
| R1 | FTS5 not available in Python's sqlite3 | Low (we tested it works in sandbox; FTS5 is part of stdlib sqlite3 since Python 3.6+) | High (BM25 path broken) | Fallback chain P3/P4 (python walk) always present; tool works without BM25, just unordered | test_fs_search_python_walk_fallback simulates missing FTS |
| R2 | BM25 + trigram two-table index gets out of sync on incremental updates | Med | Med | Per-file DELETE+INSERT for both tables in same transaction; test_idempotent_index verifies | test_fs_search_idempotent_index |
| R3 | AST call graph has false edges (dynamic calls resolved incorrectly) | High (dynamic Python is hard) | Med | Conservative heuristic: resolve only in-file and self.foo; everything else <unresolved>. No hallucinated cross-file edges in v1. | test_fs_reach_no_cross_file_hallucination (asserts <unresolved> count reported honestly) |
| R4 | Structural index slows down first fs_reach call on large repos | Low for FA (~100 .py files); Med for larger repos | Low | Lazy; bounded by file count; index is persistent for session duration (paid once); non-Python repos skip fast | Manual timing sanity check during dev; doc'd performance target <3s for FA repo |
| R5 | `~/.fa/config.yaml` is malformed YAML and crashes loader | Low | Low (would break startup) | BLE001 catch around yaml.safe_load; WARNING log, defaults used | test_config_malformed_yaml |
| R6 | Removing fs_grep/fs_instant_grep/fs_glob breaks existing agent sessions / prompt cache | Med (for in-flight sessions) | Med | S14b patch is a single atomic change; after deploy, operator restarts long-running sessions; subagent prompts updated atomically; no cross-session state held that references old names | N/A (deployment coordination) |
| R7 | Per-file regex search under regex mode is slow on large files | Med | Low | max_file_size cap bounds input; can add per-file timeout in follow-up if observed | T-SEC5 timing test |
| R8 | file_read events add write overhead to EventLog (SQLite INSERT per read) | Med | Low (inserts are fast; ~0.1ms each in WAL mode; a session has at most hundreds of reads) | Benchmark in test; if slow, batch writes (deferred to follow-up) | Timing in test_file_read_event_perf |
| R9 | The §-anchor convention is adopted inconsistently, leading to drift | High (process problem) | Low | doc-maintenance skill extends cross-ref check; seed anchors show the pattern; doc emphasizes sparse/stable | Future doc-maintenance test (out of scope here) |

### ROLLBACK

Each slice is a separate patch. Rollback = `git revert` the slice's commit (or `git checkout` the prior state of the changed files). There are no irreversible data migrations:
- `.fa/fts.db` is per-session; deleting it causes the new indexer to rebuild on next call (safe). If rolling back to pre-S14b.1, old InstantGrepIndex will simply see a DB it doesn't understand? Actually pre-S14b.1 code expects `files_fts` (trigram) which still exists; the additional bm25 table is ignored. So forward/backward DB compatibility is maintained for one cycle. (Pre-S14b.1 instant_grep uses only `files_fts`.)
- `.fa/structural.db` is new; if S16 is rolled back, the file is harmlessly ignored (no consumer).
- `~/.fa/config.yaml` is additive; pre-S14b.2 code ignores the file.
- EventLog schema changes are additive (one new event kind); older code that parses EventLog will simply see an unknown kind (current log readers don't filter by kind allowlist; verified by reading observability.py — it uses substring/kind-explicit filters, unknown kinds pass through safely).

Feature flags for emergency disable:
- If fs_search causes issues in production: register a temporary alias from fs_grep/fs_instant_grep/fs_glob → fs_search with mode defaults (we plan NOT to ship this, but it's a 10-line hot-fix if needed). Better: operator can pin to pre-S14b.1 commit and re-deploy.

### OPEN QUESTIONS

**BLOCKING (must be answered before S16 implementation starts):**

- **Q-AST (scope of call-graph symbols):** RESOLVED 2026-08-10 = **narrow** (functions/methods + direct calls only; classes/dataclass fields deferred). See §5 Step S17 default; schema uses kind="function"/"method" only in v1; kind="class" is reserved for future additive migration.

**NON-BLOCKING (defaults recorded; executor proceeds unless told otherwise):**

- **Q1:** Should S14b.1 implement BM25 with two-table hybrid? Default: **yes** (matches Q1 operator answer "BM25 в S14b сразу - принято").
- **Q2:** Should `fa reindex` CLI verb be added to force reindex? Default: **no** (lazy auto-index is sufficient; can add CLI verb later as UX polish).
- **Q3:** Should fs_search's `types` parameter actually filter by blackboard artifact type in S14b.1? Default: **no** (validated, ignored with note; blackboard_query remains the tool for artifact lookup; future slice can wire cross-search if needed).
- **Q4:** Should fs_reach be available to verifier role? Default: **no** (verifier stays bash-only to preserve its minimal "single command → PASS/FAIL" contract; verifier subagents that need navigation can be upgraded to code-reviewer/researcher role rather than expanding verifier's tool surface).
- **Q5:** Should the structural DB live in `.fa/structural.db` (separate) or be added as tables to `.fa/fts.db`? Default: **separate** (different update cadence, different rebuild triggers, keeps FTS code simple).
- **Q6:** Should the batch counter increment be per-batch or per-tool-call? Default: **per-batch** (v2.1 G-3 resolved by adding `batch_turn`; the existing `state.turn` per-tool-call counter is preserved as-is). This can be refined later.

---

## 8. Research-note disposition (§11a)

The plan draws on `knowledge/research/swe-explore-code-isnt-memory-architectural-deepdive-2026-08-10.md`. Every substantive suggestion is evaluated below per plan-authoring skill requirement.

| RN# | Note item | Verdict | Why (codebase fit / kill-checkable / invariant conflict?) | Anchor |
|---|---|---|---|---|
| SWE-Explore: iterative agentic search required | One-shot retrieval is ~random; need iterative fs_search+read_file | Accept (already the case; this plan just makes search unified/ranked) | Agents already loop; better search makes each iteration count | S14b.1 |
| SWE-Explore: line-level recall is bottleneck (Recℓ ~0.14-0.19) | fs_search regions mode reduces lines-per-useful-hit | Accept | Regions output_mode groups adjacent matches into windows; aligns with read_file range capability | S4 (output_mode=regions) |
| SWE-Explore: CtxEff r=0.95, Rec@100 ρ=0.85, FUH r=0.93 | Instrument these exact metrics | Accept | S15 implements all three (CtxEff, acc@k, FUH) using existing EventLog + transaction read/write sets | S14–S16 |
| SWE-Explore: CoSIL graph-walk subagent | Specialized subagent that walks call graph iteratively | Defer to P2 | Research-grade; we first give the agent a direct fs_reach tool (deterministic) which is smaller and easier to verify; if S15 metrics show agents getting lost in graph walks, revisit CoSIL | Backlog |
| CiM: three legs (lexical/vector/graph) | BM25 lexical + Python AST graph + embeddings | Partially accept | Lexical (BM25) in S14b.1, graph in S16, **vector leg rejected** for v1 — papers show no standalone benefit without graph; embeddings add ML deps/non-determinism; defer until S15 metrics show lexical+graph systematically failing on synonym searches | S14b.1 lexical, S16 graph; vector leg → backlog |
| CiM: acc@5 +44.3% → 84.5% with structural index; multi-file +46.4pp | Strongest evidence for call graph | Accept (motivation for S16) | CiM's finding on ≥3-file tasks is the primary reason for fs_reach; effect size is large enough to justify stdlib-AST implementation | S16 |
| CiM: OpenCode (ripgrep+read only) achieves 45.3% resolve | SWE-bench baseline without structural index | Accept (floor estimate) | Tells us fs_search BM25 alone is ~45% on foreign repos; fs_reach lifts that for Python; non-Python repos stay at ~45% | §0 non-goals |
| CiM: View B scoring (surfaced ≠ appeared-in-result-list) | surfaced_by tracking must require a read, not just result-list presence | Accept | S15's surfaced_by="search_result" is only set when a file is actually read after appearing in a search result (matches View B) | S14–S15 |
| CiM: Merkle-diff incremental updates | Per-file hashed, update only changed files | Accept (already pattern in fts_index.py and artifact_index.py) | Both FTS and structural indexes use mtime/hash incremental updates | S2, S18 |
| Paper suggestion: more_like_this (similar_to param) | Find files similar to a given file via BM25 | Defer | Nice-to-have; can be added as fs_search param in follow-up (treat document-as-query); not part of minimal-mechanism G1 | Backlog |
| Earlier proposal: P0-3 bash grep ban | Hard deny of grep/rg via fs_run_bash | **Backlog** per operator explicit decision | Operator said: "Интересно, но лучше в беклог"; noted but not in this plan | Backlog |
| Earlier proposal: P1-4 fs_search absorbs three tools | Unified discovery tool | Accept | This is S14b.1 core | S1-S9 |
| Earlier proposal: pre-commit file-length gate | Files >~1000 lines → fail pre-commit | Defer | Good hygiene but orthogonal to search/memory; file as separate hygiene task (does not need to ride this plan) | Backlog |
| Earlier proposal: stable H1/H2/H3 markdown slugs | Predictable doc anchors | Mostly already done | Quick check + doc-maintenance skill update; not code, can roll into S17 doc updates | S24 (docs only) |
| Earlier proposal: more_like_this (similar_to param for fs_search) | document-as-query search | Defer (see above) | Backlog | Backlog |

---

## 9. Definition of Done (plan-level, §11.3)

**STATE before:**
- Three overlapping search tools; no ranking; no call graph; silent iteration cap; reads tracked at file-level only; no § anchors in code; no exploration metrics.

**STATE after (all slices shipped):**
- Single discovery tool `fs_search` with 4 output modes, BM25 ranking, substring and python-walk fallbacks, token-efficient defaults, security-bounded.
- Observable iteration cap: StopInfo + log event; per-profile defaults; `~/.fa/config.yaml` override.
- Extended telemetry: `file_read` events with turn, line range, surfaced_by; `fs_exploration_metrics` computes acc@k/FUH/CtxEff.
- Python call-graph index at `.fa/structural.db` (stdlib ast, incremental, fail-degraded; Python-only; non-Python repos return "unavailable"); `fs_reach` tool navigates caller/callee relationships.
- Documented `§<id>:` code-anchor convention with 5-10 seed anchors, indexed into structural DB.

**ARTIFACTS created/modified/deleted:**

Created:
- `src/fa/memory/search_index.py` (NEW, ~500 LOC)
- `src/fa/memory/structural_index.py` (NEW, ~400 LOC)
- `src/fa/inner_loop/tools/fs_search.py` (NEW, ~400 LOC)
- `src/fa/inner_loop/tools/fs_reach.py` (NEW, ~250 LOC)
- `src/fa/inner_loop/tools/fs_exploration_metrics.py` (NEW, ~150 LOC)
- `tests/test_fs_search.py` (NEW, ~400 LOC, 18+ tests)
- `tests/test_iteration_cap.py` (NEW, ~150 LOC)
- `tests/test_file_read_event.py` (NEW, ~100 LOC)
- `tests/test_exploration_metrics.py` (NEW, ~200 LOC)
- `tests/test_structural_index.py` (NEW, ~200 LOC)
- `tests/test_fs_reach.py` (NEW, ~300 LOC)
- `tests/test_safe_walk.py` (NEW, ~100 LOC)
- `tests/fixtures/small_repo/...` (NEW, small fixture files)
- 5 patch files at `/home/user/s14b*.patch`, `/home/user/s15-*.patch`, `/home/user/s16-*.patch`, `/home/user/s17-*.patch`
- Plan file: `worklogs/implementation-plans/PLAN-cli-trace-S14b-search-tools-memory-expansion.md` (this file)

Modified:
- `src/fa/inner_loop/tool_names.py` (replace 3 names with 3 new names)
- `src/fa/inner_loop/profiles.py` (tool lists + builders)
- `src/fa/inner_loop/tools/__init__.py` (registration block)
- `src/fa/inner_loop/loop.py` (_PARALLEL_SAFE_TOOLS, iteration cap StopInfo, batch_turn increment + last_search_results reset per batch — v2.1 G-3/G-8)
- `src/fa/inner_loop/state.py` (add_read extension, new fields, EventLog calls)
- `src/fa/inner_loop/tools/read_file.py` (fire file_read event)
- `src/fa/inner_loop/runtime_limits.py` (per-profile defaults + YAML config loader)
- `src/fa/inner_loop/subagent_prompts.py` (tool references + fallback narrative)
- `src/fa/inner_loop/subagent_runner.py` (comment updates + any code references)
- `AGENTS.md` (intent-matrix updated; fs_search/fs_reach docs; §-anchor convention)
- `knowledge/llms.txt` (tool docs updated)
- 5-10 existing Python files (seed `# §` anchors)

Deleted:
- `src/fa/inner_loop/tools/grep.py`
- `src/fa/inner_loop/tools/instant_grep.py`
- `src/fa/inner_loop/tools/glob.py`
  (Note: `src/fa/memory/fts_index.py`'s InstantGrepIndex class is preserved for one release cycle with a DeprecationWarning; all in-tree callers (subagent_prompts._get_fts_files, tool registration) are migrated to SearchIndex. Full removal is a dedicated cleanup follow-up after operator confirms no external scripts rely on it.)

**CONTRACTS status (end-state):**

| CT# | Contract | Target status |
|---|---|---|
| CT-1 | fs_search signal | VERIFIED (producer + consumer + kill-check) |
| CT-2 | Iteration cap signal | VERIFIED |
| CT-3 | file_read telemetry event | VERIFIED |
| CT-4 | fs_exploration_metrics | VERIFIED |
| CT-5 | Structural index schema | VERIFIED |
| CT-6 | fs_reach tool | VERIFIED |
| CT-7 | §-anchor convention | VERIFIED (indexer; doc-enforced going forward) |
| INV-S14b-1..7 | Invariants | VERIFIED by dedicated tests |
| CT-SEC1..4 | Security contracts | VERIFIED by C3 tests |

**Plan is DONE when:**
1. All 5 slices' patches apply cleanly on top of S14 on `origin/main`.
2. Each slice passes its static + test gate.
3. LIVE-PATH PROOF blocks execute green for all five slices.
4. Anti-theater checklist (§10) is all PASS.
5. No regressions to S14 (artifact index + blackboard_query) — its 15+2 tests still pass.
6. Pre-existing baseline failures (providers_chain, pyrefly, s10a/b, s12, s5_state_root) are unchanged.
7. Doc updates (AGENTS.md, llms.txt) accurately reflect tools and conventions.

---

## 10. Anti-theater + READY gate (§11.2, §11.4)

Self-check against the plan-authoring checklist:

- [x] **Every referenced symbol verified via preflight or marked NEW** — grep-verified all file:line references to existing code; new modules marked NEW.
- [x] **Every G# maps to ≥1 CT# and ≥1 S# and ≥1 verification** — G1→CT-1→S1-S9→T1-T6+SEC; G2→CT-2→S10-S13→T10-T12; G3→CT-3,CT-4→S14-S16→T14-T15; G4→CT-5,CT-6→S17-S22→T19-T21; G5→CT-7→S23-S25→T23; G6 (cross-cutting) enforced across all slices.
- [x] **Every signal CT# has BOTH producer and consumer, or explicit defer** — CT-1..CT-7 all have both sides named.
- [x] **Every kill-check targets the PRODUCER, never the consumer alone** — verified per CT# kill-check.
- [x] **Path inventory (§4.1) has no uncovered path without explicit non-goal** — P1-P17 all covered.
- [x] **Matrix (§4.2) has ≥1 covering step per row or explicit N/A** — all rows A-F, P-r/P-c/P-s/P-t/P-x have named T#.
- [x] **Dual-write channels verified consistent** — StopInfo + EventLog dual-wire specified in CT-2 (same branch, same as existing pattern); CT-3 single-write (only EventLog, transaction.add_read preserved as existing).
- [x] **Fixtures/types in verification plan are honest (real types at wiring boundaries)** — C1 tests build real ToolSpecs/registries; mocks only for Registry dispatch where unavoidable; C0 tests exercise helpers directly.
- [x] **No vague verbs ("handle", "support", "integrate", "optimize") without a concrete mechanism attached** — all steps have explicit edits, named functions, specific SQL/Python constructs.
- [x] **Assumptions are labeled ASSUMPTION** — non-blocking Q1-Q6 carry stated defaults; Q-AST labeled BLOCKING.
- [x] **Security contracts have ≥1 adversarial case (C3)** — T-SEC1 through T-SEC5.
- [x] **All ID references resolve (G#, GAP#, CT#, A#, P#, M#, S#, T#, Q#, RN#, RK#)** — cross-checked; each ID referenced is defined in this document.
- [x] **Depth (P2) declared after preflight and matches actual scope** — cross-module, multi-slice, migration + new DB + new tools + telemetry + docs = P2.
- [x] **Executive intent, non-goals, current/target state all concrete** — §0 and §2 present and specific.
- [x] **All applicable contract subtypes (§6) present or explicitly N/A** — function/signal/data/invariant/security contracts all written where applicable.
- [x] **BLOCKING open question set is EMPTY** — Q-AST resolved (narrow, functions/methods only); Q1 resolved by operator (BM25 yes); Q2-Q6 non-blocking with stated defaults.

**Status:** READY. All 13 anti-theater gates hold. No blocking questions. Slices S14b.1 → S14b.2, S15 (order-independent after S14b.1) → S16 → S17 may proceed.

---

## 11. Artifacts inventory

| Artifact | Path | Action | Owner S# |
|---|---|---|---|
| Search index (BM25+trigram+walk) | `src/fa/memory/search_index.py` | add | S2, S3 |
| Safe file iterator | `src/fa/memory/search_index.py` (or `_safe_walk.py`) | add | S3 |
| Structural index (AST call-graph) | `src/fa/memory/structural_index.py` | add | S18, S19, S23 |
| fs_search tool | `src/fa/inner_loop/tools/fs_search.py` | add | S4 |
| fs_reach tool | `src/fa/inner_loop/tools/fs_reach.py` | add | S20 |
| fs_exploration_metrics tool | `src/fa/inner_loop/tools/fs_exploration_metrics.py` | add | S15 |
| Tool names set | `src/fa/inner_loop/tool_names.py` | edit | S1 |
| Profile wiring | `src/fa/inner_loop/profiles.py` | edit | S5, S11, S20 |
| Tool registration | `src/fa/inner_loop/tools/__init__.py` | edit | S5, S15, S20 |
| Parallel-safe set | `src/fa/inner_loop/loop.py` | edit | S5, S10 |
| Loop cap signal | `src/fa/inner_loop/loop.py` | edit | S10 |
| Telemetry (add_read) | `src/fa/inner_loop/state.py` | edit | S14 |
| read_file event emission | `src/fa/inner_loop/tools/read_file.py` | edit | S14 |
| Runtime limits (profiles + YAML) | `src/fa/inner_loop/runtime_limits.py` | edit | S11, S12 |
| Subagent prompts | `src/fa/inner_loop/subagent_prompts.py` | edit | S6 |
| Subagent runner comments | `src/fa/inner_loop/subagent_runner.py` | edit | S6 |
| fs_search saves result paths | `src/fa/inner_loop/tools/fs_search.py` | edit | S14 |
| Old grep tool | `src/fa/inner_loop/tools/grep.py` | delete | S5 |
| Old instant_grep tool | `src/fa/inner_loop/tools/instant_grep.py` | delete | S5 |
| Old glob tool | `src/fa/inner_loop/tools/glob.py` | delete | S5 |
| AGENTS.md docs | `AGENTS.md` | edit | S7, S21, S24 |
| llms.txt docs | `knowledge/llms.txt` | edit | S7, S21, S24 |
| Seed § anchors | 5-10 files in `src/fa/` | edit | S24 |
| fs_search tests | `tests/test_fs_search.py` | add | S8 |
| Safe-walk tests | `tests/test_safe_walk.py` | add | S3, S8 |
| Iteration cap tests | `tests/test_iteration_cap.py` | add | S10, S13 |
| File-read event tests | `tests/test_file_read_event.py` | add | S14 |
| Exploration metrics tests | `tests/test_exploration_metrics.py` | add | S15, S16 |
| Structural index tests | `tests/test_structural_index.py` | add | S18 |
| fs_reach tests | `tests/test_fs_reach.py` | add | S20, S22, S23, S25 |
| Small repo fixture | `tests/fixtures/small_repo/` | add | S8 |
| Patch for S14b.1 | `/home/user/s14b1-fs-search-unification.patch` | add | S9 |
| Patch for S14b.2 | `/home/user/s14b2-iteration-cap.patch` | add | S13 |
| Patch for S15 | `/home/user/s15-exploration-telemetry.patch` | add | S16 |
| Patch for S16 | `/home/user/s16-python-call-graph.patch` | add | S22 |
| Patch for S17 | `/home/user/s17-code-anchors.patch` | add | S25 |
| This plan | `worklogs/implementation-plans/PLAN-cli-trace-S14b-search-tools-memory-expansion.md` | add | (this commit) |

---

## 13. Escalation table (per plan-authoring skill §13)

| Situation | Action |
|---|---|
| Symbol referenced but not verified | STOP; grep/read it; mark NEW if absent. (Preflight executed — all symbols verified.) |
| "Handle X properly" with no mechanism | Rewrite concretely. (Audited; all steps have concrete mechanisms.) |
| Signal has producer no consumer (or reverse) | Complete it, or defer as stated non-goal. (All CTs have both sides.) |
| No falsifiable DoD for a step | Add State/Artifact/Contract check. (Every step has exit criteria with concrete checks.) |
| "Add tests" with no oracle/class named | Map to §9 explicitly. (Done per step.) |
| >1 call site exists, only one planned | Run §7.1 path inventory, add steps. (P1-P17 covered.) |
| Matrix named but rows uncovered | Add step/test per row. (§4.2 all rows have T#.) |
| Two write-channels, only one path covered | Add dual-write check. (CT-2 has explicit dual-write.) |
| Scope grew past declared depth mid-write | STOP; re-declare depth. (Depth P2 declared up-front.) |
| No rollback/non-goals on P2+ plan | Add before READY. (§7 has rollback; §1.6 has non-goals.) |
| Notes conflict with code/ADR | Code+ADR win; RN# verdict = Reject/Rewrite. (§8 disposition table.) |
| Security claim, no adversarial case | Add C3 case. (T-SEC1..T-SEC5 added.) |
| Executor needs a product/policy decision | → BLOCKING Q#, never silently decided. (Q-AST raised.) |
| Dangling ID reference found | Fix before READY. (Cross-checked.) |

---

## 14. Operator handoff (for the executing agent)

- **Prerequisite:** S14 patch (`s14-blackboard-artifact-index.patch`) must be applied and live before S14b patches. S14 patch SHA-256 is `7afa9d4857e1a9378dd531c7fafd88ddb96e0263a74337a351855fd857cb89c3` (per summary).
- **Execution order:** S14b.1 → (S14b.2, S15 either order) → S16 (blocked pending Q-AST answer; if answer is "default" proceed with narrow functions/methods only) → S17.
- **Per-slice workflow:** for each patch, apply to fresh clone with prior slices applied; run gate sequence per S9; only commit after gate green; operator runs `fa update` and verifies smoke tests before next slice.
- **Languages:** code/docs/strings in English (per project convention); operator chat in Russian.
- **Hard rules (per operator mandate):** no `# noqa` without approval (BLE001 is the pre-approved exception for fail-degraded catch-alls); no bash scripts without `bash -n` validation; no Python heredocs without py_compile; always state source-verified behavior, plan contract, allowed file list, and STOP if blocking question unresolved.
- **On Q-AST:** If operator has not answered by the time executor reaches S17, STOP and escalate (do not guess); the first three slices (S14b.1, S14b.2, S15) and S17 docs+seeds can still ship.
- **Smoke test after each slice deploy:** similar to S14's smoke — start a fresh `fa` session, exercise the new tool/capability, confirm correct output and no console errors.

Plan ends.
