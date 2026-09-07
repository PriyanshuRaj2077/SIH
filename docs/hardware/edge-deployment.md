# Hardware & Edge Deployment Considerations — AeroPulse

## 1. Context: SIH26054 is a SOFTWARE Problem Statement

DRDO has categorized this as a **Software** problem. However, discussing hardware architecture shows:
- Technical depth and awareness of real deployment constraints
- Understanding of edge vs. cloud trade-offs for mission-critical systems
- Readiness for production transition beyond the hackathon

---

## 2. Sensor Hardware (Reference Architecture)

### Sensor Suite for a Typical MALE UAV Piston Engine

| Sensor | Type | Sampling Rate | Interface | Typical Part |
|---|---|---|---|---|
| RPM | Hall effect | 100 Hz | Digital pulse | Honeywell SS495A |
| CHT (×4) | K-type thermocouple | 10 Hz | Analog (ADC) | Omega K-type probe |
| EGT (×4) | K-type thermocouple | 10 Hz | Analog (ADC) | Omega K-type probe |
| Oil Temperature | PT100 RTD | 10 Hz | Analog (ADC) | Honeywell RTD |
| Oil Pressure | Piezo-resistive | 10 Hz | 4-20mA | Keller 23SY |
| MAP | MEMS pressure | 20 Hz | SPI/I2C | Bosch BMP388 |
| Fuel Flow | Turbine flowmeter | 10 Hz | Pulse | FTI FT-60 |
| Vibration (3-axis) | MEMS accelerometer | 1000 Hz | SPI | ADXL355 |
| Coolant Temp | NTC thermistor | 10 Hz | Analog | Standard NTC |
| Voltage | Voltage divider | 10 Hz | Analog | Resistor divider |

### Data Acquisition Architecture (On-Aircraft)
```
Sensors ──▶ ADC / Signal Conditioning ──▶ Edge MCU ──▶ Flight Computer ──▶ Datalink
                                          (STM32 /                         (SATCOM /
                                           Raspberry Pi)                    LOS radio)
```

---

## 3. Edge Computing for Inference

### On-Board Processing Requirements

For a production system, critical inference runs ON the aircraft:

| Processing Level | Where | Latency | Function |
|---|---|---|---|
| **Level 0** | MCU (STM32) | < 1ms | Sensor validation, range checks |
| **Level 1** | Edge SBC (RPi/Jetson) | < 50ms | Anomaly detection, health score |
| **Level 2** | Ground station | < 1s | Full RUL estimation, trending |
| **Level 3** | Cloud/HPC | Minutes | Historical analysis, model retraining |

### Edge Hardware Options

| Platform | Compute | Power | Suitability |
|---|---|---|---|
| **Raspberry Pi 5** | ARM Cortex-A76, 8GB | 5-15W | Good for demo, limited AI |
| **NVIDIA Jetson Orin Nano** | ARM + 1024 CUDA cores | 7-15W | Ideal for edge AI inference |
| **STM32H7** | ARM Cortex-M7, 480MHz | < 1W | Sensor acquisition only |
| **Xilinx Zynq (FPGA+ARM)** | Programmable logic + ARM | 3-10W | Deterministic, certifiable |

### Recommended for Production: NVIDIA Jetson Orin Nano
- Runs ONNX models natively via TensorRT
- Low power (7W in 15W mode)
- Sufficient for all Level 0+1 inference
- Python + CUDA stack familiar to ML teams

### For Our Demo: Standard Laptop
- All processing runs on a single machine
- Simulator + Backend + Frontend + ML inference co-located
- Docker Compose for easy deployment

---

## 4. Communication Architecture

### Demo Setup
```
┌───────────────────────────────────────────────┐
│            Single Laptop / Desktop             │
│                                                │
│  ┌──────────┐  WebSocket   ┌──────────────┐   │
│  │Simulator │─────────────▶│  FastAPI      │   │
│  │(Python)  │              │  Backend      │   │
│  └──────────┘              └──────┬───────┘   │
│                                   │            │
│                              WebSocket         │
│                                   │            │
│                            ┌──────▼───────┐   │
│                            │  React       │   │
│                            │  Dashboard   │   │
│                            └──────────────┘   │
└───────────────────────────────────────────────┘
```

### Production Architecture (Future)
```
┌──────────────────┐          ┌──────────────────┐
│   ON AIRCRAFT     │          │  GROUND STATION   │
│                    │  Radio   │                    │
│ Sensors → MCU     │─────────▶│  Backend Server    │
│   → Edge SBC     │  Datalink │  Full DT + ML     │
│   (Level 0+1)    │          │  (Level 2+3)       │
│                    │          │                    │
│ Local anomaly     │          │  Dashboard         │
│ detection +       │          │  RUL estimation    │
│ health score      │          │  Mission planning  │
└──────────────────┘          └──────────────────┘
```

---

## 5. Power & Weight Budget (Production Reference)

| Component | Weight | Power | Notes |
|---|---|---|---|
| Sensor suite | ~500g | < 2W | Mostly passive sensors |
| Signal conditioning | ~200g | < 1W | ADC board |
| Edge SBC (Jetson Nano) | ~200g | 7-15W | AI inference |
| Cabling & connectors | ~300g | - | Aviation-grade |
| **Total** | **~1.2 kg** | **~18W** | Acceptable for 1800 kg UAV |

This represents < 0.07% of aircraft weight and negligible power draw.

---

## 6. Cybersecurity Considerations

### For Production Deployment
| Concern | Mitigation |
|---|---|
| Data integrity | Signed telemetry frames (HMAC) |
| Replay attacks | Monotonic timestamps, nonce |
| Model poisoning | Model integrity hash verification |
| Physical access | Tamper-evident enclosure |
| Datalink security | AES-256 encryption on radio link |

### For Our Demo
- All communication is localhost (no network exposure)
- No authentication needed for demo purposes
- Focus on functionality, not security hardening
