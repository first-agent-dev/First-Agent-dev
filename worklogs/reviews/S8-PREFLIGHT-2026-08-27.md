# S8 preflight — Full E3 cost model + calibration (Layer 3)

Branch `New-main-role-chat-and-complexity-aware-workflow-execution`, base `d076beb`
(user's squash-merge of S4b–S7; tree verified equal to my local `1cd6876` except two
cosmetic ruff reflows the user applied — the M8 `ast.Name` assertion is intact).

## 1. Current source-verified behaviour (read, not assumed)

| Fact | Verified at | Value |
|---|---|---|
| `acrr.py` surface | `src/fa/inner_loop/acrr.py` (58 lines) | only `compute_acrr_proxy(files_read, files_changed)`; `__all__ = ["compute_acrr_proxy"]` |
| Telemetry discards paths | `global_history.py:372-373` | returns `len(read_paths)` / `len(changed_paths)`; **the path strings never leave the function** |
| Paths are raw recorded params | `global_history.py:334-342` | `params["path"]` as recorded — may be absolute **or** workspace-relative |
| `workspace_root` reaches the builder | `global_history.py:385` | yes — `build_export_row(..., workspace_root=...)` |
| Proxy call site | `global_history.py:444` | `row["acrr_proxy"] = compute_acrr_proxy(...)` |
| S5 migration pattern | `global_history.py:189-196` | `PRAGMA table_info(runs)` → conditional `ALTER TABLE ADD COLUMN` |
| Display site | `cli.py:3006-3007` | `r.get("acrr_proxy")`, `"n/a (no files changed)"` |
| Blackboard precedent | `cli.py:1858-1879` | S3.5 `BlackboardEntry.create(...)` inside `try/except`, best-effort |
| Export call site | `cli.py:2159` | `state` **is** in scope ⇒ blackboard write belongs here |
| stats stream split | `cli.py` `_cmd_stats_global_history` | json→stdout, human→stderr |
| sqlite | runtime | 3.46.1 (`ALTER TABLE ... RENAME COLUMN` available, needs ≥3.25) |

## 2. Contracts and gap IDs addressed

- **CT11** — `compute_cost` / `compute_cost_floor` / `compute_acrr` (E3 Eq. 1 + Eq. 3).
- **CT12** — calibration projection: 3 new columns, rename, blackboard, `--calibration`.
- **G9** — post-run calibration observable (operator Q22: no labelled set; calibration instead).
- Depends-on S5, S7 (both shipped and merged).

## 3. Files allowed to change (from EDIT PACKET E8)

```
src/fa/inner_loop/acrr.py            EDIT
src/fa/inner_loop/global_history.py  EDIT
src/fa/cli.py                        EDIT (calibration view + rename fallout only)
tests/test_e3_cost_model.py          NEW
tests/test_acrr.py                   EDIT (rename fallout)
```

## 4. Deviations from the written plan (plan text vs. verified reality)

**D-S8-1 — the rename is NOT free.** Plan step 5 and the research note both say
`acrr_proxy` has "0 occurrences on main". Verified today: **36 occurrences across 4
files**, and it is a **shipped DB column** (S5 landed after that text was written).
So the rename additionally needs a *column* migration, which the plan does not
mention. Handled as an additive+backfill migration (see D-S8-2), not a bare rename.

**D-S8-2 — RESOLVED 2026-08-27 (operator correction): a real `RENAME COLUMN`.**
Originally I kept a dual-column compatibility layer, reasoning that an older `fa`
might read `acrr_proxy` from a shared `~/.fa/global_history.db`. The operator
corrected the premise: the only live database is this host's, holding two throwaway
`fa`-test rows. Verified before acting — `~/.fa/global_history.db` had exactly 2 rows,
both `exit_code=2` with zero telemetry and `acrr_proxy = NULL`; every other
`global_history.db` on the host is a pytest temp file. There is no external reader and
no data worth preserving, so the compatibility layer protected nothing and would have
kept the old identifier alive forever.

Now: `ALTER TABLE runs RENAME COLUMN acrr_proxy TO read_amplification` (sqlite >= 3.25;
host has 3.46.1). It carries S5 values across in place, needs no backfill that could
disagree with its source, and leaves exactly one name behind. The rename runs BEFORE
the add-missing-columns loop — reversed, that loop would create an empty
`read_amplification`, the guard would then be false, and every S5 value would be
stranded in an orphaned column. Mutation M16 pins that ordering.

Executed against the real live DB: `acrr_proxy` gone, `read_amplification` present,
both rows intact.

**D-S8-3 — weights could not be "fitted against real rows" (plan step 4).** The live
`~/.fa/global_history.db` holds exactly **2 rows, both degenerate** (`exit_code=2`,
zero tokens/tools/files). There is nothing to fit. Rather than invent a fit or fake
data, weights are **derived from a measured property of this repo** and recorded with
the derivation:

- measured: `src/*.py` median = 7234 B ⇒ **1808 tokens**; mean 11577 B; max 140572 B.
- confirmed the plan's claim: paper weights `(1.0, 0.02, 0.5, 1.5)` put the file axis
  at **0.43–2.17 %** of C on real change-sets — numerically erased.
- anchor (paper's words: one irrelevant file is *the canonical unit of redundancy*):
  keep `δ = 1.5`; set `β = 0.5·δ / 1808 = 0.000415` so a median file's *token* cost is
  half its *file* cost; `γ = 0.1`; `α = 1.0` but **excluded from the floor**.
- resulting floor composition — file axis 9–59 %, tokens 29–89 %: every axis material.
- robustness (E3 §7.5 replication, 4000 random weightings over β∈[1e-5,1e-1],
  γ∈[1e-2,10], δ∈[0.1,16]): wasteful run ranked worse than lean in **4000/4000 =
  100 %**. Ordering is weight-insensitive, so configurability matters more than the
  exact values — exactly the paper's conclusion.

## 5. Blocking questions

None. Q20–Q23 are answered and the S8 packet is unambiguous. D-S8-1/2/3 are recorded
deviations, not open policy: each keeps the plan's *intent* where its *text* was
written against a stale tree. Any new policy choice found mid-implementation stops
work and is promoted to a Q#.
