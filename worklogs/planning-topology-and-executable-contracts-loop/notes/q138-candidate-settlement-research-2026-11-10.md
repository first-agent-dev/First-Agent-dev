# Q138 research — what the settlement predicate is actually for

**Question.** May `_has_unsettled_views` count an unsettled CANDIDATE view as
blocking owner release? (Raised E509; Q114 decided the *policy*, this research
asks what the *mechanism* should be and whether the current code is wrong.)

**Answer, up front.** `access != READ` is **not a bug**. It is the normative
§2.1 release rule, and it is correct for every READ view the system has today
except one. The defect is narrower than E509 stated: CANDIDATE is the only READ
view that owns uncommitted writer-private state, and the predicate classifies it
by a property (`access`) that happens to be false for it. Everything else about
the current behaviour follows the spec.

## 1. What the code we would change is for

`_settled` (`workspace.py:1813`) is the single barrier that answers one question:
*may this workspace be handed to another writer?* It is shared by three
operations — `release_writer` (`:1747`), `release_unused_writer` (`:1736`) and
`handoff` (`:1774`). It checks two things: `_has_unsettled_views` and the presence
of `intent.json`.

Spec §2.1 release row (`i03-execution-workspace-spec-2026-10-15.md:168`), which
the spec calls the SOLE wire-shape authority, says exactly:

> every **WRITE** view is `PUBLISHED` or `REJECTED`, none is `OPEN`/`STOPPING`/
> `UNKNOWN`, and no `intent.json` exists. … READ release cannot revoke another
> actor.

So the predicate is scoped to WRITE views **by design**. A READ view does not
block release, and that is right for `PROJECT`/`VERIFICATION` read pins: they are
read-only, they hold `operation_ids` only when an EXEC ran, and releasing the
writer while a reader pin lives is the intended behaviour (the pin is revoked
separately by `release_reader`, `:2335`, which refuses while `operation_ids` is
non-empty, `:2351`).

The compiler text at `:1841–1846` also matches the spec, not the reverse: it
justifies keeping `SEALED` unsettled as *unfinished publication*, i.e. a WRITE
concept.

## 2. Why CANDIDATE is the exception, and why it is a category error

| purpose | access | owns writer-private uncommitted bytes? |
| --- | --- | --- |
| PROJECT (READ pin) | READ | no |
| VERIFICATION | READ | no |
| CANDIDATE | READ | **yes** — `write_candidate` (`:2785`) stages a whole plan body, and an in-flight `publish_candidate_plan` is *unfinished publication* with exactly the meaning `:1843` gives to `SEALED` |

So the invariant the code intends is not "access is WRITE" but **"this view owns
uncommitted, writer-private state"**. CANDIDATE satisfies the second and not the
first, because its `READ` access exists for a different reason: it is how the
authority keeps the ordinary file-write path (`write_file`) away from the buffer,
so the buffer can only be written through the purpose-bound `write_candidate`.

That is the whole defect. Nothing about `access` needs to change; the predicate
needs to stop using access as a proxy for ownership.

## 3. What actually breaks today, stated precisely

E509's probe is reproduced: an indeterminate candidate PUBLISH leaves
`CANDIDATE/READ/STOPPING` with private bytes while `workspace.json` is
`AVAILABLE`, and the next claim advances `generation`, which makes
`_closed_candidate_reader`'s check (`:4023`) reject the orphan forever.

Two things must be said about severity, and E509 over-weighted the first and
under-weighted the second:

1. **The bytes are already durable, but the outcome is not knowable.** Q114 is
     explicit: "do not assert that uncertainty means unchanged PLAN". After the
     orphan is stranded, whether the PLAN moved is still true on disk and still
     answerable by the committed tree — but nothing in the system asks, because
     the only caller that knew the view is gone.
2. **The writer is released while a writer-owned artifact is unsettled.** That
   is the actual invariant violation, and it is the same one the author already
   refuses for `SEALED` on a WRITE view. The consequence is not data corruption;
   it is an unrecoverable, unattributable private buffer plus an unanswerable
   question about who publishes next.

## 4. Why the "obvious" fix is not obvious

- **Not `access = WRITE` for CANDIDATE.** It would make the existing predicate
  cover it for free, but it also puts the view on the ordinary WRITE dispatch
  path, where `write_file` is reachable. The buffer's whole protection is that
  its view is not a file-write view. Rejected.
- **Not "count every view".** It would break the documented READ-pin release
  behaviour (§2.1) and strand legitimate reader pins. Rejected.
