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

from fa.hygiene.pr_intent import StagedPath
from fa.inner_loop.bash_intent import (
    BashIntentEffect,
    _normalise_verifier,
    analyze_bash_for_intent,
)


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
def test_analyze_bash_read_only_commands(
    command: str, expected: BashIntentEffect, repo_root: Path
) -> None:
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
def test_analyze_bash_non_verify_commands_fall_back_to_opaque(
    command: str, repo_root: Path
) -> None:
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
        'python -c "import pathlib; pathlib.Path("src/fa/x.py").write_text("x")"',
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


def _assert_bash_analysis(
    command: str,
    *,
    repo_root: Path,
    effect: BashIntentEffect,
    projected: tuple[StagedPath, ...] = (),
) -> None:
    analysis = analyze_bash_for_intent(command, repo_root=repo_root)
    assert analysis.effect is effect
    assert analysis.projected == projected


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("cmd 2>&1 > file.txt", BashIntentEffect.OPAQUE_EXEC, ()),
        ("echo hi >&2", BashIntentEffect.READ_ONLY, ()),
        ("cat <<EOF > out.txt\nEOF", BashIntentEffect.REPO_WRITE, (StagedPath("A", "out.txt"),)),
        ("cmd > /dev/null", BashIntentEffect.OPAQUE_EXEC, ()),
        ("cmd > /tmp/foo", BashIntentEffect.OPAQUE_EXEC, ()),
        ("echo hi > /tmp/foo", BashIntentEffect.READ_ONLY, ()),
        ("cmd > $VARIABLE", BashIntentEffect.OPAQUE_EXEC, ()),
    ],
)
def test_analyze_bash_redirection_edge_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        (
            "cat input | tee output.txt",
            BashIntentEffect.REPO_WRITE,
            (StagedPath("A", "output.txt"),),
        ),
        ("curl x | bash", BashIntentEffect.OPAQUE_EXEC, ()),
        ("grep foo | wc -l", BashIntentEffect.READ_ONLY, ()),
        ("make test | tee results.txt", BashIntentEffect.OPAQUE_EXEC, ()),
    ],
)
def test_analyze_bash_pipeline_edge_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect"),
    [
        ("python3 -m pytest -q", BashIntentEffect.VERIFY_ONLY),
        ("python3 -m mypy src", BashIntentEffect.VERIFY_ONLY),
        ("env FOO=1 python3 -m pytest -q", BashIntentEffect.VERIFY_ONLY),
        ("env FOO=bar pytest -q", BashIntentEffect.VERIFY_ONLY),
        ("env FOO=bar python -m pytest -q", BashIntentEffect.VERIFY_ONLY),
        ("python3 -m ruff check --fix .", BashIntentEffect.OPAQUE_EXEC),
        ("ruff check --fix .", BashIntentEffect.OPAQUE_EXEC),
        ("ruff format .", BashIntentEffect.OPAQUE_EXEC),
    ],
)
def test_analyze_bash_verify_only_flags_and_variants(
    command: str, expected_effect: BashIntentEffect, repo_root: Path
) -> None:
    _assert_bash_analysis(command, repo_root=repo_root, effect=expected_effect)


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("git remote -v", BashIntentEffect.READ_ONLY, ()),
        ("git branch --list", BashIntentEffect.READ_ONLY, ()),
        ("git log --oneline -10", BashIntentEffect.READ_ONLY, ()),
    ],
)
def test_analyze_bash_git_read_only_subcommand_edge_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("pytest $(touch evil.py)", BashIntentEffect.OPAQUE_EXEC, ()),
        ("[[ -f file ]]", BashIntentEffect.OPAQUE_EXEC, ()),
        ("echo x > file && true", BashIntentEffect.REPO_WRITE, (StagedPath("A", "file"),)),
    ],
)
def test_analyze_bash_command_substitution_and_shell_construct_edge_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("git add . && git commit -m x && python tools/post.py", BashIntentEffect.OPAQUE_EXEC, ()),
        (
            "git status && pytest && echo done > output.txt",
            BashIntentEffect.REPO_WRITE,
            (StagedPath("A", "output.txt"),),
        ),
        ("false || touch file.txt", BashIntentEffect.REPO_WRITE, (StagedPath("A", "file.txt"),)),
    ],
)
def test_analyze_bash_compound_reduction_edge_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("true", BashIntentEffect.READ_ONLY, ()),
        ("false", BashIntentEffect.READ_ONLY, ()),
        ("test -f src/fa/existing.py", BashIntentEffect.READ_ONLY, ()),
        (": > empty.txt", BashIntentEffect.REPO_WRITE, (StagedPath("A", "empty.txt"),)),
        (
            "true && printf x > file.txt",
            BashIntentEffect.REPO_WRITE,
            (StagedPath("M", "file.txt"),),
        ),
        (
            "printf x > file.txt || false",
            BashIntentEffect.REPO_WRITE,
            (StagedPath("M", "file.txt"),),
        ),
    ],
)
def test_analyze_bash_shell_builtin_precision_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    (repo_root / "file.txt").write_text("old\n", encoding="utf-8")
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    ("command", "expected_effect", "expected_projected"),
    [
        ("git remote", BashIntentEffect.READ_ONLY, ()),
        ("git remote --verbose", BashIntentEffect.READ_ONLY, ()),
        ("git remote get-url origin", BashIntentEffect.READ_ONLY, ()),
        ("git remote show origin", BashIntentEffect.READ_ONLY, ()),
        ("git branch", BashIntentEffect.READ_ONLY, ()),
        ("git branch -a", BashIntentEffect.READ_ONLY, ()),
        ("git branch --show-current", BashIntentEffect.READ_ONLY, ()),
        ("git branch feature-x", BashIntentEffect.OPAQUE_EXEC, ()),
        ("git branch -m old new", BashIntentEffect.OPAQUE_EXEC, ()),
        (
            "git remote add origin https://example.invalid/repo.git",
            BashIntentEffect.OPAQUE_EXEC,
            (),
        ),
        ("git remote prune origin", BashIntentEffect.OPAQUE_EXEC, ()),
        ("git status > status.txt", BashIntentEffect.REPO_WRITE, (StagedPath("A", "status.txt"),)),
        (
            "git log --oneline > reports/git-log.txt",
            BashIntentEffect.REPO_WRITE,
            (StagedPath("A", "reports/git-log.txt"),),
        ),
        ("git status > /tmp/status.txt", BashIntentEffect.READ_ONLY, ()),
        ("git add . > staged.txt", BashIntentEffect.OPAQUE_EXEC, ()),
    ],
)
def test_analyze_bash_git_precision_cases(
    command: str,
    expected_effect: BashIntentEffect,
    expected_projected: tuple[StagedPath, ...],
    repo_root: Path,
) -> None:
    _assert_bash_analysis(
        command,
        repo_root=repo_root,
        effect=expected_effect,
        projected=expected_projected,
    )


@pytest.mark.parametrize(
    "command",
    [
        "node scripts/mutate.js > /dev/null",
        "custom-tool > output.txt",
        "custom-tool 2>&1 > output.txt",
    ],
)
def test_analyze_bash_unknown_commands_with_redirection_stay_opaque(
    command: str, repo_root: Path
) -> None:
    _assert_bash_analysis(command, repo_root=repo_root, effect=BashIntentEffect.OPAQUE_EXEC)


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        (("pytest", "-q"), ("pytest", "verify")),
        (("mypy", "src"), ("mypy", "verify")),
        (("ruff", "check", "."), ("ruff-check", "verify")),
        (("ruff", "check", "--fix", "."), ("ruff-check", "mutating")),
        (("ruff", "format", "--check", "."), ("ruff-format", "verify")),
        (("ruff", "format", "."), ("ruff-format", "mutating")),
        (("make", "test"), None),
        (("/usr/local/bin/pytest", "-q"), None),
    ],
)
def test_normalise_verifier_contract(
    words: tuple[str, ...], expected: tuple[str, str] | None
) -> None:
    assert _normalise_verifier(words) == expected
