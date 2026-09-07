# Digital Twin Design — AeroPulse

## 1. What Is Our Digital Twin?

A **Digital Twin** is not just a 3D model. It is a **live computational model** that:
1. Receives real sensor data (or simulated data)
2. Runs a physics model to predict what the engine *should* be doing
3. Compares prediction vs. reality to detect anomalies
4. Tracks parameter drift to estimate degradation
5. Projects forward to predict remaining useful life

```
                    ┌─────────────────────────────┐
                    │       PHYSICAL ENGINE         │
                    │   (Real or Simulated Data)     │
                    └──────────────┬────────────────┘
                                   │ Sensor Data
                                   ▼
                    ┌─────────────────────────────┐
                    │        DIGITAL TWIN          │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │   Physics Model          │  │
                    │  │   (Thermodynamic +        │  │
                    │  │    Mechanical)            │  │
                    │  └────────────┬──────────────┘  │
                    │              │                  │
                    │  ┌───────────▼──────────────┐  │
                    │  │   State Estimator (EKF)   │  │
                    │  │   Fuse model + sensors    │  │
                    │  └────────────┬──────────────┘  │
                    │              │                  │
                    │  ┌───────────▼──────────────┐  │
                    │  │   Residual Analysis       │  │
                    │  │   Δ = actual - expected   │  │
                    │  └────────────┬──────────────┘  │
                    │              │                  │
                    │  ┌───────────▼──────────────┐  │
                    │  │   Parameter Tracker       │  │
                    │  │   Track degradation       │  │
                    │  └──────────────────────────┘  │
                    └─────────────────────────────┘
```

---

## 2. Physics Engine — Thermodynamic Model

### 2.1 Four-Stroke Cycle Model

We model a single cylinder through 720° of crankshaft rotation:

#### Cylinder Volume as Function of Crank Angle
```
V(θ) = V_cl + (V_disp / 2) × [l_a + 1 - cos(θ) - √(l_a² - sin²(θ))]

where:
  V_cl   = clearance volume = V_disp / (CR - 1)
  V_disp = displaced volume = π/4 × bore² × stroke
  l_a    = connecting rod length / crank radius
  θ      = crank angle (0° = TDC)
  CR     = compression ratio
```

#### Reference Engine Parameters (Rotax 912 ULS-derived)
```python
ENGINE_PARAMS = {
    "bore": 0.084,          # m (84 mm)
    "stroke": 0.061,        # m (61 mm)  
    "con_rod_length": 0.122, # m
    "compression_ratio": 10.5,
    "num_cylinders": 4,
    "displacement": 1.352e-3, # m³ (1352 cc)
    "max_rpm": 5800,
    "idle_rpm": 1400,
    "max_power_hp": 100,
    "firing_order": [1, 3, 4, 2],
}
```

#### Thermodynamic State Equations

**Compression/Expansion (polytropic process):**
```
P × V^γ = constant

where γ = 1.3 (compression), γ = 1.25 (expansion)
```

**Heat Release (Wiebe function for combustion):**
```
x(θ) = 1 - exp[-a × ((θ - θ_start) / Δθ)^(m+1)]

Q_released(θ) = Q_total × dx/dθ

where:
  a = 6.908 (99.9% burn efficiency)
  m = 2 (shape factor)
  θ_start = spark timing (typically -20° to -10° BTDC)
  Δθ = burn duration (~40-60°)
  Q_total = m_fuel × LHV × η_comb
```

**First Law of Thermodynamics (per crank angle):**
```
dP/dθ = (-γ × P / V) × dV/dθ + ((γ-1) / V) × (dQ_comb/dθ - dQ_wall/dθ)
```

**Heat Transfer (Woschni correlation):**
```
h = 3.26 × D^(-0.2) × P^0.8 × T^(-0.55) × w^0.8

where w = C₁ × S_p + C₂ × (V_d × T_r) / (P_r × V_r) × (P - P_motored)
```

### 2.2 Multi-Cylinder Extension

For a 4-cylinder flat-four engine:
- Each cylinder is phase-shifted by 180° (flat-four firing)
- Firing order: 1-3-4-2 with 180° intervals
- Total torque = Σ individual cylinder torques

### 2.3 Auxiliary Systems Model

| System | Model | Key Parameters |
|---|---|---|
| **Lubrication** | Oil temperature rise model | Oil flow rate, heat rejection, ambient temp |
| **Cooling** | Thermal network (liquid cooling) | Coolant flow, radiator effectiveness |
| **Fuel System** | Fuel flow vs. throttle + altitude | Mixture ratio, injector flow characteristic |
| **Turbocharger** (optional) | Compressor/turbine maps | Pressure ratio, efficiency, spool dynamics |
| **Gearbox** | Gear ratio + friction model | Reduction ratio (2.273:1 for Rotax 912) |

