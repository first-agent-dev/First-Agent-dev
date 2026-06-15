"""CI gate for internal documentation link integrity.

Mirrors ``tests/test_deploy_scripts.py``: a cheap, offline, deterministic guard
that runs in the suite (and thus in CI via ``just check``). It fails if any
actively-maintained Markdown doc contains a dangling *relative file* link —
the class of breakage a doc move/rename/prune introduces.

Legacy doc trees with pre-existing debt are excluded by the checker itself
(``scripts/check_doc_links.py`` ``_LEGACY_SKIP``); this test asserts the rest of
the repo stays clean, and that the instruction docs pass even strict anchor
validation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHECKER = _REPO_ROOT / "scripts" / "check_doc_links.py"
_INSTRUCTIONS = _REPO_ROOT / "knowledge" / "instructions"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CHECKER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )


def test_repo_has_no_broken_internal_file_links() -> None:
    result = _run()  # whole-repo, legacy trees excluded, file-existence only
    assert result.returncode == 0, result.stdout + result.stderr


def test_instruction_docs_pass_strict_anchor_validation() -> None:
    docs = [
        str(_INSTRUCTIONS / "README.md"),
        str(_INSTRUCTIONS / "01-install.md"),
        str(_INSTRUCTIONS / "02-operations.md"),
        str(_REPO_ROOT / "knowledge" / "pr-notes" / "README.md"),
    ]
    result = _run("--anchors", *docs)
    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_detects_a_broken_link(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("[x](./nope-missing.md)\n", encoding="utf-8")
    result = _run(str(bad))
    assert result.returncode == 1
    assert "broken link target" in result.stderr


def test_checker_detects_broken_link_with_title(tmp_path: Path) -> None:
    """A broken link carrying a "title" must not slip past the target regex."""
    bad = tmp_path / "titled.md"
    bad.write_text('[x](./nope-missing.md "a title")\n', encoding="utf-8")
    result = _run(str(bad))
    assert result.returncode == 1
    assert "nope-missing.md" in result.stderr


def test_explicit_legacy_file_is_skipped_unless_all() -> None:
    """The pre-commit hook passes filenames; touching a known-debt doc must not
    block the commit on pre-existing breakage. ``--all`` overrides."""
    legacy = _REPO_ROOT / "knowledge" / "trace" / "exploration_log.md"
    if not legacy.exists():  # pragma: no cover - repo layout guard
        return
    skipped = _run(str(legacy))
    assert skipped.returncode == 0, skipped.stdout + skipped.stderr
    forced = _run("--all", str(legacy))
    assert forced.returncode == 1


def test_link_syntax_inside_inline_code_is_ignored(tmp_path: Path) -> None:
    """Example link syntax in `backticks` is documentation, not a live link."""
    src = tmp_path / "doc.md"
    src.write_text(
        "A doc may show `](../X)` as an example without it being checked.\n",
        encoding="utf-8",
    )
    result = _run(str(src))
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_link_on_same_line_as_inline_code_still_checked(tmp_path: Path) -> None:
    src = tmp_path / "doc.md"
    src.write_text("[x](./missing.md) next to `](../X)` example\n", encoding="utf-8")
    result = _run(str(src))
    assert result.returncode == 1
    assert "missing.md" in result.stderr


def test_checker_accepts_valid_link_with_title_and_fragment(tmp_path: Path) -> None:
    target = tmp_path / "real.md"
    target.write_text("# Heading Here\n", encoding="utf-8")
    src = tmp_path / "src.md"
    src.write_text('[a](./real.md "ok")\n[b](./real.md#heading-here)\n', encoding="utf-8")
    result = _run("--anchors", str(src))
    assert result.returncode == 0, result.stdout + result.stderr
