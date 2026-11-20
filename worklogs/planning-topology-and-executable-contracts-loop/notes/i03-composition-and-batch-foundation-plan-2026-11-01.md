# Тяжёлые ходы и композиция инструментов: фундамент I03

Дата 2026-11-01, база исследования `796d0bf`. Это архитектурный обзор и проект
плана, не утверждение нового публичного API и не разрешение на реализацию. Контекст:
`fa run chat` проходит managed nested workflow в полном I03; прямой `fa workflow` остаётся
поддерживаемым legacy manual/controller путём без managed-acquisition переписывания.
Инкремент и host-приёмка остаются открыты. Сверка OpenCode v2.2.5 зафиксирована
в [предыдущем исследовании](i03-heavy-turns-batching-research-2026-11-01.md).

## 1. Зачем нужна композиция и что найдено

Отдельный запрос LLM может содержать много готовых вызовов. Они могут выполняться
по очереди или параллельно, но аргументы последующих заранее заданы: результат
первого никак не меняет структуру аргументов остальных. Зависимый поиск:

```text
search(pattern, scope)
  → взять не более N фактических найденных path
  → read(path) для каждого через тот же стык инструментов
  → вернуть результаты и ошибки по каждому path
```

Такую работу можно выполнить в несколько LLM-ходов сегодня. В будущем есть
разные способы объединить её без запроса к модели между search и read:

* **Предметный инструмент**: готовая функция, например «найди и открой»; простой
  контроль, но каждый новый сценарий расширяет поверхность. Это пример, не
  предложение добавлять такой инструмент сейчас.
* **Ограниченный декларативный pipeline**: данные, подстановки и заранее
  разрешённые операции; легче ограничить, но нужна спецификация выражений,
  ошибок, происхождения и совместимости схем. Сейчас такого движка не найдено.
* **Ограниченный программный интерпретатор**, как OpenCode Code Mode: условные
  выражения, циклы, await, независимые вызовы и структурированное сведение.
  Выразительнее, но существенно дороже в безопасности, ресурсах и тестировании.
  Нельзя исполнять сырой model code на host или делать каждую операцию через голый
  `registry.dispatch`: им обойдут lifecycle/authority. Это не готовый наш дизайн.

Общее требование всех трёх вариантов — каждый вложенный вызов проверяется и
исполняется через тот же авторизованный runtime, получает собственный outcome,
сохраняет происхождение и отражает частичные успехи/неопределённость. Внешний
ход НЕ транзакция: если первая запись совершилась, вторая отказала, это не rollback.
Декларативный конвейер или Code Mode после I03 не выбраны и не предрешены.

## 2. Реальный стык FA: что есть и чего нет

