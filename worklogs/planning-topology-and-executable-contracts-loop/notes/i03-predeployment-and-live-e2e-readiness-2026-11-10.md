# I03 — что осталось до деплоя и live-host E2E

**Срез планирования:** 2026-11-10<br>
**Сверка по checkout:** 2026-11-10 (`b7cf473f96538e2a70447bb117fabfa2876006d6`, `arena/e3879a47-first-agent-dev`)<br>
**Назначение:** свести W3/W4 задачи, фактическое состояние E2E-пакета и порядок закрытия перед approved-host deployment. Это плановый отчет: он не закрывает STEP, wave, вопрос или live case; сверка не меняет статусы и не является свидетельством запуска.

## Короткий вывод

- **W0, W1 и W2 закрыты только Arena-локально**: соответственно E503, E505–E510 и E526–E527. Это не подтверждает deployed-host поведение.
- **W3 открыт и остается полностью Arena-local.** Деплой/`fa update`, реальная clean-workspace readiness и live-host доказательства не являются условиями W3. Сначала надо завершить локальные контракты, тесты, package preparation и review.
- **W4 остается OPEN; live acceptance в репозитории не зафиксирована.** В актуальном плане нет подтвержденного approved-host `fa update`, зафиксированного образа или завершенного live suite; все 3 I01- и 35 I03-origin case rows в мастер-листах имеют `NOT RUN`. Локальные тесты, сборка пакета, collection и simulated preflight не меняют этот статус. Это утверждение ограничено имеющимися repository-артефактами и не делает выводов о возможных незафиксированных внешних действиях.
- После E530 core sequence такова: **STEP9 → STEP9A → STEP9B → Arena-local DoD каждой новой E530 slice → оставшаяся core STEP10/W3 package/review работа → W4 deployment/live E2E/evidence review → I03 sign-off**. Отдельная зависимость STEP7 → STEP8 должна быть выполнена до закрытия STEP9: текущий W3 reconciliation включает S6P7/S6P8/S6P9, а S6P9 зависит от S6P8. Это не запрещает параллельно выполнять другие STEP9-local задачи, но не позволяет начать STEP9A/B до завершения prerequisite STEP9. Под E544 broad-baseline checks (полный `just test`/`just check`/`just check-deep`, full 18-path mutation sweep, installed-wheel build, ShellCheck-only cases и Q139) остаются best-effort, а не блокерами merge/predeploy/I03 close; exact result остаётся видимым и незапущенная проверка не становится PASS.

Основной источник статусов — актуальная таблица и reconciliation в [I03 increment plan](../increments/increment-03-execution-workspace-foundation.md), с решениями E530–E544 в [ledger](../ledger.md). Для W4 следует читать вместе с [live-host E2E plan](i03-live-e2e-test-plan-2026-10-22.md), [producer register](e2e-live-verification-register.md), каноническим [E2E package index](../e2e/README.md) и отдельным [STEP9A custody design](w3-acceptance-custody-kill-attribution-design.md). Кодовые и локальные verification anchors для этой сверки перечислены в §6. Старые checkpoint paragraphs в исходных документах сохраняют историю; они не заменяют current reconciliation и более поздние ledger decisions.

## 1. Текущее состояние и границы доказательств

| Область | Статус по текущему плану | Что это означает |
| --- | --- | --- |
| W0 — local route-negative closure | CLOSED Arena-locally (E503) | Локальные negative oracles закрыты; не deployed acceptance. |
| W1 — local production cutover | CLOSED Arena-locally (E505–E510) | Managed search/reach и локальные ограничения закрыты. Проверка approved Q97 profile остается W3; Q106 отложен в W4. |
| W2 — local workflow acquisition/nesting | CLOSED Arena-locally (E526–E527) | Локальная composition/nesting доказана; execution-host и live S08 witnesses все еще впереди. |
| W3 — Arena-local closure | **OPEN** | Не запускать host deploy. Остались review/package, STEP9, STEP9A, STEP9B, новые E530 slices и оставшиеся STEP10 local gates. |
| W4 — approved-host deploy и live acceptance | **OPEN; live acceptance не записана** | По плану начинается только после W3 close; требует approved host, run sheet, один deploy, freeze, reviewed suite и evidence review. В текущих case sheets все live results остаются `NOT RUN`. |

