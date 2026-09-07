"""
AeroPulse Standalone Executable Packaging Script
Compiles Simulator.exe and Dashboard.exe using PyInstaller.
"""

import os
import sys
import subprocess
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_simulator():
    print("\n==================================================================")
    print("  BUILDING SIMULATOR.EXE                                          ")
    print("==================================================================")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Simulator",
        "--onefile",
        "--add-data", f"{os.path.join(PROJECT_ROOT, 'simulator', 'ui')};simulator/ui",
        "--hidden-import", "starlette",
        "--hidden-import", "starlette.routing",
        "--hidden-import", "starlette.staticfiles",
        "--hidden-import", "uvicorn",
        "--hidden-import", "websockets",
        "--hidden-import", "webview",
        "--hidden-import", "scipy",
        "--hidden-import", "numpy",
        "--hidden-import", "pydantic",
        os.path.join(PROJECT_ROOT, "simulator", "main.py")
    ]
    print("Executing command:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)
    print("Simulator.exe built successfully!")


def build_dashboard():
    print("\n==================================================================")
    print("  BUILDING DASHBOARD.EXE                                          ")
    print("==================================================================")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Dashboard",
        "--onefile",
        "--add-data", f"{os.path.join(PROJECT_ROOT, 'dashboard', 'ui')};dashboard/ui",
        "--hidden-import", "starlette",
        "--hidden-import", "starlette.routing",
        "--hidden-import", "starlette.staticfiles",
        "--hidden-import", "uvicorn",
        "--hidden-import", "websockets",
        "--hidden-import", "webview",
        "--hidden-import", "scipy",
        "--hidden-import", "numpy",
        "--hidden-import", "pydantic",
        "--hidden-import", "filterpy",
        "--hidden-import", "sklearn",
        os.path.join(PROJECT_ROOT, "dashboard", "main.py")
    ]
    print("Executing command:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)
    print("Dashboard.exe built successfully!")


if __name__ == "__main__":
    parser = argparse = __import__("argparse").ArgumentParser()
    parser.add_argument("--target", choices=["all", "simulator", "dashboard"], default="all")
    args = parser.parse_args()

    if args.target in ("all", "simulator"):
        build_simulator()
    if args.target in ("all", "dashboard"):
        build_dashboard()
