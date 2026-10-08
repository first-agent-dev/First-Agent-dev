"""I02/SLICE4 — the mutation sandbox: a `src` overlay with a provenance guard.

root=pure helpers + real subprocess class=C0/C3 claim=CT60/CT61/CT62/CT63/CT64 path=T3
oracle=the overlay's contents, the composed environment, and the probe's outcome.

**What is actually being defended.** A kill-check mutates production code and
watches the slice's tests fail. If the mutation is never imported, every test
passes, every contract is reported VACUOUS, and the gate blocks correct work
while never detecting a weak test — it is wrong in the direction that gets
trusted. That is not hypothetical: E125/D1 measured it. With the package
installed, an absolute path sits on `sys.path`, so running tests with `cwd`
inside a mutated copy still imports the original module.

So the slice carries two mechanisms, and the tests below hold both: the
overlay must *win* the import (CT61) and must be *proven* to have won (CT62).
The second exists because trusting the first silently is the same fragility
that produced the defect.

**Why there is no C1 here.** These functions have no production caller until
SLICE5 assembles a verdict. A composition-root test would boot the loop,
exercise none of this, and pass whether or not it exists. The live proof is
registered in `notes/e2e-live-verification-register.md` against each producer.
"""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fa.inner_loop import slice_verification
from fa.inner_loop.slice_verification import (
    CommandOutcome,
    OverlayError,
    _assert_overlay_wins,
    _overlay_env,
    _prepend_pythonpath,
    mutation_overlay,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A session workspace shaped like the real one: a `src` tree and nothing else assumed."""
    package = tmp_path / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 'original'\n", encoding="utf-8")
    (package / "helper.py").write_text("def f() -> str:\n    return 'original'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_x() -> None:\n    assert True\n", encoding="utf-8")
    return tmp_path


# ── CT60 — the overlay itself ─────────────────────────────────────────────


def test_the_overlay_holds_a_copy_of_src(workspace: Path) -> None:
    """The sandbox is a real tree, not a promise of one."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        assert (overlay / "src" / "demo" / "__init__.py").is_file()
        assert (overlay / "src" / "demo" / "helper.py").is_file()


def test_the_overlay_applies_the_mutation_and_leaves_the_rest(workspace: Path) -> None:
    """One file changes; its neighbours must not, or the kill-check proves nothing."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        assert (overlay / "src" / "demo" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 'mutated'\n"
        assert "original" in (overlay / "src" / "demo" / "helper.py").read_text(encoding="utf-8")


def test_the_operators_tree_is_never_written_to(workspace: Path) -> None:
    """The whole point: the mutation exists only in the sandbox."""
    source = workspace / "src" / "demo" / "__init__.py"
    before = source.read_text(encoding="utf-8")

    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n"):
        assert source.read_text(encoding="utf-8") == before

    assert source.read_text(encoding="utf-8") == before


def test_the_overlay_is_removed_on_normal_exit(workspace: Path) -> None:
    """A kill-check per contract would otherwise fill the disk over one run."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        captured = overlay
        assert captured.is_dir()

    assert not captured.exists()


def test_the_overlay_is_removed_when_the_body_raises(workspace: Path) -> None:
    """Cleanup on the exceptional path, which is the one that actually leaks.

    A kill-check body fails often by design — that is what it is for — so the
    failure path is the common path here, not the rare one.
    """
    with pytest.raises(ValueError, match="boom"):
        with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
            captured = overlay
            raise ValueError("boom")

    assert not captured.exists()


def test_a_failure_inside_the_body_is_not_replaced_by_a_cleanup_error(workspace: Path) -> None:
    """The reason a kill-check failed must survive the `finally`.

    Cleanup is best-effort precisely so it cannot overwrite the exception
    travelling up the stack. Losing that exception would leave an operator
    with a tidy temp directory and no idea what went wrong.
    """
    with pytest.raises(ZeroDivisionError):
        with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
            # Remove the tree early, so the `finally` block's own rmtree misses.
            slice_verification.shutil.rmtree(overlay)
            _ = 1 / 0


def test_an_absent_src_tree_is_refused_loudly(tmp_path: Path) -> None:
    """A workspace with no `src` cannot be overlaid, and must not pretend to be.

    Returning an empty overlay here would mean the kill-check runs against the
    *installed* package — the exact measured defect — and reports a confident
    VACUOUS.
    """
    with pytest.raises(OverlayError, match="no src directory"):
        with mutation_overlay(tmp_path, "src/demo/__init__.py", "x = 1\n"):
            pass


def test_a_target_outside_the_workspace_is_refused(workspace: Path) -> None:
    """CT60 names the workspace; a path that is not in it is a defect, not an input."""
    with pytest.raises(OverlayError, match="does not exist"):
        with mutation_overlay(workspace, "src/demo/absent.py", "x = 1\n"):
            pass


# ── CT63 — containment, and why it is structural ──────────────────────────


def test_only_src_is_copied_so_tests_cannot_be_mutated(workspace: Path) -> None:
    """C3. The oracle must live outside anything a kill-check can reach.

    If the sandbox copied the whole tree, a mutation operator pointed at a
    test file would rewrite the very test meant to catch it, and the kill-check
    would report success. Keeping `tests/` out of the overlay makes that
    impossible by construction rather than by policy.
    """
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        assert sorted(p.name for p in overlay.iterdir()) == ["src"]
        assert not (overlay / "tests").exists()


@pytest.mark.parametrize(
    "escape",
    [
        "src/../../etc/passwd",
        "src/demo/../../../outside.py",
        "tests/test_demo.py",
        "../outside.py",
    ],
)
def test_a_path_escaping_the_src_tree_is_refused(workspace: Path, escape: str) -> None:
    """C3. Containment is checked on the resolved path, so `..` cannot walk out.

    The message is asserted, not merely the exception type. Every one of these
    paths is also absent from the overlay, so a weaker oracle would be
    satisfied by the "does not exist" check and would pass with the
    containment guard deleted — the guard would be untested while looking
    tested. Naming the rule that must fire is what makes this a security
    oracle rather than a spelling check.
    """
    with pytest.raises(OverlayError, match="resolves outside"):
        with mutation_overlay(workspace, escape, "x = 1\n"):
            pass


def test_an_absolute_path_is_refused(workspace: Path) -> None:
    """C3. Kill-directive paths are workspace-relative by contract (E128)."""
    with pytest.raises(OverlayError, match="workspace-relative"):
        with mutation_overlay(workspace, "/etc/passwd", "x = 1\n"):
            pass


def test_a_symlink_out_of_src_cannot_be_written_through(workspace: Path) -> None:
    """C3. Resolution happens before containment, so a link is not a loophole."""
    outside = workspace / "outside.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")
    (workspace / "src" / "demo" / "link.py").symlink_to(outside)

    with pytest.raises(OverlayError, match="resolves outside"):
        with mutation_overlay(workspace, "src/demo/link.py", "x = 1\n"):
            pass

    assert outside.read_text(encoding="utf-8") == "SECRET = 1\n"


