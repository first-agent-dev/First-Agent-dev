"""S6.6a — C3 proof that each session-manifest guard is independently live.

Why this file exists
--------------------
A mutation sweep of S1-S6 (``scripts/mutation_sweep.py``) found that **8 of 9**
guards in ``fa/session/manager.py`` could be deleted with the entire suite still
green. An AST inventory of the module counted 24 distinct
``SessionManagerError`` codes, of which **16 were named in no test at all**.

The guards are not dead code. Each one was driven through the public API against
a tampered on-disk manifest and observed to fire:

    tampered session_id       -> manifest_identity_mismatch
    tampered schema_version   -> manifest_unsupported
    status=archived           -> session_not_active
    db path outside the root  -> path_escape
    workspace outside root    -> path_escape
    db path non-canonical     -> manifest_path_mismatch

So the defect was never behaviour — it was that nothing would notice if the
behaviour disappeared.

Two failure shapes, both represented here
-----------------------------------------
**A — the untested layer of a defended pair.** ``workspace_escape`` is raised at
``manager.py:182`` *and* ``:248``. ``test_session_lifecycle.py`` asserts the
code, so the pair looks covered; in fact ``:248`` alone satisfies it and ``:182``
can be deleted invisibly. Untested redundancy is not redundancy — it is one
working control plus one that may already be broken. Layered defences have to be
attacked layer by layer or their strength is assumed rather than measured.

**B — the never-exercised error path.** Manifest tampering (identity, schema,
status, canonical DB path) is raised in production and named nowhere. Line
coverage does not help: happy-path tests execute these lines and never reach the
raise, so the report calls them covered.

Design notes
------------
* Every test drives the **public** ``create_or_attach_session`` against a real
  manifest on disk. Calling the private validators directly would prove the
  function works, not that it is still wired into the path an operator hits.
* Assertions are on ``SessionManagerError.code``, not on message text: the code
  is the contract, the prose is not.
* ``test_every_error_code_is_named_in_some_test`` is the anti-regression guard.
  It fails when a new code is added without a test, so this gap cannot silently
  reopen — the problem was never one missing test, it was the absence of a
  forcing function.

Path inventory: manifest identity / schema / status / path-canonicality /
containment, plus id validation.

Test classes: C3 (adversarial, security boundary) + C0 (inventory guard).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from fa.session.manager import SessionManager, SessionManagerError

_MANAGER_SOURCE = Path("src/fa/session/manager.py")


def _manager(tmp_path: Path) -> SessionManager:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    return SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
    )


def _tamper(tmp_path: Path, **fields: Any) -> tuple[SessionManager, str]:
    """Create a real session, then rewrite its manifest fields on disk."""
    manager = _manager(tmp_path)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)
    data = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    data.update(fields)
    created.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return manager, created.session_id


# ---------------------------------------------------------------------------
# Shape B — manifest tampering. Each guard gets its own field and its own test.
# ---------------------------------------------------------------------------


def test_manifest_claiming_another_session_id_is_rejected(tmp_path: Path) -> None:
    """C3: the manifest is identity-bound to the directory that holds it.

    Without this, a manifest copied into another session's namespace would be
    honoured, and the session would silently adopt the wrong identity.
    """
    manager, session_id = _tamper(tmp_path, session_id="some-other-session")

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "manifest_identity_mismatch"


def test_manifest_with_unsupported_schema_version_is_rejected(tmp_path: Path) -> None:
    """C3: a manifest from a different schema generation must not be guessed at."""
    manager, session_id = _tamper(tmp_path, schema_version=999_999)

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "manifest_unsupported"


def test_non_active_session_cannot_be_attached(tmp_path: Path) -> None:
    """C3: an archived/closed session must not resume as if it were live."""
    manager, session_id = _tamper(tmp_path, status="archived")

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "session_not_active"


def test_manifest_db_path_outside_the_state_root_is_rejected(tmp_path: Path) -> None:
    """C3: containment for the *declared* DB path.

    The escape vector is the manifest, not the CLI flag: a tampered manifest
    could otherwise point the session DB at an arbitrary filesystem location.
    """
    manager, session_id = _tamper(tmp_path, session_db_path="/tmp/evil-session.db")

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "path_escape"


def test_manifest_workspace_path_outside_the_workspace_root_is_rejected(tmp_path: Path) -> None:
    """C3: the same containment argument for the declared workspace."""
    manager, session_id = _tamper(tmp_path, workspace_path="/tmp/evil-workspace")

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "path_escape"


def test_manifest_db_path_inside_root_but_not_canonical_is_rejected(tmp_path: Path) -> None:
    """C3: containment alone is insufficient — the DB must be *this* session's.

    A path can satisfy the escape check and still belong to a different session,
    which is how one session would end up writing into another's authority.
    """
    manager, session_id = _tamper(tmp_path)
    manifest_path = manager.sessions_root / session_id / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["session_db_path"] = str(manager.sessions_root / session_id / "not-canonical.db")
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=session_id, workspace_override=None)
    assert exc.value.code == "manifest_path_mismatch"


# ---------------------------------------------------------------------------
# Shape A — the inner layer of a defended pair, and identifier validation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", "with/slash", "with space", "", "a" * 300, "tab\tchar"],
    ids=["traversal", "slash", "space", "empty", "overlong", "control"],
)
def test_malformed_session_id_is_rejected_before_touching_the_filesystem(tmp_path: Path, bad_id: str) -> None:
    """C3: ``session_id`` reaches ``sessions_root / session_id``.

    Validation is therefore a path-traversal boundary, not cosmetics. The state
    assertion matters as much as the raise: rejecting *after* creating a
    directory would still have written attacker-controlled paths to disk.
    """
    manager = _manager(tmp_path)
    manager.sessions_root.mkdir(parents=True, exist_ok=True)
    before = sorted(manager.sessions_root.glob("**/*"))

    with pytest.raises(SessionManagerError) as exc:
        manager.create_or_attach_session(session_id=bad_id, workspace_override=None)
    assert exc.value.code in {"invalid_session_id", "unknown_session"}
    assert sorted(manager.sessions_root.glob("**/*")) == before, "rejected id still mutated the filesystem"


def test_malformed_run_id_is_rejected(tmp_path: Path) -> None:
    """C3: ``run_id`` names a directory under the session, same surface."""
    manager = _manager(tmp_path)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)

    with pytest.raises(SessionManagerError) as exc:
        manager.begin_run(created, requested_run_id="../escape")
    assert exc.value.code == "invalid_run_id"


def test_workspace_override_escape_is_rejected_by_the_validator_itself(tmp_path: Path) -> None:
    """C3, shape A: pins the *inner* layer of the ``workspace_escape`` pair.

    ``manager.py`` raises ``workspace_escape`` at two sites. The existing
    lifecycle test asserts the code at the API boundary, which the outer site
    satisfies on its own — so the inner validator could be deleted with the
    suite green. This calls the validator directly, so the layers are pinned
    independently rather than as a pair.

    Deliberate exception to this file's drive-the-public-API rule: the whole
    point is to distinguish two layers that the public path cannot separate.
    """
    manager = _manager(tmp_path)
    outside = tmp_path / "outside-the-root"
    outside.mkdir()

    with pytest.raises(SessionManagerError) as exc:
        manager._validate_workspace_override(outside)
    assert exc.value.code == "workspace_escape"


# ---------------------------------------------------------------------------
# Shape A again — a second instance, found by sweeping multi-site codes (S6.6c)
# ---------------------------------------------------------------------------


def test_opening_a_session_db_stamped_for_another_session_is_rejected(tmp_path: Path) -> None:
    """C3: the *open-time* identity guard (``session_db.py:281``).

    Found by the S6.6c probe rather than by reading: an AST sweep listed every
    error code raised at 2+ sites, and ``session_db_identity_mismatch`` has
    **five**. Deleting the one inside ``_validate_current_schema`` left all 2213
    tests green.

    The four survivors are not substitutes for it. Those guard *writes*
    (``append_event_row``, ``append_event_row_allocating``) and compare a row's
    ``session_id`` against the instance. This one guards the **open**: it
    compares the DB's persisted ``session_id`` marker against the id the caller
    claims, and it is the only thing stopping ``open_existing`` from attaching
    to another session's authority in the first place. Six production call
    sites depend on it (`cli.py:137,2507`, `manager.py:322,374,390`,
    `stats.py:289`).

    Verified live before this test was written: creating a DB stamped
    ``session-A`` and opening it as ``session-B`` raises
    ``session_db_identity_mismatch``.
    """
    from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError

    db_path = tmp_path / "session.db"
    SessionDatabase(db_path, session_id="session-A")

    with pytest.raises(SessionDatabaseError) as exc:
        SessionDatabase.open_existing(db_path, session_id="session-B")
    assert exc.value.code == "session_db_identity_mismatch"


def test_opening_a_session_db_with_its_own_id_still_works(tmp_path: Path) -> None:
    """C1 control for the test above.

    A guard test that only asserts rejection can be satisfied by a guard that
    rejects *everything*. This pins the happy path so over-tightening the
    identity check is caught too.
    """
    from fa.inner_loop.session_db import SessionDatabase

    db_path = tmp_path / "session.db"
    SessionDatabase(db_path, session_id="session-A")

    reopened = SessionDatabase.open_existing(db_path, session_id="session-A")
    assert reopened.session_id == "session-A"


# ---------------------------------------------------------------------------
# C0 — the forcing function
# ---------------------------------------------------------------------------


def _declared_error_codes() -> set[str]:
    """Every literal code passed to ``SessionManagerError`` in the module."""
    tree = ast.parse(_MANAGER_SOURCE.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "SessionManagerError"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            codes.add(node.args[0].value)
    return codes


# Codes with no test, each with a written reason. Shrinking this set is the
# point; adding to it requires justifying why the failure is unobservable.
KNOWN_UNTESTED_CODES: dict[str, str] = {
    "path_invalid": "requires an un-resolvable path (OSError from Path.resolve); not portably reproducible",
    "run_id_generation_failed": "exhaustion of the random run-id space after retries; not reachable deterministically",
    "session_id_generation_failed": "same exhaustion path for session ids",
    "session_provision_failed": (
        "wraps an OSError from mkdir/db-init; covered indirectly by the partial-provision rollback test"
    ),
    "source_workspace_invalid": (
        "constructor-time source workspace validation; exercised via SessionManager construction elsewhere"
    ),
    "workspace_invalid": "non-directory workspace; the escape and mismatch cases are the security-relevant ones",
    "workspace_missing": "manifest points at a workspace deleted out-of-band; filesystem-race shaped",
    "workspace_required": "internal invariant for attach without a resolved workspace",
    "session_context_mismatch": "begin_run called with a context from a different manager instance",
    "session_exists": "namespace collision on create; ids are generated, so only reachable by hand-crafted input",
}


def test_every_error_code_is_named_in_some_test() -> None:
    """C0: the forcing function, and the actual fix for this class of gap.

    The measured problem was not one missing test — it was that **16 of 24**
    error codes were unnamed and nothing said so. A single test is a point fix;
    this is the guard that keeps the gap closed as the module grows.

    A new ``SessionManagerError("...")`` now fails this test until it is either
    covered or explicitly listed above with a reason.
    """
    declared = _declared_error_codes()
    corpus = " ".join(p.read_text(encoding="utf-8") for p in Path("tests").glob("test_*.py"))

    untested = {code for code in declared if code not in corpus}
    unjustified = untested - set(KNOWN_UNTESTED_CODES)
    assert not unjustified, (
        f"error codes raised in manager.py but named in no test: {sorted(unjustified)}. "
        "Add a test, or add an entry to KNOWN_UNTESTED_CODES with a reason."
    )

    stale = set(KNOWN_UNTESTED_CODES) - declared
    assert not stale, f"KNOWN_UNTESTED_CODES lists codes that no longer exist: {sorted(stale)}"


def test_known_untested_codes_all_carry_a_reason() -> None:
    """C0: an allowlist without reasons decays into a silent waiver list."""
    empty = [code for code, reason in KNOWN_UNTESTED_CODES.items() if not reason.strip()]
    assert not empty, f"allowlisted codes with no rationale: {empty}"
