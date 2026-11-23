"""C0 oracles for the sealed acceptance closure (STEP9A / Q-V2-ACC-1)."""

from __future__ import annotations

import hashlib
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.acceptance_closure import (
    ACCEPTANCE_INI,
    MAX_ACCEPTANCE_BYTES,
    MAX_ACCEPTANCE_FILE_BYTES,
    AcceptanceClosureError,
    closure_digest,
    collect_acceptance_closure,
    parse_pytest_ini,
    pytest_argv,
    read_closure_payload,
    shell_command,
    validate_pytest_ini,
)

_SAFE_INI = "[pytest]\naddopts = -q --strict-markers\npython_files = test_*.py\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _closure_root(root: Path) -> Path:
    _write(root / ACCEPTANCE_INI, _SAFE_INI)
    _write(root / "conftest.py", "import pytest\n")
    _write(root / "tests" / "test_sample.py", "def test_ok() -> None:\n    assert True\n")
    _write(root / "support" / "helper.py", "VALUE = 1\n")
    return root


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(AcceptanceClosureError) as refused:
        callable_()
    return refused.value.rule


def test_collects_a_minimal_closure_with_sorted_files_and_stable_digest(tmp_path: Path) -> None:
    closure = collect_acceptance_closure(_closure_root(tmp_path / "acc"))

    paths = [entry.path for entry in closure.files]
    assert paths == sorted(paths)
    assert paths == sorted([ACCEPTANCE_INI, "conftest.py", "support/helper.py", "tests/test_sample.py"])
    assert ACCEPTANCE_INI in paths
    assert {entry.mode for entry in closure.files} == {0o644}
    assert closure.total_bytes == sum(entry.size for entry in closure.files)
    assert closure.digest == closure_digest((entry.path, entry.sha256) for entry in closure.files)
    assert collect_acceptance_closure(tmp_path / "acc").digest == closure.digest


