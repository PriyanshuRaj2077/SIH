# Domain Research — Aero Piston Engines in MALE UAVs

## 1. Reference Engine Platform: DRDO TAPAS BH-201

### Engine Evolution
| Phase | Engine | Type | Power |
|---|---|---|---|
| Early Prototypes | NPO Saturn 36T | Turboprop | ~100 HP each (×2) |
| Indigenous Development | VRDE/Jayem 2.2L | 4-cyl inline turbo diesel | 180 HP |
| Reference (our model) | Rotax 912/914 class | 4-cyl flat-four, 4-stroke | 100-115 HP |

### Why We Use Rotax 912/914 as Reference
- Publicly documented specifications and operating limits
- Widely used in small/medium UAVs globally
- Well-studied in aviation maintenance literature
- Similar operational parameters to typical MALE UAV piston engines
- DRDO's actual engine specs are classified — Rotax provides a credible proxy

### TAPAS BH-201 Key Specs
| Parameter | Value |
|---|---|
| Wingspan | 20.6 m |
| Length | 9.5 m |
| Payload | 350 kg |
| Empty Weight | 1,800 kg |
| Cruise Speed | ~225 km/h |
| Service Ceiling | 30,000+ ft |
| Endurance | 18-24 hours |
| Engine Control | FADEC |

---

## 2. Aero Piston Engine Fundamentals

### Operating Principle
Four-stroke Otto/diesel cycle:
1. **Intake** → Air-fuel mixture drawn into cylinder
2. **Compression** → Piston compresses mixture (compression ratio ~9:1 to 10.5:1)
3. **Power** → Combustion drives piston down
4. **Exhaust** → Burned gases expelled

### Critical Monitored Parameters

| Parameter | Sensor | Units | Normal Range (Rotax 912) | Criticality |
|---|---|---|---|---|
| **RPM** | Hall effect / pulse | rev/min | 1,400 - 5,800 | HIGH |
| **CHT** | Thermocouple / RTD | °C | 80 - 150 | HIGH |
| **EGT** | K-type thermocouple | °C | 650 - 880 | HIGH |
| **Oil Temperature** | RTD | °C | 50 - 140 | HIGH |
| **Oil Pressure** | Pressure transducer | bar | 2.0 - 7.0 | HIGH |
| **Manifold Pressure** | MAP sensor | inHg / kPa | 17 - 35 inHg | MEDIUM |
| **Fuel Flow** | Turbine flow meter | L/hr | 10 - 25 | MEDIUM |
| **Fuel Pressure** | Pressure transducer | bar | 0.15 - 0.40 | MEDIUM |
| **Vibration** | MEMS accelerometer (3-axis) | g / mm/s | Baseline-dependent | HIGH |
| **Coolant Temperature** | RTD | °C | 60 - 120 | MEDIUM |
| **Battery/Generator Voltage** | Voltage sensor | V | 12 - 14.4 | LOW |

### Key Operating Envelopes
```
Altitude: 0 - 32,000 ft (density altitude affects power)
Temperature: -40°C to +50°C ambient
Power settings: Idle / Cruise / Climb / Max Continuous
Mixture: Auto (FADEC) or lean/rich
```

---

## 3. Common Failure Modes — Piston Engines

### Catastrophic Failures (loss of power)
| Failure Mode | Root Cause | Observable Symptoms |
|---|---|---|
| Bearing seizure | Oil starvation, contamination | Oil pressure drop, temperature spike, vibration |
| Piston ring failure | Wear, thermal fatigue | Compression loss, EGT anomaly, oil consumption |
| Connecting rod failure | Fatigue, over-speed | Vibration spike, sudden RPM change |
| Ignition failure | Spark plug fouling, magneto failure | EGT drop on affected cylinder, RPM fluctuation |
| Fuel system failure | Injector clogging, pump failure | Fuel pressure drop, lean mixture, EGT rise |

