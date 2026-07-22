# РАСШИРЕННЫЙ ПЛАН РЕАЛИЗАЦИИ: Закрытие прорех в защитных механизмах (Фазы 1–5)

**Plan-ID:** PLAN-guardrail-gap-closure-extended-ru
**Статус:** READY | **Глубина:** P3 | **Ревизия:** v1-ru
**Дата:** 2026-07-19
**Источник:** PLAN-guardrail-gap-closure.md (v1) + external-verification-guardrail-gaps-2026-07-19.md (с корригендумом §21)

---

# ВВЕДЕНИЕ: Зачем нужен этот документ

Оригинальный план (`PLAN-guardrail-gap-closure.md`) написан плотным техническим языком и предполагает, что читатель уже глубоко понимает архитектуру проекта FA. Этот расширенный документ — **перевод и развёртка** оригинального плана на русский язык с подробными объяснениями каждой абстрактной идеи, конкретными примерами и пошаговыми инструкциями, которые может выполнить исполнитель без угадывания.

Если в оригинале сказано «заменить getattr на прямой доступ с fail-closed семантикой», здесь будет объяснено: **что такое getattr, почему он опасен, что значит fail-closed, и как именно выглядит исправление с примером до/после**.

---

# ЧАСТЬ 0: КЛЮЧЕВЫЕ ПОНЯТИЯ (глоссарий для понимания плана)

## 0.1 Что такое «защитные ограждения» (guardrails)

Представьте, что агент FA — это автомобиль. Защитные ограждения — это не руль и не двигатель, а **перила на дороге**: они не управляют движением, но предотвращают падение в пропасть. В коде это:

- **Проверки типов** (`LogKind = Literal[...]`) — не дадут передать опечатку в названии события
- **Скрипты-контракты** (`check_producer_consumer_contract.py`) — не дадут добавить событие, у которого нет обработчика
- **Замороженные dataclass** (`frozen=True`) — не дадут случайно изменить конфигурацию во время работы
- **Защита цепочки поставок** (`dependency_contract.toml`) — не дадут LLM-агенту добавить несуществующий пакет в зависимости

Без этих ограждений агент может «проехать» мимо ошибки — тесты пройдут, но система не будет работать корректно.

## 0.2 Что такое «прорехи» (gaps)

Прореха — это место, где ограждение **отсутствует**, **неполно** или **не работает как задумано**. Примеры:

| Прореха | Что не работает | Чем это грозит |
|---|---|---|
| G1: Логическая ловушка `or 150000` | `context_limit=0` превращается в 150000 | Нельзя отключить лимит контекста даже намеренно |
| G2: Стирание типа `Any | None` | Компилятор не проверяет типы compactor_chain | Опечатка в имени атрибута не ловится до runtime |
| G12: Консультативная проверка зависимостей | `check_protected_paths.py` выходит с кодом 0 для изменений в зависимостях | LLM-агент может добавить галлюцинированный пакет, и CI не заблокирует |

## 0.3 Что такое «живость» (liveness)

Это шкала готовности функции к использованию:

- **L0** — не существует. Код не написан.
- **L1** — импортируется, но не вызывается. Класс определён, но нигде не используется.
- **L2** — вызывается из реальной точки входа, но не проверен. Функция работает в теории, но нет теста.
- **L3** — работает И имеет kill-check (тест, который падает при удалении продакшн-кода). **Это единственный уровень, который считается «готовым к выпуску».**

**Пример:** Событие `context_warn` было на уровне L1 — константа существовала, но никто её не генерировал. После добавления `output.emit(OutputEvent(type="context_warn", ...))` и C1-теста оно перешло на L3.

## 0.4 Что такое kill-check (проверка на удаление)

Kill-check — это тест, который **должен упасть**, если удалить продуктивный код. Если тест проходит и без этого кода — тест вакуумный (theater), он ничего не проверяет.

**Пример вакуумного теста:**
```python
# Этот тест проверяет, что обработчик _handle_context_warn работает.
# Но он передаёт событие вручную — не проверяет, что кто-то это событие генерирует.
def test_handle_context_warn():
    renderer = ConsoleRenderer()
    event = OutputEvent(type="context_warn", data={"pct": 85})
    renderer.on_event(event)
    # Тест пройдёт, даже если НИКТО в продакшн-коде не генерирует context_warn!
```

**Пример настоящего kill-check:**
```python
# Этот тест загрузит РЕАЛЬНУЮ сессию и проверит, что событие генерируется.
def test_context_warn_produced_by_budget_check():
    drive_session(task, provider_chain=mock_chain, ...)  # реальный корень
    events = [e for e in capture if e.type == "context_warn"]
    assert len(events) >= 1
    # Если удалить output.emit(type="context_warn") из coder_loop.py — тест УПАДЁТ
```

## 0.5 Что такое «двусторонний контракт» (two-sided contract)

Каждое наблюдаемое событие (observable signal) в системе должно иметь **две стороны**:

1. **Продюсер** — код, который создаёт событие (`output.emit(...)`)
2. **Консьюмер** — код, который обрабатывает событие (`_handle_context_warn`)

Если есть только консьюмер — это «мёртвый обработчик»: он работает, но никогда не вызывается. Если есть только продюсер — событие генерируется, но никто его не видит. Оба случая — дефекты.

**Аналогия:** Поставщик (продюсер) везёт товары на склад. Клиент (консьюмер) забирает их со склада. Если поставщик не везёт — клиент ждёт впустую. Если клиент не забирает — товары портятся на складе.

## 0.6 Что такое «fail-closed» и «fail-open»

Это две стратегии поведения при ошибке или неопределённости:

- **Fail-closed (отказ-закрыто):** Если что-то пошло не так — **запретить** действие. Безопаснее.
  - Пример: если флаг `context_budget_enabled` не определён → считать его `True` (бюджет включён — безопасный дефолт)
- **Fail-open (отказ-открыто):** Если что-то пошло не так — **разрешить** действие. Удобнее, но опаснее.
  - Пример: если флаг `telemetry_enabled` не определён → считать его `False` (телеметрия выключена — нет риска для данных)

**Принцип:** Флаги, влияющие на безопасность → fail-closed. Флаги для удобства → fail-open.

## 0.7 Что такое «dual-write» (двойная запись)

Система FA пишет события через **два канала**:

1. `log.append(...)` — запись в EventLog → сохраняется в SQLite + JSONL (долговечность)
2. `output.emit(...)` — запись в EventBus → отображается в консоли (видимость для оператора)

**Правило dual-write:** Каждый код, который пишет в один канал, **обязан** писать и в другой. Если записать только в EventLog — оператор ничего не увидит. Если записать только в EventBus — данные не сохранятся.

**Пример нарушения:** В coder_loop.py был `log.append(kind="context_budget_warn")`, но не было `output.emit(type="context_warn")`. Оператор не видел предупреждения в консоли.

## 0.8 Что такое TRACE и почему он human-mediated

TRACE — это механизм, который записывает каждое исправление ошибки в структурированный лог (`.fa/corrections.jsonl`), чтобы та же ошибка не повторялась.

**Почему обязательно human-mediated (с участием человека)?**

AGENTS.md правило №1: «Держи систему курируемой человеком. Самоулучшающиеся подсистемы — известный антипаттерн.»

Если бы TRACE автоматически создавал правила из исправлений, LLM-агент мог бы:
1. Случайно внести ошибку
2. «Исправить» её, создав правило, которое маскирует ошибку
3. Система стала бы «самоулучшаться» в неправильном направлении

Поэтому: TRACE только **предлагает** правила, а человек **решает**, принимать ли их.

---

# ЧАСТЬ 1: ИСХОДНОЕ СОСТОЯНИЕ — ЧТО СЕЙЧАС НЕ ТАК

## 1.1 Логическая ловушка `or 150000` (G1)

**Где:** `src/fa/inner_loop/coder_loop.py`, строка 409

**Что написано:**
```python
context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
```

**Почему это баг:** Оператор `or` в Python возвращает первый истинный элемент. Если `context_limit = 0`, то `0 or 150000` вернёт `150000`. Это значит: **нельзя установить лимит контекста в ноль**, даже если это осознанное решение.

**Конкретный пример:**
```python
# Оператор хочет полностью отключить контекст (например, для тестирования)
config = ChainConfig(context_limit=0)  # явно указал 0
limit = getattr(config, "context_limit", 150000) or 150000
# limit = 150000  ← ОШИБКА! Оператор указал 0, а получил 150000
```

**Как исправить:** `ChainConfig` всегда имеет поле `context_limit` (проверено в `chain.py:107`), поэтому getattr с fallback не нужен:
```python
context_limit = provider_chain.config.context_limit  # прямой доступ
```

## 1.2 Двойной getattr в компакторе (G2)

**Где:** `src/fa/inner_loop/compaction/compactor.py`, строка 156

**Что написано:**
```python
model_slug = getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")
```

