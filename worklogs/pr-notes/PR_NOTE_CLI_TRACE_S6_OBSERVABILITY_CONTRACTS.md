# S6 — EventLog/EventBus two-sided and path-complete contracts

Stacks on **`57f574a`** (S5), which is the base this patch applies to.

Patches in `patches/` (sha256 in `patches/SHA256SUMS`):

* `S6-stack-from-57f574a.patch` — `git am` format, preferred:
  `git am < patches/S6-stack-from-57f574a.patch`
* `S6-stack-from-57f574a.diff` — plain diff:
  `git apply patches/S6-stack-from-57f574a.diff`

Contains **S6.0–S6.5**. Verified by `git am` onto a clean `57f574a` worktree
with the import root forced and confirmed (`/tmp/verify/src/fa/__init__.py`):
**2192 passed, 14 skipped, 1 xfailed**.

---

## Why

S3 left the observability substrate with contracts that were *asserted* but not
*enforced*. The through-line of S6 is that **a passing checker was not
evidence**: several guards could not fail, and several tests could not fail.

**1. The contract checkers could not fail.** `check_log_kind_contract.py`
CHECK 2 printed orphaned kinds and then never incremented `failures` — the
comment said *"soft warning, not a hard failure, unless CI is strict"*. Deleting
a **live** producer (`config_warning`) changed the output (`30`→`29 kinds`) and
still **exited 0**. Worse, `log-kind-check` was wired into **nothing** — not the
justfile aggregate, not the Makefile (S6-F6).

**2. A denial could be silently lost.** The parallel tool path inferred an
`AFTER_TOOL_EXEC` denial by re-reading the last five log rows — a heuristic, not
a signal. `run_session` had no way to *say* it stopped.

**3. Nine of sixteen `EventType`s had no renderer test at all.**

**4. Subagent results were one word.** A passing verifier returned the literal
`"PASS"`; the runner captured the output and the envelope discarded it (S5-F1).
Delegating work to save context lost the result.

---

## What changed

| Slice | Change |
|---|---|
| S6.1 | Checkers fail closed. Regex→AST resolver; `KNOWN_DORMANT_KINDS` with a written reason per entry; new CHECK 2b (unresolvable `kind=` is UNKNOWN **and fails**); CHECK 0 per-site producer floor. `log-kind-check` wired into `just check` + Makefile. |
| S6.2 | Explicit `StopInfo` via a structseq-compatible `SessionRun`; the log-scan heuristic is **removed**. `drive_session` honours the inner stop. |
| S6.3 | 52 renderer tests parametrised from the `EventType` literal; Q23 contract documented; `EventBus` docstring corrected (S6-F1). |
| S6.4 / S6.4b | Reasoned dormancy allowlist + stale-entry guard; per-site path-completeness oracle. |
| S6.4c | Retired source-text test theater in the blast radius (S6-F5). |
| S6.5 | Subagent stdout fidelity (S5-F1) **and** redaction (S6-F7). |

### S6.2 — the return shape (Q22 → Q24)

Researched CPython's own precedent: `os.stat_result` and `time.struct_time`
preserve the sequence protocol exactly while adding named attributes;
`subprocess.CompletedProcess` is the counter-example, and only got away with it
because `run()` was a *new* function. So `SessionRun` is a `Sequence[ToolResult]`
with `.results`/`.stop`, and `SessionRun == ()` is True, matching
`os.stat_result`. **Blast radius: 2 production call sites, 0 of 29 test call
sites.**

Scope correction found during implementation: breaking on *every* stop point
stopped `LoopGuard`'s circuit breaker from tripping. `BETWEEN_ROUNDS` denials
already shorten results, so the padding branch fires and the session continues
**by design**. The break is scoped to `AFTER_TOOL_EXEC` only.

### S6.5 — subagent fidelity, and a leak the plan had not recorded

The plan asked for a redaction decision (Q25) before coding. Measuring first
**falsified the plan's own premise**, so the recommendation was reversed.

The plan assumed S6.5 would be *introducing* subagent stdout to disk, making
"keep it in memory" a zero-risk option. It is not:

| Path | Raw stdout today? | Gitignored? |
|---|---|---|
| `summary`, verifier **PASS** | no — literal `"PASS"` (this is S5-F1) | — |
| `summary`, verifier **FAIL** | **yes** | — |
| `summary`, **researcher** | **yes** | — |
| `.fa/subagents/<id>.json` | **yes** | yes |
| `.fa/worklog-detailed.md` | **yes** | yes |
| **`worklog.md`** | **yes** | **NO — git-tracked** |

Two consequences. Withholding the field buys **no** security, because the leak
already exists. And the worst instance lands in a **committable** file:
`.gitignore:14` is `.fa/*`, which covers the artifact and `worklog-detailed.md`
but **not** `worklog.md`.

**Research** (GitHub Actions, GitLab CI, Vercel, Buildkite): every one persists
child stdout and masks on the way out; none withhold it. All document the
ceiling rather than declining to ship — GitLab states outright that masking "is
not a guaranteed way to prevent malicious users from accessing" values. GitHub
added "value encoders" for base64 forms; **this repo's `SecretRedactor` already
has that backstop** (`redaction.py:36-37,90,104,142-143`), so it is at parity,
not a weaker toy. Buildkite's over-redaction incident came from name-globbing
and short values — our `_MIN_LEN = 8` value-matching design avoids it, and a
test now pins the floor.

**Implemented:** mask **once, at the capture boundary** in `run_stateless`.
Every writer derives from that single `output` string, so one call fixes all
six paths — including the pre-existing `worklog.md` leak — and makes it
structurally hard for a new writer to reopen the hole. Fails **closed**: if
masking raises, the output is withheld rather than passed through.
`spawn_subagent` reuses the redactor `EventLog` already holds (new read-only
`EventLog.redactor`), so there is no second construction and no new config
surface.

Honest scope, stated in the docstring rather than implied away: this masks
*configured* secrets and their base64/URL-encoded forms. It cannot mask a
credential the subagent's own command materialises. A test pins that limit as a
characterisation, so the gap is executable rather than folklore.

---

## Evidence discipline — three process defects worth reporting

Each of these would have shipped a green-but-hollow slice.

**1. A kill-check that was itself vacuous.** The first S6.5 kill-check mutated a
disposable copy and the tests still passed — because `pip install -e .` resolved
`fa` to the *real* repo. The mutant was never executed. Every subsequent
kill-check forces `PYTHONPATH=<copy>/src` and prints the resolved import root
first. **A kill-check that has not proved which file it imported is not
evidence.**

**2. The composition root was untested (KC-4).** Every masking test built
`SubagentRunner` directly, so `spawn_subagent.py` could pass `redactor=None`
with the whole suite green — the leak reintroduced, invisibly. This is the same
vacuous-seam class S6.3 hit when a first draft patched a `renderer._stream` that
does not exist. Fixed by a test that drives the real registered tool and asserts
the runner received that exact redactor object; it now bites.

**3. Six tests passed alone and failed in the full suite.**
`_check_spawn_limit` reads the *contextvar* session, so the new tests were
spending the spawn budget of a `SessionState` leaked by an earlier module.
Fixed with an autouse isolation fixture. **This is why a slice is never marked
done from a single-file run.**

S6.4c's DoD was likewise resolved by measurement, not assertion: the first
rewrite still showed 7 passed with the producer assertion removed entirely, so
it was rewritten again until neutralising the real producer took it to 1 failed
while the control file failed both times.

---

## Post-completion audit (2026-07-29)

S6 was re-reviewed against `AGENTS.md`, ADR-12, the `tests-writing` skill, and
the parent's Step S6 exit criteria **after** being marked complete. Two real
defects were found and fixed; both are recorded in the plan's audit section.

**D1 — S6 shipped its own test theater.** The matrix-E test asserted
`flags.context_budget_enabled is expect_producer`: a tautology on the dataclass,
plus a substring check on `coder_loop.py`. Measured — replacing the production
gate with `budget_enabled = True` (flag ignored entirely) left it **9 passed**.
This is exactly the pattern S6.4c was written to retire. Rewritten to drive
`drive_session` with the flag as the only variable and assert both the console
event and the durable row; the gate-ignored and gate-inverted mutations now bite.

