"""
AeroPulse Dashboard Main Entry Point (Dashboard.exe)
Houses the Digital Twin core, analytics pipeline, health & mission risk engine,
advisory generator, and mission control interface.
"""

import sys
import os
import threading
import time
import argparse
import webbrowser
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Set

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from common.constants import DEFAULT_WS_URI
from common.telemetry_schema import TelemetryPacket, FlightEnvironment, SensorTelemetry
from dashboard.telemetry_client import TelemetryClient
from dashboard.digital_twin import DigitalTwin
from dashboard.analytics import AnalyticsEngine
from dashboard.health_risk import HealthRiskCalculator
from dashboard.advisory import AdvisoryGenerator

DASHBOARD_PORT = 8766


class DashboardServer:
    """
    Coordinates telemetry consumption, Digital Twin computation,
    and UI WebSocket streaming at 10 Hz.
    """

    def __init__(self, simulator_uri: str = DEFAULT_WS_URI, port: int = DASHBOARD_PORT):
        self.port = port
        self.simulator_uri = simulator_uri

        # Core analytics and Digital Twin instances
        self.digital_twin = DigitalTwin()
        self.analytics = AnalyticsEngine()
        self.health_risk = HealthRiskCalculator()
        self.advisory_gen = AdvisoryGenerator()

        # Telemetry ingestion client
        self.telemetry_client = TelemetryClient(
            uri=self.simulator_uri,
            on_packet_callback=self.handle_incoming_telemetry
        )

        # Dashboard UI WebSocket subscribers
        self.ui_subscribers: Set[WebSocket] = set()
        self.latest_dashboard_frame: Optional[dict] = None
        self.last_process_time = time.time()
        self.heartbeat_task: Optional[asyncio.Task] = None

        # Build Starlette App
        @asynccontextmanager
        async def lifespan(app):
            # Startup
            self.telemetry_client.start()
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            yield
            # Shutdown
            self.telemetry_client.stop()
            if self.heartbeat_task:
                self.heartbeat_task.cancel()

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            ui_dir = Path(sys._MEIPASS) / "dashboard" / "ui"
        else:
            ui_dir = Path(__file__).parent / "ui"
        routes = [
            WebSocketRoute("/ws/digital_twin", self.ws_digital_twin_endpoint),
            Route("/api/status", self.http_status_endpoint, methods=["GET"]),
            Mount("/", app=StaticFiles(directory=str(ui_dir), html=True), name="ui"),
        ]
        self.app = Starlette(routes=routes, lifespan=lifespan)

    async def handle_incoming_telemetry(self, packet: TelemetryPacket):
        """
        Closed-loop execution:
        Telemetry Packet -> Digital Twin -> Residuals -> Analytics -> Health/Risk -> Advisory -> UI
        """
        self.last_process_time = time.time()

        # 1. Digital Twin expected behavior & EKF state estimation
        dt_output = self.digital_twin.update(packet)

        # 2. Analytics (residual evaluation & fault attribution)
        analytics_output = self.analytics.evaluate_residuals(dt_output)

        # 3. Health & Mission Risk Assessment
        health_risk_output = self.health_risk.calculate_health_and_risk(dt_output, analytics_output)

        # 4. Operational Advisory Generation
        advisory_output = self.advisory_gen.generate_advisory(analytics_output, health_risk_output, dt_output)

        # 5. Assemble unified dashboard payload
        frame = {
            "observed": dt_output["observed"],
            "expected": dt_output["expected"],
            "residuals": dt_output["residuals"],
            "degradation": dt_output["estimated_degradation"],
            "analytics": analytics_output,
            "health_risk": health_risk_output,
            "advisory": advisory_output,
            "flight_env": packet.flight_env.model_dump(),
            "stats": {
                "packets": self.telemetry_client.packets_received,
                "latency_ms": round(self.telemetry_client.latency_ms, 1),
                "connected": self.telemetry_client.is_connected,
                "packet_loss": self.telemetry_client.packets_dropped
            }
        }
        self.latest_dashboard_frame = frame

        # Distribute to all open Dashboard UI windows
        dead_sockets = set()
        for ws in self.ui_subscribers:
            try:
                await ws.send_json(frame)
            except Exception:
                dead_sockets.add(ws)
        self.ui_subscribers.difference_update(dead_sockets)

    async def _heartbeat_loop(self):
        """Fallback nominal loop if Simulator is temporarily offline"""
        while True:
            await asyncio.sleep(0.5)
            # If no packet received in the last 2 seconds, send standby frame
            if time.time() - self.last_process_time > 1.5:
                mock_packet = TelemetryPacket()
                dt_output = self.digital_twin.update(mock_packet)
                analytics_output = self.analytics.evaluate_residuals(dt_output)
                health_risk_output = self.health_risk.calculate_health_and_risk(dt_output, analytics_output)
                advisory_output = self.advisory_gen.generate_advisory(analytics_output, health_risk_output, dt_output)

                standby_frame = {
                    "observed": dt_output["observed"],
                    "expected": dt_output["expected"],
                    "residuals": dt_output["residuals"],
                    "degradation": dt_output["estimated_degradation"],
                    "analytics": analytics_output,
                    "health_risk": health_risk_output,
                    "advisory": advisory_output,
                    "flight_env": mock_packet.flight_env.model_dump(),
                    "stats": {
                        "packets": self.telemetry_client.packets_received,
                        "latency_ms": 0.0,
                        "connected": False,
                        "packet_loss": 0
                    }
                }
                dead_sockets = set()
                for ws in self.ui_subscribers:
                    try:
                        await ws.send_json(standby_frame)
                    except Exception:
                        dead_sockets.add(ws)
                self.ui_subscribers.difference_update(dead_sockets)

    async def ws_digital_twin_endpoint(self, websocket: WebSocket):
        """Dashboard UI streaming endpoint"""
        await websocket.accept()
        self.ui_subscribers.add(websocket)
        try:
            # Send latest frame immediately if available
            if self.latest_dashboard_frame:
                await websocket.send_json(self.latest_dashboard_frame)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            self.ui_subscribers.discard(websocket)

    async def http_status_endpoint(self, request):
        """Status API query"""
        return JSONResponse({
            "status": "ONLINE",
            "telemetry_client": self.telemetry_client.get_stats(),
            "latest_health": self.health_risk.smooth_health if hasattr(self.health_risk, 'smooth_health') else 100.0,
            "connected_uis": len(self.ui_subscribers)
        })


