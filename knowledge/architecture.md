# Архитектура агента — ориентир для проектирования

> Справочный документ для research/design-фазы First-Agent. Описывает трёхслойную
> архитектуру LLM-агента, базовые паттерны и «чему учит опыт Agent». Русская часть —
> комментарий; структурные блоки намеренно оставлены двуязычными, чтобы удобно
> цитировать английские термины.

Источники: [Coding Agents 101](https://agent.ai/agents101) и
[docs.agent.ai](https://docs.agent.ai).

---

## Current implementation state (2026-05-29)

> The three-layer model below is the **conceptual** reference; this
> section maps it onto the **shipped** code as of M-1..M-8. For the
> authoritative per-module index see
> [`knowledge/llms.txt`](./llms.txt) §BY-DEMAND INDEX; for milestone
> status see [`knowledge/BACKLOG.md`](./BACKLOG.md) and
> [`HANDOFF.md`](../HANDOFF.md).

- **Instruction Layer →** `AGENTS.md` + ADRs + `knowledge/` (text
  half of NLAH); the coder system prompt + tool-spec projection are
  `src/fa/inner_loop/prompt.py` (A-bucket residue, ADR-10 I-2).
- **Execution Layer →** the inner loop is materialised:
  `src/fa/inner_loop/registry.py` (`ToolRegistry` / `ToolSpec`),
  `loop.py` (`run_session`), `coder_loop.py` (`drive_session`, the
  LLM-driven M-8 bridge), `state.py` (`events.jsonl`), and the hook
  pipeline `hooks/` (`HookRegistry`, `GuardMiddleware` /
  `ObserverMiddleware`, `SandboxHook`, `LoopGuard`, blockers,
  `IntentGuard`). Baseline tools: `fs.read_file` / `fs.write_file` /
  `fs.run_bash` + `pr.prepare`.
- **Integration Layer →** `src/fa/providers/` (ADR-9 provider chain,
  `UrllibTransport`), `src/fa/sandbox/` (ADR-6 bash gate), and the
  PR-intent enforcement loop (`src/fa/hygiene/pr_intent.py` git hook
  + `IntentGuard` middleware + `bash_intent.py` AST analyzer +
  `pr_draft.py` trusted draft store). Entry point: `fa run --task`.
- **Determinism discipline →** the five ADR-10 invariants (I-1..I-5)
  are the construction-discipline carriers; see
  [`project-overview.md` §1.2.5](./project-overview.md#125--compliance-by-construction-failure-observable).

The conceptual layers + patterns below remain the design rationale;
they predate the implementation and are kept as the «why».

---

## Трёхслойная модель агента

Любой автономный LLM-агент удобно раскладывать на три слоя. Они отвечают на разные
вопросы и проектируются в разном порядке: сначала **Instruction**, потом
**Execution**, в конце **Integration**.

### 1. Instruction Layer — что агент знает и как себя ведёт

```text
┌─────────────────────────────────────┐
│         Instruction Layer            │
│                                      │
│  System Prompt   — роль, возможности,│
│                    ограничения       │
│  Knowledge       — устойчивая память │
│                    (факты, правила)  │
│  Skills          — пошаговые         │
│                    процедуры в репо  │
│  Playbooks       — повторяемые       │
│                    шаблоны задач     │
└─────────────────────────────────────┘
```

Ключевые решения:

- Как агент получает и приоритизирует инструкции?
- Где хранится долговременная память и как она извлекается?
- Как запускаются процедуры/скиллы?

### 2. Execution Layer — чем агент физически пользуется

```text
┌─────────────────────────────────────┐
│          Execution Layer             │
│                                      │
│  Shell    — команды, сборка, тесты   │
│  IDE      — чтение/запись кода       │
│  Browser  — веб, тесты, research     │
│  Desktop  — GUI-проверка             │
└─────────────────────────────────────┘
```

Ключевые решения:

- Какой минимальный набор инструментов нужен?
- Как агент наблюдает за выводом инструментов и реагирует на ошибки?
- Каковы лимиты (время, токены, деньги)?

### 3. Integration Layer — что за пределами песочницы

```text
┌─────────────────────────────────────┐
│         Integration Layer            │
│                                      │
│  MCP        — внешние инструменты/БД │
│  Git/CI     — PR, ревью, пайплайны   │
│  Messaging  — Slack/Teams, алерты    │
└─────────────────────────────────────┘
```

Ключевые решения:

- К каким внешним системам подключаемся?
- Как управляется аутентификация и секреты?
- Что с лимитами/квотами?

---

## Базовые паттерны

### П1 — Feedback Loop (самый важный)

Агент работает хорошо, когда видит результат своих действий:

```text
Action → Observation → Reflection → Next Action
  │                                      │
  └──────────── Feedback Loop ───────────┘
```

Реализация на практике: тесты после правок, линтер, typechecker, запуск в
браузере/CLI. Именно обратная связь превращает «нестабильного джуна» в полезного
исполнителя.

### П2 — Планирование до исполнения

Для сложных задач:

1. Разобрать требования.
2. Пройтись по кодовой базе и собрать контекст.
3. Составить план (файлы, риски, тесты).
4. Исполнять по шагам, проверяя результат каждого шага.
5. Сдать итог.

### П3 — Эскалация

Агент должен уметь различать три режима:

```python
if task_is_clear:
    execute()
elif task_is_ambiguous:
    ask_clarifying_questions()
    then_execute()
elif task_exceeds_capability:
    report_blockers()
    suggest_alternatives()
```

### П4 — Накопление знаний

```text
Сессия 1: выяснили, что тестам нужен Docker
  → Knowledge: «Перед тестами поднимай docker-compose»

Сессия 2: знание подтянется автоматически
  → Docker стартует, тест проходит с первого раза
```

---

## Проектные соображения

### Выбор LLM

| Фактор | Что учитывать |
|---|---|
| Контекст | Чем больше — тем больше кода помещается в кадр |
| Качество кода | Проверять именно на вашем языке/фреймворке |
| Tool-use | Надёжность вызова инструментов в строгом формате |
| Следование инструкциям | Многошаговые процедуры без «забывания» |
| Цена vs качество | Баланс стоимости на токен и success rate |

### Дизайн инструментов

- Структурированный вывод (JSON/типизированный) — легче парсить LLM-у.
- Возвращать внятные ошибки — агенту есть от чего оттолкнуться.
- Один инструмент — одна ответственность.
- Инструменты должны быть композируемы.

### Архитектура памяти

| Тип | Назначение | Пример | CogSci-аналог |
|---|---|---|---|
| Session memory | Контекст одной задачи | Содержимое файлов, прошлые команды | working |
| Persistent knowledge | Факты между сессиями | «Используем pnpm, не npm» | semantic |
| Procedural memory | Пошаговые процедуры | `SKILL.md` | procedural |
| Episodic memory | Итоги прошлых сессий | Session Insights / логи | episodic |

Маппинг на CogSci-таксономию (Tulving 1972, Atkinson–Shiffrin) —
не переименование, а общий язык для будущих ADR'ов. Подробнее о том,
почему это важно для **памяти агента** (а не вики для человека),
— в [`knowledge/research/llm-wiki-critique-first-agent.md`](./research/llm-wiki-critique-first-agent.md).

#### Provenance и chain of custody

Любой факт в `Persistent knowledge`, который LLM *сам написал* (а не
скопировал из первоисточника), должен знать:

- **source** — на что он опирается (URL, путь в репо, номер коммита);
- **chain_of_custody** — где искать первоисточник, если нужно точное
  значение (конкретная цифра, дата, имя);
- **superseded_by** — куда идти, если заметка заменена.

Без этих трёх полей LLM-написанная summary начинает конкурировать с
первоисточником и со временем *замещает* его для retrieval'а — даже если
сам файл-источник всё ещё лежит в репо. См. детальный разбор эффекта и
template frontmatter'а в [`llm-wiki-critique.md`](../knowledge/research/llm-wiki-critique.md).

#### Стабильное vs volatile знание

Разные типы знания требуют разной политики синтеза:

| Тип | Где лежит | Политика |
|---|---|---|
| Стабильное (архитектура, ADR, глоссарий) | `knowledge/adr/`, `knowledge/` | Синтезируется один раз при ревью, редко меняется, можно цитировать из summary |
| Semi-stable (research notes) | `knowledge/research/` | Обновляется при significant findings, frontmatter-provenance обязательно |
| Volatile (логи сессий, session-digest'ы) | (пока не заведено) | Синтезировать только при необходимости, не индексировать как источник |

Конкретные числа, даты, решения — *всегда* сверяем с первоисточником, не
цитируем из summary-заметки. Это правило вынесено в routing-секцию
[`AGENTS.md`](../AGENTS.md).

### Восстановление после ошибок

Агент должен справляться с:

1. Отказами инструментов — retry c бэкоффом, альтернативный путь.
2. Ошибками LLM — неверный JSON, галлюцинированный вызов.
3. Средой — нет зависимостей, нет сети.
4. Неопределённой задачей — спросить, а не угадывать.

---

## Чему учит экосистема Agent

### Что работает

1. Типизированные языки (TypeScript, typed Python).
2. Крепкие тестовые сьюты — агент сам себя чинит.
3. Понятная структура проекта (`AGENTS.md`, `SKILL.md`) — меньше времени на разведку.
4. Небольшие фокусные задачи.
5. Preview-деплой — мгновенная визуальная проверка.

### Что пока работает плохо

1. Сложный многошаговый дебаг.
2. Пиксельная точность в UI.
3. Задачи без чётких критериев завершения.
4. Прод-доступ — держите агента в dev/staging.

### Правило 80%

Реалистично ждать ~80% экономии времени, не 100% автоматизации. Архитектурные
решения, security, финальное QA и edge-cases — всё ещё за человеком.

---

## Что из этого тащим в First-Agent

- Чёткое разделение на три слоя (и принятые решения фиксируем ADR'ами
  в [`knowledge/adr/`](../knowledge/adr/)).
- Фидбек-луп как первоклассное требование к среде: линтер + typecheck + тесты
  должны существовать раньше, чем первый модуль (см. *Phase R / S / M* в [`glossary.md`](./glossary.md), фаза S).
- Память делим на три вида: контекст сессии, долговременные заметки,
  процедуры. Что именно используем — решаем в ADR.
- Инструменты проектируем композируемыми и со структурированным выводом.
