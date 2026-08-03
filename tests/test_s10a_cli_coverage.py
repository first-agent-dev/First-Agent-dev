"""S10a — CLI coverage to 80% (prerequisite for the S10b decomposition).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10a-cli-coverage.md``
(v1-reviewed, v3).

**Why this module exists.** ``cli.py`` was at 59% with six commands effectively
dark (0-11%). Refactoring any of them would have been *unfalsifiable*: no
parity test could fail. S10a buys the right to refactor in S10b.

**Test-class labelling** (tests-writing skill §10):

* **C2** — root is a shipped ``_cmd_*`` function; oracle is an exit code, a
  structured stderr message, a filesystem effect, or the arguments a delegate
  receives. These carry the producer kill-checks.
* **C0p** — pure helpers over a table of inputs, always **paired** with the C2
  tests that exercise the same code through the command root.

**Oracle discipline.** Every test asserts a *specific* exit code, never
``!= 0`` — the codebase distinguishes 0 (ok), 1 (findings/not-found) and 2
(usage/config error), and a loose assertion cannot tell "rejected" from
"found nothing". Where a message is asserted it is the structured prefix, not
prose.

**Forward-compatibility with S10b (plan RK4).** These tests must not freeze the
shape S10b intends to change. They therefore assert **behaviour at the command
boundary** — exit code, streams, artifacts, delegate arguments — and never that
a particular private helper was called or in what order.

**Namespace contracts** were AST-extracted from each command during plan review
rather than copied from an existing test; a missing attribute raises
``AttributeError`` at an arbitrary depth instead of producing the exit code
under test.
"""

from __future__ import annotations

import argparse
import functools
import io
import json
from pathlib import Path
from typing import Any, override

import pytest

from fa.cli import (
    _cmd_authoring_check,
    _cmd_chunk,
    _cmd_egress_proxy,
    _cmd_probe,
    _cmd_routing_check,
    _cmd_run,
    _cmd_selfcheck,
    _cmd_stats,
    _resolve_task,
)
from fa.providers.base import TransportResponse
from tests.test_cli import _FAKE_MODELS_YAML, _TEST_SECRETS, _ScriptedTransport, _stop_body
from tests.test_s7_cli_run_paths import _run_args


def _stats_args_local(**overrides: Any) -> argparse.Namespace:
    """``_cmd_stats`` reads 7 attributes; see the S10a plan's Namespace table."""
    base: dict[str, Any] = {
        "dead_zones": False,
        "global_history": False,
        "output": "json",
        "run_id": None,
        "session_id": None,
        "since": None,
        "workspace": Path(),
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# S10a.1 — shared fixtures
# ---------------------------------------------------------------------------

_VALID_MODELS_YAML = """\
coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: TEST_FA_RUN_KEY
"""


def _cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ``$HOME`` so no test can touch the developer's real ``~/.fa``.

    ``fa.paths.fa_state_root`` resolves at call time (V10 / S8.8), so setting
    the environment here is honoured by production code rather than silently
    ignored.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _args_for_chunk(**overrides: Any) -> argparse.Namespace:
    """``_cmd_chunk`` reads exactly: ``output``, ``path``."""
    base: dict[str, Any] = {"output": "text", "path": Path()}
    base.update(overrides)
    return argparse.Namespace(**base)


def _args_for_routing_check(**overrides: Any) -> argparse.Namespace:
    """``_cmd_routing_check`` reads exactly: ``config``."""
    base: dict[str, Any] = {"config": Path()}
    base.update(overrides)
    return argparse.Namespace(**base)


def _args_for_authoring_check(**overrides: Any) -> argparse.Namespace:
    """``_cmd_authoring_check`` reads exactly: ``manifest``, ``output``, ``workspace``."""
    base: dict[str, Any] = {"manifest": None, "output": "text", "workspace": Path()}
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# S10a.2 / GAP1 / T1 — the three pure commands (no seam needed)
# ---------------------------------------------------------------------------


def test_s10a_chunk_missing_path_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a nonexistent path is exit 2, not a crash.

    Oracle: exit code + structured stderr prefix.
    Kill-check target: delete the ``if not path.exists()`` guard in
    ``_cmd_chunk`` — the command would raise instead of returning 2.
    """
    assert _cmd_chunk(_args_for_chunk(path=tmp_path / "nope.py")) == 2
    assert "fa chunk: path not found" in capsys.readouterr().err


def test_s10a_chunk_directory_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a directory is rejected distinctly from a missing path.

    Two guards, two messages: a test that only covered the missing-path case
    would leave this branch dark while the coverage number looked fine.

    Kill-check target: delete the ``if not path.is_file()`` guard.
    """
    assert _cmd_chunk(_args_for_chunk(path=tmp_path)) == 2
    assert "fa chunk: not a file" in capsys.readouterr().err


def test_s10a_chunk_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): the default renderer emits a chunk listing on stdout.

    Oracle: exit 0 + the header line the command promises. Chunk *contents*
    are ``default_chunker``'s contract, not the CLI's, so they are not
    asserted here.
    """
    target = tmp_path / "sample.py"
    target.write_text("def a():\n    return 1\n\n\ndef b():\n    return 2\n", encoding="utf-8")

    assert _cmd_chunk(_args_for_chunk(path=target)) == 0

    out = capsys.readouterr().out
    assert str(target) in out
    assert "chunk(s); chunker" in out


def test_s10a_chunk_json_output_is_parseable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): ``--output json`` emits machine-readable stdout.

    Oracle: the payload parses and carries its schema keys. Asserting
    ``json.loads`` succeeds is the point — this is the branch a downstream
    consumer depends on.

    Kill-check target: change the ``args.output == "json"`` branch to fall
    through to the text renderer — ``json.loads`` then fails.
    """
    target = tmp_path / "sample.py"
    target.write_text("def a():\n    return 1\n", encoding="utf-8")

    assert _cmd_chunk(_args_for_chunk(path=target, output="json")) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(target)
    assert payload["chunker_version"]
    assert isinstance(payload["chunks"], list)


