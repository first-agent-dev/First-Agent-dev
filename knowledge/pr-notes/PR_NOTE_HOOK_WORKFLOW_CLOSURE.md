# PR Note: Hook workflow closure — bootstrap reliability, seat boundaries, and model-freedom control

**Intent:** CHORE  
**Date:** 2026-06-28  
**Scope:** `justfile`, `src/fa/hygiene/hooks/`, `src/fa/hygiene/pr_intent.py`, `tests/`, `knowledge/`

## Problem

The original hook-workflow patch fixed the first-order bootstrap problem, but deeper review against the live branch exposed several additional issues that blocked this topic from being production-ready.

First, the new `pre-commit` hook claimed it would auto-restage hook-made autofixes and retry once, but the implementation placed `uv run pre-commit run "$@"` under `set -e` without wrapping it in a conditional. A non-zero exit terminated the script before the retry branch could run, so the flagship UX improvement was dead code.

Second, the M-6 PR-intent hook seat still applied the rich `INTENT / INVARIANT / FIX-only` metadata discipline too broadly. The semantic core itself is correct and valuable — the same validator powers `pr.prepare` and `IntentGuard`, which is exactly the seat where the model's degrees of freedom should be closed. But the `commit-msg` adapter still blocked ordinary human manual commits unless they used project-specific uppercase prefixes. That was the wrong boundary: hook seat should be fast local feedback, while the strict anti-cheap-workaround contract belongs primarily to `pr.prepare` + `PrDraftStore` + `IntentGuard` at runtime.

Third, the operational layer around the hooks was not yet trustworthy enough. The accepted bot fixes reintroduced a `RuntimeWarning` on `python -m fa.hygiene.hooks.install`, left real test failures behind, `hooks-status` could report success even for non-executable hooks on POSIX, and installer/status were not git-worktree-safe because they assumed `.git/` was always a directory rather than a file pointing at a worktree gitdir. A follow-up review also found two correctness gaps: the new `pre-commit` retry path discarded non-1 exit codes (`127`, `130`, etc.), and the pure-Python hook-dir resolver ignored `core.hooksPath` even though Git itself resolves hooks through that configuration via `git rev-parse --git-path hooks`.

This PR closes those gaps while preserving the strong semantic core of the model-freedom-control system.

## Changes

### `src/fa/hygiene/pr_intent.py`

- **Preserved the strict semantic core** — `validate_commit_msg(...)`, `validate_test_edits(...)`, FIX-only fields, citation resolution, and anti-tautology checks were deliberately **not** weakened globally because they are reused by `pr.prepare` and `IntentGuard`, the real anti-cheap-workaround runtime seat.
- Added `has_pr_intent_headers()` — a detector for **any** PR-intent metadata header (`INTENT:`, `CLASS:`, `INVARIANT:`, `TEST-EDITS:`, `DEGREE-OF-FREEDOM CLOSED:`, `DETERMINISTIC MECHANISM:`). This closes the subtle hole where a partial malformed metadata block (for example a lone `INVARIANT:` line) could otherwise be treated as an ordinary manual commit.
- Narrowed `_cli_validate()` only at the **hook adapter layer**: if a commit message contains **no PR-intent metadata headers at all**, it is treated as an ordinary human/manual commit and allowed through. If **any** metadata header is present, the full strict validator runs. This keeps the semantic core strong while fixing the seat boundary.
- Kept the existing git-generated-message skips (`merge`, `cherry-pick`, `revert`, `amend`) unchanged.

### `src/fa/hygiene/hooks/pre-commit`

- Rewrote the control flow so retry actually runs under `set -e`. The first `uv run pre-commit run` now executes in an explicit conditional instead of a straight-line command that aborts the shell before `rc=$?` / retry logic.
- **Critical safety change:** the retry path no longer uses dangerous global `git add -u`. Instead, it snapshots the staged path set before the first run, detects which of those already-staged paths were modified by hook autofix, and re-stages **only that subset** before retrying once. This avoids accidentally staging unrelated user changes.
- Follow-up correctness fix: the hook now preserves the **real failing exit code** when no retry happens, and the retry failure code when the second run still fails, instead of flattening everything to `1`.
- The script still sets `NO_PROXY="*"` for the isolated pre-commit env path and still uses `uv run` so Windows/PowerShell uv-managed environments work.
- The tracked file mode for `src/fa/hygiene/hooks/pre-commit` is corrected to executable (`100755`) in the patch, removing the need for installer-induced source-mode repair in a clean checkout.

