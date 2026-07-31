"""Blackboard ownership checks for the mutating tools (workspace-leak protection).

History (plan §6.0.1 — legacy tests are inputs, not authority)
--------------------------------------------------------------
This file previously targeted ``write_file._check_conflict``, a private helper
that S5.4 replaced with the shared ``fa.inner_loop.tools.mutation_guard``. Its
genuine intent — *a Blackboard belonging to a different workspace must be
ignored, and the ownership check must never raise* — is preserved here against
the new seam.

One test was dropped rather than ported: ``test_expected_root_always_resolved``
asserted on the *source text* of the function via ``inspect.getsource``,
checking that one assignment appeared before another. That is test theater: it
pins an implementation detail, passes regardless of behaviour, and breaks under
any refactor (including instrumentation that merely wraps the function). The
property it was reaching for — no unbound name on any exception path — is
covered behaviourally below, since ``belongs_to_workspace`` is exercised with
inputs that drive every branch and must return a bool rather than raise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

from fa.inner_loop.tools.mutation_guard import belongs_to_workspace, check_mutation_allowed


class _FakeBlackboard:
    """Minimal stand-in: ownership is decided by ``root`` alone."""

    def __init__(self, root: Any) -> None:
        self.root = root

    def detect_conflict(self, _entry: object) -> list[object]:
        return []


class TestBlackboardOwnership:
    def test_blackboard_in_workspace_is_owned(self, tmp_path: Path) -> None:
        bb_dir = tmp_path / ".fa" / "blackboard"
        bb_dir.mkdir(parents=True)
        assert belongs_to_workspace(_FakeBlackboard(bb_dir), tmp_path) is True

    def test_blackboard_from_other_workspace_is_foreign(self, tmp_path: Path) -> None:
        other = tmp_path.parent / "other_workspace" / ".fa" / "blackboard"
        assert belongs_to_workspace(_FakeBlackboard(other), tmp_path) is False

    def test_unrelated_absolute_root_is_foreign(self, tmp_path: Path) -> None:
        assert belongs_to_workspace(_FakeBlackboard(Path("/unrelated/path/blackboard")), tmp_path) is False

    def test_unusable_root_is_foreign_not_an_exception(self, tmp_path: Path) -> None:
        """An object whose ``root`` cannot be turned into a path must not raise.

        Replaces the old source-introspection test: every failure path returns
        a bool, so no caller can hit an unbound name or an escaping error.
        """
        assert belongs_to_workspace(_FakeBlackboard(object()), tmp_path) is False
        assert belongs_to_workspace(_FakeBlackboard(None), tmp_path) is False

    def test_missing_root_attribute_is_foreign(self, tmp_path: Path) -> None:
        assert belongs_to_workspace(object(), tmp_path) is False


class TestOwnershipGatesTheConflictCheck:
    def test_absent_blackboard_permits(self, tmp_path: Path) -> None:
        assert check_mutation_allowed(None, read_set=[], write_set=["b.py"], root=tmp_path) is None

    def test_owned_blackboard_without_conflicts_permits(self, tmp_path: Path) -> None:
        bb_dir = tmp_path / ".fa" / "blackboard"
        bb_dir.mkdir(parents=True)
        result = check_mutation_allowed(_FakeBlackboard(bb_dir), read_set=["a.py"], write_set=["b.py"], root=tmp_path)
        assert result is None

    def test_foreign_blackboard_is_never_consulted(self, tmp_path: Path) -> None:
        """A foreign Blackboard must be ignored outright, not queried.

        Querying it would let another workspace's entries decide this
        workspace's writes — the leaked-contextvar hazard the check exists for.
        """
        queried = False

        class _Tripwire(_FakeBlackboard):
            @override
            def detect_conflict(self, _entry: object) -> list[object]:
                nonlocal queried
                queried = True
                return []

        foreign = _Tripwire(tmp_path.parent / "other_workspace" / ".fa" / "blackboard")
        assert check_mutation_allowed(foreign, read_set=[], write_set=["b.py"], root=tmp_path) is None
        assert queried is False, "a foreign workspace's blackboard was consulted"
