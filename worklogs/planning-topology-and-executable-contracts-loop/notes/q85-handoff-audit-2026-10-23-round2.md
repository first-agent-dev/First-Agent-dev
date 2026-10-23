# Q85 — второй раунд: senior/production-аудит выбора механизма handoff

Дата: 2026-10-23 · Статус: **АУДИТ-КОРРЕКЦИЯ к `q85-handoff-decision-2026-10-23.md`**  
База: `i03-execution-workspace-spec-2026-10-15.md` §§2.1/7.1, `workspace.py:1300ff`, `service.py:761`, `supervisor.py:240ff`, `provisioning.py:1ff`, `session/manager.py`, `inner_loop/tools/workflow_tool.py:387ff`

## 0. Что проверено во втором раунде

Пользователь оспорил рекомендацию (2) narrow attester как потенциально избыточную и запросил проверку критерием **«простейшее, полностью покрывающее целевое поведение»** (production-accountable, Decision & Engineering Rules: планы — авторитет по контрактам, переиспользование существующего, без спекулятивных абстракций).

Проверено:

1. `i03-execution-workspace-spec:1358` — §7.1 Acquisition source/data handoffs:  
   > `Reuse _child_run_context; NamespaceRef parent_run_id is controller-attested after actual begin_run.`  
   Это дословное решение автора спеки в пользу **controller-attested**. Первый раунд трактовал фразу §2.1 «target bound to existing parent-child run relationship» как требование durable-проверки в супервизоре; §7.1 уточняет механику — связь доказывает контроллер фактом вызова `begin_run`, супервизор принимает `parent_run_id` как заявление.
2. Направление зависимости `E263 ManagedProvisioner` (`execution/provisioning.py:37`): `SessionManager → WorkspaceProvisioner(→ execution)`. Сессия вызывает execution, не наоборот. Первый раунд предложил инверсию `execution → session` (RO-чтение `sessions/*/manifest.json`), что ломает установленный ациклический слой.
3. Текущий trust-модели `acquire_writer` (`workspace.py:1319`): супервизор не проверяет существование run, только `PeerIdentity` + `namespace`-валидатор + `Binding` generation/owner. Handoff с controller-attested не создаёт новой поверхности — тот же principal.
4. Операционная стоимость узкого attester'а: +1 поле `ServiceConfig`, FS-чтение внутри `_transaction`, mount-дрейф `FA_STATE_ROOT`, TOCTOU, удлинение hold-time блокировки, новые коды ошибок и наблюдаемость.

Вывод аудита: **первый раунд переоценил угрозу и недооценил простоту (1). Senior-команда выбрала бы (1) controller-attested со строгими wire-инвариантами, а (2) отложила бы как YAGNI.**

---

## 1. Полная матрица кандидатов (расширена с 3 до 6)

| Вариант | Суть | Проверка супервизором | Зависимость | Проводное изменение |
|---|---|---|---|---|
| **A. Controller-attested (чистый)** | Супервизор принимает `target` как заявление аутентифицированного контроллера | None, кроме валидатора `NamespaceRef` | 0 | Нет |
| **A+ (усиленный, рекомендация)** | То же + wire-инварианты `session_id`/`parent_run_id` без чтения FS | `target.session_id == current.session_id && target.parent_run_id == current.run_id && target.run_id != current.run_id` | 0 | Нет |
| **B. Session-store RO attester (первый раунд)** | `ServiceConfig.session_state_root: Path` → RO-чтение `manifest.json`/`session-log/` внутри `handoff` | FS-чтение, `WORKSPACE_BUSY` при отсутствии | `execution → session` (инверсия) | +1 поле конфига |
| **C. HMAC-токен от SessionManager** | `SessionManager.begin_run` минтит `handoff_token = HMAC(parent, target, session)`; контроллер передаёт токен в `payload`, супервизор верифицирует без FS | Криптопроверка, общий ключ | Общий секрет/ключ, +1 поле wire | Да (`payload: {target_namespace, proof}`) |
| **D. Раздельный release+acquire** | Убрать `handoff` как операцию, делать `release` родителем + `acquire` ребёнком | Нет (два вызова) | 0 | Удаляет `Operation.HANDOFF` |
| **E. Defer (BACKEND_UNAVAILABLE)** | Оставить `service.py:761` как сейчас до SLICE2 STEP2 | Нет | 0 | Нет |

Исключены как несовместимые с инкрементом:

