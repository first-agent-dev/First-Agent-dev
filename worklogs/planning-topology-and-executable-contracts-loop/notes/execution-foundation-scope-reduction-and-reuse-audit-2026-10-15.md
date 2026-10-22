# Execution foundation: scope-reduction и reuse audit

**E231 current disposition (2026-10-16):** Q59/Q60/Q63/Q74 are resolved in the question tracker
and I03 execution/workspace spec §§6.1/7/9. Advisory/manual + EXISTING experimental suggestion,
source-grounded delegated reuse design, four live states with optional commentary/no reason enum,
and per-stage checkpoints. Older OPEN/proposed statements below are historical, not pending gates.
No implementation/deployment acceptance follows; retained source snapshots remain historical.

**Дата:** 2026-10-15. **Product source:** `d9109f489c84cb7f1ab3568b609d96e5b2b61ae2`.
**Предыдущий отдельный шаг:** decision note сохранена в `03413ab771110dcc2f98994e3e86738e3c1aad5a`.
**Consumers:** агент перепланирования retained I02 и автор нового foundation I03.

Это **отдельный audit**, запрошенный после обновления
[decision note](execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md).
Source facts ниже проверены чтением конкретных producers/tests и bounded diagnostics (§9).
Recommendations — предложения reviewer'а, **не новые ратифицированные operator decisions**.
Ни product implementation, ни plans/DoD/status trackers этим шагом не изменяются.

## 0. Вывод

Scope можно существенно сократить **по числу mechanisms и public surfaces**, не по mandatory guarantees:

1. Один existing session/run substrate; не второй execution-session manager или history DB.
2. Один managed execution backend с PTY и noninteractive adapters; не второй tool registry/terminal stack.
3. Одна local workspace ownership/publication authority; не отдельные lease, fencing, pointer и journal services.
4. Materialized immutable revisions и private candidates; не обязательные Git CAS, overlays или backend matrix.
5. Один structured JUnit parser с existing baseline-compatible projection; не второй verification engine.
6. Live context-provider → existing `per_role_task`; не public context field/history service.
7. Existing selection/admission/repair и artifact facades; не новый nested workflow state machine.
8. Existing private-file/lock patterns, усиленные в маленьких primitives; не generic transaction framework.

**Это не «всё уже есть».** Реально новыми остаются OS-enforced cells/host authority,
protected workspace ownership/views, process-tree terminal lifecycle, sealed publication/recovery,
trusted launch/import closure и их integrated proof. Existing interfaces дают seams, не эти гарантии.

**Важная factual correction:** current SessionManager запрещает второй session владеть workspace первого.
Desired «new session reuses old workspace» не является already-supported production lifecycle (§2.1).

## 1. Критерий сокращения

Сокращать количество независимых authorities, schemas, storage formats и implementation paths.
Не вычитать negative oracles лишь потому, что code уже содержит похожее имя.

| Класс | Что означает | Что писать в increment |
| --- | --- | --- |
| Direct reuse | Existing behavior подходит без нового subsystem | Named existing producer + regression oracle |
| Reuse seam, strengthening required | Shape/DI подходит, гарантия отсутствует | Existing producer + конкретное изменение + negative oracle |
| Genuinely new mandatory mechanism | У existing source нет нужной boundary/authority | Маленький producer, explicit owner/contract, failure oracle |
| Defer/remove | Не нужен для выбранного sequential Linux/Docker contract | Named deferred consumer/trigger; не fake completion |

Reuse не освобождает от проверки composition: source helper, вызываемый мимо нового backend,
не становится безопасным от наличия безопасного adapter где-то рядом.

## 2. Existing-code reuse: что действительно есть

### 2.1. Session/run identity и persistence — сохранить, не дублировать

**Sources:** `src/fa/session/manager.py::{SessionContext,RunContext,SessionManager}`;
`src/fa/inner_loop/session_db.py`; `src/fa/inner_loop/state.py::{SessionState,EventLog}`;
`src/fa/paths.py`.

- SessionContext уже содержит canonical workspace/DB/manifest identity; RunContext — run namespace.
- `begin_run()` создаёт private run directory и резервирует run binding в existing SQLite authority.
- EventLog пишет authoritative SQLite row и best-effort JSONL mirror; mirror не новая authority.
- SessionState уже имеет executor, worktree, artifact, transaction и session DB DI seams.
- Private roots/permissions уже имеют policy; не вводить второй state-root resolver.

