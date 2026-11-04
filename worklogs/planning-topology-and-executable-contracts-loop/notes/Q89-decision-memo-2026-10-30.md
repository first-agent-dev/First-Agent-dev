# Q89 — decision memo, verified against the tree (2026-10-30)

> Drafted against `8b1cc95`. Every claim below was re-checked against source; two of the
> seven original objections were withdrawn after verification (see §Verification).
> Not committed to `arena/0c94ceb3-*`; this file lives on `arena/09bb32f6-*` for review.

## Verification of the seven points

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | `read_candidate` is unusable after `close_admission` | **CONFIRMED (blocking)** | `workspace.py:1739` — `_reader_proof` ends with `if pin.record["state"] != "OPEN": raise VIEW_CLOSED`; `_live_view` (`:2437`) adds `gate.closed`; `read_candidate` (`:2326`) → `_file_work` → both. |
| 2 | "One transaction" is impossible (non-reentrant mutex) | **WITHDRAWN — claim was wrong** | `workspace.py:932` — `self._mutex = threading.RLock()`; `_transaction` (`:993`) acquire/release. Nesting is legal, and `publish_plan` already holds the mutex for the whole operation, so "read inside the same transaction" is both legal and cheap. |
| 3 | `publish_plan` requires an OWNER grant; PUBLISH carries a view capability | **CONFIRMED (blocking)** | `_owner_only` (`:2720`) does `hmac.compare_digest(candidate.grant, capability)`. Grants are minted independently: owner `secrets.token_hex(32)` (`:1351`, `:1446`) vs view `secrets.token_hex(32)` (`:1555`, `:1693`, `:1973`). Wire PUBLISH passes `self._capability(request)` = view capability (`service.py:714`). |
| 4 | Widening `_COMMITTED` breaks `install_project` clients | **CONFIRMED** | `protocol.py:138` `_COMMITTED` shared by PUBLISH + INSTALL; `_object` requires every key with `additionalProperties: False`; `decode_reply` checks `_RESULT_CHECKS[operation]`; `_install_project` returns `asdict(InstallResult)` (5 fields, `publication.py:495`). |
| 5 | Threading the dispatcher's op id changes `revision_id` | **CONFIRMED** | `_plan_prepare` builds the manifest with `"operation_id"` (`:3472`) and `_derive_revision_id` hashes the whole canonical manifest (`:244`); the id currently derives from `base_revision`+`new_sha256`. E269 R2 requires the caller's own id in the reply. |
| 6 | A CANDIDATE view can never be sealed; the seal-equivalent must be named | **CONFIRMED (and structurally enforced)** | `_PURPOSE_MATRIX` (`:211`): CANDIDATE = READ + plan_required + scope_required. `_sealed_source` refuses a non-`_ProjectView`; `mark_sealed` (`:2627`) states "A READ pin is never sealable (D4)". `record_terminal` (`:2499`) checks `closed` but never waits for `gate.active` to drain. |
| 7 | The candidate path must add the base-equality check | **CONFIRMED** | `_plan_prepare` bases the new revision on `binding.current["revision_id"]`; the ordinary path adds the explicit check `state == "SEALED" and binding.current["revision_id"] != view_ref.base_revision → STALE_REVISION` (`:3741`). Nothing equivalent exists on the plan path. |

## Decision block

```text
### Q89 ruling (2026-10-XX, operator) — option 1 adopted with R1–R6

Option 1: Operation.PUBLISH stays singular; sealed_manifest_id becomes nullable and must be
null exactly when view_ref.purpose == CANDIDATE; the PUBLISH reply gains plan_ref (nullable,
non-null only for a plan publish). Option 2 rejected (splits plan truth across reply and
journal); option 3 rejected (second operation = second plan writer, undoes Q58/R3).

R1 — the candidate buffer is read inside publish_plan's existing transaction, by a
closed-view-tolerant primitive. `_reader_proof` refuses `state != OPEN`, so the public
`read_candidate` cannot run after close_admission. Use `_proof_only` + `_buffer_bytes`
(the `execution_identity` precedent, `_buffer_bytes` takes only the pin).

R2 — the caller is proved by the view grant; the ownership facts are unchanged.
`publish_plan` proves an OWNER grant today. Extract a binding-level entry point that keeps
`status == OWNED`, `active_actor == namespace` and the generation check, and replaces only
the capability proof.

R3 — `_COMMITTED` is not widened. PUBLISH gets its own reply constant; `InstallResult`
keeps its five fields, so `install_project` clients and `decode_reply` stay untouched.

R4 — the reply carries the dispatcher's operation id, which changes revision identity.
`_derive_revision_id` hashes the plan manifest including `operation_id`; every pinned
`rev-…` for plan publications must be regenerated, and no second content-hash idempotency
mechanism is added (exact replay is the supervisor journal's job, `supervisor.py:244-250`).

R5 — the CANDIDATE seal-equivalent is explicit: gate closed AND no active work AND
`terminal.json` present AND the buffer passes the existing I02 validators. `record_terminal`
does not drain, so publish must refuse while `gate.active` is non-empty.

R6 — the base equality check is added, not inherited: require
`binding.current["revision_id"] == view_ref.base_revision`, as the ordinary path does.
```

## Implementation order

| # | Change | Anchor | Bank |
|---|---|---|---|
| 1 | `sealed_manifest_id` nullable + cross-field rule | `protocol.py:126`, precedent `:313-319` | `test_execution_service.py` |
| 2 | PUBLISH-only reply constant with `plan_ref` | `protocol.py:138-166` | same + conformance |
| 3 | `_publish` branch on `view_ref.purpose` | `service.py:714` | `test_execution_service.py` |
| 4 | Binding-level entry point (view proof + `_buffer_bytes` + plan core + base check) | `workspace.py:3393`, `:3451` | `test_workspace_publication.py:2436+` |
| 5 | Seal-equivalent precondition for candidates | `workspace.py:2499` (`record_terminal`), `:2437` (`_live_view`) | new cases |
| 6 | Op-id threading + regenerate pinned revision ids | `workspace.py:3472` | whole publication bank |
| 7 | Delete `publish_plan_buffer` (live second writer) | `workflow_controller.py:2279`, `plan_promotion.py:183` | `test_plan_promotion*` |