**Почему это баг:**
1. `self.compactor_chain` объявлен как `Any | None` — компилятор не проверяет типы
2. Двойной getattr — это «костыль», который скрывает реальные ошибки
3. Если `compactor_chain` — это `ProviderChain`, у него ВСЕГДА есть `config.model` — fallback `"compactor"` недостижим

**Конкретный пример:**
```python
# Если compactor_chain = None:
getattr(None, "config", None)  # → None
getattr(None, "model", "compactor")  # → "compactor" — но это мёртвый код!
# Реально, если compactor_chain is None, мы вообще не доходим до строки 156
# (есть guard на строке 133: if not self.compactor_chain)
```

**Как исправить:**
```python
if self.compactor_chain is not None:
    model_slug = self.compactor_chain.config.model
else:
    model_slug = ""  # пустая строка — компактор не используется
```

## 1.3 Отсутствие типа LogKind (G3)

**Где:** `src/fa/inner_loop/state.py`, `EventLog.append(kind: str)`

**Что не так:** Параметр `kind` объявлен как `str` — любая строка принимается. Если написать `kind="contex_warn"` (опечатка) — ни один инструмент это не поймает.

**Сколько уникальных строк-идентификаторов в коде:** 30. Каждая — потенциальная опечатка.

**Конкретный пример:**
```python
# До: любая строка допустима — опечатка не ловится
log.append(kind="contex_budget_warn")  # ← опечатка, но компилятор молчит

# После: только разрешённые значения
LogKind = Literal["context_budget_warn", "context_budget_hard_stop", ...]
log.append(kind="contex_budget_warn")  # ← pyright: ОШИБКА ТИПА!
```

## 1.4 Девять полей типа `Any | None` (G4)

**Где:** `src/fa/inner_loop/state.py`, строки 276–284

**Что не так:** 9 полей SessionState объявлены как `Any | None`. `Any` означает «любой тип» — компилятор полностью отключает проверку типов для этих полей.

**Конкретный пример:**
```python
# До: можно передать что угодно
state.feature_flags = "не флаги, а строка"  # pyright не ругается!
state.session_db = 42  # pyrich не ругается!

# После: только правильный тип или None
state.feature_flags: FeatureFlags | None = None
state.feature_flags = "не флаги"  # pyright: ОШИБКА ТИПА!
```

## 1.5 Двенадцать getattr-вызовов для чтения флагов (G5)

**Где:** 6 файлов (coder_loop, loop, state, spawn_subagent, subagent_runner, compactor)

**Что не так:** Код использует `getattr(state.feature_flags, "field_name", default)` вместо прямого доступа. Это:
1. Скрывает опечатки в именах полей
2. Даёт fallback, который может быть неправильным
3. Не даёт компилятору проверить типы

**Конкретный пример:**
```python
# До: опечатка в имени флага не ловится
getattr(state.feature_flags, "context_buget_enabled", False)
# → всегда возвращает False (дефолт), потому что поля "context_buget_enabled" нет
# А есть "context_budget_enabled" — но об этом никто не узнаёт!

# После: опечатка ловится на этапе компиляции
state.feature_flags.context_budget_enabled  # pyright поймает опечатку
```

## 1.6 Избыточный флаг `context_compaction_enabled` (G6)

**Где:** `coder_loop.py:~661`

**Что не так:** Есть два способа включить компакцию:
1. Флаг `context_compaction_enabled = True` в FeatureFlags
2. Значение `compaction_threshold = 50000` в ChainConfig

Но `compaction_threshold = None` уже означает «компакция выключена»! Флаг дублирует эту логику и создаёт **два источника истины** (SSoT нарушен).

**Пример конфликта:**
```python
# Что произойдёт, если флаг=True, но threshold=None?
flags = FeatureFlags(context_compaction_enabled=True)
config = ChainConfig(compaction_threshold=None)
# Код читает флаг → включает компакцию
# Но threshold=None → непонятно, до какого порога компактировать!
```

## 1.7 Консультативная проверка цепочки поставок (G12)

**Где:** `scripts/check_protected_paths.py`, строка 159

**Что не так:** Скрипт проверяет, изменены ли файлы зависимостей (`pyproject.toml`, `uv.lock`), но **по умолчанию выходит с кодом 0** (успех), даже если изменения есть. Только флаг `--fail-on-touch` делает проверку блокирующей.

**Конкретный пример:**
```python
# LLM-агент добавляет галлюцинированный пакет в pyproject.toml:
# [project.dependencies]
# requests2 = ">=2.0"  ← пакет не существует на PyPI

# check_protected_paths.py замечает изменение в pyproject.toml
# Выводит: ::warning Dependency manifest pyproject.toml was modified
# Выходит с кодом: 0  ← CI ЗЕЛЁНЫЙ! Пакет прошёл!
```

По данным CSA 2026-05, ~20% AI-сгенерированных ссылок на пакеты указывают на несуществующие пакеты. Это катастрофический риск: зловредный пакет может быть опубликован под галлюцинированным именем.

## 1.8 Отсутствие метрик защитных ограждений (G9)

**Где:** Вся система — нет агрегированных данных о работе ограждений

**Что не так:** Мы не знаем:
- Как часто срабатывает каждое правило? (возможно, правило никогда не ловит реальные ошибки)
- Каков уровень ложных срабатываний? (правило мешает работе)
- Как быстро исправляются ошибки? (правило найдено → исправлено за N минут)

Без этих данных невозможно **улучшать** ограждения — мы действуем вслепую.

## 1.9 Отсутствие TRACE-механизма (G2)

**Где:** Вся система — нет лога исправлений

**Что не так:** Когда агент исправляет ошибку, причина исправления **не записывается**. Через 2 недели та же ошибка может повториться, потому что никто не знает, что она уже была.

**Конкретный пример:**
1. Агент добавляет `import requests` в `authoring_tcb.py` (нарушение ADR-11-I1: только stdlib)
2. Человек замечает и исправляет → PR принят
3. Причина исправления не записана
4. Через неделю другой агент снова добавляет `import requests`
5. Цикл повторяется

## 1.10 Отсутствие frozen guard (N-G1)

**Где:** Вся система — 75 frozen dataclass без защиты от `object.__setattr__`

**Что не так:** `@dataclass(frozen=True)` блокирует обычное присваивание, но НЕ блокирует `object.__setattr__()`:

```python
@dataclass(frozen=True)
class FeatureFlags:
    context_budget_enabled: bool = True

flags = FeatureFlags()
flags.context_budget_enabled = False  # FrozenInstanceError — правильно!

# Но:
object.__setattr__(flags, "context_budget_enabled", False)
# ↑ Работает! Флаг изменён, хотя dataclass «заморожен»!
```

Если скомпрометированное правило использует этот трюк, оно может изменить конфигурацию TCB незаметно.

## 1.11 Нет ADR-11-I1 проверки (stdlib-only)

**Где:** Нет скрипта, проверяющего, что `authoring_tcb.py` импортирует только stdlib

**Что не так:** ADR-11-I1 требует, чтобы TCB (Trusted Computing Base — «ядро доверия») использовал только стандартную библиотеку Python. Но это правило — **декларативное**, без автоматической проверки. Агент может добавить `import requests` и никто не заметит, пока не произойдёт сбой.

## 1.12 Нет max_retry в FeatureFlags (G5)

**Где:** `src/fa/feature_flags.py`

**Что не так:** Нет ограничения на количество повторных попыток при ошибке. Если API-вызов постоянно падает, агент будет повторять бесконечно, тратя токены и время.

---

# ЧАСТЬ 2: ЦЕЛЕВОЕ СОСТОЯНИЕ — ЧТО ДОЛЖНО ПОЛУЧИТЬСЯ

## 2.1 Сводная таблица: было → стало

| Аспект | Было (AS-IS) | Стало (TO-BE) |
|---|---|---|
| context_limit | `getattr(...) or 150000` — глотает 0 | `provider_chain.config.context_limit` — прямой доступ |
| compactor_chain тип | `Any | None` — нет проверки | `ProviderChain | None` — типизировано |
| Двойной getattr | `getattr(getattr(...), "model", "compactor")` | `self.compactor_chain.config.model if ... else ""` |
| LogKind | `kind: str` — любая строка | `kind: LogKind` — Literal с 30 значениями |
| CONSOLE_MIRROR_KINDS | отсутствует | `frozenset[LogKind]` с 13 членами — определяет, какие события обязаны дублироваться в консоль |
| check_log_kind_contract.py | отсутствует | НОВЫЙ скрипт — проверяет все контракты LogKind |
| SessionState `Any | None` | 9 полей | 8 полей с реальными типами + 1 `Any | None` (pty_pool) |
| getattr для флагов | 12 вызовов getattr | Прямой доступ + None-check + fail-closed/open |
| Компакция | Два источника истины (флаг + threshold) | Один источник: `compaction_threshold is not None` |
| FAIL_CLOSED_FLAGS | отсутствует | `frozenset` с 3 критичными флагами |
| FAIL_OPEN_FLAGS | отсутствует | `frozenset` с 10 удобными флагами |
| dependency_contract.toml | отсутствует | НОВЫЙ замороженный TOML-контракт зависимостей |
| check_dependency_contract.py | отсутствует | НОВЫЙ скрипт — проверяет контракт зависимостей |
| check_protected_paths.py | Выходит 0 для зависимостей | Выходит 1 для зависимостей по умолчанию; `--advisory-deps` для перехода к консультативному режиму |
| session_meta метрики | Нет данных об ограждениях | `kind_counts`, `budget_threshold_breaches` при завершении сессии |
| fa stats --guardrail-metrics | отсутствует | НОВЫЙ CLI-флаг для просмотра метрик |
| Поведенческие утверждения | Нет в loop_guard тестах | 3 теста: deny→no-calls, hard_stop→no-tools, loop_guard→one-warn |
| corrections.jsonl | отсутствует | НОВЫЙ JSONL лог исправлений (только human-mediated) |
| compile_corrections.py | отсутствует | НОВЫЙ скрипт — агрегирует исправления, предлагает правила |
| frozen_guard.py | отсутствует | НОВЫЙ AST-сканер для `object.__setattr__` |
| check_tcb_stdlib.py | отсутствует | НОВЫЙ скрипт — проверяет, что TCB использует только stdlib |
| max_retry | отсутствует в FeatureFlags | `max_retry: int = 5` + guard в coder_loop |
| compaction_end visibility | Событие есть, но нет circuit-breaker сообщения | Явный loop_warn при срабатывании circuit breaker |

