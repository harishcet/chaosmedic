"""ChaosMedic 10-Stage Pipeline LangGraph Nodes.
Pipeline: CONNECT -> DETECT -> COLLECT -> UNDERSTAND -> DIAGNOSE -> REPAIR -> SANDBOX -> VALIDATE -> DEPLOY -> REMEMBER
"""
from __future__ import annotations

import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from chaosmedic import db
from chaosmedic.engine.detection import DetectionAgent
from chaosmedic.engine.evidence import EvidenceAgent
from chaosmedic.engine.diagnosis import DiagnosisAgent
from chaosmedic.engine.plan_engine import PlanEngine
from chaosmedic.engine.validation import ValidationAgent
from chaosmedic.engine.recovery import RecoveryAgent
from chaosmedic.engine.memory import MemoryAgent
from chaosmedic.graph.state import MachineState

logger = logging.getLogger(__name__)

# Single instances
_detection_agent = DetectionAgent()
_evidence_agent = EvidenceAgent()
_diagnosis_agent = DiagnosisAgent()
_plan_engine = PlanEngine()
_validation_agent = ValidationAgent()
_recovery_agent = RecoveryAgent()
_memory_agent = MemoryAgent()


def detect_node(state: MachineState) -> dict:
    """Stage: DETECT. Ingest and normalize failure signal."""
    raw = state.get("alert_payload", {})
    norm = _detection_agent.normalize_incident(raw)
    inc_id = state.get("incident_id") or norm.get("incident_id")

    msg = f"Detected incident {inc_id} [{norm.get('error_type')}]: {norm.get('title')}"
    logger.info(msg)

    # Persist initial incident
    db.create_incident({
        "incident_id": inc_id,
        "service": norm.get("service"),
        "error_type": norm.get("error_type"),
        "status": "detecting",
        "stage": "DETECT",
        "current_agent": "Detection Agent",
        "payload": norm
    })

    return {
        "incident_id": inc_id,
        "stage": "DETECT",
        "alert_payload": norm,
        "execution_status": "detecting",
        "repair_attempts": 0,
        "messages": [AIMessage(content=msg)],
    }


def collect_node(state: MachineState) -> dict:
    """Stage: COLLECT & UNDERSTAND. Collect logs, stack trace, and source code context."""
    alert = state.get("alert_payload", {})
    ws = state.get("target_workspace")
    evidence = _evidence_agent.collect_evidence(alert, target_workspace=ws)
    inc_id = state.get("incident_id", "unknown")

    files_found = list(evidence.get("source_files", {}).keys())
    msg = f"Collected evidence for {inc_id}: stack trace mapped to source files {files_found}"
    logger.info(msg)

    db.update_incident(inc_id, {
        "stage": "UNDERSTAND",
        "current_agent": "Evidence Agent",
        "evidence": evidence
    })

    return {
        "stage": "UNDERSTAND",
        "evidence": evidence,
        "context_data": {"source_files": files_found, "logs": evidence.get("logs")},
        "messages": [AIMessage(content=msg)],
    }


def diagnose_node(state: MachineState) -> dict:
    """Stage: DIAGNOSE. Root cause analysis outputting structured JSON."""
    evidence = state.get("evidence") or _evidence_agent.collect_evidence(state.get("alert_payload", {}))
    diagnosis = _diagnosis_agent.diagnose(evidence)
    inc_id = state.get("incident_id", "unknown")

    hypothesis = f"RCA Conclusion: {diagnosis.get('root_cause')} in {diagnosis.get('affected_file')}:{diagnosis.get('affected_function')}() [Confidence: {diagnosis.get('confidence')}]"
    logger.info(hypothesis)

    db.update_incident(inc_id, {
        "stage": "DIAGNOSE",
        "current_agent": "Diagnosis Agent",
        "diagnosis": diagnosis
    })

    return {
        "stage": "DIAGNOSE",
        "diagnosis": diagnosis,
        "hypothesis": hypothesis,
        "execution_status": "diagnosing",
        "messages": [AIMessage(content=hypothesis)],
    }


