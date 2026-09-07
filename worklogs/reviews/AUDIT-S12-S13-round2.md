# Adversarial audit, round 2 — S12/S13 and the surfaces round 1 never looked at

Round 1 audited **my own diff**. That is the wrong boundary for a
context/prompt-assembly system with deterministic contract validation: the
diff is one participant in a pipeline whose other halves (prompt registry,
extractor, artifact store, secret redactor, sandbox) carry the actual
guarantees. Round 2 audits the **seams**.

Why round 1 stopped early, stated plainly: I confused *"I have no more
questions about my code"* with *"the system has no more defects."* Exhausting
the author's imagination is not coverage. All 12 findings below sit outside the
lines I wrote, yet every one of them is load-bearing for S12/S13's promise.

All findings reproduced against running code.

---

## B-1 (SECURITY, new class) — S13 opened a secret-egress path around the redactor

`ADR-12` establishes a single input-side chokepoint: `_redact()` at
`coder_loop.py:2090`, applied to **tool results**. `SecretGuard` is
`BEFORE_TOOL_EXEC` — it guards tool *calls*.

S13 pastes `git diff` output into the **task string**, which reaches the
provider without touching either:

```
secret present in the eval TASK text: True     # sk-live-SUPERSECRET-DEADBEEF
```

A coder that pastes a live key into a tracked file (routine accident) now has
that key shipped to the eval provider verbatim, and written verbatim to
`events.jsonl` (`coder_loop.py:651`).

`tests/test_secret_isolation_invariants.py` and
`tests/test_model_egress_redaction.py` both pass — **they only cover the tool
channel.** S13 created a channel the ADR's guarantee does not span. This is the
single most serious finding in either round; round 1 missed it entirely because
I audited behaviour, not trust boundaries.

**Fix:** route the evidence block through `_redact()` before it enters the task.

## B-2 (DETERMINISM) — the contract is mutable by the party being judged

`WorkflowContext.plan_text()` says *"Read the plan once"*. It does not — it
re-reads on **every call** (3+ per eval stage: `:174`, `:457`, `:639`, `:643`).

`SandboxHook` has `allow_general_write=True`; a workspace-resident plan is
writable:

```
plan INSIDE workspace  -> Decision(action='allow')
plan OUTSIDE workspace -> Decision(action='deny', 'path escapes workspace')
```

```
read 1 identity: PLAN-ORIGINAL
read 2 identity: PLAN-REWRITTEN
```

So the coder can rewrite the contract it is judged against, mid-run, and
`eval_report.plan_id` (`:639`) can come from a *different read* than the
slice list `validate_slice_ids` used (`:643`). For a system whose stated
purpose is *deterministic contract validation*, the contract is neither
immutable nor snapshotted.

**Fix:** read once at `run_workflow` entry, hash it, carry the text + digest as
frozen data. Warn if the file changes mid-run.

## B-3 (SILENT DEGRADATION) — a supplied-but-unparseable plan validates nothing, silently

`_SLICE_RE = ^#{2,4}\s+(?:Step\s+)?(S\d+[a-z]?)\s*:` — heading-only, colon
required, lowercase suffix only. Real formats it rejects:

| Plan form | Extracted |
|---|---|
| `### Step S1: a` | `('S1',)` ✅ |
| `### Step S1 — a` (em-dash) | `()` |
| `### Step S5A: a` (uppercase suffix) | `()` |
| `##### Step S1: a` (5 hashes) | `()` |
| `  ### Step S1: a` (indented) | `()` |
| `\| S1 \| do a thing \|` (table) | `()` |
| `- S1: do a thing` (list) | `()` |

Consequence, with `--plan` explicitly supplied:

```
plan supplied, 2 real slices, eval invents S99
  kept: ['S99']   unreported: ()   warnings: ()
```

**S12 silently did nothing.** The operator asked for validation, got none, and
was told nothing. My own `test_plan_with_no_declared_slices_omits_the_slice_line`
codifies this as correct. "Legacy plans failing is expected" (operator ruling)
means *don't fail the run* — not *don't mention it*.

**Fix:** warn when `--plan` was supplied but zero slices were extracted.

## B-4 (UNBOUNDED INPUT) — the untracked list has no cap

I bounded the diff at 60k and left the sibling list unbounded:

```
block total chars   : 170140
untracked line chars: 170026
diff cap            : 60000
```

5,000 root-level untracked files → a 170k-char task, ~3× the cap I reasoned
about. Any `node_modules`/build output in a repo without `.gitignore` does this.

## B-5 — the harness reports its own logs as the coder's deliverables

```
New untracked files (5): .fa/, .venv/, __pycache__/, node_modules/, real_work.py
```

`.fa/` is the harness's own run directory. Also note git collapses directories,
so "read them with fs_read_file" points at **directories, not files**.

## B-6 (TOCTOU) — the block is a snapshot of whenever eval ran, not what the coder produced