def test_s10c_routing_check_missing_config_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10c.1 / GAP1 / CT1): a **nonexistent** config is exit 2 — I-40 FIXED.

    **Inverted by S10c.1.** This test previously asserted exit **0** and was
    named ``test_s10a_routing_check_missing_config_reports_no_roles``. S10a
    wrote it that way deliberately: it pinned a known defect so the eventual
    fix would be a visible diff rather than silent drift. This is that diff.

    The defect: ``load_models_config_from_path`` returns an empty ``roles``
    mapping for a missing file rather than raising, so ``_cmd_routing_check``
    took its "no roles declared" branch and reported success.
    ``scripts/fa-clean-rebuild.sh:471`` uses this exit code as a **pre-build
    deploy gate**, so a typo'd ``--config`` logged "Routing lint: OK" and
    proceeded to build having validated nothing.

    The loader's missing-file policy is unchanged — it is documented and
    correct for other callers (``config.py:323-326``, "caller decides if
    absence is fatal"). The existence check lives in the *command*, which is
    the caller that has decided absence IS fatal.

    Oracle: exit 2 + the structured message naming the path.
    Kill-check target: the ``config_path.is_file()`` guard in
    ``_cmd_routing_check``.
    """
    missing = tmp_path / "nope.yaml"
    assert _cmd_routing_check(_args_for_routing_check(config=missing)) == 2
    out = capsys.readouterr().out
    assert "config not found" in out
    assert str(missing) in out, "the message must name the path an operator typo'd"


def test_s10a_routing_check_malformed_config_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a config that *exists but is invalid* is exit 2.

    Distinct from the missing-file case above — this is the branch that
    actually raises ``ConfigurationError``, so it is the one that proves the
    ``except`` handler is wired.

    Kill-check target: remove the ``except (ConfigurationError, ...)`` handler
    — the command would propagate instead of returning 2.
    """
    config = tmp_path / "models.yaml"
    # An empty chain is a *semantic* error the loader raises ConfigurationError
    # for. Chosen deliberately over malformed YAML: unparseable YAML escapes as
    # a raw ``yaml.ParserError`` (measured), which this handler does not catch
    # — see BACKLOG I-40.
    config.write_text("coder:\n  name: m\n  family: openai\n", encoding="utf-8")

    assert _cmd_routing_check(_args_for_routing_check(config=config)) == 2
    assert "models config error" in capsys.readouterr().out


def test_s10a_routing_check_clean_config_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a conflict-free config returns 0 and says so.

    This is the positive control for the failure tests above: without it, a
    guard that rejected *every* config would still satisfy them.
    """
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")

    assert _cmd_routing_check(_args_for_routing_check(config=config)) == 0
    assert "OK (" in capsys.readouterr().out


def test_s10a_routing_check_empty_roles_is_a_warning_not_a_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.2 / GAP1): an empty config warns and returns **0**.

    Failure-observable law (attached skill): the "nothing to check" path must
    emit a structured signal rather than passing silently. It is deliberately
    **not** an error — pinning that distinction is the point, because 0 vs 2
    here is a deploy-gate decision.
    """
    config = tmp_path / "models.yaml"
    config.write_text("{}\n", encoding="utf-8")

    assert _cmd_routing_check(_args_for_routing_check(config=config)) == 0
    assert "no roles declared" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# S10a.3 / GAP2 / T2 — _cmd_egress_proxy, pre-serve surface only
# ---------------------------------------------------------------------------
#
# This command ends in a blocking ``serve(...)``. It is covered **without ever
# binding a port**: ``serve`` is imported from ``fa.egress_proxy.server`` inside
# the function body, so the attribute is resolved at call time and
# monkeypatching the *source module* intercepts it. Patching ``fa.cli.serve``
# would silently do nothing — there is no such attribute.
#
# Measured during planning: 23 statements precede ``serve()`` and 2 follow it,
# so ~93% of the function is reachable this way and the 80% floor needs no
# carve-out.


def _args_for_egress_proxy(**overrides: Any) -> argparse.Namespace:
    """``_cmd_egress_proxy`` reads exactly: ``listen``, ``models``, ``secrets``, ``token_file``."""
    base: dict[str, Any] = {
        "listen": "127.0.0.1:8080",
        "models": Path(),
        "secrets": Path(),
        "token_file": Path(),
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _proxy_fixture(tmp_path: Path) -> dict[str, Path]:
    """A complete, valid set of proxy inputs; individual tests break one."""
    models = tmp_path / "models.yaml"
    models.write_text(_VALID_MODELS_YAML, encoding="utf-8")
    secrets = tmp_path / "secrets.env"
    secrets.write_text("TEST_FA_RUN_KEY=sk-test-abcdefghij\n", encoding="utf-8")
    token = tmp_path / "token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    return {"models": models, "secrets": secrets, "token_file": token}


@pytest.fixture
def _never_serve(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the blocking ``serve`` with a recorder for EVERY proxy test.

    Applied even to tests that expect an early ``return 2``. Without it, a
    *removed* validation guard lets execution fall through to the real
    ``serve``, which binds a socket and blocks — so the test **hangs instead
    of failing**. Measured during the S10a mutation minimum: deleting the
    empty-token guard produced a 300-second timeout that the harness scored as
    "SURVIVED".

    A mutation must make a test **fail fast**, not hang; a hang is
    indistinguishable from a slow suite and gets retried away. Recording the
    calls also lets each negative test assert ``serve`` was *not* reached.
    """
    calls: list[dict[str, Any]] = []

    def _fake_serve(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("fa.egress_proxy.server.serve", _fake_serve)
    return calls


def test_s10a_egress_proxy_bad_models_config_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _never_serve: list[dict[str, Any]]
) -> None:
    """C2 (S10a.3 / GAP2): an invalid models config is exit 2, before any bind.

    Kill-check target: the ``except (ConfigurationError, OSError)`` handler.
    """
    fx = _proxy_fixture(tmp_path)
    fx["models"].write_text("coder:\n  name: m\n  family: openai\n", encoding="utf-8")

    assert _cmd_egress_proxy(_args_for_egress_proxy(**fx)) == 2
    assert "models config error" in capsys.readouterr().err
    assert not _never_serve, "rejected input must not reach serve()"


def test_s10a_egress_proxy_empty_token_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _never_serve: list[dict[str, Any]]
) -> None:
    """C2 (S10a.3 / GAP2): an empty proxy token is refused.

    This is a **security-relevant** guard, not hygiene: the token is what
    distinguishes the agent from any other process that can reach the proxy
    port (ADR-12). Starting a proxy with an empty token would accept
    unauthenticated callers.

    Kill-check target: the ``if not token`` guard.
    """
    fx = _proxy_fixture(tmp_path)
    fx["token_file"].write_text("", encoding="utf-8")

    assert _cmd_egress_proxy(_args_for_egress_proxy(**fx)) == 2
    assert "empty/missing proxy token" in capsys.readouterr().err
    assert not _never_serve, "an unauthenticated proxy must never start"


def test_s10a_egress_proxy_missing_token_file_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _never_serve: list[dict[str, Any]]
) -> None:
    """C2 (S10a.3 / GAP2): an absent token file is refused like an empty one.

    Distinct input, same guard — a missing file must not raise.
    """
    fx = _proxy_fixture(tmp_path)
    fx["token_file"] = tmp_path / "no-such-token"

    assert _cmd_egress_proxy(_args_for_egress_proxy(**fx)) == 2
    assert "empty/missing proxy token" in capsys.readouterr().err
    assert not _never_serve, "an unauthenticated proxy must never start"


@pytest.mark.parametrize("listen", ["8080", "127.0.0.1:notaport", ":8080"])
def test_s10a_egress_proxy_invalid_listen_is_usage_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    listen: str,
    _never_serve: list[dict[str, Any]],
) -> None:
    """C2 (S10a.3 / GAP2): ``--listen`` must be ``host:port`` with a numeric port.

    Three shapes: no colon, non-numeric port, and empty host. Each exercises a
    different half of ``if not host or not port_str.isdigit()``; a single case
    would leave the other operand unproven.

    Kill-check target: that guard.
    """
    fx = _proxy_fixture(tmp_path)

    assert _cmd_egress_proxy(_args_for_egress_proxy(**fx, listen=listen)) == 2
    assert "invalid --listen" in capsys.readouterr().err
    assert not _never_serve, "rejected input must not reach serve()"


def test_s10a_egress_proxy_happy_path_delegates_with_parsed_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2 (S10a.3 / GAP2): valid inputs reach ``serve`` with correctly parsed values.

    The real contract of this command is *what it hands to the server*, so the
    oracle is the delegate's keyword arguments — host and port split correctly,
    the token read from disk, the route table built. No port is bound.

    Kill-check target: remove the ``serve(...)`` call — ``captured`` stays
    empty and this fails.
    """
    fx = _proxy_fixture(tmp_path)
    captured: dict[str, Any] = {}

    def _fake_serve(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("fa.egress_proxy.server.serve", _fake_serve)

    assert _cmd_egress_proxy(_args_for_egress_proxy(**fx, listen="0.0.0.0:9443")) == 0

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9443
    assert isinstance(captured["port"], int), "port must be parsed, not passed as a string"
    assert captured["proxy_token"] == "proxy-t0ken-abcdefghij"
    assert captured["route_table"], "an empty route table would proxy nothing"


def test_s10a_routing_check_reports_findings_with_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a lint finding is exit **1**, distinct from 2.

    Exercises the branch the command exists for. The fixture is a *near-miss*
    ``base_url`` — ``/api/vl`` instead of ``/api/v1`` — which is precisely the
    lone-typo case the linter's docstring says a conflict check cannot catch,
    so this is a realistic defect rather than a synthetic one.

    The three-way exit contract (0 clean / 1 findings / 2 config error) is what
    ``scripts/fa-clean-rebuild.sh`` branches on, so each value needs its own
    test.

    Kill-check target: the ``return 1`` after the findings loop — flipping it
    to ``return 0`` makes the deploy gate pass on a real routing defect.
    """
    config = tmp_path / "models.yaml"
    config.write_text(
        "coder:\n"
        '  name: "m"\n'
        '  family: "openai"\n'
        "  chain:\n"
        "    - provider: openrouter\n"
        '      model: "test/model"\n'
        '      base_url: "https://openrouter.ai/api/vl"\n'
        "      api_key_env: K\n",
        encoding="utf-8",
    )

    assert _cmd_routing_check(_args_for_routing_check(config=config)) == 1

    out = capsys.readouterr().out
    assert "ISSUES FOUND" in out
    assert "near_miss_base_url" in out


def test_s10a_authoring_check_runs_on_a_real_workspace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C2 (S10a.2 / GAP1): the happy path runs the rule pack and returns its verdict.

    Uses **this repository** as the workspace rather than a synthetic tree:
    the command's whole purpose is auditing a First-Agent checkout, and a
    fabricated ``knowledge/llms.txt`` would exercise the guard but not the
    rules behind it.

    Oracle: the command's exit code equals the report's own ``exit_code``, and
    something was rendered. The *content* of the report is
    ``fa.authoring_rules``' contract, not the CLI's — asserting it here would
    couple this test to rule internals and make S10b's refactor harder
    (plan RK4).

    Kill-check target: delete the ``print(rendered)`` — stdout goes empty.
    """
    workspace = Path(__file__).resolve().parent.parent
    assert (workspace / "knowledge" / "llms.txt").is_file(), "test assumes it runs inside the repo"

    exit_code = _cmd_authoring_check(_args_for_authoring_check(workspace=workspace, output="json"))

    out = capsys.readouterr().out
    assert out.strip(), "the command must render a report"
    payload = json.loads(out)
    assert "diagnostics" in payload
    # The repo is expected clean (`just check` runs this), so 0 is the value;
    # asserting equality with the payload keeps the test honest if that changes.
    assert exit_code == 0
    assert payload["diagnostics"] == []


def test_s10a_authoring_check_rejects_non_workspace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.2 / GAP1): a directory without ``knowledge/llms.txt`` is exit 2.

    This guard exists per AGENTS.md so the checker never walks up into a
    parent checkout and audits the wrong tree — a correctness boundary, not a
    convenience.

    Kill-check target: delete the ``knowledge/llms.txt`` existence guard.
    """
    assert _cmd_authoring_check(_args_for_authoring_check(workspace=tmp_path)) == 2
    assert "not a First-Agent workspace" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# S10a.4 / GAP3 / T3 — _cmd_probe: the seam, and the default path it must keep
# ---------------------------------------------------------------------------


def _args_for_probe(**overrides: Any) -> argparse.Namespace:
    """``_cmd_probe`` reads exactly: ``all_roles``, ``config``, ``role``, ``timeout``."""
    base: dict[str, Any] = {"all_roles": False, "config": Path(), "role": "coder", "timeout": 5}
    base.update(overrides)
    return argparse.Namespace(**base)


class _OkTransport:
    """Minimal 200 responder — the shape ``UrllibTransport`` returns on success."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def post(
        self,
        url: str,
        *,
        headers: Any,
        json_body: Any,
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del headers, timeout_seconds, transport_retries
        self.calls.append(url)
        return TransportResponse(
            status=200,
            body={
                "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            retry_after_seconds=None,
        )


class _FailingTransport:
    """Persistent 500 — what an upstream outage looks like to the chain."""

    def post(
        self,
        url: str,
        *,
        headers: Any,
        json_body: Any,
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, json_body, timeout_seconds, transport_retries
        return TransportResponse(status=500, body={"error": "boom"}, retry_after_seconds=None)


def test_s10a_probe_uses_the_default_transport_when_no_seam_is_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / CT1): the **no-seam** path still runs — the seam is not a test-only hook.

    This is the test that answers the standard objection to optional-parameter
    DI: that a suite quietly exercises the fake and never the real default. It
    calls ``_cmd_probe(args)`` with **no** ``transport`` and **no** ``secrets``
    and asserts the command still reaches configuration handling.

    Uses a config with no roles so the default path terminates *before* any
    network call — the point is that ``effective_transport``/
    ``effective_secrets`` resolve without a caller, not that a request is made.

    Oracle: exit **2** + the structured ``no roles found`` message. (Verified
    during plan review: a nonexistent config yields "no roles", **not**
    "configuration error" — the plan's original assertion string was wrong.)
    Kill-check target: change the seam defaults from ``None`` to a stub — the
    default branch stops being exercised and this test no longer proves it.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "empty.yaml"
    config.write_text("{}\n", encoding="utf-8")

    assert _cmd_probe(_args_for_probe(config=config)) == 2
    assert "no roles found" in capsys.readouterr().err


def test_s10a_probe_default_transport_is_actually_constructed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / CT1): the ``None`` default really builds a ``UrllibTransport``.

    **This test exists because the previous one was not enough.** The kill-check
    for CT1 — replace ``transport if transport is not None else UrllibTransport()``
    with a bare ``transport`` — **survived**: the no-seam test above uses an
    empty config and returns at the "no roles" guard *before* the default is
    ever resolved. It proved the seam is optional, not that the default works.

    Here the config is valid, so execution reaches the resolution line with
    ``transport=None``. ``UrllibTransport`` is monkeypatched at its source
    module to a recorder, so no socket is opened and the assertion is that the
    production default was *constructed and used*.

    Oracle: the default class was instantiated, and the probe issued a request
    through it.
    Kill-check target: the ``else UrllibTransport()`` half of the seam
    resolution — with it removed, ``chain.request`` is handed ``None`` and this
    fails.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")
    # ``secrets=None`` makes the command call the real ``_load_secret_store``,
    # which is strictly file-based (ADR-12: keys are never read from the
    # environment). ``FA_SECRETS_FILE`` is its documented override, so this
    # exercises the production secrets default too, not just the transport one.
    secrets_file = tmp_path / "fa.env"
    secrets_file.write_text("TEST_FA_RUN_KEY=sk-test-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_SECRETS_FILE", str(secrets_file))

    built = _OkTransport()
    constructed: list[bool] = []

    def _fake_ctor() -> _OkTransport:
        constructed.append(True)
        return built

    monkeypatch.setattr("fa.cli.UrllibTransport", _fake_ctor)

    # No transport= and no secrets=: both defaults must resolve on their own.
    assert _cmd_probe(_args_for_probe(config=config)) == 0

    assert constructed, "the None default did not construct the production transport"
    assert built.calls, "the constructed default was never used to issue a request"
    assert "fa probe: OK" in capsys.readouterr().out


def test_s10a_probe_bad_config_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / GAP3): a semantically invalid config is exit 2.

    Kill-check target: the ``except (ConfigurationError, ...)`` handler.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text("coder:\n  name: m\n  family: openai\n", encoding="utf-8")

    assert _cmd_probe(_args_for_probe(config=config)) == 2
    assert "configuration error" in capsys.readouterr().err


def test_s10a_probe_unknown_role_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / GAP3): an unknown ``--role`` is exit **1**, not 2.

    1 (probe failed) and 2 (cannot start) are different operator signals, so
    the distinction is asserted rather than folded into "non-zero".

    Kill-check target: the ``if chain_config is None`` branch.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")

    code = _cmd_probe(
        _args_for_probe(config=config, role="nosuchrole"),
        transport=_OkTransport(),
        secrets={"TEST_FA_RUN_KEY": "sk-test-abcdefghij"},
    )

    assert code == 1
    assert "not found in" in capsys.readouterr().out


def test_s10a_probe_success_reports_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / GAP3): a reachable provider yields exit 0 and an OK line.

    Also the liveness control for the failure tests: without it, a command that
    rejected everything would satisfy them all.

    Kill-check target: the ``chain.request(request)`` call — no response, no
    OK line.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")
    transport = _OkTransport()

    code = _cmd_probe(
        _args_for_probe(config=config),
        transport=transport,
        secrets={"TEST_FA_RUN_KEY": "sk-test-abcdefghij"},
    )

    assert code == 0
    assert "fa probe: OK" in capsys.readouterr().out
    assert transport.calls, "the probe must actually issue a request"


def test_s10a_probe_chain_exhaustion_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / GAP3): every chain entry failing is exit 1 with a FAIL line.

    Exercises the ``ProviderChainExhaustedError`` handler — the branch that
    matters most operationally, since it is what a real outage produces.

    Kill-check target: that ``except`` clause.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")

    code = _cmd_probe(
        _args_for_probe(config=config),
        transport=_FailingTransport(),
        secrets={"TEST_FA_RUN_KEY": "sk-test-abcdefghij"},
    )

    assert code == 1
    assert "fa probe: FAIL" in capsys.readouterr().out


