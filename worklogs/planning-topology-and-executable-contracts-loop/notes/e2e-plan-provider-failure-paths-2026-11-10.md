# E2E план: провайдерские сбои через границу процесса

**Дата:** 2026-11-10. Срез: `ab40815` (provider failures) + `7064ca5` (унификация
shape-отчёта). **Статус:** план. Живой прогон не выполнялся.

Сопутствующий план: `e2e-plan-ledger-append-stage3-2026-11-10.md` — там про
budget/compaction. Этот файл — про три исхода провайдерского сбоя: `chain_exhausted`,
`request_shape`, `abnormal_stop:interrupt`.

## Зачем отдельный E2E

Юнит-тесты (`test_provider_failures.py`, `test_provider_turn.py`) проверяют решение
и строки в `read_all()` + `session_meta` внутри процесса. Они **не** проверяют то,
что видит оператор и что переживает процесс:

1. **exit code процесса** — `fa run` возвращает `outcome.exit_code`
   (`cli.py:1945 _run_exit_code`); 2 и 130 — это то, на что смотрит CI и обёртки.
2. **строки после падения процесса** — `EventLog.append` пишет в SQLite-авторитет
   и потом в JSONL-зеркало (`state.py:241`); «строка в `read_all()`» и «строка
   пережила процесс» — разные утверждения.
3. **`fa stats --run-id … --json`** в **новом** процессе читает ровно то, что
   записал драйвер: `run_stopped.reason`, счётчики по kind'ам.
4. **`session_meta.chain_exhaustion_events`** — значение, у которого до этого среза
   не было ни одного сквозного теста на ненулевой величине (см. `test_s9`, он
   гоняет чистую сессию, где 0 получается при любом коде).

## Сценарии

| # | Сценарий | Инъекция | Ожидание после процесса |
| --- | --- | --- | --- |
| F1 | исчерпание без ретраев | провайдер отдаёт 503 на все попытки, `max_chain_retries=0` | exit **2**, `stop_reason=chain_exhausted`, `run_stopped.reason=chain_exhausted` с `detail`, `chain_exhaustion_events == 1`, `provider_attempt` присутствует |
| F2 | исчерпание с одним ретраем | то же, `max_chain_retries=1`, `max_turns>=3` | exit **2**, `turns == 2`, `chain_exhaustion_events == 2` (счётчик считает события, не ретраи) |
| F3 | request_shape (провайдерский) | провайдер отдаёт 400/422 | exit **2**, `stop_reason=request_shape`, `run_stopped.detail` содержит текст провайдера, `chain_exhaustion_events == 0` |
| F4 | request_shape (композиционный) | история с висящим `tool_call` (resume) | exit **2**, `request_shape`, провайдер **не вызывался** (нужен счётчик вызовов в стенде) |
| F5 | interrupt | провайдер бросает `KeyboardInterrupt` | exit **130**, `stop_reason=abnormal_stop:interrupt`, `chain_exhaustion_events == 0` |
| F6 | headless (нет `--output`) | как F1, без консоли | строки те же; консольных `api_retry` нет, `run_stopped` есть |

## Шаги (на живом хосте)

1. `fa` в чистом venv, пины не трогаем; детерминированный провайдер-заглушка
   поднимается **вне** процесса теста (subprocess), фиксированный `run_id`.
2. Запуск с `--output console` и `--output json` (F6 — без вывода).
3. Проверка `$?` процесса против ожидаемого exit code.
4. **Новый** процесс: `fa stats --run-id <id> --json` → `run_stopped`, счётчики.
5. Чтение `session.db` (`session_meta`) → `chain_exhaustion_events`, `kind_counts`.
6. Сверка JSONL-зеркала с SQLite по `event_id` (как в stage3-плане).

## Отрицательные прогоны (иначе тест не различает состояния)

- **F1'**: убрать `log.chain_exhaustion_count += 1` → `chain_exhaustion_events`
  должен стать 0, а F1 упасть. Внутрипроцессно это уже доказано мутацией;
  E2E должен подтвердить, что значение доезжает до `session_meta` после процесса.
- **F3'**: переставить проверку `ProviderChainExhaustedError` выше
  `ProviderRequestShapeError` → `stop_reason` станет `chain_exhausted` при exit 2.
  **Важно:** exit code при этом не меняется (оба 2), поэтому проверять надо
  именно `stop_reason` — это ровно та ловушка, которую я держал в
  `test_shape_failure_is_not_mistaken_for_exhaustion`.
- **F5'**: убрать ветку `KeyboardInterrupt` → процесс завершится трассировкой
  (код 1 или 130 от Python), а `run_stopped` не появится.

## Почему не в PR сейчас

- нужен стенд с провайдером вне процесса; локально доступен только
  детерминированный фейк;
- журнал E2E-статусов (`e2e-live-verification-register.md`) не должен получать
  «passed» из песочницы.

## Что уже закрыто без границы процесса

- `test_provider_failures.py` — таблица исходов, порядок эффектов, парность,
  инкремент счётчика на обоих путях;
- `test_provider_failures.py::test_exhaustion_count_reaches_the_session_end_metric`
  — сквозь `session_meta` на реальном `SessionDatabase` (закрывает дыру `test_s9`);
- `test_provider_turn.py` — делегирование драйвера для всех четырёх исходов,
  включая композиционный `request_shape` до HTTP;
- зонд `probe_failures.py` — таймлайн «строка ↔ событие» в одном списке,
  сверенный с ревизией до среза.
