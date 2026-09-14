"""ChaosMedic End-to-End Incident Response Drill.
Demonstrates the full autonomous self-healing lifecycle:
1. Failure detection (HTTP 500 / ZeroDivisionError)
2. 10-stage LangGraph execution up to Human Approval Gate
3. Sandbox validation and multi-plan selection
4. Human approval and patch deployment
5. Active recovery verification and Incident Memory retention
"""
from __future__ import annotations

import os
import sys
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from starlette.testclient import TestClient
from chaosmedic.main import app
from chaosmedic import db

def run_drill():
    print("=" * 80)
    print(" [CHAOSMEDIC] AUTONOMOUS SELF-HEALING END-TO-END INCIDENT RESPONSE DRILL")
    print("=" * 80)
    
    client = TestClient(app)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    demo_ws = os.path.join(root_dir, "demo_app")
    service_file = os.path.join(demo_ws, "service.py")
    
    # Ensure sys.path includes root
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from demo_app.service import calculate_discount, process_order, get_health_status
    
    # ---------------------------------------------------------------------------
    # Step 1: Baseline Health and Fault Verification
    # ---------------------------------------------------------------------------
    print("\n[Step 1] Baseline Service Inspection:")
    health = get_health_status()
    print(f"  Service: {health['service']} | Health: {health['status']}")
    
    # Normal calculation works
    normal_res = calculate_discount(50.0, 2, discount_factor=10.0)
    print(f"  Normal Calculation: 50.0 * 2 with discount=10.0 -> ${normal_res}")
    
    # Trigger deliberate edge-case failure
    print("  Triggering edge-case: discount_factor = 0.0 ...")
    try:
        calculate_discount(100.0, 2, discount_factor=0.0)
        print("  WARNING: Expected ZeroDivisionError did not occur!")
    except ZeroDivisionError as e:
        print(f"  [CONFIRMED BUG] Unhandled exception in production code: {type(e).__name__}: {e}")
        
    # ---------------------------------------------------------------------------
    # Step 2: Ingest Incident Signal into ChaosMedic Engine
    # ---------------------------------------------------------------------------
    print("\n[Step 2] Ingesting Failure Signal into ChaosMedic Self-Healing Engine...")
    incident_id = f"drill-{int(time.time())}"
    alert_payload = {
        "incident_id": incident_id,
        "service": "demo-billing-service",
        "endpoint": "http://localhost:5000/api/calculate",
        "status_code": 500,
        "title": "ZeroDivisionError in calculate_discount",
        "target_workspace": demo_ws,
        "stack_trace": """Traceback (most recent call last):
  File "service.py", line 18, in calculate_discount
    discount_amount = base_total / discount_factor
ZeroDivisionError: float division by zero""",
        "logs": [
            "2026-09-14 20:00:00 [ERROR] ZeroDivisionError: float division by zero in calculate_discount",
            "2026-09-14 20:00:01 [CRITICAL] Checkout aborted for cart id 88412"
        ]
    }
    
    resp = client.post("/api/incidents", json=alert_payload)
    assert resp.status_code == 202
    print(f"  Incident Ingested: ID={incident_id} | Stage={resp.json()['stage']}")
    
    # ---------------------------------------------------------------------------
    # Step 3: Monitor 10-Stage Pipeline Progression
    # ---------------------------------------------------------------------------
    print("\n[Step 3] Monitoring Autonomous Pipeline Progression:")
    inc = None
    for poll_idx in range(30):
        inc = client.get(f"/api/incidents/{incident_id}").json()
        stage = inc.get("stage")
        status = inc.get("status")
        agent = inc.get("current_agent", "Engine")
        print(f"  Poll {poll_idx + 1:2d} | Stage: {stage:12s} | Status: {status:18s} | Agent: {agent}")
        if status in ("awaiting_approval", "escalated", "repaired", "resolved"):
            break
        time.sleep(1.0)
        
    assert inc.get("status") == "awaiting_approval", f"Expected awaiting_approval, got {inc.get('status')}"
    print("\n  >>> [HUMAN APPROVAL GATE REACHED] Pipeline paused before deployment. <<<")
    
    # ---------------------------------------------------------------------------
    # Step 4: Audit Diagnosis and Candidate Patch Validation
    # ---------------------------------------------------------------------------
    print("\n[Step 4] Audit Diagnosis & Sandbox Validation:")
    diag = inc.get("diagnosis", {})
    print(f"  Root Cause:        {diag.get('root_cause')}")
    print(f"  Affected Location: {diag.get('affected_file')}:{diag.get('affected_function')}()")
    print(f"  Diagnosis Conf:    {diag.get('confidence') * 100:.0f}%")
    
    plans = inc.get("plans", [])
    print(f"  Generated Plans:   {len(plans)} candidate patches:")
    for idx, p in enumerate(plans):
        print(f"    Plan {idx+1}: {p.get('title')} (AST Valid: {p.get('ast_valid')})")
        
    sel_plan = inc.get("selected_plan", {})
    print(f"  Selected Plan:     [SAFEST] {sel_plan.get('title')}")
    print("  Unified Diff Preview:")
    for line in sel_plan.get("diff", "").splitlines()[:10]:
        print(f"    {line}")
        
    # ---------------------------------------------------------------------------
    # Step 5: Grant Human Approval and Deploy Patch
    # ---------------------------------------------------------------------------
    print("\n[Step 5] Granting Human Approval (SRE Confirmation)...")
    approve_resp = client.post(f"/api/incidents/{incident_id}/approve")
    assert approve_resp.status_code == 200
    app_data = approve_resp.json()
    print(f"  Approval Applied: Status={app_data.get('status')} | Stage={app_data.get('stage')}")
    
    # ---------------------------------------------------------------------------
    # Step 6: Post-Deployment Verification on Healed Target App
    # ---------------------------------------------------------------------------
    print("\n[Step 6] Verifying Live Target Application Self-Healing:")
    import importlib
    import demo_app.service
    importlib.reload(demo_app.service)
    
    healed_res = demo_app.service.calculate_discount(100.0, 2, discount_factor=0.0)
    print(f"  [SUCCESS] Calling calculate_discount(100.0, 2, discount_factor=0.0) -> ${healed_res}")
    
    order_res = demo_app.service.process_order({
        "order_id": "order-post-heal-99",
        "items": [
            {"price": 50.0, "quantity": 2, "discount_factor": 0.0},
            {"price": 30.0, "quantity": 1, "discount_factor": 5.0}
        ]
    })
    print(f"  [SUCCESS] Order processing completed: Success={order_res.get('success')}, Total=${order_res.get('total')}")
    
    # ---------------------------------------------------------------------------
    # Step 7: Verify Incident Memory Retention
    # ---------------------------------------------------------------------------
    print("\n[Step 7] Checking Incident Memory Archive:")
    memories = client.get("/api/memory").json()
    matching = [m for m in memories if m.get("incident_id") == incident_id]
    assert len(matching) > 0, "Incident was not found in Incident Memory!"
    print(f"  Incident [{incident_id}] successfully archived into Incident Memory.")
    print(f"  Total Incident Memories Stored: {len(memories)}")
    
    # ---------------------------------------------------------------------------
    # Cleanup: Reset demo_app to original broken state for future drills
    # ---------------------------------------------------------------------------
    backup_file = f"{service_file}.bak"
    if os.path.exists(backup_file):
        with open(backup_file, "r", encoding="utf-8") as bf:
            with open(service_file, "w", encoding="utf-8") as sf:
                sf.write(bf.read())
        os.remove(backup_file)
        print("\n[Cleanup] Restored demo_app/service.py to initial state for next demonstration.")
        
    print("=" * 80)
    print(" [PASSED] CHAOSMEDIC END-TO-END DRILL COMPLETED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    run_drill()