Канонический [E2E index](../e2e/README.md) говорит, что ни один case в пакете не выполнялся на live host. В [I03 master sheet](../e2e/I03/live-verification.md) — **35 cases: 27 surfaces и 8 joins**, все `NOT RUN`. [I01 sheet](../e2e/I01/live-verification.md) содержит еще три planned cases, тоже `NOT RUN`; они отображают 42 I01 contract declarations и семь относящихся к I01 deferred obligations. Результаты принимают только `NOT RUN | PASS | FAIL | BLOCKED`; `NOT RUN` и `BLOCKED` не равны PASS, а попытки append-only.

Producer mapping уже содержит локально проверенное дополнение Q108: frozen I03 baseline сохраняет **125 уникальных producer keys**, а current coverage содержит **126 mappings**, включая `NEW:Q108-B-managed-inventory` → `I03-LIVE-S08`. Это проверка целостности артефактов, не свидетельство host behavior. Frozen baseline нельзя переписывать ради новых E530 producers: для них до suite freeze требуется предусмотренное пакетом явное mapping/lineage.

### Что уже есть локально, а что не следует из этого выводить

- Есть fail-closed `tests/integration/` harness (`conftest.py`, `_host.py`) и семь существующих execution-host test nodes. Readiness integration `tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication` также переведена в `execution_host`; E537 и текущий collect-only зафиксировали **8 host nodes**. Это только collection/selection evidence: в репозитории нет результата исполнения этих nodes против approved Docker/cgroup host.
- `e2e/I03/fixtures/` и `scripts/e2e_live.py` **отсутствуют** в checkout; план предусматривает создание fixtures только после независимого STEP7 review и внешний observer в рамках подготовки пакета. Создание и local verification этих частей, а также финального W4 run sheet остаются незавершенными; без них suite нельзя считать замороженным или готовым к запуску.
- E528 содержит целевые локальные проходы (в том числе `fa authoring-check` и Pyrefly), E529 — выбранные stats/C901 tests и отдельные mutation результаты, E532 — локальный C901 diff-guard и ряд общих quality checks. Это прогресс, не STEP9/W3 close.
- **Последний записанный полный `just check` — E540, exit 8.** Pytest reported 7,796 passed, 18 skipped, 8 deselected и 3 xfailed; lint также отметил Pylint R0801/R0401 и coverage-floor нарушения (`_build_role_registry` 89.2% при требовании 100%, `_cmd_stats` 50.0% при 80%, `_validate_run_args` 93.5% при 100%). Это run на широком dirty worktree, не чистая финальная приемка. E541 содержит более поздние targeted checks (54 passed), но в записях нет более позднего полного green `just check` или закрытого `just check-deep`. Этот full-gate результат остаётся красным/историческим, не PASS; high-ROI findings следует фиксировать и разбирать по source evidence, но зелёный repository-wide baseline не является условием MVP merge или test deploy по E544. Floors не ослабляются и красные результаты не маскируются.
- E529 также фиксирует, что post-run survivor packaging прервался: **500 stats-module mutants остались неразобранными**. Не выдавать частичный C901 эксперимент за завершенную полную mutation-проверку или за Q139.
- Q137 clean-readiness remains OPEN and has no host PASS. После E537 реальный clean-copy `uv sync` / hook install / `ready_repaired` / commit / publication — W4 host case; W3 проверяет только marker, default deselection, explicit selection и отказ без `FA_REQUIRE_EXECUTION_HOST=1`/реального preflight. Старый E534 `precommit_prewarm_failed` относится к прежней конфигурации с Go-backed Gitleaks pre-commit hook и не диагностирует текущий hook set: E539 удалил локальный hook, E540's более широкое удаление CI было superseded исправлением E541, а текущая конфигурация сохраняет Gitleaks только в blocking CI. E544 не переводит host readiness в best-effort и не разрешает Arena-обход: она remains a W4 live acceptance item; полный локальный baseline при этом не блокирует MVP predeploy.

