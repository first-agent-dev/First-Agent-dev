# Q-V2-STATUS-1 / Q-V2-BOOT-1 — source audit and design options (2026-11-20)

**Status: SOURCE AUDIT ONLY. No implementation, no ratified design, no code change.** This note
satisfies the first half of the operator's direction ("source-audit, then discuss until both sides
agree, then record"). Every claim below is grounded in the current checkout at `b0358ea`. Nothing
here changes a live result, the frozen producer baseline, a W3/W4 status, or a slice's status.
The linked plan remains `notes/i03-ai-native-workflow-refactor-plan-v2.md` (REVIEW DRAFT).

Question owners: `Q-V2-BOOT-1` (blocks SLICE2/SLICE5), `Q-V2-STATUS-1` (blocks SLICE4b/SLICE5;
SLICE4a unblocked). Both are pre-implementation gates: no tick producer, no seal code, and no host
witness exists yet.

## 0. Audit method

Read-only source reading of the authority write path, the bootstrap/install path, the controller
admission record writer, and the plan-publication path; plus the V2 plan's own constraints (§2 tick
gate, §3 custody, §5 error mapping) and Q154's resolved target. No test or gate was run for this
note; the STEP9 local bank is recorded separately (E556).

## 1. Q-V2-BOOT-1 — from install receipt to the revision-bound AcceptanceBundle

### 1.1 What already exists (verified facts)

| Fact | Source |
| :--- | :--- |
| `prepare_bundle` renders **exactly three** files (`roadmap.md`, `ledger.md`, `increments/increment-01-<slug>.md`) from strictly validated prose; controller owns all frontmatter. | `publication.py:556,562,611,664` |
| `store_bundle` accepts an arbitrary `files: Mapping[str, bytes]`, mints `bundle-<uuid>`, records per-file `sha256/size/mode` plus a canonical `bundle_sha256`, and validates the manifest. It proves OWNER grant, exact `base_revision`, no unsettled views and no pending intent before writing anything under the private `bundles/<id>/`. | `workspace.py:3322-3382` |
| The `_BUNDLE` manifest contract puts **no file count or path-shape limit** on `files` (`_BUNDLE_FILE` = path/sha256/size/mode; array unbounded). | `workspace.py:121-146` |
| Install re-validates every path independently: must be under `worklogs/<slug>/` with ≥3 components, no empty/`.`/`..`/dot-leading parts, none of `{.git,.fa,.venv,.env}`. Arbitrary depth is therefore allowed — `acceptance/tests/...` installs without any authority change. | `workspace.py:3638-3654, 229` |
| Install writes a durable BOOTSTRAP intent **before** the irreversible byte, then `RENAME_NOREPLACE` (collision is determinate, never repaired), then revision → pointer → proof → DONE. `operation_id` is derived deterministically from the bundle id (`op-` + bundle suffix), so retrying the same install converges on the same operation instead of inventing a second one. | `workspace.py:3485-3530, 3580-3600` |
| `_recover_bootstrap` lets the installed directory decide: absent ⇒ undo only what this attempt created; present ⇒ require the whole tree to hash to the intent's `tree_sha256`, then finish forward; a present-but-mismatched tree is never repaired or removed (`CORRUPT_STATE`). `_finish_forward` is explicitly the idempotent completion path. | `workspace.py:5385-5425, 3912-3945` |
| The install receipt is `{workspace_id, revision_id, tree_sha256, operation_id, projection_complete}` — it names **no bundle identity**. The BOOTSTRAP intent names operation/workspace/generation/base/next revision/target/tree/created dirs — also no bundle identity. | `workspace.py:3904-3910, 3587-3600` |

**Consequence:** the hard parts Q-V2-BOOT-1 was worried about are already proven — multi-file
private staging exists, install is no-clobber and forward-only, and recovery finishes a matched
install without deleting or repairing bytes. The expanded V2 manifest needs **no new authority
operation and no second writer**; the file-count/path assumptions live in the publication renderer,
not in the authority contract.

### 1.2 The actual gaps (narrower than the question assumed)

- **G1 (planner/publication layer, not authority).** `render_bundle`, `_validate_bundle_text` and
  `bundle_paths` are fixed to three prose files. V2 needs the fixed manifest
  (`roadmap.md`, `ledger.md`, `open-questions.md`, `increments/increment-01-initial-plan.md`,
  `acceptance/tests/...`) plus whole-project validation of the `INV→CT→TEST-ID→selector` graph and
  the `Plan-Format: AI-NATIVE-PLAN-V2` marker. That is a new pure renderer/validator beside the
  existing one; `store_bundle`/`install_project` are reused unchanged.
