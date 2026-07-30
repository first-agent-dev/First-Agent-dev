# G3 и G5: Детальный разбор с примерами

## G3: Spec-Code Drift Detection — почему я переоценил и как это реально работает

### Что я утверждал в v1

> «ADR — это спецификация. Код может отклониться от ADR. Нужен
> автоматический детектор расхождения (drift gate), который
> сравнивает код со спецификацией и падает, если они расходятся.»

Это звучит разумно, но содержит скрытую ошибку: **я перепутал
«документ с намерением» и «машинно-читаемую спецификацию».**

---

### Пример из реального мира: Spec Growth Engine

Статья Spec Growth Engine (июнь 2026) описывает систему, где
спецификация — это **машинно-читаемый граф**. Каждый узел графа
имеет две части:

```
Intent Graph (что должно быть)          Evidence Graph (что реализовано)
┌─────────────────────┐                ┌─────────────────────┐
│ Node: UserService    │                │ Node: UserService    │
│ contract:            │                │ contract:            │
│   GET /users → 200   │    diff?       │   GET /users → 200   │
│   POST /users → 201  │ ──────────────→│   POST /users → 201  │
│ design:              │                │ design:              │
│   pagination: cursor │                │   pagination: offset │ ← DRIFT
│   auth: required     │                │   auth: required     │
└─────────────────────┘                └─────────────────────┘
```

Каждое поле в спецификации — структурированные данные с типами.
Система может автоматически сравнить `Intent.pagination == "cursor"`
с `Evidence.pagination == "offset"` и сказать: **DRIFT DETECTED**.

Это работает потому, что **обе стороны — машины**.

---

### Что FA реально имеет: проза, а не граф

Вот реальный ADR-11 (я читал файл). Он написан на английском
прозой:

```markdown
### Threat model: LLM as Untrusted Compiler

The LLM author is an untrusted compiler that:
1. Receives intent (a natural-language task description).
2. Translates that intent into multi-file patches.
3. Can edit any file in the repository — including the guardrails themselves.
4. Can skip, weaken, or bypass validation in the same patch that introduces the violation.
```

И инварианты записаны как:

```markdown
| ADR-11-I1 | Level-0 kernel is frozen, stdlib-only |
| ADR-11-I5 | Test semantic decay lock               |
| ADR-11-I7 | Protected-path governance               |
```

Это **не** машинно-читаемый формат. Это проза для людей.

---

### Конкретный пример: что означает «drift» для FA

Представим, что LLM-агент добавляет новый провайдер в FA.
Он читает ADR-11, видит инвариант I1: «Level-0 kernel is
stdlib-only», и решает, что ему нужен YAML для парсинга
манифестов (вместо TOML). Он пишет:

```python
# src/fa/authoring_tcb.py  — LLM добавляет:
import yaml  # для лучшего парсинга манифестов
```

**Что ловят текущие guardrails:**
- ruff: ✅ проходит (yaml — валидный импорт)
- mypy: ✅ проходит (yaml имеет type stubs)
- deptry: ✅ проходит (если yaml добавлен в зависимости)
- pytest: ✅ проходит (если функциональность работает)
- authoring_tcb rules (V2/V4/V11): ✅ проходят (проверяют другое)

**Что НЕ ловит ни один guardrail:** Нарушение ADR-11-I1 —
«Level-0 kernel is stdlib-only». yaml — third-party пакет.
Инвариант нарушен, но никто этого не видит.

---

### Почему Spec Growth Engine НЕ работает для FA

Spec Growth Engine решает эту проблему так: спецификация
записана в структурированном формате (JSON-узлы с типами),
и дрифт-детектор автоматически сравнивает два графа.

Но для FA это означало бы: переписать все ADR из Markdown
в машинно-читаемый формат. Это **огромное** изменение
поверхности проекта, прямо противоречащее принципу
«less surface, more simple and robust».

Кроме того, ADR-11 содержит **рассуждения** — почему принято
решение, какие альтернативы рассматривались, какие trade-offs.
Машинно-читаемый формат теряет эту информацию.

---

### Как это реально должно работать: «скомпилированный инвариант»

Правильный подход для FA — не пытаться автоматически парсить
прозу ADR, а **написать инвариант как тест вручную**,
один раз, рядом с ADR:

