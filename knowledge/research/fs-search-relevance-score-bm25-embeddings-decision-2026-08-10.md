# Do we need relevance scores / BM25 / embeddings in `fs_search`? (2026-08-10)

**Status:** decision note. Reader = operator + future implementer.
**Question:** Should the unified `fs_search` tool return a `relevance_score` per
result, and should that score come from BM25, embeddings, hybrid, or neither?
**Method:** read peer-reviewed / arXiv papers and vendor-agnostic benchmarks from
2024–2026, plus the late-2025/2026 system-prompt leaks for Claude Code and Cursor
that establish production behavior in shipped SOTA coding harnesses.

---

## §1. TL;DR (verdict)

**Do NOT add relevance scoring (BM25 or embeddings) in v1 `fs_search`. Ship plain
deterministic ordering (match_count desc, path asc) with three output modes
(`files|content|count`) as already specified in
`knowledge/research/fs-search-unification-sota-2026-08-10.md`. Keep embeddings
and hybrid ranking explicitly out of scope. BM25 ranking becomes a candidate
for v2 only after v1 ships AND a concrete accuracy regression is demonstrated.**

Reasoning in one paragraph: The most directly applicable peer-reviewed evidence
(SWE-bench, LongMemEval, BM25-Wins-at-Scale, CORE-Bench, SWE-Explore, the
"Is Grep All You Need?" Chronos study from May 2026) consistently finds that
**(a)** lexical substring / ripgrep-style retrieval matches or outperforms dense
embedding retrieval inside *iterative* agent loops; **(b)** the dominant lever
on end-to-end agent accuracy is harness/tool-shape design, not the retrieval
scoring algorithm; **(c)** BM25 is a real improvement over raw substring only
at corpus sizes 10M+ tokens where a deterministic walk/ripgrep is no longer
free — our search corpus (a single project working copy, excluding
`node_modules/.git/.venv/…`) is typically <50MB of text, well below that
crossover; **(d)** adding scores introduces opacity (non-determinism, harder
tests, weight-tuning burden) and invites agent over-reliance on a scalar
instead of actually reading files.

---

## §2. What the evidence actually says

### 2.1 Code-agent retrieval: BM25 is the established baseline; embeddings underdeliver

- **SWE-bench (ICLR 2024, Jimenez et al., arXiv:2310.06770) [2].** The canonical
  code-agent benchmark. The authors *chose* BM25 for their retrieval backbone
  explicitly because "dense retrieval methods are ill-suited to our setting due
  to very long key and query lengths, and especially the unusual setting of
  retrieving code documents with natural language queries." BM25 recalled a
  superset of the gold-edited files in ~40% of instances at the 13k-token
  budget, and oracle retrieval (perfect file set) only *marginally* improved
  fix-rate over BM25 in many settings, because models are poor at localizing
  within retrieved context regardless.
- **SWE-Fixer (arXiv:2501.05040, 2025) [3].** Authors chose BM25 over the dense
  retrievers used in Agentless/Moatless, citing BM25 as "lightweight, scalable
  and robust" for code file retrieval.
- **SWE-Explore (arXiv:2606.07297, June 2026) [8].** Directly compares Oracle,
  Random, BM25, TF-IDF, one dense retriever (Potion/RAG), and multiple real
  agentic explorers (Claude Code, Codex, OpenHands, Mini-SWE-Agent, AweAgent).
  Result: "Sparse retrievers (BM25, TF-IDF) and the lightweight dense retriever
  remain close to Random on most metrics, while every agentic explorer is
  substantially higher" — i.e. single-shot retrieval (lexical OR dense) is
  outperformed by an agent that can iteratively read and grep. The implication
  for us: **investing in a smarter retriever is a lower ROI than making the
  iterative loop cheap and easy to use**, which is exactly what
  default-paths-only + fs_read_file already achieves.
