# Карта `coder_loop.py` и `_drive_session_inner`

**Исторический снимок (§§1–15):** 2026-11-09, рабочее дерево ветки `arena/786f6d8a-first-agent-dev`, base HEAD `9ba095d`; SHA-256 `src/fa/inner_loop/coder_loop.py`: `d13afd84f3afbbde806aa059a5975fbd163c5ede24a74b713deadc2cca42fb18`. Номера строк ниже относятся именно к этому снимку, включая локальные незакоммиченные изменения. Ruff `--select C901 --ignore-noqa`: `_drive_session_inner` 97 при конфигурационном пороге 15. Это индикатор для анализа, **не цель и не разрешение механически дробить**.

**Текущий статус (2026-11-09):** выполнены history/protocol, tool-turn, scope-turn и payload-composition срезы; актуальные владельцы, проверенные результаты и оставшиеся AL1–AL6 задачи — §§17.6–17.8 и §18. Исторические снимки и варианты §§1–17.5 не являются текущей картой или разрешением на изменение поведения. `coder_loop.py` остаётся большим оркестратором; следующий рискованный кандидат — контекстное давление/compaction после инвентаризации состояния, эффектов, частичных отказов и C1/producer/EDGE проверок. Цель — агенту легко найти владельца поведения, понять инварианты и безопасно изменить и проверить его; числовых LOC-требований или порогов нет. Полный gate и live-host acceptance не закрыты.

## 1. Назначение и границы

`drive_session` — orchestration bridge между сформированными ролью LLM-запросами и детерминированным `run_session`: логирует историю и результаты, применяет hooks, контекстный бюджет и retry, возвращает `SessionOutcome`. Это не владелец политики изоляции: managed registry/lease и provisioning формируются внешними composition roots; перенос не должен обходить их. Прямые production callers функции `drive_session`: `src/fa/cli.py` (standalone и workflow через CLI-композицию) и `src/fa/inner_loop/tools/managed_subagent.py` (ограниченная child-сессия, `output=None`, `pinned_buffer=None`). Дополнительно `workflow_controller.py` напрямую импортирует `SessionOutcome` из публичного фасада `coder_loop`, как и другие consumers; совместимость типа и идентичность существенны. Соседние tests и косвенные callers тоже чувствительны к сигнатурам/patch targets.

```text
CLI/workflow composition OR managed child
  -> drive_session: log fence, set_current_session, try/finally reset
     -> _drive_session_inner: setup -> loop of turns -> finish
        -> prompt + context budget/compaction -> ProviderChain.request
        -> AFTER_LLM_CALL -> model event -> run_session (registry + hooks)
        -> stop decision OR audited padding -> projected/redacted tool messages
     -> SessionOutcome -> caller's reporting / lifecycle
```

`drive_session` сам по себе не гарантирует завершения при любом исключении: contextvar сбрасывается в `finally`, но `finish()` вызывается явно на контролируемых return/loop-exit ветках, не из общего `finally`. Нельзя обещать summary на неожиданных исключениях без отдельного изменения контракта.

## 2. Карта всего модуля

| Строки | Существующий объект / функция | Ответственность и граница |
|---|---|---|
| 120–151 | constants, sentinel | default LLM turn/output caps, terminal finish reasons, `pinned_buffer` sentinel; не путать с per-turn tool limit |
| 153–227 | `_redact`, `_usage_event_content`, `_session_summary_content`, `_merge_memory_summary_context` | egress-redaction; value преобразования usage/summary; merge resume summary |
| 230–279 | `should_inject_ceremony`, `_ceremony_blocks` | mode/entry-turn решение и чтение governance skill blocks; advisory failure policy нужно сохранять |
| 281–309 | `_verify_failed_in_pairs` | определяет verify-only bash failure из предыдущих пар; ошибки классификации advisory |
| 311–353 | `_assert_tool_pairing_invariant`, `_assert_final_role_invariant` | debug-time проверки формы истории/финальной роли; не заменяют production provider conformance |
| 355–400 | `_fallback_projection_handler`, `_projection_spec_for_call`, `_tool_calls_for_message` | fallback spec для проекции и синхронизация raw/parsed IDs для provider history |
| 402–434 | frozen `SessionOutcome` | возвращаемое terminal value: код, причина, turn count, final text, результаты, имена failed tools |
| 437–558 | `drive_session` | публичная граница, требование log, contextvar scope + обязательный reset; стабильный API |
| 561–614 | `_restore_conversation_history` | replay после последнего `compaction_stage3_done` и merge summary; исключение → warning и текущие частичные значения |
| 616–668 | `_pad_unexecuted_tool_results` | синтетические retryable failures и audit pairing для неполного batch; сохраняет `SessionRun.stop`, учитывает только новые log rows |
| 670–742 | `_request_with_cooldown_retries` | до трёх per-turn вызовов chain, лог attempts на exhaustion, cooldown / output; наружу propagates terminal exception |
| 744–757 | `_handle_terminal_tool_stop` | terminal `AFTER_TOOL_EXEC` и LoopGuard `BETWEEN_ROUNDS`, общий output/observation; остальные continue |
| 759–2130 | `_drive_session_inner` | stateful orchestrator, карта ниже |
| 2132–2193 | `_failed_tool_names`, `_build_tool_calls` | trusted call/result failures; детерминированный разбор tool calls/fallback IDs, без LLM-решения |

Вложенные функции драйвера: `record_usage` (стр. 890), `finish` (900), `_request_shape_failure` (956), `_compose_request_payload` (1247, создаётся на каждом turn и захватывает значения через defaults). Их замыкания — настоящие текущие зависимости, а не уже существующие самостоятельные сервисы.

## 3. Поток исполнения `_drive_session_inner`

| Фаза / строки | Читает и обновляет | Внешние эффекты и переходы |
|---|---|---|
| Setup 783–889 | limits, config, state; tool specs; `ContextBudget`, history/summary, счётчики, expansion seed | создаёт `ArtifactStore`, `PinnedBuffer` (если sentinel); clamp context limit до 32000 с telemetry; replay **до** `user_msg` и `run_started`; `session_start` |
| Completion closures 890–995 | totals, usage_turns, last ratio, failed names, outcome, turn | `usage`; `finish` пишет максимум один summary и `session_end`, best-effort DB metrics, добавляет sorted `failed_tools`; request shape пишет `run_stopped` и `api_retry`, завершает code 2 |
| Turn boundary 996–1177 | turn++, ceremony mode; для chat — snapshot transaction read/write, предыдущие tool пары, expansion/near-miss/exhausted | ceremony event; scope expansion event + output или delta-gated near-miss; затем `turn_start` |
| Before LLM / compose 1178–1304 | BEFORE hook; history pairing; pinned content; current summary/history + turn-bound observation/skills | denial → terminal; pinned extraction exception → warning/fallback; provider-specific composer + cache extras; `ProviderRequestShapeError` → terminal code 2 |
| Budget / compaction 1305–1736 | `messages_payload`, tool payload, `budget`, history, summary, ratio, optional compactor chain | warn / hard stop / stage2 masking / stage3 summarisation; log and console; может перезаписать payload + историю/summary или terminal return |
| Provider 1738–1910 | `RequestInfo`, chain/cooldowns, retry counters, response | per-turn attempts; успешные `provider_attempt`, `llm_call`, `usage`, `llm_response`; interrupt / exhaustion / shape; session retry `continue` начинает **следующий turn** |
| AFTER hook / model 1911–2024 | response, raw/parsed tools, history | denial до model event; добавляет assistant history и `model_msg`; no-tools clean stop или abnormal stop с warning |
| Tools / next turn 2025–2118 | `run_session`, stop, per-turn cap, previous pairs, latched budget exhaustion, redactor, artifact store | terminal stop breaks до padding/projection; иначе audit padding, aggregate results, expansion exhausted, console tool event, project → redact → history |
| End 2120–2130 | collected results, turn, failed tools | пишет `run_stopped: iteration_cap` и возвращает code 1 / `iteration_cap` через `finish` |

Важно: в текущем коде terminal guard `break` попадает в общий финал `iteration_cap`; executed `turn_results` на этом пути **не добавляются** в `collected_results` (хотя имена failures обновлены до break). Это описание текущего кода, не утверждение желательности или окончательного соответствия планам; смена причины/результатов — отдельный поведенческий срез, а не незаметная часть декомпозиции.

## 4. Инварианты и порядок эффектов