**Предложение:** managed execution/view reference привязывать к этим contexts/DI,
не создавать persistent session на каждый role/test/PTY. Existing event path использовать для диагностики lifecycle;
не делать из JSONL источник lease/recovery correctness и не складывать туда raw control-plane secrets.
Execution job identity всё равно отличается от session/run ID: один run может иметь несколько jobs.

**Предел reuse:** run-ID reservation не writer lease и не fencing.
`_check_reverse_workspace_ownership()` выдаёт `workspace_already_owned` для второй session.
Это намеренно проверяется `tests/test_session_lifecycle.py::test_workspace_cannot_be_owned_by_two_sessions`.
Attach/resume same session поддержан; новая session может выбрать pre-existing **не принадлежащий другой session** workspace.

Desired cross-session reuse требует явного lifecycle disposition и regression tests.
Не выключать ownership guard и не добавлять незаметно transfer/alias registry.
Workspace-level lock нужен и при нынешнем guard: несколько runs/processes одной session не становятся одним writer автоматически.
Плану надо явно выбрать минимальный approved lifecycle change для requested reuse;
пока он не реализован, не объявлять этот target доступным и не подменять его silently attach.

### 2.2. Shell/PTY/tools — existing facade, новый enforced backend

**Sources:** `src/fa/runtime/bash_executor.py::{BashExecutor,InProcessPtyExecutor,RemoteRuntimeExecutor}`;
`src/fa/runtime/pty_pool.py`; `src/fa/runtime/server.py`;
`src/fa/inner_loop/tools/run_bash.py`; `src/fa/inner_loop/registry.py::{ToolSpec,ToolResult,ToolRegistry}`.

BashExecutor уже задаёт `run`, `send_ctrl_c`, `close`, `list_sessions`; PtyResult и tool-result projection существуют.
Registry validation/role registries не надо переписывать ради sandbox; role permission не isolation boundary.

**Предложение:** сохранить public tools/result framing и PTY machinery;
cell-backed executor получает internal managed-job/view reference через DI.
Noninteractive verification/readiness идут через ту же host lifecycle authority,
но сохраняют свои argv/result/deadline semantics — не обязаны имитировать interactive shell.
Не вводить `run_bash_secure`, второй tool registry или новую model-facing runtime schema.

**Предел reuse:** HTTP FastAPI server — execute/interact/session API, не host supervisor.
RemoteRuntimeExecutor не предоставляет approved-profile launch, ownership fencing, process-tree stop или sealing.
Можно переиспользовать его client/result patterns или server **внутри cell**, если это уменьшает dependencies;
не делать HTTP server вторым management authority и не считать runtime extra deployed по факту наличия source.

Current run_bash может перейти с executor failure/PTY timeout к local subprocess.
Protected paths должны fail closed; неопределённо исполненная команда не запускается повторно через fallback.
PTY Ctrl-C/kill session не доказывают завершение всех descendant writers.
Existing workspace-root equality guard также требует explicit canonical↔private-view mapping,
а не отключения guard ради несовпадающих paths.

**File-tool reuse:** `src/fa/inner_loop/tools/read_file.py::build_read_file_tool`,
`src/fa/inner_loop/tools/write_file.py::build_write_file_tool`,
`src/fa/inner_loop/tools/edit_file.py::build_edit_file_tool` и
`src/fa/inner_loop/profiles.py::build_registry_for_role` уже имеют workspace-root builder seams.
Сохранить их public schemas, fuzzy-edit/output framing и transaction telemetry, привязав actor к нужному view.
Current write handler пишет local Path, а Blackboard denial не kernel lease.
Просто поменять captured root недостаточно: PTY и file tools обязаны видеть один candidate,
relative telemetry остаётся canonical-project-relative, safe path handling не допускает symlink escape,
а readers используют pinned published view. Dynamic imports/helper execution подчиняются trusted-import/OS boundary,
не исключаются из audit как «всего лишь чтение файла».

