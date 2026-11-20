# Практический маршрут: зелёный repair-slice, W3 и один C901-кандидат

**Дата:** 2026-11-10 · **Наблюдавшийся HEAD:** `5053cb3` · **Ветка:** `arena/e3879a47-first-agent-dev`

Это рабочая запись для следующего локального среза. Она отделяет три разных
утверждения: устранённую ошибку тестового окружения, результаты выбранных W3
гейтов и будущий узкий C901-рефактор. Ни одно из первых двух само по себе не
закрывает W3.

## Правило решения

1. Сначала классифицировать **первую причину отказа**, а не чинить последнюю
   строку trace. Если тест intended-to-test штатное managed-поведение, но
   fixture не предоставляет обязательный managed setup, исправить fixture;
   не ослаблять product refusal, не подменять assertion на «запустилось» и не
   называть тест environment-only, пока он не проходит тем production path,
   который ему нужен.
2. Записывать отдельно, что тест реально использует: production entry/caller,
   настоящий SessionManager/SQLite или authority, test double, provider stub и
   фактический effect/no-effect oracle. Test-only provisioner или stage adapter
   не является доказательством managed file IO, authority custody или host
   acceptance.
3. W3 считать закрытым только по его полному STEP/DoD набору на согласованном
   candidate SHA. Зелёные 39 ранее классифицированных тестов, зелёный combined
   live-gate прогон, локальные type/authoring checks и отдельные C1 — это
   необходимые свидетельства по своим швам, но не заменяют `just check-deep`,
   недостающие STEP9 deliverables, independent review и host `fa update`.
4. C901 исправлять только когда есть реальный сложный участок и проверяемая
   ответственность. Выбрать **один** кандидат, провести его отдельным узким
   code diff, не совмещать с распутыванием `_drive_session_inner` и не поднимать
   `max-complexity`/добавлять waiver ради зелёного Ruff. Если безопасное
   разделение требует смены поведения или не удаётся сохранить внешний
   контракт — остановиться, а не «дробить ради числа».

## 1. Сверка ранее зелёной группы

Историческая классификация выделила 39 class-A случаев: 28 failed + 11 errors,
вызванных тем, что session-backed `_cmd_run` доходил до
`SessionManager._new_session` без обязательного provisioner/preparer и получал
штатный `managed_execution_unavailable`. В текущем checkout десять owning-модулей
запущены целиком:

```bash
uv run pytest \
  tests/test_s10b_cli_parity.py tests/test_s10a_cli_coverage.py \
  tests/test_s10c_artifact_posture.py tests/test_s7_correlation.py \
  tests/test_s9_stats_projection.py tests/test_s7_cli_run_paths.py \
  tests/test_scope_hint_cache_key.py tests/test_readiness_announcement.py \
  tests/test_iteration_cap.py tests/test_workflow_global_history.py -q
```

Результат: **179 passed in 25.91s**. Это прогон десяти полных файлов, а не
утверждение, что ровно 39 тестов было запущено отдельно. Набор содержит
историческую class-A группу; исходные `39` — число прежних failing/error
nodeids, не размер всей этой выборки.

### Что делает fixture и что не делает

Тесты, которым нужен session-backed run, используют общий test-only helper
`tests/test_cli.py::_install_test_managed_cli_dependencies` (через локальные
`_cli_home(..., session_backed=True)` / `_fa_home(...)` helpers):

- задают временные `HOME`/state/workspace roots;
- используют настоящий `SessionManager` и настоящую SQLite/session lifecycle;
- предоставляют readiness stub с `ReadyStatus.READY` и test provisioner для
  временного workspace, чтобы тест дошёл до задуманного поведения;
- подменяют managed execution / stage boundary тестовым адаптером и подают
  scripted provider response; этот путь годится для утверждений о жизненном
  цикле, событиях, prompt/output и projection, но **не** доказывает authority
  или managed file-tool IO.

Покрываемые наблюдаемые поведения по owning suites: CLI stdout/artifact parity;
private artifact posture; session/run/event correlation; S9 stats projection и
согласование с global-history row; выбор CLI workspace и отсутствие утечки
session state; scope-hint prompt/cache contract; readiness announcement;
iteration-cap events/stop behavior; workflow/standalone global-history rows.
У каждого такого теста остаётся собственный oracle; fixture не подменяет его.
Для настоящей authority/managed-view границы используются отдельные
`test_execution_composition` C1 tests.

