# System Architecture — AeroPulse Digital Twin

## System Name: **AeroPulse**
> AI-Enabled Digital Twin for Aero Piston Engine Health Management

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AeroPulse System Architecture                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────────┐  │
│  │  DATA SOURCE  │───▶│  EDGE PROCESSING │───▶│   CORE DIGITAL TWIN  │  │
│  │  (Sensors /   │    │  (Stream Ingest  │    │                       │  │
│  │   Simulator)  │    │   + Validation)  │    │  ┌─────────────────┐  │  │
│  └──────────────┘    └──────────────────┘    │  │ Physics Engine  │  │  │
│                                               │  │ (Thermodynamic  │  │  │
│                                               │  │  Model)         │  │  │
│                                               │  └────────┬────────┘  │  │
│                                               │           │           │  │
│                                               │  ┌────────▼────────┐  │  │
│                                               │  │ State Estimator │  │  │
│                                               │  │ (Kalman Filter) │  │  │
│                                               │  └────────┬────────┘  │  │
│                                               │           │           │  │
│                                               │  ┌────────▼────────┐  │  │
│                                               │  │ Residual        │  │  │
│                                               │  │ Generator       │  │  │
│                                               │  └────────┬────────┘  │  │
│                                               └───────────┼───────────┘  │
│                                                           │              │
│                              ┌─────────────────────────────┤              │
│                              │                             │              │
│                    ┌─────────▼─────────┐     ┌─────────────▼──────────┐  │
│                    │  ANOMALY DETECTION │     │   PROGNOSTICS ENGINE   │  │
│                    │                    │     │                        │  │
│                    │  • Autoencoder     │     │  • RUL Estimator       │  │
│                    │  • Isolation Forest│     │    (LSTM + Attention)  │  │
│                    │  • Statistical     │     │  • Degradation Tracker │  │
│                    │    (Mahalanobis)   │     │  • Confidence Bounds   │  │
│                    └─────────┬─────────┘     └────────────┬───────────┘  │
│                              │                            │              │
│                    ┌─────────▼────────────────────────────▼───────────┐  │
│                    │           DECISION ENGINE                         │  │
│                    │                                                   │  │
│                    │  • Health Score (0-100)                           │  │
│                    │  • Mission Go/No-Go Recommendation                │  │
│                    │  • Maintenance Action Queue                       │  │
│                    │  • Alert Priority Classification                  │  │
│                    └─────────────────────┬───────────────────────────┘  │
│                                          │                              │
│                    ┌─────────────────────▼───────────────────────────┐  │
│                    │           MISSION CONTROL DASHBOARD              │  │
│                    │                                                   │  │
│                    │  • Real-time engine state visualization          │  │
│                    │  • Digital twin 3D rendering                     │  │
│                    │  • Fault timeline & predictions                  │  │
│                    │  • RUL countdown                                 │  │
│                    │  • Historical trend analysis                     │  │
│                    └─────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layered Architecture

### Layer 0: Data Acquisition & Simulation
**Purpose**: Generate or ingest sensor data streams

| Component | Technology | Role |
|---|---|---|
| Engine Simulator | Python (NumPy/SciPy) | Physics-based 4-stroke engine model |
| Fault Injector | Custom module | Mathematically inject degradation profiles |
| Sensor Emulator | Python | Add noise, bias, dropout to clean signals |
| Stream Publisher | WebSocket / MQTT | Publish data as real-time stream |

### Layer 1: Data Ingestion & Validation
**Purpose**: Clean, validate, and buffer incoming telemetry

| Component | Technology | Role |
|---|---|---|
| Stream Consumer | FastAPI WebSocket | Receive real-time sensor streams |
| Data Validator | Pydantic schemas | Range checks, type checks, NaN handling |
| Feature Buffer | Ring buffer (in-memory) | Maintain sliding window for ML inference |
| Time Synchronizer | Custom | Align multi-rate sensor timestamps |

### Layer 2: Digital Twin Core
**Purpose**: Maintain a physics-accurate virtual model of the engine state

| Component | Technology | Role |
|---|---|---|
| Thermodynamic Model | Python (SciPy ODE) | Simulate expected cylinder pressures, temperatures |
| State Estimator | Extended Kalman Filter | Fuse sensor data with model predictions |
| Residual Generator | Statistical | Compute deviation between expected and actual |
| Parameter Tracker | Recursive least squares | Track slowly drifting engine parameters |

### Layer 3: AI/ML Intelligence
**Purpose**: Detect anomalies, classify faults, predict remaining life

| Component | Technology | Role |
|---|---|---|
| Anomaly Detector | Autoencoder + Isolation Forest | Identify when engine behaves abnormally |
| Fault Classifier | 1D-CNN + XGBoost | Classify fault type once anomaly confirmed |
| RUL Estimator | LSTM with Attention | Predict remaining useful life in hours |
| Uncertainty Quantifier | MC Dropout / Ensemble | Provide confidence intervals on predictions |

