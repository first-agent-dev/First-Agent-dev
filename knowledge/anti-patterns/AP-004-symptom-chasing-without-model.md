---
compiled: 2026-06-26
applies_to:
  - "Any LLM-driven fix session touching infrastructure code (Docker, bash, CI)"
  - "AGENTS.md §Industry-proven rules (rule 5 — this anti-pattern)"
status: accepted
evidence: commits 8806c4e, 98d1e6e, 4fc418b, b08f1ee, 61ec8bf, d324416, f8ea975
---

# AP-004 — Symptom-chasing without a runtime model

> Fix after fix, each correct in isolation, each creating the next bug.
> The chain stops only when someone reads the tool's documentation
> and chooses the right abstraction.

## Symptom

An LLM agent is asked to fix a runtime failure in infrastructure code
(Docker entrypoint, deploy script, CI workflow). The failure message
is clear ("Permission denied", "dubious ownership", "cross-device link").
The agent produces a fix that addresses the exact error message. CI or
the operator runs it. A new, different error appears. The agent fixes
that one. Another appears. The cycle repeats 3-8 times.

Each individual fix is technically correct for the error it addresses.
The chain persists because the agent never builds a model of the full
runtime environment — it reacts to error messages one at a time.

## Worked history (FA, June 2026)

**Task:** Clone a git repo from a read-only bind mount (`/repo`) into a
writable bind mount (`/sessions/<id>`) inside a Docker container running
as uid 1000 on a read-only rootfs.

**8 commits over 3-4 hours. 5 different fix approaches tried.**

| # | Commit | Error addressed | Fix | New error created |
|---|--------|----------------|-----|-------------------|
| 1 | `8806c4e` | Dirty worktree blocks fa-update | Auto-commit traces before pull | Local commit diverges from origin → ff-only fails |
| 2 | `98d1e6e` | (workspace isolation feature) | `git clone --local /repo` | Permission denied + .gitconfig read-only + cross-device hardlink |
| 3 | `b08f1ee` | .gitconfig: read-only filesystem | `git -c safe.directory='*'` | `-c` flag doesn't apply to source-repo ownership check (git 2.36+) |
| 4 | `61ec8bf` | safe.directory not applied | `GIT_CONFIG_COUNT` env vars | Nested single quotes break inside `bash -c '...'` in CI YAML |
| 5 | `d324416` | Quoting in CI | Move GIT_CONFIG to `docker run -e` flags | cross-device hardlink still present |
| 6 | `f8ea975` | safe.directory still failing | `git config --system` in Dockerfile | cross-device hardlink (still using `--local`) |
| 7 | (pending) | cross-device link | `--no-hardlinks` flag | Would have worked, but was another patch on a patch |
| 8 | (pending) | all of the above | `git clone file:///repo` | **None.** Single change fixes both issues. |

**The root cause was in the git documentation the entire time:**

> When the repository is specified as a URL, `--local` is ignored
> (and we never use the local optimizations).

`file:///repo` (URL form) tells git to use the transport layer (pack
protocol over pipes). No hardlinks, no ownership check on the source
repo. Both classes of bugs vanish with one word change:
`/repo` → `file:///repo`.

## Why the wrong shape dominates

Three compounding factors:

1. **Error-message-driven fixing.** The agent reads "dubious ownership"
   → searches for "safe.directory" → applies the first result. Reads
   "cross-device link" → searches for "no-hardlinks" → applies that.
   Each search-and-patch cycle is locally correct but never questions
   why `--local` mode is being used at all.

2. **No runtime model.** The agent understands the Dockerfile, the
   compose file, and the entrypoint script individually — but does
   not build a model of: "this is a read-only rootfs, with two
   separate bind mounts from different host paths, running as a
   non-root user whose uid doesn't match the repo owner." Without
   that model, each error is a surprise.

3. **Unit tests pass.** Every fix passes `bash -n` (syntax), the
   existing test suite (which mocks paths), and sometimes even a
   new CI test (which had its own quoting bugs). The real failure
   surfaces only on the production server or in the Docker CI step.
   The feedback loop is: patch → push → wait for CI → read new error
   → patch again.

## Right shape

**Before writing any fix, build the runtime model.**

For Docker infrastructure, the model must answer:

- What user does the process run as? (uid, not name)
- Which filesystems are writable? Which are read-only?
- Which paths are bind mounts? From which host paths?
- Are the bind mounts on the same host filesystem?
- What owns the bind-mount source directories on the host?
- Does the tool being invoked (git, uv, python) have implicit
  behaviors that depend on filesystem features (hardlinks, ownership)?

With this model, the correct fix for "clone across two bind mounts as
non-root on read-only rootfs" is derivable from `man git-clone` in
one reading: use `file://` protocol to bypass local-filesystem
optimizations that assume same-device, same-owner access.

**The forcing function:** when an LLM agent produces a fix for a Docker
/ bash / CI failure, and the fix addresses only the error message text,
ask: "What is the runtime model? What user, what filesystems, what
mounts, what ownership?" If the agent cannot answer, the fix is
symptom-chasing.

## Detection

- **Commit-chain signal:** 3+ sequential fix commits to the same
  script/Dockerfile, each fixing a different error from the previous
  fix. The chain itself is the anti-pattern.
- **Error-message grep:** the commit message or PR description
  contains the error message text ("dubious ownership", "cross-device
  link", "Permission denied") but does not reference the tool's
  documentation or design rationale.
- **Missing model:** the fix does not state what user the process runs
  as, what filesystem permissions apply, or what the tool's implicit
  behavior is in the given environment.

## Linked

- [AP-003](./AP-003-shallow-fix-no-mechanism.md) — shallow fix without
  named mechanism. AP-004 is the infrastructure-specific variant: the
  "mechanism" is the tool's documented behavior in the runtime
  environment, not a code-level type or schema.
- [ADR-13](../adr/ADR-13-workspace-isolation.md) — the feature that
  triggered this anti-pattern chain.
- [workspace-isolation-research.md](../research/workspace-isolation-research.md)
  — recommended `git clone --local` without testing cross-device or
  cross-owner scenarios. The research was correct about the pattern
  (RO mount + per-session clone) but wrong about the mechanism
  (`--local` vs `file://`).
