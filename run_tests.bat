@echo off
echo Running ChaosMedic Test Suite...
cd /d "%~dp0"
call .venv\Scripts\activate
pytest tests
pause