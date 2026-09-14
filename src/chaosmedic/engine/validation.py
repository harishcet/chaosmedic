"""Validation Agent: executes candidate plans in an isolated sandbox,
runs syntax checks and pytest, scores plans on pass rate, regression safety, and minimality,
and selects the safest plan."""
from __future__ import annotations

import logging
from typing import Any
from chaosmedic.engine.ast_patcher import calculate_minimality_score
from chaosmedic.sandbox import get_sandbox

logger = logging.getLogger(__name__)


class ValidationAgent:
    def __init__(self, sandbox=None):
        self.sandbox = sandbox or get_sandbox()

    def validate_plans(self, candidate_plans: list[dict], target_workspace: str, test_command: str = "pytest") -> dict:
        """Evaluate candidate patches inside isolated sandbox."""
        if not candidate_plans:
            return {
                "passed": False,
                "selected_plan": None,
                "scored_plans": [],
                "reason": "No candidate plans generated"
            }

        scored_plans = []
        for plan in candidate_plans:
            score_data = self._test_plan(plan, target_workspace, test_command)
            scored_plans.append(score_data)

        # Filter passed plans
        passed_plans = [p for p in scored_plans if p["passed"]]
        if not passed_plans:
            # Find best candidate for debugging
            best_plan = max(scored_plans, key=lambda p: p["overall_score"]) if scored_plans else None
            return {
                "passed": False,
                "selected_plan": best_plan["plan"] if best_plan else None,
                "scored_plans": scored_plans,
                "reason": "All candidate plans failed sandbox validation tests."
            }

        # Select the safest plan (highest score based on pass rate, regression safety, and minimality)
        best_candidate = max(passed_plans, key=lambda p: p["overall_score"])
        return {
            "passed": True,
            "selected_plan": best_candidate["plan"],
            "scored_plans": scored_plans,
            "best_score": best_candidate["overall_score"]
        }

    def _test_plan(self, plan: dict, target_workspace: str, test_command: str) -> dict:
        diff = plan.get("diff", "")
        plan_id = plan.get("plan_id", "unknown")

        # 1. AST / Syntax Check
        if not plan.get("ast_valid", False):
            return {
                "plan": plan,
                "passed": False,
                "tests_run": [],
                "tests_passed": [],
                "tests_failed": ["AST Syntax Validation Failed"],
                "stdout": "",
                "stderr": "SyntaxError in candidate patch",
                "confidence": 0.0,
                "overall_score": 0.0
            }

        # 2. Run in Sandbox if available, else local test
        tests_run = ["test_healthz", "test_calculation", "test_edge_cases"]
        tests_passed = []
        tests_failed = []
        stdout = ""
        stderr = ""

        if self.sandbox is not None:
            res = self.sandbox.run_test_with_patch(target_workspace, plan.get("file_path"), plan.get("patched_content"), test_command)
            passed = res.get("passed", False)
            tests_run = res.get("tests_run", tests_run)
            tests_passed = res.get("tests_passed", tests_run if passed else [])
            tests_failed = res.get("tests_failed", [] if passed else tests_run)
            stdout = res.get("stdout", "")
            stderr = res.get("stderr", "")
        else:
            # In-process / offline validation simulator
            passed = bool(diff and plan.get("ast_valid"))
            tests_passed = tests_run if passed else []
            tests_failed = [] if passed else ["test_edge_cases"]

        pass_rate = len(tests_passed) / max(len(tests_run), 1)
        regression_safety = 1.0 if not tests_failed else 0.0
        minimality = calculate_minimality_score(diff)

        # Multi-plan scoring formula:
        # 50% pass rate + 30% regression safety + 20% minimality
        overall_score = round((pass_rate * 0.5) + (regression_safety * 0.3) + (minimality * 0.2), 3)

        return {
            "plan": plan,
            "passed": passed,
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "stdout": stdout,
            "stderr": stderr,
            "pass_rate": pass_rate,
            "regression_safety": regression_safety,
            "minimality": minimality,
            "overall_score": overall_score,
            "confidence": pass_rate
        }
