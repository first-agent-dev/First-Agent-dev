# Планировщик в system workflow: карта оставшихся дефектов (2026-11-10)

> **Статус закрытия (обновлено 2026-11-10 по `HEAD=014c012`):** все дефекты `D1–D14` этой
> карты **закрыты** коммитами `E520–E524`, а выявленные при сквозном E2E-прогоне разрывы
> № 1–3 (`PIN_READER` для read-only стадий, чтение candidate seed через `WorkspacePort` и
> `REJECTED` settlement на провале) закрыты коммитами `9c4f429` и `014c012`. Содержимое
> ниже сохраняется как исторический аудит, на основании которого выполнялись `E520–E524`.

Аудит по запросу оператора («мне казалось, все дефекты уже закрыты»). Ничего не менялось
в коде. Каждое утверждение ниже либо **исполнено** в восстановленном окружении, либо
привязано к точной строке; спекуляции помечены.

> **Почему дефекты всё ещё есть, коротко.** Пять блоков S5P1 (E515–E519) строились как
> *компоненты + один путь*: банки гоняют `run_workflow` с `mode="linear"`. Adaptive-ветка
> в них не участвовала ни разу — `grep 'mode="adaptive"' tests/test_s5p1_*.py` пуст. Всё,
> что ниже, — это шов между «компонент готов» и «прогон в том режиме, который стоит по
> умолчанию».

## 0.0. Поправка от 2026-11-10 (после чтения документов)

В первой редакции этой карты был вывод «replan не перезапускает planner, то есть это repair
под другим именем». **Это неверно.** Чтение `_admit_plan` показывает обратное:

- `_admit_plan(replan=True)` → `kind = PlannerDispatchKind.EVAL_REPLAN` → резервирует кредит
  (`state.planner_calls += 1`) → вызывает `_run_admission_repair(role="planner")`;
- планировщику передаётся задача-инъекция ровно того вида, что описан в вашем вопросе:
  `"Revise only the owned candidate <path>. Read that candidate; fix structural and
  kill-directive diagnostics. Do not edit the canonical plan."` + `Revision reason` +
  санитизированные диагностики;
- механизм — **scoped candidate**: планировщик правит owned-копию, публикация и финальное
  admission идут отдельно (Q58 same-path, Q67(a) canonical остаётся ADMITTED).

То есть в коде уже есть **оба** ваших варианта, разведённые по видам:
`ADMISSION_REPAIR` — «planner чинит свои диагностики», `EVAL_REPLAN` — «получил замечание
от eval». Оба — новый кандидат, а не prompt-inject без планировщика. Вопрос «должен ли replan
перезапускать planner» закрыт документом **Q67(a), RESOLVED 2026-10-16 (E231)**: да, через
scoped candidate с общим кредитом и durable barrier.

Следствие для D6 остаётся ровно тем же и становится острее: вся эта механика живёт внутри
`_admit_plan`, который начинается с `if state is None: return True`. Пока `ctx.admission`
не связан, **ни replan, ни repair-планировщик, ни кредит не существуют** — не потому что
их нет в коде, а потому что до них не доходит управление.

### Как определялись режимы (документы, от свежих к старым)

| дата | документ | что определяет |
| --- | --- | --- |
| 2026-11-11/12 | `notes/q140…`, `q141…`, `q145…`, `q147…`, `write-seam-decomposition…` | acquisition/швы; **режимы не упоминаются вообще** — режимы считались решёнными |
| 2026-11-02 | `ledger.md` E404 | adaptive-тесты получают managed publisher seam; четыре adaptive-случая закрыты |
| 2026-10-16 | `open-questions…` **Q67 → RESOLVED (a)** | eval-replan: canonical ADMITTED держится, candidate, shared credit, никакого синтетического FAIL |
| 2026-10-16 | `ledger.md` E211 | локальная композиция Q67(a) |
| 2026-10-07+ | `increments/increment-02-…` | **определение режимов**: «Q57 repair is pre-coder in linear **and** adaptive; linear does not gain adaptive eval semantics» |
| 2026-10-07+ | `increments/increment-02-…` STEP12 | «preserve linear semantics and **shared** repair/replan counter», «reject unsafe ordinary-planner ordering» |
| старше | `knowledge/project-overview.md` I-6.3 | «simple chain planner→coder→eval is default» |

