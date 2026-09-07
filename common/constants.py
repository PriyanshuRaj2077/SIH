"""
AeroPulse Engine & Physical Constants
Reference Engine: Rotax 912/914-class 4-stroke flat-four aero piston engine
Derived from published technical manuals & aviation standards.
"""

from typing import Dict, Tuple

# =====================================================================
# Reference Engine Specifications (Rotax 912 ULS proxy)
# =====================================================================
BORE_M = 0.084                  # Cylinder bore (84 mm)
STROKE_M = 0.061                # Piston stroke (61 mm)
CON_ROD_LENGTH_M = 0.122        # Connecting rod length (122 mm)
NUM_CYLINDERS = 4               # Horizontally opposed 4-cylinder
DISPLACEMENT_M3 = 1.352e-3      # 1352 cc total displacement
COMPRESSION_RATIO = 10.5        # Geometric compression ratio
MAX_RPM = 5800.0                # Redline engine speed
IDLE_RPM = 1400.0               # Ground idle speed
CRUISE_RPM_NOMINAL = 4800.0     # Nominal cruise speed
MAX_POWER_HP = 100.0            # Rated maximum takeoff power (HP)
MAX_POWER_KW = 74.57            # Rated maximum power (kW)
REDUCTION_GEAR_RATIO = 2.43     # Propeller reduction gear ratio

# Thermodynamic constants
AIR_GAS_CONSTANT_R = 287.05     # J/(kg·K)
SPECIFIC_HEAT_RATIO_AIR = 1.40  # Gamma for dry air
LOWER_HEATING_VALUE_FUEL = 44.0e6  # J/kg (Avgas 100LL / Mogas 95)
STOICHIOMETRIC_AFR = 14.7       # Air-Fuel Ratio (stoichiometric)
FUEL_DENSITY_KG_L = 0.72        # Fuel density (kg/L)

# =====================================================================
# International Standard Atmosphere (ISA) Constants
# =====================================================================
ISA_SEA_LEVEL_TEMP_K = 288.15   # 15.0 °C
ISA_SEA_LEVEL_PRESSURE_PA = 101325.0 # 101.325 kPa
ISA_SEA_LEVEL_DENSITY = 1.225   # kg/m^3
ISA_TEMP_LAPSE_RATE_K_PER_M = 0.0065 # 6.5 K / 1000 m
GRAVITATIONAL_ACCEL = 9.80665   # m/s^2
METERS_PER_FOOT = 0.3048

# =====================================================================
# Nominal Degradation State Parameters (Health Baselines)
# =====================================================================
BASELINE_ETA_VOL = 0.88         # Nominal volumetric efficiency
BASELINE_ETA_COMB = 0.96        # Nominal combustion efficiency
BASELINE_ETA_MECH = 0.90        # Nominal mechanical efficiency

# =====================================================================
# Sensor Operational Limits & Thresholds
# Format: (Normal_Min, Normal_Max, Caution_Max, Critical_Max)
# =====================================================================
SENSOR_THRESHOLDS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "rpm": {
        "normal": (1350.0, 5500.0),
        "caution": (5500.0, 5800.0),
        "critical": (0.0, 6000.0),
    },
    "cht": {
        "normal": (75.0, 130.0),
        "caution": (130.0, 145.0),
        "critical": (50.0, 150.0),
    },
    "egt": {
        "normal": (650.0, 830.0),
        "caution": (830.0, 870.0),
        "critical": (500.0, 890.0),
    },
    "oil_temp": {
        "normal": (65.0, 110.0),
        "caution": (110.0, 125.0),
        "critical": (40.0, 135.0),
    },
    "oil_pressure": {
        "normal": (2.5, 5.5),      # bar
        "caution": (2.0, 6.2),
        "critical": (1.5, 7.0),
    },
    "coolant_temp": {
        "normal": (70.0, 95.0),
        "caution": (95.0, 110.0),
        "critical": (40.0, 115.0),
    },
    "map_kpa": {
        "normal": (55.0, 105.0),
        "caution": (50.0, 112.0),
        "critical": (40.0, 120.0),
    },
    "fuel_flow": {
        "normal": (8.0, 26.0),     # L/h
        "caution": (6.0, 29.0),
        "critical": (3.0, 34.0),
    },
    "vibration_rms": {
        "normal": (0.2, 1.8),      # mm/s
        "caution": (1.8, 3.5),
        "critical": (0.0, 5.0),
    },
    "bus_voltage": {
        "normal": (13.5, 14.4),    # V
        "caution": (12.5, 15.0),
        "critical": (11.5, 15.5),
    }
}

# Real-time Telemetry Transport Defaults
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 8765
DEFAULT_WS_URI = f"ws://{DEFAULT_WS_HOST}:{DEFAULT_WS_PORT}/telemetry"
DEFAULT_UDP_PORT = 9000
TELEMETRY_SAMPLE_RATE_HZ = 10
TELEMETRY_DT_SECONDS = 1.0 / TELEMETRY_SAMPLE_RATE_HZ
