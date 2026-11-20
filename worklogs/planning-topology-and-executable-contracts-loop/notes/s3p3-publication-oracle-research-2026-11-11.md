# S3P3: что именно осталось от «controller leg onto publication», и почему это R25

**Дата:** 2026-11-11. Состояние: HEAD `43c77aa`. Только исследование — ничего не изменено.

## 1. Что требует increment

`S3P3 | PARTIAL | bundle renderer + RENAME_NOREPLACE install (E271), plan replacement core (E273) | controller leg onto publish_candidate_plan with the host writer deleted in the same change | SLICE7`

То есть S3P3 сам по себе — «проводной край контроллера + удаление host writer в том же
изменении». Ниже — что из этого уже есть и что от него осталось.

## 2. Четыре звена существуют и проверены

| звено | где | чем доказано |
| --- | --- | --- |
| `_cmd_workflow` строит publisher из реального managed | `cli.py:2070` | `BoundPlanPublisher(managed, managed.binding)` |
| контроллер требует порт и отказывает без него | `workflow_controller.py:2296` (`_require_managed_publisher`, `managed-execution-absent`) | `test_ct94_missing_publisher_fails_closed_without_canonical_write` |
| публикация идёт сагой view→write→stop→publish→release | `client.py:479-591`, `composition.py:215` (`publish_plan`) | `tests/test_execution_client.py`: 8 тестов, включая uncertain/repeat |
| `BoundPlanPublisher` поверх **живого** supervisor | `composition.py:358` | `tests/test_execution_composition.py:330-353`, `_managed_publisher` (:363) |

Последняя строка важна: E507/E505 говорили «existing root tests stub `run_workflow`;
success also fakes publication». Это **уже не так** для звена publisher — реальная
публикация через живой `SupervisorService` доказана. Но доказана **на уровне
`BoundPlanPublisher`**, а не контроллера.

## 3. Что осталось: ровно одно звено

Не найдено: **успешная публикация, пройденная самим `run_workflow`**.

* `_run_admission_repair` (`workflow_controller.py:2433`) — единственный путь, который
  публикует, и он требует вердикт `DIAGNOSTICS` с правом на повтор
  (`state.planner_allowed`, `planner_calls < planner_limit`), затем реальную
  planner-стадию через `run_stage_fn`, затем PASS-валидацию.
* `_run_admission_repair` не имеет ни одного теста, который проходил бы её целиком:
  успех публикации проверяется либо с `RecordingPublisher` (`dummy`),
  либо `publish_candidate_plan` monkeypatch-ится (`test_execution_composition.py:654,1026`).
* `_require_managed_publisher` проверяется только на отказ.

## 4. Почему это не «S3P3-работа», а R25

E505 писал про S3P3: «W1 therefore adds a real local-authority C1 success/refusal test,
not duplicate controller code; **it does not close R25/W2**». Разделение такое:

* **S3P3 (W1), узко:** край контроллера присутствует и успешная публикация проходит
  через него. Oracle — «валидация PASS + publisher = BoundPlanPublisher над живым
  authority ⇒ байты закоммичены, `PlanRef` совпал, host writer не участвовал».
* **R25 (W2), отдельно:** Q114 — settlement/reclaim после **неопределённого**
  `CANDIDATE` PUBLISH. Q114 раздел «Impact»: неопределённые публикации могут оставить
  приватные view-записи/буферы после освобождения владельца; «authority has no
  caller-held view proof to publish or explicitly release that record». Это lifecycle,
  не wire-формат, и это W2.

Поэтому в этом срезе берём первую половину, вторую выносим явно.

## 5. Ключевое препятствие: успех = «DIAGNOSTICS с правом на повтор»

`route` в `run_workflow` выбирается как: `DIAGNOSTICS` + `can_retry` ⇒ `RETRY` ⇒
`_require_managed_publisher` ⇒ reserve ⇒ `_run_admission_repair`. Значит для успешной
публикации нужно:

1. первый проход дал **DIAGNOSTICS** (не PASS и не structural-BLOCK);
2. `planner_allowed` и есть бюджет (`planner_calls < planner_limit`);
3. planner-стадия через `run_stage_fn` отдаёт правленый план, проходящий валидацию.

## 6. Варианты реализации оракула

### (a) Реальный `run_workflow` + скриптовый planner-провайдер

`run_stage_fn = cli._cmd_run` с `_ScriptedTransport`, который пишет исправленный план в
managed view через `fs_write_file`. Затем `BoundPlanPublisher` над живым supervisor.

* **Плюс:** единственный вариант, который проходит **все** звенья: резерв попытки,
  реальная стадия, `read_plan_snapshot`, валидация, публикация, `state.snapshot`.
* **Минус:** самый тяжёлый; нужен рабочий `_cmd_run` в managed-режиме, а он в арене
  упирается в `managed_execution_unavailable` **на уровне сессии** — то есть тест
  рискует упасть по среде, как 40 других.
* **Риск:** если правка плана требует ещё и сессии/провайдера, оракул станет красным
  по причине, не относящейся к публикации.

### (b) `run_workflow` с подменённым `run_stage_fn` (скрипт вместо CLI)

Тот же путь контроллера, но стадия — детерминированная функция, пишущая кандидат.

* **Плюс:** проходит `_run_admission_repair` целиком, публикация настоящая через живой
  authority; среда сессии не нужна.
* **Минус:** `run_stage_fn` — точка подмены, то есть звено «CLI→стадия» не покрыто.
  Но оно и не входит в S3P3: S3P3 — про публикацию, не про запуск стадии.

### (c) Оракул на `_run_admission_repair` напрямую

Без `run_workflow`, только внутренняя функция + живой publisher.

* **Плюс:** минимальный и точный: ровно тот код, который публикует.
* **Минус:** начинает с середины — не доказывает, что `run_workflow` выбрал `RETRY`
  и вызвал её.

### (d) Оставить `RecordingPublisher`, добавить kill-check на реальный

Не даёт нового покрытия; отклонено.

## 7. Предпочтение и почему

**(b) + узкий (c) как два теста, плюс refusal-пара.**

* (b) доказывает главное для S3P3: `run_workflow` → `_require_managed_publisher` →
  `_run_admission_repair` → `BoundPlanPublisher` → **живой** authority → байты
  закоммичены, `state.snapshot.ref.sha256` равен опубликованному, канонический host
  путь не тронут контроллером.
* (c) даёт точечный kill-check на самое хрупкое место — что публикуются именно
  `validated.snapshot`, а не исходный draft, и что `PlanRef` строится из
  `source.ref`, а не из кандидата.
* Refusal-пара: нет publisher ⇒ `managed-execution-absent` и **ни одной** записи в
  authority (уже есть; переиспользуем как контроль, что успех не «зелёный по ошибке»).

Почему не (a): риск получить красный тест по средовой причине и потом спорить, что он
доказывает. Плюс (a) тянет за собой watchdog сессии, которого у S3P3 нет.

## 8. Что НЕ входит в этот срез (явно)

* Q114 settlement/reclaim после неопределённой публикации — R25/W2.
* Удаление host writer (`host_bootstrap`/`workspace.py`) — это отдельная часть
  формулировки S3P3, зависит от полного cutover и трогает деплой.
* `_run_admission_repair` при живом провайдере — W4.

## 9. Adversarial review этого плана (2026-11-11) — три из четырёх доводов были неверны или неполны

Проверено по коду и двумя пробами, а не по памяти. Окружение в процессе
откатилось (третий раз), поэтому опубликованные выводы §3–§7 перепроверены на
восстановленном дереве `07e1080`.

### 9.1. Ошибка, которую нашли (Crit): вариант (b) не мог пройти на managed

**Проба.** `build_registry_for_role("planner", …, workspace_io=<fake port>,
planner_dispatch=ADMISSION_REPAIR)` → `spec.handler({"path":
".fa/admission/run-1/candidate-abc.md"})`. Результат: `error: None`,
**порт получил 0 вызовов**, и файл реально появился на хосте:
`.fa/admission/run-1/candidate-abc.md` (7 байт).

