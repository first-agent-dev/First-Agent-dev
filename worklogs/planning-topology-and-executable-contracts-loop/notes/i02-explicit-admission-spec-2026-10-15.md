# I02 explicit admission: implementation contract

Date: 2026-10-15. Scope: retained I02 SLICE6, not execution isolation.
Source baseline: `d9109f489c84cb7f1ab3568b609d96e5b2b61ae2` (product source unchanged at E201).
This specification supersedes the active schema wording in migration-bank §4; the old envelope
there remains historical provenance. This document is a contract, not implementation evidence.
Q67(a) and Q68(a) were explicitly approved on 2026-10-16; see the question record and E211 for
that decision history and separately scoped implementation/test evidence.

## 1. Entry contracts and ordering — CT74/CT90/CT95

Implement one pure `_validate_workflow_request` in `workflow_controller.py`, reused by CLI before
lifecycle allocation and by `run_workflow` before deriving artifact paths. Return validated values
or a typed input error; do not create directories or catch invalid input into a passing default.

- Roles: nonempty list of strings; strip surrounding whitespace, reject blank/unknown values.
  Preserve the order of non-eval stages. `_ensure_eval_after_coder` deliberately relocates explicit
  evals and inserts one immediately after **each** coder; this is the explicit Q55 exception to
  requested-order preservation. Retain repeated coder stages and prove one T0 across them.
  For this increment, reject a configured planner after the first coder (`role-order`): ordinary
  post-coder planning otherwise changes the target after its eval. This is a new, explicit safety
  restriction, not implementation of an alternating planner/coder scheduler. Adaptive replanning
  still goes through its bounded controller path. At most one ordinary initial planner is allowed.
- Mode is exactly `linear|adaptive`. Apply adaptive role requirements to the **normalized** list:
  coder is required and inserted eval satisfies Q55; CLI must not reject omitted eval first.
- Budgets: None → existing defaults; require `type(value) is int` otherwise; clamp integers to
  `[0, MAX_REPAIRS_CEILING]` and `[0, MAX_REPLANS_CEILING]`. No bool, string or `int(value)` coercion.
  Reuse existing constants rather than separate CLI ceilings. Zero permits valid input.
- Run ID: `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`; match the artifact/session contract, not the CLI's
  current looser first-character check. Validate requested ID before generation/path construction;
  validate controller-generated ID too. A supplied RunContext must match run ID and workspace.
- Validate task/inject configuration before lifecycle allocation as well; malformed injection must
  not leave a claimed session/run. Do not execute project code during this phase.

Add read-only `SessionManager.resolve_workflow_workspace` (new method, not an existing API): for
an existing session read/validate its manifest and workspace override agreement, without touch,
provisioning or run claim; for a new session resolve the same explicit/default target the existing
manager will use. CLI resolves relative `--plan` against this selected workspace, never CWD.
A fresh default workspace that cannot already contain an explicit plan is rejected with guidance to
create/choose a workspace first. No automatic bootstrap is delivered here. After lifecycle resolution,
check the actual workspace equals the preflight workspace; disagreement blocks before provider.
Do not invoke `_resolve_workflow_lifecycle` just to discover a path: it calls `begin_run`.

Keep the named `_require_plan_for_coder` producer called directly by both `_cmd_workflow` and
`run_workflow` after pure identity validation. It checks presence, not a second independent parser.
CLI reads/checks a supplied path before lifecycle; without the presence guard, the missing-plan
case would reach lifecycle/direct rejection, which C2 must detect. The direct guard owns its
safely-addressed BLOCKED response. Do not accidentally make either declared kill VACUOUS through
duplicated presence checks elsewhere.

Failure classes are deliberately different:

| Failure | Return/evidence | Forbidden effects |
| --- | --- | --- |
| Malformed roles/mode/budget/run ID/context binding, including direct API | typed input failure, exit 2; CLI prints sanitized reason | No path derivation, session/run/artifact write or provider |
| CLI missing/unusable/outside/oversized plan | exit 2 before lifecycle; sanitized reason | No session/run/artifact write or provider |
| Direct API has valid request identity but missing/unusable plan | nonzero; best-effort BLOCKED flow and durable BLOCKED admission if storage works | No provider/T0/verification/eval |
| Artifact storage/lock/fsync failure | nonzero, separately observable error; best-effort blocked flow | No claim that an absent/uncommitted artifact persisted |

