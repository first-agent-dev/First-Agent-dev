"""S10c.1 — malformed / missing config is a structured error, not a traceback.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10c-contract-and-posture-fixes.md``

**Why this module exists.** I-40 was filed against ``fa routing-check``, but
executing the code during the S10c review showed the YAML half affected
**five** commands — ``routing-check``, ``run``, ``selfcheck``, ``probe`` and
``egress-proxy``. Each caught ``ConfigurationError`` /
``EvalFamilyConflictError`` / ``OSError``; PyYAML raises ``yaml.YAMLError``,
which is none of those, so every one of them printed a Python traceback
instead of the diagnostic it promised.

The fix converts the error **once**, at the single ``yaml.safe_load`` in
``load_models_config``. These tests exist so that claim is verified
per-command rather than assumed to propagate: a future refactor that moves a
command onto a different loader path would otherwise regress silently.

``egress-proxy`` is covered by ``test_s10c_egress_proxy_malformed_yaml_is_error``
because it loads the same config at **container start**, which is the S11
deployment path.

Test classes: C0p for the loader itself, C2 for each command root.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from fa.cli import _cmd_egress_proxy, _cmd_probe, _cmd_routing_check, _cmd_selfcheck
from fa.providers import load_models_config_from_path
from fa.providers.errors import ConfigurationError

_MALFORMED = "roles: [oops\n"


@pytest.fixture
def bad_config(tmp_path: Path) -> Path:
    path = tmp_path / "broken.yaml"
    path.write_text(_MALFORMED, encoding="utf-8")
    return path


def test_s10c_loader_raises_configuration_error_on_bad_yaml(bad_config: Path) -> None:
    """C0p (S10c.1 / CT1 / GAP2): the loader converts ``YAMLError`` at the source.

    This is the single change every command below inherits. Asserting it
    directly means a command-level regression can be told apart from a loader
    regression — five failing C2 tests and one failing C0p test point at the
    loader; five failing C2 tests alone point at the commands.

    Oracle: ``ConfigurationError`` (not ``yaml.YAMLError``) + PyYAML's own
    line/column text preserved for the operator.
    Kill-check target: the ``except yaml.YAMLError`` wrap in
    ``load_models_config``.
    """
    with pytest.raises(ConfigurationError) as excinfo:
        load_models_config_from_path(bad_config, require_api_keys=False)

    assert "not valid YAML" in str(excinfo.value)
    # PyYAML reports position; that is the actionable part of the message.
    assert "line" in str(excinfo.value).lower()
    assert isinstance(excinfo.value.__cause__, yaml.YAMLError), "the original parse error must be chained"


def test_s10c_routing_check_malformed_yaml_is_error(bad_config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10c.1 / GAP2): ``routing-check`` reports malformed YAML as exit 2.

    The deploy-gate command (``scripts/fa-clean-rebuild.sh:471``). A traceback
    here aborts the build with a stack trace instead of a one-line reason.

    Oracle: exit 2 + ``models config error``.
    Kill-check target: the loader wrap.
    """
    assert _cmd_routing_check(argparse.Namespace(config=bad_config)) == 2
    assert "models config error" in capsys.readouterr().out


def test_s10c_probe_malformed_yaml_is_error(bad_config: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 (S10c.1 / GAP2): ``probe`` reports malformed YAML as exit 2.

    Oracle: exit 2 + ``configuration error``.
    Kill-check target: the loader wrap.
    """
    args = argparse.Namespace(config=bad_config, role="coder", all_roles=False, timeout=5)
    assert _cmd_probe(args) == 2
    assert "configuration error" in capsys.readouterr().err


def test_s10c_selfcheck_malformed_yaml_is_error(
    bad_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10c.1 / GAP2): ``selfcheck`` reports malformed YAML as exit 2.

    Reaches the config load only after the proxy preflight and both HTTP
    probes succeed, so those are stubbed — the subject here is the config
    error, not the proxy.

    Oracle: exit 2 + ``models config error``.
    Kill-check target: the loader wrap.
    """
    token = bad_config.parent / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))
    monkeypatch.setattr("fa.cli._selfcheck_http_get", lambda url, headers=None: (200, b"[]"))

    assert _cmd_selfcheck(argparse.Namespace(config=bad_config, role="coder")) == 2
    assert "models config error" in capsys.readouterr().out


def test_s10c_egress_proxy_malformed_yaml_is_error(
    bad_config: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10c.1 / GAP2): ``egress-proxy`` reports malformed YAML as exit 2.

    **The S11 path.** This command loads the routing config at *container
    start*; a traceback there is a crash-looping container rather than a
    readable startup error.

    Oracle: exit 2 + ``models config error`` on **stderr** — this command
    reports to stderr where its siblings use stdout (verified, not assumed).
    No port is bound: the config load precedes ``serve()``.
    Kill-check target: the loader wrap.
    """
    secrets = tmp_path / "fa.env"
    secrets.write_text("TEST_FA_RUN_KEY=sk-test-abcdefghij\n", encoding="utf-8")
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    args = argparse.Namespace(listen="127.0.0.1:9", models=bad_config, secrets=secrets, token_file=token)

    assert _cmd_egress_proxy(args) == 2
    assert "models config error" in capsys.readouterr().err
