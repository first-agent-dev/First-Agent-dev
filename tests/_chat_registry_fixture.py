"""Shared builder for the LIVE chat tool corpus.

Three test modules need the same thing: the tool registry a real
``fa run --role chat`` ships, which is ``cli._build_run_tool_registry`` with a
workflow context bound — not the profile registry and not
``build_chat_registry``. Assembling that takes ten lines of context plumbing,
and a third copy triggered pylint's ``duplicate-code``; per the tests-writing
skill (§"third copy of same mocks"), it is extracted here instead.

Kept deliberately thin: it wires production builders together and adds no
behaviour of its own, so it cannot become a place where tests quietly diverge
from production.
"""

from __future__ import annotations

from pathlib import Path

from fa.cli import _build_run_tool_registry, _make_workflow_ctx_provider
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits


def build_live_chat_registry(
    workspace: Path,
    *,
    role: str = "chat",
    parent_run_id: str = "run-parent",
    with_workflow_ctx: bool = True,
) -> ToolRegistry:
    """Build the exact registry a live ``fa run --role <role>`` would use.

    ``with_workflow_ctx=False`` exercises the degraded path — a chat registry
    built outside a live run, which legitimately has no pipeline to escalate
    into and must still be usable.
    """
    provider = None
    if with_workflow_ctx:
        provider = _make_workflow_ctx_provider(
            parent_run_id=parent_run_id,
            config=workspace / "models.yaml",
            workspace=workspace,
            max_turns=1,
            limits=RuntimeLimits(),
            session_context=None,
            run_context=None,
            session_db=None,
            transport=None,
            secrets=None,
        )
    return _build_run_tool_registry(
        role,
        workspace,
        bash_timeout_seconds=30,
        draft_store=PrDraftStore(workspace / "pr_draft.md"),
        workflow_ctx=provider,
    )
