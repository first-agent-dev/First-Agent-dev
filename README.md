# First-Agent

Репозиторий, в котором я собираю **собственного LLM-агента** вместе с
[devin.ai](https://devin.ai). Этот README — единый ориентир: что за проект, где
он сейчас и куда движется.

> **Статус:** `scaffolding complete + Wave-0/Wave-1 docs slate landed → Phase M inner-loop scaffolding (BACKLOG M-1) next`.
> Feedback-loop поднят; ADR-7/ADR-8 contracts заморожены; следующий PR — Phase-M inner-loop runtime (`src/fa/inner_loop/`)
> + первый feature module (chunker для Mechanical Wiki / brain v0.1).

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
posts), MCP-экосистема, и Devin / Claude Code как reference-агенты:

- [When to use Devin](https://docs.devin.ai/essential-guidelines/when-to-use-devin)
- [Coding Agents 101](https://devin.ai/agents101)
- [docs.devin.ai](https://docs.devin.ai)

---

## 2. Текущее состояние

- [x] Репозиторий создан.
- [x] Базовая вики про работу с Devin собрана (см. [`docs/`](./docs/README.md)).
- [x] Слот под долговременную память (ADR, промпты, обзор) создан
      ([`knowledge/`](./knowledge/README.md)).
- [x] Заполнено видение проекта
      ([`knowledge/project-overview.md`](./knowledge/project-overview.md)).
- [x] Проведено исследование по ключевым развилкам — итог в
      [`knowledge/llms.txt`](./knowledge/llms.txt) (флэт-индекс всех
      артефактов) и в [`knowledge/research/`](./knowledge/research/).
- [x] Приняты **ADR-1..ADR-8** (см.
      [`knowledge/adr/README.md`](./knowledge/adr/README.md));
      [ADR-7](./knowledge/adr/ADR-7-inner-loop-tool-registry.md)
      фиксирует inner-loop / tool-registry contract,
      [ADR-8](./knowledge/adr/ADR-8-hook-registry.md) добавляет
      HookRegistry middleware-chain (doc-first; runtime
      tracked в [BACKLOG M-1](./knowledge/BACKLOG.md#m-1--inner-loop-scaffolding--hookregistry-runtime)).
- [x] Поднят тулинг (lint/types/tests/CI/pre-commit, `Makefile`).
- [x] Зафиксирована convention для stacked / sequenced PR'ов
      ([`AGENTS.md` §Stacked / sequenced PRs](./AGENTS.md#stacked--sequenced-prs)).
- [x] Wave-0 (borrow-roadmap) landed 2026-05-20 (PR
      [#18](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/18)):
      ADR-7 / ADR-2 amendments, AGENTS.md cluster, handoff-summarizer
      prompt, glossary, и три inert Python модуля
      ([`fa.verifier`](./src/fa/verifier/),
      [`fa.tools`](./src/fa/tools/),
      [`fa.hygiene`](./src/fa/hygiene/)) с unit-test suite.
      Inert = не вызываются до Phase-M (M-1).
- [x] Wave-1 docs+code (borrow-roadmap) landed 2026-05-20 (PR
      [#19](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/19)):
      [ADR-8](./knowledge/adr/ADR-8-hook-registry.md) HookRegistry
      doc-first, ADR-2 / ADR-6 amendments, capability-flag parser
      ([`fa.config`](./src/fa/config.py)), pause-file sentinel
      ([`fa.orchestration.pause`](./src/fa/orchestration/pause.py)),
      per-tier tool-shape registry
      ([`knowledge/prompts/tool-shapes.yaml`](./knowledge/prompts/tool-shapes.yaml)).
- [x] Wave-1 R-20 bash sandbox gate landed 2026-05-20 (PR
      [#20](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/20)):
      3-layer pipeline в [`fa.sandbox`](./src/fa/sandbox/) —
      classifier + per-command validators + symlink-resolved path
      containment. Port из Aperant TS + Gortex Go. Wiring в
      inner-loop `run_shell` отложен до BACKLOG M-1.
- [ ] Написан первый модуль (chunker для Mechanical Wiki) —
      разблокируется после Phase-M inner-loop scaffolding
      (BACKLOG M-1).

Нулевое, но важное: первый feature-модуль пишем только после feedback-loop.
Этот gate закрыт; следующий шаг — **Phase-M inner-loop scaffolding**
([BACKLOG M-1](./knowledge/BACKLOG.md#m-1--inner-loop-scaffolding--hookregistry-runtime))
— материализация ADR-7 / ADR-8 контрактов как `src/fa/inner_loop/`
(registry + loop + hooks). После M-1 разблокируется первый feature-модуль
(chunker), Wave-2 R-N's (`LoopGuard`, failure-classifier, pre-tool blocker,
PII walker), и wiring уже стоящих inert модулей
([`fa.sandbox.bash_gate`](./src/fa/sandbox/),
[`fa.config.load_capabilities`](./src/fa/config.py),
[`fa.orchestration.pause`](./src/fa/orchestration/pause.py),
[`fa.verifier.verify_action`](./src/fa/verifier/)) в hook chain.

---

## 3. Scope — что входит и что не входит

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

## 4. После scaffolding'а — первый модуль

Подробнее в [`docs/workflow.md`](./docs/workflow.md). Коротко:

1. **Scaffolding.** `pyproject.toml`, `ruff` + `mypy` + `pytest`,
   CI на GitHub Actions, `Makefile`, `pre-commit` — сделано.
2. **Первый модуль.** Chunker для Mechanical Wiki:
   `src/fa/chunker/`, `Chunk` dataclass, `Chunker` Protocol,
   `CompositeChunker`, `universal-ctags` для кода и `markdown-it-py`
   для Markdown / plain text. Ручная проверка: `fa chunk <path>`.
   Контракт — в
   [ADR-5](./knowledge/adr/ADR-5-chunker-tool.md);
   sample-tests — в
   [`knowledge/research/chunker-design.md` §8](./knowledge/research/chunker-design.md#8-sample-test-plan-pre-implementation).
3. **Далее — итеративно.** Каждый модуль = отдельный PR. Каждое
   значимое решение = ADR.

---

## 5. Как работать с этим репо

Полный inventory всех документов — в
[`knowledge/llms.txt`](./knowledge/llms.txt) (one-fetch индекс,
[llmstxt.org](https://llmstxt.org/) convention). Конвенции по
структуре и работе — в [`AGENTS.md`](./AGENTS.md).

Для нового человека / агента:

1. Прочитать [`AGENTS.md`](./AGENTS.md) — repo conventions, PR
   checklist, query routing.
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

## 6. Полезные ссылки

**Официальные:**

- [docs.devin.ai](https://docs.devin.ai)
- [When to use Devin](https://docs.devin.ai/essential-guidelines/when-to-use-devin)
- [Coding Agents 101](https://devin.ai/agents101)

**Внутри репо:**

- [`AGENTS.md`](./AGENTS.md) — конвенции и инструкции для AI-агентов.
- [`HANDOFF.md`](./HANDOFF.md) — snapshot состояния для cross-LLM сессий.
- [`docs/README.md`](./docs/README.md) — вики по работе с Devin.
- [`knowledge/README.md`](./knowledge/README.md) — как устроена память
  проекта (frontmatter schema, конвенции, supersession-rule).
- [`knowledge/llms.txt`](./knowledge/llms.txt) — one-fetch индекс
  всех документов.
- [`knowledge/adr/README.md`](./knowledge/adr/README.md) — индекс ADR.

---

*Статус документа — living. Правится по мере изменения состояния
репо; последняя ревизия — 2026-05-20 (Wave-0 + Wave-1 docs slate;
см. git history).*
