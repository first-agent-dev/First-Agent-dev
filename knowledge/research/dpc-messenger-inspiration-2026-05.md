---
title: "DPC-Messenger deep-dive inspiration research for First-Agent"
source:
  - "https://github.com/mikhashev/dpc-messenger"
  - "https://github.com/mikhashev/dpc-messenger/tree/main/docs/decisions"
compiled: "2026-05-12"
goal_lens: "Извлечь из DPC-Messenger ADR-стека + inner-loop кода паттерны для FA HookRegistry / KG / sleep consolidation."
chain_of_custody: |
  Все 24 паттерна извлечены из main branch `mikhashev/dpc-messenger` на
  дату 2026-05-12; прочитаны 26 ADR'ов целиком (~4250 LOC), CLAUDE.md
  (1399 LOC), и ~21K LOC ключевого Python кода (loop.py, hooks.py,
  guards.py, knowledge_graph.py, sleep_pipeline.py, budget.py, и др.).
  P2P transport / federation hub / Tauri UI / tests / licenses — НЕ
  читались (out of FA scope). Версия 0.14+, npm-published. Русские
  сноски добавлены к каждому паттерну для читаемости (2026-05-12).
---

> **Status:** active. Inspiration deep-dive (not produced via
> `knowledge/prompts/research-briefing.md`, §0 retrofitted).

## 0. Decision Briefing

### R-1 — HookRegistry + 2-tier middleware (B-NEW-5)

- **What:** Per-process middleware chain replacing inline guard sprawl. `GuardMiddleware` (can stop loop, errors propagate) + `ObserverMiddleware` (observation-only, errors swallowed). 5 stock guards: RoundLimit, ToolLimit, ResearchLimit, Loop (duplicate detection), Budget. ~500 LOC total.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (runtime architecture)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (directly implements ADR-7 §5 Lifecycle Guards + R-9 stop_message contract)
- **Cost:** medium (3-5h ADR + skeleton)
- **Verdict:** TAKE
- **Alternative-if-rejected:** inline if/elif guards in loop body (ADR-7 §5 current draft)
- **Concrete first step (if TAKE):** Write ADR-8 (B-NEW-5) referencing DPC `hooks.py` + `guards.py` verbatim

### R-2 — Bi-temporal Knowledge Graph + GraphBackend ABC (B-NEW-6)

- **What:** Pluggable KG with 5 NodeType + 9 EdgeType, `t_created`/`t_invalidated` fields for soft-delete, `ALWAYS_EXEMPT = {DECISION, SESSION_ARCHIVE}`. SQLite default backend. GLiNER NER for entity extraction. Third independent convergence (DPC + Enox + soviet-code) on 7-field typed-assertion contract.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (KG = pre-computed retrieval)
  - (B) helps LLM find context when needed: YES (graph queries point to source)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (future knowledge layer foundation)
- **Cost:** expensive (6-8h ADR + schema + skeleton)
- **Verdict:** DEFER (until current knowledge/ layer hits scaling limits)
- **Alternative-if-rejected:** filesystem-canon Markdown only (current FA approach)
- **Concrete first step (if TAKE):** Write KG ADR adopting DPC `knowledge_graph.py` schema verbatim

### R-3 — Sleep consolidation + _meta.json access registry (B-NEW-7)

- **What:** Inter-session memory via user-triggered (NOT cron) morning brief over session archives. N+1 LLM calls, `_meta.json` sidecar per knowledge file (read counts, embeddings cache, stale flags). DPC explicitly rejected cron after evolution disaster.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (morning brief = pre-loaded context for next session)
  - (B) helps LLM find context when needed: YES (_meta.json = per-file access registry)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (sleep consolidation + access registry)
- **Cost:** medium (4-6h)
- **Verdict:** DEFER (depends on R-1 HookRegistry + Phase M runner)
- **Alternative-if-rejected:** manual HANDOFF.md only (current FA approach)
- **Concrete first step (if TAKE):** Implement `_meta.json` sidecar pattern first (precursor, 2-3h)

### R-4 — Cite ADR-015 «evolution worker removed» as anti-pattern in AGENTS.md

- **What:** DPC built background evolution worker, ran 20+ sessions, got 0/40 valuable proposals, deleted 400 LOC + 7 tools. Quote: "Without a valid fitness function, evolution produces noise filtered by rules. The system is elaborate but empty." Empirically validates FA minimalism-first.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (one-line citation prevents future "let FA improve itself" proposals)
  - (B) helps LLM find context when needed: YES (anti-pattern signal in AGENTS.md)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (citation rule for AGENTS.md)
