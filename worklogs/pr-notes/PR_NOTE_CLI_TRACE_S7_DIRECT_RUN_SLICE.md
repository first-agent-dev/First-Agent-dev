# S7 — the direct `fa run` vertical slice (local half)

Rebased onto **`fc957f3`** ("s5"), the current origin main. Contains **S6,
S6.6 and S7**, plus three commits carried forward during the rebase (see
§Rebase note). S6's own note is
[`PR_NOTE_CLI_TRACE_S6_OBSERVABILITY_CONTRACTS.md`](./PR_NOTE_CLI_TRACE_S6_OBSERVABILITY_CONTRACTS.md).

Patches in `patches/` (sha256 in `patches/SHA256SUMS`):

* `S7-stack-from-fc957f3.patch` — `git am` format, preferred:
  `git am < patches/S7-stack-from-fc957f3.patch`
* `S7-stack-from-fc957f3.diff` — plain diff:
  `git apply patches/S7-stack-from-fc957f3.diff`

Verified by `git am` onto a pristine `fc957f3` worktree with the import root
confirmed inside it: **2227 passed, 14 skipped, 1 xfailed**.

**Status: complete-local / deployment-pending.** The container half is a
separate operator-run sheet — see §Deployment. Per the parent's §Do-not, S7
does not claim L3 on fake transport alone.

---

## Rebase note (2026-07-30)

The previous patch was cut against my local `57f574a`. Upstream landed S5 as
**`fc957f3`**, a *sibling* commit — both are children of `adc29d1` and both
implement S5, so the histories diverged rather than fast-forwarded.

**The two S5s are equivalent where it matters.** `git diff` between them shows
**zero** differences in `state.py`, `session_db.py`, `output.py` and `cli.py` —
which is why replaying 31 commits produced **no conflicts**. The rebase drops my
own S5 commits and replays only S6/S6.6/S7 on top of upstream's.

Three things upstream's S5 does **not** carry had to be brought forward, each
found by running the gate rather than by reading the diff:

| Carried forward | Why it was required on this base |
|---|---|
| `mutation_guard.py` exports | `fa authoring-check` **exits 1** with 4 EXPORTS-COMPLETENESS diagnostics |
| five S5 test typing fixes | `pyrefly` fails with `bad-assignment` on `_ExplodingBlackboard` and loose `Callable[[Path], Any]` factories |
| **S4-F3** — 12 deploy scripts `100644 → 100755` | see below |

**S4-F3 is live again on this base**, and my earlier S5 review closed it as
"already fixed" — that verdict was correct for `57f574a` and is wrong for
`fc957f3`. Measured here: all 12 files matching `fa-update.sh:872`'s pattern are
`100644` in upstream's index, including `scripts/fa` and
`scripts/fa-entrypoint.sh`, which must be executable to function
(`Dockerfile.fa:102` papers over it with `COPY --chmod=755`). Re-applied as its
own mode-only commit: 12 files, 0 content lines.

The lesson is the staleness rule in the plan-authoring skill: a finding's status
is a property of a *base*, not of the finding.

---

## Why

S5 gave the substrate a trustworthy authority; S6 gave it trustworthy signals.
Neither proved the **operator-facing command** composes them correctly — the S3
audit still recorded P1–P5 as `PARTIAL`, because coverage sat at the library
seam while `_cmd_run`'s own composition was asserted mostly by exit code.

## The audit shrank the slice

S7.0 measured P1–P15 against the tree **before any edit**, and most rows were
already covered at the CLI root:

| Rows | Verdict | Evidence |
|---|---|---|
| P1, P2, P3 | COVERED | `test_cli.py:950` — manifest + run dirs + per-run DB rows via real `_cmd_run` |
| P4, P5 / cells A, B | COVERED | `test_cli.py:423`, parametrised on `FA_DEBUG_LLM_BODIES` |
| cell C | COVERED | same test already runs `detail="debug"` in *both* env states |
| P6–P14 | COVERED | provider, loop and S6 renderer suites |
| **P15 / cell D** | **ABSENT** | no test set `output_mode` at the CLI root |
| **Do #8** | **ABSENT** | no test joined the four correlation keys |
| **Do #9** | **ABSENT** | no test ran `_cmd_run` twice in one process |

