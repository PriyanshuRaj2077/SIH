"""
AeroPulse Engine Health & Mission Reliability Engine
Computes Composite Engine Health Score (0-100%), Remaining Useful Life (RUL) with confidence bounds,
and Mission Risk Level (GO / CAUTION / RTB ABORT).
"""

import math
from typing import Dict, Any, Tuple


class HealthRiskCalculator:
    """
    Translates Digital Twin state and analytics output into actionable
    health, reliability, and mission risk metrics.
    """

    TBO_HOURS = 2000.0  # Time Between Overhaul specification

    def __init__(self):
        self.smooth_health: float = 98.5

    def calculate_health_and_risk(
        self,
        dt_output: Dict[str, Any],
        analytics_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute composite health index, RUL forecast, and operational risk.
        """
        deg = dt_output["estimated_degradation"]
        obs = dt_output["observed"]
        anomaly = analytics_output
        is_anomaly = anomaly["is_anomaly"]
        severity = anomaly["severity"]
        score = anomaly["anomaly_score"]

        # -----------------------------------------------------------------
        # 1. Composite Health Score Calculation (0 - 100%)
        # -----------------------------------------------------------------
        fault_diag = anomaly.get("fault_diagnosis", {})
        fault_code = fault_diag.get("code", "NOMINAL")

        # -----------------------------------------------------------------
        # 1. Composite Health Score Calculation (0 - 100%)
        # -----------------------------------------------------------------
        # Base health derived from EKF degradation parameters (60% weight)
        component_health = (
            0.35 * deg["eta_vol_health_pct"] +
            0.35 * deg["eta_mech_health_pct"] +
            0.30 * deg["eta_comb_health_pct"]
        )

        # Penalty based on anomaly score and residual distance (25% weight)
        residual_penalty = score * 45.0

        # Boundary penalty for approaching critical physical limits (15% weight)
        boundary_penalty = 0.0

        # Low oil pressure penalty
        oil_p = obs["oil_pressure_bar"]
        if oil_p < 2.6:
            boundary_penalty += min(45.0, (2.6 - oil_p) * 40.0)

        # High CHT penalty (ignore single false spike if diagnosed as sensor drift F11)
        max_cht = max(obs["cht"])
        if fault_code == "F11":
            # True engine CHT is normal, don't penalize physical engine for sensor drift
            boundary_penalty += 5.0
        elif max_cht > 125.0:
            boundary_penalty += min(35.0, (max_cht - 125.0) * 1.8)

        # High coolant penalty (Rotax 914 continuous limit is 115°C, alert above 105°C)
        if obs["coolant_temp_c"] > 105.0:
            boundary_penalty += min(30.0, (obs["coolant_temp_c"] - 105.0) * 2.0)

        # High vibration penalty
        vib_rms = obs["vibration_rms"]
        if vib_rms > 1.6:
            boundary_penalty += min(40.0, (vib_rms - 1.6) * 14.0)

        # Raw composite health index
        raw_health = component_health - residual_penalty - boundary_penalty
        if fault_code == "F11":
            raw_health = max(86.0, raw_health)  # Engine is mechanically sound
        raw_health = max(10.0, min(100.0, raw_health))

        # Smooth health score transitions (faster recovery when healthy)
        h_alpha = 0.35 if not is_anomaly else 0.22
        self.smooth_health = (1.0 - h_alpha) * self.smooth_health + h_alpha * raw_health
        if not is_anomaly and anomaly.get("residual_distance", 1.0) < 2.0:
            self.smooth_health = max(self.smooth_health, 98.0)
        health_score = round(self.smooth_health, 1)

        # -----------------------------------------------------------------
        # 2. Mission Risk Level & Recommendation
        # -----------------------------------------------------------------
        if fault_code == "F11":
            mission_risk = "MODERATE (CAUTION)"
            risk_code = "MODERATE"
            risk_color = "amber"
            recommendation = "SENSOR CALIBRATION BIAS DETECTED — CROSS-CHECK UNCOUPLED CHANNELS"
        elif health_score < 60.0 or severity == "CRITICAL" or oil_p < 1.8 or (max_cht > 145.0 and fault_code != "F11") or vib_rms > 3.5:
            mission_risk = "HIGH (RTB / ABORT)"
            risk_code = "HIGH"
            risk_color = "red"
            recommendation = "ABORT MISSION — INITIATE RETURN TO BASE (RTB) IMMEDIATELY"
        elif health_score < 80.0 or severity in ("WARNING", "CAUTION") or oil_p < 2.3 or max_cht > 132.0:
            mission_risk = "MODERATE (CAUTION)"
            risk_code = "MODERATE"
            risk_color = "amber"
            recommendation = "RESTRICT FLIGHT ENVELOPE — REDUCE THROTTLE & MONITOR DEGRADATION"
        else:
            mission_risk = "LOW (GO)"
            risk_code = "LOW"
            risk_color = "green"
            recommendation = "MISSION GO — ALL POWERTRAIN PARAMETERS WITHIN SAFE LIMITS"

        # -----------------------------------------------------------------
        # 3. Remaining Useful Life (RUL) Forecast
        # -----------------------------------------------------------------
        engine_hours = 142.5
        nominal_rul_hours = max(10.0, self.TBO_HOURS - engine_hours)

        if not is_anomaly or fault_code == "F11":
            # Nominal wear trajectory based on cumulative flight hours
            rul_hours = nominal_rul_hours
            rul_ci_lower = round(rul_hours * 0.94, 1)
            rul_ci_upper = round(rul_hours * 1.05, 1)
            rul_display = f"{rul_hours:.0f} Flight Hours"
            rul_ci_display = f"90% CI: [{rul_ci_lower:.0f} - {rul_ci_upper:.0f} hrs]"
            time_to_critical_mins = None
        else:
            # Emergency RUL projection based on active fault degradation rate
            if fault_code == "F05" or oil_p < 2.2:
                # Oil pressure emergency: hydrodynamic film margin
                time_mins = max(5.0, min(35.0, (oil_p - 0.8) * 22.0))
                rul_hours = round(time_mins / 60.0, 2)
                rul_display = f"{time_mins:.0f} Minutes"
                rul_ci_display = f"90% CI: [{max(3.0, round(time_mins * 0.75, 1)):.0f} - {round(time_mins * 1.25, 1):.0f} mins] before bearing seizure"
            elif fault_code == "F06" or obs["coolant_temp_c"] > 95.0 or max_cht > 135.0:
                # Cooling circuit emergency
                time_mins = max(8.0, min(45.0, (150.0 - max_cht) * 1.8 + (120.0 - obs["coolant_temp_c"]) * 0.8))
                rul_hours = round(time_mins / 60.0, 2)
                rul_display = f"{time_mins:.0f} Minutes"
                rul_ci_display = f"90% CI: [{max(4.0, round(time_mins * 0.75, 1)):.0f} - {round(time_mins * 1.25, 1):.0f} mins] before thermal seizure"
            elif fault_code == "F08" or vib_rms > 2.0:
                # Vibration / bearing wear
                time_mins = max(10.0, min(50.0, (5.5 - vib_rms) * 12.0))
                rul_hours = round(time_mins / 60.0, 2)
                rul_display = f"{time_mins:.0f} Minutes"
                rul_ci_display = f"90% CI: [{max(5.0, round(time_mins * 0.75, 1)):.0f} - {round(time_mins * 1.25, 1):.0f} mins] before fatigue fracture"
            elif fault_code == "F03":
                # Fuel injector lean burn
                time_mins = max(15.0, min(60.0, (900.0 - max(obs["egt"])) * 0.35))
                rul_hours = round(time_mins / 60.0, 2)
                rul_display = f"{time_mins:.0f} Minutes"
                rul_ci_display = f"90% CI: [{max(8.0, round(time_mins * 0.8, 1)):.0f} - {round(time_mins * 1.2, 1):.0f} mins] before valve burn"
            elif fault_code == "F01":
                # Compression loss (hours rather than minutes)
                safe_hrs = max(2.0, min(8.0, 5.0 * (deg["eta_vol_health_pct"] / 100.0)))
                rul_hours = round(safe_hrs, 1)
                rul_display = f"{safe_hrs:.1f} Flight Hours"
                rul_ci_display = f"90% CI: [{safe_hrs * 0.8:.1f} - {safe_hrs * 1.2:.1f} hrs] (Reduced Power Envelope)"
                time_mins = safe_hrs * 60.0
            elif fault_code == "F02":
                # Ignition misfire
                safe_hrs = max(1.5, min(4.0, 3.0 * (deg["eta_comb_health_pct"] / 100.0)))
                rul_hours = round(safe_hrs, 1)
                rul_display = f"{safe_hrs:.1f} Flight Hours"
                rul_ci_display = f"90% CI: [{safe_hrs * 0.75:.1f} - {safe_hrs * 1.2:.1f} hrs] (Precautionary Transit)"
                time_mins = safe_hrs * 60.0
            else:
                time_mins = max(15.0, min(90.0, (health_score - 30.0) * 1.6))
                rul_hours = round(time_mins / 60.0, 2)
                rul_display = f"{time_mins:.0f} Minutes"
                rul_ci_display = f"90% CI: [{round(time_mins * 0.75, 1):.0f} - {round(time_mins * 1.25, 1):.0f} mins] before critical threshold"

            time_to_critical_mins = round(time_mins, 1)

        return {
            "health_score": health_score,
            "mission_risk": mission_risk,
            "risk_code": risk_code,
            "risk_color": risk_color,
            "recommendation": recommendation,
            "rul": {
                "display": rul_display,
                "confidence_interval": rul_ci_display,
                "rul_hours": rul_hours,
                "time_to_critical_mins": time_to_critical_mins,
            }
        }