| ID / источник | Обязательная граница или фактический семантический контракт, который необходимо сохранить при рефакторинге |
|---|---|
| A1 / ADR-7 §10 criterion 8, S13.2 I-52 | Replay событий после последнего stage3 сохраняет порядок и не дедуплицирует; в текущем turn `_tool_calls_for_message` использует IDs из parsed calls, а продолженный неполный batch дополняется записанными synthetic парами. Это не доказывает согласованность любых исторических данных: replay читает raw `model_msg.tool_calls` и отдельно сохранённые IDs результата (см. §11.3). Не скрывать telemetry rows. |
| A2 / ADR-8, S6-F4, S12.7 CT1, S14b.2 CT2 | BEFORE/AFTER LLM guard order и tool hook order неизменны. AFTER_TOOL_EXEC либо LoopGuard trip терминальны; обычный BETWEEN_ROUNDS и per-turn iteration cap продолжаются. Не подменять остановки простым `if stop`. |
| A3 / S10 CT2, S10.9 CT-H3/4 | Scope только chat+scope_mode; результаты предыдущего tool batch и текущий snapshot transaction sets оцениваются на следующей turn-boundary; observation заменяется, не накапливается; near-miss только при отсутствии transition и при изменении относительно **последнего записанного** evidence; output mirror у transition. |
| A4 / PLAN slice ceremony S5 | Coder first turn и mode resolver; observe — telemetry без инъекции, enforce — blocks; ceremony не должна оказаться внутри chat-only branch. Turn-local skill blocks не протекают в следующий turn. |
| A5 / ADR-17, S14 compaction SSoT | Context budget по умолчанию включён без flags; `compaction_threshold is not None` управляет наличием compaction; stage2 сначала, stage3 при соответствующем решении после неё, protected recent window и breaker. Сохранять существующий порядок записи и fallback при ошибках; не обещать атомарный rollback, которого код не реализует. |
| A6 / ADR-9 §2/§4, S22 | Различать transport retries, три per-turn `ProviderChain.request` и session-level retry. Per-turn reuse same `RequestInfo`, cooldown и запись attempts; exception/interrupt не проглатывать. При exhaustion попытки не дублировать; `llm_call`/attempt IDs сохранять. На exhaustion `llm_call` не записывается текущим driver; см. §11.4. |
| A7 / ADR-12 B2 | Проекция tool result в model-facing text затем `_redact`, затем append в историю. Не переносить редактирование только на console или durable log и не обходить managed tool authority. |
| A8 / Q98, ADR-7 event trail | На контролируемых completion paths `finish` пишет один `session_summary` с вердиктом и usage, output session_end, metadata best effort. `usage_turns` — число успешных usage rows, а не обязательно число loop turns. |
| A9 / S13.3/S13.4 | Provider conformance — authoritative, debug assertions не её замена; shape failures из initial compose и provider приводятся к одному exit-2 path. Сохранить cacheable governance vs non-cacheable turn context и family-specific request shapes. |
| A10 / managed isolation | `drive_session` получает уже provisioned registry/state; нельзя создавать host fallback, расширять child capabilities или обходить managed guards при переносе зависимостей. |

Документированные планы/ADR: `knowledge/adr/ADR-7-inner-loop-tool-registry.md`, `ADR-8-hook-registry.md`, `ADR-9-llm-provider-client.md`, `ADR-12-*`, `ADR-17-context-management-and-compaction.md`; `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md` §S13.2; `PLAN-scope-control-S10.9-hardening.md` §S10.9.3–4; `PLAN-slice-ceremony-harness-enforcement.md`; S6/S12.7/S14b контракты и тесты указаны ниже. При фактическом изменении конкретной границы следует заново сверить актуальный текст плана, а не принимать эту карту как замену спецификации.

## 5. Состояние, ownership, value objects и entities

Здесь «entity» означает объект с жизненным циклом/изменяемым состоянием, а не предложение внедрить DDD-фреймворк.

| Существующее | Роль / владелец и время жизни | Риск при переносе |
|---|---|---|
| `SessionState` (`state.py`) | изменяемая entity на сессию; workspace, log, transaction, observations, flags, DB, managed capabilities | не копировать как DTO и не делить authority: registry/tools и caller уже используют тот же объект |
| `EventLog` / `TraceEvent` | SQLite authority с JSONL best-effort mirror и read-side события; run identity, chronological replay, kind_counts | порядок append/read и exception behavior; log — отдельный authority, а не снимок conversation |
| `ProviderChain` | stateful service с config/cooldown ledger, фабрикой provider и request | не клонировать cooldowns на turn/compactor; ошибки и логические IDs живут на границе вызова |
| `ContextBudget` | локальная stateful entity на сессию: thresholds + consecutive compactions | новый объект на каждый turn сбросит breaker; decision сейчас dict, а не утверждённый immutable тип |
| `ExpansionState` | frozen value state transition + read/write snapshots | связана с отдельно хранимыми `_active_skill_name`, `_exhausted_flag`, `_prev_*`, `_last_observed_evidence`; вместе образуют протокол, но пока не один объект |
| `RequestInfo`, `ResponseInfo`, `ChainAttemptRecord` | provider-boundary values; `RequestInfo` reuse при per-turn retry | сохранение extras, модели, tokens, correlation ID; не подменять adapter normalization |
| `ToolCall`, `ToolResult`, `SessionRun`, `StopInfo`, `RuntimeLimits` | типизированные tool/stop values; `SessionRun` — sequence результатов + stop | стоп не терять при padding; limits per-turn, а `max_turns` сессионный |
| `SessionOutcome` | frozen output value, финально дополнен `failed_tools` через `replace` | caller видит коды, reasons, порядок и объём результатов; отдельный внутренний transition не должен тайно менять публичный result |
| `ArtifactStore`, `HookRegistry`, `ToolRegistry`, `EventBus`, `SecretRedactor` | collaborators с I/O/effects, переданы либо созданы по существующей authority | сохранить живые registry/specs/hooks, bus optional, redactor optional и точку проекции |
| `conversation_history`, `memory_summary` | изменяемые локалы до конца сессии; event log остаётся источником replay | после compaction текущие payload/history/summary должны отвечать существующим присваиваниям; события и история не взаимозаменяемы |
| `usage_totals`, `usage_turns`, `summary_written`, `last_budget_ratio`, `failed_tools` | локальная mutable bookkeeping-группа, используется `record_usage` и `finish` | reset или раннее snapshot приведёт к неверному вердикту; `last_budget_ratio` обновляется не на всех ветках одинаково |
| turn-locals `skill_block_for_request`, composed payload/extras, request/response/results | создаются заново на turn; часть замыкается composer default args | повторная композиция после stage2/3 обязана использовать те же turn-bound pinned/skills/context |

Возможные *будущие* value objects, не существующие сегодня: `PreparedPrompt` (payload + extras, возможно body при реальной необходимости); `BudgetTransition` (новые history/summary/payload/ratio **или** terminal решение); `ExpansionBoundaryResult` (новое state + текущий context/skills). Их ввод оправдан только если связанные данные действительно пересекают seam вместе и проверки могут поймать потерю одного поля. Не добавлять универсальный `SessionContext` как мешок всех зависимостей; это лишь скроет coupling.

## 6. Выходы и fail behavior

| Путь | Текущий выход/действие | Особенность |
|---|---|---|
| отсутствует log при входе | `ValueError` до установки context | `finally` reset только после установки |
| replay read/processing exception | warning, продолжение с initial/частично построенным состоянием | не fail-closed; I-52 extraction не менял политику |
| BEFORE/AFTER LLM hook `PermissionError` | code 1, `hook_deny:<point>`, `run_stopped`, output, finish | AFTER до model history/event |
| локальный shape или provider shape | code 2 `request_shape`, `run_stopped`, output `api_retry`, finish | debug assertion pairing отдельно перехватывается; final-role assertion не является тем же типом exception |
| budget hard stop / circuit breaker | code 1 `context_budget_hard_stop`, audit/output + finish | порядок stage3_done, breaker, warnings и hard stop существенен |
| compaction exception | warning и stage error/output; дальнейшее решение использует текущее `decision` | broad catch охватывает также composer внутри этапа; частично выполненные присваивания/effects необходимо сохранить |
| exhausted chain | per-turn retry; при доступном session retry `continue`, иначе code 2 `chain_exhausted`, stop row | последний exhaustion attempt записан inner seam, не повторять снаружи |
| `KeyboardInterrupt` в provider try | code 130 + stop row + finish | не универсальная обработка interrupt на любой фазе |
| no-tools terminal / abnormal | code 0 `stopped_by_llm` либо code 1 `abnormal_stop:<reason>` | `model_msg` до выхода; abnormal также output + stop row |
| terminal tool stop | `break`, затем фактический общий итог code 1 `iteration_cap` | отмечено в §3; нельзя переименовать в рефакторинге |
| исчерпание `max_turns` | code 1 `iteration_cap`, stop row + finish | отличается от `RuntimeLimits.max_iterations` внутри одного turn |
| неожиданные исключения append, output, projection, provider и др. | распространяются там, где нет конкретного catch | не превращать автоматически в success, не расширять catch при извлечении |

## 7. Кандидатные seams и архитектурные варианты

> Исторические варианты P1–P7: переоценка с учётом размера файла, бюджета чтения и границ модулей — в §17; не использовать таблицу как план накопления helpers в `coder_loop.py`.

Приоритет — уменьшить связность и сделать изменение проверяемым, а не уменьшить цифру C901 любой ценой. Размеры и порядок являются предложением, не реализацией.

