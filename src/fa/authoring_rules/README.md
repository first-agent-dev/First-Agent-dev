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
 
## Diagnostic-code namespace (frozen, append-only — ADR-11-I2)
 
```text
FA-AUTHORING-V<N>-<SLUG>
```
 
- `V0` is **reserved** for the Level-0 kernel's own fail-closed
  diagnostics (`FA-AUTHORING-V0-MANIFEST`, `-SNAPSHOT`, `-RULE-CRASH`).
- `V1..V14` are the Level-1 catch-corpus vectors (see ADR-11 §Verification
  `F-1..F-10`). A `V<N>` is **never re-used** for a different rule.
 
## Severity lifecycle (ADR-11-I2)
 
`HARD-BLOCK` fails CI; `ADVISORY` (must carry `expires_on`) and `INFO` do
not. A rule is promoted `ADVISORY -> HARD-BLOCK` only after it catches its
`catch-corpus/` fixture **and** measures a false-positive rate `< 1 %` on
`fp-corpus/` (ADR-11 §Verification). The corpora land in PR 4.
 
## Rollout (blueprint Appendix B)
 
| PR | Rules |
| :--- | :--- |
| PR 1 (this) | none — kernel skeleton + empty allowlist |
| PR 2 | `exports.py` (V2), `tests.py` (V4/V10/V11) |
| PR 3 | `parity.py` (V3), `docs.py` (V5) |
| PR 4 | `seam.py` (V6) + catch/fp corpora |
| PR 5 | `messages.py` (V12) + advisory tuning |