### `src/fa/hygiene/hooks/_util.py`

- Expanded from “workspace + scripts dir” helpers into the shared operational substrate for hook infrastructure.
- Added canonical `HOOK_NAMES` here so `hooks/__init__.py` no longer needs to import `install.py` at package import time.
- Added `resolve_git_dir()` with support for:
  - normal checkouts (`.git/` directory),
  - hook-time `GIT_DIR` env var,
  - git worktrees (`.git` file with `gitdir: ...`).
- Added `resolve_hooks_dir()` that resolves to the **effective hooks directory**. In worktrees this means following `commondir` and landing in the common hooks dir Git actually uses.

### `src/fa/hygiene/hooks/__init__.py`

- Reworked the package export path so it keeps explicit `__all__` exports **without** reintroducing `RuntimeWarning` on `python -m fa.hygiene.hooks.install` / `status`.
- `HOOK_NAMES` now comes from `_util.py`, while `install_hooks` and `check_hooks` remain lazy wrappers to avoid importing the target execution module too early.

### `src/fa/hygiene/hooks/install.py`

- Switched from local `HOOK_NAMES` / direct `.git/hooks` assumption to the shared `_util.py` helpers.
- Installer now resolves the **real hooks dir** via `resolve_hooks_dir()`, asking Git first through `git rev-parse --git-path hooks`. This makes install work in normal clones, git worktrees, and local `core.hooksPath` setups instead of assuming a hard-coded `.git/hooks`.
- Kept the symlink-preferred / copy-fallback behavior and the best-effort executability repair on source + target.

### `src/fa/hygiene/hooks/status.py`

- Switched to the shared `HOOK_NAMES` and `resolve_hooks_dir()` helpers, making the status probe work in both normal clones and git worktrees while respecting `core.hooksPath` the same way Git itself does.
- Status now verifies not just presence/content freshness, but also **executability** on POSIX. A hook that exists and matches source but lacks execute bits is now reported as unhealthy instead of incorrectly “active”.
- Status messages now distinguish missing, stale, and non-executable cases.

### `justfile`

- `install` still performs `uv sync --extra dev` and `install-hooks`, but now also runs **`just hooks-status` before printing success**. This makes bootstrap fail-fast instead of optimistically reporting “all hooks active” after a partial install.
- The success banner remains, but now reflects a verified state rather than a best-effort assumption.

### `tests/test_hygiene_hooks_install.py`

- Repaired the broken import refactor from the accepted bot patch (`install_mod` NameErrors).
- Added tests for **worktree hook-dir resolution** in both installer and status paths.
- Added a test proving that non-executable installed hooks are unhealthy on POSIX.
- Added regression tests for `python -m fa.hygiene.hooks.install` / `status` to ensure no `RuntimeWarning` is emitted.
- Added shell-level regression tests for the new `pre-commit` retry path:
  - hook-modified staged file is re-staged and retried,
  - unrelated unstaged files are **not** staged by the retry logic.

### `tests/test_pr_intent_snapshot.py`

- Replaced the old expectation that “headerless normal commit must be blocked”. The hook-seat contract now explicitly allows ordinary manual commits with no PR-intent headers.
- Added tests for `has_pr_intent_headers()` and for the partial malformed metadata case (`INVARIANT:` without `INTENT:`) to ensure that such commits still route through strict validation and fail, rather than silently passing as ordinary manual commits.
- Kept all strict semantic-core tests intact: enum shape, invariant prefixes, FIX clauses, citation resolution, tautology checks, and `TEST-EDITS` logic.

### `knowledge/ci-guardrails-reference.md`

- Layer 3 (“git-hook seat”) rewritten to describe the **actual seat boundary** after the fix:
  - ordinary manual commits with **no** PR-intent headers are allowed,
  - any explicit metadata block is still strictly validated,
  - `pre-commit` now re-stages only the modified staged subset and retries once,
  - `hooks-status` now checks for non-executable hooks too.
- This keeps the human-facing guardrail documentation coherent with the runtime semantics now in code.

