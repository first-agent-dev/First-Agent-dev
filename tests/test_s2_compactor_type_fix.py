"""Kill-check tests for S2: Fix compactor_chain type erasure + double-getattr.

Verifies:
1. compactor_chain is typed as ProviderChain | None (not Any | None)
2. model_slug is accessed via direct attribute (not double-getattr)
3. compactor_chain=None → compact() returns local fallback (not crash)
4. compactor_chain with real config → model_slug comes from config.model
5. No getattr on compactor_chain for config/model access in source
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.inner_loop.compaction.compactor import FullLLMCompactor
from fa.providers import ProviderChain

COMPACTOR_PATH = Path("src/fa/inner_loop/compaction/compactor.py")


# ── Kill-check 1: compactor_chain=None returns local fallback ─────────


def test_compactor_chain_none_returns_local_fallback() -> None:
    """When compactor_chain is None, compact() must return the local
    fallback truncation result — not crash."""
    compactor = FullLLMCompactor(compactor_chain=None)
    history = "\n".join(f"Line {i}" for i in range(150))
    result = compactor.compact(history)

    # Must return the fallback format with 4 required headers
    assert "## PREVIOUSLY" in result
    assert "## PARKED" in result
    assert "## CURRENT" in result
    assert "## NEXT ACTION" in result


# ── Kill-check 2: compactor_chain with config uses config.model ───────


def test_compactor_chain_uses_config_model_directly() -> None:
    """When compactor_chain has a real ChainConfig with .config.model,
    the model_slug in the RequestInfo must come from config.model."""
    from tests.fixtures.session_wiring import make_test_chain_config

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        model="test-compactor-model",
        context_limit=100000,
    )
    mock_response = MagicMock()
    mock_response.text = (
        "## PREVIOUSLY\nDone.\n\n## PARKED\nNone.\n\n"
        "## CURRENT\nOngoing.\n\n## NEXT ACTION\nContinue."
    )
    mock_chain.request.return_value = (mock_response, "call-123", [])

    compactor = FullLLMCompactor(compactor_chain=mock_chain)
    compactor.compact("History content")

    # Verify the request was made and the model_slug came from config.model
    assert mock_chain.request.called
    request_arg = mock_chain.request.call_args[0][0]
    assert request_arg.model_slug == "test-compactor-model"


# ── Kill-check 3: no getattr on compactor_chain for config/model ──────


def test_no_getattr_on_compactor_chain_config_model() -> None:
    """Source code must not use getattr to access compactor_chain.config.model.
    Direct attribute access is required."""
    content = COMPACTOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "getattr":
                # Check if any string arg is "config" or "model" in the context
                # of compactor_chain access
                string_args = [
                    arg.value for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ]
                if "config" in string_args or "model" in string_args:
                    # Check context: is this on compactor_chain?
                    pytest.fail(
                        f"Found getattr(..., {string_args}, ...) at line {node.lineno}. "
                        f"Use direct attribute access on compactor_chain instead."
                    )


# ── Kill-check 4: compactor_chain type is ProviderChain | None ────────


def test_compactor_chain_type_is_provider_chain() -> None:
    """The __init__ parameter must be typed as ProviderChain | None, not Any | None."""
    sig = inspect.signature(FullLLMCompactor.__init__)
    param = sig.parameters.get("compactor_chain")
    assert param is not None, "compactor_chain parameter not found"

    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        pytest.fail("compactor_chain has no type annotation")

    annotation_str = str(annotation)
    assert "ProviderChain" in annotation_str, (
        f"Expected ProviderChain in type annotation, got: {annotation_str}"
    )
    assert "Any" not in annotation_str, (
        f"Found 'Any' in type annotation — should be ProviderChain | None: {annotation_str}"
    )


# ── Kill-check 5: direct attribute access pattern exists ──────────────


def test_direct_model_access_pattern_exists() -> None:
    """Source code must contain `self.compactor_chain.config.model` pattern."""
    content = COMPACTOR_PATH.read_text(encoding="utf-8")
    assert "self.compactor_chain.config.model" in content, (
        "Expected direct access `self.compactor_chain.config.model` not found"
    )


# ── Kill-check 6: no Any type annotation on compactor_chain parameter ─


def test_no_any_type_on_compactor_chain_in_source() -> None:
    """The source code must not use `Any | None` for the compactor_chain parameter.
    This is a static AST check on the source, not the runtime signature."""
    content = COMPACTOR_PATH.read_text(encoding="utf-8")

    # Look for the __init__ definition and check its parameter annotations
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            for arg in node.args.args:
                if arg.arg == "compactor_chain":
                    # Check the annotation doesn't contain 'Any'
                    if arg.annotation is not None:
                        annotation_source = ast.unparse(arg.annotation)
                        assert "Any" not in annotation_source, (
                            f"compactor_chain annotation contains 'Any': {annotation_source}. "
                            f"Should be 'ProviderChain | None'."
                        )
