"""Sandbox factory: selects Docker if available, otherwise falls back to SubprocessSandbox."""
from __future__ import annotations

import logging
from chaosmedic.sandbox.base import BaseSandbox
from chaosmedic.sandbox.docker_sandbox import DockerSandbox
from chaosmedic.sandbox.subprocess_sandbox import SubprocessSandbox

logger = logging.getLogger(__name__)

_active_sandbox: BaseSandbox | None = None


def get_sandbox() -> BaseSandbox:
    global _active_sandbox
    if _active_sandbox is not None:
        return _active_sandbox

    docker = DockerSandbox()
    if docker.is_available():
        logger.info("Docker daemon detected: using DockerSandbox backend.")
        _active_sandbox = docker
    else:
        logger.info("Docker daemon not detected: using SubprocessSandbox (free-tier fallback).")
        _active_sandbox = SubprocessSandbox()

    return _active_sandbox
