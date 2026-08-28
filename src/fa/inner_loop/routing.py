"""Deterministic routing predicates for the chat role (S7, CT8 + CT10).

The scope estimator (:mod:`fa.inner_loop.scope_estimator`) is a *router*: it
runs before any work happens and proposes an operating point. This module turns
that proposal into two mechanical consequences:

* **CT8 / Layer 1** — a pre-run capability gate. When the estimator is
  confident a task is repo-scale, the chat role's write tools are not
  registered at all, so escalation is the path of least resistance rather than
  a suggestion the model may ignore.
* **CT10 / Layer 2** — a mid-run tripwire. When a run estimated as chat-sized
  outgrows that estimate, one observation naming ``invoke_workflow`` is added
  to the next request.

Why the threshold is 0.8 and not "always"
-----------------------------------------
Measured 2026-08-27 over 15 hand-written realistic tasks scored against
senior-engineer labels: the estimator is **60% accurate overall (9/15)** with
**six under-scopes and zero over-scopes**. Accuracy is strongly stratified by
its own confidence:

===============  ========  ========
confidence       correct   accuracy
===============  ========  ========
0.8              4/4       100%
0.6              3/5       60%
0.3              2/6       33%
===============  ========  ========

Gating the 0.8 bucket binds exactly where the estimator has never been wrong.
Gating lower would withhold write tools from tasks that legitimately need them
— at 0.3 confidence the estimator is wrong two times in three. This is why the
gate keys on confidence and not on ``recommended_mode`` alone.

Because every observed error is an *under*-scope, the "don't interfere when the
task is simple" half of the requirement needs no mechanism at all: the
estimator has never over-scoped a simple task in measurement.

Scope of the guarantee (read before strengthening this)
-------------------------------------------------------
Layer 1 removes the *declared* write affordances (``fs_write_file``,
``fs_edit_file``, ``fs_spawn_subagent``). It does **not** make writes
impossible: ``fs_run_bash`` stays in the corpus and ``echo x > f.py`` still
works. The honest claim is "the model is not handed a write tool", not "the
model cannot write". Closing that path means denying general-write in the bash
gate, which this repo already tried and reverted — it denied 8/10 realistic
verifier commands such as ``pytest`` and ``mypy`` (see Q19 and the standing
xfail in ``tests/test_s5_isolation_boundary.py``). Do not re-litigate it here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    from fa.inner_loop.scope_estimator import OperatingPoint

__all__ = [
    "GATE_MIN_CONFIDENCE",
    "WITHHELD_WRITE_TOOLS",
    "should_withhold_write_tools",
]

# Confidence at or above which the estimator's ``workflow_linear`` verdict is
# binding. 0.8 is the estimator's top bucket and measured 4/4 correct; the 0.6
# bucket measured 3/5 and is deliberately NOT gated. See the module docstring.
GATE_MIN_CONFIDENCE: Final = 0.8

# Declared write affordances withheld when the gate fires. ``invoke_workflow``
# is deliberately absent from this set: escalation must remain reachable, or
# the gate would strand the run with no way forward.
WITHHELD_WRITE_TOOLS: Final = frozenset(
    {
        "fs_write_file",
        "fs_edit_file",
        "fs_spawn_subagent",
    }
)


def should_withhold_write_tools(
    point: OperatingPoint | None,
    *,
    role: str,
    gate_enabled: bool,
) -> bool:
    """Return ``True`` when the chat write tools must not be registered (CT8).

    Fails open on every ambiguous input. A gate that misfires costs an operator
    a capability they expected and reasonably assumed they had; a gate that
    fails open costs nothing beyond today's behaviour. When the two error
    directions are that asymmetric, the default belongs on the cheap side.

    Args:
        point: the estimator's operating point, or ``None`` when no estimate
            exists (non-chat role, or an empty task that ``estimate_scope``
            rejected).
        role: the live session role. Only ``"chat"`` is ever gated — the
            workflow stage roles own their own tool corpora and gating them
            would break the very escalation path this exists to protect.
        gate_enabled: the operator's ``chat_escalation_gate`` setting. An
            explicit ``False`` always wins over the estimator.

    Returns:
        ``True`` only when every condition holds: chat role, gate enabled, an
        estimate exists, it recommends ``workflow_linear``, and its confidence
        is at least :data:`GATE_MIN_CONFIDENCE`.
    """
    if not gate_enabled:
        return False
    if role != "chat":
        return False
    if point is None:
        return False
    if point.recommended_mode != "workflow_linear":
        return False
    return point.confidence >= GATE_MIN_CONFIDENCE
