"""C0/C3 the four non-PROJECT view purposes and the scoped candidate buffer.

E259 native proof over the real authority and real descriptor IO: the closed
create_view matrix, MUTATION root confinement, VERIFICATION's missing write
path, the CANDIDATE supervisor-staging buffer, and PROVISIONING's nullable
plan. NOT tool/PTY/service C1, not seal/publication or live acceptance.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, ExecutionContractError, GrantReply, ViewPurpose
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot
from tests.test_execution_readers import record_path, ref
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site

SCOPE_PATH = ".fa/admission/plans/candidate.plan.md"


# The closed error surface. A leak outside it escapes the oracle and fails the
# test; it is never swallowed into kill credit.
_DOMAIN_ERRORS = (SupervisorError, ExecutionContractError, OSError)


def denied(code: str, call: Any) -> None:
    """A denial must be an ASSERTION about the closed code, never a leaked type."""
    try:
        call()
    except _DOMAIN_ERRORS as error:
        assert isinstance(error, SupervisorError) and error.code == code, (
            f"expected {code}; observed {type(error).__name__}:{getattr(error, 'code', '')}"
        )
        return
    raise AssertionError(f"expected {code}; observed success")


def scope_for(plan_ref: PlanRef, path: str = SCOPE_PATH) -> dict[str, Any]:
    return {
        "candidate_path": path,
        "plan_ref": {
            "workspace_relative_path": plan_ref.workspace_relative_path,
            "source_kind": plan_ref.source_kind,
            "sha256": plan_ref.sha256,
        },
    }


@contextmanager
def setup(site: Site) -> Generator[tuple[WorkspaceAuthority, dict[str, str], GrantReply, PlanRef]]:
    (site.source / "plan.md").write_text("# plan\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        plan_ref = read_plan_snapshot(site.source, Path("plan.md")).ref
        yield owner, ids, lease, plan_ref


def views_root(owner: WorkspaceAuthority, grant: GrantReply) -> Path:
    return owner._state / "workspaces" / ref(grant).workspace_id / "views" / ref(grant).view_id


def create(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    *,
    purpose: ViewPurpose,
    access: Access,
    plan_ref: PlanRef | None = None,
    candidate_scope: dict[str, Any] | None = None,
    **kwargs: Any,
) -> GrantReply:
    """Producer proof before consumers: the grant must come with real state."""
    grant = ok(
        lambda: owner.create_view(
            kwargs.get("peer", PEER),
            kwargs.get("namespace", ACTOR),
            workspace_id=ids["workspace_id"],
            capability=kwargs.get("capability", lease.capability),
            purpose=purpose,
            access=access,
            candidate_scope=candidate_scope,
            plan_ref=plan_ref,
            formal_evidence=kwargs.get("formal", False),
            deadline=kwargs.get("deadline", until()),
        )
    )
    root = views_root(owner, grant)
    record = json.loads((root / "view.json").read_text())
    assert record["view_ref"] == ref(grant).to_dict()
    assert grant.capability not in (root / "view.json").read_text()
    if access is Access.WRITE:
        assert (root / "source/untracked.txt").read_bytes() == b"untracked"
        assert (root / "source/plan.md").is_file()
        assert (root / "scratch").is_dir()
    else:
        assert not (root / "source").exists(), "reader views retain the record only"
    return grant


def test_every_allowed_purpose_combination_constructs_its_exact_view(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        project = create(owner, ids, lease, purpose=ViewPurpose.PROJECT, access=Access.WRITE)
        verification = create(
            owner, ids, lease, purpose=ViewPurpose.VERIFICATION, access=Access.READ, plan_ref=plan_ref
        )
        mutation = create(owner, ids, lease, purpose=ViewPurpose.MUTATION, access=Access.WRITE, plan_ref=plan_ref)
        candidate = create(
            owner,
            ids,
            lease,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            plan_ref=plan_ref,
            candidate_scope=scope_for(plan_ref),
        )
        provisioning = create(owner, ids, lease, purpose=ViewPurpose.PROVISIONING, access=Access.WRITE)
        for grant, purpose, access in [
            (project, ViewPurpose.PROJECT, Access.WRITE),
            (verification, ViewPurpose.VERIFICATION, Access.READ),
            (mutation, ViewPurpose.MUTATION, Access.WRITE),
            (candidate, ViewPurpose.CANDIDATE, Access.READ),
            (provisioning, ViewPurpose.PROVISIONING, Access.WRITE),
        ]:
            assert ref(grant).purpose is purpose and ref(grant).access is access
        verification_record = json.loads(record_path(site, verification).read_text())
        assert verification_record["candidate_scope"] is None
        assert verification_record["plan_ref"] is not None
        candidate_record = json.loads(record_path(site, candidate).read_text())
        assert candidate_record["candidate_scope"] == scope_for(plan_ref)
        assert candidate_record["plan_ref"] == verification_record["plan_ref"]
        project_record = json.loads(record_path(site, project).read_text())
        assert project_record["candidate_scope"] is project_record["plan_ref"] is None
        assert json.loads(record_path(site, provisioning).read_text())["plan_ref"] is None


def test_every_forbidden_combination_denies_before_any_filesystem_effect(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        scope = scope_for(plan_ref)
        mismatched = {
            "candidate_path": SCOPE_PATH,
            "plan_ref": {
                "workspace_relative_path": plan_ref.workspace_relative_path,
                "source_kind": plan_ref.source_kind,
                "sha256": "0" * 64,
            },
        }
        forbidden = [
            (ViewPurpose.PROJECT, Access.READ, None, None),
            (ViewPurpose.PROJECT, Access.WRITE, scope, None),
            (ViewPurpose.VERIFICATION, Access.WRITE, None, plan_ref),
            (ViewPurpose.VERIFICATION, Access.READ, None, None),
            (ViewPurpose.VERIFICATION, Access.READ, scope, plan_ref),
            (ViewPurpose.MUTATION, Access.READ, None, plan_ref),
            (ViewPurpose.MUTATION, Access.WRITE, None, None),
            (ViewPurpose.MUTATION, Access.WRITE, scope, plan_ref),
            (ViewPurpose.CANDIDATE, Access.WRITE, scope, plan_ref),
            (ViewPurpose.CANDIDATE, Access.READ, None, plan_ref),
            (ViewPurpose.CANDIDATE, Access.READ, scope, None),
            (ViewPurpose.CANDIDATE, Access.READ, mismatched, plan_ref),
            (ViewPurpose.PROVISIONING, Access.READ, None, None),
            (ViewPurpose.PROVISIONING, Access.WRITE, scope, None),
        ]
        views = owner._state / "workspaces" / ids["workspace_id"] / "views"
        before = sorted(p.name for p in views.iterdir()) if views.exists() else []
        for purpose, access, candidate_scope, plan in forbidden:
            denied(
                "INPUT_POLICY",
                lambda purpose=purpose, access=access, candidate_scope=candidate_scope, plan=plan: owner.create_view(
                    PEER,
                    ACTOR,
                    workspace_id=ids["workspace_id"],
                    capability=lease.capability,
                    purpose=purpose,
                    access=access,
                    candidate_scope=candidate_scope,
                    plan_ref=plan,
                    formal_evidence=False,
                    deadline=until(),
                ),
            )
        assert (sorted(p.name for p in views.iterdir()) if views.exists() else []) == before
        assert list((site.state / "pending").iterdir()) == []


def broken(call: Any) -> None:
    """A type/shape break is ExecutionContractError; never a leaked success."""
    try:
        call()
    except ExecutionContractError:
        return
    except _DOMAIN_ERRORS as error:
        raise AssertionError(f"expected ExecutionContractError; observed {type(error).__name__}") from None
    raise AssertionError("expected ExecutionContractError; observed success")


def create_candidate(
    owner: WorkspaceAuthority, ids: dict[str, str], lease: GrantReply, scope: Any, plan_ref: PlanRef
) -> Any:
    return owner.create_view(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        capability=lease.capability,
        purpose=ViewPurpose.CANDIDATE,
        access=Access.READ,
        candidate_scope=scope,
        plan_ref=plan_ref,
        formal_evidence=False,
        deadline=until(),
    )


def test_malformed_scope_shapes_are_contract_errors_not_grants(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        for scope in [
            {"candidate_path": SCOPE_PATH},
            {"candidate_path": SCOPE_PATH, "plan_ref": scope_for(plan_ref)["plan_ref"], "extra": 1},
            {"candidate_path": SCOPE_PATH, "plan_ref": "not-a-plan"},
        ]:
            broken(lambda scope=scope: create_candidate(owner, ids, lease, scope, plan_ref))
        for scope in [
            {"candidate_path": "/absolute", "plan_ref": scope_for(plan_ref)["plan_ref"]},
            {"candidate_path": "a/../b", "plan_ref": scope_for(plan_ref)["plan_ref"]},
            {"candidate_path": "a//b", "plan_ref": scope_for(plan_ref)["plan_ref"]},
            {"candidate_path": "", "plan_ref": scope_for(plan_ref)["plan_ref"]},
        ]:
            denied("INPUT_POLICY", lambda scope=scope: create_candidate(owner, ids, lease, scope, plan_ref))
        assert list((site.state / "pending").iterdir()) == []


def test_candidate_buffer_writes_land_only_in_the_supervisor_staging_buffer(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(
            owner,
            ids,
            lease,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            plan_ref=plan_ref,
            candidate_scope=scope_for(plan_ref),
        )
        written = ok(
            lambda: owner.write_candidate(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=SCOPE_PATH,
                content="# candidate\n",
                expected_sha256=None,
                deadline=until(),
            )
        )
        assert written["sha256"] == hashlib.sha256(b"# candidate\n").hexdigest()
        assert written["bytes"] == len(b"# candidate\n")
        root = views_root(owner, grant)
        assert (root / "candidate").read_bytes() == b"# candidate\n"
        source = root / "source"
        assert not source.exists() and not (site.source / ".fa").exists()
        assert not (site.source / "candidate").exists()
        assert (site.source / "untracked.txt").read_text() == "untracked"
        read = ok(
            lambda: owner.read_candidate(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=SCOPE_PATH,
                offset_bytes=0,
                max_bytes=1024,
                deadline=until(),
            )
        )
        assert read == {"content": "# candidate\n", "sha256": written["sha256"], "eof": True}
        denied(
            "PATH_DENIED",
            lambda: owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path="untracked.txt",
                content="changed",
                expected_sha256=None,
                deadline=until(),
            ),
        )
        assert (root / "candidate").read_bytes() == b"# candidate\n"


def test_candidate_scope_equality_denies_every_other_path(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(
            owner,
            ids,
            lease,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            plan_ref=plan_ref,
            candidate_scope=scope_for(plan_ref),
        )
        for path in [".fa/admission/plans/other.plan.md", ".fa/admission/plans", SCOPE_PATH + "/child", "plan.md"]:
            denied(
                "PATH_DENIED",
                lambda path=path: owner.write_candidate(
                    PEER,
                    ACTOR,
                    view_ref=ref(grant),
                    capability=grant.capability,
                    path=path,
                    content="x",
                    expected_sha256=None,
                    deadline=until(),
                ),
            )
            denied(
                "PATH_DENIED",
                lambda path=path: owner.read_candidate(
                    PEER,
                    ACTOR,
                    view_ref=ref(grant),
                    capability=grant.capability,
                    path=path,
                    offset_bytes=0,
                    max_bytes=16,
                    deadline=until(),
                ),
            )
        assert not (views_root(owner, grant) / "candidate").exists()
        assert list((site.state / "pending").iterdir()) == []


def test_candidate_buffer_expected_sha_is_absence_or_exact_never_unconditional(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(
            owner,
            ids,
            lease,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            plan_ref=plan_ref,
            candidate_scope=scope_for(plan_ref),
        )

        def write(content: str, expected: str | None) -> Any:
            return owner.write_candidate(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=SCOPE_PATH,
                content=content,
                expected_sha256=expected,
                deadline=until(),
            )

        absent_sha = hashlib.sha256(b"").hexdigest()
        denied("STALE_REVISION", lambda: write("first", absent_sha))
        first = ok(lambda: write("first", None))
        denied("STALE_REVISION", lambda: write("second", None))
        denied("STALE_REVISION", lambda: write("second", absent_sha))
        denied("STALE_REVISION", lambda: write("second", "0" * 64))
        second = ok(lambda: write("second", first["sha256"]))
        assert second["sha256"] == hashlib.sha256(b"second").hexdigest()
        denied("INVALID_REQUEST", lambda: write("bad\x00", second["sha256"]))
        denied(
            "INVALID_REQUEST",
            lambda: owner.write_candidate(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=SCOPE_PATH,
                content="third",
                expected_sha256="not-a-sha",
                deadline=until(),
            ),
        )
        assert (views_root(owner, grant) / "candidate").read_bytes() == b"second"
        assert not (site.source / ".fa").exists()


def test_mutation_writes_are_confined_to_the_approved_roots(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(owner, ids, lease, purpose=ViewPurpose.MUTATION, access=Access.WRITE, plan_ref=plan_ref)

        def write(path: str, expected: str | None = None) -> Any:
            return owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=path,
                content="mutated",
                expected_sha256=expected,
                deadline=until(),
            )

        ok(lambda: write("src/module.py"))
        ok(lambda: write("scripts/helper.py"))
        assert (views_root(owner, grant) / "source/src/module.py").read_text() == "mutated"
        assert (views_root(owner, grant) / "source/scripts/helper.py").read_text() == "mutated"
        for path in ["tests/test_x.py", "docs/readme.md", ".fa/admission/x", ".env", "plan.md", "untracked.txt"]:
            denied("PATH_DENIED", lambda path=path: write(path))
        root = views_root(owner, grant)
        assert not (root / "source/tests").exists()
        assert (root / "source/untracked.txt").read_bytes() == b"untracked"
        assert (root / "source/plan.md").is_file()
        sha = hashlib.sha256(b"mutated").hexdigest()
        denied("STALE_REVISION", lambda: write("src/module.py", "0" * 64))
        ok(lambda: write("src/module.py", sha))


def test_verification_views_have_no_write_path_but_read_with_hash_checks(site: Site) -> None:
    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(owner, ids, lease, purpose=ViewPurpose.VERIFICATION, access=Access.READ, plan_ref=plan_ref)
        read = ok(
            lambda: owner.read_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path="untracked.txt",
                offset_bytes=0,
                max_bytes=64,
                deadline=until(),
            )
        )
        assert read["content"] == "untracked" and read["sha256"] == hashlib.sha256(b"untracked").hexdigest()
        for path in ["untracked.txt", "src/x.py", ".fa/admission/x"]:
            denied(
                "PATH_DENIED",
                lambda path=path: owner.write_file(
                    PEER,
                    ACTOR,
                    view_ref=ref(grant),
                    capability=grant.capability,
                    path=path,
                    content="changed",
                    expected_sha256=None,
                    deadline=until(),
                ),
            )
        assert not (views_root(owner, grant) / "source").exists()


def test_provisioning_view_accepts_a_null_plan_and_keeps_rooted_writes(site: Site) -> None:
    with setup(site) as (owner, ids, lease, _plan_ref):
        grant = create(owner, ids, lease, purpose=ViewPurpose.PROVISIONING, access=Access.WRITE)
        assert json.loads(record_path(site, grant).read_text())["plan_ref"] is None
        ok(
            lambda: owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path="generated/readiness.json",
                content="ready",
                expected_sha256=None,
                deadline=until(),
            )
        )
        assert (views_root(owner, grant) / "source/generated/readiness.json").read_text() == "ready"
        # .venv stays an excluded tool path (E256 policy): bootstrap outputs are
        # cell-mount effects, never file-tool writes.
        denied(
            "PATH_DENIED",
            lambda: owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=".venv/installed",
                content="ready",
                expected_sha256=None,
                deadline=until(),
            ),
        )


def test_forged_ref_purpose_never_reaches_the_effect_policy(site: Site) -> None:
    from dataclasses import replace

    with setup(site) as (owner, ids, lease, plan_ref):
        grant = create(
            owner,
            ids,
            lease,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            plan_ref=plan_ref,
            candidate_scope=scope_for(plan_ref),
        )
        forged = replace(ref(grant), purpose=ViewPurpose.PROJECT)
        denied(
            "UNAUTHORIZED",
            lambda: owner.write_candidate(
                PEER,
                ACTOR,
                view_ref=forged,
                capability=grant.capability,
                path=SCOPE_PATH,
                content="x",
                expected_sha256=None,
                deadline=until(),
            ),
        )
        denied(
            "UNAUTHORIZED",
            lambda: owner.write_file(
                PEER,
                ACTOR,
                view_ref=forged,
                capability=grant.capability,
                path="untracked.txt",
                content="x",
                expected_sha256=None,
                deadline=until(),
            ),
        )
        assert not (views_root(owner, grant) / "candidate").exists()
        assert list((site.state / "pending").iterdir()) == []
