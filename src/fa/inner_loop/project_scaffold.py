"""The fixed scaffold a ``CREATE_NEW`` project starts from (D-V2-9, CT-2.3).

The harness owns exactly this much of a new project: the *shape*. Every byte here
is a document that carries the metadata admission cross-checks and the section
headings the planner must fill, and **nothing** that could look like content. A
scaffold with a placeholder invariant or slice would be a plan the parser admits
and nobody authored, which is why the bodies are empty and the parser then
refuses the pair with ``missing-invariants`` / ``missing-slice`` until the
planner has actually written them.

Two consequences of the current writer are visible in the file set and are not
stylistic choices:

* **No directory-only entries.** ``view_io._parts`` rejects ``""``, ``.`` and
  ``..``, and ``_write_bundle_file`` refuses any component starting with ``.``,
  so ``.gitkeep`` cannot exist and the writer has no ``mkdir``. A directory
  therefore exists only as somebody's parent, and each root is carried by a real
  file -- ``notes/README.md`` and ``reviews/README.md``.
* **No test functions in the placeholder module.** ``acceptance/tests/`` must
  exist before the planner can write a selector under it, but a placeholder
  *test* would be a fake green. The module collects to zero and says so.

The scaffold is written **by the stage, through the stage's own port**, before
the planner's first tool call -- not by a second writer and not through
``publication.render_bundle``. ``roadmap.md`` is written first and last-checked:
it is the one path whose create-only write is what turns "this project already
exists" into a refusal that leaves the rest of the scaffold unwritten.
"""

from __future__ import annotations

from fa.inner_loop.acceptance_closure import ACCEPTANCE_INI
from fa.inner_loop.plan_v2 import PLAN_FORMAT

#: The increment a bootstrap always creates (CT-2.1, D-V2-7). Route property, not
#: a request field: the planner may not name it, so there is one spelling.
INITIAL_INCREMENT_SLUG = "initial-plan"

#: The two ``README.md`` carriers exist only to make their directories exist.
_README = (
    "# {title}\n\n"
    "Scaffold placeholder written by the harness (D-V2-9).\n"
    "The planner replaces this body when it has content for this directory.\n"
)

#: The sealed closure's own pytest config (Q-V2-ACC-1 fixes the root at
#: ``worklogs/<slug>/acceptance/``). The harness writes it with the scaffold because a
#: closure without ``pytest.ini`` is not a closure -- ``collect_acceptance_closure`` refuses
#: it -- and the planner has no instruction, and no reason, to author a runner config. It is
#: harness *shape*, like the front matter: nothing here decides what is tested.
_ACCEPTANCE_INI = """[pytest]
python_files = test_*.py
addopts = -q --strict-markers
testpaths = tests
"""


_PLACEHOLDER_TEST = '''"""Acceptance placeholder for this project's sealed closure.

The scaffold must create ``acceptance/tests/`` before the planner can write a
selector under it, and the writer has no mkdir -- a directory exists only as a
file's parent. This module therefore exists, and deliberately defines **no test
function**: it collects to zero.

A placeholder *test* here would be a fake green. The planner writes the real
modules beside this one and may delete this file once the first one lands.
"""

from __future__ import annotations
'''


def _roadmap_body(slug: str, created: str) -> str:
    return (
        "---\n"
        f"Plan-Format: {PLAN_FORMAT}\n"
        f"Roadmap-ID: RM-{slug}\n"
        f"slug: {slug}\n"
        f"created: {created}\n"
        "status: IN PROGRESS\n"
        "active-increment: I01\n"
        "---\n\n"
        f"# Roadmap — {slug}\n\n"
        "## Artifacts\n\n"
        "| Artifact | Path | Status |\n"
        "| --- | --- | --- |\n"
        f"| Roadmap | `worklogs/{slug}/roadmap.md` | IN PROGRESS |\n"
        f"| Increment | `worklogs/{slug}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md` | IN PROGRESS |\n"
        f"| Ledger | `worklogs/{slug}/ledger.md` | — |\n\n"
        "## Increments\n\n"
        "| ID | Slug | Status |\n"
        "| --- | --- | --- |\n"
        f"| I01 | [{INITIAL_INCREMENT_SLUG}](worklogs/{slug}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md)"
        " | IN PROGRESS |\n\n"
        "## Intent\n\n"
        "## Out of scope\n"
    )


def _increment_body(slug: str) -> str:
    loopback = f"Roadmap-ID: RM-{slug}\n"
    return (
        "---\n"
        f"Plan-Format: {PLAN_FORMAT}\n"
        f"Increment-ID: RM-{slug}-I01\n"
        f"{loopback}"
        "status: IN PROGRESS\n"
        "slices: 0\n"
        "shipped: —\n"
        "---\n"
    )


def _ledger_body(slug: str) -> str:
    return (
        "---\n"
        f"Plan-Format: {PLAN_FORMAT}\n"
        f"Roadmap-ID: RM-{slug}\n"
        "---\n\n"
        "# Ledger — decision and evidence log\n\n"
        "Fixed heading only; entries are appended by the run.\n"
    )


def _open_questions_body(slug: str) -> str:
    return (
        "---\n"
        f"Plan-Format: {PLAN_FORMAT}\n"
        f"Roadmap-ID: RM-{slug}\n"
        "---\n\n"
        "# Open questions\n\n"
        "No question has been recorded for this project yet.\n"
    )


def scaffold_files(slug: str, *, created: str) -> dict[str, str]:
    """The eight files, ``roadmap.md`` first, workspace-relative.

    ``roadmap.md`` leads because its create-only write is the collision check
    (D-V2-9.2): if ``worklogs/<slug>/`` already exists the first write fails with
    ``STALE_REVISION`` and no other byte of this scaffold is ever written. Order
    is therefore part of the contract, not a dict-iteration accident.
    """
    root = f"worklogs/{slug}"
    return {
        f"{root}/roadmap.md": _roadmap_body(slug, created),
        f"{root}/ledger.md": _ledger_body(slug),
        f"{root}/open-questions.md": _open_questions_body(slug),
        f"{root}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md": _increment_body(slug),
        f"{root}/notes/README.md": _README.format(title="Notes"),
        f"{root}/reviews/README.md": _README.format(title="Reviews"),
        f"{root}/acceptance/{ACCEPTANCE_INI}": _ACCEPTANCE_INI,
        f"{root}/acceptance/tests/test_acceptance_placeholder.py": _PLACEHOLDER_TEST,
    }


def scaffold_paths(slug: str) -> tuple[str, ...]:
    """The keys, in write order -- ``roadmap.md`` first (D-V2-9.2)."""
    return tuple(scaffold_files(slug, created="1970-01-01"))


__all__ = ["INITIAL_INCREMENT_SLUG", "scaffold_files", "scaffold_paths"]
