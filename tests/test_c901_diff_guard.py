"""Fast diff guard: do not add new Ruff C901 suppressions.

The former complexity ratchet counted legacy suppressions and ran Ruff over
all of ``src/fa``. This guard has a narrower job: inspect every Python file in
the committed branch delta plus staged, unstaged, and untracked changes, and
reject any C901 ``noqa`` not on the explicit legacy allowlist. It does not
measure or constrain legacy complexity.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import tokenize
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
Marker = tuple[str, str]

# (repository-relative path, exact stripped source line). Occurrence counts
# matter: duplicating an allowlisted line in a changed file is still new.
# Remove an entry when its legacy suppression is retired.
LEGACY_C901_NOQA: tuple[Marker, ...] = (
    (
        "src/fa/inner_loop/coder_loop.py",
        "def _drive_session_inner(  # noqa: C901 -- complexity from top-level loop, documented",
    ),
    ("src/fa/inner_loop/tools/managed_subagent.py", "def build_managed_subagent_tool(  # noqa: C901"),
    (
        "src/fa/inner_loop/tools/managed_subagent.py",
        "def handler(params: Mapping[str, object]) -> ToolResult:  # noqa: C901",
    ),
    (
        "src/fa/inner_loop/tools/observability.py",
        "def build_list_tasks_tool(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, "
        "will split Phase 3 per Paper 2 §4.4",
    ),
    (
        "src/fa/memory/fts_index.py",
        "def index_repo(  # noqa: C901 -- complexity from 24h check + pattern matching + mtime + stale cleanup, "
        "split into helpers",
    ),
    ("src/fa/sandbox/classifier.py", "def classify_command(command: str) -> BashCategory:  # noqa: C901"),
    (
        "src/fa/skills/loader.py",
        "def _handrolled_parse(raw: str) -> dict[str, Any]:  # noqa: C901 -- complexity from fallback chain "
        "graceful degradation, documented, will split Phase 3 per Paper 2 §4.4",
    ),
    (
        "src/fa/skills/loader.py",
        "def should_load_skill(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, "
        "will split Phase 3 per Paper 2 §4.4",
    ),
    ("src/fa/verifier/verify_action.py", "def load_contract(text: str) -> VerifierContract:  # noqa: C901"),
    (
        "tests/test_execution_composition.py",
        "def test_subagent_commands_carry_no_proxy_credential(  # noqa: C901 -- "
        "intentional production-caller mode matrix",
    ),
    (
        "tests/test_workspace_bootstrap.py",
        "def test_every_reason_code_has_exact_status_repair_and_marker_contract(  # noqa: C901 - "
        "explicit closed-reason matrix.",
    ),
)

_NOQA_DIRECTIVE = re.compile(
    r"#\s*noqa\b(?:\s*:\s*(?P<codes>[A-Z][A-Z0-9]*(?:\s*,\s*[A-Z][A-Z0-9]*)*))?",
    re.IGNORECASE,
)


def _git_output(repo_root: Path, *args: str) -> bytes:
    """Run one bounded list-form Git command; a failed diff must fail the gate."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AssertionError(f"could not run git {' '.join(args[:2])}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise AssertionError(f"git {' '.join(args[:2])} exited {result.returncode}: {detail}")
    return result.stdout


def _base_candidates(repo_root: Path) -> tuple[str, ...]:
    """Resolve the PR/push base, with local-main fallbacks for developer runs."""
    event_base = os.environ.get("C901_DIFF_BASE")
    if event_base is not None:
        if re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", event_base) is None:
            raise AssertionError("C901_DIFF_BASE must be a full Git object id")
        if event_base == "0" * len(event_base):
            raise AssertionError("C901_DIFF_BASE cannot be the all-zero event sentinel")
        return (event_base,)

    explicit = os.environ.get("GITHUB_BASE_REF") or os.environ.get("BASE_REF")
    candidates: list[str] = []
    if explicit and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", explicit):
        candidates.extend((f"origin/{explicit}", explicit))

    event = os.environ.get("GITHUB_EVENT_NAME", "")
    branch = _git_output(repo_root, "branch", "--show-current").decode("utf-8", errors="strict").strip()
    if event == "push" or branch in {"main", "master"}:
        candidates.extend(("HEAD^", "origin/main", "main"))
    else:
        candidates.extend(("origin/main", "main", "HEAD^"))
    return tuple(dict.fromkeys(candidates))


