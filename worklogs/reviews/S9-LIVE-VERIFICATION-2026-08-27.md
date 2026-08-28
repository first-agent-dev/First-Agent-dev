# S9 — Live verification sheet (S7 routing + S8 cost model)

**Plan:** `worklogs/implementation-plans/PLAN-ADDENDUM-deterministic-routing-S7-S9.md` §S9 (EDIT PACKET E9)
**Traces-to:** G7–G10 · **Depends-on:** S7, S8 · **Target liveness:** L3 evidence
**Date:** 2026-08-27 · **Base:** `d076beb` + S8 commits

---

## How to use this sheet

Every block below is **copy/paste-ready**. Run it on the live server, paste the
output back. Rows are ordered so that a failure early tells you not to bother
with the rest.

**Discipline (E9 "Do-not"):** this sheet contains **no expected output**. Each
command prints its own PASS/FAIL against an oracle computed at runtime, so what
you paste back is measurement, not confirmation of a guess.

**Safety properties of every command here:**

| Property | How it is enforced |
|---|---|
| Never writes to your real `~/.fa/global_history.db` | DB rows go to a `mktemp -d` `FA_STATE_ROOT` |
| Never edits your real `~/.fa/config.yaml` | Toggle rows parse temp text through the real loader |
| Never leaves temp dirs behind | `trap ... EXIT` in every shell block |
| Cannot silently "pass" on error | Every block ends with an explicit exit code |
| Read-only until Row 8 | Rows 0–7 mutate nothing in the repo |

**Exit-code convention:** `0` = all assertions in that row passed.
Non-zero = at least one failed; the failing labels are listed in the RESULT line.

> **Prerequisite (confirmed with operator):** `~/.fa/models.yaml` has a
> top-level `chat:` key. Row 0 verifies this. Without it, rows 8+ fail with
> `fa run: role 'chat' not found`.

---

## Row 0 — Preflight

Confirms the host can run the rest of the sheet. Read-only.

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
cat > /tmp/s9_row0.sh <<'SHEOF'
#!/usr/bin/env bash
set -uo pipefail
echo "S9-0 PREFLIGHT"
echo
echo "-- versions --"
fa --version 2>&1 | head -1
python -c 'import sys; print("python", sys.version.split()[0])'
python -c 'import sqlite3; print("sqlite", sqlite3.sqlite_version)'
git --version

echo
echo "-- repo state --"
git rev-parse --short HEAD 2>/dev/null || echo "  (not a git repo)"
git rev-parse --abbrev-ref HEAD 2>/dev/null
echo "  dirty files: $(git status --porcelain 2>/dev/null | wc -l)"

echo
echo "-- S7/S8 code present? --"
python - <<'PY'
import importlib
for m, attr in [("fa.inner_loop.routing", "should_withhold_write_tools"),
                ("fa.inner_loop.acrr", "compute_cost_floor"),
                ("fa.inner_loop.tools.workflow_tool", None)]:
    try:
        mod = importlib.import_module(m)
        ok = (attr is None) or hasattr(mod, attr)
        print(f"  [{'OK ' if ok else 'MISSING'}] {m}")
    except Exception as exc:
        print(f"  [MISSING] {m} -- {type(exc).__name__}: {exc}")
PY

echo
echo "-- provider config (REQUIRED for live rows 8+) --"
CFG="${HOME}/.fa/models.yaml"
if [ -f "$CFG" ]; then
  echo "  found: $CFG"
  if grep -qE '^\s*chat\s*:' "$CFG"; then
    echo "  [OK ] top-level 'chat:' key present -> 'fa run --role chat' is runnable"
  else
    echo "  [BLOCK] no top-level 'chat:' key. Live rows will fail with:"
    echo "          \"fa run: role 'chat' not found in $CFG\""
  fi
  echo "  roles declared: $(grep -E '^[a-z_-]+:' "$CFG" | tr -d ': ' | tr '\n' ' ')"
else
  echo "  [BLOCK] $CFG not found. Live rows cannot run."
fi

echo
echo "-- toggle config --"
TCFG="${HOME}/.fa/config.yaml"
if [ -f "$TCFG" ]; then
  echo "  found: $TCFG"
  grep -nE 'runtime_limits|chat_escalation_gate' "$TCFG" \
    || echo "  (no chat_escalation_gate key -> defaults to TRUE/enabled)"
else
  echo "  $TCFG absent -> chat_escalation_gate defaults to TRUE (enabled)"
fi

echo
echo "-- git remote + push capability --"
git remote -v 2>/dev/null | head -2 || echo "  (no remote configured)"
command -v gh >/dev/null 2>&1 \
  && echo "  gh CLI: $(gh --version 2>&1 | head -1)" \
  || echo "  gh CLI: NOT INSTALLED (PR row falls back to a compare URL)"
