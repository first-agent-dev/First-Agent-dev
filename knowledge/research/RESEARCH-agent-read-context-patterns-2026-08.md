# How production agent harnesses handle file reading and context — mid-2026

Research date: 2026-08-31. Sources: Arize four-harness comparison (Pi, OpenClaw, Claude
Code, Letta), OpenDev arXiv 2603.05344 (Mar 2026), OpenHands V1 SDK arXiv 2511.03690 +
official docs, SWE-agent ACI, Aider repo map, Cursor indexing architecture, NVIDIA AI-Q
deep researcher, GPT Researcher, and the coding-agent scaffold taxonomy arXiv 2604.03515.

Purpose: ground First-Agent's `fs_read_file` / projection / LoopGuard design (BACKLOG
I-57, D10) against what the field converged on, and answer "what comes after search
locates the target?"

---

## 1. The per-read budget landscape

| System | Per-read cap | Truncation shape | Self-describing? |
|---|---|---|---|
| Pi (pi-mono) | 2000 lines **or 50KB**, whichever first | head-only | yes: `[Showing lines 1-2000 of 50000. Use offset=2001 to continue.]` |
| OpenClaw | inherits Pi; tool results separately capped at 16,000 chars or 30% of window | head-only; 75/25 head/tail for bootstrap files | yes |
| Claude Code | 256KB pre-read byte gate + **25,000 token** post-read budget | **rejects** with actionable error | yes: error names offset/limit and grep |
| Letta | 5k / 15k / 25k / 40k chars **scaled to the model's context window** | middle-truncate 30/30 as fallback | yes |
| OpenDev | **30,000 chars**; offload to scratch file above **8,000 chars** | head+tail 10k+10k (at 30k) | yes: agent-aware recovery hint |
| SWE-agent | **100-line window** centred on target | n/a (window, not truncation) | yes: `[File: path (N lines total)]`, `(N more lines above)`, `(N more lines below)` |
| **First-Agent** | **4,096 bytes** (ToolSpec default, no override) | **50/50 head+tail** | **no** |

Two structural observations:

1. First-Agent's cap is **6–25× smaller** than every system in the comparison, while
   using the most aggressive truncation shape. Head+tail is what OpenDev applies at
   30,000 chars, not what anyone applies at 4,096 bytes.
2. **Every system frames the result.** SWE-agent's 20-line bash viewer emits the total
   line count and the above/below counts. Pi emits a resume instruction. Claude Code
   refuses rather than mislead. First-Agent's elided output contains no reference to the
   requested range, no total, and no resume hint — verified by direct execution against
   `src/fa/cli.py`.

The documented failure mode of unframed truncation, verbatim from field reporting on
Claude Code: *"Claude has no signal that anything is missing — it confidently reasons
over the head of the file as if it were the whole thing."* That is an exact description
of the 2026-08-31 l2 row.

### A named anti-pattern First-Agent commits

OpenDev documents "agent-aware truncation hints" specifically to avoid *"the common
failure mode where an agent attempts a recovery strategy unavailable in its tool set."*
First-Agent's elided output ends with `[artifact: <id>]` and **no artifact-fetch tool is
registered** (verified: 16 `fs_*` tools, none fetch). Cursor does the opposite with the
same primitive — see Pattern 2.

---

## 2. Golden patterns extracted

### Pattern 1 — Locate, then read the *unit*, not a line count
The taxonomy paper (arXiv 2604.03515) categorises context-retrieval paradigms: keyword/
regex search (SWE-agent, OpenHands, Codex CLI, Gemini CLI, Cline), repo map via static
analysis (Aider), AST-aware search (`search_class`, `search_method` — AutoCodeRover,
Moatless, Prometheus), knowledge-graph traversal (Prometheus/Neo4j), embedding search
(Moatless), **hierarchical localisation** (Agentless: file → class/function → line, each
level seeing only what the previous identified), and classical fault localisation.

