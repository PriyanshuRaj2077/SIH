# Engine Simulation & Synthetic Data Generation — AeroPulse

## 1. Simulation Architecture

The engine simulator is a core component of our system — it IS the engine in our demo. It must be physically credible, configurable, and capable of producing realistic degradation trajectories.

```
┌─────────────────────────────────────────────────────┐
│              ENGINE SIMULATOR (SimEngine)             │
│                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌────────────┐  │
│  │ Flight       │   │ Engine Core  │   │ Fault      │  │
│  │ Profile      │──▶│ (4-stroke    │◀──│ Injector   │  │
│  │ Generator    │   │  thermo)     │   │            │  │
│  └─────────────┘   └──────┬──────┘   └────────────┘  │
│                           │                           │
│                    ┌──────▼──────┐                     │
│                    │ Sensor      │                     │
│                    │ Emulator    │                     │
│                    │ (noise +    │                     │
│                    │  bias)      │                     │
│                    └──────┬──────┘                     │
│                           │                           │
│                    ┌──────▼──────┐                     │
│                    │ Telemetry   │                     │
│                    │ Stream      │                     │
│                    └─────────────┘                     │
└─────────────────────────────────────────────────────┘
```

---

## 2. Flight Profile Generator

### Mission Profile Types

We generate realistic MALE UAV flight profiles:

```
Altitude (ft)
25000 ─────────────────────────────────────────
      │                ╱─────────────────╲
20000 ─               ╱                   ╲
      │              ╱                     ╲
15000 ─             ╱                       ╲
      │            ╱                         ╲
10000 ─           ╱                           ╲
      │          ╱                             ╲
 5000 ─         ╱                               ╲
      │        ╱                                 ╲
    0 ─────────────────────────────────────────────
      0    1    2    4    8   12   16   20   22  24 hrs
          TAKE  CLIMB    CRUISE (MISSION)      DESC LAND
```

### Profile Segments

| Segment | Duration | Throttle | RPM | Altitude | Notes |
|---|---|---|---|---|---|
| Ground Idle | 5 min | 20% | 1400 | 0 ft | Warm-up |
| Takeoff | 2 min | 100% | 5800 | 0→500 ft | Max power |
| Climb | 30-60 min | 85% | 5200 | 500→25000 ft | Continuous climb |
| Cruise | 16-20 hrs | 55-65% | 4200-4800 | 25000 ft | Primary mission |
| Loiter | Variable | 50% | 4000 | 20000 ft | Station-keeping |
| Descent | 30 min | 30% | 3000 | 25000→500 ft | Idle descent |
| Approach/Land | 5 min | 40-60% | Variable | 500→0 ft | Controlled |

### Environmental Variations
```python
class EnvironmentModel:
    def get_conditions(self, altitude_ft, time_of_day):
        # ISA atmosphere model with perturbations
        T_isa = 288.15 - 0.00198 * altitude_ft  # K
        P_isa = 101325 * (T_isa / 288.15) ** 5.256  # Pa
        rho = P_isa / (287.05 * T_isa)  # kg/m³
        
        # Add realistic perturbations
        T_ambient = T_isa + np.random.normal(0, 3)  # ±3K variation
        P_ambient = P_isa * (1 + np.random.normal(0, 0.01))  # ±1%
        
        return T_ambient, P_ambient, rho
```

---

## 3. Engine Core Simulator

### Simplified Real-Time Model

For real-time operation, we use a **mean-value engine model (MVEM)** rather than a full crank-angle-resolved model. This runs faster while capturing the essential thermodynamic behavior.