SHEOF
bash /tmp/s9_row0.sh; echo "EXIT=$?"
```

**Paste:** whole output.
**Blocks the sheet if:** any `[MISSING]`, or `[BLOCK]` on `models.yaml`.

---

## Row 1 — Wiring: module surface and constants

Cheapest possible failure detector. If a constant drifted, everything downstream
is measuring the wrong thing.

```bash
cat > /tmp/s9_row1.py <<'PYEOF'
import sys
FAILURES = []
def check(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -- {detail}" if detail else ""))
    if not cond: FAILURES.append(label)

try:
    from fa.inner_loop import acrr
    from fa.inner_loop.routing import (
        GATE_MIN_CONFIDENCE, TRIPWIRE_READ_LIMIT, TRIPWIRE_CHANGE_LIMIT, WITHHELD_WRITE_TOOLS,
    )
    from fa.inner_loop.acrr import DEFAULT_WEIGHTS, BYTES_PER_TOKEN, compute_read_amplification
except Exception as exc:
    print(f"  [FAIL] import S7/S8 modules -- {type(exc).__name__}: {exc}")
    sys.exit(1)

print("S9-1 WIRING")
check("GATE_MIN_CONFIDENCE == 0.8", GATE_MIN_CONFIDENCE == 0.8, f"got {GATE_MIN_CONFIDENCE}")
check("TRIPWIRE_READ_LIMIT == 10", TRIPWIRE_READ_LIMIT == 10, f"got {TRIPWIRE_READ_LIMIT}")
check("TRIPWIRE_CHANGE_LIMIT == 3", TRIPWIRE_CHANGE_LIMIT == 3, f"got {TRIPWIRE_CHANGE_LIMIT}")
check("WITHHELD_WRITE_TOOLS is the exact 3-set",
      WITHHELD_WRITE_TOOLS == {"fs_write_file", "fs_edit_file", "fs_spawn_subagent"},
      f"got {sorted(WITHHELD_WRITE_TOOLS)}")
check("invoke_workflow NOT withheld (escalation stays reachable)",
      "invoke_workflow" not in WITHHELD_WRITE_TOOLS)
check("weights are the fitted values",
      (DEFAULT_WEIGHTS.alpha, DEFAULT_WEIGHTS.beta, DEFAULT_WEIGHTS.gamma, DEFAULT_WEIGHTS.delta)
      == (1.0, 0.000415, 0.1, 1.5), f"got {DEFAULT_WEIGHTS}")
check("BYTES_PER_TOKEN == 4", BYTES_PER_TOKEN == 4)
check("compute_acrr_proxy is GONE (S8 rename complete)", not hasattr(acrr, "compute_acrr_proxy"))
check("compute_read_amplification present", callable(compute_read_amplification))
print(f"\nRESULT: {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
PYEOF
python /tmp/s9_row1.py; echo "EXIT=$?"
```

---

## Row 2 — Gate + tripwire decision matrix

The full truth table, including the guards that mutation testing showed were
easy to break silently (role guard, toggle, confidence threshold).

```bash
cat > /tmp/s9_row2.py <<'PYEOF'
import sys
from fa.inner_loop.routing import (
    should_withhold_write_tools, check_scope_tripwire,
    TRIPWIRE_READ_LIMIT, TRIPWIRE_CHANGE_LIMIT,
)
from fa.inner_loop.scope_estimator import estimate_scope

FAIL = []
def check(label, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got={got!r} want={want!r}")
    if not ok: FAIL.append(label)

class P:
    def __init__(s, mode, conf): s.recommended_mode, s.confidence = mode, conf

print("S9-2A GATE MATRIX (mode x confidence x role x toggle)")
check("workflow_linear @0.8, chat, ON  -> WITHHOLD",
      should_withhold_write_tools(P("workflow_linear", 0.8), role="chat", gate_enabled=True), True)
check("workflow_linear @0.6, chat, ON  -> allow (below threshold)",
      should_withhold_write_tools(P("workflow_linear", 0.6), role="chat", gate_enabled=True), False)
check("chat_direct @0.8,     chat, ON  -> allow (wrong mode)",
      should_withhold_write_tools(P("chat_direct", 0.8), role="chat", gate_enabled=True), False)
check("workflow_linear @0.8, chat, OFF -> allow (operator toggle)",
      should_withhold_write_tools(P("workflow_linear", 0.8), role="chat", gate_enabled=False), False)
check("workflow_linear @0.8, CODER, ON -> allow (role guard)",
      should_withhold_write_tools(P("workflow_linear", 0.8), role="coder", gate_enabled=True), False)
check("workflow_linear @0.8, EVAL,  ON -> allow (role guard)",
      should_withhold_write_tools(P("workflow_linear", 0.8), role="eval", gate_enabled=True), False)
check("no estimate (None) -> allow (fail-open)",
      should_withhold_write_tools(None, role="chat", gate_enabled=True), False)

print(f"\nS9-2B TRIPWIRE BOUNDARIES (reads>{TRIPWIRE_READ_LIMIT}, changes>{TRIPWIRE_CHANGE_LIMIT})")
def fires(r, c, mode="chat_direct"):
    return check_scope_tripwire(files_read=r, files_changed=c, recommended_mode=mode) is not None
check(f"reads={TRIPWIRE_READ_LIMIT} (at limit) -> silent", fires(TRIPWIRE_READ_LIMIT, 0), False)
check(f"reads={TRIPWIRE_READ_LIMIT+1} (over)   -> FIRES",  fires(TRIPWIRE_READ_LIMIT+1, 0), True)
check(f"changes={TRIPWIRE_CHANGE_LIMIT} (at limit) -> silent", fires(0, TRIPWIRE_CHANGE_LIMIT), False)
check(f"changes={TRIPWIRE_CHANGE_LIMIT+1} (over)   -> FIRES",  fires(0, TRIPWIRE_CHANGE_LIMIT+1), True)
check("zero activity -> silent", fires(0, 0), False)
check("already workflow_linear -> silent (no point nagging)", fires(99, 99, "workflow_linear"), False)

print("\nS9-2C 'DOES NOT INTERFERE WHEN SIMPLE' (the other half of the feature)")
for label, t in [("one-line README edit", "Add a single line to README.md"),
                 ("typo fix", "Fix a typo in one docstring")]:
    s = estimate_scope(t)
    g = should_withhold_write_tools(s, role="chat", gate_enabled=True)
    print(f"  {label:<22} mode={s.recommended_mode:<14} conf={s.confidence}  gated={g}")
    check(f"{label}: NOT gated", g, False)

print(f"\nRESULT: {'ALL PASS' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
PYEOF
python /tmp/s9_row2.py; echo "EXIT=$?"
```

---

## Row 3 — E3 cost model arithmetic + hostile inputs

Hand-computed oracles for Eq. 1 and Eq. 3, then the paths that must not crash or
leak: deleted files, paths outside the workspace, `../` traversal.

```bash
cat > /tmp/s9_row3.py <<'PYEOF'
import sys, tempfile
from pathlib import Path
from fa.inner_loop.acrr import (
    CostWeights, compute_cost, compute_cost_floor, compute_acrr, compute_read_amplification,
)
FAIL = []
def check(label, got, want):
    ok = (got == want)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got={got!r} want={want!r}")
    if not ok: FAIL.append(label)

W = CostWeights(alpha=1.0, beta=0.02, gamma=0.5, delta=1.5)  # round numbers, hand-checkable

print("S9-3A EQ.1  C = a*T_lat + b*N_tok + g*N_tool + d*N_file")
check("1.0*10 + 0.02*100 + 0.5*4 + 1.5*2 = 17.0", compute_cost(10.0, 100, 4, 2, weights=W), 17.0)
check("file axis contributes exactly delta",
      compute_cost(0,0,0,1,weights=W) - compute_cost(0,0,0,0,weights=W), 1.5)

print("\nS9-3B FLOOR (must be deterministic: latency excluded)")
ws = Path(tempfile.mkdtemp()); (ws/"a.py").write_bytes(b"x"*400)   # 400B -> 100 tokens
floor = compute_cost_floor(["a.py"], ws, 50, weights=W)
check("0.02*(100+50) + 0.5*(2*1+1) + 1.5*1 = 6.0", floor, 6.0)
check("alpha cannot move the floor",
      compute_cost_floor(["a.py"], ws, 50, weights=CostWeights(9999.0, 0.02, 0.5, 1.5)), floor)
check("absolute path == relative path", compute_cost_floor([str(ws/"a.py")], ws, 50, weights=W), floor)
check("duplicate paths collapse", compute_cost_floor(["a.py","a.py"], ws, 50, weights=W), floor)

print("\nS9-3C HOSTILE INPUTS (no crash, no leak)")
check("deleted file -> 0 tokens, still counts file+tools",
      compute_cost_floor(["nope.py"], ws, 50, weights=W), 0.02*50 + 0.5*3 + 1.5*1)
outside = Path(tempfile.mkdtemp())/"secret.txt"; outside.write_bytes(b"y"*80000)
check("path OUTSIDE workspace -> 0 tokens (never statted)",
      compute_cost_floor([str(outside)], ws, 0, weights=W), 0.5*3 + 1.5*1)
check("../ traversal -> 0 tokens",
      compute_cost_floor(["../../../etc/passwd"], ws, 0, weights=W), 0.5*3 + 1.5*1)
check("empty change-set -> beta*out only", compute_cost_floor([], ws, 100, weights=W), 0.02*100)

print("\nS9-3D EQ.3 ACRR IDENTITIES")
check("actual == floor -> 0.0 (optimally lean)", compute_acrr(10.0, 10.0), 0.0)
check("5x floor -> 4.0", compute_acrr(50.0, 10.0), 4.0)
check("floor 0 -> None (undefined, NOT 0.0)", compute_acrr(5.0, 0.0), None)
check("sub-floor NOT clamped (modelling signal)", compute_acrr(5.0, 10.0), -0.5)
check("read_amplification 20/2 = 10.0", compute_read_amplification(20, 2), 10.0)
check("read_amplification x/0 -> None", compute_read_amplification(10, 0), None)

print("\nS9-3E LOUD FAILURE ON NONSENSE")
for label, fn in [("compute_cost negative", lambda: compute_cost(-1,0,0,0)),
                  ("floor negative output_tokens", lambda: compute_cost_floor([], ws, -1)),
                  ("read_amplification negative", lambda: compute_read_amplification(-1, 1))]:
    try:
        fn(); print(f"  [FAIL] {label}: no ValueError raised"); FAIL.append(label)
    except ValueError as e:
        print(f"  [PASS] {label}: ValueError({str(e)[:44]}...)")

print(f"\nRESULT: {'ALL PASS' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
PYEOF
python /tmp/s9_row3.py; echo "EXIT=$?"
```

---

## Row 4 — Projection: migration, rename, NULL semantics

Runs against a **throwaway** DB. Your real `~/.fa/global_history.db` is never
opened by this row.

```bash
cat > /tmp/s9_row4.py <<'PYEOF'
import sqlite3, sys, tempfile
from pathlib import Path
from fa.inner_loop.global_history import GlobalHistoryStore, build_export_row, _extract_telemetry_from_log
from fa.inner_loop.state import EventLog
from fa.inner_loop.acrr import DEFAULT_WEIGHTS

FAIL = []
def check(label, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got={got!r} want={want!r}")
    if not ok: FAIL.append(label)

PRE_S8 = """CREATE TABLE runs (
 run_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, role TEXT, model TEXT, family TEXT,
 exit_code INTEGER, stop_reason TEXT, turns INTEGER, input_tokens INTEGER, output_tokens INTEGER,
 cache_read_input_tokens INTEGER, cache_creation_input_tokens INTEGER, cache_hit_ratio REAL,
 tool_calls_total INTEGER, tool_calls_breakdown_json TEXT, has_compaction_summary INTEGER,
 workspace_root TEXT, duration_ms INTEGER, scope_estimate_json TEXT, files_read INTEGER,
 files_changed INTEGER, acrr_proxy REAL)"""

print("S9-4A PRE-S8 -> S8 MIGRATION (throwaway DB, real store code)")
db = Path(tempfile.mkdtemp())/"gh.db"
c = sqlite3.connect(db); c.execute(PRE_S8)
c.execute("INSERT INTO runs (run_id, acrr_proxy, files_read, files_changed) VALUES ('legacy',7.5,15,2)")
c.commit(); c.close()
before = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(runs)")}
print(f"  pre-S8: {len(before)} columns, acrr_proxy present={'acrr_proxy' in before}")

store = GlobalHistoryStore(db_path=db)     # migration runs on open
after = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(runs)")}
check("acrr_proxy GONE after rename", "acrr_proxy" in after, False)
check("read_amplification exists", "read_amplification" in after, True)
for col in ("cost_actual", "cost_floor", "acrr"):
    check(f"{col} added", col in after, True)
val = sqlite3.connect(db).execute("SELECT read_amplification FROM runs WHERE run_id='legacy'").fetchone()[0]
check("S5 value SURVIVED the rename", val, 7.5)

print("\nS9-4B IDEMPOTENCE")
for _ in range(3): GlobalHistoryStore(db_path=db)
again = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(runs)")}
check("column set stable across 3 reopens", again == after, True)

print("\nS9-4C NULL SEMANTICS (NULL is not 0.0)")
store.export_run({"run_id":"nulls","acrr":None,"cost_floor":None,"read_amplification":None})
row = [r for r in store.read_all() if r["run_id"]=="nulls"][0]
check("acrr stays NULL", row["acrr"], None)
check("cost_floor stays NULL", row["cost_floor"], None)

print("\nS9-4D REAL PRODUCER PATH (EventLog -> exported row)")
ws = Path(tempfile.mkdtemp())
(ws/"a.py").write_bytes(b"x"*4000); (ws/"b.py").write_bytes(b"y"*2000)
log = EventLog(path=ws/"events.jsonl")
for tool, p in [("fs_read_file","a.py"),("fs_read_file","b.py"),("fs_read_file","a.py"),
                ("fs_edit_file","a.py"),("fs_write_file","b.py")]:
    log.append(actor="agent", kind="tool_call", tool_name=tool, content={"name":tool,"params":{"path":p}})
tel = _extract_telemetry_from_log(log)
check("changed_paths threaded through (the S8 blocker fix)", tel["changed_paths"], ["a.py","b.py"])
check("re-reading a file counts once", tel["files_read"], 2)

class O: exit_code=0; stop_reason="done"; turns=3; final_text=""
r = build_export_row(run_id="r1", outcome=O(), log=log, role="chat", workspace_root=ws, duration_ms=12000)
expected_floor = DEFAULT_WEIGHTS.beta*(6000//4) + DEFAULT_WEIGHTS.gamma*5 + DEFAULT_WEIGHTS.delta*2
check("floor matches hand-computation", round(r["cost_floor"], 9), round(expected_floor, 9))
check("no acrr_proxy key produced", "acrr_proxy" in r, False)
print(f"  measured: read_amplification={r['read_amplification']} cost_actual={r['cost_actual']:.3f} "
      f"cost_floor={r['cost_floor']:.3f} acrr={r['acrr']:.3f}")

print(f"\nRESULT: {'ALL PASS' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
PYEOF
python /tmp/s9_row4.py; echo "EXIT=$?"
```

---

## Row 5 — Safety rails the final task depends on

Proves the bash gate permits what Row 9 needs and denies what it must.
**Also records defect D-S9-1** (see Defects section).

```bash
cat > /tmp/s9_row5.py <<'PYEOF'
import sys
from pathlib import Path
from fa.sandbox import evaluate_bash

FAIL = []
def check(cmd, want_allow, note=""):
    d = evaluate_bash(cmd, workspace_root=Path.cwd())
    ok = d.allow == want_allow
    print(f"  [{'PASS' if ok else 'FAIL'}] allow={str(d.allow):<5} {cmd[:44]:<46} {d.reason[:46]}")
    if not ok: FAIL.append(cmd)

print("S9-5A COMMANDS ROW 9 NEEDS (must be ALLOWED)")
for c in ["git status --porcelain", "git checkout -b s9-live-verification",
          "git add -A", 'git commit -m "fix(docs): repair archive links"',
          "git push -u origin s9-live-verification",
          "python -m pytest tests/test_doc_links.py -q"]:
    check(c, True)

print("\nS9-5B DESTRUCTIVE COMMANDS (must be DENIED)")
for c in ["git push --force origin main", "git push --force-with-lease origin main",
          "rm -rf /", "rm -rf ~", "chmod -R 777 /etc"]:
    check(c, False)

print("\nS9-5C KNOWN GAP D-S9-1 (pre-existing, NOT introduced by S7/S8)")
print("  validators.py:285 tests only `--force` / `--force-with-lease`;")
print("  the short flag `-f` is absent from that token check, so these are ALLOWED.")
print("  The two checks below assert the DEFECT as it stands today, not the desired state:")
for c in ["git push -f origin main", "git push -f origin master"]:
    check(c, True)

print(f"\nRESULT: {'ALL PASS' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
PYEOF
python /tmp/s9_row5.py; echo "EXIT=$?"
```

---

## Row 6 — Calibration view (real CLI, isolated state root)

```bash
cat > /tmp/s9_row6.sh <<'SHEOF'
#!/usr/bin/env bash
set -uo pipefail
export FA_STATE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FA_STATE_ROOT"' EXIT
echo "S9-6 CALIBRATION VIEW  (isolated FA_STATE_ROOT=$FA_STATE_ROOT)"

python - <<'PY'
import json
from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path
s = GlobalHistoryStore(db_path=default_global_history_path())
def row(rid, mode, acrr, ec=0):
    return {"run_id": rid, "exit_code": ec,
            "scope_estimate_json": json.dumps({"recommended_mode": mode}),
            "acrr": acrr, "cost_actual": 10.0, "cost_floor": 5.0,
            "read_amplification": 2.0, "files_read": 4, "files_changed": 2}
for r in [row("a","chat_direct",3.0), row("b","chat_direct",5.0),
          row("c","workflow_linear",0.5), row("d","workflow_linear",1.5),
          row("e","chat_direct",99.0,ec=2)]:
    s.export_run(r)
print("  seeded 5 rows (one FAILED with acrr=99.0 that MUST be excluded)")
PY
[ $? -ne 0 ] && { echo "  [FAIL] seeding failed"; exit 1; }

echo
echo "--- human report (stderr) ---"
fa stats --calibration 2>&1 1>/dev/null

echo
echo "--- JSON (stdout only) ---"
fa stats --calibration --output json 2>/dev/null | tee "$FA_STATE_ROOT/cal.json"

echo
echo "--- oracle checks ---"
python - "$FA_STATE_ROOT/cal.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
by = {e["recommended_mode"]: e for e in d["calibration"]}
ok = True
def chk(label, got, want):
    global ok
    good = got == want; ok = ok and good
    print("  [%s] %s: got=%r want=%r" % ("PASS" if good else "FAIL", label, got, want))
chk("chat_direct mean (3.0,5.0 -> 4.0)", by["chat_direct"]["acrr_mean"], 4.0)
chk("chat_direct runs", by["chat_direct"]["runs"], 2)
chk("workflow_linear mean (0.5,1.5 -> 1.0)", by["workflow_linear"]["acrr_mean"], 1.0)
chk("failed run excluded", d["skipped_failed_runs"], 1)
chk("acrr=99 did NOT pollute the mean", by["chat_direct"]["acrr_mean"] == 4.0, True)
sys.exit(0 if ok else 1)
PY
rc=$?
echo
echo "RESULT: $([ $rc -eq 0 ] && echo 'ALL PASS' || echo 'FAILURES')"
exit $rc
SHEOF
bash /tmp/s9_row6.sh; echo "EXIT=$?"
```

---

## Row 7 — Operator toggle

Proves `chat_escalation_gate` is genuinely operator-controllable, including the
fail-safe on a malformed value. **Your `~/.fa/config.yaml` is not modified.**

```bash
cat > /tmp/s9_row7.sh <<'SHEOF'
#!/usr/bin/env bash
set -uo pipefail
echo "S9-7 TOGGLE (chat_escalation_gate)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

python - "$TMP" <<'PY'
import sys
from pathlib import Path
from fa.inner_loop.runtime_limits import load_runtime_limits, load_runtime_limits_from_path
tmp = Path(sys.argv[1])
cases = [
    ("absent key     -> default ON", "runtime_limits:\n  max_iterations: 6\n", True, 0),
    ("explicit true  -> ON        ", "runtime_limits:\n  chat_escalation_gate: true\n", True, 0),
    ("explicit false -> OFF       ", "runtime_limits:\n  chat_escalation_gate: false\n", False, 0),
    ("garbage value  -> WARN + ON ", "runtime_limits:\n  chat_escalation_gate: maybe\n", True, 1),
]
ok = True
for label, text, want, want_warns in cases:
    r = load_runtime_limits(text)
    got = r.limits.chat_escalation_gate
    n = len([w for w in r.warnings if w.key == "chat_escalation_gate"])
    good = (got == want) and (n == want_warns); ok = ok and good
    print("  [%s] %s  gate=%-5s warnings=%d" % ("PASS" if good else "FAIL", label, got, n))
    for w in r.warnings:
        if w.key == "chat_escalation_gate":
            print("         -> line %d: %s" % (w.line_no, w.detail))
p = tmp / "config.yaml"
p.write_text("runtime_limits:\n  chat_escalation_gate: false\n")
res = load_runtime_limits_from_path(p)
good = res.limits.chat_escalation_gate is False; ok = ok and good
print("  [%s] load_runtime_limits_from_path (the CLI's real entry) -> gate=%s"
      % ("PASS" if good else "FAIL", res.limits.chat_escalation_gate))
sys.exit(0 if ok else 1)
PY
rc=$?
echo
echo "RESULT: $([ $rc -eq 0 ] && echo 'ALL PASS' || echo 'FAILURES')"
exit $rc
SHEOF
bash /tmp/s9_row7.sh; echo "EXIT=$?"
```

---

## Row 8 — First LIVE run: simple task must NOT be interfered with

This is the "does not interfere when simple" half of the feature, on the real
provider. **Uses a scratch workspace, not the repo.**

```bash
WS="$(mktemp -d)"; cd "$WS"
git init -q . && echo "# scratch" > README.md && git add -A \
  && git -c user.email=s9@test -c user.name=s9 commit -qm init
echo "workspace: $WS"

# PIPESTATUS, not $? -- `cmd | tail` reports tail's status, which is always 0.
fa run --role chat \
  --task "Add a line saying 'verified by S9' to README.md" \
  --workspace "$WS" --max-turns 6 --detail verbose 2>&1 | tail -40
echo "fa EXIT=${PIPESTATUS[0]}"

echo "--- did it actually edit the file? ---"
cat README.md
echo "--- scope estimate + routing for this run ---"
grep -RhoE '"kind": *"(scope_estimate|scope_tripwire)"[^}]*' ~/.fa/session-log/*/events.jsonl 2>/dev/null | tail -5 \
  || echo "(no session-log events.jsonl found; check ~/.fa/sessions/*/ instead)"
```

**Expect (do not assume — report what happens):** the estimator should say
`chat_direct`, the gate should stay quiet, write tools should be available, and
the edit should land. If the gate fired here, that is a **false positive** and a
defect.

---

## Row 9 — Capability test: the real broken-links defect, ending in a push + PR

The task is a **genuine pending defect** in the repo: a prior commit moved plans
into `worklogs/archive/` and left **46 broken internal links across 15 files**.
`tests/test_doc_links.py` currently fails because of it, which gives the agent a
binary oracle to verify against.

Why this is the right capability test:

- **Multi-file** (15 files) but conceptually simple — the estimator scores it
  `chat_direct`, i.e. it **under-scopes**. That is precisely the case the S7
  tripwire exists to catch, so this run exercises the whole design end to end.
- **Self-verifying**: `pytest tests/test_doc_links.py` is the oracle.
- **Ends in a real push + PR**, which is the functional capability you asked to
  confirm.

### 9a — Baseline (run BEFORE the agent, so the delta is measurable)

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
echo "broken links now: $(python -m pytest tests/test_doc_links.py -q -p no:randomly 2>&1 | grep -cE 'broken link target')"
echo "files affected:   $(python -m pytest tests/test_doc_links.py -q -p no:randomly 2>&1 | grep -oE '^E +[a-zA-Z0-9_/.-]+\.md:' | sed 's/E *//;s/:$//' | sort -u | wc -l)"
git rev-parse --abbrev-ref HEAD
git status --porcelain | wc -l
```

### 9b — The live agent run

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
BRANCH="s9-live-verification-$(date +%Y%m%d-%H%M)"
echo "target branch: $BRANCH"

fa run --role chat --workspace "$(pwd)" --max-turns 40 --detail verbose --task "\
The test tests/test_doc_links.py is failing: a previous commit moved old plans into \
worklogs/archive/ and left broken relative markdown links behind (about 46 of them across \
roughly 15 files). \
\
Fix the broken links so that 'python -m pytest tests/test_doc_links.py -q -p no:randomly' passes. \
Only correct link targets in markdown files; do not delete documentation content and do not \
edit anything under src/ or tests/. \
\
Then: create a new git branch named $BRANCH, commit the fix with a clear conventional-commit \
message, and push the branch to origin. Finally open a pull request against \
New-main-role-chat-and-complexity-aware-workflow-execution if the gh CLI is available; \
if it is not, print the compare URL instead." 2>&1 | tail -60
echo "fa EXIT=${PIPESTATUS[0]}"
```

### 9c — Verify the outcome (independent of what the agent claims)

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
echo "=== oracle: does the test pass now? ==="
python -m pytest tests/test_doc_links.py -q -p no:randomly 2>&1 | tail -3
echo "remaining broken links: $(python -m pytest tests/test_doc_links.py -q -p no:randomly 2>&1 | grep -cE 'broken link target')"

echo
echo "=== did it stay in scope? (src/ and tests/ must be untouched) ==="
# Compare against the branch the agent started from, NOT HEAD~1 -- HEAD~1 would
# include whatever commit happened to precede the run and give a false reading.
BASE="New-main-role-chat-and-complexity-aware-workflow-execution"
git diff --stat "$BASE"...HEAD 2>/dev/null | tail -6
TOUCHED=$(git diff --name-only "$BASE"...HEAD 2>/dev/null | grep -cE '^(src|tests)/')
echo "src/ or tests/ files touched: ${TOUCHED}  <- must be 0"
[ "${TOUCHED:-1}" -eq 0 ] && echo "  [PASS] stayed in scope" || echo "  [FAIL] out-of-scope edits present"

echo
echo "=== branch + push ==="
git rev-parse --abbrev-ref HEAD
git log --oneline -1
git ls-remote --heads origin 2>/dev/null | grep s9-live-verification || echo "  (branch not found on remote)"

echo
echo "=== ROUTING EVIDENCE: did the tripwire fire? ==="
python - <<'PY'
# Events live in sqlite (session.db :: event_log), NOT in a jsonl file.
# Verified: ~/.fa/sessions/*/session.db has table event_log(kind, content, ...).
import glob, os, sqlite3
hits = {"scope_estimate": [], "scope_tripwire": []}
dbs = glob.glob(os.path.expanduser("~/.fa/sessions/*/session.db")) \
    + glob.glob(os.path.expanduser("~/.fa/session-log/*/session.db"))
print(f"  scanned {len(dbs)} session database(s)")
for db in dbs:
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT kind, content, run_id FROM event_log "
            "WHERE kind IN ('scope_estimate','scope_tripwire') ORDER BY id"
        ).fetchall()
        for kind, content, run_id in rows:
            hits[kind].append((os.path.basename(os.path.dirname(db)), run_id, content))
        conn.close()
    except Exception as exc:
        print(f"  (skipped {os.path.basename(os.path.dirname(db))}: {type(exc).__name__})")
for kind, found in hits.items():
    print(f"  {kind}: {len(found)} event(s)")
    for sess, run_id, content in found[-3:]:
        print(f"    {sess} run={run_id}: {str(content)[:150]}")
if not hits["scope_tripwire"]:
    print("  NOTE: no tripwire event. Either the run touched <= 10 distinct files,")
    print("        or the tripwire failed to fire -> record that as a defect.")
if len(hits["scope_estimate"]) > 1:
    print("  WARNING: more than one scope_estimate for a single run would corrupt")
    print("           the S3.5 projection (it keeps the LAST one). Check run_ids above.")
PY

echo
echo "=== ACRR for this run (the S8 metric, on real data) ==="
fa stats --global-history --output json 2>/dev/null > /tmp/s9_gh.json
python - /tmp/s9_gh.json <<'PY'
import json, sys
try:
    rows = json.load(open(sys.argv[1]))
except Exception as exc:
    print("  (no global history rows yet: %s)" % exc); raise SystemExit(0)
if not rows:
    print("  (global history is empty)"); raise SystemExit(0)
for r in rows[:5]:
    print("  %-26s role=%-10s files_read=%-4s files_changed=%-4s read_ampl=%-6s acrr=%s" % (
        str(r.get("run_id",""))[:26], r.get("role",""), r.get("files_read"),
        r.get("files_changed"), r.get("read_amplification"), r.get("acrr")))
PY

echo
echo "=== calibration table, now with a REAL run in it ==="
fa stats --calibration 2>&1 1>/dev/null
```

### 9d — Cleanup (after you have inspected the PR)

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
BR="$(git rev-parse --abbrev-ref HEAD)"
echo "current branch: $BR"
# Return to the feature branch; delete the throwaway branch locally and remotely.
git checkout New-main-role-chat-and-complexity-aware-workflow-execution
# git branch -D "$BR"
# git push origin --delete "$BR"
echo "(delete commands are commented out on purpose — uncomment when ready)"
```

---

## Row 10 — Full-suite delta

```bash
cd ~/work/repo 2>/dev/null || cd "$(git rev-parse --show-toplevel)"
python -m pytest -q -p no:randomly 2>&1 | tail -12
```

Baseline to compare against: **3403p/7f** (plan) → **3484p/7f** measured after S8
in the dev sandbox. Note which failures are environment-caused on your host
(absent `semgrep` / `vulture` / `pyrefly` binaries) versus real.

---

## Estimator accuracy baseline (E9 step 3)

Re-measured on the same 15 author-written tasks used in the Task-4 measurement.

**This is not a labelled corpus.** The tasks were written by the implementer, so
the number is a self-assessment and is stated here only as the baseline that the
Row 6 calibration table is designed to supersede with real-run evidence (Q22).

| Confidence bucket | Correct | Total | Accuracy |
|---|---|---|---|
| 0.8 | 4 | 4 | **100%** |
| 0.6 | 3 | 5 | 60% |
| 0.3 | 2 | 6 | 33% |
| **overall** | **9** | **15** | **60%** |

6 under-scopes, 0 over-scopes. The gate is deliberately restricted to the 0.8
bucket because that is the only bucket that measured 100%.

**The Row 9 task is itself a 7th under-scope**: a genuinely 15-file job that the
estimator calls `single-file` / `chat_direct`. It is included precisely because
it demonstrates the tripwire covering an estimator miss.

---

## Defects found while building this sheet

| D# | Severity | Finding | Disposition |
|---|---|---|---|
| **D-S9-1** | Medium (security) | `src/fa/sandbox/validators.py:285` denies force-push to `main`/`master` by testing `"--force" in tokens or "--force-with-lease" in tokens`. The **short flag `-f` is not checked**, so `git push -f origin main` is **ALLOWED**. Verified: `--force` → denied, `-f` → `validator_git: ok`. | **NOT fixed here.** Pre-existing (`validators.py` untouched by S7/S8, confirmed via `git diff 00c1c4a..HEAD`), and out of the E9 allowed-files list. Row 5 asserts the current behaviour so the sheet stays honest. Recommend a one-line fix in its own commit: add `-f` to the token test. |

---

## Pre-ship verification of this sheet

Every block above was extracted from this markdown and executed on the dev host
before shipping. `bash -n` on all 14 blocks: clean. Rows 0-7 run green
(`rc=0`, `RESULT: ALL PASS`). Rows 8-9 had their non-LLM mechanics executed;
only the provider calls themselves are unrun here.

That process found **four bugs in the sheet itself**, all fixed before you see it.
Recording them because three would have produced *silently wrong* output rather
than an obvious error:

| # | Bug | Why it mattered | Fix |
|---|---|---|---|
| S1 | Nested `python -c '...f"{r[\"key\"]}"...'` inside a shell pipeline raised `SyntaxError` | It was followed by `|| echo "(no rows yet)"`, so the sheet would have printed a plausible "no data" message and hidden the crash | Replaced with a `python - file <<'PY'` heredoc; no nested quoting |
| S2 | Routing-evidence probe grepped `~/.fa/**/events.jsonl` | **No such file exists** - events live in `session.db :: event_log`. The probe would have reported "no tripwire fired" on every host, regardless of truth | Rewritten to query sqlite read-only (`file:...?mode=ro`); verified positively by seeding a real `scope_tripwire` row, detecting it, then removing it |
| S3 | Scope check used `git diff HEAD~1` | `HEAD~1` is whatever commit preceded the run; on the dev host it reported "src/ touched: 4" for a run that touched nothing | Compare against the branch point: `git diff "$BASE"...HEAD` |
| S4 | `echo "EXIT=$?"` after `fa run ... | tail -40` | Reports `tail`'s status (always 0), so a failed `fa run` would look successful | `${PIPESTATUS[0]}` |

S2 is the one worth dwelling on: it is exactly the "vacuous check" failure mode
the tests-writing skill warns about - a probe that cannot fail is worse than no
probe, because it manufactures false confidence.

---

## Row results

Fill in as you run. **Paste actual output; do not paraphrase.**

| Row | What it proves | Exit | Result |
|---|---|---|---|
| 0 | Preflight: host can run the sheet | | |
| 1 | Wiring: constants and module surface | | |
| 2 | Gate + tripwire decision matrix | | |
| 3 | E3 arithmetic + hostile inputs | | |
| 4 | Migration, rename, NULL semantics | | |
| 5 | Bash-gate safety rails (+ D-S9-1) | | |
| 6 | Calibration view, isolated | | |
| 7 | Operator toggle | | |
| 8 | LIVE: simple task not interfered with | | |
| 9 | LIVE: 15-file fix, push, PR | | |
| 10 | Full-suite delta | | |

## Exit criteria (E9)

- [ ] every row has real pasted output
- [ ] full-suite delta stated against the 3403p/7f baseline
- [ ] failures recorded as D# with disposition — **D-S9-1 recorded**