Отдельно от live-E2E: E543 временно отложил C901 GitHub workflow wiring ради доставки. Локальный `tests/test_c901_diff_guard.py` остается активен; без `C901_DIFF_BASE` GitHub Actions пропускает только diff-зависимый тест. Его wiring нужно вернуть отдельным workflow-authorized изменением; в этой работе защищенный workflow не редактировать. Gitleaks остается blocking full-history CI scan, pinned на 8.30.1, без локального Go-hook. **Несогласованный comment в source:** `.github/workflows/advisory.yml` по-прежнему утверждает, что version pin должен совпадать с ревизией в `.pre-commit-config.yaml`, хотя текущая конфигурация и тестовый контракт не содержат локального Gitleaks hook. Это устаревший comment, не действующая политика; workflow не менялся из-за отдельной E543 scope restriction.

## 2. Рекомендуемая последовательность Arena-local работ до W3 close

### A. Завершить независимую review-зависимость и только затем писать fixtures (SLICE6 STEP7 → STEP8)

1. Назначенный независимый reviewer закрывает ручной STEP7 checklist: source/import и installed entry, readiness, descendant/cgroup fencing, publication/recovery, nested workflow, I01 planning/parser/admission, maintenance/secret-handling и safe stop/rollback. Зафиксировать reviewer, дату и findings; self-review planner/coder недостаточен. Повторить review после material changes.
2. **Только после этого** реализовывать ограниченный disposable fixture/helper package в `e2e/I03/fixtures/`, external evidence observer, команды и cleanup. Каждый fixture/driver должен быть назван в reviewed plan, иметь local negative-control sensitivity proof и безопасную изоляцию. Live-host команды остаются вне default pytest. Обновить derived index/coverage/handoff в рамках их checker contract; не добавлять E530 witness молча и не переписывать frozen producer baseline. Поскольку STEP9B позднее добавит host witness и может изменить пакет, повторить независимую проверку затронутого oracle/fixture после такого material change.

Это обязательная отдельная dependency package preparation. Текущий W3 reconciliation включает S6P7/S6P8/S6P9 в оставшиеся STEP9-local gates, а таблица зависимостей задает S6P7 → S6P8 → S6P9. Поэтому финальный fixture package должен быть готов до закрытия STEP9 и, транзитивно, до STEP9A/STEP9B (они gated by STEP9). План не требует остановить остальные STEP9-local работы до этого; run sheet должен определить безопасное параллельное выполнение, сохранив жесткую зависимость.

### B. Закрыть существующий STEP9, только на Arena-local evidence

Довести финальный W3 bank и выполнить незакрытые критерии из increment plan:

- повторить `fa authoring-check`, полный `pyrefly`, owning C1/composition banks (`test_execution_composition.py` и связанные legacy triage), E2E coverage checker и необходимые локальные контрактные тесты;
- закончить W3-часть S6P5/7/8/9/10: подготовить копируемый host run sheet из source-grounded deployment/workspace facts и точные команды/stop conditions (S6P5; actual running-image/kernel/cgroup facts будут собраны только в W4); закрыть S6P7 review до S6P8 fixtures; завершить S6P9 mapping каждого producer к deployed-behaviour oracle; пройти S6P10 local package/marker/selection/release checks. В W3 допустимы selection/collection и simulated preflight checks; они не подтверждают Docker, cgroup или readiness на host;
- подтвердить в approved Q97 profile `memory_bytes ≥ 1,342,177,280` bytes. Конфигурационная проверка — локальный gate; фактические kernel/cgroup/profile facts собираются в W4;
- сохранить Q108 `NEW:` mapping и все producer lineage; прогнать mapping/contract validation без потери frozen keys. S6P9 mapping checker success — artifact integrity, не host acceptance;
- зафиксировать Q139 в STEP9 как **`DEFERRED`**, не `PASS`, по E531/E544. Эта запись не закрывает STEP9, не означает измерение coverage и не присваивает live verdict;
- закрыть core STEP9 package, mapping, profile, review и planning prerequisites. Для высокоценной локальной проверки фиксировать точный результат; полный `just check`/`just check-deep`, full 18-path mutation sweep, wheel build и ShellCheck-only cases — best-effort, не W3/predeploy blockers. Не превращать skip/error/unrun в PASS. Реальный readiness run здесь не требуется и не должен запускаться.

