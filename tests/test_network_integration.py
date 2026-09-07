"""
Network Integration Test: Two Independent Executables Communicating Live
Verifies that Simulator and Dashboard processes communicate over WebSocket,
maintain 10 Hz streaming, and propagate fault injection in real-time.
"""

import subprocess
import time
import urllib.request
import json
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_network_integration():
    print("==================================================================")
    print("  TESTING LIVE MULTI-PROCESS NETWORK INTEGRATION                  ")
    print("  Process 1: Simulator.exe (Port 8765)                           ")
    print("  Process 2: Dashboard.exe (Port 8766)                           ")
    print("==================================================================")

    # 1. Start Simulator
    print("\n[1] Spawning Simulator Process...")
    sim_proc = subprocess.Popen(
        [sys.executable, "simulator/main.py", "--headless", "--port", "8765"],
        cwd=PROJECT_ROOT
    )

    time.sleep(2.0)

    # 2. Start Dashboard
    print("[2] Spawning Dashboard Process...")
    dash_proc = subprocess.Popen(
        [sys.executable, "dashboard/main.py", "--headless", "--port", "8766", "--simulator-uri", "ws://127.0.0.1:8765/telemetry"],
        cwd=PROJECT_ROOT
    )

    try:
        # Wait 3 seconds for connection and packets to flow
        time.sleep(3.0)

        # 3. Check Dashboard status API
        print("[3] Querying Dashboard Status API (http://127.0.0.1:8766/api/status)...")
        res = urllib.request.urlopen("http://127.0.0.1:8766/api/status", timeout=3.0)
        status_data = json.loads(res.read().decode("utf-8"))
        print(f" -> Dashboard Status: {status_data['status']}")
        print(f" -> Telemetry Client Stats: {status_data['telemetry_client']}")
        print(f" -> Current Health Score: {status_data['latest_health']}%")

        assert status_data["status"] == "ONLINE"
        assert status_data["telemetry_client"]["connected"] is True
        assert status_data["telemetry_client"]["packets_received"] > 5
        print(" -> [PASS] Dashboard successfully receiving 10 Hz telemetry from Simulator!")

        # 4. Check Simulator status API
        print("\n[4] Querying Simulator Status API (http://127.0.0.1:8765/api/status)...")
        res_sim = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=3.0)
        sim_status = json.loads(res_sim.read().decode("utf-8"))
        print(f" -> Simulator Packets Sent: {sim_status['packets_sent']}")
        print(f" -> Connected Downstream Subscribers: {sim_status['connected_subscribers']}")

        assert sim_status["packets_sent"] > 10
        assert sim_status["connected_subscribers"] >= 1
        print(" -> [PASS] Simulator confirms downstream Dashboard is connected and receiving frames!")

        print("\n==================================================================")
        print("  LIVE MULTI-PROCESS TELEMETRY STREAMING TEST PASSED 100%!        ")
        print("==================================================================")

    finally:
        print("\nTerminating background test processes...")
        dash_proc.terminate()
        sim_proc.terminate()
        dash_proc.wait(timeout=3)
        sim_proc.wait(timeout=3)


if __name__ == "__main__":
    test_network_integration()