**Four gaps were real; eleven rows were left alone.** Writing tests for the
eleven would have added a second oracle for one behaviour — exactly the
reasoning that produced the S6 matrix-E tautology this workstream had to
retire.

## What changed

Production, **for the S7 commit itself**: `src/fa/cli.py` only, 34 lines —
everything else in that commit is tests and the plan record. (The full
`fc957f3..HEAD` range is 10 production files, because it also carries S6,
S6.6 and the carried-forward S5 CI follow-up; see the S6 note for those.)

**S7.5 — S4-F1 (Q28 option b).** `inner-loop-smoke` built an `EventLog` with no
`session_db`, so `SessionState.__post_init__` defaulted one into existence at
`<workspace>/.fa/session.db` with an **empty `session_id`** — an artifact an
operator cannot distinguish from the real authority.

The fix follows what the module is *for*. `cli_help.py:268` states it exercises
the M-1 registry **"without an LLM provider"**, so joining the real session
model (Q28a) was rejected on the module's contract. Instead it now builds an
explicit `SessionDatabase(session_id="cli-smoke")` under `.fa/smoke/`.

That is not cosmetic. Every identity guard is written `if self.session_id and
…` (`state.py`, `session_db.py`) and `event_count()` drops its `WHERE
session_id = ?` scoping — so the empty value **disabled** them. Measured: the
old DB accepted a row stamped for a *different* session. Naming the session
re-arms the guards **by construction**; no new check was added.

**P15 / matrix D.** Parametrised console-vs-quiet. Both cells assert the
durable rows and only the stderr expectation differs, because the real risk is
not "quiet prints too much" — it is a future quiet implemented by *not
emitting*. Console silence must never mean trace silence.

**Do #8 — correlation.** The join chain was measured on a real run before being
asserted: `run_id` → rows → `content["logical_call_id"]` (identical on
`provider_attempt` and `llm_call`) → `llm_bodies.jsonl`. The two intentional
non-joins are pinned as characterisation tests rather than prose, so they fail
if the fields silently start carrying something else.

## The Do #9 test found a real defect — in another test

`test_two_runs_in_one_process_do_not_leak_session_state` **passed alone and
failed in the full suite**. The leak was not in `_cmd_run`:
`test_event_type_c1_producers.py:291` called `set_current_session` with no
reset, leaking an ambient `SessionState` into every later test in the process.

Fixed at the source with a `try/finally`, not by weakening the S7 assertion.
Ignoring whitespace the change is 9 insertions / 3 deletions.

This is the **third** contextvar leak in this workstream and the second found
only because a new test happened to run after the offender. The rule worth
carrying into S8: *a test that passes alone and fails in the suite is evidence
about the suite, not a reason to relax the test.*

## A judgement call worth flagging

The first draft of the isolation test asserted that two `_cmd_run` calls create
two **sessions**. It failed with `workspace_already_owned` — S5's
reverse-ownership guard (`manager.py:196`) forbidding two sessions per
workspace. **The test was wrong, not the product.** Rewritten to attach to the
same session, which is both the realistic repeat-invocation shape and the
stronger oracle: both runs land in one authority, so misattributed rows would
show.

## Verification

**Six kill-checks, all bite:**

| # | Mutation | Result |
|---|---|---|
| KC1 | drop `session_db=` from the smoke `EventLog` | CAUGHT (1) |
| KC2 | drop `session_id=` from the smoke `SessionDatabase` | CAUGHT (1) |
| KC3 | quiet mode adds a `ConsoleRenderer` | CAUGHT (2) |
| KC4 | drop `logical_call_id` from `provider_attempt` | CAUGHT (3) |
| KC5 | blank `run_id` on `TraceEvent` | CAUGHT (11) |
| KC6 | re-introduce the contextvar leak | CAUGHT (1) |

