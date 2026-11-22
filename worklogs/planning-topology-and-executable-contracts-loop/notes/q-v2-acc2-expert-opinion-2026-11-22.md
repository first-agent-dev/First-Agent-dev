# Expert opinion — invoke_workflow / evidence model (2026-11-22)

> **SUPERSEDED 2026-11-22 (E604).** This draft contains two errors (the
> HARD+NON_EXECUTABLE framing and the SLICE3 sequencing) and has been consolidated
> into one final document. The consolidated package is
> [evidence-model-final-decision-package-2026-11-22.md](evidence-model-final-decision-package-2026-11-22.md).

**Scope:** the V2 evidence/admission model (`plan_v2.py`, `acceptance_bundle.py`, `plan_admission.py`, `workflow_controller.py`, canonical schema, skills, CLI dispositions ingress).
**Status:** read-only analysis + independent re-measurement. No production change.
**Question this answers:** the system is supposed to make one thing true — an AI-produced artifact is checked by something other than the AI that produced it, and that check cannot be talked around. What is the current state of that promise, what is actually missing, and in what order should SLICE3 proceed?

---

## 1. Чем смысл системы `workflow` в нашей продуктовой лине — и какие ценности она преследует

### 1.1. Смысл

Система не существует, чтобы «ИИ сделал код». Она существует, чтобы было нельзя обойти проверку того, что ИИ сделал, даже если сам ИИ говорит, что всё проверено. Весь слой вывода этого смысла:

| Механизм | Что он покупает |
|---|---|
| Планировщик пишет документы, coder пишет код — разные стадии, разные права | Автор утверждения — не автор доказательства |
| `INV → CT → TEST-ID → selector → one nodeid` | Каждое утверждение либо отображается в исполняемую проверку, либо отклоняется |
| Seal связывает точные байты на точной ревизии | Проверялась ровно та версия, которую ревидировали |
| `MUTATION`-вью ограничена `{src, scripts}` | Coder не редактирует тесты, которым обязан соответствовать |
| Верификатор гоняет sealed-набор в управляемой ячейке | Доказательство производится в среде, которую автор не контролирует |
| `ToolResult.fail` на упавщий create | «Завершилось» и «проект создан» — одно утверждение |
| Реальная публикация — до admission | PUBLISHED ≠ ADMITTED; unadmitted revision — audit fact, не input |

Все остальные механизмы — scaffold, repair, ticks, seal-pointer, projection — производные от этой линии. `traceability`, `custody`, `authority separation`, `fail-closed`, `minimalism-first`.

### 1.2. Ценности в том порядке, в котором они должны читаться

1. **Независимость доказательства от автора претензии.** Это самая глубокая ценность. Если бы не она, система была бы просто «генератором кода».
2. **Отказоустойчивость, а не надёжность.** Система не может нигде молчать и нигде не может «успешно» пройти через отказ. Всё структурно и стабильно.
3. **Малые, верифицируемые шаги.** Один путь от claim → check, никаких широких маршрутов вокруг.
4. **Восстанавливаемость без потери доказательств.** Repair — бюджет, не тишина. Репутация seal'а сохраняется (old evidence + new revision).
5. **Аудит-белая дорожка.** Каждый появляется/кто/когда/почему — в seal, в ledger, в pointer.
6. **Минимализм по отношению к новым механизмам.** Новый механизм — только если существующий исчерпан. Seal-путь, построенный STEP9A как библиотека без продакшн-потребителей, — это и есть пример неудачного места минимизации (§4 ниже).

### 1.3. Почему это так не работает сейчас

Ценность 1 (независимость) прямо или косвенно ломается во всех четырёх измеренных местах, найденных в аудите. Ценность 6 (минимальное добавление механизмов) — потому что всё, что доказано в STEP9A/9B, существует как библиотека и нигде не подключено: ядро продукта (`invoke_workflow` → controller → planner → coder → verifier) по-прежнему идёт через старый V1-путь admission, а не через V2 seal.

---

## 2. Состояние системы на 2026-11-22 (что реализовано, что нет)

Подготовлено по фактам в репозитории, не по плану.