```python
# tests/test_adr11_invariants.py

import ast
import sys
from pathlib import Path


def test_adr11_i1_kernel_is_stdlib_only():
    """ADR-11 I1: Level-0 kernel imports no third-party packages.

    This is a compiled invariant — the ADR prose is the spec,
    this test is the compiled version. Drift is detected when
    this test fails.

    ADR source: knowledge/adr/ADR-11-authoring-guardrails.md
    Invariant: "Level-0 kernel is frozen, stdlib-only"
    """
    import fa.authoring_tcb

    source = Path(fa.authoring_tcb.__file__).read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in sys.stdlib_module_names, (
                    f"ADR-11 I1 violation: authoring_tcb imports "
                    f"third-party package '{alias.name}'. "
                    f"Level-0 kernel must be stdlib-only."
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # absolute import
                assert node.module in sys.stdlib_module_names or node.module.split(".")[0] in sys.stdlib_module_names, (
                    f"ADR-11 I1 violation: authoring_tcb imports "
                    f"from third-party package '{node.module}'. "
                    f"Level-0 kernel must be stdlib-only."
                )
```

**Как это работает:**

1. ADR-11 — это **спецификация** (проза для людей)
2. Тест — это **скомпилированный инвариант** (код для CI)
3. Если LLM добавляет `import yaml` в authoring_tcb.py → тест падает
4. CI красный → проблема видна немедленно

**Ключевое отличие от Spec Growth Engine:**
- Spec Growth Engine: спецификация → автоматический дрифт-детектор
- FA: спецификация (проза) → ручной скомпилированный тест

Второй вариант проще, требует меньше поверхности, и не нужно
менять формат ADR. Но он **не масштабируется автоматически** —
каждый инвариант нужно писать руками.

---

### Сколько таких инвариантов реально нужно?

Не для каждого ADR. Только для **высокорисковых инвариантов**,
где нарушение = критический баг:

| ADR Invariant | Риск нарушения | Нужен тест? |
|---|---|---|
| I1: kernel stdlib-only | HIGH (LLM может добавить зависимость) | ✅ Да |
| I5: test semantic decay | LOW (уже есть V4/V11 правила) | ❌ Нет — уже покрыто |
| I7: protected paths | MEDIUM (LLM может изменить CODEOWNERS) | ⚠️ Может быть — уже частично покрыто check_protected_paths.py |
| I9: live-path DoD | LOW (уже есть contract-check) | ❌ Нет — уже покрыто |

**Вывод:** Мне нужен 1 тест для I1, возможно 1 для I7. Не 10 тестов
для каждого ADR. Это снижает оценку с MEDIUM-HIGH до LOW-MEDIUM.

---

### Ещё один реальный пример: contract-check уже делает это

Существующий `scripts/check_producer_consumer_contract.py` — это
УЖЕ скомпилированный инвариант. Он проверяет, что каждый
EventType имеет и продюсер, и консьюмер. Если LLM добавляет
новый EventType без обработчика — скрипт падает.

Это «drift detection» для контракта событий. И он уже работает!
Назвать это «spec-code drift detection» в академическом смысле
— преувеличение. Это просто **тест на инвариант**.

---

### Итог по G3

| Что я утверждал | Реальность |
|---|---|
| «Нужен drift detector» | Нужен compiled invariant (тест), не автоматический детектор |
| «MEDIUM-HIGH yield» | LOW-MEDIUM — нужно всего 1-2 теста |
| «Следуем Spec Growth Engine» | SGE требует machine-readable specs, которых у нас нет |

---

---

## G5: Self-Correction Loop Bounding — почему enforceability преувеличен

### Что я утверждал в v1

> «Нужен hard cap на self-correction loops LLM. После 3 неудачных
> попыток — STOP, эскалация к человеку. Можно реализовать через
> счётчик в session DB.»

Звучит правильно как принцип, но **реализуемость через session DB —
ошибка**.

---

### Пример сценария: LLM пытается починить тест

Представим: LLM пишет код для FA, запускает `just check`, получает
ошибку:

```
FAILED tests/test_coder_loop.py::test_context_budget_hard_stop
AssertionError: expected stop_reason "context_budget_hard_stop",
got "compaction_circuit_breaker"
```

**Попытка 1:** LLM меняет stop_reason в coder_loop.py:
```python
# Было:
state.log.append(actor="runtime", kind="context_budget_hard_stop", content=decision)
# LLM меняет на:
state.log.append(actor="runtime", kind="compaction_circuit_breaker", content=decision)
```
Результат: Другой тест падает. Теперь `test_compaction_circuit_breaker_emitted`
не находит ожидаемое событие.

