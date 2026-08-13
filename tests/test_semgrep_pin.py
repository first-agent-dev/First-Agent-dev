"""C0 parity test: semgrep pin agrees across pyproject.toml / script argv / semgrep.yml.

Single source of truth for the semgrep version pin is ``[tool.ci-pins].semgrep``
in ``pyproject.toml``. The run_targeted_semgrep.py CLI reads it at runtime and
the weekly semgrep.yml hardcodes the same value in its ``uvx --from`` argument.
If any of the three sites drift this test fails.

Skill: tests-writing, C0 (static AST + YAML + tomllib), Pyramid A.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SCRIPT = REPO_ROOT / "scripts" / "run_targeted_semgrep.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "semgrep.yml"

PIN_RE = re.compile(r"semgrep==(\d+\.\d+\.\d+)")


def _toml_pin() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    pin = data["tool"]["ci-pins"]["semgrep"]
    assert isinstance(pin, str) and re.fullmatch(r"\d+\.\d+\.\d+", pin), f"bad semgrep pin: {pin!r}"
    return pin


def _script_pin() -> str:
    """Find the semgrep version used by _build_semgrep_argv.

    The script reads the pin from pyproject.toml via ``_read_semgrep_pin()``
    and interpolates it into an f-string ``f"semgrep=={pin}"``, so the
    literal "semgrep==" is a constant but the version is a Name. Easiest
    robust check: load the module and assert that argv built from a
    known pin contains the pin.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from scripts import run_targeted_semgrep as rs

    for test_pin in ("1.172.0", "9.99.99"):
        argv = rs._build_semgrep_argv(pin=test_pin, pos_args=["x.py"])
        assert argv is not None, "test requires uvx or uv on PATH"
        joined = " ".join(argv)
        m = PIN_RE.search(joined)
        assert m is not None, f"argv does not contain semgrep==<ver>: {argv}"
        assert m.group(1) == test_pin, f"expected {test_pin} in argv, got {m.group(1)}"

    # Also confirm the module actually reads a pin from pyproject.toml at runtime.
    live = rs._read_semgrep_pin()
    assert live is not None, "run_targeted_semgrep._read_semgrep_pin() returned None"
    return live


def _workflow_pin() -> str:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    run_step = None
    for step in data["jobs"]["semgrep"]["steps"]:
        if "run" in step and "semgrep scan" in step["run"]:
            run_step = step["run"]
            break
    assert run_step is not None, "no 'semgrep scan' run step in semgrep.yml"
    m = PIN_RE.search(run_step)
    assert m, f"no semgrep==<ver> in semgrep.yml run: {run_step!r}"
    return m.group(1)


def test_semgrep_pin_parity() -> None:
    toml_pin = _toml_pin()
    script_pin = _script_pin()
    wf_pin = _workflow_pin()
    assert toml_pin == script_pin == wf_pin, (
        f"semgrep pin drift: pyproject={toml_pin} script={script_pin} workflow={wf_pin}"
    )


def test_weak_form_not_present_in_workflow() -> None:
    """The workflow must NOT use bare ``uvx semgrep`` (unpinned)."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in data["jobs"]["semgrep"]["steps"]:
        run = step.get("run", "")
        # forbid 'uvx semgrep' (i.e. uvx followed by semgrep NOT via --from)
        if "uvx semgrep" in run:
            raise AssertionError("semgrep.yml uses bare 'uvx semgrep'; pin via --from semgrep==<ver>")


def test_script_argv_is_list_of_strings() -> None:
    """_build_semgrep_argv returns a list with no space-in-argv[0] shell fragments.

    Regression test for the pre-refactor bug where _resolve_uvx returned
    ``f\"{uv} tool run\"`` as a single argv[0] string, causing FileNotFoundError.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from scripts import run_targeted_semgrep as rs

    argv = rs._build_semgrep_argv(pin="1.172.0", pos_args=["a.py"])
    assert isinstance(argv, list)
    assert all(isinstance(x, str) for x in argv)
    assert " " not in argv[0], f"argv[0] must be a single binary (no shell fragment), got {argv[0]!r}"
    assert "--from" in argv
    assert "semgrep==1.172.0" in argv
    assert "semgrep" in argv
    assert "scan" in argv