**Future subagents:** сохранить existing `SubagentRunner`, spawn ToolSpec и result envelope.
`src/fa/workspace/worktree_manager.py::SharedDirWorktreeManager.create_subagent_workspace()` возвращает session root
и сам предупреждает: это **не subagent write root**. Existing artifact directories не OS/private candidate boundary.
Передавать child execution/view через existing DI; не включать scheduler, branch merge или parallel workflow orchestration сейчас.

### 2.3. Nested workflow/Q66 — existing call graph и live state

**Sources:** `src/fa/cli.py::_make_workflow_ctx_provider`;
`src/fa/inner_loop/tools/workflow_tool.py::{WorkflowInvocationContext,build_invoke_workflow_tool}`;
`src/fa/inner_loop/workflow_controller.py::{WorkflowContext,run_workflow,_run_stage,_run_adaptive_replan}`;
`src/fa/memory/context_budget.py`; `src/fa/observability/redaction.py`.

Context-provider уже читает live `state_ref`, но сейчас отдаёт path/transaction facts, не chat history.
Nested call сейчас передаёт `per_role_task={}`; `WorkflowContext.task_for()` умеет role-specific override.
Existing budgeting/redaction — substrate, не готовая Q66 initial-context policy.

**Предложение:** в момент invocation получить bounded current parent context и составить initial planner user task
через existing `per_role_task["planner"]`. Сохранить child's own system prompt/skills и public schema.
Использовать существующие context-size estimates/redactor; не строить semantic memory service.

**Не потерять:** `task_for("planner")` может снова использовать тот же override при replan.
Initial history должен быть scoped к initial dispatch; repair/replan получают distilled goal/failures/refs по R5,
а не повторный полный parent transcript. Нужен phase-aware composition на existing dispatch path,
не новый persistent flag/history database. Просто заполнить dict один раз недостаточно.

Обычные existing child logs допустимы, credential redaction остаётся.
Ни mandatory debug-body suppression, ни universal debug enablement, ни transcript-age GC не добавляются.
Control artifacts по-прежнему не превращаются в transcript dumps.

### 2.4. Verification/JUnit — один parser, но не existing bool как kill oracle

**Sources:** `src/fa/inner_loop/slice_verification.py::{capture_test_nodeids,_parse_nodeid_report,run_commands}`;
`src/fa/inner_loop/junit_nodeid_plugin.py`; existing mutation operators/overlay/provenance guard;
`src/fa/inner_loop/workflow_controller.py::{BaselineCapture,_capture_nodeids_by_slice}`.

Already present: fresh TemporaryDirectory report path, exact pytest nodeid property,
DTD/entity rejection, duplicate/missing nodeid rejection, suite-error check, baseline capture and mutation engine.
Existing slice command/test selection сохраняется; не добавлять per-contract nodeid mapping.

**Предложение:** один internal detailed report parse result: executed/pass/failure/skip/error и validation detail.
Existing baseline bool map оставляется как compatibility projection того же parser.
Kill runner использует detailed result + actual command outcome + current run/report binding.
Не делать второй XML parser, отдельный mutation baseline subsystem или generic test framework.

**Предел reuse:** сейчас skip/xfail, failure и testcase error проецируются в `False`.
Diagnostic §9 воспроизводит одинаковый map для skip, assertion failure и testcase error при нулевом suite counter.
`any(False)` не доказывает kill; ошибка testcase не становится failure от отсутствия aggregate error count.
Структурные counters, individual outcomes и command status нужно проверять совместно.
Missing/stale/malformed reports, zero executed/all-skipped и infrastructure/collection/timeout errors никогда не PROVEN.
Fresh report path — useful reuse, но не complete version/provenance authority.
JUnit parsing само по себе не доказывает честность project-controlled tests.

**Ownership scope:** local classification fix остаётся в retained I02 owning SLICE5/SLICE6 contracts;
supervised operation/revision identity integration — I03. Дополнительная clean-control baseline policy **не принята**.

### 2.5. Small file/lock primitives — reuse patterns, добавить missing guarantees

**Sources:** `src/fa/workspace_bootstrap.py::{_open_private,_exclusive_lock,_write_atomic_text}`;
`src/fa/session/manager.py::_atomic_write_json`;
`src/fa/inner_loop/workflow_artifacts.py::_write_json_atomic`;
`src/fa/inner_loop/workflow_controller.py` baseline/verification writers; `src/fa/paths.py`.