STEP9 остается зависимостью STEP9A. Закрытие STEP9 не означает закрытия W3 или готовность к host deployment.

### C. Реализовать STEP9A: custody acceptance tests и exact kill attribution для новых планов

STEP9A — W3 hard blocker, ограниченный новым post-I03 plan schema; исторический v1 plan остается archival, без ретроактивной миграции или custody claim. По отдельному [STEP9A design](w3-acceptance-custody-kill-attribution-design.md) оператор утвердил вариант C: planner-owned semantics плюс controller-minted versioned `AcceptanceBundle`, привязанный к immutable workspace/test revision и полному closure — acceptance sources, config, support/helper/fixture/driver/runner и selector→nodeid resolution. Это зафиксированное design decision, не implementation evidence: такого символа в `src/fa` нет, и STEP9A остается открытым.

Локальные acceptance controls должны доказать:

- pre-coder syntax/import/collection/fixture/runner validation; collection/setup error, skip, timeout, crash или zero tests — это ERROR/non-kill, никогда не `PROVEN`;
- seal exact bytes/IDs/mapping/runner до coder-stage; coder видит только read-only mode A; verifier исполняет те же pinned bytes. Изменение/добавление/удаление accepted bytes, stale seal или неоднозначная mapping закрываются fail-closed;
- если C не может доказать closure/read-only projection, fail closed и использовать отдельный самодостаточный immutable payload fallback B, а не hash-only sidecar. Это payload fallback не равен скрытому visibility mode B: скрытый mode остается future/unsupported и не включается как silent fallback без отдельной реализации;
- `TEST-DEFECT` не редактирует sealed bytes in place: planner решает по pinned invariant, новая версия получает новый hash, старая evidence сохраняется, затронутые gates выполняются повторно;
- каждый kill связывает ровно один contract, стабильный TEST-ID и ровно один nodeid. Целевой тест должен быть зеленым на текущей реализации непосредственно перед mutation (не обязательно на T0); только assertion failure этого nodeid доказывает kill. Нет slice-wide fallback. Проверки durable/external effects идут по реальному production composition и authoritative sink.

### D. После STEP9 и STEP9A — STEP9B как планирование, не реализация

STEP9B должен подготовить source-grounded executable plans для полного AI-native workflow MVP, который E530 требует до I03 close. Эти планы задают planner-owned machine-checkable invariants/acceptance tests до coding, coder-proposed seams с явным owner/planner agreement до реализации, observable vertical slices и production composition. Требуются конкретные source paths/callers/EDGE oracles, test ownership, зависимости, local DoD, failure/`TEST-DEFECT`/replan, human decision gates, negative controls, project-host witness и точные обновления W4 package/index/coverage до freeze.

Планы должны явно решить schema/grammar: действующий `plan_ids._SLICE_CEILING = 7` не обходить молча. E530 разрешает превышение N≤7 только внутри I03; STEP9B должен выбрать обоснованную узкую грамматическую/validation extension либо linked new-schema план и описать миграцию/архивацию. STEP9B не меняет parser/schema и не реализует продукт. Никакая новая slice implementation не начинается до complete, reviewed plans и необходимых owner decisions; неутвержденная политика остается блокирующим ASK/Q.

### E. Сначала local DoD всех новых E530 slices; затем оставшаяся исходная STEP10

