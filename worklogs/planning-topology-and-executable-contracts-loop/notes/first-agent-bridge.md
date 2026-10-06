# First-Agent: контекст для правки планов


**первая задача сессии:** аккуратно внести правки в текущие планы перед написанием кода, чтобы идеи ниже превратились в проверяемые контракты. Выход сессии — unified diff по `worklogs/…`,
готовый к аудиту по коду и применению оператором.

---

## 1. Проект: что и где

**Репозиторий:** https://github.com/first-agent-dev/First-Agent-dev. Tip на момент проверки: `2f6b8c15e94ef361f35382f76115dc7cac77e79a`.

**Рабочая папка планов:**
```
worklogs/planning-topology-and-executable-contracts-loop/
  roadmap.md                                   индекс, 6 инкрементов I01–I06, standing decisions
  ledger.md                                   EVIDENCE-леджер, append-only, E1–E48
  increments/increment-01-plan-grammar-and-extractor.md    единственный детализированный инкремент
  notes/artifact-schema-and-grammar.md        каноническая грамматика (§4 — слайс, §5 — леджер)
  notes/verify-block-design.{md,svg}          дизайн гейта (pre-check → baseline → fail-before → pass-after)
  notes/i02-handoff-verify-gate.md            банк контекста для I02, 7 открытых вопросов
  notes/role-prompts-conformance.md           банк правок промптов по ролям
  notes/RESEARCH-ADOPTION-PLAN.md             18 пунктов внедрения из research-записки
```

**Ключевой код:**
```
src/fa/inner_loop/plan_ids.py:55,92-167,180-283   экстрактор грамматики (SLICE#, SliceRecord, slice_records)
src/fa/inner_loop/prompt.py                       PLANNER :45, CODER :533, EVAL :685, CHAT :940
src/fa/inner_loop/prompt_composer.py:80-188       сборка промпта + cache-key по роли
src/fa/inner_loop/injections.py:89-133            InjectionSpec, INJECTION_SPECS (одна запись)
src/fa/inner_loop/workflow_controller.py:332,:401,:461   читатели .slices; _git_output; контекст eval
src/fa/inner_loop/hooks/loop_guard.py             детектор лупов (identical-call + ping-pong)
src/fa/inner_loop/recovery/attempt_history.py:205 attempt_count(tool_name, params_hash)
src/fa/inner_loop/coder_loop.py:600-649,:1248-1330  пересборка истории из лог-БД, компакшн
tests/test_plan_ids.py (367 ln)                   тесты экстрактора + конформанс живых артефактов
knowledge/skills/{plan-authoring,feature-planning}/SKILL.md   скиммы, которые пишут планы
knowledge/research/PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md   research, F1–F12, 14 принципов
```

**Топология (из roadmap):** feature → increment (один прогон, можно отгрузить) → `SLICE#`
(один коммит, контракты + verify) → `STEP#` (одно атомарное действие). Rolling wave: детален
только активный инкремент. Планировщик делает основную работу, кодер исполняет в жёстких
контрактах, eval судит; трекинг статусов — **только код**.

---

## 2. Проверенное состояние: что обещано и что есть на самом деле