def test_s10a_probe_all_roles_probes_every_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.4 / GAP3): ``--all-roles`` iterates the whole config.

    Kill-check target: the ``if args.all_roles`` branch — with it removed only
    one role is probed and the second role's banner disappears.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(
        _VALID_MODELS_YAML + "eval:\n"
        '  name: "test-model"\n'
        '  family: "anthropic"\n'
        "  chain:\n"
        "    - provider: openrouter\n"
        '      model: "test/model"\n'
        '      base_url: "https://openrouter.ai/api/v1"\n'
        "      api_key_env: TEST_FA_RUN_KEY\n",
        encoding="utf-8",
    )

    code = _cmd_probe(
        _args_for_probe(config=config, all_roles=True),
        transport=_OkTransport(),
        secrets={"TEST_FA_RUN_KEY": "sk-test-abcdefghij"},
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "role=coder" in out
    assert "role=eval" in out


# ---------------------------------------------------------------------------
# S10a.5 / GAP4 / T4 — _cmd_selfcheck, best-effort floor 60%
# ---------------------------------------------------------------------------
#
# Floor is 60%, not 80% (operator decision, plan Q45): the remaining lines are
# diagnostic banner formatting whose value per test is low. The branches that
# decide an EXIT CODE are all covered here.
#
# Both network calls go through the single module-level ``_selfcheck_http_get``,
# so one monkeypatch intercepts them; no seam parameter is needed and none was
# added (smallest change that works).


def _args_for_selfcheck(**overrides: Any) -> argparse.Namespace:
    """``_cmd_selfcheck`` reads exactly: ``config``, ``role``."""
    base: dict[str, Any] = {"config": Path(), "role": "coder"}
    base.update(overrides)
    return argparse.Namespace(**base)


def test_s10a_selfcheck_without_proxy_url_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): no ``FA_EGRESS_PROXY_URL`` is exit 2.

    Kill-check target: the ``if not proxy_url`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 2
    assert "not set" in capsys.readouterr().out


def test_s10a_selfcheck_rejects_malformed_proxy_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a syntactically invalid proxy URL is exit 2.

    Distinct from "unset" — this exercises ``_validate_proxy_url``, a separate
    guard that a single unset-case test would leave dark.

    Kill-check target: the ``if proxy_url_error`` branch.
    """
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "not-a-url")

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 2
    assert "invalid FA_EGRESS_PROXY_URL" in capsys.readouterr().out


def test_s10a_selfcheck_without_token_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a reachable URL but no proxy token is exit 2.

    Security-relevant ordering: the command refuses to *send* a token-bearing
    request when it has no token, rather than calling the proxy unauthenticated
    and reporting a confusing 401.

    Kill-check target: the ``if not proxy_token`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9999/")
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    monkeypatch.setattr("fa.cli._resolve_proxy_token", lambda: "")

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 2
    assert "proxy token is missing" in capsys.readouterr().out


