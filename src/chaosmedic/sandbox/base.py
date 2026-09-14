"""Base Sandbox interface for isolated patch validation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSandbox(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the sandbox implementation."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this sandbox backend is available on the current host."""
        pass

    @abstractmethod
    def run_test_with_patch(
        self,
        target_workspace: str,
        rel_file_path: str,
        patched_code: str,
        test_command: str = "pytest",
        timeout: int = 30
    ) -> dict[str, Any]:
        """Apply patch to a temporary/isolated sandbox copy and run tests.
        
        Returns:
            dict containing:
                passed: bool
                tests_run: list[str]
                tests_passed: list[str]
                tests_failed: list[str]
                stdout: str
                stderr: str
                exit_code: int
                backend: str
                duration_ms: float
        """
        pass
