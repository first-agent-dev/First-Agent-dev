# F6 Research — IntentGuard + `pr_prepare`: the intent-declaration seat

**Defect:** F6 in [`worklogs/reviews/S12.7-LIVE-VERIFICATION-FINDINGS.md:205-219`](S12.7-LIVE-VERIFICATION-FINDINGS.md)
**PR taken over:** [#68](https://github.com/first-agent-dev/First-Agent-dev/pull/68) (S12.7 F1/F4/F7/F8/F9)
**Tip verified against:** `fc1f2e68144f2a9f4fd279c21fb619842d69cc70`
**Status:** research + verification. No code changed. Deliverable is this doc; the plan it feeds is `/plan-authoring` work, gated on §9 decisions.

**Revision 3** — rev 1 verified the defect; rev 2 reframed it against the founding sources (Q-15, AP-001, AP-003, ADR-10 I-1, ADR-8, ADR-11); **rev 3 re-baselines the goal and folds in the redesign** per operator direction. §§1–4 are rev 2's verified findings, unchanged. §§5–8 are new.

---

## 0. What rev 2 established (carried forward)

Rev 1 treated F6 as two independent bugs: an over-broad bash classifier and an under-documented tool schema. Both findings stand and are re-verified below.

Reading the founding sources changes the **diagnosis**, not the evidence. Three things emerged that rev 1 could not see:

1. **Q-15 rejected option (c) already decided this**, in 2026-05-25, before any code existed. It rejected "declare-after-the-fact" enforcement on explicit AP-001 action-count grounds, and chose **buffer pre-population** — the harness writes a filled template, the agent edits it. `pr_intent.py` implements exactly that (`render_prepare_buffer`, `pr_intent.py:307`). **The git-hook seat uses it. The harness seat does not.** `pr_prepare` asks the LLM to compose the whole header from nothing.
2. **The `Decision.modify` seat already exists** in the hook contract (`hooks/base.py:76`), with re-validation replay machinery (`hooks/base.py:180-200`) built for exactly this — and **no middleware in the codebase uses it.** The affordance for "repair the call instead of denying it" is built and unwired.
3. **`_publish_scope_estimate` (`cli.py:1920`) is the exact architectural precedent** for what the intent seat should be: a deterministic pre-classifier that computes a verdict *before the model's first token* and injects it as turn context. Intent is a strictly easier classification problem than scope, and the classifier for it already exists (`classify_intent`, `pr_intent.py:164`).

So the reframed finding is: **F6 is not a bug in the intent seat. It is the intent seat having drifted into the exact shape its own founding document rejected.** The current implementation is a *validator* placed where a *scaffold* was specified. Every symptom in the SSOT follows from that one inversion.

This matters for the fix. Rev 1's plan (widen whitelist, document schema, soften errors) treats symptoms and would leave the inversion in place. Rev 2 proposes closing the inversion, which subsumes most of rev 1's changes and makes two of them unnecessary.

---

## 1. Design intent, from the sources that predate the code

### 1.1 What the module was for

Operator statement (this session), which the sources corroborate:

> "make llm state its intents exactly before using code or doc edit tools" · "some form of *inherited context*" — the model writes its plan and continues following that trajectory · "garbage in → slop out — I want to fight that by tailoring context on input and steering llm to the right path"

That is a **context-engineering** goal. The draft is a *trajectory anchor*: a short, self-authored statement that enters the model's own context and biases every subsequent turn. Its value is that the model wrote it and can see it.

AP-001 §Why-the-wrong-shape-dominates (`knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md:112-119`) states the operating theory:

> "Adding rule #N+1 to AGENTS.md fixes nothing — it competes with rules 1..N for attention and loses under load. **Action-count drift dominates rule-count drift in weaker LLMs**; the structural fix must reduce the number of actions the LLM has to take to surface the contradiction, not add to it."

And AP-001:130-136 on the mechanism itself:

> "Cognitive load: «label your fix» (**one action**). The act of writing «CLASS: WORKAROUND, INVARIANT: …» makes the contradiction visible to the agent **mid-write**, and to the reviewer in two seconds."

**One action. Visible mid-write.** That is the whole design. The declaration is cheap by construction, and its value is the self-authored visibility, not the validation.

### 1.2 Q-15 rejected option (c) — verbatim, and decisive

[`knowledge/trace/exploration_log.md:1352-1367`](../../knowledge/trace/exploration_log.md), 2026-05-25, before `pr_intent.py` existed:

> **(c) PR-description-only enforcement (no `prepare-commit-msg` hook).** Reason: PR descriptions are post-hoc prose, written after code is complete. The action-count cost of «remember to write the four-line header AFTER writing the code» is the exact failure mode AP-001 §Why-wrong-shape-dominates lines 116–119 catalogue … **A pre-commit hook that pre-populates the buffer before the agent composes is an action-count cut, not a rule addition.**

The chosen design is **pre-population**: the harness computes the intent, renders a filled template, and the agent *edits* it. The agent is never asked to produce the structure from nothing.

`pr_intent.py` implements this faithfully for the git seat:

```python
# src/fa/hygiene/pr_intent.py:307-322
def render_prepare_buffer(intent: Intent) -> str:
    """Render the ``prepare-commit-msg`` pre-populated header block."""
    lines: list[str] = []
    for field in derive_required_fields(intent):
        if field.name == "INTENT":
            lines.append(f"INTENT: {field.placeholder}")   # mechanically filled
            continue
        lines.append(f"{field.name}: <fill me — {field.placeholder}>")
    return "\n".join(lines)
```

Consumed at `pr_intent.py:928` inside `_cli_prepare` — the git hook. **`render_prepare_buffer` has exactly one production caller, and it is not the harness.** Verified by exhaustive grep: the only other references are `hygiene/__init__.py` re-exports, the codemap row, and `tests/test_pr_intent_snapshot.py`.

### 1.3 The inversion, stated precisely

| | git-hook seat (M-6) | harness seat (M-7) |
|---|---|---|
| classifier runs | ✅ `classify_intent` on staged diff | ✅ `classify_intent` on projected paths |
| **template pre-filled for the agent** | ✅ `render_prepare_buffer` | ❌ **nothing** |
| agent's action | **edit** a filled buffer | **compose** from a bare schema |
| on malformed input | buffer already valid; validator rarely fires | deny → retry → deny → retry |
| action count | 1 (fill placeholders) | 4–6 (discover schema, then comply) |

Both seats share the validator, satisfying ADR-10 I-1. **Only one seat inherited the scaffold.** The harness seat — the *earlier, cheaper* seat that AP-001 says should carry the lower action count — is the one that got the higher one.

The operator's diagnosis in this session is exactly right, and now has a citation:

> "exactly as expected llm does not write exact sentences as first instinct - it's random by design"

Q-15 knew this in May. That is *why* it chose pre-population. The harness seat regressed to the rejected option.

### 1.4 ADR-11 already flagged the risk class

[`knowledge/adr/ADR-11-authoring-guardrails.md:509`](../../knowledge/adr/ADR-11-authoring-guardrails.md) lists in its "what existing seats already catch" table:

> | Intent before mutation (`pr_prepare` / IntentGuard) | Feature never called from `drive_session` |

ADR-11 treats `pr_intent.py` + IntentGuard as **production-grade seeds** it formalises rather than invents (`ADR-11:53-54`, `:393-394`). A seed that lost half its mechanism in transplant is precisely the "Present ≠ Wired ≠ Correct" class ADR-11 §I9 exists to catch — here at sub-feature granularity: `render_prepare_buffer` is present, tested, exported, and **unwired at the seat that needs it most.**

---

## 2. Verification of the SSOT's F6 claims (rev 1 findings, re-confirmed)

All citations re-resolved line-exact at `fc1f2e6`.

### 2.1 The gate fires on classified *effect*, not on tool name

[`intent_guard.py:121-127`](../../src/fa/inner_loop/hooks/intent_guard.py) — `_DRAFT_REQUIRED_BASH_EFFECTS = {INDEX_WRITE, REPO_WRITE, OPAQUE_EXEC}`; [`:226-232`](../../src/fa/inner_loop/hooks/intent_guard.py) — `_requires_draft`. `READ_ONLY` / `VERIFY_ONLY` are genuinely exempt. Design is sound; **the classifier rarely returns those two labels.**

### 2.2 `OPAQUE_EXEC` is the practical default — measured, not inferred

Executed the real `analyze_bash_for_intent` against real `bashlex` at the tip:

| classified safe | classified `OPAQUE_EXEC` → **draft required** |
|---|---|
| `ls`, `cat … \| head`, `git status`, `grep -rn`, `wc`, `pytest -q`, `python -m pytest`, `mypy --strict`, `ruff check` | `seq`, `sort`, `uniq`, `cut`, `tr`, `nl`, `jq`, `sed -n`, `awk`, `basename`, `dirname`, `realpath`, `readlink`, `sha256sum`, `ps aux`, `env`, `command -v`, `type`, `gh pr view`, **`uv run pytest`**, **`.venv/bin/pytest`**, `just check`, `python3 --version`, `for …; do …; done`, `{ echo A; seq 1 10; }`, `ls $(pwd)` |

Terminal fallback: [`bash_intent.py:493`](../../src/fa/inner_loop/bash_intent.py). Whitelist: [`:62-99`](../../src/fa/inner_loop/bash_intent.py), 33 verbs. Verifier matcher: [`:247-280`](../../src/fa/inner_loop/bash_intent.py), 4 families.

Three amplifiers: max-severity reduction ([`:192-193`](../../src/fa/inner_loop/bash_intent.py) — one opaque clause poisons the command); compound/brace/loop nodes unconditionally opaque ([`:174-177`](../../src/fa/inner_loop/bash_intent.py)); any word expansion opaque ([`:571-575`](../../src/fa/inner_loop/bash_intent.py)).

Two of these are **inconsistencies, not policy**: `.venv/bin/pytest` is opaque while `pytest` is verify-only, because `_is_read_only` basenames its head ([`:287-289`](../../src/fa/inner_loop/bash_intent.py)) and `_is_verify_only` does not — sibling predicates in one module disagreeing. And the module already argues the basename case for interpreters at [`:426-433`](../../src/fa/inner_loop/bash_intent.py).

Note what this means for the draft's *purpose*: a draft demanded before `sha256sum` is not an intent declaration. It is a toll. It teaches the model that the draft is noise to be cleared, which actively corrodes the "inherited context" value the module exists for.

### 2.3 The ceremony, replayed from the event logs

`cae-s127-bash-tail-1788526685-1245712.events.jsonl`:

| turn | tool | outcome |
|---|---|---|
| 1 | `fs_run_bash` | **DENY** missing draft |
| 2 | `pr_prepare` (6 keys) | `` `fix_class` is only valid when `intent` is `FIX`; got `RESEARCH` `` |
| 3 | `pr_prepare` (**byte-identical 6 keys**) | same error |
| 4 | `pr_prepare` (5 keys) | `` `degree_of_freedom_closed` is only valid when … `` |
| 5 | `pr_prepare` (4 keys) | `` `deterministic_mechanism` is only valid when … `` |
| 6 | `pr_prepare` (2 keys) | ok |
| 7 | `fs_run_bash` | ok — *objective begins, turn 7 of 10* |

`cae-s127-bash-stderr-1788527120-1246970.events.jsonl`: same staircase, 2 blind bash retries first, objective on turn 7.

**6 wasted turns each.** SSOT said "~5" — understated. Turn 3 re-sent an identical payload: the signature of an error that says what not to have done and not what to do.

### 2.4 The staircase is mechanically forced

[`prepare_pr.py:136-168`](../../src/fa/inner_loop/tools/prepare_pr.py) — `_validate_fix_fields` returns `str | None`: **first violation only**. N surplus fields → N round-trips, by construction.

Its docstring ([`:143-149`](../../src/fa/inner_loop/tools/prepare_pr.py)) says this is deliberate: *"fails fast so the LLM sees a focused error message rather than a six-violation dump for what is conceptually one omission."* Correct for the **missing**-field direction. Exactly backwards for the **surplus** direction, where N surplus fields are also one mistake ("I sent the FIX shape for a non-FIX intent") but cost N turns.

### 2.5 The schema is silent, and the description actively misleads

[`prepare_pr.py:67-97`](../../src/fa/inner_loop/tools/prepare_pr.py): **4 of 6 properties carry no `description`.** The conditional rule (`fix_class` / `degree_of_freedom_closed` / `deterministic_mechanism` valid **iff** `intent == FIX`) exists only in Python.

[`prepare_pr.py:269-278`](../../src/fa/inner_loop/tools/prepare_pr.py) — the description *names* the FIX-only clauses in a parenthetical reading as an inventory of accepted fields, never saying "only when FIX". A model optimising for compliance sends all five. Both runs did.

**The same lesson was already learned and half-applied.** `invariant` got an inline description under S12.5/CT5 ([`:78-87`](../../src/fa/inner_loop/tools/prepare_pr.py)) with the comment *"the model reads this schema, not the skill doc (live-trial D11: agents burned turns rediscovering the old `n/a` literal)"*. The other four were skipped. F6 is D11 recurring in the skipped fields.

### 2.6 `_render_draft` already discards what the validator rejects

[`prepare_pr.py:121`](../../src/fa/inner_loop/tools/prepare_pr.py) — the renderer emits FIX-only clauses **only** `if intent == Intent.FIX`. **The validator rejects a call the renderer would have handled correctly.** The surplus fields were never going to reach the draft. Six turns were spent enforcing a constraint with no effect on the artifact.

One tool over, `fs_search` answers the identical question the opposite way — [`fs_search.py:65-77`](../../src/fa/inner_loop/tools/fs_search.py) accepts inapplicable params, drops them, and reports via top-level `ignored_params` (the F8 fix in this very PR). Two tools, same registry, opposite semantics for "caller sent a param that doesn't apply".

### 2.7 Legitimacy table

| SSOT claim | verdict |
|---|---|
| Every `fs_run_bash` gated behind a trusted draft | **partly true** — gate is on classified effect; but `OPAQUE_EXEC` is the practical default (§2.2) |
| First bash call denied | **TRUE** — both logs, turn 1 |
| Burns 3-4 `pr_prepare` calls discovering schema | **TRUE** — 4 and 4 |
| Every FIX-only field rejected before it finds the right shape | **TRUE, and mechanically forced** (§2.4) |
| ~5 wasted turns per bash row | **TRUE, understated** — 6 and 6 |
| Schema undocumented in tool description | **TRUE** (§2.5) |
| Violates forgiving-tools | **TRUE** (§2.6) |
| "Backlog candidate — not in s12.7 scope" | **superseded** — largest measured turn-waster in the slice; I-58/I-59 already open |
| *(implicit)* root cause is the missing schema doc | **INCOMPLETE** — root cause is the missing scaffold (§1.3); the schema gap is downstream |

---

## 3. Root-cause model

One inversion, three consequences. Symptom-chasing on the consequences without naming the inversion is AP-004 (`symptom-chasing-without-model`).

```
ROOT: the harness seat was built as a VALIDATOR where Q-15 specified a SCAFFOLD.
      render_prepare_buffer (pr_intent.py:307) is wired to the git seat only.
      The agent must COMPOSE the header instead of EDITING a filled one.
        │
        ├─ C1  No pre-filled draft → the model must invent structure
        │      → schema-discovery staircase (§2.3, §2.4, §2.5)
        │      → 4 pr_prepare calls
        │
        ├─ C2  Nothing computes intent before the first tool call, though
        │      classify_intent (pr_intent.py:164) is pure and available and
        │      _publish_scope_estimate (cli.py:1920) is the exact precedent
        │      → the gate can only react at BEFORE_TOOL_EXEC, never prepare
        │      → first bash call always denied
        │
        └─ C3  Deny is the only failure mode, though Decision.modify
               (hooks/base.py:76) exists and no middleware uses it
               → a near-miss costs a whole turn instead of being repaired
```

Amplifier, independent of the inversion: the bash classifier's `OPAQUE_EXEC` default (§2.2) makes the gate fire on commands that mutate nothing — inflating C2's blast radius from "before writes" to "before almost any shell".

**Why "seat" is load-bearing.** Q-15 §Coupling and BACKLOG M-7 both frame this as *dual enforcement*: git hook at commit time, middleware at tool-call time, *"the earlier seat is the cheaper one per AP-001"* (`worklogs/BACKLOG.md:918-923`). The earlier seat is currently the **more expensive** one. The architecture is upside-down relative to its own justification.

---

## 4. Where the current design fights the operator's goal

| operator's goal | current behaviour | mechanism |
|---|---|---|
| model states intent **before** editing | model states intent after 1 denial + 4 failed attempts | no pre-fill; deny-only gate |
| "inherited context" — a trajectory anchor | draft's content is whatever cleared the validator; `s127-bash-stderr` shipped `invariant: "n/a"` | validator checks *shape*, never *informativeness* |
| "garbage in → slop out" | the seat that should tailor input spends 6 turns on schema compliance | validator-not-scaffold inversion |
| "push models to the limits" | tests schema-guessing stamina, not reasoning | rejection teaches syntax, not intent |
| forgiving tools (binding) | first-violation reject; `fs_search` does the opposite | §2.6 |
| AP-001: minimise **actions** | 6 actions where Q-15 specified 1 | §1.3 |

The sharpest one: **the draft that finally passed on `s127-bash-stderr` carried `invariant: "n/a"`.** Six turns bought a header that anchors nothing. The gate optimises the one dimension that does not serve the goal (syntactic shape) and does not touch the one that does (does this state a real intent?).

There is a deeper point here worth stating plainly. A validator can only ever check *shape*, and shape is not what the operator wants. You cannot deterministically verify "this is a genuine intent statement" — that is exactly the kind of judgement §1.2's question 4 says should *not* be mechanised. But you **can** deterministically make the good path cheap and the empty path visibly empty. Scaffolding does that; rejection does not. This is why the fix direction is "cheapen and steer", not "validate harder".

---

## 5. Re-baseline — what the seat is actually for (operator, rev 3)

Rev 2 diagnosed the inversion. Rev 3 re-baselines the **goal**, because the operator's workflow moved since the module was built and the module never followed.

### 5.1 The operator's stated pipeline

> "agent always works in git style repos. All changes are commits, final step is pr creation with a note attached. Idea was that pr_prepare note would serve as: **inherited context**, model starts all changes with locking in invariants and continues while following that trajectory; **some function deterministically verifies compliance**; after work is done pr_prepare note text goes in as **part of frontmatter in actual PR's description** + mentioning link to plans, docs, etc."

So the note has a **three-phase lifecycle**, and only phase 2 was ever built:

| phase | purpose | consumer | built? |
|---|---|---|---|
| **1. Anchor** | model locks intent before work; the note enters its own context and biases the trajectory | the model itself | ❌ the note is write-only; nothing re-surfaces it in-session |
| **2. Compliance** | a deterministic function verifies work matches declared intent | `IntentGuard` | ⚠️ built, but checks *header shape*, not *compliance with the declared trajectory* |
| **3. Publication** | note becomes PR-description frontmatter + links to plans/docs | `gh pr create` | ❌ **nothing in `src/fa/` creates a PR.** Verified: no `gh pr create`, no PR-body composer |

**This is the finding that reframes the whole module.** F6's turn-tax is phase 2 misfiring. But phases 1 and 3 — the two the operator actually described as the point — **do not exist**. The module is one-third built, and the built third is the enforcement third.

That explains why it feels wrong. A checkpoint that only ever *blocks*, never *pays back*, is experienced as a toll. Phases 1 and 3 are where the payback lives.

### 5.2 Verified: the anchor is write-only within a session

`pr_prepare` writes the draft (`prepare_pr.py:255`). `IntentGuard` reads it (`intent_guard.py:308`). **Nothing puts it back in front of the model during the session.**

The one place the draft *is* re-surfaced is `--resume`, across sessions:

```
# cli.py:2163-2168
# When resuming, inject the previous session's draft content as
# mutable memory-summary context so the LLM sees the existing
# plan/work-log from turn 1 …
```

**The operator's "inherited context" mechanism already exists and is wired — but only across a `--resume` boundary, never within the session where the trajectory is actually being followed.** Same class as `render_prepare_buffer` (§1.2), `Decision.modify` (§0), `should_load_skill` (§5.6): built, correct, wired to the wrong seat or no seat.

### 5.3 Verified: phase 3 has no implementation at all

Exhaustive grep across `src/fa/`: no `gh pr create`, no PR-body builder, no frontmatter composer for PR descriptions. `pr_intent.py` validates *commit messages* at the git-hook seat; `_cli_validate` (`pr_intent.py:944`) is a commit-msg gate. The draft never becomes a PR description.

So "the note goes into the PR frontmatter" is, in the operator's own words, "mostly in my head and partly written code". Correct — the head part is phase 3.

### 5.4 The two objects, and why the resemblance misleads

`pr_prepare` is **commit-shaped**; the operator's copy-paste protocol is **slice-shaped**. Field-level overlap is one row:

| operator's protocol field | `pr_prepare` equivalent |
|---|---|
| concrete intent | `intent` ✅ |
| which plan contract + gap IDs | — |
| exact files allowed to change | — |
| current behavior → target behavior | — |
| exact code mechanism | `deterministic_mechanism` (FIX-only) ⚠️ |
| production best practice | — |
| failure behavior | — |
| DoD + negative proof | — |
| tests-writing class C0/C1/C2/C3 | — |
| producer kill-check target | — |
| stop rule → promote to Q# | — |

One clean match. Two partial. Eight missing. **These are not the same artifact and should not be forced into one schema** — that is how you get a 6-property object serving two masters, which is the shape that produced F6.

But they are also not unrelated: the slice contract is *upstream* of the commit note. Which gives the answer.

### 5.5 Recommendation on the object question — derive, don't merge

**Three artifacts, one model-facing ceremony, two of them derived.**

```
   ┌─ SLICE CONTRACT ──────────────────────────────┐   ← the ONE thing the model writes
   │  plan_id · slice_id · contract_ids · gap_ids  │     (per implementation slice)
   │  files_allowed[] · current → target           │
   │  mechanism · failure_behavior                 │
   │  dod · negative_proof · test_class            │
   │  kill_check_target · open_questions[]         │
   └───────────────┬───────────────────────────────┘
                   │ mechanically derived, no LLM call
        ┌──────────┴──────────┐
        ▼                     ▼
  COMMIT NOTE           PR FRONTMATTER
  INTENT/CLASS/         slice contracts (all)
  INVARIANT/DOF/        + plan links + doc links
  MECHANISM             + per-slice verification evidence
  (per commit)          (per PR, phase 3)
```

Why derivation rather than merge or extension:

- **The mapping is total and deterministic.** `intent` ← already declared. `INVARIANT: Affects: …` ← `contract_ids` + `current→target`. `DEGREE-OF-FREEDOM CLOSED` ← `current_behavior` (the freedom that exists today). `DETERMINISTIC MECHANISM` ← `mechanism` + `kill_check_target` (which *is* a `path:line`, satisfying the citation rule by construction). **The anti-shallow-fix gate's hardest field becomes a by-product of a field the operator already writes for engineering reasons.** That is the strongest argument in the whole design: AP-003 compliance stops being ceremony and becomes exhaust.
- **§1.2 q4 answers itself.** Derivation is parsing + formatting + lookup — the exact case where the principle says "function, not LLM call". Asking the model to write the commit note *and* the slice contract is asking it to say the same thing twice, which is precisely the action-count drift AP-001 names.
- **One ceremony, richer payload.** Action count stays at 1 (AP-001:130), but the single action now carries the fields the operator actually cares about instead of five commit-message headers.
- **Phase 3 becomes trivial.** If slice contracts accumulate as typed artifacts, the PR frontmatter is a fold over them. No new authoring burden.
- **`pr_prepare` survives as an internal writer.** The model stops calling it; the harness does, from the derivation. Its validator stays authoritative (ADR-10 I-1 intact — one validator, now two *derived* consumers). No deletion, no migration of the git-hook seat, ADR-11:650 seat asymmetry preserved.

**Cost, stated honestly:** this is strictly more machinery than rev 2's C1–C4. It is a redesign, which the operator has folded into this PR. The mitigation is that every piece is a *wiring* of something that already exists — `FlowState` for state, `Decision.modify` for repair, `render_prepare_buffer` for scaffolding, `_publish_scope_estimate` for injection, `skills/_inject.py` for skill delivery, `--resume` draft injection for anchoring. **The redesign adds one new artifact type and one new tool; everything else is connection.**

### 5.6 Operator decisions, recorded

| # | decision | consequence |
|---|---|---|
| Q1 | **Derive, don't merge** (recommended above; operator asked for reasoning first) | slice contract is the model-facing object; commit note + PR frontmatter derived |
| Q2 | **Workflow pipeline only** (`planner → coder → eval`) | chat stays lightweight; the protocol formalises in the coder stage. **Major simplification** — `FlowState` already exists there, and `workflow_controller.py` already owns stage sequencing |
| Q3 | **Harness runs verification and injects real output** | the strongest option. Model cannot claim a green run that did not happen |
| Q4 | **Warn on out-of-scope writes, never block** | forgiving-tools consistent; `files_allowed` is advisory + observable |
| Q5 | **Plan-ID derivation is advisory** — operator is sceptical, citing the `pr_prepare` failure pattern | **correctly sceptical; see §5.7** |
| Q6 | **Stop-rule: first-class tool + halt**, shaped now for a future `ask_user`; backlog for this round | design the seam, don't build the tool yet |

### 5.7 On Q5 scepticism — the operator is right, and the reason matters

> "Not sure we can reliably achieve this — prior pr_prepare situation with consecutive fails is what I expect. I like the idea, but very sceptical."

**This scepticism is correct and generalises into the design's central rule.** The `pr_prepare` failure was not "the model couldn't produce a value". It was: *the harness demanded a value the model had to guess, and rejected wrong guesses one at a time*. Any field where the harness knows the answer better than the model is a field the harness must **supply**, not demand.

Applied to plan IDs: the harness can read the plan file and extract `### S11:` / `**Traces-to:** G7–G11, CT8–CT12` — both are stable conventions in the operator's actual plans (verified in `PLAN-complexity-aware-execution-chat-role.md:1752`, `:1808`). So:

- Parse the plan, offer the **detected** slice ID and contract IDs **pre-filled** in the scaffold.
- Model confirms or overrides.
- Harness verifies the final strings **exist in the plan file** — a substring check, not a schema guess.
- Unparseable plan → field is blank and **optional**, run proceeds. Never a rejection.

**Rule (binding for this redesign): no field may be rejected for absence unless the harness cannot possibly supply or derive it.** The only fields meeting that bar are genuine judgement — `mechanism`, `current→target`, `dod`. Everything else is scaffolded, pre-filled, or optional. This rule is what prevents the redesign from recreating F6 at ten times the surface area.

---

## 6. Design — the slice contract, in the pipeline

Scoped to Q2 (workflow pipeline). Chat role untouched this round.

### 6.1 Where it sits

`run_workflow` already sequences stages and writes `FlowState` before each (`workflow_controller.py:257-271`). The slice contract slots into the **coder** stage:

```
PLANNING ──► PLAN_READY ──► [SLICE_SCAFFOLD] ──► CODING ──► [VERIFYING] ──► EVALUATING ──► DONE
                                  │                              │
                          harness pre-fills            harness RUNS the
                          from plan + classifier       verify commands
```

Two new `FlowStatus` members. `FlowStatus` is already a closed literal with a frozenset guard (`workflow_artifacts.py:50-62`, `:71-84`) — additive, and the existing validator catches typos.

### 6.2 The artifact

`slice_contract.json`, sibling to `eval_report.json` / `flow_state.json`, reusing their atomic-write + typed-parse pattern (`workflow_artifacts.py:510-549`):

```python
@dataclass(frozen=True)
class SliceContract:
    # ── harness-supplied (model confirms or overrides; never rejected) ──
    plan_path: str = ""          # detected from read set / blackboard
    slice_id: str = ""           # parsed "### S11:"
    contract_ids: tuple[str, ...] = ()   # parsed "**Traces-to:** G7–G11, CT8–CT12"
    files_allowed: tuple[str, ...] = ()  # seeded from plan; advisory (Q4)
    verify_commands: tuple[str, ...] = ()  # parsed from plan's verify lines

    # ── model-authored judgement (the only rejectable fields) ──
    intent: str = ""             # reuses the Intent enum — SSOT, ADR-10 I-1
    current_behavior: str = ""   # source-verified, per the operator's protocol
    target_behavior: str = ""
    mechanism: str = ""
    failure_behavior: str = ""
    dod: str = ""
    negative_proof: str = ""

    # ── harness-derived, model may override ──
    test_class: str = ""         # C0/C0p/C1/C2/C3 — derivable from files_allowed
    kill_check_target: str = ""  # path:line — feeds DETERMINISTIC MECHANISM

    # ── phase 1 / stop-rule ──
    open_questions: tuple[str, ...] = ()
```

`test_class` derivation is real, not aspirational: the `tests-writing` skill states the rule as a decision procedure — *"Session / product / loop claim? → C1 (or C2 if CLI-only). Pure helper → C0/C0p"* (`SKILL.md:65`), *"Security? ≥1 adversarial case (C3)"* (`:75`). `path_risk.py` already tiers paths. Files under `src/fa/inner_loop/` touching the loop → C1; pure helper → C0; `_cmd_*` → C2; a hook/sandbox path → C3. Harness proposes, model overrides with a reason.

### 6.3 Phase 1 — the anchor actually anchors

The gap that makes the note feel pointless. Three wirings, all of existing parts:

1. **Pre-fill** the contract from plan + `classify_intent` + `render_prepare_buffer`, inject as turn context via the `_publish_scope_estimate` shape (`cli.py:1920`), respecting the D7 non-cacheable rule (`cli.py:1942-1947`).
2. **Re-surface** the confirmed contract each coder turn as a compact anchor — reusing the `build_skill_anchor` pattern (`skills/_inject.py`) and the observation-block budget (`observations.py`, 1800-char cap with eviction). Full body on entry turn, ~2-line anchor after. **This is the "inherited context" mechanism, applied within the session instead of only across `--resume`.**
3. **Inject `tests-writing`** at the coder stage. Its frontmatter triggers already name this exact case — *"IMPLEMENT or FIX touching src/fa/ that claims product behavior"*, *"writing or changing tests under tests/"* (`SKILL.md:11-13`) — and `should_load_skill` (`skills/loader.py:119`) exists with **zero production callers**. Fourth built-unwired affordance; wire it here.

### 6.4 Phase 2 — compliance that means something

Today: header-shape validation. Target: compliance with the *declared trajectory*, all deterministic, all observable:

| check | mechanism | on violation |
|---|---|---|
| writes stay in `files_allowed` | path compare at `BEFORE_TOOL_EXEC` | **WARNING** (Q4), never deny |
| verify commands actually ran | scan event log for `fs_run_bash` with real exit code | block the `slice complete` transition |
| tests exist for the declared class | `test_class` C1 → ≥1 new/changed test under `tests/` | WARNING |
| kill-check target is real | `resolve_citation` (`pr_intent.py`) — **already built** | WARNING at contract time, hard at commit |
| DoD is not empty under a `src/` diff | structural predicate (§C4, rev 2) | WARNING |

Every one is a pure function over artifacts the harness already holds. No LLM judgement anywhere.

### 6.5 Phase 3 — the note becomes the PR

New, and the operator's stated end-goal. After the pipeline reaches `DONE`, fold accumulated slice contracts into a PR body:

```markdown
---
plan: worklogs/implementation-plans/PLAN-….md
slices: [S11.1, S11.2]
contracts: [G7, G8, CT8]
---
INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: …
DEGREE-OF-FREEDOM CLOSED: …     ← derived from current_behavior
DETERMINISTIC MECHANISM: …      ← derived from mechanism + kill_check_target

## S11.1 - <target_behavior>
Verification: <actual command output captured by the harness>
```

Deterministic fold, no LLM call. Whether it writes the body to a file for `gh pr create -F` or shells out is a §8 decision.

### 6.6 Q3 — the harness runs verification

The strongest lever the operator chose, and the reason it works: `verify_commands` come from the **plan**, not the model, so the harness executes a command the operator authored.

- Runs after the coder stage signals slice-done, before `EVALUATING`.
- Reuses the existing bash gate (`SandboxHook`, `builtin.py:87`) — same sandbox, same containment, no second exec path.
- Real stdout/stderr/exit code injected as turn context and recorded in the contract.
- Non-zero → `REPAIR_REQUIRED` via existing routing (`workflow_controller.py:49-53`); the model sees actual output, not its own summary.
- **Kills "no exception ⇒ done"** structurally: the model never reports the result, the harness does.

Bounded by the existing wall-clock deadline (`_deadline_exceeded`, `workflow_controller.py:345`) and `bash_timeout_seconds`.

### 6.7 Q6 — the stop-rule seam, built for a later `ask_user`

Backlog the tool; build the seam now. `open_questions` on the contract + a `BLOCKED_ON_QUESTION` route that maps onto the existing `blocked` decision and `CODER_BLOCKED` status — **both already in the enums** (`workflow_artifacts.py:48`, `:55`). When `ask_user` lands it becomes the producer for a consumer that already exists. Zero throwaway work.

### 6.8 What this subsumes from rev 2

| rev 2 | rev 3 status |
|---|---|
| C1 bash safe-set widening | **keep as-is** — independent defect (I-58) |
| C2 pre-fill the draft | **absorbed** — §6.3, richer scaffold |
| C3 leniency + `Decision.modify` | **absorbed** — §5.7's "never reject what the harness can supply" |
| C4 anchor-quality warning | **absorbed** — §6.4 |

---

## 7. Docs to update

Per the operator's "update design docs if needed" — the redesign changes recorded decisions, so these are part of the work, not follow-up:

| doc | change |
|---|---|
| `knowledge/trace/exploration_log.md` | new Q# recording the three-phase lifecycle + derive-don't-merge; Q-15 amendment noting the harness seat now honours pre-population |
| `worklogs/BACKLOG.md` | I-58 closed by C1; I-59 partially addressed; new row for `ask_user` |
| `knowledge/adr/` | slice contract + harness-run verification is an architectural decision — likely an ADR-16 amendment or new ADR |
| `knowledge/skills/pr-creation/SKILL.md` | commit note is now *derived*; document the mapping |
| `knowledge/skills/plan-authoring/SKILL.md` | note which markers the harness parses (advisory, §5.7) |
| `knowledge/project-overview.md` | §1.2.5 gains the slice-contract seat as an instantiation |

---

## 8. Open decisions before the plan

1. **Slice granularity** — one contract per plan slice (S11.1), or per coder stage entry? Repairs re-enter the coder stage; does a repair amend the contract or open a new one? *(Leaning: amend, with `repair_round` from `FlowState`.)*
2. **Phase 3 boundary** — does FA shell out to `gh pr create`, or write the body to a file the operator uses? *(Leaning: file. Shelling out makes FA a publisher, which is a bigger threat-model change than it looks.)*
3. **Contract on repair rounds** — re-verify the whole contract each round, or only invalidated steps? `FlowState.invalidated_steps` already exists (`workflow_artifacts.py:264`).
4. **`tests-writing` injection cost** — the skill is large. Full body on coder entry then anchor (the `skills/_inject.py` pattern), or a distilled subset? Needs a token measurement against `estimate_tokens`.
5. **Does the chat role get any of this?** Q2 says pipeline-only. Confirming: chat keeps today's `pr_prepare` (plus C1 relief), and the protocol is pipeline-only until proven.
6. **C1 scope** — `awk` in the safe set? (carried from rev 2 §9 Q3; still open).

---
## 9. Citation index (re-resolved at `fc1f2e6`)

### Founding sources
| citation | what |
|---|---|
| `knowledge/trace/exploration_log.md:1276-1454` | Q-15 (2026-05-25), pre-code |
| `knowledge/trace/exploration_log.md:1352-1367` | **rejected option (c)** — pre-population chosen over post-hoc declaration |
| `knowledge/anti-patterns/AP-001-…:112-119` | action-count dominates rule-count |
| `knowledge/anti-patterns/AP-001-…:130-136` | "one action", visible mid-write |
| `knowledge/skills/pr-creation/SKILL.md:186-190` | D-5 typed-intent override |
| `knowledge/skills/pr-creation/SKILL.md:195-215` | §Output format (SSOT for the header) |
| `knowledge/adr/ADR-10-…:148-159` | I-1 single-source-of-truth |
| `knowledge/adr/ADR-11-…:53-54`, `:393-394` | `pr_intent.py` + IntentGuard as **seeds** |
| `knowledge/adr/ADR-11-…:509` | "Intent before mutation" vs never-wired |
| `knowledge/adr/ADR-11-…:650` | seat asymmetry is an explicit non-goal |
| `worklogs/BACKLOG.md:898-923` | M-7 scope; "the earlier seat is the cheaper one" |
| `worklogs/BACKLOG.md:928-936` | Q-N amendment: `BEFORE_LLM_CALL` pre-injection deferred |
| `worklogs/BACKLOG.md:2875-2896` | I-58, I-59 |

### The unwired scaffold
| citation | what |
|---|---|
| `src/fa/hygiene/pr_intent.py:164` | `classify_intent` — pure, available |
| `src/fa/hygiene/pr_intent.py:275-294` | `_REQUIRED_FIELDS_BY_INTENT` — per-intent placeholders |
| `src/fa/hygiene/pr_intent.py:296-304` | `derive_required_fields` |
| `src/fa/hygiene/pr_intent.py:307-322` | **`render_prepare_buffer`** |
| `src/fa/hygiene/pr_intent.py:928` | its **only** production caller — the git hook |
| `src/fa/hygiene/pr_intent.py:379-391` | `INVARIANT_REQUIRED_PREFIXES` |

### The unused repair seat
| citation | what |
|---|---|
| `src/fa/inner_loop/hooks/base.py:76-78` | **`Decision.modify`** — zero production users |
| `src/fa/inner_loop/hooks/base.py:96-102` | `revalidates_after_modify` |
| `src/fa/inner_loop/hooks/base.py:171-204` | modify + replay machinery |
| `src/fa/inner_loop/hooks/base.py:26` | `BEFORE_LLM_CALL` exists |

### The architectural precedent
| citation | what |
|---|---|
| `src/fa/cli.py:1920-1993` | `_publish_scope_estimate` — classify-then-inject |
| `src/fa/cli.py:1942-1947` | **D7 note** — per-task hints must not ride the cacheable prefix |
| `src/fa/cli.py:2230`, `:2252` | scope hint → `turn_context` |
| `src/fa/inner_loop/scope_estimator.py:1-21` | deterministic pre-dispatch, §1.2.5 rationale |
| `src/fa/cli.py:158-168` | `_READINESS_PROMPT_EXTRA` — cacheable-prefix precedent |

### The defect surfaces
| citation | what |
|---|---|
| `src/fa/inner_loop/tools/prepare_pr.py:67-97` | `_INPUT_SCHEMA`; 4/6 props undescribed |
| `src/fa/inner_loop/tools/prepare_pr.py:78-87` | `invariant` description — the D11 precedent |
| `src/fa/inner_loop/tools/prepare_pr.py:121` | renderer **already** drops surplus FIX fields |
| `src/fa/inner_loop/tools/prepare_pr.py:136-168` | `_validate_fix_fields` — first violation only |
| `src/fa/inner_loop/tools/prepare_pr.py:269-278` | misleading tool description |
| `src/fa/inner_loop/hooks/intent_guard.py:121-127` | `_DRAFT_REQUIRED_BASH_EFFECTS` |
| `src/fa/inner_loop/hooks/intent_guard.py:138-141` | `_MISSING_DRAFT_REASON` |
| `src/fa/inner_loop/hooks/intent_guard.py:226-232` | `_requires_draft` |
| `src/fa/inner_loop/bash_intent.py:62-99` | 33-verb whitelist |
| `src/fa/inner_loop/bash_intent.py:174-177`, `:192-193`, `:571-575` | opacity amplifiers |
| `src/fa/inner_loop/bash_intent.py:227-233` | `_unwrap_env` — template for `uv run` |
| `src/fa/inner_loop/bash_intent.py:247-289` | verifier matcher; basename inconsistency |
| `src/fa/inner_loop/bash_intent.py:426-433` | basename precedent for interpreters |
| `src/fa/inner_loop/bash_intent.py:493` | terminal `OPAQUE_EXEC` fallback |
| `src/fa/inner_loop/tools/fs_search.py:65-77` | `ignored_params` leniency precedent (F8) |
| `src/fa/inner_loop/pr_draft.py:45-94` | `PrDraftStore` trust model |
| `src/fa/inner_loop/registry.py:289`, `:425` | PTS-v1 gate |
| `src/fa/inner_loop/prompt_composer.py:43-59` | cache identity = name + input_schema |
| `src/fa/inner_loop/profiles.py:433-445` | `estimate_tokens` |

### Live evidence
| citation | what |
|---|---|
| `worklogs/reviews/live-trial-data/cae-s127-bash-tail-1788526685-1245712.events.jsonl` | 6-turn ceremony; turn-3 identical repeat |
| `worklogs/reviews/live-trial-data/cae-s127-bash-stderr-1788527120-1246970.events.jsonl` | 6-turn ceremony; final draft `invariant: "n/a"` |

### Rev 3 additions — the three-phase lifecycle
| citation | what |
|---|---|
| `src/fa/cli.py:2163-2168` | **`--resume` injects the prior draft as context** — the "inherited context" mechanism, wired only across sessions |
| `src/fa/cli.py:1836-1840` | clearing the draft is fatal-on-failure (trust model) |
| `src/fa/cli.py:1858` | `draft_store.clear(remove_file=not resume)` |
| *(absence)* `src/fa/**` | **no `gh pr create`, no PR-body composer** — phase 3 does not exist |
| `src/fa/inner_loop/workflow_artifacts.py:50-84` | `FlowStatus` closed literal + frozenset guard — additive-safe |
| `src/fa/inner_loop/workflow_artifacts.py:128-145` | `StepResult` — precedent for the slice contract's shape |
| `src/fa/inner_loop/workflow_artifacts.py:250-301` | `FlowState` — where the slice contract attaches |
| `src/fa/inner_loop/workflow_artifacts.py:264` | `invalidated_steps` — repair-round granularity (§8 Q3) |
| `src/fa/inner_loop/workflow_artifacts.py:510-549` | atomic write + typed load — reuse for `slice_contract.json` |
| `src/fa/inner_loop/workflow_controller.py:49-53` | verdict → status routing (`REPAIR_REQUIRED`) |
| `src/fa/inner_loop/workflow_controller.py:257-271` | `FlowState` written before each stage — the scaffold seat |
| `src/fa/inner_loop/workflow_controller.py:345` | wall-clock deadline — bounds harness-run verification |
| `src/fa/skills/loader.py:119` | **`should_load_skill` — zero production callers** (4th unwired affordance) |
| `src/fa/skills/_inject.py:1-20` | deterministic skill injection; planner skills only |
| `src/fa/inner_loop/expansion.py:128-136` | `select_l2_skill` — only two skills reachable |
| `src/fa/inner_loop/coder_loop.py:773-790` | L2 injection call site |
| `src/fa/inner_loop/hooks/builtin.py:87-104` | `SandboxHook` — reuse for harness-run verification |
| `knowledge/skills/tests-writing/SKILL.md:11-13` | triggers already name the coder-stage case |
| `knowledge/skills/tests-writing/SKILL.md:65`, `:75` | C0/C1/C2/C3 as a decision procedure → derivable |
| `worklogs/implementation-plans/PLAN-…-chat-role.md:1752`, `:1808` | `### S10:` / `**Traces-to:**` — the parseable markers (§5.7) |
