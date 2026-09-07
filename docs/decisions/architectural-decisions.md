# Architectural Decision Records (ADRs)

## ADR-001: Hybrid Physics + ML Architecture
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: We need a system that can detect anomalies and predict remaining useful life for a piston engine, but we have NO real engine data.

**Decision**: Use a physics-based thermodynamic engine model as the core digital twin, with ML models analyzing the residuals (deviations from physics predictions).

**Rationale**:
- Pure ML requires thousands of labeled failure examples — we don't have real data
- Pure physics models can't capture subtle real-world degradation patterns
- Hybrid approach: physics provides the "expected" baseline, ML identifies when reality diverges from expectation
- This is what GE Aviation and Rolls-Royce use (validated industry approach)

**Consequences**:
- (+) Works with limited/synthetic data
- (+) Physically interpretable results
- (+) ML models are smaller and train faster (residuals, not raw data)
- (-) Physics model accuracy limits overall system accuracy
- (-) Requires domain knowledge to build the thermodynamic model

---

## ADR-002: Synthetic Data Generation (Build Our Own Simulator)
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: No public piston engine run-to-failure dataset exists. NASA C-MAPSS is turbofan-specific.

**Decision**: Build our own engine simulator with fault injection capability to generate labeled training data.

**Rationale**:
- GE's C-MAPSS was itself a simulator used to generate the famous dataset
- We control the ground truth — we know exactly when faults start and what they are
- We can generate unlimited data with varied conditions
- The simulator itself IS a component of the digital twin

**Consequences**:
- (+) Unlimited labeled data with known ground truth
- (+) Can simulate any fault mode we define
- (+) Simulator doubles as the physics engine in the digital twin
- (-) Synthetic data may not perfectly match real engine behavior
- (-) Must validate simulator against published engine specifications

**Mitigation**: We validate steady-state and transient behavior against published Rotax 912 performance data.

---

## ADR-003: WebSocket for Real-Time Communication
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: Dashboard needs sub-second updates from the backend. Options: REST polling, SSE, WebSocket, gRPC.

**Decision**: Use WebSocket for all real-time communication.

**Rationale**:
- Bidirectional (dashboard can send commands back, e.g., trigger fault injection)
- Low overhead (no HTTP headers per frame)
- Native browser support (no library needed)
- FastAPI has excellent WebSocket support

**Rejected Alternatives**:
- REST polling: Too much overhead for 10 Hz updates
- SSE: One-directional only, can't send commands back
- gRPC: Over-engineered for this use case, poor browser support

---

## ADR-004: Python Backend with FastAPI
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: Need a backend that can run physics simulations, ML inference, and serve a real-time API.

**Decision**: Python with FastAPI as the web framework.

**Rationale**:
- Python ecosystem (NumPy, SciPy, PyTorch, scikit-learn) is unmatched for scientific computing
- FastAPI is async-native, supports WebSocket, auto-generates API docs
- Team expertise is strongest in Python
- ONNX Runtime for Python provides fast inference without needing C++

**Rejected Alternatives**:
- Node.js: Poor scientific computing ecosystem
- Rust: High performance but slow development, limited ML ecosystem
- C++: Same issues as Rust, unnecessary for a demo

---

## ADR-005: React + Three.js Frontend
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: Need a visually impressive dashboard that includes 3D engine visualization.

**Decision**: React 18 with TypeScript, React-Three-Fiber for 3D, Recharts for telemetry charts.

**Rationale**:
- React is the most widely used frontend framework
- React-Three-Fiber makes Three.js declarative and composable
- TypeScript prevents common bugs in a complex dashboard
- Recharts handles real-time time-series well
- Dark-mode aerospace aesthetic matches the domain

---

## ADR-006: ONNX for Model Deployment
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: ML models are trained in PyTorch but need to run efficiently during inference.

**Decision**: Export trained PyTorch models to ONNX and use ONNX Runtime for inference.

**Rationale**:
- ONNX Runtime is 2-5x faster than native PyTorch for inference
- Models can be deployed on edge devices (e.g., Jetson) via TensorRT
- Language-agnostic — could serve from C++ or JavaScript if needed
- Standard format — model can be inspected and validated independently

---

## ADR-007: Asymmetric Loss for RUL Prediction
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: RUL over-prediction (saying engine has more life than it does) is DANGEROUS. Under-prediction (saying engine has less life) is merely COSTLY.

**Decision**: Use an asymmetric loss function that penalizes over-prediction 2x more than under-prediction.

**Rationale**:
- In aerospace, the consequence of a missed failure is catastrophic (loss of aircraft)
- The consequence of premature maintenance is economic (wasted maintenance cost)
- The loss function encodes this domain-specific asymmetry directly into training
- NASA uses a similar asymmetric scoring function for the PHM challenge

---

## ADR-008: MC Dropout for Uncertainty Quantification
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: A point estimate of RUL is not sufficient for mission planning. Decision makers need to know the confidence of the prediction.

**Decision**: Use Monte Carlo Dropout to provide Bayesian uncertainty estimates on RUL predictions.

**Rationale**:
- Simply adding dropout and running multiple forward passes during inference
- No architectural changes needed — just enable dropout during prediction
- Provides calibrated confidence intervals without training a full Bayesian network
- Computationally cheaper than ensemble methods (no need for N separate models)

**Trade-off**: 50 forward passes instead of 1, but each pass is fast (~3ms), so total is ~150ms — still within our 1-second budget for RUL updates.

---

## ADR-009: Transfer Learning from NASA C-MAPSS
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: Our synthetic data may have distribution gaps. NASA C-MAPSS, while turbofan-specific, captures general degradation patterns.

**Decision**: Pre-train the LSTM encoder on C-MAPSS data, then fine-tune on our piston engine data.

**Rationale**:
- General degradation patterns (monotonic decline, knee-point acceleration) are engine-agnostic
- Pre-training gives the LSTM a better starting point for learning temporal degradation
- Demonstrates transfer learning methodology (impressive for SIH judges)
- C-MAPSS is a well-known benchmark — adds credibility

---

## ADR-010: Extended Kalman Filter for State Estimation
**Status**: Accepted  
**Date**: 2026-09-04

**Context**: Need to fuse noisy sensor data with physics model predictions to estimate true engine state.

**Decision**: Use an Extended Kalman Filter (EKF), not UKF or particle filter.

**Rationale**:
- EKF is the industry standard for aerospace state estimation
- Our system is mildly nonlinear — EKF handles this well
- Computationally lightweight (< 2ms per update)
- Well-understood tuning procedures (Q and R matrices)

**Rejected Alternatives**:
- UKF: More accurate for highly nonlinear systems, but slower. Our system doesn't need it.
- Particle Filter: Best for multi-modal distributions, but far too expensive for 10 Hz real-time.
- No filter (raw sensors): Too noisy, ML models would need to be much larger.