| Слой | Состояние | Evidence |
|---|---|---|
| V2 parser (`plan_v2.py`) | **Готово** — 45 тестов, 22 killed mutants, `parse_plan` + `contract_evidence` + `attested_contracts` + `resolve_selectors` | `tests/test_ai_native_plan_v2.py` (45 `def test_`), `plan_v2.py:610` |
| V2 admission route | **Готово** — `_validate_v2_admission`, `snapshot_from_bytes(format=PLAN_V2)` | `workflow_controller.py:3427`, `plan_admission.py:260` |
| Payload layer (plan_semantics.py → render/install) | **Удалён** — CT-2.3/2.7/2.8/2.9 реализованы | `planner_dispatch.py` с `CREATE_NEW_PROJECT` |
| Seal binding (`AcceptanceBundle`) | **Нигде не вызовется в продакшене** — 0 ссылок в `workflow_controller.py`, 0 потребителей вне `acceptance_bundle.py`/`acceptance_collection.py`/`acceptance_defect.py`/`kill_attribution.py` | grep-verified 2026-11-22; CT-2.4 отсутствует |
| Mode-A projection (closure в RootedViewIO) | **Не реализован** — protected_paths несёт только `plan_ref.workspace_relative_path`; `worklogs/<slug>/acceptance/` не защищён | `workspace.py:2188–2196`, `:2808–2816` |
| Fence retired on V2 route | **Не реализован** — `slice_verification.py:552` исполняет planner-authored verify fence | grep-verified |
| CLI dispositions ingress | **Не реализован** — `--dispositions` отсутствует в `invoke-workflow`; tool schema имеет поле, CLI его теряет | `cli.py:968–1001`, `workflow_tool.py:245` |
| Schema rewrite (V1→V2) | **Не реализован** — каноническая схема по-прежнему учит `TESTS:` + verify fence, 0 вхождений V2 marker / `KIND:` | `artifact-schema-and-grammar.md`, `tests/test_skill_grammar_emit.py` (18 тестов), `tests/test_skill_conformance.py`, `tests/test_e2e_artifact_contract.py`, `tests/test_verify_gate_live.py` |
| Skills (feature-planning, plan-authoring, tests-writing) | **Не переписаны** — оба still teach `TESTS:` | `knowledge/skills/feature-planning/SKILL.md:799`, `plan-authoring/SKILL.md:215` |
| Repair allowlist (D-V2-9.8) | **Готово, но геометрически узко** — только `increments/increment-01-initial-plan.md` + `open-questions.md`; не покрывает отсутствие acceptance test file | `workflow_controller.py:3047–3057` |

---

## 3. Source audit — четыре факта, перемеренные в этом проходе

Все четыре измерены повторно в этом проходе (read-only), с учётом того, что=container не нужен для parser/seal evidence.

### 3.1. Факт 1 — `KIND` читается ровно в одном месте и только чтобы простить

`grep -rn "invariant.kind\|item.kind" src/fa/ --include=*.py` → **1 hit** (`plan_v2.py:622`). Ни seal, ни verifier, ни verdict, ни report его не читают.

| Измерение | Результат |
|---|---|
| `SOFT` + `EVIDENCE: TEST_REQUIRED` + нет тест-строки → `parse_plan` | admitted |
| → `contract_evidence(graph)["CT-1.2"]` | `UNCOVERED` |
| → `attested_contracts(graph)` | `()` |

### 3.2. Факт 2 — HARD-инвариант допускается с waiver

| Измерение | Результат |
|---|---|
| `KIND: HARD` + `EVIDENCE: NON_EXECUTABLE` + reason → `parse_plan` | admitted |
| pre-grant `contract_evidence(graph)` | `{'CT-1.1': 'executable', 'CT-1.2': 'uncovered'}` — грант ещё не binding |
| → `bind_dispositions(graph, declarations, today=…)` + `contract_evidence` | `{'CT-1.1': 'executable', 'CT-1.2': 'attested'}` |
| → `attested_contracts(bound)` | `('CT-1.2',)` |

Самый строгий класс в словаре — тот, который легче всего переводится в подпись человека, и выбирает это планировщик, а не человек. PRESERVATION защищён только потому, что его класс-проверка стоит до waiver-ветки (`:617`) — порядок, а не правило.

### 3.3. Факт 3 — seal не умеет сказать «непроверено»

| Измерение | Результат |
|---|---|
| `mint_seal(graph=bound, …)` с `attested=('CT-1.2',)` | mint'ed; `seal.attested=('CT-1.2',)`, selectors=`(TEST-1.1,)` |
| `mint_seal(graph=fact1_graph (CT-1.2 uncovered), …)` | mint'ed без отказа; `attested=()`; selectors=`(TEST-1.1,)` |
| seal, 5 contract / 1 TEST / 1 grant vs 2 / 1 / 1 | **байтово неотличимы по форме** — нет числа контрактов, нет множества непокрытых |

