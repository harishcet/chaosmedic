from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class RemediationPlan(TypedDict, total=False):
    plan_id: str
    title: str
    summary: str
    target_repo: str
    repo_url: str
    host: str
    owner: str
    repo: str
    provider: str
    revision: str
    path: str
    file_path: str
    diff: str
    risk: str
    source: str
    patched_content: str
    strategy: str
    explanation: str
    ast_valid: bool


ExecutionStatus = Literal[
    "pending",
    "detecting",
    "collecting",
    "diagnosing",
    "repairing",
    "validating",
    "awaiting_approval",
    "approved",
    "rejected",
    "deploying",
    "recovered",
    "applied",
    "failed",
    "escalated",
]


class MachineState(TypedDict, total=False):
    # Pipeline metadata
    incident_id: str
    stage: str                                   # CONNECT, DETECT, COLLECT, UNDERSTAND, DIAGNOSE, REPAIR, SANDBOX, VALIDATE, DEPLOY, REMEMBER
    target_workspace: str

    # Alert & Context
    alert_payload: dict                          # Normalized input (HTTP 500, webhook, chat)
    context_data: dict                           # Gathered context / legacy MCP
    evidence: dict                               # Structured logs, traces, source files
    service_ref: dict                            # Resolved workload

    # Diagnosis & Plans
    hypothesis: Optional[str]                    # RCA conclusion text
    diagnosis: Optional[dict]                    # Structured RCA JSON
    candidate_plans: list[dict]                  # Multi-plan candidate diffs
    selected_plan: Optional[dict]                # Best scored candidate diff
    remediation_plan: Optional[RemediationPlan]  # Legacy plan alias

    # Sandbox & Validation
    validation_report: Optional[dict]            # Legacy validation skills output
    sandbox_results: Optional[dict]              # Real Pytest sandbox execution results

    # Deployment & Recovery
    deployment_result: Optional[dict]            # Deployment execution details
    recovery_result: Optional[dict]              # Recovery HTTP 200 verification
    memory_stored: bool

    # Execution control
    execution_status: ExecutionStatus
    pr_url: Optional[str]
    remediation_tool_calls: list
    rca_attempts: int                            # Legacy loop counter
    repair_attempts: int                         # Max 3 repair attempts before escalation

    # Chat / Reasoner stream
    messages: Annotated[list[AnyMessage], add_messages]
