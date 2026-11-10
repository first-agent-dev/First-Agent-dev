# Q#5 — `context_budget_hard_stop` пишется в двух разных схемах

**Дата:** 2026-11-10. **Статус:** ЗАКРЫТ 2026-11-10 — решение оператора: **A′** (схема вердикта,
`message` остаётся текстом брейкера, нового поля нет). Исправлено единым
билдером `ContextBudget.hard_stop_row`; все три сайта переведены на него.
Найдено при подготовке шага 3 (перенос compaction), подтверждено настоящим
парсером `fa stats`.

## Что случилось

`log.append(kind="context_budget_hard_stop", …)` встречается в драйвере четыре
раза, и содержимое у них не одно и то же:

| Сайт | Что пишется | Ключи |
| --- | --- | --- |
| stage-3 без compaction (L1104) | `content=decision` | 9: `action`, `ratio`, `message`, `current_tokens`, `limit_tokens`, `threshold`, `stage2_threshold`, `stage3_threshold`, `warning_threshold` |
| stage-3 без compaction (L1113) | `run_stopped` | — |
| **circuit breaker (L1357)** | **свой dict** | **4: `message`, `current_tokens`, `limit_tokens`, `threshold`** |
| stage-3 после compaction (L1416) | `content=decision` | 9 |

## Почему это дефект, а не стиль

`src/fa/stats.py:542` читает этот kind так:

```python
elif kind == "context_budget_hard_stop":
    context_budget_events.append(
        ContextBudgetEvent(
            action="hard_stop",
            pct=float(content.get("ratio", 0.0)) * 100,   # ← у circuit breaker ключа нет
            message=str(content.get("message", "")),
        )
    )
```

Живой прогон драйвера (`tests/fixtures/budget_effects_probe.py`, кейс
`circuit_breaker`) даёт строку **без ключа `ratio` вообще**:

```
{'message': 'Compaction circuit breaker triggered: anti-thrashing loop locked.',
 'current_tokens': 94000, 'limit_tokens': 100000, 'threshold': 80000}
```

Для сравнения, соседний кейс `stage3_after_compaction` пишет 9 ключей с
`'ratio': 0.92`.

Прогон двух строк через `_parse_events`:

```
action='hard_stop'  pct=95.0   message='critical 95%'
action='hard_stop'  pct=0.0    message='Compaction circuit breaker triggered: anti-thrashing lo'
```

То есть в сводке по сессии самый тяжёлый выход (сработавший анти-трэшинг)
выглядит как **0% контекста**, хотя контекст был переполнен — именно это и
включило breaker. `get("ratio", 0.0)` — тихий дефолт: строка есть, значение
ложное.

Это тот же класс, что Q#4: отчётное поле описывает не то состояние, по которому
принято решение. Q#4 починили в `context_warn`; durable-строка circuit breaker
осталась.

## Почему не исправлено сразу

Правка — три строки, но она меняет **durable-схему** (`context_budget_hard_stop`
у circuit breaker с 4 ключей на 9), а это контракт: строку читают `fa stats`,
`session_summary`-метрики и рендереры. По правилу «новая политика → Q#» выбор
не технический:

1. **Привести к 9 ключам** (как остальные три сайта): пишем `action="stage3"`,
   `ratio=verdict.ratio` (пост-компакция, см. Q#4), остальные пороги — из
   `budget`. Тогда `pct` честный, схема одна на все сайты.
2. **Оставить 4 ключа, научить `stats` отличать**: `pct` для breaker'а брать из
   `current_tokens / limit_tokens` — но это второй источник истины для того же
   числа, ровно тот дубль, который мы убирали в шагах 1–2.
3. **Оба поля** (`ratio` и `circuit_breaker: true`) — меняет схему сильнее всех
   и требует согласования с рендерерами.

Вариант 1 согласуется с решением оператора по Q#4 (отчётное число = состояние,
по которому принято решение) и убирает расхождение схем, а не маскирует его.

## Решение (A′) и что именно сделано

Оператор выбрал **A′**: единая схема вердикта (9 ключей), верхняя строка
`message` остаётся текстом брейкера, нового поля (`cause`/`circuit_breaker`) нет.

Почему A′ лучше чистого A: `stats.py:842` печатает `message[:60]`, значит
замена текста на «Context budget critical: 94000 tokens…» убрала бы из сводки
единственное объяснение, *почему* сессия умерла. Почему лучше C: различать
причину уже есть где — соседняя строка `compaction_circuit_breaker`; флаг-поле
в durable-схеме пришлось бы расширять на каждый следующий сайт.

Что сделано:

* `ContextBudget.hard_stop_row(current_tokens, *, message)` — единственное место,
  где собирается payload. `ratio` считается из `current_tokens`, `action` и
  пороги — из того же `check()`, что и решение. Билдер живёт в
  `context_budget`, а не в драйвере, потому что формула `ratio` уже там.
* три сайта (`stage-3 без compaction`, `circuit breaker`, `stage-3 после
  compaction`) пишут через него;
* `tests/test_q5_hard_stop_row.py` — 5 тестов: поведение в живом цикле
  (94%/92%/95%), два теста на билдер (таблица по всей лестнице) и **AST-контракт
  «ни одного литерального payload»**, чтобы четвёртый сайт не смог повторить
  дефект. Мутанты 4/4: вернуть 4 ключа руками, убрать подмену `message`,
  считать `ratio` от порога, подставить чужой message на сайте.

Зонд до/после подтвердил дельту размером в одну строку: в кейсе
`circuit_breaker` добавились `action`, `ratio: 0.94`, `stage2_threshold`,
`stage3_threshold`, `warning_threshold`, а `threshold` изменился 90000 → 80000
(теперь он означает то же, что у соседних сайтов). Остальные шесть кейсов и все
console-события не изменились. В сводке `hard_stop` стало `94%` вместо `0%`.

## Что это блокировало

Шаг 3 переносит этот сайт в `compaction_turn.py`. Если переносить «байт-в-байт»
— дефект переезжает и закрепляется тестом. Если чинить в том же срезе — срез
меняет durable-схему, то есть перестаёт быть «только переносом». Поэтому шаг 3
делается с сохранением текущего поведения, а схема приводится отдельным
маленьким срезом сразу после (или до) него — по решению оператора.
