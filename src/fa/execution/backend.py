"""One live cell episode per authenticated view, with exactly one RUN send.

This is the thin lifecycle owner between the real WorkspaceAuthority admission
and the existing Docker/worker transports. It owns no grant, no receipt and no
terminality: worker text is untrusted, and independent container/cgroup facts
are established elsewhere. A command is never replayed and a second cell is
never created for a live episode.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from fa.execution.cell_protocol import encode_cell_request
from fa.execution.docker import DockerCells, DockerEngine, DockerUnavailableError
from fa.execution.journal import JournalError, OperationJournal
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import decode_request, encode_json
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, NamespaceRef, Operation, ViewRef
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
    """Observed command result. NOT a receipt and NOT a terminality claim.

    `duration_ms` is the RUN send-to-reply window measured here; the receipt
    issuer adds the container/cgroup facts that make a receipt possible.
    """

    operation_id: str
    container_id: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    session_id: str | None
    duration_ms: int
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

    @property
    def cells(self) -> DockerCells:
        """The owned-cell lifecycle seam, for the terminal-barrier adapter."""
        return self._cells

    @contextmanager
    def _bounded_mutex(self, deadline: float) -> Generator[None]:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._mutex.acquire(timeout=remaining):
            raise SupervisorError("BACKEND_UNAVAILABLE")
        try:
            yield
        finally:
            self._mutex.release()

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
        return ViewRef.from_dict(raw)

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
            if scope.profile.interactive:
                return self._run(episode, scope, req, namespace, deadline=deadline)
            failure: BaseException | None = None
            try:
                return self._run(episode, scope, req, namespace, deadline=deadline)
            except BaseException as error:
                failure = error
                raise
            finally:
                try:
                    episode.worker.close(deadline=deadline)
                except (OSError, WorkerUnavailableError, ExecutionContractError):
                    if failure is None:
                        raise SupervisorError("EXECUTION_UNKNOWN") from None

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
        if not scope.profile.interactive:
            if req["payload"]["session_id"] is not None:
                raise SupervisorError("INPUT_POLICY")
            inputs = scope.inputs
            try:
                with scope.effect():
                    container_id = self._cells.launch_new(
                        req,
                        profile=scope.profile,
                        source=inputs.source,
                        scratch=inputs.scratch,
                        cache=inputs.cache,
                        deadline=deadline,
                    )
                    stream = self._cells.attach_created(req, profile=scope.profile, deadline=deadline)
            except JournalError as error:
                raise SupervisorError(error.code) from None
            except ExecutionContractError:
                raise SupervisorError("PATH_DENIED") from None
            except DockerUnavailableError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None
            except TimeoutError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None
            return _Episode(req, container_id, WorkerClient(stream))

        if req["payload"]["session_id"] is None:
            raise SupervisorError("INPUT_POLICY")
        with self._bounded_mutex(deadline):
            existing = self._episodes.get(key)
            creation = self._creations.setdefault(key, threading.Lock())
        if existing is not None:
            return existing
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not creation.acquire(timeout=remaining):
            raise SupervisorError("BACKEND_UNAVAILABLE")
        try:
            with self._bounded_mutex(deadline):
                existing = self._episodes.get(key)
            if existing is not None:
                return existing
            inputs = scope.inputs
            try:
                with scope.effect():
                    container_id = self._cells.launch_new(
                        req,
                        profile=scope.profile,
                        source=inputs.source,
                        scratch=inputs.scratch,
                        cache=inputs.cache,
                        deadline=deadline,
                    )
                    stream = self._cells.attach_created(req, profile=scope.profile, deadline=deadline)
                    worker = WorkerClient(stream)
            except JournalError as error:
                raise SupervisorError(error.code) from None
            except ExecutionContractError:
                raise SupervisorError("PATH_DENIED") from None
            except DockerUnavailableError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None
            except TimeoutError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None
            episode = _Episode(req, container_id, worker)
            with self._bounded_mutex(deadline):
                self._episodes[key] = episode
            return episode
        finally:
            creation.release()

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
        if scope.profile.interactive != (session_id is not None):
            raise SupervisorError("INPUT_POLICY")
        view = self._view_of(req["view_ref"])
        # The command keeps its OWN journal record; only the cell is shared.
        try:
            with scope.effect():
                record = self._journal.lookup(operation_id, namespace, deadline=deadline)
                if record is None:
                    raise SupervisorError("EXECUTION_UNKNOWN")
                if record["view_ref"] != view.to_dict():
                    raise SupervisorError("UNAUTHORIZED")
                if record["container_id"] != episode.container_id:
                    self._journal.record_container(operation_id, namespace, episode.container_id, deadline=deadline)
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
        started = time.monotonic()
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
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        )

    def cancel(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        """Persist cancel intent for the exact command, then stop the OWNED cell.

        Cancel intent is not a terminal receipt and asserts no process death.
        An interactive view resolves its cell through the live episode identity;
        a noninteractive one-shot has no episode, so its own journal record is
        the identity (spec §2.2 / E262).
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
        if not profile.interactive:
            return self._cancel_operation(operation_id, namespace, view, profile, deadline=deadline)
        with self._bounded_mutex(deadline):
            key = _EpisodeKey.build(peer, namespace, view, profile.profile_id)
            episode = self._episodes.get(key)
        if episode is None:
            raise SupervisorError("EXECUTION_UNKNOWN")
        try:
            self._journal.request_cancel(operation_id, namespace, view=view, deadline=deadline)
        except JournalError as error:
            raise SupervisorError(error.code) from None
        try:
            observed = self._cells.force_stop_created(
                episode.creation_request,
                profile=profile,
                deadline=deadline,
            )
        except JournalError as error:
            raise SupervisorError(error.code) from None
        except ExecutionContractError:
            raise SupervisorError("PATH_DENIED") from None
        except DockerUnavailableError as error:
            # A malformed or foreign observation means the cell we were told to
            # stop is not provably the owned one. It is never a successful stop.
            raise SupervisorError("PATH_DENIED" if error.status is None else "BACKEND_UNAVAILABLE") from None
        except TimeoutError:
            raise SupervisorError("BACKEND_UNAVAILABLE") from None
        return {"container_id": observed.container_id, "status": observed.status}

    def _cancel_operation(
        self,
        operation_id: str,
        namespace: NamespaceRef,
        view: ViewRef,
        profile: ExecutionProfile,
        *,
        deadline: float,
    ) -> dict[str, Any]:
        """Stop a one-shot operation through its own durable record.

        No episode map, no creation request and no replacement cell: the record
        binds the namespace and CID, and the requested view must match exactly.
        """
        try:
            observed = self._cells.force_stop_operation(
                operation_id=operation_id,
                namespace=namespace,
                view=view,
                profile=profile,
                deadline=deadline,
            )
        except JournalError as error:
            raise SupervisorError(error.code) from None
        except ExecutionContractError:
            raise SupervisorError("PATH_DENIED") from None
        except DockerUnavailableError as error:
            raise SupervisorError("PATH_DENIED" if error.status is None else "BACKEND_UNAVAILABLE") from None
        except TimeoutError:
            raise SupervisorError("BACKEND_UNAVAILABLE") from None
        if observed is None:
            # Durable intent only: the operation provably cannot create or start now.
            return {"container_id": None, "status": "not_created"}
        return {"container_id": observed.container_id, "status": observed.status}

    def reconcile(self, *, deadline: float) -> list[dict[str, Any]]:
        """Stop surviving owned cells of uncertain records. Never create or re-run."""
        profile = self._authority.approved_profile
        if profile is None:
            raise SupervisorError("UNAPPROVED_PROFILE")
        results: list[dict[str, Any]] = []
        try:
            records = self._journal.owned_cells(deadline=deadline)
        except JournalError as error:
            raise SupervisorError(error.code) from None
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
        with self._bounded_mutex(deadline):
            episodes = list(self._episodes.values())
            self._episodes.clear()
        for episode in episodes:
            try:
                episode.worker.close(deadline=deadline)
            except WorkerUnavailableError:
                continue
