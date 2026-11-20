"""C1 — the provider-call record, pinned by shape and order.

This block decides nothing, which is exactly why it needs a test that says so:
a pure-logging extraction is the easiest place to lose a field or swap two rows
and still pass every behavioural test, because nothing downstream branches on
the trace. The rows are durable — ``fa stats`` reads ``llm_call`` — so their
shape is part of the contract.

Three properties:

* **order** — attempts, then the rollup, then the console line;
* **shape** — the rollup's ``chain`` entries carry the same fields as the
  individual attempt rows (minus the logical id, which the row already has);
* **absence** — ``cost_usd`` is not invented (BACKLOG I-33: no wired cost
  source; a placeholder reads as "free").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, override

import pytest

from fa.inner_loop.provider_turn import record_provider_call
from fa.inner_loop.state import EventLog
from fa.providers.errors import ProviderRequestShapeError
from fa.providers.types import ChainAttemptRecord

if TYPE_CHECKING:
    from fa.providers.base import ResponseInfo


class _Capture:
    """Minimal EventBus stand-in: records OutputEvents the way the driver sees them."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def emit(self, event: Any) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [event.type for event in self.events]


def _attempt(**over: Any) -> ChainAttemptRecord:
    base: dict[str, Any] = {
        "provider": "anthropic",
        "slug": "claude-x",
        "status": "ok",
        "ms": 12,
        "error": None,
    }
    base.update(over)
    return ChainAttemptRecord(**base)


class _Response:
    """Only the attributes `record_provider_call` reads — a structural fake.

    Typed as `Any` at the call boundary below: `ResponseInfo` is a protocol-ish
    carrier and building a real one here would couple this test to its
    constructor rather than to the record it is checking.
    """

    in_tokens = 100
    out_tokens = 20
    cache_read_input_tokens = 7
    cache_creation_input_tokens = 3
    text = "hello"
    tool_calls: tuple[Any, ...] = ()


def _run(
    tmp_path: Path,
    *,
    attempts: list[ChainAttemptRecord] | None = None,
    output: Any = None,
) -> EventLog:
    log = EventLog(tmp_path / "events.jsonl", run_id="r1")
    record_provider_call(
        log=log,
        output=output,
        response=cast("ResponseInfo", _Response()),
        attempts=attempts if attempts is not None else [_attempt()],
        logical_call_id="call-1",
        role="coder",
        model="claude-x",
        family="anthropic",
        turn=2,
        max_turns=5,
    )
    return log


def test_rows_and_console_come_out_in_the_documented_order(tmp_path: Path) -> None:
    """C1: attempts -> rollup -> console, as ONE interleaved sequence.

    Checking the two streams separately is not enough: a mutation that emitted
    the console line before the rollup left both assertions true and survived.
    The operator and `fa stats` read the same moment, so the order between the
    durable row and the console line is what is actually pinned here.
    """
    timeline: list[str] = []

    class _Timeline(_Capture):
        @override
        def emit(self, event: Any) -> None:
            timeline.append(f"console:{event.type}")
            super().emit(event)

    bus = _Timeline()
    log = _run(tmp_path, attempts=[_attempt(), _attempt(provider="openai", ms=30)], output=bus)

    timeline[:0] = [f"row:{row.kind}" for row in log.read_all()]

    assert timeline == [
        "row:provider_attempt",
        "row:provider_attempt",
        "row:llm_call",
        "console:llm_response",
    ]


def test_rollup_chain_matches_the_attempt_rows(tmp_path: Path) -> None:
    """C1: the same fields per attempt in both places, or the rollup lies.

    The rollup embeds a compact chain; ``fa stats`` reads it as the story of what
    happened. A field present on an attempt row and missing from the rollup makes
    the two disagree about the same call.
    """
    log = _run(tmp_path, attempts=[_attempt(provider="a", ms=1), _attempt(provider="b", ms=2)])

    rows = log.read_all()
    attempt_rows = [row.content for row in rows if row.kind == "provider_attempt"]
    rollup = next(row.content for row in rows if row.kind == "llm_call")

    shared = set(attempt_rows[0]) - {"logical_call_id"}
    chain = cast("list[dict[str, Any]]", rollup["chain"])
    for entry, attempt_row in zip(chain, attempt_rows, strict=True):
        assert set(entry) == shared
        assert {k: entry[k] for k in shared} == {k: attempt_row[k] for k in shared}


def test_every_attempt_row_carries_the_logical_call_id(tmp_path: Path) -> None:
    """The join key: without it the rows cannot be attached to a call."""
    log = _run(tmp_path, attempts=[_attempt(), _attempt()])

    attempt_rows = [row.content for row in log.read_all() if row.kind == "provider_attempt"]
    assert [row["logical_call_id"] for row in attempt_rows] == ["call-1", "call-1"]


