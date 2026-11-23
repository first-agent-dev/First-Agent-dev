"""C0 oracles for sealed acceptance collection and the pinned verifier run (STEP9A)."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.acceptance_bundle import (
    AcceptanceBundle,
    AcceptanceBundleError,
    load_seal,
    mint_seal,
    write_seal,
)
from fa.inner_loop.acceptance_closure import collect_acceptance_closure
from fa.inner_loop.acceptance_collection import (
    AcceptanceCollectionError,
    SealedRun,
    collect_sealed_nodeids,
    collect_sealed_tree,
    run_sealed_acceptance,
    sealed_collection_argv,
    sealed_test_paths,
    verify_sealed_acceptance,
)
from fa.inner_loop.slice_verification import (
    JUNIT_BLOCK_END,
    JUNIT_BLOCK_START,
    CommandOutcome,
    CommandResult,
    ManagedVerifyCommandExecutor,
)
from fa.runtime.pty_pool import PtyResult
from tests.test_ai_native_plan_v2 import GRANT_PROBE_FILES, granted_graph, plan_document, plan_graph
from tests.test_slice_verification_runner import _inband_executor

_SEALED_ROOT = "worklogs/demo/acceptance"
_PUBLISH = f"{_SEALED_ROOT}/tests/test_publish.py"
_EXTRA = f"{_SEALED_ROOT}/tests/test_extra.py"
_NODEID = f"{_PUBLISH}::test_publish"
_EXTRA_NODEID = f"{_EXTRA}::test_extra"
_REVISION = "rev-" + "0" * 32
_PLAN_BYTES = plan_document().encode("utf-8")
_COLLECTED = {_PUBLISH: [_NODEID]}

_INI = """[pytest]
python_files = test_*.py
addopts = -q --strict-markers
testpaths = tests
"""


def _tree(tmp_path: Path, *, extra_test: bool = True, publish_name: str = "test_publish.py") -> Path:
    root = tmp_path / "worklogs" / "demo" / "acceptance"
    (root / "tests").mkdir(parents=True)
    (root / "support").mkdir()
    (root / "pytest.ini").write_text(_INI, encoding="utf-8")
    (root / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (root / "support" / "helper.py").write_text('def publish():\n    return "published"\n', encoding="utf-8")
    (root / "tests" / publish_name).write_text("def test_publish():\n    assert True\n", encoding="utf-8")
    if extra_test:
        (root / "tests" / "test_extra.py").write_text("def test_extra():\n    assert True\n", encoding="utf-8")
    (root / "tests" / "support_notes.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "support" / "test_helper.py").write_text("VALUE = 2\n", encoding="utf-8")
    # D-V2-12: a HOST_PROBE attestation names a probe the seal must find here.
    (root / "probes").mkdir()
    for probe in GRANT_PROBE_FILES:
        (root / "probes" / Path(probe).name).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return root


def _mint(root: Path, **overrides: Any) -> AcceptanceBundle:
    arguments: dict[str, Any] = {
        # Granted: a bare parse leaves CT-1.2's disposition as a request, and S2
        # refuses to seal an uncovered contract.
        "graph": granted_graph(),
        "plan_bytes": _PLAN_BYTES,
        "revision_id": _REVISION,
        "sealed_root": _SEALED_ROOT,
        "acceptance_root": root,
        "collected": _COLLECTED,
    }
    arguments.update(overrides)
    return mint_seal(**arguments)


def _seal(tmp_path: Path) -> tuple[AcceptanceBundle, Path]:
    return _mint(_tree(tmp_path)), tmp_path


def _junit(*rows: tuple[str, str]) -> bytes:
    """A report with pytest's exact-nodeid property and agreeing counters."""
    cases: list[str] = []
    for nodeid, state in rows:
        body = "" if state == "passed" else f"<{state}/>"
        cases.append(
            '<testcase name="t" classname="c"><properties>'
            f'<property name="fa_pytest_nodeid" value="{nodeid}"/>'
            f"</properties>{body}</testcase>"
        )
    failures = sum(state == "failure" for _nodeid, state in rows)
    skipped = sum(state == "skipped" for _nodeid, state in rows)
    return (
        f'<?xml version="1.0"?><testsuite tests="{len(rows)}" failures="{failures}" '
        f'errors="0" skipped="{skipped}">' + "".join(cases) + "</testsuite>"
    ).encode("utf-8")


