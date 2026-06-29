# Kronos Agent OS — deep dive for First-Agent inspiration

Repo: https://github.com/spyrae/kronos-agent-os (a.k.a. **KAOS**)
Local clone: `/home/ubuntu/research/kronos-agent-os` (shallow `--depth=50`)
Scope: focused research note on the four axes you asked for —
**SQLite + FTS5 + Qdrant + Knowledge Graph memory stack, Skills system, Swarm mode, Capability gates** —
plus a smaller "Adjacent patterns worth stealing" appendix.

Format mirrors the previous Gortex/Aperant briefs:
- TL;DR table (top picks across the four axes)
- Tier-1 / Tier-2 / Tier-3 file lists with FA-application notes
- "What NOT to copy" / "What's overkill for FA"
- Recommended starter set ("if you port 5 things, port these")
- Appendix: adjacent patterns we found while reading

All paths below are relative to the repo root unless prefixed. Research-only; no PR, no code changes.

---

## TL;DR — top 10 files across all four axes

| # | File | LOC | Axis | Why it matters for FA |
|---|------|-----|------|----------------------|
| 1 | `kronos/memory/fts.py` | 306 | Memory | FTS5 + Ebbinghaus decay + tiering (active/warm/cold/archive) in one self-contained module. Drop-in alternative to FA's "Wiki gets too big" problem — gives you a real "forgetting curve" without a vector DB. |
| 2 | `kronos/memory/hybrid.py` | 188 | Memory | Concrete score-normalisation + MMR re-ranking + temporal decay across vector and keyword channels. Best small example of "hybrid search done right". |
| 3 | `kronos/memory/knowledge_graph.py` | 260 | Memory | Tiny entity/relation store on plain SQLite (no Neo4j). 1–2-hop traversal formatter for LLM injection. Direct port to FA's `notes/world/` layer. |
| 4 | `kronos/swarm_store.py` | 841 | Swarm | The single cleanest **SQLite-as-coordination-bus** I've read. `BEGIN IMMEDIATE` claim arbitration replaces a pub/sub bus for N-agent races. Even if FA stays single-agent, the `SafeDB` + claim idiom is reusable. |
| 5 | `kronos/group_router.py` | 441 | Swarm | "Each agent independently decides whether to reply" — 3-tier router (explicit / relevance / peer-reaction) with per-agent cooldowns and "addressed to someone else" guard. Reusable for FA-as-second-opinion mode. |
| 6 | `kronos/skills/store.py` | 339 | Skills | Filesystem-canonical skill loader with YAML frontmatter, manifest generation, shared-overlay layering, `draft` vs `active` status. This is the **most directly FA-compatible** part of KAOS — Mechanical Wiki has the same DNA. |
| 7 | `kronos/skills/hub.py` | 190 | Skills | Import-from-`github:user/repo/path` with safe-slug validation, name collision guard, and `review_required: true` on every external import. Solves the "how does FA accept community skills safely" question. |
| 8 | `kronos/config.py` (lines 62–69) + `kronos/tools/sandbox.py` | 193 | Capability gates | The five-flag opt-in model (`ENABLE_DYNAMIC_TOOLS`, `REQUIRE_DYNAMIC_TOOL_SANDBOX`, `ENABLE_MCP_GATEWAY_MANAGEMENT`, `ENABLE_DYNAMIC_MCP_SERVERS`, `ENABLE_SERVER_OPS`) + Docker-sandbox fail-closed. Maps 1:1 onto FA's "sandbox is deny-by-default" stance. |
| 9 | `kronos/security/loop_detector.py` + `shield.py` + `output_validator.py` + `cost_guardian.py` + `pii.py` | 99 + 205 + 104 + 91 + 91 | Capability gates | The five-layer defense suite — input shield, sanitize, loop detector with WARN/CRITICAL/CIRCUIT_BREAKER, output redactor, daily/session $ budget guardian, PII masking everywhere logs touch. Each file is small, self-contained, copy-pastable. |
| 10 | `kronos/db.py` (SafeDB) | 207 | Memory + Swarm | Single-connection, lock-serialized SQLite with WAL + auto-reconnect + `BEGIN IMMEDIATE` writes. The substrate everything else stands on. If you only steal one infra file from KAOS, steal this. |

The two "out of category" but worth-knowing files:

- `kronos/cron/sleep_compute.py` (237 LOC) — nightly "consolidate facts → extract entities → relations → insights → archive stale" pass. This is the natural fit for FA's Mechanical Wiki maintenance.
- `kronos/cron/skill_create.py` (277 LOC) — agent observes its own audit log, finds repeatable patterns, drafts a new skill (status=`draft`, `review_required=true`). FA's "Exploration DAG → distilled skill" closing of the loop.

---

## Part 1 — Memory stack (SQLite + FTS5 + Qdrant + KG)

KAOS does **not** use a single fancy memory system. It composes four cheap things:

1. **`session.db`** — conversation history per `thread_id` (per-agent, per-chat, per-topic).
2. **`memory_fts.db`** — FTS5 keyword index over extracted facts, with Ebbinghaus decay columns (`relevance`, `tier`, `last_accessed`).
3. **`qdrant/`** — local-mode Qdrant collection (per-agent) holding vector embeddings of the same facts. Embeddings via HuggingFace `multi-qa-MiniLM-L6-cos-v1` (384 dims), facts extracted via DeepSeek for cost.
4. **`knowledge_graph.db`** — plain SQLite (entities + relations) for relationship-heavy recall.

Plus a fifth, **shared** across agents: `swarm.db.shared_user_facts` — "facts derived from USER messages" are mirrored here so all 6 agents converge on one view of the user.

What's clever is that **recall = parallel vector + keyword + graph, merged with MMR + temporal decay**. Not "pick a backend".

### Tier 1 — must read

