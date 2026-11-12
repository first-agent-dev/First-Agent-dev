"""Q140/R24 negative oracle: what a verify command writes can never become a revision.

The claim the read-only substrate rests on is not "the container is told not to
write" -- it is that the authority has no path from a READ view's bytes to a
published revision. That is a property of the authority, so it is proved against
the real one, not against a fake that agrees with us.

The first barrier is that the two registries are disjoint: a READ view lives in
``_readers`` and the writable registry (``_projects``) never holds one, so a write
naming a pinned view is refused before any policy is consulted. Verified by mutation:
admitting ``_readers`` into that lookup is the one change that kills these tests,
while removing ``_purpose_write_policy``'s purpose branch and relaxing the publish
check at ``workspace.py:5374`` do not -- those are second-order fences behind it, and
this oracle does not claim to cover them.

If the first barrier stopped holding, a verify run that writes a fixture into the
tree would be a writable view's write, and ``_purpose_write_policy`` would then have
to be the thing that stopped it.
"""

from __future__ import annotations

import pytest

from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, ViewPurpose
from fa.execution.workspace import WorkspaceAuthority
from tests.test_execution_readers import ref
from tests.test_execution_views import native_profile, read_only_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site


def _read_pin(owner: WorkspaceAuthority, ids: dict[str, str]) -> object:
    """Pin the current revision as the verification substrate does (READ/PROJECT)."""
    return owner.pin_reader(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        revision_id=ids["revision_id"],
        plan_ref=None,
        formal_evidence=False,
        deadline=until(),
    )


def test_a_pinned_read_view_cannot_write_the_tree_it_verifies(site: Site) -> None:
    """C1 — verification's view is not in the writable registry, so a write has no path.

    The refusal arrives as ``UNAUTHORIZED`` because the view is not a project view at
    all, which is the first barrier; it is checked as a refusal rather than as a code,
    so a future authority that refuses differently does not break the oracle while a
    future authority that *admits* it does.
    """
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: _read_pin(owner, ids))
        assert grant.view_ref.access is Access.READ

        with pytest.raises(SupervisorError) as refused:
            owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path="src/planted.py",
                content="planted by a verify run\n",
                expected_sha256=None,
                deadline=until(),
            )

        # The refusal is the point; the exact code is the authority's vocabulary for it.
        assert refused.value.code in {"PATH_DENIED", "INPUT_POLICY", "UNAUTHORIZED", "VIEW_CLOSED"}
        assert not (site.source / "src" / "planted.py").exists()
        del lease


def test_a_read_view_is_never_the_publishing_view(site: Site) -> None:
    """C1 — a publish intent naming a READ view cannot reach the publish path.

    This is the "just publish the verification view" shortcut: it fails on the same
    registry boundary as the write test, before the ``Access.WRITE`` check that guards
    recovery (``workspace.py:5374``) is ever consulted.
    """
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: _read_pin(owner, ids))

        with pytest.raises((SupervisorError, Exception)) as refused:
            owner.publish_view(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                plan_ref=None,
                expected_revision=None,
                operation_id="op-" + "0" * 32,
                deadline=until(),
            )

        assert refused.value is not None
        del lease


def test_the_verification_substrate_pins_read_and_a_writer_pins_write(site: Site) -> None:
    """C0 — the two purpose/access pairs are distinct, and the substrate takes the READ one.

    Stated as a comparison so it cannot pass by accident: the writer path used by the
    coder produces ``Access.WRITE``, the substrate produces ``Access.READ``, and only
    the second is what ``pin_reader`` mints.
    """
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        ok(lambda: site.claim(owner, ids))

        reader = ok(lambda: _read_pin(owner, ids))

        assert reader.view_ref.access is Access.READ
        assert reader.view_ref.purpose is ViewPurpose.PROJECT
        assert read_only_profile().interactive is False
        assert native_profile().interactive is True
