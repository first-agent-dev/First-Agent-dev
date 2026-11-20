# Q-V2-BOOT-1 audit — does "mint the seal after install" actually hold? (2026-11-20)

Scope: verify the selected route (**A — the acceptance closure is installed as part of the project, the
seal is derived from the installed bytes and bound to the revision the install receipt names**) against
the real authority source, enumerate the edge cases, and state honestly where A does **not** hold without
an additional decision.

Sources read (no product code changed): `src/fa/execution/workspace.py` (`install_project:3485`,
`_install_prepare:3556`, `_install_finish:3880`, `_finish_forward:3912`, `_recover_intent:5280`,
`_recover_bootstrap:5390–5428`, `_load:1322`, `_verify_revision:1463`, `_revision:1428`, `_snapshot:1317`,
`_TREE:184`) and `src/fa/inner_loop/acceptance_bundle.py` (`write_seal:429`, `verify_sealed_root:456`,
`verify_plan:483`, `verify_revision:497`, `_SEALED_ROOT_RE:77`).

## What the source proves

1. **Install computes the future tree before writing anything.** `_install_prepare` proves every
   precondition and "compute[s] the exact tree that will exist"; `revision_id`, `tree_sha256` and
   `operation_id` exist before the irreversible rename (`workspace.py:3556+`).
2. **The install receipt is a revision-bound identity.** `_install_finish` returns
   `{workspace_id, revision_id, tree_sha256, operation_id, projection_complete}` (`:3904–3910`).
3. **Crash recovery is derivation-based, not phase-based.** `_recover_intent` discriminates on the
   inspected target (`:5280`); `_recover_bootstrap` re-snapshots the installed project and *requires*
   `digest == intent["tree_sha256"]`, otherwise `CORRUPT_STATE`, then finishes forward (`:5390–5428`).
   A recovered install therefore converges on exactly the revision/digest pair a clean install produces.
4. **A revision record does not name its parent.** `_TREE` (`:184–192`) holds
   `schema_version, revision_id, tree_sha256, entries`; `base_revision` exists only in intents and view
   references. **There is no ancestry/lineage query in the authority.**
5. **The seal names the plan bytes, the closure digest and a revision** (`verify_plan:483`,
   `verify_sealed_root:456`, `verify_revision:497`); `write_seal:429` creates with `O_EXCL` and never
   replaces (`seal-exists`), fsyncing file then directory.
6. **The sealed root is a fixed relative path** `worklogs/<slug>/acceptance` (`_SEALED_ROOT_RE:77`), i.e.
   inside the revision-tracked project directory.
7. **Load-time integrity only checks each revision's own copy** (`_verify_revision:1463` →
   `_revision:1428` snapshots the revision's `data` directory); nothing compares the canonical tree to the
   current revision's manifest. Canonical drift is therefore not an error — the next publish simply
   records it as the new revision.

## The two corrections A needs (both are findings, not preferences)

**C1 — the seal must not be a plain file inside the tracked tree, and cannot be left out of the model.**
Writing `worklogs/<slug>/…seal…` as a raw file makes the canonical tree diverge from the manifest of the
revision the seal names (fact 7: nobody notices), so "the project at revision R" and "the bytes on disk"
stop meaning the same thing at exactly the artifact that is supposed to prove custody. Two ways out: make
the seal part of a revision (a second publish, i.e. a new state the model has to explain), or keep the seal
in **authority-private metadata** where revisions never walk. A′ selects the second: the seal is written
into the workspace binding directory (beside `current.json`/`revisions/`), not under `worklogs/`.

**C2 — `verify_revision` is an admission-time check, not a standing one.**
The coder's legitimate writes advance the current revision while the acceptance bytes stay frozen (that is
what mode A means). Applying `verify_revision(seal, current)` on every check would therefore invalidate
every seal immediately after the coder's first write, and the ancestry check that would repair it does not
exist (fact 4). The correct split is: **revision equality is verified once, at coder admission**, against
the receipt revision (`current` at that moment); **standing custody is content-based** —
`verify_plan(plan_bytes)` + `verify_sealed_root(root/worklogs/<slug>/acceptance)`, which are strictly
stronger than a revision pin because they name the exact bytes rather than a snapshot label.

## Edge cases

