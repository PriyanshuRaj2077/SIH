@echo off
title SIH26054 Live Demonstration Launcher
echo ==================================================================
echo   SIH26054 — DIGITAL TWIN & TELEMETRY SIMULATOR DEMO
echo   Launching Simulator.exe and Dashboard.exe Side-by-Side
echo ==================================================================
cd /d "%~dp0"

echo [1/2] Launching Simulator.exe (Telemetry Source)...
start "SIH26054 Simulator" cmd /c "python simulator\main.py"

echo Waiting 2 seconds for telemetry server initialization...
timeout /t 2 /nobreak >nul

echo [2/2] Launching Dashboard.exe (Digital Twin & Mission Control)...
start "SIH26054 Digital Twin Dashboard" cmd /c "python dashboard\main.py"

echo ==================================================================
echo   Both applications are active!
echo   Simulator: http://127.0.0.1:8765
echo   Dashboard: http://127.0.0.1:8766
echo ==================================================================
