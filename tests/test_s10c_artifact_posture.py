"""S10c.3 — sensitive artifacts are private at creation, and repaired if not (CT3).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10c-contract-and-posture-fixes.md``

**The defect (I-36).** Under the default ``umask 0022`` a real ``fa run`` left
**four** world-readable artifacts while the session manifest was already
``0600``:

```text
0644  global_history.db
0644  session-log/<run>/events.jsonl
0644  session-log/<run>/llm_bodies.jsonl
0644  sessions/<sid>/session.db
```

``llm_bodies.jsonl`` carries raw prompt and response prose, and ``session.db``
stores the same content as event rows. ``SecretRedactor`` masks known key
*values*; it cannot mask prose. So the most sensitive data the system writes
was the most permissive — in the one subsystem whose reason for existing is
"this is sensitive, so it is opt-in".

**Two mechanisms, because there are two kinds of writer**, and neither test can
substitute for the other:

* JSONL appends use the **builtin** ``open()`` with ``private_opener``
  (``Path.open()`` rejects ``opener=``);
* SQLite databases are pre-created ``0600`` inside ``create_sqlite_connection``
  before ``sqlite3.connect``, which also makes the WAL sidecars private.

**Plus a retroactive pass** (Q56): creation modes do nothing for deployments
that already hold ``0644`` files, so ``tighten_fa_artifact_modes`` repairs an
existing tree.

Test classes: **C2** for the real-run producers, **C0p** for the pass itself.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from fa.paths import tighten_fa_artifact_modes
from tests._capabilities import requires_posix_modes, requires_symlinks
from tests.test_cli import _FAKE_MODELS_YAML, _TEST_SECRETS, _ScriptedTransport, _stop_body
from tests.test_s7_cli_run_paths import _run_args


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


@pytest.fixture(autouse=True)
def _restore_writable_modes(tmp_path: Path) -> Iterator[None]:
    """Re-widen ``tmp_path`` after each test so pytest can delete it.

    These tests deliberately create `0400` files and `0700` directories, and
    pytest's ``rm_rf`` then fails with ``Directory not empty`` and leaves
    ``garbage-*`` trees behind on every run. That is a side effect of *this*
    module, so it is cleaned up here rather than left for the next person to
    discover in an unrelated failure.
    """
    yield
    for path in sorted(tmp_path.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        try:
            path.chmod(0o700 if path.is_dir() else 0o600)
        except OSError:  # pragma: no cover - best-effort teardown
            pass


@pytest.fixture
def completed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Drive a real ``fa run`` with body capture ON; return the FA state root."""
    from fa.cli import _cmd_run

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", "1")
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)

    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    args = _run_args(tmp_path, config, "posture")
    assert _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    return home / ".fa"


@requires_posix_modes
def test_s10c_no_artifact_is_group_or_world_accessible(completed_run: Path) -> None:
    """C2 (S10c.3 / CT3 / GAP4): NOTHING a run writes is group- or world-accessible.

    Deliberately a **whole-tree sweep** rather than four named assertions. The
    BACKLOG entry listed two files; measuring found four, and a future artifact
    added to this tree would slip past a fixed list exactly the same way. The
    invariant is "nothing here is readable by anyone else", so that is what is
    asserted.

    Oracle: every path under the state root has no group/other bits.
    Kill-check target: drop ``opener=`` from either JSONL writer, or the SQLite
    pre-create — each leaves a `0644` entry this catches.
    """
    offenders = {
        str(p.relative_to(completed_run)): oct(_mode(p))
        for p in completed_run.rglob("*")
        if not p.is_symlink() and _mode(p) & 0o077
    }
    assert not offenders, f"group/world-accessible artifacts: {offenders}"


@requires_posix_modes
@pytest.mark.parametrize(
    "relative",
    [
        "global_history.db",
        "session-log/posture/events.jsonl",
        "session-log/posture/llm_bodies.jsonl",
    ],
)
def test_s10c_named_artifacts_are_0600(completed_run: Path, relative: str) -> None:
    """C2 (S10c.3 / CT3): each known-sensitive artifact is exactly ``0600``.

    Paired with the sweep above: the sweep proves nothing *else* leaked, these
    prove the specific files the BACKLOG named actually exist and are private —
    a sweep alone would pass vacuously if a writer stopped producing its file.

    Oracle: ``S_IMODE == 0o600`` and the file exists.
    Kill-check target: the writer's ``opener=`` / pre-create.
    """
    path = completed_run / relative
    assert path.is_file(), f"{relative} was not produced — the sweep above would pass vacuously"
    assert _mode(path) == 0o600


