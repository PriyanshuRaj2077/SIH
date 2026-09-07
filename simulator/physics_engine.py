"""
AeroPulse Piston Engine Physics Engine (MVEM)
Implements a continuous-time, physics-informed Mean-Value Engine Model
for a 4-cylinder flat-four aero piston engine (Rotax 912/914 class).

Models:
1. International Standard Atmosphere (ISA) with altitude, pressure, density, and ambient temp.
2. Manifold dynamics, volumetric air mass flow, stoichiometric combustion & torque.
3. Multi-cylinder thermal circuits for individual CHTs and EGTs (thermal capacitance & dissipation).
4. Engine lubrication loop (oil pressure and oil temperature).
5. Liquid cylinder cooling circuit (coolant temperature).
6. Multi-axis mechanical vibration dynamics.
7. Realistic sensor noise and ADC quantization.
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple

from common.constants import (
    BORE_M, STROKE_M, DISPLACEMENT_M3, COMPRESSION_RATIO,
    MAX_RPM, IDLE_RPM, CRUISE_RPM_NOMINAL, MAX_POWER_KW,
    AIR_GAS_CONSTANT_R, LOWER_HEATING_VALUE_FUEL, STOICHIOMETRIC_AFR, FUEL_DENSITY_KG_L,
    ISA_SEA_LEVEL_TEMP_K, ISA_SEA_LEVEL_PRESSURE_PA, ISA_SEA_LEVEL_DENSITY,
    ISA_TEMP_LAPSE_RATE_K_PER_M, METERS_PER_FOOT,
    BASELINE_ETA_VOL, BASELINE_ETA_COMB, BASELINE_ETA_MECH
)
from simulator.fault_injector import FaultInjector


class EnginePhysicsSimulator:
    """
    Continuous-time aero-piston engine simulator running at 10 Hz.
    Integrates thermodynamic equations, thermal capacitance, and fault dynamics.
    """

    def __init__(self, fault_injector: Optional[FaultInjector] = None):
        self.fault_injector = fault_injector or FaultInjector()

        # Engine cumulative flight hours
        self.engine_hours: float = 142.5

        # Dynamic physical states (smooth continuous integration)
        self.rpm: float = IDLE_RPM
        self.cht: List[float] = [88.0, 89.2, 91.0, 88.5]     # Cyl 1-4 (°C)
        self.egt: List[float] = [715.0, 722.0, 730.0, 718.0] # Cyl 1-4 (°C)
        self.oil_temp_c: float = 82.0                        # Oil temp (°C)
        self.oil_pressure_bar: float = 4.2                   # Oil gallery pressure (bar)
        self.coolant_temp_c: float = 78.0                    # Coolant temp (°C)
        self.map_kpa: float = 80.0                           # Manifold Absolute Pressure (kPa)
        self.fuel_flow_lph: float = 12.0                     # Fuel flow (L/h)
        self.vibration_rms: float = 0.5                      # Vibration RMS (mm/s)
        self.bus_voltage: float = 13.8                       # Alternator voltage (V)

        # Thermal and rotational integration time constants (seconds)
        self.tau_rpm = 0.45
        self.tau_cht = 5.5
        self.tau_egt = 1.2
        self.tau_oil_temp = 14.0
        self.tau_oil_pressure = 0.6
        self.tau_coolant = 10.0

        # Sensor noise settings (standard deviations for Gaussian noise)
        self.noise_enabled = True
        self.noise_stds = {
            "rpm": 3.0,
            "cht": 0.35,
            "egt": 1.5,
            "oil_temp": 0.25,
            "oil_pressure": 0.02,
            "coolant_temp": 0.2,
            "map_kpa": 0.15,
            "fuel_flow": 0.1,
            "vibration": 0.03,
            "bus_voltage": 0.04
        }

    def compute_atmosphere(self, altitude_ft: float, ambient_temp_c: Optional[float] = None) -> Tuple[float, float, float]:
        """
        Compute ambient temperature (K), pressure (Pa), and density (kg/m^3) at altitude.
        """
        alt_m = max(0.0, altitude_ft * METERS_PER_FOOT)
        t_isa_k = ISA_SEA_LEVEL_TEMP_K - ISA_TEMP_LAPSE_RATE_K_PER_M * alt_m
        t_isa_k = max(216.65, t_isa_k)  # Tropopause clamp (~11,000m)

        # Barometric pressure formula
        p_pa = ISA_SEA_LEVEL_PRESSURE_PA * (t_isa_k / ISA_SEA_LEVEL_TEMP_K) ** 5.2561

        if ambient_temp_c is not None:
            t_actual_k = ambient_temp_c + 273.15
        else:
            t_actual_k = t_isa_k

        # Air density from ideal gas law: rho = P / (R * T)
        rho = p_pa / (AIR_GAS_CONSTANT_R * t_actual_k)
        return t_actual_k, p_pa, rho

    def step(
        self,
        dt: float,
        altitude_ft: float,
        ambient_temp_c: float,
        wind_speed_mps: float,
        throttle_pct: float,
        engine_load: float = 1.0,
        flight_phase: str = "cruise"
    ) -> Dict[str, any]:
        """
        Execute one continuous simulation step of length dt (seconds).
        Returns clean and noisy sensor telemetry.
        """
        # Advance engine total hours
        self.engine_hours += dt / 3600.0

        # Atmosphere
        t_amb_k, p_amb_pa, rho = self.compute_atmosphere(altitude_ft, ambient_temp_c)
        p_amb_kpa = p_amb_pa / 1000.0
        rho_ratio = rho / ISA_SEA_LEVEL_DENSITY

        # Normalize throttle [0.0, 1.0]
        throttle = max(0.0, min(1.0, throttle_pct / 100.0))

        # Retrieve active injected faults
        f_compression = self.fault_injector.get_fault_info("compression_loss")
        f_cooling = self.fault_injector.get_fault_info("overheating")
        f_lubrication = self.fault_injector.get_fault_info("lubrication_failure")
        f_ignition = self.fault_injector.get_fault_info("ignition_misfire")
        f_injector = self.fault_injector.get_fault_info("injector_clog")
        f_bearing = self.fault_injector.get_fault_info("bearing_wear")
        f_sensor = self.fault_injector.get_fault_info("sensor_drift")

        # -----------------------------------------------------------------
        # 1. Manifold Pressure & Volumetric Efficiency
        # -----------------------------------------------------------------
        eta_vol_engine = BASELINE_ETA_VOL
        if f_compression:
            # Compression loss degrades engine volumetric efficiency
            eta_vol_engine *= (1.0 - 0.35 * f_compression["severity"])

        # Manifold pressure: at idle ~38 kPa, at WOT ~ambient pressure * rho_ratio
        map_target_kpa = p_amb_kpa * (0.35 + 0.65 * throttle) * (eta_vol_engine / BASELINE_ETA_VOL)
        self.map_kpa += (dt / 0.2) * (map_target_kpa - self.map_kpa)

        # -----------------------------------------------------------------
        # 2. RPM & Torque Dynamics
        # -----------------------------------------------------------------
        # Effective aerodynamic propeller load factoring in wind and airspeed
        aero_load = engine_load * (1.0 + 0.004 * wind_speed_mps)
        if f_lubrication:
            # Metal-on-metal friction adds mechanical parasitic load
            aero_load += 0.25 * f_lubrication["severity"]

        # Target RPM curve based on throttle, density altitude, and aerodynamic load
        density_effect = math.sqrt(max(0.2, rho_ratio))
        rpm_target = IDLE_RPM + (MAX_RPM - IDLE_RPM) * (throttle ** 1.1) * density_effect / math.sqrt(max(0.5, aero_load))

        # Ignition misfire causes RPM drop and cyclic RPM flutter
        if f_ignition:
            rpm_target -= 350.0 * f_ignition["severity"]
            # Fast RPM cyclic wobble
            rpm_target += 45.0 * f_ignition["severity"] * math.sin(time_sec := self.engine_hours * 3600.0 * 8.0)

        rpm_target = max(IDLE_RPM * 0.85, min(MAX_RPM * 1.05, rpm_target))
        self.rpm += (dt / self.tau_rpm) * (rpm_target - self.rpm)

        # -----------------------------------------------------------------
        # 3. Fuel Mass Flow & Indicated Power
        # -----------------------------------------------------------------
        # Air mass flow rate (kg/s) through 4 cylinders
        intake_temp_k = t_amb_k + 8.0 * throttle  # Slight heat soak in intake runner
        m_dot_air = (self.map_kpa * 1000.0 * DISPLACEMENT_M3 * self.rpm) / (2.0 * AIR_GAS_CONSTANT_R * intake_temp_k * 60.0) * eta_vol_engine

        # Fuel mass flow (kg/s)
        afr = STOICHIOMETRIC_AFR
        m_dot_fuel = m_dot_air / afr
        target_fuel_flow_lph = (m_dot_fuel * 3600.0) / FUEL_DENSITY_KG_L
        self.fuel_flow_lph += (dt / 0.4) * (target_fuel_flow_lph - self.fuel_flow_lph)

        # Engine Power Output (kW)
        eta_comb = BASELINE_ETA_COMB
        if f_ignition:
            eta_comb *= (1.0 - 0.22 * f_ignition["severity"])
        eta_mech = BASELINE_ETA_MECH
        if f_lubrication:
            eta_mech *= (1.0 - 0.18 * f_lubrication["severity"])

        indicated_power_kw = (m_dot_fuel * LOWER_HEATING_VALUE_FUEL * eta_comb * 0.32) / 1000.0
        brake_power_kw = indicated_power_kw * eta_mech

        # -----------------------------------------------------------------
        # 4. Combustion Thermal Dynamics: EGT 1-4 (°C)
        # -----------------------------------------------------------------
        # Base EGT is a function of throttle, air-fuel mixture, and combustion completeness
        base_egt = 650.0 + 130.0 * throttle + 30.0 * (1.0 - rho_ratio)

        # Individual cylinder distribution (natural manufacturing/airflow spread)
        cyl_offsets_egt = [-4.0, +3.0, +7.0, -2.0]
        for i in range(4):
            cyl_num = i + 1
            cyl_egt_target = base_egt + cyl_offsets_egt[i]

            # Injected fault: Injector clog on target cylinder -> severe lean burn -> EGT SPIKES
            if f_injector and f_injector.get("target_cylinder") == cyl_num:
                cyl_egt_target += 135.0 * f_injector["severity"]  # EGT up to 880°C

            # Injected fault: Ignition misfire on target cylinder -> unburned charge -> EGT PLUNGES
            if f_ignition and f_ignition.get("target_cylinder") == cyl_num:
                cyl_egt_target -= 260.0 * f_ignition["severity"]  # EGT drops to ~480°C

            self.egt[i] += (dt / self.tau_egt) * (cyl_egt_target - self.egt[i])

        # -----------------------------------------------------------------
        # 5. Liquid Cooling Circuit & CHT 1-4 (°C)
        # -----------------------------------------------------------------
        # Coolant loop absorbs heat from combustion and rejects to radiator
        radiator_effectiveness = 1.0
        coolant_tau = self.tau_coolant
        if f_cooling:
            # Severe radiator blockage or coolant pump failure
            radiator_effectiveness = max(0.12, 1.0 - 0.88 * f_cooling["severity"])
            coolant_tau = 3.5  # Coolant boils quickly in cylinder jackets when flow stops

        cooling_airflow_mps = max(5.0, wind_speed_mps + 50.0 * (self.rpm / MAX_RPM))
        heat_generated_kw = brake_power_kw * 0.45
        target_coolant = (ambient_temp_c + 55.0) + (heat_generated_kw / 35.0) * (25.0 / radiator_effectiveness)
        if f_cooling:
            target_coolant += 28.0 * f_cooling["severity"]
        target_coolant = max(ambient_temp_c + 10.0, min(135.0, target_coolant))
        self.coolant_temp_c += (dt / coolant_tau) * (target_coolant - self.coolant_temp_c)

        # Cylinder Head Temperatures (CHT 1-4)
        cyl_offsets_cht = [-1.5, +1.0, +2.5, -0.8]
        for i in range(4):
            cyl_num = i + 1
            # CHT tracks coolant temp + local combustion thermal load
            target_cht = self.coolant_temp_c + 18.0 + (brake_power_kw / MAX_POWER_KW) * 28.0 + cyl_offsets_cht[i]

            # Cooling failure causes overall CHT surge
            if f_cooling:
                target_cht += 25.0 * f_cooling["severity"]

            # Compression loss on cylinder reduces local combustion heat
            if f_compression and f_compression.get("target_cylinder") == cyl_num:
                target_cht -= 14.0 * f_compression["severity"]

            # Injector clog slight CHT rise due to lean thermal peak
            if f_injector and f_injector.get("target_cylinder") == cyl_num:
                target_cht += 18.0 * f_injector["severity"]

            self.cht[i] += (dt / self.tau_cht) * (target_cht - self.cht[i])

        # -----------------------------------------------------------------
        # 6. Lubrication Loop: Oil Temperature & Pressure
        # -----------------------------------------------------------------
        # Oil Temperature: friction and piston splash heat
        oil_cooler_eff = 1.0
        if f_lubrication:
            oil_cooler_eff = max(0.3, 1.0 - 0.6 * f_lubrication["severity"])
        if f_cooling:
            oil_cooler_eff *= max(0.4, 1.0 - 0.5 * f_cooling["severity"])

        target_oil_temp = ambient_temp_c + 45.0 + (brake_power_kw / MAX_POWER_KW) * 35.0 / oil_cooler_eff
        if f_lubrication:
            # Friction heat increases oil temp significantly
            target_oil_temp += 32.0 * f_lubrication["severity"]
        self.oil_temp_c += (dt / self.tau_oil_temp) * (target_oil_temp - self.oil_temp_c)

        # Oil Pressure: Gear pump delivers pressure proportional to RPM, inversely to oil temperature
        temp_viscosity_factor = 1.0 - 0.005 * (self.oil_temp_c - 80.0)
        nominal_oil_p = (1.8 + 3.4 * (self.rpm / MAX_RPM)) * temp_viscosity_factor

        if f_lubrication:
            # Oil pressure collapse: drops below safe threshold (e.g. 1.3 - 1.8 bar)
            nominal_oil_p *= max(0.2, 1.0 - 0.72 * f_lubrication["severity"])

        target_oil_pressure = max(0.5, min(7.5, nominal_oil_p))
        self.oil_pressure_bar += (dt / self.tau_oil_pressure) * (target_oil_pressure - self.oil_pressure_bar)

        # -----------------------------------------------------------------
        # 7. Mechanical Vibration Spectrum (RMS & 3-Axis)
        # -----------------------------------------------------------------
        # Base rotational vibration scales with RPM^2 and load
        base_vib = 0.25 + 0.95 * ((self.rpm / MAX_RPM) ** 2) + 0.25 * (brake_power_kw / MAX_POWER_KW)

        if f_bearing:
            # Severe bearing wear injects huge high-frequency vibration
            base_vib += 4.5 * f_bearing["severity"]

        if f_ignition:
            # Rough engine misfire adds combustion unbalance vibration
            base_vib += 1.4 * f_ignition["severity"]

        self.vibration_rms += (dt / 0.5) * (base_vib - self.vibration_rms)

        vib_x = self.vibration_rms * 0.72 + 0.05 * math.sin(self.engine_hours * 3600 * 12.0)
        vib_y = self.vibration_rms * 0.85 + 0.05 * math.cos(self.engine_hours * 3600 * 12.0)
        vib_z = self.vibration_rms * 0.55

        # -----------------------------------------------------------------
        # 8. Bus Voltage
        # -----------------------------------------------------------------
        target_voltage = 13.6 + 0.6 * (self.rpm / MAX_RPM)
        self.bus_voltage += (dt / 1.0) * (target_voltage - self.bus_voltage)

        # -----------------------------------------------------------------
        # 9. Apply Sensor Emulation & Noise
        # -----------------------------------------------------------------
        out_rpm = self.rpm
        out_cht = list(self.cht)
        out_egt = list(self.egt)
        out_oil_temp = self.oil_temp_c
        out_oil_press = self.oil_pressure_bar
        out_coolant = self.coolant_temp_c
        out_map = self.map_kpa
        out_fuel_flow = self.fuel_flow_lph
        out_vib_rms = self.vibration_rms
        out_bus_v = self.bus_voltage

        # Sensor drift injection: if active, corrupts specific sensor reading
        if f_sensor:
            # Adds substantial false bias to Cylinder 2 CHT probe
            out_cht[1] += 42.0 * f_sensor["severity"]

        if self.noise_enabled:
            out_rpm += np.random.normal(0.0, self.noise_stds["rpm"])
            out_cht = [c + np.random.normal(0.0, self.noise_stds["cht"]) for c in out_cht]
            out_egt = [e + np.random.normal(0.0, self.noise_stds["egt"]) for e in out_egt]
            out_oil_temp += np.random.normal(0.0, self.noise_stds["oil_temp"])
            out_oil_press += np.random.normal(0.0, self.noise_stds["oil_pressure"])
            out_coolant += np.random.normal(0.0, self.noise_stds["coolant_temp"])
            out_map += np.random.normal(0.0, self.noise_stds["map_kpa"])
            out_fuel_flow += np.random.normal(0.0, self.noise_stds["fuel_flow"])
            out_vib_rms += np.random.normal(0.0, self.noise_stds["vibration"])
            vib_x += np.random.normal(0.0, self.noise_stds["vibration"])
            vib_y += np.random.normal(0.0, self.noise_stds["vibration"])
            vib_z += np.random.normal(0.0, self.noise_stds["vibration"])
            out_bus_v += np.random.normal(0.0, self.noise_stds["bus_voltage"])

        # Construct raw telemetry dictionary
        telemetry_frame = {
            "rpm": round(float(out_rpm), 1),
            "cht": [round(float(c), 1) for c in out_cht],
            "egt": [round(float(e), 1) for e in out_egt],
            "oil_temp_c": round(float(out_oil_temp), 1),
            "oil_pressure_bar": round(float(max(0.1, out_oil_press)), 2),
            "coolant_temp_c": round(float(out_coolant), 1),
            "map_kpa": round(float(out_map), 1),
            "fuel_flow_lph": round(float(max(0.5, out_fuel_flow)), 2),
            "vibration": {
                "x": round(float(vib_x), 3),
                "y": round(float(vib_y), 3),
                "z": round(float(vib_z), 3),
                "rms": round(float(max(0.05, out_vib_rms)), 3),
            },
            "bus_voltage": round(float(out_bus_v), 2),
            "power_kw": round(float(brake_power_kw), 1),
            "ambient_pressure_kpa": round(float(p_amb_kpa), 2),
            "engine_hours": round(float(self.engine_hours), 3)
        }
        return telemetry_frame
