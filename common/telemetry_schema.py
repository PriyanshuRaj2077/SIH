"""
AeroPulse Standard Telemetry Protocol & Schema
Pydantic model for high-frequency (10 Hz) serializable telemetry frames.
Supports validation, serialization, deserialization, and future ECU/CAN bridging.
"""

from typing import List, Dict, Optional
import json
from pydantic import BaseModel, Field


class FlightEnvironment(BaseModel):
    """Ambient and operator flight control conditions"""
    altitude_ft: float = Field(default=0.0, description="Flight altitude in feet MSL")
    ambient_temp_c: float = Field(default=15.0, description="Static ambient air temperature in deg C")
    ambient_pressure_kpa: float = Field(default=101.325, description="Ambient barometric pressure in kPa")
    wind_speed_mps: float = Field(default=0.0, description="Ambient wind speed in m/s")
    throttle_pct: float = Field(default=50.0, description="Pilot throttle demand 0.0 to 100.0%")
    engine_load: float = Field(default=1.0, description="Normalized aerodynamic propeller load factor")
    flight_phase: str = Field(default="cruise", description="Active flight regime")


class VibrationTelemetry(BaseModel):
    """3-Axis and composite vibration acceleration"""
    x: float = Field(default=0.0, description="Lateral acceleration (mm/s)")
    y: float = Field(default=0.0, description="Vertical acceleration (mm/s)")
    z: float = Field(default=0.0, description="Axial acceleration (mm/s)")
    rms: float = Field(default=0.5, description="Composite RMS vibration (mm/s)")


class SensorTelemetry(BaseModel):
    """Aero Piston Engine Sensor Suite (11 primary telemetry channels)"""
    rpm: float = Field(default=1400.0, description="Crankshaft rotational speed (RPM)")
    cht: List[float] = Field(default_factory=lambda: [90.0, 90.0, 90.0, 90.0], description="Cylinder Head Temps Cyl 1-4 (deg C)")
    egt: List[float] = Field(default_factory=lambda: [720.0, 720.0, 720.0, 720.0], description="Exhaust Gas Temps Cyl 1-4 (deg C)")
    oil_temp_c: float = Field(default=85.0, description="Engine lubrication oil temperature (deg C)")
    oil_pressure_bar: float = Field(default=4.0, description="Engine oil gallery pressure (bar)")
    coolant_temp_c: float = Field(default=80.0, description="Liquid cylinder jacket coolant temp (deg C)")
    map_kpa: float = Field(default=85.0, description="Manifold Absolute Pressure (kPa)")
    fuel_flow_lph: float = Field(default=14.0, description="Fuel volumetric flow rate (L/h)")
    vibration: VibrationTelemetry = Field(default_factory=VibrationTelemetry, description="3-axis and RMS engine vibration")
    bus_voltage: float = Field(default=13.8, description="Generator/electrical bus voltage (V)")


class SensorStatusFlags(BaseModel):
    """Sensor hardware integrity and health status"""
    cht_probes: List[str] = Field(default_factory=lambda: ["OK", "OK", "OK", "OK"])
    egt_probes: List[str] = Field(default_factory=lambda: ["OK", "OK", "OK", "OK"])
    oil_sensors: str = Field(default="OK")
    map_sensor: str = Field(default="OK")
    vibration_sensor: str = Field(default="OK")


class TelemetryPacket(BaseModel):
    """Top-Level Telemetry Frame transmitted at 10 Hz"""
    packet_id: int = Field(default=0, description="Monotonically increasing sequence number")
    timestamp: float = Field(default=0.0, description="Unix timestamp with millisecond precision")
    engine_hours: float = Field(default=120.0, description="Cumulative engine total operating hours")
    flight_env: FlightEnvironment = Field(default_factory=FlightEnvironment)
    telemetry: SensorTelemetry = Field(default_factory=SensorTelemetry)
    sensor_status: SensorStatusFlags = Field(default_factory=SensorStatusFlags)

    def to_json(self) -> str:
        """Serialize to compact JSON string"""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "TelemetryPacket":
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls.model_validate(data)