### Layer 4: Decision Engine
**Purpose**: Translate AI outputs into actionable decisions

| Component | Technology | Role |
|---|---|---|
| Health Scorer | Weighted multi-parameter | Compute composite 0-100 health score |
| Mission Advisor | Rule engine + ML | Go/No-Go recommendation with confidence |
| Alert Manager | Priority queue | Generate ranked alerts with severity |
| Maintenance Planner | Logic engine | Suggest specific maintenance actions |

### Layer 5: Presentation & Visualization
**Purpose**: Real-time mission control interface

| Component | Technology | Role |
|---|---|---|
| Dashboard | React + TypeScript | Main web-based UI |
| 3D Engine View | Three.js / React-Three-Fiber | Interactive 3D engine visualization |
| Charts/Gauges | Recharts / D3.js | Real-time telemetry gauges and trends |
| Alert Panel | Custom React | Fault alerts and recommendations |

---

## 3. Data Flow Architecture

```
Sensors/Simulator ──▶ WebSocket Stream ──▶ FastAPI Backend
                                              │
                                    ┌─────────┴──────────┐
                                    │                      │
                              Data Validation        Feature Store
                                    │                      │
                                    ▼                      ▼
                            Physics Model ◄──────── Historical Window
                                    │
                                    ▼
                          State Estimation (EKF)
                                    │
                          ┌─────────┼──────────┐
                          │         │          │
                          ▼         ▼          ▼
                    Residuals   Health      Parameter
                    (Δ values)  Indicators  Estimates
                          │         │          │
                          ▼         ▼          ▼
                    ┌─────────────────────────────┐
                    │       ML Inference Layer      │
                    │  Anomaly → Classify → RUL     │
                    └──────────────┬────────────────┘
                                   │
                                   ▼
                          Decision Engine
                                   │
                          ┌────────┼────────┐
                          │        │        │
                          ▼        ▼        ▼
                      Health    Mission   Maintenance
                      Score    Go/NoGo   Actions
                          │        │        │
                          └────────┼────────┘
                                   │
                                   ▼
                            Dashboard (WebSocket)
```

---

## 4. Technology Stack

### Backend
| Layer | Technology | Rationale |
|---|---|---|
| API Framework | **FastAPI** (Python) | Async, WebSocket support, fast, typed |
| Physics Engine | **NumPy + SciPy** | ODE solvers, linear algebra, proven |
| ML Framework | **PyTorch** | LSTM/Attention models, ONNX export |
| ML (Classical) | **scikit-learn + XGBoost** | Isolation Forest, ensemble methods |
| Data Processing | **Pandas + Polars** | Time-series manipulation |
| State Estimation | **FilterPy** | Kalman filter implementation |

### Frontend
| Layer | Technology | Rationale |
|---|---|---|
| UI Framework | **React 18 + TypeScript** | Component architecture, type safety |
| 3D Rendering | **React-Three-Fiber** (Three.js) | WebGL 3D engine visualization |
| Charts | **Recharts + D3.js** | Real-time gauge and trend rendering |
| Styling | **CSS Modules + Custom Design System** | Premium dark-mode aerospace aesthetic |
| State Management | **Zustand** | Lightweight, performant state |
| Real-time | **WebSocket (native)** | Low-latency bidirectional comms |

### Infrastructure (Demo)
| Component | Technology | Rationale |
|---|---|---|
| Containerization | **Docker + Docker Compose** | Single-command deployment |
| Process Management | **uvicorn + gunicorn** | Production ASGI server |
| Database (optional) | **SQLite / DuckDB** | Embedded, no setup needed |

---

## 5. Key Architectural Decisions

### ADR-001: Hybrid Physics+ML Architecture
**Decision**: Use physics model as the primary state estimator, ML for residual analysis  
**Rationale**: Pure ML requires enormous labeled data we don't have. Pure physics can't capture real-world degradation nuances. Hybrid gives us the best of both.

### ADR-002: Synthetic Data Generation
**Decision**: Build our own engine simulator and fault injector  
**Rationale**: No public piston engine run-to-failure dataset exists. Generating synthetic data with known ground truth enables proper model training and validation.

### ADR-003: WebSocket for Real-time Communication
**Decision**: Use WebSocket (not REST polling, not SSE)  
**Rationale**: Bidirectional, low-latency, well-supported in browsers. Mission-critical monitoring needs sub-second updates.

### ADR-004: Monorepo with Clear Module Boundaries
**Decision**: Single repository with `/backend`, `/frontend`, `/simulation` top-level modules  
**Rationale**: Team of 6 students can work in parallel without complex CI/CD. Each module has a clean API boundary.

