"""
EventStream Runtime Server — FastAPI + PTY Pool
ADR-13 final: direct FastAPI target (user chose direct_fastapi)

Prior art: OpenHands Action Execution Server, OpenCode ShellPool
"""

from __future__ import annotations

from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException  # type: ignore[import-untyped]
    from pydantic import BaseModel  # type: ignore[import-untyped]

    HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # type: ignore
    HTTPException = Exception  # type: ignore
    BaseModel = object  # type: ignore
    HAS_FASTAPI = False

from .pty_pool import PtyPool, PtyResult

if HAS_FASTAPI:
    app = FastAPI(title="fa-runtime-server", version="0.1")  # type: ignore
    pool = PtyPool(max_size=3, base_cwd=Path("/workspace"))

    class ExecuteRequest(BaseModel):  # type: ignore
        session_id: str = "main"
        command: str
        timeout: int = 30
        workdir: str | None = None

    class ExecuteResponse(BaseModel):  # type: ignore
        stdout: str
        exit_code: int
        truncated: bool
        session_id: str

    class KillRequest(BaseModel):  # type: ignore
        session_id: str

    @app.post("/execute", response_model=ExecuteResponse)
    def execute(req: ExecuteRequest):  # type: ignore
        try:
            session = pool.acquire(req.session_id, workdir=req.workdir)
            result: PtyResult = session.run(req.command, timeout=req.timeout)
            return ExecuteResponse(
                stdout=result.stdout,
                exit_code=result.exit_code,
                truncated=result.truncated,
                session_id=result.session_id,
            )
        except AssertionError as e:
            raise HTTPException(status_code=400, detail=f"Defensive check failed: {e}")
        except Exception as e:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/send_ctrl_c")
    def send_ctrl_c(session_id: str):  # type: ignore
        if session_id not in pool.sessions:
            raise HTTPException(status_code=404, detail="session not found")
        msg = pool.sessions[session_id].send_ctrl_c()
        return {"msg": msg, "session_id": session_id}

    @app.get("/list")
    def list_sessions():  # type: ignore
        return {"sessions": pool.list_sessions()}

    @app.post("/kill")
    def kill_session(req: KillRequest):  # type: ignore
        if req.session_id not in pool.sessions:
            raise HTTPException(status_code=404, detail="session not found")
        pool.kill(req.session_id)
        return {"killed": req.session_id}

    @app.get("/health")
    def health():  # type: ignore
        return {"status": "ok", "sessions": len(pool.sessions), "max_size": pool.max_size}

else:
    app = None  # type: ignore
    pool = None  # type: ignore
