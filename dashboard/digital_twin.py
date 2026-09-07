"""
AeroPulse Digital Twin Core
Maintains a real-time virtual replica of the aero-piston engine:
1. Expected Engine Behavior Model (Thermodynamic MVEM under identical operating conditions).
2. Extended Kalman Filter (EKF) tracking physical state and degradation parameters (η_vol, η_comb, η_mech).
3. Continuous Residual Generator (Δ = Observed - Expected) across all 11 sensor channels.
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple

from common.constants import (
    BORE_M, STROKE_M, DISPLACEMENT_M3, MAX_RPM, IDLE_RPM,
    AIR_GAS_CONSTANT_R, LOWER_HEATING_VALUE_FUEL, STOICHIOMETRIC_AFR, FUEL_DENSITY_KG_L,
    ISA_SEA_LEVEL_TEMP_K, ISA_SEA_LEVEL_PRESSURE_PA, ISA_SEA_LEVEL_DENSITY,
    ISA_TEMP_LAPSE_RATE_K_PER_M, METERS_PER_FOOT,
    BASELINE_ETA_VOL, BASELINE_ETA_COMB, BASELINE_ETA_MECH, MAX_POWER_KW
)
from common.telemetry_schema import TelemetryPacket


class DigitalTwin:
    """
    The Digital Twin engine state estimator and residual calculator.
    Executes in closed-loop with incoming telemetry frames.
    """

    # Sensor noise standard deviations for normalization (Z-score residual calculation)
    SENSOR_SIGMAS = {
        "rpm": 12.0,
        "cht": 1.8,
        "egt": 6.0,
        "oil_temp": 1.2,
        "oil_pressure": 0.08,
        "coolant_temp": 1.0,
        "map_kpa": 0.8,
        "fuel_flow": 0.4,
        "vibration": 0.12,
        "voltage": 0.1
    }

    def __init__(self):
        # Estimated degradation states
        self.eta_vol: float = BASELINE_ETA_VOL
        self.eta_comb: float = BASELINE_ETA_COMB
        self.eta_mech: float = BASELINE_ETA_MECH

        # EKF internal state vector [RPM, T_oil, T_coolant, MAP, eta_vol, eta_comb, eta_mech]
        self.x = np.array([IDLE_RPM, 82.0, 78.0, 80.0, BASELINE_ETA_VOL, BASELINE_ETA_COMB, BASELINE_ETA_MECH], dtype=float)
        # State covariance matrix P
        self.P = np.diag([100.0, 4.0, 4.0, 2.0, 0.01, 0.01, 0.01])
        # Process noise matrix Q
        self.Q = np.diag([2.0, 0.05, 0.05, 0.05, 0.00001, 0.00001, 0.00001])
        # Measurement noise matrix R [RPM, T_oil, T_coolant, MAP, P_oil]
        self.R = np.diag([16.0, 1.0, 1.0, 0.5, 0.01])
        # Dynamic expected states (tracks thermal capacitance alongside physics)
        self.exp_rpm = IDLE_RPM
        self.exp_cht = [88.0, 89.2, 91.0, 88.5]
        self.exp_egt = [715.0, 722.0, 730.0, 718.0]
        self.exp_oil_temp = 82.0
        self.exp_oil_pressure = 4.2
        self.exp_coolant = 78.0
        self.exp_map = 80.0
        self.exp_fuel_flow = 12.0
        self.exp_vib = 0.5
        self.last_update_time: Optional[float] = None

        # Rolling history buffers for sliding-window features (100 samples = 10s at 10Hz)
        self.history_size = 100
        self.residual_history: List[Dict[str, float]] = []

    def compute_atmosphere(self, altitude_ft: float, ambient_temp_c: float) -> Tuple[float, float, float]:
        """Compute ambient pressure (kPa), temperature (K), and density ratio"""
        alt_m = max(0.0, altitude_ft * METERS_PER_FOOT)
        t_isa_k = max(216.65, ISA_SEA_LEVEL_TEMP_K - ISA_TEMP_LAPSE_RATE_K_PER_M * alt_m)
        p_pa = ISA_SEA_LEVEL_PRESSURE_PA * (t_isa_k / ISA_SEA_LEVEL_TEMP_K) ** 5.2561
        t_actual_k = ambient_temp_c + 273.15
        rho = p_pa / (AIR_GAS_CONSTANT_R * t_actual_k)
        return p_pa / 1000.0, t_actual_k, rho / ISA_SEA_LEVEL_DENSITY

    def compute_expected_behavior(
        self,
        altitude_ft: float,
        ambient_temp_c: float,
        wind_speed_mps: float,
        throttle_pct: float,
        engine_load: float = 1.0,
        dt: float = 0.1
    ) -> Dict[str, any]:
        """
        Thermodynamic Mean-Value Engine Model under NOMINAL (Healthy) conditions.
        Produces baseline reference values with realistic thermal and rotational lag.
        """
        p_amb_kpa, t_amb_k, rho_ratio = self.compute_atmosphere(altitude_ft, ambient_temp_c)
        throttle = max(0.0, min(1.0, throttle_pct / 100.0))

        # 1. Target Manifold Pressure (MAP)
        target_map = p_amb_kpa * (0.35 + 0.65 * throttle)
        self.exp_map += (dt / 0.2) * (target_map - self.exp_map)

        # 2. Target RPM
        aero_load = engine_load * (1.0 + 0.004 * wind_speed_mps)
        density_effect = math.sqrt(max(0.2, rho_ratio))
        target_rpm = IDLE_RPM + (MAX_RPM - IDLE_RPM) * (throttle ** 1.1) * density_effect / math.sqrt(max(0.5, aero_load))
        target_rpm = max(IDLE_RPM * 0.85, min(MAX_RPM * 1.05, target_rpm))
        self.exp_rpm += (dt / 0.45) * (target_rpm - self.exp_rpm)

        # 3. Air & Fuel Flow
        intake_temp_k = t_amb_k + 8.0 * throttle
        m_dot_air = (self.exp_map * 1000.0 * DISPLACEMENT_M3 * self.exp_rpm) / (2.0 * AIR_GAS_CONSTANT_R * intake_temp_k * 60.0) * BASELINE_ETA_VOL
        m_dot_fuel = m_dot_air / STOICHIOMETRIC_AFR
        target_fuel_flow = (m_dot_fuel * 3600.0) / FUEL_DENSITY_KG_L
        self.exp_fuel_flow += (dt / 0.4) * (target_fuel_flow - self.exp_fuel_flow)

        # Power Output
        indicated_kw = (m_dot_fuel * LOWER_HEATING_VALUE_FUEL * BASELINE_ETA_COMB * 0.32) / 1000.0
        expected_power_kw = indicated_kw * BASELINE_ETA_MECH

        # 4. Temperatures (EGT 1-4 & CHT 1-4)
        base_egt = 650.0 + 130.0 * throttle + 30.0 * (1.0 - rho_ratio)
        cyl_offsets_egt = [-4.0, +3.0, +7.0, -2.0]
        for i in range(4):
            target_egt_i = base_egt + cyl_offsets_egt[i]
            self.exp_egt[i] += (dt / 1.2) * (target_egt_i - self.exp_egt[i])

        # Coolant & CHT
        heat_kw = expected_power_kw * 0.45
        target_coolant = (ambient_temp_c + 55.0) + (heat_kw / 35.0) * 25.0
        target_coolant = max(ambient_temp_c + 10.0, min(115.0, target_coolant))
        self.exp_coolant += (dt / 10.0) * (target_coolant - self.exp_coolant)

        cyl_offsets_cht = [-1.5, +1.0, +2.5, -0.8]
        for i in range(4):
            target_cht_i = self.exp_coolant + 18.0 + (expected_power_kw / MAX_POWER_KW) * 28.0 + cyl_offsets_cht[i]
            self.exp_cht[i] += (dt / 5.5) * (target_cht_i - self.exp_cht[i])

        # 5. Lubrication (Oil Temp & Pressure)
        target_oil_temp = ambient_temp_c + 45.0 + (expected_power_kw / MAX_POWER_KW) * 35.0
        self.exp_oil_temp += (dt / 14.0) * (target_oil_temp - self.exp_oil_temp)

        temp_factor = 1.0 - 0.005 * (self.exp_oil_temp - 80.0)
        target_oil_p = (1.8 + 3.4 * (self.exp_rpm / MAX_RPM)) * temp_factor
        self.exp_oil_pressure += (dt / 0.6) * (target_oil_p - self.exp_oil_pressure)

        # 6. Expected Vibration RMS
        target_vib = 0.25 + 0.95 * ((self.exp_rpm / MAX_RPM) ** 2) + 0.25 * (expected_power_kw / MAX_POWER_KW)
        self.exp_vib += (dt / 0.5) * (target_vib - self.exp_vib)

        return {
            "rpm": round(float(self.exp_rpm), 1),
            "map_kpa": round(float(self.exp_map), 1),
            "fuel_flow_lph": round(float(self.exp_fuel_flow), 2),
            "cht": [round(float(c), 1) for c in self.exp_cht],
            "egt": [round(float(e), 1) for e in self.exp_egt],
            "oil_temp_c": round(float(self.exp_oil_temp), 1),
            "oil_pressure_bar": round(float(self.exp_oil_pressure), 2),
            "coolant_temp_c": round(float(self.exp_coolant), 1),
            "vibration_rms": round(float(self.exp_vib), 3),
            "bus_voltage": 13.8
        }

    def update(self, packet: TelemetryPacket) -> Dict[str, any]:
        """
        Process an incoming real-time telemetry packet through the Digital Twin:
        1. Calculate expected baseline.
        2. Run EKF state estimation.
        3. Compute raw and normalized residuals.
        """
        env = packet.flight_env
        tel = packet.telemetry

        # 1. Compute Expected Nominal Baseline
        expected = self.compute_expected_behavior(
            altitude_ft=env.altitude_ft,
            ambient_temp_c=env.ambient_temp_c,
            wind_speed_mps=env.wind_speed_mps,
            throttle_pct=env.throttle_pct,
            engine_load=env.engine_load
        )

        # 2. Compute Raw Residuals (Observed - Expected)
        diff_rpm = tel.rpm - expected["rpm"]
        diff_cht = [obs - exp for obs, exp in zip(tel.cht, expected["cht"])]
        diff_egt = [obs - exp for obs, exp in zip(tel.egt, expected["egt"])]
        diff_oil_p = tel.oil_pressure_bar - expected["oil_pressure_bar"]
        diff_oil_t = tel.oil_temp_c - expected["oil_temp_c"]
        diff_coolant = tel.coolant_temp_c - expected["coolant_temp_c"]
        diff_map = tel.map_kpa - expected["map_kpa"]
        diff_fuel_flow = tel.fuel_flow_lph - expected["fuel_flow_lph"]
        vib_rms_obs = tel.vibration.rms if hasattr(tel.vibration, 'rms') else 0.5
        diff_vib = vib_rms_obs - expected["vibration_rms"]

        # 3. Simple Extended Kalman Filter (EKF) step for Degradation Tracking
        # State vector: [RPM, T_oil, T_coolant, MAP, eta_vol, eta_comb, eta_mech]
        # Measurement vector: [tel.rpm, tel.oil_temp_c, tel.coolant_temp_c, tel.map_kpa, tel.oil_pressure_bar]
        z_meas = np.array([tel.rpm, tel.oil_temp_c, tel.coolant_temp_c, tel.map_kpa, tel.oil_pressure_bar])

        # Prediction step
        # Transition Jacobian F ≈ I + dt * df/dx
        F = np.eye(7)
        F[0, 0] = 0.95
        F[1, 1] = 0.98
        F[2, 2] = 0.98
        F[3, 3] = 0.95
        self.P = F @ self.P @ F.T + self.Q

        # Measurement model H (5x7)
        H = np.zeros((5, 7))
        H[0, 0] = 1.0  # RPM
        H[1, 1] = 1.0  # T_oil
        H[2, 2] = 1.0  # T_coolant
        H[3, 3] = 1.0  # MAP
        H[4, 0] = 0.0006 # P_oil depends on RPM
        H[4, 1] = -0.015 # and inversely on T_oil
        H[4, 6] = 2.0    # and on mechanical condition

        # Innovation (measurement residual in filter)
        h_x = np.array([
            self.x[0],
            self.x[1],
            self.x[2],
            self.x[3],
            (1.8 + 3.4 * (self.x[0] / 5800.0)) * (1.0 - 0.005 * (self.x[1] - 80.0)) * (self.x[6] / BASELINE_ETA_MECH)
        ])
        y_innov = z_meas - h_x

        # Kalman Gain K
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)

        # State Update
        self.x = self.x + K @ y_innov
        self.P = (np.eye(7) - K @ H) @ self.P

        # Update and clamp degradation parameter estimates
        self.eta_vol = float(np.clip(self.x[4], 0.45, 1.0))
        self.eta_comb = float(np.clip(self.x[5], 0.50, 1.0))
        self.eta_mech = float(np.clip(self.x[6], 0.40, 1.0))

        # Adjust degradation parameters if physical residuals strongly point to specific loss
        # E.g. Compression loss reduces volumetric efficiency estimate
        if diff_map < -8.0 and diff_rpm < -150.0:
            self.eta_vol = min(self.eta_vol, BASELINE_ETA_VOL * 0.72)
        # Lubrication failure reduces mechanical efficiency estimate
        if diff_oil_p < -1.5:
            self.eta_mech = min(self.eta_mech, BASELINE_ETA_MECH * 0.65)
        # Combustion misfire reduces combustion efficiency estimate
        if any(e < -150.0 for e in diff_egt):
            self.eta_comb = min(self.eta_comb, BASELINE_ETA_COMB * 0.75)

        # 4. Normalized Residuals (Z-scores)
        z_scores = {
            "rpm": diff_rpm / self.SENSOR_SIGMAS["rpm"],
            "cht_mean": np.mean(diff_cht) / self.SENSOR_SIGMAS["cht"],
            "egt_mean": np.mean(diff_egt) / self.SENSOR_SIGMAS["egt"],
            "oil_press": diff_oil_p / self.SENSOR_SIGMAS["oil_pressure"],
            "oil_temp": diff_oil_t / self.SENSOR_SIGMAS["oil_temp"],
            "coolant": diff_coolant / self.SENSOR_SIGMAS["coolant_temp"],
            "map": diff_map / self.SENSOR_SIGMAS["map_kpa"],
            "vibration": diff_vib / self.SENSOR_SIGMAS["vibration"],
        }

        # Record residual frame into rolling history
        residual_record = {
            "timestamp": packet.timestamp,
            "diff_rpm": round(diff_rpm, 1),
            "diff_cht": [round(c, 1) for c in diff_cht],
            "diff_egt": [round(e, 1) for e in diff_egt],
            "diff_oil_p": round(diff_oil_p, 2),
            "diff_oil_t": round(diff_oil_t, 1),
            "diff_coolant": round(diff_coolant, 1),
            "diff_map": round(diff_map, 1),
            "diff_fuel_flow": round(diff_fuel_flow, 2),
            "diff_vib": round(diff_vib, 3),
            "z_scores": z_scores
        }

        self.residual_history.append(residual_record)
        if len(self.residual_history) > self.history_size:
            self.residual_history.pop(0)

        return {
            "expected": expected,
            "observed": {
                "rpm": tel.rpm,
                "cht": tel.cht,
                "egt": tel.egt,
                "oil_temp_c": tel.oil_temp_c,
                "oil_pressure_bar": tel.oil_pressure_bar,
                "coolant_temp_c": tel.coolant_temp_c,
                "map_kpa": tel.map_kpa,
                "fuel_flow_lph": tel.fuel_flow_lph,
                "vibration_rms": vib_rms_obs,
                "bus_voltage": tel.bus_voltage
            },
            "residuals": residual_record,
            "estimated_degradation": {
                "eta_vol": round(self.eta_vol, 3),
                "eta_comb": round(self.eta_comb, 3),
                "eta_mech": round(self.eta_mech, 3),
                "eta_vol_health_pct": round((self.eta_vol / BASELINE_ETA_VOL) * 100.0, 1),
                "eta_comb_health_pct": round((self.eta_comb / BASELINE_ETA_COMB) * 100.0, 1),
                "eta_mech_health_pct": round((self.eta_mech / BASELINE_ETA_MECH) * 100.0, 1)
            }
        }
