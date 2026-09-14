# 🩺 ChaosMedic — Quickstart Guide

This guide will help you get **ChaosMedic** running locally in under 2 minutes.

---

## ⚡ Option 1: Run the One-Command Self-Healing Drill (Fastest)

To see the complete autonomous self-healing loop in action without configuring anything:

```powershell
cd C:\Users\haris\.gemini\antigravity\scratch\chaosmedic
.venv\Scripts\activate
python demo_e2e_drill.py
```

### What this drill demonstrates automatically:
1. **Detects Fault**: Monitored billing app crashes with `ZeroDivisionError` when `discount_factor=0.0`.
2. **Autonomous Analysis**: Maps the traceback directly to `service.py:18` without hallucinating files.
3. **Multi-Plan Generation**: Produces multiple distinct Python AST patches.
4. **Sandbox Validation**: Runs each patch inside an isolated sandbox; verifies pass rates.
5. **Human Approval Gate**: Pauses before deployment with full diff inspection.
6. **Live Recovery**: Applies the approved patch and confirms the application now processes orders without crashing!
7. **Incident Memory**: Records the resolution permanently into SQLite.

---

## 🖥️ Option 2: Interactive SRE Web Console

ChaosMedic includes a built-in, light-themed SRE dashboard requiring **zero Node.js dependencies**:

### 1. Launch the ChaosMedic Server
```powershell
.venv\Scripts\activate
chaosmedic-api
```
The server will start on port `8080`.

### 2. Open the Dashboard
Open your browser and navigate to:
```
http://localhost:8080/
```

### 3. Trigger a Chaos Experiment
Click on the **⚡ Chaos Simulator** tab in the navigation bar:
- Select **Demo Billing App (`/api/checkout`)**.
- Click **⚡ Fire Incident Signal**.
- Switch to the **🚨 Live Incident Trace** tab to watch the 10-stage pipeline progress:
  `CONNECT → DETECT → COLLECT → UNDERSTAND → DIAGNOSE → REPAIR → SANDBOX → VALIDATE`
- When the **🛡️ Human Approval Gate Required** banner appears:
  - Review the Root Cause Analysis.
  - Compare the candidate patch diffs in the diff viewer.
  - Click **✅ Approve & Deploy Fix**.
- Watch the Recovery Agent deploy the fix and record it in **🧠 Incident Memory**!

---

## 🧪 Option 3: Run the Automated Test Suite

Verify all 46 core engine and sandbox tests:

```powershell
.venv\Scripts\activate
pytest tests
```

---

## 🐳 Option 4: Docker & Docker Compose

To run ChaosMedic and the monitored service inside isolated containers:

```bash
docker-compose up --build
```
Access the console at `http://localhost:8080`.