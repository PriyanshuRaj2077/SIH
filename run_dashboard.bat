@echo off
title SIH26054 - Digital Twin & Health Analytics Dashboard (Dashboard.exe)
echo ==================================================================
echo   Starting SIH26054 Digital Twin Mission Control (Dashboard.exe)
echo   Connecting to Telemetry at ws://127.0.0.1:8765/telemetry
echo   Console: http://127.0.0.1:8766
echo ==================================================================
cd /d "%~dp0"
python dashboard\main.py %*
pause
