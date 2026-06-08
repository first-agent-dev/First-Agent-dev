"""Tests for the Level-0 authoring kernel (ADR-11; src/fa/authoring_tcb.py).

Cover the frozen public contract: manifest parsing + shape validation
(fail-closed), deterministic sorted enumeration, SHA-256 binders,
deterministic diagnostic ordering, rule dispatch + crash wrapping, and
the JSON/text renderers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.authoring_tcb import (
    KERNEL_VERSION,
    KernelReport,
    Manifest,
    ManifestError,
    RuleContext,
    RuleResult,
    Severity,
    enumerate_paths,
    parse_manifest,
    render_json,
    render_text,
    run_all,
)


def _make_workspace(root: Path) -> Path:
    """Create a minimal valid First-Agent workspace under ``root``."""
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "llms.txt").write_text("# routing surface\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")
    return root


def _write_manifest(root: Path, body: str) -> Path:
    manifest_dir = root / ".fa"
    manifest_dir.mkdir(exist_ok=True)
    path = manifest_dir / "session.toml"
    path.write_text(body, encoding="utf-8")
    return path


# --- Severity --------------------------------------------------------------


def test_severity_labels_and_roundtrip() -> None:
    assert Severity.HARD_BLOCK.label == "HARD-BLOCK"
    assert Severity.ADVISORY.label == "ADVISORY"
    assert Severity.INFO.label == "INFO"
    for member in Severity:
        assert Severity.from_label(member.label) is member


def test_severity_from_label_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown severity label"):
        Severity.from_label("CRITICAL")


def test_severity_sort_rank_orders_hard_block_first() -> None:
    assert int(Severity.HARD_BLOCK) < int(Severity.ADVISORY) < int(Severity.INFO)


def test_severity_members_are_truthy() -> None:
    # Pin: bool(HARD_BLOCK) must be True, not False (the int rank is 0
    # which would otherwise be falsy — see __bool__ override comment).
    assert bool(Severity.HARD_BLOCK) is True
    assert bool(Severity.ADVISORY) is True
    assert bool(Severity.INFO) is True


# --- RuleResult ------------------------------------------------------------


def _result(**overrides: object) -> RuleResult:
    base: dict[str, object] = {
        "severity": Severity.HARD_BLOCK,
        "code": "FA-AUTHORING-V2-EXPORTS",
        "path": "src/fa/foo.py",
        "message": "msg",
        "remediation": "fix it",
        "rule_input_hash": "sha256:abc",
    }
    base.update(overrides)
    return RuleResult(**base)  # type: ignore[arg-type]


def test_rule_result_is_frozen() -> None:
    result = _result()
    with pytest.raises(AttributeError):
        result.code = "other"  # type: ignore[misc]


def test_rule_result_to_dict_shape() -> None:
    payload = _result(line=12, column=3, expires_on="2026-12-31").to_dict()
    assert payload == {
        "severity": "HARD-BLOCK",
        "code": "FA-AUTHORING-V2-EXPORTS",
        "path": "src/fa/foo.py",
        "line": 12,
        "column": 3,
        "message": "msg",
        "remediation": "fix it",
        "expires_on": "2026-12-31",
        "rule_input_hash": "sha256:abc",
    }


def test_rule_result_sort_key_none_line_sorts_first() -> None:
    assert _result(line=None).sort_key()[3] == -1
    assert _result(line=5).sort_key()[3] == 5


# --- manifest parsing (fail-closed) ----------------------------------------


def test_parse_manifest_valid(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        '[kernel]\nversion = "0.1"\n\n[session]\nid = "sess-1"\nseam = ["a", "b"]\n',
    )
    manifest = parse_manifest(path)
    assert isinstance(manifest, Manifest)
    assert manifest.kernel_version == KERNEL_VERSION
    assert manifest.session_id == "sess-1"
    assert manifest.seam == ("a", "b")
    assert manifest.raw_bytes == path.read_bytes()


def test_parse_manifest_minimal_kernel_only(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n')
    manifest = parse_manifest(path)
    assert manifest.session_id is None
    assert manifest.seam == ()


def test_parse_manifest_session_without_seam(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[session]\nid = "s"\n')
    manifest = parse_manifest(path)
    assert manifest.session_id == "s"
    assert manifest.seam == ()


def test_parse_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError) as excinfo:
        parse_manifest(tmp_path / "nope.toml")
    assert excinfo.value.diagnostic.code == "FA-AUTHORING-V0-MANIFEST"
    assert "not readable" in excinfo.value.diagnostic.message


def test_parse_manifest_invalid_toml(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, "this is = = not toml")
    with pytest.raises(ManifestError, match="not valid TOML"):
        parse_manifest(path)


def test_parse_manifest_unknown_table(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[bogus]\nx = 1\n')
    with pytest.raises(ManifestError, match="unknown manifest table"):
        parse_manifest(path)


def test_parse_manifest_missing_kernel_table(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[session]\nid = "x"\n')
    with pytest.raises(ManifestError, match=r"missing required table \[kernel\]"):
        parse_manifest(path)


def test_parse_manifest_kernel_not_table(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, 'kernel = "scalar"\n')
    with pytest.raises(ManifestError, match=r"\[kernel\] must be a table"):
        parse_manifest(path)


def test_parse_manifest_unknown_kernel_key(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\nextra = 1\n')
    with pytest.raises(ManifestError, match=r"unknown key\(s\) in \[kernel\]"):
        parse_manifest(path)


def test_parse_manifest_version_wrong_type(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, "[kernel]\nversion = 1\n")
    with pytest.raises(ManifestError, match="must be a string"):
        parse_manifest(path)


def test_parse_manifest_version_mismatch(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "9.9"\n')
    with pytest.raises(ManifestError, match="!= supported"):
        parse_manifest(path)


def test_parse_manifest_session_not_table(tmp_path: Path) -> None:
    # `session` as a top-level scalar (not a table) is fail-closed.
    path = _write_manifest(tmp_path, 'session = 1\n[kernel]\nversion = "0.1"\n')
    with pytest.raises(ManifestError, match=r"\[session\] must be a table"):
        parse_manifest(path)


def test_parse_manifest_unknown_session_key(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[session]\nbogus = 1\n')
    with pytest.raises(ManifestError, match=r"unknown key\(s\) in \[session\]"):
        parse_manifest(path)


def test_parse_manifest_session_id_wrong_type(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[session]\nid = 7\n')
    with pytest.raises(ManifestError, match=r"session\.id must be a string"):
        parse_manifest(path)


def test_parse_manifest_seam_wrong_type(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[session]\nseam = "a"\n')
    with pytest.raises(ManifestError, match="seam must be a list of strings"):
        parse_manifest(path)


def test_parse_manifest_seam_non_string_element(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n\n[session]\nseam = ["a", 2]\n')
    with pytest.raises(ManifestError, match="seam must be a list of strings"):
        parse_manifest(path)


# --- enumeration -----------------------------------------------------------


def test_enumerate_paths_sorted_and_prunes_skip_dirs(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    (tmp_path / "b.py").write_text("b\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("a\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("x\n", encoding="utf-8")

    paths = enumerate_paths(tmp_path)
    assert paths == tuple(sorted(paths))
    assert "a.py" in paths and "b.py" in paths
    assert not any(p.startswith(".git/") for p in paths)
    assert not any("__pycache__" in p for p in paths)


def test_enumerate_paths_skips_symlinks(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    (tmp_path / "real.py").write_text("x\n", encoding="utf-8")
    link = tmp_path / "link.py"
    # Windows requires admin rights for symlinks by default; skip if not available
    try:
        link.symlink_to(tmp_path / "real.py")
    except (OSError, NotImplementedError):
        # Skip test on systems without symlink support
        return
    paths = enumerate_paths(tmp_path)
    assert "real.py" in paths
    assert "link.py" not in paths


# --- run_all ---------------------------------------------------------------


def test_run_all_clean_tree_empty_diagnostics(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    report = run_all(tmp_path)
    assert isinstance(report, KernelReport)
    assert report.diagnostics == ()
    assert report.exit_code == 0
    assert report.kernel_version == KERNEL_VERSION
    assert report.session_hash is None
    assert report.snapshot_id.startswith("sha256:")
    assert report.kernel_hash.startswith("sha256:")
    assert report.rule_pack_hash.startswith("sha256:")


def test_run_all_is_deterministic(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    first = run_all(tmp_path)
    second = run_all(tmp_path)
    assert first.snapshot_id == second.snapshot_id
    assert first.kernel_hash == second.kernel_hash
    assert first.rule_pack_hash == second.rule_pack_hash


def test_run_all_snapshot_changes_with_content(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    before = run_all(tmp_path).snapshot_id
    (tmp_path / "new.py").write_text("new\n", encoding="utf-8")
    after = run_all(tmp_path).snapshot_id
    assert before != after


def test_run_all_empty_snapshot_fails_closed(tmp_path: Path) -> None:
    # An empty directory has no files: fail-closed HARD-BLOCK.
    report = run_all(tmp_path)
    assert report.exit_code == 1
    assert [d.code for d in report.diagnostics] == ["FA-AUTHORING-V0-SNAPSHOT"]


def test_run_all_with_manifest_binds_session_hash(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    manifest = _write_manifest(tmp_path, '[kernel]\nversion = "0.1"\n')
    report = run_all(tmp_path, manifest_path=manifest)
    assert report.session_hash is not None
    assert report.session_hash.startswith("sha256:")
    assert report.exit_code == 0


def test_run_all_bad_manifest_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    manifest = _write_manifest(tmp_path, '[kernel]\nversion = "9.9"\n')
    report = run_all(tmp_path, manifest_path=manifest)
    assert report.exit_code == 1
    assert any(d.code == "FA-AUTHORING-V0-MANIFEST" for d in report.diagnostics)
    assert report.session_hash is None


def test_run_all_dispatches_rule_results_sorted(tmp_path: Path) -> None:
    _make_workspace(tmp_path)

    def rule(context: RuleContext) -> list[RuleResult]:
        assert context.files  # the kernel shares its sorted snapshot
        return [
            _result(severity=Severity.INFO, code="FA-AUTHORING-V5-DOCS", path="z.md"),
            _result(severity=Severity.HARD_BLOCK, code="FA-AUTHORING-V2-EXPORTS", path="a.py"),
        ]

    report = run_all(tmp_path, rules=(rule,))
    codes = [d.code for d in report.diagnostics]
    # HARD-BLOCK (rank 0) sorts before INFO (rank 2).
    assert codes == ["FA-AUTHORING-V2-EXPORTS", "FA-AUTHORING-V5-DOCS"]
    assert report.exit_code == 1


def test_run_all_wraps_rule_crash(tmp_path: Path) -> None:
    _make_workspace(tmp_path)

    def boom(context: RuleContext) -> list[RuleResult]:
        raise RuntimeError("kaboom")

    report = run_all(tmp_path, rules=(boom,))
    assert report.exit_code == 1
    crash = [d for d in report.diagnostics if d.code == "FA-AUTHORING-V0-RULE-CRASH"]
    assert len(crash) == 1
    assert "kaboom" in crash[0].message


def test_run_all_advisory_rule_does_not_fail(tmp_path: Path) -> None:
    _make_workspace(tmp_path)

    def rule(context: RuleContext) -> list[RuleResult]:
        return [_result(severity=Severity.ADVISORY, expires_on="2026-12-31")]

    report = run_all(tmp_path, rules=(rule,))
    assert report.exit_code == 0
    assert report.diagnostics[0].severity is Severity.ADVISORY


# --- rendering -------------------------------------------------------------


def test_render_json_roundtrips(tmp_path: Path) -> None:
    import json

    _make_workspace(tmp_path)
    report = run_all(tmp_path)
    payload = json.loads(render_json(report))
    assert payload["kernel_version"] == KERNEL_VERSION
    assert payload["exit_code"] == 0
    assert payload["diagnostics"] == []


def test_render_text_lists_diagnostics(tmp_path: Path) -> None:
    _make_workspace(tmp_path)

    def rule(context: RuleContext) -> list[RuleResult]:
        return [_result(line=7)]

    text = render_text(run_all(tmp_path, rules=(rule,)))
    assert "kernel 0.1" in text
    assert "[HARD-BLOCK] FA-AUTHORING-V2-EXPORTS src/fa/foo.py:7" in text


def test_authoring_tcb_imports_only_stdlib() -> None:
    """ADR-11-I1: authoring_tcb.py MUST import only stdlib modules."""
    import ast
    import sys

    import fa.authoring_tcb as authoring_tcb

    source = Path(authoring_tcb.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    stdlib = set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in stdlib, f"{alias.name} is not stdlib"
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.level == 0:
                root = node.module.split(".")[0]
                assert root in stdlib, f"{node.module} is not stdlib"


def test_enumerate_paths_skips_symlink_to_directory(tmp_path: Path) -> None:
    """Symlink-to-directory should not be enumerated (ADR-11-I1)."""
    _make_workspace(tmp_path)
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "file.py").write_text("x\n", encoding="utf-8")

    link_dir = tmp_path / "link_dir"
    # Windows requires admin rights for symlinks by default; skip if not available
    try:
        link_dir.symlink_to(real_dir)
    except (OSError, NotImplementedError):
        # Skip test on systems without symlink support
        return

    paths = enumerate_paths(tmp_path)
    assert "real_dir/file.py" in paths
    assert "link_dir/file.py" not in paths


# --- V0 pre-pass diagnostics -----------------------------------------------


def test_run_all_emits_unparsable_diagnostic_for_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    (tmp_path / "src" / "fa_demo").mkdir(parents=True)
    (tmp_path / "src" / "fa_demo" / "broken.py").write_text("def f(:\n  pass\n")
    report = run_all(tmp_path)
    codes = [d.code for d in report.diagnostics]
    assert "FA-AUTHORING-V0-UNPARSABLE" in codes
    bad = next(d for d in report.diagnostics if d.code == "FA-AUTHORING-V0-UNPARSABLE")
    assert bad.severity is Severity.HARD_BLOCK
    assert bad.path == "src/fa_demo/broken.py"


def test_run_all_skips_corpus_files_for_unparsable_check(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    (tmp_path / "catch-corpus" / "F-X").mkdir(parents=True)
    (tmp_path / "catch-corpus" / "F-X" / "broken.py").write_text("def f(:\n  pass\n")
    report = run_all(tmp_path)
    # Corpus fixtures may be intentionally malformed; the kernel skips them.
    assert all(d.code != "FA-AUTHORING-V0-UNPARSABLE" for d in report.diagnostics)


# --- KernelReport audit fields ---------------------------------------------


def test_allowlist_signature_changes_with_rule_set(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    (tmp_path / "src" / "fa_demo").mkdir(parents=True)
    (tmp_path / "src" / "fa_demo" / "m.py").write_text("def public(): pass\n__all__ = []\n")
    from fa.authoring_rules import RULE_ALLOWLIST, EXPORTS_COMPLETENESS

    full = run_all(tmp_path, rules=RULE_ALLOWLIST)
    empty = run_all(tmp_path, rules=())
    one = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert full.dispatched_count == 3
    assert empty.dispatched_count == 0
    assert one.dispatched_count == 1
    assert full.allowlist_signature != empty.allowlist_signature
    assert full.allowlist_signature != one.allowlist_signature
    assert empty.allowlist_signature != one.allowlist_signature


def test_allowlist_signature_is_order_insensitive(tmp_path: Path) -> None:
    """The signature sorts the rule keys, so dispatch order doesn't leak."""
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    from fa.authoring_rules import EXPORTS_COMPLETENESS, TEST_SEMANTIC_DECAY

    forward = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS, TEST_SEMANTIC_DECAY))
    reverse = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY, EXPORTS_COMPLETENESS))
    assert forward.allowlist_signature == reverse.allowlist_signature


