"""Evidence / Context Agent: collects logs, stack traces, source files, and recent git history."""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)


class EvidenceAgent:
    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path

    def collect_evidence(self, alert_payload: dict, target_workspace: Optional[str] = None) -> dict:
        ws = target_workspace or self.workspace_path or os.getcwd()
        stack_trace = alert_payload.get("stack_trace") or ""
        logs = alert_payload.get("logs") or []
        if isinstance(logs, str):
            logs = [logs]

        # Extract file and line hints from stack trace or payload
        affected_files = self._extract_files_from_trace(stack_trace, ws)
        source_context = {}
        for rel_path, abs_path in affected_files.items():
            try:
                if os.path.exists(abs_path):
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        source_context[rel_path] = f.read()
            except Exception as e:
                logger.warning("Could not read file %s: %s", abs_path, e)

        return {
            "incident_id": alert_payload.get("incident_id"),
            "service": alert_payload.get("service", "unknown"),
            "endpoint": alert_payload.get("endpoint", ""),
            "status_code": alert_payload.get("status_code", 500),
            "stack_trace": stack_trace,
            "logs": logs,
            "source_files": source_context,
            "workspace_path": ws,
            "environment": {
                "python_version": "3.13",
                "os": os.name
            }
        }

    def _extract_files_from_trace(self, stack_trace: str, workspace: str) -> dict[str, str]:
        files = {}
        if not stack_trace:
            # Fallback: scan workspace for main python files
            if os.path.exists(workspace):
                for root, _, fs in os.walk(workspace):
                    for f in fs:
                        if f.endswith(".py") and not f.startswith("test_") and f != "setup.py":
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, workspace)
                            files[rel] = full
            return files

        # Python stack trace file regex: File "path", line X, in Y
        matches = re.findall(r'File "([^"]+)", line (\d+)', stack_trace)
        for fpath, _ in matches:
            cand1 = fpath if os.path.isabs(fpath) else os.path.join(workspace, fpath)
            if os.path.exists(cand1):
                rel = os.path.relpath(cand1, workspace)
                files[rel] = cand1
                continue

            if os.path.exists(fpath):
                rel = os.path.relpath(fpath, workspace) if workspace in fpath else os.path.basename(fpath)
                files[rel] = fpath
                continue

            # Search workspace for matching basename
            base = os.path.basename(fpath)
            for root, _, fs in os.walk(workspace):
                if base in fs:
                    full = os.path.join(root, base)
                    rel = os.path.relpath(full, workspace)
                    files[rel] = full
                    break

        return files
