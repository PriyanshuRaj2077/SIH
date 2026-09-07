# AI/ML Pipeline Design — AeroPulse

## 1. ML Architecture Overview

Our ML system has **three stages**, each progressively more complex:

```
Stage 1: Anomaly Detection     → "Is something wrong?"
Stage 2: Fault Classification  → "What is wrong?"
Stage 3: RUL Estimation        → "How much life is left?"
```

```
         Residual Features
              │
              ▼
    ┌─────────────────────┐
    │  ANOMALY DETECTION   │ ← Always running
    │  (Autoencoder +      │
    │   Isolation Forest)  │
    └─────────┬───────────┘
              │ Anomaly detected?
              │
         YES  ▼           NO → Continue monitoring
    ┌─────────────────────┐
    │  FAULT CLASSIFIER    │ ← Triggered on anomaly
    │  (1D-CNN + XGBoost   │
    │   Ensemble)          │
    └─────────┬───────────┘
              │ Fault type identified
              ▼
    ┌─────────────────────┐
    │  RUL ESTIMATOR       │ ← Activated for confirmed fault
    │  (LSTM + Attention   │
    │   with uncertainty)  │
    └─────────────────────┘
```

---

## 2. Stage 1: Anomaly Detection

### 2.1 Approach: Reconstruction-Based Anomaly Detection

**Key Insight**: We train a model on HEALTHY engine data only. Any data that can't be reconstructed well is anomalous.

### Autoencoder Architecture
```
Input (feature vector, dim=48) 
  → Dense(128) → BatchNorm → LeakyReLU → Dropout(0.1)
  → Dense(64) → BatchNorm → LeakyReLU → Dropout(0.1)
  → Dense(32) → BatchNorm → LeakyReLU           ← Latent Space
  → Dense(64) → BatchNorm → LeakyReLU → Dropout(0.1)
  → Dense(128) → BatchNorm → LeakyReLU → Dropout(0.1)
  → Dense(48) → Sigmoid
Output (reconstructed feature vector)

Loss: MSE(input, reconstruction) + β × KL_divergence (if VAE)
```

### Input Feature Vector (48 dimensions)
For each of the 8 primary sensor signals, we compute 6 features over a 30-second window:

| Feature | Description |
|---|---|
| Mean | Average value in window |
| Std | Standard deviation |
| Skewness | Asymmetry of distribution |
| Kurtosis | Tail heaviness |
| RMS | Root mean square |
| Δ (derivative) | Rate of change |

8 signals × 6 features = **48-dimensional feature vector**

### Anomaly Score
```
anomaly_score = MSE(x, x̂)  // reconstruction error

if anomaly_score > threshold_high:
    → ALARM (high-confidence anomaly)
elif anomaly_score > threshold_low:
    → WARNING (potential anomaly, increase monitoring)
else:
    → NORMAL
```

### Isolation Forest (Complementary)
- Trained on the same healthy data
- Provides a second, independent anomaly score
- **Ensemble rule**: Anomaly confirmed if BOTH detectors agree

### Why Two Detectors?
| Method | Strengths | Weaknesses |
|---|---|---|
| Autoencoder | Captures complex nonlinear patterns | Can miss simple outliers |
| Isolation Forest | Fast, interpretable, handles outliers well | Struggles with high-dimensional subtleties |
| **Combined** | **High sensitivity + high specificity** | |

---

## 3. Stage 2: Fault Classification

### 3.1 Fault Taxonomy

