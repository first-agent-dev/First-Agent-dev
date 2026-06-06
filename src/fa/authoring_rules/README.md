# `fa.authoring_rules` — Level-1 rule packs (ADR-11)

Level-1 holds the **allowlisted** semantic rules that the frozen Level-0
kernel ([`fa.authoring_tcb`](../authoring_tcb.py)) dispatches. This file is
part of the **I-BOOT** authoring read-set (ADR-11-I8): read it before
adding or changing an authoring rule.

## Contract

- A rule is any callable matching the `Rule` protocol
  (`__call__(context: RuleContext) -> Sequence[RuleResult]`), exported from
  [`fa.authoring_tcb`](../authoring_tcb.py).
- Rules MUST be deterministic and side-effect free. Structural Python
  checks MUST use `ast` (ADR-11-I4), never regex.
- Rules **never** own dispatch, hashing, or output — the kernel does that.
- A rule is dispatched only if it is listed in the static `RULE_ALLOWLIST`
  in [`__init__.py`](./__init__.py). There is **no dynamic discovery**.
- Shared file-iteration + parse + scope-filter logic lives in the
  internal-only [`_scan.py`](./_scan.py) module to keep each rule pack
  focused on its own diagnostic logic and to satisfy the strict
  `duplicate-code` (R0801) gate.

## Diagnostic-code namespace (frozen, append-only — ADR-11-I2)

```text
FA-AUTHORING-V<N>-<SLUG>
```

- `V0` is **reserved** for the Level-0 kernel's own fail-closed
  diagnostics (`FA-AUTHORING-V0-MANIFEST`, `-SNAPSHOT`, `-RULE-CRASH`).
- `V1..V14` are the Level-1 catch-corpus vectors (see ADR-11 §Verification
  `F-1..F-10`). A `V<N>` is **never re-used** for a different rule.

### Codes claimed by the active allowlist

| Code | Severity | Source | Rule callable |
| :--- | :--- | :--- | :--- |
| `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` | HARD-BLOCK | F-2, F-7 | `EXPORTS_COMPLETENESS` (`exports.py`) |
| `FA-AUTHORING-V4-PYTEST-SKIP` | HARD-BLOCK | ADR-11-I5 §HARD-BLOCK #1 | `TEST_SEMANTIC_DECAY` (`tests.py`) |
| `FA-AUTHORING-V4-NON-STRICT-XFAIL` | HARD-BLOCK | ADR-11-I5 §HARD-BLOCK #2 | `TEST_SEMANTIC_DECAY` (`tests.py`) |
| `FA-AUTHORING-V4-FOCUS-MARKER` | HARD-BLOCK | ADR-11-I5 §HARD-BLOCK #3 | `TEST_SEMANTIC_DECAY` (`tests.py`) |
| `FA-AUTHORING-V11-PLACEHOLDER-ASSERT` | HARD-BLOCK | ADR-11-I5 §HARD-BLOCK #4, F-9 | `PLACEHOLDER_ASSERTION` (`tests.py`) |

## Severity lifecycle (ADR-11-I2)

`HARD-BLOCK` fails CI; `ADVISORY` (must carry `expires_on`) and `INFO` do
not. A rule is promoted `ADVISORY -> HARD-BLOCK` only after it catches its
`catch-corpus/` fixture **and** measures a false-positive rate `< 1 %` on
`fp-corpus/` (ADR-11 §Verification). The corpora land in PR 4. PR-2 rules
ship directly as `HARD-BLOCK` because they are the §9.3-listed items with
a structurally near-zero false-positive rate (verified empirically on the
live repo: zero findings on PR-2 merge after one F-7-class fix to
`hooks/blockers.py` exporting `TimeSource`).

## Rollout (blueprint Appendix B)

| PR | Rules |
| :--- | :--- |
| PR 1 | none — kernel skeleton + empty allowlist (closed) |
| **PR 2 (this)** | `exports.py` (V2), `tests.py` (V4 family + V11) |
| PR 3 | `parity.py` (V3), `docs.py` (V5) |
| PR 4 | `seam.py` (V6) + catch/fp corpora |
| PR 5 | `messages.py` (V12) + advisory tuning |
| later | `references.py` (V10), `ssot.py` (V7), `trailers.py` (V14) |
