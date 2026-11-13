---
Roadmap-ID: RM-planning-topology
slug: planning-topology-and-executable-contracts-loop
created: 2026-09-09
status: IN PROGRESS
active-increment: I01
supersedes: worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md
---

# ROADMAP: Planning topology & executable-contracts loop

## Intent

Rebuild the role-based loop (planner → coder → eval, code-owned controller, chat
orchestrator) around the locked planning topology — **feature → increment → `SLICE#`
→ `STEP#`** — with **executable contracts** (the planner authors each slice's test; the
harness proves it non-vacuous), a **deterministic verify gate** (exit code = fact; eval
verdict = judgment), and an **EVIDENCE ledger** that makes each increment smarter than
the last.

This roadmap **supersedes** the 27-chapter `PLAN-slice-ceremony-harness-enforcement.md`
(198 KB), which collapsed under its own scope at the S15 eval-verification roadblock.
The still-relevant on-hold slices from that plan are **absorbed and revised** into the
increments below (see "Absorbed from the superseded plan"), not carried verbatim.

## Artifact schema

This project uses the new per-project schema (canonical spec:
[`notes/artifact-schema-and-grammar.md`](notes/artifact-schema-and-grammar.md)):

```
worklogs/planning-topology-and-executable-contracts-loop/
  roadmap.md        ← this file (the index)
  ledger.md         ← EVIDENCE ledger (append-only, provenance-tagged)
  increments/       ← one file per increment; SLICE#s are sections inside
  notes/            ← supporting specs, reviews, research for this project
```

## Increments

Rolling wave: **I01 and I02 are planned in full** (`increments/increment-01-…`,
`increments/increment-02-…`); foundation I03 has six source-grounded finalized briefs;
E231 records Q59/Q60/Q63/Q74 dispositions and current-surface reuse. E233's Q75 stop was resolved
by the operator's explicit Q75(a) selection in E234; SLICE1 resumes with bounded replay/nonsecret-result primitives only. E230 finalization strengthens
wire/state/recovery/stage handoffs and requires real-provider direct+nested deployed witnesses; it
does not restore the deferred per-slice/tracker/L2 successor. I04–I06 remain **outlines** and get executable increment briefs just-in-time. Scope migration is recorded in E200–E201;
no implementation/status tick follows from it.
The map below is expected to be refined as reality teaches.