- **G2 (custody chain).** After a crash *between* the committed install and the seal, nothing durable
  states which bundle produced the installed revision. The link is only derivable by a string
  transform (`op-<suffix>` ⇔ `bundle-<suffix>`), which is an implementation detail, not a stated
  invariant. Without a recorded identity, the seal cannot be minted idempotently for *that exact*
  revision, which is precisely Q-V2-BOOT-1's complaint.
- **Non-gap:** a provisional canonical tree is not needed. The current install already leaves either
  "nothing happened" or "the approved tree exists at the canonical path", and the second case is
  resumable forward.

### 1.3 Options

- **A (recommended) — record the bundle identity in the durable install intent and receipt.**
  Add `validated_bundle_id` + `bundle_sha256` to the BOOTSTRAP intent and to the `install_project`
  receipt. The revision-bound `AcceptanceBundle` is then minted from the triple
  `(bundle_sha256, revision_id, tree_sha256)`: absent ⇒ not sealed; minting under the existing
  workspace transaction is idempotent for an identical triple and a determinate refusal for a
  different one. Recovery has one code path: finish the install forward (unchanged), then mint the
  seal from the recorded identity. No new lifecycle state, no new authority operation, no
  "INSTALLED_UNSEALED" state machine to reconcile.
- **B — explicit `INSTALLED_UNSEALED` record as its own state machine.** Satisfies the letter of the
  plan's option (A) but duplicates information the intent already carries, adds a second state to
  reconcile after crashes, and needs its own recovery/refusal matrix.
- **C — re-prepare and reinstall when sealing fails.** Rejected: install is no-clobber, so a retry
  collides; preparing again against a new base revision breaks the custody chain the seal exists to
  protect.

### 1.4 What remains STEP9A-owned

The seal object's shape, its custody closure (acceptance source/config/support/helper/fixture/
driver/runner bytes plus selector→nodeid resolution), its identity/digest computation, and the
mode-A read-only exposure. This audit only settles **how the install receipt chains into the seal**
and which primitives are reused.

### 1.5 Provisional verdict

BOOT-1 looks answerable without a new authority operation. Pending: STEP9A's seal contract and the
operator's agreement to option A.

## 2. Q-V2-STATUS-1 — status ticks that coexist with plan admission and seal

### 2.1 What already exists (verified facts)

| Fact | Source |
| :--- | :--- |
| Managed plan publication is a pinned-`PlanRef`, candidate-buffer, same-path forward-only replacement with an `old_sha256` CAS against the pinned ref, a durable PLAN intent before the irreversible replace, and no rollback of prior bytes. | `publication.py:740`, `workspace.py:4059-4170` |
| Therefore writing a `[ ]→[>]→[x]` tick into an admitted increment **creates new plan bytes / a new revision**, invalidating the admission binding and (later) the seal. The plan states this gate explicitly and forbids assuming the publication seam is a metadata writer. | V2 plan §2 "Status-producer design gate", §6 confirmed constraints |
| There is **no** V2 tick producer and **no** `AcceptanceBundle` code in `src/` today. | repo-wide grep |
| The workspace private store already holds durable authority records: `current.json` (generation/revision/tree), `intent.json`, `bundles/<id>/bundle.json`, `revisions/<rev>/`. No general status/progress record exists. | `workspace.py:3966-4050, 5210-5230`, `1160-1240` |
| Workspace mutations are serialized by a **process-local** `threading`-style mutex in `_transaction`, plus peer/lease checks — i.e. single-writer safety comes from the supervisor being the only writer, **not** from a cross-process file lock. | `workspace.py:1226-1235` |
| The controller-side admission record writer already implements the full append/validate/CAS pattern: private dir fd (no-follow, `nlink == 1`, owner check), bounded cross-process `flock` with a 120 s cap (deadline-aware), read→validate→append under the lock, attempt numbering assigned under the lock, atomic replace with fsync and read-back, schema validation with immutable identity fields, and corrupt-record refusal. | `workflow_artifacts.py:585,618,630,691,733-800`, `admission_schema.py:533` |

**Consequence:** the mechanics needed for a revision-safe tick record (atomic append, idempotency,
identity CAS, corruption refusal, cross-process locking) already exist in this repo in two different
places with different custody strength. The open question is *where the record lives*, not how to
write it safely.

### 2.2 Candidate placements

1. **Inside the sealed plan bytes.** Rejected: mutates sealed semantics, forces re-admission and a
   new PlanRef per tick, and contradicts "progress must not mutate the sealed inputs".