### ADR-005: ONNX for Model Deployment
**Decision**: Train in PyTorch, export to ONNX for inference  
**Rationale**: ONNX enables edge deployment, faster inference, and language-agnostic model serving.

---

## 6. Working Prototype Implementation: Two Independent Executables

To meet the strict operational requirements of SIH Problem Statement SIH26054, the working prototype is engineered as **TWO completely independent Windows applications**:

```
┌────────────────────────────────────────────────────────┐
│                     SIMULATOR.EXE                      │
│                                                        │
│  • Continuous flight mission dynamics (10 Hz)          │
│  • Live Operator Controls:                             │
│    - Altitude (0 - 32,000 ft MSL)                      │
│    - Wind Speed (0 - 35 m/s)                           │
│    - Ambient Temperature (-40°C to +45°C)              │
│    - Throttle Demand (0 - 100%)                        │
│    - Propeller Aerodynamic Load (0.6x - 1.5x)          │
│  • Mean-Value Engine Model (Rotax 914 Turbo Class)     │
│  • Fault Injection Deck (7 physical fault modes)       │
│  • Telemetry Broadcast Server                          │
│    (WebSocket :8765/telemetry + UDP :9000)             │
└──────────────────────────┬─────────────────────────────┘
                           │ Real-Time Decoupled Telemetry Stream
                           │ JSON Frames (Future: CAN-to-Ethernet Bridge)
                           ▼
┌────────────────────────────────────────────────────────┐
│                     DASHBOARD.EXE                      │
│                                                        │
│  • Telemetry Ingestion Client (Auto-reconnect, Jitter) │
│  • DIGITAL TWIN CORE:                                  │
│    - Nominal Physics Model (Expected Behavior Baseline)│
│    - Extended Kalman Filter (EKF) State Estimator      │
│    - Degradation Observers (η_vol, η_comb, η_mech)     │
│    - Multi-Channel Residual Generator (Δ = y - ŷ)      │
│  • HEALTH, ANOMALY & RISK PIPELINE:                    │
│    - Mahalanobis & CUSUM Residual Anomaly Detection    │
│    - Physics-Guided Multi-Variable Fault Attribution   │
│    - Composite Engine Health Score (0 - 100%)          │
│    - Prognostics & RUL Projection with Confidence CI   │
│    - Contextual Pilot & Maintenance Advisory Engine    │
│  • Mission Control Real-time UI & Live Canvas Charts   │
└────────────────────────────────────────────────────────┘
```

### 6.1 Telemetry Interface Protocol Specification
Communication between `Simulator.exe` and `Dashboard.exe` is completely decoupled:
- **Transport**: Standard WebSocket (`ws://127.0.0.1:8765/telemetry`) and UDP datagrams (`127.0.0.1:9000`).
- **Frequency**: 10 Hz (100 ms frame interval).
- **Packet Schema**: Standardized JSON packet containing:
  - `packet_id`: Incremental sequence number (detects network drops and jitter).
  - `timestamp`: High-precision UTC epoch timestamp.
  - `engine_hours`: Cumulative total running hours.
  - `flight_env`: Ambient and control conditions (`altitude_ft`, `ambient_temp_c`, `ambient_pressure_kpa`, `wind_speed_mps`, `throttle_pct`, `engine_load`, `flight_phase`).
  - `telemetry`: 11 physical engine channels (`rpm`, `cht[4]`, `egt[4]`, `oil_temp_c`, `oil_pressure_bar`, `coolant_temp_c`, `map_kpa`, `fuel_flow_lph`, `vibration{x,y,z,rms}`, `bus_voltage`).
  - `sensor_status`: Sensor hardware integrity bitmasks.

### 6.2 Future Pathway: Replacing Simulator with Real UAV ECU Telemetry
Because the interface between `Simulator.exe` and `Dashboard.exe` is a standard, protocol-agnostic stream:
1. **ECU/CAN Hardware Integration**: In a production DRDO UAV ground station or test bench, a physical CAN-to-Ethernet transceiver or MAVLink bridge emits the identical JSON telemetry frame to port 8765 or 9000.
2. **Zero Downstream Code Changes**: `Dashboard.exe` processes the real engine data through its Digital Twin pipeline identically without requiring any architectural modifications.
3. **Honest Boundary**: The simulator is explicitly documented as our substitute for unavailable physical engine hardware and classified DRDO telemetry.

### 6.3 Standalone Executable Packaging
Both applications package into standalone Windows executables using PyInstaller:
- `dist/Simulator.exe`
- `dist/Dashboard.exe`
Native desktop windows are rendered via `pywebview` (utilizing the Windows WebView2 runtime) with automatic web browser fallback.

