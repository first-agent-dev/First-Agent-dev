# ADR-11 — Authoring Guardrails (two-tier TCB)

- **Status:** proposed
- **Date:** 2026-06-01
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

This ADR consumes a single source of truth (SSOT): the merged production blueprint
[`knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md).
The blueprint analysed four OSS stacks (Hermes Agent, Archon, Grafema, NeMo Guardrails) plus the
First-Agent target, resolved 8 R-N conflicts, and produced the R-1..R-18 specifications this ADR
decides on. The blueprint is the evidence layer; this ADR is the decision layer.

### Threat model: LLM as Untrusted Compiler

The forcing function is **not** code style — it is admission control. The LLM author is an
**untrusted compiler** that:

1. Receives intent (a natural-language task description).
2. Translates that intent into multi-file patches.
3. Can edit **any** file in the repository — including the guardrails themselves.
4. Can skip, weaken, or bypass validation **in the same patch** that introduces the violation.

This turns authoring-time validation from a *linting* problem into an **admission-control
boundary** problem. Ordinary `ruff` / `mypy` / `pytest` do not model this threat: they assume a
cooperating author. The blueprint §1.1 states the thesis verbatim; this ADR leads with it because
every option below is judged by how well it holds against an author who can edit the checker.

### Attack surface (blueprint §1.2)

| Attack vector | Countermeasure | Invariant |
|---|---|---|
| Edit the guardrail kernel to bypass checks | Frozen Level-0 TCB + protected-path governance | ADR-11-I1, ADR-11-I7 |
| Weaken tests instead of fixing code | Test semantic decay lock | ADR-11-I5 |
| Edit a generated/mirrored artifact without updating its source | I-FROZEN + parity checker | ADR-11-I3 |
| Use regex-bypassable patterns (comments / strings / aliases) | AST-based structural rules | ADR-11-I4 |
| Commit outside the declared work area | Session-seam subset check | ADR-11-I8 |
| Bypass `pre-commit` with `--no-verify` | CI-enforced, not pre-commit-only | ADR-11-I6 |
| Drown real violations in false-positive noise | Severity lifecycle + catch/FP corpus | ADR-11-I2 |

### Tooling boundary (blueprint §1.3)

`ruff` (style), `mypy` (types), and `pytest` (runtime) **supplement** these guardrails; they do not
replace them, because none detects stale parity, test decay, or seam drift, and `pytest` itself can
be skipped or weakened by the same agent. `pre-commit` is **bypassable** (`--no-verify`) and is
therefore convenience, not authority. `fa authoring-check` (this ADR) is the **authoritative**,
deterministic, offline, CI-enforced, TCB-protected surface.

### Why this ADR now

First-Agent already ships production-grade seeds that this ADR formalises rather than invents:
`src/fa/hygiene/pr_intent.py` + `tests/test_pr_intent_snapshot.py` pin hook constants to canonical
skill text (the parity pattern), and `src/fa/inner_loop/hooks/intent_guard.py` is one classifier with
two consumers (the [ADR-10 I-1](./ADR-10-deterministic-harness-invariants.md#i-1--single-source-of-truth-classifier)
single-source-of-truth pattern). The guardrails exist ad hoc; without a named decision they will
drift across `pytest`, `pre-commit`, and review prose. ADR-11 lands the architecture, the invariant
slate, and the rollout order so the next authoring rule has one home.

## Options considered

### Option A — Keep authoring checks scattered across pytest / pre-commit / review prose (status quo)

- Pros:
  - Zero new artefact; cheapest right now.
- Cons:
  - No single authoritative surface; rules drift between three locations.
  - `pre-commit`-resident rules are bypassable with `--no-verify`; review prose is not enforced.
  - Does not model the untrusted-compiler threat at all — the author can weaken the very checks that
    would catch the patch.

### Option B — Import a heavy rule engine (Grafema Datalog / graph DB, or NeMo runtime rails)

- Pros:
  - Mature cross-file analysis (Grafema) and runtime rail semantics (NeMo) out of the box.
- Cons:
  - Dependency footprint is wrong for a Level-0 kernel: NeMo pulls `aiohttp` / `onnxruntime` /
    `pydantic` / `jinja2` (blueprint §7.7); Grafema ships a Rust Datalog evaluator + RFDB server.
  - Bootstrapping and false-positive-management costs dominate the first PR — violates
    minimalism-first ([`project-overview.md` §1.2](../project-overview.md#12-enforceable-principle--minimalism-first)).
  - Network-bound checks (Archon marketplace lint) are non-reproducible in required CI.

### Option C — Enforce via standalone CODEOWNERS and/or pre-commit only

- Pros:
  - No code to write; uses GitHub-native review routing.
- Cons:
  - Standalone CODEOWNERS without branch protection + a required protected-path check is a *false*
    security boundary (blueprint R-9); none of the four OSS stacks rely on it alone.
  - `pre-commit`-only enforcement is bypassable; `.github/**` path-skips let a patch alter the
    enforcement itself (NeMo `pr-tests-skip.yml` is negative prior art).

### Option D — Two-tier deterministic TCB: frozen stdlib Level-0 kernel + allowlisted Level-1 rules, CI-enforced, protected-path-governed (chosen)

- Pros:
  - A frozen, stdlib-only Level-0 kernel gives reproducible, offline, snapshot-bound verdicts the
    author cannot silently retune.
  - Level-1 rule packs are dispatched from a static allowlist; rules grow without touching the TCB.
  - Severity lifecycle (HARD-BLOCK / ADVISORY / INFO) makes false-positive budget explicit and keeps
    CI green-able while rules mature.
  - Concepts are borrowed from the four OSS stacks; their *runtimes* are not (blueprint R-7).
- Cons:
  - Adds new files under `src/fa/` and `.github/` (offset against the drift risk Options A/C carry).
  - Protected-path governance adds small per-PR review friction on TCB paths.

## Decision

We will choose **Option D — a two-tier Trusted Computing Base (TCB)**, land the **`ADR-11-I1..I8`**
invariant slate below, bind every write target to an **active consumer**, and fix the
**enforcement-ceiling** at PR-only agent rights + required human review. Implementation is staged per
Appendix B of the blueprint (PR 1..PR 5); this ADR is the contract, not the code (see §Out of scope
in the blueprint §14).

### Two-tier TCB shape (blueprint §9.1, §9.6)

```text
src/fa/authoring_tcb.py            # Level 0 kernel (frozen, stdlib-only)
src/fa/authoring_rules/            # Level 1 rule packs (allowlisted)
  __init__.py                      # static allowlist dispatch
  exports.py parity.py docs.py tests.py seam.py messages.py
scripts/check_protected_paths.py   # CI diff-checker
.github/CODEOWNERS                 # protected paths
.github/workflows/authoring-guardrails.yml  # always-run CI
.fa/session.toml                   # session manifest
Makefile                           # check: lint typecheck authoring-check test
```

- **Level 0** is the TCB: it parses a `--manifest <path>` TOML with stdlib `tomllib`, validates the
  manifest shape, enumerates repository paths in sorted order, computes `snapshot_id`, `kernel_hash`,
  and `rule_pack_hash` (all SHA-256), dispatches an **allowlisted** static import list of Level-1
  rules, collects diagnostics, sorts them deterministically (severity rank → code → path → line →
  message), emits structured JSON/text, and exits `0` if no HARD-BLOCK else `1`.
- **Level 1** holds the rule packs. Rules return structured diagnostics; they never own dispatch,
  hashing, or output. New rules land here behind the allowlist without modifying Level 0.
- **One manifest for v0.1.** The kernel reads a **single** TOML, `.fa/session.toml`, passed as
  `--manifest`; kernel-config and session/seam metadata are **not** split into two files until a
  measured need arises (subtraction-first). Fewer synced manifests = one less parity surface = one
  less authoring attack surface.

### Invariant numbering scheme (blueprint §10.0)

ADR-11 invariants use a **per-ADR prefixed namespace** — `ADR-11-I1`, `ADR-11-I2`, … with stable
anchors (`ADR-11#adr-11-i1`). This deliberately avoids collision with
[ADR-10's global `I-1..I-5`](./ADR-10-deterministic-harness-invariants.md#1-the-invariants-i-1i-5)
and removes future renumbering churn. A mnemonic may ride in the heading (e.g. `ADR-11-I3
(I-FROZEN)`); **mixed numbered + named invariants in one ADR are not allowed.**

### The invariant slate (`ADR-11-I1..I8`)

#### ADR-11-I1 — Level-0 TCB determinism

**Rule.** The Level-0 kernel is **frozen** and **stdlib-only**. It MUST parse TOML via `tomllib`,
enumerate paths in sorted order, bind every verdict to `snapshot_id` / `kernel_hash` /
`rule_pack_hash` (plus a nullable `session_hash` when `.fa/session.toml` is present),
dispatch only a static allowlist of Level-1 rules, emit deterministically sorted
diagnostics, and use exit code `0`/`1` keyed on HARD-BLOCK presence. It MUST **never** import outside
stdlib, make network calls, load plugins dynamically, evaluate LLM output, or use regex for
structural analysis (only for text markers). Behaviour is **fail-closed**: malformed manifest,
unknown key, missing field, empty snapshot, or a rule raising → exit `1` + diagnostic.
**Source.** Blueprint R-1, R-11, R-7, R-8; §9.6–§9.8.

#### ADR-11-I2 — Severity lifecycle as a false-positive budget

**Rule.** Every diagnostic is a `RuleResult` carrying `severity ∈ {HARD-BLOCK, ADVISORY, INFO}`,
`code` (see the diagnostic-code namespace below), `path`, `line`, `message`, `remediation`,
`expires_on` (required when `severity = ADVISORY`), and `rule_input_hash`. The `rule_input_hash`
is computed over the **exact bytes the rule consumed** (not the whole file), so two conforming
kernels produce identical hashes for the same input. **CI fails only on HARD-BLOCK.** An `ADVISORY`
without an `expires_on` date is itself an ADVISORY finding (so warnings cannot become permanent
noise). Promotion `ADVISORY → HARD-BLOCK` requires the rule to catch its fixture in `catch-corpus/`
**and** measure a false-positive rate **< 1 %** on `fp-corpus/` (see [§Verification](#verification),
blueprint R-14).
**Source.** Blueprint R-2, R-14; §9.2.

**Diagnostic-code namespace.** Every `RuleResult.code` is `FA-AUTHORING-V<N>-<SLUG>` (e.g.
`FA-AUTHORING-V2-EXPORTS`). `V<N>` is the catch-corpus vector (§Verification); codes are
**append-only** and a `V<N>` is never re-used for a different rule — mirroring the `ADR-11-I<N>`
freeze rule above, so an externally-visible code is as stable as an invariant number.

#### ADR-11-I3 (I-FROZEN) — generated/mirrored parity

**Rule.** For every committed generated or hand-mirrored artifact, the source-of-truth path(s) are
recorded and a regenerated-content mismatch is a **HARD-BLOCK**. Guarded blocks are marked with a
stdlib-scannable comment, with **no YAML frontmatter in code comments**:

```text
# I-FROZEN: source=<path#anchor> checker=<path-or-rule-code>
```

The first concrete pair is `knowledge/skills/pr-creation/SKILL.md` ↔ `src/fa/hygiene/pr_intent.py`
constants — FA already seeds this in `tests/test_pr_intent_snapshot.py`.
**Source.** Blueprint R-3; §9.3.

#### ADR-11-I4 — structural rules use AST, not regex

**Rule.** Python structural rules (e.g. `__all__` completeness, `yaml.load` vs `safe_load`, swallowed
broad `except`, frozen-block edits) MUST use stdlib `ast.NodeVisitor`. Regex is permitted only for
file-inventory and simple text markers. Rationale: regex fails on comments, strings, aliases, and
nesting, and is trivially bypassable by an adversarial author.
**Source.** Blueprint R-4; §12.4.

#### ADR-11-I5 — test semantic decay lock

**Rule.** Test-weakening is blocked. **HARD-BLOCK:** `pytest.skip`, `pytest.mark.skip`, non-strict
`xfail`, `.only`-style focus markers, and placeholder assertions (`assert True` /
`assert False is False`). **ADVISORY** (until corpus-validated): `==`→`in` weakening, exact-exception
→ broad `Exception`, and other assertion weakening. `xfail` requires `strict=True` + an ADR/issue
reference; allowlisted edge cases carry an expiry date.
**Source.** Blueprint R-5; §9.3–§9.4.

#### ADR-11-I6 — CI is the authority, not pre-commit

**Rule.** The authoritative checks run inside `make check` (`check: lint typecheck authoring-check
test`) and an **always-run** CI workflow with **no `paths:` filter** (gate work inside the job, per
Hermes `contributor-check.yml`). `pre-commit` is developer convenience only. Authoring checks MUST
NOT be path-skipped for docs-only or `.github/**` changes — those paths can alter enforcement itself.
**Source.** Blueprint R-6; §12.5.

#### ADR-11-I7 — protected-path governance + TCB denylist

**Rule.** TCB and enforcement paths (`src/fa/authoring_tcb.py`,
`src/fa/authoring_rules/__init__.py`, `.github/workflows/authoring-guardrails.yml`,
`.github/CODEOWNERS`, `scripts/check_protected_paths.py`) are governed by the **bundle**: CODEOWNERS +
branch protection + a required CI diff-check. A `realpath`-resolved denylist (Hermes `file_safety.py`
pattern — check both exact paths and prefixes to defeat symlink bypass) flags writes to TCB paths.
**Standalone CODEOWNERS is not sufficient**, and there is **no `--yolo` bypass** (unlike Hermes
`HERMES_YOLO_MODE`).
**Source.** Blueprint R-12, R-15, R-9; §9.5.

#### ADR-11-I8 (I-BOOT) — session seam and bootstrap read-set

**Rule.** `.fa/session.toml` is the source of truth for the authoring seam, session id, and trailers.
The first enforceable rule is **staged paths ⊆ declared seam**. `I-BOOT` **extends** (does not
replace — `llms.txt` wins) the `knowledge/llms.txt` §MUST READ FIRST five-file set with an authoring
addendum (`.fa/session.toml`, `src/fa/authoring_rules/README.md`). I-BOOT is **procedural** until the
harness can emit read receipts (path + hash). Merge-time CI can only enforce against a trusted
committed manifest; no silent claim that CI validates local state it cannot see.
**Source.** Blueprint R-13.

### Active consumer for every write target (blueprint §9.9; AGENTS.md anti-pattern #3)

Per [AGENTS.md §Cross-project anti-patterns rule #3](../../AGENTS.md#cross-project-anti-patterns---learnt-from-precedents),
every new write target lands with a named consumer:

| Write target | Active consumer |
|---|---|
| `authoring-check` diagnostics (JSON/text) | CI workflow `authoring-guardrails.yml` (exit-code gate) + agent/human reading output |
| `.fa/session.toml` | Level-1 `seam.py` (staged ⊆ seam) + commit-msg trailer injector |
| `catch-corpus/` | R-14 corpus test — every fixture must be caught |
| `fp-corpus/` | R-14 FP-rate measurement — gate for ADVISORY → HARD-BLOCK promotion |
| `kernel_hash` / `rule_pack_hash` / `snapshot_id` | reproducibility check + `scripts/check_protected_paths.py` diff-check |
| PLAN-style leading/lagging metrics | **No named consumer yet → DEFER.** Do not create the write target until a `make` target or report consumes it. |

### Enforcement-ceiling (blueprint §12.7, resolved)

In First-Agent the authoring agent has the right only to **open** PRs — it cannot merge. The
enforcement boundary is therefore: **PR-only agent rights + required human review at merge + a CI
check (`scripts/check_protected_paths.py`) that surfaces any edit to protected/TCB paths.** Under this
model CODEOWNERS and branch protection are **recommended, not load-bearing**; the only residual
requirement is that the human reviewer acts on the protected-path flag. I-FROZEN is a HARD-BLOCK at
the CI flag; the merge gate is human review. CI detects changes — branch protection (where enabled)
enforces review; CI cannot prove human approval by itself.

## Verification

The decision is verified against a fixed baseline, not subjective review (blueprint R-14, §11.1).
Two corpora live at the repo root and are consumed as named in the active-consumer table above:

```text
catch-corpus/   # fixture diffs the rules MUST flag (true positives), sourced from the PR B/C
                # "10 authoring omissions" archaeology (F-1..F-10 below)
fp-corpus/      # diffs from recent green commits the rules MUST NOT flag (false positives)
```

**Catch-corpus baseline (F-1..F-10).** Each historical omission maps to the diagnostic vector
`V<N>` that must catch it; `V<N>` is the stable middle field of the `FA-AUTHORING-V<N>-<SLUG>`
code namespace (see [ADR-11-I2](#adr-11-i2--severity-lifecycle-as-a-false-positive-budget)).

| ID | Historical omission (PR B/C) | Root cause | Target vector(s) |
|---|---|---|---|
| F-1 | LLM bypasses `_is_mutating_call` with an unknown tool shape | Spec↔code doc drift | V1 + V7 (SSOT enum) |
| F-2 | New middleware missing from `__all__` | Cross-file omission | V2 (AST completeness) |
| F-3 | `SQUASH_MSG` updated in Python, missed in Bash | Dual-location update fail | V3 (generation parity) |
| F-4 | Test for `git add` written, `git add -i` missed | Happy-path bias | V4 (negative adjacency) |
| F-5 | `BACKLOG.md` milestone closed but blockers remain | Line-level invariant | V5 (doc integrity) |
| F-6 | `llms.txt` not updated after a new ADR | Index update omission | V5 (doc integrity) |
| F-7 | Public helper missing from re-export | Encapsulation bypass | V2 (AST completeness) |
| F-8 | Signature changed; 4 call-sites updated, 1 missed | Partial refactoring | V10 (reference safety) |
| F-9 | Test weakened (`== "deny"` → `in ("allow","deny")`) | Test semantic decay | V11 (assertion lock) |
| F-10 | Session trailer (`Co-authored-by`) omitted | Procedural drift | V14 (AI trailers) |

Vectors not yet on the v0.1 rule roadmap (e.g. V4 negative-adjacency, V14 trailers — blueprint §11.1
rates them LOW) stay catch-corpus targets for later packs; they do not block v0.1.

**Promotion gate.** A rule moves `ADVISORY → HARD-BLOCK` only when it (a) flags its F-N fixture in
`catch-corpus/`, and (b) measures a false-positive rate **< 1 %** over `fp-corpus/`. Until both
corpora exist (blueprint Appendix B, PR 4) the measurement is **DEFERRED**; the 1 % target is fixed
now so promotion is never a subjective call.

**Kernel self-verification.** Level 0 ships with its own positive/negative fixtures meeting the
repo coverage gate and strict `pylint` (see Consequences); reproducibility is checked by re-running
the kernel on an unchanged snapshot and asserting identical `snapshot_id` / `kernel_hash` /
`rule_pack_hash`.

## Consequences

- **Positive.**
  - One authoritative, deterministic, offline authoring surface (`fa authoring-check`) replaces rules
    scattered across `pytest` / `pre-commit` / review prose.
  - The untrusted-compiler threat is met structurally: the TCB is frozen and protected-path-governed,
    so an author cannot weaken the checker in the same patch without surfacing a HARD-BLOCK flag.
  - Severity lifecycle keeps CI green-able while rules mature; ADVISORY-with-expiry prevents permanent
    warning noise; promotion is measurement-based, not subjective.
  - Future authoring rules have one home (Level-1 allowlist) and one citable contract (`ADR-11#...`).

- **Negative.**
  - New files under `src/fa/` and `.github/`; new per-PR review friction on protected/TCB paths.
  - I-BOOT and the seam check stay **procedural** until the harness emits read receipts — a documented
    gap, not a silent one.
  - Some rules (V5 docs, V12 message registry) land as ADVISORY first and need FP-corpus validation
    before they can become HARD-BLOCK.
  - The Level-0 kernel must satisfy the repo's existing CI gates independently of its own logic:
    line coverage `fail_under = 90` (`pyproject.toml`, surfaced by `.github/workflows/ci.yml`) and
    **strict** `pylint` on `src/**` (`.github/workflows/pylint.yml`). This is a feature, not a tax —
    a tiny frozen kernel is exactly what makes ~100 % coverage and mutation-kill (`tests.yml`) cheap,
    which in turn reinforces the minimal-Level-0 decision.

- **Follow-up work this unlocks or requires** (blueprint Appendix B rollout):
  - **PR 1** — Level-0 TCB skeleton + protected-path governance (R-1, R-11, R-2, R-6, R-7, R-10, R-12, R-15).
  - **PR 2** — first Level-1 teeth: `exports.py`, `tests.py` (R-4, R-5).
  - **PR 3** — parity + docs rules: `parity.py`, `docs.py`, I-FROZEN marker convention (R-3, R-4).
  - **PR 4** — session seam + catch/FP corpora: `seam.py`, `.fa/session.toml`, F-1..F-10 fixtures (R-13, R-14).
  - **PR 5** — advisory experiments + severity tuning: `messages.py`, promotion criteria (R-2, R-14).
  - **Deferred (post-v0.1):** save-time `--watch` feedback (R-16), network freshness watchdog
    outside Level 0 (R-17), tool-whitelisted self-improvement that never mutates Level-0/HARD-BLOCK
    rules (R-18).

## Prior Art

Per [AGENTS.md §Cross-project anti-patterns rule #4](../../AGENTS.md#cross-project-anti-patterns---learnt-from-precedents)
(every new ADR documents existing tools/papers/projects to prove we are not re-inventing). Full audit
evidence — file inventories with line ranges — lives in the SSOT blueprint
[`ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md)
§4–§8 and §13. Each entry names what we borrow and why we do **not** reuse the runtime verbatim (R-7).

- **Hermes Agent (NousResearch).** Strongest prior art for the write-path **denylist** and CI
  discipline: `agent/file_safety.py` (≈453 LOC, stdlib `os`/`pathlib`/`typing` only) denies writes to
  control files via exact paths + prefixes resolved through `os.path.realpath()`;
  `.github/workflows/contributor-check.yml` always-runs with zero path filters;
  `agent/curator.py` constrains self-improvement to `created_by: "agent"` assets and never deletes.
  Informs ADR-11-I7 (denylist + no-bypass), ADR-11-I6 (always-run CI), and the deferred R-16/R-18.
  **Not reused verbatim:** Hermes is ≈175K LOC with a `--yolo` bypass (`approval.py`) that FA
  explicitly forbids; FA borrows the discipline, scaled down, not the platform.

- **Archon (`coleam00/Archon`).** Strongest prior art for **generated parity / anti-tampering through
  CI**: `scripts/generate-bundled-defaults.ts` runs in `--check` mode (sorted filenames, CRLF→LF
  normalisation, non-zero exit on drift) before typecheck/lint/tests; the workflow loader splits
  warn-and-drop vs hard-error. Informs ADR-11-I3 (I-FROZEN parity) and ADR-11-I6 (parity before other
  checks). **Not reused verbatim:** Archon's marketplace lint is network-bound — explicitly excluded
  from Level 0 (R-8).

- **Grafema (`Disentinel/grafema`).** Strongest prior art for **cross-file structural invariants and
  severity-as-budget**: `Analysis.Walker` routes statements to rule modules; `Rules.UnsafeDynamic`
  uses closed sets with exact node metadata; `.grafema/guarantees.yaml` is a three-tier
  `error|warning|info` corpus calibrated to "no false-positive CI failures"; `GuaranteeManager`
  defines the list→run→emit→fail lifecycle; `GraphFreshnessChecker` hashes content before trust.
  Informs ADR-11-I4 (AST over regex) and ADR-11-I2 (severity lifecycle). **Not reused verbatim:** the
  Datalog engine + RFDB server are far too heavy for a Level-0 kernel — concept only (R-7).

- **NeMo Guardrails (`NVIDIA-NeMo/Guardrails`).** Runtime-rail prior art only: the template-method
  `rail_action`, the minimal `RailResult(is_safe, reason)` frozen type, short-circuit/parallel-cancel
  semantics, and `test_config_validation.py` pinning failure messages; the security guidelines prefer
  allow-lists and **fail-closed**. Informs ADR-11-I2 (tiny frozen result type) and ADR-11-I1
  (fail-closed). **Not reused verbatim:** the dependency footprint (`aiohttp`, `onnxruntime`,
  `pydantic`, `jinja2`) and `pr-tests-skip.yml` path-skip are negative evidence — confirming Level 0
  must stay offline/stdlib-only and never path-skip (R-7, R-8, §12.5).

- **First-Agent existing seeds (in-repo).** `src/fa/hygiene/pr_intent.py` +
  `tests/test_pr_intent_snapshot.py` are the live parity-lock seed for ADR-11-I3;
  `src/fa/inner_loop/hooks/intent_guard.py` instantiates the one-classifier-two-consumers discipline
  ([ADR-10 I-1](./ADR-10-deterministic-harness-invariants.md#i-1--single-source-of-truth-classifier)).
  ADR-11 formalises and extends these rather than re-implementing them. Two further in-repo assets the
  blueprint (§8.5–§8.6) flags as directly reusable: `src/fa/chunker/` (deterministic sorted path
  enumeration, `fa chunk` CLI, positive/negative snapshot fixtures) and DSV (`verifiers/*.yaml`
  contracts + their `src/fa/verifier/` parser — the Level-1 "deterministic check against a manifest"
  shape). **Not reused inside
  Level 0:** the chunker may import non-stdlib (e.g. `markdown-it-py`) and lives outside the TCB, so
  the kernel keeps its **own** tiny stdlib `os.walk`+`sorted` enumeration — freezing the TCB boundary
  beats DRY across it. ADR-11 borrows their *patterns* (enumeration, CLI shape, manifest-driven
  verification) for Level 1, not their modules for Level 0.

## References

- [`knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md)
  — SSOT. §0 decision briefing; §1 threat model; §9 two-tier TCB + active-consumer; §10 R-1..R-18
  specs; §11 fit audit; §12.7 enforcement-ceiling; §13 files used; Appendix A/B summary + rollout.
- **R-N → invariant map.** R-1/R-11 → ADR-11-I1; R-2/R-14 → ADR-11-I2; R-3 → ADR-11-I3; R-4 →
  ADR-11-I4; R-5 → ADR-11-I5; R-6 → ADR-11-I6; R-12/R-15/R-9 → ADR-11-I7; R-13 → ADR-11-I8; R-10 →
  this §Context threat model; R-7/R-8 → §Options B/C + ADR-11-I1; R-16/R-17/R-18 → §Consequences
  deferred.
- **Catch-corpus baseline (F-1..F-10).** Imported from the PR B/C authoring-omission archaeology
  (session retrospective); blueprint §11.1 marked this baseline "must import from PR B/C audit".
  Enumerated with target vectors in [§Verification](#verification).
- [`ADR-10`](./ADR-10-deterministic-harness-invariants.md) — deterministic-harness invariants
  (I-1..I-5) around the LLM call; ADR-11 is the **authoring-time** complement and uses a disjoint
  `ADR-11-I<N>` namespace per §10.0.
- [`ADR-6`](./ADR-6-tool-sandbox-allow-list.md) — runtime tool sandbox (the execution-time boundary;
  ADR-11 governs the authoring-time boundary).
- [`ADR-7`](./ADR-7-inner-loop-tool-registry.md) / [`ADR-8`](./ADR-8-hook-registry.md) — inner-loop &
  HookRegistry contracts that the future `IntentGuard` / authoring hooks plug into.
- [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md) — the parity counterpart
  of ADR-11-I3 (its §Output format is mirrored by `src/fa/hygiene/pr_intent.py`).
- [`AGENTS.md` §Cross-project anti-patterns](../../AGENTS.md#cross-project-anti-patterns---learnt-from-precedents) — rule #3
  (active consumer, ADR-11-I-table) and rule #4 (mandatory Prior Art).
- [`knowledge/project-overview.md` §1.2](../project-overview.md#12-enforceable-principle--minimalism-first)
  — minimalism-first 4-question test applied to Option D.
- [`knowledge/trace/exploration_log.md` Q-16](../trace/exploration_log.md#q-16--what-authoring-time-guardrail-architecture-does-fa-adopt-and-how-is-it-enforced-2026-06-01) — alternatives
  considered and rejected at ADR-11 decision time.

### Amendment 2026-06-08 — KernelReport audit fields + advisory-undated policy

§9.7 (deterministic output) is extended with two non-removing fields:
`allowlist_signature` (sha256 over the sorted
`type(r).__module__.__qualname__` of each dispatched rule callable) and
`dispatched_count` (length of the static allowlist actually passed to
`run_all`). Both bind every report to *which subset of the rule pack
ran*, closing the gap between `rule_pack_hash` (which fixates only the
source bytes) and the production call site. Rule callables registered
in `RULE_ALLOWLIST` MUST be class instances (not bare functions), so
the `allowlist_signature` derivation is unambiguous. A representative
key for the current allowlist is
`fa.authoring_rules.exports._ExportsCompletenessRule`; the set is
sorted and `\0`-joined before hashing, making the signature insensitive
to dispatch order.

§9.8 (fail-closed) is extended with three new V0-namespace diagnostics:
`FA-AUTHORING-V0-UNPARSABLE` (HARD-BLOCK; emitted by the kernel's
pre-dispatch pass when a scoped `.py` fails to `ast.parse`),
`FA-AUTHORING-V0-IO` (HARD-BLOCK; emitted by the same pre-pass when
`read_bytes` raises `OSError`). The kernel pre-pass parses every scoped
`.py` before rule dispatch; Level-1 rules via `iter_python_files` parse
the same files again. This temporary duplication is accepted because the
rule count is small (3); per-file AST caching is deferred to backlog
item I-22. `FA-AUTHORING-V0-ADVISORY-UNDATED` (ADVISORY; synthesised
post-dispatch when any rule emits a `RuleResult`
with `severity=ADVISORY` and `expires_on=None`, materialising the
"missing date is itself an advisory" rule of ADR-11-I2). The
ADVISORY-UNDATED synth carries `expires_on="9999-12-31"` as a sentinel
to break the self-recursion. The synthesised diagnostic inherits
`rule_input_hash` from the offending `RuleResult` so the diagnostic pair
remains bound to the same input bytes.

`Severity` integer values are **unchanged** (blueprint §9.7-frozen:
HARD-BLOCK=0, ADVISORY=1, INFO=2); a `__bool__` override is added
returning `True` for all members to remove the
`bool(HARD_BLOCK) is False` footgun.

The corpora directories `catch-corpus/` and `fp-corpus/` are seeded
with one fixture per V-code claimed in PR-2; the parametrised harness
in `tests/test_corpus.py` enforces both directions (catch fixtures
must fire; fp fixtures must not). The full F-1..F-10 catch-corpus
expansion remains scheduled for PR-4 (Appendix B). Tool excludes
(`pyproject.toml`: ruff `extend-exclude`, mypy `exclude`, pylint
`ignore-paths`) prevent the intentionally non-conforming fixture
bodies from failing the regular CI lint gates.

None of these changes affect any pre-amendment caller: existing fields
keep their types, existing diagnostic codes remain unique, and the
wire form is additive-only.