**Как определяли:** repair — общий и pre-coder в обоих режимах; различие — только в том,
получает ли linear *adaptive eval semantics*. Раунды и общий счётчик задуманы как **общая**
инфраструктура, а не как свойство adaptive. Это буквально ваша формулировка. Документы
за последние недели режимы не пересматривали — они считались закрытыми, поэтому D6 и не
всплыл.

## 0. Состояние окружения на момент аудита

`.venv` отсутствует, `uv` не было, Python в системе 3.11 (проект требует ≥3.12 из-за
`typing.override`). Восстановлено для анализа: `pytest 9.2.0`, `pyyaml`, `markdown-it-py`,
`fastjsonschema`, `bashlex`, `pytest-asyncio`; Python 3.12 скачать нельзя (сеть закрыта),
поэтому использован шим `typing_extensions` в `/tmp/shim` (вне репозитория).
`PYTHONPATH=/tmp/shim:src python3 -m pytest` — банки запускаются.

Контрольная точка: **60 passed** по семи acquisition-банкам
(`dispatch, registry, seam, resolution, admission, lifecycle, substrate`). То есть
компоненты живы; дефекты — в проводке.

## 1. Дефекты, найденные/подтверждённые этим аудитом

### D6 — adaptive не связывает acquisition *(закрыт в E520)*

> **Статус:** **закрыт (E520).** Реализован единый цикл стадий `_run_role_loop` +
> `_StageLoopResult` в `src/fa/inner_loop/workflow_controller.py`: через него сведены
> `_run_linear`, `_run_adaptive` и `_dispatch_adaptive_round` (а `_run_initial_roles`
> оборачивает его, сохраняя 4-кортеж). Связанный `ctx` пробрасывается через
> `_run_adaptive_repair` и `_run_adaptive_replan`; `_bind_acquisition_admission` и
> `_admit_installed_plan` сбрасывают `acquisition=None`, а `_stage_acquisition_choice`
> отсекает повторный выбор по `ctx.admission is not None` и `dispatch.owns_candidate`,
> чтобы последующие `ADMISSION_REPAIR` (Q57) и `EVAL_REPLAN` (Q67a) не читались как
> второй acquisition-выбор. Покрыто параметризованными тестами (`linear`/`adaptive`) и
> сценариями repair/replan в `tests/test_s5p1_acquisition_lifecycle.py` (77 passed в
> S5P1-банках).
>
> **Исторический разбор на baseline `5193b1c` (до E520):**
> После чтения документов (см. §0.0) класс дефекта уточнён. Раунды/repair/replan
> задуманы как **общая** инфраструктура (`increment-02`: «Q57 repair is pre-coder in linear
> **and** adaptive», «shared repair/replan counter»). Поэтому D6 — не «adaptive забыл про
> acquisition», а **расхождение реализации с этим решением**: общая часть собрана, но
> точка связывания admission осталась в одной из трёх копий цикла.

**Исполнено.** Один и тот же сценарий (`SELECT_EXISTING`), меняется только `mode`:

| mode | exit | роли | `_managed_plan_ref` у coder | admission-запись |
| --- | --- | --- | --- | --- |
| linear | 1 (verify gate) | planner,coder,eval | `PlanRef(…EXISTING_SELECTION…)` | **есть**, v1, ADMITTED, 1 попытка |
| adaptive | 1 (verify gate) | planner,coder,eval | **`None`** | **НЕТ ЗАПИСИ ВООБЩЕ** |

**Механизм (три строки, каждая проверена).**

1. `result.acquisition` читает **только** `_run_linear` (`workflow_controller.py:2655`).
   `_run_initial_roles:1988`, `_dispatch_adaptive_round:2051`, `_run_adaptive:2218` — не читают.
   Проверено `inspect.getsource`: `False`, `False`, `False`.
2. `ctx.admission` создаётся в одном месте (`_run_workflow_bound`) под условием
   `snapshot is not None and "coder" in roles`. У acquisition-прогона `snapshot is None`
   (план появляется позже) ⇒ **`ctx.admission = None` на весь прогон**, в обоих режимах.
3. `_admit_plan` начинается с `state = ctx.admission; if state is None: return True`
   с комментарием «Internal legacy stage fixtures; public coder entry always binds authority».
   Для acquisition-прогона это **не** внутренняя фикстура — это штатный путь, и гейт
   пропускает coder без плана.

**Следствия.**

