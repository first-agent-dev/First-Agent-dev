"""Immutable operator-approved cell profile and fixed Docker create rendering.

This does not admit a view, validate its ownership, call Docker, attest image/
host facts, or prove terminality. The real authority must validate protected host
paths immediately before use. None of these host inputs is a wire/model field.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fa.execution.protocol import _loads
from fa.execution.types import Access, ExecutionContractError, ViewRef, _hex_id, _positive_integer


def _configured_id(value: str) -> None:
    if not isinstance(value, str) or len(value) > 48 or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value) is None:
        raise ExecutionContractError


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    image: str
    uid: int
    gid: int
    nano_cpus: int
    memory_bytes: int
    pids_limit: int
    max_command_ms: int
    interactive: bool
    cgroup_parent: str
    seccomp_json: str

    def __post_init__(self) -> None:
        _configured_id(self.profile_id)
        if (
            not isinstance(self.image, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}", self.image) is None
        ):
            raise ExecutionContractError
        for value in (self.uid, self.gid, self.nano_cpus, self.memory_bytes, self.pids_limit, self.max_command_ms):
            _positive_integer(value)
        if type(self.interactive) is not bool:
            raise ExecutionContractError
        if (
            not isinstance(self.cgroup_parent, str)
            or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", self.cgroup_parent) is None
        ):
            raise ExecutionContractError
        if any(part in {"", ".", ".."} for part in self.cgroup_parent.split("/")):
            raise ExecutionContractError
        try:
            policy = _loads(self.seccomp_json.encode("utf-8"))
        except (AttributeError, UnicodeError):
            raise ExecutionContractError from None
        # The approved syscall policy remains a host-review input. Never accept
        # Docker's "unconfined" or an allow-by-default profile as isolation.
        if policy.get("defaultAction") != "SCMP_ACT_ERRNO" or not isinstance(policy.get("syscalls"), list):
            raise ExecutionContractError

    @property
    def image_digest(self) -> str:
        return "sha256:" + self.image.rsplit("@sha256:", 1)[1]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def create_spec(
        self,
        *,
        operation_id: str,
        view: ViewRef,
        source: Path,
        scratch: Path,
        cache: Path,
    ) -> dict[str, Any]:
        """Render only; paths must come from actual protected authority records."""
        _hex_id(operation_id, "op-")
        paths = (source, scratch, cache)
        for path in paths:
            if not path.is_absolute() or ".." in path.parts or path == Path("/"):
                raise ExecutionContractError
        for index, path in enumerate(paths):
            if any(path.is_relative_to(other) or other.is_relative_to(path) for other in paths[index + 1 :]):
                raise ExecutionContractError
        mounts = [
            {
                "Type": "bind",
                "Source": str(path),
                "Target": target,
                "ReadOnly": read_only,
                "BindOptions": {"Propagation": "rprivate"},
            }
            for path, target, read_only in (
                (source, "/workspace", view.access is Access.READ),
                (scratch, "/scratch", False),
                (cache, "/opt/toolchain-cache", True),
            )
        ]
        return {
            "name": "fa-job-" + operation_id.removeprefix("op-"),
            "body": {
                "Image": self.image,
                "User": f"{self.uid}:{self.gid}",
                "WorkingDir": "/workspace",
                "Entrypoint": ["/opt/fa-venv/bin/python", "-I", "-m", "fa.execution.cell_worker"],
                "Cmd": ["--max-command-ms", str(self.max_command_ms)],
                "Env": ["HOME=/scratch/home", "TMPDIR=/scratch/tmp", "PYTHONDONTWRITEBYTECODE=1"],
                "OpenStdin": True,
                "StdinOnce": False,
                "Tty": False,
                "NetworkDisabled": True,
                "Labels": {"fa.execution.operation_id": operation_id, "fa.execution.view_id": view.view_id},
                "HostConfig": {
                    "Mounts": mounts,
                    "NetworkMode": "none",
                    "IpcMode": "private",
                    "PidMode": "",
                    "UTSMode": "",
                    "CgroupnsMode": "private",
                    "CgroupParent": self.cgroup_parent,
                    "Privileged": False,
                    "CapDrop": ["ALL"],
                    "ReadonlyRootfs": True,
                    "SecurityOpt": [
                        "no-new-privileges:true",
                        "seccomp=" + json.dumps(_loads(self.seccomp_json.encode()), separators=(",", ":")),
                    ],
                    "NanoCpus": self.nano_cpus,
                    "Memory": self.memory_bytes,
                    "MemorySwap": self.memory_bytes,
                    "PidsLimit": self.pids_limit,
                    "PublishAllPorts": False,
                },
            },
        }
