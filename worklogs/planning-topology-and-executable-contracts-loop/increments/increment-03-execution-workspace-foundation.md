---
Increment-ID: RM-planning-topology-I03
Roadmap-ID: RM-planning-topology
status: OUTLINED
slices: 7
shipped: —
---

# INCREMENT I03: Execution/workspace foundation and integrated acceptance

**Planning state:** E230/E231 retained; E243/E244 directly repair remaining joins/IO semantics before E245 construction.
Q59 advisory/manual + EXISTING experimental suggestion injection, no required mode; Q60 delegated
source-grounded reuse design in spec §7; Q63 four states/optional commentary/no reason enum; Q74
per-stage/episode ordinary-edit checkpoints. E233 found F17/Q75; the operator explicitly selected
Q75(a) in E234: narrowly bound memory-only original completed-reply replay, secret-free journal,
no fresh authority/re-execution/reconstruction. The stop is lifted; SLICE1 implementation resumes. OUTLINED
is deliberately unchanged: plan finalization assigns no implementation tick, READY automation,
live result or deployment authorization. All47 construction steps and final acceptance remain open.

**Depends on:** retained I02 local implementation/checks and plan-versus-diff review; no restored
I02 deployed-host, broad independent-review or inherited-baseline acceptance prerequisite.
**E223 final-acceptance ownership:** all four transferred obligations are unfinished under SLICE6:
deployed functional/source-to-behaviour verification; environment/readiness and inherited baseline
acceptance review; broad independent implementation/evidence review; integrated E2E/deployment signoff.
The E231 decisions finalize the plan, not runtime delivery or either increment’s final acceptance.
**Operator acceptance-scope clarification (2026-10-23):** final I03 live-host E2E acceptance covers
all changes in I01, I02, and I03 for this project. E223’s original I02+I03 transfer is a minimum
lineage, not a limit on the final gate. The package now has three planned I01-origin case IDs mapping
all 42 I01 CTs and seven in-scope deferred obligations; every I01 row remains NOT RUN. Final acceptance
stays open until the approved host evidence is collected and reviewed.
**Shippable when:** all project execution uses mandatory Linux/Docker cells, one protected workspace
writer owns coherent private views/pinned readers, terminal sealing/fenced publication/recovery
are proved, real nested selection/bootstrap/context works, and every unique required I01–I03
producer has reviewed deployed-main acceptance. PTY remains. Backend unavailable fails closed in
both observe/enforce and for every role. Partial backend success is not whole-product isolation.

**Normative detail:** [execution/workspace spec](../notes/i03-execution-workspace-spec-2026-10-15.md).
**Evidence/review:** [adversarial review](../notes/i02-i03-adversarial-review-2026-10-15.md).
**Lineage:** [migration bank](../notes/i02-to-i03-scope-migration-2026-10-15.md),
[decisions](../notes/execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md),
[reuse audit](../notes/execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md).
New module/function/test names below are **planned interfaces**, not claims about complete code.
E234 adds only immutable NamespaceRef/ViewRef, closed operation/purpose names, four grant-result
shapes, canonical input hashing and a bounded completed-grant-reply cache in types.py/supervisor.py.
These are C0/C3 foundations, NOT a wire decoder, journal, dispatcher, issuer, client or service.
E235 adds the complete closed wire/receipt codec and72 C0/C3 cases; all19 operation payload/result
shapes are covered, including real socketpair framing. No authority/service activation.
E236 adds fixed-profile rendering, a single-attempt authenticated-UDS client, receipt binding, all
four managed PTY methods and a cell-local framed PTY worker. C0/C3 only; no factory activation.
E237 adds protected operation journal, one-claim/cancel/start guards, startup singleton scope,
absolute RPC deadline and per-connection kernel-peer dispatcher with REQUIRED authority/backend
callbacks. Q75 covers successful non-grant replies too. C0/C3, not a running production service.
E238 prepares the frozen noneditable Docker install + pre-site gate and real installed CLI C2/C3
fixtures (source-byte matched, no mocked CLI); profile/session mode checked before callbacks.
E239 records the operator's explicit Q76(a) selection: protected admitted PlanRef + source recheck,
ordinary no-active-workflow null permitted, formal evidence requires actual plan; no new workflow
mode. F18 closed admission/context/receipt checks are constructed: owning347PASS/restored347PASS,
six full347kills4/6/3/1/2/1, broader768PASS; actual protected loader/authority/controller persistence
integration remains unproved. No guessed hash, C1/service proof or activation.
E240 corrects F19: fixed noninteractive one-shot worker preserves determinate command status;
interactive worker remains persistent. Local361PASS/restored361PASS, three full-bank kills1/1/8;
broader782PASS. Build toward the complete target contracts, not today's helpers. Existing verification
schedule below already defers required host acceptance without blocking dependency-order coding.
STEP1–4 remain unchecked; producer helpers exist, but C1 factory/authority/kernel wiring is uncredited.
E241 constructs private authenticated Docker create/start/owned-inspect transport + durable one-use
create claim and required injected resource validator. Start ACK is only a CID, not an exec result;
non-exited observations cannot turn provisional exit0 into success. No per-command new-cell reuse,
receipt issuance, real authority or C1/host proof. Actual backend/episode/attach/lifecycle and service
wiring remain target work. Local owning415PASS/restored415PASS, ten full-bank kills2/6/2/1/3/2/2/1/7/1;
no STEP/acceptance ticks or changed verification schedule.
E242 adds fixed live-only upgraded Docker attach, shared closed cell codec and a concurrent private
worker client (one RUN plus control) with bounded framing/deadlines, correlated replies and poisoned
stream uncertainty without reconnect/resend. Actual local PTY/worker transport tests are C0/C3, not
Docker/kernel/C1 acceptance. Protected episode registry, durable per-command backend/lifecycle,
actual authority and service/controller integration still required; all35STEPS remain unchecked.

E243 closes the short-control-RPC/long-command reply defect and makes remaining SLICE1/2 composition
executable in spec §§2.2/4.2: one authority/admission gate, existing journal per command, live-only
episode ownership, same-view read/search and safe SessionManager provisioning/cleanup. Component
repair is not complete backend/authority delivery; all35STEPS/four final duties remain unfinished.

E244 docs-first checkpoint `a7ba6d5` precedes E245 source. E245 constructs internal
`execution/view_io.py`: pinned FD/no-follow text IO, private staging/no-clobber parents, expected-SHA
writes, safe cell modes/UIDs and explicit uncertainty. Real-FS C0/C3 bank93/restored93;17 whole-bank
assertion kills, exact518 Python/build/lock hashes; broader1001PASS, static/Pyrefly PASS. See
[component evidence](../notes/evidence/i03-e245/rooted-io.json.gz). This is the STEP1 building block,
NOT WorkspaceAuthority/admission/materialization, actual public tool/PTY joins or CT101–103 closure.
All35STEPS/four final duties stay unchecked. Next: implement the one actual authority, not more
standalone wrappers or a permissive service. Required host/full-path acceptance remains final SLICE6.

## Closure state, one row per step (audit 2026-10-31, tree `200d588`)

**Why no box is ticked — and why that is not negligence.** A step is ticked only when its own `exit:` clause
has been *reproduced*, and the plan's own rule forbids ticking on a green-looking tree (E288 is the precedent:
572 green tests, zero production callers). This sandbox has no 3.13 interpreter, no pytest collection for
these banks and no Docker, so no exit clause can be reproduced here — including the local ones. That is the
first reason the boxes are empty. The second is structural, and it is the one worth acting on:

**The managed subsystem still has no production consumer.** `grep -rn "from fa.execution" src/fa
--include=*.py | grep -v "^src/fa/execution/"` is **empty**. Nothing outside the package imports it, so
SLICE1–3 build a real authority, real views, a real supervisor — and the command the operator actually runs
never reaches them: `cli._build_pty_pool` (`:1923`) still builds a host `PtyPool` and falls back to a
stateless pool on failure (`:1950`), `slice_verification._run_one` still calls `subprocess.run` (`:334`), and
`CliSessionManager` is built without a provisioner (`_session_manager_for_args`, `cli.py:247`). Slices 1–3
are therefore **components, not delivery**, and SLICE4 STEP2 is the hinge the whole increment turns on.

**Legend.** `LOCAL` — code and bank exist, exit is reproducible without a host, only the run is missing.
`PARTIAL` — named parts of the step landed, named parts did not. `HOST` — built, but the exit is a host fact.
`OPEN` — no code yet. `PLANNED` — SLICE7: written and reviewed, not started.

| step | state | what exists (verified in the tree) | what the exit still needs | waits on |
| --- | --- | --- | --- | --- |
| S1P1 | HOST | codec/client/protocol, E251 peer+deadline seam, `tests/test_execution_client.py` | installed-module `fa --help` under poisoned CWD/PYTHONPATH; over-budget reply observed once | installed wheel |
| S1P2 | HOST | `CellBackend` (E258), `tests/test_execution_backend.py`, cancel/restart seam | one cell/two records; two one-shot cells; lock expiry on a real daemon | Docker |
| S1P3 | PARTIAL | route table + socket owner + `main` (E277), receipts (E279), `pty_control` (E280), all 19 routes incl. `handoff` (E283) | install/image/entrypoint mounts applied atomically with the cutover; `register{create:true}` owner; disposable-host boot | S4P2, host |
| S1P4 | OPEN | — | CT98–CT100 full-path mutation outcomes and cost on the real profile/image/kernel | S4P2, host |
| S2P1 | LOCAL | existing-root registration/R0/writer generation (E253) | two-OS-process race reproduced; denied/stale admissions produce no effect | run |
| S2P2 | LOCAL | immutable reader pins, rooted reads, release (E255) | pinned-reader matrix reproduced | run |
| S2P3 | LOCAL | five view purposes, rooted IO (E256), admission/drain semantics (E257) | view matrix + quiesce-before-R0 reproduced | run |
| S2P4 | PARTIAL | `workspace_io=` port plumbed through `profiles.py:204,343,357,364` and `tools/__init__.py`; the managed implementation now exists — `ClientWorkspacePort` over the wire (E308) | production must pass it (today it passes `None`) and the host fallbacks must go | S4P2 |
| S2P5 | LOCAL | contention/read-pin/no-replay semantics | matrix reproduced | run |
| S2P6 | PARTIAL | `HANDOFF` authority body + service route (E283), `_handoff_owner` | controller leg: drain/suspend, one allocation, send, dispatch only after ack | S4P2 |
| S3P1 | PARTIAL | terminal barrier (E266), immutable export/seal (E267), checkpoint policy + bank (E284) | `tests/integration/test_publication_recovery.py` (directory absent, so the fence exits 4); the stage-loop call site | S4P2, host |
| S3P2 | LOCAL | intent/current/projection, `_closed_candidate_reader:3464`, `_plan_prepare:3521` (E269) | pinned-reader/stale/fault matrix reproduced | run |
| S3P3 | PARTIAL | bundle renderer + `RENAME_NOREPLACE` install (E271), plan replacement core (E273) | controller leg onto `publish_candidate_plan` with the host writer deleted in the same change | SLICE7 |
| S3P4 | PARTIAL | forward recovery hooked into `_load` (`:1099`, `_recover_intent:4519`) (E276) | kernel-observed matrix, kills inside recovery, fsync-unsupported/EIO, crash vs power-loss labels | host |
| S3P5 | PARTIAL | 17/17 producer mutants over the real authority (E276) | full declared-path kills on the approved filesystem | host |
| S4P1 | PARTIAL | inventory coverage complete at `969fa06`; the note itself says `State: OPEN`, no row closed | close each row with source line, caller and nodeid | nothing |
| S4P2 | PARTIAL | **STEP2a done (E308); STEP2b/1 done (E309)** — the commit `publish_stage` (stop→seal→publish) with bank `test_execution_client_stage.py` (11 tests; 8/8 preliminary mutants require call-phase verification, E310);  `ClientWorkspacePort` + `client.open_view`/`stop_view` + `ManagedExecution` verbs, bank `test_execution_client_port.py` (22 tests, 15/15 mutants); managed bash supplier without host fallback (E315; 9 tests, 8/8 mutants); provisioner injected (`cli.py:280`); plan publisher supplied | **STEP2b, the cutover:** `_cmd_run` → `run_stage_with_plan_write_boundary` → `_cmd_run_inner`, `workspace_io` in production, fail-open readiness removed, bash through `ManagedBashExecutor`; nested return/handoff **Q102=A supplier done (E313), controller integration open** | S4P1 (oracles), Q102 controller integration |
| S4P3 | OPEN | `_run_one` still `subprocess.run` (`slice_verification.py:334`); no `_run_managed_command` | pinned verification scratch/receipts/report parsing through managed `exec` | S4P2 |
| S4P4 | OPEN | — | the `execution_host` C1 closure matrix | S4P2, host |
| S4P5 | OPEN | — | CT97/CT110/CT111 full-path kills | S4P2, host |
| S5P1 | OPEN | no `tests/test_managed_acquisition.py`, no spec §7 v2 fixtures | fixtures + v1 compatibility and selection-vs-bootstrap tests | nothing |
| S5P2 | PARTIAL | authority/route downward (E283) and Q102 return supplier (E313); `_child_run_context` (`workflow_tool.py:387`) | controller handoff request, suspension/drain, dispatch after ack, parent resume | S4P2, S5P1 |
| S5P3 | OPEN | — | selection/clarification + controller-rendered no-clobber bundle | S5P2 |
| S5P4 | OPEN | — | live current-message provider, bounded initial task, retry/replan split | S5P2 |
| S5P5 | OPEN | — | outer `drive_session`→`invoke`→child→`_cmd_run` C1 | S5P2–P4, host |
| S5P6 | OPEN | — | CT96/CT108/CT109 full-path mutation outcomes | S5P5 |
| S6P1 | LOCAL | `e2e/I03/live-result.schema.json`, `tests/test_e2e_artifact_contract.py` | four-state conformance reproduced | run |
| S6P2 | LOCAL | `e2e/README.md`, `e2e/I03/live-verification.md` (35 I03 case ids) | index/status tests reproduced | run |
| S6P3 | LOCAL | `e2e/I03/producer-coverage.json`, `producer-baseline.json`, `scripts/check_execution_e2e_coverage.py` (green: 125 producers, 89+35 cases) | removal-of-one-unique-key test reproduced | run |
| S6P4 | LOCAL | `e2e/I03/implementation-handoffs.md` carries the CT113/Q85 split (5 references) | reviewed handoff reproduced | run |
| S6P5 | OPEN | no host run sheet | needs actual deployment/workspace facts | host |
| S6P6 | **LOCAL-CLOSED** | E287 placed E223 roles in all five required skill surfaces; E364 reproduces role/READY + artifact + delivery bank **37 passed** and 5/5 strict section-deletion mutants | actual E223 host duties and independent review remain open in S6P5/S6P7–10 | SLICE7 STEP1 |
| S6P7 | OPEN | — | independent manual review before fixtures | S4, S5 |
| S6P8 | OPEN | `e2e/I03/fixtures/` absent | reviewed bounded fixtures | S6P7 |
| S6P9 | PARTIAL | coverage script green, every producer key mapped | each producer mapped to a deployed-behaviour oracle | S6P8, host |
| S6P10 | OPEN | — | local package conformance + every `execution_host` suite + 18 kills + release gates | everything, host |
| S7P1 | **LOCAL-CLOSED** | `tests/test_delivery_law_conformance.py` (seven files, one token list each, two damage tests per surface) | exit reproduced: 8 passed, two kill-checks bite, `test_skill_conformance.py` unchanged and green (E303) | — |
| S7P2 | **LOCAL-CLOSED** | `_require_managed_publisher` (`workflow_controller.py`, called before the attempt is reserved), `publisher=` threaded into `_run_admission_repair`, `_promote_validated_plan(source, validated, *, publisher)` with no `publisher is None` branch, rule in `ADMISSION_RULES["promotion"]` | exit reproduced: CT115 test (BLOCKED, one diagnostic, no `.fa/admission`, canonical bytes intact) + seam control, 6 mutants killed (E299) | the valid-plan control on an unmanaged run is a host re-run (`baseline-unavailable` here) |
| S7P3 | **LOCAL-CLOSED** | `retain_plan_draft` + `_read_private` (`plan_promotion.py`), `_retain_rejected_draft` wrapping the promotion call (`workflow_controller.py`), `tests/test_plan_candidate_retention.py` | exit reproduced: 8 passed (digest name, success-path control, dedup, corruption, path id, deadline), 7 mutants killed (E300) | CT120 consumes the deterministic name; no host re-run needed |
| S7P4 | **LOCAL-CLOSED** | nullable `CREATE_VIEW.base_revision` (`protocol.py:106`), `already_published` (`:159`), plan-bound cross-field rule (`:385`), journal compat row | exit reproduced in E289 and unblocked by STEP5 (E291); box ticked in E298 | — |
| S7P5 | **LOCAL-CLOSED** | `_already_published` (`workspace.py:3533`), patch semantics in `_closed_candidate_reader`, `already_published` in `_PUBLISH_REPLY`/`PublishResult` | exit reproduced: publication + recovery banks green, 2 mutants killed | host re-runs are SLICE6 STEP5's, not this step's |
| S7P6 | **LOCAL-CLOSED** | `GrantReply.to_wire_capability` (`types.py`), `request(grant=...)` (`client.py:120`), `_grant()` conversion | exit reproduced: client bank 191 green, 3 mutants killed, `test_execution_grants` grep = 0 | — |
| S7P7 | **LOCAL-CLOSED** | `ExecutionClient.publish_plan` + `PlanPublication` (`client.py:195-300`), `ExecutionClientPlanPublisher` deleted, null-base rule in `_authorize_operation` | exit reproduced: client 197, service+client 223, 1341/1 across the 29 banks, 6 mutants killed (E294) | host re-runs are SLICE6 STEP5's |
| S7P8 | **LOCAL-CLOSED** | `execution/composition.py` (three types, one `ExecutionClient(` site), `load_execution_config`, `_cmd_workflow` wiring with `plan_publisher=` and a releasing `finally` | exit reproduced: composition 9 + config 26, 1350/1 across the execution+workspace banks, 15 mutants killed (E295) | STEP9 owns the chat-path join |
| S7P9 | **LOCAL-CLOSED** | `ClientWorkspaceProvisioner` + `client_workspace_provisioner`, relaxed `tree_sha256`, shared `ERROR_CODES`, `cli._session_manager_for_args` injection | exit reproduced: composition 12 + provisioning 10, 1526/1 across the banks, 8 mutants killed (E297) | S4P2 owns the rest of the cutover |
| S7P10 | **LOCAL-CLOSED** | `CANDIDATE_SCOPE` = plan identity only (`protocol.py:69`), `_candidate_scope`/ `_candidate_buffer` bound to the pinned plan (`workspace.py:285`, `:2249`), `_view_record_compat` tolerant reader (`:538`), client writes under the plan path (`client.py:224`)
| S7P11 | **LOCAL-CLOSED** | `test_the_workflow_root_reaches_promotion`, the refusal test plus its strict `xfail` twin, E300's retention bank | exit reproduced: EDGE drives a real publication through `_promote_validated_plan`, xfail measured (refusal passes, success fails), coverage script green, counts reproduce (E302) | handoff sections for I03-LIVE-25/26/S08 stay SLICE6 STEP4's |

**Counts from the table:** 9 `LOCAL`, 11 `PARTIAL`, 2 `HOST`, 14 `OPEN`, 0 `PLANNED`, 11 `LOCAL-CLOSED` = 47 steps, of
which **11 are closed** (`S7P2` E299, `S7P3` E300, `S7P4` E298, `S7P5` E291, `S7P6` E293, `S7P7` E294, `S7P8` E295, `S7P9` E297, `S7P10` E301, `S7P11` E302). **SLICE7 is now fully `LOCAL-CLOSED`**: no `PLANNED` row remains in it. The audit's count as written on 2026-10-31 was 11 `PLANNED` and zero
ticks; both changed because exit clauses were reproduced, not because `workspace.py` exists.

**Slice verification pass (2026-11-01, E306), after Q98/Q100 changed three of its contracts.** Every invariant
CT114–CT121 re-checked against the tree rather than the record: CT114 eight banks green on all six surfaces; CT115's
`_require_managed_publisher` sits before the attempt is reserved (`workflow_controller.py:2586`) and refuses with
`managed-execution-absent` (`:2293`); CT116 still has exactly one `ExecutionClient(` construction site
(`composition.py`) with the deleted adapter absent; CT117's wire half carries `already_published` with the nullable
`base_revision` and the plan-bound cross-field rule; CT118/CT119 hold under Q100's one-slot rewrite; CT120's
`candidate_path` is absent from `src`; CT121's preservation banks are **455 passed**. Two records were corrected, not
the code: `session_summary` now carries the stage verdict (Q98) and `_retain_rejected_draft` keeps one slot (Q100).

**The dependency order, said once.** Slice numbers are *authorship* order, not execution order: SLICE7 was
written after SLICE6 but depends only on SLICE3, and SLICE4–6 consume the composition it builds, which is why
`DEPS` already reads `SLICE4: SLICE3, SLICE7`, `SLICE5: SLICE4, SLICE7`, `SLICE6: SLICE5, SLICE7`. The
execution order is these five waves, monotone, and every edge above is inside a wave boundary:

1. **W0 — local, unblocked now.** SLICE7 entirely (it is the missing supplier), S4P1's inventory rows, and
   S6P6's documentation half.
2. **W1 — the cutover, local.** S4P2 (with SLICE7's client and provisioner), S2P4's production wiring, S3P3's
   controller leg; and the `LOCAL` exits of S2P1/S2P2/S2P3/S2P5/S3P2/S6P1–S6P4 reproduced in the same pass,
   because they are the banks the cutover must not break.
3. **W2 — downstream, local.** S4P3, S5P1, S5P2, S5P3.
4. **W3 — host C1.** S1P1–S1P4, S2P6's exit, S3P1(c), S3P4, S3P5, S4P4, S4P5, S5P4–S5P6.
5. **W4 — acceptance.** S6P5, S6P7, S6P8, S6P9, S6P10 and every `NOT RUN` live row.

**Сверка волн на 2026-11-01 (E317; статусы не закрываются этой записью).** W0: SLICE7 —
11/11 `LOCAL-CLOSED`, но S4P1 остаётся `PARTIAL` (строки inventory без закрытых source/caller/nodeid),
S6P6 — `LOCAL-CLOSED` по источникам E287 и воспроизведённому exit E364; реальные
приёмочные обязанности E223 открыты. Поэтому весь W0 всё ещё не закрыт из-за S4P1.
W1: S4P2/STEP2b — в работе: порт, stage publication, return-handoff и bash — поставщики;
фабрики ролей получили промежуточную managed-привязку (E317), но production cutover отсутствует.
В частности, search/reach пока не исполняются в production cell (§4.2): при bound
`workspace_io` оба инструмента fail-closed до host index holder/обхода (E365–E366),
без претензии на поиск или parity. Legacy host режим оставлен. Реальный cell supplier,
расширенный receipt/replay и host proof остаются открыты. Q108 (E367) — STOP:
закрытый wire/receipt v1 не различает helper и не передаёт большие результаты;
нужно согласовать версионирование либо продолжить поиск без изменения контракта.
Незавершённый supplier E318: symlink-контрпример Q104 закрыт в локальном memory-прототипе (E321); Q105 принят —
одноразовый memory-index вместо scratch DB (E323), цена холодной перестройки требует host-замеров.
Cell PTY retention исправлен локально (E324), но facade ещё не подключён: Q106=A принят,
созданы ограниченные frame/JSON/attach поставщики для расширенного транспорта (E325–E330),
request-bound budget общего worker reader проверен локально (E338–E339),
опциональный счётчик сохранённых public replay bytes — локально (E340–E341),
ASCII-safe envelope исправлен после tmux-контрпримера (E331–E332), строгий
parser cell helper переиспользует общий codec (E343–E344), opt-in
per-call PTY capture supplier проверен локально (E333–E334); bounded pexpect и
fail-closed отказ reuse после неудачного восстановления проверены локально (E335–E336).
Managed edit теперь не записывает неполный snapshot; неизвестная запись не называется
отказом и не предлагается к retry (E346–E348). Оба port adapter поддерживают
byte offset READ_FILE и проверены на отдельные окна через UDS (E360–E361), но
line-window consumer, SHA reconciliation и resource/deadline доказательства открыты.
Managed mutation guard при активном или ошибочно недоступном blackboard теперь
отказывает до host metadata и WRITE (E362–E363); при этом настоящего поставщика
view-bound version stamps ещё нет, поэтому полноценные write/edit при включённом
blackboard и production cutover не готовы.
Legacy PTY `strip()`/ANSI/CR и маркеры не дают byte-exact произвольный stdout;
геометрия 80 и много коротких строк приводят к timeout из-за scrollback (E337);
`pipe-pane` сохраняет stream, но его очередь без потребителя растит RSS tmux (E342),
общая память tmux/процессов и целевой host не доказаны. EXEC, journal и
replay-cache ещё не подключены,
контекстный риск отдельно открыт; host subagent временно исключён,
и включение реестра в production запрещено до безопасного cell-local поиска и Q97-паритета. Остаются S2P4,
S3P3 и регрессионные LOCAL exits перечисленные выше. W2–W4 не пройдены; Q102 orchestration
и оба сценария factory должны подтверждаться там, где указано в таблице волн. После I03 и его
host-приёмки — отдельный read-only наблюдатель из общего roadmap, не расширение I03. Статические
полные type gates пока не закрыты: E317 фиксирует ранее существовавшие ошибки;
штатная локальная среда Python 3.13.16 с FTS5 восстановлена (E345), но это не host gate.
Полный локальный suite: 6832 passed / 10 failed / 14 skipped / 4 xfailed, exit 1
(E351, после него одна ошибка authoring адресована targeted проверкой); Q107=A по
внутреннему транспорту принят оператором (E359), но механизм ещё не доказан/не
включён; Q97/STEP2b и Q103 не закрыты.

**Проект дополнительной сверки перед деплоем (E357–E358; не закрывает STEP).**
План и подтверждённые local probes: [композиция и batch foundation](../notes/i03-composition-and-batch-foundation-plan-2026-11-01.md).
Порядок Q97/STEP2b → Q103 не меняется; Q107=A принят в работу (E359). Предлагается в существующих
SLICE/exit до production принять проверку повторного dispatch, честной
неопределённости/terminality, переписанных хуками вызовов и уникальности/корреляции
ID, а также фактического восстановления истории и ограничений результата.
Если дефект препятствует безопасному cutover, остановить включение до безопасного
prerequisite; при несовместимости exit или новом контрактном выборе — Q# и стоп.
Это проект конкретизации тестирования, не новые CT/STEP и не подтверждение закрытия.
Отдельный legacy I-65 остаётся open; managed supplier и batch fallback — разные пути.

**Why the numbers are not rewritten.** Renumbering slices would move every `SLICEn STEPm` reference — the
`DEPS` graph, `plan_ids._SLICE_CEILING`, the ledger entries, code comments that cite a slice, and the E2E case
ids — for zero behavioural gain, which is the same argument E290.1 used against cosmetic renames. What was
missing was not different numbers but this table: with it, "3 → 7 → 4 → 5 → 6" is a footnote rather than a
puzzle. If the operator prefers renumbering anyway, it is a mechanical pass over 47 step ids and seven `DEPS`
lines, and it should be done once, after W1, so the rewrite is not repeated.

## Grounding, sequence and scope discipline

- Current `run_bash` and `_build_pty_pool` deliberately fall back to host subprocess; SubagentRunner,
  readiness, verifier and Git helpers execute independently. Enforcing only one shell adapter leaks.
- Existing SessionManager rejects second-session reuse; begin_run already reserves unique run/DB
  namespace. I02 `_child_run_context` ALREADY allocates valid distinct child contexts for non-coder
  delegation; extend it for managed acquisition, never duplicate allocation or regress Q70.
- Existing FastAPI server is an optional PTY transport, not supervisor; timeout/identity/lifecycle
  fields and descendant barrier are incomplete. No standalone server-completion milestone.
- Materialized snapshots, one local authority and fixed profiles suffice. No overlay/CAS backend
  matrix, lease service, distributed scheduler, advanced logging/GC or parallel orchestration.
- Sequence is **A→B→C→E→D→F** from the migration bank: whole execution integration (SLICE4) comes
  before nested composition (SLICE5), preventing a nested proof over an unsafe old prologue.
- Do not expose production managed execution until SLICE1–SLICE4 closure. Intermediate commits
  confer no safe deployment claim; do not keep an unsafe permissive backend as a compatibility mode.
- New-session/old-workspace reuse, private Git metadata/history limitations, conservative copy caps
  and filesystem support are explicit contracts in spec §§2–5, not already-supported guarantees.


## E230 trajectory and execution prerequisites (plan review, not implementation)

**Mid-roadmap target:** on the intended Ubuntu/Docker main deployment, execute a real explicit-plan
workflow AND ordinary outer chat→invoke→managed child workflow, with actual provider requests,
useful source edits/tests, admission/T0/verification/actual eval and persisted terminal evidence.
This increment is sufficient in scope for that CURRENT whole-plan system only after its
mechanics and final host acceptance are complete. It does not deliver per-slice scheduling, automatic
STEP/CT tracking or L2 VERIFIED. Those remain the named deferred successor; do not advertise that
broader roadmap loop as live-tested. I01 remains active pending its own disposition, not auto-closed.

**Source truth:** E243 reviews `e736082` (E242); `1132eee`/I02 E229 is historical retained I02 evidence,
not the current execution implementation. The original 17 FUNCTIONAL IDs remain; new private interfaces are obligations to implement/test, not existing-code assertions.
Spec §§2.1–2.2/4.1–4.2/5.1/6.1/7.1/9.1 are part of every affected STEP's contract, including error/restart
paths. All runtime/host boxes remain unchecked. Do not run deployment during plan finalization.

**Verification schedule:** design the per-slice unit/kernel oracles with each slice. Ordinary unit
checks can run during construction; local disposable Docker integration may run where available.
The `FA_REQUIRE_EXECUTION_HOST=1` commands and full declared-path kills are REQUIRED release proof,
not permission to exercise the production main host before final SLICE6 STEP7 review/STEP10 approval.
If there is no approved disposable Docker host earlier, record those checks NOT RUN/BLOCKED, never
PASS or a narrowed unit-only kill. Coding may progress in dependency order; no slice/product safety
acceptance or production enablement follows until all accumulated required checks pass at SLICE6.
Final project-scoped E2E fixtures/helpers are different from local tests/integration; STEP7 review precedes their
implementation, followed by review of actual helper code before first main-host execution.

**Deterministic scheduling:** all wire/state/type validation precedes launch. Acquire one owner,
then open views through that authority; stage prologue/provisioning is inside the boundary too.
A workflow deadline is one absolute monotonic budget across admission/provider/stage transitions,
exec and terminal barriers. Each request uses min(configured operation limit, remaining budget);
none may start after expiry. Operation elapsed times are supervisor observations, not caller clocks.
Timeout returns unsuccessful/unknown and retains fencing until terminality. Best-effort eval after
coder still obeys Q55/Q56/Q73 and may use only a safely sealed source plus explicit uncertainty.

## E246 — verified SLICE1 next menu (437ee25, before new implementation)

**SLICE1 is NOT shipped.** E242/e736082 and E245 are construction checkpoints, not completed
CT98–CT100a. Every SLICE1 STEP remains unchecked; test totals do not establish a production join.

| Obligation | Source-verified status at437ee25 | Next required work |
|---|---|---|
| STEP1 / CT98, CT100 seams | Installed entry/codec/client exist. client.py127–129 maps every ERROR to rejection, including unknown/unavailable. | FIRST repair typed ERROR handling through all four BashExecutor methods; assert original request identity/no resend. Retain installed-entry/deadline/receipt checks. |
| STEP2 / CT99–100 | backend.py/CellBackend absent; docker.py396–503 only creates/inspects/attaches. No stop/kill/control leg, exclusive episode map, reused-command owner or restart reconciliation. | NEXT owned Docker stop/kill/observation primitives; then actual CellBackend episode/per-command dispatch/cancel/restart, with the one real WorkspaceAuthority admission/drain dependency. No fake grant issuer. |
| STEP3 / CT98–99 | supervisor.py225–234 accepts callbacks; file ends after serve_connection, no build_supervisor/main/listener/config/install. scripts/fa59 and fa-update.sh839–840 retain legacy imports. | Compose actual authority/backend and closed handlers; prepare service/profile/config. Complete publication-dependent factory in SLICE3 and caller/mount activation atomically in SLICE4, not early. |
| STEP4 / CT100a, release proof | Profile rendering is not approved host facts; tests/integration/test_execution_boundary.py absent. No actual Docker/cgroup/full-path proof supplied. | Implement required integration suite as composition becomes available; execute non-skipped actual host/full-path evidence at final SLICE6. NOT an intervening approval/deployment prerequisite. |

Proceed in this order, not another standalone rooted-IO helper. Cross-slice authority construction
is a necessary dependency of the SLICE1 backend, not a reason to claim SLICE1 complete first.
Existing four final duties, Q59/Q75/Q76 and35 unchecked STEPS remain unchanged.

## E247 — first menu repair implemented, SLICE1 still NOT shipped

E247 closes only the first E246 menu item: existing client ERROR taxonomy, not SLICE1 delivery.
`client.py` now preserves closed uncertainty codes/original-or-supplied operation references and
backend-unavailable metadata across run/INTERRUPT/CLOSE/LIST, with fixed sanitized messages and no
resend. Existing exception constructors/timeout subtype remain compatible; no wire/schema change.
TEST-EDITS: `tests/test_execution_client.py` fixture gains optional error metadata; all old defaults
and assertions retained.142 new cases cover15 codes ×4methods ×2retryable, supplied references and
constructor/closed-bank compatibility. Before repair:61 assertion failures/80pass in141 selected.
Full owning14-module bank623PASS43.09s → six whole623-bank assertion-only kills48/12/36/32/4/141 →
restored623PASS42.15s; all setup/teardown pass, no skips/warnings/collection/runtime/infra credit.
Exact597 tracked non-knowledge/worklogs hashes restored. Ruff/format26PASS, Mypy26/183PASS,
configured+clean-path Pyrefly0errors (existing141suppressed/50warnings); broader27modules1143PASS54.92s,
all phases clean. Local Python3.13.16/frozen tooling, not host/deployment/full just-check acceptance.
Evidence `notes/evidence/i03-e247/typed-errors.json.gz` includes snapshots, mutations, raw phases,
pre-code failures, runners and toolchain provenance; 795957bytes SHA256d85358b63274ce97cbb510b6ded8445667c8bdf39cc1e8d424984d1a43db8f63.
NEXT remains owned Docker termination/observation, then actual CellBackend–WorkspaceAuthority and
factory/caller composition in existing dependency order. All35STEPS/four final duties stay unchecked;
Q59/Q75/Q76/final-SLICE6 host/full-path proof unchanged. No fake authority or early-host gate.

## E248 — next native lifecycle leg clarified before implementation

E247 closed the client taxonomy defect only. NEXT extend existing DockerCells/Engine with owned
fixed-SIGKILL force-stop and independent same-CID observation per spec§2.2. Persist original creation
cancel intent before daemon contact; never equate ACK/409/404 with death or release, never replay
RUN/create/start. No signal/grace configuration or new service/authority/history. The whole STEP2
and actual CellBackend–WorkspaceAuthority join remain open, including per-command cancellation,
completed-creation/live-cell startup discovery and actual descendant/cgroup barrier. Final host/
full-path proof remains SLICE6; no intervening approval gate or completion ticks.

## E249 — native lifecycle leg implemented; backend–authority NEXT

E249 implements the existing E248 native force-stop contract in DockerCells/Engine only.
Original creation namespace/input binding → durable cancel intent → owned inspect → one fixed
full-CID SIGKILL → independent SAME-CID observation. Already-exited needs only fresh inspect;
409 still observes;404/lost/malformed replies stay unavailable/uncertain, never terminal receipts.
No create/start/RUN/reconnect/resend, no signal/grace setting, no result rewrite or lease release.
Recheck the one absolute deadline after journal lookup and at each native HTTP leg. A completed
creation command's still-live cell is stoppable without replacing its original result.
TEST-EDITS:61 appended real-journal/literal-UDS C0/C3 cases; old Docker tests are an exact byte prefix.
Final whole14-module bank684PASS42.05s → nine whole684-bank assertion-only kills48/7/4/32/1/1/1/1/3 →
restored684PASS42.35s; exact597 tracked non-knowledge/worklogs hashes, clean setup/teardown,
no skips/warnings/collection/runtime/infra credit. Ruff/format26PASS; Mypy26/183PASS; configured+
clean-path Pyrefly0errors (existing141suppressed/50warnings). Broader27modules1204PASS54.79s,
all phases clean. First invalid DONE-without-CID fixture and two overly restrictive proof-checker
rejections retained, not relabelled or sensitivity credit. No old assertion/suppression/dependency change.
Evidence `notes/evidence/i03-e249/owned-stop.json.gz` contains source snapshots, raw phases/runners,
restoration, rejected diagnostics and full hash-verified Moby API reference (not host facts).
Archive1407639bytes SHA25650340b4a9e421c8d9dfcf8be1ed4d578218787f041e6bc464be179a0a8b12991. Local tooling only, not full just-check/deployment acceptance.
SLICE1 remains NOT shipped: actual CellBackend–WorkspaceAuthority admission/episodes/per-command
routing/drain/startup discovery/cgroup barrier and factory/callers remain next in existing order.
All35STEPS/four final duties unchecked; Q59/Q75/Q76/final-SLICE6 actual host/full-path proof unchanged.

## E251 — explicit peer/deadline composition seam repaired

E251 repairs the existing dispatcher composition seam, not the actual backend/authority.
DeadlineConnection retains one monotonic request start and exposes read-only start/reply deadline;
required typed authorizer/
handler protocols receive authenticated PeerIdentity and keyword execution deadline through
readonly/reserved operations. Exec deadline = original start + requested command budget; reply
waiting alone keeps the separate control+command allowance. Valid but command-late input invokes
neither authority nor backend. No clock reset, raw-wire identity or fallback callback. Expiry before fresh
authorization/begin/backend prevents late calls; reserved failure remains UNKNOWN. Actual returned
results still persist truthfully even when transport reply expires; Q75 cached original replay
invokes neither callback. Actual admission/drain/command budget/terminality owners remain absent.
TEST-EDITS: dispatch/plan fixtures and direct calls gain explicit peer/deadline arguments; all old
assertion ASTs retained except required deadline keyword in asserted private calls.48 new C0/C3
real-socket/journal cases cover all19 operations, mutating PTY controls, invalid/expired budgets,
authorization/begin elapsed time and no replay. No fake production authority or C1 claim.
Owning15modules732PASS43.34s → nine full732-bank assertion-only kills26/62/26/26/4/16/2/2/1 → restored732PASS42.05s;
all setup/call/teardown clean except intended mutant CALL assertions; no skips/warnings/collection/
runtime/infra credit.598 declared source/input hashes (including new test) exact. Ruff/format27PASS,
Mypy27/183PASS, configured+clean-path Pyrefly0errors (existing141suppressed/50warnings); broader
28modules1251PASS/1FAIL53.71s: immediate second RUN raises WorkerUnavailableError.
This is a real unresolved worker reply/gate race, NOT inherited noise or a green broader gate. Initial missing-keyword fixture migration/lint diagnostics
and missing formatted mutation anchor retained/described, not final kill credit. Superseded
transport-budget source proof and three Pyrefly fixture-unpack errors retained; corrected explicit
ViewRef fields without suppression, fresh final-source baseline/nine kills/restored run PASS.
Evidence `notes/evidence/i03-e251/context-seam.json.gz`, 1929361bytes SHA25689dafdfa8f9fa14c479f21e7d68d76c0acceefa1277a3344aece41941fbd63f7,
contains raw phases/snapshots/runners/restoration and E250 inventory rollforward; all16 production
surfaces/eight joins remain tracked, live verdicts still PLANNED/UNEXECUTED. No actual host run.
NEXT fix the confirmed worker reply/gate handoff race with deterministic scheduling proof; then
actual WorkspaceAuthority registration/generation/materialization/admit/drain joined to the
real CellBackend; no temporary issuer. SLICE1/2/all35STEPS/four final duties remain unfinished;
Q59/Q75/Q76 and final-SLICE6 host/full-path release proof unchanged. No new policy adopted.

## SLICE1: Trusted launch and single supervised execution backend
STEPS: prescriptive
DEPS: none
INTENT: establish immutable controller launch and authenticated fixed-profile Docker jobs with PTY,
  truthful timeout/uncertainty and no command replay; workspace publication follows in SLICE2/3.
CONTRACTS:
  CT98 [FUNCTIONAL]: entrypoint/wrapper/help/auto-run/session launches use installed immutable
    controller_entry with isolated Python and verified package/dependency closure. No project CWD,
    PYTHONPATH/editable pth/project venv import; project imports occur only in cells. The new module
    has an actual __main__ guard; current -m fa.cli is not a runnable CLI. Spec §2.
    kill: remove-call src/fa/controller_entry.py::_main -> _assert_controller_import_closure
  CT99 [FUNCTIONAL]: one private-UDS host supervisor authenticates caller, strictly validates framed
    requests, namespace/view/profile capability and configured limits before Docker. No raw image/
    mount/env/host-path/daemon API or public listener; no daemon socket/control secrets in cells.
    kill: remove-call src/fa/execution/supervisor.py::_dispatch -> _authorize_request
  CT100 [FUNCTIONAL]: ManagedBashExecutor reserves one operation and executes only inside its
    authorized cell; PTY timeout/disconnect remains typed uncertainty, inspect/cancel never replays
    shell through host subprocess. Interactive profiles reuse only their exact live episode; each
    noninteractive one-shot EXEC accepts `session_id=null`, uses a fresh cell/attach, sends one RUN and
    is never cached for a later operation. Same-op replay never creates a replacement. CANCEL of a
    live one-shot must resolve its exact operation/journal-bound CID without the interactive episode map. Preserve
    PtyResult fields/timeout; receipt status is truthful. Spec §§2.1–2.2.
    kill: remove-call src/fa/execution/client.py::ManagedBashExecutor.run -> _execute_once
  CT100a [CONSTRAINT]: deploy a single approved Linux/Docker profile family with private namespaces,
    nonroot/cap-drop/NNP/seccomp/resource limits, digest-pinned image/toolchains, no default network
    or host/control mounts. Dependency cache is approved/read-only; unsupported dependency access
    blocks. Root/daemon/kernel/admin are TCB; profile/cgroup/UID/UDS facts require actual host proof.
TESTS: tests/test_controller_entry.py, tests/test_controller_installed.py, tests/test_execution_supervisor.py, tests/test_execution_protocol.py, tests/test_execution_client.py, tests/test_execution_cell_worker.py, tests/test_execution_journal.py, tests/test_execution_dispatch.py, tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py, tests/integration/test_execution_boundary.py   (NEW)
```verify
uv run pytest tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_execution_boundary.py -q -m execution_host
uv run ruff check src/fa/controller_entry.py src/fa/execution tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py tests/integration/test_execution_boundary.py
```
- [ ] STEP1: retain E251 explicit peer/deadline seam and finish remaining actual spec §§2.1–2.2 composition; retain implemented types/codec/client/installed-entry closure, do not rebuild them; retain E247 typed ERROR reply classification per spec§2.2; remaining backend/authority composition is still required; distinguish control/command deadlines and exec versus non-exec uncertain replay (exit: complete owning bank passes, isolated installed module executes real CLI help under CWD/PYTHONPATH/editable-pth poison, locally invalid input sends no frame and command-over-control-budget reply is observed exactly once)
- [ ] STEP2: retain E249 native owned force-stop/observation (NOT a cgroup/terminal barrier); NEXT implement NEW CellBackend in execution/backend.py over existing DockerCells/WorkerClient/OperationJournal, with per-view live episode ownership, per-command begin/record_container and actual inspect/cancel/drain/restart facts per §2.2; join the actual SLICE2 admission gate before service composition, without a temporary authority (exit: interactive commands preserve shell state in one cell with two durable records; two distinct noninteractive operations with null sessions use two fresh one-shot cells/attaches and one RUN each; same-op duplicate/lost RUN never creates or resends; cancel-before-send, live one-shot cancel by exact journal-bound CID, and completed-creation/DONE-live-cell restart tests pass; lock expiry consumes the original deadline without a late Docker/RUN effect; no success/terminal receipt derives only from worker output)
- [ ] STEP3: prepare service/config/install/image and volume-map changes without activation; compose supervisor.py build_supervisor/main only with real WorkspaceAuthority and CellBackend, then SLICE3 publication handlers; apply controller read-only canonical mounts/private-UDS-only and entrypoint changes atomically with SLICE4 caller cutover, never before provisioner/file tools can operate. The dispatcher must route ALL nineteen closed operations and no others: `health|register_workspace|acquire_writer|pin_reader|create_view|read_file|write_file|edit_file|exec|inspect|cancel|pty_control|stop_view|seal|publish|install_project|prepare_bundle|handoff|release` (that list is `Operation` in `execution/primitives.py`; derive it from the enum, never retype it). `stop_view`, `seal`, `publish`, `install_project`, `prepare_bundle`, `handoff` and `release` are NOT readonly and MUST pass the authority check; a missing route is an explicit closed-code refusal (`INVALID_REQUEST`/`BACKEND_UNAVAILABLE`), never a silent success or a host-side fallback. A view-less route that needs an owner grant must reject a null capability. `create_view` MUST forward the wire's `base_revision` into `WorkspaceAuthority.create_view(base_revision=…)` so the CAS is enforced by the authority, not by the handler (exit: no permissive/failing-main stub or alternate host runner; a route-coverage test enumerates the nineteen `Operation` members and fails on any unrouted one; approved disposable-host test later boots that real factory and proves absent control mounts/secrets, denied profile/raw-path escalation and zero unavailable-backend project commands) **Progress and what is left (E282).** 18 of the 19 routes now dispatch to real owners (E277/E279/E280). The two closures left are `register_workspace{create:true}` (no creating owner exists until SLICE5's acquisition lands) and `handoff`, which is owned by SLICE2 STEP6/CT113; this step therefore closes only when that route stops refusing, and it does so without reopening the route table, because the wire shape, the authority gate and the `GrantReply` reservation path already exist. **Update (E283):** that route is now routed too, so all nineteen `Operation` members reach a real owner, and the only closed refusal left in the table is `register_workspace{create:true}` (a payload variant, SLICE5). STEP3 itself stays open on its remaining exit criteria — the install/image/entrypoint set and the disposable-host boot proof.
- [ ] STEP4: accumulate required real profile/image/kernel/daemon/cgroup facts and source-restored full-path CT98–CT100 mutation outcomes/cost at final SLICE6, with actual SLICE2 authority and SLICE4 callers, not injected callbacks (exit: every declared path runs non-skipped; each named producer deletion causes assertion failure in the whole owning bank; terminality uncertainty leaves ownership quarantined, source restored and no live owned cell)

## SLICE2: Workspace identity, exclusive writer and coherent private IO
STEPS: prescriptive
DEPS: SLICE1
INTENT: arbitrate all mutators by canonical workspace identity, keep dirty inputs and pinned readers,
  and make file tools and PTY observe one private view, never direct canonical writes.
CONTRACTS:
  CT101 [FUNCTIONAL]: acquire_writer serializes one workspace writer across run/session aliases,
    durably increments generation before a capability is usable, rejects stale/busy requests, and
    never expires a lease while old processes may write. Recovery precedes reacquisition. Spec §4.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.acquire_writer -> _claim_generation
  CT102 [FUNCTIONAL]: create_view materializes approved current filesystem bytes including staged/
    unstaged/untracked changes; no clean checkout. Enforce copy/protected/link/size policy and pin
    immutable reader revisions. Canonical index and user sentinels remain byte-identical.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.create_view -> _materialize_input
  CT103 [FUNCTIONAL]: actual write/edit tools use supervisor rooted IO against the same authorized
    open view as shell; deny protected/PlanRef/control destinations and alias escapes. Tool+PTY
    edits plus read/search are mutually visible for the active writer; independent readers retain
    their immutable pins. No stale canonical/index fallback or direct canonical write. Spec §§4–4.2.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.write_file -> _write_rooted
  CT103a [CONSTRAINT]: SessionManager permits explicit new-session reference to an existing
    registered workspace without transferring session DB/history ownership; one writer remains.
    Validate legacy manifests/run bindings; no blanket guard removal or second session manager.
    Future children inherit parent ownership/view/cancel scope; workflow subagents stay absent.
  CT113 [FUNCTIONAL]: handoff moves the SINGLE active mutator grant from the calling namespace to a
    controller-attested child run, as ONE durable metadata replace: owner proof, settlement (identical
    to release: every WRITE view PUBLISHED/REJECTED, no intent.json), same session, target.parent_run_id
    == caller.run_id, target.run_id != caller.run_id; then active_actor := target with owner_namespace,
    generation, status and revision_id UNCHANGED and a fresh 64-hex capability minted. Generation is
    never advanced (a handoff is not a new write epoch), the old capability dies with the replace, and
    exactly one durable operation record ends DONE. No session store, attester, ServiceConfig field,
    wire shape or second grant is introduced. Spec §2.1 handoff row, §7.1.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.handoff -> _handoff_owner
TESTS: tests/test_execution_view_io.py, tests/test_execution_workspace.py, tests/test_execution_readers.py, tests/test_execution_views.py, tests/test_execution_handoff.py, tests/test_managed_workspace.py, tests/test_session_lifecycle.py, tests/test_execution_project_tools.py, tests/integration/test_workspace_views.py   (NEW interfaces; existing session lifecycle tests retained)
```verify
uv run pytest tests/test_execution_view_io.py tests/test_execution_workspace.py tests/test_execution_readers.py tests/test_execution_views.py tests/test_execution_handoff.py tests/test_managed_workspace.py tests/test_session_lifecycle.py tests/test_execution_project_tools.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_workspace_views.py -q -m execution_host
```
- [ ] STEP1: retain E245 internal execution/view_io.py and its real-descriptor C0/C3 bank per §4.2 E244 (no admission/CT completion claim); retain E253 actual WorkspaceAuthority protected existing-root registration/current/R0/writer generation/startup fencing; retain E255 actual immutable reader pins/rooted reads/release; retain E256 actual WRITE/PROJECT views/rooted IO; NEXT construct execution admit/close-admission/drain semantics per §§2.2/4.2, not a second lock service; reject root aliases/overlaps/rebind and quiesce before R0; `create_view` keeps enforcing the wire's `base_revision` as a CAS precondition (retained from E268 review) rather than silently binding `current` (exit: two OS processes race for one workspace and exactly one obtains a durably advanced writer; denied/stale admissions produce no launch/write; when close wins before the scoped effect there are zero Docker create/start/attach/RUN and file-write effects; when the scoped effect wins, close/drain waits for that bounded effect/handler; independent pins retain original bytes across generation changes)
- [ ] STEP2: retain E256 actual WRITE/PROJECT create_view/_materialize_input and rooted read/write; NEXT complete the four non-PROJECT view purposes and actual execution-admitted read/write/edit on retained descriptors per §§4–4.2 before provisioning consumes them. The purposes are exactly CANDIDATE, VERIFICATION, MUTATION, PROVISIONING (ViewPurpose in execution/types.py; PROJECT is the retained one). Extend create_view's request to the §2 table shape `{workspace_id,base_revision,access,purpose,candidate_scope,plan_ref}` with these exact admission combinations and no purpose switch: CANDIDATE requires plan_ref + exact candidate_scope `{candidate_path,plan_ref}` with identical top-level plan_ref (bytes live in supervisor staging per §5, never canonical .fa/admission); VERIFICATION/MUTATION require nonnull plan_ref (§3.1) and are read-only-source + private scratch; MUTATION is the single write-capable derivative for mutation checks (one permitted src/scripts target, trusted controller only, §6); PROVISIONING is the provisioning view (nonnull plan_ref NOT required) and runs only inside the manager's provisioning RunContext from STEP3; every other combination denies INPUT_POLICY before copy. Keep private-metadata chmod helpers off project parents; preserve dirty/staged/untracked/deleted bytes and canonical index, enforce copy/link/secret/size policy and private-Git limitations; consume STEP1 descriptor IO under actual admission, private same-filesystem staging and explicit profile/protected-PlanRef binding (exit: exact tree/index/sentinel oracles pass; link/special/limit/root-swap failures leave no returned grant or partial revision; expected-SHA conflict and post-admission rename do not silently succeed or touch canonical/control paths; one denied-combination case per forbidden purpose/scope tuple)
- [ ] STEP3: inject the managed provisioner into the existing SessionManager BEFORE `_new_session` calls `_provision_workspace` (this is the SLICE2 component injection; SLICE4 STEP2's repetition means routing the remaining inventory callers through the SAME provisioner at activation, never a second implementation); reserve its real provisioning RunContext via early existing DB/begin_run per §4.2; update both reverse-owner call sites (manager.py `_new_session` and `resolve_workflow_workspace`) for explicit registered references per CT103a and fail non-READY; preserve session DB/run reservations and validate legacy records under authority. The provisioner result contract is exact: a frozen result carrying `{registered: bool, workspace_id, revision_id, tree_sha256}`; manager cleanup may rmtree only `registered is False` scratch the provisioner itself created, and a registered/committed workspace is NEVER an rmtree target. `workspace_preparer` returns ReadyState and the manager treats not-READY as SessionManagerError("workspace_not_ready") in BOTH `_new_session` and `_attach_session` — no log+continue. The host-Git `_provision_workspace`/`provision_git_workspace` path is removed at injection, not retained as a fallback: new-workspace provisioning until SLICE3's publication join is an explicit typed BLOCKED disposition (provisioning_unavailable), while explicit registered reuse bypasses clone/readiness/remotes. The publication-dependent provisioning leg completes with SLICE3, not host Git fallback. SLICE2 half (exit): injection ordering test proves the manager consults an injected provisioner before any `_provision_workspace` effect; **Amendment 2026-10-31 (Q90 note §15):** this slice owns only the manager's side of the seam, because a controller process cannot hold a `WorkspaceAuthority` object once the authority is the composed supervisor service — `ManagedProvisioner(WorkspaceAuthority)` (`execution/provisioning.py:37`) is imported by no module in `src/` and cannot be the injected value. The ordering test therefore uses a recording callable `WorkspaceProvisioner` (`session/provisioning.py:66`), and the real client-backed provisioner is built in SLICE7 STEP9 and injected in SLICE4 STEP2; new-session explicit reference to an existing registered workspace succeeds without transferring DB/history and one writer remains; corrupt manifests and legacy run-ID tests pass; provision failure and not-READY leave no active session; post-commit-failure cleanup never deletes registered bytes (covered with a registered=True provisioner result). (exit: the injection-ordering, registered-reuse, corrupt-manifest and legacy-run tests pass; a provision failure or a not-READY state leaves no active session; post-commit cleanup never deletes registered bytes; the DB/manifest failure after a real workspace commit is the SLICE3 evidence half, which keeps the registered bytes intact and reports SessionManagerError).
- [ ] STEP4: wire actual tool builders and SessionState internal binding per §4.2: controller fuzzy matching/telemetry, supervisor rooted writes, same-view bounded reads and cell-local existing search/reach/PDF implementations; no new public tools/search service or private state mount; join real authority/backend factory before disposable integration (exit: actual registry tools and PTY observe each other's edits with blackboard on/off and zero host Git/version-stamp reads, active search sees a new symbol, reader search stays pinned, artifacts retain their controller path, PDF/binary/large/truncated/helper-unavailable results are explicit and no canonical fallback occurs; seal/import alias tests complete with SLICE3)
- [ ] STEP5: record CT101–CT103 whole-bank full-path producer kills plus same-inode/different-label contention, queued revoke/stop races at create/start/attach/RUN (not merely after `admit()`), restart and cleanup; accumulate actual Docker/kernel runs for final SLICE6 without substituting unit fixtures (exit: every named producer removal breaks an executed assertion, including no late launch/write after closed admission; all required host cases non-skipped, exact source restored, no leftover live cell or lost pin)
- [ ] STEP6: implement CT113 `handoff` — the single mutator grant moves to the controller-attested child run (Q85 ruling, E282). Placement note: Q85's recommendation names this unit "SLICE2 STEP2"; it is recorded as its own STEP because STEP2's exit criteria are the five view purposes (a different producer and bank) and CT113 needs its own settlement/replay matrix, so folding it in would reopen a step that has nothing else outstanding. **Progress (E283).** The authority body and the route are implemented and locally proved: `handoff`/`_handoff_owner` over the real authority, the shared `_settled` predicate, the writer-fd guard and the read-back-before-grant, with `tests/test_execution_handoff.py` **17 passed** and 15/15 assertion-only mutants killed (including the declared producer kill). What this step still owes is the host case `I03-LIVE-27` and the controller leg, which is SLICE5 STEP2's and cannot exist before a `src/` composition holds an `ExecutionClient`. This step activates the LAST of the nineteen routes (`service.py::_handoff` stops refusing `BACKEND_UNAVAILABLE`); the controller leg — parent suspension, `_child_run_context`, the RPC — stays with SLICE5 STEP2, because no `src/` composition holds an `ExecutionClient` yet. No wire change is required or permitted: `Operation.HANDOFF` already decodes `{target_namespace}` into `_OWNER_REPLY`, is already in `AUTHORITY_GATED_OPERATIONS`, is already non-readonly (so it reserves `op-<request_id>` through the existing dispatcher), and is already a `GrantReply` operation in `_execute_reserved`; Q75 replay already compares the request's proof to the cached original proof, not to the current grant. The authority body reuses `_transaction`, `_owner_only`, `_has_unsettled_views` and `_replace_private_bytes` — never `_claim_generation` (the trap: it would advance the generation and stage a new write epoch), never a second flock, never a second `begin_run`. Requires the live writer fd (`binding.writer is not None`, else `STALE_GENERATION`) so the authority never moves an ownership it cannot fence. A crash after the metadata replace but before the reply leaves an OWNED workspace whose grant nobody holds: restart quarantines it exactly as for `acquire_writer`, and the attempt is never reconstructed from the journal. **E287 cross-link:** the source-backed coder handoff for this already-proved authority surface belongs in `e2e/I03/implementation-handoffs.md` under I03-LIVE-27, and links L-HAND-1/2 as planned host evidence only; the distinct controller call path remains SLICE5 STEP2/CT108 and the integrated outer-chat join remains I03-LIVE-S08. (exit: `tests/test_execution_handoff.py` proves — over the real authority, real files and the composed route — a handoff that keeps generation, `owner_namespace`, `status` and `revision_id` byte-identical while `active_actor` becomes the target; fresh work with the old capability `UNAUTHORIZED` with zero effect while Q75 replay of the same request id returns the original cached reply including the new capability; a new request id with the old proof `UNAUTHORIZED`; a `SEALED`-but-unpublished view, an `OPEN` view and a present `intent.json` each `WORKSPACE_BUSY` with the metadata unchanged; a mismatched session, a mismatched parent, a self-target and a null parent `INPUT_POLICY` before any write; a foreign principal, a foreign capability and a namespace that is not the active actor `UNAUTHORIZED`; exactly one durable record per successful handoff ending `DONE` with the capability absent from the journal; and a second handoff from the child to its own attested child succeeds, proving the chain rather than a one-shot transfer)

## SLICE3: Terminal seal, fenced publication and forward recovery
STEPS: prescriptive
DEPS: SLICE2
INTENT: prevent descendants or aliases from changing validated bytes; publish complete revisions
  and exact canonical projections with one durable recovery owner and distinct Q58/bootstrap commits.
CONTRACTS:
  CT104 [FUNCTIONAL]: stop_view closes file-write admission, drains handlers, stops all PTYs/cells
    and confirms actual cgroup descendants empty before seal. Exit/Ctrl-C/timeout is not terminality;
    UNKNOWN quarantines and holds ownership. Supervisor restart cannot release a live old writer.
    kill: remove-call src/fa/execution/supervisor.py::stop_view -> _wait_descendants_terminal
  CT105 [FUNCTIONAL]: seal_view recomputes immutable export hashes/type/mode/deletions after barrier,
    rejects protected paths/link/special/escape aliases and stale base/source/generation, and never
    imports a model manifest or live mutable directory. Spec §5.
    kill: remove-call src/fa/execution/publication.py::seal_view -> _validate_sealed_tree
  CT106 [FUNCTIONAL]: publish_view durably prepares full immutable revision+intent, CAS-commits
    current pointer then completes verified canonical projection before receipt/next writer. Managed
    readers see complete pinned revisions; canonical Git index/protected state remains untouched.
    kill: remove-call src/fa/execution/publication.py::publish_view -> _commit_current
  CT107 [FUNCTIONAL]: recover_workspace inspects intent/current/generation, discards only provably
    uncommitted owned scratch or completes committed projection forward; mismatches quarantine.
    No committed rollback, stale token success or partial-current completion at any crash point.
    kill: remove-call src/fa/execution/publication.py::recover_workspace -> _recover_intent
  CT107a [CONSTRAINT]: Q58 exact canonical replacement, no-replace new-project install, and ordinary
    multi-file revision commit keep distinct intent phases/irreversible points. Bootstrap uses real
    Linux RENAME_NOREPLACE, no existence-check+rename. Post-commit artifact failure preserves bytes
    and blocks; fsync errors are uncertainty, not permission to replay/rollback. Spec §5.
TESTS: tests/test_workspace_publication.py, tests/test_stage_checkpoints.py, tests/integration/test_publication_recovery.py   (NEW)
```verify
uv run pytest tests/test_workspace_publication.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_publication_recovery.py -q -m execution_host
```
- [ ] STEP1: implement selected Q74 per-stage/episode checkpoint policy and spec §6.1 stage transition table; implement terminal barrier/view state machine and immutable export validation in execution/publication.py plus supervisor.py::stop_view -> _wait_descendants_terminal (CT104's named producers). **Progress and the remaining parts of THIS step:** the terminal barrier shipped in E266 and the immutable export/seal in E267 (both local C0/C3); what STEP1 still owes is (a) the Q74 per-stage/episode checkpoint policy wired to §6.1's transition table and (c) `tests/integration/test_publication_recovery.py` running the kernel-observed barrier under `FA_REQUIRE_EXECUTION_HOST=1`; (b) the real Docker/cgroup `CellTermination` behind the existing seam is delivered by E278 (`termination.py`/`cgroup.py`, local C1) and is *proved* on a host only by (c). **(a) in full, so it is not mistaken for prose.** It owns the whole §6.1 transition table, not only the happy path: at every mutating episode/stage boundary after proven terminality and path/security validation, the permitted ordinary edits are checkpointed through the existing `seal`→`publish` producers into `Rn`/`current`/projection before the next episode starts; a stage that exits nonzero or is interrupted makes the same bounded stop/seal attempt and may still checkpoint allowed terminal edits while the stage stays failed; a functional/provider failure never blocks a checkpoint and a checkpoint never turns a failed stage into `DONE`; `verify`/`eval` read a separate READ source at `Rn`; the repair or repeated-coder episode allocates a NEW open view from the authoritative `Rn`; and each checkpoint writes exactly one `execution.json` record (`{kind,artifact_sha256,plan_sha256,revision_id,original_revision_id,tree_sha256,operation_ids}`, immutable order, no capabilities). Owned test file `tests/test_stage_checkpoints.py` (C1: real authority + real views, no host): the transition table's rows, the "failed stage still checkpoints" and "checkpoint is not success" pairs, the sidecar schema/ordering, and the refusal that an unknown/live/quarantined view cannot publish or release. No new CT is declared here on purpose — the durable effects are CT106's publish and CT107a's PLAN phases, the barrier is CT104, and the sidecar is CT110/CT111's receipt/report artifact; this step's job is the *policy and ordering* that composes them, which is why its evidence is those banks plus the §6.1 matrix rather than a new producer kill. STEP1 is one step with three parts, not one checkbox per part; it closes only when all three exist, and part (c) — together with the host half of (b)'s proof — is blocked in any session without an approved Docker daemon, while (a) is not host-blocked and can be taken now. Test split is fixed, no guessing: the view-state machine and immutable export validation run in tests/test_workspace_publication.py over the real local worker/attach cells (E258's fixture pattern) and prove seal/publish is refused while any handler or cell is unsettled; the actual cgroup-populated-empty descendant barrier runs only in tests/integration/test_publication_recovery.py under FA_REQUIRE_EXECUTION_HOST=1 (kernel fact, never mocked). Tests launch fork/double-fork/setsid/background writers in real cells and hold active file operations (exit: none can seal/publish while still writable)
  **Progress (E284).** Part (a)'s policy owner and its bank now exist: `src/fa/execution/checkpoints.py` owns the
  boundary order — prove terminality (`terminal is True`, nothing weaker) → seal → publish at the view's own base →
  agree with the committed receipt → append exactly one `execution.json` record — plus the append-only, run-bound
  sidecar that §6.1 freezes, and `tests/test_stage_checkpoints.py` (36 cases, C0/C1/C3) covers the transition-table
  rows this module can own without a host, including "a failed stage still checkpoints" and "a checkpoint is never
  read as success" (the record has no field for it and the boundary accepts no stage outcome). What part (a) still
  owes is its **call site**: `run_stage_with_plan_write_boundary` (CT97) is the A5 cutover, so no stage loop calls the
  boundary yet, and the verify/repair rows of the same table are A5/A6 controller actions. This step therefore still
  closes only when (b)'s cgroup observer and (c)'s `tests/integration/test_publication_recovery.py` are host-proved;
  no box is ticked here.
- [ ] STEP2: implement exact intent/current/projection schemas/order/dir fsync and generation/base CAS per spec §5, including canonical Git-index preservation and spec §5.1 exact Q58/bootstrap forward-recovery phases. Materialize Rnext **from the sealed manifest**, re-verifying every digest against the view's frozen source, and materialize it under the id `seal_view` derived (`derive_revision_id`), never a caller-supplied id; the irreversible point for an ordinary revision is the `current.json` replace, and the recovery discriminator is `current.json`, not the phase value. Publish flips the view record to `PUBLISHED` and thereby **settles the owner**: `release_unused_writer` accepts only PUBLISHED/REJECTED WRITE views and refuses OPEN/STOPPING/UNKNOWN/SEALED (retained predicate from the E268 review) (exit: complete old/new pinned-reader and stale/fault unit matrix passes; publishing a SEALED view makes a subsequent `release` succeed and a later re-claim advance generation; publishing a view whose manifest hash or source bytes moved is `CORRUPT_STATE` with no `current.json` change)
- [ ] STEP3: integrate the existing inner_loop/plan_promotion.py Q58 buffer/hash/promotion primitives and this authority's no-clobber bundle primitives (execution/publication.py::prepare_bundle / install_project, per §5's bundle handoff; §1 already assigns no-clobber project install to publication.py) with the same authority; no managed-acquisition UI/protocol before SLICE5 integration (exit: direct controller-authorized tests prove collisions preserve old bytes and post-commit failure never rolls back). **Progress and what this step still owes:** the bundle renderer/store (E271), the `RENAME_NOREPLACE` install under the Q82 (B) ruling (E271 unit B) and the same-path plan replacement with its forward-only commit (E273) are implemented and locally proved. The dispatcher's pre-reservation `authorize` seam is now real (E274); what remains is the nineteen route handlers plus `build_supervisor/main`, and then the controller leg — `_promote_validated_plan` still calls `inner_loop/plan_promotion.publish_plan_buffer` directly and must be moved onto the authority's `publish` of a CANDIDATE view, deleting that transport in the same change so exactly one writer owns the canonical plan. The step closes only when that leg is proved end to end; the components above are not a substitute for it. **Progress (E286, blocked).** A3's supervisor half is the prerequisite for that leg, and writing it exposed an
unrecorded wire-contract choice: the existing `publish` payload requires a `seal-` id (`protocol.py:126`) that a
CANDIDATE view never has, and its reply (`_COMMITTED`) carries no `plan_ref`, which §5 makes the only ref downstream
may record. Promoted as **Q89** with three options and a recommendation rather than guessed. Nothing was implemented
and the legacy writer stays in place: deleting `publish_plan_buffer` before the managed route exists would leave the
system with zero plan writers, and adding the route with a guessed encoding would ship a contract the operator has not
chosen. **That leg's planned surface, so it is not left as prose (E282).** Owning bank: `tests/test_verify_gate_live.py` (the only bank that reaches `_promote_validated_plan` today) plus `tests/test_workspace_publication.py` for the authority half; the wire route is the existing `publish` with a CANDIDATE-view ledger, not a new operation. Exit for the leg specifically: the controller's plan write reaches the authority through `ExecutionClient.publish` and `plan_promotion.publish_plan_buffer` is **deleted** in the same change (R3 — a retained fallback is a second writer by another name), the returned `plan_ref` is the only ref recorded downstream, a CANDIDATE view that is not the caller's own scoped candidate is refused, and a stale source hash is `STALE_REVISION` with the canonical plan byte-identical. **Amendment 2026-10-31 (Q90 note §15).** The authority half above is this step's; the *controller* half is SLICE7's, not a second owner: `ExecutionClientPlanPublisher` and the client verb are SLICE7 STEP7, and the composition that supplies the port is SLICE7 STEP8/CT116. Before that amendment this step's exit required end-to-end proof of a leg that no slice built, which made SLICE3 depend on SLICE7 while SLICE7 depended on SLICE3 — the cycle is removed by giving the controller leg to SLICE7 and leaving this step the authority route plus the deletion. The module named `inner_loop/plan_promotion.py` keeps its name (the SLICE7 STEP10 rename was cancelled in the reduction pass, E290.1); read `publish_plan_buffer` references here as history, since E288 already deleted the function.
- [ ] STEP4: recover from supervisor/process death at each durable boundary, before/after pointer replace and during projection; require approved filesystem and separately label process-crash versus power-loss evidence. The hook points are fixed by existing code: `WorkspaceAuthority.__enter__` calls `journal.recover_uncertain()` then `_load()`, and `_load` currently QUARANTINES every `OWNED` workspace with no forward path — `recover_workspace` must run there, before the quarantine decision, for every workspace with `intent.json`; and `_initialize_genesis` already refuses a non-empty `views/` or a present `intent.json`, so nothing else may assume a pristine workspace. Stale `pending/` staging from a hard kill is NEVER swept today (`__enter__` creates the directory and moves on), so recovery must also classify those directories as owned scratch (discard) versus unknown (quarantine), and must not delete a directory referencing a committed revision (exit: real recovery tests expose only complete current revisions or quarantine, no success from uncertain state; a killed supervisor mid-projection leaves no orphan `pending/` entry that a later authority silently ignores) **Progress (E276):** the local recovery unit is implemented and hooked into `_load` in the same change — CT107's three kinds complete forward or discard only provably-uncommitted owned scratch, stale `pending/` staging is classified, and 17/17 producer mutants are killed over the real authority. STEP4 still owes the kernel-observed matrix on the approved filesystem (`FA_REQUIRE_EXECUTION_HOST=1`), kills *inside* recovery, the fsync-unsupported/EIO cases, and explicit process-crash versus power-loss labelling.
- [ ] STEP5: record full declared-path CT104–CT107 kills and cleanup/ownership evidence (exit: all four producers killed by useful executed oracles; no cells/pins/intent abandoned without disposition)

## SLICE4: Close every execution route and bind verifier/eval evidence
STEPS: prescriptive
DEPS: SLICE3, SLICE7
INTENT: complete CT97 before nested acceptance; no early readiness/import/Git/subagent/fallback path
  may execute project code on controller/host, and stale/uncertain evidence cannot succeed.
CONTRACTS:
  CT97 [FUNCTIONAL]: real _cmd_run boundary covers whole stage prologue, all mutating provider
    tools/PTY/descendants, approved dirty view, protected PlanRef/control paths and source import.
    Valid controller promotion/ordinary edits work; file/shell/alias/rename attempts cannot change
    canonical protected bytes. Keep original stage-seam kill, not merely hook registration.
    kill: remove-call src/fa/cli.py::_cmd_run -> run_stage_with_plan_write_boundary
  CT110 [FUNCTIONAL]: verifier noninteractive commands, baseline/import/collection/mutation probes
    execute through managed operation adapters on pinned source+scratch; no host subprocess runner
    or replay. Actual exit/timeout/tree/profile/terminal identity is captured. Spec §§3/6.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_one -> _run_managed_command
  CT111 [FUNCTIONAL]: kill-check classification validates fresh operation/view/tree/PlanRef binding
    plus strengthened detailed pytest report; error/timeout/collection/setup/stale/zero/skip-only
    never PROVEN. Preserve slice sensitivity, genuine test-call failures and Q53(c)/Q54 rules.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_kill_check -> _validate_bound_pytest_report
  CT111a [CONSTRAINT]: inventory all project execution and prove closure before product acceptance:
    readiness/dependency hooks/entrypoint, project Git/config/helpers, chat SubagentRunner, PTY and
    verifier routes. Admission/isolation/integrity are mandatory in both modes and every role.
    Keep I02 pinned T0/Q55/Q56/Q73 semantics; unsuccessful safe-view/deadline recovery is explicit,
    never fabricated eval or DONE. Structured reports are not hostile-test correctness attestation.
TESTS: tests/test_verify_gate_live.py, tests/test_verify_slice.py, tests/test_slice_verification_runner.py, tests/test_workflow_deadline.py, tests/test_workflow_global_history.py, tests/integration/test_execution_closure.py   (NEW integration)
```verify
uv run pytest tests/test_verify_gate_live.py tests/test_verify_slice.py tests/test_slice_verification_runner.py tests/test_workflow_deadline.py tests/test_workflow_global_history.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_execution_closure.py -q -m execution_host
```
- [ ] STEP1: complete the inspected notes/i03-execution-call-inventory.md with exact source/caller/profile/view/negative oracle per spec §6; classify newly found subprocess/import/Git entrypoints rather than excluding them by name (exit: inventory covers every production route used by explicit/chat/nested workflows)
  **Progress (E285).** The inventory was re-scanned and rewritten at `969fa06`: 52 call sites in 22 files found by a
  widened AST scan (module-qualified *and* from-imported `subprocess`/`pty`/`pexpect`/`libtmux`/`multiprocessing`/
  `asyncio.subprocess`/`importlib`/`runpy`, `os.system|popen|fork|forkpty|exec*|spawn*|posix_spawn*`, and
  `shutil.which` gates), of which 28 launcher/import sites in 16 files are mapped one-to-one to rows R01–R28 with
  exact anchors, real caller traces, the boundary that exists today (host/cell/TCB, and the explicit statement that a
  host route has neither profile nor view) and a named negative oracle; the remaining 24 findings are classified out
  by class with a reason (in-process `shutil` cleanup, capability gates, approved-library data imports). Coverage of
  the three workflow entrypoints (explicit/chat/nested) is stated row by row. **The box is not ticked:** the
  checklist defines a row as closed only with the negative oracle's *results*, and every oracle here is a planned
  nodeid that needs the managed backend (STEP2/A5). What is left for this step is those results, not more inventory.
- [ ] STEP2: retain _cmd_run signature as pure validation→run_stage_with_plan_write_boundary→_cmd_run_inner; wrap whole _cmd_run prologue and route manager/entrypoint/bootstrap readiness through provisioning cells; remove fail-open readiness and host fallback paths. The provisioner is **injected here, not in SLICE2** (SLICE5/SLICE7 coexistence review, Q90 note §15): SLICE2 STEP3 can only prepare the manager's side of the seam, because a controller process cannot hold a `WorkspaceAuthority` object once the authority is the composed supervisor service (E277) and the in-process `ManagedProvisioner` (`execution/provisioning.py:37`) has no production caller. This step constructs `ClientWorkspaceProvisioner` (SLICE7 STEP9) in `cli.py::_session_manager_for_args` (`:247`, where `workspace_preparer` is already passed at `:272`) together with the readiness enforcement above, and routes the remaining inventory callers through that same instance; never implement a second injection or second provisioner. No rollback deleting supervisor-owned registered roots. Wire project Git/pair/subagent paths too (exit: backend-down run across each inventory route executes zero project commands; no unsupervised legacy bind/process)
- [ ] STEP3: integrate pinned verification scratch/receipts/report parsing and explicit artifact schema versions; retain old I02 evidence readers, no duplicate verification engine (exit: actual supervised tests prove candidate import provenance, stale-operation/timeout/report negatives and immutable T0 compatibility)
- [ ] STEP4: real direct C1 with actual supervisor/cells and only provider mocked proves each write/edit/shell route, dirty sentinels, denied protected paths and successful ordinary source edit/Q58; real eval sees same attempt and hard-blocks integrity failure in both modes (exit: execution_host closure matrix passes, no all-skips)
- [ ] STEP5: record full-path CT97/CT110/CT111 kills; retain original CT97 producer case identity and all I02 gate regression proofs (exit: source restored and useful executed producer oracles all killed)

## SLICE5: Managed nested selection/bootstrap and initial parent context
STEPS: prescriptive
DEPS: SLICE4, SLICE7
INTENT: deliver actual outer chat→invoke→child workflow with correct child authority, approved
  selection/bootstrap/clarification and Q66 under recorded Q59/Q60 dispositions, reusing one workflow machine.
CONTRACTS:
  CT96 [FUNCTIONAL]: under recorded Q59/Q60 dispositions, actual invoke handler calls managed
    planner acquisition, returns exactly approved stable-ID selection/bundle/clarification, admits
    selected/installed canonical PlanRef before T0/coder, and preserves ordinary chat default.
    No guessed path, public context/PlanRef field, free-form file map or raw ledger. The callee below was
    deleted with Q70 (`git grep _run_planner_managed_workflow src` is empty): STEP2 renames this directive to
    the managed entry point it creates and re-proves the kill (Q90 note §15).
    kill: remove-call src/fa/inner_loop/tools/workflow_tool.py::handler -> _run_planner_managed_workflow
  CT108 [FUNCTIONAL]: managed invocation allocates child RunContext via existing SessionManager
    before child artifacts/provider; distinct run_log_dir/DB binding and parent metadata. Suspend
    parent mutators; scoped child inherits same workspace writer, no deadlock/second writer. Same stale
    symbol as CT96: STEP2 renames this directive when the managed entry point exists.
    kill: remove-call src/fa/inner_loop/tools/workflow_tool.py::_run_planner_managed_workflow -> _child_run_context
  CT109 [FUNCTIONAL]: live provider snapshots bounded current parent messages at invocation time,
    feeds only initial planner user task beside its own prompt/skills; no SYSTEM transcript/public
    schema field. Redact credentials; retries/replans use distilled packets, ordinary logs allowed.
    kill: remove-call src/fa/cli.py::_make_workflow_ctx_provider -> _snapshot_parent_for_initial_planner
  CT109a [CONSTRAINT]: implement spec §§7/7.0/7.1 stable pair/schema, clarification, rendering/caps
    and v2 acquisition cross-fields using existing child allocator/PlannerDispatch/SessionOutcome/
    admission/repair/PrDraftStore, not a second engine. Retain v1 readers and current experimental
    injection; no new required-workflow mode. Collision/ambiguity/malformed/missing choice blocks
    before coder/eval; post-install IO failure retains valid bundle. No unavailable stub ships as CT96.
TESTS: tests/test_verify_gate_live.py, tests/test_invoke_workflow_tool.py, tests/test_managed_acquisition.py, tests/integration/test_nested_workflow.py   (NEW acquisition/integration)
```verify
uv run pytest tests/test_managed_acquisition.py tests/test_verify_gate_live.py tests/test_invoke_workflow_tool.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_nested_workflow.py -q -m execution_host
```
- [ ] STEP1: author exact spec §7 managed-v2 keys/rules/rendering fixtures and v1 compatibility/selection-vs-bootstrap hash tests; apply E231 decisions, no re-approval ceremony or new routing mode. Include existing expansion/injection preservation and source-backed registry/pr_prepare seams (exit: source-matched fixture/schema tests pass; no inferred runtime acceptance)
- [ ] STEP2: implement actual handler/reused _child_run_context/parent writer suspension and server-acknowledged handoff and acquisition capability; preserve existing task/roles/mode/budget tool fields, no path/context; reserve invocation/child identity before dispatch (exit: actual handler tests prove parent artifacts byte-identical and unique child namespace). **The handoff is split after Q85/E282 and only this step's controller half remains.** The authority and wire route are SLICE2 STEP6/CT113 and are locally proved; this step is blocked until SLICE7 supplies the controller-side composition: `managed_execution_for_run` and `BoundPlanPublisher` are SLICE7 STEP8/CT116, and the client verb `publish_plan` plus the deleted adapter are SLICE7 STEP7. Call that factory with the **child's** run context and build `BoundPlanPublisher(managed.client, child_binding)` for the child's `run_workflow`; never construct an `ExecutionClient` here (SLICE7 STEP8 keeps the only construction site in `src/`). This step also owns the authority widening the child needs: the seven `active_actor` comparisons (`workspace.py:1385,1891,2125,2572,3486,3804,4028`) and `_owner_only` (`:2735`) become one `_acts_as_active_actor(metadata, namespace)` that also accepts a namespace whose `parent_run_id` is the recorded actor's `run_id` in the same session, with the grant, generation and principal checks unchanged. **Stale kill directives (Q90 note §15).** CT96 and CT108 still name `_run_planner_managed_workflow`, which was deleted with Q70; this step must rename each directive to the function it actually creates and re-prove the kill, because a directive naming a deleted symbol cannot be executed. Source preflight: `_child_run_context` already allocates through `SessionManager.begin_run`; `ExecutionClient.request` already accepts a closed `Operation` and has no resend after uncertain transport, but no controller call sends `Operation.HANDOFF`, and no narrow `ExecutionClient.handoff` method exists. Do not invent a new operation or wire shape: after the controller composition is ready, suspend/drain parent mutators and settle all WRITE views (`PUBLISHED`/`REJECTED`, no `intent.json`) before handoff; call the existing HANDOFF RPC once with the parent namespace/capability and `target_namespace` exactly `{child.session_id, child.run_id, ctx.parent_run_id}`; validate the server reply/new grant before child dispatch. On refusal or uncertain transport, do not dispatch the child, resend with another request id, or fabricate a capability. Do not add a second allocator, a second `begin_run`, an attester or a session read in the supervisor: the attestation is the controller's own `begin_run` plus the two wire invariants the authority checks (§7.1). The future handler-level producer test must fail if the HANDOFF request is removed or if child dispatch can precede its acknowledgement; this controller proof is distinct from the authority-local I03-LIVE-27/L-HAND-1/2 host surface and belongs to the I03-LIVE-S08 integrated join.
- [ ] STEP3: implement approved stable-ID selection/clarification and controller-rendered no-clobber bundle via SLICE3 authority, shared I02 repair and before-T0 ordering (exit: exact caps/unknown+duplicate fields/status-smuggling/ambiguous/collision/post-install-fsync+append matrix passes)
- [ ] STEP4: implement live current-message provider, bounded initial task/redaction and distilled retry/replan separation; keep Q66 ordinary log policy (exit: parent-only sentinel occurs in first real planner request, not retries; configured credential sentinel absent)
- [ ] STEP5: actual outer drive_session→invoke→child run_workflow→_cmd_run→drive_session with real supervisor/cells and only ProviderChain.request mocked proves existing selection and new project, clarification/no-coder blocks, child evidence and parent refresh at turn boundary (exit: execution_host nested C1 passes with advisory/manual and existing experimental suggestion paths, in observe/enforce gate modes)
- [ ] STEP6: record CT96/CT108/CT109 full-path mutation outcomes with original CT96 handler producer lineage, no helper-only substitutes (exit: each declared producer killed; no unknown/stale report credited)

## SLICE6: Reviewed I01–I03 package and actual deployed acceptance
STEPS: prescriptive
DEPS: SLICE5, SLICE7
INTENT: execute the transferred former SLICE7 (whose STEPs1–10 now live in this slice) and E223
  acceptance with independent review, exact producer preservation and real main-host evidence for all
  I01–I03 changes; local diff review never assigns a live verdict. This slice now also depends on the
  new SLICE7: review and release gates must not certify the delivery regression.
CONTRACTS:
  CT88 [CONSTRAINT]: preserve all required unique producer keys/cases across I01–I03, keeping
    increment origin explicit;
    separate local proof/live result, stable IDs/owners/fixture/oracle/evidence. Shared scenario only
    with explicit per-producer evidence mapping. Q63 exactly NOT RUN/PASS/FAIL/BLOCKED, optional short
    commentary on ALL states, no mandatory/hardcoded reason variant.
    Append deployed SHA/image/profile/config/run/command/rc/effect/artifact/reviewer per attempt.
  CT89 [CONSTRAINT]: planner owns oracle/run sheet; coder appends source-backed seams/proposals;
    independent manual checklist precedes fixtures/helpers, repeated on material changes. Human
    review only, no approval marker. Useful host behavior/artifacts, not private-helper-only cases.
  CT112 [FUNCTIONAL]: case-index checker compares normalized original producer keys to successor
    coverage, preserves renamed/replaced producers through explicit lineage, collapses only exact
    duplicates, and rejects missing/unmapped/orphan/duplicate cases. It never assigns live PASS.
    kill: remove-call scripts/check_execution_e2e_coverage.py::main -> _check_producer_coverage
TESTS: tests/test_e2e_artifact_contract.py, tests/test_skill_conformance.py   (NEW artifact test; existing skill test)
```verify
uv run pytest tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py -q
uv run python scripts/check_execution_e2e_coverage.py
```
- [ ] STEP1: implement recorded Q63 four-state live-result schema, optional short commentary on every state, no reason-code enum/mandatory BLOCKED field; test all states with and without commentary. Keep roadmap/increment/CT vocabularies, generic READY and active I01 distinct (exit: actual artifact conformance tests pass; no live outcome inferred)
- [ ] STEP2: implement planner case index `worklogs/planning-topology-and-executable-contracts-loop/e2e/README.md` and master `worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/live-verification.md` with append-only attempts/local-vs-live fields; retain I02-origin rows and add mapped I01 obligations (exit: index/status tests pass)
- [ ] STEP3: mechanically snapshot original normalized unique producer keys from the I01 deferred-verification register and the I02/I03 live register, preserve all unique keys/CT/STEP lineage, add new producers and successor mappings; correct CT52 bounded repair and shell-exit-127 vs genuine launch-error oracles (exit: actual coverage checker/test detects removal of any unique case, not only total counts)
- [ ] STEP4: coder writes `worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/implementation-handoffs.md` after real seams/proofs exist, labeling facts vs proposals and limitations. For Q85, link CT113/SLICE2 STEP6 and its local proof to I03-LIVE-27 and the planned L-HAND-1/2 evidence; state separately that the SLICE5 STEP2/CT108 controller request/dispatch leg is absent and the I03-LIVE-S08 join remains future proof. Do not modify the case oracle, add a fixture/host command, or assign a live result (exit: handoff-shape tests enforce the links and evidence labels; coder has changed no oracle/result)
- [ ] STEP5: planner finalizes copy/paste host sheet from actual deployment/workspace facts per spec §9, complete tasks/variables/commands/run IDs/artifacts, safe update stop conditions and observe→review→enforce order (exit: run-sheet checks plus human command review, not pytest claiming deployment happened)
- [x] STEP6: update `plan-authoring/SKILL.md`, `feature-planning/{SKILL.md,INJECT.md}`, and `tests-writing/{SKILL.md,INJECT.md}` with the transferred E223 roles: planner records E2E obligations before coding; coder supplies only a source/evidence-backed implementation handoff; planner finalizes the host run sheet from actual facts; an independent reviewer completes the manual checklist before fixture/helper work; no harness/eval/coder assigns live `PASS`. Keep unrelated generic `DRAFT | READY | BLOCKED` semantics intact **Progress (E364):** E287 already supplied all five texts; role/READY + artifact + delivery-law bank 37 passed, five section-deletion mutants killed in call phase. This closes only the local skill-text exit; E223 host duties and review remain open. (exit: artifact+skill conformance tests enforce the role split and READY preservation)
- [ ] STEP7: independent reviewer completes the manual checklist before the FINAL project-scoped E2E fixture/helper package (not earlier local tests/integration-kernel tests). Review all source/import/readiness/descendant/fencing/recovery and nested cases, I01 plan-authoring/parser/admission obligations, maintenance prerequisites, secret handling, and the stop path. Include E223's transferred scope plus all I01–I03 implementation/evidence obligations; record open findings for final review (exit: named reviewer/date/notes recorded; no machine-approved marker; final broad review still required after material changes)
- [ ] STEP8: only after STEP7, implement reviewed bounded fixtures under `worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/fixtures/` in unique disposable workspaces; preserve evidence/owned cleanup and keep live-host commands outside default pytest discovery (exit: fixture conformance passes; review-before-implementation provenance exists)
- [ ] STEP9: index every distinct local/live producer, including separate CLI/direct guards, candidate/promotion/schema/T0, CT96 selection/bootstrap/clarification/context, CT97 file/edit/shell/subagent-absence/alias paths, early readiness/imports, no-replay, contention/read pins, terminal seal/publication/recovery; map I01 deferred obligations, retained I02 source/functional claims, and I03 producers to actual deployed-behaviour oracles (exit: all original+new required I01–I03 producer keys mapped with useful evidence oracles; no local-only or missing deployed claim credited)
- [ ] STEP10: run local package conformance, every accumulated non-skipped execution_host suite and all 18 full-declared-path kills, and full release gates; review environment/readiness and inherited baseline acceptance using retained I02 manifests, exact test identities/replacements and Mypy contexts, including the unreproduced historical ninth context and relevant hook observations. Resolve or explicitly disposition each item for the intended Ubuntu/Docker/Python deployment without falsifying red results. Before claiming release gates complete, build the installed-controller wheel with supported CPython 3.13 including `zlib` and frozen build dependencies (the current 11 setup errors are a blocker, not a skip); provide the approved ShellCheck binary so all 12 shellcheck-gated tests run rather than skip; and provide a trusted Go 1.24.11 SDK plus pinned Gitleaks/pre-commit dependencies or an approved cached build environment so the actual readiness→hook→commit→publication path and `just test`/`just check` complete without bypass. Go is an indirect test-hook build requirement, not an FA runtime requirement. If any prerequisite remains unavailable, record the row BLOCKED and keep the release gate open. Only with maintenance/deploy authorization perform normal main update and reviewed host runs; inspect nonzero update before retry, verify actual deployed SHA/image/profile/config, execute spec §9.1 unmocked direct+nested workflow witnesses (not only deterministic provider-stub cases), record source-to-behaviour results and broad independent implementation/evidence review plus integrated signoff. No automated/harness PASS (exit: all four E223 acceptance obligations complete with recorded review; all required I01–I03 cases independently reviewed PASS; BLOCKED/NOT RUN/skip never counts)

## SLICE7: Delivery closure — a supplier for the writer, and a patch that publishes

STEPS: prescriptive
DEPS: SLICE3
INTENT: Close the class of defect that produced I03 — a component with no production consumer — and
  the two blockers Q90 traced it to. Every unit touched here is rooted in the command the operator
  actually runs, `fa workflow --plan <path>` (`cli.py:1336`, `run_workflow` at `:1431`), and carries an
  EDGE mutation (remove the caller, not the body) that fails a named test. The slice restores a
  **supplier** for the candidate writer deleted in `5f1c292` (`notes/Q90-defect-group-closure-2026-10-31.md`
  §13), refuses before a planner call when no supplier exists, retains the candidate it cannot publish,
  and stops treating a plan replacement as a snapshot of the whole tree. It adds no wire operation and
  no second writer: the plan remains a byte-exact single-target replacement whose only writer is
  `WorkspaceAuthority.publish_candidate_plan` (`workspace.py:3399`).
  **Sequencing limitation, stated rather than hidden (E290.2).** `_unchanged` re-walks the *host* workspace
  tree and refuses when it disagrees with `current.tree_sha256` (`workspace.py:1303-1310`), so a managed
  publication is sound only while the authority is the run's only writer. This slice implements the
  supplier and the publication; SLICE4 STEP2 removes the host-side write paths. Until it lands, a run gets
  **one** publication: the admission repair happens before any coder stage, while an `EVAL_REPLAN`
  publication follows one, by which time the coder has written host-side bytes and the authority is
  entitled to refuse. The refusal is correct and is pinned by a test in STEP11, not worked around.
  **Not in this slice.** Activating the *nested coder* (`invoke_workflow` with role `coder`) belongs to
  SLICE5 STEP2/STEP5, which already own the handoff controller leg and the outer chat join; the exact
  seams they need are in the Q90 note §14.5 (composition factory keyed by run context, and the seven
  `active_actor` comparisons at `workspace.py:1385,1891,2125,2572,3486,3804,4028` plus `_owner_only`
  `:2735`). Doing it here would have created a second owner for one capability. What this slice does
  give that path is the honest failure: an unmanaged child now refuses `managed-execution-absent`
  instead of spending a planner call and deleting its candidate.
  **One publication per run until SLICE4 STEP2 — and the price is the whole process (E290.2, extended in E292).**
  A host-side write trips `_unchanged` (`:1303-1310`), which sets `_healthy = False`; from then on `_check`
  (`:985-988`) refuses **every** operation of that supervisor with `CORRUPT_STATE`, because the flag is reset
  only in `__enter__` (`:967`). So an `EVAL_REPLAN` publication after a coder stage does not merely fail: it
  ends the authority for the run. The admission repair is unaffected — it publishes before dispatch. The
  refusal is correct, since those host bytes are not the revision the authority holds; adopting them is what
  SLICE4 STEP2 removes. STEP11 pins the first refusal with
  `test_a_host_side_write_before_the_second_publish_is_refused`.
  **Run order (changed by the SLICE5/SLICE7 coexistence review, Q90 note §15).** Numbered after
  SLICE6 because it was written after it, but it executes **fourth**: immediately after SLICE3, which
  is its only dependency. Everything downstream consumes its composition — SLICE4 STEP2 injects the
  provisioner it builds (`DEPS: SLICE3, SLICE7`), SLICE5 STEP2 needs the managed client for the
  handoff controller leg (`DEPS: SLICE4, SLICE7`), SLICE6 reviews and releases it (`DEPS: SLICE5,
  SLICE7`). The previous `DEPS: SLICE3, SLICE4` was wrong in the other direction: SLICE4's readiness
  and provisioning join cannot be completed before a client exists, so SLICE4 was waiting on a slice
  that was itself waiting on SLICE4.
CONTRACTS:
  CT114 [FUNCTIONAL]: the delivery law is part of every planning and execution surface an agent
    reads, and a conformance test proves the text is load-bearing rather than decorative. Six
    surfaces: `knowledge/skills/plan-authoring/SKILL.md` (liveness ladder with ROOT/EDGE/BODY-EDGE
    mutants and SUPPORT units, cutover contract, gates, I-IP-7..9),
    `knowledge/skills/tests-writing/SKILL.md` (central laws, L1/L2/L3 table, I-TW-22..24),
    `knowledge/skills/tests-writing/INJECT.md`,
    `knowledge/skills/feature-planning/{SKILL.md,INJECT.md}` (laws 10–11, contract-card
    SUPPLIER/ROOT/EDGE, edit-packet Delivery, after-edit gates, anti-patterns),
    `src/fa/inner_loop/prompt.py` (PLANNER hard rules + `## Delivery` template + self-check; CODER
    delivery discipline and the three final-message facts), `knowledge/prompts/architect-fa.md`.
    Catches: a skill that teaches producer-only kill-checks (the E260–E288 shape: 572 green tests,
    zero production callers) and a prompt that lets a planner present an uncalled module as done.
    kill: remove-call tests/test_delivery_law_conformance.py::test_each_surface_states_the_law -> _TOKENS
  CT115 [FUNCTIONAL]: a workflow that cannot publish a repaired plan refuses BEFORE spending a
    planner call, with a closed reason distinct from a bad plan. Today an absent publisher is reported
    as `prepare-failed` (`workflow_controller.py:2293-2294`), the same code a failed validation
    produces (`:2291`), only after the planner ran (`:2401`) and the candidate was unlinked (`:2451`).
    After: the supplier is proved in `_admit_plan` before `state.planner_calls += 1` (`:2558`) on the
    repair/replan branch only, so a valid plan on an unmanaged run still admits; the refusal is
    `promotion/managed-execution-absent` in `admission.json`; the stage is never dispatched; the
    candidate directory is never created. `_promote_validated_plan` loses its optional publisher
    (`:2281`, `:2293-2294`) and its unused `workspace` parameter (`:2290`), so no call site can omit
    the port.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_admit_plan -> _require_managed_publisher
  CT116 [FUNCTIONAL]: exactly one composition supplies both controller-side managed ports — the plan
    publisher to `run_workflow` and the workspace provisioner to `SessionManager`.
    `ExecutionBinding` (frozen: `namespace`, `workspace_id`; no capability, no revision) is data;
    `managed_execution_for_run(...)` is the only constructor of `ExecutionClient` in `src/`
    (there is none today: `git grep "ExecutionClient(" src` is empty) and returns `None` when no
    supervisor endpoint is configured, never minting a grant implicitly;
    `BoundPlanPublisher(managed, binding)` is the adapter the controller port
    (`plan_promotion.py:32 CandidatePlanPublisher`) sees, and it cannot hold a token because it has no
    such field. `ExecutionClientPlanPublisher` (which held a `_owner_capability: str` and a cached
    `_base_revision`) is deleted in favour of `ExecutionClient.publish_plan`, and the verb takes the CAS
    base from the CREATE_VIEW reply rather than from any field it keeps. The second port is
    `ClientWorkspaceProvisioner` (`session/provisioning.py:66 WorkspaceProvisioner` =
    `Callable[[ProvisionRequest], ProvisionedWorkspace]`) over `register_workspace`, using the reply the
    wire already defines — `{workspace_id, revision_id}` (spec `:153`, `service.py:591`) — so the port is
    built without moving a single byte of schema; the local `ProvisionedWorkspace` rule that demanded a
    `tree_sha256` for a registered result (`session/provisioning.py:53-59`) is relaxed to match a wire that
    never carried it and a caller that never reads it. The endpoint is one string in the config file `fa`
    already reads: `~/.fa/config.yaml` (`config.py:44`) gains a top-level `execution:` block with
    `service_config: <absolute path>`, read by a **sibling** reader `load_execution_config` in `config.py`
    that reuses `iter_yaml_lines` and leaves `load_capabilities`' `capabilities:`-only contract untouched.
    That path is the same JSON `service.read_config_file` (`service.py:290`) already validates for the
    supervisor — one file, one validator, two consumers, no environment variable, no endpoint file, no
    autodiscovery, and no change to `supervisor --config`.
    The roots are `cli.py::_cmd_workflow`, which calls `run_workflow` at `:1431` and passes no
    publisher today, and `cli.py::_session_manager_for_args` (`:247`), which builds the manager at
    `:266-272` with a readiness preparer and no provisioner.
    kill: remove-call src/fa/cli.py::_cmd_workflow -> managed_execution_for_run
  CT117 [FUNCTIONAL]: a plan publication is a patch, not a snapshot. The base-equality precondition is
    removed from the candidate path only (`workspace.py:3492-3493` in `_closed_candidate_reader`
    `:3464`); the per-file CAS (`_plan_source_identity`'s `old_sha256`) and every provenance predicate
    stay. `CREATE_VIEW.base_revision` becomes nullable for `CANDIDATE`/`VERIFICATION`
    (`protocol.py:102`); `PUBLISH.expected_base_revision` stays a required `rev-` id and keeps its
    equality against the view's base (`:334`), because the view pins that base at `create_view`
    (`workspace.py:1684-1691`) — the publish still proves it acts on the view it was granted, it just
    no longer demands that nothing else changed in the workspace. The authority already accepts
    `base_revision=None` (`create_view` `:1911`, CAS only when non-null `:1932`), so null means "the
    bytes current when the copy starts", never "whatever is convenient" — and the pre-reservation proof
    resolves a null base the same way, against `binding.current["revision_id"]` (`_authorize_operation`,
    E294): a nullable field honoured by only one of the two paths is a trap, and until E294 this one
    surfaced on the wire as `BACKEND_UNAVAILABLE` rather than as the refusal it was. A publish whose
    intent equals the current tree returns the current revision with `already_published: true` instead
    of `INPUT_POLICY` from `_plan_prepare`'s "a replacement must replace something" (`:3533-3534`), so
    a re-attempt of an intent already applied is not misread as a refusal. The predicate is exact and
    already in the code — `_plan_prepare` refuses when `sha256(buffer) == plan_ref.sha256`
    (`:3533-3534`), i.e. when the buffer *is* the committed plan — so the `already_published` branch
    writes nothing at all: no `_write_intent`, no `os.replace`, no revision, and the reply carries the
    current `revision_id`/`tree_sha256` with the request's own `plan_ref`, which lets the caller's
    `RELEASE` settle normally. A failure *before* the replace is not a new hazard either: both `except`
    arms call `_plan_abort` (`:3445-3450`), so an in-flight intent never outlives a failed attempt; only
    "replace succeeded, `_plan_finish` failed" leaves an intent behind, and that is spec §5.1's
    forward-only point (`:3452`), owned by recovery — not a case this slice invents. The new reply field is
    v1-compatible by exactly one row in the journal's added-field table: a stored pre-change publish
    record is read and served as `already_published: false`, logged once, with its bytes untouched —
    no schema-version bump, no frozen schema copies, no new instruction surface (Q93-B, 2026-10-31).
    kill: remove-call src/fa/execution/workspace.py::publish_candidate_plan -> _already_published
  CT118 [FUNCTIONAL]: no bearer grant is stored as a `str` field outside `fa/execution/types.py`.
    `ExecutionClient.request` (`client.py:104-155`) takes `grant: GrantReply | None`, validates the type
    and unwraps it once inside `encode_json`; the grant a caller keeps is a `GrantReply` (composition,
    `ManagedBashExecutor`), never a string field, and `type`/`repr()`/`vars()` of those objects expose no
    64-hex value. Scoped down 2026-10-31: the four reply-wrapping sites and a separate grants bank were
    dropped — they restated the type at call sites that already pass a `GrantReply` — leaving one
    assertion in the existing client bank.
    kill: remove-call src/fa/execution/client.py::ExecutionClient.request -> GrantReply.to_wire_capability
  CT119 [CONSTRAINT]: a validated candidate that cannot be published is retained, not discarded — one slot per run (`.fa/admission/<run_id>/draft.md`), replaced atomically so the current draft is never lost during replacement (Q100, 2026-11-01).
    Operator ruling (2026-10-31, option B). The bytes are re-materialised in the directory the planner
    draft already lives in — `.fa/admission/<run_id>/` (`plan_promotion.py:71`) — through the existing
    `_private_artifact_directory` (`workflow_artifacts.py:566`) and the existing write primitive
    `_create_candidate` (`plan_promotion.py:81`, `O_EXCL` on `:85`, 0600, fsync of file and directory,
    unlink of a partial file). Two preconditions are this contract's own, not carried over from the
    draft path: the retained name is the **content hash** (`plan-<sha256>.md`; the live draft name is
    `candidate-<uuid4().hex>.md`, `plan_promotion.py:71`, `client.py:194`), and `O_EXCL` must therefore
    be read as *create-or-confirm*, not *create-or-fail* — an existing file with the same content hash
    is success after its bytes are compared, any other `EEXIST` is a retention failure reported as one
    warning. Hence the count is bounded by `planner_limit`: no cap, no eviction, no new module, and
    `retain_plan_draft` lives in `plan_promotion.py` beside the primitive (`:81`) — putting it in
    `workflow_artifacts.py` would close an import cycle, because `plan_promotion.py:18` already imports
    `_private_artifact_directory` from there. Nothing is written when publication succeeds,
    and a retention failure never masks the `PlanPromotionError` it accompanies. The admission record
    already names the bytes: the blocked attempt carries `candidate_sha256`
    (`workflow_controller.py:2383`), so the file is findable without a schema change.
    Catches: retaining into the canonical plan path, into `.fa/runs/` (a namespace that does not
    exist: `admission.json` lives in `~/.fa/session-log/<run_id>/`, `workflow_controller.py:156-157`),
    or writing before knowing that publication failed.
  CT120 [CONSTRAINT]: the candidate buffer's location is not a payload field. `candidate_scope.candidate_path`
    is removed from the wire (schema `protocol.py:105`, `_candidate_scope` `:285`, `_candidate_buffer`
    `:2248`, the service routes and their banks): it names a buffer that is always the single file
    `candidate` inside the view directory (`_buffer_bytes` `:2261`) and E259 forbids a path in the payload,
    so the field is a caller-supplied path where the authority already owns the answer. The name stays
    `candidate-<hex>.md` on the controller's host path (`plan_promotion.py:71`, `client.py:194`) — no
    module, function or directory renames: scoped down 2026-10-31 because a rename moves no behaviour and
    touches every importer, which is the opposite of what this slice is for.
    Catches: a schema change that drops a validated field without proving the remaining cross-field rules
    still hold, and a "cleanup" that renames live symbols for taste.
  CT121 [PRESERVATION]: sealed publication and recovery are untouched: `publish_view` keeps its
    `expected_base_revision` CAS and its `SEALED`-only path, `verify_publication` stays the replay
    owner, `_recover_intent`/`_recover_plan` keep forward-only semantics and `intent["next_revision"]`
    as the revision source, one writer per run remains, and every existing bank
    (`test_workspace_publication.py`, `test_workspace_recovery.py`, `test_execution_purposes.py`,
    `test_execution_service.py`, `test_execution_protocol.py`, `test_execution_client.py`) stays green.
TESTS: tests/test_delivery_law_conformance.py (NEW), tests/test_plan_candidate_retention.py (NEW),
  tests/test_execution_composition.py (NEW),
  tests/test_workspace_publication.py, tests/test_execution_protocol.py, tests/test_execution_service.py,
  tests/test_execution_client.py, tests/test_verify_gate_live.py, tests/test_workspace_recovery.py,
  tests/test_execution_purposes.py, tests/test_skill_conformance.py
```verify
uv run pytest tests/test_delivery_law_conformance.py tests/test_plan_candidate_retention.py tests/test_execution_composition.py -q
uv run pytest tests/test_workspace_publication.py tests/test_workspace_recovery.py tests/test_execution_purposes.py tests/test_execution_protocol.py tests/test_execution_service.py tests/test_execution_client.py -q
uv run pytest tests/test_verify_gate_live.py tests/test_skill_conformance.py -q
uv run python scripts/check_execution_e2e_coverage.py
```
- [x] STEP1: land CT114 on all six surfaces and add `tests/test_delivery_law_conformance.py`: per surface a token list that must be present (`EDGE mutant`, `SUPPORT`, `rooted-by`, `supplier`, `## Delivery` where the surface owns a plan shape) plus a damage test that mutates a copy of the surface (delete the section, or replace `EDGE` with `PRODUCER`) and asserts the checker flags it; do not touch the `PLAN-SKELETON` markers, the schema §4 example, or `tests/test_skill_conformance.py`'s assertions **Progress (2026-11-01, E303).** All six surfaces already carried the law; what was missing was the proof that the text is load-bearing. `tests/test_delivery_law_conformance.py` reads the seven files of the six surfaces (`plan-authoring/SKILL.md`; `tests-writing/{SKILL,INJECT}.md`; `feature-planning/{SKILL,INJECT}.md`; `inner_loop/prompt.py`; `prompts/architect-fa.md`), holds one token list per file, and asserts the vocabulary a planner must read is present: the liveness ladder and `cutover`/`I-IP-7`, `L1`-`L3` and `I-TW-22`, `SUPPLIER`/`ROOT`/`EDGE`/`anti-pattern`, `## Delivery`, `self-check`, `final message`, `rooted-by`, `supplier`. Every token was grepped in the tree before it was written down, so the lists describe the artifacts rather than a wish. **8 passed**: one whole-table test plus a two-damage test per surface — the first renames the surface's lead token to `PRODUCER` (the E260-E288 softening), the second deletes every line that carries a required token (the "section was dropped" edit) — and both must be flagged. **Kill-checks:** emptying `_TOKENS` fails the count assertion (1 failed, 1 skipped), and forcing a token that is not in the artifact fails the whole-table test (1 failed, 7 passed); the file was restored byte-identically after each. A third probe taught something worth keeping: `PRODUCER` *is* present in `tests-writing/INJECT.md` as the anti-pattern word, which is exactly why the damage test renames rather than asserts absence. `tests/test_skill_conformance.py` untouched and green (24 passed together with the new bank); `PLAN-SKELETON` markers, the schema §4 example and the skill assertions were not modified. (exit: new suite green, the damage mutant is caught for each of the six surfaces, `tests/test_skill_conformance.py` unchanged and green)
- [x] STEP2: implement CT115. Add `_require_managed_publisher(ctx) -> CandidatePlanPublisher` raising `PlanPromotionError("managed-execution-absent")`; call it in `_admit_plan` immediately before `state.planner_calls += 1` (`:2558`), which is inside the `while True:` repair/replan loop and therefore never reached by a plan that admits (`:2545-2549`); pass the result as an explicit `publisher=` argument of `_run_admission_repair` and make `_promote_validated_plan` take a required `publisher`, deleting the `publisher is None` branch (`:2293-2294`) and the unused `workspace` parameter (`:2290`, call site `:2455-2458`). Extend `ADMISSION_RULES["promotion"]` (`admission_schema.py:46-55`) with `managed-execution-absent`. Tests, in `tests/test_s8_workflow_controller.py`, the bank that already owns the repair round (`test_s8_repair_exhausted_maps_to_its_own_stop_reason`, `:292`): a diagnostic plan with no publisher → `admission.json` holds exactly one attempt `{validator: promotion, rule: managed-execution-absent}`, status `BLOCKED`, and the injected `run_stage_fn` was never called (this is the binary stand-in for `planner_calls == 0`, which the record does not store), no `.fa/admission` directory created, canonical sha unchanged; control: a valid plan on the same unmanaged run admits and runs; EDGE mutant: delete the call → the stage runs, the candidate is deleted, the test fails **Progress (2026-11-01, E299).** `_require_managed_publisher(ctx) -> CandidatePlanPublisher` raises `PlanPromotionError("managed-execution-absent")`, is called immediately before `state.planner_calls += 1` and its result is threaded as `publisher=` into `_run_admission_repair`; `_promote_validated_plan` now requires the port and lost the unused `workspace` parameter, so no host fallback can be re-introduced by omission; `ADMISSION_RULES["promotion"]` carries the new rule. Tests: `tests/test_s8_workflow_controller.py::test_s8_a_repair_without_a_managed_publisher_is_a_named_refusal` — an inadmissible explicit plan on an unmanaged run exits 2, `admission.json` records `EXPLICIT_INPUT` then `ADMISSION_REPAIR`, both `BLOCKED`; the repair attempt's diagnostics are exactly `{validator: promotion, rule: managed-execution-absent}`, `.fa/admission/<run_id>` never appears and the canonical bytes are unchanged; `tests/test_verify_gate_live.py` pairs the refusal with a passing control (a run that has the port gets the same object back). Three mutants killed, sources byte-identical: the guard never raising, `_admit_plan` bypassing it, and the rule unregistered. **Sandbox limit, stated rather than hidden:** the step's control case ("a valid plan on the same unmanaged run admits and runs") cannot be reproduced here — it stops at `fa workflow: admission blocked: baseline-unavailable`, the same environment class as the 100-odd pre-existing failures in those banks; the seam-level control above is what this box can prove. The nine workflow banks measure 102 failed / 657 passed against 108 failed / 650 passed on the tree without this change, so the refusal fixed flag-expectation tests and broke none. (exit: suite green, EDGE mutant caught, `prepare-failed` unreachable from the unmanaged path)
- [x] STEP3: implement CT119. In `_run_admission_repair`, wrap the `_promote_validated_plan` call (`:2455-2458`) so that a `PlanPromotionError` is caught, the bytes captured before the cleanup `finally` (`:2451`; they are the in-memory `candidate` read at `:2444`, so cleanup cannot lose them) are written by a new `retain_plan_draft(workspace, run_id, raw, *, deadline)` in `inner_loop/plan_promotion.py`, beside `_create_candidate` (`:81`) and reusing `_private_artifact_directory` (imported at `:18`; putting the helper in `workflow_artifacts.py` instead would close an import cycle); target `.fa/admission/<run_id>/plan-<sha256>.md`, the directory the candidate already occupies; an existing file whose bytes equal the hash is left untouched and is not an error, any other `EEXIST` is, and the original error is re-raised; a failure inside retention is logged as one structured warning and never replaces the original rule. Tests in `tests/test_plan_candidate_retention.py`, with the ordinary-path control staying in `tests/test_s8_workflow_controller.py`: an injected publisher failure → the file exists with exactly the candidate's sha256, canonical plan unchanged, admission `BLOCKED` with the publisher's rule; success → no file; two failures with the same bytes → one file, no error, two failures whose bytes differ → two files, no error and no eviction of the first; a retention failure → the admission rule is still the publisher's **Progress (2026-11-01, E300).** `retain_plan_draft(workspace, run_id, raw, *, deadline=None)` sits beside `_create_candidate` and reuses it plus `_private_artifact_directory`, so the draft has the candidate's exact writer: `O_EXCL|O_NOFOLLOW`, `0600`, `fsync` of the file and the parent. The name is `plan-<sha256>.md`, which is what lets CT120 locate the buffer without a payload path. A same-bytes `EEXIST` is success (a refusal can be replayed), any other content under that name is `prepare-failed` and is never overwritten or evicted — the name promises content, so a mismatch there is corruption, not a retry. `run_id` is refused when it is a path (`/`, `.`, `..`, NUL) and retention writes nothing after the run's own deadline; both are `scope-denied`/`prepare-failed` before any IO. The controller wraps only the promotion call (`_run_admission_repair`), retains `validation.snapshot.utf8_bytes` — the in-memory bytes, because the candidate leaf is already unlinked in the `finally` above — and re-raises the publisher's own rule; a retention fault is one `plan.draft.retained=false` warning and never becomes the admission rule. Bank `tests/test_plan_candidate_retention.py` **8 passed**: the refused bytes land under their exact digest with `0600`, the candidate is still cleaned up and the canonical file untouched; a *successful* promotion retains nothing (the control that makes retention a property of the failure); same bytes twice is one file, different bytes are two with no eviction; a foreign file and a symlink under the digest are refused with the foreign bytes intact; a path-like `run_id` and a spent deadline both refuse before creating `.fa`. **7/7 mutants killed** (retention on the success path, name not the digest, retention replacing the rule, foreign file tolerated, controller swallowing the refusal, deadline ignored, path-like run id accepted), sources byte-identical. The nine workflow banks plus this one: **101 failed / 665 passed**, FAILED set identical to the tree before this step, so no regression; `python -c "import fa.inner_loop.plan_promotion"` ok and the `workflow_artifacts` import count in `plan_promotion.py` is still 1. (exit: suite green, retention is not a side effect of the success path, no schema field added, `python -c "import fa.inner_loop.plan_promotion"` succeeds and `git grep -c "workflow_artifacts import" src/fa/inner_loop/plan_promotion.py` stays 1)

    **Amendment 2026-11-01 (Q100, operator).** Retention keeps **one** draft per run, not one per digest: `.fa/admission/<run_id>/draft.md`, replaced atomically (private temporary file in the same directory, `fsync`, then `os.replace`), so a refused draft is never lost *during* the replacement — the old bytes survive any failure before the rename and the rename itself is atomic. The digest name's two stated jobs did not survive inspection: nothing in `src` reads a `plan-<sha256>.md` name, and the authority's CANDIDATE buffer is located from the pinned `plan_ref`, never from this file (E300's sentence tying the two together was wrong — corrected in E305). Attempt evidence was already durable without the file name: `admission.json` records `candidate_sha256` per attempt. The file-name contract in this bullet (`plan-<sha256>.md`, same-bytes `EEXIST` is success, foreign file refused) is superseded by that paragraph; the writer discipline (`O_EXCL|O_NOFOLLOW`, `0600`, `fsync`, deadline, `run_id` scope) is unchanged.
- [x] STEP4: implement the wire half of CT117 in `execution/protocol.py`: `CREATE_VIEW.base_revision` (`:102`) becomes `_nullable(_id("rev-"))`, `_PUBLISH_REPLY` (`:145`) gains `already_published={"type": "boolean"}`, and the decoder gains two cross-field rules — a null `base_revision` only for `CANDIDATE`/`VERIFICATION`, and `already_published: true` only with a non-null `plan_ref`; `PUBLISH.expected_base_revision` (`:126`) is **not** relaxed (the view pins its base, so the equality at `:334` is still provable) and the sealed publish producer emits `already_published: false`. **Progress (2026-11-01, E289).** The wire half is implemented and locally proved: nullable `CREATE_VIEW.base_revision` accepted only for CANDIDATE/VERIFICATION, `already_published` on `_PUBLISH_REPLY` with the plan-bound cross-field rule, both producers updated (`_published_receipt`, `PublishResult`/`PlanPublishResult`), and the one-row journal compat table filling a pre-change PUBLISH record for validation and for the served copy without rewriting its bytes (438 local tests; four mutants killed). **Box ticked 2026-11-01 (E298).** The only blocker named here was the authority half, and that is STEP5, closed in E291: the wire half is in the tree (`protocol.py:106` nullable base, `:159` `already_published`, `:385` the plan-bound cross-field rule) and the protocol/service/client banks are green in the same `/tmp/vt` toolchain every closure since E291 uses. The 3.11-collection caveat is the toolchain note, not a missing deliverable. **Amendment 2026-11-02 (E304):** the key was added as *required* without a protocol bump, so the newer reader (`decode_reply(..., tolerate_legacy=True)`, used only by `ExecutionClient`) treats a reply that predates it as `already_published: False` — a server without the repeat path always committed. The server's own self-check stays strict, and the opposite direction (an older client against a newer server) is not repairable from here: client and supervisor are upgraded together.
 **The reply field is journal-visible, and the answer is one compatibility table (Q93 decision B, 2026-10-31).** `journal._validate_record` (`journal.py:130-131`) re-checks every stored `DONE` against the *current* `protocol.RESULTS`, `_PUBLISH_REPLY` is a closed `_object` (all keys required, `additionalProperties: False`, `protocol.py:25-26`), and one mismatch becomes `CORRUPT_STATE` (`journal.py:222-235`) on the start-up path `WorkspaceAuthority.__enter__` → `recover_uncertain` (`workspace.py:965`) — so a bare required key bricks a sandbox whose journal predates the change. The seam is deliberate and small: a module-level `_ADDED_REPLY_FIELDS: dict[Operation, dict[str, tuple[Any, str]]]` in `journal.py` with exactly one row — `PUBLISH: {"already_published": (False, "v1 records predate the flag; a DONE publish did the write")}` — and one pure `_complete_result(op, result) -> tuple[dict, tuple[str, ...]]` that copies, fills only listed keys that are *absent*, and returns the filled names. It is called in two places, both inside `journal.py`: `_validate_record` validates the completed copy, and `lookup` returns a completed **copy** — never the stored dict — so no write path can persist the fill and the on-disk record keeps its original bytes. Serving an upgraded record logs exactly one `logger.warning("journal.compat.filled", op=..., operation_id=..., fields=...)` per (record, field) per process (a module set guards the repeat), which is the failure-observable half: the agent sees the filled field in the log, not a silent default. Boundaries, all tested: an unknown **extra** key is still `CORRUPT_STATE`; only additive fields may ever be listed, never removed or renamed ones; the default is a constant and is never derived from workspace state or from another field; the table does not apply to records whose `result` is null. No schema-version bump, no frozen v1 schema copies, and no instruction added to any skill or prompt — A was rejected on 2026-10-31 as a larger surface for a rarer read. Update `test_execution_protocol.py` with the refusal and acceptance matrices, and `test_workspace_recovery.py`/`test_execution_service.py` with one seeded pre-change `PUBLISH` record read back after the change (exit: protocol suite green, two new refusals and one accepted-shape matrix proved, `_COMMITTED` untouched for `install_project`, a seeded pre-change `PUBLISH` `DONE` record reads without `CORRUPT_STATE`, `lookup` returns `already_published: false` with the stored file's bytes unchanged, the fill is logged once, an added unknown key still raises `CORRUPT_STATE`, and two EDGE mutants are caught — deleting the `_complete_result` call from `_validate_record` bricks the read, deleting it from `lookup` serves a result the current decoder refuses)
- [x] STEP5: implement the authority half of CT117. Delete the base-equality comparison in `_closed_candidate_reader` (`:3492-3493`) and leave every other predicate in that method; add `_already_published(binding, plan_ref, buffer)` (validating the target shape through `_plan_parts` first) and call it in `publish_candidate_plan` after the buffer read (`:3433`) and before `_plan_prepare` (`:3436`), returning the current `revision_id`/`tree_sha256` with the intent's `plan_ref` and `already_published: true` — no intent write, no stage, no replace, no new revision directory. The view is still settled by the caller's RELEASE. Update the mutants: re-adding the base comparison must fail "publish after an unrelated commit succeeds", and removing `_already_published` must fail "an applied intent is reported as applied" **The already-applied branch must be inert, and the failure matrix belongs to the contract.** When `sha256(buffer) == plan_ref.sha256` the authority returns the current revision without writing: no `_write_intent`, no `os.replace`, no new `rev-`, `projection_complete` stays true and `plan_ref` is the request's own. That this is *all* the change needs is visible in the file already — `_plan_prepare` refuses exactly that case (`:3533-3534`), `_plan_abort` (`:3676-3683`) discards this attempt's staging and intent whenever anything before the replace fails, and `_plan_finish`'s docstring (`:3686-3693`) states that nothing after the replace is undone, so the intent stays for forward recovery and the authority stops serving. Four rows, each with an observable: intent equal → canonical bytes and `current.json` byte-identical, no `rev-` appears, reply `already_published: true`; intent differs → exactly one replace and one new revision; failure injected before the replace → canonical bytes identical, `intent.json` absent, temporaries swept (`.plan.<uuid>.publish`, `:3572`); failure injected after the replace → `intent.json` present, the next `acquire_writer` refused `WORKSPACE_BUSY` (`_forward_gates`, `:3739-3751`), recovery the only thing that clears it. The last row is what stops a green suite from lying about durability.  **Progress (2026-11-01, E291).** Landed: the candidate view's base is no longer compared to current (patch semantics), `_already_published` short-circuits before any staging and answers with the committed revision, `already_published: true` and the request's `plan_ref`; the same `_forward_gates` still run and the view is settled so `RELEASE` follows. Two legacy assertions were rewritten to the new contract (patch after an unrelated commit; a fresh identical request is a repeat, not `STALE_REVISION`), and three tests were added (patch, stale plan bytes via the per-file CAS, repeat twice with no write). 549 passed in the affected set; both mutants killed. **Exit reproduced at `d9b4cb4`, so the box is ticked (E291):** publication and recovery banks green, both mutants killed with byte-exact restoration, and no added test hardcodes a `rev-` literal — the new assertions compare against the reply; host re-runs are SLICE6 STEP5's work, not this step's exit. (exit: publication and recovery banks green, both mutants caught, no regenerated `rev-` literal left in a fixture)
- [x] STEP6: implement CT118, scoped down. `ExecutionClient.request` takes `grant: GrantReply | None` and unwraps once at `"capability": grant.to_wire_capability() if grant is not None else None`; `GrantReply.to_wire_capability()` lands in `types.py`; the composition and `ManagedBashExecutor` keep a `GrantReply`, never a string field. One assertion in the **existing** `tests/test_execution_client.py`: `repr()` and every `vars()` value of the client, the executor and the composition adapter contain no `[0-9a-f]{64}`, no receipt, event or tool result carries the grant, and `to_journal_result` still refuses a projection containing it. No reply-wrapping sites beyond the composition that consumes them, and no new test file **Progress (2026-11-01, E293).** `request(..., grant: GrantReply | None)` unwraps once, at the frame; a bare string is refused before the socket is touched; `GrantReply.to_wire_capability()` is the only unwrap; `ManagedBashExecutor` and the CANDIDATE adapter hold a `GrantReply`, and `_grant()` (module-private in `client.py`) is the single reply→grant conversion. `tests/test_execution_client.py` gained one test: the frame still carries the capability, no holder exposes it through `repr`/`vars()`, and a string grant never reaches the server. 191 passed, three mutants killed, `capability` survives in `client.py` only inside the frame literal. (exit: client bank green, the assertion fails if a hex grant reaches any attribute reachable by `vars()`, `git grep -c "test_execution_grants" tests` is 0)
- [x] STEP7: implement the client verb and delete the adapter (CT116/CT118). Add `ExecutionClient.publish_plan(binding, source, candidate, *, grant: GrantReply, deadline)` carrying the saga now in `ExecutionClientPlanPublisher.publish_candidate` (`client.py:180-266`): CREATE_VIEW with a null base and the pinned `plan_ref`, WRITE_FILE into the scoped buffer, STOP_VIEW requiring `terminal is True`, PUBLISH with `sealed_manifest_id: null`, the `plan_ref` identity check, `already_published` passthrough, and RELEASE only on a determinate outcome; **the base the PUBLISH CAS must carry is the one the CREATE_VIEW reply returned** (`view.base_revision`, `protocol.py:56-64`, enforced against the view at `:334`), never a cached client field — the adapter being replaced sends its own `_base_revision` (`client.py:265`), which is set at construction and re-set only after a successful publish, so after any other commit in the same workspace the pair mismatches and the publish is refused; delete the class and `_release_candidate_best_effort` (`:268-283`), move its tests into the client's bank as one saga test plus one uncertainty test that asserts the view is *not* released and that no second commit happens **Who releases, and when, is a rule rather than a habit.** The publication sends its own `RELEASE` on every *determinate* outcome — success, a typed refusal before any durable effect, and the `already_published` case — from the same `finally` that releases the view, so a refused publish never leaves the workspace `OWNED` by this client. An *indeterminate* outcome (`DURABILITY_UNKNOWN`, `EXECUTION_UNKNOWN`, `TERMINALITY_UNKNOWN`, `CORRUPT_STATE`) is the opposite: the client must **not** release, because releasing asserts the writer is settled and that is precisely the assertion the authority cannot make. The workspace stays unsettled, `acquire_writer` refuses (`:1326-1338`) and recovery owns it; the uncertainty test asserts no `RELEASE` frame was sent and that a second attempt is refused rather than quietly succeeding. The bug this names is a `finally` that releases unconditionally: it looks safer and fabricates certainty. **Progress (2026-11-01, E294).** `ExecutionClient.publish_plan(binding, source, candidate, *, grant, deadline)` carries the saga and returns `PlanPublication(plan_ref, revision_id, already_published)`; `ExecutionClientPlanPublisher` and `_release_candidate_best_effort` are gone and `git grep -c ExecutionClientPlanPublisher src tests` is 0. Two defects fell out of the move. First, the PUBLISH CAS now carries `view.base_revision` from the CREATE_VIEW reply, so a commit made between construction and publication can no longer leave the pair stale — the adapter's cached field is what made it possible. Second, `CREATE_VIEW` on a null base is legal on the wire for CANDIDATE (`protocol.py:330`) but `WorkspaceAuthority._authorize_operation` still called `_hex_id(base_revision)` for every create, so the null path died as `ExecutionContractError` and surfaced as `BACKEND_UNAVAILABLE`; the authority now resolves a null base to the current revision and keeps `STALE_REVISION` for a named one. Release is one `finally` gated on determinacy: a typed refusal and the `already_published` repeat release the view, while `EXECUTION_UNKNOWN`, `TERMINALITY_UNKNOWN`, `DURABILITY_UNKNOWN`, `CORRUPT_STATE` and a reply whose `plan_ref` is not the pinned one leave it open for recovery and are named by the uncertainty test. 197 in the client bank, 223 service+client, **1341 passed / 1 skipped** across the 29 execution+workspace banks; six mutants killed (CAS from the grant, a named base at CREATE_VIEW, release always, never release, trusting the reply's `PlanRef`, and the authority's null-base rule) with byte-exact restoration. (exit: `git grep -c ExecutionClientPlanPublisher src tests` is 0, both tests green, no `RELEASE` frame on the uncertainty path)
- [x] STEP8: add `src/fa/execution/composition.py` with `ExecutionBinding` (frozen: `namespace`, `workspace_id`), `ManagedExecution` (client + binding + the run's one `GrantReply`) and `managed_execution_for_run(run_context, *, config_path=None, deadline) -> ManagedExecution | None` — `run_context` alone carries the run id (the namespace) and the workspace path, so no second context parameter is threaded — the only `ExecutionClient(...)` in `src/`. The endpoint is one string in the config file `fa` already reads: `~/.fa/config.yaml` (`config.py:44 DEFAULT_CONFIG_PATH`) gains a top-level `execution:` block with `service_config: <absolute path>`, parsed by a new sibling reader `load_execution_config(text) -> Path | None` in `config.py` (reusing `iter_yaml_lines` and `strip_inline_comment`); `load_capabilities` and its `capabilities:`-only contract stay untouched, so the module's two sections remain independent. That named path is the same JSON the supervisor validates with `service.read_config_file` (`service.py:290`), and the composition calls that same reader — one file, one validator, two consumers. It keeps `socket_path` and `rpc_timeout_ms`, refuses unless `os.getuid()` is in `config.controller_uids`, and builds `ExecutionClient(socket_path, server_uid=os.getuid(), rpc_timeout_ms=...)` (`client.py:85-93`), with `_connect_authenticated` (`:65-81`) still proving the socket owner. The workspace identity comes from one `register_workspace{create:false, input_id:null}` whose `{root_id, relative_root}` is derived from `workspace_path` against `approved_roots` — idempotent, because an existing binding for that root is returned as-is (`workspace.py:1193-1216`). Absent key, unreadable or invalid file, a uid outside `controller_uids`, or a workspace under no approved root → `None`, never a minted grant and never a default socket; no environment variable, no endpoint file, no autodiscovery, and no change to `supervisor --config`. **Amendment 2026-11-01 (E295): the writer is acquired once per run, not once per publication.** `managed_execution_for_run` sends one `ACQUIRE_WRITER` (`ACQUIRE_WRITER` refuses unless the workspace is `AVAILABLE`, `workspace.py:1326-1338`; a second acquisition of the same workspace is `WORKSPACE_BUSY` by construction) and returns it inside `ManagedExecution(client, binding, grant)`; `BoundPlanPublisher` is a pure adapter over that grant and refuses any binding other than the one it was composed with, and `_cmd_workflow`'s single `finally` calls `ManagedExecution.close()`, which sends one `RELEASE` and returns `False` — logged, never retried — for a typed refusal, an unavailable endpoint or `EXECUTION_UNKNOWN`. The previous wording (acquire and release around each publication) contradicted this step's own type list, which puts the run's one `GrantReply` on `ManagedExecution`: a per-publication release would make the second publication depend on a `RELEASE` that the first publication's indeterminate path deliberately does not send, and it would leave the run's writer unsettled between stages. `create_view` still re-proves `active_actor == namespace` on every publication, so the grant is per-run but the authority is not weakened (CT118). Wire `cli.py::_cmd_workflow` to build it after `resolve_workflow_workspace` (`manager.py:469`, called at `cli.py:1405`) and pass `plan_publisher=` into `run_workflow` (`:1431`). **One resolver, both commands — narrowed in E295 to what has a consumer.** `managed_execution_for_run` is that resolver: one `load_execution_config` read, one `service.read_config_file` validation, one `register_workspace` identity per workspace, and `grep -rn "ExecutionClient(" src` is one line, so a second resolution path cannot exist without a second construction site. `fa workflow` is its only caller until a second command consumes the authority: the chat/manage path (`_session_manager_for_args`, `cli.py:247`, manager built at `:266-272`) has no plan publication and no managed I/O yet, so wiring a writer grant into it would acquire and release a grant nothing reads — the E288 shape (a helper whose only caller is a test) in mirror image. The two-command test and its EDGE mutant (a literal second config file must be detected) move to STEP9, which gives the chat path its consumer through `ClientWorkspaceProvisioner`; they are named there, not dropped. Tests `tests/test_execution_composition.py`: no `execution:` key → `None` and CT115's rule; a temp config naming a temp service JSON over the in-process supervisor → binding fields match the registered workspace and `publish_plan` reaches a real commit; a socket whose uid is not the controller's → refused, not connected; EDGE mutant deletes `plan_publisher=` at `:1431` and the "workflow publishes a repaired plan" test must fail **Progress (2026-11-01, E295).** `src/fa/execution/composition.py` (214 lines: the three types plus the two private resolvers) is the only module that constructs a client; `config.py` gains `load_execution_config` beside `load_capabilities` from the same `iter_yaml_lines`/`strip_inline_comment` primitives and the capability reader is untouched; `cli.py::_cmd_workflow` resolves the run's execution after the lifecycle (`:1436`), passes `plan_publisher=` (`:1459`) and releases the writer in one `finally` (`:1461-1463`). `grep -rn "ExecutionClient(" src` = **1** (composition `:158`). Bank `tests/test_execution_composition.py` **9 passed**: no block, no file and three unusable blocks (relative, `..`, unknown key) → `None`; against a live in-process supervisor built from the same JSON, a control run is managed and a foreign-uid document, a workspace outside every approved root and the approved root itself all return `None` **while a listening socket beside them records zero connections** — the guard refuses, not a dead endpoint; the happy path commits a real plan and reads the promoted bytes back; another run's binding is refused by the publisher; `close()` returns `True` and a fresh composition acquires the writer again, so the release really happened; a refusal, an unavailable endpoint and `EXECUTION_UNKNOWN` each return `False` from exactly one `RELEASE` with no retry. `tests/test_config.py` **26 passed** with the reader's one positive shape and nine unusable ones. 15/15 mutants killed (uid, containment, root-itself, binding guard, `create:true`, namespace without the session id, legacy-path raise, publisher ref, release-refusal-reported-as-success, the three config shapes, and both CLI EDGE mutants: `plan_publisher=` deleted and `close()` deleted), sources restored byte-identical. Execution+workspace banks **1350 passed / 1 skipped**; `test_cli_ergonomics` (14) and `test_s10a` (1) fail identically on `087993e` without these changes — they need a real git workspace and the repository cwd. `ruff check`/`format --check` and `git diff --check` clean. **Amendment 2026-11-02 (E304, external review).** An uncertain `ACQUIRE_WRITER` is not "no managed execution": the authority may have issued the writer against a frame nobody read. `_control` replays the same request id once (the journal plus the completed-reply cache answer a repeat with the original grant, which is a reconciliation and not a second effect), and a still-unconfirmed answer raises `ExecutionUncertainError` out of `managed_execution_for_run`; `_cmd_workflow` turns that into one operator line and exit 2. Registration stays non-committal: `create:false` mints nothing, so an unreadable answer there is still `None`. (exit: suite green, EDGE mutant caught, `git grep "ExecutionClient(" src` shows exactly one site, the file both processes read is proved by the same test that proves the commit, `load_capabilities` tests unchanged)
- [x] STEP9: implement CT116's second port. Add `ClientWorkspaceProvisioner` to `execution/composition.py` implementing `session.provisioning.WorkspaceProvisioner` (`session/provisioning.py:66`) over `Operation.REGISTER_WORKSPACE`: build the `ProvisionRequest`'s `{root_id, relative_root}` from the request's `workspace_path` relative to `approved_roots`, send one `register_workspace{create:false, input_id:null}` and map the reply into `ProvisionedWorkspace(registered=True, workspace_id, revision_id, tree_sha256=None)`.
   **The wire does not change for this port.** The register reply is `{workspace_id, revision_id}` by the frozen spec
   (`notes/i03-execution-workspace-spec-2026-10-15.md:153`) and `service.py:591` matches it; the only thing asking for a
   third field is `ProvisionedWorkspace.__post_init__`'s local rule (`session/provisioning.py:53-59`), and nothing in
   `src/` reads `ProvisionedWorkspace.tree_sha256` (`grep '\.tree_sha256' src` hits only the supervisor's own revision
   records and `checkpoints.py`/`publication.py`, never this dataclass). So relax, do not extend: make the field optional
   for a registered result, keep the 64-hex check when it is present, and update
   `tests/test_execution_provisioning.py:81`. Adding it to the reply would have been a journal-visible schema change
   (`journal.py:130-131`) bought for a value no consumer reads; if a later readiness oracle needs the tree hash, it takes
   it from the operation that already returns one (`SEAL`, `INSTALL_PROJECT`) or from `PIN_READER`'s revision, in that
   slice, with its own Q93 decision. A failed register maps to the existing `SessionManagerError` codes through `_ERROR_CODES` (`execution/provisioning.py:28-35`) rather than a new vocabulary. Tests in `tests/test_execution_composition.py`: over the in-process supervisor a REUSE request returns exactly the `workspace_id`/`revision_id` the authority holds and `tree_sha256 is None`, and the reply is byte-identical to the spec's two-field result; an unknown root, an escaping relative path and a missing socket each raise the mapped code with no bytes written; a pre-change `REGISTER_WORKSPACE` `DONE` record still reads without `CORRUPT_STATE` (the schema did not move) **Progress (2026-11-01, E297).** `ClientWorkspaceProvisioner(config, client)` and `client_workspace_provisioner(*, config_path=None)` live in `execution/composition.py`; both resolve the workspace with the same `_root_binding` the run's registration uses, and one private `_client_for(config)` is now the only place a client is built. `ProvisionedWorkspace` accepts a registered result without `tree_sha256` and still validates the digest when present (`session/provisioning.py`). The error vocabulary is shared, not duplicated: `execution/provisioning.py::ERROR_CODES` (formerly `_ERROR_CODES`) is imported as-is, and a client refusal maps to `workspace_denied`/`workspace_corrupt`/`workspace_provision_failed`. **Q94 (operator, 2026-11-01): wire it in production** — `cli._session_manager_for_args` now passes `workspace_provisioner=client_workspace_provisioner()`, so `fa run chat` and every session-creating command reach the authority whenever the operator configured `execution:`, and keep today's host path when no file exists. The in-process `ManagedProvisioner` (`execution/provisioning.py:37`) therefore stays as the component adapter until S4P2 owns the rest of the cutover (`workspace_io`, `PtyPool`): deleting it now would leave five authority-semantics tests needing a socket for no product gain. Banks: `tests/test_execution_composition.py` **12 passed** (registered identity with `tree_sha256 is None`, idempotent re-ask, PROVISION refused, missing dir, escaping path, the approved root itself, a client whose root id the authority does not know → `workspace_denied`, a dead supervisor → `workspace_provision_failed`, and the manager taking its provisioner from the operator file, foreign uid → `None`), `tests/test_execution_provisioning.py` **10 passed** (the relaxed and still-validated tree hash). 8/8 mutants killed with byte-identical sources: hash check removed, provisioner inventing a hash, containment skipped, PROVISION allowed, CLI not injecting, uid rule dropped, mapping flattened, missing-dir check removed. Execution+workspace+session+cli banks **1526 passed / 1 skipped**, and the 14 `test_cli*.py` failures are identical on the pre-STEP9 tree (they need a real git workspace). (exit: protocol and provisioning banks green, the provisioner and `managed_execution_for_run` share one `_root_binding(config, workspace_path)` helper and are the only two `register_workspace` senders in `src/`, and `SessionManager` is constructed with the provisioner in production (`cli._session_manager_for_args`), with the in-process adapter retained until S4P2)
- [x] STEP10: implement CT120, scoped down. **Ordering (Q95 = B, E297): CT119 lands first** — the deterministic `plan-<sha256>.md` draft name is what lets the authority locate the buffer without a payload path; this step then removes the alias and keeps a tolerant reader for records written before it. Remove `candidate_scope.candidate_path` from `protocol.py` (`:105`), `_candidate_scope` (`:285`), `_candidate_buffer` (`:2248`), the service routes and the banks, keeping the exact `plan_ref` equality that already exists (`publish_candidate_plan` `:3431`); the buffer is located by the authority, not by a payload path. No renames: `seed_plan_candidate`, `plan_promotion.py` and `candidate-<hex>.md` keep their names, because the controller host path is the only place `candidate` means a file and a rename would move every importer without moving behaviour **Progress (2026-11-01, E301).** The alias is gone from the wire: `CANDIDATE_SCOPE = _object(plan_ref=PLAN_REF)` (`protocol.py:69`) and the `byte_limits` key list no longer names it. `_candidate_scope` (`workspace.py:285`) accepts exactly `{"plan_ref"}`, and `_candidate_buffer` (`:2249`) authorises the view's one writable target as `pin.record["plan_ref"]["workspace_relative_path"]` — the identity the authority already pinned, instead of a path the caller named. The physical buffer was never that path: it is the supervisor's own private `candidate` file opened by `dir_fd` (`:2263`), so the deletion removes a label, not an IO route. `ExecutionClient.publish_plan` writes the buffer under the plan's canonical path and sends `{"plan_ref": plan_ref}` (`client.py:224-255`). `_view_record_compat` (`:538`) is the tolerant reader the step asked for: a `view.json` written by the older code carries the alias, the record schema is closed (`additionalProperties: false`), so the loader keeps the declared keys and drops the rest — nothing is added, and the publish path still proves the same `plan_ref` equality. Banks: purposes **12** (a wrong label is `PATH_DENIED`, the removed alias is refused as an unknown key, and an old record still loads), protocol/client/service/workspace-authorize/workspace-publication updated to the new shape. **6/6 mutants killed**: label ignored, scope accepting extra keys, legacy record refused, client minting its own path again, the alias back on the wire, plan identity not compared — sources byte-identical. Execution+workspace banks **1359 passed / 1 skipped**, `ruff check` clean. **Exit-clause amendment, stated rather than hidden:** `git grep candidate_path` is empty in `src` but **not in `tests`** — two fixtures name the removed alias on purpose (`test_execution_purposes.py:231` proves it is now an unknown key; `:327` proves an old record still loads). A criterion that forbids the tests which pin the change is the wrong criterion, so it is amended here rather than satisfied by deleting them. (exit: `git grep -n "candidate_path" src tests` is empty, protocol and purpose banks green, `git grep -c "seed_plan_candidate" src` unchanged from before the step, `check_doc_links.py` clean)
- [x] STEP11: prove the class, not the instance, and record it. **Amended (Q96 = A, E297): the sequencing pin changes shape.** A host-side write already refuses the next publish today, so the strict `xfail` goes on the assertion that fails now — a *successful* second publication after a host-side write — while today's refusal and the stale-source `INPUT_POLICY` rule become plain tests; the EDGE test also extends the STEP8 test in place and is renamed `…_reaches_promotion`. Add the EDGE test that would have caught E288 — `tests/test_execution_composition.py::test_the_workflow_root_supplies_a_managed_publisher`: over the real controller with a recording port, assert a publisher reached `_promote_validated_plan` (recorded by the port, never inferred from a green run) — plus `tests/test_plan_candidate_retention.py::test_a_publish_failure_never_loses_the_candidate`. Record the new producers under the **existing** live cases in `e2e/I03/implementation-handoffs.md` (I03-LIVE-26 for the composition, I03-LIVE-25 for recovery of a candidate publish, I03-LIVE-S08 for the chat join) and add one ledger entry for this slice; do not add register cases here, because the register, the `e2e/README.md` index, `e2e/I03/live-verification.md` and `producer-coverage.json` must change as one set (`scripts/check_execution_e2e_coverage.py:659-670`) and their counts are pinned by `tests/test_e2e_artifact_contract.py:340-350` — new case ids are the planner's host-sheet work in SLICE6 STEP5. Also pin the sequencing limitation instead of hiding it: `tests/test_execution_composition.py::test_a_host_side_write_before_the_second_publish_is_refused` writes one project file on the host path after a successful publication and asserts the next candidate publish is refused (`CORRUPT_STATE` at `acquire_writer`'s `_unchanged`) — marked `xfail(strict=True, reason="SLICE4 STEP2 cutover")` so the bank stays green, and strict enough that the mark must be removed by the step that makes it pass. No helper may survive without a production caller, which is the E288 shape this slice exists to close: every helper it adds is named here with the bank that proves its reach from `fa workflow` — `_root_binding` (STEP8), `BoundPlanPublisher.publish_candidate`'s acquisition *and* release (STEP7's saga and uncertainty tests), the `GrantReply` lifetime (STEP8's release test), `retain_plan_draft` (STEP3's injected failure) — so a helper whose only caller is a test cannot land. Update this increment's derived DoD counts and record that I03 now sits at the slice ceiling (7 of 7, `plan_ids._SLICE_CEILING`) **Progress (2026-11-01, E302).** The EDGE test exists and reaches promotion: `tests/test_execution_composition.py::test_the_workflow_root_reaches_promotion` drives the port the CLI actually hands over through the controller's own `_promote_validated_plan`, and the publication is recorded at the managed boundary — deleting `plan_publisher=` at the call site now fails an assertion about a commit, not about an argument. The sequencing pin is split the way Q96 = A meant it, and the split is measured rather than argued: `test_a_host_side_write_before_the_second_publish_is_refused` **passes** today (the refusal is `CORRUPT_STATE` from `_plan_prepare` → `_forward_gates` → `_unchanged`, and the first commit's bytes stand), while `test_the_runs_own_second_publication_survives_a_host_side_write` **fails**, so the strict `xfail` naming SLICE4 STEP2 sits on the success that does not happen yet. The step's own earlier wording put the mark on the refusal, which would have been `XPASS(strict)`; that is the sentence this evidence corrects. Retention conformance is `tests/test_plan_candidate_retention.py::test_a_refused_promotion_retains_the_exact_bytes_under_their_hash` held under its E300 name (the step's working title was `…_never_loses_the_candidate`); its success-path control is what makes it a proof rather than a coincidence. **One body clause could not be honoured, and is amended instead of faked:** `e2e/I03/implementation-handoffs.md` has sections only for `I03-LIVE-23/24/27`; `I03-LIVE-25/26/S08` are registered in the master sheet but have no handoff sections, and creating them is register-set work — the file is parsed per case by `tests/test_e2e_artifact_contract.py:634-665` with ten required fields, and this increment forbids register changes here. The new producers are therefore named in ledger E302 against those three case ids, and the handoff sections stay SLICE6 STEP4's (that step already says the coder writes that file and that the S08 join is future proof). Counts reproduce: CT **33**, `kill:` **23**, STEP **47**, slices **7 of 7** (`_SLICE_CEILING`), operations **19**, register cases **27**; `scripts/check_execution_e2e_coverage.py` green, `tests/test_e2e_artifact_contract.py` **28 passed** from the repo root. (exit: coverage script unchanged-green, no register set change, DoD counts reproduce from their commands, CT121's banks named in the ledger entry, the sequencing test is a strict `xfail` naming SLICE4 STEP2, and that hand-off is named in the ledger entry)


## Increment definition of done — binary, no partial isolation claim

**Counts in this section are derived, never hand-typed.** Canonical numbers at the E268 review, each
reproducible by the command beside it:

| Quantity | Value | Derive it with |
| --- | --- | --- |
| CT declarations (23 FUNCTIONAL + 9 CONSTRAINT + 1 PRESERVATION) | **33** (E282 added CT113/`handoff`; the SLICE7 review added CT114–CT121 and retagged CT114 as FUNCTIONAL so the kill row below stays exact; every earlier count in this log is that entry's snapshot) | `grep -cE '^\s+CT[0-9]+[a-z]? \[(FUNCTIONAL|CONSTRAINT|PRESERVATION)\]' increments/increment-03-*.md` |
| Declared `kill:` directives | **23** (one per FUNCTIONAL contract; a `grep -c 'kill:'` returns more because prose lines quote the word) | `grep -cE '^\s+kill: remove-call ' increments/increment-03-*.md` |
| Closed wire operations | **19** | `grep -cE '^\s+[A-Z_]+ = "' src/fa/execution/primitives.py` |
| E2E live surfaces / joins | **27 / 8** (SLICE7 deliberately adds none: its producers map onto I03-LIVE-25/26 and S08, because the register, index, master and coverage mapping must change as one set and their counts are pinned in `tests/test_e2e_artifact_contract.py`) (E282 added `handoff` as I03-LIVE-27; E250 recorded 18/8; E267 added `publication.py` as I03-LIVE-19; E269 the publish path as I03-LIVE-20; E271 the bundle path as I03-LIVE-21; E272 the install path as I03-LIVE-22; E273 the plan-replacement path as I03-LIVE-23; E274 the authorizer as I03-LIVE-24; E276 forward recovery as I03-LIVE-25; E277 the composed supervisor as I03-LIVE-26 -- E281 re-ran the derivation) | `grep -o 'I03-LIVE-[0-9]\{2\}' notes/e2e-live-verification-register.md \| sort -u \| wc -l` |
| I01 source mapping | **42 CTs / 7 deferred obligations / 3 planned cases (all NOT RUN)**; explicit I01-LIVE-01..03 mapping; no live verdict inferred | `scripts/check_execution_e2e_coverage.py` |
| Seven slices, forty-seven STEPs | **7 / 47** (E282 added SLICE2 STEP6; SLICE7 adds eleven) | `grep -cE '^- \[.\] STEP[0-9]+:' increments/increment-03-*.md` |

If a later edit changes a count, the edit updates the table and the ledger entry that introduced the
change; a plan sentence with a stale number is a defect, not a rounding error.

**Ticking rule (2026-10-31, after the closure audit).** A `- [ ] STEP` box becomes `- [x]` when, and only
when, that step's own `exit:` clause has been *reproduced* and the evidence is named in the ledger — never
because the code exists, never because a bank looks green, and never from a phase of a larger step. The
per-step truth therefore lives in `## Closure state, one row per step` above, which classifies every step as
`LOCAL` (code and bank exist, only the run is missing), `PARTIAL`, `HOST` (built, exit is a host fact),
`OPEN` or `PLANNED`. The audit's counts: 9 `LOCAL`, 11 `PARTIAL`, 2 `HOST`, 14 `OPEN`, 11 `PLANNED` — zero
ticked, and the three local verify blocks cannot run in a 3.11 sandbox, so a tick today would be a claim
nobody made.

- [ ] All seven local verify blocks exit 0 AND collect every path named in their slice's `TESTS:` line —
      collection is proved by `--collect-only -q` naming each file, because a verify block whose single
      path does not exist yet reports "no tests ran" and exits 4, not 0. Required execution_host runs use
      `FA_REQUIRE_EXECUTION_HOST=1` and cannot succeed by skipping unavailable Docker/profile.
      All **23** declared `kill:` directives have useful executed failing oracles, provenance,
      elapsed cost and byte-exact restored source; errors, collection failures, skips and
      `PRODUCER_ABSENT` do not count as kills.
- [ ] Implemented artifacts conform to recorded Q59/Q60/Q63/Q74 and spec §7 managed-v2/schema/rendering
      contract; no conditional runtime proposal/stub remains. Existing Q62/I02 v1 readers and strict IDs stay compatible.
- [ ] Real profile/UID/UDS/cgroup/mount/import proof and complete execution inventory show zero
      project execution outside cells for every production path/role, including readiness and chat
      subagents; backend-down/transport uncertainty never triggers fallback/replay. No legacy writer.
- [ ] New workspace, resumed session and new-session registered-workspace reuse work through actual
      manager/DB. Two writer processes/run/session aliases cannot mutate simultaneously; read pins
      survive publication. Dirty/staged/untracked inputs and canonical Git index preserved; private
      Git/input/secret-dependent compatibility limits have explicit accepted dispositions.
- [ ] File tools/PTY share one private view. Real alias/parent-rename/protected-write/descendant cases
      cannot alter canonical PlanRef/state or import forbidden bytes; ordinary edits/Q58 succeed.
      Seal requires all writers terminal; stale generation/base fails. Crash/durability-uncertainty
      matrix yields complete old/new revision or quarantine, no partial-current success/rollback.
- [ ] Actual direct and nested C1 use real supervisor/cells with only provider mocked. Child artifacts
      never overwrite parent; acquired explicit canonical PlanRef/T0/verification/eval share identity;
      Q66 current initial context/distilled retry and Q55/Q56/Q73/both-mode integrity floor are proved.
- [ ] E223 deployed functional/source-to-behaviour verification covers all I01–I03
      claims, including admission/repair/promotion/T0/eval/failure paths, with actual deployed
      code/image/config identities and useful effect/artifact oracles; local green is not host proof.
- [ ] E223 environment/readiness and inherited baseline acceptance review is complete for the
      intended Ubuntu/Docker/Python deployment. Run existing just test/just check release gates;
      review exact baseline/candidate failure identities/phases, changed/replaced test intent,
      recorded Mypy contexts (including the unreproduced historical ninth) and relevant hook
      observations using preserved I02 evidence. New/changed checks green; no new/missing/
      unclassified failures, aborted/no-summary or count-only waiver. No unauthorized E19 changes,
      skipped security check or invented FA Go runtime requirement; actual red remains red.
- [ ] E223 integrated E2E/deployment acceptance: full CT88/CT89 producer-preserving package/
      manual review/handoff/skills/fixtures complete;
      spec §9.1 real-provider direct+nested witnesses and every unique required I01–I03 deployed-main case have reviewed PASS with code/image/config/run/
      oracle/artifact evidence. No local proof sets live status, no unresolved blocked deployment row.
- [ ] E223 broad independent I01–I03 implementation/security/recovery/evidence review and final
      operator deployment signoff recorded in
      notes/i03-local-and-deployed-acceptance.md with commands/rc/environment/source references;
      registers updated only from actual proof. Until then status remains unshipped.

## E268 — adversarial review of the remaining I03 (2026-10-22): plan and code corrections

**Method.** Read every remaining slice against the modules it touches and their callers, reproduced
each suspected defect before believing it, and separated confirmed defects (fixed here or given a named
owner) from suspicions (recorded, not fixed). Nothing in this section ticks a STEP, closes a contract or
assigns a live verdict. Implementation numbering after this review: **E269 = SLICE3 STEP2 (publish/CAS)**,
**E270 = SLICE4's clean-up of the recovery hook if STEP2/4 split needs it**, **E271 = SLICE3 STEP5 kills**;
recovery itself stays inside STEP4.

### A. Confirmed defects — fixed in this review

| # | Defect (evidence) | Why it would bite | Fix |
| --- | --- | --- | --- |
| D1 | `release_unused_writer` refused settlement for **any** non-READ view, whatever its state (`workspace.py::release_unused_writer`, old `_has_writer_views`) while spec §2.1:168 allows release when there are "no writable/live/unknown jobs or unfinished projection". | With E267's `SEALED` and E269's `PUBLISHED`, a **finished** view kept the writer captive forever; the next `acquire_writer` returns `WORKSPACE_BUSY`, and a restart then quarantines the workspace (`workspace.py::_load`) with no forward path. Reproduced: sealed view → `release REFUSED: WORKSPACE_BUSY`. | `_has_unsettled_views` + `_SETTLED_VIEW_STATES = {PUBLISHED, REJECTED}`: SEALED still holds the writer (an unpublished candidate is unpublishable once the grant dies), OPEN/STOPPING/UNKNOWN always refuse, PUBLISHED/REJECTED settle. Four cases added; 3/3 mutants killed. |
| D2 | `WorkspaceAuthority.create_view` ignored the wire's `base_revision` (`protocol.py:102` requires it; the method had no such parameter). | A caller naming revision A received a view over revision B with no error — the exact stale-base confusion CT102/CT106 and spec §4's "generation/base CAS" exist to prevent, and undetectable by any current test because the field is dropped before any check. | `base_revision` keyword with `STALE_REVISION` before any filesystem effect; two cases added; mutant killed. The dispatcher must forward it (SLICE1 STEP3). |
| D3 | Name collision: `WorkspaceAuthority._install_project` actually installs a **view** directory (`workspace.py::_install_project` @6ff1121), while spec §5 assigns `publication.install_project` (no-clobber *project* install) to the same authority. | An agent implementing the bundle path could "reuse" the existing helper and silently install a view where a project install was intended. | Renamed `_install_view`; the spec name stays reserved for E269+. |
| D4 | Stale line citations inside E267's own section (`_revision` cited at 898 → now 919; `_proof_only` at 2033 → now 2054) because the section's own edit shifted them. | Every later agent either lands on the wrong line or stops trusting citations. | Citations corrected; new rule below. |
| D5 | E250's "18 surfaces / eight joins" is a dated snapshot, but nothing said how the count grows; E267 added a 19th row. | Silent divergence between register prose and the actual inventory. | Growth rule stated in the register (E267 section) and the count table above. |

**Citation rule (normative for this project).** A plan or ledger citation names the **symbol**
(`workspace.py::_proof_only`), never a bare line. A line number may accompany a symbol only when it is
pinned to a commit sha (`workspace.py:2054 @ a299c12`). Line-only citations are treated as drift.

### B. Suspicions — recorded, each with an owner; not fixed here

| # | Suspicion (evidence) | Why it is not fixed now | Owner |
| --- | --- | --- | --- |
| S1 | A composed service with no `CellTermination` configured returns `terminal=false` and leaves the view `STOPPING` forever (`ViewStopper.stop_view`, `supervisor.py`), which is honest but looks like a hang. | The seam is deliberately optional for local tests; requoting it inside the service is composition work. | SLICE1 STEP3 exit: service startup must refuse to run without a real observer. |
| S2 | `_load` quarantines every `OWNED` workspace and nothing recovers it; stale `pending/` staging from a hard kill is never swept (`__enter__` creates the dir then continues). | Recovery is STEP4, and doing it before `publish_view` exists has nothing to recover forward to. | SLICE3 STEP4 (hook point now named in the STEP text). |
| S3 | `_Capture` excludes a component named `.git`/`.fa`/`.venv`/`.env` at **any** depth (component match), so a legitimate nested `.fa/x.py` never enters a revision and `.fa` is "protected" by name only. | Changing the exclusion semantics is a behaviour change with no failing case yet; the protected-plan boundary is the actual safety rule. | SLICE3 STEP2 (§5 wording) — decide "excluded by name at any depth" explicitly. |
| S4 | Sealed/published views persist their full source copy plus manifest forever; nothing garbage-collects them. | Retention is a policy question (evidence vs disk) that belongs with the publication receipt contract. | E269's receipt contract + I06 disposition, explicitly stated. |

### C. Verified fine (checked, no action)

- **`17` kills is correct at E268.** 17 FUNCTIONAL contracts, 17 distinct `kill: remove-call` directives (E282 later added CT113, so the current derivation is 18); a raw
  `grep -c 'kill:'` returns 19 because two prose lines quote the word. My first reading flagged a
  mismatch; the count is right and is now derived in the DoD table instead of asserted.
- **Spec §5 steps 1–3 vs the §5.1 table do not contradict each other for REVISION.** Intent may only be
  written after Rnext is durable, and the irreversible point is the `current.json` replace. The one thing
  worth stating explicitly (and now stated in STEP2) is that the recovery **discriminator is
  `current.json`**, not `phase`, because `PREPARED` legitimately exists on both sides of the CAS.
- **Gate/drain vs a running command.** E257 already fixes the intent ("scope ends after dispatch, NOT the
  command reply/exit wait") and the code matches: `admit()` registers work for the dispatch scope only,
  `close_admission` refuses later dispatches, and `stop_cells`/cancel handle the running cell. No defect.
- **`prepare_seal`/`mark_sealed` duplicate checks** are intentional defence (E267 records the masking).

### D. Executability gaps found in the plan text — rewritten in place

1. **SLICE1 STEP3** never said which handlers to route. It now lists all nineteen operations, requires
   authority for the non-readonly ones, forbids a silent fallback, and adds a route-coverage test that
   enumerates `Operation` so a forgotten route fails a test instead of hanging at runtime.
2. **SLICE3 STEP1** was one checkbox covering a shipped barrier and two host-only parts. It now names
   its three parts explicitly, so nobody closes it on local evidence.
3. **SLICE3 STEP2** now says what it must materialize (Rnext from the sealed manifest, under the derived
   id), what the irreversible point is, and that publish is what settles the owner.
4. **SLICE3 STEP4** now names the real hook points (`__enter__` → `recover_workspace` before the
   quarantine decision; `_initialize_genesis`'s existing refusals; the unswept `pending/` directory) so
   an implementer does not have to rediscover them.
5. **The DoD** now proves collection (a missing `TESTS:` path exits 4, not 0) and derives every count.

### E. Explicitly deferred, with reasons

- **The bundle/Q58/BOOTSTRAP half (STEP3)** stays after STEP2: `install_project` needs the current
  pointer, and `publish_plan_buffer` (`inner_loop/plan_promotion.py:183`) already does its own same-path
  atomic replace with its own lock and CAS, so integrating it before the pointer contract exists would
  create two commit paths with different failure vocabularies.
- **Candidate-buffer seal** stays in STEP3 with §5's PLAN intent; sealing a buffer without its publisher
  would produce a half-specified path.
- **Host proofs (Docker/cgroup), deployment and every live verdict** remain SLICE6 or `BLOCKED`.

## E269 — SLICE3 STEP2 pre-code plan: publish (CT106), intent/current/projection (APPROVED after review)

Declared 2026-10-22 **before any code**, per the standing rule, then **reviewed by a peer agent and
amended** the same day. Status: **approved for implementation** — the reviewed rules (E269.3–E269.4) are
the approved version; the lead implements, the reviewer reads the final R5/R6/R9 diff, and neither ticks a
STEP nor assigns a verdict. No STEP is ticked and no contract changes state by this section. Numbering
follows E268: **E269 = SLICE3 STEP2**, `E270` = STEP3 (Q58/BOOTSTRAP bundle), `E271` = STEP5 kills;
recovery stays inside STEP4.

**Review outcome, recorded because it changed the plan.** Seven findings were raised; six held against
source and are incorporated, one was right in diagnosis and wrong in prescription. The one factual claim
*against* the lead that mattered: the plan's D2 justification was **false** (spec:658 says "initial"), so
D2 was withdrawn and promoted to **Q80**, resolved as option (B). Two prescriptions were rejected with
reasons, not preference: a durable stored receipt (exact replays are journal-served, and a foreign id
fails the caller's operation binding) and factoring the drift check out of `_unchanged` (no behavioural
change; five callers already depend on it). Two of the lead's own lines were withdrawn on the reviewer's
evidence: the `operation_ids` append (D10) and the over-broad restart claim (R13).

### E269.0 Blocking questions — Q79 is not one

**Verdict: Q79 does not block E269.** Q79 is about the managed *tool view* (text-only reads, `derive_text`
capability, role→port threading) and gates **SLICE4 STEP2's cutover**. E269 writes no tool, no port, no
registry and no role. Checked against E269's actual surface rather than assumed:

| Q79 claim that could touch publish | Verified position | Verdict |
| --- | --- | --- |
| "`d` (pre-convert outside the sealed tree) is rejected as a publication concern; Stage 1 adopts a content-addressed, view-private cache" | E269 has no converter, no `/scratch` reader and no cache. A view-private cache under `scratch/` is already outside the sealed domain (`_Capture` walks `source/`, not `scratch/`), so nothing in E269 can freeze a derivative. | **not blocking** |
| `session.artifact_store` is `workspace/.fa/artifacts`, inside the validated tree and unreachable through the port | `.fa` is an excluded component at any depth (`_Capture._excluded`), so artifacts can never enter a revision, a manifest or a tombstone. E269's projection never touches `.fa`. This is the *consistent* outcome; whether artifacts should be publishable at all is Q79 Stage 1's question. | **not blocking; agreement recorded** |
| "managed `fs_write_file` is create-only by accident (STALE_REVISION when `expected_sha256` is None)" | That is `write_file`/`edit_file` semantics inside SLICE2. E269 changes no file handler. | **not blocking** |
| Q79 Stage 0 allowed-files list | `tools/__init__.py`, `workspace_port.py`, `read_file.py`, `write_file.py`, `edit_file.py`, `profiles.py`, `recovery/classify.py`, `tool_port.py` — **disjoint** from E269's list (`execution/workspace.py`, `execution/publication.py`, one test file). | **no collision** |

The three Q79 sub-items that *will* land on E269's contract later, so they are named rather than
silently absorbed: (a) `view.record["operation_ids"]` gains its first non-EXEC writer here (publish), so
the "managed records must not carry empty `operation_ids`" rule from §6 has a precedent to follow;
(b) sealed/published views retain bytes with no GC (E268 S4) — Q79's artifact-store GC discussion must
decide retention for *both* stores; (c) a derived-text cache under `scratch/` is view-lifetime by
construction, which E269 makes true structurally rather than by convention.

**Questions raised by this plan, and their rulings (both promoted before any code, per the register-first
rule).** **Q80** — `current.json` has two frozen shapes (spec:658 "initial" three-key vs §5.1 five-key).
Resolved **(B)**: one five-key shape everywhere, spec:658 marked SUPERSEDED, invariant
`current.generation <= metadata.generation`; the union-schema alternative was rejected because it would
accommodate a state with no deployed instance and make the ownership invariant conditional. **Q81** —
canonical roots must be writable on the deployed host (`/repo` ships `read_only: true`). Decided **(A)**:
composition refuses a non-writable root, publish probes without writing and fails fast at prepare, and
the mount decision is verified at SLICE6. Both entries are now in `notes/open-questions-2026-10-07.md`,
which was first **backfilled with Q78 and Q79** — it had ended at Q77, leaving two raised questions cited
only by ledger offset.

### E269.1 Ordering verification

| Claim | Verified against | Result |
| --- | --- | --- |
| publish is the next unit | E267 closed STEP1 part 2; STEP1's remaining parts are Q74 policy + cgroup observer + the host test; STEP2 is "intent/current/projection schemas/order/dir fsync and generation/base CAS" | **holds** — STEP2 needs no cell, no Docker, no service route |
| publish's preconditions all shipped | `prepare_seal`/`mark_sealed`/`_SealInputs` (E267), terminal receipt (E266), `_revision`/`_Capture`/`_snapshot`/`_rename_directory`/`_replace_private_bytes` | **holds** |
| the wire already defines publish | `protocol.py::PUBLISH` request `{sealed_manifest_id, expected_base_revision}`; result `_COMMITTED = {workspace_id, revision_id, tree_sha256, operation_id, projection_complete: true}` | **holds — and it constrains the design**: publish must not reply before projection verifies, and the revision id is *not* a caller field |
| publish needs no dispatcher route | `_dispatch`/`_handle` are injected seams; tests call owners directly (E267 precedent) | **holds**, SLICE1 STEP3 |
| STEP2 does not need STEP4 | STEP2 ships intent/current/projection in-process; restart recovery (`_load` hook) is STEP4 | **holds — stated as a limit, not fudged** |

### E269.2 Current behaviour (source-verified, `6b7f300`)

- `current.json` is `{schema_version, revision_id, tree_sha256}` (`workspace.py::_CURRENT`), written in
  exactly one place today: `_register` (`::_register`), under a `pending/<uuid>` staging tree that is
  renamed in with `renameat2(RENAME_NOREPLACE)`.
- `revisions/<rev>/` = `{tree.json, data/}`; `_revision()` re-walks `data/` and compares it to
  `tree.json` with `mode` substituted, because `data/` is a **retention copy** (0600/0700) while
  `tree.json` carries **logical** modes. `create_view` restores logical modes onto `views/<v>/source/`
  through `_materialize_input`, so a sealed manifest already records the modes a projection must apply.
- `_Capture` fsyncs every copied file and every destination directory it descends through, so a
  materialized tree is durable per level before the walk returns; `_replace_private_bytes` fsyncs the
  file *and* the directory (intent/current writes are durable by construction).
- There is no `intent.json` producer, no `revisions/` writer outside `_register`, and no code that
  writes canonical bytes after registration: `publication.py` is seal-only (`seal_view`,
  `_validate_sealed_tree`, `_derive_revision_id`) and states in its module docstring that publish is
  E268/E269's job.
- `SEALED` is terminal-in-process: seal writes `sealed.json` + flips `view.json`, and `_project_view`
  refuses any state but `OPEN`, so a sealed view's bytes cannot move through the authority again.
- `release_unused_writer` now settles on `PUBLISHED|REJECTED` (E268 D1) — a state nothing can reach
  today, because no producer writes it.

### E269.3 Target behaviour (the rules the tests will hold)

Reviewed 2026-10-22 against a peer review; every rule below is the post-review version. Rules that
changed are marked **(R)** with the reason.

- **R1 preconditions — STATE FIRST, then equality (R).** One transaction, no writes. In this order:
  (a) `_proof_only` capability+principal proof; (b) **dispatch on view state** — `UNKNOWN` →
  `TERMINALITY_UNKNOWN`; `OPEN`/`STOPPING` → `VIEW_CLOSED`; `PUBLISHED` → **R9 replay** (skipping every
  equality check below, because its `current.revision_id` *is* the derived revision); only `SEALED`
  continues; (c) gate closed; (d) `terminal.json` present; (e) `ProtectedPlanContext.recheck()`;
  (f) `binding.metadata["status"] == "OWNED"` with this actor and grant; (g) generation equality
  `view_ref.generation == metadata.generation == manifest.generation` else `STALE_GENERATION`;
  (h) base equality `expected_base_revision == view_ref.base_revision == manifest.base_revision ==
  current.revision_id` else `STALE_REVISION`; (i) payload `sealed_manifest_id ==
  record.sealed_manifest_id` else `STALE_REVISION`.
  *Why (R):* the pre-review plan checked equality before state, so a legitimate retry on a `PUBLISHED`
  view failed `STALE_REVISION` and never reached the replay branch that exists for exactly that case.
- **R2 manifest is read, recomputed against, never re-derived from a directory.** `sealed.json` is read
  from the view directory and re-validated with the *same* `_validate_sealed_tree` seal used
  (`plan_path`/`base_entries` from `prepare_publish`), and cross-checked against the record (`view_id`,
  `workspace_id`, `generation`, `base_revision`). A manifest that disagrees with the record is
  `CORRUPT_STATE`; a malformed one is `INPUT_POLICY`; neither writes anything.
- **R3 id derivation.** `revision_id = derive_revision_id(manifest)` (shipped, content-addressed over the
  canonical manifest). No caller-supplied id exists on the wire, so none can be honoured.
- **R4 materialization verifies every digest.** Copy the frozen `views/<v>/source/` into
  `pending/<uuid>/revisions/<derived>/data/` with `_Capture`, then compare the copied tree to the
  manifest's **non-deleted** entries on `(path, type, size, sha256, link_target)` in sorted order,
  requiring the same length. Extra path, missing path or moved byte ⇒ `CORRUPT_STATE` and no revision is
  installed. `tree.json` is written from the manifest (`revision_id=derived`, `entries=live`,
  `tree_sha256=manifest.tree_sha256`), never from the walk's own hash. A directory that already exists at
  `revisions/<derived>` is accepted only after `_revision()` re-verifies it equals the manifest.
- **R5 pre-flight, install and intent (R).** Before anything: call the existing
  `workspace.py::_unchanged` (canonical re-walk vs `current.tree_sha256`) and the Q81 writability probe
  (§E269.4 D4/D9). Then `renameat2(RENAME_NOREPLACE)` the staged revision into `revisions/<derived>`,
  fsync `revisions/` and `pending/`, and durably write `intent.json` (`kind=REVISION`, `phase=PREPARED`,
  `base_revision`, `next_revision`, `tree_sha256`, `operation_id`, `target_relative/old_sha256/
  new_sha256` null) with read-back equality. **No canonical byte is written in this phase**, and the
  intent precedes the pointer.
- **R6 the irreversible point is the pointer (R).** `_commit_current` re-reads `current.json` (CAS against
  the value R1 validated) and `workspace.json` (still `OWNED`, same generation), replaces `current.json`
  with the five §5.1 keys `{schema_version:1, workspace_id, generation, revision_id, tree_sha256}`,
  read-back verifies. Then — **before the first canonical byte** — advances the intent to
  `phase=PROJECTING`. `COMMITTED` is **not** produced in E269: projection is always entered (and is a no-op when nothing
  differs), so the phase goes `PREPARED → PROJECTING → DONE`. `phase` remains advisory in every case:
  `current.json` alone discriminates whether the commit happened.
  A **determinate** pre-commit failure (CAS lost, generation moved) discards only this attempt's own
  `revisions/<derived>` and clears the intent, leaving `current.json` byte-identical.
- **R7 projection is a pure function of the committed revision.** For each live entry: if the canonical
  path already matches `(type, mode, size, sha256)` it is skipped (idempotent by construction); otherwise a
  directory is created, or a file is written to a sibling temp with the manifest's logical mode, fsynced
  and `os.replace`d into place. Tombstones unlink the canonical path when present (`no-follow`) and are
  otherwise no-ops. Rules: never traverse a symlink, never touch a path with an excluded component at
  **any** depth (`.git`, `.fa`, `.venv`, `.env`, configured exclusions), and refuse (`PATH_DENIED`) a
  destination that is a symlink, a special file or a hard-linked regular file. `.git/index` and every
  excluded tree are therefore untouched structurally, not by luck.
- **R8 completion proof (R).** After projection, re-walk the canonical root with `_snapshot` and require
  equality with the manifest's live entries — this is the "no partial current state" test, including
  extra-path drift. Then intent `DONE` + clear, then flip `view.json` to `PUBLISHED` with read-back
  equality. Return `_COMMITTED` `{workspace_id, revision_id, tree_sha256, operation_id,
  projection_complete: true}` where **`operation_id` is the caller's own** (`"op-" + request_id`).
  Publish does **not** append to `view.record["operation_ids"]` (R; see §E269.4 D10): that field's only
  existing meaning is EXEC's duplicate-id uncertainty, and its only consumers are `release_reader` and
  `admit`'s `EXECUTION_UNKNOWN` branch.
- **R9 replay is state-driven and stores nothing (R).** A new request observing `PUBLISHED`:
  re-verify `current.revision_id == derive_revision_id(stored manifest)`, re-run `_unchanged`, re-verify
  the projection (R8's comparison), and return the same five-field receipt with the caller's own
  `operation_id`. No second commit, no second intent, no stored receipt. Exact same-request-id replays
  never reach here — `_dispatch` serves them from the journal (`supervisor.py:409-414`, Q75). A mismatch
  is `CORRUPT_STATE`. An `intent.json` present in any other situation is `WORKSPACE_BUSY`: uncertain state
  belongs to recovery (STEP4), never to a second attempt.
  *Why (R):* the pre-review plan promised "the same receipt" but `operation_id` is the one non-derivable
  field, and a stored foreign id would fail the caller's own operation-binding check — turning a
  recoverable retry into a false uncertainty.
- **R10 no side effects beyond the contract.** No canonical write before the pointer commit; no revision
  write after it; no change to `.git`, `.fa`, `.venv`, `.env`, other views, reader pins, scratch, cell
  state or the journal; no Docker call; nothing found in the tree is executed; no model metadata is read.
- **R11 bounds and observability.** Every phase deadline-bounded (`_budget`), bounded by `InputLimits`,
  reporting the closed error vocabulary (`INPUT_POLICY`, `PATH_DENIED`, `STALE_*`, `VIEW_CLOSED`,
  `TERMINALITY_UNKNOWN`, `WORKSPACE_BUSY`, `DURABILITY_UNKNOWN`, `CORRUPT_STATE`, `UNAUTHORIZED`). No new
  error code: the wire list is closed, so adding one would be a protocol change.
- **R12 seal bytes stay frozen.** If `sealed.json`'s digest no longer matches a re-walk of the view source
  (bytes moved after the barrier), publish is `CORRUPT_STATE` **before** any write — the check R4 performs
  is ordered before install so a moved source cannot land a revision.
- **R13 uncertainty after the pointer (R).** Any failure at or after the `current.json` replace is
  `DURABILITY_UNKNOWN`, marks the authority unhealthy, quarantines the workspace where state allows, and
  never returns a receipt. The view stays `SEALED`, which keeps the writer captive (E268 D1) so reuse is
  impossible until recovery finishes it forward. The same holds after a *successful* publish until
  `release`: the workspace is `OWNED`, so a restart quarantines it — **restart-clean iff released**.

### E269.4 Decisions (D1–D10; D2 withdrawn and promoted, D4 and D10 revised after review)

- **D1 — kill placement (unchanged).** CT106's declared kill stays literal:
  `publication.py::publish_view -> _commit_current`, where `_commit_current` is a private function in
  `publication.py` that owns the pointer phase and calls `authority.commit_revision_current(...)`.
  Removing that call leaves `current.json` at the base revision, so every functional case fails.
- **D2 — WITHDRAWN, promoted to Q80 and resolved as option (B).** `current.json` is five keys everywhere
  (§5.1), written by `_register` and by publish; `_load` enforces `current.workspace_id == workspace_id`
  and `current.generation <= metadata.generation`. The pre-review justification ("the frozen schema always
  had five keys") was **false** — spec:658 says "initial" and describes a real 3-key shape — so spec:658
  now carries an explicit **SUPERSEDED** note rather than a silent edit. No union schema: it would
  accommodate a state with no deployed instance and no committed fixture, and would make the ownership
  invariant conditional on precisely the files that establish it.
- **D3 — four durable boundaries, one transaction each** (unchanged): `prepare_publish` (validate, no
  writes), `materialize_publication` (copy + verify + install + intent), `_commit_current` (CAS + pointer
  + `PROJECTING`), `project_publication` (projection + proof + `DONE` + `PUBLISHED`). The copy runs under
  the authority mutex exactly as `create_view`'s materialization does, so no new locking model.
- **D4 — drift check REUSES `_unchanged` (R).** Publish calls the existing canonical re-walk rather than
  writing a second comparison. Its global effect is accepted and tested: `_unchanged` marks the authority
  unhealthy, so one drifted project tree disables the supervisor until restart. That is already the
  established rule — **five** callers rely on it (`_register` path, `acquire_writer`, `pin_reader`,
  `create_view` ×2) — so publish joining them is consistency, not new blast radius. Factoring the
  comparison out was rejected: it changes nothing behaviourally and splits one rule across two functions.
- **D5 — deterministic failures write nothing; uncertain ones write no success** (unchanged; see R13).
- **D6 — intent vocabulary complete, REVISION-only producer, `PROJECTING` now written (R).**
  `_INTENT` implements all §5.1 keys and the full `kind ∈ {REVISION, PLAN, BOOTSTRAP}` /
  `phase ∈ {PREPARED, COMMITTED, PROJECTING, DONE}` vocabulary, but E269 produces **only** `kind=REVISION`.
  `PLAN` arrives with STEP3's Q58 path, `BOOTSTRAP` with `install_project`; recovery rows for all three
  are STEP4's. `PROJECTING` is written before the first canonical byte so recovery dispatches rather than
  infers.
- **D7 — projection refuses a symlink/special/hard-linked destination (`PATH_DENIED`)** (unchanged).
- **D8 — scope** (unchanged): no dispatcher route, no `prepare_bundle`/`install_project`, no
  CANDIDATE-buffer seal, no recovery hook, no GC, no `REJECTED` producer.
- **D9 — non-writable canonical root fails at prepare (NEW, Q81).** `prepare_publish` proves writability
  **without writing**: `os.fstatvfs(fd).f_flag & os.ST_RDONLY` (verified `os.ST_RDONLY == 1`) plus
  euid-vs-mode on the root directory; refusal is `PATH_DENIED` before any filesystem effect. No free-space
  or ENOSPC pre-check: advisory, racy, and recovery must exist regardless. This is a fail-fast for a
  composition error; the mount decision itself is Q81 and is verified at SLICE6.
- **D10 — publish does not write `operation_ids` (NEW, R).** Publish's operation id lives in
  `intent.json.operation_id`. Adding a second writer with an idempotent meaning to a field whose only
  semantics today are EXEC's duplicate-id uncertainty would overload it, and the field has no consumer on
  project views beyond `release_reader`/`admit`. Result: Q79 Stage 0's "who may append to a view record"
  rule inherits exactly **one** precedent.

### E269.5 Allowed files (nothing else)

- `src/fa/execution/workspace.py` — `_CURRENT` (5 keys, Q80) + `_INTENT` schema; `_write_intent`/
  `_read_intent`/`_set_intent_phase`/`_clear_intent`; `_PublishInputs`; `prepare_publish`,
  `materialize_publication`, `commit_revision_current`, `project_publication`; `_load`'s `current.json`
  invariants.
- `src/fa/execution/publication.py` — `PublishResult`, `publish_view`, `_read_sealed_manifest`,
  `_commit_current`, pure projection helpers; `__all__` extended.
- `tests/test_workspace_publication.py` — new CT106 cases beside the CT104/CT105 banks.
- Docs: this section, `ledger.md` E269 result (after code), `notes/open-questions-2026-10-07.md`
  (Q78/Q79 backfill + Q80/Q81), the spec note's Q80 amendment and E269 review rules.
- **Forbidden:** `protocol.py`, `primitives.py`, `supervisor.py`, `docker.py`, `backend.py`, `client.py`,
  `view_io.py`, any tool/port/profile file (Q79's surface), any second lock, any second walker, any GC.

### E269.6 Tests (C1 composition-root over the real authority; C0 for pure helpers; one C3 case)

Fixture: the existing `Site`/`native_profile`/`_stopped`/`_seal` helpers, then `publish_view` directly —
the real `WorkspaceAuthority`, real filesystem, real views, real barrier (the `CellTermination` seam
doubled only for the kernel fact, as E266/E267). **28 cases**, each naming the rule it holds:

*Happy path and receipt* (R1,R4,R6,R7,R8): pointer advances to the derived id; `_revision` verifies the
new revision; canonical bytes equal the sealed bytes; logical mode restored (not 0600); `current.json` is
exactly five §5.1 keys; the receipt decodes against `protocol.decode_reply(operation=PUBLISH)`;
`intent.json` is gone.

*Preconditions* (R1): stale `expected_base_revision` (`current.json` byte-identical); wrong
`sealed_manifest_id`; `OPEN` view; `STOPPING` view; wrong capability (`UNAUTHORIZED`); tampered manifest
entry digest (R2, no revision installed); source bytes moved after seal (R12); generation moved
(`STALE_GENERATION`).

*Projection* (R7,R10): tombstone removes the file from canonical and from `tree.json`, digest over live
entries only; `.git/index`, `.fa/artifacts` and a `.venv` sentinel byte-identical; a
symlinked destination refused (`PATH_DENIED`).

*Settlement and pins* (R8, E268 D1): publish settles the owner (real `release` succeeds, re-claim advances
generation) — **and the publish→release sequence is restart-clean** (reopened authority keeps it
`AVAILABLE`); a pinned reader keeps the old bytes while a new pin reads the new revision.

*Replay and uncertainty* (R9,R13): second publish on `PUBLISHED` returns the same
`{revision_id, tree_sha256}` with the **new** caller's `operation_id` and writes no second intent; a
pre-existing `intent.json` ⇒ `WORKSPACE_BUSY`; injected `os.replace` failure mid-projection ⇒
`DURABILITY_UNKNOWN`, `current` **is** the new revision, view still `SEALED`, intent still on disk,
`release` refused, authority refuses further work; publish→restart→quarantine still holds (STEP4 limit).

*Pre-flight* (D4,D9,Q80): canonical drift before publish ⇒ `CORRUPT_STATE`, nothing written, authority
unhealthy (the accepted global consequence); a `0o555` canonical root ⇒ `PATH_DENIED` before any write
(C3); a read-only **mount** ⇒ `PATH_DENIED` via a disclosed `os.fstatvfs` double; `_load` rejects a
`current.json` with a foreign `workspace_id` and accepts `generation < metadata.generation`.

### E269.7 Negative proof — declared kills (assertion-only, byte-exact restore)

1. `publication.py::publish_view -> _commit_current` (CT106's named producer).
2. `publish_view -> materialize_publication` (no revision, no intent, no pointer).
3. `_read_sealed_manifest`'s record cross-check (R2: an edited `sealed.json` would publish).
4. R4's copied-tree-vs-manifest comparison (a moved source byte would land).
5. R7's skip-if-equal rule (a resumed projection would rewrite or fail).
6. R8's canonical re-verification (a partial projection would report success).
7. D4's `_unchanged` pre-flight (unmanaged bytes would publish).
8. R9's replay branch (a retry would double-commit).
9. R6's CAS + read-back on `current.json` (a lost CAS would overwrite a newer pointer).
10. R1's state-first ordering (a `PUBLISHED` retry would be refused `STALE_REVISION`).

Reused and **not** claimed as new credit: `_Capture` (walk, fsync, fingerprint staleness, link rules),
`_revision`, `_unchanged`, `_rename_directory`, `_replace_private_bytes`, `_validate_sealed_tree` (E267),
`_proof_only`, `_gate`, `terminal_receipt`.

### E269.8 Definition of done

Red-first evidence per case; `tests/test_workspace_publication.py` + the execution bank
(`tests/test_execution_*.py`) green; `ruff check`, `ruff format --check`, `mypy src/fa/execution`,
`pyrefly check src/fa/execution` clean; `authoring check` `exit_code 0`; all **ten** kills executed with
byte-exact restore and provenance; `ledger.md` E269 result; register row `I03-LIVE-19` unchanged in
wording and status (same file, no new surface) — **no** STEP tick, **no** CT `VERIFIED`, **no** live
verdict, **no** deployment. Known and stated: after a successful publish a supervisor restart still
quarantines the workspace until STEP4's `recover_workspace` exists; the **only** restart-clean path today
is publish → `release`.

### E269.9 Out of scope, leaks and risks

- **Leak (recorded, not fixed):** a crash before `intent.json` exists leaves `revisions/<derived>` and
  `pending/<uuid>` trees with no reference from `current.json`. They are inert but unbounded; STEP4
  classifies them (owned scratch vs unknown) and GC remains out of scope with E268 S4.
- **R1 — size:** ~430 lines in `workspace.py`, ~260 in `publication.py`, 28 cases. Phases are ordered so
  each is independently verifiable; splitting at `materialize`/`project` remains possible without moving
  CT106's kill.
- **R2 — mode fidelity depends on `_materialize_input`:** it restores logical modes onto the view source,
  which is why publishing modes is faithful. A future change that stops restoring modes would rewrite
  every canonical mode to 0600; the happy-path mode assertion is the tripwire.
- **R3 — hard-linked canonical files** are refused (D7); `_Capture` already refuses them at registration,
  so this is consistency, not new behaviour.
- **R4 — `.fa` exclusion is load-bearing:** publication can never carry `.fa`, so an artifact-store file
  is invisible to revisions by construction. Q79 Stage 1 must reason about that boundary; E269 must not
  "fix" it by widening the manifest domain.
- **R5 — `_unchanged`'s global unhealthy flag** is now deliberately reachable from publish (D4); a single
  drifted tree disables the supervisor until restart. Tested, not assumed.
- **R6 — read failure mode most likely to be misjudged by the implementer:** reading a helper's first
  lines and inferring the rest. Mitigation is procedural: quote whole function bodies in evidence, and the
  R5/R6/R9 commit seam gets a second reader on the final diff, not on the plan.


### E269 result — CT106 publish implemented and locally proved (SLICE3 STEP2)

**Status: implemented as a local C1/C3 component. No STEP ticked, no contract `VERIFIED`, no live verdict,
no deployment.** The dispatcher route, the bundle/Q58 half (STEP3) and restart recovery (STEP4) remain
open, so SLICE2's provisioning leg is *not* closed by this.

**What runs now.** `publication.publish_view` drives four durable boundaries, each its own authority
transaction: `prepare_publish` (validate, zero writes) → `materialize_publication` (copy the frozen view
source, verify every entry against the sealed manifest, install `revisions/<derived>`, write
`intent.json` `PREPARED`) → `_commit_current` (CAS `current.json`, then `PROJECTING`) →
`project_publication` (idempotent canonical projection, re-walk proof, `DONE`, clear intent,
`PUBLISHED`, receipt). `verify_publication` is the `PUBLISHED` replay; `abandon_publication` discards only
a provably uncommitted revision.

**Evidence (all re-run at `HEAD`, commands in the ledger).** `tests/test_workspace_publication.py`
**58 passed** (32 pre-existing CT104/CT105 + **26 new CT106 cases**); execution bank with it
**1146 passed**; `ruff check`/`ruff format --check` clean; `mypy src/fa/execution` 19 files; `pyrefly` 0
errors; `authoring check` `exit_code 0`, `diagnostics []`. **10/10 declared kills executed** with
sha256-verified byte-exact restore (one needed a new oracle: see mutant 3 below).

**Three implementation findings, recorded rather than smoothed over.**

1. **D11 — destination-type pre-flight (implementation refinement of D7/D9).** The first draft let a
   symlink-standing-where-a-file-must-go fail during projection, i.e. *after* the pointer, which
   surfaced as `DURABILITY_UNKNOWN`. That is exactly the failure class D9 exists to prevent, so
   `prepare_publish` now type-checks every non-deleted destination (regular single-link file / matching
   symlink / directory) before the pointer and refuses `PATH_DENIED`. Judged a refinement, not a new
   policy: same refusal, earlier and typed. **If the operator disagrees, this is the line to promote.**
2. **`_derive_revision_id` lives in `workspace.py`.** The id names a directory under `revisions/`, so the
   storage module owns the formula and `publication.derive_revision_id` delegates. One implementation
   means a drifted derivation cannot silently disagree with itself (the E259/E264/E265 drift pattern).
3. **`tree.json` never carries tombstones.** `_TREE` pins `deleted` to `False`, so the revision stores
   the manifest's live entries only; tombstones stay a manifest/transport fact. Asserted in the happy
   path rather than assumed.

**Mutant 3 needed a new oracle, which is the interesting part.** Removing the manifest-vs-record
cross-check survived the first sweep: every existing test failed *earlier*, either in the seal validator
(a tampered digest) or in the copied-tree comparison (moved bytes). The cross-check only matters when a
manifest is internally valid but belongs to another grant, so the new case seals two views of the same
revision and copies one view's `sealed.json` into the other. Its identity fields are then the only thing
standing between a sibling's provenance and this grant — `CORRUPT_STATE` at prepare, pointer untouched.

**Explicitly not proved here.** No Docker/cgroup barrier, no dispatcher route, no restart recovery, no
Q58/BOOTSTRAP path, no retention/GC, no live host. The "published but not released ⇒ restart quarantines"
case is asserted as the STEP4 limit, and "publish → release ⇒ restart-clean" is the one claimed clean
path. Register: `I03-LIVE-20` added (`PLANNED / UNEXECUTED`) with the full host choreography and the two
negative controls; the S06 join row updated to say both halves now exist locally.

### E271 result — STEP3 unit A: trusted bundle renderer + private store (Q58/install open)

**Status: unit A of SLICE3 STEP3 implemented and locally proved. `install_project` is BLOCKED on Q82 and
`publish_plan` (Q58) is not started — STEP3 is NOT done, and nothing here ticks it.**

**What runs now.** `publication.render_bundle` is a pure renderer over plain prose producing exactly the
three spec §7.1 paths, with controller-owned frontmatter (`RM-<slug>`, `RM-<slug>-I01`, created, statuses,
actual slice count, `shipped: —`), a fixed ledger heading, and a fixed Artifacts/Increments table.
`publication.prepare_bundle` validates and stores it through
`WorkspaceAuthority.store_bundle`: OWNER grant + no view + no intent, exact `base_revision` CAS, staging
under `pending/` renamed in with `RENAME_NOREPLACE`, and one self-contained directory
`bundles/<bundle-id>/{bundle.json, worklogs/<slug>/…}` — no shared index a concurrent prepare could
corrupt. The reply is `{validated_bundle_id, bundle_sha256}` per the wire row.

**Evidence.** `tests/test_workspace_publication.py` **67 passed** (9 new: 5 C0 renderer, 3 C1 storage, 1
C3 traversal); execution bank with it **1220 passed**; `ruff check`/`format --check` clean (507 files);
`mypy` 19 files; `pyrefly` 0 errors; `authoring check` `exit_code 0`, `diagnostics []`. **7/7 new kills**
executed with sha256-verified restore: disguised-metadata scan, exact-heading rule, slice contiguity, fixed
frontmatter, bundle base CAS, unsettled-view refusal, bundle path traversal.

**Two things the implementation changed, both recorded.**

1. **Path traversal is refused twice, deliberately.** `protocol._check`'s `_byte_limits` already rejects
   `.`/`..`/empty components for any `path` key, so `store_bundle` now translates that
   `ExecutionContractError` into `INPUT_POLICY` instead of letting it escape as an authority failure; the
   writer keeps its own component guard as defence in depth. Reuse first, duplicate second, never invent.
2. **A bundle is one directory, not a directory plus an index.** The first draft kept a shared
   `bundles/index.json`; a second prepare would have overwritten it. Each bundle now owns its manifest, so
   "the bundle I prepared" and "the bundle I install" cannot be confused.

**Deliberately not done, with the reason.**

- **`install_project` is blocked on Q82** — whether a bundle installs as a sibling project directory or in
  place inside the preparing workspace changes what `_COMMITTED`'s `revision_id` means and which root may
  be created in. The mechanism (no-clobber rename, BOOTSTRAP intent before install, never delete an
  installed bundle) is settled; the destination is not, so no code was written for it.
- **`publish_plan` (Q58) is not started.** It is the inverse of E269's order — the canonical plan replace
  *is* the irreversible point, before any pointer commit — and it needs its own PLAN-kind phase ordering.
  Starting it late in a session to claim STEP3 would be the same defect this project keeps recording.
- No dispatcher route, no auto-registration of an installed project, no GC for stored bundles.

### E272 result — adversarial review of `e4fcfae`: eight findings verified, seven closed

**Status: the review's findings are closed and the owning bank is green. STEP3 is still NOT done
(install and `publish_plan` remain) and nothing here ticks a STEP or assigns a CT verdict.**

**Method.** Each finding was re-derived from source before any edit; none was accepted on assertion,
and none was rejected. Where a fix was possible two ways, the one that removes the defect *class* was
chosen over the one that repairs the instance (F2 below is the clearest case).

| # | Finding | Verdict | Disposition |
| --- | --- | --- | --- |
| F1 | `prepare_publish` loaded base entries only when the view was `SEALED`, so any replay validated the manifest against an empty base. Three `_validate_against_base` rules compare each entry with its base, so replay of any manifest carrying a tombstone, a symlink or a plan was refused — i.e. replay was unreachable for every real workflow. | **real, functional** | Base entries now load unconditionally; only the pointer-equality check stays in the `SEALED` branch. Three replay cases (tombstone / symlink / plan) added; mutant killed. |
| F2 | Projection temporaries were created as `.<name>.<uuid>.publish` **in the canonical directory**, so a killed process left debris that `_verify_projection` and `_unchanged` would see as drift, quarantining a workspace whose only sin was being interrupted. | **real, class-wide** | The class is removed, not swept: temporaries live in `<root>/.fa/publish-tmp` (same filesystem for atomic `os.replace`, and `.fa` is excluded at any depth so debris is structurally invisible), and every projection sweeps its own abandoned `*.publish` files first. Mutants killed: temporary-in-canonical-dir, no-sweep, and the scratch-mode regression below. |
| F2a | Second-order defect found while testing F2: `_temporary_directory` demanded `_private` (0700) on every component, but `.fa` is the project's own artifact directory and is normally 0755 — that would have refused **every** publish in a real project, with `CORRUPT_STATE`. | **real, introduced by F2** | Only "a real directory of ours" is required (`O_NOFOLLOW` already refuses a link); no mode demand on a directory inside the user's own tree. Pinned by a case that plants a 0755 scratch. |
| F3 | `_BUNDLE_FILE` had no `mode`, so install would have chosen one at install time and frozen it into the project's genesis revision. | **real** | `mode` is now recorded per file (0644) and once per bundle for directories (0755). Done now, while the schema is still unshipped. |
| F4 | `_outside_fences` was a hand-rolled ``` scanner, so `~~~` fences and 4-space indented blocks were read as prose: metadata could be smuggled inside either, and a fenced `## SLICE2:` could be counted. §7.1 asks for the existing MarkdownIt tokens. | **real** | The project's existing `markdown_it` dependency yields the tokens; code blocks are blanked (line positions preserved), everything else unchanged. Hand-rolled-scanner mutant killed. |
| F5 | `slices: {max(slices)}` where §7.1 says "actual extracted count". | **cosmetic** | Behaviourally equivalent: the same validator refuses non-contiguous slice numbers, so `max == len` whenever rendering succeeds. Changed to `len` for honesty; no kill exists and none is claimed. |
| F6 | Every `prepare_bundle` mints a fresh id, so identical retries accumulate bundles under `bundles/`. | **accepted by design** | Ids are never reused, because "the bundle I prepared" must not be confusable with an earlier attempt's. Retention is a GC concern for a later increment; recorded here so it is not rediscovered as a defect. |
| F7 | `_owner_only` selected the first binding matching principal+actor and *then* compared the digest, so a caller holding a valid grant on a second workspace got `UNAUTHORIZED` whenever the first matching binding was someone else's. | **real** | The capability is now part of the selection predicate. Mutant killed. |
| F8 | `COMMITTED` is never written (`PREPARED → PROJECTING → DONE`). | **not a defect, needs a record** | §5.1 already says a missing `COMMITTED` write is not evidence that the replacement happened; the recovery decision inspects the target directory, so writing the phase would add a durable write with no branch depending on it. Recorded for STEP4: **recovery must never key on `COMMITTED`** (see the §5.1 note). |

**Q82 settled.** The install destination is **(B) in place** — `<workspace root>/worklogs/<project_slug>`,
with `_COMMITTED.revision_id` naming the preparing workspace's new revision. The ruling, its four
evidentiary grounds and the binding rules it implies are recorded in
[`notes/open-questions-2026-10-07.md`](../notes/open-questions-2026-10-07.md#q82--where-does-a-prepared-bundle-install-and-what-identifies-the-project-it-creates).

**Evidence.** `tests/test_workspace_publication.py` **76 passed** (9 new: three F1 replay cases, two F2
cases — the sweep case also pins the 0755 scratch mode —, F4, F5 pin, F3, F7); execution bank + CLI **1229 passed**; `ruff
check`/`format --check` clean on the three changed files; `mypy src/fa/execution` 19 files; `pyrefly
check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`, `diagnostics 0`. **7/7 mutants
killed** with sha256-verified byte-exact restore (`F1`, `F2` location, `F2` sweep, `F2a` scratch mode,
`F3`, `F4`, `F7`); F5 has no mutant because none exists.

Not proved, and not claimed: the Docker/cgroup barrier, the dispatcher route, restart recovery (CT107,
STEP4), Q58/`publish_plan`, retention/GC, and the live host.

### E271 unit B result — `install_project` implemented on the Q82 (B) ruling

**Status: SLICE3 STEP3's install half is implemented and locally proved. STEP3 is still NOT done —
`publish_plan` (Q58) remains — and nothing here ticks a STEP or assigns a CT verdict.**

**What runs now.** `publication.install_project` validates and hands off; `WorkspaceAuthority.install_project`
owns the whole irreversible step. Order is §5.1's BOOTSTRAP row, deliberately *not* publish's: preconditions
(owner grant, no settled view, no intent, canonical bytes still the current revision, bundle bound to this
workspace/generation/base/slug) → the complete post-install tree is computed and digested *before* any write
→ `intent.json` (`kind=BOOTSTRAP`, `target_relative=worklogs/<slug>`, `new_sha256` = bundle manifest hash) →
the bundle is copied into `<root>/.fa/publish-tmp/<op>` and fsynced (same filesystem, invisible to every
walk) → `renameat2(RENAME_NOREPLACE)` → revision from the canonical tree the rename just created →
`current.json` → projection proof → `DONE`. The bundle is never moved, mutated or deleted.

**Two decisions recorded.** Q82 is settled as **(B) in place** (see the open-questions file for the four
grounds). Q83 records why the operation id is derived from the bundle (`op-` + the bundle's hex): the wire
carries none for this call, and a retried install must correlate to the *same* operation for §5.1 recovery.

**One defect found by the unit's own kill-check, and fixed.** The expected entry list was first sorted
component-wise (`a/b` before `a.md`), but `_Capture.finish` orders entries by **plain path string**, so a
workspace containing a file whose name sorts next to the project directory produced a tree whose digest
could never match. The test written for that refactor (`test_install_orders_entries_as_the_capture_walks`)
caught it at once; the sort is now the capture's own order and the case stays as the oracle.

**What is refused, with nothing written.** `COLLISION` for an existing destination (including the
check-then-rename race, where an *empty* racing directory would have been silently replaced by an ordinary
rename), `STALE_REVISION` for a bundle prepared against another revision, `STALE_GENERATION`, `UNAUTHORIZED`
for a bundle directory copied into the wrong store, `INPUT_POLICY` for an unknown id or a retargeted slug,
`WORKSPACE_BUSY` for an unsettled view.

**Evidence.** `tests/test_workspace_publication.py` **87 passed** (10 install cases); execution bank + CLI
**1240 passed**; `ruff check`/`format --check` clean on the changed files; `mypy src/fa/execution` 19 files;
`pyrefly check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`, `diagnostics 0`. **8/8 mutants
killed** with sha256-verified byte-exact restore: no base CAS, ordinary rename instead of `RENAME_NOREPLACE`,
no pointer commit, no bundle digest check, no durable intent, empty base entries, chmod of an existing
`worklogs`, component-wise entry order.

**Deliberately not done, with the reason.** Recovery (`CT107`, STEP4) — the intent this unit leaves behind is
the input to it, and no recovery row is implemented or claimed; the dispatcher route (SLICE1 STEP3);
auto-registration of the installed project (SLICE5); bundle GC/retention; and `publish_plan` (Q58), which
is the inverse ordering (the canonical plan replace *is* the irreversible point) and needs its own phase
analysis. `I03-LIVE-22` is PLANNED / UNEXECUTED: no Docker/cgroup barrier, no installed service, no restart.

### E273 result — SLICE3 STEP3 unit C: `publish_plan` (Q58) implemented and locally proved

**Status: STEP3's plan half is implemented. STEP3 is still NOT complete — routing the controller through
it (the dispatcher leg) is what remains — and nothing here ticks a STEP or assigns a CT verdict.**

**The order is the inverse of publish, on purpose.** `publication.publish_plan` validates and hands off;
`WorkspaceAuthority.publish_plan` owns the boundary. Every precondition and the *complete* post-replace tree
are computed before any write (owner grant; no unsettled view; no intent; canonical bytes still the current
revision; the ref's path is exactly `worklogs/<slug>/increments/<name>.md`; the buffer passes the plan rules —
strict UTF-8, non-empty, ≤ 1 MiB; the ref's hash is not the hash of the bytes being written) → durable
`intent.json` (`kind=PLAN`, `target_relative`, `old_sha256`, `new_sha256`, `next_revision`, `phase=PREPARED`) →
`os.replace` of a staged, fsynced, mode-preserving sibling **at the same path** (the irreversible point) →
parent fsync → revision from the canonical tree the replace just created → `current.json` → projection proof →
`DONE`. After the replace there is no step that can restore the old bytes: recovery is forward, by design.

**One mechanism, shared with install (refactor, behaviour-neutral).** `_install_write_revision` and
`_install_commit_current` are now `_write_revision_from_canonical` / `_commit_pointer`, and both forward-only
kinds call them; install is the case where the directory was renamed, replacement the case where the file was.
`_forward_gates` (view/intent check, writability probe, `unchanged` proof) is likewise one helper now. The
install bank stayed at its full size through the refactor — the one test that patched the old private names by
string was re-pointed, and that is the only edit the refactor needed.

**What is shared with `inner_loop/plan_promotion.py`, and what supersedes it.** The *rules* are imported,
never retyped: `_decode_plan_bytes` (strict UTF-8, non-empty, ≤ 1 MiB), `PlanRef`, `PlanSnapshot` from
`plan_admission`. The *transport* cannot be reused from inside the authority: `publish_plan_buffer` reopens the
workspace by host path (which §4's rooted, no-follow IO exists to forbid) and takes a second, path-keyed lock
inside the authority's own mutex. So the promotion discipline — prove the source hash, stage a unique sibling,
fsync, replace the same path, prove the result, never leave a second active plan — is reproduced on
descriptors, and serialization comes from the authority mutex plus the pointer CAS instead of a lock file. The
old transport is not a fallback: it is deleted when the controller is routed (see the last paragraph).

**Two checks were deleted because they could not disagree with the copy proof (found by the unit's own
mutants, which survived).** (a) The revision-level source CAS in `_plan_prepare` was dropped: the pre-replace
re-proof compares the ref's `old_sha256` against the bytes that `_forward_gates`/`_unchanged` has just proved
equal to the current revision, so the two comparisons cannot differ — the surviving double is the one that also
closes the TOCTOU window. (b) The post-replace hash/mode re-check was dropped for the same reason:
`_write_revision_from_canonical` copies this exact path and refuses the whole tree unless every entry's size,
digest, type and mode match *before a revision or pointer exists*. Q58's "post-hash/mode checks" are therefore
satisfied by the copy, not by a second check that could never fire on its own.

**The path shape is enforced here, not by callers.** `publish_plan` is not a general controller file-write API
(spec §7.1, Q58's "not an arbitrary model file-map API"): exactly four components, `worklogs/<slug>/increments/`
and a `.md` leaf, no `.`/`..`/empty component, no protected component. Anything else is `INPUT_POLICY`, or
`PATH_DENIED` for a protected component.

**Refusals, all with nothing written.** `STALE_REVISION` for a stale ref hash (also when the plan vanished
between prepare and replace), for a concurrent host write detected by the pre-replace re-proof, and for a plan
whose bytes are the ones already there is `INPUT_POLICY` (a replacement must replace something);
`PATH_DENIED` for a link swapped in after staging (`O_NOFOLLOW` + `O_NONBLOCK` open, then regular-file and
single-link `fstat`); `INPUT_POLICY` for bytes that are not a plan, for a path that is not the canonical plan,
and for an entry that is not a committed regular file; `UNAUTHORIZED` for a capability that is not this
workspace's owner grant; `WORKSPACE_BUSY` for an unsettled view or an existing intent. A symlinked plan can
never reach a revision at all: admission refuses the ref (`symlink`) and registration refuses the tree.

**Failures after the replace keep the truth and stop serving.** `DURABILITY_UNKNOWN` for an I/O failure
(including the parent fsync), `CORRUPT_STATE` when the copied tree provably differs from the expectation; in
both cases the intent stays `PREPARED`, `_healthy` goes false, and a later operation is refused because the
canonical tree no longer matches any committed revision. No rollback, no replay, no receipt.

**Evidence.** `tests/test_workspace_publication.py` **99 passed** (12 replacement cases, C1 over the real
authority); execution bank + publication **1190 passed**; `ruff check`/`format --check` clean on the three
changed files; `mypy src/fa/execution` 19 files; `pyrefly check src/fa/execution` 0 errors; `fa
authoring-check` `exit_code 0`, `diagnostics 0`. **10/10 mutants killed** with sha256-verified byte-exact
restore: no pre-replace re-proof, no durable intent, no mode preservation, follow the replace path, no plan byte
rules, any path replaceable, no revision commit, rollback after replace, identical bytes accepted, no forward
gates. Two further candidate mutants were removed from the sweep rather than "fixed": the parent-fsync ordering
and the `_healthy` flag are not observable in-process (the API-visible consequence of the latter is the
canonical-vs-revision drift refusal, which is asserted).

**Deliberately not done, with the reason.** The controller leg: `_promote_validated_plan` still calls
`inner_loop/plan_promotion.publish_plan_buffer` directly, because the authority route needs the dispatcher
(SLICE1 STEP3) and a controller-side client handle. That route is the **`publish` of a CANDIDATE view**
(§5: "publish of CANDIDATE uses PLAN intent at the scoped canonical PlanRef path"), not a twentieth
operation — the closed enum stays nineteen, so `publish_plan` is the authority's primitive and never a
wire verb. Until the route lands, the transitional rule is explicit: the
authority refuses any seal whose plan bytes moved outside it (`_validate_plan_boundary`), so mixing the two
writers fails closed instead of silently forking the plan; the switch to a single writer must delete
`publish_plan_buffer`, not keep it as a fallback. Recovery of a `PLAN` intent is CT107/STEP4 — the intent this
unit leaves is its input. `I03-LIVE-23` is PLANNED / UNEXECUTED: no Docker/cgroup barrier, no installed
service, no restart.

### E274 result — SLICE1 STEP3 part 1: the pre-reservation authority check (CT99)

**Status: the dispatcher's `authorize` seam is real. STEP3 is NOT done — the nineteen handlers and
`build_supervisor/main` are the next part — and nothing here ticks a STEP or assigns a CT verdict.**

**What was missing.** `SupervisorDispatcher` existed with an injected `authorize`/`handle` pair, but
every construction of it was a test double (`tests/test_execution_dispatch.py`,
`tests/test_execution_context.py`): "authorized" meant "a fixture said so", and the authority's grants
were only proved *inside* each handler, after a journal reservation. A request that could never own
anything therefore still consumed a reservation.

**What runs now.** `WorkspaceAuthority.authorize(peer, request, *, deadline)` — CT99's
`_authorize_request` owner — decodes the closed envelope, proves the grant the operation names
(`_owner_only` for a view-less request, `_proof_only` for a view-scoped one; `RELEASE` therefore keeps
exactly its two shapes without a special case), and returns the **stored** `ProtectedPlanContext` for
`pin_reader`, `create_view` and `exec`, rechecked against the pinned bytes. It reserves nothing, mints
nothing, writes nothing, and is not admission: every state rule (view state, publication ordering,
collision, CAS) stays with the handler, which re-proves under its own transaction.

**The layering decision, found by two survivors.** The first version also re-derived the §2.1 envelope
shape inside the authorizer (`_VIEWLESS_OPERATIONS`, `_CAPABILITY_FREE_OPERATIONS`). Three mutants
survived because those rules **could never fire**: `authorize` decodes with the same
`decode_request` the dispatcher uses, and that decoder already enforces the null-capability set, the
null-namespace-only-for-health rule and the null-view set. The tables and the duplicate checks are
deleted: the closed wire decoder owns shape, the authority owns proof. The cases stay in the bank as
the composed guarantee (they must still refuse `INVALID_REQUEST`), but they no longer pretend to kill a
second implementation. Two further mutants were retargeted rather than dropped: "any live view instead
of this one" and "namespace not proved" (the second needed a unique anchor inside `_proof_only`).

**One boundary default recorded.** The wire carries no formal-evidence claim, so a plan context built
on the wire has `formal_evidence=False`; only the internal API can set it true. A wire request can
therefore bind a plan but can never claim formal evidence for it.

**Classification is derived, not retyped.** `supervisor.py` now owns `READONLY_OPERATIONS` and
`AUTHORITY_GATED_OPERATIONS`; the dispatcher refuses to construct if a mutator could ever be classified
readonly, and `_dispatch` uses the constant instead of an inline literal set.

**Evidence.** `tests/test_workspace_authorize.py` **10 passed** (C1 over the real authority, C0 for the
classification); execution bank + publication + this bank **1200 passed**; `ruff check`/`format --check`
clean; `mypy src/fa/execution` 19 files; `pyrefly check src/fa/execution` 0 errors; `fa authoring-check`
`exit_code 0`, `diagnostics 0`. **7/7 mutants killed** with sha256-verified byte-exact restore: no owner
proof, any live view instead of this one, no workspace claim check, namespace not proved, pin context
not proved, exec context not proved, named revision not opened.

**Deliberately not done, with the reason.** The nineteen `handle` routes and `build_supervisor/main`:
each route needs its own reply-shape proof, and shipping a table of half-wired owners would be the
"failing-main stub" §4 forbids. Also untouched: service config/install/image and the atomic caller
cutover (SLICE4), and the CANDIDATE `publish` leg that carries Q58's plan replacement onto the wire —
that is the `publish` route for a CANDIDATE view (§5), **not** a twentieth operation; the closed enum
stays nineteen. `I03-LIVE-24` is PLANNED / UNEXECUTED: no installed service, no UDS, no restart.

### E275 — ordering verification for the remaining I03 work (no implementation claim)

**Why this exists.** Two units landed that nothing calls yet (`publish_plan` E273, the authorizer E274),
and an E2E lane (SLICE6) is now being written against these commits. Before adding more, the remaining
order was verified against what the repository actually executes, so no unit lands behind a
composition that does not route it.

**Fact 1 — the whole managed path is dormant, and that is verified, not assumed.**
`src/fa/cli.py` never imports `fa.execution`. Nothing in `src/` imports
`fa.execution.{publication,backend,provisioning}`; `ManagedProvisioner` is constructed only in tests;
`build_tools(..., workspace_io=…)` is never passed a port anywhere in `src/`. What users execute today is
the **host** path. So "dead code in prod" cannot happen yet by construction — the live risk is the
inverse: a composition that starts routing a component whose crash semantics are still open.

**Fact 2 — two merged irreversible points have no forward path.** `_load` rewrites every `OWNED`
workspace to `QUARANTINED` and never inspects `intent.json`; `_forward_gates` then refuses any workspace
whose intent survives (`WORKSPACE_BUSY`). A SIGKILL after `install_project`'s `RENAME_NOREPLACE` or after
`publish_plan`'s same-path replace therefore leaves a workspace that can never advance again, and the
E2E rows already registered (`I03-LIVE-22`, `I03-LIVE-23`) assert exactly that it "must recover forward".

**Fact 3 — the remaining items and their real dependencies.**

| # | Item | Record | Depends on | Lands with |
| --- | --- | --- | --- | --- |
| 1 | CT107 `_recover_intent` + stale `pending/` classification | SLICE3 STEP4 | the two shipped irreversible points; `_write_revision_from_canonical`/`_commit_pointer` | its `_load` hook in the same change, so it is live the moment it exists |
| 2 | the nineteen routes + `build_supervisor/main` | SLICE1 STEP3 | 1 (a routed crash is recoverable), E274 authorizer | one change: route table and composition together |
| 3 | CANDIDATE-view `publish` (Q58 controller leg) | SLICE3 STEP3 rest | 2 (a wire `publish` route) | deletes `inner_loop/plan_promotion.publish_plan_buffer` in the same change |
| 4 | provisioner + file-tool port injection, caller cutover | SLICE2 STEP3 injection / SLICE4 | 2 | `SessionManager(workspace_provisioner=…)`, `workspace_io=…`, host `_provision_workspace` removed together |
| 5 | managed acquisition (SLICE5), then accepted package (SLICE6) | SLICE5/6 | 3, 4 | — |

**Addendum (E282, 2026-10-23).** Q85 is answered, so the `handoff` row now has an owner: SLICE2 STEP6/CT113. Items 3–5 remain unchanged and unstarted.

**Status of this table (2026-10-23).** Item 1 is delivered by E276 — `_recover_intent`, the stale
`pending/` classification and the `_load` hook all shipped in one change, as the "lands with" column
required. Item 2's route table and composition are delivered by E277, E278 delivered the
`CellTermination` join its `stop_view` route needs, E279 the receipt issuer (`exec`, `inspect`, `cancel`)
and E280 `pty_control`. Items 3–5 are unchanged and none is started; `handoff` and
`register_workspace{create:true}` stay dormant until their owners land.

**Why recovery precedes the routes, in one sentence each.** (a) Routes multiply the number of ways to
crash into an unrecoverable workspace, so the recovery owner must exist first. (b) The E2E lane cannot
pass its registered fault rows without it. (c) Routes add no durable semantics, so nothing in them is
blocked by going second — whereas a route table built first would have to be re-opened to thread the
recovery outcomes.

**Why the routes and `build_supervisor` are one change.** A route table with a handler that no
composition can construct is the "failing-main stub" §4 forbids; conversely a `main` that serves a
subset is a silent-success surface. The route-coverage test (every `Operation` member routed, none
extra) is the guard, and it must land with both halves.

**Dead-code rules adopted by this ordering (binding for the remaining units).**

- **R1 — join or declare.** A unit either gains an executing caller in the same change, or is listed in
  this table as dormant with the unit that activates it. No third state.
- **R2 — one enum, one table.** No `Operation` member without a route in the same change; the closed
  enum stays nineteen, and `publish_plan`/`recover_*` are authority primitives, never wire verbs.
- **R3 — replacement, not addition.** Activating a managed path deletes the path it supersedes in the
  same change (`publish_plan_buffer`, host `_provision_workspace`). A retained fallback is a second
  writer by another name.
- **R4 — recovery first.** No new irreversible point before its recovery row exists.
- **R5 — name the real seam.** A kill target may only name a producer that exists and is called.

**Two plan-text repairs made here (recorded, not silently).**

1. CT107's kill target was `publication.py::recover_workspace -> _recover_intent`, but `publication.py`
   imports `workspace.py`; a `publication.recover_workspace` that only tests call would itself be the
   dead entry this unit is meant to prevent. The producer is `workspace.py::_load -> _recover_intent`,
   which is the seam `__enter__` already owns. CT107's *contract* text is unchanged; only the kill site
   is corrected (R5).
2. §5.1's frozen intent keys do not include the directories a BOOTSTRAP attempt created, while the
   operator-approved Q82 ruling requires exactly that ("record the directories an attempt created so
   recovery can remove exactly those"). The key is added as `created_directories` (BOOTSTRAP only, `[]`
   elsewhere) — executing a recorded decision, not a new one. No v1 intent exists outside tests today
   (Fact 1), so the added required key needs no migration rule yet; if the composition ships before a
   later schema change, that changes.

**Q84 raised (non-blocking, default = today's behaviour).** When recovery cannot materialize a
deterministic outcome, `_load` fails closed and the authority refuses to start — which is exactly what
`_load` already does for every unprovable workspace and what CT107 calls "quarantine". The alternative
(mark that one workspace `QUARANTINED`, serve the others) needs a status meaning distinct from the
existing "previous epoch is dead" flip. Recorded in the open questions with the reopen condition; the
implementation follows the existing fail-closed rule.

### E276 — CT107 forward recovery: inspect the target, never roll back (SLICE3 STEP4 part 1)

**Why this exists.** E275 Fact 2 named the defect this unit removes: two merged irreversible points
(`install_project`'s `RENAME_NOREPLACE`, `publish_plan`'s same-path replace) plus the ordinary
`current.json` CAS left state that no later process could advance. `_load` flipped every `OWNED`
workspace to `QUARANTINED` without ever reading `intent.json`, and `_forward_gates` then refused that
workspace for as long as the intent survived — so a SIGKILL anywhere after an irreversible syscall froze
the workspace permanently, while `I03-LIVE-22`/`I03-LIVE-23` assert the opposite ("must recover
forward"). Recovery is now the first of E275's five ordering items and lands with its `_load` hook in the
same change (R1).

**The discriminator, per kind, is the inspected target — never `phase`** (§5.1, E272 note).

| Kind | Inspected | Completed forward | Discarded |
| --- | --- | --- | --- |
| REVISION | `current.json` vs `intent.base_revision`/`next_revision` | pointer already `next_revision`: re-project that revision's own `revisions/<id>/data` (idempotent per entry), prove the whole tree, settle the view, `DONE` | pointer still `base_revision` **and** phase `PREPARED`: discard only the owned, re-derivable `revisions/<next_revision>` |
| PLAN | the canonical plan file's own sha256 | hash `== new_sha256`: rebuild the promised tree from the named base revision plus the observed size/hash, then revision/pointer/proof/`DONE` | hash `== old_sha256`: nothing to undo; discard the uncommitted revision and clear the intent |
| BOOTSTRAP | the installed directory at `target_relative` | present: the whole canonical tree must hash to `intent.tree_sha256`, then revision/pointer/proof/`DONE` | absent: discard the attempt's own scratch, remove exactly `created_directories`, prove canonical still equals `current`, clear the intent |

Anything else — a pointer naming a revision this attempt never named, a projected phase with no commit,
a plan hash that is neither side, an installed tree that is not the approved bundle, canonical drift
where the attempt would have to undo something — raises `CORRUPT_STATE` and the workspace keeps its
intent as evidence. No path rolls committed bytes back to `Rold`, and no path reports success for an
observation it did not make.

**Ordering repair in `project_publication` (a defect removed, not a test adjusted).** The publish path
previously wrote `DONE`, **cleared the intent**, and only then flipped `view.json` to `PUBLISHED`. A kill
in that window left a `SEALED` view holding a committed revision with no intent: `prepare_publish`
refuses the retry (`current != view_ref.base_revision` → `STALE_REVISION`), `release_unused_writer`
accepts only `PUBLISHED|REJECTED`, and no evidence remained to reconstruct which view the commit
belonged to. The settle write now happens **before** the clear, so the intent outlives the last
unrecoverable step, and `_recover_revision` performs the same tail.

**Intent schema extension: `view_ref` (nullable).** Completing a committed publish forward is not enough
— the view record must be settled or the owner can never be released. The intent therefore carries the
view it published (`null` for `PLAN`/`BOOTSTRAP`), which is how recovery knows which record to prove and
flip. This is the same class of extension as `created_directories` (Q82): executing a requirement CT107
and CT106 already state ("completes committed projection forward", "publishing settles the owner"), not a
new decision. §5.1's key list is again amended rather than silently exceeded. Because `_INTENT` requires
every key, an intent written by the previous build would now quarantine; no such intent exists outside
tests (E275 Fact 1 — nothing in `src/` constructs the authority), so no migration rule is owed yet.

**Where it runs, and what failure costs.** `_load` calls `_recover_at_load` after `_verify_revision` (which
already proves `revisions/<current>/tree.json` is the bytes `current.json` names) and `_initialize_genesis`,
and before the `OWNED -> QUARANTINED` write, so recovery always sees the status the crash left. It also runs
before the Q80 pointer check, which now reads `binding.current` because recovery may advance the pointer.
Three consequences, stated rather than inherited:

1. **Q84 is answered by the implementation as the shipped per-workspace rule.** An unsettled workspace
   keeps its intent and is held by the same `QUARANTINED` write that holds every restarted workspace;
   every other workspace keeps loading. Only `DURABILITY_UNKNOWN` — the authority's own writes no longer
   reading back — escapes and refuses the whole start, which is the existing poison rule for anything it
   cannot prove (`_healthy = False`). E275's wording described this as a start refusal; the shipped
   behaviour is the narrower one, and it is what `_load` already did for a leftover intent.
2. **`_verify_revision` still gates the load.** A pointer whose durable revision is missing fails the
   whole load before recovery, because that is unprovable state rather than an interrupted attempt.
3. **Recovery is outside every grant.** It takes no capability, proves no peer and writes no journal
   entry: it is the authority inspecting itself, and the mutex plus the catalog loop serialise it.

**Stale `pending/` staging.** `pending/<uuid4().hex>` has exactly two producers (`store_bundle`'s bundle
copy and `_write_revision_from_canonical`'s revision copy) and neither is ever the committed artifact:
committed revisions live under `workspaces/<id>/revisions/`, which this sweep never opens. `_load`
discards an entry only when its name is the 32-hex stage form, it is a private directory owned by this
authority, and it satisfies `_discard_stage`'s own ownership check; anything else refuses the start and is
left for an operator. That satisfies STEP4's exit clause (a killed supervisor leaves no `pending/` entry a
later authority silently ignores) without inventing a "probably ours" deletion rule.

**Replacement, not addition (R3).** One forward-only tail `_finish_forward` now serves
`install_project`, `publish_plan` and both recovery completions, so "revision, pointer, proof, `DONE`" has
one implementation and one idempotent replay path. `_plan_entries`, `_remove_created` and `_settle_view`
were extracted from the producers that already did that work (`_plan_prepare`, `_install_abort`,
`project_publication`), and `_project_entries`/`_project_file`/`_verify_projection` now take the byte
source and entries explicitly instead of a `_ProjectView`, which is what lets recovery replay a committed
revision from `revisions/<id>/data` rather than from a live view that may no longer exist.

**Evidence.** `tests/test_workspace_recovery.py` **22 passed** (C3: real authority, real filesystem, kills
driven by `SystemExit` at named producers so no `except`/`finally` cleanup runs; C1 for the planted
intent/pointer states). Adoption banks: execution bank + publication + authorizer + this bank
**459 passed**; whole `tests/` **682 passed, 1 error** in the sandbox before the `uv`-dependent
`tests/test_controller_entry.py` cases (6 setup errors from the rebuilt environment's empty `uv` cache
under `--offline`, unrelated to this unit). `ruff check`/`format --check` clean; `mypy src/fa/execution`
19 files; `pyrefly check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`,
`diagnostics 0`. **17/17 mutants killed** with sha256-verified byte-exact restore: intent
workspace/epoch guard, phase-vs-pointer guard, keeping the uncommitted revision, completing a revision
the pointer does not name, the completed-projection proof, the settle write, the revision-vs-intent hash
guard, the "old plan bytes" branch, the recomputed-vs-promised plan tree, `_remove_created`, the
canonical-drift proof before undoing, the installed-tree proof, the staging name check, discarding the
staging, both `view.json` proofs, and the single intent-clear.

**Deliberately not done, with the reason.** STEP4 stays unticked: this is the local C0/C3 half. Still
owed are the kernel-observed crash matrix on the approved filesystem (`tests/integration/
test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`, including kills *inside* recovery
itself), the explicit process-crash versus power-loss labelling, and the fsync-unsupported/EIO cases —
none of which a process-only `SystemExit` can produce. `bundles/` retention is left alone: a stored
bundle is a valid retained artifact (E271), and garbage collection is its own unit with its own
reachability rule, not recovery's business. `I03-LIVE-25` is PLANNED / UNEXECUTED: no installed service,
no UDS, no real kill, no restart.

## Scope and ownership handoff

Migration groups A/B/C/E/D/F map respectively to SLICE1/2/3/4/5/6. CT96/CT97 original producer
kills retained; CT88/CT89 and former SLICE7 STEPs1–10 retain IDs inside final SLICE6. Clause
successors for retained CT90/CT92–CT95: managed capability/selection/schema → SLICE5; supervised
IO/PlanRef/promotion → SLICE2/3/4. Local CT66 parser remains I02; supervised binding → SLICE4.
E223's four acceptance successors are SLICE6 STEP7/9/10 and the explicit DoD items above;
[migration bank §9](../notes/i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16)
keeps the mapping and uncompleted status. No ownership transfer is evidence, no old unique case
is deleted or assigned PASS. The local plan-versus-diff review remains I02 work, not a substitute
for I03's final broad review. No successor box is checked by this documentation change.

Not delivered: old per-slice scheduler/tracker/L2-eval/TEST-DEFECT/CT10b/tests_note consumers. They
remain the roadmap's named deferred successor; foundation shipping neither expires operator ticking
nor provides L2 VERIFIED. I04–I06 numbering and Q64→I06 unchanged. Parallel orchestration, CAS/
overlay/backend matrix, advanced privacy/anti-persistence/GC, package-proxy platform and calibration
remain outside I03. PTY/FastAPI is a cell transport choice, not a fourth role or independent milestone.

## E250 — E2E source/seam inventory repaired before further implementation

The existing live register previously omitted explicit I03 entries. It now tracks all14 added
Python modules, both modified production surfaces and8 cross-module joins against exact source
hashes/AST inventory.16 omitted-module controls fail; no live case is implemented/executed by this
inventory. Historical I02 project-import/env assertions apply inside cells, not the controller.
Next dependency-ready STEP1 seam: dispatcher must pass authenticated peer and original absolute
deadline explicitly through authorization/handler to actual backend/admission (§2.2, F20/F21),
not infer identity from namespace or reset command budget. Actual owners/SLICE2 remain unfinished.

## E252 — confirmed worker handoff repaired; actual owners NEXT

E252 repairs the E251-confirmed reply-visible/RUN-gate-retirement race in cell_worker.serve.
Production best practice: use the existing publication lock as one linearization boundary for
next-RUN admission and completed-RUN gate retirement, including reply-write failure cleanup.
No retry, scheduler, timeout increase, policy change or parallel command execution. Concurrent
controls and main-thread PTY acquisition/prior-thread join remain. Unavailable stream is still
uncertain; STOP/worker exit remains no cgroup/terminality proof.
TEST-EDITS: tests/test_execution_attach.py — append one deterministic real worker/PTY/UDS/attach
scheduling regression; old file is an exact byte prefix. Native-lock wrappers expose the window,
not fake worker results. Unfixed source fails the admission assertion [True, False] != [True]
(1failed/52deselected0.70s, clean setup/teardown); fixed focused127PASS5.53s.
Final whole15-module owning bank733PASS43.25s → eleven whole733-bank assertion-only kills
26/62/26/26/4/16/2/2/1/1/1 → restored733PASS42.43s. Both worker producers (admission coordination,
retirement-inside-publication) kill independently. All phases clean except intended mutant CALL
assertions; no skips/warnings/collection/runtime/infra credit. All598 source/input hashes
exact; supervisor.py AND cell_worker.py independently match frozen snapshots. Ruff/format27PASS,
Mypy27/183PASS; configured+clean-path Pyrefly0errors (existing141suppressed/50warnings).
Broader28modules1253PASS57.98s, including the actual E251 failing sequential-RUN test.
E2511251PASS1FAIL remains immutable red history, repaired by this changed source, not a rerun waiver.
Evidence `notes/evidence/i03-e252/worker-handoff.json.gz`, 1173316bytes SHA25683da84e828616b1b109579c83866c166f9cefb08348a0eb06fe285fbba4f7c40.
C0/C3 component proof only; C1 actual authority/backend factory and C2 deployed callers remain absent.
E250 inventory unchanged:16 production surfaces/eight joins, all live PLANNED/UNEXECUTED; extend
I03-LIVE-11/S03 with the forced reply-publication/next-RUN schedule. No early host/deployment run.
NEXT implement actual WorkspaceAuthority registration/writer generation/readers/materialization/
admit/drain, reusing E245 RootedViewIO, joined to actual CellBackend per-view episodes/per-command
records and independent terminality; then real factory/caller/mount cutover. SLICE1 is NOT shipped;
SLICE2/all35STEPS/four final duties remain open. Q59/Q75/Q76/final-SLICE6 rollout unchanged.

## E253 — existing-root/R0/writer implemented; actual view/admission/backend NEXT


### E253 — actual owner construction: existing-root registration/R0/writer (before code)

Implement the first real WorkspaceAuthority ownership path in execution/workspace.py; retain
OperationJournal.single_supervisor as the ONE startup lock and journal, not a second lock service.
Existing-root registration is an internal construction API, not a partial production wire dispatcher.
New-root install/provisioning remains the SLICE3 join; do not add a failing factory or permissive gate.
Before snapshot, deployment must already quiesce legacy canonical writers as §4 requires; ordinary
metadata/hash checks detect conflicts, not a kernel CAS or proof of host rollout.

Protected registration uses the exact §3.1 workspace.json schema, initially generation0/AVAILABLE.
Freeze the private initial current.json schema as exactly {schema_version:1,revision_id,tree_sha256};
the retained revision's tree.json is exactly {schema_version:1,revision_id,tree_sha256,entries}, entries
use §5's sorted ordinary tree-entry fields, without deletions for R0. Tree hash is the existing
canonical-JSON nondeleted-entry hash. This is data retention, not a second operation history or seal.
Private manifest cap64MiB is independent of the4MiB wire cap; supported traversal depth is1..64.
Count directory entries while enumerating, before unbounded list allocation. Mutex queueing and
post-generation checks consume the original deadline; expiry cannot issue a grant.
Copy dirty filesystem bytes under descriptor roots, excluding .git/.fa/.venv/.env and configured
exclusions; preserve modes in the manifest, store service-private immutable revision data. No Git
execution/index/config/hooks. Validate relative in-root symlink chains as data, not dereferenced copy;
unsafe links/hardlinks/special files/limits fail. Nested mount crossings fail closed before copy;
Linux fdinfo mount IDs prevent importing an external bind-mounted control tree. Check root identity, approved-root identity and
physical filesystem ancestry (including Linux bind-mount aliases), not only lexical paths.
Stage registration wholly under private state, fsync files/directories/metadata, no-clobber install
then fsync catalog before returning IDs. No canonical mkdir/chmod/chown or registered-tree cleanup.

Acquire holds a per-workspace writer.lock for its lifetime, persists advanced generation plus
owner_namespace/active_actor before creating a memory-only principal+namespace-bound grant. Recheck
canonical bytes against retained current input; detected maintenance changes block/quarantine,
never silently serve stale R0. Release is allowed only for an unused owner with no views/intents;
used-view settlement remains actual admission/backend/publication work. Startup retains pins/views,
quarantines prior OWNED metadata, and never renews old tokens/generations or admits a writer before
real recovery. Persistence ambiguity poisons this owner and blocks further work, not retry success.

Local binary proof: dirty/untracked/deleted/index sentinels and modes; same-inode/physical ancestor/
root-rebind denial; bounded regular copy/link policy; two writer claimers exactly one grant; exact
metadata generation-before-grant, disk secret absence, principal/namespace/release rejection;
startup lock/process contention and restart quarantine; short-write/fsync/copy faults; no canonical
cleanup or mutations on denial. Full owning-bank mutations target root binding/overlap, input policy,
generation persistence and restart quarantine. C0/C3/component sensitivity only, no C1/C2/CT closure.
Then construct immutable pins/views/admission/drain with E245 RootedViewIO and actual CellBackend;
no temporary authority. All checkboxes and final-SLICE6 live rollout obligations remain open.

### E253 implementation/evidence checkpoint

E253 constructs the actual WorkspaceAuthority existing-root/R0/writer path, not a placeholder
admission callback. Reuses the SAME OperationJournal.single_supervisor/startup recovery; one protected
JSON catalog, retained directory identities and per-workspace writer flock, no second DB/service.
Source evidence: src/fa/execution/workspace.py::WorkspaceAuthority:406, register_existing:603, acquire_writer:717, _claim_generation:765, _load:541, release_unused_writer:774.
Registration captures dirty/binary/untracked filesystem bytes and relative safe link chains under
bounded no-follow descriptors, excludes control/Git/env/cache data, rejects root/inode/physical
ancestry/bind aliases and nested mount crossings, then stages/fsyncs/no-clobber installs private R0.
Canonical bytes/index/modes are untouched. Manifest retention cap64MiB is independent of4MiB wire;
entry enumeration allocates only within the limit; input traversal supports1..64 levels.
Writer generation/owner/actor persists and is reread before a memory-only principal/namespace grant;
mutex queueing and post-durability checks consume the original deadline. Unused release cannot settle
views/intents. Restart quarantines old ownership without renewal; persistence ambiguity fences owner.
Legacy-writer quiescence remains the deployment prerequisite, not proved by source/hash checks.
77 new C0/C3 cases, real Linux FS/FDs/flocks and child processes; bind-mount counterfactuals explicitly
simulate kernel facts, NOT actual deployed mount proof. No existing source/test changed. Found root
selection FD leak: actual new fault regression fails unfixed source by assertion1!=0, repaired via
FD ownership transfer before fallible mount reads, not retry/suppression. Focused77PASS (exact timing in raw proof).
Final whole16-module bank810PASS43.84s → fifteen whole810-bank assertion-only kills
1/4/17/1/14/1/1/1/1/1/1/2/1/1/1 → restored810PASS42.77s. All phases clean except intended mutant CALL
assertions; no skips/warnings/collection/runtime/infra credit. All600 source/input hashes restored
exactly. Ruff/format29PASS, Mypy29/184PASS, configured clean-path Pyrefly0errors (existing141suppressed/
50warnings). Broader29modules1330PASS58.06s. First806 trial's copy mutation rejected for two escaping
consumer domain exceptions; two NEW tests now assert authoritative retained bytes BEFORE idempotency/
restart consumers, no catch/reclassification/old assertion weakening. Controlled stopped FD-review
baseline also preserved without credit. Corrected inconsistent directory-mount counterfactual to
assign the whole subtree one foreign mount ID; development77-case producer preflight retained
WITHOUT final sensitivity credit. Complete prior807/14/1327 proof superseded by final review fix:
non-UTF8 symlink targets now return INPUT_POLICY, not escaping UnicodeError; malformed filename/
target and valid Unicode preservation checked. Pre-fix runtime diagnostic is NOT a mutation kill.
Only fresh final-source full-bank proof above counts.
Evidence `notes/evidence/i03-e253/workspace-owner.json.gz`, 3894523bytes SHA2561d60a28c98cfb4588ce885670e0c3bc98c73bbd6afa381b16288942fd4206faf.
E2E inventory now17 production surfaces/eight joins; new module tracked before coding and omission
counterfactual rejects its removal. E250 historical hashes/E251 red/E252 proof unchanged; ALL live
verdicts PLANNED/UNEXECUTED. No C1/C2/service/host/CT101–103 completion or checkbox tick.
NEXT construct immutable pins/views and actual admit/close-admission/drain using retained E245
RootedViewIO and Q76 protected context, then actual CellBackend episodes/per-command records,
startup owned-cell reconciliation/independent terminality and real factory/caller/mount cutover.
SLICE1 remains NOT shipped; all35STEPS/four final duties open. Q59/Q75/Q76/final-SLICE6 rollout unchanged.


## E254 pre-code declaration — Q77 uniformly positive genesis

Operator delegated the production-engineering solution; select genesis1/first-writer2, preserving
positive identity/receipt contracts rather than introducing READ-only zero exceptions. This
supersedes E253's initial0 (historical evidence unchanged). Code scope is workspace.py plus its
existing tests: guarded durable legacy0 initialization after R0 validation under startup lock,
no-owner/no-view/no-intent/native-writer-lock checks, persist/reread before proceeding; nonzero
untouched. No token minted, no caller activation, no pin/admission stub. CT102/103 prerequisite
and SLICE1 STEP2 dependency only. New C0/C3 actual-FS/lock/fault regressions; old generation
expectations shift by one, all other assertions preserved. Full owning-bank sensitivity removes
initialization call/unsafe-state guard/durable persistence; no runtime or infrastructure kill credit.
Future actual fresh-R0 pin/view/PTY service witness remains planned at final SLICE6; all35STEPS
and four duties stay open. Allowed supporting edits: Q77/spec/HANDOFF/ledger/increment/register/
review/index plus evidence/i03-e254/genesis.json.gz. No runtime dependency/schema changes.

### E254 implementation checkpoint

Q77 resolved by explicit operator delegation to production-engineering judgment: select one
uniformly positive epoch. Registration now persists genesis1/AVAILABLE WITHOUT ownership or a
grant; first writer durably advances to2. Existing positive identities/receipts stay strict; no
READ-only zero exception, extra allocator, DB or token renewal. Old epoch0 initializes only under
the original startup guard after R0 validation, no owner/views/intent and acquired native writer
lock. Private atomic replace/fsync plus exact reread precede accepting work; ambiguity blocks.
Source: src/fa/execution/workspace.py::_load:541, _initialize_genesis:568, register_existing:639.
17 new native C0/C3 cases;94focusedPASS2.30s. Exactly17 pre-existing generation assertions shift
by one; original test prefix otherwise exact except required helper imports. No old assertion
removed/caught. New successful-startup tests reuse the existing closed-domain ok oracle; OS/runtime
failures stay uncaught. Whole16-module827PASS46.39s → seven whole827-bank assertion-only kills
19/12/2/2/1/5/1 → restored827PASS46.42s; all collection/setup/teardown clean, no runtime/
infra credit. All600 frozen inputs exact. Ruff/format29PASS, Mypy29/184PASS, Pyrefly0errors with
existing141suppressed/50warnings. Broader1347PASS59.74s. Fixture-only static diagnostics are
retained in the archive without kill credit. Prior E253 evidence is unchanged.
Evidence: `notes/evidence/i03-e254/genesis.json.gz`, 955682bytes SHA25653ebe8dca0e114c32a766cc75ca770767183ae9ee09bb34b9d4ed604e6c70428.
This fixes genesis identity, NOT a reader grant or pin implementation. Actual immutable pins/views,
admit/close-admission/drain, CellBackend episodes/restart/terminality, service/factory and caller/
mount cutover remain next. SLICE1 NOT shipped; all35STEPS/four final duties remain open. Q75/Q76
and final-SLICE6 host rollout unchanged. Inventory17surfaces/eight joins; all live UNEXECUTED.


## E255 pre-code — actual immutable reader ownership and rooted reads

Construct pin_reader/read_file/release_reader inside the existing WorkspaceAuthority, not a second
service or permissive execution authority. CT102/CT103 retention and SLICE1 STEP2 dependency;
no create_view/admit/CellBackend/full-contract completion from reader construction. Protected
view.json uses the existing exact §3.1 schema, READ/PROJECT, OPEN and operation_ids:[]; base revision
is retained before acknowledgement. Capability/principal/formal policy stay process-private.
Required private formal_evidence + admitted PlanRef are supplied by the trusted caller; construct
ProtectedPlanContext from the actual retained source, never infer policy from PROJECT/null. An
explicit operator-approved view_profile config supplies UID/GID; absent config rejects reader IO,
not guessed deployment identities. No new wire key, profile routing mode or runtime dependency.
Reopen/verify protected revision and view identities; validate complete revision on pin creation,
retain its actual source descriptor/tree entries. Rooted reads reuse E245, hash complete files and
compare retained SHA; no canonical fallback. READ pins ignore later writer generation. Writer
unused-release ignores valid READ retention but still blocks unknown/writable views/intents.
Release revokes this exact reader only, retains revision/metadata, never claims cell terminality.
Read/release/shutdown use the existing original-deadline authority lock through IO so admitted
FDs stay alive; no global journal lock is held waiting on handlers. Per-workspace execution
admission/drain remains separate actual construction work, not fulfilled by this coarse reader lock.
Allowed code: workspace.py and NEW test_execution_readers.py; old source/tests otherwise unchanged.
Allowed supporting files: spec/increment/register/ledger/review/HANDOFF/index and new E255 evidence.
Native C0/C3 proof checks durable source first, actual bytes/hash, cross-epoch pins, proof/plan/path/
read-only/restart/fault/drain boundaries. Full owning-bank assertion-only producer kills and exact
restoration required. Real UDS/tool/PTY witnesses remain planned at final SLICE6; no early rollout.

### E255 implementation checkpoint

E255 implements actual immutable READ retention, principal/namespace/token/exact-ref authorization,
rooted read_file and release_reader in the SAME WorkspaceAuthority. Protected view.json uses the
existing exact schema; durable no-clobber install/fsync/reread precedes acknowledgement. Retained
revision/source descriptors, manifest identity, full-file SHA and actual admitted PlanRef rechecks
prevent canonical fallback or stale private input. Reuses E245 RootedViewIO with read-only access;
required trusted formal policy and explicit approved profile are private DI, not wire/model fields.
READ pins do not compare the newest writer epoch; valid READ retention no longer blocks unused
writer release. Read/release/shutdown share the original-deadline coarse authority lock THROUGH IO,
not a global journal lock. This is reader lifetime serialization, NOT execution admission/drain.
Revocation does not depend on a still-valid plan. Post-revocation uncertainty fences the owner;
successful release closes descriptors/discards heavy entry maps idempotently after readers drain,
retains on-disk references/data, and cannot close reused FD numbers at shutdown. No pin GC/token
reconstruction/new service/dependency or cell permission. Source src/fa/execution/workspace.py:
pin_reader:949, _retain_reader:1032, _reader:1088,
_reader_io:1126, read_file:1167, release_reader:1186.
52 new C0/C3 native cases; combined146PASS3.71s. ALL old test files unchanged. Native UID1001 vs
sample1000 originally masked the read-only mutant with fchown EPERM; corrected only the NEW
counterfactual fixture to permit creation absent readonly. Rejected51-case run retained without
credit. Native three-release FD leak reproduced BEFORE repair by assertion28!=22; controlled
old-source proof stop retained without credit. Actual release-close and reused-FD regression added.
Final whole17-module879PASS48.16s → sixteen whole879-bank assertion-only kills
46/1/2/1/5/3/2/1/27/1/2/1/1/2/1/1 → restored879PASS43.48s; collection/setup/teardown clean, no runtime,
warning, skip or infrastructure credit. All601 source/input hashes restored exactly. Ruff/format30
PASS, Mypy30/184PASS; configured Pyrefly0errors, existing141suppressed/50warnings. Broader30-module
1399PASS63.44s. Producer call replacements use explicit closed counterfactuals, not None-deref
runtime failures; exact scripts/outputs/ordered IDs/source snapshots and diagnostics archived.
Evidence `notes/evidence/i03-e255/readers.json.gz`, 2157199bytes SHA2565f0d802f4665b135aedab84b8cbd6bc1638f618b7eef1eb1f95280c20d363acf.
Pins/read ownership is component proof, NOT writable create_view/materialization, actual execution
admit/close-admission/drain, CellBackend episodes/restart/terminality, service/factory or caller/mount
cutover. Those are NEXT. SLICE1 NOT shipped; all35STEPS/four final duties remain open. Q75–77
unchanged. Inventory17 production surfaces/eight joins; all live UNEXECUTED, final-SLICE6 only.

### E256 pre-code — verified remaining SLICE1 and working PROJECT view dependency

Source inspection at9fe2a6c: supervisor.py has dispatcher/reply cache, no build_supervisor/main;
backend.py absent; WorkspaceAuthority has no create_view/write_file/admit/close-admission/drain.
DockerCells and WorkerClient are implemented components, not episode/terminality owners. Retain
E255 pins; do not call them unimplemented or equate their coarse IO lock with execution admission.
SLICE1 STEP1 composition, STEP2 backend, STEP3 real factory/caller/mount cutover and STEP4 full-path
host acceptance remain unchecked. Dependency-ready next: CT102/103 PROJECT working-view ownership.
Allowed code workspace.py + NEW tests/test_execution_views.py; supporting existing spec/increment/
ledger/register/review/HANDOFF/index + new E256 evidence. No new production module or service.
Implement create_view for the concrete WRITE/PROJECT construction path; do not expose dispatcher
handlers or pretend provisioning/candidate/verification views or execution permits exist. Trusted
formal policy/actual PlanRef and explicit approved profile remain private required inputs. Owner
proof authorizes creation, distinct view proof authorizes IO. Copy the validated current revision
using existing bounded no-follow _Capture; only new copied files/directories get approved profile
UID/GID and logical0777 modes (scratch/new source root0755). Canonical bytes/index/modes unchanged.
Use private stage then fsync/no-clobber rename/exact view.json reread before acknowledgement; no
secret-bearing metadata. Retain source/view FDs and exact namespace/principal/epoch/ref/context;
read/write reuse E245 on the SAME materialized tree. Independent pins still use immutable revision.
Recheck actual source/view/registration/plan identities under original-deadline IO lock. This is
file-handler ownership, not command admission. Installation/post-write durability ambiguity fences
owner; no rollback of installed data, cell terminality claim, view GC or unused-writer release.
Binary DoD: native exact dirty/binary/link/mode/UID/tree/index observations; cross-proof denials,
read-your-writes and simulated external private-tree edit visibility; old reader unchanged; stale
SHA/protected/plan/root substitution/restart/fsync/deadline/cleanup negatives. C0/C3 only. Full owning
bank baseline/assertion-only producer kills/restoration plus statics/broader required. Full tool/PTY,
backend/factory/kernel C1/C2 and final-SLICE6 live evidence stay open. No new policy/routing mode.

### E256 implementation checkpoint

E256 source-verified remaining SLICE1 before editing: actual CellBackend/admit and factory/main
are absent, not hidden behind completed component proof. Retain E255 readers; implement next actual
CT102/103 dependency inside SAME WorkspaceAuthority: create_view for WRITE/PROJECT, bounded dirty
input materialization, durable secret-free view retention and distinct principal/namespace/exact-ref
view proof. Existing copier and RootedViewIO reused, no new service/module/dependency or clean Git
checkout. Current retained input verified; canonical/root conflict denies. Newly copied source has
logical0777 modes and explicit approved profile UID/GID; scratch0755, no protected Git/env/control
copy. Native C0 uses actual service UID/GID to reach real operations, NOT deployed different-UID
ownership or mount evidence. Install uses private stage/fsync/no-clobber/exact reread before grant.
write_file/_write_rooted and read_file use SAME working tree; independent READ pins keep old bytes.
Actual PlanRef is bound/rechecked; closed/stale/forged/substituted views deny before IO. Post-write
identity/deadline/context-close/fsync ambiguity fences owner and retains effects, no clean success.
File handlers hold original-deadline lock through IO; this is NOT command admission/drain.
Source src/fa/execution/workspace.py:create_view:1259, _materialize_input:1366,
_install_project:1409, _project_view:1431, _project_io:1484,
write_file:1538, _write_rooted:1556.
46 new C0/C3 native cases;192focusedPASS4.71s. ALL old test files unchanged. Native stage-context
exit fault after install reproduced transient FD leak24!=23 before repair. ExitStack now owns
transient descriptors across that boundary and transfers only after view registration; native
negative proof/cleanup producer retained. No source acceptance before repair. Directory-swap fixture
preserves exact valid metadata AND original source identity to avoid masked deletion. Rooted-write
counterfactual returns closed typed hash/size data; byte/existence oracles run BEFORE consumers.
Final whole18-module925PASS49.62s → nineteen whole925-bank assertion-only kills
30/34/4/1/1/2/3/1/1/1/1/1/2/14/1/1/1/1/1 → restored925PASS46.28s. Clean collection/setup/teardown; no warning/skip/
runtime/infra credit. All602 frozen source/input hashes restored. Ruff/format31PASS, Mypy31/184PASS;
configured Pyrefly0errors with existing141suppressed/50warnings. Broader31-module1445PASS60.60s.
Evidence `notes/evidence/i03-e256/project-views.json.gz`, 2153879bytes SHA256df5a5f4697dc31422f52bff943e420ebfc5a29307b73900f20498160277d7518; exact source/scripts/
ordered outcomes/pre-fix diagnostics and pre-edit SLICE1 inventory retained. Prior E255 unchanged.
NEXT actual per-workspace execution admission/close/drain with approved profile/path triple, then
CellBackend episode/per-command/cancel/restart/independent terminality and actual factory/caller/
mount cutover. Candidate/verification/provisioning view owners, seal/publication remain unimplemented.
No generic purpose switch, dispatcher activation, temporary permit, GC or release/terminality claim.
All35STEPS/four final duties remain open; SLICE1 NOT shipped. All17surfaces/eight joins live PLANNED/
UNEXECUTED at final SLICE6; no early host prerequisite or new policy/routing mode.

### E257 — source assessment and explicit construction order (before code)

At b862632 no complete I03 slice/product execution cutover is shipped. E232–256 are local
component implementations, not 1–2 completed whole contracts per checkpoint. SLICE1 presentation
hid dependencies: authority is SLICE2; factory requires SLICE3; activation joins SLICE4. Do not
report repetitive pending steps as if component checkpoints shipped SLICE1. Actual ordering
(plan-review corrected 2026-10-18; supersedes the earlier compressed tail):
1. Admission/irreversible close/drain + trusted profile/source/scratch/cache (E257 shipped).
2. CellBackend episodes, per-command begin/one-send/cancel/restart/independent terminality
   (E258 shipped).
3. SLICE2 STEP2: the four non-PROJECT view purposes (CANDIDATE/VERIFICATION/MUTATION/
   PROVISIONING) and execution-admitted read/write/edit on retained descriptors.
4. SLICE2 STEP3: managed provisioner injection into SessionManager + provisioning RunContext
   reservation + explicit-registered-reference session ownership (CT103a). Host Git
   provisioning is removed at injection; the publication-dependent provisioning leg
   completes with item 5.
5. SLICE2 STEP4–5 + SLICE3: tool builders + terminal seal/fenced publication/forward
   recovery (publication completes STEP3's provisioning leg and STEP4's seal/import alias
   tests).
6. SLICE4: real factory + atomic caller/mount/registry activation cutover; no
   permissive/failing stub. The provisioner is NOT reimplemented here (route-only).
7. Local full-path C1/C2 and declared producer proofs; final live acceptance at SLICE6.
No completion checkbox is changed by this clarification. All six slices/four final duties open.

Allowed code workspace.py + NEW tests/test_execution_admission.py; existing spec/increment/ledger/
register/review/HANDOFF/index + E257 evidence. Reuse one authority/journal/profile/copier, no new
production module/service/schema/history. Approved dependency-cache path is private operator DI,
never a wire/model path; absent config blocks execution admission, not file IO. READ execution
gets its own bounded materialized readonly source/private scratch, not service0600 R0 mounts.
Admission validates exact actual proof/profile/PlanRef/identities and original EXECUTING uncancelled
journal binding before granting bounded dispatch work. Register work before effects; recheck at
actual create/start/send boundary through scoped effect guard. Scope ends after dispatch, NOT the
command reply/exit wait; stop must be able to signal a running command. File handlers use SAME
view gate. Close wins => no late effect; admitted effect wins => close/drain waits for that bounded
effect/handler. Gate active counts/conditions use existing authority lock for short transitions,
never hold journal lock waiting on drain. Shared mutex serialization is NOT parallel scheduling.
Persist STOPPING before acknowledging close; repeat close does not reopen. Drain waits with original
deadline, never releases writer, deletes source, asserts terminality or interprets expiry as death.
Persist actual operation retention before execution permission. A reader with execution references
cannot be released as an unused file-only pin. Unknown durability fences owner. Shutdown retains
FD owners until scoped work retires. New cache/projection identities must be rechecked before use.
Binary C0/C3 DoD: native bytes/path triple; exact proof/profile/plan/journal/cancel negatives;
queued close => zero effects; admitted effect => close waits; drain consumes deadline; other view
unaffected; file IO closed by same gate; root shutdown does not close live FDs; faults retain refs/
writer quarantine. Whole owning bank assertion-only producer mutations and exact restoration;
actual backend/tool/PTY C1 and final-SLICE6 host proof remain unimplemented/unexecuted.

### E257 checkpoint — SLICE1/2 admission foundation (no slice completion)

Actual authority-owned dispatch admission, trusted source/scratch/cache inputs, irreversible
close/drain and a read-only journal send guard now exist inside the ONE WorkspaceAuthority. This
advances CT99/CT100/CT101-103 preparation; it does not complete any SLICE step or contract.
CT100 ManagedBashExecutor still lacks a CellBackend, so no command permit reaches a cell.
All 35 STEP checkboxes, 17 FUNCTIONAL contracts and four final duties remain unchecked.

### E258 — CellBackend episode owner, one-send discipline, cancel and restart (before code)

E257 proved the authority side (admit/close/drain/trusted inputs). The remaining SLICE1
STEP2 owner is the live cell lifecycle itself. Source-verified: there is NO backend module,
NO episode map, NO one-send command owner and NO restart reconciliation. docker.py creates,
inspects, attaches and force-stops; worker_client.py exchanges private frames; journal.py
records per-operation claims. Nothing owns "one live cell per view with exactly one RUN
send, cancelled before send, and no second cell after restart".

Allowed production files: NEW src/fa/execution/backend.py; src/fa/execution/worker_client.py
(split write from reply wait, existing semantics preserved); src/fa/execution/journal.py
(read-only unfinished-record listing for reconciliation); src/fa/execution/docker.py
(read-only journal accessor); src/fa/execution/workspace.py (read-only approved-profile
accessor). NEW tests/test_execution_backend.py. Existing plan/increment/ledger/register/
review/HANDOFF/index and E258 evidence. No new service, schema, history, receipt type or
routing mode; the ONE journal and the ONE authority stay.

Allowed test edits beyond the new module: tests/test_execution_attach.py and
tests/test_execution_docker.py gain assertion-only oracles for their own success paths
(an expected transport or daemon refusal becomes a failed ASSERTION about the expected
outcome, never a leaked domain-error type). E258's producer mutations reach the worker
transport and the owned stop, so those two modules must fail BY ASSERTION for the
whole-bank kill to count; their expectations are unchanged, only the failure reporting
is normalized. No existing assertion is deleted or weakened. The session configuration
(pyproject.toml) may additionally filter ONE exact CPython 3.13 platform notice by its own
message, as recorded in the amendments below.

Mechanism:
- CellBackend owns a private live episode map keyed by authenticated principal + NamespaceRef
  + exact ViewRef + approved profile id. An episode holds the ORIGINAL creation request, the
  original container id and the SOLE attach/WorkerClient. Worker PTY session ids stay
  subordinate to the episode, so a different namespace/view can never reuse a shell named
  "main".
- execute() consumes the real WorkspaceAuthority admission. A fresh episode performs the
  existing create_once -> durable CID -> start_once path and attaches once. A later command in
  the SAME episode binds the original container id to its own journal record and reuses the
  sole attach; it never creates or starts a second cell and never rebinds the original labels.
- The single RUN frame write happens inside the journal send guard so a persisted cancel
  linearizes against the WRITE, while the reply wait runs OUTSIDE that lock. A lost or late
  reply is EXECUTION_UNKNOWN, never a resend and never a new operation id.
- cancel() persists cancel intent for the exact command operation id BEFORE any stop, then
  stops the OWNED cell through the original creation binding. Cancel intent is not a
  terminal receipt and asserts no process death.
- reconcile() inspects owned cells for uncertain records by id/name/labels and stops a
  surviving cell; it never creates or starts a second cell and never re-runs a command.
- The backend returns a CommandOutcome, NOT a receipt: worker text is untrusted, exit code is
  the command's, and terminal_barrier is always False here because no independent container
  or cgroup fact is established in this increment.
- One cell per episode identity: concurrent commands on the same view share a single
  per-identity creation lock, so a second cell is never created for a live episode and a
  concurrent create is never a duplicate shell.
- The admission scope stays open for the whole command because the work is still in
  flight, while the journal send guard covers ONLY the RUN frame write. The reply wait
  is outside that lock, so a cancel can be persisted while a command runs.
- A daemon answer that violates the owned-cell contract (a foreign container name or
  foreign labels) is PATH_DENIED, never a successful stop and never a synthetic
  completion.

Failure behaviour: unknown/duplicate operation id, forged principal/namespace/view, wrong
profile, expired budget, closed view, cancelled-before-send and lost reply all fail closed
with existing SupervisorError codes; no replay, no second cell, no synthetic completion.

Binary DoD: native local worker over the real attach transport proves one create/start/attach
per episode, shell state preserved across two commands in one cell with two durable records
binding the SAME original container id, the original labels still naming the original
operation, a foreign namespace/view getting its own cell, a duplicate operation id denied
without a second send, cancel-before-send producing NO RUN frame, cancel during a running
command persisting intent while the command is still running (the journal lock is not held
across the reply wait), a lost reply yielding EXECUTION_UNKNOWN with exactly one RUN frame,
and restart reconciliation stopping a surviving owned cell without creating a second one.
Whole owning-bank assertion-only producer kills and exact restoration; statics and broader
regression required. Negative proof must not rely on runtime/name errors.

C0/C3 only. Actual CellBackend -> supervisor -> tool/PTY composition, receipts, independent
terminality, seal/publication, factory/main and caller/mount cutover stay unimplemented.

#### E258 amendment 1 — the scope retirement path and its killable equivalent

execute() now retires the admission scope ONLY through the `with scope:` block; the
redundant `finally: scope.close()` was removed, so there is exactly one retirement path
and the scope's own context manager is the single owner of the admitted work.

A producer mutation that leaves the scope open cannot be counted as a kill: the
authority's shutdown waits for the gate's admitted work with NO deadline, so a leaked
scope hangs the fixture teardown and a timeout is not a kill. The equivalent contract is
therefore proven by a killable producer instead: the native case
test_drain_waits_for_a_running_command_and_returns_when_it_retires requires the drain to
STAY BLOCKED while a command is still running and to return only once that command has
retired, and its producer mutation (WorkspaceAuthority._wait_drained: `while gate.active:`
-> `while False:`) is killed by that assertion. The native case
test_completed_command_leaves_no_admitted_work_behind still proves that a finished
command leaves no admitted work behind, through the unchanged drain path.

E258 amendment 2 (test-surface normalisation, no expectation changed): a command that runs
off the main thread RECORDS its own outcome and the oracle checks that recorded outcome
(EXECUTION_UNKNOWN or BACKEND_UNAVAILABLE for a stopped owned cell). An unhandled thread
exception is a pytest warning, and a warning is never kill credit, so the recorded
outcome replaces the raised one. The session filters ONE exact CPython 3.13 platform
notice by message (the forkpty-in-a-multi-threaded-process DeprecationWarning) in
pyproject.toml: in production the cell worker forks only on the cell's own main thread,
while the native fixtures run that worker inside the pytest process. No assertion is
added, removed or weakened, and no other warning class is filtered.

E258 amendment 3 (the narrow warning filter is a SESSION filter): the forkpty notice can
surface in any bank module, because a producer that wedges the transport leaves a live
thread while a later native case forks its PTY. The single session level filter in
pyproject.toml therefore replaces the per-module filters, so the rule is uniform and the
proof's no-warning claim stays absolute. The notice stays VISIBLE in the pytest output of
any run that does not use the project configuration, and the production cell worker keeps
its own main-thread-only fork rule.

E258 amendment 4 (kill credit): a kill is a call-phase ASSERTION. A setup failure means the
case never ran and is never kill credit. A teardown failure under a producer that
deliberately wedges the transport is a RECORDED signal and never kill credit: the baseline
and the restored source must tear down completely clean, and every producer kill must come
from at least one call-phase assertion with no other failure class in the call phase. The
transport-wedging producer (the worker that never writes its frame) also trips the native
fixture's own teardown assertion; that is recorded in the evidence, not credited.

E258 amendment 5 (the declared docker.py accessor was not needed): the declaration allowed a
read-only journal accessor in src/fa/execution/docker.py. The existing
DockerEngine.inspect_owned and DockerCells.force_stop_owned paths already carry the
owned-cell proof (the exact container name, the operation and view labels and the recorded
container id), so docker.py is UNCHANGED by E258. The E258 producers reach that existing
path to prove the owned stop, and the authority keeps the one trusted path triple.

### E258 — CellBackend episode owner: local component proof (result)

E258 implements the live cell episode owner in a NEW src/fa/execution/backend.py. A
private episode map is keyed by the authenticated principal, the NamespaceRef, the EXACT
ViewRef and the approved profile id, so a shell name alone is never an identity. One
episode performs create -> durable container id -> start -> sole attach exactly once; a
later command in the same episode binds the ORIGINAL container id to its OWN journal
record and reuses the sole attach, so a second cell is never created for a live episode.
Exactly ONE RUN frame write happens per command, inside the journal send guard, while
the reply wait stays OUTSIDE that lock, so a cancel can be persisted while a command is
still running. cancel() persists the exact-command intent BEFORE the owned stop, and a
daemon answer that violates the owned-cell contract (a foreign container name or foreign
labels) is PATH_DENIED, never a successful stop. reconcile() stops a surviving owned
cell of an uncertain record and never creates, starts or re-runs anything. The backend
returns a CommandOutcome, never a receipt: worker text is untrusted, the exit code is
the command's own, and terminal_barrier is always False here because no independent
container or cgroup fact is established in this increment. 19 new native C0/C3 cases;
focused 7-module owning bank 369 PASS 26.05s. Whole 20-module owning bank 985 PASS 68.20s -> twenty-four whole
985-bank assertion-only kills 1/1/2/3/1/3/2/1/1/1/5/2/1/2/16/26/6/1/40/4/7/6/15/15 ->
restored 985 PASS 67.71s; clean collection and setup, no warning/skip/runtime/infra
credit, every kill by a call-phase ASSERTION. All 605 frozen source/input hashes
restored exactly. Ruff/format/Mypy clean; configured Pyrefly 0 errors with the existing
141 suppressed/50 warnings. Broader 31-module 1505 PASS. Evidence
notes/evidence/i03-e258/episodes.json.gz, 2666870 bytes SHA256
299c301625545cd8f6fd69bb9a7b5bb74859f43c4e1f74f5697e040c54a30e90. NOT shipped: other
view purposes, seal/publication/forward recovery, the real build_supervisor/main with
closed handlers, the atomic SessionManager/tool/caller/mount cutover, receipts and
independent terminality. SLICE1 NOT shipped; all 35 STEP checkboxes, 17 FUNCTIONAL
contracts and four final duties remain open; all 17 production surfaces and eight joins
stay PLANNED/UNEXECUTED at final SLICE6. No early host prerequisite, no new policy, no
new routing mode.

### E259 — the four non-PROJECT view purposes (before code)

IDEA: complete SLICE2 STEP2's view-purpose owners: every declared ViewPurpose becomes a
real authority-constructed view with its exact admission combination, reusing the retained
E256 materialization/install and E257 admitted IO — no new service, no purpose switch, no
generic permissive factory.

CONTRACT/GAP IDS: SLICE2 STEP2 (view purposes + admitted IO per §§4–4.2), CT102's
create_view materialization contract (extended to all purposes), CT103's rooted-IO
obligations applied per purpose, §2 create_view table row (purpose/candidate_scope
combinations), §3.1 (VERIFICATION/MUTATION/CANDIDATE need nonnull plan), §5 (CANDIDATE
buffer-in-staging), §6 (MUTATION derivative; VERIFICATION disposable views). Live ledger:
I03-LIVE-17 (workspace.py) witnesses extended; I03-LIVE-S05 join note extended.

ALLOWED FILES: src/fa/execution/workspace.py (purpose-parameterized create_view, purpose
policy in rooted IO, candidate buffer methods); tests/test_execution_purposes.py (NEW);
plus the mechanical create_view call-shape migration of the shared `create` helper in
tests/test_execution_views.py (adds purpose/access/candidate_scope kwargs; NO assertion
changes; the backend/admission fixtures inherit it via import);
existing plan/increment/ledger/register/review/HANDOFF/index + E259 evidence. No protocol,
types, journal, worker, docker, supervisor or session change; wire validation is already
correct and is NOT reimplemented (the authority REVALIDATES independently).

CURRENT BEHAVIOR: create_view (workspace.py:1389) hard-codes Access.WRITE +
ViewPurpose.PROJECT (:1430–1431), always candidate_scope=None; pin_reader hard-codes
READ/PROJECT (:1128–1129); the wire payload's purpose/access/candidate_scope never reach
the authority. The wire layer ALREADY validates the matrix (protocol.py:314–320) and
_VIEW_RECORD already supports nullable candidate_scope (workspace.py:127).

TARGET BEHAVIOR: create_view(peer, namespace, *, workspace_id, capability, purpose,
access, candidate_scope, plan_ref, formal_evidence, deadline) constructs exactly the pinned
matrix and denies every other combination with INPUT_POLICY BEFORE any staging copy:
- PROJECT (retained): WRITE or READ is NOT re-issued here; create_view stays WRITE/PROJECT
  when purpose=PROJECT with candidate_scope=None; pin_reader stays the READ/PROJECT owner.
- VERIFICATION: access=READ, plan_ref REQUIRED (nonnull), materialized immutable input +
  private scratch, formal evidence bound and rechecked; no write path exists on it.
- MUTATION: access=WRITE, plan_ref REQUIRED; rooted writes confined to the approved
  mutation roots src/ and scripts/ (slice_verification._MUTATION_ROOTS); writes to tests/,
  .fa, .env, .git, the plan path, or any path outside those roots deny PATH_DENIED. The
  "one permitted target" discipline is TWO-LAYER (Q77 construction, no new wire field):
  the authority confines writes to the roots; the controller's mutation edit remains a
  single-file expected_sha write (I02 overlay discipline).
- CANDIDATE: plan_ref REQUIRED and candidate_scope REQUIRED with candidate_scope.plan_ref
  == plan_ref; internal binding = source READ materialization + ONE supervisor-owned
  staging buffer addressed by the exact candidate_path; buffer writes/reads go through new
  authority methods (write_candidate/read_candidate) bound to the view's scope; bytes NEVER
  land in canonical .fa/admission or any cell/control mount (§5). Generic write_file denies
  the candidate_path; that tool-level cutover stays STEP4.
- PROVISIONING: access=WRITE, plan_ref NOT required (may be null); materializes the
  registered current bytes like PROJECT; it is the view in which bootstrap/readiness
  commands run (the provisioning consumer lands in STEP3; this increment owns admission +
  construction only).

MECHANISM: one parameterized construction path reusing _materialize_input/_install_project
under a per-purpose policy object; the ViewRef carries the real purpose/access; the view
record carries candidate_scope for CANDIDATE and the plan_ref as today; execution_trusted
and admit keep routing by access with a purpose recheck added at the effect boundary; the
candidate buffer is a service-owned staged file inside the view's protected directory tree,
written only through the scope-checked authority method.

PRODUCTION BEST PRACTICE: closed-enum dispatch with an exhaustive deny (no default-allow
fallthrough); authority-side revalidation of every wire claim (never trust the codec
alone); reuse the one materialization/install path rather than forking per purpose; keep
the frozen request shape (no new wire fields); make the deny path return the existing
INPUT_POLICY code before any filesystem effect.

FAILURE BEHAVIOR: wrong purpose/access/scope/plan combination -> INPUT_POLICY before any
mkdir/copy; candidate write to a path other than the exact scope path -> PATH_DENIED;
MUTATION write outside src//scripts/ -> PATH_DENIED; VERIFICATION write anywhere ->
PATH_DENIED (no write path); plan_ref substitution after creation -> STALE_REVISION at
effect recheck; staging/install failure -> existing BACKEND_UNAVAILABLE /
DURABILITY_UNKNOWN semantics, never a returned grant; secret/capability never in records.

DoD: native bank proves every allowed combination constructs a real materialized view with
the right record/ref fields, and one denied-combination case per forbidden
purpose/access/scope/plan tuple denies INPUT_POLICY with zero filesystem effect (no
pending staging dir left behind); candidate buffer writes land ONLY in the supervisor
staging buffer and never at the canonical path; MUTATION writes outside the roots deny
PATH_DENIED and inside succeed with expected_sha conflict semantics; VERIFICATION exposes
no write path and binds/rechecks its plan; PROVISIONING accepts null plan and refuses
nothing it should allow. NEGATIVE PROOF: no runtime/name-error kill credit; denied cases
assert the typed error + the absence of effects; producer mutations rerun the whole owning
bank, assertion-only kills, exact restoration.

TESTS-WRITING CLASS: C0/C3 native cases over the real authority + real descriptor IO
(no mocks of the filesystem); kill-check on the PRODUCER call sites (the per-purpose
policy call inside create_view's construction and the write path's purpose recheck);
existence pre-check first (grep the call sites); path inventory = all five purposes ×
access × scope × plan on/off; C4 mutation handoff after C1-equivalent native bank.

PRODUCER KILL-CHECK TARGETS (whole-bank mutations): remove the matrix deny in create_view;
remove VERIFICATION's plan-required check; remove MUTATION's root confinement; remove
CANDIDATE's scope-path equality check; allow PROVISIONING plan_ref to be required wrongly;
make candidate writes fall through to the source tree; drop the authority-side revalidation
(the wire-only trust fallacy); drop the purpose recheck at the effect boundary.

E2E LEDGER ENTRIES: extend I03-LIVE-17's live fixture with the purpose matrix witnesses
(five purposes, denied combinations, candidate staging isolation, mutation root
confinement); extend I03-LIVE-S05 with "purpose-correct views" wording; add the E259
checkpoint section at close; surface count unchanged (workspace.py already tracked).

C0/C3 only. Candidate tool cutover (STEP4), the provisioning consumer (STEP3), seal/export
of mutation/candidate outputs (SLICE3) and live proof stay open.

### E259 — the four non-PROJECT view purposes: local component proof (result)

E259 completes SLICE2 STEP2's view-purpose owners in src/fa/execution/workspace.py. create_view
now takes the closed matrix (purpose, access, candidate_scope, plan_ref) and constructs exactly:
VERIFICATION (READ, plan required) and CANDIDATE (READ, plan + exact scope) as immutable reader
views reusing the one reader-registration path; MUTATION (WRITE, plan required) and PROVISIONING
(WRITE, plan optional) as project views reusing the E256 materialization. Every other
combination denies INPUT_POLICY before any filesystem effect, revalidated at the authority
independent of the codec. The purpose write gate at the effect boundary confines MUTATION
writes to the approved src//scripts roots and gives VERIFICATION/CANDIDATE no generic write
path; the scoped candidate buffer is ONE supervisor-owned staged file written only through
write_candidate/read_candidate with exact scope-path equality and expected-absence/exact-SHA
semantics, never canonical .fa/admission. pin_reader stays the READ/PROJECT owner unchanged.
10 new native C0/C3 cases; focused 4-module bank 202 PASS 5.1s. Whole 21-module owning bank
995 PASS 65.6s -> eleven whole-bank assertion-only kills
1/1/2/7/1/2/3/1/2/1/1 -> restored 995 PASS 64.9s; clean collection/setup/teardown,
no warning/skip/runtime/infra credit, every kill a call-phase builtins.AssertionError. Source
restored byte-exact. Ruff/format 35 files clean; Mypy 35+185 files clean; Pyrefly 0 errors with
the existing 141 suppressed/50 warnings; broader 1515 PASS. Evidence
notes/evidence/i03-e259/purposes.json.gz, 1343665 bytes SHA256 e689ea3b92258128c1ab20a2d4e7ed312e63bf7b81bdce53f4a52c4081e1b9bd.
Honest notes: one candidate producer (a second path-traversal parser in the matrix) was found
MASKED by the record-layer path rules (protocol._byte_limits) and DELETED as redundant rather
than counted — the single enforcement point stays the record check. A first runner attempt
aborted on a frozen-hash comparison poisoned by the git tracking pointer moving mid-run (an
environmental artifact); restoration was then verified byte-exact against start-of-run bytes.
NOT shipped: the candidate tool cutover (STEP4), the provisioning consumer (STEP3), seal/export
of mutation/candidate outputs (SLICE3), receipts/independent terminality and live proof. SLICE1
NOT shipped; all 35 STEP checkboxes, 17 FUNCTIONAL contracts and four final duties remain open;
all live verdicts stay PLANNED/UNEXECUTED at final SLICE6. No new policy or routing mode.

## E260 — plan and E2E audit after lifecycle review (2026-10-22)

**Audit result:** the 2026-10-21 review's R1–R5 behaviors have local component implementations/tests,
but do not establish service/host proof. E261 separately records a source-only one-shot CANCEL path
not exercised by the sequential lifecycle tests. E258's planned "one episode" wording did not
explicitly separate persistent interactive reuse from per-operation noninteractive one-shot cells,
and its live witnesses did not name the cross-view cancel, create/start/attach gate race, DONE-owned-cell
restart or absolute lock-deadline cases individually.
Spec §2.2 and the SLICE1/SLICE2 exits now state those contracts; the single existing live register is
extended below. No new protocol, authority, lock service, production module or acceptance status is
introduced.

| Finding / open gap | Normative plan owner and direct remedy step | Future live witness (not run; remains PLANNED/UNEXECUTED) |
|---|---|---|
| R1 — noninteractive EXEC lifecycle | Spec §§2.1–2.2, CT100, SLICE1 STEP2: only interactive profiles reuse a view episode; each distinct noninteractive operation uses null session + fresh one-shot cell/attach + one RUN; same-op replay never launches again. CANCEL during a live one-shot must resolve/stop that exact operation CID without relying on the interactive map. | I03-LIVE-11/18 and S03/S04: two sequential noninteractive ops use distinct CIDs, verify null-session result/exit/timeout/no replay, and issue a concurrent same-view CANCEL against a running one-shot; keep interactive two-command state reuse separate. |
| R2 — `admit()` is not a side-effect guard | Spec §2.2, SLICE2 STEP1/STEP5: `WorkAdmission.effect()` wraps actual Docker create/start/attach; `send()` guards the RUN frame. Paired schedule proves close-wins→zero effects and effect-wins→close/drain waits. | I03-LIVE-18 and S02/S04: actual installed service/daemon barrier schedule; assert zero create/start/attach/RUN when close wins, no late RUN after attach, and bounded drain when the effect wins. |
| R3 — cross-view CANCEL | Spec §2.2, SLICE1 STEP2: compare namespace and exact `ViewRef` with the EXEC journal record in the same transaction that persists cancel; same-namespace operation from another view returns `UNAUTHORIZED` before stop. | I03-LIVE-18 and S04: two real views in one namespace; wrong-view operation ID leaves both journal records and daemon request log unchanged. |
| R4 — DONE record can still own a cell | Spec §2.2, SLICE1 STEP2: enumerate every EXEC record with a durable CID (separate from `unfinished()`), including DONE; stop/inspect only original CID/name/labels and do not rewrite the completed result or create/start/attach/RUN. CT104 cgroup barrier remains independent. | I03-LIVE-07/18 and S03/S04: mark interactive creator DONE while its cell remains live; restart supervisor/backend; inspect/stop that CID only, preserve DONE result and withhold terminality until the independent barrier. |
| R5 — request deadline across locks and effects | Spec §2.2, SLICE1 STEP2: pass the original monotonic deadline through authority/registry/episode locks, every request journal transaction, Docker/attach/RUN; pre-body/pre-effect expiry is `BACKEND_UNAVAILABLE`, possible post-write/effect uncertainty remains uncertain; no reset or late follow-up. | I03-LIVE-06/18 and S02/S03: force journal-flock and episode-lock contention plus late Docker/attach; verify expiry/no effect and truthful uncertainty after a possible write. |
| Q66 — parent context to actual planner input | Existing CT109, SLICE5 STEP4/STEP5 and SLICE6 DoD already directly require an internal bounded snapshot only in the initial planner request, credential redaction and distilled retry separation; no public `context` field. | S08: parent-only sentinel present in first real planner request and absent from retries; credential sentinel absent; direct+nested workflow runs with actual provider requests. |
| Service/factory/caller/mount cutover | Existing CT99, SLICE1 STEP3 and SLICE4 STEP2: compose real `build_supervisor/main` with the one authority/backend/journal; remove controller source-prepending/import shadow and direct host fallbacks; activate caller/mount changes atomically; no unrestricted Docker socket in model-facing controller. | I03-LIVE-01/06/07 and S01/S02/S07: actual installed launch, private UDS supervisor, startup recovery, real tool/PTY/provisioner/verifier routes and denied-backend/no-host-effect oracles. |
| Sealing, publication, recovery and descendant terminality | Existing CT104–CT107, SLICE3 STEP1–STEP5: close admission, drain handlers, stop cells, prove cgroup empty, then seal immutable bytes; recover forward or quarantine. | S04/S06 and `tests/integration/test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`: fork/double-fork/setsid/background writers, held file handler, every irreversible crash/fsync boundary; no seal/publish while writable. |
| Ubuntu/Docker/image and release-environment proof | Existing CT100a, SLICE1 STEP4 and SLICE6 STEP7/9/10: actual approved host/image/profile/mount/daemon/cgroup evidence, complete non-skipped execution inventory and E223 review; specific wheel/zlib, ShellCheck, Go/Gitleaks hook prerequisites are now explicit in STEP10 above. | I03-LIVE-02/05/13/16, all cross-module joins and SLICE6: actual installed wheel/image, approved daemon and host facts; full `just test`/`just check` + readiness acceptance, no setup errors or required-case skips; retain the documented Q19 xfail with its separate disposition; no bypass. |
| Broad independent review and release signoff | CT89, SLICE6 STEP7/10 and the binary DoD: named independent reviewer, pre-fixture manual checklist repeated after material changes, source/image/config/run-bound evidence, all four E223 duties, and explicit operator signoff after required E2E; no harness-generated approval | E223 final acceptance package; S01–S08 artifacts feed review but never self-approve |

All 35 STEP boxes, all FUNCTIONAL contracts and the four transferred E223 duties stay open. The
component regressions and local result remain evidence only; every live witness above is future work
after the service/caller composition exists and at final SLICE6. This audit does not run E2E, authorize
production deployment, or change I02's local/pending-E2E status, Q59–Q66 dispositions, E19, Q53(c),
or the append-only ledger policy.

## E261 — one-shot CANCEL ownership seam found in plan audit (2026-10-22)

Source review during E260 found one additional I03 seam that the R1–R5 passing tests do not cover:
`CellBackend.execute()` creates a noninteractive `_Episode` for the duration of the call but does not
put it in the persistent interactive `_episodes` map; `CellBackend.cancel()` currently resolves its
cell only through that map. Thus the local sequential one-shot tests do not demonstrate that CANCEL
can stop an in-flight one-shot operation. This is a source-path gap, not a newly executed regression;
do not claim one-shot cancellation is implemented or validated.

Direct remedy, with no new service or registry: SLICE1 STEP2 must persist exact-view cancellation in
the existing journal, resolve the running EXEC record's durable CID and original labels, then use the
existing owned-cell Docker stop/observation path. Keep the identity bound to operation + namespace +
exact `ViewRef` + approved profile. A missing/mismatched record denies before Docker effects; no
replacement create/start/RUN, no re-execution and no terminal claim from the stop ACK. Preserve the
interactive episode path. Add a native regression in `tests/test_execution_backend.py` for a running
one-shot command cancelled from its own view and a same-namespace wrong-view cancellation with zero
journal/daemon mutation. The host seam is I03-LIVE-18/S04 and remains PLANNED/UNEXECUTED.

**Status:** open until the owner path and regression are implemented and reviewed in I03; final real
daemon/cgroup proof remains at SLICE6. This audit does not edit product source or claim release
readiness.

### E262 — one-shot CANCEL ownership: declaration before code

**Idea.** Close the seam E261 recorded: a CANCEL issued while a *noninteractive one-shot* EXEC is
running must stop that operation's own journal-bound cell. Today it cannot, because the only
cancel path resolves the cell through the interactive episode map.

**Contract/gap IDs.** I03 SLICE1 STEP2 (exit clause "live one-shot cancel by exact journal-bound
CID"), CT100, CT103a lineage; spec §2.2 (cancel must match namespace + exact `ViewRef` in the same
journal transaction, applies to in-flight one-shot, never create a replacement) and the §E262
implementation note; E261 GAP record in the ledger and the I03-LIVE-18 / S04 witness.

**Allowed files.** `src/fa/execution/docker.py` (one new method on the existing `DockerCells`),
`src/fa/execution/backend.py` (`CellBackend.cancel` branch), `src/fa/execution/journal.py`
(`request_cancel` return value only — no new validation, no schema change),
`tests/test_execution_backend.py`
(new C0/C3 cases + docstring path inventory), plan docs/ledger/E2E register. No new module, no
second registry, no protocol/schema change, no supervisor or service composition, no admission
change for cancel.

**Current behaviour (source-verified).** `CellBackend.cancel` builds an `_EpisodeKey` and reads
`self._episodes`; only the interactive branch of `_live_episode` inserts there (backend.py:281), so
for a noninteractive profile the lookup returns `None` and cancel raises `EXECUTION_UNKNOWN` before
persisting anything — even while the one-shot cell is running. `DockerCells` already owns two
owned-stop entry points (`force_stop_created`, and the engine-level `force_stop_owned`) and
`OperationJournal.request_cancel` already enforces the exact-`ViewRef` match.

**Target behaviour.** Noninteractive cancel resolves the EXEC record by `operation_id` under the
original namespace, verifies `op == exec` and exact `ViewRef`, persists cancel intent, and stops the
record's own durable CID through the existing `force_stop_owned` path (which re-validates
name/labels/image/CID before one fixed SIGKILL and independently re-inspects the same CID). If the
record has no CID yet, the intent alone is durable and the operation is refused a later
create/start; the caller receives a distinct `not_created` observation. Interactive cancel is
unchanged. Return values remain observations, never receipts or terminality.

**Mechanism.** `OperationJournal.request_cancel` returns the record it durably wrote inside its own
transaction (identity, exact view, intent and read of the CID are then one decision point — an extra
`lookup` before it would both duplicate the checks and open a create-then-cancel race). New
`DockerCells.force_stop_operation(*, operation_id, namespace, view, profile, deadline) ->
ContainerObservation | None`: type checks, `journal.request_cancel(...)` (sole authority for
unknown/other-op/foreign-view refusal and for durable intent), then `engine.force_stop_owned(...)`
with `record["container_id"]`, or `None` when it is absent. `CellBackend.cancel` branches once on
`profile.interactive`: the existing episode path, or `force_stop_operation` mapped through the same
error surface (`JournalError → SupervisorError(code)`, `ExecutionContractError → PATH_DENIED`,
`DockerUnavailableError → PATH_DENIED` when no status else `BACKEND_UNAVAILABLE`, `TimeoutError →
BACKEND_UNAVAILABLE`).

**Production best practice.** Reuse the existing journal as the single source of durable truth
instead of adding in-memory state; make identity checks precede effects; keep one stop
implementation (`force_stop_owned`) for every path; express "nothing to stop yet" as data, not as an
exception or a false success; keep the deadline and the error surface uniform across paths.

**Failure behaviour.** Unknown/foreign/other-op id → `EXECUTION_UNKNOWN`; foreign view → 
`UNAUTHORIZED` with no journal write and no daemon request; journal or Docker unavailability →
`BACKEND_UNAVAILABLE`; malformed/foreign observation → `PATH_DENIED`; expired deadline →
`BACKEND_UNAVAILABLE` with no late effect. A stopped cell makes the concurrent command end in
`EXECUTION_UNKNOWN`/`BACKEND_UNAVAILABLE`, never success.

**DoD.** Same-view cancel of a running one-shot: intent durable, one SIGKILL to the exact CID, the
concurrent command ends in a legal closed outcome, exactly one RUN frame, no second create/start/
attach. Cross-view cancel: `UNAUTHORIZED`, `cancel_requested` still false, no daemon request at all.
Unknown operation: `EXECUTION_UNKNOWN`, no daemon request. Cancel before creation: intent durable,
`not_created`, the later execute refuses to create/start and sends zero frames. A fresh
`CellBackend` over the same journal (no episode map) still stops the live one-shot cell.
**Negative proof:** deleting the new branch, the exact-view check, the intent write, or the
CID-based stop each fails a named test.

**Tests-writing class.** C0/C3 (this module's proven level: real authority/journal, literal HTTP
Docker peer, real PTY worker; no container/cgroup/terminality claim). Classes and path inventory are
recorded in the test module docstring.

**Producer kill-check targets (declared, 4 new + 1 reused).** (1) the noninteractive branch in
`CellBackend.cancel`; (2) the exact-`ViewRef` comparison in `journal.request_cancel` — **reused**
pre-existing producer, already killed by journal tests, so not claimed as new evidence; (3) the
durable `request_cancel` intent (mutant: read-only `lookup` instead); (4) the
`record["container_id"]` argument to `force_stop_owned`; (5) the `None`/`not_created` handling for a
record without a CID.

**E2E ledger.** Existing I03-LIVE-18 / S04 witnesses already name the required live case; the
register's open-gap paragraph is updated to "implemented locally, live still PLANNED". Surface
count unchanged (18/8). No STEP checkbox, FUNCTIONAL contract or E223 duty is closed by this
component work.

#### E262 result — implementation, evidence and one design correction

**Shipped.** `journal.request_cancel` now returns the record it wrote (behaviour otherwise identical);
`DockerCells.force_stop_operation` in front of `attach_created`; `CellBackend.cancel` branches once on
`profile.interactive` into `_cancel_operation`. Four new producers, one reused.

**Correction found by mutation testing (recorded, not hidden).** The first implementation looked up the
record, then checked op and view, then called `request_cancel`, then read the CID from the *earlier*
lookup. Mutation exposed both defects: deleting the local checks did not fail anything (they were
duplicates of checks inside `request_cancel` — a masked producer, the E259 pattern), and reading the
CID outside the intent transaction leaves a create-then-cancel window in which a freshly created cell
would be recorded as cancelled but never stopped. Both were fixed by having `request_cancel` return the
record it wrote, so identity, intent and CID belong to one journal transaction. The declared kill (2)
is therefore attributed to the journal, and the `request_cancel` mutation was changed from "delete the
call" to "replace with a read-only lookup", which is the mutation that exists in the final design.

**Red→green.** Before the implementation, the red run was 4 failed / 2 passed with the failure at the
cancel call (`SupervisorError`). After: `pytest tests/test_execution_backend.py -q` → 30 passed in
19.35s; the seven-module execution bank (`backend docker journal dispatch attach client cell_worker`)
→ **462 passed in 36.62s**.

**Static checks (actual output).** `ruff check src tests` → `All checks passed!`; `ruff format --check
src tests` → `498 files already formatted`; `mypy src/fa/execution` → `Success: no issues found in 16
source files`; `pyrefly check src/fa/execution` → `0 errors`.

**Targeted mutation run (assertion-only credit; source SHA256-restored after each mutant and the bank
re-run green).** 5/5 kills:

| Mutant | File | Killed by |
| --- | --- | --- |
| noninteractive branch deleted | `backend.py` | G2, G5, G6 (and G3, since the episode path is taken) |
| exact-`ViewRef` check deleted | `journal.py` | G3 + 2 journal cancel tests (**reused**) |
| `request_cancel` → read-only `lookup` | `docker.py` | G2, G3, G4, G5 |
| `record["container_id"]` → `None` | `docker.py` | G2, G6 |
| `not_created` → `exited` | `backend.py` | G5 |

**Scope unchanged.** No STEP checkbox, FUNCTIONAL contract, or E223 duty is closed. I03-LIVE-18 / S04
remain PLANNED/UNEXECUTED; surface count 18/8.

### E263 — SLICE2 STEP3 (SLICE2 half): managed provisioner injection into SessionManager

**Idea.** `SessionManager` is still the host-Git owner of workspaces: `_new_session` materializes a
directory with `provision_git_workspace`/`copytree`, and the supervisor never learns that the workspace
exists. STEP3 reverses that ownership inside the existing manager: the supervisor becomes the only
creator/registrar of canonical workspace bytes, the manager keeps its manifest/DB/run duties, and the
provisioner receives a real provisioning run identity before it acts. This increment implements the
SLICE2 half only (component injection + contract); the publication-dependent new-root leg is SLICE3's
join and the remaining inventory callers are routed at SLICE4 STEP2 (the same provisioner, never a
second one).

**Contract/gap IDs.** I03 SLICE2 STEP3 (SLICE2 half) exit clauses; CT103a; CT100 lineage; spec §4.1
("Registration and SessionManager cutover") and the §"SessionManager ordering/recovery" note; increment
line 308 (STEP3 declaration) and 297 (CT103a); I03-LIVE rows that consume the provisioning route.

**Allowed files.** New `src/fa/session/provisioning.py` (request/result values + provisioner callable
type; no execution imports, so the session layer stays execution-agnostic), new
`src/fa/execution/provisioning.py` (the adapter that turns `WorkspaceAuthority.register_existing` into
the frozen result), `src/fa/session/manager.py` (injection point, provisioning run reservation,
not-READY enforcement, cleanup ownership, reverse-owner confirmation),
`src/fa/execution/workspace.py` (`register_existing` returns `tree_sha256` as well — no new validation,
no behaviour change), `tests/test_session_lifecycle.py`, new `tests/test_execution_provisioning.py`,
plan/ledger/E2E register. No second provisioner, no new session manager, no manifest schema change, no
CLI/composition change (SLICE4 owns that), no publication code.

**Current behaviour (source-verified).** `SessionManager.__init__` accepts only
`workspace_preparer`; `_new_session` writes a `provisioning` manifest, calls `_provision_workspace`
(host Git clone when `source_workspace` has `.git`, else `copytree`), creates `SessionDatabase`, calls
`workspace_preparer(workspace_path)` and *ignores its `ReadyState`*, then writes `active`.
`_attach_session` likewise ignores a not-READY result. `_check_reverse_workspace_ownership` rejects any
workspace path equal to another session's manifest path. Nothing in the manager knows a run identity
before the CLI's later `begin_run`, so a supervisor-side provisioner would have to invent one.
`WorkspaceAuthority.register_existing` already registers quiescent existing bytes idempotently (returns
the existing ids and re-verifies unchanged bytes when already registered) and returns only
`{workspace_id, revision_id}`.

**Target behaviour.** With a provisioner injected: the manager never clones, copies or chmods canonical
bytes; it creates the manifest (`provisioning`) and session DB, reserves one real provisioning
`RunContext` through the existing `begin_run(session, None)`, passes that namespace plus the session and
workspace root to the provisioner, enforces readiness, and only then writes `active`. A provisioner
result is exactly `{registered, workspace_id, revision_id, tree_sha256}`: `registered=True` means the
supervisor committed and verified those bytes and the manager must never delete them; `registered=False`
means provisioner-created scratch that only the manager may clean up. A new workspace whose bytes do not
exist becomes the typed BLOCKED disposition `provisioning_unavailable` (no host-Git fallback) until
SLICE3 joins publication. A not-READY `ReadyState` is `workspace_not_ready` in both `_new_session` and
`_attach_session`. An explicit reference to another session's registered workspace is permitted
(CT103a: reference, not ownership transfer — the other session keeps its DB/run bindings and manifest),
while an unregistered conflict stays `workspace_already_owned`. Without a provisioner the manager keeps
today's exact behaviour, because SLICE4 STEP2 performs the actual cutover.

**Mechanism.** `fa/session/provisioning.py`: frozen `ProvisionRequest{mode, session_id, run_id,
workspace_path, deadline}` with `ProvisionMode{REUSE, PROVISION}`, frozen
`ProvisionedWorkspace{registered, workspace_id, revision_id, tree_sha256}` whose `__post_init__` rejects
partial results, and `WorkspaceProvisioner = Callable[[ProvisionRequest], ProvisionedWorkspace]`.
`fa/execution/provisioning.py`: `ManagedProvisioner(authority, *, peer, root_id, relative_root)` — REUSE
maps to `register_existing(...)` built from the request's `NamespaceRef`, returns the frozen result with
`registered=True`; PROVISION raises `SessionManagerError("provisioning_unavailable")` before any effect;
`SupervisorError` maps to explicit session codes (`CORRUPT_STATE → workspace_corrupt`,
`UNAUTHORIZED/EXECUTION_UNKNOWN → workspace_denied`, everything else → `workspace_provision_failed`).
Manager: `__init__(workspace_provisioner=...)`; in `_new_session` the reserved run id comes from
`begin_run` on a provisional `SessionContext` under the `provisioning` manifest; the provisioner is
called after DB creation and *before* the readiness gate (so readiness runs against registered bytes,
matching SLICE4 where it executes inside provisioning cells), asking for `PROVISION` when the manager
would have had to create the root and `REUSE` for a named existing directory; its result drives a
three-state cleanup (`None` = never ran,
`False` = scratch, `True` = registered) where only `None`-with-`workspace_created` and `False` are
rmtree-eligible. The reverse-owner scan returns conflicting owners instead of raising when a provisioner
is injected, and the conflict is confirmed after the result is known.

**Production best practice.** Keep one owner per responsibility (manager: identity/DB/run; supervisor:
canonical bytes), express ownership as data in a frozen result rather than as side-channel flags, make
the ordering observable through the injected callable, fail closed with typed dispositions instead of
host fallbacks, and never delete bytes whose registration the manager cannot disprove.

**Failure behaviour.** Provisioner exception → no active session, no workspace deletion unless the
result was `registered is False`; `provisioning_unavailable` for a new root; `workspace_not_ready` for a
degraded/failed readiness result in both paths, with `last_used_at` untouched on attach; conflict without
registration → `workspace_already_owned`; corrupt/unavailable authority → typed session error, no
partial result; run reservations survive rollback, so an issued run id never becomes reusable.

**DoD.** Injection ordering proven (the provisioner observes the workspace absent, creates it itself, and
no source bytes are copied); the request carries an existing session DB binding and run directory;
registered bytes survive a later readiness failure while the session dir is removed; a registered
conflicting workspace can be referenced by a second session with the first session's manifest/DB/run
bindings byte-identical; an unregistered conflict is rejected with no session dir; new-root provisioning
is a typed BLOCKED disposition; not-READY blocks new *and* attach; corrupt-manifest and legacy run-ID
tests still pass. **Negative proof:** deleting the injection call, the run reservation, either readiness
check, the registered-cleanup guard, or either half of the conflict confirmation each fails a named test.

**Tests-writing class.** C1 for the manager (real filesystem, real `SessionDatabase`, injected
provisioner boundary double) and C0/C1 for the adapter (real `WorkspaceAuthority` over a temporary
approved root). No container, no cgroup, no live deployment claim.

**Producer kill-check targets (declared, 8).** (1) the provisioner invocation in `_new_session`;
(2) the provisioning `begin_run` reservation (its namespace must exist before the call);
(3) not-READY enforcement in `_new_session`; (4) not-READY enforcement in `_attach_session`;
(5) the registered-aware cleanup guard; (6) the "permit registered reference" branch; (7) the
"reject unregistered conflict" branch; (8) the typed `provisioning_unavailable` disposition in
`ManagedProvisioner`.

**E2E ledger.** No surface count change (18/8); live rows stay PLANNED/UNEXECUTED. No STEP checkbox,
FUNCTIONAL contract or E223 duty is closed by a component increment.

#### E263 result — SLICE2 half shipped, with the Q78 readiness boundary

**Shipped.** `src/fa/session/provisioning.py` (frozen `ProvisionRequest`/`ProvisionedWorkspace`,
`ProvisionMode`, callable type, no execution imports), `src/fa/execution/provisioning.py`
(`ManagedProvisioner` over `register_existing`), `register_existing` now also returns `tree_sha256`,
and `SessionManager` gains `workspace_provisioner`, the provisioning `begin_run` reservation, the
frozen-result cleanup ownership, the reverse-owner confirmation and the readiness gate. Files:
`src/fa/session/{manager,provisioning}.py`, `src/fa/execution/{provisioning,workspace}.py`,
`tests/test_session_lifecycle.py`, `tests/test_execution_provisioning.py`.

**Evidence (actual outputs).** Red first: `ModuleNotFoundError: fa.session.provisioning`. Green:
`pytest tests/test_session_lifecycle.py tests/test_execution_provisioning.py -q` → 22 passed in 0.92s;
`test_cli.py` + `test_s10c_artifact_posture.py` → 54 passed. Statics: `ruff check src tests` → All
checks passed!; `ruff format --check` → clean; `mypy src/fa/session src/fa/execution` → Success: no
issues found in 21 source files; `python -m pyrefly check` → 0 errors. Targeted mutation: **11/11
assertion-only kills** (the provisioner call, the run reservation, both readiness call sites, the
readiness condition, the cleanup discriminator, both conflict branches, the PROVISION/REUSE mode
selection, the pre-cutover guard and the adapter's blocked disposition), sources restored byte-exact
with the bank green after every mutant.

**Q78 — when is not-READY a closed error?** Enforcing the declared rule unconditionally made the full
suite 141 failed / 6115 passed, of which **130 were one cause** (`workspace_not_ready` on bare `tmp_path`
workspaces) across 14 CLI/workflow modules, plus the sandbox's own repo classifying
`degraded_environment: precommit_prewarm_failed`. That would both hide real regressions in a long-red
suite and turn the inherited STEP10 toolchain gap into a hard product block. Decision (recorded, not
assumed): readiness is enforced **in the managed composition** — the configuration that injects the
provisioner, i.e. exactly the composition SLICE4 STEP2 creates when it removes fail-open readiness. The
pre-cutover host composition keeps reporting readiness without blocking, proven explicitly by
`test_readiness_degradation_without_a_managed_provisioner_stays_non_blocking` so the transition cannot
silently persist. After the change the suite returns to its pre-existing state (6181 passed / 81
failed, of which 78+2 are `T0 baseline unavailable` and 1 is the blocked readiness-integration case;
all 81 reproduce identically with this change stashed).

**SLICE4 STEP2 migration obligation (measured, not deferred silently).** When the provisioner is
injected into the CLI composition, these tests assert the pre-cutover contract and must be migrated to
a registered/real project workspace (or drive the managed provisioner): `test_verify_gate_live` 81,
`test_s8_workflow_controller` 16, `test_s10b_cli_parity` 8, `test_s10a_cli_coverage` 7,
`test_s10c_workflow_exit_contract` 6, `test_cli_ergonomics` 6, `test_s10c_artifact_posture` 6,
`test_s9_stats_projection` 4, `test_s7_cli_run_paths` 3, `test_verify_slice` 2,
`test_scope_hint_cache_key` 2, `test_readiness_announcement` 2, `test_workflow_global_history` 1,
`test_iteration_cap` 1, `test_cli` 1. Total 146 occurrences. This is a cutover task, not a defect.

**Not closed.** STEP3's SLICE3 half (publication-dependent new-root provisioning, post-commit failure
preserving registered bytes), the SLICE4 caller routing, every live row (18 surfaces / 8 joins remain
PLANNED/UNEXECUTED), all STEP checkboxes and FUNCTIONAL contracts. `ManagedProvisioner` is a component
adapter: it is not composed into any running service yet.

### E264 — SLICE2 STEP4 (part A): injectable workspace port for the file tools

**Idea.** `fs_read_file`, `fs_write_file` and `fs_edit_file` reach the filesystem by resolving a host
path under `workspace_root` and calling `Path.read_text`/`write_text`. That is a second, un-rooted write
path beside the supervisor's rooted view IO, so CT103's "tools use the same authorized view as shell"
cannot hold and the view's CAS/policy never applies to model edits. This increment gives those three
tools one injectable IO port, implemented by the execution authority over an admitted view, and carries
that binding on `SessionState` as the internal execution binding §4.2 asks for.

**Contract/gap IDs.** I03 SLICE2 STEP4 (part A; part B — search/reach, PTY parity, artifacts, PDF/
binary — follows as E265); CT103 (actual write/edit tools use supervisor rooted IO against the same
authorized open view as shell; deny protected/PlanRef/control destinations and alias escapes; no
canonical fallback); CT103a lineage; spec §4.2; Q76 (the binding carries the exact `ViewRef`; ordinary
non-workflow execution needs no plan hash).

**Allowed files.** New `src/fa/inner_loop/tools/workspace_port.py` (port protocol, result values,
`port_relative`, error codes; no `fa.execution` import, preserving today's layering where nothing
outside `fa.execution` imports it), new `src/fa/execution/tool_port.py` (adapter over
`WorkspaceAuthority.read_file`/`write_file`), `src/fa/inner_loop/tools/{read_file,write_file,edit_file}.py`
(one optional `workspace_io` parameter and one swapped IO seam each), `src/fa/inner_loop/profiles.py`
and `src/fa/inner_loop/tools/__init__.py` (forward the port; the role builder is the composition point
`build_baseline_registry` already uses), `src/fa/inner_loop/state.py` (`SessionState.workspace_io`),
tests, plan/ledger. No change to fs_search/reach, run_bash, the registry schema, or the CLI.

**Current behaviour (source-verified).** `build_write_file_tool`/`build_edit_file_tool`/
`build_read_file_tool` take only `workspace_root`; handlers call `resolve_workspace_path` then POSIX IO;
`edit_file` reads the whole file and rewrites it with `path.write_text` (no CAS, so a concurrent writer —
a PTY shell, another process — is silently overwritten). `WorkspaceAuthority.read_file`/`write_file`
already provide bounded rooted reads with `sha256`/`eof` and atomic writes with an optional
`expected_sha256` that raises `STALE_REVISION`, and `SessionState` has no execution binding at all. No
production module outside `fa.execution` imports `fa.execution` yet.

**Target behaviour.** With a workspace port present, the three tools read and write only through the
admitted view: relative POSIX paths validated by the port (no host resolution, no absolute paths, no
`..`, no NUL), bounded reads that return the exact `sha256`, and writes that carry the base `sha256`
observed by the edit so a concurrent change is a reported conflict instead of a silent overwrite.
Without a port the tools keep today's behaviour exactly (the pre-cutover composition); the port is the
seam SLICE4 wires into the real factory, never a second implementation of the tools.

**Mechanism.** `workspace_port.py`: frozen `PortRead{content, sha256, eof}`, `PortWrite{sha256, bytes}`,
`WorkspacePortError(code)` with a closed code set (`invalid_request`, `denied`, `stale`, `input_policy`,
`unavailable`, `not_found`), `port_relative(raw) -> str` (rejects empty, absolute, `..`, NUL; normalizes
`/`), and a `WorkspacePort` Protocol with `read_file(path, *, max_bytes)` /
`write_file(path, content, *, expected_sha256)`. `tool_port.py`: `AuthorityWorkspacePort(authority, *,
peer, namespace, view_ref, capability, deadline_factory)` maps `SupervisorError`/`ViewIOError` codes onto
the port vocabulary and passes `deadline` per call. Each tool gains `workspace_io: WorkspacePort | None`
and swaps exactly one seam (`_read_file_text` / the `writer` closure / the read+write pair), keeping its
parsing, framing, telemetry, blackboard guard and result shapes unchanged.

**Production best practice.** One implementation per behaviour with a seam, not a fork: the port is a
Protocol (the tools do not import the execution layer), the adapter is the only place that knows
authority call shapes and error codes, and optimistic concurrency comes from the substrate that already
implements it rather than from a new lock. Failure is expressed as a closed code the tool turns into a
`ToolResult.fail`, so a denied or stale write is never a silent success.

**Failure behaviour.** Path outside the view / absolute / `..` / NUL → `invalid_request` before any IO;
reader view or revoked capability → `denied`; changed base bytes → `stale` with the file left untouched;
too large or binary → `input_policy`; authority timeout or unavailable → `unavailable`; unknown file →
`not_found`. Each maps to a non-retryable or retryable `ToolResult.fail` per its class; no host fallback
occurs when the port is present.

**DoD.** Real tools built with a real `AuthorityWorkspacePort` over a real registered workspace write,
read and edit only the admitted view's bytes; an edit whose base changed between read and write reports
`stale` and leaves the other writer's bytes intact; a READ view denies writes; traversal and NUL are
rejected before the authority is touched; `build_baseline_registry(..., workspace_io=...)` and
`SessionState.workspace_io` carry the port to `fs_write_file`. **Negative proof:** removing the port
write, the read, the `expected_sha256` argument, `port_relative`'s traversal check, the adapter's error
mapping, or the registry forwarding each fails a named test.

**Tests-writing class.** C0 for `port_relative`/error mapping, C1 for the tools+registry over a real
authority and view (producer-level kill), C3 for traversal/reader-write denial. No PTY, container or
live claim in this part.

**Producer kill-check targets (declared, 6).** (1) the port write seam in `write_file`; (2) the port read
seam in `read_file`; (3) the `expected_sha256` base passed by `edit_file`; (4) `port_relative`'s
traversal/NUL rejection; (5) `AuthorityWorkspacePort`'s error mapping; (6) registry/profile forwarding
of `workspace_io`.

#### E264 result — part A shipped, and one mutant that turned out to be equivalent

**Shipped.** `fa/inner_loop/tools/workspace_port.py` (Protocol, `PortRead`/`PortWrite`, closed codes,
`port_relative`, `PORT_READ_MAX_BYTES` mirroring the substrate's single-read bound),
`fa/execution/tool_port.py` (`AuthorityWorkspacePort` over `WorkspaceAuthority.read_file`/`write_file`
with the closed error mapping), the three tool seams (`fs_read_file`/`fs_write_file`/`fs_edit_file`
each take `workspace_io=` and swap exactly one IO seam), registry/role-builder forwarding
(`build_registry_for_role`, `_build_tool_builders`, `_add_optional_tool_builders`,
`build_baseline_registry`), and `SessionState.workspace_io` as the §4.2 internal binding.

**Evidence (actual outputs).** Red first (`ModuleNotFoundError: fa.execution.tool_port`). Green:
`pytest tests/test_execution_tool_port.py -q` → 21 passed; the tool/registry bank
(`test_inner_loop_tools`, `test_inner_loop_registry`, `test_write_file_expected_root`,
`test_s127_fs_surface`, `test_s11_session_state_typing`, `test_prompt_registry_coherence`,
`test_fs_search`, `test_fs_reach`, `test_tools_common`, `test_coverage_tools_batch`, `test_cli`) →
210 passed. Statics: `ruff check src tests` → All checks passed!; `ruff format --check` → clean;
`mypy` on the changed modules → Success: no issues found in 23 source files; `pyrefly check` → 0
errors. Targeted mutation: **7/7 assertion-only kills** with byte-exact restoration.

**Findings the work forced (recorded, not hidden).**
1. *Circular import*: `SessionState` is imported by `fa.inner_loop.artifacts`, so a runtime import of
   the port from `state.py` re-entered the tools package. Fixed with `TYPE_CHECKING` imports in
   `state.py`/`profiles.py`; the annotation-only dependency is also the correct layering signal.
2. *Bound drift*: the first `PORT_READ_MAX_BYTES` (8 MiB) exceeded the substrate's 1 MiB single-read
   limit, so every full-file read would have failed as `input_policy`. The constant now mirrors
   `protocol.MAX_TEXT_BYTES` and the test asserts both values agree, so drift fails loudly.
3. *Absence is not disclosed*: a missing path surfaces as `PATH_DENIED`, not `NOT_FOUND`. The port
   vocabulary therefore has no `not_found` code; the tools report `read_failed` and say the file is
   missing *or* not permitted, which is the substrate's actual guarantee.
4. *Equivalent mutant*: removing `expected_sha256` from the edit write is **not** observable, because
   `RootedViewIO._target` already refuses to overwrite an existing file without a base digest. The
   tool's digest is defence in depth; the load-bearing mutant is a *wrong* digest, which fails the
   ordinary-edit test. Kill credit for the no-clobber rule stays with the substrate's own bank
   (`test_execution_views`), not with this increment.
5. *Test-double drift*: `test_prompt_registry_coherence`'s rogue builder did not accept the new
   `workspace_io` keyword, so the composition root's failure was swallowed by the fallback and the
   wire-name guard stopped firing. The double now mirrors the real signature — a reminder that a
   composition-root signature change must be reflected in every double that stands in for it.
   The full-suite run then found **two more** such doubles (`test_s13_10_tool_names` rogue and
   with_workflow, `test_quality_slice_coverage` broken_builders), each failing with
   `TypeError: ... unexpected keyword argument 'workspace_io'`. This is the same failure mode as (5)
   and worth naming plainly: the targeted bank passed while three suites outside it were red, so the
   *composition-root* signature is a cross-suite contract and only the full run proves it. All three
   doubles now mirror the real signature and take the real `WorkspacePort | None` type instead of an
   `object` stand-in (a weaker type hid the mismatch from mypy as well).

**Not closed.** STEP4 part B (fs_search/fs_reach pinning, PTY mutual visibility, artifact path
retention, PDF/binary/helper-unavailable results, seal/import alias with SLICE3), STEP5's whole-bank
producer kills, all live rows (18 surfaces / 8 joins PLANNED/UNEXECUTED), STEP boxes and FUNCTIONAL
contracts. `AuthorityWorkspacePort` is a component adapter: nothing composes it into a running service
yet (SLICE4 STEP2), so the pre-cutover host-path tools remain the deployed behaviour.

### E265 — SLICE2 STEP4 (part B-1): cell-local indexes, explicit read outcomes, no host Git

**Idea.** Part A gave the file tools a port for *bytes*. The rest of the tool surface still assumes
it owns the filesystem: `fs_search` writes its FTS index to `<root>/.fa/fts.db`, `fs_reach` hardcodes
`<root>/.fa/structural.db`, `fs_checkpoint`/`fs_undo`/`fs_diff` shell out to host `git`, and a `.pdf`
read goes to `_read_file_text`, which opens the *host* path. Under an admitted view those are three
distinct violations of the STEP4 exit clause — a tool writing into project bytes the supervisor owns,
a host Git read, and a canonical read that bypasses the port. This increment makes each one closed and
explicit: indexes move to the view's private cache (never project bytes), the two tools refuse rather
than index in-place when no such home exists, PDF/binary/oversized reads become named results instead
of a generic refusal, artifacts keep resolving through the controller's store, and the managed
composition stops shipping host-Git tools at all.

**Contract/gap IDs.** I03 SLICE2 STEP4 exit clauses (b) zero host Git/version-stamp reads, (c) active
search sees a new symbol while a reader stays pinned, (d) artifacts retain their controller path,
(e) PDF/binary/large/truncated/helper-unavailable results explicit with no canonical fallback;
increment line 309; spec §4.2 ("same-view bounded reads and cell-local existing search/reach
implementations; no new public tools/search service or private state mount"). Part B-2 (PTY/tool
mutual visibility with blackboard on/off) and the seal/import alias stay open — see "Not closed".

**Allowed files.** `src/fa/inner_loop/tools/workspace_port.py` (add the view's private cache home to
the port contract plus one shared index-placement helper), `src/fa/execution/tool_port.py` (adapter
supplies it), `src/fa/inner_loop/tools/fs_search.py`, `src/fa/inner_loop/tools/fs_reach.py` (derive the
index path from the port, refuse in-place indexing), `src/fa/inner_loop/tools/read_file.py` (explicit
PDF/binary/oversize outcomes and no host read on the port path), `src/fa/inner_loop/profiles.py` and
`src/fa/inner_loop/tools/__init__.py` (thread the port to search/reach; suppress host-Git pair tools
when it is bound), new `tests/test_execution_tool_index.py`, plan/ledger/E2E register. No new public
tool, no new search service, no private state mount, no substrate change, no change to the host-mode
(default) behaviour of any tool.

**Current behaviour (source-verified).** `build_fs_search_tool(db_path, workspace_root)` builds
`_IndexHolder(db_path)` and calls `SearchIndex.ensure_indexed(root)`; `profiles._build_tool_builders`
passes `root/<fts_db_path>` (default `.fa/fts.db`) and `tools/__init__._resolve_fts_path` does the same,
so the index lives *inside* the workspace. `build_fs_reach_tool(workspace_root)` hardcodes
`root/.fa/structural.db`. Both index the host directory tree directly (that is the intended "cell-local
existing implementation" — the defect is only where the index is *written*). `_register_extra_tools`
registers `fs_checkpoint`/`fs_undo`/`fs_diff`/`fs_send_ctrl_c`, and `pair_tools` runs
`git status|add|commit|rev-parse|branch|stash|checkout|reset|diff` with `cwd=root`. In `read_file`,
`handler` branches to `_read_file_text(path)` only when no port is bound; with a port it calls
`_read_port_text`, which returns `read_failed` for every closed code with a message that only names the
code — a `input_policy` refusal (the substrate's non-UTF-8/NUL answer) is therefore reported as a
generic workspace refusal, and `.pdf` (whose bytes the port cannot deliver) is reported the same way.
Artifacts never touch either path: `_read_artifact` resolves through `session.artifact_store` and the
run's projection store — the controller's own roots.

**Target behaviour.** With a `workspace_io`, `fs_search`/`fs_reach` place their index under the view's
private cache home (`workspace_io.cache_dir`) and **refuse** (typed, no IO, no index write) when that
home is absent or resolves inside the workspace root. Only the index location changes: both tools still
read the cell's own materialized tree, so an active view sees a symbol written a moment ago while a
pinned reader's index — a different cache home — keeps answering from its own revision. A `.pdf` read
through the port is refused by name before any IO (the substrate is text-only by contract); a
non-UTF-8/NUL refusal (`input_policy`) is named as binary content; an oversized read names the exact
managed bound and does not offer a line-window workaround the port cannot serve. Artifact reads are
unaffected: they resolve through the controller store even with a port bound. With a port bound, the
composition ships no tool that runs host `git`; host mode keeps all three pair tools unchanged.

**Mechanism.** `workspace_port.py` gains `WorkspacePort.cache_dir -> Path | None` (the view's private
scratch, deliberately *not* project bytes) and `index_db(port, root, filename, fallback) -> Path` which
returns `fallback` when no port is bound, else `cache_dir/filename`, raising
`WorkspacePortError("unavailable")` when `cache_dir` is None or is inside `root` — one implementation of
the placement rule for both tools. `tool_port.AuthorityWorkspacePort` takes `cache_dir=` and exposes it
(no authority change: the composition already knows the view's cache from `ViewInputs.cache`).
`fs_search`/`fs_reach` take `workspace_io=None`, resolve their index through `index_db` at *handler*
time (build time stays side-effect free) and return a `search_failed`/`reach_failed` non-retryable
result naming the missing index home. `read_file` maps the closed codes to named outcomes:
`input_policy` → "binary or non-UTF-8 content"; `not read.eof` → the managed bound; `.pdf` →
refusal before IO. `profiles`/`__init__` pass `workspace_io` to both builders and pass
`include_pair=False` when it is bound, logging the omission once (a silent drop would be the worse
failure).

**Production best practice.** Keep the index out of the artifact under validation (writing a cache into
the tree you are hashing invalidates the hash and makes a reader's answer depend on someone else's
write); make "I have nowhere to put this" a typed refusal rather than an implicit fallback to the
canonical tree; keep the default (host) path byte-identical so the pre-cutover behaviour cannot regress;
and let one helper own the placement rule so search and reach cannot drift.

**Failure behaviour.** No port → today's behaviour exactly. Port without a usable cache home → typed
non-retryable failure, zero index writes, zero host reads. Port with a cache home → index under it;
the returned tool result names neither the host path nor the cache path. PDF/binary/oversize → named
non-retryable or retryable-per-reason failures with no host-path mention. A pair tool is simply absent
from the managed registry (the model sees a smaller, honest tool set).

**DoD and negative proof.** New tests: managed search writes no index into the view and answers from
its cache; no cache home and an in-view cache home are both refused with no index file created;
`fs_reach` resolves from its cache home; an active view finds a newly added symbol while a pinned view
with a separate cache home does not; a `.pdf` read refuses without calling the port; `input_policy`
is named as binary content; an oversized read names the bound; an artifact read succeeds while the
bound port refuses any call; the managed registry contains no `fs_checkpoint`/`fs_undo`/`fs_diff`
while the host registry still does. Negative proof: delete `index_db`'s placement check → the in-view
case indexes inside the view; drop the `workspace_io` argument to the search builder → the view gains
`.fa/fts.db`; re-add `include_pair=True` under a port → the managed-registry test fails; restore the
generic `input_policy` message → the binary assertion fails.

**Not closed.** PTY/tool mutual visibility with blackboard on/off (needs the cell's PTY inside the
admission, i.e. the real backend — SLICE4/6), the seal/import alias (SLICE3), STEP5's whole-bank
producer kills, and every live row. Nothing composes `AuthorityWorkspacePort` yet, so the deployed
behaviour is still the host path.

#### E265 result — part B-1 shipped; one oracle had to be rewritten before it could hold

**Shipped.** `WorkspacePort.cache_dir` (the view's private cache home) and the shared `index_db`
placement helper; `AuthorityWorkspacePort(cache_dir=…)`; `fs_search`/`fs_reach` resolve their index
per call and refuse when the home is missing or inside the searched tree; `read_file` refuses `.pdf`
before any IO and names `input_policy` as binary content and a non-`eof` read as the exact bound;
`profiles`/`tools/__init__` forward the port to both index tools and drop the host-Git pair tools under
a bound port; `_safe_walk` skips its `git ls-files` fast path when the root has no `.git`.

**Evidence (actual outputs).** Red first (9 of 14 new cases failed on the unmodified tree). Green:
`tests/test_execution_tool_index.py` → 21 passed; the index/search/reach bank (`+ test_fs_search`,
`test_fs_reach`) → 80 passed. Targeted regression bank (tool, registry, session, provisioning, CLI
suites) → 285 passed. Statics: `ruff check src tests` → All checks passed; `ruff format --check` → 505
files clean; project `mypy` → Success, 493 source files; `pyrefly check` → 0 errors. Targeted mutation:
**10/10 assertion-only kills**, sources restored byte-exact.

**Findings the work forced.**
1. *A fail-degraded producer hides its own deletion.* The first version of the host-Git case made
   `subprocess.run` raise and asserted the search still worked. With the guard removed the search still
   passed: `_git_ls_files` catches every exception and falls back to `os.walk`, so the exception never
   reached the test — a masked producer in exactly the E259 pattern. The case now records invocations
   and asserts the list is empty; only then does deleting the guard fail it. Rule for the rest of
   SLICE2: when the code under test is fail-degraded by design, assert the *call*, never the exception.
2. *Three more composition-root doubles drifted* (`test_quality_slice_coverage` ×2, and the same class
   as E264's five): each failed with `TypeError: … unexpected keyword argument 'workspace_io'` because
   `_register_extra_tools`/`profiles` now pass the port to `build_fs_search_tool`. This is the third
   time this increment series has paid for that; the doubles now mirror the real signature and the
   real type, and the lesson is recorded once here rather than rediscovered per slice.
3. *`index_db` was typed for a port that "cannot be None"* while every caller passes `None` in host
   mode; `mypy` caught it only after the first draft. The signature is now `WorkspacePort | None` and
   the helper owns the host-mode fallback, so callers carry no `type: ignore`.
4. *PDF extraction cannot follow the bytes into the view.* The substrate is text-only by contract
   (`MAX_TEXT_BYTES`, NUL/UTF-8 rejection), so managed PDF reads have no path to the extractor chain.
   The refusal is explicit and named rather than silent — but this is a **capability difference against
   host mode**, so it is raised as Q79 below, not decided here.
5. *Index locality is now structural, not conventional.* Because both tools derive the index home from
   the view's cache, two views cannot share an index even in principle; the pinned-reader case asserts
   that by construction (distinct homes → distinct answers) rather than by timing.

**Not closed.** STEP4 part B-2 (PTY/tool mutual visibility with blackboard on/off — needs the real
cell), the seal/import alias (SLICE3), STEP5's whole-bank producer kills, every live row (18 surfaces /
8 joins still `PLANNED / UNEXECUTED`), and the STEP boxes and FUNCTIONAL contracts. `AuthorityWorkspacePort`
is still a component adapter: nothing composes it into a running service, so the deployed behaviour
remains the host path until SLICE4 STEP2. The live verification plan for these cases (including the
`PATH`-shim and `strace` oracles) is
[notes/i03-live-e2e-test-plan-2026-10-22.md](../notes/i03-live-e2e-test-plan-2026-10-22.md).

### E266 — SLICE3 STEP1 (part 1): the terminal barrier (CT104)

**Idea implemented now.** Closing a view's write admission is already possible and already durable; what
does not exist is the other half of the contract — proving the view's *cells* are dead before anything
downstream treats the tree as frozen. This increment adds exactly that half: a stop flow that closes
admission, drains live handlers, stops the view's cells, and then waits for a positive observation that
the cgroup is empty before the view may become `TERMINAL`. Everything short of that observation leaves
the view `STOPPING` (quarantined), because "we asked it to stop" is not terminality.

**Contract/gap IDs.** CT104 (and its named producer `supervisor.py::stop_view ->
_wait_descendants_terminal`); I03 SLICE3 STEP1 (terminal barrier/view state machine half; the seal and
immutable-export half is the next increment); spec §4.2 ("actual terminality plus sealed-tree/protected-
path validation is the publication authority").

**Allowed files.** `src/fa/execution/workspace.py` (add `mark_terminal` only — the authority stays the
single owner of view state), `src/fa/execution/supervisor.py` (`ViewStopper`, `CellTermination`,
`TerminalVerdict`, `ViewStopResult`, `_wait_descendants_terminal`), new
`tests/test_workspace_publication.py` (the plan's fixed filename for the local half), plan/ledger.
Not touched: `publication.py` (seal/publish — next increment), `docker.py` (no cgroup reader yet), the
backend, the CLI/service composition, any wire schema.

**Current behaviour (source-verified).** `WorkspaceAuthority.close_admission` sets the per-view gate
closed, moves `view.record["state"]` from `OPEN` to `STOPPING` with fsync + read-back, and turns every
subsequent file operation into `VIEW_CLOSED` via `_live_view`. `drain` waits for the gate's active set
and refuses if admission is not already closed. Nothing anywhere transitions `STOPPING` to anything
else: `grep -rn "def stop_view\|_wait_descendants_terminal" src/fa/execution` is empty, `docker.py`
documents "Deliberately no terminal_barrier: Docker stopped != cgroup populated=0", and
`CellBackend.close` is a backend-wide teardown rather than a per-view stop plus observation. So a view
can be admission-closed while its cells still write: the CT104 hole, exactly.

**Target behaviour.** `stop_view` is the only path that may produce `TERMINAL`, and it produces it only
after: (1) irreversible admission closure, (2) a drained handler set, (3) a stop call for the view's
cells, (4) a *positive* observation of descendant emptiness inside the remaining budget. A view whose
cells are still populated, whose observation is unavailable, whose observer raises, or whose budget runs
out stays `STOPPING` and keeps its ownership — no release, no seal, no reuse. A `TERMINAL` view is
idempotent: stopping it again touches no cell. `mark_terminal` alone can advance `STOPPING`, never
`OPEN`, so the barrier cannot be short-circuited by calling the state transition directly.

**Exact mechanism.** `WorkspaceAuthority.mark_terminal(peer, namespace, *, view_ref, capability,
deadline)`: proof, then `VIEW_CLOSED` unless the gate is closed; `OPEN` is refused explicitly; `TERMINAL`
is a no-op; otherwise rewrite `view.json` through the existing `_replace_private_bytes` and read it back —
a mismatch or OS error marks the authority unhealthy and raises `DURABILITY_UNKNOWN`, exactly as
`close_admission` does. `supervisor.CellTermination` is the two-method seam the real backend will
implement (`stop_cells`, `cells_terminal -> bool | None`; `None` means "cannot tell"). `ViewStopper
.stop_view` sequences close → drain → stop → `_wait_descendants_terminal` → `mark_terminal`, and returns a
frozen `ViewStopResult{state, verdict, reason}`. `_wait_descendants_terminal` polls on a small interval
until the deadline, treating `False` as "not yet", `None` and any exception as `UNKNOWN`, and the deadline
itself as `UNKNOWN` — never as success.

**Production best practice.** The state owner stays single: the authority writes view records, the
stopper only decides when to ask it to. The barrier is an injected seam because the observation is a
kernel fact that cannot be faked in-process; a missing seam is a closed refusal, not a bypass. Polling
exists because stopping a container is asynchronous — the API returning is explicitly not the kernel
fact. And the whole flow is bounded: a hung observer must not hang the supervisor.

**Failure behaviour.** Live cells → `POPULATED`, state `STOPPING`, ownership retained. Observer absent,
raising, or unreadable → `UNKNOWN`, state `STOPPING`. Budget exhausted while draining or observing →
`SupervisorError` from the drain or `UNKNOWN` from the observation; either way nothing is marked. Record
persistence failure at the mark → `DURABILITY_UNKNOWN` and the authority goes unhealthy. Repeated stop on
a `TERMINAL` view → `TERMINAL` with no cell traffic.

**DoD and negative proof.** New tests (C0 for `mark_terminal`, C3 for the orchestration over the real
authority, real view records on disk and a recording barrier): write denial is observable *at* cell-stop
time (proving admission closed first); polling continues until a positive observation; a populated view
stays `STOPPING` with its on-disk record unchanged; an exception is `UNKNOWN`; no observer is `UNKNOWN`
and stops no cells; a terminal view is idempotent; `mark_terminal` refuses `OPEN`, is idempotent for
`TERMINAL`, and persists durably. Negative proofs: deleting the `close_admission`, `drain`, or
`stop_cells` call, treating `None`/exception as terminal, treating a deadline as terminal, or dropping
`mark_terminal`'s state guard each breaks a named assertion. Classes: C0 + C3. The kernel fact
(`/sys/fs/cgroup/**/cgroup.events` `populated 0`) is C-host and belongs to
`tests/integration/test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`; it is NOT claimed
here and the local tests use an observer double only where the observation is genuinely external.

**Not closed.** Seal and immutable-export validation (CT105), publish (CT106), recovery (CT107), the real
cgroup reader and the Docker-backed `CellTermination`, "restart cannot release a live old writer"
(durability of the stop intent), and every live row.

#### E266 result — the barrier exists, and two "obvious" oracles had to be replaced

**Shipped.** `WorkspaceAuthority.record_terminal` / `terminal_receipt` (a durable, separate
`terminal.json` receipt; the view keeps the closed state vocabulary the protocol publishes) and
`supervisor.ViewStopper` with `stop_view` + `_wait_descendants_terminal`, the `CellTermination`
seam and typed `TerminalVerdict` / `ViewStopResult` (`to_wire()` == the protocol's `{view_id,
terminal}`). Every path that cannot *observe* emptiness leaves the view `STOPPING` and owned.

**Evidence (actual outputs).** `pytest tests/test_workspace_publication.py` → 11 passed. Execution
bank (`workspace`, `views`, `readers`, `purposes`, `view_io`, `backend`, `journal`, `dispatch`,
`client`, `supervisor`) → 643 passed. Statics: `ruff check src tests` → All checks passed;
`ruff format --check` → 506 files clean; project `mypy` → Success, 494 source files; `pyrefly check`
→ 0 errors. Targeted mutation: **9/9 assertion-only kills**, sources restored byte-exact.

**Findings the work forced.**
1. *A receipt, not a state.* My first design minted a `TERMINAL` view state; the compiled
   `_VIEW_RECORD` schema publishes the closed set `OPEN/STOPPING/SEALED/PUBLISHED/REJECTED/UNKNOWN`,
   so terminality had to become a **separate durable receipt** that sealing will consume. This is the
   better contract anyway: terminality is a precondition of seal, not a view phase.
2. *`drain` is load-bearing only for dispatch work.* Under the authority mutex a file handler
   serializes against `close_admission`, so "skip the drain" was initially an **equivalent mutant**.
   The real window is a `WorkAdmission` held across create/start/send (outside the mutex); the test
   that holds one proves cells are not stopped under a live dispatch. Without that test the drain
   call could have been deleted with no red anywhere.
3. *A read-back needs a non-persisting write to be observable.* Deleting the post-write verification
   survived until a test replaced `_replace_private_bytes` with a no-op and required
   `DURABILITY_UNKNOWN` — the honest oracle for "the write claimed success but did not land".
4. *Three mutation expectations named the wrong test.* The mutants were killed, but by the new
   cases, not the ones listed. The `expect` lists now name the test that actually holds each
   producer; a kill attributed to a test that does not assert the property is not evidence.

**Not closed.** Seal and immutable-export validation (CT105), publish (CT106), recovery (CT107), the
Docker-backed `CellTermination` + real cgroup reader (C-host, `tests/integration/test_publication_recovery.py`
under `FA_REQUIRE_EXECUTION_HOST=1`), "restart cannot release a live old writer", STEP5's full-bank
kills, and every live row (18 surfaces / 8 joins still `PLANNED / UNEXECUTED`). Nothing composes
`ViewStopper` into the service yet: `STOP_VIEW` has an encoded reply but no dispatcher route.


## E267 — SLICE3 STEP1 (part 2): immutable export and seal (CT105) — declaration before code

**Status: PLAN ONLY, awaiting operator approval. No `src/` edit, no STEP tick, no live verdict.**
Written 2026-10-22 after E266 (`6ff1121`) and after a source re-read of `workspace.py`,
`supervisor.py`, `protocol.py` and spec §5. This section is the approval artifact: nothing below
is implemented or claimed.

### E267.0 Ordering verification (the operator asked for this first)

The incoming hand-off said *"E267 — SLICE3 STEP2: seal (CT105)"*. Source and plan say that label is
off by one step, and the **work content is still the right next unit**:

| Claim | Verified against | Result |
| --- | --- | --- |
| seal is STEP1's remainder, not STEP2 | `increment-03:343` — STEP1 = "Q74 policy + stage transition table + terminal barrier + **immutable export validation in execution/publication.py**"; `increment-03:344` — STEP2 = "exact intent/current/projection schemas … generation/base CAS" | **correction:** E266 shipped STEP1's barrier; E267 is STEP1 *part 2* (seal), and STEP2 (CAS/publish state) follows as E268 |
| seal needs no unfinished SLICE2/STEP1 code | seal's inputs all shipped: view records + view records + `workspace.py::_proof_only`, closed gate (`::close_admission`, `::drain`), terminal receipt (`::record_terminal`, `::terminal_receipt`), base revisions (`::_revision`), tree walker (`::_Capture`, `::_snapshot`), purpose matrix (`_purposes`, E259) | **holds** — no dependency on SLICE2 STEP4 part B-2 (needs a real cell), STEP5 (kill recording), SLICE1 STEP2/3 (service composition) or Docker |
| publish is what closes SLICE2 STEP3's provisioning leg | `increment-03:295` (SLICE2 STEP3 "SLICE3 half (exit, moves to SLICE3's evidence)") + spec §5 steps 1–5 | **holds** — seal alone closes nothing; say so and do not imply it |
| `SEALED` is a real state the receipt unlocks | `_VIEW_RECORD` state enum `OPEN|STOPPING|SEALED|PUBLISHED|REJECTED|UNKNOWN` (`workspace.py::_VIEW_RECORD`); E266 left the view in `STOPPING` with `terminal.json` | **holds** — seal is the only `STOPPING → SEALED` transition, and it must require the receipt |
| `STOP_VIEW` has no dispatcher route yet | `_dispatch`/`_handle` are injected seams; no `stop_view`/`seal` route exists in `supervisor.py` | **holds** — local tests call the owners directly; routes land with SLICE1 STEP3 composition |

Two source findings that change the step's shape and must be resolved *inside* E267:

1. **id-prefix contradiction.** The wire says `seal-…`: `Operation.SEAL` result
   (`protocol.py:162`) and `Operation.PUBLISH` payload (`protocol.py:126`). The persisted view record
   says `manifest-…`: `_VIEW_RECORD.sealed_manifest_id` (`workspace.py::_VIEW_RECORD.sealed_manifest_id`). Seal is the first writer
   of that field, so one of the two must move now (decision D5).
2. **the seal manifest is not `_TREE`.** Spec §5 freezes a different header
   (`schema_version, workspace_id, generation, base_revision, view_id, tree_sha256, entries`) and
   requires deletion tombstones, while `_TREE`/`_ENTRY` (`workspace.py::_TREE`, `::_ENTRY`) carry `revision_id`
   and pin `deleted` to `False`. `publication.py` therefore owns its own `_SEALED_MANIFEST`; extending
   `_TREE` would silently widen the revision format that readers verify with `_revision()`.

Also verified so the plan does not promise them: `_seal_readonly_source` (`workspace.py::_seal_readonly_source`) is a
**different** operation (freezing a READ execution input for a cell, write bits stripped) and is not
CT105; and `_Capture` refuses hardlinked files (`nlink == 1`), setuid/setgid/sticky bits, mounts
crossing device ids, non-UTF-8 names and unsafe links — seal inherits those refusals as declared
contract, not surprise.

### E267.1 Contract and gap IDs

CT105 (FUNCTIONAL, kill target `publication.py::seal_view -> _validate_sealed_tree`); SLICE3 STEP1;
spec §5 (seal half only — the current-pointer half is STEP2) and §5.1's `kind`/`phase` vocabulary
only where seal must *not* write it; E266's receipt is the precondition; E259's purpose matrix is
inherited unchanged. Q63/Q74/Q59–Q66 are untouched. Nothing here is L2 `VERIFIED`.

### E267.2 Current behaviour (source-verified, `6ff1121`)

- A writable view is a full private materialization at
  `state/workspaces/<ws>/views/<view_id>/{view.json,source/,scratch/}`, installed once by
  `_install_view` (`workspace.py::_install_view`) through `_rename_directory` → `renameat2(RENAME_NOREPLACE)`
  (`view_io.py:29-33,94-98`). After install nothing re-walks the source tree.
- `view.record` holds `state`, `input_tree_sha256` (base tree hash at creation),
  `sealed_manifest_id` (always `None` today) and `plan_ref`; it is the closed record the protocol
  publishes, and `_project_view` (`workspace.py::_project_view`) refuses any state other than `OPEN`.
- The barrier writes `terminal.json` (`record_terminal:2113`) and leaves `view.json` in `STOPPING`;
  admission is closed and handlers drained before that.
- There is no `publication.py`, no sealed manifest, no `SEALED` transition, and no producer that
  recomputes a view's tree after the barrier. `tests/test_workspace_publication.py` (E266, 11 cases)
  covers CT104 only.

### E267.3 Target behaviour (rules the tests will hold)

- **R1 preconditions.** Exact-view proof by capability and principal (`_proof_only`), gate closed,
  state exactly `STOPPING`, terminal receipt present, binding still `OWNED` by this actor at
  `ref.generation`, `current.revision_id == ref.base_revision`, `input_tree_sha256` equal to that
  revision's tree hash, and `ProtectedPlanContext.recheck()`. Absent receipt → `TERMINALITY_UNKNOWN`;
  open gate / `OPEN` view → `VIEW_CLOSED`; stale base/generation/source → `STALE_REVISION` or
  `INPUT_POLICY`. A `SEALED` view re-seals idempotently (R8). No `seal` on `UNKNOWN`/quarantine.
- **R2 recompute, never trust.** Walk `source/` through the existing `_Capture` under the caller's
  deadline and `InputLimits`, with the authority's exclusions. The tree hash is computed from the
  bytes read after the barrier; `input_tree_sha256`, `tree.json` or any model/cell-supplied manifest
  is cross-checked, never adopted.
- **R3 base comparison and tombstones.** Base entries come from `_revision(binding, base_revision)`.
  Paths present in base and absent in the seal become tombstones carrying that base entry's
  `type/mode/size/sha256/link_target` with `deleted: true`; a type change at one path is delete+add;
  additions/changes carry recomputed facts. `tree_sha256` hashes canonical JSON of **non-deleted**
  entries only (§5), so `deleted` is a transport fact, not part of the digest.
- **R4 manifest v1.** Exact header from §5, entries sorted by unique relative path, `mode` an integer
  `<= 0o777`, `size >= 0`, file SHA over bytes, symlink SHA over UTF-8 target with the byte length as
  size, directory `sha256`/`link_target` null. A `_SEALED_MANIFEST` schema in `publication.py`, not a
  reuse of `_TREE`.
- **R5 protected and excluded domain.** Reject any entry or tombstone that **is**, **contains** or **is
  contained by** the PlanRef canonical path; reject deletion, rename or type change of an ancestor that
  would carry protected/excluded canonical bytes; `.git`, `.fa`, `.venv`, `.env` (and configured
  exclusions) are dropped by `_Capture`, so they can never become tombstones — the test asserts that
  rather than trusting it.
- **R6 links.** Only symlinks already present and unchanged in the base revision may seal; a new or
  changed link is `INPUT_POLICY`. Absolute, escaping and excluded-target links stay refused by
  `_Capture._link` (reused producer, no new credit).
- **R7 durability order.** Write the sealed manifest (`seal-…` id, manifest v1 body) to the view's
  private directory with `_replace_private_bytes` + fsync + read-back equality, **then** flip
  `view.json` to `SEALED` with `sealed_manifest_id` and read it back. Any failure after the manifest
  exists is `DURABILITY_UNKNOWN`; the view stays `STOPPING` and no `SEALED` success is reported.
- **R8 idempotence.** A retried seal on a `SEALED` view returns the stored identity after verifying
  the stored manifest's own hash, without a second manifest and without re-sealing changed bytes
  (there cannot be any: the gate is closed and the barrier holds). A retry that recomputes a
  *different* tree hash than the stored manifest is `CORRUPT_STATE`, never a quiet re-seal. `PUBLISHED`
  is a finished lifecycle and `OPEN`/`REJECTED` have nothing to seal, so both are `VIEW_CLOSED`.
- **R9 failure classification.** Determinate validation failure (protected/link/mode/type/path/limits)
  → its closed error code with **no state write** (D3: `STOPPING` is kept; `REJECTED` is not reachable
  from `STOPPING` per §5:884); staleness (`ref.generation`, `current.revision_id`, source hash) →
  `STALE_GENERATION`/`STALE_REVISION`, never `SEALED`; missing receipt or `UNKNOWN`/quarantined view →
  `TERMINALITY_UNKNOWN`; OS/durability → `DURABILITY_UNKNOWN`, state untouched, authority unhealthy;
  wrong capability/namespace/principal → `UNAUTHORIZED`.
- **R10 no side effects.** Canonical roots, `current.json`, revisions, Git index, other views' pins,
  scratch and any cell state are untouched; no Docker call; no execution of anything found in the
  tree; no model-provided metadata is read.
- **R11 reply.** Exactly `{sealed_manifest_id, revision_id, tree_sha256}` per `protocol.py:162` and
  spec §2.1:163. `sealed_manifest_id` is this seal's opaque object id (`seal-…`, D5); `revision_id` is
  the deterministic id of the revision publish must materialize (D2), recomputable from the stored
  manifest; `tree_sha256` is the sealed tree digest.

### E267.4 Decisions requested (answer these, then code starts)

- **D1 — step label.** Record E267 as SLICE3 **STEP1 part 2** (seal/CT105) and renumber the intended
  next unit (CAS/publish) as E268 = SLICE3 STEP2. Recommended, matches `increment-03:343-344`.
- **D2 — `revision_id` in the SEAL reply. RESOLVED from records (2026-10-22), not asked.** Spec
  §2.1:163 freezes the reply as `{sealed_manifest_id, revision_id, tree_sha256}` and says the
  *"immutable revision may be unpublished"*, while §5's five-step publish flow creates `Rnext` at its
  step 1 and §5.1 only discriminates recovery through `intent.json` (`PREPARED + old current … discard
  only uncommitted owned **Rnext**`). A revision materialized at seal would therefore sit outside every
  documented recovery row. **Decision:** seal mints the id of the revision publish must create, derived
  deterministically from the sealed bytes — `"rev-" + sha256(canonical(sealed_manifest))[:32]` — so
  publish recomputes the same id from the stored manifest instead of trusting a caller, and the id is
  tamper-evident by construction. Seal writes no `revisions/…` bytes, no `intent.json`, no `current.json`.
  Materializing `Rnext` under exactly that id is E268's step. Rejected alternative (materialize at seal)
  is recorded above with the recovery-table reason.
- **D3 — durable `REJECTED`. RESOLVED from records, and it overturns the declaration's own
  recommendation.** Spec §5:884 fixes the chain `OPEN → STOPPING → SEALED → PUBLISHED|REJECTED`:
  `REJECTED` is reachable **from `SEALED`**, never from `STOPPING`. Writing `REJECTED` on a failed seal
  would invent an undocumented transition. **Decision:** a determinate seal validation failure returns
  its closed error code and writes **no** state — the view stays `STOPPING` with its gate closed, its
  receipt and its frozen bytes, so the same deterministic refusal repeats on retry; `REJECTED` belongs
  to E268's `SEALED → PUBLISHED|REJECTED` branch. `UNKNOWN`/quarantined views cannot seal at all
  (`TERMINALITY_UNKNOWN`), and `DURABILITY_UNKNOWN`/`STALE_*` never write `SEALED`.
- **D4 — scope.** E267 seals the tree for `PROJECT`/`PROVISIONING`/`MUTATION`. `CANDIDATE` buffer
  validation and `PLAN`/`BOOTSTRAP` kinds move to STEP3 with `prepare_bundle`/`install_project`
  (recommended: §5 ties the candidate buffer to PLAN-intent publication, and sealing a buffer without
  its publisher would create a second, half-specified path).
- **D5 — `sealed_manifest_id` prefix.** (a) widen `_VIEW_RECORD.sealed_manifest_id` from
  `_id("manifest-")` to `_id("seal-")` so the record and the wire name one object (recommended;
  internal record schema only — the wire contract at `protocol.py:126,162` is unchanged and no test
  writes a `manifest-` id today); (b) mint `manifest-` ids in the record and translate at publish.
- **D6 — evidence environment.** This sandbox has **no Docker** (host work stays `BLOCKED` by
  design) and its source-built CPython 3.13.7 lacks `_ctypes`, `_sqlite3`, `_ssl` and `zlib`
  (no libffi/zlib/sqlite headers, no reachable distro mirror). A disclosed, out-of-repo shim
  (`pysqlite3` alias + `renameat2` emulation) makes the local banks runnable: baseline right now is
  **1126 passed, 6 errors**, the six being the installed-wheel build cases (`uv build` offline).
  Options: (i) I run local construction checks under that shim, label them **non-authoritative**,
  and you re-run the declared fences on your 3.13 host before any STEP tick (recommended);
  (ii) I write code only and you run every bank; (iii) stop until a conforming environment exists.

### E267.5 Allowed files (nothing else)

- `src/fa/execution/publication.py` — **NEW**: `seal_view`, `_validate_sealed_tree`, `_SEALED_MANIFEST`.
- `src/fa/execution/workspace.py` — only the D5 record-prefix widening (and, if D5(b), the mapping).
- `tests/test_workspace_publication.py` — new CT105 cases beside the E266 CT104 bank.
- Docs: this section, `ledger.md` E267 result, one new E2E register row `I03-LIVE-19`.
- **Forbidden:** `protocol.py` (no wire change), `supervisor.py` (no dispatcher route in this step),
  `docker.py`/`backend.py`/`client.py`, any caller, mount or cutover change, any new module beyond
  `publication.py`, any second walker or second lock.

### E267.6 Tests (C0/C3, real filesystem, real authority)

Fixture: the existing `Site`/`Site.claim`/`native_profile` helpers, real view creation through the
authority, real `stop_view` with the `CellTermination` seam doubled only for the kernel fact (as
E266), then `seal_view` called directly. Cases: happy-path seal and exact manifest body; recompute
beats a poisoned `tree.json`; tombstone from a deleted file; type change; protected PlanRef path,
its ancestor and its descendant each refused; new/changed/escaping link refused; unchanged legal link
accepted; setuid bit refused; excluded paths absent from the manifest; stale generation and stale base
refused; missing receipt → `TERMINALITY_UNKNOWN`; `OPEN` view → `VIEW_CLOSED`; seal twice → same id;
manifest rewrite → `CORRUPT_STATE`; read-back failure → `DURABILITY_UNKNOWN` and no `SEALED`; a
concurrent write attempt after the barrier cannot change sealed bytes; canonical root, `current.json`,
revisions and a pinned reader are byte-identical before/after.

### E267.7 Negative proof — declared kills (assertion-only, byte-exact restore)

1. `publication.py::seal_view -> _validate_sealed_tree` (CT105's named producer).
2. the terminal-receipt precondition in R1.
3. the base/generation staleness equality in R1.
4. the protected-path rejection in R5.
5. the tombstone derivation in R3.
6. the recompute in R2 (mutant: trust `input_tree_sha256`/stored manifest).
7. the `SEALED` write + read-back in R7.
8. the manifest-id binding between record and manifest file.
9. the new-link rejection in R6.

Reused and **not** claimed as new credit: `_Capture._link`, `_Capture` fingerprint staleness,
`_revision` corruption checks, `record_terminal`.

### E267.8 Definition of done

Red-first evidence for the functional cases; the owning bank (`tests/test_workspace_publication.py` +
the execution bank) green; `ruff check`, `ruff format --check`, `mypy src/fa/execution`,
`pyrefly check src/fa/execution` clean; all declared kills executed with source restored; the E2E
register extended with `I03-LIVE-19` (`publication.py`, `PLANNED / UNEXECUTED`) and S06 wording
unchanged; no STEP checkbox, no CT `VERIFIED`, no deployment claim. SLICE3 STEP1 stays open
afterwards: Q74's per-stage checkpoint policy and the real cgroup observer are still its parts.

### E267.9 Out of scope (explicit)

`publish_view`/`current.json`/intent/projection/CAS and Git-index preservation (STEP2); recovery
(STEP4); `prepare_bundle`/`install_project`/Q58/BOOTSTRAP and candidate-buffer seal (STEP3); CT104–107
whole-bank kill recording (STEP5); SEAL/STOP_VIEW dispatcher routes, `build_supervisor/main` and any
caller/mount cutover (SLICE1 STEP3, SLICE4 STEP2); real Docker/cgroup proofs
(`tests/integration/test_publication_recovery.py`, `FA_REQUIRE_EXECUTION_HOST=1`, host work);
deployment and every live verdict (final SLICE6).

### E267 result — SLICE3 STEP1 (part 2) shipped as local component proof

**Shipped.** `src/fa/execution/publication.py` (NEW): `seal_view`, `_validate_sealed_tree`, the frozen
`_SEALED_MANIFEST` schema, `derive_revision_id`, `SealResult`. `src/fa/execution/workspace.py`:
`prepare_seal` (all seal preconditions + the post-barrier recompute), `mark_sealed` (the single durable
`STOPPING → SEALED` transition with read-back), `_SealInputs`, and the D5 id alignment
(`sealed_manifest_id` now requires `seal-…`, matching `protocol.py:126,162`). Tests:
`tests/test_workspace_publication.py` (CT105 section added beside the E266 CT104 bank).

**Decisions as resolved.** E267a records D2 (seal mints a *content-derived* revision id, publish
materializes it) and D3 (`REJECTED` is not reachable from `STOPPING`; a determinate seal failure writes
no state). D1/D4/D5 were approved as written.

**Red → green.** Red: with `workspace.py` reverted and `publication.py` absent, the module errors at
`import fa.execution.publication` (collection error, recorded honestly rather than claimed as a
per-rule red). Green: `pytest tests/test_workspace_publication.py` → **24 passed** (11 retained CT104
cases + 13 new CT105 cases).

**Owning/broader banks.** `test_execution_views`, `_workspace`, `_readers`, `_view_io`, `_admission`,
`_purposes`, `test_workspace_publication` → **359 passed**. Execution + readiness + provisioning bank
(`tests/test_execution_*.py`, `test_workspace_publication.py`, `test_controller_entry.py`,
`test_workspace_readiness_integration.py`, `test_session_workspace_provisioning.py`) →
**1241 passed, 1 failed**. The failure is
`test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication`
with `degraded_environment: precommit_prewarm_failed`; **proved pre-existing** by reverting both source
files and reproducing the identical failure (the Q78/E263 sandbox blocker, not this change).

**Static gates (actual output).** `ruff check src tests` → `All checks passed!`; `ruff format --check
src tests` → `507 files already formatted`; `mypy src/fa/execution` → `Success: no issues found in 19
source files`; `pyrefly check src/fa/execution` → `0 errors`.

**Declared kills — 9/9, assertion-only, source restored by sha256 after each mutant.** Mutants and the
test that killed each: validator call removed → the link case; terminal-receipt precondition removed →
the open-view/receipt case; generation equality removed → the generation case; plan boundary removed →
the direct plan case; tombstone derivation removed → the tombstone case; recompute replaced by the
stored hash → three recompute/tombstone/link cases; `SEALED` write removed → 10 cases; reply id unbound
from the record → two cases; new-link rejection removed → the link case.

**Two masked producers found by the sweep, and how each was handled (the E259/E262 pattern).**
1. *Terminal-receipt precondition.* `mark_sealed` repeats the check, so removing it from
   `prepare_seal` was invisible. The real difference is a durable side effect: the manifest would be
   written for a view whose terminality was never proved. The case now asserts the absence of
   `sealed.json` after the refusal, which is the property that matters, and the kill is attributed to
   that assertion.
2. *Plan boundary.* End-to-end it is **fully masked** by `prepare_seal`'s `ProtectedPlanContext.recheck`
   (a WRITE view's context roots at its own source, so an edited plan never reaches the manifest rules).
   The rule is kept as manifest-level defence and given its own direct oracle; the kill is recorded as
   unit-level, not as an end-to-end seal-flow win. Also verified while doing this: the recompute
   mutant (6) is not masked — it fails three independent cases.

**Recorded findings.** (1) `_TREE`/`_ENTRY` cannot express tombstones (`deleted` pinned `false`) and
carry `revision_id`, so the seal manifest needed its own schema — extending the revision format would
have widened what readers verify. (2) The wire id prefix (`seal-`) and the persisted record prefix
(`manifest-`) disagreed; the record moved, the wire did not. (3) A `SEALED` view re-enters
`prepare_seal`, so the idempotent path answers from durable bytes and compares the *recomputed* digest
with the stored one, which is what catches a rewritten manifest. (4) The expected-sha/link rules that
`_Capture` already enforces are reused, not re-implemented.

**Not closed.** SLICE3 STEP1 stays open: Q74's per-stage checkpoint policy, the real Docker/cgroup
`CellTermination` observer and `tests/integration/test_publication_recovery.py` under
`FA_REQUIRE_EXECUTION_HOST=1` are untouched. STEP2 (publish/CAS/projection, CT106) is E268; STEP3
(bundle/Q58/BOOTSTRAP + candidate-buffer seal), STEP4 (recovery, CT107) and STEP5 (whole-bank kills)
remain. `STOP_VIEW`/`SEAL` still have no dispatcher route. No STEP box, FUNCTIONAL contract, live row
or E223 acceptance duty is closed by this work; the SLICE2 STEP3 provisioning leg stays open until
publish lands.

### E277 result — SLICE1 STEP3 part 2: the composed supervisor (route table, socket owner, `main`)

**What shipped.** A new `src/fa/execution/service.py` owns the composition and the private UDS:
`ServiceConfig` (strict, no defaults for trust inputs), `load_config`/`read_config_file`, and
`SupervisorService` — the real `WorkspaceAuthority`, its journal, the completed-reply cache, the
`SupervisorDispatcher` and the one socket. `supervisor.build_supervisor(config)` and `supervisor.main(argv)`
are the §2.2 names and are thin over that object. Two authority additions were required by the wire
schema: `ready` (the `health` fact, true only after flock + `recover_uncertain` + `_load`) and
`release_writer(capability)` (the `release` payload is empty, so only the proved grant can name the
binding; it and `release_unused_writer` now share one `_settle_owner`). `profiles.profile_set_sha256`
is the canonical digest of the enforced profile set.

**Route table (nineteen rows, derived names, checked for totality at construction).** *(E282 note: this is
E277's snapshot. E279/E280 then routed `exec`, `inspect`, `cancel` and `pty_control`, so only the last two
rows below are still dormant, and `handoff` now has an owner — SLICE2 STEP6/CT113.)* Live against a
real owner: `health`, `register_workspace{create:false}`, `acquire_writer`, `pin_reader`, `create_view`,
`read_file`, `write_file`, `edit_file`, `release` (pin or owner), `stop_view` (close + drain only),
`seal`, `publish`, `prepare_bundle`, `install_project`. Declared dormant with an explicit
`BACKEND_UNAVAILABLE` refusal and the activating unit:

| route | why it cannot be honest yet | activated by |
| --- | --- | --- |
| `exec`, `inspect`, `cancel` | `CellBackend` returns a `CommandOutcome`; there is no `ExecutionReceipt` issuer and no independent (cgroup) terminal barrier, so `EXITED` could not be asserted truthfully | receipt issuer + terminal barrier unit |
| `pty_control` | `WorkerClient` has `begin`/`await_reply`/`request`/`close` only — no list/interrupt/close verbs scoped to an episode | PTY control unit |
| `handoff` | no `WorkspaceAuthority.handoff` exists at all | owner-handoff unit (terminal/settled source, parent-child proof) |
| `register_workspace{create:true}` | only `register_existing` exists; creating a root is managed acquisition | SLICE5 |

**Current vs target behaviour.** Current: the service starts only with an explicit config, completes
recovery before binding, serves one request per connection over a 0600 socket, and answers every
operation with either its real owner's exact closed reply or a closed-code refusal. Target (unchanged):
STEP3's exit also needs the install/image/entrypoint set, the real `CellBackend` composition behind the
execution routes and the disposable-host boot proof — so the box stays unticked.

**Why the publication half cannot complete yet.** `stop_view` has no `CellTermination` adapter, so it
returns `terminal: false` after really closing and draining; `seal` then refuses `TERMINALITY_UNKNOWN`.
That is the truthful consequence of the missing kernel observation, not a gap in the composition, and it
is why a `CellTermination` manufactured out of `CellBackend.episode_container` was deliberately **not**
written: "the container is gone" is not "its cgroup is empty".

**Evidence.** `tests/test_execution_service.py` 21 passed (C0 table/config/digest; C3 real socket + real
codec + real authority); owning bank 556 passed; wider `-k "execution or workspace"` 1563 passed, 1
skipped (3 known offline-install errors elsewhere); ruff/format clean, mypy 21 files, pyrefly 0,
`fa authoring-check` 0. 9/9 assertion-only mutants killed with byte-exact restore. `I03-LIVE-26` is
PLANNED / UNEXECUTED; no STEP box, contract or live verdict is ticked.

### E278 result — CT104's join: `CellTermination` over journal-owned cells + kernel `populated 0`

**What shipped.** `src/fa/execution/cgroup.py` (pure cgroup-v2 reader: both driver layouts, `O_NOFOLLOW`,
regular-file check, 64 KiB bound, exactly one `populated <int>` line; `True` only for `0`, `None` otherwise) and
`src/fa/execution/termination.py::OwnedCellTermination`, the `CellTermination` that `ViewStopper` was written for:
cells come from `OperationJournal.owned_cells()` filtered to the exact namespace and `ViewRef`, the stop goes
through `DockerCells.force_stop_operation` with the record's own operation id, and emptiness comes from the
cgroup. The composed service now always installs it: without Docker it can still prove a never-executed view
empty (a journal fact), and with Docker (`ServiceConfig` gained all-or-none daemon facts, `cgroup_root`,
`startup_timeout_ms`) it builds `CellBackend`, reconciles surviving owned cells before binding the socket, and
closes the backend on shutdown.

**Current vs target behaviour.** Current: `stop_view` reaches `TERMINAL` for views that never bound a cell, and
refuses (`BACKEND_UNAVAILABLE`) for one it cannot stop; `seal`, `publish`, `prepare_bundle`, `install_project`
and `release` are therefore reachable through the closed codec, proved end-to-end on real files. Target: the same
flow with a *real* worker/attach cell and a real cgroup — that is `tests/integration/test_publication_recovery.py`
under `FA_REQUIRE_EXECUTION_HOST=1`, still BLOCKED here. STEP1 stays open (Q74's per-stage checkpoint policy, the
host rows, and the exec half's receipt issuer), so no box is ticked.

**Why a view with a cell is still not sealed locally.** The stop leg is doubled at the `DockerCells` seam in the
local bank (C1); only a host run may claim the daemon actually signalled the cell and that its cgroup emptied.
`cells_terminal` returns `None` for any unreadable fact, so an unproved cell keeps the view `STOPPING` and owned.

**Evidence.** `tests/test_execution_termination.py` 20 passed; `tests/test_execution_service.py` 24 passed
(the publication half now driven through the wire); owning bank 387 passed; wider `-k "execution or workspace"`
1585 passed, 1 skipped; ruff/format clean, mypy 22 files, pyrefly 0, `fa authoring-check` 0; 14/14 assertion-only
mutants killed with byte-exact restore. `I03-LIVE-19/20/25/26` remain PLANNED / UNEXECUTED.

### E279 result — `ExecutionReceipt` v1: `exec`, `inspect` and `cancel` over observed facts

**What shipped.** `src/fa/execution/receipts.py::CommandReceipts` (plus `bounded_tail`) and
`WorkspaceAuthority.execution_identity`; `CommandOutcome.duration_ms` (RUN send → reply, measured in the backend);
`service.py` composes the issuer when the four Docker facts are configured and keeps a closed
`BACKEND_UNAVAILABLE` otherwise. A receipt's identity is the reserved record, the view record (input tree and
plan digest) and the approved profile; its facts are one owned `inspect_owned` plus the kernel's `populated 0`.

**Current vs target behaviour.** Current: a one-shot command is `EXITED` only when the daemon's exit agrees with
the command's *and* the cgroup is proved empty; an interactive shell may report `EXITED` with
`terminal_barrier: false` (the barrier is `stop_view`'s question); a timeout is `TIMED_OUT` with no exit code and
no daemon contact; `inspect` replays a DONE record verbatim and never sends a RUN; `cancel` is intent → stop →
`CANCELLED` under its own operation id. Target: the same facts against a real container and a real cgroup — the
host rows (`I03-LIVE-19/20/25/26`), still BLOCKED here. STEP1 stays open, so no box is ticked.

**Why the local bank cannot promote a row.** Every daemon answer in the bank is a literal HTTP reply queued on a
real AF_UNIX peer, and the cgroup is a real directory holding a hand-written `cgroup.events`; the container's
exit, the SIGKILL and the kernel's emptiness are *not* observed. The receipt is proven to be closed, bound and
internally consistent — not proven to be true of a live host.

**Evidence.** `tests/test_execution_receipts.py` 21 passed; `tests/test_execution_service.py` 25 passed; all
`tests/test_execution_*.py` 1157 passed; wider `-k "execution or workspace"` 1608 passed, 1 skipped (3 known
offline-install errors); ruff/format clean, mypy 23 files, pyrefly 0, `fa authoring-check` 0; 14/14
assertion-only mutants killed with byte-exact restore.

### E280 result — `pty_control` P1–P9: the last execution route

**What shipped.** `CellBackend.pty_control` (grant proof through `WorkspaceAuthority.authorize`, episode identity,
at most two bounded control frames, no cell creation and no journal write) and the `service.py` route through the
composed backend. One transport fix was required by the two-frame exchange: `WorkerClient._read`'s retirement gate
was id-keyed, so a sequential id reuse deadlocked until the deadline; it is now keyed on the exchange object.

**Current vs target behaviour.** Current: `LIST` answers the worker's own listing, `INTERRUPT` answers the listing
plus the ACK message while the shell and cell survive, `CLOSE` drops that session and a later command recreates it
on the same cell; an absent session is refused (`EXECUTION_UNKNOWN`) **without writing the frame**, so a caller
typo cannot poison the live shell; a view with no live episode is `EXECUTION_UNKNOWN`, never an empty listing; a
noninteractive profile is `INPUT_POLICY`. Target: the same against a real container and a real kernel barrier —
`I03-LIVE-19/20/25/26`, still BLOCKED here.

**Evidence.** `tests/test_execution_pty_control.py` 10 passed; `tests/test_execution_service.py` 26 passed; all
`tests/test_execution_*.py` 1168 passed; wider `-k "execution or workspace"` 1619 passed, 1 skipped (3 known
offline-install errors); ruff/format clean, mypy 23 files, pyrefly 0, `fa authoring-check` 0; 9/9 assertion-only
mutants killed with byte-exact restore.

### E281 — remaining-I03 assessment before SLICE6: what is missing, in what order (no implementation claim)

**Question this answers.** With Q85 open, the operator asked what still stands between `8106709` and the
last acceptance slice (SLICE6), and in what dependency order the remainder should be taken.

**Method.** Every claim below is a source check at `8106709` (the grep or the function named), plus the
plan's own derived counts re-run instead of copied. **No test was executed for this entry** — the sandbox
lost its 3.13 interpreter between sessions (see "Toolchain" below) — and the only edits are documentation,
so no bank result changed. Counts re-derived here: 24 CTs, 17 `kill:` directives, 19 operations, 35 STEPs,
**26** E2E surfaces / 8 joins.

**What is live.** Route table + socket owner + `main` (`supervisor.py`, E277); 17 of the 19 operations
dispatch to a real owner; registration/R0/writer generation, five view purposes, rooted IO, seal,
publication, bundle/install, Q58 plan replacement and forward recovery (`workspace.py`,
`publication.py`); episodes, receipts and PTY control (`backend.py`, `receipts.py`); the barrier over
journal-owned cells plus the kernel's `populated 0` (`termination.py`, `cgroup.py`).

**What is provably not live.** `grep -rn "from fa.execution" src/fa --include=*.py | grep -v ^src/fa/execution/`
is **empty**. Nothing outside the package imports it, so every managed owner above is dormant and users
still execute the host path: `cli._cmd_run` builds a host `PtyPool` and degrades to `subprocess`.

#### A. Product work still missing (no host needed)

*(Rows A1 and A2 are superseded: A1 by E284 — `execution/checkpoints.py` is the Q74/§6.1 policy owner and `tests/test_stage_checkpoints.py` its bank, with the stage-loop call site (CT97) moving to A5 — and A2 by E282: Q85 is answered and `handoff` is now planned surface — CT113 / SLICE2 STEP6. Rows A3–A9 remain as written, each already owning a contract, step and bank; see E282 for the two surfaces that were missing one.)*

| # | Unit (plan row) | What is absent, source-checked | Blocked by |
| --- | --- | --- | --- |
| A1 | Q74 per-stage/episode checkpoint policy wired to spec §6.1's transition table (SLICE3 STEP1a) | `grep -rn checkpoint src/fa/execution` is empty; the view state machine exists without a checkpoint owner | nothing |
| A2 | `handoff` route (SLICE1 STEP3) | `service.py::_handoff` is a `BACKEND_UNAVAILABLE` stub; `WorkspaceAuthority` has no `handoff` | **Q85** |
| A3 | CANDIDATE `publish` (Q58) + the controller leg (SLICE3 STEP3 rest) | `publication.publish_plan` has **no caller outside tests**; the wire `publish` payload is `{sealed_manifest_id, expected_base_revision}` (`protocol.py:126`) and `prepare_publish` requires a SEALED view with a closed gate and a terminal record, so a CANDIDATE view cannot travel that route at all; `workflow_controller._promote_validated_plan` (`:2279`) still writes the canonical plan through `plan_promotion.publish_plan_buffer` — the second writer R3 forbids | the controller half needs the client composition (A5) |
| A4 | inventory completion (SLICE4 STEP1) | `notes/i03-execution-call-inventory.md` still says "State: OPEN"; no exact new source lines, caller traces or test nodeids | nothing |
| A5 | caller cutover (SLICE2 STEP4 wiring + SLICE4 STEP2) — the largest unit | `run_stage_with_plan_write_boundary` **does not exist anywhere in `src/`** (CT97's named producer); `workspace_io=` and `workspace_provisioner=` have no `src/` call site; `cli._prepare_managed_workspace` prints a warning and continues; `_init_live_pty_pool` returns `None` on any failure and the bash tool falls back to `subprocess`; the controller read-only mounts / private-UDS-only entrypoint are not switched | A3 (supervisor half) and A4 |
| A6 | managed verification (SLICE4 STEP3) | `slice_verification._run_one` still spawns a host subprocess; `_run_managed_command` does not exist | A5 |
| A7 | managed acquisition (SLICE5 STEP1–3) | `tests/test_managed_acquisition.py` and the spec §7 v2 fixtures do not exist | STEP2 on **Q85**; STEP3 on A3 |
| A8 | the SLICE6 package itself | no `e2e/` directory, no `scripts/check_execution_e2e_coverage.py`, no `tests/test_e2e_artifact_contract.py`; markers `execution_host`/`live_e2e` are **not registered** while `--strict-markers` is on (`-m` merely deselects today, but the first decorator use is an error) | A1–A7 |
| A9 | the test files the verify fences name | `tests/integration/` does not exist at all (five fences name it: boundary, workspace_views, publication_recovery, execution_closure, nested_workflow), plus `test_managed_workspace.py`, `test_execution_project_tools.py`, `test_managed_acquisition.py`, `test_e2e_artifact_contract.py` — those fences currently exit 4, not 0 | the units above |

#### B. Host/operator prerequisites (cannot be produced in this session)

Approved Docker daemon + image built from `Dockerfile.fa` with a recorded digest; an installed-controller
wheel from a CPython 3.13 that has `zlib` (and `sqlite3`/`ssl` for the controller itself); the approved
ShellCheck binary (12 parametrised `shellcheck` cases skip without it); Go 1.24.11 plus the pinned
Gitleaks/pre-commit dependencies for `just test` / `just check`; real provider credentials for the spec
§9.1 direct+nested witnesses; `CAP_SYS_PTRACE` if the `strace` oracles are used; a readable cgroup v2.
Every `FA_REQUIRE_EXECUTION_HOST=1` row (27 surfaces after `I03-LIVE-27`, 8 joins) is `PLANNED / UNEXECUTED` until then.

#### C. Dependency order for the remainder

1. **A1** — Q74 checkpoints. Unblocked, and the stage loop, the seal and the verifier's evidence all read
   them, so it goes first among equals. **Shipped as policy + bank in E284**; its call site is A5.
2. **A4** — inventory completion. It is the checklist the cutover must close; doing the cutover first
   leaves it without a closure test.
3. **A3 (supervisor half)** — CANDIDATE `publish` over the wire. Must precede A5: R3 requires the host
   plan writer to be deleted in the same change that activates the managed one.
4. **A5** — the cutover, including A3's controller half and the deletion of `publish_plan_buffer`.
5. **A6** — the managed verifier adapter; it needs the managed operation client A5 composes.
6. **A7** — acquisition: STEP1 fixtures can start earlier, but STEP2's handler and handoff leg wait on
   **Q85**, and STEP3's bundle selection needs A3's publish leg.
7. **A8** — SLICE6 STEP1/2/3/6 (contract, indexes, coverage snapshot, skills). The coverage snapshot
   must be taken after the last register row exists, i.e. after A3/A5/A6/A7 add theirs.
8. **SLICE6 STEP7 → STEP8 → STEP9 → STEP10** — independent review before any fixture/helper is written,
   index mapping after the fixtures, and the release/host gates last. Every host row is last of all.

**While Q85 is open** the unblocked, non-overlapping units are A1, A4 and A3's supervisor half. Everything
else either needs the cutover (A5) or the Q85 decision (A2, A7 STEP2). This was the dependency state at
E281, not the current state.

#### Current dependency-order addendum (E287, 2026-10-30) — Q85 resolved; Q89 blocks A3 → A5

This dated addendum supersedes E281's current-status statements wherever they describe Q85 as open or
A7 STEP2 as blocked by Q85. E281 remains an intact historical assessment; its other source findings and
ordering constraints are not erased.

- **Q85 / A2:** resolved by E282; CT113 and SLICE2 STEP6's authority body and service route landed in
  E283 with local proof. The old A2 authority gap is closed. The **controller leg is not**: SLICE5 STEP2
  still has no `HANDOFF` caller, parent-mutation suspension/drain, or child-dispatch-after-ack path.
- **A1 / A4:** A1's checkpoint policy and bank landed in E284; its controller call site remains A5.
  A4's source-grounded inventory closed in E285. These facts do not close the enclosing STEPs.
- **A3 → A5:** A3 remains blocked by unresolved Q89 (the CANDIDATE `publish` wire choice); do not
  select a wire shape or implement that route. A5 cannot start before A3 and A4; it owns the controller
  composition/cutover and must delete `publish_plan_buffer` in the same change that activates the managed
  writer. A6 depends on A5. SLICE5 STEP2 depends on SLICE4/A5 and must not be implemented ahead of that
  composition. Q85 itself is no longer a blocker, but it does not remove these dependencies.
- **Q85 controller handoff seam:** `ExecutionClient.request` exists and is one-shot, but no controller
  call sends `Operation.HANDOFF`; `workflow_tool.handler` currently refuses acquisition-dependent
  nested roles before child dispatch. When SLICE5 STEP2 becomes dependency-ready, it must drain/suspend
  parent mutators, settle every WRITE view with no `intent.json`, allocate exactly once via
  `_child_run_context`/`SessionManager.begin_run`, send the existing HANDOFF operation with the exact
  controller-attested `target_namespace`, and dispatch only after the server returns the new grant.
  Transport uncertainty must not cause a resend or child dispatch. No new operation, supervisor-side
  session attester/read, second allocator, or second `begin_run` is allowed.
- **Ready documentation work:** SLICE6 STEP4 may now record the already-existing CT113 source/local
  proof as a coder handoff, explicitly separating it from the unimplemented SLICE5 controller leg.
  SLICE6 STEP6's transferred skill obligations are documentation-only and do not alter producer
  coverage, so they may be completed independently; preserve the existing generic `DRAFT | READY |
  BLOCKED` semantics. Neither task changes the E2E oracle or assigns a live result.
- **Still gated:** SLICE6 STEP5 requires actual deployment/workspace facts and remains unavailable here.
  STEP7 independent manual review still precedes any STEP8 fixture/helper implementation. The I03-LIVE-27
  row and L-HAND-1/2 oracle stay unchanged and **NOT RUN**; the integrated controller/outer-chat witness
  remains the planned I03-LIVE-S08 join. Do not tick any STEP/CT or promote any live case from this work.

The current next product implementation is A3, but it is intentionally stopped at Q89. After the
independent documentation work above, wait for the operator's Q89 decision rather than bypassing A3/A5.

#### Two plan-text defects found and fixed here

1. The increment's derived-count row read **25 surfaces** while `grep -o 'I03-LIVE-[0-9]\{2\}'` returns
   **26**: E277 added `I03-LIVE-26` for the composed supervisor and the row was not updated. Corrected,
   with the adding entry named in the row, as the section's own rule requires.
2. `I03-LIVE-26`'s description still called `exec`, `inspect`, `cancel` and `pty_control` dormant
   ("thirteen over real owners, six declared `BACKEND_UNAVAILABLE`") and said `seal` "refuses
   `TERMINALITY_UNKNOWN` until the cgroup observer exists". E279/E280 routed those four operations and
   E278 built `OwnedCellTermination`. The row now describes the real split (seventeen live, `handoff` and
   `register{create:true}` dormant) and states the barrier's honest limit: unproved on a host, so a view
   whose cell cannot be stopped stays `STOPPING`. The row's status stays `PLANNED / UNEXECUTED`.

#### Toolchain (recorded so the next session does not repeat it)

`notes/sandbox-venv.sh` builds a 3.11 venv; since E276 the banks use PEP 695 generics
(`tests/test_execution_workspace.py:36 def ok[T]`), so `pytest tests/test_execution_*.py` aborts at
collection there and `fa authoring-check` reports four test files `UNPARSABLE`. A from-source 3.13 build in
this sandbox needs `zlib`, `sqlite3`, `ssl` and `ctypes`, and the image has **no development headers**
(`/usr/include` has no `zlib.h`, `sqlite3.h`, `openssl/`, `ffi.h`) and no root, so each has to be built
from source. This entry's own edits are documentation only; they were checked with what the 3.11 venv can
parse (authoring-check went from 4 to 4 `HARD-BLOCK` lines, all of them the pre-existing PEP 695 test
files, with no worklog diagnostic added), and no bank was run or claimed.

**Not done, deliberately.** No STEP or CT box ticked, no live row promoted, no `handoff` guess, and no
implementation started in this entry.

### E282 — Q85 ruled; the remaining audit promoted into planned surface (documentation only)

**What this entry is.** The operator resolved Q85 after review with the agent working the E2E slice, and
asked that the E281 remaining-surface audit stop being prose and become planned surface with a contract,
exit criteria, owning bank and register row like every other unit. No code changed; two plan facts were
promoted and one stale progress note repaired.

**The ruling, recorded so it is not re-litigated.** The source of truth for the parent-child link is
`_child_run_context`: it proves the parent `RunContext`/`SessionContext`/workspace bindings agree and
allocates the child run through the existing `begin_run` **in the same session**, so `parent_run_id` is
controller-attested after an actual allocation (spec §7.1). The supervisor therefore gains **no** session
store, **no** attester module, **no** `ServiceConfig` field and **no** new operation or payload:
`WorkspaceAuthority.handoff` proves ownership, settlement and the two wire invariants, then performs one
**generation-preserving** metadata replace. The round-1 alternative — a narrow read-only attester injected
into the service — is rejected: it inverts the E263 session→execution dependency, adds an `FA_STATE_ROOT`
mount contract plus filesystem IO on the hot path, and buys no boundary the controller cannot already cross,
because a compromised controller can already `exec` as the owner.

**Why it is sound, checked against source at `0619ecd`.** The wire already carries the shape and the
dispatch already carries the semantics, so this is one authority body and one route: `Operation.HANDOFF`
decodes `{target_namespace}` into `_OWNER_REPLY` (`protocol.py:135`/`:151`), whose `capability` is a 64-hex
`SHA`, exactly what `secrets.token_hex(32)` produces; `HANDOFF` is in `AUTHORITY_GATED_OPERATIONS` and is not
readonly, so it cannot skip the authority check and it reserves `op-<request_id>`; `_execute_reserved` already
treats it as a `GrantReply` operation; `_owner_only` matches the stored grant with `hmac.compare_digest`
**and** the full active-actor dict, so replacing grant and `active_actor` revokes the old capability exactly;
Q75 replay compares the presented proof to the *original* proof recorded with the cached reply
(`_authorize_replay`), so a revoked proof still retrieves only its own bound reply and cannot admit fresh work;
`_settle_owner` already spells the settlement predicate (`_has_unsettled_views` + `intent.json`); and
`owner_namespace` is only nullity-checked, so keeping it while `active_actor` moves is coherent. The
attestation is also visibly real rather than decorative: `RunContext` has **no** `parent_run_id` field, so the
controller must supply it — the supervisor could not invent it even if it wanted to.

**Four details the ruling left implicit, settled in the plan text rather than guessed in code.** (1) The
preconditions have a fixed **order** — ownership, then settlement, then the writer fd, then the wire
invariants — so a refusal is deterministic and testable. (2) Settlement must reuse `_settle_owner`'s predicate,
**not** `_forward_gates`: the latter also probes writability and recomputes the canonical tree hash, which are
commit preconditions and would refuse a legitimate handoff. (3) The swap requires the live writer fd this
process opened (`binding.writer is not None`, else `STALE_GENERATION`) so the authority never moves an ownership
it cannot fence. (4) The crash window is stated: after the metadata replace and before the reply, the workspace
is `OWNED` by a namespace whose capability nobody holds — restart quarantines it exactly as for `acquire_writer`,
and the attempt is never reconstructed from the journal. The plan text also names what the attestation does
**not** prove and bounds it: a controller that names a nonexistent child run can only strand its own grant until
release/restart — self-inflicted denial of service, never escalation.

**Plan changes made here.** (a) spec §2.1's `handoff` row now carries the full rule set (order, settlement,
generation-preserving swap, capability rotation, replay), and §7.1 states the attestation chain and its bound.
(b) The increment gains **CT113 [FUNCTIONAL]** with `kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.handoff -> _handoff_owner`,
a new **SLICE2 STEP6** carrying the exit criteria and its owning bank `tests/test_execution_handoff.py`, and
that file is added to SLICE2's `TESTS:` line and both verify fences. (c) SLICE1 STEP3 records 18/19 routes and
names STEP6 as the owner of the nineteenth. (d) SLICE5 STEP2 is split explicitly: the authority and route land
in STEP6, this step keeps only the controller half (suspend the parent, `_child_run_context`, build
`target_namespace`, send the RPC, then dispatch the child). (e) **A stale progress note is repaired**: SLICE3
STEP1 still listed `CellTermination` ("part (b)") as outstanding although E278 delivered it, and part (a) —
Q74/§6.1 — is now spelled out as a full obligation with `tests/test_stage_checkpoints.py` and an explicit
statement of why it declares no new CT (its durable effects are CT106/CT107a, its barrier is CT104, and its
sidecar is CT110/CT111's artifact). (f) Counts re-derived, never hand-typed: CT **25** (18 FUNCTIONAL + 7
CONSTRAINT), `kill:` **18**, STEPs **36**, surfaces **27** / joins **8**.

**One deviation from the ruling's wording, recorded deliberately.** The recommendation says "implement in
SLICE2 STEP2"; the unit is recorded as **STEP6** instead. STEP2's exit criteria are the five view purposes — a
different producer and bank — and CT113 needs its own settlement/replay matrix, so folding it in would reopen a
step with nothing else outstanding. The slice, the contract and the sequencing (before SLICE4, before SLICE5
STEP2) are exactly as ruled; only the step number differs, and the step says so in its first sentence.

**Not done, and not claimed.** No code, no bank run (the sandbox has no usable 3.13 interpreter this session —
see E281's toolchain note), no STEP or CT ticked, no register row promoted. `handoff` still refuses
`BACKEND_UNAVAILABLE` on the wire until SLICE2 STEP6 lands. Of the nine units in E281's table,
`handoff` was the only one without a planned surface; the rest already had contract, step, exit criteria and
owning bank, which is what this entry checked before adding anything.


### E287 — Q89 resolved: CANDIDATE `publish` wire and controller cutover plan (2026-10-30)

**Decision.** The operator selected Q89 option 1 with R1–R6. This is a plan/contract update before
implementation; no STEP/CT checkbox or live verdict is inferred. It activates the already-planned
SLICE3 STEP3 CANDIDATE `publish` on the existing `Operation.PUBLISH`, after E276 recovery and E277–E280
service/route dependencies. It does not add an operation, route table, journal, idempotency scheme, or
caller-controlled plan destination.

**Source-verified seams and gap.** E273's authority PLAN commit is already implemented, including the
existing I02 `_decode_plan_bytes` validation and forward-only same-path replace/revision/pointer core.
`protocol.py` currently requires a seal ID for every PUBLISH and reuses `_COMMITTED` for install;
`service.py::_publish` dispatches only `publish_view`; `WorkspaceAuthority._reader_proof` rejects a
closed reader pin; the private candidate buffer is exposed only by direct `write_candidate`/
`read_candidate` methods and is not reached by the existing file routes; `_plan_prepare` currently
hashes a synthesized plan operation ID into the PLAN manifest; and `_promote_validated_plan` still calls
the host-path `publish_plan_buffer`. The latter path is a second writer and must disappear in the same
cutover.

**Implementation dependency order and contracts.**

1. Make `PUBLISH.sealed_manifest_id` nullable exactly for CANDIDATE `view_ref`; keep the ordinary
   sealed WRITE path and its checks unchanged. Add a PUBLISH-only reply schema with nullable `plan_ref`;
   install continues to use the exact existing `_COMMITTED` shape (R3).
2. Route existing `WRITE_FILE` (and the scoped `READ_FILE` buffer path) for CANDIDATE views through
   the supervisor's exact-scope candidate methods. The authority remains the only private-buffer owner;
   no path/buffer is added to the payload (Q89 gap closure, E259).
3. Add the candidate PLAN authority transaction: authenticate the view grant with closed-view-tolerant
   proof (R1/R2), verify workspace `OWNED`, `active_actor == namespace`, generation and current-base
   equality (R2/R6), require closed gate + drained active work + exact matching `terminal.json` (R5),
   then read bytes directly from the private candidate file. Reuse the E273 PLAN validators and
   irreversible commit/recovery core; require `op-<request_id>` in its intent and reply (R4). Do not
   replace the view proof with OWNER grant. Keep ordinary sealed WRITE publication behavior unchanged.
4. Cut `_promote_validated_plan` over to the existing client/service PUBLISH request and delete
   `plan_promotion.publish_plan_buffer`; no fallback or parallel writer survives (R3/R5 cutover).

**Acceptance / negative proof.** Add schema cross-field tests; ordinary-vs-candidate service routing and
exact reply-shape tests; authority tests for wrong capability/namespace/status/actor/generation/base,
open gate, active work, missing or mismatched terminal receipt, absent/wrong-scope buffer, invalid plan,
stale canonical plan, and forward-only durability faults. Prove `record_terminal` without drain cannot
publish. Prove request ID reaches PLAN intent/reply and changes `_derive_revision_id` output; exact replay
is checked at the supervisor journal, not by a content hash. Assert ordinary sealed publication remains
unchanged and install still validates against `_COMMITTED` without `plan_ref`. Controller tests must
fail if `publish_plan_buffer` is reintroduced or called. Run owning protocol/service/workspace and
plan-promotion tests, relevant static checks, and targeted mutation checks; inspect the complete diff.

**Ordering/ownership caveats.** CT107 recovery remains the owner for interrupted PLAN intents; do not
claim a new recovery mechanism here. I03-LIVE-23 remains `PLANNED / NOT RUN` and its current host row
still names a direct OWNER-grant path. This coding slice does not edit the frozen E2E baseline or
planner-owned host oracle; the planner must reconcile that invocation contract before STEP8 fixtures or
any live run. All live E2E remains deferred until I01–I03 are merged to `main` and deployed, with operator
host evidence required before joint evaluation.

**Plan-only status at E287.** E287 was a planning snapshot; the implementation and executed evidence below supersede its “not done” statement. The host-run, fixture/helper, STEP tick and CT closure prohibitions remain in force.


### E288 — Q89 option 1 implementation and bounded proof (2026-10-30)

**Implemented contract.** The existing PUBLISH wire now permits a null seal only for a CANDIDATE view; PUBLISH has its own closed result schema with nullable `plan_ref`, and install retains `_COMMITTED`. The service routes exact CANDIDATE `READ_FILE`/`WRITE_FILE` scope to the private candidate buffer. `WorkspaceAuthority.publish_candidate_plan` authenticates the closed view capability, checks OWNED/active actor/generation/current-base equality, requires closed gate + drained work + exact terminal record, reads the private buffer inside the transaction, applies the I02 PLAN validator, and enters the existing forward-only PLAN commit. The dispatcher `op-<request_id>` enters the PLAN intent/reply and revision derivation. Ordinary sealed WRITE publication remains separate. `plan_promotion.publish_plan_buffer` is deleted.

**Controller/client boundary.** `ExecutionClientPlanPublisher` stages through CREATE_VIEW → WRITE_FILE → STOP_VIEW → PUBLISH, retains the view on uncertain outcomes, and advances its base CAS after a confirmed publish for later repair/replan attempts. `run_workflow` and `WorkflowContext` expose the injected publisher port. No production managed-session composition supplies the trusted client, namespace, workspace, OWNER capability and current revision yet; absence of injection fails closed with an existing admission rule and never falls back to a host writer. Controller integration tests use a test-only port; it is not a production authority. This separate composition blocker is Q90. Thus Q89's contract/component cutover is implemented, but this does not close SLICE3 STEP3 or activate SLICE4.

**Executed evidence.**

- `.venv/bin/pytest tests/test_execution_protocol.py tests/test_execution_service.py -q` — **112 passed**.
- `.venv/bin/pytest tests/test_workspace_publication.py tests/test_workspace_recovery.py tests/test_execution_purposes.py -q` — **135 passed**.
- `PATH="$PWD/.venv/bin:$PATH" .venv/bin/pytest tests/test_verify_gate_live.py -q` — **572 passed**. The PATH addition is required because nested verification children invoke `python -m pytest`.
- Ruff check passed; Ruff format check reported **12 files already formatted**; Mypy reported **Success: no issues found in 7 source files**; compileall and `git diff --check` passed.
- Two temporary, restored source mutants were caught by their named oracles: removing the R6 current-base comparison made a candidate publish after an unrelated revision commit; replacing the dispatched operation ID in the PLAN manifest broke the revision-ID derivation assertion. No mutation was left in the worktree.

An initial full verify-bank run without the venv on `PATH` had nested child failures (`/usr/bin/python: No module named pytest`); rerunning with the venv on `PATH` exposed one test-double mismatch at the post-replace fsync boundary, which was corrected. The final full bank is the 572-pass result above.

**Not claimed.** No live host run, E2E fixture/helper, I03-LIVE-23 baseline/oracle edit, STEP tick, CT closure, merge/deploy, or production readiness is claimed. The planner must reconcile I03-LIVE-23's old OWNER-grant oracle with the candidate-view route before any later host run.

## E290 — SLICE7 re-review against the committed text (2026-10-31, code at `2fa8d30`)

The §14 review in `notes/Q90-defect-group-closure-2026-10-31.md` judged the **draft** `d31222f`. This
entry re-reads what actually landed, contract by contract and step by step, against the code. Nine
findings: seven were plan defects and are fixed in place above; two are checks that stand.

**R1 [confirmed, fixed] — a step reference survived renumbering.** STEP3 said retention writes to
`.fa/admission/<run_id>/` "until STEP9 renames the namespace", but STEP9 is the client workspace
provisioner and the rename is STEP10. Draft numbering leaked into the committed text; the reference is
now STEP10.

**R2 [confirmed, fixed] — CT119 presented a new rule as existing behaviour, and it collided with the
primitive it reused.** The live draft names are `candidate-<uuid4().hex>.md`
(`plan_promotion.py:71`, `client.py:194`), so "the name is the content hash" is introduced by this
contract, not observed. Worse, the reused `_create_candidate` opens `O_EXCL` (`plan_promotion.py:85`),
so a second retention of the same bytes would have raised `FileExistsError` — the contract promised
idempotency and the step promised reuse of create-or-fail. Fixed: content-hash naming is named as this
contract's rule, `O_EXCL` is read as *create-or-confirm* (bytes compared; only an equal file is a
no-op), and the test matrix now includes "same bytes twice → one file, no error" and "different bytes
twice → two files, no eviction".

**R3 [confirmed, fixed] — the retention helper would have closed an import cycle.**
`plan_promotion.py:18` already imports `_private_artifact_directory` from `workflow_artifacts.py`
(`:566`), so putting `retain_plan_draft` there while importing `_create_candidate` back from the draft
module is a cycle. **Superseded by the 2026-11-01 reduction:** nothing moves and nothing is renamed —
`retain_plan_draft` lives in `plan_promotion.py` beside `_create_candidate` (`:81`), the module that already
owns the write primitive, so the cycle never exists. STEP3's exit states the import check explicitly.

**R7 [confirmed, fixed] — STEP7 never said which base revision PUBLISH carries.** The wire compares the payload's
`expected_base_revision` with the **view's** base (`protocol.py:334`), and the view's base is whatever revision was
current when `create_view` ran (`workspace.py:1684-1691`; the optional parameter is a precondition, not a pin).
The adapter STEP7 replaces sends its own cached `_base_revision` (`client.py:265`), initialised at construction and
updated only after a successful publish — so a commit by anyone else in the same workspace between two repair
attempts makes the two disagree and the publish is refused as `INVALID_REQUEST`, which reads as a protocol bug
rather than a stale-cache bug. STEP7 now names the CREATE_VIEW reply (`view.base_revision`) as the only source.

**R8 [confirmed, fixed] — CT117 relaxed a wire field that does not need relaxing.** The plan made
`PUBLISH.expected_base_revision` nullable "for a candidate publish", but the candidate publish's CAS is
compared with the **view's** base (`protocol.py:334`), and `create_view` always stores the revision
current at creation as the view base (`workspace.py:1684-1691`). A client that sends the base it was
handed in the CREATE_VIEW reply can therefore always satisfy it — nullability would only license a
payload that proves nothing, and the cross-field rule for it would be dead code. Removed: the field
stays required, and only `CREATE_VIEW.base_revision` becomes nullable. This also keeps the change
surface to two refusal rules plus `already_published`.

**R4 [confirmed, fixed] — STEP4 and STEP9 added required keys to closed reply schemas without naming
the migration decision.** `journal._validate_record` re-checks every stored `DONE` against the
*current* `protocol.RESULTS` (`journal.py:130-131`), each reply is a closed `_object` (all keys
required, `additionalProperties: False`, `protocol.py:25-26`), and one mismatch becomes
`CORRUPT_STATE` in `_read` (`journal.py:222-235`), on the start-up path
`WorkspaceAuthority.__enter__` → `recover_uncertain` (`workspace.py:965`). Both `already_published`
(STEP4) and `tree_sha256` (STEP9) are therefore journal-visible: adding them as bare required keys
bricks a sandbox whose journal predates the change. The steps now name Q93 (schema version on the
record, or a named tolerance for the missing key) and require a seeded pre-change record to be read
back.

**R9 [confirmed, fixed] — STEP9 planned a wire change the spec forbids and nothing needs.** The register
reply is fixed at `{workspace_id, revision_id}` (`notes/i03-execution-workspace-spec-2026-10-15.md:153`;
`service.py:591` matches it). The only thing asking for a third field was `ProvisionedWorkspace.__post_init__`'s
own rule (`session/provisioning.py:53-59`), and nothing in `src/` reads `ProvisionedWorkspace.tree_sha256`.
Adding it would have been a second journal-visible schema change of R4's class, bought for a value no consumer
reads. STEP9 now builds the port on the two-field reply and relaxes the local rule; a later readiness oracle
that wants the tree hash takes it from an operation that already returns one (`SEAL`, `INSTALL_PROJECT`) or
from `PIN_READER`'s revision, with its own Q93 decision.

**R5 [checked, stands] — the CT115 guard is executable where it is placed.** The only path to
`state.planner_calls += 1` (`workflow_controller.py:2558`) besides an explicit replan is the
`RETRY`/`BLOCKED` tail of the loop, `_run_admission_repair` (`:2559`) is the only caller of
`run_stage_fn`, and `_admit_plan`'s `except (PlanRefError, PlanPromotionError, PlannerDispatchError)`
(`:2570`) routes the refusal through `_admission_blocked` (`:2465-2480`) as
`promotion/managed-execution-absent` with the attempt's `candidate_sha256`. So "the stage was never
dispatched" is a real assertion, and CT119's findability claim needs no schema field. `run_workflow`
already accepts `plan_publisher` (`:2657`), so STEP8 wires an existing parameter rather than inventing
one.

**R6 [checked, stands] — the wire and composition anchors are accurate.** `_PUBLISH_REPLY`
(`protocol.py:145`) currently carries exactly six keys; `read_config_file` is at `service.py:290`;
the `REGISTER_WORKSPACE` reply at `service.py:591` emits exactly `{workspace_id, revision_id}`;
`WorkspaceProvisioner` is `session/provisioning.py:66`; `ExecutionClientPlanPublisher` spans
`client.py:154-283` with `_release_candidate_best_effort` at `:283`; `DEFAULT_CONFIG_PATH` is
`config.py:44`; `_planner_target_allowed` refuses `.fa/admission` at `profiles.py:250-262`.

**Stale counters, fixed in the same pass.** Front matter said `slices: 6` and the planning-state
paragraph said "All35 construction steps"; the roadmap row for I03 still called it the "six-slice
plan", and I02's hand-off pointed at that same "six-slice" plan. Derived counts do not move:
33 CTs (23 FUNCTIONAL / 9 CONSTRAINT / 1 PRESERVATION), 23 `kill:` directives, 47 STEPs, 7 slices.

**Open, not closed here.** Q92 (the R6 base-pin revocation) is still absent from
`notes/open-questions-2026-10-07.md`, so CT117 remains in tension with the canonical Q89 until that
append-only entry exists; Q93 gates STEP4 and STEP9 as described in R4; Q91 has no canonical entry —
`load_capabilities` (`config.py:110-146`) reads only the `capabilities:` block, so STEP8's
`execution.service_config` needs a second reader or an extension of that contract, and the step says so.

**E290.1 — reduction pass and Q91 closure (2026-10-31, later the same day).** Operator direction: fewer
surfaces, YAGNI where it is worth it, key seams spelled out. Four changes, each verified against the code:
(i) CT118/STEP6 scoped down — the four reply-wrapping sites and a separate grants bank are gone; the
invariant (a stored grant is a `GrantReply`, never a `str` field) and one assertion in the existing client
bank remain. (ii) CT120/STEP10 scoped down — no module, function or directory renames; only
`candidate_scope.candidate_path` leaves the wire, because a rename moves no behaviour and touches every
importer. (iii) CT119/STEP3 — `retain_plan_draft` now lives in `plan_promotion.py` beside
`_create_candidate`, so the primitive does not move and no import cycle is created. (iv) CT116/STEP8 — the
endpoint is one string in `~/.fa/config.yaml` (`execution.service_config`), read by a sibling
`load_execution_config` that leaves `load_capabilities` untouched; `managed_execution_for_run` takes only
`run_context` and registers the workspace through the idempotent `register_workspace` route instead of a
threaded `ProvisionedWorkspace`.
R3's placement (primitive moved into `workflow_artifacts.py`) and the rename/directory half of CT120 are
superseded by this pass; R9 stands (it argued against putting `tree_sha256` on the wire, which is exactly
what remains true). §15.3/§15.4 of the Q90 note are amended to match.

**E290.2 — the sequencing blocker the final pass surfaced.** `_unchanged` (`workspace.py:1303-1310`) re-walks
`binding.source`, the **host** workspace tree, and fails closed when the digest disagrees with
`current.tree_sha256`, marking the authority unhealthy; `acquire_writer` (`:1329`) and `_plan_prepare`
(`:3535`) both call it. A managed publication is therefore sound only while the authority is the run's only
writer, and the workflow's coder stages still write host-side until SLICE4 STEP2's cutover. With the chosen
order (3 → 7 → 4) the consequence is bounded and now written down: the admission repair happens before any
coder stage and publishes; an `EVAL_REPLAN` publication follows a coder stage, by which time host bytes have
moved, and the authority refuses it. That refusal is the design working, not a defect to route around —
adopting drifted host bytes is what SLICE4 exists to remove. STEP11 pins it with
`test_a_host_side_write_before_the_second_publish_is_refused`, which fails on today's code and becomes
SLICE4's green test; SLICE7's INTENT states the limitation, so no reader can mistake one publication per run
for the whole behaviour.

**Extended at `d9b4cb4` (E292): the refusal is sticky, and it is reached by six call sites, not two.**
`_unchanged` sets `self._healthy = False` (`:1308`); `_check` (`:985-988`) raises `CORRUPT_STATE` while that flag
is false, and nothing turns it back on except `__enter__` (`:967`). A single host-side write therefore retires
the supervisor for the rest of the run — not one operation, every operation — which makes the sequencing limit
a run-ending one and makes SLICE4 STEP2's order non-negotiable rather than tidy. Current call sites of
`_unchanged`: `register_workspace`'s reuse branch (`:1211`), `acquire_writer` (`:1329`), the reader branch
(`:1674`), `create_view` (`:1953`, `:1994`) and `_forward_gates` (`:3797`, defined at `:3785`), which both
`publish_candidate_plan` (`:3441`) and `_plan_prepare` (`:3581`, defined at `:3567`) call. Line numbers above
were re-read at `d9b4cb4`; E291 shifted them, so the older `:3535`/`:3739` in this section refer to the same
calls.

## E290.3 — the operator's 2026-10-31 SLICE7 draft, reconciled with the plan and with the code

The draft arrived after SLICE7 had already been written from the same defect group and re-reviewed here
(`## E290`, `E290.1`). Reconciling it line by line was therefore not a rewrite but a check: which of its
claims are already the committed text, which are additions this plan lacked, and which name code that does
not exist. The third class is the reason this section exists at all — the draft is executable only in its
prose, not in its anchors.

| draft claim | what the repository actually has | disposition |
| --- | --- | --- |
| second config consumer: in-process `serve` with `SubprocessWorkspaceAuthority` (`cli.py:323`) | no `SubprocessWorkspaceAuthority` anywhere in `src/` (`grep -rn "Subprocess" src/fa` yields only `subprocess.SubprocessError`, `workflow_controller.py:861`, and a docstring, `slice_verification.py:14`); `cli.py` has no `serve` subcommand; the only server is `execution/service.py:457 serve_forever` behind `supervisor.main` (`supervisor.py:471 serve_connection`) | rejected — there is one reader (`load_execution_config` → `service.read_config_file`) and one server |
| atomic intent inside `_commit_bundle` (`workspace.py:1220`), `_intent`, `_recording` (`:1442`), `_plan_publish` (`:2190`) | none of those symbols exist; the real ones are `publish_candidate_plan` (`:3399`), `_plan_prepare` (`:3521`), `_plan_abort` (both `except` arms, `:3445` and `:3449`), `_read_intent` (`:4449`), `_write_intent` (`:4455`), `_clear_intent` (`:4469`), `_forward_gates` (`:3739`) | rejected as anchors, checked as behaviour: a failed attempt already aborts its intent, so the draft's "intent written then raise" hazard does not exist (CT117 now says so) |
| typed `Blocker(TOOL_DENIED)` as the refusal vocabulary | `TOOL_DENIED` does not occur in `src/`; `Blocker*` in `inner_loop/hooks/blockers.py:79+` is middleware policy, not admission coding; the real vocabulary is `ADMISSION_RULES["..."]` (`admission_schema.py:46-55`) | rejected — STEP2 already uses the real mechanism and its `managed-execution-absent` rule |
| `tests/test_workflow_admission_repair.py` | no such file; the repair round's bank is `tests/test_s8_workflow_controller.py` (`test_s8_repair_exhausted_maps_to_its_own_stop_reason`, `:292`) | adopted — STEP2 and STEP3 now name that bank instead of leaving the test file implied |
| `supervisor.py:60-84` as endpoint discovery | that range is `logger` (`:56`), `ReplyUnavailableError` (`:62`), `ReplayConflictError` (`:66`), `operation_input_sha256` (`:74`) — no discovery, and this plan adds none (no env var, no endpoint file, no autoscan) | rejected — nothing to change |
| `receipts.py:31-39` as the completion base class | those lines are imports (`cgroup`, `backend`, `docker`, `journal`, `profiles`, `supervisor`, `types`); completion validation is `_validate_completed_receipt` (`journal.py:134`) | rejected — no change; CT117's journal rule is the only schema-adjacent work |
| add the completion mark to the publish reply once | `_PUBLISH_REPLY` (`protocol.py:145-152`) already carries `workspace_id`, `revision_id`, `tree_sha256`, `operation_id`, `projection_complete`, `plan_ref` — the change is one boolean | adopted, already planned (CT117, STEP4) |
| the CAS must carry the base the CREATE_VIEW reply returned | `_VIEW_REPLY = {view_ref, capability}` (`:158`) and `VIEW` carries `base_revision` (`:56-64`) | adopted, already planned (STEP7) and now the stated rule |
| do not put the tree hash on the register reply | `register_existing` returns three keys (`:1213-1217`) but `service.py:591` masks the reply to two, matching the spec's table (`notes/i03-execution-workspace-spec-2026-10-15.md:153`) | adopted, already planned (STEP9 relaxes the local dataclass instead of the wire) |
| a retained plan draft beside the live candidate, no module move | `seed_plan_candidate` targets `.fa/admission/<run_id>/candidate-<uuid4().hex>.md` (`plan_promotion.py:71`) with `_create_candidate` (`:81`, `O_EXCL`); removal on failure is an inline `unlink` at `workflow_controller.py:2451`, not a named helper (`plan_promotion.py:66` is the tail of `seed_plan_candidate`) | adopted, already planned (CT119) |
| no-collapse rule: a unit is not done until a caller reaches it | this is the E288 class the slice exists for | adopted — STEP11 now names each helper and the bank that proves its reach |
| the host tree digest blocks a second publication | `_unchanged` (`:1303-1310`) compares the **whole** `binding.source` snapshot with `current.tree_sha256`, is called from `acquire_writer` (`:1329`) and through `_forward_gates` from `_plan_prepare` (`:3535`) | adopted this pass — E290.2, the INTENT limitation, and STEP11's strict `xfail` |

Net effect on the slice: CT114–CT121, eleven steps, `CT 33 / kill 23 / STEP 47 / SLICE 7` unchanged. The
draft's three real additions (named repair bank, survivor clause, and the already-published predicate) are in
the steps; its fabricated anchors are not, because a plan that cites a `SubprocessWorkspaceAuthority` that no
one can open is worse than one that says less.

## E290.4 — SLICE7 plan review, second pass on fresh eyes (2026-10-31, code at `31ddfdb`)

Run separately from the writing, against the six questions of the review template rather than against the
slice's own prose. Every verdict below was re-checked in the tree; nothing is carried over from E290.

| step | contract | parent exists where the step says | change is behavioural, not textual | acceptance is binary | mutant removes a caller |
| --- | --- | --- | --- | --- | --- |
| 1 | CT114 | yes — all six surfaces exist (`plan-authoring/SKILL.md`, `tests-writing/{SKILL.md,INJECT.md}`, `feature-planning/{SKILL.md,INJECT.md}`, `inner_loop/prompt.py`, `prompts/architect-fa.md`), `PLAN-SKELETON` appears twice in the skill | yes — text that a planner reads is the product | yes — token list plus damage mutant per surface | yes — `remove-call ... test_each_surface_states_the_law` |
| 2 | CT115 | yes — `_admit_plan`, `_run_admission_repair`, `_promote_validated_plan` at the cited lines; bank named after E290.3 | yes — a refusal moves before the planner call | yes — one `admission.json` attempt, stage never dispatched | yes — delete `_require_managed_publisher` |
| 3 | CT119 | yes — `plan_promotion.py:71`, `:81`, `_private_artifact_directory` imported at `:18` | yes — bytes survive a failed publication | yes — file bytes equal `candidate_sha256`, canonical plan untouched | yes — retention removed, admission rule still asserted |
| 4 | CT117 wire | yes — `_PUBLISH_REPLY:145`, `CREATE_VIEW` payload `:102`, decoder cross-field rules `:334` | yes — an applied intent stops being an error | yes — seeded pre-change `DONE` reads; unknown key is `CORRUPT_STATE` | yes — `_already_published` removed |
| 5 | CT117 authority | yes — `_closed_candidate_reader:3464`, `_plan_prepare:3521`, `_plan_abort:3445` | yes — no snapshot equality on the candidate path, per-file CAS kept | yes — intent-equal publish writes nothing and returns current | yes — the deleted base comparison |
| 6 | CT118 | yes — `client.py:104-155`, `GrantReply` in `types.py` | yes — a wire string stops being storable | yes — `type`/`repr`/`vars` expose no 64-hex | yes — `to_wire_capability` unplugged |
| 7 | CT116 client | yes — `ExecutionClientPlanPublisher` `client.py:154-283`, `_release_candidate_best_effort:268` | yes — one client verb replaces an adapter | yes — `git grep -c ... src tests` is 0, saga plus uncertainty test | yes — adapter deleted, saga test fails |
| 8 | CT116 composition | yes — `config.py:44`, `service.py:290`, `workspace.py:1193-1216`, `cli.py:1336`, `run_workflow` `:1431` | yes — the workflow root gains the only `ExecutionClient` | yes — one `ExecutionClient(` in `src/`, mutant at `:1431` | yes — `plan_publisher=` removed |
| 9 | CT116 provisioner | yes — `session/provisioning.py:52-61`, `service.py:591`, `execution/provisioning.py:28-37` | yes — a real port replaces an in-process-only adapter | yes — reply byte-identical to the two-field result, mapped codes, old `DONE` still reads | yes — the shared `_root_binding` |
| 10 | CT120 | yes — `CANDIDATE_SCOPE` (`protocol.py:73`), `_candidate_scope`, `_candidate_buffer`, `_buffer_bytes:2261` | yes — the authority owns the buffer location | yes — `candidate_path` grep is empty | not a call-removal step: it is a field removal, and the protocol bank is the mutant |
| 11 | class proof | yes — `e2e/I03/implementation-handoffs.md`, `scripts/check_execution_e2e_coverage.py:659-670`, `tests/test_e2e_artifact_contract.py:340-350` | yes — recording port, not a green run | yes — `xfail(strict=True)` plus ledger entry | yes — every helper named with its bank |

Findings, all closed in this pass:

1. **The already-applied predicate was described but not located** — a reader could not tell which branch becomes
   `already_published`. Now pinned to `sha256(buffer) == plan_ref.sha256` (`:3533-3534`) and to "writes
   nothing", including the point that `_plan_abort` already covers a failed attempt.
2. **The repair path named no existing bank** — STEP2/STEP3 pointed at a file that did not exist in the draft
   and at a new bank only. Now `tests/test_s8_workflow_controller.py` is named for the ordinary path.
3. **The survivor rule was implicit** — STEP11 now lists each helper and its proving bank, so the E288 shape
   cannot recur inside the slice that closes it.
4. **Draft anchors that do not exist** — recorded in E290.3 rather than silently dropped, because the next
   reader of that draft will otherwise look for `SubprocessWorkspaceAuthority` and `_commit_bundle` again.
5. **Verified, no change needed** — `_PUBLISH_REPLY` already carries `plan_ref`; `VIEW` already carries
   `base_revision`; `ProvisionedWorkspace.tree_sha256` is read by nothing (`manager.py:384`, `:423` read only
   `.registered`); `ExecutionClient(` really is absent from `src/`; all six CT114 surfaces exist.
6. **Dependency graph re-checked** — `SLICE4: SLICE3, SLICE7`, `SLICE5: SLICE4, SLICE7`,
   `SLICE6: SLICE5, SLICE7`, `SLICE7: SLICE3`: acyclic, and the run order stays 3 → 7 → 4 → 5 → 6.

## E296 — SLICE7 plan review, third pass: STEP9–STEP11 read against the tree at `a6dcd58` (2026-11-01)

**Why this pass exists.** E295 closed STEP8, so the slice's own code now exists and can be used as an oracle for
the steps that have not been written yet. Every claim below was checked against the tree or measured with a run,
not inferred from the text. Four findings: two blocked exits, one instruction that would fail its own bank, one
name collision. Nothing here changes a contract without a Q.

### R1 (STEP9) — the step replaces a caller that does not exist

`grep -rn "ManagedProvisioner(" src` is **0** and `grep -n "workspace_provisioner" src/fa/cli.py` is **0**:
production builds `SessionManager` with `workspace_provisioner=None` (`session/manager.py:92,99`), and the only
constructor of `ManagedProvisioner` is `tests/test_execution_provisioning.py`, whose own docstring calls itself
"component evidence only … no deployed-service claim". So the step's exit ("`SessionManager` can be constructed
with the provisioner in place of the in-process-only `ManagedProvisioner`") describes a substitution that happens
nowhere: the real substitution is `None → ClientWorkspaceProvisioner`, and that one changes `fa run chat` from
"resolve the workspace on the host path" to "fail closed unless a supervisor answers". The closure table already
gives the production injection to **S4P2** ("one client + provisioner into `_session_manager_for_args`").
→ **Q94** below.

### R2 (STEP10) — one half is implementable, the other half needs a rule nobody wrote

Measured in the tree: `candidate_scope` is **persisted** in the view record (`workspace.py:1702`) and validated by
the strict record schema (`_VIEW_RECORD` at `:189-201`, `candidate_scope=_nullable(CANDIDATE_SCOPE)`, and
`_object` means *all keys required, no extras*, `protocol.py:25-26,69`); it is read back at `:2255`, where
`path != scope["candidate_path"]` is `PATH_DENIED`. The physical buffer is already authority-owned
(`os.open("candidate", dir_fd=pin.directory)`, `:2263`), and `candidate_path` is only the workspace-relative
**alias** the controller writes through (`client.py:224` names it, `:255` writes it). Consequences:

1. *Feasible now:* drop the key from the payload and authorise the CANDIDATE view's one writable target as the
   buffer, keeping `plan_ref` equality (`:3431`). The authorisation stops trusting a caller-named path, which is
   exactly the intent.
2. *Not feasible without a decision:* old view records on disk carry `candidate_path`, and the record schema
   rejects extras — so removal is a journal-visible schema change unless the record schema keeps the key
   **optional and ignored** (the same "relax, do not extend" shape STEP9 uses for `tree_sha256`).
3. *The step's own alternative is unbuilt:* "the buffer is located by the authority" via a deterministic name is
   CT119 (`retain_plan_draft`, `.fa/admission/<run_id>/plan-<sha256>.md`), and `grep -rn retain_plan_draft src
   tests` is **0** while `tests/test_plan_candidate_retention.py` does not exist — the same two names STEP11
   already depends on.
→ **Q95** below.

### R3 (STEP11) — the sequencing pin is already true, so `xfail(strict=True)` would XPASS

Measured over the real in-process supervisor with the `Site` fixture and the STEP8 composition (probe script,
three scenarios in one process):

| scenario | outcome |
| --- | --- |
| two publications in one run, source re-read before the second | second **succeeds**, `already_published=False` |
| second publication with the source snapshot taken *before* the first | `INPUT_POLICY` at `workspace.py:4883` → `_pinned_plan_context` → `_recheck_context:274` |
| one host-side write after a successful publication | next `CREATE_VIEW` refused `CORRUPT_STATE` (surfaced as `ExecutionUncertainError`) from `_unchanged:1303-1309`; `close()` returns `False` because the `RELEASE` is refused too |

So the step's proposed test ("writes one project file … and asserts the next candidate publish is refused") **passes
today**; marking it `xfail(strict=True)` fails the bank on XPASS. What SLICE4 STEP2 actually buys is a *successful*
second publication after a host-side write — that is the assertion that fails today and that belongs under the
mark. The middle row is a production rule the plan never states and STEP11 should also pin: **after any successful
publication in a run, the next publication must re-read its source snapshot**, or it is refused `INPUT_POLICY` for
pinning bytes the authority no longer holds.
→ **Q96** below.

### R4 (STEP11) — the EDGE test name is taken by what STEP8 shipped

`tests/test_execution_composition.py::test_the_workflow_root_supplies_a_managed_publisher` exists (E295) and proves
that `_cmd_workflow` passes `plan_publisher=` into `run_workflow`, with `run_workflow` monkeypatched. STEP11 asks
for the same name to prove the publisher reaches `_promote_validated_plan`
(`workflow_controller.py:2455-2456`, which already takes `publisher=ctx.plan_publisher`). No behaviour is at stake:
STEP11 extends the existing test to drive the real controller with a recording port and renames it
`…_reaches_promotion`, instead of adding a second test with a name that already means something narrower.

### Verified and unchanged

`WorkspaceProvisioner` is a `Callable[[ProvisionRequest], ProvisionedWorkspace]` alias (`session/provisioning.py:66`),
so a `__call__` class satisfies it; `service.py:591` really answers `register_workspace` with exactly
`{workspace_id, revision_id}`; `ProvisionedWorkspace.tree_sha256` is read by nothing outside
`tests/test_execution_provisioning.py:81`; `_root_binding` is already the shared helper STEP9 expects;
`SessionManager._resolve` allocates the provisioning run through `begin_run` before calling the provisioner
(`:299-307`), so a run id exists at that seam; `_promote_validated_plan` accepts a `publisher=` port.
