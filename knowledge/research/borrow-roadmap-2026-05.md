---
title: "FA Borrow-Roadmap — consolidated action items from 7 research notes"
source:
  - "knowledge/research/gortex-aperant-inspiration-2026-05.md"
  - "knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md"
  - "knowledge/research/dpc-messenger-inspiration-2026-05.md"
  - "knowledge/research/chat-cross-reference-2026-05.md"
  - "knowledge/research/kronos-agent-os-inspiration-2026-05.md"
  - "external: user-curated borrow-list (2026-05-13)"
  - "external: yt-concepts-for-FA.md (4 YT summaries, 21 concepts)"
compiled: "2026-05-13"
goal_lens: "Извлечь из 7 research-нот concrete actionable list для FA Phase M implementation; bypass research → ADR → impl cycle через targeted borrowing."
chain_of_custody: |
  Все R-N derived from prior research notes (compiled 2026-05-08..2026-05-13) + user
  manual selection 2026-05-13. Source notes остаются source of truth для глубоких
  деталей; эта нота — индекс для действий. Каждый R-N имеет поле «Source(s)» с
  путём к исходной ноте и §-номером для глубоких деталей. Russian primary prose
  per AGENTS.md §Conventions; English identifiers (file paths, ADR refs, LOC,
  function names, YAML keys, code blocks) сохранены в оригинале как точки поиска.
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification: []
---

> **Status:** active. Inspiration-consolidation note. Не произведена через
> `knowledge/prompts/research-briefing.md`; §0 retrofitted с cross-source R-N.
>
> **Назначение:** working backlog для Phase M implementation. После того как
> R-N landed (PR merged), его строка в §3 master mapping таблице переходит
> из `pending` в `landed` без удаления — нота остаётся audit-trail.
>
> **Reading guide:** §0 (47 R-N) — для project lead и LLM-агентов, читающих
> «сверху вниз»; mirrors chat-handover. §1..§10 — глубокие сечения; грузить
> только когда §0 недостаточно. **Когда нужны deep-dive по конкретному источнику** — открывать source-ноту из frontmatter, не эту.

---

## 0. Decision Briefing

> 🇷🇺 **Что в этой секции:** 47 R-N (recommendations / actionable items),
> сгруппированных по группам A..J (FA-оси, не по source-проекту). Каждый блок
> следует AGENTS.md §0 контракту (8 полей + 7-col Summary table). Поле
> **Source(s)** добавлено к стандартному шаблону — указывает откуда взято и
> где живут глубокие детали.



## TL;DR

🇷🇺 **Что это:** консолидированный action-backlog из 7 research-нот (gortex-aperant /
correlated-llm-errors / dpc-messenger / chat-cross-reference / kronos-agent-os) +
4 YT-конспектов + soviet-code B-NEW-* (через DPC §4 inheritance) + user-curated
borrow-list. **47 решений** (29 TAKE, 15 DEFER, 1 REFERENCE-only) после
дедупа ~74 raw items + Step-3 line-by-line gap-fill re-pass (§11). См. §11.2
for updated counters.

🇷🇺 **Зачем эта нота существует:** обойти full research → ADR → implementation
цикл для каждой identified-borrow. Большая часть R-N — это либо (а) docs/AGENTS.md
citation (cheap, ~0.5h), либо (б) ~100-300 LOC port из proven source (Aperant /
Kronos / Gortex). ADR-7 + ADR-8 (HookRegistry) — единственные **архитектурные**
блокеры; всё остальное лежит сверху как middleware / prompt / config.

🇷🇺 **Топ-5 «cheap wins» что можно landit немедленно (Wave 0, нет зависимостей):**

1. **R-9** Identity-preserving compaction prompt — 5-line snippet в новый
   `knowledge/prompts/handoff-summarizer.md`; upgrades HANDOFF.md quality.
2. **R-8** Filesystem-canon learning loop (`record_gotcha` + `record_discovery`)
   — ~150 LOC Python port; immediately replaces manual HANDOFF.md edits.
3. **R-26** DPC-derived AGENTS.md citation cluster (4 sub-items) — ~2h
   docs-only; вкатывает minimalism-first discipline empirically.
4. **R-5** DSV post-tool gate — ~100 LOC + YAML schema; cheapest reliability
   gate возможный; нет depends-on.
5. **R-13** Tokens-classifier + buildSuggestions + discover (standalone
   audit blocks) — ~250 LOC; standalone module не требует chunker/index.

🇷🇺 **Топ-3 unblocking-items для Phase M (Wave 1):**

1. **R-1** HookRegistry + 2-tier middleware — **разблокирует** R-2 / R-3 /
   R-4 / R-22 / R-29 (5 downstream items). Самый высокий ROI structural item.
2. **R-18** Per-tier tool-shape registry — ~50 LOC; pairs с ADR-2 routing.
3. **R-20** Bash sandbox upgrade — ADR-6 maturation; pairs с R-4 blocker
   middleware но technically independent.

🇷🇺 **Anti-pattern signals (что НЕ делать) — extracted из 4+ source-нот:**

1. **Cron / background self-modification без external fitness** (DPC ADR-015,
   Kronos R-6) — два независимых проекта построили и удалили.
2. **Write-only subsystem без read-side consumer** (DPC ADR-021) — собирает
   maintenance debt.
3. **Brute-force retry-loop без circuit-breaker** (Aperant 5 reference) —
   `MAX_QA_ITERATIONS=50` работает но дорого; используй R-2 + R-34
   constants как better default.
4. **Prompt-diversity ensembling без verifier** (Correlated R-3) — не даёт
   consistent gains, добавляет cost.
5. **Hardcoded scope estimation в часах** (DPC ADR-005 P18) — bias-prone;
   estimate lines / files only.

🇷🇺 **Empirical anchors для AGENTS.md / ADR rationale (use as direct quotes):**

- DPC ADR-015: 20+ sessions × ~40 evolution proposals = **0 valuable changes**
  после rule-filter → удалили worker + 400 LOC + 7 tools.
- DPC ADR-005 S14: Coder estimated 5-7h для what took **11 min (27-38× error)**.
- Aperant `qa-loop.ts` constants: `MAX_QA_ITERATIONS=50`,
  `RECURRING_ISSUE_THRESHOLD=3` — proven values из production system.
- YT-4 Hacker News upvote experiment: GPT-3.5 Turbo failed unharnessed,
  **succeeded within 6 iterations** with DSV + login middleware harness.
- KAOS `kronos/security/pii.py:1-91`: recursive PII walker preserving
  UUIDs/hashes/tokens — drop-in для FA audit log redaction.

---

## 1. Sources & reader's guide

### 1.1 Source notes (durable, version-controlled)

🇷🇺 Все source-ноты живут в [`knowledge/research/`](../research/) и
обновляются independently. Эта мастер-нота **не заменяет** их — она
индексирует и связывает. Когда нужны глубокие детали по конкретному
паттерну (полный LOC анализ, design rationale, supersession history) —
открывать source-ноту, не эту.

| # | Source note | Compiled | Scope | Items в borrow-list |
|---|-------------|----------|-------|---------------------|
| 1 | [`gortex-aperant-inspiration-2026-05.md`](../research/gortex-aperant-inspiration-2026-05.md) | 2026-05-10 | Gortex audit/hooks + Aperant role-routing + orchestration | 16 (Gortex) + 16 (Aperant) = 32 |
| 2 | [`correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md) | 2026-05-08 | 4 papers + Eval-disjoint + ADR-2/ADR-7 amendments | 9 R-N |
| 3 | [`dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md) | 2026-05-12 | DPC HookRegistry + KG + sleep + ADR citations + soviet-code inheritance | 6 R-N + 4 soviet B-NEW + 24 patterns |
| 4 | [`chat-cross-reference-2026-05.md`](../research/chat-cross-reference-2026-05.md) | 2026-05-09 | Reading-list bootstrap + watchdog | 3 R-N |
| 5 | [`kronos-agent-os-inspiration-2026-05.md`](../research/kronos-agent-os-inspiration-2026-05.md) | 2026-05-13 | KAOS SafeDB + skills + capability gates | 6 R-N |
| 6 | `yt-concepts-for-FA.md` (external — `/home/ubuntu/research/`) | 2026-05-13 | 4 YT summaries: tuning / memory / verification / harnesses | 21 concepts (15 в borrow-list) |
| 7 | `borrow-list+manual+selection+unfiltered.md.md` (user attachment) | 2026-05-13 | User-curated TAKE/DEFER selector across sources 1-6 | 74 raw entries |

### 1.2 How to use this note vs source notes

🇷🇺 **Default reading path** (cold-start, agent landing на repo):

1. HANDOFF.md §60-second bootstrap → AGENTS.md pre-flight checklist.
2. Эта нота §0 Decision Briefing (~37 R-N) — для action surface.
3. Эта нота §5 Execution waves — для prioritization.
4. **При выборе конкретного R-N для landing** → открыть source-ноту по
   `Source(s):` ссылке для глубокого контекста (LOC, code references,
   alternative approaches considered).

🇷🇺 **Mapping R-N → source note §X:** каждый R-N в §0 имеет поле
**Source(s)** с path + §-номером в source-ноте. Это primary navigation
mechanism — не дублируй здесь deep details.

### 1.3 Sort orders (для navigation)

🇷🇺 §0 sorted by FA-axis groups (A..J). Для других sort orders:

- **by-cost** — §3 Master FA-relevance mapping имеет cost column,
  можно sort через grep / table view tooling.
- **by-execution-order** — §5 Execution waves группирует по dependency.
- **by-source** — §1.1 table выше + поле `Source(s)` в каждом R-N.

---

## 2. Pattern groups — narratives & cross-references

🇷🇺 §0 уже содержит full R-N detail. Эта секция даёт **group-level
narrative** для понимания «почему именно эти R-N в одной группе» +
intra-group reading order + ROI per group. Полезна когда уже прочёл §0 и
хочешь общую картину.

### 2.1 Group A — Inner-loop / Hook / Guard middleware (R-1..R-5, 5 items)

🇷🇺 **Связующий концепт:** HookRegistry (R-1) — это **architectural
substrate**, на которое садятся 4 других middleware. Без R-1 остальные
4 — это inline if/elif блоки в loop body, которые scatter rationale по
кодовой базе и затрудняют unit-testing каждого guard'а independently.

🇷🇺 **Reading order within group:**
1. R-1 (HookRegistry skeleton) — read first; design substrate.
2. R-7 (retry-budget invariant) — ADR-7 amendment landит вместе с R-1 ADR-8.
3. R-2 (LoopGuard) — самый простой middleware subclass, good first impl.
4. R-3 (failure classification) — нужно для R-2 + R-4 + R-6.
5. R-4 (pre-tool blocker) — middleware для resolution предсказуемых блокеров.
6. R-5 (DSV post-tool gate) — можно landit **первым** standalone (Wave 0),
   потом интегрировать в R-1 как `AFTER_TOOL_EXEC` middleware.

🇷🇺 **ROI per group:** highest — R-1 разблокирует 5 downstream items;
R-5 standalone Wave 0 + затем integration. Estimated total ~1000 LOC Python
для всех 5; реальный ARC: «agent перестаёт hallucinate success».

### 2.2 Group B — Exploration DAG enrichment (R-6, R-7, 2 items)

🇷🇺 **Связующий концепт:** превратить FA's passive `knowledge/trace/exploration_log.md`
в **active control surface**. R-6 = writer+reader pair (attempt_history.json), R-7 =
config-bounded retry-budget invariant.

🇷🇺 **Reading order:**
1. R-7 ADR-7 amendment первым (docs-only, Wave 0).
2. R-6 reader-prompt (`knowledge/prompts/coder-recovery.md`) — copy from
   Aperant verbatim, adapt paths.
3. R-6 writer side (Python port of `recovery-manager.ts`) — последним;
   blocked-on R-3 failure classification.

🇷🇺 **ROI per group:** medium-high — closes feedback loop between Exploration
DAG entries and downstream Coder retries. Без R-6 reader-prompt — Coder
читает все past attempts в каждом retry (high context cost); С reader-prompt
— Step 0 prompts «if attempt_count >= 2, switch strategy» (cheap).

### 2.3 Group C — Mech-Wiki / Memory enrichment (R-8..R-12, 5 items)

🇷🇺 **Связующий концепт:** filesystem-canon memory с **graceful escalation**
от cheapest (R-8 append-only Markdown) до richest (R-11 bi-temporal KG).
Каждый next item требует maturity от previous.

🇷🇺 **Reading order:**
1. R-8 (`record_gotcha` + `record_discovery`) — Wave 0 entry point.
2. R-9 (compaction prompt fragment) — Wave 0 too; orthogonal.
3. R-10 (insight extractor) — Wave 3; pairs с R-6 attempt_history.
4. R-12 (sleep consolidation + `_meta.json`) — Wave 3-4; depends on R-1.
5. R-11 (bi-temporal KG) — DEFER until current `knowledge/` hits scaling limits.

🇷🇺 **ROI per group:** very high — R-8 alone заменяет manual HANDOFF.md
edits; R-9 boosts HANDOFF.md quality за 5-line edit; R-10/R-11/R-12 дают
diminishing returns по cost вверх. **Не landить R-11/R-12 до R-10 maturity.**

### 2.4 Group D — Audit / hygiene tools (R-13, R-14, R-15, 3 items)

🇷🇺 **Связующий концепт:** subset of Gortex audit subsystem ported as
**standalone modules**, не требующие full audit-subsystem integration.
R-13 (tokens classifier) ценен сам по себе; R-14 (workspace rule) docs-only;
R-15 (full audit Python tool) DEFERRED потому что prompt-version
(`knowledge/prompts/repo-audit-playbook.md`) уже существует.

🇷🇺 **Reading order:**
1. R-14 (workspace rule) — Wave 0 docs-only.
2. R-13 (tokens classifier + buildSuggestions + discover) — Wave 0 impl.
3. R-15 (full audit Python tool) — DEFER unless prompt-workflow станет bottleneck.

🇷🇺 **ROI per group:** medium — R-13 даёт ~250 LOC standalone module
полезный для будущих `fa hygiene` команд; R-14 предотвращает walk-up bugs
заранее.

### 2.5 Group E — Role-routing / prompts (R-16..R-19, 4 items)

🇷🇺 **Связующий концепт:** matures FA's ADR-2 tier-routing с
spec-pipeline (R-16) + QA orchestrator (R-17) + tool-shape registry
(R-18) + Eval-disjoint policy (R-19). R-16 + R-17 — Phase S/M
maturation; R-18 + R-19 — Wave 0/1 cheap landings.

🇷🇺 **Reading order:**
1. R-19 (Eval-role disjoint policy) — Wave 0 ADR-2 amendment.
2. R-18 (per-tier tool-shape registry) — Wave 1 cheap impl.
3. R-16 (multi-stage spec pipeline) — Wave 3 Phase S maturation.
4. R-17 (QA orchestrator agentic) — Wave 3 pairs с R-16.

🇷🇺 **ROI per group:** high cumulative — R-19 protects future ensembling;
R-18 reduces per-tier retry cost; R-16 + R-17 — substantial Phase M scope.

### 2.6 Group F — Capability gates / sandbox (R-20..R-23, 4 items)

🇷🇺 **Связующий концепт:** ADR-6 sandbox maturation. R-20 + R-21 — Layer 1
(deny-by-default + 5-flag opt-in); R-22 (PII redaction) — Layer 2
observability boundary; R-23 (subagent execution rules) — Phase M-prep
documentation.

🇷🇺 **Reading order:**
1. R-21 (5-flag capability opt-in) — Wave 1 cheap config-only.
2. R-23 (sub-agent execution rules) — Wave 0 docs-only.
3. R-20 (bash sandbox upgrade) — Wave 1 ~400 LOC.
4. R-22 (PII redaction walker) — DEFER pairs с R-12 sleep consolidation.

🇷🇺 **ROI per group:** medium — R-21 + R-23 cheap, R-20 medium-cost
sandbox upgrade требует ADR-6 amendment.

### 2.7 Group G — Skills / progressive disclosure (R-24, R-25, 2 items)

🇷🇺 **Связующий концепт:** filesystem-canon skill store (R-24, 3-project
convergence) + pause-file sentinel (R-25, runtime pattern). R-25 не
напрямую skills-related, но share filesystem-sentinel idiom.

🇷🇺 **Reading order:**
1. R-25 (pause-file sentinel) — Wave 1 cheap port.
2. R-24 (filesystem-canon skill store) — Wave 3 Phase M maturity.

🇷🇺 **ROI per group:** high — R-24 unblocks BACKLOG I-9 (convert
`repo-audit-playbook.md` в loadable SKILL).

### 2.8 Group H — AGENTS.md / ADR citations cluster (R-26..R-32, 7 items)

🇷🇺 **Связующий концепт:** 7 lightweight citation rules в AGENTS.md /
ADR-2 / ADR-7. Все ~0.5-1h каждое; batchable в один Wave 0 PR (7 items
= ~5-7h total work). Низкая cost / высокая ROI потому что rules
**предотвращают** future bad designs.

