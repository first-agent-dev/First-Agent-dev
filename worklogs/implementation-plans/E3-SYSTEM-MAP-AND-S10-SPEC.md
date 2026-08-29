# E3 system map + S10 specification — rev 3

**Status:** DRAFT for operator review — no code written yet
**Date:** 2026-08-27
**Revision:** rev 3 — merge of two independent adversarial reviews of rev 1.
Base is rev 2 (full-paper verification pass; resolves Q24/Q25/Q27 with
argument). Merged in from the parallel review: the H-reuse correctness
argument (§1.12 item 4, gap-14 deferral, new exit criterion), the
`difficulty_to_level` explicit-mapping requirement (§3.2), and the
"`ŝ` is aspirational in the paper too" framing (§1.11). Operator decisions
pending in §3.10.
**Source:** arXiv 2607.13034v1, Yin & Feng (UTK; Microsoft), "Do AI Agents
Know When a Task Is Simple? Toward Complexity-Aware Reasoning and Execution".
All 14 HTML chunks read.
**Sourcing note:** every figure, table value and quotation below is taken from
the arXiv HTML we fetched. Front-matter metadata that could *not* be verified
against that source (journal of record, page/figure counts, the code-release
URL, the simulation seed) appeared in rev 2 and has been removed rather than
carried into ADR-16 unsourced. Re-add only from the PDF front matter.
**Upstream:** `PLAN-complexity-aware-execution-chat-role.md` (S1–S6),
`PLAN-ADDENDUM-deterministic-routing-S7-S9.md` (S7–S9)

---

## Part 1 — The complete E3 system, as the paper defines it

### 1.1 The object model

| Symbol | Definition | Where consumed | § |
|---|---|---|---|
| `τ = (q, E, V)` | task = query, environment (a repo), acceptance check `V` returning success/failure | throughout | 3.1 |
| `π = (a₁…a_T)`, `aₜ ∈ 𝒜` | trajectory: a sequence of tool calls | throughout | 3.1 |
| `𝒜` | action set: `list_dir, search, read_range, inspect_file, dependency_trace, edit, reason, verify` | — | 4.5 |
| `T_lat, N_tok, N_tool, N_file` | cost axes: wall-clock latency; **reasoning + context** tokens; tool calls; **distinct files pulled fully into context** | Eq. 1 | 3.1 |
| `α, β, γ, δ` | weights rendering the axes commensurable; raw axes also reported "so that conclusions do not hinge on a single weighting" | Eq. 1 | 3.1 |
| `C(π)` | scalar trajectory cost, Eq. 1 | throughout | 3.1 |
| `ε` | reliability target: success must hold with probability ≥ 1−ε. **Never numerically fixed in the paper** | Eq. 2 | 3.2 |
| `π*` | minimum-sufficient trajectory, Eq. 2; oracle-constructible in a controlled environment, "which makes `C_min` measurable rather than hypothetical" | Eq. 2 | 3.2 |
| `C_min(τ)` | `C(π*)` — the effort the task *ought* to require | Eq. 3 | 3.2 |
| `C_act(τ)`, `ACRR(τ)` | realized cost; `(C_act − C_min)/C_min`, Eq. 3 | metric | 3.3 |
| `f` | estimator: `f(q, E, M)` | Stage 1 | 3.4, 4.2 |
| `x₀ = (d̂, ŝ, r̂, ĉ)` | initial operating point: estimated difficulty, scope (files/sites to touch), risk, confidence | see map below | 3.4 |
| `M` | **prior experience** — third input to `f` in Eq. 4 and Algorithm 1 line 2. **Never instantiated in the reference implementation** (which is lexical + ≤1 probe) | Eq. 4 only | 3.4 |
| `K` | bound on the number of expansions — an *input*; the paper **never states the value used** | Alg. 1 | 4.1, 4.4 |
| `ℓ ∈ {1,2,3}` | current scope level; seeded `ℓ ← d̂` | Alg. 1 | 4.1, 4.3 |
| `ℋ` (`H`) | cached search hits — produced by Estimate's probe, **consumed by Execute at ℓ≥2**, carried across expansions | Alg. 1 | 4.1–4.4 |

**Component-consumption map (design-critical).** Eq. 4 defines four
components; Algorithm 1 and §§4.3–4.4 consume only three:

| Component | Consumption point | Note |
|---|---|---|
| `d̂` | seeds `ℓ` (Alg. 1 line 3) — **the route** | the only estimate the control loop reads directly |
| `ŝ` | **nowhere** | defined in Eq. 4, never consumed; the reference loop is level-driven. Do not implement `ŝ`-consumption and call it fidelity |
| `r̂` | verification posture inside Execute (§4.3) | never the route, never a tool-withholder |
| `ĉ` | conflict flag "flagging a candidate for expansion" (§4.2); plus the low-confidence trigger of §4.1/Fig. 1 — see §1.3 | the only component with a contested consumption point |

> **→ For S10.** (1) `M` is a free socket the paper leaves open: First-Agent's
> calibration history (`fa stats --calibration`) is a legitimate `M`. Keep
> `f`'s signature swappable — §6.2: "the same interface accepts an LLM-backed
> estimator as a drop-in" (compatible with Principle 1 *today*, evolvable
> later). (2) S10b's path-tier resolver is an instantiation of the paper's
> "cheap environment probes on `E`" — exactly the `E` term our S7 estimator
> lacks (gap 8). (3) Gap 6's real shape: our `risk`-as-dead-alias mirrors the
> paper's own `ŝ` — dead symbols happen in the reference too; the fix is to
> *wire `r̂` to the verifier* (S10b), not to invent consumers for everything
> in the tuple.
>
> **(4) The framing this map forces — S10 is not a conformance exercise.**
> `x₀` is a 4-tuple, but the control loop consumes only `d̂` (as `ℓ ← d̂`),
> `ĉ` (prose-only), and `r̂` (one prose use in §4.3); `ŝ` gets none. So we are
> **not** "fixing our code against a fully-specified paper" — we are
> *specifying what the paper left aspirational*. Two consequences, both
> binding on S10: do **not** over-invest in `ŝ` (it buys nothing the paper can
> vouch for), and treat `ℓ ← d̂` as a **decision, not an inheritance** —
> Algorithm 1 line 2 identifies a difficulty estimate with a 3-valued scope
> level *by fiat*. S10a makes that mapping an explicit, unit-tested function
> (§3.2), so the conflation is reviewable instead of being an accident of
> notation we copied.

### 1.2 The four equations

```
Eq.1  C(π)   = α·T_lat + β·N_tok + γ·N_tool + δ·N_file
Eq.2  π*     = argmin_π C(π)   s.t.   P(success | π, τ) ≥ 1 − ε
Eq.3  ACRR   = (C_act − C_min) / C_min
Eq.4  x₀     = f(q, E, M) = (d̂ difficulty, ŝ scope, r̂ risk, ĉ confidence)
```