### `knowledge/codemaps/model-freedom-control-runtime-pipeline.md` (new)

- Added a production-grade codemap for the whole “система управления степенью свободы модели” surface.
- Covers:
  - component inventory,
  - seat separation,
  - catalog of freedom-closing mechanisms,
  - traces for contract → semantic core, human hook seat, `pr.prepare`, `PrDraftStore`, `IntentGuard`, `bash_intent`, and hook bootstrap infrastructure,
  - data-flow diagram,
  - freedom-closure matrix,
  - important asymmetries,
  - known limitations and high-ROI follow-up improvements.
- The codemap was reviewed once more against the real code after landing these changes and updated for coherence (for example, clarifying that `prepare-commit-msg` is a narrow/non-skipped prefill seat rather than a universal prefill layer).

## What this PR intentionally preserves

This PR **does not** flatten the whole design into a soft human-only workflow.

It intentionally preserves:

- `validate_commit_msg(...)` as a strict shared semantic core;
- `validate_test_edits(...)` as the same anti-test-gaming rule at hook and runtime seats;
- `pr.prepare` as the explicit producer of intent/invariant/work-log state;
- `PrDraftStore` as the current-session trust boundary;
- `IntentGuard` as the primary runtime mutation gate.

In other words: the **runtime seat stays strict**; only the human hook seat becomes narrow enough not to punish ordinary manual commits.

## What this PR still does NOT do

Per scope discipline, this PR still does **not**:

- block `git commit --no-verify` for the agent path — this remains a backlog / future hardening topic, to be handled at runtime / sandbox / CI level if real misuse is observed;
- introduce a dedicated first-party agent commit tool (`git.commit_prepared` or similar) — that remains a high-ROI follow-up, not a prerequisite to fixing this PR;
- make `prepare-commit-msg` explicit opt-in by env flag. The current narrower skip logic is sufficient for this iteration; an explicit opt-in prefill policy is a future refinement if wanted.

## Acceptance criteria

1. Hook bootstrap is deterministic and verified: `just install` succeeds only when all hook seats are actually healthy.
2. `pre-commit` auto-restage/retry path works under `set -e` and does **not** stage unrelated changes.
3. Ordinary manual commits with **no** PR-intent metadata headers are not blocked by the hook seat.
4. Partial malformed metadata blocks do **not** silently pass — they still trigger strict validation.
5. `pr.prepare` + `PrDraftStore` + `IntentGuard` remain the primary anti-cheap-workaround runtime seat.
6. Hook installer/status work in both normal clones and git worktrees.
7. `hooks-status` detects missing, stale, and non-executable hooks correctly.
8. No `RuntimeWarning` on `python -m fa.hygiene.hooks.install` or `status`.
9. The touched test surface is green.
10. `pre-commit` preserves operator-relevant non-1 exit codes instead of masking them.
11. Installer/status honor `core.hooksPath` and git-worktree hook resolution.
12. The new codemap accurately reflects the implementation after a follow-up code review.

## Verification results on the reviewed branch state

Verified against branch head `92dabcb5e16fa2916dee86b2ad411a2cdef95d6f` plus the changes in this patch:

- `uv run pytest -q tests/test_hygiene_hooks_install.py tests/test_pr_intent_snapshot.py tests/test_prepare_pr.py tests/test_intent_guard.py tests/test_cli.py tests/test_test_edit_protection.py` → **191 passed**
- `uv run python -Wdefault -m fa.hygiene.hooks.install --help` → **no RuntimeWarning**
- `uv run python -Wdefault -m fa.hygiene.hooks.status` → **no RuntimeWarning**
- manual checks confirmed:
  - no-header manual commit path allowed,
  - partial metadata block still denied,
  - worktree install/status path works,
  - hooks-status rejects non-executable hooks on POSIX,
  - installer/status succeed on a git worktree by resolving the common hooks dir.

## Refs

- Rigorous branch analysis: `pr46-rigorous-code-analysis-2026-06-28.md`
- Updated implementation plan: `pr46-updated-plan-ready-for-implementation-2026-06-28.md`
- ADR-11-I6: hook seat is bypassable, CI is authority
- ADR-10 I-1: single validator across git hook / middleware / `pr.prepare`
- Codemap: `knowledge/codemaps/model-freedom-control-runtime-pipeline.md`
