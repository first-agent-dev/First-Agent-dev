#!/usr/bin/env python3
"""Verify GitHub Actions workflow hygiene.

Two invariant classes are checked against every ``.github/workflows/*.yml``:

1. **Path-filter invariant (ADR-11-I6):** no blocking job's trigger
   section uses ``paths:`` / ``paths-ignore:``. A guardrail that only
   runs when its own files change is trivially bypassed.
2. **No-constant-skip invariant:** no blocking job is guarded by a
   job-level ``if:`` that statically reduces to constant-false (literal
   ``false``/``0``/``null``/``"${{ false }}"``/``"${{ 0 }}"``) or by a
   ``github.event.pull_request.draft`` gate without an explicit
   ``# ci-hygiene: draft-ok`` annotation. ``if: false`` on a blocking
   job is a trivial CI bypass.

Why this script exists (instead of naive grep):
    # BAD oracle (false FAIL): matches comments that mention "paths: filter".
    grep -q "paths:" .github/workflows/foo.yml && echo FAIL

    YAML is parsed properly so comment prose is ignored; ``on`` (which
    YAML 1.1 parses as boolean ``True`` — a well-known gotcha) is
    handled. Job-level ``if:`` detection uses a small line-scan pre-pass
    because PyYAML ``safe_load`` drops comments (needed for the
    ``draft-ok`` escape hatch).

Exit codes:
    0 — no hygiene findings in any checked workflow
    1 — one or more workflows contain a finding
    2 — usage / file-not-found error

Dependencies: PyYAML (project dev-dep); stdlib otherwise.
This file IS a protected TCB path (``scripts/check_*`` prefix).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# UTF-8 console: this script prints non-ASCII (checkmarks / box drawing);
# force UTF-8 so cp1251 Windows hosts don't crash while reporting
# success. See scripts/_console.py for the full rationale.
if __package__ in (None, ""):  # invoked as a file, not as scripts.<name>
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import (
    add_output_arg,
    add_repo_root_arg,
    force_utf8_stdio,
    resolve_repo_root,
)

force_utf8_stdio()

# Keys that constitute path filtering at the trigger level.
_PATH_FILTER_KEYS = frozenset({"paths", "paths-ignore"})

# Job-level if: values that ALWAYS skip the job (no runtime data needed).
# - Python False is YAML bare ``false`` / ``off`` / ``no``.
# - 0, None (YAML null/~), "" (empty string) are also falsy in GHA
#   expressions and represent a trivially-skipped job.
_BLOCKING_FALSE_LITERALS: frozenset[Any] = frozenset({False, None, ""})

# String ``if:`` expressions that are exactly a static-false ${{ }} wrap.
# Compounds like ``${{ false || true }}`` intentionally NOT matched —
# those need human review; this is an advisory gate, not an evaluator.
_BLOCKING_FALSE_EXPR = re.compile(r"^\s*\$\{\{\s*(false|0)\s*\}\}\s*$")

# ``# ci-hygiene: draft-ok`` annotation, placed within 5 lines before a
# job-level if: (or as an inline comment on the if: line itself) to mark
# that a draft-gate on that job is intentional.
_DRAFT_OK_COMMENT = re.compile(r"#\s*ci-hygiene:\s*draft-ok\b")

# Heuristic: an if: expression mentioning pull_request.draft is a
# "run only on non-draft PR" (or vice versa) guard, which on a blocking
# job is suspicious — draft PRs must still run all blocking checks.
_DRAFT_GUARD_EXPR = re.compile(r"github\.event\.pull_request\.draft")


# ---------------------------------------------------------------------------
# Trigger walking (original path-filter logic)
# ---------------------------------------------------------------------------


def _collect_on_triggers(on_section: Any) -> list[tuple[str, dict[str, Any]]]:
    """Walk the ``on:`` section and return (trigger_name, config) pairs.

    Handles shorthand, longhand, and list forms::

        on: [pull_request, push]                # list
        on:                                     # dict
          pull_request:                         # shorthand (config=None)
          push:                                 # longhand
            branches: [main]
    """
    if on_section is None:
        return []
    if isinstance(on_section, list):
        return [(str(item), {}) for item in on_section]
    if isinstance(on_section, dict):
        pairs: list[tuple[str, dict[str, Any]]] = []
        for name, config in on_section.items():
            pairs.append((str(name), config if isinstance(config, dict) else {}))
        return pairs
    return []


# ---------------------------------------------------------------------------
# Comment pre-pass for draft-ok annotations
# ---------------------------------------------------------------------------


def _scan_draft_ok_annotations(text: str) -> set[str]:
    """Line-scan a workflow YAML string for draft-ok annotations.

    Returns the set of job names whose job-level ``if:`` is immediately
    preceded (or trailed inline) by a ``# ci-hygiene: draft-ok`` comment.

    A job qualifies as draft-ok only if the annotation sits within the
    job's own body — i.e. after the job-name line AND before the next
    job-name line at the same indent. We DO NOT scan across job
    boundaries, otherwise an annotation in job ``a`` would apply to a
    later job ``b`` that has no intervening blank lines.

    Because PyYAML ``safe_load`` drops comments, we do a cheap
    indentation-aware scan:
      1. Find the ``jobs:`` mapping line and record its indent.
      2. Job names are keys at ``jobs_indent + 2``. Track "current job"
         and reset on each new job-name line.
      3. A job-level ``if:`` key lives at ``jobs_indent + 4`` inside a
         job (between two job-name lines at ``job_indent``).
      4. If the 5 lines above the if: line (within the SAME job's body)
         or the if: line's inline comment contain the annotation, mark
         that job draft-ok.
    This is deliberately narrow; it is not a general YAML parser.
    """
    draft_ok: set[str] = set()
    lines = text.splitlines()

    jobs_indent: int | None = None
    jobs_line_idx: int = -1
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)jobs\s*:\s*(?:#.*)?$", line)
        if m:
            jobs_indent = len(m.group(1))
            jobs_line_idx = i
            break
    if jobs_indent is None:
        return draft_ok

    job_indent = jobs_indent + 2
    if_indent = jobs_indent + 4

    # Walk forward tracking the current job and collecting its job-level if:
    # positions. Each new job-name at job_indent resets the current job,
    # which NATURALLY bounds the lookback — we just look back from each if:
    # up to the start-of-job (or 5 lines, whichever is smaller).
    job_start_idx: int = jobs_line_idx
    current_job: str | None = None
    ifs_found: list[tuple[str, int, int]] = []
    job_re = re.compile(r"^(\s*)([A-Za-z0-9_-]+)\s*:\s*(?:#.*)?$")
    if_re = re.compile(r"^(\s*)if\s*:\s*(.*?)$")
    for i in range(jobs_line_idx + 1, len(lines)):
        line = lines[i]
        jm = job_re.match(line)
        if jm and len(jm.group(1)) == job_indent:
            # Entering a new job body; flush lookback boundary.
            current_job = jm.group(2)
            job_start_idx = i
            continue
        if current_job is None:
            continue
        im = if_re.match(line)
        if im and len(im.group(1)) == if_indent:
            ifs_found.append((current_job, i, job_start_idx))
            # Inline comment on the if: line itself (after any YAML value).
            inline_comment_idx = line.find("#", len(im.group(1)) + 3)
            if inline_comment_idx != -1:
                tail = line[inline_comment_idx:]
                if _DRAFT_OK_COMMENT.search(tail):
                    draft_ok.add(current_job)

    for job_name, if_idx, start_idx in ifs_found:
        lookback_start = max(start_idx + 1, if_idx - 5)
        for j in range(lookback_start, if_idx):
            if _DRAFT_OK_COMMENT.search(lines[j]):
                draft_ok.add(job_name)
                break

    return draft_ok


# ---------------------------------------------------------------------------
# if:-bypass detection
# ---------------------------------------------------------------------------


def _find_bypass_if(
    data: dict[str, Any],
    draft_ok_jobs: set[str],
) -> list[dict[str, str]]:
    """Return a list of {'job': name, 'reason': slug} for blocked jobs with a
    constant-false or undecorated draft guard at the job level.

    Heuristics (intentionally narrow):
      - skip jobs where ``continue-on-error: true`` (advisory by definition);
      - ``if: <literal False|0|None|"">`` → ``literal-false``;
      - ``if:`` a string EXACTLY matching ``${{ false }}`` or ``${{ 0 }}``
        (after stripping surrounding whitespace) → ``expr-false``;
      - ``if:`` string contains ``github.event.pull_request.draft`` and
        the job is NOT in ``draft_ok_jobs`` → ``draft-gate-no-annotation``.
    Step-level ``if:`` is ignored (per-step artifacts like ``if: always()``
    on upload steps are legitimate).
    """
    findings: list[dict[str, str]] = []
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return findings
    for job_name, body in jobs.items():
        if not isinstance(body, dict):
            continue
        # Advisory jobs are allowed to be conditional.
        if body.get("continue-on-error", False) is True:
            continue

        # We need to detect a job-level key ``if:`` that is present AND set
        # to a falsy literal. Two distinct cases:
        #   * ``"if" not in body``       — no job-level if (ok; don't flag).
        #   * ``"if" in body`` but value is e.g. ``False``/``0``/``None``/``""``
        #     — present and statically-skip (flag).
        # ``body.get("if", None)`` cannot distinguish "missing key" from
        # "key set to None (YAML null)", so test membership explicitly.
        if "if" not in body:
            continue
        if_val = body.get("if")
        if if_val is True or if_val == "true":
            # ``if: true`` / ``if: True`` is a no-op (always run); not a bypass.
            continue
        if if_val in _BLOCKING_FALSE_LITERALS:
            findings.append({"job": str(job_name), "reason": "literal-false"})
            continue
        if isinstance(if_val, str):
            if _BLOCKING_FALSE_EXPR.match(if_val):
                findings.append({"job": str(job_name), "reason": "expr-false"})
                continue
            if _DRAFT_GUARD_EXPR.search(if_val) and str(job_name) not in draft_ok_jobs:
                findings.append({"job": str(job_name), "reason": "draft-gate-no-annotation"})
    return findings


# ---------------------------------------------------------------------------
# Per-workflow check
# ---------------------------------------------------------------------------


def check_workflow(path: Path) -> dict[str, Any]:
    """Check a single workflow file for hygiene violations.

    Returns a dict with keys:
        path: str
        has_path_filter: bool
        has_bypass_if: bool
        triggers_with_filter: list[str]
        filter_keys_found: list[str]
        bypass_findings: list[{job: str, reason: str}]
        draft_ok_jobs: list[str]
        error: str | None
    """
    result: dict[str, Any] = {
        "path": str(path),
        "has_path_filter": False,
        "has_bypass_if": False,
        "triggers_with_filter": [],
        "filter_keys_found": [],
        "bypass_findings": [],
        "draft_ok_jobs": [],
        "error": None,
    }
    if not path.exists():
        result["error"] = f"file not found: {path}"
        return result

    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        result["error"] = f"YAML parse error: {exc}"
        return result

    if not isinstance(data, dict):
        result["error"] = "workflow is not a YAML mapping"
        return result

    # YAML parses bare ``on`` as boolean True (YAML 1.1 gotcha).
    on_section = data.get("on") or data.get(True)
    triggers = _collect_on_triggers(on_section)

    filter_keys_found: set[str] = set()
    triggers_with_filter: list[str] = []
    for trigger_name, config in triggers:
        for key in _PATH_FILTER_KEYS:
            if key in config:
                filter_keys_found.add(key)
                if trigger_name not in triggers_with_filter:
                    triggers_with_filter.append(trigger_name)

    result["has_path_filter"] = bool(filter_keys_found)
    result["triggers_with_filter"] = triggers_with_filter
    result["filter_keys_found"] = sorted(filter_keys_found)

    draft_ok_jobs = _scan_draft_ok_annotations(raw)
    bypass_findings = _find_bypass_if(data, draft_ok_jobs)
    result["bypass_findings"] = bypass_findings
    result["has_bypass_if"] = bool(bypass_findings)
    result["draft_ok_jobs"] = sorted(draft_ok_jobs)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_workflow_hygiene",
        description=(
            "Verify GitHub Actions workflows have no paths:/paths-ignore: "
            "filters and no constant-false `if:` bypass on blocking jobs."
        ),
    )
    parser.add_argument(
        "workflows",
        nargs="*",
        type=Path,
        help="Workflow YAML files to check (default: .github/workflows/*.yml).",
    )
    add_repo_root_arg(parser)
    add_output_arg(parser)
    args = parser.parse_args(argv)

    repo_root = resolve_repo_root(args)

    if args.workflows:
        workflow_paths = [p if p.is_absolute() else repo_root / p for p in args.workflows]
    else:
        workflow_dir = repo_root / ".github" / "workflows"
        if not workflow_dir.is_dir():
            print(f"error: no .github/workflows/ directory found in {repo_root}", file=sys.stderr)
            return 2
        workflow_paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))

    if not workflow_paths:
        print("error: no workflow files found", file=sys.stderr)
        return 2

    results = [check_workflow(p) for p in workflow_paths]
    any_finding = any(r["has_path_filter"] or r["has_bypass_if"] or r["error"] for r in results)
    errors_present = any(r["error"] for r in results)

    if args.output == "json":
        json.dump(
            {
                "has_finding": any_finding,
                "has_error": errors_present,
                "workflows": results,
            },
            sys.stdout,
            indent=2,
        )
        print()
    else:
        for r in results:
            if r["error"]:
                print(f"ERROR {r['path']}: {r['error']}")
                continue
            bad_parts: list[str] = []
            if r["has_path_filter"]:
                keys = ", ".join(r["filter_keys_found"])
                trigs = ", ".join(r["triggers_with_filter"])
                bad_parts.append(f"has {keys} in trigger(s): {trigs}")
            for bp in r["bypass_findings"]:
                bad_parts.append(f"job '{bp['job']}' has bypass if: {bp['reason']}")
            if bad_parts:
                print(f"FAIL {r['path']}: " + "; ".join(bad_parts))
            else:
                print(f"PASS {r['path']}: no path filters, no if-bypass")

    return 1 if (any_finding or errors_present) else 0


if __name__ == "__main__":
    raise SystemExit(main())
