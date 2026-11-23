# Q-V2-SLICE3-5 / Q-V2-SLICE3-6 — expert opinion (2026-11-23)

**Status: both questions OPEN. No code written for either. No production change made.**
**Method.** Every claim below is re-measured against the current source (`grep` / `sed` / AST read) on this commit; no test was executed and no runtime behavior is asserted. A "measured" claim cites a file and line. The one thing that did not happen is a full pytest run — the four cheap gates on `23d5d03` are recorded (ruff 0, ruff-format 7, mypy 62 lines / 29 unique, authoring-check 0 — see the brief §5) and pytest remains **owed**; nothing in this document rests on the full suite being green.
**Ledger:** E627 (the second axis was added to 3-5), E628 (the brief), E629 (gate recording). This document is E630.
**Branch:** `arena/529586c5-first-agent-dev` at `dd259eb` (merge of `arena/a8316e90-first-agent-dev`, 56 commits, merge-base `1acb56b`).

---

## 0. What the system is, and what it is for

**System's meaning.** An artifact produced by a model is checked by something other than the model that produced it, and the check cannot be talked around — not by the plan, not by the author, not by "it finished". The chain that makes this true:

```
roadmap → increment → INV → CT → TEST-ID → selector → exactly one nodeid
       → seal (bytes at a revision, digest-bound) → pinned read-only cell
       → sealed closure runs (never the planner's fence)
       → attempt (route, identity, claims, commands, errors) → artifact + eval
```

Two mechanisms are the product: the **seal** (immutable per-seal file in private metadata plus one atomic pointer; never under `worklogs/`) and the **disposition pipeline** (a waiver a model cannot mint for itself — caller-granted, one-shot, time-boxed, route-typed). Everything else is scaffolding.

**Values the design holds to.** The plan and the external cross-review name six; this document uses the same six because they are the six promotion axes every mechanism is checked against:

| # | Value | What it means concretely |
|---|---|---|
| 1 | **Independence** | Checker ≠ author. Planner ≠ coder ≠ verifier; the verifier reads the seal, not the author's beliefs. |
| 2 | **Fail-closed reliability** | No verdict without evidence. Uncertainty is recorded as `ERROR`, never as a pass; a refused attempt is distinguishable from an empty one (F4); a candidate that cannot be named by the substrate is refused (F5). |
| 3 | **Small verifiable steps** | Slices with exact contracts and exact tests; a refusal at admission is the repair trigger, not a coin-flip discovered after the coder has spent a round (D-V2-10). |
| 4 | **Repair without losing evidence** | A failed claim can be repaired in place (one authoring repair round, N1) without erasing what was measured; the attempt log is append-only, so a re-run never overwrites the evidence of the previous run. |
| 5 | **Audit trail** | The seal digests the plan at the revision; the attempt carries the identity (seal, closure, revisions, substrate); the eval block and the artifact show the *gaps* (`kill_declared`, `attested`, `pending`), never a simplified "green". |
| 6 | **Minimalism toward new mechanisms** | No second seal, no second runner, no second store, no second severity axis — a mechanism exists only when its absence is the actual defect. SLICE3's intent names this: reuse STEP9A's seal, projection and attribution; do not fork. |

**Why this ordering (meaning first, then analysis).** Q-V2-SLICE3-5/6 are not formatting questions. They decide what "executable" means on the one route that exists (V2), and what a claim can honestly say about its own mutation. Both questions are load-bearing for the whole stack above:

- 3-5 decides whether `TARGET-ID` is a **site**, which is a type of oracle. If it is a site, the planner is held to something checkable; if it is a label, the plan can say anything and the check is decoration.
- 3-6 decides where the mutation runs. If the mutation runs on the host, the substrate that F10 removed is back; if it runs in the pinned cell, the command stays harness-built and CT-3.6 holds.

Both are therefore *philosophy-of-verification* questions, not implementation details. That is the reason for the meaning-first framing of this document.

---

## 1. The brief's claims, re-measured