* **D** нарушает «same generation» (§2.1) — `acquire_writer` инкрементит `generation` (`workspace.py:_claim_generation`), handoff обязан сохранить его. Потребовал бы новый флаг `acquire_writer(preserve_generation=true)` — изменение контракта ради обхода, хуже простоты.
* **C** меняет wire-форму `PAYLOADS[HANDOFF]` (`protocol.py:135`) с `_object(target_namespace=NAMESPACE)` на токен — breaking change для всех контроллеров и тестов. Сильный, но несоизмеримо дороже цели; вводится второй секрет-менеджмент без доказанной угрозы.

Остаются реалистичные **A+**, **B**, **E**.

---

## 2. Senior-критерии (DoD + Engineering Rules → чек-лист)

Применён порядок из правил:

1. **Планы — авторитет по контрактам.** Если спека выбрала механику, переизобретать нельзя без RFC к спеке.
2. **Простейшее, закрывающее поведение.** Production-команда штрафует каждую новую зависимость/конфиг/FS-I/O в hot path.
3. **Переиспользование.** Предпочтение существующему коду/паттерну перед новым модулем.
4. **Industry-standard.** Однозначный wire, детерминированная ошибка, отсутствие скрытой распределённой консистентности.

Оценка:

| Критерий | **A+ controller-attested + wire-инварианты** | **B RO-attester** | **E defer** |
|---|---|---|---|
| **Соответствие спеке** | **Прямо указано в §7.1** — `parent_run_id is controller-attested after actual begin_run`. §2.1 «bound to existing» читается как «контроллер уже аллоцировал via begin_run перед handoff». Первый раунд неверно усилил требование. | Противоречит §7.1 (вводит проверку, которую спека делегировала контроллеру). Требует правки спеки. | Честно сегодня, но нарушает SLICE1 STEP3 «19 роутов роучены» и блокирует I03-LIVE witnesses. |
| **Простота / blast radius** | **0 новых файлов, 0 полей конфига, 0 FS-чтений в `_transaction`.** Только 2 сравнения строк внутри существующего `handoff`. Hold-time блокировки не растёт. | +1 модуль `handoff_attester.py` (~80 строк), +1 поле `ServiceConfig`, валидация пути, резолв `fa_state_root()` с env-override, обработка `deadline` для FS-I/O, новые коды `WORKSPACE_BUSY` vs `BACKEND_UNAVAILABLE`, логирование. Hold-time блокировки растёт на `open/read/parse` manifest. | 0, но откладывает решение и оставляет E277 dormancy. |
| **Переиспользование** | Переиспользует **тот же** trust-модель что `acquire_writer` и тот же helper `_child_run_context` (§7). Контроллер уже валидирует `parent.run_id==ctx.parent_run_id && session_id && workspace_path` (`workflow_tool.py:392ff`) перед `begin_run` — супервизор доверяет результату той валидации. | Инвертирует E263: E263 — `session → execution` (сессия вызывает `ManagedProvisioner`), B делает `execution → session` (супервизор читает `sessions/`). Требует нового граничного типа, хотя `fa.session.provisioning` уже запрещает импорт `fa.execution`. | Ничего не переиспользует. |
| **Production-надёжность** | Детерминированная ошибка: `INPUT_POLICY` при несовпадении `session_id`/`parent_run_id`, иначе `WORKSPACE_BUSY` от settled-check. Нет флейков от NFS/монтажа. Наблюдаемость — стандартный `SupervisorError`. | Недетерминированная: контроллер сбросил `manifest.json`? host-путь `FA_STATE_ROOT` совпадает с container-путем? lag ФС? При расхождении — ложный `WORKSPACE_BUSY`, ретрай не помогает до сброса контроллера. Нужен мониторинг mount-дрейфа. При инверсии слоёв — риск циклического импорта при сборке `build_supervisor` (attester тянет `fa.session.manager` в `fa.execution`). | Бросает `BACKEND_UNAVAILABLE` на каждый handoff — честно, но I03 не может закрыться. |
| **Безопасность (реальная, не воображаемая)** | Контроллер уже может `exec`/`create_view`/`pin_reader`/`prepare_bundle` как владелец. Скомпрометированный контроллер с тем же `uid:gid` не получает новой возможности через handoff: он и так может мутировать workspace. Изобретённый `target.run_id` с правильным `parent_run_id` даёт writer мёртвому run без `session DB`/`run_log_dir` — он не может `create_view` вне writer? Может, но это эквивалентно продолжению работы родителем. Нет латерального движения за пределы `same root owner/generation` (проверяет `_Binding`). | Даёт защиту от бага контроллера (handoff в несуществующий run). Но контроллер-баг уже ловится `_child_run_context` (валидирует `workspace_path`/`session_id`/`parent_run_id` до `begin_run`). Дублирование проверки в супервизоре — defense-in-depth, не исправление уязвимости. Цена — распределённая консистентность. | Нет оценки. |
| **Тестируемость** | Чистый unit: `NamespaceRef` + `Binding` + `views_fd` моки. Негативный тест — `INPUT_POLICY` на несовпадение `parent_run_id`. Нет ФС-фикстур. | Требует fake ФС с `sessions/<sid>/manifest.json` + `session-log/<run>/`, резолв `state_root`/`workspace_root`, deadline-bounded I/O. Копирует тесты `test_execution_provisioning.py` без их выгоды. | Тестов нет. |
| **Эволюция** | Wire неизменно `{target_namespace}`. Если позже понадобится durable-проверка, её можно добавить **внутри** `WorkspaceAuthority.handoff` без изменения wire/контроллера — A+ апгрейдится в B без breaking change. | Wire тоже неизменно, но деплой-контракт уже сломан (поле конфига обязательно). Откат к A+ — breaking для операторов. | Блокирует эволюцию. |

