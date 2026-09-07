# SIH26054 — Official Problem Statement

## Verification Status: ✅ VERIFIED

**Source**: [sih.gov.in/sih2026PS](https://sih.gov.in/sih2026PS) (accessed 2026-09-04)  
**Cross-verified against**: Multiple independent sources (DSCE portal, BlinknBuild SIH tracker, GitHub repositories)

---

## Problem Statement

> **AI-Enabled Real-Time Digital Twin System for Health Monitoring, Fault Prediction and Mission Reliability Enhancement of Aero Piston Engines used in MALE UAVs**

| Field | Value |
|---|---|
| **PS Code** | SIH26054 |
| **Organization** | DRDO (Defence Research and Development Organisation) |
| **Category** | Software |
| **Theme** | Robotics and Drones |

---

## Decomposition of Requirements

### Explicit Requirements (from title)

1. **AI-Enabled** → Must use artificial intelligence / machine learning (not just rule-based)
2. **Real-Time** → System must operate with low-latency, not batch/offline
3. **Digital Twin** → Virtual replica of the physical engine that mirrors its state
4. **Health Monitoring** → Continuous assessment of engine condition
5. **Fault Prediction** → Anticipate failures before they occur (prognostics)
6. **Mission Reliability Enhancement** → Actionable output that improves mission success rate
7. **Aero Piston Engines** → Specific engine class (NOT turbofan/turboprop — piston-driven)
8. **MALE UAVs** → Medium-Altitude Long-Endurance Unmanned Aerial Vehicles

### Implied Requirements

1. The system must work with **realistic sensor data** (or high-fidelity simulated data)
2. Must demonstrate a **working prototype/MVP** — not just a research paper
3. Must show **operational value** — DRDO wants something that could actually be deployed
4. Must handle the specific **failure modes** of piston engines (not generic turbomachinery)
5. **Remaining Useful Life (RUL)** estimation is strongly implied by "fault prediction"
6. **Condition-Based Maintenance (CBM)** is the operational paradigm being targeted

---

## Context: Why This Matters

### The Operational Problem
MALE UAVs like DRDO's TAPAS BH-201 (Rustom-II) fly 18-24 hour missions at 25,000-32,000 ft. Engine failure mid-mission means:
- **Loss of a ₹100+ crore asset** (the UAV itself)
- **Mission failure** (surveillance gap, intelligence loss)
- **Potential collateral damage** on ground

Currently, maintenance is **calendar/hour-based** (Time Between Overhaul — TBO). This leads to:
- Over-maintenance of healthy engines (wasted resources)
- Under-maintenance of degraded engines (catastrophic risk)

### What DRDO Wants
A shift from **scheduled maintenance → condition-based maintenance** using:
- A digital twin that mirrors the engine's real health
- AI that can detect anomalies and predict remaining life
- A system that tells the mission controller: "This engine is safe for X more hours"

---

## Scope Boundaries

### In Scope
- Software system (digital twin + AI + dashboard)
- Piston engine physics modeling
- Synthetic data generation for fault scenarios
- Real-time inference pipeline
- Health scoring and RUL estimation
- Fault classification and anomaly detection

### Out of Scope (but acknowledged)
- Actual hardware sensor integration (no access to real engine)
- Full DO-178C/DO-254 certification (production avionics standard)
- Real flight test validation
- Classified engine specifications

### Honest Limitations We Must Acknowledge
1. We will NOT have real engine telemetry — we must generate **high-fidelity synthetic data**
2. Our physics model will be based on **published literature**, not DRDO's proprietary specs
3. RUL predictions cannot be validated against real failure data — we validate against our simulation
4. "Real-time" in our demo means processing speed, not actual flight integration
