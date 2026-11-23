"""The two write predicates, and why there are two.

`is_path_within_allowlist` protects the profile allowlists, where every entry is a
directory and a path equal to one is not a writable file. `is_path_in_write_scope`
protects the create-new repair scope, where an entry may be an exact document -- and
using the directory predicate there denied every repair target, silently, because
nothing is strictly *under* a file name.
"""

from __future__ import annotations

import pytest

from fa.inner_loop.profiles import is_path_in_write_scope, is_path_within_allowlist


def test_the_directory_predicate_refuses_a_write_to_the_directory_itself() -> None:
    assert is_path_within_allowlist("knowledge/research/paper.md", ["knowledge/research/"])
    assert is_path_within_allowlist("knowledge/research/deep/paper.md", ["knowledge/research/"])
    assert not is_path_within_allowlist("knowledge/research", ["knowledge/research/"])
    assert not is_path_within_allowlist("knowledge/researcher/paper.md", ["knowledge/research/"])
    assert not is_path_within_allowlist("knowledge/research-paper.md", ["knowledge/research/"])


def test_the_scope_predicate_admits_an_exact_target_and_a_subtree() -> None:
    scope = ("worklogs/demo/roadmap.md", "worklogs/demo/acceptance")
    assert is_path_in_write_scope("worklogs/demo/roadmap.md", scope)
    assert is_path_in_write_scope("worklogs/demo/acceptance/tests/a.py", scope)
    assert is_path_in_write_scope("./worklogs/demo/roadmap.md", scope)


def test_the_scope_predicate_admits_no_sibling_and_no_escape() -> None:
    scope = ("worklogs/demo/roadmap.md", "worklogs/demo/acceptance")
    for refused in (
        "worklogs/demo/roadmap.md.bak",
        "worklogs/demo/roadmap",
        "worklogs/demo/acceptances/a.py",
        "worklogs/other/roadmap.md",
        "/etc/passwd",
        "worklogs/demo/../demo/roadmap.md.bak",
    ):
        assert not is_path_in_write_scope(refused, scope), refused


@pytest.mark.parametrize(
    "path",
    ["", ".", "..", "../worklogs/demo/roadmap.md", "worklogs/../../demo/roadmap.md"],
)
def test_both_predicates_refuse_an_empty_or_climbing_path(path: str) -> None:
    assert not is_path_within_allowlist(path, ["worklogs/demo/"])
    assert not is_path_in_write_scope(path, ["worklogs/demo"])


def test_a_traversal_inside_the_root_is_normalised_the_same_way_by_both() -> None:
    # Same normalisation, different verdicts -- which is the whole point of sharing it.
    inside = "worklogs/demo/acceptance/../roadmap.md"
    assert is_path_in_write_scope(inside, ["worklogs/demo/roadmap.md"])
    assert not is_path_within_allowlist(inside, ["worklogs/demo/roadmap.md"])
