# First-Agent

Репозиторий, в котором я собираю **собственного LLM-агента** вместе с devin.ai).

> **Статус:** Разработка deterministic harness ADR-10, подведение к релизу F-A 0.1.
---

## 1. Зачем это

**First-Agent** — research-backed implementation-first проект, стремящийся
стать open-source reference implementation для locally orchestrated coding
agents. Помимо самого факта построения работающего harness, проект ставит
4 явных цели (полная формулировка —
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)):

1. Пройти весь путь от формулировки до working prototype, документируя
   каждое архитектурное решение через ADR + research note. Ригор делает
   репо одновременно учебным инструментом и forkable reference.
2. Выпустить v0.1 как pragmatic single-user product под UC1 (coding+PR) +
   UC3 (local-docs-to-wiki) с hybrid-shape (filesystem-canon + lazy
   search-side scaling).
3. Построить **наиболее token- и tool-call-efficient harness** среди
   известных open-source / open-design агент-стэков под целевые UC1+UC3
   при single-user single-workstation use. KPI-числа фиксируются после
   landing UC5 (eval-harness) и первого baseline-run; до того стоят
   как `TBD`.
4. **Iteration via measurement.** База в v0.1 — способность агента писать
   собственные skills (`SKILL.md`-файлы) по итогам решённых задач и
   найденных улучшений. UC5 (post-v0.1) расширяется до eval-driven
   harness iteration.

**Принцип построения — minimalism-first.** Не «вырезать лишнее потом», а
не добавлять без research-evidence или измеренного KPI-impact. Подробнее:
[`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first).

Опора — research papers (Tsinghua module-ablation `arXiv:2603.25723`,
Stanford / Khattab Meta-Harness `arXiv:2603.28052v1`, Anthropic engineering
posts), MCP-экосистема, и Devin / Claude Code / OSS repo's как reference-агенты.

---

## 2. Scope — что входит и что не входит

Полная версия — в
[`knowledge/project-overview.md`](./knowledge/project-overview.md) §4–§5.
Краткая выжимка:

### В scope (v0.1)

- **UC1** — coding + PR-write end-to-end (FA + 1–2 controlled-list
  репозитория пользователя).
- **UC3** — local-docs-to-wiki (`fa ingest <path-or-url>`,
  chunk-aware retrieval, Q&A).
- Static role-routing LLM tiering (Planner / Coder / Debug),
  mechanical-wiki memory (no embeddings/graph в v0.1), SQLite FTS5
  индекс, sandbox + path allow-list для тулов.

### Вне scope (v0.1)

- **UC2** continuous multi-source research — best-effort.
- **UC4** multi-user Telegram chat — deferred.
- **UC5** semi-autonomous multi-LLM research/experiment — deferred
  (см. [ADR-1 Amendment 2026-05-01](./knowledge/adr/ADR-1-v01-use-case-scope.md)).
- Production-деплой, мульти-тенантность, биллинг, собственный веб-UI,
  обучение/дообучение моделей, агент-общего-назначения «на всё».

---

## 3. Как работать с этим репо

Полный inventory всех документов — в
[`knowledge/llms.txt`](./knowledge/llms.txt) (one-fetch индекс,
[llmstxt.org](https://llmstxt.org/) convention). Конвенции по
структуре и работе — в [`AGENTS.md`](./AGENTS.md).

Для нового человека / агента:

1. Прочитать [`AGENTS.md`](./AGENTS.md) — repo conventions, query routing.
2. Прочитать [`knowledge/llms.txt`](./knowledge/llms.txt) — карта
   репо в одном fetch'е.
3. Просмотреть [`knowledge/project-overview.md`](./knowledge/project-overview.md)
   — что v0.1 ships и что non-goal.
4. Просмотреть индекс ADR — [`knowledge/adr/README.md`](./knowledge/adr/README.md).
5. Проверить [`HANDOFF.md`](./HANDOFF.md) — текущий snapshot
   состояния репо для cross-LLM сессий.

Дальше — по необходимости (ADR / research-нота / промпт). Не нужно
загружать всё в контекст сразу; routing-table в
[`AGENTS.md` §Query Routing](./AGENTS.md#query-routing).

---

## 4. Основные файлы

- [`AGENTS.md`](./AGENTS.md) — конвенции и инструкции для AI-агентов.
- [`HANDOFF.md`](./HANDOFF.md) — snapshot состояния для cross-LLM сессий.
- [`docs/README.md`](./docs/README.md) — вики по работе с Devin.
- [`knowledge/README.md`](./knowledge/README.md) — как устроена память
  проекта (frontmatter schema, конвенции, supersession-rule).
- [`knowledge/llms.txt`](./knowledge/llms.txt) — one-fetch индекс
  всех документов.
- [`knowledge/adr/README.md`](./knowledge/adr/README.md) — индекс ADR.
---