| Кандидат | Предлагаемая ответственность / интерфейсная граница | Польза / опасность | Доказательства перед переносом |
|---|---|---|---|
| P1. Turn prompt composer | собрать family-specific payload из явно заданных turn-bound pinned/context/skills, history + summary; повторно использовать при compaction | уменьшит неявные closure captures; опасность — late binding, cache key и provider extras | `test_pr3_wiring.py`, `test_scope_hint_cache_key.py`, `test_s13_replay.py`, `test_slice_ceremony_injection.py`; C1 caller + composer/EDGE mutations |
| P2. Scope expansion boundary | от state transaction snapshot + prior pairs + expansion state получить новое state и turn advice; эффекты log/output явно упорядочены | цельный per-turn domain transition; опасность — lost evidence delta, skills leak или задержка на неправильный turn | `test_scope_expansion_wiring.py`, `test_observations_builder.py`, `test_slice5_6_7_wiring.py`; positive/negative role and next-turn oracles, producer/EDGE |
| P3. Context budget/compaction orchestration | фаза получает подготовленный prompt и устойчивый `ContextBudget`; возвращает изменённые prompt/history/summary/ratio или terminal outcome, при этом existing compactor и event effects сохраняются | наибольшая связность и потенциальная польза, но самый высокий риск: partial effects, порядок logging, exception coverage, stale ratio и anti-thrash state | `test_compaction_c1_wiring.py`, `test_s14_compaction_ssot.py`, `test_s23_circuit_breaker_loop_warn.py`, `test_pr1_wiring.py`, `test_pr4_wiring.py`; C1 fault matrix каждого этапа + producer/EDGE; предварительно описать все присваивания и выходы |
| P4. Provider success/terminal telemetry | отдельно связать attempt rows, rollup, usage, output; session retry decision остаётся в orchestration | устраняет размазанность effects, но преждевременный общий обработчик может дублировать attempts или сменить ID | `test_coder_loop.py`, `test_s7_correlation.py`, `test_s22_max_chain_retries.py`, `test_stats.py`; реальный chain success/exhaustion и mutations |
| P5. Model response → history и terminal classification | сгруппировать обработку ответа после AFTER hook, с отдельным решением no-tools | логически единая граница, но нельзя записать model раньше hook или сменить `message_extras` precedence | `test_coder_loop.py`, `test_s13_replay.py`, `test_s13_error_surfacing.py`; hook denial, all finish reasons, malformed calls |
| P6. Tool result handoff | собрать turn-local post-run side effects и redacted projections после terminal check, включая exhaustion latch | снимет несвязанные детали из основного цикла; риск: записать synthetic на terminal path, выдать секрет, изменить order `zip(strict=True)` | `test_s6_stop_paths.py`, `test_iteration_cap.py`, `test_model_egress_redaction.py`, `test_coder_loop.py`, `test_scope_expansion_wiring.py`; terminal/continue matrix и egress mutation |
| P7. Completion bookkeeping | `record_usage`/`finish` в малом session-lifetime объекте только если один owner объединяет summary, counters и DB metrics | устранит closure/nonlocal; риск ненужного класса, сброса guard, раннего snapshot `failed_tools`/ratio | `test_coder_loop.py`, `test_s9_guardrail_metrics.py`, `test_stats.py`, `test_cli.py`; каждый controlled exit, один summary, DB write failure |

**Альтернативы:** (1) независимые функции с явными input/output для чистых преобразований; (2) ограниченный private session-lifetime object для действительно shared mutable state и методов с одним владельцем; (3) отдельный модуль при проверяемой тематической границе, явных входах и проверке import cycles / patch paths. Модуль можно выделять поэтапно, не дожидаясь абстрактной полной «стабилизации» всех соседних seams; подробности §17. Не стоит заранее создавать иерархию `SessionRunner`/`Turn`/`Manager`, generic event dispatcher, новую публичную API или переносить сразу весь цикл: C901 можно снизить, не уменьшив сложности рассуждения.

Предварительная гипотеза, не обязательная зависимость: P1 может быть полезен для P3 (compaction повторно вызывает composer); P2 и P4 могут обсуждаться отдельно; P6 после сохранения уже выделенных stop/padding seams; P7 независимо, но только с полной матрицей exits. Выбирать следующий срез после анализа тестов и контракта, не считать это согласованным графиком.

## 8. Тестовая карта и стратегия доказательств

- **C0:** таблицы детерминированных переходов и value objects; защита отсутствия side effects/unchanged fallback, AST/census только как дополнительный structural сигнал, не доказательство wiring.
- **C1:** реальный `drive_session` + настоящие state/log/hooks/registry/chain; scripted provider и контролируемое время как внешние границы. Проверять порядок и поля log, output, response messages, call counts и terminal outcome; охватывать все path families.
- **C2/C3:** существующие CLI и managed composition (`tests/test_cli.py`, `tests/test_execution_composition.py`, `tests/test_managed_subagent.py`) там, где seam действительно пересекает root. Local doubles не доказывают live-host isolation.
- **C4/live:** планы ledger append `i03-live-e2e-test-plan-2026-10-22.md` §4.1 L-RCPT-2/L-RCPT-6 и §4.2 L-ENTRY-4 остаются NOT RUN. Не выдавать локальный pytest за live acceptance.
- Для каждого среза: test-writing skill (`knowledge/skills/tests-writing/SKILL.md`), положительный/отрицательный DoD, producer mutation (удалить эффект) и EDGE mutation (убрать/исказить вызов или границу), восстановление SHA, targeted bank, Ruff/format/type checks/diff и отчёт. При изменении event dual-write отдельно проверять producer и consumer.

## 9. Риски и открытые наблюдения, не включённые в рефакторинг

1. **ADR-9 Tier-2:** в текущем `src/fa` поиск обнаруживает `llm_chain_exhausted` только в документации `providers/errors.py`, тогда как driver пишет `run_stopped` на exhaustion/shape. Контракт ADR-9 §4 требует отдельного анализа и тестов; карта не утверждает исправление.
2. **Tool guard break:** факт общего `iteration_cap` и отсутствия текущих `turn_results` в outcome зафиксирован выше. Требуется отдельно сверить внешние контракты до возможной коррекции; изменение не объединять с extraction.
3. **Compaction partial state:** `_compose_request_payload` присваивает payload до `estimate_tokens` и log/output внутри try; при последующем исключении история может не быть присвоена, а payload уже изменён. Stage3 после successful compaction пересчитывает `decision`, но не обновляет `last_budget_ratio` в этой точке. Это source observations, не доказанный баг; нужно проверить контракты и fault tests прежде чем менять.
4. **Replay error:** предупреждение и продолжение — существующее поведение, не гарантия fail-closed восстановления.
5. **Pytest sleep shim:** `PYTEST_CURRENT_TEST` меняет ожидание только на тестовом runtime path; существующая семантика, не свидетельство поведения production host.
6. **Full gate:** последний полный `just test` exit 1 (37 failed, 7252 passed, 18 skipped, 4 xfailed, 11 errors); Q137 остаётся BLOCKING. Рефакторинг и отдельные зелёные банки не являются полным sign-off.

## 10. Точка решения для следующего обсуждения

Выбрать один из P1–P7, обсудить его inputs/outputs, ownership, политику исключений и возможность избежать новых типов. Перед кодом объявить точные файлы, соответствующий план/ADR, source-verified delta, safeguards, C0–C3/producer/EDGE проверки и ограничения. Если выяснится неразрешённый product/policy выбор — оформить Q# и остановиться; иначе сохранять поведение, включая неидеальные текущие пути, до отдельно мотивированного исправления.

## 11. Второй проход: исправления и упущенные границы

### 11.1. Уже сделанная декомпозиция от исходных 125

Значение 125 — измеренный baseline **самого `_drive_session_inner` до этих срезов**, а не сумма сложностей модуля. История измерений — Q137 working-entry inventory §§ I-52 / padding / retry / attempts / stop (в том же каталоге):

| Изменение | Драйвер до → после | Куда ушла ответственность / что изменилось |
|---|---:|---|
| I-52 replay | 125 → 115 | `_restore_conversation_history`, поведение восстановления сохранено |
| ADR-7 padding | 115 → 109 | `_pad_unexecuted_tool_results`, audit + in-band stop |
| S22 per-turn retry | 109 → 101 | `_request_with_cooldown_retries`, session-level retry остался в драйвере |
| устранение повторной записи attempts | 101 → 100 | **исправление поведения**, а не только extraction: удалён второй append последнего exhaustion attempt |
| S6/S12.7 terminal-stop | 100 → 97 | `_handle_terminal_tool_stop`, фактический `break` остаётся в драйвере |

Все значения — исторические замеры в ledger; прямой повтор текущего снимка ниже. Уменьшение драйвера **не равно исчезновению сложности системы**: она распределена между четырьмя helpers и соседними модулями. McCabe по функциям не складывается напрямую (базовые единицы, вложенные функции и граф вызовов считаются отдельно); ни 125−97, ни сумма новых scores не являются доказательством улучшения поведения.

Ruff 0.16.0, `--select C901 --ignore-noqa --config 'lint.mccabe.max-complexity=0'` на текущем snapshot: replay **10**, padding **7**, retry **9**, terminal stop **4**, driver **97**, `drive_session` **2**, `_assert_tool_pairing_invariant` **14**, `_verify_failed_in_pairs` **7**, `_build_tool_calls` **6**. Nested `record_usage` **2**, `finish` **5**, `_request_shape_failure` **2**, `_compose_request_payload` **4**. Это дополнительный просмотр распределения, не предложение менять порог конфигурации и не утверждение, что каждый helper нуждается в дроблении. Ruff команда с диагностическим порогом 0 закономерно exit 1. Новые измерения получены отдельно скачанным Ruff версии из `uv.lock`; проектное окружение не было восстановлено, см. §15.

### 11.2. Разграничение существующих seams и оставшейся orchestration