Bootstrap уже имеет private leaf open + O_NOFOLLOW и process-shared bounded flock.
Several JSON writers уже используют temp file, file fsync и replace.

**Предложение:** выделить маленькие internal protected-open/lock/durable-write primitives только для новых authorities
и непосредственно затрагиваемых callers. Existing bootstrap readiness facade/typed reason codes оставить.
Не переносить repo-wide все writers и не создавать pluggable transaction framework.

**Предел reuse:** bootstrap lock сейчас лежит в editable workspace `.fa`, защищает readiness, не весь workflow.
Новый workflow lock должен быть у trusted authority вне cell-writable tree, с canonical workspace identity.
Leaf no-follow не доказывает безопасность ancestor traversal, hardlinks или protected root.
Bounded wait не TTL и не разрешение красть living lease. Crash освобождает lock, но не обязательно убивает jobs.
Atomic JSON helper fsync'ит file, но не parent directory (§9).
Нужны appropriate directory fsync, safe unique temp creation и protected path handling;
при durability/recovery error publication останавливается, не best-effort success.

**Не объединять semantics:** Q58 same-path replacement, bootstrap no-replace install и multifile publication
имеют разные irreversible points/oracles. Shared low-level IO полезен; один универсальный `promote()` скрывает различия.
`os.replace()` не bootstrap no-clobber primitive; обычный rename может заменить existing empty directory.

### 2.6. Readiness/acquisition — reuse policy/results, не controller subprocess

**Sources:** `src/fa/cli.py::_prepare_managed_workspace`;
`src/fa/session/manager.py::{_new_session,_attach_session}`;
`src/fa/workspace_bootstrap.py::{ensure_workspace_ready,_run_process,_command_environment}`.

Readiness уже имеет fingerprints, locked repair, typed ReadyState/reason codes и telemetry.
Но session lifecycle вызывает preparer до model/tool dispatch, а `_run_process()` исполняет local subprocess:
project interpreter probes, dependency/build/hook execution нельзя объявить безопасными от env scrubbing.
Readiness facade сейчас сообщает degraded state без blocking; это не fail-closed runtime admission.

**Предложение:** сохранить reusable checks/result vocabulary, а project-code commands направить в approved cell/profile.
Boundary нужна **до первой** такой команды, не только после `begin_run()` или nested planner launch.
Existing preparer callable — reuse seam; execution routing и typed backend-unavailable admission требуют strengthening.
Не требовать наличия normal RunContext до provisioning: план должен явно учитывать operation identity на этом lifecycle edge,
без второй session DB. Backend unavailable останавливает protected execution независимо от readiness degradation policy.

Acquisition и verification используют ту же lifecycle authority, но не одинаковые network privileges.
Fixed approved acquisition sources/cache достаточны для initial scope; package hooks остаются внутри cell.
Не делать package-manager abstraction matrix, transparent egress-proxy product или dynamic privilege escalation.
Approved profile без реально нужного источника означает typed failure/clarification, не «временно сеть controller».

### 2.7. Что не является готовым revision backend

- `src/fa/inner_loop/artifacts.py::ArtifactStore` хранит tool payloads/elided outputs, не immutable workspace revisions.
  Сохранить output offload; не переименовывать этот store в snapshot/CAS authority.
- `IsolatedWorktreeManager` создаёт Git worktree от branch/HEAD; это не dirty working-tree snapshot.
  `WorktreeManagerFactory.from_flags()` в production отвергает nonshared mode.
  Не включать deferred isolated flag как замену выбранной boundary.
- SessionDatabase/Blackboard facts полезны как references/audit, но не новый источник raw project-write permission.
  FlowState/EvalReport уже различают controller observations и model judgment; сохранить facades.

## 3. Что объединить в design

### 3.1. Один local ownership/publication domain

Вместо независимых lease-manager + generation-store + revision-pointer DB + journal service:
одна небольшая protected per-workspace state directory, один lock и одна trusted coordination path.
Owner/generation, current revision и pending intent принадлежат этой authority.