def test_s10a_selfcheck_unreachable_proxy_is_runtime_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a proxy that cannot be reached is exit **1**, not 2.

    The 1/2 split is the operator signal that matters here: 2 means "you
    configured this wrong", 1 means "your configuration is fine but the proxy
    is down". Conflating them would send an on-call engineer to the wrong file.

    Kill-check target: the ``except _SelfcheckNetworkError`` around the
    ``/healthz`` probe. (Written first with ``OSError`` and it failed: the
    command catches a *domain-specific* wrapper, not the raw socket error —
    a fake that raises the wrong type would have proved nothing.)
    """
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9999/")
    monkeypatch.setattr("fa.cli._resolve_proxy_token", lambda: "t0ken")

    from fa.cli import _SelfcheckNetworkError

    def _boom(url: str, headers: Any = None) -> tuple[int, str]:
        raise _SelfcheckNetworkError("connection refused")

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _boom)

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 1
    assert "proxy" in capsys.readouterr().out.lower()


def test_s10a_selfcheck_non_200_health_is_runtime_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a proxy answering non-200 on ``/healthz`` is exit 1.

    Reachable-but-unhealthy is a third state, distinct from unreachable, and it
    has its own branch.

    Kill-check target: the ``if health_status != 200`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9999/")
    monkeypatch.setattr("fa.cli._resolve_proxy_token", lambda: "t0ken")
    monkeypatch.setattr("fa.cli._selfcheck_http_get", lambda url, headers=None: (503, "unhealthy"))

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 1
    # Assert the *healthz-specific* wording, not merely "503" or exit 1: with
    # this guard deleted the run still exits 1 further down (the /routes stage
    # rejects the same stub), so an exit-code-only oracle SURVIVED the
    # mutation. Measured, then fixed.
    assert "/healthz returned HTTP 503" in capsys.readouterr().out


def _selfcheck_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration valid enough to reach the ``/routes`` stage."""
    _cli_home(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9999/")
    monkeypatch.setattr("fa.cli._resolve_proxy_token", lambda: "t0ken")


def _staged_http(*responses: tuple[int, bytes]) -> Any:
    """Return a ``_selfcheck_http_get`` stub that answers calls in order.

    ``/healthz`` is called first, then ``/routes`` — staging by position keeps
    the tests readable without asserting on URL strings, which would couple
    them to endpoint spelling that S10b may reformat.
    """
    queue = list(responses)

    def _fake(url: str, headers: Any = None) -> tuple[int, bytes]:
        return queue.pop(0) if queue else (200, b"{}")

    return _fake


def test_s10a_selfcheck_routes_403_is_token_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a 403 on ``/routes`` is reported as a token mismatch.

    A dedicated branch, separate from the generic non-200 case, because the
    remedy differs: 403 means the agent's token disagrees with the proxy's, and
    the message says exactly which files to compare.

    Kill-check target: the ``if routes_status == 403`` branch — folding it into
    the generic handler loses the actionable hint.
    """
    _selfcheck_env(tmp_path, monkeypatch)
    monkeypatch.setattr("fa.cli._selfcheck_http_get", _staged_http((200, b"ok"), (403, b"denied")))

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 1
    # The token-mismatch hint is unique to this branch; the generic non-200
    # handler also exits 1 and also prints "403", so asserting either alone
    # let the mutation survive. Measured, then fixed.
    out = capsys.readouterr().out
    assert "rejected the fa→proxy token" in out
    assert "FA_PROXY_TOKEN_FILE" in out


def test_s10a_selfcheck_routes_non_200_is_runtime_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): any other non-200 on ``/routes`` is exit 1.

    Kill-check target: the ``if routes_status != 200`` guard.
    """
    _selfcheck_env(tmp_path, monkeypatch)
    monkeypatch.setattr("fa.cli._selfcheck_http_get", _staged_http((200, b"ok"), (500, b"boom")))

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 1
    assert "500" in capsys.readouterr().out


def test_s10a_selfcheck_malformed_routes_json_is_runtime_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a 200 carrying non-JSON is caught, not raised.

    Fail-closed: a proxy answering 200 with garbage must produce a diagnostic,
    never a traceback, because this command is what an operator runs *when
    something is already wrong*.

    Kill-check target: the ``except (UnicodeDecodeError, json.JSONDecodeError)``
    handler.
    """
    _selfcheck_env(tmp_path, monkeypatch)
    monkeypatch.setattr("fa.cli._selfcheck_http_get", _staged_http((200, b"ok"), (200, b"not json")))

    assert _cmd_selfcheck(_args_for_selfcheck(config=tmp_path / "models.yaml")) == 1
    assert "non-JSON" in capsys.readouterr().out


def test_s10a_selfcheck_bad_models_config_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.5 / GAP4): a healthy proxy but broken local config is exit **2**.

    Proves the command distinguishes *your config is wrong* (2) from *the proxy
    is wrong* (1) even after the proxy has answered successfully — the exit
    code tracks the actual fault, not how far the command got.

    Kill-check target: the ``except (ConfigurationError, ...)`` handler after
    the routes stage.
    """
    _selfcheck_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "fa.cli._selfcheck_http_get",
        # The payload contract is a JSON *list* of {name, has_key} objects —
        # verified against _selfcheck_parse_routes_payload rather than guessed;
        # an object here is rejected earlier and would test the wrong branch.
        _staged_http((200, b"ok"), (200, b'[{"name": "openrouter", "has_key": true}]')),
    )
    config = tmp_path / "models.yaml"
    config.write_text("coder:\n  name: m\n  family: openai\n", encoding="utf-8")

    assert _cmd_selfcheck(_args_for_selfcheck(config=config)) == 2
    assert "models config error" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# S10a.6 / GAP6+GAP7 / T5-T7 — the runtime-critical functions
