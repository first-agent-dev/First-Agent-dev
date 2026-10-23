# Q85 — решение: кто доказывает parent-child связь для `handoff`

Дата: 2026-10-23 · Статус: **РЕКОМЕНДАЦИЯ к утверждению** (покрывает OPEN из `open-questions-2026-10-07.md:2102`, promotion E280)
Автор: agent-архитектурный разбор по `src/fa/{execution,session,inner_loop}` + `i03-execution-workspace-spec-2026-10-15.md:167`

## 1. Что уже есть и где дыра

§2.1 задаёт `handoff` как `{target_namespace} → {view_ref:null, capability, generation, revision_id}` с тремя предусловиями:

1. **views terminal/settled** у текущего актёра,
2. **target привязан к существующей parent-child связи run'ов**,
3. **тот же root-owner/generation + ровно один активный mutator-грант**.

В `src/` сегодня:

* (1) покрыто: `WorkspaceAuthority._settle_owner` / `_has_unsettled_views` (`workspace.py:620ff`, `_SETTLED_VIEW_STATES={PUBLISHED,REJECTED}`) — то же правило, что в `release`.
* (3) покрыто: `_Binding` (`workspace.py:430ff`) уже хранит `owner_namespace`, `active_actor`, `generation`, `grant`/`principal` и `status=OWNED` — один writer, монóтонный generation, `acquire_writer` инкрементит.
* (2) **не покрыто**: `NamespaceRef{session_id,run_id,parent_run_id}` (`types.py:27`, `protocol.py:49`) валидирует лишь «null или валидный run ID», диспетчер аутентифицирует *principal* (`supervisor.py:PeerIdentity.principal = uid:gid`), а не run. `WorkspaceAuthority`/`ServiceConfig` (`service.py:50ff`) не видят `fa.session.manager` и не могут проверить «существующий run». Единственный хелпер — `_child_run_context` (`inner_loop/tools/workflow_tool.py:387`) — аллоцирует ребёнка через `SessionManager.begin_run` и требует совпадения `RunContext`/`SessionContext`/`workspace_path` — это seam уровня tool, запланированный под SLICE2 STEP2, не под супервизор.

Маршрут `handoff` в `service.py:761` честно висит как `BACKEND_UNAVAILABLE` (E277) — это последний нероученный operation из 19. `exec/inspect/cancel` (E279) и `pty_control` (E280) уже разблокированы.

Вопрос Q85 — не «инженерная деталь», а выбор смысла wire: что означает `target_namespace` и что может доказать тест.

## 2. Три кандидата — честный разбор