- **Code Isn't Memory (arXiv:2606.22417, June 2026) [1][4].** Leak-audited
  causal ablation of a shipped structural index (vector + call-graph + BM25)
  versus agentic grep, with Claude Opus 4.7 fixed. The structural index
  improved $/solved from $2.92 → $2.30, but the paper explicitly frames this
  as "does the workload include multi-file changes where structural ranking
  pays off" — i.e. the win is from the *structural/graph* component, not from
  BM25-over-embeddings, and it is a deployment-cost question, not a quality
  cliff.
- **CORE-Bench (arXiv:2606.11864, July 2026) [7].** 180K agentic-code-search
  queries across 106K labels. Reports a "sharp drop from traditional code
  search to code retrieval in the agentic coding setting" — i.e. existing
  off-the-shelf embeddings underperform once the task is not a clean
  top-K-nearest dataset but an in-situ agent query with iterative tool calls.
- **SpIDER (arXiv:2512.16956, Feb 2026) [6].** Dense retrieval + graph walk
  beats BM25 on SWE-Bench-Verified *when passed to a mini-agent with k=5/10*,
  but this requires LLM-reasoned graph exploration, not just vector similarity.
  Infrastructure cost is much larger than BM25.
- **CodeXEmbed (COLM 2025, Wang et al., arXiv:2411.12644) [5].** Purpose-built
  code embeddings, 7B params, improve SWE-Bench-Lite from ~19.7% → 30.7% at
  gpt-4o, but this is still low in absolute terms and the model is a
  non-trivial serving dependency.

**Pattern:** In code-agent literature, embeddings win only when (i) the corpus
is large enough that lexical scan is prohibitive, (ii) the retriever is
purpose-fine-tuned on code, AND (iii) it is part of a multi-stage pipeline
that still ends with a human/agent reading the actual source. None of these
are true for our single-repo, in-process, iterative tool.

### 2.2 Generic agentic memory/retrieval

- **"Is Grep All You Need?" (Sen et al., arXiv:2605.15184, May 2026).** The
  single most directly applicable study. Wired literal grep and vector
  retrieval into the same agents (Chronos, Claude Code CLI, Codex CLI, Gemini
  CLI), ran 116 LongMemEval questions across both inline and file-based tool
  outputs, then progressively injected irrelevant context. **Finding 1: grep
  generally yielded higher accuracy than vector retrieval.** **Finding 2:
  "overall scores still depend strongly on which harness and tool-calling
  style is used, even when the underlying conversation data are the same"** —
  i.e. harness design dominates algorithm choice. **Finding 3:** vector
  retrieval degrades as distractors are added; grep stays flat. The authors
  explicitly do NOT say "grep always wins" — they say "for literal-token-heavy
  queries over a small-to-medium corpus inside an iterative agent loop, grep
  is the better default." That is exactly our setting.