**«Одна authority» не значит «один magic JSON update».** Lock FD, current manifest и durable intent могут быть разными
маленькими files: sequencing/recovery требует их разных ролей. Existing session manifest остаётся session identity,
а runtime labels — job inventory, не authoritative published revision.
Controller и supervisor не должны независимо решать, кто current writer, или брать один flock повторно в одной call chain.
Exact placement/schema планируется явно; new global control-plane DB не нужен для single-host contract.

Проверка before publication под тем же ownership domain: owner/generation, expected base revision,
sealed job/candidate identity, pending intent и completion state. Stale cell/report не публикуется после recovery.
Container inspect/approved labels можно использовать для discovery managed jobs после restart,
но это **предложение**, не проверенный deployment guarantee; неизвестные jobs не дают ownership authority.
До reconcile/stop/seal surviving jobs новый writer не получает workspace.
Не добавлять TTL lease stealing, distributed scheduler или durable task queue ради local restart.

### 3.2. Один materialized revision/view lifecycle

Начать с materialized copies/immutable revisions и private candidate, сохраняющих approved dirty tracked/untracked inputs.
Copy strategy обязана иметь defined handling symlinks, metadata, special files, excluded control state и nested boundaries;
«copytree в произвольный path» не достаточно.

Sequential workflow имеет один evolving private candidate; verification/mutation получают нужные derived views.
Reader pins immutable published revision; current manifest переключается атомарно после durable publication.
Индексы/caches не требуют нового workspace writer: хранить derived cache вне project mutation surface.

Отложить overlays, mandatory reflink, dedup CAS, Git object storage и multi-backend selection.
Optimizations можно добавить позже на measured copy/storage bottleneck без изменения contracts.
Не вводить revision age-GC/history platform. Cleanup ephemeral views после terminal jobs отдельна от published-reader retention;
pinned revision нельзя удалять. Exact safe retention/ref tracking нужен, если deletion вообще входит в initial implementation.
Raw host checkout всё ещё не обещается atomically observable; managed readers используют pinned revisions.

### 3.3. Один lifecycle для PTY, verifier и readiness

Adapters отличаются transport/result semantics, но create/inspect/cancel/terminal/seal authority одна.
Interactive shell сохраняется; opaque shell command не анализируется на «безопасные слова».
PTY timeout/transport disconnect — uncertain outcome, не reason replay.
Seal начинается после authoritative terminal barrier по всем writers; read-only export не proof отсутствия процессов.

Не строить новую terminal server реализацию, agent daemon или orchestration framework.
Не объединять Ctrl-C, process-tree stop и candidate seal в один success boolean: failure states остаются различимыми.

### 3.4. Один workflow state machine и dispatch path

Admission/selection/bootstrap, role dispatch, repair routing, PlanRef/version binding и handoff расширяют existing controller.
Q66 initial task composition — local addition здесь, не отдельный increment/service.
Stable ID/path/reference checks переиспользуются с current actual grammar; не invent generic artifact catalog.
Bootstrap filesystem install и workspace publication могут разделять safe IO, но не their commit semantics.

## 4. Candidate compact decomposition для нового I03

Это **planning recommendation**, не изменение §12.6 decision note и не assignment CT IDs.
У прежнего seven-group skeleton можно объединить runtime launch и adapter wiring;
verification/provisioning остаются integration consumers, а не ещё один execution engine.
Получается кандидат из **6 связных groups**, если briefs/CTs действительно остаются небольшими:

| Group | Объединённый deliverable | Минимальный negative oracle |
| --- | --- | --- |
| A | Trusted launches/imports + approved cell backend + existing execution adapters | Editable project FA не импортируется controller; unavailable backend выполняет zero project commands; PTY не replay'ит uncertain command |
| B | Workspace identity/lease + materialized private views/pinned readers | Same-workspace writers конфликтуют независимо от run/session labels; dirty inputs preserved; other writer cannot mutate; reader не видит evolving candidate |
| C | Terminal barrier/sealing + fenced publication/recovery + parent refresh | Surviving descendant blocks seal/publication; stale generation rejected; injected crash не делает partial current revision; Q58/bootstrap irreversible points различимы |
| D | Actual nested selection/admission/bootstrap + simple initial Q66 | Real invoke path selects/clarifies/no-clobber installs; initial provider receives current parent input; retry не получает full initial transcript |
| E | Verifier/readiness/acquisition integration + version-bound evidence | Whole call inventory routed; early provisioning command inside boundary; stale/skip/error report не PROVEN; actual PlanRef/evidence относится к executed revision |
| F | Migrated complete E2E/operator package для delivered I02+I03 | Каждый unique producer case имеет actual reviewed deployed result; skip/BLOCKED не PASS |