# ---------------------------------------------------------------------------
#
# Ordered most-operationally-important first (operator: "focus on important
# runtime functions"). `_cmd_run` is also S10b's decomposition target, so its
# error branches must be pinned before that refactor can be falsifiable.


def test_s10a_run_rejects_missing_task(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.6 / GAP6): no task at all is exit 2 with guidance.

    Kill-check target: the ``if resolved is None`` guard in ``_cmd_run``.
    """
    args = _run_args(tmp_path, tmp_path / "models.yaml", "s10a-notask")
    args.task = None
    args.task_pos = None

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "provide a task" in capsys.readouterr().err


def test_s10a_run_rejects_blank_task(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.6 / GAP6): a whitespace-only task is exit 2.

    Separate branch from "no task": a user who typed ``--task "  "`` gets a
    different, more specific message.

    Kill-check target: the ``if not str(args.task).strip()`` guard.
    """
    args = _run_args(tmp_path, tmp_path / "models.yaml", "s10a-blank")
    args.task = "   "

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "task must be non-empty" in capsys.readouterr().err


def test_s10a_run_rejects_non_positive_max_turns(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.6 / GAP6): ``--max-turns 0`` is refused before any provider call.

    A zero-turn run would burn session setup and produce nothing, so the guard
    is a real budget protection rather than input pedantry.

    Kill-check target: the ``if args.max_turns < 1`` guard.
    """
    args = _run_args(tmp_path, tmp_path / "models.yaml", "s10a-turns")
    args.max_turns = 0

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "--max-turns must be a positive integer" in capsys.readouterr().err


def test_s10a_run_rejects_invalid_run_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10a.6 / GAP6): a run id outside the charset is refused.

    ``run_id`` becomes a **directory name** under ``~/.fa/session-log/``, so
    this guard is path-traversal defence, not cosmetics.

    Kill-check target: the ``if args.run_id and not _valid_run_id(...)`` guard.
    """
    args = _run_args(tmp_path, tmp_path / "models.yaml", "../escape")

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "--run-id must match" in capsys.readouterr().err