| Тема | Уже реализовано и где | Что реально осталось в драйвере / следствие для дальнейшего дизайна |
|---|---|---|
| Replay | `_restore_conversation_history` + `_merge_memory_summary_context`, `EventLog.read_all` | первоначальный `task`/`run_started` append, lifetime summary/history; не строить второй replay service без найденной необходимости |
| Tool pairing/stop | `_build_tool_calls`, `_tool_calls_for_message`, `_pad_unexecuted_tool_results`, `_handle_terminal_tool_stop`; `run_session` и `SessionRun` в `loop.py` | управление последовательностью stop → padding → projection, счётчики и turn handoff. Нельзя повторно реализовать execution/parallel settlement в P6 |
| Execution / batching | `loop.py`: `classify_batches`, `_execute_one_sequential`, `_execute_batch_parallel`, `_dispatch_parallel_batch`, `_settle_parallel_batch_failure`, `run_session` | `run_session` сам управляет batching, `BETWEEN_ROUNDS`, hook sink/contextvar, cap и post-loop stop. Driver не владеет scheduler; после неоднозначного parallel submit повторять возможный side effect нельзя |
| Prompt assembly | `prompt_composer.py`: `PromptParts`, `build_prompt_parts_v2`, `to_anthropic_request_v2` / `to_openai_request_v2`; provider finalizer `providers/message_rules.py` | локальная closure связывает per-turn inputs, семью и проверку роли и вызывается до и во время compaction. P1 — seam **связывания**, не новый composer и не подмена finalizer |
| Budget and compaction | `ContextBudget.check` + `record_compaction_attempt`, `estimate_tokens`; `project_messages_after_mask`, `find_turn_boundary_backward`, `FullLLMCompactor.compact` | driver владеет workflow decisions, эффектами и commit локальных payload/history/summary. P3 не переписывает пороги или summarizer. Driver вызывает `project_messages_after_mask` для message dicts, **не** `ObservationMasker.mask_history` для TraceEvent |
| Projection / artifacts / security | `projection.project_for_model`: ошибки, ограничение UTF-8 bytes, elision и `ArtifactStore.put`; `_redact` после projection; `EventLog` отдельно redacts content, если ему передан redactor | tool output event формируется раньше model projection/redaction и имеет свой путь через `EventBus`; нельзя считать, что `_redact` защищает все console/log payloads. Разные redactors можно передать независимо; доказательства не обобщать |
| Scope & skills | `expansion.py`: `ExpansionState`, `ExpansionDecision`, `next_level`, `near_miss_evidence`; `observations.py`: `ObservationRender`, `build_observation_block`; `path_risk.py`, `skills._inject`; ceremony helpers в coder_loop | драйвер связывает transaction, snapshot, previous pairs, переходы, skill reading и telemetry. P2 — coordination существующих функций, не новый policy engine |
| Provider / retry | `ProviderChain` делает per-entry fallback, cooldown ledger и conformance; `_request_with_cooldown_retries` — outer per-turn cooldown; chain session retry в driver | не объединять три retry уровня или терять IDs между chain invocations; attempt logs из seam и успешной ветки имеют разных владельцев |
| Persistence / display | `SessionState`, `EventLog`, `SessionDatabase`, `EventBus`, stats parser | SQLite — авторитет при append; mirror JSONL best effort. `EventLog.read_all` сначала читает DB по run_id, при injected DB не fallback на зеркало, legacy/default может. `fa.stats` парсит `provider_attempt`, поэтому двойные rows меняют totals |
| Session lifetime | `drive_session` + `context.set_current_session/reset_current_session`; `run_session` также устанавливает вложенный context и очищает hook sink в `finally` | не сдвигать context scope или hooks sink cleanup; Anthropic composer читает flags из current session, при отсутствии загружает flags с диска |

Эти границы — реальные функции и классы, а не предлагаемая новая модель. Перенос в соседний модуль нужен только при ясном ownership, проверке циклов imports и тестовых patch targets.

### 11.3. Поправка к pairing, replay и безопасности

Моя первая редакция слишком широко утверждала, что IDs replay всегда согласованы. На самом деле `model_msg` сохраняет **raw** `response.tool_calls`, а current-turn assistant history использует `_tool_calls_for_message` с fallback ID из `_build_tool_calls`. `_restore_conversation_history` позже читает raw `model_msg.tool_calls`, а у `tool_result` использует сохранённый `tool_call_id`. При отсутствующем raw ID это потенциальное различие между текущим turn и resume; требуется отдельный тест реального отсутствующего ID → log → resume и проверка плана, прежде чем называть это дефектом или менять код. Аналогично, replay выбирает `result.stdout` либо `summary`, а не повторяет точно прежний `project_for_model` и `_redact`; EventLog может иметь собственный redactor. Это не обещание побайтовой идентичности model-facing history на resume.

`_assert_tool_pairing_invariant` использует **множества** ID: он проверяет равенство множеств, но сам по себе не обнаруживает кратность одинаковых IDs и не проверяет хронологию пар. В `_request_shape_failure` сообщение упоминает duplicate, но из реализации этой debug-проверки такую гарантию выводить нельзя. Provider conformance (`message_rules.py`) — отдельный production gate; его реальные проверки и тесты нужно изучать отдельно, не приписывать их debug helper.

Уточнение по near-miss (§4 A3): запоминается один `_last_observed_evidence`, а не множество всех ранее виденных. Последовательность A → B → A потенциально снова пишет A; отсутствие evidence или transition само по себе не сбрасывает ключ. Утверждение «одна запись на каждый уникальный tuple за весь run» было бы неверно, несмотря на комментарий в source.

### 11.4. Точная механика retry, budget и частичных эффектов

- `_request_with_cooldown_retries`: **максимум** три chain invocation при последовательном exhaustion, а не три всегда. Для каждой exhaustion exception логируются содержащиеся attempts (они могут быть пустыми, если все entries на cooldown); `api_retry` и sleep только до последних попыток. Production wait = минимум будущих cooldowns, с минимумом 1 секунда; если активных нет — 5 секунд; pytest shim 0.01 секунды. `ProviderChain.request` назначает собственный logical ID каждому вызову, если не передан ID. Сессионный счётчик exhaustion увеличивается после исчерпания per-turn попыток и **не сбрасывается на успех** в показанном driver. `continue` расходует следующий `turn` и может упереться в `max_turns`.
- Успешный chain вызов пишет `provider_attempt` + `llm_call` + `usage` + output до AFTER_LLM_CALL; при отрицательном AFTER hook tokens уже учтены. Exhaustion attempt rows фиксируются seam, но отдельный `llm_call` и обещанный ADR-9 Tier-2 event в текущем driver на этом пути не создаются. Не приравнивать «logical call» к одному пользовательскому turn, особенно с retry. Соответствие ADR — отдельное открытое исследование, а не цель документа.
- `estimate_tokens` применяет приблизительный chars/4 к содержимому `messages_payload` и `tool_payload`. В Anthropic-ветке composer возвращает сообщения и пустые extras; код не передаёт отдельный `pinned_text` в estimator. Не предполагать точное число реальных wire tokens.
- Если compaction enabled и исходное решение `stage2` **или** `stage3`, драйвер сначала запускает stage2. Если stage2 вызывает exception, `decision` остаётся текущим: первоначальный `stage2` продолжает отправку без повторного hard stop, первоначальный `stage3` запускает stage3. Внутри `try` некоторые effects могут уже произойти; любые предлагаемые result objects не должны молча превращать процесс в атомарный transaction.
- `FullLLMCompactor` сам делает local truncate fallback при отсутствии compactor chain, ошибке запроса или невалидных summary headers; это отдельная политика от внешнего broad catch driver. Artifact offload для stage2 сам best-effort, но `project_for_model` использует `ArtifactStore.put` без того же catch. Не обобщать их failure semantics.
- Stage3 при отсутствии `older_history_text` только предупреждает, затем повторно проверяется уже существующее `decision`; после успеха `budget.check` обновляет decision, но last ratio не присваивается. Зафиксировать эти наблюдения до выбора value object; не «исправлять» их во время переноса.

### 11.5. Выходы и границы событий, пропущенные ранее

1. `summary_written` выставляется **после успешного append** summary, но до output и DB metrics. Ошибка output не проглатывается и может оборвать completion после durable summary; DB metadata errors перехватываются только внутри своего блока. «Ровно один summary» в §4 означает нормальное прохождение контролируемого `finish`, не гарантию при отказах sinks.
2. Tool `OutputEvent` содержит `dict(call.params)`, `result.summary` и error message до model projection/redaction; log path может дополнительно redaction делать независимо. Проверять внешние sinks и секреты на каждой поверхности, а не расширять утверждение A7.
3. `message_extras` копируется в assistant dict после `role`/`content` и **может их перезаписать**; затем при наличии tools `tool_calls` перезаписывается нормализованными данными. Это фактический precedence, а не безопасность неизменного role. Долговременный `model_msg` хранит другую форму: text, raw calls, finish и usage поля, не arbitrary extras.
4. При остановке в tool execution `run_session` уже пишет собственные события; после driver `break` дополнительно пишется `run_stopped` с iteration_cap. Граница логов/объёма результатов требует отдельного contract review. Текущую неточность нельзя исправлять незаметно в P6.
5. Порядок/границы исключений имеют значение: при обычном initial compose ловится только `ProviderRequestShapeError`, а compaction catch ловит `Exception` вокруг нескольких действий, включая compose, log/output и возврат `finish` из try. Ошибка финализации внутри этого try может быть интерпретирована как compaction error; не заявлять, что все `finish` exceptions всегда распространяются из одного и того же места.
6. `_pad_unexecuted_tool_results` использует последнее `run_stopped` только среди новых rows после сохранённой длины, причём `log.read_all()` вызывается до dispatch и снова при padding. Это не transactional snapshot; любые изменения стратегии чтения или конкурентности требуют отдельных доказательств, а не замены индекса предположением о глобальной последовательности.