def repair_node(state: MachineState) -> dict:
    """Stage: REPAIR. Plan Engine generates MULTIPLE distinct candidate recovery plans."""
    evidence = state.get("evidence", {})
    diagnosis = state.get("diagnosis", {})
    attempts = state.get("repair_attempts", 0) + 1
    inc_id = state.get("incident_id", "unknown")

    plans = _plan_engine.generate_candidate_plans(evidence, diagnosis)
    plan_titles = [p.get("title") for p in plans]
    msg = f"Repair attempt {attempts}/3: Generated {len(plans)} candidate plans: {plan_titles}"
    logger.info(msg)

    db.update_incident(inc_id, {
        "stage": "REPAIR",
        "current_agent": "Plan Engine",
        "plans": plans
    })

    return {
        "stage": "REPAIR",
        "candidate_plans": plans,
        "repair_attempts": attempts,
        "execution_status": "repairing",
        "messages": [AIMessage(content=msg)],
    }


def sandbox_validate_node(state: MachineState) -> dict:
    """Stage: SANDBOX & VALIDATE. Runs candidate patches in isolated sandbox, scores them, selects safest."""
    plans = state.get("candidate_plans", [])
    ws = state.get("target_workspace", "")
    attempts = state.get("repair_attempts", 1)
    inc_id = state.get("incident_id", "unknown")

    val_result = _validation_agent.validate_plans(plans, ws)
    passed = val_result.get("passed", False)
    selected_plan = val_result.get("selected_plan")

    if passed and selected_plan:
        msg = f"Sandbox Validation PASSED for {inc_id} using {selected_plan.get('title')} (score: {val_result.get('best_score')}). Awaiting human approval."
        status = "awaiting_approval"
        stage = "VALIDATE"
    else:
        if attempts >= 3:
            msg = f"Sandbox Validation FAILED after {attempts} attempts. Escalating incident {inc_id} to human on-call."
            status = "escalated"
            stage = "ESCALATED"
        else:
            msg = f"Sandbox Validation failed on attempt {attempts}. Retrying repair generation..."
            status = "failed"
            stage = "VALIDATE"

    logger.info(msg)

    db.update_incident(inc_id, {
        "stage": stage,
        "status": status,
        "current_agent": "Validation Agent",
        "selected_plan": selected_plan,
        "sandbox_results": val_result
    })

    return {
        "stage": stage,
        "sandbox_results": val_result,
        "selected_plan": selected_plan,
        "remediation_plan": selected_plan, # legacy alias
        "validation_report": {"passed": passed, "summary": msg}, # legacy alias
        "execution_status": status,
        "messages": [AIMessage(content=msg)],
    }


def deploy_node(state: MachineState, config: RunnableConfig) -> dict:
    """Stage: DEPLOY. Runs only AFTER human approval (interrupt_before gate).
    Applies patch to target service and verifies HTTP 200 recovery."""
    selected_plan = state.get("selected_plan") or state.get("remediation_plan")
    ws = state.get("target_workspace", "")
    inc_id = state.get("incident_id", "unknown")
    health_url = (state.get("alert_payload") or {}).get("endpoint")

    if not selected_plan:
        msg = "Deployment failed: No approved plan found."
        return {"execution_status": "failed", "messages": [AIMessage(content=msg)]}

    dep_result = _recovery_agent.deploy_and_verify(ws, selected_plan, health_url=health_url)
    success = dep_result.get("success", False)
    recovered = dep_result.get("recovery_verified", False)

    status = "recovered" if success and recovered else ("deployed" if success else "failed")
    msg = f"Deployment executed for {inc_id}. Patch applied. Recovery verification: {'HTTP 200 OK' if recovered else 'Pending check'}."
    logger.info(msg)

    db.update_incident(inc_id, {
        "stage": "DEPLOY",
        "status": status,
        "current_agent": "Recovery Agent",
        "deployment": dep_result,
        "recovery": {"recovered": recovered}
    })

    return {
        "stage": "DEPLOY",
        "deployment_result": dep_result,
        "recovery_result": {"recovered": recovered},
        "execution_status": status,
        "messages": [AIMessage(content=msg)],
    }


def remember_node(state: MachineState) -> dict:
    """Stage: REMEMBER. Stores incident, root cause, patch, and recovery results in Incident Memory."""
    inc_id = state.get("incident_id", "unknown")
    memory_id = _memory_agent.remember_incident(dict(state))

    msg = f"Incident {inc_id} permanently recorded in Incident Memory as [{memory_id}]. Self-healing pipeline completed."
    logger.info(msg)

    db.update_incident(inc_id, {
        "stage": "REMEMBER",
        "status": "resolved",
        "current_agent": "Memory Agent"
    })

    return {
        "stage": "REMEMBER",
        "memory_stored": True,
        "execution_status": "recovered",
        "messages": [AIMessage(content=msg)],
    }
