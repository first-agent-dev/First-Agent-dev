"""FailureClassifier (Wave-2 R-3) behavior tests.

Assert real category + action mapping, not just "function returns
something". Each test pins a specific error code or message keyword to
a specific (category, action) pair, so regressing the lookup table
breaks at least one test loudly.
"""

from __future__ import annotations

import pytest

from fa.inner_loop.recovery import (
    FailureCategory,
    RecoveryAction,
    RecoveryActionKind,
    classify,
    classify_result,
)
from fa.inner_loop.registry import ToolError, ToolResult


@pytest.mark.parametrize(
    ("code", "expected_category", "expected_kind"),
    [
        ("invalid_params", FailureCategory.INVALID_ARGUMENTS, RecoveryActionKind.RETRY),
        ("invalid_payload", FailureCategory.INVALID_ARGUMENTS, RecoveryActionKind.RETRY),
        ("hook_deny", FailureCategory.POLICY_DENIED, RecoveryActionKind.ESCALATE),
        ("read_failed", FailureCategory.UNEXPECTED_ENVIRONMENTS, RecoveryActionKind.RETRY),
        ("write_failed", FailureCategory.UNEXPECTED_ENVIRONMENTS, RecoveryActionKind.RETRY),
        ("command_timeout", FailureCategory.PROVIDER_ERRORS, RecoveryActionKind.RETRY),
        ("command_failed", FailureCategory.BROKEN_BUILD, RecoveryActionKind.RETRY),
        ("audit_failure", FailureCategory.UNEXPECTED_ENVIRONMENTS, RecoveryActionKind.RETRY),
    ],
)
def test_classify_routes_known_codes(
    code: str,
    expected_category: FailureCategory,
    expected_kind: RecoveryActionKind,
) -> None:
    """Each M-1 error code maps to one specific category + action."""

    action = classify(ToolError(code=code, message="", retryable=True), target="t")
    assert action.category == expected_category
    assert action.kind == expected_kind
    assert action.target == "t"


@pytest.mark.parametrize(
    ("keyword_message", "expected_category"),
    [
        ("HTTP 429 too many requests", FailureCategory.RATE_LIMITED),
        ("rate limit exceeded", FailureCategory.RATE_LIMITED),
        ("401 unauthorized", FailureCategory.AUTH_FAILURE),
        ("forbidden", FailureCategory.AUTH_FAILURE),
        ("maximum context length exceeded", FailureCategory.CONTEXT_EXHAUSTED),
        ("token limit reached", FailureCategory.CONTEXT_EXHAUSTED),
        ("DSV_VIOLATION on rule R-9", FailureCategory.VERIFICATION_FAILED),
        ("provider returned 500", FailureCategory.PROVIDER_ERRORS),
        ("connection refused", FailureCategory.PROVIDER_ERRORS),
    ],
)
def test_classify_falls_back_to_keyword_match(
    keyword_message: str,
    expected_category: FailureCategory,
) -> None:
    """Codes outside the lookup table get categorized via keyword match."""

    # ``custom_error_code`` is intentionally NOT in the code table so
    # the classifier must fall back to ``message.lower()`` keyword
    # matching.
    error = ToolError(code="custom_error_code", message=keyword_message, retryable=True)
    action = classify(error, target="t")
    assert (
        action.category == expected_category
    ), f"{keyword_message!r} should map to {expected_category}, got {action.category}"


def test_classify_unknown_code_with_no_keywords_escalates() -> None:
    """A novel error → ``UNKNOWN`` → ``ESCALATE`` (fail-safe default)."""

    error = ToolError(code="brand_new_code", message="something opaque", retryable=False)
    action = classify(error)
    assert action.category == FailureCategory.UNKNOWN
    assert action.kind == RecoveryActionKind.ESCALATE
    assert action.retryable is False
    assert action.reason == "something opaque"


def test_classify_propagates_retryable_through() -> None:
    """``ToolError.retryable`` must round-trip into ``RecoveryAction``."""

    error = ToolError(code="invalid_params", message="bad arg", retryable=True)
    assert classify(error).retryable is True

    error2 = ToolError(code="invalid_params", message="bad arg", retryable=False)
    assert classify(error2).retryable is False


def test_classify_result_returns_none_for_success() -> None:
    """No error → no recovery action; loop driver must short-circuit."""

    success = ToolResult.ok("did the thing")
    assert classify_result(success, target="t") is None


def test_classify_result_returns_action_for_failure() -> None:
    """Failure result → :class:`RecoveryAction` with the same fields."""

    failure = ToolResult.fail("invalid_params", "missing field", retryable=True)
    action = classify_result(failure, target="fs.read_file")
    assert isinstance(action, RecoveryAction)
    assert action.category == FailureCategory.INVALID_ARGUMENTS
    assert action.kind == RecoveryActionKind.RETRY
    assert action.target == "fs.read_file"
    assert action.reason == "missing field"
    assert action.retryable is True


def test_code_lookup_wins_over_keyword_match() -> None:
    """A known code dominates even when the message contains a keyword.

    Regression: ``invalid_params`` with «rate limited» phrasing in the
    message must still classify as ``INVALID_ARGUMENTS`` — codes are
    the authoritative signal, message-keywords are the fallback only.
    """

    error = ToolError(
        code="invalid_params",
        message="rate limit on retry knob",
        retryable=True,
    )
    action = classify(error)
    assert action.category == FailureCategory.INVALID_ARGUMENTS
