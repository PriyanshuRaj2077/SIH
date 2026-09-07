# Data Strategy & Pipeline — AeroPulse

## 1. Data Flow End-to-End

```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Data Source  │────▶│  Stream Layer  │────▶│  Processing Layer │────▶│  Storage     │
│              │     │               │     │                  │     │              │
│ • Simulator  │     │ • WebSocket   │     │ • Validation     │     │ • In-Memory  │
│ • (Future:   │     │ • 10 Hz rate  │     │ • Windowing      │     │   Ring Buffer │
│   Real       │     │ • JSON frames │     │ • Feature Calc   │     │ • Parquet    │
│   Sensors)   │     │               │     │ • Normalization   │     │   (persist)  │
└──────────────┘     └───────────────┘     └──────────────────┘     └──────────────┘
```

---

## 2. Real-Time Data Frame Format

Each sensor frame transmitted at 10 Hz:

```json
{
    "timestamp": 1725456789.123,
    "engine_hours": 1423.7,
    "flight_phase": "cruise",
    "altitude_ft": 25000,
    "throttle": 0.62,
    "sensors": {
        "RPM": 4520,
        "CHT": [118.2, 120.1, 117.5, 119.8],
        "EGT": [742.3, 738.9, 745.1, 740.2],
        "oil_temp": 98.3,
        "oil_pressure": 4.2,
        "MAP": 24.5,
        "fuel_flow": 18.7,
        "vibration": [0.42, 0.38, 0.55],
        "coolant_temp": 88.2,
        "voltage": 13.8
    }
}
```

**Frame size**: ~400 bytes JSON → at 10 Hz = **4 KB/s** (trivial bandwidth)

---

## 3. Feature Engineering Pipeline

### 3.1 Sliding Window Features

Window size: 300 samples (30 seconds at 10 Hz)

For each of the 8 primary sensor signals:

```python
def compute_window_features(window: np.ndarray) -> dict:
    """Compute statistical features over a sliding window"""
    return {
        'mean': np.mean(window),
        'std': np.std(window),
        'skewness': scipy.stats.skew(window),
        'kurtosis': scipy.stats.kurtosis(window),
        'rms': np.sqrt(np.mean(window**2)),
        'delta': (window[-1] - window[0]) / len(window),  # trend
        'peak_to_peak': np.max(window) - np.min(window),
        'zero_crossing_rate': zero_crossings(window) / len(window),
    }
```

### 3.2 Cross-Sensor Features

```python
def compute_cross_features(sensors: dict) -> dict:
    """Compute inter-sensor correlation features"""
    return {
        'cht_spread': max(sensors['CHT']) - min(sensors['CHT']),
        'egt_spread': max(sensors['EGT']) - min(sensors['EGT']),
        'egt_cht_ratio': np.mean(sensors['EGT']) / np.mean(sensors['CHT']),
        'power_fuel_ratio': sensors['power_est'] / sensors['fuel_flow'],
        'oil_temp_pressure_product': sensors['oil_temp'] * sensors['oil_pressure'],
        'vibration_magnitude': np.linalg.norm(sensors['vibration']),
    }
```

### 3.3 Spectral Features (for vibration)

```python
def compute_spectral_features(vibration_window: np.ndarray, rpm: float, fs=10) -> dict:
    """FFT-based vibration analysis"""
    freqs, psd = scipy.signal.welch(vibration_window, fs=fs)
    
    # Engine rotation frequency
    f_rot = rpm / 60  # Hz
    
    return {
        'psd_1x_rpm': psd_at_freq(psd, freqs, f_rot),
        'psd_2x_rpm': psd_at_freq(psd, freqs, 2 * f_rot),
        'psd_0.5x_rpm': psd_at_freq(psd, freqs, 0.5 * f_rot),
        'dominant_freq': freqs[np.argmax(psd)],
        'spectral_centroid': np.sum(freqs * psd) / np.sum(psd),
        'total_power': np.sum(psd),
    }
```

---

## 4. Data Normalization

### Min-Max Scaling (per sensor)
```python
NORMALIZATION_BOUNDS = {
    'RPM':          (1000, 6000),
    'CHT':          (50, 200),
    'EGT':          (400, 1000),
    'oil_temp':     (20, 160),
    'oil_pressure': (0.5, 8.0),
    'MAP':          (10, 40),
    'fuel_flow':    (5, 30),
    'vibration':    (0, 5.0),
}

def normalize(value, sensor_name):
    lo, hi = NORMALIZATION_BOUNDS[sensor_name]
    return (value - lo) / (hi - lo)
```

### Z-Score Normalization (for ML features)
Computed from healthy baseline statistics:
```python
def z_normalize(features, healthy_mean, healthy_std):
    return (features - healthy_mean) / (healthy_std + 1e-8)
```

---

## 5. Data Storage Architecture

### In-Memory (Real-Time)
```python
class RingBuffer:
    """Fixed-size circular buffer for sliding window operations"""
    def __init__(self, capacity=3000):  # 5 minutes at 10 Hz
        self.buffer = np.zeros((capacity, num_features))
        self.index = 0
        self.full = False
    
    def append(self, frame):
        self.buffer[self.index] = frame
        self.index = (self.index + 1) % self.capacity
        if self.index == 0:
            self.full = True
    
    def get_window(self, size=300):
        """Get most recent 'size' samples"""
        if self.full:
            end = self.index
            start = (end - size) % self.capacity
            # handle wrap-around...
        # ...
```

### Persistent Storage (Historical)
- **Format**: Apache Parquet (columnar, compressed, fast reads)
- **Partitioning**: By date and flight_id
- **Compression**: Snappy (fast decompression)
- **Retention**: Keep all data (storage is cheap, engine data is valuable)

---

## 6. Data Quality Checks

### Real-Time Validation
```python
class DataValidator:
    VALID_RANGES = {
        'RPM': (0, 7000),
        'CHT': (-40, 300),
        'EGT': (0, 1200),
        'oil_temp': (-40, 200),
        'oil_pressure': (0, 12),
        'MAP': (5, 50),
        'fuel_flow': (0, 50),
    }
    
    def validate_frame(self, frame: dict) -> tuple[bool, list[str]]:
        errors = []
        for param, (lo, hi) in self.VALID_RANGES.items():
            value = frame.get(param)
            if value is None or np.isnan(value):
                errors.append(f"{param}: missing/NaN")
            elif value < lo or value > hi:
                errors.append(f"{param}: {value} out of range [{lo}, {hi}]")
        
        return len(errors) == 0, errors
```

### Rate-of-Change Checks
```python
MAX_RATES = {
    'RPM': 500,        # max RPM change per second
    'CHT': 5,          # max °C change per second
    'oil_temp': 2,     # max °C change per second
    'oil_pressure': 1, # max bar change per second
}
```
