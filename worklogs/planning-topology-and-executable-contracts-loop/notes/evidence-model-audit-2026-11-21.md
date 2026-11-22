# Evidence-model audit — what `KIND`/`EVIDENCE` actually do, and what they must do

**Date:** 2026-11-21<br>
**Scope:** `plan_v2.py` evidence matrix, `acceptance_bundle.py` seal, `plan_admission.py` grants,
`acceptance_closure.py` budgets, `prompt.py` V1/V2 prompt split.<br>
**Status:** source audit + read-only measurements. No production change in this commit.<br>
**Authority:** [i03-ai-native-workflow-refactor-plan-v2.md](i03-ai-native-workflow-refactor-plan-v2.md), Q-V2-ACC-2.

---

## 1. What the system is for

The workflow exists to make one thing true: **the artifact an AI produces is checked by something
other than the AI that produced it, and the check cannot be talked around.**

Every mechanism in the stack follows from that:

| Mechanism | The property it buys |
|---|---|
| Planner writes documents, coder writes code, different stages | the author of the claim is not the author of the proof |
| `INV → CT → TEST-ID → selector → one nodeid` | a claim maps to an executable check, or the mapping is refused |
| The seal binds exact bytes at an exact revision | the check that ran is the check that was reviewed |
| `MUTATION` view confined to `{"src","scripts"}` | the coder cannot edit the tests it must pass |
| Verifier runs the sealed closure in a managed cell | the proof is produced in an environment the author does not control |
| `ToolResult.fail` on settled create failure | "finished" and "created the project" are the same statement |

This is why the evidence model is not bookkeeping. It is the only place the system records
*how a claim is checked*. If that record can be left empty without anyone refusing, the chain
above still looks intact — seals still mint, verifiers still run, verdicts still print — and
nothing is actually being guaranteed.

---

## 2. The four measured facts

All four were verified by executing the production code, not by reading it.

### Fact 1 — `KIND` is read in exactly one place, and it only exempts

`grep -rn 'invariant.kind'` over `src/fa/` returns one hit: `plan_v2.py:622`,
`if invariant.kind != "HARD": continue`.

`KIND` therefore reaches nothing: not the seal, not verification, not the verdict, not the
report. Its entire function is to decide whether `_admit_evidence` refuses. `SOFT` is not a
severity; it is an exemption flag.

### Fact 2 — a `HARD` invariant may be waived, which the plan forbids

The plan states, in its grammar delta:

> `NON_EXECUTABLE` is forbidden for HARD/ready contracts unless Q-V2-ACC-2 is resolved under a
> ratified rule.

Measured: a plan with `INV-2 / KIND: HARD / EVIDENCE: NON_EXECUTABLE /
DISPOSITION-REASON: OWNER_APPROVAL` is **admitted**, and after `bind_dispositions` the contract
grades `ATTESTED` and lands in `seal.attested`.

```
BEFORE grant: {'CT-1.1': 'executable', 'CT-1.2': 'uncovered'}  attested: ()
AFTER  grant: {'CT-1.1': 'executable', 'CT-1.2': 'attested'}   attested: ('CT-1.2',)
```

So the strictest class in the vocabulary can be converted into a human signature by the
planner *choosing* `NON_EXECUTABLE` on it. The one class the plan protects most strongly is
the one the code lets through. `PRESERVATION` is protected correctly (refused with
`preservation-without-executable-evidence`, because the class check precedes the waiver
check at `:617`).

**This, not the `SOFT` gap, is the defect that matters.** Q-V2-ACC-2's wording ("hard
INV/ready CT") describes what the code does *not* do.

### Fact 3 — the seal cannot express "some contracts are unverified"

The seal record carries `selectors` (contracts with a test) and `attested` (contracts with a
grant). It does not carry the graph, so it does not carry a contract count. `UNCOVERED`
contracts are simply absent from both lists.

Consequence: given a seal alone, `|selectors| + |attested|` is the only count available, and
it silently equals "all contracts" only when nothing is uncovered. A seal over a plan with 5
contracts, 1 test and 1 grant is byte-identical in shape to a seal over a plan with 2
contracts, 1 test and 1 grant. **The consumer cannot tell "we waived the rest" from "the rest
were never mentioned".**

This is the downstream cost of Fact 1: `UNCOVERED` is computed but never recorded and never
refused, so it has no consequence anywhere in the system.

### Fact 4 — `"ready CT"` does not exist

`grep -rn 'ready_ct\|ready CT\|READY_CT'` over `src/fa/` returns nothing. The plan's central
requirement is stated over a category the implementation never defines. This is not a coding
oversight; it is the signature of a requirement that was never given a runtime meaning.

---

## 3. The root cause, stated plainly

Two authorities describe the grammar and they disagree.