An invalid run ID cannot also have an admission record addressed by that invalid ID. CT95's
structured artifact obligation applies only after safe request identity exists.

## 2. Types, snapshot and admission loop — CT87/CT91/CT95

Add frozen `PlanRef(workspace_relative_path, source_kind, sha256)` and private
`PlanSnapshot(ref, utf8_bytes, text, ids)`; raw bytes/text never go into admission.json.
Use one rooted descriptor-walk reader: reject absolute input to capability writers, traversal,
symlink at **any** component, nonregular terminal, invalid UTF-8, empty/whitespace-only input,
and >1 MiB. Open with no-follow flags; fstat the opened descriptor; read at most limit+1 bytes.
Check identity from the descriptor, not `is_file()` followed by unrelated `read_text()`.
Normalize the stored relative POSIX path; reject empty, `.` and `..` components, not just escapes.

Public explicit-path resolution may accept an absolute path **inside** the selected workspace;
store only its normalized relative identity. File tools accept only capability-relative targets.
This is local validation/race detection, not protection against arbitrary shell/host writers.

Initial sequence: pure request check → explicit snapshot read → create durable ACQUIRING admission
with attempts=[] before the first provider → optional configured ordinary planner → recheck source
hash → shared pre-coder validation/repair → durable ADMITTED attempt → T0 → coder.
The ordinary planner is free, once; it may write its existing allowed notes, not revise the active
PlanRef. Deny the active target in its file writer and block on detected out-of-band hash changes.
Do not silently accept ordinary-planner edits as a new admitted target.

`_validate_plan_admission(snapshot)` invokes both `precheck(text, path=relative_path)` and
`validate_kill_directives(text, ids, path=relative_path)` on **the same** text/IDs. Return typed PASS, DIAGNOSTICS or
INDETERMINATE plus sanitized diagnostics. No caller independently rereads or reparses the target.
PASS needs ≥1 parsed slice and no FAIL/ERROR. WARN alone is advisory. Nonempty zero-slice text
with determinate FAILs may be repaired; empty text, unexplained zero slices, validator exception,
reader error, or final zero slices is indeterminate/blocking. Never turn an exception into [].
Use extractor-produced slice IDs only; preserve existing strict accessor semantics. This does not
ratify Q43's separate leniency proposal or add canonical-ID coercion.

On DIAGNOSTICS, append RETRY before dispatch; require a configured planner and reserve one shared
planner credit **before** `_run_admission_repair`, even on provider/write/promotion failure.
Admission repairs and adaptive eval replans consume that same counter; initial ordinary planning
is free. Max repairs still bounds additional coder dispatches. Configured repeated coders are
explicit stages, not hidden retry credit. Linear does not enter adaptive routing.
Repair seeds from the latest rejected draft, validates each result, and repeats only determinate
FAILs within the remaining budget. No planner, timeout, indeterminate result, capability error or
promotion/artifact error terminates BLOCKED, without T0/coder/eval. Do not endlessly retry IO.

Separate `PlannerDispatchKind = ORDINARY_PLANNING|ADMISSION_REPAIR|EVAL_REPLAN` from the admission
artifact's input-attempt kinds below. Thread the former and a controller-created candidate target
through `_run_stage` → `_cmd_run` → registry → profiles → scoped writer; not model JSON fields.
I02 `invoke_workflow` lacking explicit supported admission returns `acquisition_unavailable` before
child controller/provider dispatch. Do not pass the parent's RunContext into a speculative child.

## 3. Exact admission.json v1 — CT92 / Q62 implementation specification

The table below supplies the missing implementation vocabulary. Q62 is a spec gap, not a new
operator-policy choice; its historical Status line is left unchanged until implementation review.
Q59/Q60/Q63 choices are not resolved by this document. Reserved I03 enum values do not authorize
managed acquisition in I02. Reject unknown keys, values, validator/rule pairs and versions on read
and write; validate **all** old attempts, not just newly appended data.

Top-level keys exactly `{schema_version, run_id, status, plan_ref, attempts}`:

- `schema_version`: JSON integer 1, not true; run_id as §1; status `ACQUIRING|ADMITTED|BLOCKED`.
- `plan_ref`: null or exactly `{workspace_relative_path, source_kind, sha256}`; path as §2;
  source_kind `EXPLICIT|EXISTING_SELECTION|BOOTSTRAP`; I02 writes EXPLICIT only.