**Итог:** по трём старшим критериям (контракт, простота, переиспользование) **A+ выигрывает однозначно**. B — классический over-engineering: добавляет распределённую проверку там, где доверие уже установлено архитектурой (контроллер — единственный writer-актёр, аутентифицирован `SO_PEERCRED`).

---

## 3. Почему первый раунд выбрал B и где ошибся

Первый раунд корректно выписал gap (middle precondition без владельца) и честно взвесил «IDs are not secrets». Ошибка — в весе угрозы:

* Фраза «any caller with same uid can name any run» верна для `acquire_writer` уже сегодня, но не эксплуатируема: единственный caller с этим uid — сам контроллер; второй процесс с тем же uid — это уже компрометация хоста, где handoff — наименьшая проблема (attacker уже может `exec rm -rf` через writer).
* «No second policy engine, no second store» трактовалась как «RO-чтение — не policy engine», но senior-команда читает строже: **любое** чтение чужого durability внутри `WorkspaceAuthority._transaction` — это второй источник истины в hot path, даже если RO. E263 потому и сделан как `session → execution`, а не наоборот.
* Цена B («одно поле конфига и RO-чтение») недооценена: в проде это mount-контракт (`controller FA_STATE_ROOT` ↔ `supervisor host path`), наблюдаемость, документация оператора, тесты на dfrift, удлинение блокировки.

Признание ошибки не отменяет ценности B как defense-in-depth — но production-отбор требует доказать, что без B поведение **не** удовлетворяет цели. Оно удовлетворяет (см. §4).

---

## 4. Рекомендация (исправленная): **(A+) controller-attested + строгие wire-инварианты**

Формулировка для `open-questions-2026-10-07.md:2102`:

> **Q85 — RESOLVED (1) controller-attested + wire invariants.** `WorkspaceAuthority.handoff` проверяет `target.session_id == current.session_id && target.parent_run_id == current.run_id && target.run_id != current.run_id` (и валидность `NamespaceRef` через существующий `NAMESPACE/run_id` валидатор) **до** атомарной замены гранта, без чтения session store. Источник parent-child факта — `_child_run_context` (валидация `parent RunContext/SessionContext/workspace_path` + `SessionManager.begin_run`) на стороне контроллера; супервизор доверяет `parent_run_id is controller-attested after actual begin_run` (§7.1). `ServiceConfig` не получает новых полей. SLICE2 STEP2 приносит `WorkspaceAuthority.handoff` + handler-ногу (parent suspension + `_child_run_context` + handoff RPC) без изменения wire. Будущий переход к durable-attester возможен внутри `handoff` без breaking change.

### 4.1. Владелец и порядок операций (уточнён)

* **Источник факта:** `SessionManager` (как и раньше) — аллоцирует ребёнка, пишет `sessions/<sid>/manifest.json` + `session-log/<run>/` (`manager.py:begin_run`). Но **владелец проверки в супервизоре — сам `WorkspaceAuthority`**, без делегата. Это сохраняет ацикличность `fa.execution ⊄ fa.session`.
* **Владелец аллокации на caller'е:** `inner_loop/tools/workflow_tool.py:387 _child_run_context` + будущая parent-suspension (закрыть file commands, `stop_view`+cgroup barrier, `seal`→`publish` или `release_unused_writer`) — как в §7.
* **Порядок внутри `WorkspaceAuthority.handoff(peer, namespace, *, capability, target_namespace, deadline)`** — тот же, что в первом раунде, минус attester:

```
with _transaction(peer, deadline):
    binding = _owner_only(peer, namespace, capability)  # active_actor == namespace, principal+grant OK
    # (1) settled — переиспользует существующее
    views = os.open("views", dir_fd=binding.fd)
    try:
        if _has_unsettled_views(binding, views) or _read_intent(binding.fd) is not None:
            raise SupervisorError("WORKSPACE_BUSY")
    finally:
        os.close(views)

    # (2) parent-child — wire-инварианты, без FS
    if target.session_id != namespace.session_id: raise SupervisorError("INPUT_POLICY")
    if target.parent_run_id != namespace.run_id:  raise SupervisorError("INPUT_POLICY")
    if target.run_id == namespace.run_id:         raise SupervisorError("INPUT_POLICY")
    # NamespaceRef уже провалидирован dispatcher'ом (run_id shape), дополнительно можно
    # проверить target.parent_run_id shape через тот же валидатор — но он уже not-null valid run ID по wire.

    # (3) same root owner/generation, exactly one grant — уже гарантировано Binding'ом:
    # binding.metadata["status"] == "OWNED" (иначе _owner_only бы отказал),
    # generation не инкрементится (в отличие от acquire_writer._claim_generation),
    # owner_namespace остаётся прежним, меняется только active_actor.

    # атомарная замена гранта (как в первом раунде, без attester)
    binding.metadata["active_actor"] = target.to_dict()  # owner_namespace unchanged
    # generation unchanged — это суть handoff vs acquire
    _replace_private_bytes(binding.fd, "workspace.json", encode_json(binding.metadata))
    old_grant = binding.grant
    binding.grant = secrets.token_hex(32)
    binding.principal = peer.principal  # тот же principal, новый grant
    # fsync уже внутри _transaction/_replace_private_bytes
    return GrantReply(Operation.HANDOFF, binding.grant, None, binding.metadata["generation"], binding.current["revision_id"])
    # journal.reserve → EXECUTING → journal.complete + replies.remember_completed(old_proof, reply)
    # — как в первом раунде §5.1
```

Генерация **не** инкрементится — это отличие от `acquire_writer` (`workspace.py:1375 generation+1`). Handoff сохраняет generation, меняя только `active_actor`/`grant`/`principal`.

`supervisor.py:240ff Q75` остаётся: `CompletedReplyCache._authorize_replay` сравнивает старый proof с кэшем, а `authorize` — с текущим `binding.grant`.

### 4.2. Что **не** делать (явный анти-список для SLICE2 STEP2)

* Не добавлять `session_state_root`/`child_run_attester` в `ServiceConfig` — это инверсия слоёв.
* Не читать `fa.session.manager`/`sessions/*/manifest.json` из `fa.execution` — нарушает `fa.session.provisioning` boundary («deliberately imports nothing from fa.execution»).
* Не менять `protocol.py:135 PAYLOADS[HANDOFF]` — wire остаётся `{target_namespace}`.
* Не вводить новый `Operation`/`payload`-поле/второй journal/lease-сервис.
* Не делать `close_admission`/`drain`/`mark_terminal` внутри `handoff` — parent suspension — это предусловие caller'а (settled views), не действие супервизора.

---

## 5. Два допвопроса — ответы без изменений (подтверждены вторым раундом)

### 5.1. Ревокация исходного гранта — да, атомарно до выдачи нового

Обоснование и порядок `journal.reserve → hmac.compare_digest(old_grant) → wire-инварианты → mint new grant → binding.grant=new → journal.complete → remember_completed` — без изменений из первого раунда §5.1. Q75 replay разрешает чтение кэша старым proof'ом только для того же `request_id`/`operation_input_sha256`.

### 5.2. `SEALED`-but-unpublished блокирует handoff — да, как `release`

`_SETTLED_VIEW_STATES = {PUBLISHED, REJECTED}` (`workspace.py:1435`), `SEALED` не settled (E268 D1). `_has_unsettled_views` вернёт `True`, handoff → `WORKSPACE_BUSY`. Легальный путь — `publish` → `PUBLISHED`, затем `handoff`. `OPEN`/`STOPPING`/`UNKNOWN` также блокируют; `REJECTED` — settled.

---

## 6. Чеклист SLICE2 STEP2 (исправленный, без attester)

Без нового сервиса/конфига/FS-чтения:

- [ ] `src/fa/execution/workspace.py:WorkspaceAuthority` — `handoff(peer, namespace, *, capability, target_namespace, deadline) -> GrantReply` с порядком §4.1 (переиспользует `_owner_only`, `_has_unsettled_views`, `_read_intent`, `_replace_private_bytes`; generation не инкрементит; `secrets.token_hex(32)` для нового grant).
- [ ] `src/fa/execution/service.py:SupervisorService._handoff` — перестаёт `raise BACKEND_UNAVAILABLE`, зовёт `authority.handoff`, проецирует `GrantReply.to_wire_result()` (`_OWNER_REPLY`).
- [ ] `src/fa/inner_loop/tools/workflow_tool.py` — handler-нога SLICE2 STEP2: `candidate = child_run_id(parent.run_id, invocation_count)` → `_child_run_context(ctx, candidate)` → parent suspension (close file commands, `stop_view`+barrier, `seal`→`publish` или `release_unused_writer`) → `handoff` RPC; на успехе — `run_workflow` ребёнка, на ошибке — `workflow_context_error`.
- [ ] Тесты: `tests/test_execution_handoff.py` (C1: settled/unsettled, `INPUT_POLICY` на несовпадение `session_id`/`parent_run_id`, generation preserved, exactly-one-grant, revocation+Q75 replay, SEALED-blocks) + unit для `_owner_only`/`_has_unsettled_views` переиспользования. 7–9 producer-мутантов с byte-exact restore.
- [ ] Док: обновить `open-questions-2026-10-07.md:2102` в `RESOLVED (1) controller-attested + wire invariants` со ссылкой на этот файл; `ledger.md` — E281.

Что **не** делать: `handoff_attester.py`, `ServiceConfig.session_state_root`, чтение `sessions/` из execution, новый `Operation`, новое поле `payload`.

---

## 7. Связь с планом и риски

* SLICE1 STEP3 (19 роутов) — `handoff` последний; до SLICE2 STEP2 честно `BACKEND_UNAVAILABLE` (E277) — не баг, а dormancy. Выбор (A+) не требует досрочной посадки — wire уже роучен, enforcement приходит в SLICE2 STEP2.
* SLICE2 STEP2 уже описан как «reused `_child_run_context`/parent writer suspension and server-acknowledged handoff» — рекомендация лишь **называет** missing piece (wire-инварианты, не attester) и его владельца.
* Spec §2.1:167, §4.1 (SessionManager cutover, CT103a), §7.1 (controller-attested) — без изменений.

Риски A+ и закрытия:

* **Контроллер врёт `parent_run_id`?** Требует компрометации контроллера (единственного процесса с `uid:gid`). При компрометации attacker уже может `exec`/`create_view`/`publish` как владелец — handoff не расширяет blast radius. Wire-инварианты `session_id`/`parent_run_id` ловят случайные баги/опечатки.
* **TOCTOU ребёнка нет в session DB?** Handoff даёт writer мёртвому run — тот не появится в `sessions/<sid>/manifest.json`, но supervisor journal всё равно запишет `active_actor=target`. Это inconsistency аудита, не safety-нарушение: writer остаётся single, generation сохранён. Если позже нужен строгий аудит lineage, можно добавить RO-attester **без** изменения wire (эволюция внутри `handoff`).
* **Два caller с тем же uid?** В проде единственный writer — контроллер; второй процесс с тем же uid — компрометация хоста.

---

## 8. Итог для утверждения

* **Решение (исправлено): (1) controller-attested + wire invariants** — владелец parent-child проверки — `WorkspaceAuthority.handoff` (строгие сравнения `session_id`/`parent_run_id`), источник факта — `_child_run_context` + `SessionManager.begin_run` на стороне контроллера. Spec §7.1 уже выбрал этот путь.
* **(2) narrow attester отклонён для I03** как over-engineering: инверсия слоёв, mount-контракт, FS-I/O в `_transaction`, флейки, без доказанного gain безопасности.
* **Defer (3) остаётся фазой** до SLICE2 STEP2, не решением.
* **Ревокация:** да, атомарно до нового capability; replay — только через `CompletedReplyCache`.
* **SEALED:** да, блокирует `WORKSPACE_BUSY` как `release`.

Следующий шаг: PR — этот файл + правка `open-questions-2026-10-07.md:2102` в RESOLVED (1) + запись `ledger.md` E281, без изменения `src/` (код — в SLICE2 STEP2).

### История решения

* Раунд 1 (`q85-handoff-decision-2026-10-23.md`): (2) narrow attester — зафиксирован как рекомендация, но оспорен пользователем за избыточность.
* Раунд 2 (этот файл): (1) controller-attested + wire invariants — **заменяет** раунд 1 по критерию «простейшее, покрывающее поведение» и прямому указанию спеки §7.1.