🇷🇺 **Reading order:** все в Wave 0; landit в одном PR или batch'нуто
по 2-3 в day:
1. R-26 (DPC-derived cluster: 4 sub-items) — ~2h.
2. R-27 (Correlated-derived: 2 sub-items) — ~1h.
3. R-28 (intra-role T=1.0) — ~0.5h.
4. R-29 (LLM-using hooks ≠ acting-role) — ~0.2h.
5. R-30 (max_iterations cap rationale) — ~0.2h.
6. R-31 (Phase M runner shape: Komissar Naikan + heartbeat) — Wave 3, отдельно.
7. R-32 (anti-pattern catalog living document) — Wave 3, отдельно.

🇷🇺 **ROI per group:** very high per-hour-spent — R-26/R-27/R-28/R-29/R-30
вместе ~5h work, blocks 6+ future bad-design proposals empirically anchored.

### 2.9 Group I — GitHub workflow (R-33..R-37, 5 items, mostly DEFER)

🇷🇺 **Связующий концепт:** PR review (R-33) + QA loop constants (R-34) +
triage (R-35) + merge (R-36) + CI (R-37). Все будут полезны в Phase M+
когда FA получит GitHub-workflow capabilities. R-34 — **only TAKE-now**
item (constants standalone).

🇷🇺 **Reading order:**
1. R-34 (QA loop constants only) — Wave 2 pairs с R-1/R-2.
2. Остальные (R-33 / R-35 / R-36 / R-37) — DEFER pending Phase M+
   GitHub workflow scope.

🇷🇺 **ROI per group:** low-now / high-later — DEFER bundle, не
блокировать Phase M на этом.

### 2.10 Group J — Deferred / out-of-immediate-scope (R-38..R-40)

🇷🇺 Three items deferred until specific milestones land:

- R-38 (multi-model ensembling) — blocked на UC5d eval-harness.
- R-39 (verifier-based selection) — blocked на UC5 + R-38.
- R-40 (worker-thread isolation) — blocked на corruption-risk
  materializing.

🇷🇺 **ROI:** N/A pre-block; tracked in BACKLOG для future re-eval.

---


### Group A — Inner-loop / Hook / Guard middleware

#### R-1 — HookRegistry + 2-tier middleware (`GuardMiddleware` + `ObserverMiddleware`)

- **What:** Per-process middleware chain заменяет inline if/elif guard sprawl во внутреннем цикле. `GuardMiddleware` (errors propagate, может остановить loop) + `ObserverMiddleware` (observation-only, errors swallowed at DEBUG). 5 lifecycle-точек: `BEFORE_LLM_CALL / AFTER_LLM_CALL / BEFORE_TOOL_EXEC / AFTER_TOOL_EXEC / BETWEEN_ROUNDS`. Это **8-project convergence** (DPC + 4 cited in DPC ADR-007 + Gortex + KAOS + FA's own ADR-7 §5).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (runtime architecture)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — прямо имплементирует ADR-7 §5 Lifecycle Guards + R-9 `stop_message` контракт; разблокирует R-2 / R-3 / R-4 / R-5
- **Cost:** medium (3-5h ADR-8 skeleton + base contracts; ~500 LOC Python)
- **Verdict:** TAKE (Wave 1 — unblocking)
- **Alternative-if-rejected:** inline if/elif блоки в loop body (current ADR-7 §5 draft)
- **Concrete first step:** Прочитать DPC `dpc_agent/hooks.py` (207 LOC) + `dpc_agent/guards.py` (222 LOC) + Gortex `internal/hooks/dispatch.go` (38 LOC); написать ADR-8 «B-NEW-5: HookRegistry» со ссылками на оба источника.
- **Source(s):** DPC `dpc-messenger-inspiration-2026-05.md` §0 R-1 (primary); Gortex `gortex-aperant-inspiration-2026-05.md` Addendum I (convergence-only).

#### R-2 — Loop/circular-fix guard middleware (`LoopGuard`)

- **What:** Three-detector circuit breaker как `GuardMiddleware` поверх R-1: (1) identical tool-call повторы → `WARN`; (2) near-identical action signatures within N turns → `CRITICAL`; (3) thrash на одном файле/path → `CIRCUIT_BREAKER`. Дополнительно: `simpleHash(error)` × `CIRCULAR_FIX_THRESHOLD=3` для повторных fix-attempts (из Aperant 8 как auxiliary). На `CIRCUIT_BREAKER` → write NOTE в trace и force task abort.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: YES (escalation NOTE становится контекстом для следующего turn-а — как HANDOFF.md, но runtime)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Phase M inner-loop нуждается в «Coder fails loudly» механизме более гранулярном чем ADR-2 «retry-once-then-stop»)
- **Cost:** cheap (~99 LOC Kronos + ~30 LOC simpleHash из Aperant; всего ~130 LOC)
- **Verdict:** TAKE (Wave 2 — blocked-on R-1)
- **Alternative-if-rejected:** rely на ADR-2 §Consequences «Coder fails loudly» + user-driven retry без automatic circuit-breaker
- **Concrete first step:** Прочитать Kronos `kronos/security/loop_detector.py` (99 LOC) full; map 3 detectors на ADR-7 §7 trace fields; добавить `simpleHash`-based attempt counter из Aperant `recovery-manager.ts:120-145`.
- **Source(s):** Kronos `kronos-agent-os-inspiration-2026-05.md` §0 R-3 (primary 3-detector shape); Aperant `gortex-aperant-inspiration-2026-05.md` Part 2 item 8 (`simpleHash` auxiliary).

#### R-3 — Failure classification enum + RecoveryAction dispatcher