**Целевой уровень живости для ВСЕХ сигналов: L3** (kill-checkable от корня композиции).

---

# ЧАСТЬ 3: КОНТРАКТЫ — ТВЁРДЫЙ ЦЕНТР ПЛАНА

Каждый контракт определяет, **что именно** должно быть реализовано и **как проверить**, что реализация верна. Контракты — это не пожелания, а проверяемые спецификации.

## CT1: Тип LogKind

**Что:** `Literal[30 строковых значений]` в `src/fa/output.py`

**Зачем:** Когда параметр `kind` типизирован как `str`, опечатка `"contex_budget_warn"` проходит незамеченной. С `Literal` опечатку ловит Pylance/pyright на этапе редактирования кода.

**До:**
```python
def append(self, kind: str, ...):  # любая строка допустима
```

**После:**
```python
LogKind = Literal["context_budget_warn", "context_budget_hard_stop", ...]

def append(self, kind: LogKind, ...):  # только разрешённые значения
```

**Проверка:** Удалить один член из Literal → pyright выдаёт ошибку на всех местах, где используется это значение.

## CT2: CONSOLE_MIRROR_KINDS — дублирование в консоль

**Что:** `frozenset[LogKind]` с 13 членами в `src/fa/output.py`

**Зачем:** Не все LogKind-события нужно показывать в консоли оператору. Например, `telemetry`-события — только для внутреннего лога. CONSOLE_MIRROR_KINDS определяет, **какие** события обязаны дублироваться через `output.emit`.

**Пример:** Событие `context_budget_warn` входит в CONSOLE_MIRROR_KINDS → код ОБЯЗАН одновременно:
1. Записать в EventLog: `log.append(kind="context_budget_warn", ...)`
2. Отправить в консоль: `output.emit(OutputEvent(type="context_warn", ...))`

Если программист забыл `output.emit` — скрипт `check_log_kind_contract.py` поймает это.

**Проверка:** Удалить `output.emit` для CONSOLE_MIRROR_KIND → скрипт проверки выходит с кодом 1.

## CT3: Скрипт check_log_kind_contract.py

**Что:** Скрипт, который проверяет:
1. Все `log.append(kind=...)` используют значения из LogKind
2. Все CONSOLE_MIRROR_KINDS имеют dual-write (log.append + output.emit)
3. C1-тесты покрывают все LogKind

**Выход:** Код 0 (всё хорошо) или 1 (есть gaps) с конкретными сообщениями об ошибках.

## CT4: Типизированные поля SessionState

**Что:** 8 полей меняют тип с `Any | None` на реальный тип; pty_pool остаётся `Any | None`

**Почему pty_pool остаётся:** Модуль `fa.runtime` опциональный — он может не быть установлен. Тип `PtyPool` не всегда доступен для импорта.

**До:**
```python
feature_flags: Any | None = None  # можно передать строку, число, что угодно
```

**После:**
```python
feature_flags: FeatureFlags | None = None  # только FeatureFlags или None
```

## CT5: Категории флагов FAIL_CLOSED / FAIL_OPEN

**Что:** Два `frozenset[str]` в `feature_flags.py`

**FAIL_CLOSED_FLAGS (3 флага — безопасный дефолт = включено):**
- `context_budget_enabled` — если не определён → True (бюджет включён — безопасно)
- `context_compaction_enabled` — если не определён → True (компакция включена — безопасно)
- `subagent_spawning_enabled` — если не определён → True (запуск подагентов разрешён — но только если явно)

**FAIL_OPEN_FLAGS (10 флагов — безопасный дефолт = выключено):**
- `blackboard_enabled`, `telemetry_enabled`, `tool_batching_enabled`, и т.д.
- Если не определены → False (функция выключена — нет риска утечки данных)

**Инвариант:** Каждый флаг FeatureFlags входит ровно в один набор. Тест проверяет:
```python
assert FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS == {
    f.name for f in fields(FeatureFlags)
} - {"context_compaction_enabled", "max_retry"}
```

## CT6: Единый источник истины для компакции (SSoT)

**Что:** `compaction_enabled = compaction_threshold is not None`

**Почему:** Один источник истины вместо двух. Если `compaction_threshold` задан (не None) → компакция включена. Если None → выключена. Флаг `context_compaction_enabled` становится устаревшим.

**До:**
```python
compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)
```

**После:**
```python
compaction_enabled = compaction_threshold is not None
```

## CT7: Замороженный контракт зависимостей (dependency_contract.toml)

**Что:** TOML-файл с разрешёнными зависимостями, их версиями и категориями

**Структура:**
```toml
[kernel]
version = "0.1"

[packages.core]        # Основные зависимости — обязательно
markdown-it-py = ">=3.0"
fastjsonschema = ">=2.21"
pyyaml = ">=6.0"
bashlex = ">=0.18"
libtmux = ">=0.40"
pexpect = ">=4.9"

[packages.security_critical]  # Критичные для безопасности
pyyaml = ">=6.0"             # yaml.safe_load только, по ADR-9

[registries]
default = "pypi"       # Разрешённый реестр пакетов
```

**Логика fail-closed:**
- Неизвестный ключ → HARD-BLOCK (как в `authoring_tcb.py`)
- Пакет в pyproject.toml, но не в контракте → ADVISORY с `expires_on`
- Пакет security_critical отсутствует → HARD-BLOCK
- Неизвестный пакет в контракте → HARD-BLOCK

**Почему это важно:** Без контракта, LLM-агент может добавить `requests2 = ">=2.0"` в `pyproject.toml`. Если кто-то опубликует зловредный пакет под именем `requests2` на PyPI — система скомпрометирована.

## CT8: Скрипт check_dependency_contract.py

**Что:** Скрипт, который сравнивает `pyproject.toml` с `dependency_contract.toml`

**Поведение:**
- Все пакеты из pyproject.toml есть в контракте → код 0
- Неизвестный пакет → код 1 с диагностикой в формате RuleResult

**Проверка (kill-check):** Добавить `requests = ">=2.0"` в pyproject.toml → скрипт выходит с кодом 1.

## CT9: Метрики защитных ограждений в session_meta

**Что:** При завершении сессии записывать в session_meta:
- `kind_counts` — сколько раз каждое событие произошло
- `budget_threshold_breaches` — сколько раз бюджет был превышен

**Как:** Использовать СУЩЕСТВУЮЩИЙ `SessionDatabase.set_meta()` — не нужен новый инструмент.

**До:**
```python
# В конце сессии — ничего не записывается
```

**После:**
```python
if state.session_db is not None:
    kind_counts = {}
    for event in state.log.read_all():
        kind_counts[event.kind] = kind_counts.get(event.kind, 0) + 1
    state.session_db.set_meta("kind_counts", kind_counts, _now_iso_z())
```

## CT10: Лог исправлений (corrections.jsonl)

**Что:** JSONL-файл, куда человек записывает каждое исправление ошибки

**Схема записи:**
```json
{"ts": "2026-07-19T14:30:00Z", "code": "FA-AUTHORING-V2-EXPORTS-COMPLETENESS", "remediation": "add 'MyClass' to __all__", "path": "src/fa/exports.py", "corrected_by": "human"}
```

**Критически важно:** Записи делает только человек. Никакой автоматической записи. Скрипт `compile_corrections.py` только читает и агрегирует.

## CT11: Замороженный страж (frozen_guard.py)

**Что:** AST-сканер, который ищет `object.__setattr__` в `src/fa/`

**Как работает:**
1. Обходит все `.py` файлы через `ast.walk`
2. Ищет вызовы вида `object.__setattr__(self, 'field', value)`
3. Проверяет, что все `@dataclass` в TCB-файлах имеют `frozen=True`
4. Проверяет отсутствие `__post_init__` на замороженных dataclass в TCB