Groups A/E **не разрешают промежуточный unsafe fallback**: A's backend contract и E's complete consumer coverage — разные claims.
До complete coverage нельзя объявлять whole-product isolation delivered.
Grouping не сокращает process-tree lifecycle tests и не превращает E в скрытую rewrite всего workflow.
Если A/C/D требуют giant brief, split **increment**, не compress obligations ради числа slices.
Последняя group остаётся integrated acceptance реально delivered path; старый tracker/L2-eval не примешивается сюда.

## 5. Что реально убрать/отложить из initial foundation

| Не строить сейчас | Что сохраняет нужный contract |
| --- | --- |
| Execution-specific persistent sessions/history DB/public modes | Existing SessionContext/RunContext/SessionState + internal job/view ref |
| Parallel terminal implementation/second tool API | Existing PTY/result/tool facades + enforced adapter |
| Lease/fencing/journal микросервисы и distributed scheduler | One local authority/lock/protected records + explicit recovery |
| Git CAS/overlay/reflink/backend matrix | Materialized immutable revisions/private candidates |
| Per-contract nodeid mapping/new test selection grammar | Existing slice TESTS/verify grammar + detailed report classification |
| Mandatory new clean-control mutation baseline | Existing retained T0/baseline; this extra policy not adopted |
| Context field/history service/DLP/body suppression/age GC | Live bounded initial user-task composition + existing logs/redaction + distilled retry |
| Parallel subagent/workflow scheduler, branch reconciliation | Sequential owner/delegated child-view seam; future enablement has separate concurrency proof |
| Repo-wide durable-writer refactor/generic transaction framework | Small safe IO primitives for directly affected authorities |
| Package/proxy framework/unrestricted network fallback | Fixed approved profiles; hooks in cell; unavailable→fail closed |
| Old I03 tracker/per-slice loop/three-level eval | Named deferred successor with preserved capability references |

Не использовать defer table как justification stub bootstrap, fake cell, guessed PlanRef или silently ignored isolation request.

## 6. Обязательства, которые не сокращаются

- Mandatory OS boundary на всех project-code paths, включая early readiness/imports/build hooks и arbitrary PTY shell.
- Controller trusted imports для wrapper/entrypoint variants; cell не получает secrets/control state/raw daemon socket.
- Host supervisor private access/profile validation и explicit TCB/deployment assumptions.
- Exclusive workspace writer, immutable pinned readers, private candidate; no uncontrolled shared candidate mutation.
- Process-tree termination/terminal barrier, uncertain outcome без replay, sealed output до trusted publication.
- Generation/base-revision fencing, durable intent/recovery, no lost update и bootstrap no-clobber.
- Actual admission/PlanRef/version evidence, error/skip/stale reports не PROVEN; Q53(c) slice attribution остаётся.
- Q66 initial-vs-retry separation и credentials redaction без расширения logging/privacy architecture.
- Real local composition proof и final reviewed deployed I02+I03 E2E с сохранением unique producer coverage.

## 7. Plan migration: сокращение без потери obligations

1. Retained I02 ends at SLICE6, но содержит **7 sections** из-за SLICE2b; не удалять source-position work.
2. Local kill-classification change находится в retained I02 owning CT/tests, не случайно уходит в runtime increment.
3. CT96/CT97, CT95 managed-acquisition clause и CT90 nested exception имеют explicit I03 successor ownership.
4. До functional nested acquisition недоступный path сообщает unavailable до child coder/provider dispatch.
5. Reduced I02 SHIPPED possible только после формально amended retained DoD/evidence/review;
   old host-E2E gate не исчезает молча и становится incomplete I03 acceptance obligation.
6. Preserve старый I03 loop/tracker/eval outline как named deferred successor.
   Grammar «until I03 ships»/L2 VERIFIED references следуют capability, а не номеру foundation increment.
7. Ни Q59/Q62/Q63 exact dispositions, ни Q60 preferred candidate schema не ратифицируются этим audit.
   Q64 остаётся I06; Q65 existing ratification/Q66 settled public API не означают runtime proof.