| Fault Code | Fault Type | Affected Parameters | Severity |
|---|---|---|---|
| F01 | Cylinder compression loss | CHT↓, EGT↑, Power↓ | HIGH |
| F02 | Ignition degradation | EGT↓ (affected cyl), RPM flutter | MEDIUM |
| F03 | Fuel system lean | EGT↑↑, CHT↑, Power↓ | HIGH |
| F04 | Fuel system rich | EGT↓, CHT↓, fuel flow↑ | MEDIUM |
| F05 | Oil system degradation | Oil temp↑, oil pressure↓ | HIGH |
| F06 | Cooling system degradation | CHT↑, coolant temp↑ | MEDIUM |
| F07 | Turbocharger degradation | MAP↓, boost lag↑ | MEDIUM |
| F08 | Bearing wear | Vibration↑ (specific freq), temperature↑ | HIGH |
| F09 | Gearbox wear | Vibration↑ (sub-harmonic), noise | MEDIUM |
| F10 | Exhaust leak | EGT↓ (post-valve), noise | LOW |

### 3.2 1D-CNN Architecture
```
Input: (window_size=300, channels=8)  // 30 seconds × 10 Hz × 8 sensors

Conv1D(8→32, kernel=7, stride=2) → BatchNorm → ReLU → MaxPool(2)
Conv1D(32→64, kernel=5, stride=1) → BatchNorm → ReLU → MaxPool(2)
Conv1D(64→128, kernel=3, stride=1) → BatchNorm → ReLU
GlobalAvgPool1D()
Dense(128) → ReLU → Dropout(0.3)
Dense(64) → ReLU → Dropout(0.3)
Dense(10) → Softmax  // 10 fault classes

Loss: CrossEntropy with class weights (to handle imbalance)
```

### 3.3 XGBoost Ensemble Member
- Operates on the **same 48 hand-crafted features** used for anomaly detection
- Plus additional features: cross-correlations between sensor pairs, spectral features
- Total features: ~120

### 3.4 Ensemble Strategy
```python
# Soft voting ensemble
p_cnn = cnn_model.predict_proba(X_raw)       # from raw time series
p_xgb = xgb_model.predict_proba(X_features)  # from engineered features

p_ensemble = α * p_cnn + (1-α) * p_xgb       # α = 0.6 (CNN gets more weight)
prediction = argmax(p_ensemble)
confidence = max(p_ensemble)
```

**Why ensemble CNN + XGBoost?**
- CNN excels at learning temporal patterns from raw data
- XGBoost excels at structured, engineered features
- Together they capture both temporal dynamics and statistical signatures

---

## 4. Stage 3: Remaining Useful Life (RUL) Estimation

### 4.1 Problem Formulation
Given a time series of degradation indicators up to time t, predict the number of operating hours remaining before the engine health drops below a critical threshold.

```
RUL(t) = T_failure - t

where T_failure is the predicted time of functional failure
```

### 4.2 LSTM with Attention Architecture
```
Input: (sequence_length=100, features=16)
  // 100 time steps of 16 degradation features

Bidirectional LSTM(16→64, return_sequences=True)
  → Dropout(0.2)
Bidirectional LSTM(128→64, return_sequences=True)
  → Dropout(0.2)

Multi-Head Self-Attention(heads=4, dim=128)
  // Attention lets the model focus on the most informative time steps

Dense(128) → ReLU → Dropout(0.2)
Dense(64) → ReLU
Dense(1) → ReLU  // RUL output (non-negative)

Loss: Asymmetric loss function
```

### 4.3 Asymmetric Loss Function
**Key Design Decision**: Under-predicting RUL (saying engine has less life than it does) wastes money but is safe. Over-predicting RUL (saying engine has more life) is **dangerous**.

```python
def asymmetric_rul_loss(y_true, y_pred):
    error = y_pred - y_true
    # Penalize over-prediction more heavily
    loss = torch.where(
        error > 0,
        error * 2.0,   # over-prediction penalty (2x)
        -error * 1.0   # under-prediction penalty (1x)
    )
    return loss.mean()
```

### 4.4 Input Features for RUL (16 dimensions)
```
Degradation features:
  1. η_vol (volumetric efficiency from EKF)
  2. η_comb (combustion efficiency from EKF)
  3. η_mech (mechanical efficiency from EKF)
  4. CHT_residual_mean
  5. EGT_residual_mean
  6. Oil_temp_residual_mean
  7. Oil_pressure_residual_mean
  8. Vibration_rms_trend
  9. RPM_stability (std over window)
  10. Fuel_efficiency_trend
  11. Power_output_trend
  12. Cumulative_anomaly_score
  13. Hours_since_overhaul
  14. Total_engine_hours
  15. Ambient_temperature
  16. Altitude_profile_severity
```

