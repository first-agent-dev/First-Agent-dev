"""Shared builder for the unmanaged chat registry composition root.

This helper exercises ``cli._build_run_tool_registry`` with a workflow context
but without a managed stage lease. It is used for prompt/profile coherence, not
to claim the full managed production corpus; managed R13 is attached separately
by the live stage caller. A third copy of this context plumbing triggered
pylint's ``duplicate-code``, so it is extracted here.

Kept deliberately thin: it wires production builders together and adds no
behaviour of its own, so it cannot become a place where tests quietly diverge
from production.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.cli import _build_run_tool_registry, _make_workflow_ctx_provider
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.providers.base import Transport


def build_live_chat_registry(
    workspace: Path,
    *,
    role: str = "chat",
    parent_run_id: str = "run-parent",
    with_workflow_ctx: bool = True,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
) -> ToolRegistry:
    """Build the CLI registry before the managed stage-edge capability is added.

    ``with_workflow_ctx=False`` exercises the degraded chat path with no
    pipeline to escalate into; neither form exposes the legacy host runner.
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
            transport=transport,
            secrets=secrets,
        )
    return _build_run_tool_registry(
        role,
        workspace,
        bash_timeout_seconds=30,
        draft_store=PrDraftStore(workspace / "pr_draft.md"),
        workflow_ctx=provider,
    )
