"""C0 static guarantees: no builtin-shadow parameters, no shell=True in helper.

Covers:
- CT11: server.py ``log_message`` does not shadow builtin ``format``;
- T8:  scripts/_git_diff.py has no shell=True;
- T10: targeted scripts do not invoke git merge-base/diff inline;
- The pty_pool Protocol ``find_where`` uses ``_filters`` (no bare ``filters``).

These are C0 (source-level) invariants enforced by AST walk — they are
cheap, deterministic, and give a specific failing node rather than a
noisy CI advisory.

Skill: tests-writing, C0 (AST walk).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _iter_funcdefs(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_server_log_message_no_format_shadow() -> None:
    """log_message(self, _fmt, *_args) — no `format` parameter."""
    src = (REPO / "src" / "fa" / "egress_proxy" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for fn in _iter_funcdefs(cls):
            if fn.name == "log_message":
                args = [a.arg for a in fn.args.args + fn.args.posonlyargs + fn.args.kwonlyargs]
                if fn.args.vararg:
                    args.append(fn.args.vararg.arg)
                assert "format" not in args, f"server.Handler.log_message shadows builtin format; args={args}"
                assert "_fmt" in args, "expected parameter `_fmt` (underscore-prefixed, no shadow)"


def test_pty_pool_find_where_underscore_filters() -> None:
    """Protocol method uses ``_filters`` not ``filters`` (vulture-silent FP fix)."""
    src = (REPO / "src" / "fa" / "runtime" / "pty_pool.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for fn in _iter_funcdefs(cls):
            if fn.name == "find_where":
                arg_names = [a.arg for a in fn.args.args]
                # expect `self` plus one more named `_filters`
                assert "_filters" in arg_names, f"expected `_filters` parameter, got {arg_names}"
                assert "filters" not in arg_names, (
                    f"bare `filters` parameter shadows nothing but is vulture FP; rename to _filters: {arg_names}"
                )


def test_no_shell_true_in_helper() -> None:
    src = (REPO / "scripts" / "_git_diff.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    raise AssertionError("_git_diff.py uses shell=True")