**Выход:** Код 0 (чисто) или 1 (нарушения найдены) + генерирует `.fa/frozen_integrity_report.md`

## CT12: Проверка ADR-11-I1 (stdlib-only)

**Что:** Скрипт, проверяющий, что `authoring_tcb.py` импортирует только из стандартной библиотеки

**Как:** Сравнивает имена импортов с `sys.stdlib_module_names`

**Проверка (kill-check):** Добавить `import requests` в `authoring_tcb.py` → скрипт выходит с кодом 1.

## CT13: max_retry в FeatureFlags

**Что:** Поле `max_retry: int = 5` + проверка в coder_loop

**До:**
```python
# Бесконечный цикл повторов при ошибке API
while retry_needed:
    try:
        response = provider_chain.request(...)
        retry_needed = False
    except APIError:
        pass  # Попробуем снова... и снова... и снова...
```

**После:**
```python
max_retry = state.feature_flags.max_retry if state.feature_flags is not None else 5
attempt = 0
while retry_needed and attempt < max_retry:
    try:
        response = provider_chain.request(...)
        retry_needed = False
    except APIError:
        attempt += 1
```

---

# ЧАСТЬ 4: ПОШАГОВАЯ РЕАЛИЗАЦИЯ — ФАЗЫ 1–5

## ═══ ФАЗА 1: Исправление логических ошибок ═══

Фаза 1 — это исправление багов, которые уже существуют в коде. Никаких новых артефактов, только исправления.

---

### Шаг S1: Исправить логическую ловушку `or 150000`

**Связь:** G1, CT4
**Зависимости:** нет | **Параллельно с:** S2
**Живость:** L2→L3

**Файл:** `src/fa/inner_loop/coder_loop.py`, символ `_drive_session_inner`

**Что сделать:**

Заменить строки 409–410:
```python
# БЫЛО:
context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
compaction_threshold = getattr(provider_chain.config, "compaction_threshold", None)

# СТАЛО:
context_limit = provider_chain.config.context_limit
compaction_threshold = provider_chain.config.compaction_threshold
```

**Почему это безопасно:** `ChainConfig` ВСЕГДА имеет оба поля (проверено в `chain.py:107-108`). getattr с fallback — мёртвый код.

**НЕ делать:**
- Не трогать логику hard-stop или бюджет — это отдельные контракты

**Критерии выхода:**
```bash
grep -n "or 150000" src/fa/inner_loop/coder_loop.py  # → 0 результатов
grep -n "getattr.*context_limit\|getattr.*compaction_threshold" src/fa/inner_loop/coder_loop.py  # → 0 результатов
```

**Kill-check:** Установить `context_limit=0` в тестовом ChainConfig → тест утверждает `budget.limit_tokens == 0` (не 150000).

---

### Шаг S2: Исправить стирание типа compactor_chain + двойной getattr

**Связь:** G2, CT4
**Зависимости:** нет | **Параллельно с:** S1
**Живость:** L2→L3

**Файл:** `src/fa/inner_loop/compaction/compactor.py`

**Что сделать:**

1. Строка 128 — заменить тип:
```python
# БЫЛО:
def __init__(self, compactor_chain: Any | None = None):

# СТАЛО:
from fa.providers.chain import ProviderChain

def __init__(self, compactor_chain: ProviderChain | None = None):
```

2. Строка 156 — заменить двойной getattr:
```python
# БЫЛО:
model_slug = getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")

# СТАЛО:
model_slug = self.compactor_chain.config.model if self.compactor_chain is not None else ""
```

**Объяснение пустой строки:** Если `compactor_chain is None`, мы до строки 156 не доходим (guard на строке 133). Но если дошли — пустая строка корректна: «модель не задана, компакция не используется».

**НЕ делать:**
- Не добавлять fallback `"compactor"` — это мёртвый код, config всегда имеет model на ProviderChain

**Критерии выхода:**
```bash
grep -n "Any | None" src/fa/inner_loop/compaction/compactor.py  # → 0 для compactor_chain
grep -n "getattr.*config.*model" src/fa/inner_loop/compaction/compactor.py  # → 0
```

**Kill-check:** Передать `compactor_chain=None` → `compact()` возвращает результат `_local_fallback_truncate` (без крушения).

---

### Шаг S3: Верификация Фазы 1

**Что сделать:**
```bash
python scripts/check_producer_consumer_contract.py  # → exit 0
python scripts/check_no_mocked_dataclasses.py        # → exit 0
python -m pytest tests/ -k "context_limit or compactor or compaction" --tb=short -q
```

**Коммит:** `"fix: logic traps in context_limit getattr and compactor_chain typing (F-3, F-4)"`

---

## ═══ ФАЗА 2: LogKind + Console-Mirror + Проверка контрактов + Метрики G9 ═══

Фаза 2 добавляет типизацию для строковых идентификаторов и механизм проверки контрактов.

---

### Шаг S4: Добавить `LogKind = Literal[...]` в output.py

**Связь:** G3, CT1
**Зависимости:** S1 (чистый diff) | **Параллельно с:** S9
**Живость:** L0→L1

**Файл:** `src/fa/output.py`, модульный уровень

**Что сделать:**

После определения `EventType` (~строка 58), добавить:

```python
LogKind = Literal[
    # Жизненный цикл сессии
    "run_started",
    "run_stopped",
    "session_summary",
    # Ввод/вывод LLM
    "user_msg",
    "model_msg",
    "usage",
    "provider_attempt",
    # Ввод/вывод инструментов
    "tool_call",
    "tool_result",
    # Хуки / охранники
    "hook_decision",
    "loop_guard_warn",
    "audit",
    # Бюджет контекста
    "context_budget_warn",
    "context_budget_hard_stop",
    # Компакция
    "compaction_warning",
    "compaction_circuit_breaker",
    "compaction_stage2_start",
    "compaction_stage2_done",
    "compaction_stage2_error",
    "compaction_stage3_start",
    "compaction_stage3_done",
    "compaction_stage3_error",
    # Подагенты
    "subagent_spawn_start",
    "subagent_spawn_done",
    "subagent_spawn_fail",
    # Наблюдаемость / восстановление
    "recovery_action",
    "verification",
    "cost_observation",
    "telemetry",
    # Инфраструктура
    "service_unavailable",
    "timeout",
]
```

Добавить `"LogKind"` в `__all__`.

**НЕ делать:**
- Не добавлять новые log kinds, которых нет в `src/fa/` — только те, что уже используются

**Проверка:**
```python
from fa.output import LogKind
import typing
assert len(typing.get_args(LogKind)) == 30  # столько же, сколько grep нашёл
```

**Kill-check:** Удалить один член из Literal → pyright выдаёт ошибку на месте вызова `log.append(kind="удалённый_вид")`.

---

### Шаг S5: Добавить `CONSOLE_MIRROR_KINDS` в output.py

**Связь:** G3, CT2
**Зависимости:** S4 | **Параллельно с:** нет
**Живость:** L0→L1

**Что добавить после LogKind:**

```python
CONSOLE_MIRROR_KINDS: frozenset[LogKind] = frozenset({
    "context_budget_warn",           # Предупреждение о бюджете → оператор должен видеть
    "context_budget_hard_stop",      # Жёсткая остановка → критично для оператора
    "compaction_stage2_start",       # Начало компакции Stage 2
    "compaction_stage2_done",        # Компакция Stage 2 завершена
    "compaction_stage2_error",       # Ошибка компакции Stage 2
    "compaction_stage3_start",       # Начало компакции Stage 3
    "compaction_stage3_done",        # Компакция Stage 3 завершена
    "compaction_stage3_error",       # Ошибка компакции Stage 3
    "compaction_circuit_breaker",    # Сработал circuit breaker
    "tool_call",                     # Вызов инструмента → оператор видит, что делает агент
    "subagent_spawn_done",           # Подагент завершил работу
    "subagent_spawn_fail",           # Подагент упал
    "run_stopped",                   # Сессия остановлена
})
```

**Почему 13 из 30:** Остальные 17 видов — внутренние (telemetry, audit, usage) или стартовые (run_started, session_summary) — не критичны для оператора в реальном времени.

---

### Шаг S6: Типизировать `EventLog.append(kind: LogKind)`

**Связь:** G3, CT1
**Зависимости:** S4 | **Параллельно с:** S5
**Живость:** L1→L2

**Файл:** `src/fa/inner_loop/state.py`, символ `EventLog.append`

**Что сделать:**
1. Добавить `from fa.output import LogKind` в импорты
2. Изменить `kind: str` на `kind: LogKind` в `EventLog.append()`
3. **НЕ менять** `TraceEvent.kind: str` — JSONL-десериализация теряет Literal-ограничение

**Почему TraceEvent.kind остаётся str:** При чтении из JSONL мы получаем обычную строку. Если бы поле было LogKind, десериализация потребовала бы валидацию каждого значения — усложнение без практической пользы.

**Kill-check:** Изменить `kind="typo_value"` в продюсере → pyright выдаёт ошибку.