- coder в adaptive получает `plan_ref=None` — границы записи нет вовсе;
- admission-истории нет: ни ACQUIRING-барьера, ни попытки, ни провенанса;
- отказы acquisition (уточнение, мусор, bootstrap) в adaptive **не останавливают прогон**:
  исполнено — `NEEDS_CLARIFICATION` в adaptive дал `planner,coder,eval`, в linear — только
  `planner`, exit 2;
- бюджет планировщика (`planner_allowed/calls/limit`) живёт в `_WorkflowAdmission`, то есть
  при `ctx.admission is None` **не существует** ⇒ ограничение повторов планировщика не действует.

**Почему это не поймали.** Все 7 банков `test_s5p1_acquisition_lifecycle.py` — linear.
Инвариант «zero coder/provider effect on refusal» доказан на ветке, которую вызывает
`fa workflow --mode linear`, а не та, что стоит по умолчанию.

**Класс.** Не «забыли строку», а **дублирование оркестрации**: два цикла стадий
(`_run_linear` и `_run_initial_roles`+adaptive), и связывание admission реализовано в одном.
Ровно тот риск, от которого предостерегает «one workflow machine, no second engine».

### D7 — `PlannerDispatchKind.ACQUISITION` не производится *(закрыт в E521)*

> **Статус:** **закрыт (E521).** `_stage_planner_dispatch`
> (`src/fa/inner_loop/workflow_controller.py`) при `role == "planner"`, `dispatch is None`,
> `ctx.acquisition is not None`, `ctx.admission is None` и `active is None` теперь
> производит `PlannerDispatch(PlannerDispatchKind.ACQUISITION, ctx.run_id)`. Обычный
> явный план, пост-admission этапы и `ADMISSION_REPAIR`/`EVAL_REPLAN` сохраняют прежние
> виды.

### D8 — `build_acquisition_registry` без производственного вызова *(закрыт в E521)*

> **Статус:** **закрыт (E521).**
> - `build_planner_registry` (`src/fa/inner_loop/tools/__init__.py`) при
>   `PlannerDispatchKind.ACQUISITION` делегирует напрямую в `build_acquisition_registry`
>   (отвергая ненулевой `candidate_io` через `PlannerDispatchError` и не добавляя
>   `fs_chronicle_search`/`fs_usage`/`fs_run_bash`);
> - `build_registry_for_role` (`src/fa/inner_loop/profiles.py`) отвергает `ACQUISITION`
>   через `PlannerDispatchError`, закрывая профильный обход;
> - `cli._build_run_tool_registry` (`src/fa/cli.py`) не регистрирует `pr_prepare`, а
>   `cli._register_managed_subagent_tool` не регистрирует `fs_spawn_subagent` для
>   `ACQUISITION`. До провайдера в `_cmd_run` доходят строго 5 инструментов
>   `ACQUISITION_TOOLS`.

### D9 — модель не знает протокола выбора *(закрыт в E522)*

> **Статус:** **закрыт (E522, по Q149=B + Q145 + Q151=A).**
> - `src/fa/inner_loop/prompt.py`: введён статический `ACQUISITION_SYSTEM_PROMPT`
>   (read-only инструменты из `ACQUISITION_TOOLS`, строгий однообъектный JSON-протокол
>   `SELECT_EXISTING` / `BOOTSTRAP_NEW_PROJECT` / `NEEDS_CLARIFICATION`, требования
>   `render_bundle` + `_validate_plan_admission` включая `## Intent` / `## Out of scope`
>   и `kill:` на `FUNCTIONAL` контрактах, запрет на `BOOTSTRAP_NEW_PROJECT` по
>   существующим/`incomplete`/пустым каталогам из-за `COLLISION`) и
>   `resolve_base_system_prompt(role, planner_dispatch=...)`.
> - `src/fa/inner_loop/coder_loop.py`, `src/fa/cli.py`: `planner_dispatch` проброшен
>   в `drive_session` / `resolve_base_system_prompt` без изменения `cache_key` от
>   динамических полей (`Q66` отложен, как решено).
> - `src/fa/inner_loop/workflow_controller.py`: `AcquisitionSubstrate.incomplete_names`
>   захватывается в `_pinned_acquisition_substrate` вместе с `project_names`;
>   `_stage_task` через `_acquisition_stage_task` добавляет `Projects` и `Incomplete`
>   строго на стадии `ACQUISITION`.
> - `src/fa/inner_loop/tools/workflow_tool.py`: `build_handoff_task(..., acquisition=True)`
>   исключает `"3) Produce the plan"` для managed-coder handoff; `_workflow_outcome_summary`
>   выносит `blocked_reason` и подсказку по `worklogs/<slug>/roadmap.md` в `summary`,
>   сохраняя точный набор ключей CT4 `result`.