| Стык | Факт по коду | Что следует / не следует |
|---|---|---|
| LLM → tools | `coder_loop.py:1863–1874,1946–1954,2099–2122`: один ответ → несколько `ToolCall`, `run_session`, отдельные model-visible tool results. | База для независимых вызовов уже есть, но не доказано, что все провайдеры/режимы формируют их одинаково. |
| scheduler → hooks → registry | `loop.py:188–249,315–405`: классификация перед BEFORE; `registry.dispatch` проверяет schema и вызывает handler; lifecycle hooks живут СНАРУЖИ registry. | Прямая вложенная `registry.dispatch` не эквивалентна обычному вызову. Наивная рекурсия `run_session` тоже не доказана: она меняет shared `hooks.set_event_sink` и session context. Не добавлять speculative facade; определить фактический общий стык при появлении реального потребителя. |
| authority/view | `ClientWorkspacePort` в `execution/tool_port.py:170–263` связан с namespace, view, grant; `ExecutionClient.request` имеет конкретный request ID. | Можно использовать одну область с отдельными операциями, но нельзя обещать неизменяемый snapshot mutable writer-view или передачу старого capability после handoff. При Q102 вернуть новый capability/revision. |
| cell | `execution/backend.py:95–115,300–345` владеет episode в пределах view; `cell_worker.py:169–210` принимает лишь один активный RUN и отказывает конкурентному. | Изоляция процессов и batching совместимы, однако proposed helper через EXEC не получает прозрачную параллельность. Обычный `READ_FILE` другой путь; не распространять ограничение RUN на все операции. |
| journal/trace | `supervisor.py:418–458` для non-readonly использует reservation и completed replay; readonly идёт отдельной ветвью. `state.py:743–765,767–850` фиксирует tool call/result. | Два уровня ID и две записи не равны сквозной связке LLM call → operation receipt. `ClientWorkspacePort` генерирует свежий UUID на вызов; требование доказать корреляцию и отсутствие повтора, а не объявить exactly-once. |
| projection/артефакты | `projection.py:53–92` получает уже готовый `ToolResult`, может сохранить raw и отдать head/tail + ссылку; `read_file.py:266–347` позволяет читать artifact по ID/окну. | Offload не восстанавливает данные, потерянные до projection. Две существующие корневые директории артефактов; их trust, containment, корректность при managed binding и доставка после сбоя отдельно проверить, не обещать их готовность. |
| история | `coder_loop.py:620–671` при rebuild берет `stdout` либо summary из event, а не вызывает `project_for_model` для исходного результата; `state.py:767–850` пишет полную result-структуру. | Персистентный event log есть; одинаковая полнота/ограниченность model context после resume не доказана. Проверить Q102 на настоящем сценарии, не обещать автоматического сохранения всех деталей по одному факту записи event. |
| файлы/search | `read_file.py:439–474`: managed port читает файл целиком и честно отказывает при `eof=false` выше 1 MiB; поиск/reach в `profiles.py:359–362,405–408` ещё связан с host root. | Q97 остаётся открыт; окна/артефакты не снимают требование полного и авторизованного получения данных. |

## 3. Прямые проверки опасных случаев

Все следующие результаты — изолированные local probes через реальные `run_session`,
`ToolRegistry`, `HookRegistry` и `SessionState`, с тестовыми handlers и
искусственными входами. Исходники probes для воспроизведения: [приложение](i03-batch-probes-2026-11-01.md). Это не C1/deployed host, не статистика частоты и не
подтверждение, что штатный provider или конкретный production hook так поступает.

### F1: повтор после начала исполнения — подтверждён fault injection

`loop.py:367–403`: если исключение в общем параллельном блоке, fallback повторно
диспетчеризует **все** разрешённые payloads. В E356 внедрено исключение в `wait`
после окончания двух handlers: они вызваны по два раза, результаты — success.
Вероятность реальной ошибки не измерена; класс ошибки подтверждён. Инвариант на
целевом пути: автоматический fallback никогда не повторяет уже начатую работу;
при неизвестном исходе — честное `unknown`, а не «отказ/можно повторить». Оговорка:
не обещать физическое exactly-once для произвольных сторонних эффектов.

Похожий backlog [I-65](../../BACKLOG.md)
относится к *другому месту*: legacy `run_bash` rerun после PTY timeout. Managed
bash supplier уже не делает fallback (`run_bash.py:384–395`), production cutover
ещё нет. I-65 и batch fallback — один класс риска повторного исполнения, но один
не доказывает исправление другого; точное совпадение с другими аудитами не установлено.

### F2: timeout/отмена потока — подтверждён локальный control probe

Сократили только тестовый аргумент `wait` до 0.02 сек, оба handlers продолжали
0.35 сек. `run_session` вернулся примерно через 0.42 сек, оба handlers выполнили
эффект, модельным результатам назначен `exec_timeout`. Значение 30 секунд в
реальном коде не гарантирует hard deadline, завершение или отсутствие эффектов.
Не добавлять искусственный «успешно отменён»; контракт deadline/terminality требует
явного доказательства фактической остановки либо отказа от такой гарантии.

### F3: классификация до изменения через hook — подтверждён synthetic probe

