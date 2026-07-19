"""Regression test for FINDING-V1: import os shadowing in _cmd_run.

The `import os` inside the PtyPool try block (line ~1895) was shadowing
the module-level `import os`, making Python treat `os` as a local variable
throughout `_cmd_run`. This caused UnboundLocalError on:

1. `os.environ["NO_COLOR"] = "1"` (line 1667, guarded by --no-color)
2. `os.getpid()` (line 1761, hit when --run-id is empty)

The fix removes the inner `import os`, relying on the module-level import.

Kill-check: re-introducing `import os` inside _cmd_run makes this test fail.
"""

from __future__ import annotations

import inspect

from fa.cli import _cmd_run


def test_cmd_run_os_not_local_variable() -> None:
    """C0: _cmd_run must NOT have `os` as a local variable.

    If `import os` appears inside _cmd_run, Python treats `os` as local
    for the entire function scope, causing UnboundLocalError on earlier
    `os.environ` and `os.getpid()` references.

    Kill-check: adding `import os` anywhere inside _cmd_run makes this
    test fail because `os` appears in co_varnames.
    """
    code = _cmd_run.__code__
    assert "os" not in code.co_varnames, (
        "`os` is a local variable in _cmd_run — this means an `import os` "
        "statement inside the function body is shadowing the module-level "
        "import. Remove the inner `import os` to fix UnboundLocalError on "
        "os.environ/os.getpid()."
    )


def test_cmd_run_os_references_use_module_import() -> None:
    """C0: Verify _cmd_run uses module-level os for os.environ and os.getpid.

    Checks that the function's compiled code references `os` as a global
    (LOAD_GLOBAL) rather than a local (LOAD_FAST) variable.
    """
    # Disassemble and check that `os` accesses use LOAD_GLOBAL, not LOAD_FAST
    import dis

    instructions = list(dis.get_instructions(_cmd_run))
    os_loads = [i for i in instructions if i.argval == "os" and "LOAD" in i.opname]

    # All os loads should be LOAD_GLOBAL (or LOAD_NAME), never LOAD_FAST
    bad_loads = [i for i in os_loads if i.opname == "LOAD_FAST"]
    assert len(bad_loads) == 0, (
        f"Found LOAD_FAST for 'os' in _cmd_run at offset(s) "
        f"{[i.offset for i in bad_loads]} — `os` is being treated as a "
        f"local variable, which will cause UnboundLocalError."
    )
