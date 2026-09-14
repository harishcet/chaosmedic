@echo off
echo Starting ChaosMedic SRE Dashboard & Autonomous Engine...
cd /d "%~dp0"
call .venv\Scripts\activate
start http://localhost:8080
chaosmedic-api
pause