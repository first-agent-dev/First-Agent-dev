"""C1 smoke tests for targeted mutmut/semgrep scripts after _git_diff extraction.

Verifies:
- Both scripts import and honor FA_SKIP_TARGETED_* (fail-open path exits 0);
- Neither script calls git merge-base/diff inline (must use helper);
- semgrep argv uses list form, no shell=True, no space-in-argv[0];
- mutmut script's argv list for mutmut invocation is plain list-form.

Skill: tests-writing, C1 smoke (subprocess + module import + AST).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.parametrize(
    "script,envvar",
    [
        ("scripts/run_targeted_mutmut.py", "FA_SKIP_TARGETED_MUTATION"),
        ("scripts/run_targeted_semgrep.py", "FA_SKIP_TARGETED_SEMGREP"),
    ],
)
def test_skip_env_exits_zero(script: str, envvar: str) -> None:
    env = os.environ.copy()
    env[envvar] = "1"
    r = subprocess.run(
        [sys.executable, script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"{script} should exit 0 when {envvar}=1; stderr={r.stderr}"
    assert "fail-open" in r.stderr.lower() or "skipping" in r.stderr.lower()


def _no_inline_git_subprocess(path: Path) -> None:
    """Assert the script does NOT build a subprocess argv containing git
    merge-base/diff tokens. Docstrings may legitimately mention 'merge-base',
    so we walk Call nodes only, not every string constant."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Look at the first positional arg of any subprocess.run/Popen/check_call
        fn = node.func
        is_subprocess_call = (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id in {"subprocess"}
            and fn.attr in {"run", "Popen", "call", "check_call", "check_output"}
        )
        if not is_subprocess_call or not node.args:
            continue
        first = node.args[0]
        argv_strings: set[str] = set()
        if isinstance(first, (ast.List, ast.Tuple)):
            for el in first.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    argv_strings.add(el.value)
        assert "merge-base" not in argv_strings and "--name-only" not in argv_strings, (
            f"{path.name}: calls git merge-base/diff directly; must delegate to scripts._git_diff"
        )
        has_shell_true = any(
            kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in node.keywords
        )
        assert not has_shell_true


def test_no_inline_merge_base_in_targeted_scripts() -> None:
    """Regression: the shared helper owns all git subprocess invocations."""
    for fname in ("run_targeted_mutmut.py", "run_targeted_semgrep.py"):
        _no_inline_git_subprocess(SCRIPTS / fname)


def test_semgrep_argv_builder_is_clean() -> None:
    from scripts import run_targeted_semgrep as rs

    argv = rs._build_semgrep_argv(pin="1.172.0", pos_args=["a.py"])
    assert isinstance(argv, list)
    assert all(isinstance(x, str) for x in argv)
    assert " " not in argv[0], f"argv[0] must not be shell fragment: {argv[0]!r}"


def test_no_shell_true_in_targeted_scripts() -> None:
    for fname in ("run_targeted_mutmut.py", "run_targeted_semgrep.py", "_git_diff.py"):
        tree = ast.parse((SCRIPTS / fname).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in getattr(node, "keywords", ()):
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        raise AssertionError(f"{fname} has subprocess call with shell=True")