The instructive part is *how* it passed review: the test's own docstring argued
the emit was "covered by `test_compaction_c1_wiring.py`, and duplicating it here
would add a second oracle." That is how a tautology gets waved through —
justifying asserting nothing by pointing at another file. Cross-file coverage
does exist (the inverted-gate mutation fails 13 tests across 6 files), but a
matrix row must bite on its own.

**D2 — the secret-leakage boundary's stated minimum proof was missing.** The
skill names it *"Secret NOT in model-facing messages"*; all eleven S6.5
redaction tests asserted the on-disk channel only. Added a C3 test for the model
channel that also pins the layering against ADR-12 B2.

**D3 — a mutation sweep found three mutants that survived the whole suite.**
Because D1 was found by accident, the rest of S6 was audited by mutation rather
than by re-reading. The worst was the **fail-closed branch of `_mask`**:
replacing it with `return text` passed all 2193 tests — an untested security
branch inside the slice whose entire subject is redaction. Also unpinned: the
stop `observations` entry (the only channel telling the *model* why its turn
ended) and `from_researcher`'s `stdout`. Separately, S6.2's stop-*scope*
decision ("break on `AFTER_TOOL_EXEC`, **not** on `BETWEEN_ROUNDS`") had a test
for the positive half only; the negative half lived in a source comment, and
comments do not fail. All four are now pinned.

**The pattern is worth carrying into S7:** every gap found — D1 included — is a
*negative* or *defensive* case: the branch that must not fire, the fallback that
should never be reached, the flag that must suppress. S6's tests pinned what the
code does and under-pinned what it must refuse to do.

**Gate-invocation correction.** Earlier S6 slices reported the gate as pytest +
mypy + pyrefly + ruff + contract scripts. That is **not** `just check`, which
also runs `deptry src/`, `pylint src/fa` (with `duplicate-code` as a `fail-on`
gate) and `pytest --cov` with `fail_under = 80` rather than bare pytest. All
have now been run.

**ADR-12 positioning** is now written into `_mask`'s docstring. ADR-12 is
explicit that `SecretRedactor` is best-effort and *not* the boundary — the
boundary is container separation plus the scrubbed child env. S6.5 adds the
*persistence* layer ADR-12 left uncovered (artifact, worklogs, trace); it is
defense-in-depth, not a new boundary claim.

## Gate

* pytest **2197 passed** / 14 skipped / 1 xfailed (S5 baseline 2178 — **+19, zero regressions**), run twice, idempotent
* **mutation sweep** on S6's production changes: 4 surviving mutants found and killed — 3 of them survived the *entire* suite (see the plan's sweep table)
* **coverage 81.17%**, above the `fail_under = 80` ratchet (`just test` runs `pytest --cov`, not bare pytest)
* `pylint src/fa` **10.00/10** — `duplicate-code` is a `fail-on` gate, so this also refutes the "`_mask` duplicates `_redact`" concern
* `deptry src/` clean
* bare `python -m mypy` clean, 310 files — note `pyproject.toml` sets
  `files = ["src", "tests"]`, so `mypy src/` is **not** the gate; the bare
  invocation caught a real `Collection[str]` indexing error that pyrefly did not
* `pyrefly check` 0 errors
* `ruff check` and `ruff format --check` clean on `src/ tests/ scripts/`
* all 9 `scripts/check_*.py` PASS
* `fa authoring-check --output json` exit 0, 0 diagnostics
* doc-links 182 OK

**Pre-existing, not introduced:** `ruff format --check .` reports 40 markdown
files at `57f574a` and 40 here. Ruff 0.16 formats Python blocks inside `.md`
while the project pins `ruff>=0.5`; this is version drift. The one file S6 added
to that set was formatted, so the count is unchanged.

---

## Known gaps (unchanged by this PR)

* **Q19 / V24 / V25 — subagent containment.** The bash gate cannot contain a
  subagent; real containment needs an OS-level writable-mount boundary. Recorded
  as a strict `xfail` in `tests/test_s5_isolation_boundary.py` that should start
  passing when containment lands.
* **S6-F5 residual** (§11.3): ~34 source-text assertions across ~10 files
  outside the S6 blast radius, itemised in the plan.
* **Q25 residual, by design:** an exact-value redactor cannot mask a credential
  the subagent's command itself prints. Masking is a safety net, not a
  containment boundary — and the containment boundary is Q19.
