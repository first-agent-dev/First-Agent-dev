#!/usr/bin/env python3
"""Stdlib entrypoint for the checked-out workspace readiness engine."""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    root = _repo_root()
    source = (root / "src").resolve()
    sys.path.insert(0, str(source))
    try:
        import fa.workspace_bootstrap as bootstrap

        module_path = Path(bootstrap.__file__).resolve()
        if not module_path.is_relative_to(source):
            raise ImportError(f"workspace bootstrap resolved outside checkout: {module_path}")
    except (ImportError, OSError) as exc:
        print(f"[WORKSPACE_BOOTSTRAP] cannot load checked-out readiness engine: {exc}", file=sys.stderr)
        return 70
    return bootstrap._main(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