**Причина.** `_builder_for_role` (`profiles.py:427-435`) выбирает
`fs_write_file_limited` в managed-режиме, а `build_scoped_write_file_tool`
(`write_file.py:188-211`) пишет **прямо по хосту**: `path = root / target` и
`_private_artifact_directory` + `_replace_private_bytes`. `workspace_io` он не
принимает вообще.

**Следствие.** Managed planner физически не может записать кандидата в
приватный буфер `CANDIDATE`-view. Значит `_run_admission_repair` в managed-прогоне
не может получить правленый план **ни при каком** провайдере. §7 предлагал
вариант (b) как основной и вариант (a) как «тяжёлый, но возможный» — оба неверны:
(b) не может работать, (a) невозможен по той же причине.

**Это дефект продукта, а не тесты.** И он ровно того класса, что R28: host-write
внутри managed-маршрута. Плюс второй: `_write_with_guard` в managed с
`workspace_io=None` (scoped writer) пишет на хост без heartbeat-гейта
session-режима, то есть на хосте остаётся файл в `.fa/`, невидимый git.

### 9.2. Что план утверждал верно (проверено)

* `_run_admission_repair` — единственный путь публикации. Подтверждено чтением
  `run_workflow` (`workflow_controller.py:2490`, `:2580-2600`).
* Успех требует `DIAGNOSTICS` + права на повтор + PASS-ревалидации. Подтверждено.
* Публикация через `BoundPlanPublisher` живая (не мок). Подтверждено.
* `_require_managed_publisher` покрыт только отказом. Подтверждено.

### 9.3. Ошибка в §8 «что не входит»

§8 вынес «удаление host writer» из среза как «трогает деплой». Это неверно по
сути: `build_scoped_write_file_tool` — host writer **внутри managed-маршрута**, а
не деплой-скрипт. Аргумент §3 («четыре из пяти звеньев есть») при этом не
доказывает, что цепь managed-записи цела: буфер кандидата в ней отсутствует.
Заголовок S3P3 «with the host writer deleted in the same change» описывает именно
эту поломку, и вынести её в §8 — значит закрыть S3P3 по букве, оставив дефект.

### 9.4. Риск, который план недооценил

Публикация плана в managed не проверяется соседями так, как правки кода: plan-путь
валидируется структурно и по хешу, а не authority-ревизией. Поэтому оракул должен
доказывать **до/после**: до публикации `current_revision_id` — ревизия writer-гранта,
после — новая ревизия и `plan_ref.sha256` из `validated.snapshot`. Иначе тест
сможет пройти на host-write, который мы как раз и нашли. Это ровно то, что M3
(d) проверит.

### 9.5. Пересмотренный план

1. **Сначала дефект, не тест.** Срезать host-write кандидата в managed: scoped
   writer получает `workspace_io` и пишет через `port.write_file(candidate_target,
   …)`; host-ветка остаётся только для `workspace_io is None`. Плюс отказ, если в
   managed маршруте планировщику дали scoped writer без порта.
2. **Проверка на реальном supervisor.** В `CANDIDATE`-view писать может только
   scoped buffer-метод; view с `purpose=PROJECT` в `.fa` не пройдёт
   `_BLOCKED_COMPONENTS` (`view_io.py:28`), поэтому вырезание host-write
   проверяется отказом, а не только успехом.
3. **Оракул (b) после п.1** — теперь он достижим: `run_workflow` со скриптовым
   `run_stage_fn`, кандидат через порт, публикация через живой authority,
   до/после-ревизия из §9.4, канонический хост `.fa/admission/**` не создан.
4. **Отдельно записать как находку** (не в этом срезе): `_run_admission_repair`
   не имеет managed-эквивалента записи кандидата, поэтому managed-режим сегодня
   может **только отказать** в исправлении плана — «repair» в managed не работает.
   Это меняет W1/W2 границу: возможно, это R25, а не S3P3.

## 10. Проверка на живом supervisor (2026-11-11): три слоя, все три ломают managed-repair

