"""ChaosMedic Orchestrator: manages 10-stage LangGraph execution, checkpointing, and approval resumption."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver

from chaosmedic import db
from chaosmedic.config import get_settings
from chaosmedic.graph.builder import build_app
from chaosmedic.pipeline.spec import load_spec_file

logger = logging.getLogger(__name__)

# Global compiled app
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_SPEC_PATH = os.path.join(_ROOT, "config", "chaosmedic_pipeline.yaml")
_checkpointer = MemorySaver()
_spec = load_spec_file(_SPEC_PATH) if os.path.exists(_SPEC_PATH) else None
_app = build_app(_checkpointer, spec=_spec) if _spec else None

# In-memory thread -> incident mapping
_incident_threads: dict[str, str] = {}
_thread_incidents: dict[str, str] = {}


def get_app():
    global _app, _checkpointer
    if _app is None:
        spec = load_spec_file(_SPEC_PATH)
        _app = build_app(_checkpointer, spec=spec)
    return _app


def run_incident_pipeline(alert_payload: dict, target_workspace: Optional[str] = None, incident_id: Optional[str] = None) -> dict:
    """Run the 10-stage pipeline synchronously up to the approval gate or completion."""
    app = get_app()
    inc_id = incident_id or alert_payload.get("incident_id") or f"inc-{uuid.uuid4().hex[:8]}"
    thread_id = str(uuid.uuid4())
    _incident_threads[inc_id] = thread_id
    _thread_incidents[thread_id] = inc_id

    ws = target_workspace or alert_payload.get("target_workspace") or os.getcwd()

    initial_state = {
        "incident_id": inc_id,
        "alert_payload": alert_payload,
        "target_workspace": ws,
        "service_ref": {"name": alert_payload.get("service", "target-app")},
        "repair_attempts": 0
    }

    config = {"configurable": {"thread_id": thread_id}}
    logger.info("Starting ChaosMedic incident pipeline for %s (thread: %s)", inc_id, thread_id)

    # Initial DB record
    db.create_incident({
        "incident_id": inc_id,
        "thread_id": thread_id,
        "service": alert_payload.get("service", "target-app"),
        "error_type": alert_payload.get("error_type") or f"HTTP {alert_payload.get('status_code', 500)}",
        "status": "detecting",
        "stage": "DETECT",
        "payload": alert_payload
    })

    try:
        final_state = app.invoke(initial_state, config=config)
        return {
            "incident_id": inc_id,
            "thread_id": thread_id,
            "stage": final_state.get("stage", "DONE"),
            "status": final_state.get("execution_status", "completed"),
            "awaiting_approval": final_state.get("execution_status") == "awaiting_approval",
            "state": final_state
        }
    except Exception as e:
        logger.error("Error executing incident pipeline: %s", e)
        db.update_incident(inc_id, {"status": "failed", "stage": "FAILED"})
        return {
            "incident_id": inc_id,
            "thread_id": thread_id,
            "status": "failed",
            "error": str(e)
        }


def resume_incident_pipeline(incident_id: str, action: str = "approve") -> dict:
    """Resume execution from the approval gate."""
    app = get_app()
    thread_id = _incident_threads.get(incident_id)

    if not thread_id:
        inc = db.get_incident(incident_id)
        if inc and inc.get("thread_id"):
            thread_id = inc.get("thread_id")
            _incident_threads[incident_id] = thread_id

    if not thread_id:
        return {"success": False, "error": f"Active thread for incident {incident_id} not found."}

    config = {"configurable": {"thread_id": thread_id}}

    if action == "approve":
        logger.info("Resuming approved pipeline for incident %s", incident_id)
        db.update_incident(incident_id, {"status": "approved", "stage": "DEPLOY"})
        final_state = app.invoke(None, config=config)
        return {
            "success": True,
            "incident_id": incident_id,
            "stage": final_state.get("stage"),
            "status": final_state.get("execution_status"),
            "state": final_state
        }
    else:
        logger.info("Rejecting candidate patch for incident %s", incident_id)
        db.update_incident(incident_id, {"status": "rejected", "stage": "REJECTED"})
        return {
            "success": True,
            "incident_id": incident_id,
            "status": "rejected"
        }
