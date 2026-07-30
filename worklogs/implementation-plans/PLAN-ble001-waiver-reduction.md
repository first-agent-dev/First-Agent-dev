# PLAN — BLE001 waiver reduction: make the broad-catch policy real

Plan-ID: `PLAN-ble001-waiver-reduction`

- **Status:** **DRAFT — not scheduled.** Findings are measured and carried
  forward; execution needs an operator decision on Q30 (see §6).
- **Depth:** P2 — touches ~197 sites across 10 packages, but in independently
  landable batches.
- **Origin:** S7 review, 2026-07-30. While fixing two BLE001 findings in
  `hooks/base.py` I claimed the `exc_info` pattern was the house norm. The
  operator asked *"repo-wide?"* — it was not. Measuring properly produced this
  plan.
- **Related:** [`PLAN-cli-trace-S7-direct-run-vertical-slice.md`](./PLAN-cli-trace-S7-direct-run-vertical-slice.md),
  `pyproject.toml` `[tool.ruff.lint] select = ["BLE", ...]`

---

## 1. Why this exists

`pyproject.toml` states the policy verbatim:

> *"BLE: blind `except Exception` — top LLM-agent smell: defensive swallow that
> hides real bugs for months. Every legitimate broad catch carries an inline
> `# noqa: BLE001` + one-line rationale (machine-checked intent)."*

The intent is that a waiver marks the **rare** legitimate case. Measured, the
ratio is inverted:

| Broad `except Exception` in `src/fa` | Count |
|---|---:|
| **Satisfies BLE001 — no waiver** | **37** |
| — re-raises | 33 |
| — logs with `exc_info` | 4 |
| **Waived** | **197** |

**84 % of broad catches are waived.** A waiver that appears 197 times is not a
marked exception; it is the default, and the rule has stopped carrying
information. That is the defect this plan addresses — not the individual
`noqa`s.

*Counting method.* All figures come from an AST walk, not grep. A
`grep 'except Exception'` returns **35** clean sites, not 37 — it misses two
`except BaseException:` handlers (`session_db.py:419`, `manager.py:288`). Any
re-measurement should use the AST, or it will silently under-count.

## 2. Findings (measured, 2026-07-30)

### 2.1 Classification of the 197 waived sites

Built with an AST walk that does **not** descend into nested handlers or inner
functions — the first attempt did, and mis-attributed a nested `raise` in
`pty_pool.py:529` to its outer handler. Corrected before use.

| Cat | Shape | Count | Convertible? |
|---|---|---:|---|
| **A** | bare `pass` (silent swallow, co-waived `S110`) | **34** | no — needs a per-site decision |
| **B** | already logs, but **without** `exc_info` | **119** | mechanical-ish, see §2.3 |
| **E** | no logging, no re-raise — swallows with a side effect (returns a default, builds a `ToolResult`) | **44** | no — needs a per-site decision |

**There are no stale waivers.** Every one of the 197 is load-bearing: stripping
all BLE001-only directives and re-running ruff re-flagged **113 of 113**.

Distribution: `inner_loop` 146, `runtime` 19, `skills` 10, `memory` 8,
`cli.py` 6, `telemetry` 3, remainder 5.

### 2.2 What actually satisfies the rule

BLE001's documentation gives two exemptions:

* the exception is **re-raised**;
* it is **logged with `exc_info` enabled** — *"a common pattern for propagating
  exception traces."*

The repo's 37 clean sites use exactly these: 33 re-raise, 4 log with
`exc_info` (`output.py:212`, `cli.py:2617`, and the two `hooks/base.py` sites
converted during S7).

### 2.3 The trap that makes category B **not** a find-and-replace

Converting one real B site (`state.py:288`, `logger.warning(..., exc_info=True)`)
was clean on ruff 0.16 and **still flagged on 0.15.18**.