def _report_path(command: str) -> Path:
    tokens = shlex.split(command)
    (token,) = [item for item in tokens if item.startswith("--junitxml=")]
    return Path(token[len("--junitxml=") :])


@dataclass
class _FakeHost:
    """A substrate that records the command and writes the report itself."""

    report: bytes | None
    exit_code: int | None = 0
    outcome: CommandOutcome = CommandOutcome.PASS
    writes_are_visible: bool = True
    #: F5: the revision the substrate is pinned at. ``None`` models a substrate that cannot
    #: name one, which the sealed verifier must refuse rather than trust the caller.
    view_revision_id: str | None = None
    commands: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def run_verify_command(self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]) -> CommandResult:
        self.commands.append(command)
        self.env = env
        if self.report is not None:
            _report_path(command).write_bytes(self.report)
        return CommandResult(
            command=command,
            outcome=self.outcome,
            exit_code=self.exit_code,
            stdout_tail="",
            stderr_tail="",
            duration_s=0.0,
        )


@dataclass
class _InbandHost:
    """A managed-shaped substrate that returns whatever receipt it was given."""

    stdout: str
    exit_code: int | None = 0
    outcome: CommandOutcome = CommandOutcome.PASS
    writes_are_visible: bool = False
    commands: list[str] = field(default_factory=list)

    def run_verify_command(self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]) -> CommandResult:
        del cwd, timeout_s, env
        self.commands.append(command)
        return CommandResult(
            command=command,
            outcome=self.outcome,
            exit_code=self.exit_code,
            stdout_tail="",
            stderr_tail="",
            duration_s=0.0,
            inband_stdout=self.stdout,
        )


def _receipt(*rows: tuple[str, str]) -> str:
    return f"{JUNIT_BLOCK_START}\n{_junit(*rows).decode('utf-8')}\n{JUNIT_BLOCK_END}"


# --- collect_sealed_tree: the pre-mint half of D-V2-5's chain ----------------------------------


def test_a_sealed_tree_is_collected_before_any_seal_exists(tmp_path: Path) -> None:
    """The cycle that kept the controller from minting: no report without a seal, no seal without one.

    ``collect_sealed_nodeids`` needs a minted bundle, so the only collector that existed could not
    run first. A tree plus a sealed root are enough for the closure and for the harness argv, so the
    collection is taken there and the mint follows.
    """
    root = _tree(tmp_path)
    collection = collect_sealed_tree(
        root,
        sealed_root=_SEALED_ROOT,
        workspace=tmp_path,
        executor=_inband_executor(writes_visible=False),
    )
    # Only ``tests/test_*.py`` inside the closure is a target: the support module and the
    # helper parked under ``support/`` collect nothing, and the nodeids are workspace-relative
    # exactly as the plan writes its selectors.
    assert dict(collection.nodeids) == {_PUBLISH: (_NODEID,), _EXTRA: (_EXTRA_NODEID,)}
    assert collection.outcomes == {_NODEID: True, _EXTRA_NODEID: True}
    assert collection.argv[0:3] == ("python", "-m", "pytest")
    assert f"{_SEALED_ROOT}/pytest.ini" in collection.argv
    assert collection.command is not None


def test_precode_nonce_crosses_managed_adapter_into_real_pytest(tmp_path: Path) -> None:
    """Adapter plus real shell/pytest: no env forwarded by the lower cell double."""
    root = _tree(tmp_path)

    class ShellCell:
        view_revision_id = _REVISION

        def run(self, command: str, timeout: int, workdir: Path | None, session_id: str | None) -> PtyResult:
            assert session_id is None
            clean_env = {key: value for key, value in os.environ.items() if not key.startswith("FA_VERIFY_")}
            result = subprocess.run(
                command,
                shell=True,
                cwd=workdir,
                timeout=timeout,
                env=clean_env,
                capture_output=True,
                text=True,
                check=False,
            )
            return PtyResult(result.stdout + result.stderr, result.returncode, False, "", False)

    executor = ManagedVerifyCommandExecutor(ShellCell(), root=tmp_path)  # type: ignore[arg-type]
    collection = collect_sealed_tree(
        root, sealed_root=_SEALED_ROOT, workspace=tmp_path, expected_revision_id=_REVISION, executor=executor
    )
    assert collection.outcomes == {_NODEID: True, _EXTRA_NODEID: True}
    assert collection.command is not None and collection.command.outcome is CommandOutcome.PASS
    assert collection.closure_sha256 == collect_acceptance_closure(root).digest


