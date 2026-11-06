"""
app.py – GUI entry point for the Lab Control System.

Replaces the terminal-based main.py.

Usage
-----
    python app.py

Dependencies
------------
    pip install PyQt6 pyqtgraph
"""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui     import QFont

import gui.style as style

from core.motor        import Motor
from core.oscilloscope import Oscilloscope
from core.power_meter  import PowerMeter
from utils.config      import (
    MOTOR_1_ADDRESS, MOTOR_2_ADDRESS, MOTOR_3_ADDRESS,
    OSCILLOSCOPE_ADDRESS,
)
from gui.main_window import MainWindow


#  Axis mapping 

AXES = {
    "z": MOTOR_1_ADDRESS,
    "x": MOTOR_2_ADDRESS,
    "y": MOTOR_3_ADDRESS,
}


#  Instrument startup 

def connect_motors() -> dict:
    """
    Attempt to connect all motors. Returns only the ones that succeeded.
    Failures are printed but do not crash the app.
    """
    motors = {}
    for axis, address in AXES.items():
        m = Motor(axis=axis, address=address)
        try:
            m.connect()
            motors[axis] = m
            print(f"  [Motor {axis.upper()}]  Connected on {address}")
        except Exception as exc:
            print(f"  [Motor {axis.upper()}]  Could not connect ({address}): {exc}")
    return motors


def build_scope() -> Oscilloscope:
    """
    Return an Oscilloscope instance.
    Connection is attempted but failure is non-fatal - the panel
    will show "Disconnected" and retry on first Acquire.
    """
    scope = Oscilloscope(OSCILLOSCOPE_ADDRESS)
    try:
        scope.connect()
        print(f"  [Oscilloscope]  Connected")
    except Exception as exc:
        print(f"  [Oscilloscope]  Not connected at startup: {exc}")
    return scope


def build_power_meter() -> PowerMeter:
    """
    Return a PowerMeter instance (auto-detects address).
    Connection failure is non-fatal.
    """
    pm = PowerMeter()   # address=None -> auto-detect
    try:
        pm.connect()
        print(f"  [Power Meter]   Connected")
    except Exception as exc:
        print(f"  [Power Meter]   Not connected at startup: {exc}")
    return pm


#  Main 

def main():
    print("\n" + "=" * 50)
    print("  Lab Control System - Starting up")
    print("=" * 50)

    motors = connect_motors()
    scope  = build_scope()
    pm     = build_power_meter()

    print("=" * 50 + "\n")

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    style.apply(app)

    window = MainWindow(motors=motors, scope=scope, pm=pm)
    window.show()

    exit_code = app.exec()

    #  Cleanup 
    print("\nShutting down ...")
    for axis, motor in motors.items():
        try:
            motor.disconnect()
        except Exception:
            pass
    try:
        scope.disconnect()
    except Exception:
        pass
    try:
        pm.disconnect()
    except Exception:
        pass
    print("Goodbye.\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
