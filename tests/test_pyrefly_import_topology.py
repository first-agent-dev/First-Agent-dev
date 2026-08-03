"""Tests for pyrefly import-topology configuration (PY1/PY2 closure).

These tests verify that the pyrefly configuration correctly resolves
tests.* and scripts.* imports through the repository root search path.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pyrefly_config() -> dict[str, Any]:
    """Parse the ``[tool.pyrefly]`` table.

    Parsed with ``tomllib`` rather than substring-matched against the raw file.
    A substring test cannot tell configuration from prose: both checks below
    used to pass on a *commented-out* setting, or on the word appearing in an
    unrelated paragraph — and this file is full of explanatory comments that
    mention these exact keys.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return dict(tomllib.load(handle).get("tool", {}).get("pyrefly", {}))


def test_pyrefly_config_has_search_path() -> None:
    """C1 (F1): pyrefly resolves ``tests.*`` / ``scripts.*`` via the repo-root search path.

    Oracle: the parsed value of ``[tool.pyrefly] search-path``.

    **Rewritten because the original could not fail (F1 review).** It read:

        assert 'search-path = ["src", "."]' in content or "search-path" in content

    The second disjunct subsumes the first, so the whole assertion reduced to
    "the string ``search-path`` appears somewhere in pyproject.toml" — which
    the *comment* above the setting satisfies on its own. Deleting the actual
    configuration would have left this green. Now the value is parsed and its
    two required entries are asserted, so the check is about behaviour.
    """
    search_path = _pyrefly_config().get("search-path")
    assert search_path is not None, "[tool.pyrefly] has no search-path; tests.* and scripts.* will not resolve"
    assert "." in search_path, (
        f"[tool.pyrefly] search-path must include '.' so tests.fixtures.* and scripts.* resolve "
        f"the way pytest's pythonpath resolves them; got {search_path!r}"
    )
    assert "src" in search_path, f"[tool.pyrefly] search-path must include 'src'; got {search_path!r}"


def test_pyrefly_config_includes_scripts() -> None:
    """C1 (F1): ``scripts/`` is inside pyrefly's analysis scope.

    Oracle: the parsed ``[tool.pyrefly] project-includes`` list.

    **Rewritten for the same reason as its sibling.** The original asserted
    that the seven-character string ``"scripts"`` appeared anywhere in
    pyproject.toml — satisfied by any comment, any other tool's config, or a
    dependency named "scripts". It made no contact with pyrefly's scope.
    """
    includes = _pyrefly_config().get("project-includes")
    assert includes is not None, "[tool.pyrefly] has no project-includes"
    for required in ("src", "tests", "scripts"):
        assert required in includes, (
            f"[tool.pyrefly] project-includes must contain {required!r} or that tree is never "
            f"type-checked; got {includes!r}"
        )


def test_pyrefly_is_installed() -> None:
    """C1 (F1 / Q51): pyrefly is importable, so the gate below can actually run.

    **This test exists because its absence let a red gate read as green.**
    ``test_pyrefly_check_passes`` used to score a *missing* pyrefly as a pass:
    it filtered stdout for lines starting with ``ERROR`` and ignored the
    return code, so an absent module produced ``returncode=1, stdout=''`` →
    zero ERROR lines → assertion satisfied. Measured directly, not reasoned
    about: running a nonexistent module returns exactly that shape.

    The consequence was not hypothetical. The sandbox for several slices had
    no ``pyrefly`` installed, the gate passed silently throughout, and four
    real type errors accumulated undetected until the environment was rebuilt
    with ``uv sync --extra dev``.

    Separating "the tool ran" from "the tool was happy" is the fix (Q51:
    **fail loudly** — a gate that cannot run is a gate that failed). This one
    names the missing dependency and how to get it; the next one judges the
    code. A single combined test cannot report those two failures distinctly.

    Oracle: ``importlib.util.find_spec`` — checked in-process rather than by
    the subprocess's exit code, so "not installed" is distinguishable from
    "installed but crashed".
    Kill-check target: uninstall pyrefly → this test fails with an actionable
    message instead of the suite going quietly green.
    """
    assert importlib.util.find_spec("pyrefly") is not None, (
        "pyrefly is not installed, so the type-check gate below cannot run.\n"
        "  It is a BLOCKING gate (Q50), not advisory — install the dev extras:\n"
        "    uv sync --frozen --extra dev\n"
        "  Do not delete or skip the gate to get a green suite."
    )


