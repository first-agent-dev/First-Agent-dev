# F6 Research — IntentGuard + `pr_prepare`: the intent-declaration seat

**Defect:** F6 in [`worklogs/reviews/S12.7-LIVE-VERIFICATION-FINDINGS.md:205-219`](S12.7-LIVE-VERIFICATION-FINDINGS.md)
**PR taken over:** [#68](https://github.com/first-agent-dev/First-Agent-dev/pull/68) (S12.7 F1/F4/F7/F8/F9)
**Tip verified against:** `fc1f2e68144f2a9f4fd279c21fb619842d69cc70`
**Status:** research + verification. No code changed. Deliverable is this doc; the plan it feeds is `/plan-authoring` work, gated on §9 decisions.

**Revision 2** — reframed after operator context: the module's founding sources (Q-15, AP-001, AP-003, `pr-creation/SKILL.md`, ADR-10 I-1, ADR-8, ADR-11) and the stated design intent ("inherited context", "garbage in → slop out", "push models to the limits").

---

## 0. What changed in rev 2, and why it matters

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

## 5. Option space

Five options. Weighed against §1.2 minimalism-first, §1.2.5 compliance-by-construction, AP-001 action-count, Pillar 3 KPI #2.

### Option A — Patch the symptoms (rev 1's plan)

Widen the bash whitelist; add schema descriptions; make surplus fields lenient; enrich the deny message.

- ✅ Small, low-risk, each piece independently revertable.
- ❌ Leaves the inversion. The model still composes from nothing; still no pre-filled draft; still deny-only. Cuts ~6 turns to ~2, not to ~0.
- ❌ **AP-004 risk:** four call-site guards, no named root cause. The anti-shallow-fix gate would rightly ask what producer freedom was closed — "the model can send wrong fields" is a symptom, not a freedom.
- **Verdict:** necessary but insufficient. Its good parts survive inside C/D.

### Option B — Delete the harness seat, keep the git hook

- ✅ Maximum subtraction; §1.2 would ask this question.
- ❌ Destroys the operator's actual goal. The git hook fires at *commit* time — after the code is written. "Inherited context" requires the anchor to exist *before* the trajectory. This is Q-15's rejected (c) with extra steps.
- **Verdict:** rejected on goal grounds, not cost grounds.

### Option C — Restore the scaffold (wire `render_prepare_buffer` into the harness seat)

Do at the harness seat what the git seat already does.

1. **Pre-compute + pre-fill.** At session bootstrap, run `classify_intent` over the current staged/dirty state, render the per-intent template via `render_prepare_buffer` (`pr_intent.py:307`), and surface it as turn context — exactly the `_publish_scope_estimate` shape (`cli.py:1920`, injected at `cli.py:2252` via `turn_context`, deliberately *not* on the cacheable prefix per the D7 note at `cli.py:1942-1947`). The model sees a filled draft with `<fill me — …>` placeholders before it acts.
2. **Accept the filled template.** `pr_prepare` gains a single-field path: send the edited text, harness parses it with the same `parse_field` / `validate_commit_msg`. Structured fields stay supported.
3. **Repair instead of deny.** On a near-miss, return `Decision.modify` (`hooks/base.py:76`) with the corrected payload, plus a loud `repaired[]` notice. The replay machinery at `hooks/base.py:180-200` already handles re-validation. **Currently zero middlewares use this seat** — building the affordance and never wiring it is the ADR-11 §I9 shape.
4. **Keep rejecting what must be rejected.** Missing FIX clauses stay hard denials — those are AP-003's load-bearing fields. Never auto-fill `DETERMINISTIC MECHANISM`; auto-filling the anti-shallow-fix gate would *be* the shallow fix.

- ✅ Restores Q-15's chosen design; cites its own founding document.
- ✅ Action count 6 → 1, matching AP-001:130 "one action".
- ✅ Adds **no new component** — wires an existing function, an existing hook affordance, an existing precedent. §1.2 question 3 answers itself: nothing to replace, only to connect.
- ✅ Improves anchor quality: a pre-filled template with intent-specific placeholders steers content, where a bare schema steers only syntax.
- ⚠️ Touches the composition root (`cli.py`) and the hook decision path.
- ⚠️ `Decision.modify` is unexercised in production — first user pays the integration cost. Mitigated: the replay path is already tested at the registry level.

### Option D — C, plus make the anchor earn its place

C, plus: the classifier's intent is **injected as the default**, so the model's job shrinks to confirm-or-override with a one-line reason (the skill's D-5 override, `SKILL.md:186-190`, already permits typed override — it just has no cheap surface). And a *warning-only* signal when the invariant is content-free (`n/a` under an intent whose diff shape is non-trivial) — observable, never blocking, per §1.2.5 "WARNING surface, never a silent pass".

- ✅ Directly targets the `invariant: "n/a"` failure §4 identifies.
- ✅ Warning-only respects forgiving-tools and keeps judgement out of the deny path.
- ⚠️ "Content-free" needs a deterministic definition or it becomes the LLM-judgement §1.2 q4 forbids. Proposal: purely structural — `n/a`-only invariant **and** classifier intent ∉ {RESEARCH, CHORE} **and** ≥1 projected path under `src/`. No semantics.
- **Verdict:** the goal-aligned target. Ships after C proves out.

### Option E — Full redesign (I-59)

Rule composition, per-intent policy objects, deny-reason taxonomy.

- ❌ Operator set I-59 to P4, "deliberately unscheduled until the live series closes" (`BACKLOG.md:2889-2896`). C+D delivers the KPI win without pre-empting it.
- **Verdict:** stays deferred. C is deliberately shaped to not foreclose it.

### Recommendation

**C now, D next, with A's cheap parts folded into C.** Specifically:

- A's bash-whitelist widening is **kept** — it is an independent defect (I-58) with its own root cause, and it shrinks how often the seat fires at all.
- A's schema descriptions are **kept** — cheap, and they make the fallback path (structured fields) coherent.
- A's surplus-field leniency is **kept**, now justified by `_render_draft` already discarding them (§2.6) rather than by "be nice".
- A's deny-message enrichment is **subsumed** by C3: repair beats a better rejection.

---

## 6. Proposed changes

Ordered by dependency. Each independently landable and kill-checkable.

### C1 — Widen the deterministic safe set (closes I-58)

**Degree of freedom closed:** `analyze_bash_for_intent` labels a command `OPAQUE_EXEC` — and therefore draft-requiring — whenever its head verb is absent from a 33-entry table, even when the verb provably cannot write. The draft requirement is decided by an omission in a data table, not by the command's effect.

**Deterministic mechanism:** extend `_READ_ONLY_COMMANDS` (`bash_intent.py:62`) with the pure-filter / pure-inspect POSIX set; add a `uv run` / `uvx` unwrap mirroring `_unwrap_env` (`bash_intent.py:227`); basename the head in `_is_verify_only` to match its sibling `_is_read_only` (`bash_intent.py:287`).

Safety argument: every added verb is a pure filter or inspector, and **write redirects are detected upstream of the verb lookup** (`_analyze_redirects`), escalating to `REPO_WRITE` regardless. Widening the verb table cannot widen write authority.

- Add: `seq sort uniq cut tr nl rev fold column paste join comm expand unexpand basename dirname realpath readlink md5sum sha1sum sha256sum cksum jq yq xxd od strings ps printenv command type sleep yes tac`
- `sed`: `READ_ONLY` only when no `-i` / `--in-place`; `_sed_target_files` (`bash_intent.py:307`) already owns the in-place path. Same for `perl -i`.
- `awk`: **excluded by default** — it can write via `print > "file"` inside its program text, invisible to bashlex. See §9 Q1.
- `uv run <verifier>` → unwrap → `VERIFY_ONLY`; `uv run <anything else>` stays `OPAQUE_EXEC`. The unwrap widens nothing on its own.
- **Deliberately unchanged:** `_reduce_analyses` max-severity (`:192`) and compound-node opacity (`:174`). Both are genuine safety properties; recursing into them is I-59. Pinned by tests so the non-change is intentional.

### C2 — Pre-compute the intent and pre-fill the draft (the core fix)

**Degree of freedom closed:** the harness never computes the session's likely intent before the model's first tool call and never renders the per-intent template, although `classify_intent` (`pr_intent.py:164`) and `render_prepare_buffer` (`pr_intent.py:307`) both exist and the git seat consumes both (`pr_intent.py:928`). The model must therefore infer the entire header shape from a schema, which is the composition burden Q-15 rejected as option (c).

**Deterministic mechanism:** at session bootstrap, classify the current staged/dirty snapshot and inject the rendered template as turn context, following `_publish_scope_estimate` (`cli.py:1920`) — same pure-function-then-inject shape, same non-cacheable placement per the D7 note (`cli.py:1942-1947`).

- New `_publish_intent_scaffold(...)`, sibling to `_publish_scope_estimate`, emitting an `intent_scaffold` event and returning a `## Draft Intent (pre-filled)` block appended to the existing `turn_context` (`cli.py:2252`).
- **D7 compliance is mandatory:** the block is per-session, so it must ride `turn_context`, never `system_prompt_extra`. Putting it on the cacheable prefix would fork the prompt cache per session — the exact measured failure the D7 note records.
- Empty/clean workspace → classifier yields `CHORE` → template is two lines. Cheap floor, no special-casing.
- Token cost: ~40–90 tokens. Against 6 turns, this is not close.

### C3 — Accept the filled template; repair near-misses instead of denying

**Degree of freedom closed:** `pr_prepare` accepts exactly one input shape (structured JSON fields, `prepare_pr.py:67-97`) and `_validate_fix_fields` (`:136-168`) surfaces one violation per call, so a caller who edited the pre-filled template, or who sent surplus fields the renderer would have discarded anyway (`:121`), pays one turn per deviation instead of being repaired or corrected in one pass.

**Deterministic mechanism:** add a `draft_text` input parsed by the same `parse_field` / `validate_commit_msg`; collect **all** violations in one pass; accept-and-report surplus FIX-only fields under a non-FIX intent via top-level `ignored_params`, mirroring `fs_search.py:74-77`; and return `Decision.modify` (`hooks/base.py:76`) for repairable near-misses at the guard seat.

**The asymmetry is load-bearing and must survive:**

| direction | behaviour | why |
|---|---|---|
| surplus FIX-only fields under non-FIX intent | **accept, drop, report** | `_render_draft:121` already drops them — the artifact is identical either way (§2.6) |
| missing FIX clauses under `INTENT: FIX` | **reject, all violations at once** | AP-003's load-bearing fields; relaxing this *is* the shallow fix |
| invariant prefix mismatch | **reject, constructive message** | shape-bearing; message already names expected prefixes |
| `DETERMINISTIC MECHANISM` auto-fill | **never** | auto-filling the anti-shallow-fix gate defeats its purpose |

Plus C2's companion: schema descriptions on the four undescribed properties, derived from `INVARIANT_REQUIRED_PREFIXES` (`pr_intent.py:391`) and the enums rather than hand-typed, per ADR-10 I-1.

**Constraints verified:**
- **PTS-v1** (`registry.py:289`, enforced `:425`): `if`/`then`/`dependentRequired` are **not** permitted. Conditionality must be prose in `description`, which `invariant` already proves passes (`prepare_pr.py:78`).
- **Prompt cache:** `prompt_composer.py:43-59` hashes name + `input_schema`, excluding `description`. Adding a `draft_text` property changes the cache key **once at deploy**, not per session. Note in the PR.
- **Token budget:** `estimate_tokens` (`profiles.py:433-445`). Target ≤ ~120 added tokens.

### C4 — Warning-only anchor-quality signal (Option D; ships after C)

**Degree of freedom closed:** nothing observes whether the draft states a real intent, so a `invariant: "n/a"` draft under a source-touching diff satisfies the gate identically to a substantive one — the seat's stated purpose (trajectory anchor) has no failure surface at all.

**Deterministic mechanism:** a purely structural predicate — `invariant` is `n/a`-only **and** classifier intent ∉ {RESEARCH, CHORE} **and** ≥1 projected path under `src/` — emitting a WARNING event, never a deny, per §1.2.5 "WARNING surface, never a silent pass".

No semantics, no LLM judgement, no blocking. It makes the empty case *observable*, which is the §1.2.5 half currently missing.

### Explicitly out of scope

- `_reduce_analyses` / compound-node opacity — considered, deliberately unchanged (§C1).
- I-59 structural refactor — stays P4. C is shaped not to foreclose it.
- `intent_guard.mode: observe` (`intent_guard.py:130-136`) — the tactical lever is not a substitute for the semantic fix; untouched.
- Making the git-hook seat as strict as the harness seat — ADR-11:650 names seat asymmetry as an explicit non-goal.

---

## 7. Anti-shallow-fix gate — draft PR clauses

```text
INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: harness-side intent-declaration seat (Q-15 pre-population
contract, S12.7 F6, backlog I-58)

DEGREE-OF-FREEDOM CLOSED: the harness seat asks the LLM to COMPOSE the
PR-intent header from a bare schema, while the git seat hands it a
mechanically pre-filled template to EDIT — so the seat Q-15 chose for its
LOWER action count (exploration_log.md:1352-1367, rejecting post-hoc
declaration on AP-001 action-count grounds) carries the higher one, and the
model's first-instinct phrasing is met with denial instead of a scaffold.
Compounding it, the draft requirement is triggered by a verb-table omission
rather than by a command's actual write capability.

DETERMINISTIC MECHANISM: the session bootstrap classifies the staged
snapshot and injects the rendered per-intent template as turn context,
reusing the same render_prepare_buffer the git hook consumes and the same
pure-function-then-inject shape as the scope estimator, so the agent edits a
filled buffer instead of composing one — src/fa/hygiene/pr_intent.py:307;
near-miss payloads are repaired via the existing Decision.modify seat rather
than denied — src/fa/inner_loop/hooks/base.py:76; and the read-only safe set
is widened so the effect label follows write capability, with redirect
detection unchanged upstream of the verb lookup —
src/fa/inner_loop/bash_intent.py:62.

TEST-EDITS:
tests/test_bash_intent.py — new safe-set verbs and uv-run unwrap must be pinned
tests/test_prepare_pr.py — draft_text path and surplus-field leniency replace first-violation rejection
tests/test_intent_guard.py — repair-instead-of-deny path is new behaviour at the guard seat
tests/test_pr_intent_snapshot.py — render_prepare_buffer gains a second production consumer
```

---

## 8. Test plan

### 8.1 Offline (pytest)

| file | pins |
|---|---|
| `tests/test_bash_intent.py` | each new verb → `READ_ONLY`; **kill-check:** each still → `REPO_WRITE` with `> out.txt`; `sed -n` read-only / `sed -i` mutating; `uv run pytest` → `VERIFY_ONLY` but `uv run rm -rf /` → `OPAQUE_EXEC`; `.venv/bin/pytest` → `VERIFY_ONLY`; brace/compound/`$(…)` **still** opaque (guards the deliberate non-change) |
| `tests/test_cli.py` | `_publish_intent_scaffold` emits `intent_scaffold` once per session; block reaches `turn_context` and **never** `system_prompt_extra` (D7 kill-check); clean workspace → CHORE two-line template |
| `tests/test_prepare_pr.py` | `draft_text` round-trips to a byte-identical draft vs structured fields; `{intent: CHORE, +3 FIX fields}` → **ok** + all three in `ignored_params` + rendered draft identical to the two-field call; `INTENT: FIX` missing all three → **one** rejection listing **all three**; invariant-prefix mismatch still rejects; `DETERMINISTIC MECHANISM` never auto-filled |
| `tests/test_intent_guard.py` | repairable near-miss → `Decision.modify` with `repaired[]`, not `deny`; missing FIX clauses → still `deny`; read-only bash never reaches the draft branch; **kill-check:** revert the modify path → row denies |
| `tests/test_pr_intent_snapshot.py` | `render_prepare_buffer` has ≥2 production consumers (guards the ADR-11 §I9 unwiring class that caused this) |
| `tests/test_s127_doc_gates.py` | one required-field line per `INTENT_VALUES` member, derived from the enum, so adding an intent fails the test |
| `tests/test_prompt_registry_coherence.py` | PTS-v1 still passes; `estimate_tokens` delta within budget |

After every edit, per standing rule: `tests/test_live_check_script.py` + `scripts/adversarial_battery_live_check.sh`.

### 8.2 Live rows (`scripts/run_live_check.sh`, `s127_row` conventions at `:568-572`)

**`s127-intent-scaffold`** (C2) — task: make one small edit to a source file and report it.
- `[PASS]` `"kind": "intent_scaffold"` present
- `[PASS]` **at most one** `pr_prepare` call (assert on count, not presence)
- `[PASS]` absent `is only valid when .intent. is .FIX.`
- kill-check: pre-fix shows 4 `pr_prepare` calls

**`s127-bash-recon-nodraft`** (C1) — three read-only recon commands (`wc -l`, `sort`, `uv run pytest --version`), nothing written.
- `[PASS]` `fs_run_bash` ran
- `[PASS]` **absent** `missing or untrusted current-session PR draft`
- `[PASS]` **absent** `"tool_name": "pr_prepare"` — the point is that no ceremony was needed
- kill-check: pre-fix denies on turn 1

**`s127-intent-repair`** (C3) — instruct a deliberately slightly-wrong `pr_prepare` (FIX fields under CHORE), then proceed.
- `[PASS]` the call **succeeded**
- `[PASS]` `ignored_params` present
- `[PASS]` **absent** a second corrective `pr_prepare`

**`s127-intent-anchor-quality`** (C4, after C ships) — non-trivial `src/` edit with a deliberately empty intent.
- `[PASS]` WARNING event present
- `[PASS]` run **not** blocked (forgiving-tools kill-check)

**Re-runs:** `s127-bash-tail`, `s127-bash-stderr`, and `s127-bash-small` (still pending in the SSOT progress table) on the fixed build.

---

## 9. Decisions needed before planning

1. **Scope — C2 in or out of this PR?** C1+C3 alone cuts ~6 turns to ~2 and is low-risk. C2 is the actual root-cause fix, cuts to ~1, and touches the composition root. One PR (coherent story, one anti-shallow-fix argument) or two (smaller review surface, C1+C3 lands immediately)? **My recommendation: one PR, C1+C2+C3.** Splitting means the first PR's mechanism clause has to describe a symptom fix, which is the AP-003 shape.
2. **`Decision.modify` first production use.** C3 wires an affordance that exists, is tested at registry level, and has zero production consumers. Accept that risk, or land C3 as better-rejection-only and defer repair to a follow-up?
3. **`awk`** — excluded by default (can write via `print > "file"`, invisible to bashlex). Include and accept the blind spot, or keep opaque?
4. **C4 now or later?** It targets the `invariant: "n/a"` failure most directly — the thing closest to your actual goal — but it is the only piece touching *content* rather than *shape*. Fold into this round, or ship after C proves out?
5. **I-58 / I-59 disposition.** This closes I-58 outright. Mark I-59 partially addressed (deny-reason taxonomy improved by C3) but open for the structural refactor?
6. **`s127-bash-tail`'s brace group stays opaque** by design here — ceremony drops from six turns to one, not zero. Accept, or also reword the row?

---

## 10. Citation index (re-resolved at `fc1f2e6`)

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
