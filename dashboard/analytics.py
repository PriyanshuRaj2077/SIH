"""
AeroPulse Analytics & Anomaly Detection Pipeline
Fuses statistical residual tracking (CUSUM, Mahalanobis distance) and
physics-guided multi-variable fault attribution to diagnose root causes.
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple, Any


class AnalyticsEngine:
    """
    Analyzes Digital Twin residuals to detect anomalies, quantify severity,
    and isolate the exact physical root cause through a diagnostic matrix.
    """

    def __init__(self):
        # CUSUM cumulative sum change detection buffers
        self.cusum_pos: Dict[str, float] = {}
        self.cusum_neg: Dict[str, float] = {}
        self.cusum_k = 0.5   # Slack allowance in standard deviations
        self.cusum_h = 4.0   # Decision boundary threshold

        # Rolling anomaly score smoother
        self.smooth_anomaly_score: float = 0.0

    def evaluate_residuals(self, dt_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the Digital Twin output to detect anomalies and identify root cause.
        """
        res = dt_output["residuals"]
        z_scores = res["z_scores"]
        observed = dt_output["observed"]
        expected = dt_output["expected"]
        degradation = dt_output["estimated_degradation"]

        diff_rpm = res["diff_rpm"]
        diff_cht = res["diff_cht"]
        diff_egt = res["diff_egt"]
        diff_oil_p = res["diff_oil_p"]
        diff_oil_t = res["diff_oil_t"]
        diff_coolant = res["diff_coolant"]
        diff_map = res["diff_map"]
        diff_vib = res["diff_vib"]

        # -----------------------------------------------------------------
        # 1. Statistical Anomaly Detection (Mahalanobis / Chi-Square Metric)
        # -----------------------------------------------------------------
        z_array = np.array(list(z_scores.values()), dtype=float)
        # Mahalanobis distance metric on normalized residual vector
        d_res = float(np.sqrt(np.sum(z_array ** 2)))

        # Update CUSUM on key critical channels (Oil P, Coolant, Vib, EGT)
        cusum_triggered = False
        for channel in ["oil_press", "coolant", "vibration"]:
            val = z_scores.get(channel, 0.0)
            self.cusum_pos[channel] = max(0.0, self.cusum_pos.get(channel, 0.0) + val - self.cusum_k)
            self.cusum_neg[channel] = max(0.0, self.cusum_neg.get(channel, 0.0) - val - self.cusum_k)
            if self.cusum_pos[channel] > self.cusum_h or self.cusum_neg[channel] > self.cusum_h:
                cusum_triggered = True

        # Rapidly decay/reset CUSUM accumulators when residuals return to nominal band
        if d_res < 2.5:
            self.cusum_pos = {k: 0.0 for k in self.cusum_pos}
            self.cusum_neg = {k: 0.0 for k in self.cusum_neg}
            cusum_triggered = False

        # Normalized Anomaly Score (0.0 = completely nominal, 1.0 = severe anomaly)
        # Normal baseline d_res is typically 1.0 - 2.5 due to sensor noise
        raw_anomaly_score = max(0.0, min(1.0, (d_res - 2.2) / 6.5))
        if cusum_triggered:
            raw_anomaly_score = max(raw_anomaly_score, 0.65)

        if d_res < 2.2:
            raw_anomaly_score = 0.0
            self.smooth_anomaly_score = 0.0

        # Smooth anomaly score to avoid single-frame flickering
        alpha = 0.4 if raw_anomaly_score > self.smooth_anomaly_score else 0.3
        self.smooth_anomaly_score = (1.0 - alpha) * self.smooth_anomaly_score + alpha * raw_anomaly_score
        anomaly_score = round(self.smooth_anomaly_score, 3)

        # Determine Anomaly Severity State
        if d_res < 2.2 and abs(diff_oil_p) < 0.5 and diff_vib < 0.5 and max(diff_cht) < 12.0:
            severity = "NOMINAL"
            is_anomaly = False
            confidence_pct = 96.0
        elif anomaly_score >= 0.70 or abs(diff_oil_p) > 1.8 or diff_vib > 2.8 or max(diff_cht) > 30.0:
            severity = "CRITICAL"
            is_anomaly = True
            confidence_pct = min(99.0, 75.0 + anomaly_score * 24.0)
        elif anomaly_score >= 0.40 or abs(diff_oil_p) > 0.9 or diff_vib > 1.2 or max(diff_cht) > 14.0 or diff_coolant > 5.0:
            severity = "WARNING"
            is_anomaly = True
            confidence_pct = min(92.0, 60.0 + anomaly_score * 30.0)
        elif anomaly_score >= 0.20 or any(abs(e) > 50.0 for e in diff_egt) or abs(diff_oil_p) > 0.5 or diff_vib > 0.5:
            severity = "CAUTION"
            is_anomaly = True
            confidence_pct = min(85.0, 50.0 + anomaly_score * 35.0)
        else:
            severity = "NOMINAL"
            is_anomaly = False
            confidence_pct = 95.0  # Confidence that engine is healthy

        # -----------------------------------------------------------------
        # 2. Physics-Guided Fault Attribution Matrix
        # -----------------------------------------------------------------
        fault_code = "NOMINAL"
        fault_name = "Engine Operating Nominally"
        root_cause = "All cylinder temperatures, pressures, and vibration signatures match Digital Twin expected baseline."
        affected_subsystem = "None (System Healthy)"

        if is_anomaly:
            # Priority 1: Check F05: Lubrication Failure / Oil Pressure Drop
            if diff_oil_p < -0.55 or observed["oil_pressure_bar"] < 2.5:
                fault_code = "F05"
                fault_name = "Lubrication Oil Pressure Collapse"
                root_cause = f"Oil pressure dropped by {abs(diff_oil_p):.2f} bar below expected baseline ({observed['oil_pressure_bar']:.2f} bar observed vs {expected['oil_pressure_bar']:.2f} bar expected). Starvation poses critical risk of crankshaft bearing seizure."
                affected_subsystem = "Lubrication Circuit (Oil Pump / Pressure Relief Valve)"

            # Priority 2: Check F02: Ignition Spark Plug Misfire - Localized EGT Plunge (Checks before F08 since misfire causes roughness)
            elif any(e < -40.0 for e in diff_egt) or (np.median(diff_egt) - min(diff_egt) > 35.0):
                cold_cyl_idx = int(np.argmin(diff_egt))
                cold_cyl_num = cold_cyl_idx + 1
                fault_code = "F02"
                fault_name = f"Ignition Spark Misfire (Cylinder {cold_cyl_num})"
                root_cause = f"Cylinder {cold_cyl_num} EGT collapsed by {diff_egt[cold_cyl_idx]:.1f}°C ({observed['egt'][cold_cyl_idx]:.0f}°C observed). Incomplete combustion dumping raw charge into exhaust; engine speed dropped by {abs(diff_rpm):.0f} RPM with torque flutter."
                affected_subsystem = f"Dual Ignition Circuit (Coil / Spark Plug #{cold_cyl_num})"

            # Priority 3: Check F08: Mechanical Bearing Wear / Vibration Spike
            elif (diff_vib > 0.55 or observed["vibration_rms"] > 1.35) and all(e > -40.0 for e in diff_egt):
                fault_code = "F08"
                fault_name = "Bearing Mechanical Wear / Propeller Unbalance"
                root_cause = f"RMS vibration surged by +{diff_vib:.2f} mm/s to {observed['vibration_rms']:.2f} mm/s. Severe harmonic acceleration indicates journal bearing surface spalling or reduction gear defect."
                affected_subsystem = "Mechanical Drive (Crankshaft Bearing / Reduction Gearbox)"

            # Priority 4: Check F03: Fuel Injector Partial Clog (Lean Burn) - Localized EGT Spike
            elif (max(diff_egt) > 35.0 and (max(diff_egt) - np.median(diff_egt) > 25.0)) or max(diff_egt) > 55.0:
                bad_cyl_idx = int(np.argmax(diff_egt))
                bad_cyl_num = bad_cyl_idx + 1
                fault_code = "F03"
                fault_name = f"Fuel Injector Restriction (Cylinder {bad_cyl_num})"
                root_cause = f"Cylinder {bad_cyl_num} EGT spiked by +{diff_egt[bad_cyl_idx]:.1f}°C ({observed['egt'][bad_cyl_idx]:.0f}°C observed vs {expected['egt'][bad_cyl_idx]:.0f}°C expected). Localized lean fuel-air mixture indicates injector nozzle fouling."
                affected_subsystem = f"Fuel Delivery (Injector Nozzle #{bad_cyl_num})"

            # Priority 5: Check F11: Sensor Probe Bias Drift (Isolated CHT offset with uncoupled normal thermals)
            elif (max(diff_cht) - min(diff_cht) > 15.0) and diff_coolant < 3.0 and (max(diff_egt) - min(diff_egt) < 35.0):
                drift_cyl_idx = int(np.argmax(diff_cht))
                drift_cyl_num = drift_cyl_idx + 1
                fault_code = "F11"
                fault_name = f"Sensor Probe Calibration Drift (CHT Cyl {drift_cyl_num})"
                root_cause = f"Cylinder {drift_cyl_num} CHT reading indicates +{diff_cht[drift_cyl_idx]:.1f}°C offset while coolant temperature ({observed['coolant_temp_c']:.1f}°C) and exhaust gas temperatures remain physically normal. Isolated sensor probe calibration drift."
                affected_subsystem = f"Avionics Telemetry Sensor (CHT Probe #{drift_cyl_num})"

            # Priority 6: Check F06: Cooling Degradation / Radiator Airflow Restriction
            elif diff_coolant > 3.0 or (np.mean(diff_cht) > 6.0 and diff_coolant > 1.5):
                fault_code = "F06"
                fault_name = "Liquid Cooling Circuit Failure / Thermal Runaway"
                root_cause = f"Coolant temperature elevated by +{diff_coolant:.1f}°C and cylinder head temperatures elevated by +{np.mean(diff_cht):.1f}°C. Severe radiator airflow restriction or coolant circulation failure."
                affected_subsystem = "Liquid Cooling System (Radiator / Water Pump)"

            # Priority 7: Check F01: Cylinder Compression Loss / Blowby
            elif diff_map < -2.5 or degradation["eta_vol_health_pct"] < 92.0:
                fault_code = "F01"
                fault_name = "Cylinder Compression Loss & Piston Blowby"
                root_cause = f"Volumetric efficiency degraded to {degradation['eta_vol_health_pct']:.1f}% of baseline. Manifold pressure dropped by {abs(diff_map):.1f} kPa with corresponding engine brake power reduction."
                affected_subsystem = "Combustion Chamber (Piston Rings / Cylinder Barrel)"

            else:
                fault_code = "F99"
                fault_name = "Multi-Parameter Engine Operational Anomaly"
                root_cause = f"Cumulative residual deviation (D_res = {d_res:.2f}) indicates coupled engine degradation."
                affected_subsystem = "Powertrain Assembly"

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": anomaly_score,
            "severity": severity,
            "confidence_pct": round(confidence_pct, 1),
            "residual_distance": round(d_res, 2),
            "fault_diagnosis": {
                "code": fault_code,
                "name": fault_name,
                "root_cause": root_cause,
                "subsystem": affected_subsystem,
            }
        }
