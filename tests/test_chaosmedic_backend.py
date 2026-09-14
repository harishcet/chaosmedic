import os
import pytest
from chaosmedic import db
from chaosmedic.engine.detection import DetectionAgent
from chaosmedic.engine.evidence import EvidenceAgent
from chaosmedic.engine.diagnosis import DiagnosisAgent
from chaosmedic.engine.plan_engine import PlanEngine
from chaosmedic.engine.validation import ValidationAgent
from chaosmedic.engine.ast_patcher import validate_python_syntax, generate_unified_diff, calculate_minimality_score
from chaosmedic.engine.orchestrator import run_incident_pipeline, resume_incident_pipeline


def test_sqlite_db_and_incident_lifecycle():
    db.ensure_schema()
    inc_id = "test-inc-lifecycle-1"
    db.create_incident({
        "incident_id": inc_id,
        "service": "checkout",
        "error_type": "HTTP 500",
        "status": "detecting",
        "stage": "DETECT",
        "current_agent": "Detection Agent"
    })
    
    inc = db.get_incident(inc_id)
    assert inc is not None
    assert inc["incident_id"] == inc_id
    assert inc["service"] == "checkout"
    assert inc["stage"] == "DETECT"
    
    db.update_incident(inc_id, {"status": "resolved", "stage": "REMEMBER"})
    inc2 = db.get_incident(inc_id)
    assert inc2["status"] == "resolved"
    assert inc2["stage"] == "REMEMBER"


def test_incident_memory_store_and_search():
    db.ensure_schema()
    mid = db.store_memory({
        "incident_id": "inc-mem-test",
        "service": "payment",
        "error_signature": "KeyError: 'stripe_token'",
        "root_cause": "Missing stripe_token in request body",
        "patch": "--- a/pay.py\n+++ b/pay.py\n@@ -1 +1 @@\n-token = body['stripe_token']\n+token = body.get('stripe_token')",
        "validation_results": {"passed": True},
        "deployment_result": {"success": True},
        "recovery_result": {"recovered": True}
    })
    assert mid is not None
    
    memories = db.find_memory_candidates("KeyError")
    assert len(memories) > 0
    assert any(m["error_signature"] == "KeyError: 'stripe_token'" for m in memories)


def test_ast_patcher_and_minimality():
    valid, msg = validate_python_syntax("def foo():\n    return 42\n")
    assert valid is True
    
    invalid, msg = validate_python_syntax("def foo() return 42\n")
    assert invalid is False
    
    orig = "def foo():\n    return 1\n"
    patched = "def foo():\n    return 2\n"
    diff = generate_unified_diff(orig, patched, "foo.py")
    assert "return 2" in diff
    
    score = calculate_minimality_score(diff)
    assert score >= 0.8


def test_multi_plan_generation_and_scoring():
    engine = PlanEngine()
    validator = ValidationAgent()
    
    evidence = {
        "source_files": {
            "math_ops.py": "def divide(a, b):\n    result = a / divisor\n    return result\n"
        }
    }
    diagnosis = {
        "affected_file": "math_ops.py",
        "root_cause": "ZeroDivisionError: float division by zero"
    }
    
    plans = engine.generate_candidate_plans(evidence, diagnosis)
    assert len(plans) >= 2
    for p in plans:
        assert p["ast_valid"] is True
        assert len(p["diff"]) > 0
        
    val_res = validator.validate_plans(plans, target_workspace="")
    assert val_res["passed"] is True
    assert val_res["selected_plan"] is not None
    assert val_res["best_score"] > 0.5


def test_orchestrator_10_stage_execution(tmp_path):
    failing_file = tmp_path / "app.py"
    failing_file.write_text("def run(val, divisor):\n    result = val / divisor\n    return result\n")
    
    alert = {
        "title": "ZeroDivisionError",
        "service": "test-service",
        "status_code": 500,
        "endpoint": "http://localhost:8000/run",
        "stack_trace": f'File "{failing_file}", line 2, in run\nZeroDivisionError: division by zero',
        "logs": ["ZeroDivisionError: division by zero"]
    }
    
    res = run_incident_pipeline(alert, target_workspace=str(tmp_path))
    assert res["status"] == "awaiting_approval"
    assert res["stage"] == "VALIDATE"
    
    # Approve
    inc_id = res["incident_id"]
    res_approve = resume_incident_pipeline(inc_id, action="approve")
    assert res_approve["success"] is True
    assert res_approve["stage"] == "REMEMBER"
    assert res_approve["status"] == "recovered"
