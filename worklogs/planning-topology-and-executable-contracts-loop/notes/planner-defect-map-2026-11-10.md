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

### D6 — adaptive не связывает acquisition *(новый, самый тяжёлый)*

> **После чтения документов (см. §0.0):** класс дефекта уточнён. Раунды/repair/replan
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

### D7 — `PlannerDispatchKind.ACQUISITION` не производится *(подтверждён исполнением)*

`grep PlannerDispatchKind.ACQUISITION src/ --include=*.py` → 2 совпадения: валидация
(`planner_dispatch.py:74`) и docstring (`workflow_controller.py:2372`). Ни одного производителя.
`_stage_planner_dispatch` (`:1183`) при `dispatch is None` всегда возвращает `ORDINARY_PLANNING`.

Следствие: спека §7.0 («initial `_run_stage` uses `PlannerDispatchKind.ACQUISITION`») не
выполняется; kind, его инварианты и 12 тестов существуют, но в прогон не попадают.

### D8 — `build_acquisition_registry` без производственного вызова

Определён в `profiles.py:441`, вызывающих в `src/` — ноль. Стадия планировщика ходит
`build_registry_for_role("planner")` с обычным профилем: `fs_write_file`
(allowlist `knowledge/research/`, `.fa/`) + `pr_prepare` регистрируется безусловно
(`cli.py:2637`). Спека требует фильтровать `pr_prepare` для ACQUISITION — «иначе read-only
профиль молча получает writer».

### D9 — модель не знает протокола выбора

`grep SELECT_EXISTING|BOOTSTRAP_NEW_PROJECT|NEEDS_CLARIFICATION` по `src/` и `knowledge/`:
**ноль** совпадений вне `managed_acquisition.py`. `_stage_task` (`:1333`) дополняет задачу
только для eval. `_decode_choice` требует ровно один JSON без обёртки и лишней прозы ⇒
обычный текстовый план планировщика даёт `choice-malformed`. Положительный путь недостижим
независимо от D6–D8. Носитель — **Q149** (не решён ни одним документом).

### D10 — v1-писатель отвергает `dispatch_kind: ACQUISITION`

**Исполнено:** `write_admission_record(..., attempt={dispatch_kind:"ACQUISITION", …})` →
`AdmissionIOError(corrupt-record)`. В `_record_attempt_hashes` (`admission_schema.py:178-195`)
ветки есть для `EXPLICIT_INPUT` и `{ADMISSION_REPAIR, EVAL_REPLAN}`; `ACQUISITION` не попадает
ни в одну, и `route="ADMITTED"` требует `promoted`, которого нет. v2, где
`_validate_v2_acquisition` расписана целиком, **недостижима**: `ManagedAdmissionBinding`
не строится ни в одной производственной ветке, а v2-попытке нужны
`input_revision/output_revision/bundle_sha256`.

Сейчас незаметен только потому, что D7 не даёт kind'у дойти до записи.

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

### D13 — `_scoped_stage_failed` без семантики для нового kind

`:1299` возвращает `False` только для `ORDINARY_PLANNING`; всё остальное считается scoped
repair-стадией и проверяется на `fs_write_file`/`pr_prepare`. Если D7 починить и ничего не
сделать здесь, acquisition-планировщик молча переедет в правила repair-стадии.

### D14 — описание инструмента врёт модели

`INVOKE_WORKFLOW_SCHEMA`/`ToolSpec.description` (`workflow_tool.py:832`): «Coder-containing
requests currently return `acquisition_unavailable`». После Q148=B это неверно для
planner-first. Модель читает описание как политику — устаревший текст влияет на её выбор.

## 2. Сводная таблица

| id | дефект | класс | доказательство | блокирует |
| --- | --- | --- | --- | --- |
| D6 | adaptive не связывает acquisition; coder без плана; отказы не останавливают | **оркестрация** | исполнено | всё в adaptive (по умолчанию!) |
| D7 | ACQUISITION-вид не производится | проводка | исполнено | §7.0, D10/D11/D13 |
| D8 | acquisition-реестр без вызова; writer у планировщика | проводка | grep = 0 | §7.0 read-only |
| D9 | протокол выбора не доходит до модели | **контракт (Q149)** | grep = 0 вне модуля | положительный путь |
| D10 | v1 отвергает ACQUISITION-попытку; v2 недостижима | схема | исполнено | провенанс |
| D11 | попытка пишется как EXPLICIT_INPUT | схема | исполнено | провенанс |
| D12 | отказы → validator-error | схема | код + E516 | диагностика |
| D13 | `_scoped_stage_failed` без семантики | проводка | код | тихая смена правил |
| D14 | описание инструмента устарело | док/контракт | код | поведение модели |

## 3. Порядок закрытия (предложение)

Зависимости, не предпочтения:

```
D6 ─┬─► (без него остальное проверяется только в linear)
    │
D9 ─┴─► D7 ──► D13 ──► D8 ──► D10/D11/D12
      носитель  kind   правила  реестр   провенанс
```

- **D6 первым**, потому что он единственный делает недоказанным всё остальное: пока
  adaptive не связывает admission, «zero coder effect on refusal» верно лишь для режима,
  который никто не запускает по умолчанию. Это же чинит D12-следствие (отказы не тормозят).
- **D9** — единственный, где нужно ваше решение (Q149), и он стоит до D7: kind без носителя
  ничего не меняет.
- **D10–D12** — последними и одним решением: это выбор «прогон пишет v2» против «acquisition
  вообще не пишет попытку», и он определяет схему, а не наоборот.

## 4. Что этот аудит **не** покрывает

- R24 (verify на реальном authority) — Q140 открыт; здесь только подтверждено, что гейт
  в пробах срабатывал (`verify gate mode=observe blocking=True`).
- R26 (вложенный coder) — Q141 открыт; сюда не входит.
- Live-host поведение: Docker недоступен, `BACKEND_UNAVAILABLE` — как и раньше.
- Мутации по D6 не гонялись: сначала нужен тест, который его ловит (сейчас такого нет —
  это и есть причина, почему дефект дожил до аудита).
