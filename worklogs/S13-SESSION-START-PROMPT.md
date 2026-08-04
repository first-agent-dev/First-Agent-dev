# S13 session-start prompt

Paste everything below the line into a fresh session.

---

## Task

Continue the First-Agent CLI/formal-trace substrate re-baselining workplan at
**Slice 13 (S13) — multi-provider conformance**. S11 (live controlled
deployment) is complete: 10 of 12 steps pass, 2 blocked by one P1 defect that
S13 exists to fix.

**Do not write code yet.** First task is: clone, set up the environment, read
the plan and the code it touches, and give me a source-verified assessment of
current state. Then stop and report before any edit.

## Repository and patch

```bash
git clone https://github.com/first-agent-dev/First-Agent-dev.git
cd First-Agent-dev
git checkout 35068c60e3977582498b2b1448876493a5a9effb
git am --3way patches/S13-on-35068c6.patch     # 9 commits, docs+scripts only
```

`patches/S13-on-35068c6.patch` — `sha256 daa9c73293b56661f9b494ec1fdb3cbffb2262a394b2215d1ce700f36d94c2e6`.
It touches only `knowledge/BACKLOG.md`, two plan files under
`worklogs/implementation-plans/`, and two helper scripts under
`worklogs/s11-scripts/`. **Zero `src/` changes.** If `git am` reports the
commits already present, they were merged upstream — verify with
`ls worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md`
and continue.

> `git am` **applies and commits**. A clean `git status` afterwards is correct,
> not a failure.

## Environment (the sandbox resets; `uv` and `just` disappear)

```bash
pip install -q uv
curl -fsSL https://just.systems/install.sh | bash -s -- --to /usr/local/bin
uv sync --frozen --extra dev
git config user.email "fa@local" && git config user.name "fa"
```

**Two instrument checks before trusting any measurement.** Both have produced
false results in this workplan:

```bash
uv run python -c "import fa; print(fa.__file__)"   # must be <repo>/src/fa/__init__.py
uv run which pytest                                 # MUST resolve inside .venv/
```

`uv sync` has reported *"Checked 76 packages"* while `.venv/bin/pytest` did not
exist; `uv run pytest` then silently used the system binary and reported
`ModuleNotFoundError: No module named 'fa'`. The `import fa` probe alone is
**not** sufficient.

Also run `git diff --numstat` — a 16-file, 0-line mode-only drift appears after
resets. Restore with `git checkout -- scripts/ src/fa/hygiene/hooks/`.

**Baseline to reproduce before changing anything:**
`2461 passed, 15 skipped, 1 xfailed`, coverage **83.22%**, `fail_under = 80`.

## Read these, in this order

1. `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md`
   — **553 lines, the slice you are executing.** Closed core S13.0–S13.4c,
   open exploration S13.5–S13.9, contracts CT1–CT8, kill-checks K1–K10,
   open questions **Q61–Q65** (Q59/Q60 are already answered — see below).
2. `worklogs/implementation-plans/PLAN-cli-trace-S11-controlled-deployment.md`
   — the live evidence S13 is built on. Read the execution notes at the end
   (R10–R26 and the step results); they are the empirical basis for the design.
3. `knowledge/BACKLOG.md` — I-46 through I-53 are this slice's findings.
4. Source S13 touches: `src/fa/inner_loop/prompt_composer.py:96-125`,
   `src/fa/inner_loop/coder_loop.py:408-409,450-490,1124,1367-1379`,
   `src/fa/providers/chain.py:330-368`, `src/fa/providers/registry.py:25-58`,
   `src/fa/roles.py:186-230`, `src/fa/providers/base.py:52,126`.

## The defect S13 fixes (root-caused, do not re-derive)

`fa workflow planner,coder,eval` cannot complete. Stage 2 dies at turn 1 with
`in=0` and, recovered from the deployed `events.jsonl`:

```
status=400 code=3230 type=invalid_request_message_order
"Expected last role User or Tool (or Assistant with prefix True) for serving but got assistant"
```

Mechanism, confirmed in source:

