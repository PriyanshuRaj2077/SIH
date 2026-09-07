"""
AeroPulse Simulator Main Entry Point
Launches the background 10 Hz telemetry server and native desktop operator UI.
Can run as standalone Python script or packaged Simulator.exe.
"""

import sys
import os
import threading
import time
import argparse
import webbrowser

# Add project root to sys.path so modules can be imported directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from common.constants import DEFAULT_WS_HOST, DEFAULT_WS_PORT
from simulator.telemetry_server import TelemetryServer

server_instance = None
uvicorn_server = None


def run_server(host: str, port: int):
    """Run uvicorn ASGI server in background thread"""
    global server_instance, uvicorn_server
    server_instance = TelemetryServer(host=host, port=port)
    config = uvicorn.Config(
        app=server_instance.app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False
    )
    uvicorn_server = uvicorn.Server(config)
    uvicorn_server.run()


def main():
    parser = argparse.ArgumentParser(description="SIH26054 — Engine & Mission Telemetry Simulator")
    parser.add_argument("--host", type=str, default=DEFAULT_WS_HOST, help="Server bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_WS_PORT, help="Server bind port")
    parser.add_argument("--headless", action="store_true", help="Run in headless server mode (no GUI window)")
    parser.add_argument("--browser", action="store_true", help="Open in default web browser instead of webview")
    args = parser.parse_args()

    print("==================================================================")
    print("  SIH26054 — ENGINE & MISSION TELEMETRY SIMULATOR (SIMULATOR.EXE)")
    print(f"  Broadcasting at 10 Hz on ws://{args.host}:{args.port}/telemetry")
    print(f"  Operator Console: http://{args.host}:{args.port}")
    print("==================================================================")

    # Start uvicorn server in a dedicated background daemon thread
    server_thread = threading.Thread(target=run_server, args=(args.host, args.port), daemon=True)
    server_thread.start()

    # Wait for server port to bind
    time.sleep(1.2)
    url = f"http://{args.host}:{args.port}"

    if args.headless:
        print("[Simulator] Running in headless mode. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Simulator] Shutting down...")
            if uvicorn_server:
                uvicorn_server.should_exit = True
            sys.exit(0)

    # If webview is installed and not forced to browser, open native desktop window
    has_webview = False
    if not args.browser:
        try:
            import webview
            has_webview = True
        except ImportError:
            has_webview = False

    if has_webview and not args.browser:
        try:
            print("[Simulator] Opening native desktop operator console...")
            window = webview.create_window(
                title="SIH26054 — ENGINE & MISSION TELEMETRY SIMULATOR",
                url=url,
                width=1180,
                height=840,
                resizable=True,
                min_size=(900, 650)
            )
            webview.start()
        except Exception as e:
            print(f"[Simulator] Native window failed ({e}), falling back to browser.")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print(f"[Simulator] Opening operator console in web browser: {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[Simulator] Exiting...")
    if uvicorn_server:
        uvicorn_server.should_exit = True


if __name__ == "__main__":
    main()
