"""
AeroPulse Dashboard Telemetry Ingestion Client
Maintains a resilient real-time WebSocket connection to the Simulator (or UAV test rig),
performs data validation, monitors packet loss, and feeds the Digital Twin pipeline.
"""

import asyncio
import json
import time
from typing import Optional, Callable, Dict, Any
import websockets

from common.constants import DEFAULT_WS_URI
from common.telemetry_schema import TelemetryPacket


class TelemetryClient:
    """
    Asynchronous telemetry receiver with automatic exponential-backoff reconnect,
    packet sequence tracking, and jitter estimation.
    """

    def __init__(self, uri: str = DEFAULT_WS_URI, on_packet_callback: Optional[Callable[[TelemetryPacket], None]] = None):
        self.uri = uri
        self.on_packet_callback = on_packet_callback

        self.is_connected: bool = False
        self.is_running: bool = False
        self.last_packet: Optional[TelemetryPacket] = None
        self.last_packet_time: float = 0.0

        # Quality & Diagnostic Statistics
        self.packets_received: int = 0
        self.packets_dropped: int = 0
        self.last_sequence: int = -1
        self.latency_ms: float = 0.0
        self.reconnect_count: int = 0
        self.task: Optional[asyncio.Task] = None

    def start(self):
        """Start the ingestion loop as an asyncio background task"""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._client_loop())

    def stop(self):
        """Stop the ingestion loop"""
        self.is_running = False
        if self.task:
            self.task.cancel()

    async def _client_loop(self):
        """Continuously maintain WebSocket connection with exponential backoff"""
        backoff = 1.0
        while self.is_running:
            try:
                async with websockets.connect(self.uri, ping_interval=5, ping_timeout=5) as ws:
                    self.is_connected = True
                    backoff = 1.0
                    # Send an initial handshake text
                    await ws.send(json.dumps({"client": "Dashboard.exe", "version": "1.0.0"}))

                    while self.is_running:
                        msg_str = await ws.recv()
                        t_recv = time.time()
                        try:
                            packet = TelemetryPacket.from_json(msg_str)
                            self.packets_received += 1
                            self.last_packet_time = t_recv
                            self.latency_ms = max(0.0, (t_recv - packet.timestamp) * 1000.0)

                            # Check for dropped packet sequence numbers
                            if self.last_sequence >= 0:
                                expected_seq = self.last_sequence + 1
                                if packet.packet_id > expected_seq:
                                    self.packets_dropped += (packet.packet_id - expected_seq)
                            self.last_sequence = packet.packet_id

                            self.last_packet = packet

                            # Fire processing callback into Digital Twin
                            if self.on_packet_callback:
                                if asyncio.iscoroutinefunction(self.on_packet_callback):
                                    await self.on_packet_callback(packet)
                                else:
                                    self.on_packet_callback(packet)

                        except Exception as parse_err:
                            pass

            except (websockets.ConnectionClosed, OSError, asyncio.CancelledError) as e:
                self.is_connected = False
                self.reconnect_count += 1
                if not self.is_running:
                    break
                await asyncio.sleep(backoff)
                backoff = min(4.0, backoff * 1.5)

    def get_stats(self) -> Dict[str, Any]:
        """Return communication quality metrics"""
        return {
            "connected": self.is_connected,
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
            "latency_ms": round(self.latency_ms, 1),
            "reconnect_count": self.reconnect_count,
            "packet_loss_pct": round(
                (self.packets_dropped / max(1, self.packets_received + self.packets_dropped)) * 100.0, 2
            ),
        }
