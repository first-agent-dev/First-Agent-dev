# S18 Live Verification — Validator Checklist

**You run commands on live server, I validate outputs.**

## What S18 is
- Sandbox already proved pipeline (3k tests). Nothing ran on LIVE deployment yet.
- S18 converts every shipped feature to live evidence: deterministic probes = hard gates, agent runs = soft signals.
- No source edits. Findings → I-63+ ledger, fix nothing.

## Goals mapped to steps

| Goal | Feature | Step | Type | Oracle (must match exactly) |
|------|---------|------|------|-----------------------------|
| G1 | identity / no drift | C0 | deterministic | revision recorded, `iteration_cap` grep ≥1, `structural_index.py` + `fs_reach.py` exist, `git archive` copy at `/tmp/s18-repo-ws`, config snapshot saved |
| G2 | S14b.2 cap signal | C1 | deterministic | smoke with `max_iterations:2` → 1 run_stopped row: point=iteration_cap, used=2, limit=2, profile=coder, reason starts `iteration_cap:` contains `used 2 of 2`; smoke exit 0 |
| G2 | renderer + stats consumers | C1b | deterministic | renderer line contains `iteration cap reached` + `used 2 of 2`; stats parse_session ok=True, stop_reason startswith `iteration_cap:` |
| G2 | exact-fit silence | C2a | deterministic | no override, 3 calls vs global 6 → cap_rows=0, tool_result_rows=3, exit 0 |
| G2 | role-key no-leak | C2b | deterministic | override `max_iterations_coder:2` only → smoke still uses global 6 → cap_rows=0, tool_result_rows=3 |
| G2 | stub keys ignored | C3 | deterministic | global 3 + researcher 2 → 3 calls exact fit → cap_rows=0, tool_result_rows=3 |
| G3 | file_read + surfaced_by | C4 | deterministic | `[('a.txt', 2, 'search_result', None, None)]` turn=2 second batch |
| G3 | metrics tool | C5 | deterministic | n_reads=1, n_searches=1, ctx_efficiency=0.0, acc_at_k all None, note contains `declare gold files` |
| G4 | fs_reach down | C6a | deterministic | `classify_batches` down depth1 → resolved path `src/fa/inner_loop/loop.py`, callees non-empty, every distance==1 (true BFS) |
| G4 | fs_reach up | C6b | deterministic | `classify_batches` up depth2 → callers == `[('run_session',1)]` ONLY — drive_session absent is CORRECT (cross-file unresolved in v1) |
| G4 | fs_reach unresolved | C6c | deterministic | `os.path.join` up → resolved_to=null, candidates=[] |
| G4 | fs_reach unavailable | C6d | deterministic | app.js workspace → status=unavailable, detected_languages contains `.js` |
| G5 | S17 anchors | C7 | deterministic | 6 seeds resolve kind=doc_anchor at pinned paths, prints `ALL SIX ANCHORS RESOLVED` |
| G4/G6 | fs_search live regression | C8a | deterministic | fs_search `iteration_cap` files → contains `src/fa/inner_loop/loop.py` |
| G4 | artifact index S14.0 closure | C8b | deterministic | scanned>=9, query type=skill >=9 rows with title, all 7 types non-empty |
| G6 | quiet contract | C8c | deterministic | quiet mode stdout == final text only, stdout_bytes recorded |
| G6 | agent fixture e2e | C9 | soft | console has 5 lines S14B/S16/S15/S17/CAP-PROBE, tool_call counts show fs_search, fs_reach, fs_exploration_metrics, fs_blackboard_query each ≥1 |
| G7 | wiring + corpus | C10 | deterministic | 4 profiles contain fs_reach+fs_exploration_metrics, verifier contains neither, TOOL_NAMES superset, coder corpus ==17 names including fs_search, fs_reach, fs_exploration_metrics, pr_prepare |

## Your execution order (copy/paste blocks from plan)

All blocks already `bash -n` checked and python-probe verified in sandbox.

1. **C0** constants, identity, workspace (`git archive`), config snapshot → record EVIDENCE path, revision, grep count, archive listing, snapshot bytes
2. **C1** cap matrix + renderer + stats + agent half → record smoke exit, projection txt, consumers txt, agent console + stats json
3. **C2a/C2b** exact-fit + no-leak → record cap_rows, tool_result_rows, exits
4. **C3** stub ignored → record cap_rows, tool_result_rows
5. **C4-C5** telemetry + metrics single python probe → record `CT-S18-4/5 PASS` + oracle line
6. **C6-C7** fs_reach + anchors → record 6a-6d lines + `ALL SIX ANCHORS RESOLVED`
7. **C8** regression (fs_search live + artifact smoke + quiet) → record PASS markers, quiet stdout/stderr bytes
8. **C9** agent fixture `--max-turns 20` (Q-S18-1 resolved) → record console + tool counts
9. **C10** wiring/corpus + config restore byte-identical + git status clean + evidence pack SHA256

## What to give me per step

For each step, paste:
```
STEP=Cx
EXIT=...
STDOUT:
<exact output>
STDERR:
<if any>
ORACLE MATCH: yes/no + note
```

For C1-C10 I need:
- exit codes (PIPESTATUS captured in plan)
- projection files content (c1-cap-projection.txt, c1-consumers.txt, c2a.txt, etc.)
- agent consoles
- final tar.gz path + SHA256SUMS

## STOP RULE
If deterministic probe oracle mismatch → record exact output, continue only INDEPENDENT steps (S7 precedent). Don't fix.

## After you run
I will:
- diff actual vs oracle per CT-S18-1..10
- classify PASS/FAIL per contract
- produce findings ledger I-63+ if any mismatch
- confirm DoD: all deterministic PASS markers, corpus 17, config byte-identical, deployment git status empty, archive + sha256 recorded

Ready when you are — start with C0 and paste output.