Два заранее классифицированных `read` вызова. Тестовый BEFORE hook изменил один
на `fs_run_bash` с `permission=workspace`, сохранив ID; два тестовых handlers
встретились на barrier и успешно выполнились одновременно. Это доказывает
отсутствие повторной scheduler-классификации *эффективного* вызова, а не то, что
существующие штатные хуки меняют имя на bash или что обойдена авторизация.
Другая форма — изменение path после overlap-проверки. При исправлении не обойти
повторную проверку guards после `Decision.modify`, schema и single-mutation rule.

### F4: duplicate `call_id` — подтверждён synthetic probe

В одном параллельном `run_session` отправлены два разных read input с ID `same`.
Оба handler выполнились, но `results_map[call_id]` свёл их к одному результату,
и два ответа оказались одинаковыми; порядок выбранного значения не гарантирован.
`_assert_tool_pairing_invariant` сравнивает множества IDs и принимает два calls и
два results с одинаковым ID. Достижимость через реального provider и внешние
валидации не доказана. До эффектов проверить отказ/корректную нормализацию при
пустых/повторённых/переписанных IDs на всей цепочке, не просто поменять словарь.

## 4. Предлагаемая программа в существующем I03

Не переименовывать семь SLICE, не увеличивать CT/kill/STEP counts незаметно.
Пункты ниже — реальные обязательства на review-плане; перед кодом требуется
отдельная 8-пунктная заявка, точная привязка к существующим шагам и tests-writing
C0–C3, либо явное согласование изменения плана при несовместимости формальных exit.
Ни одна галочка не проставлена.

1. **STEP2b / Q97, сначала.** Сверить актуальные callers и authority; закрыть
   single-view managed search/reach и metadata guard без host fallback. Q106=A:
   результат, превышающий лимит, не считать успешно полным. Q107=A принят оператором для закрытого allowlisted non-PTY пути (E359);
   его безопасность и применимость к production ещё предстоит доказать. Для выбранного пути доказать поведение при
   нескольких одновременных вызовах и ограниченном worker: bounded сериализация
   или явный отказ до эффекта с корректной семантикой, не скрытый resend. Это
   не требование реализовать параллельные RUN. Если safe cutover невозможно
   выполнить без изменения контракта — остановиться и вынести Q#.
2. **Сразу после STEP2b — полные type gates Q103**, затем подтверждение local exits
   W1 согласно действующему плану. Факт 60 ошибок полного pyrefly на E349 и
   6832/10/14/4 на E351 остаётся историческим; после последнего адресного исправления
   полный suite не повторялся. Targeted checks не заменяют его.
3. **До production/deployment — закрыть batch safety (F1–F4) в действующем пути**,
   привязав к SLICE4/6 и соответствующим существующим exit, а не отдельной новой
   платформе. Если F1–F4 мешают безопасно включить STEP2b, остановить cutover и
   выполнить необходимый минимальный prerequisite раньше; не нарушить обещание
   Q103 как следующего шага после *закрытия* STEP2b. Альтернативу «оставить
   concurrency отключённой» считать временной защитой только после доказательства
   безопасности остальных путей и решения о поведении, а не закрытием исправления.
4. **Q102 и история.** Проверить после workflow возврат в тот же чат на новый
   grant/view/revision: tool calls/results по IDs и подтверждённые эффекты без
   восстановления старой capability; resume/compaction не теряют значимые ошибки,
   неопределённость и ссылки на реально доступные артефакты. Не приписывать event
   log полноту истории модели без E2E. Блокер при изменении договора — Q#.