## 12. Контрольный граф данных и ownership по существующим seams

```text
EventLog.read_all -> replay helper -> memory_summary + conversation_history
state.transaction + prev calls/results -> expansion funcs -> ObservationRender
ceremony helpers + pinned buffer + role + history -> existing PromptParts composer
  -> family adapter -> messages_payload/extras -> estimate_tokens / ContextBudget
  -> stage2 message projector + ArtifactStore -> recompose
  -> stage3 boundary + FullLLMCompactor (+ optional ProviderChain) -> recompose
  -> RequestInfo -> per-turn retry helper -> ProviderChain / message_rules / provider
  -> provider audit + usage -> AFTER hook -> model history + raw model event
  -> _build_tool_calls -> run_session -> SessionRun(stop, results)
  -> terminal-stop helper OR iteration-cap display -> padding helper
  -> failed/result aggregation, expansion latch -> projection + redaction -> history
  -> finish(usage, last ratio, failed names, outcome) -> DB + output + metadata
```

`SessionState` и `EventLog` передаются между несколькими существующими слоями. Ни один новый объект не должен одновременно становиться альтернативным источником правды для transaction, DB и history. Представленные `PreparedPrompt`/`BudgetTransition` — варианты связи данных, а не сущности, уже существующие в коде. Особенно P3 нельзя считать чистой функцией: сейчас она включает обращения к artifact store/provider/log/output и управляет результатом до/после частичных исключений.

## 13. Выверка кандидатов после второго прохода

- **P1:** начинать с существующего `PromptParts` и adapter функций; не создавать второго независимого компоновщика. При переносе надо сохранить session context, family branch, exact extras, флаг caching, позднюю повторную композицию и exception границы.
- **P2:** `ExpansionState` и `ObservationRender` уже существуют. Вероятно достаточно явного orchestration seam; отдельный тип состояния оправдан лишь если он объединяет реальные latches и единый жизненный цикл, без дублирования `SessionState`.
- **P3:** высокая связность остаётся в orchestration, но большая часть механики уже существует. Сначала описать матрицу переходов/частичных ошибок, а не переносить ~430 строк в другой сложный метод; разделять stage2 и stage3 только сохраняя их порядок и тот же `ContextBudget` instance.
- **P4:** существует retry seam и `ChainAttemptRecord`; устранять дублирование структур записи только при доказанном едином владельце, не перенося session-level retry внутрь provider chain. Проверять empty attempts и повторную сессию.
- **P5:** полезен только если value/decision не скрывает raw-vs-normalized различие и текущий precedence extras, а log ещё следует после AFTER hook.
- **P6:** должен вызывать существующие stop/padding/projection seams, не дублировать `run_session` или изменять terminal break. Тесты на durable pairing, provider-visible history и отдельную redaction path обязательны.
- **P7:** полезность класса не доказана: `summary_written` и totals — реальное session-lifetime состояние, но надо сначала проверить, выигрывает ли небольшой узкий owner у closure без лишнего дублирования `SessionState` и без изменения исключений.

## 14. План дополнительной проверки перед любым кодовым срезом

Не заменяет план реализации; это недостающие вопросы к доказательствам по карте:

- Проверить end-to-end resume c raw missing/duplicate ID и отдельно conformance gate; различать фактическую проверку множеств и контракт кратности/порядка. Не ослаблять malformed input tests.
- Для compaction зафиксировать таблицу исходного `allow/warn/stage2/stage3` × enabled/disabled × stage2/3 success/failure × breaker × ошибки logger/output/append; какие state/payload уже изменены на каждой границе. Проверить захват turn-context/skills и флагов family adapter при повторном compose.
- Для provider — успешный первый call, transient→success, все cooldown-skipped/empty attempts, три полных exhaustion, session retry и выход по max_turns, быстрый request-shape, interrupt; сравнивать IDs и порядок событий до/после.
- Для tool path — `AFTER_TOOL_EXEC`, LoopGuard trip, обычный `BETWEEN_ROUNDS`, cap/exact fit, partial result, parallel unknown outcome, отсутствие redactor и custom elider. Проверять отдельно stop effects, audit rows, model history и внешние output events.
- Для завершения — все контролируемые exits, summary vs `usage_turns`, уже записанный summary при ошибке output, DB метрики best effort, контекстные токены после nested `run_session`, неожиданное исключение до finish.
- Различать существующие tests и **доказанные** покрытия: одни имена файлов не доказывают каждый путь; перед конкретным срезом прочитать реальные assertions и добавить недостающие C1/EDGE cases без фиктивных doubles.

## 15. Учёт проверки второго прохода

Проверены код самого драйвера, четыре новые helper seams, `loop.py`, `prompt_composer.py`, `compaction/compactor.py`, `context_budget.py`, `state.py`, `projection.py`, `artifacts.py`, `message_rules.py`, `expansion.py`, production call sites и Q137 ledger. Это review карты, не полноценный аудит каждого соседнего модуля или утверждение отсутствия других ошибок. Изменения только документа; source SHA совпал с исходным снимком.

Для инвентаризации C901 первоначальный вызов `ruff` не найден (exit 127, ephemeral venv отсутствует). Попытка `scripts/arena-env-build.sh` заново компилировала зависимости и была остановлена во время сборки; готовое окружение не заявляется. Вместо этого отдельно получен Ruff **0.16.0** (версия `uv.lock`, wheel проверен по SHA256 PyPI metadata), без установки в репозиторий; диагностический census exit 1 ожидаем из-за порога 0. Тесты и полный gate в этом документальном проходе не запускались; результаты из Q137 — прошлые измерения.

## 16. Аудит предложений и решение о первом срезе

> Историческое решение для выполненного P5. Отложения и приоритеты этой таблицы пересмотрены в §17; сохранены ради traceability.

Повторно проверено по текущему коду и перечисленным seams: потенциальная архитектурная польза — не равна количеству ветвей, вынесенных из драйвера. Здесь «брать сейчас» означает узкий срез с отдельным объявлением и подтверждёнными тестами, не одобрение всего P1–P7.

| Вариант | Решение | Обоснование / упрощение |
|---|---|---|
| P1 composer | Отложить до появления конкретной необходимости в явной границе recomposition. | Есть готовый `PromptParts` и адаптеры; текущее замыкание фиксирует turn-local данные для stage2/3. Новый class/DTO сейчас может лишь заменить видимую closure на много аргументов и скрыть флаги contextvar. Не считать его обязательной предпосылкой P3. |
| P2 expansion | Отложить как цельный срез. | Политика уже отделена в `expansion.py`/`observations.py`; оставшаяся часть связывает несколько session latches и effects. Сначала обосновать одного владельца состояния, иначе новый object дублирует state или станет container'ом. |
| P3 budget/compaction | Отложить, несмотря на наибольший вклад в размер. | Он наиболее подвержен изменению границ exception и частичных effects, при этом существующие compactor/budget уже владеют вычислениями. Сначала fault/transition matrix; не извлекать монолит за счёт переноса сложности. Поскольку P1 может оказаться не нужен, исследовать узкую передачу существующего callable вместо обязательной P1. |
| P4 provider telemetry | Отложить. | Current retry seam и success logging имеют разные владельцы; общий abstraction легко объединит разные logical IDs или затронет нерешённый ADR-9 Tier-2. Нужен сначала контрактный анализ, а не косметический перенос. |
| P5 model response | **Брать сейчас, но только no-tool terminal decision.** | Предыдущий P5 слишком широкий: response-history writing и stop classification имеют разные outputs, а raw vs normalized IDs и extras создают самостоятельные риски. Небольшой `_finish_no_tool_response` (имя может быть уточнено) возвращает существующий `SessionOutcome` и управляет только abnormal stop audit/output; caller уже гарантирует отсутствие calls и вызывает существующий `finish`. History и `model_msg` остаются до него в драйвере. Класс или DTO не нужен. |
| P6 tool handoff | Отложить целиком. | Уже есть stop/padding/projection seams. Совмещать exhaustion latch, output и history в одном новом методе опасно: разная ответственность и terminal path; позднее рассматривать только независимую границу при наличии достаточной C3/redaction матрицы. |
| P7 completion | Пока не делать. | Closure — один session-lifetime owner; класс с теми же captured fields сам по себе не снижает coupling. Не хватает оснований заменить его новым объектом. |

**Выбран один вариант:** P5, сокращённый до no-tool terminal decision. Это даёт понятную фазовую границу без новых типов и не переписывает рядом лежащие механизмы. После него повторно оценивать выгоду следующего среза, не продолжать только ради C901. Verification и результат будут записаны отдельно; текущая карта остаётся снимком до изменения кода.

### P5 execution record

Выполнен только выбранный узкий срез: `_finish_no_tool_response` возвращает существующий `SessionOutcome`, пишет warning/stop только для abnormal no-tool response; `model_msg` и вызов `finish` остаются у драйвера. Новая C1 матрица (stop, end_turn, empty, length, content_filter, unexpected) проверяет authority, output и summary; другой C1 подтверждает обработку tool-bearing ответа и сохранение предыдущего результата. Банк 89 passed, ratchet 11 passed; targeted Ruff/format/Pyrefly/mypy/diff-check exit 0. Producer audit/output и caller EDGE mutations пойманы. Детали/команды/ошибочный первый выбор test ID и восстановленный SHA в Q137 ledger. Драйвер 97→93, helper 5; это не полный аудит и не live-host acceptance. SHA и номера строк §1–15 относятся к исходному снимку до этого среза.