---

### Шаг S7: Создать `scripts/check_log_kind_contract.py`

**Связь:** G3, CT3
**Зависимости:** S4, S5 | **Параллельно с:** S6
**Живость:** L0→L3

**Что делает скрипт:**
1. Извлекает LogKind-литералы из output.py (regex по определению Literal)
2. Извлекает CONSOLE_MIRROR_KINDS из output.py
3. Находит все `log.append(kind=...)` в `src/fa/`
4. Проверяет, что каждый kind ∈ LogKind
5. Для каждого CONSOLE_MIRROR_KINDS проверяет, что output.emit существует на том же пути кода
6. Проверяет C1-покрытие для каждого kind
7. Выходит с кодом 1, если есть gaps

**Паттерн:** Следовать `check_producer_consumer_contract.py` (уже существует, 206 строк, проверяет EventTypes).

**Также:** Добавить тест `tests/test_check_log_kind_contract.py`.

**Kill-check:** Удалить `log.append(kind=...)` продюсер → контракт-чек выходит с кодом 1.

---

### Шаг S8: Обновить I-TW-17 в SKILL.md

**Связь:** G3, CT2
**Зависимости:** S5

Заменить расплывчатый инвариант I-TW-17 на конкретный:

```
I-TW-17: CONSOLE_MIRROR_KINDS (в output.py) определяет, какие log.append
виды ОБЯЗАНЫ также отправлять OutputEvent. Каждый вид в этом множестве
должен иметь и log.append-продюсер, и output.emit-продюсер на том же
пути кода. Скрипт check_log_kind_contract.py валидирует это.
```

---

### Шаг S9: Расширить session_meta метриками защитных ограждений (G9)

**Связь:** G9, CT9
**Зависимости:** нет | **Параллельно с:** S4–S8
**Живость:** L2→L3

**Файлы:** `src/fa/inner_loop/coder_loop.py`, `src/fa/stats.py`

**Что сделать:**

1. В coder_loop.py, в месте завершения сессии (где `state.log.append(actor="runtime", kind="run_stopped", ...)`), добавить:
```python
# G9: метрики ограждений для data-driven улучшения
if state.session_db is not None:
    kind_counts = {}
    for event in state.log.read_all():
        kind_counts[event.kind] = kind_counts.get(event.kind, 0) + 1
    state.session_db.set_meta("kind_counts", kind_counts, _now_iso_z())
    budget_breaches = kind_counts.get("context_budget_warn", 0) + kind_counts.get("context_budget_hard_stop", 0)
    state.session_db.set_meta("budget_threshold_breaches", budget_breaches, _now_iso_z())
```

2. В stats.py добавить флаг `--guardrail-metrics`, который читает session_meta по запускам.

3. Добавить C1-тест: `test_session_meta_guardrail_metrics` — запускает сессию и проверяет, что kind_counts записаны.

**НЕ делать:**
- НЕ создавать новый скрипт-сборщик метрик — расширить существующую инфраструктуру
- НЕ добавлять guardrail_overrides (требует парсинга CI-аннотаций, отложить)

**Kill-check:** Удалить вызовы set_meta → `fa stats --guardrail-metrics` возвращает пусто.

---

### Шаг S10: Верификация Фазы 2

```bash
python scripts/check_log_kind_contract.py         # → exit 0
python scripts/check_producer_consumer_contract.py # → exit 0
python scripts/check_no_mocked_dataclasses.py      # → exit 0
python -m pytest tests/ --tb=short -q
```

**Коммит:** `"feat: LogKind type + console-mirror contract + G9 session_meta metrics (F-1, F-2, G9)"`

---

## ═══ ФАЗА 3: Типизация полей SessionState ═══

---

### Шаг S11: Типизировать 9 полей `Any | None`

**Связь:** G4, CT4
**Зависимости:** S6 (нужен тип LogKind для импорта EventLog) | **Параллельно с:** нет
**Живость:** L1→L2

**Файл:** `src/fa/inner_loop/state.py`, символ `SessionState`

**Что сделать:**

1. Добавить TYPE_CHECKING-импорты:
```python
if TYPE_CHECKING:
    from fa.blackboard.blackboard import Blackboard
    from fa.inner_loop.artifacts import ArtifactStore
    from fa.inner_loop.transaction import Transaction
    from fa.observability.redaction import SecretRedactor
    from fa.output import EventBus
    from fa.telemetry.telemetry import TelemetryLogger
    from fa.workspace.worktree_manager import WorktreeManager
```

2. Переместить `from fa.feature_flags import FeatureFlags` в TYPE_CHECKING (оставить runtime-импорт в `__post_init__`).

3. Заменить поля (строки 276–284):
```python
# БЫЛО:
feature_flags: Any | None = None
transaction: Any | None = None
blackboard: Any | None = None
# ... и так далее

# СТАЛО:
transaction: Transaction | None = None
blackboard: Blackboard | None = None
telemetry: TelemetryLogger | None = None
feature_flags: FeatureFlags | None = None
artifact_store: ArtifactStore | None = None
pty_pool: Any | None = None  # PtyPool — опциональный модуль, оставляем Any
worktree_manager: WorktreeManager | None = None
session_db: SessionDatabase | None = None
output_bus: EventBus | None = None
```

**Объяснение TYPE_CHECKING:** Эти импорты используются только для type-checking, не для runtime. Это предотвращает циклические импорты. Код, который обращается к полям в runtime, должен делать None-проверку:

```python
# До: Any | None — не нужно проверять, но и тип неизвестен
if state.feature_flags:  # проходит, но что внутри feature_flags?

# После: FeatureFlags | None — нужно проверить, но тип известен
if state.feature_flags is not None:
    budget = state.feature_flags.context_budget_enabled  # pyright проверит!
```

**НЕ делать:**
- Не менять pty_pool с Any (fa.runtime — опциональный модуль)
- Не добавлять properties (отложено до P6)

**Kill-check:** Передать неверный тип полю → pyrich выдаёт ошибку.

---

### Шаг S12: Верификация Фазы 3

```bash
pyright  # чисто на всех изменённых файлах
python scripts/check_producer_consumer_contract.py  # → exit 0
```

**Коммит:** `"feat: type 9 Any|None fields on SessionState (F-5)"`

---

## ═══ ФАЗА 4: Fail-Closed/Open + Компакция SSoT + G12 + G13 ═══

---

### Шаг S13: Добавить FAIL_CLOSED_FLAGS / FAIL_OPEN_FLAGS + заменить getattr

**Связь:** G5, CT5
**Зависимости:** S11 | **Параллельно с:** S14
**Живость:** L0→L3

**Файлы:** `src/fa/feature_flags.py` + 6 файлов с getattr-вызовами

**Что сделать:**

1. Добавить в feature_flags.py после класса FeatureFlags:
```python
FAIL_CLOSED_FLAGS: frozenset[str] = frozenset({
    "context_budget_enabled",      # бюджет → по умолчанию ВКЛ (безопасно)
    "context_compaction_enabled",  # компакция → по умолчанию ВКЛ
    "subagent_spawning_enabled",   # подагенты → по умолчанию ВКЛ
})

FAIL_OPEN_FLAGS: frozenset[str] = frozenset({
    "blackboard_enabled",          # чёрная доска → по умолчанию ВЫКЛ
    "telemetry_enabled",           # телеметрия → по умолчанию ВЫКЛ
    "tool_batching_enabled",       # батчинг → по умолчанию ВЫКЛ
    "pty_pool_max_size",           # размер пула → не флаг, но в наборе
    "worktree_mode",               # режим worktree → по умолчанию "shared"
    "fts_db_path",                 # путь к FTS → по умолчанию ".fa/fts.db"
    "prompt_caching",              # кэширование промптов → по умолчанию ВКЛ
    "offload_threshold",           # порог оффлоада → по умолчанию 8000
    "max_subagent_spawns_per_session",  # лимит подагентов → по умолчанию 3
    "blackboard_filtered_history_include_plans",  # включение планов → по умолчанию ВЫКЛ
})
```

2. Заменить 12 getattr-вызовов на прямой доступ с None-проверкой:

```python
# БЫЛО (12 мест по коду):
budget_on = getattr(state.feature_flags, "context_budget_enabled", False)

# СТАЛО:
budget_on = state.feature_flags.context_budget_enabled if state.feature_flags is not None else True
#                                                                                       ^^^^
# fail-closed: если флаги не определены, бюджет ВКЛЮЧЁН (безопасный дефолт)
```

Для fail-open флагов:
```python
# БЫЛО:
bb_on = getattr(state.feature_flags, "blackboard_enabled", False)

# СТАЛО:
bb_on = state.feature_flags.blackboard_enabled if state.feature_flags is not None else False
#                                                                                      ^^^^^
# fail-open: если флаги не определены, чёрная доска ВЫКЛЮЧЕНА (нет риска утечки)
```

3. Добавить тест: `FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS == set(f.name for f in fields(FeatureFlags)) - {"context_compaction_enabled", "max_retry"}`