Cause: v0.15.18 grants the exemption only for `.error` / `.critical` /
`.exception`; ruff **≥0.16 widened it to all log levels** (ruff
[#21889](https://github.com/astral-sh/ruff/issues/21889)). So a B-site that
logs at `warning` or `debug` needs *either* a newer ruff *or* a level change to
`error` — and **raising a log level is a product decision**, not lint
housekeeping. A `debug` line promoted to `error` changes what an operator sees
at default verbosity.

This is now partly moot: S7 unpinned ruff (`repo: local`, `language: system`)
so one version governs, and the lock resolves 0.16.0. But it must be stated,
because it means **B is only mechanical while the floor stays ≥0.16**.

### 2.4 Categories A and E are the real work

A (34) and E (44) — 78 sites — swallow without logging anything. For each, the
honest question is not "how do I satisfy the linter" but:

1. can the catch be **narrowed** to the exception actually expected?
2. if not, should the failure be **observable** (log it), and at what level?
3. if it must stay silent, *why* — and does the existing one-line rationale say
   so, or just assert "graceful degradation"?

Spot-checked rationales are frequently boilerplate: `loop.py` carries
`# graceful degradation per Phase 0.5, failure-observable WARNING` on five
sites, two of which log nothing at all — so the comment is inaccurate on its
own terms.

## 3. Non-goals

- **Not** a mass `--fix`. The measured lesson from S6.3 is that an automated
  fix which removes a *waiver* is a policy change.
- **Not** a push to zero. Some broad catches are correct: a `finally`-style
  cleanup, an observability sink, a plugin boundary. The target is that a
  waiver means something again.
- No behaviour change to logging levels **without** naming it as such (§2.3).

## 4. Proposed slices (each independently landable)

| Slice | Scope | Sites | Mechanism |
|---|---|---:|---|
| **W1** | category B in `inner_loop` | ~90 | add `exc_info=True`, drop the waiver; **no level changes** — sites logging below `error` are deferred to W2 |
| **W2** | category B needing a level decision | ~29 | one operator call: promote to `error`, or keep the waiver with an accurate rationale |
| **W3** | category E — swallow with side effect | 44 | per site: narrow the catch, or add a log, or keep with a real rationale |
| **W4** | category A — bare `pass` | 34 | highest-value, hardest: each is a silent failure by construction |
| **W5** | guardrail | — | see §5 |

Order is deliberate: W1 is the largest and lowest-risk, and shrinking the
population makes W3/W4 reviewable.

## 5. The guardrail matters more than the count

Reducing 197 → 80 achieves nothing durable if the next slice adds 20 more. A
ratchet is the mechanism that holds:

```text
scripts/check_ble_waiver_budget.py  (proposed)
  count `# noqa: ...BLE001` in src/fa
  fail if the count EXCEEDS a committed budget
  budget only ever ratchets down; lowering it is a normal PR
```

Precedent in this repo: `check_log_kind_contract.py`'s `KNOWN_DORMANT_KINDS`
and `test_session_manifest_guards.py`'s `KNOWN_UNTESTED_CODES` both use the
"allowlist with a written reason, guarded by a test" shape. A budget file is
the same idea at scale, and it is the only part of this plan that prevents
regression.

**Recommendation:** land W5 *first*, pinned at today's 197. It is small, it
stops the bleeding immediately, and every later slice becomes a visible
ratchet-down.

## 6. Open question

### Q30 — is this worth doing, and at what granularity?

* **(a) Full programme W1–W5.** Honest policy, ~197 sites, multi-session.
* **(b) Guardrail only (W5).** Pin the budget at 197 and require new code to
  justify additions. Cheapest; leaves the existing debt.
* **(c) W5 + W1.** Ratchet plus the one mechanical batch — halves the count for
  roughly one session of work.
* **(d) Nothing; close this plan.** Defensible if the operator's view is that
  the waivers are all genuine and the policy text should change instead.

**Recommendation: (c).** W5 alone leaves a rule that everybody waives; the full
programme is hard to justify against feature work. (c) buys the durable part
(the ratchet) plus the batch where the fix is known-correct, and leaves A/E —
the sites needing real judgement — as a tracked, shrinking backlog.

Whichever is chosen, **§2.3's caveat is binding**: no site's log level moves
without that being called out as a product change.

## 7. Definition of Done (for whichever slices run)

- [ ] every converted site verified on the **pinned** ruff, not just the local one;
- [ ] no site's log level changed silently — level changes listed in the PR note;
- [ ] `just check` green: pytest+cov ≥ 80, bare `mypy`, `pyrefly`, `ruff`,
      `pylint src/fa` 10.00/10, `deptry`, contract scripts;
- [ ] the waiver count **decreases** and the budget file is lowered in the same PR;
- [ ] a negative proof per batch: re-adding one waiver-free catch without its
      `exc_info` must fail the gate;
- [ ] no test asserts on a log level that this work changed (grep before landing).
