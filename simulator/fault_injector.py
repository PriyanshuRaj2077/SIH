"""
AeroPulse Fault Injection Engine
Provides logically consistent, mathematically modeled fault profiles
for UAV aero-piston engine components.
"""

from typing import Dict, Optional, Any
import time


class FaultInjector:
    """
    Manages active faults and computes real-time degradation multipliers.
    Each fault mode impacts physical thermodynamic & mechanical parameters.
    """

    AVAILABLE_FAULTS = {
        "compression_loss": {
            "name": "Cylinder Compression Loss",
            "description": "Piston ring wear / valve leak reducing volumetric efficiency and cylinder pressure.",
            "target": "cyl_volumetric_eff",
            "default_severity": 0.6,
        },
        "overheating": {
            "name": "Cooling System Degradation",
            "description": "Radiator airflow restriction or coolant pump degradation causing thermal runaway.",
            "target": "cooling_effectiveness",
            "default_severity": 0.7,
        },
        "lubrication_failure": {
            "name": "Lubrication Oil Degradation",
            "description": "Oil pump bypass leak or oil starvation causing pressure collapse and friction surge.",
            "target": "oil_system",
            "default_severity": 0.75,
        },
        "ignition_misfire": {
            "name": "Ignition Spark Misfire",
            "description": "Spark plug fouling or coil failure leading to partial combustion and RPM flutter.",
            "target": "cylinder_ignition",
            "default_severity": 0.8,
        },
        "injector_clog": {
            "name": "Fuel Injector Partial Clog",
            "description": "Partial fuel injector restriction leading to localized lean burn and EGT surge.",
            "target": "fuel_mixture",
            "default_severity": 0.7,
        },
        "bearing_wear": {
            "name": "Crankshaft / Gearbox Bearing Wear",
            "description": "Mechanical race spalling generating severe rotational and harmonic vibration.",
            "target": "mechanical_vibration",
            "default_severity": 0.8,
        },
        "sensor_drift": {
            "name": "Sensor Probe Bias / Drift",
            "description": "Thermocouple junction drift or calibration bias causing telemetry offset.",
            "target": "sensor_calibration",
            "default_severity": 0.6,
        },
    }

    def __init__(self):
        # Maps fault_type -> { "severity": float, "target_cylinder": Optional[int], "start_time": float }
        self._active_faults: Dict[str, Dict[str, Any]] = {}

    def set_fault(self, fault_type: str, severity: float = 0.5, target_cylinder: Optional[int] = 3) -> bool:
        """Inject or update a specific fault state"""
        if fault_type not in self.AVAILABLE_FAULTS:
            return False

        clamped_severity = max(0.0, min(1.0, float(severity)))
        if clamped_severity <= 0.001:
            self.clear_fault(fault_type)
            return True

        self._active_faults[fault_type] = {
            "severity": clamped_severity,
            "target_cylinder": target_cylinder if target_cylinder in (1, 2, 3, 4) else 3,
            "start_time": time.time(),
        }
        return True

    def clear_fault(self, fault_type: str) -> bool:
        """Clear an active fault"""
        if fault_type in self._active_faults:
            del self._active_faults[fault_type]
            return True
        return False

    def clear_all_faults(self):
        """Reset all injected faults to nominal"""
        self._active_faults.clear()

    def is_fault_active(self, fault_type: str) -> bool:
        """Check if a specific fault is active"""
        return fault_type in self._active_faults

    def get_fault_info(self, fault_type: str) -> Optional[Dict[str, Any]]:
        """Get details for an active fault"""
        return self._active_faults.get(fault_type)

    def get_active_faults(self) -> Dict[str, Dict[str, Any]]:
        """Return snapshot of all active faults"""
        return dict(self._active_faults)
