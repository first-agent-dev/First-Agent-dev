# PLAN: S6 — EventLog/EventBus two-sided and path-complete contracts

Status: **READY (v2 — adversarial review applied 2026-07-28)** · Parent: `cli-trace-substrate-rebaseline-2026-07-25.md` §Step S6
Traces-to: G3, G5, CT3 · Depends-on: S3, S5 (both merged) · Base: `main` after the S5 merge

---

## 0. Scope and execution boundary

### IDEA

The session substrate has two output sides: a **durable** side (`EventLog` →
`session.db`, the authority S5 made trustworthy) and an **ephemeral** side
(`EventBus` → `ConsoleRenderer`/`QuietRenderer`, what the operator actually
sees). S5 proved the durable side tells the truth. S6 asks the next question:
**does the operator ever see it, and do the checkers that claim to verify this
actually verify anything?**

The S3 audit already measured the answer as *no* in specific, named places. S6
is the slice that closes them.

### CONCRETE INTENT

Three things, in dependency order:

1. **Make the checkers real.** `check_log_kind_contract.py` currently produces
   byte-identical output after a real producer is deleted (S3-F1, re-measured
   2026-07-28 — still reproduces). Any S6 work that relies on a checker PASS is
   built on sand until this is fixed, so it goes first.
2. **Close the operator-silence gaps.** A run that stops on a hook denial writes
   a durable `run_stopped` row and emits **nothing** to the console (S3-F9). The
   operator sees the agent stop for no stated reason.
3. **Make the producer/consumer inventory honest.** One EventType has a handler
   and zero producers (`cost_alert`, S3-F5); one real producer is reported as
   dormant because the checker cannot see through a local variable
   (`subagent_spawn_done`, S3-F4).

### GOALS

- G-S6-1 — the two contract checkers fail when a real producer is removed.
- G-S6-2 — every durable stop/deny/warn path has a defined console policy:
  emitted, or explicitly exempt with a recorded reason.
- G-S6-3 — the EventType inventory has no entry without a live producer, and no
  live producer reported as dormant.
- G-S6-4 — `ConsoleRenderer` and `QuietRenderer` are tested as **separate**
  consumers of the same event stream.
- G-S6-5 — S5-F1 (verifier envelope discards stdout) is closed, since S6 owns
  `tools/spawn_subagent.py` and the subagent producer/consumer path.

### NON-GOALS

- No new EventTypes without a named consumer **and** an active producer
  (parent Do-not).
