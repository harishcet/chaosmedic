@echo off
echo Running ChaosMedic End-to-End Self-Healing Drill...
cd /d "%~dp0"
call .venv\Scripts\activate
python demo_e2e_drill.py
pause