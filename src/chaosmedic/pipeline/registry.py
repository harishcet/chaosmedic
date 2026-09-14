from __future__ import annotations

from collections.abc import Callable

from chaosmedic.graph.nodes.action import action_node
from chaosmedic.graph.nodes.rca import rca_node
from chaosmedic.graph.nodes.resolve import resolve_target_node
from chaosmedic.graph.nodes.validation import validation_node
from chaosmedic.graph.nodes.chaos_nodes import (
    detect_node,
    collect_node,
    diagnose_node,
    repair_node,
    sandbox_validate_node,
    deploy_node,
    remember_node,
)
from chaosmedic.graph.state import MachineState

# Named step implementations a pipeline node binds to via `step:` in config/pipeline.yaml.
STEP_REGISTRY: dict[str, Callable] = {
    # ChaosMedic 10-stage steps
    "detect": detect_node,
    "collect": collect_node,
    "diagnose": diagnose_node,
    "repair": repair_node,
    "sandbox_validate": sandbox_validate_node,
    "deploy": deploy_node,
    "remember": remember_node,

    # Backwards-compatible legacy steps
    "rca": rca_node,
    "resolve_target": resolve_target_node,
    "validation": validation_node,
    "action": action_node,
}


def _route_after_validation(state: MachineState) -> str:
    report = state.get("validation_report") or {}
    if report.get("passed") and state.get("remediation_plan"):
        return "action"
    if state.get("execution_status") == "failed":
        return "escalate"
    return "rca"


def _route_after_sandbox_validate(state: MachineState) -> str:
    """Route after sandbox validation: deploy if passed, repair retry if attempts < 3, else escalate."""
    res = state.get("sandbox_results") or {}
    if res.get("passed") and (state.get("selected_plan") or state.get("remediation_plan")):
        return "deploy"
    if state.get("execution_status") == "escalated" or state.get("repair_attempts", 0) >= 3:
        return "escalate"
    return "repair"


# Named routers a conditional edge binds to via `route:` in config/pipeline.yaml.
ROUTER_REGISTRY: dict[str, Callable] = {
    "after_validation": _route_after_validation,
    "after_sandbox_validate": _route_after_sandbox_validate,
}
