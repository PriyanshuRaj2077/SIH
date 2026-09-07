"""
AeroPulse Operational Advisory Generator
Translates Digital Twin state, fault attribution, and mission risk into
clear, natural-language, actionable instructions for UAV Pilot and Ground Maintenance.
"""

from typing import Dict, Any, List


class AdvisoryGenerator:
    """
    Generates pilot advisories, mission go/no-go directions,
    and post-flight maintenance work orders.
    """

    @staticmethod
    def generate_advisory(
        analytics_output: Dict[str, Any],
        health_risk_output: Dict[str, Any],
        dt_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate contextual operational advice.
        """
        diagnosis = analytics_output["fault_diagnosis"]
        fault_code = diagnosis["code"]
        health = health_risk_output["health_score"]
        risk = health_risk_output["risk_code"]
        rul = health_risk_output["rul"]

        pilot_actions: List[str] = []
        maintenance_actions: List[str] = []
        urgency: str = "NORMAL"

        if fault_code == "F05":  # Lubrication failure
            urgency = "IMMEDIATE"
            pilot_actions = [
                "1. Immediately throttle back to 55-60% to reduce bearing journal load.",
                "2. Turn aircraft toward nearest recovery airfield / home base (RTB).",
                "3. Maintain best glide airspeed; avoid any climb maneuvers.",
                f"4. Land within estimated safe window ({rul['display']}) to prevent catastrophic in-flight engine seizure."
            ]
            maintenance_actions = [
                "• Perform full lubrication system teardown and oil filter cut examination for metal flakes.",
                "• Inspect oil pressure relief valve spring and plunger for debris sticking.",
                "• Conduct oil pump gear backlash and scavenge pump check per Rotax Maintenance Manual Section 12-20.",
                "• Bore-scope crankshaft main journals and connecting rod big-end bearings."
            ]

        elif fault_code == "F06":  # Overheating / Radiator
            urgency = "HIGH"
            pilot_actions = [
                "1. Reduce throttle demand to 60% cruise setting.",
                "2. Descend to denser, cooler air mass (e.g. below 10,000 ft) if mission airspace allows.",
                "3. Increase airspeed to maximize radiator ram-air cooling velocity.",
                "4. If CHT exceeds 145°C or coolant exceeds 115°C, initiate immediate forced descent and RTB."
            ]
            maintenance_actions = [
                "• Inspect radiator matrix and air ducting for bird strike, dust buildup, or debris ingestion.",
                "• Check coolant expansion bottle level and pressure cap seal (0.9 / 1.2 bar).",
                "• Verify mechanical coolant pump impeller integrity and drive belt tension.",
                "• Flush and bleed cylinder head cooling jackets."
            ]

        elif fault_code == "F03":  # Injector Clog / Lean Burn
            urgency = "ELEVATED"
            pilot_actions = [
                "1. Enrich air-fuel mixture command via ECU override or reduce throttle to 65%.",
                "2. Avoid full-throttle climb which will trigger thermal valve seat burning.",
                "3. Continue mission on modified profile or return to base if CHT continues trending upward."
            ]
            maintenance_actions = [
                f"• Remove and ultrasonic-clean {diagnosis['subsystem']}.",
                "• Replace inline fuel micro-filter (10 micron).",
                "• Test fuel rail delivery pressure (nominal 3.0 bar) and flow bench calibrate injectors.",
                "• Inspect affected cylinder combustion chamber with borescope for thermal discoloration."
            ]

        elif fault_code == "F02":  # Ignition Misfire
            urgency = "ELEVATED"
            pilot_actions = [
                "1. Switch ECU ignition channel select from AUTO to manual Lane A / Lane B check.",
                "2. Avoid idle settings where misfire causes severe airframe resonance.",
                "3. Abort high-threat mission tasks; return to base for ignition servicing."
            ]
            maintenance_actions = [
                f"• Inspect and replace spark plugs on {diagnosis['subsystem']} (gap 0.6 - 0.7 mm).",
                "• Check ignition coil secondary resistance and spark plug connector caps.",
                "• Verify crankshaft trigger pickup gap (0.4 - 0.5 mm) and wiring harness continuity."
            ]

        elif fault_code == "F08":  # Bearing Wear / Vibration
            urgency = "HIGH"
            pilot_actions = [
                "1. Reduce engine RPM below harmonic vibration peak (set throttle to 55-65%).",
                "2. Check propeller pitch governor response.",
                "3. Terminate mission; route direct to base to avoid fatigue failure of engine mounts or propeller."
            ]
            maintenance_actions = [
                "• Dynamic propeller balance check (spectral 1X/2X order vibration analysis).",
                "• Inspect reduction gearbox dog clutch and Belleville spring pre-load.",
                "• Drain oil and check magnetic drain plug for ferrous metal fuzz.",
                "• Measure crankshaft runout and propeller shaft radial play."
            ]

        elif fault_code == "F01":  # Compression Loss
            urgency = "MODERATE"
            pilot_actions = [
                "1. Engine maximum power degraded by ~15-25%; plan descent accordingly.",
                "2. Monitor oil consumption and crankcase breather blowby.",
                "3. Complete low-demand tasks or RTB."
            ]
            maintenance_actions = [
                "• Perform differential pressure compression test (min 60/80 psi required).",
                "• Bore-scope cylinder cross-hatch hone and piston crown for blowby scoring.",
                "• Inspect intake and exhaust valve lash clearances."
            ]

        elif fault_code == "F11":  # Sensor Drift
            urgency = "LOW"
            pilot_actions = [
                "1. Cross-check uncoupled sensor telemetry (Coolant and EGT normal).",
                "2. Engine physical health is verified intact by Digital Twin model.",
                "3. Mission can proceed with reliance on remaining healthy redundant sensor channels."
            ]
            maintenance_actions = [
                "• Recalibrate or replace thermocouple probe.",
                "• Verify avionics ADC wiring shielding and terminal block tightness."
            ]

        else:
            urgency = "NOMINAL"
            pilot_actions = [
                "• Powertrain operating within nominal green band.",
                "• All physical variables tracking Digital Twin baseline within 1.2 standard deviations.",
                "• Full mission flight envelope approved (Takeoff, Climb, Cruise, Loiter)."
            ]
            maintenance_actions = [
                "• Routine post-flight pre-flight inspection at next 25-hour service interval."
            ]

        advisory_title = f"{'ALERT - ANOMALY DETECTED: ' if analytics_output['is_anomaly'] else 'NOMINAL STATUS: '}{diagnosis['name'].upper()}"

        return {
            "title": advisory_title,
            "urgency": urgency,
            "fault_code": fault_code,
            "subsystem": diagnosis["subsystem"],
            "root_cause_summary": diagnosis["root_cause"],
            "pilot_instructions": pilot_actions,
            "maintenance_instructions": maintenance_actions,
            "mission_decision": health_risk_output["recommendation"]
        }
