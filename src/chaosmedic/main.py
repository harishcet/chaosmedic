from __future__ import annotations

import html
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from chaosmedic import db, runner
from chaosmedic.config import get_settings
from chaosmedic.engine import orchestrator
from chaosmedic.triggers import github as gh
from chaosmedic.triggers import normalize

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.ensure_schema()
    yield


app = FastAPI(
    title="ChaosMedic",
    description="Autonomous Multi-Agent Infrastructure Self-Healing & Incident Response Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "engine": "ChaosMedic", "database": "Postgres" if db.is_postgres() else "SQLite"}


# --- ChaosMedic Autonomous Incident API ---------------------------------------------------

@app.post("/api/incidents", status_code=202)
async def create_incident_endpoint(payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Ingest a failure signal (HTTP 500, crash, health failure) and trigger self-healing."""
    inc_id = payload.get("incident_id") or f"inc-{uuid.uuid4().hex[:8]}"
    service = payload.get("service") or payload.get("app") or "target-service"
    endpoint = payload.get("endpoint") or payload.get("url") or "/api"
    status_code = payload.get("status_code", 500)
    target_ws = payload.get("target_workspace")

    alert_payload = {
        "incident_id": inc_id,
        "title": payload.get("title") or f"HTTP {status_code} on {endpoint}",
        "service": service,
        "endpoint": endpoint,
        "status_code": status_code,
        "stack_trace": payload.get("stack_trace") or "",
        "logs": payload.get("logs") or [],
        "target_workspace": target_ws
    }

    # Record incident in database immediately
    db.create_incident({
        "incident_id": inc_id,
        "service": service,
        "error_type": f"HTTP {status_code}",
        "status": "detecting",
        "stage": "DETECT",
        "current_agent": "Detection Agent",
        "payload": alert_payload
    })

    # Run LangGraph pipeline in background to guarantee free-tier non-blocking UI response
    background_tasks.add_task(orchestrator.run_incident_pipeline, alert_payload, target_ws, inc_id)

    return {
        "incident_id": inc_id,
        "status": "detecting",
        "stage": "DETECT",
        "message": f"ChaosMedic self-healing pipeline triggered for {service} ({endpoint})."
    }


@app.get("/api/incidents")
def list_incidents_endpoint(limit: int = 50) -> list[dict]:
    """List recent incidents with pipeline state and triage status."""
    return db.list_incidents(limit)


@app.get("/api/incidents/{incident_id}")
def get_incident_endpoint(incident_id: str) -> dict:
    """Get live incident status, stage, diagnosis, candidate diffs, and validation scores."""
    inc = db.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc


@app.post("/api/incidents/{incident_id}/approve", status_code=200)
def approve_incident_endpoint(incident_id: str) -> dict:
    """Human approval gate: approve the safest validated patch and trigger deployment & recovery."""
    res = orchestrator.resume_incident_pipeline(incident_id, action="approve")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/incidents/{incident_id}/reject", status_code=200)
def reject_incident_endpoint(incident_id: str) -> dict:
    """Human approval gate: reject candidate patch."""
    res = orchestrator.resume_incident_pipeline(incident_id, action="reject")
    return res


@app.get("/api/memory")
def get_incident_memory(limit: int = 50) -> list[dict]:
    """Retrieve historical incidents and candidate patches from Incident Memory."""
    return db.list_memory(limit)


@app.get("/api/pipeline")
def get_pipeline_stages() -> dict:
    """Return the official 10-stage autonomous self-healing pipeline architecture."""
    return {
        "stages": [
            {"id": "CONNECT", "label": "Connect", "agent": "Incident Monitor", "desc": "Connects to endpoints & logs"},
            {"id": "DETECT", "label": "Detect", "agent": "Detection Agent", "desc": "Detects HTTP 500 / health failure"},
            {"id": "COLLECT", "label": "Collect", "agent": "Evidence Agent", "desc": "Collects stack traces & logs"},
            {"id": "UNDERSTAND", "label": "Understand", "agent": "Context Agent", "desc": "Maps source code & AST"},
            {"id": "DIAGNOSE", "label": "Diagnose", "agent": "Diagnosis Agent", "desc": "Generates RCA JSON & hypothesis"},
            {"id": "REPAIR", "label": "Repair", "agent": "Plan Engine", "desc": "Generates multiple candidate diffs"},
            {"id": "SANDBOX", "label": "Sandbox", "agent": "Validation Agent", "desc": "Applies diffs in isolated sandbox"},
            {"id": "VALIDATE", "label": "Validate", "agent": "Scoring Engine", "desc": "Scores pass rate, safety, minimality"},
            {"id": "DEPLOY", "label": "Deploy", "agent": "Recovery Agent", "desc": "Human approval + patch deployment"},
            {"id": "REMEMBER", "label": "Remember", "agent": "Memory Agent", "desc": "Stores fix in Incident Memory"}
        ]
    }


# --- Backwards-Compatible Legacy Endpoints --------------------------------------------------

@app.post("/webhook/grafana", status_code=202)
async def grafana_webhook(payload: dict) -> dict:
    return await runner.enqueue(normalize.from_grafana(payload))


@app.post("/chat", status_code=202)
async def chat(payload: dict) -> dict:
    return await runner.enqueue(normalize.from_chat(payload))


@app.get("/runs")
def list_runs(limit: int = 50) -> list[dict]:
    return runner.list_runs(limit)


@app.get("/runs/{thread_id}")
def get_run(thread_id: str) -> dict:
    return runner.get_run(thread_id)


@app.get("/graph")
def system_graph() -> dict:
    from chaosmedic import graphview
    return graphview.build_system_graph()


@app.post("/runs/{thread_id}/approve", status_code=202)
async def approve_run(thread_id: str) -> dict:
    return await runner.enqueue_resume(thread_id, "approve")


@app.post("/runs/{thread_id}/reject", status_code=202)
async def reject_run(thread_id: str) -> dict:
    return await runner.enqueue_resume(thread_id, "reject")


# Mount static console frontend if present
_public_dir = Path(__file__).resolve().parent.parent.parent / "console" / "public"
if _public_dir.exists():
    app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="static")


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()