Пробы на реальном `SupervisorService` + `WorkspaceAuthority`, не на моках.
Окружение: восстановленное дерево `a410caf`, CPython 3.13.16.

### Слой 1 — planner пишет кандидата на хост (подтверждено §9.1)

`build_registry_for_role("planner", workspace_io=<port>, planner_dispatch=ADMISSION_REPAIR)`
→ `fs_write_file` → файл появился на хосте, порт получил **0** вызовов.
`_builder_for_role` выбирает `fs_write_file_limited`, а он `workspace_io` не принимает.

### Слой 2 — `client.open_view` не умеет открыть CANDIDATE вообще

`client.open_view(access=READ, purpose=CANDIDATE, plan_ref=…)` всегда шлёт
`candidate_scope: None`. Но codec (`protocol.py:511-515`) требует
`(candidate_scope is not None) == (purpose == CANDIDATE)`, поэтому такой запрос
**невозможен на проводе**: `InvalidRequestError`. То есть у client API нет способа
открыть CANDIDATE-view, хотя authority его поддерживает (`write_candidate`).

**Рабочий путь (проверен):** ручной `CREATE_VIEW` с
`candidate_scope={"plan_ref": pr}` + `protocol_version=1` →
`1) CREATE_VIEW(candidate+scope): OK`.

### Слой 3 — `ClientWorkspacePort` отказывает писать в CANDIDATE-view

```
2) запись FAILED: WorkspacePortError denied
3) канонический план на хосте: b'# Existing plan\n'   ← не изменён, это хорошо
4) .fa/admission создан: False                          ← и это хорошо
```

Причина (`tool_port.py:161`): `ClientWorkspacePort.write_file` отказывает на
`view.access is not Access.WRITE`. Но по матрице authority
(`workspace.py:219`) `CANDIDATE: (Access.READ, …, True)`, то есть CANDIDATE —
**read-view**, который пишет только в свой приватный буфер через `write_candidate`.

**Вывод:** managed-запись кандидата в приватный буфер невозможна на трёх
уровнях: нет выбора writer'а (слой 1), нет API открытия view (слой 2), нет
порта записи (слой 3). Это не один дефект, а отсутствующее звено целиком.

### Что это значит для плана

Порядок из §9.5 («сначала дефект, потом оракул») сохраняется, но объём работы
больше, чем «дать scoped writer порт». Нужны:

1. **Порт записи кандидата** — отдельный, узкий: `write_candidate(path, content, expected_sha256)`,
   который шлёт `WRITE_FILE` в CANDIDATE-view. Не расширять `write_file` до
   «пиши в read-view», иначе PERF-портал потеряет различие access↔effect.
2. **API открытия CANDIDATE-view** — `open_candidate_view(plan_ref)`, который
   заполняет `candidate_scope`. `open_view` остаётся как есть (у него нет способа
   выразить scope, и это корректно для его вызывающих).
3. **Выбор writer'а для planner** — в managed-режиме scoped writer должен писать
   через этот порт, а не по хосту; host-ветка только для `workspace_io is None`,
   и в managed без порта — честный отказ.
4. **Оракул** — только после 1–3. Плюс он должен доказывать, что канонический
   `.fa/admission/**` на хосте **не создан** (проба 4 это уже показала как
   ожидаемое) и что план не изменился до публикации (проба 3).

### Что уже проверено и работает (не надо чинить)

* authority: `write_candidate` / `read_candidate` есть и работают, `WRITE_FILE`
  для CANDIDATE роутится в `write_candidate` (`service.py:767`).
* codec: CANDIDATE + `candidate_scope` валиден (V1).
* в CANDIDATE-view нельзя писать в канон: план на хосте остался прежним,
  `.fa/admission` не создан.

### Открытый вопрос, который надо решить до кода

Есть ли у CANDIDATE-view **владелец-грант**? `ClientWorkspacePort` требует
`grant.view_ref == view` и `Access.WRITE`. Для CANDIDATE grant — от `CREATE_VIEW`
(READ-грант). Порт должен принимать именно такой грант и всё равно писать — то
есть проверка «write ⇒ Access.WRITE» переносится с порта на authority. Это
изменение инварианта порта, и его надо зафиксировать явно, а не протащить молча.