|  | (1) Controller-attested | (2) Session-store attester в сервисе | (3) Defer до SLICE2 STEP2 |
|---|---|---|---|
| **Суть** | Супервизор принимает `target.run_id/parent_run_id` как заявление того же аутентифицированного контроллера («controller-attested after actual begin_run», как в E263 `ManagedProvisioner`) | `ServiceConfig` получает `attest_child_run(parent, target)` (или `session_state_root`), супервизор проверяет `target` существует и `parent_run_id == current_active_actor.run_id` **до** перемещения гранта | Оставить `handoff` в `BACKEND_UNAVAILABLE` до handler-ноги SLICE2 STEP2, пусть она принесёт доказательство |
| **Безопасность** | «IDs are not secrets» — любой caller с тем же uid может назвать любой run. При компрометации контроллера (а он уже может `exec`/`create_view`) handoff даёт латеральное движение в произвольный namespace без `SessionManager.begin_run`-проверок (`workspace_path`/`session_id` binding). Узкий, но реальный escalation. Совместимо с текущим `acquire_writer` (он тоже не проверяет существование run) — поэтому не «новый» риск, но расширяет его. | Сильнейшее: супервизор проверяет durable факт, созданный `SessionManager` (manifest `sessions/<id>/manifest.json` + `session-log/<run>/`). Компрометация контроллера не может выдать грант несуществующему ребёнку. | То же, что (1) или (2) в будущем — само по себе не добавляет/не убирает риск, но откладывает его решение. |
| **Развёртывание** | 0 изменений. | **Одна** опциональная зависимость: `Path` к `FA_STATE_ROOT` или callable. В деплое `FA_STATE_ROOT` уже есть (`src/fa/paths.py:42`, `${FA_STATE_ROOT:-$HOME/.fa}`, entrypoint `fa_state_root`), контроллер монтирует `…/sessions` RO, супервизор на хосте видит host-путь. Это *не* «второй durable authority» в смысле плана (вторым был бы второй journal/lease-сервис) — это RO-чтение уже существующего durable факта. Конфиг меняется (1 поле), но без нового сервиса/daemon. | 0 изменений сейчас, но оставляет route-totality неполной (SLICE1 STEP3 требует все 19 роутов) и блокирует I03-LIVE witnesses. |
| **Слойность** | Сохраняет «супервизор не знает о сессиях». Контринтуитивно для спеки, где «bound to existing relationship» звучит как факт супервизора. | Размывает слойность минимально: `fa.execution` начинает читать `fa.session` *только* через узкий интерфейс. Компромисс: `fa.session.provisioning.ManagedProvisioner` уже пересекает границу в том же направлении (E263) и собирается в `service.build_supervisor` — attester ложится рядом. | Чисто по слоям, но оставляет спеку недоказуемой. |
| **Тестируемость** | Тест не может отличить «контроллер солгал» от «ребёнок реален» — отрицательный тест отсутствует. | Тест инжектит fake-attester (как `ManagedProvisioner` в `test_execution_provisioning.py`) и доказывает оба исхода. | Тестов нет. |

**Замечание про «второй store»:** фраза из плана «no second policy engine, no second store» направлена против второго journal/lease/scheduler. RO-чтение `sessions/*/manifest.json` и `session-log/<run>/` — не policy engine; оно не принимает решений, не хранит грантов, не конкурирует с `OperationJournal`. `E263` уже ввёл пересечение `session ↔ execution` через `ManagedProvisioner` и это принято.

## 3. Рекомендация

**Выбирать (2) — узкий session-store attester, с (1) как test-only fallback и (3) как текущее честное состояние до посадки.**

Формулировка для `open-questions-2026-10-07.md`:

> **Q85 — RESOLVED (2) narrow attester.** `ServiceConfig` получает опциональный `child_run_attester: ChildRunAttester | None` (или `session_state_root: Path | None`). `WorkspaceAuthority.handoff` требует attester в production; когда `None` (локальные C0/C3 без сессий) — ведёт себя как (1) и тест явно помечает это. Владелец parent-child факта — attester в `ServiceConfig`, реализованный над `SessionManager` (чтение manifest'ов, не запись), сконструированный в `build_supervisor` рядом с `ManagedProvisioner`. SLICE2 STEP2 приносит `WorkspaceAuthority.handoff` + этот attester + handler-ногу `_child_run_context`/parent suspension.

Почему не (1) в проде: при (1) предусловие (2) недоказуемо супервизором и любой uid-равный процесс может увести owner-грант в произвольный namespace, минуя `SessionManager.begin_run`-инварианты (`session_id`/`workspace_path`/`parent_run_id` match, `workspace.py:390ff`). Это именно тот «IDs are not authorization» surface, о котором спека предупреждает в §2.1. Цена (2) — одно поле конфига и RO-чтение — несоизмерима с этим.

Почему не чистый (3): (3) честен сегодня (и остаётся честным до SLICE2 STEP2), но оставляет `handoff` последним незакрытым route'ом (SLICE1 STEP3: все 19 `Operation` роучены) и блокирует I03-LIVE witnesses. Приняв (2) как целевой дизайн, мы можем оставить `BACKEND_UNAVAILABLE` до SLICE2 STEP2 без риска «передумать» позже — (3) становится *фазой*, а не *решением*.

## 4. Конкретный владелец и интерфейс

### 4.1 Где живёт доказательство

* **Источник факта:** `SessionManager` — единственная durability для parent-child (создаёт `sessions/<sid>/manifest.json` + `session-log/<run_id>/`, проверяет `workspace_path` под `workspace_root`, см. `manager.py:_new_session`, `begin_run`, `_child_run_context`).
* **Владелец проверки в супервизоре:** `ServiceConfig` (DI) + `WorkspaceAuthority.handoff` (enforcement). `ServiceConfig` хранит зависимость, `WorkspaceAuthority` — транзицию гранта. `supervisor.Service` — композиция (как для `ManagedProvisioner`).
* **Владелец аллокации на стороне caller'а:** `inner_loop/tools/workflow_tool.py` — `build_invoke_workflow_tool`/`_child_run_context` + будущая parent-suspension логика (SLICE2 STEP2). Он аллоцирует ребёнка, затем зовёт `handoff` — два шага, один `request_id`.

### 4.2 Минимальный интерфейс (не «второй SessionManager»)

```python
# src/fa/execution/handoff_attester.py (новый, ~40 строк, без импорта fa.session в workspace.py)
class ChildRunAttester(Protocol):
    def attest_child(self, parent: NamespaceRef, target: NamespaceRef, *, deadline: float) -> None:
        """Raise SupervisorError(WORKSPACE_BUSY|STALE_*) if parent→target is not a durable child.
           Attester is RO, never mints runs. Deadline = original handoff deadline.
        """
        ...

# Production impl — единственное место, где execution импортирует session:
def build_session_attester(state_root: Path, workspace_root: Path) -> ChildRunAttester: ...

# ServiceConfig
@dataclass(frozen=True)
class ServiceConfig:
    ...
    session_state_root: Path | None = None  # или child_run_attester: ChildRunAttester | None
    # валидация: либо все None, либо абсолютный Path, не внутри state_root/approved_roots, как approved_cache
```

Почему `Path`, а не полный `SessionManager`: супервизору не нужны `workspace_provisioner`, `repo_push_url` и т.п.; достаточно RO-совместимости с `fa_state_root()` резолвом (`paths.py:42` — absolute override или `~/.fa`). Тестам инжектится `lambda p,t: ...` без ФС.

Альтернатива — сразу `ChildRunAttester` callable — чище для тестов, но `Path` проще для оператора (один путь в JSON-конфиге). Рекомендую **callable в `ServiceConfig` + фабрику `build_session_attester(state_root, workspace_root)`** — оператор пишет путь, композиция строит attester, тесты инжектят лямбду. Это зеркалит `ManagedProvisioner(authority, peer, root_id, relative_root)`.

Проверка внутри attester (вне `WorkspaceAuthority`):

1. `_check` deadline, `target.parent_run_id == parent.run_id` иначе `INPUT_POLICY` (нарушена wire-семантика parent-child).
2. `target.session_id == parent.session_id` иначе `INPUT_POLICY` (ребёнок всегда в той же сессии — инвариант `_child_run_context`).
3. `sessions/<sid>/manifest.json` существует, `status==active`, `session_id` совпадает; `session-log/<target.run_id>/` (или запись в `session.db` `runs`) существует и `parent_run_id` совпадает. Любое отсутствие — `WORKSPACE_BUSY` (нет «existing relationship»), не `BACKEND_UNAVAILABLE` (это durable факт, а не daemon).
4. Никаких записей не создаёт, ничего не мутирует, не требует `SessionManager` write-lock.

`WorkspaceAuthority` вызывает attester **после** проверки (1) settled и **до** мутации гранта, внутри той же `_transaction(peer, deadline)`:

```
with _transaction(peer, deadline):
    binding = _owner_only(peer, current_namespace, capability)  # active_actor == current
    if _has_unsettled_views(binding, views_fd): raise WORKSPACE_BUSY  # (1)
    # attester — (2)
    # same-generation + one-grant checks — (3)
    revoke old grant, mint new capability, swap active_actor = target, fsync, reply _OWNER_REPLY
```

### 4.3 Parent writer suspension — что это значит

В плане фразой «parent writer suspension» названа **предпосылка**, а не действие внутри `handoff`:

* Caller обязан довести свои WRITE views до `PUBLISHED`/`REJECTED` (через `seal`→`publish` или `release_unused_writer` для неиспользованного owner) и пройти `stop_view`+cgroup barrier до `handoff`. Иначе `handoff` отказывает `WORKSPACE_BUSY` — та же логика, что `release` (`workspace.py:_has_unsettled_views` + `intent.json` check).
* Сам `handoff` не делает `close_admission`/`drain`/`mark_terminal` — он лишь атомарно меняет `active_actor`/`grant`/`principal`, сохраняя `generation` (в отличие от `acquire_writer`, который инкрементит).

Если позже понадобится «suspend без publish» (родитель с грязными bytes, которые не должны стать ревизией), это отдельный `suspend`/`park` operation, не перегрузка `handoff`. В текущем инкременте suspension = settled.

## 5. Два допвопроса из Q85 — ответы

### 5.1 Ревокация исходного гранта — да, атомарно до выдачи нового

`handoff` — это `release`+`acquire` в одной транзакции с сохранением `generation`. Старый `capability` инвалидируется **до** того, как новый попадает в ответ; иначе два live гранта нарушили бы «exactly one active mutator grant».

Q75 это подтверждает, а не опровергает: Q75 разрешает *replay* уже-DONE `handoff` по оригинальному `request_id`/`input_sha256`/`original_proof` из `CompletedReplyCache`, даже если тот proof уже отозван. Это исключение для чтения кэша (`supervisor.py:240ff`, `_authorize_replay`), а не для свежей работы — `authorize`/`_owner_only` всё равно требуют текущий грант. Поэтому порядок:

1. `journal.reserve` → `EXECUTING` (дедуп по `operation_input_sha256`),
2. внутри `handoff` — `hmac.compare_digest(old_grant)`, `attest_child`, `secrets.token_hex(32)` новый, `binding.grant=new`, `binding.principal=peer.principal`, `binding.metadata.active_actor=target.to_dict()`, fsync,
3. `journal.complete` + `replies.remember_completed(binding, old_proof, GrantReply(HANDOFF,...))`.

Старый proof после этого не проходит `authorize` для свежей команды, но проходит `_authorize_replay` для *того же* `request_id`.

### 5.2 `SEALED`-but-unpublished блокирует `handoff` — да, как `release`

`_SETTLED_VIEW_STATES = {PUBLISHED, REJECTED}` (`workspace.py:620`). `SEALED` туда не входит **намеренно** (E268 D1): отдать writer, пока кандидат не опубликован, значит strand кандидата — его `sealed_manifest_id`/`sealed.json` живут в view, а capability умирает с грантом, и опубликовать будет нечем. `_has_unsettled_views` вернёт `True` на `SEALED`, `handoff` ответит `WORKSPACE_BUSY`.

Это ровно тот же `release_unused_writer` путь: `release` и `handoff` делят settled-логику. Единственный легальный путь — `publish` → `PUBLISHED`, затем `handoff`/`release`. `OPEN`/`STOPPING`/`UNKNOWN` также блокируют; `REJECTED` (ветка `SEALED→REJECTED` из E267 D3) — settled и не блокирует.

## 6. Что это меняет в коде — чеклист SLICE2 STEP2

Без нового сервиса, без нового journal, без нового wire-поля:

- [ ] `src/fa/execution/handoff_attester.py` — `ChildRunAttester` Protocol + `build_session_attester(state_root, workspace_root)` (RO-чтение manifest'ов, `deadline`-bounded, closed коды).
- [ ] `src/fa/execution/service.py:ServiceConfig` — опциональное `session_state_root: Path | None` (валидация как у `approved_cache`: absolute, вне `state_root`/`approved_roots`, ≤107 не применяется — это не socket) или `child_run_attester` callable; `load_config`/`read_config_file` пробрасывают.
- [ ] `src/fa/execution/service.py:SupervisorService.__init__` — строит attester, если путь задан, передаёт в `WorkspaceAuthority`; без attester — `handoff` остаётся `BACKEND_UNAVAILABLE` (honest defer) или в тестах — controller-attested.
- [ ] `src/fa/execution/workspace.py:WorkspaceAuthority` — `handoff(peer, namespace, *, capability, target_namespace, deadline) -> GrantReply` с порядком: `_owner_only` → settled-check (`_has_unsettled_views` + `intent.json`) → attester → generation/one-grant → atomic swap → `_OWNER_REPLY`. Добавить `_has_unsettled_views` переиспользование, не дублировать. Генерация **не** инкрементится.
- [ ] `src/fa/execution/service.py:SupervisorService._handoff` — перестаёт быть `raise BACKEND_UNAVAILABLE`, зовёт `authority.handoff`, проецирует `GrantReply.to_wire_result()`.
- [ ] `src/fa/inner_loop/tools/workflow_tool.py` — handler-нога: `candidate = child_run_id(...)` → `_child_run_context(ctx, candidate)` → `handoff` RPC → на успехе продолжает child `run_workflow`, на ошибке — typed `workflow_context_error`. Родительские views должны быть settled до вызова (документировать как предусловие).
- [ ] Тесты: `tests/test_execution_handoff.py` (C1: settled/unsettled, generation, one-grant, attester positive/negative, revocation + Q75 replay, SEALED-blocks) + `tests/test_workspace_handoff_cases.py`-style unit для attester. 7–9 producer-мутантов с byte-exact restore.

Что **не** делать: новый `Operation`, новое поле `payload`, второй journal, lease-сервис, host-shell fallback, «второй SessionManager внутри execution».

## 7. Связь с текущим планом

* SLICE1 STEP3 (роутинг) уже требует 19 роутов — `handoff` последний; до SLICE2 STEP2 он остаётся `BACKEND_UNAVAILABLE` — это не баг, а `E277`-заявленная dormancy.
* SLICE2 STEP2 в инкременте уже описан как «reused `_child_run_context`/parent writer suspension and server-acknowledged handoff» — рекомендация лишь **называет** missing piece (attester) и его владельца.
* Spec §2.1:167, §4.1 (SessionManager cutover, CT103a) и §7.1 (reuse `_child_run_context`) остаются без изменений — attester следует тем же path-резолвам, что `ManagedProvisioner`.

## 8. Риски и как их закрыть

* **Attester читает ФС контроллера — а если контроллер ещё не сбросил manifest?** `begin_run` в `_child_run_context` делает durable запись до `handoff`; `handoff` с `deadline` подождёт. Если записи нет — `WORKSPACE_BUSY`, caller ретраит после фиксации. Не `DURABILITY_UNKNOWN` (это не authority-own запись).
* **TOCTOU: ребёнок удалён между attest и swap?** SessionManager никогда не удаляет `sessions/*/manifest.json` для active сессии; run'ы append-only. Удаление — `CORRUPT_STATE`/`WORKSPACE_BUSY` и authority quarantines, как в `_load`.
* **Конфиг-дрейф: `FA_STATE_ROOT` override?** Attester резолвит через `fa_state_root()` с env-override (как `session/manager.py`), или берёт путь из `ServiceConfig` — оба абсолютные, второй приоритетнее.

---

### Итог для утверждения

* **Решение:** (2) narrow attester, owner — `ServiceConfig` (DI) + `WorkspaceAuthority.handoff` (enforcement), аллокация — `_child_run_context` (handler).
* **Ревокация:** да, атомарно до нового capability; replay старого — только через `CompletedReplyCache` по тому же `request_id`.
* **SEALED:** да, блокирует `handoff` как `release` (`WORKSPACE_BUSY`), пока не `PUBLISHED`/`REJECTED`.
* **Defer (3):** остаётся текущим честным состоянием до SLICE2 STEP2; (1) — только test-only fallback без attester.

Следующий шаг после утверждения: один PR — этот файл + запись в `ledger.md` + правка `open-questions-2026-10-07.md:2102` в RESOLVED со ссылкой сюда, без изменения `src/` (код — в SLICE2 STEP2).
