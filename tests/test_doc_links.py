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