def test_the_tree_collection_is_exactly_what_the_mint_accepts(tmp_path: Path) -> None:
    """The two halves must meet on the same bytes: this is the whole point of the seam."""
    root = _tree(tmp_path)
    collection = collect_sealed_tree(
        root,
        sealed_root=_SEALED_ROOT,
        workspace=tmp_path,
        executor=_inband_executor(writes_visible=False),
    )
    bundle = _mint(root, collected=collection.nodeids)
    assert {selector.test_id for selector in bundle.selectors} == {"TEST-1.1"}
    assert bundle.selectors[0].nodeid == _NODEID
    # The seal describes the closure that was collected, not a second walk of the tree.
    assert bundle.closure.digest == collect_acceptance_closure(root).digest


def test_a_tree_collection_refuses_a_substrate_it_cannot_read_back() -> None:
    """No host fallback, the same rule the sealed verifier applies: an unread receipt is not evidence."""
    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(Path("worklogs/demo/acceptance"), sealed_root=_SEALED_ROOT, workspace=Path("."))
    assert refused.value.rule == "verifier-substrate-required"


def test_a_tree_collection_refuses_a_root_that_is_not_an_acceptance_tree(tmp_path: Path) -> None:
    """``sealed-root-invalid`` stays the seal's rule: this module does not re-label what it borrows.

    The same reason ``collect_sealed_nodeids`` lets the drift refusal escape -- one rule, one owner --
    so the pre-mint collector refuses with the seal's exception rather than a second vocabulary.
    """
    root = _tree(tmp_path)
    for acceptance_root, sealed_root in (
        (root.parent, _SEALED_ROOT),
        (root, "acceptance"),
        (root, f"{_SEALED_ROOT}/nested"),
    ):

        def collect_here(acceptance_root: Path = acceptance_root, sealed_root: str = sealed_root) -> object:
            # A named function, not a lambda: mypy cannot infer the lambda's types. The default
            # arguments bind the loop variable, which is what ruff's B023 asks for.
            return collect_sealed_tree(
                acceptance_root,
                sealed_root=sealed_root,
                workspace=tmp_path,
                executor=_inband_executor(writes_visible=False),
            )

        assert _seal_rule(collect_here) == "sealed-root-invalid"


def test_a_tree_collection_carries_the_closure_rules_instead_of_relabelling_them(tmp_path: Path) -> None:
    """A tree with no ``pytest.ini`` is the closure's own refusal, prefixed and not replaced."""
    unsealed = tmp_path / "worklogs" / "demo" / "acceptance"
    unsealed.mkdir(parents=True)
    (unsealed / "notes.md").write_text("x", encoding="utf-8")
    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(
            unsealed, sealed_root=_SEALED_ROOT, workspace=tmp_path, executor=_inband_executor(writes_visible=False)
        )
    assert refused.value.rule == "closure-missing-pytest-ini"


def test_a_tree_without_test_modules_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path, extra_test=False, publish_name="support_publish.py")
    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(
            root, sealed_root=_SEALED_ROOT, workspace=tmp_path, executor=_inband_executor(writes_visible=False)
        )
    assert refused.value.rule == "no-sealed-tests"


def test_a_tree_collection_refuses_a_report_that_escaped_the_closure(tmp_path: Path) -> None:
    """A receipt naming a file the closure does not hold is refused, never re-prefixed into belief."""
    root = _tree(tmp_path)

    class _ForeignReceipt(_InbandHost):
        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            self.stdout = _receipt((f"{_SEALED_ROOT}/tests/test_elsewhere.py::test_x", "passed")).replace(
                "</properties>",
                f'<property name="fa_pytest_run_id" value="{env["FA_VERIFY_JUNIT_RUN_ID"]}"/>'
                '<property name="fa_pytest_call_outcome" value="passed"/></properties>',
            )
            return super().run_verify_command(command, cwd=cwd, timeout_s=timeout_s, env=env)

    host = _ForeignReceipt(stdout="")
    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(root, sealed_root=_SEALED_ROOT, workspace=tmp_path, executor=host)
    assert refused.value.rule == "collection-nodeid-outside-closure"
    # ...and the command it refused to believe was the in-band one, not a host invocation.
    assert "$__fa_rep" in host.commands[0]