def test_pyrefly_check_passes() -> None:
    """C1 (F1 / Q50): ``pyrefly check`` reports zero errors — a BLOCKING gate.

    **Q50 (resolved 2026-08-01): this seat is blocking and the repo now says
    so.** pyrefly previously had two contradictory seats — ``advisory.yml``
    and ``just typecheck-advisory`` treated it as advisory, while this test,
    living inside ``just test``, blocked. The contradiction is resolved in
    favour of blocking, and ``pyproject.toml`` / ``justfile`` /
    ``ci-guardrails-reference.md`` were corrected to match rather than left to
    disagree with the code.

    **Three oracles, because the old single one was satisfiable by failure.**

    1. **Return code** — the primary signal, and the one the old test threw
       away. Verified empirically: pyrefly exits 0 on a clean subset and 1
       when it reports errors.
    2. **Error lines from stdout** — retained for the *message*, so a failure
       names the offending files instead of just a number.
    3. **Liveness: the summary line on stderr** — pyrefly writes
       ``INFO N errors (...)`` to **stderr**, which the old test never read.
       Asserting it appears proves pyrefly actually analysed the project. A
       crash, a bad config path, or a version whose CLI changed shape all
       produce "no ERROR lines in stdout" too, and without this the test would
       call that success.

    The three are asserted in that order so the most specific diagnosis wins.

    Oracle: exit code 0 **and** a parsed error count of 0 **and** proof the
    run happened.
    Kill-check target: introduce a type error anywhere under ``src``/``tests``
    /``scripts`` → this fails naming the file; break the config path → the
    liveness assertion fails instead of passing vacuously.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pyrefly", "check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    error_lines = [line for line in result.stdout.splitlines() if line.startswith("ERROR")]

    # Liveness first: prove pyrefly ran and produced its own summary. Without
    # this, every other assertion below is satisfiable by the tool not running.
    summary = re.search(r"^\s*INFO (\d+) errors?\b", result.stderr, re.MULTILINE)
    assert summary is not None, (
        "pyrefly produced no 'INFO <n> errors' summary on stderr, so it did not "
        "complete a project check — the result below cannot be trusted.\n"
        f"  exit code: {result.returncode}\n"
        f"  stderr (tail): {result.stderr[-2000:]!r}\n"
        f"  stdout (tail): {result.stdout[-1000:]!r}"
    )

    reported = int(summary.group(1))
    assert reported == 0 and result.returncode == 0, (
        f"pyrefly check failed: {reported} error(s), exit code {result.returncode}.\n"
        + "\n".join(error_lines[:10])
        + ("\n  ... (truncated)" if len(error_lines) > 10 else "")
    )


def test_tests_fixtures_session_wiring_importable() -> None:
    """Verify tests.fixtures.session_wiring is importable (resolves PY1)."""
    from tests.fixtures.session_wiring import (
        make_mock_chain,
        mock_success_response,
    )

    # Verify the imported symbols are callable
    assert callable(make_mock_chain)
    assert callable(mock_success_response)


def test_scripts_modules_importable() -> None:
    """Verify scripts.* modules are importable (resolves PY2)."""
    from scripts.check_dead_flags import check_dead_flags
    from scripts.compile_corrections import compile_summary
    from scripts.frozen_guard import scan_tcb_frozen

    assert callable(check_dead_flags)
    assert callable(compile_summary)
    assert callable(scan_tcb_frozen)
