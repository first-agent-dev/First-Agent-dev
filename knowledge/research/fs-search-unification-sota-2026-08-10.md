# Unified `fs_search` — SOTA Design Research (2026-08-10)

**Status:** research, pre-implementation. Inputs = verified state of current tooling (post-S14) + Cursor / Claude Code / Aider / Cline public tool-surface knowledge (late-2026). Goal: define the single content-search tool that replaces `fs_instant_grep` + `fs_grep` (and absorbs the name-only slice of `fs_glob`), leaving exactly 3 discovery tools: `fs_blackboard_query` (registry/memory), `fs_search` (content/name discovery), `fs_read_file` (body fetch).

---

## §1. Current state (source-verified)

| Tool | Backend | Returns | Cost/latency |
|---|---|---|---|
| `fs_instant_grep` | FTS5 trigram → git-ls-files → walk (read-only; no query-time index) | **paths only** | <50ms FTS, fallback linear |
| `fs_grep` | `git grep` subprocess → python streaming | **matches = `{path,line,content}`** | subprocess per call, streaming |
| `fs_glob` | `git ls-files` pattern | **paths only** | ~0ms |
| bash `grep -ril` | ripgrep/grep via PTY | unconstrained text | unbounded tokens, 124-step timeout history |

Pain points:
- Two tools ask «where is substring X?» with overlapping intent but incompatible return shapes → agent calls both, wastes tokens.
- `fs_instant_grep` gives no line numbers/snippets → forces a follow-up `fs_read_file` or `fs_grep` just to see context.
- `fs_grep` has no FTS fast path → on large repos (10k+ files) it's slower than instant_grep even though it returns more.
- Both have `glob`/no-glob inconsistency, different default limits (10 vs 20), different caps (50 vs implicit).
- `fs_glob` is name-only but its job is partially covered by `fs_grep(glob=...)` with any query; the disjoint case is «list files by pattern without substring».
- Raw bash grep escapes all token/limit discipline.

Target: **one** `fs_search`. Agent never types `grep`/`rg`/`find` in bash for discovery.

---

## §2. SOTA reference (late-2026, late-2025 leaks/pubs)

### Claude Code `Grep` (Anthropic, prod since late 2025) [1][3][4][5]
- **Backend:** `ripgrep` subprocess.
- **Parameters:** `pattern` (regex, required), `path?`, `glob?`, `type?` (rg --type), `output_mode` ∈ {`content`, `files_with_matches` (default), `count`}, `-i?`, `-n?` (default true in content), `-A/-B/-C?`, `multiline?`, `head_limit?`.
- **Default `output_mode = files_with_matches`** — i.e. paths-only is the CHEAP default; agent opts-in to content explicitly.
- **Hard rule in system prompt:** «ALWAYS use Grep for search tasks. NEVER invoke grep/rg as a Bash command.»
- Content mode returns lines with numbers + optional context lines. No relevance ranking — ripgrep order.

### Cursor (3.x, mid-2026)
- Three layers: (1) **Instant grep** (FTS5 trigram, <50ms, paths only, same design as our current `fs_instant_grep`), (2) **ripgrep** (Cmd-Shift-F style, line snippets), (3) **@codebase semantic search** (embeddings via Turbopuffer, conceptual matches, returns file ranges to read) [4].
- Cursor defaults to instant-grep for fast narrowing, falls back to semantic when results are poor.
- **Lesson:** keeping a paths-only fast first pass AND snippets has proven value; Cursor does this by stacking TWO tools. We can get the same ergonomics with ONE tool that defaults to paths-only but can opt into snippets.

### ai-grep / AI-grep (open source, late 2025) [2]
- Blends FTS + ripgrep → compact shortlist of **`{path, line range, snippet, relevance score}`** in one call.
- Claimed: -97% input tokens vs grep+read loop.
- **Lesson:** ranked/snippet-first responses cut the grep→read→grep cycle. But requires ranker (BM25 or embeddings).

### Aider / Cline (open source agents)
- Expose `search_files` / `search_file_regex` wrappers around ripgrep; Aider uses a repo-map heuristic + grep; Cline's `search_files` supports both regex and glob and returns matches with line numbers.
- **Lesson:** glob-without-substring («list by pattern») is a genuine distinct query class; best modelled as `pattern=""` with `glob=…` (Claude Code does this implicitly via Glob as a separate tool; but the 2-tool separation there is exactly what we are trying to avoid).