def test_rollup_reports_total_wallclock_not_the_last_attempt(tmp_path: Path) -> None:
    """Two attempts at 12 + 30 ms are 42 ms of wallclock, not 30.

    The console line, by contrast, reports the last attempt's latency — that is
    what the operator sees as "how long the successful call took". Pinning both
    keeps a future "simplification" from making them agree for the wrong reason.
    """
    bus = _Capture()
    log = _run(tmp_path, attempts=[_attempt(ms=12), _attempt(ms=30)], output=bus)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert rollup["wallclock_ms"] == 42
    assert bus.events[0].data["ms"] == 30


@pytest.mark.parametrize("forbidden", ["cost_usd", "cost", "cost_estimate"])
def test_cost_is_absent_not_zero(tmp_path: Path, forbidden: str) -> None:
    """BACKLOG I-33: absence is honest, 0.0 would read as "this call was free"."""
    log = _run(tmp_path)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert forbidden not in rollup


def test_headless_run_still_writes_rows(tmp_path: Path) -> None:
    """``output=None`` suppresses the console only; the trace is durable state."""
    log = _run(tmp_path, output=None)

    assert [row.kind for row in log.read_all()] == ["provider_attempt", "llm_call"]


def test_no_attempts_does_not_raise(tmp_path: Path) -> None:
    """A response with an empty attempt list is representable; wallclock is 0."""
    bus = _Capture()
    log = _run(tmp_path, attempts=[], output=bus)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert rollup["chain"] == []
    assert rollup["wallclock_ms"] == 0
    assert bus.events[0].data["ms"] == 0


# ── Is the seam alive? The driver must go through it, not around it ──────
#
# A module with 16 passing tests proves the decision table is right; it does not
# prove the driver uses it. The same edge mutant bit `classify_budget` before, so
# this is checked behaviourally: make the chain fail, and assert the outcome the
# seam produced reaches `SessionOutcome`.


def test_driver_routes_provider_exhaustion_through_handle_provider_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the retry/stop decision is made by `provider_turn`, not re-inlined.

    The chain here is a real `ProviderChain` over a one-entry `FakeProvider`, not
    a mock: `drive_session` calls `chain.request()`, so the seam it goes through
    is the real one. Stubbing the chain instead would test the stub.
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.state import EventLog, SessionState
    from fa.providers import ChainConfig, ChainEntry, ProviderChain
    from fa.providers.errors import ProviderTransientError
    from tests.test_coder_loop import FakeProvider

    seen: list[str] = []
    real = coder_loop.handle_provider_failure

    def spy(exc: BaseException, **kwargs: Any) -> Any:
        seen.append(type(exc).__name__)
        return real(exc, **kwargs)

    # Patched where the driver LOOKS THE NAME UP: it imports the function at
    # module load, so patching `provider_turn` leaves the driver holding the
    # original. (Measured — that variant reports the seam dormant here while
    # the module's own tests stay green. Same trap as the ContextBudget patch.)
    monkeypatch.setattr(coder_loop, "handle_provider_failure", spy)

    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )
    provider = FakeProvider([ProviderTransientError("503", status=503, kind="service_unavailable")])
    chain = ProviderChain(
        ChainConfig(role="coder", name="test-model", family="", chain=(entry,)),
        provider_factory=lambda _e: provider,
        env={"TEST_KEY": "k"},
    )
    log = EventLog(tmp_path / "events.jsonl", run_id="seam")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="seam",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False, max_chain_retries=0),
    )

    outcome = coder_loop.drive_session(
        "seam", provider_chain=chain, registry=ToolRegistry(), hooks=HookRegistry(), state=state, max_turns=2
    )

    assert seen, "the driver never called handle_provider_failure — the seam is dormant"
    assert outcome.exit_code == 2 and outcome.stop_reason == "chain_exhausted"
    # The counter reached session state: its only consumer is the end-of-session
    # metric, so a driver that dropped the returned value would look identical.
    assert log.chain_exhaustion_count == 1


def test_driver_retries_the_turn_when_the_failure_says_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1: `ProviderRetry` must reach `continue`, not be flattened into a stop.

    Mutating the driver's retry branch to `if False` left every test green before
    this one existed: the stop path is exercised by the exhaustion scenario, and
    nothing noticed that a retryable failure had become terminal. ``max_retries=1``
    means the first exhaustion retries and the second stops, so one session
    exercises both halves of the decision.
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.state import EventLog, SessionState
    from fa.providers import ChainConfig, ChainEntry, ProviderChain
    from fa.providers.errors import ProviderTransientError
    from tests.test_coder_loop import FakeProvider

    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )
    failing = ProviderTransientError("503", status=503, kind="service_unavailable")
    provider = FakeProvider([failing, failing])
    chain = ProviderChain(
        ChainConfig(role="coder", name="test-model", family="", chain=(entry,)),
        provider_factory=lambda _e: provider,
        env={"TEST_KEY": "k"},
    )
    log = EventLog(tmp_path / "events.jsonl", run_id="retry")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="retry",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False, max_chain_retries=1),
    )

    outcome = coder_loop.drive_session(
        "retry", provider_chain=chain, registry=ToolRegistry(), hooks=HookRegistry(), state=state, max_turns=3
    )

    # Two turns were driven, and the event counter saw both exhaustions even
    # though only one of them was a retry.
    assert outcome.stop_reason == "chain_exhausted"
    assert outcome.turns == 2
    assert log.chain_exhaustion_count == 2
    assert provider.calls, "the retry must reach the provider again"