@requires_posix_modes
def test_s10c_session_db_and_wal_sidecars_are_private(completed_run: Path) -> None:
    """C2 (S10c.3 / CT3 / P11b): ``session.db`` and any WAL sidecar are ``0600``.

    ``session.db`` is the artifact the BACKLOG entry missed. It stores full
    event ``content`` — the same prose that justifies ``llm_bodies.jsonl``
    being opt-in — so fixing the JSONL files while leaving the database
    world-readable would have closed the documented hole and left the larger
    one open.

    The sidecars matter because SQLite creates ``-wal``/``-shm`` itself; they
    inherit the mode from the pre-created database (measured).

    Oracle: the DB and every sidecar are ``0600``.
    Kill-check target: the ``os.open(..., PRIVATE_FILE_MODE)`` pre-create in
    ``create_sqlite_connection``.
    """
    dbs = list(completed_run.glob("sessions/*/session.db"))
    assert dbs, "no session.db was created"
    for db in dbs:
        assert _mode(db) == 0o600, f"{db} is {oct(_mode(db))}"
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db) + suffix)
            if sidecar.exists():
                assert _mode(sidecar) == 0o600, f"{sidecar} is {oct(_mode(sidecar))}"


@requires_posix_modes
def test_s10c_directories_are_0700(completed_run: Path) -> None:
    """C2 (S10c.3 / CT3 / P13): run and session directories are ``0700``.

    A private file inside a traversable directory still leaks its *name*, size
    and mtime — and for a run directory the names are the run ids.

    Oracle: every directory under the state root is ``0o700``.
    Kill-check target: the ``mode=PRIVATE_DIR_MODE`` arguments in
    ``SessionManager``.
    """
    dirs = [p for p in completed_run.rglob("*") if p.is_dir() and not p.is_symlink()]
    assert dirs, "no directories found — the fixture did not run"
    bad = {str(d.relative_to(completed_run)): oct(_mode(d)) for d in dirs if _mode(d) != 0o700}
    assert not bad, f"directories not 0700: {bad}"


@requires_posix_modes
def test_s10c_tighten_pass_repairs_existing_modes(tmp_path: Path) -> None:
    """C0p (S10c.3 / GAP5 / Q56): a pre-existing over-permissive tree is repaired.

    The retroactive half. Creation modes do nothing for a deployment that
    already holds ``0644`` artifacts, and claiming I-36 resolved while those
    files sit on disk would be false.

    Also asserts **idempotence**: the second pass reports zero changes, so this
    cannot churn modes on every run.

    Oracle: files become ``0600``, directories ``0700``, second run returns 0.
    Kill-check target: the ``current & ~0o077`` chmod.
    """
    root = tmp_path / ".fa"
    (root / "session-log" / "old").mkdir(parents=True)
    stale_file = root / "session-log" / "old" / "events.jsonl"
    stale_file.write_text("{}\n", encoding="utf-8")
    stale_file.chmod(0o644)
    (root / "session-log" / "old").chmod(0o755)

    changed = tighten_fa_artifact_modes(root)

    assert changed >= 2, "the pass reported no work on a tree that needed it"
    assert _mode(stale_file) == 0o600
    assert _mode(root / "session-log" / "old") == 0o700
    assert tighten_fa_artifact_modes(root) == 0, "the pass must be idempotent, not churn every run"


@requires_posix_modes
@requires_symlinks
def test_s10c_tighten_pass_skips_symlinks(tmp_path: Path) -> None:
    """C0p (S10c.3 / RK11): the pass must NOT chmod a symlink's target.

    **The hazard this closes is real and was measured during plan review.**
    ``os.chmod`` follows symlinks, and ``os.chmod(..., follow_symlinks=False)``
    raises ``NotImplementedError`` on Linux — ``os.chmod`` is not in
    ``os.supports_follow_symlinks``. So the only correct guard is an explicit
    ``is_symlink()`` skip. Without it, a crafted
    ``~/.fa/session-log/x/evil -> /etc/passwd`` inside the walked tree would
    have its **target's** mode rewritten by a routine housekeeping pass.

    Oracle: the target's mode is unchanged after the pass.
    Kill-check target: the ``if path.is_symlink(): continue`` guard.
    """
    root = tmp_path / ".fa"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not ours", encoding="utf-8")
    outside.chmod(0o644)
    (root / "evil").symlink_to(outside)

    tighten_fa_artifact_modes(root)

    assert _mode(outside) == 0o644, "the pass followed a symlink and rewrote a file outside the state root"
    assert outside.read_text(encoding="utf-8") == "not ours"


