import os
import pytest
from chaosmedic.sandbox.base import BaseSandbox
from chaosmedic.sandbox.subprocess_sandbox import SubprocessSandbox
from chaosmedic.sandbox.docker_sandbox import DockerSandbox
from chaosmedic.sandbox.factory import get_sandbox
from chaosmedic.engine.plan_engine import PlanEngine
from chaosmedic.engine.validation import ValidationAgent


def test_sandbox_factory_and_fallback():
    sandbox = get_sandbox()
    assert sandbox is not None
    assert isinstance(sandbox, BaseSandbox)
    assert sandbox.is_available() is True
    # In environments without docker, falls back to subprocess_isolated
    assert sandbox.name in ("docker_container", "subprocess_isolated")


def test_subprocess_sandbox_isolation(tmp_path):
    # Setup temporary project inside tmp_path
    app_file = tmp_path / "calc.py"
    app_file.write_text("def add(a, b):\n    return a + b\n")
    test_file = tmp_path / "test_calc.py"
    test_file.write_text("from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    
    sb = SubprocessSandbox()
    res = sb.run_test_with_patch(
        target_workspace=str(tmp_path),
        rel_file_path="calc.py",
        patched_code="def add(a, b):\n    return a + b\n",
        test_command="pytest test_calc.py"
    )
    assert res["passed"] is True
    assert "test_add" in res["tests_passed"]
    assert res["exit_code"] == 0


def test_subprocess_sandbox_catches_failure(tmp_path):
    app_file = tmp_path / "broken.py"
    app_file.write_text("def faulty():\n    raise RuntimeError('boom')\n")
    test_file = tmp_path / "test_broken.py"
    test_file.write_text("from broken import faulty\ndef test_faulty():\n    faulty()\n")
    
    sb = SubprocessSandbox()
    res = sb.run_test_with_patch(
        target_workspace=str(tmp_path),
        rel_file_path="broken.py",
        patched_code="def faulty():\n    raise RuntimeError('boom')\n",
        test_command="pytest test_broken.py"
    )
    assert res["passed"] is False
    assert len(res["tests_failed"]) > 0


def test_demo_app_service_behavior():
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from demo_app.service import calculate_discount, get_health_status, process_order
    
    assert get_health_status()["status"] == "healthy"
    
    # Normal input
    res = calculate_discount(100.0, 2, discount_factor=5.0)
    assert res == 160.0
    
    # Zero divisor raises ZeroDivisionError in unpatched code
    with pytest.raises(ZeroDivisionError):
        calculate_discount(100.0, 2, discount_factor=0.0)