@pytest.mark.parametrize(
    ("error", "exit_code", "reason"),
    [
        (ProviderRequestShapeError("bad request body", status=400, provider="openrouter"), 2, "request_shape"),
        (KeyboardInterrupt(), 130, "abnormal_stop:interrupt"),
    ],
    ids=["shape", "interrupt"],
)
def test_driver_performs_the_stop_the_seam_reported(
    tmp_path: Path, error: BaseException, exit_code: int, reason: str
) -> None:
    """C1: the stop is the one `provider_turn` decided, not a constant.

    Hardcoding `finish_at(2, "chain_exhausted")` in the driver passed every test
    before this one: the exhaustion scenario asserts exactly that pair, so the
    wrong constant and the right value were indistinguishable. These two
    scenarios need different exit codes, which is what makes the constant visible.
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.state import EventLog, SessionState
    from fa.providers import ChainConfig, ChainEntry, ProviderChain

    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )

    class _Raises:
        """Provider that raises the given BaseException.

        `FakeProvider` tests `isinstance(item, Exception)`, and `KeyboardInterrupt`
        is a BaseException — it would be *returned* and then read as a response
        (measured: `AttributeError: 'KeyboardInterrupt' object has no attribute
        'in_tokens'`). The provider contract allows an interrupt mid-call, so the
        fake has to be able to produce one.
        """

        name = "raises"

        def request(self, request: Any, **_kwargs: Any) -> Any:
            raise error

    chain = ProviderChain(
        ChainConfig(role="coder", name="test-model", family="", chain=(entry,)),
        provider_factory=lambda _e: _Raises(),
        env={"TEST_KEY": "k"},
    )
    log = EventLog(tmp_path / "events.jsonl", run_id="stop")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="stop",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False, max_chain_retries=0),
    )

    outcome = coder_loop.drive_session(
        "stop", provider_chain=chain, registry=ToolRegistry(), hooks=HookRegistry(), state=state, max_turns=2
    )

    assert (outcome.exit_code, outcome.stop_reason) == (exit_code, reason)
    assert log.chain_exhaustion_count == 0  # neither path is a chain exhaustion


def test_composition_shape_failure_reports_identically_to_the_provider_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: both shape-failure origins produce the same exit and the same rows.

    There used to be two implementations of this reporting — a driver closure for
    the composition path and the handler for the provider path — and they drifted
    far enough that the console line was written twice. Now the driver delegates
    and only performs the stop. This test asserts the *composition* origin
    reaches that same code, which is the half the provider scenario cannot cover.
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.state import EventLog, SessionState
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    seen: list[str] = []
    real = coder_loop.handle_provider_failure

    def spy(exc: BaseException, **kwargs: Any) -> Any:
        seen.append(type(exc).__name__)
        return real(exc, **kwargs)

    monkeypatch.setattr(coder_loop, "handle_provider_failure", spy)

    log = EventLog(tmp_path / "events.jsonl", run_id="composition")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="composition",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    chain = make_mock_chain(context_limit=100_000)
    chain.request.return_value = mock_success_response("done")

    # The composer raises before HTTP: a dangling-tool history on resume.
    # Patched at the composer, because the driver's wrapper is a local closure —
    # there is no module attribute to replace, and patching one that does not
    # exist fails loudly (`AttributeError`) rather than silently testing nothing.
    def _explode(**_kwargs: Any) -> Any:
        raise ProviderRequestShapeError("history pairing invariant violated", status=400)

    from fa.inner_loop import prompt_composer

    # The driver imports the composer INSIDE the closure, so the definition
    # module is the address that matters here (unlike `handle_provider_failure`,
    # which is imported at module load).
    monkeypatch.setattr(prompt_composer, "compose_turn_request", _explode)

    outcome = coder_loop.drive_session(
        "composition", provider_chain=chain, registry=ToolRegistry(), hooks=HookRegistry(), state=state, max_turns=1
    )

    assert seen == ["ProviderRequestShapeError"], "the composition path must use the shared handler"
    assert (outcome.exit_code, outcome.stop_reason) == (2, "request_shape")
    assert [row.kind for row in log.read_all()][-2:] == ["run_stopped", "session_summary"]
    assert chain.request.call_count == 0, "a local shape failure must fail before HTTP"
