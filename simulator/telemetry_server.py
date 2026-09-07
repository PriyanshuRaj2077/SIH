"""
AeroPulse Simulator Telemetry Server
Provides real-time 10 Hz telemetry streaming via WebSocket,
operator control bi-directional messaging, and UDP broadcast capability.
"""

import asyncio
import json
import socket
import time
from typing import Set, Dict, Any
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from common.constants import (
    DEFAULT_WS_HOST, DEFAULT_WS_PORT, DEFAULT_UDP_PORT,
    TELEMETRY_DT_SECONDS
)
from common.telemetry_schema import (
    TelemetryPacket, FlightEnvironment, SensorTelemetry,
    VibrationTelemetry, SensorStatusFlags
)
from simulator.physics_engine import EnginePhysicsSimulator
from simulator.fault_injector import FaultInjector


class TelemetryServer:
    """
    Manages the physics simulation loop and broadcasts telemetry packets
    to all connected downstream consumers (Dashboard, test bench, recorders).
    """

    def __init__(self, host: str = DEFAULT_WS_HOST, port: int = DEFAULT_WS_PORT):
        self.host = host
        self.port = port
        self.fault_injector = FaultInjector()
        self.simulator = EnginePhysicsSimulator(fault_injector=self.fault_injector)

        # Operator controls state
        self.controls: Dict[str, Any] = {
            "altitude_ft": 5000.0,
            "ambient_temp_c": 15.0,
            "wind_speed_mps": 6.0,
            "throttle_pct": 72.0,
            "engine_load": 1.0,
            "flight_phase": "cruise",
            "simulation_running": True,
        }

        # Subscribed WebSocket clients
        self.telemetry_clients: Set[WebSocket] = set()
        self.control_clients: Set[WebSocket] = set()

        # Telemetry transmission statistics
        self.packet_sequence: int = 0
        self.start_time: float = time.time()
        self.packets_sent: int = 0
        self.loop_task: Optional[asyncio.Task] = None

        # UDP broadcast socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_enabled = True

        # Starlette Application with modern lifespan handler
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app):
            await self.on_startup()
            yield
            await self.on_shutdown()

        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            ui_dir = Path(sys._MEIPASS) / "simulator" / "ui"
        else:
            ui_dir = Path(__file__).parent / "ui"
        routes = [
            WebSocketRoute("/telemetry", self.ws_telemetry_endpoint),
            WebSocketRoute("/control", self.ws_control_endpoint),
            Route("/api/status", self.http_status_endpoint, methods=["GET"]),
            Route("/api/faults", self.http_faults_endpoint, methods=["GET"]),
            Mount("/", app=StaticFiles(directory=str(ui_dir), html=True), name="ui"),
        ]
        self.app = Starlette(routes=routes, lifespan=lifespan)

    async def on_startup(self):
        """Start the background 10 Hz simulation loop"""
        self.loop_task = asyncio.create_task(self._simulation_loop())

    async def on_shutdown(self):
        """Cleanly cancel the simulation loop"""
        if self.loop_task:
            self.loop_task.cancel()
        try:
            self.udp_sock.close()
        except Exception:
            pass

    async def http_status_endpoint(self, request):
        """HTTP diagnostic endpoint"""
        return JSONResponse({
            "status": "ONLINE",
            "packets_sent": self.packets_sent,
            "connected_subscribers": len(self.telemetry_clients),
            "engine_hours": round(self.simulator.engine_hours, 3),
            "controls": self.controls,
            "active_faults": self.fault_injector.get_active_faults()
        })

    async def http_faults_endpoint(self, request):
        """List all available faults and their current states"""
        return JSONResponse({
            "available_faults": self.fault_injector.AVAILABLE_FAULTS,
            "active_faults": self.fault_injector.get_active_faults()
        })

    async def ws_telemetry_endpoint(self, websocket: WebSocket):
        """Downstream client subscription for 10 Hz telemetry frames"""
        await websocket.accept()
        self.telemetry_clients.add(websocket)
        try:
            while True:
                # Keep socket alive; clients can also send heartbeats or queries
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            self.telemetry_clients.discard(websocket)

    async def ws_control_endpoint(self, websocket: WebSocket):
        """Operator UI communication: receives control tweaks, sends state"""
        await websocket.accept()
        self.control_clients.add(websocket)
        try:
            # Send initial state immediately
            await websocket.send_json({
                "type": "state_sync",
                "controls": self.controls,
                "active_faults": self.fault_injector.get_active_faults()
            })

            while True:
                data_str = await websocket.receive_text()
                try:
                    msg = json.loads(data_str)
                    action = msg.get("action")

                    if action == "set_controls":
                        new_vals = msg.get("controls", {})
                        for k, v in new_vals.items():
                            if k in self.controls:
                                self.controls[k] = v

                    elif action == "set_fault":
                        fault_type = msg.get("fault_type")
                        severity = float(msg.get("severity", 0.5))
                        target_cylinder = msg.get("target_cylinder", 3)
                        self.fault_injector.set_fault(fault_type, severity, target_cylinder)

                    elif action == "clear_fault":
                        fault_type = msg.get("fault_type")
                        self.fault_injector.clear_fault(fault_type)

                    elif action == "clear_all_faults":
                        self.fault_injector.clear_all_faults()

                    elif action == "toggle_simulation":
                        self.controls["simulation_running"] = not self.controls["simulation_running"]

                    # Broadcast state update to all operator control panels
                    await self._broadcast_control_state()

                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

        except WebSocketDisconnect:
            pass
        finally:
            self.control_clients.discard(websocket)

    async def _broadcast_control_state(self):
        """Send updated controls and fault status to all control clients"""
        state_msg = {
            "type": "state_sync",
            "controls": self.controls,
            "active_faults": self.fault_injector.get_active_faults()
        }
        for ws in list(self.control_clients):
            try:
                await ws.send_json(state_msg)
            except Exception:
                self.control_clients.discard(ws)

    async def _simulation_loop(self):
        """High-precision 10 Hz telemetry calculation and distribution loop"""
        dt = TELEMETRY_DT_SECONDS
        while True:
            t_start = time.perf_counter()

            if self.controls.get("simulation_running", True):
                # Step physics simulation forward by dt
                frame_dict = self.simulator.step(
                    dt=dt,
                    altitude_ft=float(self.controls["altitude_ft"]),
                    ambient_temp_c=float(self.controls["ambient_temp_c"]),
                    wind_speed_mps=float(self.controls["wind_speed_mps"]),
                    throttle_pct=float(self.controls["throttle_pct"]),
                    engine_load=float(self.controls["engine_load"]),
                    flight_phase=str(self.controls["flight_phase"])
                )

                self.packet_sequence += 1
                self.packets_sent += 1

                # Construct standardized TelemetryPacket
                packet = TelemetryPacket(
                    packet_id=self.packet_sequence,
                    timestamp=time.time(),
                    engine_hours=frame_dict["engine_hours"],
                    flight_env=FlightEnvironment(
                        altitude_ft=float(self.controls["altitude_ft"]),
                        ambient_temp_c=float(self.controls["ambient_temp_c"]),
                        ambient_pressure_kpa=frame_dict["ambient_pressure_kpa"],
                        wind_speed_mps=float(self.controls["wind_speed_mps"]),
                        throttle_pct=float(self.controls["throttle_pct"]),
                        engine_load=float(self.controls["engine_load"]),
                        flight_phase=str(self.controls["flight_phase"])
                    ),
                    telemetry=SensorTelemetry(
                        rpm=frame_dict["rpm"],
                        cht=frame_dict["cht"],
                        egt=frame_dict["egt"],
                        oil_temp_c=frame_dict["oil_temp_c"],
                        oil_pressure_bar=frame_dict["oil_pressure_bar"],
                        coolant_temp_c=frame_dict["coolant_temp_c"],
                        map_kpa=frame_dict["map_kpa"],
                        fuel_flow_lph=frame_dict["fuel_flow_lph"],
                        vibration=VibrationTelemetry(
                            x=frame_dict["vibration"]["x"],
                            y=frame_dict["vibration"]["y"],
                            z=frame_dict["vibration"]["z"],
                            rms=frame_dict["vibration"]["rms"]
                        ),
                        bus_voltage=frame_dict["bus_voltage"]
                    ),
                    sensor_status=SensorStatusFlags()
                )

                json_payload = packet.to_json()

                # 1. Distribute to all WebSocket telemetry subscribers
                dead_sockets = set()
                for ws in self.telemetry_clients:
                    try:
                        await ws.send_text(json_payload)
                    except Exception:
                        dead_sockets.add(ws)
                self.telemetry_clients.difference_update(dead_sockets)

                # 2. Distribute to local control UI (at 10 Hz) for live gauge rendering
                dead_controls = set()
                for ws in self.control_clients:
                    try:
                        await ws.send_json({
                            "type": "telemetry_frame",
                            "packet": packet.model_dump(),
                            "stats": {
                                "packets_sent": self.packets_sent,
                                "clients_connected": len(self.telemetry_clients),
                                "fps": 10.0
                            }
                        })
                    except Exception:
                        dead_controls.add(ws)
                self.control_clients.difference_update(dead_controls)

                # 3. Optional UDP broadcast to 127.0.0.1:9000
                if self.udp_enabled:
                    try:
                        self.udp_sock.sendto(json_payload.encode("utf-8"), ("127.0.0.1", DEFAULT_UDP_PORT))
                    except Exception:
                        pass

            # Maintain exact 10 Hz timing
            elapsed = time.perf_counter() - t_start
            sleep_duration = max(0.001, dt - elapsed)
            await asyncio.sleep(sleep_duration)
