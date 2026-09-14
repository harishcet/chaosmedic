"""Memory Agent: stores incident, root cause, patch, test results, recovery result.
Fixes retrieved from memory are CANDIDATES ONLY and MUST pass sandbox validation again before use."""
from __future__ import annotations

import logging
import time
from typing import Optional
from chaosmedic import db

logger = logging.getLogger(__name__)


class MemoryAgent:
    def remember_incident(self, incident_state: dict) -> str:
        incident_id = incident_state.get("incident_id")
        diagnosis = incident_state.get("diagnosis") or {}
        selected_plan = incident_state.get("selected_plan") or {}
        sandbox_results = incident_state.get("sandbox_results") or {}
        deployment = incident_state.get("deployment_result") or {}
        recovery = incident_state.get("recovery_result") or {}

        memory_item = {
            "incident_id": incident_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "service": incident_state.get("service") or "target-service",
            "error_signature": diagnosis.get("root_cause") or "HTTP 500",
            "root_cause": diagnosis.get("root_cause"),
            "patch": selected_plan.get("diff"),
            "validation_results": sandbox_results,
            "deployment_result": deployment,
            "recovery_result": recovery
        }

        memory_id = db.store_memory(memory_item)
        logger.info("Stored incident in memory as %s", memory_id)
        return memory_id

    def recall_candidates(self, error_signature: str) -> list[dict]:
        """Candidate retrieval: past fixes are candidates only and must re-pass validation."""
        return db.find_memory_candidates(error_signature)