| ID | Increment | Status | One-line intent |
|---|---|---|---|
| **I01** | Plan grammar & extractor | **IN PROGRESS** | the harness can parse and lint the new plan format |
| I02 | Executable contracts & verify gate | **SHIPPED** ([plan](increments/increment-02-verify-gate-and-kill-checks.md)) | Retained explicit-plan Q57/Q58 admission/repair/promotion, slice-scoped verify/kill classification, T0 and real local controller/session/eval proof. Seven sections through SLICE6 (including SLICE2b). Locally implemented and diff-reviewed (E229), pending E2E as I03 ships; actual just check remains red on the common readiness failure, not OS isolation/deployed acceptance. Every unique live producer case remains I03-owned. E223 explicitly moves deployed functional/source-to-behaviour verification, environment/inherited-baseline acceptance, broad independent implementation/evidence review and integrated deployment signoff to final I03, all incomplete. [Migration map](notes/i02-to-i03-scope-migration-2026-10-15.md). |
| I03 | Execution/workspace foundation & integrated acceptance | **OUTLINED** ([finalized seven-slice plan](increments/increment-03-execution-workspace-foundation.md)) | Mandatory Linux/Docker project-code cells with PTY, trusted launch/host supervisor, exclusive workspace writer/private views/pinned readers, sealing/fenced publication/recovery, real nested selection/bootstrap/simple Q66, and final reviewed deployed I02+I03 acceptance. Owns CT96/CT97, managed clauses and all former SLICE7 CT88/CT89. Reuse existing facades; no standalone FastAPI completion gate or second authority. Six briefs ordered A/B/C/E/D/F; E230 source-reviewed contracts and real-provider direct+nested final witnesses; E231 route/bundle/live-schema/checkpoint decisions resolved; E232 partial CT98 exists; E234 resolves Q75(a) and adds C0/C3 replay/type foundations. E257–E259 add local admission/CellBackend/view-purpose components; E260 records the plan correction for R1–R5 and binds their future witnesses to the E2E register; E261 records the still-open in-flight noninteractive CANCEL owner gap; E262–E266 close it and the CT104 barrier; E267 adds the local seal component (`publication.py`, CT105) and register row I03-LIVE-19, with publish/recovery still open. These are C0/C3/local proofs, not production composition or host acceptance. Q66 runtime input proof, real factory/caller/mount cutover, descendant terminality, Docker/Ubuntu evidence and E223’s four final acceptance duties remain open. I03 remains OUTLINED; no shipping or deployment status follows. R13/W0 (operator, 2026-11-04): full read-only/scratch managed child implemented and its local row DoD closed across chat/planner/coder production callers; global W0 still requires all Q113 rows. Per-role capability flags default off; observer W-A then W-B post-I03. Live-host ledger/ENOSPC E2E is reserved for the final wave. See [R13 plan](notes/r13-managed-subagent-plan-2026-11-04.md). W0 audit refresh (2026-11-04): R01, R03, R14–R28 remain OPEN; the inventory's named nodeids for R15–R28 are stale; most audited tests are component/local, not production-caller; R21 had no production caller; R23's isolated worktree Git producer has no production caller found; the legacy artifact-root subagent route is distinct, and the managed child is R13. Q126-A was implemented per E469: R23 is RETIRED / NOT APPLICABLE TO MANAGED W0, not PASS, after the two-path audit and product-registry cleanup. At E469 Q113 gated 27 active rows, R01–R22 and R24–R28; subsequent Q131-C/E477 removes the unused R21 helper/export and retires R21 as NOT APPLICABLE TO MANAGED W0, not PASS. At E477, the then-current W0 set was R01–R20, R22, and R24–R28 (26 rows). Q132-D/E481 defers R24 to W2 and Q133-B/E482 defers R25/R26 to W2 and R28 to W1; all remain OPEN, not PASS/N/A. The current W0 active set is R01–R20, R22, and R27 (**22 rows**). W1 may begin only after those 22 pass; R28 must pass before W1 closes, and R24–R26 before W2 closes. R16's Arena-local row is CLOSED by E466. Q125 is resolved by option A and R12's scoped local W0 row is CLOSED (E448). See [W0 audit](notes/w0-r01-r03-r14-r28-audit-2026-11-04.md), [Q125 audit](notes/q125-r12-audit-2026-11-04.md), and [R23/Q126-A closeout](notes/r23-q126a-callgraph-closeout-2026-11-06.md). **Status reconciled through E524 / `014c012` (2026-11-10):** W0 (22 active rows) is **CLOSED Arena-locally** by E503; W1 (local S2P4/S3P3/S4P2 cutover, Q97 bounds, and R28) is **CLOSED Arena-locally** by E505–E510 (live-host profile/process evidence and Q139 mutmut calibration belong to W3/W4); **W2 is IN PROGRESS** — Q138-B fence (E511), R25 bound publisher/Q114 local closure (E513–E514, leaving the E512 lost `CREATE_VIEW` reply gap), S5P1–S5P3 managed acquisition/v2 admission provenance (E516–E524), and the end-to-end integration fixes (`9c4f429`, `014c012`) have landed locally, while R24 (`slice_verification.py` / `_pinned_verify_substrate` defects), R26 (`Q141=C` nested `MUTATION` enforcement + real authority C1 + child-return/lease fixes), S5P4 (`Q66` parent context snapshot), and cross-cutting W2 repairs remain OPEN. **W3** (local `just check-deep`, `authoring-check`/baseline repair, `tests/integration/`, S6 package/fixtures/Q108 coverage update, and candidate `fa update` deploy prerequisite) and **W4** (live deployed E2E acceptance plus deferred `Q106` large-envelope parity) remain OPEN; I03 as a whole remains OUTLINED/UNSHIPPED pending W2–W4 closure. |
| I04 | Evidence ledger, pinned invariants, retry hygiene | outlined | the loop carries evidence, pins governance, retries clean, never wedges (includes the ledger **parser**, moved here from I01 — build it beside its consumers; and the **pinned-invariants injection**, drafted as an I01 slice on 2026-10-06 and moved back here as scope creep — contracts banked in `notes/role-prompts-conformance.md`, ledger E79) |
| I05 | Rolling-wave, ASK#, autonomy, chat orchestration | outlined | the roadmap closes across runs; the ceremony/scope/draft work lands here, revised |
| I06 | Telemetry & distillation (parallel deferred) | outlined | runs are measured and distilled; slice-DAG parallelism deferred |