## 11. Вопросы оператора: зачем изоляция, откуда требование репарации, какой инвариант (2026-11-11)

Три вопроса оператора к §10, и ответы из первоисточников. Ниже — только то, что
подтверждено документом или кодом; мои прошлые формулировки, которые этим
опровергаются, помечены явно.

### 11.1. Зачем изолировали managed

**Источник:** `notes/execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md`
§0 п.2, §4.2, §4.3; `ledger.md` E259.

Причина не в чистоте, а в одном конкретном обещании: **чужой actor не должен
прочитать evolving candidate как canonical** (§4.2), и **canonical host tree
меняется только на checkpoint/publication, не после каждой записи** (§4.3).

Отсюда три механизма, и все три видимы в коде:

| механизм | обещание | код |
| --- | --- | --- |
| private view из pinned revision | reader не следует изменяемому `current` | `view_io.py`, `workspace.py`|
| один buffer на CANDIDATE-view | у кандидата ровно один адрес | `workspace.py:2745-2758` |
| `.fa` исключён из любой ревизии | control-plane никогда не публикуется | `workspace.py:228`, `view_io.py:28` |

Последняя строка — решающая для §10, и я её не заметил. `.fa` исключён **на
любой глубине** из `_Capture` и из view-IO. Значит `.fa/admission/**` не может
быть «местом, куда кандидат пишется» в managed-мире: этот путь не принадлежит
ни одной ревизии, то есть не существует в том пространстве, с которым работает
view.

### 11.2. Как появилось требование «исправлять план»

**Источник:** §6.1 (Q58/CT94), §7 (Q55–Q58, T0).

Требование — не про запись файла, а про **допуск**: coder не стартует без
принятого плана. Отказ детерминированного admission'а идёт в *bounded planner
repair* с общим replan-бюджетом, и после репарации нужен **re-admission по новым
bytes** (§7: «Re-admission после authorized plan revision; stale evidence не
переносится на новые bytes»).

Код это выполняет буквально: `_admit_plan` — цикл `while True` с
`planner_calls < planner_limit`, и `_run_admission_repair` возвращает новую
валидацию, а не правит состояние на месте.

Это же объясняет, почему §6.1 требует exact candidate + source-hash recheck +
`os.replace` по тому же каноническому пути: **канон остаётся каноном**, меняются
только его bytes, и это отдельный irrevocable commit point.

### 11.3. Как это вписывается в изоляцию: инвариант артефактов

Тут мой §10 был неполон, а вариант 3 из моего же вопроса — просто неверен.

**Где я ошибся.** Я предложил «в managed кандидат живёт по каноническому пути
плана» и назвал это «как требует буфер». Проверка кода:

- `seed_plan_candidate` ещё до CANDIDATE-мира создаёт host-копию по `.fa/admission/<run>/candidate-<uuid>.md`
  и *пишет её на хост*;
- `_run_admission_repair` читает кандидата обратно **host-путём**
  (`read_plan_snapshot(ctx.workspace, target)`) и в `finally` удаляет host-лист;
- `_canonical_parts` допускает к публикации только `worklogs/.../increments/`;
- `_planner_target_allowed` запрещает модели трогать `active_plan`.

То есть буфер и репарация уже **разведены**: буфер адресует *идентичность*
плана (label = канонический путь), репарация владеет *host-копией* под `.fa`.
Моё «одно место для кандидата» смешивало эти две вещи и требовало сломать
`_planner_target_allowed` — security-boundary, защищающий канон от модели.

**Инвариант, который отсюда следует (E259, дословно):**
`CANDIDATE` = «plan + scope equal plan_refs, ONE supervisor staging buffer via
`write_candidate`/`read_candidate`, **never canonical `.fa/admission`**».

Расшифровка в трёх частях:

1. **В managed канон существует только как byte-identical копия плана на хосте.**
   Managed-repair переписывает эту копию через CANDIDATE-буфер и публикует её
   обратно по тому же каноническому пути. Хост-путь `.fa/admission/**` остаётся
   **транспортом репарации**, не адресом кандидата.
