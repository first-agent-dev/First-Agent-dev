"""Shared execution contract primitives with no protocol/model dependencies."""

from __future__ import annotations

import re
from enum import StrEnum


class ExecutionContractError(ValueError):
    """Sanitized structural failure; never include caller data or grants."""

    def __init__(self) -> None:
        super().__init__("execution_contract_invalid")


def _positive_integer(value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ExecutionContractError


class Operation(StrEnum):
    """The nineteen closed v1 operation names; not executable callbacks."""

    HEALTH = "health"
    REGISTER_WORKSPACE = "register_workspace"
    ACQUIRE_WRITER = "acquire_writer"
    PIN_READER = "pin_reader"
    CREATE_VIEW = "create_view"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    EXEC = "exec"
    INSPECT = "inspect"
    CANCEL = "cancel"
    STOP_VIEW = "stop_view"
    SEAL = "seal"
    PUBLISH = "publish"
    INSTALL_PROJECT = "install_project"
    RELEASE = "release"
    PTY_CONTROL = "pty_control"
    HANDOFF = "handoff"
    PREPARE_BUNDLE = "prepare_bundle"


def _hex_id(value: object, prefix: str, length: int = 32) -> None:
    if not isinstance(value, str) or re.fullmatch(prefix + rf"[0-9a-f]{{{length}}}", value) is None:
        raise ExecutionContractError