### D10 — v1-писатель отвергает `dispatch_kind: ACQUISITION` *(закрыт в E524, Q150=A)*

> **Статус:** **закрыт (E524).** Реализован перехватчик `ManagedAdmissionBinding`
> (`_managed_admission_binding` в `src/fa/inner_loop/workflow_controller.py`), строго
> активирующий `schema_version = 2` только для managed-child запусков с полным
> `ManagedExecution` (`owner_run_id != run_id`, `ws-<32hex>`, `generation >= 1`,
> `rev-<32hex>`), оставляя top-level запуски (`owner_run_id == run_id`) и unmanaged/mock
> вызовы на `schema_version = 1`.
> - `ExecutionClient.publish_plan` и `reconcile_candidate_publication`
>   (`src/fa/execution/client.py`) возвращают реальный `PlanPublication.operation_id`;
>   `BoundPlanPublisher.publish_candidate_receipt` (`src/fa/execution/composition.py`)
>   передаёт полный `PlanPublication` с ревизией и `operation_id`;
>   `PlanPromotionError` (`src/fa/inner_loop/plan_promotion.py`) сохраняет `operation_id`
>   при неопределённой публикации (`durability-unknown`, `output_revision = None`).
> - `_initialize_admission_record` пишет стартовый барьер `status = "ACQUIRING"`,
>   `plan_ref = None`, `attempts = []` до выбора; `_admit_bootstrap_attempt` и
>   `_install_bootstrap_project_with_detail` пробрасывают `bundle_sha256`,
>   `candidate_sha256`, `input_revision`/`output_revision` и `operation_id`.

### D11 — провенанс стирается: попытка пишется как `EXPLICIT_INPUT` *(закрыт в E524, Q150=A)*

> **Статус:** **закрыт (E524).**
> - На управляемых дочерних запусках v2 (`ctx.admission_binding is not None`) первый
>   допуск и `RETRY`/`BLOCKED` после acquisition пишутся с `dispatch_kind = "ACQUISITION"`
>   (при `max_repairs = 0` на FAIL-диагностиках `EXISTING_SELECTION` эмиттится цепочка
>   `#1 ACQUISITION/RETRY` → `#2 ADMISSION_REPAIR/BLOCKED`), а `EVAL_REPLAN` при
>   исчерпании бюджета пишет `dispatch_kind = "EVAL_REPLAN"`, `route = "BLOCKED"`.
> - `_v2_attempt_diagnostics` отфильтровывает не-`FAIL` предупреждения в pre-coder
>   `EXISTING_SELECTION RETRY`, а `_canonical_parts` (`src/fa/inner_loop/plan_promotion.py`)
>   разрешает `ADMISSION_REPAIR`/`EVAL_REPLAN` для приобретённых путей
>   `worklogs/<slug>/increments/<name>.md` (отклоняя `.md`/`.hidden.md`), сохраняя
>   строгий `_CANONICAL_PARENT` для `EXPLICIT` (CT94).

### D12 — отказы acquisition теряют точную причину *(закрыт в E524, Q150=A)*

> **Статус:** **закрыт (E524).** `_stage_acquisition_choice`, `_pinned_acquisition_substrate`,
> `_bind_acquisition_admission`, `_refusal_exit_code`, `_classify_bootstrap_exception` и
> `_blocked_plan_request` (`_v2_blocked_diagnostic`) проецируют отказы выбора, уточнения,
> пина, `prepare_bundle` и `install_project` в закрытый v2-словарь `ADMISSION_RULES_V2`
> (`selection/*`, `bootstrap/*`, `workspace/*`) с сохранением `bundle_sha256`/
> `candidate_sha256` и `operation_id` на post-prepare/uncertain отказах.

### D13 — `_scoped_stage_failed` без семантики для нового kind *(закрыт в E521)*