### Degradation Modes (gradual)
| Degradation | Physics | Observable Trend |
|---|---|---|
| Cylinder wear | Friction, thermal cycling | Increasing oil consumption, compression drop |
| Valve seat recession | Thermal + mechanical erosion | Gradually rising CHT, EGT shift |
| Turbocharger wear (914) | Bearing wear, blade erosion | MAP decrease at same throttle, lag increase |
| Cooling system degradation | Thermostat, hose, pump wear | CHT/coolant temp drift upward |
| Gearbox wear | Gear tooth fatigue | Vibration frequency content changes |

### Vibration Signature Analysis
| Frequency Component | Source |
|---|---|
| 1× RPM | Propeller imbalance, crankshaft unbalance |
| 2× RPM | Misalignment, reciprocating forces |
| 0.5× RPM (sub-harmonic) | Gearbox issues (reduction gear) |
| High-frequency broadband | Bearing defects |
| Cylinder firing frequency | Combustion irregularities |

---

## 4. State of the Art — Digital Twins for Engines

### Industry Leaders
- **GE Aviation**: Digital twin for LEAP and GE9X turbofans (Predix platform)
- **Rolls-Royce**: IntelligentEngine — uses Azure DT for real-time monitoring
- **Pratt & Whitney**: EngineWise for predictive analytics
- **Siemens**: MindSphere-based digital twin platform

### Academic State of the Art
| Approach | Description | Maturity |
|---|---|---|
| Physics-based model + ML correction | Thermodynamic model provides baseline; ML corrects residuals | HIGH |
| Pure data-driven (LSTM, Transformer) | End-to-end from sensor data to prediction | MEDIUM |
| Physics-Informed Neural Networks (PINNs) | Neural network with physics loss terms | EMERGING |
| Hybrid ensemble (XGBoost + mechanism) | Fast, interpretable, production-ready | HIGH |
| Bayesian deep learning | Quantified uncertainty on predictions | EMERGING |
| Graph Neural Networks | Model component interactions as graphs | EMERGING |

### Key Insight for Our Design
> **The winning approach is HYBRID**: Physics model provides the "expected" behavior; ML detects deviations from expected behavior. This is more robust than pure data-driven and more flexible than pure physics.

---

## 5. Available Datasets & Data Strategy

### Public Datasets (for benchmarking and transfer learning)
| Dataset | Source | Relevance |
|---|---|---|
| NASA C-MAPSS (FD001-FD004) | NASA PCoE | Turbofan run-to-failure — use for RUL model architecture benchmarking |
| NASA N-CMAPSS | NASA PCoE | New CMAPSS with flight-realistic profiles |
| CWRU Bearing Dataset | Case Western Reserve | Bearing fault detection — applicable to engine bearings |
| PHM08 Challenge | PHM Society | Turbofan prognostics challenge data |

### Our Data Strategy: Synthetic Data Generation
Since no public piston engine run-to-failure dataset exists, we MUST generate our own:
1. Build a physics-based engine simulator
2. Define nominal operating profiles (cruise, climb, descent)
3. Inject fault degradation trajectories mathematically
4. Add realistic sensor noise and environmental effects
5. Generate labeled datasets with known fault onset times and RUL values

This is not a weakness — it's what GE and Rolls-Royce do internally. Our simulator IS part of the digital twin.

---

## 6. References

1. Rotax 912/914 Installation Manual, BRP-Rotax
2. "Digital Twin for Aeroengine Performance Diagnosis" — MDPI Sensors, 2023
3. "Study on Fault Prognostics and Health Management for UAV" — ResearchGate
4. "Health Status Assessment of UAV Engine Based on AHP and Multimodal Fusion" — SciOpen
5. NASA C-MAPSS Dataset Documentation — NASA PCoE
6. DRDO TAPAS BH-201 specifications — public domain press releases
7. "Physics-Informed Neural Networks for Engine Modeling" — various arxiv papers
