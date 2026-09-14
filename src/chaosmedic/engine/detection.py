"""Detection Agent: polls target endpoints with backoff, normalizes incidents, never hammers services."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)


class DetectionAgent:
    def __init__(self, check_interval: float = 5.0, max_backoff: float = 60.0):
        self.check_interval = check_interval
        self.max_backoff = max_backoff
        self._current_interval = check_interval

    def normalize_incident(self, raw_alert: dict) -> dict:
        """Normalize failure signals from webhooks, health checks, or logs."""
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        title = raw_alert.get("title") or raw_alert.get("error") or "Service Failure"
        service = raw_alert.get("service") or raw_alert.get("app") or "target-service"
        status_code = raw_alert.get("status_code") or raw_alert.get("code") or 500
        stack_trace = raw_alert.get("stack_trace") or raw_alert.get("traceback") or ""
        endpoint = raw_alert.get("endpoint") or raw_alert.get("url") or "/api"

        return {
            "incident_id": incident_id,
            "title": title,
            "service": service,
            "error_type": f"HTTP {status_code}" if isinstance(status_code, int) else str(status_code),
            "status_code": status_code,
            "endpoint": endpoint,
            "stack_trace": stack_trace,
            "timestamp": time.time(),
            "raw": raw_alert,
            "labels": raw_alert.get("labels", {}),
            "severity": "critical" if status_code in (500, 502, 503, 504) else "high"
        }

    async def poll_endpoint(self, url: str, timeout: float = 3.0) -> Optional[dict]:
        """Safely probe endpoint with backoff on failure."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, timeout=timeout)
                if resp.status_code >= 500:
                    self._current_interval = min(self._current_interval * 1.5, self.max_backoff)
                    return self.normalize_incident({
                        "title": f"HTTP {resp.status_code} on {url}",
                        "status_code": resp.status_code,
                        "endpoint": url,
                        "body": resp.text[:500]
                    })
                # Reset interval on recovery
                self._current_interval = self.check_interval
                return None
            except httpx.RequestError as exc:
                self._current_interval = min(self._current_interval * 1.5, self.max_backoff)
                return self.normalize_incident({
                    "title": f"Connection Failure on {url}: {exc}",
                    "status_code": 503,
                    "endpoint": url,
                    "error": str(exc)
                })