**Q130/R19 policy update (2026-11-06).** Runtime IntentGuard is retired from all production `fa run` paths; no active-view snapshot API is planned. R19 remains the next open applicable W0 row until its real managed production-caller first-write-without-`pr_prepare` oracle, zero Git/path-producer assertions, and producer/EDGE kills pass. This does not close global W0 or authorize W1. See [Q130](notes/open-questions-2026-10-07.md#q130--what-complete-managed-snapshot-should-drive-intentguard-without-controller-git), [decision note](notes/intent-guard-runtime-retirement-2026-11-06.md), and the [R19 inventory row](notes/i03-execution-call-inventory.md).

**R13 implementation and local acceptance boundary (2026-11-04).** The
operator superseded the deny-only W0 split and directed full generic
read-only/scratch child behavior in W0, including Q122 per-view profiles; role
flags gate access, not child toolset shape. Q123 is resolved. R13's Arena-local
W0 row DoD is CLOSED after positive and negative production-caller oracles for
chat/planner/coder, including configured-backend refusal and Q124 evidence.
Global W0 remains OPEN until every Q113 row passes; W1 starts only after that.
Live-host ledger-append and Docker ENOSPC/mount-release E2E are reserved for the
final wave. See the R13 plan.

### Идея после I03: управляемая композиция инструментов

После полного I03 и его host-приёмки отдельно оценить зависимые цепочки инструментов
в одном ходе без промежуточного вызова LLM: сравнить native multi-call, предметный
инструмент, ограниченный pipeline и Code Mode на измеренных сценариях. Это не выбор
реализации и не новый инкремент. Любой будущий путь должен сохранять авторизацию
view, lifecycle hooks, отдельные результаты/историю и честную неопределённость;
не считать многодействие транзакцией. Обоснование и текущие незакрытые стыки —
[заметка I03](notes/i03-composition-and-batch-foundation-plan-2026-11-01.md).
Порядок I04–I06 не меняется.

### Будущая отдельная фича после I03: наблюдатель за workflow

После завершения и тестирования I03 рассмотреть отдельную фичу: параллельный read-only
собеседник, которому пользователь может задавать вопросы о ходе выполняющегося workflow.
Базовый кандидат — отдельный агент или опциональный субагент с доступом к проверенным статусу,
событиям и опубликованным ревизиям, с заметками в отдельном безопасном хранилище; он не изменяет
проект или авторитетные записи workflow. Показывать различие между промежуточными событиями и
опубликованным состоянием. Более широкий detached workflow с продолжающимся основным чатом —
возможное последующее развитие, не обязательная часть первого варианта. Интерфейс, изоляция,
доступ к данным, хранение заметок и проверки проектируются отдельно по результатам I03.

**Статус: идея, не спланирована и не входит в I03.** ID и порядок определить при rolling-wave
планировании; существующие I04–I06 не переименовываются и не переносятся.

**Уточнение оператора (2026-11-04).** Выбран порядок **W-A → W-B**: сначала отдельный
read-only observer attachment, затем same-session read-only chat lane с durable workflow
child. W-C (full chat tools + workflow mutate concurrently) отклонён как несовместимый с
one-writer контрактом. Observer остаётся post-I03 и не является implicit side effect
добавления subagent. Решение по subagent (read-only/scratch, без writer handoff) не меняет
observer trade-off. Детали — [R13 plan](notes/r13-managed-subagent-plan-2026-11-04.md).

<a id="slice-loop-tracker-l2-eval-successor"></a>
### Deferred capability: slice-loop/tracker/L2-eval successor

The former I03 outline is **preserved, not delivered or abandoned**: controller per-slice dispatch,
code-owned tracker/STEP ticking, L1/L2/L3 eval, scoped coder brief via `section`, `steps_mode`,
CT10b/tests_note semantics and corresponding coder/eval prompt consumers. Numeric increment ID/
order will be assigned by separate rolling-wave disposition; do not renumber I04–I06 or Q64→I06.
Foundation I03 does not include these just because it inherited the number.

Interim operator ticking expires only when the actual tracker capability is delivered with proof,
not when foundation I03 ships. Contract VERIFIED requires actual L2 judgment capability; I02
local implementation/mutation evidence or foundation shipping does not supply it. Existing I04
ledger/retry and I05 orchestration dependencies follow actual consumer capabilities.

### Deferred — explicitly not scheduled (from `RESEARCH-ADOPTION-PLAN.md`)

Recorded so nothing is silently dropped. Each is a real adoption item, deferred for cause;
none is in any increment above until promoted.

| Item | Why deferred | Promote when |
|---|---|---|
| #10 Escalation ladder / N-version repair | needs the parallel runner (shared with #11); the simple budgeted retry must prove out first | after the actual slice-loop/tracker/L2-eval successor + I04 stall counter |
| #11 Slice DAG + parallel git worktrees | most premature; sequential first; worktree + runtime isolation is real work | after foundation isolation and the sequential-loop successor, on measured parallelism bottleneck |
| #15 Post-feature distillation ritual | pays off over many features, not one | after several increments ship (I06) |
| #16 Hash-anchored tamper-evident run record | nice audit property, not load-bearing yet | if/when telemetry must be trusted by an outsider (after #17) |
| #18 Model tiering (planner-tagged) | conditional on #17 telemetry; premature tiering corrupts the data it saves on | after I06 telemetry has a few hundred slices |
| Prompt-side effort routing (`reasoning.effort` per slice class) | a different lever from prose scaffolding; must be measured in its own arm or it contaminates every other result | I06, as its own ablation arm |
| N-version repair as *diagnosis* only | resampling cannot lower a verifier's false-positive rate, so verify-based *selection* inherits the verifier's ceiling; optimal k is often ≤5 and zero when a false positive costs 10× | if used at all: diagnosis only, selection on CONSTRAINT satisfaction, k ≤ 3 |
| Reliability SLO and its per-slice target | needs a baseline; a target invented without one is either trivially met or permanently missed | I06, after the first runs produce data |
| I02 gate calibration corpus and ≥95% rejection target (20 known-good/known-bad slices) | explicitly deferred by the operator on 2026-10-14; reduced I02 may ship retained local DoD without calibrated accuracy; deployed acceptance belongs to I03 | follow-up deferred to I06 by operator; I06 defines the trigger before calibrated claims or gate-policy changes and keeps calibration examples separate from held-out regression data |

(#17 telemetry *schema* is pulled forward into I06 — "cheap now, expensive later" — even
though the attribution *loop* is later.)

## Standing decisions (ADR-level)

Tagged `decided:` (chosen) or `assumed:` (never verified — an `ASK#` candidate).

- `decided:` Four tiers — feature → increment (one run, shippable) → `SLICE#` (one
  commit, contracts + verify) → `STEP#` (one atomic action).
- `decided:` Rolling wave — full detail for the current increment, one-line outline for
  later ones; staleness is managed at the **increment** boundary.
- `decided:` The **planner does the heavy lifting** — roadmap, increment, slices, steps,
  and the `TESTS:` files. The coder executes steps within firm contracts; major drift is
  a `REPLAN`.
- `decided:` Artifact schema = `roadmap.md` + `ledger.md` + `increments/` + `notes/`;
  folder is a pure slug, `created:` lives in frontmatter; increments zero-padded.
- `decided:` Rename `S#` → `SLICE#`, steps → `STEP#` (kills the `### Step S#` ambiguity).
- `decided:` Contracts carry **classes** (`FUNCTIONAL` / `CONSTRAINT` / `PRESERVATION`);
  the planner authors the test; the harness proves non-vacuity (fail-before/pass-after)
  — landed in I02.
- `decided:` A `kill:` directive may name only a producer **its own slice builds**, and the
  kill-check runs that slice's own `TESTS:`. A directive is an instrument for hardening a
  test suite; it cannot specify an interface for code that does not exist yet, because it can
  only guess the future private name or mutate code the declaring slice's tests never run.
  Cross-slice expectations are `INTENT:` prose plus a contract in the slice that builds the
  producer — schema §4 "Producer ownership", Q48, E169.
- `decided:` Verify exit code = **fact**; eval verdict = **judgment**; eval runs on a
  different model family, blind to authorship.
- `decided:` Tracker updates (CT# status, STEP# boxes) are **code**, not an LLM step.
- `decided:` Agent-executable text is written as **exact imperatives** — file:line targets
  and runnable `(exit: …)` checks; no citations, history, or rationale inline. Rationale
  lives in `notes/`. (Schema §1; exemplified in increment-01.)
- `decided:` **N ≤ 7 slices per increment is a complexity ceiling, not a sizing prior.** More
  than that means the increment is mis-scoped: split it into smaller increments rather than
  into smaller slices. Autonomous success multiplies across a chain (s^N), so slice *count* sits
  in the exponent while per-slice quality sits in the base — finer slicing makes a long chain
  worse, added hierarchy makes it better. Deliberately **unchecked**: the operator reviews every
  plan. Expires into a pre-check FAIL if plans are ever authored without operator review.
- `decided:` **Cite research with versions.** Every claim in a research note cites
  `{arxiv-id}v{N}, retrieved {date}`, marks whether it came from the abstract, the body or a
  table, and **quotes the exact sentence** when a locked decision rests on it; anything
  benchmark-derived carries a 90-day re-check date. Six of the eight citation errors found by
  the 2026-10-06 reviews would have been caught by the quote rule alone.
- `decided:` **Syntactic first.** A trigger the controller acts on is a syntactic or structural
  rule. Semantic or model-judged detection runs **log-only** until it has demonstrated precision
  and recall on recorded data. This protects the "the controller is code" rule from erosion.
- `decided:` **A ≤3-slice plan is a first-class fast path**, not a degenerate case of the full
  ceremony. Ceremony is fixed-cost; a flat plan skips it by design.
- `decided:` **Recoverability is the fourth reason the planner writes steps** (after scoping,
  reviewability and attribution): a checkpointed chain turns an exponential failure into a
  linear count of human touches.
- `decided:` **Nothing proposed by a review ships without (a) a named failure mode it prevents
  and (b) an on/off ablation planned in the increment that adds it.** The research this roadmap
  implements found that 3 of 14 multi-agent failure modes are *created by* structure.
- `decided:` **Graceful degradation order, logged, never silent:** N-version → retry; k=2 →
  k=1 plus samples; frontier model → cheap model. Each downgrade appends a ledger entry.
- `decided:` **Zero-deprecation removals are allowed only while three conditions hold** — no
  live consumers of the old form, a small archived mechanically-migratable corpus, and a
  migration note shipped for humans. All three held for the `S#` → `SLICE#` rename (E24). If any
  fails later, the next removal is warn-then-remove.
- `decided:` **SD-C — no increment is DONE without one live-path test.** Every increment ships
  at least one test that boots the real composition root (`drive_session` and the shipped
  factories; only `ProviderChain.request` is mocked) and asserts an observable effect of that
  increment's feature, naming the production call site whose deletion makes it fail. Static
  conformance over fixture text is necessary and **never sufficient**: it proves a string
  parses, not that anything calls the parser. The two failure modes this exists to stop are
  code that is wired to nothing and an agent reporting "done" for a path no test ever entered —
  both of which this project has already produced (a dead `_slice_sections` shipped inside
  SLICE2 and caught only by the mutation sweep, ledger E89; and the per-slice coverage gate at
  `workflow_controller.py:332` silently no-opping for the whole life of I01, ledger E52).
  Where no live path exists yet, the increment says so in one line and names the increment that
  will add it — the same discipline as SD-B's `consumer:`.
- `assumed:` Per-slice eval beats one cumulative eval — confirmed by the slice-diff size,
  re-checked once the actual sequential-loop successor and I06 telemetry exist.

## Absorbed from the superseded plan

The monster plan's on-hold slices (`S6, S6a, S6b, S7, S11b, S8, S9`) are **revised** into
this roadmap, not resumed as written. Mapping (verified against the monster plan's GAP
ledger and step headers):

| Old slice | Was | Becomes | Note |
|---|---|---|---|
| S6 | harness runs verification (GAP5/GAP13) | **I02** | the verify gate; now planner-authored tests + non-vacuity |
| S9 | mirror grammar into planning skills | **I01** | skill migration is part of the grammar increment |
| S11b | reconcile claimed vs observed verdict | **deferred slice-loop/tracker/L2-eval successor** | preserved three-level eval capability; not delivered by foundation I03 |
| S6a | persist edit packets (GAP12, PR-body source) | **I05** | revised: the slice brief / PR source under the new schema |
| S6b | harness-derived draft (IntentGuard) | **deferred post-I03** | Runtime IntentGuard is retired from all production `fa run` paths by Q130/R19; any successor needs a separate post-I03 contract and authorization. |
| S7 | `ScopeWarnHook` files-allowed signal | **I05** | revised: scope signal under the slice-brief model |
| S8 | `pr_prepare` role in chat (GAP7/GAP8) | **revised/deferred** | Keep it available as an optional human-readable note in chat and other `fa run` roles; it is not a write permit or pre-mutation ceremony. |

The superseded plan and its `worklogs/reviews/*` artifacts remain as **evidence only**;
they move to `worklogs/archive/` later (operator decision, not part of any increment).

## Sources

- `PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md` — the research (F1–F12, the
  18-item backlog, the evidence appendix).
- `RESEARCH-ADOPTION-PLAN.md` — the ranked adoption set this roadmap implements.
- `PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md` §2 — the topology this roadmap is
  built on. (It condenses a design doc *Planning topology explained*, which is **not** in this
  repo; the earlier citation of `PLANNING-TOPOLOGY-EXPLAINED.md` was a dead reference.)
- `notes/decisions-qa-2026-10-06.md` — **the rationale-context surface** for the 2026-10-06
  plan edits: every decision with its alternatives and the reason it won. Plan bodies and the
  ledger stay rationale-free (§1); this is where the reasoning lives.
- `notes/findings-register-2026-10-06.md` — the exhaustive finding register those decisions
  were walked from, including §S (substrate that already exists in `src/`).
- `worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md` — the
  superseded plan (evidence only).
