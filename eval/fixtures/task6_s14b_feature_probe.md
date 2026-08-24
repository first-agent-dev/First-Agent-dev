---
task_id: task6_s14b_feature_probe
role: coder
scoring_kind: llm_judge
goal_lens: verify the S14b.2/S15/S16/S17 feature pipeline end-to-end on the live harness
---

# Live feature probe — S14b.2 / S15 / S16 / S17 (agent-run surface)

You are running INSIDE the First-Agent harness. Your job is to exercise the
features this pipeline shipped and REPORT the recorded outputs. Do not fix
anything; findings go in your final message.

Run the tools in this order and record each result:

## 1. Discovery surface (S14b.1 / S14 regression sanity)

- `fs_search(query="iteration_cap", output_mode="files", limit=5)` — expect files
  including `src/fa/inner_loop/loop.py`; record the paths.
- `fs_blackboard_query(type="skill")` — expect rows with titles (≥9); record the count.

## 2. Call-graph navigation (S16)

- `fs_reach(symbol="classify_batches", direction="down", depth=1)` — expect
  `resolved_to.path` endswith `src/fa/inner_loop/loop.py` and a non-empty callee list.
- `fs_reach(symbol="os.path.join", direction="up", depth=1)` — expect
  `resolved_to=null` (cross-module symbols are not indexed); candidates may be EMPTY
  (no symbol ends with that suffix) — record what it actually returns.
- `fs_reach(symbol="§I-S16-1", direction="down", depth=1)` — expect a
  `doc_anchor` resolved at `src/fa/memory/structural_index.py` (S17).

## 3. Exploration metrics (S15)

- `fs_exploration_metrics()` — expect `n_reads > 0` (this session's reads are
  tracked), `n_searches >= 1`, `acc_at_k` values null (no gold declared) with a
  note explaining why.

## 4. Iteration-cap observability (S14b.2) — self-observation

You cannot observe your own cap from inside one turn, so verify the SUBSTRATE
instead: check YOUR TOOL-RESULT HISTORY (not console output — you cannot see
the operator's console) for any synthetic failure whose error reason contains
"iteration limit". If none appear, report that the cap was not hit this
session (expected under the 99-per-turn testing default).

## Final report format

```text
S14B-PROBE: <pass|fail> <note>
S16-PROBE: <pass|fail> <note>
S15-PROBE: <pass|fail> <note>
S17-PROBE: <pass|fail> <note>
CAP-PROBE: <observed|not-observed> <note>
```

The operator diffing this output against the plan's oracle table decides
pass/fail per probe; your notes must quote the actual returned values.