### 3.4. Факт 4 — «ready CT» не существует

`grep -rn "ready" src/fa/ --include=*.py` → 0 вхождений (кроме `ReadyState`/`READY` status, не имеющих отношения к контрактам). Q-V2-ACC-2 и INV-05 и CT-3.1 сформулированы над категорией, у которой нет рантайм-смысла.

### 3.5. Дополнительные находки этого прохода

| # | Находка | Evidence |
|---|---|---|
| D1 | **План противоречит сам себе.** §8 step 4: «Q-V2-ACC-1/2 are closed»; Q-V2-ACC-2 row: «BLOCKING for CT-3.1… filed 2026-11-21 (E600)». Строка §8 неверна. | `plan-v2:650` vs `plan-v2:621` |
| D2 | **Seal-механика — библиотека, без продакшн-потребителей.** `mint_seal`/`sealed_collection_argv`/`acceptance_collection`/`acceptance_defect`/`kill_attribution` — 0 импортов вне своих модулей. | grep-verified |
| D3 | **Repair-геометрия:** allowlist repair-стадии (`increments/increment-01-initial-plan.md` + `open-questions.md`) физически не может исправить gap coverage, требующий добавить acceptance test file. | `workflow_controller.py:3047–3057` |
| D4 | **CT-2.4 отсутствует** — named test `test_validation_and_seal_precede_coder...` отсутствует (grep-verified). Controller не имеет ни одной ссылки на AcceptanceBundle. | `plan-v2:517` |
| D5 | **§8 step 4 и §5 SLICE3 DEPS**: Q-V2-ACC-1/2 оба должны блокировать SLICE3; Q-V2-MODEA-1 остаётся resolved (B). | `plan-v2:650`, `:622` |
| D6 | **Verify fence всё ещё исполняется** на PLAN-V2-маршруте (`slice_verification.py:552`, `subprocess.run(... shell=True)`). | grep-verified |
| D7 | **Protected paths** несут только plan file; closure — `worklogs/<slug>/acceptance/` — нигде не protected. | `workspace.py:2191–2199`, `:2810–2819` |

### 3.6. Что действительно исправляет `KIND`, но не говорит этого в схеме

Слова приглашения «hard invariant/ready CT» появляется ровно в трёх местах плана: line 60 (grammar delta), line 233 (production grammar requirement), line 284 (INV-05), line 511 (CT-3.1 row) — и все четыре ссылаются на категорию, которая не существует. Каждый раз это один и тот же дефект: **план требует от рантайма то, что рантайм никогда не должен был знать**.

---

## 4. Отдельно: словарь dispositions-reason

Закрытый набор из четырёх значений:

```text
HOST_READINESS  DEPLOYMENT_IDENTITY  OWNER_APPROVAL  DURABILITY_POWER_LOSS
```

Это **не** классификация по трудности планировщика. Это классификация по причине непроверяемости в песочнице. Каждый reason обязан соответствовать одному из четырёх классов непроверяемости, каждый класс — с именованной причиной и человеком, который должен её перепроверить на хосте:

| Reason | Что говорит | Кто отвечает |
|---|---|---|
| `HOST_READINESS` | «Проверка проходит только на утверждённом хосте» (инфраструктура) | Оператор |
| `DEPLOYMENT_IDENTITY` | «Кто развернул — не проверить изнутри» | Оператор / W4 |
| `OWNER_APPROVAL` | «Только человек может утвердить это» | Holder ключа |
| `DURABILITY_POWER_LOSS` | «Физика вне песочницы» | Оператор / W4 |

**Здоровый смысл этого словаря:** новый reason — это не выбор планировщика, а регистрация нового класса непроверяемости. Он требует ratification и редакции схемы, и это правильно: если закрытый словарь растут, это симптом, что система признаёт новый непроверяемый контракт в каждом доступе. Сама схема должна нести причину закрытости («reason существует, потому что человек может его перепроверить»).

---

## 5. Вопрос Q-V2-ACC-2 переосмыслен

### 5.1. Что спрашивают

