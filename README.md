# AeroPulse — SIH 2026 Working Prototype

> **AI-Enabled Real-Time Digital Twin System for Health Monitoring, Fault Prediction and Mission Reliability Enhancement of Aero Piston Engines used in MALE UAVs**

**SIH Problem Statement**: SIH26054  
**Organization**: DRDO (Defence Research and Development Organisation)  
**Category**: Software  
**Theme**: Robotics and Drones  
**Reference Engine**: Rotax 914 Turbo-Class 4-Stroke Flat-Four (DRDO TAPAS BH-201 Proxy)

---

## 1. System Architecture Overview

The system consists of **TWO completely independent Windows applications** communicating via a real-time telemetry stream:

```
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│            SIMULATOR.EXE             │          │            DASHBOARD.EXE             │
│                                      │          │                                      │
│  • Simulated Physical UAV / Engine   │          │  • Digital Twin State & Baseline     │
│  • 10 Hz Continuous Mission Physics  │          │  • Extended Kalman Filter (EKF)      │
│  • Live Operator Controls            │  10 Hz   │  • Multi-Channel Residual Generator  │
│    (Altitude, Wind, Throttle, Load)  │─────────▶│  • Anomaly Detection (CUSUM, D_res)  │
│  • Fault Injection Deck (7 Faults)   │WebSocket │  • Physics-Guided Fault Attribution  │
│  • Telemetry Broadcast Server        │(Port8765)│  • Engine Health (0-100%) & RUL      │
│    (ws://127.0.0.1:8765/telemetry)   │          │  • Mission Risk (GO / CAUTION / RTB) │
│    (+ UDP Port 9000)                 │          │  • Pilot & Maintenance Advisories    │
└──────────────────────────────────────┘          └──────────────────────────────────────┘
```

> [!IMPORTANT]
> **Future Hardware Replacement**:
> The telemetry interface is completely protocol-agnostic. In production, a physical UAV CAN/ECU bus bridge or telemetry downlink emits the identical JSON packet to `ws://127.0.0.1:8765/telemetry` or UDP `9000`. `Dashboard.exe` consumes it directly with **zero code modifications**.

---

## 2. Quick Start: Live SIH Demonstration

### Option A: One-Click Dual Launch (Recommended)
Double-click [`run_demo.bat`](run_demo.bat) or run from PowerShell:
```powershell
.\run_demo.bat
```
This launches both `Simulator.exe` and `Dashboard.exe` side-by-side on your screen.

### Option B: Launch Applications Individually
```powershell
# Terminal 1: Launch Simulator (Telemetry Source)
.\run_simulator.bat
# (Or: python simulator/main.py)

# Terminal 2: Launch Digital Twin Dashboard (Telemetry Receiver)
.\run_dashboard.bat
# (Or: python dashboard/main.py)
```

