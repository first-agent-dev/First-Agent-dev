# F6 Research — IntentGuard + `pr_prepare` ceremony friction

**Defect:** F6 in [`worklogs/reviews/S12.7-LIVE-VERIFICATION-FINDINGS.md:205-219`](S12.7-LIVE-VERIFICATION-FINDINGS.md)
**PR taken over:** [#68](https://github.com/first-agent-dev/First-Agent-dev/pull/68) (S12.7 F1/F4/F7/F8/F9)
**Tip verified against:** `fc1f2e68144f2a9f4fd279c21fb619842d69cc70`
**Status of this doc:** research + verification only. No code changed yet. Every source citation below was re-resolved line-exact at the tip.

---

## 0. Executive summary

F6 as written in the SSOT is **real, reproducible from the recorded event logs, and under-scoped**. The finding describes one symptom (`pr_prepare` schema is undocumented → the model brute-forces it) and proposes one fix (document the schema in the tool description). Verification confirms that symptom exactly, but shows it is the **second** of two independent producer-site degrees of freedom. The first — and the larger turn-waster — is that `analyze_bash_for_intent` classifies almost every benign read-only shell command as `OPAQUE_EXEC`, so the draft gate fires on reconnaissance that mutates nothing.

Both are already partially catalogued in the backlog as **I-58** (read-only bash denied before a draft exists,
[`worklogs/BACKLOG.md:2875-2887`](../BACKLOG.md)) and **I-59** (IntentGuard structural refactor,
[`worklogs/BACKLOG.md:2889-2896`](../BACKLOG.md)). F6 is the live-verified evidence that I-58 has graduated from P3 speculation to a measured, quantified defect. This doc merges the three.

**Net measured cost:** 5 wasted turns on `s127-bash-tail`, 6 on `s127-bash-stderr`, out of 10-turn budgets. Between 50 % and 60 % of both rows' turn budget was consumed by ceremony before the row's actual objective began.

---

## 1. Verification of the SSOT claim, line-exact

### 1.1 Claim: "Every `fs_run_bash` is gated behind a trusted current-session PR draft"

**Partly true — precise form matters.** The gate is not on the tool name; it is on the *classified effect* of the command.

[`src/fa/inner_loop/hooks/intent_guard.py:121-127`](../../src/fa/inner_loop/hooks/intent_guard.py) —

```python
_DRAFT_REQUIRED_BASH_EFFECTS: frozenset[BashIntentEffect] = frozenset(
    {
        BashIntentEffect.INDEX_WRITE,
        BashIntentEffect.REPO_WRITE,
        BashIntentEffect.OPAQUE_EXEC,
    }
)
```

[`intent_guard.py:226-232`](../../src/fa/inner_loop/hooks/intent_guard.py) —

```python
def _requires_draft(call: ToolCall, repo_root: Path) -> tuple[bool, BashIntentAnalysis | None]:
    if call.name in _MUTATING_TOOL_NAMES:
        return True, None
    analysis = _bash_analysis_for_call(call, repo_root)
    if analysis is None:
        return False, None
    return analysis.effect in _DRAFT_REQUIRED_BASH_EFFECTS, analysis
```

So `READ_ONLY` and `VERIFY_ONLY` are genuinely exempt. The design intent is sound. **The defect is that the classifier almost never returns those two labels for real-world commands.**

### 1.2 The real producer site — `OPAQUE_EXEC` is the default, and the whitelist is tiny

[`src/fa/inner_loop/bash_intent.py:493`](../../src/fa/inner_loop/bash_intent.py) is the terminal fallback:

```python
return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"unsupported literal command: {head}",))
```

Reachable only after the read-only whitelist at [`bash_intent.py:62-99`](../../src/fa/inner_loop/bash_intent.py) (33 verbs) and the verifier matcher at [`bash_intent.py:247-280`](../../src/fa/inner_loop/bash_intent.py) (`pytest` / `mypy` / `ruff check` / `ruff format --check` only) both miss.

**Empirically probed at the tip** (executing the real `analyze_bash_for_intent` against the real `bashlex`):

| command | effect | reason |
|---|---|---|
| `ls` | `read_only` | ✅ |
| `cat foo.py \| head -20` | `read_only` | ✅ |
| `git status` | `read_only` | ✅ |
| `grep -rn foo src/` | `read_only` | ✅ |
| `pytest -q` | `verify_only` | ✅ |
| `python -m pytest -q` | `verify_only` | ✅ |
| `mypy src/fa --strict` | `verify_only` | ✅ |
| **`uv run pytest -q`** | **`opaque_exec`** | `unsupported literal command: uv` |
| **`.venv/bin/pytest -q`** | **`opaque_exec`** | `unsupported literal command: pytest` |
| **`just check`** | **`opaque_exec`** | `unsupported literal command: just` |
| **`seq 1 40000`** | **`opaque_exec`** | `unsupported literal command: seq` |
| **`sed -n 1,20p src/fa/cli.py`** | **`opaque_exec`** | `unsupported literal command: sed` |
| **`awk '{print}' f`** | **`opaque_exec`** | `unsupported literal command: awk` |
| **`sort` / `uniq` / `cut` / `tr` / `nl` / `jq`** | **`opaque_exec`** | not on the whitelist |
| **`basename` / `dirname` / `realpath` / `readlink`** | **`opaque_exec`** | not on the whitelist |
| **`sha256sum` / `md5sum`** | **`opaque_exec`** | not on the whitelist |
| **`command -v pytest` / `type pytest`** | **`opaque_exec`** | not on the whitelist |
| **`gh pr view 68`** | **`opaque_exec`** | `unsupported literal command: gh` |
| **`env`** | **`opaque_exec`** | `env without subcommand` |
| **`ps aux`** | **`opaque_exec`** | not on the whitelist |
| **`python3 --version`** | **`opaque_exec`** | `python executable` |
| **`for i in 1 2 3; do echo $i; done`** | **`opaque_exec`** | `unsupported node kind: compound` |
| **`{ echo A; seq 1 10; echo B; }`** | **`opaque_exec`** | `unsupported node kind: compound` |
| **`ls $(pwd)`** | **`opaque_exec`** | `word expansion in '$(pwd)'` |

Three structural amplifiers make this worse than a missing-verb list:

1. **`_reduce_analyses` is max-severity, not per-clause.** [`bash_intent.py:192-193`](../../src/fa/inner_loop/bash_intent.py) — a single `OPAQUE_EXEC` clause poisons the whole command. `echo START; seq 1 40000; echo END` has two `read_only` clauses and one unknown verb, and reduces to `opaque_exec`.
2. **Compound / brace / loop constructs are unconditionally opaque.** [`bash_intent.py:174-177`](../../src/fa/inner_loop/bash_intent.py) returns `OPAQUE_EXEC` for any node kind that is not `command` / `list` / `pipeline`. `{ …; }`, `for`, `if`, `while`, `case`, `$(…)` all land here regardless of content.
3. **Any word expansion is opaque.** [`bash_intent.py:571-575`](../../src/fa/inner_loop/bash_intent.py) — `ls $(pwd)` and even `echo "$HOME"` fail closed.

The fail-closed *direction* is correct and must be preserved (the module docstring at [`bash_intent.py:22-24`](../../src/fa/inner_loop/bash_intent.py) makes it an explicit design invariant). What is wrong is that the *safe* set is so small that fail-closed is the common path rather than the exceptional one.

**This is the real F6 root cause, and the SSOT does not name it.** The SSOT names only the downstream schema-discovery symptom.

### 1.3 Claim: "burns 3-4 `pr_prepare` calls discovering the schema by trial and error"

**Confirmed exactly, from the recorded events.** Reconstructed tool-call sequence:

`worklogs/reviews/live-trial-data/cae-s127-bash-tail-1788526685-1245712.events.jsonl`

| turn | tool | params sent | outcome |
|---|---|---|---|
| 1 | `fs_run_bash` | `command` | **DENY** `IntentGuard: missing or untrusted current-session PR draft` |
| 2 | `pr_prepare` | `body, degree_of_freedom_closed, deterministic_mechanism, fix_class, intent, invariant` | `invalid_params` — `` `fix_class` is only valid when `intent` is `FIX`; got `RESEARCH` `` |
| 3 | `pr_prepare` | *same six* | **identical error again** |
| 4 | `pr_prepare` | dropped `fix_class` | `invalid_params` — `` `degree_of_freedom_closed` is only valid when `intent` is `FIX` `` |
| 5 | `pr_prepare` | dropped `degree_of_freedom_closed` | `invalid_params` — `` `deterministic_mechanism` is only valid when `intent` is `FIX` `` |
| 6 | `pr_prepare` | `intent, invariant` | **ok** |
| 7 | `fs_run_bash` | `command` | ok — *the row's actual objective, on turn 7 of 10* |

`worklogs/reviews/live-trial-data/cae-s127-bash-stderr-1788527120-1246970.events.jsonl`

| turn | tool | outcome |
|---|---|---|
| 1 | `fs_run_bash` | **DENY** missing draft |
| 2 | `fs_run_bash` | **DENY** missing draft (retried blind) |
| 3 | `pr_prepare` | `` `fix_class` … got `CHORE` `` |
| 4 | `pr_prepare` | `` `degree_of_freedom_closed` … got `CHORE` `` |
| 5 | `pr_prepare` | `` `deterministic_mechanism` … got `CHORE` `` |
| 6 | `pr_prepare` | ok |
| 7 | `fs_run_bash` | ok — *turn 7 of 10* |

**Measured cost: 6 wasted turns (bash-tail) and 6 (bash-stderr).** The SSOT's "~5 wasted turns per bash row" is if anything conservative.

### 1.4 Claim: "The `pr_prepare` schema is undocumented in the tool description"

**Confirmed.** [`prepare_pr.py:269-278`](../../src/fa/inner_loop/tools/prepare_pr.py) — the entire model-visible description:

> "Write the per-session PR-description draft to `~/.fa/session-log/<run_id>/pr_draft.md` so the IntentGuard middleware (M-7) can validate subsequent mutating tool calls against the declared INTENT / INVARIANT (and the FIX-only CLASS / DEGREE-OF-FREEDOM CLOSED / DETERMINISTIC MECHANISM clauses). The path is fixed at session bootstrap; the tool takes no `path` parameter."

Note the trap: the description **names** the FIX-only clauses in a parenthetical that reads as an inventory of what the tool accepts. It never says *only when intent is FIX*. A model reading this and wanting maximum compliance sends all five — which is precisely what both live runs did.

The schema at [`prepare_pr.py:67-97`](../../src/fa/inner_loop/tools/prepare_pr.py) is worse, because it is *structurally* misleading rather than merely silent:

```python
_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["intent", "invariant"],          # :69
    "properties": {
        "intent":   {"type": "string", "enum": sorted(INTENT_VALUES)},          # :71-74
        "invariant": {..., "description": "One-line invariant statement. …"},   # :75-87  ← the ONLY description
        "fix_class": {"type": "string", "enum": sorted(CLASS_VALUES)},          # :88-91  ← no description
        "degree_of_freedom_closed": {"type": "string", "minLength": 1},         # :92     ← no description
        "deterministic_mechanism":  {"type": "string", "minLength": 1},         # :93     ← no description
        "body": {"type": "string", "maxLength": 64000},                         # :94     ← no description
    },
    "additionalProperties": False,                                              # :96
}
```

Four of six properties carry **no description at all**. The conditional rule — *these three are valid **iff** `intent == FIX`, and required iff `intent == FIX`* — exists only in Python at [`prepare_pr.py:136-168`](../../src/fa/inner_loop/tools/prepare_pr.py) (`_validate_fix_fields`). It is invisible on the wire.

Worth noting what the codebase already got right one property over: `invariant` **does** carry an inline description ([`prepare_pr.py:78-87`](../../src/fa/inner_loop/tools/prepare_pr.py)), added under S12.5/CT5 with the comment *"the model reads this schema, not the skill doc (live-trial D11: agents burned turns rediscovering the old `n/a` literal)"*. **The exact same lesson was learned, written down, applied to one field, and not applied to the other four.** F6 is the recurrence of D11 in the fields that were skipped.

### 1.5 Sub-claim not in the SSOT: the error messages are subtractive, not constructive

Every rejection at [`prepare_pr.py:162-166`](../../src/fa/inner_loop/tools/prepare_pr.py) names exactly one offending field and stops:

```python
return f"`fix_class` is only valid when `intent` is `FIX`; got `{intent.value}`"
```

`_validate_fix_fields` returns `str | None` — **first violation only, by construction**. With three surplus fields, the model needs three round-trips minimum to peel them off one at a time. That is the mechanical explanation for the "one field per turn" staircase in both event logs; it is not model stupidity.

The irony is documented in the function's own docstring at [`prepare_pr.py:143-149`](../../src/fa/inner_loop/tools/prepare_pr.py): *"this function fails fast so the LLM sees a focused error message rather than a six-violation dump for what is conceptually one omission."* The optimisation is correct for the **missing-field** direction (one omission → one message). It is exactly backwards for the **surplus-field** direction, where N surplus fields are also conceptually one mistake ("I sent the FIX shape for a non-FIX intent") but cost N turns.

Contrast the pattern the project already endorses — the F8 fix landed in this very PR, [`fs_search.py:65-77`](../../src/fa/inner_loop/tools/fs_search.py):

```python
def _ignored_params(data): return [{"param": name, "replacement": steer} for name, steer in _REMOVED_PARAMS if data.get(name) is not None]
def _attach_ignored_params(result, data): ...  # top-level ignored_params, result still returned
```

`fs_search` **accepts and ignores** inapplicable params, surfaces them loudly, and returns the result. `pr_prepare` **rejects** on the first one and returns nothing. Two tools in the same registry, opposite answers to the same question.

### 1.6 Sub-claim not in the SSOT: turn 3 of `bash-tail` re-sent byte-identical params

The model repeated the *exact same six-key payload* after a rejection. That is the signature of an error message that did not tell the model what to do next — only what not to have done. LoopGuard did not fire (different tool, and under the repeat threshold), so the turn was silently spent.

---

## 2. Legitimacy verdict

| SSOT claim | verdict | evidence |
|---|---|---|
| Every `fs_run_bash` gated behind a trusted draft | **partly true, mechanism mis-stated** | gate is on classified *effect*, `intent_guard.py:121-127`; but `OPAQUE_EXEC` is the practical default (§1.2) |
| First bash call denied | **TRUE** | both event logs, turn 1 |
| Model burns 3-4 `pr_prepare` calls discovering the schema | **TRUE, understated** | 4 calls (bash-tail), 4 calls (bash-stderr) |
| "every FIX-only field is rejected before it finds …" | **TRUE, and mechanically forced** | `_validate_fix_fields` returns first violation only, `prepare_pr.py:136-168` |
| ~5 wasted turns per bash row | **TRUE, understated** | 6 and 6 |
| Schema undocumented in the tool description | **TRUE** | `prepare_pr.py:269-278`; 4 of 6 properties have no `description` |
| Violates the forgiving-tools principle | **TRUE** | contrast `fs_search` leniency, `fs_search.py:65-77` |
| "Backlog candidate — not in s12.7 scope" | **superseded** | it is the largest measured turn-waster in the slice; I-58/I-59 already open |

**F6 is legitimate. Its stated root cause is incomplete.** The tool-description gap is real but is the *smaller* half; the classifier's over-broad `OPAQUE_EXEC` default is the larger half and is what makes the ceremony fire at all on rows that mutate nothing.

---

## 3. Alignment with project axes

Checked against [`knowledge/project-overview.md`](../../knowledge/project-overview.md).

**§1.2.5 compliance-by-construction, failure-observable.** The principle asks whether compliance is *enforced by construction rather than by LLM judgement*. Today the conditional field rule is enforced by construction (good) but **communicated by trial and error** (bad) — the model must discover a deterministic rule through a stateless search whose cost is turns. The construction side is fine; the *observability* side fails. The fix must keep the validator authoritative and make its rule visible on the wire; it must not weaken the validator.

**§1.2 minimalism-first, 5-question test** (for the tool-description change):
1. *Evidence?* Two live rows, 12 wasted turns, plus the same lesson already recorded as live-trial D11 and fixed for `invariant` only.
2. *Has an OSS stack removed this?* No stack requires an undocumented conditional schema; the standard is inline `description` per property — which this repo already does elsewhere.
3. *Can it be replaced?* No. A stateless LLM cannot learn a schema across sessions. The skill doc is not in the chat role's context.
4. *Deterministic function, no LLM call?* Yes — a static string and a pure validator. No LLM step added.

**§1.2 for the classifier widening:** answers (1)–(4) all hold; the change is a data-table extension plus a pure-function refinement, zero new components. **Nothing is added to the harness; the safe-set is widened and one string is enriched.** This is subtraction-second in the intended sense.

**Pillar 3 (token/tool-call efficiency), KPI #2 "median tool-calls / completed task".** F6 costs a fixed ~6-turn tax on the first mutating-or-opaque bash call of *every* session. On a 10-turn budget that is 60 %. This is the single highest-leverage KPI item observed in S12.7.

**§1.2.7 Pair over Autonomy / I-7.x.** Ceremony that the pair partner must brute-force is the opposite of a good pair surface. Forgiving-tools is the operator's binding principle, cited twice in the SSOT.

**Anti-shallow-fix gate (§1.2.5).** This work is `INTENT: FIX`. Each proposed change below carries a named producer-site degree of freedom and a deterministic mechanism with a resolvable citation — drafted in §5. Adding a *guard* at the deny site without naming the producer freedom would be exactly the AP-003 shape the gate exists to catch; that is why §4 fixes the classifier and the schema, not the deny message alone.

---

## 4. Proposed fix, in dependency order

Four changes. **C1 and C2 close the two producer-site degrees of freedom; C3 and C4 are the observability companions.** Each is independently landable and independently testable.

### C1 — Widen the deterministic read-only / verify-only safe set (closes I-58)

**Degree of freedom closed:** `analyze_bash_for_intent` labels a command `OPAQUE_EXEC` — thereby requiring a PR draft — whenever its head verb is absent from a 33-entry whitelist, even when the verb provably cannot mutate the workspace. The draft requirement is therefore decided by an omission in a data table rather than by the command's actual effect.

**Deterministic mechanism:** extend `_READ_ONLY_COMMANDS` (`src/fa/inner_loop/bash_intent.py:62`) with the pure-filter / pure-inspect POSIX set, and add a `_VERIFY_ONLY_RUNNERS` unwrap so `uv run <verifier>` and path-qualified verifier binaries route through the existing `_normalise_verifier` matcher (`src/fa/inner_loop/bash_intent.py:247`).

Concretely:

- **Add to `_READ_ONLY_COMMANDS`** (all pure stdin→stdout filters or pure inspectors, none can write without a redirect — and a redirect is *already* independently detected by `_analyze_redirects` and escalates to `REPO_WRITE`, so widening this list does not widen write authority):
  `seq`, `sort`, `uniq`, `cut`, `tr`, `nl`, `rev`, `fold`, `column`, `paste`, `join`, `comm`, `expand`, `unexpand`, `basename`, `dirname`, `realpath`, `readlink`, `md5sum`, `sha1sum`, `sha256sum`, `cksum`, `jq`, `yq`, `xxd`, `od`, `strings`, `ps`, `env` (bare), `printenv`, `command`, `type`, `sleep`, `yes`, `tac`, `awk`, `sed` **(only when no `-i`)**.
- **`sed` needs care.** `_sed_target_files` (`bash_intent.py:307`) already exists for the `-i` in-place case. Route `sed` to `READ_ONLY` **only** when no `-i` / `--in-place` token is present; otherwise keep today's `REPO_WRITE`/`OPAQUE` path. Same shape for `perl -i`.
- **`awk`** likewise: `READ_ONLY` unless it carries a write redirect (already handled) — note `awk` can write via `print > "file"` inside its program text, which is *not* visible to bashlex. **Decision required from operator (Q1 below).** Conservative default: leave `awk` out of the safe set.
- **`uv run <cmd>` / `uvx <cmd>`:** add an unwrap analogous to `_unwrap_env` (`bash_intent.py:227`), so `uv run pytest -q` re-enters `_analyze_literal_words` as `pytest -q` → `VERIFY_ONLY`. `uv run` with a non-verifier tail stays `OPAQUE_EXEC` — the unwrap widens nothing on its own.
- **Path-qualified verifiers:** `_normalise_verifier` (`bash_intent.py:247`) matches `words[0]` exactly, so `.venv/bin/pytest` misses while `pytest` hits. `_is_read_only` (`bash_intent.py:287-289`) already basenames via `Path(words[0]).name`. Make `_is_verify_only` consistent by basenaming its head the same way. This is a **one-line consistency fix between two sibling predicates in the same module**, not a trust widening: the strict word-for-word match on `words[1:]` is untouched, and the module already argues this exact case for the Python interpreter at `bash_intent.py:426-433`.
- **Per-clause reduction for mixed-safety lists.** `_reduce_analyses` (`bash_intent.py:192`) currently poisons the whole command on one `OPAQUE_EXEC` clause. **Leave this as-is.** It is a genuine safety property (an opaque clause can do anything, including to paths a sibling clause names) and changing it is a much larger risk surface than the whitelist. Note it in the plan as explicitly-considered-and-rejected.
- **Compound / brace / loop node kinds** (`bash_intent.py:174-177`): **leave as-is** for the same reason. `{ echo A; seq 1 10; }` stays opaque. Recursing into compound bodies is the I-59 refactor, not this slice.

**Fail-closed direction is preserved.** Every addition is a verb that cannot write absent a redirect, and redirects are detected upstream of the verb lookup.

**Live-behaviour delta:** `s127-bash-tail`'s `{ echo START_MARKER; seq 1 40000; echo END_MARKER; }` stays `OPAQUE_EXEC` (brace group). So C1 alone does **not** fix that row — which is precisely why C2/C3 are not optional.

### C2 — Make the `pr_prepare` conditional schema visible on the wire

**Degree of freedom closed:** the rule *"`fix_class` / `degree_of_freedom_closed` / `deterministic_mechanism` are valid iff `intent == FIX`"* is enforced in Python (`prepare_pr.py:136-168`) but is absent from every model-visible surface, so a caller's only route to the correct payload shape is trial-and-error rejection.

**Deterministic mechanism:** add a `"description"` to each of the four undescribed properties in `_INPUT_SCHEMA` (`src/fa/inner_loop/tools/prepare_pr.py:88-94`) naming the FIX-only conditionality, and extend the `ToolSpec.description` (`src/fa/inner_loop/tools/prepare_pr.py:270`) with a per-intent required-field table plus one worked non-FIX example.

Shape (illustrative, exact bytes settled at implementation):

```
Required always: intent, invariant.
  RESEARCH / CHORE -> intent + invariant only. invariant is free-form.
  ADR-RULE -> invariant starts "Contract: "
  IMPLEMENT -> invariant starts "Implements: "
  FIX -> invariant starts "Affects: " AND requires fix_class +
         degree_of_freedom_closed + deterministic_mechanism.
Send the three FIX-only fields ONLY for intent=FIX; they are rejected otherwise.
Example (chore): {"intent": "CHORE", "invariant": "n/a (read-only recon)"}
```

Constraints that bind this change:
- **PTS-v1 portability.** `validate_tool_schema_portability` (`registry.py:289`) is called on every registered spec (`registry.py:425`). `description` on a property is already used by `invariant` (`prepare_pr.py:78`) and passes; adding more is within the profile. `if/then/else` and `dependentRequired` are **not** in PTS-v1 — the conditionality must be expressed in prose, not in JSON Schema keywords. Confirmed by reading `_validate_schema_header` / `_validate_schema_children` / `_validate_schema_values`.
- **Token budget.** `estimate_tokens` (`profiles.py:433-445`) sums description + schema JSON. Target ≤ ~120 added tokens; a 6-turn saving buys that back on the first bash call of any session.
- **Prompt-cache stability.** `prompt_composer.py:43-59` hashes `name` + `input_schema` for cache identity, excluding `description`. Enriching the schema changes the cache key **once**, at deploy, not per session. Acceptable; note it in the PR.
- **ADR-10 I-1 single-source-of-truth.** The prose must be *derived from* `INVARIANT_REQUIRED_PREFIXES` (`pr_intent.py:391`) and `INTENT_VALUES` / `CLASS_VALUES` where mechanically possible — f-string the enum members rather than hand-typing them, exactly as `intent`'s `enum` already does at `prepare_pr.py:73`. A snapshot test pins the rest against the skill doc (`tests/test_pr_intent_snapshot.py` is the existing dual-located-rule guard).

### C3 — Forgiving surplus-field handling, aligned with the F8 `ignored_params` precedent

**Degree of freedom closed:** `_validate_fix_fields` (`prepare_pr.py:136-168`) returns the **first** violation only and rejects the whole call, so a caller who sent N surplus FIX-only fields under a non-FIX intent pays N round-trips to discover a single conceptual mistake.

**Deterministic mechanism:** for the surplus-field direction, collect **all** inapplicable fields in one pass, drop them from the render, succeed, and report them in a top-level `ignored_params: [{param, replacement}]` on the `ToolResult`, mirroring `_attach_ignored_params` (`src/fa/inner_loop/tools/fs_search.py:74-77`).

**Asymmetry is deliberate and must be preserved:**
- **Surplus** FIX-only fields under a non-FIX intent → **accept, ignore, report loudly.** The draft renders correctly without them (`_render_draft` at `prepare_pr.py:100-134` already only emits them `if intent == Intent.FIX`, line 121 — so the surplus fields are *already* discarded by the renderer; the validator rejects a call the renderer would have handled fine). Nothing about the resulting draft is weakened.
- **Missing** required fields under `INTENT: FIX` → **keep rejecting.** These are the anti-shallow-fix gate's load-bearing clauses (§1.2.5). Relaxing that direction would let a FIX draft through without a `DETERMINISTIC MECHANISM`, which is the exact failure AP-003 catalogues. **Do not touch.**
- **Invariant prefix mismatch** → **keep rejecting** (`_validate_invariant_prefix`, `prepare_pr.py:171-185`). It is shape-bearing and already carries a constructive message naming the expected prefixes.

When rejection *is* correct (the FIX-missing-fields direction), collect all violations into one message instead of returning on the first, so one turn closes the whole gap.

This makes `pr_prepare` and `fs_search` give the same answer to the same question, which is itself the ADR-10 I-1 consistency argument.

### C4 — Constructive deny message on the IntentGuard missing-draft path

**Degree of freedom closed:** `_MISSING_DRAFT_REASON` (`src/fa/inner_loop/hooks/intent_guard.py:138-141`) names the required tool but not the payload that would satisfy it, so a denied model's cheapest next action is an under-informed guess.

**Deterministic mechanism:** extend the constant to carry the minimal satisfying payload and the classified effect that triggered the gate — e.g. `… call \`pr_prepare\` first; for read-only recon the minimal draft is {"intent": "CHORE", "invariant": "n/a (recon)"} (this command classified as opaque_exec: unsupported literal command: seq)`.

The `BashIntentAnalysis.reasons` tuple is already computed and already threaded to the decision site (`intent_guard.py:304`, `bash_analysis` is in scope at the `_decide` call on `:310`) — **it is currently discarded.** Surfacing it is failure-observability per §1.2.5, and it doubles as the operator's diagnostic for which verb is missing from the C1 whitelist.

Also worth pinning: `_READINESS_PROMPT_EXTRA` (`src/fa/cli.py:158-168`) already tells the model *"Before the first workspace mutation, call `pr_prepare` (use CHORE for chores)"*. That line is in the cacheable prefix and is the right seat for a one-line payload example — cheaper than any per-call surface. Consider extending it in the same change.

### Explicitly out of scope

- The `_reduce_analyses` max-severity rule and the compound-node opacity (§C1) — deliberately unchanged, noted as considered.
- The I-59 structural refactor (rule composition, per-intent policy objects) — stays deferred; operator set it P4.
- `intent_guard.mode: observe` — the existing tactical lever (`intent_guard.py:130-136`) is not a substitute for the semantic fix and is not touched.

---

## 5. Anti-shallow-fix gate — draft PR clauses

Per §1.2.5 / `knowledge/skills/pr-creation/SKILL.md`. Citations resolve at the tip; they will be re-resolved against the staged tree at commit time.

```text
INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: IntentGuard draft gate + pr_prepare schema surface (S12.7 F6, backlog I-58)

DEGREE-OF-FREEDOM CLOSED: two producer sites let a non-mutating bash call
cost ~6 turns of ceremony — (a) analyze_bash_for_intent labels any verb
outside a 33-entry whitelist OPAQUE_EXEC and therefore draft-requiring,
so the gate fires on reconnaissance that cannot write; (b) pr_prepare's
"FIX-only fields are invalid under other intents" rule is enforced in
Python but absent from every model-visible surface, and is reported one
field per rejection, so the correct payload is reachable only by N
round-trips.

DETERMINISTIC MECHANISM: (a) the read-only/verify-only safe set is widened
to the pure-filter POSIX verbs and uv-run/path-qualified verifier forms so
the effect label follows the command's actual write capability, with
redirect detection unchanged upstream of the verb lookup —
src/fa/inner_loop/bash_intent.py:62; (b) the per-intent field contract is
rendered into the wire schema and tool description, and surplus FIX-only
fields under a non-FIX intent are accepted-and-reported via a top-level
ignored_params list instead of rejected one at a time, mirroring the
fs_search leniency precedent — src/fa/inner_loop/tools/prepare_pr.py:88.

TEST-EDITS:
tests/test_bash_intent.py — new safe-set verbs and uv-run unwrap must be pinned
tests/test_prepare_pr.py — surplus-field leniency replaces first-violation rejection
tests/test_intent_guard.py — deny message now carries the classified effect reason
```

---

## 6. Test plan

### 6.1 Offline (pytest) — added with the code

| test file | pins |
|---|---|
| `tests/test_bash_intent.py` | every newly-safe verb → `READ_ONLY`; **kill-check**: each still escalates to `REPO_WRITE` with `> out.txt`; `sed -i` stays mutating while `sed -n` is read-only; `uv run pytest` → `VERIFY_ONLY` but `uv run rm -rf /` → `OPAQUE_EXEC`; `.venv/bin/pytest` → `VERIFY_ONLY`; brace/compound/`$(…)` **still** `OPAQUE_EXEC` (guards the deliberate non-change) |
| `tests/test_prepare_pr.py` | `{intent: CHORE, fix_class, dof, mechanism}` → **ok**, all three in `ignored_params`, rendered draft byte-identical to the two-field call; `INTENT: FIX` missing all three → **one** rejection listing **all three**; invariant-prefix mismatch still rejects |
| `tests/test_s127_doc_gates.py` | `pr_prepare` description contains one required-field line per `INTENT_VALUES` member and one non-FIX example; each FIX-only property carries a `description` mentioning FIX — derived from the enum, so adding an intent fails the test |
| `tests/test_intent_guard.py` | missing-draft deny message contains the minimal payload example **and** the `BashIntentAnalysis.reasons` head; read-only bash never reaches the draft branch |
| `tests/test_prompt_registry_coherence.py` | `validate_tool_schema_portability` still passes; `estimate_tokens` delta within budget |

Full suite after every edit: `tests/test_live_check_script.py` + `scripts/adversarial_battery_live_check.sh`, per the operator's standing rule.

### 6.2 Live rows for the host harness (`scripts/run_live_check.sh`)

Two new rows, following the `s127_row` / `s127_expect` / `s127_finish` conventions at `scripts/run_live_check.sh:568-572`.

**`s127-bash-recon-nodraft`** — C1 + C4. Task: run three read-only recon commands (`wc -l` on a source file, `sort` a small listing, `uv run pytest --version`) and report the outputs. Nothing may be written.
- `[PASS]` `fs_run_bash` ran
- `[PASS]` **absent** `missing or untrusted current-session PR draft`
- `[PASS]` **absent** `"tool_name": "pr_prepare"` — the row's whole point is that no ceremony was needed
- kill-check: pre-fix this row denies on turn 1

**`s127-prprepare-firstcall`** — C2 + C3. Task: declare a CHORE intent with `pr_prepare` before running one bash command, then run it.
- `[PASS]` `pr_prepare` succeeded
- `[PASS]` **at most one** `pr_prepare` call in the run (the discovery staircase is gone) — assert on the *count*, not on presence
- `[PASS]` **absent** `is only valid when .intent. is .FIX.`
- `[PASS]` if surplus fields were sent, `ignored_params` appears and the call still succeeded
- kill-check: pre-fix this row shows 4 `pr_prepare` calls

**Re-runs of existing rows** to confirm the turn-tax is gone: `s127-bash-tail`, `s127-bash-stderr`, `s127-bash-small` (the last is still pending in the SSOT progress table and should be run once, post-merge, on the fixed build).

---

## 7. Open questions for the operator

1. **`awk` in the read-only safe set?** `awk` can write via `print > "file"` inside its program text, which bashlex cannot see. Conservative default in the plan above is **exclude**. Include it (accepting the blind spot) or keep it opaque?
2. **Scope of C1 vs. C3 in one PR.** C1 (classifier) and C2/C3 (pr_prepare surface) are independent and separately revertable. Land as one FIX PR closing I-58, or split — classifier first (bigger KPI win, bigger risk surface), schema second?
3. **`s127-bash-tail`'s brace group stays opaque** under this plan by design. Accept that the row keeps a (now one-turn, not six-turn) ceremony, or also reword the row's task to a non-brace form?
4. **I-58 / I-59 disposition.** This work closes I-58 outright. Mark I-59 as partially addressed (deny-reason taxonomy improved by C4) but still open for the structural refactor, or leave I-59 untouched?

---

## 8. Citation index (all re-resolved at `fc1f2e6`)

| citation | what |
|---|---|
| `src/fa/inner_loop/hooks/intent_guard.py:121-127` | `_DRAFT_REQUIRED_BASH_EFFECTS` |
| `src/fa/inner_loop/hooks/intent_guard.py:138-141` | `_MISSING_DRAFT_REASON` |
| `src/fa/inner_loop/hooks/intent_guard.py:226-232` | `_requires_draft` |
| `src/fa/inner_loop/hooks/intent_guard.py:304-310` | `bash_analysis` computed, reasons discarded at deny |
| `src/fa/inner_loop/bash_intent.py:22-24` | fail-closed design invariant |
| `src/fa/inner_loop/bash_intent.py:62-99` | `_READ_ONLY_COMMANDS` (33 verbs) |
| `src/fa/inner_loop/bash_intent.py:174-177` | compound nodes → `OPAQUE_EXEC` |
| `src/fa/inner_loop/bash_intent.py:192-193` | `_reduce_analyses` max-severity |
| `src/fa/inner_loop/bash_intent.py:227-233` | `_unwrap_env` (template for `uv run`) |
| `src/fa/inner_loop/bash_intent.py:247-280` | `_normalise_verifier` |
| `src/fa/inner_loop/bash_intent.py:287-289` | `_is_read_only` basenames; `_is_verify_only` does not |
| `src/fa/inner_loop/bash_intent.py:307` | `_sed_target_files` |
| `src/fa/inner_loop/bash_intent.py:426-433` | basename-matching precedent for interpreters |
| `src/fa/inner_loop/bash_intent.py:493` | terminal `OPAQUE_EXEC` fallback |
| `src/fa/inner_loop/bash_intent.py:571-575` | word-expansion → opaque |
| `src/fa/inner_loop/tools/prepare_pr.py:67-97` | `_INPUT_SCHEMA`; 4 of 6 props undescribed |
| `src/fa/inner_loop/tools/prepare_pr.py:78-87` | `invariant` description (the D11 precedent) |
| `src/fa/inner_loop/tools/prepare_pr.py:100-134` | `_render_draft` already drops surplus FIX fields (line 121) |
| `src/fa/inner_loop/tools/prepare_pr.py:136-168` | `_validate_fix_fields`, first-violation-only |
| `src/fa/inner_loop/tools/prepare_pr.py:171-185` | `_validate_invariant_prefix` |
| `src/fa/inner_loop/tools/prepare_pr.py:269-278` | `ToolSpec.description` |
| `src/fa/inner_loop/tools/fs_search.py:65-77` | `ignored_params` leniency precedent (F8) |
| `src/fa/inner_loop/registry.py:289` / `:425` | PTS-v1 portability gate |
| `src/fa/inner_loop/prompt_composer.py:43-59` | cache identity = name + input_schema |
| `src/fa/inner_loop/profiles.py:433-445` | `estimate_tokens` |
| `src/fa/cli.py:158-168` | `_READINESS_PROMPT_EXTRA` |
| `src/fa/hygiene/pr_intent.py:379-391` | `INVARIANT_REQUIRED_PREFIXES` |
| `worklogs/BACKLOG.md:2875-2896` | I-58, I-59 |
| `worklogs/reviews/live-trial-data/cae-s127-bash-tail-1788526685-1245712.events.jsonl` | 6-turn ceremony |
| `worklogs/reviews/live-trial-data/cae-s127-bash-stderr-1788527120-1246970.events.jsonl` | 6-turn ceremony |