Каждая новая slice закрывается отдельно на Arena: production caller и EDGE oracle, локальные acceptance tests, mutation/negative controls и все явно записанные exit criteria. До этого **не возобновлять оставшуюся исходную STEP10 работу**.

После всех новых local DoD завершить core STEP10 package, run-sheet, marker/selection и review prerequisites. На Arena предпочитать высокоценные focused C1/caller checks и targeted producer/EDGE proofs для изменяемых production seams; записывать команды, точные результаты и ограничения. Полные `just test`/`just check`/`just check-deep`, 18 full-declared-path mutation kills, установленный-controller wheel build на CPython 3.13 + `zlib` и ShellCheck-only cases (12 параметризованных cases) — best-effort по E544, не hard W3/merge/deploy gates. Не строить отдельный runner, не ослаблять критерии и не переименовывать красные/skip/unrun проверки в PASS. Q139 остается отдельной best-effort проверкой после W4; `just check-deep` его не заменяет.

Финальный W3 review/run sheet должен фиксировать candidate source, approved suite/commands, fixtures и их ownership/cleanup, expected artifacts, rollback/stop criteria и prerequisites. Любая material change после review требует повторного review. W3 закрывается после STEP9, STEP9A, STEP9B, всех новых slice DoD и core Arena-local package/review prerequisites; best-effort baseline items могут остаться красными, skipped, deferred или unrun и должны быть названы без PASS. Отсутствие host availability не мешает локальному close, но host evidence нельзя записывать как будто оно получено.

## 3. W4 go/no-go и порядок approved-host выполнения

W4 разрешается начинать только после W0–W3 Arena-local close и обязательного review/run sheet. До первой команды host оператор должен иметь maintenance approval, clean approved-host checkout, freshly fetched `origin/main` на точном утвержденном candidate SHA и удерживать `main` замороженным на время updater (у него нет pinned-SHA input). Это не место для разработки fixtures или изменения тестов: недостающий host prerequisite дает BLOCKED, а не повод дописывать suite на сервере.

1. Выполнить **один** approved deploy/build на Linux/Docker host:

   ```sh
   AUTO_STASH=0 SKIP_TESTS=1 SKIP_UV_SYNC=1 PRUNE=0 fa update
   ```

   `PRUNE=0` не дает updater cleanup запустить `docker image prune`, сохраняя предыдущий образ для reviewed rollback. `SKIP_TESTS=1` пропускает только updater step 7 (`run_tests`: deploy-smoke-test cleanup, optional host `uv sync` и repository-wide pytest); предыдущий step 6 `smoke_tests()` все равно вызывается, как и отдельный reviewed W4 suite. Скрипт заранее задает `TEST_RC=0`, поэтому печатное `Tests: rc=0` при skip — не PASS и не заменяет W4 suite. При ненулевом update нельзя заключать, что deployment не произошел: зафиксировать выведенные HEAD/health/test status и не делать blind retry.

2. Независимо подтвердить approved source SHA, running image digest и config/profile; Docker health должен быть `healthy`, не `no-healthcheck`; явно проверить внутри образа `fa --version` и core-import smoke. Exit 0 сам по себе недостаточен, поскольку updater может печатать smoke warnings. При ошибке identity/health/smoke остановить suite и применить reviewed recovery.
3. **Заморозить работающий образ** и его identity. После freeze запрещены повторный `fa update` и rebuild до конца suite/evidence capture.
4. Запустить только reviewed suite по run sheet с `FA_REQUIRE_EXECUTION_HOST=1`, включая семь `tests/integration/` host cases и `tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication`, а также все требуемые I01–I03 cases. Существующий `tests/integration/test_nested_workflow.py` использует controlled callback и **не** заменяет spec §9.1 real-provider direct+nested witnesses. В W4 suite до freeze должны быть зарегистрированы/включены эти реальные witnesses и новый E530 AI-native workflow MVP project-host witness; последний еще не определен STEP9B и не входит в frozen suite.
5. Clean readiness case должна пройти настоящие Linux/UID/cgroup-v2/Docker/config/cache/image preflight **до side effects**, затем показать fresh-copy `uv sync`, `pre-commit install-hooks`, `ready_repaired`, установленные hooks, реальный test commit и local publication. Наличие теста, его collection или симулированный preflight не заменяют эти наблюдения.
6. Для каждой строки собирать append-only evidence с точными SHA, image digest, profile/config, run ID, command, exit/effect, artifact и reviewer. Использовать persisted artifacts, Docker/kernel/cgroup/process/DB facts и safe sentinels, а не in-process object или текстовый log как sole oracle. Проверять negative controls и cleanup (ноль owned containers/cgroup entries/supervisors); BLOCKED, setup/collection/infra failure, skip или неизвестная terminality не PASS. Не делать retries ради зеленого verdict. Production image/service не мутировать для host negative control; разрешен только заранее approved, изолированный disposable test image/cell.