| Элемент плана | Реальность на `2f6b8c1` | Как проверить |
|---|---|---|
| I01/SLICE1 — грамматика + `slice_records` | **Сделано.** `_SLICE_RE` только `SLICE#`; `SliceRecord`; тест `extract_plan_ids("### Step S1: legacy").slices == ()` | `grep -n "_SLICE_RE\|class SliceRecord" src/fa/inner_loop/plan_ids.py`; `sed -n '360,367p' tests/test_plan_ids.py` |
| I01/SLICE1/STEP3 — миграция теста и glob | **Сделано.** Фикстуры на `## SLICE1:`; glob покрывает `worklogs/*/increments/increment-*.md` | `sed -n '200,216p;291,367p' tests/test_plan_ids.py` |
| I01/SLICE2 — доступы `commands_for` / `section` | **Нет.** Методов нет; `.commands` плоский | `grep -n "def commands_for\|def section" src/fa/inner_loop/plan_ids.py` |
| I01/SLICE3 — предварительная проверка плана кодом | **Нет.** `tests/test_plan_precheck.py` отсутствует | `ls tests/test_plan_precheck.py` |
| I01/SLICE4 — миграция скиллов | **Нет.** `plan-authoring/SKILL.md:430` — `### Step S#: <title>`; в `feature-planning/SKILL.md` нет ни `SLICE`, ни `TESTS:`, ни `STEPS:` | `grep -n "Step S#\|SLICE\|TESTS:" knowledge/skills/*/SKILL.md` |
| I02 — гейт | Не начинался: `.commands` — ноль читателей (E39) | `grep -rn "\.commands" src/ \| grep -v plan_ids.py` |
| Промпт планировщика | Не содержит ни одного `SLICE`/`STEP#`. Свой формат: Class/Goal/Evidence/Scope/Assumptions/Constraints/Plan/Verification/Risks, шаги с полями `deps`/`accept`/`verify`, уровневые `focused:`/`regression:` | `grep -c "SLICE" src/fa/inner_loop/prompt.py` → 0 |
| Промпт eval `:857-880` | Отдаёт вердикты как `- S1: PASS` — старая лексика | `sed -n '857,880p' src/fa/inner_loop/prompt.py` |
| Кэш промпта по роли | **Уже построен.** `build_prompt_parts_v2` отдаёт `(cacheable, non_cacheable)` и ключ `fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}`; в докстринге прямо сказано, что «то, что меняется от задачи, разрушает переиспользование префикса» | `sed -n '1,20p;80,130p' src/fa/inner_loop/prompt_composer.py`; `tests/test_prompt_caching_per_role.py` |
| Канал инъекций (#7) | **Уже построен.** `InjectionSpec` + `INJECTION_SPECS`; зарегистрирована ровно одна инъекция — `coder_slice_ceremony` (роль `coder`, «before-gate, edit packet, after-gate», текст в `feature-planning/SKILL.md` §9-12). Пина инвариантов нет: добавить = одна строка в реестр + поле в `FeatureFlags` | `sed -n '89,133p' src/fa/inner_loop/injections.py` |
| Счётчик попыток (#2) | `AttemptHistory.attempt_count(tool_name, params_hash)` — по сигнатуре инструмента, не по `STEP#`/`CT#`. `stall` в контроллере нет | `grep -n "def attempt_count" src/fa/inner_loop/recovery/attempt_history.py`; `grep -rn "stall" src/fa/inner_loop/workflow_controller.py` |
| Контекст ретрая | `coder_loop.py:600-649` пересобирает историю из лог-БД; маскирование `:1248-1330` — про парность tool-call, не про дистилляцию провалов | `sed -n '600,649p' src/fa/inner_loop/coder_loop.py` |
| Статусы в increment-01 | `status: READY`, все `- [ ]`, хотя SLICE1 отгружён (трекинг кодом ещё не автоматизирован — I03) | `sed -n '1,10p' worklogs/…/increments/increment-01-*.md` |

---

## 3. Правила редактирования их артефактов

**Стиль (standing decision E48):** агентно-исполняемый текст — точные императивы, цели
`file:line`, запускаемые проверки `(exit: …)`. Никаких цитат, истории и обоснований внутри
шага — rationale живёт в `notes/`.

**Ownership (schema §1, E43):**

| Артефакт | Пишет |
|---|---|
| `roadmap.md` | планировщик (чат может подсказать) |
| тело `increment-*.md` (`SLICE#`/`CT#`/`STEP#`) | планировщик |
| галочки `STEP#`, статусы `CT#` | **только харнесс (код)** |
| `ledger.md` | eval (EVIDENCE) + харнесс (FACT) |
| `notes/` | планировщик / ревьюер |
| код и тесты | кодер |

**Ограничения, которые ломают правку, если их не знать:**

1. `tests/test_plan_ids.py::test_this_plan_is_conforming` требует, чтобы increment-01
   содержал `SLICE1` в `.slices` и `CT1` в `.contracts`. **Не переименовывать и не удалять их.**
2. `test_grammar_example_is_indistinguishable_from_a_real_fence`: ```verify-блок, показанный как
   пример грамматики, извлекается как настоящая команда. Примеры — только в обёртке ````text
   (CT13 фиксирует это поведение; менять не надо).
3. `test_real_plan_yields_its_own_verification_commands`: verify-блоки инкремента должны
   остаться настоящими командами.
4. Правила будущего pre-check (CT8/CT9/CT10): слайс с `CT#` обязан иметь `TESTS:`; каждый
   `STEP#` в `prescriptive`-слайсе обязан иметь `(exit: …)`; `DEPS:` — без циклов и ссылок на
   несуществующие id. **Все новые слайсы писать сразу под эти правила.**
5. `CT#` матчится `\bCT(\d+[a-z]?)\b`, уникален в инкременте; дефисы запрещены. Свободные
   номера: **CT16 и выше** (CT1–CT15 заняты, включая переименование `CT-DATA`→`CT7` по E34).
6. Идентификатор слайса — `SLICE(\d+[a-z]?)`, то есть **`SLICE1b` грамматически допустим**
   (суффикс-буква разрешён) — это позволяет вставить слайс без перенумерации.
7. Слайсов на инкремент — гипотеза 4–7 (E16). Сейчас 4; после правки ниже станет 6.
8. CI: `uv run fa authoring-check` (Level-0 kernel, блокирующий) + `scripts/check_protected_paths.py`.
9. Два красных doc-гейта (`test_doc_links`, `test_historical_workspace_docs_have_top_level_superseded_banner`)
   — **намеренно красные**, «чинить» их запрещено (E19). Новые файлы в `notes/` могут их
   задеть — предупредить оператора, не исправлять.

---

## 4. Рекомендации: что брать, where to land

### Взять

| # | Что | lands where | Зависимость | Почему |
|---|---|---|---|---|
| **R1** | Реордер внутри I01: выделить **SLICE1b «эмиттеры пишут грамматику»** сразу после SLICE1 | `increments/increment-01-…md` | только SLICE1 | путь «планировщик пишет → экстрактор понимает → контроллер видит» требует только SLICE1. Это самое дешёвое, что возвращает контроллеру слух (A) |
| **R2** | **SLICE5: пины инвариантов (байт-стабильный блок)** | там же | канал уже есть (`InjectionSpec`) | adoption #7; стоит одну строку в реестре, а закрывает и «компакшн вымывает правила» (F10), и кэш-префикс |
| **R3** | Правки промптов ролей: кодер (убрать дубли гейта, добавить бюджет разведки + стоп-условия), eval (L1 — код), планировщик (механические пункты self-check → в precheck) | **`notes/role-prompts-conformance.md` как забаненные дельты**, реализация в owning-инкременте | E47: planner→I01, coder→I03, eval→I03 | единственный рычаг без зависимостей от I01/I02 |
| **R4** | Счётчик попыток с ключом по `STEP#`/`CT#`/`accept:` | I02 (рядом с гейтом) | I02 | `LoopGuard` по устройству не видит «три разных неудачных фикса одного контракта» (distinct params = progress) |
| **R5** | Дистиллированный failure packet (≤15 строк), никогда сырой трансcript | I03 (там же REFLECT/реплан) | I03 | сейчас ретрай пересобирает историю из лог-БД — ровно самообусловливание из F3 |
| **R6** | GIVEN-компилятор из леджера (факты, которые не перепроверять) | I04 | формат леджера (notes §5) | дешёвый автономный скрипт; якоря в записях разнородны (`@ arena/01a0762b` — ветка, `@ 0e08ece` — коммит) → резолвить ветку в SHA, нерезолвимое пропускать |
| **R7** | `STEPS: prescriptive\|outcome` привязать к классификации TRIVIAL/STANDARD/LARGE (`prompt.py:91`) | дописать в SLICE4/STEP2 | SLICE4 | там уже написано «add authoring guidance for contract classes, TESTS:, and STEPS: mode» — новый слайс не нужен |
| **R8** | Держать кэшируемую часть байт-стабильной; не менять состав инструментов/effort внутри прогона; мерить hit rate | расширить `tests/test_prompt_caching_per_role.py` | — | кэш по роли уже построен (`prompt_composer`), осталось не разрушать его и измерять |

---

## 5. Открытый вопрос (решить до SLICE4)

В системе **два формата плана**:

1. рабочий формат планировщика (`prompt.py:166-240`): Class/Goal/Evidence/Scope/Assumptions/
   Constraints/Plan/Verification/Risks/Open questions; шаги с полями `deps` / `accept` /
   `verify`; уровневые `focused:` и `regression:`;
2. долговечная грамматика инкремента (`notes/artifact-schema-and-grammar.md` §4): `SLICE#`,
   `CT# [CLASS]`, `TESTS:`, `STEPS:`, `DEPS:`, ```verify.

Как один превращается в другой — ни в roadmap, ни в схеме нет. Пока это не решено, правило
«у каждого `CT#` есть тест» неприменимо к планам, которые планировщик реально пишет.

**Варианты:** (а) планировщик эмитит грамматику инкремента сразу; (б) есть шаг компиляции
рабочего плана в инкрементный файл **кодом**, без модели.

**Оформить как `ASK#`** (ваш #13) и добавить в `roadmap.md` в секцию `assumed:`/«Deferred».
Если к началу SLICE4 ответа нет — SLICE1b делать по варианту (а), но зафиксировать в леджере
записью типа `GAP`, что решение provisional.

---

## 6. Предлагаемые правки(нужно проверить)

Ниже — текст для `worklogs/planning-topology-and-executable-contracts-loop/`.
Идентификаторы: новые слайсы `SLICE1b`, `SLICE5`; новые контракты `CT16`–`CT19`.

### 6.1 `increments/increment-01-plan-grammar-and-extractor.md`

**(a) Изменить DEPS у SLICE4** — разделить эмиттеры и фикстуру:

было: `DEPS: SLICE1, SLICE2, SLICE3`
стало: `DEPS: SLICE1b, SLICE3`

**(b) Вставить SLICE1b сразу после SLICE1** (до SLICE2):

````markdown
## SLICE1b: Emitters write the new grammar
STEPS: prescriptive
DEPS: SLICE1
INTENT: planning skills and the planner prompt emit `## SLICE<n>:`, `- [ ] STEP<n>:`,
  `CT<n> [CLASS]:`, `TESTS:`, `STEPS: prescriptive|outcome`, `DEPS:` — so a freshly authored
  plan parses to a non-empty `.slices` and the controller's coverage gate stops no-op'ing.
CONTRACTS:
  CT16 [FUNCTIONAL]: a plan authored strictly from `knowledge/skills/plan-authoring/SKILL.md`
    yields `extract_plan_ids(...).slices` with every declared slice id.
  CT17 [FUNCTIONAL]: a plan authored strictly from `knowledge/skills/feature-planning/SKILL.md`
    yields non-empty `.slices`, and every `CT#` in it carries one of
    `FUNCTIONAL|CONSTRAINT|PRESERVATION`.
  CT18 [CONSTRAINT]: the slice-ceremony injection text (`coder_slice_ceremony`,
    feature-planning SKILL §9-12) states the acceptance predicate in the planner's step
    vocabulary (`accept:` / `verify:`), never in the verify-block vocabulary.
TESTS: tests/test_skill_grammar_emit.py
```verify
uv run pytest tests/test_skill_grammar_emit.py -q
uv run ruff check knowledge/skills tests/test_skill_grammar_emit.py
```
- [ ] STEP1: Edit `knowledge/skills/plan-authoring/SKILL.md`. Do exactly: replace the
      `### Step S#: <title>` heading form at `:430` with `## SLICE<n>: <title>`; replace step
      bullets with `- [ ] STEP<n>:`; add the `INTENT:` / `CONTRACTS:` / `TESTS:` / `STEPS:` /
      `DEPS:` lines in the order given in notes/artifact-schema-and-grammar.md §4.
      (exit: `grep -n "### Step S" knowledge/skills/plan-authoring/SKILL.md` returns nothing.)
- [ ] STEP2: Edit `knowledge/skills/feature-planning/SKILL.md`. Do exactly: add the slice
      skeleton with `SLICE#` / `CT# [CLASS]` / `TESTS:` / `STEPS:` / `DEPS:`; add the
      `STEPS:` mode rule — `outcome` when the slice's own verify result is what will teach the
      coder (unfamiliar subsystem, performance, flaky integration), `prescriptive` when the
      planner could have written the diff from what it read.
      (exit: a fixture written from the skill text parses to non-empty `.slices`.)
- [ ] STEP3: Edit the slice-ceremony injection text (feature-planning SKILL §9-12). Do exactly:
      keep the before-gate / edit packet / after-gate shape; state the acceptance predicate as
      the step's `accept:` check; add a bounded-recon budget and a two-attempt stop rule using
      the wording in notes/role-prompts-conformance.md §Coder.
      (exit: CT18 green.)
- [ ] STEP4: Add tests/test_skill_grammar_emit.py (NEW). Do exactly: for each skill, build a
      short plan from the skill's skeleton and assert
      `extract_plan_ids(text).slices` equals the declared ids, and — for feature-planning —
      that every record contract carries a class.
      (exit: CT16/CT17/CT18 green.)
````

**(c) Добавить SLICE5 в конец файла** (после SLICE4):

````markdown
## SLICE5: Pinned invariants, re-injected every call
STEPS: prescriptive
DEPS: SLICE1
INTENT: standing decisions survive compaction: the assembled block is byte-identical for every
  role call within a run, so the prompt-cache prefix is reused and a compacted context cannot
  silently drop the rules.
CONTRACTS:
  CT19 [FUNCTIONAL]: every role call in a run receives the standing-decisions block; the block
    is byte-identical across calls within the run (compared by hash in the test).
TESTS: tests/test_injection_pins.py
```verify
uv run pytest tests/test_injection_pins.py -q
uv run ruff check src/fa/inner_loop/injections.py tests/test_injection_pins.py
```
- [ ] STEP1: Add one `InjectionSpec` row for `standing_decisions` in
      `src/fa/inner_loop/injections.py` (registry at `:123`) plus the matching `FeatureFlags`
      field. Resolve in `off|observe|enforce`; default `observe`.
      (exit: `fa inject --explain` lists the new injection.)
- [ ] STEP2: Assemble the block from `roadmap.md` «Standing decisions» + ledger entries tagged
      `DECIDED` / `PRESERVE`. Do exactly: stable ordering (sort by entry id), no timestamps, no
      run ids, no paths that change per run.
      (exit: two consecutive assemblies produce identical bytes.)
- [ ] STEP3: Add tests/test_injection_pins.py (NEW). Do exactly: assemble twice within one run
      and assert equal hashes; assert the block is present in the cacheable part returned by
      `build_prompt_parts_v2`, not the non-cacheable part.
      (exit: CT19 green.)
````

### 6.2 `roadmap.md`

**(a) Таблица инкрементов — дописать в строки I02/I03/I04:**

| ID | One-line intent (дополнение) |
|---|---|
| **I02** | … + счётчик попыток с ключом по `STEP#`/`CT#`/`accept:` и трёхзначный результат (PASS/FAIL/ERROR; ERROR ≠ PASS) |
| **I03** | … + дистиллированный failure packet на ретрае (никогда сырой трансcript), L1-проверки в коде, трекинг статусов кодом |
| **I04** | … + GIVEN-компилятор: FACT-записи леджера → блок «уже проверено, не перепроверять» в промпт |

**(b) В «Standing decisions» добавить:**
```
- `assumed:` The planner's runtime plan format (prompt.py:166-240, steps with `accept:`) and the
  increment grammar (notes/ §4) are compiled one into the other by code, not by a model.
  Unresolved → ASK#-01, blocks SLICE4.
```

**(c) В секцию «Deferred — explicitly not scheduled» добавить строку:**

| Item | Why deferred | Promote when |
|---|---|---|
| Prompt-side effort routing (`reasoning.effort` per slice class) | a different lever from prose: it changes the budget, not the distribution. Must be measured in its own arm, never mixed with prompt changes | after I06 telemetry exists and the prose arms are measured |

### 6.3 `ledger.md` — дописать (append-only, старое не трогать)

```markdown
## Code-verified state at tip 2f6b8c1 (plan-edit session, 2026-10-05)

E49 FACT  I01/SLICE1 is shipped: `_SLICE_RE` is `SLICE#`-only, `SliceRecord` + `slice_records`
    exist, and `tests/test_plan_ids.py:367` asserts a legacy `### Step S1:` string parses to
    `()`.  [verified: plan_ids.py:55,92-143; tests/test_plan_ids.py:367 @ 2f6b8c1]
E50 FACT  I01/SLICE2 (accessors `commands_for` / `section`) and I01/SLICE3 (pre-check) are NOT
    implemented: no such methods in plan_ids.py; tests/test_plan_precheck.py absent.
    [verified: grep @ 2f6b8c1]
E51 FACT  The emitters still write the old grammar: plan-authoring/SKILL.md:430 is
    `### Step S#: <title>`; feature-planning/SKILL.md contains no SLICE/TESTS/STEPS tokens.
    [verified: grep @ 2f6b8c1]
E52 FACT  Because of E51 + the `SLICE#`-only extractor (E49), a freshly authored plan yields
    empty `.slices`, so `workflow_controller.py:332` returns early and the coverage gate
    silently no-ops. E23 describes this state; it is live, not archival.
    [verified: workflow_controller.py:332-334 @ 2f6b8c1]
E53 FACT  Prompt caching per role already exists: `build_prompt_parts_v2` returns
    (cacheable, non-cacheable) and key `fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}`;
    its own docstring warns that per-task variation destroys prefix reuse.
    [verified: prompt_composer.py:5-8,80-130 @ 2f6b8c1]
E54 FACT  The injection channel exists (`InjectionSpec`, `INJECTION_SPECS`) and holds exactly
    one spec, `coder_slice_ceremony` (role `coder`). A pinned-invariants injection costs one
    registry row plus one `FeatureFlags` field.  [verified: injections.py:89-133 @ 2f6b8c1]
E55 FACT  Attempt counting is per tool signature, not per work unit:
    `AttemptHistory.attempt_count(tool_name, params_hash)`; no `stall` counter in the controller.
    LoopGuard detects identical-call repeats and A/B ping-pong only — by its own docstring,
    distinct params count as progress, so "three different failed fixes for one contract" is
    invisible to it.  [verified: attempt_history.py:205; loop_guard.py:1-40 @ 2f6b8c1]
E56 GAP   The planner's runtime plan format (prompt.py:166-240; steps carry `accept:`,
    `verify:`, `deps:`; plan-level `focused:` / `regression:`) and the durable increment
    grammar (notes/ §4) are two formats with no defined transform between them. Until resolved,
    "every `CT#` has a test" cannot be enforced on plans the planner actually writes.
    [→ ASK#-01, blocks SLICE4]
E57 DECIDED  Reorder I01: emitters (SLICE1b) follow SLICE1, before SLICE2/SLICE3; SLICE4 keeps
    the conformance fixture and depends on SLICE1b + SLICE3. Rationale: notes/.
    [plan-edit session, 2026-10-05]
```

### 6.4 `notes/` — rationale (новый файл `notes/plan-edit-2026-10-05-rationale.md`)

Сюда вынести обоснование реордера, выбора R1–R8 и отвергнутых вариантов. В теле плана и в
леджере обоснований быть не должно (E48, schema §1).

---

## 7. Порядок работы и критерии приёмки

1. Перепроверить §2 командами из таблицы (код мог уехать).
2. Поднять вопрос о двух форматах плана (§5). Если ответа нет — идти по варианту (а) и
   зафиксировать E56 как `GAP`.
3. Вставить SLICE1b и SLICE5, поправить DEPS у SLICE4, дописать roadmap и леджер, создать
   `notes/plan-edit-2026-10-05-rationale.md`.
4. Проверить сам файл инкремента его же инструментами:
   - `python -c "from fa.inner_loop.plan_ids import extract_plan_ids as e; import pathlib; p=pathlib.Path('worklogs/…/increments/increment-01-*.md'); i=e(p.read_text()); print(i.slices); print([c for c in i.contracts]); print([r.slice_id for r in i.slice_records]); print(i.commands)"`
     → в `.slices` есть `SLICE1`; есть `CT1`; слайсы идут в порядке документа; команды —
     настоящие, а не пример грамматики.
   - каждый новый слайс имеет `TESTS:` и ```verify; каждый `STEP#` — `(exit: …)`;
     `DEPS:` не содержат циклов и ссылок на несуществующие id.
   - `uv run fa authoring-check --output json` — без новых нарушений.
   - Слайсов стало 6 (гипотеза 4–7, E16).
5. Выход: unified diff по `worklogs/` + короткая записка оператору: что изменено, что
   забанено, что требует решения (ASK#-01).

---

## 8. Приложение: тексты блоков для ролей (когда дойдёт очередь)

Держать забаненными в `notes/role-prompts-conformance.md`, вставлять в owning-инкременте.

### A. Кодер — блок эффективности и стоп-условий (для I03 / текста церемонии слайса)

```
You implement one step of a plan. The harness runs the acceptance checks; you do not re-run them.

## Scope
- Implement only the step(s) named in the brief.
- Read at most 6 files before your first edit. If you need more, name them in one message and
  stop reading there.
- Do not edit files outside the brief. Do not tick steps, do not edit the increment plan, the
  ledger, or notes/.

## Execution (STEPS: prescriptive)
- The brief is the path. Implement the steps in order; do not re-derive a decision the brief
  already made.
- Each step names its `accept:` criterion. When it is met, go to the next step.

## Execution (STEPS: outcome) — use instead when the brief says so
- You own the path between contract checkpoints. The `CT#` are the checkpoints; the steps are
  not a script.
- After each checkpoint, run only the command that tells you whether that checkpoint is met.

## Verification belongs to the harness
- The step's `accept:` (and the slice's verify command) are the acceptance criteria. The harness
  runs them.
- Do not re-run a check the acceptance predicate already covers (pytest, ruff, mypy, the plan's
  regression command). The regression command runs once, at the end of the increment.
- Run a command yourself only when you need its output to decide the next edit.
- A green acceptance ends the work. Do not add "just in case" checks.

## Stop conditions
- Done when: the step's `accept:` check passes.
- Local failure (typo, wrong path, missing import): fix once, re-run once.
- The same step failing twice: stop. Emit
  `BLOCKED: <STEP#> | <command> | <exit code> | <first 10 lines of output>` and end the turn.
- Brief is wrong, missing a prerequisite, or self-contradictory: emit
  `REPLAN: <CT# or STEP#> | <evidence: file:line or command output>` and end the turn.
- Do not emit a third attempt at the same fix.

## Output
- Emit the patch and nothing else. No preamble, no restatement of the brief, no summary of what
  you did.
- Deviations: one line, `DEVIATION: <what> | <why>`.
- No narration of your reasoning. The evaluator reads the diff and the command output.
```

### B. Failure packet (для I03)

```
FAILED: <SLICE#>/<STEP#>   attempt 2 of 2
command: <exact command>
exit: <code>
output (first 10 lines):
<...>
contracts in scope: CT3 [CONSTRAINT], CT4 [FUNCTIONAL]
diff stat: <n files, +a -b>
Rule: fix the named failure. Do not restate the plan. Do not re-explore.
```

### C. GIVEN-блок (для I04)

```
## Given (verified in this repo; do not re-derive)

- plan_ids.py:55 `_SLICE_RE` matches `## SLICE<n>:` only; the legacy `S#` pattern is gone.
  [E1 @ 2f6b8c1]
- extract_plan_ids has exactly two external callers, workflow_controller.py:332 and :461; both
  read only `.slices`. [E2,E3 @ 2f6b8c1]

Rules:
- Treat a GIVEN line as true. Do not re-read the file to confirm it. Do not re-run a command
  whose result is recorded here.
- A GIVEN line is valid only for the commit in its tag. If your change invalidates one, emit
  `STALE: <E-n> | <what changed>` instead of silently working around it.
- If you need a fact that is not listed here, read for it once and record it.
```

Компилятор блока: брать только `FACT` с якорем `[verified: … @ <tag>]`; `<tag>` резолвить в
SHA (ветка → SHA); нерезолвимое — не включать.
