"""Zero-cost, dual SQLite / PostgreSQL persistence layer for ChaosMedic.

Defaults to a local SQLite database (zero external servers or credentials required),
while seamlessly supporting PostgreSQL if DATABASE_URL is configured.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from chaosmedic.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = os.environ.get("CHAOSMEDIC_DB_PATH", "chaosmedic.db")


def is_postgres() -> bool:
    url = get_settings().database_url or ""
    return url.startswith("postgres://") or url.startswith("postgresql://")


def get_sqlite_path() -> str:
    url = get_settings().database_url or ""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "")
    return DEFAULT_SQLITE_PATH


@contextmanager
def get_connection() -> Generator[Any, None, None]:
    if is_postgres():
        import psycopg
        conn = psycopg.connect(get_settings().database_url, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(get_sqlite_path())
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def ensure_schema() -> None:
    """Idempotently bootstrap the database schema for runs, incidents, and incident memory."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_postgres():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chaosmedic_runs (
                    thread_id text PRIMARY KEY,
                    status text NOT NULL,
                    summary jsonb,
                    pr_url text,
                    error text,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS chaosmedic_incidents (
                    incident_id text PRIMARY KEY,
                    thread_id text,
                    service text,
                    error_type text,
                    status text NOT NULL,
                    stage text NOT NULL,
                    current_agent text,
                    payload jsonb,
                    evidence jsonb,
                    diagnosis jsonb,
                    plans jsonb,
                    selected_plan jsonb,
                    sandbox_results jsonb,
                    deployment jsonb,
                    recovery jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS chaosmedic_memory (
                    memory_id text PRIMARY KEY,
                    incident_id text,
                    timestamp timestamptz NOT NULL DEFAULT now(),
                    service text,
                    error_signature text,
                    root_cause text,
                    patch text,
                    validation_results jsonb,
                    deployment_result jsonb,
                    recovery_result jsonb
                );
                CREATE TABLE IF NOT EXISTS opsgentic_runs (
                    thread_id text PRIMARY KEY,
                    status text NOT NULL,
                    summary jsonb,
                    pr_url text,
                    error text,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS opsgentic_pr_events (
                    comment_id text PRIMARY KEY,
                    pr_url text,
                    processed_at timestamptz NOT NULL DEFAULT now()
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chaosmedic_runs (
                    thread_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    summary TEXT,
                    pr_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chaosmedic_incidents (
                    incident_id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    service TEXT,
                    error_type TEXT,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    current_agent TEXT,
                    payload TEXT,
                    evidence TEXT,
                    diagnosis TEXT,
                    plans TEXT,
                    selected_plan TEXT,
                    sandbox_results TEXT,
                    deployment TEXT,
                    recovery TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chaosmedic_memory (
                    memory_id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    timestamp TEXT NOT NULL,
                    service TEXT,
                    error_signature TEXT,
                    root_cause TEXT,
                    patch TEXT,
                    validation_results TEXT,
                    deployment_result TEXT,
                    recovery_result TEXT
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opsgentic_runs (
                    thread_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    summary TEXT,
                    pr_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opsgentic_pr_events (
                    comment_id TEXT PRIMARY KEY,
                    pr_url TEXT,
                    processed_at TEXT NOT NULL
                );
            """)
    logger.info("ChaosMedic database schema verified (backend: %s)", "Postgres" if is_postgres() else "SQLite")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Incidents Store ------------------------------------------------------------------------

def create_incident(incident_data: dict) -> None:
    ensure_schema()
    ts = now_iso()
    with get_connection() as conn:
        cursor = conn.cursor()
        inc_id = incident_data.get("incident_id")
        thread_id = incident_data.get("thread_id")
        service = incident_data.get("service") or "unknown"
        error_type = incident_data.get("error_type") or "HTTP 500"
        status = incident_data.get("status") or "detected"
        stage = incident_data.get("stage") or "DETECT"
        agent = incident_data.get("current_agent") or "Detection Agent"
        payload = json.dumps(incident_data.get("payload") or {})
        evidence = json.dumps(incident_data.get("evidence") or {})
        diagnosis = json.dumps(incident_data.get("diagnosis") or {})
        plans = json.dumps(incident_data.get("plans") or [])
        sel_plan = json.dumps(incident_data.get("selected_plan") or {})
        sandbox = json.dumps(incident_data.get("sandbox_results") or {})
        deployment = json.dumps(incident_data.get("deployment") or {})
        recovery = json.dumps(incident_data.get("recovery") or {})

        if is_postgres():
            cursor.execute(
                """
                INSERT INTO chaosmedic_incidents 
                (incident_id, thread_id, service, error_type, status, stage, current_agent, payload, evidence, diagnosis, plans, selected_plan, sandbox_results, deployment, recovery, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    status = EXCLUDED.status, stage = EXCLUDED.stage, current_agent = EXCLUDED.current_agent,
                    payload = EXCLUDED.payload, evidence = EXCLUDED.evidence, diagnosis = EXCLUDED.diagnosis,
                    plans = EXCLUDED.plans, selected_plan = EXCLUDED.selected_plan, sandbox_results = EXCLUDED.sandbox_results,
                    deployment = EXCLUDED.deployment, recovery = EXCLUDED.recovery, updated_at = EXCLUDED.updated_at
                """,
                (inc_id, thread_id, service, error_type, status, stage, agent, payload, evidence, diagnosis, plans, sel_plan, sandbox, deployment, recovery, ts, ts)
            )
        else:
            cursor.execute(
                """
                INSERT INTO chaosmedic_incidents 
                (incident_id, thread_id, service, error_type, status, stage, current_agent, payload, evidence, diagnosis, plans, selected_plan, sandbox_results, deployment, recovery, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (incident_id) DO UPDATE SET
                    status = excluded.status, stage = excluded.stage, current_agent = excluded.current_agent,
                    payload = excluded.payload, evidence = excluded.evidence, diagnosis = excluded.diagnosis,
                    plans = excluded.plans, selected_plan = excluded.selected_plan, sandbox_results = excluded.sandbox_results,
                    deployment = excluded.deployment, recovery = excluded.recovery, updated_at = excluded.updated_at
                """,
                (inc_id, thread_id, service, error_type, status, stage, agent, payload, evidence, diagnosis, plans, sel_plan, sandbox, deployment, recovery, ts, ts)
            )


def update_incident(incident_id: str, updates: dict) -> None:
    ensure_schema()
    ts = now_iso()
    with get_connection() as conn:
        cursor = conn.cursor()
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
        fields.append("updated_at = ?")
        values.append(ts)
        values.append(incident_id)

        sql = f"UPDATE chaosmedic_incidents SET {', '.join(fields)} WHERE incident_id = ?"
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, tuple(values))


def get_incident(incident_id: str) -> Optional[dict]:
    ensure_schema()
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM chaosmedic_incidents WHERE incident_id = ?"
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, (incident_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _format_incident_row(row)


def list_incidents(limit: int = 50) -> list[dict]:
    ensure_schema()
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM chaosmedic_incidents ORDER BY created_at DESC LIMIT ?"
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()
        return [_format_incident_row(r) for r in rows]


def _format_incident_row(row: Any) -> dict:
    def _parse(val):
        if not val:
            return {}
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return val

    # Works with both sqlite3.Row and dict
    d = dict(row)
    for field in ("payload", "evidence", "diagnosis", "plans", "selected_plan", "sandbox_results", "deployment", "recovery"):
        d[field] = _parse(d.get(field))
    return d


# --- Incident Memory Store ------------------------------------------------------------------

def store_memory(memory_item: dict) -> str:
    ensure_schema()
    mid = memory_item.get("memory_id") or f"mem-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ts = memory_item.get("timestamp") or now_iso()
    with get_connection() as conn:
        cursor = conn.cursor()
        inc_id = memory_item.get("incident_id")
        service = memory_item.get("service")
        err_sig = memory_item.get("error_signature")
        root_cause = memory_item.get("root_cause")
        patch = memory_item.get("patch")
        validation = json.dumps(memory_item.get("validation_results") or {})
        deployment = json.dumps(memory_item.get("deployment_result") or {})
        recovery = json.dumps(memory_item.get("recovery_result") or {})

        sql = """
            INSERT INTO chaosmedic_memory
            (memory_id, incident_id, timestamp, service, error_signature, root_cause, patch, validation_results, deployment_result, recovery_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, (mid, inc_id, ts, service, err_sig, root_cause, patch, validation, deployment, recovery))
    return mid


def list_memory(limit: int = 50) -> list[dict]:
    ensure_schema()
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM chaosmedic_memory ORDER BY timestamp DESC LIMIT ?"
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for jf in ("validation_results", "deployment_result", "recovery_result"):
                if d.get(jf) and isinstance(d[jf], str):
                    try:
                        d[jf] = json.loads(d[jf])
                    except Exception:
                        pass
            result.append(d)
        return result


def find_memory_candidates(error_signature: str, service: Optional[str] = None) -> list[dict]:
    """Retrieve past candidate fixes from incident memory matching the error signature.
    Note: Retrieved memory fixes are CANDIDATES ONLY and MUST pass sandbox validation again before use."""
    ensure_schema()
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM chaosmedic_memory WHERE error_signature LIKE ? OR root_cause LIKE ? ORDER BY timestamp DESC LIMIT 5"
        param1 = f"%{error_signature}%"
        if is_postgres():
            sql = sql.replace("?", "%s")
        cursor.execute(sql, (param1, param1))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for jf in ("validation_results", "deployment_result", "recovery_result"):
                if d.get(jf) and isinstance(d[jf], str):
                    try:
                        d[jf] = json.loads(d[jf])
                    except Exception:
                        pass
            result.append(d)
        return result