| Claim (brief §2.1, §3.1, §3.2) | Measured against source | Verdict |
|---|---|---|
| `kill_attribution` has no production importer | `grep -rn kill_attribution src/ scripts/` → only the module itself; importers are `tests/` | **Holds** |
| `run_kill_checks` does not exist | `grep -rn run_kill_checks src/` → one docstring hit, no definition | **Holds** |
| V1 requires a directive per `FUNCTIONAL` contract; V2 does not | `slice_verification.py:1177+` (`kill-directive-missing`, CT54) vs `plan_v2.py:610–615` (only rows that exist are validated; no missing-row rule) | **Holds** |
| `_run_kill_check` dispatches to the in-band path whenever `executor.writes_are_visible is False` | `slice_verification.py:2101–2114` | **Holds** |
| `_build_inband_kill_command` copies `src` (+`scripts`) into cell scratch, writes the mutated bytes, proves provenance, runs pytest, returns JUnit in-band | `slice_verification.py:1873–1990` (overlay build, `_PROVENANCE_PROBE`, pytest run, in-band JUnit block) | **Holds** |
| `KILL_CHECK_COMMAND = "python -m pytest {path} -q"` | `slice_verification.py:1781` | **Holds** |
| `run_node_oracle` writes its report to a host tempfile | `kill_attribution.py:265–267` (`tempfile.TemporaryDirectory`), reads it back from the host path (`:270–272`) | **Holds** |
| `_junit_block` requires exactly one block | `slice_verification.py:832–843` | **Holds** |
| `verify_sealed_acceptance` never runs a mutation and refuses a non-empty `kill_required` before running any cell command | `acceptance_collection.py:442–445` | **Holds** |
| Plan parser accepts any non-empty `TARGET-ID` ≤ 256 chars | `plan_v2.py:521–530` | **Holds** |
| Plans never check duplicate `target_id`; the comment in `kill_attribution.py:211` cites a rule (`duplicate-kill-target-id`) that does not exist | `plan_v2.py:521–530` (no duplicate check); `grep -rn duplicate-kill-target-id src/ tests/` → zero hits; the only duplicate rule is the attempt's write-time `kill-target-duplicate` (`verification_attempt.py:357–359`) | **Holds — with an additional defect the brief did not name (§3.3)** |

One claim that is *not* carried by the brief and that I verified while re-reading the plan: `prompt.py:1248` makes the `KILL-TARGETS` block mandatory, and the example at `:1299–1300` teaches `TARGET-ID: src/widget.py::parse` — while every test fixture writes a dotted id (`publication.publish_plan`). That is the brief's fact #1 of §2.2, and it is the complete picture of the grammar's ambiguity.

---

## 2. Q-V2-SLICE3-5 — the shape of `TARGET-ID`

### 2.1 The measured facts

- `plan_v2.py:201–205` — `KillTarget(target_id, ct, test_id)`: **no operator, no path, no symbol**.
- `plan_v2.py:521–530` — `_parse_kill_targets` — accepts any non-empty string ≤ 256 chars as `TARGET-ID`; only `CT`/`TEST-ID` are validated.
- `prompt.py:1299–1300` — teaches `TARGET-ID: src/widget.py::parse`; `prompt.py:1248` makes the block mandatory.
- `tests/test_ai_native_plan_v2.py:121`, `tests/test_ai_native_kill_attribution.py:341–355` — fixtures write dotted ids (`publication.publish_plan`, `target.one`).
- `kill_attribution.py:207` (`bindings`) — binds by `ct`/`test_id` and sealed nodeid; **`target_id` is never read as a path**.
- `verification_attempt.py:213–220` (`ClaimEvidence.proven`) — `outcome == "passed" and (mutation is None or mutation.verdict == "proven")`. `None` is indistinguishable from "mutation ran and died" by this field alone; only `kill_declared`'s presence distinguishes them.
- `workflow_controller.py:653,686` — the V2 route always passes `kill_required=()` and records the declaration as `kill_declared`.
- V1: `slice_verification.validate_kill_directives` requires a directive per `FUNCTIONAL` contract (CT54), exempts `CONSTRAINT`/`PRESERVATION`.

So the field is, at once, a **site** (to the prompt), a **label** (to the fixtures), and a **site** (to `kill_attribution.bindings`, which ignores it). A runner cannot be specified against it.