**НЕ делать:**
- НЕ добавлять функцию `read_flag()` — прямой доступ проще

**Kill-check:** Установить `feature_flags=None` → safety-critical флаг даёт рестриктивный дефолт.

---

### Шаг S14: Удалить флаговый затвор компакции (F-10 / G6)

**Связь:** G6, CT6
**Зависимости:** S13 | **Параллельно с:** S15
**Живость:** L2→L3

**Файл:** `src/fa/inner_loop/coder_loop.py`, ~строка 661

**Что сделать:**

```python
# БЫЛО:
compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)

# СТАЛО:
compaction_enabled = compaction_threshold is not None
```

Отметить `context_compaction_enabled` в FeatureFlags как устаревшее с комментарием.

**Объяснение:** Раньше компакция управлялась флагом `context_compaction_enabled`. Теперь единственный источник истины — `compaction_threshold`:
- `compaction_threshold = None` → компакция выключена
- `compaction_threshold = 50000` → компакция включена

**Kill-check:**
- `compaction_threshold=None` → компакция выключена
- `compaction_threshold=50000` → компакция включена

---

### Шаг S15: Создать dependency_contract.toml + check_dependency_contract.py (G12)

**Связь:** G7, CT7, CT8
**Зависимости:** нет | **Параллельно с:** S13, S14
**Живость:** L0→L3

**Файлы:**
- `.fa/dependency_contract.toml` — НОВЫЙ замороженный контракт
- `scripts/check_dependency_contract.py` — НОВЫЙ скрипт проверки
- `scripts/check_protected_paths.py` — ИЗМЕНИТЬ: добавить контракт в TCB, сделать deps блокирующими

**Содержимое dependency_contract.toml:**
```toml
[kernel]
version = "0.1"

[packages.core]
markdown-it-py = ">=3.0"
fastjsonschema = ">=2.21"
pyyaml = ">=6.0"
bashlex = ">=0.18"
libtmux = ">=0.40"
pexpect = ">=4.9"

[packages.security_critical]
pyyaml = ">=6.0"   # yaml.safe_load только, по ADR-9

[registries]
default = "pypi"
```

**Скрипт check_dependency_contract.py (~80 строк):**
1. Парсит контракт через `tomllib` (stdlib-only, соответствует ADR-11-I1)
2. Читает зависимости pyproject.toml через `tomllib`
3. Сравнивает: пакет в pyproject, но не в контракте → ADVISORY с `expires_on`
4. Пакет security_critical отсутствует → HARD-BLOCK
5. Неизвестные ключи → HARD-BLOCK (fail-closed)
6. Вывод: диагностика в формате RuleResult

**Обновление check_protected_paths.py:**
1. Добавить `.fa/dependency_contract.toml` в `_TCB_PATHS`
2. Изменить дефолтный exit для `_DEPENDENCY_PATHS` с 0 на 1 (блокирующий)
3. Добавить флаг `--advisory-deps` для восстановления консультативного поведения

**Kill-check:** Добавить `requests = ">=2.0"` в pyproject.toml → check выходит с кодом 1.

---

### Шаг S16: Добавить поведенческие утверждения в loop_guard тесты (G13)

**Связь:** G8, CT2
**Зависимости:** S13 | **Параллельно с:** S15
**Живость:** L2→L3

**Файл:** `tests/test_inner_loop_loop_guard.py`

**Добавить 3 теста:**

```python
def test_intent_guard_deny_no_provider_calls():
    """Если IntentGuard запрещает — нет вызовов провайдера после запрета."""
    # Запускаем сессию, где IntentGuard запрещает вызов инструмента
    # Утверждаем: provider_chain.request.call_count == 0 после запрета

def test_hard_stop_no_tool_calls():
    """Если context_budget_hard_stop срабатывает — нет вызовов инструментов."""
    # Запускаем сессию до порога hard-stop
    # Утверждаем: нет tool_call событий после hard_stop события

def test_loop_guard_exactly_one_warn():
    """Если loop_guard срабатывает — ровно одно loop_warn событие."""
    # Запускаем сессию с повторяющимися идентичными вызовами инструментов
    # Утверждаем: len([e for e in events if e.kind == "loop_guard_warn"]) == 1
```

**НЕ делать:**
- НЕ добавлять runtime-утверждения в продакшн-код (только CI-тесты для поведенческих контрактов)

**Kill-check:** Удалить логику IntentGuard deny → test_intent_guard_deny_no_provider_calls падает.

---

### Шаг S17: Добавить информативное сообщение при abnormal_stop (LOGIC-10)

**Связь:** G12, CT2
**Зависимости:** нет | **Параллельно с:** S16
**Живость:** L1→L3

**Файл:** `src/fa/inner_loop/coder_loop.py`, путь abnormal stop

**Что добавить:**

```python
hint = ""
if response.finish_reason == "length":
    hint = "Output truncated (finish_reason=length). Consider increasing max_tokens or simplifying the task."
elif response.finish_reason == "content_filter":
    hint = "Output blocked by content filter (finish_reason=content_filter). Review the prompt for policy violations."
else:
    hint = f"Unexpected finish_reason: {response.finish_reason}"
output.emit(OutputEvent(type="loop_warn", data={"detector": "abnormal_stop", "message": hint}))
```

**Зачем:** Раньше при abnormal stop оператор видел только «сессия завершилась» без объяснения причин. Теперь будет конкретное сообщение с рекомендацией.

---

### Шаг S18: Верификация Фазы 4

Все контракт-скрипты → exit 0, все тесты → pass.

**Коммит:** `"feat: fail-closed flags, compaction SSoT, dependency TCB, behavioral assertions (F-6, F-10, G12, G13, LOGIC-10)"`

---

## ═══ ФАЗА 5: Покрытие + TRACE + Аудит + Стражи ═══

---

### Шаг S19: Добавить отсутствующие парсеры log-kind в fa stats (F-7)

**Связь:** G12, CT1
**Зависимости:** S4 | **Параллельно с:** S20–S23
**Живость:** L2→L3

**Файл:** `src/fa/stats.py`, символ `parse_session`

**Что сделать:**
1. Добавить dataclass'ы: `CompactionTiming`, `CircuitBreakerEvent`, `RecoveryAction`, `VerificationEvent`, `CostObservation`, `ModelMessage`, `UserMessage`, `AuditEvent`, `TelemetryEvent`
2. Добавить поля в `SessionAnalytics`
3. Добавить elif-ветки в parse_session для каждого нового kind
4. Добавить рендеринг в render_session

**Критерий:** Все 30 log kinds имеют парсеры ИЛИ находятся в UNPARSED_KINDS allowlist.

---

### Шаг S20: Создать TRACE-механизм (G2)

**Связь:** G10, CT10
**Зависимости:** нет | **Параллельно с:** S19, S21–S23
**Живость:** L0→L3

**Файлы:**
- `.fa/corrections.jsonl` — НОВЫЙ лог исправлений
- `scripts/compile_corrections.py` — НОВЫЙ скрипт агрегации

**corrections.jsonl (пустой файл с заголовком):**
```jsonl
# TRACE: Лог исправлений, курируемый человеком. Каждая запись фиксирует
# исправление и его ремедиацию для будущей генерации правил.
# Никогда не комментируется автоматически.
# Схема: {"ts": "ISO-8601", "code": "FA-AUTHORING-...", "remediation": "...", "path": "...", "corrected_by": "human"}
```

**compile_corrections.py:**
1. Читает corrections.jsonl
2. Группирует по code, подсчитывает вхождения
3. Выводит сводку: наиболее частые шаблоны исправлений
4. Предлагает спецификации Level-1 правил (для ревью человеком)
5. **НИКОГДА не комментирует автоматически** — вывод только в stdout

**Kill-check:** Пустой corrections.jsonl → compile_corrections.py выдаёт пустую сводку.

---

### Шаг S21: Создать страж замороженных dataclass (N-G1/N-G2)

**Связь:** G11, CT11
**Зависимости:** нет | **Параллельно с:** S19, S20, S22, S23
**Живость:** L0→L3

**Файл:** `scripts/frozen_guard.py` — НОВЫЙ AST-сканер (~80 строк)

**Что делает:**
1. `ast.walk` все `.py` файлы в `src/fa/`
2. Ищет `object.__setattr__` вызовы
3. Проверяет `frozen=True` на всех `@dataclass` в TCB-файлах
4. Проверяет отсутствие `__post_init__` на замороженных dataclass в TCB
5. Генерирует `.fa/frozen_integrity_report.md`
6. Выходит с кодом 1 при нарушениях

**Kill-check:** Добавить `object.__setattr__(self, 'x', 1)` в TCB-файл → guard выходит с кодом 1.

---

### Шаг S22: Проверка ADR-11-I1 (stdlib-only) + max_retry (G5)

**Связь:** G3, G5, CT12, CT13
**Зависимости:** нет | **Параллельно с:** S19–S21, S23
**Живость:** L0→L3

