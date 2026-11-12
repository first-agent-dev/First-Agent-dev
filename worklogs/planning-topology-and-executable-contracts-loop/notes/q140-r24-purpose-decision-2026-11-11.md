# Q140 / R24: where does verified work actually run? (2026-11-11)

Second research pass, requested by the operator ("check again — maybe there is a
more logical path"). The first pass recommended "C then B (MUTATION view)". That
recommendation is **withdrawn**: this pass found that the system was already
designed for exactly this case, and B contradicts it.

## What changed the answer

Three facts, none of which the first pass had:

1. **The spec already names the mechanism, twice.**
   `i03-execution-workspace-spec:640` — "Read-only verification may write only its
   **private scratch**." `:806` — "A pin may support read-only cell execution on its
   retained source with **private scratch**; it cannot open a writable PROJECT view,
   mutate source, publish or inherit writer authority." So R24's target is not a
   new capability to design; it is a documented capability that was never wired.

2. **The authority already hands the reader a scratch that is not the source.**
   `execution_trusted` (`workspace.py:2965`) returns
   `(owner, source, scratch, cache, environment)` and already branches on
   `Access.READ` vs WRITE (`:2975`). The scratch path is a per-view trusted input,
   not something the caller chooses — `backend._validate_binding` refuses any path
   the authority did not admit (`backend.py:161–181`).

3. **The scratch is already isolated and already quota'd.**
   A read view gets `Tmpfs /scratch`, `size=READ_SCRATCH_BYTES` (64 MiB),
   `mode=1777,nosuid,nodev` (`profiles.py:161–166`, Q124-A), and the cell worker
   points `HOME`/`TMPDIR` at `/scratch/home` and `/scratch/tmp`
   (`cell_worker.py:39–42`). So "verification writes scratch" is not a new trust
   boundary — it is a tmpfs that never becomes a revision.

4. **MUTATION is the wrong tool for the job, on inspection.** `_MUTATION_ROOTS =
   {"src", "scripts"}` (`workspace.py:224`) confines its writes to the canonical
   source tree, which is precisely where a verify command must *not* write. B would
   let a test run dirty `src/`. Its scratch is the source tree.

## The options, compared

| | A: VERIFICATION gains write-bearing scratch | B: run verify on MUTATION | **C: read-only exec on a pin, private tmpfs scratch** |
| --- | --- | --- | --- |
| Contradicts the spec? | No — but invents a second mechanism beside the documented one | **Yes** — spec says a pin cannot open a writable view, and gives verify its own scratch | No — it *is* the documented mechanism (`:640`, `:806`) |
| Confines writes away from source? | Yes, if a scratch subtree is defined | **No** — mutation roots are the source tree | Yes: tmpfs `/scratch`, never a revision, 64 MiB cap |
| New trust boundary? | A new purpose/access combination in a pinned matrix | None | None: `execution_trusted` already returns a separate scratch |
| Work to do | widen matrix + write policy + tests | allow verify on MUTATION + accept source-tree writes | allow `EXEC` on a READ pin + `ManagedReadOnlyBashExecutor` + inject executor |
| Reviewability | matrix grows, duplicates a purpose | matrix unchanged, but the guarantee "verify cannot dirty src" is lost | matrix unchanged, guarantee strengthened |
| Failure mode if wrong | verify writes somewhere unexpected | **a test run mutates source** | verify runs, scratch fills → bounded ENOSPC |

The decisive column is "confines writes away from source": running a test suite
inside the tree it is judging is the one behaviour that makes verification
untrustworthy, because a test that writes a fixture into `src/` would pass and then
be published.

## What is actually missing, precisely

`ManagedBashExecutor.__init__` requires `access is Access.WRITE`
(`client.py:1059`). That single predicate is the whole gap, and it reads as
deliberate: the executor was written for a compiler that mutates. The authority is
*not* the blocker — `admit()` accepts a READ view's EXEC (`workspace.py:5555`) and
`_profile_for_record` already expects a READ view to use the non-interactive
profile (`:2943`). So the work is client-side and additive:

1. `run_commands` accepts an injected executor (Q140's "C" — a behavioural no-op).
2. A read-only executor variant that binds a READ view + the non-interactive
   profile, minting no session (a session is what `interactive` means;
   `admit()` requires `profile.interactive == (session_id is not None)`).
3. R24's caller passes that executor; the host `subprocess.run` stays the default
   for unmanaged runs, which is what "no host fallback" actually constrains — a
   *fallback* appears when a managed run silently reverts to the host, not when an
   unmanaged run never had a managed path.

## Recommendation (revised)

**C, in the spec's sense:** read-only cell execution on a VERIFICATION pin with its
private tmpfs scratch, behind an injected executor seam. Not B, and not A.

Ordering: the seam first (behavioural no-op, independently testable), then the
read-only executor (client-side predicate + profile choice), then the caller
one-liner, then a C1 through a real supervisor plus a negative proof that a verify
command's writes never reach a revision.

**One thing to confirm rather than assume:** whether the READ profile's
`max_command_ms` and image can host a test suite at all (it is a separate approved
profile, `profiles.py:204–206`). If the read profile is intentionally too small for
a full pytest run, then the honest answer is a *third* approved profile for
verification work — which is A's cost without A's matrix change, and should be
decided before the caller is wired.

## Q141 was decided by the operator (C)

Recorded here because it interacts: the operator chose "child coder writes only
inside an approved mutation root, project-level edits to the parent". That is
consistent with the above — MUTATION is the *coder's* confined write surface, not
verification's, and the two must not be conflated. Verification gets scratch;
mutation gets a confined source write; the parent publishes either.
