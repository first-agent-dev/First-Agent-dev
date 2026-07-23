"""
EventStream Runtime Server — FastAPI + PTY Pool
ADR-13 final: direct FastAPI target (user chose direct_fastapi)

Prior art: OpenHands Action Execution Server, OpenCode ShellPool
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from .pty_pool import PtyPool, PtyResult

logger = logging.getLogger(__name__)

# Optional runtime dependency: FastAPI + pydantic.
# These names are only called/used inside `if HAS_FASTAPI:` blocks.
# Pre-declare with explicit Any annotations (PY8 closure) so that pyrefly
# does not narrow them to None/Exception/object from the fallback branch.
FastAPI: Any
HTTPException: Any
BaseModel: Any
HAS_FASTAPI: bool

try:
    _fastapi = importlib.import_module("fastapi")
    _pydantic = importlib.import_module("pydantic")
    FastAPI = _fastapi.FastAPI
    HTTPException = _fastapi.HTTPException
    BaseModel = _pydantic.BaseModel
    HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # guarded by HAS_FASTAPI=False; never called
    HTTPException = Exception
    BaseModel = object
    HAS_FASTAPI = False

app: Any = None
pool: PtyPool | None = None
runtime_pool: Any = None


if HAS_FASTAPI:
    # Local reference for the type checker: the module-level HTTPException may
    # be narrowed to Exception by the fallback branch above.  Inside this block
    # the real FastAPI HTTPException is guaranteed, but pyrefly cannot prove it.
    _HTTPException: Any = HTTPException

    app = FastAPI(title="fa-runtime-server", version="0.1")
    pool = PtyPool(max_size=3, base_cwd=Path("/workspace"))
    runtime_pool = pool

    class ExecuteRequest(BaseModel):  # type: ignore[misc]  # optional dependency is loaded dynamically
        session_id: str = "main"
        command: str
        timeout: int = 30
        workdir: str | None = None

    class ExecuteResponse(BaseModel):  # type: ignore[misc]  # optional dependency is loaded dynamically
        stdout: str
        exit_code: int
        truncated: bool
        session_id: str

    class KillRequest(BaseModel):  # type: ignore[misc]  # optional dependency is loaded dynamically
        session_id: str

    @app.post("/execute", response_model=ExecuteResponse)  # type: ignore[untyped-decorator]  # FastAPI is optional
    def execute(req: ExecuteRequest) -> ExecuteResponse:
        try:
            session = runtime_pool.acquire(req.session_id, workdir=req.workdir)
            result: PtyResult = session.run(req.command, timeout=req.timeout)
            return ExecuteResponse(
                stdout=result.stdout,
                exit_code=result.exit_code,
                truncated=result.truncated,
                session_id=result.session_id,
            )
        except AssertionError as e:
            logger.error("/execute assertion failure session=%s: %s", req.session_id, e, exc_info=True)
            raise _HTTPException(status_code=400, detail=f"Defensive check failed: {e}") from e
        except Exception as e:
            # Fail-closed HTTP boundary: the endpoint MUST return a structured
            # error response rather than crashing the server.  Loud logging
            # ensures the error is observable ("open stand" principle).
            logger.error("/execute error session=%s command=%s: %s", req.session_id, req.command, e, exc_info=True)
            raise _HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/send_ctrl_c")  # type: ignore[untyped-decorator]  # FastAPI is optional
    def send_ctrl_c(session_id: str) -> dict[str, str]:
        if session_id not in runtime_pool.sessions:
            raise _HTTPException(status_code=404, detail="session not found")
        msg = runtime_pool.sessions[session_id].send_ctrl_c()
        return {"msg": msg, "session_id": session_id}

    @app.get("/list")  # type: ignore[untyped-decorator]  # FastAPI is optional
    def list_sessions() -> dict[str, list[str]]:
        return {"sessions": runtime_pool.list_sessions()}

    @app.post("/kill")  # type: ignore[untyped-decorator]  # FastAPI is optional
    def kill_session(req: KillRequest) -> dict[str, str]:
        if req.session_id not in runtime_pool.sessions:
            raise _HTTPException(status_code=404, detail="session not found")
        runtime_pool.kill(req.session_id)
        return {"killed": req.session_id}

    @app.get("/health")  # type: ignore[untyped-decorator]  # FastAPI is optional
    def health() -> dict[str, str | int]:
        return {"status": "ok", "sessions": len(runtime_pool.sessions), "max_size": runtime_pool.max_size}

else:
    app = None
    pool = None
