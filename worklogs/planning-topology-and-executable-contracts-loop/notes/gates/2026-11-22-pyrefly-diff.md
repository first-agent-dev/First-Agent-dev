# pyrefly: base `1acb56b` -> head `ceab747`

`tests/test_pyrefly_import_topology.py::test_pyrefly_check_passes` asserts a **count of zero**, and it is
red on both sides — so the count alone says nothing about whether this branch added anything. Same method
as the gate tracker: run the same command in both trees, normalise to a list, diff.

```
# base worktree at 1acb56b, `.venv` symlinked in, PYTHONPATH=<worktree>/src
python -m pyrefly check   > /tmp/pyrefly-base.txt   # exit 1
# branch checkout
python -m pyrefly check   > /tmp/pyrefly-head.txt   # exit 1
```

| | base `1acb56b` | head `ceab747` |
|---|---|---|
| reported errors | 63 | 59 |
| unique findings (`file` + message, line:col stripped) | 27 | 26 |
| **new** | | **0** |
| gone | 1 | |

The one finding that left is the same one mypy lost — the tests were building a `SimpleNamespace` and
passing it to `_cmd_invoke_workflow(args: Namespace)`:

```
- Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace`
  in function `fa.cli._cmd_invoke_workflow` [bad-argument-type]
```

So the 59 remaining pyrefly findings are **pre-existing red**, and the gate for this branch is `0 new`,
not `0`. A `pyrefly` gate is not yet wired into `scripts/gate_tracker.py`; until it is, this file is the
recording. Note that the file-level test asserts a total, which is exactly the quantity E608 argues is
the wrong unit — the count moved 63 -> 59 while saying nothing about direction.
