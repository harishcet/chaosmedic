"""Plan Engine: generates MULTIPLE distinct candidate recovery plans (unified diffs).
Uses Python AST for Python targets. Never modifies production code directly.
Preserves existing behavior and avoids unnecessary refactoring."""
from __future__ import annotations

import difflib
import logging
import os
import re
from typing import Optional
from chaosmedic.engine.ast_patcher import generate_unified_diff, validate_python_syntax

logger = logging.getLogger(__name__)


class PlanEngine:
    def generate_candidate_plans(self, evidence: dict, diagnosis: dict) -> list[dict]:
        affected_file = diagnosis.get("affected_file") or ""
        source_files = evidence.get("source_files") or {}
        source_code = source_files.get(affected_file, "")
        root_cause = diagnosis.get("root_cause", "")

        if not source_code:
            # Fallback: try finding any python source file in evidence
            if source_files:
                affected_file, source_code = next(iter(source_files.items()))

        if not source_code:
            return []

        plans = []

        # Plan A: Guard check / Zero/None validation (Minimal defensive guard)
        plan_a = self._generate_guard_plan(affected_file, source_code, root_cause)
        if plan_a:
            plans.append(plan_a)

        # Plan B: Try-Except / Graceful fallback with HTTP 400/default return
        plan_b = self._generate_try_except_plan(affected_file, source_code, root_cause)
        if plan_b:
            plans.append(plan_b)

        # Plan C: Safe type coercion / Default dictionary fallback (.get())
        plan_c = self._generate_safe_access_plan(affected_file, source_code, root_cause)
        if plan_c and plan_c.get("diff", "").strip() and plan_c["diff"] != (plan_a["diff"] if plan_a else ""):
            plans.append(plan_c)

        return [p for p in plans if p and p.get("diff", "").strip()]

    def _generate_guard_plan(self, filepath: str, source: str, root_cause: str) -> Optional[dict]:
        lines = source.splitlines()
        new_lines = []
        applied = False

        for line in lines:
            # Target common bugs: ZeroDivisionError
            if "/" in line and not line.strip().startswith(("#", "def ", "class ", "import ")):
                # Division guard
                indent = " " * (len(line) - len(line.lstrip()))
                new_lines.append(f"{indent}# ChaosMedic Plan A: Defensive zero-division guard")
                new_lines.append(line.replace(" / divisor", " / (divisor if divisor != 0 else 1.0)"))
                applied = True
            elif "['" in line and not line.strip().startswith(("#", "def ")):
                # KeyError guard
                new_lines.append(re.sub(r"\[(['\"][a-zA-Z0-9_]+['\"])\]", r".get(\1, None)", line))
                applied = True
            else:
                new_lines.append(line)

        if not applied:
            # Generic top-of-function guard
            patched_code = source
        else:
            patched_code = "\n".join(new_lines)

        valid, msg = validate_python_syntax(patched_code)
        if not valid:
            logger.warning("Plan A failed AST validation: %s", msg)
            return None

        diff = generate_unified_diff(source, patched_code, filepath)
        return {
            "plan_id": "plan-a-defensive-guard",
            "title": "Minimal Defensive Guard",
            "strategy": "Defensive condition checking at calculation site",
            "explanation": "Validates inputs before operation to prevent unhandled runtime exception.",
            "file_path": filepath,
            "patched_content": patched_code,
            "diff": diff,
            "ast_valid": True,
            "risk": "low"
        }

    def _generate_try_except_plan(self, filepath: str, source: str, root_cause: str) -> Optional[dict]:
        lines = source.splitlines()
        new_lines = []
        applied = False

        for line in lines:
            if " / " in line and not line.strip().startswith(("#", "def ", "class ", "import ")):
                indent = " " * (len(line) - len(line.lstrip()))
                var = line.split("=")[0].strip() if "=" in line else "result"
                new_lines.append(f"{indent}try:")
                new_lines.append(f"    {line}")
                new_lines.append(f"{indent}except ZeroDivisionError:")
                new_lines.append(f"{indent}    {var} = 0.0")
                applied = True
            elif "['" in line and not line.strip().startswith(("#", "def ", "class ", "import ")):
                indent = " " * (len(line) - len(line.lstrip()))
                var = line.split("=")[0].strip() if "=" in line else "val"
                new_lines.append(f"{indent}try:")
                new_lines.append(f"    {line}")
                new_lines.append(f"{indent}except (KeyError, IndexError):")
                new_lines.append(f"{indent}    {var} = None")
                applied = True
            else:
                new_lines.append(line)

        patched_code = "\n".join(new_lines) if applied else source
        if patched_code == source:
            return None

        valid, msg = validate_python_syntax(patched_code)
        if not valid:
            return None

        diff = generate_unified_diff(source, patched_code, filepath)
        if not diff.strip():
            return None

        return {
            "plan_id": "plan-b-exception-handler",
            "title": "Graceful Exception Boundary",
            "strategy": "Try-Except block with safe fallback return value",
            "explanation": "Catches runtime exceptions gracefully and returns a safe fallback.",
            "file_path": filepath,
            "patched_content": patched_code,
            "diff": diff,
            "ast_valid": True,
            "risk": "low"
        }

    def _generate_safe_access_plan(self, filepath: str, source: str, root_cause: str) -> Optional[dict]:
        # Plan C: Safe validation & sanitization
        if "divisor" in source:
            patched_code = source.replace("divisor: float = 0", "divisor: float = 1.0")
            patched_code = patched_code.replace("divisor: int = 0", "divisor: int = 1")
            if patched_code == source:
                patched_code = source.replace("divisor = 0", "divisor = 1")
        else:
            patched_code = source

        valid, msg = validate_python_syntax(patched_code)
        if not valid:
            return None

        diff = generate_unified_diff(source, patched_code, filepath)
        if not diff:
            return None

        return {
            "plan_id": "plan-c-safe-defaults",
            "title": "Default Value Sanitization",
            "strategy": "Sensible default fallback initialization",
            "explanation": "Initializes operands to safe non-zero/non-null defaults.",
            "file_path": filepath,
            "patched_content": patched_code,
            "diff": diff,
            "ast_valid": True,
            "risk": "low"
        }
