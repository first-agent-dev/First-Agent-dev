"""S13.5 conformance harness (offline) — thin re-export of the production matrix.

The matrix logic (scenario definitions + real composer/validator drive) lives in
``fa.providers.conformance`` so the ``fa conformance`` CLI command can run it
without importing test infrastructure. This module re-exports it for the test
package (``tests/conformance/``) so the CI ratchet and the CLI share ONE source
of truth.
"""

from __future__ import annotations

from fa.providers.conformance import (
    ConfCase,
    ConfRow,
    default_cases,
    matrix_to_text,
    run_conformance_matrix,
)

__all__ = [
    "ConfCase",
    "ConfRow",
    "default_cases",
    "matrix_to_text",
    "run_conformance_matrix",
]