- **Not a new wire operation or a second writer.** Q114 forbids both, and §1315
  forbids retrying an indeterminate acquisition, while permitting reconciliation
  of a known operation.
- **The repair must also retire the orphan view, not just settle the
  publication.** Under a fence, a workspace whose reconciliation succeeds but
  whose orphan record stays `STOPPING` would be fenced forever — turning a leak
  into a permanent `WORKSPACE_BUSY`. This is the detail that makes "fence only"
  insufficient and is why the two halves must ship together.

## 5. The mechanism that satisfies all of it, with no wire change

The authority already provides everything reconciliation needs; none of it is
new:

- `publish_candidate_plan` accepts **any** `STOPPING` CANDIDATE view of the same
  generation and actor (`:4000–4040`), not one particular view id.
- The operation journal answers a **repeat of the same request id** from its
  completed-reply cache (`journal.py:332–349`; `backend.py:340–343` reads
  `record["view_ref"]`, so even a lost `CREATE_VIEW` reply is recoverable by
  re-sending its id). `composition._control` (`:410–430`) already relies on this.
  **But that cache is process-local, bounded, and explicitly not durable**
  (`supervisor.py:159–168`: "no eviction/recovery/serialization"), and a missing
  entry becomes `EXECUTION_UNKNOWN` (`:379–386`). Replay is therefore a
  best-effort reconciliation that holds for a lost *transport* reply inside one
  supervisor process — it is not a durable proof, and it is exactly why the
  fence is needed alongside it.
- `_already_published` (`:4061–4091`) answers a repeat from the committed tree
  when the bytes are already there; `_settle_view` (`:4591`) is explicitly
  idempotent and is what makes a view releasable.

Therefore: **store the pending publication on `ManagedExecution` — the four
request ids, the view ref and grant, source and candidate — and reconcile by
re-sending the same ids.** That settles the orphan view (PUBLISHED) instead of
leaking it, completes or proves the commit, and needs no second view, no new
verb, no retry of an *indeterminate acquisition* (the operation is known, its id
is known, and §1315 forbids retrying the *acquisition decision*, not replaying a
journaled request).

Process death stays fenced without any predicate change at all: `_load` turns
`OWNED` into `QUARANTINED` on the next start (`:1358–1360`), which is exactly the
Q114 answer. **So the fence is not needed for the process-death case — it is
needed for the in-process case where `close()` would otherwise pass, and for the
case where the reply cache no longer holds the entry.**

This also bounds what reconciliation can promise: because the reply cache is not
durable, a replay is only available while the same supervisor process still holds
the completed reply. Reconciliation is therefore "complete the ordinary case and
prove it", never "guarantee recovery" — which is precisely the Q114 wording that
process death leaves the workspace unavailable for recovery.

## 6. Consequence for the decision

Two independent halves, and they can be chosen separately:

- **Handle + same-id replay** (no authority change). Recovers the ordinary
  indeterminate case, settles the orphan, and prevents the specific E509
  reproduction *provided* `close()` refuses while a publication is pending.
- **Fence** (authority change, one predicate). Covers the case where
  reconciliation itself cannot run — e.g. the run crashes between receiving the
  error and storing the handle, or reconciliation is refused. Without it,
  `close()` can still be reached with an unsettled CANDIDATE view.

The scope question the operator must answer is not technical: **the authority
cannot distinguish a managed run from legacy direct `fa workflow`** — both reach
`publish_candidate_plan` through the same client and both release through
`_settle_owner`. A predicate change therefore fixes legacy behaviour too, which
Q114 currently says not to touch in this scope ("its observed orphan-view
behaviour remains an R25 acceptance gap, not an approved policy"). That is the
one genuine blocker: it needs an explicit scope authorization, not a design.

## 7. Checks run

- Predicate and its three callers read in source; spec §2.1 row read verbatim.
- Journal replay path read (`journal.lookup`, `backend.execute`), including that
  the cached reply carries `view_ref`.
- `_already_published` / `_plan_parts` read: replay preserves
  `path`/`source_kind` and hashes the staged buffer, so the client's
  `expected_ref` comparison (`client.py:582`) succeeds on an exact repeat.
- Probe from E509 reproduced (indeterminate → `AVAILABLE` + `STOPPING`; determinate
  refusal → `REJECTED`), then reverted; tree clean.
- No test currently codifies the orphan-as-desired behaviour (grep for
  uncertainty + `AVAILABLE` finds only unrelated EXEC-code tests).