### Approved-host prerequisites

Перед suite должны быть доступны реальные условия из run sheet: approved Linux host и Docker daemon/socket; cgroup v2 с нужными `cpu`, `memory`, `pids` controllers и profile parents; approved digest-pinned images, config/profile и безопасный cache; controller UID из конфигурации; wheel/build и pinned dependencies, требуемые reviewed suite (для `I03-LIVE-02` — поддерживаемый CPython 3.13 с `zlib` и frozen build dependencies); реальные provider credentials для spec §9.1 direct+nested и S08 witnesses; `CAP_SYS_PTRACE`, если run sheet выберет `strace` oracle. Не записывать credentials в artifacts. **ShellCheck — best-effort локальная W3 check** для исполнения 12 ShellCheck-only cases; под E544 это не hard gate для merge/deploy, текущий `tests/integration/_host.py` его не проверяет и он не является approved-host prerequisite. Локальный installed-wheel build тоже best-effort, но если reviewed host suite требует wheel, его фактическая identity/build contract проверяется в W4. Текущий Python policy — `>=3.13` без искусственного pin; Gitleaks local hook/Go не являются readiness prerequisites.

## 4. Отложенные после W4 вещи и финальный sign-off

- **Q106:** strict xfails `tests/test_execution_project_tools.py::test_q106_large_outline_parity_remains_open` и `tests/test_execution_project_tools.py::test_q106_large_reach_parity_remains_open` удерживают legacy large-outline/reach parity сверх действующего 60 KiB Q97/Q111 envelope. В W4 требуется разрешить или явно disposition этот вопрос на реальных host results; это не waiver, полученный от локального теста. В плане остался устаревший line locator `:304,315`; стабильные nodeids соответствуют текущему коду.
- **Q139:** E531 первоначально назначил full configured-scope mutation baseline после W4 suite/evidence capture. E544 сохраняет это как best-effort post-W4 opportunity, но снимает его как prerequisite для MVP merge, test deployment и I03 close. Не строить runner или Arena workaround ради запуска. Если проверка выполнима и ROI оправдывает, команда ровно такая:

  ```sh
  uv run --frozen python scripts/run_slice_mutmut.py --configured-scope
  ```

  Если run завершен, записать selection, версии инструментов, полные counters и вручную вычисленный denominator `killed / (total − type_invalid − no_tests)`. Не использовать вместо него runner field `mutation_score_non_type_invalid`: код runner задает его denominator как `total − type_invalid` и он не эквивалентен предписанию E531. Не подменять этот run `run_targeted_mutmut.py`, stats/C901 экспериментом или `just check-deep`. Если run не стартовал/не завершился, или actionable statuses не разобраны, оставить Q139 `DEFERRED`/unmeasured и не заявлять full-scope mutation coverage; это не блокирует MVP/test deploy/I03 close по E544. Unreviewed status — не PASS.