«Где отказывать SOFT-плану с TEST_REQUIRED, который не покрыт тестом» — это вопрос уровня маршрута неправильно задан. Правильный вопрос, как показал audit: «что `KIND` обязывает?»

### 5.2. Ответ

`KIND` — это не степень строгости, а выбор контракта, который остаётся проверяемым. После исправления:

| Значение | Обязывает | Граница при отказе |
|---|---|---|
| `HARD` | Проверяется тестом. Нельзя отписаться | Отказ на admission: `hard-invariant-cannot-be-waived` |
| `SOFT` | Может быть подтверждён человеком через ratified pipeline | Отказ на admission, если нет теста и нет grant'а |
| `PRESERVATION` (пересечение) | Класс, не KIND — PRESERVATION ВСЕГДА executable | Уже реализовано, как должно быть |
| `UNCOVERED` | Недопустим подписанию и sealed | Seal refuse (именованный контракт) + admission refuse |

HARD + NON_EXECUTABLE — это не «классы, которым может быть дан waiver», это bug против слов плана. SOFT + (нет теста, нет grant'а) — это не «допустимый промежуточный план», а неутверждённая приёмка.

### 5.3. Что нельзя читать из схемы

«ready CT» — категория, не существующая. Её убираем из плана и состояний, а не пытаемся реализовать. Семантика «ready» в смысле «ready to admit» — это синоним «admitted», и «admitted» уже существует как проект.

### 5.4. Ответ на вопрос «должен ли план SOFT+TEST_REQUIRED дойдёт до coder'a без теста»

**Нет.** Ни при каком способе. Но это ответ не «отказ на seal», а отказ на admission + seal-refusal. Реализация:

- **На admission** (в `_admit_evidence`): любой контракт, для которого нет теста и нет валидного grant'а, — отказ. Diagnostic: `evidence-uncovered` (или `contract-uncovered`, имя закрытого rule).
- **На seal** (`mint_seal`): проверка покрытия, либо отказ, либо sealed-граф с coverage-картой.
- **`SOFT` + grant**: тот же путь, что уже существует (`bind_dispositions`) — owner/evidence/reviewed_at от caller'а, грант не старше 30 дней. Правило мягкое — authorised, но видно.
- **`HARD` + waiver**: отказ. Bug fix.

---

## 6. Порядок работ — SLICE3 и соседние

**Что делаем первым (не code):** устранить противоречие плана и единое «закрытое» утверждение. Reframe Q-V2-ACC-2 на «KIND obliges», убрать «ready CT», переписать строку §8 step 4 («are closed») в текст, который будет истинным. Это редакция документа, без реализации.

**Вторым** — schema rewrite (artifact-schema-and-grammar.md → V2) + 2 skills + 4 conformance tests одним commit'е. Это вопрос «где отказывать», но это вопрос уровня «чего схема хочет от парсера». План требует этого до SLICE3.

**Третьим** — сам фикc Evidence (Step A из E601):
1. `HARD` + `NON_EXECUTABLE` → `hard-invariant-cannot-be-waived`
2. `UNCOVERED` → admission refusal (или же seal refusal — D)
3. `mint_seal` refuse while any contract is `UNCOVERED`
4. Переписать два encoding-теста (`test_a_soft_invariant_may_still_stay_uncovered`, `test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered`)

**Четвертым** — seal self-description (Step B из E601):
- `contract_total`, `contract_covered: [...]`, `contract_attested: [...]`, `contract_uncovered: [...]` (после шага 3 пустой) — seal становится аудируемым без графа
- `schema_version` bump

**Пятым** — fix repair allowlist:
- `_repair_allowlist` возвращает suffix'и по категориям отказа: increment (+open-questions) при конгрант-отказах, acceptance/tests/** при покрытии-отказах.
- Или: отказ «coverage» — не repairable, приводим к BLOCKED с чётким диагностикой и operator decision. Моя рекомендация — widen allowlist: repair предназначен именно для того, чтоб дописать документ, а не чтоб отдавать operator'у, что нельзя.

**Шестым** — CLI `--dispositions` (CT-1.5 bounded): add `--dispositions <path-or-json>` и передать на tool, без второй проверки.

**Седьмым** — SLICE3 integration:
1. CT-3.2 (seal mint wiring) — сначала — это то, чему всё остальное опирается.
2. CT-3.3 (mode A projection) — after CT-3.2 или параллельно.
3. CT-3.4/3.5/3.6 (attribution, TEST-DEFECT, verifier) — after CT-3.2.
4. CT-3.1 (graph + nodeid edges) — после того, как §5 поправлена.

---

## 7. Финальная рекомендация

1. **Q-V2-ACC-2 = новый вопрос: «что обязан KIND».** Переписывает CT-3.1-row и INV-05 без фразы «ready CT». Опция «HARD = must execute» — bug fix vs. слов плана; «SOFT = attested via ratified pipeline» — уже реализовано. UNCOVERED — не должен выходить наружу.
2. **Seal — self-describing**: contract count + coverage map. После шага 3 uncovered set пуст by construction; sealed record утверждает инвариант, который seal обеспечивает.
3. **Schema rewrite = first actual work item**, не «второй этап». План сам ставит эту задачу первым пунктом SLICE1. Это единственный инструмент, который не даёт каждому новому контракту проектироваться слепо.
4. **Repair geometry** — расширить allowlist.
5. **CLI --dispositions** — отдельным bounded коммитом.
6. **§8 step 4 «are closed» — fix** как правило этого же commit'а.
7. **Q-V2-ACC-1** — budgets есть и строгие (30 tests). Записываем как closed-by-code. Transitive-import half — named residual, не открытая gate.

### Словарь disposition reasons — закрывается правильным способом

Закрытый набор четырёх reason'ов не является неправильным. Ему не хватает ratification-процедуры, которая говорит «новый reason = изменение схемы + ratification, а не выбор планировщика». Схема должна нести это как правило.

---

## 8. Открытые вопросы для оператора

1. **Q-V2-ACC-2 re-framed:** согласен ли оператор с новым вопросом «что KIND obliges» вместо «где отказывать»? (Я даю да.)
2. **Allowlist repair** — widen (рекомендую) или отдельный ОБЪЯвленный blocking?
3. **§4 dispositions split** — согласен ли оператор с отказом на admission + seal-side check, или один «второй gate» это избыточно? (Рекомендую: admission для repair/diagnostics, seal для любых путей, которые не прошли admission — TEST-DEFECT re-mint, external caller.)
4. **Схема rewrite vs. план §5 vs. план §10** — после переписывания схемы нужно скорректировать ссылки в плане (§2 «Sole V2 source», §5 SLICE1, §11).
5. **«В чём смысл workflow»** — §1 этого документа — это мои внутренние суждения; если оператор хочет иную формулировку — отложить.

---

## 9. Что я НЕ делал, и что не делаю

- Я не менял плановые документы, код или тесты — это read-only аудит.
- Я не менял `plan_v2.py` / `acceptance_bundle.py` — это реализация (Step A), не анализ.
- Я не утверждаю, что сейчас накопленный код «правилен» — только то, что я измерил.
- Я не рекомендую переезжать весь SLICE3 вперед schema rewrite — все CT-3.x ждут решения Q-V2-ACC-2, а не конкретного коммита.

---

## Приложение: измерения в этом проходе

Все результаты, которые я сам перемерил (read-only, 2026-11-22):

1. `SOFT` + `TEST_REQUIRED`, нет селектора → `parse_plan` admits; `contract_evidence(graph)["CT-1.2"] == UNCOVERED` ✓ (на реальном коде, синтетический вход)
2. `HARD` + `NON_EXECUTABLE` + reason → `parse_plan` admits; после `bind_dispositions` → `contract_evidence["CT-1.2"] == ATTESTED`; `attested_contracts == ("CT-1.2",)` ✓
3. `mint_seal` → mint'ed над graph'ом с UNCOVERED contract; seal.attested=(); seal не записывает contract-count ✓
4. «ready CT» → 0 вхождений в `src/fa/` ✓ (grep)
5. `mint_seal` / `sealed_collection_argv` / `acceptance_collection` / `acceptance_defect` / `kill_attribution` → 0 production consumers (grep) ✓
6. `protected_paths` несёт только `plan_ref.workspace_relative_path` (`workspace.py:2188–2196`, `:2808–2816`) ✓
7. `slice_verification.py:552` — verify fence исполняется на PLAN-V2-маршруте ✓
8. CLI `fa invoke-workflow` — `--project-action`, `--project-slug`, НЕТ `--dispositions` ✓
9. `_repair_allowlist` — increment + open-questions only ✓
10. §8 step 4 «are closed» vs Q-V2-ACC-2 «BLOCKING» — прямое противоречие в плане ✓
