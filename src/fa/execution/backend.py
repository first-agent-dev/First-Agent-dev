"""One live cell episode per authenticated view, with exactly one RUN send.

This is the thin lifecycle owner between the real WorkspaceAuthority admission
and the existing Docker/worker transports. It owns no grant, no receipt and no
terminality: worker text is untrusted, and independent container/cgroup facts
are established elsewhere. A command is never replayed and a second cell is
never created for a live episode.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from fa.execution.cell_protocol import encode_cell_request
from fa.execution.docker import DockerCells, DockerEngine, DockerUnavailableError
from fa.execution.journal import JournalError, OperationJournal
from fa.execution.protocol import decode_request, encode_json
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import Access, ExecutionContractError, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.execution.worker_client import WorkerClient, WorkerUnavailableError
from fa.execution.workspace import WorkAdmission, WorkspaceAuthority


@dataclass(frozen=True)
class _EpisodeKey:
    """Identity of a live episode. A shell name alone is never an identity."""

    principal: str
    namespace: tuple[str, str, str | None]
    view: tuple[str, str, str, str, int, str, str]
    profile_id: str

    @classmethod
    def build(cls, peer: PeerIdentity, namespace: NamespaceRef, view: ViewRef, profile_id: str) -> _EpisodeKey:
        return cls(
            peer.principal,
            (namespace.session_id, namespace.run_id, namespace.parent_run_id),
            (
                view.workspace_id,
                view.view_id,
                view.base_revision,
                view.owner_run_id,
                view.generation,
                view.access.value,
                view.purpose.value,
            ),
            profile_id,
        )


@dataclass
class _Episode:
    """Original creation binding plus the SOLE attach for one live cell.

    The episode identity is the map key (principal, namespace, exact view and
    approved profile); this record keeps only what a later command needs: the
    ORIGINAL creation request, its durable container id and the sole attach.
    """

    creation_request: dict[str, Any]
    container_id: str
    worker: WorkerClient


@dataclass(frozen=True)
class CommandOutcome:
    """Observed command result. NOT a receipt and NOT a terminality claim."""

    operation_id: str
    container_id: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    session_id: str
    terminal_barrier: bool = False


class CellBackend:
    """Per-view live episode owner over DockerCells, WorkerClient and the journal.

    The authority admission is mandatory: no create, start, attach or RUN send
    happens without a live admitted scope. Every command keeps its own durable
    journal record while reusing the original cell and its original labels.
    """

    def __init__(
        self,
        authority: WorkspaceAuthority,
        engine: DockerEngine,
        journal: OperationJournal,
    ) -> None:
        if not isinstance(authority, WorkspaceAuthority) or not isinstance(engine, DockerEngine):
            raise ExecutionContractError
        if not isinstance(journal, OperationJournal):
            raise ExecutionContractError
        self._authority = authority
        self._engine = engine
        self._journal = journal
        self._cells = DockerCells(engine, journal, validate_binding=self._validate_binding)
        self._mutex = threading.RLock()
        self._episodes: dict[_EpisodeKey, _Episode] = {}
        # One creation at a time per episode identity: two concurrent commands
        # on the same view must never produce two live cells.
        self._creations: dict[_EpisodeKey, threading.Lock] = {}

    @property
    def journal(self) -> OperationJournal:
        return self._journal

    def episode_count(self) -> int:
        with self._mutex:
            return len(self._episodes)

    def episode_container(self, peer: PeerIdentity, namespace: NamespaceRef, view: ViewRef) -> str | None:
        """The live cell of the EXACT episode, or None. Never a shell-name lookup.

        The supervisor needs this to stop a view's own cell. The key binds the
        authenticated principal, namespace, exact view and approved profile, so
        a foreign principal, namespace or view can never reach a live shell.
        """
        profile = self._authority.approved_profile
        if profile is None:
            return None
        key = _EpisodeKey.build(peer, namespace, view, profile.profile_id)
        with self._mutex:
            episode = self._episodes.get(key)
        return None if episode is None else episode.container_id

    def _validate_binding(
        self,
        namespace: NamespaceRef,
        view: ViewRef,
        source: Any,
        scratch: Any,
        cache: Any,
    ) -> None:
        """Only the authority's own trusted triple may reach Docker."""
        trusted = self._authority.execution_trusted(view)
        if trusted is None:
            raise ExecutionContractError
        owner, trusted_source, trusted_scratch, trusted_cache = trusted
        if owner != namespace or source != trusted_source or scratch != trusted_scratch or cache != trusted_cache:
            raise ExecutionContractError

    @staticmethod
    def _view_of(raw: dict[str, Any]) -> ViewRef:
        return ViewRef(
            workspace_id=raw["workspace_id"],
            view_id=raw["view_id"],
            base_revision=raw["base_revision"],
            owner_run_id=raw["owner_run_id"],
            generation=raw["generation"],
            access=Access(raw["access"]),
            purpose=ViewPurpose(raw["purpose"]),
        )

    def _admitted(
        self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float
    ) -> tuple[WorkAdmission, dict[str, Any], NamespaceRef, ViewRef]:
        req = decode_request(encode_json(request))
        if req["op"] != Operation.EXEC.value:
            raise SupervisorError("INPUT_POLICY")
        namespace = NamespaceRef(**req["namespace"])
        raw = req["view_ref"]
        if raw is None:
            raise SupervisorError("INPUT_POLICY")
        view = self._view_of(raw)
        scope = self._authority.admit(peer, request, deadline=deadline)
        return scope, req, namespace, view

    def execute(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> CommandOutcome:
        """Run one command in the view's live cell, with exactly one RUN send."""
        scope, req, namespace, view = self._admitted(peer, request, deadline=deadline)
        # The scope owns the admitted work: leaving this block retires it, so a
        # finished command never keeps the view's drain waiting.
        with scope:
            key = _EpisodeKey.build(peer, namespace, view, scope.profile.profile_id)
            episode = self._live_episode(scope, req, key, deadline=deadline)
            return self._run(episode, scope, req, namespace, deadline=deadline)

    def _live_episode(
        self,
        scope: WorkAdmission,
        req: dict[str, Any],
        key: _EpisodeKey,
        *,
        deadline: float,
    ) -> _Episode:
        """The live cell of this exact identity, created at most once, ever.

        A later command in the SAME episode reuses the original cell, its
        original container id and its sole attach. Concurrent commands on the
        same view share this creation, so a second cell is never created for a
        live episode.
        """
        with self._mutex:
            creation = self._creations.setdefault(key, threading.Lock())
        with creation:
            with self._mutex:
                existing = self._episodes.get(key)
            if existing is not None:
                return existing
            inputs = scope.inputs
            try:
                container_id = self._cells.launch_new(
                    req,
                    profile=scope.profile,
                    source=inputs.source,
                    scratch=inputs.scratch,
                    cache=inputs.cache,
                    deadline=deadline,
                )
                stream = self._cells.attach_created(req, profile=scope.profile, deadline=deadline)
            except ExecutionContractError:
                raise SupervisorError("PATH_DENIED") from None
            except DockerUnavailableError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None
            worker = WorkerClient(stream)
            episode = _Episode(
                creation_request=req,
                container_id=container_id,
                worker=worker,
            )
            with self._mutex:
                self._episodes[key] = episode
            return episode

    def _run(
        self,
        episode: _Episode,
        scope: WorkAdmission,
        req: dict[str, Any],
        namespace: NamespaceRef,
        *,
        deadline: float,
    ) -> CommandOutcome:
        """Bind this command's own durable record, then send exactly one RUN."""
        payload = req["payload"]
        operation_id = payload["operation_id"]
        session_id = payload["session_id"]
        if session_id is None:
            raise SupervisorError("INPUT_POLICY")
        # The command keeps its OWN journal record; only the cell is shared.
        try:
            record = self._journal.lookup(operation_id, namespace)
        except JournalError as error:
            raise SupervisorError(error.code) from None
        if record is None:
            raise SupervisorError("EXECUTION_UNKNOWN")
        if record["container_id"] != episode.container_id:
            try:
                self._journal.record_container(operation_id, namespace, episode.container_id)
            except JournalError as error:
                raise SupervisorError(error.code) from None
        frame = encode_cell_request(
            request_id=operation_id.removeprefix("op-"),
            action="RUN",
            payload={
                "command": payload["command"],
                "cwd": payload["cwd"],
                "timeout_ms": payload["timeout_ms"],
                "session_id": session_id,
            },
        )
        exchange = None
        try:
            with scope.send():
                try:
                    # The frame write is inside the journal send guard; the reply
                    # wait happens outside it, so a cancel can still be persisted.
                    exchange = episode.worker.begin(frame, deadline=deadline)
                except WorkerUnavailableError:
                    raise SupervisorError("EXECUTION_UNKNOWN") from None
            result = episode.worker.await_reply(exchange, deadline=deadline)
        except WorkerUnavailableError:
            raise SupervisorError("EXECUTION_UNKNOWN") from None
        return CommandOutcome(
            operation_id=operation_id,
            container_id=episode.container_id,
            exit_code=result["exit_code"],
            stdout=result["stdout"],
            stderr="",
            timed_out=result["timed_out"],
            truncated=result["truncated"],
            session_id=result["session_id"],
        )

    def cancel(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        """Persist cancel intent for the exact command, then stop the OWNED cell.

        Cancel intent is not a terminal receipt and asserts no process death.
        """
        req = decode_request(encode_json(request))
        if req["op"] != Operation.CANCEL.value:
            raise SupervisorError("INPUT_POLICY")
        namespace = NamespaceRef(**req["namespace"])
        raw = req["view_ref"]
        if raw is None:
            raise SupervisorError("INPUT_POLICY")
        view = self._view_of(raw)
        operation_id = req["payload"]["operation_id"]
        profile = self._authority.approved_profile
        if profile is None:
            raise SupervisorError("UNAPPROVED_PROFILE")
        with self._mutex:
            key = _EpisodeKey.build(peer, namespace, view, profile.profile_id)
            episode = self._episodes.get(key)
        if episode is None:
            raise SupervisorError("EXECUTION_UNKNOWN")
        try:
            self._journal.request_cancel(operation_id, namespace)
        except JournalError as error:
            raise SupervisorError(error.code) from None
        try:
            observed = self._cells.force_stop_created(
                episode.creation_request,
                profile=profile,
                deadline=deadline,
            )
        except ExecutionContractError:
            raise SupervisorError("PATH_DENIED") from None
        except DockerUnavailableError as error:
            # A malformed or foreign observation means the cell we were told to
            # stop is not provably the owned one. It is never a successful stop.
            raise SupervisorError("PATH_DENIED" if error.status is None else "BACKEND_UNAVAILABLE") from None
        return {"container_id": observed.container_id, "status": observed.status}

    def reconcile(self, *, deadline: float) -> list[dict[str, Any]]:
        """Stop surviving owned cells of uncertain records. Never create or re-run."""
        profile = self._authority.approved_profile
        if profile is None:
            raise SupervisorError("UNAPPROVED_PROFILE")
        results: list[dict[str, Any]] = []
        records = self._journal.unfinished()
        for container_id in sorted({r["container_id"] for r in records if r["container_id"]}):
            candidates = [r for r in records if r["container_id"] == container_id]
            stopped = False
            for record in candidates:
                view = self._view_of(record["view_ref"])
                try:
                    observed = self._engine.force_stop_owned(
                        operation_id=record["operation_id"],
                        view=view,
                        profile=profile,
                        container_id=container_id,
                        deadline=deadline,
                    )
                except (DockerUnavailableError, ExecutionContractError, OSError):
                    continue
                results.append({"operation_id": record["operation_id"], "status": observed.status})
                stopped = True
                break
            if not stopped:
                results.append({"operation_id": container_id, "status": "UNKNOWN"})
        return results

    def close(self, *, deadline: float) -> None:
        """Release the local attach handles. Never asserts cell or descendant death."""
        with self._mutex:
            episodes = list(self._episodes.values())
            self._episodes.clear()
        for episode in episodes:
            try:
                episode.worker.close(deadline=deadline)
            except WorkerUnavailableError:
                continue