The common shape: **narrow first, then read exactly the narrowed unit.** Nobody pages
through a file to find a function; they locate it and read it.

### Pattern 2 — Spill to a file, never to a dead end
Cursor's *dynamic context discovery*: "files as the unit of context management. Instead
of eagerly injecting retrieved content into the prompt, tool responses that are too large
get written to temporary files. The agent is given the file path and can decide whether
to read it, tail it, or grep it… This prevents context bloat while ensuring **no
information is lost to truncation**."

OpenDev's 8,000-char offload does the same with a recovery hint tailored to the agent's
actual tool set. The invariant: **if you remove content, the pointer must be followable.**

### Pattern 3 — The frame is the product
SWE-agent's ACI thesis: a 100-line windowed viewer + line-targeted edit + syntax-checked
autosave roughly **doubles** SWE-Bench score versus raw bash. "The agent isn't smarter;
it's better-housed." The viewer's entire output is a frame:

```
[File: path (3664 lines total)]
(3329 more lines above)
3330: def _cmd_stats(...
...
(204 more lines below)
```

### Pattern 4 — Shape layer and body layer are separate budgets
Aider allocates **1/8 of the context window** to the repo map (default 1024 tokens,
`max(1024, min(max_input/8, 4096))`), renders *scope-aware elided code views* —
signatures, not bodies — ranks symbols with personalised PageRank over the reference
graph (identifiers in conversation get 10× boost, chat files 50×, edge weight
`sqrt(count)`), caches in SQLite, and **binary-searches the ranked list to fit the token
budget**.

SWE-agent's `filemap` bundle is the same idea per file: "condensed Python file viewer
(skips long bodies, shows just signatures)."

Implication: a 3,664-line file has a *shape* that costs ~1k tokens and a *body* that
costs ~12k. You almost always want the shape of the whole and the body of one part.

### Pattern 5 — Retrieval returns coordinates, not content
Cursor's search returns **metadata — obfuscated path + start/end line** — and the client
reads the actual code locally at inference time. Retrieval is cheap and repeatable;
content is materialised only for the lines actually needed.

### Pattern 6 — Hybrid lexical + semantic
Cursor runs a vector index *and* a trigram/sparse-n-gram inverted index, because
"semantic search misses exact identifier matches; lexical search misses conceptual
similarity." First-Agent's `fs_search` (bm25 over an FTS index, 845 files indexed in the
l2 trace) is the lexical half and is the right primary for a coding agent; a repo map is
the structural complement. Embeddings are the layer you add last, if at all — Aider is
explicitly symbol-level, not semantic, and remains competitive.

### Pattern 7 — Compaction as a *view*, never a mutation
OpenHands V1: "The results of any given condensation are stored in the event log as a
CondensationEvent. Before sending the event history to the LLM, the agent *applies* these
condensation events by removing forgotten events and inserting summaries. This strategy
lets the SDK **preserve the entirety of the event log**, regardless of condensation,
while also keeping the condenser implementations stateless."

Their four design principles: stateless components, single source of truth, **the only
mutable thing is ConversationState**, state changes happen by appending events — never by
mutating objects. Default condenser: `LLMSummarizingCondenser(max_size=80, keep_first=4)`,
reported ~2× per-turn cost reduction at equivalent or better task performance.

