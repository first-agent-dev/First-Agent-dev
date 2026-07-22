"""S21: Kill-check tests for frozen_guard.py — AST scanner.

root=frozen_guard.py matrix=C claim=object.__setattr__ detection + TCB frozen check
kill-check=adding object.__setattr__ to TCB file → guard exits 1
path-inventory: 3 paths (clean tree, setattr fixture, unfrozen fixture)

Covers:
- Clean tree → exits 0
- object.__setattr__ call detected → exits 1
- TCB file without frozen=True → exits 1
- TCB file with __post_init__ on frozen → exits 1
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.frozen_guard import (
    scan_object_setattr,
    scan_tcb_frozen,
)


def test_clean_tree_no_violations(tmp_path: Path) -> None:
    """Clean src/fa/ → no violations."""
    src_dir = tmp_path / "src" / "fa"
    src_dir.mkdir(parents=True)
    (src_dir / "clean.py").write_text(textwrap.dedent("""\
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class Clean:
            x: int = 1
    """))
    setattr_hits = scan_object_setattr(src_dir)
    assert setattr_hits == []


def test_object_setattr_detected(tmp_path: Path) -> None:
    """object.__setattr__ call → violation found."""
    src_dir = tmp_path / "src" / "fa"
    src_dir.mkdir(parents=True)
    (src_dir / "bad.py").write_text(textwrap.dedent("""\
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class Bad:
            x: int = 1
            def __post_init__(self):
                object.__setattr__(self, "x", 42)
    """))
    setattr_hits = scan_object_setattr(src_dir)
    assert len(setattr_hits) >= 1
    assert any("bad.py" in hit[0] for hit in setattr_hits)


def test_tcb_missing_frozen_detected(tmp_path: Path) -> None:
    """TCB file with @dataclass but no frozen=True → violation."""
    tcb_file = tmp_path / "src" / "fa" / "authoring_tcb.py"
    tcb_file.parent.mkdir(parents=True)
    tcb_file.write_text(textwrap.dedent("""\
        from dataclasses import dataclass
        @dataclass
        class NotFrozen:
            x: int = 1
    """))
    repo_root = tmp_path
    tcb_hits = scan_tcb_frozen({tcb_file}, repo_root)
    assert len(tcb_hits) >= 1
    assert any("missing frozen" in hit[2] for hit in tcb_hits)


def test_tcb_post_init_on_frozen_detected(tmp_path: Path) -> None:
    """TCB file with __post_init__ on frozen dataclass → violation."""
    tcb_file = tmp_path / "src" / "fa" / "feature_flags.py"
    tcb_file.parent.mkdir(parents=True)
    tcb_file.write_text(textwrap.dedent("""\
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class WithPostInit:
            x: int = 1
            def __post_init__(self):
                pass
    """))
    repo_root = tmp_path
    tcb_hits = scan_tcb_frozen({tcb_file}, repo_root)
    assert len(tcb_hits) >= 1
    assert any("__post_init__" in hit[2] for hit in tcb_hits)
