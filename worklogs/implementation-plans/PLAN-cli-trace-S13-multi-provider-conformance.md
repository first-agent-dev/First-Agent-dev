# PLAN: S13 — multi-provider conformance (open-scope)

**Status:** DRAFT — awaiting review
**Author:** agent, 2026-08-03 (v2, restructured after operator scope decision)
**Parent:** `cli-trace-substrate-rebaseline-2026-07-25.md`
**Closes:** **I-50 (P1)**, **I-52 (P2)**, **I-51 (P2)**. Unblocks S11.7 / Q35b.
**Ceremony:** lean
**Supersedes:** `PLAN-cli-trace-S13-message-normalization.md` (v1, narrow scope)

---

## 0. Scope decision and what changed

The operator answered the two open questions and widened the slice:

- **Q59 → fix FA's own composition bug first**, then build on that.
- **Q60 → fix the history rebuild** (I-52), not defer it.
- **New goal:** exercise **providers that do not exist in the config today** —
  no adapter, no registry entry, no `models.yaml` mention.

That makes S13 **open-scope by design**. This plan therefore splits into a
**closed core** (S13.0–S13.4, fully specified, fixed DoD) and an **open
exploration** (S13.5+, bounded by a protocol rather than a list). The core must
land and stay green regardless of how the exploration goes.

**Why this ordering is not negotiable:** every new provider is a new source of
truth about our request shape. Onboarding providers *before* the composition
bug is fixed means each one reports the same known defect and we learn nothing
new. Fix the emitter, then let new providers tell us what else is wrong.

---

## 1. Preflight — source-verified

### 1.1 Two defects, one emitter

| # | site | defect |
|---|---|---|
| I-50 | `prompt_composer.py:123-125` | task appended as `user`, **then** `observations` — a resumed session ends on `assistant` |
| I-52 | `coder_loop.py:450-490` | rebuild maps only `model_msg`→`assistant`, `tool_result`→`tool`; **`user_msg` rows are never replayed** |

They are the same emitter seen twice: FA's history reconstruction is neither
**faithful** (I-52) nor **ordered** (I-50). Fixing only ordering would make an
invalid request valid while leaving the model without the instruction its
inherited turns were answering.

### 1.2 The chokepoint is genuinely single

`grep` across `src/`: exactly one call site reaches a provider —
`chain.py:368 provider.request(...)`. No module outside `chain.py` constructs a
provider. Any conformance pass placed there is unbypassable.

### 1.3 Adding a provider is already nearly free

`registry.py:40-58` maps **18 provider names** onto **4 adapters**; 14 already
share `_OPENAI_COMPAT`. So a new OpenAI-compatible provider is *one line* today.

**But that is exactly the trap.** Groq, Cerebras, NVIDIA NIM and OpenRouter are
all "OpenAI-compatible" and all diverge in practice — the S11 evidence shows
Mistral rejecting orderings OpenAI accepts. A registry entry claims
compatibility; only a conformance run proves it.

### 1.4 Eval independence: blocking → adversarial (operator decision, 2026-08-03)

**Today (source-verified).** `roles.py:186 check_eval_disjoint` **raises**
`EvalFamilyConflictError` when the eval family equals planner's or coder's. It
is called from `config.py:316-321`, guarded by
`if _FAMILY_DISJOINT_ROLES.issubset(roles.keys())` — so it fires only when all
three roles are declared. `EvalFamilyConflictError` is caught in **four**
`cli.py` sites (2039, 2651, 2833, 2901) and surfaces as **exit 2**.

**Operator decision: change from blocking to adversarial.** Same-family eval is
no longer a configuration error. It becomes a **recorded risk** plus an
**adversarial posture on the eval role itself**.

**Why this is the better design, not merely a relaxation.** The blocking rule
enforced a *proxy* for the real goal. ADR-2's evidence is about **error
correlation** (~+0.6 same-family vs ~−0.05 cross-family) — the family string was
a cheap stand-in for independence. Three problems with the proxy:

1. **It is trivially satisfiable without being satisfied.** The live deployment
   runs `mistral-small-2603` in all three roles and passes the gate, because the
   YAML says `family: "mistral"` for coder and `family: "mistral_eval"` for eval.
   The gate is green; the independence is fictional. **A gate that a string edit
   defeats is not protecting anything.**
