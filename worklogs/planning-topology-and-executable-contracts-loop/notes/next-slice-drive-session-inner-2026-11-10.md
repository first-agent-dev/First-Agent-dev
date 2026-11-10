# Следующий срез: `_drive_session_inner` — что именно в нём переусложнено

**Дата:** 2026-11-10. Состояние: HEAD `0b57d48`. Измерения — AST, не глазомер.

## 1. Где сейчас сложность

| Метрика | Значение | Комментарий |
| --- | --- | --- |
| `coder_loop.py` | 1719 строк | крупнейший файл в `inner_loop` после `workflow_controller`/`slice_verification` |
| `_drive_session_inner` | **1083 строки** (626–1708) | функция-драйвер |
| C901 `_drive_session_inner` | **68** (порог 15) | подавлен `# noqa` на строке 626 |
| C901 остальных в файле | 9, 5, 5, 5, 2, 2, 2, 1, 1 | всё остальное — далеко от порога |
| `If` / `Try` / `For` / `BoolOp` / `IfExp` в драйвере | 43 / 10 / 6 / 8 / 14 | 43 `if` — это и есть 68 цикломатики |
| Тело `while` (816 строк) | **31** оператор верхнего уровня | из них 4 блока съедают 78% |

### Четыре блока, которые держат сложность

| Строки | Строк | Ветвлений внутри | Что это |
| --- | --- | --- | --- |
| 1070–1450 | **380** | **29** | бюджет + compaction (весь блок `if budget_enabled`) |
| → 1074–1450 | 376 | 28 | ветка `warn`/`stage2`/`stage3` |
| → 1120–1450 | 330 | 24 | «compaction выключена» / «включена» |
| → 1231–1425 | 194 | 16 | `stage3` внутри включённой compaction |
| 1468–1608 | 141 | — | provider request + обработка ошибок цепочки |
| 963–1003 | 41 | — | pinned-buffer извлечение + `__debug__`-проверка |
| 1022–1052 | 31 | — | локальный `_compose_request_payload` (замыкание на каждый turn) |

**Вывод:** 380 из 1083 строк и 29 из 68 ветвлений — один блок. Всё остальное в драйвере уже читается как маршрут.

## 2. Почему это дороже, чем «просто длина»

1. **Пять выходов из сессии внутри одного блока** (warn→нет, stage2-без-compaction→нет, stage3-без-compaction→exit 1, circuit-breaker→exit 1, stage3-после-compaction→exit 1). Пока они лежат внутри 380 строк, любой из них легко «выпадает» из общего поведения — ровно это и случилось в S6-F5 и в `iteration_cap`.
2. **Порядок эффектов обязателен и не выражен типом:** `log.append` → `output.emit` → (возможно) `finish`; compaction может переписать `messages_payload`, `conversation_history`, `memory_summary`, `usage`, `decision` — и после этого снова проверяется `stage3`.
3. **`last_budget_ratio` обновляется не на всех ветках** (см. §18.5 плана): это состояние, которое переживает блок, но семантически принадлежит ему.
4. **Broad `try` вокруг stage2** и его маскировка (`compaction_stage2_error`) — единственное место, где исключение не всплывает наружу; при переносе это первое, что теряется.

## 3. Предлагаемая последовательность (не один срез)

### Шаг 1 — вынести бюджетное *решение* (без эффектов)

```python
@dataclass(frozen=True)
class BudgetVerdict:
    action: str          # "ok" | "warn" | "stage2" | "stage3"
    ratio: float
    usage: int
    compaction_enabled: bool
    threshold: float
    message: str
```

Чистая функция `classify_budget(decision, budget, compaction_threshold) -> BudgetVerdict`. Никаких `log.append`, `emit`, `finish`. Проверка: `test_s14_compaction_ssot.py` + новый C0 на таблицу переходов. Это снимает ~10 ветвлений и делает «что решили» отделимым от «что сделали».

### Шаг 2 — вынести эффекты одного решения

`_apply_budget_verdict(verdict, ...) -> BudgetEffect` с явными полями: `may_stop: bool`, `stop_message: str`, `compacted: bool`, новые `history`/`summary`/`usage`. Внутри — те же `log.append`/`emit` в том же порядке. Проверка: `test_observability_fix_p4.py`, `test_s23_circuit_breaker_loop_warn.py`, `test_s6_path_completeness.py` (per-site pairing — уже научен разрешать хелперы), плюс C1 на каждый из пяти выходов.

### Шаг 3 — перенести compaction в `compaction_turn.py`

Только после шагов 1–2: тогда у функции уже есть вход (verdict) и выход (effect), и перенос не тащит 380 строк разом.

## 4. Чего делать не надо (и почему)

- **Не резать «до-llm/hook» части** (963–1003, 1022–1052): 41+31 строка, высокая связность с окружающим маршрутом, выигрыш по C901 ~4. Это та же ошибка, что «10 перенесённых единиц» из §17.7 — движение без снижения сложности.
- **Не снимать `# noqa: C901`** до шага 2: пока в драйвере 43 `if`, порог 15 недостижим, а подавление с честным комментарием лучше, чем дробление ради метрики.
- **Не вводить `SessionContext`** как мешок — уже отклонено в Q#2 (см. `q2-session-accounting-review-2026-11-10.md`).

## 5. Оракулы, которые уже есть и которые придётся не сломать

`test_s14_compaction_ssot.py` (пять выходов), `test_s23_circuit_breaker_loop_warn.py` (circuit breaker), `test_observability_fix_p4.py` (`context_warn` на всех порогах), `test_s6_path_completeness.py` (per-site pairing + floor), `test_s14_compaction_c1.py`, `test_pr1_wiring.py`/`test_pr4_wiring.py`, `test_coder_loop.py` (маршрут), `test_stats.py` (вердикт в summary).

## 6. Ограничения

- Полный гейт прогнан один раз на `0b57d48`: 4 из 8 гейтов зелёные, 4 падают на предсуществующих проблемах (pylint cyclic-import в `fa.execution`, `IsolatedWorktreeManager` без `__all__`, 37 тестов, не связанных со слайсом). Подробности — в отчёте ниже.
- Живой провайдер не проверялся (`L-RCPT-2/6`, `L-ENTRY-4` — NOT RUN).