- `attempts`: array; empty allowed only for initialized ACQUIRING. No completed admission is empty.
- Attempt keys exactly `{attempt, dispatch_kind, validation, diagnostics, source_sha256,
  candidate_sha256, promoted_sha256, route}`. Positive integer attempt indices contiguous from 1,
  never bool. dispatch_kind `EXPLICIT_INPUT|ADMISSION_REPAIR|EVAL_REPLAN|ACQUISITION`; EXPLICIT_INPUT
  is essential for the initial local validation, not a repair or I03-only acquisition dispatch.
- validation `PASS|DIAGNOSTICS|INDETERMINATE`; route `RETRY|ADMITTED|BLOCKED`.
  DIAGNOSTICS/RETRY needs ≥1 FAIL; ERROR entails INDETERMINATE/BLOCKED; ADMITTED requires PASS,
  a nonnull PlanRef and a nonempty accepted plan (not inferred from this JSON alone).
  A determinate failure with no credit/planner may be DIAGNOSTICS/BLOCKED.
- All hash fields are null or lowercase 64-hex. Initial valid-source attempt: source hash equals
  snapshot, candidate/promoted null. Repair/replan: source is the CAS base, candidate is validated
  draft; promoted is null before replacement and equals candidate only after verified promotion.
  Final ADMITTED PlanRef sha equals the initial source or successful promoted hash as appropriate.
  Never overwrite the last known canonical PlanRef with a rejected candidate's hash.
- Diagnostic keys exactly `{validator, rule, severity, line}` plus optional `contract_id`.
  severity `FAIL|WARN|ERROR`; line positive JSON integer or null, never bool; null for no source
  location. Optional contract_id `^CT\d+[a-z]?$`. No message/snippet/path/exception string field.

Closed validator/rule sets (hyphen spelling is normative):

| validator | allowed rule values |
| --- | --- |
| precheck | heading-near-miss, step-marker-unknown, step-near-miss, slice-count-at-ceiling, orphaned-slice-field, slice-without-tests, step-without-exit, deps-undefined-slice, deps-cycle, contract-reference-undeclared, contract-declared-twice, contract-declaration-lost |
| kill-directives | kill-directive-near-miss, kill-directive-malformed, kill-directive-ambiguous, kill-directive-missing |
| plan-ref | missing, path-escape, symlink, not-regular, unreadable, invalid-utf8, empty, too-large, zero-slices, source-changed, validator-error |
| promotion | scope-denied, symlink, not-regular, source-changed, prepare-failed, replace-failed, durability-unknown, hash-mismatch |
| artifact-io | corrupt-record, lock-failed, append-failed, durability-unknown |
| bootstrap | unavailable (reserved I03; successful bootstrap rules need an explicit schema extension) |

Do not invent a generic `unknown` rule; unrecognized validator diagnostics map to
plan-ref/validator-error, ERROR, INDETERMINATE/BLOCKED without persisting exception text.
Artifact write errors may be recorded in flow/session diagnostics if admission itself cannot write.
Changing a closed table or adding fields needs an explicit schema-version/compatibility disposition,
not silently accepting the new value. No existing production admission v1 exists to migrate in I02.
I03 must define its managed extension rather than pretending the reserved bootstrap value suffices.

Implement `write_admission_record` in `workflow_artifacts.py`: use existing private-root conventions;
new no-follow 0600 process-shared flock file, bounded lock acquisition under workflow deadline,
0700 directory, schema-check old/full new payload, same-directory unique temp, fsync file, replace,
fsync directory. Never truncate an old record on error. Reject corrupt/incompatible prior data;
no best-effort reset to attempts=[]. A concurrent append must not lose either committed attempt.
Each retry/final admission append is a barrier before the next pre-coder provider/coder.
Append failure after promotion keeps canonical bytes and prevents coder; no rollback.
After a successful coder, admission IO must **not** short-circuit required eval (§5).

## 4. Exact-target writer and Q58 promotion — CT93/CT94