5. **Оставшийся действующий граф W2 → W3 → W4 (wave boundary clarified 2026-11-03):**
   W2 locally wires controller/acquisition/nested workflow; W3 locally proves chat-only
   `invoke_workflow` composition through `fa run chat` (direct `fa workflow` remains the unchanged
   legacy manual path), stop/seal/publish/recovery, roles and descendant-safety through real local
   supervisor/authority paths, mutation-sensitive tests, independent review, fixture/driver code and
   the deployment runbook. After those local gates close, W3 runs the approved
   `AUTO_STASH=0 SKIP_TESTS=1 SKIP_UV_SYNC=1 PRUNE=0 fa update` on the user's host to build/start and
   identify the candidate image; this is a deployment prerequisite, not live acceptance. W4 performs
   only the frozen suite against that already-running image: actual Docker-cell behavior,
   host-resource/cgroup/kernel, real-provider and all I01–I03 live-row acceptance. No local fake is
   W4 evidence, and W4 does not rerun `fa update` or rebuild.

### План верификации безопасности batch

* C0: поданные 0/duplicate IDs, пропавший/изменённый ID/name при hook mutation,
  malformed input и конфликт path: до эффекта явный outcome; ни одно значение не
  присваивается другому call. Определить фактический контракт на пустой ID через
  существующие adapters, не выдумывать публичную схему.
* C1/C3: реальный `drive_session`/registry/hooks, два read-only и сценарий mixed
  write/bash: последовательный порядок в нужных случаях, пары по original ID,
  реальные guards перед каждым эффектом, denial/AFTER stop не ретраят операции;
  независимые вызовы параллельны только при доказанно безопасном стыке.
* F1: injected submission failure до первого старта, после первого и после завершения
  одного/всех, включая lost response; проверить число фактических действий,
  journal correlation и отсутствие повторного выполнения. `unknown` не retryable
  автоматически. Отдельно проверить связанный I-65 managed/legacy по scope I03.
* F2: детерминированные barrier/event тесты deadline/cancel без sleep-only
  ожиданий: результат/terminality истинны, background не продолжает эффект
  после заявленного безопасного стопа; если доказательства нет, fail closed и
  publication запрещён. Тест resource ceilings: число одновременных операций,
  общий stdout/model-context и memory-per-call; отслеживать куда уходит overflow.
* Q97: большие/Unicode/escape-heavy payload, полнота before projection, остаток
  доступен либо честный отказ по принятому контракту; один `truncated` не превращать
  в паритет. Проверить recovery артефакта в нужном run/view и после resume.
* Обязательные C1/C2 host: один LLM response с несколькими calls в одном
  авторизованном view, смешанные исходы, ID, traces и receipts, ресурсные ceilings,
  controlled cancellation/descendants и STOP→SEAL→PUBLISH; на каждом действии
  отдельное отрицательное доказательство no host access и no duplicate effect.
  Реальные test nodeids, owner producer, строгие call-phase mutants,
  provider/host prerequisites и exit codes определить на плановой заявке; никаких
  вымышленных кейсов E2E register и замен живого host mock-ом.

## 5. Отложено после полного I03

Code Mode или альтернативная композиция — отдельная опция, не обещанная реализация.
До выбора сравнить с native multi-call/предметным инструментом на записанных задачах:
успех и качество end-to-end, p50/p95 latency, стоимость/токены, размер итогового
контекста, cache hit, CPU/RSS, частичные эффекты и восстановление. Измерять не
только число LLM calls: сокращение их числа само по себе не доказывает улучшение.

Будущий дизайн сохраняет инварианты I03 и пользуется существующими registry,
hooks, view/grant, journal, event log и result projection. Исследовать, как
безопасно представлять происхождение nested calls, stateful Bash, потерю ответа,
ограниченные ветвления/циклы и I/O; никаких скрытых host access, новых полномочий,
самоповторов или предположения о едином snapshot. Не нарушать порядок I04–I06.

## 6. Q135 — F1-only prerequisite; F2–F4 deferred