- **"BM25 Wins at Scale" (arXiv:2607.26497, July 2026) [9].** Across corpora
  sized 1K → 600M tokens, BM25 overtakes raw-file agency around 10M corpus
  tokens and leads by ~20 points at 500M+ tokens; DenseRAG and GraphRAG both
  underperform BM25 at scale AND are more expensive to build. At the small
  end, raw file reads + agent reasoning wins (which is what "default paths +
  fs_read_file" gives us). Crossover ~10M tokens — that's roughly 50–100k
  lines of code/text. Our typical working copy (excluding node_modules etc.)
  is 10K–200K lines — right at the edge; BM25 would not give us a measurable
  lift here, and deterministic grep/glob is simpler.
- **Financial-doc retrieval (arXiv:2604.01733, April 2026) [2].** BM25
  *outperformed* text-embedding-3-large (one of the strongest commercial
  embedders in 2026) on every metric except Recall@20 (0.797 vs 0.798 —
  tie). Hybrid RRF without reranker gave a small gain; a reranker was
  required for a meaningful lift.
- **Medical-doc classification (arXiv:2505.11582, June 2025) [5].** BM25 and
  MiniLM achieved the highest accuracy; BM25 was faster and slightly more
  accurate.
- **Microbenchmark (Chen, 2026, practice report) [8]:** query latency P95:
  BM25 = 6–9 ms, Vector ANN (HNSW) = 18–30 ms.
- **Hybrid search practitioner consensus (DigitalApplied 2026, Softwaredoug,
  Qdrant blog) [7]:** Hybrid (BM25 + vectors + RRF + rerank) is best for
  large-scale search products, BUT "start with BM25, add vectors when exact-
  match stops being enough." Adding vectors first is a premature optimization.

### 2.3 What the shipped SOTA harnesses actually do

- **Claude Code (late 2025/2026) [1][3][4][5]:** a SINGLE `Grep` tool wrapping
  `ripgrep`. **No vector search, no relevance score.** Three output modes:
  `files_with_matches` (paths, default), `content` (with `-n`/`-A`/`-B`/`-C`),
  `count`. Head limit across all modes. System prompt: "ALWAYS use Grep… NEVER
  invoke grep/rg as a bash command." That is exactly the shape we are
  converging on for v1 `fs_search`.
- **Cursor (mid-2026) [4]:** three layers — instant grep (FTS5 trigram, paths
  <50ms), ripgrep (Cmd-Shift-F, line snippets), @codebase semantic (embeddings
  via Turbopuffer). The semantic layer is explicitly for conceptual queries
  when keywords fail; Cursor's own docs direct users to grep for exact matches
  (error strings, identifiers). Relevance scoring exists only on the
  @codebase path.
- **Aider/Cline/OpenHands:** ripgrep-backed `search_files`/grep-style tool,
  repo-map as a separate heuristic; no mandatory vector layer in default
  configs.

In other words: the two most-used production coding agents in late 2026 ship
**without** a relevance-scored embedding search in the inner grep loop.
Embeddings, where they exist, are an opt-in second layer for conceptual
queries, not the default search primitive.

---

## §3. Applying this to First-Agent

### 3.1 Our corpus

- Working copy after pruning (EXCLUDE_DIRS already in place for instant_grep):
  `.fa/`, `node_modules/`, `.venv/`, `__pycache__/`, `.git/`, `sessions/`,
  plus build outputs.
- Typical First-Agent working copy: 1–50 MB text, ~100K–500K lines of code +
  docs. Our own repo today: ~100 .py files in `src/fa/**` (~25K LOC), ~200 .md
  knowledge files.
- This is **well below** the ~10M-token crossover where BM25 begins to pull
  away from deterministic substring in the "BM25 Wins at Scale" study.
- Critically: agents can iterate. A paths-only response → `fs_read_file` on
  1–3 candidates → re-query with a tighter glob is cheap (sub-100ms for the
  FTS path, no external API calls). The "Is Grep All You Need?" paper
  specifically finds that iterativity favors lexical search over vector
  retrieval because the agent can narrow by literal tokens.

### 3.2 What adding a `relevance_score` field costs (concrete)

- **API surface bloat.** Agent has to learn to interpret scores (cosine is
  0..1, BM25 is unbounded positive, scores aren't comparable across modes or
  queries). If scores exist, agents will over-trust them ("if score > X it's a
  match"), which is a well-known failure mode from RAG literature.
- **Non-determinism → test flakiness.** BM25 is stable, but any embedding or
  reranker path introduces floating-point and model-version drift. Our current
  test regime (deterministic fixtures, 51 blackboard tests) relies on
  reproducibility.
- **Dependency creep.** BM25 can be done in pure SQLite (it's built into FTS5
  via the `bm25()` function), but hybrid search needs RRF tuning; embeddings
  need (a) a model (MiniLM/all-MiniLM-L6-v2 is ~80MB on disk, aigate has a
  free API), (b) an ANN index (HNSW via sqlite-vss or chroma/faiss — new native
  deps), (c) a refresh strategy when files change, (d) failure semantics when
  the embedding API is unavailable.
- **Cold-start / reindex latency.** Embedding a project at session start
  costs 1–30s depending on model/CPU; doing it lazily adds 1–5s to the first
  search. FTS5 trigram is <100ms to build on our repo size.
- **False-confidence risk.** A "relevance score" invites the agent to stop
  reading after the top-1 result. Empirically (see SWE-bench §4) agents do
  this even without scores; adding a numeric score amplifies the bias.

### 3.3 What embeddings via aigate *would* theoretically buy us

- **Paraphrase/synonym matching.** E.g. query "auth" finding files that say
  "authentication middleware"; query "rollback" finding ADRs that say
  "revert to prior commit". In practice, in a codebase most *names* are
  literal (identifiers, error strings, error classes) — grep wins on those.
  Paraphrase is mostly useful for docs/knowledge notes.
- **Cross-file conceptual queries** ("where do we handle write conflict
  serialization?") where the code doesn't use the query words. SWE-Explore
  and Code-Isn't-Memory show that an agent that iteratively reads does this
  adequately with grep; structural/graph indices beat lexical there, not
  flat embeddings.
- **Cold-start "find relevant docs for this task" before reading anything.**
  Our blackboard already provides type-browsing of knowledge artifacts
  (`fs_blackboard_query(type=adr)`), which handles the common "what is the
  policy for X" question without embeddings.

### 3.4 Failure modes we *should* avoid (from the literature)

1. **Score-over-trust bias (CORE-Bench, SWE-bench oracle ablation).** Presenting
   a scalar score makes the agent less likely to read a lower-ranked file that
   is actually relevant. Oracle retrieval in SWE-bench only marginally
   improved fix rates over BM25, and sometimes hurt, because agents were
   "satisfied" by retrieved context even when it was incomplete.
2. **Hybrid weight-chasing.** Linear mixes of BM25 + cosine are known to be
   dominated by BM25 unless you use RRF (per [7]); RRF adds tunable k=60 and
   two rankings but gives only +5–10% NDCG in most reported experiments, at
   2× retrieval cost.
3. **Embedding-domain drift (BEIR, financial-doc study).** Off-the-shelf
   embeddings underperform BM25 on domain text (finance, biomedical, code)
   without fine-tuning. The aigate free API will be a general-purpose
   embedding; we have no evidence it is code-competitive.
4. **Distractor sensitivity ("Is Grep All You Need?" experiment 2).** Vector
   retrieval accuracy falls as irrelevant context is added to the corpus;
   grep stays flat. In a long-lived repo where notes, logs, scratch files,
   `.fa/` scratch all coexist, this is a real risk.

---

## §4. Recommendation (locked for v1; decision rule for v2)

**v1 `fs_search` (S14b) — NO relevance score.** Three modes (`files` default,
`content`, `count`), literal-substring default, `regex=true` opt-in,
`glob`/`path`/`limit`/`context_lines` params, deterministic ordering
(match_count desc → path asc; in content mode path asc → line asc). No BM25,
no embeddings, no reranking. Same surface shape as Claude Code's Grep, which
we know works in production.

**Add BM25 (still no embeddings) in v2 iff** we observe at least one of:
- Real sessions where agent fails to find an artifact after 2+ targeted
  searches AND a post-hoc BM25 ranking of the same FTS hit-set would have
  placed the correct file at position ≤3.
- The working copy routinely exceeds 10M indexed tokens (~50MB of source)
  after pruning, making the linear fallback path measurably slow.
- Evidence that match_count-based ordering puts the correct file below
  position 5 on realistic traces.

BM25 is cheap to add later because FTS5 ships with `bm25()` built-in; it's a
single `ORDER BY bm25(...)` flip with no schema change. We lose nothing by
deferring it.

**Add embedding / hybrid search in v3 only if** BM25 still demonstrably misses
classes of queries AND we are willing to pay for the dependency (ANN index,
model refresh, API fallbacks when aigate is down, non-determinism budget in
tests). Even then, semantic search should be an **opt-in** parameter
(e.g. `semantic=true`) rather than the default — following Cursor's model,
where @codebase is an explicit opt-in and grep is the primary tool.

**Concrete guidance going into AGENTS.md after S14b:**
> `fs_search` answers "where". It returns paths (default) or line-matched
> snippets, deterministically ordered. It does NOT score or rank by
> relevance. If the first results don't contain the target, narrow the
> query (tighter glob, different literal token, add regex) or read the
> promising files with `fs_read_file` rather than expecting magic ranking.
> There is no semantic/vector mode in v1 — paraphrase-style queries are
> answered by a combination of blackboard type-browsing + read, not by a
> search score.

---

## §5. Summary of ROI by feature

| Feature | End-to-end accuracy gain (literature) | Implementation cost | Risk / new failure modes | Verdict for v1 |
|---|---|---|---|---|
| paths-only default (ripgrep/FTS) | baseline (Claude Code, SWE-bench BM25) | already planned | minimal | **Ship** |
| line-snippet content mode | slight (fewer follow-up reads) | ~100 LOC | minimal | **Ship** |
| glob/path filter | prevents noise | ~20 LOC | minimal | **Ship** |
| literal-by-default + regex opt-in | avoids escape bugs, FTS fast path | ~30 LOC | minimal | **Ship** |
| BM25 ranking | +0–5% nDCG at our corpus size, per [2][9] | trivial (FTS5 bm25()) | slight non-determinism feel; tuning risk; score misinterpretation | **Defer to v2** |
| Embedding/semantic search | +0–15% nDCG on paraphrase queries; often negative on literal code queries per [1][8][6]; model-sensitive | high (model, ANN index, reindex lifecycle, API failures, tests) | domain drift, distractor sensitivity, score-over-trust bias | **Defer to v3, opt-in only** |
| Hybrid + RRF + reranker | +5–12% nDCG in large-corpus hybrids per [2][7]; at our scale likely ≤2% | very high (two rankings, reranker model) | major complexity, hard to test | **Do not build without measured regression** |
| relevance_score field | negative if it causes agent to stop reading | small schema change | score misinterpretation, false confidence | **Do not ship** |

---

## §6. References

1. Sen et al., "Is Grep All You Need? How Agent Harnesses Reshape Agentic
   Search," arXiv:2605.15184, May 2026.
   https://arxiv.org/abs/2605.15184
2. Jimenez et al., "SWE-bench: Can Language Models Resolve Real-World GitHub
   Issues?" (ICLR 2024), arXiv:2310.06770.
3. SWE-Fixer (Xia et al.), arXiv:2501.05040, 2025.
4. "Code Isn't Memory: A Structural Codebase Index Inside a Coding Agent,"
   arXiv:2606.22417, June 2026.
5. Wang et al., "CodeXEmbed" (COLM 2025), arXiv:2411.12644.
6. "SpIDER: Spatially Informed Dense Embedding Retrieval," arXiv:2512.16956,
   Feb 2026.
7. CORE-Bench, arXiv:2606.11864, July 2026.
8. SWE-Explore, arXiv:2606.07297, June 2026.
9. "BM25 Wins at Scale: A Scaling Study of RAG Paradigms," arXiv:2607.26497,
   July 2026.
10. "From BM25 to Corrective RAG," arXiv:2604.01733, April 2026.
11. "Comparing Lexical and Semantic Vector Search When Classifying Medical
    Documents," arXiv:2505.11582, June 2025.
12. Chen, "What I Learned About BM25 While Stress-Testing Hybrid Search,"
    Jan 2026 (practitioner report, Microbenchmark P95 latency).
13. Claude Code Grep tool spec (verified system-prompt leaks Oct 2025),
    https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/Claude%20Code/grep-tool.md
14. Cursor AI Semantic Search architecture, Dec 2025
    https://www.digitalapplied.com/blog/cursor-semantic-search-coding-ai-guide
15. DigitalApplied, "Hybrid Search: BM25, Vector & Reranking Reference 2026."
