"""Module-as-script entrypoint for the PR-intent hooks.

Invoked by the ``prepare-commit-msg`` / ``commit-msg`` shell wrappers
under :mod:`fa.hygiene.hooks` as ``python -m fa.hygiene
{prepare|validate} <commit-msg-file>``. Routing this through the
package's :mod:`__main__` (rather than ``python -m fa.hygiene.pr_intent``)
avoids the ``RuntimeWarning`` that fires when the package's
``__init__`` already imports ``pr_intent`` for re-export.
"""

from __future__ import annotations

from fa.hygiene.pr_intent import main

raise SystemExit(main())
