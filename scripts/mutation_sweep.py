#!/usr/bin/env python3
"""Targeted mutation sweep for the CLI-trace substrate (S1-S6).

Why this exists
---------------
``mutmut``'s configured scope is ``src/fa/sandbox`` only (``pyproject.toml``
``[tool.mutmut] source_paths``). The whole S1-S6 substrate -- session manager,
EventLog, coder_loop, subagent runner, output bus -- has therefore **never**
been under mutation coverage. The S6 audit found four mutants by hand, three of
which survived the entire suite, so "the suite is green" was demonstrably not
evidence for this code.

This is a deliberately small, auditable harness rather than a second mutation
framework: it applies ONE textual mutation, runs a chosen test subset, and
classifies the outcome. It is meant for reviewing a slice's delta, not for
computing a repo-wide mutation score (that stays mutmut's job).

Two harness bugs burned during the S6 sweep, both now guarded:

1. **Shadowed imports.** Running the copy with ``PYTHONPATH=<copy>/src`` made
   ``fa`` resolve but hid installed third-party deps, so every run "passed" via
   a collection error. Now the copy is installed with ``pip install -e`` and the
   resolved import root is asserted to live inside the copy.
2. **``xfailed`` contains ``failed``.** Substring matching on the pytest summary
   line reported a caught mutant as survived. Now the counts are parsed from
   ``-p no:cacheprovider --tb=no -q`` summary numbers with word boundaries, and
   a collection error is its own outcome, never "survived".

A mutation whose pattern is absent, or which leaves the file byte-identical, is
reported as SKIP -- silently counting it as "survived" is how a sweep talks
itself into false confidence.

**The suite is always run whole.** The sweep's question is "would *any* test
notice this change?", so narrowing the run per mutation could only weaken the
answer -- and a mis-specified subset would narrow it to nothing and manufacture
a false SURVIVED. Keeping the pytest argv a fixed literal also means no value
from a spec file ever reaches a command line.

Usage::

    python scripts/mutation_sweep.py --spec sweep_specs/s5.json
    python scripts/mutation_sweep.py --spec ... --only M3 --keep
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Outcomes. SURVIVED is the only one that means "add a test".
CAUGHT = "CAUGHT"
SURVIVED = "SURVIVED"
SKIP = "SKIP"
HARNESS_FAIL = "HARNESS-FAIL"

# Excluded from the mutant copy: version control, caches, generated artefacts
# and the patch bundles. Shared by the copy and the free-space estimate so the
# two cannot drift.
_COPY_IGNORE = (
    ".git",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gremlins_cache",
    "coverage",
    "mutants",
    "patches",
    "node_modules",
    ".venv",
)

_SUMMARY_FAILED = re.compile(r"(\d+) failed")
_SUMMARY_PASSED = re.compile(r"(\d+) passed")
_SUMMARY_ERROR = re.compile(r"(\d+) error")


@dataclass(frozen=True)
class Mutation:
    """One semantic edit and the tests that should notice it."""

    mid: str
    file: str
    old: str
    new: str
    rationale: str

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> Mutation:
        missing = [key for key in ("id", "file", "old", "new") if key not in raw]
        if missing:
            raise ValueError(f"mutation spec entry is missing required key(s): {missing}")
        return cls(
            mid=str(raw["id"]),
            file=str(raw["file"]),
            old=str(raw["old"]),
            new=str(raw["new"]),
            rationale=str(raw.get("why", "")),
        )


@dataclass(frozen=True)
class Outcome:
    mid: str
    verdict: str
    detail: str
    rationale: str


def _classify(stdout: str) -> tuple[str, str]:
    """Map a pytest run to an outcome.

    ``xfailed``/``xpassed`` deliberately do not count: ``\\d+ failed`` with a
    word boundary cannot match ``1 xfailed`` because the digit group must be
    preceded by whitespace in the summary line.
    """
    tail = stdout.strip().splitlines()
    summary = tail[-1] if tail else ""
    errors = _SUMMARY_ERROR.search(summary)
    failed = _SUMMARY_FAILED.search(summary)
    passed = _SUMMARY_PASSED.search(summary)

    if errors:
        return HARNESS_FAIL, f"collection/run error: {summary}"
    if failed:
        return CAUGHT, summary
    if passed:
        return SURVIVED, summary
    return HARNESS_FAIL, f"unparseable summary: {summary!r}"


def _apply(copy_root: Path, mut: Mutation) -> str | None:
    """Apply the mutation in-place. Returns an error string, or None on success."""
    target = copy_root / mut.file
    if not target.exists():
        return f"file not found: {mut.file}"
    source = target.read_text(encoding="utf-8")
    if mut.old not in source:
        return "pattern not found"
    mutated = source.replace(mut.old, mut.new, 1)
    if mutated == source:
        return "mutation is a no-op (old == new)"
    target.write_text(mutated, encoding="utf-8")
    return None


def _repo_size_bytes() -> int:
    """Approximate on-disk size of what ``copytree`` will duplicate."""
    total = 0
    for path in REPO.rglob("*"):
        if any(part in _COPY_IGNORE for part in path.parts):
            continue
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _restore_host_install() -> None:
    """Re-point the editable install at the real repo.

    Idempotent and quiet: it runs after every mutant, including on the SKIP and
    error paths, because a half-finished sweep must not leave the developer's
    environment importing a deleted tempdir.
    """
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-e", "."],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


def _scratch_root() -> Path:
    """Where to put mutant copies.

    Not the default ``tempfile`` location: on this sandbox (and on many CI
    images) ``/tmp`` is a small tmpfs -- measured at 993 MB here, against a
    ~47 MB repo. A sweep of a dozen mutants filled it and ``copytree`` died
    with ENOSPC partway through, which surfaces as a wall of per-file errors
    rather than one clear message.

    ``FA_SWEEP_TMPDIR`` overrides; otherwise a sibling of the repo, which lives
    on the roomy filesystem the checkout is already on.
    """
    override = os.environ.get("FA_SWEEP_TMPDIR")
    root = Path(override) if override else REPO.parent / ".fa-mutation-sweep"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _require_space(root: Path, needed_bytes: int) -> str | None:
    """Fail fast and legibly rather than mid-``copytree``."""
    free = shutil.disk_usage(root).free
    if free < needed_bytes:
        return f"insufficient space in {root}: {free // 1_048_576} MiB free, need ~{needed_bytes // 1_048_576} MiB"
    return None


def run_one(mut: Mutation, *, keep: bool) -> Outcome:
    scratch = _scratch_root()
    # Repo plus the editable install's build artefacts, with headroom.
    problem = _require_space(scratch, _repo_size_bytes() * 3)
    if problem is not None:
        return Outcome(mut.mid, HARNESS_FAIL, problem, mut.rationale)
    workdir = Path(tempfile.mkdtemp(prefix=f"musweep_{mut.mid}_", dir=scratch))
    copy_root = workdir / "repo"
    try:
        shutil.copytree(REPO, copy_root, ignore=shutil.ignore_patterns(*_COPY_IGNORE))
        problem = _apply(copy_root, mut)
        if problem is not None:
            return Outcome(mut.mid, SKIP, problem, mut.rationale)

        install = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-e", "."],
            cwd=copy_root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if install.returncode != 0:
            return Outcome(mut.mid, HARNESS_FAIL, f"pip install failed: {install.stderr[-200:]}", mut.rationale)

        # Guard 1: the mutant must be what gets imported.
        probe = subprocess.run(
            [sys.executable, "-c", "import fa,sys; sys.stdout.write(fa.__file__)"],
            cwd=copy_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        root = probe.stdout.strip()
        if not root.startswith(str(copy_root)):
            return Outcome(mut.mid, HARNESS_FAIL, f"import root escaped the copy: {root}", mut.rationale)

        # The argv is a fixed literal: no value from the spec file reaches a
        # command line. That is a design decision, not a lint workaround.
        #
        # The first draft took a per-mutation ``tests`` list and splatted it
        # here, which earned an S603 ("check for execution of untrusted
        # input"). Waiving it would have been wrong twice over. First, ruff is
        # right in principle -- a JSON-supplied string was reaching argv, and
        # the rule cannot see any validation the caller might add, so the only
        # honest way to clear it is to remove the data flow. Second, and more
        # importantly, the field was **unused generality**: all 16 mutations in
        # the shipped specs passed ``["tests/"]``.
        #
        # Whole-suite is also the semantically correct oracle. The sweep asks
        # "would ANY test notice this change?" -- a per-mutation subset can only
        # narrow that question, and a mis-specified subset silently narrows it
        # to nothing, manufacturing a false SURVIVED. Deleting the field removes
        # the injection surface and the footgun together.
        #
        # (Real mutation frameworks do subset for speed, but they derive the
        # selection from coverage data rather than a hand-written list. If this
        # harness ever needs that, it should take the same route.)
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no"],
            cwd=copy_root,
            capture_output=True,
            text=True,
            timeout=2400,
            check=False,
        )
        verdict, detail = _classify(run.stdout)
        return Outcome(mut.mid, verdict, detail, mut.rationale)
    except subprocess.TimeoutExpired:
        return Outcome(mut.mid, HARNESS_FAIL, "timeout", mut.rationale)
    finally:
        # Restore the host's editable install BEFORE deleting the mutant tree.
        #
        # ``pip install -e`` above rewrites the interpreter-wide
        # ``_editable_impl_*.pth`` to point at the mutant copy. Deleting the
        # tempdir then leaves the host environment pointing at a path that no
        # longer exists, so ``import fa`` fails for every later command in the
        # session -- and a subsequent pytest run reports a *collection error*,
        # which some tools summarise as "100% killed". Measured: a
        # pytest-gremlins run right after a sweep printed
        # "Zapped: 120 gremlins (100%)" while zero tests had actually executed.
        #
        # This is the same class of bug as the two harness failures already
        # burned, so it is repaired here rather than left to the caller.
        _restore_host_install()
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="JSON file describing the mutations")
    parser.add_argument("--only", default=None, help="run a single mutation id")
    parser.add_argument("--keep", action="store_true", help="keep the mutant worktree for inspection")
    args = parser.parse_args()

    raw = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    muts = [Mutation.from_dict(item) for item in raw["mutations"]]
    if args.only:
        muts = [m for m in muts if m.mid == args.only]
        if not muts:
            print(f"no mutation with id {args.only}", file=sys.stderr)
            return 2

    print(f"sweep: {len(muts)} mutation(s) from {args.spec}\n")
    outcomes: list[Outcome] = []
    for mut in muts:
        outcome = run_one(mut, keep=args.keep)
        outcomes.append(outcome)
        marker = ">>>" if outcome.verdict == SURVIVED else "   "
        print(f"{marker} {outcome.mid:<6} {outcome.verdict:<12} {outcome.detail}")
        if outcome.verdict == SURVIVED and outcome.rationale:
            print(f"    ^ untested: {outcome.rationale}")

    survivors = [o for o in outcomes if o.verdict == SURVIVED]
    broken = [o for o in outcomes if o.verdict == HARNESS_FAIL]
    skipped = [o for o in outcomes if o.verdict == SKIP]
    print(
        f"\ncaught={len(outcomes) - len(survivors) - len(broken) - len(skipped)} "
        f"survived={len(survivors)} skipped={len(skipped)} harness-fail={len(broken)}"
    )
    # Harness failures are not "pass": an unverifiable sweep must be loud.
    return 1 if survivors or broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
