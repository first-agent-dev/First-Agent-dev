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