В текущем рабочем diff нет прямых правок этих десяти class-A модулей: общий
managed-setup helper уже присутствует в checkout. Не приписывать все 179
результатов новым fixture edits этого среза. Отдельно, текущие изменения
`tests/test_verify_gate_live.py` заменяют неполную SessionManager setup на
общий managed fixture и добавляют test-only parent-stage lease для acquisition
handoff cases; `tests/test_cli.py::_TestCliManagedClient.handoff` моделирует
сгенерированный owner grant. Это поддерживает нужные CLI lifecycle tests, но
lease/client double не является настоящим authority и не доказывает view IO.

## 2. Combined W3 live-gate результат и граница

Команда ниже была выполнена отдельно, одним pytest invocation:

```bash
uv run pytest tests/test_verify_gate_live.py tests/test_s10a_cli_coverage.py -q
```

Результат: **634 passed in 298.73s**, без skip/xfail в выводе этой команды.
`test_s10a_cli_coverage.py` намеренно перекрывается с десятифайловым прогоном;
суммировать `179 + 634` как число уникальных тестов нельзя. Combined invocation
подтверждает, что текущие verify-gate и S10a selections вместе исполняются и
зелёные на этом checkout. Это не замена полному W3 bank и не доказательство
каждого W3 exit criterion.

Дополнительные текущие результаты: после managed multi-publication C1 замены
старого host-write xfail `tests/test_execution_composition.py` вместе с
`tests/test_controller_installed.py` — **92 passed**; acquisition/provenance
bank — **49 passed**; CLI/invoke workflow — **179 passed**; full
`pyrefly check` — 0 errors; `fa authoring-check` — 0 diagnostics; два целевых
entrypoint tests — **2 passed**. Само значение каждого результата ограничено
названным suite. `just check-deep`, полный W3 signoff и host deploy этим не
выполнялись.

STEP9 остаётся **OPEN**. Среди явно не закрытых пунктов: `tests/integration/`
ещё отсутствует; S6P5/S6P7/S6P8/S6P9/S6P10 и `just check-deep` не завершены;
Q108 `NEW:`→`I03-LIVE-S08` mapping и Q139 mutmut calibration не закрыты;
approved Q97 profile check, independent review/run sheet и host `fa update` не
проведены. **STEP9A не начинать до закрытия STEP9.** Исторические два
`uv sync`/CPython download ошибки из class-B в §7 старой карты не повторялись в
этом checkpoint: считать их neither fixed nor current failure без нового
диагностического прогона. Никакой candidate `fa update` или W4 acceptance не
заявляется.

## 3. Выбранный следующий C901-срез: `stats._parse_events`

Source-grounded preflight в текущем checkout:

- `src/fa/stats.py::_parse_events` — **C901 45 при лимите 15**; это единственный
  C901 finding в `stats.py` при `ruff check src/fa/stats.py --select C901
  --ignore-noqa`.
- Функция — настоящий JSONL/SQLite event consumer; её зовут `parse_session` и
  `parse_session_db`, а CLI stats path формирует наблюдаемый `fa stats --json`
  результат. Это реальный кандидат, не перенос сложности из функции ради
  метрики.
- До изменений текущие parser/stats/projection suites дали **51 passed**:
  `tests/test_s19_stats_parsers.py`, `tests/test_stats.py`,
  `tests/test_s9_stats_projection.py`.
- Важный существующий контракт: `PARSED_KINDS` равен kinds, реально
  диспетчеризуемым парсером (24); текущий AST test извлекает ветви из тела
  `_parse_events`. При выносе event dispatch этот контроль нужно перенастроить
  на все выделенные dispatch helpers, сохранив exact set и liveness assertion,
  не удаляя его и не заменяя независимым literal.
- Обнаружена mutation-selection дыра: `src/fa/stats.py` уже входит в
  `[tool.mutmut].source_paths`, но `pytest_add_cli_args_test_selection` не
  содержит stats-owning suites. В selection добавлены и в
  `tests/test_slice_mutmut.py` закреплены непосредственные владельцы контракта:
  `tests/test_stats.py`, `tests/test_s19_stats_parsers.py`,
  `tests/test_s9_stats_projection.py`. S10a/S10b compatibility modules
  остаются обязательными отдельными pre-mutation oracles, но не включаются в
  каждый mutant run: полный `test_s10a_cli_coverage.py` содержит
  `test_s10a_authoring_check_runs_on_a_real_workspace`, который предполагает
  полный checkout и не исполняется внутри mutmut partial overlay (ошибка была
  на отсутствии `knowledge/llms.txt`, не на stats behavior). Целевой mutation
  selection должен содержать только эти три stats-owning файла, чтобы мутанты
  не проверялись нерелевантным банковским набором и не выдавались no-tests /
  infra failure за kills. Это исправление test selection, не изменение
  продукта или W3 policy.