| | Canonical schema `artifact-schema-and-grammar.md` | Runtime parser `plan_v2.py` |
|---|---|---|
| Format marker | `AI-NATIVE-PLAN-V2`: **0 occurrences** | required, exactly once |
| `KIND:` | **0 occurrences** | required per invariant |
| `EVIDENCE:` | 3 hits, all about `ledger.md` provenance | required per invariant |
| Contracts | `CT<n> [CLASS]: ...` (**0** `CT-` hits) | `CT-1.1 [CLASS] INV: ...` |
| Tests | `TESTS: <path>` + ```` ```verify ```` fence | `ACCEPTANCE: TEST-ID/CT/SELECTOR` + kill targets |
| Classes | FUNCTIONAL / CONSTRAINT / PRESERVATION | same |

The plan says this document is *"the sole V2 grammar/source-of-truth after cutover"* and
*"not yet a runtime-admitted artifact"*. The parser is the de-facto truth; the nominal truth
is V1 prose. `knowledge/skills/plan-authoring` and `knowledge/skills/feature-planning` both
still teach `TESTS:`; four conformance tests read the schema.

`prompt.py` already reflects the split: `AUTHORING_SYSTEM_PROMPT` (V2, `INVARIANTS`/`KIND`,
line 1245) is used for `CREATE_NEW_PROJECT`, while `ACQUISITION_SYSTEM_PROMPT` and the
`ORDINARY_PLANNING` path still teach `TESTS:` + `verify` fences.

**Every evidence question is unanswerable while this is true.** You cannot say "every HARD
invariant must have a test" when the document that defines invariants does not mention
`HARD`. This is precisely the drift the plan named as the reason the router and the parser
diverged.

---

## 4. Recommendation

**Do not ship C as the whole answer.** C (refuse at seal while any contract is `UNCOVERED`) is
correct but insufficient: it would make the system refuse plans whose defects the vocabulary
cannot describe, and it leaves the `HARD` waiver hole open, because a waived `HARD` contract is
`ATTESTED`, not `UNCOVERED` — C would wave it through.

The dependency order is:

### Step A — give `KIND` a meaning, and enforce the one the plan already states (small, blocking)

1. `HARD` + `NON_EXECUTABLE` → refuse (`hard-invariant-cannot-be-waived`). The plan already
   says this; the code does not. This is a **bug fix**, not a policy choice.
2. `SOFT` becomes the only waivable class, and only through the existing ratified pipeline
   (typed reason → caller grant → `ATTESTED`). That is *already* implemented and correct.
3. `UNCOVERED` becomes impossible to ship: `mint_seal` refuses while any contract is
   `UNCOVERED`, with the rule naming the contract.

After Step A the vocabulary is tautological in the good sense: `HARD` = must be executed,
`SOFT` = may be attested by a human, nothing = not admissible. No third state to reason about.

### Step B — make the seal self-describing (small)

Add the contract count and the uncovered set (always empty after Step A, which is the point:
the seal states the invariant it enforces) to the seal record. Cost: one field, one version
bump. Benefit: a seal becomes auditable without the plan graph, and a future regression that
reintroduces an uncovered contract is detectable from bytes already on disk.

### Step C — make the canonical schema the V2 schema (large, blocking, plan-mandated)

Rewrite `artifact-schema-and-grammar.md` to describe `plan_v2.py` (or the agreed final grammar),
then update `knowledge/skills/plan-authoring`, `knowledge/skills/feature-planning` and the four
conformance tests in the same change. The plan requires this *before* SLICE3 work is credible:
`SLICE1` is "canonical V2 grammar, strict graph validation, and admission cutover".

Until Step C, every new contract designs against a document that cannot answer questions about
its own vocabulary — which is exactly how this audit found four problems in one afternoon.

---

## 5. On Q-V2-ACC-1 (test closure)

Measured: the budgets exist and are strict — 512 files, 4 MiB/file, 16 MiB aggregate, 4096
path chars, depth 64, and refusal of symlinks, hidden components, nested `conftest.py`,
hardlinks and foreign-uid files. `pytest_argv` pins `-c`/`--rootdir` and a closed `--addopts`
(no `-p`, `-c`, `-o`, `--rootdir`, plugins or paths). Covered by 30 tests in
`test_ai_native_acceptance_closure.py`.

So the *enforceable budgets* half of Q-V2-ACC-1 is implemented. The *transitive closure* half
is not, and cannot be: see the boundary below. Record the budget half as closed-by-code, and
file the transitive half as a named residual rather than an open gate.

**The honest boundary.** A sealed test may import a package from outside `acceptance/` and the
closure will not see it. On the `MUTATION` route the verifier imports the *current candidate*
by design (CT-3.6 requires exactly that), so this is intended for the code under test — but it
means "sealed closure" guarantees the *test bytes*, never the *import graph*. No static check
inside this design can close that; pretending otherwise would be a hash-only sidecar by another
name, which the plan refuses.

---

## 6. Ledger entry

Recorded as `E601`.