@requires_posix_modes
def test_s10c_tighten_pass_never_widens(tmp_path: Path) -> None:
    """C0p (S10c.3 / RK5): a deliberately stricter mode survives the pass.

    An operator who set ``0400`` on an archived artifact meant it. A pass that
    normalised everything to ``0600`` would silently *grant* write permission —
    tightening security posture is the goal, uniformity is not.

    Oracle: ``0400`` is still ``0400`` afterwards.
    Kill-check target: replace ``current & ~0o077`` with an unconditional
    ``chmod(0o600)`` → this fails.
    """
    root = tmp_path / ".fa"
    root.mkdir()
    locked = root / "archived.jsonl"
    locked.write_text("{}\n", encoding="utf-8")
    locked.chmod(0o400)

    tighten_fa_artifact_modes(root)

    assert _mode(locked) == 0o400, "the pass widened a deliberately read-only artifact"


def test_s10c_tighten_pass_on_missing_root_is_a_noop(tmp_path: Path) -> None:
    """C0p (S10c.3): a first-ever run has no state root yet; the pass must not fail.

    Called from the ``fa run`` entry path, so it executes before the root is
    guaranteed to exist. An exception here would break every first run.

    Oracle: returns 0, raises nothing.
    Kill-check target: the ``if not root.is_dir()`` guard.
    """
    assert tighten_fa_artifact_modes(tmp_path / "does-not-exist") == 0


@requires_posix_modes
def test_s10c_private_opener_creates_0600_and_appends(tmp_path: Path) -> None:
    """C0p (S10c.3): the opener sets the mode at creation and still appends.

    Pins the mechanism itself. ``Path.open()`` rejects ``opener=`` with
    ``TypeError`` (the shape the BACKLOG entry originally prescribed), so this
    also documents that the builtin ``open`` is required.

    Oracle: mode ``0600`` on creation; a second append preserves content.
    Kill-check target: ``private_opener``'s mode argument.
    """
    from fa.paths import private_opener

    target = tmp_path / "bodies.jsonl"
    with open(target, "a", encoding="utf-8", opener=private_opener) as handle:
        handle.write("first\n")
    assert _mode(target) == 0o600

    with open(target, "a", encoding="utf-8", opener=private_opener) as handle:
        handle.write("second\n")
    assert target.read_text(encoding="utf-8").splitlines() == ["first", "second"]
    assert _mode(target) == 0o600

    with pytest.raises(TypeError):
        target.open("a", opener=private_opener)  # type: ignore[call-overload]  # the point of the test


@requires_posix_modes
def test_s10c_umask_does_not_affect_created_modes(tmp_path: Path) -> None:
    """C0p (S10c.3): the mode comes from the syscall, not from the process umask.

    The whole point of an opener over a post-hoc ``chmod`` is that no window
    exists. Under a permissive ``umask 0000`` a plain ``open`` would yield
    ``0666``; the opener must still produce ``0600``.

    Oracle: ``0600`` under ``umask 0000``.
    Kill-check target: replacing the opener with a plain ``open`` + ``chmod``.
    """
    from fa.paths import private_opener

    previous = os.umask(0o000)
    try:
        target = tmp_path / "permissive.jsonl"
        with open(target, "a", encoding="utf-8", opener=private_opener) as handle:
            handle.write("{}\n")
        assert _mode(target) == 0o600
    finally:
        os.umask(previous)


@requires_posix_modes
def test_s10c_session_dir_is_private_at_creation_without_the_repair_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2 (S10c.3 / CT3): ``mkdir(mode=)`` alone makes the session dir private.

    **Written because the mutation sweep found a survivor.** Deleting
    ``mode=PRIVATE_DIR_MODE`` from ``SessionManager``'s ``session_dir.mkdir``
    changed nothing observable: the whole suite stayed green because
    ``tighten_fa_artifact_modes`` runs on the same ``fa run`` path and repairs
    the directory a moment later.

    Root-caused rather than papered over: disabling *both* layers was measured
    to leave the directory at ``0755``, so the two are genuinely independent
    and the survivor is **defence in depth**, not a weak oracle. The creation
    mode is still worth having on its own — it closes the window between
    ``mkdir`` and the repair pass, and ``SessionManager`` is a library that a
    caller can use without going through ``fa run`` at all.

    This test pins the creation layer *in isolation* so the redundancy is
    deliberate and each layer keeps its own oracle.

    Oracle: the session directory is ``0700`` immediately after
    ``SessionManager`` creates it, with no repair pass involved.
    Kill-check target: ``mode=PRIVATE_DIR_MODE`` on ``session_dir.mkdir`` —
    this is the test that now fails when it is removed.
    """
    from fa.session.manager import SessionManager

    state_root = tmp_path / "state"
    manager = SessionManager(state_root=state_root, workspace_root=tmp_path / "ws")
    session = manager.create_or_attach_session(session_id=None, workspace_override=None)

    session_dir = state_root / "sessions" / session.session_id
    assert session_dir.is_dir(), "the manager did not create the session directory"
    assert _mode(session_dir) == 0o700, (
        "the session directory must be private AT CREATION, independent of the repair pass"
    )