- No making every audit-only LogKind console-visible (parent Do-not).
- No speculative general AST framework. The checkers get the smallest change
  that makes their kill-check bite (parent Do #8).
- No changes to the durable authority itself — that was S5, and it is merged.
- Q19 / V24-V25 subagent containment is **out of scope**; it needs an OS-level
  boundary and is tracked separately.

### SIZE

Seven steps. S6.0 is preflight-only (it produces the §11 inventory every later
step cites). **S6.1 gates everything after it** — the other steps' evidence
depends on the checkers being trustworthy, and S3 forbids citing a checker PASS
until then. S6.2 and S6.4 are additionally blocked on Q22 and Q20.

Rough shape: S6.1 and S6.4b carry most of the work; S6.5 is small and additive;
S6.2 may reduce to a documentation change depending on Q22.

### STOP RULE

If implementation reveals a policy choice — in particular *which* durable kinds
must be console-visible, or whether a swallowed renderer exception should ever
become fatal — **stop and raise a Q#** rather than deciding inline. S5 raised
Q18 and Q19 this way and both changed the design; the same discipline applies.

---

## 1. Preflight — source-verified current state

All facts below were re-verified against `main` on 2026-07-28, after the S5
merge and the CI follow-up. Line numbers are current, not inherited from S3.

### 1.1 Defect sites (to be changed)

| ID | Site | Verified current behavior |
|---|---|---|
| S3-F1 | `scripts/check_log_kind_contract.py:214-221` (CHECK 2) | **Re-measured 2026-07-28, and the S3 wording is imprecise — corrected here.** Deleting the `subagent_spawn_done` producer *is* byte-identical, but only because that kind is **already listed dormant on clean `main`** (alongside `service_unavailable` and `timeout`), so removing its producer changes nothing that was not already reported. Deleting a *live* producer (`config_warning` from `state.py`) **does** change the output (`30 distinct kinds` → `29`, plus a new 💤 line) — but **still exits 0**. Root cause is one line: CHECK 2 prints orphans and never increments `failures`, with the in-code comment *"This is a soft warning, not a hard failure, unless CI is strict"* (`:219-220`). So the defect is **advisory-only dormancy**, not blindness. That distinction changes the fix: it is a policy/exit-code change, not a parser rewrite. |
| S3-F3 | `loop.py:290, 422, 483` | Three `kind="run_stopped"` producers; `grep -c "emit(" loop.py` → **0**, and `loop.py` holds no `output_bus` reference at all. All three sites *do* receive `state`, which carries `output_bus`, so emitting is mechanically possible. **But see §1.4 — S5 Q12 already ruled these three exempt, and `output.py:148-149` contains an explicit instruction not to wire a bus into `loop.py`.** |
| S3-F4 | `spawn_subagent.py:71` | `kind: LogKind = "subagent_spawn_done" if ... else ...` then `append(kind=kind)`. Real, test-covered producer; the regex checker reports it dormant. |
| S3-F5 | `output.py:64` + `:430` | `cost_alert` is in `EventType` and has `_handle_cost_alert`; **zero** producers repo-wide (`grep -rn '"cost_alert"' src/` outside `output.py` → empty). Genuinely dormant. |
| S5-F1 | `subagent_envelope.py:90` + `:56-69` | `summary = "PASS" if passed else f"FAIL: {stdout[:200]}"`; the envelope dataclass has **no stdout field**. A passing verifier returns the literal `"PASS"` and the parent sees nothing else. |
| S6-F2 (new, review) | `scripts/check_producer_consumer_contract.py` | **Partial-removal blindness, measured.** Removing **one** of four `api_retry` producers → output byte-identical, exit 0. Removing **all four** → exit 1 with `CONSUMER ONLY — handler exists, NO emit()`. So this checker detects *type-level* dormancy but not *site-level* regression: three of four call sites can rot away undetected. S6-CT1 must state which of the two it guarantees. |
| S6-F3 (**resolved by Q23** — not a defect) | `output.py:199-209` + `QuietRenderer` | Measured: `EventBus` with a `QuietRenderer` **and** a raising listener writes 351 bytes of traceback to stderr via `logger.error`. **Operator decision (Q23): this is correct behaviour** — stdout carries the answer, diagnostics belong on stderr, and suppressing them would hide a real defect precisely in the least verbose mode. Action is documentation + assertion only, no code change. |
| S6-F6 (new, review 2) | `Makefile:34`, `.github/workflows/advisory.yml:40` | **`check_log_kind_contract.py` is not run by CI at all.** `just check` runs only `check_producer_consumer_contract.py` (Makefile `contract-check`). So S6.1's whole premise needs restating: making that checker hard-fail changes **nothing in CI** until it is also wired into the check target. Fixing the exit code without wiring it in would be a fix nobody ever executes. |
| S6-F7 (new, review 2) | `subagent_envelope.py:140` | **S6.5's new `stdout` field lands on disk and in the event log.** `write_envelope_artifact` writes the full envelope JSON to `.fa/subagents/<task_id>.json`, and the runner logs envelope fields. Subagent stdout is arbitrary command output — plausibly containing tokens or key material. `EventLog` has a `SecretRedactor` seam (`state.py:167,214-218`) but the artifact writer does **not**. S6.5 must state a redaction policy rather than silently persisting raw output. |
| S6-F5 (new, review 2) | `tests/test_s6_log_kind_typing.py` + 11 other files | **Source-introspection test theater in S6's own target area, proven vacuous.** Six assertions in that file are `CODER_LOOP_PATH.read_text()` + `assert '...' in content`. Measured: commenting out the **real** `kind="compaction_warning"` producer and leaving only a dead comment — so the literal still appears in the file — leaves **all 7 tests passing**, while the genuine C1 test (`test_compaction_c1_wiring.py`) **fails 2 of 5**. Repo-wide there are ~34 such assertions across 12 files. Two of them (`test_s6_log_kind_typing.py`, `test_s5_console_mirror_kinds.py`) are **named for the very slices S6 must extend** and would be cited as "existing coverage" by an executing agent. |
| S6-F1 (new) | `output.py:187-209` | `EventBus` docstring says a raising listener "is caught and **printed to stderr**"; the code calls `logger.error(...)`. Measured: it *does* reach stderr via logging's lastResort handler, so the behaviour is acceptable — **the docstring is what is wrong**, and the policy is undocumented rather than absent. |

### 1.4 BLOCKING CONFLICT — S5 Q12 already decided S6.2's three sites

The first draft of this plan proposed emitting an OutputEvent at the three
`loop.py` `run_stopped` sites. **That directly contradicts a resolved decision
recorded in production source.** `src/fa/output.py:126-149` states:

> *SCOPE — the mirror contract binds the `drive_session` composition root only
> (Q12, resolved 2026-07-28). `fa.inner_loop.loop.run_session` is the
> deterministic non-LLM root. It holds no `EventBus` reference and emits
> nothing; it is intentionally console-silent so the one pure path in the
> harness keeps no display dependency.*

and closes with an explicit instruction to the S6 executor:

> *Whether `drive_session` should emit on behalf of `run_session` after it
> returns is a separate, still-open S6 question; **do not close it by wiring a
> bus into `loop.py`.***

**Consequence for this plan.** S6.2's mechanism as first written is forbidden.
The real S6 question is narrower and is restated in §5 S6.2: *should
`drive_session` emit on behalf of `run_session` after it returns?* Answering it
by editing `loop.py` would silently reverse Q12 and re-introduce a display
dependency into the one pure path in the harness.

This is also why S6.2 is **not** simply "add three emits": under `fa run`,
`drive_session` already wraps every execution and the operator *does* get the
mirror. The uncovered surface is the bare `run_session` caller
(`fa inner-loop-smoke`, direct library use) — a much smaller and differently
shaped problem than the first draft implied.

### 1.2 Invariants to pin, not re-open

S5 closed these; S6 must not regress them and should not re-litigate them:

- authority reads never fall back to the mirror (S5.5);
- `EventLog` and `Blackboard` share one authority (S5-P20);
- `FA_STATE_ROOT` resolves through one function (S5.4.5).

### 1.3 Reproductions carried in

| Finding | Repro | Result (2026-07-28) |
|---|---|---|
| S3-F1 | delete producer in disposable copy, diff checker output | byte-identical → **reproduces** |
| S3-F3 | `grep -n 'kind="run_stopped"' loop.py` vs `grep -n 'emit(' loop.py` | 3 producers, 0 emits → **reproduces** |
| S3-F5 | `grep -rn '"cost_alert"' src/ \| grep -v output.py` | empty → **reproduces** |
| S6-F1 | raising listener + captured stderr | text *does* appear → behaviour OK, **docstring wrong** |

---

## 2. Current state → target state

| Aspect | Current | Target |
|---|---|---|
| checker kill-check | vacuous (S3-F1) | removing a producer fails the checker |
| dynamic producers | false "dormant" (S3-F4) | resolved, or explicitly listed as known-dynamic with a reason |
| dormant EventTypes | `cost_alert` handler with no producer | producer added **or** type removed — decided by whether cost alerting is wanted now |
| stop paths | durable row, console silence (S3-F3/F9) | every stop has a console policy: emit, or exempt with a recorded reason |
| renderers | tested together | tested as separate consumers, both output modes |
| subagent result | `"PASS"`, output discarded (S5-F1) | bounded stdout on the envelope, both branches |
| listener failure policy | undocumented, docstring wrong | documented and tested |

---

## 3. Contracts

### S6-CT1 — Checker honesty

**PRE:** a real producer for a live LogKind / EventType exists and is
test-covered.
**POST — stated at two levels, because the two checkers differ (S6-F2):**
- *type-level*: removing the **last** producer of a kind ⇒ non-zero exit naming
  the kind. Both checkers must satisfy this.
- *site-level*: removing **one of several** producers ⇒ detected by
  `check_producer_consumer_contract.py`. Measured today: **not** detected.
**Explicitly NOT promised:** neither checker parses arbitrary dynamic
expressions. Anything unresolvable is reported `unknown` and fails, rather than
being silently classified as absent.
**KILL-CHECK:** delete a live producer in a disposable copy → non-zero exit
naming the kind; delete one of four `api_retry` sites → non-zero exit.

### S6-CT2 — Two-sided path completeness

**PRE:** a run stops via hook denial, budget stop, or provider exhaustion.
**POST:** a durable row **and** a console event, or an entry in a recorded
exemption list explaining why the path is intentionally silent.
**KILL-CHECK:** remove the emit → the path test fails.

### S6-CT3 — Consumer separation

**PRE:** one event stream, two renderers.
**POST:** `ConsoleRenderer` and `QuietRenderer` are each asserted independently;
a change to one cannot mask a regression in the other.
**KILL-CHECK:** make `QuietRenderer` print → its test fails.

### S6-CT4 — Inventory truth

**PRE:** the `EventType` literal set.
**POST:** every entry has a live producer, or is deliberately removed. No live
producer is reported dormant.
**KILL-CHECK:** re-add a producerless type → the inventory test fails.

### S6-CT5 — Subagent result fidelity (S5-F1)

**PRE:** a subagent runs a command that succeeds and prints output.
**POST:** the parent receives that output, bounded.
**KILL-CHECK:** drop the stdout field → the test fails.

---

## 4. Path and flag matrix

| ID | Parent path | Path under test | Root | Current state (verified) | Class | Kill-check |
|---|---|---|---|---|---|---|
| S6-P1 | — | live producer deleted ⇒ checker fails | `check_log_kind_contract.py` | prints 💤, **exits 0** | C0 | revert CHECK 2 to soft-warn |
| S6-P2 | — | one of N producers deleted ⇒ detected | `check_producer_consumer_contract.py` | **undetected** (S6-F2) | C0 | restore type-level-only counting |
| S6-P3 | — | dynamic `kind=` local resolved | `spawn_subagent.py:71` | reported dormant (S3-F4) | C0 | make the resolver literal-only |
| S6-P4 | **P11** | hook-deny stop under `drive_session` | `coder_loop.py` → bus | **already emits** — pin only | C1 | remove the emit |
| S6-P5 | **P11** | hook-deny stop under bare `run_session` | `loop.py` → (no bus) | **silent by Q12 design** (§1.4) | C1 | flip the exemption |
| S6-P6 | **P12** | context budget, no compaction | `coder_loop.py` | emits `context_warn` | C1 | remove the emit |
| S6-P7 | **P13** | context budget **with** compaction | `coder_loop.py` | `compaction_*` kinds exist | C1 | remove the emit |
| S6-P8 | **P14** | console mode renders each type | `ConsoleRenderer` | 10 tests exist; audit for gaps | C1 | swap renderer |
| S6-P9 | **P14** | quiet mode emits nothing on happy path | `QuietRenderer` | 1 test (`test_quiet_does_nothing`) | C1 | make it print |
| S6-P10 | **P14** | quiet mode on the **failure** path | `EventBus` + `QuietRenderer` | **leaks 351 bytes** (S6-F3) | C3 | silence the diagnostic |
| S6-P11 | — | listener raises ⇒ loop survives, operator informed | `EventBus.emit` | survives; policy undocumented | C3 | make it propagate |
| S6-P12 | — | provider retry exhausted | `coder_loop.py` `api_retry` | 4 emit sites exist | C1 | remove all four |
| S6-P13 | — | tool result | `loop.py`/`coder_loop.py` | **to be inventoried in S6.0** | C1 | remove the emit |
| S6-P14 | — | config warning | `state.py:381-385` | emits + pends pre-attach | C1 | remove the emit |
| S6-P15 | — | dormant EventType has no producer | `output.py` inventory | `cost_alert` dormant (S3-F5) | C0 | re-add a producerless type |
| S6-P16 | — | subagent stdout, success branch | `subagent_envelope.py` | discarded (S5-F1) | C1 | drop the field |
| S6-P17 | — | subagent stdout, failure branch | same | truncated to 200 chars | C1 | drop the field |
| S6-P18 | **P22** | dual-write correspondence, per-site | `output.py` mirror set | file-level only (S3-F3) | C1 | break one pair |

**Parent traceability.** Parent Step S6 exit criterion says *"path inventory
P11–P14 and P22 is complete"*. Mapping: **P11** → S6-P4/S6-P5; **P12** →
S6-P6; **P13** → S6-P7; **P14** → S6-P8/S6-P9/S6-P10; **P22** → S6-P18.
Parent Do #4 names seven paths that need happy **and** failure coverage:
context budget (S6-P6), compaction (S6-P7), hook-deny (S6-P4/P5), provider
retry (S6-P12), tool result (S6-P13), subagent (S6-P16/P17), config warning
(S6-P14). All seven are now represented; the first draft omitted compaction,
tool result and config warning.

Every row needs a named test. A row without an oracle is not covered.

---

## 5. Execution order

Incremental: **land each step behind its own tests before starting the next.**
Each step states intent · mechanism · production rationale · failure behaviour ·
**files allowed to change** · concrete test names · exit criteria (parent §13
shape, matching the S5 subplan format).

### Step S6.0 — Preflight (no production edits)

**Intent.** Establish the inventory the rest of the slice is scored against, and
re-verify every §1.1 citation before relying on it.

**Do:**
1. Re-run the four §1.3 reproductions; record drift.
2. Build the **producer/consumer/path table from exact call sites** (parent Do
   #1) — for every `EventType` and every `CONSOLE_MIRROR_KINDS` member, record
   file:line of each producer and each consumer. This table is the S6 artifact
   the parent asks for; later steps cite it instead of re-grepping.
3. Fill the two `to be inventoried` cells in §4 (S6-P13 tool result).
4. Confirm the S5 gate is still green on the merge commit under §6.1
   invocations.

**Files:** none (audit only). Output is a new section §11 in this plan.

**Exit:**
- [ ] all four reproductions confirmed or re-characterised in writing;
- [ ] producer/consumer/path table complete, with file:line for every entry;
- [ ] no §4 row left marked "to be inventoried".

### Step S6.1 — Make the checkers bite (S3-F1, S3-F4, S6-F2) — **gates the rest**

**Intent.** A checker that cannot fail is a liability: it converts absence of
evidence into apparent evidence of absence. S3 explicitly forbids citing its
PASS, so until this lands no other S6 step can use a checker as proof.

**Current behavior (source-verified).** `check_log_kind_contract.py` CHECK 2
(`:214-221`) prints `💤 <kind> — NO producer found` for orphans and **never
increments `failures`**; the in-code comment says *"soft warning, not a hard
failure, unless CI is strict"*. Three kinds are dormant on clean `main`:
`service_unavailable`, `timeout`, `subagent_spawn_done`. The first two are
**genuinely** producerless as log kinds (they appear only as
`ProviderError.kind` values in `providers/base.py`, a different namespace); the
third has a real producer behind a local variable (`spawn_subagent.py:71`).
`check_producer_consumer_contract.py` detects type-level dormancy but not
site-level removal (S6-F2, measured).

**Target behavior.** (a) A live LogKind losing its last producer **fails** the
checker. (b) `subagent_spawn_done` resolves and is no longer dormant. (c) The
two genuinely-dormant kinds are either removed from `LogKind` or recorded in an
explicit, reviewed allowlist — silence is not an option for either.

**Mechanism.** Resolve `kind=<local>` through single-assignment locals in the
same function before declaring a kind dormant; make CHECK 2 count failures
except for an explicit `KNOWN_DORMANT_KINDS` allowlist carrying a reason per
entry. Parent Do #8 forbids a speculative general AST system — a targeted
resolver plus an allowlist is the smallest change that makes the kill-check
bite.

**Production best practice.** An allowlist with a written reason per entry is
how lint suppressions are kept honest; a bare soft-warn is how they rot.

**Failure behaviour.** An unresolvable dynamic producer is reported as
**`unknown`** and counts as a failure — never silently as `absent`. Fail
closed: a checker that cannot tell must not claim.

**Files:** `scripts/check_log_kind_contract.py`,
`scripts/check_producer_consumer_contract.py`, **`Makefile`** (see S6-F6).
**S6-F6 — do not skip this:** `check_log_kind_contract.py` is currently run by
**neither** `just check` nor any workflow; only
`check_producer_consumer_contract.py` is (`Makefile:34`). Making the exit code
strict without adding the script to the `contract-check` target produces a fix
that never runs. Wire it in the **same** commit, and verify by breaking a
producer and watching `just check` fail.
**Do-not:** do not add an AST framework; do not widen either checker's scope
beyond producer resolution and exit-code policy.

**Tests** (`tests/test_s6_checker_contracts.py`, NEW):
- `test_log_kind_checker_fails_when_live_producer_removed` — C0 (S6-P1)
- `test_log_kind_checker_resolves_dynamic_kind_local` — C0 (S6-P3)
- `test_log_kind_checker_reports_unresolvable_as_unknown_not_absent` — C3
- `test_known_dormant_allowlist_requires_a_reason` — C0
- `test_producer_consumer_checker_detects_single_site_removal` — C0 (S6-P2)

**DoD / negative proof.** In a disposable copy, delete one live producer →
checker exits **non-zero** and names the kind. Restore the soft-warn → the test
fails.

**Tests-writing class.** C0 (checker semantics) + C3 (unresolvable path).

**Producer kill-check.** Revert CHECK 2 to not increment `failures` →
`test_log_kind_checker_fails_when_live_producer_removed` fails.

**Exit:**
- [ ] deleting a live producer fails both checkers;
- [ ] `subagent_spawn_done` no longer dormant;
- [ ] every remaining dormant kind is in a reasoned allowlist;
- [ ] fallout from (a) triaged before S6.2 starts (risk S6-R1).

#### S6.1 execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2105 passed / 14 skipped / 1 xfailed**
(2096 before) · `python -m mypy` clean (306 files) · `pyrefly check` **0 errors**
· `fa authoring-check` exit 0 · ruff check + format clean.

**Landed.**
* **CHECK 2 fails closed.** Orphan kinds now increment `failures` unless present
  in `KNOWN_DORMANT_KINDS`, a dict of *kind → reason*. Two entries:
  `service_unavailable` and `timeout`, both justified as `ProviderError.kind`
  values in a different namespace (`providers/base.py:119,140`) rather than log
  kinds — candidates for removal from `LogKind` later.
* **Regex → AST.** `extract_log_append_kinds` is now an `ast.NodeVisitor` that
  resolves single-assignment locals, including the annotated-ternary form
  `kind: LogKind = "a" if c else "b"` that the old lookahead could not see. A
  file that does not parse is now a hard error — the previous regex printed PASS
  on unparseable source (S3 §5.1).
* **New CHECK 2b, fail-closed.** A `kind=` expression the resolver cannot
  follow is reported **UNKNOWN and fails**, never silently as absent. Absent
  hides a live producer (S3-F4); present hides a real gap; neither is safe.
* **New CHECK 0 (S6-F2).** `PRODUCER_SITE_FLOOR` records the expected emit-site
  count per EventType. Fewer fails (a producer was deleted); **more also fails**
  (an unrecorded path — skill §3.14). Extracted to
  `_check_producer_site_floor` to stay under the C901 budget.
* **S6-F6 wired.** `log-kind-check` added to the **`justfile` aggregate `check`
  target** — the one CI actually runs (`uv run just check`) — and mirrored in
  the Makefile.

**Course corrections during the step, both caught by tests rather than review.**
1. The first test helper copied only `src`, `scripts`, `pyproject.toml`. The
   producer checker also scans `tests/` for C1 coverage (`:95`), so the
   clean-tree baseline failed **and** the site-level mutation was masked into a
   false pass. The deliberate clean-tree baseline is what exposed it.
2. The S6-F6 test first asserted on the `Makefile`. CI runs `just check`, so a
   recipe present in the Makefile but absent from the justfile aggregate target
   would still never run — the exact shape of the original defect. The test now
   asserts the aggregate target line itself.

**Kill-checks — all four bite** (disposable copies): KC-1 revert CHECK 2 to
soft-warn → 2 fail; KC-2 neutralise the site floor → 1 fail; KC-3 revert the AST
resolver to literal-only → 3 fail (including the clean-tree baseline, since
`subagent_spawn_done` becomes an unexplained orphan); KC-4 remove
`log-kind-check` from the justfile `check` target → 1 fail. KC-2 re-verified
after the C901 refactor.

### Step S6.2 — Stop-path console policy (S3-F3, S3-F9) — **constrained by §1.4**

**Intent.** An agent that stops silently is indistinguishable from one that hung.

**Current behavior (source-verified).** Under `fa run`, `drive_session` wraps
every execution and the operator **does** get the mirror. Under a bare
`run_session` (`fa inner-loop-smoke`, direct library callers) a hook denial
writes a durable `run_stopped` row and produces **no** console output.

**The question S6 must answer** — stated verbatim in `output.py:147-149`:
*should `drive_session` emit on behalf of `run_session` after it returns?*

**Mechanism — CONSTRAINED.** Q12 forbids wiring an `EventBus` into `loop.py`
(§1.4). The two admissible options are: **(a)** `drive_session` inspects the
returned results / the durable log after `run_session` returns and emits on its
behalf — keeping `loop.py` display-free; or **(b)** formally accept that a bare
`run_session` is console-silent and extend the recorded exemption to say so for
`run_stopped` specifically, so the contract stops implying otherwise.

**Stop rule.** Choosing between (a) and (b) is a policy decision about the
harness's public contract. **Raise it as Q22 and get an answer before editing**
— do not infer it from the code.

**Files (option a):** `src/fa/inner_loop/coder_loop.py`, `src/fa/output.py`.
**Files (option b):** `src/fa/output.py` only.
**Do-not:** `src/fa/inner_loop/loop.py` is **off-limits for bus wiring** in both
options (Q12, `output.py:148-149`).

**Tests** (`tests/test_s6_stop_paths.py`, NEW):
- `test_hook_deny_under_drive_session_emits_and_logs` — C1 (S6-P4), pins today's
  working path so the fix cannot regress it
- `test_hook_deny_under_bare_run_session_matches_recorded_policy` — C1 (S6-P5)
- `test_loop_module_holds_no_event_bus_reference` — C0, a structural guard that
  fails if anyone wires a bus into `loop.py`, enforcing Q12 mechanically rather
  than by comment

**DoD / negative proof.** Attach a real bus, trigger a hook denial on both
roots, assert the durable row **and** the console outcome each path's policy
promises. Negative proof: flip the policy → the matching test fails.

**Tests-writing class.** C1 (both roots) + C0 (structural Q12 guard).

**Exit:**
- [ ] Q22 answered and recorded before any edit;
- [ ] both roots have an asserted, documented policy;
- [ ] `loop.py` still holds no `EventBus` reference, enforced by a test.

#### S6.2 execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2113 passed / 14 skipped / 1 xfailed**
(2105 before) · `python -m mypy` clean (307 files) · `pyrefly check` **0 errors**
· ruff clean except the 2 known pre-existing RUF100 · both contract checkers
exit 0.

**Landed (Q22 option (c), shaped by Q24 option (e)).**
* `StopInfo(point, reason)` and `SessionRun(Sequence[ToolResult])` in `loop.py`.
* `run_session` returns `SessionRun`; `_execute_one_sequential` and
  `_execute_batch_parallel` return their stop reason in-band.
* **Removed an inference heuristic**: the parallel path used to re-read the last
  five log rows to guess whether `AFTER_TOOL_EXEC` had denied — it could match a
  stale row from an earlier turn and degraded silently on read failure. The stop
  now arrives as data.
* `drive_session` honours the stop and emits `hook_deny`; padding rebuilds a
  `SessionRun` so `.stop` survives.

**Blast radius: 2 production call sites changed, 0 of 29 test call sites.**
That is the whole point of the structseq shape.

**Four course corrections, each caught by a test or a checker — none by
inspection:**
1. `SessionRun == ()` was `False` (dataclass `__eq__` compares by type), breaking
   `test_run_session_handles_pause_guard_denial_cleanly`. Checked the precedent:
   `os.stat_result == tuple(os.stat_result)` is **True**. Added `__eq__`/`__hash__`
   for structseq fidelity — the failure was loud, not silent, which is the
   property Q24 selected for.
2. **Breaking on every stop point was wrong.** It stopped `LoopGuard`'s circuit
   breaker from ever tripping (`test_loop_guard_circuit_breaker_works_without_sink`).
   A `BETWEEN_ROUNDS` denial already shortens the result list, so the existing
   padding branch fires and the session continues *by design*. S6-F4 is
   specifically the `AFTER_TOOL_EXEC` case; the break is now scoped to it.
3. The declared return type was still `tuple[ToolResult, ...]`. mypy accepted it
   (a `Sequence` satisfies the alias structurally in most uses) but **pyrefly
   caught it** — a case where the advisory checker earned its place.
4. **My own S6.1 CHECK 0 caught the new `hook_deny` emit** (3 sites vs floor 2)
   and required updating the floor and the §11 inventory in the same commit —
   the guard behaving exactly as designed, one step after it was built.

**Kill-checks — all three bite:** KC-1 remove the outer-loop break → 1 fail
(the correctness oracle); KC-2 return a bare tuple → 6 fail; KC-3 import
`EventBus` into `loop.py` → `test_loop_module_holds_no_event_bus_reference`
fails, enforcing Q12 mechanically rather than by comment.

### Step S6.3 — Renderer separation and quiet-mode integrity (S6-CT3, S6-F3)

**Intent.** Two consumers of one stream must be independently verifiable, and
`--output quiet` must mean what it says.

**Current behavior (source-verified).** `tests/test_output.py` has 12 tests: 10
exercise `ConsoleRenderer`, **one** covers `QuietRenderer`
(`test_quiet_does_nothing`), one covers bus fan-out. Measured: a `QuietRenderer`
plus a raising listener writes **351 bytes** of traceback to stderr via
`logger.error` (S6-F3) — quiet mode is not quiet on the failure path.

**Target behavior.** Quiet mode's stderr contract is explicit and tested for
both the happy and the listener-failure path.

**Mechanism.** Add per-EventType consumer assertions for both renderers driven
from the §11 inventory, so a new EventType without renderer coverage is caught.
Decide and document the quiet-mode diagnostic policy.

**Stop rule.** If quiet mode should suppress listener diagnostics, that trades
debuggability for silence — **raise as Q23** rather than deciding inline.

**Files:** `tests/test_output.py` (extend), `tests/test_s6_renderers.py` (NEW),
and `src/fa/output.py` only if Q23 chooses suppression.

**Tests** (`tests/test_s6_renderers.py`, NEW):
- `test_console_renders_every_event_type` — C1 (S6-P8), parametrised over the
  `EventType` literal so a new type without coverage fails
- `test_quiet_emits_nothing_on_happy_path` — C1 (S6-P9)
- `test_quiet_failure_path_matches_documented_policy` — C3 (S6-P10)
- `test_listener_exception_does_not_break_fanout` — C3 (S6-P11), asserting the
  *other* listener still receives the event

**DoD / negative proof.** Make `QuietRenderer` print → its test fails. Add a new
`EventType` without a renderer branch → the parametrised console test fails.

**Tests-writing class.** C1 (renderer behaviour) + C3 (failure paths).

**Exit:**
- [ ] every `EventType` has an asserted console rendering;
- [ ] quiet mode's stderr contract is documented and tested on both paths;
- [ ] a raising listener cannot starve the other listeners.

#### S6.3 execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2165 passed / 14 skipped / 1 xfailed**
(2113 before) · mypy clean (308 files) · pyrefly **0 errors** · **ruff fully
clean** (the two long-standing RUF100 in `hooks/base.py` were auto-fixed) ·
authoring exit 0 · all 7 contract scripts PASS.

> **Correction (2026-07-30).** That RUF100 "fix" was a **regression**, not a
> win. `ruff check --fix` under 0.16 stripped two `# noqa: BLE001` waivers from
> `hooks/base.py` because 0.16 exempts a broad catch that logs via
> `exc_info=`. The pinned pre-commit ruff (**v0.15.18**) does not, so the hook
> failed with 2 × BLE001 on exactly those lines.
>
> **Resolved in code, with no waiver.** BLE001's documentation states the
> exemption outright: *"Exceptions that are logged with `exc_info` enabled will
> not be flagged."* v0.15.18 honours that only for `.error`/`.critical`/
> `.exception`; the two sites used `LOGGER.debug(..., exc_info=exc)`, which is
> outside the exemption on the older version. Rewriting them as
> `LOGGER.error(..., exc_info=True)` — the shape `EventBus.emit` already uses
> for the identical Q23 case, with zero waivers — is clean on **both** versions
> and is also the better diagnostic: a swallowed failure in the hook pipeline
> belongs at ERROR, not DEBUG.
>
> The underlying cause (two ruff versions, one repo) is fixed separately: the
> pre-commit ruff hook is now `repo: local` / `language: system`, so it runs the
> project's own ruff instead of an independently pinned mirror.
>
> Lesson: an auto-`--fix` that removes a *waiver* is a policy change. Here the
> right answer was neither "keep the waiver" nor "trust the newer tool" — it was
> to satisfy the rule's documented contract so no waiver is needed at all.

**Gap measured before writing anything.** Cross-checking the `EventType`
literal against `tests/test_output.py`: **7 of 16 types referenced, 9 not** —
`api_retry`, `compaction_end`, `compaction_start`, `context_warn`,
`cost_alert`, `hook_deny`, `loop_warn`, `subagent_start`, `subagent_end`.

**Landed.** `tests/test_s6_renderers.py` — 52 tests, parametrised **from the
`EventType` literal itself**, so a new type without a renderer branch fails
immediately rather than shipping invisible. Plus `test_payload_table_covers_
every_event_type`, a guard on the guard: without it the payload table could
drift and the parametrised test would silently skip a type.

Q23 recorded in source: `QuietRenderer`'s docstring now states the real
contract (silence on stdout and on the happy path; listener faults still
reported), and the `EventBus` docstring was corrected — it said errors are
"printed to stderr" when the mechanism is `logger.error` (**S6-F1 closed**).

**Three course corrections, all caught by running the tests:**
1. **A vacuous seam.** The first draft patched `renderer._stream`, an attribute
   that does not exist — `_write` calls `sys.stderr` directly
   (`output.py:265-267`). Every assertion would have passed while the renderer
   wrote to the real stderr. Replaced with a `sys.stderr` capture and the
   reason recorded in the helper docstring.
2. **Two "failures" were correct behaviour.** `context_warn` only prints at
   `pct >= 80` (`:380`) and `subagent_end` is silent on success at standard
   detail (`:424`). The handlers were right; my payloads did not meet their
   documented display conditions. Fixed the payloads, not the code.
3. **`caplog`, not captured stderr,** for the Q23 diagnostic: `EventBus` reports
   via `logger.error` and pytest's logging plugin owns the handlers, so a
   `sys.stderr` patch observes nothing and the test would pass or fail for the
   wrong reason.

**Kill-checks — all three bite:** KC-1 delete a `_handle_*` → that type's
parametrised case fails; KC-2 make `QuietRenderer` print → 16 fail; KC-3 swallow
listener errors silently → the Q23 diagnostic test fails.

### Step S6.4 — Inventory truth (S3-F5)

**Intent.** An `EventType` with a handler and no producer is a promise the code
does not keep.

**Current behavior.** `cost_alert` is in `EventType` (`output.py:64`) with
`_handle_cost_alert` (`output.py:430`) and **zero** producers repo-wide.

**Mechanism.** Either wire a producer in `observability/cost_guardian.py`, or
remove the type **and** its handler. These are opposite answers, so this is
**Q20** — escalated, not decided in implementation.

**Files (produce):** `src/fa/observability/cost_guardian.py`, `src/fa/output.py`.
**Files (remove):** `src/fa/output.py`, plus any test referencing `cost_alert`.

**Tests:** `test_no_event_type_without_a_producer` — C0 (S6-P15), driven from
the §11 inventory so the invariant holds for future types too.

**DoD / negative proof.** Re-add a producerless `EventType` → the inventory test
fails.

**Exit:**
- [ ] Q20 answered; `cost_alert` either produced or gone;
- [ ] inventory test in place and kill-checked.

#### S6.4 execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2169 passed / 14 skipped / 1 xfailed**
(2165 before) · mypy clean (308 files) · pyrefly **0 errors** · ruff check +
format clean · authoring exit 0 · all 7 contract scripts PASS · doc-links 181 OK.

**The defect was narrower than the plan assumed — and worth restating.**
S6.4 was written as *"`cost_alert` has a handler and no producer; produce it or
delete it"*, with Q20 resolving to *keep + allowlist*. Measuring first showed
CHECK 1 **already** fails on a producerless EventType (added a probe type with a
handler: exit 1, named correctly). So the plan's headline problem was already
solved.

The real gap was the **escape hatch**. `DORMANT_TYPES` was a bare `set` with an
inline comment, so a single unjustified line silenced a genuine contract gap —
measured: exit 1 → **exit 0** after adding one bare name. That is a mute button,
not an allowlist, and it is asymmetric with the reasoned
`KNOWN_DORMANT_KINDS: dict[str, str]` built in S6.1 one step earlier.

**Landed.**
* `DORMANT_TYPES` is now `dict[str, str]`, same shape as the S6.1 allowlist, so
  both checkers agree on what an exemption looks like. `cost_alert` carries the
  Q20 rationale in full (registered on both production paths, writes audit rows,
  denies over budget, emit blocked on the T-2 driver).
* **New CHECK 4** guards the allowlist itself against the two ways it rots:
  an entry with **no reason**, and an entry that has become **stale** because a
  producer landed. The second matters here specifically — a dormancy entry also
  suppresses CHECK 3's C1-coverage requirement, so a stale entry would exempt a
  live type forever. The S6.1 log-kind allowlist has no equivalent hazard,
  because a kind that gains a producer simply stops being orphaned.
* Extracted `_check_consumer_without_producer` when CHECK 4 pushed `main` over
  the C901 budget (16 > 15) — a real complexity increase, fixed by extraction
  rather than a suppression comment.

**Three test-authoring corrections, all caught by running the tests:**
1. A probe EventType named `s64_probe_no_producer` was **invisible to the
   checker**: its literal regex is `[a-z_]+`, which excludes digits. The
   experiment "passed" while proving nothing. Renamed, and the trap recorded in
   the helper docstring.
2. Two mutation anchors did not exist in the real source (`"cost_alert":` when
   the set used `"cost_alert",`; a module logger in `cost_guardian.py` that is
   not there). Caught by `_edit`'s no-op guard — the assertion that a mutation
   actually changed the file, which exists precisely so a kill-check cannot
   silently test nothing.
3. After the fix, the mutation anchor `DORMANT_TYPES = {` stopped matching the
   now-annotated `DORMANT_TYPES: dict[str, str] = {`. Updated.

**Kill-checks — all five bite:** KC-1 revert to a bare set → 3 fail; KC-2 drop
the empty-reason check → 1 fail; KC-3 drop the stale-entry check → 1 fail;
KC-4 stop failing on a producerless type → 1 fail; KC-5 neutralise CHECK 4 → 2
fail. KC-4/KC-5 re-verified after the C901 extraction.

**DoD negative proof, run end to end:** re-adding a producerless EventType →
exit 1 naming it; silencing it with an empty reason → **still** exit 1.

**Exit criteria:** Q20 answered and encoded with its rationale; inventory test
in place and kill-checked. `cost_alert` is neither produced nor removed — it is
*justified*, which was the decision.

### Step S6.4b — Path-completeness matrix for the parent's seven paths

**Intent.** Parent Do #4 requires happy **and** failure coverage for seven named
paths. Three of them (compaction, tool result, config warning) had no test named
anywhere in the first draft, and three more (budget, retry, dual-write) are
emitted today but unpinned — so a regression would be silent.

**Current behavior (source-verified).** `coder_loop.py` already emits
`context_warn`, `compaction_*`, `hook_deny` and `api_retry` (4 sites);
`state.py:381-385` emits `config_warning` and queues it when no bus is attached
yet. None of these has a paired producer+consumer assertion, so §4 rows S6-P6,
S6-P7, S6-P12, S6-P13, S6-P14 and S6-P18 are **pins to be written, not features
to be built**.

**Mechanism.** One parametrised C1 suite driven from the §11 inventory: for each
path, attach a real `EventBus`, drive the path, assert the durable row **and**
the console event. Reuse `tests/fixtures/session_wiring.py`
(`make_session_state`, `make_mock_chain`, `require_log`) — do **not** re-invent
wiring helpers.

**Production best practice.** A dual-write contract that is only checked at
file granularity (today's CHECK 3) passes when a producer and an emit merely
live in the same file. Per-site pairing is what makes the contract real.

**Failure behaviour.** A path that cannot be driven deterministically in-process
is recorded as **not covered** in §11 with a reason — never quietly dropped.

**Files:** tests only — `tests/test_s6_path_completeness.py` (NEW). Any
production change discovered here belongs to the owning step (S6.2/S6.3), not
this one.

**Tests** (`tests/test_s6_path_completeness.py`, NEW):
- `test_context_budget_warn_logs_and_emits` — C1 (S6-P6)
- `test_compaction_path_logs_and_emits` — C1 (S6-P7)
- `test_provider_retry_exhausted_logs_and_emits` — C1 (S6-P12)
- `test_tool_result_path_logs_and_emits` — C1 (S6-P13)
- `test_config_warning_logs_and_emits_after_bus_attach` — C1 (S6-P14), covering
  the pre-attach queue in `state.py:383`
- `test_console_mirror_kinds_pair_per_site` — C1 (S6-P18), the per-site
  dual-write assertion CHECK 3 cannot make

**DoD / negative proof.** Remove any single emit → exactly one of these tests
fails, and it names the path. Verified in a disposable copy.

**Tests-writing class.** C1 throughout (real bus, real log, real path).

**Producer kill-check.** Delete the `config_warning` emit at `state.py:385` →
`test_config_warning_logs_and_emits_after_bus_attach` fails.

**Exit:**
- [ ] all seven parent Do #4 paths have a happy-path assertion;
- [ ] each has a failure-path assertion or a recorded reason why not;
- [ ] every §4 row now names an existing test.

#### S6.4b execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2178 passed** (2169 before) · mypy clean
(309 files) · pyrefly 0 errors · ruff check + format clean.

**Landed.** `tests/test_s6_path_completeness.py` — 9 tests covering all six
previously-unpinned §4 rows plus the flag matrix.

**S6-P18 needed measurement before it could be written.** A "same function"
oracle is useless here: 10 of the 13 `run_stopped` appends and every
`compaction_*` append live inside one giant `_drive_session_inner`. So I
measured the actual append→emit distance at every `CONSOLE_MIRROR_KINDS` site:

* `coder_loop.py` — all sites pair within **3-24 lines**;
* `state.py:652` (`tool_call`) — nearest emit **267 lines** away, genuinely
  paired across a call boundary (`coder_loop.py:1591`);
* `spawn_subagent.py:109` (`subagent_spawn_fail`) — **44 lines**, paired via the
  `_emit_subagent_event` helper;
* `loop.py:292,429,563` (`run_stopped`) — **no emit at all**, the Q12 exemption.

A naive proximity rule would have produced 3 false positives and 2 false
negatives. The test encodes the measured structure instead: pair inline within
30 lines, or via a **named** cross-boundary entry, or be on the Q12 list —
nothing else passes.

**A kill-check exposed a weak assertion — the same class as S6-F5.**
`test_q12_exemption_is_still_accurate` first asserted `".emit(" not in source`.
KC-4 wired a *bound method reference* into `loop.py`
(`state.output_bus.emit` — no parens) and the test **passed**. Substring
matching on source text misses any form it did not anticipate. Rewritten as an
AST walk for `ast.Attribute(attr="emit")`; KC-4 now fails as intended.

**Kill-checks — all five bite:** KC-1 drop the pending-events flush → S6-P14
fails; KC-2 remove the `tool_call` durable row → S6-P13 fails; KC-3 neutralise
the emits around `compaction_warning` → S6-P18 fails; KC-4 bound-method emit in
`loop.py` → Q12-staleness fails (after hardening); KC-5 remove an `api_retry`
producer → S6-P12 fails. KC-3 re-verified after a C901 extraction.

**Flag matrix (skill §3.5/§3.15):** `context_budget_enabled` cells A/B each have
their own test id. The emit arithmetic itself stays covered by
`test_compaction_c1_wiring.py` — duplicating it here would add a second oracle
for one behaviour.

### Step S6.4c — Retire source-introspection theater in the S6 blast radius (S6-F5)

**Intent.** S6 exists to make observability claims trustworthy. It cannot do
that while its own target area is guarded by tests that pass on deleted code.

**Current behavior (measured, not inferred).** `tests/test_s6_log_kind_typing.py`
asserts producer existence with `CODER_LOOP_PATH.read_text()` +
`assert 'kind="compaction_warning"' in content`. Commenting out the real
producer and leaving a dead comment containing the literal:

```
tests/test_s6_log_kind_typing.py        7 passed      <- vacuous
tests/test_compaction_c1_wiring.py      2 failed      <- genuine C1 catches it
```

This is S3-F1's disease one layer up: **the string survives, so the test
survives.** It also passes on syntactically broken or commented-out code — the
same sub-finding S3 recorded for the checker.

**Why it must be handled inside S6, not deferred.** These files are named
`test_s5_*` / `test_s6_*` for a *legacy* slice numbering unrelated to this plan.
An executing agent grepping for existing coverage will find
`test_s6_log_kind_typing.py`, conclude the producer is already pinned, and skip
writing the real C1 test — inheriting a false green. The risk is specific and
foreseeable, so it is closed here rather than left as a trap.

**Mechanism.** For each source-introspection assertion **inside S6's blast
radius**, either (i) replace it with a behavioural assertion that drives the
path and observes the event, or (ii) delete it where an equivalent C1 test
already exists (`test_compaction_c1_wiring.py` covers the compaction case
today). Do **not** simply add new tests alongside — leaving the vacuous one in
place preserves the false signal.

**Scope discipline.** Only the files S6 touches: `test_s6_log_kind_typing.py`
and `test_s5_console_mirror_kinds.py`. The other ~10 files carrying this pattern
are recorded in §11 as a **backlog item (S6-F5-residual)**, not fixed here —
scope creep into 34 assertions across the suite would swamp the slice.

**Production best practice.** A test asserting on source *text* pins the
implementation's spelling, not its behaviour: it blocks refactors while
permitting deletions — precisely inverted. Structural facts that genuinely
warrant a test (e.g. "`loop.py` holds no `EventBus`") should assert on the
imported **module object**, not on a `read_text()` substring.

**Failure behaviour.** If a structural property cannot be expressed
behaviourally, it may stay source-based **only** with an inline comment
explaining why, plus a companion behavioural test — never as the sole guard.

**Files:** `tests/test_s6_log_kind_typing.py`,
`tests/test_s5_console_mirror_kinds.py`. **Production code is out of scope for
this step.**

**Tests:**
- rewrite `test_compaction_warning_producer_in_source` → behavioural, or delete
  as covered by `test_compaction_c1_wiring.py` (record which, and why)
- rewrite `test_spawn_subagent_dynamic_kind_is_typed` → assert the produced
  `LogKind` value by driving a spawn, not by grepping the file
- keep the genuinely-structural typing assertions (`append(kind: LogKind)`) —
  those test a **signature**, reachable via `inspect.signature`, not source text

**DoD / negative proof.** Re-run the S6-F5 experiment: comment out the real
`compaction_warning` producer → the rewritten suite **fails**. Today it passes.

**Tests-writing class.** C1 (behavioural replacement) + C0 (signature checks).

**Producer kill-check.** Comment out `kind="compaction_warning"` in
`coder_loop.py` → at least one test in the rewritten file fails and names the
producer.

**Exit:**
- [ ] no `read_text()`-substring assertion remains in the two named files;
- [ ] the neutralised-producer experiment fails the suite;
- [ ] residual ~10 files recorded as backlog with counts, not silently ignored.

#### S6.4c execution record — 2026-07-28

**Status: COMPLETE.** Gate: pytest **2178 passed** · mypy clean (309 files) ·
pyrefly **0 errors** · ruff check + format clean · all 7 contract scripts PASS ·
authoring exit 0.

**Scope correction found during preflight.** The plan named two files;
`test_s5_console_mirror_kinds.py` turned out to contain **zero** `read_text`
assertions — it was already behavioural. Only `test_s6_log_kind_typing.py`
needed work (5 of its 7 tests were source-text).

**Landed.** File rewritten:
* **kept** the two `inspect`/`dataclasses` tests — they assert a *signature*
  through the imported object, a structural fact with no behavioural
  equivalent. That is the line this file now draws: assert on the **module**,
  never on its text;
* **replaced** the `state.py` import check with `getattr(state_module,
  "LogKind") is LogKind` — an aliased or re-exported import still satisfies the
  contract, whereas the old substring failed on a reformat and passed on a
  commented-out import;
* **replaced** the subagent-kind grep with a C1 that drives
  `_record_subagent_completion` for both outcomes;
* **added** `test_this_file_contains_no_source_text_assertions`, an AST guard
  so the anti-pattern cannot return here quietly.

**A judgement call worth recording.** After the first rewrite the DoD
experiment still showed **7 passed** — because I had moved the producer
assertion out entirely, on the grounds that `test_compaction_c1_wiring.py`
already owns it behaviourally. That was defensible but did not satisfy the
step's own DoD ("the rewritten suite fails"). Resolved by keeping a producer
check *and* making it honest: it asserts a live `ast.Call` node, so a
commented-out or stringified occurrence no longer counts. Behavioural coverage
stays in the C1 suite; this file now proves the call site is **code**.

**DoD / negative proof — the S6-F5 experiment, before and after:**

```
comment out kind="compaction_warning", leave the literal in a dead comment
  before:  test_s6_log_kind_typing.py   7 passed   <- vacuous
  after:   test_s6_log_kind_typing.py   1 failed   <- catches it
  control: test_compaction_c1_wiring.py 2 failed   (unchanged, still honest)
```

**Kill-checks — all four bite:** KC-A revert `append(kind)` to `str` → typing
test fails; KC-B delete the subagent completion append → C1 fails; KC-C
reintroduce a source-text assertion → the anti-pattern guard fails; plus the
DoD producer check above.

**Residual backlog unchanged.** ~10 other files still carry the pattern (§11.3);
sweeping them is out of S6 scope and recorded, not silently skipped.

### Step S6.5 — Subagent result fidelity (S5-F1)

**Intent.** Delegating work to save context is pointless if the result is one
word.

**Current behavior (source-verified).** `SubagentEnvelope.from_verifier`
(`subagent_envelope.py:90`) sets `summary = "PASS" if passed else f"FAIL:
{stdout[:200]}"`; the dataclass (`:56-69`) has **no** stdout field. The runner
captures output (`subagent_runner.py:308`) and passes it as `stdout=output`
(`:321`); the envelope discards it. A passing verifier returns the literal
`"PASS"`.

**Target behavior.** The parent receives bounded subagent output on **both**
branches, without changing `summary` semantics that existing consumers read.

**Mechanism.** Add a bounded `stdout: str = ""` field to `SubagentEnvelope`;
populate it in `from_verifier` (and `from_researcher` for symmetry); **add it to
`SUBAGENT_ENVELOPE_SCHEMA["properties"]`** — the schema has no
`additionalProperties: false`, so omitting it would not fail validation but
would leave the schema lying about the payload. Keep it out of `required` so
older envelopes still validate.

**Production best practice.** Additive, bounded, and schema-declared; existing
`summary` untouched so `subagent_runner.py:211` and `stats.py:453` keep working.

**Failure behaviour.** Output larger than the bound is truncated with an
explicit marker, never silently.

**Redaction (S6-F7) — RESOLVED 2026-07-29, Q25 option (i).** Operator answered
after the addendum re-measurement and the CI-runner research (§9 Q25): **redact,
fold the `worklog.md` fix into this slice, and reuse the existing 8000-char
cap** (no second truncation — the field carries what the runner already bounded).

Resolved mechanism — **redact once at the runner boundary, not per writer.**
`SubagentRunner.run_stateless` builds a single `output` string
(`subagent_runner.py:308`) that every downstream writer derives from: `summary`,
the new `stdout` field, the `.fa/subagents/<id>.json` artifact, `worklog.md`,
`.fa/worklog-detailed.md`, and the `EventLog` trace via
`ToolResult.result = envelope.to_json()`. Masking that one string therefore
fixes all six paths — including the pre-existing git-tracked `worklog.md` leak —
with one call, and makes it structurally hard for a future writer to re-open the
hole. Redacting inside `from_verifier` or inside `write_envelope_artifact`
instead would each leave some of the six uncovered.

Per Q25 research finding 2 (GitLab's posture), the docstring must state the
uncovered case plainly: this masks *configured* secrets and their base64/URL
encodings; it cannot mask a credential the subagent's own command materialises.

**Superseded below.** The original option list and "Files:" line are kept for
the record; the resolved Files list is:
`src/fa/inner_loop/subagent_envelope.py`,
`src/fa/inner_loop/subagent_runner.py`,
`src/fa/inner_loop/tools/spawn_subagent.py`,
`src/fa/inner_loop/state.py` (public read-only accessor for the already-stored
`EventLog._redactor`, so the runner can reuse the redactor `cli.py:1885`
already builds — no second construction, no new config surface).

**Redaction (S6-F7) — original options, decided above.** The envelope is persisted:
`write_envelope_artifact` (`subagent_envelope.py:140`) writes the full JSON to
`.fa/subagents/<task_id>.json`. Subagent stdout is arbitrary command output and
may contain credentials. `EventLog` already has a `SecretRedactor` seam
(`state.py:167`, `_redact_value` at `:214`); the artifact writer has none.
Options: (i) route the new field through `SecretRedactor` before storing;
(ii) store it only in-memory for the parent and omit it from the artifact;
(iii) accept raw persistence because `.fa/` is gitignored and already holds
`llm_bodies.jsonl`. **Prefer (i)** — it reuses an existing seam and matches the
posture ADR-12 takes elsewhere. If (iii) is chosen, say so explicitly in the
docstring; do not let it happen by omission.

**Files:** `src/fa/inner_loop/subagent_envelope.py`, and
`src/fa/observability/redaction.py` only if option (i) needs a new entry point.
**Do-not:** do not change `summary`; do not add the field to `required`.

**Tests:**
- `test_verifier_envelope_carries_stdout_on_success` — C1 (S6-P16)
- `test_verifier_envelope_carries_stdout_on_failure` — C1 (S6-P17)
- `test_envelope_schema_declares_stdout` — C0
- `test_oversized_stdout_is_truncated_with_marker` — C3
- `test_persisted_envelope_does_not_contain_raw_secrets` — C3 (S6-F7), driving a
  subagent whose output contains a token-shaped string and asserting the
  on-disk artifact
- extend `tests/test_subagent_runner.py` for the end-to-end parent view

**DoD / negative proof.** A subagent running `echo '12 passed'` must surface
`12 passed` to the parent. Drop the field → the test fails.

**Tests-writing class.** C1 (both branches) + C0 (schema) + C3 (bound).

**Exit:**
- [x] stdout reaches the parent on success and failure;
- [x] schema declares the field; old envelopes still validate;
- [x] truncation is explicit and tested;
- [x] *(added by Q25 resolution)* captured output is masked, and the
  git-tracked `worklog.md` leak is closed.

#### S6.5 execution record — 2026-07-29 (commit `c2c79f2`)

**What shipped.** `tests/test_s6_subagent_fidelity.py` (14 tests) and four
production files: `subagent_envelope.py` (bounded schema-declared `stdout`),
`subagent_runner.py` (optional `SecretRedactor`, `_mask` at the capture
boundary), `state.py` (`EventLog.redactor` read-only accessor),
`spawn_subagent.py` (wire the session's redactor). 85 insertions, 2 deletions.

**Two findings that changed the slice.**

1. **Q25's premise was false** (see §9 addendum). Raw subagent stdout already
   reached disk on the FAIL and researcher branches, so the recommended option
   (ii) would have bought no security. Operator chose option (i) after the
   re-measurement and the CI-runner research.
2. **A leak the plan had never recorded.** `worklog.md` receives
   `summary[:200]` — which on the FAIL branch embeds raw stdout — and
   `.gitignore:14` (`.fa/*`) does **not** cover it. Credentials could be
   committed. Folded into this slice per the operator's scope answer.

**Kill-checks (6, all under forced `PYTHONPATH` — see the trap below).**

| # | Mutation | Result |
|---|---|---|
| KC-1 | drop `stdout=stdout` in `from_verifier` | 7 failed |
| KC-2 | remove the `_mask` call | 4 failed (incl. the worklog test) |
| KC-3 | delete the schema property | 1 failed, precisely |
| KC-4 | `redactor=None` at the composition root | **0 failed — did not bite** |
| KC-4b | same, after adding the wiring test | 1 failed |
| KC-5 | make `EventLog.redactor` return `None` | 1 failed |
| KC-6 | drop the truncation marker | 1 failed |

**Three process defects caught, each by a different gate — recorded because
each would have shipped a green-but-hollow slice.**

* **KC-4 did not bite.** Every masking test constructed `SubagentRunner`
  directly, so `spawn_subagent.py` could pass `redactor=None` with the suite
  still fully green — the leak reintroduced, invisibly. This is the S6.3
  vacuous-seam class recurring at the composition root. Fixed by
  `test_spawn_subagent_wires_the_session_redactor_into_the_runner`, which
  drives the real registered tool and asserts the runner received that exact
  redactor object.
* **The first kill-check run was itself vacuous.** The disposable copy was
  mutated but `pip install -e .` resolved `fa` to `/home/user/repo/src`, so
  KC-1 "passed" against unmutated code. Every later kill-check forces
  `PYTHONPATH=<copy>/src` and the import root was printed once to confirm.
  **Rule for future slices: a kill-check that does not first prove which file
  it imported is not evidence.**
* **Six tests passed alone and failed under the full suite.**
  `_check_spawn_limit` reads the *contextvar* session, so these tests were
  spending the spawn budget of a `SessionState` leaked by an earlier module.
  Fixed with an autouse fixture that detaches the ambient session. **This is
  why the slice is not marked done from a single-file run.**

**Gate (all re-run after the fix).** pytest **2192 passed** / 14 skipped /
1 xfailed (baseline was 2178 — +14, zero regressions) · bare `python -m mypy`
clean, 310 files — it caught one real `Collection[str]` indexing error that
`pyrefly` did not · `pyrefly check` 0 errors · `ruff check` + `format --check`
clean · all 9 `scripts/check_*.py` PASS · `fa authoring-check --output json`
exit 0, 0 diagnostics · file-level idempotency confirmed on a second run.

**End-to-end re-probe.** The original preflight probe was re-run against the
implementation; all three roles now report `summary_leak=False`,
`json_leak=False`, `files_leaked=0`, and each carries
`stdout='tok=***REDACTED***'` — i.e. the output is present (S5-F1 closed) *and*
masked (S6-F7 closed).

#### S6 post-completion audit — 2026-07-29 (against AGENTS.md, ADR-12, tests-writing, parent exit criteria)

S6 was re-reviewed after being marked complete, reading `AGENTS.md`,
`knowledge/project-overview.md`, `knowledge/adr/DIGEST.md` + ADR-12, the
`tests-writing` and `plan-authoring` skills, and the parent's Step S6 exit
criteria. **Two real defects and two process gaps were found and fixed.**

**D1 (material) — the matrix-E test was theater.**
`test_context_budget_matrix_gates_the_producer` asserted
`flags.context_budget_enabled is expect_producer` — a tautology on the
dataclass — plus a substring check on `coder_loop.py`. **Measured:** replacing
the production gate with `budget_enabled = True` (flag ignored entirely,
identifier surviving in a comment) left it at **9 passed**. This is precisely
the source-text theater S6.4c was written to retire, shipped inside S6 itself.
Rewritten as a real C1: drives `drive_session` with the flag as the only
variable and asserts the console event *and* the durable row on both cells.
Both mutations now bite (gate-ignored → 1 failed; gate-inverted → 2 failed).

Root cause worth naming: the original test's own docstring argued the emit was
"covered by `test_compaction_c1_wiring.py`, and duplicating it here would add a
second oracle." That reasoning is how the tautology got waved through — it
justified asserting *nothing* by pointing at another file. The parent's exit
criterion is "matrices E/F **covered**", and cross-file coverage does exist
(the inverted-gate mutation fails 13 tests across 6 files), but S6's own matrix
row must still bite. **Naming a matrix is not covering it; pointing at another
file is not either.**

**D2 (moderate) — the secret-leakage boundary's stated minimum proof was
missing.** `tests-writing` §11 names it as *"Secret NOT in model-facing
messages"*. All eleven S6.5 redaction tests asserted the on-disk channel; none
asserted the model channel, which is a different path
(`ToolResult.ok(result=envelope.to_json())` → `project_for_model`). Added
`test_model_facing_channel_is_masked_even_with_no_runner_redactor` (C3), which
also pins the *layering*: with the runner deliberately unmasked, ADR-12 B2's
`coder_loop._redact` still masks the payload. Kill-check: neutralising that
chokepoint fails the test.

**P1 — the AGENTS.md pre-flight checklist was skipped.** Steps 1–5 (recency
surface, term expansion, symmetric reading, subtraction-check, goal-lens) are
mandatory before edits. Run retroactively; the subtraction-check is the one that
mattered, see P2.

**P2 — no subtraction-check was run before adding `SubagentRunner._mask`.**
Retroactive answers: *Removing what makes this redundant?* — `coder_loop._redact`
(ADR-12 B2) already masks the **model** channel, and `EventLog._redact_value`
already masks the **trace**. Neither covers the artifact, `worklog.md`, or
`worklog-detailed.md`, which is the gap S6.5 closes, so `_mask` is not
redundant. *Capability lost if omitted?* Subagent output persists unmasked to a
git-tracked file. *Precedent?* GitHub Actions' runner-side `SecretMasker`
applies at the capture boundary for the same reason. **Verified not duplication:**
`pylint src/fa` (with `duplicate-code` as a `fail-on` gate) rates 10.00/10.
ADR-12 linkage is now written into `_mask`'s docstring — previously the ADR that
governs this code was not cited at all.

**Gate-invocation correction.** Earlier S6 slices reported the gate as pytest +
mypy + pyrefly + ruff + contract scripts. That is **not** `just check`, which
also runs `deptry src/`, `pylint src/fa`, `lock-check`, and — critically —
`pytest --cov` with `fail_under = 80`, not bare pytest. All were re-run here:
`deptry` clean · `pylint` 10.00/10 · coverage **81.17%** · **2193 passed** / 14
skipped / 1 xfailed.

**Parent Step S6 exit criteria, re-verified:**

| Parent criterion | Status |
|---|---|
| path inventory P11–P14, P22 complete | met — §4 maps every row to a parent path |
| producer C1 and consumer tests paired | met |
| matrices E/F and output modes covered | **now** met — was theater (D1) |
| checker mutation tests prove removed producers are caught | met (S6.1, 5 kill-checks) |
| dual-write policy explicit | met (S6.4b per-site oracle) |

#### S6 mutation sweep — 2026-07-29 (adequacy layer, skill §1 C4)

D1 was found by accident, so the remaining S6 tests were checked **by
mutation** rather than by re-reading them. Semantic mutations were applied to
S6's production changes one at a time; each mutant was `pip install -e .`'d so
imports resolved normally (a `PYTHONPATH`-only harness shadowed installed deps
and reported false survivors — the harness was validated against a
known-caught mutation before any result was trusted).

| # | Mutation | S6 tests before | Wider suite | Now |
|---|---|---|---|---|
| M1 | truncation cap `8000` → effectively disabled | caught | — | caught |
| M2 | `_mask` fail-closed → `return text` | **survived** | **survived all 2193** | caught |
| M3 | `from_researcher` `stdout=summary` → `""` | **survived** | **survived all 2193** | caught |
| M4 | composition root `redactor=None` | caught | — | caught |
| M5 | `EventLog.redactor` → `None` | caught | — | caught |
| M6b | stop-scope widened to `stop is not None` | **survived** | caught (LoopGuard) | caught |
| M7 | drop the stop `observations.append` | **survived** | **survived all 2193** | caught |
| M9b | CHECK 2 `failures += 1` removed | caught | — | caught |
| M11b | drop `compaction_warning` from mirror set | survived | caught (S5 test) | unchanged |

**Three mutants survived the entire 2193-test suite** — M2, M3, M7. All were
S6.5/S6.2 code this plan claimed was covered:

* **M2 — the fail-closed redaction branch.** `_mask` deliberately withholds
  output when masking raises, because a failed mask cannot prove the text is
  clean. Nothing tested it, so a later "simplification" to `return text` would
  have been invisible **and would have leaked**. This is the highest-severity
  finding of the sweep: an untested security branch in the slice whose whole
  subject is redaction.
* **M3 — `from_researcher`.** Blanking its `stdout` changed nothing. Pinned,
  with the honest note that the factory has **no production caller today**, so
  the new test is a unit pin on a dormant constructor, not a live-path claim.
* **M7 — the stop observation.** `hook_deny` (console) and the `run_stopped`
  row (durable) were both pinned; the `observations` entry — the only channel
  that tells the **model** why its turn ended — was not.

**M6b is the sharper lesson.** S6.2's decision had two halves: break on
`AFTER_TOOL_EXEC`, and *do not* break on `BETWEEN_ROUNDS` (or `LoopGuard`'s
circuit breaker never trips). Only the positive half had a test. The negative
half was recorded in a source comment and in this plan's prose — and prose does
not fail. A pre-existing S5 test caught it, so the codebase was safe, but S6
was relying on another slice's coverage for its own decision.

**Pattern across D1, M2, M3, M6b, M7:** every gap is a *negative* or
*defensive* case — the branch that should NOT fire, the fallback that should
never be reached, the flag that should suppress. S6's tests pin what the code
does and under-pin what it must refuse to do.

Four tests added (`2193 → 2197`); all four previously-surviving mutants now die.

## 6. Verification plan

### 6.0 Test-authoring contract (binding)

Per S5 §6.0.1, carried forward verbatim in spirit: **old tests are inputs, not
authority.** S5 re-authored five legacy tests that asserted defects as
contracts. S6 must assume the same is possible here — especially for any test
that currently passes *because* a checker is vacuous.

### 6.0.2 Binding test-authoring rules for S6 (from `knowledge/skills/tests-writing`)

The skill is not optional context — its §3 checklist is a **gate** for C1 work.
Three of its mandates were missing from v2 and are made explicit here, because
an executing agent that follows only §5 would produce tests that pass the plan
but fail the skill.

**(1) Existence pre-check before every kill-check (§3.1).** A kill-check is
**vacuous if the producer was never written**. For each of the 18 §4 rows, the
test must first assert the production call site *exists* — otherwise "removing
it breaks the test" proves nothing. This matters acutely for S6: several rows
(S6-P6, S6-P7, S6-P12, S6-P14) are **pins on already-working code**, where a
badly written test can pass without touching the producer at all.

*Concretely:* before asserting behaviour, assert the emit site is reachable —
e.g. drive the path and assert `output.emit` was called with the expected
`EventType`, not merely that "no exception occurred".

**(2) Mock boundary (§3.6).** Mock **`ProviderChain.request`** only; keep
`drive_session`, `HookRegistry`, `ToolRegistry` and `EventLog` real. Use
`tests/fixtures/session_wiring.py` — `make_session_state`, `make_mock_chain`,
`make_test_chain_config`, `mock_success_response`, `make_tool_call`,
`require_log`. **Do not hand-roll a session fixture**; S5 established these and
duplicating them is how type drift starts.

**(3) Flag matrix (§3.5, §3.15) — REQUIRED, and v2 omitted it.** Two S6 paths
are flag-gated in production:

| Path | Gating flag | Source | Matrix |
|---|---|---|---|
| S6-P6, S6-P7 (context budget / compaction) | `context_budget_enabled` | `coder_loop.py:681` | **A:** `True` (budget active) · **B:** `False` (budget bypassed — assert **no** `context_warn` emit) |
| S6-P12 (provider retry exhausted) | `max_chain_retries` | `coder_loop.py:1303` | **A:** `0` (fail-fast default) · **B:** `>0` (retry then exhaust) |

≥1 C1 test per combination. **Naming a matrix is not covering it** (§3.15) —
each cell needs its own test id. Flags must be passed explicitly via
`FeatureFlags(...)`; relying on defaults hides the matrix.

**(4) Mutation handoff (§skill "AI-authored").** S6 tests are AI-authored, so
after C1 lands they hand off to `mutation-clearing`. Not part of the S6 exit
criteria, but the executor records which files are ready for it.

**(4b) BANNED: source-introspection assertions.** No S6 test may assert on the
*text* of a production file (`Path(...).read_text()` + `assert "..." in
content`, or `inspect.getsource()` + substring). Measured rationale (S6-F5):
such a test passes when the producer is commented out, and passes on code that
does not parse — it pins spelling and permits deletion, which is inverted. If a
structural property must be asserted, assert on the imported **module object**
(`inspect.signature`, `hasattr`, module attributes), never on source text. S5
removed one such test (`test_expected_root_always_resolved`) for exactly this
reason; S6 must not add more.

**(5) Two-sided + path inventory (§3.13, §3.14).** Already in this plan (§4,
§11), restated here so the executor sees all five in one place: for every
EventType, **both** producer and consumer must be verified, and **all** emitting
paths enumerated — testing one path does not prove the others.

### 6.1 Gates

Run the **configured** invocations, not convenient subsets:

```
python -m pytest -q                 # full suite, twice, must be idempotent
python -m mypy                      # NO path argument — config is files=["src","tests"]
pyrefly check
fa authoring-check --output json    # exit_code must be 0
python -m ruff check src/ tests/    # 2 known pre-existing RUF100 in hooks/base.py
python -m ruff format --check src/ tests/
scripts/check_*.py                  # all contract scripts
```

**`python -m mypy src/` is not the gate.** The S5 CI follow-up shipped six
type errors that were invisible because only `src/` was checked locally while
the config covers `src` **and** `tests`. That mistake is not to be repeated.

---

## 7. Risks

| ID | Risk | Mitigation |
|---|---|---|
| S6-R1 | Fixing the checker exposes many latent violations at once | Land S6.1 first and triage the fallout before any other step |
| S6-R2 | Emitting on every stop path floods console output | Exemption list is a first-class outcome, not a failure |
| S6-R3 | Adding a `stdout` field breaks envelope consumers | Bounded field, additive only; existing `summary` untouched |
| S6-R4 | "Checker PASS" is cited as evidence before S6.1 lands | Explicitly forbidden by parent Do-not; S3-F1 note stands until proven otherwise |
| S6-R5 | S6.2 silently reverses Q12 by wiring a bus into `loop.py` | §1.4 records the prohibition; `test_loop_module_holds_no_event_bus_reference` enforces it mechanically |
| S6-R6 | Making CHECK 2 hard-fail breaks CI on the two genuinely dormant kinds | Land the allowlist in the **same** commit as the exit-code change; S6.1 exit criteria require both |
| S6-R7 | Adding `stdout` to the envelope inflates parent context, the opposite of the module's purpose | Bounded with explicit truncation; the bound is a named constant, tested |

---

## 8. Definition of Done

Each item names the command that proves it. "No exception raised" is not proof.

**Checkers (S6.1)**
- [x] in a disposable copy, deleting a live producer makes
      `python scripts/check_log_kind_contract.py` **exit non-zero** and name the
      kind (today: exits 0);
- [x] deleting **one of four** `api_retry` producers makes
      `python scripts/check_producer_consumer_contract.py` exit non-zero
      (today: byte-identical, exit 0 — S6-F2);
- [x] `subagent_spawn_done` is absent from the 💤 list on clean `main`;
- [x] `service_unavailable` and `timeout` are either removed from `LogKind` or
      present in `KNOWN_DORMANT_KINDS` **with a written reason each**.

**Stop paths (S6.2)**
- [x] Q22 answered and recorded in §9 before any production edit;
- [x] `grep -c "output_bus" src/fa/inner_loop/loop.py` still returns **0**,
      asserted by `test_loop_module_holds_no_event_bus_reference` (Q12, §1.4);
- [x] hook denial under `drive_session` asserts durable row **and** console
      event with a bus attached;
- [x] hook denial under bare `run_session` asserts the recorded policy exactly.

**Renderers (S6.3)**
- [x] `test_console_renders_every_event_type` is parametrised over the
      `EventType` literal — adding a type without a branch fails it;
- [x] quiet mode's stderr contract is documented in `output.py` and asserted on
      both the happy and the listener-failure path (S6-F3);
- [x] a raising listener still lets other listeners receive the event.

**Inventory (S6.4)**
- [x] Q20 answered; `cost_alert` either has a producer or no longer exists;
- [x] `test_no_event_type_without_a_producer` passes and is kill-checked.

**Subagent (S6.5)**
- [x] a subagent running `echo '12 passed'` surfaces `12 passed` to the parent
      (today: returns the literal `"PASS"`);
- [x] `SUBAGENT_ENVELOPE_SCHEMA` declares `stdout`; envelopes without it still
      validate;
- [x] oversized output truncates with an explicit marker.

**Test quality (S6-F5, §6.0.2)**
- [x] no `read_text()`-substring assertion remains in
      `test_s6_log_kind_typing.py` or `test_s5_console_mirror_kinds.py`;
- [x] the neutralised-producer experiment (comment out
      `kind="compaction_warning"`, leave the literal in a dead comment) **fails**
      the rewritten suite — today it passes 7/7;
- [x] every new C1 test does an **existence pre-check** before its kill-check;
- [x] flag matrix cells from §6.0.2 each have their own test id;
- [x] no hand-rolled session fixture — `tests/fixtures/session_wiring.py` reused.

**Slice-wide**
- [x] every kill-check in §4 verified to bite in a disposable copy, with the
      command output recorded in the execution record;
- [x] full gate green under **§6.1 invocations**, run twice, idempotent;
- [x] no §4 row without a named, existing test;
- [x] execution record written into this plan (S5 format).

## 9. Open questions

Each carries a **recommendation with its evidence**, so the operator is choosing
between analysed options rather than being handed a bare question. None is
decided in implementation.

### Q20 — RESOLVED (operator, 2026-07-28): keep the type, allowlist it.

Adopt the recommendation below: `cost_alert` stays, recorded in a reasoned
`KNOWN_DORMANT_TYPES` entry (*"awaiting T-2 cost artifact emitter; handler and
guardian both live"*). S6.4 implements the allowlist + inventory test; it does
**not** delete the type and does **not** add a producer.

**Evidence gathered during review.** `CostGuardian` is **not** an abandoned
feature — it is registered on both production paths (`cli.py:922`, `cli.py:2045`)
and it works: it accumulates cost, writes `kind="cost_observation"` audit rows
(`cost_guardian.py:250`), and **denies** the next tool call when the budget is
exceeded (`:231`). The `cli.py:919-921` comment states it is *"dormant on
baseline tools (no `cost=…` artifact) … wired here so the chain is stable when
the T-2 LLM driver lands the artifact emitter."*

So the gap is narrower than "half-built feature": the guardian has one
console-visible outcome already — its denial travels the existing `hook_deny`
emit (`coder_loop.py:612`). What is missing is a *warning before* the budget is
hit; `cost_alert`'s handler (`output.py:430`) renders exactly that
(`💰 cost: <message>`).

**Recommendation: keep the type, and treat it as blocked-on-upstream rather
than dormant-and-deletable.** Concretely: add `cost_alert` to a reasoned
`KNOWN_DORMANT_TYPES` allowlist with the entry *"awaiting T-2 cost artifact
emitter; handler and guardian both live"*, and let S6.4's inventory test enforce
that every dormant entry has such a reason. Deleting the type would discard a
working renderer for a feature whose producer is scheduled, and re-adding it
later costs more than the allowlist line.

**Cheaper alternative if you want it live now:** emit `cost_alert` from
`_observe` when `rollup.usd` crosses a fraction of `budget_usd` (e.g. 80%). That
is ~5 lines and needs no T-2 work, because `cost_observation` rows already carry
the rollup. Choose this only if you want budget warnings before denial.

### Q21 — RESOLVED (operator, 2026-07-28): adopt the three-way rule.

The rule below is now binding and must be written into `output.py` beside
`CONSOLE_MIRROR_KINDS` in S6.4b. Current membership already conforms, so this
codifies rather than changes behaviour.

**Why it matters.** Without a rule, the exemption list becomes a place to hide
inconvenient paths, and `CONSOLE_MIRROR_KINDS` drifts by accretion.

**Recommendation — adopt this three-way rule and record it in `output.py`:**

1. **Must be visible** — anything that *stops, blocks, or denies* work the
   operator asked for: `run_stopped`, `hook_deny`, `context_budget_hard_stop`,
   budget denials. Rationale: the operator cannot act on what they cannot see,
   and a silent stop is indistinguishable from a hang.
2. **Should be visible** — anything that *degrades* the run without stopping it:
   `compaction_warning`, `context_budget_warn`, `config_warning`, provider
   retries. These change the result quality; the operator should know.
3. **Must not be visible** — pure audit rows with no operator decision attached:
   `cost_observation`, `usage`, `llm_call`, `model_msg`. Mirroring these floods
   the console and trains the operator to ignore it.

The current `CONSOLE_MIRROR_KINDS` set is consistent with this rule, so adopting
it is a codification rather than a change — which is the point: it makes future
additions decidable without a debate.

### Q22 — RESOLVED (operator, 2026-07-28): **option (c)** — explicit `StopInfo`.

`run_session` returns `(tuple[ToolResult, ...], StopInfo | None)`. The stop
signal becomes **explicit data** instead of something the caller infers by
re-reading the log. Accepted cost: breaking signature, 2 call sites
(`cli.py:988`, `coder_loop.py:1507`) plus tests.

This also supersedes the `missing > 0` log-scan heuristic at
`coder_loop.py:1524-1538` for stop detection — the reason now arrives in-band.
Q12 is respected: `StopInfo` is plain data, so `loop.py` gains no display
dependency and still holds no `EventBus`.

Original analysis and the four options retained below for the record.

**The question got bigger during review, and my earlier recommendation was
based on an incomplete reading. Correcting it here.**

#### New evidence (measured 2026-07-28)

**(1) `run_session` returns no stop reason.** Verified via
`inspect.signature`: `-> tuple[ToolResult, ...]`. There is no `stopped` flag and
no reason.

**(2) `coder_loop` ALREADY does "option (a)" — but only on one branch.**
`coder_loop.py:1506` captures `log_len_before = len(log.read_all())`, and after
`run_session` returns it scans the new rows for `kind == "run_stopped"` to build
a stop reason (`:1524-1538`). So the read-back mechanism I described as
hypothetical **already exists and works**. Critically, it is guarded by
`if missing > 0:` — it only runs when `run_session` returned **fewer** results
than calls issued.

**(3) A hook-deny at `AFTER_TOOL_EXEC` returns a FULL result set.** Measured
with a real `run_session`, a real registry, and a guard denying at
`AFTER_TOOL_EXEC`:

```
calls issued: 1 | results returned: 1  ->  missing = 0
run_stopped rows written: 1
```

`_execute_one_sequential` returns `result, True` — the result is *preserved* and
the stop is signalled out-of-band (`loop.py:295`). So `missing == 0`, the
existing read-back never fires, and the caller never learns the run was stopped.

**(4) Consequence — this is not only a console gap (S6-F4, new).** Grep of
`_drive_session_inner` after the `run_session` call shows the only `break` is
inside the `missing > 0` padding block. On an `AFTER_TOOL_EXEC` denial,
`drive_session` **continues to the next turn** as though nothing happened: the
guard said stop, a durable `run_stopped` row exists, and the outer loop keeps
calling the model. No test covers this (`grep run_stopped tests/` finds
assertions that the *row exists*, none that the outer loop *halts*).

**So Q22 is no longer "should we print something?" — it is "the stop signal is
dropped by the caller, and the missing console event is the symptom."** That
reframing changes which option is right.

#### Options

| | Option | What it does | Cost | Risk |
|---|---|---|---|---|
| **(a)** | `drive_session` reads back the log after `run_session` returns, unconditionally (not just when `missing > 0`), emits `run_stopped`, and breaks the turn loop | Reuses the mechanism that already exists at `:1524`; `loop.py` untouched, Q12 honoured | Small — move the read-back out of the `missing > 0` guard, add an emit + `break` | Log-scan is inference; a future producer writing `run_stopped` for a non-fatal reason would halt the loop wrongly |
| **(b)** | Formally accept bare `run_session` as console-silent; document only | Zero code | **Does not fix S6-F4.** The dropped stop signal remains. My earlier recommendation — now clearly insufficient on its own |
| **(c)** | Change `run_session` to return a structured result (`tuple[ToolResult, ...], StopInfo \| None`) | Makes the stop signal *explicit* rather than inferred; caller decides display and control flow | Breaking signature change; 2 call sites (`cli.py:988`, `coder_loop.py:1507`) + tests | Touches the pure path's public API — but adds no display dependency, so Q12 is respected |
| **(d)** | (a) now, (c) recorded as the upgrade path | Fixes the correctness bug immediately with the smallest diff; leaves the clean design documented | Small | Two-step, but each step is independently shippable |

#### Recommendation: **(d)** — implement (a), record (c)

Reasoning:
- **(b) alone is now wrong.** It only ever addressed the console symptom; the
  measured defect is that the outer loop ignores a stop it was told about.
  Shipping (b) would document a correctness bug as intended behaviour.
- **(a) is small and uses a proven mechanism** — the same log-scan already
  running two lines away, just not gated behind `missing > 0`.
- **(c) is the honest design** (explicit signal beats inference) but is a
  breaking API change; it deserves its own slice rather than being smuggled into
  an observability step.
- Q12 is respected by all of (a), (c), (d): none wires an `EventBus` into
  `loop.py`.

**If (a) is chosen, S6.2 gains a correctness test, not just a display test:**
`test_after_tool_exec_denial_halts_the_outer_loop` — assert the model is **not**
called again after the guard denies. That test fails today.

### Q24 — RESOLVED by research (2026-07-28): **option (e), the CPython `structseq` pattern.**

None of options (a)-(d) was chosen. Research into how production systems widen a
return type without silent breakage produced a better answer than any option I
had listed.

**Prior art.** This is a solved problem in CPython itself:

* **`os.stat_result`** — `os.stat()` returned a 10-tuple; fields were added over
  many releases. Verified live: `len(st) == 10` still, `st[0] == st.st_mode`
  still, **and** `st.st_atime` exists. Indexing and length were preserved
  exactly; new data arrived as named attributes.
* **`time.struct_time`** — same shape: `localtime()[0] == localtime().tm_year`.
* **`subprocess.CompletedProcess`** (3.5) — the counter-example that proves the
  rule. `subprocess` moved *away* from tuple returns to a named object, and
  could only do so because `run()` was a **new** function; the old
  `check_output`/`call` API kept its contract. Where an existing signature had
  to be preserved, CPython used structseq; where a clean break was possible, it
  introduced a new name.

Our case matches the first pattern, not the second: `run_session` is an existing
function with 31 call sites.

**Applied design (prototyped and measured before adoption).**

```python
@dataclass(frozen=True)
class SessionRun(Sequence[ToolResult]):
    results: tuple[ToolResult, ...]
    stop: StopInfo | None = None

    def __len__(self):
        return len(self.results)

    def __getitem__(self, i):
        return self.results[i]

    def __iter__(self):
        return iter(self.results)
```

Measured against the exact Q24 hazard:

```
assert len(results) == 2   -> True   (measures RESULTS, not the pair)
results[0]                 -> "r0"   (element, not a nested tuple)
for r in results           -> [r0, r1]
tuple(results) == (...)    -> True
results.stop               -> StopInfo | None      <- the new, explicit signal
```

**Why this beats every option I had listed.** (a) had the silent-`len` bug; (b)
frozen dataclass fixed `len` by making it a `TypeError` — loud, but it still
breaks all 31 sites for no behavioural gain; (c) and (d) hide the signal in a
parameter or in mutable state. Option (e) is the only one where **zero call
sites change**, **no assertion silently changes meaning**, and the stop signal
is still explicit, in-band, and typed — which was Q22's actual requirement.

**Net effect on S6.2 scope:** `src` diff shrinks to the two production callers
that *want* the new field; the 29 test call sites are untouched, because their
meaning is genuinely unchanged. That is the correct amount of churn for this
change: zero.

### Q24 (original analysis, retained for the record)

Q22 chose option (c) — `run_session` returns the stop reason explicitly. The
*shape* of that return turns out to matter more than expected, and one obvious
shape has a measured silent-failure mode. Raising rather than choosing.

**Blast radius (measured).** 31 `run_session` call sites: 2 in `src`
(`cli.py:988`, `coder_loop.py:1507`), 29 across 8 test files. 22 bind the result
directly; 57 lines index or iterate it.

**The hazard with a bare tuple `(results, stop)`.** Most old code fails loudly —
`results[0].error` raises `AttributeError` because `results[0]` is now the inner
tuple. But `len(results)` does **not**:

```
2-call session, old assert len(results) == 2, new return (results, None)
  -> len((results, None)) == 2  -> True  -> SILENT PASS
```

`tests/test_inner_loop_blockers.py:482` (`assert len(results) == 2`) is exactly
this case, and `loop.py:466` uses `len(results)` internally against
`max_iterations`. A migration that leaves a test green while measuring the wrong
thing is precisely the failure mode S5 §6.0.1 warns about.

**Options.**

* **(a) Bare tuple `(results, StopInfo | None)`.** Smallest diff. **Rejected
  unless paired with an audit of all 57 index/len sites** — the silent case
  above is real, not theoretical.
* **(b) A `NamedTuple`/frozen dataclass `SessionRun(results=..., stop=...)`.**
  Old positional code still breaks loudly on attribute access, `len()` on the
  object is a `TypeError` for a dataclass (loud) — and for a `NamedTuple` it is
  still 2 (same silent hazard). **Frozen dataclass avoids the `len` trap
  entirely**; `NamedTuple` does not.
* **(c) Keep the return type, add an out-parameter** — e.g. `stop_sink:
  list[StopInfo]` the caller passes in. No call site breaks; ugly, and easy to
  ignore, which is how the current bug happened.
* **(d) Keep the return type; put `StopInfo` on `SessionState`.** `state` is
  already passed to every call and is the natural home for run-scoped facts.
  Zero call-site churn, no silent-pass class, and the caller reads
  `state.last_stop`. Weaker than (b) on explicitness — a mutable field can be
  stale — but it is mitigable by clearing it at the top of `run_session`.

**Recommendation: (b) with a frozen dataclass, or (d).** (b) is the honest
signature Q22 asked for and its failure mode is loud on every shape; cost is
touching 31 sites. (d) is near-zero-churn and cannot silently pass, at the cost
of being state rather than signature.

I lean **(b)** because Q22's stated intent was *"the stop signal becomes
explicit data instead of something the caller infers"*, and a return value is
harder to ignore than a field. But (d) delivers the same correctness fix for a
fraction of the diff, and the 29 test call sites are churn with no behavioural
benefit — so if diff size is the binding constraint, (d) is defensible.

**Either way S6.2 must include:** an audit of the 57 `len`/index sites, and the
correctness test `test_after_tool_exec_denial_halts_the_outer_loop`, which fails
today.

### Q23 — RESOLVED (operator, 2026-07-28): keep listener diagnostics in quiet mode.

No behaviour change. S6.3 documents the real contract — quiet guarantees silence
on **stdout** and on the happy path, **not** suppression of listener failures,
which stay on stderr by design — and asserts exactly that. **S6-F3 is therefore
reclassified from a defect to an undocumented-but-correct behaviour**; the §1.1
row is updated accordingly.

**Evidence.** `QuietRenderer` is documented as *"Emits nothing"*
(`output.py:443`), and `--output quiet` exists so `fa run … > result.txt` stays
parseable. Measured: with a `QuietRenderer` **and** a raising listener, the bus
writes **351 bytes** of traceback to stderr via `logger.error`
(`output.py:204`).

**This is arguably not a bug.** stdout carries the answer; the traceback goes to
**stderr**, so redirection still works and the parseable-output guarantee is
intact. Suppressing it would hide a real defect precisely when the operator has
chosen the least verbose mode.

**Recommendation: do not suppress — document and test the actual contract.**
State in `output.py` that quiet mode guarantees *silence on stdout and on the
happy path*, **not** suppression of listener failures, which remain on stderr by
design. Then assert exactly that in S6.3. This closes the question without a
behaviour change, and turns an undocumented accident into a stated guarantee.

**Reverse only if** you have a consumer that treats *any* stderr output as
failure. That would be a real constraint — worth saying so now if it exists.

### Inherited, still open (not S6 scope)

- **BACKLOG (operator, 2026-07-28) — subagent containment via an OS-level
  writable-mount boundary, or a better mechanism found by research.** Accepted
  as a tracked backlog item rather than an open question: the decision to fix it
  is made, only the mechanism is open. Entry criteria for picking it up: it
  gates enabling `subagent_spawning_enabled` by default, together with S5-F1.
  Research note for whoever takes it: the shipped comparables all solve this at
  the OS layer, not in a shell gate — worktree-per-agent (Claude Code, Codex,
  Cursor) isolates *files* but not *writes*; a read-only bind of the repo plus a
  single writable mount at the artifact dir is the smallest thing that makes the
  artifact-only claim true for arbitrary commands. The existing container work
  is the natural host. Guarded meanwhile by the strict `xfail` in
  `tests/test_s5_isolation_boundary.py`, which fails the suite the day behaviour
  changes.
- **Q19 / V24 / V25 — subagent containment (superseded by the backlog entry above).** Resolved *for S5* as option (d):
  ship V18–V21, leave containment open with the measurement recorded. The real
  fix is an OS-level writable-mount boundary (option (c)). Tracked by the strict
  `xfail` in `tests/test_s5_isolation_boundary.py`, which will fail the suite if
  the behaviour changes. **No action needed until you want subagents enabled.**
- **S5-F1 — verifier envelope discards stdout.** Not a question; it has an owner
  and a design (S6.5). Listed here only so the subagent story reads in one
  place: S5-F1 (usefulness) and Q19 (safety) are the two gates on turning
  `subagent_spawning_enabled` on.

## 11. Producer / consumer / path inventory (S6.0 artifact, 2026-07-28)

Parent Do #1. Built from exact call sites; later steps cite this instead of
re-grepping. Regenerate after any change to `EventType`.

### 11.1 EventType producer/consumer table

| EventType | producers | consumer | note |
|---|---|---|---|
| `api_retry` | 4 | yes | `coder_loop.py` — flag-gated by `max_chain_retries` |
| `compaction_end` | 5 | yes | |
| `compaction_start` | 2 | yes | |
| `compaction_warning` | 1 | yes | gated by `context_budget_enabled` |
| `config_warning` | 2 | yes | `state.py` — queues pre-bus-attach |
| `context_warn` | 5 | yes | gated by `context_budget_enabled` |
| `hook_deny` | 3 | yes | `coder_loop.py:612`, `:1406`, and the S6.2 outer-loop stop |
| `llm_response` | 1 | yes | |
| `loop_warn` | 3 | yes | |
| `session_end` / `session_start` / `tool_call` / `turn_start` | 1 each | yes | |
| **`subagent_start`** | **1** | yes | **literal-invisible** — passed positionally to `_emit_subagent_event` (`spawn_subagent.py:204`), so a `type="..."` regex reports 0. Same class as S3-F4. |
| **`subagent_end`** | **2** | yes | same (`:86`, `:120`) |
| **`cost_alert`** | **0** | yes | **genuinely dormant** — Q20 resolved: keep + allowlist |

**Every EventType has a consumer** (`HANDLER-LESS: []`), so S6's inventory work
is producer-side only.

**Method note, and a warning for S6.1.** A naive `type="([a-z_]+)"` scan reports
`subagent_start`/`subagent_end` as dormant; both are real, test-covered
producers whose literal is a positional argument. This is exactly the
false-negative S3-F4 describes, reproduced independently here — **three** of the
sixteen EventTypes are literal-invisible, not one. Any S6.1 resolver must handle
positional args to a helper, not just `kind=<local>`.

### 11.2 Reproductions re-verified at S6.0 (2026-07-28)

| Finding | Result |
|---|---|
| S3-F1 | live producer removed → output changes (`30`→`29 kinds`, new 💤) but **exit stays 0**. Confirms: soft-fail policy, not blindness. |
| S6-F4 | `AFTER_TOOL_EXEC` denial → `missing = 0`, `run_stopped` row written, caller cannot observe. **Reproduces.** |
| S3-F5 | `cost_alert` producers outside `output.py`: **0**. Still dormant. |
| S6-F6 | `check_log_kind_contract` occurrences in `Makefile` + workflows: **0**. Not wired to CI. |

### 11.3 S6-F5 residual backlog (out of S6 scope)

Source-introspection assertions outside S6's blast radius, left for a future
test-hygiene pass: `test_compaction_sota.py` (6), `test_s1_context_limit_fix.py`
(4), `test_pr3_wiring.py` (4), `test_pr1_wiring.py` (4),
`test_subagent_runner.py` (3), `test_s11_session_state_typing.py` (2), plus 5
files with 1 each. ~34 assertions across 12 files total; S6 fixes only the two
files it touches.

---

### Q25 — OPEN (raised during S6.5 preflight): redaction policy for persisted subagent stdout. *(blocks S6.5)*

S6.5 adds a bounded `stdout` field to `SubagentEnvelope` (S5-F1: a passing
verifier currently returns the literal `"PASS"` and nothing else). The plan
already flagged S6-F7 — the envelope is persisted — and told the executor to
choose a redaction option before coding. Measuring first changed what the
options are worth.

**Measured.**
* `write_envelope_artifact` (`subagent_envelope.py:136-141`) writes the full
  envelope JSON to `<session>/.fa/subagents/<task_id>.json`. There is no
  redaction on that path.
* `SubagentRunner` has **no** redactor (grep: zero references), so option (i)
  is not "reuse an existing seam here" — it means threading one in.
* `SecretRedactor` masks **exact matches of configured env vars**, verified:

  ```
  known secret   -> token=***REDACTED***
  UNKNOWN secret -> token=sk-live-zzzzzzzzzzzzzzzz
  ```

  So it cannot mask a credential the subagent printed that FA never knew about
  — which is the realistic leak (a test fixture, a `.env` the command cat'd, a
  cloud CLI dumping a token).
* `.gitignore:14` excludes `.fa/*`, and `llm_bodies.jsonl` — full LLM request
  and response bodies — already lands there unredacted under the debug flag.

**Why this needs a decision rather than a default.** Option (i) gives *partial*
masking with a real risk of being read as "subagent output is redacted", which
is worse than a documented gap. Option (iii) is consistent with how the repo
already treats `.fa/`, but it should be a stated choice, not an omission.

**Options.**

* **(i) Route the new field through `SecretRedactor`.** Catches configured
  secrets. Cost: thread a redactor into `SubagentRunner`. **Caveat measured
  above** — it does not catch unknown credentials, so the guarantee is weaker
  than the name suggests.
* **(ii) Keep `stdout` in-memory for the parent; omit it from the artifact.**
  Closes S5-F1 (the parent gets the output) with zero new persistence. The
  artifact keeps today's fields. Smallest security surface; cost is that the
  on-disk record stays as thin as it is now.
* **(iii) Persist raw, document it.** Consistent with `llm_bodies.jsonl` and
  the gitignored `.fa/`. Cost: a subagent that prints a token writes it to
  disk, and only a docstring says so.
* **(iv) (ii) now, (i) when a redactor reaches the runner.** Parent gets the
  output immediately; persistence waits until masking exists to apply.

**Recommendation: (ii), with (iv) as the stated path.** S5-F1 is a
*usefulness* defect — the parent cannot see test output — and (ii) fixes it
completely without adding a new place for credentials to land. Option (i)'s
partial masking is the option most likely to be misread as a guarantee. If the
on-disk artifact later needs the output, that is the moment to thread a
redactor, and the reason will be concrete rather than speculative.

#### Q25 addendum — re-measured 2026-07-29 at the start of the S6.5 session

The framing above assumed S6.5 would be *introducing* subagent stdout to disk,
so that omitting the field (option (ii)) would keep the leak surface at zero.
**Re-measurement falsifies that assumption.** Probe (`from_verifier` +
`write_envelope_artifact`, run against a known secret `sk-live-…`):

| Path | Carries raw stdout today? | Gitignored? |
|---|---|---|
| `summary` on **PASS**, verifier | no — literal `"PASS"` (this is S5-F1) | — |
| `summary` on **FAIL**, verifier | **yes** — `f"FAIL: {stdout[:200]}"` | — |
| `summary` on any exit, **researcher** | **yes** — `stdout[:500]` | — |
| `.fa/subagents/<id>.json` artifact | **yes**, via `summary` | yes (`.gitignore:14`) |
| `.fa/worklog-detailed.md` (`subagent_runner.py:239`) | **yes**, `to_json()[:2000]` | yes |
| **`worklog.md`** (`subagent_runner.py:219`, `- Steps: {summary[:200]}`) | **yes** | **NO — tracked** |
| `EventLog` trace (`ToolResult.result = envelope.to_json()`, `spawn_subagent.py:241`) | **yes** | via `.fa/` |

Two consequences, both of which change the decision:

1. **Option (ii) does not achieve "zero new persistence", because persistence
   already exists.** Raw subagent stdout reaches disk today on the FAIL and
   researcher paths. Withholding `stdout` from the artifact would leave that
   untouched — it buys no security while still leaving the artifact thin. The
   security question is therefore not "should S6.5 add a leak?" but "S6.5 is
   touching the one file that already leaks; does it fix it?"
2. **The worst leak lands in a git-tracked file.** `worklog.md` is *not*
   covered by `.gitignore:14` (`git check-ignore` confirms: `.fa/*` matches
   `.fa/worklog-detailed.md` but not `worklog.md`). The `llm_bodies.jsonl`
   precedent cited above therefore does **not** cover this path — that
   precedent is about gitignored `.fa/`, and this one is committable.

Also re-measured, and materially in favour of option (i):

* **`EventLog` already accepts and applies a redactor** (`state.py:167,214-225`
  — `_redact_value` recurses through str/dict/list/tuple), wired from
  `cli.py:1885,1979`. Option (i) is therefore *not* a novel mechanism; it is
  applying the seam the trace path already uses to the one sibling writer that
  skipped it. That materially lowers option (i)'s cost and raises its
  consistency argument.
* The "unknown credential" caveat is real but **narrower than stated**:
  `build_scrubbed_env` (`bash_env.py:70-89`) allowlists env names and then
  drops anything matching `SECRET_NAME_RE` fail-closed, so the subagent does
  not inherit FA's credentials in the first place. The residual leak is a
  secret the *command itself* materialises (cat a `.env`, a cloud CLI dumping
  a token) — which no exact-match redactor can catch, but which is also not
  made worse by masking the ones we do know.

**Revised recommendation: (i) + bounded field, i.e. thread the existing
`SecretRedactor` into the envelope writer and fix the pre-existing `worklog.md`
leak in the same slice.** Rationale: option (ii)'s security premise is void;
option (iii) is already the de-facto state and is what leaks to a tracked file;
option (i) reuses a proven in-repo seam rather than inventing one. The
"partial masking misread as a guarantee" risk is answered by naming the field
and docstring honestly (masks *configured* secrets; does not mask secrets the
command itself prints) rather than by declining to mask.

**Scope caution.** Fixing the `worklog.md` leak is a pre-existing defect
outside S5-F1's literal statement. It is inside S6.5's blast radius (same two
files) and is the highest-severity item found, so folding it in is defensible —
but it is a scope decision, so it is put to the operator rather than assumed.

#### Q25 research — how production systems solve "persist subprocess output that may contain secrets"

Surveyed the closest real-world analogue: CI runners persisting build-job
stdout, which is the same shape (untrusted child process output, retained on
disk/served to humans, may contain credentials the platform never registered).

| System | Mechanism | Scope gate | Documented limit |
|---|---|---|---|
| GitHub Actions | runner-side `SecretMasker`, value + regex sets, **plus "value encoders"** for common transforms (base64 etc.) | automatic for registered secrets; `::add-mask::` for runtime values | docs state masking "relies on finding an exact match"; structured data (JSON/XML) defeats it |
| GitLab CI | per-variable `Masked` toggle | opt-in; ≥8 chars, single line, no spaces | docs state masking "is not a guaranteed way to prevent malicious users from accessing variable values" |
| Vercel build logs (2026-07-09) | redact `Sensitive`-typed env var values | opt-in by type **and** ≥32 chars | vars never marked Sensitive get nothing; short values pass through |
| Buildkite agent | `BUILDKITE_REDACTED_VARS` name patterns + 6-byte floor | opt-in patterns | over-redaction bug: unanchored patterns and short values (`1`, `true`) shredded ordinary logs |

Four findings that bear directly on Q25:

1. **Nobody solves this by withholding the output.** Every system persists the
   child's stdout and masks on the way out. Option (ii)'s "don't record it" is
   not the industry answer; it is the answer only when the output has no value,
   and here the output *is* the value (S5-F1 exists because it is missing).
2. **Exact-value masking is the universal mechanism, and everyone documents its
   ceiling rather than declining to ship it.** GitLab's wording is the model:
   ship the mask, state plainly that it is not a guarantee. This directly
   answers the Q25 objection that option (i) "reads like a guarantee" — the
   production practice is to mask *and* say what it does not cover.
3. **Encoding backstops are considered table stakes.** GitHub added "value
   encoders" precisely because base64/URL-encoded secrets slipped the raw
   match. **This repo's `SecretRedactor` already has them** — `redact()` covers
   URL-encoded forms (`redaction.py:90,104`) and runs a decoded-scan backstop
   over base64 and hex windows (`_B64_WINDOW_RE`, `_HEX_WINDOW_RE`,
   `:36-37,142-143`). Our redactor is therefore at parity with the GitHub
   mechanism, not a weaker toy.
4. **Length floors and name patterns are the failure mode to avoid.**
   Buildkite's over-redaction incident came from pattern-matching *names* and
   masking very short values. Our redactor matches values with a `_MIN_LEN = 8`
   floor and no name globbing, which is the safer of the two designs. No change
   needed — but the S6.5 tests should pin the floor so a future edit cannot
   introduce the Buildkite failure.

**Research verdict: option (i).** The revised recommendation above is what all
four production systems do; option (ii) has no production analogue, and option
(iii) is the pre-mitigation state each of those systems shipped a masker to
leave behind. Applying finding 2, the field's docstring must state the
uncovered case (a secret the command itself materialises) rather than implying
completeness.

## 10. Review gate

### Round 1 — adversarial review, 2026-07-28 (applied)

Reviewer question posed: *given S3-F1, is any evidence in this plan resting on a
checker PASS?* Answer: **no** — but six other defects were found, four of them
material. All are closed in this v2.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R1 | **S6.2's mechanism was forbidden by a resolved decision.** `output.py:148-149` says verbatim *"do not close it by wiring a bus into `loop.py`"* (S5 Q12). The draft proposed exactly that. | **Blocking** | §1.4 added; S6.2 rewritten with two admissible options; Q22 raised; `test_loop_module_holds_no_event_bus_reference` added as a mechanical guard |
| R2 | **S3-F1 was mis-stated.** "Byte-identical" holds only for kinds *already* dormant. Deleting a **live** producer *does* change the output — it just still exits 0. Root cause is one line (CHECK 2 never increments `failures`), not parser blindness. | **Material** — wrong fix implied | §1.1 corrected with both measurements; S6.1 retargeted at exit-code policy + allowlist, not a parser rewrite |
| R3 | **No parent traceability.** Parent exit criterion names paths P11–P14 and P22; the draft invented S6-P1..P12 with no mapping, so "path inventory complete" was unverifiable. | **Material** | §4 rebuilt with a `Parent path` column and an explicit mapping paragraph |
| R4 | **Parent Do #4 coverage incomplete.** It names seven paths needing happy+failure coverage; compaction, tool result and config warning were absent from the matrix. | **Material** | All seven now represented (S6-P6, S6-P13, S6-P14) |
| R5 | **No `Files:` directive on any step**, versus seven in the S5 subplan. An executing agent had no change boundary. | **Material** — executability | Every step now carries `Files:` and, where relevant, `Do-not:` |
| R6 | **Rows asserted work that already exists.** S6-P4/P5 (budget, retry) are already emitted by `coder_loop.py`; the draft implied they were missing. | Minor | §4 gained a `Current state (verified)` column; those rows are now *pins*, not builds |

Two further defects were discovered **by measurement during the review** and
added as findings rather than assumptions: **S6-F2** (producer/consumer checker
misses single-site removal) and **S6-F3** (quiet mode leaks 351 bytes of
listener traceback to stderr).

### Round 2 — adversarial review, 2026-07-28 (applied)

**Lens deliberately changed.** Round 1 asked *"is the plan internally correct?"*
Round 2 asked the operator's question: ***"if an agent executes this exactly,
will the resulting code and tests be production-grade?"*** — i.e. audit the plan
against `knowledge/skills/tests-writing`, and look for traps an executor would
fall into rather than errors a reader would notice.

That lens found five defects Round 1 missed, three of them material.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R7 | **Q22 was answered on incomplete evidence, and the underlying bug is a correctness bug, not a display bug.** `coder_loop:1506` already does the log read-back I called hypothetical — but only under `if missing > 0`. Measured: an `AFTER_TOOL_EXEC` denial returns a **full** result set (`missing == 0`), so the branch never fires and `drive_session` **continues to the next turn** after a guard said stop. | **Material** — my prior recommendation (b) would have documented a correctness bug as intended | Q22 reframed with four options and new evidence; **S6-F4** filed; recommendation changed to (d) = (a) now + (c) as upgrade |
| R8 | **Plan violated three mandates of its own governing skill.** No *existence pre-check* (§3.1), no *mock boundary* (§3.6), and **no flag matrix** (§3.5/§3.15) — despite S6-P6/P7 being gated by `context_budget_enabled` (`coder_loop.py:681`) and S6-P12 by `max_chain_retries` (`:1303`). | **Material** — tests would pass the plan and fail the skill | §6.0.2 added: five binding rules incl. an explicit matrix table with named cells |
| R9 | **Test theater inside S6's own blast radius, proven vacuous.** `tests/test_s6_log_kind_typing.py` asserts producer existence via `read_text()` substring. Commenting out the real `compaction_warning` producer (leaving a dead comment) → **7/7 pass**, while the genuine C1 suite **fails 2/5**. The file is *named for this slice*, so an executor would cite it as existing coverage. ~34 such assertions across 12 files repo-wide. | **Material** — inherited false green | **S6-F5** filed; **S6.4c** added to retire it in-scope; source-introspection assertions **banned** in §6.0.2(4b); residual files logged as backlog |
| R10 | **S6.1's fix would never execute.** `check_log_kind_contract.py` is run by **neither** `just check` nor any workflow — only `check_producer_consumer_contract.py` is (`Makefile:34`). Making its exit code strict changes nothing in CI. | **Material** | **S6-F6** filed; `Makefile` added to S6.1's files with a same-commit requirement and a verification step |
| R11 | **S6.5 persists arbitrary command output to disk with no redaction policy.** `write_envelope_artifact` writes the full envelope to `.fa/subagents/<id>.json`; the new `stdout` field is unbounded command output that may contain credentials. `EventLog` has a `SecretRedactor` seam; the artifact writer does not. | **Material** (security) | **S6-F7** filed; S6.5 must choose a redaction option before coding; C3 test added asserting the on-disk artifact |
| R12 | S6-F3 (quiet-mode stderr) was filed as a defect; operator decision Q23 says it is correct behaviour. | Minor | Reclassified in §1.1 from defect to *undocumented-but-correct*; action is documentation + assertion only |

**Answer to the operator's question, after these fixes:** yes for code, with one
caveat. The plan now names files, mechanisms, failure behaviour and negative
proof per step, and its tests are bound to the skill's checklist including the
matrix and existence pre-check. The caveat is **Q22**: until it is answered, the
largest correctness item in the slice (S6-F4, a dropped stop signal) has no
chosen mechanism, and S6.2 cannot start.

### Round 3 — recommended before execution

Ask a reviewer who has not read this plan: *for each of the 18 rows in §4, name
the test file and the command that proves it.* Any row where that cannot be
answered in one sentence is not ready to execute.
