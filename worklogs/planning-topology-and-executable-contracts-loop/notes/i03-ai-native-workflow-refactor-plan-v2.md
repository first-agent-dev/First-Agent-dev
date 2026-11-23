# I03 linked plan — AI-native workflow refactor (V2)

**Plan format:** `AI-NATIVE-PLAN-V2` (planning contract; not yet a runtime-admitted artifact)<br>
**Owning record:** [I03 execution/workspace increment](../increments/increment-03-execution-workspace-foundation.md), STEP9B<br>
**Canonical target specification:** [artifact-schema-and-grammar.md](artifact-schema-and-grammar.md), the sole V2 grammar/source-of-truth after cutover. This linked plan specifies its V2 acceptance and slice obligations; it does not implement or replace the canonical schema, parser, or runtime.<br>
**State:** REVIEW DRAFT, PLAN ONLY. SLICE6 STEP9 is locally closed (E556/E558); STEP9A and STEP9B remain open. This document was drafted ahead of the required predecessor closure solely to enable review. It does not satisfy/close STEP9B, authorize implementation, or claim product implementation, new-schema parser, project-host witness, deployment, or acceptance. Reconfirm predecessor evidence and update review disposition before STEP9B can close.<br>
**Date:** 2026-11-15; adversarial reviews 2026-11-15/2026-11-21; **corrected 2026-11-22 (E605).**  
**Corrections 2026-11-22 (why this plan was edited before implementation).** A source audit found the plan contradicting itself on the one rule the next slice must enforce, so five sentences said different things about evidence (grammar delta, §2 production grammar, INV-05, CT-3.1, §8 step 4) and §8 claimed Q-V2-ACC-1/2 were closed while the register carried no resolution. Changed in this revision: the `INVARIANTS` grammar and the deletion of `KIND` (D-V2-10); those five sentences, now one rule; Q-V2-ACC-2 marked RESOLVED; §8 step 4 and the SLICE3 planning-questions paragraph; Q-V2-MODEA-1 no longer described as open after D-V2-6 closed it; the canonical-schema status (D-V2-11); the SLICE2 paragraph that still described the deleted payload route as *today*; the duplicated §5 number; the out-of-order §11/§12; and five stale source citations (`parse_plan`, `_admit_published_project`, `_validate_plan_admission`, `_run_stage`, the acceptance-bank test count). Defects the audit found are §12 rows P4-1–P4-6 rather than prose in a note, so a later slice closes a row instead of re-describing it. Evidence and the independent cross-review: [i03-external-design-review-2026-11-22.md](i03-external-design-review-2026-11-22.md).

**Operator direction 2026-11-23 — rolling-wave planning, vertical slices and deferred mutation binding.** The ratified
MVP behavior and implementation work are in SLICE3's `D-V2-13` block below. It supersedes earlier proposals that
make `TARGET-ID = path::symbol`, require the planner to guess future private symbols, or require two particular
command invocations. Current code and historical ledger entries are not rewritten as if the feature landed.
Rolling wave means a broad roadmap with the nearest increment and its slices detailed while later increments remain
outlined; it does not require detailed I02 while I01 is unfinished. Collection of the current increment and
proposal-transport proof remain technical checks, not implementation or host evidence. Existing user-facing semantics and other ratified decisions continue to apply.

**Operator layout amendment E695 (2026-11-23; target, not implemented).** The canonical V2
working paths are `worklogs/<slug>/notes/ledger.md` and
`worklogs/<slug>/notes/open-questions.md`. The user accepts relocating the ledger and asks
that open questions move to notes. Keep `worklogs/<slug>/roadmap.md` at the root: moving it
into increments has no demonstrated mount benefit and changes discovery/collision contracts.
This supersedes earlier *target* mentions of a root ledger or root open-questions in this
plan (including CT-2.3, CT-2.8, CT-4.3 and D-V2-9), but does not rewrite historical evidence,
change the current implementation, or migrate the I03 parent. The writable notes Q file is
working material: a post-admission edit must not itself unblock scope, alter an admitted
Q decision or rewrite a ratified invariant. Planner may resolve ordinary product questions
best-effort with a recorded rationale, without a mandatory human/coder approval or automatic reseal for each Q edit. The implementation
must bind any decision that is used for a gate to its relevant run/revision and validate
authority; changing an already admitted plan/oracle or other sealed basis requires the
appropriate new revision/admission/seal. The exact decision-binding mechanism is open, not
a selected extra journal or blanket reseal requirement. These requirements do not make the
notes file read-only or require reseal merely to edit it. Maintain independent plan/oracle
custody and old evidence.

## 1. Intent, scope, and authority

Deliver an AI-native, production-composed planning workflow for a fresh project: the chat role supplies a validated project slug through `invoke_workflow`; the planner authors semantic planning and acceptance content; trusted harness code owns scaffolding, fixed-path materialization, full-project validation, admission and seal; revision-safe V2 status ticks are a required target but remain gated by Q-V2-STATUS-1; coder can start only after the complete acceptance closure is sealed and can inspect it read-only (mode A); the managed verifier runs that same pinned closure. A successful vertical run must reach the real caller and produce an observable, reviewable host witness. Every refusal must be structured and leave no ambiguous success or accidental overwrite.

This is a linked semantic/acceptance authority for the new refactor slices, not a migration of the I03 parent. The existing I03 increment remains human-only planning/status context and is not a V2 conformance input. Cutover uses the single unified `invoke_workflow` route (used by both chat agents and CLI) with the new canonical V2 schema and no V1 parser, compatibility mode, or legacy `fa workflow` fallback. The I03 parent is not submitted to this route. Do not add a V1 status bridge. The runtime's supported grammar version is trusted control-plane input, never selected by project content. Internal `admission.json schema_version: 2` is not the plan grammar version.

### Ratified boundaries retained

- The outer chat role supplies `project_slug` as an `invoke_workflow` field; controller/authority validates and owns its filesystem use. Planner output never chooses a filesystem slug. A slug alone does not imply create-new or existing-project selection; the route discriminator is explicit and closed. Invalid input or collision fails; do not auto-substitute, overwrite, or silently select an existing project.
- Harness owns fixed scaffold/materialization. Project semantic artifacts and acceptance bytes are immutable after admission/seal; runtime evidence is run-scoped. Production V2 status ticks are a target obligation gated by Q-V2-STATUS-1; until a revision-safe authority design is source-proven, no tick implementation or host evidence is authorized. Planner owns semantic plans, scenarios, project questions, test-support/acceptance content, and acceptance criteria; it does not receive generic project write authority. Coder is unavailable until complete validation and seal.
- `INV → CT → TEST-ID → selector`: one primary INV per CT; one INV may have multiple CTs; each TEST-ID belongs to exactly one CT and resolves to exactly one collected nodeid; one CT may have multiple TEST-IDs. Optional formal SCN expresses a scenario/path and links explicit `CT-ID[]`; TEST membership derives through CT→TEST.
- Follow STEP9A custody: controller-minted versioned `AcceptanceBundle`; artifact C/workspace-revision strategy; mode A prevents writes through both file tools and shell (D-V2-6, amended by E657 / CT-3.3); immutable-payload storage fallback if the selected revision strategy cannot prove the required custody. No hash-only sidecar. Visibility mode B is unsupported in MVP and fails closed. Mode A is visible/read-only, not an independent or hidden oracle.
- Exact kill attribution is one mutation target → one CT → one TEST-ID → one nodeid on the sealed revision. A mapped assertion failure alone proves a kill. A pass under mutation is VACUOUS; collection/setup/skip/timeout/crash/launch/JUnit failure or zero executions is ERROR, not PROVEN. Unrelated failures never prove the target. Custody/mapping integrity blocks in observe and enforce; determinate kill failures are advisory in observe and repair-blocking in enforce. TEST-DEFECT creates a new sealed revision and preserves the old evidence; invariant changes require replan.
- No mandatory coder→planner/owner approval before implementation. Coder owns routine internal seam choices inside admitted behavior/safety/ownership constraints. Planner may resolve ordinary product-semantic questions best-effort in `notes/open-questions.md`; only dependent scope is held if unresolved. Changing a ratified invariant requires replan. Risk-gated independent review remains an open policy question, not an MVP gate.
- The I03 one-off slice-count exception applies to these planned slices only; `_SLICE_CEILING = 7` remains unchanged for other increments.

### Out of scope / evidence boundary

No implementation in this task; no old I03 migration; no V1 compatibility; no parallel test runner without source evidence; no generic planner filesystem writer; no hidden-test mode; no Arena status bridge; no automatic slug generation; no claim that local checks equal host acceptance. Existing project selection remains a distinct route. Held-out evaluation and broad architecture recommendations not ratified by the operator remain future considerations.

## 2. Current production seams and target flow

Source grounding is summarized here; cited symbols are starting points for each implementation slice and must be rechecked against source when implementation begins.

**Terminology (two different "V2"s already coexist in this repository).** *`PLAN-V2`* / *artifact V2* is the Markdown plan grammar this plan introduces (`Plan-Format: AI-NATIVE-PLAN-V2`, `plan_v2.py`). *Admission-record v2* is the existing controller record schema exercised by `tests/test_admission_v2_provenance.py` (bootstrap bundle/plan hashes, install receipt, revision chain). Every statement below says `PLAN-V2` when it means the grammar; "the admission record" always means the existing one. An implementation that reads bare "V2" as the record schema will wire the wrong seam — that misreading has already cost one draft of this table.

| Concern | Existing source seam / observed behavior | Target seam reuse and required change |
|---|---|---|
| Chat caller | `src/fa/cli.py::_build_run_tool_registry` registers `invoke_workflow` only for chat. `src/fa/inner_loop/tools/workflow_tool.py::INVOKE_WORKFLOW_SCHEMA` is closed and currently has task/mode/roles/repair/replan fields only; `_prepare_invocation` carries no project slug. Child invocation, HANDOFF, return reconciliation, and `ToolResult.fail` already exist. | Extend this real tool contract with optional validated slug plus explicit route discriminator; thread context to existing child controller. Bootstrap errors must map after child HANDOFF/return settles to stable safe code/text/retryability, not `ToolResult.ok` with a nonzero child exit. Preserve non-bootstrap invocation behavior. |
| Acquisition/bootstrap | `src/fa/inner_loop/managed_acquisition.py::BootstrapNewProjectChoice` currently carries planner-selected project/increment slugs and free-prose roadmap/increment bodies. `workflow_controller.py::_stage_acquisition_choice`, `_install_bootstrap_project_with_detail`, `_admit_installed_plan` render/install three files and then immediately admit the increment. | Evolve this path, not a parallel bootstrap. On explicit create-new, chat slug is authoritative. **D-V2-9 (2026-11-21) replaces the bounded-payload split:** the planner is the *writer* of the installed documents (it holds the WRITE `PROJECT` view under `worklogs/<slug>/`), the harness owns the scaffold, the path allowlist and the metadata cross-check. See §"D-V2-9 — planner-as-writer" for the ratified design; the payload/renderer/`install_project` path for create-new is deleted, not extended. Keep SELECT_EXISTING separate and do not reinterpret a typo as creation. |
| Path/materialization authority | `src/fa/execution/publication.py::prepare_bundle/install_project` and `WorkspaceAuthority.install_project` implement a bound bundle, private staging, no-replace install, forward completion and uncertainty states — the **bootstrap** primitive. The **revision** primitive is separate and equally live: a WRITE view commits its whole tree through `STOP_VIEW → SEAL → PUBLISH` (`client.py:963–1030`), which is what every coder stage already uses. A `PROJECT` view is writable across `worklogs/`; only a `MUTATION` view is confined to `{"src","scripts"}` (`workspace.py:222–226`). | **D-V2-9 uses the revision primitive for create-new**, not the bundle: one stage publication, no install, no post-rename recovery branch. Reuse `RootedViewIO` path policy (no `..`, no dot components, no symlinks, `_BLOCKED_COMPONENTS`) and the authority's existing uncertainty handling. The acceptance closure ships **inside** the same committed revision (D-V2-5 unchanged); E657 retains the required isolated immutable-payload fallback if revision-backed custody cannot be proved. `install_project` stays for its other callers and is off this path. |
| Grammar/admission | `src/fa/inner_loop/plan_ids.py::precheck/extract_plan_ids` and `workflow_controller.py::_validate_plan_admission/_admit_plan` validate current grammar and gate coder; `_SLICE_CEILING = 7`. Runtime grammar is currently code-defined while `notes/artifact-schema-and-grammar.md` is conformance input. | Make the canonical Markdown schema the only V2 source; trusted installed runtime pins supported V2 grammar independently of project files. Add explicit project plan-format marker and reject unsupported/missing/mixed/V1 input before coder. Whole-project validator checks required artifacts and complete graph, not only an increment. Do not change parser in STEP9B. |
| Acceptance execution/custody | `workflow_controller.py::_pinned_verify_substrate` binds `ManagedVerifyCommandExecutor`; `slice_verification.py::verify_slice` and existing nodeid capture run tests from a pinned read view. `src/fa/execution/profiles.py` defines managed no-network/read-only-rootfs restrictions. Existing V1 does not prove stable TEST-ID→nodeid graph or complete closure custody. | Reuse managed runner, not a parallel runner. Resolve selector to exactly one nodeid, pin tests plus transitive support/config/fixture/driver/runner closure, expose identical bytes read-only to coder, and have verifier execute that exact seal. Missing or ambiguous closure is fail-closed; no host fallback. Read-only enforcement already has a live seam: `RootedViewIO(protected_paths=…)` is fed `plan_ref.workspace_relative_path` at both construction sites (`src/fa/execution/view_io.py:119–158`, `workspace.py:2188–2196` and `2808–2816`) and refuses writes to those paths **and their ancestors**; the closure is not in that tuple today. Shell access is separate: a writable view can write the closure; Q-V2-MODEA-1 was resolved to D-V2-6; E657 amends that decision to require true read-only shell projection, with immutable-payload fallback if revision-backed projection cannot be proven. The old plan-only protected-path observation predates CT-3.3. |
| Tick ownership | Canonical schema assigns tick updates to harness, but source audit found no production Markdown tick producer; run/admission status is not equivalent. | Add production harness-owned V2 tick producer and verify it at the host witness. Arena plan editing is not constrained by the production rule. Do not infer ticks from workflow status records. |

### V2 artifact and grammar contract to be ratified in the canonical schema

The current `artifact-schema-and-grammar.md` is the V1 artifact contract; it is not already a V2 parser/schema. STEP9B defines this target here, and the first implementation slice must update that one canonical document, its skills and conformance tests together. This linked plan is not a second runtime schema. At cutover the unified `invoke_workflow` route uses only this versioned contract with no V1 or legacy `fa workflow` fallback.

**Fixed project-root manifest (all paths relative to `worklogs/<project_slug>/`):**

| Path | Writer / authority | V2 role |
|---|---|---|
| `roadmap.md` | Harness writes fixed metadata/version; planner writes semantic body | Exactly one roadmap, explicit `Plan-Format: AI-NATIVE-PLAN-V2`, project slug and creation date. Any status/active-increment display is a deterministic authority projection under Q-V2-STATUS-1, not a post-seal planner edit. |
| `notes/ledger.md` | Harness initializes; agents maintain working content | Writable without re-admission/reseal; a working journal, not an authoritative PASS or admission input. Runtime evidence remains independently bound to its run, plan, seal and candidate. Nested MUTATION scope is amended by Q-V2-WRITE-SCOPE-1=A, implementation open. |
| `notes/open-questions.md` | Planner writes/resolves working records; harness validates semantic decisions | Required working artifact with bounded Q records; no interactive ask dependency. Ordinary edits and planner best-effort resolution need no automatic reseal or mandatory human approval; a gate must validate and bind the decision it relies on. Changes to an admitted plan/oracle require the appropriate new revision/admission/seal. |
| `increments/increment-01-initial-plan.md` | Harness writes fixed metadata; planner writes semantic plan; tick mutation is gated by Q-V2-STATUS-1 | `initial-plan` is harness-fixed, not a planner field. Explicit same `Plan-Format` marker; one active new-format increment. Contains invariants, optional scenarios, SLICE/CT/STEP declarations, acceptance selectors and kill-target mappings. Semantic bytes stay immutable after seal; any update requires new revision/re-admission/seal. |
| `acceptance/tests/` plus all referenced `acceptance/` support/fixture/driver files | **Planner writes them directly** (D-V2-9), confined to `worklogs/<slug>/acceptance/` by the stage allowlist; immutable after seal | New, project-scoped acceptance root; selected to avoid mixing these sources with repository harness tests. V2 selectors are workspace-relative `worklogs/<project_slug>/acceptance/tests/<path>.py::nodeid`, formed by the planner under the scaffold's front matter (no renderer expands anything). The only paths written are beneath `worklogs/<slug>/acceptance/`; the closure's own `pytest.ini` is written by the scaffold **inside** that root and is bound by the seal's digest like every other closure file (Q-V2-ACC-1: keys are allowlisted, `acceptance_closure.py:266`), while the runner itself is a trusted existing workspace input, never planner-overwritten. The authority refuses absolute paths, `..`, dot components and symlinks at the write boundary (`view_io.py:226–234`, `_BLOCKED_COMPONENTS` `:28`); admission additionally refuses selectors resolving outside the closure. `TEST-ID` selectors are the sole source of nodeid membership; legacy slice-wide `TESTS:` lists are not accepted on this route. |

This is a new fixed root, not a discovered production convention. It is chosen because the existing managed verifier accepts workspace-relative pytest paths and runs from workspace root (`slice_verification.py::capture_test_nodeids`, `:825–845`; `verify_plan`, `:2371–2408`), and the authority install path already constrains bundle files under `worklogs/<slug>` (`workspace.py::_install_file_record`, `:3637–3654`). SLICE3 C1 must actually collect/import/run a project test at this exact path through the managed runner; if it cannot, fail closed and replan before implementation rather than silently relocating paths or adding a runner. This suite is distinct from the repository's `tests/test_ai_native_*.py` harness tests that exercise the implementation.

**Machine-checkable V2 grammar delta:** retain frontmatter ownership and roadmap/increment layout, with the E695 ledger location, `## SLICE<n>` sections, typed CT classes and STEP syntax from the canonical artifact contract, with the explicit V2 step-exit extension below. The exact version field is `Plan-Format: AI-NATIVE-PLAN-V2`, occurring exactly once in roadmap and once in each admitted increment; reject missing, duplicate, mismatched markers, extra active-increment ambiguity and mixed V1/V2 tokens. Inside an increment, strict `## INVARIANTS` entries use one heading `### INV-<n>` and exactly one each `TEXT: <criterion>` and `EVIDENCE: TEST_REQUIRED | NON_EXECUTABLE`. **There is no severity field (D-V2-10).** `KIND: HARD | SOFT` is removed: its single consumer exempted an invariant from having any evidence, so a label that reads as policy while obliging nothing was the mechanism by which an uncovered contract entered an admitted plan. The obligation is a property of the **graph**, not of a label: every contract is discharged exactly once — a `TEST_REQUIRED` contract needs a selector that resolves to exactly one collected nodeid, and a `NON_EXECUTABLE` contract needs a grant the **caller** supplied through the disposition pipeline. So `NON_EXECUTABLE` is legal for any contract, including a critical one, but only the caller can make it legal; a plan cannot grant itself an exemption, and no class of invitation ("soft") exists to reason from. `PRESERVATION` contracts are never dispositionable. Severity, if a real consumer ever needs it, arrives as a separate `SEVERITY` field with its own reader and test (SLICE4) — not as a resurrection of `KIND`. Optional strict `## SCENARIOS` entries use one heading `### SCN-<n>` and exactly one each `PATH: <scenario-path>`, `TRIGGER: <condition>`, `OUTCOME: <observable-result>`, `CT-ID[]: CT-<slice>.<n>[, ...]`; no implicit CT edges. Within each slice, the grammar is:

```markdown
Plan-Format: AI-NATIVE-PLAN-V2

## INVARIANTS
### INV-<n>
TEXT: <criterion>
EVIDENCE: TEST_REQUIRED | NON_EXECUTABLE

## SCENARIOS
### SCN-<n>
PATH: <scenario-path>
TRIGGER: <condition>
OUTCOME: <observable-result>
CT-ID[]: CT-<slice>.<n>[, ...]

## SLICE<slice>: <name>
STEPS: prescriptive | outcome
CONTRACTS:
  CT-<slice>.<n> [FUNCTIONAL|CONSTRAINT|PRESERVATION] INV: INV-<n>: <acceptance criterion>
ACCEPTANCE:
  TEST-ID: TEST-<slice>.<n> | CT: CT-<slice>.<n> | SELECTOR: worklogs/<project_slug>/acceptance/tests/<path>.py::test_name
KILL-TARGETS:
  CT: CT-<slice>.<n> | TEST-ID: TEST-<slice>.<n> | SITE: DEFERRED
STEP-EXIT-CHECKS:
  CHECK-ID: CHECK-<n> | STEP: STEP<n> | TEST-ID[]: TEST-<slice>.<n>[, TEST-<slice>.<n>...]
- [ ] STEP<n>: <imperative> EXIT-CHECK: CHECK-<n>
```

**Example status:** the `KILL-TARGETS` row above is the D-V2-13 target shape, not accepted by current `plan_v2.py`;
its pinned-site alternative and atomic cutover are specified in SLICE3 below. All other current/target differences
remain as recorded by the slice status.

**Two positional facts the block above encodes and the parser enforces** (recorded because both were got wrong in
review, 2026-11-20): `STEPS: <mode>` is the *mode line* and there is exactly one per slice — a second `STEPS:` header
whose value is empty is refused as `slice-<n>-steps-mode`, so a step list never gets its own heading; and a step line
is a slice-level list item, not a member of any typed bucket, so it must not appear inside `STEP-EXIT-CHECKS:`'s
block. A renderer that emits either shape produces bytes admission refuses.

**Who writes plan bytes (D-V2-9, ratified 2026-11-21 — supersedes D-V2-7).** The planner **writes the installed
documents directly**. It runs with a WRITE `PROJECT` view and the ordinary file tools; the harness writes nothing
into `worklogs/<slug>/` except the scaffold the planner will fill. D-V2-7 (typed payload → controller renders every
byte) is **withdrawn**: it imposed an orthogonal serialization on a model that already writes Markdown well, and it
cost ~3 600 lines of renderer/parser/payload code that existed only to move bytes between two representations of the
same grammar.

Original D-V2-9 rationale (source observations and proposed behavior, not proof of safe
custody or create-new admission; E657/E679 and E696 below govern current status):

* **A WRITE `PROJECT` view can write `worklogs/`.** Only a `MUTATION` view is confined to `_MUTATION_ROOTS = {"src",
  "scripts"}` (`workspace.py:222–226`, `_purpose_write_policy` `:2843–2855`). The earlier barrier was the planner's
  *tool list* (`ACQUISITION_TOOLS`, `profiles.py:443`) and its *stage read-only flag* (`cli.py:2091`) — configuration,
  not an authority invariant.
* **Publication is a separate lifecycle.** `STOP_VIEW → SEAL → PUBLISH` commits a view revision, with explicit
  uncertain/failure states; it does not prove individual writes or recovery cannot be lost.
* **Mode A is not yet established.** Rooted file-IO protection does not constrain shell writes; complete
  acceptance closure and private seal wiring remain unproved, so E657 blocks coder dispatch.
* **Collision needs more than a single file check.** `expected_sha256=None` checks absence of the roadmap file;
  it does not by itself prove that an existing empty/incomplete project directory is rejected or handle races.
  The actual inventory/admission and effect-boundary no-overwrite path need their own proof (CT-2.2/2.7).

Authoring split (the whole design):

| Path | Written by | Enforcement |
|---|---|---|
| `roadmap.md`, `notes/open-questions.md` | planner; agents may edit working notes | path allowlist `worklogs/<slug>/`; trusted validation/binding for any decision used to gate scope (§D-V2-9.3, E695–E696) |
| `increments/increment-01-initial-plan.md` | planner (repair rewrites only this file) | same |
| `notes/ledger.md` | planner and agents | Working journal; ordinary edits/appends do not require reseal (E686). Harness-created scaffold is not an authority for later verdicts. |
| `acceptance/tests/**` (+ support it imports) | planner | confined under `worklogs/<slug>/acceptance/` |
| `notes/**`, `reviews/**` | planner and scope-authorized agents | working material; `notes/open-questions.md` is a planned Q source and must not be assumed unread by admission or gates |

**D-V2-9.1 — one commit, no intermediate state.** The scaffold is written by the harness *inside* the planner's
stage, through the same port the model uses:

```
planner stage opens WRITE PROJECT view @ rev_N
  → harness writes the scaffold (empty documents: frontmatter + section headings, no bodies)
  → planner writes the documents
  → lease.finish(accepted) → STOP_VIEW → SEAL → PUBLISH → one revision
  → admission reads that revision
```

A definitively rejected pre-publication stage calls `reject_view` (`composition.py:413`); its
private scaffold must not become a new canonical project. An already existing project remains
untouched. Publication uncertainty is different and requires reconciliation; do not claim
no project exists before resolving it. F5 concerns intermediate project visibility, not a
reason to bypass failure/uncertainty checks. `prepare_bundle` / `install_project` / `_BootstrapReceipt` do **not**
participate in V2 create-new. They stay in the codebase for their other callers; the create-new path stops calling
them and the bundle renderer is deleted with the payload layer.