Defaults (§4.5): `α=1.0/s, β=0.02/token, γ=0.5/call, δ=1.5/file`. δ is the
largest by design — "pulling an irrelevant file into context is the canonical
unit of redundancy" (§3.1) — and a full-file read also charges tokens ∝
length, so it is expensive on **three axes at once** (δ file, β tokens, γ the
call itself) (§4.5).

**Eq. 2 is a constrained optimisation.** The `s.t.` clause is not decoration:
it is what stops "cheapest" from meaning "does nothing". `ACRR` is defined
**only over successful runs** — "a cheap failure is not an efficiency" (§3.3).

**The normalizer is the point of ACRR (§3.3).** The paper explicitly disclaims
novelty of the ratio: "We make no claim that the ratio itself is novel — it is
a deliberately simple, task-normalized diagnostic". Its value "lies in the
normalizer: because the oracle makes `C_min` exact and *per task*, redundancy
becomes comparable across tasks of very different absolute cost" — which is
what licenses the paper's signature claim (§7.2). Consequence for us: an ACRR
computed against a **self-referential** floor (our current state, gap 15) does
not inherit that license; comparisons across tasks of different sizes are
unsafe until `C_min` is measured.

### 1.3 Algorithm 1 — the control loop, and the trigger question

```
input: task τ, estimator f, max expansions K
1  x₀ ← f(q, E, M)                     ▷ Estimate: ≤ 1 cheap probe
2  ℓ  ← d̂ ;  H ← cached search hits
3  ok ← Execute(τ, ℓ, x₀, H)
4  k  ← 0
5  while ¬ok and ℓ < 3 and k < K:
6      ℓ ← ℓ+1 ;  k ← k+1              ▷ Expand ONE scope level
7      ok ← Execute(τ, ℓ, x₀, H)       ▷ H is REUSED, not rediscovered
return ok
```

Three properties the paper leans on: expansion is **monotone** in scope,
**bounded** by `K`, and therefore "degrades gracefully toward the exhaustive
strategy in the worst case while remaining lean in the common case" (§4.4).

**The trigger discrepancy (matters for S10a/S10c).** The paper states the
expansion trigger two ways:

- **Algorithm 1 + §4.4:** `while ¬ok …` — expansion fires on **verification
  failure** only.
- **§4.1 prose + Figure 1 caption:** "expands scope only when verification
  fails **or confidence is low**" / "Successful verification exits
  immediately." §4.2 adds that a lowered `ĉ` flags "a candidate for
  expansion".

Resolution adopted here: **Algorithm 1 is the authoritative control flow; low
`ĉ` does not itself fire expansion — it arms it.** A conflict-flagged task is
a candidate that Expand is primed to rescue; failure (or, in our adaptation,
counter-evidence) is what fires. The paper never shows `ĉ` entering the loop
condition, and no result depends on it firing pre-hoc.

Two further mechanics the loop depends on:

- **`x₀` is computed once and never re-estimated.** Across expansions the
  loop passes the *original* `x₀`; `ℓ` is the only mutated variable, and `ℋ`
  is carried. Re-estimation mid-run is *our* extension (S10a), not the
  paper's loop.
- **Two independent bounds:** the level cap (`ℓ < 3`) and the budget
  (`k < K`). From `ℓ=1` at most **2** expansions are possible, so `K=2` makes
  `K` non-binding; `K>2` is inert under the level cap; `K=1` would leave the
  paper's deceptive-L3 class (needs 1→3) under-recovered. The paper itself
  never states a numeric `K`.

### 1.4 Stage 1 — Estimate (§4.2)

Maps `q` (plus at most one probe of `E`; Eq. 4 also admits `M`, uninstantiated
— see §1.1) to `x₀`. It "combines lexical cues with an optional structural
probe." Three rules:

1. explicit file references **and quoted literals** with localized verbs
   ("replace … in index.html") → single-file edit. Quoted literals are half
   of this fast path: §7.6's held-out wording deliberately removes the
   "file-plus-quoted-literal fast path", and R1 must do the same;
2. broad-scope cues ("refactor across the codebase", "every call site",
   "re-export") → repository-level;
3. otherwise **one** search for the salient token; count occurrences to
   separate local from cross-file.

> "When wording and structure **conflict** — localized phrasing but multiple
> occurrences — **confidence ĉ is lowered**, flagging a candidate for
> expansion. Crucially, the estimator is deliberately **imperfect** … The
> Expand stage exists precisely to recover these cases, so the estimator can
> be cheap and optimistic rather than exhaustive."

