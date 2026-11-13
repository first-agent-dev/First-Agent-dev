# Планировщик в system workflow: карта оставшихся дефектов (2026-11-10)

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

### D9 — модель не знает протокола выбора

`grep SELECT_EXISTING|BOOTSTRAP_NEW_PROJECT|NEEDS_CLARIFICATION` по `src/` и `knowledge/`:
**ноль** совпадений вне `managed_acquisition.py`. `_stage_task` (`:1333`) дополняет задачу
только для eval. `_decode_choice` требует ровно один JSON без обёртки и лишней прозы ⇒
обычный текстовый план планировщика даёт `choice-malformed`. Положительный путь недостижим
независимо от D6–D8. Носитель — **Q149** (согласован вариант **B**: статический
`ACQUISITION_SYSTEM_PROMPT` + динамика и Q145 `project_names` в `_stage_task`; перед
финализацией текста промпта ждём подтверждения по `incomplete` / Q151).

### D10 — v1-писатель отвергает `dispatch_kind: ACQUISITION`

**Исполнено:** `write_admission_record(..., attempt={dispatch_kind:"ACQUISITION", …})` →
`AdmissionIOError(corrupt-record)`. В `_record_attempt_hashes` (`admission_schema.py:178-195`)
ветки есть для `EXPLICIT_INPUT` и `{ADMISSION_REPAIR, EVAL_REPLAN}`; `ACQUISITION` не попадает
ни в одну, и `route="ADMITTED"` требует `promoted`, которого нет. v2, где
`_validate_v2_acquisition` расписана целиком, **недостижима**: `ManagedAdmissionBinding`
не строится ни в одной производственной ветке, а v2-попытке нужны
`input_revision/output_revision/bundle_sha256` (согласовано в **Q150 = A**: v2 для
managed-child при `owner_run_id != run_id`, v1 для unmanaged).

Сейчас незаметен только потому, что до D10–D12 контроллер ещё не переключён на v2.

### D11 — провенанс стирается: попытка пишется как `EXPLICIT_INPUT`

`_admit_plan:3122`: `kind=kind.value if candidate else "EXPLICIT_INPUT"`. Для плана из
acquisition `candidate=False` ⇒ история говорит «план подан извне», хотя его выбрал
планировщик. Расхождение со спекой («Initial managed choice uses ACQUISITION») и потеря
различимости, на которую ссылается вся аргументация admission. **Исполнено:** в linear-пробе
`plan_ref.source_kind == EXISTING_SELECTION`, но `dispatch_kind` попытки — `EXPLICIT_INPUT`.

### D12 — отказы acquisition теряют точную причину

`_PERSISTED_PLAN_REF_RULES` — словарь v1 `plan-ref`. Всё вне него (`clarification/*`,
`bootstrap-*`) пишется как `validator-error`; точная причина остаётся лишь в свободном
`blocked_reason`. Уже ловили для refusals в E516; для acquisition спека требует
v2-словарь `selection/*`.

### D13 — `_scoped_stage_failed` без семантики для нового kind *(закрыт в E521)*

> **Статус:** **закрыт (E521).** `_scoped_stage_failed`
> (`src/fa/inner_loop/workflow_controller.py`) теперь проверяет
> `if dispatch is None or not dispatch.owns_candidate: return False`, поэтому
> `ACQUISITION` не перехватывается правилами scoped repair-стадии, при `exit_code == 0`
> и пустом `sink` доходит до `_stage_acquisition_choice` (`choice-missing`), а при
> ненулевом коде возвращает реальный `exit_code` стадии.

### D14 — описание инструмента врёт модели

`INVOKE_WORKFLOW_SCHEMA`/`ToolSpec.description` (`workflow_tool.py:832`): «Coder-containing
requests currently return `acquisition_unavailable`». После Q148=B это неверно для
planner-first. Модель читает описание как политику — устаревший текст влияет на её выбор.

## 2. Сводная таблица

| id | дефект | класс | доказательство | статус / блокирует |
| --- | --- | --- | --- | --- |
| D6 | adaptive не связывает acquisition; coder без плана; отказы не останавливают | **оркестрация** | исполнено + kill-проверка | **ЗАКРЫТ (E520)** |
| D7 | ACQUISITION-вид не производится | проводка | C1 + мутация M1 | **ЗАКРЫТ (E521)** |
| D8 | acquisition-реестр без вызова; writer у планировщика | проводка | C1 `_cmd_run` + M3–M5 | **ЗАКРЫТ (E521)** |
| D9 | протокол выбора не доходит до модели | **контракт (Q149=B, Q145)** | grep = 0 вне модуля | открыт (следующий; ждёт `incomplete`/Q151) |
| D10 | v1 отвергает ACQUISITION-попытку; v2 недостижима | схема (**Q150=A**) | исполнено | открыт; провенанс |
| D11 | попытка пишется как EXPLICIT_INPUT | схема (**Q150=A**) | исполнено | открыт; провенанс |
| D12 | отказы → validator-error | схема (**Q150=A**) | код + E516 | открыт; диагностика |
| D13 | `_scoped_stage_failed` без семантики | проводка | C1 + мутация M2 | **ЗАКРЫТ (E521)** |
| D14 | описание инструмента устарело | док/контракт | код | открыт (после D9) |

## 3. Порядок закрытия (актуализирован по зависимостям)

```
[D6 (E520)] ─► [D13 → D8 → D7 (E521)] ─► D9 (Q149=B, Q145; ждёт Q151 по incomplete) ─► D14 ─► D10–D12 (Q150=A)
```

- **D6 (E520) и D13 → D8 → D7 (E521) закрыты:** контроллер в обоих режимах производит
  `PlannerDispatchKind.ACQUISITION`, отгружает модели только 5 read-only инструментов из
  `ACQUISITION_TOOLS` (без `fs_write_file`, `pr_prepare`, `fs_spawn_subagent`), и не
  срабатывает как scoped repair-стадия.
- **D9** — следующий шаг по утверждённым решениям (**Q149=B** `ACQUISITION_SYSTEM_PROMPT`
  + `_stage_task`; **Q145** `project_names`, `Q66` отложен); перед реализацией текста
  промпта поднято уточнение **Q151** по `incomplete`/пустым директориям, т.к.
  `workspace.py:3468` при `INSTALL_PROJECT` ставит no-clobber `COLLISION`, а `ACQUISITION`
  является read-only.
- **D14** — обновляется сразу после D9, когда положительный вызов `invoke_workflow`
  полностью работоспособен.
- **D10–D12 (Q150=A)** — финальный срез: включение v2 `admission.json` на managed-child
  пути (`owner_run_id != run_id`) с пробросом `ManagedAdmissionBinding`, `BundlePreparation`
  и `InstallReceipt` / `BoundPlanPublisher` (`operation_id`, `revision_id`), сохраняя v1
  для unmanaged вызовов без `ManagedExecution`.

## 4. Что этот аудит **не** покрывает

- R24 (verify на реальном authority) — Q140 открыт; здесь только подтверждено, что гейт
  в пробах срабатывал (`verify gate mode=observe blocking=True`).
- R26 (вложенный coder) — Q141 открыт; сюда не входит.
- Live-host поведение: Docker недоступен, `BACKEND_UNAVAILABLE` — как и раньше.
- Мутации: D6 (5/5 неэквивалентных мутантов убиты, E520); D13+D8+D7 (6/6 неэквивалентных
  мутантов M1–M5 убиты на `tests/test_s5p1_acquisition_{registry,lifecycle}.py`, E521).