**D-V2-9.2 — collision is `project_exists`, not `stale`.** The first create-only write returns `STALE_REVISION` from
the authority, but the model must not see the generic text `"workspace refused the write: stale"`. The planned-file
writer maps *expected-absence refusal on `roadmap.md`* to `project_exists` with actionable text ("`worklogs/<slug>/`
already exists; select the existing project"), which is the same stable code `invoke_workflow` already returns
(CT-2.2, CT-2.5). An existing incomplete directory is not established by a file-absence check alone; the
inventory and effect-boundary no-overwrite behavior and their race handling require proof.

**D-V2-9.3 — metadata is cross-checked, not authored by the harness.** Admission verifies a closed table; it does not
rewrite the file. `parse_plan` currently strips frontmatter and never validates it (`plan_v2.py:252–264`, `:688`),
so this table is new work and **is part of this slice**, not an existing guarantee:

| Field | Rule | Why this strength |
|---|---|---|
| `Plan-Format:` | exactly one per document, value `AI-NATIVE-PLAN-V2` | already enforced (`_require_marker`, `plan_v2.py:267–272`) |
| `Roadmap-ID:` / `Increment-ID:` | exactly one, `RM-<slug>` / `RM-<slug>-I01` | identity is caller authority; a model must not rename the project or the increment |
| `slug:` in `roadmap.md` | equals the view's `worklogs/<slug>/` component | same |
| `active-increment:` in `roadmap.md` | names the one admitted increment | the roadmap cannot point at a plan that does not exist |
| `status:` | member of the canonical vocabulary; **any legal value is accepted** | the planner legitimately chooses the lifecycle state; admission does not dictate `IN PROGRESS` |
| `created:` | any valid date, and identical across the project's documents | free-form value, one-fact consistency |
| absent `Roadmap-ID` in `open-questions.md` / `ledger.md` | not required | those documents are not part of the admitted pair |

Everything not in this table is the planner's content. The check is one table walk over the three admitted
documents — flexible by construction, because it names only the fields that must agree with something else.

**D-V2-9.4 — `render_project`'s self-check moves into admission, with no loss.** Today a bad payload is refused
before bytes exist because `render_project` parses its own output. After D-V2-9 the model can write an inadmissible
plan; the refusal becomes `plan-format-*` / `slice-*` rules from `parse_plan` at admission, and the repair round
(`_run_admission_repair_with_receipt`, `workflow_controller.py:3719–3770`) hands the planner the sanitized
diagnostics against the **published file** rather than a private candidate. Net guarantee is unchanged: no coder sees
an unadmitted plan. What changes is *when* the bad bytes are visible: in the revision history rather than nowhere.
That is the accepted cost, and it is what makes repair possible against the real artifact.

**D-V2-9.5 — `plan_ref` is null on the authoring stage.** `_validate_plan_boundary` (`publication.py:336–353`) freezes
the plan path, its ancestors and its descendants. If the authoring stage carried a `plan_ref` pointing at
`worklogs/<slug>/increments/`, its own first write would be refused. The authoring stage therefore runs with
`plan_ref=None` (the same shape `_pinned_acquisition_substrate` already uses, `workflow_controller.py:2596–2610`), and
CT-2.4 stays true because there is no admitted plan to protect yet. `PlannerDispatch` must make this explicit rather
than rely on the null default.

**D-V2-9.6 — the planner's write surface is an allowlist, not a new policy engine.**
`build_registry_for_role` already routes `planner`+`fs_write_file` through the limited writer
(`profiles.py:495–499`), whose allowlist is `PROFILES_RAW["planner"]["write_allowlist"]`
(`profiles.py:151`) and whose second gate `_planner_target_allowed` (`:238–256`) already refuses `.fa/admission`
and the active plan. The create-new stage passes `allowed_paths=("worklogs/<slug>/",)` for that stage only; the
module default is unchanged, so an ordinary planner keeps its current narrow allowlist. Nothing new is invented:
one parameter of an existing function, threaded to a stage.

Ordering constraint that follows from the above: the scaffold must be written **before** the planner's first tool
call, and the `roadmap.md` create-only write must be the **first** write of the stage. If it is not, a failed stage
leaves directories behind that `reject_view` cannot remove (they would only exist inside the rejected view's private
tree, so this is a hygiene rule, not a durability one).

**D-V2-9.7 — an empty directory cannot be materialized; the scaffold must carry a file in each root.** Source fact:
the view writer has **no mkdir primitive** (`grep -n "def mkdir\|def create_directory" view_io.py workspace.py
tool_port.py` → nothing), directories exist only as parents of a written file (`view_io.py:442`,
`_parents(create=...)`), and dot-only names are refused as path components (`_parts`, `view_io.py:83` rejects `""`,
`"."`, `".."`; `_write_bundle_file` additionally refuses any component starting with `.`, `workspace.py:3454`). So
`notes/.gitkeep` is **not** a legal write and an empty `notes/`, `reviews/` or `acceptance/tests/` simply does not
survive into the revision. The scaffold therefore writes a real file in every root it must create:
`notes/README.md` and `reviews/README.md` (one paragraph each, harness-authored), and
`acceptance/tests/test_acceptance_placeholder.py` — a module with **no test functions**, which collects to zero and
cannot become a passing oracle. `acceptance/` gets no other support directory until the planner creates one by
writing a file into it.

**D-V2-9.8 — repair must not go through the candidate buffer.** Source fact: `seed_plan_candidate` refuses any kind
except `ADMISSION_REPAIR`/`EVAL_REPLAN` (`plan_promotion.py:85–86`), writes the draft to
`.fa/admission/<run>/candidate-*.md` (`:87`), and `publish_candidate_plan` commits **one** file at that pinned
`PlanRef` (`workspace.py:4059+`). A create-new authoring stage owns no candidate, and a repair that rewrote only the
increment would leave `roadmap.md`/`notes/open-questions.md` unrestorable and would publish a revision whose other files
still hold the refused content. Therefore the repair for a create-new project is **not** the candidate path: it is a
second authoring stage over a WRITE `PROJECT` view opened at the revision the first stage published, whose allowlist
is narrowed to the current repair families: roadmap, initial increment, `notes/open-questions.md`
and acceptance subtree, as needed for repairable refusals (E607; notes path is the E695 target,
not yet implemented). Two consequences the implementation must honour:

* if the second stage carried `plan_ref=<the published increment>`, `_validate_plan_boundary`
  (`publication.py:336–353`) would refuse the intended repair. Instead the repair stage uses
  `plan_ref=None` and the narrowed repair families; the E695 notes path must be wired and
  verified. Do not use an unscoped authoring stage as a substitute for that boundary.
* `admission.planner_calls`/`planner_limit` continue to bound retries exactly as today
  (`workflow_controller.py:4082–4090`); no new budget concept is introduced.

**D-V2-9.9 — the scaffold file set is the *only* harness write, and it is idempotent-by-construction.** Because the
harness never rewrites a scaffold file after the planner has touched it, a second authoring stage (repair) writes no
scaffold at all: it opens the view at the published revision and hands the planner the diagnostics. This keeps the
"harness writes only the scaffold" rule true for every stage, not just the first.


The production grammar must require one primary INV on each CT; each TEST-ID belongs to one CT and one exact selector; selectors resolve to exactly one collected nodeid (including stable parametrized IDs); every target maps to exactly one CT and TEST-ID; SCN contains explicit CT-ID[] edges and derives TEST membership; every CT is discharged exactly once at the contract-evidence level, by one or more selectors each resolving to one collected nodeid or by a typed disposition the caller granted — no severity, no exempt class, and no `ready` state to argue about. Reject duplicate IDs, dangling edges, multiple primary INV, missing evidence, duplicate selector ownership, uncollected/ambiguous selectors, unknown fields and orphan V1 `TESTS:`/kill syntax. The schema's prose example and parser/conformance tests must agree byte-for-byte on these names/cardinalities; this plan does not claim runtime parsing exists.

**Trusted schema pin:** the deployed source is the single canonical `notes/artifact-schema-and-grammar.md` in the approved read-only `/repo` mount; installed runtime must read it only from that fixed trusted control-plane path and verify its content digest/version against build-time trusted metadata. Never load it from `worklogs/<slug>`, `ctx.workspace`, a planner payload or an editable project copy. Missing path, digest mismatch, malformed canonical document or unsupported version fails closed before provider/coder. Local tests inject a fixed trusted schema fixture; host test proves installed path+digest match the approved source/image. This chooses a packaging/runtime boundary without copying a second normative schema; record the digest with run evidence. The image/approved checkout update mechanism must ensure both are the same candidate SHA before execution.

**Question and status records:** `open-questions.md` uses one stable `Q-ID` per record with exactly: `Question`, `Affected-IDs` (INV/CT/SCN/SLICE), `Status: OPEN | RESOLVED | REPLAN`, `Options`, `Selected`, `Rationale/Evidence`, `Owner`, `Updated`, and optional `Replan-Ref`. OPEN blocks only listed dependent scope; RESOLVED requires a selected option and concise evidence; REPLAN blocks only affected scope and points to owner/replan work. A planner may resolve ordinary product questions best-effort; no model may rewrite a ratified INV under a Q resolution.

For status ticks preserve canonical vocabularies: increment `OUTLINED→READY→IN PROGRESS→SHIPPED`; CT `PLANNED→IMPLEMENTED→VERIFIED`; STEP `[ ]→[>]→[x]`. V2 `STEPS: prescriptive` and `STEPS: outcome` both require every STEP to reference one unique machine-checkable `EXIT-CHECK-ID`, mapped only to one or more same-slice TEST-IDs; command text is never planner-authored or executed for tick promotion. Every referenced TEST-ID must already have one exact collected nodeid under the normal acceptance graph. No free-text exit can drive a status. On coder dispatch the harness marks only the first unfinished step `[>]`. After verification, the harness marks `[x]` only for the sequential prefix whose sealed exit checks passed; the first failed/unavailable step remains `[>]`, later steps remain `[ ]`. A retry resumes from the first non-done step; stale/replanned plan revisions get new status lineage. Only harness code writes these fields. CT `IMPLEMENTED` requires implementation evidence; CT `VERIFIED` requires the canonical full criteria (verify pass, non-vacuity and passing L2 contract judgment). If MVP does not provide L2 judgment, keep CT at `IMPLEMENTED`; pytest/host pass cannot imply `VERIFIED`.

**Status-producer design gate (confirmed integration risk; do not implement the presumed seam yet):** current managed plan publication is a same-path forward-only replacement of one candidate buffer under a pinned `PlanRef` (`publication.py:740–775`; `workspace.py:4059–4130`); it is not a general harness metadata writer. V2 seal/admission also binds the plan and acceptance closure to revisions. Therefore editing STEP/CT tick text in an admitted increment may invalidate the very plan ref/seal that authorized coder/verifier and can re-enter planner admission; publication of a changed plan is not equivalent to status metadata update. Before SLICE4 implementation, source-audit the full seal, plan-admission and publication call graph and prove one safe design: (A) a distinct authority-owned revision-bound status record with a deterministic host-visible Markdown artifact/projection that does not mutate sealed semantic bytes; or (B) a deliberately re-admitted, re-sealed new plan revision on each tick, preserving exact acceptance bytes and safely resuming all workflow state. If neither is proven using existing authority and durability semantics, SLICE4/5 are blocked for a scoped design decision; no host filesystem writer, generic PROJECT grant, or silent seal bypass. CT-4.2 tests the selected design only after that gate. CAS conflict, unresolved receipt or stale revision is non-success and must use existing exact-request reconciliation/fencing. Do not claim atomicity with session-log artifacts.

### Target lifecycle and visibility barrier

**D-V2-9 lifecycle (supersedes the install-based row for create-new):**

`NEW_REQUEST → SLUG_VALIDATED → STAGE_VIEW_OPENED(WRITE/PROJECT) → SCAFFOLD_WRITTEN → PLANNER_AUTHORED → STAGE_PUBLISHED(one revision) → METADATA_CHECKED → PLAN_ADMITTED → REVISION_BOUND_ACCEPTANCE_SEAL/ADMITTED → CODER → PINNED_VERIFY → TERMINAL_RESULT`

Every transition before `STAGE_PUBLISHED` is private to one view and disappears if the stage is rejected
(`composition.reject_view`, `composition.py:413–433`). There is no `PRIVATE_VALIDATED_PAYLOAD`, no
`NO_REPLACE_INSTALL`, and no post-install recovery branch on this route: the authority's ordinary
`STOP_VIEW → SEAL → PUBLISH` saga already owns intent, pointer, projection and `DURABILITY_UNKNOWN`
(`workspace.py:5110+`, `client.py:963–1030`). Failure behaviour is therefore the *existing* stage failure
behaviour, not a new state machine:

- **Stage refused or crashed before publish** → `reject_view`; no `worklogs/<slug>/` exists; canonical tree and
  current revision unchanged; the child run reports a structured failure (CT-2.5).
- **Publish uncertain** → the existing `DURABILITY_UNKNOWN` path; the writer is not released, the run blocks, and
  recovery is the authority's. Never retried as a new operation.
- **Published but admission refused** → the revision exists and is history; coder is never dispatched; the repair
  round rewrites `increments/increment-01-initial-plan.md` and publishes a second revision (D-V2-9.4). A run that
  exhausts its repair budget ends `BLOCKED` with the project present and unadmitted — that is an honest, inspectable
  end state, and CT-2.9 requires that no coder ever sees it.
- **Collision** → `project_exists` on the first create-only write; nothing published (D-V2-9.2).

Once admitted, roadmap/increment semantics, the admission decision and acceptance oracle remain protected;
semantic changes require a new authoritative revision and repeat validation/admission/seal. E686 supersedes the
former project-wide immutability of `ledger.md`, `notes/` and `e2e/`: they are working artifacts, writable without
reseal and not authoritative verdicts. Question records continue to block dependent scope as specified; the safe
mechanism for their post-admission evolution must not silently change admitted semantics. Runtime evidence remains
run-scoped and status projection follows Q-V2-STATUS-1; neither may silently rewrite sealed semantic inputs.

**What D-V2-5 still governs:** the revision-bound `AcceptanceBundle` mint (closure inside the installed revision,
seal derived from the committed bytes + plan bytes + revision receipt) is unchanged — only the way the revision is
produced changed. `notes/q-v2-boot1-install-seal-audit-2026-11-20.md` E1–E9 remain the recovery reference for the
seal half; its install half no longer applies to V2 create-new.

## 3. Global semantic invariants and graph

| INV | Required invariant |
|---|---|
| INV-01 | Only the trusted runtime-selected canonical V2 grammar can admit a project; missing, unknown, mixed, or V1 format fails before coder. |
| INV-02 | A new project is created only by explicit create-new intent; chat-supplied slug is validated at tool and authority boundaries and never silently substituted or overwritten. |
| INV-03 | The harness materializes only a closed fixed scaffold, and the planner may write only inside `worklogs/<slug>/` through the ordinary view writer. The planner never receives a destination path it can choose outside that root, never names the project or the increment, and never holds a generic workspace write capability. (D-V2-9 supersedes the D-V2-7 "planner semantics only, no writes" form.) |
| INV-04 | No provisional/unvalidated/unsealed plan reaches coder. Every role sees only its declared capability; coder cannot mutate the plan or the acceptance closure. A published-but-unadmitted revision is an audit fact, never a coder input (D-V2-8). |
| INV-05 | Every admitted CT is discharged **exactly once** — an executable selector that resolves to exactly one collected nodeid, or a typed disposition the caller granted — and the `INV→CT→TEST-ID→selector` graph is complete. No `KIND`, severity or class exempts a contract (D-V2-10); the seal records the contract total and attests every one of them, so a contract cannot disappear between the graph and the evidence (P4-2). |
| INV-06 | AcceptanceBundle binds canonical plan and full acceptance source/config/support/helper/fixture/driver/runner closure to immutable workspace revision; verifier executes that same closure. |
| INV-07 | Mode A is actually read-only across file tools and shell (D-V2-6 as amended by E657); post-hoc drift detection alone does not satisfy it. The authority protects the full sealed closure and relevant ancestors, and the verifier executes the same pinned bytes. If revision-backed projection cannot prove this, use the isolated immutable-payload fallback. No differing acceptance bytes may produce a verdict. Unsupported mode B, missing/stale seal, ambiguous mapping or incomplete closure fails closed. |
| INV-08 | Kill outcome is attributable only to its exact mapped TEST-ID/nodeid assertion against the pinned revision. Other outcomes never imply PROVEN. |
| INV-09 | Planner TEST-DEFECT cannot mutate sealed evidence in place; new revision, evidence lineage and affected gate reruns are required. Ratified semantics change only via replan. |
| INV-10 | V2 STEP/CT status ticks are produced by production harness code and observable on the host; status projections do not substitute for artifact ticks. |
| INV-11 | Every refusal/partial/uncertain state has a stable structured result and safe actionable text; no child failure is surfaced as success. |
| INV-12 | A fresh V2 project succeeds only through real chat→`invoke_workflow`→managed controller/authority→planner→coder→managed verifier composition; component/parser-only tests are insufficient. |
| INV-13 | Exactly one production entry point exists (D-V2-2): the `invoke_workflow` composition, reachable by an agent and by a human; no parallel manual workflow route survives that can run a plan. |

All `CT`s below have exactly one primary `INV`, and every plan-local TEST-ID maps to exactly one CT and one exact repository pytest nodeid. These tables are the refactor's implementation-test/harness map only: their `tests/test_ai_native_*.py` selectors are not valid project V2 acceptance selectors and are not materialized into a fresh project's AcceptanceBundle. In a runtime V2 project, TEST-ID selectors must use the fixed `worklogs/<project_slug>/acceptance/tests/...` closure defined above. Keep the two inventories and evidence claims separate. Tests may assert secondary invariants, but primary mapping is unique; coder-added support/regression tests do not become project acceptance/kill oracles without a new sealed project revision.

## 4. Position in I03 and remaining W2–W4 work

This plan is an E530/E546 exceptional **W3 planning input**. It is not W2 work and is not a W4 host run sheet. Current dependency/status is:

| Order | I03 state / blocking work | Relationship to this plan |
|---|---|---|
| W2 | **CLOSED Arena-locally** by E526–E527. Nested `invoke_workflow`, acquisition, lease/return, selection/bootstrap and Q66 local composition are predecessors only; W4 host witnesses remain open. | Reuse these seams; do not reopen or claim their local closure proves V2. |
| W3 / STEP9 | **LOCAL-CLOSED** (SLICE6 STEP9 `[x]`, E556/E558). Four local exit families were reproduced; Q139 remains `DEFERRED` under E544. Other W3 and W4 work remains open and is not evidence against this specific tick. | STEP9 no longer blocks STEP9A; this closure does not close STEP9A, STEP9B, W3 or host acceptance. |
| W3 / STEP9A | **OPEN and gated by STEP9.** Implement and locally prove artifact-C `AcceptanceBundle`, mode-A shell+file read-only custody, full closure, exact target attribution, pre-code gate and TEST-DEFECT lifecycle for the new plan path; immutable-payload fallback if C cannot prove custody/projection. | The new slices consume this mechanism; they must not build a second custody/kill engine. |
| W3 / STEP9B | Planning-only gate after STEP9 and STEP9A. | This document is presently an early review draft. Only after predecessor evidence is reproduced and this plan is independently reviewed, links/grammar structure pass, and gaps below are resolved may STEP9B be marked complete. No product code starts before that. |
| W3 / new slices + STEP10 | After STEP9B, implement each new slice and pass its Arena-local DoD. Then resume remaining original STEP10 local package/review prerequisites and close W3 on Arena-local evidence only. | Slices 1–5 are the new I03 extension; no W4-only work may be pulled forward as proof. |
| W4 | **OPEN, after W3 closes.** Single approved `fa update`, identity/health/CLI smoke, freeze image, then reviewed `FA_REQUIRE_EXECUTION_HOST=1` suite: all required I01–I03 host cases, real clean readiness, nested/direct witnesses, new V2 witness, Q106 disposition and independent evidence review. No rebuild/update during suite. Q139 may be attempted only after suite capture and remains best-effort. | SLICE5 defines a future witness/package obligation; it is not registered/frozen/run and is not W3 acceptance. |

A roadmap summary line currently lists “candidate host `fa update`” among STEP9/W3 missing work, but the increment's controlling wave table and E544/E546 sequence put deployment/update in W4. This plan review corrects that summary wording only; W3 has no host-deployment prerequisite.

## 5. Slice DAG

All five slices receive semantic/acceptance completeness now. Only later coder work orders, exact helper/module layout, and internal sequencing remain rolling-wave. The DAG is:

```text
SLICE1 (V2 grammar/admission)
  ├── SLICE2 (slug + staged bootstrap) ─┐
  ├── SLICE3 (acceptance graph/custody) ─┼── SLICE4 (role + tick composition)
  └─────────────────────────────────────┘              │
                                                       └── SLICE5 (vertical proof + W4 witness)
```

**STEP9A wiring gaps and their owners (E564).** STEP9A shipped the mechanisms; nothing in production
calls them. The review found this set listed as prose in the ledger and assigned to no slice — each row below
is now a slice obligation, so the gap cannot be silently deferred:

| Gap (E564) | Owner | Contract |
|---|---|---|
| Nothing in the controller mints an `AcceptanceBundle` | SLICE2 (publish→seal, D-V2-5 on the D-V2-9 revision) + SLICE3 | CT-2.4, CT-3.2 |
| The coder never receives a mode-A projection | SLICE3 | CT-3.3 (prevention for file tools, detection for shell) |
| `verify_slice` still executes planner `verify` fences | SLICE3 | CT-3.6 (fence retired on the PLAN-V2 route) |
| No gate blocks on a missing or stale seal | SLICE3 | CT-3.2 (admission refuses before coder) |
| `sealed_collection_argv` is not wired into the verifier path | SLICE3 | CT-3.6 |

STEP9 and STEP9A are increment prerequisites to all five. STEP9B completes only when this plan and its link/artifact checks are reviewed; implementation starts only after that gate. Each slice's Arena-local DoD is required before STEP10. W3 core close then precedes W4 deployment/host acceptance per parent STEP10.

### SLICE1: Canonical V2 grammar, strict graph validation, and admission cutover

**STEPS:** outcome<br>
**DEPS:** STEP9, STEP9A<br>
**INTENT:** Establish the single canonical V2 Markdown contract and a trusted, version-pinned parser/validator. Stop V1 or partial/mixed plans before coder without changing the human-only I03 parent.<br>
**Production producer/caller:** update the canonical `notes/artifact-schema-and-grammar.md`, its conformance consumer `tests/test_skill_grammar_emit.py`, and the V2 grammar instructions in `knowledge/skills/feature-planning/SKILL.md`, `knowledge/skills/plan-authoring/SKILL.md`, and `knowledge/skills/tests-writing/SKILL.md` (plus their `INJECT.md` surfaces); **bind the already-implemented** `src/fa/inner_loop/plan_v2.py::parse_plan` (`:674`, 45 local tests, 22 killed mutants) — do **not** write a second parser and do **not** touch `plan_ids.py` beyond freezing it — through `plan_admission.py::PlanSnapshot` (add `format` + `graph`), `workflow_controller.py::_admit_published_project` (`:3141`, which binds the plan from the published revision) and `workflow_controller.py::_validate_plan_admission` (`:3427`, V2 branch `_validate_v2_admission` at `:3476`). The format is chosen by the **route** (new-project bootstrap ⇒ `PLAN-V2`), never by sniffing the document; V1 keeps its own path untouched and is scheduled for deletion. Caller/EDGE is the real managed initial planner→admission→coder flow via `workflow_controller.py::_run_stage` (`:1601`, the shared pre-coder choke point whose coder gate is `:1634`) and `run_workflow`; `_run_role_loop` funnels initial, linear and adaptive role passes through it, including adaptive rounds. Do not put the barrier in one mode loop.<br>
**Planner-owned acceptance:** extend the existing `tests/test_ai_native_plan_v2.py` (45 parser tests today) with the admission selectors below; do not create a second bank.<br>
**Evidence classes:** C0/C0p parser properties plus C1 managed workflow admission; C3 adversarial malformed/mixed/untrusted-version controls. Component tests alone do not satisfy the slice.

> **Reading the `TEST-` column.** Every row cites the name its control will have, and the
> name is checked against the tree: a cited test that is *absent* means the row's slice is
> not implemented yet (this plan is PLAN ONLY, §State above), not that the control was
> dropped. Measured 2026-11-21: 8 present, 19 absent, and the absentees are exactly the
> rows owned by SLICE2–SLICE5 plus CT-2.4 (SLICE2, §"Nothing in the controller mints an
> `AcceptanceBundle`"). Every CT-1.x row — the only implemented slice — is present.
> Slice status is tracked in §4 (W3/W4), not by this column.

| CT | Class / primary INV | Acceptance behavior | TEST-ID → exact selector |
|---|---|---|---|
| CT-1.1 | CONSTRAINT / INV-01 | The parser is selected by the **route**, never by the document: a new-project bootstrap snapshot is `PLAN-V2` even when its bytes contain no marker, a V1-looking body on that route is refused, and a `PLAN-V2` document never reaches V1 validators. | TEST-1.1 → `tests/test_ai_native_plan_v2.py::test_admission_format_comes_from_route_never_from_document_bytes` |
| CT-1.2 | FUNCTIONAL / INV-05 | Controller projects every `plan_v2` refusal as a stable bounded diagnostic code (`PlanV2Error.rule`), never as a raw exception or a repair prompt with prose; a passing graph reports `PASS` with the same parity as V1. | TEST-1.2 → `tests/test_ai_native_plan_v2.py::test_v2_admission_surfaces_closed_rule_codes_not_exceptions` |
| CT-1.3 | CONSTRAINT / INV-01 | A `PLAN-V2` document is never judged by V1 rules: absent `TESTS:`/`INTENT:` lines, V1 slice tokens or V1 kill syntax produce **no** V1 diagnostic, and the V1 `zero-slices` refusal cannot fire on a V2 graph. | TEST-1.3 → `tests/test_ai_native_plan_v2.py::test_v2_document_is_never_judged_by_v1_validators` |
| CT-1.4 | PRESERVATION / INV-04 | No production route dispatches a coder with `ctx.admission is None` (today `_admit_plan` returns `True` in that case, `workflow_controller.py:3740–3742`, on the strength of a comment); the control proves the public coder entry always binds authority, and that a V1 document on the new-project route is refused before provider/coder. | TEST-1.4 → `tests/test_ai_native_plan_v2.py::test_coder_never_dispatches_without_bound_admission_on_a_v2_route` (no-coder-without-admission) + `::test_v2_document_is_never_judged_by_v1_validators` (a V1 document is refused by the V1 route; the same document passes V2) |
| CT-1.5 | PRESERVATION / INV-13 | **Partially landed 2026-11-20.** `fa invoke-workflow` exists and calls the *same* `ToolSpec` a chat session registers (`build_invoke_workflow_tool` + `_make_workflow_ctx_provider`), so the operator path and the agent path are one composition: task/roles/mode/project fields go through the tool's own validation, a tool refusal maps to exit 2, and an ok result returns the child's exit code. `fa workflow` still runs (its help now states DEPRECATED and points at the new front) because 57 call sites across nine test modules drive it; **retiring it is a bounded follow-up**, not a silent defer: the remaining work is moving those call sites and deleting the plan-running surface with a refusal test. | TEST-1.5 → `tests/test_ai_native_plan_v2.py::test_invoke_workflow_cli_calls_the_same_tool_the_chat_registers` |

```verify
uv run pytest tests/test_ai_native_plan_v2.py tests/test_plan_ids.py tests/test_admission_v2_provenance.py tests/test_skill_grammar_emit.py tests/test_cli.py -q
```

**Prescriptive implementation order (SLICE1 is the first new implementation slice after STEP9B):**

1. Extend the existing planner-owned bank `tests/test_ai_native_plan_v2.py` (45 parser tests today) with the five admission selectors below. Do not create a second file and do not re-test `parse_plan`'s grammar rules — CT-1.2 owns only the controller-side projection of those rules.
2. Amend `notes/artifact-schema-and-grammar.md` plus `tests/test_skill_grammar_emit.py`, `knowledge/skills/feature-planning/SKILL.md`, `knowledge/skills/plan-authoring/SKILL.md`, `knowledge/skills/tests-writing/SKILL.md` and their `INJECT.md` surfaces in one change; no dual-format branching.
3. `plan_admission.py`: `PlanSnapshot` gains `format: str` and `graph: PlanGraph | None`; `snapshot_from_bytes(..., format="PLAN-V1")` keeps every existing caller's behaviour byte-for-byte, and `graph is None` ⇔ V1. Nothing else in `plan_ids.py` changes.
4. `workflow_controller.py`: `_admit_installed_plan` reads `worklogs/<slug>/roadmap.md` through the **same pinned substrate** it already uses for the increment (`:2846–2857`) — a roadmap read failure is `PlanRefError("bootstrap-unreadable")`, never a synthesized document — then passes `format=plan_v2.PLAN_FORMAT` and that roadmap text. `_validate_plan_admission` dispatches on `snapshot.format` — for `PLAN-V2` it calls `parse_plan(roadmap=…, increment=snapshot.text)` and **skips** `precheck`, `validate_kill_directives`, `snapshot.ids` and the `zero-slices` branch entirely. `PlanV2Error.rule` becomes the diagnostic code with outcome `INDETERMINATE`; `resolve_selectors` is **not** called here (it needs a collection and belongs to SLICE3).
5. Retire the legacy manual entry point per D-V2-2: `cli.py:848–956` parser and `_cmd_workflow` (`src/fa/cli.py:2200`) stops being a plan-running surface; the human path calls the same `invoke_workflow` composition the chat tool uses. Keep one implementation, not two.
6. Run the commands below (exit 0, no unreviewed skips), `uv run fa authoring-check`, `uv run ruff check` on the touched files, `uv run pyrefly check`, and `git diff --check`.

**Where the route switch is flipped (recorded 2026-11-20, after the first implementation increment).** The
format is carried by `WorkflowContext.plan_format` (default `PLAN-V1`, so every existing caller is unchanged)
and is set by the component that *renders* the artifact — the V2 bootstrap renderer in SLICE2. Until SLICE2
lands, the `PLAN-V2` branch has **no production caller**: it is reachable from tests and from any route that
sets the field, and the plan says so rather than implying a cutover that has not happened. That is deliberate:
the alternative, flipping to V2 by looking at the document, is exactly the content sniffing INV-01 forbids.
Consequence for sequencing: SLICE2 is no longer "the bootstrap slice", it is the slice that makes the cutover
real, and it starts before any further admission work.

**CT-1.5 state (2026-11-20).** The single entry point is real and human-callable; the legacy surface is
deprecated but not yet removed. Evidence for the front: `tests/test_ai_native_plan_v2.py` proves the CLI
builds the chat's own tool (a recorder on `build_invoke_workflow_tool`), that project fields reach the tool
unmodified, that a tool refusal becomes exit 2, that a missing task refuses before any lifecycle, and that an
ok result returns the child exit code — five mutants, 5/5 killed. What is *not* proven is a live end-to-end
manual run: the CLI context is the unmanaged shape by design (no parent stage lease), so a planner-led child
gets exactly what an unmanaged caller gets, and managed composition stays where it is proven (the chat
harness inside `fa run`).

**CT-1.5 gap — `dispositions` had no human ingress (found 2026-11-21, closed 2026-11-22 as P4-6).** `fa invoke-workflow`
forwards `project_action`/`project_slug` (`cli.py:2451–2452`), but not `dispositions`; the field exists only on
the tool schema (`workflow_tool.py:245`) and the parser has no flag for it (`cli.py:975–993`). That is not a test
gap — it is a capability gap: R1 makes the caller's grant the *only* source of owner/evidence, and a caller that
needs one `NON_EXECUTABLE` invariant has no way to supply it from the human front, so a legal V2 plan is
unreachable there while it is reachable from chat. A dispatch on the *unmanaged* shape is also the only context
where `_install_bootstrap_project_with_detail` can be exercised without a parent lease, which is what made the
gap invisible. Bounded fix, CT-1.5 scope: add `--dispositions <path-or-json>` to the `invoke-workflow` parser and
pass it through unmodified, exactly as the other two fields are; validation stays in the tool, so the CLI adds no
second rule. **Landed 2026-11-22 (E607):** `fa invoke-workflow --dispositions PATH_OR_JSON` exists and forwards the decoded value to the tool under the same rule the other project fields follow — the CLI is transport, `parse_dispositions` is still the only validator, and a value that is not JSON is refused before any lifecycle starts (a grant that cannot be decoded must not start a pipeline that then reports something deeper). Six mutants, 6/6 killed. What is still unproven is a *live* end-to-end run with a grant; that belongs to the same unmanaged-composition gap CT-1.5 already records, not to the flag.

**Failure/negative controls:** version marker cannot override runtime pin; project cannot load a grammar copy from its own root; malformed references never yield a partial admitted snapshot; no legacy fallback; no coder/provider call on rejection. The V1 negative and valid V2 positive use production admission, not only parser helpers. **Producer kill-check:** remove the V2 admission producer at `_validate_plan_admission`/its caller choke point and show the C1 admission test fails. **EDGE kill-check:** bypass the real admission→initial coder dispatch in `_run_stage`/workflow composition; assert coder is not reached or the live witness fails. Re-ground exact current call site before mutation; do not target a dead helper. **Local DoD:** all selectors pass without unreviewed skip; canonical schema, skills, parser and conformance fixtures agree; authoring/typing checks on changed files pass; no V1 fallback; test gate rejects before provider/coder. No deployment claim.

### SLICE2: Explicit chat slug and staged trusted bootstrap

**STEPS:** outcome<br>
**DEPS:** SLICE1<br>
**INTENT:** Evolve the existing nested acquisition/bootstrap route into a **scaffold-then-author** stage. Chat supplies project identity and route intent; the harness writes the fixed scaffold inside the planner's own stage; the planner authors the documents with the ordinary file tools; one atomic view publication produces the project; admission validates and seals it before coder. D-V2-9 replaces the typed-payload renderer on this route.<br>
**Production producer/caller — under D-V2-9, as landed.** P2-4 (E588) deleted the payload route: `_install_bootstrap_project_with_detail`, `plan_semantics.py` and the renderer are gone, so `publication.{prepare_bundle,install_project}` is **not** on this path any more (it keeps its other callers). The create route is `workflow_tool.py::INVOKE_WORKFLOW_SCHEMA/_prepare_invocation/build_invoke_workflow_tool` → child `run_workflow` → `workflow_controller.py::_stage_acquisition_choice` → **the planner stage itself** (`cli.py::_stage_with_ports`/`_build_stage_ports` → `_open_stage_view(write_purpose=PROJECT)` → `composition.publish_stage` → `STOP_VIEW/SEAL/PUBLISH`) → `workflow_controller.py::_admit_plan`, with `WorkspaceAuthority.{create_view,write_file,prepare_seal,publish}` (all already production-live) as the authority seam. Writing the target as present tense is the P0-1 defect in a different file: the plan would say a path exists that the code does not yet run.<br>
**Planner-owned acceptance:** `tests/test_ai_native_bootstrap.py` (new) and real composition tests in `tests/test_managed_workflow_e2e.py` / `tests/test_invoke_workflow_tool.py`; new selectors below. C1/C2/C3: actual chat tool composition, tool-schema/CLI boundary, adversarial slug/collision/path tests.

| CT | Class / primary INV | Acceptance behavior | TEST-ID → exact selector |
|---|---|---|---|
| CT-2.1 | FUNCTIONAL / INV-02 | Closed tool fields: `project_action: AUTO_SELECT_EXISTING (default) \| CREATE_NEW`; optional `project_slug`. Omitted action preserves the existing-project selection flow only; `AUTO_SELECT_EXISTING` can never create a project, and a planner `BOOTSTRAP_NEW_PROJECT` reply on that route is refused rather than installed. `project_slug` is accepted only with `CREATE_NEW` and required then; slug alone, slug with AUTO_SELECT_EXISTING, unknown action or invalid slug refuses before child/provider. CREATE_NEW requires managed execution and planner before coder. Planner bootstrap JSON omits `project_slug`; only chat context supplies it. Authority independently rechecks lowercase kebab-case/max-48/path confinement. | TEST-2.1 → `tests/test_ai_native_bootstrap.py::test_chat_slug_and_explicit_route_are_required_for_new_project` |
| CT-2.2 | CONSTRAINT / INV-02 | Invalid slug, traversal and malformed route refuse before provider. Collision returns stable safe code with no auto-slug, overwrite or existing-project fallback; collision discovered at install is still authoritatively refused after no-replace recheck. Existing tree and revision remain unchanged. Do not promise collision-before-provider unless a source-proven exact-path preflight closes the empty-directory/race gap. | TEST-2.2 → `tests/test_invoke_workflow_tool.py::test_an_invalid_slug_is_refused_before_any_child_exists` (ten shapes, including traversal) + `::test_a_slug_without_a_create_route_is_refused_before_any_child_exists` + `::test_an_unknown_project_action_is_refused_before_any_child_exists` (**present, E597**); the collision half of the old title is `::test_create_over_existing_directory_is_project_exists_and_unchanged` in `test_ai_native_bootstrap.py` (E596). Each asserts `workflow.calls == []`, so the control is the ordering, not the message. |
| CT-2.3 | FUNCTIONAL / INV-03 | **D-V2-9.** On `CREATE_NEW`, the planner stage opens a WRITE `PROJECT` view and the harness writes the fixed scaffold through that same port before the planner's first tool call: `roadmap.md`, `notes/ledger.md`, `notes/open-questions.md`, `increments/increment-01-initial-plan.md`, `notes/README.md`, `reviews/README.md`, `acceptance/pytest.ini`, `acceptance/tests/test_acceptance_placeholder.py`. The two notes paths are E695 targets, not yet implemented. The three roots exist **as parents of those files** (D-V2-9.7: the writer has no mkdir, dot-only names are refused, so no `.gitkeep`). Each admitted document carries its frontmatter and section headings with **empty bodies** — no placeholder invariant, slice or test, because `parse_plan` must refuse an unfilled scaffold (`missing-invariants`/`missing-slice`) rather than admit a fake plan; the placeholder test module defines no test function and collects to zero. The planner's write allowlist for that stage is exactly `worklogs/<slug>/`; the project slug comes from the caller and the increment slug is harness-fixed `initial-plan`. Nothing is written outside that root; the harness never writes a planner-authored byte into the project. | TEST-2.3 → `tests/test_ai_native_bootstrap.py::test_create_new_stage_scaffolds_then_planner_writes_only_inside_slug` (**present, E598**) |
| CT-2.7 | CONSTRAINT / INV-02 | **D-V2-9.2.** Existing complete and incomplete `worklogs/<slug>/` trees must be refused through the combined inventory and effect-boundary checks, with file create-only `STALE_REVISION` where applicable surfaced as `project_exists` (not `stale`), non-retryable and actionable, with the existing tree and revision byte-unchanged. No auto-slug, overwrite or fallback. Covers complete and incomplete existing directories, and a hostile or traversal-shaped slug is still refused before the child exists. | TEST-2.7 → `tests/test_ai_native_bootstrap.py::test_create_over_existing_directory_is_project_exists_and_unchanged` (**present, E596:** both halves of the guard -- the inventory decision, including the *incomplete* directory case, and create-only scaffold writes that leave the published tree byte-identical -- plus the ordering guarantee that the planner is never dispatched onto a refused create.) |
| CT-2.8 | FUNCTIONAL / INV-04 | **D-V2-9.3/9.4/9.8.** Admission validates the planner-authored documents against the closed metadata table (marker, `Roadmap-ID`/`Increment-ID`, `slug`, `active-increment`, `status` vocabulary, consistent `created`) and then `parse_plan`. A refusal blocks coder; the repair is a **second authoring stage** over a WRITE `PROJECT` view at the published revision whose allowlist admits roadmap, initial increment, `notes/open-questions.md` and acceptance subtree for repairable refusals (E607; E695 notes path still to wire), with `plan_ref=None` and sanitized diagnostics; its publication is a second revision that admission re-validates. No candidate buffer, no `.fa/admission` draft, no single-file publish. A legal but unexpected `status` value is accepted; a wrong identity field is refused. Unfilled scaffold, missing `notes/open-questions.md`, an increment outside `increments/`, and a repair attempt to touch any other file are refused. | TEST-2.8 → `tests/test_ai_native_bootstrap.py::test_metadata_table_and_parse_refusal_block_coder_then_repair_rewrites_published_file` (**present, E594:** two real stages -- a published pair whose `Roadmap-ID` disagrees is refused by `check_project_metadata`, then a second WRITE stage at that revision repairs the increment and admission binds it. Mechanism tests from E592 still stand: narrowed allowlist, dispatch-level scope validation, repairability/budget decision.) |
| CT-2.9 | CONSTRAINT / INV-04 | **D-V2-8.** Publication is not admission. A revision containing an unadmitted plan is never a coder input; if the stage is refused or rejected, no `worklogs/<slug>/` exists in the canonical tree, and a rejected view's bytes are unreachable through any reader pin. | TEST-2.9 → `tests/test_ai_native_bootstrap.py::test_rejected_create_leaves_no_project_and_no_reader_sees_bytes` |
| CT-2.6 | FUNCTIONAL / INV-03 | The planner is told the grammar the parser enforces, **in the terms it now writes**: the acquisition/authoring prompt names the fixed document set, the frontmatter fields the harness cross-checks and the refusal rules, and carries one worked example document pair that `parse_plan` admits. Prose about a typed JSON payload the planner no longer produces is removed rather than left beside the new contract — two descriptions of the grammar is how the router and the parser drifted apart (`plan-format-marker-roadmap`, `slice-1-unknown-field`, measured 2026-11-20). | TEST-2.6 → `tests/test_prompt_registry_coherence.py::test_the_authoring_prompt_example_is_a_document_pair_the_parser_admits` (**written 2026-11-21, E590**) **Measured 2026-11-21 (E590):** the prompt carried no worked example at all, so the test could not have passed; the example was written for it and the first two drafts were refused by `parse_plan` (`slice-1-exit-check-entry`, `acceptance-selector-invalid`), which is the control doing its job. |
| CT-2.4 | FUNCTIONAL / INV-04 | Complete project is parsed, validated and acceptance-sealed before coder starts. Under D-V2-9 the ordering is: the planner stage publishes one revision (scaffold + authored content), admission validates that revision and mints the revision-bound seal, and only then is coder dispatchable. An unadmitted or unsealed revision never reaches coder even though it exists in history (D-V2-8). | TEST-2.4 → `tests/test_ai_native_bootstrap.py::test_validation_and_seal_precede_coder_and_hide_provisional_content` (**absent — SLICE2 work, E590:** the controller has no `AcceptanceBundle` reference, so there is no seal for the gate to precede the coder with; `_validate_plan_admission` for V2 is a projection of an already-parsed graph. Writing this test before SLICE2 would assert an ordering the code does not implement.) |
| CT-2.5 | CONSTRAINT / INV-11 | V2 create-new `invoke_workflow` returns `ToolResult.ok` only for child exit 0 + terminal `DONE` + committed/refreshed parent revision. After HANDOFF/return settles, child failure is `ToolResult.fail` with stable code, retryability and path/secret-free text; include child run_id in safe summary for artifact lookup. Invalid params/content before install may be retryable; collision, unsupported schema and `DURABILITY_UNKNOWN` are not. Do not map child failure as outer ok. Preserve existing result semantics for `AUTO_SELECT_EXISTING` calls. | TEST-2.5 → `tests/test_invoke_workflow_tool.py::TestCreatNewRouteFailureMapping` (**present, E599**). Eight tests: the collision code, a closed-rule table (eight rules × code × retryability, plus the fail-closed fallback), the summary's child run id against four hostile segments, exit-0-without-DONE, the create route still succeeding at DONE, and the select route's published semantics unchanged. The suite lives beside the other `invoke_workflow` contract tests rather than in the bootstrap bank: the mapping is the tool's own return contract, and the ordering proof for the rest of the route is already there. |

```verify
uv run pytest tests/test_ai_native_bootstrap.py tests/test_invoke_workflow_tool.py tests/test_managed_workflow_e2e.py tests/test_s5p1_bootstrap.py -q
```

**V2 tool error mapping:** `invalid_project_action` / `invalid_project_slug` (pre-child, retryable); `project_exists` (collision, not retryable); `bootstrap_content_invalid` (retryable only when child evidence proves no install/irreversible effect); `unsupported_plan_format` (not retryable); `acceptance_seal_failed` (retryable only for a proved pre-install/no-effect refusal, otherwise blocked); `durability_unknown` (not retryable); `workflow_failed` (not automatically retryable; retain the child run for inspection). `invoke_workflow` maps these only for V2 project actions after child lifecycle settlement. Its `ToolResult.fail` has no structured `result` payload (`src/fa/inner_loop/registry.py::ToolResult.fail`), so the safe summary includes the non-secret child run_id; never serialize raw exceptions, filesystem paths, planner bodies, credentials or supervisor internals. Successful V2 result includes run_id, exit/status, route, and parent revision outcome (with `tick/evidence refs` optional until SLICE4b/5).

**Failure/negative controls:** child planner emits a different slug; hostile slug; collision with complete and incomplete project; prepare refusal; install pre-rename failure; post-rename uncertainty; post-install validation/seal failure; return/HANDOFF reconciliation failure. In every refusal, inspect the authoritative workspace revision/tree and caller result, not only mocked DTO. Preserve no-replace install and forward recovery semantics. **Producer kill-check:** remove the real controller's bootstrap transition/materialization call and the success composition test fails to produce the new project. **EDGE kill-check:** remove `invoke_workflow`'s call into the child workflow or chat registry binding and C1/C2 test fails; parser-only tests do not count. **Local DoD:** real local authority + real managed caller success and refusal tests, no coder before seal, no side effects on pre-install refusal, uncertain post-install state remains blocked/recoverable, stable structured tool result; targeted typing/format/authoring checks pass. No host acceptance claim.

**SLICE2 increments 1–2 (2026-11-20).** A `PLAN-V2` bootstrap pair is validated **before** `prepare_bundle`
and therefore before the irreversible install; the refusal is `PlanRefError("bootstrap-invalid-body")` with
the recorded `bootstrap`/`invalid-body` diagnostic and no operation id. The route flip has **landed**:
`BOOTSTRAP_NEW_PROJECT` sets `ctx.plan_format = PLAN_V2` before any bytes exist, so the V2 parser and the V2
admission rules finally have a production caller. Only one test encoded the old order
(`test_v2_bootstrap_invalid_body_...`), and it is rewritten to assert refusal-before-install; the earlier
"eight tests" claim was a measurement artefact from converting the shared V1 fixtures (E573 records the
correction).

**SLICE2 increment 3 — CT-2.1 route authority (2026-11-20).** Creation is now a *caller* decision, enforced
on both sides of the prelude. `invoke_workflow` accepts `project_action` (`AUTO_SELECT_EXISTING` default |
`CREATE_NEW`) and `project_slug`; the pair is validated before any child run exists (`invalid_project_action`
/ `invalid_project_slug`, both retryable) — a slug without `CREATE_NEW`, an unknown action, a bad grammar or a
missing slug all refuse at `_prepare_invocation`. The slug travels as `AcquisitionSubstrateRequest.project_slug`,
is carried by the pinned `AcquisitionSubstrate` (the request object never reaches the run body), lands in
`WorkflowContext.project_hint`, and decides one fact: **whether this run may install a new project at all**.
A `BOOTSTRAP_NEW_PROJECT` reply on a select-only route is refused by the installer
(`_install_bootstrap_project_with_detail(creation_authorized=...)`) *before* the body is parsed, because a body
is only worth validating when a project may exist; an existing-project selection on a create route is refused
by `_bind_acquisition_admission`. Both directions record the new closed-vocabulary rule
`selection/project-route-mismatch` (`admission_schema.py`, spec §"Keep all v1 rule tables"). When both sides
name a project, `_with_project_hint` installs under the caller's slug and only logs the planner's, so the name
is never a model claim. The acquisition task text and the static prompt now state the route the controller
enforces, so the planner is never invited to take a path that will be refused
(`test_the_acquisition_task_states_the_route_the_controller_enforces`). Evidence:
`tests/test_ai_native_bootstrap.py::test_chat_slug_and_explicit_route_are_required_for_new_project` (three real
managed runs: refusal, mirror refusal, caller-slug install), 8/8 mutants killed (route flag, installer guard,
slug override, snapshot guard, substrate carriage, and the four tool-validation branches).

**CT-2.1 remainder — CLOSED 2026-11-20 (E586).** The proposal/resolved split landed exactly as specified:
`BootstrapProposal` (no name) is what the wire parses, `BootstrapNewProjectChoice` is what the controller builds from
the caller's slug plus `INITIAL_INCREMENT_SLUG`. A payload carrying `project_slug` or `increment_slug` is
`choice-malformed`, so the planner can no longer name the path admission reads. Also open on SLICE2: CT-2.2's
collision proof (`project_exists`, not retryable) against a real authority, the closure materialization inside the
installed revision and the seal mint (D-V2-5).

**D-V2-9 ordering (ratified 2026-11-21; supersedes the D-V2-7 ordering).** The steps below are ordered by what
unblocks what, and each is independently revertible:

1. **Delete the payload layer.** `plan_semantics.py` (573 lines: `parse_semantics`, `render_roadmap/increment/
   open_questions/project`, `from_graph`), the `semantics` branch of `_parse_bootstrap_choice`
   (`managed_acquisition.py:638–660`), `_bootstrap_bodies`/`_rendered_increment_sha256`
   (`workflow_controller.py:2759–2790`), the V1 prose fields `roadmap_body`/`increment_body`, and the V2 branches of
   `publication.render_bundle`/`_validate_bundle_text`/`bundle_paths`. **No test may be deleted to make this pass**:
   the renderer-law tests are replaced by CT-2.8's admission tests, and `tests/test_s5p1_bootstrap.py`'s direct
   controller calls are rewritten against the new stage.
2. **Planner-as-writer plumbing.** `PlannerDispatchKind.CREATE_NEW_PROJECT` (an authoring dispatch that owns the
   write allowlist and forbids a candidate buffer and an active plan; `planner_dispatch.py:64–78` gets a third case),
   `allowed_paths` threaded from the stage into `build_registry_for_role`, `_open_stage_view` selecting a WRITE
   `PROJECT` view for this dispatch, and `plan_ref=None` for it (D-V2-9.5).
3. **Scaffold writer.** One module-level constant in the controller that returns `dict[str, str]` for the seven
   files of D-V2-9.7 (four documents with empty bodies, two `README.md` root carriers, one test module with no test
   functions); written through the stage port before the first tool call, `roadmap.md` first so a collision refuses
   the whole stage before any other byte. It contains no planner content and no placeholder plan.
4. **Metadata cross-check** (D-V2-9.3) as a new function next to `parse_plan`, called from `_admit_plan` before
   `parse_plan` for the create-new route.
5. **`project_exists` mapping** (D-V2-9.2) in the planned-file writer.
5b. **Repair path** (D-V2-9.8): a second authoring stage over a WRITE `PROJECT` view at the published revision with
   the allowlist narrowed to the increment (plus `open-questions.md`), `plan_ref=None`, replacing the candidate-buffer
   promotion for create-new only. The `ADMISSION_REPAIR` candidate path stays for every other route.
6. **Prompt rewrite** (CT-2.6) — last, because it can only be written truthfully once 1–5 exist (the P0-1 lesson).

Every step keeps the suite green on its own. Step 1 is a pure deletion once step 3 is in place, so steps 3 and 4
land first if a single commit is preferred.

**Bounded planning ASK/Q items:** Q-V2-BOOT-1 is **resolved** (D-V2-5, audit `notes/q-v2-boot1-install-seal-audit-2026-11-20.md`): the closure is installed inside the revision, the seal is minted from installed bytes + plan bytes + receipt revision into private metadata, and the pointer/recovery rules are E1–E9. SLICE2 therefore implements that chain rather than choosing one; Q-V2-MODEA-1 was resolved by D-V2-6; E657 strengthens it to true read-only file-tool and shell projection, with fallback if unprovable; it does not block installation. Route fields/error mapping above are this plan's selected bounded interface, not coder choices. The initial increment slug is harness-fixed `initial-plan`; planner cannot supply it. No interactive approval is required for routine implementation seams.

### SLICE3: V2 acceptance graph and STEP9A custody integration

**STEPS:** outcome<br>
**DEPS:** SLICE1, STEP9A<br>
**INTENT:** Adapt the V2 semantic graph and fresh-project acceptance closure to the already-implemented STEP9A `AcceptanceBundle`, mode-A projection and exact attribution mechanisms. This slice owns only V2 serialization/materialization/admission/evidence integration and fresh-project closure proof; it MUST NOT reimplement STEP9A sealing, protected-path authority, JUnit classification, mutation runner, TEST-DEFECT state machine or immutable-payload store. If STEP9A does not expose a stable supported contract needed here, stop this dependent slice and file a scoped replan/Q rather than creating a second mechanism. Reuse the managed read-only verifier; no parallel runner.<br>
**Production producer/caller:** `plan_admission.py::PlanSnapshot/PlanRef` and `workflow_controller.py::_validate_plan_admission/_admit_plan` must bind the V2 graph and selected manifest to STEP9A's controller-minted seal; `workflow_controller.py::_pinned_verify_substrate` binds verification; `slice_verification.py::capture_test_nodeids`, `verify_plan`, `_run_kill_check` and `_kill_check_result` are current test execution seams whose V1 slice-wide behavior is explicitly replaced/consumed only through STEP9A, not copied. `src/fa/execution/workspace.py` revision/read view and `profiles.py` managed cell are substrate. Caller/EDGE is admitted managed `run_workflow`→sealed verifier, with identical sealed acceptance-path bytes available to coder read-only and verifier. The candidate implementation revision may advance after seal: verifier must prove the acceptance closure digest still matches the sealed revision while importing the current candidate code; record both identities and refuse any overlapping code/acceptance path that would make that composition ambiguous.<br>
**Planner-owned acceptance:** extend the existing STEP9A bank `tests/test_ai_native_acceptance_bundle.py` (59 top-level `def test_` on 2026-11-22; the row said 45) rather than creating a second file; plus exact STEP9A tests selected when that step closes; C0/C0p graph adaptation, C1 fresh-project managed verifier and C3 boundary controls. Do not fork STEP9A's tests or duplicate test ownership.

| CT | Class / primary INV | Acceptance behavior | TEST-ID → exact selector |
|---|---|---|---|
| CT-3.1 | FUNCTIONAL / INV-05 | Build and validate the `INV→CT→TEST-ID→selector` graph with required cardinalities; **every** CT is discharged exactly once — executable evidence resolving to one collected nodeid, or a caller-granted typed disposition (`PRESERVATION` never dispositionable, no `KIND` exemption, no `SOFT` escape); TEST-ID maps to one exact collected nodeid. | TEST-3.1 → `tests/test_ai_native_plan_v2.py::test_slice_rules_refuse_invalid_graphs` (the closed edge/cardinality rules) plus `tests/test_ai_native_acceptance_bundle.py::test_an_incomplete_nodeid_report_never_reaches_the_seal`, `…::test_a_record_with_two_rows_for_one_test_id_is_refused` and `…::test_a_seal_is_refused_while_a_contract_has_no_evidence` (discharged exactly once). **Corrected 2026-11-22 (D-2):** the row named `…bundle.py::test_acceptance_graph_requires_complete_unique_contract_and_nodeid_edges`, which exists in no file. |
| CT-3.2 | FUNCTIONAL / INV-06 | Fresh-project V2 materializer emits the complete schema-declared acceptance manifest into the STEP9A seal request; the authority returns a controller-minted seal bound to exact plan and acceptance-closure revision. Admission rejects a missing/stale seal, unresolved selector or closure mismatch before coder. | TEST-3.2 → `tests/test_ai_native_acceptance_bundle.py::test_mints_a_seal_bound_to_plan_revision_closure_and_nodeids`, `…::test_a_selector_outside_the_sealed_bytes_is_refused`, `…::test_a_graph_that_does_not_describe_the_plan_bytes_is_refused`, and on the route `tests/test_v2_seal_store_and_mint.py::test_admission_mints_the_seal_and_the_next_stage_reads_it` (the mint now *has* a caller: N1, `7b750f5`). **Corrected 2026-11-22 (D-2):** the row named `test_v2_materialization_binds_complete_closure_to_step9a_seal`, absent from the tree. |
| CT-3.3 | CONSTRAINT / INV-07 | Mode A under D-V2-6 as amended E657: the authority derives sealed semantic paths and prevents file-tool writes to them and their ancestors in both PROJECT and MUTATION coder views. Coder shell must also have a genuinely read-only acceptance projection, including resistance to ancestor replacement and transient ABA; post-hoc drift detection and publication validation are additional safeguards, not substitutes. The verifier must execute the same pinned closure. If revision-backed projection cannot establish these properties, use the isolated immutable-payload fallback. Until authority-private seal and this projection are proven, the V2 pre-dispatch guard refuses coder execution. | Existing TEST-3.3 file-tool coverage: `tests/test_execution_purposes.py::test_v2_coder_projection_protects_every_sealed_semantic_path`; shell projection, exact verifier binding and host tests remain required, not credited by existing drift tests. |
| CT-3.4 | PRESERVATION / INV-08 | Every V2 target/CT/TEST-ID edge is translated without loss into STEP9A's exact-attribution contract. On the V2 route, target pass remains VACUOUS; only the mapped nodeid's assertion failure can be PROVEN; unrelated failures remain suite failures; setup/collect/skip/timeout/crash/JUnit/zero-run remain ERROR. This test proves V2 does not reintroduce the existing Q53(c) slice-wide rule. | TEST-3.4 → `tests/test_ai_native_kill_attribution.py::test_a_target_is_bound_to_its_contract_test_nodeid_and_sealed_evidence`, `…::test_a_baseline_pass_and_a_mutation_failure_is_proven`, `…::test_a_mutation_that_still_passes_is_vacuous`, `…::test_a_report_with_a_second_row_is_refused`, `…::test_an_empty_report_never_proves_anything`. **Corrected 2026-11-22 (D-2):** the row named `…bundle.py::test_v2_mapping_delegates_exact_attribution_without_slice_fallback`, absent from the tree. **Not wired to the route yet:** `kill_attribution` has no production caller (measured `grep -rn kill_attribution src/` → the module itself only), which is the recorded deviation in §8 step 4 and the factual basis of Q-V2-SLICE3-4/5. |
| CT-3.5 | PRESERVATION / INV-09 | V2 `TEST-DEFECT` report is bound to STEP9A seal/test/nodeid; it follows STEP9A's existing immutable old-evidence/new-revision baton and replan behavior. V2 adds no second state machine and cannot silently change an invariant. | TEST-3.5 → `tests/test_ai_native_acceptance_defect.py::test_a_report_is_pinned_to_the_seal_revision_nodeid_and_invariant`, `…::test_a_correction_is_a_new_seal_that_supersedes_the_reported_one`, `…::test_the_old_revision_stays_readable_after_a_correction`. **Corrected 2026-11-22 (D-2):** the row named `…bundle.py::test_v2_test_defect_uses_step9a_revision_and_preserves_prior_evidence`, absent from the tree. |
| CT-3.6 | CONSTRAINT / INV-06 | Managed verifier runs the acceptance closure through STEP9A's pinned managed no-network/read-only cell (`slice_verification.py:162` argv, not the planner fence at `:552`) and the same closure revision while importing the explicit current candidate revision; records both revision identities and refuses a closure/code path overlap. **Planner-authored `verify` fences are no longer executed on the `PLAN-V2` route** — command text never drives a result (the fence path is retired for V2, retained only for the frozen legacy route). No host fallback or different runner/config. | TEST-3.6 → `tests/test_ai_native_acceptance_bundle.py::test_v2_verifier_uses_sealed_closure_with_current_candidate_revision` | **Landed in part 2026-11-22 (E615):** the pinned verifier now exists as `acceptance_collection.verify_sealed_acceptance` — it refuses a host-shaped substrate (`verifier-substrate-required`), a malformed candidate (`candidate-revision-invalid`) and a closure that overlaps a code root (`sealed-root-code-overlap`) *before* any cell command, runs the sealed argv with its report carried in the receipt, and records **both** revision identities (`sealed_revision_id`, `candidate_revision_id`). Test: `test_v2_verifier_uses_sealed_closure_with_current_candidate_revision`. **Landed since (2026-11-22):** the controller wiring — on a sealed snapshot the verifier stage calls `_sealed_stage_verification` and never `verify_plan` (`workflow_controller.py:2084–2104`), so the planner fence is not reached on the `PLAN-V2` route, and the attempt lands in `verification.json`'s append-only entry. **Still not landed:** `run_kill_checks` itself (F10 item 5), which is what Q-V2-SLICE3-4 and Q-V2-SLICE3-5 now own. **Superseded detail:** the paragraph below describes the pre-wiring state and thereby retires the planner fence (`slice_verification.py:552`) — that needs an answer to what the V2 verification artifact should be (today's `write_verification` consumes `PlanVerification`, which is built from planner commands). Filed as Q-V2-SLICE3-1 (now answered, see `notes/verification-entities-2026-11-22.md`). **Verified defect in the landed half (F9, 2026-11-22):** `verify_sealed_acceptance` never runs a mutation, so for a plan carrying `KILL-TARGETS` it would record a claim as proven while the kill check never ran. It must compose with STEP9A's existing runner through a public `run_kill_checks` seam (SLICE3's intent forbids a second runner) and, until it does, **record the declaration instead of refusing** (**RATIFIED 2026-11-22 = Q-V2-SLICE3-4 option A**): the attempt carries `kill_declared` with `executed: false`, the artifact and the eval block name the gap, and `proven` speaks only about the selector's execution. The refusal this paragraph used to demand (`claim-mutation-missing` for a *declared* target) is option B and was rejected by measurement: the authoring prompt requires a `KILL-TARGETS` block (`prompt.py:1248`, `:1299`), so B would block every project written to the instructions, permanently, until `run_kill_checks` exists.

```verify
uv run pytest tests/test_ai_native_acceptance_bundle.py tests/test_slice_verification_runner.py tests/test_verify_gate_live.py -q
```

**D-V2-4 addition (2026-11-20).** A coder's test-change proposal is a second input to the *existing*
planner decision, not a second mechanism: the proposal must name the current seal, `TEST-ID` and nodeid, and
the planner's `correct(...)` refuses a plan change, a same-revision re-seal and an unchanged closure exactly
as it does for a report. The proposal artifact lives outside `acceptance/`, so mode A still holds and no
coder-authored byte can reach the sealed closure without a new seal. CT-3.5 covers both inputs.

**Failure/negative controls (E657 supersedes detection-only wording):** stale/missing seal; modified, added or deleted accepted bytes; a file-tool write attempt on every sealed semantic path (refused) and a shell-level mutation of the closure (prevented, including transient/ABA attempts), including a sealed path under `src/`/`scripts/`; unsupported visibility mode B; incomplete closure; ambiguous selector; target passes while unrelated test fails; collection/setup/skip/timeout/crash; new behavior test red at pre-coder T0 but mapped assertion fails on scenario-specific no-op/known-bad witness; then mapped test passes against current implementation immediately before STEP9A's kill; changed test assertion preserves prior evidence; managed executor unavailable. Custody/mapping integrity blocks in observe and enforce; determinate kill results follow configured observe/enforce behavior. **No duplicate producer kill:** STEP9A owns mutation engine/JUnit classification producer kill and its EDGE; this slice's local mutation/EDGE check targets only the V2 adapter/mapping and its caller into the already-proven STEP9A/managed verifier, proving that bypassing the adapter loses the exact V2 project selector/evidence. If STEP9A proof is unavailable, SLICE3 is blocked, not credited with a new local mutant. **Local DoD:** V2 project closure is materially collected and run at the exact `worklogs/<slug>/acceptance/tests/...` path through existing managed runner; seal/mode-A/digest behavior is delegated and proven by STEP9A evidence; V2 graph round-trips to exactly the same bundle/test/nodeid; no closure/code path overlap; exact attribution behavior is not reimplemented; no unreviewed skip; targeted static checks pass. Host remains separate.

### D-V2-13 — rolling-wave mutation obligation and late binding (operator direction 2026-11-23)

**Status: behavior selected; NOT implemented or runtime-verified.** This block is the forward specification for
Q-V2-SLICE3-5/6, not a claim that the current V2 route runs mutations. Do not treat the old brief's A recommendation
or its two-command sketch as the selected contract. The goal is carefully designed cross-component seams and
critical invariants with MVP-level internals, implemented in vertical slices; future private names are not a
planner obligation. The planner authors invariants, optional explicit scenarios and CTs, and the acceptance tests
that demonstrate those requirements. One primary INV per CT; optional SCN links explicit CTs; tests belong to CTs,
with membership of SCN derived from CT. An INV/SCN is not silently given a new direct test edge. Coder owns routine
implementation choices within those admitted boundaries; harness performs deterministic work where possible.

**Contract B1 — responsibility and grammar.** Every **executable** `FUNCTIONAL` CT has exactly one mandatory
mutation check for this MVP and its `TEST-ID` is **always explicitly named**, including when only one test exists.
The TEST-ID must exist, belong to that CT and resolve to exactly one sealed nodeid. A CT may have multiple acceptance
tests; the named TEST-ID selects the mutation oracle without discarding any other test evidence. `CONSTRAINT` and
`PRESERVATION` have no blanket mutation obligation. A FUNCTIONAL carried solely by a valid caller-granted
`NON_EXECUTABLE` disposition is attested/pending, not mutation-proven; a CT with an executable selector is
executable even if its invariant also requests disposition (`contract_evidence` strongest-wins). Missing or
unauthorized dispositions cannot be used as an exemption. Preserve D-V2-10/12 and `PRESERVATION`'s prohibition.

Target authoring shape for the **atomic D-V2-11 cutover**, using the existing pipe-separated labelled-row convention:

```text
KILL-TARGETS:
  CT: CT-1.1 | TEST-ID: TEST-1.1 | SITE: DEFERRED
  CT: CT-1.2 | TEST-ID: TEST-1.2 | SITE: src/orders/api.py::create_order | MUTATION: remove-call -> save_order
```

`SITE: DEFERRED` means the obligation and oracle are sealed now, not that a mutation may be skipped. A pinned
`SITE` is used only when a known producer/public or cross-component seam is genuinely a plan constraint; presence
of an existing repository alone is not a reason to bind a new private implementation. `MUTATION` is required only
for pinned SITE and forbidden for DEFERRED. For a pinned SITE, `MUTATION` is `neutralise` or
`remove-call -> <callee>`; `neutralise` has no callee. Path is repo-relative under existing `src`/`scripts` mutation roots; symbol
is an exact qualified dotted identifier supported by CT50b/CT81. Reject ambiguous/duplicate rows, invalid paths,
operators, callee shapes, foreign CT/TEST, and missing rows for applicable CTs at admission, without requiring a
future candidate file or symbol to exist at admission. For this MVP use CT as the stable identity of the *one*
check; do not make the planner mint a separate target ID. Any internal identity and old-record mapping must be
unambiguous, not based on row position. More than one mutation per CT is out of scope, not silently discarded.
These target rows supersede current `TARGET-ID` grammar; the actual parser today still requires that field. V1
remains frozen. Grammar table, parser, authoring prompt, skills, fixtures and conformance tests move together;
repair diagnostics and admission-record vocabulary must accept the new rules without relaxing legacy validation.

**Contract B2 — proposal, authority and receipt.** For DEFERRED, after code is published the coder supplies one
bounded, untrusted proposal for the CT: exact site, operator/callee and a short claimed connection to the sealed
behavior. Harness, not the coder, binds it to the seal/plan digest, explicit CT/TEST/nodeid, run/attempt and the
actual candidate revision named by the pinned substrate. Do not trust a revision, verdict or nodeid supplied in
coder text. A planner-pinned directive uses the same validation/execution path and records `planned` provenance;
a deferred proposal records `coder-proposed`. Do not claim `derived` unless an actual deterministic producer is
implemented and proven; no automatic first-killed-mutant search. A proposal neither changes the seal nor becomes an
acceptance test. Once verification begins for an attempt, the selected directive is fixed; a later revision or
proposal is a new attempt with retained prior evidence. No automatic retry with alternate candidates until green.

The selected minimal transport is the existing in-memory **terminal coder `SessionOutcome.final_text`** through
`_cmd_run(..., outcome_sink=...)` into `_run_stage` after `_capture_managed_revision_boundary(..., after_stage=True)`.
This is a new consumer of an existing channel, not a claim that current code reads coder output. In a PLAN-V2 coder
stage the prompt requests exactly one fenced block ` ```fa-kill-proposals ` (without the spaces) containing a JSON
object with exactly `{"proposals": [...]}`. Each proposal has exactly `ct`, `test_id`, `path`, `symbol`, `operator`,
`callee` (string or null), and `rationale` (bounded untrusted text); no nodeid, revision, seal, verdict or command.
The block may coexist with ordinary final prose. A stage with no deferred obligations need not supply a block; if it does, it must satisfy the same rules with an empty array. Harness extracts at most one well-formed block, uses JSON parsing
that rejects duplicate object keys, limits the block to 32 KiB UTF-8 and rationale to 512 characters per entry, and
requires exactly one proposal per in-scope DEFERRED CT, no extra CTs, no duplicates, no proposal for a pinned CT.
An empty proposal array is valid only when no in-scope CT is deferred. Reject a missing block when deferred obligations exist, multiple/unterminated blocks,
non-object/unknown fields, unknown or mismatched CT/TEST, oversized text, invalid operator/callee and unexpected
proposal rather than repairing or guessing it. Explicit `TEST-ID` must equal the sealed target row. Take only the
successful terminal coder stage outcome for the current invocation, check the sink and exit/release outcome, then
bind that in-memory input to the controller-observed post-stage candidate revision and run/attempt; clear it on
failure, retry, new stage or replan. Never accept a model-supplied revision or recover a prior stage's final text.
Keep stdout behavior unchanged; do not echo proposal text into a privileged command or unbounded eval context. The
real CLI prints final_text, so tests must check both output and result transport; file-based handoff is **not**
a fallback. If production source proves this channel unavailable on a supported topology, stop and file a scoped
Q before substituting a different authority or adding a writable project file. This design adds no extra LLM call.
D-V2-4 is a useful *analogy* for a bounded coder proposal, not an existing mutation channel:
its test patch and `acceptance_defect.correct` have different semantics and must not be reused to alter the plan or
acceptance. No extra approval/LLM call for routine binding; independent review remains Q-V2-REVIEW-1, not an MVP gate.

Harness checks site syntax/root confinement, no path traversal/absolute path or symlink escape, one exact AST
definition, correct operator/callee and at least one actual edit, and reads bytes via the same pinned `WorkspacePort`
as the executor's revision. Missing, malformed, duplicate, ambiguous, stale or foreign proposal never becomes a
mutation pass or silently falls back to another target. Plan-pinned site missing at candidate time is a diagnosed
producer/binding failure, not admission-time proof that future code is absent. Facts only: this validates execution
and provenance, **not** semantic optimality of the site. The sealed acceptance still checks observable behavior;
for external/durable effects it must observe the authoritative effect/no-effect (Hollow-Facade). A killed mutation
is evidence that the named test detected this particular perturbation, not proof of requirement completeness.

**Contract B3 — execution and honest evidence.** Generalise the existing V1 managed in-band mutation overlay and
pure `apply_kill`, do not build a second runner or host fallback. `run_kill_checks` is the composition seam, not an
independent engine: thread the port from `_VerifySubstrate`, reuse `oracle_argv` from the seal and execute baseline
and mutant for the same exact nodeid, same candidate revision, same sealed config/closure and equivalent environment.
The baseline is immediately before mutation on the current candidate, not pre-coder T0. Prove overlay import
provenance in both relevant runs and ensure actual mutated bytes are imported. Preserve the existing one-JUnit-block
per receipt rule. MVP uses two harness-built managed commands, one baseline and one mutant, each with one report
and a fresh scratch overlay built by the same setup, argv/config/nodeid, cwd and environment policy; compare
normalised configuration and source snapshot identities rather than requiring identical absolute temporary paths.
Each command cleans up its own scratch. The only intentional source difference is the one mutated file. The pinned
executor/view must remain alive across both, and the same absolute deadline covers both; failure/uncertainty of
either yields no PROVEN. A different composition requires demonstrated equivalent receipts and must not weaken
the one-block parser. The existing in-band bootstrap removes its scratch in `finally`, so two commands do not share
one directory. The existing `_PROVENANCE_PROBE` runs in a separate process and checks a module path, not what pytest
actually imports: extend/reuse the trusted pytest-side overlay hook to attest the selected module path and original/
mutated bytes in the **test process**, with a distinct run nonce and before verdict. Prove an import diverted after
the standalone probe cannot pass. If that cannot be enforced under the selected profile, stop and replan the owning
STEP9A seam; do not describe the standalone probe as proof of pytest's actual import. Use the
existing detailed JUnit parser through an in-band adapter, not `parse_inband_nodeids`' boolean projection; verify
command outcome/exit against report, exact nodeid, run binding, complete untruncated receipt and phase/type. A
pytest `<failure>` alone does not establish `AssertionError`; only assertion failure in the named test's call phase
is PROVEN, never non-assertion exceptions, setup/teardown, skip, crash, timeout, zero/extra rows or bad report.
**E652/E653 READ projection binding:** the authority now compares the finished read-only
execution copy with the revision manifest (normalizing only write-bit stripping) before it
accepts its digest; failed read-only staging cleanup is safe and retryable. Authority and
backend negative tests prove no cell launch on injected copy corruption; positive read-only
mount rendering is exercised through a literal Docker peer, not a live container. This does
not close coder mode A, complete custody or STEP9A; see ledger E652–E653.

**E650/E651 local evidence:** candidate sealed pytest now requires nonce-bound call-phase
classification and exit/report coherence; skipped/error calls refuse instead of becoming
ordinary failed claims. Publication and replay tests also prove rejection of a forged,
self-consistent manifest with substituted or omitted acceptance entries. These are local
sub-obligations, not B5 routing, full custody, STEP9A closure or live-host evidence; see ledger.

**E649 partial publication safeguard:** the common seal/publication validator now
freezes an existing acceptance subtree for a project-increment-bound view against the
base manifest, including additions/deletions/mode/omission; ordinary no-plan authoring
and code-only publication have service-backed positive tests. This is not a coder
shell read-only projection, a bundle-scoped complete closure fence, an immutable payload,
or TEST-DEFECT reseal; STEP9A remains open. See ledger E649 for evidence and limits.

**E648 custody controller join:** admission and V2 verifier compare the live pinned
authority inventory to a complete no-symlink host walk before and after execution, including
empty directories; admission rechecks after mint and joins bundle file hashes while the reader
is still open. Real authority/UDS→controller admission tests and 583 gate tests pass; the
pytest executor in that admission test is a local double. This closes neither transient/ABA
protection nor mode-A coder projection/publication and does not prove live host; see E648.

**E647 custody transport:** bounded authority inventory is now exposed through negotiated V2
read-only operation and client, with revision/tree join to the reader grant; service/authority
and real UDS client tests pass. It is not yet consumed by admission or compared with the seal,
and does not prove mode-A custody; see E647.

**E646 custody component:** `WorkspaceAuthority.inventory_acceptance` projects bounded complete
subtree metadata from a capability-bound pinned revision; local authority tests cover foreign
grant, host drift, symlink and over-limit refusal. It has no wire or controller consumer and
does not yet join inventory to the seal or prove coder projection; see E646.

**E645 priority gap-closure work order (STEP9A; all unchecked).** This is execution detail for the
existing E530/STEP9A and B1–B6 gates, not a new step or permission to bypass STEP9B:

- [ ] **Custody, first critical dependency (INV-04/08, CT-3.3/3.6):** extend the existing authority
  revision/pinned-reader and mode-A write-view seams to bind complete closure bytes and membership
  to the authority's revision, pre-code run, minted bundle and candidate verifier. Prove added,
  deleted, substituted, symlinked and transiently changed content cannot produce a verdict;
  prove file tools and shell cannot write coder-visible acceptance and publication rejects drift.
  Existing READ projection is authority-materialized and read-only, but host-side closure hashing
  is not evidence of that projection's content. `WorkspacePort.read_file` has no recursive
  inventory; checking only host-known files misses extra authority files. Use a bounded
  authority-owned inventory/manifest seam, or the ratified immutable-payload fallback if C cannot
  prove full closure and read-only projection. No host filesystem or in-band self-attestation
  fallback. C1 authority→controller→managed execution and C3 adversarial tests, producer/EDGE
  kills, then live-host witness remain required.
- [ ] **Pre-code (INV-04/11/12):** use the same custody binding for real admission→pinned pytest→
  seal; retain classified per-node outcomes and applicable known-bad/no-op witness evidence.
  Test a fresh project without foreknowledge of coder seams; if impossible, record the scoped
  producer-absent replan rather than weakening mandatory later checks (E639).
- [ ] **Exact mutation (INV-06/08, CT-3.4):** B2 grammar/guard cutover, B3 coder proposal and
  B4 managed baseline/mutant composition over existing overlay and authority port; bind selected
  TEST-ID, candidate, seal, actual imported source, receipts and call-phase assertion. No
  manufactured PROVEN or standalone probe substituted for actual pytest import provenance.
- [ ] **TEST-DEFECT (INV-09, CT-3.5):** validate both planner decisions against sealed report,
  plan and revision, connect coder→planner→decision→coder and retain old evidence; corrected
  closure creates a new seal and re-runs affected gates. E645 hardens decision components only;
  full workflow and authority-backed retention remain open.
- [ ] **Evidence/routing (INV-08/11, B5):** preserve typed pass/assertion/skip/error outcomes
  through real linear and adaptive routes: custody and indeterminate failures block both modes;
  determinate failure is advisory only in observe and repairable in enforce. Check artifact
  history, declared versus executed mutation and no missing/duplicate evidence.
- [ ] **W4 live and ledger E2E (INV-10/12):** after W3 and approved deploy, add/run reviewed
  host cases for actual workflow and writable project ledger: observe old+new content in the
  published revision and fresh read, plus fail-closed publication/reconciliation and retained
  authority evidence across TEST-DEFECT and mutation. Ledger is editable working content, not
  an append-only authority; verify that forged PASS there cannot satisfy the gate. Q-V2-WRITE-
  SCOPE-1=A governs nested coder; implementation remains open. These cases are planned, not host acceptance.

**E644 adversarial review:** TEST-DEFECT correction validates report identity and
conservatively re-proves all closure tests/targets; workflow integration remains open.
The E643 service failure was a PTY stateful-shell regression and is fixed with a subshell
prefix; 435 local tests pass. Custody, exact managed mutation, typed observe/enforce
routing and production-path pre-code witness remain open; see E644.

**E643 STEP9A review:** managed shell markers are exported for subsequent subprocesses, with
real-shell and managed-adapter/pytest tests; separate service-backed test initially failed with
uncertain execution; resolved and re-tested in E644. This is not authority custody proof; see E643.

**E642 STEP9A component:** an unconfirmed pinned-reader stop now invalidates pre-code admission and
post-coder provisional attempts instead of merely logging; observe/enforce remain blocked. Fault-injected local
controller evidence is not managed-host custody proof; see E642.

**E641 STEP9A component:** the pre-code caller checks the executor's named revision, compares the pre-run
closure digest to the minted closure and refuses identity mismatches without a planner repair. This does not
prove authority-backed receipt/source identity, in-run custody or host execution; see E641.

**E640 STEP9A component:** pre-mint full pytest collection now distinguishes assertion-red from other call
exceptions/skip and checks invocation metadata and exit/report coherence. This is not witness sensitivity,
managed authority/custody proof or full pre-code gate closure; see E640.

**E637 component progress:** sealed projection now preserves multiple unique tests per CT, counts distinct CTs,
checks pending against attested and compares projected keys to the seal; controller baseline pass/fail and payload
are exercised. This is not selected-TEST-ID mutation binding or the managed kill EDGE; see ledger E637.

**E636 component progress:** the trusted pytest plugin writes call-phase outcome metadata, the strict parser checks
it together with a run nonce, and `run_node_oracle` checks report/exit coherence. The in-band parser shares this
validation. Real local pytest negatives and component kills pass; neither managed runner integration nor trusted
actual overlay-import provenance nor receipt/candidate identity joins have been proven. The plugin, run nonce and
report must be supplied via the trusted harness path; the metadata alone is not proof against an adversary who can
rewrite the runner/report or manipulate plugin execution.
Baseline pass + mutant pass is VACUOUS; failed baseline or unprovable execution is not a kill. Keep the existing
single verdict vocabulary and `attribute` as the verdict owner after its input classification is made sufficient.

Persist in the existing append-only `verification.json` attempt and bounded eval projection: plan/seal/closure and
candidate identities, CT, explicit TEST-ID, exact nodeid, one proposed/planned site, operator/callee, selection
provenance, actual mutation application, baseline and mutant outcomes and their harness-authored command receipts.
No model-supplied free text is authority; bound and label it untrusted. Maintain all acceptance results for multi-test
CTs and the seal's contract totality without confusing the number of selectors with the number of contracts.
`kill_required` must cover every applicable CT and absence of its mutation cannot be `ClaimEvidence.proven`.
Until the entire new path is wired, retain Q-V2-SLICE3-4's honest `kill_declared`/`executed: false` behavior for
current-format records; preserve old readers/history when changing new records. Do not invent an eternal
`declared-but-not-executed` success state for executable checks. The exact new key shape is a consumer-audited
implementation choice, not an authorization to erase historical fields or bump a schema gratuitously.

**Source-audited adapter contracts (required before B2/B3 can be credited).**

1. **Seal ↔ graph:** `acceptance_bundle._bind_graph_to_bytes` currently checks INV heading count plus invariant/
   contract text and CT substring, not class, INV edge, selectors, TEST-ID, kill rows or steps. A direct stdlib
   probe on this checkout parsed both the original test fixture and a version with `test_publish` replaced by
   `test_different` (and separately `FUNCTIONAL` → `CONSTRAINT`); `_bind_graph_to_bytes(changed_graph,
   original_bytes)` accepted both. This proves the helper accepts graph/byte disagreement, not that an attacker can
   reach `mint_seal` through every production topology. Replace the substring check at the owning seal boundary with
   structural equality against the parsed increment's semantic graph, including all plan-owned fields and edges (apply trusted dispositions through the existing binder before comparing grant-bearing fields);
   compare caller-granted disposition data separately against the existing binding authority, without treating the
   planner as grantor. The roadmap marker is separately validated by admission; do not synthesize roadmap bytes.
   `mint_seal` and `acceptance_defect.correct` must both refuse substituted class, CT→INV, selector, TEST ownership,
   kill mode/TEST/site/operator, SCN and step edges, even when all old text/IDs remain present. Prove the real mint
   and correct paths, not only the helper; old seal bytes remain loadable under the existing schema contract.
2. **Seal ↔ selected nodeid:** E635 adds a component-level binding: `bindings` validates seal identity, exact
   plan bytes and authored graph, then joins `(ct, test_id, selector, nodeid)`; `run_node_oracle` re-derives the
   binding before a subprocess, and `oracle_argv` checks seal/revision/closure/test identity. It refuses wrong CT,
   swapped selector, forged target or reused binding. This is **not production wiring**: the module has no caller
   in `src`; the forthcoming managed composition must supply admitted plan bytes and prove its real EDGE. Candidate
   revision, run nonce and baseline/mutant receipts remain B3–B5 obligations and are not provided by these sealed
   revision checks. The current legacy `TARGET-ID` grammar remains until the atomic D-V2-13 cutover.
3. **Multi-test projection and totality:** `sealed_attempt` builds one claim per `bundle.selectors`; current
   `VerificationAttempt._check_v2` rejects two claims with the same CT. Change the entity and projection together:
   expected selector keys are the exact sealed `(CT, TEST-ID, nodeid)` tuples, each appears once, none extra/missing;
   distinct executable CT IDs plus `attested` cover the seal's `contracts_total` exactly, `pending ⊆ attested`, and
   no CT is both executed and attested. Attach one mutation only to the explicitly selected TEST-ID; other claims
   remain ordinary test evidence. Contract completion requires *all* selected tests pass and the mandatory mutation
   proves for functional CT, not just the mapped test. Compute obligations from the admitted graph, never from a
   caller-supplied empty tuple. Include adversarial same-count substitution/duplicate tests, not only length checks.
4. **Admission diagnostics:** `ADMISSION_RULES_V2` lacks `plan-v2`, `_record_diagnostics` checks only V1-style
   `CT\d+`, and `_validate_v2_existing_selection`/`_validate_v2_bootstrap` constrain permitted namespaces. Trace
   `_validate_v2_admission`, create-new repair (`_admit_published_project` and `_bootstrap_failure`) and record
   writers/readers end-to-end. Add a closed V2 namespace and grammar-specific CT validation without broadening V1;
   update relevant route/severity validation or explicitly retain a lossless bounded diagnostic detail if the
   canonical schema requires the existing bootstrap wrapper. Assert specific missing TEST-ID and foreign mapping
   rule survives to the legal repair/caller path; do not merely update the enum while the route still folds it.
5. **Route projection:** `_sealed_stage_verification` currently converts every `sealed.blocking` into
   `PlanVerification.errors`; `_verification_is_indeterminate` treats *any* error as indeterminate, and
   `_effective_controller_route` consequently blocks completion even in observe. Project determinate failed tests
   and VACUOUS as determinate results, not generic errors; classify missing/stale mapping, unavailable substrate,
   invalid reports and mutation-not-executed as indeterminate/integrity. With evaluator requesting complete,
   observe may complete for a determinate VACUOUS while enforce requests bounded coder repair; neither mode may
   finish successfully for indeterminate evidence. Preserve the existing precedence of explicit eval repair/replan
   routes; a repair attempt may run but cannot convert missing integrity evidence into DONE. Test actual `_run_stage`
   and linear/adaptive terminal routing and emitted artifact, not only a `VerificationAttempt.blocking` property.
6. **Evidence joins and retention:** `NodeRun` contains outcome/command/exit but no nodeid, run nonce or candidate
   identity; `attribute` cannot itself prove both runs are for its binding. Extend the existing run/result entity or
   its single owning adapter so that it refuses cross-target, cross-seal, cross-revision or cross-attempt receipts,
   binds each nonce and baseline/mutant phase before verdict, and persists the actual `CommandResult` receipts in
   the same append-only attempt (not only `commands_authored_by`). Persist a refusal with stable code and available
   verified identity even when no full attempt can be constructed; never reuse `_WorkflowAdmission.last_attempt`.
   An artifact append/identity failure prevents DONE, with existing authority reconciliation; no host-side retry
   can mint a success. Source-hash and overlay-hash checks bind actual target bytes, not a claimed mutation string.

**Failure policy and UX.** Custody, plan/test mapping, revision mismatch, stale/ambiguous/missing binding and
unavailable substrate are integrity/uncertainty failures and block in observe and enforce; determinate test/kill
failures remain advisory in observe and repair-blocking in enforce per §1. A failure must identify the safe CT and
TEST-ID and the actionable category, not just `claims-total-mismatch` or `bootstrap-invalid-metadata`; sanitize and
bound any path/text, distinguish source/proposal defect, test defect and infrastructure, and never tell the coder to
edit sealed files. A real TEST-DEFECT follows D-V2-4; a changed semantic invariant/plan requires replan and a new
seal; an internal proposal correction is a new attempt, not an acceptance edit. No semantic change is silently
approved. The previous `proven` word for a passed claim without a required kill must not be reused to imply a kill.

**Rolling-wave planning and pre-code collection (operator clarification 2026-11-23).** A roadmap can describe the
long-term direction, but only the nearest increment and its vertical slices are detailed; later increments may
remain `OUTLINED`. Do not require I02's architecture, detailed CTs, selectors or acceptance tests to be authored,
sealed, synchronized or executed while I01 is unfinished. This does **not** authorize partial sealing or
selective verification of an admitted increment: STEP9A's current complete-closure, pre-code and pinned-verifier
contracts still apply. `parse_plan(roadmap, increment)` currently parses one increment; this is a source observation,
not a claim that the complete multi-increment workflow is implemented.

The independent technical risk is within the **current** increment: `collect_sealed_tree` runs pytest before
mint, so an acceptance module importing a not-yet-created producer may fail before coder. First diagnose with a
production-root fixture for one detailed increment and an outlined successor, using an acceptance test that imports
its not-yet-implemented producer. Record command, collection/seal/dispatch boundary and error without assuming
outcome; also exercise a legal acceptance test that is collected and red at T0. A later acceptance test must prove
that this workflow can progress without detailing the successor, while preserving all current-increment seal,
pre-code, scope and evidence obligations. No future-increment tests are manufactured for the experiment. If the
current-inc test cannot meet the existing pre-code contract, stop and file a scoped Q with evidence and options;
no automatic collect-only substitution, test rewriting, skipped claim, active-slice authority or policy change is
approved here. Q-V2-ROLLING-1's prior active-slice premise was my misinterpretation and is withdrawn.

**Ordered implementation slices and DoD (all unchecked).** Respect STEP9/STEP9A and S0 host prerequisites;
when a required STEP9A interface is absent, amend that owner through a scoped replan, not a parallel engine.

- [ ] B1 — run the current-increment pre-code diagnostic described above against the production root, and audit `SessionOutcome.final_text` /
  `_cmd_run` / `_run_stage` / revision boundary and artifact consumers on direct and nested managed paths. It may
  record a blocking result: this is diagnostic, not B6 acceptance. If an existing pre-code contract cannot be
  satisfied or the selected outcome transport is not viable, stop and file a scoped Q. Record reproducible
  commands, fixture, outcomes and exact owner; no success or host claim from a mocked substrate.
- [ ] B1a — fix and prove the seal/graph equality and seal→binding tuple checks in the owning STEP9A modules before
  handing new rows to the verifier (source-audited adapter contracts 1–2); include both seal producers and an EDGE
  mutant. This is a prerequisite for B2/B3, not a second seal, not the full runner.
- [ ] B2 — atomic grammar cutover (D-V2-11), explicit TEST-ID and total FUNCTIONAL obligation, both site modes,
  all prompt/skill/schema/fixture readers and safe diagnostic routing. Preserve valid multiple tests per CT.
  Migrate `acceptance_defect.affected_scope` and correction output, `kill_attribution` bindings,
  `verification_attempt._check_kill_targets`, `_sealed_attempt_payload`, `_verification_evidence_lines` and
  their callers/tests from TARGET-ID to unambiguous CT identity in the same cutover. Keep V1 frozen; read historical
  target-ID records in their original shape without rewriting or treating them as new CT evidence. Test old/new
  records, correction and eval readers, including `tests/test_v2_seal_store_and_mint.py`.
  Ship an executable-route guard with the cutover: until B3/B4 provide required evidence, the controller must
  refuse or produce a blocking missing-mutation result, never pass `kill_required=()` as if no check were owed.
  If this guard cannot land safely on its own, land B2–B4 together; test the intermediate and final paths.
- [ ] B3 — compose the bounded coder final-text block through the real coder→controller path; bind planned and
  deferred rows to the post-stage candidate view; exercise multiple CTs, strict duplicate/missing/extra fields,
  provenance/staleness/revision mismatch and closed failure reporting. A pinned-only or no-deferred stage requires
  no block; a supplied block must still be well-formed and contain no unauthorized proposals.
- [ ] B4 — implement managed exact-nodeid baseline/mutation using existing engine and port; preserve F9 fail-closed
  transition and do not claim mutation execution until this and B3 are live. Repair assertion-phase classification
  at the STEP9A owner via the scoped prerequisite, then consume it here.
- [ ] B5 — integrate complete attempt/eval evidence, mode matrix and history (adapter contracts 3–6). A stage-time CT/TEST/nodeid check
  runs without relying on status ticks. V2 CT83 completed-slice auditing of persisted late bindings is a separate
  task gated by Q-V2-STATUS-1: source-prove revision-safe completion/evidence identity before reading ticks; the V1
  script is not a V2 producer-ownership proof. Do not claim B5/SLICE3's full ownership DoD until that task closes;
  any semantic slice-ownership assertion not derivable from source is reported as a residual, not invented.
- [ ] B6 — prove a real vertical caller→planner→seal→coder→candidate→managed verification→artifact flow and
  retained history for pinned/deferred cases, followed by the existing host/S0/W4 witness, separately reported.

Planned test ownership (names below are **NEW targets**, not existing evidence):
`tests/test_ai_native_acceptance_bundle.py::test_mint_rejects_changed_graph_semantics_with_original_plan_bytes`;
`tests/test_ai_native_acceptance_defect.py::test_correct_rejects_changed_graph_semantics_with_original_plan_bytes`;
`tests/test_ai_native_kill_attribution.py::test_binding_rejects_foreign_ct_and_cross_revision_receipt`;
`tests/test_admission_v2_provenance.py::test_v2_rule_survives_real_route_and_legacy_contract_ids_stay_strict`;
`tests/test_verify_gate_live.py::test_coder_proposal_reaches_pinned_verifier_and_observe_enforce_routes`;

`tests/test_ai_native_plan_v2.py::test_functional_kill_requires_explicit_owned_test_and_accepts_deferred_site` and
`::test_multiple_tests_per_contract_are_preserved`; `tests/test_ai_native_kill_attribution.py::test_managed_binding_and_exact_assertion_phase`;
`tests/test_ai_native_acceptance_collection.py::test_managed_baseline_and_mutant_share_pinned_identity`;
`tests/test_v2_verification_attempt.py::test_required_kill_and_all_contract_tests_survive_projection`;
`tests/test_ai_native_bootstrap.py::test_current_increment_seals_without_detailing_outlined_successor`;
and the existing `tests/test_verify_gate_live.py` production-caller bank for a **NEW** pinned/deferred binding
case reaching the actual stage/artifact writer. The pre-code diagnostic must establish whether this bootstrap bank reaches the production path; if not, move the NEW
test to the verified live-composition bank, retaining the same oracle. The post-implementation B6 acceptance, not
the diagnostic, must pass.
Mutation handoff: removing the B1 required-test check must fail the first parser test; replacing structural graph
comparison with the old substring check must fail both named seal-producer tests; removing the revision binding
must fail the managed binding test; collapsing determinate VACUOUS into `errors` must fail the observe route case;
bypassing the stage→binding call must fail the real caller test. These are
planned oracles and mutation targets, not claims they already exist or have killed a mutant.

Required tests: parser/refusal matrix including explicit TEST-ID even with one test, duplicate CT directive, dotted
method, both operators/callee, cross-CT selector, mixed executable/disposition, traversal/symlink, no source at
admission; two tests per CT without lost claims; known seam and a deferred fresh implementation whose internal
rename does not modify the seal; missing, stale, duplicate, malformed and foreign proposals; candidate/port/executor
revision mismatch and altered closure; mutation not applied, over-limit payload, baseline failed, mutant pass,
assertion failure vs other call exception, setup/teardown, skip, second nodeid, malformed/truncated JUnit, runner
exit mismatch, timeout and provenance failure; planned/coder provenance and append-only retry history; observe and
enforce including linear/adaptive caller routes; current increment plus outlined successor and pre-code import case. Each new enforcement rule has a named
producer kill-check and the production caller has an EDGE kill-check; prove removing the binding/validator cannot
produce a green attempt. Test real durable effect/no-effect, not just an HTTP status. UX diagnostics must be
bounded, structured, identify available CT/TEST and name a permitted action. Measure first-pass admission, repair
causes, tokens/tool calls and stale/missing site frequency as baseline, without invented success thresholds.
Local targeted tests, static/format and no-new-red gate comparisons are necessary; live host evidence and S0 are
separate and cannot be inferred from fake executors, a documentation change or a local green.

**Bounded planning questions — both resolved 2026-11-22.** Q-V2-ACC-1: the test root is fixed at `worklogs/<slug>/acceptance/tests/`, the trusted external inputs (workspace `pytest.ini`, runner, toolchain) are bound by digest at seal, and the transitive-import half stays a **named residual** rather than a closed gate — an import that reaches outside the closure is pinned, so a change to it invalidates the seal instead of silently changing what ran. Q-V2-ACC-2 = **D-V2-10**: every CT is discharged exactly once at admission; refusal there is the repair trigger, and the seal refuses while any contract is uncovered. Neither may become a free-text exception or a newly invented reviewer gate. The fixed `acceptance/tests/` root, artifact C and mode A remain selected; no hash-only custody and no second runner.

### SLICE4: Role capabilities, question lifecycle, and production status ticks

**STEPS:** outcome<br>
**DEPS:** SLICE1, SLICE2, SLICE3<br>
**INTENT:** Compose the planner→controller→coder→verifier route with capability boundaries and harness-owned V2 lifecycle ticks. Preserve planner autonomy for bounded product questions; do not add an approval handoff.<br>
**Production producer/caller:** `workflow_controller.py` role/stage dispatch, `_admit_plan`, `_run_stage` and terminal transitions; `workflow_tool.py` child invocation. Canonical artifact ownership in `notes/artifact-schema-and-grammar.md` is the design reference but current production Markdown tick producer is absent. Caller/EDGE is actual chat `invoke_workflow` entering managed `run_workflow`.<br>
**Planner-owned acceptance:** `tests/test_ai_native_roles_and_ticks.py` (new), real workflow composition. C1 for roles/ticks, C3 for capability/authority attacks.

| CT | Class / primary INV | Acceptance behavior | TEST-ID → exact selector |
|---|---|---|---|
| CT-4.1 | FUNCTIONAL / INV-04 | Planner can author semantic plan/SCN/questions/acceptance payload; controller alone validates/mints seal/admission; coder gets scoped task and mode-A read-only closure only after seal; eval receives pinned evidence. No generic planner project writer. | TEST-4.1 → `tests/test_ai_native_roles_and_ticks.py::test_real_role_composition_enforces_planner_controller_coder_capabilities` |
| CT-4.2 | FUNCTIONAL / INV-10 | After the status-producer design gate is resolved without mutating/bypassing sealed semantic bytes, production harness alone emits revision-bound V2 ticks on actual lifecycle transitions; STEP `[x]` requires its named EXIT-CHECK (TEST-ID) evidence and sequential-prefix rules; CT `IMPLEMENTED` requires implementation evidence, and CT `VERIFIED` is forbidden unless canonical passing verification, non-vacuity and L2 judgment all exist. This MVP must leave CT `IMPLEMENTED` when it lacks L2 judgment; pytest green or host PASS alone never promotes it to VERIFIED. Refusal/uncertainty stays truthful, recoverable and not-DONE. | TEST-4.2 → `tests/test_ai_native_roles_and_ticks.py::test_production_harness_owns_v2_ticks_without_false_verified_state` |
| CT-4.3 | CONSTRAINT / INV-11 | `notes/open-questions.md` is lightweight, project-scoped working material; planner may resolve ordinary product questions with option/rationale/evidence. Unresolved Q blocks only dependent scope; changing ratified INV triggers replan. No mandatory interactive ask or coder approval. | TEST-4.3 → `tests/test_ai_native_roles_and_ticks.py::test_question_resolution_blocks_only_dependent_scope_and_replans_invariant_change` |
| CT-4.4 | PRESERVATION / INV-04 | Existing modes, bounded repair/replan budgets, parent/child handoff and return reconciliation remain correct; no bypass via linear/adaptive role loop or outer success summary. | TEST-4.4 → `tests/test_ai_native_roles_and_ticks.py::test_all_workflow_dispatch_modes_preserve_seal_barrier_and_child_result` |

```verify
uv run pytest tests/test_ai_native_roles_and_ticks.py tests/test_invoke_workflow_tool.py tests/test_managed_workflow_e2e.py -q
```

**Failure/negative controls:** attempt planner writes outside payload; coder starts before seal; shell/file writes to acceptance bytes; model attempts to tick plan; unresolved unrelated Q does not block independent slice; unresolved dependent Q blocks only that slice; invariant rewrite without replan refuses; child timeout/failure/uncertain return remains structured non-success; adaptive and linear paths both observe admission barrier. **Producer kill-check:** remove the V2 tick emit/update at the production transition and the exact tick test fails; remove capability enforcement at dispatch and actual role composition demonstrates unauthorized write or premature coder. **EDGE kill-check:** remove outer chat→managed child binding or stage→tick producer call and C1 caller test fails. **Local DoD:** actual composition covers roles, status side effects, open-question behavior and refusal; all supported dispatch modes covered; no handoff approval requirement; targeted checks and authoring/typing pass. No host tick result claimed.

**Open semantic detail:** the Q record fields/statuses are selected in §2 and implemented in SLICE1. Q-V2-STATUS-1 is not a routine coder choice: it blocks status-tick implementation and SLICE5 until source proves a revision-safe authority design. Capability/question lifecycle work may proceed independently; no status-tick producer or host witness is claimed before that gate.

### SLICE5: Fresh-project vertical MVP, result contract, and W4 host witness

**STEPS:** prescriptive<br>
**DEPS:** SLICE1, SLICE2, SLICE3, SLICE4<br>
**INTENT:** Prove the whole AI-native product through its real production caller, then specify the independent W4 host witness and final package registration. Local green, simulation, or a test callback is not host acceptance.<br>
**Production producer/caller:** `cli.py::_build_run_tool_registry` → `workflow_tool.py::build_invoke_workflow_tool` → managed child `run_workflow`/acquisition/bootstrap/admission/coder/eval/verifier and authority. Existing `tests/test_managed_workflow_e2e.py` proves other nested workflow behavior locally but does not prove V2 bootstrap.<br>
**Planner-owned acceptance:** `tests/test_ai_native_workflow_e2e.py` (new) plus selected unit/component tests above. C1/C2/C3 and exact production producer + caller/EDGE kill checks.

| CT | Class / primary INV | Acceptance behavior | TEST-ID → exact selector |
|---|---|---|---|
| CT-5.1 | FUNCTIONAL / INV-12 | Fresh unique slug through real chat registry and `invoke_workflow`; actual managed planner authors V2 content, harness materializes/validates/seals, coder executes after seal, verifier evaluates same pinned closure, terminal caller gets structured success and durable artifacts/ticks. | TEST-5.1 → `tests/test_ai_native_workflow_e2e.py::test_fresh_project_runs_chat_to_pinned_verifier_through_production_composition` |
| CT-5.2 | CONSTRAINT / INV-11 | Production negatives: invalid/colliding slug, planner wrong slug, malformed/mixed/V1 output, missing/ambiguous test closure, custody drift/write, unsupported mode B, provider/tool failure, uncertain install, verifier failure. Each reports safe stable result and authoritative no-effect/refusal or explicit durability-unknown; no false success. | TEST-5.2 → `tests/test_ai_native_workflow_e2e.py::test_fresh_project_refusal_matrix_never_claims_success_or_overwrites` |
| CT-5.3 | FUNCTIONAL / INV-10 | Approved-host witness observes production V2 status ticks and exact V2 plan revision/status transitions on the installed pinned image, including one bounded refusal path. Evidence records image SHA/digest/profile/config and authoritative workspace revision. | TEST-5.3 → `tests/integration/test_ai_native_workflow_host.py::test_installed_host_proves_v2_ticks_and_fresh_project_lifecycle` |
| CT-5.4 | PRESERVATION / INV-12 | Existing selection path, parent I03 human-only record, no-V1-fallback policy, frozen producer baseline and existing host case contracts remain intact; new producer mapping follows reviewed explicit `NEW:` protocol. | TEST-5.4 → `tests/test_ai_native_workflow_e2e.py::test_v2_cutover_keeps_parent_human_only_and_existing_route_separate` |

```verify
uv run pytest tests/test_ai_native_workflow_e2e.py tests/test_ai_native_plan_v2.py tests/test_ai_native_bootstrap.py tests/test_ai_native_acceptance_bundle.py tests/test_ai_native_roles_and_ticks.py -q
```

**Failure/negative controls:** run success and each refusal through outer chat tool, observe child lifecycle completion and actual authority revision/tree, not mocked outcome; test one unrelated failing test never promotes acceptance; missing host prerequisites fail (never skip); absent opt-in fails before side effects. **Producer kill-check:** remove production bootstrap/admission/seal/tick transition and the exact real-flow test fails. **EDGE KILL-CHECK:** remove chat registry `invoke_workflow` binding or its call into the managed child and the C1 success test loses the complete effect and fails; no test direct-calling internals substitutes. Run these on the actual implementation at local test-clearing and again as applicable under approved production composition; do not use an unregistered mutation as host evidence. **Local DoD:** fresh slug success and authoritative refusal/no-overwrite bank pass via actual local managed composition, output and revision evidence are inspectable, all child/parent lifecycle results stable, no unreviewed skips, and targeted static/authoring checks pass. This closes only the slice-local DoD, never W4.

#### Required W4 host witness and E2E package work (not yet registered or frozen)

The witness is an MVP acceptance obligation, not evidence that `I03-LIVE-S08` already covers V2. Candidate join: existing S08 is the likely home only if its reviewed oracle is extended to assert the exact new V2 producers and effects; otherwise use the explicit producer-mapping protocol and obtain reviewed case assignment before suite freeze. Do not edit `I03-LIVE-S07` registered source row or producer baseline without a separately reviewed producer-baseline revision. Do not modify frozen baseline/coverage/index/register merely to make this plan appear registered.

Before final W4 suite freeze, STEP10's package owner must:

1. Re-ground every new production producer and caller from source; assign each a distinct `NEW:` producer key using the existing protocol. For S08 sharing, the host oracle must assert V2 fresh-project `invoke_workflow`/bootstrap/seal/tick effects and refusal semantics, not merely nested invocation or inventory. Keep `LIST_PROJECTS` distinct; its S08 oracle must also assert `projects`/`incomplete` semantics plus inventory/read before that mapping is shared.
2. Update the planner-owned `e2e/I03/live-verification.md` case/run sheet, E2E README index, producer coverage, producer baseline only through reviewed baseline revision, exact integration fixture/package and required selectors, `implementation-handoffs.md`, and any generated/result schema or coverage artifacts required by `scripts/check_execution_e2e_coverage.py`. Freeze and review the final fixture and package before host execution. The linked plan does not make these changes or assert that the witness is registered.
3. Run `python scripts/check_execution_e2e_coverage.py` and artifact checks after mapping changes; retain frozen producer counts/keys unless authorized reviewed revision. Unmapped producer, altered frozen key, or changed baseline without authorization fails, not a waived result.
4. Execute only in W4, after W3 closes: fresh-fetch/freeze approved `origin/main` candidate SHA on clean approved host; perform the sole approved `AUTO_STASH=0 SKIP_TESTS=1 SKIP_UV_SYNC=1 PRUNE=0 fa update`; record exit, running image SHA/digest/config/profile/healthy status and explicit in-container CLI/core-import smoke. Then freeze image; run reviewed suite with `FA_REQUIRE_EXECUTION_HOST=1`, including unmocked direct+nested witnesses, real clean-readiness test, every reviewed `tests/integration/` host case, and this V2 witness. No rebuild/update during suite. Missing host/cgroup/image/opt-in prerequisite is failure, never skip. Capture authoritative project revision, plan version, AcceptanceBundle identity, exact verifier revision/digest, status ticks, tool result, safe diagnostics and no-effect evidence for refusal controls.

**Ledger append host E2E obligation (NEW, not registered):** add a reviewed live-host case to the W4 package
that observes a real permitted ledger append through its production author/authority path and verifies the durable
revision, exact appended content and preservation of prior entries after a fresh read; include protected-plan/oracle
write refusals and failed/uncertain publication controls with authoritative no-effect or explicit uncertainty.
Prove producer and caller/EDGE via local mutation tests. The ledger is a writable working journal per E686, not
authoritative test evidence; do not waive custody. Record actual
host evidence in the worklog ledger, distinguish test artifacts from project ledger, and map the actual producers
through the reviewed protocol above.

**Host exit:** independently reviewed PASS for installed image identity/health/smoke and all required cases, including the V2 witness; reviewed fixture/package/producer mapping frozen before execution; no simulated/local evidence substituted. Until that exact run exists, mark NOT RUN/OPEN. W4 remains separate from STEP9B plan completion and Arena-local slice DoD.

## 5b. Cross-slice failure policy and evidence semantics

*Numbered 5b because §5 above already owns 5 and the cross-references elsewhere point at it; this section stays next to the slices it governs.*

| Failure | Required behavior |
|---|---|
| Malformed/unsupported/V1 plan or incomplete graph | Stable validation refusal before coder; no fallback, partial parse, or provider dispatch. |
| Invalid/colliding slug | Stable non-retryable refusal for collision/invalid path; preserve existing tree, no substitution, no selection fallback. |
| Correctable authored-document error (D-V2-9) | Bounded repair round against the published increment with sanitized diagnostics; on budget exhaustion the project stays present and unadmitted (`BLOCKED`), never half-admitted. |
| Stage rejected / crashed before publish (D-V2-9) | `reject_view`; no `worklogs/<slug>/` in the canonical tree; current revision unchanged; structured failure to the caller. |
| Publish uncertainty after the seal boundary | Durability-unknown / blocked; writer not released; preserve operation evidence; prohibit blind retry/overwrite; recover forward or explicit operator disposition. |
| Missing/stale AcceptanceBundle, incomplete closure, nodeid ambiguity, mode B request, byte drift/write attempt | Fail closed before coder or verifier; no downgrading to hash-only sidecar or visibility fallback. |
| Exact kill oracle collects/errors/skips/times out/crashes/zero-runs | ERROR/non-kill; never PROVEN. Target pass under mutation is VACUOUS. Unrelated assertion failure is separate and cannot prove target. |
| TEST-DEFECT | Preserve old revision, seal, and evidence; planner decision yields new sealed revision or no-change rationale; affected gates rerun; invariant change triggers replan. |
| Child/provider/verifier failure | `invoke_workflow` returns stable safe structured failure after lifecycle settlement; no `ToolResult.ok` success implication from child status alone. |
| Host prerequisite absent | Explicit host test failure before side effects; never skip or convert to local pass. |

## 6. Owner duties and review

- **Planner:** author the canonical semantic artifacts, graph, acceptance closure, selectors and Q decision trace; every CT has exactly one primary INV; no coder-authored acceptance substitution. Resolve ordinary project questions best-effort; record option/rationale/evidence; replan invariant changes.
- **Harness/controller/authority:** own input validation, slug/path, fixed scaffold/materialization, lifecycle, whole-project validation, admission, AcceptanceBundle minting, capability projection, structured outcomes and evidence persistence. Production status ticks remain gated by Q-V2-STATUS-1. Never let planner supply destination paths or choose trusted grammar.
- **Coder:** implement admitted behavior and choose internal seams; cannot change sealed acceptance bytes or gain broader authority; no mandatory approval handoff. Report TEST-DEFECT against exact seal/test/nodeid only, and when a test is genuinely wrong submit a **test-change proposal** (patch artifact outside the sealed tree plus the same report) for the planner to apply and seal (D-V2-4).
- **Eval/verifier:** execute pinned exact closure, independently classify mapped outcomes, report evidence without changing plan/test bytes.
- **Independent reviewer:** review source call graph, safety/failure matrix, custody and kill attribution; high-risk independent-review triggers remain an open policy question and are not added as mandatory MVP gate unless ratified.
- **Host operator/reviewer:** freeze approved image and package, provide actual deployment identity, execute required host cases, preserve raw evidence, independently disposition PASS/FAIL/NOT RUN. No local author may label host acceptance.

## 7. Planning questions register (lightweight)

This linked plan fixes a lightweight V2 `open-questions.md` table (6 compact fields so prompts stay focused): `Q-ID`, `Question`, `Blocks` (`INV | CT | SLICE | NON-GOAL | RISK`), `Status` (`OPEN | RESOLVED | REPLAN`), `Decision / Evidence` (chosen option, resolver/source, concise rationale), and `Updated`. Planner may resolve ordinary product choices best-effort without interactive `ask_user`, **except** when a conflict or impossibility touches a ratified `INV`, `NON-GOAL`, `RISK`, or `authority` boundary (E530/E549): those must never be silently overridden and must transition to `REPLAN` / `ASK` escalation. OPEN blocks only affected dependencies.

| Ref | Question / bounded choices | Affected scope / default handling | Evidence (measured) |
|---|---|---|---|
| Q-V2-BOOT-1 | **RESOLVED 2026-11-20 = A′ (D-V2-5).** The closure is installed with the project; the seal is minted from the installed bytes + plan bytes + receipt revision and stored as an immutable per-seal file in authority-private metadata with one atomically-replaced private pointer. Admission = pointer present + seal loadable + `verify_plan` + `verify_sealed_root` + `verify_revision` against the receipt revision; standing custody is content-based because the coder's own writes advance the current revision and no revision ancestry is recorded. Recovery mints only when the pointer is absent (byte-identical result) and hard-fails on an unloadable seal; a replan appends a new seal and swings the pointer, keeping `supersedes_sha256` walkable. Audit, edge cases E1–E9: `notes/q-v2-boot1-install-seal-audit-2026-11-20.md`. | SLICE2/3; no `INSTALLED_UNSEALED` record, no fifth intent kind, no new recovery branch, and nothing is written into `worklogs/` after install. | |
| Q-V2-ACC-1 | **RESOLVED 2026-11-22 = config inside the root, plus a named residual (last cell).** Prove the transitive helper/config closure is inside `worklogs/<slug>/acceptance/` or specify the smallest trusted external pytest config/runner/toolchain inputs to pin, plus enforceable existing authority budgets for file count, per-file/aggregate bytes, path length and depth. | SLICE3; test root is selected. Dynamic/unbounded imports and ambiguous plugins fail closed; do not add a runner. | **Closed as code, with the residual named.** The runner config is *inside* the sealed root, not an external pinned input: `acceptance_closure.ACCEPTANCE_INI` requires `pytest.ini` at the root (`:223 missing-pytest-ini`, `pytest-ini-invalid`) and refuses any key outside the allowlist (`:266 validate_pytest_ini`), and the scaffold ships it with the project (`project_scaffold.py:152`) — so the digest covers the file the run actually reads. **Residual:** transitive *imports* are not enumerated; the closure carries what the planner declared, and an import reaching outside `acceptance/` fails closed at collection rather than being silently trusted. No runner added. |
| Q-V2-ACC-2 | **RESOLVED 2026-11-22 = refuse at admission (D-V2-10).** Not "waive", and not "only at seal". A `TEST_REQUIRED` contract with neither a selector nor a disposition is refused where the plan is admitted, because a refusal there *is* the repair trigger (`bootstrap-invalid-metadata` → one authoring repair → re-admission), and because the seal must assert the consequence rather than discover it. `HARD + NON_EXECUTABLE` stays legal: the disposition pipeline exists precisely for critical unobservable claims, and refusing it would leave the mechanism only for claims nobody cares about. Its residual — the caller grants a *reason*, and the planner chooses *which claim* carries it — is recorded with its mitigation in S2 (attested ids, reason and owner written into the seal and the run report). The measurements that made the old wording untenable: a `SOFT`+`TEST_REQUIRED` contract with no selector is admitted and grades `UNCOVERED`; `KIND` is read in exactly one place and only to exempt; `mint_seal` mints happily with `attested=()` and records no contract total; three tests encode the hole deliberately. | SLICE1 (parser policy), SLICE2/3 (seal and route); implemented by S1–S2 in §8. No waiver for a test the planner did not write, no free-text exception, no new reviewer gate. Measurements: [evidence-model-audit-2026-11-21.md](evidence-model-audit-2026-11-21.md); cross-review and reproductions: [i03-external-design-review-2026-11-22.md](i03-external-design-review-2026-11-22.md) §3, §6, Appendix A. | |
| Q-V2-STATUS-1 | **RESOLVED 2026-11-20 = projection outside the sealed bytes (option A).** Ticks live in a harness-written status record plus a deterministic human-readable projection; the sealed plan bytes never change on a tick and validation never reads the status record. Chosen because a single agent must learn slice/step state in one read instead of filtering a multi-thousand-line ledger, and because tick state must not be able to influence admission. | SLICE4b/5; the status record is authority-owned and revision-referencing, never in `acceptance/`, never an admission input. No re-admission/re-seal per tick. | |
| Q-V2-MODEA-1 | **RESOLVED; amended 2026-11-23 by E657.** True read-only acceptance for coder shell and file tools is required, with authority-private seal and revision-backed projection as primary route; isolated immutable payload is mandatory if that route cannot be proved. The earlier shell drift-detection-only resolution is superseded. | SLICE3 CT-3.3/3.6, STEP9A B1; actual Docker host proof remains W4. | |
| Q-V2-EVIDENCE-1 | **RESOLVED 2026-11-22 = A (D-V2-12).** **Do the four ratified disposition reasons belong in one bucket?** `HOST_READINESS`, `DEPLOYMENT_IDENTITY` and `DURABILITY_POWER_LOSS` are *deferred executables* — each becomes checkable in a named place (a host probe, an image digest, a fault-injection test); only `OWNER_APPROVAL` is untestable by construction. Today all four are `NON_EXECUTABLE` + a caller's grant, so "we cannot run it here" and "nobody can ever test this" cost the same human signature. Options: **(A, recommended)** replace the severity axis with a closed *route* axis `EVIDENCE: TEST | HOST_PROBE | APPROVAL`, each naming its artifact — a probe file plus host label, an image digest, or the approval lane — and let admission check the artifact exists; a `HOST_PROBE` claim is `pending` (a debt that blocks deploy) rather than `attested` (a decision that does not). **(B)** keep one bucket and only narrow the grant (contract id + claim hash + expiry, per P4-8). **(C)** status quo. A/B differ in what the planner is allowed to be wrong about: with B it still declares "unprovable", with A it declares "provable elsewhere" and the pointer is checkable. Ratified as A: the record half (route, artifact, owner, `reviewed_at`, scope digest, `pending` beside `attested`) lands in S2's single schema bump, the authoring half (`ROUTE:` replacing the two-valued `EVIDENCE:` axis on invariants, the prompt example and the grammar table) lands with S6/D-V2-11 because it changes what the model writes and must arrive with the one table. A also re-scopes the S0 host probe from a wiring prerequisite to an evidence type. |
| Q-V2-S0-1 | **Where does the S0 managed-executor probe live, and what counts as proof?** The plan names "the managed-executor probe at `acceptance/tests/`" and stops there: it does not say whether that is a *repo* test that opens a real managed view through the authority and runs one sealed pytest command inside it, a probe inside a **fixture project's** acceptance closure exercised by a live `fa invoke-workflow` run, or both. The stakes are not stylistic — S0 gates SLICE3 wiring (nothing may depend on the pinned substrate before something proves it actually executes sealed bytes), so the answer decides what "SLICE3 has started" means. Measured 2026-11-22: this environment has **no container runtime** (`docker` and `podman` absent, no `/var/run/docker.sock`), so the probe can be written here and cannot be *run* here. Options: **(A, recommended)** a repo test `tests/test_ai_native_managed_substrate_probe.py` marked `xfail(strict=True, reason="requires the W4 Docker host: managed executor + approved profile")` — the repo's V4 rule allows exactly this, `strict` makes the host run fail loudly if the probe stops working, and the file carries the exact command to run it; **(B)** no repo test: a documented manual host check plus a ledger entry, and SLICE3 wiring begins with the real run; **(C)** only the fixture-project closure probe, which needs a live planner run first and therefore cannot gate SLICE3 — it *is* SLICE3. Senior take: A now and C as the live evidence once a host can run it; **RESOLVED 2026-11-22 = A.** Ratified by the operator's direction to finish the remaining work after the recommendation was presented (and after the transport measurement in E612 showed B's premise — an in-process run without a container engine — does not exist). Landed as `tests/test_ai_native_managed_substrate_probe.py`; the host XPASS and marker removal remain owed on W4. B leaves nothing in the tree that would notice the substrate breaking. **Transport answer measured 2026-11-22 (E612), which closes the interesting half of this question:** a Docker-free, in-process path to a real managed command does **not** exist, so the probe is host-only by construction and option A is not a concession to the sandbox. `backend.CellBackend` (`:95`) is built over `DockerEngine`/`DockerCells` (`:20`, `:113`) and every RUN goes through `self._cells.launch_new` (`:252`, `:290`); both fallbacks are ruled out in the modules' own words (`supervisor.py:288` "no … host-shell fallback", `service.py:7` "no host-side runner"), and `DockerUnavailableError` is caught only to fail honestly (`:266`, `:305`, `:493`, `:527`). The harnesses that look like they run a cell do not: `test_execution_composition._configure_local_cell_backend` points the authority at `test_execution_docker.Endpoint`, a fake Docker unix socket that answers the HTTP API and records calls, so `test_managed_workflow_e2e.py` proves the protocol rather than the execution. The option-A probe (written, unrun, unlanded) is parked verbatim at `notes/s0-managed-substrate-probe-draft-2026-11-22.md` with its host command. | Blocks SLICE3 wiring start. | |
| Q-V2-SLICE3-1 | **RESOLVED 2026-11-22 = one append-only attempt log (the second half of this row).** What artifact does a sealed verification write? `write_verification` (`workflow_controller`) persists a `PlanVerification` whose per-slice record is built from the planner's own `verify` commands — the thing CT-3.6 retires on the V2 route. A sealed run produces `SealedVerification` (seal, closure digest, both revisions, sealed nodeids), which is a different shape and answers a different question ("did the sealed oracle execute against this candidate" vs "did the slice's declared commands pass"). Options: **(A, recommended)** add a sibling artifact `verification-v2.json` written beside the existing one, leaving the legacy artifact untouched and the gate mode logic reading whichever the route produced; **(B)** widen `PlanVerification` with an optional sealed block, so one artifact stays one artifact but every existing reader must be taught to ignore it; **(C)** replace the legacy artifact on the V2 route and accept that anything reading `verification.json` cannot see a V2 run. A is additive and keeps D-V2-8's "publication is not admission" honest, but it is new state and must be argued. | Blocks CT-3.6's wiring half. **Answered 2026-11-22 by going back to entities instead of files:** the minimal surface is **one append-only attempt log** — `VerificationAttempt = RunIdentity + [ClaimEvidence] + [CommandRun] + Verdict` — where the route is a *value* in the attempt (`sealed` / `planner-fence`) rather than a second file. Today's `SliceVerification`/`PlanVerification` lacks the whole `RunIdentity` (seal, closure digest, sealed revision, candidate revision) and attaches per-contract evidence only as mutation verdicts; that absence, not the layout, was the real question. So: not A (two logs, join by attempt index — the join is the drift), not C (destroys the legacy record operators use to switch to enforce mode), but **B with a different justification**: route-tagged attempt, legacy keys retained for the legacy route. Reasoning in `notes/verification-entities-2026-11-22.md`. **Adversarial pass changed the design (same note, second half):** per-contract rows must fold mutation evidence in, otherwise the artifact joins two structures by contract id; `route` splits into grammar (`v2`/`legacy`) and a per-command `authored_by` (`planner`/`harness`), which turns the rule that the fence never drives a V2 result into a write-time invariant instead of an omission; `claims[]` must cover the seal's total including `attested`/`pending`, or a vanished selector reads as green; a refused attempt must be distinguishable from an empty one; and `candidate_revision_id` must come from the substrate's own view, refused on disagreement (`verifier-revision-mismatch`), rather than believed from the caller. | |
| Q-V2-SLICE3-2 | **RESOLVED 2026-11-22 = the entity below, implemented and landed.** What is the verification attempt entity, and which write-time rules make it honest? Answered 2026-11-22 by entity analysis plus an adversarial pass, both verified against the code (`notes/verification-entities-2026-11-22.md`, findings F1–F9). The artifact stays **one append-only attempt log**; the attempt is `route (v2|legacy) + identity + claims[] + commands[] + errors[]`, with `blocking` derived. Refused at write time: `claims-total-mismatch` (claims must cover the seal's `contracts_total`, including `attested`/`pending`), `claim-mutation-missing` (a contract that declares a kill target may not carry `mutation=None`), `fence-on-v2-route` (no `planner`-authored command on the V2 route), `empty-attempt-unexplained` (empty claims require non-empty errors), `identity-missing-on-v2`, and `verifier-revision-mismatch` (the candidate revision comes from the substrate's own `ViewRef.base_revision`, not from the caller). Two of these are corrections of my own first draft: the refusal/empty distinction became an invariant instead of a field (F4 — redundant state can disagree), and the unbounded `detail` became a per-field bound because the eval renderer truncates by *head*, so one long field evicts the rest of the evidence (F6). **Landed 2026-11-22 (E616):** the entity and its five write-time refusals are in `src/fa/inner_loop/verification_attempt.py` (21 tests, 7 mutants killed), and `verify_sealed_acceptance` now refuses `claim-mutation-missing` before running a cell when the plan declares kill targets. Implementation order: entity + invariants and their tests (done), then `run_kill_checks` composition (F9), then the controller branch that retires the fence. | Blocks CT-3.6's wiring half. |
| Q-V2-REVIEW-1 | **OPEN (deferred).** Which high-risk changes merit independent reviewer trigger? | Future policy discussion; not an MVP gate absent ratification. | |
| Q-V2-RESUME-1 | **Withdrawn — it asked the wrong question.** As filed it asked *which authority tells a resuming run what grammar an installed project is written in*, and offered marker-reading as the pragmatic answer. That misplaced the problem: it treated "a V2 project cannot be resumed" as a requirement, when resuming V2 is not a product scenario today. A V2 project's bytes are rendered by that same run's bootstrap renderer and admitted immediately; there is exactly one grammar forward (`plan_v2.PLAN_FORMAT = AI-NATIVE-PLAN-V2`) and one legacy grammar on its way out, and the mechanism for the transition is **already ratified in §2/§40**: "trusted installed runtime pins supported V2 grammar independently of project files… reject unsupported/missing/mixed/V1 input before coder". Rejecting V1 is not marker dispatch, so no new policy decision was ever needed. **Measured on the route that declares V2:** a valid V2 pair admits (`graph` present, no `format_error`); a V1 document is refused (`plan-format-marker-roadmap`); a malformed V2 is refused (`unknown-top-level-section`). That is the requirement — *a new plan validates correctly and malformed input errors* — and it holds. The marker is also not planner-owned (`plan_semantics._MARKER` is a renderer constant and `publication._METADATA_LINE` refuses a prose `Plan-Format:`), so reading it can never trust model text. | Nothing is blocked. P0-2 is re-scoped below; P1-1/P1-2 proceed. Retained as a **withdrawn** row rather than deleted, so a later reader sees the reasoning and does not re-open a solved question. | |

### Ratified operator decisions, 2026-11-20 (STEP9B finalisation)

| Ref | Decision | Consequence for the slices | Evidence (measured) |
|---|---|---|---|
| D-V2-1 | **V2 is the only forward grammar.** `src/fa/inner_loop/plan_v2.py` (produced by STEP9A slice 2, 45 local tests, 22 killed mutants) is the V2 parser/admission module; V1 is kept only as a *lightweight legacy module* that still serves the stages that need it today and is **removed entirely later**. It is not extended, not mirrored and not a supported product path. | SLICE1 re-targets its parser work from "extend `plan_ids.py`" to "bind `plan_v2.parse_plan` at the admission choke point, keep `plan_ids` frozen as legacy, and add the removal obligation to the plan". `PlanSnapshot` carries the V2 graph alongside the legacy `PlanIds` only while the legacy module exists. | |
| D-V2-2 | **Full V2 cutover with `invoke_workflow` as the single entry point.** The legacy manual `fa workflow --plan` route is retired rather than kept in parallel; the same `invoke_workflow` composition is callable by an agent (chat tool) and by a human (CLI). No V1 fallback, no marker dispatch, no parallel code path. | SLICE1/SLICE5: the CLI surface becomes a thin human-callable front for the same composition, not a second workflow implementation. Retirement of the legacy route is part of the slice, with its own negative control (the retired route cannot run a V1 plan). | |
| D-V2-3 | **Status ticks are a projection, not a plan edit** (Q-V2-STATUS-1 = A). | SLICE4b: harness writes one authority-owned status record keyed to the sealed revision and renders the artifact view; ticks never enter `acceptance/`, never change the seal and are never an admission input. | |
| D-V2-4 | **The coder may propose a test change, never apply one** (Q159 = C). A proposal is a bounded patch artifact outside the sealed tree plus the `DefectReport` (seal, `TEST-ID`, nodeid, assertion); the planner applies it through `acceptance_defect.correct(...)`, which mints the superseding seal and returns the affected tests/kill targets to re-prove. | SLICE3/SLICE4: no new state machine and no new writer into `acceptance/`; the proposal path is a second *input* to the existing correct/uphold decision. Prompts stay the first gate; the proposal path exists so the coder never has to weaken an assertion to make progress. | |
| D-V2-5 | **Install→seal chain = A′** (Q-V2-BOOT-1). Closure shipped inside the installed revision; seal derived from installed bytes + plan bytes + receipt revision; immutable per-seal files in private metadata plus one atomic pointer; revision pin at coder admission, content checks afterwards; supersede appends rather than overwrites. | SLICE2/SLICE3: no `INSTALLED_UNSEALED` record, no fifth intent kind, no extra recovery branch, and the seal never lives under `worklogs/`. | |
| D-V2-6 | **Mode A = actual read-only file-tool and shell projection** (operator amendment E657, 2026-11-23). The earlier detection-only shell allowance is superseded. Authority-private seal and revision-backed projection are preferred; if not provable use isolated immutable payload. Drift/publication checks are supplementary. | STEP9A B1, SLICE3 CT-3.3/3.6; profile/mount changes may be required and must be verified locally and on W4 host. | |
| D-V2-9 | **Planner-as-writer, scaffold-inside-the-stage** (ratified 2026-11-21). The planner holds a WRITE `PROJECT` view and authors the documents; the harness writes only the scaffold, inside the same stage, through the same port; one stage publication produces the project; the bundle/`install_project` path is retired for create-new. See §2 "D-V2-9.1–9.6" for the mechanism and the authoring split. | SLICE2 CT-2.3/2.7/2.8; supersedes D-V2-7 and its ordering; P2-4 owns the deletion list. | |
| D-V2-8 | **Publication is not admission** (ratified 2026-11-21). Under D-V2-9 the plan is committed to canonical history *before* it is validated, because the planner writes the artifact and the ordinary stage publication commits it. Admission remains the sole gate to coder. A revision holding an unadmitted plan is an audit fact with no consumer: no coder dispatch, no seal, no verification, no reader pin that presents it as the plan of record. A refused run therefore leaves either no project (stage rejected) or a blocked project with an unadmitted revision (repair budget exhausted) — never a half-valid state that looks approved. | SLICE2 CT-2.9; the revision history must not be read as "the plan was valid from the start", and no component may treat "published" as "admitted". | |
| D-V2-10 | **Evidence totality, and `KIND` deleted** (ratified 2026-11-22; answers Q-V2-ACC-2). Every admitted CT is discharged exactly once — an executable selector resolving to one collected nodeid, or a caller-granted typed disposition — and no label exempts a contract. `KIND` leaves the MVP grammar, `PRESERVATION` is never dispositionable, and the seal records the contract total, attests every contract, and refuses to mint while any is `UNCOVERED` or has no owner. `HARD + NON_EXECUTABLE` stays legal; the residual (the caller grants a reason, the planner picks which claim carries it) is mitigated by recording attested ids, reason and owner in the seal and the run report. | SLICE1 policy and field removal; SLICE2/3 seal mint on the route; the three tests that encode the hole are rewritten with their rules named. No waiver for a test the planner did not write. | |
| D-V2-11 | **One machine-readable grammar table, and the doc triad moves atomically** (ratified 2026-11-22). `notes/artifact-schema-and-grammar.md` is the single V2 source, but it is still the V1 contract: measured 2026-11-22 it holds 0 occurrences of `AI-NATIVE-PLAN-V2`, 0 of `KIND:` and still teaches `TESTS:`. The rule vocabulary is split across three places that disagree — `plan_v2` emits rule codes, `admission_schema.ADMISSION_RULES_V2` (`:71`) has no `plan-v2` name, and `contract_id` (`admission_schema.py:169`, `CT\d+[a-z]?`) cannot carry the `CT-<slice>.<n>` ids the parser produces. | SLICE1: schema, the three skills, their `INJECT.md` surfaces and `tests/test_skill_grammar_emit.py` change in one commit, and the prompt's worked example must parse. Until then no new contract is designed against the document. | |
| Q-V2-SLICE3-4 | **RATIFIED 2026-11-22 = A (operator), implemented — a declared kill target that never runs must not look like "none declared".** The V2 route passes `kill_required=()` unconditionally, correctly, because `KillTarget(target_id, ct, test_id)` carries no *operator*, and — more precisely than this row first said — no agreed shape for `target_id` either (the authoring prompt teaches `path::symbol`, every fixture uses a dotted id; Q-V2-SLICE3-5), so nothing here is executable (F10 item 5). The artifact then records `kill_required: []` even for a plan that declares `KILL-TARGETS  KT-1 -> CT-1.1, TEST-1.1`, so absence of mutation evidence and absence of a declared target are the same bytes — F3's shape, one field over, and the reason F1 was called the worst defect. Options: **(A, recommended)** record the declaration without claiming it ran — `kill_declared: [{target_id, ct_id, test_id, executed: false}]` on the attempt and in the artifact, `proven` unchanged, and the schema bump shared with N3; **(B)** pass the declared CT ids as `kill_required` so the attempt refuses `claim-mutation-missing` — honest but it blocks every plan that declares a target until `run_kill_checks` exists (F10 item 5), i.e. a permanent refusal is traded for a silent gap; **(C)** status quo with the gap named in the run report. A and B differ in which party is asked to be patient: with A the report tells the truth and the coder keeps working, with B the pipeline stops on a field the grammar only uses for attribution. | SLICE3 (artifact, **additive — no schema bump**: `verification.json`'s envelope is versioned and the new keys live inside one attempt entry, and N3's `attestations` ride the same change; the earlier "one bump with N3" was not needed and would have broken readers for nothing); `run_kill_checks` stays unbuilt until the grammar can express an executable mutation (Q-V2-SLICE3-5). | Measured 2026-11-22: `grep kill_required src/fa/inner_loop/workflow_controller.py` → one call site, literal `()`; artifact key `kill_required` is always `[]` on V2; audit table in [verification-entities-2026-11-22.md](verification-entities-2026-11-22.md) §"F1–F9 closure audit". |
| Q-V2-SLICE3-3 | **RESOLVED 2026-11-22 = A (operator): one axis, one spelling.** Two vocabularies described the same fact — did the mutation die? — and they disagreed on case: `SliceVerdict` (`proven`/`vacuous`/`error`) versus `kill_attribution.ATTRIBUTION_VERDICTS` (`PROVEN`/`VACUOUS`/`ERROR`). Measured before the fix: `ATTRIBUTION_VERDICTS` was exported and read by nothing (no validation inside `KillAttribution`), and `MutationEvidence` refuses anything outside `MUTATION_VERDICTS` (lowercase), so the day CT-3.4/3.5 wired attribution into the attempt, the honest outcomes were a hard `mutation-invalid` on a correct proof or a silent `False` from comparing `"PROVEN"` to `SliceVerdict.PROVEN` — F1's exact shape, one entity over. Options were **(A, chosen)** unify on `SliceVerdict` and derive the constant; **(B)** keep the uppercase spelling with one derived set and one conversion function; **(C)** status quo plus a guard test. A won because there were zero production consumers and zero stored artifacts, so the change was free exactly then and a migration later. `NODE_OUTCOMES` was **not** merged: `PASSED/FAILED/SKIPPED/MISSING` describe one run, not a verdict (no verdict counterpart exists for `MISSING`), so it is typed as its own `StrEnum` with the set derived from it. | SLICE3 (before CT-3.4/3.5 wiring); no artifact, grammar or prompt change. | Landed: `kill_attribution.py` (`NodeOutcome`, derived `NODE_OUTCOMES`/`ATTRIBUTION_VERDICTS`, `KillAttribution.verdict: SliceVerdict` with `kill-attribution-invalid`, `NodeRun` validating `kill-run-invalid`); bank 35 passed, 9/9 mutants killed; `tests/test_ai_native_kill_attribution.py::test_an_attribution_verdict_is_the_verdict_the_attempt_accepts` is the bind that stops the third spelling appearing. |
| D-V2-13 | **DECIDED 2026-11-23 — rolling-wave planned/deferred mutation binding and explicit TEST-ID.** | SLICE3 B1–B6 specifies behavior, ownership, cutover, gates and tests; no production implementation is claimed. | Operator direction and E630; source anchors and open dependencies in the SLICE3 block. |
| Q-V2-SLICE3-5 | **DECIDED 2026-11-23 — D-V2-13: explicit CT/TEST obligation plus planned or deferred site binding.** Each executable FUNCTIONAL CT has one mutation check and an explicitly named TEST-ID; coder may propose a late site as untrusted input, harness binds and verifies. Target grammar and implementation contracts are in SLICE3 B1–B6; this supersedes the earlier `TARGET-ID = path::symbol` recommendation. | SLICE3 and atomic D-V2-11 cutover; transport proof and current-increment pre-code diagnostic remain open implementation gates, not further permission to drop the obligation. | Current `KillTarget` has no operator; production still passes `kill_required=()` and records `kill_declared`. |
| Q-V2-SLICE3-6 | **DIRECTION SELECTED 2026-11-23 — managed harness-owned in-band composition (a), not yet implemented.** Reuse the existing managed overlay, pure AST transform and exact sealed oracle; no host fallback, no second runner. Exact receipt/scratch lifecycle is an engineering proof, not an assumed two-command requirement. | SLICE3 B3–B6; preserve F9, detailed assertion-phase classification, one report per receipt, same pinned revision/closure and observable outcome. | `_run_inband_kill_check` exists; baseline, sealed argv, port plumbing, managed `run_node_oracle` and production composition do not. |
| Q-V2-ROLLING-1 | **WITHDRAWN 2026-11-23** — active-slice scope was incorrectly inferred from rolling wave. Operator clarified that planning detail advances increment by increment, with later increments outlined. No partial-seal or scoped-verification authority is selected. | Current-increment pre-code collection remains a source-grounded diagnostic in D-V2-13, not an open policy decision about future increments. | `parse_plan` parses one increment; `collect_sealed_tree` runs the current closure before mint. |
| Q-V2-SEQUENCE-1 | **RESOLVED 2026-11-23 — operator: remove ownership ceremony; actively resolve dependencies toward I03 MVP.** Do the necessary custody/attribution work on existing seams to satisfy STEP9A, preserving its DoD and predecessor order; reconcile new grammar and remaining slice obligations as they are implemented. No review, STEP or host gate is silently marked complete. | Graph/plan binding now has a scoped implementation; seal-to-binding tuple, runner/composition and associated evidence remain open. Finish STEP9A, then recorded independent STEP9B review and remaining local slices/W3, then W4. | Operator clarification and E634; parent I03 STEP9A/STEP9B exit clauses. |
| Q-V2-PRECODE-1 | **DIRECTION SELECTED 2026-11-23 — retain full pinned pre-code run and classify outcomes honestly.** A planner-authored suitable no-op/known-bad witness can support an assertion-sensitivity claim; a fake is not proof of production behavior, and skip, unexpected exception or absent producer are not sensitivity evidence. The complete STEP9A gate and actual receipt identity remain to be implemented/proven. | Future concrete fresh-project fixture must test viability without planner knowledge of future private seams. If impossible, scope a replan for an explicit producer-absent state and later mandatory checks; do not silently switch to collect-only or relax custody. This direction does not close STEP9A, B1 or the later workflow. | E638 diagnostic, source audit and E639 operator decision. |
| Q-V2-LEDGER-1 | **RESOLVED in policy (E686):** project ledger is a freely editable working journal; ordinary append/edit needs no reseal and is not authoritative verification evidence. E2E plans/run sheets are editable; host verdict depends on a recorded execution and assigned reviewer. | Implementation and host E2E are open; nested coder scope is amended by Q-V2-WRITE-SCOPE-1=A, implementation open. No new authority journal is required merely to append project ledger. | Supersedes the earlier blanket ledger immutability and options A/B/C. |
| D-V2-12 | **Evidence routes: "cannot be tested here" must name where it can be tested** (ratified 2026-11-22; answers Q-V2-EVIDENCE-1 = A). The four disposition reasons are not one bucket. `HOST_READINESS`, `DEPLOYMENT_IDENTITY` and `DURABILITY_POWER_LOSS` name a place where the claim *is* checkable — a host probe, an image identity, a fault-injection case — while only `OWNER_APPROVAL` is untestable by construction. Under one bucket a reviewer's "we cannot run this in the sandbox" and a planner's "nobody can ever test this" cost the same signature, and a cheap signature is the `KIND: SOFT` hole with better syntax. So the route is a closed axis derived from the reason — `HOST_READINESS`/`DEPLOYMENT_IDENTITY`/`DURABILITY_POWER_LOSS` → `HOST_PROBE`, `OWNER_APPROVAL` → `APPROVAL` — and the route decides the **kind** of artifact the caller must name: for `HOST_PROBE` a probe path inside the sealed acceptance closure plus a host label (`probe:<path>@host:<label>`), for `APPROVAL` a doc digest, an issue or a review (`doc:|issue:|review:`). `plan_admission.parse_dispositions` enforces the reason↔kind pairing, so "host readiness" cannot be discharged by a document that says nothing about a host; `mint_seal` proves the probe path is in the closure, records route, artifact, owner, `reviewed_at` and a scope digest over the invariant and contract text it attested, and lists such contracts as **`pending`** — a debt that blocks deploy — beside `attested`, which stays the set of contracts a named party carries. Invalidation is the rule that keeps this from being a bypass: a plan edit invalidates the seal through `plan_sha256`, `mint_seal` now refuses a graph whose bytes are not the plan bytes handed to it (so a scope digest can never describe a plan nobody sealed), and the scope digest names exactly which sentence was attested, so a re-review can be shown to cover the new text. The authoring surface (`ROUTE:` on invariants) is S6/D-V2-11; no route removes the requirement that a named party carries the claim, and `APPROVAL` is the only route with no artifact to check — which is what makes it the expensive one. |

Two consequences of D-V2-1/D-V2-2 that the implementation slices must state explicitly: the legacy module
has a named removal step (so it cannot become permanent by drift), and the retired CLI route has a
negative control (so its absence is proven, not asserted).


## 8. Implementation sequence and local acceptance gates

The dated progress paragraphs below are historical snapshots, not assertions of current route or fresh test results; D-V2-13 and the latest ledger govern remaining work.

1. STEP9 is locally closed (E556/E558); confirm STEP9A closes with its actual evidence before new-slice implementation. STEP9A's exact custody/mapping controls are dependencies, not repeated implementation authorization.
2. Implement SLICE1; run its named local command and producer/EDGE kill checks. No dependent cutover until V2 parser/admission gate is complete.
3. Implement SLICE2 as **D-V2-9** (P2-4): delete the payload/renderer layer, plumb the authoring dispatch and its write allowlist, write the scaffold inside the stage, add the metadata cross-check and the `project_exists` mapping, then rewrite the prompt. Keep D-V2-5's revision-bound seal mint. Prove slug no-clobber (`project_exists`) and the rejected-stage-leaves-nothing property before touching the prompt.
4. Implement SLICE3 and prove full closure, mode-A projection and exact attribution before coder can consume acceptance tests. **Recorded deviation (2026-11-22):** the route now consumes sealed acceptance claims while exact attribution is still unwired (`kill_attribution` has no production caller). What keeps that honest rather than a hole is Q-V2-SLICE3-4 = A — a declared target is recorded with `executed: false` and the artifact names the gap — and the exit criterion is that every executable FUNCTIONAL CT moves to `kill_required` only with the D-V2-13 planned/deferred binding and real runner wired; no executable obligation is silently proven without mutation. **Q-V2-ACC-2 is RESOLVED (D-V2-10)** and implemented by S1 before CT-3.1 is written; **Q-V2-ACC-1 is closed as code plus a named residual** (the transitive-import half is pinned by digest and fails closed, not enumerated) — its §7 row carries both; **Q-V2-MODEA-1 is RESOLVED, amended E657**: CT-3.3 requires actual prevention for both interfaces, with fallback if unprovable; a profile change may be necessary.
5. Implement SLICE4 roles/questions; status tick producer is blocked until the distinct design gate in §2 has a source-proven, revision-safe resolution. Cover every actual dispatch path and caller edge.
6. Implement SLICE5 local real composition only after SLICE4's design gate closes; test success/refusal matrix and record local-only evidence. Then finish reviewed E2E package/mapping updates before suite freeze; host test remains unrun until W4.
7. Every slice local DoD is independently reviewed and evidenced before remaining STEP10/W3 work. Broad baseline failures/skips remain their real disposition under E544; do not claim pass. Do not begin W4 before W3 closes.

**Standing gate: `no new red` (ratified 2026-11-22, E608).** A red baseline is tolerated as *known*; adding to it is not. The unit of evidence is the **list**, never the count: `scripts/gate_tracker.py record` runs `pytest`, `mypy`, `ruff` and `fa authoring-check`, keeps each raw log beside a normalised finding list, and `gate_tracker.py compare <base> <head>` prints the new/gone sets and **exits 1 when anything is new**. A baseline is recorded from a worktree of the base commit with `--pythonpath`, because an editable install otherwise imports the working tree's package and measures the wrong commit. Counts are explicitly *not* evidence: mid-S1 mypy went 83 → 65 → 62 while three of those errors were mine. `ruff format --check` is part of `just lint` (`justfile:230`) and **is not recorded** by `gate_tracker.py`, which is how S2/S3 drifted four format-clean-at-base files under the recorded gate set (E613; fixed in `7b3561b`); the recording tool gains the formatter before the next gate run. `xfail` stays what the repository already enforces (`tests/test_authoring_rules_tests.py` V4: `strict=True` plus a reason) and is allowed only for a test whose prerequisite is the real Ubuntu/Docker host — never for typing, logic, or a sandbox quirk. Known red that turns out to be code, not environment, is fixed before deploy as its own list item; known red that is environment is recorded with its reason, not worked around.

**S3 status (2026-11-22) — landed (mode A / CT-3.3, closes P4-4).** `execution.workspace.sealed_project_paths`
derives the protected set from the admitted plan — the whole `worklogs/<slug>` tree, or the plan path on the legacy
route — and both view construction sites use it, so a top-level coder (`PROJECT`) and a nested coder (`MUTATION`)
refuse the same bytes. Tests: `test_execution_purposes.py::test_v2_coder_projection_protects_every_sealed_semantic_path`
(both purposes, existing and *new* files, the directory and its ancestors, plus a scoped negative control: another
project stays writable for `PROJECT` and stays outside the approved roots for `MUTATION`), the derivation test
(`..._is_derived_from_the_plan_not_declared_by_the_caller`), the layout↔enforcement bind
(`test_ai_native_acceptance_bundle.py::test_every_scaffolded_project_artifact_is_inside_a_protected_path`), and the
drift half tightened at both verdict entry points to the named rule `seal-byte-drift` with `executor.commands == []`.
Producer kill-check: with the derivation reduced to the plan path, the projection test fails as
`expected PATH_DENIED; observed success` for an injected file beside the seal — the hole P4-4 described.
Not in S3: the S0 host probe at `acceptance/tests/` (needs a live run, first thing SLICE3 wiring) and CT-3.6.

**CT-3.6 status (2026-11-22) — verifier half landed, wiring half blocked.**

**Measured defect (F10, E617): on the `PLAN-V2` route the verification stage is green by emptiness.**
`PlanSnapshot.ids` is `PlanIds()` for a V2 snapshot by design (`plan_admission.py:74–76`, `:401`), and the call
site passes exactly those ids to `verify_plan` (`workflow_controller.py:1757` via `_stage_plan:1335`). Measured:
`verify_plan(PlanIds(), root=<tmp>)` → `plan commands: ()`, `slices: ()`, `errors: ()`, **`blocking: False`** —
so enforce mode reads a stage that measured nothing as a pass, today, on the only forward grammar. This is
strictly worse than the F9 guard (which cannot even fire: V2 `KILL-TARGETS` are `KillTarget(target_id, ct,
test_id)` attribution, whose `TARGET-ID` is an unconstrained string — the prompt teaches `path::symbol`, the fixtures use dotted ids — and which carries no operator, so nothing is executable in the current code; D-V2-13 now specifies its planned/deferred successor), and it fixes the order of work: projection →
substrate-named revision → controller branch on the snapshot grammar (not on "are there commands") → artifact
writer. Recorded in `notes/verification-entities-2026-11-22.md` (F10), including the correction that F9 did not
make today's V2 results false.
`acceptance_collection.verify_sealed_acceptance` runs the sealed closure on a managed substrate only, refuses
a host-shaped one, refuses a closure/code overlap, and records both revision identities (E615). What is missing
is the caller: `workflow_controller` still routes the V2 verification through `verify_plan(plan_ids, …)`, which
executes the planner's `verify` fences. Retiring that fence decides what a V2 verification artifact *is*, and
`write_verification` currently persists a `PlanVerification` built from those very commands — so the choice is
filed as **Q-V2-SLICE3-1** rather than made by whoever next touches the file. Order of remaining work (F10): projection of the sealed result into `VerificationAttempt`, substrate-named candidate revision (F5), controller branch on the snapshot grammar, artifact writer; `run_kill_checks` is **not** on the critical path because no route can declare an executable mutation today.

**F10 item 1 landed (2026-11-22, E618): the projection exists, its caller does not.** `acceptance_collection.sealed_attempt` turns a `SealedVerification` into a `VerificationAttempt` (one claim per sealed selector, harness-authored command with its receipt, seal totals carried verbatim, identity proved against the bundle *and* against the run). Two defects were found while wiring it and both were fixed in the same change: the seal recorded no `CommandResult` (`collection-no-command` now refuses a receipt that cannot name its command), and the attempt's `claims-total-mismatch` summed three list lengths while the seal requires `pending ⊆ attested`, so it refused every correct projection of a real seal; it is a coverage rule now. This does **not** close F10 — nothing calls the projection yet, so `_stage_plan` still reaches `verify_plan(PlanIds())` and the V2 verification stage is still green by emptiness. Item 2 (F5) and item 3 (controller branch on `snapshot.format`) remain, in that order.

**F10 item 2 landed (2026-11-22, E619): the substrate names the revision (F5).** `ReadOnlyManagedBashExecutor.view_revision_id` answers from the authority's `ViewRef.base_revision`, `ManagedVerifyCommandExecutor` forwards it (never invents one: absent or blank yields `None`), and `verify_sealed_acceptance` refuses a substrate that cannot name the candidate revision or names another (`verifier-revision-mismatch`) **before** any cell command. `candidate_revision_id` is now checked rather than recorded. Remaining: item 3, the controller branch on `snapshot.format` — nothing calls the sealed verifier yet, so the V2 stage is still green by emptiness.

**F10 item 3 landed (2026-11-22, E620): the controller branches on the snapshot's grammar — F10 is closed.** `_run_stage` selects the sealed gate when the admitted snapshot's `format` is `PLAN-V2` and never reaches `verify_plan` on that route, so the planner's `verify` fence can no longer be the oracle and an empty command list can no longer read as a pass. A missing seal (`acceptance-seal/*`), an unmanaged cell (`verifier-substrate-required`), a substrate that cannot name the candidate revision (`verifier-revision-mismatch`), a verifier refusal (`sealed-verification/*`) and a blocking attempt (`sealed-attempt/*`) are each recorded as a blocking `PlanVerification` error; a passing stage carries the receipt that ran. The attempt is held on `_WorkflowAdmission.last_attempt`. What is *not* done is item 4: `verification.json` and the eval block still render only the receipt and the reason, not the claims, the identity or the route.

**F10 item 4 landed (2026-11-22, E621): the artifact and the eval block carry the attempt.** `write_verification(..., attempt=...)` adds `route`, `identity`, `claims`, authorship and the seal's `attested`/`pending`/`contracts_total` beside the untouched legacy keys, and OR-s the attempt's verdict into `blocking`; the legacy route passes `None` and its entry is unchanged. The eval block renders the claims with the harness's own `proven` word and each `detail` labelled `untrusted` and cut to 300 characters (F6). F10's four items are now landed; item 5 (`run_kill_checks`) stays unbuilt because no route can declare an executable mutation. The remaining V2 work is outside that list: proving the substrate half on the W4 host (S0) and the S0 probe's XPASS removing its `xfail` in the same change.

**F1 schema gap closed (2026-11-22, E622).** `MutationEvidence.verdict` is now drawn from `KILL_CHECK_VERDICTS` (derived, not copied) and both of its readers compare to `SliceVerdict.PROVEN.value`. Measured before the fix: the landed code accepted any string and compared against a literal `"PROVEN"`, so the only verdict production can emit read as *not proven*. That was the last F1–F10 rule the entity did not implement; F1–F10 are now spec-complete. `kill_attribution`'s second, uppercase verdict vocabulary was filed as Q-V2-SLICE3-3 and is **resolved = A** (operator, 2026-11-22): it is now `SliceVerdict`'s own member set, `ATTRIBUTION_VERDICTS` is derived from it, and `KillAttribution`/`NodeRun` validate what they name (see the Q-V2-SLICE3-3 row and `notes/verification-entities-2026-11-22.md`).

**N1–N3 closed (2026-11-22).** The three defects the entity audit left open are implemented and evidenced; the full
record is [verification-entities-2026-11-22.md](verification-entities-2026-11-22.md) §"N1–N3 landed". N1 is custody:
the seal moved out of the tracked tree into `.fa/` (`acceptance_seal_store.SealStore`: immutable per-digest records
plus one atomically-replaced pointer), `mint_seal` now has a caller on the create route — after every admission
refusal, before any coder — and the stage reads it back through the store, so the V2 stage no longer refuses
`acceptance-seal/missing` by construction and CT-3.6's guard has a subject. N2 is `Q-V2-SLICE3-4`, implemented as
the recorded option **A** (declared targets recorded with `executed: false`; `kill_required` stays empty; option B
remains one revert of `kill_declared` away and still needs the operator's choice). N3 is D-V2-10's report half: the
seal's attestation records — who, on what evidence, when — now reach the artifact and the eval block instead of only
their id lists. Both new rule families are validated on every route, not just `v2`. Verification: new bank
`tests/test_v2_seal_store_and_mint.py` 19 passed, affected bucket 675 passed, full suite 8411 passed / 1 failed (the
pre-existing pyrefly topology red), the previously-owed live bank `tests/test_verify_gate_live.py` **581 passed in
183 s**, 14/14 mutants killed, gate recording `2026-11-22-head-n1n3` vs `head-2f9924b` **0 new**, `fa
authoring-check` diagnostics 0. Still open: `Q-V2-SLICE3-3`, and the operator's
confirmation of A.

**S0 status (2026-11-22) — landed as option A.** `tests/test_ai_native_managed_substrate_probe.py` walks the
production path (`managed_execution_for_run` → `PIN_READER` → `ReadOnlyManagedBashExecutor` →
`ManagedVerifyCommandExecutor` → `capture_test_nodeids`) and asserts the nodeid of a test that exists *only*
inside `worklogs/demo/acceptance/`, plus the harness's own in-band command. It carries
`xfail(strict=True, reason="requires the W4 Docker host: …")` per the repository's V4 rule, and its failure
was verified to be the *intended* one: `--runxfail` shows `ExecutionUnavailableError: execution_unavailable`
from the managed executor, i.e. the supervisor refused at EXEC because no container engine exists — not a
broken probe. On the W4 host it must XPASS, and `strict` turns that into a failure so the marker is removed in
the same change that proves the substrate. The transport reading behind this (E612) stands: there is no
Docker-free in-process path, so A is the only home that can exist, not a sandbox concession.


**S2 status (2026-11-22) — landed.** `SCHEMA_VERSION` 2, mint refuses `seal-uncovered-contracts` /
`seal-attestation-unowned` / `seal-attestation-artifact-missing` / `seal-plan-graph-mismatch`, the record carries
`contracts_total`, `attested`, `pending` and `attestations` (contract, invariant, reason, route, artifact, owner,
`reviewed_at`, scope digest) inside the digest, and `load_seal` re-proves the block (`seal-attestation-mismatch`,
`seal-attestation-route-invalid`, `seal-totality-mismatch`) instead of trusting the digest. D-V2-12's checkable half
is in: `probe:<path>@host:<label>`, the closed reason→kind matrix (`disposition-evidence-route-mismatch`, mapped in
the tool's failure table as retryable), and the probe-existence check at the seal. E609 records the change set and
the two defects found while writing the oracles (a bare `AcceptanceBundleError` escaping `correct`; `plan_sha256`
naming bytes a graph did not describe). Still open by design: `ROUTE:` on invariants and the grammar table (S6), and
the deploy gate that *acts* on `pending` (W4). Next: S3 (mode A / CT-3.3 across both coder topologies), per §8.

**Next slice, decided 2026-11-22 (E605): S1 policy closure, then S2 seal totality — before any SLICE3 wiring.**
These are the two cheapest changes that stop the pipeline saying "ok" when it cannot. Both are inside SLICE1/SLICE2
scope, neither needs a live managed run, and each is proven by banks that already exist. The order is load-bearing:
S1 closes the admission hole, S2 makes the seal assert what S1 now guarantees. A seal minted before S1 would
certify a graph admission no longer accepts.

*S1 — policy closure (one change set).* (1) `workflow_controller._admit_published_project` (`:3209`): drop
`and granted`, so `bind_dispositions` always runs (P4-1). (2) `plan_v2._admit_evidence` (`:594`): remove the `KIND`
exemption (`:622`) and refuse every `UNCOVERED` contract at admission; remove the required `KIND` field (`:312`)
together with its fixtures and the prompt example (D-V2-10, P4-5). (3) `disposition-undeclared` becomes
non-repairable, and the retryable `disposition_required` row enters both closed tables — the tool's failure map and
the controller's repairability map — so the model's reachable move is "ask the caller". (4) `_REPAIR_WRITABLE_SUFFIXES` (`:3044`, today exactly the increment and `open-questions.md`) admits
`roadmap.md` and `acceptance/` as well, and the repair task text carries the rule code and names the legal
repair moves (P4-3). The roadmap belongs in the allowlist for a mechanical reason: `plan-format-marker-roadmap` is repairable by `_may_repair_authored_project` (`:2929`), yet its only fix is outside today's allowlist, so the repair is a guaranteed failure that costs a model call and ends in the worse code `bootstrap-refused`. Widening cannot weaken the gate — the second revision is re-admitted whole, including the metadata cross-check — it only stops a dead-end repair. (5) `cli.py:975–993` gains `--dispositions <path-or-json>` (CT-1.5, P4-6). (6) The three
tests that encode the hole are rewritten with their rules named, plus an always-bind control and a repair-scope
control. Gate: `uv run pytest tests/test_ai_native_plan_v2.py tests/test_ai_native_dispositions.py
tests/test_ai_native_bootstrap.py tests/test_invoke_workflow_tool.py -q`, `uv run ruff check` on the touched files,
`uv run fa authoring-check`. The `artifact-schema-and-grammar.md` edits for the *vocabulary S1 changes* ride with S1 —
the document must not describe a field S1 deletes — while the full grammar-table rewrite stays S6 (D-V2-11).

**S1 status (2026-11-22).** Admission's policy half is landed: items 1–3 in `763239f` and `f932b13` (KIND deleted and evidence totality at admission, the always-bind `_admit_published_project`, and `disposition-undeclared` closed as non-repairable with its retryable caller code), and item 4 here, together with **P4-7** — the defect that made the whole repair scope inert and that no existing test could see because every one of them bound the workspace port directly. Evidence: 11 hand-run mutants, each killed by its named oracle (`test_a_create_new_repair_may_write_only_the_paths_a_refusal_can_be_fixed_in`, `test_the_bound_repair_path_runs_both_stages_and_binds_the_result`, `test_a_grammar_refusal_reaches_the_repair_as_the_parser_rule`, `tests/test_profiles_allowlist.py`). Item 5 (`--dispositions` ingress, P4-6) landed in the same change set: the flag is on the parser, the CLI decodes it and hands it to the tool unmodified, and the tool's `parse_dispositions` remains the single rule. Still open in S1: item 7 (the grammar-doc vocabulary, D-V2-11's first half) — **measured and closed 2026-11-22 without an edit**: `notes/artifact-schema-and-grammar.md` contains `KIND:` ×0, `AI-NATIVE-PLAN-V2` ×0, `CT-` ×0, `DISPOSITION` ×0 and `^EVIDENCE:` ×0, so it describes no field S1 deletes and contradicts nothing S1 changed; it is the V1 contract, and the V2 grammar table that replaces it is D-V2-11/S6. Writing a partial V2 section now would create the *fourth* description the review counted, three commits before the slice whose job is to collapse them into one — so the measurement is the deliverable, not prose. E607 for the whole set is next.

*S2 — seal totality and the attestation record (one change set, one schema bump).* (1) `acceptance_bundle.mint_seal`
(`:296`) refuses while any contract is `UNCOVERED` or has `owner is None`, and that refusal holds for **every**
producer — the second one is `acceptance_defect.correct` (`:246`), which reaches the same refusal through `mint_seal`.
(2) The record carries `contracts_total`, `attested`, `pending`, `uncovered`, with
`len(selectors)+len(attested)==contracts_total` asserted on mint *and* on load; `SCHEMA_VERSION` goes 1→2 (no
production seal exists and `load_seal` fails closed on an unknown version, so migration is zero). (3) **P4-8, the
grant leaves no trace:** the seal carries `attestations` — contract id, invariant id, reason, route, artifact,
owner, `reviewed_at`, scope digest — inside the digest, and `load_seal` refuses a block whose contract ids are not
exactly `attested` or whose `pending` is not a subset of it (D-V2-12). (4) The route half that does not need the
grammar: `plan_admission` gains the `probe:<path>@host:<label>` evidence kind and the closed reason↔kind matrix, and
`mint_seal` refuses a `HOST_PROBE` whose probe path is not in the sealed closure — the artifact-existence check can
only happen where the tree is visible, which is the seal, not admission. (5) `mint_seal` refuses a `graph` whose
bytes are not `plan_bytes`, so `plan_sha256` means what it says and a scope digest cannot describe an unsealed plan.
(6) Tests cover both producers, the reason↔kind matrix, the missing-probe refusal, the totals identity on load, and
prove an unknown-version or drifted seal is refused rather than read leniently (P4-2). Not in S2: `ROUTE:` on
invariants, the prompt example and the grammar table (S6/D-V2-11), and any deploy gate that would *act* on
`pending` — the seal states the debt, the acting gate is W4.

*Deliberately not in this slice:* S0 (the managed-executor probe at `acceptance/tests/`) needs a live run and only
gates SLICE3 wiring, so it stays the first thing SLICE3 does; mode A / CT-3.3 is S3 and must cover both coder
topologies (P4-4); the grammar table and the doc triad are S6; and no severity field is introduced, because it still
has no consumer.

For every implementation slice, follow `/tests-writing` (active skill): existence/pre-call check, C1 live composition for product behavior, C2 for chat/CLI boundary, C3 adversarial controls, type-honest fixtures, observable state/effect oracle, explicit flag/dispatch matrix, path inventory, no reimplemented production double, producer kill-check and caller/EDGE kill-check. Source-ground exact production call path before designing the kill mutation; a test-only call or helper-only mutant is vacuous. New tests are planner-authored and TEST-EDITS are sealed; coder support tests remain separate. Real durable effects must assert the authoritative workspace revision/operation state or absence on refusal.

## 9. Adversarial review findings (source-grounded; no runtime conformance claimed)

- **Confirmed source constraint, not a current product defect:** managed plan publication is a candidate-buffer, pinned-`PlanRef`, same-path forward-only replacement (`src/fa/execution/publication.py:740–775`; `src/fa/execution/workspace.py:4059–4130`). It is not a general status metadata write API. The former draft's suggestion to update Markdown ticks via this seam was unsupported and is replaced by Q-V2-STATUS-1. The existing code also has no V2 tick producer; implementing one without a revision/seal-safe path is blocked, not assumed feasible.
- **High-confidence integration risk, pending source audit:** changing the admitted increment to persist a tick changes its plan bytes/`PlanRef`; the design must establish how admission and STEP9A's revision-bound seal remain valid or are re-established. Evidence: `workspace.py:4089–4105` pins candidate publication to the exact `PlanRef`; current workflow admission binds to a `PlanRef` (`workflow_controller.py:3296` onward). This is not reported as a production failure because V2 ticks are not implemented.
- **Confirmed install behavior (Q-V2-BOOT-1 resolved by D-V2-5; audit `notes/q-v2-boot1-install-seal-audit-2026-11-20.md`):** `prepare_bundle` is currently only a fixed three-file private validated bundle (`publication.py:507–553, 664–701`), distinct from STEP9A's `AcceptanceBundle`. Install is no-clobber/forward-only and has recovery that uses the exact installed tree to finish the revision (`workspace.py:3485–3554, 5385–5422`). Not proven is how V2's expanded closure is staged and how a crash after recovered install but before final AcceptanceBundle minting resumes against that exact operation/revision. Solved as A′: closure inside the installed revision, seal derived from installed bytes + plan bytes + receipt revision, immutable per-seal files with one atomic pointer, revision pin at admission and content checks afterwards.
- **Confirmed current caller behavior requiring a scoped V2 fix:** after child lifecycle settlement, `workflow_tool.py:894–904` unconditionally returns `ToolResult.ok` with `exit_code` and `status`; there is no success gate there for child exit 0 plus terminal `DONE`. CT-2.5 now requires the V2 new-project route to enforce that gate and map child failure safely, while leaving `AUTO_SELECT_EXISTING` semantics unchanged.
- **Confirmed defect — V1 validators would judge V2 documents (found in the 2026-11-20 adversarial review):** `snapshot_from_bytes` always runs V1 `extract_plan_ids` (`plan_admission.py:160–169`), whose slice regex matches `PLAN-V2` headings verbatim (`plan_ids.py:65`); `_validate_plan_admission` then runs `precheck`, `validate_kill_directives` and a `zero-slices` refusal unconditionally (`workflow_controller.py:3058–3100`). A correct V2 plan would therefore be admitted or refused by V1 rules — precisely the mixed state INV-01 forbids. SLICE1 CT-1.3 now requires that a V2 snapshot never reaches those validators.
- **Confirmed defect — mode A was overclaimed (same review):** the plan asserted path-level read-only custody, but the only live mechanism protects the plan file (`RootedViewIO(protected_paths=plan_ref.workspace_relative_path)`, `workspace.py:2188–2196`, `2808–2816`), nothing protects `worklogs/<slug>/acceptance/`, and a writable view mounts the whole source read-write (`profiles.py:108–113`), so `run_bash` can write the closure. CT-3.3 names the real seam; Q-V2-MODEA-1 was subsequently resolved by D-V2-6.
- **Confirmed defect — the verifier still executes planner-authored shell (same review):** `slice_verification.py:552` runs the planner `verify` fence while §2 forbids planner-authored command text from driving promotion. CT-3.6 now retires the fence on the `PLAN-V2` route, keeping the frozen legacy route only.
- **No other defect found in reviewed boundaries:** the unified `invoke_workflow` V2 cutover, W2/W3/W4 ordering, STEP9A custody reuse, E2E non-registration boundary, and exact target-to-test mapping are explicitly bounded in this plan. These document-level checks do not establish parser conformance, runtime success, producer-baseline changes, or host PASS.

## 10. STEP9B plan-only verification and exit boundary

**Plan artifact checks (this task):** linked references resolve; unique slice/CT/TEST IDs; every CT has one primary INV and each executable selector has an exact TEST-ID/nodeid (a CT may have several); every planned slice has dependency, producer, caller/EDGE, exact command, local DoD, negative controls and failure behavior; all proposed slices are semantically complete; host witness and final package/index/coverage update obligations are present; no unratified recommendation becomes policy; no baseline/register row is changed; no implementation starts. Run repository document-link validation, I03 execution E2E coverage validation, and `git diff --check`. Historical note: the original review found no V2 production caller; this is no longer current. `workflow_controller._validate_plan_admission` and `_run_stage` now have V2 admission/verification paths (E620), while D-V2-13 mutation composition remains unimplemented. V1 and V2 validation remain separate. The canonical V2 grammar source/version binding is specified here as the target of SLICE1; runtime parser conformance is an implementation-slice gate, not evidence furnished by this plan.

**STEP9B exit:** complete linked plan and parent/handoff references are reviewed; document/link checks pass; no implementation, migration, deploy, test-suite pass, or host acceptance is claimed. STEP10 remains blocked until all new slices meet Arena-local DoD. W3 and W4 criteria remain exactly as in parent I03 STEP10.

## 11. Source index and grounding references

- Parent dependency/status/exit rules: [`increment-03-execution-workspace-foundation.md`](../increments/increment-03-execution-workspace-foundation.md), STEP9, STEP9A, STEP9B, STEP10; [`roadmap.md`](../roadmap.md); [`ledger.md`](../ledger.md), E530/E544–E555 and 2026-11-15 entries.
- Research decisions, source call graph, open details and bootstrap audit: [`ai-native-planner-refactor-load-bearing-research-2026-11-15.md`](ai-native-planner-refactor-load-bearing-research-2026-11-15.md), §§7, 9–12.
- Custody, revision strategy C, immutable-payload fallback, mode A, exact kill attribution and TEST-DEFECT: [`w3-acceptance-custody-kill-attribution-design.md`](w3-acceptance-custody-kill-attribution-design.md).
- Canonical V2 target: [`artifact-schema-and-grammar.md`](artifact-schema-and-grammar.md); current code grammar is in `src/fa/inner_loop/plan_ids.py`, current pre-coder admission in `src/fa/inner_loop/workflow_controller.py`.
- Chat/acquisition/bootstrap: `src/fa/inner_loop/tools/workflow_tool.py`, `src/fa/inner_loop/managed_acquisition.py`, `src/fa/inner_loop/workflow_controller.py`, `src/fa/cli.py`.
- Revision/materialization/custody substrates: `src/fa/execution/publication.py`, `src/fa/execution/workspace.py`, `src/fa/execution/view_io.py`, `src/fa/execution/profiles.py`.
- Managed verification and exact kill path: `src/fa/inner_loop/slice_verification.py`, `src/fa/inner_loop/workflow_controller.py::_pinned_verify_substrate`.
- Test class, producer and EDGE doctrine: [`knowledge/skills/tests-writing/SKILL.md`](../../../knowledge/skills/tests-writing/SKILL.md).
- Host witness package/status boundaries: [`e2e/I03/live-verification.md`](../e2e/I03/live-verification.md), [`e2e/README.md`](../e2e/README.md), [`e2e/I03/implementation-handoffs.md`](../e2e/I03/implementation-handoffs.md), producer-baseline and coverage artifacts. No new host witness is registered/frozen by this plan.

## 12. Defect register and corrections (measured 2026-11-20)

Every row below was reproduced by running the production code, not read off a document. The ids are stable so a
later entry can close a row instead of re-describing it.

| Id | Defect | Evidence | Owner / state |
|---|---|---|---|
| **P0-1** | The acquisition prompt teaches the V1 `Schema-4` Markdown the planner no longer writes, while the new-project route admits only `PLAN-V2`. A body written exactly as instructed is refused (`plan-format-marker-roadmap`; with the marker, `slice-1-unknown-field`; with headings renamed, `unknown-top-level-section`). **First real create-new cannot produce an admissible plan.** | `ACQUISITION_SYSTEM_PROMPT` (`prompt.py:1244–1258`) vs `parse_plan` on that exact body. | **Closed 2026-11-20 (E582, `7077b85`):** `plan_semantics.py` owns the payload and every byte; the prompt is rewritten in its terms with one worked payload that the CT-2.6 test walks through parse → render → parse. Remaining: the managed-run end-to-end DoD is SLICE2's. |
| **P0-2** | ~~A `PLAN-V2` project cannot be resumed.~~ **Corrected 2026-11-20: not a defect on a supported route — it was a symptom of a stale premise.** `resolve_existing_choice` builds a `PLAN-V1` snapshot, and both installed documents keep V1-shaped front matter, so a V2 pair selected through the *existing-project* route is silently admitted as a valid V1 plan (`format=PLAN-V1`, `format_error=None`, `graph is None`). That is only wrong if V2 must flow through `AUTO_SELECT_EXISTING`, and today it must not: V2 is produced by the run's own bootstrap renderer and admitted in that run; the legacy grammar is legal until retirement. The real requirement — a **new** plan validates and malformed input errors — already holds on the V2 route (valid → `graph` present; V1 body → `plan-format-marker-roadmap`; malformed → `unknown-top-level-section`). | `managed_acquisition.py:496`; `workflow_controller.py:3081`. **Measured both ways:** on the V2 route valid/malformed/V1 behave correctly; on the resume route a V2 pair yields `format=PLAN-V1`, `graph is None`; a V1 pair yields `format=PLAN-V1` correctly. | **Re-scoped, not blocked.** Belongs to **SLICE5** legacy-route retirement (D-V2-2, CT-1.5), not SLICE1/2: when the legacy route is retired, `SELECT_EXISTING` must either read the runtime-pinned marker under the §40 rule or refuse, and that choice rides the retirement's own negative control. Two facts let the retirement decide cheaply: the marker is renderer-owned, never planner-supplied, and the runtime pin is a single constant (`plan_v2.PLAN_FORMAT`). No code change now; the old "must be resumable" framing is withdrawn (E583 correction, E584). |
| **P1-1** | R2 grading predates R1. `contract_evidence` grades `ATTESTED` from `reason` alone, but after R1 a reason is only a *request*; the grant lives in `owner`/`evidence_ref`. An unbound, ungranted graph reports `attested_contracts == ('CT-1.1',)`, and `bind_dispositions` is called for its refusal only — its returned graph is discarded. The seal can therefore name a contract as attested that nobody granted. | `plan_v2.py:721–739`; `workflow_controller.py:2872–2873`. | **Closed 2026-11-20 (E585):** `ATTESTED` now requires the bound grant (`owner is not None`), and the second half — a grant proved before the install then dropped before the read-back — is closed by carrying the granted graph as `authorised` and reconciling it by *graph* in `_authorised_graph` (`None` on any difference). E577's "authorised once, never rebound" is untouched: the grant is carried forward, never re-minted. Mutants M1/M2/M5–M8. |
| **P1-2** | ~~The cluster bound is per invariant, not per grant.~~ **Re-scoped 2026-11-20:** R3/E580 had already closed the cluster (`disposition-covers-several-contracts`). The real hole is one level down — R3 bounds *contracts per invariant*, but the authorisation travels by **reason**, which the plan may reuse, so one caller decision could still authorise two different invariants. | Reproduced: two `HOST_READINESS` invariants + one grant → `('CT-1.1','CT-1.2')`. | **Closed 2026-11-20 (E585):** a reason is a one-shot capability at the point the request is parsed (`_parse_invariants` → `disposition-reason-reused`), deliberately on the *invariant* so it stays orthogonal to the cluster rule. A first attempt put it on the contract loop and reported the cluster's rule for a reuse — a surviving mutant (M4) caught the wrong diagnosis. Prompt names both codes; coherence bank pins it. |
| **P2-1** | The plan requires artifacts nothing writes. `render_bundle` emits exactly three files; `open-questions.md` appears nowhere in `src/`; `plan_v2` parses no Q records. V2 grammar *requires* selectors under `worklogs/<slug>/acceptance/tests/...`, but the install creates no `acceptance/` file at all, so admission passes a plan whose oracle does not exist. | `publication.py:562`; `grep -r "open-questions" src/` empty. | **Re-owned 2026-11-21 by P2-4:** under D-V2-9 the scaffold writer emits `open-questions.md` and `acceptance/tests/` as part of the closed set, so this defect is closed by construction rather than by extending `render_bundle`. The closure *contents* remain SLICE3. |
| **P2-3** | **The acquisition prompt instructs a shape the parser refuses.** `_acquisition_stage_task` still says "Return `BOOTSTRAP_NEW_PROJECT` with exactly that `project_slug`", while `_parse_bootstrap_choice` now requires `set(value) == {"kind","semantics"}` and raises `choice-malformed` for any `project_slug`. A model that follows the instruction is guaranteed a refusal; the test pins only the phrases `caller: <slug>`/`COLLISION`, not the instruction. Introduced by E586 and not caught by the 8 259-test suite. | `workflow_controller.py:1440–1444` vs `managed_acquisition.py:640`; `tests/test_ai_native_bootstrap.py:499–530`. | **Closed 2026-11-21 (E587)**, not patched: the `BOOTSTRAP_NEW_PROJECT` instruction disappeared with the payload route. Recorded because the same class of drift (prompt vs parser) is P0-1, and because the test that should have caught it asserted phrases rather than the contract. |
| **P2-4** | **Scaffold-first create-new (D-V2-9).** The typed-payload renderer is an orthogonal serialization for a model that already writes Markdown; it costs `plan_semantics.py` (573), the payload half of `managed_acquisition.py` (~535 of 685), `render_bundle`/`_validate_bundle_text`/`bundle_paths` (~200), `_bootstrap_bodies`/`_resolve_bootstrap_identity`/`_rendered_increment_sha256`/`_admit_bootstrap_attempt` (~150), the JSON prompt block (~180) and ~2 000 lines of renderer tests. Meanwhile the planner cannot write its own notes or its own plan, because the barriers that prevent it (`ACQUISITION_TOOLS`, `read_only_stage`, `write_allowlist`) encode a *selection*-time threat that the caller-supplied slug removed. | `plan_semantics.py`; `profiles.py:443`, `:495–499`, `:151`, `:238–256`; `cli.py:2091`; `workspace.py:222–226`, `:2843–2855`; `view_io.py:410–417`; `composition.py:413`; `client.py:963–1030`. | **Closed 2026-11-21 (E588):** the payload layer, the install chain and the renderer are deleted (proved unreachable first); the create route publishes once and admits from that revision; R1/R6 restored on the live path; `AUTHORING_SYSTEM_PROMPT` replaces the JSON wire. Implements D-V2-9 §2 (deletion order), CT-2.3/2.7/2.8/2.9, and closes P2-1, P2-2 and P2-3 with it. V1 prose (`roadmap_body`/`increment_body`) dies here as well: it has no live writer and, with a plausible scaffold, no live reader. |
| **P2-2** | `initial-plan` is not fixed. The plan states it three times ("harness-fixed, planner cannot supply it"); `choice.increment_slug` still comes from the planner's JSON and `grep '"initial-plan"' src/` is empty. | `managed_acquisition.py:590–600`. **Re-measured:** `_bootstrap_bodies` already renders the fixed key, but `render_bundle` received the planner's slug, so `increment_slug="my-own-name"` wrote `increments/increment-01-my-own-name.md` — the model chose the path admission reads. `_with_project_hint` silently overwrote a planner slug. | **Closed 2026-11-20 (E586):** the ratified proposal/resolved split. Wire = `{kind, semantics}`; a payload naming `project_slug`/`increment_slug` is `choice-malformed`; `INITIAL_INCREMENT_SLUG` owns the increment; `_resolve_bootstrap_identity` fills identity from caller + harness and refuses when the caller named nothing. The refusal mirrors the installer's own precedence (authority before route), so the same fact keeps the same rule. Mutants 6/6. |
| **P3-1** | CT-1.4 names a test that does not exist under that name and whose V1-refusal half is not asserted; the live test is `..._on_a_v2_route`. | Row vs `tests/test_ai_native_plan_v2.py:474`. | **Closed 2026-11-21 (E589):** the row now names both live tests. The V1 half was never missing -- `test_v2_document_is_never_judged_by_v1_validators` asserts it -- it was just not cited, so a reader could not tell whether the control existed or the row was aspirational. |
| **P3-2** | Ledger E570 was recorded twice — the same entry, lightly re-worded, with the second copy the edited one. | `grep -c "### E570"` = 2. | **Closed 2026-11-20 (E581):** the first copy is removed, the edited copy kept. |
| **P3-3** | Ledger heading level was inconsistent (E565–E575 used `###`, E576–E580 used `##`). | `grep -c "^## E5[5-8]"` = 7 vs `"^### E5[5-8]"` = 25. | **Closed 2026-11-20 (E581):** E576–E581 normalised to `###`, matching the entry level every earlier entry uses. |
| **P3-4** | The R1/R6 audit names a rule the code does not use: `disposition-review-invalid` (audit) vs `disposition-reviewed-at-invalid` (code). | Note §4 vs `plan_admission.py`. | **Closed 2026-11-20 (E581):** the audit note now uses the code's name, so one rule has one spelling. |

| **P4-1** | **An un-granted request is admitted *and* minted.** The binding step is skipped entirely when the caller supplied no dispositions: `if snapshot.graph is not None and granted:` (`workflow_controller.py:3209`). The library rule is live and tested (`bind_dispositions` raises `disposition-undeclared`; `tests/test_ai_native_dispositions.py:183`), so the controller's guard is what makes a plan that *requests* a grant and never receives one pass admission and reach the seal. | `workflow_controller.py:3209`; `plan_admission.bind_dispositions` (`:171`); reproduced by probe (E602/E604). | **Open — S1.** Delete the guard so binding always runs; make `disposition-undeclared` non-repairable and add a retryable `disposition_required` row, so the model's only reachable move is "ask the caller", not "delete the claim". |
| **P4-2** | **The seal is blind to what it does not attest, and it has a second producer.** `mint_seal` records selectors and attested ids but no `contracts_total`/`uncovered`, so a seal over a graph with an uncovered contract is indistinguishable from a complete one once the graph is gone — measured: `attested=()`, `selectors=['CT-1.1']`, and `"CT-1.2"` absent from the record. `acceptance_defect.correct(...)` passes a caller-supplied graph into `mint_seal` (`acceptance_defect.py:246`), so "a future caller might pass a bad graph" is not hypothetical. | `acceptance_bundle.py:65`, `:271–300`; `acceptance_defect.py:246`. | **Closed 2026-11-22 (N1, `7b750f5`).** The mint refuses an uncovered contract (`seal-uncovered-contracts`, `acceptance_bundle.py:369`), the record carries `contracts_total` and re-checks `len(selectors)+len(attested)==contracts_total` on load (`:600`), `SCHEMA_VERSION` is 2, and the route now mints on the create path — so the former "second producer" passes through the same totality rule rather than around it. Tests: `tests/test_ai_native_acceptance_bundle.py::test_a_seal_is_refused_while_a_contract_has_no_evidence`, `tests/test_v2_seal_store_and_mint.py`. **Superseded detail:** the pre-fix description follows — Refuse to mint while any contract is `UNCOVERED` or has `owner is None`; record `contracts_total`/`attested`/`uncovered` with `len(selectors)+len(attested)==contracts_total`; `SCHEMA_VERSION` 1→2 costs nothing (no production seal exists and `load_seal` fails closed on an unknown version). |
| **P4-3** | **Repair cannot repair what admission refuses.** The repair allowlist (`_REPAIR_WRITABLE_SUFFIXES`, `workflow_controller.py:3044`) does not admit `acceptance/tests/`; every grammar refusal is folded into one code (`bootstrap-invalid-metadata`, `:3202`), so the repair prompt cannot say which rule failed; the budget is one attempt shared with replans (`DEFAULT_MAX_REPLANS=1`, `:157`). A planner told "invalid metadata" can only delete the claim or ask for a grant. | `workflow_controller.py:3044`, `:3081`, `:3202`; `_V2_CREATE_FAILURES` (`workflow_tool.py:834`). | **Closed 2026-11-22 (E607).** The scope now admits `roadmap.md`, the pair admission parses, `open-questions.md` and the `acceptance` subtree; the task text is built *from* that tuple (prose can no longer promise a scope the writer lacks) and names the rule code, bounded at the one place a code becomes text; both legal exits -- a test, or a declaration the caller grants -- are stated, and deleting the claim is named as what it is. Fixing this exposed **P4-7**, without which none of it would have worked. |
| **P4-4** | **Coder write confinement is topology-dependent.** `write_purpose = MUTATION if is_nested_coder else PROJECT` (`cli.py:2165`); only a `MUTATION` view is confined to `{"src","scripts"}` (`workspace.py:2844–2854`, `_MUTATION_ROOTS` `:226`); a `PROJECT` view falls through to ordinary rooted IO, where the only barrier is `protected_paths` — which carries the plan file and nothing else (`workspace.py:2194`, `:2814`) — while the coder holds unconfined `fs_write_file`/`fs_edit_file` (`profiles.py:123–137`). So "the coder cannot edit the tests it must pass" holds *because the V2 coder stage is nested*, not because the role is confined: a top-level managed coder could write `worklogs/<slug>/acceptance/tests/**`. Making the purpose unconditionally `MUTATION` is **not** the fix — the coder legitimately writes repository tests and docs outside those roots. | `cli.py:2165`; `workspace.py:226`, `:2194`, `:2814`, `:2844–2854`; `profiles.py:123–137`. | **Open — S3, urgent rather than defence-in-depth.** CT-3.3's `protected_paths` over every sealed semantic path is the correct mechanism precisely because it is topology-independent; its test must cover both coder topologies.  **Closed in S3 (2026-11-22):** `protected_paths` is now derived in the authority from the plan (`sealed_project_paths`), so both topologies refuse the sealed set; the oracle opens a `PROJECT` and a `MUTATION` view and requires the same denials from each. `write_purpose` was left alone — it decides what a view may write, not what it may not. |
| **P4-5** | **`KIND` is a required field whose only reader exempts.** `plan_v2.py:312` requires it; `:622` (`if item.kind != "HARD": continue`) is its only read in `src/fa`, and it exists to skip the evidence check. The canonical schema never mentions it, so the field is defined by the parser and documented nowhere. | `plan_v2.py:312`, `:622`; three tests pin the behaviour. | **Closed in policy by D-V2-10; code in S1.** Removing the field touches one required-field read, three tests and the prompt example. |
| **P4-7** | **The narrowed repair scope admitted no path at all.** `_REPAIR_WRITABLE_SUFFIXES` named *files* (`increments/…md`, `open-questions.md`) and the only matcher the limited writer had was `is_path_within_allowlist`, which is strictly-descendant: it requires at least one component *below* a prefix, so a prefix that is a file name admits nothing. Measured through `build_registry_for_role`: writing the increment a repair exists to fix returned `path_denied`. Every repair test bound the workspace port directly, so no test could see it — the double hid the defect (this is the "production double" failure the test skill names). | `profiles.py:31` (strict descendant), `_build_limited_write` and `_planner_target_allowed` (both gates). | **Closed 2026-11-22 (E607).** `is_path_in_write_scope` admits an exact entry *or* a subtree and is used by both gates when the dispatch carries a repair scope; the directory predicate is unchanged for every profile allowlist, and a regression mutant proves the two are not interchangeable. |
| **P4-8** | **The grant leaves no trace.** A declaration is validated, bound into the graph and graded (`attested`), and then it is gone: `dispositions` exists only in `WorkflowContext`, the tool's params and the CLI argument; the seal records the attested *contract ids* and nothing about **who** granted, **on what evidence**, **when**. Measured: `grep -rn dispositions src/fa` outside plan/controller/tool/cli → 0 hits, and `admission_schema` has no field for it. So the artifact says "CT-1.1 was attested" and a reader cannot tell an owner's twenty-minute review from a rubber stamp. | `acceptance_bundle.py:281`, `plan_admission.py:171`, `admission_schema.py`. | **Landed in S2** (same record, same schema bump, one migration instead of two): the seal carries `attestations` — contract id, invariant id, reason, route, artifact, owner, `reviewed_at`, scope digest — inside the digest, `load_seal` refuses a block whose ids are not exactly `attested`, and D-V2-12 adds the route that makes the artifact checkable. |
| **P4-6** | **`--dispositions` has no human ingress** (already rowed in SLICE1 as CT-1.5 scope): the field exists on the tool schema (`workflow_tool.py:245`) but the CLI parser has no flag (`cli.py:975–993`), so a legal V2 plan that needs a grant is unreachable from the human front while it is reachable from chat. | `cli.py:975–993`; `workflow_tool.py:245`. | **Closed 2026-11-22 (E607).** `--dispositions PATH_OR_JSON` on the parser, decoded and forwarded unmodified; validation stays in `parse_dispositions`, and an undecodable value refuses before any lifecycle. |
**Resolved 2026-11-22 (supersedes the paragraph below):** the seal now has a production caller — the create route mints and stores it before any coder is dispatched (`workflow_controller._seal_published_project`, N1, `7b750f5`). "An operator sees a verdict" still waits for a host run, but the gap the paragraph describes is closed. **Original record:** R2's seal half has no production caller yet — `mint_seal` is invoked only from
`acceptance_defect.py` and tests. "G3 landed for the seal" must not be read as "an operator sees a verdict"; that
waits for SLICE3's seal mint.

### Current custody audit continuation — E654–E656 (2026-11-23)

E654 hardens local seal-pointer parsing and binds the loaded seal to the pointer, including
predecessor validation on replay/supersession. E655 bounds shared closure traversal by
incremental bytes and 4096 entries before returning inventory or closure. Regression,
mutation and remaining limits are recorded in [ledger E654–E656](../ledger.md).
Neither change satisfies B1 authority custody: local `.fa` metadata and the writable coder
shell leave a systemic exposure. The first attempted interim guard was removed after an incorrect context lookup; E657 subsequently implements a tested pre-dispatch refusal. Do not treat V2 coder
execution as custody-safe or close STEP9A on these patches. Continue B1 with authority-private
seal and protected execution or the specified immutable fallback, then complete B2–B6;
independent STEP9B and W4 remain required.

### E657 — operator amendment and interim dispatch fence (2026-11-23)

The operator selected authority-private seal metadata plus revision-backed, genuinely read-only
mode-A projection (B); isolated immutable payload (C) is mandatory if B cannot be proved.
This **supersedes D-V2-6's shell drift-detection-only allowance**, including historical
detection-only wording in CT-3.3. It does not move W4 or require an early live deployment.
Local tests and Docker request-contract evidence are necessary but do not prove live-host
mount behavior; W4 remains mandatory. E657's temporary guard refuses V2 coder dispatch in
both modes until the authority-owned custody and projection are implemented and proven.
The existing host-workspace `.fa` store is not authority-private. Historical E656's guard
status is superseded by E657; the store and projection are not yet fixed. STEP9A remains open.

**E658 regression correction:** old bootstrap fixtures discarded the now-required authority
inventory. They now retain the actual pin/service inventory and substitute only local pytest;
205 related tests pass. This is not evidence of a live Docker cell or completed B1.

**E659/E660 preparation, not B1 closure:** the legacy seal-store's metadata reads are now
bounded and refuse final-component links/nonregular files; the foreign-nodeid regression
fixture was updated for nonce/call-phase reports. Six related modules report 373 passed;
see [ledger](../ledger.md) for mutants and limits. Workspace-local seal still lacks
private-authority ownership and safe ancestor binding. The guard is still active; B requires
the authority-backed seal lifecycle and revision-backed read-only projection/fallback.

**E661 internal authority seam, not B1 closure:** a candidate record can now be stored
under private workspace/project authority state only after OWNER, current revision,
settled-view, plan and full file-inventory checks. Replay and project isolation are
locally tested; supersession remains deliberately refused pending correction authorization.
See [ledger](../ledger.md) for tests, mutants and durability limits. Collection/semantic
provenance, loss-of-metadata recovery, integration and genuinely read-only mode A (or C)
remain open; the E657 dispatch fence must remain in place.

**E662 recovery hardening, still not B1 closure:** absent private pointer plus any
surviving seal record or unexpected `.fa` entry is now an ambiguous-history refusal, not
a remint. Full metadata loss cannot be detected by this check; integration and actual
read-only custody remain open. See [ledger](../ledger.md) for negative proof and scope.

**E663/E664 linked preparation, not STEP9A closure:** authority-local per-project
started markers now detect loss of a project seal directory while the workspace
binding survives; total binding rollback/loss remains unprovable. Classified sealed
assertion failures are now determinate in the existing controller gate, while skip,
error and mutation uncertainty remain blocking in both modes. See [ledger](../ledger.md)
for exact boundaries, negative proofs and regression banks. Guard E657 remains active;
full mode-A custody, managed mutation, end-to-end routing and host proof remain open.

**E665/E666 custody preparation:** the internal authority store now reparses the
revision's actual plan to reject foreign TEST/CT/selector/attestation scope and
reuses the canonical closure collector on revision bytes before writing. The
candidate's purported nodeids and grants are not independent provenance. See
[ledger](../ledger.md) for negative controls and limits; no service/controller C1,
mode-A proof or STEP9A closure follows, and guard E657 stays active.

### Q-V2-CUSTODY-RECOVERY-1 — authority state loss / rollback boundary (RESOLVED, 2026-11-23)

**Blocking STEP9A authority custody.** The later operator requirement forbids a silent
remint when prior seal history cannot be disproved; historical D-V2-5 audit E9 and its
pointer-absent deterministic-remint rule must not be treated as authorization for that
case. Existing E663 started marker survives loss of a project subdirectory only: it is
inside the same workspace binding/state root as the pointer. `WorkspaceAuthority.__enter__`
creates an absent catalog, `register_existing` assigns a new workspace/revision when no
binding is loaded, and E661–E666's internal `store_acceptance_seal` accepts a matching
candidate without external proof of an earlier seal. A local diagnostic with real authority
and a temporary filesystem sealed a project, deleted the entire protected state root, then
registered the unchanged canonical project and accepted a different seal under new workspace
and revision identities. This is an **internal seam diagnostic**, not an exposed wire operation
or a claim of live coder dispatch: E657 remains in force. A coherent older backup of the
entire authority state is a separate rollback case; a marker within that backup cannot prove
it is newest. No host rollback witness was run.

**Historical question and options (resolved below): which independent trust and recovery boundary is operationally
available?** (A) An independently protected durable workspace-identity/history registry,
with a rollback-resistant checkpoint where rollback is in scope; require it for existing-root
registration and fail closed on missing/mismatched proof. (B) Fail closed whenever history
is unavailable, and provide a separately authorized recovery/rebootstrap process that preserves
or explicitly accounts for old evidence; a normal missing marker must never authorize mint.
This still needs a way to distinguish a clean new installation from a coherent old-state
rollback if the latter is in scope. (C) Another owner-specified independent backup/registry
and recovery protocol with equivalent no-silent-remint and history guarantees. The engineering
recommendation is **A plus B's fail-closed recovery**, but the owner must identify the trusted
host/backup boundary and whether coherent rollback must be detected; inventing an external
service or declaring an untrusted reset a fresh project would be a policy choice.

Until implementation is proven: do not wire this internal store as seal authority, do not lift E657, and do
not claim B1/STEP9A or recovery closure. A sound authorized fresh-install proof and recovery
intent/replay design remain required whichever option is chosen. The immutable-payload fallback
C is not by itself a history/rollback authority and cannot resolve this question merely by
copying bytes. W4 must test the chosen boundary, failure and evidence retention; no early host
run is implied. Q-V2-LEDGER-1 policy was subsequently resolved by E686; implementation and
host proof remain open.

**E668 risk calibration:** this is an exceptional state-loss/restore problem, not an
observed normal-run failure. The repository's current backup script omits the spec's
supervisor state path and session workspaces, although actual host backup coverage is
unknown. Session SQLite/blackboard are session-scoped and event bus is transient; none is
currently the independent workspace/seal history authority. Before choosing a new external
registry, evaluate fail-closed fresh-vs-existing lifecycle and consistent backup/restore.
Full coherent rollback detection is a separate stronger boundary. See [ledger](../ledger.md)
for source audit; this assessment preceded the resolution below.


**Q-V2-CUSTODY-RECOVERY-1 resolution, amended E683 (operator, 2026-11-23):** a
missing or unprovable prior seal blocks ordinary agent mint, but does not permanently
block a project. A trusted, explicit owner/workflow recovery may revalidate the current
plan, full closure, collection and pre-code gates and establish a new seal/evidence
lineage; previous verification and mutation results must never be credited to it. It does
not claim the lost prior bytes were restored. Coordinated project/session/supervisor backup
is appropriate when the exact old history must be restored; W4 must verify the chosen
recovery and backup/restore boundary. A deliberately deleted project ends its incarnation
and releases its slug for a new incarnation, whose evidence cannot be confused with the
old one; authorized cleanup may remove stale private artifacts. A manual out-of-band
deletion requires explicit authority reconciliation, not a filesystem watcher or silent
adoption. The authority must distinguish these trusted lifecycle decisions from coder
edits or arbitrary missing files, and recover durable operations idempotently. No separate
external anti-rollback registry is mandated; detecting a coherent rollback of all state
remains outside MVP. This amends E669's blanket no-remint/fresh-versus-existing policy:
no **silent** remint remains mandatory, but explicitly authorized reset is allowed.
It is a decision, not implemented or host proof; E657 remains active. Q-V2-LEDGER-1 was
subsequently resolved in policy by E686.

**E671 partial custody hardening:** the authority's BOOTSTRAP origin now records a durable
first-mint transition; losing both the separate marker and project seal directory cannot
make the surviving origin authorize a fresh mint. Interrupted or contradictory state fails
closed. This does not detect a coherent rollback of that origin, implement recovery/backup,
prove mode A, or authorize removal of E657. STEP9A remains open; see ledger E670–E671.

**E672 mount-topology diagnostic:** a read-only bind at `acceptance` alone is not sufficient:
a real namespace experiment moved its writable project ancestor and substituted the visible
path. A top-level read-only `worklogs` bind under a separately mounted workspace resisted the
same operations locally while permitting `src` writes. This is a candidate to investigate,
not a production mount design or C1/host proof; full alias/race/closure and verifier binding
remain open. Reproducible diagnostic and precise limitations: ledger E672 and
`tests/test_acceptance_mount_topology.py`. E657 remains active.

**E673 authority read component:** private seal read re-proves original and current revision,
plan semantics and full subtree manifest, with exact path/SHA bound to the origin. It allows
code-only revision advancement but refuses closure changes including modes and empty dirs.
It is internal and not a trusted collection receipt or production caller; the current
single-plan-per-project pointer and disabled supersession do **not** satisfy multi-increment
or TEST-DEFECT lifecycle. E657 remains; see ledger E673 for tests and remaining obligations.


### STEP9A final full gate — operator requirement (2026-11-23; NOT RUN)

Before STEP9A closure, run `source .venv/bin/activate && just check` using the
`./scripts/arena-env-build.sh` environment; report each constituent gate, including
repository-wide mypy and pyrefly. Independently mutation-test every complete production
module implemented or changed for STEP9A, not only the configured `[tool.mutmut]` scope,
a selected line subset or the small producer/EDGE samples already in the ledger. Freeze the
final source-grounded module/test inventory at the candidate SHA and extend it as work lands.
Initial minimum inventory: `src/fa/execution/{workspace,publication,profiles,docker,backend,
composition,primitives,protocol,service,client,view_io}.py`; `src/fa/inner_loop/{plan_v2,
plan_admission,acceptance_bundle,acceptance_closure,acceptance_collection,acceptance_seal_store,
acceptance_defect,kill_attribution,slice_verification,verification_attempt,junit_nodeid_plugin,
junit_properties,workflow_controller,coder_loop}.py`; and `src/fa/cli.py` where STEP9A
integration changes it. Include further STEP9A production files introduced or changed by
implementation; omit no initial file without recorded source-grounded correction and owner
review. Shard the full files through `scripts/run_slice_mutmut.py --source <file> --test
<relevant-test> ...`, with `--also-copy` dependencies as needed; verify each test selection
actually exercises that module, baseline passes, complete results reconcile, and producer +
caller/EDGE mutants have meaningful oracles. Preserve full reports externally or in ignored
artifacts; log commands, SHA, tool versions, denominators and counts per module. Triage all
survivors under `/mutation-clearing`, repair meaningful gaps, record evidence for equivalents;
No missing, timeout, infrastructure-failed, unreviewed or skipped shard counts as
PASS. Type-invalid mutants are reported and reviewed as invalid rather than credited as killed;
their presence alone is not a functional failure, but cannot hide incomplete execution. Targeted mutation checks remain required after each implementation slice and do not
replace this final sweep. This STEP9A gate supersedes E544's best-effort language **only for
STEP9A**; Q139 and unrelated broad-baseline dispositions are unchanged. W4 actual-host
custody, recovery and ledger-append E2E remain separate.

**E675:** origin JSON size is checked before the first-mint replace and the read bound now
covers the declared path schema; a real escaped filename reproduced the old durability failure.
Interim full mypy/pyrefly are red (89/65 errors before one test-type fix), not final-gate
results. See ledger E675. All STEP9A integration, multi-plan and custody obligations remain open.

**E676:** experimental authority-private per-plan origin registry and independent stores
remove the internal one-plan-per-project restriction, subject to bounded registry capacity,
no automatic migration and no supersession. Component evidence and TEST-EDITS are in ledger
E676; production custody integration, C1, correction, projection and final gate remain open.

**E677:** V2 OWNER-only private seal read transport is available through the real client,
service and authority, with bounded semantic client validation; see ledger E677 for
negative proof, compatibility and limitations. No production controller consumes it yet;
authority mint transport, trusted collection, mode-A and E657 guard remain open.

**E678:** authority-private first-seal storage now has an OWNER-only, journalled V2
transport with exact request replay and crash uncertainty, plus V2 journalled response
handling. See ledger E678 for C3/negative/mutation evidence and limits. Controller use,
trusted collection, correction/reseal, mode A and dispatch readiness remain open.

**E679/E680 — next custody dependency, not a closure:** the real staged CREATE_NEW_PROJECT
publishes a REVISION rather than an INSTALL_PROJECT/BOOTSTRAP, so it produces no authority
origin; its current success is backed only by the legacy workspace-local store. A real
managed-stage/UDS test confirms private store refuses without effect. ManagedExecution now
retains uncertain private-seal request identity for same-ID reconciliation and withholds
close/handoff; current direct `managed.client` paths bypass this composition fence and
must be audited before wiring the controller. See ledger for exact tests and limits.

**Next engineering increment (amended by E683):** implement explicit authority-trusted
project-incarnation lifecycle, including staged REVISION creation, owner-requested deletion
and re-creation, out-of-band deletion reconciliation, and recovery of an existing project
whose seal was lost. A monotonic permanent slug history is **not** a selected requirement.
Specify the actual privileged caller/authorization boundary before exposing reset: current
OWNER is a run capability and must not automatically become coder authority to reset its
own acceptance. Bind operation identity, project incarnation and fresh seal lineage to
workspace and revision; wire durable intent/recovery, replay, stale/concurrent fencing and
cleanup. Revalidating current documents is not proof of old bytes. Even unchanged bundle
inputs produce the same deterministic seal digest today (`test_the_same_inputs_always_mint_the_same_bytes`):
evidence must additionally bind an authority-issued new lineage, or the new seal must
incorporate that lineage, so pre-reset evidence cannot regain credit after reset. Decide
format/migration and public command after the source and threat-boundary audit; no
caller-supplied lineage may self-authorize reset. Prove real staged CREATE_NEW→publication→
private seal, explicit reset and delete/recreate, lost-reply/restart, old-evidence refusal,
coder denial and producer/EDGE before replacing E679's diagnostic or wiring controller.
Preserve E657, independent collection, mode A/fallback and the E674 full gate.

**E681:** known verify/acquisition/child READ pin edges now route through the managed seal
fence, with child binding constrained to the same workspace/session and direct parent.
See ledger for real-service producer test, three caller-edge tests and five killed mutants.
This is not a universal or concurrency-safe custody proof: audit remaining direct client
calls, candidate-publication interactions and controller-loss recovery before integration.

### E683 lifecycle implementation matrix (open; supersedes E682 permanent-history proposal)

| Case | Required effect / evidence | Negative and recovery controls |
|---|---|---|
| CREATE_NEW authoring | Real managed authoring REVISION becomes an authority-identified new project incarnation; validated current plan and closure can enter private seal flow. | No caller-selected reset proof, no legacy `SealStore` authority; reject collision and stale revision, preserve authoring repair. |
| Trusted project deletion | Close incarnation and remove/archive its associated authority data according to the selected cleanup; same slug can be created again as a different incarnation. | No coder-supplied file deletion silently authorizes reset. Preserve other projects/plans, symlink-safe cleanup, crash/replay with no half-authorized new incarnation. |
| Manual deletion | Detect drift or explicit operator reconciliation and let trusted lifecycle close the incarnation; no watcher dependency. | Never interpret a transient absence or unchecked host path as an authorized delete; no stale writer/view or unproved reconciliation. |
| Existing project, lost seal | Explicit trusted recovery revalidates current plan and complete closure, independent collection and applicable pre-code gates, then establishes new lineage. | Missing/corrupt origin/pointer/record alone cannot authorize reset; unchanged bytes and unchanged revision must still invalidate old results; coder cannot grant itself reset. |
| Lost reply/crash | Reconcile exact operation and durable state; preserve uncertainty and prevent concurrent work until settled. | No duplicate incarnation, phantom success, partial cleanup or id reuse with different inputs; test before and after each irreversible point and across restart/quarantine. |
| Restore | Coordinated restore when exact history is required; W4 validates deployed boundary. | Do not claim coherent total rollback detection, old-byte recovery from a reset, or host proof from Arena-local tests. |

The run OWNER proof (`WorkspaceAuthority._owner_only`) binds a capability, active namespace
and UID/GID principal, but has no planner/coder/owner role field; it is insufficient by
itself as proof that an LLM coder may authorize reset. The trusted management entry point,
its authorization/provenance, safe durable lifecycle and evidence epoch are **not yet
implemented**. Fixed SHA-only `AcceptanceBundle` and `VerificationIdentity` currently have
no incarnation identity: identical plan/revision/closure inputs mint identical seal bytes,
so a new seal must have an authority-controlled distinct lineage or all evidence consumers
must bind a separate authority-proved lineage. Component mocks cannot prove this lifecycle.

**E685:** exact canonical private seal read is enforced: rehashed unknown fields,
duplicate keys/identity, and noncanonical records can no longer turn one pointer digest
into a different client-visible digest; stale in-memory digest cannot create a store
record or pointer. Real service/UDS, no-effect tests and four killed mutants are recorded
in ledger. This is identity-integrity preparation only, not issuance of E683's distinct
lineage or authorization of reset; staged origin and E657 remain open.


### E686 — narrow protected boundary, usable agent workspace (operator policy; implementation open)

**Decided:** coder/planner working `ledger.md`, `notes/` and `e2e/` are writable via file tools and
shell without reseal. E2E verdict requires recorded execution and an assigned reviewer, not editable
Markdown alone. Plan/admission and planner-authored acceptance oracle remain protected; coder sees
the same closure read-only and `TEST-DEFECT` uses a new revision/seal. A seal proves identity, not
test quality. A free note may supply context; operator accepts the risk that a plan can reference
mutable notes, but mutable notes cannot silently become an authoritative PASS or excuse closure
integrity. This does not relax E657, E683, E674, or pre-code/mutation/observe-enforce requirements.

**Source gap:** `sealed_project_paths` protects the complete project for rooted file IO, while the
WRITE container mounts the workspace writable and publication validates the plan path and acceptance
subtree; no uniform early protection exists. `MUTATION` is separately confined to `src/`/`scripts/`
(Q141=C), so direct and nested coder cannot both satisfy the requested write behavior as-is. No
production behavior or Docker host proof is claimed. The E672 kernel experiment proves an acceptance-only
nested read-only bind is bypassable by ancestor rename; it does not prove a finer safe topology.

**Q-V2-WRITE-SCOPE-1 — RESOLVED = A (operator, 2026-11-23):** amend Q141=C for nested
coder to permit ordinary `ledger.md`, `notes/` and `e2e/` writes **only under its current
project**, in addition to existing source roots. This is not generic write access to other
project files, other slugs or authority state. The single-target mutation execution path
retains its own confinement; do not implicitly widen its scope merely because it shares a
`MUTATION` name. Legacy/non-project references must not manufacture a current slug. The
policy is resolved; role/capability binding, implementation and proof are open. E527's
historical local closure is not rewritten as proof of the amended behavior.

**STEP9A tasks (all open):**

1. Define one authority-derived policy for protected plan/admission/acceptance paths and writable
   working paths, roles and purposes, including the Q-V2-WRITE-SCOPE-1=A amendment to Q141=C; use it consistently across tools,
   cell projection and publication. Preserve independent write scopes and authority-private state.
2. Prototype a selective projection: read-only protected ancestor skeleton, writable binds only for
   designated working locations and editable source, while excluding alternate writable aliases;
   treat regular-file ledger replacement/append, missing/new files, writable parent directory metadata,
   nested mounts, safe stop/snapshot and publication as explicit feasibility questions. Do not claim
   it works based on mount declarations. If revision strategy cannot be proven, use the mandatory
   isolated immutable-payload fallback with equivalent usability and custody, not a hash-only sidecar.
3. Prove before dispatch that shell and file tools agree on allowed working writes and protected-path
   denial. Defend ancestor rename/replacement, symlink/hardlink aliases, mount/remount, transient ABA,
   additions/deletions, and stale/incorrect projection. Retain end-of-stage check as defense-in-depth,
   not the first point a normal protected write is detected. Audit semantic roadmap binding separately.
4. Minimize late rejection and preserve user work: verify known configuration and projection before
   coder, provide actionable bounded reasons, and design/test safe recovery of unrelated candidate
   edits on rejection or uncertain publication without publishing unvalidated changes or bypassing
   reconciliation. Do not promise universal recovery across crash or state loss without proof.
5. C1/C3 through real workflow/composition and production authority: file tool and shell both edit
   and append ledger, notes, E2E; committed bytes survive publish and a fresh pin while seal/plan
   identity remains valid; protected write/unlink/rename/ancestor substitution fails immediately on
   both surfaces; an attempted protected edit plus valid code/notes edits cannot silently publish
   protected changes and has the specified no-loss/recovery behavior. Include conflict, crash/replay,
   concurrent stages, missing paths, nested/direct scope and plan/evidence drift. Kill producer and
   caller EDGE guards and relevant bypass mutants. No local test counts as host proof.
6. Plan W4 live host E2E: real agent file-tool and shell appends to project ledger after admission,
   edit notes/E2E, publish and fresh-read authoritative revision, seal identity unchanged; negative
   oracle attempts protected edits through both paths, checks retained work and correct refusal; forged
   PASS in editable E2E/ledger cannot satisfy the host gate. Record actual host run, SHA/image/profile,
   evidence and assigned reviewer; NOT RUN until performed. Existing run-scoped verification store is
   a reuse candidate, not an unproved independent authority or a requirement for a new journal.

Mutable-note references are an accepted semantic ambiguity, not a proof that mutable test helpers
are safe: transitive execution dependencies and exact oracle identity remain unresolved technical
proof obligations. E686 is policy and work specification only, not closure.


### E687 — source audit: selective custody and nested working writes (implementation open)

**Decision reconciliation:** E686's working ledger/notes/e2e, file-tool/shell parity, early
prevention, safe recovery, mutable-notes semantic risk, host verdict requiring a recorded run
and reviewer, planner-owned oracle + TEST-DEFECT, and E683 deletion/reset and fresh lineage
remain authoritative. Q-V2-WRITE-SCOPE-1=A amends only nested-coder working paths, not
the security of the plan, oracle, private evidence, other projects or mutation oracle. The
plan continues to require pre-code sensitivity, exact mutation attribution, both-mode integrity
blocking, same pinned verifier closure, mode-A visibility, fallback, E674 and W4. These are
design obligations, not a claim that current implementation achieves them.

**Current data path (source audit, not a new execution test):**

1. `cli._drive_stage_with_managed_workspace` chooses `PROJECT` for direct coder and
   `MUTATION` when `parent_run_id` is set, obtains an authority view through
   `_open_stage_view`, and constructs `ClientWorkspacePort`, `ManagedBashExecutor` and
   `ManagedProjectToolExecutor` for the same grant. `_stage_custody_admitted` stops V2
   before dispatch under E657. A caller-supplied project slug must not be treated as proof.
2. `WorkspaceAuthority.create_view/_materialize_input` copies the pinned revision to private
   view `source`; `_project_io` uses that descriptor and `_purpose_write_policy` rejects
   MUTATION paths outside top-level src/scripts. `RootedViewIO` receives
   `sealed_project_paths(plan_ref)` which currently protects the **entire** project, and
   stages file writes in authority-private `pending` with `link` or `os.replace`. Thus both
   the purpose gate and protected set must change for working writes; keep path-component
   checks, nofollow/identity checks and existing negative permissions.
3. `admit/_ensure_inputs` on a WRITE view supplies the same view `source` for cell input.
   `DockerCells` calls `ExecutionProfile.create_spec`, currently a single writable bind at
   `/workspace`; the file-tool guard alone does not restrict shell. Any new split projection
   must be authority-derived, checked before dispatch and prevent an accessible writable alias
   of protected bytes. The cell and file tools must see the same working content.
4. `prepare_seal` snapshots `view/source` after stop/terminal receipt; `publication.seal_view`
   compares the manifest with base entries, plan boundary, acceptance subtree and MUTATION
   root restriction. PUBLISH materializes from the frozen view source. A bind layered only
   in the Docker namespace may be absent from authority's source snapshot: accepting in-cell
   edits without proving their path to the authority snapshot would silently lose them.
   Conversely an RO mount may hide writable underlying bytes; shell/file tool divergence and
   verifier mismatch must be tested. Mount lifetime, stage-stop and restart reconciliation
   are part of the design, not details deferred after enabling coder.
5. `_read_sealed_manifest` revalidates on publish/replay without passing `purpose`; the initial
   `seal_view` and seal replay do pass it. No exploit is claimed from this source observation,
   since the manifest is authority-private; the amended end-to-end audit must explicitly prove
   scope and plan binding across seal, publish/replay and recovery instead of assuming the
   purpose check is repeated there.
6. `_ManagedStageLease.finish` suspends ports then publishes accepted work; on error it marks
   the lease broken. `abort` rejects an active view best-effort. Existing code does not establish
   a user-facing selective salvage contract for unrelated edits, nor durable reconciliation of
   every stage publication uncertainty. Design safe recovery against exact operation/base and
   no unvalidated commit; never treat an uncertain response as a definite no-effect.
7. Authority seal validation checks plan `PlanRef`, acceptance manifest and closure;
   `AcceptanceBundle.plan_sha256` is one plan hash and the current verification/controller
   uses workspace-local `SealStore`. This does not prove roadmap binding, independent
   collection, transitive oracle closure or authority-private controller integration. Those
   need their own explicit proof before E657 can be lifted.

**Engineering route to prototype, not a chosen/proven mount implementation:** use one
authority-owned policy derived from admitted plan/current project and trusted purpose; wire
it into (a) file IO, (b) container projection, (c) post-stop manifest and (d) replay/recovery.
The path from CLI to authority must carry or derive any needed identity without trusting a
model-chosen prefix. Do not broaden all `MUTATION` grants or verifier mutation roots to
obtain the nested-coder exception. Consider a protected ancestor skeleton with narrowly
writable working directories and separate ledger handling, but test feasibility first:
a file bind at ledger can defeat temp-file+rename, while a writable project parent can
replace protected path components. A composite projection requires a descriptor-backed,
crash-safe mapping/merge or equivalent so all edits enter exactly the snapshot authority
publishes; no second untrusted source of truth. Test cross-device staging, hardlinks,
project renames, missing working directories, future files, atomic replace and both tool
views. If the strategy cannot be proven, E657 requires the isolated immutable-payload
fallback; that fallback still needs a usable, ancestor-safe projection.

**Probability:** E672 proves the attack is possible in the tested kernel namespace, not
that it is frequent in normal runs or possible in the not-yet-designed Docker topology.
There is no measured incident rate. Ordinary append/edit usually does not rename project
ancestors; recursive cleanup, refactoring, repair scripts or an intentional shell workaround
can. A single bypass invalidates the custody claim, so defend structurally without a prompt
warning or a claim that the event happens often.

Next local slices: prototype topology with the E672 test harness first (including real
file-tool atomic-replace semantics and snapshot continuity), then implement the production
composition with C1/C3 and producer/EDGE kills, followed by E674 and the separate W4 host
witness. Neither source review nor a kernel-only diagnostic can close STEP9A.

### E688 — selective file-bind prototype rejects itself (local diagnostic)

Extended `tests/test_acceptance_mount_topology.py` using the existing kernel namespace seam:
read-only `worklogs` ancestor; writable binds for `notes/`, `e2e/`, and the existing
`ledger.md` file. A capability-free child successfully appends ledger and performs an
atomic rename inside notes; accepted file write and project ancestor rename are denied.
While the child holds its mount, a parent **outside** the child namespace reads and replaces
ledger through the real `RootedViewIO`, with its expected digest and authority staging.
That writer returns the new content; the child subsequently reads that content but its
next ledger append returns `EROFS`. A temporary file in the project root is also refused;
replacing ledger using a file from the notes mount returns `EXDEV`. Parent reads confirm
notes/e2e content and ledger replacement. This exact candidate therefore fails working-write
parity/usability after an ordinary file-tool edit and MUST NOT be promoted to production.
No explanation beyond the observed behavior is required or asserted; filesystem/kernel and
mount topology matter. An earlier attempt performed replacement inside the same namespace
and hit `EBUSY`, which did not model authority's separate namespace; the test was corrected.

This is a C3 kernel+actual rooted-writer diagnostic, **not** full authority/UDS, Docker,
production projection, atomic publication, ABA, hostile-alias or W4 proof. Three diagnostic
mutants (omit RO remount, omit ledger bind, change rooted write) killed; no production
producer/EDGE claim. Combined topology/view-IO/purposes/views/publication bank 278 passed;
scoped Ruff/format and `MYPYPATH=src` mypy pass, environment and diff check pass.
TEST-EDITS: `tests/test_acceptance_mount_topology.py` — extend the existing diagnostic without
removing the two original assertions. Continue investigating a topology/merge that supports
atomic shell edits and durable authority snapshots; E657 remains active, E674 and W4 open.

### E689 — anchored writable project diagnostic: continuity versus scope

A second E672-based C3 experiment binds `worklogs` read-only, binds the current project
writable as a mountpoint, then binds its `acceptance`, `increments` and `roadmap.md`
read-only. In this specific capability-free child namespace, direct accepted/plan/roadmap
writes fail EROFS; renaming the project fails EROFS, `worklogs`/protected mountpoints fail
EBUSY, and hardlinking a protected test into the writable project fails EXDEV. The real
`RootedViewIO` outside the namespace atomically replaces ledger while the child is paused;
the child reads the new content, atomically replaces ledger in the writable project and
appends afterward. Parent source reads show the final bytes and notes/e2e writes. Unlike
E688, the tested ledger sequence works.

**Counterexample to Q-V2-WRITE-SCOPE-1=A:** the same child can create `other.md` and
rewrite existing `open-questions.md` under the project; both changed bytes appear in the
source the authority would later inspect. Thus this is not a complete nested-coder
projection: permitted shell surface exceeds ledger/notes/e2e. The current publication
MUTATION check would refuse non-source changes at seal, not prevent them early, and it has
not yet been updated for the selected exception. Do not deploy this scheme alone or claim
it enforces plan or custody generally. The diagnostic has an external host alias and is not
Docker, authority/service publication, ABA, malicious alias, recovery, or W4 proof. First
expected project-rename errno was corrected from EBUSY to observed EROFS.

TEST-EDITS: `tests/test_acceptance_mount_topology.py` adds this candidate to the existing
namespace harness without removing prior cases. Four diagnostic mutants killed/restored:
omit project bind, acceptance bind, increment bind, or change real rooted ledger write.
No production producer/EDGE claim. Related topology/view-IO/purposes/views/publication bank
**279 passed**, scoped Ruff/format and `MYPYPATH=src` mypy pass. Next determine an
architecture that enforces the complete current-project working-path allowlist for shell
*before* user work is lost while retaining both atomic ledger editing and source continuity;
no new broad project permission is authorized. E657/E674/W4 remain open.

### E690 — Landlock path-rights probe (local diagnostic, not selected architecture)

`tests/test_acceptance_mount_topology.py` now runs two real Landlock ABI-2 rulesets in
capability-free subprocesses on this Linux host (x86_64, kernel 6.1.158+). The narrow
ruleset gives the project directory MAKE_REG/REMOVE_FILE/REFER, grants WRITE_FILE only
to the existing ledger inode and grants the notes directory the handled rights. Direct
ledger append succeeds, direct other-file write and ordinary sibling-temp write return
EACCES; importantly the failed temp write leaves an empty file. A temp prepared in notes
can nevertheless be renamed over *either* ledger or another existing project file: parent
reads confirm the other file is actually overwritten. After the ledger replacement, a
second append returns EACCES. The wide ruleset grants WRITE_FILE to the project directory;
ordinary temp/write and the second append succeed, but direct other-file write and the same
rename-over-other also succeed. The tests assert errno and actual external file contents.

These outcomes reject **these two** rulesets as complete implementations of E686/Q-V2-
WRITE-SCOPE-1=A; they do not prove every combination of Landlock, mounts, filesystem and
supervisor mediation impossible. Landlock has its own ABI, inherited-FD and supported-right
constraints; Docker seccomp/host preflight and lifecycle integration have not been proved.
`/dev/fuse` exists and can be opened here, but that does not prove a FUSE filesystem is
installed, mountable, safe, available on the deployment host, or an accepted new dependency.
No FUSE implementation or policy change is selected by this audit. Further exploration
must preserve early denial, atomic working edits and authority snapshot identity, and should
compare realistic deployment requirements before selecting any new production dependency.

C3 syscall/component diagnostic only; not authority/UDS, C1, Docker or host proof. Three
manual diagnostic mutants killed/restored: remove ledger file grant, project MAKE_REG, or
project REFER. No production producer/EDGE claim. Targeted five-module bank 281 passed,
scoped Ruff/format and `MYPYPATH=src` mypy pass; environment and diff check pass. On an
unsupported ABI/architecture or absent `setpriv`, these tests explicitly skip and must not
count as proof for E674 or W4. TEST-EDITS: extend `tests/test_acceptance_mount_topology.py`;
existing assertions retained. E657 remains active; STEP9A and W4 remain open.

### E691 — external research: candidate name-based MAC, not a selected dependency

**Research question:** with existing `/workspace/worklogs/<slug>/ledger.md` location, allow
shell and file-tool atomic ledger edits plus notes/e2e writes, deny nested-coder writes to
other project paths before publication, preserve the pinned plan/closure and authoritative
snapshot, resist rename/alias/ABA, and avoid wasted agent turns. Searched for Linux
name-based rename/create controls, LSM/container integration, FUSE per-operation policy,
seccomp pointer/TOCTOU and fanotify permission events; compared results to E688–E690.

**Most promising next experiment: AppArmor plus existing protected mounts.** Unlike
Landlock's hierarchy-FD allow rules, AppArmor's file rules are path-pattern based;
its manual states directory write permission is not required for creation/rename of
children, but applicable file-name permissions are. Docker can attach an already-loaded
custom AppArmor profile per container. Sources: [apparmor.d(5)](https://manpages.debian.org/bullseye/apparmor/apparmor.d.5.en.html),
[AppArmor policy discussion](https://en.opensuse.org/SDB:AppArmor_geeks),
[Docker AppArmor guide](https://docs.docker.com/engine/security/apparmor/).
Hypothesis, not proven: an enforce-mode per-view policy bound by trusted authority to the
current admitted slug permits the exact ledger and a narrowly designed temporary-write
strategy, `notes/**`, `e2e/**`, approved `src/scripts`, and denies other project paths;
mount restrictions protect plan/acceptance as independent defense. Correct source *and*
destination rules, directory ancestors and aliases matter. Broad denial of a parent path
may override permits; do not assume an example profile is correct. The allowed temporary
file names, visibility, cleanup, crash and concurrent collisions must be explicitly tested
against the approved scope, not treated as free extra project writes or selected silently.
A path-only allowlist must handle directory rename, symlinks, hardlinks, open FDs, procfd,
`renameat2` flags, exchange, unlink/recreate, path replacement and child exec/profile
transitions; it cannot replace custody, complete closure or E683 lineage checks.

**Host feasibility is not proved:** Arena reports no `/sys/module/apparmor/parameters/enabled`
and neither `apparmor_parser` nor `aa-exec` was found. Current `ExecutionProfile.create_spec`
renders seccomp and `no-new-privileges` but no explicit AppArmor profile; current authority
has no checked profile provisioning/identity/lifecycle. Docker documentation describes
loading profiles and `security-opt`; whether the target host can load/verify immutable
per-view policy, recover, safely reuse or delete it, and bind actual enforcement to a view
is unmeasured. Fail closed if enforcement identity/mode cannot be proved; do not silently
fall back to unconfined or `docker-default`. AppArmor support is a **candidate**, not a
new mandatory deployment prerequisite. Host profiling is a planned W4/host experiment,
not permission for early deploy or declaration of W4 PASS.

**Alternatives and limitations:**
- FUSE can implement mediated `create`, `rename`, `link`, and other filesystem operations
  ([Linux FUSE documentation](https://docs.kernel.org/filesystems/fuse/fuse.html),
  [libfuse passthrough reference](https://github.com/libfuse/libfuse/blob/master/example/passthrough.c)).
  It would introduce a new privileged/trusted filesystem daemon and operational/crash/cache
  surface: prove descriptor-rooted backing operations, complete syscall coverage, atomic
  rename, direct-source bypass exclusion, `allow_other`/permission behavior and continuity
  between actual cell view, file tools and snapshot before treating it as custody. Kernel
  FUSE docs note `default_permissions` and mount-owner restrictions; merely opening
  `/dev/fuse` here proves none of that. FUSE is a research fallback, not selected.
- `seccomp` filters alone cannot inspect pointed-to path strings
  ([kernel seccomp documentation](https://docs.kernel.org/userspace-api/seccomp_filter.html));
  the [seccomp user-notification manual](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html)
  explicitly warns against using CONTINUE with mutable pointer arguments as a security policy.
  Do not substitute a userspace string-check/CONTINUE interceptor for the boundary.
- `fanotify` has notification events and a separate set of permission events; rename
  notification is not evidence of a synchronous rename permission decision
  ([fanotify(7)](https://man7.org/linux/man-pages/man7/fanotify.7.html)). It can aid audit,
  not by itself prove rename prevention. Landlock remains a potential supplementary layer,
  but E690 is a counterexample to two naive policies, not a general impossibility theorem.
- A layout change placing ledger under its own writable directory may simplify OS isolation,
  but the current canonical artifact and user workflow name `ledger.md` at the project root.
  Do not silently relocate it, use an unverified symlink, or weaken Q-V2-WRITE-SCOPE-1=A.

**Planned discriminating experiment, before any production change:** on an approved or
representative disposable AppArmor-enabled host, compile and load an enforce profile with a
fresh project/slug and exact expected profile identity; run an unprivileged Docker cell with
current mount semantics. Simultaneously assert `(1)` shell appends and atomic ledger edits,
real `RootedViewIO` write followed by shell edit and fresh authority snapshot, `(2)` writes
and rename to a different project file and other project denied before effect, `(3)` protected
plan/acceptance and ancestors resist write, rename/exchange, aliases, hardlink, symlink,
transient ABA, subprocess inheritance and in-flight profile replacement, `(4)` no
uncontrolled temp leakage, and `(5)` failure to load/attach/enforce prevents dispatch with a
structured error, no unconfined fallback. Include concurrent views/slugs, startup cleanup,
crash/replay and mutation producer/EDGE tests at real composition. Acceptance requires actual
`STOP_VIEW→SEAL→PUBLISH` and fresh pin, not a filesystem-only probe. Preserve unrelated
candidate work safely on any late refusal; measure performance and agent-visible denials.
No host execution or PASS is claimed. Keep E657 and mandatory isolated immutable-payload
fallback until the full selected strategy is proven. E674 full checks/mutation and W4 remain.

### E692 — local FUSE feasibility and open-descriptor diagnostic

The primary E691 AppArmor experiment is blocked on this host: the active LSM list is
`capability,landlock,selinux`, with no AppArmor tools, and no Docker or Podman executable.
No inference about the deployment host follows. An unprivileged upstream libfuse 3.14.0
passthrough example did mount locally. Full reproducible procedure, source hashes, code,
results and caveats: [E692 diagnostic](../e2e/I03/fuse-passthrough-diagnostic-e692.md).

With `RootedViewIO` targeting backing storage and the FUSE process accessing the mirror,
ordinary fresh-path appends and atomic rename after an authority-side replacement worked.
However, this unmodified example has **no confinement**: other-file writes and direct
backing access succeed. Separately, an already-open FUSE descriptor accepted a write after
external atomic replacement, while fresh FUSE and backing reads saw only the new inode's
contents. Old-descriptor read also returned old bytes; do not infer exact cache or old-inode
contents from this. Thus fresh-path continuity alone misses a potentially lost successful
write. Future candidates must specify and verify concurrent open FD behavior, agent-visible
failure or safe recovery, and snapshot consistency; cannot silently equate a successful
write on a stale FD with publication. A direct backing-path control reproduced the successful stale write absent from the new
pathname, with old-FD read showing the append; this is not a FUSE-specific finding. Test
any selected design against its actual concurrency and safe recovery contract.

This is neither a FUSE security-policy experiment nor Docker/host C3 or C1 evidence.
No producer or EDGE, production change, dependency decision, or E657/W4 closure is claimed.

### E693 — directory-bound ledger layout candidate (local kernel diagnostic)

The user is willing to consider a small `worklogs/<slug>` layout change; this is an
invitation to investigate, not approval of a specific migration or broader write scope.
A new diagnostic variant in `tests/test_acceptance_mount_topology.py` puts the ledger at
`worklogs/demo/journal/ledger.md`, makes `worklogs` a read-only bind, and bind-mounts
`journal`, `notes` and `e2e` directories writable from the same backing source. A
capability-free child operates in a disposable Linux user/mount namespace; the authority
outside that namespace runs the real `RootedViewIO` atomic replacement. The child succeeds
at initial ledger append, sees the authority replacement, creates a sibling temp within
journal, renames it over ledger and appends again; the parent sees the final bytes, notes,
e2e and `src` changes. Tested writes/renames of acceptance, increment, roadmap, project
and worklogs ancestors, project other file, open-questions and another project's ledger are
refused; tested link/rename to acceptance and symlink-followed write cannot change it.
The child can create the symlink in notes, however: current publication rejects newly
introduced symlinks (and policy may reject other working changes), so this is still a
possible late-refusal/recovery issue. A temporary attack file also remains in notes.

This is the simplest promising mechanism observed so far, not an implementation or a
complete boundary. An entire writable journal directory grants creation/rename/deletion of
*other files in that directory*, not only ledger. A filename, temporary-file and cleanup
contract must be reviewed; this may change Q-V2-WRITE-SCOPE-1=A and cannot be silently
selected. The shell also still sees the rest of source writable in this diagnostic: it
does **not** prove the full nested write scope beyond worklogs, other purposes, immutable
closure, ABA, open FDs, concurrency, stop/publish, verifier or authority identity. Separate
bind mounts can yield EXDEV for rename across working directories; test real workflows and
file-tool staging before deciding. Producer/EDGE, no-host-alias isolation, recursive mounts,
mount propagation, subprocesses, links, `renameat2`, failure recovery and W4 need coverage.
No Docker, AppArmor, FUSE or new dependency is needed for this local experiment, but
Docker/container integration and supported-host prerequisites remain unproven.

Compatibility is substantive: `project_scaffold.py`, `project_metadata.py`, workflow and
prompts, `publication.py` bootstrap paths, documentation, user links, existing projects,
revision manifests and test fixtures reference the current root `ledger.md`. Do not add a
symlink, silently relocate data or rewrite historical evidence. Plan versioned layout,
explicit compatibility/migration, conflict/crash/replay and canonical single source; choose
a policy after testing. A read-only compatibility copy would not be an automatically coherent
ledger and cannot masquerade as one. Keep the existing layout until approved.

**TEST-EDITS:** extended the existing local mount diagnostic; old assertions remain. Five
module topology/view-IO/purposes/views/publication bank **282 passed**, scoped Ruff/format
and source-path mypy passed. Three diagnostic mutants (drop parent RO, drop journal mount,
alter real rooted ledger replacement) killed and restored; no production producer/EDGE
claim. The diagnostic uses `unshare -Urnm`, `mount`, `setpriv`, non-root uid/gid, pytest and
project environment; a skip is not PASS. E657, mandatory immutable-payload fallback, E674,
STEP9A/9B and W4 remain open.

### E694 — prioritize simplest layout to unblock STEP9A, not a separate research project

Historical candidate/status below is superseded by E695: notes-ledger was selected and its
local kernel diagnostic has run; no production implementation or host proof follows.

Operator accepts relocating the ledger in principle and emphasizes closing STEP9A, then
I03, before live-host deployment. Do not take this as approval of a particular migration,
a broader nested-coder scope, or changing trusted evidence. The next comparison is bounded:

1. **Leading simpler candidate:** put the canonical ledger at
   `worklogs/<slug>/notes/ledger.md`, reusing the already approved writable notes subtree
   instead of introducing E693's additional `journal/` writable subtree. The name is a
   proposal, not an implemented/approved canonical path. In principle this avoids a new
   directory-wide scope exception and a third writable bind, and temp files can live beside
   ledger. E693's separate-directory result makes it plausible, but **no test has run with
   ledger inside notes**, and notes cleanup/editing could overwrite or remove it. Document
   its canonical location in prompts and distinguish narrative from authoritative evidence.
2. E693's separate `journal/ledger.md` keeps ledger semantically distinct and passed a local
   diagnostic, but permits all files inside a new writable directory and needs an explicit
   scoped-contract decision. It is a fallback if the single notes location is undesirable.
3. Keep the current root ledger only if an adequately proven mechanism beats this simpler
   layout; E688 file bind, E689 project bind, and E690 naive Landlock each fail a required
   local property. AppArmor needs an AppArmor-capable host and secure profile lifecycle;
   FUSE adds a trusted daemon and lifecycle; neither is selected. Do not build either
   merely because it is available.

**Only remaining discriminators before choosing implementation direction:** run the focused
notes-ledger topology probe, including normal file-tool/shell replacement and sibling denial;
then inventory compatibility and devise a single canonical location for new/existing projects
with explicit conflict, crash/retry and historical-reference handling. No silent duplicate
ledger, symlink alias or rewriting old evidence. Check bootstrap paths, prompts, scaffolding,
publication, metadata and fixtures. Prove nested scope beyond `worklogs`, including allowed
`src/scripts`, and protect the *complete* pinned closure even if support/config lies outside
acceptance. A top-level worklogs mount alone cannot prove those properties. Design shell and
file-tool consistency, late-failure work preservation, and stale-FD concurrency semantics;
run real authority stop/snapshot/publish/repin and producer/EDGE tests. Then verify on an
appropriate Linux/container host before claiming deployment readiness. Do not block unrelated
STEP9A slices on speculative attack research, but keep E657 until the actual boundary is
proven. Legacy fresh-project BOOTSTRAP origin issue E679, E683 lineage/reset, immutable
fallback, exact attribution, full E674 gates, STEP9B and W4 remain separate open obligations.
A user-run standalone host harness is optional if an environment-dependent question cannot
be answered locally; Docker-free syscall results alone are not Docker integration evidence.

### E695 — accepted notes layout and focused kernel probe

Operator accepts `notes/ledger.md` and directs `notes/open-questions.md`; roadmap relocation
is optional only if it materially simplifies architecture. It does not: the E693 read-only
worklogs parent already protects the root roadmap without a separate mount, while
`workspace.py` project discovery/collision, `project_metadata.py` role recognition,
scaffold, admission reads and prompts explicitly use the root path. Leave roadmap at root.
This decision concerns new V2 project targets, not an automatic move of the existing I03
worklogs or historical evidence. Source runtime and canonical schema have not changed.

The local E693 diagnostic now also tests notes as the ledger's only writable directory
mount, alongside e2e. `RootedViewIO` replaces `notes/ledger.md` from outside the child
namespace; fresh shell append, same-directory atomic replace and subsequent append are
visible in backing storage. Tested outside-scope worklogs writes and ancestor/acceptance
attacks fail; a working `notes/open-questions.md` edit succeeds and is visible. This is
expected usability, but proves the Q file alone cannot be trusted as an immutable admitted
decision. Parent and child use the same backing; the child has a host alias outside this
namespace and this is not a Docker isolation or publish witness. Notes symlink creation
is allowed even though the tested follow-write into acceptance fails; current publication
may reject new links late. Full nested scope, Q decision binding, lifecycle,
migration, recovery, open-FD concurrency, full closure and real composition remain open.

TEST-EDITS: parameterized the existing diagnostic, preserving previous cases. Five-module
bank **283 passed**, scoped Ruff/format and source-path mypy passed. Three targeted
diagnostic mutants killed/restored: omit parent RO, omit notes mount, suppress questions
write. This is C3 local observation and no production producer/EDGE, W4 or E657 closure.
Follow E694's bounded next steps: update canonical schema and actual production seams in
properly grounded vertical slices; test existing/new projects, conflict/crash recovery,
independent mutation confinement and real authority stop/seal/publish/repin.

### E696 — desired behavior and progress reconciliation (audit, 2026-11-23)

**Current truth:** E695 is a local mount diagnostic, not a production projection, actual
Docker isolation, full closure, authority publication or host witness. E657's dispatch
fence remains. The V2 controller still has a workspace-local seal-store path; E679 shows
real staged create-new does not establish the BOOTSTRAP origin needed for the authority
private seal. E683 deletion/reset with fresh lineage remains a policy and implementation
task, not an operational recovery guarantee. Historical green scoped checks do not satisfy
E674: complete repository `just check`, full mypy/pyrefly and the complete STEP9A module
mutation sweep remain required and unrun at the final candidate SHA. STEP9A/9B, subsequent
new slices, STEP10, W3/W4 and I03 remain open in their prescribed order.

**Behavior contract:** ordinary file-tool and shell edits to current-project notes/e2e and
notes/ledger are working edits, without separate ledger authority, mandatory re-admission,
reseal, interactive approval or manual evidence ritual per edit. The harness captures
verification at the relevant execution boundary. A host PASS still requires a recorded
run and assigned reviewer, not agent-authored Markdown. Acceptance, admitted semantic plan
and authority-controlled admission/evidence must not silently change, whether via shell,
file tools, ancestor replacement, transient ABA or alternate aliases. Where a semantic
decision is used to unblock a Q-dependent gate, preserve the planner's best-effort decision
rights and bind/validate the decision to the relevant run/revision, so later working-note
edits cannot retroactively alter it. The exact binding/authorization and when an affected
semantic change requires a new admission or seal are implementation design/proof tasks;
do not require a reseal for every ordinary Q resolution, add a separate journal by default,
or change user-approved policy without an explicit Q#. A changed admitted plan or oracle
uses the existing new-version/replan or TEST-DEFECT flow, retaining old evidence.

**Bounded implementation obligations:** follow E686/E687 plus E695 in a grounded vertical
slice: use one authority-derived policy across file IO, shell projection, seal and replay;
preserve Q141's independent single-target mutation executor; protect source-based oracle
closure even when dependencies lie outside `worklogs`; avoid hidden writable backing aliases;
validate required mounts/paths before dispatch; give actionable denials and preserve safe
non-protected work on late refusal/uncertainty subject to reconciliation, never publish
unvalidated or uncertain changes. Test existing/new projects, notes layout migration
(including conflicting copies and historical references), early failure, stale open FDs,
concurrent views, actual stop/seal/publish/repin, TEST-DEFECT, lost seal/deletion and
recovery, producer/EDGE kills, observe/enforce and W4 host evidence. No unsupported
AppArmor/FUSE dependency, Docker-free experiment or local PASS may be substituted for
production C1 and the eventual reviewed host witness. Continue independent STEP9A work in
parallel where possible; do not block unrelated work on optional exploratory depth.
