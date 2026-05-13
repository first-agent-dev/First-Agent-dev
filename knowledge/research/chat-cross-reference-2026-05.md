---
title: "Cross-reference list — chat extract analysis (pre-ADR-6 + post-ADR-7)"
source:
  - "User-attached chat extracts from community chat with humans and autonomous agents"
  - "https://github.com/Disentinel/soviet-code"
  - "https://github.com/mikhashev/dpc-messenger"
  - "https://github.com/AndyMik90/Aperant"
  - "https://github.com/zzet/gortex"
compiled: "2026-05-13"
goal_lens: "Извлечь из чат-логов имена/проекты/паттерны для cross-reference в будущих сессиях; собрать reading-list."
chain_of_custody: |
  Все имена и цитаты извлечены из двух user-attached chat extracts
  (~325 строк pre-ADR-6 + ~741 строка post-ADR-7); URL'ы не открывались
  в этой сессии, помечены для будущего изучения. 27 паттернов
  классифицированы из reported quotes агентов (Ираида, Mikhashev, Vadim,
  Dmitry-Тезей).
---

> **Status:** active. Chat-extract analysis (not produced via
> `knowledge/prompts/research-briefing.md`, §0 retrofitted).

## 0. Decision Briefing

### R-1 — Add 5 repos + 2 bonus to future cross-reference reading list

- **What:** Document 6 repos identified in chat as reference material for FA: `Disentinel/soviet-code`, `mikhashev/dpc-messenger` (+ `docs/decisions/`), `AndyMik90/Aperant`, `zzet/gortex`, plus bonus `spyrae/kronos-agent-os` (KAOS) and `makroumi/ulmen` (LangGraph ext).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (single reading-list vs scattered chat refs)
  - (B) helps LLM find context when needed: YES (per-repo pointers)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (this note IS the reading list)
- **Cost:** cheap (<1h, document only)
- **Verdict:** TAKE
- **Alternative-if-rejected:** scattered chat URLs in BACKLOG.md
- **Concrete first step (if TAKE):** §2 of this note already lists them with priority + first-pass notes

### R-2 — 6 key concepts with direct FA mapping (catalog)

- **What:** Cross-reference table mapping 6 concepts from chat to FA artifacts: Protocol 13 ↔ HANDOFF, trigger-gated vs content-autonomous, Memento-Skills ↔ Devin SKILL.md, confidence tiers, tool-call hallucination watchdog, convergent evolution KG.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (pre-computed mappings)
  - (B) helps LLM find context when needed: YES (each concept points to specific FA file)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (catalog IS the deliverable)
- **Cost:** cheap (already done in §3)
- **Verdict:** TAKE
- **Alternative-if-rejected:** keep concepts in chat-only memory
- **Concrete first step (if TAKE):** Already documented in §3 of this note

### R-3 — Tool-call hallucination watchdog as BACKLOG candidate

- **What:** Pattern #20 from chat: agent emits fake `<tool_call>` XML in thought text that gets executed. ADR-7 §5 currently doesn't catch this.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (runtime check)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (cross-references chat to ADR-7 gap)
- **Cost:** medium (1-2h ADR amendment + 2-3h implementation in Phase M)
- **Verdict:** UNCERTAIN-ASK
- **If UNCERTAIN-ASK:** Should this be: (a) ADR-7 amendment now, (b) BACKLOG entry deferred to Phase M, (c) skip as DPC's HookRegistry covers it via middleware?
- **Alternative-if-rejected:** rely on DPC's HookRegistry adoption (B-NEW-5) covering the case
- **Concrete first step (if TAKE):** Add BACKLOG entry "tool-call hallucination guard"

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES | cheap | scattered chat refs | No |
| R-2 | TAKE | YES / YES | YES | cheap | chat-only memory | No |
| R-3 | UNCERTAIN-ASK | NO / NO | PARTIAL | medium | rely on B-NEW-5 | Yes (a/b/c) |

---

# Cross-reference list for next session — chat extract analysis

## §-1. How to use this document (fresh session bootstrap)

**Task type:** ANALYSIS ONLY — no PR, no code changes in this repo. The
output is a Markdown findings report attached to chat.

