"""D-V2-9.1/9.3/9.7 oracles: the scaffold, and the table admission cross-checks.

Three properties are pinned here, and each one is a way the design could quietly
become a lie:

* **The scaffold is empty.** If an unfilled scaffold parsed as a plan, the
  harness would have authored a plan nobody wrote, and admission would admit it.
* **The scaffold's directories exist only as file parents.** The writer has no
  ``mkdir`` and refuses dot-only components, so ``.gitkeep`` is impossible. A test
  that assumed otherwise would pass against a mock and fail against the authority.
* **The metadata table names only fields that must agree.** It is deliberately not
  a schema: a legal ``status`` value is the planner's choice, and the table's job
  is to catch disagreement, not to second-guess the author.
"""

from __future__ import annotations

import ast
from collections.abc import Callable

import pytest

from fa.inner_loop.plan_v2 import PlanV2Error, parse_plan
from fa.inner_loop.project_metadata import MetadataError, check_project_metadata
from fa.inner_loop.project_scaffold import (
    INITIAL_INCREMENT_SLUG,
    scaffold_files,
    scaffold_paths,
)

_SLUG = "demo-project"
_CREATED = "2026-11-21"
_ROOT = f"worklogs/{_SLUG}"
_ROADMAP = f"{_ROOT}/roadmap.md"
_INCREMENT = f"{_ROOT}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md"


@pytest.fixture()
def files() -> dict[str, str]:
    return scaffold_files(_SLUG, created=_CREATED)


def test_scaffold_is_the_seven_fixed_files_in_write_order(files: dict[str, str]) -> None:
    """The closed set, and ``roadmap.md`` first because its write is the collision check."""
    assert scaffold_paths(_SLUG) == (
        _ROADMAP,
        f"{_ROOT}/ledger.md",
        f"{_ROOT}/open-questions.md",
        _INCREMENT,
        f"{_ROOT}/notes/README.md",
        f"{_ROOT}/reviews/README.md",
        f"{_ROOT}/acceptance/tests/test_acceptance_placeholder.py",
    )
    assert tuple(files) == scaffold_paths(_SLUG)


def test_scaffold_carries_no_planner_content_and_no_placeholder_plan(files: dict[str, str]) -> None:
    """An unfilled scaffold must be *refused*, not admitted as a plan with empty bodies."""
    with pytest.raises(PlanV2Error) as refusal:
        parse_plan(roadmap=files[_ROADMAP], increment=files[_INCREMENT])
    assert refusal.value.rule in {"missing-slice", "missing-invariants"}


def test_scaffold_documents_carry_the_marker_the_parser_requires(files: dict[str, str]) -> None:
    """``_require_marker`` counts exactly one marker line per admitted document."""
    for path in (_ROADMAP, _INCREMENT):
        assert files[path].count("Plan-Format: AI-NATIVE-PLAN-V2") == 1


def test_scaffold_creates_every_directory_only_as_a_file_parent(files: dict[str, str]) -> None:
    """No ``.gitkeep`` is possible, so each root must be implied by a real file."""
    implied = {path.rsplit("/", 1)[0] for path in files}
    assert {_ROOT, f"{_ROOT}/increments", f"{_ROOT}/notes", f"{_ROOT}/reviews", f"{_ROOT}/acceptance/tests"} <= implied


def test_scaffold_placeholder_module_defines_no_test_function(files: dict[str, str]) -> None:
    """A placeholder *test* would be a fake green; the module must collect to zero."""
    module = files[f"{_ROOT}/acceptance/tests/test_acceptance_placeholder.py"]
    tree = ast.parse(module)
    definitions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]
    assert [name for name in definitions if name.startswith("test_")] == []


def test_the_metadata_table_accepts_the_scaffold_it_ships(files: dict[str, str]) -> None:
    """The harness's own output must satisfy the rule admission applies to it."""
    check_project_metadata(files)


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        (lambda g: g.__setitem__("worklogs/other/roadmap.md", g[_ROADMAP]), "duplicate-document"),
        (lambda g: g.pop(_ROADMAP), "roadmap-missing"),
        (lambda g: g.pop(_INCREMENT), "increment-missing"),
        (
            lambda g: g.__setitem__(_ROADMAP, g[_ROADMAP].replace(f"slug: {_SLUG}", "slug: other")),
            "slug-mismatch",
        ),
        (
            lambda g: g.__setitem__(_ROADMAP, g[_ROADMAP].replace("status: IN PROGRESS", "status: BOGUS")),
            "status-invalid",
        ),
        (
            lambda g: g.__setitem__(_ROADMAP, g[_ROADMAP].replace("active-increment: I01", "active-increment: I02")),
            "active-increment-invalid",
        ),
        (
            lambda g: g.__setitem__(_ROADMAP, g[_ROADMAP].replace(f"Roadmap-ID: RM-{_SLUG}", "Roadmap-ID: RM-other")),
            "roadmap-id-mismatch",
        ),
        (lambda g: g.__setitem__(_ROADMAP, "no front matter at all\n"), "front-matter-missing"),
        (
            lambda g: g.__setitem__(_ROADMAP, g[_ROADMAP].replace(f"created: {_CREATED}", "created: 21-11-2026")),
            "created-invalid",
        ),
    ],
)
def test_the_metadata_table_refuses_every_disagreement_it_names(
    files: dict[str, str], mutate: Callable[[dict[str, str]], None], rule: str
) -> None:
    """Each refusal is the closed string the caller maps to a diagnostic."""
    documents = dict(files)
    mutate(documents)
    with pytest.raises(MetadataError) as refusal:
        check_project_metadata(documents)
    assert refusal.value.rule == rule


def test_one_fact_has_one_value_across_the_project(files: dict[str, str]) -> None:
    """A project claiming two creation dates has no creation date."""
    documents = dict(files)
    ledger = documents[f"{_ROOT}/ledger.md"]
    documents[f"{_ROOT}/ledger.md"] = ledger.replace("---\n\n#", "created: 2020-01-01\n---\n\n#")
    with pytest.raises(MetadataError) as refusal:
        check_project_metadata(documents)
    assert refusal.value.rule == "created-inconsistent"


def test_a_side_document_without_front_matter_is_not_a_refusal(files: dict[str, str]) -> None:
    """The table names what must agree; a planner may strip a side document's front matter."""
    documents = dict(files)
    documents[f"{_ROOT}/notes/README.md"] = "# Notes\n"
    check_project_metadata(documents)


def test_every_legal_status_is_accepted() -> None:
    """The planner chooses the lifecycle state; only membership is enforced."""
    from fa.inner_loop.project_metadata import PLAN_STATUSES

    for status in sorted(PLAN_STATUSES):
        documents = scaffold_files(_SLUG, created=_CREATED)
        documents[_ROADMAP] = documents[_ROADMAP].replace("status: IN PROGRESS", f"status: {status}")
        check_project_metadata(documents)