**Файлы:**
- `scripts/check_tcb_stdlib.py` — НОВЫЙ (~20 строк)
- `src/fa/feature_flags.py` — добавить `max_retry: int = 5`
- `src/fa/inner_loop/coder_loop.py` — добавить guard

**check_tcb_stdlib.py:**
```python
"""Проверяет, что authoring_tcb.py импортирует только stdlib."""
import sys, ast
from pathlib import Path

STDLIB = sys.stdlib_module_names
tcb_path = Path("src/fa/authoring_tcb.py")
tree = ast.parse(tcb_path.read_text())
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split('.')[0] not in STDLIB:
                print(f"FAIL: non-stdlib import '{alias.name}' in TCB")
                sys.exit(1)
    elif isinstance(node, ast.ImportFrom):
        if node.module and node.module.split('.')[0] not in STDLIB:
            print(f"FAIL: non-stdlib import from '{node.module}' in TCB")
            sys.exit(1)
print("PASS: all TCB imports are stdlib")
```

**max_retry в FeatureFlags:**
```python
max_retry: int = 5  # Максимальное количество повторных попыток при ошибке API
```

**guard в coder_loop.py:**
```python
max_retry = state.feature_flags.max_retry if state.feature_flags is not None else 5
if attempt >= max_retry:
    break
```

**Kill-check:** Добавить `import requests` в authoring_tcb.py → check_tcb_stdlib.py выходит с кодом 1.

---

### Шаг S23: Видимость circuit-breaker при компакции (G11)

**Связь:** G11, CT2
**Зависимости:** нет | **Параллельно с:** S19–S22
**Живость:** L2→L3

**Файл:** `src/fa/inner_loop/coder_loop.py`, путь circuit-breaker

**Что добавить:**
```python
output.emit(OutputEvent(
    type="loop_warn",
    data={
        "detector": "compaction_circuit_breaker",
        "message": "Compaction circuit breaker triggered — context budget exceeded after compaction attempts"
    },
))
```

**Зачем:** Раньше circuit breaker срабатывал, но оператор не получал конкретного сообщения. Теперь получает loop_warn с объяснением.

---

### Шаг S24: Аудит сообщений об ошибках для не-RuleResult путей кода (G6)

**Связь:** G6 (переформулированный), CT4
**Зависимости:** нет | **Параллельно с:** S19–S23
**Живость:** L2→L3

**Файлы:** `src/fa/providers/*.py`, `src/fa/cli.py`, `src/fa/inner_loop/coder_loop.py`

**Что сделать:**

1. Запустить аудит:
```bash
grep -rn 'raise ValueError\|raise RuntimeError\|logger.error' \
  src/fa/providers/ src/fa/cli.py src/fa/inner_loop/coder_loop.py \
  | grep -v 'remediation\|expected\|got\|must be\|should be'
```

2. Для каждого попадания (~30 мест) переписать, включая: (1) что произошло, (2) почему, (3) как исправить.

**Пример:**
```python
# БЫЛО:
raise ValueError("invalid model")

# СТАЛО:
raise ValueError(
    f"invalid model slug {model_slug!r}: expected format 'provider/model-name', "
    f"got {model_slug!r}. Check ~/.fa/models.yaml role configuration."
)
```

---

### Шаг S25: Обновить I-TW-20 в SKILL.md + задокументировать None-окно output_bus

**Связь:** G12
**Зависимости:** S11 | **Параллельно с:** S24

**Что добавить:**

I-TW-20:
```
I-TW-20: Никогда не мокайте dataclass-объекты конфигурации (ChainConfig,
ChainEntry, CooldownRow, и т.д.). Используйте реальные экземпляры через
make_test_chain_config(). Мокайте только объекты с поведением
(ProviderChain, Provider, Transport).
Guard: scripts/check_no_mocked_dataclasses.py
```

Docstring для output_bus в state.py — документировать None-окно (период, когда output_bus ещё не инициализирован).

---

### Шаг S26: Верификация Фазы 5

Все контракт-скрипты → exit 0, все тесты → pass.

**Коммит:** `"feat: stats parsers, TRACE, frozen guard, error audit, dependency contract (F-7, F-8, F-9, G2, G3, G5, G6, G11, N-G1)"`

---

# ЧАСТЬ 5: ДОКАЗАТЕЛЬСТВА ЖИВОГО ПУТИ (LIVE-PATH PROOF)

## Основной продуктовый Anspruch: Типобезопасность LogKind

```
root: drive_session                    matrix: C (defaults)
test: tests/test_check_log_kind_contract.py  oracle: event kind+fields (ранг 1)
kill-check: удаление log.append продюсера → контракт-чек падает
producer: coder_loop.py:log.append     consumer: ConsoleRenderer._handle_*
paths-covered: 14/14 EventTypes + 30/30 LogKinds
contract-check: check_log_kind_contract.py PASS обязателен в CI
efficiency: n/a
pyramid: A
```

## Цепочка поставок TCB

```
root: check_dependency_contract.py    matrix: C (defaults)
test: tests/test_check_dependency_contract.py  oracle: exit code (ранг 2)
kill-check: добавление неизвестного dep в pyproject.toml → exit 1
producer: check script                consumer: CI gate
paths-covered: 1/1
contract-check: check_dependency_contract.py PASS обязателен в CI
pyramid: A
```

## Страж замороженных dataclass

```
root: frozen_guard.py                 matrix: C (defaults)
test: tests/test_frozen_guard.py      oracle: exit code (ранг 2)
kill-check: добавление object.__setattr__ в TCB → exit 1
producer: frozen_guard.py scan        consumer: CI gate
paths-covered: 75 frozen dataclass
pyramid: A
```

---

# ЧАСТЬ 6: РИСКИ, ОТКАТЫ, ОТКРЫТЫЕ ВОПРОСЫ

## Риски

| RK# | Риск | Смягчение | Обнаружение |
|---|---|---|---|
| RK1 | P2 LogKind: типизация append() вызывает ошибки в невидимых местах | Контракт-чек валидирует все продюсер-сайты; pyright проверяет | Ошибки pyright |
| RK2 | P3 типизация: потребитель ожидает `Any` и ломается на конкретном типе | Это желаемое поведение — типобезопасность ловит баги | Ошибки pyright, падения тестов |
| RK3 | P4 компакция SSoT: удаление флага меняет поведение для конфигов с `compaction_enabled=False` + threshold | `threshold=None` уже означает «нет компакции»; флаг был избыточен | grep подтверждает, что продакшн-код не читает `context_compaction_enabled` |
| RK4 | P4 зависимость TCB: блокировка deps ломает CI для легитимных обновлений | Флаг `--advisory-deps` для осознанных обновлений | CI failure при изменении dep |
| RK5 | P5 stats: elif-цепочки могут пропустить новые log kinds | LogKind контракт-чек ловит новые виды, не вошедшие в union | check_log_kind_contract.py |
| RK6 | P5 frozen guard: AST-сканер может давать ложные срабатывания на тестовых фикстурах | Исключить CORPUS_PREFIXES и тестовые директории | Вывод guard |

## Откаты

Каждая фаза независимо откатываема через `git revert`. Фичи-флаги не нужны для аддитивных изменений.

- **P1:** revert commit (чистый багфикс)
- **P2:** revert commit (аддитивно: LogKind — тип, контракт-чек — новый скрипт)
- **P3:** revert commit (только типы, нет изменения runtime-поведения)
- **P4:** F-10 — единственное семантическое изменение; откат возвращает флаговый затвор. G12: `--advisory-deps` восстанавливает старое поведение
- **P5:** всё аддитивно (новые скрипты, новые поля, новые доки)

## Открытые вопросы

**БЛОКИРУЮЩИЕ:** (нет — все архитектурные решения приняты)

**НЕБЛОКИРУЮЩИЕ:**

| Q# | Вопрос | Дефолт | Обоснование |
|---|---|---|---|
| Q1 | Должен ли frozen_guard.py сканировать `tests/` на `object.__setattr__`? | Нет — тестовые фикстуры могут легитимно тестировать мутацию. Сканировать только `src/fa/` | Тесты — не продакшн |
| Q2 | Должен ли check_dependency_contract.py сравнивать точные версии или диапазоны? | Диапазоны — точные версии требовали бы обновления контракта при каждом `uv lock` | Автоматизация удобнее |
| Q3 | Должны ли записи corrections.jsonl подписываться или хешироваться? | Нет — записи курируются человеком, нет модели угроз для целостности файла | Преждевременная оптимизация |

---

# ЧАСТЬ 7: ДИСПОЗИЦИЯ ИССЛЕДОВАТЕЛЬСКИХ ЗАМЕТОК

Каждая заметка из внешнего верификационного документа получает вердикт — не копируется слепо.