## 17. Пересмотр: читаемость модулей для агента, а не только C901

### 17.1. Поправка к направлению

Пользовательское замечание справедливо: **извлечение ветвей в helpers, оставшихся в том же файле, может облегчить конкретную функцию, но само по себе не решает проблему чтения модуля**. Мой прежний критерий «отдельный модуль только после стабилизации seam» был чрезмерно осторожным. Это отодвигает устранение существенной проблемы и делает локальное уменьшение C901 видимее реального выигрыша для читателя. P5 как проверенный небольшой шаг не нужно отменять, но продолжать по той же схеме без реального уменьшения когнитивной нагрузки файла — плохой план.

Актуальный снимок после P5: `coder_loop.py` **2198 строк / 104 802 UTF-8 байта**, `_drive_session_inner` **1325 строк / 66 255 символов**, C901 **93**; `tests/test_coder_loop.py` **1488 строк**. Исходный замер драйвера — **125**, история 125 → 115 → 109 → 101 → 100 → 97 → 93 в §11.1 и P5 record. Данные о размере — `wc -l`, `Path.read_bytes()` и AST диапазон в текущем рабочем дереве, не подсчёт LLM-токенов; числа не являются ни потолком, ни метрикой качества. SHA текущего исходника `8d2ed317cc5623fd89ecaeba7bc2dfdb3d85870845d40f024a2ceeed217b532c`. Предыдущие номера строк и snapshot в §§1–15 исторические.

Проблема двойная: (1) файл объединяет несколько предметных ответственностей и заставляет агента держать слишком много контекста; (2) **сама функция всё ещё 1325 строк**, и один перенос готовых верхнеуровневых helpers проблему её последовательного понимания не решит. Новая цель — ориентироваться на понятный control flow, стабильное владение состоянием и тематические модули, а не только на числовое снижение C901 или длины. Фрагментация на десятки однострочных файлов тоже ухудшит навигацию.

### 17.2. Критерии качества для читателя и следующего среза

Для каждого нового seam/module ответить до кода:

1. **Путь чтения:** с какого публичного entry point начать; какие 1–3 непосредственно связанные реализации нужны для одного сценария; где указаны инварианты, side effects и terminal transitions. Число — ориентир для ревью, не жёсткий закон; security/композиция закономерно требуют дополнительных файлов.
2. **Одна понятная ответственность:** имя и короткий module docstring говорят, за какой жизненный цикл/протокол отвечает модуль. Не группировать только по признаку «все это helpers»; не создавать `utils.py`/всеобъемлющий `context.py`.
3. **Видимый главный маршрут:** driver должен показывать последовательность и решения о продолжении/остановке, а не скрывать их в длинной цепочке однострочных вызовов. Понятны владелец данных, точка commit и где находятся исключения.
4. **Зависимости и совместимость:** направленный граф `composition root → orchestration → domain/seam → существующие collaborators`; не импортировать обратно `coder_loop` из нового модуля, если он импортирует этот модуль. Не использовать implicit global/contextvar как новый канал передачи состояния. Сохранить `drive_session`, `SessionOutcome`, default values и текущий import surface для внешних потребителей, включая identity типа при реэкспорте.
5. **Рабочий набор:** измерять до/после размер основного файла и **осмысленный объём кода, необходимый для чтения конкретного сценария**, число пересечённых модулей и изменения явных зависимостей; показывать call chain и эффекты. Нет требования уменьшать сумму всех строк или насильно соблюдать произвольный лимит.
6. **Не переименовывать поведение в процессе переноса:** состояние, последовательность effect/exception границ, cancellation/stop, authority и output сохраняются; альтернативный смысл — отдельный FIX с отдельной traceability. Fail-closed managed boundaries нельзя обходить.
7. **Тесты также читаемы:** тематические test banks допустимы, но не дробить механически и не клонировать fixtures; использовать реальные composition roots. Сохранить обнаруживаемость тестов и их producer/EDGE proof.

### 17.3. Предлагаемые модули по ответственности — дизайн для обсуждения, не готовая схема

Имена ниже provisional и должны сверяться с существующими модулями перед внедрением. Они предлагаются как **несколько связных областей**, не как один файл на helper. Не использовать автоматически все четыре: если связность/тесты показывают естественное расположение в существующем owner, предпочесть его. В каждой строке указаны как уже вынесенные вещи, так и ещё остающаяся в driver orchestration.

| Кандидат и первые читаемые сценарии | Предполагаемый owner / граница | Что остаётся видимым в `coder_loop` и основные риски |
|---|---|---|
| **Conversation history и tool-message protocol** (рабочее имя `conversation_history.py`) | Уже выделенные `_restore_conversation_history`, `_merge_memory_summary_context`, `_build_tool_calls`, `_tool_calls_for_message`, pairing/final-role checks — только если при разборе подтвердится их общая ответственность за message representation. Учесть raw audit vs normalised ID и replay. Здесь возможен первый физический перенос: replay + summary merge, затем отдельно границу protocol; не требуется перемещать всё разом. | Порядок вызовов (replay перед append, проверки до provider, model event до tool dispatch) остаётся в оркестраторе. Replay использует `EventLog.read_all`, не становится новым event authority. Direct private imports тестов `_restore_conversation_history`, `_assert_tool_pairing_invariant` надо обрабатывать осознанно; протокол debug assertions не объявлять полной проверкой конформности. |
| **Tool-turn handoff** (имя уточнить; не `loop.py`) | Рассмотреть вместе `_handle_terminal_tool_stop`, `_pad_unexecuted_tool_results`, и оставшийся coordination после `run_session`, но сохранить `loop.py` хозяином execution, batching и hooks, а `projection.py` хозяином model projection. Не утверждать, что stop classification и redaction обязаны жить в одном модуле: их объединение годится лишь при ясном сценарном интерфейсе и ownership. | Главный driver видит terminal vs continue и место последующего вызова модели. Ни один внутренний модуль не должен заново запускать инструменты или менять stop/partial results, durable rows и redaction. Проверить C3 и parallel uncertain execution. |
| **Provider turn / retry** | `_request_with_cooldown_retries` уже выделен; его тематический owner может жить рядом с provider orchestration, но не внутри `ProviderChain` без анализа границ: последний владеет per-entry fallback/validation, а driver — turn/session retry и output. Выносить event emission вместе с проверкой реестров producers. | Driver явно обрабатывает session retry/terminal outcomes; не маскировать logical IDs, cooldown и difference между transport/per-turn/session retry. Если переместить лишь один helper в отдельный микрофайл, выгода недостаточна; допускается задержать до появления cohesive owner. |
| **Context-pressure / compaction coordination** | `ContextBudget`, `FullLLMCompactor` и projection уже существуют. Рассмотреть отдельный модуль orchestration для stage2/stage3, поэтапно с чёткими входами/выходами/эффектами; разумно исследовать передачу существующего callable composer, но не навязывать callback или класс до проверки. Это главный кандидат на фактическое сокращение **длины функции**. | Основной loop показывает вызов и решение продолжить/остановить; новый модуль не может незаметно стать атомарным или поменять broad try/partial writes. Предварительная матрица §14 и текущая спецификация — обязательны. Один перемещённый 430-строчный монолит не считается завершением улучшения. |
| **Terminal outcome / session bookkeeping** | Сейчас `SessionOutcome` принадлежит `coder_loop`, `_finish_no_tool_response` там же, usage/finish замыкаются в driver. Возможное будущее объединение outcome types + terminal decision в отдельной тематической области имеет смысл только при действительно общей ответственности; session bookkeeping не переносить автоматически. | `workflow_controller.py`, CLI, managed subagent и tests импортируют `SessionOutcome` из `coder_loop`. Если тип переедет, фасад обязан импортировать и реэкспортировать **тот же объект**, без второго класса; избегать обратного импорта из нового модуля. Пока возможен отдельный seam, но маленький файл исключительно для 49 строк без более широкой cohesion может добавить лишний переход. |

Корректировка старых P1–P7: P1/P2/P4/P6 больше не отложены только потому, что они потенциально требуют отдельного файла; решение зависит от того, **уменьшает ли новая граница читательский working set и явно ли выражает ownership**. P3 остаётся наиболее рискованным, но его размер — самостоятельный аргумент за приоритет анализа и подготовки, а не за бессрочное откладывание. P5 уже выполнен внутри файла: при проектировании терминального owner учесть и этот helper. P7 не превращать в класс лишь ради перемещения — сравнить конкретный граф чтения и state ownership.

### 17.4. Эскиз поэтапной работы и ориентир навигации

Это порядок для дальнейшего планирования, **не разрешение автоматически выполнять все этапы**:

1. **Карта entry points в самом коде:** короткий модульный docstring у фасада после реорганизации должен показывать sequence фаз и ссылаться на смысловых владельцев. Документ worklogs — вспомогательная карта; на неё одну нельзя опираться для понимания текущего кода. Не создавать дублирующую машинерию/мануал, расходящийся с кодом.
2. **Пилот физического переноса связной области history**, а не просто ещё одного helper в исходном файле. Прежде чем выбрать файлы, проверить все внутренние вызовы и точные import/patch paths. Можно начать с двух связанных функций replay/merge и честно признать ограниченный выигрыш (~53+ строк вокруг replay, до учёта импортов), затем расширять только при видимой cohesion. Граница не меняет driver control flow; она подготовительный шаг, а не закрытие 1325-строчной функции.
3. **Разобрать сам driver по смысловым фазам**, в первую очередь context-pressure и turn-level scope/tool handoff. Для каждой фазы сначала составить таблицу входов, live state, эффектов, return/continue/break и исключений; выбирать узкие модули/значения только на основании этой таблицы. Оркестратор не должен превращаться в «магический» state machine с неявными мутациями.
4. **Переоценить tests и проверки по настоящим границам:** если producer переместился, его местоположение меняется, но не исчезает обязанность проверять реализацию и достижимость от реального driver. Сначала разбирать фиксацию source path, затем менять тест или checker только так, чтобы он продолжал обнаруживать удалённый producer **и** разорванный вызов; не заменять на поиск строки в комментарии и не понижать floors без доказательства.
5. После каждого этапа показать карту изменённых вызовов/состояния, размер и количество модулей, C0–C3 где применимо, producer/EDGE kill checks и фактические команды. Сравнивать читаемость до/после по конкретному примеру (например «восстановление истории после compaction», «AFTER_TOOL_EXEC stop», «stage2 failure»), а не объявлять успех по числу строк.

Пример целевого маршрута чтения (схематично, имена и итоговая организация не утверждены):

```text
Обычный turn: coder_loop.drive_session → явный драйвер/turn → provider + tool-turn seam
Восстановление: coder_loop.drive_session → conversation-history seam → EventLog.read_all
Давление контекста: драйвер → context-pressure seam → существующие ContextBudget/compactor
Tool stop: драйвер → tool-turn seam → loop.run_session + StopInfo → padding/projection при continuation
```

Для понимания orchestration нормально открыть несколько предметных файлов. Цель — чтобы они были предсказуемыми по имени и у каждого был понятный владелец, а не чтобы один файл скрывал все детали или чтобы читатель вынужден был открывать десятки микромодулей.

### 17.5. Реальные ограничения миграции в репозитории

- `src/fa/inner_loop/workflow_controller.py`, CLI и managed subagent импортируют публичные имена из `coder_loop`; разные тесты непосредственно импортируют приватные helpers. Проверять конкретный контракт на каждый перенос: публичный facade и identity сохранять; для приватных test imports использовать оправданную совместимость или переносить тест к настоящему owner, не оставляя бессмысленные бесконечные alias wrappers.
- `scripts/check_producer_consumer_contract.py` использует явный `PRODUCER_FILES` и точный floor числа emit sites, `scripts/check_log_kind_contract.py` — отдельный список producer files для console-mirror heuristic. Перемещение emitter может сделать анализ неполным или сломать floor. Добавление нового owner в сканирование должно сохранять точность/count и негативные mutation controls. Эти проверки эвристические, не доказывают живую достижимость и exact dual-write order.
- `tests/test_pr3_wiring.py` ожидает конкретные calls в AST `coder_loop.py`; `tests/test_s6_log_kind_typing.py` ищет compaction producer там же; `tests/test_slice_ceremony_injection.py` ищет конкретные тексты/порядок в этом файле. Такие тесты не следует обходить alias/comment для прохождения: при изменении архитектуры пересмотреть oracle, удерживая исходный инвариант, producer и caller edge.
- `pyproject.toml` включает pylint циклических импортов и duplicate-code; полный lint ранее уже имел исходные проблемы. Для переноса проверять **новые** циклы и сравнивать с baseline; не добавлять waivers и не выдавать частичную проверку за полный зелёный gate.
- Прямые monkeypatch/import targets и tooling могут быть чувствительны к расположению: уточнять по конкретному изменению; сохранить публичную совместимость, но не превращать старый файл в коллекцию реэкспортов всех внутренних деталей. Любой runtime import cycle проверять с реальными entry points, не только статическим поиском.
- `tests/test_coder_loop.py` тоже длинный. При достаточной предметной связности можно позже перенести тесты в существующие/новые тематические банки, оставив общие реальные fixtures доступными без импорта из другого test-модуля; отдельный тестовый срез и собственные mutation checks обязательны.

**Текущий статус:** выполнен только анализ и правка карты. Код и tests в этом проходе не менялись, новые архитектурные модули пока не существуют. Full gate и live-host acceptance по-прежнему не закрыты; перед первым кодовым переносом требуется объявление конкретного среза, файлов и проверок по правилам пользователя.

### 17.6. Пилот границы history: выполнен, с ограничениями

S13.2/I-52 replay и связанный merge перемещены в `src/fa/inner_loop/conversation_history.py`; `coder_loop` остаётся composition root и вызывает seam до нового user event. Исторический logger warning сохранён. Тела обеих функций совпали по AST с pre-slice; C1 replay/compaction/no-dedup и C0 failure проверены, producer и EDGE mutants пойманы. Реальный путь чтения для replay: `coder_loop.drive_session` → `conversation_history.restore_conversation_history` → `EventLog.read_all`; авторитет и формат логов не изменены. Файл driver 2198→2136 строк, новый модуль 78 строк; `_drive_session_inner` не стал короче и этот перенос **не завершает** его декомпозицию. Команды, результаты и SHA — Q137 ledger.

Обнаружено предшествовавшее этому переносу расхождение source-site producer floor для `hook_deny`: объединённая stop-ветка оставила 3 физических emit sites вместо 4, но две разные terminal paths всё ещё существуют. Проверка producer-consumer exit 1 как до переноса, так и после (сравнение saved source). Нужен отдельный анализ и решение, сохраняющее path-sensitive producer/EDGE проверки; не считать полный gate зелёным и не ослаблять check ради прохождения.

### 17.7 Protocol/tool-turn extraction — ten existing units, two ownership boundaries

The next slice moves four existing protocol functions (`_assert_tool_pairing_invariant`, `_assert_final_role_invariant`, `_tool_calls_for_message`, `_build_tool_calls`) to `conversation_history.py`, and six tool-turn functions (`_redact`, `_fallback_projection_handler`, `_projection_spec_for_call`, `_pad_unexecuted_tool_results`, `_handle_terminal_tool_stop`, `_failed_tool_names`) to `tool_turn.py`. These are ten transferred units, not ten independently demonstrated architectural seams. Nine bodies are AST-identical to the pre-slice driver; terminal-stop deliberately restores two separate terminal emit sites with the same data and common observation. Former test-facing private imports and `LOOP_GUARD_REASON_PREFIX` identity remain available through the driver.

The driver file shrank 2136 → 1921 lines; history owner is 203 lines and tool-turn owner 123. This reduces the default file-reading surface, not the main function's branch complexity: the driver still orchestrates the same work, and the total code has not disappeared. `loop.py` still owns execution; no new scheduler or generic abstraction was introduced. The producer and LogKind checkers now scan the tool-turn owner. The former remains at its existing four-site `hook_deny` floor and passes; independent mutations of either relocated terminal site fail it. This resolves the structural checker regression documented in §17.6, not the remaining full-gate failures.

Verification after restoration: 155 passed / 1 deselected (known CLI managed-provisioning case), checker/path/typing/ratchet bank 42 passed; both contract scripts, Ruff, format, targeted Pyrefly, targeted mypy and diff-check exit 0. The undeselected bank was also run: 155 passed / 1 failed, the pre-existing CLI `managed_execution_unavailable` failure. Added a real provider-edge raw/base64 redaction test and per-terminal-site checker mutation tests. Explicit producer and driver-edge mutations for protocol IDs, padding, terminal stop and redaction all failed their targeted tests; files were restored. Import-order probes passed, not a proof of all import orders. Live-host ledger-append tests remain planned and were not run; no full gate was rerun.

### 17.8 Response and continuing tool-turn phases (P5/P6)

The driver now calls `conversation_history.record_model_response` only after `AFTER_LLM_CALL`, then retains no-tool completion, actual `run_session`, and terminal break. For non-terminal tool turns `tool_turn.prepare_continuing_tool_results` emits the cap signal and pads; the driver then updates failed/collected results and previous-turn pairs, before `tool_turn.append_tool_turn_messages` performs the exhaustion latch + dual-write and ordered output/project/redact/history append. Explicit arguments and the returned latch keep ownership visible; no execution scheduler, policy or session-lifetime object is introduced. The order of effects and raw audit versus canonical provider IDs are preserved. The `tool_turn` helper has a wide argument list: it reflects the existing separate dependencies, and is a tradeoff rather than evidence all turn complexity is eliminated.

`coder_loop.py` 1921 → 1866 lines (including navigation doc update); `_drive_session_inner` 1325 → 1260 lines; diagnostic Ruff C901 93 → 81. History and tool-turn owners grew to 236 and 223 lines. The navigable path is now driver → response recorder or continuing tool-turn owner → existing projection/registry/log; callers needing full order still read the driver. The numbers do not prove maintainability or total complexity reduction.

The existing S6 per-site proximity test previously accepted the driver's final `run_stopped` cap row due to a nearby **unrelated** emit; moving that emit exposed the flaw. A narrow AST recognition now checks the actual final `iteration_cap` row immediately followed by `return finish(...)`, and a real `drive_session` test checks matching `session_end`; the remaining proximity heuristic remains unchanged and is not proof of exact pairing elsewhere. It is not a new general exemption for all stops.