# ── CT64 — no git, at all ─────────────────────────────────────────────────


def test_the_overlay_leaves_the_real_checkout_untouched() -> None:
    """CT64. Measured against this repository, not a fixture.

    An earlier design used `git worktree`, which puts a mutation one mistake
    away from the operator's branch — and could not have worked anyway, since
    the deployed `/repo` is read-only (E128).
    """
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout

    source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "plan_ids.py").read_text(encoding="utf-8")
    with mutation_overlay(REPO_ROOT, "src/fa/inner_loop/plan_ids.py", source.replace("def precheck", "def gone", 1)):
        pass

    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert after == before


SANDBOX_FUNCTIONS = (
    "_copy_src",
    "_overlay_target",
    "mutation_overlay",
    "_prepend_pythonpath",
    "_overlay_env",
    "_assert_overlay_wins",
)


def _sandbox_code_nodes() -> list[ast.AST]:
    """Every executable node of the SLICE4 functions, docstrings excluded.

    Reading the raw source would match the prose that *explains* why git is
    absent, which is the opposite of the claim. The AST is the only place the
    distinction between code and commentary survives.
    """
    tree = ast.parse(Path(slice_verification.__file__).read_text(encoding="utf-8"))
    nodes: list[ast.AST] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef) or function.name not in SANDBOX_FUNCTIONS:
            continue
        body = function.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]  # the docstring
        for statement in body:
            nodes.extend(ast.walk(statement))
    return nodes


def test_the_sandbox_functions_were_all_found_by_the_structural_oracle() -> None:
    """Guards the two tests below against passing because they inspected nothing."""
    names = {
        f.name
        for f in ast.walk(ast.parse(Path(slice_verification.__file__).read_text(encoding="utf-8")))
        if isinstance(f, ast.FunctionDef)
    }

    assert set(SANDBOX_FUNCTIONS) <= names, f"missing: {set(SANDBOX_FUNCTIONS) - names}"
    assert _sandbox_code_nodes(), "the oracle collected no executable nodes"