> **Статус:** **закрыт (E521).** `_scoped_stage_failed`
> (`src/fa/inner_loop/workflow_controller.py`) теперь проверяет
> `if dispatch is None or not dispatch.owns_candidate: return False`, поэтому
> `ACQUISITION` не перехватывается правилами scoped repair-стадии, при `exit_code == 0`
> и пустом `sink` доходит до `_stage_acquisition_choice` (`choice-missing`), а при
> ненулевом коде возвращает реальный `exit_code` стадии.

### D14 — описание инструмента врёт модели *(закрыт в E523)*

> **Статус:** **закрыт (E523).** `ToolSpec(name="invoke_workflow").description` в
> `src/fa/inner_loop/tools/workflow_tool.py` обновлён под актуальную политику
> `acquisition_refusal`: managed-сессии с ведущим `planner` автоматически проходят
> acquisition для `planner,coder,eval`, вызовы с `coder` без ведущего `planner`
> получают `acquisition_requires_planner`, а unmanaged-вызовы с `coder` возвращают
> `acquisition_unavailable`. Покрыт C1-тестом и kill-check'ом в
> `tests/test_invoke_workflow_tool.py`.

## 2. Сводная таблица

| id | дефект | класс | доказательство | статус / блокирует |
| --- | --- | --- | --- | --- |
| D6 | adaptive не связывает acquisition; coder без плана; отказы не останавливают | **оркестрация** | исполнено + kill-проверка | **ЗАКРЫТ (E520)** |
| D7 | ACQUISITION-вид не производится | проводка | C1 + мутация M1 | **ЗАКРЫТ (E521)** |
| D8 | acquisition-реестр без вызова; writer у планировщика | проводка | C1 `_cmd_run` + M3–M5 | **ЗАКРЫТ (E521)** |
| D9 | протокол выбора не доходит до модели | **контракт (Q149=B, Q145, Q151=A)** | C1 `_cmd_run` + M1–M6 (7/7) | **ЗАКРЫТ (E522)** |
| D10 | v1 отвергает ACQUISITION-попытку; v2 недостижима | схема (**Q150=A**) | C1 `SupervisorService` + `validate_admission_record` + M1–M2, M5 | **ЗАКРЫТ (E524)** |
| D11 | попытка пишется как EXPLICIT_INPUT | схема (**Q150=A**) | C1 `EVAL_REPLAN`/`REPAIR` + M3–M4, M6, M8 | **ЗАКРЫТ (E524)** |
| D12 | отказы → validator-error | схема (**Q150=A**) | C1 отказы + `pin_reader` + M7, M9 | **ЗАКРЫТ (E524)** |
| D13 | `_scoped_stage_failed` без семантики | проводка | C1 + мутация M2 | **ЗАКРЫТ (E521)** |
| D14 | описание инструмента устарело | док/контракт | C1 + kill-check | **ЗАКРЫТ (E523)** |

## 3. Порядок закрытия (актуализирован по зависимостям)

```
[D6 (E520)] ─► [D13 → D8 → D7 (E521)] ─► [D9 (E522)] ─► [D14 (E523)] ─► [D10–D12 (E524, Q150=A)]
```

- Все дефекты **D6–D14** закрыты: контроллер (`linear` + `adaptive`), `ACQUISITION`-реестр,
  статический/динамический промпт, описание `invoke_workflow` и `schema_version = 2`
  провенанс на managed-child пути (`owner_run_id != run_id`) полностью согласованы при
  сохранении `schema_version = 1` для unmanaged/top-level вызовов.

## 4. Что этот аудит **не** покрывает

- R24 (verify на реальном authority) — Q140 открыт; здесь только подтверждено, что гейт
  в пробах срабатывал (`verify gate mode=observe blocking=True`).
- R26 (вложенный coder) — Q141 открыт; сюда не входит.
- Live-host поведение: Docker недоступен, `BACKEND_UNAVAILABLE` — как и раньше.
- Мутации: D6 (5/5 неэквивалентных мутантов убиты, E520); D13+D8+D7 (6/6 неэквивалентных
  мутантов M1–M5 убиты, E521); D9 (7/7 неэквивалентных мутантов M1–M6 убиты на банках
  `prompt_registry_coherence` / `handoff_payload` / `invoke_workflow_tool` /
  `s5p1_acquisition_{substrate,lifecycle}`, E522); D14 (1/1 мутант описания инструмента
  убит на `test_invoke_workflow_tool.py`, E523); D10–D12 (9/9 целевых мутантов M1–M9 убиты
  на `test_admission_v2_provenance.py` + `test_execution_composition.py`, E524).