dashboard_server = None
uvicorn_server = None


def run_dashboard_server(port: int, simulator_uri: str):
    global dashboard_server, uvicorn_server
    dashboard_server = DashboardServer(simulator_uri=simulator_uri, port=port)
    config = uvicorn.Config(
        app=dashboard_server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False
    )
    uvicorn_server = uvicorn.Server(config)
    uvicorn_server.run()


def main():
    parser = argparse.ArgumentParser(description="SIH Digital Twin & Health Monitoring Dashboard")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Dashboard port")
    parser.add_argument("--simulator-uri", type=str, default=DEFAULT_WS_URI, help="Simulator telemetry URI")
    parser.add_argument("--headless", action="store_true", help="Run in headless server mode")
    parser.add_argument("--browser", action="store_true", help="Open in default browser instead of native window")
    args = parser.parse_args()

    print("==================================================================")
    print("  SIH — DIGITAL TWIN & HEALTH MONITORING SYSTEM")
    print(f"  Ingesting Telemetry from: {args.simulator_uri}")
    print(f"  Mission Control Console: http://127.0.0.1:{args.port}")
    print("==================================================================")

    # Start Dashboard backend in daemon thread
    server_thread = threading.Thread(
        target=run_dashboard_server,
        args=(args.port, args.simulator_uri),
        daemon=True
    )
    server_thread.start()

    time.sleep(1.2)
    url = f"http://127.0.0.1:{args.port}"

    if args.headless:
        print("[Dashboard] Running in headless mode. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Dashboard] Shutting down...")
            if uvicorn_server:
                uvicorn_server.should_exit = True
            sys.exit(0)

    # Open native desktop window via webview
    has_webview = False
    if not args.browser:
        try:
            import webview
            has_webview = True
        except ImportError:
            has_webview = False

    if has_webview and not args.browser:
        try:
            print("[Dashboard] Opening native desktop mission control console...")
            window = webview.create_window(
                title="SIH26054 — DIGITAL TWIN",
                url=url,
                width=1320,
                height=880,
                resizable=True,
                min_size=(1000, 700)
            )
            webview.start()
        except Exception as e:
            print(f"[Dashboard] Native window failed ({e}), opening in browser.")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print(f"[Dashboard] Opening console in web browser: {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[Dashboard] Exiting...")
    if uvicorn_server:
        uvicorn_server.should_exit = True


if __name__ == "__main__":
    main()