This is a bounded application of E357/E358, not a plan amendment, new CT/STEP,
deployment authorization, or evidence that any exit is closed. Following the
operator direction, source review resolves only F1: `_execute_batch_parallel`
catches exceptions around submission/collection and can re-dispatch every
executable payload; E356 recorded duplicate handler effects. The F1-only local
prerequisite may proceed under the already accepted no-repeat invariant. F2–F4
remain unresolved and are deferred until live E2E after W3 because current
contracts/source do not settle their production reachability or exact semantics.
The overall Q135 safety gate stays BLOCKING; no dependent production cutover is
authorized by this local slice.

### Eight-point application

1. **Behavior/gap.** Close F1–F4 in the existing `run_session` batch path before
   any dependent production cutover: never retry a submitted/started call because
   bookkeeping failed; do not report cancellation/terminality solely from a wait
   timeout; ensure a hook-rewritten effective call cannot inherit an unsafe
   parallel/effect classification; and preserve one-to-one call/result identity.
   F1 is source-confirmed plus recorded local fault injection. F2–F4 have only the
   synthetic local reachability recorded in §3/E358.
2. **Seams and candidate files.** Reuse `src/fa/inner_loop/loop.py`'s
   `_execute_batch_parallel`/`run_session`, `HookRegistry`, `ToolRegistry.dispatch`
   (which validates the effective call's schema), and the existing
   `coder_loop.py::drive_session` caller. Candidate code files are
   `src/fa/inner_loop/loop.py` and, only if the ID contract belongs at provider
   normalization, `src/fa/inner_loop/coder_loop.py`. Candidate owning banks are
   `tests/test_tool_batching.py`, `tests/test_coder_loop.py`, and the existing
   production-composition bank `tests/test_execution_composition.py`. The direct
   `cli.py::_cmd_inner_loop_smoke` caller must be inventoried, but is a diagnostic
   route, not the `fa run chat` production root. Do not change `registry.py`, CLI,
   provider adapters, or introduce a scheduler/worker unless source review proves
   the current seams cannot enforce the approved contract; any expansion is a
   new Q# before editing.
3. **Dependency and mapping.** Preserve Q97/STEP2b → Q103. Before STEP2b's
   dependent cutover, attach local regression/producer-caller evidence to existing
   SLICE4 STEP2 (cutover), STEP4 (real direct C1 composition), and STEP5 (full-path
   producer kills); do not claim the generic CT97/CT110/CT111 banks prove batch
   safety unless their actual call paths are exercised. If the safety prerequisite
   cannot close, keep the dependent cutover blocked; do not reorder Q103 or mark
   an unchecked STEP complete. Final deployed acceptance remains SLICE6, not this
   local application.
4. **Safety invariants / F1-only mechanism.** Reuse the already accepted F1
   invariant: track each submitted future and settle it at most once; never run a
   blanket sequential fallback over submitted or possibly submitted work. Preserve
   original call order in returned results. Sequential fallback is allowed only
   if the executor fails before any submit attempt. If a submit was attempted but
   no future was retained, return an explicit non-retryable `exec_failed` result;
   calls not attempted after a partial failure receive an explicit retryable
   `exec_failed` result because they did not run. No hard cancellation claim may
   be made for `ThreadPoolExecutor`; no new pool/process architecture is assumed.
   F2–F4 are not changed here: after `Decision.modify`, schema validation already
   occurs through `ToolRegistry.dispatch`, but batch reclassification remains
   unresolved; repeated-ID and empty-ID policy remains open.
5. **Failure semantics / unresolved contract.** F2 must distinguish elapsed wait
   budget from stopped work: `Future.cancel()` is not proof that a running handler
   stopped, and the executor context waits for workers on exit. Decide whether the
   existing synchronous wait is retained with an honest timeout/non-retry outcome,
   or whether any stronger deadline requires a separately approved cancellable
   owner. F3 must preserve lifecycle/security checks for an effective rewritten
   call. F4 must choose where duplicate IDs are rejected/normalized and what the
   caller observes, without inventing a public empty-ID contract. Until these
   decisions are approved, no code may guess at them.
6. **Test classes and oracles (`/tests-writing`).** C0/C0p: duplicate/missing IDs,
   malformed calls, submission/collection faults, and order/correlation properties;
   every invalid-ID outcome must be checked before the first handler effect. C1:
   real `drive_session` + `run_session`, real registry/hooks/state, only provider
   I/O mocked; assert ordered per-call structured results and exact handler
   call-count/effects for pre-submit, partial-submit, post-completion and lost
   bookkeeping cases. C3: adversarial hook rewrite from read to a different
   permission/effect class, plus duplicate IDs and mixed outcomes. Add C2 only if
   the CLI diagnostic route itself changes. Avoid sleep-only timing and reimplemented
   scheduler doubles; use barriers/events and fault injection at the existing seam.
7. **Production path and live acceptance.** C1 producer/caller proof is required
   before claiming the code is shipped. At SLICE6 STEP7, the planner/reviewer must
   decide whether to add a new live register row or extend a reviewed existing row;
   STEP8 fixture work follows review, STEP9 maps the producer, and STEP10 runs the
   actual deployed suite. Candidate witness: one real provider response with
   multiple calls in one authorized view, mixed per-call outcomes, exact IDs/results,
   bounded concurrency/resources, and no duplicate effect or host access. Local
   injected-failure tests are not host evidence; do not claim real-provider delivery
   of an injected internal fault unless a reviewed deployment-safe harness exists.
   This runtime path does not append the planning ledger, so a ledger-append E2E
   is not applicable here.
8. **Verification / closure.** Producer kill: remove/neutralize the no-re-dispatch
   and per-future settlement decision in `_execute_batch_parallel`; the counter,
   result-correlation, and no-duplicate-effect C1 oracle must fail. EDGE kill:
   bypass the production `drive_session -> run_session` call; the same caller-rooted
   C1 oracle must lose the behavior. F3/F4 receive their own producer and caller
   mutations after their source owners are selected. Then run affected tests,
   relevant Ruff/type gates, diff review, and targeted mutation checks with call-phase
   failures (no collection/setup errors credited). SLICE6 host/release evidence
   remains separate; E357/E358 probes and local tests cannot close it.

### Existing-step map and decision gate

| Finding | Current proof / gap | Existing owner proposed for evidence | Not claimed |
|---|---|---|---|
| F1 | E356 fault injection + current broad exception fallback | SLICE4 STEP2/STEP5; C1 through `drive_session` | No production incident frequency or deployed proof |
| F2 | E358 local short-wait probe; executor still joins workers | SLICE4 STEP4/STEP5, then SLICE6 STEP7–10 if terminality is claimed | No hard cancellation/deadline guarantee |
| F3 | E358 synthetic BEFORE-hook rewrite | SLICE4 STEP4/STEP5 with the actual production hook chain | No claim a shipped hook currently rewrites tool/effect class |
| F4 | E358 duplicate-ID collision in `results_map` + set-based pairing check | C0/C3 plus SLICE4 C1 caller root; index any required deployed row at SLICE6 | No provider-wide uniqueness guarantee |

**Review gate:** Q135 remains BLOCKING overall. This turn's bounded local scope is
only the F1 no-repeat prerequisite in `src/fa/inner_loop/loop.py`, with its C1
caller-rooted test in `tests/test_coder_loop.py`; it does not close batch safety.
F2 timeout/terminality, F3 effective-call rewrite, and F4 duplicate/empty-ID
semantics are deferred until live E2E after W3. Keep STEP2b and every dependent
production enablement blocked until those decisions and their oracles are closed;
do not silently disable batching or call that a fix. The live acceptance remains
separate, and the runtime path does not append the planning ledger.

**F1-only local verification:** `tests/test_coder_loop.py` and
`tests/test_tool_batching.py` — 33 passed; Ruff check/format passed; focused
Pyrefly — 0 errors. The producer re-dispatch mutant and the caller-edge bypass
mutant were both killed by the C1 oracle. These local results do not close Q135,
STEP2b, or the SLICE6 live/deployed gate.
