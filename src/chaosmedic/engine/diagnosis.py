"""Diagnosis (RCA) Agent: analyzes evidence and outputs strictly structured JSON.
Never hallucinates files or evidence. If insufficient, marks incident for human investigation."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional
from chaosmedic.agents.llm import get_llm

logger = logging.getLogger(__name__)


class DiagnosisAgent:
    def diagnose(self, evidence: dict) -> dict:
        stack_trace = evidence.get("stack_trace", "")
        source_files = evidence.get("source_files", {})
        logs = evidence.get("logs", [])

        # Check if LLM is configured
        llm = get_llm()
        if llm is not None:
            return self._diagnose_with_llm(llm, evidence)

        # Free-tier deterministic AST / Stack-trace analyzer fallback
        return self._deterministic_diagnose(evidence)

    def _deterministic_diagnose(self, evidence: dict) -> dict:
        stack_trace = evidence.get("stack_trace", "")
        source_files = evidence.get("source_files", {})
        logs = "\n".join(evidence.get("logs", []))

        affected_file = ""
        affected_function = "unknown"
        error_name = "InternalServerError"
        error_msg = "Unhandled exception resulting in HTTP 500"

        # Parse python traceback
        if stack_trace:
            trace_lines = [l.strip() for l in stack_trace.strip().splitlines() if l.strip()]
            for line in reversed(trace_lines):
                m = re.match(r'([A-Za-z0-9_]*(?:Error|Exception)):?\s*(.*)', line)
                if m:
                    error_name = m.group(1).strip()
                    error_msg = m.group(2).strip() or "Unhandled exception"
                    break
                elif ":" in line and not line.startswith("File "):
                    error_name, _, error_msg = line.partition(":")
                    error_name = error_name.strip()
                    error_msg = error_msg.strip()
                    break

            # Find affected file and function
            func_matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', stack_trace)
            if func_matches:
                fpath, _, func = func_matches[-1]
                affected_file = list(source_files.keys())[0] if source_files else os.path.basename(fpath)
                affected_function = func
        elif source_files:
            affected_file = list(source_files.keys())[0]

        if not affected_file and not source_files:
            return {
                "root_cause": "Insufficient evidence: no source files or stack trace located",
                "affected_file": "",
                "affected_function": "",
                "confidence": 0.2,
                "evidence": ["HTTP 500 received without source code mapping"],
                "severity": "high",
                "recommended_action": "Mark incident for manual human investigation."
            }

        root_cause = f"{error_name}: {error_msg}" if error_msg else f"Application error in {affected_function}()"
        confidence = 0.95 if stack_trace and affected_file else 0.75

        return {
            "root_cause": root_cause,
            "affected_file": affected_file,
            "affected_function": affected_function,
            "confidence": confidence,
            "evidence": [
                f"Exception type: {error_name}",
                f"Message: {error_msg}",
                f"Target file: {affected_file}",
                f"Scope: {affected_function}"
            ],
            "severity": "critical" if "ZeroDivision" in error_name or "Connection" in error_name or "KeyError" in error_name else "high",
            "recommended_action": f"Apply AST-aware patch to {affected_file} around {affected_function}() to guard against {error_name}."
        }

    def _diagnose_with_llm(self, llm, evidence: dict) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage
        prompt = (
            f"Incident Evidence:\n"
            f"Service: {evidence.get('service')}\n"
            f"Endpoint: {evidence.get('endpoint')}\n"
            f"Stack Trace:\n{evidence.get('stack_trace')}\n\n"
            f"Source Files available: {list(evidence.get('source_files', {}).keys())}\n\n"
            "Analyze this evidence and output ONLY valid JSON with fields:\n"
            '{"root_cause": str, "affected_file": str, "affected_function": str, "confidence": float, "evidence": list[str], "severity": str, "recommended_action": str}\n'
            "Never hallucinate files. If evidence is insufficient, state it clearly."
        )
        try:
            resp = llm.invoke([
                SystemMessage(content="You are an expert SRE Root Cause Analysis agent. Output strictly structured JSON."),
                HumanMessage(content=prompt)
            ])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            # clean json tags
            clean = re.sub(r"^```(json)?", "", text.strip(), flags=re.MULTILINE).replace("```", "").strip()
            return json.loads(clean)
        except Exception as e:
            logger.warning("LLM diagnosis failed, using deterministic fallback: %s", e)
            return self._deterministic_diagnose(evidence)