### 4.5 Uncertainty Quantification (MC Dropout)

During inference, we run the model **N=50 times** with dropout enabled:
```python
def predict_rul_with_uncertainty(model, x, n_samples=50):
    model.train()  # Enable dropout
    predictions = [model(x).item() for _ in range(n_samples)]
    model.eval()
    
    rul_mean = np.mean(predictions)
    rul_std = np.std(predictions)
    rul_lower = np.percentile(predictions, 5)   # 5th percentile
    rul_upper = np.percentile(predictions, 95)  # 95th percentile
    
    return {
        "rul_hours": rul_mean,
        "confidence_interval": (rul_lower, rul_upper),
        "uncertainty": rul_std
    }
```

This gives the mission controller not just a point estimate, but a **credible interval**:
> "Engine has approximately **340 ± 45 hours** remaining (90% confidence: 280-420 hours)"

---

## 5. Training Strategy

### 5.1 Data Split
```
Total synthetic dataset: ~50,000 engine operating cycles
  ├── Training:    35,000 (70%)
  ├── Validation:   7,500 (15%)
  └── Testing:      7,500 (15%)

Additional:
  ├── Healthy-only subset (for anomaly detector training)
  └── Transfer learning pre-training on NASA C-MAPSS
```

### 5.2 Training Pipeline
```
1. Pre-train LSTM encoder on NASA C-MAPSS FD001 → Learn general degradation patterns
2. Fine-tune on our synthetic piston engine data → Adapt to piston-specific physics
3. Train Autoencoder on healthy-only data → Learn normal operating envelope
4. Train CNN + XGBoost on fault-labeled data → Learn fault classification
5. Train RUL estimator on degradation trajectories → Learn life prediction
```

### 5.3 Validation Metrics

| Model | Primary Metric | Secondary Metrics |
|---|---|---|
| Anomaly Detector | F1-Score (anomaly class) | Precision, Recall, AUC-ROC |
| Fault Classifier | Macro F1-Score | Per-class accuracy, Confusion matrix |
| RUL Estimator | RMSE on RUL | MAE, Scoring function (NASA), Coverage of CI |

### 5.4 Model Deployment
```
Training: PyTorch (GPU-accelerated)
Export: ONNX format
Inference: ONNX Runtime (CPU-optimized)

Expected inference times:
  - Anomaly detection: ~2ms
  - Fault classification: ~5ms
  - RUL estimation (single forward pass): ~3ms
  - RUL with uncertainty (50 passes): ~150ms (run async)
```

---

## 6. Honest Assessment of ML Claims

### What We CAN Credibly Demonstrate
- ✅ Anomaly detection on synthetic data with known ground truth
- ✅ Fault classification accuracy on our simulated fault catalog
- ✅ RUL prediction accuracy validated against our simulation
- ✅ Transfer learning from NASA C-MAPSS improving our model
- ✅ Uncertainty quantification providing calibrated confidence intervals
- ✅ Real-time inference speed meeting mission requirements

### What We CANNOT Claim
- ❌ "Validated on real engine data" — we don't have any
- ❌ "Production-ready for military deployment" — requires extensive V&V
- ❌ "Guaranteed fault detection rate" — our simulator has modeling assumptions
- ❌ "Works on any engine" — we're tuned to our reference engine parameters

### Mitigation
We explicitly frame our system as a **Technology Demonstrator** that proves the architecture works. Transitioning to a production system requires:
1. Real engine telemetry for model calibration
2. Domain expert validation of fault models
3. Formal safety analysis (FMEA/FMECA)
4. DO-178C compliance for flight-critical software
