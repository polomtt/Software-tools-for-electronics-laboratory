"""
main.py – Interactive test entry point for the lab control system.

Currently supported components:
  - Motors      (Opto Sigma SRC-101)
  - Oscilloscope (Tektronix MDO3102)
  - Power Meter  (Thorlabs PM100D)

Usage
-----
    python main.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.motor        import Motor
from core.oscilloscope import Oscilloscope
from core.power_meter  import PowerMeter
from utils.config import (
    MOTOR_1_ADDRESS, MOTOR_2_ADDRESS, MOTOR_3_ADDRESS,
    OSCILLOSCOPE_ADDRESS, STEP_DELAY,
)


# -----------------------------------------------------------------
# Axis mapping  (label -> VISA address from config.py)
# -----------------------------------------------------------------

AXES = {
    "z": MOTOR_1_ADDRESS,
    "x": MOTOR_2_ADDRESS,
    "y": MOTOR_3_ADDRESS,
}

DEFAULT_WAVEFORM_DIR = "data/waveforms"
DEFAULT_POWER_DIR    = "data/power"

DONE_FLAGS = {"done", "d"}
QUIT_FLAGS  = {"quit", "q", "exit"}
VALID_AXES  = set(AXES.keys())


# -----------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------

def print_banner():
    print("\n" + "=" * 55)
    print("  Lab Control System")
    print("=" * 55)
    print("  [1] Motor control")
    print("  [2] Oscilloscope  – read waveform")
    print("  [3] Power meter   – measure power")
    print("  [Q] Quit")
    print("=" * 55 + "\n")


def ask_int(prompt, allow_zero=False, allow_negative=False):
    """Generic validated integer input."""
    while True:
        raw = input(prompt).strip()
        if raw.lower() in QUIT_FLAGS:
            raise SystemExit
        if raw.lower() in DONE_FLAGS:
            return None
        try:
            value = int(raw)
            if not allow_zero and value == 0:
                raise ValueError
            if not allow_negative and value < 0:
                raise ValueError
            return value
        except ValueError:
            hint = "non-zero " if not allow_zero else ""
            hint += "positive " if not allow_negative else ""
            print(f"  [!] Enter a {hint}integer.")


def ask_float(prompt, positive_only=True):
    """Generic validated float input."""
    while True:
        raw = input(prompt).strip()
        if raw.lower() in QUIT_FLAGS:
            raise SystemExit
        try:
            value = float(raw)
            if positive_only and value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("  [!] Enter a valid positive number.")


def ask_direction(prompt):
    """Ask for + or - direction. Returns +1 or -1."""
    while True:
        raw = input(prompt).strip()
        if raw.lower() in QUIT_FLAGS:
            raise SystemExit
        if raw in ("+", "+1", "1", "pos", "forward"):
            return +1
        if raw in ("-", "-1", "neg", "backward"):
            return -1
        print("  [!] Enter + (forward) or - (backward).")


def ask_output_dir(default_dir):
    """Ask where to save output files. Returns the chosen directory path."""
    print(f"\n  Where do you want to save the file(s)?")
    print(f"  [1] Default folder  ({default_dir}/)")
    print( "  [2] Create a new folder")
    while True:
        raw = input("\n  Choice [1 / 2]: ").strip()
        if raw.lower() in QUIT_FLAGS:
            raise SystemExit
        if raw == "1":
            return default_dir
        if raw == "2":
            folder = input("  New folder name: ").strip()
            if not folder:
                print("  [!] Folder name cannot be empty.")
                continue
            return folder
        print("  [!] Enter 1 or 2.")


# -----------------------------------------------------------------
# Top-level menu
# -----------------------------------------------------------------

def select_top_menu():
    """Returns '1', '2', '3', or raises SystemExit."""
    while True:
        raw = input("  Select [1 / 2 / 3]  (or 'quit'): ").strip().lower()
        if raw in QUIT_FLAGS or raw == "q":
            raise SystemExit
        if raw in ("1", "2", "3"):
            return raw
        print("  [!] Enter 1, 2, or 3.")


# =================================================================
# OSCILLOSCOPE SECTION
# =================================================================

def ask_channel():
    """Ask which channel(s) to read. Returns 1, 2, or 'both'."""
    print("\n  Which channel(s) do you want to read?")
    print("  [1] CH1 only")
    print("  [2] CH2 only")
    print("  [3] Both channels")
    while True:
        raw = input("\n  Channel [1 / 2 / 3]: ").strip()
        if raw.lower() in QUIT_FLAGS:
            raise SystemExit
        if raw == "1": return 1
        if raw == "2": return 2
        if raw == "3": return "both"
        print("  [!] Enter 1, 2, or 3.")


def resolve_channel_dirs(base_dir: str, channel) -> dict:
    if channel == "both":
        return {
            1: os.path.join(base_dir, "CH1"),
            2: os.path.join(base_dir, "CH2"),
        }
    return {channel: os.path.join(base_dir, f"CH{channel}")}


def run_oscilloscope():
    """Full oscilloscope workflow: connect → choose channel → choose folder → save."""
    print("\n" + "-" * 55)
    print("  Oscilloscope – Waveform Acquisition")
    print("-" * 55)

    channel  = ask_channel()
    base_dir = ask_output_dir(DEFAULT_WAVEFORM_DIR)
    chan_dirs = resolve_channel_dirs(base_dir, channel)

    print("\n  Base filename (leave blank for auto timestamp):")
    raw_name = input("  > ").strip()
    filename = raw_name if raw_name else None

    scope = Oscilloscope(OSCILLOSCOPE_ADDRESS)
    try:
        scope.connect()
    except Exception as exc:
        print(f"\n  [!] Could not connect to oscilloscope: {exc}")
        print("       Check the address in config.py and the USB cable.")
        return

    try:
        if channel == "both":
            scope.save_waveform(channel=1, output_dir=chan_dirs[1], filename=filename)
            scope.save_waveform(channel=2, output_dir=chan_dirs[2], filename=filename)
        else:
            scope.save_waveform(channel=channel,
                                output_dir=chan_dirs[channel], filename=filename)
        print("\n  [OK] Acquisition complete.")
        print(f"  Files saved under: {base_dir}/")
    except Exception as exc:
        print(f"\n  [ERR] Acquisition failed: {exc}")
    finally:
        scope.disconnect()


# =================================================================
# POWER METER SECTION
# =================================================================

def run_power_meter():
    """Full power meter workflow: connect → configure → measure → save."""
    print("\n" + "-" * 55)
    print("  Power Meter – Thorlabs PM100D")
    print("-" * 55)

    # Parameters
    wavelength = ask_float("  Calibration wavelength [nm]: ")
    n_samples  = ask_int("  Number of samples      (e.g. 10): ")
    if n_samples is None:
        return
    averaging  = ask_int("  Hardware averaging count (e.g. 5): ")
    if averaging is None:
        return

    # Output directory
    output_dir = ask_output_dir(DEFAULT_POWER_DIR)

    # Optional filename
    print("\n  Base filename (leave blank for auto timestamp):")
    raw_name = input("  > ").strip()
    filename = raw_name if raw_name else None

    # Connect and measure
    pm = PowerMeter()       # auto-detects by vendor ID
    try:
        pm.connect()
    except Exception as exc:
        print(f"\n  [!] Could not connect to power meter: {exc}")
        print("       Check the USB cable and try again.")
        return

    try:
        pm.set_auto_range(True)
        pm.save_power(
            n_samples     = n_samples,
            averaging     = averaging,
            wavelength_nm = wavelength,
            output_dir    = output_dir,
            filename      = filename,
        )
        print("\n  [OK] Measurement complete.")
    except Exception as exc:
        print(f"\n  [ERR] Measurement failed: {exc}")
    finally:
        pm.disconnect()


# =================================================================
# MOTOR SECTION  (unchanged)
# =================================================================

def select_mode():
    """Ask the user which input mode to use. Returns 'a' or 'b'."""
    print("\n  Select input mode:")
    print("  [A] Full control   – axis / pulses / speed for each move")
    print("  [B] Shared params  – pulses & speed once, then steps & direction per axis")
    while True:
        raw = input("\n  Mode [A / B]  (or 'quit'): ").strip().lower()
        if raw in QUIT_FLAGS:
            raise SystemExit
        if raw in ("a", "b"):
            return raw
        print("  [!] Enter A or B.")


def collect_moves_mode_a():
    moves = []
    print("\n  [Mode A] Enter axis / pulses / speed for each move.")
    print("  Type 'done' at any prompt to stop adding moves.\n")

    while True:
        while True:
            raw = input("  Axis [x / y / z]  (or 'done' / 'quit'): ").strip().lower()
            if raw in QUIT_FLAGS:  raise SystemExit
            if raw in DONE_FLAGS:  return moves
            if raw in VALID_AXES:  axis = raw; break
            print(f"  [!] Choose from: {', '.join(sorted(VALID_AXES)).upper()}")

        pulses = ask_int("  Pulses per step (positive integer): ")
        if pulses is None: return moves

        print("  Speed: positive = forward (+),  negative = backward (-)")
        speed = ask_int("  Speed in pulse/s (non-zero, e.g. +5000 or -3000): ",
                        allow_negative=True)
        if speed is None: return moves

        moves.append({"axis": axis, "pulses": pulses, "speed": speed})
        print(f"  [+] Queued: axis={axis.upper()}  pulses={pulses}  speed={speed:+d}\n")


def collect_moves_mode_b():
    print("\n  [Mode B] Set pulses and speed once, then configure each axis.\n")

    pulses = ask_int("  Pulses per step (positive integer): ")
    if pulses is None: return []

    abs_speed = ask_int("  Speed in pulse/s (positive, direction set per axis): ")
    if abs_speed is None: return []

    print(f"\n  Pulses={pulses}  Speed={abs_speed} pulse/s")
    print("  Now configure each axis. Type 'done' to stop.\n")

    moves = []
    while True:
        while True:
            raw = input("  Axis [x / y / z]  (or 'done' / 'quit'): ").strip().lower()
            if raw in QUIT_FLAGS:  raise SystemExit
            if raw in DONE_FLAGS:  return moves
            if raw in VALID_AXES:  axis = raw; break
            print(f"  [!] Choose from: {', '.join(sorted(VALID_AXES)).upper()}")

        steps = ask_int(f"  Number of steps for {axis.upper()}: ")
        if steps is None: return moves

        direction    = ask_direction(f"  Direction for {axis.upper()} [+ / -]: ")
        signed_speed = direction * abs_speed
        moves.append({"axis": axis, "pulses": pulses, "speed": signed_speed,
                      "steps": steps})
        print(f"  [+] Queued: axis={axis.upper()}  pulses={pulses}  "
              f"speed={signed_speed:+d}  steps={steps}\n")


def execute_moves(motors, moves):
    """Execute all queued moves sequentially."""
    if not moves:
        print("\n  [i] No moves queued – nothing to execute.\n")
        return

    expanded = []
    for move in moves:
        steps = move.get("steps", 1)
        for _ in range(steps):
            expanded.append({"axis": move["axis"],
                              "pulses": move["pulses"],
                              "speed": move["speed"]})

    print(f"\n-- Executing {len(expanded)} move(s) --")
    for i, move in enumerate(expanded, start=1):
        axis, pulses, speed = move["axis"], move["pulses"], move["speed"]
        print(f"\n  [{i}/{len(expanded)}] Axis {axis.upper()} "
              f"-> {pulses} pulses @ {speed:+d} pulse/s")

        motor = motors.get(axis)
        if motor is None:
            print(f"  [!] No motor registered for axis {axis.upper()}. Skipping.")
            continue

        try:
            motor.move(pulses=pulses, speed=speed, wait=True)
            pos = motor.get_position()
            print(f"  [OK] Done. Current position: {pos} pulses")
        except Exception as exc:
            print(f"  [ERR] Axis {axis.upper()}: {exc}")

        if i < len(expanded):
            time.sleep(STEP_DELAY)

    print("\n-- All moves completed --\n")


def setup_motors():
    """Connect all motors defined in AXES. Returns dict of successful connections."""
    motors = {}
    print("-- Connecting motors --")
    for axis, address in AXES.items():
        motor = Motor(axis=axis, address=address)
        try:
            motor.connect()
            motors[axis] = motor
        except Exception as exc:
            print(f"  [!] Could not connect axis {axis.upper()} ({address}): {exc}")
    return motors


def teardown_motors(motors):
    """Disconnect all connected motors gracefully."""
    print("\n-- Disconnecting motors --")
    for motor in motors.values():
        motor.disconnect()


def run_motors(motors):
    """Full motor workflow: choose mode → collect moves → execute."""
    print("\n" + "-" * 55)
    print("  Motion Control System")
    print("-" * 55)

    mode  = select_mode()
    moves = collect_moves_mode_a() if mode == "a" else collect_moves_mode_b()

    if not moves:
        confirm = input("\n  No moves entered. Back to menu? [Y/n]: ").strip().lower()
        if confirm in ("n", "no"):
            raise SystemExit
        return

    execute_moves(motors, moves)


# =================================================================
# ENTRY POINT
# =================================================================

def main():
    motors = setup_motors()

    if not motors:
        print("\n[!] No motors available. Check connections and try again.")
        sys.exit(1)

    print(f"\n  Connected axes: {', '.join(k.upper() for k in sorted(motors))}\n")

    try:
        while True:
            print_banner()
            choice = select_top_menu()

            if choice == "1":
                run_motors(motors)
            elif choice == "2":
                run_oscilloscope()
            elif choice == "3":
                run_power_meter()

            again = input("\n  Back to main menu? [Y/n]: ").strip().lower()
            if again in ("n", "no"):
                break

    except (SystemExit, KeyboardInterrupt):
        print("\n\n  [i] Exit requested by user.")
    finally:
        teardown_motors(motors)
        print("\n  Goodbye.\n")


if __name__ == "__main__":
    main()