2. **`candidate_target` не может быть каноном** — `PlannerDispatch` это уже
   запрещает (`candidate_target == active_plan` → ошибка). Это не баг, а граница:
   модель правит staged-копию, а не канон.
3. **`.fa` не является хранилищем managed-артефактов.** Ни буфер, ни публикация
   туда не пишут (E259: «never canonical `.fa/admission`»); `.fa/admission`
   остаётся host-side местом controller'а для сида и CT119-ретенции.

### 11.4. Что это меняет в срезе A

Не «куда писать», а **как контроллер читает кандидата обратно**. Сегодня:

```
planner пишет .fa/admission/<run>/candidate-<uuid>.md   (host)
controller читает его host-путём                         (read_plan_snapshot)
```

Целевое (и уже реализованное в `ExecutionClient.publish_plan`):

```
planner пишет буфер CANDIDATE-view по label = plan_ref.workspace_relative_path
controller читает буфер через READ_FILE на том же view
publication: PUBLISH по тому же view (CAS base_revision)
```

`publish_plan` (`client.py:479-591`) — **готовая правильная последовательность**:
CREATE_VIEW(READ, CANDIDATE, scope={plan_ref}) → WRITE_FILE(label) → STOP_VIEW →
PUBLISH → release. Срез A переиспользует её, а не изобретает: нужен обратный
read (READ_FILE до publication) и путь, где эти bytes попадают в
`admission.candidate` вместо host-листа.

**Следствие для слоя 3 из §10.** Отказ `ClientWorkspacePort.write_file` для
READ-view — не дефект, который надо «починить», а верное поведение: порт
general-purpose IO обязан требовать `Access.WRITE`. Запись кандидата — отдельная
операция с отдельным grant'ом (`CREATE_VIEW(READ, CANDIDATE)` + буфер). Поэтому в
срезе A появляется **отдельный узкий порт кандидата**, а не расширение
`write_file`. Это подтверждает форму среза A и снимает мой открытый вопрос из §10.

### 11.5. Следствия, которые надо решить до кода

1. **Репарация в managed меняет канон без host-write.** Значит `planner_calls`
   может пойти на второй раунд, а `source.ref.sha256` уже другой — `_check_admission_source`
   сравнивает `ctx.admission.snapshot` с **host**-файлом. Для managed нужен
   re-read через view, иначе второй раунд упадёт на `source-changed`.
2. **`seed_plan_candidate` создаёт host-файл до вызова стадии.** В managed это
   staging-артефакт, который не должен существовать (или должен, но не быть
   адресом). Нужен явный ответ: host-сид остаётся транспортом или уходит в view.
3. **Повторный раунд в managed:** после публикации CANDIDATE-view закрывается, и
   следующий раунд должен открыть новый view от новой ревизии.

Ни один из трёх не решается «молча»: 1 и 3 меняют место чтения источника, 2 —
существование host-артефакта.

### 11.6. Три следствия §11.5 проверены — все три снимаются

**Следствие 1 (второй раунд vs `source-changed`).** Снимается: PUBLISH пишет план
в **тот же** канонический host-root, который читает `read_plan_snapshot`. Цепь
подтверждена: `_ManagedStageLease`/`ManagedExecution` владеет проектом, authority
пишет через `_project_parent(binding.source, inputs.plan_relative)` и
`os.replace` по канону (`workspace.py:3973-3982`); `binding.source` — это fd
зарегистрированного workspace, а `SessionManager._provision_managed` регистрирует
именно `run_context.workspace_path` (`manager.py:345`), то есть чекаут
оператора. После публикации host-файл содержит новые bytes, поэтому
`_check_admission_source` на втором раунде сравнивает канон с обновлённым
снапшотом и расхождения нет.

**Следствие 2 (host-сид под managed).** Снимается: host-сид остаётся
**транспортом инициала**, а не адресом. Он нужен, чтобы у стадии был вход, и он
же — то, что удаляется в `finally`. В managed он не является местом записи
кандидата: пишет планер в буфер.

