# F6 Research — IntentGuard + `pr_prepare`: the intent-declaration seat

**Defect:** F6 in [`worklogs/reviews/S12.7-LIVE-VERIFICATION-FINDINGS.md:205-219`](S12.7-LIVE-VERIFICATION-FINDINGS.md)
**PR taken over:** [#68](https://github.com/first-agent-dev/First-Agent-dev/pull/68) (S12.7 F1/F4/F7/F8/F9)
**Tip verified against:** `fc1f2e68144f2a9f4fd279c21fb619842d69cc70`
**Status:** research + verification. No code changed. Deliverable is this doc; the plan it feeds is `/plan-authoring` work, gated on §9 decisions.

**Revision 5** — operator decisions on injection payload, extractor investment, and PR publishing folded in (§5.8, §5.7, §8). Rev 4's finding stands: the hand-pasted ceremony *is* `feature-planning/SKILL.md` §9–§12, so nothing new is invented — but the **injected** form is a purpose-built condensate, not the skill body (§5.8).

**Revision 4** — rev 3 proposed a new `SliceContract` schema; **rev 4 retracts it.** Operator feedback forced a re-read of the planning skills, which showed the hand-pasted ceremony *is* `feature-planning/SKILL.md` §9–§12 verbatim (§5.1). The design collapses to skill injection + two gates. §§1–4 are rev 2's verified findings, unchanged.

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
            lines.append(f"INTENT: {field.placeholder}")  # mechanically filled
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

## 5. Re-baseline — the finding that dissolves most of the problem

Rev 3 proposed a new `SliceContract` schema. **Rev 4 retracts that proposal.** Operator feedback ("overall i am lost", "simple system per my desired behaviour") forced a re-read of the planning skills, and the re-read produced the finding below.

### 5.1 The operator's ceremony already exists, in the repo, as a skill

The prompt the operator hand-pastes for every slice **is `knowledge/skills/feature-planning/SKILL.md` §9–§12, near-verbatim.**

| operator's pasted prompt | source in repo |
|---|---|
| "state current source-verified behavior" + "stop if blocking question, append it" | `feature-planning/SKILL.md:306-336` — `BEFORE EDITING GATE` |
| "what idea is implemented now?" | `:344` |
| plan contract + gap IDs / files allowed | `:314-325` |
| concrete intent · current→target · code mechanism · **degree of freedom closed** · **deterministic mechanism** · production best practice · failure behavior · DoD + negative proof · C0–C4 class · producer kill-check target | `:342-386` — `EDIT PACKET E# / S#` |
| "run targeted tests, static checks, inspect diff, report actual output, not complete from 'no exception'" | `:388-415` — `AFTER EDIT GATE` |
| "after a big chunk, run mutation testing" | `:423-441` — kill-check protocol |
| "if implementation reveals a new policy choice, stop and promote to Q#" | `:326-334` |

**Every element. No exceptions.** The operator is not asking for a new artifact — he is hand-delivering a skill the harness already contains and never injects.

**This inverts the entire problem.** Rev 3 asked "what new schema should the model fill in?" The right question is: **"why is the harness making the operator paste a skill it already ships?"**

Answer, verified: `select_l2_skill` (`expansion.py:128-136`) injects a planning skill **once, at L2 entry**, and only `plan-authoring` or `feature-planning`. There is **no per-slice injection during the coder stage**, and `should_load_skill` (`skills/loader.py:119`) — the function that would do trigger-based injection — has **zero production callers**. The skill is injected as *planning* input and never re-applied as *execution* protocol, which is what §9–§12 actually are.

**Consequence: no new schema. The design becomes "inject §9–§12 at the coder stage, per slice, and enforce the two gates the harness can check deterministically."** That is dramatically smaller than rev 3, and it is why rev 4 retracts the `SliceContract` dataclass.

### 5.2 Operator correction accepted — I was wrong about DEGREE-OF-FREEDOM CLOSED

Operator: *"Degree of freedom closed is more like 'what agent should do exactly?' — scope, best practices to use maybe."*

I claimed it derives from `current_behavior`. **That is wrong**, and the repo settles it — against both of us, in a way that matters:

> `DEGREE-OF-FREEDOM CLOSED:` names the **producer-site** decision (schema typing) the LLM previously had freedom on. The previous wrong-shape fix had freedom on «which truth-strings to accept»; this fix removes the freedom entirely.
> — `AP-003:152-156`

> One sentence naming the spec-bearing decision **the LLM previously had a degree of freedom on, that this fix removes.** … A genuine answer names a **producer-site** decision (a schema field shape, a function return contract, a config validation rule).
> — `pr-creation/SKILL.md:142-150`

So it is neither "the freedom that exists today" (my rev-3 error) nor "what the agent should do / scope / best practices" (the operator's reading). It is: **the producer-site decision that this change removes freedom on.** It is about *the code's* freedom, not the agent's, and it is inherently **per-change** — which is exactly why it cannot be a PR-level generalized rule list.

Two things follow, and they are load-bearing:

1. **My "mapping is total and deterministic" claim is retracted.** DoF-closed is genuine per-slice judgement. It cannot be derived from `current_behavior` or anything else. Rev 3's strongest argument was wrong.
2. **`feature-planning:361` already asks for exactly this field, per edit packet, in the operator's own ceremony.** The field the commit gate needs is already produced by the protocol the operator already runs by hand. It does not need deriving — it needs **carrying**.

The operator's instinct that these are "2 different artifacts" is therefore correct, but the relationship is simpler than rev 3's derivation machinery: the edit packet **contains** the commit note's hardest fields as ordinary content.

### 5.3 The schema conflict is smaller than it looks

Operator: *"skills produce different shapes of plans… there is a schema conflict."*

Real, but narrow. The ID vocabularies are **identical**:

| ID | `feature-planning:120-132` | `plan-authoring:161-181` |
|---|---|---|
| `G#` `GAP#` `CT#` `P#` `M#` `A#` `S#` `T#` `Q#` `RK#` `RN#` | all present | all present, same meanings |

Both use `S#` for the implementation slice. Both use `GAP#`/`CT#` for contracts. **Liveness `L0`–`L3` is in both.** The plan *skeletons* differ (feature-planning has 10 sections, plan-authoring ~12 with a heavier preflight/READY gate), but **the machine-relevant surface — the ID grammar — is common.**

So the extractor parses `S#`, `GAP#`, `CT#`, `T#` and works against both skills. The operator's proposed mitigation ("force workflow to use only plan-authoring") is **not necessary**, and I'd advise against it: `feature-planning` is the skill that carries §9–§12, which is the part being mechanized.

**The actual conflict is the opposite of the stated one:** `plan-authoring` has **no** before-edit gate, no edit packet, and no after-edit gate. Verified — `grep` for `BEFORE EDITING`/`EDIT PACKET`/`AFTER EDIT`/`Producer kill-check`/`Tests-writing class` in `plan-authoring/SKILL.md` returns a **single** hit (`:442`, "Degree of freedom closed", inside a step template). Operator: *"plan-authoring does not conform currently to pr_prepare and my prompt."* Correct — and the fix is to port §9–§12 into `plan-authoring` (a doc change, §7), not to restrict which skill the workflow may use.

### 5.4 Should `pr_prepare` exist at all?

Operator: *"while writing this i become more sceptical on whole pr_prepare feature, should it exist?"* … *"Pr_prepare should be a generalized intent / guideline and degree-of-freedom-closed list of rules that all slices should follow, like 'implement features strictly following design decisions locked in ADR-20'."*

**Split it into the three things it currently conflates**, and the answer differs for each:

| role | keep? | why |
|---|---|---|
| **The commit-message gate** (`pr_intent.py`, git hook) | **keep, untouched** | Runs at the git seat, costs the model nothing, catches AP-003 shallow fixes at the boundary. Not implicated in F6. `ADR-10 I-1` keeps it as the single validator. |
| **The agent-facing `pr_prepare` tool** (`prepare_pr.py`) | **delete from chat; replace in workflow** | This is the F6 turn-tax. Operator's Q5 already says strip it from chat. In the workflow, the edit packet supersedes it. |
| **"Generalized rules all slices follow"** (operator's new idea) | **new, and it is not `pr_prepare`** | This is a *session-scoped constraint set* ("follow ADR-20"), not a per-commit note. Different lifetime, different shape. |

That third row is the operator's real want, and it is **the phase-1 "inherited context" mechanism** — the thing rev 3 found already exists but only across `--resume` (`cli.py:2163-2168`). It is one field, set once per run, re-surfaced every coder turn. It is not `pr_prepare`; it is *smaller* than `pr_prepare`.

**So: `pr_prepare` as an agent tool should not exist.** The commit gate stays; the constraint set is new and tiny; the per-slice ceremony is a skill injection. Three simple things replacing one confused one — which is the "simple system per my desired behaviour" the operator asked for.

### 5.5 The corrected object model

```
RUN CONSTRAINTS  (new, tiny, set once per run — the operator's "generalized rules")
  "follow ADR-20"  ·  "no new deps"  ·  links to plan/docs
  └─ re-surfaced every coder turn as inherited context   [phase 1]
              │
              ▼
PLAN ARTIFACT  (already exists, authored by plan-authoring / feature-planning)
  S# · GAP# · CT# · T#  ← common ID grammar, both skills
              │  script extraction only, no LLM  [§5.7]
              ▼
EDIT PACKET  (already specified — feature-planning §9-§12; injected, not invented)
  before-gate → packet → after-gate → kill-check
              │  the model writes this as PROSE, per slice
              ▼
COMMIT  (one slice = one commit, per operator)
  DoF-closed + mechanism carried from the packet, checked by the existing hook
              │
              ▼
PR  (fa publishes branch→main; operator verifies and merges)  [phase 3]
```

Nothing here is a new schema. One new small artifact (run constraints), one skill injection, two gates.

### 5.6 Operator decisions, recorded

| # | decision | status |
|---|---|---|
| Q1 | object model | **superseded by §5.5** — no `SliceContract`; skill injection + run constraints |
| Q2 | **workflow pipeline only** | confirmed; chat strips `pr_prepare` entirely (§8 Q5) |
| Q3 | **harness runs verification, injects real output** | confirmed — mechanizes the `AFTER EDIT GATE` (`:388-415`) |
| Q4 | **warn on out-of-scope writes, never block** | confirmed; note `feature-planning:337` says "Allowed files are binding" — the *skill* says stop, the *harness* only warns. Deliberate: forgiving-tools |
| Q5 | plan-ID extraction | **script-only, no LLM**; build it, measure it, invest further only if warranted. Legacy plans failing is expected, not a kill signal (§5.7) |
| Q6 | stop-rule tool | backlogged; seam only |

### 5.7 Q5 — script-only extraction, and how far to invest

Operator: *"no llm call, only script extraction. If script will fail — not worth to invest further."*

Accepted as a **hard gate on the feature, decided before any code**:

- Extractor is a pure function: plan text → `{S#, GAP#, CT#, T#}`. Regex over the common ID grammar (§5.3). No LLM, no fallback prompt.
- **Operator decision (rev 5):** older plans do not conform and the extractor *will* fail on them — that is expected and is **not** a kill signal. Build the function, measure it, and invest further only if the measurement shows it is worth it.
- **Corrected criterion: conformance is scoped to plans authored under the current skills, not the whole back-catalogue.** Step 1 of the plan measures extraction across `worklogs/implementation-plans/` and reports a per-plan pass/fail table, splitting *conforming* (post-skill) from *legacy*. Legacy misses are recorded, not counted against the gate.
- Failure stays **soft in every case**: unparseable plan → fields blank and optional, run proceeds, WARNING emitted. Never a rejection (this is the §5.7 rule that keeps F6 from recurring).
- The ceremony injection (§5.1, §5.8) does not depend on the extractor and ships regardless.

### 5.8 Injection payload — condensates, not skill bodies (operator, rev 5)

Operator: *"i would prefer a separate shorter version for this task. My prompt is ~30 loc, parts from skill are ~150 loc. We can add a new .md file right besides SKILL.md and inject it instead."* Same for `tests-writing`: *"we dont [inject the whole skill]. Same treatment, shorter version for injection."*

Accepted. This is the right call, and the size argument understates it: injecting `feature-planning` §9–§12 (~135 lines) plus `tests-writing` (828 lines) **every coder turn** is a per-turn tax that the operator's own 30-line prompt proves is unnecessary. The hand-pasted prompt is the **empirical proof of sufficiency** — it has been driving real slices successfully at ~30 lines.

**Two new files:**

| file | content | budget |
|---|---|---|
| `knowledge/skills/feature-planning/INJECT.md` | before-gate → edit packet → after-gate → stop rule, condensed from `SKILL.md:306-441` | ~30–40 lines |
| `knowledge/skills/tests-writing/INJECT.md` | C0–C4 ladder + producer kill-check + anti-theater minimum, condensed from `SKILL.md:123-128,156` | ~20–30 lines |

Authoring rule: **the condensate is derived from the skill, never divergent from it.** The skill stays SSOT for the full protocol; `INJECT.md` is the executable subset. Drift between them is a real risk (`parity.py` precedent, `authoring-hardening-workplan-2026-07-16.md:273`), so the plan carries a **parity test**: every field name in `INJECT.md` must appear in its `SKILL.md`. Cheap, and it stops the two from silently forking.

#### Three verified obstacles, none fatal

1. **The loader hardcodes the filename.** `SKILL_FILE_NAME = "SKILL.md"` (`_inject.py:47`) and `read_skill_for_injection` builds `skills_root / skill_name / SKILL_FILE_NAME` (`:216-224`) — it **cannot** read a sibling file today. Fix: add an optional filename parameter defaulting to `SKILL.md`. Small, backward-compatible, and `test_read_skill_from_temp_fixture` (`tests/test_skill_injection.py:184`) already exercises the read path against a tmp fixture, so the new arg is testable without touching the real tree.

2. **`skill-writing/SKILL.md:63` states an invariant: "Each skill is single file `SKILL.md` under `knowledge/skills/<name>/`".** Adding `INJECT.md` **violates a written rule**. This must be amended deliberately, not silently — the amendment goes in the plan's doc step (§7), stating that a skill is one `SKILL.md` **plus an optional derived `INJECT.md`**, and that only `SKILL.md` carries frontmatter/triggers. Unamended, this is exactly the "doc says X, code does Y" drift the repo has anti-patterns against.

3. **Naming.** `INJECT.md` over the operator's `<SkillName>-inject.md`: the directory already names the skill, so the prefix is redundant, and a fixed filename means the loader takes a constant, not a computed string. Trivially reversible if the operator prefers the explicit form.

**`knowledge/skills/README.md:101-110` index** gains no rows — `INJECT.md` is not a skill, it is a payload of one. Worth one line in the README preamble so the layout is discoverable.

---

## 6. Design — three mechanisms

### 6.1 M1 — inject the ceremony at the coder stage

The core change, and mostly wiring.

- On entering the coder stage for a slice, inject **`feature-planning/INJECT.md`** (~30–40 ln, §5.8) into turn context via the existing observation-block path (`coder_loop.py:773-790`) — not the 135-line skill excerpt, not the 643-line skill.
- Inject **`tests-writing/INJECT.md`** (~20–30 ln) alongside it, since the packet demands a C0–C4 class. Use `should_load_skill` (`loader.py:119`) — currently zero callers.
- Requires the loader filename parameter (§5.8 obstacle 1): `read_skill_for_injection(..., file_name="INJECT.md")`.
- Re-surface `RUN CONSTRAINTS` compactly each turn (phase 1), reusing the `--resume` injection shape (`cli.py:2163`) but within-session.
- Anchor pattern still applies: full condensate on slice entry, short anchor on later turns (`build_skill_anchor`) — with a ~30-line payload the entry cost is now negligible.

No new schema. The model emits the packet as prose, as it does today when the operator pastes it.

### 6.2 M2 — harness runs the after-edit gate (Q3)

The `AFTER EDIT GATE` currently asks the *model* to run commands and report output — precisely the self-report the operator distrusts.

- Harness executes the plan's `T#` commands itself after the coder signals slice-done, through the existing `SandboxHook` bash path (`builtin.py:87-104`) — no second exec path.
- Real stdout/exit code injected as turn context and recorded.
- Non-zero → `REPAIR_REQUIRED` via existing routing (`workflow_controller.py:49-53`).
- Structurally kills "complete from no exception" (`feature-planning:410`): the model never reports the result.

### 6.3 M3 — two deterministic gates, both cheap

| gate | check | on violation |
|---|---|---|
| files-allowed | writes ⊆ declared set | **WARNING** (Q4) |
| commit fields | DoF-closed + mechanism present with resolvable `path:line` | existing hook, unchanged |

`resolve_citation` already exists in `pr_intent.py`. Nothing new.

### 6.4 Retracted from rev 3

`SliceContract` dataclass · new `FlowStatus` members · derivation of commit fields from contract fields · `test_class` auto-derivation (it is a judgement call the packet already asks for). Rev 2's **C1** (bash safe-set widening) stays — independent defect.

---

## 7. Docs to update

| doc | change |
|---|---|
| `knowledge/skills/feature-planning/INJECT.md` | **new** — ~30–40 ln condensate, the injected ceremony (§5.8) |
| `knowledge/skills/tests-writing/INJECT.md` | **new** — ~20–30 ln condensate: C0–C4 + kill-check |
| `knowledge/skills/skill-writing/SKILL.md:63` | **amend the single-file invariant** to allow a derived `INJECT.md` (§5.8 obstacle 2) |
| `knowledge/skills/plan-authoring/SKILL.md` | **port §9–§12 from `feature-planning`** — the conforming fix for the real schema gap (§5.3) |
| `knowledge/instructions/02-operations.md` | **operator instructions** (per feedback) — the ceremony is now automatic; stop pasting it |
| `knowledge/skills/pr-creation/SKILL.md` | `pr_prepare` tool is retired from the agent seat; commit gate unchanged |
| `knowledge/trace/exploration_log.md` | new Q# — ceremony-as-skill finding; Q-15 amendment |
| `knowledge/adr/` | ADR for harness-run verification + agent-tool retirement |
| `worklogs/BACKLOG.md` | I-58 (C1); `ask_user` row; `should_load_skill` wired |

---

## 8. Open decisions

**Q1 — slice granularity.** Operator asked for examples. Concretely, for a plan with `S11: add files_allowed warning`:

- **(a) one contract per plan slice** — S11 = one commit, one edit packet. Repair rounds amend the same packet. Matches "one slice = one commit". Risk: a slice touching 4 files across 2 subsystems yields a bundled packet, which `feature-planning:386` forbids ("do not combine unrelated contracts").
- **(b) one packet per edit** — S11 might yield E1 (add the warning), E2 (wire it), E3 (test). Three packets, one commit. Matches the skill exactly (`EDIT PACKET E# / S#` — note it is keyed by **both**). Risk: more ceremony per slice.
- **(c) hybrid** — packet per edit, gate per slice: before-gate once at slice entry, packet per edit, after-gate once before commit.

**Resolved (rev 5): (c) hybrid**, per recommendation. Before-gate once at slice entry; one edit packet per edit (`E# / S#`, bounded, no bundling per `feature-planning:386`); after-gate + harness-run verification once before the commit. One slice = one commit.

**Q2 — phase 3. Resolved (rev 5):** fa **should publish** — push commits to a branch and open a PR to `main` via standard git + its GitHub token; the operator verifies and merges manually. Two verified facts shape the implementation: no PR-creation code exists anywhere in the repo (`gh pr create` appears only in two research docs), and **`gh` is not in the bash read-only whitelist** (`bash_intent.py:62-99`), so an agent-issued `gh` call classifies as `OPAQUE_EXEC`. Therefore publishing is a **harness action, not an agent bash call** — deterministic, at the end of the pipeline, with the PR body composed from the run's edit packets. This also keeps the token out of model-reachable surface. Threat-model note for the plan: publishing is the first outbound-write capability in the pipeline; it must be gated on the pipeline reaching `DONE` and must target the session branch only, never `main` directly (`validators.py:251` already guards force-push to `main`).

**Q3 — re-verify all each round?** Operator asks what a senior production team would do. **Answer: neither extreme — this is the standard CI/local split.** Locally, re-run only the affected subset each iteration (fast feedback); before the merge boundary, run the full suite once. Selective re-runs risk missing a regression that a fixed test would have caught; full re-runs each round waste wall-clock and hit the deadline (`workflow_controller.py:345`). **Recommendation:** targeted `T#` per repair round, full plan verification once before the slice is marked done. `FlowState.invalidated_steps` (`workflow_artifacts.py:264`) already models exactly this.

**Q4 — injection payload. Resolved (rev 5):** neither full skill nor a raw §9–§12 slice — a purpose-built `INJECT.md` condensate per skill (§5.8). Supersedes rev 4's "full body" reading. Token measurement stays in step 1, but the budget question largely dissolves: ~60 lines total instead of ~970.

**Q5 — strip from chat. Resolved:** remove the `pr_prepare` tool and its description from the chat role. Confirms §5.4. Saves tokens in the common path and removes the F6 tax where it was measured.

**Q6 — stop-rule best practice.** Operator asks. **Recommendation: fail-closed halt, no auto-continue.** When a blocking `Q#` appears the run stops and surfaces the question; it does not guess a default. Rationale: the skill already mandates it (`feature-planning:326-334`, "STOP immediately"), a guessed policy choice is the most expensive error class (it silently propagates through every later slice), and halting is the only behaviour that stays correct when `ask_user` later lands — the seam becomes a producer for a consumer that already exists (`CODER_BLOCKED`, `workflow_artifacts.py:55`). Non-blocking questions with explicit defaults continue, per the skill.

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

### Rev 4 additions — the ceremony-as-skill finding
| citation | what |
|---|---|
| `knowledge/skills/feature-planning/SKILL.md:306-336` | `BEFORE EDITING GATE` — operator's "state current behavior / stop on blocking Q#" |
| `…/feature-planning/SKILL.md:342-386` | `EDIT PACKET E# / S#` — **all ten** of the operator's per-edit fields |
| `…/feature-planning/SKILL.md:361` | `Degree of freedom closed` already in the packet, per edit |
| `…/feature-planning/SKILL.md:388-415` | `AFTER EDIT GATE` — targeted tests, static checks, diff, "not complete from no exception" |
| `…/feature-planning/SKILL.md:423-441` | mutation / kill-check protocol |
| `…/feature-planning/SKILL.md:337` | "Allowed files are binding" — skill says stop, harness only warns (Q4, deliberate) |
| `…/feature-planning/SKILL.md:120-132` | ID grammar `G#/GAP#/CT#/P#/M#/A#/S#/T#/Q#/RK#/RN#` |
| `knowledge/skills/plan-authoring/SKILL.md:161-181` | **identical** ID grammar — extractor works against both (§5.3) |
| *(absence)* `plan-authoring/SKILL.md` | **no** before-edit gate / edit packet / after-edit gate — the real schema gap |
| `knowledge/anti-patterns/AP-003:152-156` | DoF-closed = **producer-site** decision the change removes freedom on |
| `knowledge/skills/pr-creation/SKILL.md:142-150` | same definition; `n/a (reason)` allowed |
| `src/fa/inner_loop/bash_intent.py:62-99` | `gh` **not** in the read-only whitelist — bears on Q2 |
| *(absence)* repo-wide | `gh pr create` appears only in two research docs; **no PR-creation code** |

### Rev 5 additions — injection payload, extractor, publishing
| citation | what |
|---|---|
| `src/fa/skills/_inject.py:47` | `SKILL_FILE_NAME = "SKILL.md"` — hardcoded; blocks sibling-file injection |
| `src/fa/skills/_inject.py:216-224` | `read_skill_for_injection` builds `skills_root/<name>/SKILL.md`; needs a filename param |
| `tests/test_skill_injection.py:184` | `test_read_skill_from_temp_fixture` — existing tmp-fixture read test to extend |
| `knowledge/skills/skill-writing/SKILL.md:63` | **"Each skill is single file `SKILL.md`"** — invariant that `INJECT.md` violates; must be amended |
| `knowledge/skills/README.md:101-110` | skill index; `INJECT.md` adds no row (payload, not skill) |
| `knowledge/research/authoring-hardening-workplan-2026-07-16.md:273` | parity-check precedent for doc↔code mirrors → parity test for `SKILL.md` ↔ `INJECT.md` |
| `src/fa/sandbox/validators.py:251` | force-push guard on `main` — bears on harness-side publishing |
| `src/fa/inner_loop/bash_intent.py:62-99` | `gh` absent from whitelist → publishing must be a harness action, not agent bash |