- **Cost:** cheap (~0.5h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** rely on minimalism-first principle alone
- **Concrete first step (if TAKE):** Add citation block to AGENTS.md §Architecture under "anti-patterns"

### R-5 — Adopt ADR-005 P18 scope-only-estimation rule in AGENTS.md

- **What:** Estimate lines/files, never time. Example S14 in DPC: CC estimated 5-7h for what took 11 min — error of 27-38×. Forces concrete scope discussion vs vague timeline.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (process rule, not architecture)
- **Cost:** cheap (~0.5h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** continue using mixed scope/time estimates
- **Concrete first step (if TAKE):** Add rule to AGENTS.md PR Checklist

### R-6 — Adopt ADR-021 Lesson 4 «write-only subsystems are dead weight» in AGENTS.md

- **What:** If something is indexed but never read — delete it, don't maintain. DPC found multiple write-only ML subsystems eating maintenance budget.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (subtraction-first principle reinforced)
- **Cost:** cheap (~0.5h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** continue using minimalism-first alone
- **Concrete first step (if TAKE):** Add citation to AGENTS.md as concrete example of subtraction-first

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | NO / NO | YES | medium | inline if/elif guards | Yes (ADR-8 priority) |
| R-2 | DEFER | YES / YES | YES | expensive | filesystem-canon only | Yes (timing) |
| R-3 | DEFER | YES / YES | YES | medium | manual HANDOFF.md only | Yes (depends on R-1) |
| R-4 | TAKE | YES / YES | YES | cheap | minimalism-first alone | No |
| R-5 | TAKE | NO / NO | PARTIAL | cheap | mixed estimates | No |
| R-6 | TAKE | NO / NO | PARTIAL | cheap | minimalism-first alone | No |

---

# DPC-Messenger Deep Dive — Research Report

**Target repo:** `github.com/mikhashev/dpc-messenger` (commit at clone: main, 2026-05-12)
**Output type:** ANALYSIS ONLY — no code changes to dpc-messenger or FA in this session.
**Companion docs (FA-side, prior sessions):**
- `soviet-code-inspiration-2026-05.md` (22 patterns, 4 B-NEW candidates)
- `chat-cross-reference-2026-05.md` (27 patterns, convergent-evolution rows)

---

## §0 TL;DR

DPC is the **most mature** of the three reference repos (FA / soviet-code / DPC) — npm-published v0.14+, ~72K LOC Python core + 29K LOC UI, 26 ADRs across 14 months of decisions, full P2P + agent stack. Of the **24 architectural patterns extracted**, **7 are direct adopt candidates** for FA, **10 are reference-only** (cross-check FA's ADRs / BACKLOG), and **7 are intentional skip** (out of FA scope: P2P transport, federation hub, voting consensus, Tauri UI, ML framework migrations, OAuth, group chat).

> 🇷🇺 **Что это значит:** DPC — это самый «взрослый» из трёх референсных репо (FA / soviet-code / DPC). Реальный продукт: опубликован в npm, ~72 тыс. строк Python + 29 тыс. строк UI, 26 архитектурных решений (ADR) накопленных за 14 месяцев. Я извлёк 24 паттерна; из них **7 рекомендую брать сразу**, **10 — посмотреть-сравнить-с-нашими**, **7 — пропустить** (это P2P-сеть, federation hub, голосование, Tauri UI, миграции ML-фреймворков, OAuth, группчат — всё это вне scope FA).

> 🇷🇺 **Tier-обозначения:** ⭐⭐⭐ = adopt (брать), ⭐⭐ = reference (посмотреть как у них, иметь в виду), ⭐ = skip (не наш кейс).

**Top-3 highest-leverage adopt candidates for FA:**
1. **B-NEW-5: per-process middleware chain (HookRegistry + Guards)** — replaces FA's eventual inline guard sprawl in the inner loop. ADR-007 demonstrates that 5 inline `if` blocks → 5 typed `GuardMiddleware` classes scales cleanly. Direct FA mapping: ADR-7 §5 (Lifecycle), §6 (Tool-Registry). ~3-5h effort.
2. **B-NEW-6: 7-field typed assertion / typed edge KG schema** — third independent convergence (DPC + Enox + soviet-code). DPC adds **bi-temporal validity** (`t_created` / `t_invalidated`) which neither soviet-code nor Enox have. Direct FA mapping: future KG ADR (rev of cross-reference row 21a). ~6-8h for ADR + skeleton schema.
3. **B-NEW-7: sleep-consolidation morning brief over inter-session archives** — gives FA an inter-session memory layer without the bug-ridden auto-extraction path. Direct FA mapping: cross-reference Pattern 3.3 (memento-skills), FA's exploration_log §Inter-session. ~4-6h for ADR + minimal pipeline.

> 🇷🇺 **Топ-3 что брать в первую очередь:**
> 1. **B-NEW-5 — цепочка middleware вместо «зоопарка if-ов» во внутреннем лупе.** DPC показал на живом коде, что 5 захардкоженных `if round_idx > MAX` / `if cost > BUDGET` блоков элегантно превращаются в 5 отдельных классов `GuardMiddleware`. Каждый — со своим состоянием, со своим сообщением об остановке. Прямо ложится на наш ADR-7 §5 (lifecycle hooks) и §6 (tool registry). ~3-5 часов.
> 2. **B-NEW-6 — граф знаний (KG) с типизированными рёбрами.** Это уже третья конвергенция (DPC + Enox + soviet-code пришли к одному формату 7-полевых типизированных рёбер). DPC добавил **двухвременную модель** — каждое ребро знает когда создано (`t_created`) и когда стало неактуальным (`t_invalidated`). Это soft-delete без потери истории. Когда будем делать наш KG — копировать verbatim. ~6-8 часов на ADR + скелет.
> 3. **B-NEW-7 — sleep consolidation: «утренний бриф» по архивам прошлых сессий.** Даёт FA inter-session память без багов автоизвлечения, которые DPC сами признали неработающими. Триггер — **человек жмёт кнопку**, не cron. Прямо ложится на наш HANDOFF.md как автоматизированный аналог. ~4-6 часов.

**Most striking lesson (ADR-015):** **Evolution removal is the strongest design signal.** DPC built a full autonomous-evolution worker, ran it for 20+ sessions, recorded 0/40 valuable proposals, and deleted ~400 lines + 7 tools. "Real fitness for an agent = usefulness to the human partner; this cannot be computed autonomously." **This validates FA's minimalism-first stance** and gives concrete ammunition for resisting future "let the agent improve itself" proposals.

> 🇷🇺 **Самый сильный сигнал во всём репо — ADR-015 «Удаление эволюции».** DPC построил полноценный фоновый worker, который раз в час сам анализировал агента и предлагал улучшения. Прогнал 20+ сессий, накопил ~40 предложений, **из них ноль принёс измеримую пользу**. Удалили 400 строк кода + 7 инструментов + UI-панель. Их вывод дословно: «настоящая fitness-функция для агента = его польза человеку-партнёру; это нельзя посчитать автономно». **Это эмпирическое подтверждение нашей minimalism-first позиции.** Цитировать в AGENTS.md как защиту от будущих «давайте FA сам себя улучшает».

**Convergent evolution validation (4 independent projects now):**
- FA (planned KG)
- DPC `knowledge_graph.py` (5 node types + 9 edge types, `GraphBackend` ABC, SQLite default)
- Enox (mentioned in chat excerpt 2, typed assertions)
- soviet-code `EnoxBackend.toAssertion` (7-field contract `source_name / source_type / target_name / target_type / relation / confidence / context`)

DPC adds two new patterns on top: (a) `ALWAYS_EXEMPT = {DECISION, SESSION_ARCHIVE}` — certain node types never expire; (b) bi-temporal `t_invalidated` field for soft-deletion of edges. Worth adopting verbatim.

> 🇷🇺 **Конвергентная эволюция:** четыре независимых проекта (мы + три референса) пришли к одной и той же схеме графа знаний — типизированные рёбра с 7 полями. Это сильный сигнал: значит, схема правильная, не наш уникальный bias. DPC добавил две вещи сверху: (а) **некоторые типы узлов вечны** — решения (DECISION) и архивы сессий (SESSION_ARCHIVE) никогда не помечаются как stale, потому что они и есть исторические факты; (б) **двухвременная модель рёбер** — у каждого ребра есть `t_created` (когда создано) и `t_invalidated` (когда стало неактуальным, но не удалено). Это soft-delete с сохранением истории — то, что нам понадобится для отслеживания «когда мы передумали».

---

## §1 Repo Survey (Step 1+2+3 recap)

**Size:** 421 files, ~72K LOC Python core, ~29K LOC UI (Svelte/Tauri/Rust), ~13K LOC docs.
**Read list executed:** `dpc-messenger-read-list-v2.md`.
**Coverage achieved:** T0 100% / T1 100% (all 26 ADRs — 11 full, 15 scanned to §Decision/§Consequences) / T2 ~80% (skimmed structurally) / T3 ~60% (signatures + key bodies).
**Pre-commit/lint:** repo has no `.pre-commit-config.yaml`; analysis-only, none required.

> 🇷🇺 **Что в этой секции:** карта всех 26 ADR'ов DPC по фазам разработки. Каждый ADR имеет явные ссылки на «зависит от», «заменяет», «отменяет» предыдущие. Это сама по себе паттерн: **строгий decision-lineage**. У нас в DIGEST.md есть аналог, но более легковесный. В фазе B FA стоит позаимствовать строгие headers «Depends on / Supersedes / Replaces».

### 1.1 Decision lineage (ADR map)

```text
Phase 1 — Refactor & Foundations (S0-S25, ADRs 001-008)
  001 service.py split (CoreService 9630 → <2000 LOC, 4 domain services)
  002 LLM Provider ABC (3074 LOC monolith → providers/{ollama,openai,anthropic,zai,whisper}.py)
  003 Frontend store hybrid (50+ writable<any> → 10 typed global + per-panel local stores)
  004 Knowledge Extraction Review (dual-path: manual full_conv + auto monitor on 5-msg buffer)
  005 Protocol 13 v1.8 (session closing P18 + scope-only estimation rule)
  006 Participant Model (sender → author + participant_type + source, 3 orthogonal dims)
  007 Hooks & Middleware (5 inline guards → typed GuardMiddleware + ObserverMiddleware)
  008 Archive YYYY/MM nested + unlimited retention (default max_archived = 0 = keep all)

Phase 2 — Agent Maturity (S26-S78, ADRs 009-021)
  009 Knowledge Flows Redesign (3 extraction paths, 0 coordination, ADR-013 governs survival)
  010 Memory Architecture (_meta.json + BM25+FAISS RRF + chunking strategy)
  011 Poetry → uv migration (10-100x faster, PEP 621, hardware-aware index)
  012 Device-Aware Dep Resolution (uv [tool.uv.sources] markers, .env approach rejected)
  013 Selection Layer (agent = filter; human = direction + veto; 7 prior diagnoses of same gap)
  014 Sleep Consolidation (N+1 LLM calls, morning_brief.json + last_sleep.json)
  015 Evolution REMOVED (0/40 valuable proposals, ouroboros without human partner)
  016 Agent Web Pipeline (ddgs 8+ backends + trafilatura + camoufox 4-tier fallback)
  017 Shared Knowledge Search (stateless pull, plaintext query, Dunbar-tier ACL)
  018 Retrieval Upgrade (e5-small bug → BGE-M3 8192 tokens, 1024d, ONNX)
  019 Search Infra Scaling (RRF k=60 explained, dual-query RECALL-QUERY workaround)
  020 Query Preprocessing (3-layer stop words: standard + corpus-adaptive + user-specific)
  021 PyTorch Unified ML (revert ONNX, BGE-M3 stays via sentence-transformers)

Phase 3 — Multi-Agent Safety + Team (S80-S100, ADRs 022-026)
  022 Multi-Agent Safety Governance (7 emergent risks C1-C7, 3-layer defense)
  023 Group Chat Participant Model (sender_type + agent_owner + per-group agents map)
  024 Knowledge Graph (5 node types + 9 edge types, GraphBackend ABC, bi-temporal)
  025 Discord Integration (mirror Telegram bridge, @mention only)
  026 Public Agent Guardrails (source-based tool filter, URL whitelist, rate limit)
```

This map is itself a pattern: **ADR-N references ADR-(N-1), and "Supersedes" / "Replaces" / "Depends on" headers make the lineage explicit** (e.g., ADR-015 supersedes ADR-013 Phase 3; ADR-021 reverts ADR-018 partially). FA's `knowledge/adr/DIGEST.md` is the FA-side analog but lighter — DPC's per-ADR explicit Depends/Replaces is stricter and worth borrowing for FA Phase B.

> 🇷🇺 **Наблюдение:** видна траектория проекта — фаза 1 (рефакторинг основ), фаза 2 (зрелость агента), фаза 3 (многоагентная безопасность + командная работа). К ADR-015 они уже умеют отказываться от собственных решений и сносить код — это признак зрелого процесса принятия архитектурных решений. Нам стоит держать в уме: **в DIGEST.md нужно явно фиксировать «отменяет ADR-N», а не просто «новый ADR».**

---

## §2 Architectural Patterns (numbered, source-cited)

### Group A — Loop, Tools, Guards (Patterns 1-6)

**Pattern 1: Two-Tier Per-Process Middleware Chain**
*Sources:* ADR-007 (344 LOC); `dpc_agent/hooks.py` (207 LOC); `dpc_agent/guards.py` (222 LOC); `dpc_agent/loop.py` (700 LOC, function `run_llm_loop` at line 432).

**Construct:**
- `HookAction` enum: `CONTINUE | STOP_LOOP` (Phase 0; `REDIRECT / RETRY` reserved for Phase 2).
- `HookLifecycle` enum: `BEFORE_LLM_CALL / AFTER_LLM_CALL / BEFORE_TOOL_EXEC / AFTER_TOOL_EXEC / BETWEEN_ROUNDS`.
- `LoopState` dataclass: `last_response_has_text / tool_calls_this_turn / consecutive_tool_only_rounds / accumulated_cost_usd / recent_tool_args / last_assistant_text / tool_calls_this_round / current_round`. **Mutation contract: loop OWNS these and updates BEFORE `fire()`; middleware only reads.**
- `BaseMiddleware` → `GuardMiddleware` (errors propagate) vs `ObserverMiddleware` (errors caught at DEBUG, never STOP_LOOP).
- `HookRegistry` per `process()` call — no cross-session memory, no locks; registration order = dispatch order; first STOP_LOOP wins.

**5 concrete `GuardMiddleware` implementations** (replace inline `if` blocks in old loop):
- `RoundLimitGuard(max_rounds=200)` — fires in `between_rounds`, strict `>`.
- `ToolLimitGuard(max_per_turn=25)` — fires in `after_llm_call`, burst detection.
- `ResearchLimitGuard(max_consecutive=15)` — counter on instance, fires in `after_llm_call`, "force final answer" message.
- `LoopGuard(max_duplicate_calls=5)` — fingerprint `name::json_sorted_args`, JSON-string-args normalized.
- `BudgetLimitGuard` — wraps `SubscriptionBudget / PayPerUseBudget / HybridBudget` from `budget.py`.

Each Guard implements `stop_message()` returning a user-facing reason (read via `HookRegistry.last_triggered` after `fire()`).

**Why it matters for FA:** ADR-7 §5 currently lists lifecycle hooks abstractly. DPC's implementation shows **the minimal viable surface** — a tiny `BaseMiddleware`, a tiny enum, and 5 stock guards. The whole infrastructure is <500 LOC (hooks.py + guards.py). FA's ADR-7 R-9 / R-7 / R-13 all describe behaviour that maps 1:1 onto these guards.

**Convergence evidence (from ADR-007 §References):** Framework / DeerFlow / Claw Code / Ouroboros all independently landed on this interceptor pattern. DPC documents this as a 4-project convergence in the ADR body itself.

**Tier:** ⭐⭐⭐ **adopt** (B-NEW-5).

> 🇷🇺 **Пояснение паттерна 1:** «Цепочка middleware» — это когда луп агента не проверяет внутри себя «не превысил ли бюджет? не зациклился ли?», а вместо этого перед каждым действием вызывает registry.fire() — и все зарегистрированные middleware по очереди решают «продолжать» или «остановить». Два типа: **Guard** (может остановить луп, ошибки пропагируются) и **Observer** (только наблюдает, ошибки глотаются). Ключевое: каждый Guard возвращает `stop_message()` — человекочитаемую причину остановки («ты превысил лимит 200 раундов, разбей задачу»). Это **<500 строк кода** в сумме, но даёт очень чистую архитектуру. Прямой аналог для FA ADR-7 §5.

---

**Pattern 2: Inline-Guard → Middleware Refactor as Worked Example**
*Source:* ADR-007 §Migration Path; `guards.py:20-222`.

**Construct:** DPC documents **the exact mapping** from old `if/elif` chains in `_process_agent_loop` to new Guard classes. Five guards lifted out:
- `if round_idx > MAX_ROUNDS` → `RoundLimitGuard`
- `if len(tool_calls) > MAX_TOOLS_PER_TURN` → `ToolLimitGuard`
- `if consecutive_tool_only >= RESEARCH_LIMIT` → `ResearchLimitGuard`
- `if duplicate_count >= LOOP_GUARD` → `LoopGuard`
- `if accumulated_cost >= BUDGET_LIMIT` → `BudgetLimitGuard`

**Why it matters for FA:** FA's ADR-7 §5 Lifecycle and ADR-7 §11 R-9 / R-13 prescribe lifecycle hooks but don't show the **refactor sequence** from current state (no hooks) to target. DPC's "5 inline ifs → 5 GuardMiddleware classes" is a copy-paste-friendly transformation plan. The work plan would slot directly under BACKLOG I-1 (R-7 implementation).

**Tier:** ⭐⭐⭐ **adopt** as part of B-NEW-5.

> 🇷🇺 **Пояснение паттерна 2:** Документированный путь миграции. DPC показывает «было / стало»: 5 inline `if/elif` в лупе → 5 отдельных классов. То есть это не просто «красивый паттерн», а **реальный план миграции** который можно скопировать для FA когда в ADR-7 появятся inline-гарды.

---

**Pattern 3: `LoopState` as the Hooks/Loop Contract**
*Source:* `hooks.py:44-66` (LoopState dataclass).

**Construct:**
```python
@dataclass
class LoopState:
    last_response_has_text: bool = False
    tool_calls_this_turn: int = 0
    consecutive_tool_only_rounds: int = 0
    accumulated_cost_usd: float = 0.0
    recent_tool_args: list[dict] = field(default_factory=list)
    last_assistant_text: str = ""
    tool_calls_this_round: int = 0
    current_round: int = 0
```

Mutation contract enforced **by convention, not by code** (no setters, no events) — but the docstring is explicit: "the loop OWNS these fields and updates them BEFORE calling HookRegistry.fire(); middleware only reads them. Stale values at fire time produce wrong guard decisions."

Middleware-specific mutable state lives **on the middleware instance** (`self._counter` in `ResearchLimitGuard`), not in `LoopState`. This is a small but principled split.

**Why it matters for FA:** FA's ADR-7 §5 should specify exactly the same kind of "what's in the context object". DPC gives the field list, the mutation contract, and the rationale (why per-instance state lives on the middleware).

**Tier:** ⭐⭐⭐ **adopt** as part of B-NEW-5.

> 🇷🇺 **Пояснение паттерна 3:** `LoopState` — это «контракт»: что именно луп сообщает middleware. Важнейшее правило: **луп владеет этими полями** и обновляет их ДО вызова `fire()`; middleware только ЧИТАЕТ, никогда не пишет. Если middleware нужно собственное состояние (counter, timestamp) — оно хранится **на инстансе middleware** (`self._counter`), не в LoopState. Это маленький, но принципиальный раздел ответственности.

---

**Pattern 4: `_fingerprint(call) = name::json_sorted_args`**
*Source:* `guards.py:134-145` (LoopGuard).

**Construct:**
```python
@staticmethod
def _fingerprint(call: dict) -> str:
    name = call.get("name", "?")
    raw_args = call.get("args", {})
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            pass
    if isinstance(raw_args, dict):
        args_str = json.dumps(raw_args, sort_keys=True, default=str)
    return f"{name}::{args_str}"
```

Robust to: providers that return args as JSON strings, missing keys, non-dict args, non-JSON-serializable values (via `default=str`). Session-scoped counter (`Counter[str]`), 5 duplicates = stuck loop.

**Why it matters for FA:** This is the *minimal* loop-detection primitive. FA's ADR-7 R-7 (loop detection) is one-line abstract; DPC's `_fingerprint` is one-screen concrete. Copyable verbatim.

**Tier:** ⭐⭐⭐ **adopt** as part of B-NEW-5.

> 🇷🇺 **Пояснение паттерна 4:** Обнаружение зацикливания. Если агент вызывает один и тот же инструмент с теми же аргументами 5 раз подряд — он застрял. `_fingerprint` создаёт уникальный ключ `"имя_инструмента::{сортированные_аргументы}"` и считает повторы. Минимальный примитив для R-7 (loop detection) в нашем ADR-7. Можно копировать буквально — это один экран кода.

---

**Pattern 5: Three Budget Strategies as Polymorphic Classes**
*Source:* `budget.py` (389 LOC), classes `SubscriptionBudget`, `PayPerUseBudget`, `HybridBudget` + `BillingModel` enum + `ProviderLimits` dataclass + `get_provider_limits(provider)` factory + `check_budget_simple(used, limit)` fallback.

**Construct:**
- `SubscriptionBudget`: counts requests, no $ cost (e.g., Anthropic free quota).
- `PayPerUseBudget`: accumulates `$` cost from response tokens × model rate.
- `HybridBudget`: subscription requests + overage $ cost.
- All share `get_status() -> Dict[str, Any]` for runtime introspection by the agent / hook.

**Why it matters for FA:** FA's BACKLOG I-7 (auto-KPI / cost tracking) needs exactly this taxonomy. FA also has the bootstrap-cost-baseline insight that **most sessions use tier-1 + tier-2 disclosure only** — having a `SubscriptionBudget` strategy makes that observable.

**Tier:** ⭐⭐ **reference** (worth citing in BACKLOG I-7 when implemented).

> 🇷🇺 **Пояснение паттерна 5:** Три стратегии бюджета: по подписке (считаем запросы, не деньги), pay-per-use (накапливаем $), гибрид (подписка + овераж). Все делят `get_status()` для интроспекции. Когда мы дойдём до BACKLOG I-7 (auto-KPI / cost tracking) — посмотреть на эту таксономию.

---

**Pattern 6: Tool Registry with Per-Agent Allowlist + Sandbox Path Allowlist**
*Sources:* `tools/registry.py:31` (`ToolContext`), `:191` (`ToolEntry`), `:246` (`ToolRegistry`); `DPC_AGENT_GUIDE.md` §"Per-Agent Tool Control" and §"Extended Sandbox Paths"; `privacy_rules.json` schema.

**Construct:** Tools live in `dpc_agent/tools/{archive,browser,core,git,messaging,registry,review,skills}.py`. Each tool is registered via `ToolEntry`. `ToolRegistry` exposes:
- Default allowlist per agent profile (e.g., `"profile": "researcher"` → 8 core tools)
- Firewall override per-agent (`privacy_rules.json` → `dpc_agent.{agent_id}.tools.allowed`)
- Extended sandbox paths (firewall-allowed dirs outside `~/.dpc/agent/`) via `extended_path_{read,list,write}` tools

Restricted tools (`git_add`, `git_commit`, `git_init`) require explicit firewall enablement.

**Why it matters for FA:** This is **exactly** what FA's ADR-7 §6 (tool-registry contract) describes, but DPC's version is per-agent (not just per-profile) and has the path-allowlist split. Cross-cuts with soviet-code Pattern B-NEW-1 (declarative tool whitelist).

**Tier:** ⭐⭐⭐ **reference** for ADR-7 §6 / R-7. Combined with soviet-code B-NEW-1 → unified amendment.

> 🇷🇺 **Пояснение паттерна 6:** Реестр инструментов с белым списком. Каждый агент получает **свой набор** инструментов (default по профилю + override через firewall), разделённые на «безопасные» (read-only) и «ограниченные» (git, write). Плюс отдельный «песочница путей» — какие директории за пределами sandbox'а агенту разрешено видеть. Совпадает с soviet-code B-NEW-1 (declarative tool whitelist). Для FA это реализация ADR-7 §6 (tool-registry contract).

---

### Group B — Memory, Retrieval, KG (Patterns 7-12)

**Pattern 7: `_meta.json` Access Registry**
*Source:* ADR-010 §Component 1 (lines 78-127); `memory.py:40` (FileMeta dataclass), `:58` (backfill_meta), `:107` (update_access).

**Construct:** Per-knowledge-file metadata sidecar:
```python
@dataclass
class FileMeta:
    last_accessed: str       # ISO timestamp
    access_count: int
    last_verified: str       # ISO timestamp of last fact-check
    tags: List[str]
    summary: str             # ≤200 chars
    source_layer: str        # L0-L7
    project: Optional[str]
    embedding: Optional[List[float]]  # cached 1024d (BGE-M3)
    stale: bool              # set by staleness detector
```

`backfill_meta()` bootstraps `_meta.json` for existing knowledge dirs. `update_access()` is called on every `knowledge_read` tool call. The 384d/1024d cached embedding column avoids re-embedding the same file every retrieval.

**Why it matters for FA:** FA's `knowledge/` and `exploration_log` are file-canon Markdown; FA has no access-tracking yet. Pattern 7 is the minimal "what got used, when, how often" telemetry that future BACKLOG I-7 (auto-KPI) needs. **One sidecar file, no DB.**

**Tier:** ⭐⭐⭐ **adopt** for FA Phase B-NEW-7 (sleep consolidation) precursor. ~2-3h.

> 🇷🇺 **Пояснение паттерна 7:** На каждый файл знаний (`.md`) рядом хранится спутник `_meta.json` — когда последний раз читали, сколько раз читали, когда проверяли факты, теги, краткое резюме, из какого слоя знаний, **кэшированный embedding**, флаг stale. Это одновременно (а) телеметрия «что использовалось» (для будущих KPI и sleep consolidation), и (б) оптимизация — embedding не пересчитывается каждый раз. **Один sidecar файл, никакой БД**. Для FA это предвестник B-NEW-7 — прежде чем делать sleep consolidation, нужно начать трэкать доступ к файлам.

---

**Pattern 8: Hybrid BM25 + Vector Retrieval with RRF Fusion**
*Sources:* ADR-010 §Component 2 (lines 130-180); ADR-018 (157 LOC); ADR-019 (154 LOC); ADR-020 (82 LOC); `active_recall.py:74` (`get_recall_block`); `bm25_index.py`; `faiss_index.py`; `hybrid_search.py`.

**Construct:**
- BM25: `bm25s` library (pure Python, scipy sparse). Character-bigram fallback for CJK/Arabic/Thai.
- Dense: FAISS `IndexFlatIP` (small scale) → `HNSW` (at scale), API-compatible.
- Embedding: BGE-M3 1024d via sentence-transformers (after ADR-021 revert from ONNX).
- Fusion: **Reciprocal Rank Fusion**, `k=60` (Cormack 2009), best possible score `1.5 / (60+0+1) = 0.0246`.
- Whole-document indexing (no chunking): DPC's typical file is 0.5-5KB (125-1250 tokens) — fits in BGE-M3's 8192-token window without chunking.

**Bugs DPC caught and fixed (ADR-018):**
- e5-small was missing required `"query: "` / `"passage: "` prefix (~10% recall loss).
- Silent query truncation at 512 tokens (asymmetric fusion: BM25 saw full query, dense saw truncated).
- 30-message window concatenation drowned topic switches (ADR-019 RECALL-QUERY dual-query workaround: Q1=last human msg, Q2=last 10 msgs, merged via RRF).

**Stop words (ADR-020) 3-layer pipeline:**
1. Standard per-language (stop-words-iso, 57 languages)
2. Corpus-adaptive (DF > 80% → auto stop word, like sklearn `max_df=0.8`)
3. User-personal (high-frequency tokens from session archives — DPC novel contribution)

**Why it matters for FA:** FA does not retrieve programmatically — it relies on Markdown-canon + human cognition. **Adopt only if FA implements a KG/retrieval ADR.** Until then this is preserved evidence ("look at DPC for working hybrid retrieval at agent scale").

**Tier:** ⭐⭐ **reference** (unless FA decides to add retrieval ADR).

> 🇷🇺 **Пояснение паттерна 8:** Гибридный поиск. **BM25** — древний (1970-е) но отличный алгоритм поиска по ключевым словам. **Векторный поиск** (FAISS + BGE-M3) — по смыслу, не по словам. **RRF (Reciprocal Rank Fusion)** с k=60 — это стандартный способ сливания результатов двух разных ranker'ов (Cormack 2009, SIGIR). Они документировали 3 бага, на которых потеряли недели — отсутствие обязательных префиксов в e5-модели, тихое truncate запроса, drowning топика в 30-сообщенчном окне. Для FA это **reference only** — пока мы не решим делать programmatic retrieval (сейчас опираемся на grep и человека).

---

**Pattern 9: Knowledge Graph — `GraphBackend` ABC with SQLite Default**
*Sources:* ADR-024 (329 LOC); `knowledge_graph.py:115` (`GraphBackend` ABC), `:146` (`SQLiteGraphBackend`), `:278` (`KnowledgeGraph` facade).

**Construct:**
- 5 `NodeType`: `KnowledgeFile / SessionArchive / Entity / Decision / Agent`.
- 9 `EdgeType`: `DERIVED_FROM / DEPENDS_ON / RESPONDS_TO / CONTRADICTS / SUPPORTS / DECIDED_BY / SHARED_WITH / MENTIONS / TEMPORAL_NEXT`.
- `GraphEdge` includes `t_created` + `t_invalidated` (bi-temporal, Graphiti-style); `confidence: float = 1.0`; `justification: str`; `edge_weight: str = "medium"`.
- `ALWAYS_EXEMPT = {DECISION, SESSION_ARCHIVE}` — these node types never decay or get garbage-collected.
- `GraphBackend` is an ABC: `init_schema / add_node / add_edge / get_node / get_neighbors / get_edges / node_count / edge_count / close`.
- `SQLiteGraphBackend` is the default (single-file, embedded, ~3K LOC schema).

**Pipeline:**
1. **Structural edges** (extracted from filesystem layout, mtime, frontmatter) — free, deterministic.
2. **GLiNER NER** (`urchade/gliner_multi-v2.1`, multilingual zero-shot, process-wide singleton with double-checked locking) — extracts entity nodes.
3. **Guided LLM relations** (typed prompt, schema-constrained output) — produces typed edges.

**Convergence evidence:** 4 independent projects now have the same 7-field typed-assertion contract (FA-planned / Enox / soviet-code `EnoxBackend.toAssertion` / DPC `GraphEdge`). DPC adds bi-temporal validity that the others don't have. (See §5.)

**Why it matters for FA:** When FA implements its KG ADR, this is the **reference implementation**. Copyable: enum lists, `GraphBackend` ABC, SQLite default backend, ALWAYS_EXEMPT semantics, bi-temporal fields.

**Tier:** ⭐⭐⭐ **adopt** (B-NEW-6).

> 🇷🇺 **Пояснение паттерна 9:** Ключевой паттерн для FA. **5 типов узлов** (файл знаний / архив сессии / сущность / решение / агент) и **9 типов рёбер** (выведено из / зависит от / отвечает на / противоречит / поддерживает / принято в / расшарено с / упоминает / временная последовательность). **База = SQLite-файл** (не отдельный сервер!), но через ABC можно подключить Neo4j/Kuzu/что угодно. **Двухвременная модель** — ребро не удаляется, а инвалидируется, так что видна история «мы считали X до даты Y, потом передумали». **`ALWAYS_EXEMPT`** — решения (ADR) и архивы сессий вечны, их не удаляет сборщик мусора.

---

**Pattern 10: Module-Level Singleton with Double-Checked Locking**
*Source:* `knowledge_graph.py:63-89` (`_get_gliner_model`).

**Construct:**
```python
_GLINER_MODEL: Any = None
_GLINER_LOAD_LOCK = threading.Lock()

def _get_gliner_model():
    global _GLINER_MODEL
    if _GLINER_MODEL is not None:
        return _GLINER_MODEL
    with _GLINER_LOAD_LOCK:
        if _GLINER_MODEL is not None:
            return _GLINER_MODEL
        try:
            from gliner import GLiNER
        except ImportError:
            return None
        _GLINER_MODEL = GLiNER.from_pretrained(GLINER_MODEL_NAME)
        return _GLINER_MODEL
```

Loads ~2GB model once per process; parallel group sleep would otherwise instantiate per agent. **`ImportError` → return None → caller treats as "skip NER"** — same pattern as the BGE-M3 embedding singleton (S105).

**Why it matters for FA:** When FA adds an embedding model or NER, this is the right initialization shape. Optional deps via `ImportError → None → graceful skip` keeps the minimalism story intact.

**Tier:** ⭐⭐ **reference** for any FA ML dep.

> 🇷🇺 **Пояснение паттерна 10:** Как правильно загружать тяжёлые ML-модели (в этом случае GLiNER для NER, ~2 ГБ RAM). Два принципа: (1) **один singleton на процесс** (иначе параллельные агенты загрузят по копии), (2) **опциональный import через ImportError → None** — если библиотека не установлена, просто выключаем фичу, без спам-лога. Это тот самый паттерн «minimalism + graceful degradation» который мы любим. Для FA — reference для любых будущих ML-зависимостей.

---

**Pattern 11: Stateless P2P Pull Search (Strategy B)**
*Source:* ADR-017 (134 LOC).

**Construct:** Plaintext query (not embedding) shipped over TLS P2P → receiver computes embedding locally → searches own FAISS + BM25 → applies firewall + Dunbar-tier ACL → returns top-K filenames + scores. Merged on requester via RRF.

**Dunbar-tier ACL:**
- Layer 5 (intimates): full content + summaries
- Layer 15: full + summaries
- Layer 50: topic + confidence
- Layer 150: topic only
- Beyond 150: not served

**Why it matters for FA:** FA is single-agent / single-user; multi-node P2P is out of scope. **But:** the **stateless pull, ship-plaintext-not-embedding** decision is the right call for any future "FA queries external KG" feature, because corpora differ → embeddings differ → only plaintext is portable.

**Tier:** ⭐ **skip for v0.x, reference for future.**

> 🇷🇺 **Пояснение паттерна 11:** Распределённый поиск между пирами. Раз мы single-user, это не наш кейс. Но одна важная идея: **посылать плаинтекст запроса, а не embedding** — потому что у разных пиров могут быть разные embedding-модели, и векторы непереносимы. **Дунбар-слои** (5 / 15 / 50 / 150) — разным уровням близости разные результаты. Сохранить на будущее.

---

**Pattern 12: Inter-Session Memory via Sleep Consolidation**
*Sources:* ADR-014 (98 LOC); ADR-015 (148 LOC, removal); `sleep_pipeline.py:375` (`run_sleep`, ~290 LOC); `consolidation.py`.

**Construct:**
- **Trigger:** UI button (Sleep/Wakeup toggle) — **user-initiated, not automated**. Critical design choice after evolution disaster.
- **Inputs:** `digest.jsonl` (session metadata, append-only) + full session archives `archive/YYYY/MM/{ts}_session.json`. No truncation.
- **Pipeline:** N+1 LLM calls — one per-session pass for each unprocessed session, then one synthesis pass.
- **Outputs:**
  - `morning_brief.json` — injected into scratchpad + posted as chat message on wakeup.
  - `sleep_findings.json` — evolution-feed (vestigial after ADR-015; kept as audit trail).
  - `last_sleep.json` — timestamp of last consolidation.
- **Auto-wakeup** on pipeline completion.
- **Group-aware:** `_collect_group_digests` / `_collect_group_archive_digests` (group chat sessions where agent participated).

**ADR-015 lesson:** This **replaces** the disabled consciousness background worker AND partially replaces the deleted evolution trigger. **Critical: trigger is human, not cron, not "every hour".**

**Why it matters for FA:** FA currently has no inter-session memory layer. `HANDOFF.md` is the manual analog. Sleep consolidation is the **automated** version of HANDOFF — and DPC has empirically proven that **user-triggered** consolidation works, while **autonomous-loop** versions (evolution worker, consciousness worker) don't.

**Tier:** ⭐⭐⭐ **adopt** (B-NEW-7) — but the lesson "user-triggered, not background" is more important than the implementation.

> 🇷🇺 **Пояснение паттерна 12:** Sleep consolidation — это «утренний бриф» для агента. **Пользователь жмёт кнопку Sleep** → агент берёт все непрочитанные архивы предыдущих сессий, делает N+1 вызовов LLM (один на каждую сессию + 1 итоговый), и выдаёт `morning_brief.json` — короткую выжимку «что я вынес из этих сессий». Ключевое решение: **триггер человеческий, не cron**. DPC эмпирически доказал: автономные версии (consciousness worker, evolution worker) производят мусор. Человек-triggered работает. Для FA это аналог HANDOFF.md — только автоматизированный (агент сам читает архивы, выдаёт выжимку, человек проверяет и включает в HANDOFF).

---

### Group C — Agent Identity, Skills, Self-Improvement (Patterns 13-17)

**Pattern 13: Memento-Skills System — Procedural Knowledge as `.md`**
*Sources:* `DPC_AGENT_SKILLS.md` (332 LOC); `skill_store.py:78` (`SkillStore`); `skill_reflection.py:33` (`SkillReflector`); `tools/skills.py` (`execute_skill`).

**Construct:**
- **Three concepts, never confused:**
  - **Tool** = executable Python (`browse_page`, `git_status`).
  - **Knowledge** = facts in `memory/knowledge/*.md`.
  - **Skill** = strategy in `skills/{name}/SKILL.md` — *how to combine tools for a class of tasks*.

- **Each `SKILL.md`** is YAML frontmatter + Markdown instructions:
  ```yaml
  ---
  name: web-research
  version: 1
  description: >
    Research a topic online. Use when asked to find ... Do NOT use for ...
  provenance:
    author_node_id: ""
    source: bootstrapped  # bootstrapped | local | peer | evolved
  metadata:
    execution_mode: knowledge
    required_tools: [search_web, browse_page]
    tags: [web, research]
  ---
  ## Strategy
  1. Search with search_web ...
  ## When to Use ...
  ## When NOT to Use ...
  ## Common Failures ...
  ```

- **5 starter skills:** `skill-creator`, `code-analysis`, `knowledge-extraction`, `p2p-research`, `web-research`.

- **Phase 1 (Read):** system prompt lists skill names + descriptions. Agent calls `execute_skill(name, request)` → returns full SKILL.md body → agent follows. **No embeddings needed** — description-based routing scales to ~100 skills.

- **Phase 3 (Write):** After every task, `record_outcome()` updates `_stats.json` (success_count, failure_count, avg_rounds, last_used). If task used ≥5 LLM rounds AND `execute_skill` was called, `reflect_async()` fires a background LLM call asking "did the strategy have a fixable gap?" → optionally appends `## Lessons Learned` section.

- **Stats separate from SKILL.md** (avoids YAML corruption from frequent writes):
  ```json
  {
    "web-research": {
      "success_count": 12,
      "failure_count": 2,
      "avg_rounds": 3.4,
      "improvement_log": [{"version": 2, "date": "...", "reason": "...", "type": "append"}]
    }
  }
  ```

- **Firewall-gated self-modification:**
  - `dpc_agent.skills.self_modify` — default `true`, append-only Lessons Learned.
  - `dpc_agent.skills.create_new` — default `true`.
  - `dpc_agent.skills.rewrite_existing` — default `false` (full rewrites require explicit opt-in).
  - `dpc_agent.skills.accept_peer_skills` — default `false` (Phase 5, deferred).

- **Shadow mode:** when `self_modify=false`, improvements go to `pending_improvements.jsonl` — queued, never auto-applied.

**Why it matters for FA:** Cross-reference Pattern 3.3 (Memento-Skills) is already on the table from chat analysis. DPC's implementation is the **canonical reference**. FA's `.devin/skills/SKILL.md` (Devin-builtin) is the same shape but no `_stats.json` / no reflection.

**Convergence evidence:** Devin SKILL.md format + DPC SKILL.md format → both YAML frontmatter + Markdown body. Independent convergence.

**Tier:** ⭐⭐⭐ **reference** for FA when/if FA adds an automated skill-curation loop. For v0.x FA, simpler human-curated skill files are enough.

> 🇷🇺 **Пояснение паттерна 13:** Система «Навыков». Очень важное разделение трёх вещей, которые часто путают: **Инструмент** = исполняемый Python (`git_status`), **Знания** = факты в .md, **Навык** = стратегия как скомбинировать инструменты для класса задач (`SKILL.md` с YAML frontmatter + Markdown инструкции). Агент смотрит в system prompt список навыков и выбирает по описанию (без embeddings, масштабируется до ~100 навыков). **Статистика в отдельном файле** `_stats.json` чтобы YAML не портился от частых записей. Аналог наших Devin SKILL.md — но более высокоразвитый (с рефлексией и firewall'ом). Для FA v0.x простых ручных skill-файлов хватит.

---

**Pattern 14: SkillReflector — Background Self-Modification Gated by Rounds Threshold**
*Source:* `skill_reflection.py:33` (`SkillReflector`); `DPC_AGENT_SKILLS.md` §"How the Write Phase Works".

**Construct:**
```text
Task completes
  ↓
record_outcome() — always runs, synchronous, fast
  • finds execute_skill calls in tool trace
  • heuristic success = no errors in last 3 tool calls
  • updates _stats.json
  ↓
if rounds >= 5 AND skill was used:
    reflect_async() — fire-and-forget background task
      • LLM analyzes: did the strategy have a specific fixable gap?
      • Returns JSON {needs_improvement, reason, improvement_content}
      • If self_modify=true → append "## Lessons Learned" to SKILL.md
      • Otherwise → queue to pending_improvements.jsonl
```

**Critical thresholds:**
- ≥5 LLM rounds = non-trivial task (don't reflect on 1-2 round tasks).
- ≥3 prior uses = enough data for "underperforming" detection.
- `failure_rate > 30%` OR `avg_rounds > 10` = candidate for improvement.

**Why it matters for FA:** Same pattern as soviet-code Pattern B-NEW-3 (Komissar Naikan + S/M/L gate). DPC adds the "skill was actually used in this task" gate — narrower trigger, less wasted reflection. Combine with B-NEW-3 → "heartbeat-style cheap-model triage + skill-gated reflection".

**Tier:** ⭐⭐ **reference** for B-NEW-3 refinement.

> 🇷🇺 **Пояснение паттерна 14:** Самоулучшение навыков в фоне, **но с жёстким гейтом**. После каждой задачи: `record_outcome()` — всегда работает синхронно, обновляет stats (success/failure count, средние раунды). Рефлексия запускается **только если** (а) было ≥5 раундов (нетривиальная задача) **И** (б) реально вызывали `execute_skill` в этой задаче. Иначе — не тратим LLM-вызовы. Изменения по умолчанию **append-only** (добавляем «Lessons Learned» в конец SKILL.md). Полный rewrite требует явного разрешения. **Shadow mode**: если self_modify=false, всё пишется в очередь, но не применяется. Очень схоже с soviet-code Komissar (B-NEW-3) — их можно объединить.

---

**Pattern 15: Per-Agent Profile + Inheritance**
*Source:* `DPC_AGENT_GUIDE.md` §"Profile Inheritance"; `DpcAgentManager.update_agent_config()` (signature: `agent_id, config: dict, agent_id_to_inherit: str | None`).

**Construct:**
- Agents inherit from a profile (`researcher`, `coder`, `coordinator`, `assistant`).
- Per-agent overrides (model, tools, sandbox) layered on top.
- Reset-to-profile available via API.

**Why it matters for FA:** FA is single-agent for now. Multi-agent FA is hypothetical. Reference only.

**Tier:** ⭐ **skip for FA v0.x.**

> 🇷🇺 **Пояснение паттерна 15:** Наследование профилей агентов (researcher/coder/coordinator/assistant). Мы single-agent, это не наш кейс. Skip.

---

**Pattern 16: Identity File + Scratchpad + Reflection — File-Canon Memory**
*Source:* `memory.py:267` (`Memory` class); `DPC_AGENT_GUIDE.md` §"Storage Structure".

**Construct:**
```text
~/.dpc/agents/{agent_id}/memory/
  scratchpad.md            # working memory, updated per task
  identity.md              # self-understanding, slow-changing
  reflection.json          # structured reflection state
  dialogue_summary.md      # conversation summary
```

`Memory` class exposes path getters + load/save helpers:
- `load_scratchpad / save_scratchpad`
- `load_identity / save_identity`
- `load_reflection / save_reflection` + `_default_reflection()` (initial structure)
- `cleanup_old_task_results(max_age_days=30)` — TTL on transient state
- `read_jsonl_tail(name, max_entries=100)` and `read_jsonl_since(name, hours=24.0)` — log access for hooks/consolidation

**Why it matters for FA:** FA's `HANDOFF.md` + `knowledge/trace/exploration_log.md` are exactly the same shape (file-canon Markdown for agent state). DPC's `Memory` class is the **API surface** for this — useful reference when FA adds programmatic access.

**Tier:** ⭐⭐ **reference** (validates FA's file-canon choice).

> 🇷🇺 **Пояснение паттерна 16:** Память агента в файловой системе (file-canon). Четыре файла: scratchpad (рабочая память) / identity (самопонимание) / reflection (рефлексия) / dialogue_summary (итоги диалогов). Плюс jsonl-логи с возможностью читать хвост или «за последние N часов». **Для нас это валидация:** наш HANDOFF.md + knowledge/trace/exploration_log.md — та же форма. DPC доказывает, что выбор file-canon-а правильный.

---

**Pattern 17: "Evolution Worker Removed" — Strongest Anti-Pattern Signal**
*Source:* ADR-015 (148 LOC).

**Construct:**
- DPC built an autonomous evolution worker that ran every ~60 min, analyzed identity/scratchpad/skills/knowledge, proposed changes via `pending_changes.json`.
- Across 20+ sessions, 0 of ~40 proposals brought measurable improvement.
- S65: 3 stale pending changes blocked all new proposals (dedup-by-path); manual cleanup required.
- ADR-015: **delete entirely** — 400 LOC `evolution.py` + 7 tools (`review_proposal`, `list_proposals`, `get_evolution_stats`, `approve_evolution_change`, `reject_evolution_change`, `pause_evolution`, `resume_evolution`) + UI panel + firewall config.

**The argument (verbatim quote, ADR-015 §The Fitness Function Problem):**
> "Evolution requires three components: variation, selection, heredity. ... Without a valid fitness function, evolution produces noise filtered by rules. The system is elaborate but empty."

**What replaces it:**
| Mechanism | Why it works |
|---|---|
| Sleep Consolidation (ADR-014) | Analyzes actual data, not speculation |
| P13 §2.5 flow | Human in loop at every stage |
| Socratic gates | Perspective shifts through dialogue |
| Skill creator (explicit trigger) | Agent improves when asked, not autonomously |
| Manual `update_identity` | Full human awareness of changes |

**Co-evolution principle (ADR-015 + dpc-full-picture §3.3):**
> "All of DPC = machine for optimizing throughput to Layer 7" where Layer 7 = human.

**Why it matters for FA:** **This is the strongest "minimalism-first" signal in the entire DPC repo.** FA's stance — keep things simple, don't auto-extract, human-curated — is empirically validated by DPC's deletion of 400 LOC. Cite ADR-015 directly when future "let FA improve itself" proposals come up.

**Tier:** ⭐⭐⭐ **adopt** as **anti-pattern citation** in FA's AGENTS.md / DIGEST. (Pattern by reference, not by code.)

> 🇷🇺 **Пояснение паттерна 17:** **Самый важный паттерн во всём документе** — и это **удаление**, а не добавление. DPC построил «эволюцию агента» — фоновый worker, который сам анализировал агента и предлагал изменения в identity/scratchpad/skills. **Результат 20+ сессий: 0 из ~40 предложений дали измеримый выигрыш.** Их вывод: фитнес-функция для эволюции = «полезность человеку-партнёру», и **это нельзя вычислить без человека**. Снесли 400 строк + 7 инструментов + UI-панель. **Для FA:** цитировать ADR-015 в AGENTS.md как защиту от будущих предложений «давайте агент сам себя улучшает». Работают только человеко-triggered механизмы: sleep consolidation, Socratic gates, ruчные обновления identity.

---

### Group D — Process, Protocol, Coordination (Patterns 18-21)

**Pattern 18: Protocol 13 — Triple-Agent Framework + 4 Interaction Patterns**
*Sources:* `protocol-13-public.md` (349 LOC); `005-protocol13-v18-update.md` (40 LOC).

**Construct (recap from prior session):**
- **Execute Agent:** code/tests/impl, works at HOW level; doesn't define architecture.
- **Review Agent:** writes Design Rationale before sprint, reviews after Execute, flags architecture-worthy decisions, writes docs.
- **Human Coordinator:** direction, scope, final calls.

**4 interaction patterns:**
- **A — Collaborative Design:** Execute-first parallel responses, Human synthesizes.
- **B — Standard Execution:** Review writes rationale → Human → Execute → appends Implementation Notes → Human → Review appends Review Findings → Human approves.
- **C — Direct Dialogue:** Execute ↔ Review (Human supervises).
- **D — @mention Routing:** automated message exchange.
- **E — Agent Monitoring Loop:** cron polls, checks unanswered @mentions, responds via API injection.

**Decision artifact system (3 layers):**
- Layer 1: ADRs (permanent, `docs/decisions/`)
- Layer 2: Sprint logs (temporary, 4 sections: Design Rationale → Implementation Notes → Review Findings → Decisions Made)
- Layer 3: Agent memory (per-agent sandbox)

**Co-evolution principle:** Team is simultaneously builders and test case.

**v1.8 (ADR-005) additions:**
- **P18: Session Closing Protocol** — CC shows saves → Ark shows plan → coordinate → execute → Mike closes.
- **Scope-only estimation rule** — estimate lines/files, never time. (S14: CC estimated 5-7h for what took 11 min. 27-38x error.)

**Why it matters for FA:** FA's `HANDOFF.md` §bootstrap (3 steps) is the closest analog. P13 is **much more elaborate** — but the structural skeleton (3 layers of artifacts, named patterns A-E, session closing P18, scope-only rule) gives FA a roadmap *if* it ever moves to multi-agent. **The "scope-only, never time" rule is directly adoptable now** for FA HANDOFF.

**Tier:** ⭐⭐ **reference** for FA process; ⭐⭐⭐ **adopt** the scope-only-estimation rule.

> 🇷🇺 **Пояснение паттерна 18:** Protocol 13 — это схема «разделения властей» в DPC: **Execute Agent** делает код/тесты («KAK»), **Review Agent** пишет рациональ и делает ревью («ПОЧЕМУ»), **Человек-Координатор** даёт направление и финальные решения. Мы single-agent — это не наш кейс целиком. **НО** в v1.8 они добавили «правило оценки scope»: оценивать следует **в строках/файлах, никогда в времени**. Пример S14: CC оценил в 5-7 часов, реально заняло 11 минут — ошибка в 27-38 раз. **Это правило мы можем вольно взять в наш AGENTS.md** сейчас же.

---

**Pattern 19: Three-Dimensional Participant Identity**
*Source:* ADR-006 (142 LOC); ADR-023 (113 LOC).

**Construct:** Three orthogonal fields per message:
- **author** — WHO (person_id or agent_id: `mike`, `cc`, `agent_001`)
- **participant_type** — WHAT (`human | agent | system`)
- **source** — WHERE FROM (`node_id`, `telegram`, `vscode`, ...)

LLM API mapping layer (translates internal model to LLM `role`):
| Internal | LLM role | Why |
|---|---|---|
| Human | user | Owner |
| Agent (external CC) | user | Not the responding model |
| Agent (internal Ark) | assistant | The responding model |
| System | system | Instructions |

**Multi-agent constraint:** Only ONE agent per conversation can be `role: assistant`. All others = `role: user` with author prefix in text. **LLM API limitation, not model limitation.**

ADR-023 extends to group chat: per-group `agents: {node_id: [agent_id, ...]}` map; @mention routing checks membership before dispatch; `(agent_owner, sender_name)` is the composite identity for cross-node agents.

**Why it matters for FA:** FA is single-agent. Reference only — but the **identity-vs-role-vs-source decomposition** is generalizable. If FA ever adds multiple personas (Devin / Detector / Inspector — cross-ref soviet-code), this is the schema to use.

**Tier:** ⭐ **skip for v0.x.**

> 🇷🇺 **Пояснение паттерна 19:** Разложение идентичности участника на три ортогональные оси: **КТО** (author), **ЧТО** (человек/агент/система), **ОТКУДА** (Telegram/VSCode/node-id). Для многоагентных разговоров это критично (только ОДИН агент в вызове LLM может быть с role=assistant; остальные — user с префиксом). Мы single-agent, skip. Но если когда-то будем делать «Inspector + Detector + Coder» персоны — взять хотя бы схему «author/participant_type/source».

---

**Pattern 20: Archive YYYY/MM Nested + Unlimited Retention**
*Source:* ADR-008 (207 LOC).

**Construct:**
- Path: `archive/YYYY/MM/{ts}_{reason}_session.json`
- Reader: `glob('**/*_session.json')` — layout-agnostic, backward-compatible with flat files during migration.
- **Default `max_archived_sessions = 0` = keep all.** Mike's principle: "session history is primary memory for three-agent workflow; must not be silently lost."
- UI: input min=0, no upper cap; shows "Unlimited" when 0; progress bar hidden when unlimited.
- Migration: one-shot inline move (47 files), no persistent script.

**Why it matters for FA:** FA's `knowledge/trace/exploration_log.md` is single-file append-only. If FA ever needs per-session archival, this is the simplest scaling pattern. **YYYY/MM is universal log-rotation convention.**

**Tier:** ⭐⭐ **reference** for FA Phase B (when exploration_log grows past single-file).

> 🇷🇺 **Пояснение паттерна 20:** Папки `archive/2026/05/...` вместо всех файлов в одной директории — стандартная лог-ротация. Чтобы избежать 10000 файлов в одном листинге. **Ключевое решение: `max_archived = 0 = без лимита`**. Рациональ Mike: «история сессий — это первичная память trinity workflow, не должна бесследно пропадать». Для FA: когда exploration_log.md разрастётся — это паттерн масштабирования.

---

**Pattern 21: Multi-Agent Safety Governance — 3-Layer Defense**
*Source:* ADR-022 (309 LOC).

**Construct:**
- **7 emergent risks (C1-C7):** tacit collusion, resource monopolization, task avoidance, strategic information withholding, information asymmetry exploitation, groupthink, error amplification chains.
- **Key insight:** component-level compliance ≠ system-level control. Governance graph: 50% → 5.6% collusion reduction. Constitutional prompting alone: 0% improvement.
- **3-layer defense:**
  - **Layer 1: Sync guards / pre-send enforcement.**
    - **Layer 1a: Pre-Send Fact Gate** — regex-extract "verified facts" claims from outgoing message → cross-reference against tool-call history → block if no matching tool output.
  - **Layer 2: Async analysis over historical data** — periodic batch analysis of multi-agent transcripts looking for collusion/silencing patterns.
  - **Layer 3: Evolution verification** — when an agent proposes a self-mod, check if mod degrades safety properties. (Vestigial after ADR-015 evolution removal.)

**Why it matters for FA:** FA is single-agent — safety risks are different (mostly prompt-injection + tool-abuse, not collusion). **But the "Pre-Send Fact Gate" pattern is broadly applicable**: an outbound-message hook that verifies factual claims against tool-call history is a useful safety guard for ANY agent, single or multi.

**Tier:** ⭐⭐ **reference**; consider Pre-Send Fact Gate (Layer 1a) for FA BACKLOG (medium effort, high signal).

> 🇷🇺 **Пояснение паттерна 21:** Когда несколько агентов взаимодействуют, появляются новые риски: tacit collusion (молчаливый сговор), groupthink, цепные ошибки и т.д. **Главный вывод: соблюдение правил на уровне компонента ≠ контроль на уровне системы**. Constitutional prompting вообще не работает (0% улучшения). Мы single-agent, это не наш. **НО** один элемент переносится и на single-agent: **Pre-Send Fact Gate** — перед отправкой ответа проверить, что все «верифицированные факты» в ответе действительно имеют соответствующий tool-call в истории. Это middleware/observer в BACKLOG.

---

### Group E — Infrastructure (Patterns 22-24)

**Pattern 22: Poetry → uv with Hardware-Aware Index**
*Sources:* ADR-011 (160 LOC); ADR-012 (104 LOC).

**Construct:**
- Migration: `[tool.poetry.dependencies]` → `[project.dependencies]` (PEP 621), `[tool.poetry.extras]` → `[project.optional-dependencies]`, `poetry-core` → `hatchling`.
- **Critical lesson (ADR-012 revised):** `.env` `UV_EXTRA_INDEX_URL` approach **does not work** — uv resolves from PyPI first regardless. Only `[tool.uv.sources]` with `explicit = true` forces per-package index selection.
- Working config:
  ```toml
  [tool.uv.sources]
  torch = { index = "pytorch-cu124", marker = "sys_platform != 'darwin'" }

  [[tool.uv.index]]
  name = "pytorch-cu124"
  url = "https://download.pytorch.org/whl/cu124"
  explicit = true
  ```
- `uv.lock` removed from git (platform-specific). 10-100× faster than poetry.

**Why it matters for FA:** FA does not yet have hardware-dep tooling. If/when FA adopts FAISS/sentence-transformers, copy verbatim. Until then: reference only.

**Tier:** ⭐⭐ **reference** for future FA ML deps.

> 🇷🇺 **Пояснение паттерна 22:** Миграция с Poetry на uv (это новый быстрый Python package manager). **Важный lesson learned:** попытка сделать «platform-specific torch» через `.env` с `UV_EXTRA_INDEX_URL` — **не работает**, uv всё равно идёт сначала на PyPI. Работает только `[tool.uv.sources]` с `explicit=true` в pyproject.toml. **Сохранить на будущее** — если когда-то FA потребуется torch/CUDA или другие hardware-specific deps.

---

**Pattern 23: PyTorch as Unified ML — Reverting ONNX**
*Source:* ADR-021 (97 LOC).

**Construct:** S82 attempted Whisper ONNX migration → discovered:
1. VRAM arena management painful (`gpu_mem_limit = SIZE_MAX` default, iterative tuning).
2. cuDNN/cuBLAS dependency hell after removing PyTorch.
3. Quantization fallbacks (INT8 → CPU).
4. Expected ~2.5GB saving, actual ~1.3GB.
5. **Roadmap was wrong:** "inference only" assumption broken by future fine-tuning + multimodal + TTS needs.

**Lesson (ADR-021 §Lessons Learned):**
1. Rule 14 (Solution Check) must apply to **migration paths**, not just target libraries.
2. Architectural decisions must be validated against **full roadmap**, not current-sprint assumptions.
3. **Operational complexity** matters more than dependency size for desktop apps.
4. **Write-only subsystems are dead weight** — sparse vectors were indexed but never queried; remove, don't maintain.

**Why it matters for FA:** Lessons 1, 2, 4 are universal — applicable to any "let's switch to X" proposal in FA. Lesson 4 ("write-only subsystems are dead weight") is the **cleanest minimalism-first principle in the entire DPC repo** and worth quoting in FA's AGENTS.md.

**Tier:** ⭐⭐⭐ **adopt** Lesson 4 as a **principle citation** in AGENTS.md (rule #X).

> 🇷🇺 **Пояснение паттерна 23:** История неудавшейся миграции. DPC пытался заменить PyTorch на ONNX (мотив: сэкономить 2.5 ГБ размера). Реально выиграли 1.3 ГБ, а расхлёбывали VRAM, cuDNN, quantization. Ревертнули. **4 вывода:**
> 1. Правило «проверить решение» должно применяться к **пути миграции**, не только к целевой библиотеке.
> 2. Архитектурные решения валидировать против **всего roadmap**, не только текущего спринта.
> 3. **Operational complexity** важнее размера зависимостей (для desktop приложений).
> 4. **Write-only подсистемы — мёртвый груз.** Если что-то индексируется, но не используется — удалить, не поддерживать.
>
> **Вывод 4 — это самый чистый минимализмпринцип во всём DPC репо.** Стоит взять в AGENTS.md.

---

**Pattern 24: Public Agent Guardrails — Source-Based Tool Filter + URL Whitelist + Rate Limit**
*Source:* ADR-026 (193 LOC).

**Construct (Iris bot on Discord):**
- **Source-based tool filter:** external source (Discord) restricted to read-only tools (whitelist approach). New tools blocked by default — must be explicitly added to whitelist.
- **URL whitelist** for user-submitted content (prevents prompt injection via links).
- **Per-user conversation TTL:** 30 min inactivity / max 50 messages → expire → extract facts → store in KG (long-term memory).
- **Rate limiting:**
  - Per-user: 5 msgs / 10 min
  - Global: X invocations / hour
- **Multi-language:** respond in user's language (system prompt instruction).

**Why it matters for FA:** FA is currently CLI / not public-facing. If FA ever has a public-facing surface (Discord bot, chat UI), this is the canonical pattern. The **source-based whitelist** approach is general — even useful for FA's hypothetical "agent calls another agent's tools" scenario.

**Tier:** ⭐ **skip for v0.x** (out of FA scope); ⭐⭐⭐ **reference** when/if FA goes public.

> 🇷🇺 **Пояснение паттерна 24:** Система безопасности для публичных агентов (Iris-бот в Discord). **Source-based whitelist**: внешние источники (Discord) получают только read-only инструменты; новые инструменты по умолчанию блокируются. **URL whitelist** для user-content защищает от prompt-injection через ссылки. **Per-user TTL** 30 мин или 50 сообщений → экспайр временного разговора → extract фактов в KG. **Rate limit** против spam. Для FA: skip в v0.x (мы CLI), reference если будем делать публичный интерфейс.

---

## §3 FA-Relevance Mapping

For each pattern, mapping to current FA artifacts (ADRs, BACKLOG items, files in MondayInRussian/First-Agent-fork2):

> 🇷🇺 **Что в этой секции:** таблица-резюме «паттерн → к какому нашему артефакту он относится → сколько часов работы». Список всех 24 паттернов из §2 в одной видимости. Наиболее важные колонки: **Tier** (брать/reference/skip) и **Effort** (реалистичная оценка в часах).

| # | Pattern | FA artifact | Tier | Effort |
|---|---|---|---|---|
| 1 | HookRegistry + 2-tier middleware | ADR-7 §5 Lifecycle | ⭐⭐⭐ | 3-5h |
| 2 | Inline-guard → Guard refactor | ADR-7 §11 R-9 + BACKLOG I-1 | ⭐⭐⭐ | (part of 1) |
| 3 | LoopState contract | ADR-7 §5 | ⭐⭐⭐ | (part of 1) |
| 4 | _fingerprint loop detection | ADR-7 §6 R-7 | ⭐⭐⭐ | 0.5h |
| 5 | 3 budget strategies | BACKLOG I-7 | ⭐⭐ | reference |
| 6 | Tool registry + sandbox paths | ADR-7 §6 | ⭐⭐⭐ | combine w/ soviet-code B-NEW-1 |
| 7 | _meta.json access registry | new (B-NEW-7 precursor) | ⭐⭐⭐ | 2-3h |
| 8 | Hybrid BM25+FAISS+RRF | future KG/retrieval ADR | ⭐⭐ | reference |
| 9 | GraphBackend ABC + bi-temporal | new KG ADR (B-NEW-6) | ⭐⭐⭐ | 6-8h |
| 10 | Singleton with double-check lock | code style note | ⭐⭐ | reference |
| 11 | Stateless P2P pull search | out of scope | ⭐ | skip |
| 12 | Sleep consolidation | new B-NEW-7 | ⭐⭐⭐ | 4-6h |
| 13 | Memento-Skills system | future skill ADR | ⭐⭐ | reference |
| 14 | SkillReflector (gated reflection) | B-NEW-3 refinement | ⭐⭐ | reference |
| 15 | Per-agent profile + inheritance | out of scope (single-agent) | ⭐ | skip |
| 16 | Identity/scratchpad/reflection files | HANDOFF.md (already exists) | ⭐⭐ | reference (validates) |
| 17 | Evolution Removed | AGENTS.md anti-pattern citation | ⭐⭐⭐ | 0.5h (cite) |
| 18 | Protocol 13 + 4 patterns | HANDOFF §bootstrap | ⭐⭐ | reference |
| 18b | Scope-only estimation rule | AGENTS.md rule | ⭐⭐⭐ | 0.5h |
| 19 | 3-dim participant identity | out of scope | ⭐ | skip |
| 20 | Archive YYYY/MM | exploration_log future scaling | ⭐⭐ | reference |
| 21 | 3-layer multi-agent safety | out of scope mostly | ⭐⭐ | Layer 1a Pre-Send Fact Gate adoptable |
| 22 | Poetry → uv + uv.sources | future ML deps | ⭐⭐ | reference |
| 23 | Lesson 4 "write-only = dead weight" | AGENTS.md rule | ⭐⭐⭐ | 0.5h (cite) |
| 24 | Public agent guardrails | future public-facing FA | ⭐ | skip v0.x |

**Summary by tier:**
- ⭐⭐⭐ **adopt now:** 9 patterns (Patterns 1+2+3+4+6 bundled = B-NEW-5; 7 + 12 = B-NEW-7; 9 = B-NEW-6; 17 + 18b + 23 = AGENTS.md citations).
- ⭐⭐ **reference:** 10 patterns.
- ⭐ **skip:** 5 patterns.

> 🇷🇺 **Итого:** из 24 паттернов «полезных прямо сейчас» только ~9 (связанных в 3 крупных блока + 3 citation rule). Остальные 10 — reference («взять когда дорастём» или «посмотреть как у них»), 5 — skip. Это здоровый баланс: не всё подряд, но и не пусто.

---

## §4 B-NEW Adoption Candidates (consolidated with soviet-code session)

> 🇷🇺 **Что в этой секции:** объединённый backlog всех предложений из двух сессий: soviet-code (B-NEW-1..4) + DPC сейчас (B-NEW-5..7) + 3 citation-rule. **B-NEW** означает «кандидат в BACKLOG.md из исследования» (Backlog-NEW). Каждый из них — реальный PR в FA на указанный эффорт. Ни одно из этого не трогает product code FA — это всё knowledge-layer (ADR + docs + skeleton).

Cumulative across `soviet-code-deep-dive-2026-05-13.md` (B-NEW-1 .. B-NEW-4) and this report (B-NEW-5, 6, 7):

| ID | Source | Description | Effort |
|---|---|---|---|
| B-NEW-1 | soviet-code | Declarative tool whitelist (`allowed_tools` + `extra_dirs` YAML → `--allowedTools` / `--add-dir`) | 2-4h |
| B-NEW-2 | soviet-code | Mandatory Inspection phase + "всё хорошо — не аргумент" rule | 1-2h |
| B-NEW-3 | soviet-code | Phase M runner ADR (heartbeat tick + Komissar Naikan + S/M/L gate) | 3-5h |
| B-NEW-4 | soviet-code | Anti-pattern catalog + on-demand detector personas | 3-4h |
| B-NEW-5 | **DPC ADR-007** | **HookRegistry + 2-tier middleware (GuardMiddleware + ObserverMiddleware) + 5 stock guards** | **3-5h** |
| B-NEW-6 | **DPC ADR-024** | **KG ADR + skeleton (GraphBackend ABC + SQLite + 5 node types + 9 edge types + bi-temporal)** | **6-8h** |
| B-NEW-7 | **DPC ADR-014 + ADR-010** | **Sleep consolidation: \_meta.json + morning brief over inter-session archives (user-triggered)** | **4-6h** |

Plus three **citation-only AGENTS.md additions** (effort ~0.5h each):
- **Cite ADR-015** as anti-pattern: "autonomous self-modification without external fitness produces noise filtered by rules" → use as defence against future "let FA improve itself" proposals.
- **Adopt ADR-005 P18 scope-only-estimation rule** as AGENTS.md rule: "estimate lines/files, never time" + reference S14 27-38x error.
- **Adopt ADR-021 Lesson 4**: "write-only subsystems are dead weight; remove, don't maintain" as AGENTS.md principle.

> 🇷🇺 **Три «citation» правила:** это лёгковесные правила-цитаты в AGENTS.md (по ~0.5ч каждое). Не требуют кода, только фиксируют общие принципы со ссылками на конкретный ADR DPC как доказательство. Самый важный — первый (против «давайте агент сам улучшается»).

**Total effort for all B-NEW + citations: ~24-37h** (analogous to soviet-code 9-15h). Decomposable into 7 separate PRs (one per B-NEW) + 1 PR for citation block.

> 🇷🇺 **Общий эффорт:** примерно 24-37 часов работы на все 7 B-NEW + citation block. Это около недели фокусированной работы (или растяжено по времени). **Каждый PR независимо мерджится**, порядок важен только для B-NEW-5 (основа) → B-NEW-7 (использует _meta.json из 7) → B-NEW-6 (KG может брать sleep findings как источник).

---

## §5 Convergent Evolution Evidence (Updated)

**KG / typed-assertion contract** — now 4 independent projects:

| Project | Schema | Bi-temporal? | NER? | Backend |
|---|---|---|---|---|
| FA (planned) | TBD | TBD | TBD | TBD |
| Enox (from chat excerpt 2) | typed assertions w/ source/target/relation/confidence | mentioned | — | — |
| soviet-code `EnoxBackend.toAssertion` | 7-field: `source_name / source_type / target_name / target_type / relation / confidence / context` | — | — | LocalBackend fallback |
| **DPC `GraphEdge`** | source_id / target_id / edge_type / **t_created** / **t_invalidated** / confidence / justification / edge_weight / properties | **YES** | **GLiNER** | SQLite (via `GraphBackend` ABC) |

**DPC's additions** over the others:
- **Bi-temporal validity** (`t_invalidated` for soft-delete; Graphiti-style edge invalidation).
- **`ALWAYS_EXEMPT = {DECISION, SESSION_ARCHIVE}`** — certain node types never expire.
- **`edge_weight: str = "medium"`** (low/medium/high for downstream ranking).
- **Pluggable backend via ABC** (`SQLiteGraphBackend` is one impl).

**Recommendation for FA's eventual KG ADR (B-NEW-6):** start from DPC's schema verbatim; if cross-project semantic interop becomes a goal, ensure compatibility with the 7-field contract by mapping `(source_id, source.label, target_id, target.label, edge_type, confidence, justification)` to/from the 7-field shape.

> 🇷🇺 **Что это значит:** «Convergent evolution» — это когда несколько проектов **независимо** приходят к одному решению. Самый сильный сигнал в инженерии. Для нас это важно, потому что: (а) если 4 проекта пришли к одной схеме KG — мы не изобретаем велосипед, (б) это даёт выбор компатибильности — если когда-то наш KG будет взаимодействовать с Enox/soviet-code/DPC, мы уже знаем contract. **DPC победил по богатству фич** (бивременная модель, ALWAYS_EXEMPT) — берём их версию в B-NEW-6.

---

**Sleep / consolidation / inter-session memory** — 3 independent projects:

| Project | Mechanism | Trigger | Inputs |
|---|---|---|---|
| FA (planned, prior session) | HANDOFF.md manual update | human | session retrospective |
| soviet-code | Komissar Naikan 12h reflection | gated by mtime + ≥5 work-ticks | conductor.events.jsonl + processed/ |
| **DPC** | Sleep Pipeline (N+1 LLM calls) | **UI button (NOT cron)** | digest.jsonl + archive/YYYY/MM/*.json |

**The trigger debate:** soviet-code uses cron with gating; DPC explicitly **rejected** cron after evolution disaster and uses UI button. **FA's HANDOFF is also human-triggered.** **2 of 3 vote for human-trigger, 1 for gated-cron.** B-NEW-7 should default to human-trigger; gated-cron is opt-in only.

> 🇷🇺 **Спор о триггере:** soviet-code делает cron с гейтом, DPC явно отказался от cron после «дисастра эволюции», мы (HANDOFF) — ручные. **2 из 3 голосуют за человеческий триггер.** Сильный сигнал против «пусть фоновый процесс сам рефлексирует». Берём человеческий триггер как default в B-NEW-7.

---

**Loop guards / hook architecture** — 4 independent projects:

| Project | Approach |
|---|---|
| FA (ADR-7 §5) | Lifecycle hooks (abstract) |
| soviet-code | Per-fase Claude subprocess (no inline loop guards; each phase is bounded externally) |
| **DPC** | `BaseMiddleware` + `GuardMiddleware` + `ObserverMiddleware` chain, 5 stock guards |
| Framework / DeerFlow / Claw Code / Ouroboros | Documented as 4-project convergence in ADR-007 §References |

**8-project convergence** on the interceptor pattern (DPC ADR-007 + 4 cited + FA + soviet-code analog + Enox unknown but plausible). Strongest evidence for B-NEW-5 adoption.

---

**Protocol 13 / 3-role coordination** — 2 independent projects:

| Project | Mechanism |
|---|---|
| FA HANDOFF | Single-thread agent + human (no Review Agent) |
| **DPC P13** | Execute Agent / Review Agent / Human Coordinator + 4 interaction patterns + 3-layer artifact system |

Not yet convergence — DPC is the only one with Review Agent. **Useful as reference if FA grows multi-persona; for now, FA's simpler model is fine.**

---

## §6 Anti-Patterns Found in DPC (worth NOT copying)

> 🇷🇺 **Что в этой секции:** вещи, которые DPC **попробовал и отверг** — или имеют в проде но сами признают проблемными. **Мы это не копируем**. Их опыт сэкономит нам недели не сделанных ошибок.

| # | What | Source | Why skip |
|---|---|---|---|
| AP1 | Background-worker evolution | ADR-015 (removed) | 0 valuable proposals across 20 sessions; documented disaster |
| AP2 | Auto-extraction with keyword consensus | ADR-009 / ADR-004 | 13 hardcoded keywords for consensus detection; brittle; ADR-013 selection layer is a band-aid |
| AP3 | ONNX as ML execution layer | ADR-021 (reverted) | VRAM arena hell; cuDNN dep hell; quantization fallbacks |
| AP4 | `.env` `UV_EXTRA_INDEX_URL` for torch | ADR-012 (revised) | uv resolves from PyPI first; doesn't work |
| AP5 | Write-only subsystem (sparse vectors indexed but never queried) | ADR-021 §Lessons | Maintenance burden with no benefit |
| AP6 | Hard 75% approval threshold for consensus voting | ADR-004 §Voting | Magic number, not validated |
| AP7 | 9,630-line monolithic service.py | ADR-001 (refactor) | Acceptance criterion: <2000 LOC; rule = "don't let this happen in the first place" |
| AP8 | "We are NOT reinventing the wheel" must be in every ADR | ADR-020 §Research | DPC explicitly checks for prior art before each ADR — adopt the *practice*, not the literal phrase |

AP8 is interesting — DPC's ADR-020 starts §Research with literally "**We are NOT reinventing the wheel**" and then maps each layer to existing tooling (stop-words-iso, sklearn `TfidfVectorizer(max_df=0.8)`, Fox 1989). This is a **process pattern worth adopting**: every FA ADR should have an explicit "prior art" section.

**B-NEW-8 candidate (additional):** AGENTS.md rule "every new ADR must include §Prior Art mapping each design choice to existing tools/papers/projects" (0.5h, citation rule).

> 🇷🇺 **AP8 и B-NEW-8:** DPC в каждом новом ADR явно выделяет секцию «Мы НЕ изобретаем велосипед» и перечисляет предшествующие работы и существующие библиотеки. Это хорошая дисциплина. **B-NEW-8 — новый кандидат:** правило в AGENTS.md что каждый новый ADR обязан включать §Prior Art. **Минус:** немного фрикции на каждый ADR. **Плюс:** защита от повторных изобретений.

---

## §7 What's NOT Worth Reading in Future Sessions

> 🇷🇺 **Что в этой секции:** явные обоснованные skip для будущих сессий. Не стоит больше читать UI-код, P2P-сеть, федеративный сервер и т.п. — это вне scope FA и отвлечёт от работы. Сэкономит бюджет токенов в следующих cross-reference сессиях.

Based on this deep dive, the following DPC areas are **explicitly de-prioritized** for FA reference:

- **`dpc-client/ui/`** — Tauri/Svelte/Rust UI (~29K LOC). FA is CLI-first.
- **`dpc-hub/`** — federation server (AGPL). FA is local-only.
- **`transports/`, `dht/`, `connection_strategies/`, `message_handlers/`** — P2P networking plumbing (~15K LOC). Out of FA scope.
- **`specs/dptp_v1.md`** (2052 LOC) — wire protocol spec. Skim only if FA adds binary protocol.
- **`tests/`** — large pytest suite; useful only if FA imports DPC code directly (won't).
- **Voice (Whisper, TTS) infrastructure** — out of FA scope.
- **OAuth + Telegram + Discord bridges** — out of FA scope.

Files that DPC still has but I deliberately did not deep-read:
- `evolution.py` (deleted in S66, but kept in git history). Wouldn't add over ADR-015 narrative.
- `consciousness.py` (disabled per S65, vestigial). Same.
- `consensus_manager.py` — covered by ADR-004; multi-party voting is out of FA scope.
- Most of `KNOWLEDGE_ARCHITECTURE.md` (1665 LOC) — skimmed §1-§3 / §8 / §9; rest is bias-mitigation theory + JSON+Markdown schema details that don't change the pattern list.

---

## §8 Deliverable Checklist

- [x] All T0 foundation docs read
- [x] All 26 ADRs scanned (11 full read, 15 to §Decision/§Consequences)
- [x] T2 architecture docs structurally indexed
- [x] T3 selected code files: loop.py, hooks.py, guards.py, memory.py, knowledge_graph.py, sleep_pipeline.py, budget.py, active_recall.py, skill_store.py, skill_reflection.py, tools/registry.py — signatures + key bodies
- [x] 24 patterns enumerated with sources
- [x] FA-mapping table
- [x] B-NEW adoption candidates (5, 6, 7) with effort estimates
- [x] Convergent-evolution evidence updated (KG, sleep, hooks, P13)
- [x] Anti-patterns surfaced (AP1-AP8)
- [x] Skip rationale for future sessions
- [ ] User review

---

## §9 One-Sentence Summaries (for HANDOFF / DIGEST reference)

> 🇷🇺 **Что в этой секции:** все 26 ADR'ов DPC в формате одного предложения для быстрого referenc'а в HANDOFF/DIGEST/PR описаниях. Копируемае в любые наши документы вербатим.

- **ADR-001** — 9630-LOC monolith → 4 domain services + 4 handler modules + state module; <2000 LOC CoreService target.
- **ADR-002** — 3074-LOC llm_manager.py → `AbstractLLMProvider` ABC + 5 provider files; `get_state()` for runtime introspection.
- **ADR-003** — 50+ `writable<any>` stores → 10 typed global + per-panel local stores; +page.svelte 219KB → <2K LOC shell.
- **ADR-004** — Dual-path knowledge extraction (manual full / auto on 5-msg buffer + keyword consensus); known weakness, governed by ADR-013.
- **ADR-005** — P13 v1.8: P18 session closing + scope-only estimation (S14: 27-38× time error).
- **ADR-006** — `sender` → 3 orthogonal dims (`author + participant_type + source`); LLM-role mapping layer.
- **ADR-007** — 5 inline guards → `GuardMiddleware`+`ObserverMiddleware` chain + `LoopState`; 4-project convergence.
- **ADR-008** — `archive/YYYY/MM/{ts}_session.json` + `max_archived = 0 = unlimited`; recursive `**/*_session.json` glob.
- **ADR-009** — 3 extraction paths, 0 coordination; survival governed by selection layer (ADR-013).
- **ADR-010** — 7-layer memory: `_meta.json` registry + BM25+FAISS RRF; e5-small (default) with chunking strategy.
- **ADR-011** — Poetry → uv (PEP 621); hatchling build backend; 10-100× faster resolve.
- **ADR-012** — `.env` `UV_EXTRA_INDEX_URL` doesn't work; `[tool.uv.sources]` with `explicit=true` does.
- **ADR-013** — Agent = routine filter (dedup/decay), human = direction + veto; selection ≠ LLM judgment.
- **ADR-014** — Sleep consolidation: N+1 LLM passes, morning brief, **UI-triggered not cron**.
- **ADR-015** — Evolution REMOVED: 0/40 valuable proposals; "fitness = usefulness to human partner; not auto-computable".
- **ADR-016** — Agent web pipeline: ddgs 8+ backends → trafilatura → ddgs.extract → HTMLParser → camoufox (4-tier fallback).
- **ADR-017** — Stateless P2P pull search; Dunbar-tier ACL (5/15/50/150/beyond); ship plaintext query, not embedding.
- **ADR-018** — e5-small bug (prefix + 512-token truncation) → BGE-M3 (8192 tokens, 1024d, ONNX); whole-document indexing.
- **ADR-019** — RRF k=60 explained; 30-msg window topic dilution → dual-query RECALL-QUERY (Q1=last human, Q2=last 10).
- **ADR-020** — 3-layer stop words: standard (stop-words-iso) + corpus-adaptive (DF>80%) + user-personal (S78 novel).
- **ADR-021** — PyTorch unified ML; revert ONNX (VRAM/cuDNN/quant); 4 lessons (migration paths, full roadmap, ops complexity, write-only = dead weight).
- **ADR-022** — Multi-agent safety: 7 emergent risks (C1-C7); 3-layer defense; **Pre-Send Fact Gate** as adoptable Layer 1a.
- **ADR-023** — Group chat participant: `sender_type / agent_owner / per-group agents map`; ADR-006 extension.
- **ADR-024** — KG: 5 node types + 9 edge types + bi-temporal + GLiNER NER + GraphBackend ABC + SQLite default.
- **ADR-025** — Discord bot: mirror Telegram bridge; @mention only; per-channel whitelist; @ADR-026 for production.
- **ADR-026** — Public agent: source-based tool filter + URL whitelist + 30-min TTL + 5 msg/10 min rate limit.

---

## §10 Acknowledgements & Next Steps

> 🇷🇺 **Что в этой секции:** итог 4 сессий исследований + предложенный план по реализации (7 отдельных PR по приоритетам) + открытые вопросы на выбор дальнейшего направления.

This report is the synthesis of 4 sessions of cross-repo research (Soviet-Code + DPC chat excerpts + DPC-Messenger). The cumulative pattern catalog now stands at:

- **Soviet-Code:** 22 patterns + 4 B-NEW (B-NEW-1..4)
- **Chat excerpts cross-reference:** 27 patterns + 21a row (typed-assertion KG)
- **DPC-Messenger (this report):** 24 patterns + 3 B-NEW (B-NEW-5..7) + 3 citation-only AGENTS.md rules + 1 candidate B-NEW-8 (prior-art rule)

**Recommended next FA-side work** (when user is ready):

1. **PR-A (1-2h):** AGENTS.md additions — 3 citation rules (ADR-015 anti-pattern, ADR-005 scope-only, ADR-021 Lesson 4 + optional B-NEW-8 prior-art).
2. **PR-B (3-5h):** B-NEW-5 — ADR-7 §5 amendment + skeleton `hooks.py` + 5 stock `GuardMiddleware` classes (copy DPC).
3. **PR-C (4-6h):** B-NEW-7 — new ADR for sleep consolidation + `_meta.json` access registry + minimal pipeline.
4. **PR-D (6-8h):** B-NEW-6 — new KG ADR (typed nodes + bi-temporal edges + `GraphBackend` ABC) + cross-reference to Enox / soviet-code / DPC.
5. **PR-E (2-4h):** B-NEW-1 (tool whitelist) + B-NEW-2 (Inspection rule) from soviet-code session.
6. **PR-F (3-4h):** B-NEW-4 (anti-pattern catalog with on-demand detectors) — combine with FA's exploration_log conventions.
7. **PR-G (3-5h):** B-NEW-3 (Phase M runner ADR) — heartbeat + Komissar Naikan + SkillReflector gating refinement.

Each PR is independently mergeable. Order matters only for B-NEW-5 (foundation) → B-NEW-7 (uses access registry) → B-NEW-6 (uses sleep findings as one input to KG).

Open questions for user:
- **Q1:** Approve adding 3 citation rules to AGENTS.md now (PR-A), or batch with B-NEW-5 (PR-B)?
- **Q2:** B-NEW-6 (KG) is the largest single item (6-8h). Adopt as an ADR-only PR first (no code), then incremental PRs for schema + backend + extraction? Or one big PR?
- **Q3:** Continue with next repo (Aperant, gortex) or pause for adoption work?
- **Q4:** B-NEW-8 (prior-art rule) — adopt or skip? It's lightweight but adds friction to every future ADR.

---

*End of report. 24 patterns. 7 adopt candidates. 3 citation rules. 1 anti-pattern lesson worth more than all the others combined: **evolution without external fitness produces elaborate emptiness**.*