- `prompt_composer.py:123-125` appends the task as `user`, **then**
  `non_cacheable.extend(observations)` — history lands *after* the task;
- `coder_loop.py:450-490` rebuilds history as `assistant`/`tool` messages only
  and **never replays `user_msg`** (that is I-52);
- `cli.py:1248` passes `resume: not fresh`, so stage 2 inherits stage 1's
  transcript, which ends on an assistant message.

Explains all four observations: standalone `fa run` 200 (empty history, `user`
last) · planner stage-1 200 (`fresh`) · coder stage-2 **400** (`resume`,
assistant last) · turn 2+ 200 (`tool` last). **Not model-specific, not
role-specific.**

Local tests missed it because S8 drives the workflow through a **scripted
transport that accepts any message order**, and
`_assert_tool_pairing_invariant` (`coder_loop.py:176`) checks tool-call/result
*pairing*, never the *final role*.

## Decisions already made — do not reopen

- **Q59** — fix FA's own composition bug first, build from there.
- **Q60** — fix the history rebuild (I-52) too, not defer it.
- **Eval family-disjoint → adversarial, not blocking** (S13.4c). The current
  gate raises `EvalFamilyConflictError`; the live box passes it while running
  `mistral-small` in all three roles, because the YAML says `family: "mistral"`
  for coder and `"mistral_eval"` for eval. Replace refusal with a loud recorded
  warning plus an adversarial eval stance, and record the stance in
  `eval_report.json`. Amend ADR-2 in the same commit. **Family *validation*
  stays** — only *disjointness* relaxes.
- **Repair by reordering FA's own messages, never by injecting synthetic
  assistant text.** LibreChat's `"Understood."` approach is rejected: it
  pollutes the transcript the model reasons over and costs tokens every turn.
- **Capability flags, not provider-name branching.**
- **I-37 (context cost) is out of scope** — see Q65 for the reasoning.

## Working agreement

- **Before editing:** state source-verified current behaviour; name the contract
  and gap IDs; list exact files allowed to change; stop if a blocking question
  is unresolved.
- **Per edit:** intent · current vs target behaviour · exact mechanism ·
  production rationale · failure behaviour · DoD · negative proof ·
  tests-writing class (C0/C0p/C1/C2/C3) · producer kill-check target.
- **After each edit:** run targeted tests, run static checks on changed files,
  inspect `git diff`, report **actual command output**. Never mark a slice
  complete from "no exception".
- **After a big chunk:** targeted mutation testing.
- **Stop rule:** a new policy choice becomes a Q#, not an assumption.
- **NO `noqa` waivers.** Fix the design.
- `just check` is the real gate, not the Makefile. It runs everything through
  `uv run`; a bare-`pip` setup does not run the real gate.
- Deliver `.patch` files in `patches/` (gitignored); the operator cannot receive
  a git push.
- Ceremony: **lean**. Ask when intent is ambiguous.

## The lesson this workplan keeps re-teaching

Of ~26 defects S11 surfaced, **six were the measuring instruments, not the
product**: a gawk builtin that silently printed 0; a `hits[:10]` that truncated
away the very strays the check existed to find; a wrong `--output` flag that
made a contract check pass on an argparse error; a `pgrep` pattern that matched
its own wrapper; an empty `$DEPLOY_SHA` that made a comparison unfalsifiable; an
unset `SID` that made `sqlite3.connect()` fabricate an empty database.

**Every one produced confident, well-formed, wrong output. None crashed.**

S13 builds a conformance matrix — a grid of green cells, exactly that shape. Its
§D5a makes three rules binding: every CONF case carries a positive control;
every case must be shown to **fail** before it is trusted; no truncation in any
matrix output.

## First deliverable

A written assessment covering:

1. env verified (both instrument checks, baseline reproduced);
2. what you found reading the S13 plan and the source it names — including
   anything you believe is **wrong** in the plan;
3. the concrete first slice you propose (expected: **S13.0 + S13.1**, both
   no-edit / oracle-first);
4. any Q# you need answered before editing.

Then stop.