# --- V0-ADVISORY-UNDATED synthesis ------------------------------------------


def test_advisory_without_expires_on_synthesises_v0_diagnostic(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")

    class _UndatedAdvisoryRule:
        __name__ = "undated_advisory_rule"

        def __call__(self, context: RuleContext) -> list[RuleResult]:
            return [
                RuleResult(
                    severity=Severity.ADVISORY,
                    code="FA-AUTHORING-V99-TEST-ADVISORY",
                    path="x.py",
                    line=1,
                    message="m",
                    remediation="r",
                    rule_input_hash="sha256:" + "0" * 64,
                    # expires_on intentionally omitted
                )
            ]

    report = run_all(tmp_path, rules=(_UndatedAdvisoryRule(),))
    codes = [d.code for d in report.diagnostics]
    assert "FA-AUTHORING-V99-TEST-ADVISORY" in codes
    assert "FA-AUTHORING-V0-ADVISORY-UNDATED" in codes
    synth = next(d for d in report.diagnostics if d.code == "FA-AUTHORING-V0-ADVISORY-UNDATED")
    assert synth.severity is Severity.ADVISORY
    assert synth.expires_on == "9999-12-31"
    # Synth itself does NOT recursively trigger another synth (sentinel breaks the loop).
    assert sum(1 for d in report.diagnostics if d.code == "FA-AUTHORING-V0-ADVISORY-UNDATED") == 1


def test_dated_advisory_does_not_synthesise(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")

    class _DatedAdvisoryRule:
        __name__ = "dated_advisory_rule"

        def __call__(self, context: RuleContext) -> list[RuleResult]:
            return [
                RuleResult(
                    severity=Severity.ADVISORY,
                    code="FA-AUTHORING-V99-DATED",
                    path="x.py",
                    line=1,
                    message="m",
                    remediation="r",
                    rule_input_hash="sha256:" + "0" * 64,
                    expires_on="2027-01-01",
                )
            ]

    report = run_all(tmp_path, rules=(_DatedAdvisoryRule(),))
    assert all(d.code != "FA-AUTHORING-V0-ADVISORY-UNDATED" for d in report.diagnostics)