**Следствие 3 (новый view на второй раунд).** Снимается по той же причине, что и
1: ревизия после PUBLISH включает новые bytes плана, а `ClientWorkspacePort`
открывает PROJECT-view от `managed.current_revision_id` в начале каждой стадии
(`cli.py:1812-1821`), не переиспользуя старый грант.

### 11.7. Оставшийся настоящий вопрос: адрес, который видит модель

Он не про безопасность и не про authority, а про **model-facing contract**, и
здесь два пространства имён расходятся по делу:

| пространство | значение | кто задаёт |
| --- | --- | --- |
| то, что видит модель | `.fa/admission/<run>/candidate-<uuid>.md` | `seed_plan_candidate` |
| то, что требует провод | `plan_ref.workspace_relative_path` (канон плана) | `_candidate_buffer` |

Оба нужны: первый — staging-адрес, о котором модель может рассуждать и который
не выглядит как «перезапиши план»; второй — идентичность, которую view уже
закрепил. Уравнять их нельзя: `PlannerDispatch` запрещает `candidate_target ==
active_plan`, и этот запрет — граница, а не рудимент.

**Решение (в духе «перевод в одном месте»):** адрес модели остаётся staging-
адресом; **узкий порт кандидата знает оба** и переводит один в другой. Authority
не меняется, `PlannerDispatch` не меняется, `_planner_target_allowed` не
трогается, 38 тестов и security-boundary остаются как есть. Именно это и есть
шов: единственное место, которое знает и model-facing адрес, и wire-facing
идентичность.

**Следствие для `ClientWorkspacePort`:** не расширяем. Порт получает узкий
`write_candidate(path_label, content, expected_sha256)` и `read_candidate(...)`,
привязанные к purpose, а не к `Access`. Инвариант «write ⇒ Access.WRITE»
остаётся верным для general-purpose порта и не распространяется на
purpose-bound буфер — это разные операции.

### 11.8. Mutation-policy для кандидата: почему guard не нужен, и это надо сказать вслух

Сегодня scoped writer вызывает `_write_with_guard(..., managed=False)`. Это
выглядит как недоделка; по факту ровно так и должно быть, и вот почему:

- буфер — **single-writer by construction**: один view, один owner, один файл
  `candidate`; конкурента, от которого `detect_conflict` защищает, не существует;
- путь `.fa/admission/**` **исключён из любой ревизии** (`.fa` в
  `_PROTECTED_COMPONENTS` и `_BLOCKED_COMPONENTS`), поэтому у него нет
  `file_version` в том пространстве, где конфликт имел бы смысл.

Значит `managed=True` добавил бы чтение `llms.txt` через view и проверку, у
которой нет предмета, — то есть риск ложного отказа без выигрыша. Решение:
оставить `managed=False`, но **зафиксировать причину комментарием и тестом**, а
не оставить её случайностью. Fail-closed сохраняется там, где он нужен: если
порт отсутствует в managed-композиции, writer отказывает, а не пишет на хост.

## 12. Что реализовано в срезе A (2026-11-11)

Решение оператора: чтение кандидата — **через view** (`READ_FILE` на CANDIDATE),
срез A делается целиком. Реализация и её проверка — в `ledger.md` E508.

Три решения, принятые по ходу и здесь зафиксированные, потому что каждое
меняет наблюдаемое поведение:

1. **`expected_sha256` протягивается, а не остаётся `None`.** Для буфера `None`
   означает «ожидание отсутствия», поэтому вторая запись в одну стадию была бы
   `STALE_REVISION`, тогда как host-путь перезаписывал свободно. Планер сохраняет
   право править свой кандидат; CAS остаётся реальным.
2. **Чтение буфера происходит внутри жизни view, а не после стадии.** View
   закрывается в `finally` композиционного корня, поэтому байты читаются там же и
   передаются контроллеру как данные.
3. **Сброс захваченных байт — на стороне потребителя и на входе стадии.** Иначе
   второй раунд репарации валидировал кандидата предыдущего раунда. Это поймал
   тест, а не рассуждение.