def test_s10a_run_unknown_role_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): a role absent from models.yaml is exit 2 and lists known roles.

    Kill-check target: the ``if chain_config is None`` branch.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_VALID_MODELS_YAML, encoding="utf-8")
    args = _run_args(tmp_path, config, "s10a-role")
    args.role = "nosuchrole"

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "not found in" in capsys.readouterr().err


def test_s10a_run_proxy_mode_rewrites_the_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10a.6 / GAP6, matrix M3): proxy mode drives the rewrite branch.

    This branch (``_proxy_rewrite_chain``) is dark today and is one of S10b's
    four parity cells, so it must be pinned before the decomposition. Verified
    reachable during plan review: ``FA_EGRESS_PROXY_URL`` plus
    ``FA_PROXY_TOKEN_FILE`` are both plain env inputs — no live proxy needed.

    Oracle: exit 0 through the full session, proving the rewritten chain is
    still usable rather than merely that the branch was entered.
    Kill-check target: the ``if proxy_mode:`` rewrite block.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))

    args = _run_args(tmp_path, config, "s10a-proxy")

    assert _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0


def test_s10a_stats_rejects_invalid_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP7): ``fa stats --run-id`` validates its charset.

    Same path-traversal reasoning as ``fa run``: the value selects a directory.

    Kill-check target: the ``invalid_run_id`` raise in
    ``_discover_stats_sources``.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args_local(run_id="../escape", workspace=tmp_path)) == 2
    assert "invalid_run_id" in capsys.readouterr().err


def test_s10a_stats_rejects_invalid_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP7): ``--session-id`` is validated before any filesystem read.

    Kill-check target: the ``invalid_session_id`` raise.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args_local(session_id="../escape", workspace=tmp_path)) == 2
    assert "invalid_session_id" in capsys.readouterr().err


def test_s10a_stats_unknown_session_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP7): a well-formed but absent session id is a coded error.

    Distinct from a malformed id — "you typed it wrong" versus "it is gone"
    are different operator situations.

    Kill-check target: the ``unknown_session`` raise.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args_local(session_id="session-doesnotexist", workspace=tmp_path)) == 2
    assert "unknown_session" in capsys.readouterr().err


def _seed_global_history(home: Path, rows: int = 2) -> None:
    """Write a real ``global_history.db`` under the isolated ``$HOME``.

    Uses the production ``GlobalHistoryStore`` rather than hand-rolled SQL, so
    the fixture cannot drift from the schema the reader expects.
    """
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    store = GlobalHistoryStore(db_path=default_global_history_path())
    for i in range(rows):
        store.export_run(
            {
                "run_id": f"gh-run-{i}",
                "created_at": "2026-07-31T00:00:00Z",
                "updated_at": f"2026-07-31T00:00:0{i}Z",
                "role": "coder",
                "model": "test-model",
                "family": "openai",
                "exit_code": 0,
                "stop_reason": "stopped_by_llm",
                "turns": 1,
            }
        )
    assert (home / ".fa" / "global_history.db").is_file()


def test_s10a_stats_global_history_empty_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): ``--global-history`` with no rows is exit 1, not a crash.

    Failure-observable: "there is no history yet" must be a structured message,
    since an operator running this after a fresh install needs to tell it apart
    from a broken database.

    Kill-check target: the ``if not rows`` branch.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args_local(global_history=True, workspace=tmp_path)) == 1
    assert "no global history found" in capsys.readouterr().err


def test_s10a_stats_global_history_json_lists_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): ``--global-history --output json`` emits the rows on stdout.

    Machine-readable output goes to **stdout** while the console renderer uses
    stderr — the S8.4 stream contract. Asserting ``json.loads`` succeeds is
    what proves the split is intact.

    Kill-check target: the ``store.read_all()`` call — no rows, no payload.
    """
    home = _cli_home(tmp_path, monkeypatch)
    _seed_global_history(home)

    assert _cmd_stats(_stats_args_local(global_history=True, workspace=tmp_path)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert {r["run_id"] for r in payload} == {"gh-run-0", "gh-run-1"}


def test_s10a_stats_global_history_run_id_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): ``--run-id`` narrows the projection to one row.

    Kill-check target: the ``rows = [r for r in rows if ...]`` filter — without
    it both rows come back and this fails.
    """
    home = _cli_home(tmp_path, monkeypatch)
    _seed_global_history(home)

    assert _cmd_stats(_stats_args_local(global_history=True, run_id="gh-run-1", workspace=tmp_path)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [r["run_id"] for r in payload] == ["gh-run-1"]


def test_s10a_stats_global_history_unknown_run_id_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): filtering to a run that is not there is exit 1.

    Kill-check target: the ``if not rows`` check inside the run-id filter.
    """
    home = _cli_home(tmp_path, monkeypatch)
    _seed_global_history(home)

    assert _cmd_stats(_stats_args_local(global_history=True, run_id="gh-nope", workspace=tmp_path)) == 1
    assert "not found in global history" in capsys.readouterr().err


def test_s10a_stats_global_history_console_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): the non-JSON renderer writes to **stderr**.

    Pins the S8.4 stream contract on this branch: human output must not land on
    stdout, or ``fa stats --global-history > file`` stops being parseable.

    Kill-check target: the ``file=sys.stderr`` on the console rendering block.
    """
    home = _cli_home(tmp_path, monkeypatch)
    _seed_global_history(home)

    assert _cmd_stats(_stats_args_local(global_history=True, output="text", workspace=tmp_path)) == 0

    captured = capsys.readouterr()
    assert "Global history" in captured.err
    assert captured.out == "", "human rendering must not pollute stdout"


# --- _resolve_task: the stdin-piping branches (GAP7) ------------------------