- **E223 / I03 close:** четыре transferred duties остаются обязательными: deployed source-to-behaviour verification; environment/readiness и inherited-baseline review; broad independent implementation/security/recovery/evidence review; integrated E2E/deployment signoff. Baseline review must state red/skip/deferred/unrun evidence truthfully; E544 does not require a repository-wide green gate before MVP merge, test deployment, or I03 close. Каждое обязательное I01–I03 live row, включая readiness и E530 witness, должно быть независимо принято как PASS на точной image/SHA/config; затем записывается operator sign-off. Никакая локальная проверка не присваивает live verdict.

## 5. Сжатая dependency map

```text
E530 gate order:
W0–W2 Arena-local (closed)
  → STEP9 local gates (Q139 = DEFERRED)
  → STEP9A sealed acceptance custody + exact attribution
  → STEP9B source-grounded plans for E530 MVP
  → Arena-local DoD for every new E530 slice
  → remaining core STEP10 package/review prerequisites (broad quality/mutation checks best-effort)
  → W3 close (Arena evidence only; red/unrun broad checks stay visible)
  → approved-host preflight + one fa update + identity/health/smoke
  → freeze image → reviewed W4 suite + live evidence + cleanup
  → disposition Q106; optionally attempt full Q139 if worthwhile
  → independent evidence review → I03 sign-off (no full-scope Q139 claim unless completed)

Separate SLICE6 package dependency, to be completed before W3 close:
STEP7 independent review → STEP8 fixtures/package (never reverse this order)
```

Это dependency order, не календарное расписание: STEP9B еще не создал новые планы, fixture package не завершен, а последний записанный полный gate остается красным. STEP7 → STEP8 и S6P7 → S6P8 → S6P9 должны быть выполнены до закрытия STEP9, а значит до STEP9A/B; reviewed run sheet должен определить, какие остальные STEP9-local задачи можно безопасно вести параллельно. До выполнения W3 close и одобрения run sheet не запускать `fa update` и не начинать live-host E2E.

## 6. Повторная сверка и локальные evidence (2026-11-10)

Дата среза наверху остается 2026-11-10; эта повторная сверка относится к checkout `b7cf473f96538e2a70447bb117fabfa2876006d6`. Источники плановых обязательств и текущих статусов:

- W0–W4, S6P5–S6P10 и STEP7–STEP10: [актуальная reconciliation increment plan](../increments/increment-03-execution-workspace-foundation.md); E530/E531/E537/E540–E545 — [ledger](../ledger.md). STEP9A design: [custody/kill-attribution note](w3-acceptance-custody-kill-attribution-design.md).
- Case inventory/statuses: [E2E index](../e2e/README.md), [I01 sheet](../e2e/I01/live-verification.md), [I03 master sheet](../e2e/I03/live-verification.md), producer baseline/coverage JSON. В текущих case fields: I01 **3/3 NOT RUN**; I03 **35/35 NOT RUN**, по kinds **27 surfaces + 8 joins**.
- Selection/readiness code: [`pyproject.toml`](../../../pyproject.toml), [`tests/integration/_host.py`](../../../tests/integration/_host.py), [`tests/test_execution_host_markers.py`](../../../tests/test_execution_host_markers.py), [`tests/test_workspace_readiness_integration.py`](../../../tests/test_workspace_readiness_integration.py). Host preflight implementation не проверяет ShellCheck; local marker/preflight tests не вызывают approved Docker/cgroup host.
- Update behavior: [`scripts/fa`](../../../scripts/fa) dispatches `fa update` to [`scripts/fa-update.sh`](../../../scripts/fa-update.sh). The current script calls `smoke_tests()` before `run_tests()`, `SKIP_TESTS=1` skips the latter, and `PRUNE=0` bypasses `docker image prune`. Gitleaks source consistency: [`advisory.yml`](../../../.github/workflows/advisory.yml), [`.pre-commit-config.yaml`](../../../.pre-commit-config.yaml), [`test_hygiene_hooks_install.py`](../../../tests/test_hygiene_hooks_install.py); the workflow comment at line 107 is stale, while the test asserts CI-only policy.
- Q106 code anchors are the two named strict-xfail functions in [`tests/test_execution_project_tools.py`](../../../tests/test_execution_project_tools.py). Q139 ordering/denominator is E531; executable is [`scripts/run_slice_mutmut.py`](../../../scripts/run_slice_mutmut.py), whose `mutation_score_non_type_invalid` denominator differs from the required E531 accounting.