**Measured calibration (Fig. 4b).** The transparent estimator is exact on
Levels 1–2 and on *obvious* Level-3 tasks, and under-scopes **exactly the 18
deceptive Level-3 tasks — predicting difficulty 2 rather than 3** ("the
estimator stops one dependency trace short"). Mis-estimation is not noise; it
is a structured, characterizable failure mode concentrated in one task class.
That is what makes optimism safe *here* — and it is the property our R2 class
must reproduce in our tree.

> **→ For S10.** R1 (held-out wording) must strip **both** fast paths —
> keyword vocabulary *and* quoted-literal/file-reference cues — or it is a
> weaker test than §7.6's. R2 should assert not just "estimator under-scopes"
> but a *stable mis-scope delta* (e.g. predicts one level short) so the
> trigger logic can be tuned against a characterized failure, not a random one.

### 1.5 Stage 2 — Execute (§4.3)

Scope-sized execution. The path **never gathers context beyond what the
current level requires**:

| ℓ | Behaviour |
|---|---|
| 1 | localize the single site, edit it |
| 2 | reuse cached search hits `H`, read them, edit direct sites |
| 3 | additionally follow imports (`dependency_trace`) and inspect importer files to reach **indirect** sites a grep cannot see |

> "**Verification effort scales with risk**: low-risk edits are checked
> locally, whereas high-risk repository changes run the heavier acceptance
> check."

`r̂` is consumed here and only here: risk selects the *verifier*, never the
route. (`d̂` selects the route via `ℓ ← d̂`; `ĉ` arms expansion; `ŝ` is
consumed nowhere — §1.1 map.) Note `H` is consumed *inside Execute* at ℓ≥2,
not only across expansions.

**Instantiation fact relevant to gap 10:** in LLM-Case (§7.7) the entire
policy — including scope-sized Execute — is "**nothing but system prompts**"
over six shared tools. The level-sized budget ("at level 1, localize and
edit; do not read beyond") is a *prompt-level norm* the model follows, not a
withheld toolset. Scope-sized Execute therefore has an advisory
implementation that requires no second gate and no tool withholding —
consistent with Q21. See the gap-10 note in §3.8.

### 1.6 Stage 3 — Expand (§4.4)

On the trigger (§1.3: failure fires; low `ĉ` arms): do **not** restart, do
**not** jump to reading everything. Increment `ℓ` by one, reuse `H`, replan —
re-running Execute with the **same `x₀`**. "Cost grows only in response to
**evidence** that the task is harder than estimated." Bounded by `K` and
monotone; on exhaustion the loop returns the last `ok` — the graceful-
degradation endpoint (our `expansion_exhausted`).

### 1.7 What the evidence says each stage buys (§7.4 ablation)

| Variant | Success | C | ACRR | L3 cost |
|---|---|---|---|---|
| E3 full | 100.0% | 18.55 | 0.55 | 34.59 |
| **− Expand** | **85.1%** | 14.88 | 0.47 | 23.48 |
| − Estimate | 100.0% | 22.21 | 0.71 | 47.01 |

**The asymmetry is the single most important fact in the paper for us.**
Removing Estimate raises **scalar cost +20% overall and +36% on Level 3**
(47.0 vs 34.6), success unchanged. Removing Expand loses 15 points of success
— all 18 deceptive L3 tasks — and its mean cost is *lower*: but every mean
and ACRR is over **successful runs only** (Table 7.1 convention), so
−Expand's 14.88 averages over the 103 surviving tasks *after dropping the 18
most expensive ones*. It is cheap **because it fails** — read that way, the
ablation is stronger, not weaker, than the raw table suggests.

> "estimation reduces cost, and expansion protects reliability."

Mechanism (Fig. 4b): the estimator under-scopes exactly the 18 deceptive
tasks (`d̂=2` vs true 3); Expand recovers exactly those. Estimation and
expansion are tuned as a *pair* — the optimism is safe only because the
mis-scope is bounded and the recovery is verified.

### 1.8 Benchmark, baselines, and headline numbers (§5–§7.3)

Every headline number in this paper is relative to a baseline set; this
section pins the set down before any reduction is quoted.

**Editability mechanism (§5.1) — the mechanical definition of "deceptive".**
A **direct** site (location contains the searched token literally) becomes
editable once its file is observed via search or read; an **indirect** site
(alias/re-export the token does not match) becomes editable **only after its
file is fully inspected, discovered via dependency tracing**. Capability is
held identical across policies — yet "the Fixed ReAct policy — given
*identical* edit capability — fails a third of all tasks because its fixed
trajectory never reaches those sites". Holding capability fixed does not make
success trivial: trajectory *shape* is what fails.

**Task tiers (§5.2).** 121 tasks, procedurally generated from one archetype
per tier (L3 split obvious/deceptive), randomized identifiers, **randomized
distractor files** for realistic surface area:

| Level | # | Direct | Ind. | Oracle actions |
|---|---|---|---|---|
| 1 local | 41 | 1 | 0 | `locate, edit, verify` |
| 2 cross-file | 40 | 2 | 0 | `search, edit×2, verify` |
| 3 repo-level | 40 (18 **deceptive**) | 2 | 1 | `search, trace, edit×3, test` |

Every task ships an oracle realizing `π*`, defining `C_min` exactly.
Metrics (§5.3): success, the four axes, scalar `C`, ACRR; aggregates are
means over all 121 tasks; ACRR averaged over successful runs only.

**Baselines (§6.1) — all four, because every headline number is relative:**

| Policy | What it is | Why it exists |
|---|---|---|
| Max-Context-First (MCF) | walks the tree, fully reads every file, reasons about architecture, edits, heavy check | an **explicit upper-bound stress model** of "gather everything, then act" — "we do not claim that any deployed frontier agent literally reads an entire repository" |
| Fixed ReAct | fixed search→read-hits→edit→test, no scope adaptation | the lean-but-blind failure mode (66.9%) |
| Adaptive Retrieval (**AR**) | searches the salient token, fully reads retrieved files, **always** traces imports on cross-file tasks (so indirect sites are always reached), edits, heavy check | the **strong, non-straw-man** adaptive baseline; solves everything; "what it lacks is an up-front difficulty estimate" |
| Oracle | executes `π*` | defines `C_min` |

**Main table (§7.1), means over 121 tasks:**

| Policy | Succ.% | Lat. | Tok. | Tool | File | C | ACRR |
|---|---|---|---|---|---|---|---|
| MCF | 100.0 | 13.80 | 4421 | 15.9 | 8.46 | 122.85 | 12.90 |
| Fixed ReAct | 66.9 | 6.26 | 404 | 5.7 | 0.00 | 17.16 | 1.29 |
| AR | 100.0 | 7.56 | 410 | 6.6 | 1.99 | 22.08 | 1.21 |
| **E3** | **100.0** | **5.71** | **403** | 7.6 | **0.66** | **18.55** | **0.55** |
| Oracle | 100.0 | — | — | — | — | 11.74 | 0.00 |

Vs MCF: −58.6% latency, −90.9% tokens, −52.3% tool calls, −92.2% files,
−84.9% cost. Vs **AR** at equal success: −16.0% cost, −66.8% files — while
spending **~14% more tool calls** (7.6 vs 6.6): E3 pays small probes and
occasional expansions to avoid big reads. That trade is the design.

**The signature result (§7.2): redundancy is worst on the simplest tasks.**
MCF's ACRR: **22.1 (L1) → 11.0 (L2) → 5.4 (L3)** — "partly mechanical"
(constant cost over a growing `C_min`), presented as a descriptive signature,
not a scaling law. E3 stays low across tiers (0.64 / 0.26 / 0.73). **Honest
caveat the paper states: on Level 3, AR (ACRR 0.42) is leaner than E3
(0.73)** — E3 pays extra expansions on deceptive tasks it under-scopes; AR
pays tracing up front. E3's advantage concentrates exactly where the thesis
says: **45% (L1) and 43% (L2) cheaper than AR**; on genuinely hard tasks a
thorough adaptive agent is competitive. Motivating case (§7.3): `C_min=6.0`;
E3 0 files / 248 tok / C 9.51 / ACRR 0.59 vs MCF 7 files / 1844 tok / 66.78 /
10.13 (−85.8%; −51% vs AR's 19.60).

> **→ For S10.** (1) RK-L's mitigation cites §7.4; §7.2 is the counterweight
> — over-provisioning at the top level is what AR does, and it *wins* on L3.
> Our Expand must escalate **one level at a time** precisely because jumping
> to level-3-by-default is AR, and AR is 19% more expensive overall. (2) R2's
> oracle-action template is the §5.2 table: a deceptive task's minimum
> trajectory is `search, trace, edit×3, test` — our R2 tasks should pin the
> equivalent (e.g. `fs_search, fs_reach, 3 edits, pytest`). (3) The
> ~14%-more-tool-calls trade maps to our advisory observations: expect S10a
> to *add* cheap calls while removing expensive reads — measure both axes or
> the win will look like a loss.

### 1.9 Robustness results that constrain the design

**§7.6 held-out wording.** Every instruction paraphrased into vocabulary
*disjoint* from the estimator's keyword lists **and with the file-plus-
quoted-literal fast path removed**. Estimator exact accuracy
85.1% → 66.9%; under-scoping 14.9% → **33.1%** (it now under-scopes *all* 40
L3 tasks). Yet **success stays 100.0%** and cost rises only 8.7%
(18.55 → 20.17; still 84% below MCF and 9% below AR).

> "the headline efficiency is a property of the Estimate–Expand
> **architecture** … not of the estimator's keywords matching the benchmark.
> A better estimator would shift cost down by expanding less often; a worse
> one (as here) shifts it up; **neither changes the success guarantee that
> Expand provides**."

**§7.5 weight sensitivity.** 4000 draws over hostile ranges (α∈[0.5,2],
β∈[0,0.1], γ∈[0,2], δ∈[0,3]) — a draw may zero the token or file axis
entirely. Method matters: because `C` is **linear in the four axes**, a
policy's cost under any weight vector is that vector dotted with its mean
per-axis usage, so the sweep needs no re-simulation. Results: E3 cheapest
fully-successful policy in **99.8%** of draws; vs MCF cheaper in **100%**
(median reduction 86.6%, 5th percentile 74.0%); vs AR cheaper in **99.8%**
(median 9.3%, interdecile 3.5–21.2%); at **δ=0** — the weighting most hostile
to E3 — still cheaper than AR in 96.7% and than MCF in 100%. Ordering robust;
exact weights not load-bearing.

**§7.7 LLM-Case — the full picture, including the parts that sting.**
Design: the three policies are *only system prompts* (`mcf-thorough`, `react`,
`e3`) over 6 shared tools (`list_dir, grep, read_file, edit_file, run_tests,
finish`); real vendored `toml 0.10.2` (7 modules, 10 files); 5 tasks
(`L1_version, L1_spec, L2_commentdecoder, L2_arrayseparator,
L3_decoderbase` — the L3 rename sounds local but must reach `toml/ordered.py`,
which subclasses the base class); success = real pytest against hidden
per-task graders; `C_min` **measured** by running each gold patch through the
same instrumented tools. Self-consistency: every gold patch passes its grader
**and the pristine repo fails every grader**; the oracle inspects exactly the
1/2/3 files each patch touches. Measured floors: `L1_version` 7.7,
`L1_spec` 7.8, `L2_commentdecoder` 205.5, `L2_arrayseparator` 60.2,
`L3_decoderbase` 209.8 — **file size dominates, not count** (`decoder.py`
≈10k tokens vs ~210 for L1 edits). Wall-clock deliberately excluded from
`C_min` to keep it deterministic.

Results (gpt-4o, **3 runs per cell — a case study, not a powered
benchmark**): gpt-4o reads only **1–4 files** even under "read everything" —
the simulator's gross over-reading does not reproduce in a frontier model.
Means: tokens 98.6k (thorough) / 83.9k (ReAct) / **80.5k (E3)**; files
2.0/2.0/**1.7**; latency 192.3s/165.9s/**157.6s**. E3: −18% tokens, −18%
latency vs thorough; −4% tokens, −5% latency vs ReAct. **Success: thorough
80%, ReAct 100%, E3 93% — and E3's single failure was an HTTP 429 rate
limit, not a wrong edit.** The edge is "small and non-uniform": L1 edits are
within noise across policies (the estimate step is **cost-neutral**, not a
win); E3's big win is token-heavy `L2_commentdecoder` (76k vs 100k/116k);
E3 is **priciest** on `L2_arrayseparator` (46.0k vs ~34–35k); on L3 **ReAct
is cheapest** (260k vs E3's 271k). The operationally critical finding for
live-budget work: **the heaviest-reading trajectories are the ones that
fail** — thorough's L3 runs took 575–863s and *none* passed (step-budget
exhaustion, a wrong edit, a 429 at 315k cumulative tokens) vs ~450s for E3's
successful runs; and "the identity of the failing policy moves across runs".
The real-model claim is therefore not "E3 always cheaper" but, in the paper's
words, "**the leanest policy overall, and one that does not spend itself into
failure as hidden coupling grows**".

> **→ For S10.** (1) R1 must mirror §7.6 exactly: disjoint vocabulary **plus
> removed fast paths**, and must assert the *architecture* property (every
> newly under-scoped task is recovered by the trigger), not estimator
> accuracy. (2) S8's weight-sensitivity replication should use the paper's
> linearity trick (dot mean-axis-usage vectors) — it is exact and free.
> (3) The 429/step-budget failure mode belongs in the S9 live-sheet risk
> list: over-reading doesn't just cost money, it converts into *failed runs*
> under provider limits — this is the strongest live-budget argument for
> shipping S10 before executing S9 (§3.0).

### 1.9a `H`-reuse is a correctness property, not a token optimisation

Rev 1 wrote gap 14 off as "pure token optimisation; no correctness value."
**That was wrong**, and it is worth stating plainly because the error points at
the one way S10a could be built to the letter and still miss the point.

§4.4: on the trigger E3 "does not restart from scratch and it does not jump to
reading everything. It increases the scope level by one, **reusing what it
already learned** (the remembered search hits), and replans." The paper calls
the result **progressive context expansion** and names it "the opposite of
maximum-context-first."

Reuse is therefore what makes expansion *progressive* rather than a re-search.
An Expand stage that re-discovers context at every level is not a cheap
approximation of E3 — each level becomes a fresh audit, which is the
maximum-context-first failure mode in miniature, rebuilt inside the very
mechanism meant to avoid it. The cost curve would grow super-linearly in `ℓ`
exactly when the task is hardest.

> **→ For S10.** The full cached-`H` feature stays deferred (gap 14, §3.8) to
> keep the slice small — but the *guarantee* it protects is cheap to keep now:
> `ExpansionState` already carries `observed_read_paths`, so S10a must thread
> it through and never re-read a path a lower level already read. That is a
> one-line exit criterion (§3.7), and it converts a deferral into a pinned
> invariant. Ship the invariant now, the cache later.

### 1.10 The framing the paper gives the system (§2.3, §8, §9, §10)

**Power-flow analogy (§8) — where `x₀` comes from.** The paper solves a
three-bus AC power flow by Newton–Raphson and measures convergence vs
initial-point error: flat and DC warm starts converge in **3 iterations with
100% reliability**; reliability falls to **35% at error 0.6** and to near
zero beyond **~2.4**, where the solver diverges. The basin of attraction is
compact; cheap structured starts sit deep inside it. The parallel is
"structural rather than exact" and offered "as an engineering intuition that
motivated E3's design, not as evidence for its agent-side results". The
broader frame is **engineering-grounded AI (EGAI)**: anchor reasoning in the
procedural reality of the task rather than unconstrained search.

Design lesson for us: a *bounded* expansion budget (`K`) exists because, in
the analogy, a far-off start doesn't merely cost more — it diverges. Our
`expansion_exhausted` endpoint is the agent-side analogue of leaving the
basin; the ADR should say that escalating forever is not a fallback, it is a
different (AR-like) policy.

**Routing contrast (§2.3, Table 2.3) — S7∘S10 composition.** The paper
distinguishes routing (choose from a fixed menu before acting; **recovery if
misjudged: one-shot choice — none**) from execution-scope estimation
(structured scope predicted before acting; **recovery: verified progressive
expansion**). E3 is "compatible with, and complementary to" effort routers;
"a natural integration uses an effort router **inside** each E3 stage" (§9).

> **→ For S10.** This is the architectural statement of what our own gap
> analysis discovered empirically: S7 (the gate) is a *router* — per
> Table 2.3 it has no recovery if misjudged; S10a is what supplies the
> missing recovery column. They are different layers and must not be merged:
> the gate decides *whether to escalate to workflow*; Expand decides *how far
> the run goes once moving*. See the traceability row in Part 4.

**Future work the paper names (§10):** calibrated/learned estimators behind
the same interface; more hidden-complexity mechanisms in the benchmark;
per-step effort routers inside E3 stages; scaling LLM-Case to more models and
SWE-bench-style tasks. (Ours aligns: S10d is the first step toward a
calibrated estimator; our R2 class extends the mechanism set.)

### 1.11 Stated limits (§9) — do not oversell

- No LLM is invoked in the main experiments; numbers are "properties of a
  cost model", not of any deployed agent. MCF is an explicit **upper-bound
  stress model**, not a claim about real agents (§6.1).
- The estimator is "a transparent lexical rule"; a learned one "may
  generalize better and mis-estimate differently".
- MSE-Bench captures **one** hidden-complexity mechanism (aliases/re-exports),
  not dynamic dispatch, configuration coupling, or runtime reflection.
- §7.2 monotonicity is "partly mechanical" — a descriptive signature, not a
  scaling law.
- The simulator cannot show how a real model's *edit accuracy* interacts with
  scope: "a model might make errors that only broader context would prevent,
  raising the optimal operating point and shifting the estimate/expand
  balance". A live LLM's optimism may need to be *less* optimistic than the
  simulator's — S10a's triggers should be watched for exactly this.
- LLM-Case is **3 runs per cell on one model** under a low provider rate
  limit — a case study; the aggregate edge is "small and non-uniform". Do not
  quote −18% as a guarantee.
- ACRR's cross-task comparability rests on an exact per-task oracle (§3.3);
  with a self-referential floor (gap 15), our ACRR aggregates are
  provisional.

---

## Part 2 — Gap analysis: E3 vs. First-Agent as shipped

Verified against the code at `d924879`, not from memory.

| # | E3 mechanism | § | Our status | Value |
|---|---|---|---|---|
| 1 | Eq. 1, four axes | 3.1 | **SHIPPED** S8 `compute_cost` | — |
| 2 | Eq. 3 ACRR | 3.3 | **SHIPPED** S8 `compute_acrr` | — |
| 3 | Four axes stored separately | 5.3 | **SHIPPED** (`duration_ms`, `output_tokens`, `tool_calls_total`, `files_read/changed`) | — |
| 4 | ACRR successful-runs-only at display | 3.3 | **SHIPPED** (Q22) | — |
| 5 | Weight-sensitivity replication | 7.5 | **SHIPPED** S8 (4000 draws, 4000/4000 — name which statistic this replicates: the paper reports 99.8% for "cheapest fully-successful" and 100% only vs MCF; ours is over our own policy set) | — |
| 6 | `x₀ = (d̂, ŝ, r̂, ĉ)` | 3.4 | **PARTIAL** — `risk` is a dead alias for difficulty; never consumed (the paper's own `ŝ` is likewise dead — the fix is to wire `r̂` to the verifier, not to invent consumers) | MED |
| 7 | Eq. 2 `s.t. P(success) ≥ 1−ε` | 3.2 | **MISSING** — no ε, no measured success rate per route | HIGH |
| 8 | Estimate: lexical **+ one probe** | 4.2 | **PARTIAL** — `f(q)` only; the `E` term is absent | HIGH |
| 9 | Estimate: conflict **lowers ĉ** | 4.2 | **MISSING** | HIGH |
| 10 | Execute: scope-sized path | 4.3 | **MISSING** (a prompt-level instantiation exists — see the §3.8 note) | MED |
| 11 | Execute: **verification scales with risk** | 4.3 | **MISSING** | HIGH |
| 12 | Expand: +1 level on evidence | 4.4 | **MISSING** — one-shot advisory nudge only | **HIGHEST** |
| 13 | Expand: bounded by `K`, monotone | 4.4 | **MISSING** | MED |
| 14 | Expand: reuse cached hits `H` | 4.4 | **MISSING** — cache deferred, but the no-re-read *invariant* ships in S10a (§1.9a) | LOW |
| 15 | `C_min` **measured** via gold patch | 7.7 | **MISSING** — self-referential floor; without a measured floor, cross-task ACRR comparisons are provisional (§1.2) | HIGH |
| 16 | Held-out wording robustness test | 7.6 | **MISSING** | HIGH |
| 17 | Deceptive-variant task class | 5.2 | **MISSING** | HIGH |

**The pattern:** every *measurement-side* mechanism is shipped; every
*control-side* mechanism is missing. We built the instrument panel and no
steering.

### 2.1 Measured evidence that this matters here

Our own §7.6 replication, run against `estimate_scope`:

| Keyword wording | verdict | Paraphrase | verdict |
|---|---|---|---|
| "refactor the protocol across the codebase" | `workflow_linear` | "give the message format a new name project-wide" | `chat_direct` |
| "implement a new command" | `chat_planned` | "add a way for users to run this from the terminal" | `chat_direct` |
| "migrate the database schema" | `workflow_linear` | "move the stored data over to the new layout" | `chat_direct` |
| "fix typo in README.md" | `chat_direct` | "there's a spelling mistake in the readme" | `chat_direct` |

**3/4 flipped.** Same degradation the paper reports — but the paper survives it
because Expand recovers. We have no Expand, so degradation is uncorrected.
*(Note: this mini-replication paraphrases vocabulary only; §7.6 also removes
the file+quoted-literal fast path — R1 must do both.)*

The operator's real prompting style measured at `confidence = 0.3` on every
sample ("update the handoff", "find the doc about the handoff process",
"there's a backlog item about subagent containment"). The gate requires 0.8, so
**on the operator's actual usage the S7 gate never fires.**

Deceptive coupling is real in this repo: "fix the `-f` gap" sounds single-file
(`validators.py`) but a correct patch must also touch
`tests/test_sandbox_validators.py`, `tests/test_sandbox_bash_gate.py` and two
others that pin current behaviour. That is E3's deceptive L3 archetype, in our
own tree.

### 2.2 Tools: we already own the action set

| E3 action | Ours | Status |
|---|---|---|
| `search` | `fs_search` | present |
| `read_range` / `inspect_file` | `fs_read_file` | present |
| `dependency_trace` | **`fs_reach`** (symbol, `direction: up/down/both`, `depth`) | present |
| `edit` | `fs_edit_file`, `fs_write_file` | present |
| `verify` | `fs_run_bash` (pytest) | present |
| `list_dir` | `fs_search` / `fs_usage` | adequate |

No new tool is required for Execute or Expand.

---

## Part 3 — S10 specification

### 3.0 Scope decision

S10 implements gaps **6, 7, 8, 9, 11, 12, 13, 16, 17** — the control-side
stages plus the two robustness test classes. It **defers** gaps 10, 14, 15
(scope-sized Execute, cached `H`, measured `C_min`) with reasons in §3.8.

**Sequencing:** S10 lands **before** the S9 live sheet is executed. Rationale:
S9 exists to exercise routing on real runs; running it against a system whose
estimator flips on 3/4 paraphrases and whose gate never fires for this operator
would produce exactly the "mixed results" predicted, and would burn live budget
measuring a known-broken configuration. A second, paper-grounded rationale:
§7.7 shows over-reading converts into outright failed runs under provider rate
limits — 575–863s trajectories that pass nothing. Over-scoped runs don't just
cost budget; they consume it and fail.

### 3.1 Design principles (binding)

1. **Deterministic inputs only.** Tool-call *params* and *results* are
   structured facts. Model prose is not an input — routing must not vary with
   provider, temperature, or model version. (`scope_estimator.py:16`:
   "routing is deterministic, testable, auditable".)
2. **Advisory by default.** Q21 stands: inject and let the model decide. There
   is no rollback from a half-edited tree.
3. **Optimistic start.** E3 §4.2 — under-estimating is *correct* behaviour when
   Expand exists. S10 must not make the estimator conservative. The paper's
   own bound on this principle (§9): with a real model, edit accuracy may
   interact with scope and "raise the optimal operating point" — if S10a's
   triggers fire disproportionately on real runs, that is the signal to
   revisit the principle, not to suppress the triggers.
4. **Honest scope.** Runtime path-risk is a **nudge**, never containment.
   `fs_run_bash` (`sed -i`, `echo >`) bypasses all tool-param logic — RK-G,
   unchanged and not re-litigated.
5. **One cheap probe.** No call-graph walk in the estimator, no filesystem
   crawl, no LLM call. Keep the estimator's **signature** `f(q, E, M)` even
   while `M` is unused — §6.2's drop-in-LLM-estimator interface is the
   paper's stated evolution path.

### 3.2 S10a — Runtime scope re-estimation (the real Expand)

**Replaces:** the one-shot `_tripwire_fired` latch in `coder_loop.py:573`.

**New module:** `src/fa/inner_loop/expansion.py`

```python
SCOPE_LEVEL_MAX  = 3
DEFAULT_MAX_EXPANSIONS = 2          # E3's K

@dataclass(frozen=True)
class ExpansionState:
    level: int                       # current ℓ, starts at d̂
    expansions_used: int             # k
    observed_read_paths: frozenset[str]
    observed_write_paths: frozenset[str]

def next_scope_level(
    state: ExpansionState,
    *,
    files_read: int,
    files_changed: int,
    risk_tier: int,
    max_expansions: int,
) -> ExpansionDecision | None
```

Monotone (`level` only increases), bounded (`k < K`), and idempotent per turn.

**`difficulty → level` is an explicit mapping, not an assignment.** The paper
writes `ℓ ← d̂` (Algorithm 1 line 2), identifying a difficulty estimate with a
3-valued scope level by fiat (§1.1 note 4). S10a implements this as a named,
unit-tested `difficulty_to_level(difficulty) -> int` rather than an inline
assignment, so the conflation is a reviewable decision we can change when live
evidence says our difficulty scale and our scope levels are not the same thing.

**`H`-reuse invariant (§1.9a).** `next_scope_level` threads
`observed_read_paths` through every expansion, and a higher level must never
re-read a path a lower level already read. The cached-`H` *feature* is deferred
(gap 14); this *invariant* is not, because it is what makes expansion
progressive rather than a re-search.

*`K` semantics:* under the level cap `ℓ < 3`, `K=2` is non-binding — from
`ℓ=1` at most 2 expansions exist anyway; `K>2` is inert and `K=1`
under-recovers the deceptive class. The paper never states its own numeric
`K`. Keep `K` in the signature as the explicit knob; document that `K=2` is
the ceiling the level cap already imposes.

**Trigger.** E3 expands on *verification failure* (Algorithm 1); §4.1/Fig. 1
additionally name **low confidence** as an expansion condition — the paper's
own texts differ, and the resolution adopted in §1.3 is: *failure fires, low
ĉ arms*. We have no per-turn verifier (RN13, confirmed: no `run_tests` in the
turn loop). S10 uses an evidence proxy, and the ADR must say so plainly:

| Evidence | Level → | Rationale |
|---|---|---|
| `files_read > 10` or `files_changed > 3` | ℓ+1 | current S7 tripwire thresholds, retained |
| a read path in a **higher risk tier** than the estimate assumed | ℓ+1 | §3.3 — this is also the natural home of the paper's "low-confidence arms expansion": estimate/conflict state sets *readiness*, counter-evidence *fires* |
| a failed `fs_run_bash` whose command matches the verify pattern | ℓ+1 | closest available analogue to E3's real trigger |

Each firing emits **one** `scope_expansion` event and appends **one**
observation to `turn_context` naming the evidence and `invoke_workflow`. After
`K` expansions the loop stops escalating and records `expansion_exhausted`
— the graceful-degradation endpoint of §4.4.

**Why this is the highest-value item:** §7.4 says this stage is worth 15 points
of success, and §7.6 says it is what makes a weak estimator survivable. It is
also the operator's own requirement: the system must learn from turns 1–2
rather than from the prompt alone.

### 3.3 S10b — Path risk tier (the missing `E` probe, feeding `r̂`)

**Fills gaps 6, 8, 11.** `r̂` stops being a dead alias.

Tier table, **in `~/.fa/config.yaml`, not in code** (repo-specific policy the
operator must tune without a deploy):

```yaml
scope_risk_tiers:
  safe:   1     # worklogs/archive, worklogs/research, worklogs/implementation-plans,
                # worklogs/reviews, worklogs/pr-notes
  medium: 3     # knowledge/**, tests/**, scripts/**
  high:   5     # src/**, repo-root files (AGENTS.md, pyproject.toml, *.toml, *.cfg)
```

Measured distribution over 848 tracked files: safe 19.2%, medium ~55%,
high ~21%. (`tests/` is placed at medium deliberately: a test edit is
recoverable, a `src/` edit is not.)

**Combination rule — MAX, never average.** Recorded decision:

| task | lexical | path | avg | max |
|---|---|---|---|---|
| "fix typo in `validators.py`" | 1 | 5 | 3.0 → not gated | **5 → gated** |

Averaging lets a safe signal *cancel* a dangerous one; a one-line edit to the
force-push validator would score "medium" and pass. For a safety signal the
dangerous axis must dominate. The cost is over-escalating "refactor" on an
archive doc — the correct direction to be wrong.

**Edit-position rule (mandatory).** Only paths in *edit position* set the tier.
Paths after `verify|run|test|according to|described in|documented in` are
ignored. This is not optional polish: the S9 sheet was itself mis-scored when
`pytest tests/test_doc_links.py` pushed confidence 0.3 → 0.8. Named test class,
below.

**What `r̂` then drives (§4.3):** verification effort, not the route.

| `r̂` | Verification posture |
|---|---|
| low | no added pressure |
| medium | observation: name the changed files, suggest a targeted test |
| high | observation: name the risk tier and the specific verification command |

### 3.4 S10c — Conflict lowers confidence (§4.2)

When the lexical axis and the path axis disagree, **reduce ĉ** rather than
picking a winner:

| lexical | path | ĉ | Effect |
|---|---|---|---|
| agree | agree | unchanged | gate may fire (≥0.8) |
| disagree | disagree | **× 0.6** | drops below 0.8 → gate withdraws, run proceeds under Expand |

This uses machinery already shipped — the gate's 0.8 threshold — and is
faithful to §4.2 verbatim. Disagreement stops forcing a guess; it hands the
case to the stage designed for it.

*Adaptation note:* in the paper, lowered ĉ "flags a candidate for expansion"
— it arms the recovery stage. Our mapping routes the effect through the S7
gate (withdrawal) instead, because the gate is the only consumer of ĉ today.
Same spirit — hand the case to Expand — different wire. The ADR must record
this as an adaptation; S10a's trigger table (row 2) is where the "armed"
state becomes observable at runtime.

> **SUPERSEDED 2026-08-29 (S10.9 / GAP-H9).** The ĉ×0.6 conflict penalty
> above was **never implemented and will not be**. S10 shipped the two-layer
> design instead (ADR-16 addendum §A): the lexical estimator is deliberately
> weak, and wording-vs-structure disagreement is resolved by the *runtime
> evidence engine* (`inner_loop/expansion.py` + `path_risk.py`), which arms
> and escalates on observed reads/writes regardless of the estimate. The
> completion criterion "disagreement pulls ĉ below the gate threshold (exact
> float)" (§Completion, row 4.2) is void; its intent — disagreement hands the
> case to Expand — is carried by the `read_high_arm` / `high_tier_write`
> triggers, pinned by the R1/R2 suites. Rationale for the pivot: adjusting a
> lexical confidence number cannot express *positional* evidence, and the
> gate (auto-tool-withholding) ships OFF (Q25), leaving the estimate-time
> penalty with no consumer.

### 3.5 S10d — Eq. 2's reliability constraint, measured

`fa stats --calibration` already groups realized ACRR by `recommended_mode` and
already filters to successful runs. Add, per mode:

```
runs_total, runs_succeeded, success_rate, acrr_mean/min/max
```

`success_rate` is the empirical `P(success | mode)` — Eq. 2's missing term,
measured rather than assumed. It is the only mechanism that would ever reveal
the gate making runs *worse*, and it is the operator's Q3 answer (no labelled
set; calibration supplies the evidence).

**Kill-check:** with a mode whose runs all fail, `success_rate` must read 0.0
and must not be silently omitted from the table.

**Open design point — no consumer yet.** As specified, S10d builds an
instrument with no actuator: nothing consumes `success_rate`, and Eq. 2 needs
both a measured `P(success)` **and** an `ε`. Minimal consumer to consider
(operator decision, not assumed here): `fa stats --calibration` flags any
mode with `success_rate < 1−ε_default` (suggest `ε=0.05`; the paper leaves ε
free) so a demonstrably failing mode stops being recommended; full gating
consequences deferred until there are enough runs per mode to be meaningful.

### 3.6 S10e — The two robustness test classes

**Class R1 — held-out wording (§7.6).** ≥12 task pairs: keyword wording vs a
paraphrase whose vocabulary is disjoint from `_KEYWORD_PATTERNS` **and with
any file-reference/quoted-literal fast-path cues removed** (§7.6 does both).
Assert the *architecture* survives, not the estimator:

- record estimator accuracy on both sets (expected to drop — that is the point);
- assert that for every paraphrase that under-scopes, the Expand trigger fires
  given the same simulated evidence.

This encodes the paper's actual claim: a worse estimator shifts cost, never the
success guarantee.

**Class R2 — deceptive variants (§5.2).** ≥6 tasks with localized wording and
real hidden coupling in *this* repo, e.g. the `-f` force-push fix
(`validators.py` + 4 test files). Assert the estimator under-scopes (expected)
**and** that Expand escalates once the read set reveals the coupling. Also,
per Fig. 4b, assert a **stable mis-scope delta** — predicts one level short,
consistently — not merely "under-scopes"; and pin each R2 task's minimum
trajectory in the shape of §5.2's oracle column, e.g.
`fs_search → fs_reach → edit×N → pytest`.

**Class R3 — edit-position discipline.** The false-escalation guard:
`"Fix links in worklogs/archive/. Verify with pytest tests/test_doc_links.py"`
must score tier 1, not 3.

### 3.7 Exit criteria

- [ ] `next_scope_level` is monotone: level never decreases (property test)
- [ ] bounded: never exceeds `K`; `expansion_exhausted` recorded at the bound
- [ ] at most one `scope_expansion` event per turn
- [ ] `difficulty_to_level` is a named, unit-tested function (not an inline `ℓ ← d̂`)
- [ ] expansion never re-reads a path already in `observed_read_paths` — pins the
      `H`-reuse guarantee (§1.9a) while full cached-`H` stays deferred (gap 14)
- [ ] risk tier read from `config.yaml`; absent file → documented defaults + warning
- [ ] MAX combination proven: lexical-1 + path-5 ⇒ high (not 3)
- [ ] edit-position rule proven by R3
- [ ] conflict lowers ĉ below the gate threshold (exact float)
- [ ] `success_rate` present per mode, 0.0 when all runs failed
- [ ] R1 recorded with both accuracy numbers, in the paper's framing
- [ ] R2: estimator under-scopes AND Expand escalates
- [ ] no new full-suite failures against 3484p/7f
- [ ] `ruff`, bare `mypy`, `pyrefly`, 4 contract scripts green
- [ ] hand-applied mutation on `expansion.py` + the tier resolver, 0 survivors
- [ ] *(proposed)* `--calibration` surfaces at least one consumer decision
      or explicitly prints "no modes below ε-threshold"

### 3.8 Explicitly deferred, with reasons

| Gap | Why deferred |
|---|---|
| 10 — scope-sized Execute | Requires withholding tools *by level*, i.e. a second gate. Q21 (advisory) and RK-G (evadable) both argue against more hard mechanism before we have live evidence. Revisit after S9 data. *Caveat — this premise overstates the requirement:* §7.7's LLM-Case instantiates scope-sized Execute as a **system prompt only**. A per-level advisory budget ("level 1: localize and edit; do not read beyond the located file") needs no gate and no withholding, and is Q21-compatible. If the deferral stands, record that the prompt-level variant was considered and why it is still deferred; otherwise pull a one-line advisory into S10a's observation text. |
| 14 — cached hits `H` | Correctness-neutral **only if** expansion never re-reads what a lower level already read. `H`-reuse is what makes expansion *progressive* rather than a re-search (§4.4, §1.9a); re-discovery at every level would rebuild the maximum-context-first failure mode inside Expand itself. The *invariant* therefore ships in S10a (`observed_read_paths`, pinned by an exit criterion); only the *cache* is deferred, to keep the slice small. LOW as scoped. |
| 15 — measured `C_min` | Needs a gold-patch corpus (§7.7's oracle). Real work, own slice. Until then the self-referential caveat stands verbatim in ADR-16 — and, per §1.2/§3.3, cross-task ACRR comparisons stay provisional until it lands. |

### 3.9 Risks

| RK | Risk | Mitigation |
|---|---|---|
| RK-I | Expand nags on legitimately large tasks | Bounded by `K=2`; advisory; silent when the estimate already said `workflow_linear` |
| RK-J | Tier table drifts from repo layout | Config-driven; R3 pins behaviour; unknown prefixes default to **medium**, not high |
| RK-K | Proxy trigger ≠ E3's verification trigger | Stated plainly in ADR-16 as an adaptation; revisit if a per-turn verifier lands |
| RK-L | MAX over-escalates | Accepted and measured; §7.4 shows over-provisioning costs tokens while under-provisioning costs success. Counterweight (§7.2): on genuinely hard (L3) tasks the always-thorough AR baseline is *leaner* than E3 (ACRR 0.42 vs 0.73) — one-level-at-a-time escalation is what keeps us off AR's cost curve |
| RK-G | Gate evadable via `fs_run_bash` | **Unchanged, not re-litigated.** Nudge, not containment. |

### 3.10 Open questions for the operator

| Q# | Question | Options |
|---|---|---|
| Q24 | `K` (max expansions) | **2** (proposed) / 1 / 3. Under the `ℓ<3` cap: 3 ≡ unbounded (inert knob); 1 provably under-recovers the paper's deceptive class (needs 1→3). K=2 is the only value that is both meaningful and sufficient. |
| Q25 | Should a high risk tier ever *withhold* write tools mid-run, or only observe? | observe-only (proposed, consistent with Q21) / withhold at tier 5. The paper supports observe-only as the faithful reading: `r̂` modulates verification effort only (§4.3), no E3 policy ever withholds actions, and LLM-Case is prompt-only — withholding would exceed the paper's design, not implement it. |
| Q26 | `tests/**` tier | medium (proposed) / high |
| Q27 | Ship S10 before executing the S9 live sheet? | yes (proposed) / no. §7.7's failed 575–863s over-reading runs under provider rate limits strengthen "yes". |

---

## Part 4 — Traceability

| E3 § | Mechanism | S10 item |
|---|---|---|
| 3.2 Eq. 2 | reliability constraint | S10d |
| 3.3 | ACRR normalizer needs a per-task oracle | gap-15 deferral caveat (§3.8, §1.2) |
| 3.4 Eq. 4 | `r̂` populated and consumed | S10b |
| 3.4 Eq. 4 | `M` (prior experience) socket | Principle 5 signature note; future `M` = calibration history |
| 4.2 | one cheap probe | S10b |
| 4.2 | conflict lowers ĉ | ~~S10c~~ **SUPERSEDED** (S10.9): evidence engine, §3.4 disposition |
| 4.2 | quoted-literal fast path | R1 fast-path removal |
| 4.3 | verification scales with risk | S10b |
| 4.4 | progressive expansion, `K`, monotone | S10a |
| 4.4 | `H`-reuse = progressive, not re-search | S10a `observed_read_paths` invariant (§1.9a); cache deferred (gap 14) |
| 4.1 Alg. 1 line 2 | `ℓ ← d̂` identification | S10a `difficulty_to_level` (explicit, tested) |
| 3.4 Eq. 4 | `ŝ` unoperationalized *by the paper* | do not invest; §1.1 note 4 |
| 4.1 + Fig. 1 | low-confidence trigger ("failure fires, low ĉ arms") | S10a trigger table row 2 |
| 5.1 | direct/indirect editability mechanism | R2 task construction |
| 5.2 | deceptive variants + oracle action shapes | R2 |
| 6.1/7.1 | baselines (MCF stress model; AR strong adaptive) | §1.8 context; RK-L |
| 6.2 | drop-in LLM-estimator interface | Principle 5 |
| 7.4 | ablation ⇒ Expand is the priority | S10a rationale |
| 7.5 | linearity trick for weight sweeps | S8 replication method note |
| 7.6 | held-out wording | R1 |
| 7.7 | measured-oracle method | gap-15 future slice |
| 7.7 | over-reading ⇒ rate-limit/step-budget failures | Q27 / S9 sequencing |
| 2.3 Table 2.3 / 9 | routing has no recovery; scope estimation supplies it; routers compose *inside* stages | S7∘S10 layering |
| 8 | initial operating point / basin of attraction | §1.10 framing; `expansion_exhausted` semantics |
