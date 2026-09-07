@echo off
title SIH26054 - Engine & Mission Telemetry Simulator (Simulator.exe)
echo ==================================================================
echo   Starting SIH26054 UAV Engine Simulator (Simulator.exe)
echo   Broadcasting 10 Hz Telemetry on ws://127.0.0.1:8765/telemetry
echo   Console: http://127.0.0.1:8765
echo ==================================================================
cd /d "%~dp0"
python simulator\main.py %*
pause