class _PipedStdin(io.StringIO):
    """A non-TTY stdin carrying data, as a shell pipe produces.

    ``close`` is a no-op **on purpose.** ``monkeypatch`` restores the *object*
    ``sys.stdin`` pointed at, but it cannot un-close a file: when the CLI read
    this handle and closed it, every later test in the session inherited a
    closed stdin and died with ``ValueError: I/O operation on closed file``.

    Measured: this test passed alone and broke a test 40 lines further down —
    the fourth cross-test leak in this workstream. *A test that passes alone
    and fails in the suite is evidence about the suite, not a reason to relax
    the test.*
    """

    @override
    def isatty(self) -> bool:
        return False

    @override
    def close(self) -> None:
        """Deliberately inert — see the class docstring."""

    @override
    def fileno(self) -> int:  # pragma: no cover - only reached if select() runs
        raise ValueError("no real fd in tests")


def test_s10a_resolve_task_prefers_flag_over_positional() -> None:
    """C0p (S10a.6 / GAP7): ``--task`` wins over the positional argument.

    Paired with the C2 ``_cmd_run`` tests above, which drive the same helper
    through the command root (skill §10: a C0p never stands alone).
    """
    assert _resolve_task("positional", "flagged") == "flagged"
    assert _resolve_task("positional", None) == "positional"
    assert _resolve_task(None, None) is None


def test_s10a_resolve_task_handles_unreadable_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """C0p (S10a.6 / GAP7): a stdin whose ``isatty`` raises degrades to interactive.

    Under pytest ``sys.stdin`` is a ``DontReadFromInput`` object with no real
    file descriptor, so this is the *normal* path in CI rather than an exotic
    one — and it must not raise.

    Kill-check target: the ``except (AttributeError, ValueError, OSError)``
    around ``sys.stdin.isatty()``.
    """

    class _Hostile:
        def isatty(self) -> bool:
            raise ValueError("no fd")

    monkeypatch.setattr("sys.stdin", _Hostile())

    assert _resolve_task(None, "task from flag") == "task from flag"


def test_s10a_resolve_task_dash_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """C0p (S10a.6 / GAP7): an explicit ``-`` reads the task from stdin.

    Kill-check target: the ``chosen == "-"`` branch.
    """
    monkeypatch.setattr("sys.stdin", _PipedStdin("task piped in\n"))

    assert _resolve_task(None, "-") == "task piped in"


# --- _cmd_stats: the session-analytics path (GAP6) --------------------------


def test_s10a_stats_no_sessions_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): an empty state root reports "no matching sessions".

    Kill-check target: the ``if not sources`` branch.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args_local(workspace=tmp_path)) == 1
    assert "no matching sessions" in capsys.readouterr().err


