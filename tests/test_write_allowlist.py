"""Write-allowlist path containment for role-limited ``fs_write_file`` (D6).

**Why this module exists.** ``PROFILES_RAW["planner"]["write_allowlist"]``
advertises ``[".fa/", "knowledge/research/"]``, but the enforcement closure
normalised candidate paths with ``path.lstrip("./")``. ``str.lstrip`` strips a
character *set*, not a prefix, so ``".fa/notes.md"`` became ``"fa/notes.md"``
and matched neither entry: the planner could never write to a directory its own
profile declared writable. The textual ``startswith`` check it fed also let
``"knowledge/research/../../etc/passwd"`` through on prefix alone.

Tests are labelled per the tests-writing skill:

- **C0p** — properties of :func:`is_path_within_allowlist` across the normalisation
  and containment space (leading ``./``, traversal, prefix look-alikes, absolute).
- **C1** — the live ``build_registry_for_role("planner", ...)`` registry, which is
  what ``_build_role_registry`` hands to a real session.

**Kill-checks:**
- restore ``norm = p.lstrip("./")`` + ``startswith`` →
  ``test_dotfa_prefix_is_reachable`` and ``test_planner_can_write_to_dot_fa`` fail;
- drop the strict-containment check → ``test_bare_prefix_is_not_a_target`` fails;
- hardcode the prefixes back into the closure →
  ``test_allowlist_is_read_from_profile`` fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.profiles import PROFILES_RAW, build_registry_for_role, is_path_within_allowlist

_ALLOW = ("knowledge/research/", ".fa/")


# ── C0p: containment properties ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "expected", "reason"),
    [
        (".fa/note.md", True, "the regression: lstrip('./') ate the leading dot"),
        ("./.fa/note.md", True, "explicit relative marker is normalised, not stripped char-wise"),
        (".fa/nested/deep.md", True, "nested under an allowed prefix"),
        ("knowledge/research/x.md", True, "plain allowed prefix"),
        ("knowledge/research/sub/deep.md", True, "nested under an allowed prefix"),
        ("src/fa/cli.py", False, "product source is never allowlisted"),
        ("knowledge/research/../../etc/passwd", False, "traversal escapes the subtree"),
        ("knowledge/researcher/x.md", False, "prefix look-alike is a different directory"),
        ("/etc/passwd", False, "absolute paths cannot be within a relative subtree"),
        ("../outside.md", False, "climbing above the workspace root"),
        ("..fa/x.md", False, "'..fa' is not the '.fa' directory"),
        ("", False, "empty path"),
        (".fa", False, "the directory itself is not a file target"),
        (".fa/", False, "trailing slash does not create a component below the prefix"),
        ("knowledge/research", False, "the directory itself is not a file target"),
    ],
)
def test_allowlist_containment_properties(path: str, expected: bool, reason: str) -> None:
    """C0p — component-wise containment over the normalisation space."""
    assert is_path_within_allowlist(path, _ALLOW) is expected, reason


def test_dotfa_prefix_is_reachable() -> None:
    """C0p (kill-check) — the exact defect: a dotted prefix must be matchable.

    Restoring ``p.lstrip("./")`` turns ``.fa/notes.md`` into ``fa/notes.md``
    and this assertion fails.
    """
    assert is_path_within_allowlist(".fa/notes.md", [".fa/"]) is True


def test_bare_prefix_is_not_a_target() -> None:
    """C0p (kill-check) — containment is strict; the directory itself is denied."""
    assert is_path_within_allowlist(".fa", [".fa/"]) is False
    assert is_path_within_allowlist("knowledge/research", ["knowledge/research/"]) is False


def test_traversal_cannot_escape_via_textual_prefix() -> None:
    """C0p — a path with the right textual prefix that escapes the subtree is denied."""
    assert is_path_within_allowlist("knowledge/research/../../src/fa/cli.py", _ALLOW) is False


def test_empty_allowlist_denies_everything() -> None:
    """C0p — failure-observable: no prefixes configured means no writes allowed."""
    assert is_path_within_allowlist("anything.md", []) is False


# ── C1: live planner registry ────────────────────────────────────────────────


@pytest.fixture()
def planner_write_handler(tmp_path: Path):  # type: ignore[no-untyped-def]
    """The real ``fs_write_file`` spec the planner profile builds."""
    (tmp_path / ".fa").mkdir()
    (tmp_path / "knowledge" / "research").mkdir(parents=True)
    registry = build_registry_for_role("planner", tmp_path)
    return registry.lookup("fs_write_file").handler, tmp_path


def test_planner_can_write_to_dot_fa(planner_write_handler) -> None:  # type: ignore[no-untyped-def]
    """C1 (kill-check) — the profile's ``.fa/`` entry is honoured on the live path.

    Oracle rank 5 (FS effect) plus the structured result: the write both
    succeeds and lands on disk.
    """
    handler, workspace = planner_write_handler
    result = handler({"path": ".fa/note.md", "content": "scratch"})
    assert result.error is None, f"unexpected denial: {result.error}"
    assert (workspace / ".fa" / "note.md").exists()


def test_planner_can_write_to_knowledge_research(planner_write_handler) -> None:  # type: ignore[no-untyped-def]
    """C1 — the previously-working allowlist entry still works (no regression)."""
    handler, workspace = planner_write_handler
    result = handler({"path": "knowledge/research/n.md", "content": "note"})
    assert result.error is None
    assert (workspace / "knowledge" / "research" / "n.md").exists()


def test_planner_denied_outside_allowlist(planner_write_handler) -> None:  # type: ignore[no-untyped-def]
    """C3 — the security boundary still denies product source, with a typed error."""
    handler, workspace = planner_write_handler
    result = handler({"path": "src/fa/cli.py", "content": "pwned"})
    assert result.error is not None
    assert result.error.code == "path_denied"
    assert result.error.retryable is False
    assert not (workspace / "src" / "fa" / "cli.py").exists()


def test_planner_denied_traversal_escape(planner_write_handler) -> None:  # type: ignore[no-untyped-def]
    """C3 — adversarial: a textual-prefix match that escapes the subtree is denied."""
    handler, _ = planner_write_handler
    result = handler({"path": "knowledge/research/../../src/evil.py", "content": "x"})
    assert result.error is not None
    assert result.error.code == "path_denied"


def test_allowlist_is_read_from_profile() -> None:
    """C1 (kill-check) — the profile key is the source of truth, not a closure literal.

    ``write_allowlist`` was decorative: the enforced prefixes lived in
    ``_build_limited_write``. Editing the profile silently changed nothing.
    """
    declared = PROFILES_RAW["planner"]["write_allowlist"]
    assert ".fa/" in declared
    for prefix in declared:
        probe = f"{prefix.rstrip('/')}/probe.md"
        assert is_path_within_allowlist(probe, declared) is True, (
            f"profile declares {prefix!r} but containment rejects {probe!r}"
        )
