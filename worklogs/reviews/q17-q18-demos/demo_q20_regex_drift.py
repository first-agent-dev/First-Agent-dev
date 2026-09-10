"""Q20: how brittle is the judge-output regex, and why it matters under a full gate."""

from fa.inner_loop.workflow_artifacts import _STEP_LINE_RE as R
from fa.inner_loop.workflow_artifacts import parse_eval_report
from fa.inner_loop.workflow_controller import validate_slice_ids

print("=== 1. Which judge line formats does _STEP_LINE_RE accept? ===")
cases = [
    ("- S1: PASS - ok", "canonical"),
    ("- S1: PASS — em-dash note", "em dash"),
    ("* S2: FAIL: broken", "asterisk + colon"),
    ("  - s3: pass - lowercase", "lowercase + indent"),
    ("- S5a: PARTIAL - suffix id", "letter suffix"),
    ("- **S1**: PASS - bolded", "MARKDOWN BOLD"),
    ("- S1 — PASS - no colon", "no colon"),
    ("| S1 | PASS | ok |", "TABLE ROW"),
    ("- S1: PASSED - past tense", "PASSED"),
    ("1. S1: PASS - numbered", "NUMBERED LIST"),
    ("- Step S1: PASS - prefixed", "Step prefix"),
]
for text, note in cases:
    print(f"  {text!r:42s} {'yes' if R.match(text) else 'NO ':4s} {note}")

print()
print("=== 2. Why it matters: identical review quality, different formatting ===")
plan = "# P Plan-ID: X\n### Step S1: a\n### Step S2: b\n"
variants = [
    ("plain markdown", "- S1: PASS - ok\n- S2: PASS - ok\n"),
    ("bolded IDs", "- **S1**: PASS - ok\n- **S2**: PASS - ok\n"),
    ("markdown table", "| S1 | PASS | ok |\n| S2 | PASS | ok |\n"),
]
for label, body in variants:
    report = parse_eval_report(
        f"### Step results\n{body}\n### Verdict\nPASS\n",
        run_id="r",
        plan_id="X",
        evaluation_id="e",
    )
    out = validate_slice_ids(report, plan)
    rep = out[0] if isinstance(out, tuple) else out
    print(
        f"  {label:16s} parsed={[s.step_id for s in rep.step_results]!s:16s} unreported={list(rep.unreported_slices)}"
    )

print()
print("  A judge that reviewed EVERY slice correctly but wrote '**S1**' is")
print("  indistinguishable from a judge that reviewed nothing. Under the Q17")
print("  full gate this becomes a FALSE HALT -- hence the S15d normalisation.")