### Порядок исполнения

1. Зафиксировать baseline команды, C901 score и полный внешний контракт до
   правки. Baseline зафиксирован выше.
2. Перед кодом повторно прочитать event dispatch, `SessionAnalytics`,
   `parse_session(_db)`, `_cmd_stats`, fixture/oracle source. Не менять
   production entrypoint и DB schema.
3. Разбить только по имеющим смысловую границу группам event kinds. Сохранить
   отдельный parse state на один вызов; никакой module-global mutable state,
   общих side-effect sinks или параллельной перестановки событий.
4. Сохранить без изменений public dataclasses, функции, поля JSON output,
   parsed/unparsed kind set, `None` vs structured source errors, stop/verdict
   precedence (`session_summary`/`run_stopped`/iteration-cap), counts, sorting,
   per-run filtering и legacy JSONL compatibility.
5. До mutation запускать parser contract suite (`test_stats`, `test_s19`,
   `test_s9`) и CLI compatibility oracles (`test_s10a`, `test_s10b`), а не
   только helper unit tests. `test_s9_authority_and_projection_agree` и
   `test_s10a_stats_renders_a_real_session` проверяют persisted DB→projection;
   `test_s10b_stats_parity_single_session_json_shape` pins single-session JSON
   shape versus aggregate. Существующие тесты остаются; не ослаблять их ради
   рефактора.
6. Сверить C901 на изменённом файле: ни одна новая функция не выше 15, не
   добавлять `noqa`/complexity waiver. Запустить Ruff, Pyrefly/mypy scope и
   связанные tests.
7. Выполнить targeted mutmut только по `src/fa/stats.py`, с явными stats-owning
   test selection и сохранёнными артефактами; `no_tests`, skipped/timeout,
   type-invalid и survivors классифицировать отдельно, ни один не выдавать за
   kill. Дополнительно проверить BODY (убрать реальную parsed-kind обработку →
   точный assertion падает) и EDGE (убрать вызов dispatch helper из parser
   loop → соответствующий production-projection test падает), затем
   побайтно восстановить источники.
8. Если baseline/test selection не выполняется, compatibility test ломается,
   mutation outcome неполон или нужна семантическая политика — остановиться и
   записать точную причину до продолжения. Если всё зелёное, записать этот
   отдельный C901 experiment; не считать это W3 exit.

### Готовность и acceptance граница

Рефактор принимается, когда behavior-preservation bank и stats CLI JSON
compatibility проходят, 24 parsed kinds остаются ровно покрыты dispatch,
C901 score ниже/равен 15 без waiver, проверка типов/линтеры чистые, targeted
mutation содержит реальные killed результаты (без пустого/no-tests запуска), и
BODY/EDGE mutants убиты своими точными oracles с восстановлением байтов. Это
локальный C901-срез. W3 остаётся OPEN, пока не пройдены все перечисленные
STEP9/STEP9A/STEP10 условия на нужном candidate SHA и host boundary.

## 4. E529 execution record — stats C901 slice (2026-11-10)

### Changes and compatibility

`_parse_events` now keeps one `_StatsAccumulator` per parse and forwards each
input event, in the original order, through the small `_dispatch_stats_*`
handlers. The handlers group activity, tool/compaction outcomes, subagent and
budget records, extended observability, and summary/scope/stop facts. Unknown
kinds remain unconsumed. `PARSED_KINDS`, public API/dataclasses, `None` and
structured source failures, DB/JSONL reads, output fields, sorting and stop /
verdict precedence remain unchanged. The C901 waiver was removed; no mutability
was introduced outside one parse call.

The AST contract now collects comparisons from the dispatch helpers, still
asserts the exact `PARSED_KINDS` set and liveness count of 24. The mutation
selection pin binds `src/fa/stats.py` to its owning parser/projection test files
in `pyproject.toml` / `tests/test_slice_mutmut.py`. S10a/S10b remain in the
normal CLI compatibility bank, not in every mutmut run: the full S10a file
contains a checkout-root authoring-check test that correctly cannot run in a
partial mutant overlay.