- **What:** Все failure-узлы в Exploration DAG получают категорию из tripartite-классификатора: `invalid_arguments / unexpected_environments / provider_errors` (YT-1 #1) + Aperant's расширение: `broken_build / verification_failed / circular_fix / context_exhausted / rate_limited / auth_failure / unknown` (keyword-matching на lowercased error text). На выходе `RecoveryAction { action: rollback|retry|skip|escalate, target, reason }`. Каждая категория → детерминированная retry-стратегия, не «попробуем то же самое снова».
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: YES (category surfaced в HANDOFF.md / hot.md как «session ended in `provider_errors`» — следующая сессия знает контекст)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Exploration DAG превращается из passive log в active control surface)
- **Cost:** medium (~150 LOC классификатор + ~80 LOC `RecoveryAction` dispatcher = ~230 LOC)
- **Verdict:** TAKE (Wave 2 — pairs с R-6)
- **Alternative-if-rejected:** ловить все failures одним «retry-once» правилом без category
- **Concrete first step:** Прочитать Aperant `apps/desktop/src/main/ai/orchestration/recovery-manager.ts` (456 LOC, классификатор на строках 200-340); подмешать tripartite-категории YT-1 как top-level rollup перед Aperant-specific.
- **Source(s):** YT-1 (см. `yt-concepts-for-FA.md` #1 — empirical citation); Aperant `gortex-aperant-inspiration-2026-05.md` Part 2 item 8 / Addendum (реф-имплементация).

#### R-4 — Pre-tool blocker middleware injection

- **What:** Для предсказуемых deterministic-блокеров (login-wall, rate-limit, expired token, FS-permission, lockfile conflict, git-stash dirty, browser-auth) — `pre_tool` middleware в HookRegistry детектит блокер по URL/error-pattern, разрешает в коде (`harness.injectCredentials(env.SECRETS); submitForm(); push synthetic system message «Harness logged in. Proceed.»`), LLM никогда не видит failure. Обобщает YT-4 `login_handler` до **классa middleware** по 6 категориям блокеров.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: PARTIAL (synthetic message убирает шум из ошибки, но не добавляет контекст)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (offload deterministic operations from LLM к harness — прямо minimalism-first ось)
- **Cost:** medium (~120 LOC post-R-1: 3 первых middleware subclasses по 30-50 LOC каждый — rate-limit, auth-expired, lockfile)
- **Verdict:** TAKE (Wave 2 — blocked-on R-1)
- **Alternative-if-rejected:** LLM сам обрабатывает каждый блокер; повышенная стоимость токенов + риск hallucinated-success в стиле YT-4 эксперимента
- **Concrete first step:** Реализовать `rate_limit_middleware` (Aperant `pause-handler.ts:30-80` интервалы 30s) первым; это единственный блокер с явными tunable constants из реальной prod-системы.
- **Source(s):** YT-4 (см. `yt-concepts-for-FA.md` #20 — primary pattern); Aperant `pause-handler.ts` (рабочий рантайм для rate-limit subclass).

#### R-5 — Deterministic State Verification (DSV) post-tool gate

- **What:** Post-action гейт: парсит tool-execution event trace, проверяет required-event signatures, **override LLM-claimed success** при mismatch. Никаких LLM-вызовов внутри (cheapest reliability gate possible). YAML-схема per tool с полями `target_action / required_trace_events / failure_conditions / override_action`. Дополняет R-2 (loop-detection runtime) — DSV ловит «LLM наврал что успех», R-2 ловит «LLM застрял в цикле».
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: YES (forced failure state → next turn видит реальную ошибку, не hallucinated success)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (детерминированный кузен #2 LLM-verifier; стэкируются — DSV сначала, LLM-verifier потом для semantic judgments)
- **Cost:** cheap (~100 LOC: `verify_action.py` + 4-5 YAML контрактов в `verifiers/*.yaml`)
- **Verdict:** TAKE (Wave 0 — может landed первым, нет зависимостей; pairs с R-1 после)
- **Alternative-if-rejected:** доверять LLM-claimed success как сегодня; commit-time hooks ловят только некоторые failure-классы
- **Concrete first step:** Создать `verifiers/edit_file.yaml` с `failure_conditions: [file_unchanged_after_edit, sandbox_violation]`; написать ~50 LOC parser в `src/fa/verifier/verify_action.py`; интегрировать в ADR-7 inner-loop как mandatory post-tool step.
- **Source(s):** YT-4 (см. `yt-concepts-for-FA.md` #18 — primary).

---

### Group B — Exploration DAG enrichment

#### R-6 — `attempt_history.json` writer + reader prompt pair

- **What:** Парный writer + reader для per-subtask retry-history. **Writer (Aperant `recovery-manager.ts`):** записывает attempt в `<specDir>/memory/attempt_history.json` с timestamp + error-hash + outcome; sliding window 2h + cap 50 attempts. **Reader (Aperant `coder_recovery.md` prompt):** Step 0 читает history; если `attempt_count >= 1` — `⚠️⚠️⚠️ THIS SUBTASK HAS BEEN ATTEMPTED BEFORE!` + force articulate different approach; `>= 2` — `HIGH RISK` + suggest «completely different library / pattern / check feasibility». Прямо ложится на FA Exploration DAG: writer = `knowledge/trace/exploration_log.md` ровный append; reader = новый prompt вызываемый перед каждым retry.
- **Project-axis fit:**
  - (A) reduces session-start noise: PARTIAL (history замёрзает старые попытки, но не удаляет — нужно сделать)
  - (B) helps LLM find context when needed: YES (reader-prompt **активно** surfaces dead-ends перед retry)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Exploration DAG из passive log → active control surface)
- **Cost:** cheap-medium (writer ~50 LOC + reader prompt ~100 LOC + sliding-window logic ~30 LOC = ~180 LOC + prompt)
- **Verdict:** TAKE (Wave 2 — pairs с R-3; reader prompt можно landed раньше как docs-only)
- **Alternative-if-rejected:** только passive append в `exploration_log.md` без active reader-prompt; agent повторяет dead-ends в следующих сессиях
- **Concrete first step:** Скопировать `apps/desktop/prompts/coder_recovery.md` (290 LOC) → `knowledge/prompts/coder-recovery.md` с адаптацией: `<specDir>/memory/attempt_history.json` → `knowledge/trace/attempt_history.json`; затем portировать writer side в Python.
- **Source(s):** Aperant items 8 + 13 в `gortex-aperant-inspiration-2026-05.md` Part 2 + Addendum.

#### R-7 — Retry-budget invariant + intra-role retry T=1.0

- **What:** Два инварианта для ADR-7 hook design: (1) **Retry budget MUST be config-bounded** — каждый retry-loop (Planner, Coder, Eval) имеет hard cap из `config.yaml`, не magic-number в коде. Empirical anchor: YT-4 GPT-3.5 Turbo успешно завершил Hacker News upvote within `max_iterations=6` когда harness был корректен. (2) **Intra-role retry temperature default `T=1.0`** (P-3 §4.1 finding) — повторяющий retry с той же T выбирает то же гипотезу-кандидат; T=1.0 forces diversity внутри одной роли. Оба правила — текст в ADR-7, ноль кода, но крайне важная дисциплина для Phase M HookRegistry guards.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (ADR rule, не runtime)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Phase M HookRegistry guards получают чёткие конфигурируемые invariants)
- **Cost:** cheap (~0.5h ADR-7 §5 edit + ~0.5h ADR-2 amendment приложить T=1.0; всего ~1h)
- **Verdict:** TAKE (Wave 0 — docs-only)
- **Alternative-if-rejected:** разработчик landит ADR-8 HookRegistry без явного retry-cap → magic numbers в guard коде → нет audit trail
- **Concrete first step:** Открыть `knowledge/adr/ADR-7-inner-loop-tool-registry.md` §5; добавить параграф «Retry budgets per guard MUST come from config, not constants; max_iterations cap default = 6 (YT-4 empirical anchor)». Аналогично ADR-2 §Lifecycle hooks для T=1.0.
- **Source(s):** Correlated R-7 + R-8 в `correlated-llm-errors-and-ensembling-2026-05.md` §6; YT-4 (см. `yt-concepts-for-FA.md` #21 — empirical citation).

---

### Group C — Mech-Wiki / Memory enrichment

#### R-8 — Filesystem-canon learning loop (`record_gotcha` + `record_discovery`)

- **What:** Две минимальные tool-функции которые записывают в `knowledge/trace/gotchas.md` (append-only, timestamped sections) и `knowledge/trace/codebase_map.json` (atomic rename per-key upsert). Это **«FA Mechanical Wiki, miniaturized»** — drop-in patten. **3-project convergence:** Aperant items 1 + 2 (реф-имплементация TS); YT-3 #6 (empirical citation для Mavis runtime extraction); Kronos `audit.py` `_meta.json` (FS-canon хранение). Идиома atomic-rename (`.tmp` + `os.rename`) обязательна — несколько процессов могут писать в parallel.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (gotchas preloaded в hot.md; `~/.fa/cache/codebase_map.json` грузит chunker pointers за 1 файл)
  - (B) helps LLM find context when needed: YES (codebase_map.json = pointer index «не перечитывай `src/fa/chunker/`»)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (filesystem-canon learning — прямо FA's stated design)
- **Cost:** cheap (1-2h — port two TS tools в Python; ~150 LOC всего)
- **Verdict:** TAKE (Wave 0 — нет зависимостей)
- **Alternative-if-rejected:** оставить manual HANDOFF.md edits; agent не учится между сессиями
- **Concrete first step:** Прочитать Aperant `apps/desktop/src/main/ai/tools/auto-claude/record-gotcha.ts` (78 LOC) + `record-discovery.ts` (90 LOC); создать `src/fa/tools/record_gotcha.py` и `record_discovery.py` с тем же контрактом.
- **Source(s):** Aperant items 1 + 2 в `gortex-aperant-inspiration-2026-05.md` Part 2; YT-3 (см. `yt-concepts-for-FA.md` #6 — convergence).

#### R-9 — Identity-preserving compaction prompt fragment

- **What:** 5-строчный system-prompt fragment для любых session-handoff summary tasks: `CRITICAL — preserve verbatim (do NOT paraphrase, do NOT omit): UUIDs, hashes, tokens, IDs · URLs, hostnames, IPs, file paths · batch progress · decision status + reason · TODOs · names, dates, sums · API keys masked`. Плюс 5-block structure mandate (`Context / Decisions / Progress / Pending / Data`). Сохраняет identifiers verbatim → следующая сессия может их грепнуть → нет re-derivation cost. Прямо upgrade-ит current FA HANDOFF.md freeform shape.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (better handoff = fewer re-asks at session start)
  - (B) helps LLM find context when needed: YES (UUID-style identifiers preserved → grep-friendly)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (HANDOFF.md quality — closest FA-equivalent к LLM compaction)
- **Cost:** cheap (~5-line prompt fragment + 1-paragraph addition к HANDOFF.md «When to update»; ~15 LOC total)
- **Verdict:** TAKE (Wave 0 — нет зависимостей, самый дешёвый item в noте)
- **Alternative-if-rejected:** continue с current HANDOFF.md freeform structure
- **Concrete first step:** Verbatim copy fragment в `knowledge/prompts/handoff-summarizer.md` (new file); update `HANDOFF.md` §When to update this file с cross-reference.
- **Source(s):** Kronos `kronos/memory/compaction.py:22-43` в `kronos-agent-os-inspiration-2026-05.md` §0 R-5.

#### R-10 — Post-session insight extractor

- **What:** Структурированный post-session pass: `generateText` (no tools) с Zod-схемой (`ExtractedInsightsOutputSchema`) на inputs: git diff (capped at 15 000 chars), subtask description, attempt history (last 3 entries), commit messages, success flag. Output: `file_insights[]`, `patterns_discovered[]`, `gotchas_discovered[]`, `approach_outcome{success, why_it_worked, why_it_failed, alternatives_tried}`, `recommendations[]`. Использует cheap tier (haiku-equivalent) потому что high-volume. **Это feeder loop для Mech-Wiki:** R-8 пишет gotchas mid-task, этот pass mines diff + history после session-а для structured learnings которые in-flight LLM пропустил.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (consolidated insights → next session's HANDOFF.md)
  - (B) helps LLM find context when needed: YES (structured patterns_discovered field → grep-friendly index)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (closes Exploration DAG → distilled skill loop)
- **Cost:** medium (~308 LOC TS port + ~178 LOC prompt = ~250 LOC Python + ~150 prompt-line)
- **Verdict:** TAKE (Wave 3 — pairs с R-6 attempt_history; нужна Phase M маturity)
- **Alternative-if-rejected:** только R-8 mid-task `record_gotcha`; пропустим cross-session pattern extraction
- **Concrete first step:** Прочитать Aperant `apps/desktop/src/main/ai/runners/insight-extractor.ts` (308 LOC) + `apps/desktop/prompts/insight_extractor.md` (178 LOC); особое внимание 15 000-char diff cap (key empirical detail — bigger diffs degrade extraction).
- **Source(s):** Aperant item 11 в `gortex-aperant-inspiration-2026-05.md` Part 2 + Addendum.

#### R-11 — Bi-temporal Knowledge Graph + `GraphBackend` ABC

- **What:** Pluggable KG с 5 NodeType + 9 EdgeType, `t_created`/`t_invalidated` поля для soft-delete, `ALWAYS_EXEMPT = {DECISION, SESSION_ARCHIVE}` (некоторые типы вечны). SQLite default backend. GLiNER NER для entity extraction. **4-project convergence** (DPC + Enox + soviet-code + KAOS) на 7-field typed-assertion контракте — DPC добавляет bi-temporal как уникальную фичу. Schema verbatim в DPC `dpc_agent/knowledge_graph.py`.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (KG = pre-computed retrieval, доставляет нужный subgraph за 1 query)
  - (B) helps LLM find context when needed: YES (graph queries point к source)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (future knowledge layer foundation)
- **Cost:** expensive (6-8h ADR + schema + skeleton; ~700 LOC across `graph_backend.py` + `sqlite_graph_backend.py`)
- **Verdict:** DEFER (until current `knowledge/` layer hits scaling limits — пока FTS5 + chunker pointers достаточны)
- **Alternative-if-rejected:** filesystem-canon Markdown only (current FA approach); accept manual cross-linking
- **Concrete first step (if TAKE later):** Прочитать DPC `dpc_agent/knowledge_graph.py` end-to-end; написать KG ADR копирующий schema verbatim.
- **Source(s):** DPC `dpc-messenger-inspiration-2026-05.md` §0 R-2 + §2 Pattern 9.

#### R-12 — Sleep consolidation + `_meta.json` access registry

- **What:** Inter-session memory через user-triggered (не cron!) morning brief над session archives. N+1 LLM calls, `_meta.json` sidecar per knowledge-file (read counts, embeddings cache, stale flags). DPC явно отверг cron после evolution disaster (ADR-015). **3-project convergence** (DPC user-trigger + soviet-code gated-cron + FA HANDOFF.md manual): 2 из 3 vote за human-trigger. `_meta.json` precursor (без brief) можно landed раньше — это просто sidecar per file.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (morning brief = pre-loaded context for next session)
  - (B) helps LLM find context when needed: YES (`_meta.json` = per-file access registry)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (sleep consolidation + access registry; pairs с R-10 insight extractor)
- **Cost:** medium (4-6h ADR + minimal pipeline; ~400 LOC)
- **Verdict:** DEFER (depends on R-1 HookRegistry + Phase M runner maturity; `_meta.json` precursor можно landed раньше как 2-3h side task)
- **Alternative-if-rejected:** manual HANDOFF.md updates only (current FA approach)
- **Concrete first step (if TAKE later):** Имплементировать `_meta.json` sidecar pattern первым (precursor, 2-3h) перед full sleep-pipeline.
- **Source(s):** DPC `dpc-messenger-inspiration-2026-05.md` §0 R-3 + §2 Patterns 7 + 12.

---

### Group D — Audit / hygiene tools

#### R-13 — Tokens-classifier + buildSuggestions output formatter + probe-path discovery

- **What:** Три бомбы из Gortex audit subsystem, каждая standalone-полезна даже если full audit-subsystem (R-15) не landed: (1) **`tokens.go` (156 LOC)** — conservative classifier для backticked tokens с правилами `requires uppercase OR :: qualifier OR explicit () suffix` чтобы не false-positive на tool names типа `search_symbols` или option keys типа `older_than`. Hard skip list для shell verbs (`grep`, `ls`, `git`). (2) **`buildSuggestions()` (15 LOC)** — turns raw audit report в 1-3 human-readable hints (`"Remove stale symbol references"`, `"Config files are bloated (score >=60)"`, `"Config looks clean."`). (3) **`discover.go` (83 LOC)** — `DefaultConfigPaths()` canonical probe list (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, …).
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (audit forces minimalism; «config looks clean» = ноль шума при clean state)
  - (B) helps LLM find context when needed: YES (dead-ref detection keeps refs valid → grep / cross-ref не битый)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Mechanical Wiki hygiene KPI становится concrete)
- **Cost:** medium (~250 LOC Python: ~150 для tokens classifier + ~30 для buildSuggestions output + ~80 для discover.go port = standalone `src/fa/hygiene/` module)
- **Verdict:** TAKE (Wave 0 — нет зависимостей; standalone module не требует chunker/index integration)
- **Alternative-if-rejected:** continue manual review; rely на rule #3 file-length caps в AGENTS.md PR Checklist
- **Concrete first step:** Прочитать Gortex `internal/audit/tokens.go` (156 LOC) + `internal/audit/audit.go:185-199` (buildSuggestions); портировать tokens classifier первым (самый bound) → затем discover.go → затем output formatter.
- **Source(s):** Gortex items B + C + K в `gortex-aperant-inspiration-2026-05.md` Part 1 + Addendum.

#### R-14 — Workspace resolution rule (no walk-up; explicit marker)

- **What:** Two-mode workspace resolution: marker файл (`.gortex/workspace.toml`) at cwd → workspace mode (members = immediate children с `.gortex/`), or `.gortex/` directly at cwd → single-project mode. **No walk-up** — entry-point discovery explicit by design. Workspace isolation enforced (members must live strictly inside resolved root; no cross-workspace bridging). Это **ADR-equivalent rule** даже если FA сегодня single-project — закрывает scope-creep bug когда какой-то tool walks up из nested dir и находит чужой `AGENTS.md`.
- **Project-axis fit:**
  - (A) reduces session-start noise: PARTIAL (explicit marker file = ноль ambiguity при cold-start)
  - (B) helps LLM find context when needed: YES (deterministic «где FA root» избегает confused cross-project context)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (ADR fix-rule; готово к monorepo expansion)
- **Cost:** cheap (~50 LOC + ADR-9 update; формальное правило в AGENTS.md)
- **Verdict:** TAKE (Wave 0 — docs-first; impl при следующей tool которая ищет FA root)
- **Alternative-if-rejected:** `find . -name AGENTS.md` walk-up; risk cross-workspace contamination когда FA включает submodules
- **Concrete first step:** Прочитать Gortex `internal/workspace/workspace.go` (331 LOC); добавить параграф в AGENTS.md §«Working in This Repo» с no-walk-up правилом + marker file (`.fa/workspace.toml` или просто `knowledge/llms.txt` как existing marker).
- **Source(s):** Gortex item O в `gortex-aperant-inspiration-2026-05.md` Addendum.

#### R-15 — Full bloat/staleness audit subsystem (Python tool)

- **What:** Lift Gortex's 0-100 bloat scoring (lines, long lines, duplicate bullets, nesting depth, code blocks; soft cap 600, hard cap 1500) + stale-reference detection (extract backticked tokens, graph-validate symbols, stat-check paths) в `fa audit` CLI command. Outputs `StaleRef[] / DeadPath[] / BloatMetrics / Suggestions[]`.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (forces minimalism)
  - (B) helps LLM find context when needed: YES (dead-ref detection keeps refs valid)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (FA уже имеет audit prompt-workflow в `knowledge/prompts/repo-audit-playbook.md` — Python tool вторичная польза)
- **Cost:** medium (3-5h skeleton — port heuristics + integrate с `knowledge/llms.txt` index; ~500 LOC)
- **Verdict:** DEFER (есть prompt-alternative; Python tool пригодится только когда prompt-workflow станет bottleneck)
- **Alternative-if-rejected:** continue с existing `knowledge/prompts/repo-audit-playbook.md` prompt-driven audit
- **Concrete first step (if TAKE later):** Прочитать Gortex `internal/audit/bloat.go` (158 LOC) + `internal/audit/audit.go` (201 LOC); port heuristic в Python в `src/fa/audit/`.
- **Source(s):** Gortex item A + R-1 в `gortex-aperant-inspiration-2026-05.md` §0 + Part 1 (note: user's borrow-list марк «we already got audit prompt-workflow» → DEFER здесь).

---

### Group E — Role-routing / prompts

#### R-16 — Multi-stage spec creation pipeline с mandatory write-tool gate

- **What:** 5-stage spec pipeline (вместо single-prompt spec writer): `complexity_assessor → spec_quick OR (spec_gatherer → spec_researcher → spec_writer → spec_critic)`. Complexity assessor читает `requirements.json + project_index.json` → classifies task SIMPLE/STANDARD/COMPLEX → routes accordingly. **Каждый prompt имеет explicit contract:** `MANDATORY: You MUST call the Write tool. Describing the assessment in your text response does NOT count — the orchestrator validates that the file exists on disk.` Это **canonical filesystem-canonical validation** правило — соответствует soviet B-NEW-2 «mandatory Inspection phase» (2-project convergence). Подходит к FA Phase S.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (per-task pipeline, не bootstrap)
  - (B) helps LLM find context when needed: YES (complexity-routing → правильная глубина spec'a без overhead)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (filesystem-canon validation = FA core philosophy; spec pipeline = Phase S maturation)
- **Cost:** medium (2-3h — extract + adapt 5 prompts; full prompt-library port ~700 LOC markdown)
- **Verdict:** TAKE (Wave 3 — Phase S/M maturation; selective adoption — complexity_assessor + spec_quick + spec_writer)
- **Alternative-if-rejected:** continue с ad-hoc prompts в `knowledge/prompts/`; нет complexity routing
- **Concrete first step:** Прочитать `apps/desktop/prompts/complexity_assessor.md` + `spec_quick.md` (SIMPLE branch); adapt к FA `knowledge/prompts/` shape; зафиксировать «Write or it didn't happen» правило в AGENTS.md как universal pattern.
- **Source(s):** Aperant item 15 в `gortex-aperant-inspiration-2026-05.md` Part 2; soviet B-NEW-2 в DPC `dpc-messenger-inspiration-2026-05.md` §4.

#### R-17 — QA orchestrator agentic + filesystem-sentinel human override

- **What:** Agentic QA loop (вместо процедурной brute-force 50-iteration версии): LLM reasons о each review cycle и decides what to fix / accept / escalate. Использует `SpawnSubagent` для delegate к `qa_reviewer` (с browser/test tools) и `qa_fixer` (полный write access). Pre-flight reads `implementation_plan.json`, verifies все subtasks completed; reads `spec.md`; checks `QA_FIX_REQUEST.md` — **human feedback takes priority** (explicit override path). Это **filesystem-sentinel** pattern: human может inject priority feedback через файл на disk, без modify tool surface.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (QA-specific runtime)
  - (B) helps LLM find context when needed: PARTIAL (agentic reasoning surfaces реал failures)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (role-routing matures; human-in-the-loop через FS-sentinel — FA-friendly idiom)
- **Cost:** medium (~200 LOC orchestrator + ~150 LOC prompt)
- **Verdict:** TAKE (Wave 3 — pairs с R-16; нужна Phase M maturity)
- **Alternative-if-rejected:** procedural QA pipeline (Aperant item 5 — `MAX_QA_ITERATIONS=50` brute force) — proven работает но дороже токенов
- **Concrete first step:** Прочитать `apps/desktop/prompts/qa_orchestrator_agentic.md`; design FA equivalent с `QA_FIX_REQUEST.md` sentinel path в `knowledge/trace/`.
- **Source(s):** Aperant item 16 в `gortex-aperant-inspiration-2026-05.md` Part 2.

#### R-18 — Per-tier tool-shape registry + role-switch handoff rule

- **What:** Два связанных правила для multi-tier ADR-2 routing: (1) **per-tier tool-shape registry** — patch-based для OpenAI vs string-replace для Anthropic vs whatever для DeepSeek/Kimi/Qwen. Принцип «tool shape follows the model's training distribution». Маленький registry (`src/fa/tools/per_tier_shapes.yaml`), не full provider translation. (2) **Role-switch handoff warning** — при передаче Planner→Coder инжектится one-liner «ignore Planner's tool format, use yours». Cheap, defensible, никаких структурных изменений.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (per-call adjustment)
  - (B) helps LLM find context when needed: PARTIAL (правильный tool shape = меньше retries)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (ADR-2 tier-routing получает явный tool-shape level)
- **Cost:** cheap (~50 LOC registry + 1 line в каждом role prompt)
- **Verdict:** TAKE (Wave 1 — independent of HookRegistry)
- **Alternative-if-rejected:** single tool-shape для всех tiers (works но потенциально 5-15% degradation на cross-family models)
- **Concrete first step:** Создать `knowledge/prompts/tool-shapes.yaml` с 3-4 entries (anthropic / openai / qwen-family / deepseek-family); добавить 1-line в каждый role-prompt «Use the tool shape for your tier; ignore other tiers».
- **Source(s):** YT-1 (см. `yt-concepts-for-FA.md` #7 + #8 — primary).

#### R-19 — Eval-role provider/family disjointness + regex slug extraction

- **What:** Два связанных правила для ADR-2: (1) **policy** — Eval-role MUST использовать provider+family disjoint от Planner и Coder. Empirical evidence: paper показал correlated errors при ensembling same-family models. User confirms 95% workload на Chinese OSS LLMs (qwen / kimi / glm / deepseek / mimo) от **разных лабораторий с разной архитектурой** → naturally disjoint. (2) **implementation** — `(c) Inferred from model-slug pattern: regex-based extraction` (`glm-*` → `glm`, `qwen*` → `qwen`, `claude-*` → `claude`). Cheaper than explicit provider whitelist, risky для less-canonical slugs но работает для current FA tier picks.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (ADR rule)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (correlated-LLM-errors paper R-1 amends ADR-2 с empirical grounding)
- **Cost:** cheap (~0.5h ADR-2 amendment + ~30 LOC regex slug extractor)
- **Verdict:** TAKE (Wave 0 — docs + cheap impl)
- **Alternative-if-rejected:** оставить ADR-2 без disjointness rule; ensemble может dégrade при добавлении future Eval LLM
- **Concrete first step:** Открыть `knowledge/adr/ADR-2-llm-tiering.md`; добавить §Amendment с правилом + примером regex extraction. Включить пример: «Eval=qwen2.5-coder-32b, Planner=glm-4.5-air, Coder=deepseek-v3 — all different families».
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §0 R-1 + §6 R-1 + Open Q answers (c).

---

### Group F — Capability gates / sandbox

#### R-20 — Bash sandbox upgrade (denylist + per-command validators + path-containment + pattern classifier)

- **What:** Hybrid bash security: **denylist** (allow-by-default с per-command validators для `rm`, `chmod`, `git`, `pkill`, `psql`) + **path-containment** (resolves symlinks, lowercases on Windows, blocks `..` traversal) + **pattern classifier** (pre-classifies bash в `read-only / git-write / package-manager-install / dangerous` категории, no-LLM zero-latency). 3 источника — Aperant `bash-validator.ts` (300 LOC) + `path-containment.ts` (147 LOC) для validators + path; Gortex `bash_classify.go` (266 LOC) для pattern classifier. ADR-6 sandbox upgrades от path-only-deny до full bash gate.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (ADR-6 sandbox maturation; pairs c R-4 blocker middleware)
- **Cost:** medium (~400 LOC Python: ~200 validators + ~80 path-containment + ~100 pattern classifier + ~20 wiring)
- **Verdict:** TAKE (Wave 1 — pairs с R-1 но technically independent)
- **Alternative-if-rejected:** ADR-6 path-only sandbox; bash command вылетают через `subprocess.run` без validation
- **Concrete first step:** Прочитать Aperant `apps/desktop/src/main/ai/security/bash-validator.ts` (300 LOC) + `path-containment.ts` (147 LOC); портировать в `src/fa/sandbox/bash_gate.py`; затем добавить Gortex pattern classifier как fast pre-pass.
- **Source(s):** Aperant item 6 в `gortex-aperant-inspiration-2026-05.md` Part 2; Gortex item M в same note Addendum.

#### R-21 — 5-flag capability opt-in model + declarative tool whitelist

- **What:** Two-layer capability model. **Layer 1: 5-flag opt-in** (Kronos `config.py:62-69`): `ENABLE_DYNAMIC_TOOLS / REQUIRE_DYNAMIC_TOOL_SANDBOX / ENABLE_MCP_GATEWAY_MANAGEMENT / ENABLE_DYNAMIC_MCP_SERVERS / ENABLE_SERVER_OPS` — все default `False`. Maps 1:1 к FA's «sandbox is deny-by-default» stance. **Layer 2: declarative tool whitelist** (soviet B-NEW-1): `allowed_tools` + `extra_dirs` в YAML config → CLI flags `--allowedTools` + `--add-dir`. Принципиальное правило: capability включается через config файл (audit-able), не runtime decision.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime config)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (deny-by-default — FA core принцип)
- **Cost:** cheap (~50 LOC config parser + ADR-6 amendment с 5-flag list; ~2-4h)
- **Verdict:** TAKE (Wave 1 — independent unblocking)
- **Alternative-if-rejected:** hardcoded capability list в коде; нет audit trail кто что включил когда
- **Concrete first step:** Прочитать Kronos `kronos/config.py:62-69`; добавить в FA `src/fa/config.py` 5 boolean flags; зафиксировать в ADR-6 §Capability gates.
- **Source(s):** Kronos `kronos-agent-os-inspiration-2026-05.md` TL;DR item 8 + sandbox.py; soviet B-NEW-1 в DPC `dpc-messenger-inspiration-2026-05.md` §4.

#### R-22 — PII redaction recursive walker

- **What:** Recursive Python walker `mask_pii_object()` (Kronos `pii.py`, 91 LOC) который обходит nested dicts/lists и маскирует API keys, emails, secrets но **сохраняет** UUIDs, hashes, tokens (нужны для grep / cross-ref). Применяется на observability boundary (audit log write), не в user-facing response. Pairs с R-12 sleep consolidation — make audit log shareable cross-session без leaking secrets.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (post-write only)
  - (B) helps LLM find context when needed: PARTIAL (redacted log безопасно загружать в new session)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (ADR-7 §7 `events.jsonl` уже существует но без redaction)
- **Cost:** cheap (~91 LOC walker + audit-write hook integration; ~150 LOC total)
- **Verdict:** DEFER (relevant когда audit log начинает шарится cross-session; Wave 2-3)
- **Alternative-if-rejected:** continue с raw `events.jsonl` без redaction; не share-able cross-session
- **Concrete first step (if TAKE later):** Прочитать Kronos `kronos/security/pii.py` (91 LOC) — особо `mask_pii_object()` recursive walker.
- **Source(s):** Kronos `kronos-agent-os-inspiration-2026-05.md` §0 R-2 (part 2).

#### R-23 — Sub-agent execution rules (`generateText` not stream + remove spawn-tool)

- **What:** Два non-obvious correctness fixes для sub-agent orchestration: (1) **Sub-agents используют `generateText`, не `streamText`** — потому что output flows back к orchestrator's context, не к UI. Streaming здесь бесполезен и стоит дороже из-за overhead. (2) **Sub-agent tool set MUST exclude `SpawnSubagent` tool** — иначе recursion. Cap `SUBAGENT_MAX_STEPS = 100`. Применимо немедленно когда FA получит sub-agent dispatch (BACKLOG I-2 «Agent + sub-agents for context-load reduction»).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (BACKLOG I-2 prep — правило в ADR-7 backlog ahead-of-time)
- **Cost:** cheap (~0.5h ADR-7 prep notes; impl только при I-2 unblocked)
- **Verdict:** TAKE (Wave 0 — docs-only до I-2 lands)
- **Alternative-if-rejected:** при I-2 lands развернуть streamText/spawn-recursion bugs самим и debug
- **Concrete first step:** Добавить параграф в `knowledge/BACKLOG.md` I-2 entry: «Subagent invocation MUST use generateText (not stream), MUST remove SpawnSubagent from subagent tool set, MUST cap SUBAGENT_MAX_STEPS at 100».
- **Source(s):** Aperant item 7 в `gortex-aperant-inspiration-2026-05.md` Part 2.

---

### Group G — Skills / progressive disclosure

#### R-24 — Filesystem-canonical skill store + safe community import

- **What:** SKILL.md файлы с YAML frontmatter (`name`, `description`, `triggers`, `status: draft|active`, `review_required`); 3-section template (`## Trigger / ## Protocol / ## Output`); shared-overlay layering (project / user / global); `import_skill("github:user/repo/path")` с safe-slug validation, name-collision guard, mandatory `review_required: true` на каждом external import; `load_skill()` reveals draft skills с «say 'approve skill X' if useful» prefix (inverts feature-flag model: visible но gated на user assent). **3-project convergence** — Kronos R-4 (primary impl); DPC Pattern 13 «Memento-Skills» (same shape); Aperant filesystem-canon learning (same DNA). Unblocks BACKLOG I-9 «convert `repo-audit-playbook.md` into loadable SKILL».
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (skills lazy-loaded by trigger; не все в context)
  - (B) helps LLM find context when needed: YES (Mech-Wiki + 1 trigger lookup → right skill loaded)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (most directly FA-compatible KAOS subsystem)
- **Cost:** medium (~600 LOC source to port; FA equivalent ~300-400 LOC потому что нет draft-status workflow yet)
- **Verdict:** TAKE (Wave 3 — Phase M maturity; pairs с R-16 spec pipeline)
- **Alternative-if-rejected:** continue с flat `knowledge/prompts/*.md` без status / triggers / draft workflow
- **Concrete first step:** Прочитать Kronos `kronos/skills/store.py` (339 LOC) + `kronos/skills/tools.py` (~150 LOC, особенно `load_skill` reveal-with-prompt at lines 46-51).
- **Source(s):** Kronos `kronos-agent-os-inspiration-2026-05.md` §0 R-4 (primary); DPC `dpc-messenger-inspiration-2026-05.md` §2 Pattern 13 (convergence); Aperant gotchas/discoveries paradigm (broader convergence).

#### R-25 — Pause-file sentinel pattern (rate-limit + auth-failure)

- **What:** Filesystem-sentinel pause/resume mechanism. Orchestrator писает `<specDir>/RATE_LIMIT_PAUSE` (с reset timestamp) или `AUTH_PAUSE` когда hits HTTP 429/401; frontend (или human) пишет `<specDir>/RESUME` для unblock. Constants empirically validated: `MAX_RATE_LIMIT_WAIT_MS = 7_200_000` (2h), `RATE_LIMIT_CHECK_INTERVAL_MS = 30_000` (30s), `AUTH_RESUME_MAX_WAIT_MS = 86_400_000` (24h), `AUTH_RESUME_CHECK_INTERVAL_MS = 10_000` (10s). FA inherits same problem (rate-limited or auth-failed local LLM tier blocks whole session). Pause-file pattern = FA idiom (Markdown/JSON на disk, no IPC, no daemon).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: PARTIAL (RESUME-detection pulls session back from blocked state)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Mech-Wiki idiom применённый к runtime; pairs с R-4 blocker middleware)
- **Cost:** cheap (~80 LOC Python в `src/fa/orchestration/pause.py`)
- **Verdict:** TAKE (Wave 1 — pairs с R-1 но technically independent)
- **Alternative-if-rejected:** in-memory pause без on-disk sentinel — теряется при session restart
- **Concrete first step:** Lift verbatim из Aperant `apps/desktop/src/main/ai/orchestration/pause-handler.ts` (276 LOC); сохранить exact intervals (30s rate-limit, 10s auth) — empirically well-tuned, не менять без evidence.
- **Source(s):** Aperant item 9 в `gortex-aperant-inspiration-2026-05.md` Part 2 + Addendum.

---

### Group H — AGENTS.md / ADR citations cluster

#### R-26 — DPC-derived AGENTS.md citation cluster (4 sub-items)

- **What:** Четыре lightweight citation rules в AGENTS.md, каждое — one-paragraph reference к конкретному DPC ADR как empirical proof: **(1) ADR-015 «evolution worker removed»** — DPC построил background evolution worker, 20+ sessions, 0/40 valuable proposals, удалили 400 LOC + 7 tools. Цитата защищает от future «let FA improve itself» предложений. **(2) ADR-005 P18 scope-only-estimation rule** — estimate lines/files, never time. DPC example S14: CC estimated 5-7h для what took 11 min (27-38× error). **(3) ADR-021 Lesson 4 «write-only subsystems are dead weight»** — DPC found multiple write-only ML subsystems eating maintenance budget. Subtraction-first reinforcement. **(4) Prior-Art rule (DPC AP8 → B-NEW-8)** — каждый new FA ADR должен включать §Prior Art mapping each design choice к existing tools / papers / projects.
- **Project-axis fit:**
  - (A) reduces session-start noise: YES (one-line citations предотвращают future re-proposals)
  - (B) helps LLM find context when needed: YES (anti-pattern signal в AGENTS.md видим за один read)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (все 4 reinforce minimalism-first + subtraction-first + prior-art discipline)
- **Cost:** cheap (~0.5h каждое × 4 = ~2h всего; могут landed в одном PR or batch'нуты в 4 PR-а)
- **Verdict:** TAKE (Wave 0 — docs-only)
- **Alternative-if-rejected:** rely на minimalism-first principle alone без empirical examples
- **Concrete first step:** Открыть `AGENTS.md` §«PR Checklist» + §«Working in This Repo»; добавить 4 citation blocks с прямыми ссылками на DPC ADR-015 / ADR-005 / ADR-021 / ADR-020 §Research.
- **Source(s):** DPC `dpc-messenger-inspiration-2026-05.md` §0 R-4 / R-5 / R-6 + §6 AP8.

#### R-27 — Correlated-derived AGENTS.md citations (2 sub-items)

- **What:** Две lightweight citation rules из correlated-llm-errors note: **(1) Cornell / Simula primary-source citation в ADR-2** — strengthen «no cross-tier auto-escalation» rationale с конкретной academic-source citation (P-2 / P-3 papers per §6 R-2). **(2) «Prompt-diversity layer» as recognized anti-pattern** — добавить в AGENTS.md rule #10 minimalism-first evidence (P-3 §4.4 finding: prompt-diversity ensembles не дают consistent gains, только sample-by-sample noise).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (rationale, не код)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (process discipline)
- **Cost:** cheap (~0.5h каждое × 2 = ~1h)
- **Verdict:** TAKE (Wave 0 — docs-only)
- **Alternative-if-rejected:** ADR-2 + AGENTS.md rule #10 остаются без empirical-source citations
- **Concrete first step:** Открыть `knowledge/adr/ADR-2-llm-tiering.md` §Amendment 2026-04-29; добавить P-2/P-3 citation. Открыть AGENTS.md rule #10; добавить «prompt-diversity layer» one-paragraph с цитатой P-3 §4.4.
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §0 R-2 + R-3 + §6.

#### R-28 — Intra-role retry temperature default `T=1.0`

- **What:** ADR-2 / ADR-7 amendment fixing intra-role retry default: при повторе той же роли (Coder retries after error) — `T=1.0` (P-3 §4.1 finding). Если оставить T при default value (часто 0.0 или 0.2) — модель просто перевыбирает ту же гипотезу. T=1.0 forces diversity. NB: это не intra-role retry temperature; это температура **повторов в рамках одной роли** (отличается от R-19 cross-role disjointness).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime config)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Phase M HookRegistry guards получают чёткое retry-temp правило)
- **Cost:** cheap (~0.5h ADR-7 §5 + ~10 LOC в HookRegistry retry guard)
- **Verdict:** TAKE (Wave 0 — docs + cheap impl)
- **Alternative-if-rejected:** keep T at default — retry returns same answer; cost доуплицируется без benefit
- **Concrete first step:** Открыть ADR-7 §5 Lifecycle Guards; добавить «Intra-role retry: T=1.0 default per P-3 §4.1 finding»; зафиксировать в HookRegistry retry-strategy contract.
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §6 R-8.

#### R-29 — LLM-using hooks MUST use family ≠ acting-role (ADR-7 future amendment)

- **What:** Future ADR-7 amendment (vacuous пока все хуки детерминированы Python функции; landит когда первый LLM-using hook появится): «если HookRegistry middleware вызывает LLM (например LoopGuard просит вторую модель оценить loop-evidence), то эта LLM MUST быть из другой provider/family чем acting-role». Простыми словами: судья не должен быть из того же семейства что подсудимый. Одно семейство = одни ошибки повторяются.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (future-conditional)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (generalization of R-19 Eval-disjoint к hook-context)
- **Cost:** cheap (~0.2h — добавить ADR-7 §Lifecycle hooks параграф)
- **Verdict:** TAKE (Wave 0 — docs-only; vacuous до first LLM-using hook lands)
- **Alternative-if-rejected:** при первом LLM-using hook появляется same-family judge anti-pattern bug
- **Concrete first step:** Открыть ADR-7 §5 Lifecycle Guards; добавить параграф: «LLM-using hooks MUST use provider+family disjoint from acting-role per Correlated R-9 / generalisation of ADR-2 R-1».
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §6 R-9.

#### R-30 — `max_iterations` cap rationale citation (YT-4 empirical anchor)

- **What:** Docs-only addition в ADR-7 rationale section: YT-4 эмпирический anchor — GPT-3.5 Turbo успешно завершил multi-step Hacker News upvote within **6 итераций** when harness был correct (DSV + login middleware + max_iter=6). Без harness — hallucinated success на step 2. Reinforces текущий retry-budget invariant (R-7) с конкретным числом. Cite в ADR-7 §5 Lifecycle Guards как «default cap = 6 derived from YT-4 empirical».
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (docs)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (empirical citation для existing principle)
- **Cost:** cheap (~10 min — 1-line citation в ADR-7)
- **Verdict:** TAKE (Wave 0 — landit с R-7 в одном edit)
- **Alternative-if-rejected:** keep max_iterations cap без empirical citation; bias toward magic-number suspicion
- **Concrete first step:** Открыть ADR-7 §5; добавить 1-line citation: «default `max_iterations = 6` per YT-4 Tejas Kumar empirical (GPT-3.5 Turbo + DSV harness)».
- **Source(s):** YT-4 (см. `yt-concepts-for-FA.md` #21 — primary).

#### R-31 — Phase M runner with Komissar Naikan + heartbeat tick (soviet B-NEW-3)

- **What:** Soviet-code's Phase M runner pattern: **(1) Heartbeat tick** — каждые N seconds runner emits one-line status в `conductor.events.jsonl` («still working on subtask X, attempt Y/Z»). **(2) Komissar Naikan** — 12h periodic reflection prompt: «what went well in past 12h, what failed, what to change tomorrow» — gated by mtime + ≥5 work-ticks (не cron). **(3) S/M/L gate** — каждые ~30min runner reviews scope-creep: «Are we still doing Small task? Did it become Medium? Large?». Если creep > gate → escalate. Прямо ложится на FA Phase M ADR (будущий).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: YES (heartbeat + reflection становятся context для next session)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (Phase M runner shape — основная разблокировка)
- **Cost:** medium (3-5h ADR + skeleton; ~250 LOC)
- **Verdict:** TAKE (Wave 3 — Phase M ADR scope)
- **Alternative-if-rejected:** Phase M runner ad-hoc без structured heartbeat / reflection / gate
- **Concrete first step:** Прочитать DPC's coverage soviet-code в `dpc-messenger-inspiration-2026-05.md` §4 B-NEW-3 row; разворачивать в собственный Phase M runner ADR.
- **Source(s):** soviet-code via DPC `dpc-messenger-inspiration-2026-05.md` §4 (B-NEW-3).

#### R-32 — Anti-pattern catalog as living document (soviet B-NEW-4)

- **What:** Soviet-code's «anti-pattern catalog + on-demand detector personas» pattern: `knowledge/anti-patterns/` directory с per-anti-pattern markdown files (one each), плюс «detector personas» — prompts которые при invoke ищут текущий codebase / artifact на presence of specific anti-pattern. Пример: `anti-pattern-100-percent-ai-driven.md` + persona prompt «You are anti-pattern detector for fully-AI-driven workflows. Scan recent PRs for ...». Это **complementary к §6 Anti-Patterns в этой ноте** — catalogue lives и обновляется, не однократный dump.
- **Project-axis fit:**
  - (A) reduces session-start noise: PARTIAL (catalog lazy-loaded только при detector invoke)
  - (B) helps LLM find context when needed: YES (cataloged anti-pattern → детектор знает что искать)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (subtraction-first дисциплина получает active enforcement, не только passive AGENTS.md rules)
- **Cost:** medium (3-4h directory + 3-5 stub anti-patterns + 1-2 detector personas; ~400 LOC markdown total)
- **Verdict:** TAKE (Wave 3 — Phase M maturity)
- **Alternative-if-rejected:** anti-patterns живут только в §6 этой ноты и в DPC AP1-AP8 — passive, нет detector
- **Concrete first step:** Создать `knowledge/anti-patterns/` directory; первые 3 stubs: DPC AP1 (evolution worker), DPC AP5 (write-only subsystems), soviet «100%-AI-driven».
- **Source(s):** soviet-code via DPC `dpc-messenger-inspiration-2026-05.md` §4 (B-NEW-4).

---

### Group I — GitHub workflow (partially TAKE, mostly DEFER)

#### R-33 — `pr_orchestrator` + `pr_followup_orchestrator` prompt template lift

- **What:** Hardened PR-review prompts: three-phase review (Understand → Deep Analysis → Verify), section «Never classify a PR as trivial and skip analysis» backed by реальной war-story (1-line PR с 9 latent issues), explicit subagent-dispatch playbook (`spawn_security_review`, `spawn_quality_review`, `spawn_deep_analysis`). Pull **structure** (не verbatim text) в FA `knowledge/prompts/code-review.md`. «War story → discipline» framing — high-leverage way encode lessons в prompts без unbounded growth.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (per-task prompt)
  - (B) helps LLM find context when needed: YES (when PR review is invoked, right prompt loaded)
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (GitHub workflow scope, not Phase M)
- **Cost:** medium (2-3h — extract structure + adapt; full prompt ~700 LOC)
- **Verdict:** TAKE (Wave 3 — Phase M maturity; selective adoption)
- **Alternative-if-rejected:** ad-hoc PR review prompts
- **Concrete first step:** Прочитать Aperant `apps/desktop/prompts/github/pr_orchestrator.md` (435 LOC) + `pr_followup_orchestrator.md` (364 LOC); adapt structure (not verbatim) к FA.
- **Source(s):** Aperant item 3 в `gortex-aperant-inspiration-2026-05.md` Part 2.

#### R-34 — QA loop circuit-breaker constants (extract без full engine)

- **What:** Three magic-validated constants из Aperant `qa-loop.ts` (630 LOC) которые можно landit standalone в FA HookRegistry guards без full QA engine: `MAX_QA_ITERATIONS = 50`, `MAX_CONSECUTIVE_ERRORS = 3`, `RECURRING_ISSUE_THRESHOLD = 3` (escalate-to-human after same issue recurs 3x). Эти числа empirically tuned в Aperant prod-системе; brute-force porting full 630-LOC orchestrator пока не нужен, но **constants — нужны**.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (runtime)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: YES (HookRegistry guards получают proven defaults вместо magic numbers)
- **Cost:** cheap (~0.5h — лишь записать константы в HookRegistry guard configs)
- **Verdict:** TAKE (Wave 2 — pairs с R-1 / R-2)
- **Alternative-if-rejected:** изобретать свои defaults для retry / error / recurring thresholds
- **Concrete first step:** При написании ADR-8 (HookRegistry) — упомянуть три константы как defaults в guard configs.
- **Source(s):** Aperant item 5 в `gortex-aperant-inspiration-2026-05.md` Part 2 (constants only, engine = DEFER R-37).

#### R-35 — Triage engine pattern (structured output via Zod)

- **What:** Reference pattern: structured-output triage через AI SDK `Output.object()` + Zod schema. Returns `{issueNumber, category, confidence, labelsToAdd, labelsToRemove, isDuplicate, duplicateOf, isSpam, priority, comment}`. Любая FA tool которая нуждается в structured output получает parser-free output ценой одного extra schema definition (Python equivalent: Pydantic).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (GitHub workflow scope, not Phase M priority)
- **Cost:** medium (~302 LOC TS — reference, not port)
- **Verdict:** DEFER (Phase M+ GitHub workflow scope)
- **Alternative-if-rejected:** ad-hoc parsing of LLM output для triage tasks
- **Concrete first step (if TAKE later):** Прочитать Aperant `apps/desktop/src/main/ai/runners/github/triage-engine.ts` (302 LOC); pattern уже знаком (Pydantic equivalents).
- **Source(s):** Aperant item 4 в `gortex-aperant-inspiration-2026-05.md` Part 2.

#### R-36 — Semantic merge analyzer (regex-by-extension)

- **What:** Six-file intent-aware merge subsystem: pipeline `load baselines → semantic-analyzer.ts extracts language-aware deltas (imports added/removed, functions added/removed/modified, hook calls, JSX changes) via regex patterns per file extension → conflict-detector.ts flags conflicts → auto-merger.ts applies deterministic merges → ambiguous conflicts go to one-shot AI call → final merged content + detailed report`. FA сегодня single-agent; multi-agent worktree-based parallelism — future state. Но **semantic-analyzer regex-by-extension pattern** (`semantic-analyzer.ts:26-50`) reusable standalone для FA changelog generation / triage / decide whether change safe для auto-merge.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: NO (multi-agent future scope)
- **Cost:** medium-high (~725 + 363 + 118 LOC TS = ~1200 LOC source; Python port ~600 LOC)
- **Verdict:** DEFER (only when FA gets multi-agent worktree parallelism — далекий horizon)
- **Alternative-if-rejected:** continue с git merge defaults + LLM-only conflict resolution
- **Concrete first step (if TAKE later):** Прочитать Aperant `apps/desktop/src/main/ai/merge/semantic-analyzer.ts` lines 26-50 — это reusable standalone Python ~80 LOC.
- **Source(s):** Aperant item 14 в `gortex-aperant-inspiration-2026-05.md` Part 2.

#### R-37 — CI workflow hardening (SHA-pinned actions + build-tag matrix)

- **What:** Two patterns из Gortex `.github/workflows/ci.yml`: (1) **SHA-pinned actions** — readable comment + immutable pin (`actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6`). Supply-chain hygiene. (2) **Build-tag matrix to prevent silent rot** — FA имеет optional dependency paths (ctags, FTS5) которые могут broke без обнаружения. 3-line build-mode matrix catches that. Бонус: `benchmark` job только на PRs.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO (CI)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: PARTIAL (process discipline, не product)
- **Cost:** cheap-medium (~1-2h — edit `.github/workflows/ci.yml`)
- **Verdict:** DEFER (FA CI сегодня light; relevant когда optional dependencies (ctags / FTS5) станут sources of silent rot)
- **Alternative-if-rejected:** FA CI без SHA-pin (vulnerable to supply-chain) + без build-tag matrix (silent rot possible)
- **Concrete first step (if TAKE later):** Открыть Gortex `.github/workflows/ci.yml` (~110 LOC); copy SHA-pin pattern + 3-line build-mode matrix.
- **Source(s):** Gortex item P в `gortex-aperant-inspiration-2026-05.md` Addendum.

---

### Group J — Deferred / out-of-immediate-scope items

#### R-38 — Multi-model ensembling with diversity-based selector (UC5 candidate)

- **What:** Cross-model ensemble (3-5 OSS LLMs от разных labs) + diversity-based selector выбирает ответ с highest disagreement-resolved confidence. Empirically validated в P-3 papers. **Не для текущей фазы** — требует UC5d (eval-driven harness iteration) ships + selector primitive lands. Записан как BACKLOG I-10 placeholder.
- **Project-axis fit:**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: NO (UC5 scope, not Phase M)
- **Cost:** expensive (multi-week — needs eval-harness + selector + benchmark suite)
- **Verdict:** DEFER → BACKLOG I-10 placeholder
- **Alternative-if-rejected:** stick с ADR-2 single-model-per-role routing
- **Concrete first step (if TAKE later):** Re-open после UC5d harness ships; first re-read Correlated R-4 + P-3 papers.
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §0 R-4 + §6 R-4.

#### R-39 — Verifier-based selection (vs majority-vote)

- **What:** Verifier-based selection: separate verifier LLM (cross-family) reviews N candidate outputs и selects лучший (вместо majority vote). P-3 §4.4 finding: verifier > majority-vote when models trained on different data. Pairs с R-19 (Eval disjoint) и R-38 (multi-model ensemble).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: NO (UC5 scope)
- **Cost:** expensive (depends на UC5)
- **Verdict:** DEFER → UC5 candidate
- **Alternative-if-rejected:** при ensembling в UC5 — majority vote (proven suboptimal but cheap)
- **Source(s):** Correlated `correlated-llm-errors-and-ensembling-2026-05.md` §0 R-5.

#### R-40 — Worker-thread isolation between phases

- **What:** Worker-thread isolation для каждой agent session. Каждая phase (planning/coding/QA/spec) получает свой worker thread; `WorkerConfig` через `workerData`, structured `WorkerMessage`s через `parentPort`. Python's `multiprocessing` analog. FA сегодня single-process; isolation between phases pригодится при corruption-risk between agents (e.g., planner не может accidentally corrupt coder's spec dir).
- **Project-axis fit:**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit:**
  - (C) advances chosen goal_lens: NO (Phase M+ scope, multi-process)
- **Cost:** medium-high (~600 LOC Python; non-trivial debugging)
- **Verdict:** DEFER (only when corruption-risk between agents materializes)
- **Alternative-if-rejected:** single-process FA с in-process phase isolation (current state)
- **Source(s):** Aperant item 12 в `gortex-aperant-inspiration-2026-05.md` Part 2.

---

### REFERENCE-only appendix

#### REF-1 — Aperant `subtask-iterator.ts` (528 LOC) as reference implementation

- **Why REFERENCE:** Pre-written 528-LOC concrete implementation того loop'a что FA сам напишет — cancellation via AbortSignal, worktree-mode RESUME fallback, stuck-subtask escalation, attempt counting, insight extraction. Не порируем; читаем перед написанием своего to save 2 design iterations.
- **Source:** Aperant item 10 в `gortex-aperant-inspiration-2026-05.md` Part 2.

---

### Summary table

| R-N   | Verdict   | Project-fit (A / B) | Goal-fit (C) | Cost         | Alternative-if-rejected                | User decision needed? |
| ----- | --------- | ------------------- | ------------ | ------------ | -------------------------------------- | --------------------- |
| R-1   | TAKE      | NO / NO             | YES          | medium       | inline if/elif guards                  | No                    |
| R-2   | TAKE      | NO / YES            | YES          | cheap        | rely on ADR-2 fail-loudly              | No                    |
| R-3   | TAKE      | NO / YES            | YES          | medium       | retry-once без categories              | No                    |
| R-4   | TAKE      | NO / PARTIAL        | YES          | medium       | LLM handles each blocker               | No                    |
| R-5   | TAKE      | NO / YES            | YES          | cheap        | trust LLM-claimed success              | No                    |
| R-6   | TAKE      | PARTIAL / YES       | YES          | cheap-medium | passive log only                       | No                    |
| R-7   | TAKE      | NO / NO             | YES          | cheap        | magic numbers в guards                 | No                    |
| R-8   | TAKE      | YES / YES           | YES          | cheap        | manual HANDOFF.md only                 | No                    |
| R-9   | TAKE      | YES / YES           | YES          | cheap        | freeform HANDOFF.md                    | No                    |
| R-10  | TAKE      | YES / YES           | YES          | medium       | mid-task gotchas only                  | No                    |
| R-11  | DEFER     | YES / YES           | YES          | expensive    | filesystem-canon Markdown only         | Yes (timing)          |
| R-12  | DEFER     | YES / YES           | YES          | medium       | manual HANDOFF.md only                 | Yes (depends on R-1)  |
| R-13  | TAKE      | YES / YES           | YES          | medium       | manual review + rule #3                | No                    |
| R-14  | TAKE      | PARTIAL / YES       | YES          | cheap        | `find . -name AGENTS.md` walk-up       | No                    |
| R-15  | DEFER     | YES / YES           | PARTIAL      | medium       | existing repo-audit-playbook.md prompt | No (prompt exists)    |
| R-16  | TAKE      | NO / YES            | YES          | medium       | ad-hoc prompts                         | No                    |
| R-17  | TAKE      | NO / PARTIAL        | YES          | medium       | procedural QA pipeline                 | No                    |
| R-18  | TAKE      | NO / PARTIAL        | YES          | cheap        | single tool-shape                      | No                    |
| R-19  | TAKE      | NO / NO             | YES          | cheap        | no disjointness rule                   | No                    |
| R-20  | TAKE      | NO / NO             | YES          | medium       | path-only sandbox                      | No                    |
| R-21  | TAKE      | NO / NO             | YES          | cheap        | hardcoded capability list              | No                    |
| R-22  | DEFER     | NO / PARTIAL        | PARTIAL      | cheap        | raw events.jsonl без redaction         | No (pairs с R-12)     |
| R-23  | TAKE      | NO / NO             | PARTIAL      | cheap        | discover bugs at I-2 land              | No                    |
| R-24  | TAKE      | YES / YES           | YES          | medium       | flat prompts/ без status               | No                    |
| R-25  | TAKE      | NO / PARTIAL        | YES          | cheap        | in-memory pause                        | No                    |
| R-26  | TAKE      | YES / YES           | YES          | cheap        | rely on minimalism alone               | No                    |
| R-27  | TAKE      | NO / NO             | PARTIAL      | cheap        | ADR-2 + rule#10 без citations          | No                    |
| R-28  | TAKE      | NO / NO             | YES          | cheap        | T at default, identical retries        | No                    |
| R-29  | TAKE      | NO / NO             | PARTIAL      | cheap        | discover bug at first LLM-hook         | No                    |
| R-30  | TAKE      | NO / NO             | PARTIAL      | cheap        | max_iter cap без empirical             | No                    |
| R-31  | TAKE      | NO / YES            | YES          | medium       | Phase M runner ad-hoc                  | No                    |
| R-32  | TAKE      | PARTIAL / YES       | YES          | medium       | anti-patterns только пассив            | No                    |
| R-33  | TAKE      | NO / YES            | PARTIAL      | medium       | ad-hoc PR review prompts               | No                    |
| R-34  | TAKE      | NO / NO             | YES          | cheap        | invent own thresholds                  | No                    |
| R-35  | DEFER     | NO / NO             | PARTIAL      | medium       | ad-hoc structured output parsing       | No                    |
| R-36  | DEFER     | NO / NO             | NO           | medium-high  | git merge defaults + LLM resolver      | No                    |
| R-37  | DEFER     | NO / NO             | PARTIAL      | cheap-medium | FA CI без SHA-pin / build-matrix       | No                    |
| R-38  | DEFER     | NO / NO             | NO           | expensive    | single-model-per-role                  | No                    |
| R-39  | DEFER     | NO / NO             | NO           | expensive    | majority-vote in ensemble              | No                    |
| R-40  | DEFER     | NO / NO             | NO           | medium-high  | in-process phase isolation             | No                    |
| REF-1 | REFERENCE | —                   | —            | —            | write our own without reading source   | No                    |


---

## 3. Master FA-relevance mapping (sortable)

🇷🇺 Compact one-row-per-R-N table; sortable mentally или через grep.
Cross-references к ADR / BACKLOG / source.

| R-N      | FA artifact (existing or new)                                                         | Wave      | Source(s) — short               | LOC              |
| -------- | ------------------------------------------------------------------------------------- | --------- | ------------------------------- | ---------------- |
| R-1      | ADR-8 «HookRegistry» (new)                                                            | 1         | DPC R-1 + Gortex hooks          | ~500             |
| R-2      | HookRegistry guard middleware                                                         | 2         | Kronos R-3 + Aperant 8          | ~130             |
| R-3      | `src/fa/middleware/failure_classifier.py`                                             | 2         | YT-1 #1 + Aperant 8             | ~230             |
| R-4      | HookRegistry `pre_tool` middleware                                                    | 2         | YT-4 #20                        | ~120             |
| R-5      | `src/fa/verifier/verify_action.py` + `verifiers/*.yaml`                               | 0         | YT-4 #18                        | ~100             |
| R-6      | `knowledge/trace/attempt_history.json` writer + `knowledge/prompts/coder-recovery.md` | 2         | Aperant 8 + 13                  | ~180 + prompt    |
| R-7      | ADR-7 §5 amendment                                                                    | 0         | Correlated R-7 + R-8 + YT-4 #21 | docs-only        |
| R-8      | `src/fa/tools/record_gotcha.py` + `record_discovery.py`                               | 0         | Aperant 1 + 2                   | ~150             |
| R-9      | `knowledge/prompts/handoff-summarizer.md` (new)                                       | 0         | Kronos R-5                      | ~15              |
| R-10     | `src/fa/runners/insight_extractor.py` + prompt                                        | 3         | Aperant 11                      | ~250 + prompt    |
| R-11     | KG ADR + `src/fa/graph/sqlite_graph_backend.py`                                       | 4 (DEFER) | DPC R-2                         | ~700             |
| R-12     | Sleep ADR + `src/fa/sleep/pipeline.py` + `_meta.json` sidecar                         | 4 (DEFER) | DPC R-3                         | ~400             |
| R-13     | `src/fa/hygiene/{tokens,suggestions,discover}.py`                                     | 0         | Gortex B + C + K                | ~250             |
| R-14     | AGENTS.md §workspace addition                                                         | 0         | Gortex O                        | docs-only        |
| R-15     | `src/fa/audit/` (full subsystem)                                                      | 4 (DEFER) | Gortex R-1 / A                  | ~500             |
| R-16     | `knowledge/prompts/spec-pipeline/{complexity-assessor,spec-quick,spec-writer}.md`     | 3         | Aperant 15 + soviet B-NEW-2     | ~700 prompt      |
| R-17     | `knowledge/prompts/qa-orchestrator-agentic.md` + runner                               | 3         | Aperant 16                      | ~350             |
| R-18     | `knowledge/prompts/tool-shapes.yaml` + per-role 1-liner                               | 1         | YT-1 #7 + #8                    | ~50              |
| R-19     | ADR-2 §Amendment + `src/fa/llm/family_extractor.py`                                   | 0         | Correlated R-1                  | ~30 + docs       |
| R-20     | `src/fa/sandbox/bash_gate.py` + ADR-6 amendment                                       | 1         | Aperant 6 + Gortex M            | ~400             |
| R-21     | ADR-6 §Capability gates + 5 flags в `config.yaml`                                     | 1         | Kronos config + soviet B-NEW-1  | ~50              |
| R-22     | `src/fa/audit/pii.py` + audit-write hook                                              | 3 (DEFER) | Kronos R-2 part 2               | ~150             |
| R-23     | BACKLOG I-2 prep notes + ADR-7 mention                                                | 0         | Aperant 7                       | docs-only        |
| R-24     | `knowledge/skills/` directory + `src/fa/skills/store.py`                              | 3         | Kronos R-4 + DPC P-13           | ~400             |
| R-25     | `src/fa/orchestration/pause.py` + sentinel files                                      | 1         | Aperant 9                       | ~80              |
| R-26     | AGENTS.md citations (4 sub-items DPC)                                                 | 0         | DPC R-4 + R-5 + R-6 + AP8       | docs-only        |
| R-27     | AGENTS.md + ADR-2 citations (2 sub-items Correlated)                                  | 0         | Correlated R-2 + R-3            | docs-only        |
| R-28     | ADR-7 §5 amendment (T=1.0)                                                            | 0         | Correlated R-8                  | docs + ~10 LOC   |
| R-29     | ADR-7 §Lifecycle hooks future amendment                                               | 0         | Correlated R-9                  | docs-only        |
| R-30     | ADR-7 §5 citation                                                                     | 0         | YT-4 #21                        | docs-only        |
| R-31     | Phase M runner ADR (new)                                                              | 3         | soviet B-NEW-3                  | ~250             |
| R-32     | `knowledge/anti-patterns/` directory                                                  | 3         | soviet B-NEW-4                  | ~400 markdown    |
| R-33     | `knowledge/prompts/code-review.md` (new)                                              | 3         | Aperant 3                       | ~250 prompt      |
| R-34     | HookRegistry guard config constants                                                   | 2         | Aperant 5 (constants)           | docs + ~5 LOC    |
| R-35     | `src/fa/github/triage.py`                                                             | 4 (DEFER) | Aperant 4                       | ~302 (reference) |
| R-36     | `src/fa/github/semantic_analyzer.py`                                                  | 4 (DEFER) | Aperant 14                      | ~600             |
| R-37     | `.github/workflows/ci.yml` hardening                                                  | 4 (DEFER) | Gortex P                        | ~20 LOC YAML     |
| R-38     | BACKLOG I-10 placeholder                                                              | 4 (DEFER) | Correlated R-4                  | TBD UC5          |
| R-39     | UC5 candidate                                                                         | 4 (DEFER) | Correlated R-5                  | TBD UC5          |
| R-40     | Future ADR (multi-process FA)                                                         | 4 (DEFER) | Aperant 12                      | ~600             |
| REF-1    | (reference reading before writing FA's subtask iterator)                              | REF       | Aperant 10                      | 0                |


---

## 4. Convergent evolution evidence

🇷🇺 **Что это:** многопроектные подтверждения дизайн-выборов. Когда
3+ проектов независимо пришли к одному паттерну — это **strongest
signal** для FA borrowing-decision: «не изобретаем велосипед, потому что
независимо изобретённый велосипед — это уже сильный отбор-фильтр».

### 4.1 HookRegistry / 2-tier middleware (8-project convergence)

| Source | Manifestation |
|--------|---------------|
| DPC `dpc_agent/hooks.py` | `HookRegistry` class + `GuardMiddleware` / `ObserverMiddleware` parent classes |
| Cited in DPC ADR-007 (4 prior arts) | LangGraph, AutoGen, OpenDevin, custom middleware patterns |
| Gortex `internal/hooks/{dispatch,pretooluse,posttask,...}.go` | Runtime hooks in Claude Code: enrich-or-deny per tool call, recursion-guard, silent-degrade |
| Kronos `kronos/security/loop_detector.py` | Middleware-shaped 3-detector circuit breaker (subset, не registry) |
| FA `knowledge/adr/ADR-7-inner-loop-tool-registry.md` §5 | Lifecycle hooks already declared as design surface — R-1 lands ADR-8 fleshing-out |

🇷🇺 **Vote weight:** 8-project convergence on «inner-loop needs explicit
middleware substrate, not inline if/elif». Map to R-1 в §0.

### 4.2 Filesystem-canonical learning loop (3-project convergence)

| Source | Manifestation |
|--------|---------------|
| Aperant `record-gotcha.ts` + `record-discovery.ts` | Two minimal tools appending to `memory/gotchas.md` + `memory/codebase_map.json` |
| YT-3 #6 (Mavis runtime extraction) | Empirical citation: runtime-extracted rules persisted to filesystem |
| Kronos `audit.py` + `_meta.json` | Per-file sidecar with access counts, embeddings cache, stale flags |

🇷🇺 **Vote weight:** 3-project + atomic-rename idiom across all three.
Map to R-8 + R-12 (`_meta.json` precursor part).

### 4.3 Filesystem-canonical skills (3-project convergence)

| Source | Manifestation |
|--------|---------------|
| Kronos `kronos/skills/{store,tools,hub}.py` | SKILL.md + YAML frontmatter + status flags + draft/active workflow |
| DPC Pattern 13 «Memento-Skills» | DPC reference to filesystem-canonical skills with status |
| Aperant filesystem-canon paradigm | Broader DNA shared (gotchas/discoveries = same idiom) |

🇷🇺 **Vote weight:** 3-project + identical YAML frontmatter shape (`name`,
`description`, `triggers`, `status`). Map to R-24.

### 4.4 Sleep consolidation / morning brief (3-project convergence)

| Source | Manifestation |
|--------|---------------|
| DPC `dpc_agent/sleep_pipeline.py` (user-triggered) | N+1 LLM calls over session archives |
| soviet-code (gated cron, через DPC §4 inheritance) | Cron но gated на ≥5 work-ticks (не pure cron) |
| FA HANDOFF.md (manual trigger) | Pre-existing manual analog |

🇷🇺 **Vote weight:** 2 of 3 votes against pure-cron (DPC + FA);
1 split (soviet uses gated cron). Map to R-12.

### 4.5 Failure classification + recovery action (2-project convergence)

| Source | Manifestation |
|--------|---------------|
| YT-1 #1 (Mavis tripartite) | `invalid_arguments` / `unexpected_environments` / `provider_errors` |
| Aperant `recovery-manager.ts` `classifyFailure()` | 7 categories with `RecoveryAction` enum |

🇷🇺 **Vote weight:** 2-project + tripartite ⊂ Aperant 7-cat extension.
Map to R-3.

### 4.6 Loop detection / circular fix guard (3-project convergence)

| Source | Manifestation |
|--------|---------------|
| YT-4 #18 (DSV — verifier shape) | Post-action verifier overrides LLM-claimed success |
| Kronos `loop_detector.py` (3-detector shape) | Runtime 3-detector × 3-level circuit breaker |
| Aperant `recovery-manager.ts` simpleHash (3-attempt threshold) | `CIRCULAR_FIX_THRESHOLD=3` + simpleHash error grouping |

🇷🇺 **Vote weight:** 3-project, complementary not duplicate — DSV =
post-action verifier; Kronos = runtime loop detector; Aperant = retry
counter. Map to R-2 (Kronos + Aperant merge) + R-5 (DSV standalone).

### 4.7 PII redaction recursive walker (2-project convergence)

| Source | Manifestation |
|--------|---------------|
| Aperant `secret-scanner.ts` | Per-file secret detection (file-level) |
| Kronos `pii.py:1-91` | Recursive walker (object-level, deeper) |

🇷🇺 **Vote weight:** 2-project; Kronos has deeper recursive shape than
Aperant. Map to R-22 (use Kronos primary).

### 4.8 Pause-file filesystem sentinel (2-project convergence)

| Source | Manifestation |
|--------|---------------|
| Aperant `pause-handler.ts` | `RATE_LIMIT_PAUSE` / `AUTH_PAUSE` / `RESUME` sentinel files |
| Kronos conversational `approve_skill()` chat-tool | Different mechanism but same «human-as-circuit-completer» idiom |

🇷🇺 **Vote weight:** 2-project (different mechanisms but shared
philosophy). Map to R-25 (Aperant primary).

### 4.9 Spec pipeline mandatory write-tool gate (2-project convergence)

| Source                                                   | Manifestation                                                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Aperant `complexity_assessor.md` + spec pipeline prompts | «MANDATORY: You MUST call the Write tool. Describing in text doesn't count.» |
| soviet B-NEW-2 «mandatory Inspection phase»              | Inspection phase MUST produce on-disk artifact                               |

🇷🇺 **Vote weight:** 2-project, identical contract «orchestrator
validates by disk, not text». Map to R-16.

### 4.10 Anti-patterns — convergent removal evidence

| Anti-pattern | Removed in | Evidence shape |
|--------------|-----------|----------------|
| Cron / background self-modification без external fitness | DPC ADR-015 (background worker removed) + Kronos R-6 (cron skipped) | 2 projects independently identified + abandoned |
| Write-only subsystem | DPC ADR-021 Lesson 4 + Aperant subsystem cleanup | 2 projects independently identified |
| Brute-force retry без circuit breaker | Aperant has circuit breaker; Kronos has 3-detector | 2 projects added explicit circuit-breaker on top of retry loop |
| Hardcoded scope estimation в часах | DPC ADR-005 P18 | Single project, but explicit lesson with 27-38× error empirical |

🇷🇺 **Use evidence:** §6 Anti-Patterns consolidated list использует эти
multi-project convergences как «strongest signal» для AGENTS.md citations.

---

## 5. Execution waves (topological by dependency)

🇷🇺 **Что это:** R-N в groups (A..J) — это **what** + **why**. Эта секция
— **when**, в каком порядке landить. Wave 0 = «можешь делать сегодня».
Wave 1-4 = upstream-dependent.

### Wave 0 — No dependencies, cheap, can land now (16 R-Ns)

🇷🇺 Все можно landit в ближайшие 1-2 недели; ~25-30h total work spread.

| R-N | Cost | Action |
|-----|------|--------|
| R-5 | cheap (~100 LOC) | DSV gate `verifiers/edit_file.yaml` + `verify_action.py` |
| R-7 | cheap (~1h) | ADR-7 §5 amendment (retry-budget invariant + T=1.0) |
| R-8 | cheap (~150 LOC) | `record_gotcha.py` + `record_discovery.py` |
| R-9 | cheap (~15 LOC) | `knowledge/prompts/handoff-summarizer.md` |
| R-13 | medium (~250 LOC) | `src/fa/hygiene/{tokens,suggestions,discover}.py` |
| R-14 | cheap (docs) | AGENTS.md §workspace addition |
| R-19 | cheap (~30 LOC + ADR) | ADR-2 §Amendment (Eval disjoint) + regex slug extractor |
| R-23 | cheap (docs) | BACKLOG I-2 prep + ADR-7 mention |
| R-26 | cheap (~2h docs) | DPC-derived AGENTS.md citation cluster (4 sub-items) |
| R-27 | cheap (~1h docs) | Correlated-derived citations (2 sub-items) |
| R-28 | cheap (~10 LOC) | ADR-7 §5 amendment T=1.0 + HookRegistry config |
| R-29 | cheap (docs) | ADR-7 future-amendment LLM-using-hooks rule |
| R-30 | cheap (docs) | ADR-7 §5 max_iterations citation |

🇷🇺 **Suggested daily batches** (3-4 cheap + 1 medium per day):

- **Day 1:** R-9 + R-7 + R-23 + R-26 cluster sub-1 (ADR-015) — ~3h, all docs.
- **Day 2:** R-14 + R-26 cluster sub-2/3 (ADR-005 + ADR-021) + R-27 — ~3h docs.
- **Day 3:** R-26 cluster sub-4 (Prior-Art rule) + R-28 + R-29 + R-30 — ~3h docs.
- **Day 4:** R-19 ADR-2 amendment + regex slug extractor — ~3h.
- **Day 5-6:** R-8 record_gotcha + record_discovery port — ~3-4h.
- **Day 7-8:** R-13 hygiene module port — ~4-6h.
- **Day 9-10:** R-5 DSV gate impl + 4-5 YAML verifier contracts — ~3-4h.

🇷🇺 **Total Wave 0 ROI:** ~25-30h work; lands 13 R-N spanning AGENTS.md
discipline, HANDOFF.md quality, audit hygiene, DSV gate, sandbox prep.

### Wave 1 — Independent unblocking (5 R-Ns)

🇷🇺 Не depend on R-1 HookRegistry; can run in parallel.

| R-N | Cost | Action | Pairs с |
|-----|------|--------|---------|
| R-18 | cheap (~50 LOC) | `knowledge/prompts/tool-shapes.yaml` + role 1-liners | ADR-2 |
| R-20 | medium (~400 LOC) | `src/fa/sandbox/bash_gate.py` + ADR-6 amendment | R-4 (Wave 2) |
| R-21 | cheap (~50 LOC) | 5 capability flags в `config.yaml` + ADR-6 §Capability gates | R-20 |
| R-25 | cheap (~80 LOC) | `src/fa/orchestration/pause.py` + sentinel files | R-4 (Wave 2) |
| **R-1** | medium (~500 LOC) | **ADR-8 «HookRegistry» — UNBLOCKS Wave 2** | — |

🇷🇺 **Strategy:** parallelize R-18/R-20/R-21/R-25 (independent) с R-1
(blocker для Wave 2). Total ~2-3 недели если 4-8h/неделя.

### Wave 2 — Blocked-on R-1 HookRegistry (6 R-Ns)

🇷🇺 Все нужны R-1 substrate.

| R-N | Cost | Action | Subclass type |
|-----|------|--------|---------------|
| R-2 | cheap (~130 LOC) | `LoopGuard` middleware subclass | GuardMiddleware |
| R-3 | medium (~230 LOC) | Failure classifier + RecoveryAction dispatcher | GuardMiddleware |
| R-4 | medium (~120 LOC) | Pre-tool blocker middleware (3 subclasses) | GuardMiddleware |
| R-6 | cheap-med (~180 LOC) | `attempt_history.json` writer + coder-recovery prompt | — (pairs с R-3) |
| R-22 | cheap (~150 LOC) | PII redaction walker + audit-write hook | ObserverMiddleware |
| R-34 | cheap (~5 LOC) | HookRegistry guard constants (Aperant 5 reference) | — config-only |

🇷🇺 **Strategy:** R-2 первым (самый простой middleware), затем R-3 + R-4
параллельно, R-6 + R-22 + R-34 параллельно.

### Wave 3 — Phase M maturity (8 R-Ns)

🇷🇺 Требуют HookRegistry stable + Phase M ADR landing.

| R-N | Cost | Action |
|-----|------|--------|
| R-10 | medium (~250 LOC + prompt) | Insight extractor (post-session pass) |
| R-16 | medium (~700 LOC prompt) | Multi-stage spec pipeline (5 prompts) |
| R-17 | medium (~350 LOC) | QA orchestrator agentic + sentinel override |
| R-24 | medium (~400 LOC) | Filesystem-canon skill store |
| R-31 | medium (~250 LOC) | Phase M runner (Komissar Naikan + heartbeat) |
| R-32 | medium (~400 markdown) | `knowledge/anti-patterns/` directory + 3 stubs |
| R-33 | medium (~250 LOC prompt) | `code-review.md` prompt lift from Aperant |

### Wave 4 — DEFER until specific milestones (7 R-Ns)

🇷🇺 Tracked но не landit без trigger.

| R-N | Blocker / trigger |
|-----|-------------------|
| R-11 (bi-temporal KG) | Current `knowledge/` layer hits scaling limits |
| R-12 (sleep consolidation) | Phase M maturity + R-1 stable |
| R-15 (full audit Python tool) | Prompt-workflow becomes bottleneck |
| R-35 (triage engine) | GitHub workflow capability added к FA |
| R-36 (semantic merge) | Multi-agent worktree parallelism (far horizon) |
| R-37 (CI hardening) | Optional dependencies (ctags / FTS5) cause silent rot |
| R-38 (multi-model ensembling) | UC5d eval-harness ships |
| R-39 (verifier-based selection) | UC5 + R-38 |
| R-40 (worker-thread isolation) | Corruption-risk materializes |

---

## 6. Anti-patterns consolidated (DON'T-COPY list)

🇷🇺 Lessons from removed / abandoned subsystems across all source-нот.
Используются как basis для AGENTS.md citation rules (R-26..R-32 в §0)
и для §7 Out of Scope.

### 6.1 Cron / background self-modification без external fitness

- **Manifested in:** DPC evolution worker (ADR-015), Kronos cron suite
  (4 cron jobs, R-6).
- **Evidence:** DPC — 20+ sessions × ~40 evolution proposals = 0
  valuable changes filtered through rule-set; subsystem removed
  (400 LOC + 7 tools). KAOS — заявленные benefits не materialized без
  fitness signal.
- **FA rule:** R-26 sub-1 cites ADR-015 verbatim в AGENTS.md.
- **Trigger for re-eval:** eval-harness operational + external fitness
  signal (BACKLOG I-7 / I-8).

### 6.2 Write-only subsystem без read-side consumer

- **Manifested in:** DPC «multiple ML write-only subsystems» (ADR-021
  Lesson 4), Aperant subsystem cleanup history.
- **Evidence:** subsystem writes to durable store, никто не читает; pure
  maintenance cost.
- **FA rule:** R-26 sub-3 cites ADR-021 verbatim в AGENTS.md.
- **Trigger for re-eval:** demonstrated read-side consumer materializes.

### 6.3 Hardcoded scope estimation в часах

- **Manifested in:** DPC S14 (Coder estimated 5-7h, took 11 min;
  27-38× error).
- **Evidence:** time-estimation by LLM is high-variance; lines/files
  estimation has lower variance and is auditable.
- **FA rule:** R-26 sub-2 cites ADR-005 P18 verbatim в AGENTS.md.

### 6.4 Prompt-diversity ensembling без verifier

- **Manifested in:** Correlated R-3 (P-3 §4.4 finding).
- **Evidence:** prompt-diversity ensemble не дают consistent gains, только
  sample-by-sample noise. Не пути к reliability.
- **FA rule:** R-27 sub-2 cites paper в AGENTS.md rule #10.

### 6.5 Brute-force retry-loop без circuit breaker

- **Manifested in:** Aperant `qa-loop.ts` (50-iteration brute force).
- **Evidence:** works но дорого по токенам. Aperant uses + escalates;
  better to use R-2 + R-34 constants from day one.
- **FA rule:** R-2 LoopGuard middleware + R-34 constants.

### 6.6 «100% AI-driven» as design goal

- **Manifested in:** soviet-code anti-pattern catalog (через chat-cross-ref).
- **Evidence:** removes human-in-the-loop checkpoints прежде чем
  agent reliable enough; produces low-quality output cheap volume.
- **FA rule:** R-32 anti-pattern catalog as living document; first
  entry should be «100%-AI-driven workflows» с rationale.

### 6.7 ONNX as ML execution layer (over-engineered)

- **Manifested in:** DPC removed; Kronos has similar over-engineering risk.
- **Evidence:** ONNX is production-scale ML serving; FA scale doesn't
  warrant. Use simple Python implementations until ≥100k inferences/day.
- **FA rule:** §7 Out of Scope explicit mention.

### 6.8 `.env UV_EXTRA_INDEX_URL` для PyTorch

- **Manifested in:** DPC build issue (ADR-013 prior version).
- **Evidence:** mixing torch wheels via env-vars breaks reproducibility.
- **FA rule:** keep PyTorch out of FA dependency graph entirely (no Phase M
  PyTorch model adoption planned).

### 6.9 Hard 75% approval threshold

- **Manifested in:** DPC removed.
- **Evidence:** magic number; should be config-driven с justification.
- **FA rule:** all thresholds в HookRegistry guards должны быть config-driven
  per R-7 retry-budget invariant.

### 6.10 9 630-line monolithic service.py

- **Manifested in:** DPC pre-cleanup state.
- **Evidence:** unmaintainable; one PR change breaks 5 features.
- **FA rule:** AGENTS.md PR Checklist rule #3 уже enforces file-size tier
  limits (<2000 deep-dive, <1000 summary).

### 6.11 «We are NOT reinventing the wheel» as process pattern

- **Manifested in:** DPC process retrospective.
- **Evidence:** the phrase is used **after** wheel-reinvention already
  happened; psychological self-justification.
- **FA rule:** Prior-Art ADR rule (R-26 sub-4 = DPC AP8 → B-NEW-8) MUST be
  invoked **before** new ADR drafting starts, not after.

---

## 7. Out of scope (intentional skips with rationale)

🇷🇺 Items explicitly NOT в FA borrow roadmap, с rationale why.

### 7.1 Multi-agent / swarm infrastructure

- **From Kronos:** `swarm_store.py` (~600 LOC), `group_router.py`, Telegram
  multi-agent.
- **Why skip:** FA stays single-agent v0.x. Even though Kronos swarm is
  elegant (`BEGIN IMMEDIATE` SQLite arbitration without pub/sub), no FA
  use case demands it.
- **Re-eval trigger:** when FA needs concurrent multi-process agents
  (Phase M+ multi-process scope).

### 7.2 Vector DB как primary memory

- **From Kronos:** Qdrant + Mem0 integration, embeddings cache.
- **Why skip:** FA's FTS5 single-writer достаточно для current scale.
- **Re-eval trigger:** when knowledge layer exceeds ~10k chunks или
  RAG cosine-similarity demands semantic vectors.

### 7.3 P2P / federation transports

- **From DPC:** federation, P2P transport, protocol spec, voice, OAuth,
  bridges (UI-/Telegram-/Discord-specific).
- **Why skip:** FA is CLI for now; no federation needs.

### 7.4 Tauri / Svelte / Rust frontend UI

- **From Aperant:** `apps/desktop/src/renderer/`, `src-tauri/`, Svelte +
  Tauri stack.
- **Why skip:** FA stays CLI-only in 0.1

### 7.5 Browser-use агент

- **From YT-3 #17:** browser-use agent для CLI.
- **Why skip:** FA does not browse web in 0.1

### 7.6 Third-party memory-MCP servers

- **From YT-3 #16:** memory-MCP third-party services.
- **Why skip:** FA's stated design = filesystem-canon, no external service
  dependencies for memory layer. Re-eval if MCP gateway lands в FA later.

### 7.7 Aperant `apps/desktop/src/main/ai/memory/{graph,db,injection,...}`

- **Why skip:** V5 production memory stack; deep, requires SQLite-vectors;
  patterns already covered abstractly via R-8 / R-11 / R-12.
- **Re-eval trigger:** if R-11 (KG) is taken, deep-read these modules first.

### 7.8 Gortex `internal/{indexer,resolver,semantic,query}/`

- **Why skip:** graph build pipeline requires tree-sitter / LSP infra.
- **Re-eval trigger:** if FA adopts code-symbol graph beyond chunker
  pointers.


---

## 8. Deliverable / coverage checklist

🇷🇺 **Acceptance criteria для landing R-Ns** — checklist для каждого PR.

- [ ] **For each TAKE R-N**, PR description cites: (a) source note path + §
      from §0 «Source(s)»; (b) wave from §5; (c) expected LOC delta.
- [ ] **For Wave 0 docs-only PRs**, cite §6 Anti-Patterns row when the
      change adds a citation (e.g., R-26 sub-1 cites §6.1).
- [ ] **For each landed R-N**, update этой ноты §3 Master mapping table —
      row status `pending` → `landed YYYY-MM-DD blob-URL`.
- [ ] **No supersession of source notes** — they remain `Status: active`.
- [ ] **§5 Wave order respected** — Wave 2 PRs cite R-1 as merged
      blocker resolved.
- [ ] **AGENTS.md PR Checklist** rule #10 (harness components: 4-question
      minimalism-first test) — every component R-N (R-1, R-2, R-3, R-4,
      R-5, R-6, R-13, R-17, R-20, R-22, R-24) MUST include answers.
- [ ] **AGENTS.md PR Checklist** rule #11 (≤100k tokens context per LLM
      call) — applicable to R-10 / R-16 / R-17 / R-33 (prompt-heavy items).
      Cite expected p90 input-token shape.

---

## 9. One-sentence summaries (для HANDOFF / DIGEST cross-ref)

🇷🇺 Каждый R-N в одну строку, для quick-grep / HANDOFF.md reference.

```text
R-1  HookRegistry + 2-tier middleware substrate (ADR-8 new); unblocks 5 downstream R-Ns.
R-2  LoopGuard middleware (Kronos R-3 + Aperant simpleHash); CIRCUIT_BREAKER on 3-strike thrash.
R-3  Failure classifier + RecoveryAction dispatcher (YT-1 tripartite + Aperant 7-cat extension).
R-4  Pre-tool blocker middleware (YT-4 #20 generalized to 6 blocker classes).
R-5  Deterministic State Verification (DSV) post-tool gate; YAML schema; zero LLM calls.
R-6  attempt_history.json writer + coder-recovery.md reader prompt (Aperant pair).
R-7  Retry-budget invariant + intra-role T=1.0 (Correlated R-7 + R-8 + YT-4 #21).
R-8  record_gotcha + record_discovery filesystem-canon learning loop (Aperant 1+2).
R-9  Identity-preserving compaction prompt fragment for HANDOFF.md (Kronos R-5).
R-10 Post-session insight extractor with Zod schema + 15k-char diff cap (Aperant 11).
R-11 Bi-temporal Knowledge Graph + GraphBackend ABC (DPC R-2); DEFER until scaling needs.
R-12 Sleep consolidation + _meta.json access registry (DPC R-3); DEFER pair с R-1.
R-13 Tokens classifier + buildSuggestions output + discover (Gortex audit subset).
R-14 Workspace resolution rule: no walk-up; explicit marker file (Gortex O).
R-15 Full bloat/staleness audit Python tool (Gortex R-1); DEFER, prompt version exists.
R-16 Multi-stage spec pipeline + mandatory write-tool gate (Aperant 15 + soviet B-NEW-2).
R-17 QA orchestrator agentic + filesystem-sentinel override (Aperant 16).
R-18 Per-tier tool-shape registry + role-switch handoff rule (YT-1 #7 + #8).
R-19 Eval-role provider/family disjointness + regex slug extractor (Correlated R-1).
R-20 Bash sandbox upgrade — denylist + validators + path-containment + pattern classifier.
R-21 Five-flag capability opt-in model + declarative tool whitelist (Kronos + soviet).
R-22 PII redaction recursive walker (Kronos pii.py); DEFER pairs с R-12.
R-23 Sub-agent execution rules: generateText not stream + remove SpawnSubagent.
R-24 Filesystem-canonical skill store + safe community import (Kronos R-4; 3-project).
R-25 Pause-file filesystem sentinel pattern (Aperant 9).
R-26 DPC-derived AGENTS.md citation cluster (4 sub-items: ADR-015 / 005 / 021 / AP8).
R-27 Correlated-derived AGENTS.md / ADR-2 citations (2 sub-items: P-2/P-3 + diversity-AP).
R-28 Intra-role retry T=1.0 default (Correlated R-8).
R-29 LLM-using hooks MUST use family ≠ acting-role (Correlated R-9; ADR-7 future amendment).
R-30 max_iterations cap = 6 empirical anchor (YT-4 #21).
R-31 Phase M runner with Komissar Naikan + heartbeat tick (soviet B-NEW-3).
R-32 Anti-pattern catalog as living document (soviet B-NEW-4); first 3 stubs.
R-33 pr_orchestrator + pr_followup template lift (Aperant 3); DEFER Phase M+.
R-34 QA loop circuit-breaker constants (Aperant 5 partial; constants only).
R-35 Triage engine pattern with Zod (Aperant 4); DEFER GitHub workflow scope.
R-36 Semantic merge analyzer regex-by-extension (Aperant 14); DEFER multi-agent.
R-37 CI workflow hardening: SHA-pin actions + build-tag matrix (Gortex P); DEFER.
R-38 Multi-model ensembling with diversity-based selector (Correlated R-4); UC5 candidate.
R-39 Verifier-based selection > majority-vote (Correlated R-5); UC5 candidate.
R-40 Worker-thread isolation между phases (Aperant 12); DEFER multi-process.
REF-1 Aperant subtask-iterator (528 LOC) — REFERENCE-only pre-read.
```

---

## 10. Open questions for user

🇷🇺 Questions surfaced during writing этой ноты. Each marked Q-N for
later answer-tracking.

### Q-1: Wave 3 R-31 Phase M runner timing — нужен ли отдельный ADR прежде R-1 HookRegistry, или после?

🇷🇺 R-1 lands HookRegistry substrate; R-31 Phase M runner — это
overarching loop orchestrator. Options:

- (a) Phase M runner ADR прежде R-1 → R-1 уточняет HookRegistry contract
  под Phase M runner requirements (preferred — top-down design).
- (b) R-1 first → Phase M runner ADR строит на top — bottom-up, может
  потребовать R-1 amendments.

🇷🇺 **Моё рекомендация:** (a) top-down — Phase M runner ADR sketch первым
(может быть скетч, не full ADR), затем R-1 уточняет hook contract.

### Q-2: Russian companion (`.ru.md`) этой ноты — нужно?

🇷🇺 По твоему предыдущему сигналу «без ру версии, ты быстрее» — этот
файл primarily Russian. Но AGENTS.md явно говорит «keep protocol names
+ identifiers in source language» — что и сделано. Должна ли быть
парная English-prose version?

🇷🇺 **Моё рекомендация:** **нет** — текущая нота already bilingual
(Russian prose + English identifiers). Парный full-English files become
maintenance burden; single bilingual is FA-idiom for research notes.

### Q-3: BACKLOG.md update — частью какого PR?

🇷🇺 По твоему ответу — «BACKLOG.md update только мастер-нота» = эта нота
**не** добавляет I-10..I-25 rows в BACKLOG.md. Но три R-N явно ссылаются
на BACKLOG slots:

- R-23 prep notes идут в существующий BACKLOG I-2 entry (sub-agent dispatch).
- R-38 wants BACKLOG I-10 placeholder (multi-model ensembling).
- R-15 already noted (full audit Python tool) — нет существующего BACKLOG row.

🇷🇺 **Моё рекомендация:** не trogать BACKLOG.md в текущем мерже этой ноты.
Когда конкретный R-N landит, его PR может добавить single BACKLOG row at that point.

### Q-4: §6.4 «prompt-diversity layer» anti-pattern — формулировка?

🇷🇺 R-27 sub-2 хочет добавить «prompt-diversity layer» как anti-pattern
citation в AGENTS.md rule #10. Точная формулировка важна. Я предложу:

```text
**Anti-pattern: prompt-diversity layer.** Adding N prompts с разной
формулировкой как «cheap ensembling» не даёт consistent gains; P-3 §4.4
shows sample-by-sample noise, no improvement on aggregate metrics. If
ensembling is needed, use cross-family model diversity (R-19) instead.
```

🇷🇺 **Question:** OK с такой формулировкой или нужно tighter / looser?

### Q-5: R-31 Phase M runner — landing strategy?

🇷🇺 R-31 (Phase M runner с Komissar Naikan + heartbeat) — самый
архитектурно-сложный single R-N после R-1. Option matrix:

- (a) Sketch ADR first, защититься 1-2 sessions feedback, затем impl.
- (b) Skip ADR, прямой impl prototype + retroактивная ADR documentation.
- (c) Mark Phase M runner as research-needed → new research-briefing
  session prior до impl.

🇷🇺 **Моё рекомендация:** (a) — sketch ADR (~1-2h) для feedback first.

### Q-6: R-32 anti-pattern catalog — какие первые 3 entries?

🇷🇺 R-32 хочет создать `knowledge/anti-patterns/` directory. Я
рекомендую первые 3 stubs based on §6:

1. `100-percent-ai-driven.md` (§6.6 soviet-code source)
2. `evolution-worker-without-fitness.md` (§6.1 DPC ADR-015)
3. `write-only-subsystem.md` (§6.2 DPC ADR-021)

🇷🇺 **Question:** OK с этими тремя, или хочешь другую initial set?

### Q-7: Master mapping table §3 — track `landed` status here, or separate file?

🇷🇺 Эта нота — work backlog. По мере landing R-Ns, я предлагаю обновлять
§3 column rightmost с `landed YYYY-MM-DD blob-URL`. Альтернатива — keep
ноту immutable + tracking файл (`borrow-roadmap-status.md`).

🇷🇺 **Моё рекомендация:** in-place update §3. Audit trail сохраняется
через git history.


---

## 11. Step-3 addendum — line-by-line borrow-list re-pass (gap-fill items)

🇷🇺 **Purpose:** второй проход по `borrow-list.md`. Найдено 7 missed items: 5 Gortex DEFER-кластер + 4 Kronos top-10. Добавлены как R-41..R-47 ниже + cross-referenced
обратно в §0 / §3 / §5.

### R-41 — Generated AGENTS.md / CLAUDE.md from chunker output (Gortex D+E+F+G+J+L bundle)

- **What:** unified config emission subsystem; FA generates **its own
  block** в AGENTS.md / CLAUDE.md / .cursor/rules / .cursorrules / etc.
  через marker fences (`<!-- fa:rules:start -->` ... `<!-- fa:rules:end -->`)
  + Adapter interface (`Detect / Plan / Apply` + `Mode = Project | Global`)
  + auto-generated «Codebase Overview» block synthesized from chunker
  output (entry points, top-10 referenced symbols, language breakdown).
- **Source(s):** Gortex `internal/agents/instructions.go` (576 LOC marker
  fences) + `internal/agents/agents.go` (182 LOC Adapter interface) +
  `internal/skills/generator.go` (298 LOC per-community SKILL.md emission)
  + `internal/agents/claudecode/adapter.go` (408 LOC reference adapter) +
  `internal/claudemd/generator.go` (142 LOC live-graph synthesis).
- **Project-axis fit:** (A) yes (single source of truth for multiple
  AGENTS.md / CLAUDE.md / etc.) — но only if FA ever has multiple targets.
  (B) yes (auto-generated codebase overview reduces stale rot).
- **Goal-lens fit:** (C) PARTIAL — currently FA emits только AGENTS.md
  from `knowledge/llms.txt`; no multi-target need yet.
- **Cost:** high (~1500 LOC bundle); должен landit как multi-PR series.
- **Verdict:** **DEFER** — multi-target need не materialized; current
  AGENTS.md hand-maintenance работает на FA scale.
- **Alternative-if-rejected:** continue hand-maintain AGENTS.md +
  `knowledge/llms.txt` regen via maintenance scripts.
- **Concrete first step (if TAKE later):** Read Gortex bundle в order
  `instructions.go` → `agents.go` → `claudecode/adapter.go`; map fields
  на FA's `knowledge/llms.txt` + AGENTS.md surface.
- **Trigger for re-eval:** FA emits configuration for ≥2 external agents
  (e.g. AGENTS.md + Cursor rules + Cline rules) OR `knowledge/llms.txt`
  drift becomes major maintenance burden.

### R-42 — SWE-bench-Lite eval harness template (Gortex H)

- **What:** full reproducible eval harness from Gortex `eval/` subtree:
  `agents/gortex_agent.py` + `prompts/{system,instance}_*.jinja` +
  `bridge/` + `environments/` + `analysis/`. Industry-standard SWE-bench-Lite
  evaluation methodology that **directly answers** «does the harness
  actually help?» — Pillar-1 (token/tool-call efficiency) measurement
  needs exactly this template.
- **Source(s):** Gortex `eval/` subtree, full directory.
- **Project-axis fit:** (A) yes (eval data informs noise-reduction
  decisions empirically). (B) yes (eval results = strong signal for
  context-finding rule tuning).
- **Goal-lens fit:** (C) yes if goal_lens = «provide empirical evidence
  for harness component decisions»; otherwise PARTIAL.
- **Cost:** medium-high (~600 LOC for FA equivalent + SWE-bench-Lite
  environment setup; Docker images).
- **Verdict:** **DEFER → UC5 candidate** — blocked on
  [BACKLOG I-7 / I-8 eval-harness items](../BACKLOG.md). Convergent с
  Aperant 16 QA orchestrator agentic (different eval domain — QA loop
  metrics vs end-to-end SWE-bench).
- **Alternative-if-rejected:** continue qualitative «does harness feel
  good» evaluation through user sessions.
- **Concrete first step (if TAKE later):** Read Gortex `eval/README.md` +
  `eval/agents/gortex_agent.py`; map FA's harness call shape onto SWE-bench
  task envelope.
- **Trigger for re-eval:** UC5d (eval-driven iteration) landing.

### R-43 — Per-symbol feedback + frecency decay learning loop (Gortex N)

- **What:** tiny on-disk JSON store with per-symbol `{useful, not_useful,
  missing}` counters; `frecency` decay function combines recency +
  frequency with `AgentMode`-dependent half-lives; `combo` blends
  frecency + feedback + base rank into a single score used by
  `smart_context` / `winnow_symbols`. The agent's votes durably reshape
  future query results.
- **Source(s):** Gortex `internal/mcp/feedback.go` + `frecency.go` +
  `combo.go` (~450 LOC total).
- **Project-axis fit:** (A) yes (cheap signals shape future context
  selection without bloating session-start). (B) yes (best signal
  reused → relevant context more likely surfaced next time).
- **Goal-lens fit:** (C) yes for FA's Exploration DAG → retrieval-ranking
  closing-the-loop story; currently FA tracks rejected paths but doesn't
  feed back into retrieval.
- **Cost:** medium (~200 LOC FA port; filesystem-canonical JSON store,
  no DB needed).
- **Verdict:** **DEFER** — pairs с R-10 (insight extractor) и R-24
  (filesystem-canon skills); landit после R-10 maturity.
- **Alternative-if-rejected:** continue R-10 insight-extraction without
  per-symbol feedback ranking.
- **Concrete first step (if TAKE later):** Read Gortex `frecency.go` (~150
  LOC, especially the half-life formula); design FA's JSON store schema
  для per-symbol counters в `knowledge/trace/feedback.json`.
- **Trigger for re-eval:** R-10 (insight extractor) landed + at least 5
  sessions of accumulated data.
- **Convergence:** related shape к R-12 sleep consolidation (`_meta.json`
  access counts) — both filesystem-canon counter stores. Could merge if
  scope creates conflict.

### R-44 — FTS5 Ebbinghaus tiering for knowledge layer (Kronos memory/fts.py + hybrid.py)

- **What:** two bundled improvements к existing FA FTS5 layer: (1) explicit
  `relevance` + `tier` (active/warm/cold/archive) + `last_accessed` columns
  с Ebbinghaus decay formula so «Wiki gets too big» problem is solved by
  tier-shifting не deletion; (2) hybrid search — score normalization +
  MMR re-ranking + temporal decay across vector and keyword channels.
- **Source(s):** Kronos `kronos/memory/fts.py` (306 LOC, especially
  Ebbinghaus formula at lines 122-148) + `kronos/memory/hybrid.py` (188
  LOC, hybrid search done right).
- **Project-axis fit:** (A) yes (tiering keeps cold facts out of context
  budget; hybrid re-ranking surfaces freshest most-relevant). (B) yes
  (decay surfaces fresh facts).
- **Goal-lens fit:** (C) yes if goal_lens = «scale knowledge layer past
  current size limits»; PARTIAL otherwise (current FA FTS5 layer работает
  без tiering).
- **Cost:** medium-high (~500 LOC port; tier columns + decay schedule +
  MMR re-ranking + temporal decay function).
- **Verdict:** **DEFER** — relevant когда ADR-3 v0.2 volatile-store hooks
  land + `knowledge/` corpus crosses 10k chunks scale; below that point
  current FTS5 single-writer достаточно.
- **Alternative-if-rejected:** continue current FTS5 layer без tiering /
  без hybrid re-ranking.
- **Concrete first step (if TAKE later):** Read `kronos/memory/fts.py:1-148`
  (especially Ebbinghaus formula) + `kronos/memory/hybrid.py:1-188`.
- **Trigger for re-eval:** `knowledge/` corpus crosses ~10k chunks OR
  cosine-similarity rerank demand materializes.

### R-45 — Cost guardian (Kronos cost_guardian.py)

- **What:** daily / session $ budget guardian; tracks spend per-session
  + per-day, aborts further LLM calls если budget exceeded; integration
  с retry-budget invariant (R-7).
- **Source(s):** Kronos `kronos/security/cost_guardian.py` (91 LOC).
- **Project-axis fit:** (A) no (runtime). (B) PARTIAL (budget-exceeded
  signal becomes context for the next turn).
- **Goal-lens fit:** (C) yes — pillar-1 (token efficiency) literally
  measures $ cost; explicit budget enforcement is principled mitigation.
- **Cost:** cheap (~100 LOC port + ADR-7 §5 amendment) — fits into
  HookRegistry as GuardMiddleware subclass (similar к R-2 LoopGuard
  shape).
- **Verdict:** **TAKE (Wave 2)** — landит после R-1 HookRegistry; pair
  с R-2 LoopGuard + R-7 retry-budget invariant как third guard в budget
  cluster.
- **Alternative-if-rejected:** rely on per-call max_tokens + manual
  session limit; no automatic abort на $ budget exceed.
- **Concrete first step (if TAKE):** Read `kronos/security/cost_guardian.py`
  (91 LOC); design FA's `BudgetGuard` middleware с `DAILY_BUDGET_USD` +
  `SESSION_BUDGET_USD` config constants.

### R-46 — Input shield / prompt-injection filter (Kronos shield.py)

- **What:** input sanitization layer + prompt-injection detection +
  jailbreak pattern filtering. Adjacent к PII redaction (R-22) but
  on **input** path не output path.
- **Source(s):** Kronos `kronos/security/shield.py` (205 LOC).
- **Project-axis fit:** (A) PARTIAL (input sanitization is preventive
  not session-start noise). (B) no.
- **Goal-lens fit:** (C) PARTIAL — FA's single-user CLI scope makes
  prompt-injection less relevant than for multi-user services; защита
  всё ещё ценна если FA reads untrusted GitHub PR content или web pages.
- **Cost:** medium (~250 LOC port + integration с HookRegistry as
  GuardMiddleware на `PRE_USER_INPUT` lifecycle hook).
- **Verdict:** **DEFER** — single-user CLI scope reduces immediate need;
  re-evaluate когда FA processes untrusted external content (GitHub
  PR content review, web-scraped data).
- **Alternative-if-rejected:** rely on trust в user's input + LLM
  provider's own injection defenses.
- **Concrete first step (if TAKE later):** Read `kronos/security/shield.py`
  full (205 LOC); identify which patterns are FA-relevant (skip
  multi-user-specific ones).
- **Trigger for re-eval:** FA processes untrusted external content
  routinely.
- **Convergence:** input-side counterpart к R-22 (PII redaction =
  output/audit-side). Together с R-47 (output validator) — 3-layer
  redaction/validation defense.

### R-47 — LLM-side output validator (Kronos output_validator.py)

- **What:** LLM-side post-output validation layer; complements deterministic
  R-5 DSV gate (which uses code parsing — zero LLM). Output validator
  uses Eval-tier LLM call to verify «does the agent's output match the
  task contract?» — for cases where deterministic verification cannot
  capture full semantics (e.g. «is this explanation accurate»).
- **Source(s):** Kronos `kronos/security/output_validator.py` (104 LOC).
- **Project-axis fit:** (A) no (runtime per-call). (B) PARTIAL — validation
  signal becomes part of failure-classification context.
- **Goal-lens fit:** (C) PARTIAL — FA's Eval-role (R-19) is the natural
  consumer; R-19 disjoint policy applies.
- **Cost:** cheap (~150 LOC FA port + Eval-tier prompt template).
- **Verdict:** **DEFER → Wave 3** — pair с R-19 Eval-disjoint + R-5 DSV.
  Stacking model: R-5 cheap deterministic first, R-47 expensive LLM
  validation second (only if R-5 passes but agent claims «I'm done»).
- **Alternative-if-rejected:** rely on R-5 DSV + user-visible output
  review only.
- **Concrete first step (if TAKE later):** Read `kronos/security/output_validator.py`
  (104 LOC); design FA's `output_validator` prompt template + Eval-tier
  invocation rule.
- **Convergence:** stacks с R-5 DSV. Could be split into separate ADR
  если scope grows beyond simple post-output validation.

### 11.1 Updated summary table (gap-fill items only)

🇷🇺 Прибавляем 7 новых R-N к §3 master mapping.

| R-N  | FA artifact (existing or new)                    | Wave                 | Source(s) — short                | LOC   |
| ---- | ------------------------------------------------ | -------------------- | -------------------------------- | ----- |
| R-41 | Multi-target config emission subsystem           | 4 (DEFER)            | Gortex D+E+F+G+J+L bundle        | ~1500 |
| R-42 | `eval/` SWE-bench-Lite harness                   | 4 (DEFER → UC5)      | Gortex H                         | ~600  |
| R-43 | `knowledge/trace/feedback.json` + frecency decay | 3 (DEFER pairs R-10) | Gortex N                         | ~200  |
| R-44 | FTS5 tier columns + Ebbinghaus + hybrid re-rank  | 4 (DEFER)            | Kronos memory/fts.py + hybrid.py | ~500  |
| R-45 | `BudgetGuard` middleware + ADR-7 §5 amendment    | 2                    | Kronos cost_guardian.py          | ~100  |
| R-46 | Input shield / prompt-injection filter           | 4 (DEFER)            | Kronos shield.py                 | ~250  |
| R-47 | LLM-side output validator                        | 3                    | Kronos output_validator.py       | ~150  |

### 11.2 Updated counters

🇷🇺 После Step-3 re-pass: **42 → 49 R-N**.

- TAKE: 28 (was 28) + R-45 = 29
- DEFER: 9 (was 9) + R-41 + R-42 + R-43 + R-44 + R-46 + R-47 = 15
- REFERENCE-only: 1 (unchanged)
- **Total raw items mapped: 49  + 1 REF = 50 entries**.

### 11.3 Updated convergence map (additions)

🇷🇺 New convergent clusters surfaced в Step 3:

**3-layer redaction/validation defense (input + output + audit):**
- R-46 input shield (Kronos `shield.py`)
- R-47 LLM output validator (Kronos `output_validator.py`)
- R-22 PII redaction on audit write (Kronos `pii.py`)
- Plus R-5 DSV (zero-LLM verification) which is orthogonal но stacks.

**Budget + retry-budget cluster:**
- R-7 retry-budget invariant (config-bounded counters; Wave 0 ADR-7 amendment)
- R-2 LoopGuard middleware (CIRCUIT_BREAKER на thrash patterns)
- R-45 BudgetGuard (daily/session $ limits)
- All three are GuardMiddleware subclasses на HookRegistry (R-1).

**Filesystem-canon learning loop (3 layers):**
- R-8 record_gotcha + record_discovery (per-event Markdown / JSON; in-flight)
- R-10 insight extractor (post-session Zod schema; offline pass)
- R-43 per-symbol feedback + frecency (per-symbol counter; ongoing)
- All three filesystem-canon, no DB; different temporal granularities.

### 11.4 Action items resulting from Step-3 re-pass

🇷🇺 **Nothing requires immediate user attention.** Все 7 missed items —
DEFER или secondary tier (R-45 — single new TAKE Wave-2 item). Они дополняют
master backlog без перетряхивания primary roadmap.

- R-45 **TAKE Wave 2** добавляется в §5 execution order pairs с R-2.
- R-41 / R-42 / R-43 / R-44 / R-46 / R-47 — все DEFER, добавляются в
  Wave 4 «DEFER» bucket.

### 11.5 Coverage final check

Confirmed coverage check после Step-3:
**100% coverage confirmed.**

| Borrow-list section                   | Items raw                              | Coverage                                                                                                                                                                                                                                                                             |
| ------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Gortex (A..P, 16 items)               | 16                                     | A→R-15, B→R-13, C→R-13, **D→R-41**, **E→R-41**, **F→R-41**, **G→R-41**, **H→R-42**, I→R-1, **J→R-41**, K→R-13, **L→R-41**, M→R-20, **N→R-43**, O→R-14, P→R-37 — 16/16 ✓                                                                                                              |
| Aperant (1..16)                       | 16                                     | 1→R-8, 2→R-8, 3→R-33, 4→R-35, 5→R-34, 6→R-20, 7→R-23, 8→R-3+R-6, 9→R-25, 10→REF-1, 11→R-10, 12→R-40, 13→R-6, 14→R-36, 15→R-16, 16→R-17 — 16/16 ✓                                                                                                                                     |
| Correlated (R-1..R-9)                 | 8 (R-6 not used by user)               | R-1→R-19, R-2→R-27.1, R-3→R-27.2, R-4→R-38, R-5→R-39, R-7→R-7, R-8→R-28, R-9→R-29 — 8/8 ✓                                                                                                                                                                                            |
| DPC (reference base)                  | 6 + 4 soviet                           | R-1→R-1, R-2→R-11, R-3→R-12, R-4→R-26.1, R-5→R-26.2, R-6→R-26.3, soviet B-NEW-1..4→R-21+R-16+R-31+R-32 — 10/10 ✓                                                                                                                                                                     |
| YT (21 concepts, #12-17 out-of-scope) | 15 in-scope                            | #1→R-3, #2→R-17, #3→R-5 (gates), #4→R-26, #5→R-24+L0/L1/L2, #6→R-8, #7→R-18, #8→R-18, #9→R-12, #10→R-11, #11→AGENTS.md citation (cluster R-26), #18→R-5, #19→R-9 fallback, #20→R-4, #21→R-30 — 15/15 ✓                                                                               |
| Kronos (R-2..R-5 + top-10 table)      | R-2 + R-3 + R-4 + R-5 + top-10 #1..#10 | R-2 PII→R-22, R-2 FTS5→**R-44**, R-3→R-2, R-4→R-24, R-5→R-9; top-10: #1→**R-44**, #2→**R-44** (hybrid), #3→R-11, #4→S-1+§7.1, #5→§7.1, #6→R-24, #7→R-24, #8→R-21, #9: loop→R-2, shield→**R-46**, output_validator→**R-47**, cost_guardian→**R-45**, pii→R-22, #10→S-1+§7.1 — 10/10 ✓ |