Выполнены только локальные проверки (их результаты не дают live verdict):

- `uv run --frozen pytest -q tests/test_execution_host_markers.py tests/test_execution_host_preflight.py` — **27 passed**; selection/opt-in contracts и simulated preflight only.
- `FA_REQUIRE_EXECUTION_HOST=1 uv run --frozen pytest --collect-only -q tests/integration tests/test_workspace_readiness_integration.py -m 'execution_host or live_e2e'` — **8 tests collected**, не исполнены.
- `uv run --frozen pytest -q tests/test_e2e_artifact_contract.py` — **29 passed**; только artifact contract.
- `uv run --frozen python scripts/check_execution_e2e_coverage.py` — **OK**: I01 42 CTs / 7 deferred obligations / 3 cases; 126 I02-origin/I03 producers across 89 I02-origin and 35 I03 cases; 2 exact duplicate keys collapsed. Сам checker прямо не выводит live PASS.
- `uv run --frozen pytest -q tests/test_hygiene_hooks_install.py tests/test_secret_isolation_invariants.py` — **54 passed**; Gitleaks configuration contract, не запуск самого Gitleaks scanner.

В этой сверке не запускались полный `just check`, `just check-deep`, configured-scope Q139, реальный `load_and_probe_execution_host`, `fa update` или W4 suite. Следовательно, она не сообщает host readiness, deployment, live PASS либо I03 acceptance. Последний записанный полный `just check` остается E540; case sheets остаются `NOT RUN`.

### Дополнительные Arena-local проверки после E544 (2026-11-10; E545)

- `uv run --frozen pytest -q tests/test_execution_composition.py tests/test_execution_host_markers.py tests/test_execution_host_preflight.py tests/test_e2e_artifact_contract.py` — **127 passed**; локальные композиция/selection/preflight/artifact contracts, не host execution.
- `uv run --frozen python scripts/check_execution_e2e_coverage.py` — **OK**: I01 42 CTs / 7 deferred obligations / 3 cases; 126 producer mappings across 89 I02-origin and 35 I03 cases; 2 exact duplicate keys collapsed. Это mapping integrity, не live PASS.
- Первый повтор `uv run --frozen fa authoring-check` завершился exit 1 из-за `FA-AUTHORING-V4-PYTEST-SKIP` в `tests/test_c901_diff_guard.py:240`. E545 заменил imperative `pytest.skip(...)` на `@pytest.mark.skipif(...)`, сохранив ровно прежнее условие: GitHub Actions и отсутствующий `C901_DIFF_BASE`. Workflow и CI authorization scope не менялись.
- После изменения: `fa authoring-check` — **0 diagnostics**; `pytest -q tests/test_c901_diff_guard.py tests/test_authoring_rules_tests.py tests/test_s12_marker_hygiene.py` — **62 passed**; Pyrefly — **0 errors**; Ruff check/format и `git diff --check` — **pass**. Для проверки условия C901 guard: с полной базой `9ba095dba7ea862fcbac3371e552e49ae4cb7533` тест **1 passed**; без `C901_DIFF_BASE` при `GITHUB_ACTIONS=true` тест был **1 skipped намеренно**, и этот skip не засчитан как PASS.
- Эти результаты дают только targeted Arena-local evidence. Они не закрывают STEP7/STEP9/W3, не разрешают STEP8 до независимого review и не подтверждают approved host, clean readiness, deployment или live behavior. Полный `just check`, `just check-deep`, Q139, host preflight, `fa update` и W4 suite по-прежнему не запускались; I01/I03 case sheets остаются `NOT RUN`.