def _resolve_diff_base(repo_root: Path, candidates: Iterable[str]) -> str:
    """Return the merge-base commit; never turn missing Git history into a pass."""
    for ref in candidates:
        try:
            result = subprocess.run(
                ["git", "merge-base", "HEAD", ref],
                cwd=repo_root,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AssertionError(f"could not resolve git merge-base for {ref!r}: {error}") from error
        if result.returncode == 0:
            try:
                base = result.stdout.decode("ascii", errors="strict").strip()
            except UnicodeDecodeError as error:
                raise AssertionError("git merge-base returned a non-ASCII commit id") from error
            if base:
                return base
    tried = ", ".join(repr(ref) for ref in candidates)
    raise AssertionError(f"could not resolve a merge base for the C901 diff scan (tried {tried})")


def _decode_paths(payload: bytes, *, command: str) -> set[str]:
    try:
        return {item.decode("utf-8", errors="strict") for item in payload.split(b"\0") if item}
    except UnicodeDecodeError as error:
        raise AssertionError(f"git {command} returned a non-UTF-8 path") from error


def _changed_python_sources(
    repo_root: Path,
    *,
    base_candidates: Iterable[str] | None = None,
) -> dict[str, str]:
    """Read every changed Python file, including branch, index, worktree, and untracked files."""
    root = repo_root.resolve()
    candidates = tuple(base_candidates) if base_candidates is not None else _base_candidates(root)
    base = _resolve_diff_base(root, candidates)
    diff_filter = "--diff-filter=ACMRT"
    path_sets = (
        (
            "committed diff",
            _git_output(root, "diff", "--name-only", "-z", diff_filter, f"{base}...HEAD", "--"),
        ),
        (
            "staged diff",
            _git_output(root, "diff", "--cached", "--name-only", "-z", diff_filter, "HEAD", "--"),
        ),
        ("worktree diff", _git_output(root, "diff", "--name-only", "-z", diff_filter, "--")),
        ("untracked files", _git_output(root, "ls-files", "--others", "--exclude-standard", "-z")),
    )

    names: set[str] = set()
    for label, payload in path_sets:
        names.update(_decode_paths(payload, command=label))

    sources: dict[str, str] = {}
    for name in sorted(names):
        if not name.endswith(".py"):
            continue
        candidate = root / name
        if not candidate.exists():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            relative = resolved.relative_to(root).as_posix()
        except (OSError, ValueError) as error:
            raise AssertionError(
                f"changed Python path escapes the repository or cannot be resolved: {name!r}"
            ) from error
        if not resolved.is_file():
            continue
        try:
            sources[relative] = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise AssertionError(f"could not read changed Python file {relative}: {error}") from error
    return sources


def _is_c901_noqa(comment: str) -> bool:
    """Recognize explicit C901 selectors and bare noqa directives (which suppress all rules)."""
    match = _NOQA_DIRECTIVE.match(comment)
    if match is None:
        return False
    codes = match.group("codes")
    if codes is None:
        return True
    return "C901" in {code.strip().upper() for code in codes.split(",")}


def _marker_inventory(sources: dict[str, str]) -> Counter[Marker]:
    markers: Counter[Marker] = Counter()
    for relative, source in sources.items():
        lines = source.splitlines()
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT or not _is_c901_noqa(token.string):
                    continue
                markers[(relative, lines[token.start[0] - 1].strip())] += 1
        except (IndentationError, tokenize.TokenError) as error:
            raise AssertionError(f"could not tokenize changed Python file {relative}: {error}") from error
    return markers


def _new_c901_markers(
    sources: dict[str, str],
    *,
    legacy: Iterable[Marker] = LEGACY_C901_NOQA,
) -> Counter[Marker]:
    """Return changed-file C901 suppressions not covered by the counted legacy allowlist."""
    return _marker_inventory(sources) - Counter(legacy)


def test_no_new_c901_noqa_in_python_diff() -> None:
    """C0: scan the local/branch diff; CI wiring is temporarily deferred."""
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true" and not os.environ.get("C901_DIFF_BASE"):
        pytest.skip("temporary: re-enable the CI diff scan with the separately authorized workflow update")
    sources = _changed_python_sources(REPO_ROOT)
    unexpected = _new_c901_markers(sources)
    assert not unexpected, (
        "new C901 suppressions are not allowed; decompose the function or review and add an exact legacy entry:\n"
        + "".join(f"  {path}: {line}\n" for (path, line), count in sorted(unexpected.items()) for _ in range(count))
    )


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        ("# noqa: C901", True),
        ("# NOQA: F401, C901 -- reviewed reason", True),
        ("# noqa: C901 - reviewed reason", True),
        ("# noqa", True),
        ("# noqa: F401 -- C901 appears only in the explanation", False),
        ("# noqa: E501", False),
        ("# not-noqa: C901", False),
    ],
)
def test_c901_noqa_comment_classifier(comment: str, expected: bool) -> None:
    assert _is_c901_noqa(comment) is expected


