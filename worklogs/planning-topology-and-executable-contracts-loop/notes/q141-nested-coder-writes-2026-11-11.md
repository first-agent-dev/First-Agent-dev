# Q141: may a nested child's coder write project files? (2026-11-11)

The operator selected C ("child coder writes only inside an approved mutation
root, project-level edits stay with the parent") and asked me to compare it against
my A on criteria, with another round of research. I did that, and **C is right —
but for a stronger reason than the one it was chosen on.** This note records the
comparison and the finding, because the reason is what makes C enforceable rather
than merely narrow.

## The finding that decides it

A nested coder's *only* job is to revise the plan. On this substrate the plan does
not live in the project source at all:

- `plan_promotion._CANONICAL_PARENT = ("worklogs",
  "planning-topology-and-executable-contracts-loop", "increments")`
  (`plan_promotion.py:21`), enforced at `:43`.
- `_MUTATION_ROOTS = frozenset({"src", "scripts"})` (`workspace.py:224`), and
  `_purpose_write_policy` refuses any MUTATION write whose first path component is
  not in that set (`:2747–2748`).

Therefore **under C a nested coder cannot write the plan at all** — `worklogs/` is
outside its confinement, and the refusal is `PATH_DENIED` at the effect boundary,
not a convention. C is not "a narrower A"; it is a different claim: the child's
coder writes only implementation, and every plan edit is the parent's.

That inverts the usual objection to C ("the nested coder can't do its job"). The
nested coder's job, per the tool's own gate (`workflow_tool.py:400–402`,
`:611–616`), is the I03 *plan acquisition* path; publication is already the
controller's (`_promote_validated_plan`, `workflow_controller.py:2326`, via
`BoundPlanPublisher`). C matches the architecture that already exists.

## Criteria comparison

| Criterion | A — child coder writes project files through its own bound view | **C — writes only inside `src`/`scripts`; plan edits are the parent's** |
| --- | --- | --- |
| Q61 invariant ("controller alone validates and promotes"; "validated import") | Preserved, but the child's view becomes a second promotion surface that must re-prove every rule | Preserved exactly: the child never reaches `worklogs/`, so it cannot promote, and the parent still owns publication |
| Enforceability | Convention: the child *could* be granted more later | **Structural**: `PATH_DENIED` at `_purpose_write_policy`; a bad grant is refused, not discouraged |
| Blast radius of a bad child stage | Any project path | `src`/`scripts` only, and only inside its view |
| Plan integrity | Child could rewrite its own plan and self-approve | Impossible by construction |
| Detectability of a violation | Requires diff review | Refused before any effect; the refusal is a typed code |
| Reuse of existing machinery | Needs a new view purpose or a per-child PROJECT grant | Reuses MUTATION, already admitted, already confined, already tested |
| Consistency with R24 (this session) | Both surfaces widen | Verification gets *scratch*, mutation gets a *confined source write* — two distinct, non-overlapping surfaces |
| Cost to close | Child PlanRef acquisition + child publication authority | Child PlanRef acquisition only; publication stays where it already is |
| DoD reading ("no child project write on denial") | Implies writes on success | Reads naturally: writes are confined, never absent |
| Risk if the assumption is wrong | Child corrupts a plan it was supposed to be judged against | Nested coder may be too weak for plan-revision use cases — a *capability* gap, visible in tests, not a *safety* gap |

The row that decides it is enforceability: A's boundary lives in how grants are
issued (a policy choice that a future change can widen), while C's lives in
`_purpose_write_policy` (a predicate that refuses). For a security-shaped boundary,
prefer the one the code enforces.

## What must be stated positively, so C is not a silent limit

1. **Nested coder revisions are implementation-only.** A nested coder that needs to
   change the plan must return that need to the parent, which revises and
   publishes. This should be written into the R26 row, not inferred.
2. **The child's MUTATION view is seeded from the parent's current revision**, so
   the child sees the parent's committed work rather than a stale tree. Without
   this, C is safe but useless.
3. **Import is the parent's**: the child's view settles, and the parent decides what
   of it becomes a revision. C already makes the child unable to publish; the row
   should say who imports.
4. **`worklogs/` stays outside every mutation root deliberately.** That single fact
   is what makes C enforceable. If a future row wants a child to edit plans, it
   must be a new purpose with its own explicit decision — not a widened
   `_MUTATION_ROOTS`, which is shared by every MUTATION view.

## Residual question for the operator (small, not blocking)

Under C, does a nested **planner** also write only `src`/`scripts`? A planner that
must *draft* a plan has no legal write surface at all under C. Two coherent answers:

- **C1** — nested planners do not draft; they return analysis to the parent, which
  drafts and publishes (fully consistent with C, smallest change).
- **C2** — nested planners get CANDIDATE (plan-staging) rights, which is the one
  purpose that exists for drafting plan bytes and is deliberately not a project
  write.

I recommend **C1** for R26's first cut: it keeps one drafting surface (the parent)
and C2 remains available later without reopening C.

## Recommendation

Adopt the operator's **C**, recorded with the four positive statements above and
with the enforcement point named (`_purpose_write_policy`, `workspace.py:2747`).
Raise the planner sub-question as a comment on R26 rather than a new Q, since C1
and C2 are both consistent with C and neither changes its safety properties.
