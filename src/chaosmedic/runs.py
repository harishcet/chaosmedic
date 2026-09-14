from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from chaosmedic import db

_COLS = "thread_id, status, summary, pr_url, error, created_at, updated_at"


def ensure_schema() -> None:
    db.ensure_schema()


def _summary_from_alert(alert: dict) -> dict:
    """Initial row summary from the trigger (known at enqueue, before resolution)."""
    alert = alert or {}
    labels = alert.get("labels") or {}
    return {
        "title": alert.get("title"),
        "source": alert.get("source"),
        "severity": alert.get("severity"),
        "namespace": labels.get("namespace"),
        "service": labels.get("app") or labels.get("workload") or labels.get("deployment") or alert.get("service"),
        "repo": None,
    }


def _row(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    summary = d.get("summary")
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            pass
    return {
        "thread_id": d.get("thread_id"),
        "status": d.get("status"),
        "summary": summary or {},
        "pr_url": d.get("pr_url"),
        "error": d.get("error"),
        "created_at": str(d.get("created_at")),
        "updated_at": str(d.get("updated_at")),
    }


def create(thread_id: str, alert: dict, status: str = "queued") -> None:
    ensure_schema()
    ts = datetime.now(timezone.utc).isoformat()
    summary = _summary_from_alert(alert)
    with db.get_connection() as conn:
        c = conn.cursor()
        if db.is_postgres():
            from psycopg.types.json import Jsonb
            c.execute(
                "INSERT INTO chaosmedic_runs (thread_id, status, summary, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (thread_id) DO UPDATE SET status = EXCLUDED.status, "
                "summary = EXCLUDED.summary, updated_at = EXCLUDED.updated_at",
                (thread_id, status, Jsonb(summary), ts, ts),
            )
        else:
            c.execute(
                "INSERT INTO chaosmedic_runs (thread_id, status, summary, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (thread_id) DO UPDATE SET status = excluded.status, "
                "summary = excluded.summary, updated_at = excluded.updated_at",
                (thread_id, status, json.dumps(summary), ts, ts),
            )


def set_status(thread_id: str, status: str, *, pr_url: Optional[str] = None, error: Optional[str] = None) -> None:
    ensure_schema()
    ts = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = "UPDATE chaosmedic_runs SET status = ?, pr_url = COALESCE(?, pr_url), error = COALESCE(?, error), updated_at = ? WHERE thread_id = ?"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        c.execute(sql, (status, pr_url, error, ts, thread_id))


def set_summary(thread_id: str, extra: dict) -> None:
    """Merge non-null fields into the row summary (e.g. resolved service/repo after the run)."""
    extra = {k: v for k, v in (extra or {}).items() if v is not None}
    if not extra:
        return
    ensure_schema()
    run = get(thread_id) or {}
    merged = {**(run.get("summary") or {}), **extra}
    ts = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        c = conn.cursor()
        if db.is_postgres():
            from psycopg.types.json import Jsonb
            c.execute(
                "UPDATE chaosmedic_runs SET summary = %s, updated_at = %s WHERE thread_id = %s",
                (Jsonb(merged), ts, thread_id),
            )
        else:
            c.execute(
                "UPDATE chaosmedic_runs SET summary = ?, updated_at = ? WHERE thread_id = ?",
                (json.dumps(merged), ts, thread_id),
            )


def list_recent(limit: int = 50) -> list[dict]:
    ensure_schema()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = f"SELECT {_COLS} FROM chaosmedic_runs ORDER BY updated_at DESC LIMIT ?"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        c.execute(sql, (limit,))
        rows = c.fetchall()
    return [_row(r) for r in rows]


def get(thread_id: str) -> Optional[dict]:
    ensure_schema()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = f"SELECT {_COLS} FROM chaosmedic_runs WHERE thread_id = ?"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        c.execute(sql, (thread_id,))
        row = c.fetchone()
    return _row(row) if row else None


def get_by_pr_url(pr_url: str) -> Optional[dict]:
    if not pr_url:
        return None
    ensure_schema()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = f"SELECT {_COLS} FROM chaosmedic_runs WHERE pr_url = ? AND thread_id NOT LIKE 'prcomment-%' ORDER BY updated_at DESC LIMIT 1"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        c.execute(sql, (pr_url,))
        row = c.fetchone()
    return _row(row) if row else None


def upsert_comment_run(thread_id: str, *, status: str, summary: dict,
                       pr_url: Optional[str] = None, error: Optional[str] = None) -> None:
    ensure_schema()
    ts = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        c = conn.cursor()
        if db.is_postgres():
            from psycopg.types.json import Jsonb
            c.execute(
                "INSERT INTO chaosmedic_runs (thread_id, status, summary, pr_url, error, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (thread_id) DO UPDATE SET status = EXCLUDED.status, "
                "summary = EXCLUDED.summary, pr_url = COALESCE(EXCLUDED.pr_url, chaosmedic_runs.pr_url), "
                "error = EXCLUDED.error, updated_at = EXCLUDED.updated_at",
                (thread_id, status, Jsonb(summary or {}), pr_url, error, ts, ts),
            )
        else:
            c.execute(
                "INSERT INTO chaosmedic_runs (thread_id, status, summary, pr_url, error, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (thread_id) DO UPDATE SET status = excluded.status, "
                "summary = excluded.summary, pr_url = COALESCE(excluded.pr_url, chaosmedic_runs.pr_url), "
                "error = excluded.error, updated_at = excluded.updated_at",
                (thread_id, status, json.dumps(summary or {}), pr_url, error, ts, ts),
            )


def is_comment_processed(comment_id: str) -> bool:
    ensure_schema()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = "SELECT 1 FROM opsgentic_pr_events WHERE comment_id = ?"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        c.execute(sql, (str(comment_id),))
        row = c.fetchone()
    return row is not None


def mark_comment_processed(comment_id: str, pr_url: Optional[str] = None) -> None:
    ensure_schema()
    ts = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        c = conn.cursor()
        sql = "INSERT INTO opsgentic_pr_events (comment_id, pr_url, processed_at) VALUES (?, ?, ?)"
        if db.is_postgres():
            sql = sql.replace("?", "%s")
        try:
            c.execute(sql, (str(comment_id), pr_url, ts))
        except Exception:
            pass