8. Grouping proposal → explicit CT/producer/test/case mapping при планировании; никаких status ticks от doc edit.

## 8. Regression bank — existing tests использовать, не считать уже passed

| Existing bank | Что защищает при reuse | Что требуется добавить |
| --- | --- | --- |
| `tests/test_session_lifecycle.py`, `tests/test_session_manifest_guards.py`, `tests/test_session_db_authority.py` | Identity/run/ownership/DB facades | Approved reuse lifecycle, process-shared workflow writer fencing |
| `tests/test_pty_persistence.py`, `tests/test_pty_pool_narrowing.py`, `tests/test_run_bash_env_scrub.py`, `tests/test_run_bash_tool_projection.py` | PTY state, DI/env/output contracts | Protected-path failure/no replay, descendant cleanup, private-view mapping |
| `tests/test_runtime_server_c1.py` | Current server/result semantics (optional extra) | Actual host authority/cell deployment; current endpoint tests не substitute |
| `tests/test_slice_verification_runner.py`, `tests/test_mutation_overlay.py`, `tests/test_plan_ids.py` | Selection/runner/provenance grammar | Detailed failure/skip/error, zero/stale reports и real cell evidence binding |
| `tests/test_invoke_workflow_tool.py`, `tests/test_verify_gate_live.py`, `tests/test_workflow_global_history.py` | Real call signatures/composition/history boundaries | Initial live provider input, distilled replan, protected nested install/handoff |
| `tests/test_workspace_bootstrap.py`, `tests/test_workspace_readiness_integration.py`, `tests/test_workflow_artifacts.py` | Readiness reason codes/locks/artifact facades | Early cell execution, protected lock location, durability/crash recovery |
| `tests/test_subagent_runner.py`, `tests/test_subagent_termination_wiring.py`, `tests/test_s6_subagent_fidelity.py` | Child envelope/context/termination wiring | Future child-view delegation; no inference of parallel scheduling support |

Новые assertions должны проходить actual composition producer, не только fake executor с заявленной capability.
Existing banks здесь перечислены по source, **не перезапущены** в этом docs-only audit.

## 9. Выполненная проверка и границы evidence

1. Прочитаны roadmap, retained I02 scope/DoD/handoff, decision note и bounded source ranges перечисленных producers.
   AST/symbol inventories использованы как navigation; audit не заявляет exhaustive security certification.
2. Reverse ownership подтверждён manager source и existing named regression test (§2.1).
3. Stdlib diagnostics исполняли **actual extracted source bodies** в isolated globals, не package import с compatibility shims:
   - `_parse_nodeid_report`: skip, assertion failure и testcase error с нулевым suite counter →
     одинаковое `{"tests/test_x.py::test_x": false}`, empty detail. Это probe на loss of outcome information,
     не утверждение, что stock pytest обычно выпускает inconsistent counters.
   - `_write_json_atomic`: payload round-trip успешен; instrumented actual `os.fsync` calls → `['file']`,
     directory fsync отсутствует. Не crash/power-loss test.
   - Bootstrap `_open_private`/`_exclusive_lock`: parent держит flock, child process получает bounded timeout;
     после release reacquire успешен; leaf symlink отвергнут, target unchanged.
     Только для diagnostic wait constants уменьшены до 0.03 s/0.005 s; product source не менялся.
4. Environment: Python **3.11.2**, project targets **3.13**; `.venv`, Docker и pytest executable в текущем checkout отсутствуют.
   Full package suite, actual Docker/cgroup/host supervisor и production deployment этим шагом не проверены.
   Historical test results из ledger не переобозначены как PASS этого audit.
5. Doc checks перед commit: ledger append-only E199, unique index links, local link/source-bank existence,
   balanced fenced blocks, factual correction в primary note и `git diff --check`.
   Commit/push branch и remote SHA проверяются отдельно; этот документ не заменяет их tool evidence.

**Recommended next action:** согласовать сокращённые mechanisms/grouping и lifecycle disposition,
затем отдельно мигрировать I02/DoD/roadmap/case ownership и написать concrete I03.
В этом шаге ни эти migration edits, ни product implementation не выполнялись.