```python
class PistonEngineModel:
    """
    Mean-Value Engine Model for 4-cylinder flat-four
    Runs at 10 Hz update rate
    """
    
    def step(self, throttle, altitude, dt=0.1):
        """
        Inputs:
            throttle: 0.0 to 1.0
            altitude: feet
            dt: time step (seconds)
        
        Outputs:
            Dictionary of engine state variables
        """
        # Air density at altitude
        rho = self._atmosphere(altitude)
        rho_ratio = rho / self.rho_sl
        
        # Manifold pressure (function of throttle and altitude)
        MAP = self.P_atm * throttle * rho_ratio * self.eta_vol
        
        # Air mass flow
        m_air = (MAP * self.V_d * self.RPM) / (2 * self.R * self.T_intake * 60)
        
        # Fuel mass flow (stoichiometric with mixture control)
        m_fuel = m_air / self.AFR
        
        # Indicated power (from combustion)
        Q_in = m_fuel * self.LHV * self.eta_comb
        P_indicated = Q_in * self.eta_thermal
        
        # Brake power (after mechanical losses)
        P_brake = P_indicated * self.eta_mech
        
        # Torque
        torque = P_brake / (self.RPM * 2 * np.pi / 60)
        
        # Temperature models
        EGT = self._compute_egt(m_fuel, m_air, self.eta_comb)
        CHT = self._compute_cht(P_brake, self.RPM, self.T_coolant)
        
        # Oil system
        T_oil_new = self._oil_temp_model(P_brake, self.T_oil, dt)
        P_oil = self._oil_pressure_model(self.RPM, T_oil_new)
        
        # Vibration model
        vib = self._vibration_model(self.RPM, P_brake, self.balance_factor)
        
        # Update state
        self.T_oil = T_oil_new
        # ... update other states
        
        return {
            'RPM': self.RPM,
            'CHT': CHT,
            'EGT': EGT,
            'oil_temp': T_oil_new,
            'oil_pressure': P_oil,
            'MAP': MAP,
            'fuel_flow': m_fuel * 3600,  # kg/hr
            'power_hp': P_brake / 745.7,
            'vibration_rms': vib,
            'coolant_temp': self.T_coolant,
        }
```

---

## 4. Fault Injection System

### 4.1 Degradation Profiles

Each fault mode follows a **mathematical degradation trajectory**:

```python
class DegradationProfile:
    """
    Models how a parameter degrades over time
    """
    
    @staticmethod
    def linear(t, onset, rate):
        """Gradual linear degradation after onset"""
        return max(0, rate * (t - onset)) if t > onset else 0
    
    @staticmethod  
    def exponential(t, onset, rate, knee_point):
        """Slow then accelerating degradation"""
        if t <= onset:
            return 0
        dt = t - onset
        return rate * (np.exp(dt / knee_point) - 1)
    
    @staticmethod
    def step_with_recovery(t, event_time, magnitude, recovery_rate):
        """Sudden partial failure with partial recovery"""
        if t < event_time:
            return 0
        return magnitude * np.exp(-recovery_rate * (t - event_time))
    
    @staticmethod
    def intermittent(t, onset, period, duration, magnitude):
        """Periodic fault that comes and goes"""
        if t < onset:
            return 0
        cycle_pos = (t - onset) % period
        return magnitude if cycle_pos < duration else 0
```

### 4.2 Fault Injection Catalog

| Fault | Parameter Affected | Degradation Type | Implementation |
|---|---|---|---|
| **Compression loss** | η_vol | Exponential | Reduce volumetric efficiency gradually |
| **Combustion degradation** | η_comb | Linear | Decrease combustion efficiency |
| **Oil pump wear** | P_oil | Linear | Reduce oil pressure at given RPM |
| **Cooling degradation** | CHT | Linear | Reduce cooling effectiveness |
| **Bearing wear** | vibration | Exponential | Add bearing-frequency vibration component |
| **Fuel injector clogging** | fuel_flow | Step + Linear | Sudden then progressive lean shift |
| **Ignition miss** | EGT | Intermittent | Periodic EGT drops on affected cylinder |
| **Turbo degradation** | MAP | Linear | Reduce boost pressure capability |
| **Exhaust leak** | EGT | Step | Sudden EGT drop post-leak |
| **Sensor drift** | Any sensor | Linear | Gradual bias in sensor reading |

### 4.3 Run-to-Failure Scenario Generation

```python
class ScenarioGenerator:
    """
    Generates complete engine life trajectories with known fault onsets
    """
    
    def generate_run_to_failure(self, total_hours=2000, fault_config=None):
        """
        Generate a complete engine life with one or more faults
        
        Returns:
            time_series: DataFrame with all sensor readings
            labels: fault onset times, fault types, true RUL at each timestep
        """
        if fault_config is None:
            fault_config = self._random_fault_config(total_hours)
        
        engine = PistonEngineModel()
        profile = FlightProfileGenerator()
        
        records = []
        for t in np.arange(0, total_hours * 3600, 0.1):  # 10 Hz
            hours = t / 3600
            
            # Get flight condition
            throttle, altitude = profile.get_conditions(hours)
            
            # Apply degradation
            for fault in fault_config:
                fault.apply(engine, hours)
            
            # Step engine
            state = engine.step(throttle, altitude)
            
            # Add sensor noise
            noisy_state = self._add_sensor_noise(state)
            
            # Compute true RUL
            rul = self._compute_true_rul(hours, fault_config)
            
            records.append({
                'time': t,
                'hours': hours,
                **noisy_state,
                'true_rul': rul,
                'fault_active': [f.name for f in fault_config if f.is_active(hours)],
                'health_state': 'degraded' if any(f.is_active(hours) for f in fault_config) else 'healthy'
            })
        
        return pd.DataFrame(records)
```

