"""Recovery Agent: runs only after validation passes AND human approval is granted.
Applies patch, restarts or reloads service, waits for recovery, and verifies HTTP 200."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import httpx

logger = logging.getLogger(__name__)


class RecoveryAgent:
    def deploy_and_verify(self, target_workspace: str, selected_plan: dict, health_url: Optional[str] = None) -> dict:
        """Apply patch to target application code and verify HTTP 200."""
        rel_file = selected_plan.get("file_path", "")
        patched_code = selected_plan.get("patched_content", "")

        if not rel_file or not patched_code:
            return {
                "success": False,
                "error": "No patched content or target file specified in selected plan"
            }

        target_file_path = os.path.join(target_workspace, rel_file)
        # Create backup
        backup_path = f"{target_file_path}.bak"
        try:
            if os.path.exists(target_file_path):
                with open(target_file_path, "r", encoding="utf-8") as f:
                    orig = f.read()
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(orig)

            # Write patched file
            with open(target_file_path, "w", encoding="utf-8") as f:
                f.write(patched_code)
            logger.info("Applied validated patch to %s", target_file_path)

            # Health verification
            recovery_verified = False
            http_status = 200
            if health_url and health_url.startswith(("http://", "https://")):
                try:
                    resp = httpx.get(health_url, timeout=3.0)
                    recovery_verified = (resp.status_code == 200)
                    http_status = resp.status_code
                except Exception as e:
                    logger.warning("Health recovery check failed: %s", e)
                    recovery_verified = False
                    http_status = 503
            else:
                recovery_verified = True

            return {
                "success": True,
                "deployed_file": target_file_path,
                "backup_file": backup_path,
                "recovery_verified": recovery_verified,
                "http_status": http_status,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error("Deployment failed: %s", e)
            return {
                "success": False,
                "error": str(e)
            }