---

## 3. State Estimator — Extended Kalman Filter

### Why EKF?
The engine state cannot be directly measured — we infer it from noisy sensors. The EKF:
1. Predicts the next state using the physics model
2. Corrects the prediction using actual sensor readings
3. Provides an **optimal estimate** of the true state

### State Vector
```
x = [P_cyl, T_cyl, T_oil, T_coolant, RPM, m_fuel_dot, η_vol, η_comb, η_mech]

where:
  P_cyl     = cylinder pressure (Pa)
  T_cyl     = cylinder gas temperature (K)
  T_oil     = oil temperature (K)
  T_coolant = coolant temperature (K)
  RPM       = engine speed (rev/min)
  m_fuel_dot = fuel mass flow rate (kg/s)
  η_vol     = volumetric efficiency (degradation indicator)
  η_comb    = combustion efficiency (degradation indicator)
  η_mech    = mechanical efficiency (degradation indicator)
```

### Measurement Vector
```
z = [RPM_meas, CHT_meas, EGT_meas, T_oil_meas, P_oil_meas, MAP_meas, V_vib]
```

### EKF Equations
```
Prediction:
  x̂(k|k-1) = f(x̂(k-1|k-1), u(k))     // physics model
  P(k|k-1)  = F(k) P(k-1|k-1) F(k)ᵀ + Q(k)

Update:
  K(k) = P(k|k-1) H(k)ᵀ [H(k) P(k|k-1) H(k)ᵀ + R(k)]⁻¹
  x̂(k|k) = x̂(k|k-1) + K(k) [z(k) - h(x̂(k|k-1))]
  P(k|k) = [I - K(k) H(k)] P(k|k-1)
```

### Key: The Degradation Parameters
The last three elements of the state vector (η_vol, η_comb, η_mech) are **health indicators**:
- A healthy engine: η_vol ≈ 0.85, η_comb ≈ 0.98, η_mech ≈ 0.92
- As the engine degrades, these slowly decrease
- The EKF **tracks their drift** without needing explicit fault labels

---

## 4. Residual Generation

### What Are Residuals?
```
r(k) = z(k) - h(x̂(k|k-1))
```

The residual is the **difference between what we measure and what the physics model predicted**. In a healthy engine, residuals are small and normally distributed. Deviations indicate:

| Residual Pattern | Interpretation |
|---|---|
| Single large spike | Sensor glitch or sudden event |
| Sustained positive bias | Systematic degradation in that parameter |
| Increasing variance | Intermittent fault or loose connection |
| Correlated multi-parameter shift | Specific fault mode signature |

### Residual Features for ML
For each residual signal, we compute over a sliding window:
- Mean, variance, skewness, kurtosis
- RMS value
- Peak-to-peak amplitude
- Zero-crossing rate
- FFT dominant frequency and amplitude
- CUSUM statistic (cumulative sum for change detection)

---

## 5. Digital Twin Synchronization Loop

The digital twin runs a continuous update cycle at **10 Hz** (matching sensor sampling):

```
Every 100ms:
  1. Receive new sensor frame [z(k)]
  2. Run physics model forward by Δt → get x̂_predicted
  3. Run EKF update → get x̂_corrected
  4. Compute residuals r(k)
  5. Update residual feature buffer (sliding window)
  6. If window full → trigger ML inference
  7. Publish updated state to dashboard
```

### Performance Target
- Physics model step: < 5ms
- EKF update: < 2ms
- Residual computation: < 1ms
- ML inference: < 20ms
- Total loop budget: < 50ms (leaves margin for 10 Hz operation)

---

## 6. What Makes This a "Digital Twin" and Not Just a "Model"

| Feature | Simple Model | Our Digital Twin |
|---|---|---|
| Uses sensor data | ❌ Open-loop | ✅ Closed-loop (EKF) |
| Updates in real-time | ❌ Batch | ✅ 10 Hz continuous |
| Tracks individual engine | ❌ Generic | ✅ Instance-specific parameters |
| Detects degradation | ❌ | ✅ Parameter drift tracking |
| Predicts future state | ❌ | ✅ RUL projection |
| Actionable output | ❌ | ✅ Health score + recommendations |

The digital twin is **personalized to the specific engine instance** — as it receives more data, it refines its internal parameters to match that particular engine's behavior.
