# E2E план: ledger-append для stage-2/3 compaction и hard-stop

**Дата:** 2026-11-10. Срез: `4571abe` (stage-2) + `2ca297f` (stage-3).
**Статус:** план. Живой прогон не выполнялся — L-RCPT-2/6 и L-ENTRY-4 по-прежнему NOT RUN.

## Зачем отдельный E2E

Юнит-тесты проверяют, что модуль пишет строки и события. Они **не** проверяют,
что строка доезжает до авторитетного хранилища:

`EventLog.append` устроен в три шага (`src/fa/inner_loop/state.py:241`):

1. `session_db.append_event_row_allocating(...)` — авторитетная запись, id
   выделяет база; исключение здесь не глотается, событие не теряется молча;
2. счётчики `kind_counts` двигаются **после** коммита;
3. best-effort JSONL-зеркало, ошибки которого только логируются.

То есть «строка в `read_all()`» и «строка пережила процесс» — разные
утверждения. В юнит-тестах `tmp_path`-база живёт ровно столько же, сколько
тест; E2E должен проверить переживание границы процесса и то, что `fa stats`
читает ровно то, что записал драйвер.

## Что именно проверяется (по сценариям среза)

| # | Сценарий | Что должно остаться в ledger после процесса |
| --- | --- | --- |
| E1 | warn rung | `context_budget_warn` (9 ключей) |
| E2 | stage-2 disabled | `compaction_warning` + `context_budget_warn` |
| E3 | stage-2 enabled | `compaction_stage2_start/done`, `compaction_end` в JSONL |
| E4 | stage-3 disabled | `compaction_warning`, `context_budget_hard_stop` (9 ключей), `run_stopped` |
| E5 | stage-3 после compaction | `compaction_stage3_start/done` + `context_budget_hard_stop` с `ratio` **пост-компакции** (92, не 99) |
| E6 | breaker | `compaction_circuit_breaker`, `context_budget_hard_stop` (9 ключей, `ratio` есть), `run_stopped` |

## Шаги (на живом хосте)

1. `fa` установлен в чистом venv; `--frozen`, пины не трогаем.
2. Прогон драйвера через CLI с детерминированным провайдером-заглушкой
   **вне** процесса теста (subprocess), `max_turns=1`, фиксированный
   `run_id`. Для E5/E6 нужна предзаполненная история (≥7 парных
   `model_msg`/`tool_result`) — иначе stage-3 нечего компактить.
3. Процесс завершается; **новый** процесс читает ledger:
   `fa stats --run-id <id> --json` и сравнивает с ожидаемым.
4. Проверки: `pct` в `stats` равен записанному `ratio*100` (Q#4/Q#5),
   `kind_counts` в `session_meta` совпадает с числом строк по kind (шаг 2
   `append`), JSONL-зеркало содержит те же `event_id`.
5. Отрицательный прогон: E5 с фиксом отката (`last_budget_ratio` не
   принимается) должен дать 99 — иначе тест не различает состояния.

## Почему это не в PR сейчас

- Нужен живой провайдер/стенд: локально доступен только детерминированный
  фейк, а такой прогон почти повторяет уже написанный `drive_session`-тест;
- журнал E2E-статусов ведётся отдельно (L-RCPT-2/6, L-ENTRY-4) и не должен
  получать «passed» из песочницы.

## Что закрывает пробел, уже сейчас

`tests/test_compaction_turn_stage3.py::test_driver_stops_with_the_post_compaction_percentage`
— это E2E-по-смыслу minus граница процесса: реальный `drive_session`, реальный
`EventLog` с SQLite-авторитетом, проверка `session_end.context_used_pct == 92.0`.
Он ловит Q#4-регрессию (мутант «не принимать `stage3.verdict.ratio`» убит).