2. **It blocks the free-tier reality.** Groq, Cerebras and NVIDIA NIM serve
   largely the *same open-weight families* (Llama, Qwen, DeepSeek). Requiring a
   disjoint family can make a legitimate multi-provider setup unloadable — the
   config fails to parse rather than warning.
3. **It punishes honesty.** An operator who labels families accurately is
   blocked; one who fudges the string is not.

**Adversarial replacement — two mechanisms, both required:**

- **Declared risk, not refusal.** Same-family eval loads with a
  `ModelsConfig.warnings` entry (the soft channel already exists,
  `config.py:176`) and a `config_warning` event (already wired,
  `state.py:390-399`). The operator is told the ensemble-error correlation they
  are accepting, with the ADR-2 figures, and the run proceeds.
- **Adversarial eval stance.** When the eval family is *not* disjoint, the eval
  role is instructed to actively seek disconfirming evidence rather than
  ratify. Correlated priors are countered by an opposing objective instead of a
  config error. Cross-family eval keeps today's neutral stance.

**What must NOT be lost.** The correlation risk is real and measured — this is a
change of *mechanism*, not a claim the risk is gone. Three guards:

- the warning must be **impossible to miss** (structured event + stderr, not a
  buried log line);
- the eval verdict must **record which stance produced it**, so a `DONE` from a
  same-family adversarial eval is distinguishable in `eval_report.json` from a
  `DONE` by a disjoint neutral eval;
- ADR-2 must be **amended, not contradicted** — the amendment records the
  decision and its rationale.

**Consequence for this slice.** Removing the hard gate is what makes the S13.7+
matrix runnable at all: three providers over the same open-weight families can
now be exercised. It also removes a false-confidence signal — a green gate that
a `family:` string satisfies.

### 1.5 Free tiers with tool calling (researched 2026-08-03)

Candidates that are OpenAI-compatible, need no card, and support tool use:

| provider | free limit | tool calling | notes |
|---|---|---|---|
| **Groq** | 30 RPM, ~14.4k RPD | yes | LPU, sub-second; Llama/Qwen/Kimi/GPT-OSS |
| **Cerebras** | 30 RPM, 1M TPD | yes | Qwen3, Llama 3.3 70B |
| **NVIDIA NIM** | ~40 RPM, 1k credits | yes | 120+ open-weight incl. DeepSeek, GLM, Qwen |
| **OpenRouter** | 20 RPM, ~50–200 RPD | model-dependent | already in the registry |
| **Google AI Studio** | 15 RPM, 1.5k RPD | yes | **not** OpenAI-shaped — real adapter work |
| **Z.AI (GLM)** | 1 concurrent | yes | `glm` family already named in `config.py` |

Groq, Cerebras and NVIDIA NIM are already **registry names** but have never been
exercised. Gemini is the genuinely new *adapter* and is the honest test of "how
hard is a new provider".

**Rate limits are a first-class design input, not a footnote.** At 30 RPM a
three-role workflow with 6 turns per role is ~18 requests — one run is fine, a
matrix of 6 providers × 3 roles is not. S13.6 addresses this explicitly.

---

## 2. Design

### D1 — Fix the emitter, then conform at the boundary

Two layers, deliberately separate:

1. **Composition** (`prompt_composer.py`, `coder_loop.py`) — produce a
   *correct, faithful, provider-neutral* message list. Fixes I-50 + I-52 at
   source.
2. **Conformance** (`chain.py:368`) — enforce per-adapter rules on the way out,
   for divergences FA cannot know about centrally.

Layer 1 is the fix. Layer 2 is the **safety net and the discovery instrument** —
it is what will catch the *next* provider's quirk without a live outage.

### D2 — Capability records, never provider-name branching

`MessageRules` attached to `ProviderSpec`. Adding a provider = one line; adding a
*quirk* = one field. Same lesson as S12's probes: describe the capability, not
the platform.

### D3 — Repair by reordering FA's own content