def test_s10a_stats_renders_a_real_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): the happy path parses a real trace and emits JSON.

    Drives the whole chain — a genuine ``fa run`` writes the authority DB, then
    ``fa stats`` discovers, parses and renders it. That is the command's actual
    contract, and it is the positive control for every "not found" test above.

    Kill-check target: the ``parse_session_db`` call — no analytics, no output.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    run_args = _run_args(tmp_path, config, "s10a-stats-run")
    assert _cmd_run(run_args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()  # discard the run's own output

    assert _cmd_stats(_stats_args_local(run_id="s10a-stats-run", workspace=tmp_path)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "s10a-stats-run"


def test_s10a_stats_global_history_since_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): ``--since`` filters the projection by ``updated_at``.

    Complements S9's ``--since`` *validation* tests: those proved a bad value
    is rejected, this proves a good one actually filters. The seeded rows are
    stamped in 2026, so a 1-hour window excludes them all and the command
    reports an empty result rather than crashing on the date arithmetic.

    Kill-check target: the ``dt.timestamp() >= cutoff`` comparison.
    """
    home = _cli_home(tmp_path, monkeypatch)
    _seed_global_history(home)

    code = _cmd_stats(_stats_args_local(global_history=True, since="1h", workspace=tmp_path))

    # Rows are older than the window, so JSON output is an empty list.
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_s10a_stats_global_history_unparseable_timestamp_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): a row with a junk ``updated_at`` survives the filter.

    Fail-*open* here is deliberate and worth pinning: dropping rows because
    their timestamp cannot be parsed would silently shrink an operator's
    history. The code catches ``(TypeError, ValueError, AttributeError)`` and
    keeps the row.

    Kill-check target: that ``except`` branch — with it removed the command
    raises instead of degrading.
    """
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    _cli_home(tmp_path, monkeypatch)
    store = GlobalHistoryStore(db_path=default_global_history_path())
    store.export_run(
        {
            "run_id": "gh-bad-ts",
            "created_at": "not-a-date",
            "updated_at": "not-a-date",
            "role": "coder",
            "exit_code": 0,
            "stop_reason": "ok",
            "turns": 1,
        }
    )

    assert _cmd_stats(_stats_args_local(global_history=True, since="1h", workspace=tmp_path)) == 0
    assert [r["run_id"] for r in json.loads(capsys.readouterr().out)] == ["gh-bad-ts"]


def test_s10a_stats_global_history_read_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): a projection read failure is a message, never a traceback.

    ``fa stats`` is run *when something is already wrong*, so an unreadable
    history database must produce a diagnostic and exit 1.

    Kill-check target: the broad ``except Exception`` around the
    global-history block.
    """
    _cli_home(tmp_path, monkeypatch)

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("db is corrupt")

    monkeypatch.setattr("fa.inner_loop.global_history.GlobalHistoryStore", _boom)

    assert _cmd_stats(_stats_args_local(global_history=True, workspace=tmp_path)) == 1
    assert "failed to read global history" in capsys.readouterr().err


def test_s10a_stats_aggregate_across_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): with no ``--run-id`` the command aggregates every run.

    The aggregate branch is distinct from the single-run render already covered
    — it takes a different code path and emits a different payload shape
    (``sessions_detail``).

    Kill-check target: the ``aggregate_sessions(sessions)`` call.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    first = _run_args(tmp_path, config, "s10a-agg-a")
    assert _cmd_run(first, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()

    assert _cmd_stats(_stats_args_local(workspace=tmp_path)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert "sessions_detail" in payload, "the no-run-id path must render the aggregate shape"


# NOTE: no test for ``_cmd_run``'s ``except SecretRedactorError`` branch.
# Attempted with an empty secret store; the run is rejected ~40 lines earlier
# by models-config validation ("api_key_env not set or empty"), so the
# redactor branch is unreachable from the CLI without patching internals.
# Reaching it would require monkeypatching ``SecretRedactor.from_models_config``
# to raise -- a test that asserts a handler exists rather than that any real
# input reaches it. Left uncovered deliberately: an honest gap beats a test
# that proves only its own mock. ``_cmd_run`` clears its 80% floor without it.


def test_s10a_stats_console_render_and_dead_zones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): the console renderer and ``--dead-zones`` both run.

    Two branches the JSON tests never touch. ``--dead-zones`` walks the
    workspace looking for ``src/`` files no run ever opened, so it needs a real
    workspace layout rather than an empty temp dir.

    Oracle: exit 0 and nothing on stdout (S8.4 stream contract).
    Kill-check target: the ``render_session`` call and the
    ``if getattr(args, "dead_zones", False)`` branch.

    **Ordering note (BACKLOG I-41).** ``fa.stats.render_session`` binds
    ``stream=sys.stderr`` as a *default argument*, i.e. at import time, so it
    writes to whichever stderr existed when the module was first imported. A
    prior test in this module replaces ``sys.stderr``, after which this one
    fails with ``ValueError: I/O operation on closed file`` — it passes alone
    and fails in the suite. That is a real defect (third instance of the
    import-time-binding class, after V10 and S8.8) and is filed as **I-41**,
    not fixed here: S10a's DoD permits exactly one production edit and it is
    already spent on the ``_cmd_probe`` seam.

    The workaround is to assert on the *exit code and stdout* only, which is
    the contract this test actually owns; stderr content is asserted by the
    ``--global-history`` console test where the renderer is a plain ``print``.
    """
    _cli_home(tmp_path, monkeypatch)
    # I-41 workaround: rebind the renderers' import-time-captured default to a
    # live buffer for the duration of this test. Without it the call writes to
    # a stderr object captured when `fa.stats` was first imported, which pytest
    # has since closed.
    import fa.stats as _stats

    sink = io.StringIO()
    monkeypatch.setattr(_stats, "render_session", functools.partial(_stats.render_session, stream=sink))
    monkeypatch.setattr(_stats, "render_aggregate", functools.partial(_stats.render_aggregate, stream=sink))

    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "untouched.py").write_text("x = 1\n", encoding="utf-8")

    run_args = _run_args(tmp_path, config, "s10a-render")
    assert _cmd_run(run_args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()

    code = _cmd_stats(_stats_args_local(run_id="s10a-render", output="text", dead_zones=True, workspace=tmp_path))

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "", "human rendering must not pollute stdout"
    assert sink.getvalue().strip(), "the console renderer produced nothing"
    # Oracle strengthened after the mutation minimum: without this, deleting
    # the whole --dead-zones block SURVIVED, since the command still exits 0.
    assert "Dead zones" in captured.err, "--dead-zones produced no report"


def test_s10a_stats_reports_source_errors_from_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): a ``StatsSourceError`` during parsing surfaces as exit 2.

    Discovery succeeds (the manifest is well-formed) but the authority DB is
    unusable, so the error is raised from the *parse* stage — a different
    handler from the discovery-time guards already covered.

    Kill-check target: the ``except StatsSourceError`` around
    ``parse_session_db``.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    run_args = _run_args(tmp_path, config, "s10a-corrupt")
    assert _cmd_run(run_args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()

    # Truncate the session authority so `open_existing` rejects it.
    home = tmp_path / "home"
    db = next((home / ".fa" / "sessions").glob("*/session.db"))
    db.write_bytes(b"not a sqlite database")

    assert _cmd_stats(_stats_args_local(run_id="s10a-corrupt", workspace=tmp_path)) == 2
    assert "source error" in capsys.readouterr().err


def test_s10a_run_resume_reads_the_existing_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): ``--resume`` reads the on-disk PR draft.

    The resume branch is dark today and is the seam by which one role reads the
    previous role's work log, so it matters for the workflow contract, not just
    for coverage.

    Kill-check target: the ``draft_path.read_text`` block under ``--resume``.
    """
    home = _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    first = _run_args(tmp_path, config, "s10a-resume")
    assert _cmd_run(first, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0

    session_id = json.loads(next((home / ".fa" / "sessions").glob("*/manifest.json")).read_text(encoding="utf-8"))[
        "session_id"
    ]
    draft = home / ".fa" / "session-log" / "s10a-resume" / "pr_draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("# previous role's draft\n", encoding="utf-8")
    capsys.readouterr()

    second = _run_args(tmp_path, config, "s10a-resume-b", session_id=session_id)
    second.resume = True

    assert _cmd_run(second, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0


def test_s10a_run_builds_compactor_chain_under_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10a.6 / GAP6): a configured ``compactor`` role gets its own chain.

    ``_FAKE_MODELS_YAML`` declares only ``coder``, so the compactor block has
    never been exercised. Combined with proxy mode it also drives the
    *compactor-specific* rewrite branch, which is separate from the primary
    chain's and fails independently.

    Oracle: exit 0 through the full session — proving the extra chain was built
    and remained usable, not merely that the branch was entered.
    Kill-check target: the ``if compactor_config is not None`` block.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(
        _FAKE_MODELS_YAML + "compactor:\n"
        '  name: "test-model"\n'
        '  family: "openai"\n'
        "  chain:\n"
        "    - provider: openrouter\n"
        '      model: "test/model"\n'
        '      base_url: "https://example.invalid/v1"\n'
        "      api_key_env: TEST_FA_RUN_KEY\n",
        encoding="utf-8",
    )
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))

    args = _run_args(tmp_path, config, "s10a-compactor")

    # Oracle strengthened after the mutation minimum: asserting exit 0 alone
    # SURVIVED deleting the compactor block, because a run without a compactor
    # chain still succeeds. Patching the builder and counting invocations is
    # what actually distinguishes "chain built" from "block skipped".
    import fa.cli as _cli

    built: list[str] = []
    real_builder = _cli._build_provider_chain

    def _counting_builder(cfg: Any, **kw: Any) -> Any:
        built.append(cfg.name)
        return real_builder(cfg, **kw)

    monkeypatch.setattr("fa.cli._build_provider_chain", _counting_builder)

    assert _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    assert len(built) >= 2, f"compactor chain was not built; only {built} were"


def test_s10a_run_reports_proxy_rewrite_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10a.6 / GAP6): a chain the proxy cannot route is exit 2, not a silent run.

    Proxy mode rewrites every chain entry to point at the egress proxy. If an
    entry names a provider the proxy has no route for, continuing would send
    the request *direct* — bypassing the secret-isolation boundary ADR-12
    exists to enforce. Failing closed is the security property; this pins it.

    The rewrite failure is injected by stubbing ``_proxy_rewrite_chain`` to
    return an error string. A malformed provider name was tried first and
    rejected ~40 lines earlier by models-config validation, so it never reached
    this branch — the stub targets the contract under test rather than a
    proxy for it.

    Kill-check target: the ``if proxy_err`` branch after
    ``_proxy_rewrite_chain``.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))
    monkeypatch.setattr("fa.cli._proxy_rewrite_chain", lambda cfg, url: (cfg, "no route for provider"))

    args = _run_args(tmp_path, config, "s10a-proxyfail")

    assert _cmd_run(args, transport=_OkTransport(), secrets=_TEST_SECRETS) == 2
    assert "no route for provider" in capsys.readouterr().err
