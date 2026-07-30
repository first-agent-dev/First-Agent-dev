"""S6.5 — subagent result fidelity (S5-F1) and stdout redaction (S6-F7, Q25 option (i)).

Two contracts are pinned here, and they pull in opposite directions, which is
why they live in one file:

1. **Fidelity (S5-F1).** A passing verifier currently returns the literal
   ``"PASS"`` and nothing else, so delegating work to save context loses the
   result. The envelope must carry bounded subagent output on *both* branches.

2. **Redaction (S6-F7 / Q25 option (i)).** That output is arbitrary command
   output and it reaches disk — including ``worklog.md``, which is **not**
   gitignored (``.gitignore:14`` covers ``.fa/*``, catching the artifact and
   ``worklog-detailed.md``, but not ``worklog.md``). Every writer derives from
   the single ``output`` string the runner builds, so masking happens once at
   that boundary and all writers inherit it.

Per the tests-writing skill: these drive the real ``run_stateless`` /
``from_verifier`` code paths and assert on real files on disk, not on source
text and not on a mocked seam. The redaction tests use a *known* (configured)
secret, because that is exactly the guarantee ``SecretRedactor`` makes; the
final test pins the documented limit rather than pretending it is total.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.subagent_envelope import (
    SUBAGENT_ENVELOPE_SCHEMA,
    SubagentEnvelope,
    validate_envelope,
    write_envelope_artifact,
)
from fa.inner_loop.subagent_runner import SubagentRunner
from fa.observability.redaction import SecretRedactor

# A token-shaped value long enough to clear SecretRedactor._MIN_LEN (8).
KNOWN_SECRET = "sk-live-Q25KNOWNSECRET0123456789"
UNKNOWN_SECRET = "ghp_Q25UNKNOWNSECRET0123456789"


def _redactor() -> SecretRedactor:
    return SecretRedactor(
        env={"OPENAI_API_KEY": KNOWN_SECRET},
        api_key_env_vars=["OPENAI_API_KEY"],
    )


@pytest.fixture(autouse=True)
def _isolated_session_context() -> Generator[None]:
    """Detach any ambient SessionState for the duration of each test.

    Found by running the full suite rather than this file alone: six tests
    passed in isolation and failed under `pytest -q`. ``_check_spawn_limit``
    reads the *contextvar* session, so these tests were consuming the
    per-session spawn budget (max 3) of a SessionState leaked by an earlier
    test module, and tripping ``subagent_spawn_limit`` partway through the
    file. Detaching makes each test depend only on its own fixtures — and
    keeps this file from silently spending some other test's budget.
    """
    token = set_current_session(None)
    try:
        yield
    finally:
        reset_current_session(token)


# --------------------------------------------------------------------------
# 1. Fidelity — S6-P16 / S6-P17
# --------------------------------------------------------------------------


def test_verifier_envelope_carries_stdout_on_success() -> None:
    """S6-P16 / S5-F1: a PASSING verifier must surface its output, not just "PASS"."""
    env = SubagentEnvelope.from_verifier(task_id="t-pass", exit_code=0, stdout="12 passed in 3.4s", role="verifier")
    assert env.stdout == "12 passed in 3.4s"
    # summary semantics are explicitly unchanged (existing consumers read it)
    assert env.summary == "PASS"


def test_verifier_envelope_carries_stdout_on_failure() -> None:
    """S6-P17: the FAILING branch must carry output too, and keep its summary shape."""
    env = SubagentEnvelope.from_verifier(task_id="t-fail", exit_code=1, stdout="3 failed, 9 passed", role="verifier")
    assert env.stdout == "3 failed, 9 passed"
    assert env.summary.startswith("FAIL: ")


def test_stdout_survives_the_json_round_trip() -> None:
    """The field must actually be serialised — an in-memory-only field would
    satisfy the two tests above while still losing the output on every path
    that reads the artifact."""
    env = SubagentEnvelope.from_verifier(task_id="t-json", exit_code=0, stdout="12 passed", role="verifier")
    assert json.loads(env.to_json())["stdout"] == "12 passed"


# --------------------------------------------------------------------------
# 2. Schema — C0
# --------------------------------------------------------------------------


def test_envelope_schema_declares_stdout() -> None:
    """The schema has no ``additionalProperties: false``, so an undeclared field
    would validate silently and leave the schema lying about the payload."""
    properties = SUBAGENT_ENVELOPE_SCHEMA["properties"]
    assert isinstance(properties, dict)
    assert "stdout" in properties
    assert properties["stdout"] == {"type": "string"}


def test_stdout_is_not_required_so_older_envelopes_still_validate() -> None:
    """Back-compat: an envelope written before this slice must not fail validation."""
    assert "stdout" not in SUBAGENT_ENVELOPE_SCHEMA["required"]
    legacy = {
        "task_id": "legacy",
        "type": "verifier",
        "goal": "Verify legacy",
        "exit_code": 0,
        "summary": "PASS",
        "verification": "exit_code=0",
    }
    validate_envelope(legacy)  # must not raise


# --------------------------------------------------------------------------
# 3. Redaction — S6-F7 / Q25 option (i)
# --------------------------------------------------------------------------


def test_runner_masks_known_secret_in_captured_output(tmp_path: Path) -> None:
    """Q25(i): masking happens once at the runner boundary, so the envelope the
    parent receives is already clean. Drives the real subprocess path."""
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=_redactor())
    env = runner.run_stateless(
        task_id="t-redact",
        command=f"echo 'token={KNOWN_SECRET}'",
        role="verifier",
    )
    assert KNOWN_SECRET not in env.stdout
    assert "***REDACTED***" in env.stdout


def test_persisted_envelope_does_not_contain_raw_secrets(tmp_path: Path) -> None:
    """S6-F7: the on-disk artifact is the thing that outlives the session."""
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=_redactor())
    env = runner.run_stateless(
        task_id="t-artifact",
        command=f"echo 'token={KNOWN_SECRET}'",
        role="verifier",
    )
    artifact = write_envelope_artifact(env, tmp_path)
    assert KNOWN_SECRET not in artifact.read_text(encoding="utf-8")


def test_failing_subagent_does_not_leak_secret_into_tracked_worklog(tmp_path: Path) -> None:
    """The leak found during the S6.5 preflight, and the reason Q25 was folded:

    ``worklog.md`` is written by ``append_to_worklog`` from ``summary``, and it
    is **git-tracked** — ``.gitignore:14`` (``.fa/*``) does not cover it. On the
    FAIL branch ``summary`` embeds raw stdout, so a subagent that printed a
    token wrote it into a committable file.
    """
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=_redactor())
    env = runner.run_stateless(
        task_id="t-worklog",
        command=f"echo 'token={KNOWN_SECRET}'; exit 1",
        role="verifier",
    )
    assert env.exit_code != 0, "test needs the FAIL branch to be taken"
    # run_stateless already wrote the artifact and both worklogs; this asserts
    # against everything it actually put on disk.
    leaked = [
        p
        for p in tmp_path.rglob("*")
        if p.is_file() and KNOWN_SECRET in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert leaked == [], f"secret reached {[str(p) for p in leaked]}"


def test_researcher_role_output_is_also_masked(tmp_path: Path) -> None:
    """The researcher branch puts ``stdout[:500]`` straight into ``summary``, so
    it leaks on SUCCESS too — a different path from the verifier FAIL branch."""
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=_redactor())
    env = runner.run_stateless(
        task_id="t-research",
        command=f"echo 'token={KNOWN_SECRET}'",
        role="researcher",
    )
    assert KNOWN_SECRET not in env.summary
    assert KNOWN_SECRET not in env.to_json()


def test_redaction_is_optional_so_unconfigured_callers_still_work(tmp_path: Path) -> None:
    """No redactor is a supported configuration (tests, embedded use). It must
    degrade to "no masking", never to a crash."""
    runner = SubagentRunner(session_root=tmp_path, timeout=30)
    env = runner.run_stateless(task_id="t-noredact", command="echo hello", role="verifier")
    assert "hello" in env.stdout


def test_model_facing_channel_is_masked_even_with_no_runner_redactor(tmp_path: Path) -> None:
    """C3, skill §11: *"Secret NOT in model-facing messages"* is the stated
    minimum proof for the secret-leakage boundary, and it is a different
    channel from the on-disk artifact the tests above cover.

    ``spawn_subagent`` returns ``ToolResult.ok(result=envelope.to_json())``,
    which is projected into the LLM message stream. This pins the layering
    claimed in ``_mask``'s docstring: even when the runner has **no** redactor
    (a supported configuration), ADR-12 B2's egress chokepoint
    ``coder_loop._redact`` still masks the payload. If that chokepoint were
    removed, the S6.5 masking alone would not save the model channel for an
    unconfigured runner — so the two layers are asserted together rather than
    assumed independent.
    """
    from fa.inner_loop.coder_loop import _redact

    runner = SubagentRunner(session_root=tmp_path, timeout=30)  # deliberately unmasked
    env = runner.run_stateless(
        task_id="t-model",
        command=f"echo 'token={KNOWN_SECRET}'",
        role="verifier",
    )
    payload = env.to_json()
    assert KNOWN_SECRET in payload, "pre-check: without a runner redactor the payload carries the secret"
    assert KNOWN_SECRET not in _redact(_redactor(), payload)


def test_redaction_failure_withholds_output_instead_of_passing_it_through(tmp_path: Path) -> None:
    """C3: the fail-CLOSED branch of ``_mask``.

    Added 2026-07-29 after a mutation sweep: replacing the withhold return with
    ``return text`` survived the whole 2193-test suite. The branch was written
    deliberately fail-closed — if masking raised we cannot prove the text is
    clean — but nothing proved it, so a later "simplification" to pass the text
    through would have been invisible and would have leaked.

    A redactor whose ``redact`` raises is the realistic trigger (a corrupted
    pattern, an encoding backstop blowing up on binary-ish output).
    """

    class _ExplodingRedactor:
        def redact(self, text: str) -> str:
            raise RuntimeError("redactor exploded")

    runner = SubagentRunner(session_root=tmp_path, timeout=30)
    runner.redactor = _ExplodingRedactor()  # type: ignore[assignment]

    env = runner.run_stateless(
        task_id="t-explode",
        command=f"echo 'token={KNOWN_SECRET}'",
        role="verifier",
    )

    assert KNOWN_SECRET not in env.stdout, "masking failed and the raw output was passed through"
    assert KNOWN_SECRET not in env.to_json()
    assert "withheld" in env.stdout


def test_researcher_envelope_carries_its_summary_as_stdout() -> None:
    """C0: ``from_researcher`` is the envelope's other factory.

    Added 2026-07-29 after a mutation sweep: blanking ``stdout=summary`` in
    ``from_researcher`` survived the whole suite. The factory has **no
    production caller today** (grep: only its own definition), so this is a
    unit-level pin on a currently-dormant constructor rather than a live-path
    claim — recorded as such so the next reader does not mistake it for
    behavioural proof.
    """
    env = SubagentEnvelope.from_researcher(
        task_id="r1",
        query="what is the retry policy",
        urls=["https://example.invalid/a"],
        snippets=["snippet"],
        summary="the retry policy is three attempts",
    )
    assert env.stdout == "the retry policy is three attempts"
    assert json.loads(env.to_json())["stdout"] == "the retry policy is three attempts"


def test_documented_limit_unknown_secrets_are_not_masked(tmp_path: Path) -> None:
    """Q25 research finding 2 (GitLab's posture): ship the mask, and state its
    ceiling honestly. This test is the executable form of the docstring's
    caveat — an exact-value redactor cannot mask a credential the command
    itself materialises. It is a *characterisation* test: if a future change
    makes this masking total, this test should be rewritten, not deleted.
    """
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=_redactor())
    env = runner.run_stateless(
        task_id="t-unknown",
        command=f"echo 'token={UNKNOWN_SECRET}'",
        role="verifier",
    )
    assert UNKNOWN_SECRET in env.stdout


def test_min_len_floor_prevents_buildkite_style_over_redaction() -> None:
    """Q25 research finding 4: Buildkite shredded ordinary logs by masking very
    short values (``1``, ``true``). Pin the floor so a future edit cannot
    reintroduce that failure mode."""
    assert SecretRedactor._MIN_LEN >= 8
    with pytest.raises(Exception):  # noqa: B017 - SecretRedactorError, kept broad on purpose
        SecretRedactor(env={"TINY": "1"}, api_key_env_vars=["TINY"])


# --------------------------------------------------------------------------
# 4. Composition root — the wiring itself
# --------------------------------------------------------------------------


def test_spawn_subagent_wires_the_session_redactor_into_the_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KC-4 gap: every other masking test constructs ``SubagentRunner``
    directly, so all of them keep passing even if the composition root at
    ``spawn_subagent.py`` passes ``redactor=None``. That is the whole leak,
    reintroduced, with a green suite.

    This pins the wiring itself: build a real SessionState whose EventLog holds
    a redactor, run the real spawn path, and assert the runner it constructed
    received that exact object.
    """
    from fa.feature_flags import FeatureFlags
    from tests.fixtures.session_wiring import make_session_state

    redactor = _redactor()
    session = make_session_state(
        tmp_path,
        run_id="s65-wiring",
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
        redactor=redactor,
    )
    assert session.log is not None
    # The accessor must expose what was injected, or the wiring below is moot.
    assert session.log.redactor is redactor

    seen: dict[str, object] = {}
    real_init = SubagentRunner.__init__

    def spy_init(self: SubagentRunner, *args: object, **kwargs: object) -> None:
        seen["redactor"] = kwargs.get("redactor")
        real_init(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(SubagentRunner, "__init__", spy_init)

    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

    # Drive the real registered tool, not a private helper.
    tool = build_spawn_subagent_tool(tmp_path)
    token = set_current_session(session)
    try:
        tool.handler({"task_id": "wire", "command": "echo hi", "role": "verifier"})
    except Exception:  # noqa: BLE001 - the spawn may fail; the wiring is the assertion
        pass
    finally:
        reset_current_session(token)

    assert "redactor" in seen, "spawn_subagent never constructed a SubagentRunner"
    assert seen["redactor"] is redactor, (
        "spawn_subagent did not pass the session's redactor to the runner — subagent output would be persisted unmasked"
    )


# --------------------------------------------------------------------------
# 5. Bound — C3
# --------------------------------------------------------------------------


def test_oversized_stdout_is_truncated_with_marker(tmp_path: Path) -> None:
    """Q25: reuse the runner's existing 8000-char cap; truncation must be
    explicit so a reader can tell output was cut, never silent."""
    runner = SubagentRunner(session_root=tmp_path, timeout=30, redactor=None)
    env = runner.run_stateless(
        task_id="t-big",
        command="python3 -c \"print('x' * 20000)\"",
        role="verifier",
    )
    assert len(env.stdout) < 20000
    assert "truncated" in env.stdout