Never inject invented assistant text (LibreChat's `"Understood."`). Zero added
tokens, and task-after-context is semantically more correct.

### D4 — A conformance suite, not a provider list

The open half is specified as a **protocol** any provider must pass, so adding
provider N+1 needs no plan edit:

```
CONF-1  minimal completion            (200, non-empty)
CONF-2  single tool call round-trip   (tool_calls -> tool result -> answer)
CONF-3  resumed transcript            (the I-50 shape: history then new task)
CONF-4  multi-turn tool chain         (2+ sequential calls)
CONF-5  trailing-assistant tolerance  (records the capability, does not require it)
CONF-6  user-after-tool tolerance     (Mistral 3230's other half)
CONF-7  prompt-cache behaviour        (records hit rate; no pass/fail)
```

Output is a **capability matrix**, not a pass/fail verdict. A provider that
fails CONF-5 is not broken — it has a rule, and the rule goes in its
`MessageRules`.

### D5 — Every conformance probe runs offline first

Each CONF case runs against `StrictScriptedTransport` in CI **and** optionally
against a live provider. CI is the ratchet; live is discovery. A CONF case that
cannot run offline is not admitted.

---

## 3. Contracts

**CT1** — resumed transcripts are *faithful*: a replayed history contains the
prior stage's user instruction (I-52).
**CT2** — every outbound request satisfies its adapter's `MessageRules` (I-50).
**CT3** — normalization never invents content; repair is reordering only.
**CT4** — the cacheable prefix is byte-identical after normalization
(protects the 74–99% live cache-hit rate).
**CT5** — unfixable lists (dangling `tool_call_id`) fail **locally**, before HTTP.
**CT6** — adding a provider is one registry line; adding a quirk is one field.
**CT7** — the conformance suite runs fully offline in CI.
**CT8** — same-family eval **loads with a loud warning** and runs with an
adversarial eval stance; disjoint eval warns not at all. A verdict records which
stance produced it.

---

## 4. Steps — CLOSED CORE (must land)

### S13.0 — Pin the failure (no edits)

Commit the live failing message shape from `events.jsonl` as a fixture.
**DoD:** fixture committed; documented as the I-50 reproduction. **Class:** C0.

### S13.1 — `StrictScriptedTransport` — fix the oracle first

**The reason the suite missed a P1 defect:** S8's transport accepts any message
order. New transport enforces: last role ∈ {user, tool}; no `user` after `tool`;
every `tool` message resolves to a declared `tool_call_id`.

**DoD (negative proof):** pointed at **today's** code it **reproduces the 400**.
If it passes before the fix, the oracle is wrong and the slice stops.
**Class:** C1. **Kill-check:** revert S13.2/S13.3 → this fails.

### S13.2 — I-52: faithful history rebuild

Replay `user_msg` rows in `coder_loop.py:450-490`.
**Interaction to measure, not assume:** the compaction window
(`latest_comp_idx`, `coder_loop.py:455-463`) and the token/cache cost of extra
messages.
**DoD:** C1 test asserts a resumed transcript contains the prior stage's user
instruction; token delta measured and recorded. **Class:** C1.

### S13.3 — I-50: correct ordering at composition

Task message emitted **after** observations when history is non-empty.
**DoD:** S13.1's transport passes; CT4 proven (cacheable prefix unchanged).
**Class:** C1.

### S13.4 — `MessageRules` + conformance pass at `chain.py:368`

**DoD:** `git diff` touches only `providers/`; K1–K6 green; suite unchanged.
**Class:** C1 + C0p.

### S13.4c — Eval independence: blocking → adversarial

**Current source-verified behaviour.** `check_eval_disjoint` (`roles.py:186`)
raises `EvalFamilyConflictError`; called at `config.py:316-321`; caught at
`cli.py:{2039,2651,2833,2901}` → exit 2. Pinned by tests in
`test_roles.py`, `test_providers_config.py`, `test_providers_chain.py`,
`test_mistral_integration.py`, `test_s10b_cli_parity.py`,
`test_s10c_config_error_contract.py`.

**Files allowed to change:** `src/fa/roles.py`, `src/fa/providers/config.py`,
`src/fa/inner_loop/profiles.py` (eval stance), `knowledge/adr/ADR-2-*.md`,
plus the six test modules above.

**Mechanism.**

1. `check_eval_disjoint` → `assess_eval_independence(...) -> EvalIndependence`,
   a value object (`disjoint: bool`, `reason: str`, `stance: "neutral" |
   "adversarial"`). **It no longer raises.**
2. `config.py:316` appends to `ModelsConfig.warnings` when not disjoint —
   reusing the existing soft channel rather than inventing one.
3. The eval role composes an **adversarial** system stance when
   `stance == "adversarial"`.
4. `eval_report.json` records `eval_independence: {disjoint, stance}` so a
   verdict carries its own provenance.

**Failure behaviour.** A malformed/unknown family still raises
`FamilyExtractionError` — this step relaxes the *disjointness* rule only, not
family validation. Do not widen it into "any family string is fine".

**Deprecation, not deletion.** Keep `EvalFamilyConflictError` exported and keep
the four `cli.py` handlers: removing a public exception is a separate breaking
change, and the handlers cost nothing. Mark it deprecated in the docstring.

**DoD.**
- same-family config **loads**, emits exactly one warning naming both roles and
  the ADR-2 figures, and the run proceeds;
- disjoint config emits **zero** warnings (no false positives);
- eval stance is adversarial iff not disjoint — asserted on the composed prompt,
  not on a flag;
- `eval_report.json` carries `eval_independence`;
- the six pinning test modules are updated to assert the **new** contract, not
  deleted;
- ADR-2 amended in the same commit.

**Tests-writing class:** C1 + C0p (contract change).
**Producer kill-check:** force `stance="neutral"` on a same-family config → the
adversarial-prompt assertion fails, naming the missing stance.

---

### S13.4b — I-51: surface the provider's error

Carry real `provider`/`status`; render `reason`.
**DoD:** C1 test asserts the rendered line contains the provider's message.
**Class:** C1.

---

## 5. Steps — OPEN EXPLORATION (bounded by protocol)

### S13.5 — The conformance harness

`tests/conformance/` implementing CONF-1…7 against `StrictScriptedTransport`,
plus `fa conformance --provider <name>` for live runs.
**DoD:** all 7 run offline in CI; the command exists and is documented.
**Class:** C2.

### S13.6 — Rate-limit-aware live runner

At 30 RPM a full matrix will 429 (already observed in S11.4e). The runner needs
per-provider RPM config, sequential execution with backoff, and **resumability**
so a 429 does not discard completed results.
**DoD:** a matrix run survives an induced 429 without losing prior rows.
**Class:** C1.

### S13.7 — Onboard registry-known-but-unexercised providers

**Groq, Cerebras, NVIDIA NIM** — already registry names, never run.
**DoD per provider:** CONF matrix recorded; `MessageRules` set from *measured*
behaviour, never assumed; deltas → BACKLOG.
**Class:** C3. **Stop rule:** a provider needing more than a `MessageRules`
field gets its own slice — do not grow adapters inside S13.

### S13.8 — One genuinely new adapter (Gemini)

Gemini is **not** OpenAI-shaped, so this measures the real cost of "add a
provider". It is the honest answer to the operator's question.
**DoD:** CONF matrix; **a measured line count** for the new adapter, recorded in
the parent plan as the true onboarding cost.
**Class:** C3. **Stop rule:** if it exceeds ~200 lines, stop and promote to its
own slice.

### S13.9 — Cross-family workflow (§1.4's real payoff)

Run `planner→coder→eval` with **genuinely different families** per role, which
is what `check_eval_disjoint` was written for.
**DoD:** one full workflow completes across ≥2 providers; ensemble behaviour
recorded. **Class:** C3.

---

## 6. Kill-checks

| # | force | expected |
|---|---|---|
| K1 | revert S13.3 | strict transport fails with the 3230 shape |
| K2 | `allows_trailing_assistant=True` for Mistral | strict transport fails |
| K3 | already-valid list | normalization is a **no-op** (identity) |
| K4 | dangling `tool_call_id` | raises locally, before HTTP |
| K5 | revert either half of S13.4b | rendered line loses the provider message |
| K6 | new `ProviderSpec`, no rules | defaults apply, suite green |
| K7 | revert S13.2 | the CT1 faithfulness test fails |
| K8 | induced 429 mid-matrix | runner resumes, prior rows intact |
| K9 | same-family config | **loads** (no exit 2), exactly one warning, adversarial stance in the composed eval prompt |
| K10 | disjoint config | **zero** warnings, neutral stance — proves K9 is not vacuous |

K3 is the quiet one: a normalizer that rewrites *healthy* requests would
silently invalidate every prompt-cache entry.

---

## 7. Risks

| # | risk | mitigation |
|---|---|---|
| R1 | **prompt-cache regression** | CT4; live before/after; **<74% is a stop condition** |
| R2 | I-52 raises token cost per resumed request | measured in S13.2, recorded; compaction interaction explicitly checked |
| R3 | **open scope never closes** | closed core is independently shippable; S13.5+ has per-provider stop rules |
| R4 | free-tier 429s make live results noisy | S13.6 is a prerequisite for S13.7+, not an afterthought |
| R5 | a new provider needs deep adapter work | stop rule: >~200 lines → own slice |
| R7 | **eval independence silently degrades** now that it does not block | CT8 + K9/K10; warning on the structured event bus, and `eval_report.json` records the stance so a correlated `DONE` is auditable after the fact |
| R8 | adversarial stance makes eval reject good work | S13.9 measures verdict distribution across both stances; a false-reject spike is a stop condition |
| R6 | ToS: free tiers are dev/test only | conformance runs are development testing; no production traffic, one account per provider |

---

## 8. Definition of Done

**Closed core (blocking):**

- [ ] S13.1 reproduces the 400 on unfixed code
- [ ] K1–K7 executed with real output
- [ ] Linux suite green; coverage ≥ 83.22%
- [ ] Zero `noqa`
- [ ] **Live:** `fa workflow planner,coder,eval` completes past stage 2
- [ ] **Live:** cache-hit ≥ 74%
- [ ] S11.7 re-run; Q35b exit-1 path attempted
- [ ] Same-family eval loads + warns + runs adversarial (K9); disjoint stays
      silent and neutral (K10)
- [ ] ADR-2 amended in the same commit as the behaviour change

**Open exploration (reported, not gated):**

- [ ] CONF-1…7 run offline in CI
- [ ] ≥3 providers with a recorded capability matrix
- [ ] ≥1 non-OpenAI-shaped adapter, with measured line count
- [ ] ≥1 cross-family workflow completed
- [ ] Every divergence found → BACKLOG with repro

---

## 9. Open questions

**Q61 — which providers, and who holds the keys?** S13.7/S13.8 need real
accounts. Groq + Cerebras + NVIDIA NIM cover three infrastructures with no card.
Confirm the list and who registers.

**Q62 — does the conformance matrix become a CI gate?** Recommend **no** for
live runs (flaky, rate-limited, costs tokens) and **yes** for the offline
`StrictScriptedTransport` half. Confirm.

**Q63 — `models.yaml` schema for multi-provider roles.** Cross-family roles may
want per-provider `sampling`. The current schema supports it via chain entries;
S13.9 will show whether that is ergonomic. Defer until measured.

---

**Q64 — should the adversarial stance also apply to *cross-family* eval?**
Arguably an adversarial eval is better in general, and only its *necessity*
depends on family overlap. This plan keeps cross-family neutral so S13.9 can
measure the two stances against each other; making both adversarial would
remove the control group. Revisit once there is data.

## 10. Anti-theatre checklist

- [x] Researched production harnesses before designing (opencode #19517/#6346,
      LiteLLM #17761, LibreChat #12429, crush #279, pydantic-ai #3733)
- [x] Rejected LibreChat's synthetic-message fix with a stated reason
- [x] Verified the chokepoint is single by `grep`, not assumption
- [x] Verified 18 providers → 4 adapters, and named why that is a trap
- [x] Found the pre-existing architectural driver (`check_eval_disjoint`)
      rather than treating multi-provider as a new feature
- [x] Rate limits treated as a design input (S13.6 gates S13.7)
- [x] Open half bounded by a protocol + stop rules, so it can end
- [x] The eval-disjoint relaxation is justified by showing the **existing gate
      is already defeated by a string edit on the live box**, not by asserting
      the risk is gone; replacement mechanism + audit trail specified
- [ ] READY — pending operator review
