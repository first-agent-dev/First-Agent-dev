"""
EventStream Runtime Server — FastAPI + PTY Pool
ADR-13 final: direct FastAPI target (user chose direct_fastapi)

Prior art: OpenHands Action Execution Server, OpenCode ShellPool
"""

from __future__ import annotations

from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .pty_pool import PtyPool, PtyResult

app = FastAPI(title="fa-runtime-server", version="0.1")
pool = PtyPool(max_size=3, base_cwd=Path("/workspace"))

class ExecuteRequest(BaseModel):
    session_id: str = "main"
    command: str
    timeout: int = 30
    workdir: Optional[str] = None

class ExecuteResponse(BaseModel):
    stdout: str
    exit_code: int
    truncated: bool
    session_id: str

class KillRequest(BaseModel):
    session_id: str

@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
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
        # Defensive check failure (Gap 6)
        raise HTTPException(status_code=400, detail=f"Defensive check failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send_ctrl_c")
def send_ctrl_c(session_id: str):
    if session_id not in pool.sessions:
        raise HTTPException(status_code=404, detail="session not found")
    msg = pool.sessions[session_id].send_ctrl_c()
    return {"msg": msg, "session_id": session_id}

@app.get("/list")
def list_sessions():
    return {"sessions": pool.list_sessions()}

@app.post("/kill")
def kill_session(req: KillRequest):
    if req.session_id not in pool.sessions:
        raise HTTPException(status_code=404, detail="session not found")
    pool.kill(req.session_id)
    return {"killed": req.session_id}

@app.get("/health")
def health():
    return {"status": "ok", "sessions": len(pool.sessions), "max_size": pool.max_size}

# Thin client for run_bash.py (to be used)
# Example:
# import requests
# resp = requests.post("http://fa-runtime-server:8001/execute", json={"session_id":"main","command":"cd /tmp && pwd"})
# data = resp.json()
# ToolResult.ok(f"bash exited {data['exit_code']}", result=data)