**Попытка 2:** LLM меняет логику ранней остановки:
```python
# LLM добавляет:
if budget.exceeded_hard_stop():
    break  # вместо продолжения к compaction
```
Результат: Тест проходит, но теперь 3 других теста падают —
потому что early-break убивает compaction path.

**Попытка 3:** LLM добавляет None-проверку:
```python
if state.log is not None:
    state.log.append(...)
```
Результат: TypeError на другой строке — `NoneType not subscriptable`.

**Попытка 4:** LLM переписывает весь budget-check блок...
Результат: 7 тестов падают. Контекст LLM заполнен 4 неудачными
попытками. Качество кода деградирует.

Это **спираль смерти**. Каждая попытка хуже предыдущей.

---

### Почему «счётчик в session DB» НЕ работает

Я предложил: «добавить счётчик в session DB, после 3 попыток — STOP».

Проблема: **FA не контролирует LLM, который пишет его код.**

```
┌─────────────────────────────────────────────────┐
│  Claude Code / Devin / Cursor (ВНЕШНИЙ процесс) │
│  ┌─────────────────────────────────────────────┐ │
│  │  LLM делает попытку 1                      │ │
│  │  LLM делает попытку 2                      │ │
│  │  LLM делает попытку 3                      │ │
│  │  ← КТО СЧИТАЕТ? FA? Нет — FA не запущен!  │ │
│  └─────────────────────────────────────────────┘ │
│                     │                            │
│                     ▼                            │
│            git commit (попытка N)                │
│                     │                            │
│                     ▼                            │
│            CI: just check                        │
│            ← ЗДЕСЬ FA видит результат            │
└─────────────────────────────────────────────────┘
```

FA видит только **результат** каждого коммита (pass/fail CI).
FA **не видит**:
- Сколько попыток LLM сделал внутри своей сессии
- Как заполняется контекст LLM
- Какие подходы LLM уже пробовал

Session DB в FA — это база данных **продуктовых сессий**
(запусков `fa run`), а не сессий разработки. Когда Devin пишет
код для FA, Devin не запускает `fa run` — он запускает `just check`.

---

### Что реально работает: три уровня контроля

#### Уровень 1: Prompt-level (AGENTS.md) — feedforward guide

Добавить в AGENTS.md правило:

```markdown
## Self-correction discipline

After 2 consecutive failed attempts to fix the same test failure, STOP.
Do not attempt a 3rd fix with the same approach. Instead:

1. Paste the FULL error output (not a summary)
2. State which approaches you already tried
3. Ask the operator for guidance

Escalation is not failure — it is the correct action when
deterministic debugging has exhausted its yield.

Evidence: Chroma Research (July 2025) shows all 18 frontier
models degrade with context growth. Microsoft/Salesforce documented
90%→51% accuracy drop in multi-turn conversations. Each failed
attempt adds noise to your context and reduces your accuracy.
```

**Плюсы:** Простой, не требует кода, LLM может последовать.
**Минусы:** LLM может проигнорировать. Это рекомендация, не закон.

**Реальный кейс из практики Claude Code:**
Из статьи chudi.dev (июнь 2026):

> «Context hygiene — clear the session after two failed corrections;
> compact around 50%.»

Это уже community best practice. FA просто формализует его.

#### Уровень 2: CI-level detection — feedback sensor

FA **может** наблюдать паттерн «много коммитов, всё ещё красный»:

```python
# scripts/check_struggle_signal.py (концепт)

"""Detect branches where the same test fails 3+ consecutive commits."""

import subprocess


def count_consecutive_failures(branch: str, test_name: str) -> int:
    """Count how many consecutive commits on branch fail the same test."""
    commits = (
        subprocess.run(["git", "log", "--format=%H", branch], capture_output=True, text=True).stdout.strip().split("\n")
    )

    consecutive = 0
    for commit in commits[:10]:  # look at last 10 commits
        result = subprocess.run(
            ["git", "stash", "&&", "git", "checkout", commit, "&&", "uv", "run", "pytest", "-x", test_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            consecutive += 1
        else:
            break  # test passed at some earlier commit

    return consecutive
```

