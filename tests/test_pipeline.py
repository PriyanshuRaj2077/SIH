"""
Comprehensive Pipeline & Fault Diagnosis Verification Suite
Tests the complete coupled chain:
Simulator Physics -> Telemetry Serialization -> Digital Twin EKF -> Residuals -> Analytics & Attribution -> Health/Risk -> Advisory
"""

import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.telemetry_schema import TelemetryPacket, FlightEnvironment, SensorTelemetry
from simulator.physics_engine import EnginePhysicsSimulator
from dashboard.digital_twin import DigitalTwin
from dashboard.analytics import AnalyticsEngine
from dashboard.health_risk import HealthRiskCalculator
from dashboard.advisory import AdvisoryGenerator


def run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=20, alt=5000, temp=15.0, wind=6.0, throttle=72.0):
    for _ in range(steps):
        frame = sim.step(0.1, alt, temp, wind, throttle)
        packet = TelemetryPacket(
            packet_id=1,
            timestamp=time.time(),
            engine_hours=frame["engine_hours"],
            flight_env=FlightEnvironment(
                altitude_ft=alt,
                ambient_temp_c=temp,
                wind_speed_mps=wind,
                throttle_pct=throttle
            ),
            telemetry=SensorTelemetry(**{k: v for k, v in frame.items() if k in SensorTelemetry.model_fields})
        )
        dt_out = dt.update(packet)
        analytics_out = analytics.evaluate_residuals(dt_out)
        hr_out = hr_calc.calculate_health_and_risk(dt_out, analytics_out)
        adv_out = adv_gen.generate_advisory(analytics_out, hr_out, dt_out)
    return dt_out, analytics_out, hr_out, adv_out


def test_complete_fault_suite():
    print("==================================================================")
    print("  RUNNING AEROPULSE FULL DIGITAL TWIN & FAULT SUITE VERIFICATION  ")
    print("==================================================================")

    sim = EnginePhysicsSimulator()
    dt = DigitalTwin()
    analytics = AnalyticsEngine()
    hr_calc = HealthRiskCalculator()
    adv_gen = AdvisoryGenerator()

    # 1. Nominal Flight Condition
    print("\n[TEST 1] Nominal Flight at 25,000 ft, 72% Throttle...")
    dt_out, a_out, hr_out, adv_out = run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=25, alt=25000)
    print(f" -> Health Score: {hr_out['health_score']}% (Target: > 80%)")
    print(f" -> Mission Risk: {hr_out['mission_risk']} (Target: LOW)")
    print(f" -> Anomaly Flag: {a_out['is_anomaly']} (Target: False)")
    print(f" -> Diagnosis: {a_out['fault_diagnosis']['name']}")
    assert hr_out["health_score"] >= 80.0
    assert a_out["is_anomaly"] is False
    assert hr_out["risk_code"] == "LOW"
    print(" -> [PASS] Nominal baseline tracking verified!")

    # 2. Inject Lubrication Failure
    print("\n[TEST 2] Injecting F05: Lubrication Failure (Oil Pressure Collapse)...")
    sim.fault_injector.set_fault("lubrication_failure", severity=0.85)
    dt_out, a_out, hr_out, adv_out = run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=20, alt=25000)
    print(f" -> Health Score: {hr_out['health_score']}% (Target: < 60%)")
    print(f" -> Mission Risk: {hr_out['mission_risk']} (Target: HIGH)")
    print(f" -> Diagnosed Code: {a_out['fault_diagnosis']['code']} (Target: F05)")
    print(f" -> Diagnosed Name: {a_out['fault_diagnosis']['name']}")
    print(f" -> Subsystem: {a_out['fault_diagnosis']['subsystem']}")
    print(f" -> Advisory Title: {adv_out['title']}")
    assert a_out["is_anomaly"] is True
    assert a_out["fault_diagnosis"]["code"] == "F05"
    assert hr_out["risk_code"] == "HIGH"
    print(" -> [PASS] F05 Lubrication Failure diagnosed successfully!")
    sim.fault_injector.clear_all_faults()
    # Let engine recover
    run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=15, alt=25000)

    # 3. Inject Cooling System Failure
    print("\n[TEST 3] Injecting F06: Cooling Degradation (Thermal Runaway)...")
    sim.fault_injector.set_fault("overheating", severity=0.85)
    dt_out, a_out, hr_out, adv_out = run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=20, alt=25000)
    print(f" -> Diagnosed Code: {a_out['fault_diagnosis']['code']} (Target: F06)")
    print(f" -> Diagnosed Name: {a_out['fault_diagnosis']['name']}")
    assert a_out["is_anomaly"] is True
    assert a_out["fault_diagnosis"]["code"] == "F06"
    print(" -> [PASS] F06 Cooling Failure diagnosed successfully!")
    sim.fault_injector.clear_all_faults()
    run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=15, alt=25000)

    # 4. Inject Fuel Injector Clog
    print("\n[TEST 4] Injecting F03: Fuel Injector Clog (Cyl 3 Lean Burn)...")
    sim.fault_injector.set_fault("injector_clog", severity=0.8, target_cylinder=3)
    dt_out, a_out, hr_out, adv_out = run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=20, alt=25000)
    print(f" -> Diagnosed Code: {a_out['fault_diagnosis']['code']} (Target: F03)")
    print(f" -> Diagnosed Name: {a_out['fault_diagnosis']['name']}")
    assert a_out["is_anomaly"] is True
    assert a_out["fault_diagnosis"]["code"] == "F03"
    print(" -> [PASS] F03 Fuel Injector Clog diagnosed successfully!")
    sim.fault_injector.clear_all_faults()
    run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=15, alt=25000)

    # 5. Inject Bearing Wear
    print("\n[TEST 5] Injecting F08: Bearing Wear (High-Frequency Vibration Spike)...")
    sim.fault_injector.set_fault("bearing_wear", severity=0.85)
    dt_out, a_out, hr_out, adv_out = run_pipeline_steps(sim, dt, analytics, hr_calc, adv_gen, steps=15, alt=25000)
    print(f" -> Diagnosed Code: {a_out['fault_diagnosis']['code']} (Target: F08)")
    print(f" -> Diagnosed Name: {a_out['fault_diagnosis']['name']}")
    assert a_out["is_anomaly"] is True
    assert a_out["fault_diagnosis"]["code"] == "F08"
    print(" -> [PASS] F08 Bearing Wear diagnosed successfully!")
    sim.fault_injector.clear_all_faults()

    print("\n==================================================================")
    print("  ALL 5 CORE VERIFICATION TESTS PASSED WITH 100% ACCURACY!        ")
    print("==================================================================")


if __name__ == "__main__":
    test_complete_fault_suite()