### 2.2 Options — with the obligation axis folded in (as the brief does)

| Option | Shape | Obligation | Verdict |
|---|---|---|---|
| **A** | `TARGET-ID: <path>::<symbol>`, `MUTATION: <op> [-> <callee>]` (separate field) | Restored: FUNCTIONAL without a row → `kill-target-missing` (V1's CT54 precedent) | **Recommended** |
| B | Keep `TARGET-ID` opaque; `MUTATION: <op> <path>::<symbol> [-> <callee>]` free-text | Same | Rejected: two sources of truth, an unparseable site, and the runner needs a second parser |
| C | Retire `KILL-TARGETS` until the grammar can express an operator | None | Rejected: destroys attribution; the report would say nothing about which test a mutation would belong to |

**A** wins because it makes exactly one normalisation (grammar), keeps the site structural (path/symbol split at the same point as validation), and lets the runner consume `KillDirective(operator, path, symbol, callee, line)` directly with no text parse. It is also the only option that lets the `MUTATION` field validate the operator's **callee requirement** — `remove-call` without `-> callee` is the V1 `_weak` shape, `neutralise` with a callee is a malformed row.

The **obligation axis** must ride the same change set. The V1 CT54 precedent is the correct shape: an admission-time rule, not a runtime refusal, and no requirement beyond `FUNCTIONAL` (which is exactly the class V1 requires and V2 never asks). A `FUNCTIONAL` contract that reaches the runner with no declared target is a plan that cannot be checked, and the refusal belongs at admission — where the repair round can fix it (D-V2-10's repair-trigger principle).

**The three sub-decisions to name explicitly** (all three ride the ratification):

1. **The row's exact grammar.** Proposed:
   ```
   KILL-TARGETS:
     TARGET-ID: src/widget.py::parse | MUTATION: neutralise | CT: CT-1.1 | TEST-ID: TEST-1.1
     TARGET-ID: src/widget.py::parse | MUTATION: remove-call -> render_widget | CT: CT-1.1 | TEST-ID: TEST-1.1
   ```
   - `TARGET-ID` = `<path>::<symbol>`; `path` is repo-relative, under `_MUTATION_ROOTS` (`src`/`scripts`), no `..`, no absolute, no empty symbol; `symbol` is a dotted identifier (`_resolve_targets` accepts qualified names like `_Silence.visit_Call` — the parser must not be stricter than the engine).
   - `MUTATION` = `<op> [-> <callee>]`; `op ∈ {neutralise, remove-call}` (the exact two `KillOperator` members — the engine has no third, and V1 fixed that choice in CT50); `remove-call` with no callee → refused (`kill-target-mutation-invalid`); `neutralise` with a callee → refused (same rule; a neutralised function cannot call anything).
   - Grammar rows are validated at parse time under the closed rule family, and the **same rule kills the three unreachable shapes** V1 kills (`kill-target-id-invalid`, `kill-target-attribution-invalid` extended for the new field, `kill-target-unknown-operator`).
2. **Where `target_id` is stored.** Prefer: the parser splits `TARGET-ID` into `path` + `symbol` at admission and carries both on `KillTarget` (one normalisation, not two — the runner consumes the split directly; `kill_attribution._binding` never needs to re-parse it). `KillTarget` becomes `(path, symbol, operator, callee, ct, test_id)`.
3. **`kill_declared` disposition.** After 3-5 and 3-6 land, the runner exists; a declared target means the runner will execute it. `kill_declared` loses its producer — every contract with a row now means `kill_required`. **Decision required:** remove the key (cleanest; the artifact would say `kill_required: [CT-1.1]` and carry mutation verdicts on the claim) or keep it for targets that cannot be executed. Removing is honest — `kill_required == ()` already means "no executable target" — and it is the same class of question D-V2-4 named. Either is admissible **only after the runner exists**; today the key is load-bearing.

### 2.3 Additional measured findings (beyond the brief's §2.1–2.6)

1. **A false citation in `kill_attribution.py:211`.** The comment claims "Target ids are already unique per plan (`duplicate-kill-target-id`)". No such rule exists anywhere in `src/` or `tests/`. The attempt-level rule `kill-target-duplicate` does exist (`verification_attempt.py:357–359`), but it is a write-time rule — it fires at the attempt, after the seal. The plan should catch the duplicate at parse/admission, where `kill-target-id-invalid` already lives. This is bug-class (§5), not a shape decision.
2. **`kill_attribution.bindings` never re-checks the site.** It binds by `ct`/`test_id`. That is correct today — `TARGET-ID` is a label and admission has already validated `CT`/`TEST-ID`. Once `TARGET-ID` becomes a site, `_binding` stays correct but becomes a binding between a contract/test pair and a sealed nodeid; the *site* (path/symbol) binds to the runner, not to `bindings`. This is worth stating, because it is the exact boundary between "shape decision" (3-5) and "runner decision" (3-6).
3. **The mandatory block is the asymmetric trap.** The authoring prompt requires a `KILL-TARGETS` block, and today every V2 plan writes *some* row. With the obligation restored, **every** `FUNCTIONAL` contract must have one. That means the repair path (the N1 unsealed-acceptance repair) will be exercised more often — a planner that writes a FUNCTIONAL contract without a row will get the refusal and have to add the row. That is the desired behavior; it is also the argument for making the grammar rule crisp (§2.2, sub-decision 1) and the error message itself teach the row shape, rather than a bare `kill-target-missing`.

---

## 3. Q-V2-SLICE3-6 — how a mutation reaches the pinned read-only cell

### 3.1 The corrected premise

The plan's row and the brief §3.1 both record that "the existing mutation engine is host-side by construction". Measured: that is true only of the **non-managed** path. `_run_kill_check` (`slice_verification.py:2061`) dispatches to `_run_inband_kill_check` whenever `executor.writes_are_visible is False` (`:2101–2114`), and that path builds a self-contained cell-side bootstrap (`_build_inband_kill_command`, `:1873–1990`) that copies `src` (+`scripts`) into a scratch overlay in the cell's own `$TMPDIR`, writes the mutated bytes, proves with `_PROVENANCE_PROBE` that the overlay is the imported module, runs pytest and returns JUnit **in-band** between the `<<<FA-JUNIT-REPORT>>>` markers. The V1 host path (`mutation_overlay` + `_assert_overlay_wins`) is the `executor is None` branch — the frozen legacy route.

### 3.2 What is actually missing — five items (all with addresses)

1. **No baseline run in the cell.** `_run_inband_kill_check` runs only the mutated version. V1 compares the mutated result to a host-side baseline snapshot (`_capture_nodeids_by_slice` → `verify_plan`); the sealed route has no such side — there is no baseline, so the mutated run's verdict is unanchored. The sealed-oracle arm of the V1 flow (`oracle_argv`) exists but has never run under the managed executor.
2. **`run_node_oracle` is host-shaped — a defect, not a design.** `kill_attribution.py:247–267` writes its report to `tempfile.TemporaryDirectory` on the **host**, and `:270–272` reads it back from that host path. Under a managed executor the file is created in the cell's scratch and the host cannot read it — every sealed baseline reads as `MISSING`/`oracle-no-report` → `ERROR`. The 28 test functions in `test_ai_native_kill_attribution.py` all route through `FakeHost` (`tests/test_ai_native_kill_attribution.py:154–156,238–241`), so the managed path is untested and **untested-by-construction, not tested-and-broken**.
3. **`verify_sealed_acceptance` does not receive a `WorkspacePort`.** Its signature (`acceptance_collection.py:406`) names only `executor`; the controller's `_VerifySubstrate` carries a port (`:484–495`, built at `:559`) that is discarded. Without the port, the cell-side mutation cannot read the candidate's source file, and `_run_inband_kill_check` returns `ERROR` ("managed kill-check requires a pinned WorkspacePort").
4. **The in-band contract requires one block per command.** `_junit_block` (`slice_verification.py:832–843`) refuses duplicates, half-blocks and out-of-order markers. Two runs = two commands, not one command with two reports. The parser is the oracle; it must not be relaxed.
5. **No `run_kill_checks` seam.** V2's route passes `kill_required=()` unconditionally (`workflow_controller.py:653`) and `acceptance_collection.py:442` refuses a non-empty `kill_required` before running anything. The F9 refusal is a real guard; it is simply that the composition that turns `kill_required` into a live run does not exist.

### 3.3 What is additionally missing (found in this turn, not in the brief)

6. **The baseline and mutated runs must share the exact argv.** `oracle_argv` is already the right baseline (one sealed nodeid, `-c <sealed>/pytest.ini`, `--rootdir <sealed root>`, the nodeid plugin, no cache — `kill_attribution.py:215`). The mutated run must be the **same argv**, run after the overlay is built — not the V1 `KILL_CHECK_COMMAND` (`python -m pytest {path} -q`, `:1781`). Building two commands with different argv would make the verdict about *two* things ("does this test fail after the mutation" and "does it behave identically to the baseline"), which is not what the oracle is for. One argv, two commands.
7. **The in-band bootstrap must be generalized, not copied.** `_build_inband_kill_command` is tightly coupled to `KILL_CHECK_COMMAND`, the `_MUTATION_ROOTS` overlay, and the JUnit block contract. The baseline command needs a *different* shape — no overlay, same argv, and an in-band report — that is not a variation on `_build_inband_kill_command`'s payload. The clean fit: a small harness function that builds the baseline command from `oracle_argv` + `inband_junit_command` (the same pattern as `sealed_collection_inband_command`) and leaves the mutation command unchanged. Both must keep the one-JUnit-block-per-command rule of the cell-side protocol.
8. **`kill_attribution` must distinguish two evidence generations.** The sealed collection writes a report into `$__fa_rep`; the mutation needs the report of a *different* command (baseline vs mutated) carrying the **same nodeid**. The `_PROVENANCE_PROBE`'s "module resolves inside the overlay" check must run separately against the baseline command (proving the sealed bytes are what ran) and the mutated command (proving the mutated module is what ran). This is the "two commands" rule made concrete.
9. **The F9 refusal must be lifted at the right moment, not before and after.** `acceptance_collection.py:442` refuses a non-empty `kill_required` before the cell runs. That refusal is correct **today** (no runner exists, so `kill_required` is always empty and the guard never fires). After 3-6 lands, the guard's contract changes: a declared target must actually execute, and **a target that cannot execute must record `ERROR`, never `PROVEN`**. The guard's *refusal* is then the right answer for the *unavailable* case (port missing), not the executed-but-not-proven case.

### 3.4 Options — with pricing

| Option | Shape | Cost after measurement | Verdict |
|---|---|---|---|
| **(a) Harness-owned cell-side bootstrap** | generalized from landed code; two commands per target (baseline + mutated), one argv; port plumbed through; `KILL_CHECK_COMMAND` → sealed argv | Moderate: baseline command builder, `run_node_oracle` in-band, port plumbing, command-payload ceilings (unchanged) | **Recommended** |
| (b) Second pinned view of mutated tree | Authority publishes a mutated revision | Needs the immutable-payload store D-V2-5 forbids | Rejected |
| (c) Host execution | Reuse V1's `mutation_overlay` on the host | Forbidden by `verifier-substrate-required` (`acceptance_collection.py:276`) and by CT-3.6's intent | Rejected |
| (d) Defer — keep 3-4 = A (`executed: false`) | — | Zero | The recorded recommendation against the prioritised work; **rejected as the only answer** because the operator prioritised the mutation operator |

(a) wins because it reuses landed, exercised code: the pure AST transform (`apply_kill`), the in-band overlay (`_build_inband_kill_command`'s provenance-probe + scratch-overlay + report-block contract), the cell-side report parsing (`parse_inband_nodeids`), and the attribution oracle (`attribute()`). It adds one new piece — the baseline command — and removes none. It is not a new substrate; it is the same substrate exercised through the same protocol for the exact case the plan's slip-rule requires.

### 3.5 The in-band baseline, in code terms

- Baseline command: `oracle_argv(bundle, binding, report=_INBAND_REPORT_NAME)` rendered via `_render_inband` (or the existing `sealed_collection_inband_command` pattern) — no overlay, same argv the sealed verifier runs. Its report is parsed by `parse_inband_nodeids`, whose result feeds `_classify` into `NodeRun` — the same `_classify` the mutated path uses, so "pass / fail" speaks one language.
- Mutated command: the existing `_build_inband_kill_command` **generalized** to take `oracle_argv` (the sealed nodeid, not the V1 test paths) instead of `KILL_CHECK_COMMAND`. Its payload carries the mutated file bytes (as today) but no `KILL_CHECK_COMMAND` string; the overlay copy of `src`/`scripts` stays host-independent (it copies the cell's own view).
- Both commands run through `run_commands` with the pinned executor and `port` passed in. The mutated command is built from a snapshot of the **candidate** source (read via `port` — the only file the harness may read from the pinned view).
- `attribute(binding, baseline=baseline_run, mutated=mutated_run)` decides the verdict — **one judge, not two**.
- Payload ceiling unchanged: `_build_inband_kill_command` returns `None` when the payload exceeds `MAX_TEXT_BYTES`; that is the honest answer when the candidate is too large, and it stays.

---

## 4. Per-change classification

The standing audit constraint (no production change without operator ratification) binds every row below — the classification says which decision the operator must make before code moves, not whether the work may proceed today.

| # | Change | Class | Why |
|---|---|---|---|
| 1 | `TARGET-ID` shape + `MUTATION` field (3-5) | **Ratification-gated** | New grammar: field semantics, two new admission rules, fixtures + prompt + skills moving atomically (D-V2-11). A decision, not a repair. |
| 2 | Obligation axis (`kill-target-missing` for FUNCTIONAL) | **Ratification-gated** | Restores a rule V1 enforced and V2 dropped. Adding a grammar rule without the operator's ratification is exactly the D-V2-10 class of change (admission refusal changes what the planner is allowed to write). |
| 3 | `kill_declared` disposition (remove or keep) | **Ratification-gated** | Artifact vocabulary. Cleanup, but `kill_declared` is load-bearing today (N2) and the eval/artifact lines speak about it; removing a key is a vocabulary decision. |
| 4 | Cell-side bootstrap option (a) (3-6) | **Ratification-gated** | Architecture + runner shape. The option's cost is the two-commands-per-target contract and the baseline command's existence; the ratification is about *where the mutation runs*, not about one field. |
| 5 | `ADMISSION_RULES_V2` namespace + `contract_id` regex (CT-1.1) | **Ratification-gated-adjacent** | The atomicity rule is ratified (D-V2-11); the exact regex choice is implementation. Recommended: extend the contract-id regex to `CT-<slice>.<n>` (i.e. `CT-\d+(\.\d+)?[a-z]?` — the shape `_CT_RE` accepts at the parser) and add a `plan-v2` rules namespace, so admission records speak V2 vocabulary. Must move with the grammar bump, not separately. |
| 6 | `run_node_oracle` in-band form (host-tempfile → in-band) | **Bug-class** | The function is *supposed* to run on the sealed route; the host-tempfile report makes every managed-mode baseline `MISSING`. No new policy — the failure is named today by construction, and the fix is a property of the same function. Rides 3-6. |
| 7 | `verify_sealed_acceptance` port plumbing | **Bug-class / mechanical** | The port already exists (`_VerifySubstrate`); the runner requires it; the plumbing is the minimum wiring to make the seam reachable. Not a new mechanism. |
| 8 | `kill_attribution.py:211` false citation (`duplicate-kill-target-id`) + admission-time duplicate-id rule | **Bug-class** | Comment describes a rule that does not exist; the attempt-level rule fires too late (post-seal). The plan-side rule restores the stated invariant with no policy change. |
| 9 | Artifact/eval line hardcoding "the V2 grammar expresses attribution only" | **Bug-class** | Stale statement that will become false on the runner path; must report facts, not grammar. |
| 10 | `sealed_attempt` docstring stale ("kill_required is empty because the V2 grammar declares no executable mutation") | **Bug-class** | Stale derivation; must become a statement of the *fact at the time*, or be removed. |
| 11 | CT83 (`check_kill_directive_ownership.py`) V2 equivalence | **Ratification-gated-adjacent** | New audit tool, but it is a V2 analogue of an already-ratified rule (CT83); the shape is inherited from V1. Recommended: do it in the same change set as 3-5, so the audit does not silently skip the new grammar. |

Rule of thumb for the table: **ratification-gated** = the operator must choose (option, shape, vocabulary); **bug-class** = the existing decided behavior or design was implemented imperfectly and must be repaired — and that repair still obeys the audit constraint (no code without ratification).

---

## 5. Desired behavior and code architecture (to be recorded in the plan)

### 5.1 Grammar (3-5)

- Row: `TARGET-ID: <path>::<symbol> | MUTATION: <op> [-> <callee>] | CT: CT-<s>.<n> | TEST-ID: TEST-<s>.<n>`.
- `TARGET-ID` split at parse time: `path` (repo-relative, under `_MUTATION_ROOTS`, no `..`/absolute), `symbol` (dotted identifier). Stored on `KillTarget` as `path`/`symbol`, not as a string.
- `MUTATION` parsed by the same strict logic as V1 (`_KILL_STRICT_RE` over the tail, or the same two-operator vocabulary): `op ∈ {neutralise, remove-call}`; `remove-call` requires `-> <callee>`; `neutralise` refuses `-> <callee>`.
- Admission rules (closed): `kill-target-id-invalid` (path/symbol unparseable), `kill-target-mutation-invalid` (operator unknown / callee mismatch), `kill-target-missing` (FUNCTIONAL contract without any row — restored obligation), `kill-target-duplicate` (same target_id twice — plan-side, extending the attempt rule).
- FUNCTIONAL contracts without a row → `kill-target-missing` admission refusal; CONSTRAINT/PRESERVATION remain exempt; the rule is a plan-grammar rule and lives with the atomic D-V2-11 bump.
- The prompt's `## KILL-TARGETS` example becomes the new grammar (`TARGET-ID: src/widget.py::parse | MUTATION: neutralise`); the skills (`plan-authoring`), fixtures and the grammar table move atomically.
- **`kill_declared` disposition:** ratification requested — (a) remove the key once the runner exists, or (b) keep it with `executed: false` for anything the runner cannot finish; either way the eval line must speak the fact and stop naming the grammar.

### 5.2 Cell-side runner (3-6)

- Public seam (new): `run_kill_checks(bundle, bindings, *, port, executor, deadline)` — constructed in the same family as the existing public oracle (`kill_attribution` — same module; a new module would duplicate the in-band rendering and the parse contract).
- Per target (port required):
  1. Read candidate source via `port` (as `_read_port_source` does today — the only file the harness may read from the pinned view, per the V1 in-band precedent).
  2. Build baseline command: `oracle_argv` over the sealed nodeid, rendered in-band (the sealed-collection pattern); no overlay.
  3. Build mutated command: the same argv, carried inside the scratch overlay (the V1 `_build_inband_kill_command` pattern, generalized), with the mutated file's bytes.
  4. `apply_kill` (pure AST, unchanged), provenance probe (unchanged), pytest, JUnit block per command.
  5. Parse both reports (`parse_inband_nodeids` → `_classify` → `NodeRun`).
  6. `attribute(binding, baseline=…, mutated=…)` → `KillAttribution`; one judge, not two.
  7. `KillCheck` per target, verdict from the closed vocabulary (`SliceVerdict`), `detail` required for non-`PROVEN`.
- `port is None` → `ERROR` (not skip, not refuse) — the same rule V1 has ("managed kill-check requires a pinned WorkspacePort").
- The F9 refusal: `acceptance_collection.verify_sealed_acceptance` refuses a non-empty `kill_required` **until the runner exists**; with the runner, it delegates and the refusal applies only to the unavailable-substrate case (port missing) and is never a proxy for "the mutation did not run" — that is a `ERROR` on the claim, never a refusal on the run.
- `kill_attribution.run_node_oracle` in-band: a managed executor never receives a report path on the host; the report travels in the receipt (the same pattern as `collect_sealed_nodeids_inband`).
- `_junit_block` is not relaxed: two commands, two one-block receipts.
- The F9-stated boundary **does not move**: no second substrate, no second profile, no second view, no second store. The scratch the read-only profile already grants is used; the cell-side overlay is harness-built and stays harness-built (CT-3.6).

### 5.3 Artifact and eval (desired behavior)

- Claim evidence carries the executed mutation (`mutation={operator, target, verdict, detail}`) on the claim whose contract the target names. The attempt's total rule (`claims-total-mismatch`) is unchanged.
- `kill_required` fills from the declared targets the day the runner lands; `kill_declared` becomes empty or is removed (ratification requested, §2.2 (sub-decision 3)).
- The eval line stops hardcoding "the V2 grammar expresses attribution only"; it reports the actual verdict (e.g. `mutation neutralise src/widget.py::parse: proven` or `vacuous — the oracle still passes`).
- The artifact `verification.json` key set is additive; `kill_required` is the canonical list of the executable targets.

### 5.4 Architectural boundary (standing constraint)

No authority/profile change. No host fallback. No new command string in production — the cell-side bootstrap is a harness-built command (CT-3.6: "the fence never drives a result"). The runner reuses `_build_inband_kill_command`'s provenance and scratch contract and changes only its argv and its report destination. Everything else already exists: `apply_kill`, `_PROVENANCE_PROBE`, `run_commands`, `_junit_block`, `parse_inband_nodeids`, `attribute()`, `verify_sealed_root`.

---

## 6. Ratification requests (the exact ask)

1. **Q-V2-SLICE3-5 = A + obligation** — shape (`path::symbol` + `MUTATION` field), the obligation rule, the duplicate-id admission rule, with the atomic grammar bump (plan_v2, schema, prompt, skills, fixtures — D-V2-11).
2. **Q-V2-SLICE3-6 = (a)** — harness-owned cell-side bootstrap; two commands per target; sealed argv (not `KILL_CHECK_COMMAND`); port plumbed; `run_node_oracle` in-band.
3. **The `kill_declared` disposition** — remove the key once the runner lands, or keep it for the not-executed case; either way the artifact must stop hardcoding "V2 grammar expresses attribution only".
4. **The `ADMISSION_RULES_V2` namespace + contract_id regex** — extend the V2 contract-id regex to the `CT-<slice>.<n>` shape and name the `plan-v2` namespace; rides the same atomic change as 1.
5. **CT83 V2 equivalence** — same shape, same audit rule; rides the same change set as 1.

**Explicitly not requested:** option (b)/(c)/(d) of 3-6; option B/C of 3-5; a change to `KillOperator`'s two-member set; a change to the sealed-argv contract; a second seal or a second runner.

---

## 7. What must not be re-opened

- Q-V2-SLICE3-4 = A (declared, `executed: false`) — the artifact's `kill_declared` is the only record of a declared target that never ran; changing it without the runner landing would erase the distinction it exists for.
- Q-V2-SLICE3-3 = A (one vocabulary, derived constants).
- D-V2-5, D-V2-11, D-V2-12, D-1…D-13, F10's composition rule (one attempt log), F9's refusal for the pre-runner window.
- The F10 correction: the controller branches on the snapshot's grammar, not on "are there commands".

---

## 8. Gate debt and verification posture

- 4 gates recorded on `23d5d03` (ruff 0, ruff-format 7, mypy 62/29, authoring-check 0); pytest **not recorded** (operator chose not to wait; the background run is in `/tmp/head-suite.log`).
- No new test was run for this document (documentation only). Deliverables in this turn are documentation only; **no production change made in this turn.**
- Add the classification rows in §4 to the plan's ratification register (§7) and to the ledger as the natural follow-up of E628/E629; the ledger entry for this turn is E630.

---

## 9. The one-paragraph version

The system is a closed loop in which an artifact produced by a model is checked by something other than the model that produced it, and the check cannot be talked around — not by the plan, not by the author, not by "it finished". Q-V2-SLICE3-5 and Q-V2-SLICE3-6 are the two questions that decide whether that loop holds on the mutation axis. Both are recommendable now, with exact grammar and cell-side behavior, and both must wait for the operator's ratification before any code moves. The meaning of the system is the reason the answers must be exact: a target that is a site is a claim the planner cannot talk around; a mutation that runs in the cell is a check no plan can route around.