Use small descriptor-rooted IO primitives shared by admission and scoped writer, not a generic
transaction framework. Add `build_scoped_write_file_tool` in `tools/write_file.py`; retain the
ordinary tool surface but close over a controller-created single normalized target. Reject a
second path, symlinked ancestor/terminal, absolute path, hard-link target (`st_nlink != 1`), and
nonregular files. Do not delegate a checked string to the existing unrestricted `write_file`.
Ordinary planner denies `.fa/admission/` and its active PlanRef. Do not broaden worklogs prefixes.
I02 permits fresh repair/replan candidates only, under `.fa/admission/<run_id>/`; exact-target C3
must reach the actual `_cmd_run` registry handler, not a handcrafted substitute registry.

`_promote_validated_plan(snapshot, candidate_bytes, …)` only accepts the canonical increment
namespace already approved by Q58. Valid explicit non-increment inputs can admit, but a required
repair/replan of one blocks scope-denied before a candidate provider. Under one canonical-target
process-shared lock, rooted no-follow reopen/verify source hash, type and link count; stage the
**validated byte buffer** into a unique hidden sibling (never recopy a mutable draft), preserve
permission bits, fsync, os.replace, fsync parent, reread/hash resulting target, update PlanRef,
then final durable admission append. A rejected draft can be retained for the next bounded retry;
clean only owned temps/candidates on terminal exit, retaining hashes/diagnostics.

Before replace: original bytes/mode unchanged. After replace: no automatic rollback, including
parent-fsync/hash/final-append failure; preserve canonical state, report uncertainty and block.
Lock serialization/CAS prevents cooperating publishers, not arbitrary host/shell writers; never
claim I03's no-escape boundary. Hard links and symlink races need subprocess negative tests.
Q58 one-file replacement is not bootstrap no-clobber or crash-atomic multi-file publication.

## 5. T0, attempt evidence and routing — CT71–CT77/CT86/CT95

Add an explicit run-local baseline state `NOT_CAPTURED|CAPTURED|FAILED`, independent of repair
counter. Only NOT_CAPTURED may call capture_baseline, after admission, immediately before the
first coder. Mark failed capture FAILED; do not retry on the changed tree. Reused/pre-existing
baseline must schema-check run identity and the complete normalized slice→TESTS map in **both**
directions. A stored baseline without this identity is incompatible, not silently upgraded.
A legitimate red test baseline with exact nodeids is allowed; failed collection, absent/stale/
corrupt report or baseline persistence is not. T0 uncertainty blocks before coder in both modes.
Exclusive/no-follow write and file+directory durability are required for the immutable T0 file.

Each admitted coder stage uses its pinned snapshot for verifier ownership and eval ID validation;
`ctx.plan_text()` must not become an independent authority. Verification attempt is bound to the
snapshot's PlanRef hash (extend the existing artifact explicitly, no second verifier engine).
Before coder and after its successful return, reread/hash via the same reader. A post-coder
mismatch appends typed indeterminate evidence while keeping the original snapshot; it does not
return a nonzero StageResult early. Run real eval with this attempt's evidence, then hard-block
completion in **both** observe and enforce. Missing required verification/admission persistence,
T0 identity or eval artifact also prevents a successful terminal result in both modes. Observe
remains advisory only for determinate command/kill/regression judgment; it is not a waiver of
PlanRef/control-plane integrity or missing evidence. Preserve Q56 non-complete eval precedence.

Do not replace the model report or synthesize eval. If artifacts cannot persist after coder,
attempt eval once while deadline permits, retain the IO failure in returned/terminal diagnostics,
and return nonzero; never claim persisted evidence. If the shared deadline is already exhausted,
record eval not executed and fail: Q55 does not authorize unbounded work or a fabricated report.
Terminal completion also rechecks active PlanRef to prevent a later stage's stale success.
Harden `workflow_exit_code(0, None)` to nonzero; preserve already-nonzero results. Missing terminal
state is never successful completion, even if the caller lost the flow artifact.

## 6. Binary local proof package (future evidence, not this review's result)

Extend `tests/test_verify_gate_live.py`; required named groups match SLICE6 selectors. Every group
must collect ≥1 test and exit 0; exit 5 or all-skipped is not evidence. Direct C1 keeps only the
provider seam mocked. C2 uses actual CLI preflight; C3 actual role registry/scoped writer. Unit
fault injection supplements, not substitutes for, these compositions. Inspect persisted JSON bytes.

