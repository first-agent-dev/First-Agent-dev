"""S6.1 — the contract checkers must fail when a real producer disappears.

Contract under test (S6-CT1)
----------------------------
* **type-level**: removing the *last* producer of a live kind ⇒ non-zero exit
  naming the kind. Both checkers.
* **site-level**: removing *one of several* producers ⇒ detected by
  ``check_producer_consumer_contract.py``.
* **unresolvable**: a dynamic producer the resolver cannot follow is reported
  as ``unknown`` and **fails**, never silently as ``absent``.

Why this file exists
--------------------
S3-F1 recorded that ``check_log_kind_contract.py`` produces byte-identical
output after a producer is deleted. Re-measured at S6.0, the truth is sharper
and implies a different fix: deleting a **live** producer *does* change the
output (``30 distinct kinds`` -> ``29`` plus a new dormancy line) — it just
still **exits 0**, because CHECK 2 prints orphans without incrementing
``failures`` (``:219-220``: *"soft warning, not a hard failure, unless CI is
strict"*). So the defect is an advisory-only policy, not blindness.

S6-F2 (found in review) adds that the producer/consumer checker detects
*type-level* dormancy but not *site-level* removal: deleting one of four
``api_retry`` producers is invisible.

Method note
-----------
These tests run the checkers as **subprocesses against a mutated copy of the
tree**, because that is how CI invokes them and because the scripts resolve
paths from ``__file__``. Importing and calling ``main()`` in-process would
check *this* tree, not the mutated one, and would exercise a path CI never
takes.

Test class: C0 (checker semantics) + C3 (unresolvable producer).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_KIND_CHECKER = "scripts/check_log_kind_contract.py"
PRODUCER_CHECKER = "scripts/check_producer_consumer_contract.py"

# Copying the whole tree per test is slow; only these subtrees are read by the
# checkers. ``tests`` is required: check_producer_consumer_contract.py scans it
# for C1 coverage (``:95``), so omitting it makes the checker fail on a *clean*
# tree and silently masks mutation results. Found by the clean-tree baseline
# test — which is why that baseline exists.
_COPY_PARTS = ("src", "scripts", "tests", "pyproject.toml")


def _make_tree(tmp_path: Path) -> Path:
    """Materialise a minimal, mutable copy of the repo for one experiment."""
    root = tmp_path / "tree"
    root.mkdir()
    for part in _COPY_PARTS:
        source = REPO_ROOT / part
        if not source.exists():
            continue
        target = root / part
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return root


def _run_checker(root: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _edit(root: Path, rel: str, mutate: Callable[[str], str]) -> None:
    path = root / rel
    original = path.read_text(encoding="utf-8")
    updated = mutate(original)
    assert updated != original, f"mutation was a no-op for {rel} — the test would be vacuous"
    path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Baseline — the checkers must pass on an unmutated tree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script", [LOG_KIND_CHECKER, PRODUCER_CHECKER])
def test_checker_passes_on_clean_tree(tmp_path: Path, script: str) -> None:
    """C0: a green baseline, so a later red result means the mutation caused it."""
    result = _run_checker(_make_tree(tmp_path), script)
    assert result.returncode == 0, f"{script} failed on a clean tree:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# S6-P1 — type-level: last producer removed
# ---------------------------------------------------------------------------


def test_log_kind_checker_fails_when_live_producer_removed(tmp_path: Path) -> None:
    """C0 (S6-P1): losing the last producer of a live kind must fail the build.

    ``config_warning`` is used because it is a CONSOLE_MIRROR kind with exactly
    one ``log.append`` producer, so removing it makes the kind genuinely
    orphaned rather than merely thinner.

    Kill-check target: revert CHECK 2 to print without incrementing ``failures``.
    """
    root = _make_tree(tmp_path)
    _edit(
        root,
        "src/fa/inner_loop/state.py",
        lambda s: s.replace('kind="config_warning"', 'kind="run_started"', 1),
    )

    result = _run_checker(root, LOG_KIND_CHECKER)

    assert result.returncode != 0, (
        "checker exited 0 after the last producer of a live kind was removed; "
        f"its PASS carries no information.\n{result.stdout}"
    )
    assert "config_warning" in result.stdout, "failure did not name the orphaned kind"


def test_producer_consumer_checker_fails_when_last_producer_removed(tmp_path: Path) -> None:
    """C0: the same guarantee for the EventType checker."""
    root = _make_tree(tmp_path)
    _edit(
        root,
        "src/fa/inner_loop/coder_loop.py",
        lambda s: s.replace('type="api_retry"', 'type="session_start"'),
    )

    result = _run_checker(root, PRODUCER_CHECKER)

    assert result.returncode != 0, f"removing every api_retry producer was not detected\n{result.stdout}"
    assert "api_retry" in result.stdout


# ---------------------------------------------------------------------------
# S6-P2 — site-level: one of several producers removed (S6-F2)
# ---------------------------------------------------------------------------


def test_producer_consumer_checker_detects_single_site_removal(tmp_path: Path) -> None:
    """C0 (S6-P2): a per-site regression must not hide behind its siblings.

    Measured before the fix: ``api_retry`` has four producers; deleting one left
    the output byte-identical and the exit code 0. Three of four call sites
    could rot away undetected.

    Kill-check target: restore type-level-only counting.
    """
    root = _make_tree(tmp_path)
    _edit(
        root,
        "src/fa/inner_loop/coder_loop.py",
        lambda s: s.replace('type="api_retry"', 'type="session_start"', 1),
    )

    result = _run_checker(root, PRODUCER_CHECKER)

    assert result.returncode != 0, (
        f"removing one of several producers was not detected — site-level regressions are invisible.\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# S6-P3 — dynamic producers must resolve, not be reported absent (S3-F4)
# ---------------------------------------------------------------------------


def test_dynamic_kind_local_is_resolved_not_dormant(tmp_path: Path) -> None:
    """C0 (S6-P3): ``kind=<local>`` must resolve to its literal values.

    ``spawn_subagent.py:71`` assigns
    ``kind: LogKind = "subagent_spawn_done" if ... else "subagent_spawn_fail"``
    and passes the local to ``append``. That is a real, test-covered producer;
    reporting it dormant is a false negative that trains readers to ignore the
    dormancy list.
    """
    result = _run_checker(_make_tree(tmp_path), LOG_KIND_CHECKER)

    assert "subagent_spawn_done" not in _dormant_kinds(result.stdout), (
        "a real producer behind a local variable is still reported dormant"
    )


def test_remaining_dormant_kinds_are_allowlisted_with_reasons(tmp_path: Path) -> None:
    """C0: every surviving dormant kind is a deliberate, documented decision.

    Silence is not an option: a kind is either produced, removed, or explicitly
    allowlisted with a reason. Without this, the dormancy list grows by
    accretion and stops being read.
    """
    from scripts.check_log_kind_contract import KNOWN_DORMANT_KINDS

    result = _run_checker(_make_tree(tmp_path), LOG_KIND_CHECKER)

    for kind in _dormant_kinds(result.stdout):
        assert kind in KNOWN_DORMANT_KINDS, f"{kind!r} is dormant but not allowlisted"
        assert KNOWN_DORMANT_KINDS[kind].strip(), f"{kind!r} is allowlisted with an empty reason"


def test_unallowlisted_dormant_kind_fails_the_checker(tmp_path: Path) -> None:
    """C3: fail closed — an unexplained orphan breaks the build.

    Negative proof for the allowlist: adding a LogKind with no producer and no
    allowlist entry must fail, otherwise the allowlist is decorative.
    """
    root = _make_tree(tmp_path)
    _edit(
        root,
        "src/fa/output.py",
        lambda s: s.replace("LogKind = Literal[\n", 'LogKind = Literal[\n    "s6_probe_never_produced",\n', 1),
    )

    result = _run_checker(root, LOG_KIND_CHECKER)

    assert result.returncode != 0, f"an unexplained dormant kind did not fail the checker\n{result.stdout}"
    assert "s6_probe_never_produced" in result.stdout


def _dormant_kinds(stdout: str) -> set[str]:
    """Parse the kinds the checker reported as having no producer."""
    found: set[str] = set()
    for line in stdout.splitlines():
        if "NO producer found" in line or "dormant" in line.lower():
            for token in line.split("'"):
                if token.islower() and "_" in token:
                    found.add(token)
    return found


# ---------------------------------------------------------------------------
# S6-P15 / S6-CT4 — inventory truth: no EventType without a producer
# ---------------------------------------------------------------------------


def test_producerless_event_type_fails_the_checker(tmp_path: Path) -> None:
    """C0 (S6-P15): a handler with no producer is a contract gap, not a warning.

    S3-F5's shape: a type is added to ``EventType`` with a ``_handle_*`` in
    ``ConsoleRenderer`` but nothing ever emits it. The renderer looks wired and
    is dead.

    Kill-check target: stop setting ``gaps_found`` in CHECK 1.
    """
    root = _make_tree(tmp_path)
    _add_producerless_event_type(root)

    result = _run_checker(root, PRODUCER_CHECKER)

    assert result.returncode != 0, f"a producerless EventType did not fail the checker\n{result.stdout}"
    assert "probe_no_producer" in result.stdout


def test_dormant_allowlist_requires_a_written_reason(tmp_path: Path) -> None:
    """C3 (S6-CT4): the escape hatch must cost more than one unjustified line.

    Measured before the fix: adding a bare name to ``DORMANT_TYPES`` silenced a
    genuine gap and the checker exited **0**. An allowlist anyone can extend
    without saying why is not an allowlist — it is a mute button, and it is how
    a dormancy list grows until nobody reads it.

    The fix mirrors ``KNOWN_DORMANT_KINDS`` from S6.1 (``dict[str, str]``), so
    the two checkers now agree on what an exemption looks like.

    Kill-check target: revert ``DORMANT_TYPES`` to a bare ``set``.
    """
    root = _make_tree(tmp_path)
    _add_producerless_event_type(root)
    # Silence it the lazy way: name only, no justification.
    _edit(
        root,
        "scripts/check_producer_consumer_contract.py",
        # Works against both shapes: a bare set entry today, a dict entry
        # after the fix. Either way the name is muted without a justification.
        lambda s: s.replace(
            "DORMANT_TYPES: dict[str, str] = {",
            'DORMANT_TYPES: dict[str, str] = {\n    "probe_no_producer": "",',
            1,
        ),
    )

    result = _run_checker(root, PRODUCER_CHECKER)

    assert result.returncode != 0, (
        "an EventType was muted with an empty reason and the checker passed; "
        f"the allowlist is a mute button\n{result.stdout}"
    )
    assert "probe_no_producer" in result.stdout


def test_every_dormant_entry_carries_a_reason_today(tmp_path: Path) -> None:
    """C0: the shipped allowlist itself satisfies the rule it enforces."""
    from scripts.check_producer_consumer_contract import DORMANT_TYPES

    assert DORMANT_TYPES, "allowlist unexpectedly empty — did the constant move?"
    for name, reason in DORMANT_TYPES.items():
        assert isinstance(reason, str) and reason.strip(), f"{name!r} is allowlisted with no reason"
        assert len(reason.strip()) > 20, f"{name!r} has a reason too short to be useful: {reason!r}"


def test_dormant_type_that_gains_a_producer_is_flagged(tmp_path: Path) -> None:
    """C3: the allowlist must expire when its reason stops being true.

    A dormancy entry records "no producer is expected *yet*". Once a producer
    lands, the entry is stale and must go — otherwise the type stays
    permanently exempt from CHECK 3's C1-coverage requirement and can never be
    held to the same standard as its peers.

    This failure mode did not exist for the S6.1 log-kind allowlist: a log kind
    that gains a producer simply stops being orphaned. Here the exemption also
    suppresses a *separate* check, so it has to be actively retired.
    """
    root = _make_tree(tmp_path)
    _edit(
        root,
        "src/fa/observability/cost_guardian.py",
        lambda s: s.replace(
            "from fa.inner_loop.registry import ToolResult",
            "from fa.inner_loop.registry import ToolResult\n"
            "from fa.output import OutputEvent\n\n"
            '_PROBE = OutputEvent(type="cost_alert", data={})  # emit',
            1,
        ),
    )

    result = _run_checker(root, PRODUCER_CHECKER)

    assert result.returncode != 0, (
        f"a dormant-listed EventType gained a producer and the stale allowlist entry was not flagged\n{result.stdout}"
    )
    assert "cost_alert" in result.stdout


def _add_producerless_event_type(root: Path) -> None:
    """Add an EventType with a handler and no emit — the S3-F5 shape.

    Note the name avoids digits: the checker's literal regex is ``[a-z_]+``, so
    a probe called ``s64_probe`` is invisible to it and the experiment would
    silently prove nothing. Found the hard way.
    """
    _edit(
        root,
        "src/fa/output.py",
        lambda s: s.replace("EventType = Literal[\n", 'EventType = Literal[\n    "probe_no_producer",\n', 1),
    )
    _edit(
        root,
        "src/fa/output.py",
        lambda s: s.replace(
            "    def _handle_cost_alert(self, e: OutputEvent) -> None:",
            "    def _handle_probe_no_producer(self, e: OutputEvent) -> None:\n"
            '        self._write("probe")\n\n'
            "    def _handle_cost_alert(self, e: OutputEvent) -> None:",
            1,
        ),
    )


# ---------------------------------------------------------------------------
# S6-F6 — the checker must actually run in CI
# ---------------------------------------------------------------------------


def test_log_kind_checker_is_wired_into_the_check_target() -> None:
    """C0 (S6-F6): a strict exit code is worthless if nothing invokes it.

    Measured at review: ``check_log_kind_contract.py`` appeared in neither the
    Makefile nor any workflow, while ``check_producer_consumer_contract.py``
    did. Making the former fail-closed would have changed nothing in CI.

    **The `justfile` assertion is the load-bearing one.** CI runs
    ``uv run just check`` (`.github/workflows/advisory.yml`), so a recipe that
    exists but is absent from the aggregate ``check`` target still never runs —
    which is the exact shape of the original defect. The Makefile is asserted
    too so the local convenience path does not silently diverge.
    """
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "check_log_kind_contract.py" in justfile, "no justfile recipe invokes the log-kind checker"
    assert "check_log_kind_contract.py" in makefile, "Makefile has drifted from the justfile"

    check_target = next(
        (line for line in justfile.splitlines() if line.startswith("check:")),
        "",
    )
    assert check_target, "aggregate `check` target not found in justfile"
    assert "log-kind-check" in check_target, (
        f"log-kind-check is not part of the aggregate target CI runs: {check_target!r}"
    )
