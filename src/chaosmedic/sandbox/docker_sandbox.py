"""Docker Sandbox: runs isolated patch tests in Docker container when daemon is available."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any

from chaosmedic.sandbox.base import BaseSandbox
from chaosmedic.sandbox.subprocess_sandbox import SubprocessSandbox

logger = logging.getLogger(__name__)


class DockerSandbox(BaseSandbox):
    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self._fallback = SubprocessSandbox()

    @property
    def name(self) -> str:
        return "docker_container"

    def is_available(self) -> bool:
        """Check if Docker CLI and daemon are operational."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_test_with_patch(
        self,
        target_workspace: str,
        rel_file_path: str,
        patched_code: str,
        test_command: str = "pytest",
        timeout: int = 30
    ) -> dict[str, Any]:
        if not self.is_available():
            logger.info("Docker daemon not available; delegating to SubprocessSandbox fallback.")
            return self._fallback.run_test_with_patch(
                target_workspace, rel_file_path, patched_code, test_command, timeout
            )

        start_time = time.time()
        with tempfile.TemporaryDirectory(prefix="chaosmedic_docker_ws_") as temp_ws:
            # Copy workspace
            self._fallback._copy_workspace(target_workspace, temp_ws)
            if rel_file_path and patched_code:
                sandbox_file = os.path.join(temp_ws, rel_file_path)
                os.makedirs(os.path.dirname(sandbox_file), exist_ok=True)
                with open(sandbox_file, "w", encoding="utf-8") as f:
                    f.write(patched_code)

            # Run in ephemeral container
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{temp_ws}:/app",
                "-w", "/app",
                "--network", "none",  # complete isolation from network
                self.image,
                "sh", "-c", f"pip install -q pytest && {test_command}"
            ]

            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                stdout = ""
                stderr = f"Docker test execution timed out after {timeout}s."
                exit_code = 124
            except Exception as e:
                stdout = ""
                stderr = f"Docker execution error: {e}"
                exit_code = 1

            duration_ms = round((time.time() - start_time) * 1000, 2)
            passed, tests_run, tests_passed, tests_failed = self._fallback._parse_pytest_output(stdout, stderr, exit_code)

            return {
                "passed": passed,
                "tests_run": tests_run,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "backend": self.name,
                "duration_ms": duration_ms
            }