Required matrix: linear/adaptive × observe/enforce; omitted/misordered eval; repeated coder T0;
invalid roles/order/types/run IDs and context mismatch; CWD different from selected/resumed workspace;
invalid inject with no lifecycle effects; PlanRef size/UTF8/path/symlink/hard-link failures; initial
record/no provider on IO failure; WARN, structural repair, no planner, zero/shared exhausted budget;
rejected-draft retry; source CAS conflict; pre/post-replace faults; corrupt old admission/unknown
keys/enums/bool integers; concurrent appends; T0 collection/storage/schema/topology failure; actual
post-coder mismatch and artifact failure reaching eval but never DONE in either mode; unavailable
nested acquisition dispatching zero child providers. Successful ordinary source editing still works.

Record all 16 retained SLICE6 FUNCTIONAL **full test-path** mutation runs and their individual
provenance/outcome/duration, without contract→nodeid attribution. A collector/runner/timeout/infra
error is ERROR, not a kill. Q53(c)'s slice sensitivity remains; no new clean-control policy.

Create the actual implementation acceptance report at `notes/i02-local-acceptance.md` only when
results exist: commands, code SHA, environment, rc, collected/pass/fail/error/skip identities,
artifact references, mutation table, source-restoration diff, independent review and operator signoff.
Run the full suite through the existing `just test` gate, and `just check`; separately retain each
blocking subgate result so expected red tests do not hide missing type/lint/coverage checks.
For baseline comparison use an isolated `git archive d9109f4` tree and the same supported Python,
locked dependencies/config/command; use separate tree-local environments and verify module origins
so an editable candidate install cannot contaminate baseline. Do not switch this session's branch. Capture baseline and
candidate exact failure nodeids plus failure phase/category, not just totals. Both runs need
complete collection/execution manifests and normal terminal summaries: E174's aborted reporter is
not an eligible baseline. Changed/new tests and changed-file checks must be green. Existing E19
and each unrelated baseline test/Mypy diagnostic need an explicit operator-reviewed disposition;
new or missing/unclassified failures = 0. If a usable full-run report cannot be obtained, local
DoD stays open. A blanket baseline waiver or lower count is never a passing result.


## 7. Ratified lifecycle and fixture clarifications — Q67–Q70, 2026-10-16

**Q67(a):** during the first eval-only replan, preserve canonical v1 ADMITTED and durably rewrite
its unchanged history before provider dispatch. Reserve shared planner credit before dispatch.
Append the actual EVAL_REPLAN validation/publication outcome afterward. A subsequent RETRY needs
an actual candidate FAIL; neither PASS/RETRY, synthetic FAIL nor a new pending state is allowed.
Retained canonical ADMITTED is not permission to dispatch coder during the revision. Final
validation, publication and durable admission of the revised snapshot remain prerequisites.

**Q68(a):** trusted result errors from actual publication tools `fs_write_file` or `pr_prepare`
invalidate a scoped attempt, even if later recovered. Recovered read/list/search errors alone do
not. Missing/nonzero terminal outcome and final validation/preparation/publication/IO uncertainty
remain fail-closed. Ordinary planning is unaffected. Project trusted paired tool names, not raw
error bodies or model prose, into the scoped controller's outcome check.

**Q69 (explicitly approved):** the constructed original C1 plan may select a nonrecursive leaf
fixture preserving the real-session/global/slice/eval assertions and nine internal producer kills.
The leaf's own plan has no FUNCTIONAL contracts. Runtime recursion markers are unchanged. All
16 normative SLICE6 kills still execute the complete outer public TESTS path, after a completed
unmutated whole-file baseline. No selected-mutant or test-subset substitution, fake PROVEN,
contract→nodeid mapping or infrastructure-error-as-kill is authorized.

**Q70 (coder-containing-only option explicitly selected):** unavailable managed acquisition
rejects nested requests containing coder (including default roles), before child identity,
handoff, artifacts or provider dispatch, as `acquisition_unavailable`. Do not reject otherwise
valid planner/eval-only delegation. Session-bound noncoder children use their own actual
SessionManager.begin_run binding, sharing the verified parent session/workspace/DB, not the
parent's RunContext. Invalid/missing authority or allocation fails closed. This is local supported
noncoder delegation, not successful managed acquisition, I03 context propagation or OS isolation.
