# References & Bibliography — AeroPulse

## 1. Official Sources

| # | Reference | URL | Used For |
|---|---|---|---|
| R01 | SIH 2026 Problem Statements (Official) | https://sih.gov.in/sih2026PS | Problem statement verification |
| R02 | SIH 2026 Guidelines | https://sih.gov.in/letters/2026/SIH%202026%20Guidelines.pdf | Competition rules |

---

## 2. Engine & Domain References

| # | Reference | Source | Used For |
|---|---|---|---|
| R10 | Rotax 912/914 Installation Manual | BRP-Rotax (flyrotax.com) | Engine parameters, operating limits |
| R11 | Rotax 912 ULS Operators Manual | BRP-Rotax | Normal operating procedures |
| R12 | DRDO TAPAS BH-201 specifications | Public press releases, PIB | MALE UAV context |
| R13 | VRDE Indigenous UAV Engine | DRDO press releases | Indian engine development context |

---

## 3. Digital Twin & PHM Literature

| # | Reference | Authors / Source | Key Contribution |
|---|---|---|---|
| R20 | "A Novel Digital Twin Framework for Aeroengine Performance Diagnosis" | MDPI Sensors, 2023 | Hybrid physics+data approach |
| R21 | "Study on Fault Prognostics and Health Management for UAV" | ResearchGate | PHM architecture for UAVs |
| R22 | "Health Status Assessment of UAV Engine Based on AHP and Multimodal Fusion" | SciOpen | Multi-parameter health scoring |
| R23 | "Digital Twin-Driven Machine Condition Monitoring: A Literature Review" | Smart Eureka, 2024 | State of the art survey |
| R24 | "Physics-Informed Neural Networks: A Deep Learning Framework" | Raissi et al., JCP 2019 | PINN methodology |
| R25 | "Remaining Useful Life Estimation Using LSTM" | Various (IEEE, MDPI) | LSTM for RUL |

---

## 4. Datasets

| # | Dataset | Source | URL | Used For |
|---|---|---|---|---|
| R30 | NASA C-MAPSS (FD001-FD004) | NASA PCoE | https://data.nasa.gov/Aerospace/CMAPSS-Jet-Engine-Simulated-Data/ | Transfer learning, benchmarking |
| R31 | NASA N-CMAPSS | NASA PCoE | NASA repository | Flight-realistic profiles |
| R32 | CWRU Bearing Dataset | Case Western Reserve Univ. | https://engineering.case.edu/bearingdatacenter | Bearing fault detection |

---

## 5. Software & Libraries

| # | Library | Version | License | Used For |
|---|---|---|---|---|
| R40 | Python | 3.11+ | PSF | Core language |
| R41 | FastAPI | 0.100+ | MIT | Backend API framework |
| R42 | NumPy | 1.24+ | BSD | Numerical computation |
| R43 | SciPy | 1.11+ | BSD | ODE solvers, signal processing |
| R44 | PyTorch | 2.0+ | BSD | ML model training |
| R45 | ONNX Runtime | 1.15+ | MIT | ML model inference |
| R46 | scikit-learn | 1.3+ | BSD | Classical ML (Isolation Forest) |
| R47 | XGBoost | 2.0+ | Apache 2.0 | Gradient boosting |
| R48 | Pandas | 2.0+ | BSD | Data manipulation |
| R49 | FilterPy | 1.4+ | MIT | Kalman filter |
| R50 | React | 18+ | MIT | Frontend UI |
| R51 | Three.js / R3F | Latest | MIT | 3D visualization |
| R52 | Recharts | 2.0+ | MIT | Charts & gauges |
| R53 | Docker | Latest | Apache 2.0 | Containerization |

---

## 6. Standards & Regulatory (Reference Only)

| # | Standard | Relevance |
|---|---|---|
| R60 | SAE ARP4761 | Safety assessment process for aerospace systems |
| R61 | DO-178C | Software considerations for airborne systems |
| R62 | DO-254 | Hardware considerations for airborne systems |
| R63 | MIL-STD-1629A | FMECA methodology |
| R64 | ISO 13374 | Condition monitoring and diagnostics |
| R65 | SAE AS5553 | Counterfeit parts avoidance |

> **Note**: Our demo is NOT compliant with these standards. They are listed for awareness and to show we understand the production pathway.

---

## 7. Related SIH Problem Statements (for context)

| PS Code | Title | Organization | Overlap |
|---|---|---|---|
| SIH26054 | **Our PS** — Digital Twin for Aero Piston Engine | DRDO | This is us |
| Other DRDO PS | Various defense tech problems | DRDO | Same organization, different domains |

---

## 8. Academic Textbooks

| # | Title | Authors | Relevance |
|---|---|---|---|
| T01 | "Internal Combustion Engine Fundamentals" | Heywood, J.B. | Thermodynamic modeling |
| T02 | "Prognostics and Health Management of Engineering Systems" | Kim, N.H. et al. | PHM methodology |
| T03 | "Deep Learning" | Goodfellow, Bengio, Courville | ML theory |
| T04 | "Bayesian Filtering and Smoothing" | Särkkä, S. | Kalman filter theory |
| T05 | "Gas Turbine Engineering Handbook" | Boyce, M.P. | Engine thermodynamics (adapted) |