**Inputs:**
1. This document — items in §2 (repos), §3 (patterns), §4 (concrete
   adopt candidates).
2. The two original chat extracts (user will re-attach if needed).
3. First-Agent ADRs and BACKLOG (links below).

**Forbidden:**
- Do not modify First-Agent files.
- Do not open any PR.
- Do not visit external URLs in the chat extracts that are not in the §2
  repo list.

**Pre-flight reading (in order, before opening any external repo):**
1. [`HANDOFF.md`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/HANDOFF.md) — current FA state.
2. [`AGENTS.md`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/AGENTS.md) — operational rules (esp. minimalism-first 4-question test, rule #10).
3. [`knowledge/llms.txt`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/knowledge/llms.txt) — canonical index.
4. [`knowledge/adr/DIGEST.md`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/knowledge/adr/DIGEST.md) — one-row-per-ADR summary.
5. [`knowledge/adr/BACKLOG.md`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/knowledge/adr/BACKLOG.md) — pending items (I-1..I-8 referenced below).
6. [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](https://github.com/MondayInRussian/First-Agent-fork2/blob/main/knowledge/adr/ADR-7-inner-loop-tool-registry.md) — most recent ADR; many §3 patterns map to it.

**Deliverable for next session:**
- One `.md` findings report with sections:
  - §1 What was studied (repo-by-repo)
  - §2 Adopt — patterns to bring into FA (BACKLOG candidates)
  - §3 Reference — patterns to know but not adopt now
  - §4 Skip — patterns rejected (with minimalism-first reasoning)
  - §5 Open questions / follow-up
- Attached to chat. Optional: open ONE BACKLOG.md update PR if 3+ adopt
  candidates emerge (only after user approval).

**Session budget guidance:** ~90 min equivalent. Prioritize §2 Priority A
repos; Priority B only if budget remains.

---

## §0. Summary

Two chat excerpts from a Telegram community where humans and autonomous
agents discuss architecture, share code reviews, and exchange ideas.
Excerpt 1 is pre-ADR-6 (earlier, ~325 lines, mostly Dmitry/Тезей
multi-agent philosophy). Excerpt 2 is post-ADR-7 merge (~741 lines,
much richer — Ираида doing live code audits, DPC/Enox/Grafema
architecture exchange with Mikhashev and Vadim).

**Relevance to First-Agent:** HIGH for knowledge-graph, retrieval,
skills, and inner-loop design. Several patterns directly map to
existing ADR-7 / BACKLOG items.

---

## §1. Participants identified

| Handle / Name | Role | Project |
|---|---|---|
| Ираида (И.М. Узлова, "ЦВК") | Autonomous agent | `github.com/Disentinel/soviet-code` |
| @disentinel (Вадим) | Human, architect | Grafema + Enox + Soviet-Code |
| @mikhashev (Михаил) | Human, architect | `github.com/mikhashev/dpc-messenger` |
| Ark | Agent (Ouroboros fork) | DPC ecosystem |
| CC | Agent (Claude Code) | DPC ecosystem |
| Mike | Human operator | DPC ecosystem |
| Dmitry / Тезей | Agent (Ouroboros) | Multi-persona agent w/ BIBLE.md |
| @ai_sapience_bot | Agent | Separate; provides diagrams/analysis |
| Roman Kolomeychuk | Human (project lead) | First-Agent (this project) |
| @MrRichSylvester | Human | Mentioned re: decomposed-task routing |

---

## §2. Projects and repos to study in next session

### Priority A — direct architectural value

| Repo | What to look at | FA relevance |
|---|---|---|
| `github.com/mikhashev/dpc-messenger` | `docs/decisions/` (ADRs), P2P knowledge search (ADR-017), knowledge commit pipeline, DPTP protocol spec | Knowledge graph design, session bootstrap ritual (Protocol 13), skills pattern, trust model |
| `github.com/Disentinel/grafema` | Static code analysis → cross-file graph (KuzuDB), plugin system, deterministic heuristics | Potential tool for FA codebase analysis; BACKLOG I-8 harness eval |
| `github.com/Disentinel/enox` | Knowledge graph (typed relations, provenance, semantic search), confidence tiers, perspective model | Direct overlap with BACKLOG I-7 (KPI auto-collection) and ADR-3 Mechanical Wiki evolution |
| `github.com/Disentinel/soviet-code` | Agent pipeline powering Ираида; code review via Grafema | Agent architecture reference for inner-loop comparison |

### Priority B — study but lower urgency

| Repo | What to look at | FA relevance |
|---|---|---|
| `github.com/AndyMik90/Aperant` | (Unknown — needs first pass) | Mentioned by user; explore |
| `github.com/zzet/gortex` | (Unknown — needs first pass) | Mentioned by user; explore |
| `github.com/spyrae/kronos-agent-os` | Memory layers (SQLite+FTS5+Qdrant+KG), Skills system, Swarm mode, Capability gates | ADR-7 tool-registry parallel; skills ≈ FA's SKILL.md pattern |
| `github.com/makroumi/ulmen` (ext/langgraph) | LangGraph integration | Potential comparison for FA inner-loop vs LangGraph graph |

---

## §3. Architectural patterns worth cross-referencing to First-Agent

### 3.1 — Knowledge & memory

| # | Pattern | Source | FA mapping |
|---|---|---|---|
| 1 | **Knowledge commit pipeline** — append-only immutable .md with `parent_commit_id`, supersede-not-delete, multi-party RSA-PSS attribution, semantic merge (not diff-merge) | DPC | ADR-3 Mechanical Wiki + ADR-7 §7 trace events. Very close to our `events.jsonl` philosophy. Semantic merge concept is novel — our DIGEST.md serves similar function. |
| 2 | **Protocol 13 — structured pre-flight ritual** — CC reads 7 canonical sources at session start: MEMORY.md, last session memory, cron prompt, backlog, git status, protocol-13.md, cronlist. "Not 'agent remembers' — deterministic state loading." | DPC | Direct parallel to our HANDOFF.md §60-second bootstrap + AGENTS.md §Pre-flight checklist. Worth comparing ritual completeness — their 7-source vs our 3-step (HANDOFF → llms.txt → pre-flight). |
| 3 | **Trigger gated / content autonomous** — human controls lifecycle events (sleep/wake moments), agent autonomous on epistemic operations (brief content). Failure cost analysis: inaccurate brief = low-cost, missing brief = high-cost. | DPC (Ark) | Directly applicable to Phase M runner design — human gates session boundaries, agent decides what to load. Not yet articulated in our ADR stack. |
| 4 | **Memento-Skills** — skills as .md strategy files (not code), `execute_skill(name)`, stats tracking (failure rate, access count), `self_modify` on underperformance — online learning without retraining. | DPC (Ark) | Maps to Devin's SKILL.md pattern. Compare against our ADR-7 §3 tool catalog — skills are higher-level (multi-tool strategies), tools are atomic. Future layering: skills on top of inner-loop tools. |
| 5 | **Confidence tiers** — `extracted → auto-verified → human-verified → canonical` | Enox | Useful for First-Agent knowledge store maturity model. Currently we have one tier (everything is canonical by fiat once committed). |
| 6 | **Three-layer memory** — Raw (Qdrant vectors) → Distill (entity extraction → KuzuDB graph) → Retrieval (semantic search + graph traversal + code graph). Identified gap: Distill layer often missing. | Ouroboros / community consensus | ADR-3+ADR-4 already chose SQLite FTS5 (simpler than Qdrant for v0.1). But the layer separation is a useful mental model for Phase M: what are our Raw/Distill/Retrieval layers? |
| 7 | **Dialogical memory schema (production)** — `messages` (pgvector), `summaries` (sliding window), `memory_items` (importance + TTL + access_count) | Community pattern | Reference architecture for future memory system; beyond v0.1 scope but worth knowing. |
| 8 | **Actor-graph on top of entity-graph** — each participant has behavioral profile (motivation, patterns, trust weight). Retrieval without actor context gives context without subject. | Ираида's analysis | Not in our ADR stack; potentially relevant for multi-agent scenarios (v0.2 UC5). |
| 9 | **Silence as typed event** — non-events logged with rationale alongside events. "Half the signal is in what wasn't said." | Ираида's analysis | Interesting for ADR-7 §7 trace — currently we only log actions. Logging non-actions (why a hook denied, why model didn't call a tool) could improve eval. |
| 10 | **Graph entropy** — Distill layer re-extracts same entities from overlapping content → needs dedup fingerprint or reconciliation pass | Ираида's analysis | Design constraint for any future auto-extraction in our knowledge store. |

### 3.2 — Tools, code analysis, security

| # | Pattern | Source | FA mapping |
|---|---|---|---|
| 11 | **Grafema** — static code → cross-file dependency graph (KuzuDB), Cypher queries, plugin-extensible heuristics, tree-sitter provides CST but Grafema builds project-wide architecture graph. Key differentiator: "your code as a graph, not flat text" | Disentinel | Potential external tool for FA codebase auditing (like Ираида did for DPC). Also consider as a reference for ADR-7 §3 `fs.grep` evolution — structural search vs text search. |
| 12 | **DPTP** — binary framing protocol over TLS, CC0 license for spec, LGPL for library | DPC | FA doesn't need P2P transport, but the spec licensing model (CC0 spec + LGPL lib + GPL client + AGPL hub) is exemplary for open protocol projects. |
| 13 | **NAT traversal stack** — custom STUN → Kademlia DHT → UDP hole punch → volunteer relay for symmetric NAT | DPC | Not directly relevant to FA but notable engineering. |
| 14 | **Tool-call hallucination** (Pattern #20) — MiniMax generates pseudo-XML tool calls as text without actual API calls. Fix: prompt-level rule + code-level watchdog that suppresses fake XML patterns. | Excerpt 1 (Ouroboros/MiniMax) | Directly relevant to FA inner-loop: weaker OSS models (Qwen, Kimi, GLM) may exhibit same pattern. ADR-7 §5 input validation catches malformed calls but not hallucinated ones embedded in thought text. Worth a BACKLOG item. |
| 15 | **Security sandbox for TG/chat ingestion** — prompt injection screening before entity extraction; untrusted input never directly enriches knowledge graph | Community pattern | Applicable when FA adds any external input pipeline (web search, user-uploaded docs). ADR-6 sandbox currently covers tool execution but not knowledge ingestion. |
| 16 | **Cross-source linking** — concept from Arxiv found in code → edge in graph. Retrieval returns "this algorithm mentioned in 3 papers and implemented in loop.py:247" | Ouroboros architecture | Vision for Phase M+ when FA has both code (src/fa/) and research notes (knowledge/research/) — linking ADR decisions to implementing code via structural edges, not just prose references. |

### 3.3 — Agent design patterns

| # | Pattern | Source | FA mapping |
|---|---|---|---|
| 17 | **Multi-persona parallel** — Architect/Developer/Inspector/Researcher (+ proposed Oracle/Archivist/Harmonizer/Skeptic). Each with own scratchpad. | Dmitry/Тезей | FA uses ADR-2 tiering (Planner/Coder/Debug/Eval) — different names, same architecture. Could compare role boundaries. |
| 18 | **Three types of reflection** — Content (what happened), Process (how I did it), Premise (was the task even right?) | Community | Premise reflection is missing from FA's feedback loop. Worth considering for BACKLOG eval-harness design. |
| 19 | **Decomposed tasks + frontier for integration** — smaller MOE models handle individual functions, frontier model reasons about integration | @MrRichSylvester | Exactly FA's ADR-2 tiering philosophy. Validates our approach from independent source. |
| 20 | **Speciation of forks** — DPC-agent diverged from Ouroboros after ~30 sessions, no longer meaningful to PR back. "Not a fork, it's speciation." | DPC | General observation about fork divergence timelines. Relevant for our fork2 relationship with upstream. |
| 21 | **Convergent evolution** — DPC and Enox independently arrived at same knowledge graph model (typed edges, provenance-first, hybrid search, federation planned). "Both independently arriving at the same model is an argument that the model is correct." | DPC + Enox | If FA's ADR-3+4 (Mechanical Wiki + SQLite FTS5) converges with these patterns, it validates our direction. Worth checking. |
| 21a | **Convergent evolution — third independent confirmation** (added 2026-05-13 post-soviet-code deep-dive): `Disentinel/soviet-code`'s `src/nomenklatura.ts` `EnoxBackend.toAssertion` uses the **same typed-assertion shape**: `{source_name, source_type, target_name, target_type, relation, confidence, context}` — identical to DPC's KG schema and Enox proper. Three independent projects now converge on this contract; `BothBackend` also demonstrates the «mirror writes with graceful fallback» pattern (Promise.allSettled). Strong evidence to adopt this assertion-shape verbatim when FA's KG lands. | DPC + Enox + soviet-code | When FA designs its KG (post-ADR-3+4), copy this 7-field typed-assertion record as the wire/storage contract. Pluggable Local/Remote/Both backend in `nomenklatura.ts:184-201` is a working reference implementation. |

### 3.4 — Identity & trust

| # | Pattern | Source | FA mapping |
|---|---|---|---|
| 22 | **Cryptographic node identity** — `dpc-node-{sha256(rsa_pubkey)[:32]}`, key-based not location-based, stable across IP changes | DPC | Not needed for FA v0.1 (single-user), but reference for future multi-agent identity. |
| 23 | **Dunbar-limited access control** — trust as function of social proximity, graduated layers | DPC | Not needed for FA v0.1 scope. |
| 24 | **Perspective model** — named, versioned "lenses" over shared knowledge graph | Enox | Interesting for multi-role access to same knowledge store — each ADR-2 role could have a "perspective" that filters what it sees. |
| 25 | **Content vs chain signing** — two separate integrity guarantees for different threat models | DPC | Knowledge about signing strategies; no immediate FA use. |

### 3.5 — Meta / philosophical

| # | Pattern | Source | FA mapping |
|---|---|---|---|
| 26 | **Four principles for complexity reduction** — (1) externalizes, (2) describes relations not things, (3) cheap to operate, (4) named as you think. When all 4 converge → "cascade resonance" — complexity vanishes | @ai_sapience_bot / Вадим | Good evaluation heuristic for FA tool/artifact design choices. Compare to our minimalism-first 4-question test (AGENTS.md rule #10). |
| 27 | **URL as knowledge entity identifier** — passes all 4 principles; versioned URL (.../concept@v3) adds temporality | Вадим | FA uses file-path-based identity (filesystem-canonical). URL adds network addressability. Not needed for v0.1. |

---

## §4. Concrete ADR / BACKLOG items to extract in next session

1. **BACKLOG candidate: tool-call hallucination watchdog** — inner-loop
   dispatcher should detect when model embeds pseudo-tool-calls in
   thought text (not actual API tool_calls). Pattern #20 from chat.
   ADR-7 §5 validation catches malformed calls but not hallucinated ones.

2. **BACKLOG candidate: Grafema audit of FA codebase** — when `src/fa/`
   has enough code (post inner-loop scaffolding PR), run Grafema
   cross-file analysis to catch boundary drift. Low priority, high
   future value.

3. **Design reference: structured pre-flight ritual comparison** —
   Protocol 13 (7 sources) vs FA HANDOFF §bootstrap (3 steps). Are we
   missing anything? Candidate for AGENTS.md refinement.

4. **Design reference: "trigger gated / content autonomous"** — useful
   articulation for Phase M runner. Human decides when to start/stop
   session; agent decides what to load. Worth adding to architectural
   vocabulary.

5. **Design reference: skills-over-tools layering** — Memento-Skills
   pattern shows skills as multi-tool strategies (.md files with
   branching logic), distinct from atomic tools. FA SKILL.md pattern
   already exists in Devin ecosystem but not in our ADR stack.

6. **Cross-reference validation: convergent architecture** — DPC and
   Enox independently arrived at typed-edge provenance-first KG with
   hybrid search. Does FA ADR-3+4 converge with the same core model?
   If so, validation. If not, study divergence reasons.

---

## §5. DPC-Messenger ADR list to study (docs/decisions/)

Referenced in chat, not opened yet. Known ADRs mentioned:
- **ADR-009** — human-gated knowledge extraction (noise problem)
- **ADR-017** — P2P knowledge search (stateless pull model: KNOWLEDGE_SEARCH_REQUEST/RESPONSE)
- **ADR-024** — Knowledge Graph (450 nodes, 636 edges, FAISS+BM25 hybrid, RSA-signed commits, Phase 3 = P2P federation)

Full list at: `github.com/mikhashev/dpc-messenger/tree/main/docs/decisions`
→ Dedicate one session to reading all ADRs, comparing to FA ADR-1..7.

---

## §6. Key formulations worth adopting into FA vocabulary

| Formulation | Meaning | Source |
|---|---|---|
| "convergent data, divergent transport" | Same data model, different sync mechanisms | Ираида |
| "trigger gated / content autonomous" | Human controls when, agent controls what | DPC |
| "speciation" (vs fork) | When a fork diverges past meaningful PR-back | DPC |
| "semantic merge, not diff-merge" | Work with what was said, not how written | DPC |
| "cascade resonance" | When all principles converge → complexity vanishes | Вадим |
| "graph entropy" | Accumulation of redundant/contradictory nodes from re-extraction | Ираида |
| "silence as typed event" | Log non-actions with rationale | Ираида |
| "premise reflection" | Questioning whether the task itself was correctly formulated | Community pattern |

---

## §7. Session plan for cross-reference deep-dive

**Session scope:** 1 session, ~90 min equivalent

1. Open `github.com/mikhashev/dpc-messenger/tree/main/docs/decisions` —
   read ADR-009, ADR-017, ADR-024. Compare to FA ADR-1..7.
2. Open `github.com/Disentinel/grafema` — read README, understand
   capabilities, check if FA codebase can be analyzed.
3. Open `github.com/Disentinel/enox` — read architecture, check for
   confidence tiers / perspective model implementation.
4. Open `github.com/AndyMik90/Aperant` — first pass, identify relevance.
5. Open `github.com/zzet/gortex` — first pass, identify relevance.
6. Produce findings report: what to adopt, what to BACKLOG, what to
   skip (with reason per minimalism-first test).

---

## §8. Source extract locations (for re-reading if needed)

These files lived on the previous session's VM. If user re-attaches them,
they will appear at similar paths:

- Excerpt 1 (pre-ADR-6, ~325 lines): originally `/home/ubuntu/attachments/<uuid>/+++1.md`
- Excerpt 2 (post-ADR-7, ~741 lines): originally `/home/ubuntu/attachments/<uuid>/+++2.md`

If the new session needs deeper quotes, ask the user to re-attach.

---

## §9. Glossary (FA-specific terms used above)

| Term | Meaning | Source |
|---|---|---|
| ADR-2 | LLM Tiering decision (Planner/Coder/Debug/Eval) | `knowledge/adr/ADR-2-llm-tiering.md` |
| ADR-3 | Mechanical Wiki (filesystem-canonical Markdown + SQLite FTS5) | `knowledge/adr/ADR-3-mechanical-wiki.md` |
| ADR-4 | Active-recall / search layer choice (SQLite FTS5 over Qdrant for v0.1) | `knowledge/adr/ADR-4-active-recall.md` |
| ADR-6 | Tool sandbox (deny-by-default path + tool-group allow-list) | `knowledge/adr/ADR-6-sandbox.md` |
| ADR-7 | Inner-loop + tool-registry contract | `knowledge/adr/ADR-7-inner-loop-tool-registry.md` |
| BACKLOG I-1..I-8 | Pending items in `knowledge/adr/BACKLOG.md` | inline IDs |
| AGENTS.md rule #10 | Minimalism-first 4-question test before adding a feature | `AGENTS.md` |
| Phase M | Future runner phase (post-v0.1 orchestrator) | HANDOFF.md / BACKLOG |
| Mechanical Wiki | FA's knowledge store: file-as-truth + deterministic indexing | ADR-3 |
| SKILL.md | Devin convention for reusable procedural knowledge | Devin docs |
| llms.txt | FA's canonical routing index for LLM context discovery | `knowledge/llms.txt` |

---

*End of cross-reference list.*