### Verification (exact selections)

- `uv run pytest tests/test_s19_stats_parsers.py tests/test_stats.py tests/test_s9_stats_projection.py tests/test_s10a_cli_coverage.py tests/test_s10b_cli_parity.py -q`: **exit 0, 154 passed in 15.77s**. This includes persisted DB projection and both single-session `fa stats --json`/CLI shape oracles.
- `uv run pytest tests/test_slice_mutmut.py -q`: **exit 0, 21 passed in 15.48s**; the permanent source/test selection pin passes.
- `uv run ruff check src/fa/stats.py tests/test_s19_stats_parsers.py tests/test_slice_mutmut.py`: **exit 0**, all checks passed.
- `uv run ruff check src/fa/stats.py --select C901 --ignore-noqa --output-format concise`: **exit 0**, no C901 findings (the pre-refactor `_parse_events` was 45 > 15).
- `uv run pyrefly check src/fa/stats.py tests/test_s19_stats_parsers.py tests/test_slice_mutmut.py`: **exit 0, 0 errors**. `git diff --check`: **exit 0**.

### Mutation evidence and runner limitation

The first too-broad configured mutation selection reached the unrelated
`test_s10a_authoring_check_runs_on_a_real_workspace` inside mutmut's partial
overlay and failed because the overlay lacks `knowledge/llms.txt`; it was not a
stats behavior failure. The selection was corrected to the three direct stats
owners, and S10a/S10b compatibility remained separately green in the 154-test
run above.

The targeted command used `src/fa/stats.py` with only
`tests/test_stats.py`, `tests/test_s19_stats_parsers.py`, and
`tests/test_s9_stats_projection.py` selected, plus `src/fa` and `scripts` as
stage copies. Mutmut generated/classified **1,408** file-scope mutants; the
Pyrefly filter marked 588 type-invalid, and the remaining 820 were test-run.
Its export plus the runner's `_parse_results`/`_classify` reconciliation gave:
**320 killed, 500 survived, 588 caught by type check, 0 no-tests, 0 skipped,
0 suspicious, 0 timeout, 0 interrupted, 0 segfault, 0 not-checked**; the counts
close exactly to 1,408. `mutmut results` exited 0 with 1,088 non-killed result
records, and the official classifier exited 0 on those records plus the
exported counters. These are honest whole-`stats.py` totals, not a claim that
all kills came from `_parse_events`; 500 survivors remain survivors and are not
claimed as killed.

The wrapper itself did **not** finish artifact packaging: after all mutation
statuses were available it attempted to run `mutmut show` sequentially for the
survivor diff report. The 30-minute shell call timed out while that report was
still being generated (around mutant 54); `mutants/stats-c901-result.json` was
therefore not produced. The mutation status/count data above were recovered
from the completed stage export and complete `mutmut results`, then reconciled
with the official classifier. Do not report the wrapper invocation as exit 0;
its shell result was `timeout` / no captured exit code. No mutation waiver was
added.

### Exact negative proofs (source byte-restored)

Each temporary mutation ran one named pytest oracle, failed with exit 1 as
expected, and restored `src/fa/stats.py` byte-for-byte to SHA-256
`178e489ad4ed4d5e3cdb408f581d5ce95df59f7661325080bdb570df73ef8826`:

1. **Producer BODY:** change the `model_msg_count` increment from `+= 1` to
   `+= 0`; `tests/test_s19_stats_parsers.py::test_model_user_msg_counted` fails
   exactly at `assert result.model_msg_count == 2`.
2. **Parsed-kind producer deletion:** remove the `model_msg` comparison branch;
   `test_s9_parsed_kinds_matches_dispatch` fails its 24-kind liveness assertion
   with 23 kinds.
3. **Dispatcher-call EDGE:** remove `_dispatch_stats_event(state, event,
   content)` from the parse loop; `test_model_user_msg_counted` fails at the
   event-derived user count (0 != 2). This separately proves the extracted
   dispatcher call is on the production parse path.

**Local C901 slice result:** parser/API/CLI compatibility, 24-kind AST
completeness, type/lint checks, real mutation kills, and the BODY/branch/EDGE
negative proofs pass. Mutation reporting is count-complete but its verbose
survivor-diff artifact is incomplete; 500 survivors remain explicitly
unresolved. This is not W3 sign-off: STEP9/STEP9A/STEP10 and W3 remain OPEN;
no `fa update`, STEP9A implementation, host or W4 acceptance was run.