| RN# | Заметка | Вердикт | Почему | Якорь |
|---|---|---|---|---|
| RN1 | «7 EventTypes» (внешняя) | **Отклонить** | ОПРОВЕРГНУТО исходным кодом: 14 EventTypes. Все рекомендации, предполагающие 7-типовую модель, недействительны. | — |
| RN2 | «check_producer_consumer_contract.py не существует» | **Отклонить** | ОПРОВЕРГНУТО: скрипт существует, 206 строк, выходит с кодом 0. | — |
| RN3 | «57.5% сокращение нарушений» | **Отклонить** | НЕПРОВЕРЕНО — нет доступного источника. Исключено из всех оценок. | — |
| RN4 | «Авто-TRACE / самоулучшение» | **Отклонить** | Нарушает правило AGENTS.md #1 и project-overview.md §1.2.7. G2 — только human-mediated. | S20 |
| RN5 | «Сообщения об ошибках G6 уже хороши» | **Переписать** | RuleResult-сообщения хороши; не-RuleResult пути кода нуждаются в доработке. Переформулировать G6 для не-RuleResult области. | S24 |
| RN6 | «Import-linter как самостоятельный контроль» | **Отложить** | Неполно без N-G4 dynamic-import guard. Небольшая кодовая база не оправдывает новую зависимость. | — |
| RN7 | «G3 ADR-инварианты требуют выделенного контроля» | **Переписать** | Принцип вычитания: существующие механизмы покрывают ~85%. Одной проверки ADR-11-I1 достаточно. | S22 |
| RN8 | «Контекстный компилятор» | **Отложить** | Ручная консолидация навыков даёт тот же ~20% прирост без новой поверхности. | — |
| RN9 | «Компилятор поведенческих контрактов» | **Отложить** | C1-тесты + контракт-чек + mutmut уже обеспечивают kill-check-валидацию. | — |
| RN10 | «Страж замороженных dataclass» | **Принять** | Низкие усилия, высокая ценность, закрывает N-G1/N-G2, использует проверенный AST-паттерн. | S21 |
| RN11 | «Контракт зависимостей TCB» | **Принять** | Пользователь выбрал полный TCB-паттерн. Зеркалирует дизайн authoring_tcb.py. | S15 |
| RN12 | «G9 нужен пакетный скрипт» | **Переписать** | Проверка сокращения показала, что SessionDatabase.set_meta() уже существует. Расширить, не строить новое. | S9 |
| RN13 | «Discriminated union events в P6» | **Отложить** | Ограничение области: остановиться на P5. P6 отложен до отдельного плана. | — |
| RN14 | «Property-typed SessionState» | **Отложить** | Область P6. Фаза 3 типизирует поля; properties — последующее улучшение. | — |
| RN15 | «G4 инференциальные сенсоры (LLM-as-judge)» | **Отложить** | Высокая стоимость, высокие усилия. Не оправдано на ранней стадии разработки. | — |
| RN16 | «G12 просто сделать блокирующим» | **Переписать** | Пользователь выбрал полный TCB-паттерн с dependency_contract.toml. | S15 |
| RN17 | «Добавить read_flag() хелпер» | **Отклонить** | Проще использовать прямой доступ + None-проверка. Новая абстракция не нужна. | S13 |
| RN18 | «G13 runtime-утверждения в продакшн-коде» | **Переписать** | Гибрид: только CI для поведенческих контрактов + расширить существующие runtime guards. Без нового фреймворка. | S16 |

---

# ЧАСТЬ 8: ОПРЕДЕЛЕНИЕ ГОТОВНОСТИ (Definition of Done)

## Состояние

**До:** 14 EventTypes без типа LogKind; 9 полей `Any | None`; 12 getattr fallbacks; консультативная цепочка поставок; нет метрик ограждений; нет TRACE; нет frozen guard.

**После:** 14 EventTypes + 30 LogKinds оба Literal-типизированы; 0 `Any | None` на SessionState (кроме pty_pool); 0 getattr fallbacks; блокирующая цепочка поставок TCB; session_meta метрики при завершении сессии; corrections.jsonl + compile_corrections.py; frozen_guard.py.

**Наблюдать after-state:**
```bash
python scripts/check_log_kind_contract.py && \
python scripts/check_dependency_contract.py && \
python scripts/frozen_guard.py && \
python scripts/check_tcb_stdlib.py
```

## Артефакты

| Артефакт | Путь | Действие | Шаг |
|---|---|---|---|
| coder_loop.py (F-4 fix) | src/fa/inner_loop/coder_loop.py | edit | S1 |
| compactor.py (F-3 fix) | src/fa/inner_loop/compaction/compactor.py | edit | S2 |
| LogKind определение | src/fa/output.py | edit | S4 |
| CONSOLE_MIRROR_KINDS | src/fa/output.py | edit | S5 |
| EventLog.append типизация | src/fa/inner_loop/state.py | edit | S6 |
| check_log_kind_contract.py | scripts/check_log_kind_contract.py | add | S7 |
| SKILL.md I-TW-17 | knowledge/skills/tests-writing/SKILL.md | edit | S8 |
| session_meta метрики | src/fa/inner_loop/coder_loop.py | edit | S9 |
| fa stats --guardrail-metrics | src/fa/stats.py | edit | S9 |
| SessionState типизированные поля | src/fa/inner_loop/state.py | edit | S11 |
| FAIL_CLOSED/OPEN флаги | src/fa/feature_flags.py | edit | S13 |
| getattr замены | 6 файлов | edit | S13 |
| компакция SSoT | src/fa/inner_loop/coder_loop.py | edit | S14 |
| dependency_contract.toml | .fa/dependency_contract.toml | add | S15 |
| check_dependency_contract.py | scripts/check_dependency_contract.py | add | S15 |
| check_protected_paths.py update | scripts/check_protected_paths.py | edit | S15 |
| поведенческие утверждения | tests/test_inner_loop_loop_guard.py | edit | S16 |
| LOGIC-10 abnormal_stop | src/fa/inner_loop/coder_loop.py | edit | S17 |
| stats парсеры | src/fa/stats.py | edit | S19 |
| corrections.jsonl | .fa/corrections.jsonl | add | S20 |
| compile_corrections.py | scripts/compile_corrections.py | add | S20 |
| frozen_guard.py | scripts/frozen_guard.py | add | S21 |
| check_tcb_stdlib.py | scripts/check_tcb_stdlib.py | add | S22 |
| max_retry поле | src/fa/feature_flags.py | edit | S22 |
| compaction circuit-breaker | src/fa/inner_loop/coder_loop.py | edit | S23 |
| аудит ошибок | providers/*.py, cli.py, coder_loop.py | edit | S24 |
| SKILL.md I-TW-20 | knowledge/skills/tests-writing/SKILL.md | edit | S25 |
| output_bus docstring | src/fa/inner_loop/state.py | edit | S25 |

## Контракты

Все 13 контрактов (CT1–CT13) должны пройти путь: PLANNED → IMPLEMENTED → VERIFIED.

**План ГОТОВ только когда:** все G# достигли L3, все артефакты существуют, LIVE-PATH PROOF блоки зелёные, матричное/путевое покрытие держится, не-цели соблюдены, все RN# диспозиционированы.

---

# ЧАСТЬ 9: АНТИТЕАТР + READY GATE

## Чек-лист антитеатра

- [x] Каждый упомянутый символ верифицирован через preflight или помечен NEW
- [x] Каждый G# маппится на ≥1 CT# и ≥1 S# и ≥1 верификацию (нет сирот)
- [x] Каждый сигнальный CT# имеет И продюсера, И консьюмера, или явный defer
- [x] Каждый kill-check нацелен на ПРОДЮСЕРА, никогда на консьюмера одного
- [x] Инвентарь путей (§4.1) не имеет непокрытых путей без явной не-цели
- [x] Матрица (§4.2) имеет ≥1 покрывающий шаг на строку или явное «N/A — почему»
- [x] Dual-write каналы верифицированы консистентно по каждому пути
- [x] Фикстуры/типы в плане верификации честные (реальные типы, не ослабленные моки)
- [x] Нет расплывчатых глаголов без конкретного механизма
- [x] Допущения помечены (ASSUMPTION: ChainConfig всегда имеет context_limit/compaction_threshold)
- [x] Контракты безопасности имеют ≥1 адверсальный пример
- [x] Все ID-ссылки резолвятся — нет висящих S#/CT#/G#/Q#/RN#/RK#

## READY GATE

- [x] Preflight log на месте и нетривиален
- [x] Глубина P3 объявлена и соответствует фактической области
- [x] Executive intent, не-цели, текущее/целевое состояние — все конкретны
- [x] Все применимые подтипы контрактов (§6) на месте
- [x] Покрытие путей + матрицы удовлетворено
- [x] Каждый шаг — файл:символ с критериями выхода
- [x] План верификации + LIVE-PATH PROOF на месте для каждого продуктового утверждения
- [x] Чек-лист антитеатра полностью выполняется
- [x] Исследовательские заметки полностью диспозиционированы (18 элементов)
- [x] Набор БЛОКИРУЮЩИХ открытых вопросов ПУСТ
- [x] Все ID резолвятся

**Статус: READY** ✅

---

*Документ составлен: 2026-07-19. Перевод и развёртка оригинального плана PLAN-guardrail-gap-closure.md с включением исправлений из корригендума §21 внешнего верификационного документа. Все факты верифицированы против исходного кода на ветке `main`.*