Это **реально наблюдаемый сигнал**. FA может обнаружить:
«на этой ветке тест X падает 3 коммита подряд → LLM в спирали смерти».

**Но это дорого:** нужно запускать pytest для каждого коммита.
Лучше: просто считать коммиты с `just check` fail в CI logs.

#### Уровень 3: Error message quality (G6) — самый мощный уровень

Самый эффективный способ предотвратить спираль смерти — **сделать
так, чтобы LLM решал проблему с 1-й попытки**.

Сейчас ошибка выглядит так:
```
AssertionError: expected stop_reason "context_budget_hard_stop",
got "compaction_circuit_breaker"
```

LLM видит это и думает: «Надо поменять stop_reason». Это неправильно.
Реальная проблема: budget check не останавливает цикл вовремя.

Если ошибка будет такой:
```
AssertionError: test_context_budget_hard_stop failed:
  Expected stop_reason = "context_budget_hard_stop"
  Got stop_reason = "compaction_circuit_breaker"

  DIAGNOSIS: The session continued to compaction instead of
  stopping at the hard-stop threshold. This means the budget
  check at coder_loop.py:690 did not trigger an early break.

  LIKELY FIX: Check that getattr(state.feature_flags,
  "context_budget_enabled", True) returns True and that the
  budget.exceeded_hard_stop() condition is reached before
  the compaction threshold.
```

LLM получает **точный диагноз** и может исправить за 1 попытку
вместо 3+.

**Это превращает проблему G5 (bounding) в проблему G6
(error message quality).** Если ошибки достаточно подробные,
спираль смерти возникает реже, и bounding становится менее
критичным.

---

### Почему v1 переоценил enforceability

v1 предлагал: «добавить счётчик в session DB, после 3 попыток —
автоматический STOP».

Это **не работает**, потому что:

1. FA не видит попытки LLM — только финальные коммиты
2. FA не может остановить внешнюю сессию Claude Code/Devin
3. «3 попытки» — это не универсальное число; для простых багов
   может хватить 1, для сложных архитектурных проблем нужно 5+

Правильная модель:

```
Запрос: "почини тест"
     │
     ▼
┌─────────────────┐    Уровень 3: Хорошие ошибки
│ LLM читает      │    (G6 — actionable error messages)
│ ошибку           │    → решает за 1 попытку
└────────┬────────┘
         │ если не помогло
         ▼
┌─────────────────┐    Уровень 1: Prompt-правило
│ LLM пробует     │    (AGENTS.md — "2 попытки, потом STOP")
│ ещё раз         │    → запрашивает помощь
└────────┬────────┘
         │ если продолжает
         ▼
┌─────────────────┐    Уровень 2: CI-сигнал
│ CI видит 3+     │    (struggle detection в CI)
│ красных коммита │    → флаг для ревьюера
└─────────────────┘
```

Ни один из этих уровней не является «hard cap» в том смысле,
как я описывал в v1. Это **soft, layered defense** — каждый
уровень уменьшает вероятность спирали смерти, но ни один
не гарантирует её предотвращения.

---

### Итог по G5

| Что я утверждал | Реальность |
|---|---|
| «Hard cap через session DB» | Невозможно — FA не контролирует внешнюю LLM-сессию |
| «MEDIUM yield» | LOW — в основном prompt-level, не computational |
| «3 попытки — потом STOP» | Модель должна быть layered: (1) хорошие ошибки, (2) prompt-правило, (3) CI-сигнал |

---

## Общий вывод

Оба gap (G3 и G5) страдают от одной и той же ошибки мышления:
**я проектировал решение для идеализированного мира, где
FA контролирует весь стек**. В реальности:

- FA — это **harness** (набор инструментов), а не **runtime**
  для LLM, который пишет код. LLM работает во внешнем
  инструменте (Claude Code / Devin / Cursor).

- Поэтому FA может только: (1) направлять через промпты,
  (2) проверять через CI, (3) давать хорошие ошибки.
  FA **не может** наблюдать или ограничивать внутренний цикл
  внешнего LLM.

- «Drift detection» для FA означает не «автоматически
  сравнить spec с code», а «написать тест-инвариант руками
  для критических ADR». Это дешевле, проще, и не требует
  новой поверхности.

- «Self-correction bounding» для FA означает не «hard cap»,
  а «layered soft defense» с акцентом на качество ошибок (G6),
  которое делает bounding менее нужным.