**`kronos/db.py`** — `SafeDB` (207 LOC). Single connection per database, `threading.Lock` around every read/write (because sqlite3 connection objects are not thread-safe even in WAL mode), WAL + `busy_timeout=30000` + `wal_autocheckpoint=100`, `BEGIN IMMEDIATE` for writes, auto-reconnect on `OperationalError`. **FA application**: this is what you replace "ad-hoc sqlite3 + filesystem locks" with. The whole rest of the memory stack depends on it.

**`kronos/memory/store.py`** — Mem0 + HuggingFace + local Qdrant wiring (166 LOC). The `search_memories(query, user_id, limit=5)` function runs vector search via Mem0, runs FTS5 in parallel, then calls `merge_hybrid_results()`. `add_memories()` extracts facts with a cheap model (DeepSeek), then indexes into FTS5 **in parallel** — failures in either path do not crash the chat. **FA application**: even if FA stays vector-free, the "fact extraction with cheap LLM → durable index" pattern is a clean abstraction to copy. Note the cost economics: facts ≠ messages, and the index is the asset.

**`kronos/memory/fts.py`** — FTS5 with Ebbinghaus decay (306 LOC). Two tables: `memory_facts` (id, user_id, content, source, created_at, mem0_id) + `memory_fts` virtual table (with `UNINDEXED user_id` so per-user filtering doesn't break tokenization). Three migrations add `relevance REAL DEFAULT 1.0`, `tier TEXT DEFAULT 'active'`, `last_accessed TEXT`. Three behaviours that matter:
  - `search()` orders by `rank * (1.0 / relevance)` and filters out `tier='archive'` — popular facts surface first, dead facts vanish without being deleted.
  - `touch_facts()` bumps `relevance += 0.05` (capped at 1.0) when a fact is recalled — implicit reinforcement.
  - `decay_all_facts(half_life_days=14)` is the nightly job: `new_relevance = relevance * 2^(-days_since_access / half_life)`, then re-tiers: `active >=0.6`, `warm 0.3-0.6`, `cold 0.1-0.3`, `archive <0.1`.
  - Query sanitization strips FTS5 operators and quotes tokens to prevent syntax errors from user-supplied queries.

**FA application**: this gives FA's Mechanical Wiki a **forgetting curve without deleting anything**. Every fact stays, but stale ones drop off the active search frontier. Almost zero ops overhead vs a vector DB. The decay column is the entire learning loop in 4 numbers.

**`kronos/memory/hybrid.py`** — score normalization + MMR (188 LOC). Weights: `VECTOR_WEIGHT=0.7`, `TEXT_WEIGHT=0.3`, `MMR_LAMBDA=0.7`, `DECAY_HALF_LIFE=60` days. Pipeline:
  1. Normalize vector scores (cosine already 0–1) + FTS5 scores (negative BM25 → 0–1 via `1 / (1 + abs(rank))`).
  2. Merge by text key; if a fact appears in both channels, score gets a `+20%` boost.
  3. Apply temporal decay: `score *= 2^(-age_days / 60)`.
  4. Greedy MMR select to balance relevance vs diversity.

**FA application**: this is the cleanest 150-LOC reference implementation of "hybrid search" I've seen — `merge_hybrid_results()` is the function. Even if you don't implement vectors, the **score-normalize-then-merge** template is reusable for "ripgrep + symbol-graph + recent edits" hybrid search inside FA.

**`kronos/memory/knowledge_graph.py`** — SQLite KG (260 LOC). Schema:
  - `entities(id, name, type, properties JSON, created_at, updated_at)` with `UNIQUE(name, type)`.
  - `relations(source_id, target_id, relation_type, properties, created_at)` with `UNIQUE(source_id, target_id, relation_type)`.
  - Entity types: `person | company | project | concept | tool | location | event`.
  - Relation types: `knows | works_at | uses | owns | related_to | part_of | created`.
  - `get_connections(entity_name, depth=1)` does 1–2-hop traversal in pure SQL.
  - `get_graph_context(query, limit=5)` searches entities and returns a formatted string for direct LLM injection.

**FA application**: this is the cheapest possible KG and it works. FA's `notes/world/` can store entities and relations in the same shape; the `get_graph_context()` formatter is the right "graph → string" abstraction. **Don't** reach for Neo4j until SQLite hurts.

**`kronos/memory/context_engine.py`** — pluggable context strategy (182 LOC). Three implementations behind one `ContextEngine` ABC:
  - `SummarizeEngine` — when `len(messages) > 30`, summarize old, keep 6 recent. ~$0.01 per compaction.
  - `SlidingWindowEngine` — truncate to last 20. $0.
  - `HybridEngine` — sliding window + flush old to Mem0 at threshold. ~$0.005 per flush.
  - `assemble()` hook lets the engine inject memories as `SystemMessage` before the LLM call.

Strategy is config-driven (`context_strategy: "summarize" | "sliding_window" | "hybrid"` in `Settings`). **FA application**: this is the "context budget" knob FA needs. Today FA assumes the agent will manage its own context; this gives the runtime a strategy slot. The `HybridEngine` (window + durable flush) is the most ambitious and probably the right default once Mechanical Wiki is wired.

**`kronos/memory/compaction.py`** (172 LOC) — concrete summarization with **identity preservation**. The prompt is worth reading: it explicitly says "preserve verbatim UUIDs, hashes, tokens, URLs, paths, batch progress, decisions+reason, TODOs, names, dates, sums — do not paraphrase". Chunks at 6000 chars when the conversation is long, summarizes each chunk, merges. **FA application**: stealable prompt template. The "what to preserve verbatim" list is exactly the kind of thing that breaks naive summarization.

**`kronos/memory/nodes.py`** (163 LOC) — `retrieve_memories(state)` builds a `SystemMessage` from {shared facts + personal memories + KG context} before the LLM call. `store_memories_background(state)` after-the-fact extracts the last user-assistant turn into facts + mirrors user-sourced facts into the shared swarm ledger. **FA application**: the **shape of the SystemMessage injection** is the key — it's an obvious "L4 retrieval" before the model.

### Tier 2 — read if working on memory

- `kronos/cron/sleep_compute.py` (237 LOC) — nightly memory consolidation pipeline: dedupe similar facts, extract entities/relations into KG, generate insights, archive stale (>90d, low relevance). Three explicit phases with a notification at the end. **FA application**: this is the natural fit for FA's Mechanical Wiki maintenance pass (the "monthly hygiene" cron). Note the explicit prompts:
  - `ENTITY_EXTRACTION_PROMPT` constrains output to JSON, says "Only extract clearly stated facts, don't infer", "Normalize names".
  - `INSIGHT_PROMPT` is run separately after entity extraction.
- `kronos/cron/skill_create.py` (277 LOC) — the "agent observes its own audit log, finds patterns, drafts a skill" loop. Reads `logs/audit.jsonl` for the last 7 days, filters complex sessions (`tool_calls_count >= 5 || supervisor_steps >= 3`), deduplicates via token overlap, asks an LLM to draft a SKILL.md with `status=draft`, `review_required=true`. **FA application**: this is the closing of the **Exploration DAG → distilled skill** loop. The dedupe heuristic (`_simple_token_overlap`) is intentionally cheap; it doesn't try to be smart.
- `kronos/session.py` (246 LOC) — durable session history with FTS5 over message content. `SessionStore.load(thread_id)` / `save(thread_id, messages)`. Per-message fingerprint (added later via migration) to dedupe. **FA application**: simpler than memory; just shows how to persist langchain `BaseMessage` lists into SQLite with FTS over the text.
- `kronos/router.py` (47 LOC) — message tier classifier (LITE vs STANDARD LLM) based on length + RU/EN keyword lists. **FA application**: tiny and crude, but it's the kind of "0-latency LLM-tier gate" that adds up — similar in spirit to Gortex's bash classifier.

### Tier 3 — context only

- `kronos/llm.py` (623 LOC) — provider-chain resolution with cooldowns and a fallback adapter for arbitrary OpenAI-compatible providers. Useful **as a reference** for how to keep multiple providers behind one `get_model(tier)` call. Most of this is too provider-specific to port; the **cooldown idea** (failed provider goes into a 5-minute timeout) is what's portable.
- `kronos/state.py` — `AgentState` TypedDict — minimal, mostly just `messages`, `user_id`, `session_id`, `safety_passed`, `loop_detector`. **FA application**: shows what the per-request shared state needs to carry between pipeline nodes.

---

## Part 2 — Skills system

KAOS's skill system is the part most directly compatible with FA's Mechanical Wiki: it's **filesystem-canonical** and uses **progressive disclosure** (L1 catalog → L2 protocol → L3 references). It's also small — three files do 80% of the work.

The data model:

```
workspaces/<agent>/self/skills/
└── <skill-name>/
    ├── SKILL.md           # YAML frontmatter + protocol body
    └── references/        # optional supporting files
        ├── WATCHLIST.md
        └── CRITERIA.md
```

Frontmatter is intentionally minimal: `name`, `description`, `status` (`active|draft`), `version`, `author`, `tags`, `tools`, `tier`, plus import-tracking fields (`imported_from`, `source_url`, `imported_at`, `review_required`).

### Tier 1 — must read

**`kronos/skills/store.py`** (339 LOC) — the loader. Read it end-to-end; it's small. Key behaviours:
  - `_parse_frontmatter()` handles flat `key: value`, YAML folded scalars (`>`, `|`), and inline lists (`[item1, item2]`). It's a 30-line implementation that intentionally does **not** depend on PyYAML — handy for portability.
  - `SkillStore.__init__()` supports **shared workspace overlay**: if `SHARED_WORKSPACE_PATH` is set, shared skills are loaded first and per-agent local skills overlay them by name. **FA application**: clean way to ship community-curated skills as a base layer and let users override.
  - `_load_all()` calls `_generate_manifest_file()` after each scan — produces a single human-readable `manifest.md` listing all skills, which doubles as docs and a "what's installed" surface.
  - `build_catalog()` produces the **L1 catalog string** that gets injected into the system prompt: 50–100 tokens per skill (name + description + tags + tier + ref names). This is the only thing the LLM sees by default.
  - `add_skill()` writes a new SKILL.md to disk and registers in-memory. `update_status(name, status)` flips between draft/active by rewriting the frontmatter.
  - Reference discovery: any `.md` file in `references/` becomes loadable via `load_skill_reference(skill, ref_name)`.

**FA application**: this is the cleanest reference for FA's "skills/procedures" layer. The L1/L2/L3 progressive disclosure is exactly what FA needs to keep system prompts small. Status-as-frontmatter (`draft` vs `active`) is the simplest possible "approval gate" model.

**`kronos/skills/tools.py`** (119 LOC) — the four LangChain tools exposed to the agent:
  - `load_skill(skill_name)` — returns full SKILL.md body. If `status == "draft"`, prepends a `⚡ Это черновик навыка, созданного автоматически. Если он полезен — скажи 'одобрить skill ...'`. So drafts are visible to the LLM but advertised as "tell me to approve if useful".
  - `load_skill_reference(skill_name, reference_name)` — load an L3 file.
  - `approve_skill(skill_name)` — flip `draft` → `active`. **The user does this through chat**: "approve skill X" → the supervisor calls this tool. Beautiful — no admin panel needed.
  - `import_skill_from_source(source)` — defers to `hub.import_skill()`.

**FA application**: the **conversational approval** path (`approve_skill` via chat) is the elegant part. FA can adopt this directly: "approve this gotcha" / "approve this procedure" as tool calls instead of a separate admin flow.

**`kronos/skills/hub.py`** (190 LOC) — import from URL or `github:user/repo/path`:
  - `_parse_github_source()` resolves `github:user/repo/skill-name` to `https://raw.githubusercontent.com/user/repo/main/skill-name/SKILL.md`. Rejects `..` in the path.
  - `_validate_skill_package()` requires `name` (matching `^[a-z0-9][a-z0-9_-]{0,79}$`), `description`, non-empty body. Pre-flight before touching the filesystem.
  - On import:
    - Name collision → reject ("Remove it first to re-import"). No silent overwrite.
    - Status is forced to `draft`, `review_required: true`, tags get `external` and `imported` appended.
    - `imported_from`, `source_url`, `imported_at`, `created_by`, `imported_original_status` are all recorded — full provenance.

**FA application**: this is the answer to "how does FA accept community skills without becoming a malware vector". Force every external import into draft + review_required + provenance. The pattern is small enough to port wholesale.

### Tier 2

- `docs/SKILLS.md` (170 LOC) — the design doc. Three things worth reading:
  - **Progressive disclosure rationale**: "L1 always in system prompt; L2 loaded only when matched; L3 loaded only when the protocol references it". This is the cost argument for the architecture.
  - **Minimal SKILL.md template**: frontmatter + `## Trigger` + `## Protocol` + `## Output`. Three sections, that's it.
  - **Install/disable flow**: "Place a folder under skills/" / "Remove or rename to disable". Filesystem-canonical the way FA already likes.
- `templates/skill-packs/{research,content,ops,productivity,finance-lite}/` — five reference packs. Each is `pack.yaml` (name, description, capabilities, skills, examples) + one skill folder. The skill bodies are tiny (10–30 LOC each) and follow the `## Protocol / ## Output` template strictly. **FA application**: copy the pack structure for distributing FA's curated procedures (e.g., "FA hygiene", "FA recovery", "FA spec-write").
- `templates/agents/personal-operator/template.yaml` — agent profile template. Worth a look: `memory_defaults`, `capability_policy`, `example_prompts`. **FA application**: shows how to ship a pre-configured agent persona without committing all the workspace files.
- `kronos/cron/skill_improve.py` (177 LOC) — nightly pass that looks at skill usage in the audit log and proposes edits to existing SKILL.md files. Companion to `skill_create.py`. **FA application**: this is the "skills that are used a lot get refined, skills that are never used get pruned" loop.

### Tier 3

- `kronos/cron/skill_create.py` (also Tier 2 above for memory) — note the dedupe approach (`_simple_token_overlap`) and the constraints (`MIN_TOOL_CALLS = 5`, `MIN_SUPERVISOR_STEPS = 3`). Pragmatic cutoffs over learned thresholds.

---

## Part 3 — Swarm mode

Swarm mode in KAOS is **optional** — KAOS works fine as a single agent. When you turn it on, each agent runs as **a separate OS process** with its own Telegram account, workspace, and memory. The whole coordination layer is **one SQLite file** + per-agent group routers. There is no message bus, no leader election, no RPC.

This is the "minimum viable swarm" — and it's both the most surprising and most portable part of KAOS.

### Mental model

```
6 agents (separate processes)
        │
        ▼ (each sees every group message)
   GroupRouter (per agent)  ──► decides: should I respond?
        │
        ▼ (yes)
   SwarmStore.claim_reply()  ──► insert into reply_claims
        │
        ▼ (after eta delay)
   SwarmStore.can_send_claim()  ──► IMMEDIATE TX: am I still winner?
        │
        ├── won  ──► send reply ──► mark_sent
        └── lost ──► cancel claim
```

Winner rule: `ORDER BY tier ASC, eta_ts ASC, agent_name ASC`.

### Tier 1 — must read

**`kronos/swarm_store.py`** (841 LOC) — the shared ledger facade. Read at least the first ~500 lines. Key parts:

1. **Schema** (lines 63–155):
   - `swarm_messages` — every observed message (PRIMARY KEY `(chat_id, topic_id, msg_id)`, indexes on `recent`, `replies`, `agent`).
   - `reply_claims` — the coordination table. `UNIQUE(chat_id, topic_id, trigger_msg_id, agent_name)` makes claims idempotent. Indexes on `active` (state-filtered) and `winner` (the exact order used in arbitration).
   - `swarm_metrics` — durable counters (`addressing_violations`, `duplicate_replies`). Lives here because every agent agrees on this table.
   - `shared_user_facts` — cross-agent view of the user. Heuristic v1: "facts from USER messages go here; facts from the agent's own reflections stay per-agent". No LLM classifier.
   - `session_messages` later gets a `fingerprint` column via `ALTER TABLE`. Migrations are inline and idempotent.

2. **`can_send_claim()`** (lines 355–426) — the heart of swarm coordination. Runs under `BEGIN IMMEDIATE`:
   - Lazy-expire claims older than 120s (`CLAIM_EXPIRY_SECONDS`) — handles crashed agents.
   - Tier 1 (explicit address) → always wins, bypasses cap.
   - Anti-flood cap: count `sent` replies for this `root_msg_id` (Tier 2+); reject if `>= DEFAULT_MAX_IMPLICIT_REPLIES = 2`.
   - Winner lookup: `ORDER BY tier ASC, eta_ts ASC, agent_name ASC LIMIT 1`. If that's not me, I lose.
   - Returns `ClaimOutcome(won: bool, reason: str)`.

   This is the **"replace pub/sub with one IMMEDIATE transaction"** pattern. Two agents racing → SQLite serialises them → exactly one wins. No external broker.

3. **`record_inbound_message` / `record_outbound_message`** — idempotent via PRIMARY KEY. Agents post their own outbound messages with `sender_id = -1` because Telethon doesn't give the bot's id until next poll.

4. **`shared_user_facts`** management (in the lower half) — `add_shared_fact()` is idempotent on `(user_id, fact)`. `touch_shared_fact()` bumps `last_accessed_at` and `access_count`. Same Ebbinghaus pattern as `memory/fts.py`.

**FA application**: even if FA stays single-agent, this is the cleanest example of **SQLite-as-arbitration** I've read. Anywhere FA has "concurrent writers might step on each other" (e.g., parallel tool calls writing to Mechanical Wiki), the `BEGIN IMMEDIATE` + UNIQUE-constraint + winner-rule pattern applies. The `_db.write_tx(_tx)` idiom in `SafeDB` is the wrapper.

**`kronos/group_router.py`** (441 LOC) — per-agent routing logic. Three tiers + a guard:

- **Cross-agent addressing guard**: if the user @-addresses agents A and B, agents C/D/E/F skip silently. Implemented by parsing `target_agents` set from the message text and checking `explicit_to_other and not explicit_to_me`. This is the patch for "Impulse answers when Nexus was addressed".
- **Tier 1 — explicit** (delay 1–5s): `@mention` of my username, reply to my message. Cap-exempt.
- **Tier 2 — relevance** (delay 5–20s, **user messages only**): LLM quick-check "is this my domain? score 1–10, respond if >=7". Skipped if another known agent is addressed.
- **Tier 3 — peer reaction** (delay 15–45s, **bot messages only**): another bot replied to a user → "do I meaningfully disagree?". Guards:
  - 5-minute cooldown (`PEER_REACTION_COOLDOWN = 300`).
  - `_reacted_to_msgs` set so a single message can't be reacted to twice.
  - Requires a **user-root message** — peer→peer chains do NOT trigger reactions (otherwise bots argue with each other forever).

Aliases (`_alias_in_text`) use word-boundary matching with `(?:^|[^\w]) ... (?:$|[^\w])` so substring matches don't fire on unrelated words.

**FA application**: even single-agent FA can adopt the tiering for **"should I autonomously chime in"** vs **"explicitly invoked"**. The peer-reaction tier maps onto FA's "second-opinion mode" for code review.

**`agents.yaml`** (38 LOC) — single source of truth for agent identity in swarm mode:

```yaml
kronos:
  username: kronosagnt
  aliases: ["кронос", "kronos", "стратег"]
  role: "strategic advisor, chief of staff — priorities, planning, multi-model analysis"
```

`username` is the Telegram handle; `aliases` is the natural-language matcher; `role` is the one-line description used by the relevance LLM. Env vars (`AGENT_USERNAME_KRONOS=...`) override per-agent.

**FA application**: even a single FA agent should expose a `role` line that downstream consumers can match against. The pattern of "small YAML + env overrides" is right.

### Tier 2

- `docs/SWARM.md` (156 LOC) — the design doc. Worth reading for the **role taxonomy**: Researcher / Critic / Operator / Synthesizer. Useful framing for FA's role-routing.
- `kronos/bridge.py` (1343 LOC, large) — the Telegram bridge that wires `group_router → swarm_store → KronosAgent`. Don't read end-to-end; skim the request-handling section to see how `claim_reply / can_send_claim / mark_sent` are sequenced around the LLM call. **FA application**: pattern for "claim before doing work, confirm after" applies to any external action FA wants to make exactly-once.
- `kronos/cron/group_digest.py` — periodic digest of swarm activity. Lightly read; useful for the "what did the agents do today" surface.

### Tier 3

- `docs/SWARM_DEMO.md` — runs through a demo scenario. Useful only for context, not for code.

---

## Part 4 — Capability gates

KAOS's security/capability story is one of the cleanest I've read: **public-safe defaults**, **explicit env flags**, **fail-closed sandbox**, **layered defense at every boundary**, **PII masked at the observability surface**, **per-day and per-session $ budgets**.

There's no single "gate" file — it's the composition of:
- 5 env flags in `Settings` (`config.py`)
- 5 small security modules in `kronos/security/`
- Sandbox executor (`tools/sandbox.py`)
- Cost guardian (`security/cost_guardian.py`)
- Tool-call audit (`audit.py`)

### Tier 1 — must read

**`kronos/config.py` lines 62–69** — the five capability flags:

```python
# Capability gates — public-safe defaults.
enable_dynamic_tools: bool = False
require_dynamic_tool_sandbox: bool = True
enable_mcp_gateway_management: bool = False
enable_dynamic_mcp_servers: bool = False
enable_server_ops: bool = False
```

Every risky surface is opt-in. **`require_dynamic_tool_sandbox=True`** is the right default — even if you turn dynamic tools on, you still need Docker. This is **deny-by-default with a clear opt-in path**, not "trust the user".

**FA application**: copy this exact shape. FA's `sandbox` story should have the same flag set. Document each flag with one comment line explaining what enabling it unlocks.

**`kronos/tools/sandbox.py`** (193 LOC) — Docker sandbox for dynamic tool execution:
- `_docker_available()` + `_docker_image_available()` — both must be true.
- `sandbox_unavailable_message()` produces an operator-facing hint ("Sandbox image kronos-sandbox:latest is missing. Run `scripts/build-sandbox.sh`.").
- `build_sandbox_command()` is the **complete Docker command** for one execution:
  ```
  docker run --rm
    --memory=256m
    --network=none           # default; can be 'bridge' per call
    --cpus=1
    --pids-limit=50
    --read-only
    --cap-drop=ALL
    --tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m
    --security-opt=no-new-privileges
    --user=10001:10001
    --workdir=/code
    -v <tmpdir>:/code:ro
    kronos-sandbox:latest
    python /sandbox/runner.py
  ```
  Note the layering: read-only filesystem, dropped caps, no-new-privileges, non-root user, noexec tmpfs, no network by default. Every flag is a layer.
- `execute_sandboxed()` — if `REQUIRE_DYNAMIC_TOOL_SANDBOX=true` (the default) and Docker is unavailable, **return error**. Do not fall back to in-process exec. The fallback path exists only when the operator explicitly opts out of the sandbox.

**FA application**: this is the gold standard for FA's `ACI sandbox` story. The full Docker command is portable; the fail-closed semantics are critical. **Copy the flag list verbatim** unless you have a reason not to.

**`kronos/tools/dynamic.py`** (361 LOC) — dynamic tool creation. Two-layer validation:
1. Regex blocklist: `os`, `subprocess`, `shutil`, `pathlib`, `__import__`, `eval`, `exec`, `open`, `compile`, `globals`, `locals`, `getattr`, `setattr`, `delattr`. Pattern-based, fast.
2. AST validation: parse, allow only one `FunctionDef|AsyncFunctionDef`, disallow decorators / `*args` / `**kwargs`, allow only imports from `SAFE_IMPORTS = {json, re, math, datetime, collections, itertools, functools, hashlib, base64, urllib.parse, statistics}`. Reject top-level statements other than the function.

Then the generated code runs in the Docker sandbox (the regex+AST is defense in depth, not the only barrier).

**FA application**: even if FA never creates tools dynamically, the **two-layer (regex → AST) validation** pattern is reusable for anything FA accepts from an LLM that will be executed (skills, hooks, sandbox prompts). Don't trust pattern-matching alone; don't trust AST alone.

**`kronos/security/shield.py`** (99 LOC) — input shield. 25+ regex patterns covering: direct override (`ignore previous instructions`), role manipulation (`you are now DAN`), system-prompt extraction, credential extraction (`cat .env`, `echo $X_KEY`), encoding tricks (`base64 decode`, `eval(`, `exec(`, `__import__`). Plus Russian-language equivalents (`игнорируй`, `забудь`, `покажи ключ`). Rate limiter: `max_requests=10, window_seconds=60` per source. `validate_input()` returns rejection string or None.

**FA application**: this is a "cheap, conservative, no-LLM" shield. FA can borrow the patterns wholesale and add language-specific ones. The rate limiter is per-source, not global — so a misbehaving user can't lock out everyone else.

**`kronos/security/sanitize.py`** (179 LOC) — sanitize untrusted content **before** it reaches the LLM:
- `fold_homoglyphs()` — NFKC normalize so `Ｓｙｓｔｅｍ` → `System`, `𝐒𝐲𝐬𝐭𝐞𝐦` → `System`. Defeats homoglyph injection that would otherwise bypass the regex shield.
- `sanitize_text()` — fold homoglyphs, strip null/control chars, truncate lines >2000 chars (prevents context stuffing).
- `sanitize_html()` — strip hidden styles (`display:none`, `visibility:hidden`, `font-size:0`, white-on-white, `aria-hidden=true`, HTML comments, `<script>/<style>/<head>`). Solves the classic email-injection vector where the visible body is benign but a hidden `<div>` instructs the LLM.

**FA application**: anywhere FA pulls in external content (email summaries, web pages, GitHub PRs), pipe it through `sanitize_html()` or its equivalent. The homoglyph fold is **non-obvious** and matters.

**`kronos/security/loop_detector.py`** (205 LOC) — three loop detectors, three severity levels:

- **Detectors**:
  - `generic_repeat` — same tool + same args called N times.
  - `ping_pong` — alternating between two tools (`names[i] != names[i-1]` for >80% of last 20 calls).
  - `poll_no_progress` — same tool, same result hash repeatedly.
- **Levels**: `WARN_THRESHOLD = 10`, `CRITICAL_THRESHOLD = 20`, `CIRCUIT_BREAKER_THRESHOLD = 30`.
- **Response**: WARNING injects a nudge into the model's context; CRITICAL forces a strategy switch; CIRCUIT_BREAKER aborts the loop and returns a partial result. Each detector hashes its inputs and result for cheap comparison.

**FA application**: this is **the missing piece** for FA's "the agent is stuck in a fix-loop" detection. The three detectors cover the most common failure modes without needing a deep behavioral analysis. The level escalation (nudge → strategy → abort) is the right interaction model.

**`kronos/security/output_validator.py`** (104 LOC) — regex-based output redactor (no LLM):
- Secrets: `sk-[a-zA-Z0-9]{20,}`, `AIza...`, `AKIA...`, `ghp_...`, JWTs, connection strings, generic `password|secret|token|api_key = '...'`. Match → replace with `<first 4 chars>***REDACTED***`.
- System info: `/Users/<name>/`, `/home/<name>/`, `/root/`, `.env`, `Traceback (most recent call last)`, `File "...", line N`. Logged as `system_info` issue; not auto-redacted (just flagged).
- Prompt leakage: `IDENTITY.md`, `SOUL.md`, `AGENTS.md`, "system prompt", "you are an AI assistant", "I am a language model", "as an AI, I". Flag-only.

**FA application**: dirt cheap final pass before any response leaves the agent. Even if FA's outputs are mostly code, this catches the "model echoes a secret from the environment" failure mode.

**`kronos/security/cost_guardian.py`** (91 LOC) — daily + per-session $ budgets. `DEFAULT_DAILY_LIMIT_USD = 5.0`, `DEFAULT_SESSION_LIMIT_USD = 1.0`. `check_budget(session_id)` returns `(allowed: bool, reason: str)`. Reads aggregated cost from `cost.jsonl`. Warns at 80% of daily limit. **FA application**: FA already cares about "is this loop spending too much" — this gives you the API surface.

**`kronos/security/pii.py`** (91 LOC) — recursive PII masker over strings, mappings, lists, tuples, sets, and LangChain `BaseMessage`/`LLMResult` shapes. Patterns: email, credit card (last 4 preserved), RU/INT phone, RU passport, IPv4. **`mask_pii_object()` is what gets called everywhere the audit log or observability records data**. **FA application**: this is the "masking at the *observability* surface, not the user-facing surface" pattern. PII is hidden in logs/audit but still visible to the user in their own conversation. Right tradeoff.

**`kronos/audit.py`** (266 LOC) — tool-call lifecycle audit trail:
- Three JSONL files in `logs/`: `audit.jsonl` (request-level), `cost.jsonl` (token aggregation), `tool_calls.jsonl` (every tool event).
- `log_tool_event(event, payload)` — writes a redacted summary with `capability` (inferred from tool name), `approval_status`, `args_summary`, `result_summary`, `duration_ms`, `cost_usd`, `error`. **Raw args/results never leave memory** — only redacted summaries persist.
- `_infer_tool_capability(tool_name)` — pattern-matches `delegate_to_*`, `mcp_*`, `load_skill*`, `browser/search/fetch/exa/brave`, `expense/budget`, `server/ssh`, `dynamic/create_new_tool` → capability buckets. Useful for filtering audit logs by risk class.
- `redact_tool_payload()` — recursively scrubs `_token`, `_secret`, `_password`, `_api_key`, `_key` keys to `***REDACTED***`; also runs PII masking on strings; truncates to 500 chars.

**FA application**: this is FA's missing "tool-call audit" file. The capability inference + redaction + JSONL format is straight-up portable. The "raw never leaves memory" rule is the right default.

### Tier 2

- `docs/SECURITY.md` (260 LOC) — the design doc. Worth reading for the **5-layer defense framing** (Shield / Sanitize / Loop / Output / Cost). Also documents the approval queue (`logs/approval_queue.jsonl`) for capability requests that need human review. **FA application**: borrow the framing — "5 layers, each cheap, each composable". Cite specific patterns in your own SECURITY.md.
- `kronos/tools/gateway.py` (186 LOC) — MCP gateway with hot-reload. Persists dynamic MCP servers in `mcp_registry.db`. Gated by `enable_mcp_gateway_management` and `enable_dynamic_mcp_servers`. Even when enabled, `add_server` only updates the DB — tools require reload to activate. **FA application**: pattern for "add config, restart-required" actions.
- `kronos/tools/manager.py` (83 LOC) — load each MCP server independently; one server failing doesn't stop the rest. Sets `tool.metadata["mcp_server"] = name` so sub-agents can filter tools by origin. **FA application**: resilient loading with per-source labelling. Very small, very portable.
- `kronos/tools/server_ops.py` (518 LOC) — Level 1 (read-only: logs, status, health, DB queries) and Level 2 (whitelisted actions: restart services, deploy, clear cache) via asyncssh with key auth. Arbitrary shell **never** allowed. All commands derived from the YAML server registry. **FA application**: even if FA never SSHes anywhere, the **Level 1 / Level 2 / never-arbitrary** model is the right shape for any tool that touches infrastructure.
- `kronos/cli.py` (head ~150 LOC) — `kaos doctor` validates the environment before chat starts. Pattern: prefer an explicit pre-flight that says "missing FIREWORKS_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY" over a runtime failure mid-conversation. **FA application**: FA already has hygiene; doctor-style pre-flight is the natural CLI surface.

### Tier 3

- `kronos/tools/composio_integration.py` — Composio tools. Specific to that platform, not generally portable, but useful as a model for "external tool catalog with metadata".

---

## What NOT to copy / out of scope for FA

- **`kronos/llm.py` provider chain machinery** — 623 LOC of provider-specific adapters. FA's role-routing model is different; you don't need an open-ended provider chain with cooldowns. The **cooldown idea** is portable; the rest isn't.
- **`kronos/bridge.py`** (1343 LOC) — Telegram-specific transport. Only relevant if FA grows a chat interface. Pattern of "claim → eta delay → confirm" generalises, but the file as a whole doesn't.
- **`dashboard/` + `dashboard-ui/`** — FastAPI + a separate UI for memory/jobs/audit. Worth knowing the surface exists (`audit_trail`, `swarm`, `skills`, `memory`, `agents`, `performance`, `anomalies` are the routes), but FA shouldn't build a dashboard before it has something to observe. **Defer**.
- **Qdrant local mode + Mem0** — heavy dependency surface for what FA likely doesn't need yet. The **hybrid search pattern** (`memory/hybrid.py`) is portable to a vector-less FA (e.g., embedding-free FTS + symbol-graph + recent-edit recency); the Qdrant wiring itself is overkill.
- **Telegram-forum routing** (`telegram_swarm_chat_id`, `telegram_general_topic_id`, etc.) — transport detail. Skip.
- **Agent.example.yaml multi-agent role taxonomy** (Researcher / Critic / Operator / Synthesizer) — useful as **framing**, but don't ship FA as a 6-process swarm. The swarm is optional in KAOS for a reason.

---

## Highest-leverage "if you only port 5 things"

In priority order, with rough Python LOC estimate for a clean FA port:

1. **`SafeDB` + capability gate env flags + Docker sandbox command** (~400 LOC). Foundation. Everything else builds on the lock-serialized SQLite + the deny-by-default flag set + the precise Docker invocation in `sandbox.py`.

2. **`memory/fts.py` Ebbinghaus decay + tiering** (~300 LOC). Drop into FA's `notes/` as the "facts that decay" layer. Combine with FA's existing Markdown-based wiki — facts get a tier, tier=archive falls out of the active search frontier without being deleted.

3. **`security/loop_detector.py` 3-detector × 3-level escalation** (~200 LOC). Solves FA's "stuck in fix loop" detection cleanly. Wire into FA's ReAct/Exploration DAG so circuit-breaker → write a NOTE to the DAG saying "stop trying X".

4. **`skills/store.py` + `skills/tools.py` + `skills/hub.py` progressive disclosure + conversational approval + safe import** (~600 LOC, but each file is small and self-contained). Maps directly onto FA's Mechanical Wiki for skills/procedures. The `approve_skill` via chat is the elegant detail.

5. **`audit.py` JSONL tool-call trail with redaction + capability inference** (~250 LOC). FA needs this for "what did the agent actually do" surface, especially as it gains autonomy. Pair with `security/pii.py` (~90 LOC) so audit logs never leak credentials or PII.

Total: ~1.5k LOC of Python for a substantial upgrade to FA's runtime safety, observability, and self-improvement loops.

---

## Adjacent patterns worth stealing (appendix)

These are not in the four focus axes but are notable while reading:

- **Three-Space workspace layout** (`kronos/workspace.py`, 83 LOC):
  ```
  workspace/
  ├── self/     ← WHO I AM (identity, skills, methodology)
  ├── notes/    ← WHAT I KNOW (user model, memory, world)
  └── ops/      ← WHAT I DO (sessions, heartbeat, tools, workflow)
  ```
  Quick to grok, easy to file new content. FA's `notes/world/contacts/`, `notes/user/MEMORY.md`, `ops/sessions/handoff.md` map cleanly. **The `self/` / `notes/` / `ops/` trichotomy is a strong default scaffold.**

- **Per-agent isolated storage** (`config.py:model_post_init`):
  ```
  ./data/<agent_name>/session.db
  ./data/<agent_name>/memory_fts.db
  ./data/<agent_name>/knowledge_graph.db
  ./data/<agent_name>/qdrant/
  ./data/swarm.db         ← shared
  ```
  Solves "file lock contention on a shared Qdrant directory" problem at the architecture level. **Legacy paths are auto-rewritten** so old `.env` files still work — that's the right migration shape. FA can adopt "per-instance subdir + one shared ledger" for any multi-agent or multi-workspace mode.

- **Conversational tool approval pattern**: `approve_skill(name)` is just a regular tool the supervisor can call when the user says "approve skill X". No admin panel, no out-of-band UI, no JSON payloads. The status field flips in the SKILL.md frontmatter. **FA can use the same shape for "approve gotcha", "approve auto-discovered ACI rule", "approve sandbox carve-out"**.

- **Cron-scheduled self-improvement** (`kronos/cron/{self_improve,skill_create,skill_improve,sleep_compute}.py`):
  - `self_improve.py` (146 LOC) — daily, picks ONE concrete improvement from audit log.
  - `skill_create.py` (277 LOC) — weekly, drafts a new skill from repeatable patterns.
  - `skill_improve.py` (177 LOC) — nightly, refines existing skills based on usage.
  - `sleep_compute.py` (237 LOC) — nightly memory consolidation (dedupe + entity extraction + insight + archive).

  The **right cadence** for each task (daily vs weekly vs nightly) is the load-bearing detail. Don't run them all at once. **FA application**: this is the full "agent gets better while you sleep" loop. Each file is small enough to port standalone.

- **Identity-preserving summarization prompt** (`memory/compaction.py:22–43`):
  > CRITICAL — preserve verbatim (do NOT paraphrase, do NOT omit):
  > UUIDs, hashes, tokens, IDs · URLs, hostnames, IPs, file paths · batch progress · decision status + reason · TODOs · names, dates, sums · API keys masked

  This is the prompt that turns summarization from "lossy compression" into "lossless on the things that matter". The "structure of the summary" section also enforces a five-block layout (Context / Decisions / Progress / Pending / Data). **FA can copy this verbatim** for its session-handoff summaries.

- **Three-section minimal SKILL.md template**: `## Trigger / ## Protocol / ## Output`. That's it. The skill body in `templates/skill-packs/research/skills/research-brief/SKILL.md` is 17 lines. **FA can adopt this for "procedure files"**.

- **`agents.yaml` single source of truth**: 38 lines, one block per agent (`username` / `aliases` / `role`). Env vars override per-key. Loaded once, parsed lazily. **Right scale for a config file**.

- **`mask_pii_object()` for langchain messages/results** (`security/pii.py`): recursively masks strings inside `BaseMessage.content` and `LLMResult.generations[*].text/message`. Useful pattern for **any framework that wraps your strings in objects**: define the recursive walker once, apply at the observability boundary.

- **`tool.metadata["mcp_server"]` for filtering by origin** (`tools/manager.py:29–31`): stamps every loaded tool with its source server. Sub-agents can then filter tools by `(t.metadata or {}).get("mcp_server") in TASK_MCP_SERVERS` (see `kronos/agents/task.py:55–62`). **Lightweight provenance for tools** that FA can adopt without restructuring its tool layer.

- **`load_skill` reveals draft-with-prompt** (`skills/tools.py:46–51`): draft skills are loadable but prefixed with "this is a draft, say 'approve skill X' if useful". So drafts are not hidden — they're advertised with their approval action. **Inverts the usual "feature flag" model: the feature is visible but gated on user assent**.

- **Server-ops Level 1 / Level 2 model** (`tools/server_ops.py`): read-only Level 1 (`get_logs`, `get_status`, `get_health`, `db_query`) vs whitelisted Level 2 (`restart_service`, `deploy`, `clear_cache`). Arbitrary shell is never allowed. **Generalises to any FA tool that touches infrastructure or external state**: split into read-only and a whitelist of mutating actions, never accept arbitrary input.

---

## Reading order, if you have 90 minutes

1. **`README.md`** (10 min) — mental model, capability flags table.
2. **`docs/ARCHITECTURE.md`** (10 min) — system map + key file pointers per subsystem.
3. **`kronos/db.py`** + **`kronos/config.py:62–69`** (10 min) — substrate + flags.
4. **`kronos/memory/fts.py`** + **`kronos/memory/hybrid.py`** + **`kronos/memory/knowledge_graph.py`** (20 min) — the memory stack in one sitting.
5. **`kronos/skills/store.py`** + **`kronos/skills/tools.py`** + **`kronos/skills/hub.py`** (15 min) — the whole skills system.
6. **`kronos/swarm_store.py:63–426`** + **`kronos/group_router.py:1–235`** (15 min) — SQLite-as-arbitration + per-agent routing.
7. **`kronos/security/{shield,sanitize,loop_detector,output_validator,cost_guardian,pii}.py`** + **`kronos/tools/sandbox.py`** + **`kronos/audit.py`** (10 min skim) — 5-layer defense + sandbox + audit.

What you can safely skip on a first pass: `bridge.py`, `dashboard/`, `dashboard-ui/`, `llm.py`'s provider chain internals, all `cron/*_digest.py` / `cron/*_weekly.py` (transport/notification-specific).

---

*End of brief.*