| # | Situation | Route A′ outcome | Proven by |
|---|---|---|---|
| E1 | Crash before the rename (intent `PREPARED`, no project) | Nothing installed, no seal; recovery discards the attempt | `_recover_bootstrap` discard branch |
| E2 | Crash after rename, before revision/pointer | Recovery proves `digest == intent.tree_sha256`, finishes forward with the same `revision_id`; seal then minted over those bytes | `:5390–5428`, `_finish_forward` |
| E3 | Crash after revision, before the seal exists | Restart sees an installed revision with no seal → mints deterministically from installed bytes + plan bytes + revision; byte-identical to the seal a clean run would have written | `_install_prepare` determinism (fact 1) + content-only mint inputs |
| E4 | Crash mid-`write_seal` (torn file) | `load_seal` fails → **hard error, never a silent re-mint** (re-minting over a corrupt record would launder it) | `write_seal:429` (O_EXCL + fsync) |
| E5 | Two concurrent installs of one slug | The loser gets `COLLISION` before any seal write | `install_project:3520–3526` |
| E6 | Installed acceptance bytes tampered after the seal | `seal-byte-drift` / `seal-missing-bytes` / `seal-extra-bytes`, fail closed before any verification or kill oracle runs | `verify_sealed_root:456` |
| E8 | Coder writes normal project files after the seal | Acceptance bytes untouched → content checks still pass; the revision pin is not re-consulted | C2 |
| E9 | Workspace restored from a backup that lacks the private seal | Seal re-minted from the restored bytes; equality of content is what the check asserts | C1 + E3 rule |
| **E7** | **The plan is revised (replan) and a new seal must supersede the old one** | **`write_seal` refuses (`O_EXCL`), so route A′ has no defined supersede behaviour yet — this is the open fork** | `write_seal:429`, `acceptance_defect.supersede` |

E7 is the only case A does not answer. It needs one decision about the seal's storage shape:

- **A′-1 — per-seal immutable files keyed by the revision they name, plus one authority-owned pointer.**
  `write_seal` keeps its `O_EXCL` guarantee for the store; supersession appends a new immutable seal and
  atomically replaces a private pointer file under the workspace lock. Keeps every seal ever minted as the
  audit trail (`supersedes_sha256` chain becomes readable), costs one small authority write (atomic
  `rename` of a pointer, no new intent kind, no new recovery branch: a pointer naming a missing seal file
  is `CORRUPT_STATE`).
- **A′-2 — one mutable private slot replaced atomically on supersede.** Fewest moving parts, but the
  previous seal disappears, so the `supersedes_sha256` chain cannot be walked and a reviewer cannot see
  what was superseded.
- **A′-3 — seal inside the tracked tree, as part of its own revision.** Self-describing and revision-
  proven, but it needs a second publish immediately after the install (a new state the model must
  explain), and it puts the custody artifact inside the directory the coder's tools can reach.

## Verdict

Route A is **optimal in shape** — no new durable intent kind, no new recovery branch, and the window it
leaves ("installed but unsealed") is closed by a single admission gate that requires the seal. It is only
correct with **C1** (seal in private metadata) and **C2** (revision pin at admission, content checks
thereafter), and it is **incomplete on E7** until the storage shape is chosen. Option C from the earlier
comparison (`INSTALLED_UNSEALED` record) fixes none of C1/C2/E7: it adds a fifth intent kind and a full
recovery matrix without changing where the seal lives or how it stays valid.

## Resolution (operator, 2026-11-20)

**Q-V2-BOOT-1 = A′ = route A + C1 + C2 + storage shape A′-1.** Ratified as **D-V2-5** in the linked V2
plan. The shape, stated so no slice has to re-derive it:

1. The acceptance closure is installed as part of the project bundle, so it is inside the revision the
   install receipt names and no harness write ever adds to `worklogs/<slug>/acceptance/` afterwards.
2. The seal is minted from the installed bytes + plan bytes + receipt revision and stored under
   **authority-private metadata** as an immutable per-seal file named by the revision it names; one
   private pointer names the seal in force and is replaced by atomic rename under the workspace lock.
   `write_seal`'s `O_EXCL` guarantee therefore stands for every stored seal, and supersession appends
   rather than overwrites, so `supersedes_sha256` stays walkable for review.
3. Coder admission requires: pointer present, seal loadable, `verify_plan(plan_bytes)`,
   `verify_sealed_root(<root>/worklogs/<slug>/acceptance)`, and `verify_revision(seal, receipt_revision)`
   where the receipt revision is `current` at that moment. Nothing later re-consults the revision pin.
4. Recovery: pointer absent → mint deterministically from the installed bytes (byte-identical to the
   clean-run seal); seal file present but unloadable → **hard error**, never a silent re-mint; pointer
   naming a missing file → `CORRUPT_STATE`.
5. Replan: the planner's `correct`/`supersede` path appends the new seal and swings the pointer; the old
   seal file stays on disk as the previous rung of the chain.
