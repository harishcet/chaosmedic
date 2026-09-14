# 🩺 ChaosMedic — Autonomous Multi-Agent Infrastructure Self-Healing Engine

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Architecture: LangGraph](https://img.shields.io/badge/State_Machine-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Free Tier: 100% Zero-Cost](https://img.shields.io/badge/Free_Tier-Zero_Cost-emerald.svg)](#free-tier-zero-cost-architecture)
[![Sandbox: Subprocess + Docker](https://img.shields.io/badge/Sandbox-Dual_Abstraction-purple.svg)](#dual-sandbox-architecture)

> **Autonomous application source code remediation engine.** 
> Turns production crashes (HTTP 500, unhandled exceptions) into validated, syntax-safe Python AST patches with isolated sandbox verification and human-in-the-loop approval.

---

## 🌟 What is ChaosMedic?

Traditional AIOps tools stop at modifying infrastructure configurations (Kubernetes YAML manifests, Helm charts, or scaling replica counts). However, **over 80% of real-world production outages stem from application code errors**—such as unhandled edge cases, `ZeroDivisionError`, `KeyError`, and `TypeError`.

**ChaosMedic** is an autonomous, multi-agent self-healing system that directly remediates application source code. Powered by a stateful **10-stage LangGraph pipeline**, ChaosMedic ingests failure signals, maps stack traces to source files, executes multi-plan AST patch generation, validates candidate fixes in isolated sandboxes, enforces a human approval gate, and commits permanent resolutions into Incident Memory.

---

## 🏗️ 10-Stage Autonomous Self-Healing Pipeline

```
  ┌─────────┐     ┌────────┐     ┌─────────┐     ┌────────────┐     ┌──────────┐
  │ CONNECT │ ──▶ │ DETECT │ ──▶ │ COLLECT │ ──▶ │ UNDERSTAND │ ──▶ │ DIAGNOSE │
  └─────────┘     └────────┘     └─────────┘     └────────────┘     └──────────┘
                                                                          │
  ┌──────────┐     ┌────────┐     ┌─────────┐     ┌───────────┐           ▼
  │ REMEMBER │ ◀── │ DEPLOY │ ◀── │VALIDATE │ ◀── │  SANDBOX  │ ◀─── ┌────────┐
  └──────────┘     └────────┘     └─────────┘     └───────────┘      │ REPAIR │
                        ▲                                            └────────┘
                        │
             [ HUMAN APPROVAL GATE ]
          (interrupt_before: ["deploy"])
```

| Stage | Name | Responsible Agent | Description |
| :--- | :--- | :--- | :--- |
| **1** | **CONNECT** | Incident Monitor | Connects to application health checks, Prometheus, or webhook streams. |
| **2** | **DETECT** | Detection Agent | Identifies HTTP 500 errors, service crashes, or health check failures. |
| **3** | **COLLECT** | Evidence Agent | Captures stack traces, error logs, and git commit history. |
| **4** | **UNDERSTAND** | Context Agent | Parses source code, builds AST representation, and maps failure locations. |
| **5** | **DIAGNOSE** | Diagnosis Agent | Produces structured Root Cause Analysis (RCA JSON) with confidence metrics. |
| **6** | **REPAIR** | Plan Engine | Generates multiple distinct candidate patches (Plan A, Plan B, Plan C). |
| **7** | **SANDBOX** | Validation Agent | Applies candidate diffs inside an isolated environment without touching production. |
| **8** | **VALIDATE** | Scoring Engine | Executes test suites; scores pass rate (50%), safety (30%), and minimality (20%). |
| **9** | **DEPLOY** | Recovery Agent | **Human Approval Gate**: Pauses for review, deploys safest patch, and verifies HTTP 200. |
| **10**| **REMEMBER** | Memory Agent | Stores incident, RCA, patch diff, and verification data in Incident Memory. |

---

## 🤖 Specialized Multi-Agent Roles

ChaosMedic separates incident response responsibilities across dedicated specialized agents:

1. **Detection Agent**: Normalizes failure signals from HTTP requests, Grafana/Prometheus webhooks, or log streams into a standardized incident schema.
2. **Evidence Agent**: Extracts source files and line numbers directly from stack traces. Never hallucinates files or paths.
3. **Diagnosis (RCA) Agent**: Classifies exception types and outputs structured root-cause JSON. Falls back to deterministic AST error inspection when external LLMs are unavailable.
4. **Plan Engine**: Generates multiple distinct recovery plans using Python AST transformations:
   - **Plan A**: Minimal defensive guard check (e.g. zero divisor / null check).
   - **Plan B**: Graceful exception boundary (`try-except` fallback).
   - **Plan C**: Safe attribute / dictionary access (`.get()` fallback).
5. **Validation Agent**: Evaluates each candidate patch inside an isolated sandbox. Calculates a composite score:
   $$\text{Score} = (\text{PassRate} \times 0.5) + (\text{RegressionSafety} \times 0.3) + (\text{Minimality} \times 0.2)$$
6. **Recovery Agent**: Applies the validated patch to the target service, backs up the original source, and executes an active health probe to confirm HTTP 200 recovery.
7. **Memory Agent**: Indexes resolved incidents in SQLite/Postgres for continuous learning and similarity matching.

---

## 🛡️ Human-in-the-Loop Approval Gate

ChaosMedic guarantees that **no application code is ever modified in production without explicit human authorization**.

- The LangGraph pipeline uses state checkpointing (`interrupt_before: ["deploy"]`).
- When candidate patches are validated in the sandbox, the pipeline halts at stage `VALIDATE` with status `awaiting_approval`.
- On-call engineers can review the root cause, compare multi-plan diffs, and inspect validation test logs in the SRE Console.
- Clicking **Approve & Deploy Fix** resumes the pipeline, deploys the safest patch, and runs recovery health checks.

---

## 📦 Dual Sandbox Architecture

ChaosMedic supports running in any environment without external infrastructure requirements:

- **Subprocess Sandbox (Default / Free-Tier)**:
  - Creates temporary isolated directories (`tempfile.TemporaryDirectory`).
  - Copies the workspace, applies candidate patches, and executes test suites (`pytest`).
  - Strict subprocess execution timeouts and environment variable isolation (`PYTHONPATH`).
  - Requires **zero external daemons** and zero cost.
- **Docker Sandbox (Optional)**:
  - Mounts temporary copies into ephemeral containers (`python:3.12-slim`).
  - Automatically detected via `docker info`.

---

## 💡 Free-Tier Zero-Cost Compatibility

ChaosMedic is designed from the ground up to operate completely free of cost:
- **Persistence**: File-based **SQLite** by default (`chaosmedic.db`). Optional PostgreSQL via `DATABASE_URL`.
- **Background Queue**: Asynchronous in-process task execution via FastAPI `BackgroundTasks`. Optional Redis via `REDIS_URL`.
- **LLM Independence**: Includes a deterministic, AST-aware rule engine that works offline with zero API keys required.
- **Self-Contained Frontend**: Single-page SRE console served directly by FastAPI without Node.js dependencies.

---

## 🚀 Quickstart Guide

### 1. Installation

Clone the repository and install dependencies using `uv` (recommended) or standard `pip`:

```bash
# Clone repository
git clone https://github.com/chaosmedic/chaosmedic.git
cd chaosmedic

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 2. Start the ChaosMedic Engine & Console

```bash
chaosmedic-api
```
The server will start at `http://localhost:8080`.
- Open `http://localhost:8080/` in your browser to view the **Light-Themed SRE Dashboard**.
- API documentation is available at `http://localhost:8080/docs`.

### 3. Run the Monitored Demo Application

The included demo application (`demo_app`) is an e-commerce billing service containing an edge-case `ZeroDivisionError` when `discount_factor` is `0.0`:

```bash
python -m demo_app.service
```

### 4. Trigger Self-Healing Simulation

You can trigger self-healing directly from the SRE Dashboard under the **⚡ Chaos Simulator** tab, or via `curl`:

```bash
curl -X POST http://localhost:8080/api/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "service": "demo-billing-service",
    "endpoint": "/api/checkout",
    "status_code": 500,
    "title": "ZeroDivisionError in calculate_discount",
    "stack_trace": "ZeroDivisionError: float division by zero\n  File \"service.py\", line 18, in calculate_discount\n    discount_amount = base_total / discount_factor"
  }'
```

Watch the pipeline transition through all 10 stages in real time on the dashboard!

---

## 🐳 Docker & Docker Compose

Deploy the complete ChaosMedic self-healing stack using Docker Compose:

```bash
docker-compose up --build
```

Services started:
- `chaosmedic-engine`: Port `8080` (API & Console)
- `chaosmedic-demo-app`: Port `5000` (Monitored service)

---

## 🧪 Running Automated Tests

ChaosMedic includes a comprehensive automated test suite covering AST patch generation, sandbox execution, pipeline checkpoints, frontend routes, and database persistence:

```bash
# Run unit and integration tests
pytest tests

# Verify demo application edge case behavior
pytest demo_app/tests/test_service.py
```

---

## 📡 API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/healthz` | `GET` | Health check endpoint returning engine and database status. |
| `/api/incidents` | `POST` | Ingest failure signal and trigger autonomous 10-stage pipeline. |
| `/api/incidents` | `GET` | List recent incidents with stage, status, and diagnosis. |
| `/api/incidents/{id}` | `GET` | Retrieve detailed incident state, candidate patches, and scores. |
| `/api/incidents/{id}/approve`| `POST` | Human approval gate: deploy safest patch and verify recovery. |
| `/api/incidents/{id}/reject` | `POST` | Human approval gate: reject proposed plans. |
| `/api/pipeline` | `GET` | Retrieve official 10-stage pipeline blueprint schema. |
| `/api/memory` | `GET` | Query historical incident resolutions from Incident Memory. |

---

## ⚖️ Legal & License

ChaosMedic is licensed under the **GNU General Public License v3.0** (`GPL-3.0`). See the [`LICENSE`](LICENSE) file for full details.

### Notice & Attribution
This project incorporates and builds upon code from **OpsGentic** (Copyright 2024–2026 Huan Nguyen, licensed under GPL-3.0). See [`NOTICE`](NOTICE) for detailed attribution and architectural transformation history.