---

## §3. Design decisions for First-Agent `fs_search`

### D3.1 One tool, three output modes (mirrors Claude Code, adds FTS fast path)
`output_mode ∈ {"files", "content", "count"}` — default **`files`** (paths-only, cheapest, token-bounded).

| mode | Returns | Token cost | Use when |
|---|---|---|---|
| `files` (default) | `{path}[]` sorted deterministically, deduped | ~1 token/path | Broad discovery: «which files mention X?» — then `fs_read_file` on the 1–3 that look right. |
| `content` | `{path, line, content, context_before?, context_after?}[]` | ~3–6 tokens/match | You need to see the match inline to decide relevance without a follow-up read. |
| `count` | `{path, count}[]` | negligible | «where is this most concentrated?», «did I introduce new TODOs?». |

**Why default to paths?** (Same choice as Claude Code.)
- Token discipline (the #1 reason `grep -ril` caused 124-step timeouts).
- In the common case the agent only needs to know where to read next.
- FTS fast path naturally returns paths first (the FTS index maps term→rowid→path; fetching line/snippet costs an extra file read per match, which we skip by default).
- Agent can always re-issue the same query with `output_mode="content"` and a tighter `glob`/`path` once it narrows.

### D3.2 Substring by default; regex opt-in
- **Default** search = plain substring (SQL `LIKE`/FTS-matched literally). This matches what our existing tools do and is what agents want 90% of the time.
- `regex: bool = false` → switches the fast-path to `ripgrep`/python-re (FTS5 can't do regex), with streaming fallback; reject pathological patterns with a clear error.
- Rationale: LLM habitually reaches for `.*` and escapes; default literal avoids footguns AND is faster on FTS. Regex is there when needed (log analysis, tokens like `\bfoo\b`).

### D3.3 Glob filter + optional `path` root
- `glob?: string` — ripgrep-style `*.py`, `**/*.tsx`, `knowledge/**/*.md`. FTS path can apply LIKE glob filter on the `path` column; git-grep fallback passes `--glob`.
- `path?: string` — directory/file to narrow (defaults to workspace root).
- **Absorbs `fs_glob`:** list-by-name is `fs_search(pattern="", glob="**/test_*.py")` or equivalently `output_mode="files"` with empty pattern (fast: git-ls-files filter only, no content scan). One semantic: `glob` is ALWAYS the filename filter, regardless of whether content is scanned.

### D3.4 Type filter — integration point for blackboard (deferred)
Future param `artifact_type?: skill|adr|…|file_version|code` — scope search to (a) files whose relpath maps to a blackboard-tracked artifact, or (b) code only. Not in v1; v1 uses `glob`/`path` (e.g. `glob="knowledge/adr/**/*.md"`) for the same effect.

### D3.5 Case sensitivity
`case_sensitive?: bool = false` (default insensitive). Easier for agents; FTS trigram is case-insensitive by default.

### D3.6 Context window control (content mode only)
`context_lines?: int = 0` (alias `-C`); `before_lines?/after_lines?` override symmetric value. Hard cap at 5 lines each direction (prevents a match from dumping the whole file).

### D3.7 Limits — single bounded contract
- `limit?: int` — **default 20 paths / 20 matches / 20 counts** respectively, **hard cap 50**. Over-max silently clamps (same as existing blackboard_query clamp pattern — predictable, no error on over).
- In `content` mode, also `max_total_bytes?: int = 8000` (≈ ~2k tokens) — if the snippets collected would exceed this, we return the first N that fit and set `truncated: true` in the result. This is the hard backstop against a query like "the" dumping everything.

### D3.8 Backend routing (transparent, not a parameter)
```
if pattern == "":
    → git ls-files <glob>                                   (name-only listing; absorbs fs_glob)
elif output_mode == "files" and not regex:
    → FTS5 trigram (read-only) <50ms
    → fallback: git ls-files + streaming substring match (symlink-safe prune)
elif output_mode == "content" and not regex:
    → FTS5 to get candidate paths → read + extract matching line + context (bounded bytes)
    → fallback: git grep -n <pattern> [--glob] -C <N>
    → fallback: streaming walk with per-file line scan
elif regex or mode == "count":
    → git grep -n -c (subprocess) if available
    → fallback: streaming walk + python re (multiline off by default)
```
All three fallbacks respect `.gitignore`, prune excluded dirs (`.fa/`, `node_modules/`, `.venv/`, `__pycache__/`, `.git/`, `sessions/`, `.next/`, `dist/`, `build/` — same EXCLUDE_DIRS that instant_grep uses today), are symlink-safe.

The method used is reported back as `result.method ∈ {"fts5","git_grep","git_ls","python_walk"}` for operator diagnostics (not surfaced to user unless there's a problem).

### D3.9 Result schema (all modes)

Top-level result envelope (same shape as other tools):
```json
{
  "query": "...",
  "regex": false,
  "glob": null,
  "path": ".",
  "output_mode": "files",
  "method": "fts5",
  "limit": 20,
  "returned": 12,
  "truncated": false,
  "total_bytes": 3812,
  "files":    [{"path": "src/...", "match_count": 3}] /* mode=files */,
  "matches":  [{"path": "...", "line": 47, "content": "...",
                "before": ["..."], "after": ["..."]}]   /* mode=content */,
  "counts":   [{"path": "...", "count": 3}]              /* mode=count */
}
```
Only ONE of `files/matches/counts` is present (matches `output_mode`). Each item also includes `match_count` for mode=files (how many hits in that file — cheap from FTS, helps the agent pick which file to open first).

### D3.10 Deterministic ordering (testable, reproducible)
- mode=files: by `match_count desc, path asc`, then `limit`.
- mode=content: by `path asc, line asc`, within limit + byte cap.
- mode=count: by `count desc, path asc`.

This is **not BM25** — BM25 rank belongs to a v2 improvement (see §5). v1 ordering is deterministic and doesn't need embeddings.

### D3.11 Error & edge-case behaviour
- Empty pattern + no glob → error (reject to prevent accidental «list everything», which would return 10k paths). Either give a glob (name-listing intent) or a pattern.
- Zero results → `{files: [], returned:0, truncated:false}` + clear summary; never raises.
- FTS index missing/stale → transparent fallback to git/walk; does NOT auto-build at query time (preserves the FIND-013 read-only guarantee carried by `fs_instant_grep`). Operator builds/refreshes FTS via `fa reindex` (existing verb) — we do not change that lifecycle.
- Binary/mis-encoded files: skipped silently (matches git-grep behaviour); not counted as errors.
- File read error during context-line pull: that file's matches are returned without context, error appended to `errors[]` in the envelope (fail-degraded, matches BLE001 catch-all pattern).

### D3.12 Size: hard limits match existing conventions
- `_MAX_FILE_BYTES = 200_000` (matches artifact_indexer; files larger skipped streaming, reported in `errors[]`).
- FTS walk respects EXCLUDE_DIRS from instant_grep.py (don't rescan .fa, node_modules, .venv, __pycache__, .git, sessions).

### D3.13 Naming
- **Name: `fs_search`** (not `fs_grep`, not `fs_instant_grep`, not `fs_find`). The verb «search» maps to the intent (discovery by content or name); it's also consistent with the sibling family `fs_search / fs_read_file / fs_write_file / fs_edit_file / fs_run_bash / fs_blackboard_query`.
- Legacy names (`fs_instant_grep`, `fs_grep`, `fs_glob`) are **removed** from all profiles in the same PR that ships `fs_search`. We do NOT keep aliases — the harness is internal, versioned with sessions; no external callers.

---

## §4. Tool description for the LLM (verbatim, tuned for intent clarity)

```
fs_search(query, glob?, path?, output_mode="files", limit=20,
          context_lines=0, case_sensitive=false, regex=false)

Find files in the workspace by content substring or name pattern.
- output_mode "files" (default): returns paths + per-file match count. Cheapest.
  Use first; follow up with fs_read_file on the relevant paths.
- output_mode "content": returns matching lines with line numbers and
  optional surrounding context (context_lines, default 0, max 5).
- output_mode "count": returns per-file match counts (for heat-map questions).
- Use glob (e.g. "*.py", "knowledge/**/*.md") to restrict to file type/path.
- path (default ".") narrows the subtree to search.
- regex=true enables regex patterns (slower, literal is default).
- limit (default 20, max 50) caps returned entries; over-max is clamped.
- NEVER invoke grep/rg/find/ag/ack via fs_run_bash for discovery; this tool is
  the only approved content/name search. It respects .gitignore, excludes
  .fa/node_modules/.venv/.git/sessions, and enforces a token budget.
- For type-scoped artifact / mutation history queries (e.g. list all skills,
  see pre/post file snapshots, detect conflicts), use fs_blackboard_query
  instead.
```

That description is ~180 words vs ~40 each for the current two specs combined → **net saving in prompt tokens**, and removes the decision ambiguity.

---

## §5. Deferred out of v1 (future S-slices)

- **BM25/snippet ranking** → needs body stored (either FTS content column or alongside blackboard). Tracked as candidate S15b after this consolidation lands; v1 ordering is deterministic (path + count), which is sufficient when limit ≤ 50 and the agent re-filters by reading.
- **Artifact-aware scope** (`artifact_type=adr` etc.) → requires cross-joining FTS with blackboard logical ids; do after blackboard body-index ships.
- **Semantic/embedding search** → out of scope entirely for the substrate; would be a separate optional tool if ever added, because it pulls in model weight/dependency weight and conflicts with the stdlib-only FTS design.
- **Multiline regex** → can add `multiline: bool` when a real use-case appears; v1 patterns match within a line.

---

## §6. Tests to carry over / add

Carry over (renamed to reference `fs_search`):
- All existing `tests/test_instant_grep_tool.py` assertions (FTS path, fallback to git/walk, respects limit, excluded dirs).
- All existing `tests/test_grep_tool.py` assertions (glob filter, streaming fallback, max_file_size skip, matching lines w/ content).
- All existing `tests/test_glob_tool.py` assertions (empty-pattern + glob = name listing).

New v1 tests:
- T1: default call returns mode=files shape, no matches/counts key, deterministic ordering.
- T2: mode=content returns `{path,line,content,before,after}` with context_lines capped at 5.
- T3: pattern="" + glob="**/*.md" returns .md files; pattern="" without glob → ValueError.
- T4: limit=50 with 200 candidates returns exactly 50 and `truncated=false` (clamped); limit=999 → clamped to 50.
- T5: total_bytes cap truncates content-mode with `truncated=true` and reports `total_bytes`.
- T6: regex=true finds `log.*Error`, regex=false treats dot/literals literally.
- T7: backend selection: method=fts5 for plain substring files-mode, method=git_grep for regex/count, method=git_ls for empty pattern + glob.
- T8: FTS index missing → graceful git-ls/walk fallback, no exception, method reflects fallback.
- T9: EXCLUDE_DIRS (.fa, node_modules, .venv, .git, sessions) pruned in all modes.
- T10: profile registration: researcher/code-reviewer/implementer/planner all list `fs_search`; none list `fs_grep`/`fs_instant_grep`/`fs_glob`.
- T11: AGENTS.md + llms.txt contain the new tool name and do NOT mention raw `grep -ril`/`rg` as primary; legacy names appear only in a deprecation note on first rollout.
- T12: `fs_blackboard_query` is unchanged; smoke-test 51 blackboard tests still pass.

---

## §8. Operator decisions (locked 2026-08-10)

- **Q1 (pre-decided):** One tool `fs_search` replaces `fs_instant_grep` + `fs_grep`. Raw `grep`/`rg`/`find` in bash is verboten for discovery.
- **Q2 (glob disposition):** `fs_glob` is **absorbed** into `fs_search` as `(pattern="", glob=...)`. Discovery tools total = 3 (blackboard/search/read). The separate ToolSpec is removed.
- **Q3 (when to ship):** **Separate S14b patch, immediately after S14 live-smoke.** S14 patch stays untouched; fs_search consolidation lands as the next slice on top.
- **Q4 (default output_mode):** `output_mode="files"` (paths only, token-cheap, FTS-fast-path). Agent re-issues in `content` mode when it needs snippets. Matches Claude Code convention.
- **Q5 (literal vs regex):** **Literal substring default, `regex=true` opt-in.** Avoids LLM escape footguns, FTS5 serves 90%+ calls at <50ms.
- **Q6 (default context_lines):** `context_lines=1` in content mode (one line before AND after the match, symmetric). Max 5 lines in each direction is a hard cap regardless of requested value.

v1 scope is now fully defined; implementation can begin as S14b.

---

## §7. Files touched by implementation slice (proposed S14b on top of current S14 patch)

Deleted:
- `src/fa/inner_loop/tools/instant_grep.py` (moved into fs_search)
- `src/fa/inner_loop/tools/grep.py` (merged)
- `src/fa/inner_loop/tools/glob.py` (merged as pattern="" path)

New:
- `src/fa/inner_loop/tools/fs_search.py` (unified builder; ~350 LOC)

Edited:
- `src/fa/inner_loop/profiles.py` — replace names in PROFILES_RAW and in `_add_optional_tool_builders`.
- `src/fa/inner_loop/tools/__init__.py` (if it exports names).
- `AGENTS.md` §Querying Artifacts — collapse 8-row intent table into 3 rows (blackboard/search/read).
- `knowledge/llms.txt` §FORMAL SUBSTRATE + «What to use instead» list.
- `tests/` — merge into `tests/test_fs_search.py`; remove 3 old files.

NOT touched:
- `src/fa/blackboard/**` (blackboard unchanged).
- `src/fa/inner_loop/tools/blackboard_query.py` (S14 stays).
- `src/fa/inner_loop/tools/read_file.py` / `write_file.py` / `edit_file.py` / `bash*.py`.
- Anything in `knowledge/research/**` except this note itself.

---

## §8. Open questions for the operator (locking in before code)

Q1 (recap, decided): one tool `fs_search` — yes.

Q2 (recap): **fs_glob disposition.** Recommendation: absorb into `fs_search(pattern="", glob=...)` as per D3.3, removing the separate tool. Net discovery tools = 3 (blackboard + search + read). **Trade-off:** a single call with `pattern=""` is a slightly odd semantic, but in practice the LLM learns the idiom quickly (Cursor/Aider already treat empty-query-as-name-search implicitly), and we save ~400 prompt tokens per turn plus eliminate one whole decision branch from AGENTS.md. Alternative: keep `fs_glob` as a 4th tool (cleaner semantics, +1 tool).

Q3 (recap): **when to ship.** Recommendation: **separate S14b patch, immediately after S14 lands and live-smoke passes.** Reason: S14 is blackboard-scoped and validated; folding a tool-surface consolidation into the same patch loses bisection and makes reverting harder if anything surfaces in live. It is still a small, scoped change (~350 LOC new, ~550 LOC removed, same day).

Q4 (new, specific to this design): **default `output_mode`.** Claude Code defaults to `files_with_matches` (paths). My recommendation matches that → `output_mode="files"` as default. Reasoning: token discipline and FTS fast path. Alternative: default `content` (like current `fs_grep`) gives snippets immediately but costs more tokens and on a large re-scan pulls the read into the response.

Q5 (new): **regex opt-in or opt-out.** Recommendation: literal-by-default, `regex=true` to enable. Slight friction for the rare case the agent wants a pattern, but avoids LLM escaping bugs and lets FTS serve 90%+ of calls.

Q6 (new): **context_lines default** in content mode. Recommendation: `0` (match line only). Agent asks for context explicitly via `context_lines=2` if needed. Alternative: 2 by default (richer responses, more tokens).

---

## §9. References

- [1] Claude Code Grep tool spec (system-prompt leak, Oct 2025): https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/Claude%20Code/grep-tool.md
- [2] ai-grep (open source, hybrid FTS+ripgrep+rerank): https://github.com/moinulmoin/ai-grep
- [3] Claude Code internal Grep impl reference: https://gist.github.com/bgauryy/0cdb9aa337d01ae5bd0c803943aa36bd
- [4] Cursor semantic search architecture (Dec 2025): https://www.digitalapplied.com/blog/cursor-semantic-search-coding-ai-guide
- [5] Claude Code tools quick reference: https://www.vtrivedy.com/posts/claudecode-tools-reference/
