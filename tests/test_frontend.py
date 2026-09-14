"""Tests for ChaosMedic Frontend UI and Console static routing."""
import pytest
from starlette.testclient import TestClient
from chaosmedic.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_frontend_dashboard_loads(client):
    """Test that visiting the root endpoint returns the light-themed SRE dashboard."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "ChaosMedic" in html
    assert "Autonomous Infrastructure Self-Healing" in html
    assert "Human Approval Gate Required" in html
    assert "Incident Memory" in html
    assert "pipeline-stepper" in html
    assert "diff-container" in html
    assert "reasoning-feed" in html


def test_pipeline_stages_schema(client):
    """Test that pipeline endpoint provides the complete 10-stage architecture."""
    resp = client.get("/api/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert "stages" in data
    assert len(data["stages"]) == 10
    stage_ids = [s["id"] for s in data["stages"]]
    expected_ids = [
        "CONNECT", "DETECT", "COLLECT", "UNDERSTAND", "DIAGNOSE",
        "REPAIR", "SANDBOX", "VALIDATE", "DEPLOY", "REMEMBER"
    ]
    assert stage_ids == expected_ids
