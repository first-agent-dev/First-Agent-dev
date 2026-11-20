# Q138 research — what the settlement predicate is actually for

**Question.** May `_has_unsettled_views` count an unsettled CANDIDATE view as
blocking owner release? (Raised by E509; Q114 decided the *policy*, this asks what
the *mechanism* should be and whether the current code is wrong.)

**Answer, up front.** `access != READ` is **not a bug**. It is the normative §2.1
release rule and it is correct for every READ view the system has today except
one. The defect is narrower than E509 stated: CANDIDATE is the only READ view that
owns uncommitted, writer-private state, and the predicate classifies it by a
property (`access`) that is false for it for an unrelated and deliberate reason.

## 1. What the code we would change is for

`_settled` (`workspace.py:1813`) is the single barrier answering one question:
*may this workspace be handed to another writer?* Three operations share it —
`release_writer` (`:1747`), `release_unused_writer` (`:1736`) and `handoff`
(`:1774`) — and it checks exactly two facts: `_has_unsettled_views`, and whether
`intent.json` exists.

Spec §2.1's release row, which the spec calls the SOLE wire-shape authority
(`i03-execution-workspace-spec-2026-10-15.md:168`), says:

> every **WRITE** view is `PUBLISHED` or `REJECTED`, none is `OPEN`/`STOPPING`/
> `UNKNOWN`, and no `intent.json` exists. … READ release cannot revoke another
> actor.

The predicate is therefore scoped to WRITE views **by design**. A READ view does
not block release, and that is right for the `PROJECT`/`VERIFICATION` pins the
system actually creates: they are read-only, hold `operation_ids` only when an EXEC
ran, and releasing the writer while a reader pin lives is intended (the pin is
revoked separately by `release_reader`, `:2335`, which refuses while
`operation_ids` is non-empty, `:2351`). Counting every view would fence legitimate
reader pins.

## 2. Why CANDIDATE is the exception

| purpose | access | owns writer-private uncommitted bytes? |
| --- | --- | --- |
| PROJECT (READ pin) | READ | no |
| VERIFICATION | READ | no |
| CANDIDATE | READ | **yes** — `write_candidate` (`:2785`) stages a whole plan body, and an in-flight `publish_candidate_plan` is unfinished publication with exactly the meaning `:1843` gives to `SEALED` |

The invariant the code intends is not "access is WRITE" but **"this view owns
uncommitted writer-private state"**. CANDIDATE satisfies the second and not the
first, because its READ access exists for a different job: keeping the ordinary
`write_file` path off the buffer, so the buffer is writable only through the
purpose-bound `write_candidate`. That is the whole defect — no access needs to
change; the predicate needs to stop using access as a proxy for ownership.

## 3. What actually breaks, stated precisely

E509's probe reproduces: an indeterminate candidate PUBLISH leaves
`CANDIDATE/READ/STOPPING` with private bytes while `workspace.json` is
`AVAILABLE`, and the next claim advances `generation`, after which
`_closed_candidate_reader` (`:4023`) rejects the orphan forever.

E509 over-weighted one half of this and under-weighted the other:

1. The bytes are durable; the *outcome attribution* is what is lost. Q114 is
   explicit that uncertainty must not be read as "PLAN unchanged". After the
   orphan is stranded, whether the PLAN moved is still answerable from the
   committed tree — but nothing asks, because the only caller that held the view
   is gone.
2. The writer is released while a writer-owned artifact is unsettled. That is the
   real invariant violation, and it is the same condition the author already
   refuses for `SEALED` on a WRITE view. The consequence is an unrecoverable,
   unattributable private buffer and an unanswerable ownership question for the
   next publisher — not silent corruption.

## 4. Why the obvious fixes are wrong

- **`access = WRITE` for CANDIDATE.** Would make the existing predicate cover it
  for free, but puts the view on the ordinary WRITE dispatch path where
  `write_file` is reachable. The buffer's protection *is* that its view is not a
  file-write view. Rejected.
- **Count every view.** Breaks documented read-pin release (§2.1) and strands
  legitimate reader pins. Rejected.
- **A new wire operation or a second writer.** Q114 forbids both; §1315 forbids
  retrying an indeterminate *acquisition*, while permitting reconciliation of a
  known operation.
- **Fence only.** A workspace whose reconciliation succeeds but whose orphan
  record stays `STOPPING` would be fenced forever — converting a leak into a
  permanent `WORKSPACE_BUSY`. This is why the fence and the retirement of the
  orphan must ship together.

## 5. The mechanism that satisfies all of it, with no wire change

The authority already provides everything reconciliation needs:

- `publish_candidate_plan` accepts **any** `STOPPING` CANDIDATE view of the same
  generation and actor (`:4000–4040`), not one particular view id.
- `_already_published` (`:4061–4091`) answers a repeat from the committed tree
  when the bytes are already there, and `_settle_view` (`:4591`) is explicitly
  idempotent — it is what makes a view releasable.
- A repeat of the same request id is served from the completed-reply cache
  (`journal.lookup`, `journal.py:332–349`; `backend.py:340–343` proves
  `record["view_ref"]`). **But that cache is process-local, bounded and
  explicitly not durable** (`supervisor.py:159–168`), and a miss becomes
  `EXECUTION_UNKNOWN` (`:379–386`). Replay is therefore a best-effort
  reconciliation that holds for a lost *transport* reply inside one supervisor
  process — not a durable proof, and precisely why the fence is still needed.

So: **store the pending publication on `ManagedExecution` — the four request ids,
the view ref and grant, source and candidate — and reconcile by re-sending the
same ids.** That settles the orphan view (`PUBLISHED`) instead of leaking it,
completes or proves the commit, and needs no second view, no new verb, and no retry
of an indeterminate acquisition (the operation and its id are known).

Process death stays fenced with **no predicate change at all**: `_load` turns
`OWNED` into `QUARANTINED` on the next start (`:1358–1360`), exactly the Q114
answer. The fence is needed only for the in-process case where `close()` would
otherwise pass, and for when the reply cache no longer holds the entry.

## 6. Consequence for the decision

Two independent halves, separable:

- **Handle + same-id replay** (no authority change): recovers the ordinary
  indeterminate case and retires the orphan, provided `close()` refuses while a
  publication is pending.
- **Fence** (one predicate): covers the case where reconciliation cannot run.

The scope question is not technical. **The authority cannot distinguish a managed
run from legacy direct `fa workflow`** — both reach `publish_candidate_plan`
through the same client and release through the same `_settle_owner`. A predicate
change therefore changes legacy behaviour, which Q114 currently forbids in this
scope ("its observed orphan-view behaviour remains an R25 acceptance gap, not an
approved policy"). That, and only that, is the genuine blocker.

## 7. Checks performed

- Predicate and its three callers read in source; spec §2.1 release row read
  verbatim.
- Journal replay path read, including that the cached reply carries `view_ref`
  and that the cache is not durable.
- `_already_published` / `_plan_parts` read: replay preserves `path`/`source_kind`
  and hashes the staged buffer, so the client's `expected_ref` comparison
  (`client.py:582`) succeeds on an exact repeat.
- E509's probe reproduced and reverted; tree clean.
- No test currently codifies the orphan-as-desired behaviour.