Targeted restored banks 144 passed/1 deselected, 56 passed, 106 passed; both observability checkers, targeted Ruff/format/Pyrefly/mypy/diff and two import orders exit 0. A broader run including `test_s7_correlation.py` gave 144 passed/1 deselected/5 setup errors: the existing CLI fixture gets `managed_execution_unavailable` before the driver. Eleven explicit mutations failed their tests: model audit and history producers, response edge, cap producer and edge, exhaustion log/output/latch, tool output, handoff edge and session-end producer. This is targeted evidence, not proof of all paths. Full gate and live-host ledger-append cases L-RCPT-2/6 and L-ENTRY-4 were not rerun.

## 18. Agent-legible code: requirement and sub-goals (2026-11-09)

### 18.1. Key requirement

For a representative task, an unfamiliar agent must be able to **locate the owner, understand the relevant invariants and state/effect order, make a bounded change and run a discriminating verification** with a small, predictable working set. Optimize the *whole task path* (entry point, relevant ranges, contracts, adjacent dependencies and tests), not just any single file, model context size or function complexity. Security and existing contracts are non-negotiable.

No file-length target, threshold, floor, review trigger or automatic LOC gate is adopted. File and function size are contextual observations only: investigate whether the code has cohesive ownership, whether related invariants and state/effect order are discoverable together, and whether understanding one task requires excessive unrelated reading or excessive file hopping. Never split, merge, pad or rearrange code just to change a number; preserve security and compatibility. Count physical lines (`wc -l`) only when documenting an actual snapshot, alongside relevant paths/ranges and qualitative tradeoffs.

External grounding as of 2026-11-09: OpenAI's [harness engineering](https://openai.com/index/harness-engineering/) describes a short repository map and navigable knowledge as system of record; Anthropic's [skills design](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) describes progressive disclosure and evaluating representative tasks; the [2026 agentic codebase review](https://maintainable.software/agentic-engineering-part-2-agentic-codebase-principles/) identifies locality, cohesive ownership, bounded blast radius and narrow feedback. These sources do not establish a universal optimal file size; none is adopted here. Existing `AGENTS.md` is 376 lines before this addition: a broader routing/documentation audit is worthwhile, but blindly shrinking it or removing its safety rules is out of scope.

### 18.2. Sub-goals and verification, dependency order

- **AL1 — baseline paths [IN PROGRESS].** For representative changes (replay/pairing, model response→tool results, context pressure/compaction, scope expansion, session completion), record entry → owner → effects → focused tests, files and *actual ranges/bytes* read, largest required function and risks. Start from current source, not stale historical map. Report before/after on the same tasks; no assumption that an agent must read every line of every referenced file. No pretense of controlled benchmark from one manual run.
- **AL2 — cohesive phase owners [IN PROGRESS].** Reduce `coder_loop.py` and its 1260-line driver by extracting subject-owned phases where their ordering and outputs can be explicit and verifiable. Reuse `conversation_history`, `tool_turn`, `expansion`, `observations`, `prompt_composer`, `ContextBudget` and compactor; avoid a swarm of tiny files. Current baseline `coder_loop.py` 1866, `conversation_history.py` 236, `tool_turn.py` 223, `loop.py` 735, `expansion.py` 246, `observations.py` 182, `prompt_composer.py` 276 physical lines. These figures are the baseline, not targets or thresholds.
- **AL3 — risk-first dependency order [OPEN].** Map live variables, early exits, dual writes and fault behavior before moving compaction or provider/session completion. Preserve terminal `break`, partial effects, exceptions, and fail-closed decisions; avoid moving complexity to anonymous parameter bundles. Defer unresolved product/policy choices to Q# rather than silently alter behavior. No assumption each phase must become a new module.
- **AL4 — source-first navigation [OPEN].** Maintain a short sequence and pointers at entry points and clear module responsibility docstrings; measure the entry-to-owner route. Review oversized root instructions separately with a compatibility and safety inventory before editing their existing rules. Do not introduce a parallel documentation system.
- **AL5 — behavioral proof [OPEN].** For each coherent slice: plan/ADR traceability, exact files, current→target, failure behavior, C0–C3 as applicable, explicit producer/EDGE mutants, adjacent scanner and import checks, restored targeted banks and diff. Preserve source-path-sensitive tests via equivalent or stronger tests; count observed effects, not merely AST text. Never conflate local C1/C2 doubles with live-host evidence.
- **AL6 — acceptance and remaining work [OPEN].** Assess representative paths after each major phase: physical LOC, function LOC, files/ranges, coupled state and effects, focused test command/runtime, cycles/indirection, and remaining caveats. A lower LOC or C901 alone is not completion. Full Q137 gate and live ledger append L-RCPT-2/6 and L-ENTRY-4 remain open, and are not subsumed by this refactoring.

**Next selection:** investigate the large chat scope-expansion phase and its existing `expansion.py` / `observations.py` owners. Compare cohesive owner options with context-pressure and session completion; source-check state transitions, dispatch/dual-write, patch paths and tests before announcing an executable slice. Do not extract compaction merely to reach a line count.

### 18.3. AL2 scope-turn runtime owner — executed

`scope_turn.py` now owns the **effectful** chat boundary: transaction snapshot → verify classification → existing pure decision/render → advisory skill read → transition/near-miss audit and console signal. It returns the expansion state, skill name, delta key and render explicitly; driver still chooses chat-only execution, threads state, and appends skill blocks without replacing ceremony. `expansion.py` / `observations.py` remain pure; `loop.py` still owns tool execution. The new file has a real cohesive ownership boundary; inflating it or merging policy and I/O solely for size would undermine AL2. Input surface is wide (13 keyword parameters), a tradeoff to revisit only with a justified shared owner; not a claim of perfect architecture.

Example task path, measured from actual source spans rather than assuming entire files must be read: for "why did verify failure escalate?", pre-slice the driver had scope boundary lines 877–1005 (129 lines/6356 UTF-8 bytes) and `_verify_failed_in_pairs` lines 282–309 (28/1068), in addition to pure policy/render and tests. Post-slice driver boundary lines 842–865 (24/1108) points to `scope_turn.py` evaluator lines 65–200 (136/5414) and classifier lines 35–62 (28/1068), with the same pure modules and focused tests still needed. This adds one file transition and does **not** establish a total-context or token reduction for that task; the benefit is locating the phase without reading unrelated driver code. The source ranges omit imports, contracts, supporting dependencies and tests; these counts are not actual agent read telemetry or a controlled benchmark. Driver file 1866→1726 lines, function 1260→1154; diagnostic C901 81→74, evaluator 8, and these are signals only.

After variable-name normalization and excluding the caller-owned render/block handling, the moved phase statements match the old AST exactly; logger remains `fa.inner_loop.coder_loop`. One initial mechanical substitution also changed the string `scope_expansion`; targeted Pyrefly/mypy detected this, corrected before tests. An existing PLAN S5 literal source check initially failed when the render variable became `scope_turn.render`; a real `render` local restores the existing actual append expression, not a comment or fake oracle. Added C1 sequence high-read L1→L2 then failed verified bash L2→L3, ensuring stale L2 does not survive, plus missing-skill advisory fallback. A checker copied-tree mutation verifies relocated `scope_expansion` emitter is required. Final targeted banks 181 and 133 passed. Eight real producer/EDGE mutants (scope entry, durable/console transition, verify classifier, observation and skill edges, near-miss producer/delta) failed targeted tests. Both checkers, targeted Ruff/format/Pyrefly/mypy, doc links, two import orders, diff-check exit 0. No C2/C3/live-host or complete-gate claim. Further AL1 representative-path measurements and AL3 compaction analysis remain open.

### 18.4. AL2/P1: turn payload composition and compaction rebuilds

`prompt_composer.compose_turn_request` now owns the existing build-parts → family-specific formatting → final-role debug assertion sequence. The driver's per-turn closure still binds its original inputs/defaults and reads provider family at invocation time; its three existing invocation sites (initial, after Stage 2 and after Stage 3) and surrounding exception/partial-update behavior remain in place. No compaction policy was moved. `conversation_history` owns the final-role assertion, used by the composer; tested both CLI-first and provider-conformance-first import orders, not every possible cycle.

A source-navigation example: the old per-turn assembly closure was 43 lines / 2430 bytes; it is now a 31-line / 1679-byte binding and delegation, and the existing composer contains a 38-line / 1459-byte family assembly. This adds a hop but collocates formatting logic with its existing formatter owner and keeps both decision order and bound inputs visible. Counts are observations only, **not targets** or a claim that this reading path consumes fewer total tokens. Driver snapshot before this slice: 1726 physical lines and 1155-line driver function; after: 1711 and 1139; diagnostic C901 74→71. Data excludes the preceding qualitative-plan correction, which explicitly withdrew all LOC thresholds.

The PR3 AST test now checks three driver invocations, the closure→owner edge, and both actual formatter calls, without treating a string in the old file as proof. C1 compaction tests exercise real replay/masking/compactor and assert that Stage 2 masked content or Stage 3 summary reaches the provider; C0 checks final-role assertion on each family. Restored banks: 98 passed and 159 passed. Eight targeted mutations killed (driver delegation, family binding, OpenAI extras, Anthropic formatter, role guard, Stage 2/3 inputs, skill binding). An initial skill mutation used an incorrect test node (exit 4, no tests); corrected node killed the mutant. An initial adjacent bank specified a nonexistent `test_prompt_composer.py` (exit 4, no tests); corrected bank passed. Ruff/format/Pyrefly/mypy, both producer checkers, doc links, imports in two orders and diff-check exit 0. No full gate, live-host ledger append or C2/C3 claim. Context-pressure ownership, its fault matrix, and its established partial-write behavior remain AL3 work, not implicitly resolved by composition extraction.