This is the direct answer to First-Agent's `conversation_history = masked_history`
(coder_loop.py:1163), which permanently rewrites the prefix — both an audit loss and, per
the 2026 prompt-caching consensus, a cache-destroying move ("shrink the context, don't
rewrite it").

### Pattern 8 — Subagent isolation is the long-context strategy
NVIDIA AI-Q (#1 on DeepResearch Bench I and II): *"The multi-agent design also serves as
a long-context strategy: each subagent works within its own context window and returns
only its synthesized output, so the orchestrator never sees the raw tool responses."*
OpenHands, same point: "the parent never sees the 200 lines of grep output — only the
sub-agent's distilled answer." Cursor Cloud Agents fan subagents out in parallel to build
a context map *before* editing.

### Pattern 9 — Plan → gather → synthesise → gap → iterate → write
The deep-research convergence (NVIDIA AI-Q, GPT Researcher, LangChain/Together Open Deep
Research, qx-labs): an orchestrator, a planner that builds an **evidence-grounded**
outline (it surveys before committing to structure), and researchers dispatched in
parallel; then a gap-analysis pass and a bounded number of loops (AI-Q default: 2); then
a writer. AI-Q adds a **refiner in a fresh context window** as "a second evidence recovery
point."

**Counter-evidence worth holding:** Deep Researcher Reflect Evolve (arXiv 2601.20843)
reports sequential plan refinement beating parallel scaling, and names the *"siloed
knowledge problem inherent in parallel architectures like Static-DRA and GPT Researcher."*
Parallel fan-out is not free; it trades coherence for coverage.

### Pattern 10 — Runtime owns the batch, not the model
Practitioner consensus for wide fan-out: "LLM plans the calls (arguments only) → runtime
owns execution (batch + parallelism, rate limits, retries) → results aggregated →
only the summary goes back." Reads parallelise safely; writes to shared state do not.
Every call must return a result, including failures, or the transcript is malformed.

### Pattern 11 — Train the retriever on your own agent traces
Cursor: "agent sessions are the training data… they feed each trace to an LLM that ranks
what content would have been most helpful at each step, then train the embedding model to
align its similarity scores with those rankings." The objective shifts from "do these
resemble each other" to "given this task, which chunk actually helps."

First-Agent already records everything needed for this — `expansion_observed`,
`file_read` telemetry with `surfaced_by`, the full EventLog. This is a latent asset.

---

## 3. The cost tradeoff nobody hides

Cursor loads heavy context per message — users report ~18.5k tokens to say "hello" —
because editor state, open files, index results and MCP metadata all ride along. Codex is
measured **2–4× leaner** by cloning fresh and searching on demand. Retrieval-heavy is not
automatically better; it is better for *huge* repos and worse for focused tasks.

---

## 4. Answering the operator's questions directly

**"Do we need to read files in sections? Maybe for 4k-line ones."**

The honest arithmetic: 3,664 lines of First-Agent's `cli.py` is 12,607 bytes ≈ 3.2k
tokens — **2% of a 150k window.** A 4,000-line file is roughly 12–16k tokens, which is
inside Claude Code's 25k per-read budget and Pi's 50KB. So for source files, no: you
don't need sections. You need a budget that permits the whole file, plus a shape layer
for orientation. Sections are for logs, generated code, data files, and 20k+ line
monsters — which is exactly what offset/limit exists for, and why every harness keeps it.

**"We located the file, maybe the exact function. What's next?"**

1. **Frame the read.** Window centred on the located line, with total lines and
   above/below counts (Pattern 3). One read, ~130 lines, ~2k tokens.
2. **If you need the file's shape**, read the *outline*, not a chunk: signatures only
   (Pattern 4). SWE-agent's `filemap` and Aider's repo map are the same move at different
   scopes.
3. **If you need several files**, either batch full reads in one turn (affordable once
   the per-read budget is real) or fan out subagents that each return a brief (Pattern 8).
4. **If you need to compose across files**, use the shell — one script execution instead
   of ten reads ("think in code"). This is the cheapest batching lever and First-Agent
   already ships the tool.

**"What about 3k + 2k + 1.5k LOC files, or plan documents?"**

≈22k tokens total, ~15% of a 150k window. Read all three whole, in one turn, in parallel.
That is what Codex/Claude Code/OpenHands would do. For plan documents, the deep-research
shape applies instead: outline → per-section parallel gather → synthesise → gap pass →
write, with subagents holding the raw material and the orchestrator holding only briefs.

**"The deterministic chunker tool I tried to build early on."**

The instinct was right; the placement was wrong. Every AST-aware system in the field
chunks — but at the **index/symbol layer**, on AST boundaries (Cursor: tree-sitter, merge
siblings to ~500 tokens, never split a function; Aider: tree-sitter tags + PageRank +
scope-aware elision). None of them chunk at the *read* layer; the read layer uses line
windows. So the chunker belongs behind `fs_search`, producing symbols and line ranges,
not in front of `fs_read_file`.

---

## 5. First-Agent scorecard

| Golden pattern | First-Agent today | Gap |
|---|---|---|
| 1 Locate → read unit | `fs_search` bm25 with ±context lines; returns matches | Good primary. No symbol/unit notion; no AST-aware `search_method` |
| 2 Spill, don't dead-end | ArtifactStore writes JSON to disk; `[artifact: id]` in output | **Dead end** — no fetch tool. Either register one or stop emitting the ref |
| 3 Frame the result | none | **Largest single gap.** No total, no above/below, no resume hint |
| 4 Shape vs body budgets | conflated: one 4096-byte cap for everything | No outline/repo-map layer at all |
| 5 Retrieval returns coordinates | `fs_search` returns content snippets | Partially there (has `before`/`after`/line info) |
| 6 Hybrid lexical + structural | lexical only | Aider-shaped gap; acceptable, embeddings are optional |
| 7 Compaction as view | `conversation_history = masked_history` mutates | **Anti-pattern**; currently disabled so no live harm |
| 8 Subagent isolation | `fs_spawn_subagent`, `invoke_workflow` exist | Present; not used as the context strategy in the l2 rows |
| 9 Plan→gather→synth→gap | CAE levels + IntentGuard + PR draft | Different (and arguably stronger) ceremony; no gap-analysis loop |
| 10 Runtime owns batch | model emits parallel calls; LoopGuard punishes same-path batches | **Inverted**: batching same-file reads accelerates the breaker |
| 11 Learn from traces | full EventLog + expansion + file_read telemetry recorded | Latent asset, unused |
| Per-read budget | 4096 B ≈ 1000 tokens of 150,000 (0.7%) | 6–25× below field norms |

The l2 task — simplify one function in a 3,664-line file — should cost one search, one
~130-line read (~2k tokens) and one edit: three turns. First-Agent spent nine and killed
the session, because the read layer could not return the unit the search had already
located.

---

## 6. What this changes in the recommendation

Ordered by leverage, not effort:

1. **Frame every read** (Pattern 3). Contiguous window, header with `path (N lines total)`,
   `(N more lines above)` / `(N more lines below)`, and an explicit resume line. This is
   the cheapest change with the largest behavioural effect and it is what SWE-agent's
   doubled score is attributed to.
2. **Raise the per-read budget to something real** — 24–32KB is defensible against a 150k
   window (Pi 50KB, Claude Code 25k tokens, OpenDev 30k chars). 4096 bytes is the actual
   root cause of the paging spiral; framing alone still leaves the model paging through
   fragments.
3. **Make the artifact pointer followable or remove it** (Pattern 2). Either register an
   artifact-fetch tool or stop printing a reference nothing can resolve.
4. **Add a shape layer** (Pattern 4): a `filemap`-style outline mode on `fs_read_file`
   (signatures only, budget-fitted by binary search per Aider) or a symbol index behind
   `fs_search`. This is where the "deterministic chunker" belongs.
5. **Stop punishing pagination** (Pattern 10 inverted): exempt reads from LoopGuard
   Detector 2, and make guard denial terminal rather than zombie.
6. **Fix compaction before enabling it** (Pattern 7): apply masking as a send-time view
   over an intact EventLog; never mutate the prefix.
7. **Use subagents as the context strategy** (Pattern 8) for multi-file exploration —
   the tools already exist.

Deliberately *not* recommended: embeddings/vector retrieval (last, if ever, for a
terminal coding agent); a batch-read tool before the per-read budget is fixed (batching
fragments is worse than batching wholes); silent truncation anywhere.