def _init_synthetic_repo(repo_root: Path) -> None:
    repo_root.mkdir()
    _git_output(repo_root, "init", "--quiet", "-b", "main")
    _git_output(repo_root, "config", "user.email", "c901-guard@example.invalid")
    _git_output(repo_root, "config", "user.name", "C901 diff guard tests")
    (repo_root / "src").mkdir()
    (repo_root / "tests").mkdir()


def _commit_all(repo_root: Path, message: str) -> None:
    _git_output(repo_root, "add", "--all")
    _git_output(repo_root, "commit", "--quiet", "-m", message)


def test_diff_scanner_checks_committed_staged_unstaged_and_untracked_python(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_synthetic_repo(repo)
    legacy_line = "def legacy() -> None:  # noqa: C901"
    legacy_file = repo / "src" / "legacy.py"
    legacy_file.write_text(f"{legacy_line}\n", encoding="utf-8")
    (repo / "src" / "staged.py").write_text("value = 0\n", encoding="utf-8")
    _commit_all(repo, "base")
    _git_output(repo, "switch", "--quiet", "-c", "feature")

    legacy_file.write_text(
        f"{legacy_line}\n"
        "def committed() -> None:  # noqa: C901, E501 -- branch addition\n"
        "literal = '# noqa: C901'\n"
        "other = 1  # noqa: F401 -- C901 is prose, not a selector\n",
        encoding="utf-8",
    )
    _commit_all(repo, "committed suppression")

    staged_file = repo / "tests" / "staged.py"
    staged_file.write_text("value = 1  # noqa: C901 -- staged addition\n", encoding="utf-8")
    _git_output(repo, "add", "tests/staged.py")

    (repo / "src" / "staged.py").write_text("value = 2  # noqa: C901 -- unstaged addition\n", encoding="utf-8")
    (repo / "tests" / "untracked.py").write_text("value = 3  # noqa: C901 -- untracked addition\n", encoding="utf-8")

    sources = _changed_python_sources(repo, base_candidates=("main",))
    unexpected = _new_c901_markers(sources, legacy=(("src/legacy.py", legacy_line),))
    assert unexpected == Counter(
        {
            ("src/legacy.py", "def committed() -> None:  # noqa: C901, E501 -- branch addition"): 1,
            ("tests/staged.py", "value = 1  # noqa: C901 -- staged addition"): 1,
            ("src/staged.py", "value = 2  # noqa: C901 -- unstaged addition"): 1,
            ("tests/untracked.py", "value = 3  # noqa: C901 -- untracked addition"): 1,
        }
    )


def test_push_event_base_includes_every_commit_in_the_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_synthetic_repo(repo)
    (repo / "src" / "base.py").write_text("value = 0\n", encoding="utf-8")
    _commit_all(repo, "base")
    base_sha = _git_output(repo, "rev-parse", "HEAD").decode("ascii").strip()
    _git_output(repo, "switch", "--quiet", "-c", "feature")

    marker = "def pushed() -> None:  # noqa: C901"
    (repo / "src" / "first.py").write_text(f"{marker}\n", encoding="utf-8")
    _commit_all(repo, "first pushed commit")
    (repo / "src" / "second.py").write_text("value = 2\n", encoding="utf-8")
    _commit_all(repo, "second pushed commit")

    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("C901_DIFF_BASE", base_sha)
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("BASE_REF", raising=False)

    sources = _changed_python_sources(repo)
    assert set(sources) == {"src/first.py", "src/second.py"}
    assert _new_c901_markers(sources) == Counter({("src/first.py", marker): 1})


def test_duplicate_of_legacy_suppression_is_still_new(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_synthetic_repo(repo)
    legacy_line = "value = 1  # noqa: C901"
    source = repo / "src" / "legacy.py"
    source.write_text(f"{legacy_line}\n", encoding="utf-8")
    _commit_all(repo, "base")
    _git_output(repo, "switch", "--quiet", "-c", "feature")
    source.write_text(f"{legacy_line}\n{legacy_line}\n", encoding="utf-8")
    _commit_all(repo, "duplicate legacy marker")

    sources = _changed_python_sources(repo, base_candidates=("main",))
    unexpected = _new_c901_markers(sources, legacy=(("src/legacy.py", legacy_line),))
    assert unexpected == Counter({("src/legacy.py", legacy_line): 1})


def test_missing_diff_base_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    _git_output(repo, "init", "--quiet", "-b", "main")
    with pytest.raises(AssertionError, match="could not resolve a merge base"):
        _resolve_diff_base(repo, ("origin/main", "main", "HEAD^"))
