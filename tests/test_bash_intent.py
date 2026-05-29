"""Unit tests for :mod:`fa.inner_loop.bash_intent`.

These tests pin the IntentGuard-specific bash effect classifier to the
agreed contract:

- READ_ONLY / VERIFY_ONLY commands stay outside the draft-first gate;
- INDEX_WRITE reuses the current staged snapshot semantics;
- REPO_WRITE requires a draft and may project high-confidence paths;
- OPAQUE_EXEC is the conservative fallback for unsupported or ambiguous
  execution forms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.bash_intent import (
    BashIntentEffect,
    analyze_bash_for_intent,
)
from fa.hygiene.pr_intent import StagedPath


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "src" / "fa").mkdir(parents=True)
    (tmp_path / "src" / "fa" / "existing.py").write_text("a\n", encoding="utf-8")
    (tmp_path / "old.py").write_text("old\n", encoding="utf-8")
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ls -la", BashIntentEffect.READ_ONLY),
        ("/bin/cat README.md", BashIntentEffect.READ_ONLY),
        ("git status --short", BashIntentEffect.READ_ONLY),
        ("git diff --stat", BashIntentEffect.READ_ONLY),
        ("grep foo file | wc -l", BashIntentEffect.READ_ONLY),
        ("tee", BashIntentEffect.READ_ONLY),
        ("echo hello > /dev/null", BashIntentEffect.READ_ONLY),
    ],
)
def test_analyze_bash_read_only_commands(command: str, expected: BashIntentEffect, repo_root: Path) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is expected
    assert analysis.projected == ()


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "PYTEST_ADDOPTS=-q pytest",
        "python -m pytest -q",
        "python3 -m pytest -q",
        "ruff check .",
        "ruff format --check .",
        "mypy src",
    ],
)
def test_analyze_bash_verify_only_commands(command: str, repo_root: Path) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.VERIFY_ONLY
    assert analysis.projected == ()


@pytest.mark.parametrize(
    "command",
    [
        "ruff check --fix .",
        "python -m ruff check --fix .",
        "ruff format .",
        "./pytest -q",
        "python_evil -m pytest",
        "git remote add origin https://example.invalid/repo.git",
        "git branch -D feature-x",
        "make test",
        "npm run build",
    ],
)
def test_analyze_bash_non_verify_commands_fall_back_to_opaque(command: str, repo_root: Path) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.OPAQUE_EXEC


@pytest.mark.parametrize(
    ("command", "expected_paths"),
    [
        (
            "printf 'x\\n' > src/fa/new.py",
            (StagedPath("A", "src/fa/new.py"),),
        ),
        (
            "python -m pytest --version > reports/pytest.txt",
            (StagedPath("A", "reports/pytest.txt"),),
        ),
        (
            "tee src/fa/new.py",
            (StagedPath("A", "src/fa/new.py"),),
        ),
        (
            "mkdir -p src/fa/generated",
            (StagedPath("A", "src/fa/generated/"),),
        ),
        (
            "rm src/fa/existing.py",
            (StagedPath("D", "src/fa/existing.py"),),
        ),
        (
            "mv old.py src/fa/moved.py",
            (StagedPath("D", "old.py"), StagedPath("A", "src/fa/moved.py")),
        ),
        (
            "sed -i s/a/b/ src/fa/existing.py",
            (StagedPath("M", "src/fa/existing.py"),),
        ),
    ],
)
def test_analyze_bash_repo_write_commands(
    command: str,
    expected_paths: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.REPO_WRITE
    assert analysis.projected == expected_paths


@pytest.mark.parametrize(
    "command",
    [
        "git add src/fa/existing.py",
        "git commit -m 'msg'",
        "git add . && git commit -m 'msg'",
    ],
)
def test_analyze_bash_index_write_commands(command: str, repo_root: Path) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.INDEX_WRITE
    assert analysis.projected == ()


@pytest.mark.parametrize(
    "command",
    [
        'python -c "import pathlib; pathlib.Path(\"src/fa/x.py\").write_text(\"x\")"',
        "python tools/generate.py",
        "bash scripts/gen.sh",
        "make build",
        'echo "unterminated',
        "f() { touch evil; }; f",
        "printf x > $OUT",
        "git add . && python -c 'print(1)'",
    ],
)
def test_analyze_bash_opaque_exec_commands(command: str, repo_root: Path) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.OPAQUE_EXEC


def test_analyze_bash_compound_read_then_repo_write_reduces_to_repo_write(repo_root: Path) -> None:
    analysis = analyze_bash_for_intent("cat foo && rm src/fa/existing.py", repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.REPO_WRITE
    assert analysis.projected == (StagedPath("D", "src/fa/existing.py"),)


def test_analyze_bash_git_unknown_write_subcommand_defaults_to_opaque(repo_root: Path) -> None:
    analysis = analyze_bash_for_intent("git checkout -b feature", repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.OPAQUE_EXEC


def test_analyze_bash_env_wrapper_preserves_verify_classification(repo_root: Path) -> None:
    analysis = analyze_bash_for_intent("env PYTHONPATH=src pytest -q", repo_root=repo_root)
    assert analysis.effect is BashIntentEffect.VERIFY_ONLY