```
at coder finish -> judge would see CODER_WORK: True
at eval time    -> judge sees CODER_WORK:      False
                   judge sees SOMETHING_ELSE:  True
```

The coder has `fs_spawn_subagent`; the operator shares the workspace. Nothing
pins the evidence to the stage boundary.

## B-7 — in a repair loop the diff grows monotonically

```
eval round 0: ['round1.py']
eval round 1: ['round1.py','round2.py']
eval round 2: ['round1.py','round2.py','round3.py']
```

Round N re-judges all prior rounds, and the diff can cross the truncation cap
mid-loop — so the *same* code becomes invisible as the loop proceeds.

## B-8 — truncation drops by git's file order, not by importance

A 9,000-line filler change in `a_big.py` evicted `z_critical.py`'s
`DELETED_THE_AUTH_CHECK = True` from the diff body (the stat still lists the
file). One noisy lockfile hides the security-relevant hunk.

## B-9 (GOVERNANCE) — the S13 block violates ADR-10 I-6 on all five clauses

I-6: injected prompt payloads MUST be registered, resolved once per invocation,
role-gated, default to `observe`, and be introspectable without running the
model. The S13 block is:

1. **Unregistered** — `INJECTION_SPECS` contains only `coder_slice_ceremony`.
   I-6 explicitly forbids "a call site composing a payload the registry does
   not know about". Mine is exactly that.
2. **Re-read mid-run** — `plan_text()` per call (B-2).
3. Role-gated in an `if`, not by the registry.
4. **Always `enforce`** — no `off`, no `observe`, no flag.
5. **Invisible to `fa inject`** — the introspection command shows one row.

I read ADR-10 I-6 while writing S12/S13 (it is in my own workspace notes as
"owns injected prompts") and still shipped an ad-hoc injection. Round 1 didn't
catch it because I audited behaviour, not governance.

## B-10 — the judge is never told the block is authoritative

`grep "Evidence supplied by the harness" src/ knowledge/` → only the controller.
The eval system prompt (`prompt.py:857`) never mentions it, so the judge cannot
distinguish harness-authored evidence from the coder-authored diff inside it —
which is what makes A-7's injection surface exploitable.

## B-11 — artifact identity is inconsistent and collision-prone

`eval_report.plan_id = PLAN-REAL-IDENTITY` but
`flow_state.active_plan_id = idmix` (the run_id). S12a upgraded one artifact
and not the other; four call sites still pass `ctx.run_id`.

`run_id = wf-<unix_seconds>-<slug>` collides at 1s granularity — two runs of the
same task in the same second share `eval_report.json` and `flow_state.json`.

## B-12 — repair history is destroyed; T16e still unwritten

Per stage D-1 holds (1 write). Across an adaptive loop: **3 writes to the same
path**, last-writer-wins. Rounds 1–2 are unrecoverable, so *why* the loop ran is
not auditable. S6a (append-only packet log) is the intended fix and is not built.
T16e ("written exactly once") is still listed as an exit criterion with no test.

---

## Round-1 findings this round strengthens

**A-1** is worse than reported. My `test_clean_worktree_says_so_explicitly`
does not merely miss the commit case — it **encodes the bug as correct**. Of 15
S13 tests, every `git commit` call establishes a *baseline before* the work;
none commits the work product. The suite is structurally incapable of failing
on A-1, which is why 11/11 mutants died while the feature was broken.

---

## Revised state

| Property | Status |
|---|---|
| P1 judge receives the contract | ⚠️ works, but B-2/B-3 make it unverified and mutable |
| P2 judge receives the work | ❌ A-1, B-6, B-7, B-8 |
| P3 unjudged slice cannot pass | ❌ A-2 |
| P4 failed slice cannot pass | ✅ Q16 works |
| P5 repair can converge | ❌ A-3 |
| **P6 no secret egress** (unstated, assumed) | ❌ **B-1** |
| **P7 injections are governed** (ADR-10 I-6) | ❌ **B-9** |

Round 1 measured against the plan. The plan never stated P6 or P7 — they are
ADR-level invariants the plan silently assumed, and both are now violated.

**Fix order:** B-1 (security) → A-1/B-6 (base-commit snapshot, fixes B-7 too) →
B-2/B-3 (freeze + warn) → A-2 (Q17) → B-9 (register the injection) → A-3.

---

## Disposition

All findings in this note are consolidated into **PLAN §27 — SLICE S15
(BLOCKING)**, with a `GAP#` row, a contract card, a falsifiable `T#`, and a
named kill-check for each. S6/S6a/S6b/S7/S11b/S8/S9 are on hold until S15 lands.

Blocking operator decisions: **Q17** (unjudged slice ⇒ REPAIR / BLOCKED / warn)
gates S15d; **Q18** (I-6 default-mode vs shipped always-on) gates S15g.