def test_digest_changes_when_one_sealed_byte_changes(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    before = collect_acceptance_closure(root).digest
    _write(root / "tests" / "test_sample.py", "def test_ok() -> None:\n    assert 1 == 1\n")

    assert collect_acceptance_closure(root).digest != before


def test_refuses_a_closure_without_the_sealed_pytest_ini(tmp_path: Path) -> None:
    root = tmp_path / "acc"
    _write(root / "tests" / "test_sample.py", "def test_ok() -> None:\n    assert True\n")

    assert _rule(lambda: collect_acceptance_closure(root)) == "missing-pytest-ini"


def test_refuses_an_empty_closure(tmp_path: Path) -> None:
    root = tmp_path / "acc"
    root.mkdir()

    assert _rule(lambda: collect_acceptance_closure(root)) == "empty-closure"


def test_refuses_a_nested_conftest_below_the_sealed_root(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    _write(root / "tests" / "conftest.py", "import pytest\n")

    assert _rule(lambda: collect_acceptance_closure(root)) == "nested-conftest"


def test_refuses_a_symlinked_acceptance_source(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    outside = tmp_path / "outside.py"
    outside.write_text("def test_smuggled() -> None:\n    assert True\n", encoding="utf-8")
    (root / "tests" / "test_link.py").symlink_to(outside)

    assert _rule(lambda: collect_acceptance_closure(root)) == "symlink-refused"


def test_refuses_hidden_components_inside_the_closure(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    _write(root / ".cache" / "junk.py", "VALUE = 0\n")

    assert _rule(lambda: collect_acceptance_closure(root)) == "path-hidden-component"


def test_refuses_a_file_over_the_per_file_budget(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    oversized = root / "support" / "big.py"
    oversized.write_bytes(b"#" * (MAX_ACCEPTANCE_FILE_BYTES + 1))

    assert _rule(lambda: collect_acceptance_closure(root)) == "file-too-large"


def test_refuses_more_files_than_the_closure_budget(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    extra = root / "support" / "bulk"
    extra.mkdir()
    for index in range(510):
        (extra / f"f{index:03d}.py").write_text("VALUE = 0\n", encoding="utf-8")

    assert _rule(lambda: collect_acceptance_closure(root)) == "too-many-files"


def test_refuses_an_aggregate_over_the_closure_budget(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    chunk = b"#" * MAX_ACCEPTANCE_FILE_BYTES
    for index in range(MAX_ACCEPTANCE_BYTES // MAX_ACCEPTANCE_FILE_BYTES):
        (root / "support" / f"chunk{index}.py").write_bytes(chunk)

    assert _rule(lambda: collect_acceptance_closure(root)) == "closure-too-large"


def test_refuses_a_tree_deeper_than_the_depth_budget(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    deep = root
    for index in range(70):
        deep = deep / f"d{index}"
    _write(deep / "leaf.py", "VALUE = 0\n")

    assert _rule(lambda: collect_acceptance_closure(root)) == "path-too-deep"


@pytest.mark.parametrize(
    ("ini", "rule"),
    [
        ("[pytest]\naddopts = -p xdist\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = --rootdir=/tmp\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\nplugin_option = 1\n", "pytest-ini-unknown-key"),
    ],
)
def test_collect_refuses_an_unsafe_sealed_ini(tmp_path: Path, ini: str, rule: str) -> None:
    root = _closure_root(tmp_path / "acc")
    _write(root / ACCEPTANCE_INI, ini)

    assert _rule(lambda: collect_acceptance_closure(root)) == rule


def test_parse_pytest_ini_requires_one_pytest_section() -> None:
    assert parse_pytest_ini("[pytest]\npython_files = test_*.py\n") == {"python_files": "test_*.py"}
    assert _rule(lambda: parse_pytest_ini("python_files = test_*.py\n")) == "pytest-ini-invalid"
    assert _rule(lambda: parse_pytest_ini("[pytest]\n[pytest]\n")) == "pytest-ini-invalid"
    assert _rule(lambda: parse_pytest_ini("[coverage]\n")) == "pytest-ini-invalid"
    assert _rule(lambda: parse_pytest_ini("[pytest]\nkey = 1\nkey = 2\n")) == "pytest-ini-invalid"


def test_validate_pytest_ini_accepts_strict_safe_options() -> None:
    validate_pytest_ini("[pytest]\naddopts = -q -x --strict-markers --tb=short --maxfail=1\n")


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("[pytest]\nrandomly_seeded = 1\n", "pytest-ini-unknown-key"),
        ("[pytest]\naddopts = -p xdist\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = --rootdir=/tmp\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = -c other.ini\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = -o addopts=\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = --basetemp=/tmp\n", "pytest-ini-unsafe-addopts"),
        ("[pytest]\naddopts = tests/\n", "pytest-ini-unsafe-addopts"),
    ],
)
def test_validate_pytest_ini_refuses_any_redirection(text: str, rule: str) -> None:
    assert _rule(lambda: validate_pytest_ini(text)) == rule


def test_testpaths_is_allowed_when_it_stays_inside_the_closure() -> None:
    validate_pytest_ini("[pytest]\ntestpaths = tests support\n")


def test_pytest_argv_pins_the_sealed_config_and_disables_the_cache(tmp_path: Path) -> None:
    argv = pytest_argv(
        tests=("worklogs/demo/acceptance/tests",),
        ini="worklogs/demo/acceptance/pytest.ini",
        rootdir="worklogs/demo/acceptance",
        report="reports/kill.xml",
    )

    assert argv == (
        "python",
        "-m",
        "pytest",
        "worklogs/demo/acceptance/tests",
        "-c",
        "worklogs/demo/acceptance/pytest.ini",
        "--rootdir",
        "worklogs/demo/acceptance",
        "-p",
        "fa.inner_loop.junit_nodeid_plugin",
        "-p",
        "no:cacheprovider",
        "--junitxml=reports/kill.xml",
        "-q",
    )
    assert "-c" in argv and "--rootdir" in argv
    assert "pyproject.toml" not in argv
    assert argv.index("-c") < argv.index("--rootdir")


def test_pytest_argv_refuses_empty_targets_and_unsafe_paths() -> None:
    assert _rule(lambda: pytest_argv(tests=(), ini="a/pytest.ini", rootdir="a", report="r.xml")) == "pytest-no-targets"
    assert (
        _rule(lambda: pytest_argv(tests=("../escape",), ini="a/pytest.ini", rootdir="a", report="r.xml"))
        == "path-invalid"
    )
    assert (
        _rule(lambda: pytest_argv(tests=("a/.hidden",), ini="a/pytest.ini", rootdir="a", report="r.xml"))
        == "path-hidden-component"
    )
    assert (
        _rule(lambda: pytest_argv(tests=("a/tests",), ini="a/pytest.ini", rootdir="a", report=""))
        == "pytest-report-invalid"
    )


def test_shell_command_round_trips_to_the_exact_argv() -> None:
    argv = pytest_argv(tests=("a/tests",), ini="a/pytest.ini", rootdir="a", report="r.xml")

    assert shlex.split(shell_command(argv)) == list(argv)


def test_closure_digest_is_order_independent_and_path_bound() -> None:
    forward = [("a.py", hashlib.sha256(b"1").hexdigest()), ("b.py", hashlib.sha256(b"2").hexdigest())]
    reversed_ = list(reversed(forward))

    assert closure_digest(forward) == closure_digest(reversed_)
    moved = [("a.py", hashlib.sha256(b"2").hexdigest()), ("b.py", hashlib.sha256(b"1").hexdigest())]
    assert closure_digest(moved) != closure_digest(forward)


def test_reads_exactly_the_bytes_the_closure_recorded(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    closure = collect_acceptance_closure(root)

    payload = read_closure_payload(root, closure)

    assert set(payload) == {entry.path for entry in closure.files}
    assert hashlib.sha256(payload["tests/test_sample.py"]).hexdigest() == next(
        entry.sha256 for entry in closure.files if entry.path == "tests/test_sample.py"
    )


def test_a_changed_byte_after_the_inventory_never_becomes_a_payload(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    closure = collect_acceptance_closure(root)
    _write(root / "support" / "helper.py", "VALUE = 2\n")

    assert _rule(lambda: read_closure_payload(root, closure)) == "closure-drift"


def test_an_added_file_never_becomes_a_payload(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    closure = collect_acceptance_closure(root)
    _write(root / "tests" / "test_extra.py", "def test_extra() -> None:\n    assert True\n")

    assert _rule(lambda: read_closure_payload(root, closure)) == "closure-extra-bytes"


def test_a_removed_file_never_becomes_a_payload(tmp_path: Path) -> None:
    root = _closure_root(tmp_path / "acc")
    closure = collect_acceptance_closure(root)
    (root / "support" / "helper.py").unlink()

    assert _rule(lambda: read_closure_payload(root, closure)) == "closure-missing-bytes"


@pytest.mark.parametrize("root", [None, "acc"])
def test_the_payload_reader_needs_a_path_and_a_record(tmp_path: Path, root: Any) -> None:
    closure = collect_acceptance_closure(_closure_root(tmp_path / "acc"))

    assert _rule(lambda: read_closure_payload(root, closure)) == "root-invalid"
    empty: Any = {}
    assert _rule(lambda: read_closure_payload(tmp_path / "acc", empty)) == "root-invalid"


def test_walk_refuses_aggregate_limit_before_reading_excess_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import acceptance_closure as closure_module

    root = tmp_path / "acc"
    root.mkdir()
    (root / "a").write_bytes(b"1234")
    (root / "b").write_bytes(b"5678")
    monkeypatch.setattr(closure_module, "MAX_ACCEPTANCE_BYTES", 6)
    real_read = closure_module.os.read
    returned: list[int] = []

    def recording(fd: int, count: int) -> bytes:
        chunk = real_read(fd, count)
        returned.append(len(chunk))
        return chunk

    monkeypatch.setattr(closure_module.os, "read", recording)
    assert _rule(lambda: closure_module.collect_acceptance_inventory(root)) == "closure-too-large"
    assert sum(returned) == 4, "second file's bytes must not be read after the budget is exhausted"


def test_walk_refuses_extra_empty_directories_before_returning_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import acceptance_closure as closure_module

    root = _closure_root(tmp_path / "acc")
    (root / "extra1").mkdir()
    (root / "extra2").mkdir()
    monkeypatch.setattr(closure_module, "MAX_ACCEPTANCE_ENTRIES", 3)
    assert _rule(lambda: closure_module.collect_acceptance_inventory(root)) == "too-many-entries"
    assert _rule(lambda: collect_acceptance_closure(root)) == "too-many-entries"