def test_a_tree_collection_refuses_a_receipt_with_no_report_block(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    host = _InbandHost(stdout="no report here")
    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(root, sealed_root=_SEALED_ROOT, workspace=tmp_path, executor=host)
    assert refused.value.rule == "collection-report-invalid"


@pytest.mark.parametrize("tampering", ["status", "nonce"])
def test_precode_rejects_inconsistent_receipt(tmp_path: Path, tampering: str) -> None:
    root = _tree(tmp_path)
    actual = _inband_executor(writes_visible=False)

    class TamperedReceipt:
        writes_are_visible = False

        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            result = actual.run_verify_command(command, cwd=cwd, timeout_s=timeout_s, env=env)
            if tampering == "status":
                return replace(result, exit_code=1, outcome=CommandOutcome.FAIL)
            return replace(result, stdout_tail=result.stdout_tail.replace(env["FA_VERIFY_JUNIT_RUN_ID"], "stale"))

    with pytest.raises(AcceptanceCollectionError) as refused:
        collect_sealed_tree(root, sealed_root=_SEALED_ROOT, workspace=tmp_path, executor=TamperedReceipt())
    assert refused.value.rule == ("collection-unusable" if tampering == "status" else "collection-report-invalid")


def _seal_rule(callable_: Callable[[], object]) -> str:
    """The seal's own closed rule: drift is refused by the seal, never re-labelled."""
    with pytest.raises(AcceptanceBundleError) as refused:
        callable_()
    return refused.value.rule


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(AcceptanceCollectionError) as refused:
        callable_()
    return refused.value.rule


# -- argv derivation --------------------------------------------------------


def test_only_sealed_test_modules_are_targets(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert sealed_test_paths(bundle) == (_EXTRA, _PUBLISH)


def test_a_sealed_module_that_is_not_a_test_module_is_not_a_target(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert f"{_SEALED_ROOT}/tests/support_notes.py" not in sealed_test_paths(bundle)
    assert f"{_SEALED_ROOT}/support/test_helper.py" not in sealed_test_paths(bundle)


def test_a_closure_without_any_test_module_is_refused(tmp_path: Path) -> None:
    checker = "worklogs/demo/acceptance/tests/check_publish.py"
    root = _tree(tmp_path, extra_test=False, publish_name="check_publish.py")
    bundle = _mint(
        root,
        graph=plan_graph(slice_body=_SLICE_WITHOUT_TESTS),
        plan_bytes=plan_document(slice_body=_SLICE_WITHOUT_TESTS).encode(),
        collected={checker: [f"{checker}::check_publish"]},
    )

    assert _rule(lambda: sealed_test_paths(bundle)) == "no-sealed-tests"


_SLICE_WITHOUT_TESTS = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/check_publish.py::check_publish
KILL-TARGETS:
STEP-EXIT-CHECKS:
"""


def test_the_argv_pins_the_sealed_configuration(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    argv = sealed_collection_argv(bundle, report="/tmp/report.xml")

    assert argv[:3] == ("python", "-m", "pytest")
    assert argv[3:5] == (_EXTRA, _PUBLISH)
    assert argv[5:7] == ("-c", f"{_SEALED_ROOT}/pytest.ini")
    assert argv[7:9] == ("--rootdir", _SEALED_ROOT)
    assert argv[9:13] == ("-p", "fa.inner_loop.junit_nodeid_plugin", "-p", "no:cacheprovider")
    assert argv[13] == "--junitxml=/tmp/report.xml"
    assert argv[-1] == "-q"
    assert not any("pyproject" in token or "addopts" in token for token in argv)


# -- collection -------------------------------------------------------------


def test_collects_nodeids_from_the_sealed_bytes_and_reprefies_them(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(
        report=_junit(("tests/test_publish.py::test_publish", "passed"), ("tests/test_extra.py::test_extra", "passed"))
    )

    collection = collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)

    assert collection.nodeids == {_PUBLISH: (_NODEID,), _EXTRA: (_EXTRA_NODEID,)}
    assert collection.outcomes == {_NODEID: True, _EXTRA_NODEID: True}
    assert len(executor.commands) == 1
    assert f"-c {_SEALED_ROOT}/pytest.ini" in executor.commands[0]
    assert executor.env.get("UV_NO_SYNC") == "1"


def test_a_failing_sealed_test_still_yields_its_nodeid(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(
        report=_junit(
            ("tests/test_publish.py::test_publish", "failure"), ("tests/test_extra.py::test_extra", "passed")
        ),
        exit_code=1,
        outcome=CommandOutcome.FAIL,
    )

    collection = collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)

    assert collection.outcomes == {_NODEID: False, _EXTRA_NODEID: True}


def test_a_drifted_tree_never_runs(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    (workspace / _SEALED_ROOT / "tests" / "test_publish.py").write_text(
        "def test_publish():\n    assert False\n", encoding="utf-8"
    )
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")))

    # The rule, not just "something refused": INV-07's shell half is exactly
    # `seal-byte-drift`, and a different refusal would mean a different check fired.
    assert (
        _seal_rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == "seal-byte-drift"
    )
    assert executor.commands == [], "no sealed byte produced a row: the drift is found first"


def test_a_smuggled_test_file_never_runs(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    (workspace / _SEALED_ROOT / "tests" / "test_smuggled.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )

    with pytest.raises(AcceptanceBundleError):
        collect_sealed_nodeids(bundle, workspace=workspace, executor=_FakeHost(report=b""))


def test_a_substrate_without_visible_writes_is_refused(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")), writes_are_visible=False)

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == (
        "substrate-unsupported"
    )
    assert executor.commands == []


def test_an_error_outcome_never_becomes_a_collection(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=None, outcome=CommandOutcome.ERROR, exit_code=None)

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == "collection-error"


def test_a_missing_report_is_refused(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=_FakeHost(report=None))) == (
        "collection-no-report"
    )


def test_a_report_without_the_nodeid_property_is_refused(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    report = b'<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="t"/></testsuite>'

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=_FakeHost(report=report))) == (
        "collection-report-invalid"
    )


def test_an_empty_report_is_refused(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    report = b'<testsuite tests="0" failures="0" errors="0" skipped="0"/>'

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=_FakeHost(report=report))) == (
        "collection-empty"
    )


@pytest.mark.parametrize("exit_code", [2, 3, 4, 5, None])
def test_a_runner_status_that_contradicts_a_collection_is_refused(tmp_path: Path, exit_code: int | None) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")), exit_code=exit_code)

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == (
        "collection-unusable"
    )


def test_a_nodeid_outside_the_sealed_closure_is_refused(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("test_other.py::test_other", "passed")))

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == (
        "collection-nodeid-outside-closure"
    )


def test_a_nodeid_addresses_a_file_the_closure_does_not_hold(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_ghost.py::test_ghost", "passed")))

    assert _rule(lambda: collect_sealed_nodeids(bundle, workspace=workspace, executor=executor)) == (
        "collection-nodeid-outside-closure"
    )


# -- the pinned run ---------------------------------------------------------


def test_the_pinned_run_reports_which_seal_and_revision_executed(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(
        report=_junit(("tests/test_publish.py::test_publish", "passed"), ("tests/test_extra.py::test_extra", "passed"))
    )

    run = run_sealed_acceptance(
        bundle,
        workspace=workspace,
        revision_id=_REVISION,
        plan_bytes=_PLAN_BYTES,
        executor=executor,
    )

    assert isinstance(run, SealedRun)
    assert run.seal_sha256 == bundle.seal_sha256
    assert run.revision_id == _REVISION
    assert run.closure_sha256 == bundle.closure.digest
    assert run.nodeids == {_PUBLISH: (_NODEID,), _EXTRA: (_EXTRA_NODEID,)}
    assert run.argv[5:7] == ("-c", f"{_SEALED_ROOT}/pytest.ini")


def test_the_pinned_run_refuses_a_stale_revision(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")))

    with pytest.raises(AcceptanceBundleError):
        run_sealed_acceptance(
            bundle,
            workspace=workspace,
            revision_id="rev-" + "1" * 32,
            plan_bytes=_PLAN_BYTES,
            executor=executor,
        )
    assert executor.commands == []


def test_the_pinned_run_refuses_other_plan_bytes(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")))

    with pytest.raises(AcceptanceBundleError):
        run_sealed_acceptance(
            bundle,
            workspace=workspace,
            revision_id=_REVISION,
            plan_bytes=b"other plan",
            executor=executor,
        )
    assert executor.commands == []


def test_a_sealed_selector_that_did_not_execute_never_proves_anything(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit(("tests/test_extra.py::test_extra", "passed")))

    assert (
        _rule(
            lambda: run_sealed_acceptance(
                bundle,
                workspace=workspace,
                revision_id=_REVISION,
                plan_bytes=_PLAN_BYTES,
                executor=executor,
            )
        )
        == "sealed-test-missing"
    )


def test_a_written_seal_loads_and_then_drives_the_same_run(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    seal_path = write_seal(bundle, workspace / "acceptance.seal.json")
    reloaded = load_seal(seal_path.read_bytes())
    executor = _FakeHost(report=_junit(("tests/test_publish.py::test_publish", "passed")))

    run = run_sealed_acceptance(
        reloaded,
        workspace=workspace,
        revision_id=_REVISION,
        plan_bytes=_PLAN_BYTES,
        executor=executor,
    )

    assert run.seal_sha256 == bundle.seal_sha256
    assert run.nodeids == {_PUBLISH: (_NODEID,)}


# -- F5: the revision is named by the substrate, not asserted by the caller ----


def _sealed_call(bundle: AcceptanceBundle, workspace: Path, executor: Any) -> Any:
    return lambda: verify_sealed_acceptance(
        bundle,
        workspace=workspace,
        candidate_revision_id=_REVISION,
        plan_bytes=_PLAN_BYTES,
        executor=executor,
    )


def test_a_substrate_that_cannot_name_its_revision_is_refused(tmp_path: Path) -> None:
    """F5 — "I ran somewhere" is not an identity, and the refusal precedes the cell."""
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(report=_junit((_NODEID, "passed")), writes_are_visible=False)

    assert _rule(_sealed_call(bundle, workspace, executor)) == "verifier-revision-mismatch"
    assert executor.commands == []


def test_a_substrate_pinned_at_another_revision_is_refused(tmp_path: Path) -> None:
    """F5 — the caller's revision is evidence only when the view is at it."""
    bundle, workspace = _seal(tmp_path)
    executor = _FakeHost(
        report=_junit((_NODEID, "passed")),
        writes_are_visible=False,
        view_revision_id="rev-" + "1" * 32,
    )

    assert _rule(_sealed_call(bundle, workspace, executor)) == "verifier-revision-mismatch"
    assert executor.commands == []


def test_a_substrate_pinned_at_the_candidate_revision_is_believed(tmp_path: Path) -> None:
    """F5's other half: agreement is not a refusal -- the run happens and is recorded."""
    bundle, workspace = _seal(tmp_path)
    prepared: dict[str, Any] = {}
    executor = _inband_executor(writes_visible=False, prepared=prepared, revision=_REVISION)

    verification = _sealed_call(bundle, workspace, executor)()

    assert verification.candidate_revision_id == _REVISION == executor.view_revision_id
    assert prepared["command"], "the accepted call must have run the sealed command"


def test_a_bundle_without_selectors_is_never_minted(tmp_path: Path) -> None:
    without_acceptance = plan_document(invariants=_INV_NON_EXECUTABLE, slice_body=_SLICE_WITHOUT_ACCEPTANCE)
    with pytest.raises(AcceptanceBundleError) as refused:
        _mint(
            _tree(tmp_path),
            # The bytes and the graph must describe the same plan: S2 refuses a
            # mismatch, so a fixture that paired one plan's bytes with another
            # plan's graph would be refused for the wrong reason.
            graph=plan_graph(invariants=_INV_NON_EXECUTABLE, slice_body=_SLICE_WITHOUT_ACCEPTANCE),
            plan_bytes=without_acceptance.encode("utf-8"),
            collected={},
        )

    assert refused.value.rule == "no-sealed-selectors"


_INV_NON_EXECUTABLE = """### INV-2
TEXT: Host readiness is proven on the approved host.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
"""

_SLICE_WITHOUT_ACCEPTANCE = """## SLICE1: host readiness
STEPS: outcome
CONTRACTS:
  CT-1.1 [CONSTRAINT] INV: INV-2: readiness is proven on the host
ACCEPTANCE:
KILL-TARGETS:
STEP-EXIT-CHECKS:
"""


# -- Public handles for sibling suites ---------------------------------------
# The defect bank needs the same sealed tree, the same fake substrate and the
# same plan fixtures; reusing them keeps one definition of "a sealed tree".
sealed_tree = _tree
mint_sealed = _mint
seal_fixture = _seal
FakeHost = _FakeHost
junit_report = _junit


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("assert True", "passed"),
        ("assert False", "failed"),
        ("raise ValueError('broken')", "collection-call-error"),
        ("import pytest; pytest.skip('not executed')", "collection-skipped"),
        ("raise NotImplementedError()", "collection-call-error"),
    ],
)
def test_candidate_verifier_classifies_real_pytest_call_phase(tmp_path: Path, body: str, expected: str) -> None:
    """C1: the actual pinned-run caller executes pytest; skip/error never become a failed claim."""
    root = _tree(tmp_path, extra_test=False)
    (root / "tests/test_publish.py").write_text(f"def test_publish():\n    {body}\n", encoding="utf-8")
    bundle = _mint(root)

    class ShellCell:
        view_revision_id = _REVISION

        def run(self, command: str, timeout: int, workdir: Path | None, session_id: str | None) -> PtyResult:
            assert session_id is None
            env = {key: value for key, value in os.environ.items() if not key.startswith("FA_VERIFY_")}
            result = subprocess.run(
                command, shell=True, cwd=workdir, timeout=timeout, env=env, capture_output=True, text=True, check=False
            )
            return PtyResult(result.stdout + result.stderr, result.returncode, False, "", False)

    executor = ManagedVerifyCommandExecutor(ShellCell(), root=tmp_path)  # type: ignore[arg-type]
    call = _sealed_call(bundle, tmp_path, executor)
    if expected.startswith("collection-"):
        assert _rule(call) == expected
    else:
        verification = call()
        assert verification.run.outcomes == {_NODEID: expected == "passed"}
        assert verification.command.exit_code == (0 if expected == "passed" else 1)


@pytest.mark.parametrize("tampering", ["nonce", "status", "outcome", "duplicate", "failure-reported-pass"])
def test_candidate_verifier_rejects_receipt_tampering(tmp_path: Path, tampering: str) -> None:
    """C3: a valid pytest report cannot be replayed or contradicted by its receipt."""
    if tampering == "failure-reported-pass":
        root = _tree(tmp_path)
        (root / "tests/test_publish.py").write_text("def test_publish():\n    assert False\n", encoding="utf-8")
        bundle, workspace = _mint(root), tmp_path
    else:
        bundle, workspace = _seal(tmp_path)
    actual = _inband_executor(writes_visible=False, revision=_REVISION)

    class TamperedReceipt:
        writes_are_visible = False
        view_revision_id = _REVISION

        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            result = actual.run_verify_command(command, cwd=cwd, timeout_s=timeout_s, env=env)
            if tampering == "status":
                return replace(result, exit_code=1, outcome=CommandOutcome.FAIL)
            if tampering == "outcome":
                return replace(result, outcome=CommandOutcome.FAIL)
            if tampering == "failure-reported-pass":
                return replace(result, exit_code=0, outcome=CommandOutcome.PASS)
            stdout = result.inband_stdout if result.inband_stdout is not None else result.stdout_tail
            if tampering == "nonce":
                stdout = stdout.replace(env["FA_VERIFY_JUNIT_RUN_ID"], "stale")
            else:
                stdout += "\n" + stdout
            return replace(result, stdout_tail=stdout, inband_stdout=stdout)

    assert _rule(_sealed_call(bundle, workspace, TamperedReceipt())) == (
        "collection-unusable"
        if tampering in {"status", "outcome", "failure-reported-pass"}
        else "collection-report-invalid"
    )


def test_candidate_verifier_refuses_setup_error_from_real_pytest(tmp_path: Path) -> None:
    root = _tree(tmp_path, extra_test=False)
    (root / "conftest.py").write_text(
        "import pytest\n@pytest.fixture(autouse=True)\ndef broken():\n    raise RuntimeError('setup')\n",
        encoding="utf-8",
    )
    bundle = _mint(root)
    executor = _inband_executor(writes_visible=False, revision=_REVISION)
    assert _rule(_sealed_call(bundle, tmp_path, executor)) == "collection-report-invalid"
