"""The closed metadata table admission cross-checks on an authored project (D-V2-9.3).

``parse_plan`` deliberately reads only the roadmap/increment *pair* and ignores
front matter (``_strip_front_matter``). That is right for the grammar and wrong
for a project the planner authored: the pair can parse while the documents
disagree about which project they belong to, which increment is active, or when
they were created. This module is the missing half -- one table walk over the
documents admission is about to trust, and nothing else.

**The table names only fields that must agree with something else.** Q#10 asked
for a check that is as flexible as it can be while still being a check, so the
rule for membership is: *if a field's value is the planner's to choose, it is
not in this table*. ``status`` is the clearest case -- every legal value is
accepted, because the planner legitimately chooses the lifecycle state; only
membership in the canonical vocabulary is enforced. That is enough to catch a
typo or an invented state, and it never overrules an authored decision.

Refusals are closed strings, never sentences: the caller maps them to a
diagnostic rule, and the operator sees the same word the test asserts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

#: The states a roadmap or increment may declare. Membership is enforced; the
#: choice among them is the planner's.
PLAN_STATUSES = frozenset({"PLANNED", "IN PROGRESS", "SHIPPED", "ABANDONED"})

_FRONT_MATTER_OPEN = "---"
_SLUG_IN_PATH = re.compile(r"^worklogs/(?P<slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/(?P<rest>.+)$")


class MetadataError(ValueError):
    """A closed refusal from the metadata table."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"project metadata refused: {rule}")


def _front_matter(text: str) -> dict[str, str]:
    """The front matter as a flat map, or a refusal if it is absent/malformed.

    Only ``key: value`` lines are read. A nested or repeated key is refused rather
    than resolved by precedence, because "which of these two ``status`` lines
    counts" is exactly the ambiguity this check exists to remove.
    """
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip() != _FRONT_MATTER_OPEN:
        raise MetadataError("front-matter-missing")
    fields: dict[str, str] = {}
    index += 1
    while index < len(lines) and lines[index].strip() != _FRONT_MATTER_OPEN:
        line = lines[index]
        index += 1
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise MetadataError("front-matter-malformed")
        key = key.strip()
        if key in fields:
            raise MetadataError("front-matter-duplicate-key")
        fields[key] = value.strip()
    if index >= len(lines):
        raise MetadataError("front-matter-unterminated")
    return fields


def _one(fields: Mapping[str, str], key: str, *, rule: str) -> str:
    value = fields.get(key)
    if not value:
        raise MetadataError(rule)
    return value


def _slug_of(path: str) -> str:
    match = _SLUG_IN_PATH.match(path)
    if match is None:
        raise MetadataError("path-outside-project")
    return match.group("slug")


def check_project_metadata(documents: Mapping[str, str]) -> None:
    """Cross-check the authored project's documents against each other.

    ``documents`` maps a workspace-relative path to its text. The roadmap and
    increment are required; ``ledger.md`` and ``open-questions.md`` are checked
    only for the identity fields they carry, because those documents are not part
    of the admitted pair and a missing one is not this function's business.

    Every refusal is one of:

    ``front-matter-missing`` / ``front-matter-malformed`` /
    ``front-matter-duplicate-key`` / ``front-matter-unterminated`` /
    ``path-outside-project`` / ``roadmap-missing`` / ``increment-missing`` /
    ``roadmap-id-invalid`` / ``increment-id-invalid`` /
    ``roadmap-id-mismatch`` / ``increment-id-mismatch`` / ``slug-mismatch`` /
    ``active-increment-invalid`` / ``status-invalid`` / ``created-invalid`` /
    ``created-inconsistent``
    """
    roadmap_path = _select_document(documents, role="roadmap", missing="roadmap-missing")
    increment_path = _select_document(documents, role="increment", missing="increment-missing")
    slug = _slug_of(roadmap_path)
    if _slug_of(increment_path) != slug:
        raise MetadataError("slug-mismatch")

    roadmap = _front_matter(documents[roadmap_path])
    increment = _front_matter(documents[increment_path])

    roadmap_id = _one(roadmap, "Roadmap-ID", rule="roadmap-id-invalid")
    if roadmap_id != f"RM-{slug}":
        raise MetadataError("roadmap-id-mismatch")
    if _one(roadmap, "slug", rule="slug-mismatch") != slug:
        raise MetadataError("slug-mismatch")

    increment_id = _one(increment, "Increment-ID", rule="increment-id-invalid")
    if not increment_id.startswith(f"{roadmap_id}-"):
        raise MetadataError("increment-id-mismatch")
    # The increment must be the one the roadmap activates. Comparing the id
    # suffixes keeps this independent of the file name, so renaming a file cannot
    # make a stale `active-increment` look current.
    active = _one(roadmap, "active-increment", rule="active-increment-invalid")
    if increment_id != f"{roadmap_id}-{active}":
        raise MetadataError("active-increment-invalid")
    if _one(increment, "Roadmap-ID", rule="roadmap-id-invalid") != roadmap_id:
        raise MetadataError("roadmap-id-mismatch")

    for fields, _path in ((roadmap, roadmap_path), (increment, increment_path)):
        if _one(fields, "status", rule="status-invalid") not in PLAN_STATUSES:
            raise MetadataError("status-invalid")

    created = _one(roadmap, "created", rule="created-invalid")
    if not _DATE.fullmatch(created):
        raise MetadataError("created-invalid")
    # One fact, one value: a project that claims two creation dates has no
    # creation date. Documents that carry one must agree with the roadmap.
    for path, text in sorted(documents.items()):
        if path in (roadmap_path, increment_path):
            continue
        if not path.startswith("worklogs/"):
            continue
        try:
            fields = _front_matter(text)
        except MetadataError:
            # The side documents are not required to carry front matter; the
            # scaffold gives them some, but a planner may strip it.
            continue
        if "created" in fields and fields["created"] != created:
            raise MetadataError("created-inconsistent")
    return


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _select_document(documents: Mapping[str, str], *, role: str, missing: str) -> str:
    """The single document playing one role, or a refusal.

    Two matches is a refusal, not a pick: a project with two roadmaps has no
    roadmap, and choosing one would make admission depend on dict order.
    """
    matches = sorted(path for path in documents if path.startswith("worklogs/") and _plays_role(path, role))
    if not matches:
        raise MetadataError(missing)
    if len(matches) > 1:
        raise MetadataError("duplicate-document")
    return matches[0]


def _plays_role(path: str, role: str) -> bool:
    """``roadmap`` is the root document; ``increment`` is anything under ``increments/``."""
    parts = path.split("/")
    if role == "roadmap":
        return len(parts) == 3 and parts[2] == "roadmap.md"
    if role == "increment":
        # ``worklogs/<slug>/increments/<file>.md`` -- exactly four parts. Deeper
        # nesting is a different document, not this project's increment.
        return len(parts) == 4 and parts[2] == "increments" and parts[3].endswith(".md")
    return False


__all__ = ["PLAN_STATUSES", "MetadataError", "check_project_metadata"]
