# R24 step 3 — the caller cannot be wired yet: JUnit reports live on the host

Status: **blocker, escalated as Q142.** Steps 1–2 are committed (`238f75b`, `7e4dfcb`).

## What steps 1–2 actually delivered

`run_commands` can now be handed a substrate, and `ManagedVerifyCommandExecutor`
implements it over `ReadOnlyManagedBashExecutor` (pin_reader → READ view with a
private tmpfs `/scratch`). Both are behaviour-neutral for `executor=None`.

## Why the last wiring step does not fit

Wiring `verify_plan` to the managed executor looks mechanical — pass an executor
down from `WorkflowContext.managed_execution`. It is not, because the verification
*gate* is not just "run a command and look at the exit code". It needs the command
to leave an artifact **on the controller host**, and it reads it there:

| where | what it does | why a container breaks it |
|---|---|---|
| `slice_verification.py:709` | `tempfile.TemporaryDirectory(prefix="fa-verify-junit-")` | the JUnit XML is written by the command into a host temp dir |
| `:715–725` | `run_commands((NODEID_CAPTURE_COMMAND...))`, then `_parse_junit_report(report_path)` | the report is read back from the host path |
| `:1673` | `tempfile.TemporaryDirectory(prefix="fa-kill-junit-")` | same for every kill-check |
| `:1684–1686` | kill-check writes `--junitxml=` into that host dir, then parse | same |
| `:555–565` | `_existing_test_paths` uses `(Path(root) / path).exists()` | decides what to run from the **host** tree, not the revision |
| kill/overlay path | copies source roots into a host overlay | the overlay is host state |

So the substrate seam is necessary but not sufficient: a managed run would ask the
container to write `--junitxml=/tmp/fa-verify-junit-xxxx/results.xml` — a path that
does not exist inside the cell — and then read that host path for the verdict. The
command would fail or write nowhere, and the gate would record `ERROR` for every
slice. That is not a subtle degradation; it is a verify gate that can never pass.

`tempfile` appears exactly twice and `_parse_junit_report` reads are exactly five, so
the surface is small and enumerable — but every one of them is a *contract* decision,
not a plumbing detail.

## The three shapes of a fix

**A. Managed run collects evidence in-band.** The JUnit XML is emitted to stdout
inside the cell and parsed from `CommandResult.stdout_tail`. No host path at all.
Cheapest to wire; but the tail is bounded (`TAIL_LIMIT`), so a large report would be
truncated — and a truncated report is exactly the "not evidence" case the adapter
already refuses. Also changes what `stdout_tail` means for every existing caller.

**B. The cell writes the report into its private `/scratch`, and the controller
reads it back through the workspace port.** Evidence stays an artifact, the bound
stays honest, and `ClientWorkspacePort` already exists to read a pinned view. Costs a
new port method (read a path under scratch), and `/scratch` is a 64 MiB tmpfs that
must be sized for a real report.

**C. Verification runs on a MUTATION view instead.** Withdrawn already: `_MUTATION_ROOTS`
is the canonical source, so a verify run that writes fixtures would publish them.

**D. Keep the gate on the host and treat R24 as "only the substrate seam".** Honest
but does not answer the question R24 exists to answer: in a managed run the coder
edits a revision the controller host never sees, so a host-run verify gate is
verifying a stale tree.

## What I recommend

**B**, for the same reason Q140 chose C: it is the only option that keeps the
evidence a real artifact *and* keeps it inside the trust boundary the authority
already proves. A is a protocol change disguised as a convenience; D leaves the
managed gate meaningless.

The immediate next step under B is a scratch-relative report path plus one
read-back through the port — after which `verify_plan` gets the executor it now
accepts. Steps 1–2 are unaffected by the choice.