2. **Deliberate re-admission/re-seal per changed plan revision (the plan's option B).** Legal but
   expensive: every tick becomes a full validation/admission/seal cycle and a new revision; the
   revision history then encodes progress, which makes the "seal permits coder" barrier depend on
   tick churn. Acceptable only if we accept revision-per-tick.
3. **Authority-owned progress record in the workspace private store (option A).** Strongest custody:
   written inside the same supervisor transaction family that owns revisions/pointers, bound to
   `(revision_id, tree_sha256, plan_sha256, bundle_sha256)`. This is a **new authority operation**,
   which the plan says requires explicit STEP9A dependency review before implementation.
4. **Controller-owned progress record beside `admission.json` (option A, weaker custody).** Reuses
   the proven lock/append/validate writer; per-run rather than per-workspace-revision; must carry the
   workspace/revision/plan/bundle identity fields itself to be revision-safe.

### 2.3 Recommended design (for agreement, not yet implemented)

Take **placement 3 if STEP9A approves a new authority record, else placement 4** — with one identical
record schema and one identical projection renderer, so the choice changes custody only:

- **Record:** `{schema_version, workspace_id, generation, sequence, entries:[{seq, step_id, tick,
  exit_check_id, test_ids[], revision_id, tree_sha256, plan_sha256, bundle_sha256, at}]}`.
- **Append contract:** caller supplies the expected identity triple plus the step; the writer refuses
  on mismatch (`STALE_PROGRESS_IDENTITY`) with no partial write; a replay of the same `(step_id,
  seq)` returns the recorded entry unchanged (idempotent); a skipped/overlapping `seq` is refused;
  the writer assigns the next `seq` under its lock. Durability failure ⇒ `DURABILITY_UNKNOWN`, last
  committed sequence remains authoritative, no tick is shown.
- **Non-mutation proof:** the append must leave `revision_id`, `tree_sha256`, `PlanRef.sha256` and
  bundle digest byte-identical — asserted directly, not inferred.
- **Projection:** a pure renderer `render_progress_markdown(record) -> bytes` (C0 oracle), written to
  a controller-owned **read-only** location, never into the sealed tree; the same record must render
  byte-identically (digest stability asserted). The projection is derived state only — losing it
  loses nothing; it is never read back as authority.
- **Ticks and vocabulary:** only the canonical `[ ]→[>]→[x]` / `OUTLINED→READY→IN PROGRESS→SHIPPED`
  / `PLANNED→IMPLEMENTED→VERIFIED` values, and promotion only from sealed `EXIT-CHECK-ID` results;
  no free-text exit can advance a tick, and `VERIFIED` stays unreachable until L2 judgment exists.
- **Producer/EDGE kill-checks:** remove the append call ⇒ the accepted-transition assertion fails;
  remove the identity CAS ⇒ the stale-identity case advances when it must refuse; write the
  projection into the tree ⇒ the sealed-bytes digest changes and the test fails.

### 2.4 Open decisions for the discussion

1. **Custody vs. friction:** new authority operation (placement 3, strongest, needs STEP9A review)
   vs. controller-side record (placement 4, proven writer, weaker custody). This is the only real
   product/contract choice left in Q-V2-STATUS-1.
2. **Where the projection is visible:** controller state directory vs. the run's log directory vs. an
   explicit `progress.md` in an authority-owned read-only projection root. It must be host-inspectable
   for the W4 witness without entering the sealed revision.
3. **Revision lineage on replan:** the plan says stale/replanned plan revisions get new status
   lineage. Whether lineage is a new record (new `workspace_id`-scoped sequence) or a `lineage` field
   in the same record is a contract detail STEP9A can settle; it must not allow a replayed old-plan
   tick to advance.
4. **Cross-process assumption:** placement 4's `flock` protects concurrent writers; placement 3 relies
   on the supervisor's single-writer model. If any future shape allows two writers to a workspace,
   placement 3 needs an explicit lock, and that must be stated rather than assumed.

## 3. What this audit does and does not decide

- **Decides:** BOOT-1 needs no new authority operation; its gaps are (G1) a V2 renderer/validator and
  (G2) recording the bundle identity in the durable install intent/receipt. STATUS-1 needs no change
  to sealed bytes; its mechanics already exist, and its only real choice is custody placement.
- **Does not decide:** the seal object's identity/custody contract (STEP9A), the custody placement of
  the progress record (operator + STEP9A), or any slice authorization. No slice is unblocked by this
  note; SLICE4b/SLICE5 stay blocked until the design is ratified in the documents.
