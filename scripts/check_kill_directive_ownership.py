#!/usr/bin/env python3
"""Reject unfirable kill directives once their owning slice is complete. (CT83)

A plan is allowed to name producers that a later slice will build. Auditing
those while the plan is still in progress confuses "not implemented yet" with
"the completed slice claims coverage of nothing." This check therefore waits
until every declared STEP checkbox in a slice is done, then requires each
parsed kill target to resolve to exactly one definition in the named source.

It is an ownership audit, not a full plan precheck: malformed/missing kill
syntax remains the precheck's responsibility. It never edits source or plan
files.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Running as `python scripts/check_kill_directive_ownership.py` does not make
# src/ importable in a bare checkout. Keep the script runnable outside `uv`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fa.inner_loop import plan_ids
from fa.inner_loop.plan_ids import SliceRecord, extract_plan_ids
from fa.inner_loop.slice_verification import _resolve_targets, parse_kill_directives

_INCREMENTS = Path("worklogs/planning-topology-and-executable-contracts-loop/increments")


def _fully_ticked(record: SliceRecord) -> bool:
    """True iff the slice has at least one STEP box and every box is done.

    Reuse I01's checkbox recognizer and marker normalizer rather than keeping
    a second grammar here. A slice with no declared STEP boxes is not "fully
    ticked": treating the empty set as complete would audit work that has no
    recorded completion boundary.
    """
    marks = tuple(match.group("mark") for match in plan_ids._STEP_RE.finditer(record.section))
    return bool(marks) and all(plan_ids._step_state(mark) == "done" for mark in marks)


def _diagnostic(
    root: Path,
    plan_path: Path,
    record: SliceRecord,
    contract_id: str,
    target: str,
    message: str,
) -> str:
    """One stable, actionable line for an unfirable directive."""
    plan_rel = plan_path.relative_to(root).as_posix()
    return f"{plan_rel}::{record.slice_id}::{contract_id} {target}: {message}"


def _unresolved_directives(repo_root: Path) -> tuple[str, ...]:
    """Return defects in fully-ticked increment slices, in stable plan order."""
    root = Path(repo_root).resolve()
    plan_dir = root / _INCREMENTS
    if not plan_dir.is_dir():
        return (f"{_INCREMENTS.as_posix()}: increment plan directory is missing",)

    plan_files = tuple(sorted(plan_dir.rglob("*.md")))
    if not plan_files:
        return (f"{_INCREMENTS.as_posix()}: no increment plan files found",)

    out: list[str] = []
    for plan_path in plan_files:
        try:
            plan_text = plan_path.read_text(encoding="utf-8")
        except OSError as exc:
            out.append(f"{plan_path.relative_to(root).as_posix()}: cannot read plan: {exc}")
            continue

        ids = extract_plan_ids(plan_text)
        for record in ids.slice_records:
            if not _fully_ticked(record):
                continue
            for contract_id, directive in parse_kill_directives(record).items():
                target = f"{directive.path}::{directive.symbol}"
                source_path = (root / directive.path).resolve()
                if not source_path.is_relative_to(root):
                    out.append(
                        _diagnostic(root, plan_path, record, contract_id, target, "path escapes repository root")
                    )
                    continue
                try:
                    source = source_path.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=source_path.as_posix())
                except (OSError, SyntaxError, UnicodeError) as exc:
                    out.append(
                        _diagnostic(root, plan_path, record, contract_id, target, f"cannot inspect target: {exc}")
                    )
                    continue

                count = len(_resolve_targets(tree, directive.symbol))
                if count != 1:
                    out.append(
                        _diagnostic(
                            root,
                            plan_path,
                            record,
                            contract_id,
                            target,
                            f"resolved to {count} definitions; expected exactly one",
                        )
                    )
    return tuple(out)


def main(repo_root: Path | None = None) -> int:
    """Print every unresolved target and return a gate-style exit code."""
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    findings = _unresolved_directives(root)
    for finding in findings:
        print(finding, file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