---

## 5. Sensor Noise Model

Real sensors are noisy. We add realistic noise profiles:

```python
class SensorNoiseModel:
    """
    Adds realistic noise to clean simulation signals
    """
    
    NOISE_PROFILES = {
        'RPM':          {'white_noise_std': 5,    'bias': 0,    'quantization': 1},
        'CHT':          {'white_noise_std': 1.5,  'bias': 0,    'quantization': 0.1},
        'EGT':          {'white_noise_std': 3.0,  'bias': 0,    'quantization': 0.5},
        'oil_temp':     {'white_noise_std': 0.5,  'bias': 0,    'quantization': 0.1},
        'oil_pressure': {'white_noise_std': 0.05, 'bias': 0,    'quantization': 0.01},
        'MAP':          {'white_noise_std': 0.3,  'bias': 0,    'quantization': 0.1},
        'fuel_flow':    {'white_noise_std': 0.2,  'bias': 0,    'quantization': 0.1},
        'vibration_rms':{'white_noise_std': 0.1,  'bias': 0,    'quantization': 0.01},
    }
    
    def add_noise(self, signal_name, clean_value, t):
        profile = self.NOISE_PROFILES[signal_name]
        
        # White Gaussian noise
        noise = np.random.normal(0, profile['white_noise_std'])
        
        # Slow bias drift (sensor aging)
        bias = profile['bias'] + 0.001 * t  # very slow drift
        
        # Quantization
        q = profile['quantization']
        noisy = clean_value + noise + bias
        quantized = np.round(noisy / q) * q
        
        # Occasional dropout (0.1% chance)
        if np.random.random() < 0.001:
            return np.nan  # Sensor dropout
        
        return quantized
```

---

## 6. Dataset Generation Plan

### 6.1 Dataset Composition

| Dataset | Scenarios | Fault Type | Purpose |
|---|---|---|---|
| **Healthy baseline** | 200 flights × 20 hrs | None | Anomaly detector training |
| **Single fault** | 100 per fault × 10 types | One fault each | Fault classifier training |
| **Multi-fault** | 200 scenarios | 2-3 concurrent faults | Robustness testing |
| **Edge cases** | 50 scenarios | Extreme conditions | Stress testing |
| **Run-to-failure** | 100 trajectories | Progressive to failure | RUL training |

### 6.2 Data Format
```
output/
├── healthy/
│   ├── flight_0001.parquet
│   ├── flight_0002.parquet
│   └── ...
├── faulty/
│   ├── compression_loss/
│   ├── oil_system/
│   ├── bearing_wear/
│   └── ...
├── run_to_failure/
│   ├── trajectory_001.parquet
│   ├── trajectory_002.parquet
│   └── ...
└── metadata/
    ├── fault_labels.json
    ├── scenario_configs.json
    └── dataset_statistics.json
```

### 6.3 File Schema (Parquet)
```
Columns:
  timestamp        float64   Unix timestamp
  hours            float64   Engine hours
  throttle         float64   Throttle position (0-1)
  altitude_ft      float64   Flight altitude
  RPM              float64   Engine speed
  CHT_1..4         float64   Cylinder head temps (per cylinder)
  EGT_1..4         float64   Exhaust gas temps (per cylinder)
  oil_temp         float64   Oil temperature
  oil_pressure     float64   Oil pressure
  MAP              float64   Manifold absolute pressure
  fuel_flow        float64   Fuel flow rate
  vibration_x      float64   Vibration X-axis
  vibration_y      float64   Vibration Y-axis
  vibration_z      float64   Vibration Z-axis
  coolant_temp     float64   Coolant temperature
  voltage          float64   Generator voltage
  fault_label      string    Active fault code(s) or "healthy"
  true_rul         float64   True remaining useful life (hours)
  health_score     float64   True health score (0-100)
```

---

## 7. Validation Strategy

### Simulation Fidelity Checks
1. **Steady-state validation**: At fixed throttle/altitude, do outputs match published Rotax performance curves?
2. **Transient validation**: Does engine response to throttle changes have realistic time constants?
3. **Altitude effects**: Does power decrease with altitude as expected (density altitude)?
4. **Temperature correlations**: Are CHT/EGT/oil_temp relationships physically consistent?

### Statistical Properties
1. Healthy data should form a well-defined cluster in feature space
2. Fault data should be separable from healthy with realistic margins
3. Degradation trajectories should be monotonic (no spontaneous recovery)
4. Sensor noise should match published specs for aviation sensors
