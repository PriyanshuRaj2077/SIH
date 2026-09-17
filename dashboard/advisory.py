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
        tactical_actions: List[str] = []
        urgency: str = "NOMINAL"

        is_anomaly = analytics_output.get("is_anomaly", False)
        severity = analytics_output.get("severity", "NOMINAL")

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
            tactical_actions = [
                "• Immediate Mission Abort (RTB): Discontinue tactical loiter and mission objectives immediately.",
                "• Vector direct to primary emergency recovery runway or designated ditching waypoint.",
                f"• Safe Window: Estimated {rul['display']} remaining before hydrodynamic oil film breakdown.",
                "• Request priority airspace clearance and alert ground emergency crash tender."
            ]

        elif fault_code == "F06":  # Overheating / Radiator
            urgency = "HIGH"
            pilot_actions = [
                "1. Reduce throttle demand to 60% cruise setting.",
                "2. Descend to denser, cooler air mass (e.g. below 8,000 ft) if mission airspace allows.",
                "3. Increase indicated airspeed to maximize radiator ram-air cooling velocity.",
                "4. If CHT exceeds 145°C or coolant exceeds 115°C, initiate immediate forced descent and RTB."
            ]
            maintenance_actions = [
                "• Inspect radiator matrix and air ducting for bird strike, dust buildup, or debris ingestion.",
                "• Check coolant expansion bottle level and pressure cap seal (0.9 / 1.2 bar).",
                "• Verify mechanical coolant pump impeller integrity and drive belt tension.",
                "• Flush and bleed cylinder head cooling jackets."
            ]
            tactical_actions = [
                "• Flight Envelope Restriction: Continuous power capped at 60% MAP; climb maneuvers prohibited.",
                "• Altimetry Directive: Descend into ambient cooler dense boundary layer to enhance heat rejection.",
                "• Tactical Re-route: Establish direct course to recovery airfield with minimum thermal accumulation.",
                "• Mission Decision: Abort persistent loiter; payload set to low-drag stow position."
            ]

        elif fault_code == "F03":  # Injector Clog / Lean Burn
            urgency = "ELEVATED"
            pilot_actions = [
                "1. Enrich air-fuel mixture command via ECU override or reduce throttle to 65%.",
                "2. Avoid full-throttle climb which will trigger localized thermal valve seat burning.",
                "3. Continue mission on modified profile or return to base if CHT continues trending upward."
            ]
            maintenance_actions = [
                f"• Remove and ultrasonic-clean {diagnosis['subsystem']}.",
                "• Replace inline fuel micro-filter (10 micron).",
                "• Test fuel rail delivery pressure (nominal 3.0 bar) and flow bench calibrate injectors.",
                "• Inspect affected cylinder combustion chamber with borescope for thermal discoloration."
            ]
            tactical_actions = [
                "• Operational Envelope Restriction: Restrict ceiling to 14,000 ft MSL to avoid lean vaporization.",
                "• Abort High-Demand Mission Legs: Cancel rapid climb or high-speed dash tasks.",
                "• Thermal Monitoring: Commit to diversion airfield if cylinder EGT spread exceeds 45°C.",
                "• Flight Route: Maintain flight within 30 NM radius of suitable recovery strip."
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
            tactical_actions = [
                "• Dual-Lane Ignition Compromised: Engine redundancy depleted; no over-water or hostile penetration.",
                "• Vibration Avoidance: Keep engine speed within 4,400 - 4,800 RPM to avoid airframe harmonic excitation.",
                "• Direct Recovery Vector: Plan straight-in landing profile to minimize low-power throttle transients.",
                "• Mission Clearance Revoked: Return to home base under precautionary caution rules."
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
            tactical_actions = [
                "• Structural Fatigue Hazard: Limit airspeed and RPM to minimize gearbox / propeller resonance.",
                "• Mission Termination: Abort reconnaissance mission immediately; proceed to nearest recovery base.",
                "• Real-time Tracking: Continuous vibration telemetry monitoring; declare emergency if vib > 4.0 mm/s.",
                "• Aerodynamic Cushion: Maintain safe altitude above minimum terrain clearance along route."
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
            tactical_actions = [
                "• Thrust Margin Deficit: Recalculate climb capability and go-around margins.",
                "• Low-Altitude Cruise: Settle at best-range airspeed (75 KIAS) with conservative throttle setting.",
                "• Fuel Consumption Allowance: Budget 12% higher specific fuel consumption due to volumetric loss.",
                "• Mission Revision: Downgrade from primary mission profile to direct return or low-workload loiter."
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
            tactical_actions = [
                "• Analytic Redundancy Verified: Digital Twin confirms thermodynamic core integrity; no physical overheat.",
                "• Mission Approval: Full mission envelope cleared; continue flight on remaining valid sensors.",
                "• Telemetry Flag: Invalidate corrupted sensor channel in GCS display to avoid pilot distraction.",
                "• Post-Flight Work: Schedule sensor replacement upon routine post-mission turnaround."
            ]

        elif fault_code == "F99" or is_anomaly:  # Multi-parameter anomaly or unclassified anomaly
            urgency = severity if severity in ("CRITICAL", "WARNING", "CAUTION") else "WARNING"
            pilot_actions = [
                "1. Reduce throttle demand to 65% cruise setting to alleviate coupled thermodynamic stress.",
                "2. Cross-check analog flight instruments against digital twin residual predictions.",
                "3. Maintain safe glide altitude; avoid steep bank angles or rapid throttle adjustments.",
                "4. Establish communication with Mission Control; prepare for precautionary RTB if divergence widens."
            ]
            maintenance_actions = [
                "• Download full 10 Hz high-rate telemetry flight recorder and EKF observer logs.",
                "• Perform comprehensive multi-point ground engine run-up per Rotax Maintenance Manual Section 05-50.",
                "• Inspect electrical grounding harness, ECU CAN bus termination, and sensor terminal shielding.",
                "• Conduct differential compression check, spark plug check, and oil filter cut examination."
            ]
            tactical_actions = [
                "• Envelope Restriction: Restrict flight envelope to straight-and-level transit; suspend aggressive maneuvers.",
                "• Contingency Vector: Align flight path within safe gliding distance of alternate recovery airfields.",
                "• Telemetry Downlink: Maintain continuous real-time telemetry link for remote engineering monitoring.",
                "• Mission Decision: Abort to base if composite health index drops below 65% or divergence exceeds 3.5."
            ]

        else:  # Nominal healthy state
            urgency = "NOMINAL"
            pilot_actions = [
                "• Powertrain operating within nominal green band.",
                "• All physical variables tracking Digital Twin baseline within 1.2 standard deviations.",
                "• Full mission flight envelope approved (Takeoff, Climb, Cruise, Loiter)."
            ]
            maintenance_actions = [
                "• Routine post-flight pre-flight inspection at next 25-hour service interval."
            ]
            tactical_actions = [
                "• Mission GO: All propulsion subsystems operating with optimal thermodynamic margins.",
                "• Full operational flight envelope approved across all flight phases.",
                "• Closed-loop Digital Twin observer reports zero unmodeled physical divergence."
            ]

        advisory_title = f"{'ALERT - ANOMALY DETECTED: ' if is_anomaly else 'NOMINAL STATUS: '}{diagnosis['name'].upper()}"

        return {
            "title": advisory_title,
            "urgency": urgency,
            "fault_code": fault_code,
            "subsystem": diagnosis["subsystem"],
            "root_cause_summary": diagnosis["root_cause"],
            "pilot_instructions": pilot_actions,
            "maintenance_instructions": maintenance_actions,
            "tactical_recommendations": tactical_actions,
            "mission_decision": health_risk_output["recommendation"]
        }