**Mutation pass (S7.6):** `pytest --gremlins --gremlin-targets=src/fa/cli.py`
→ **479 gremlins, 479 zapped, 0 survived**, verified against `2227 passed`.
`cli.py` is the largest module in the repo (475–479 mutants) and had **never**
been mutation tested before this slice.

The two tools stay complementary: gremlins mutates expressions and ships no
statement-deletion operator, so the six kill-checks above (statement deletion,
via `scripts/mutation_sweep.py`) are not substitutable for it, or it for them.

## Gate

* pytest **2227 passed** / 14 skipped / 1 xfailed (baseline 2215 — **+12, zero regressions**)
* coverage **81.30 %**, above the `fail_under = 80` ratchet
* bare `python -m mypy` clean (313 files) — note `pyproject.toml` sets `files = ["src","tests"]`, so `mypy src/` is *not* the gate
* `pyrefly check` 0 errors · `ruff check` + `format --check` clean
* `pylint src/fa` **10.00/10** · `deptry` clean · 9/9 `scripts/check_*.py`
* `RUF002` (en-dash in a docstring range) fixed by rewriting the range, **not** waived

## Two binary artifacts were caught by the verification pass, not by CI

The first S7 commit included a **15 MB** `.coverage.e2b_local.pid….` file and a
mutation-bloated `.gremlins_cache/results.db`. `just check` is blind to both —
no linter or test objects to a committed artifact.

Root cause: `.gitignore` carried `.coverage`, but coverage.py's parallel mode
writes `.coverage.<host>.<pid>.<rand>`, which that entry does not match; and
`results.db` was already **tracked**, so an ignore rule alone could not have
stopped it. Fixed by amending the commit, adding `.coverage.*` and
`.gremlins_cache/`, and `git rm --cached`-ing the cache. The plan's own workflow
caused this — S7.6 mandates a gremlins run and gremlins rewrites its cache — so
the rules ship as part of closing S7.

## Deployment — operator action required

The container half is
[`PLAN-cli-trace-S7-container-verification.md`](../archive/PLAN-cli-trace-S7-container-verification.md):
eight steps (S7.C0–S7.C7) with exact `docker compose exec` commands, EXPECT
lines, an evidence template and a rollback. It covers deployment drift, matrix
cells A–D on the real path, DB↔mirror agreement, correlation joins on real
rows, the S4-F1 regression check, and post-run hygiene.

Two properties enforced by construction:

* **No body content is ever printed** — counts, byte sizes and identifiers only
  (ADR-12). Every probe was dry-run locally against a real `session.db`, so the
  SQL and column names are verified rather than guessed.
* **S7.C6 discriminates.** Checked against the *unfixed* tree it reported
  `PRESENT / ABSENT / session_id=('',)`; against this branch it reports
  `absent / present / cli-smoke`. A regression check that cannot fail is
  theater — this one was tested in both states.

Sequencing: run S7.C6 **after** deploying this branch, since it is that fix's
regression check. The others are order-independent after S7.C0.

## Known gaps (unchanged by this PR)

* **Q19 / V24 / V25 — subagent containment.** Open by decision; strict `xfail`
  in `tests/test_s5_isolation_boundary.py`, now tracked as
  [`BACKLOG I-34`](../BACKLOG.md).
* **Q29** — whether an empty `session_id` should remain a legal "unscoped"
  mode. Three production sites still construct DBs that way; changing that
  sentinel's meaning needs its own slice and sweep.
* **I-35** — `SessionDatabase` first-create is not concurrency-safe under a
  DEFERRED DDL transaction (6/30 concurrent first-opens fail). P3: production
  serialises creation via `mkdir(exist_ok=False)`. Should be resolved with Q29,
  since both touch the same three unserialised construction sites.