def test_no_git_command_appears_in_the_sandbox_implementation() -> None:
    """CT64's second half, as a structural oracle over code rather than prose.

    The runtime check above proves this particular run touched nothing. This
    proves the capability is absent, which is the claim that survives someone
    adding a "just this once" worktree later.
    """
    literals = [
        node.value.lower()
        for node in _sandbox_code_nodes()
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert [text for text in literals if "git" in text] == []
    assert [text for text in literals if "worktree" in text] == []


def test_the_sandbox_spawns_processes_only_through_the_slice1_runner() -> None:
    """CT62. One subprocess convention, so the probe matches the commands it vouches for.

    A second call site would be free to drift on timeout, scrubbing or output
    handling, and a probe that succeeds under conditions the real command
    never sees is worse than no probe.
    """
    called = {
        node.func.id for node in _sandbox_code_nodes() if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attribute_calls = {
        f"{node.func.value.id}.{node.func.attr}"
        for node in _sandbox_code_nodes()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
    }

    assert "_run_one" in called, "the probe must go through the SLICE1 runner"
    assert not {c for c in attribute_calls if c.startswith("subprocess.")}
    assert not {c for c in attribute_calls if c.startswith("os.popen") or c.startswith("os.system")}


# ── CT61 — pythonpath: prepend, never replace ─────────────────────────────


def test_pythonpath_puts_the_overlay_first(workspace: Path) -> None:
    """Order is the whole mechanism: first entry wins the import."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = _overlay_env(workspace, overlay)

        assert env["PYTHONPATH"].split(os.pathsep)[0] == str(overlay / "src")


def test_pythonpath_preserves_what_it_inherited() -> None:
    """CT61. Replacing the inherited value would delete the coder's own `src`.

    `scripts/fa-entrypoint.sh:237` prepends `<workspace>/src` so a verify
    command imports the coder's edits instead of the baked image. An overlay
    that overwrote `PYTHONPATH` would make itself win by removing the
    workspace, and the kill-check would then measure the image's code.
    """
    env = {"PYTHONPATH": f"/workspace/src{os.pathsep}/opt/first-agent/src"}

    _prepend_pythonpath(env, Path("/tmp/overlay/src"))

    assert env["PYTHONPATH"] == f"/tmp/overlay/src{os.pathsep}/workspace/src{os.pathsep}/opt/first-agent/src"


def test_pythonpath_is_set_cleanly_when_nothing_was_inherited() -> None:
    """No empty trailing entry — an empty `PYTHONPATH` segment means `cwd`."""
    env: dict[str, str] = {}

    _prepend_pythonpath(env, Path("/tmp/overlay/src"))

    assert env["PYTHONPATH"] == "/tmp/overlay/src"
    assert os.pathsep not in env["PYTHONPATH"]


def test_the_overlay_env_keeps_the_slice1_environment(workspace: Path) -> None:
    """Built on `_build_env`, so a kill-check and the verify it judges match.

    Divergence here would mean the kill-check runs a different program from
    the one the gate approved.
    """
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = _overlay_env(workspace, overlay)

        assert env["UV_PROJECT_ENVIRONMENT"] == str((workspace / ".venv").resolve())
        assert env["UV_NO_SYNC"] == "1"
        assert "PATH" in env


# ── CT62 — provenance: prove the overlay won ──────────────────────────────


def test_provenance_passes_when_the_module_comes_from_the_overlay(workspace: Path) -> None:
    """The happy path, and the only one that may let a verdict be produced."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        env = _overlay_env(workspace, overlay)

        result = _assert_overlay_wins("demo", overlay, env, workspace=workspace)

        assert result.outcome is CommandOutcome.PASS
        assert result.exit_code == 0


def test_provenance_errors_when_the_module_resolves_elsewhere(workspace: Path) -> None:
    """E125/D1 itself, reproduced: the overlay is built but never put on the path.

    Without the prepend the import falls through to whatever `sys.path`
    already offered. The probe must refuse this; the alternative is a
    kill-check measuring unmutated code.
    """
    other = workspace / "elsewhere"
    (other / "demo").mkdir(parents=True)
    (other / "demo" / "__init__.py").write_text("VALUE = 'not the overlay'\n", encoding="utf-8")

    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        env = slice_verification._build_env(workspace)
        _prepend_pythonpath(env, other)

        result = _assert_overlay_wins("demo", overlay, env, workspace=workspace)

        assert result.outcome is CommandOutcome.ERROR
        assert result.exit_code == 3


def test_provenance_reports_error_never_fail(workspace: Path) -> None:
    """A harness fault must not be dressed as a verdict about the coder's code.

    `FAIL` means "the command said no" and routes back to the coder. "The
    mutation was never loaded" is the harness's problem, and the three-state
    design exists so an operator can tell the two apart.
    """
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = _overlay_env(workspace, overlay)

        result = _assert_overlay_wins("demo.no_such_module", overlay, env, workspace=workspace)

        assert result.outcome is CommandOutcome.ERROR
        assert result.outcome is not CommandOutcome.FAIL


def test_provenance_explains_itself_when_it_refuses(workspace: Path) -> None:
    """The operator reads the tail, so the tail has to name the module and the tree."""
    other = workspace / "elsewhere"
    (other / "demo").mkdir(parents=True)
    (other / "demo" / "__init__.py").write_text("VALUE = 'x'\n", encoding="utf-8")

    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = slice_verification._build_env(workspace)
        _prepend_pythonpath(env, other)

        result = _assert_overlay_wins("demo", overlay, env, workspace=workspace)

        assert "demo" in result.stderr_tail
        assert str(overlay / "src") in result.stderr_tail


def test_provenance_rejects_a_sibling_whose_name_shares_a_prefix(tmp_path: Path) -> None:
    """C3. The reason containment is `is_relative_to` and not `startswith`.

    `/tmp/ov2/demo` starts with `/tmp/ov`, so a string-prefix check reports
    that the module came from the overlay when it came from a neighbour. This
    is the single comparison standing between a real kill-check and a
    confident false one, so it is tested adversarially rather than trusted.
    """
    overlay_src = tmp_path / "ov" / "src"
    sibling = tmp_path / "ov2"
    overlay_src.mkdir(parents=True)
    (sibling / "demo").mkdir(parents=True)
    (sibling / "demo" / "__init__.py").write_text("VALUE = 'sibling'\n", encoding="utf-8")

    probe = subprocess.run(
        [sys.executable, "-c", slice_verification._PROVENANCE_PROBE, str(overlay_src), "demo"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(sibling)},
        check=False,
    )

    assert str(overlay_src).startswith(str(tmp_path / "ov")), "precondition: the names share a prefix"
    assert probe.returncode == 3, "a sibling directory was accepted as the overlay"


# ── STEP4 — the negative oracle the slice was written for ─────────────────


def test_without_the_overlay_on_the_path_the_mutation_is_invisible(workspace: Path) -> None:
    """The measured defect (E125/D1), reproduced end to end.

    This is the test that justifies the whole slice. The overlay is built and
    the file really is mutated, but the environment does not prefer it — so
    the import resolves to the unmutated copy and the mutation has no effect
    whatsoever. A kill-check run this way passes against original code and
    reports VACUOUS against a perfectly good test.
    """
    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        assert (overlay / "src" / "demo" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 'mutated'\n"

        env = slice_verification._build_env(workspace)
        _prepend_pythonpath(env, workspace / "src")
        seen = subprocess.run(
            [sys.executable, "-c", "import demo; print(demo.VALUE)"],
            cwd=workspace,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert seen.stdout.strip() == "original", "the mutation must be invisible without the prepend"

        refused = _assert_overlay_wins("demo", overlay, env, workspace=workspace)
        assert refused.outcome is CommandOutcome.ERROR, "and the probe must refuse to let that count"


def test_with_the_overlay_on_the_path_the_mutation_is_observed(workspace: Path) -> None:
    """The same arrangement with the prepend restored — the only difference."""
    with mutation_overlay(workspace, "src/demo/__init__.py", "VALUE = 'mutated'\n") as overlay:
        env = _overlay_env(workspace, overlay)
        seen = subprocess.run(
            [sys.executable, "-c", "import demo; print(demo.VALUE)"],
            cwd=workspace,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert seen.stdout.strip() == "mutated"
        assert _assert_overlay_wins("demo", overlay, env, workspace=workspace).outcome is CommandOutcome.PASS


# ── Mutation-driven oracles (C4 follow-up to the SLICE4 sweep) ────────────


def test_stale_bytecode_is_left_behind(workspace: Path) -> None:
    """Found by mutation testing: eight survivors all mutated the ignore list.

    The fixture had no `__pycache__`, so the exclusion was asserted by nobody
    and could have been deleted silently. It is not cosmetic: a `.pyc` copied
    alongside its module is bytecode compiled from the **pre-mutation**
    source. Python normally invalidates it by mtime and size, but "normally"
    is not a property worth betting a kill-check on — if the stale object were
    ever used, the mutated module would run unmutated and the contract would
    be reported VACUOUS against a perfectly good test.
    """
    cache = workspace / "src" / "demo" / "__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-313.pyc").write_bytes(b"stale")
    (workspace / "src" / "demo" / "loose.pyc").write_bytes(b"stale")

    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        copied = {p.relative_to(overlay).as_posix() for p in overlay.rglob("*")}

        assert not [p for p in copied if "__pycache__" in p], f"bytecode cache copied: {sorted(copied)}"
        assert not [p for p in copied if p.endswith(".pyc")], f"bytecode copied: {sorted(copied)}"
        assert "src/demo/__init__.py" in copied, "the exclusion must not take the sources with it"


def test_an_unusable_path_is_refused_rather_than_crashing(workspace: Path) -> None:
    """Found by mutation testing: the `OSError`/`ValueError` arm ran in no test.

    A kill-directive path is planner-authored text, so it can be anything at
    all. A NUL byte makes `Path.resolve` raise `ValueError`, which without
    this arm would escape as a bare `ValueError` from inside a context
    manager and read like a harness bug rather than a bad directive.
    """
    with pytest.raises(OverlayError, match="unusable kill-directive path"):
        with mutation_overlay(workspace, "src/demo/\x00bad.py", "x = 1\n"):
            pass


def test_the_probe_takes_no_caller_supplied_budget() -> None:
    """The budget is the module's policy, not a per-call knob. (Q46(b))

    A `timeout_s` parameter existed here and no caller ever passed it, so
    mutation testing could not tell `_command_timeout(timeout_s)` from
    `_command_timeout(None)` — dead surface, removed rather than pinned by a
    test for a caller that does not exist. This records the shape so
    reintroducing it is a deliberate act with a named consumer, not a drift.
    """
    signature = inspect.signature(slice_verification._assert_overlay_wins)

    assert "timeout_s" not in signature.parameters
    assert set(signature.parameters) == {"module", "overlay_root", "env", "workspace"}


def test_a_sanity_check_does_not_borrow_the_test_suites_budget(workspace: Path) -> None:
    """Q46(b). The probe runs on the probe budget, and nothing else.

    600 s sizes the work a slice asked for — a suite, a compile. A provenance
    probe is an assertion about the execution environment and finishes in
    milliseconds. Sharing one timeout between them means it can only ever be
    tuned for one, and a hung probe would hold the gate for ten minutes
    before reporting that the environment is broken.
    """
    captured: dict[str, float] = {}
    real_run_one = slice_verification._run_one

    def spy(command: str, **kwargs: object) -> slice_verification.CommandResult:
        captured["timeout_s"] = float(kwargs["timeout_s"])  # type: ignore[arg-type]
        return real_run_one(command, **kwargs)  # type: ignore[arg-type]

    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = _overlay_env(workspace, overlay)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(slice_verification, "_run_one", spy)
            _assert_overlay_wins("demo", overlay, env, workspace=workspace)

    assert captured["timeout_s"] == slice_verification.DEFAULT_PROBE_TIMEOUT_SECONDS
    assert captured["timeout_s"] != slice_verification.DEFAULT_VERIFY_TIMEOUT_SECONDS


def test_the_two_budgets_stay_separate_and_the_probe_is_the_smaller() -> None:
    """The invariant behind Q46(b), stated so collapsing them is a red test.

    The value equals `runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS` by
    coincidence rather than derivation, and that coincidence is an invitation
    to "simplify" the three into one. Doing so would let a change made for
    the model's interactive shell silently retune this gate's failure
    detection.
    """
    assert slice_verification.DEFAULT_PROBE_TIMEOUT_SECONDS == 30.0
    assert slice_verification.DEFAULT_PROBE_TIMEOUT_SECONDS < slice_verification.DEFAULT_VERIFY_TIMEOUT_SECONDS


def test_a_hanging_probe_is_cut_short_and_reported_as_error(workspace: Path) -> None:
    """The budget has to be wired, not merely declared.

    A constant that no code path honours is documentation. This drives a probe
    that never returns and asserts the gate gives up on its own schedule and
    calls the result ERROR — the harness's fault, never the coder's.
    """
    with mutation_overlay(workspace, "src/demo/__init__.py", "x = 1\n") as overlay:
        env = _overlay_env(workspace, overlay)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(slice_verification, "_PROVENANCE_PROBE", "import time; time.sleep(600)")
            patch.setattr(slice_verification, "DEFAULT_PROBE_TIMEOUT_SECONDS", 1.0)
            started = time.monotonic()
            result = _assert_overlay_wins("demo", overlay, env, workspace=workspace)
            elapsed = time.monotonic() - started

    assert result.outcome is CommandOutcome.ERROR
    assert result.exit_code is None, "a killed probe has no exit code to report"
    assert elapsed < 30.0, f"the probe budget was not honoured ({elapsed:.1f}s)"