- **Simulator Operator Console**: [http://127.0.0.1:8765](http://127.0.0.1:8765)
- **Dashboard Mission Control**: [http://127.0.0.1:8766](http://127.0.0.1:8766)

---

## 3. Step-by-Step Live Demonstration Script for Judges

1. **Launch Both Apps**: Run [`run_demo.bat`](run_demo.bat). Observe that `Dashboard.exe` immediately establishes synchronization with `Simulator.exe` (`10.0 Hz SYNC`, latency `< 1 ms`).
2. **Observe Nominal Mission**: At nominal cruise (25,000 ft, 72% throttle):
   - Engine Health reads **98-100% (Green)**.
   - Mission Reliability reads **LOW RISK (MISSION GO)**.
   - All Digital Twin residual bars sit at **0.0 (Green)**.
   - RUL forecast shows **1,857 Flight Hours**.
3. **Change Operational Variables on Simulator**:
   - Slide **Altitude** from 5,000 ft $\to$ 25,000 ft $\to$ observe intake MAP decrease from 82 kPa to 58 kPa (density altitude effect).
   - Slide **Throttle** from 72% to 100% (Takeoff / Climb) $\to$ observe RPM ramp to 5,500 RPM, power rise to 74 kW, and CHTs adjust smoothly with realistic thermal inertia.
   - Observe that the **Digital Twin tracks the expected physics baseline**, so residuals remain small and **NO false alarms** are triggered!
4. **Inject Fault 1 — Lubrication Collapse**:
   - On `Simulator.exe`, toggle **F05: LUBRICATION COLLAPSE** (80% severity).
   - On Simulator: Oil pressure plunges to 1.35 bar, oil temperature rises.
   - On `Dashboard.exe`:
     - Oil pressure residual bar plunges to **-2.6 bar (Flashing Crimson)**.
     - Anomaly Detected: **CRITICAL ALERT**.
     - Diagnosed Cause: **F05 Lubrication Oil Pressure Collapse**.
     - Health Score drops to **14-25%**.
     - Mission Risk escalates to **HIGH RISK (RTB / ABORT)**.
     - RUL switches from hours to emergency window: **~28 Minutes before bearing seizure**.
     - Pilot Advisory triggers immediate throttle reduction and emergency landing instructions.
5. **Clear Fault**:
   - On Simulator, click **RESET ALL**.
   - Observe Digital Twin smoothly recovers to 100% health and clears the warning.
6. **Test Other Fault Modes**:
   - **F06 (Cooling Failure)**: Radiator blockage $\to$ Coolant and CHT thermal runaway $\to$ diagnosed within 3 seconds.
   - **F03 (Injector Clog)**: Cylinder 3 lean burn $\to$ EGT 3 spikes to 865°C $\to$ diagnosed specifically to Cylinder 3.
   - **F08 (Bearing Wear)**: Vibration surges to 5.2 mm/s $\to$ diagnosed as mechanical bearing defect.

---

## 4. Packaging into Standalone Windows Executables

To build standalone `dist/Simulator.exe` and `dist/Dashboard.exe` using PyInstaller:
```powershell
python build/build_all.py
```
Outputs:
- `dist/Simulator.exe` (Single-file self-contained executable)
- `dist/Dashboard.exe` (Single-file self-contained executable)

---

## 5. Automated Verification Test Suite

Run the automated test suite to verify physics fidelity, telemetry protocol serialization, and fault classification:
```powershell
# Run Digital Twin core & fault diagnosis unit test
python tests/test_pipeline.py

# Run live multi-process network integration test
python tests/test_network_integration.py
```
Both test suites validate 100% pass rates across all nominal and failure modes.

---

## 6. Project Layout

```
SIH/
├── common/                           # Standard telemetry protocol & constants
│   ├── constants.py                  # Physical specs (Rotax 914), limits, ISA atmosphere
│   └── telemetry_schema.py           # Pydantic 10 Hz JSON telemetry packet schema
├── simulator/                        # Simulator.exe (Simulated Physical Engine)
│   ├── physics_engine.py             # Mean-Value Engine Model (MVEM) + thermal capacitance
│   ├── fault_injector.py             # 7 physical fault injection degradation profiles
│   ├── telemetry_server.py           # 10 Hz WebSocket & UDP broadcast server
│   ├── ui/                           # Operator console (HTML5 / CSS3 / JavaScript)
│   └── main.py                       # Simulator application entry point
├── dashboard/                        # Dashboard.exe (Digital Twin & Analytics)
│   ├── telemetry_client.py           # WebSocket stream consumer with auto-reconnect
│   ├── digital_twin.py               # Physics expected baseline + EKF state estimator
│   ├── analytics.py                  # CUSUM, Mahalanobis D_res & physics attribution matrix
│   ├── health_risk.py                # Health scoring (0-100%), RUL forecast, mission risk
│   ├── advisory.py                   # Plain-English pilot & maintenance advisory generator
│   ├── ui/                           # Mission Control UI & real-time canvas strip charts
│   └── main.py                       # Dashboard application entry point
├── build/                            # Packaging configuration
│   └── build_all.py                  # PyInstaller build script for .exe creation
├── tests/                            # Automated verification tests
│   ├── test_pipeline.py              # Physics & fault diagnosis unit test
│   └── test_network_integration.py   # Multi-process network communication test
├── docs/                             # Complete project documentation & research
├── run_simulator.bat                 # Standalone Simulator launcher
├── run_dashboard.bat                 # Standalone Dashboard launcher
├── run_demo.bat                      # 1-Click Side-by-Side Demonstration Launcher
└── README.md                         # This file
```

---

## 7. License & Hackathon Submission

Developed for **Smart India Hackathon (SIH) 2026** — Problem Statement **SIH26054** (DRDO).
